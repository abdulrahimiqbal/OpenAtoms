"""Shared adapter interface and DAG preparation helpers."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseAdapter(ABC):
    """Abstract hardware adapter contract for OpenAtoms DAG execution."""

    @abstractmethod
    def execute(self, dag_json: Any) -> Dict[str, Any]:
        """Execute a ProtocolGraph-like object against a hardware target."""
        raise NotImplementedError

    @staticmethod
    def _prepare_payload(dag_json: Any) -> Dict[str, Any]:
        """Run DAG validation and return parsed JSON payload.

        This method intentionally calls `dag.dry_run()` so every concrete adapter
        enforces physics checks before any hardware side effect.
        """
        if not hasattr(dag_json, "dry_run") or not hasattr(dag_json, "export_json"):
            raise TypeError(
                "Adapter.execute expects a ProtocolGraph-like object with "
                "dry_run() and export_json()."
            )

        # Must bubble PhysicsError directly to the caller.
        dag_json.dry_run()
        payload = dag_json.export_json()

        try:
            protocol_data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("DAG export_json() did not return valid JSON.") from exc

        if not isinstance(protocol_data, dict):
            raise ValueError("DAG payload must be a JSON object.")
        if "steps" not in protocol_data or not isinstance(protocol_data["steps"], list):
            raise ValueError("DAG payload is missing a valid 'steps' list.")

        return protocol_data

    @staticmethod
    def _env_flag(name: str, default: bool = False) -> bool:
        """Return a bool parsed from an env var."""
        raw = os.environ.get(name)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _load_env_json(name: str) -> Dict[str, Any]:
        """Load optional JSON object from env var."""
        raw = os.environ.get(name, "").strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Environment variable {name} must contain valid JSON.") from exc
        if not isinstance(data, dict):
            raise ValueError(f"Environment variable {name} must contain a JSON object.")
        return data
