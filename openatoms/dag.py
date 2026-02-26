"""Deterministic protocol graph compilation and validation."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Union, cast

from .actions import Action, Combine, Move, Transform
from .core import Container, Matter, Phase
from .exceptions import (
    DependencyGraphError,
    OrderingViolationError,
    PhysicsError,
)
from .ir import IR_SCHEMA_VERSION, IR_VERSION, validate_protocol_payload
from .profiles import CapabilityProfile


@dataclass
class ProtocolNode:
    """One action node in the protocol dependency graph."""

    step_id: str
    action: Action
    depends_on: Set[str]
    resources: Set[str]
    insertion_order: int


class ProtocolGraph:
    """A deterministic graph of protocol actions with dependency semantics."""

    def __init__(self, name: str):
        self.name = name
        self.sequence: List[Action] = []
        self.is_compiled = False
        self._nodes: List[ProtocolNode] = []
        self._node_by_id: Dict[str, ProtocolNode] = {}

    def add_step(
        self,
        action: Action,
        *,
        step_id: Optional[str] = None,
        depends_on: Optional[List[str]] = None,
        resources: Optional[List[str]] = None,
    ) -> str:
        """Add an action step with optional DAG dependencies and resource locks."""
        resolved_step_id = step_id or f"s{len(self._nodes) + 1}"
        if resolved_step_id in self._node_by_id:
            raise DependencyGraphError(
                message=f"Duplicate step_id '{resolved_step_id}' detected.",
                details={"step_id": resolved_step_id},
            )

        if depends_on is None:
            default_deps = {self._nodes[-1].step_id} if self._nodes else set()
            resolved_deps = default_deps
        else:
            resolved_deps = {dep for dep in depends_on}

        for dep in resolved_deps:
            if dep not in self._node_by_id:
                raise DependencyGraphError(
                    message=f"Unknown dependency '{dep}' referenced by '{resolved_step_id}'.",
                    details={"step_id": resolved_step_id, "depends_on": sorted(resolved_deps)},
                )

        node = ProtocolNode(
            step_id=resolved_step_id,
            action=action,
            depends_on=resolved_deps,
            resources={r for r in (resources or [])},
            insertion_order=len(self._nodes),
        )

        self._nodes.append(node)
        self._node_by_id[resolved_step_id] = node
        self.sequence.append(action)
        return resolved_step_id

    def _topological_nodes(self) -> List[ProtocolNode]:
        """Return nodes in deterministic topological order or raise on cycles."""
        indegree: Dict[str, int] = {}
        adjacency: Dict[str, Set[str]] = {node.step_id: set() for node in self._nodes}

        for node in self._nodes:
            indegree[node.step_id] = len(node.depends_on)
            for dep in node.depends_on:
                adjacency[dep].add(node.step_id)

        ready = sorted(
            [node for node in self._nodes if indegree[node.step_id] == 0],
            key=lambda n: n.insertion_order,
        )
        ordered: List[ProtocolNode] = []

        while ready:
            node = ready.pop(0)
            ordered.append(node)
            for nxt in sorted(adjacency[node.step_id]):
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    ready.append(self._node_by_id[nxt])
                    ready.sort(key=lambda n: n.insertion_order)

        if len(ordered) != len(self._nodes):
            unresolved = [step for step, degree in indegree.items() if degree > 0]
            raise DependencyGraphError(
                message="Dependency cycle detected in protocol graph.",
                details={"unresolved_step_ids": sorted(unresolved)},
            )

        return ordered

    def _collect_containers(self) -> Set[Container]:
        containers: Set[Container] = set()
        for action in self.sequence:
            for value in vars(action).values():
                if isinstance(value, Container):
                    containers.add(value)
        return containers

    def _snapshot_container_state(self, containers: Set[Container]) -> Dict[Container, list]:
        return {container: deepcopy(container.contents) for container in containers}

    @staticmethod
    def _restore_container_state(snapshot: Dict[Container, list]) -> None:
        for container, contents in snapshot.items():
            container.contents = deepcopy(contents)

    @staticmethod
    def _simulate_move(action: Move) -> None:
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

    @staticmethod
    def _simulate_mock(action: Action) -> None:
        if isinstance(action, Move):
            ProtocolGraph._simulate_move(action)
        elif isinstance(action, Transform):
            if action.parameter == "temperature_c":
                for matter in action.target.contents:
                    matter.temp_c = action.target_value

    @staticmethod
    def _simulate_science(action: Action, science_context: Dict[str, str]) -> None:
        ProtocolGraph._simulate_mock(action)

        if isinstance(action, Transform) and action.parameter == "temperature_c":
            from .sim.registry.kinetics_sim import VirtualReactor

            reactor = VirtualReactor()
            result = reactor.simulate_hydrogen_oxygen_combustion(
                initial_temp_k=action.target_value + 273.15,
                residence_time_s=max(action.duration_s / 1000.0, 0.001),
            )
            action.state_observation_json = result["state_observation_json"]

        if isinstance(action, Move):
            protocol_path = science_context.get("opentrons_protocol_path")
            if protocol_path:
                from .sim.registry.opentrons_sim import OpentronsSimValidator

                validator = OpentronsSimValidator()
                validation = validator.validate_protocol(protocol_path)
                action.state_observation_json = validation["state_observation_json"]
                simulation_error = validation.get("error")
                if simulation_error is not None:
                    raise simulation_error

    @staticmethod
    def _enforce_ordering_rules(action: Action) -> None:
        if isinstance(action, Move) and action.amount_ml <= 0:
            raise OrderingViolationError(
                message="Move amount must be greater than zero.",
                details={"amount_ml": action.amount_ml},
            )
        if isinstance(action, Combine) and action.duration_s <= 0:
            raise OrderingViolationError(
                message="Combine duration must be greater than zero seconds.",
                details={"duration_s": action.duration_s},
            )

    @staticmethod
    def _resolve_profile(
        capability_profile: Optional[Union[CapabilityProfile, Dict[str, Any]]],
    ) -> Optional[CapabilityProfile]:
        if capability_profile is None:
            return None
        if isinstance(capability_profile, CapabilityProfile):
            return capability_profile
        profile_dict = cast(Dict[str, Any], capability_profile)
        return CapabilityProfile.from_iterables(
            name=str(profile_dict.get("name", "target")),
            allowed_actions=[
                str(value) for value in cast(List[Any], profile_dict.get("allowed_actions", []))
            ],
            blocked_hazard_classes=[
                str(value)
                for value in cast(
                    List[Any], profile_dict.get("blocked_hazard_classes", [])
                )
            ],
            max_steps=int(profile_dict.get("max_steps", 200)),
            max_move_ml=float(profile_dict.get("max_move_ml", 1000.0)),
            max_temperature_c=float(profile_dict.get("max_temperature_c", 300.0)),
        )

    @staticmethod
    def _enforce_capability_profile(action: Action, profile: CapabilityProfile) -> None:
        action_name = type(action).__name__
        profile.validate_action(action_name)

        if isinstance(action, Move) and action.amount_ml > profile.max_move_ml:
            raise OrderingViolationError(
                message=(
                    f"Move amount {action.amount_ml}mL exceeds capability bound "
                    f"{profile.max_move_ml}mL."
                ),
                details={"capability_profile": profile.name, "max_move_ml": profile.max_move_ml},
            )

        if isinstance(action, Transform) and action.parameter == "temperature_c":
            if action.target_value > profile.max_temperature_c:
                raise OrderingViolationError(
                    message=(
                        f"Target temperature {action.target_value}C exceeds capability bound "
                        f"{profile.max_temperature_c}C."
                    ),
                    details={
                        "capability_profile": profile.name,
                        "max_temperature_c": profile.max_temperature_c,
                    },
                )

        if profile.blocked_hazard_classes:
            for matter in action.__dict__.values():
                if isinstance(matter, Container):
                    blocked = matter.hazard_classes.intersection(profile.blocked_hazard_classes)
                    if blocked:
                        raise OrderingViolationError(
                            message="Capability profile blocks hazardous container contents.",
                            details={
                                "capability_profile": profile.name,
                                "container": matter.name,
                                "blocked_hazard_classes": sorted(blocked),
                            },
                        )

    def dry_run(
        self,
        mode: str = "mock",
        science_context: Optional[Dict[str, str]] = None,
        capability_profile: Optional[Union[CapabilityProfile, Dict[str, Any]]] = None,
    ) -> bool:
        """Validate and simulate every step before physical execution.

        On failures, all involved containers are restored to their pre-run state.
        """
        mode_name = mode.strip().lower()
        if mode_name not in {"mock", "science"}:
            raise ValueError("dry_run mode must be either 'mock' or 'science'.")

        profile = self._resolve_profile(capability_profile)
        science_context = science_context or {}
        ordered_nodes = self._topological_nodes()
        if profile and len(ordered_nodes) > profile.max_steps:
            raise OrderingViolationError(
                message=(
                    f"Protocol has {len(ordered_nodes)} steps, exceeding max "
                    f"{profile.max_steps} for '{profile.name}'."
                ),
                details={
                    "capability_profile": profile.name,
                    "step_count": len(ordered_nodes),
                    "max_steps": profile.max_steps,
                },
            )

        container_snapshot = self._snapshot_container_state(self._collect_containers())
        print(f"--- Starting Dry Run for Protocol: {self.name} ---")
        for step_index, node in enumerate(ordered_nodes):
            action = node.action
            try:
                self._enforce_ordering_rules(action)
                if profile:
                    self._enforce_capability_profile(action, profile)
                action.validate()

                if mode_name == "science":
                    self._simulate_science(action, science_context)
                else:
                    self._simulate_mock(action)
                print(
                    f"[✓] Step {step_index + 1} ({node.step_id}) Validated ({mode_name}): "
                    f"{type(action).__name__}"
                )
            except PhysicsError as exc:
                self._restore_container_state(container_snapshot)
                self.is_compiled = False
                print(f"\n[X] LINTER FATAL ERROR at Step {step_index + 1}:")
                print(exc.to_agent_payload())
                raise exc
        # Dry runs are deterministic checks and must not leave mutated state behind.
        self._restore_container_state(container_snapshot)
        self.is_compiled = True
        return True

    def _collect_references(self) -> Dict[str, List[Dict[str, object]]]:
        containers = sorted(
            [container.to_reference() for container in self._collect_containers()],
            key=lambda item: str(item["id"]),
        )
        materials = []
        for container in self._collect_containers():
            for matter in container.contents:
                materials.append(matter.to_reference())
        materials.sort(key=lambda item: str(item["id"]))
        return {"containers": containers, "materials": materials}

    def to_payload(self) -> Dict[str, object]:
        if not self.is_compiled:
            raise RuntimeError("Must pass dry_run() first.")

        steps_payload = []
        for index, node in enumerate(self._topological_nodes(), start=1):
            action = node.action
            parameters = {
                key: value.name if hasattr(value, "name") else value
                for key, value in vars(action).items()
                if key != "status"
            }
            steps_payload.append(
                {
                    "step": index,
                    "step_id": node.step_id,
                    "action_type": type(action).__name__,
                    "parameters": parameters,
                    "depends_on": sorted(node.depends_on),
                    "resources": sorted(node.resources),
                }
            )

        payload: Dict[str, object] = {
            "protocol_name": self.name,
            "ir_version": IR_VERSION,
            "schema_version": IR_SCHEMA_VERSION,
            "error_contract_version": PhysicsError.ERROR_CONTRACT_VERSION,
            "steps": steps_payload,
            "references": self._collect_references(),
        }
        validate_protocol_payload(payload)
        return payload

    def export_json(self) -> str:
        """Export compiled protocol as deterministic JSON payload."""
        payload = self.to_payload()
        return json.dumps(payload, indent=2, sort_keys=True)
