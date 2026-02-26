import pytest

from openatoms.actions import Move, Transform
from openatoms.core import Container, Matter, Phase
from openatoms.dag import ProtocolGraph
from openatoms.exceptions import PhysicsError, StructuralIntegrityError
from openatoms.sim.registry import kinetics_sim, opentrons_sim
from openatoms.sim.registry.kinetics_sim import Vessel, VirtualReactor
from openatoms.sim.registry.opentrons_sim import OpentronsSimValidator


def test_virtual_reactor_raises_structural_integrity_error(monkeypatch):
    class FakeSolution:
        def __init__(self, _mechanism):
            self.T = 300.0
            self.P = 101325.0
            self._x = ""

        @property
        def TPX(self):
            return self.T, self.P, self._x

        @TPX.setter
        def TPX(self, values):
            self.T, self.P, self._x = values

    class FakeReactor:
        def __init__(self, gas, **_kwargs):
            self.thermo = gas

    class FakeReactorNet:
        def __init__(self, reactors):
            self.reactor = reactors[0]
            self.time_s = 0.0

        def step(self):
            self.time_s += 0.01
            self.reactor.thermo.P = 225000.0
            self.reactor.thermo.T += 10.0
            return self.time_s

    class FakeCantera:
        Solution = FakeSolution
        IdealGasReactor = FakeReactor
        ReactorNet = FakeReactorNet

    monkeypatch.setattr(
        VirtualReactor,
        "_load_cantera",
        staticmethod(lambda: FakeCantera),
    )

    reactor = VirtualReactor()
    vessel = Vessel(name="Glass_Vessel", burst_pressure_pa=150000.0)

    with pytest.raises(StructuralIntegrityError) as exc:
        reactor.simulate_hydrogen_oxygen_combustion(
            initial_temp_k=500.0,
            residence_time_s=0.02,
            vessel=vessel,
        )

    assert exc.value.error_type == "StructuralIntegrityError"
    assert "state_observation_json" in exc.value.details


def test_opentrons_out_of_bounds_returns_physics_error(monkeypatch, tmp_path):
    protocol_file = tmp_path / "protocol.py"
    protocol_file.write_text("metadata = {'apiLevel': '2.15'}\n", encoding="utf-8")

    class FakeSimModule:
        @staticmethod
        def simulate(*_args, **_kwargs):
            raise RuntimeError("Pipette moved out of bounds while targeting well H13")

    monkeypatch.setattr(
        OpentronsSimValidator,
        "_load_opentrons_simulate",
        staticmethod(lambda: FakeSimModule),
    )

    validator = OpentronsSimValidator()
    result = validator.validate_protocol(str(protocol_file))

    assert isinstance(result["error"], PhysicsError)
    assert result["error"].error_type == "DeckOutOfBoundsError"
    assert '"type": "StateObservation"' in result["state_observation_json"]
    assert result["run_log"] is None


def test_dry_run_science_mode_switches_backends(monkeypatch, tmp_path):
    protocol_file = tmp_path / "science_protocol.py"
    protocol_file.write_text("metadata = {'apiLevel': '2.15'}\n", encoding="utf-8")

    source = Container("Source", max_volume_ml=250, max_temp_c=120)
    destination = Container("Dest", max_volume_ml=250, max_temp_c=120)
    source.contents.append(Matter("H2O", Phase.LIQUID, mass_g=100, volume_ml=100, temp_c=20))

    graph = ProtocolGraph("Science_Mode_Test")
    graph.add_step(Move(source=source, destination=destination, amount_ml=10))
    graph.add_step(
        Transform(
            target=destination,
            parameter="temperature_c",
            target_value=60,
            duration_s=10,
        )
    )

    called = {}

    def fake_validate_protocol(self, path):
        called["protocol_path"] = path
        return {
            "state_observation_json": '{"type":"StateObservation","status":"ok"}',
            "error": None,
            "run_log": [],
        }

    def fake_simulate_h2o2(self, **kwargs):
        called["initial_temp_k"] = kwargs["initial_temp_k"]
        return {
            "state_observation_json": '{"type":"StateObservation","status":"ok"}',
            "thermo_state": object(),
            "reactor_state": object(),
            "reactor_network": object(),
        }

    monkeypatch.setattr(
        opentrons_sim.OpentronsSimValidator,
        "validate_protocol",
        fake_validate_protocol,
    )
    monkeypatch.setattr(
        kinetics_sim.VirtualReactor,
        "simulate_hydrogen_oxygen_combustion",
        fake_simulate_h2o2,
    )

    assert (
        graph.dry_run(
            mode="science",
            science_context={"opentrons_protocol_path": str(protocol_file)},
        )
        is True
    )
    assert called["protocol_path"] == str(protocol_file)
    assert called["initial_temp_k"] == pytest.approx(333.15)

