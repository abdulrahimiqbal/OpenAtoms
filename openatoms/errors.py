"""Physics error taxonomy used for deterministic validation and agent correction.

Example:
    >>> from openatoms.errors import VolumeOverflowError
    >>> err = VolumeOverflowError("A", "120 milliliter", "100 milliliter", "Reduce volume")
    >>> err.constraint_type
    'volume'
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class PhysicsError(Exception):
    """Base OpenAtoms physics error.

    Attributes:
        error_code: Stable error identifier.
        constraint_type: One of volume/thermal/mass_balance/ordering/reaction.
        description: Human-readable error description.
        actual_value: Computed value that violated the constraint.
        limit_value: Bound or expected value for the constraint.
        remediation_hint: Complete machine-readable correction instruction.

    Example:
        >>> err = PhysicsError(
        ...     error_code="VOL_001",
        ...     constraint_type="volume",
        ...     description="Overflow",
        ...     actual_value="120 milliliter",
        ...     limit_value="100 milliliter",
        ...     remediation_hint="Reduce volume to 100 milliliter or below.",
        ... )
        >>> err.error_code
        'VOL_001'
    """

    error_code: str
    constraint_type: str
    description: str
    actual_value: Any
    limit_value: Any
    remediation_hint: str

    def __post_init__(self) -> None:
        super().__init__(self.description)

    def to_dict(self) -> dict[str, Any]:
        """Return serializable error details.

        Example:
            >>> PhysicsError("O_1", "ordering", "bad", 2, 1, "Reorder.").to_dict()["error_code"]
            'O_1'
        """
        return {
            "error_code": self.error_code,
            "constraint_type": self.constraint_type,
            "description": self.description,
            "actual_value": self.actual_value,
            "limit_value": self.limit_value,
            "remediation_hint": self.remediation_hint,
        }

    def to_agent_payload(self) -> str:
        """Serialize the error for an agent correction loop.

        Example:
            >>> payload = PhysicsError("O_1", "ordering", "bad", 2, 1, "Reorder.").to_agent_payload()
            >>> '"error_code": "O_1"' in payload
            True
        """
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)


class VolumeOverflowError(PhysicsError):
    """Raised when container volume constraints are violated."""

    def __init__(self, description: str, actual_value: Any, limit_value: Any, remediation_hint: str):
        super().__init__(
            error_code="VOL_001",
            constraint_type="volume",
            description=description,
            actual_value=actual_value,
            limit_value=limit_value,
            remediation_hint=remediation_hint,
        )


class ThermalExcursionError(PhysicsError):
    """Raised when thermal limits are violated."""

    def __init__(self, description: str, actual_value: Any, limit_value: Any, remediation_hint: str):
        super().__init__(
            error_code="THM_001",
            constraint_type="thermal",
            description=description,
            actual_value=actual_value,
            limit_value=limit_value,
            remediation_hint=remediation_hint,
        )


class MassBalanceViolationError(PhysicsError):
    """Raised when mass conservation fails."""

    def __init__(self, description: str, actual_value: Any, limit_value: Any, remediation_hint: str):
        super().__init__(
            error_code="MAS_001",
            constraint_type="mass_balance",
            description=description,
            actual_value=actual_value,
            limit_value=limit_value,
            remediation_hint=remediation_hint,
        )


class OrderingConstraintError(PhysicsError):
    """Raised when protocol ordering constraints fail."""

    def __init__(self, description: str, actual_value: Any, limit_value: Any, remediation_hint: str):
        super().__init__(
            error_code="ORD_001",
            constraint_type="ordering",
            description=description,
            actual_value=actual_value,
            limit_value=limit_value,
            remediation_hint=remediation_hint,
        )


class ReactionFeasibilityError(PhysicsError):
    """Raised when a reaction is thermodynamically infeasible."""

    def __init__(self, description: str, actual_value: Any, limit_value: Any, remediation_hint: str):
        super().__init__(
            error_code="RXN_001",
            constraint_type="reaction",
            description=description,
            actual_value=actual_value,
            limit_value=limit_value,
            remediation_hint=remediation_hint,
        )


class SimulationDependencyError(PhysicsError):
    """Raised when optional simulation dependencies are unavailable."""

    def __init__(self, dependency: str, import_error: str):
        super().__init__(
            error_code="SIM_001",
            constraint_type="ordering",
            description=(
                f"Optional simulator dependency '{dependency}' is unavailable: "
                f"{import_error}"
            ),
            actual_value=dependency,
            limit_value="installed dependency",
            remediation_hint=f"Install {dependency} and retry the simulation.",
        )
