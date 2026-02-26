"""Unit-safe quantity utilities built on Pint.

Example:
    >>> from openatoms.units import Q_, require_volume
    >>> require_volume(Q_(5, "milliliter")).to("liter").magnitude
    0.005
"""

from __future__ import annotations

from typing import Any

from pint import UnitRegistry

ureg = UnitRegistry(autoconvert_offset_to_baseunit=True)
Q_ = ureg.Quantity
Quantity = type(Q_(1, "meter"))


def require_quantity(value: Any) -> Quantity:
    """Return a pint quantity or raise.

    Example:
        >>> from openatoms.units import Q_, require_quantity
        >>> require_quantity(Q_(1, "gram")).to("milligram").magnitude
        1000.0
    """
    if isinstance(value, Quantity):
        return value
    raise TypeError("Physical quantities must be Pint Quantity objects with explicit units.")


def require_volume(value: Any) -> Quantity:
    """Validate that `value` is a volume quantity.

    Example:
        >>> from openatoms.units import Q_, require_volume
        >>> require_volume(Q_(1, "liter")).to("milliliter").magnitude
        1000.0
    """
    quantity = require_quantity(value)
    if not quantity.check("[length] ** 3"):
        raise TypeError(f"Expected volume quantity, received '{quantity.units}'.")
    return quantity


def require_mass(value: Any) -> Quantity:
    """Validate that `value` is a mass quantity.

    Example:
        >>> from openatoms.units import Q_, require_mass
        >>> require_mass(Q_(2, "gram")).to("milligram").magnitude
        2000.0
    """
    quantity = require_quantity(value)
    if not quantity.check("[mass]"):
        raise TypeError(f"Expected mass quantity, received '{quantity.units}'.")
    return quantity


def require_temperature(value: Any) -> Quantity:
    """Validate that `value` is a temperature quantity.

    Example:
        >>> from openatoms.units import Q_, require_temperature
        >>> round(require_temperature(Q_(300, "kelvin")).to("degC").magnitude, 2)
        26.85
    """
    quantity = require_quantity(value)
    if not quantity.check("[temperature]"):
        raise TypeError(f"Expected temperature quantity, received '{quantity.units}'.")
    return quantity


def require_time(value: Any) -> Quantity:
    """Validate that `value` is a time quantity.

    Example:
        >>> from openatoms.units import Q_, require_time
        >>> require_time(Q_(2, "minute")).to("second").magnitude
        120
    """
    quantity = require_quantity(value)
    if not quantity.check("[time]"):
        raise TypeError(f"Expected time quantity, received '{quantity.units}'.")
    return quantity


def quantity_json(value: Quantity) -> dict[str, str | float]:
    """Encode a pint quantity as deterministic JSON metadata.

    Example:
        >>> from openatoms.units import Q_, quantity_json
        >>> quantity_json(Q_(1.5, "gram"))["unit"]
        'g'
    """
    quantity = require_quantity(value)
    return {
        "value": float(quantity.magnitude),
        "unit": f"{quantity.units:~}",
    }
