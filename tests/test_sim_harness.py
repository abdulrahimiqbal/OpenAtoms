from pathlib import Path

from openatoms.actions import Move
from openatoms.core import Container, Matter, Phase
from openatoms.dag import ProtocolGraph
from openatoms.provenance import new_run_context
from openatoms.sim.harness import SimulationHarness, SimulationThresholds


def _graph(step_count: int = 1) -> ProtocolGraph:
    source = Container("A", max_volume_ml=500, max_temp_c=120)
    destination = Container("B", max_volume_ml=500, max_temp_c=120)
    source.contents.append(Matter("H2O", Phase.LIQUID, 200, 200))

    graph = ProtocolGraph("Sim_Harness")
    for _ in range(step_count):
        graph.add_step(Move(source, destination, 1))
    graph.dry_run()
    return graph


def test_sim_harness_contract_shape():
    harness = SimulationHarness()
    result = harness.run(dag=_graph(), run_context=new_run_context(seed=1))
    assert "status" in result
    assert "observation" in result
    assert result["observation"]["type"] == "StateObservation"
    assert result["observation"]["schema_version"] == "1.0.0"


def test_sim_harness_regression_threshold_is_stable():
    harness = SimulationHarness(simulator_version="sim-v1")
    graph = _graph(step_count=3)
    context = new_run_context(seed=42, simulator_version="sim-v1")
    thresholds = SimulationThresholds(max_temperature_c=120.0, max_pressure_pa=2_000_000.0)
    result = harness.run(dag=graph, run_context=context, thresholds=thresholds)
    assert result["status"] == "ok"


def test_state_observation_artifact_storage(tmp_path: Path):
    harness = SimulationHarness()
    result = harness.run(dag=_graph(), run_context=new_run_context(seed=8))
    target = tmp_path / "provenance" / "state_observation.json"
    harness.write_observation(target, result["observation"])
    assert target.exists()
