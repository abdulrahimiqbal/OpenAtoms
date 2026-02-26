import json

from openatoms.actions import Move
from openatoms.core import Container, Matter, Phase
from openatoms.dag import ProtocolGraph
from openatoms.provenance import new_run_context
from openatoms.replay import replay_signature
from openatoms.sim.harness import SimulationHarness


def _graph() -> ProtocolGraph:
    source = Container("A", max_volume_ml=100, max_temp_c=100)
    destination = Container("B", max_volume_ml=100, max_temp_c=100)
    source.contents.append(Matter("H2O", Phase.LIQUID, 10, 10))
    graph = ProtocolGraph("Deterministic")
    graph.add_step(Move(source, destination, 5))
    graph.dry_run()
    return graph


def test_same_ir_seed_and_sim_version_produce_same_observation():
    graph = _graph()
    harness = SimulationHarness(simulator_version="sim-v1")
    ctx1 = new_run_context(seed=11, simulator_version="sim-v1")
    ctx2 = new_run_context(seed=11, simulator_version="sim-v1")

    obs1 = harness.run(dag=graph, run_context=ctx1)["observation"]
    obs2 = harness.run(dag=graph, run_context=ctx2)["observation"]

    assert obs1["state"] == obs2["state"]
    assert obs1["status"] == obs2["status"]


def test_replay_signature_is_stable():
    payload = json.loads(_graph().export_json())
    sig1 = replay_signature(ir_payload=payload, simulator_version="sim-v1", seed=77)
    sig2 = replay_signature(ir_payload=payload, simulator_version="sim-v1", seed=77)
    assert sig1 == sig2
