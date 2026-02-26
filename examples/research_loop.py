"""Science-first agent loop using the Cantera-backed VirtualReactor."""

from __future__ import annotations

import json

from openatoms.exceptions import SimulationDependencyError
from openatoms.sim.registry.kinetics_sim import VirtualReactor

SAFE_PEAK_TEMPERATURE_K = 1500.0


def main() -> None:
    reactor = VirtualReactor()

    # Agent proposal starts aggressively and self-corrects from feedback.
    proposal = {"temperature_k": 1200.0, "residence_time_s": 0.02}

    print("== OpenAtoms Research Loop ==")
    print(f"Initial proposal: {proposal}")

    for attempt in range(1, 6):
        print(f"\nAttempt {attempt}: simulate at {proposal['temperature_k']}K")
        try:
            result = reactor.simulate_hydrogen_oxygen_combustion(
                initial_temp_k=proposal["temperature_k"],
                residence_time_s=proposal["residence_time_s"],
            )
            trajectory = result["trajectory"]
            peak_temperature = max(trajectory.temperatures_k)
            if peak_temperature <= SAFE_PEAK_TEMPERATURE_K:
                print("Simulation succeeded. StateObservation JSON:")
                print(result["state_observation_json"])
                return

            print("Safety gate violation caught:")
            print(
                json.dumps(
                    {
                        "error_code": "THM_001",
                        "description": "Peak temperature exceeds safe process envelope.",
                        "actual_peak_temperature_k": peak_temperature,
                        "limit_temperature_k": SAFE_PEAK_TEMPERATURE_K,
                        "remediation_hint": "Lower initial temperature before execution.",
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            proposal["temperature_k"] = max(320.0, proposal["temperature_k"] - 120.0)
            print(f"Revised proposal: {proposal}")
        except SimulationDependencyError as exc:
            print(exc.to_agent_payload())
            return

    print("Reached max attempts without finding a safe proposal.")


if __name__ == "__main__":
    main()
