from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from openatoms.ir import get_schema_resource_name, validate_ir


def _known_good_payload() -> dict[str, object]:
    return {
        "ir_version": "1.2.0",
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
            "simulator_versions": {},
            "noise_seed": None,
            "validator_version": "1.2.0",
        },
    }


def test_ir_schema_packaged_and_loadable() -> None:
    schema_resource = resources.files("openatoms.schemas").joinpath(get_schema_resource_name())
    schema = json.loads(schema_resource.read_text(encoding="utf-8"))
    assert schema.get("$id") == "https://openatoms.org/ir/v1.2.0/schema.json"
    assert schema.get("title") == "OpenAtoms Protocol IR"
    for top_key in ("type", "required", "properties"):
        assert top_key in schema


def test_no_legacy_ir_module_file_exists() -> None:
    legacy_module_path = Path(__file__).resolve().parents[1] / "openatoms" / "ir.py"
    assert not legacy_module_path.exists(), "openatoms/ir.py must not coexist with openatoms/ir/"


def test_schema_single_source_and_no_runtime_duplication() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    canonical_schema = repo_root / "openatoms" / "schemas" / "ir.schema.json"
    legacy_ir_schema = repo_root / "openatoms" / "ir" / "schema_v1_1_0.json"
    versioned_schema = repo_root / "openatoms" / "schemas" / "versioned"

    assert canonical_schema.is_file()
    assert not legacy_ir_schema.exists()
    assert not versioned_schema.exists()

    json_resources = sorted(
        resource.name
        for resource in resources.files("openatoms.schemas").iterdir()
        if resource.name.endswith(".json")
    )
    assert json_resources == [get_schema_resource_name()]
