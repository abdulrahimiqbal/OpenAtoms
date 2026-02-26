from __future__ import annotations

import json
from importlib.util import find_spec
from pathlib import Path

import pytest

from openatoms import create_bundle, replay_bundle

from ._bundle_test_utils import build_minimal_protocol


def _missing_optional_simulator() -> str | None:
    if find_spec("cantera") is None:
        return "cantera"
    if find_spec("mujoco") is None:
        return "mujoco"
    return None


def test_bundle_replay_equivalence_strict(tmp_path: Path) -> None:
    missing_sim = _missing_optional_simulator()
    if missing_sim is None:
        pytest.skip("requires at least one missing optional simulator dependency")

    bundle_dir = tmp_path / "bundle"
    create_bundle(
        output_path=bundle_dir,
        protocol=build_minimal_protocol("replay_demo"),
        deterministic=True,
        simulators=[missing_sim],
    )

    replay_report = replay_bundle(
        bundle_dir,
        protocol=build_minimal_protocol("replay_demo"),
        strict=True,
    )
    assert replay_report.ok is True

    recorded = json.loads(
        (bundle_dir / "checks" / "simulators" / missing_sim / "report.json").read_text(
            encoding="utf-8"
        )
    )
    assert recorded["status"] == "skipped"
    replayed = replay_report.checks["simulators"][missing_sim]
    assert replayed["status"] == "skipped"
    assert replayed == recorded
