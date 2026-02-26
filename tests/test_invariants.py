from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from openatoms.actions import Move
from openatoms.core import Container, Matter, Phase
from openatoms.errors import VolumeOverflowError
from openatoms.units import Q_
from openatoms.validators import assert_mass_conservation, assert_volume_feasibility, clone_containers


@given(
    initial_volumes=st.lists(
        st.floats(min_value=0.1, max_value=50, allow_nan=False, allow_infinity=False),
        min_size=2,
        max_size=5,
    ),
    transfer_fraction=st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False),
)
def test_mass_conservation_under_random_transfers(
    initial_volumes: list[float],
    transfer_fraction: float,
) -> None:
    containers: list[Container] = []
    for index, volume in enumerate(initial_volumes):
        container = Container(
            id=f"c{index}",
            label=f"C{index}",
            max_volume=Q_(200, "milliliter"),
            max_temp=Q_(120, "degC"),
            min_temp=Q_(-20, "degC"),
        )
        container.contents.append(
            Matter(
                name="water",
                phase=Phase.LIQUID,
                mass=Q_(volume, "gram"),
                volume=Q_(volume, "milliliter"),
                density=Q_(1.0, "gram / milliliter"),
            )
        )
        containers.append(container)

    source = containers[0]
    destination = containers[1]
    transfer_volume = source.current_volume.to("milliliter").magnitude * transfer_fraction

    before = clone_containers(containers)
    move = Move(source, destination, Q_(transfer_volume, "milliliter"))
    move.execute()
    after = clone_containers(containers)

    assert_mass_conservation(before, after)


@given(
    max_vol=st.floats(min_value=10, max_value=500, allow_nan=False, allow_infinity=False),
    fill_vol=st.floats(min_value=0.1, max_value=600, allow_nan=False, allow_infinity=False),
)
def test_volume_overflow_always_caught(max_vol: float, fill_vol: float) -> None:
    container = Container(
        id="target",
        label="Target",
        max_volume=Q_(max_vol, "milliliter"),
        max_temp=Q_(120, "degC"),
        min_temp=Q_(-20, "degC"),
    )

    if fill_vol > max_vol:
        try:
            assert_volume_feasibility(container, Q_(fill_vol, "milliliter"))
        except VolumeOverflowError:
            return
        raise AssertionError("VolumeOverflowError was not raised for overflow condition.")

    assert_volume_feasibility(container, Q_(fill_vol, "milliliter"))
