from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from openatoms.actions import Move, Transform
from openatoms.core import Container, Matter, Phase
from openatoms.dag import ProtocolGraph
from openatoms.errors import PhysicsError
from openatoms.units import Q_


@dataclass(frozen=True)
class EvaluationOutcome:
    violating: bool
    error_code: str | None
    constraint_type: str | None
    message: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _build_graph(protocol: dict[str, Any]) -> ProtocolGraph:
    source = Container(
        id=f"{protocol['protocol_id']}_src",
        label="SRC",
        max_volume=Q_(max(protocol["source_volume_ul"], 1), "microliter"),
        max_temp=Q_(120, "degC"),
        min_temp=Q_(0, "degC"),
    )
    destination = Container(
        id=f"{protocol['protocol_id']}_dst",
        label="DST",
        max_volume=Q_(max(protocol["destination_capacity_ul"], 1), "microliter"),
        max_temp=Q_(protocol["max_temp_c"], "degC"),
        min_temp=Q_(0, "degC"),
    )
    source.contents.append(
        Matter(
            name="water",
            phase=Phase.LIQUID,
            mass=Q_(protocol["source_volume_ul"], "milligram"),
            volume=Q_(protocol["source_volume_ul"], "microliter"),
        )
    )
    if protocol["destination_start_ul"] > 0:
        destination.contents.append(
            Matter(
                name="water",
                phase=Phase.LIQUID,
                mass=Q_(protocol["destination_start_ul"], "milligram"),
                volume=Q_(protocol["destination_start_ul"], "microliter"),
            )
        )

    graph = ProtocolGraph(protocol["protocol_id"])
    graph.add_step(Move(source, destination, Q_(protocol["transfer_ul"], "microliter")))
    graph.add_step(
        Transform(
            destination,
            "temperature",
            Q_(protocol["target_temp_c"], "degC"),
            Q_(30, "second"),
        )
    )
    return graph


def evaluate_protocol(protocol: dict[str, Any]) -> EvaluationOutcome:
    """Return deterministic violation outcome for a single protocol."""
    try:
        graph = _build_graph(protocol)
        graph.dry_run()
    except PhysicsError as exc:
        return EvaluationOutcome(
            violating=True,
            error_code=exc.error_code,
            constraint_type=exc.constraint_type,
            message=exc.description,
        )

    return EvaluationOutcome(
        violating=False,
        error_code=None,
        constraint_type=None,
        message=None,
    )


def apply_validator_repairs(protocol: dict[str, Any]) -> dict[str, Any]:
    """Repair proposal deterministically using simple invariant-aware rules."""
    repaired = dict(protocol)

    source = max(int(repaired["source_volume_ul"]), 1)
    capacity = max(int(repaired["destination_capacity_ul"]), 1)
    destination_start = int(repaired["destination_start_ul"])
    destination_start = min(max(destination_start, 0), max(capacity - 2, 0))
    available_room = max(capacity - destination_start - 1, 1)

    repaired["source_volume_ul"] = source
    repaired["destination_capacity_ul"] = capacity
    repaired["destination_start_ul"] = destination_start
    repaired["transfer_ul"] = min(max(int(repaired["transfer_ul"]), 1), source, available_room)
    repaired["target_temp_c"] = max(
        0,
        min(
            int(repaired["target_temp_c"]),
            int(repaired["max_temp_c"]),
        ),
    )
    return repaired


def intent_proxy_preserved(original: dict[str, Any], repaired: dict[str, Any]) -> bool:
    """Heuristic intent proxy for benchmark correction scoring."""
    if original.get("protocol_id") != repaired.get("protocol_id"):
        return False

    transfer_original = int(original["transfer_ul"])
    transfer_repaired = int(repaired["transfer_ul"])
    transfer_tolerance = max(5, int(round(0.10 * max(abs(transfer_original), 1))))

    temp_original = int(original["target_temp_c"])
    temp_repaired = int(repaired["target_temp_c"])
    temp_tolerance = 10

    return (
        abs(transfer_repaired - transfer_original) <= transfer_tolerance
        and abs(temp_repaired - temp_original) <= temp_tolerance
    )
