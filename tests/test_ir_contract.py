import json

from openatoms.actions import Move
from openatoms.core import Container, Matter, Phase
from openatoms.dag import ProtocolGraph
from openatoms.ir import IR_VERSION, canonical_json, load_ir_payload, validate_protocol_payload


def _graph() -> ProtocolGraph:
    source = Container("Source", max_volume_ml=100, max_temp_c=100)
    destination = Container("Destination", max_volume_ml=100, max_temp_c=100)
    source.contents.append(Matter("H2O", Phase.LIQUID, 20, 20))

    graph = ProtocolGraph("IR_Contract")
    graph.add_step(Move(source, destination, 5))
    assert graph.dry_run() is True
    return graph


def test_exported_ir_validates():
    payload = json.loads(_graph().export_json())
    assert payload["ir_version"] == IR_VERSION
    assert payload["schema_version"] == IR_VERSION
    validate_protocol_payload(payload)


def test_old_ir_versions_load_within_support_window():
    old = {
        "protocol_name": "Legacy",
        "version": "1.0.0",
        "steps": [{"action_type": "Move", "parameters": {"amount_ml": 1}}],
    }
    normalized = load_ir_payload(json.dumps(old))
    assert normalized["ir_version"] == "1.1.0"
    assert normalized["steps"][0]["step_id"] == "s1"


def test_golden_ir_export_is_stable():
    payload1 = json.loads(_graph().export_json())
    payload2 = json.loads(_graph().export_json())
    assert canonical_json(payload1) == canonical_json(payload2)


def test_references_include_stable_ids():
    payload = json.loads(_graph().export_json())
    container_refs = payload["references"]["containers"]
    assert all("id" in item for item in container_refs)
    assert all(item["id"].startswith("container_") for item in container_refs)
