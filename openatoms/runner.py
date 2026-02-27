"""Runner utilities that connect DAGs to adapters with policy and provenance."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .adapters import BaseAdapter
from .exceptions import PhysicsError, PolicyViolationError
from .policy import PolicyHook, SafetyProfile
from .provenance import build_provenance, new_run_context
from .sim.harness import SimulationHarness


class ProtocolRunner:
    """Execute a ProtocolGraph with adapter retries, policy hooks, and provenance."""

    def __init__(
        self,
        adapter: BaseAdapter,
        *,
        max_retries: int = 0,
        fail_closed: bool = True,
        policy_hooks: Optional[List[PolicyHook]] = None,
        safety_profile: Optional[SafetyProfile] = None,
        simulation_harness: Optional[SimulationHarness] = None,
        seed: int = 0,
        simulator_version: str = "mock-1.0.0",
    ):
        self.adapter = adapter
        self.max_retries = max(0, int(max_retries))
        self.fail_closed = fail_closed
        self.policy_hooks = list(policy_hooks or [])
        self.safety_profile = safety_profile or SafetyProfile()
        self.simulation_harness = (
            simulation_harness
            if simulation_harness is not None
            else SimulationHarness(simulator_version=simulator_version)
        )
        self.seed = seed
        self.simulator_version = simulator_version
        self._idempotency_cache: Dict[str, Dict[str, Any]] = {}

    def run(self, dag: Any, *, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """Run a DAG and return adapter output enriched with provenance metadata."""
        if idempotency_key and idempotency_key in self._idempotency_cache:
            cached = dict(self._idempotency_cache[idempotency_key])
            cached["idempotent_replay"] = True
            return cached

        run_context = new_run_context(seed=self.seed, simulator_version=self.simulator_version)
        policy_context = {
            "run_id": run_context.run_id,
            "correlation_id": run_context.correlation_id,
            "safety_profile": self.safety_profile.name,
        }

        for hook in self.policy_hooks:
            hook.before_run(dag=dag, context=policy_context)

        dag_sequence = dag.sequence if hasattr(dag, "sequence") else None
        if (
            isinstance(dag_sequence, list)
            and len(dag_sequence) > self.safety_profile.max_actions_per_run
        ):
            raise PolicyViolationError(
                message="Run blocked by safety profile action limit.",
                details={
                    "max_actions_per_run": self.safety_profile.max_actions_per_run,
                    "requested_actions": len(dag_sequence),
                },
            )

        simulation_gate = None
        if self.simulation_harness is not None:
            dag.dry_run()
            simulation_gate = self.simulation_harness.run(dag=dag, run_context=run_context)
            if simulation_gate["status"] == "failed":
                raise PhysicsError(
                    error_code="SIM_002",
                    constraint_type="ordering",
                    description="Simulation gate failed; execution blocked.",
                    actual_value=simulation_gate["observation"],
                    limit_value="status=ok",
                    remediation_hint=(
                        "Adjust protocol parameters until simulation gate returns "
                        "status=ok."
                    ),
                )

        last_error: Optional[Exception] = None
        effective_retries = min(self.max_retries, self.safety_profile.max_retries)
        for attempt in range(effective_retries + 1):
            try:
                adapter_result = self.adapter.execute(dag)
                if not hasattr(dag, "is_compiled") or not dag.is_compiled:
                    dag.dry_run()
                payload = json.loads(dag.export_json())
                provenance = build_provenance(
                    payload=payload,
                    run_context=run_context,
                    adapter_name=type(self.adapter).__name__,
                    outcome="ok",
                )
                merged = dict(adapter_result)
                merged["provenance"] = provenance
                if simulation_gate is not None:
                    merged["simulation_gate"] = simulation_gate
                merged["idempotent_replay"] = False

                for hook in self.policy_hooks:
                    hook.after_run(dag=dag, result=merged, context=policy_context)

                if idempotency_key:
                    self._idempotency_cache[idempotency_key] = dict(merged)
                return merged
            except PhysicsError as exc:
                exc.correlation_id = run_context.correlation_id
                raise
            except Exception as exc:  # pragma: no cover - fail-closed branch
                last_error = exc
                if attempt >= effective_retries:
                    if self.fail_closed:
                        raise
                    return {
                        "status": "failed",
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                        "correlation_id": run_context.correlation_id,
                    }

        if last_error is not None:  # pragma: no cover - defensive
            raise last_error
        raise RuntimeError("Execution loop exited unexpectedly.")
