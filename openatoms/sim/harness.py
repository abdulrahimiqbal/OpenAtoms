"""Deterministic simulation harness with real simulator routing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from ..errors import SimulationDependencyError
from ..provenance import RunContext
from ..units import Q_
from .registry.kinetics_sim import VirtualReactor


@dataclass(frozen=True)
class SimulationThresholds:
    """Pass/fail threshold controls for simulation gating."""

    max_temperature_c: float = 120.0
    max_pressure_pa: float = 2_000_000.0


class SimulationHarness:
    """Routes protocol checks to available real simulators for safety gating."""

    def __init__(self, *, simulator_version: str = "sim-harness-1.0.0"):
        self.simulator_version = simulator_version

    def run(
        self,
        *,
        dag: Any,
        run_context: RunContext,
        thresholds: Optional[SimulationThresholds] = None,
    ) -> Dict[str, Any]:
        resolved_thresholds = thresholds or SimulationThresholds()
        payload = json.loads(dag.export_json())
        action_types = {
            str(step.get("action_type", ""))
            for step in payload.get("steps", [])
            if isinstance(step, dict)
        }

        if "Transform" not in action_types:
            message = (
                "No real simulator is registered for action types "
                f"{sorted(action_types) if action_types else ['<none>']}."
            )
            observation = {
                "type": "StateObservation",
                "schema_version": "1.0.0",
                "simulator_version": self.simulator_version,
                "seed": run_context.seed,
                "correlation_id": run_context.correlation_id,
                "status": "not_simulated",
                "check_type": "not_simulated",
                "message": message,
                "state": {},
                "errors": [],
            }
            return {"status": "not_simulated", "check_type": "not_simulated", "observation": observation}

        initial_temp_k = 900.0
        residence_time_s = 0.02
        for step in payload.get("steps", []):
            if not isinstance(step, dict) or step.get("action_type") != "Transform":
                continue
            parameters = step.get("parameters", {})
            if not isinstance(parameters, dict):
                continue
            target_value = parameters.get("target_value")
            if isinstance(target_value, dict):
                try:
                    value = float(target_value.get("value"))
                    unit = str(target_value.get("unit", "kelvin"))
                    initial_temp_k = Q_(value, unit).to("kelvin").magnitude
                except Exception:
                    pass
            duration = parameters.get("duration")
            if isinstance(duration, dict):
                try:
                    value = float(duration.get("value"))
                    unit = str(duration.get("unit", "second"))
                    residence_time_s = Q_(value, unit).to("second").magnitude
                except Exception:
                    pass

        try:
            output = VirtualReactor().simulate_hydrogen_oxygen_combustion(
                initial_temp_k=initial_temp_k,
                residence_time_s=residence_time_s,
            )
        except SimulationDependencyError as exc:
            observation = {
                "type": "StateObservation",
                "schema_version": "1.0.0",
                "simulator_version": self.simulator_version,
                "seed": run_context.seed,
                "correlation_id": run_context.correlation_id,
                "status": "not_simulated",
                "check_type": "not_simulated",
                "message": str(exc),
                "state": {},
                "errors": [],
            }
            return {
                "status": "not_simulated",
                "check_type": "not_simulated",
                "observation": observation,
            }

        trajectory = output["trajectory"]
        peak_temp_k = max(trajectory.temperatures_k)
        peak_temp_c = Q_(peak_temp_k, "kelvin").to("degC").magnitude
        peak_pressure_pa = max(trajectory.pressures_pa)

        status = "ok"
        errors = []
        if peak_temp_c > resolved_thresholds.max_temperature_c:
            status = "failed"
            errors.append(
                {
                    "type": "SimulationThresholdExceeded",
                    "details": {
                        "metric": "temperature_c",
                        "observed": peak_temp_c,
                        "max_allowed": resolved_thresholds.max_temperature_c,
                    },
                }
            )
        if peak_pressure_pa > resolved_thresholds.max_pressure_pa:
            status = "failed"
            errors.append(
                {
                    "type": "SimulationThresholdExceeded",
                    "details": {
                        "metric": "pressure_pa",
                        "observed": peak_pressure_pa,
                        "max_allowed": resolved_thresholds.max_pressure_pa,
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
            "check_type": "safety_gate",
            "state": {
                "peak_temperature_c": round(peak_temp_c, 6),
                "peak_pressure_pa": round(peak_pressure_pa, 6),
                "solver_rtol": trajectory.solver_rtol,
                "solver_atol": trajectory.solver_atol,
                "mechanism_file": trajectory.mechanism_file,
                "mechanism_hash": trajectory.mechanism_hash,
                "cantera_version": trajectory.cantera_version,
                "integrator": trajectory.integrator,
                "trajectory_points": len(trajectory.times_s),
            },
            "errors": errors,
        }

        return {"status": status, "check_type": "safety_gate", "observation": observation}

    @staticmethod
    def write_observation(path: Path, observation: Dict[str, Any]) -> None:
        """Write standardized state observation artifact to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(observation, indent=2), encoding="utf-8")
