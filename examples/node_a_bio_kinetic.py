"""Node A demo: bio-kinetic pipetting simulation with self-correction."""

from __future__ import annotations

import json

from openatoms.actions import Move
from openatoms.core import Container, Matter, Phase
from openatoms.dag import ProtocolGraph
from openatoms.errors import PhysicsError
from openatoms.sim.bio.molarity import MolarityTracker
from openatoms.sim.registry.opentrons_sim import OT2Simulator
from openatoms.units import Q_


def _well(well_id: str) -> Container:
    return Container(
        id=well_id,
        label=well_id,
        max_volume=Q_(300, "microliter"),
        max_temp=Q_(60, "degC"),
        min_temp=Q_(4, "degC"),
    )


def _build_invalid_graph() -> tuple[ProtocolGraph, dict[str, Container], MolarityTracker]:
    a1, a2, a3, a4 = _well("A1"), _well("A2"), _well("A3"), _well("A4")

    a1.contents.append(
        Matter(
            name="NaCl_solution",
            phase=Phase.LIQUID,
            mass=Q_(150, "milligram"),
            volume=Q_(150, "microliter"),
            molecular_weight=Q_(58.44, "gram / mole"),
        )
    )
    for well in (a2, a3, a4):
        well.contents.append(
            Matter(
                name="water",
                phase=Phase.LIQUID,
                mass=Q_(75, "milligram"),
                volume=Q_(75, "microliter"),
            )
        )

    tracker = MolarityTracker()
    tracker.set_molarity(a1, "NaCl", Q_(0.1, "mole / liter"))
    tracker.set_molarity(a2, "NaCl", Q_(0.0, "mole / liter"))
    tracker.set_molarity(a3, "NaCl", Q_(0.0, "mole / liter"))
    tracker.set_molarity(a4, "NaCl", Q_(0.0, "mole / liter"))

    graph = ProtocolGraph("node_a_invalid")
    graph.add_step(Move(a1, a2, Q_(75, "microliter")))
    graph.add_step(Move(a2, a3, Q_(75, "microliter")))
    graph.add_step(Move(a3, a4, Q_(75, "microliter")))
    graph.add_step(Move(a4, a1, Q_(200, "microliter")))

    tracker.transfer(
        a1,
        a2,
        Q_(75, "microliter"),
        source_volume=Q_(150, "microliter"),
        destination_volume=Q_(75, "microliter"),
    )
    tracker.transfer(
        a2,
        a3,
        Q_(75, "microliter"),
        source_volume=Q_(150, "microliter"),
        destination_volume=Q_(75, "microliter"),
    )
    tracker.transfer(
        a3,
        a4,
        Q_(75, "microliter"),
        source_volume=Q_(150, "microliter"),
        destination_volume=Q_(75, "microliter"),
    )

    return graph, {"A1": a1, "A2": a2, "A3": a3, "A4": a4}, tracker


def _build_corrected_graph(wells: dict[str, Container]) -> ProtocolGraph:
    graph = ProtocolGraph("node_a_corrected")
    graph.add_step(Move(wells["A1"], wells["A2"], Q_(75, "microliter")))
    graph.add_step(Move(wells["A2"], wells["A3"], Q_(75, "microliter")))
    graph.add_step(Move(wells["A3"], wells["A4"], Q_(75, "microliter")))
    graph.add_step(Move(wells["A4"], wells["A1"], Q_(100, "microliter")))
    return graph


def main() -> None:
    invalid_graph, wells, tracker = _build_invalid_graph()
    simulator = OT2Simulator()

    observation = simulator.run(invalid_graph)
    print("StateObservation JSON:")
    print(observation.to_json())

    if observation.errors:
        error = observation.errors[0]
        print("\nCaught error remediation_hint:")
        print(error.remediation_hint)

    print("\nSerial dilution molarity (NaCl):")
    for well in ("A1", "A2", "A3", "A4"):
        concentration = tracker.get_molarity(wells[well], "NaCl").to("millimole / liter")
        print(f"{well}: {concentration.magnitude:.3f} mM")

    corrected_graph = _build_corrected_graph(wells)
    corrected_graph.dry_run()
    corrected_observation = simulator.run(corrected_graph)

    print("\nCorrected protocol passes dry_run and simulation:")
    print(json.dumps({"dry_run_passed": True, "simulation_success": corrected_observation.success}, indent=2))


if __name__ == "__main__":
    main()
