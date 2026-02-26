"""Runner utilities that connect DAGs to adapters."""

from __future__ import annotations

from typing import Any, Dict

from .adapters import BaseAdapter


class ProtocolRunner:
    """Execute a ProtocolGraph with a specific adapter implementation."""

    def __init__(self, adapter: BaseAdapter):
        self.adapter = adapter

    def run(self, dag: Any) -> Dict[str, Any]:
        """Run a DAG by delegating to `adapter.execute(dag)`."""
        return self.adapter.execute(dag)
