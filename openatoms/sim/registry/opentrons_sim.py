"""Opentrons simulation wrapper with structured StateObservation outputs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from ...exceptions import PhysicsError, SimulationDependencyError

_OUT_OF_BOUNDS_PATTERNS = (
    "out of bounds",
    "out-of-bounds",
    "outside of deck",
    "outside deck",
    "deck collision",
    "invalid deck slot",
)


def _state_observation_json(
    *,
    status: str,
    inputs: Dict[str, Any],
    state: Dict[str, Any],
    errors: Optional[list[dict]] = None,
) -> str:
    payload = {
        "type": "StateObservation",
        "schema_version": "1.0.0",
        "node": "Bio-Kinetic",
        "status": status,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": inputs,
        "state": state,
        "errors": errors or [],
    }
    return json.dumps(payload, indent=2)


class OpentronsSimValidator:
    """Validate Opentrons protocols via `opentrons.simulate`."""

    @staticmethod
    def _load_opentrons_simulate():
        try:
            from opentrons import simulate  # type: ignore
        except ImportError as exc:  # pragma: no cover - exercised when optional dep missing
            raise SimulationDependencyError("opentrons", str(exc)) from exc
        return simulate

    @staticmethod
    def _is_out_of_bounds(exc: Exception) -> bool:
        message = str(exc).lower()
        return any(pattern in message for pattern in _OUT_OF_BOUNDS_PATTERNS)

    @staticmethod
    def _run_simulation(simulate_module: Any, protocol_path: Path) -> Any:
        simulate_fn = getattr(simulate_module, "simulate", None)
        if simulate_fn is None:
            raise AttributeError("opentrons.simulate.simulate entrypoint not found.")

        with protocol_path.open("rb") as protocol_file:
            last_type_error: Optional[TypeError] = None
            attempts = [
                lambda: simulate_fn(protocol_file),
                lambda: simulate_fn(protocol_file=protocol_file),
                lambda: simulate_fn(str(protocol_path)),
                lambda: simulate_fn(protocol_file=str(protocol_path)),
            ]
            for attempt in attempts:
                protocol_file.seek(0)
                try:
                    return attempt()
                except TypeError as exc:
                    last_type_error = exc
                    continue
            if last_type_error is not None:
                raise last_type_error

        raise RuntimeError("Unable to execute opentrons.simulate with supported signatures.")

    def validate_protocol(self, protocol_path: str) -> Dict[str, Any]:
        """Simulate a protocol and return StateObservation JSON and any PhysicsError."""
        path = Path(protocol_path)
        inputs = {"protocol_path": str(path)}

        if not path.exists():
            physics_error = PhysicsError(
                message=f"Protocol file not found at '{path}'.",
                error_type="ProtocolNotFoundError",
                details={"protocol_path": str(path)},
            )
            state_observation_json = _state_observation_json(
                status="failed",
                inputs=inputs,
                state={"executed_steps": 0},
                errors=[
                    {
                        "type": physics_error.error_type,
                        "message": str(physics_error),
                        "details": physics_error.details,
                    }
                ],
            )
            return {
                "state_observation_json": state_observation_json,
                "error": physics_error,
                "run_log": None,
            }

        simulate_module = self._load_opentrons_simulate()

        try:
            run_log = self._run_simulation(simulate_module, path)
        except Exception as exc:
            if self._is_out_of_bounds(exc):
                physics_error = PhysicsError(
                    message=f"Opentrons out-of-bounds simulation failure: {exc}",
                    error_type="DeckOutOfBoundsError",
                    details={
                        "protocol_path": str(path),
                        "exception_type": type(exc).__name__,
                    },
                )
                state_observation_json = _state_observation_json(
                    status="failed",
                    inputs=inputs,
                    state={"executed_steps": 0},
                    errors=[
                        {
                            "type": physics_error.error_type,
                            "message": str(physics_error),
                            "details": physics_error.details,
                        }
                    ],
                )
                return {
                    "state_observation_json": state_observation_json,
                    "error": physics_error,
                    "run_log": None,
                }
            raise

        executed_steps = len(run_log) if isinstance(run_log, list) else None
        state_observation_json = _state_observation_json(
            status="ok",
            inputs=inputs,
            state={"executed_steps": executed_steps},
        )
        return {
            "state_observation_json": state_observation_json,
            "error": None,
            "run_log": run_log,
        }
