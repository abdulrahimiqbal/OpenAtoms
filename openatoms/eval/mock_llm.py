"""Mock LLM protocol generator for benchmark validation without API keys.

Example:
    >>> llm = MockLLM(seed=3)
    >>> protocol = llm.generate_protocol({"id": "p1", "domain": "pipetting", "prompt": "x"}, feedback=None)
    >>> "actions" in protocol
    True
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any


@dataclass
class MockLLM:
    """Seeded protocol generator that intentionally creates fixable violations."""

    seed: int = 42

    def generate_protocol(self, benchmark_item: dict[str, Any], feedback: dict[str, Any] | None) -> dict[str, Any]:
        """Generate synthetic protocol actions.

        Without feedback, emits a violation with high probability.
        With feedback, repairs the likely violating parameter.
        """
        rng = random.Random(f"{self.seed}:{benchmark_item['id']}:{feedback}")
        domain = benchmark_item["domain"]

        if domain in {"chemistry", "pipetting"}:
            move_amount = 650 if feedback is None and rng.random() < 0.7 else 120
            target_temp = 250 if feedback is None and rng.random() < 0.4 else 60
            if feedback and feedback.get("constraint_type") == "volume":
                move_amount = 120
            if feedback and feedback.get("constraint_type") == "thermal":
                target_temp = 60
            return {
                "id": benchmark_item["id"],
                "domain": domain,
                "actions": [
                    {"action": "move", "source": "A", "destination": "B", "amount_ul": move_amount},
                    {
                        "action": "heat",
                        "temperature_c": target_temp,
                        "duration_s": 30,
                    },
                ],
            }

        # robotics domain
        force = 3000 if feedback is None and rng.random() < 0.6 else 80
        area_cm2 = 0.2 if feedback is None and rng.random() < 0.6 else 2.0
        if feedback:
            force = 80
            area_cm2 = 2.0

        return {
            "id": benchmark_item["id"],
            "domain": domain,
            "actions": [
                {
                    "action": "vial",
                    "material": "glass",
                    "force_n": force,
                    "area_cm2": area_cm2,
                }
            ],
        }
