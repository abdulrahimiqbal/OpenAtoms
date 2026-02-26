import json
import inspect
import warnings
from importlib import resources

import jsonschema
import pytest

import openatoms.ir as ir_module
from openatoms.ir import (
    IRValidationError,
    IR_VERSION,
    canonical_json,
    get_schema_resource_name,
    get_schema_path,
    get_schema_version,
    ir_hash,
    legacy_validate_ir,
    load_schema,
    schema_resource_name,
    schema_version,
    validate_protocol_payload,
    validate_ir,
)
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


def test_ir_schema_is_packaged() -> None:
    schema = json.loads(
        resources.files("openatoms.schemas")
        .joinpath(get_schema_resource_name())
        .read_text(encoding="utf-8")
    )
    assert schema["title"] == "OpenAtoms Protocol IR"


def test_ir_hash_is_stable() -> None:
    p1 = _payload()
    p2 = _payload()
    assert ir_hash(p1) == ir_hash(p2)
    assert json.loads(canonical_json(p1))["ir_version"] == IR_VERSION


def test_legacy_and_canonical_validation_match() -> None:
    payload = _payload()
    canonical = validate_ir(payload)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        legacy = legacy_validate_ir(payload)

    assert canonical == legacy
    assert any(issubclass(item.category, DeprecationWarning) for item in caught)


def test_legacy_validate_protocol_payload_forwards() -> None:
    payload = _payload()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        legacy = validate_protocol_payload(payload)
    assert legacy == validate_ir(payload)
    assert any(issubclass(item.category, DeprecationWarning) for item in caught)


def test_single_runtime_schema_resource_is_canonical() -> None:
    canonical_version = schema_version()
    canonical_name = get_schema_resource_name()
    assert canonical_version == "1.1.0"
    assert canonical_name == "ir.schema.json"

    json_resources = sorted(
        resource.name
        for resource in resources.files("openatoms.schemas").iterdir()
        if resource.name.endswith(".json")
    )
    assert json_resources == [canonical_name]
    assert not resources.files("openatoms.ir").joinpath("schema_v1_1_0.json").is_file()


def test_ir_single_source_of_truth() -> None:
    module_source = inspect.getsource(ir_module)
    validate_source = inspect.getsource(ir_module.validate_ir)
    assert "openatoms.schemas" in module_source
    assert "load_schema()" in validate_source
    assert ir_module.get_schema_resource_name() == "ir.schema.json"


def test_legacy_schema_entrypoints_forward_to_canonical() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert get_schema_version() == schema_version()
        assert get_schema_path().name == get_schema_resource_name()
        assert schema_resource_name() == get_schema_resource_name()
    assert any(issubclass(item.category, DeprecationWarning) for item in caught)


def test_invalid_payload_has_stable_error_code_and_message() -> None:
    payload = _payload()
    payload.pop("protocol_id")

    with pytest.raises(IRValidationError) as exc_info:
        validate_ir(payload)

    assert exc_info.value.code == "IR_MISSING_FIELD"
    assert str(exc_info.value) == "IR payload missing required field 'protocol_id'."


def test_invalid_payload_schema_type_error_is_stable() -> None:
    payload = _payload()
    payload["steps"] = "not-a-list"

    with pytest.raises(IRValidationError) as exc_info:
        validate_ir(payload)

    assert exc_info.value.code == "IR_SCHEMA_VALIDATION"
    assert str(exc_info.value).startswith("IR schema validation failed at steps:")
