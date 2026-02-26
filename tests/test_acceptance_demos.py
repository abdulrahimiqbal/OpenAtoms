import json

import pytest

from openatoms.actions import Move, Transform
from openatoms.adapters import HomeAssistantAdapter, OpentronsAdapter
from openatoms.core import Container, Matter, Phase
from openatoms.dag import ProtocolGraph
from openatoms.exceptions import StructuralIntegrityError, ThermodynamicViolationError
from openatoms.runner import ProtocolRunner
from openatoms.sim.registry.kinetics_sim import Vessel, VirtualReactor


def _build_graph(temp: float) -> ProtocolGraph:
    source = Container("Source", max_volume_ml=100, max_temp_c=100)
    dest = Container("Dest", max_volume_ml=100, max_temp_c=80)
    source.contents.append(Matter("H2O", Phase.LIQUID, mass_g=20, volume_ml=20))
    graph = ProtocolGraph("Acceptance")
    graph.add_step(Move(source, dest, 10))
    graph.add_step(Transform(dest, "temperature_c", temp, 30))
    return graph


def test_self_correcting_agent_loop_demo():
    with pytest.raises(ThermodynamicViolationError) as exc:
        _build_graph(250).dry_run()
    payload = exc.value.to_agent_payload()
    assert '"error_type": "ThermodynamicViolationError"' in payload

    corrected = _build_graph(70)
    assert corrected.dry_run() is True


def test_one_ir_to_multiple_targets_with_consistent_provenance():
    graph = _build_graph(60)
    op_result = ProtocolRunner(OpentronsAdapter()).run(graph)
    ha_result = ProtocolRunner(HomeAssistantAdapter()).run(graph)

    assert "protocol_script" in op_result
    assert "service_calls" in ha_result
    assert op_result["provenance"]["ir_hash"] == ha_result["provenance"]["ir_hash"]


def test_thermo_safety_envelope_blocks_unsafe_scenario(monkeypatch, tmp_path):
    class FakeSolution:
        def __init__(self, _mechanism):
            self.T = 300.0
            self.P = 101325.0
            self._x = ""

        @property
        def TPX(self):
            return self.T, self.P, self._x

        @TPX.setter
        def TPX(self, values):
            self.T, self.P, self._x = values

    class FakeReactor:
        def __init__(self, gas, **_kwargs):
            self.thermo = gas

    class FakeReactorNet:
        def __init__(self, reactors):
            self.reactor = reactors[0]

        def step(self):
            self.reactor.thermo.P = 3_000_000.0
            self.reactor.thermo.T = 900.0
            return 0.02

    class FakeCantera:
        Solution = FakeSolution
        IdealGasReactor = FakeReactor
        ReactorNet = FakeReactorNet

    monkeypatch.setattr(
        VirtualReactor,
        "_load_cantera",
        staticmethod(lambda: FakeCantera),
    )

    reactor = VirtualReactor()
    vessel = Vessel(name="Pressure_Test", burst_pressure_pa=2_000_000.0)

    with pytest.raises(StructuralIntegrityError) as exc:
        reactor.simulate_hydrogen_oxygen_combustion(initial_temp_k=800.0, vessel=vessel)

    observation = json.loads(exc.value.details["state_observation_json"])
    artifact = tmp_path / "observation.json"
    artifact.write_text(json.dumps(observation, indent=2), encoding="utf-8")
    assert observation["status"] == "failed"
    assert observation["errors"][0]["type"] == "StructuralIntegrityError"
    assert artifact.exists()
