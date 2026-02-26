"""Atoms for the Real World: end-to-end dry-run and adapter translation demo."""

from __future__ import annotations

import os

from openatoms.actions import Transform
from openatoms.adapters import HomeAssistantAdapter
from openatoms.core import Container
from openatoms.dag import ProtocolGraph
from openatoms.exceptions import ThermodynamicViolationError


def main() -> None:
    print("== OpenAtoms Real-World Demo ==")

    # 1) Setup: initialize a virtual lab vessel with a strict thermal limit.
    plastic_vessel = Container("Plastic_Vessel", max_volume_ml=100, max_temp_c=80)
    print("[Setup] Plastic_Vessel initialized (max temp: 80C).")

    # 2) The Hallucination: impossible high-temperature target.
    hallucinated_graph = ProtocolGraph("Hallucinated_Protocol")
    hallucinated_graph.add_step(
        Transform(
            target=plastic_vessel,
            parameter="temperature_c",
            target_value=200,
            duration_s=120,
        )
    )
    print("[Hallucination] Proposed Transform target: 200C.")

    # 3) The Catch: dry run raises, and we print structured correction payload.
    try:
        hallucinated_graph.dry_run()
    except ThermodynamicViolationError as exc:
        print("[Catch] ThermodynamicViolationError captured.")
        print(exc.to_agent_payload())

    # 4) The Correction: safe target within vessel limits.
    corrected_graph = ProtocolGraph("Corrected_Protocol")
    corrected_graph.add_step(
        Transform(
            target=plastic_vessel,
            parameter="temperature_c",
            target_value=70,
            duration_s=120,
        )
    )
    print("[Correction] Proposed Transform target: 70C.")

    # 5) The Execution: translate corrected graph to Home Assistant command.
    os.environ.setdefault("HOME_ASSISTANT_CLIMATE_ENTITY_ID", "climate.virtual_lab")
    adapter = HomeAssistantAdapter()
    translation = adapter.execute(corrected_graph)

    service_calls = translation.get("service_calls", [])
    climate_call = next(
        (
            call
            for call in service_calls
            if call.get("domain") == "climate"
            and call.get("service") == "set_temperature"
        ),
        None,
    )

    if climate_call:
        target_value = climate_call["data"].get("temperature")
        print(
            "Hardware Command: CALL service climate.set_temperature "
            f"with value {target_value}"
        )
    else:
        print("Hardware Command: no climate command was generated.")


if __name__ == "__main__":
    main()
