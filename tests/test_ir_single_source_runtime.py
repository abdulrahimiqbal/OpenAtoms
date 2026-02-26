from __future__ import annotations

import importlib.util
import json
import warnings
from importlib import resources
from pathlib import Path

from openatoms.ir import get_schema_resource_name, validate_ir


def _known_good_payload() -> dict[str, object]:
    return {
        "ir_version": "1.1.0",
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
            "validator_version": "1.1.0",
        },
    }


def test_ir_schema_packaged_and_loadable() -> None:
    schema_resource = resources.files("openatoms.ir").joinpath(get_schema_resource_name())
    schema = json.loads(schema_resource.read_text(encoding="utf-8"))
    assert schema.get("$id") == "https://openatoms.org/ir/v1.1.0/schema.json"
    assert schema.get("title") == "OpenAtoms Protocol IR"
    for top_key in ("type", "required", "properties"):
        assert top_key in schema


def test_legacy_ir_wrapper_warns_and_forwards() -> None:
    legacy_module_path = Path(__file__).resolve().parents[1] / "openatoms" / "ir.py"
    assert legacy_module_path.is_file()

    spec = importlib.util.spec_from_file_location("openatoms._legacy_ir_file", legacy_module_path)
    assert spec is not None
    assert spec.loader is not None
    legacy_module = importlib.util.module_from_spec(spec)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        spec.loader.exec_module(legacy_module)

    assert any(
        str(item.message) == "openatoms.ir.py is deprecated; use openatoms.ir (package) instead."
        for item in caught
    )
    payload = _known_good_payload()
    assert legacy_module.validate_ir(payload) == validate_ir(payload)


def test_no_runtime_schema_duplication() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    legacy_schema = repo_root / "openatoms" / "schemas" / "ir-1.1.0.schema.json"
    runtime_py_files = (repo_root / "openatoms").rglob("*.py")

    forbidden_hits: list[Path] = []
    for source_file in runtime_py_files:
        source = source_file.read_text(encoding="utf-8")
        if "openatoms/schemas" in source or "schemas/ir-1.1.0.schema.json" in source:
            forbidden_hits.append(source_file)

    assert not forbidden_hits, f"runtime code references legacy schema path(s): {forbidden_hits}"
    assert not legacy_schema.exists()
