# OpenAtoms Adapter Layer

All adapters share one contract: `adapter.execute(dag)`.

- `dag` must be an OpenAtoms `ProtocolGraph` (or ProtocolGraph-like object with `dry_run()` + `export_json()`).
- Every adapter calls `dag.dry_run()` before translation/dispatch.
- If `dry_run()` raises `PhysicsError`, the exception is re-raised immediately.

## Base Interface

- Class: `BaseAdapter`
- File: `openatoms/adapters/base.py`
- Required method: `execute(self, dag_json)`

## OpentronsAdapter

- File: `openatoms/adapters/opentrons.py`
- Translation:
  - `Move` -> `pipette.transfer(...)`
  - `Transform(parameter="temperature_c")` -> temperature module commands
- Optional HTTP POST on execute (`OPENTRONS_POST_ON_EXECUTE=true`)
- Environment variables:
  - `OPENTRONS_ROBOT_URL`
  - `OPENTRONS_API_TOKEN` (optional)
  - `OPENTRONS_PROTOCOLS_PATH` (optional, default `/protocols`)
  - `OPENTRONS_HTTP_TIMEOUT_S` (optional)

## ViamAdapter

- File: `openatoms/adapters/viam.py`
- Mapping:
  - `Move` -> `component.move_to(...)` for arm mode
  - `Move` -> `base.set_power(...)` for mobile base mode
- Optional SDK dispatch on execute (`VIAM_EXECUTE_ENABLED=true`)
- Environment variables:
  - `VIAM_COMPONENT_KIND` (`arm` or `base`)
  - `VIAM_COMPONENT_NAME`
  - `VIAM_ARM_TARGETS_JSON` (optional destination->target map)
  - `VIAM_BASE_POWER_MAP_JSON` (optional destination->power map)
  - `VIAM_ROBOT_ADDRESS`, `VIAM_API_KEY_ID`, `VIAM_API_KEY` (required for live dispatch)

## BambuAdapter

- File: `openatoms/adapters/bambu.py`
- Mapping:
  - `Transform(parameter="temperature_c")` -> `M104 S...`
  - `Action/Actions(Print)` -> `M23` + `M24`
  - `Action/Actions(Extrude)` -> `G1 E...`
- Optional MQTT send on execute (`BAMBU_SEND_ON_EXECUTE=true`)
- Environment variables:
  - `BAMBU_MQTT_HOST`
  - `BAMBU_MQTT_PORT` (optional, default `1883`)
  - `BAMBU_MQTT_TOPIC` (optional)
  - `BAMBU_MQTT_USERNAME`, `BAMBU_MQTT_PASSWORD` (optional)
  - `BAMBU_MQTT_TIMEOUT_S` (optional)

## HomeAssistantAdapter

- File: `openatoms/adapters/home_assistant.py`
- Mapping:
  - Generic service calls from step parameter `service` (e.g. `switch.turn_on`)
  - `Transform(parameter="temperature_c")` -> `climate.set_temperature`
  - `Move` -> configurable service call (default `switch.turn_on`)
- Optional REST execution on execute (`HOME_ASSISTANT_EXECUTE_ENABLED=true`)
- Environment variables:
  - `HOME_ASSISTANT_URL`
  - `HOME_ASSISTANT_TOKEN`
  - `HOME_ASSISTANT_TIMEOUT_S` (optional)
  - `HOME_ASSISTANT_CLIMATE_ENTITY_ID` (optional)
  - `HOME_ASSISTANT_MOVE_SERVICE` / `HOME_ASSISTANT_MOVE_ENTITY_ID` (optional)

## ArduinoCloudAdapter

- File: `openatoms/adapters/arduino_cloud.py`
- Mapping:
  - `Move` -> cloud variable update (default `pump_volume_ml`)
  - `Transform(parameter="temperature_c")` -> cloud variable update (default `target_temperature_c`)
  - Explicit variable update via step parameter `cloud_variable`
- Optional REST execution on execute (`ARDUINO_EXECUTE_ENABLED=true`)
- Environment variables:
  - `ARDUINO_IOT_ACCESS_TOKEN` (or OAuth credentials below)
  - `ARDUINO_IOT_CLIENT_ID`, `ARDUINO_IOT_CLIENT_SECRET`
  - `ARDUINO_VARIABLE_MAP_JSON` (variable -> `{thing_id, property_id}`)
  - `ARDUINO_THING_ID` and `ARDUINO_PROPERTY_ID_<VARIABLE_NAME>` fallbacks
  - `ARDUINO_MOVE_VARIABLE`, `ARDUINO_TEMP_VARIABLE` (optional)
  - `ARDUINO_TIMEOUT_S` (optional)

## Runner Integration

```python
from openatoms.adapters import OpentronsAdapter
from openatoms.runner import ProtocolRunner

runner = ProtocolRunner(adapter=OpentronsAdapter())
result = runner.run(dag)
```
