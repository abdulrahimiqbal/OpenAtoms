"""Opentrons adapter for OT-2/Flex protocol generation and submission."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List
from urllib import request

from .base import BaseAdapter


class OpentronsAdapter(BaseAdapter):
    """Translate OpenAtoms DAG steps into an Opentrons Python protocol."""

    def __init__(self, *, urlopen_func=None):
        self._urlopen = urlopen_func or request.urlopen

    def execute(self, dag_json: Any) -> Dict[str, Any]:
        protocol_data = self._prepare_payload(dag_json)
        script = self._build_protocol_script(protocol_data)

        result: Dict[str, Any] = {"protocol_script": script}
        if self._env_flag("OPENTRONS_POST_ON_EXECUTE", default=False):
            result["post_response"] = self.post_protocol(script)
        return result

    def post_protocol(self, protocol_script: str) -> Dict[str, Any]:
        """POST a generated protocol script to an Opentrons HTTP endpoint."""
        robot_url = os.environ.get("OPENTRONS_ROBOT_URL")
        if not robot_url:
            raise RuntimeError("OPENTRONS_ROBOT_URL is required to POST protocols.")

        path = os.environ.get("OPENTRONS_PROTOCOLS_PATH", "/protocols")
        endpoint = f"{robot_url.rstrip('/')}{path if path.startswith('/') else '/' + path}"
        timeout_s = float(os.environ.get("OPENTRONS_HTTP_TIMEOUT_S", "15"))

        headers = {"Content-Type": "application/json"}
        token = os.environ.get("OPENTRONS_API_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        body = json.dumps(
            {
                "source": "openatoms",
                "format": "python",
                "protocol": protocol_script,
            }
        ).encode("utf-8")

        req = request.Request(endpoint, data=body, headers=headers, method="POST")
        with self._urlopen(req, timeout=timeout_s) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8", errors="replace")
            return {"status_code": resp.status, "body": raw}

    def discover_capabilities(self) -> Dict[str, Any]:
        return {
            "name": "OpentronsAdapter",
            "actions": ["Move", "Transform"],
            "features": ["protocol_script", "http_post", "health_check"],
        }

    def health_check(self) -> Dict[str, Any]:
        base = super().health_check()
        base["robot_url_configured"] = bool(os.environ.get("OPENTRONS_ROBOT_URL"))
        return base

    def secure_config_schema(self) -> Dict[str, Any]:
        return {
            "required_env": [],
            "optional_env": ["OPENTRONS_ROBOT_URL", "OPENTRONS_API_TOKEN"],
        }

    @staticmethod
    def _build_protocol_script(protocol_data: Dict[str, Any]) -> str:
        metadata_name = protocol_data.get("protocol_name", "OpenAtoms Protocol")
        lines: List[str] = [
            "from opentrons import protocol_api",
            "",
            f"metadata = {{'apiLevel': '2.15', 'protocolName': {metadata_name!r}}}",
            "",
            "def run(protocol: protocol_api.ProtocolContext):",
            "    plate = protocol.load_labware('corning_96_wellplate_360ul_flat', '1')",
            "    pipette = protocol.load_instrument('p300_single', 'right')",
        ]

        for step in protocol_data.get("steps", []):
            action = step.get("action_type")
            params = step.get("parameters", {})

            if action == "Move":
                amount_ml = params.get("amount_ml", 0)
                source = params.get("source", "A1")
                destination = params.get("destination", "A2")
                lines.append(
                    "    pipette.transfer("
                    f"{amount_ml}, "
                    f"plate.wells_by_name().get({source!r}, plate.wells()[0]), "
                    f"plate.wells_by_name().get({destination!r}, plate.wells()[1])"
                    ")"
                )
            elif action == "Transform" and params.get("parameter") == "temperature_c":
                target_value = params.get("target_value", 25)
                lines.extend(
                    [
                        "    temp_module = protocol.load_module('temperature module', '3')",
                        f"    temp_module.set_temperature({target_value})",
                    ]
                )
            else:
                lines.append(
                    f"    # Step {step.get('step', '?')}: {action} not mapped for Opentrons"
                )

        return "\n".join(lines)
