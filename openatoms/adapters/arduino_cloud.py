"""Arduino IoT Cloud adapter for Cloud Variable updates."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Tuple
from urllib import parse, request

from .base import BaseAdapter


class ArduinoCloudAdapter(BaseAdapter):
    """Map DAG actions into Arduino Cloud variable updates."""

    def __init__(self, *, urlopen_func=None):
        self._urlopen = urlopen_func or request.urlopen

    def execute(self, dag_json: Any) -> Dict[str, Any]:
        protocol_data = self._prepare_payload(dag_json)
        updates = self._map_variable_updates(protocol_data)

        result: Dict[str, Any] = {"variable_updates": updates}
        if self._env_flag("ARDUINO_EXECUTE_ENABLED", default=False):
            result["responses"] = [self.publish_update(update) for update in updates]
        return result

    def publish_update(self, update: Dict[str, Any]) -> Dict[str, Any]:
        """Publish one cloud variable value to Arduino IoT Cloud."""
        thing_id, property_id = self._resolve_binding(update["variable"])
        token = self._access_token()
        timeout_s = float(os.environ.get("ARDUINO_TIMEOUT_S", "15"))

        endpoint = (
            "https://api2.arduino.cc/iot/v2/things/"
            f"{thing_id}/properties/{property_id}/publish"
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        body = json.dumps({"value": update["value"]}).encode("utf-8")

        req = request.Request(endpoint, data=body, headers=headers, method="PUT")
        with self._urlopen(req, timeout=timeout_s) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8", errors="replace")
            return {
                "status_code": resp.status,
                "variable": update["variable"],
                "body": raw,
            }

    def discover_capabilities(self) -> Dict[str, Any]:
        return {
            "name": "ArduinoCloudAdapter",
            "actions": ["Move", "Transform", "Action"],
            "features": ["cloud_variable_mapping", "rest_publish"],
        }

    def secure_config_schema(self) -> Dict[str, Any]:
        return {
            "required_env": [],
            "optional_env": [
                "ARDUINO_IOT_ACCESS_TOKEN",
                "ARDUINO_IOT_CLIENT_ID",
                "ARDUINO_IOT_CLIENT_SECRET",
                "ARDUINO_THING_ID",
            ],
        }

    def _map_variable_updates(self, protocol_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        move_var = os.environ.get("ARDUINO_MOVE_VARIABLE", "pump_volume_ml")
        temp_var = os.environ.get("ARDUINO_TEMP_VARIABLE", "target_temperature_c")

        updates: List[Dict[str, Any]] = []
        for step in protocol_data.get("steps", []):
            action = step.get("action_type")
            params = step.get("parameters", {})

            explicit_var = params.get("cloud_variable")
            if explicit_var:
                explicit_val = params.get("value", params.get("target_value", 1))
                updates.append({"variable": str(explicit_var), "value": explicit_val})
                continue

            if action == "Move":
                updates.append({"variable": move_var, "value": params.get("amount_ml", 0)})
            elif action == "Transform" and params.get("parameter") == "temperature_c":
                updates.append({"variable": temp_var, "value": params.get("target_value")})

        return updates

    def _resolve_binding(self, variable_name: str) -> Tuple[str, str]:
        mapping = self._load_env_json("ARDUINO_VARIABLE_MAP_JSON")
        item = mapping.get(variable_name, {})

        thing_id = item.get("thing_id") or os.environ.get("ARDUINO_THING_ID")
        variable_key = variable_name.upper().replace("-", "_")
        property_id = item.get("property_id") or os.environ.get(
            f"ARDUINO_PROPERTY_ID_{variable_key}"
        )

        if not thing_id or not property_id:
            raise RuntimeError(
                "Missing Arduino binding for variable "
                f"'{variable_name}'. Configure ARDUINO_VARIABLE_MAP_JSON or env IDs."
            )

        return str(thing_id), str(property_id)

    def _access_token(self) -> str:
        preset = os.environ.get("ARDUINO_IOT_ACCESS_TOKEN")
        if preset:
            return preset

        client_id = os.environ.get("ARDUINO_IOT_CLIENT_ID")
        client_secret = os.environ.get("ARDUINO_IOT_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise RuntimeError(
                "Set ARDUINO_IOT_ACCESS_TOKEN or both ARDUINO_IOT_CLIENT_ID and "
                "ARDUINO_IOT_CLIENT_SECRET."
            )

        timeout_s = float(os.environ.get("ARDUINO_TIMEOUT_S", "15"))
        form = parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "audience": "https://api2.arduino.cc/iot",
            }
        ).encode("utf-8")

        req = request.Request(
            "https://api2.arduino.cc/iot/v1/clients/token",
            data=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with self._urlopen(req, timeout=timeout_s) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8", errors="replace")
            payload = json.loads(raw)
            token = payload.get("access_token")
            if not token:
                raise RuntimeError("Arduino token response did not include access_token.")
            return str(token)
