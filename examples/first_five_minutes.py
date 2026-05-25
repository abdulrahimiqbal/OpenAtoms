"""No-API first-click trace: one accepted protocol and one rejected proposal."""

from __future__ import annotations

import json

from openatoms.actions import Move
from openatoms.core import Container, Matter, Phase
from openatoms.dag import ProtocolGraph
from openatoms.errors import PhysicsError
from openatoms.units import Q_


def water_container(container_id: str, volume_ul: float, capacity_ul: float) -> Container:
    container = Container(
        id=container_id,
        label=container_id,
        max_volume=Q_(capacity_ul, "microliter"),
        max_temp=Q_(100, "degC"),
        min_temp=Q_(0, "degC"),
    )
    if volume_ul:
        container.contents.append(
            Matter(
                name="H2O",
                phase=Phase.LIQUID,
                mass=Q_(volume_ul, "milligram"),
                volume=Q_(volume_ul, "microliter"),
            )
        )
    return container


def run_protocol(name: str, source_ul: float, dest_ul: float, move_ul: float) -> dict[str, object]:
    source = water_container("source", source_ul, 500)
    dest = water_container("dest", dest_ul, 150)
    graph = ProtocolGraph(name)
    graph.add_step(Move(source, dest, Q_(move_ul, "microliter")))
    graph.dry_run()
    return graph.to_payload()


def main() -> None:
    accepted = run_protocol("accepted_transfer", source_ul=200, dest_ul=25, move_ul=100)
    print("ACCEPTED")
    print(
        json.dumps(
            {
                "dry_run_passed": accepted["dry_run_passed"],
                "ir_hash": accepted["provenance"]["ir_hash"],
                "steps": len(accepted["steps"]),
            },
            indent=2,
            sort_keys=True,
        )
    )

    print("REJECTED")
    try:
        run_protocol("overflow_transfer", source_ul=200, dest_ul=100, move_ul=100)
    except PhysicsError as exc:
        print(exc.to_agent_payload())


if __name__ == "__main__":
    main()
