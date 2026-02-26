from __future__ import annotations

from openatoms import (
    Q_,
    Container,
    Matter,
    Move,
    Phase,
    build_protocol,
    create_protocol_state,
)


def build_minimal_protocol(name: str = "bundle_protocol"):
    source = Container(
        id="A1",
        label="A1",
        max_volume=Q_(300, "microliter"),
        max_temp=Q_(80, "degC"),
        min_temp=Q_(4, "degC"),
    )
    destination = Container(
        id="A2",
        label="A2",
        max_volume=Q_(300, "microliter"),
        max_temp=Q_(80, "degC"),
        min_temp=Q_(4, "degC"),
    )
    source.contents.append(
        Matter(
            name="water",
            phase=Phase.LIQUID,
            mass=Q_(100, "milligram"),
            volume=Q_(100, "microliter"),
        )
    )
    state = create_protocol_state([source, destination])
    return build_protocol(name, [Move(source, destination, Q_(50, "microliter"))], state=state)
