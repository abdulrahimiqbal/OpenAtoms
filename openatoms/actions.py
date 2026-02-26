"""Action primitives used to build OpenAtoms protocol graphs.

Example:
    >>> from openatoms.actions import Move
    >>> from openatoms.core import Container, Matter, Phase
    >>> from openatoms.units import Q_
    >>> src = Container(id="s", label="S", max_volume=Q_(100, "milliliter"), max_temp=Q_(100, "degC"), min_temp=Q_(0, "degC"))
    >>> dst = Container(id="d", label="D", max_volume=Q_(100, "milliliter"), max_temp=Q_(100, "degC"), min_temp=Q_(0, "degC"))
    >>> src.contents.append(Matter(name="H2O", phase=Phase.LIQUID, mass=Q_(10, "gram"), volume=Q_(10, "milliliter")))
    >>> Move(src, dst, Q_(5, "milliliter")).validate()
    True
"""

from __future__ import annotations

from typing import Optional

from .core import Container, Matter
from .errors import MassBalanceViolationError, OrderingConstraintError
from .units import Quantity, Q_, require_quantity, require_temperature, require_time, require_volume
from .validators import assert_thermal_safety, assert_volume_feasibility


class Action:
    """Base class for protocol actions."""

    def __init__(self) -> None:
        self.status = "pending"
        self.state_observation_json: Optional[str] = None

    def validate(self) -> bool:
        """Validate action constraints before execution.

        Example:
            >>> Action().validate()  # doctest: +IGNORE_EXCEPTION_DETAIL
            Traceback (most recent call last):
            ...
            NotImplementedError
        """
        raise NotImplementedError

    def execute(self) -> None:
        """Execute validated action.

        Example:
            >>> Action().execute()  # doctest: +IGNORE_EXCEPTION_DETAIL
            Traceback (most recent call last):
            ...
            NotImplementedError
        """
        raise NotImplementedError


class Move(Action):
    """Transfer liquid volume from one container to another."""

    def __init__(self, source: Container, destination: Container, amount: Quantity):
        super().__init__()
        self.source = source
        self.destination = destination
        self.amount = require_volume(amount)

    def validate(self) -> bool:
        if self.amount.to("milliliter").magnitude <= 0:
            raise OrderingConstraintError(
                description="Transfer volume must be positive.",
                actual_value=f"{self.amount:~P}",
                limit_value="> 0 milliliter",
                remediation_hint="Set transfer volume to a positive value with explicit units.",
            )

        if self.source.current_volume < self.amount.to(self.source.current_volume.units):
            raise MassBalanceViolationError(
                description=f"Source {self.source.label} does not contain enough volume.",
                actual_value=f"{self.source.current_volume:~P}",
                limit_value=f"{self.amount:~P}",
                remediation_hint=(
                    f"Reduce transfer volume to {self.source.current_volume:~P} or less, "
                    f"or replenish {self.source.label} before transfer."
                ),
            )

        assert_volume_feasibility(self.destination, self.amount)
        return True

    def execute(self) -> None:
        self.validate()
        requested_ml = self.amount.to("milliliter")
        remaining_ml = requested_ml
        transferred_matter: list[Matter] = []

        for matter in list(self.source.contents):
            if remaining_ml.magnitude <= 0:
                break

            matter_volume_ml = matter.volume.to("milliliter")
            pull_ml = min(matter_volume_ml.magnitude, remaining_ml.magnitude)
            if pull_ml <= 0:
                continue

            ratio = pull_ml / matter_volume_ml.magnitude
            pulled_volume = Q_(pull_ml, "milliliter")
            pulled_mass = matter.mass.to("gram") * ratio

            matter.volume = matter.volume.to("milliliter") - pulled_volume
            matter.mass = matter.mass.to("gram") - pulled_mass

            transferred_matter.append(
                Matter(
                    name=matter.name,
                    phase=matter.phase,
                    mass=pulled_mass.to("gram"),
                    volume=pulled_volume,
                    density=matter.density,
                    enthalpy_of_formation=matter.enthalpy_of_formation,
                    molecular_weight=matter.molecular_weight,
                    cas_number=matter.cas_number,
                    flash_point=matter.flash_point,
                    thermal_expansion_coefficient=matter.thermal_expansion_coefficient,
                    temperature=matter.temperature,
                )
            )

            remaining_ml -= pulled_volume

            if matter.volume.to("milliliter").magnitude <= 1e-12:
                self.source.contents.remove(matter)

        if remaining_ml.magnitude > 1e-9:
            raise MassBalanceViolationError(
                description="Transfer execution ended with unresolved requested volume.",
                actual_value=f"{remaining_ml:~P}",
                limit_value="0 milliliter",
                remediation_hint=(
                    "Recompute source composition and requested transfer amount; unresolved "
                    "volume indicates non-physical state drift."
                ),
            )

        self.destination.contents.extend(transferred_matter)
        self.status = "completed"


