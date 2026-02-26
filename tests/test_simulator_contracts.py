from __future__ import annotations

import math
from importlib.util import find_spec
from types import SimpleNamespace

import pytest

from openatoms.actions import Move
from openatoms.core import Container, Matter, Phase
from openatoms.errors import OrderingConstraintError, SimulationDependencyError
from openatoms.dag import ProtocolGraph
from openatoms.sim.registry.kinetics_sim import VirtualReactor
import openatoms.sim.registry.robotics_sim as robotics_module
from openatoms.sim.registry.opentrons_sim import OT2Simulator
from openatoms.sim.registry.robotics_sim import MUJOCO_AVAILABLE, RoboticsSimulator
from openatoms.sim.types import Pose
from openatoms.units import Q_


def _well(well_id: str) -> Container:
    return Container(
        id=well_id,
        label=well_id,
        max_volume=Q_(300, "microliter"),
        max_temp=Q_(70, "degC"),
        min_temp=Q_(4, "degC"),
    )


class _FakeThermo:
    def __init__(self, temperature: float, pressure: float, composition: dict[str, float]):
        self.T = temperature
        self.P = pressure
        self._x = composition
        self.species_names = list(composition.keys())
        self.chemical_potentials = [1000.0 + idx for idx, _ in enumerate(self.species_names)]

    def mole_fraction_dict(self):
        return dict(self._x)

    def species_index(self, species: str) -> int:
        return self.species_names.index(species)


class _FakeSolution(_FakeThermo):
    def __init__(self, _mechanism: str):
        super().__init__(temperature=300.0, pressure=101325.0, composition={"H2": 0.5, "O2": 0.25, "N2": 0.25})

    @property
    def TPX(self):
        return self.T, self.P, self._x

    @TPX.setter
    def TPX(self, values):
        t, p, composition = values
        self.T = t
        self.P = p
        if isinstance(composition, str):
            parsed = {}
            for token in composition.split(","):
                name, value = token.split(":")
                parsed[name] = float(value)
            self._x = parsed
            self.species_names = list(parsed.keys())
            self.chemical_potentials = [1000.0 + idx for idx, _ in enumerate(self.species_names)]

    @property
    def TP(self):
        return self.T, self.P

    @TP.setter
    def TP(self, values):
        self.T, self.P = values

    def equilibrate(self, mode: str):
        if mode in {"UV", "HP"}:
            self.T = self.T + 150.0
            self.P = self.P + (250.0 if mode == "UV" else 0.0)
            for species in list(self._x.keys()):
                self._x[species] = max(self._x[species] * 0.96, 0.0)
            self._x.setdefault("H2O", 0.05)
            self.species_names = list(self._x.keys())
            self.chemical_potentials = [1000.0 + idx for idx, _ in enumerate(self.species_names)]


class _FakeCantera:
    Solution = _FakeSolution

    @staticmethod
    def IdealGasReactor(gas, energy="on"):
        return SimpleNamespace(thermo=gas)

    @staticmethod
    def IdealGasConstPressureReactor(gas, energy="on"):
        return SimpleNamespace(thermo=gas)


def test_ot2_contract_is_deterministic_and_has_stable_error_code() -> None:
    a1, a2 = _well("A1"), _well("A2")
    a1.contents.append(Matter(name="w", phase=Phase.LIQUID, mass=Q_(150, "milligram"), volume=Q_(150, "microliter")))
    graph = ProtocolGraph("ot2_contract")
    graph.add_step(Move(a1, a2, Q_(200, "microliter")))

    simulator = OT2Simulator()
    first = simulator.run(graph)
    second = simulator.run(graph)

    assert first.to_json() == second.to_json()
    assert first.errors[0].error_code == "VOL_001"


