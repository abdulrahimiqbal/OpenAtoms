"""Deterministic protocol graph compilation and validation.

Example:
    >>> from openatoms.actions import Move
    >>> from openatoms.core import Container, Matter, Phase
    >>> from openatoms.units import Q_
    >>> src = Container(id="s", label="S", max_volume=Q_(100, "milliliter"), max_temp=Q_(100, "degC"), min_temp=Q_(0, "degC"))
    >>> dst = Container(id="d", label="D", max_volume=Q_(100, "milliliter"), max_temp=Q_(100, "degC"), min_temp=Q_(0, "degC"))
    >>> src.contents.append(Matter(name="H2O", phase=Phase.LIQUID, mass=Q_(10, "gram"), volume=Q_(10, "milliliter")))
    >>> g = ProtocolGraph("demo")
    >>> g.add_step(Move(src, dst, Q_(5, "milliliter")))
    's1'
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set
from uuid import NAMESPACE_URL, uuid5

from .actions import Action, Move
from .core import Container
from .errors import OrderingConstraintError, PhysicsError
from .ir import IR_SCHEMA_VERSION, IR_VERSION, validate_ir
from .ir.provenance import attach_ir_hash
from .units import Quantity, quantity_json
from .validators import assert_mass_conservation, clone_containers


@dataclass
class ProtocolNode:
    """One action node in the protocol dependency graph."""

    step_id: str
    action: Action
    depends_on: Set[str]
    resources: Set[str]
    insertion_order: int


class ProtocolGraph:
    """Deterministic protocol graph with explicit dependency ordering."""

    def __init__(self, name: str):
        self.name = name
        self.sequence: list[Action] = []
        self.is_compiled = False
        self._nodes: list[ProtocolNode] = []
        self._node_by_id: dict[str, ProtocolNode] = {}

    def add_step(
        self,
        action: Action,
        *,
        step_id: Optional[str] = None,
        depends_on: Optional[list[str]] = None,
        resources: Optional[list[str]] = None,
    ) -> str:
        """Add one action step to the graph.

        Raises:
            OrderingConstraintError: If dependencies are malformed.
        """
        resolved_step_id = step_id or f"s{len(self._nodes) + 1}"
        if resolved_step_id in self._node_by_id:
            raise OrderingConstraintError(
                description=f"Duplicate step id '{resolved_step_id}'.",
                actual_value=resolved_step_id,
                limit_value="unique step_id",
                remediation_hint="Provide a unique step_id for each protocol node.",
            )

        if depends_on is None:
            resolved_deps = {self._nodes[-1].step_id} if self._nodes else set()
        else:
            resolved_deps = set(depends_on)

        unknown = sorted(dep for dep in resolved_deps if dep not in self._node_by_id)
        if unknown:
            raise OrderingConstraintError(
                description="Unknown dependency reference.",
                actual_value=unknown,
                limit_value="existing step ids",
                remediation_hint="Reference only previously declared step ids in depends_on.",
            )

        node = ProtocolNode(
            step_id=resolved_step_id,
            action=action,
            depends_on=resolved_deps,
            resources=set(resources or []),
            insertion_order=len(self._nodes),
        )
        self._nodes.append(node)
        self._node_by_id[resolved_step_id] = node
        self.sequence.append(action)
        return resolved_step_id

    def _topological_nodes(self) -> list[ProtocolNode]:
        indegree: dict[str, int] = {}
        adjacency: dict[str, set[str]] = {node.step_id: set() for node in self._nodes}

        for node in self._nodes:
            indegree[node.step_id] = len(node.depends_on)
            for dep in node.depends_on:
                adjacency[dep].add(node.step_id)

        ready = sorted(
            [node for node in self._nodes if indegree[node.step_id] == 0],
            key=lambda item: item.insertion_order,
        )
        ordered: list[ProtocolNode] = []

        while ready:
            node = ready.pop(0)
            ordered.append(node)
            for nxt in sorted(adjacency[node.step_id]):
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    ready.append(self._node_by_id[nxt])
                    ready.sort(key=lambda item: item.insertion_order)

        if len(ordered) != len(self._nodes):
            unresolved = [step for step, degree in indegree.items() if degree > 0]
            raise OrderingConstraintError(
                description="Dependency cycle detected.",
                actual_value=sorted(unresolved),
                limit_value="acyclic dependency graph",
                remediation_hint="Remove cyclic depends_on references.",
            )

        return ordered

    def _collect_containers(self) -> list[Container]:
        containers: list[Container] = []
        seen: set[int] = set()
        for action in self.sequence:
            for value in vars(action).values():
                if isinstance(value, Container):
                    marker = id(value)
                    if marker not in seen:
                        containers.append(value)
                        seen.add(marker)
        return containers

    @staticmethod
    def _restore_container_state(snapshot: list[Container], live: list[Container]) -> None:
        by_id = {container.id: container for container in live}
        for item in snapshot:
            if item.id in by_id:
                target = by_id[item.id]
                target.contents = deepcopy(item.contents)

    def dry_run(self, mode: str = "mock", science_context: Optional[dict[str, str]] = None) -> bool:
        """Validate and simulate every action deterministically.

        Parameters:
            mode: `mock` for deterministic local checks.
            science_context: Optional simulator context.

        Returns:
            True when all steps pass.

        Raises:
            PhysicsError: On any invariant violation.
        """
        if mode not in {"mock", "science"}:
            raise ValueError("dry_run mode must be 'mock' or 'science'.")

        science_context = science_context or {}
        ordered_nodes = self._topological_nodes()
        live_containers = self._collect_containers()
        checkpoint = clone_containers(live_containers)

        try:
            for node in ordered_nodes:
                before = clone_containers(live_containers)
                node.action.validate()
                node.action.execute()
                after = clone_containers(live_containers)
                assert_mass_conservation(before, after)

                if mode == "science" and isinstance(node.action, Move):
                    protocol_path = science_context.get("opentrons_protocol_path")
                    if protocol_path:
                        from .sim.registry.opentrons_sim import OT2Simulator

                        simulator = OT2Simulator()
                        observation = simulator.run(self)
                        node.action.state_observation_json = observation.to_json()
        except PhysicsError:
            self._restore_container_state(checkpoint, live_containers)
            self.is_compiled = False
            raise

        self._restore_container_state(checkpoint, live_containers)
        self.is_compiled = True
        return True

    def _serialize_value(self, value: Any) -> Any:
        if isinstance(value, Container):
            return value.id
        if isinstance(value, Quantity):
            return quantity_json(value)
        if hasattr(value, "value") and hasattr(value, "name"):
            return getattr(value, "value")
        if isinstance(value, list):
            return [self._serialize_value(item) for item in value]
        if isinstance(value, dict):
            return {key: self._serialize_value(item) for key, item in value.items()}
        return value

    def _collect_references(self) -> dict[str, list[dict[str, object]]]:
        containers = sorted(
            [container.to_reference() for container in self._collect_containers()],
            key=lambda item: str(item["id"]),
        )
        materials: list[dict[str, object]] = []
        for container in self._collect_containers():
            for matter in container.contents:
                materials.append(matter.to_reference())
        materials.sort(key=lambda item: str(item["id"]))
        return {"containers": containers, "materials": materials}

    def to_payload(self) -> dict[str, object]:
        """Return IR payload for the compiled protocol graph."""
        if not self.is_compiled:
            raise RuntimeError("Must pass dry_run() before export.")

        steps_payload = []
        for index, node in enumerate(self._topological_nodes(), start=1):
            parameters = {
                key: self._serialize_value(value)
                for key, value in vars(node.action).items()
                if key not in {"status", "state_observation_json"}
            }
            steps_payload.append(
                {
                    "step": index,
                    "step_id": node.step_id,
                    "action_type": type(node.action).__name__,
                    "parameters": parameters,
                    "depends_on": sorted(node.depends_on),
                    "resources": sorted(node.resources),
                }
            )

        deterministic_id = str(uuid5(NAMESPACE_URL, f"openatoms:{self.name}:{len(steps_payload)}"))
        payload: dict[str, object] = {
            "ir_version": IR_VERSION,
            "schema_version": IR_SCHEMA_VERSION,
            "protocol_id": deterministic_id,
            "correlation_id": deterministic_id,
            "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
            "dry_run_passed": True,
            "simulation_nodes_passed": [],
            "protocol_name": self.name,
            "steps": steps_payload,
            "references": self._collect_references(),
            "provenance": {
                "ir_hash": "0" * 64,
                "simulator_versions": {},
                "noise_seed": None,
                "validator_version": "1.1.0",
            },
        }
        payload = attach_ir_hash(payload)
        validate_ir(payload)
        return payload

    def export_json(self) -> str:
        """Export deterministic JSON IR.

        Example:
            >>> from openatoms.actions import Move
            >>> from openatoms.core import Container, Matter, Phase
            >>> from openatoms.units import Q_
            >>> s = Container(id="s", label="S", max_volume=Q_(10, "milliliter"), max_temp=Q_(100, "degC"), min_temp=Q_(0, "degC"))
            >>> d = Container(id="d", label="D", max_volume=Q_(10, "milliliter"), max_temp=Q_(100, "degC"), min_temp=Q_(0, "degC"))
            >>> s.contents.append(Matter(name="H2O", phase=Phase.LIQUID, mass=Q_(2, "gram"), volume=Q_(2, "milliliter")))
            >>> g = ProtocolGraph("x")
            >>> _ = g.add_step(Move(s, d, Q_(1, "milliliter")))
            >>> _ = g.dry_run()
            >>> '"ir_version"' in g.export_json()
            True
        """
        return json.dumps(self.to_payload(), sort_keys=True, indent=2)
