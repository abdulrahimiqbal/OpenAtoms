"""Bambu Lab adapter using MQTT transport with G-code payloads."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from .base import BaseAdapter


class BambuAdapter(BaseAdapter):
    """Translate Transform/Action steps into printer G-code over MQTT."""

    def __init__(self, *, mqtt_client_factory=None):
        self._mqtt_client_factory = mqtt_client_factory

    def execute(self, dag_json: Any) -> Dict[str, Any]:
        protocol_data = self._prepare_payload(dag_json)
        gcode_lines = self._to_gcode(protocol_data)

        result: Dict[str, Any] = {"gcode": gcode_lines}
        if self._env_flag("BAMBU_SEND_ON_EXECUTE", default=False):
            result["mqtt_response"] = self.publish_gcode(gcode_lines)
        return result

    def publish_gcode(self, gcode_lines: List[str]) -> Dict[str, Any]:
        """Send generated G-code commands to a Bambu MQTT broker."""
        if self._mqtt_client_factory is None:
            try:
                import paho.mqtt.client as mqtt
            except ImportError as exc:  # pragma: no cover - optional dependency path
                raise RuntimeError("Install paho-mqtt to publish Bambu MQTT commands.") from exc
            mqtt_client_factory = mqtt.Client
        else:
            mqtt_client_factory = self._mqtt_client_factory

        host = os.environ.get("BAMBU_MQTT_HOST")
        if not host:
            raise RuntimeError("BAMBU_MQTT_HOST is required to publish over MQTT.")

        port = int(os.environ.get("BAMBU_MQTT_PORT", "1883"))
        topic = os.environ.get("BAMBU_MQTT_TOPIC", "device/request")
        timeout_s = int(os.environ.get("BAMBU_MQTT_TIMEOUT_S", "60"))

        client = mqtt_client_factory()
        username = os.environ.get("BAMBU_MQTT_USERNAME")
        password = os.environ.get("BAMBU_MQTT_PASSWORD")
        if username:
            client.username_pw_set(username, password)

        client.connect(host, port, timeout_s)

        published: List[Dict[str, Any]] = []
        for line in gcode_lines:
            payload = json.dumps({"command": "gcode_line", "line": line})
            info = client.publish(topic, payload=payload, qos=1)
            published.append({"line": line, "mid": getattr(info, "mid", None)})

        client.disconnect()
        return {"topic": topic, "published": published}

    def discover_capabilities(self) -> Dict[str, Any]:
        return {
            "name": "BambuAdapter",
            "actions": ["Transform", "Print", "Extrude", "Action"],
            "features": ["gcode_generation", "mqtt_dispatch"],
        }

    def secure_config_schema(self) -> Dict[str, Any]:
        return {
            "required_env": [],
            "optional_env": ["BAMBU_MQTT_HOST", "BAMBU_MQTT_USERNAME", "BAMBU_MQTT_PASSWORD"],
        }

    @staticmethod
    def _to_gcode(protocol_data: Dict[str, Any]) -> List[str]:
        gcode: List[str] = []

        for step in protocol_data.get("steps", []):
            action = str(step.get("action_type", ""))
            params = step.get("parameters", {})
            action_name = str(params.get("command") or params.get("name") or action).lower()

            if action == "Transform" and params.get("parameter") == "temperature_c":
                gcode.append(f"M104 S{params.get('target_value', 0)}")
                continue

            if action in {"Print", "Action", "Actions"} and action_name == "print":
                filename = params.get("filename") or params.get("file") or "openatoms.gcode"
                gcode.append(f"M23 {filename}")
                gcode.append("M24")
                continue

            if action in {"Extrude", "Action", "Actions"} and action_name == "extrude":
                length = params.get("length_mm", params.get("amount_ml", 1))
                feedrate = params.get("feedrate_mm_min", 300)
                gcode.append(f"G1 E{length} F{feedrate}")

        return gcode
