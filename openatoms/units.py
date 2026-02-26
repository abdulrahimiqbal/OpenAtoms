"""Typed quantity primitives and deterministic unit conversions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple, Union

_VOLUME_TO_ML: Dict[str, float] = {
    "ml": 1.0,
    "l": 1000.0,
}

_TEMP_TO_C: Dict[str, Tuple[float, float]] = {
    # celsius = (value * scale) + offset
    "c": (1.0, 0.0),
    "k": (1.0, -273.15),
}

_TIME_TO_S: Dict[str, float] = {
    "s": 1.0,
    "min": 60.0,
    "h": 3600.0,
}


@dataclass(frozen=True)
class Quantity:
    """Represents a typed quantity that supports deterministic conversions."""

    value: float
    unit: str
    dimension: str

    def to(self, target_unit: str) -> "Quantity":
        """Convert this quantity into another unit with the same dimension."""
        dim = self.dimension.strip().lower()
        source_unit = self.unit.strip().lower()
        target = target_unit.strip().lower()

        if dim == "volume":
            if source_unit not in _VOLUME_TO_ML or target not in _VOLUME_TO_ML:
                raise ValueError(f"Unsupported volume conversion {source_unit} -> {target}.")
            ml = self.value * _VOLUME_TO_ML[source_unit]
            return Quantity(value=ml / _VOLUME_TO_ML[target], unit=target, dimension=self.dimension)

        if dim == "temperature":
            if source_unit not in _TEMP_TO_C or target not in _TEMP_TO_C:
                raise ValueError(f"Unsupported temperature conversion {source_unit} -> {target}.")
            scale, offset = _TEMP_TO_C[source_unit]
            celsius = (self.value * scale) + offset
            target_scale, target_offset = _TEMP_TO_C[target]
            target_value = (celsius - target_offset) / target_scale
            return Quantity(value=target_value, unit=target, dimension=self.dimension)

        if dim == "time":
            if source_unit not in _TIME_TO_S or target not in _TIME_TO_S:
                raise ValueError(f"Unsupported time conversion {source_unit} -> {target}.")
            seconds = self.value * _TIME_TO_S[source_unit]
            return Quantity(
                value=seconds / _TIME_TO_S[target],
                unit=target,
                dimension=self.dimension,
            )

        raise ValueError(f"Unsupported dimension '{self.dimension}'.")


def as_volume_ml(value: Union[float, Quantity]) -> float:
    """Convert raw value or typed volume quantity to milliliters."""
    if isinstance(value, Quantity):
        if value.dimension.strip().lower() != "volume":
            raise ValueError("Expected volume quantity.")
        return value.to("ml").value
    return float(value)


def as_temp_c(value: Union[float, Quantity]) -> float:
    """Convert raw value or typed temperature quantity to celsius."""
    if isinstance(value, Quantity):
        if value.dimension.strip().lower() != "temperature":
            raise ValueError("Expected temperature quantity.")
        return value.to("c").value
    return float(value)


def as_time_s(value: Union[float, Quantity]) -> float:
    """Convert raw value or typed time quantity to seconds."""
    if isinstance(value, Quantity):
        if value.dimension.strip().lower() != "time":
            raise ValueError("Expected time quantity.")
        return value.to("s").value
    return float(value)
