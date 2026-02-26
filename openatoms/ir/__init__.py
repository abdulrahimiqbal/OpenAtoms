"""OpenAtoms IR schema, validation, and canonicalization helpers.

Example:
    >>> payload = {
    ...   "ir_version": "1.1.0",
    ...   "protocol_id": "00000000-0000-0000-0000-000000000000",
    ...   "correlation_id": "00000000-0000-0000-0000-000000000001",
    ...   "created_at": "2026-01-01T00:00:00Z",
    ...   "steps": [
    ...      {"step": 1, "step_id": "s1", "action_type": "Move", "parameters": {}, "depends_on": [], "resources": []}
    ...   ],
    ...   "provenance": {
    ...      "ir_hash": "0000000000000000000000000000000000000000000000000000000000000000",
    ...      "simulator_versions": {},
    ...      "noise_seed": None,
    ...      "validator_version": "1.1.0"
    ...   }
    ... }
    >>> isinstance(canonical_json(payload), str)
    True
"""

from __future__ import annotations

import hashlib
import json
import warnings
from importlib import resources
from pathlib import Path
from typing import Any

IR_VERSION = "1.1.0"
IR_SCHEMA_VERSION = "1.1.0"
SUPPORTED_IR_VERSIONS = {"1.1.0"}
SCHEMA_FILENAME = "schema_v1_1_0.json"
# Backward-compatible alias from legacy module API.
IR_SCHEMA_FILE = SCHEMA_FILENAME


