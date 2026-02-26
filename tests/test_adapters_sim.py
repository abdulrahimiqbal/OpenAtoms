import json

import openatoms.adapters.arduino_cloud as arduino_cloud_module
import openatoms.adapters.home_assistant as home_assistant_module
import openatoms.adapters.opentrons as opentrons_module
from openatoms.actions import Move, Transform
from openatoms.adapters import (
    ArduinoCloudAdapter,
    BambuAdapter,
    HomeAssistantAdapter,
    OpentronsAdapter,
    ViamAdapter,
)
from openatoms.core import Container, Matter, Phase
from openatoms.dag import ProtocolGraph


def build_valid_graph(target_temp: int = 70) -> ProtocolGraph:
    source = Container("Source_Vessel", max_volume_ml=250, max_temp_c=120)
    destination = Container("Plastic_Vessel", max_volume_ml=150, max_temp_c=80)
    source.contents.append(Matter("H2O", Phase.LIQUID, mass_g=100, volume_ml=100, temp_c=20))

    graph = ProtocolGraph("Adapter_Sim_Protocol")
    graph.add_step(Move(source=source, destination=destination, amount_ml=10))
    graph.add_step(
        Transform(
            target=destination,
            parameter="temperature_c",
            target_value=target_temp,
            duration_s=45,
        )
    )
    return graph


class _FakeResponse:
    def __init__(self, status: int = 200, body: str = "{}"):
        self.status = status
        self._body = body.encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_opentrons_adapter_simulated_post(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["timeout"] = timeout
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse(status=201, body='{"accepted": true}')

    monkeypatch.setenv("OPENTRONS_POST_ON_EXECUTE", "1")
    monkeypatch.setenv("OPENTRONS_ROBOT_URL", "http://opentrons.local")
    monkeypatch.setattr(opentrons_module.request, "urlopen", fake_urlopen)

    result = OpentronsAdapter().execute(build_valid_graph(target_temp=65))

    assert "pipette.transfer" in result["protocol_script"]
    assert "temp_module.set_temperature(65)" in result["protocol_script"]
    assert captured["url"] == "http://opentrons.local/protocols"
    assert captured["method"] == "POST"
    assert captured["body"]["format"] == "python"
    assert "pipette.transfer" in captured["body"]["protocol"]
    assert result["post_response"]["status_code"] == 201


def test_viam_adapter_simulated_dispatch(monkeypatch):
    captured = {}

    def fake_dispatch(self, commands):
        captured["commands"] = commands
        return [{"status": "sent", "command": command} for command in commands]

    monkeypatch.setenv("VIAM_EXECUTE_ENABLED", "1")
    monkeypatch.setenv("VIAM_COMPONENT_KIND", "arm")
    monkeypatch.setenv(
        "VIAM_ARM_TARGETS_JSON",
        '{"Plastic_Vessel": {"pose": [0.1, 0.2, 0.3], "frame": "lab"}}',
    )
    monkeypatch.setattr(ViamAdapter, "_dispatch_with_sdk", fake_dispatch)

    result = ViamAdapter().execute(build_valid_graph())

    assert result["commands"] == [
        {"api": "component.move_to", "target": {"pose": [0.1, 0.2, 0.3], "frame": "lab"}}
    ]
    assert result["dispatch"][0]["status"] == "sent"
    assert captured["commands"] == result["commands"]


def test_bambu_adapter_simulated_mqtt_publish(monkeypatch):
    captured = {}

    def fake_publish(self, gcode_lines):
        captured["gcode_lines"] = gcode_lines
        return {"topic": "device/request", "published": [{"line": line} for line in gcode_lines]}

    monkeypatch.setenv("BAMBU_SEND_ON_EXECUTE", "1")
    monkeypatch.setattr(BambuAdapter, "publish_gcode", fake_publish)

    result = BambuAdapter().execute(build_valid_graph(target_temp=70))

    assert result["gcode"] == ["M104 S70"]
    assert captured["gcode_lines"] == ["M104 S70"]
    assert result["mqtt_response"]["topic"] == "device/request"


def test_home_assistant_adapter_simulated_rest_post(monkeypatch):
    requests_made = []

    def fake_urlopen(req, timeout):
        requests_made.append(
            {
                "url": req.full_url,
                "method": req.get_method(),
                "timeout": timeout,
                "body": json.loads(req.data.decode("utf-8")),
            }
        )
        return _FakeResponse(status=200, body='{"ok": true}')

    monkeypatch.setenv("HOME_ASSISTANT_EXECUTE_ENABLED", "1")
    monkeypatch.setenv("HOME_ASSISTANT_URL", "http://ha.local:8123")
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "fake-token")
    monkeypatch.setenv("HOME_ASSISTANT_MOVE_SERVICE", "switch.turn_on")
    monkeypatch.setenv("HOME_ASSISTANT_MOVE_ENTITY_ID", "switch.transfer_pump")
    monkeypatch.setenv("HOME_ASSISTANT_CLIMATE_ENTITY_ID", "climate.virtual_lab")
    monkeypatch.setattr(home_assistant_module.request, "urlopen", fake_urlopen)

    result = HomeAssistantAdapter().execute(build_valid_graph(target_temp=70))
    climate_call = next(
        call for call in result["service_calls"] if call["domain"] == "climate"
    )

    assert climate_call == {
        "domain": "climate",
        "service": "set_temperature",
        "data": {"entity_id": "climate.virtual_lab", "temperature": 70},
    }
    assert any(
        req["url"].endswith("/api/services/climate/set_temperature")
        and req["method"] == "POST"
        and req["body"] == {"entity_id": "climate.virtual_lab", "temperature": 70}
        for req in requests_made
    )


def test_arduino_cloud_adapter_simulated_publish(monkeypatch):
    requests_made = []

    def fake_urlopen(req, timeout):
        requests_made.append(
            {
                "url": req.full_url,
                "method": req.get_method(),
                "timeout": timeout,
                "body": json.loads(req.data.decode("utf-8")),
            }
        )
        return _FakeResponse(status=200, body='{"published": true}')

    monkeypatch.setenv("ARDUINO_EXECUTE_ENABLED", "1")
    monkeypatch.setenv("ARDUINO_IOT_ACCESS_TOKEN", "fake-access-token")
    monkeypatch.setenv("ARDUINO_THING_ID", "thing-123")
    monkeypatch.setenv("ARDUINO_PROPERTY_ID_PUMP_VOLUME_ML", "prop-move")
    monkeypatch.setenv("ARDUINO_PROPERTY_ID_TARGET_TEMPERATURE_C", "prop-temp")
    monkeypatch.setattr(arduino_cloud_module.request, "urlopen", fake_urlopen)

    result = ArduinoCloudAdapter().execute(build_valid_graph(target_temp=70))

    assert result["variable_updates"] == [
        {"variable": "pump_volume_ml", "value": 10},
        {"variable": "target_temperature_c", "value": 70},
    ]
    assert any(
        req["url"].endswith("/things/thing-123/properties/prop-temp/publish")
        and req["method"] == "PUT"
        and req["body"] == {"value": 70}
        for req in requests_made
    )
    assert len(result["responses"]) == 2
