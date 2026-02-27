from __future__ import annotations

import importlib.util
import json
import os
import zipfile
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_DIR = ROOT / "examples" / "bci_verification_bottleneck"
RUN_EXAMPLE_PATH = EXAMPLE_DIR / "run_example.py"

# Keep tests deterministic and offline-safe; real API path is exercised in manual runs.
os.environ.setdefault("OPENATOMS_BCI_FORCE_LOCAL_LM", "1")


def _load_run_example_module():
    spec = importlib.util.spec_from_file_location("bci_run_example", RUN_EXAMPLE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load run_example.py module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_synthetic_derco(path: Path) -> Path:
    rng = np.random.default_rng(7)
    n_trials = 500
    n_channels = 16
    n_time = 256

    labels = rng.integers(low=0, high=2, size=n_trials)
    epochs = rng.normal(0.0, 1.0, size=(n_trials, n_channels, n_time))
    # Very weak passive effect (unexpected label 0): near-zero d'.
    epochs[labels == 0, :, 92:142] -= 0.003

    metadata = {
        "source": "pytest_synthetic_derco",
        "sfreq": 256.0,
        "tmin": -0.1,
    }

    np.savez(path, epochs=epochs, labels=labels, metadata=json.dumps(metadata, sort_keys=True))
    return path


@pytest.fixture(scope="session")
def bci_module():
    return _load_run_example_module()


@pytest.fixture(scope="session")
def derco_npz(tmp_path_factory: pytest.TempPathFactory) -> Path:
    data_dir = tmp_path_factory.mktemp("bci_derco")
    return _write_synthetic_derco(data_dir / "derco_n400.npz")


@pytest.fixture(scope="session")
def phase1_result(bci_module, derco_npz: Path) -> dict:
    return bci_module.phase1_reproduce_crossover(str(derco_npz))


@pytest.fixture(scope="session")
def phase2_result(bci_module) -> dict:
    return bci_module.phase2_test_scaling_law(bci_module.PANGRAM)


@pytest.fixture(scope="session")
def phase3_result(bci_module, derco_npz: Path) -> dict:
    return bci_module.phase3_closed_loop(str(derco_npz))


@pytest.fixture(scope="session")
def bundle_result(bci_module, derco_npz: Path, tmp_path_factory: pytest.TempPathFactory) -> dict:
    out_dir = tmp_path_factory.mktemp("bci_bundle")
    bundle_path = out_dir / "bci_verification_bottleneck_bundle.zip"
    return bci_module.run_all(str(derco_npz), output_bundle=bundle_path, seed=42)


def _read_manifest_from_zip(zip_path: Path) -> dict:
    with zipfile.ZipFile(zip_path, "r") as archive:
        manifest_members = [name for name in archive.namelist() if name.endswith("/manifest.json")]
        if not manifest_members:
            raise AssertionError("manifest.json missing from bundle")
        raw = archive.read(manifest_members[0]).decode("utf-8")
    return json.loads(raw)


def test_phase1_crossover_within_tolerance(phase1_result: dict) -> None:
    crossover = float(phase1_result["crossover_d_prime_measured"])
    assert 1.5 <= crossover <= 1.9


def test_phase2_claude_entropy_below_gpt2(phase2_result: dict) -> None:
    entropy = float(phase2_result["measured_entropy_bits"])
    assert entropy < 2.2


def test_phase2_speedup_exceeds_gpt2(phase2_result: dict) -> None:
    claude_speedup = float(phase2_result["empirical_speedups"]["claude"])
    assert claude_speedup > 2.3


def test_phase3_loop_converges(phase3_result: dict) -> None:
    iterations = phase3_result["iterations"]
    assert len(iterations) <= 10
    assert iterations[-1]["result"]["accepted"] is True


def test_phase3_rejected_proposals_recorded(phase3_result: dict) -> None:
    iterations = phase3_result["iterations"]
    rejected = [item for item in iterations if not item["result"]["accepted"]]
    assert len(rejected) >= 1


def test_bundle_contains_bci_check_type(bundle_result: dict) -> None:
    bundle_path = Path(bundle_result["bundle_path"])
    manifest = _read_manifest_from_zip(bundle_path)
    metadata = manifest.get("metadata", {})
    assert metadata.get("check_type") == "validated_simulation"


def test_bundle_contains_entropy_measurement(bundle_result: dict) -> None:
    bundle_path = Path(bundle_result["bundle_path"])
    manifest = _read_manifest_from_zip(bundle_path)
    metadata = manifest.get("metadata", {})
    lm_entropy_bits = metadata.get("lm_entropy_bits")
    assert isinstance(lm_entropy_bits, float)
    assert 0.5 <= lm_entropy_bits <= 3.0


def test_n400_d_prime_matches_paper(phase1_result: dict) -> None:
    passive = float(phase1_result["n400_passive"]["d_prime"])
    active = float(phase1_result["n400_active"]["d_prime"])
    assert passive < 0.1
    assert active < 0.35


def test_simulation_is_deterministic(bci_module, derco_npz: Path) -> None:
    run_a = bci_module.phase1_reproduce_crossover(str(derco_npz))
    run_b = bci_module.phase1_reproduce_crossover(str(derco_npz))
    assert run_a["crossover_d_prime_measured"] == run_b["crossover_d_prime_measured"]


def test_crossover_shifts_with_better_lm() -> None:
    module = _load_run_example_module()

    entropies = [2.2, 1.9, 1.6, 1.3, 1.0, 0.7]
    d_prime_range = np.linspace(0.1, 3.0, 30)

    crossovers: list[float] = []
    for entropy in entropies:
        result = module.compute_crossover_d_prime(
            lm_entropy_bits=entropy,
            d_prime_range=d_prime_range,
            n_trials_per_point=2200,
            seed=42,
        )
        crossovers.append(float(result["crossover_d_prime"]))

    assert all(crossovers[i + 1] >= crossovers[i] for i in range(len(crossovers) - 1))
