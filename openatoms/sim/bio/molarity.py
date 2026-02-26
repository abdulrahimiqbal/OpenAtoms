"""Molarity tracking for bio-kinetic transfer protocols.

Example:
    >>> from openatoms.core import Container
    >>> from openatoms.units import Q_
    >>> a = Container(id="a", label="A1", max_volume=Q_(300, "microliter"), max_temp=Q_(70, "degC"), min_temp=Q_(4, "degC"))
    >>> b = Container(id="b", label="A2", max_volume=Q_(300, "microliter"), max_temp=Q_(70, "degC"), min_temp=Q_(4, "degC"))
    >>> tracker = MolarityTracker()
    >>> tracker.set_molarity(a, "NaCl", Q_(0.1, "mole / liter"))
    >>> tracker.set_molarity(b, "NaCl", Q_(0.0, "mole / liter"))
    >>> tracker.transfer(a, b, Q_(100, "microliter"), source_volume=Q_(200, "microliter"), destination_volume=Q_(100, "microliter"))
    >>> round(tracker.get_molarity(b, "NaCl").to("mole/liter").magnitude, 3)
    0.05
"""

from __future__ import annotations

from typing import Dict

from ...core import Container
from ...errors import MassBalanceViolationError
from ...units import Quantity, Q_, require_quantity, require_volume


class MolarityTracker:
    """Track solute concentrations and enforce physical plausibility."""

    SOLUBILITY_LIMITS: Dict[str, Quantity] = {
        "NaCl": Q_(360.0, "gram / liter"),
        "KCl": Q_(340.0, "gram / liter"),
        "Glucose": Q_(909.0, "gram / liter"),
    }

    MOLECULAR_WEIGHTS: Dict[str, Quantity] = {
        "NaCl": Q_(58.44, "gram / mole"),
        "KCl": Q_(74.55, "gram / mole"),
        "Glucose": Q_(180.156, "gram / mole"),
    }

    def __init__(self) -> None:
        self._molarity: dict[str, dict[str, Quantity]] = {}

    def set_molarity(self, container: Container, solute: str, concentration: Quantity) -> None:
        """Set initial solute concentration for a container."""
        quantity = require_quantity(concentration)
        if not quantity.check("[substance] / [length] ** 3"):
            raise TypeError("Molarity must have amount/volume units.")
        self._molarity.setdefault(container.id, {})[solute] = quantity.to("mole / liter")

    def get_molarity(self, container: Container, solute: str) -> Quantity:
        """Return current solute concentration for a container."""
        return self._molarity.get(container.id, {}).get(solute, Q_(0.0, "mole / liter"))

    def _assert_physical(self, solute: str, concentration: Quantity) -> None:
        if concentration.to("mole / liter").magnitude < 0:
            raise MassBalanceViolationError(
                description="Negative concentration encountered in molarity tracking.",
                actual_value=f"{concentration:~P}",
                limit_value=">= 0 mole/liter",
                remediation_hint="Adjust transfer matrix to avoid negative concentration states.",
            )

        if solute in self.SOLUBILITY_LIMITS and solute in self.MOLECULAR_WEIGHTS:
            mass_concentration = concentration.to("mole / liter") * self.MOLECULAR_WEIGHTS[solute]
            if mass_concentration.to("gram / liter") > self.SOLUBILITY_LIMITS[solute].to("gram / liter"):
                raise MassBalanceViolationError(
                    description=f"Concentration exceeds {solute} solubility limit.",
                    actual_value=f"{mass_concentration.to('gram/liter'):~P}",
                    limit_value=f"{self.SOLUBILITY_LIMITS[solute].to('gram/liter'):~P}",
                    remediation_hint=(
                        f"Reduce {solute} concentration or increase solvent volume to stay below "
                        f"{self.SOLUBILITY_LIMITS[solute].to('gram/liter'):~P}."
                    ),
                )

    def transfer(
        self,
        source: Container,
        destination: Container,
        transfer_volume: Quantity,
        *,
        source_volume: Quantity,
        destination_volume: Quantity,
    ) -> None:
        """Apply molarity update using C_final = (C1*V1 + C2*V2)/(V1+V2)."""
        v_transfer = require_volume(transfer_volume).to("liter")
        v_source = require_volume(source_volume).to("liter")
        v_destination = require_volume(destination_volume).to("liter")

        if v_transfer.magnitude <= 0:
            return

        source_state = self._molarity.get(source.id, {})
        destination_state = self._molarity.setdefault(destination.id, {})

        for solute, source_conc in source_state.items():
            c1 = source_conc.to("mole / liter")
            c2 = destination_state.get(solute, Q_(0.0, "mole / liter")).to("mole / liter")

            # Source remains ideally well-mixed and concentration stays constant after withdrawal.
            destination_total_volume = v_destination + v_transfer
            if destination_total_volume.magnitude <= 0:
                continue

            c_final = (c1 * v_transfer + c2 * v_destination) / destination_total_volume
            self._assert_physical(solute, c_final)
            destination_state[solute] = c_final.to("mole / liter")

        # Ensure destination-only solutes remain unchanged when source lacks them.
        for solute, concentration in list(destination_state.items()):
            self._assert_physical(solute, concentration)
