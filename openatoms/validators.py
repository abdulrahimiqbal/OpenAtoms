"""Physical invariants for OpenAtoms protocol validation.

Example:
    >>> from openatoms.core import Container
    >>> from openatoms.units import Q_
    >>> c = Container(id="c", label="C", max_volume=Q_(100, "milliliter"), max_temp=Q_(80, "degC"), min_temp=Q_(0, "degC"))
    >>> assert_volume_feasibility(c, Q_(5, "milliliter"))
"""

from __future__ import annotations

from copy import deepcopy
from typing import Optional

from .core import Container
from .errors import (
    MassBalanceViolationError,
    ThermalExcursionError,
    VolumeOverflowError,
)
from .units import Quantity, Q_, require_temperature, require_time, require_volume

FLASH_POINT_DB_C = {
    "67-56-1": Q_(11.0, "degC"),  # methanol
    "64-17-5": Q_(13.0, "degC"),  # ethanol
    "67-64-1": Q_(-20.0, "degC"),  # acetone
}


def _total_mass(containers: list[Container]) -> Quantity:
    total = Q_(0.0, "gram")
    for container in containers:
        for matter in container.contents:
            total += matter.mass.to("gram")
    return total


def assert_mass_conservation(before: list[Container], after: list[Container]) -> None:
    """Assert mass conservation across all containers.

    Parameters:
        before: Container state before an operation.
        after: Container state after an operation.

    Raises:
        MassBalanceViolationError: If total mass differs by more than 1e-9 g.

    Example:
        >>> from openatoms.core import Container, Matter, Phase
        >>> from openatoms.units import Q_
        >>> a = Container(id="a", label="A", max_volume=Q_(100, "milliliter"), max_temp=Q_(100, "degC"), min_temp=Q_(0, "degC"))
        >>> a.contents.append(Matter(name="H2O", phase=Phase.LIQUID, mass=Q_(10, "gram"), volume=Q_(10, "milliliter")))
        >>> assert_mass_conservation([a], [deepcopy(a)])
    """
    before_mass = _total_mass(before).to("gram")
    after_mass = _total_mass(after).to("gram")
    delta = abs((after_mass - before_mass).to("gram").magnitude)
    if delta > 1e-9:
        raise MassBalanceViolationError(
            description="Mass conservation invariant violated.",
            actual_value=f"{after_mass:~P}",
            limit_value=f"{before_mass:~P}",
            remediation_hint=(
                "Adjust transfer and reaction stoichiometry so total container mass "
                "is conserved within 1e-9 gram tolerance."
            ),
        )


def assert_volume_feasibility(container: Container, added_volume: Quantity) -> None:
    """Assert volume feasibility with thermal expansion.

    Parameters:
        container: Destination container.
        added_volume: Incoming volume.

    Raises:
        VolumeOverflowError: If projected thermally-expanded volume exceeds capacity.

    Example:
        >>> from openatoms.core import Container
        >>> from openatoms.units import Q_
        >>> c = Container(id="c", label="C", max_volume=Q_(10, "milliliter"), max_temp=Q_(100, "degC"), min_temp=Q_(0, "degC"))
        >>> assert_volume_feasibility(c, Q_(5, "milliliter"))
    """
    inc = require_volume(added_volume).to("milliliter")
    base_volume = container.current_volume.to("milliliter") + inc

    avg_temp = container.average_temperature.to("degC")
    alpha = max((matter.thermal_expansion_coefficient for matter in container.contents), default=2.14e-4)
    expansion_factor = 1.0
    if avg_temp.magnitude > 25.0:
        expansion_factor = 1.0 + alpha * (avg_temp.magnitude - 25.0)

    effective_volume = base_volume * expansion_factor
    limit = container.max_volume.to("milliliter")

    if effective_volume > limit:
        safe_added = (limit / expansion_factor) - container.current_volume.to("milliliter")
        safe_added = max(safe_added.magnitude, 0.0)
        raise VolumeOverflowError(
            description=(
                f"Projected expanded volume exceeds container capacity for {container.label}."
            ),
            actual_value=f"{effective_volume:~P}",
            limit_value=f"{limit:~P}",
            remediation_hint=(
                f"Reduce transfer volume from {inc:~P} to below {safe_added:.3f} milliliter "
                f"to maintain safe headspace in {container.label}."
            ),
        )


