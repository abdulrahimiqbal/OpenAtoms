"""Node C demo: contact-kinetic safety checks for robotic manipulation."""

from __future__ import annotations

import json

from openatoms.errors import OrderingConstraintError
from openatoms.sim.registry.robotics_sim import RoboticsSimulator
from openatoms.sim.types import Pose
from openatoms.units import Q_


def main() -> None:
    simulator = RoboticsSimulator()

    print("=== DEMO 1: Vial Shattering Prevention ===")
    safe_force = Q_(80, "newton")
    area = Q_(2, "centimeter**2").to("meter**2")
    safe_stress = (safe_force / area).to("kilopascal")
    print(
        json.dumps(
            {
                "force_N": safe_force.magnitude,
                "contact_area_m2": area.magnitude,
                "contact_stress_kPa": round(safe_stress.magnitude, 3),
                "glass_yield_MPa": 50.0,
            },
            indent=2,
        )
    )

    safe_error = simulator.check_vial_integrity("glass", safe_force, area)
    print(json.dumps({"safe_configuration_passed": safe_error is None}, indent=2))

    # Calibration error collapses contact patch and spikes local stress.
    unsafe_force = Q_(2000, "newton")
    unsafe_area = Q_(0.4, "centimeter**2").to("meter**2")
    unsafe_stress = (unsafe_force / unsafe_area).to("megapascal")
    unsafe_error = simulator.check_vial_integrity("glass", unsafe_force, unsafe_area)
    print(
        json.dumps(
            {
                "unsafe_force_N": unsafe_force.magnitude,
                "effective_contact_area_m2": unsafe_area.magnitude,
                "contact_stress_MPa": round(unsafe_stress.magnitude, 3),
            },
            indent=2,
        )
    )
    if unsafe_error is None:
        raise RuntimeError("Expected vial integrity error for unsafe contact stress.")
    print("Caught PhysicsError with remediation_hint:")
    print(unsafe_error.to_agent_payload())

    print("\n=== DEMO 2: Torque Limit Violation ===")
    try:
        simulator.simulate_arm_trajectory(
            waypoints=[
                Pose(x_m=0.1, y_m=0.0, z_m=0.2),
                Pose(x_m=1.0, y_m=0.0, z_m=0.2),
            ],
            payload_mass=Q_(2.0, "kilogram"),
        )
    except OrderingConstraintError as exc:
        print("Caught OrderingConstraintError:")
        print(exc.to_agent_payload())

    print("\n=== DEMO 3: Collision-Free Path Validation ===")
    try:
        simulator.simulate_arm_trajectory(
            waypoints=[
                Pose(x_m=0.3, y_m=0.3, z_m=0.02),
                Pose(x_m=0.35, y_m=0.35, z_m=0.015),
            ],
            payload_mass=Q_(0.2, "kilogram"),
        )
    except OrderingConstraintError as exc:
        print("Caught OrderingConstraintError:")
        print(exc.to_agent_payload())


if __name__ == "__main__":
    main()
