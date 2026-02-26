import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from openatoms.actions import Move, Transform
from openatoms.adapters import BambuAdapter, OpentronsAdapter
from openatoms.core import Container, Matter, Phase
from openatoms.dag import ProtocolGraph
from openatoms.runner import ProtocolRunner

source = Container("Vessel_A", max_volume_ml=1000, max_temp_c=120)
dest = Container("Vessel_B", max_volume_ml=250, max_temp_c=120)
source.contents.append(Matter("H2O", Phase.LIQUID, 500, 500))

graph = ProtocolGraph("Transfer_and_Heat")
graph.add_step(Move(source, dest, 50))
graph.add_step(Transform(dest, "temperature_c", 90.0, 60))

print("\n[Runner -> OpentronsAdapter]")
print(ProtocolRunner(OpentronsAdapter()).run(graph)["protocol_script"])

print("\n[Runner -> BambuAdapter]")
print(ProtocolRunner(BambuAdapter()).run(graph)["gcode"])
