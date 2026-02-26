"""Shared simulation datatypes.

Example:
    >>> from openatoms.sim.types import StateObservation
    >>> StateObservation(success=True).success
    True
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from ..errors import PhysicsError


@dataclass
class StateObservation:
    """Structured simulator output for one dry run."""

    success: bool
    errors: list[PhysicsError] = field(default_factory=list)
    timing_estimate_s: float = 0.0
    tip_usage_count: int = 0
    volume_dispensed_per_well: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize state observation.

        Example:
            >>> StateObservation(success=True).to_dict()["success"]
            True
        """
        return {
            "success": self.success,
            "errors": [error.to_dict() for error in self.errors],
            "timing_estimate_s": self.timing_estimate_s,
            "tip_usage_count": self.tip_usage_count,
            "volume_dispensed_per_well": self.volume_dispensed_per_well,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """Serialize state observation JSON.

        Example:
            >>> '"success"' in StateObservation(success=True).to_json()
            True
        """
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


@dataclass
class ReactionTrajectory:
    """Time-series output from thermo-kinetic simulation."""

    times_s: list[float]
    temperatures_k: list[float]
    pressures_pa: list[float]
    species_mole_fractions: dict[str, list[float]]
    heat_release_rate_w_m3: list[float]


@dataclass
class SimulationParams:
    """Simulation parameters used for robustness noise injection."""

    pipette_cv: float
    thermocouple_offset_c: float
    pressure_scale_fraction: float
    seed: Optional[int] = None


@dataclass
class RobustnessReport:
    """Summary of stochastic robustness sweep."""

    pass_rate: float
    n_trials: int
    failure_modes: dict[str, int]
    worst_case_parameter_sensitivity: dict[str, float]
    research_ready: bool


@dataclass
class Pose:
    """Minimal robot pose representation."""

    x_m: float
    y_m: float
    z_m: float


@dataclass
class GraspFeasibilityResult:
    """Result of grasp force feasibility check."""

    stable: bool
    required_force_n: float
    available_force_n: float


@dataclass
class TrajectoryResult:
    """Result of trajectory simulation/analysis."""

    torque_per_joint_nm: list[float]
    collision_risk_zones: list[str]
    cycle_time_s: float
    mode: str
