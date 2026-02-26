"""Core physical primitives used by the OpenAtoms compiler."""

from enum import Enum
from typing import Dict, List, Optional, Set, Union

from .ids import stable_id
from .units import Quantity, as_temp_c, as_volume_ml


class Phase(Enum):
    """Enumerates supported physical phases for matter."""

    SOLID = "solid"
    LIQUID = "liquid"
    GAS = "gas"
    PLASMA = "plasma"


class Matter:
    """Represents a physical substance in a container."""

    def __init__(
        self,
        name: str,
        phase: Phase,
        mass_g: float,
        volume_ml: Union[float, Quantity],
        temp_c: Union[float, Quantity] = 20.0,
        *,
        matter_id: Optional[str] = None,
        hazard_class: str = "none",
    ):
        """Create a matter object with basic physical properties."""
        self.name = name
        self.phase = phase
        self.id = matter_id or stable_id("matter", name)
        self.mass_g = mass_g
        self.volume_ml = as_volume_ml(volume_ml)
        self.temp_c = as_temp_c(temp_c)
        self.hazard_class = hazard_class.strip().lower()

    def __repr__(self):
        return f"<Matter: {self.name} | {self.phase.value} | {self.volume_ml}mL | {self.temp_c}°C>"

    def to_reference(self) -> Dict[str, object]:
        """Serialize stable matter reference metadata."""
        return {
            "id": self.id,
            "name": self.name,
            "phase": self.phase.value,
            "mass_g": self.mass_g,
            "volume_ml": self.volume_ml,
            "temp_c": self.temp_c,
            "hazard_class": self.hazard_class,
        }


class Container:
    """Represents a bounded vessel that can hold matter."""

    def __init__(
        self,
        name: str,
        max_volume_ml: Union[float, Quantity],
        max_temp_c: Union[float, Quantity],
        min_temp_c: Union[float, Quantity] = -80.0,
        *,
        container_id: Optional[str] = None,
        incompatible_hazards: Optional[Set[str]] = None,
    ):
        """Initialize a container with capacity and thermal limits."""
        self.name = name
        self.id = container_id or stable_id("container", name)
        self.max_volume_ml = as_volume_ml(max_volume_ml)
        self.max_temp_c = as_temp_c(max_temp_c)
        self.min_temp_c = as_temp_c(min_temp_c)
        self.contents: List[Matter] = []
        self.incompatible_hazards = {
            hazard.strip().lower() for hazard in (incompatible_hazards or set())
        }

    @property
    def current_volume(self) -> float:
        """Return the total volume currently present in the container."""
        return sum(m.volume_ml for m in self.contents)

    @property
    def hazard_classes(self) -> Set[str]:
        """Return all hazard classes currently present in this container."""
        hazards = {matter.hazard_class for matter in self.contents if matter.hazard_class}
        hazards.discard("none")
        return hazards

    def __repr__(self):
        return (
            f"<Container: {self.name} | Vol: {self.current_volume}/{self.max_volume_ml}mL"
            f" | Items: {len(self.contents)}>"
        )

    def to_reference(self) -> Dict[str, object]:
        """Serialize stable container reference metadata."""
        return {
            "id": self.id,
            "name": self.name,
            "max_volume_ml": self.max_volume_ml,
            "max_temp_c": self.max_temp_c,
            "min_temp_c": self.min_temp_c,
            "incompatible_hazards": sorted(self.incompatible_hazards),
        }


class Environment:
    """Represents ambient environmental context for protocol execution."""

    def __init__(self, ambient_temp_c: float = 20.0, pressure_atm: float = 1.0):
        """Initialize environmental conditions."""
        self.ambient_temp_c = ambient_temp_c
        self.pressure_atm = pressure_atm
