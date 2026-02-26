"""Demonstrates an LLM tool-calling loop with OpenAtoms physics feedback."""

import json

from openatoms.actions import Move, Transform
from openatoms.core import Container, Matter, Phase
from openatoms.dag import ProtocolGraph
from openatoms.errors import PhysicsError
from openatoms.units import Q_


def _build_environment() -> tuple[Container, Container]:
    source = Container(
        id="source_vessel",
        label="Source_Vessel",
        max_volume=Q_(1000, "milliliter"),
        max_temp=Q_(120, "degC"),
        min_temp=Q_(0, "degC"),
    )
    destination = Container(
        id="dest_vessel",
        label="Dest_Vessel",
        max_volume=Q_(50, "milliliter"),
        max_temp=Q_(80, "degC"),
        min_temp=Q_(0, "degC"),
    )
    source.contents.append(
        Matter(
            name="H2O",
            phase=Phase.LIQUID,
            mass=Q_(500, "gram"),
            volume=Q_(500, "milliliter"),
        )
    )
    return source, destination


def execute_ai_protocol(ai_generated_steps: list[dict]) -> str:
    """Execute AI-generated steps and return success JSON or structured physics error."""
    source, destination = _build_environment()
    graph = ProtocolGraph("AI_Agent_Run")
    try:
        for step in ai_generated_steps:
            if step["action"] == "Move":
                graph.add_step(Move(source, destination, Q_(step["amount_ml"], "milliliter")))
            elif step["action"] == "Transform":
                graph.add_step(
                    Transform(
                        destination,
                        step["parameter"],
                        Q_(step["target_value_c"], "degC"),
                        Q_(step["duration_s"], "second"),
                    )
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
            "parameter": "temperature",
            "target_value_c": 250.0,
            "duration_s": 60,
        },
    ]
    corrected_input = [
        {"action": "Move", "amount_ml": 20},
        {
            "action": "Transform",
            "parameter": "temperature",
            "target_value_c": 75.0,
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
