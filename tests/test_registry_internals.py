from __future__ import annotations

import pytest

from openatoms.errors import OrderingConstraintError, ReactionFeasibilityError
from openatoms.sim.registry.kinetics_sim import VirtualReactor
from openatoms.sim.registry.opentrons_sim import OT2Simulator, OpentronsSimValidator
from openatoms.sim.types import ReactionTrajectory
from openatoms.units import Q_


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

    def __getitem__(self, species: str):
        return type("SpeciesView", (), {"X": [self._x.get(species, 0.0)]})()


class _FakeSolution(_FakeThermo):
    def __init__(self, _mechanism: str):
        super().__init__(
            temperature=300.0,
            pressure=101325.0,
            composition={"H2": 0.5, "O2": 0.25, "N2": 0.25, "N": 0.0},
        )
        self.source = "fake.yaml"

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
        else:
            self._x = dict(composition)

    @property
    def TP(self):
        return self.T, self.P

    @TP.setter
    def TP(self, values):
        self.T, self.P = values

    def equilibrate(self, mode: str):
        if mode in {"UV", "HP"}:
            self.T = self.T + 200.0
            self.P = self.P + (500.0 if mode == "UV" else 0.0)
            for species in list(self._x.keys()):
                self._x[species] = max(self._x[species] * 0.95, 0.0)
            self._x.setdefault("H2O", 0.1)
            self.species_names = list(self._x.keys())
            self.chemical_potentials = [1000.0 + idx for idx, _ in enumerate(self.species_names)]


class _FakeCantera:
    Solution = _FakeSolution
    __version__ = "fake-cantera-1.0"

    @staticmethod
    def IdealGasReactor(gas, energy="on"):
        return type("FakeReactor", (), {"thermo": gas})()

    @staticmethod
    def IdealGasConstPressureReactor(gas, energy="on"):
        return type("FakeReactor", (), {"thermo": gas})()

    @staticmethod
    def get_data_directories():
        return []

    class ReactorNet:
        def __init__(self, reactors):
            self.reactor = reactors[0]
            self.time = 0.0
            self.rtol = 1.0e-9
            self.atol = 1.0e-15
            self.max_time_step = 1.0e-3

        def step(self):
            dt = max(self.max_time_step, 1.0e-6)
            self.time += dt
            self.reactor.thermo.T += 5000.0 * dt
            self.reactor.thermo.P += 1000.0 * dt
            return self.time


def test_virtual_reactor_simulate_and_gibbs(monkeypatch) -> None:
    monkeypatch.setattr(VirtualReactor, "_load_cantera", staticmethod(lambda: _FakeCantera))

    reactor = VirtualReactor(mechanism="fake.yaml")
    trajectory = reactor.simulate_reaction(
        reactants={"H2": 2.0, "O2": 1.0, "N2": 3.76},
        mechanism="fake.yaml",
        T_initial=Q_(1000, "kelvin"),
        P_initial=Q_(1, "atm"),
        duration=Q_(0.2, "second"),
        reactor_type="IdealGasReactor",
    )
    assert len(trajectory.times_s) > 10

    spontaneous, delta_g = reactor.check_gibbs_feasibility(
        reactants={"N2": 1.0},
        products={"N": 2.0},
        T=Q_(300, "kelvin"),
        P=Q_(1, "atm"),
    )
    assert spontaneous is False
    assert delta_g.to("kilojoule/mole").magnitude > 0


def test_virtual_reactor_unknown_species_raises(monkeypatch) -> None:
    monkeypatch.setattr(VirtualReactor, "_load_cantera", staticmethod(lambda: _FakeCantera))
    reactor = VirtualReactor(mechanism="fake.yaml")

    with pytest.raises(ReactionFeasibilityError):
        reactor.check_gibbs_feasibility(
            reactants={"XYZ": 1.0},
            products={"ABC": 1.0},
            T=Q_(300, "kelvin"),
            P=Q_(1, "atm"),
        )


def test_thermal_runaway_detection() -> None:
    reactor = VirtualReactor(mechanism="h2o2.yaml")
    trajectory = ReactionTrajectory(
        times_s=[0.0, 0.05, 0.1, 0.15, 0.2],
        temperatures_k=[300.0, 320.0, 350.0, 400.0, 460.0],
        pressures_pa=[101325.0] * 5,
        species_mole_fractions={"H2": [0.5] * 5},
        heat_release_rate_w_m3=[0.0] * 5,
        solver_rtol=1.0e-9,
        solver_atol=1.0e-15,
        mechanism_file="h2o2.yaml",
        mechanism_hash="0" * 64,
        cantera_version="3.0.0",
        integrator="CVODE",
    )
    error = reactor.check_thermal_runaway(trajectory)
    assert error is not None


def test_opentrons_deck_collision_and_missing_file() -> None:
    simulator = OT2Simulator()
    collisions = simulator.check_deck_collisions(
        {
            "plate1": {"slot": "1"},
            "plate2": {"slot": "1"},
        }
    )
    assert collisions

    result = OpentronsSimValidator().validate_protocol("/tmp/does-not-exist-protocol.py")
    assert result["error"] is not None
    assert "state_observation_json" in result
