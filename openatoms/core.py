"""Core physical primitives used by the OpenAtoms compiler."""

from enum import Enum
from typing import List

class Phase(Enum):
    """Enumerates supported physical phases for matter."""

    SOLID = "solid"
    LIQUID = "liquid"
    GAS = "gas"
    PLASMA = "plasma"

class Matter:
    """Represents a physical substance in a container."""

    def __init__(self, name: str, phase: Phase, mass_g: float, volume_ml: float, temp_c: float = 20.0):
        """Create a matter object with basic physical properties."""
        self.name = name
        self.phase = phase
        self.mass_g = mass_g
        self.volume_ml = volume_ml
        self.temp_c = temp_c
        
    def __repr__(self):
        return f"<Matter: {self.name} | {self.phase.value} | {self.volume_ml}mL | {self.temp_c}°C>"

class Container:
    """Represents a bounded vessel that can hold matter."""

    def __init__(self, name: str, max_volume_ml: float, max_temp_c: float, min_temp_c: float = -80.0):
        """Initialize a container with capacity and thermal limits."""
        self.name = name
        self.max_volume_ml = max_volume_ml
        self.max_temp_c = max_temp_c
        self.min_temp_c = min_temp_c
        self.contents: List[Matter] = []
        
    @property
    def current_volume(self) -> float:
        """Return the total volume currently present in the container."""
        return sum(m.volume_ml for m in self.contents)
        
    def __repr__(self):
        return f"<Container: {self.name} | Vol: {self.current_volume}/{self.max_volume_ml}mL | Items: {len(self.contents)}>"

class Environment:
    """Represents ambient environmental context for protocol execution."""

    def __init__(self, ambient_temp_c: float = 20.0, pressure_atm: float = 1.0):
        """Initialize environmental conditions."""
        self.ambient_temp_c = ambient_temp_c
        self.pressure_atm = pressure_atm
