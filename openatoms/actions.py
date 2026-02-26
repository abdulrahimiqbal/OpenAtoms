"""Action primitives used to build OpenAtoms protocol graphs."""

from typing import Optional, Union

from .core import Container
from .exceptions import (
    CapacityExceededError,
    CompatibilityViolationError,
    EmptyContainerError,
    InsufficientMassError,
    ThermodynamicViolationError,
)
from .units import Quantity, as_time_s, as_volume_ml


class Action:
    """Base class for all protocol actions."""

    def __init__(self):
        self.status = "pending"
        self.state_observation_json: Optional[str] = None

    def validate(self) -> bool:
        """Validate that an action is physically executable."""
        raise NotImplementedError


class Move(Action):
    """Transfer liquid volume from one container to another."""

    def __init__(
        self,
        source: Container,
        destination: Container,
        amount_ml: Union[float, Quantity],
    ):
        """Create a move operation."""
        super().__init__()
        self.source = source
        self.destination = destination
        self.amount_ml = as_volume_ml(amount_ml)

    def validate(self):
        """Validate source availability and destination capacity."""
        if self.source.current_volume < self.amount_ml:
            raise InsufficientMassError(
                self.source.name, self.amount_ml, self.source.current_volume
            )

        projected_vol = self.destination.current_volume + self.amount_ml
        if projected_vol > self.destination.max_volume_ml:
            raise CapacityExceededError(
                self.destination.name, projected_vol, self.destination.max_volume_ml
            )

        source_hazards = self.source.hazard_classes
        destination_hazards = self.destination.hazard_classes
        blocked = self.destination.incompatible_hazards.intersection(source_hazards)
        if blocked:
            raise CompatibilityViolationError(
                message=(
                    f"Destination '{self.destination.name}' rejects hazard classes: "
                    f"{sorted(blocked)}."
                ),
                details={
                    "destination": self.destination.name,
                    "blocked_hazard_classes": sorted(blocked),
                    "source_hazard_classes": sorted(source_hazards),
                    "destination_hazard_classes": sorted(destination_hazards),
                },
            )

        return True


class Transform(Action):
    """Apply a controlled transformation to a target container."""

    def __init__(
        self,
        target: Container,
        parameter: str,
        target_value: float,
        duration_s: Union[float, Quantity],
    ):
        """Create a transformation action."""
        super().__init__()
        self.target = target
        self.parameter = parameter
        self.target_value = target_value
        self.duration_s = as_time_s(duration_s)

    def validate(self):
        """Validate that transformation parameters are within safe limits."""
        if self.parameter == "temperature_c":
            if self.target_value > self.target.max_temp_c:
                raise ThermodynamicViolationError(
                    self.target.name,
                    self.target_value,
                    self.target.max_temp_c,
                    "maximum",
                )
            if self.target_value < self.target.min_temp_c:
                raise ThermodynamicViolationError(
                    self.target.name,
                    self.target_value,
                    self.target.min_temp_c,
                    "minimum",
                )

        return True


class Combine(Action):
    """Mix or combine the contents of a container."""

    def __init__(
        self,
        target: Container,
        method: str,
        duration_s: Union[float, Quantity],
    ):
        """Create a mixing action."""
        super().__init__()
        self.target = target
        self.method = method
        self.duration_s = as_time_s(duration_s)

    def validate(self):
        """Validate that the target contains material to combine."""
        if self.target.current_volume == 0:
            raise EmptyContainerError(self.target.name, self.method)

        return True


class Measure(Action):
    """Measure a property of a container with a virtual sensor."""

    def __init__(self, target: Container, sensor_type: str):
        """Create a measurement action."""
        super().__init__()
        self.target = target
        self.sensor_type = sensor_type
        self.result = None

    def validate(self):
        """Always valid for now; concrete adapters may enforce constraints."""
        return True
