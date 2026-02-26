import json

import pytest

from openatoms.adapters import (
    ArduinoCloudAdapter,
    BambuAdapter,
    HomeAssistantAdapter,
    OpentronsAdapter,
    ViamAdapter,
)
from openatoms.actions import Move
from openatoms.core import Container, Matter, Phase
from openatoms.dag import ProtocolGraph
from openatoms.exceptions import CapacityExceededError
from openatoms.runner import ProtocolRunner


class FakeDag:
    def __init__(self, payload: dict, should_fail: bool = False):
        self.payload = payload
        self.should_fail = should_fail
        self.dry_run_calls = 0

    def dry_run(self):
        self.dry_run_calls += 1
        if self.should_fail:
            raise CapacityExceededError("Dest", 100, 50)
        return True

    def export_json(self) -> str:
        return json.dumps(self.payload)


PAYLOAD = {
    "protocol_name": "Adapter_Test",
    "version": "1.0.0",
    "steps": [
        {
            "step": 1,
            "action_type": "Move",
            "parameters": {"source": "A1", "destination": "B1", "amount_ml": 5},
        },
        {
            "step": 2,
            "action_type": "Transform",
            "parameters": {
                "target": "B1",
                "parameter": "temperature_c",
                "target_value": 65,
                "duration_s": 30,
            },
        },
        {
            "step": 3,
            "action_type": "Action",
            "parameters": {
                "service": "switch.turn_on",
                "entity_id": "switch.pump",
                "cloud_variable": "relay_state",
                "value": 1,
                "command": "extrude",
                "length_mm": 3,
            },
        },
    ],
}


@pytest.mark.parametrize(
    "adapter",
    [
        OpentronsAdapter(),
        ViamAdapter(),
        BambuAdapter(),
        HomeAssistantAdapter(),
        ArduinoCloudAdapter(),
    ],
)
def test_adapters_enforce_dry_run(adapter):
    dag = FakeDag(PAYLOAD)
    adapter.execute(dag)
    assert dag.dry_run_calls == 1


def test_adapter_bubbles_physics_error():
    dag = FakeDag(PAYLOAD, should_fail=True)

    with pytest.raises(CapacityExceededError):
        OpentronsAdapter().execute(dag)


def test_runner_executes_dag_with_adapter():
    source = Container("A", max_volume_ml=100, max_temp_c=100)
    dest = Container("B", max_volume_ml=100, max_temp_c=100)
    source.contents.append(Matter("H2O", Phase.LIQUID, 10, 10))

    dag = ProtocolGraph("Runner_Test")
    dag.add_step(Move(source, dest, 5))

    runner = ProtocolRunner(adapter=OpentronsAdapter())
    result = runner.run(dag)

    assert "protocol_script" in result
    assert "pipette.transfer" in result["protocol_script"]
