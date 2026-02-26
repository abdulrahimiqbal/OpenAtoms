"""Stable deterministic IDs for OpenAtoms IR entities."""

from __future__ import annotations

import hashlib


def stable_id(entity_type: str, label: str) -> str:
    """Build a deterministic ID from entity type and label."""
    normalized = f"{entity_type.strip().lower()}::{label.strip().lower()}".encode("utf-8")
    digest = hashlib.sha256(normalized).hexdigest()[:12]
    return f"{entity_type.strip().lower()}_{digest}"

