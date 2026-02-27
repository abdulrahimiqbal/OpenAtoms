from __future__ import annotations

import warnings

import pytest

from openatoms.errors import ReactionFeasibilityError
from openatoms.sim.registry.kinetics_sim import VirtualReactor
from openatoms.units import Q_


class _FakeSolution:
    def __init__(self, _mechanism: str):
        self.species_names = ["H2", "O2", "H2O", "N2"]
        self._composition = {"H2": 0.5, "O2": 0.3, "H2O": 0.2, "N2": 0.0}
        self.chemical_potentials = [0.0 for _ in self.species_names]
        self.T = 300.0
        self.P = 101325.0
        self.source = "fake.yaml"

    @property
    def TPX(self):
        return self.T, self.P, self._composition

    @TPX.setter
    def TPX(self, values):
        self.T, self.P, composition = values
        parsed: dict[str, float] = {}
        for token in str(composition).split(","):
            name, value = token.split(":")
            parsed[name] = float(value)
        self._composition = parsed
        self.species_names = list(parsed.keys())
        # Synthetic, deterministic state-dependent chemical potentials.
        self.chemical_potentials = [
            1000.0 + (100.0 * parsed[species]) + index
            for index, species in enumerate(self.species_names)
        ]

    def species_index(self, species: str) -> int:
        return self.species_names.index(species)

    def mole_fraction_dict(self):
        return dict(self._composition)

    def __getitem__(self, species: str):
        return type("SpeciesView", (), {"X": [self._composition.get(species, 0.0)]})()


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


def test_affinity_heuristic_is_explicitly_state_defined(monkeypatch) -> None:
    monkeypatch.setattr(VirtualReactor, "_load_cantera", staticmethod(lambda: _FakeCantera))
    reactor = VirtualReactor(mechanism="fake.yaml")

    favorable_a, delta_g_a = reactor.estimate_reaction_affinity_heuristic(
        reactants={"H2": 1.0, "O2": 0.5},
        products={"H2O": 1.0},
        composition={"H2": 0.6, "O2": 0.3, "H2O": 0.1},
        T=Q_(300, "kelvin"),
        P=Q_(1.0, "atm"),
    )
    favorable_b, delta_g_b = reactor.estimate_reaction_affinity_heuristic(
        reactants={"H2": 1.0, "O2": 0.5},
        products={"H2O": 1.0},
        composition={"H2": 0.1, "O2": 0.1, "H2O": 0.8},
        T=Q_(300, "kelvin"),
        P=Q_(1.0, "atm"),
    )

    assert isinstance(favorable_a, bool)
    assert isinstance(favorable_b, bool)
    assert delta_g_a != delta_g_b


def test_affinity_heuristic_rejects_empty_composition(monkeypatch) -> None:
    monkeypatch.setattr(VirtualReactor, "_load_cantera", staticmethod(lambda: _FakeCantera))
    reactor = VirtualReactor(mechanism="fake.yaml")
    with pytest.raises(ReactionFeasibilityError):
        reactor.estimate_reaction_affinity_heuristic(
            reactants={"H2": 1.0},
            products={"H2O": 1.0},
            composition={},
            T=Q_(300, "kelvin"),
            P=Q_(1.0, "atm"),
        )


def test_legacy_gibbs_check_is_deprecated_wrapper(monkeypatch) -> None:
    monkeypatch.setattr(VirtualReactor, "_load_cantera", staticmethod(lambda: _FakeCantera))
    reactor = VirtualReactor(mechanism="fake.yaml")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        favorable, delta_g = reactor.check_gibbs_feasibility(
            reactants={"H2": 1.0, "O2": 0.5},
            products={"H2O": 1.0},
            T=Q_(300, "kelvin"),
            P=Q_(1.0, "atm"),
        )

    assert isinstance(favorable, bool)
    assert delta_g.check("[mass] * [length] ** 2 / [time] ** 2 / [substance]")
    assert any(issubclass(item.category, DeprecationWarning) for item in caught)
