"""Legacy compatibility shim for the historical ``openatoms/ir.py`` module.

This module forwards all behavior to the canonical ``openatoms.ir`` package.
"""

from __future__ import annotations

import warnings
from typing import Any

from openatoms.ir import (
    IR_SCHEMA_FILE,
    IR_SCHEMA_VERSION,
    IR_VERSION,
    SUPPORTED_IR_VERSIONS,
    canonical_json,
    get_schema_path,
    get_schema_resource_name,
    load_ir_payload,
    load_schema,
    schema_version,
    validate_ir,
)

warnings.warn(
    "openatoms.ir.py is deprecated; use openatoms.ir (package) instead.",
    DeprecationWarning,
    stacklevel=2,
)


def schema_path():
    """Forward legacy name to canonical deprecated helper."""
    warnings.warn(
        "openatoms.ir.schema_path() from openatoms/ir.py is deprecated; use openatoms.ir.get_schema_resource_name().",
        DeprecationWarning,
        stacklevel=2,
    )
    return get_schema_path()


def validate_protocol_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Forward legacy name to canonical validator."""
    warnings.warn(
        "openatoms.ir.validate_protocol_payload() from openatoms/ir.py is deprecated; use openatoms.ir.validate_ir().",
        DeprecationWarning,
        stacklevel=2,
    )
    return validate_ir(payload)


__all__ = [
    "IR_SCHEMA_FILE",
    "IR_SCHEMA_VERSION",
    "IR_VERSION",
    "SUPPORTED_IR_VERSIONS",
    "canonical_json",
    "get_schema_resource_name",
    "load_ir_payload",
    "load_schema",
    "schema_path",
    "schema_version",
    "validate_ir",
    "validate_protocol_payload",
]
