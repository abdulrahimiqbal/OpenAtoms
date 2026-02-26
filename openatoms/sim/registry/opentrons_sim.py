"""Bio-kinetic simulation wrapper for Opentrons-compatible protocols.

Example:
    >>> from openatoms.actions import Move
    >>> from openatoms.core import Container, Matter, Phase
    >>> from openatoms.dag import ProtocolGraph
    >>> from openatoms.units import Q_
    >>> a = Container(id="A1", label="A1", max_volume=Q_(300, "microliter"), max_temp=Q_(70, "degC"), min_temp=Q_(4, "degC"))
    >>> b = Container(id="A2", label="A2", max_volume=Q_(300, "microliter"), max_temp=Q_(70, "degC"), min_temp=Q_(4, "degC"))
    >>> a.contents.append(Matter(name="water", phase=Phase.LIQUID, mass=Q_(100, "milligram"), volume=Q_(100, "microliter")))
    >>> g = ProtocolGraph("ot2")
    >>> _ = g.add_step(Move(a, b, Q_(50, "microliter")))
    >>> obs = OT2Simulator().run(g)
    >>> obs.success
    True
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from ...actions import Move
from ...core import Container
from ...dag import ProtocolGraph
from ...errors import (
    OrderingConstraintError,
    PhysicsError,
    SimulationDependencyError,
    VolumeOverflowError,
)
from ..types import StateObservation

SLOT_WIDTH_MM = 127.76
SLOT_HEIGHT_MM = 85.48
SLOT_COORDS = {
    "1": (0.0, 0.0),
    "2": (SLOT_WIDTH_MM, 0.0),
    "3": (2 * SLOT_WIDTH_MM, 0.0),
    "4": (0.0, SLOT_HEIGHT_MM),
    "5": (SLOT_WIDTH_MM, SLOT_HEIGHT_MM),
    "6": (2 * SLOT_WIDTH_MM, SLOT_HEIGHT_MM),
    "7": (0.0, 2 * SLOT_HEIGHT_MM),
    "8": (SLOT_WIDTH_MM, 2 * SLOT_HEIGHT_MM),
    "9": (2 * SLOT_WIDTH_MM, 2 * SLOT_HEIGHT_MM),
}


class OT2Simulator:
    """Run ProtocolGraph logic through Opentrons-compatible simulation checks."""

    def compile_to_otprotocol(self, graph: ProtocolGraph) -> str:
        """Compile ProtocolGraph into executable Opentrons Python protocol text."""
        lines = [
            "from opentrons import protocol_api",
            "",
            "metadata = {'apiLevel': '2.15', 'protocolName': 'OpenAtoms OT2 Simulation'}",
            "",
            "def run(protocol: protocol_api.ProtocolContext):",
            "    plate = protocol.load_labware('corning_96_wellplate_360ul_flat', '1')",
            "    pipette = protocol.load_instrument('p300_single', 'right')",
        ]

        step = 0
        for action in graph.sequence:
            if not isinstance(action, Move):
                continue
            step += 1
            volume_ul = action.amount.to("microliter").magnitude
            src = action.source.label
            dst = action.destination.label
            lines.append(
                f"    pipette.transfer({volume_ul:.6f}, plate.wells_by_name()['{src}'], plate.wells_by_name()['{dst}'])"
            )
            lines.append(f"    # step {step}: {src} -> {dst} ({volume_ul:.3f} uL)")

        return "\n".join(lines)

    def run(self, graph: ProtocolGraph) -> StateObservation:
        """Execute protocol simulation and map errors to PhysicsError taxonomy."""
        script = self.compile_to_otprotocol(graph)
        errors: list[PhysicsError] = []
        dispensed_per_well: dict[str, float] = {}
        source_remaining: dict[str, float] = {}
        tip_count = 0

        containers: list[Container] = graph._collect_containers()  # noqa: SLF001
        for container in containers:
            source_remaining[container.label] = container.current_volume.to("microliter").magnitude

        for action in graph.sequence:
            if not isinstance(action, Move):
                continue

            transfer_ul = action.amount.to("microliter").magnitude
            source_label = action.source.label
            destination_label = action.destination.label

            available_ul = source_remaining.get(source_label, 0.0)
            if transfer_ul > available_ul + 1e-9:
                errors.append(
                    VolumeOverflowError(
                        description=(
                            f"Aspirate volume exceeds available volume in well {source_label}."
                        ),
                        actual_value=f"{transfer_ul:.3f} microliter",
                        limit_value=f"{available_ul:.3f} microliter",
                        remediation_hint=(
                            f"Reduce aspirate volume from {transfer_ul:.3f} microliter to "
                            f"{available_ul:.3f} microliter or below in {source_label}."
                        ),
                    )
                )
                continue

            source_remaining[source_label] = available_ul - transfer_ul
            source_remaining[destination_label] = (
                source_remaining.get(destination_label, 0.0) + transfer_ul
            )
            dispensed_per_well[destination_label] = (
                dispensed_per_well.get(destination_label, 0.0) + transfer_ul
            )
            tip_count += 1

        # Optional direct call to opentrons.simulate for additional runtime compatibility checks.
        try:
            from opentrons import simulate  # type: ignore

            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as handle:
                handle.write(script)
                path = Path(handle.name)
            with path.open("rb") as protocol_file:
                simulate.simulate(protocol_file)
            path.unlink(missing_ok=True)
        except ImportError:
            # Graceful fallback is allowed; analytical checks above remain active.
            pass
        except Exception as exc:  # pragma: no cover - depends on opentrons internals
            errors.append(
                OrderingConstraintError(
                    description="Opentrons simulator raised an execution exception.",
                    actual_value=str(exc),
                    limit_value="successful opentrons.simulate execution",
                    remediation_hint=(
                        "Adjust deck layout, labware mapping, and transfer commands to produce "
                        "a valid Opentrons simulation run."
                    ),
                )
            )

        return StateObservation(
            success=len(errors) == 0,
            errors=errors,
            timing_estimate_s=tip_count * 2.0,
            tip_usage_count=tip_count,
            volume_dispensed_per_well=dispensed_per_well,
            metadata={"node": "bio_kinetic", "compiled_protocol": script},
        )

    def check_deck_collisions(self, labware_layout: dict[str, Any]) -> list[PhysicsError]:
        """Detect deck collisions using OT-2 slot footprints and optional custom bounds."""
        errors: list[PhysicsError] = []

        # Duplicate slot assignments are immediate collisions.
        occupied_slots: dict[str, str] = {}
        for name, item in labware_layout.items():
            slot = str(item.get("slot", "")).strip()
            if slot in occupied_slots:
                errors.append(
                    OrderingConstraintError(
                        description="Two labware items occupy the same deck slot.",
                        actual_value={"slot": slot, "items": [occupied_slots[slot], name]},
                        limit_value="one labware per slot",
                        remediation_hint=(
                            f"Move either {occupied_slots[slot]} or {name} to a unique OT-2 slot."
                        ),
                    )
                )
            occupied_slots[slot] = name

        # If custom x/y/width/height are provided, run AABB overlap checks.
        boxes: list[tuple[str, float, float, float, float]] = []
        for name, item in labware_layout.items():
            if {"x_mm", "y_mm", "width_mm", "height_mm"}.issubset(item.keys()):
                x0 = float(item["x_mm"])
                y0 = float(item["y_mm"])
                w = float(item["width_mm"])
                h = float(item["height_mm"])
            else:
                slot = str(item.get("slot", ""))
                if slot not in SLOT_COORDS:
                    errors.append(
                        OrderingConstraintError(
                            description="Invalid OT-2 slot identifier.",
                            actual_value=slot,
                            limit_value="1..9",
                            remediation_hint="Assign labware to slots 1 through 9 only.",
                        )
                    )
                    continue
                x0, y0 = SLOT_COORDS[slot]
                w, h = SLOT_WIDTH_MM, SLOT_HEIGHT_MM

            boxes.append((name, x0, y0, x0 + w, y0 + h))

        for index, (name_a, ax0, ay0, ax1, ay1) in enumerate(boxes):
            for name_b, bx0, by0, bx1, by1 in boxes[index + 1 :]:
                overlap_x = ax0 < bx1 and bx0 < ax1
                overlap_y = ay0 < by1 and by0 < ay1
                if overlap_x and overlap_y:
                    errors.append(
                        OrderingConstraintError(
                            description="Deck footprint overlap detected.",
                            actual_value={"labware_a": name_a, "labware_b": name_b},
                            limit_value="non-overlapping OT-2 deck footprints",
                            remediation_hint=(
                                f"Reposition {name_a} and {name_b} so their footprints do not overlap "
                                "on the OT-2 deck."
                            ),
                        )
                    )

        return errors


class OpentronsSimValidator:
    """Backward-compatible validator wrapper around OT2Simulator."""

    def validate_protocol(self, protocol_path: str) -> dict[str, Any]:
        """Validate a standalone protocol script path.

        Returns:
            dict with `state_observation_json`, `error`, and `run_log` keys.
        """
        path = Path(protocol_path)
        if not path.exists():
            error = OrderingConstraintError(
                description="Protocol file not found.",
                actual_value=protocol_path,
                limit_value="existing path",
                remediation_hint="Provide a valid protocol script path.",
            )
            observation = StateObservation(success=False, errors=[error], metadata={"path": protocol_path})
            return {"state_observation_json": observation.to_json(), "error": error, "run_log": None}

        try:
            from opentrons import simulate  # type: ignore

            with path.open("rb") as protocol_file:
                run_log = simulate.simulate(protocol_file)
            observation = StateObservation(success=True, metadata={"path": protocol_path})
            return {
                "state_observation_json": observation.to_json(),
                "error": None,
                "run_log": run_log,
            }
        except ImportError:
            error = SimulationDependencyError("opentrons", "Package not installed")
            observation = StateObservation(success=False, errors=[error], metadata={"path": protocol_path})
            return {"state_observation_json": observation.to_json(), "error": error, "run_log": None}
        except Exception as exc:  # pragma: no cover - external simulator branch
            error = OrderingConstraintError(
                description="Opentrons simulator execution failed.",
                actual_value=str(exc),
                limit_value="valid protocol execution",
                remediation_hint="Fix protocol syntax/deck mapping and rerun simulation.",
            )
            observation = StateObservation(success=False, errors=[error], metadata={"path": protocol_path})
            return {"state_observation_json": observation.to_json(), "error": error, "run_log": None}
