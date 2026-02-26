"""Minimal OpenAtoms hello world producing IR JSON."""

from openatoms.actions import Move
from openatoms.core import Container, Matter, Phase
from openatoms.dag import ProtocolGraph
from openatoms.units import Q_


def main() -> None:
    a = Container(id="A", label="A", max_volume=Q_(500, "microliter"), max_temp=Q_(100, "degC"), min_temp=Q_(0, "degC"))
    b = Container(id="B", label="B", max_volume=Q_(500, "microliter"), max_temp=Q_(100, "degC"), min_temp=Q_(0, "degC"))
    a.contents.append(Matter(name="H2O", phase=Phase.LIQUID, mass=Q_(200, "milligram"), volume=Q_(200, "microliter")))

    graph = ProtocolGraph("Hello_Atoms")
    graph.add_step(Move(a, b, Q_(100, "microliter")))
    graph.dry_run()
    print(graph.export_json())


if __name__ == "__main__":
    main()
