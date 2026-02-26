import pytest

from openatoms.actions import Move
from openatoms.core import Container, Matter, Phase
from openatoms.dag import ProtocolGraph
from openatoms.exceptions import DependencyGraphError


def _containers():
    a = Container("A", max_volume_ml=100, max_temp_c=100)
    b = Container("B", max_volume_ml=100, max_temp_c=100)
    c = Container("C", max_volume_ml=100, max_temp_c=100)
    a.contents.append(Matter("H2O", Phase.LIQUID, 30, 30))
    return a, b, c


def test_dependency_ordering_executes_topologically():
    a, b, c = _containers()
    graph = ProtocolGraph("Deps")
    graph.add_step(Move(a, b, 10), step_id="s1")
    graph.add_step(Move(b, c, 5), step_id="s2", depends_on=["s1"])
    assert graph.dry_run() is True


def test_unknown_dependency_rejected():
    a, b, _ = _containers()
    graph = ProtocolGraph("Deps_Invalid")
    with pytest.raises(DependencyGraphError):
        graph.add_step(Move(a, b, 10), step_id="s2", depends_on=["missing"])
