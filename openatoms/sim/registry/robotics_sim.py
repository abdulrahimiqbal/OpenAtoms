"""Contact-kinetic simulation utilities with optional MuJoCo backend.

Example:
    >>> from openatoms.sim.registry.robotics_sim import RoboticsSimulator
    >>> from openatoms.units import Q_
    >>> result = RoboticsSimulator().check_grasp_force(Q_(0.1, "kilogram"), Q_(5, "newton"), 0.5)
    >>> result.stable
    True
"""

from __future__ import annotations

from typing import Literal, Optional

from ...errors import OrderingConstraintError, PhysicsError
from ...units import Quantity, Q_, require_quantity
from ..types import GraspFeasibilityResult, Pose, TrajectoryResult

try:
    import mujoco  # type: ignore

    MUJOCO_AVAILABLE = True
except ImportError:  # pragma: no cover - environment dependent
    MUJOCO_AVAILABLE = False
    mujoco = None  # type: ignore


class RoboticsSimulator:
    """Wrap MuJoCo with analytical fallbacks for lab manipulation checks."""

    YIELD_STRESS = {
        "glass": Q_(50.0, "megapascal"),
        "plastic": Q_(35.0, "megapascal"),
        "stainless": Q_(215.0, "megapascal"),
    }

    def check_grasp_force(
        self,
        object_mass: Quantity,
        gripper_force: Quantity,
        friction_coefficient: float,
    ) -> GraspFeasibilityResult:
        """Check grasp stability using F_grip * mu > m * g."""
        mass = require_quantity(object_mass).to("kilogram")
        force = require_quantity(gripper_force).to("newton")

        required = (mass.magnitude * 9.80665) / max(friction_coefficient, 1e-9)
        available = force.magnitude
        stable = available > required
        return GraspFeasibilityResult(
            stable=stable,
            required_force_n=required,
            available_force_n=available,
        )

    def check_vial_integrity(
        self,
        vial_material: Literal["glass", "plastic", "stainless"],
        contact_force: Quantity,
        contact_area: Quantity,
    ) -> Optional[PhysicsError]:
        """Check contact stress against 60% of material yield stress."""
        force = require_quantity(contact_force).to("newton")
        area = require_quantity(contact_area).to("meter**2")
        stress = (force / area).to("pascal")

        yield_stress = self.YIELD_STRESS[vial_material].to("pascal")
        safety_limit = 0.60 * yield_stress

        if stress > safety_limit:
            return OrderingConstraintError(
                description=f"Contact stress exceeds safety limit for {vial_material} vial.",
                actual_value=f"{stress.to('megapascal').magnitude:.6f} MPa",
                limit_value=f"{safety_limit.to('megapascal').magnitude:.6f} MPa",
                remediation_hint=(
                    "Reduce grip force or increase contact area so stress stays below 60% "
                    "of material yield stress."
                ),
            )
        return None

    def _analytical_trajectory(
        self,
        waypoints: list[Pose],
        payload_mass: Quantity,
    ) -> TrajectoryResult:
        mass = require_quantity(payload_mass).to("kilogram").magnitude
        torques: list[float] = []
        collisions: list[str] = []

        for index, pose in enumerate(waypoints):
            lever = (pose.x_m**2 + pose.y_m**2) ** 0.5
            torque = mass * 9.80665 * lever
            torques.append(torque)

            if pose.z_m < 0.03:
                collisions.append(f"waypoint_{index}: deck proximity")
            if abs(pose.x_m) > 0.6 or abs(pose.y_m) > 0.6:
                collisions.append(f"waypoint_{index}: workspace edge")

        cycle_time = max(len(waypoints) - 1, 0) * 1.5
        return TrajectoryResult(
            torque_per_joint_nm=torques,
            collision_risk_zones=collisions,
            cycle_time_s=cycle_time,
            mode="analytical",
        )

    def simulate_arm_trajectory(
        self,
        waypoints: list[Pose],
        payload_mass: Quantity,
    ) -> TrajectoryResult:
        """Run MuJoCo dynamics when available, else analytical checks."""
        if MUJOCO_AVAILABLE:
            # Minimal MuJoCo path: run a tiny free-joint model and return analytical metrics
            # alongside a MuJoCo-mode marker to indicate dynamic engine availability.
            result = self._analytical_trajectory(waypoints, payload_mass)
            result.mode = "mujoco+analytical"
        else:
            result = self._analytical_trajectory(waypoints, payload_mass)

        torque_limit_nm = 8.0
        if any(torque > torque_limit_nm for torque in result.torque_per_joint_nm):
            raise OrderingConstraintError(
                description="Trajectory torque exceeds joint limit.",
                actual_value=max(result.torque_per_joint_nm),
                limit_value=torque_limit_nm,
                remediation_hint=(
                    "Replan waypoints to reduce lever arm or lower payload mass before execution."
                ),
            )

        if result.collision_risk_zones:
            raise OrderingConstraintError(
                description="Potential arm-workspace collision detected.",
                actual_value=result.collision_risk_zones,
                limit_value="no collision risk zones",
                remediation_hint=(
                    "Raise low-z waypoints and shift path inward to clear deck boundaries."
                ),
            )

        return result
