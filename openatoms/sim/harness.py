"""Deterministic simulation harness with regression-friendly artifacts."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from ..provenance import RunContext


@dataclass(frozen=True)
class SimulationThresholds:
    """Pass/fail threshold controls for simulation gating."""

    max_temperature_c: float = 120.0
    max_pressure_pa: float = 2_000_000.0


class SimulationHarness:
    """Produces deterministic simulation outcomes for protocol gating."""

    def __init__(self, *, simulator_version: str = "sim-harness-1.0.0"):
        self.simulator_version = simulator_version

    def run(
        self,
        *,
        dag: Any,
        run_context: RunContext,
        thresholds: Optional[SimulationThresholds] = None,
    ) -> Dict[str, Any]:
        thresholds = thresholds or SimulationThresholds()
        payload = json.loads(dag.export_json())

        rng = random.Random(run_context.seed)
        noise = rng.uniform(-0.25, 0.25)
        estimated_temp_c = 20.0 + (len(payload.get("steps", [])) * 5.0) + noise
        estimated_pressure_pa = 101_325.0 + (len(payload.get("steps", [])) * 1_000.0)

        status = "ok"
        errors = []
        if estimated_temp_c > thresholds.max_temperature_c:
            status = "failed"
            errors.append(
                {
                    "type": "SimulationThresholdExceeded",
                    "details": {
                        "metric": "temperature_c",
                        "observed": estimated_temp_c,
                        "max_allowed": thresholds.max_temperature_c,
                    },
                }
            )

        if estimated_pressure_pa > thresholds.max_pressure_pa:
            status = "failed"
            errors.append(
                {
                    "type": "SimulationThresholdExceeded",
                    "details": {
                        "metric": "pressure_pa",
                        "observed": estimated_pressure_pa,
                        "max_allowed": thresholds.max_pressure_pa,
                    },
                }
            )

        observation = {
            "type": "StateObservation",
            "schema_version": "1.0.0",
            "simulator_version": self.simulator_version,
            "seed": run_context.seed,
            "correlation_id": run_context.correlation_id,
            "status": status,
            "state": {
                "estimated_temperature_c": round(estimated_temp_c, 6),
                "estimated_pressure_pa": round(estimated_pressure_pa, 6),
            },
            "errors": errors,
        }

        return {"status": status, "observation": observation}

    @staticmethod
    def write_observation(path: Path, observation: Dict[str, Any]) -> None:
        """Write standardized state observation artifact to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(observation, indent=2), encoding="utf-8")
