import pytest

from openatoms.actions import Move
from openatoms.adapters.base import BaseAdapter
from openatoms.core import Container, Matter, Phase
from openatoms.dag import ProtocolGraph
from openatoms.exceptions import PolicyViolationError
from openatoms.policy import HazardApprovalPolicy
from openatoms.runner import ProtocolRunner


class _FlakyAdapter(BaseAdapter):
    def __init__(self):
        self.calls = 0

    def execute(self, dag_json):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("transient")
        return {"ok": True}

    def discover_capabilities(self):
        return {"name": "flaky"}

    def health_check(self):
        return {"status": "ok"}

    def secure_config_schema(self):
        return {"required_env": [], "optional_env": []}


def _graph(hazard=False):
    src = Container("A", max_volume_ml=100, max_temp_c=100)
    dst = Container("B", max_volume_ml=100, max_temp_c=100)
    src.contents.append(
        Matter("M", Phase.LIQUID, 10, 10, hazard_class="flammable" if hazard else "none")
    )
    graph = ProtocolGraph("Runner")
    graph.add_step(Move(src, dst, 5))
    return graph


def test_runner_retries_and_idempotency():
    adapter = _FlakyAdapter()
    runner = ProtocolRunner(adapter, max_retries=1)

    first = runner.run(_graph(), idempotency_key="abc")
    assert first["ok"] is True
    assert first["idempotent_replay"] is False
    assert adapter.calls == 2

    second = runner.run(_graph(), idempotency_key="abc")
    assert second["idempotent_replay"] is True
    assert adapter.calls == 2


def test_runner_fail_closed_policy_hook():
    runner = ProtocolRunner(
        _FlakyAdapter(),
        policy_hooks=[HazardApprovalPolicy(approved=False)],
    )
    with pytest.raises(PolicyViolationError):
        runner.run(_graph(hazard=True))
