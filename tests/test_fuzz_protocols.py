import random

from openatoms.actions import Combine, Move, Transform
from openatoms.core import Container, Matter, Phase
from openatoms.dag import ProtocolGraph
from openatoms.exceptions import PhysicsError


def test_random_protocol_generation_fail_closed_no_crash():
    rng = random.Random(1234)

    for idx in range(75):
        source = Container(f"src_{idx}", max_volume_ml=100, max_temp_c=100)
        dest = Container(f"dest_{idx}", max_volume_ml=40, max_temp_c=80)
        source.contents.append(Matter("H2O", Phase.LIQUID, mass_g=30, volume_ml=30))

        graph = ProtocolGraph(f"fuzz_{idx}")
        graph.add_step(Move(source, dest, rng.uniform(-5, 80)))
        graph.add_step(
            Transform(
                dest,
                "temperature_c",
                rng.uniform(-120, 260),
                rng.uniform(-10, 120),
            )
        )
        graph.add_step(Combine(dest, "vortex", rng.uniform(-5, 50)))

        try:
            graph.dry_run()
        except PhysicsError as exc:
            payload = exc.to_agent_payload()
            assert '"error_type"' in payload
            assert '"status": "failed"' in payload
