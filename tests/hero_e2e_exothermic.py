"""Exothermic stress-test e2e scenario for science-mode dry runs."""

from __future__ import annotations

import json
import sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openatoms.actions import Transform
from openatoms.core import Container
from openatoms.dag import ProtocolGraph
from openatoms.exceptions import StructuralIntegrityError
from openatoms.sim.registry.kinetics_sim import Vessel, VirtualReactor


class _FakeSolution:
    def __init__(self, _mechanism: str):
        self.T = 300.0
        self.P = 101325.0
        self.composition = ""

    @property
    def TPX(self):
        return self.T, self.P, self.composition

    @TPX.setter
    def TPX(self, values):
        self.T, self.P, self.composition = values


class _FakeReactor:
    def __init__(self, gas: _FakeSolution, **_kwargs):
        self.thermo = gas


class _FakeReactorNet:
    def __init__(self, reactors):
        self.reactor = reactors[0]
        self.time_s = 0.0
        self.initial_t = float(self.reactor.thermo.T)
        self.initial_p = float(self.reactor.thermo.P)

    def step(self):
        self.time_s += 0.002

        if self.initial_t >= 780.0:
            pressure_multiplier = 24.0
            temp_rise_k = 260.0
        elif self.initial_t >= 500.0:
            pressure_multiplier = 5.0
            temp_rise_k = 90.0
        else:
            pressure_multiplier = 1.15
            temp_rise_k = 15.0

        self.reactor.thermo.P = self.initial_p * pressure_multiplier
        self.reactor.thermo.T = self.initial_t + temp_rise_k
        return self.time_s


class _FakeCantera:
    Solution = _FakeSolution
    IdealGasReactor = _FakeReactor
    ReactorNet = _FakeReactorNet


def _run_exothermic_stress_test() -> tuple[dict, dict]:
    max_pressure_pa = 2.0e6
    vessel = Vessel(name="Pressure_Vessel_20atm", burst_pressure_pa=max_pressure_pa)

    unsafe_target_k = 800.0
    unsafe_target_c = unsafe_target_k - 273.15
    safe_target_k = 400.0
    safe_target_c = safe_target_k - 273.15

    original_simulate = VirtualReactor.simulate_hydrogen_oxygen_combustion

    def _simulate_with_vessel(self, **kwargs):
        self.composition = "H2:2,O2:1"
        kwargs.setdefault("vessel", vessel)
        return original_simulate(self, **kwargs)

    with ExitStack() as stack:
        stack.enter_context(
            patch.object(
                VirtualReactor,
                "_load_cantera",
                staticmethod(lambda: _FakeCantera),
            )
        )
        stack.enter_context(
            patch.object(
                VirtualReactor,
                "simulate_hydrogen_oxygen_combustion",
                _simulate_with_vessel,
            )
        )

        # Explicit gas object setup for the stress-test scenario.
        ct = VirtualReactor._load_cantera()
        gas = ct.Solution("h2o2.yaml")
        gas.TPX = 300.0, 101325.0, "H2:2,O2:1"

        reactor_vessel = Container(
            "Hero_Stress_Reactor",
            max_volume_ml=50.0,
            max_temp_c=700.0,
        )

        first_attempt = ProtocolGraph("Exothermic_Stress_Attempt_1")
        first_attempt.add_step(
            Transform(
                target=reactor_vessel,
                parameter="temperature_c",
                target_value=unsafe_target_c,
                duration_s=30.0,
            )
        )

        try:
            first_attempt.dry_run(mode="science")
        except StructuralIntegrityError as exc:
            failure_observation = json.loads(exc.details["state_observation_json"])
        else:
            raise AssertionError(
                "Expected StructuralIntegrityError for 800K exothermic attempt."
            )
        print("Failure StateObservation JSON:")
        print(json.dumps(failure_observation, indent=2))

        agent_limits = {
            "pressure_limit_pa": vessel.burst_pressure_pa,
            "temperature_limit_k": safe_target_k,
            "attempted_temperature_k": unsafe_target_k,
        }
        print("Agent received limits:")
        print(json.dumps(agent_limits, indent=2))
        print("Agent recovery plan: Lower the target temperature to 400K.")

        second_attempt = ProtocolGraph("Exothermic_Stress_Attempt_2")
        second_attempt.add_step(
            Transform(
                target=reactor_vessel,
                parameter="temperature_c",
                target_value=safe_target_c,
                duration_s=30.0,
            )
        )

        assert second_attempt.dry_run(mode="science") is True
        success_observation = json.loads(
            second_attempt.sequence[0].state_observation_json
        )
        print("Success StateObservation JSON:")
        print(json.dumps(success_observation, indent=2))

    return failure_observation, success_observation


def test_hero_e2e_exothermic_stress_recovery():
    failure_observation, success_observation = _run_exothermic_stress_test()

    assert failure_observation["type"] == "StateObservation"
    assert failure_observation["status"] == "failed"
    assert failure_observation["errors"][0]["type"] == "StructuralIntegrityError"
    assert (
        failure_observation["errors"][0]["details"]["observed_pressure_pa"]
        > 2.0e6
    )

    assert success_observation["type"] == "StateObservation"
    assert success_observation["status"] == "ok"
    assert success_observation["state"]["pressure_pa"] < 2.0e6


if __name__ == "__main__":
    test_hero_e2e_exothermic_stress_recovery()
