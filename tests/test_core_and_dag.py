from openatoms.actions import Move, Transform
from openatoms.core import Container, Matter, Phase
from openatoms.dag import ProtocolGraph
from openatoms.errors import MassBalanceViolationError, ThermalExcursionError, VolumeOverflowError
from openatoms.units import Q_


def _vessel(cid: str, label: str) -> Container:
    return Container(
        id=cid,
        label=label,
        max_volume=Q_(300, "microliter"),
        max_temp=Q_(80, "degC"),
        min_temp=Q_(0, "degC"),
    )


def test_protocol_graph_validates_move_and_transform() -> None:
    a = _vessel("a", "A1")
    b = _vessel("b", "A2")
    a.contents.append(
        Matter(
            name="water",
            phase=Phase.LIQUID,
            mass=Q_(200, "milligram"),
            volume=Q_(200, "microliter"),
        )
    )

    graph = ProtocolGraph("core_dag")
    graph.add_step(Move(a, b, Q_(100, "microliter")))
    graph.add_step(
        Transform(
            target=b,
            parameter="temperature",
            target_value=Q_(60, "degC"),
            duration=Q_(30, "second"),
        )
    )

    assert graph.dry_run() is True
    exported = graph.export_json()
    assert '"ir_version": "1.2.0"' in exported


def test_volume_overflow_is_caught() -> None:
    a = _vessel("a", "A1")
    b = _vessel("b", "A2")
    a.contents.append(
        Matter(name="water", phase=Phase.LIQUID, mass=Q_(250, "milligram"), volume=Q_(250, "microliter"))
    )

    graph = ProtocolGraph("overflow")
    graph.add_step(Move(a, b, Q_(400, "microliter")))

    try:
        graph.dry_run()
    except (VolumeOverflowError, MassBalanceViolationError):
        return
    raise AssertionError("Expected VolumeOverflowError")


def test_thermal_excursion_is_caught() -> None:
    c = _vessel("c", "A3")
    c.contents.append(
        Matter(name="ethanol", phase=Phase.LIQUID, mass=Q_(100, "milligram"), volume=Q_(100, "microliter"), cas_number="64-17-5")
    )

    graph = ProtocolGraph("thermal")
    graph.add_step(
        Transform(
            target=c,
            parameter="temperature",
            target_value=Q_(90, "degC"),
            duration=Q_(2, "second"),
        )
    )

    try:
        graph.dry_run()
    except ThermalExcursionError:
        return
    raise AssertionError("Expected ThermalExcursionError")
