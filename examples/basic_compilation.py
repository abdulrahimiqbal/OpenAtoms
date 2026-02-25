import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from openatoms.core import Matter, Container, Phase
from openatoms.actions import Move, Transform
from openatoms.dag import ProtocolGraph
from openatoms.adapters import OpentronsAdapter, SmartBaristaAdapter

source = Container("Vessel_A", max_volume_ml=1000, max_temp_c=120)
dest = Container("Vessel_B", max_volume_ml=250, max_temp_c=120)
source.contents.append(Matter("H2O", Phase.LIQUID, 500, 500))

graph = ProtocolGraph("Transfer_and_Heat")
graph.add_step(Move(source, dest, 50))
graph.add_step(Transform(dest, "temperature_c", 90.0, 60))

if graph.dry_run():
    payload = graph.export_json()
    print("\n[Universal JSON DAG]\n", payload)
    print("\n[Opentrons Compilation]\n", OpentronsAdapter(payload).compile())
    print("\n[Barista Compilation]\n", SmartBaristaAdapter(payload).compile())