def assert_thermal_safety(
    container: Container,
    delta_temp: Quantity,
    duration: Optional[Quantity] = None,
) -> None:
    """Assert thermal safety constraints for a planned temperature change.

    Parameters:
        container: Target container.
        delta_temp: Planned temperature increase/decrease.
        duration: Optional ramp duration used for rate checking.

    Raises:
        ThermalExcursionError: If container bounds, flash point, or thermal ramp rates are unsafe.

    Example:
        >>> from openatoms.core import Container
        >>> from openatoms.units import Q_
        >>> c = Container(id="c", label="C", max_volume=Q_(100, "milliliter"), max_temp=Q_(120, "degC"), min_temp=Q_(-20, "degC"))
        >>> assert_thermal_safety(c, Q_(10, "delta_degC"))
    """
    delta = require_temperature(delta_temp).to("delta_degC")
    target_temp = container.average_temperature.to("degC") + delta

    if target_temp > container.max_temp.to("degC"):
        raise ThermalExcursionError(
            description=f"Target temperature exceeds max limit for {container.label}.",
            actual_value=f"{target_temp:~P}",
            limit_value=f"{container.max_temp:~P}",
            remediation_hint=(
                f"Reduce target temperature so {container.label} remains at or below "
                f"{container.max_temp:~P}."
            ),
        )

    if target_temp < container.min_temp.to("degC"):
        raise ThermalExcursionError(
            description=f"Target temperature is below min limit for {container.label}.",
            actual_value=f"{target_temp:~P}",
            limit_value=f"{container.min_temp:~P}",
            remediation_hint=(
                f"Increase target temperature so {container.label} remains at or above "
                f"{container.min_temp:~P}."
            ),
        )

    for matter in container.contents:
        flash = matter.flash_point
        if flash is None and matter.cas_number:
            flash = FLASH_POINT_DB_C.get(matter.cas_number)
        if flash is not None and target_temp >= flash.to("degC"):
            raise ThermalExcursionError(
                description=(
                    f"Target temperature crosses flash point for {matter.name} in "
                    f"{container.label}."
                ),
                actual_value=f"{target_temp:~P}",
                limit_value=f"{flash.to('degC'):~P}",
                remediation_hint=(
                    f"Keep {matter.name} below its flash point ({flash.to('degC'):~P}) "
                    "or choose inert atmosphere and explosion-rated hardware."
                ),
            )

    if duration is not None:
        ramp_time = require_time(duration).to("second")
        if ramp_time.magnitude <= 0:
            raise ThermalExcursionError(
                description="Temperature ramp duration must be positive.",
                actual_value=f"{ramp_time:~P}",
                limit_value="> 0 second",
                remediation_hint="Set a positive duration for the thermal ramp.",
            )
        rate = abs(delta.to("delta_degC").magnitude) / ramp_time.magnitude
        if rate > 10.0:
            raise ThermalExcursionError(
                description="Temperature ramp rate exceeds safe limit.",
                actual_value=f"{rate:.3f} delta_degC / second",
                limit_value="10 delta_degC / second",
                remediation_hint=(
                    "Increase heating/cooling duration to keep rate below 10 delta_degC "
                    "per second."
                ),
            )


def clone_containers(containers: list[Container]) -> list[Container]:
    """Deep-copy container states for invariant comparisons.

    Example:
        >>> from openatoms.core import Container
        >>> from openatoms.units import Q_
        >>> c = Container(id="c", label="C", max_volume=Q_(10, "milliliter"), max_temp=Q_(100, "degC"), min_temp=Q_(0, "degC"))
        >>> clone_containers([c])[0].label
        'C'
    """
    return [deepcopy(container) for container in containers]
