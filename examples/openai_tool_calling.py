"""Demonstrates an LLM tool-calling loop with OpenAtoms physics feedback."""

import json

from openatoms.actions import Move, Transform
from openatoms.core import Container, Matter, Phase
from openatoms.dag import ProtocolGraph
from openatoms.exceptions import PhysicsError

# Shared physical environment used by each simulated tool call.
SOURCE = Container("Source_Vessel", max_volume_ml=1000, max_temp_c=120)
DEST = Container("Dest_Vessel", max_volume_ml=50, max_temp_c=80)
SOURCE.contents.append(Matter("H2O", Phase.LIQUID, mass_g=500, volume_ml=500))


def execute_ai_protocol(ai_generated_steps: list[dict]) -> str:
    """Execute AI-generated steps and return success JSON or structured physics error."""
    graph = ProtocolGraph("AI_Agent_Run")
    try:
        for step in ai_generated_steps:
            if step["action"] == "Move":
                graph.add_step(Move(SOURCE, DEST, step["amount_ml"]))
            elif step["action"] == "Transform":
                graph.add_step(
                    Transform(DEST, step["parameter"], step["target_value"], step["duration_s"])
                )

        graph.dry_run()
        return graph.export_json()
    except PhysicsError as exc:
        return exc.to_agent_payload()
    except Exception as exc:  # pragma: no cover - demo fallback
        return json.dumps({"status": "failed", "error": str(exc)}, indent=2)


def main() -> None:
    """Simulate a failing LLM tool call followed by a corrected retry."""
    hallucinated_input = [
        {"action": "Move", "amount_ml": 20},
        {
            "action": "Transform",
            "parameter": "temperature_c",
            "target_value": 250.0,
            "duration_s": 60,
        },
    ]
    corrected_input = [
        {"action": "Move", "amount_ml": 20},
        {
            "action": "Transform",
            "parameter": "temperature_c",
            "target_value": 75.0,
            "duration_s": 60,
        },
    ]

    print("--- SIMULATING LLM HALLUCINATION ---")
    print(execute_ai_protocol(hallucinated_input))

    print("\n--- SIMULATING LLM SELF-CORRECTION ---")
    # No manual reset required: `dry_run()` now auto-rolls back on PhysicsError.
    print(execute_ai_protocol(corrected_input))


if __name__ == "__main__":
    main()
