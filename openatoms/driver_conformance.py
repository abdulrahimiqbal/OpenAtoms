"""Driver conformance kit for third-party adapter implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Type

from .adapters.base import BaseAdapter
from .exceptions import PhysicsError


@dataclass(frozen=True)
class ConformanceResult:
    """Result entry for one conformance assertion."""

    check: str
    passed: bool
    detail: str = ""


class _ConformanceDag:
    def __init__(self):
        self._dry_run_calls = 0

    def dry_run(self) -> bool:
        self._dry_run_calls += 1
        return True

    def export_json(self) -> str:
        return (
            '{"protocol_name":"Conformance","ir_version":"1.1.0","schema_version":"1.1.0",'
            '"steps":[{"step":1,"step_id":"s1","action_type":"Move","parameters":{"amount_ml":1},'
            '"depends_on":[],"resources":[]}],"references":{"containers":[],"materials":[]}}'
        )


def run_conformance(adapter_cls: Type[BaseAdapter]) -> List[ConformanceResult]:
    """Execute conformance checks against an adapter class."""
    results: List[ConformanceResult] = []
    adapter = adapter_cls()

    capabilities = adapter.discover_capabilities()
    results.append(
        ConformanceResult(
            check="capability discovery",
            passed=isinstance(capabilities, dict) and "name" in capabilities,
            detail=str(capabilities),
        )
    )

    health = adapter.health_check()
    results.append(
        ConformanceResult(
            check="health check",
            passed=isinstance(health, dict) and health.get("status") == "ok",
            detail=str(health),
        )
    )

    cfg = adapter.secure_config_schema()
    cfg_ok = isinstance(cfg, dict) and "required_env" in cfg and "optional_env" in cfg
    results.append(
        ConformanceResult(check="secure config schema", passed=cfg_ok, detail=str(cfg))
    )

    dag = _ConformanceDag()
    try:
        adapter.execute(dag)
        execute_ok = True
        detail = "execute returned successfully"
    except PhysicsError:
        execute_ok = False
        detail = "execute raised PhysicsError unexpectedly"
    except Exception as exc:  # pragma: no cover - adapter-specific branch
        execute_ok = False
        detail = f"execute raised {type(exc).__name__}: {exc}"

    results.append(ConformanceResult(check="basic execute", passed=execute_ok, detail=detail))
    results.append(
        ConformanceResult(
            check="dry_run enforcement",
            passed=dag._dry_run_calls >= 1,  # noqa: SLF001 - kit internal check
            detail=f"dry_run calls={dag._dry_run_calls}",
        )
    )

    return results

