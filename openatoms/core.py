"""Core physical primitives used by OpenAtoms.

Example:
    >>> from openatoms.core import Container, Matter, Phase
    >>> from openatoms.units import Q_
    >>> water = Matter(name="H2O", phase=Phase.LIQUID, mass=Q_(10, "gram"), volume=Q_(10, "milliliter"))
    >>> vessel = Container(id="v1", label="Vessel 1", max_volume=Q_(100, "milliliter"), max_temp=Q_(120, "degC"), min_temp=Q_(-20, "degC"), contents=[water])
    >>> round(vessel.current_volume.to("milliliter").magnitude, 2)
    10
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .errors import VolumeOverflowError
from .ids import stable_id
from .units import Quantity, Q_, quantity_json, require_mass, require_quantity, require_temperature, require_volume


class Phase(str, Enum):
    """Supported physical phases."""

    SOLID = "solid"
    LIQUID = "liquid"
    GAS = "gas"
    PLASMA = "plasma"


class Matter(BaseModel):
    """Physical material with explicit units.

    Parameters:
        name: Human-readable identifier.
        phase: Physical phase.
        mass: Mass quantity with mass units.
        volume: Volume quantity with volume units.
        density: Optional density quantity (mass/volume). If omitted, derived from mass/volume.
        enthalpy_of_formation: Optional thermochemistry term (kJ/mol).
        molecular_weight: Optional molecular weight (g/mol).
        cas_number: Optional CAS registry number for external property lookup.
        flash_point: Optional flash point for thermal safety checks.
        thermal_expansion_coefficient: Volumetric expansion coefficient in 1/K.

    Raises:
        TypeError: If a physical field is passed without units.
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True,
        json_encoders={Quantity: quantity_json},
    )

    name: str
    phase: Phase
    mass: Quantity
    volume: Quantity
    density: Optional[Quantity] = None
    enthalpy_of_formation: Optional[Quantity] = None
    molecular_weight: Optional[Quantity] = None
    cas_number: Optional[str] = None
    flash_point: Optional[Quantity] = None
    thermal_expansion_coefficient: float = Field(default=2.14e-4, ge=0.0)
    temperature: Quantity = Q_(25.0, "degC")

    @field_validator("mass")
    @classmethod
    def _validate_mass(cls, value: Quantity) -> Quantity:
        return require_mass(value)

    @field_validator("volume")
    @classmethod
    def _validate_volume(cls, value: Quantity) -> Quantity:
        return require_volume(value)

    @field_validator("density")
    @classmethod
    def _validate_density(cls, value: Optional[Quantity]) -> Optional[Quantity]:
        if value is None:
            return None
        quantity = require_quantity(value)
        if not quantity.check("[mass] / [length] ** 3"):
            raise TypeError("Density must have mass/volume units.")
        return quantity

    @field_validator("enthalpy_of_formation")
    @classmethod
    def _validate_enthalpy(cls, value: Optional[Quantity]) -> Optional[Quantity]:
        if value is None:
            return None
        quantity = require_quantity(value)
        if not quantity.check("[mass] * [length] ** 2 / [time] ** 2 / [substance]"):
            raise TypeError("Enthalpy of formation must have energy/mol units.")
        return quantity

    @field_validator("molecular_weight")
    @classmethod
    def _validate_molecular_weight(cls, value: Optional[Quantity]) -> Optional[Quantity]:
        if value is None:
            return None
        quantity = require_quantity(value)
        if not quantity.check("[mass] / [substance]"):
            raise TypeError("Molecular weight must have mass/mol units.")
        return quantity

    @field_validator("flash_point")
    @classmethod
    def _validate_flash_point(cls, value: Optional[Quantity]) -> Optional[Quantity]:
        if value is None:
            return None
        return require_temperature(value)

    @field_validator("temperature")
    @classmethod
    def _validate_temperature(cls, value: Quantity) -> Quantity:
        return require_temperature(value)

    @model_validator(mode="after")
    def _derive_density(self) -> "Matter":
        if self.density is None:
            self.density = (self.mass / self.volume).to("gram / milliliter")
        return self

    @property
    def id(self) -> str:
        """Stable identifier for IR exports.

        Example:
            >>> from openatoms.core import Matter, Phase
            >>> from openatoms.units import Q_
            >>> Matter(name="NaCl", phase=Phase.SOLID, mass=Q_(1, "gram"), volume=Q_(0.4, "milliliter")).id.startswith("matter_")
            True
        """
        return stable_id("matter", self.name)

    def to_reference(self) -> dict[str, object]:
        """Return deterministic reference metadata.

        Example:
            >>> from openatoms.core import Matter, Phase
            >>> from openatoms.units import Q_
            >>> ref = Matter(name="H2O", phase=Phase.LIQUID, mass=Q_(1, "gram"), volume=Q_(1, "milliliter")).to_reference()
            >>> ref["name"]
            'H2O'
        """
        payload: dict[str, object] = {
            "id": self.id,
            "name": self.name,
            "phase": self.phase.value,
            "mass": quantity_json(self.mass),
            "volume": quantity_json(self.volume),
            "density": quantity_json(self.density) if self.density is not None else None,
            "cas_number": self.cas_number,
        }
        if self.enthalpy_of_formation is not None:
            payload["enthalpy_of_formation"] = quantity_json(self.enthalpy_of_formation)
        if self.molecular_weight is not None:
            payload["molecular_weight"] = quantity_json(self.molecular_weight)
        if self.flash_point is not None:
            payload["flash_point"] = quantity_json(self.flash_point)
        payload["temperature"] = quantity_json(self.temperature)
        return payload


