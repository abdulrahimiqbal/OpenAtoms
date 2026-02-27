"""Stable public API contract for OpenAtoms user/agent integrations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Literal, Mapping, Sequence, cast

from .actions import Action
from .bundle import (
    BUNDLE_VERSION,
    BundleError,
    BundleReplayReport,
    BundleVerificationReport,
    create_bundle,
    replay_bundle,
    sign_bundle,
    verify_bundle,
    verify_signature,
)
from .core import Container
from .dag import ProtocolGraph
from .errors import SimulationDependencyError
from .ir import IRValidationError, canonical_json, ir_hash, validate_ir
from .sim.registry import OT2Simulator, RoboticsSimulator, VirtualReactor
from .sim.types import Pose
from .units import Q_


@dataclass(frozen=True)
class ProtocolState:
    """State envelope for protocol construction."""

    containers: tuple[Container, ...]


@dataclass(frozen=True)
class SimulatorInvocation:
    """Outcome envelope for optional simulator invocation."""

    simulator: Literal["opentrons", "cantera", "mujoco"]
    status: Literal["ok", "skipped"]
    payload: Mapping[str, Any]
    reason: str | None = None


def create_protocol_state(containers: Iterable[Container]) -> ProtocolState:
    """Create a validated protocol state envelope from containers."""
    resolved = tuple(containers)
    ids = [container.id for container in resolved]
    if len(ids) != len(set(ids)):
        raise ValueError("Protocol state contains duplicate container ids.")
    return ProtocolState(containers=resolved)


def _action_container_ids(action: Action) -> set[str]:
    ids: set[str] = set()
    for value in vars(action).values():
        if isinstance(value, Container):
            ids.add(value.id)
    return ids


def build_protocol(
    name: str,
    actions: Sequence[Action],
    *,
    state: ProtocolState | None = None,
) -> ProtocolGraph:
    """Build a protocol graph from actions and optional explicit state."""
    if not name.strip():
        raise ValueError("Protocol name must be non-empty.")
    graph = ProtocolGraph(name)
    if state is not None:
        declared = {container.id for container in state.containers}
        used = {
            container_id
            for action in actions
            for container_id in _action_container_ids(action)
        }
        unknown = sorted(used - declared)
        if unknown:
            raise ValueError(
                f"Action references container ids not present in state: {', '.join(unknown)}"
            )
    for action in actions:
        graph.add_step(action)
    return graph


def run_dry_run(
    protocol: ProtocolGraph,
    *,
    mode: Literal["mock", "science"] = "mock",
) -> bool:
    """Run deterministic dry-run safety checks for a protocol graph."""
    return cast(bool, protocol.dry_run(mode=mode))


def compile_protocol(
    protocol: ProtocolGraph,
    *,
    run_dry_run_gate: bool = True,
    mode: Literal["mock", "science"] = "mock",
) -> dict[str, Any]:
    """Compile protocol to IR payload, optionally running dry-run first."""
    if run_dry_run_gate and not protocol.is_compiled:
        run_dry_run(protocol, mode=mode)
    payload = cast(dict[str, Any], protocol.to_payload())
    validate_protocol_ir(payload, check_invariants=True)
    return payload


def serialize_ir(
    protocol: ProtocolGraph,
    *,
    run_dry_run_gate: bool = True,
    mode: Literal["mock", "science"] = "mock",
) -> str:
    """Serialize protocol to deterministic canonical IR JSON."""
    payload = compile_protocol(protocol, run_dry_run_gate=run_dry_run_gate, mode=mode)
    return canonical_json(payload)


def _expected_ir_hash(payload: Mapping[str, Any]) -> str:
    stripped = dict(payload)
    provenance = dict(stripped.get("provenance", {}))
    provenance["ir_hash"] = ""
    stripped["provenance"] = provenance
    return ir_hash(stripped)


def validate_protocol_ir(
    payload: Mapping[str, Any],
    *,
    check_invariants: bool = True,
) -> dict[str, Any]:
    """Validate IR payload against schema and deterministic invariants."""
    validated = validate_ir(dict(payload))
    if not check_invariants:
        return validated

    steps = validated.get("steps")
    if not isinstance(steps, list):
        raise IRValidationError("IR_INVARIANT", "IR payload steps must be a list.")

    step_ids: list[str] = []
    for expected_index, step in enumerate(steps, start=1):
        if step.get("step") != expected_index:
            raise IRValidationError(
                "IR_INVARIANT",
                f"IR steps must be contiguous and start at 1; found step={step.get('step')}.",
            )
        step_id = step.get("step_id")
        if not isinstance(step_id, str):
            raise IRValidationError("IR_INVARIANT", "Each IR step must define a string step_id.")
        step_ids.append(step_id)
        depends_on = step.get("depends_on", [])
        if not isinstance(depends_on, list) or not all(isinstance(dep, str) for dep in depends_on):
            raise IRValidationError("IR_INVARIANT", "IR depends_on must be a list of step ids.")
        if any(dep not in step_ids for dep in depends_on):
            raise IRValidationError(
                "IR_INVARIANT",
                f"IR step {step_id} depends on undefined predecessor step(s).",
            )

    if len(step_ids) != len(set(step_ids)):
        raise IRValidationError("IR_INVARIANT", "IR step_id values must be unique.")

    expected_hash = _expected_ir_hash(validated)
    actual_hash = str(validated.get("provenance", {}).get("ir_hash", ""))
    if actual_hash != expected_hash:
        raise IRValidationError(
            "IR_INVARIANT",
            "IR provenance hash does not match canonical payload hash.",
        )

    return validated


def invoke_optional_simulator(
    protocol: ProtocolGraph,
    *,
    simulator: Literal["opentrons", "cantera", "mujoco"],
) -> SimulatorInvocation:
    """Invoke optional simulator backend and return a normalized result envelope."""
    try:
        if simulator == "opentrons":
            observation = OT2Simulator().run(protocol)
            return SimulatorInvocation(
                simulator=simulator,
                status="ok",
                payload=observation.to_dict(),
            )
        if simulator == "cantera":
            output = VirtualReactor().simulate_hydrogen_oxygen_combustion(
                initial_temp_k=900.0,
                residence_time_s=0.02,
            )
            trajectory = output["trajectory"]  # type: ignore[assignment]
            return SimulatorInvocation(
                simulator=simulator,
                status="ok",
                payload={
                    "state_observation_json": output["state_observation_json"],
                    "trajectory_points": len(trajectory.times_s),  # type: ignore[union-attr]
                    "check_type": "validated_simulation",
                    "solver_rtol": trajectory.solver_rtol,  # type: ignore[union-attr]
                    "solver_atol": trajectory.solver_atol,  # type: ignore[union-attr]
                    "mechanism_file": trajectory.mechanism_file,  # type: ignore[union-attr]
                    "mechanism_hash": trajectory.mechanism_hash,  # type: ignore[union-attr]
                    "cantera_version": trajectory.cantera_version,  # type: ignore[union-attr]
                    "integrator": trajectory.integrator,  # type: ignore[union-attr]
                },
            )
        trajectory = RoboticsSimulator().simulate_arm_trajectory(
            waypoints=[Pose(x_m=0.10, y_m=0.10, z_m=0.20)],
            payload_mass=Q_(0.10, "kilogram"),
            mode="mujoco",
        )
        return SimulatorInvocation(
            simulator=simulator,
            status="ok",
            payload=asdict(trajectory),
        )
    except SimulationDependencyError as exc:
        return SimulatorInvocation(
            simulator=simulator,
            status="skipped",
            payload={"error_code": exc.error_code, "message": str(exc)},
            reason=exc.remediation_hint,
        )


def protocol_hash(payload: Mapping[str, Any]) -> str:
    """Return deterministic SHA-256 hash for an IR payload."""
    return ir_hash(dict(payload))


def protocol_provenance(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return deterministic provenance envelope for an IR payload."""
    resolved = dict(payload)
    return {
        "ir_hash": protocol_hash(resolved),
        "ir_version": resolved.get("ir_version"),
        "schema_version": resolved.get("schema_version"),
        "step_count": len(resolved.get("steps", [])),
    }


__all__ = [
    "BUNDLE_VERSION",
    "BundleError",
    "BundleReplayReport",
    "BundleVerificationReport",
    "ProtocolState",
    "SimulatorInvocation",
    "build_protocol",
    "compile_protocol",
    "create_bundle",
    "create_protocol_state",
    "invoke_optional_simulator",
    "protocol_hash",
    "protocol_provenance",
    "replay_bundle",
    "run_dry_run",
    "serialize_ir",
    "sign_bundle",
    "validate_protocol_ir",
    "verify_bundle",
    "verify_signature",
]
