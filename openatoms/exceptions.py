"""Structured physics validation exceptions for agent feedback loops."""

import json
from typing import Optional


class PhysicsError(Exception):
    """Base exception for all OpenAtoms physical validations."""

    ERROR_CONTRACT_VERSION = "1.1.0"

    def __init__(self, message: str, error_type: str, details: dict):
        super().__init__(message)
        self.error_type = error_type
        self.details = details
        self.correlation_id: Optional[str] = None

    def to_agent_payload(self, correlation_id: Optional[str] = None) -> str:
        """
        Serialize the error into structured JSON designed for LLM self-correction.
        """
        resolved_correlation = correlation_id or self.correlation_id
        payload = {
            "status": "failed",
            "error_type": self.error_type,
            "error_contract_version": self.ERROR_CONTRACT_VERSION,
            "message": str(self),
            "physical_constraints": self.details,
            "hint": "Adjust your parameters to fit within the physical_constraints provided.",
        }
        if resolved_correlation:
            payload["correlation_id"] = resolved_correlation
        return json.dumps(payload, indent=2)


class InsufficientMassError(PhysicsError):
    """Raised when requested transfer volume exceeds available source volume."""

    def __init__(self, container_name: str, requested_ml: float, available_ml: float):
        super().__init__(
            message=(
                f"Cannot extract {requested_ml}mL. '{container_name}' only contains "
                f"{available_ml}mL."
            ),
            error_type="InsufficientMassError",
            details={
                "container": container_name,
                "requested_amount_ml": requested_ml,
                "available_amount_ml": available_ml,
            },
        )


class CapacityExceededError(PhysicsError):
    """Raised when a move would overflow the destination container."""

    def __init__(self, container_name: str, projected_vol_ml: float, max_vol_ml: float):
        super().__init__(
            message=(
                f"Overflow risk: Moving matter into '{container_name}' results in "
                f"{projected_vol_ml}mL, exceeding the max capacity of {max_vol_ml}mL."
            ),
            error_type="CapacityExceededError",
            details={
                "container": container_name,
                "projected_volume_ml": projected_vol_ml,
                "max_capacity_ml": max_vol_ml,
            },
        )


class ThermodynamicViolationError(PhysicsError):
    """Raised when a thermal target violates container bounds."""

    def __init__(
        self,
        container_name: str,
        target_temp: float,
        limit_temp: float,
        boundary: str,
    ):
        super().__init__(
            message=(
                f"Thermal constraint violated. Target {target_temp}°C exceeds "
                f"'{container_name}' {boundary} limit of {limit_temp}°C."
            ),
            error_type="ThermodynamicViolationError",
            details={
                "container": container_name,
                "attempted_temp_c": target_temp,
                f"{boundary}_limit_c": limit_temp,
            },
        )


class EmptyContainerError(PhysicsError):
    """Raised when a combine operation targets an empty container."""

    def __init__(self, container_name: str, method: str):
        super().__init__(
            message=(
                f"Cannot apply '{method}'. Container '{container_name}' is empty and "
                "cannot be processed."
            ),
            error_type="EmptyContainerError",
            details={
                "container": container_name,
                "method": method,
                "available_amount_ml": 0.0,
            },
        )


class StructuralIntegrityError(PhysicsError):
    """Raised when simulated pressure exceeds vessel structural limits."""

    def __init__(
        self,
        vessel_name: str,
        observed_pressure_pa: float,
        burst_pressure_pa: float,
        state_observation_json: Optional[str] = None,
    ):
        details = {
            "vessel": vessel_name,
            "observed_pressure_pa": observed_pressure_pa,
            "burst_pressure_pa": burst_pressure_pa,
        }
        if state_observation_json is not None:
            details["state_observation_json"] = state_observation_json

        super().__init__(
            message=(
                f"Structural failure risk in '{vessel_name}'. Simulated pressure "
                f"{observed_pressure_pa} Pa exceeds burst pressure {burst_pressure_pa} Pa."
            ),
            error_type="StructuralIntegrityError",
            details=details,
        )


class SimulationDependencyError(PhysicsError):
    """Raised when an optional science simulation dependency is unavailable."""

    def __init__(self, dependency: str, import_error: str):
        super().__init__(
            message=(
                f"Science simulation dependency '{dependency}' is unavailable. "
                "Install it to run science-mode simulations."
            ),
            error_type="SimulationDependencyError",
            details={
                "dependency": dependency,
                "import_error": import_error,
            },
        )


class DependencyGraphError(PhysicsError):
    """Raised when a dependency graph is malformed or cyclic."""

    def __init__(self, message: str, details: dict):
        super().__init__(message=message, error_type="DependencyGraphError", details=details)


class OrderingViolationError(PhysicsError):
    """Raised when action ordering rules are violated."""

    def __init__(self, message: str, details: dict):
        super().__init__(message=message, error_type="OrderingViolationError", details=details)


class CompatibilityViolationError(PhysicsError):
    """Raised when incompatible materials are mixed or transferred."""

    def __init__(self, message: str, details: dict):
        super().__init__(message=message, error_type="CompatibilityViolationError", details=details)


class HazardClassViolationError(PhysicsError):
    """Raised when hazard constraints or safe-default rules are violated."""

    def __init__(self, message: str, details: dict):
        super().__init__(message=message, error_type="HazardClassViolationError", details=details)


class CapabilityBoundError(PhysicsError):
    """Raised when requested steps exceed a target capability profile."""

    def __init__(self, message: str, details: dict):
        super().__init__(message=message, error_type="CapabilityBoundError", details=details)


class PolicyViolationError(PhysicsError):
    """Raised when runtime policy gates reject an execution."""

    def __init__(self, message: str, details: dict):
        super().__init__(message=message, error_type="PolicyViolationError", details=details)
