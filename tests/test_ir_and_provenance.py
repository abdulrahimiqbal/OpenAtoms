import json

import jsonschema

from openatoms.ir import IR_VERSION, canonical_json, ir_hash, load_schema, validate_ir
from openatoms.ir.provenance import attach_ir_hash


def _payload() -> dict:
    payload = {
        "ir_version": IR_VERSION,
        "protocol_id": "00000000-0000-0000-0000-000000000000",
        "correlation_id": "00000000-0000-0000-0000-000000000001",
        "created_at": "2026-01-01T00:00:00+00:00",
        "steps": [
            {
                "step": 1,
                "step_id": "s1",
                "action_type": "Move",
                "parameters": {"amount": {"value": 1, "unit": "microliter"}},
                "depends_on": [],
                "resources": [],
            }
        ],
        "provenance": {
            "ir_hash": "0" * 64,
            "simulator_versions": {"bio_kinetic": "1.0.0"},
            "noise_seed": 42,
            "validator_version": "1.1.0",
        },
    }
    return attach_ir_hash(payload)


def test_ir_schema_loads_and_validates() -> None:
    schema = load_schema()
    assert schema["title"] == "OpenAtoms Protocol IR"
    jsonschema.Draft7Validator.check_schema(schema)

    payload = _payload()
    validate_ir(payload)
    assert len(ir_hash(payload)) == 64
    assert canonical_json(payload).startswith("{")


def test_ir_hash_is_stable() -> None:
    p1 = _payload()
    p2 = _payload()
    assert ir_hash(p1) == ir_hash(p2)
    assert json.loads(canonical_json(p1))["ir_version"] == IR_VERSION
