"""Runtime policy hooks for approval and safety gating."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from .exceptions import PolicyViolationError


@dataclass(frozen=True)
class SafetyProfile:
    """Simple policy profile for risky action approvals and rate limits."""

    name: str = "default"
    require_approval_for_hazard: bool = True
    max_retries: int = 1
    max_actions_per_run: int = 500


class PolicyHook:
    """Base policy hook for run lifecycle gating."""

    def before_run(self, *, dag: Any, context: Dict[str, Any]) -> None:
        """Called before adapter execution."""

    def after_run(self, *, dag: Any, result: Dict[str, Any], context: Dict[str, Any]) -> None:
        """Called after adapter execution."""


class HazardApprovalPolicy(PolicyHook):
    """Fail-closed policy: block runs with hazardous matter unless approved."""

    def __init__(self, approved: bool = False):
        self.approved = approved

    def before_run(self, *, dag: Any, context: Dict[str, Any]) -> None:
        if self.approved:
            return
        for container in dag._collect_containers():  # noqa: SLF001 - internal introspection by design
            if container.hazard_classes:
                raise PolicyViolationError(
                    message="Run blocked: hazardous contents require explicit approval.",
                    details={
                        "container": container.name,
                        "hazard_classes": sorted(container.hazard_classes),
                    },
                )

