"""Science-grade thermo-kinetic simulation backed by Cantera."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ...exceptions import SimulationDependencyError, StructuralIntegrityError


def _state_observation_json(
    *,
    status: str,
    inputs: Dict[str, Any],
    state: Dict[str, Any],
    errors: Optional[list[dict]] = None,
) -> str:
    payload = {
        "type": "StateObservation",
        "node": "Thermo-Kinetic",
        "status": status,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": inputs,
        "state": state,
        "errors": errors or [],
    }
    return json.dumps(payload, indent=2)


@dataclass(frozen=True)
class Vessel:
    """Mechanical envelope used for integrity checks."""

    name: str
    burst_pressure_pa: float


class VirtualReactor:
    """Hydrogen-oxygen combustion simulator that exposes thermodynamic objects."""

    def __init__(
        self,
        *,
        mechanism: str = "h2o2.yaml",
        composition: str = "H2:2,O2:1,N2:3.76",
        initial_pressure_pa: float = 101325.0,
        reactor_volume_m3: float = 1e-3,
    ):
        self.mechanism = mechanism
        self.composition = composition
        self.initial_pressure_pa = initial_pressure_pa
        self.reactor_volume_m3 = reactor_volume_m3

    @staticmethod
    def _load_cantera():
        try:
            import cantera as ct  # type: ignore
        except ImportError as exc:  # pragma: no cover - exercised when optional dep missing
            raise SimulationDependencyError("cantera", str(exc)) from exc
        return ct

    def simulate_hydrogen_oxygen_combustion(
        self,
        *,
        initial_temp_k: float,
        residence_time_s: float = 0.02,
        flow_rate_slpm: float = 1.0,
        max_steps: int = 4000,
        vessel: Optional[Vessel] = None,
    ) -> Dict[str, Any]:
        """Run a real Cantera simulation and emit a StateObservation JSON payload."""
        ct = self._load_cantera()

        gas = ct.Solution(self.mechanism)
        gas.TPX = initial_temp_k, self.initial_pressure_pa, self.composition

        reactor = ct.IdealGasReactor(
            gas,
            energy="on",
            volume=self.reactor_volume_m3,
        )
        network = ct.ReactorNet([reactor])

        elapsed_s = 0.0
        peak_pressure_pa = float(reactor.thermo.P)
        step_count = 0

        while elapsed_s < residence_time_s and step_count < max_steps:
            elapsed_s = float(network.step())
            peak_pressure_pa = max(peak_pressure_pa, float(reactor.thermo.P))
            step_count += 1

        state = {
            "elapsed_s": elapsed_s,
            "steps": step_count,
            "temperature_k": float(reactor.thermo.T),
            "pressure_pa": float(reactor.thermo.P),
            "peak_pressure_pa": peak_pressure_pa,
        }
        inputs = {
            "reaction": "Hydrogen-Oxygen combustion",
            "initial_temp_k": initial_temp_k,
            "initial_pressure_pa": self.initial_pressure_pa,
            "residence_time_s": residence_time_s,
            "flow_rate_slpm": flow_rate_slpm,
            "mechanism": self.mechanism,
        }

        if vessel is not None and peak_pressure_pa > vessel.burst_pressure_pa:
            failure_json = _state_observation_json(
                status="failed",
                inputs=inputs,
                state=state,
                errors=[
                    {
                        "type": "StructuralIntegrityError",
                        "message": (
                            f"Pressure spike exceeded burst pressure for '{vessel.name}'."
                        ),
                        "details": {
                            "burst_pressure_pa": vessel.burst_pressure_pa,
                            "observed_pressure_pa": peak_pressure_pa,
                        },
                    }
                ],
            )
            raise StructuralIntegrityError(
                vessel_name=vessel.name,
                observed_pressure_pa=peak_pressure_pa,
                burst_pressure_pa=vessel.burst_pressure_pa,
                state_observation_json=failure_json,
            )

        state_observation_json = _state_observation_json(
            status="ok",
            inputs=inputs,
            state=state,
        )
        return {
            "state_observation_json": state_observation_json,
            "thermo_state": reactor.thermo,
            "reactor_state": reactor,
            "reactor_network": network,
        }