class Container(BaseModel):
    """Bounded vessel with unit-safe capacity and thermal limits."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True,
        json_encoders={Quantity: quantity_json},
    )

    id: str
    label: str
    max_volume: Quantity
    max_temp: Quantity
    min_temp: Quantity
    contents: list[Matter] = Field(default_factory=list)

    @field_validator("max_volume")
    @classmethod
    def _validate_max_volume(cls, value: Quantity) -> Quantity:
        return require_volume(value)

    @field_validator("max_temp", "min_temp")
    @classmethod
    def _validate_temperature_bounds(cls, value: Quantity) -> Quantity:
        return require_temperature(value)

    @model_validator(mode="after")
    def _validate_capacity(self) -> "Container":
        if self.current_volume > self.max_volume.to(self.current_volume.units):
            remediation = (
                f"Reduce total content volume in {self.label} below "
                f"{self.max_volume:~P} before execution."
            )
            raise VolumeOverflowError(
                description=(
                    f"Container {self.label} exceeds max volume during invariant check."
                ),
                actual_value=f"{self.current_volume:~P}",
                limit_value=f"{self.max_volume:~P}",
                remediation_hint=remediation,
            )
        return self

    @property
    def current_volume(self) -> Quantity:
        """Return total contained volume with full unit checking.

        Example:
            >>> from openatoms.core import Container
            >>> from openatoms.units import Q_
            >>> c = Container(id="c1", label="C", max_volume=Q_(10, "milliliter"), max_temp=Q_(100, "degC"), min_temp=Q_(0, "degC"))
            >>> c.current_volume.to("milliliter").magnitude
            0
        """
        unit = self.max_volume.units
        total = Q_(0, unit)
        for matter in self.contents:
            total += matter.volume.to(unit)
        return total

    @property
    def average_temperature(self) -> Quantity:
        """Return volume-weighted average temperature of contents.

        Example:
            >>> from openatoms.core import Container, Matter, Phase
            >>> from openatoms.units import Q_
            >>> c = Container(id="c1", label="C", max_volume=Q_(100, "milliliter"), max_temp=Q_(120, "degC"), min_temp=Q_(-20, "degC"))
            >>> c.contents.append(Matter(name="A", phase=Phase.LIQUID, mass=Q_(1, "gram"), volume=Q_(1, "milliliter")))
            >>> round(c.average_temperature.to("degC").magnitude, 1)
            25.0
        """
        if not self.contents:
            return Q_(25.0, "degC")
        weighted_kelvin = Q_(0.0, "kelvin * milliliter")
        total_volume = Q_(0.0, "milliliter")
        for matter in self.contents:
            weighted_kelvin += matter.temperature.to("kelvin") * matter.volume.to("milliliter")
            total_volume += matter.volume.to("milliliter")
        return (weighted_kelvin / total_volume).to("degC")

    def to_reference(self) -> dict[str, object]:
        """Return deterministic reference metadata.

        Example:
            >>> from openatoms.core import Container
            >>> from openatoms.units import Q_
            >>> ref = Container(id="c1", label="C", max_volume=Q_(10, "milliliter"), max_temp=Q_(100, "degC"), min_temp=Q_(0, "degC")).to_reference()
            >>> ref["label"]
            'C'
        """
        return {
            "id": self.id,
            "label": self.label,
            "max_volume": quantity_json(self.max_volume),
            "max_temp": quantity_json(self.max_temp),
            "min_temp": quantity_json(self.min_temp),
        }


class Environment(BaseModel):
    """Ambient physical environment."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    ambient_temp: Quantity = Q_(25.0, "degC")
    pressure: Quantity = Q_(1.0, "atm")

    @field_validator("ambient_temp")
    @classmethod
    def _validate_ambient_temp(cls, value: Quantity) -> Quantity:
        return require_temperature(value)

    @field_validator("pressure")
    @classmethod
    def _validate_pressure(cls, value: Quantity) -> Quantity:
        quantity = require_quantity(value)
        if not quantity.check("[mass] / [length] / [time] ** 2"):
            raise TypeError("Pressure must have pressure units.")
        return quantity
