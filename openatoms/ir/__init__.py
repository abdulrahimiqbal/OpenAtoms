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
from pathlib import Path
from typing import Any

IR_VERSION = "1.1.0"
IR_SCHEMA_VERSION = "1.1.0"
SUPPORTED_IR_VERSIONS = {"1.1.0"}


def schema_path() -> Path:
    """Return JSON schema path for IR v1.1.0.

    Example:
        >>> schema_path().name
        'schema_v1_1_0.json'
    """
    return Path(__file__).resolve().parent / "schema_v1_1_0.json"


def load_schema() -> dict[str, Any]:
    """Load schema document.

    Example:
        >>> load_schema()["title"]
        'OpenAtoms Protocol IR'
    """
    return json.loads(schema_path().read_text(encoding="utf-8"))


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


def validate_ir(payload: dict[str, Any]) -> None:
    """Validate IR payload against schema.

    Raises:
        ValueError: If required contract fields are missing.
        jsonschema.ValidationError: If `jsonschema` is installed and schema validation fails.

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
        raise ValueError("IR payload must be a JSON object.")
    if payload.get("ir_version") != IR_VERSION:
        raise ValueError(f"IR payload must declare ir_version={IR_VERSION}.")

    required = ["protocol_id", "correlation_id", "created_at", "steps", "provenance"]
    for key in required:
        if key not in payload:
            raise ValueError(f"IR payload missing required field '{key}'.")

    try:
        import jsonschema  # type: ignore

        jsonschema.validate(instance=payload, schema=load_schema())
    except ImportError:
        pass


def load_ir_payload(raw: str) -> dict[str, Any]:
    """Load and validate serialized IR payload.

    Example:
        >>> payload = load_ir_payload('{\"ir_version\":\"1.1.0\",\"protocol_id\":\"00000000-0000-0000-0000-000000000000\",\"correlation_id\":\"00000000-0000-0000-0000-000000000001\",\"created_at\":\"2026-01-01T00:00:00Z\",\"steps\":[{\"step\":1,\"step_id\":\"s1\",\"action_type\":\"Move\",\"parameters\":{},\"depends_on\":[],\"resources\":[]}],\"provenance\":{\"ir_hash\":\"0000000000000000000000000000000000000000000000000000000000000000\",\"simulator_versions\":{},\"noise_seed\":null,\"validator_version\":\"1.1.0\"}}')
        >>> payload["ir_version"]
        '1.1.0'
    """
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("IR payload must decode to an object.")
    validate_ir(payload)
    return payload
