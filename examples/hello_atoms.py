from openatoms.actions import Move
from openatoms.core import Container, Matter, Phase
from openatoms.dag import ProtocolGraph

a = Container("A", 100, 100)
b = Container("B", 100, 100)
a.contents.append(Matter("H2O", Phase.LIQUID, 10, 10))

g = ProtocolGraph("Hello_Atoms")
g.add_step(Move(a, b, 5))
g.dry_run()
print(g.export_json())
