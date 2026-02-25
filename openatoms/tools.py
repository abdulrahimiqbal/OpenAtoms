"""Tool schemas for LLM function-calling integrations."""

from __future__ import annotations

import json


def get_tool_definitions() -> list[dict]:
    """Return platform-agnostic tool definitions for OpenAI/Anthropic."""
    return [
        {
            "name": "move_liquid",
            "description": "Moves liquid from a source container to a destination.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "Name of source vessel",
                    },
                    "destination": {
                        "type": "string",
                        "description": "Name of destination vessel",
                    },
                    "amount_ml": {"type": "number", "description": "Volume in mL"},
                },
                "required": ["source", "destination", "amount_ml"],
                "additionalProperties": False,
            },
        },
        {
            "name": "transform",
            "description": (
                "Applies a controlled transformation (e.g., temperature) to a vessel."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "Name of target vessel"},
                    "parameter": {
                        "type": "string",
                        "description": "Parameter to control (e.g., temperature_c)",
                    },
                    "target_value": {
                        "type": "number",
                        "description": "Desired value for the parameter",
                    },
                    "duration_s": {
                        "type": "number",
                        "description": "Duration in seconds",
                    },
                },
                "required": ["target", "parameter", "target_value", "duration_s"],
                "additionalProperties": False,
            },
        },
        {
            "name": "combine",
            "description": "Combines or mixes liquid contents in a target vessel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "Name of target vessel"},
                    "method": {
                        "type": "string",
                        "description": "Combination method (e.g., stir, shake, vortex)",
                    },
                    "duration_s": {
                        "type": "number",
                        "description": "Duration in seconds",
                    },
                },
                "required": ["target", "method", "duration_s"],
                "additionalProperties": False,
            },
        },
    ]


def get_tool_definitions_json(*, indent: int = 2) -> str:
    """Return tool definitions serialized as JSON."""
    return json.dumps(get_tool_definitions(), indent=indent)
