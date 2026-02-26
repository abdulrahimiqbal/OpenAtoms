"""Hardware adapters for OpenAtoms protocol execution."""

from .arduino_cloud import ArduinoCloudAdapter
from .bambu import BambuAdapter
from .base import BaseAdapter
from .home_assistant import HomeAssistantAdapter
from .opentrons import OpentronsAdapter
from .viam import ViamAdapter

# Legacy alias for earlier examples.
SmartBaristaAdapter = BambuAdapter

__all__ = [
    "BaseAdapter",
    "OpentronsAdapter",
    "ViamAdapter",
    "BambuAdapter",
    "HomeAssistantAdapter",
    "ArduinoCloudAdapter",
    "SmartBaristaAdapter",
]
