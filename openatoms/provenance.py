"""Provenance and observability utilities for reproducible execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from .ir import canonical_json, ir_hash


@dataclass(frozen=True)
class RunContext:
    """Context for one execution run."""

    run_id: str
    correlation_id: str
    started_at_utc: str
    seed: int
    simulator_version: str


def new_run_context(*, seed: int = 0, simulator_version: str = "mock-1.0.0") -> RunContext:
    """Build a deterministic context envelope for a run."""
    run_id = str(uuid4())
    correlation_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    return RunContext(
        run_id=run_id,
        correlation_id=correlation_id,
        started_at_utc=now,
        seed=seed,
        simulator_version=simulator_version,
    )


def build_provenance(
    *,
    payload: Dict[str, Any],
    run_context: RunContext,
    adapter_name: str,
    adapter_version: str = "1.0.0",
    outcome: str = "ok",
) -> Dict[str, Any]:
    """Create deterministic run provenance metadata."""
    return {
        "run_id": run_context.run_id,
        "correlation_id": run_context.correlation_id,
        "started_at_utc": run_context.started_at_utc,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": run_context.seed,
        "simulator_version": run_context.simulator_version,
        "adapter": {"name": adapter_name, "version": adapter_version},
        "ir_hash": ir_hash(payload),
        "ir_canonical": canonical_json(payload),
        "outcome": outcome,
    }