def test_virtual_reactor_contract_is_deterministic(monkeypatch) -> None:
    monkeypatch.setattr(VirtualReactor, "_load_cantera", staticmethod(lambda: _FakeCantera))

    reactor = VirtualReactor(mechanism="fake.yaml")
    first = reactor.simulate_reaction(
        reactants={"H2": 2.0, "O2": 1.0, "N2": 3.76},
        mechanism="fake.yaml",
        T_initial=Q_(800, "kelvin"),
        P_initial=Q_(1, "atm"),
        duration=Q_(0.1, "second"),
        reactor_type="IdealGasReactor",
    )
    second = reactor.simulate_reaction(
        reactants={"H2": 2.0, "O2": 1.0, "N2": 3.76},
        mechanism="fake.yaml",
        T_initial=Q_(800, "kelvin"),
        P_initial=Q_(1, "atm"),
        duration=Q_(0.1, "second"),
        reactor_type="IdealGasReactor",
    )
    assert first == second


def test_virtual_reactor_missing_cantera_has_install_hint(monkeypatch) -> None:
    import builtins

    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "cantera":
            raise ImportError("simulated missing cantera")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(SimulationDependencyError) as exc_info:
        VirtualReactor._load_cantera()
    assert 'pip install ".[sim-cantera]"' in exc_info.value.remediation_hint


@pytest.mark.skipif(find_spec("cantera") is None, reason="requires cantera")
def test_cantera_golden_tiny_system() -> None:
    reactor = VirtualReactor(mechanism="h2o2.yaml")
    output = reactor.simulate_hydrogen_oxygen_combustion(initial_temp_k=900.0, residence_time_s=0.02)
    trajectory = output["trajectory"]
    assert math.isclose(max(trajectory.temperatures_k), 1994.9656575997055, rel_tol=0.10)
    assert math.isclose(max(trajectory.pressures_pa), 204431.8268276758, rel_tol=0.10)


def test_robotics_contract_is_deterministic_and_reports_expected_error_code() -> None:
    simulator = RoboticsSimulator()
    safe_waypoints = [Pose(x_m=0.1, y_m=0.1, z_m=0.2), Pose(x_m=0.15, y_m=0.1, z_m=0.2)]

    first = simulator.simulate_arm_trajectory(safe_waypoints, payload_mass=Q_(0.1, "kilogram"), mode="analytical")
    second = simulator.simulate_arm_trajectory(safe_waypoints, payload_mass=Q_(0.1, "kilogram"), mode="analytical")
    assert first == second

    with pytest.raises(OrderingConstraintError) as exc_info:
        simulator.simulate_arm_trajectory(
            [Pose(x_m=1.0, y_m=0.0, z_m=0.2)],
            payload_mass=Q_(2.0, "kilogram"),
            mode="analytical",
        )
    assert exc_info.value.error_code == "ORD_001"


def test_robotics_mujoco_mode_dependency_hint() -> None:
    if MUJOCO_AVAILABLE:
        pytest.skip("mujoco installed; dependency-path test applies only when absent")

    simulator = RoboticsSimulator()
    with pytest.raises(SimulationDependencyError) as exc_info:
        simulator.simulate_arm_trajectory(
            [Pose(x_m=0.1, y_m=0.1, z_m=0.2)],
            payload_mass=Q_(0.1, "kilogram"),
            mode="mujoco",
        )
    assert 'pip install ".[sim-mujoco]"' in exc_info.value.remediation_hint


def test_robotics_mujoco_mode_changes_behavior_when_available(monkeypatch) -> None:
    simulator = RoboticsSimulator()
    monkeypatch.setattr(robotics_module, "MUJOCO_AVAILABLE", True)

    waypoints = [Pose(x_m=0.1, y_m=0.1, z_m=0.2)]
    auto_result = simulator.simulate_arm_trajectory(waypoints, payload_mass=Q_(0.1, "kilogram"), mode="auto")
    analytical_result = simulator.simulate_arm_trajectory(waypoints, payload_mass=Q_(0.1, "kilogram"), mode="analytical")
    assert auto_result.mode == "mujoco+analytical"
    assert analytical_result.mode == "analytical"
