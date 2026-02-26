"""IR provenance helpers for tamper-evident exports.

Example:
    >>> from openatoms.ir.provenance import canonical_ir_json, compute_ir_hash
    >>> compute_ir_hash({"a": 1}) == compute_ir_hash({"a": 1})
    True
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_ir_json(payload: dict[str, Any]) -> str:
    """Return canonical JSON string used for deterministic hashing.

    Example:
        >>> canonical_ir_json({"b": 1, "a": 2})
        '{"a":2,"b":1}'
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_ir_hash(payload: dict[str, Any]) -> str:
    """Compute SHA-256 hash from canonical IR JSON.

    Example:
        >>> len(compute_ir_hash({"a": 1}))
        64
    """
    return hashlib.sha256(canonical_ir_json(payload).encode("utf-8")).hexdigest()


def attach_ir_hash(payload: dict[str, Any]) -> dict[str, Any]:
    """Return payload copy with provenance.ir_hash populated.

    Example:
        >>> p = {"provenance": {}}
        >>> "ir_hash" in attach_ir_hash(p)["provenance"]
        True
    """
    enriched = dict(payload)
    provenance = dict(enriched.get("provenance", {}))

    temp = dict(enriched)
    temp["provenance"] = dict(provenance)
    temp["provenance"]["ir_hash"] = ""
    provenance["ir_hash"] = compute_ir_hash(temp)

    enriched["provenance"] = provenance
    return enriched
