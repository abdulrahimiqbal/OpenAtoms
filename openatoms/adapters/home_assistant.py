"""Home Assistant adapter using REST service calls."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Tuple
from urllib import request

from .base import BaseAdapter


class HomeAssistantAdapter(BaseAdapter):
    """Map DAG actions to Home Assistant service invocations."""

    def __init__(self, *, urlopen_func=None):
        self._urlopen = urlopen_func or request.urlopen

    def execute(self, dag_json: Any) -> Dict[str, Any]:
        protocol_data = self._prepare_payload(dag_json)
        service_calls = self._map_service_calls(protocol_data)

        result: Dict[str, Any] = {"service_calls": service_calls}
        if self._env_flag("HOME_ASSISTANT_EXECUTE_ENABLED", default=False):
            result["responses"] = [self.call_service(call) for call in service_calls]
        return result

    def call_service(self, service_call: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single Home Assistant service call over REST."""
        base_url = os.environ.get("HOME_ASSISTANT_URL")
        token = os.environ.get("HOME_ASSISTANT_TOKEN")
        if not base_url or not token:
            raise RuntimeError("HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN are required.")

        timeout_s = float(os.environ.get("HOME_ASSISTANT_TIMEOUT_S", "15"))
        domain = service_call["domain"]
        service = service_call["service"]
        endpoint = f"{base_url.rstrip('/')}/api/services/{domain}/{service}"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        body = json.dumps(service_call.get("data", {})).encode("utf-8")

        req = request.Request(endpoint, data=body, headers=headers, method="POST")
        with self._urlopen(req, timeout=timeout_s) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8", errors="replace")
            return {"status_code": resp.status, "body": raw}

    def discover_capabilities(self) -> Dict[str, Any]:
        return {
            "name": "HomeAssistantAdapter",
            "actions": ["Move", "Transform", "Action"],
            "features": ["service_mapping", "rest_dispatch"],
        }

    def secure_config_schema(self) -> Dict[str, Any]:
        return {
            "required_env": [],
            "optional_env": ["HOME_ASSISTANT_URL", "HOME_ASSISTANT_TOKEN"],
        }

    def _map_service_calls(self, protocol_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        calls: List[Dict[str, Any]] = []
        default_move_service = os.environ.get("HOME_ASSISTANT_MOVE_SERVICE", "switch.turn_on")
        climate_entity = os.environ.get("HOME_ASSISTANT_CLIMATE_ENTITY_ID", "")

        for step in protocol_data.get("steps", []):
            action = step.get("action_type")
            params = step.get("parameters", {})

            if action == "Move":
                domain, service = self._split_service(default_move_service)
                entity_id = params.get("entity_id") or os.environ.get(
                    "HOME_ASSISTANT_MOVE_ENTITY_ID"
                )
                data: Dict[str, Any] = {}
                if entity_id:
                    data["entity_id"] = entity_id
                data["amount_ml"] = params.get("amount_ml")
                calls.append({"domain": domain, "service": service, "data": data})
                continue

            if action == "Transform" and params.get("parameter") == "temperature_c":
                entity_id = params.get("entity_id") or climate_entity
                if not entity_id:
                    continue
                calls.append(
                    {
                        "domain": "climate",
                        "service": "set_temperature",
                        "data": {
                            "entity_id": entity_id,
                            "temperature": params.get("target_value"),
                        },
                    }
                )
                continue

            service_name = params.get("service")
            if service_name:
                domain, service = self._split_service(str(service_name))
                data = dict(params.get("data", {}))
                if "entity_id" in params and "entity_id" not in data:
                    data["entity_id"] = params["entity_id"]
                calls.append({"domain": domain, "service": service, "data": data})

        return calls

    @staticmethod
    def _split_service(service_name: str) -> Tuple[str, str]:
        if "." not in service_name:
            raise ValueError(
                "Service name must be 'domain.service' format, "
                f"received: {service_name}"
            )
        domain, service = service_name.split(".", 1)
        return domain.strip(), service.strip()
