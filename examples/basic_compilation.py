from openatoms.actions import Move, Transform
from openatoms.adapters import BambuAdapter, OpentronsAdapter
from openatoms.core import Container, Matter, Phase
from openatoms.dag import ProtocolGraph
from openatoms.runner import ProtocolRunner
from openatoms.units import Q_


def main() -> None:
    source = Container(
        id="vessel_a",
        label="Vessel_A",
        max_volume=Q_(1000, "milliliter"),
        max_temp=Q_(120, "degC"),
        min_temp=Q_(0, "degC"),
    )
    dest = Container(
        id="vessel_b",
        label="Vessel_B",
        max_volume=Q_(250, "milliliter"),
        max_temp=Q_(120, "degC"),
        min_temp=Q_(0, "degC"),
    )
    source.contents.append(
        Matter(
            name="H2O",
            phase=Phase.LIQUID,
            mass=Q_(500, "gram"),
            volume=Q_(500, "milliliter"),
        )
    )

    graph = ProtocolGraph("Transfer_and_Heat")
    graph.add_step(Move(source, dest, Q_(50, "milliliter")))
    graph.add_step(Transform(dest, "temperature", Q_(90, "degC"), Q_(60, "second")))

    print("\n[Runner -> OpentronsAdapter]")
    print(ProtocolRunner(OpentronsAdapter()).run(graph)["protocol_script"])

    print("\n[Runner -> BambuAdapter]")
    print(ProtocolRunner(BambuAdapter()).run(graph)["gcode"])


if __name__ == "__main__":
    main()
