from openatoms.actions import Move
from openatoms.core import Container, Matter, Phase
from openatoms.dag import ProtocolGraph
from openatoms.errors import ReactionFeasibilityError
from openatoms.sim.registry.kinetics_sim import VirtualReactor
from openatoms.sim.registry.opentrons_sim import OT2Simulator
from openatoms.sim.registry.robotics_sim import RoboticsSimulator
from openatoms.sim.types import Pose
from openatoms.units import Q_


def _well(well_id: str) -> Container:
    return Container(
        id=well_id,
        label=well_id,
        max_volume=Q_(300, "microliter"),
        max_temp=Q_(70, "degC"),
        min_temp=Q_(4, "degC"),
    )


def test_ot2_simulator_catches_aspiration_error() -> None:
    a1, a2 = _well("A1"), _well("A2")
    a1.contents.append(Matter(name="w", phase=Phase.LIQUID, mass=Q_(150, "milligram"), volume=Q_(150, "microliter")))

    graph = ProtocolGraph("ot2_check")
    graph.add_step(Move(a1, a2, Q_(200, "microliter")))

    obs = OT2Simulator().run(graph)
    assert obs.success is False
    assert any(err.error_code == "VOL_001" for err in obs.errors)


def test_virtual_reactor_gibbs_check_returns_expected_sign() -> None:
    reactor = VirtualReactor(mechanism="h2o2.yaml")
    spontaneous, delta_g = reactor.check_gibbs_feasibility(
        reactants={"H2": 1.0, "O2": 0.5},
        products={"H2O": 1.0},
        T=Q_(300, "kelvin"),
        P=Q_(1, "atm"),
    )
    assert spontaneous is True
    assert delta_g.to("kilojoule/mole").magnitude < 0


def test_robotics_simulator_flags_torque_and_collision() -> None:
    sim = RoboticsSimulator()

    try:
        sim.simulate_arm_trajectory(
            waypoints=[Pose(x_m=1.0, y_m=0.0, z_m=0.2)],
            payload_mass=Q_(2.0, "kilogram"),
        )
    except Exception as exc:
        assert "torque" in str(exc).lower() or "joint" in str(exc).lower()
    else:
        raise AssertionError("Expected torque limit error")

    try:
        sim.simulate_arm_trajectory(
            waypoints=[Pose(x_m=0.2, y_m=0.2, z_m=0.01)],
            payload_mass=Q_(0.1, "kilogram"),
        )
    except Exception as exc:
        assert "collision" in str(exc).lower() or "workspace" in str(exc).lower()
    else:
        raise AssertionError("Expected collision risk error")
