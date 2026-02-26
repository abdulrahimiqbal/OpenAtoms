"""Backward-compatible exception exports.

Example:
    >>> from openatoms.exceptions import CapacityExceededError
    >>> isinstance(CapacityExceededError("overflow", "120 mL", "100 mL", "reduce"), Exception)
    True
"""

from __future__ import annotations

from .errors import (
    MassBalanceViolationError,
    OrderingConstraintError,
    PhysicsError,
    ReactionFeasibilityError,
    SimulationDependencyError,
    ThermalExcursionError,
    VolumeOverflowError,
)


class InsufficientMassError(MassBalanceViolationError):
    """Alias for legacy insufficient-mass errors."""


class CapacityExceededError(VolumeOverflowError):
    """Alias for legacy capacity errors."""


class ThermodynamicViolationError(ThermalExcursionError):
    """Alias for legacy thermal errors."""


class EmptyContainerError(OrderingConstraintError):
    """Alias for legacy empty-container errors."""


class StructuralIntegrityError(ThermalExcursionError):
    """Alias for legacy structural errors."""


class DependencyGraphError(OrderingConstraintError):
    """Alias for dependency graph constraint errors."""


class OrderingViolationError(OrderingConstraintError):
    """Alias for ordering validation errors."""


class CompatibilityViolationError(OrderingConstraintError):
    """Alias for compatibility errors."""


class HazardClassViolationError(OrderingConstraintError):
    """Alias for hazard-policy errors."""


class CapabilityBoundError(OrderingConstraintError):
    """Alias for capability boundary errors."""


class PolicyViolationError(OrderingConstraintError):
    """Alias for policy gating errors."""


__all__ = [
    "PhysicsError",
    "VolumeOverflowError",
    "ThermalExcursionError",
    "MassBalanceViolationError",
    "OrderingConstraintError",
    "ReactionFeasibilityError",
    "SimulationDependencyError",
    "InsufficientMassError",
    "CapacityExceededError",
    "ThermodynamicViolationError",
    "EmptyContainerError",
    "StructuralIntegrityError",
    "DependencyGraphError",
    "OrderingViolationError",
    "CompatibilityViolationError",
    "HazardClassViolationError",
    "CapabilityBoundError",
    "PolicyViolationError",
]
