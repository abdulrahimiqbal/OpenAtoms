"""Versioned IR helpers: schema, canonicalization, and hashing."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, cast

IR_VERSION = "1.1.0"
IR_SCHEMA_FILE = "ir-1.1.0.schema.json"
IR_SCHEMA_VERSION = "1.1.0"
SUPPORTED_IR_VERSIONS = {"1.0.0", "1.1.0"}


def schema_path() -> Path:
    """Return the schema file path for the active IR version."""
    return Path(__file__).resolve().parent / "schemas" / IR_SCHEMA_FILE


def load_schema() -> Dict[str, Any]:
    """Load the active IR JSON schema."""
    return cast(Dict[str, Any], json.loads(schema_path().read_text(encoding="utf-8")))


def canonical_json(payload: Dict[str, Any]) -> str:
    """Return deterministic canonical JSON encoding for the protocol payload."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def ir_hash(payload: Dict[str, Any]) -> str:
    """Compute a stable SHA-256 hash for canonical IR payload."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def validate_protocol_payload(payload: Dict[str, Any]) -> None:
    """Validate payload shape against the active schema.

    Uses `jsonschema` if installed, with a deterministic structural fallback.
    """
    try:
        import jsonschema  # type: ignore

        jsonschema.validate(instance=payload, schema=load_schema())
        return
    except ImportError:
        pass

    if not isinstance(payload, dict):
        raise ValueError("IR payload must be an object.")
    if payload.get("ir_version") != IR_VERSION:
        raise ValueError("IR payload must include supported ir_version.")
    if "protocol_name" not in payload or not isinstance(payload["protocol_name"], str):
        raise ValueError("IR payload is missing protocol_name.")
    if "steps" not in payload or not isinstance(payload["steps"], list):
        raise ValueError("IR payload is missing steps.")
    for step in payload["steps"]:
        if not isinstance(step, dict):
            raise ValueError("Each step must be an object.")
        if "step_id" not in step or "action_type" not in step:
            raise ValueError("Each step must include step_id and action_type.")


def load_ir_payload(raw: str) -> Dict[str, Any]:
    """Load and normalize an IR JSON string across supported versions."""
    payload = cast(Dict[str, Any], json.loads(raw))
    version = str(payload.get("ir_version") or payload.get("version") or "")
    if version not in SUPPORTED_IR_VERSIONS:
        raise ValueError(f"Unsupported IR version '{version}'.")

    if version == "1.0.0":
        payload = dict(payload)
        payload["ir_version"] = "1.1.0"
        payload["schema_version"] = "1.1.0"
        payload.setdefault("references", {"containers": [], "materials": []})
        for index, step in enumerate(payload.get("steps", []), start=1):
            step.setdefault("step", index)
            step.setdefault("step_id", f"s{index}")
            step.setdefault("depends_on", [] if index == 1 else [f"s{index - 1}"])
            step.setdefault("resources", [])
    validate_protocol_payload(payload)
    return payload