class Transform(Action):
    """Apply a controlled transformation to a target container."""

    def __init__(
        self,
        target: Container,
        parameter: str,
        target_value: Quantity,
        duration: Optional[Quantity] = None,
    ):
        super().__init__()
        self.target = target
        self.parameter = parameter
        self.target_value = require_quantity(target_value)
        self.duration = duration

    def validate(self) -> bool:
        if self.parameter != "temperature":
            raise OrderingConstraintError(
                description="Unsupported transform parameter.",
                actual_value=self.parameter,
                limit_value="temperature",
                remediation_hint="Use parameter='temperature' for supported transforms.",
            )

        target_temp = require_temperature(self.target_value).to("degC")
        delta = target_temp - self.target.average_temperature.to("degC")
        assert_thermal_safety(self.target, delta, self.duration)
        return True

    def execute(self) -> None:
        self.validate()
        final_temp = require_temperature(self.target_value).to("degC")
        for matter in self.target.contents:
            matter.temperature = final_temp
        self.status = "completed"


class Combine(Action):
    """Mix contents in a target container."""

    def __init__(self, target: Container, method: str, duration: Quantity):
        super().__init__()
        self.target = target
        self.method = method
        self.duration = require_time(duration)

    def validate(self) -> bool:
        if not self.target.contents:
            raise OrderingConstraintError(
                description=f"Cannot {self.method}: container {self.target.label} is empty.",
                actual_value="0 milliliter",
                limit_value="> 0 milliliter",
                remediation_hint=(
                    f"Add material to {self.target.label} before executing {self.method}."
                ),
            )
        if self.duration.to("second").magnitude <= 0:
            raise OrderingConstraintError(
                description="Combine duration must be positive.",
                actual_value=f"{self.duration:~P}",
                limit_value="> 0 second",
                remediation_hint="Increase combine duration above zero seconds.",
            )
        return True

    def execute(self) -> None:
        self.validate()
        self.status = "completed"


class Measure(Action):
    """Measure a property of a container using a virtual sensor."""

    def __init__(self, target: Container, sensor_type: str):
        super().__init__()
        self.target = target
        self.sensor_type = sensor_type
        self.result: Optional[Quantity] = None

    def validate(self) -> bool:
        if self.sensor_type not in {"volume", "temperature", "mass"}:
            raise OrderingConstraintError(
                description="Unsupported sensor type.",
                actual_value=self.sensor_type,
                limit_value="volume | temperature | mass",
                remediation_hint="Use one of: volume, temperature, mass.",
            )
        return True

    def execute(self) -> None:
        self.validate()
        if self.sensor_type == "volume":
            self.result = self.target.current_volume
        elif self.sensor_type == "temperature":
            self.result = self.target.average_temperature
        else:
            total_mass = Q_(0.0, "gram")
            for matter in self.target.contents:
                total_mass += matter.mass.to("gram")
            self.result = total_mass
        self.status = "completed"
