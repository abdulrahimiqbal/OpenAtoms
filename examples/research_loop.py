"""Science-first agent loop using the Cantera-backed VirtualReactor."""

from __future__ import annotations

from openatoms.exceptions import SimulationDependencyError, StructuralIntegrityError
from openatoms.sim.registry.kinetics_sim import Vessel, VirtualReactor


def main() -> None:
    reactor = VirtualReactor()
    vessel = Vessel(name="Reactor_Vessel_01", burst_pressure_pa=125000.0)

    # Agent proposal starts aggressively at 500K.
    proposal = {"temperature_k": 500.0, "flow_rate_slpm": 1.0}

    print("== OpenAtoms Research Loop ==")
    print(f"Initial proposal: {proposal}")

    for attempt in range(1, 6):
        print(f"\nAttempt {attempt}: simulate at {proposal['temperature_k']}K")
        try:
            result = reactor.simulate_hydrogen_oxygen_combustion(
                initial_temp_k=proposal["temperature_k"],
                flow_rate_slpm=proposal["flow_rate_slpm"],
                residence_time_s=0.02,
                vessel=vessel,
            )
            print("Simulation succeeded. StateObservation JSON:")
            print(result["state_observation_json"])
            return
        except StructuralIntegrityError as exc:
            print("StructuralIntegrityError caught:")
            print(exc.to_agent_payload())

            # Agent "researches" a safer policy: lower temperature and slower flow.
            proposal["temperature_k"] = max(320.0, proposal["temperature_k"] - 40.0)
            proposal["flow_rate_slpm"] = max(0.2, proposal["flow_rate_slpm"] * 0.7)
            print(f"Revised proposal: {proposal}")
        except SimulationDependencyError as exc:
            print(exc.to_agent_payload())
            return

    print("Reached max attempts without finding a safe proposal.")


if __name__ == "__main__":
    main()

