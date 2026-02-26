from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BaselineDefinition:
    name: str
    description: str


NO_VALIDATION_BASELINE = BaselineDefinition(
    name="no_validation",
    description="Pass protocol proposals directly to execution checks without repair.",
)


def apply_no_validation(protocol: dict[str, Any]) -> dict[str, Any]:
    """Baseline policy: no correction, no repair, no re-ordering."""
    return dict(protocol)

