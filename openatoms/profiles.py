"""Capability profiles for compile/validation target bounds."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Set

from .exceptions import CapabilityBoundError


@dataclass(frozen=True)
class CapabilityProfile:
    """Describes execution limits for a target adapter or device."""

    name: str
    allowed_actions: Set[str] = field(default_factory=set)
    max_steps: int = 200
    max_move_ml: float = 1000.0
    max_temperature_c: float = 300.0
    blocked_hazard_classes: Set[str] = field(default_factory=set)

    @classmethod
    def from_iterables(
        cls,
        *,
        name: str,
        allowed_actions: Iterable[str],
        blocked_hazard_classes: Iterable[str] = (),
        max_steps: int = 200,
        max_move_ml: float = 1000.0,
        max_temperature_c: float = 300.0,
    ) -> "CapabilityProfile":
        return cls(
            name=name,
            allowed_actions={a.strip() for a in allowed_actions},
            blocked_hazard_classes={h.strip().lower() for h in blocked_hazard_classes},
            max_steps=max_steps,
            max_move_ml=max_move_ml,
            max_temperature_c=max_temperature_c,
        )

    def validate_action(self, action_name: str) -> None:
        if self.allowed_actions and action_name not in self.allowed_actions:
            raise CapabilityBoundError(
                message=f"Action '{action_name}' is not supported by target '{self.name}'.",
                details={"capability_profile": self.name, "action": action_name},
            )

