"""Viam adapter using the Viam Python SDK for robot dispatch."""

from __future__ import annotations

import asyncio
import inspect
import os
from typing import Any, Dict, List

from .base import BaseAdapter


class ViamAdapter(BaseAdapter):
    """Map Move actions to arm/base commands and optionally dispatch via Viam SDK."""

    def execute(self, dag_json: Any) -> Dict[str, Any]:
        protocol_data = self._prepare_payload(dag_json)
        commands = self._map_commands(protocol_data)

        result: Dict[str, Any] = {"commands": commands}
        if self._env_flag("VIAM_EXECUTE_ENABLED", default=False):
            result["dispatch"] = self._dispatch_with_sdk(commands)
        return result

    def discover_capabilities(self) -> Dict[str, Any]:
        return {
            "name": "ViamAdapter",
            "actions": ["Move"],
            "features": ["arm_move_to", "base_set_power", "sdk_dispatch"],
        }

    def secure_config_schema(self) -> Dict[str, Any]:
        return {
            "required_env": [
                "VIAM_ROBOT_ADDRESS",
                "VIAM_API_KEY_ID",
                "VIAM_API_KEY",
                "VIAM_COMPONENT_NAME",
            ],
            "optional_env": [
                "VIAM_COMPONENT_KIND",
                "VIAM_ARM_TARGETS_JSON",
                "VIAM_BASE_POWER_MAP_JSON",
            ],
        }

    def _map_commands(self, protocol_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        component_kind = os.environ.get("VIAM_COMPONENT_KIND", "arm").strip().lower()
        arm_targets = self._load_env_json("VIAM_ARM_TARGETS_JSON")
        base_powers = self._load_env_json("VIAM_BASE_POWER_MAP_JSON")

        commands: List[Dict[str, Any]] = []
        for step in protocol_data.get("steps", []):
            if step.get("action_type") != "Move":
                continue

            params = step.get("parameters", {})
            destination = str(params.get("destination", ""))

            if component_kind == "base":
                power = base_powers.get(
                    destination,
                    {"linear": [0.25, 0.0, 0.0], "angular": [0.0, 0.0, 0.0]},
                )
                commands.append({"api": "base.set_power", "power": power})
            else:
                target = arm_targets.get(
                    destination,
                    {
                        "destination": destination,
                        "amount_ml": params.get("amount_ml"),
                    },
                )
                commands.append({"api": "component.move_to", "target": target})

        return commands

    def _dispatch_with_sdk(self, commands: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        try:
            from viam.components.arm import Arm
            from viam.components.base import Base
            from viam.robot.client import RobotClient
            from viam.rpc.dial import Credentials, DialOptions
        except ImportError as exc:  # pragma: no cover - optional dependency path
            raise RuntimeError("Install viam-sdk to dispatch commands with ViamAdapter.") from exc

        address = os.environ.get("VIAM_ROBOT_ADDRESS")
        api_key_id = os.environ.get("VIAM_API_KEY_ID")
        api_key = os.environ.get("VIAM_API_KEY")
        component_name = os.environ.get("VIAM_COMPONENT_NAME")
        component_kind = os.environ.get("VIAM_COMPONENT_KIND", "arm").strip().lower()

        missing = [
            name
            for name, value in {
                "VIAM_ROBOT_ADDRESS": address,
                "VIAM_API_KEY_ID": api_key_id,
                "VIAM_API_KEY": api_key,
                "VIAM_COMPONENT_NAME": component_name,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError(f"Missing required Viam env vars: {', '.join(missing)}")

        async def _run() -> List[Dict[str, Any]]:
            dial_options = DialOptions(
                auth_entity=api_key_id,
                credentials=Credentials(type="api-key", payload=api_key),
            )
            robot = await RobotClient.at_address(address, dial_options)

            try:
                component: Any
                if component_kind == "base":
                    component = Base.from_robot(robot, component_name)
                else:
                    component = Arm.from_robot(robot, component_name)

                sent: List[Dict[str, Any]] = []
                for command in commands:
                    if command["api"] == "component.move_to":
                        move_to = component.move_to
                        maybe_awaitable = move_to(command["target"])
                        if inspect.isawaitable(maybe_awaitable):
                            await maybe_awaitable
                    elif command["api"] == "base.set_power":
                        set_power = component.set_power
                        power = command["power"]
                        linear = power.get("linear", [0.25, 0.0, 0.0])
                        angular = power.get("angular", [0.0, 0.0, 0.0])
                        maybe_awaitable = set_power(linear, angular)
                        if inspect.isawaitable(maybe_awaitable):
                            await maybe_awaitable

                    sent.append({"status": "sent", "command": command})

                return sent
            finally:
                close = getattr(robot, "close", None)
                if close is not None:
                    maybe_awaitable = close()
                    if inspect.isawaitable(maybe_awaitable):
                        await maybe_awaitable

        return asyncio.run(_run())
