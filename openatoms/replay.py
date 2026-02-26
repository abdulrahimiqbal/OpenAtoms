"""Replay helpers for deterministic run verification."""

from __future__ import annotations

import json
from typing import Any, Dict

from .ir import ir_hash


def replay_signature(
    *,
    ir_payload: Dict[str, Any],
    simulator_version: str,
    seed: int,
) -> str:
    """Return deterministic replay signature.

    Contract: same IR + simulator version + seed => same signature.
    """
    envelope = {
        "ir_hash": ir_hash(ir_payload),
        "simulator_version": simulator_version,
        "seed": seed,
    }
    return json.dumps(envelope, sort_keys=True, separators=(",", ":"))

