"""Deterministic protocol graph compilation and validation."""

import json
from copy import deepcopy
from typing import Dict, List, Set

try:
    from .actions import Action, Move, Transform
    from .exceptions import PhysicsError
    from .core import Container, Matter, Phase
except ImportError:  # pragma: no cover - fallback for direct script execution
    from actions import Action, Move, Transform
    from exceptions import PhysicsError
    from core import Container, Matter, Phase

class ProtocolGraph:
    """A deterministic, ordered graph of physical protocol actions."""

    def __init__(self, name: str):
        """Create an empty protocol graph."""
        self.name = name
        self.sequence: List[Action] = []
        self.is_compiled = False

    def add_step(self, action: Action):
        """Append an action to the protocol sequence."""
        self.sequence.append(action)

    def _collect_containers(self) -> Set[Container]:
        """Collect all container instances referenced by actions in the graph."""
        containers: Set[Container] = set()
        for action in self.sequence:
            for value in vars(action).values():
                if isinstance(value, Container):
                    containers.add(value)
        return containers

    def _snapshot_container_state(self, containers: Set[Container]) -> Dict[Container, list]:
        """Take a deep snapshot of container contents before simulation."""
        return {container: deepcopy(container.contents) for container in containers}

    @staticmethod
    def _restore_container_state(snapshot: Dict[Container, list]) -> None:
        """Restore container contents from a snapshot."""
        for container, contents in snapshot.items():
            container.contents = deepcopy(contents)

    @staticmethod
    def _simulate_move(action: Move) -> None:
        """Apply a deterministic state simulation for a move action."""
        transferred = Matter("mixture", Phase.LIQUID, 0, action.amount_ml)
        remaining = action.amount_ml
        while remaining > 0 and action.source.contents:
            source_matter = action.source.contents[-1]
            pulled = min(source_matter.volume_ml, remaining)
            source_matter.volume_ml -= pulled
            remaining -= pulled
            if source_matter.volume_ml <= 0:
                action.source.contents.pop()
        action.destination.contents.append(transferred)

    def dry_run(self) -> bool:
        """Validate and simulate every step before physical execution.

        On physics failures, the method restores all involved containers to the
        exact pre-run snapshot so the caller can retry safely.
        """
        container_snapshot = self._snapshot_container_state(self._collect_containers())
        print(f"--- Starting Dry Run for Protocol: {self.name} ---")
        for step_index, action in enumerate(self.sequence):
            try:
                action.validate()
                if isinstance(action, Move):
                    self._simulate_move(action)
                elif isinstance(action, Transform):
                    if action.parameter == "temperature_c":
                        for matter in action.target.contents:
                            matter.temp_c = action.target_value
                print(f"[✓] Step {step_index + 1} Validated: {type(action).__name__}")
            except PhysicsError as e:
                self._restore_container_state(container_snapshot)
                self.is_compiled = False
                print(f"\n[X] LINTER FATAL ERROR at Step {step_index + 1}:")
                print(e.to_agent_payload())
                # Bubble the error up so orchestration layers can consume structured payloads.
                raise e
        self.is_compiled = True
        return True

    def export_json(self) -> str:
        """Export a compiled protocol graph as deterministic JSON payload."""
        if not self.is_compiled: raise RuntimeError("Must pass dry_run() first.")
        payload = {"protocol_name": self.name, "version": "1.0.0", "steps": []}
        for i, action in enumerate(self.sequence):
            step_data = {
                "step": i + 1,
                "action_type": type(action).__name__,
                "parameters": {k: v.name if hasattr(v, 'name') else v for k, v in vars(action).items() if k != 'status'}
            }
            payload["steps"].append(step_data)
        return json.dumps(payload, indent=4)
