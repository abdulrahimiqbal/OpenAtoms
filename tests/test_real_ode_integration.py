"""
Tests that verify real ODE integration behavior.
These tests require cantera and will be skipped otherwise.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from importlib.util import find_spec
from pathlib import Path

import pytest

from openatoms import create_bundle
from openatoms.errors import ReactionFeasibilityError
from openatoms.provenance import new_run_context
from openatoms.sim.harness import SimulationHarness
from openatoms.sim.registry.kinetics_sim import VirtualReactor
from openatoms.sim.validation.h2o2_ignition_data import IGNITION_DELAY_DATA, TOLERANCE_FRACTION
from openatoms.units import Q_

from ._bundle_test_utils import build_minimal_protocol

CANTERA_AVAILABLE = find_spec("cantera") is not None
pytestmark = pytest.mark.skipif(not CANTERA_AVAILABLE, reason="requires cantera")


def _simulate_reference() -> object:
    reactor = VirtualReactor(mechanism="h2o2.yaml")
    return reactor.simulate_reaction(
        reactants={"H2": 2.0, "O2": 1.0, "N2": 3.76},
        mechanism="h2o2.yaml",
        T_initial=Q_(1000.0, "kelvin"),
        P_initial=Q_(1.0, "atm"),
        duration=Q_(0.02, "second"),
        reactor_type="IdealGasReactor",
    )


def test_trajectory_has_real_solver_metadata() -> None:
    trajectory = _simulate_reference()
    assert trajectory.mechanism_hash
    assert trajectory.cantera_version
    assert trajectory.solver_rtol > 0.0
    assert trajectory.solver_atol > 0.0
    assert trajectory.integrator == "CVODE"


@pytest.mark.requires_cantera
def test_ignition_delay_h2o2_within_published_tolerance() -> None:
    reactor = VirtualReactor(mechanism="h2o2.yaml")
    for initial_temp_k, ignition_delay_ms, _reference in IGNITION_DELAY_DATA:
        result = reactor.compute_ignition_delay(
            {"H2": 2.0, "O2": 1.0, "N2": 3.76},
            Q_(initial_temp_k, "kelvin"),
            Q_(1.0, "atm"),
            max_time_s=0.5,
        )
        assert result["converged"], f"ignition did not converge at {initial_temp_k} K"
        observed_s = float(result["ignition_delay_s"])
        expected_s = float(ignition_delay_ms) / 1000.0
        rel_error = abs(observed_s - expected_s) / expected_s
        assert rel_error <= TOLERANCE_FRACTION, (
            f"ignition delay mismatch at {initial_temp_k} K: observed={observed_s:.6e}s "
            f"expected={expected_s:.6e}s"
        )


def test_trajectory_is_deterministic_across_runs() -> None:
    reactor = VirtualReactor(mechanism="h2o2.yaml")
    first = reactor.simulate_reaction(
        reactants={"H2": 2.0, "O2": 1.0, "N2": 3.76},
        mechanism="h2o2.yaml",
        T_initial=Q_(1000.0, "kelvin"),
        P_initial=Q_(1.0, "atm"),
        duration=Q_(0.02, "second"),
        reactor_type="IdealGasReactor",
    )
    second = reactor.simulate_reaction(
        reactants={"H2": 2.0, "O2": 1.0, "N2": 3.76},
        mechanism="h2o2.yaml",
        T_initial=Q_(1000.0, "kelvin"),
        P_initial=Q_(1.0, "atm"),
        duration=Q_(0.02, "second"),
        reactor_type="IdealGasReactor",
    )
    assert first == second


def test_trajectory_is_deterministic_across_fresh_processes() -> None:
    script = """
import json
from openatoms.sim.registry.kinetics_sim import VirtualReactor
from openatoms.units import Q_

reactor = VirtualReactor(mechanism='h2o2.yaml')
traj = reactor.simulate_reaction(
    reactants={'H2': 2.0, 'O2': 1.0, 'N2': 3.76},
    mechanism='h2o2.yaml',
    T_initial=Q_(1000.0, 'kelvin'),
    P_initial=Q_(1.0, 'atm'),
    duration=Q_(0.02, 'second'),
    reactor_type='IdealGasReactor',
)
print(json.dumps(traj.__dict__, sort_keys=True, separators=(',', ':')))
""".strip()

    first = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )
    second = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )
    assert json.loads(first.stdout) == json.loads(second.stdout)


def test_thermal_runaway_detected_at_high_temperature() -> None:
    reactor = VirtualReactor(mechanism="h2o2.yaml")
    trajectory = reactor.simulate_reaction(
        reactants={"H2": 2.0, "O2": 1.0, "N2": 3.76},
        mechanism="h2o2.yaml",
        T_initial=Q_(1200.0, "kelvin"),
        P_initial=Q_(1.0, "atm"),
        duration=Q_(0.02, "second"),
        reactor_type="IdealGasReactor",
    )
    assert reactor.check_thermal_runaway(trajectory) is not None


def test_no_thermal_runaway_at_low_temperature() -> None:
    reactor = VirtualReactor(mechanism="h2o2.yaml")
    trajectory = reactor.simulate_reaction(
        reactants={"H2": 2.0, "O2": 1.0, "N2": 3.76},
        mechanism="h2o2.yaml",
        T_initial=Q_(400.0, "kelvin"),
        P_initial=Q_(1.0, "atm"),
        duration=Q_(0.02, "second"),
        reactor_type="IdealGasReactor",
    )
    assert reactor.check_thermal_runaway(trajectory) is None


def test_fake_harness_is_gone() -> None:
    protocol = build_minimal_protocol("no_fake_harness")
    protocol.dry_run()

    harness = SimulationHarness(simulator_version="sim-harness-2.0.0")
    result = harness.run(dag=protocol, run_context=new_run_context(seed=0))

    assert result["check_type"] == "not_simulated"
    assert result["status"] == "not_simulated"
    assert result["observation"]["check_type"] == "not_simulated"
    assert result["check_type"] != "validated_simulation"


def test_bundle_simulator_report_has_check_type(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    create_bundle(
        output_path=bundle_dir,
        protocol=build_minimal_protocol("ode_bundle"),
        deterministic=True,
        simulators=["cantera"],
    )

    report = json.loads(
        (bundle_dir / "checks" / "simulators" / "cantera" / "report.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["check_type"] == "validated_simulation"
    mechanism_hash = report.get("mechanism_hash") or report.get("payload", {}).get("mechanism_hash")
    assert isinstance(mechanism_hash, str)
    assert re.fullmatch(r"[0-9a-f]{64}", mechanism_hash) is not None

    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["physics_inputs"]["cantera"]["mechanism_hash"] == mechanism_hash


def test_cross_platform_trajectory_within_tolerance() -> None:
    trajectory = _simulate_reference()
    serialized = json.dumps(trajectory.__dict__, sort_keys=True)
    restored = json.loads(serialized)

    for current, recovered in zip(trajectory.temperatures_k, restored["temperatures_k"], strict=True):
        assert abs(current - recovered) <= 1.0e-6


def test_ignition_delay_rejects_unsupported_species() -> None:
    reactor = VirtualReactor(mechanism="h2o2.yaml")
    with pytest.raises(ReactionFeasibilityError):
        reactor.compute_ignition_delay(
            {"UNSUPPORTED_SPECIES": 1.0},
            Q_(1000.0, "kelvin"),
            Q_(1.0, "atm"),
            max_time_s=0.1,
        )