class IRValidationError(ValueError):
    """Stable IR validation error with a machine-readable code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def get_schema_version() -> str:
    """Deprecated schema version helper."""
    warnings.warn(
        "openatoms.ir.get_schema_version() is deprecated; use openatoms.ir.schema_version().",
        DeprecationWarning,
        stacklevel=2,
    )
    return schema_version()


def schema_version() -> str:
    """Return canonical IR schema version."""
    return IR_SCHEMA_VERSION


def get_schema_resource_name() -> str:
    """Return canonical schema resource filename."""
    return SCHEMA_FILENAME


def _schema_resource():
    return resources.files("openatoms.ir").joinpath(get_schema_resource_name())


def schema_resource_name() -> str:
    """Deprecated schema resource helper."""
    warnings.warn(
        "openatoms.ir.schema_resource_name() is deprecated; use openatoms.ir.get_schema_resource_name().",
        DeprecationWarning,
        stacklevel=2,
    )
    return get_schema_resource_name()


def get_schema_path() -> Path:
    """Deprecated filesystem-path helper for schema resource."""
    warnings.warn(
        "openatoms.ir.get_schema_path() is deprecated; use openatoms.ir.get_schema_resource_name().",
        DeprecationWarning,
        stacklevel=2,
    )
    with resources.as_file(_schema_resource()) as schema_file:
        return Path(schema_file)


def schema_path() -> Path:
    """Deprecated schema path helper.

    Example:
        >>> schema_path().name
        'schema_v1_1_0.json'
    """
    warnings.warn(
        "openatoms.ir.schema_path() is deprecated; use openatoms.ir.get_schema_path().",
        DeprecationWarning,
        stacklevel=2,
    )
    return get_schema_path()


def load_schema() -> dict[str, Any]:
    """Load schema document.

    Example:
        >>> load_schema()["title"]
        'OpenAtoms Protocol IR'
    """
    return json.loads(_schema_resource().read_text(encoding="utf-8"))


def canonical_json(payload: dict[str, Any]) -> str:
    """Return canonical JSON (sorted keys, compact separators).

    Example:
        >>> canonical_json({"b": 1, "a": 2})
        '{"a":2,"b":1}'
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def ir_hash(payload: dict[str, Any]) -> str:
    """Compute SHA-256 over canonical JSON.

    Example:
        >>> len(ir_hash({"a": 1}))
        64
    """
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def validate_ir(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate IR payload against schema.

    Raises:
        IRValidationError: If required contract fields are missing or schema validation fails.

    Example:
        >>> minimal = {
        ...   "ir_version": "1.1.0",
        ...   "protocol_id": "00000000-0000-0000-0000-000000000000",
        ...   "correlation_id": "00000000-0000-0000-0000-000000000001",
        ...   "created_at": "2026-01-01T00:00:00Z",
        ...   "steps": [{"step": 1, "step_id": "s1", "action_type": "Move", "parameters": {}, "depends_on": [], "resources": []}],
        ...   "provenance": {
        ...      "ir_hash": "0000000000000000000000000000000000000000000000000000000000000000",
        ...      "simulator_versions": {},
        ...      "noise_seed": None,
        ...      "validator_version": "1.1.0"
        ...   }
        ... }
        >>> validate_ir(minimal)
    """
    if not isinstance(payload, dict):
        raise IRValidationError("IR_TYPE", "IR payload must be a JSON object.")
    if payload.get("ir_version") != IR_VERSION:
        raise IRValidationError("IR_VERSION", f"IR payload must declare ir_version={IR_VERSION}.")

    required = ["protocol_id", "correlation_id", "created_at", "steps", "provenance"]
    for key in required:
        if key not in payload:
            raise IRValidationError("IR_MISSING_FIELD", f"IR payload missing required field '{key}'.")

    try:
        import jsonschema  # type: ignore
    except ImportError as exc:  # pragma: no cover - dependency invariant path
        raise IRValidationError(
            "IR_RUNTIME_DEPENDENCY",
            "jsonschema is required for IR validation. Install with: pip install \"openatoms[dev]\"",
        ) from exc

    validator = jsonschema.Draft7Validator(load_schema())
    errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.path))
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.path) or "<root>"
        raise IRValidationError(
            "IR_SCHEMA_VALIDATION",
            f"IR schema validation failed at {location}: {first.message}",
        )
    return payload


def legacy_validate_ir(payload: dict[str, Any]) -> dict[str, Any]:
    """Deprecated validate wrapper preserved for legacy callers."""
    warnings.warn(
        "openatoms.ir.legacy_validate_ir() is deprecated; use openatoms.ir.validate_ir().",
        DeprecationWarning,
        stacklevel=2,
    )
    return validate_ir(payload)


def validate_protocol_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Deprecated legacy validator wrapper."""
    warnings.warn(
        "openatoms.ir.validate_protocol_payload() is deprecated; use openatoms.ir.validate_ir().",
        DeprecationWarning,
        stacklevel=2,
    )
    return validate_ir(payload)


def load_ir_payload(raw: str) -> dict[str, Any]:
    """Load and validate serialized IR payload.

    Example:
        >>> payload = load_ir_payload('{\"ir_version\":\"1.1.0\",\"protocol_id\":\"00000000-0000-0000-0000-000000000000\",\"correlation_id\":\"00000000-0000-0000-0000-000000000001\",\"created_at\":\"2026-01-01T00:00:00Z\",\"steps\":[{\"step\":1,\"step_id\":\"s1\",\"action_type\":\"Move\",\"parameters\":{},\"depends_on\":[],\"resources\":[]}],\"provenance\":{\"ir_hash\":\"0000000000000000000000000000000000000000000000000000000000000000\",\"simulator_versions\":{},\"noise_seed\":null,\"validator_version\":\"1.1.0\"}}')
        >>> payload["ir_version"]
        '1.1.0'
    """
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise IRValidationError("IR_TYPE", "IR payload must decode to an object.")
    validate_ir(payload)
    return payload


__all__ = [
    "IR_SCHEMA_FILE",
    "IR_SCHEMA_VERSION",
    "IR_VERSION",
    "IRValidationError",
    "SUPPORTED_IR_VERSIONS",
    "canonical_json",
    "get_schema_resource_name",
    "get_schema_path",
    "get_schema_version",
    "ir_hash",
    "legacy_validate_ir",
    "load_ir_payload",
    "load_schema",
    "schema_path",
    "schema_resource_name",
    "schema_version",
    "validate_protocol_payload",
    "validate_ir",
]
