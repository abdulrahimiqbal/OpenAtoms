from __future__ import annotations

from pathlib import Path

from openatoms import create_bundle

from ._bundle_test_utils import build_minimal_protocol


def test_bundle_redacts_agent_trace_secrets(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    secret_value = "sk-1234567890abcdefghijklmnopqrstuvwxyz"

    create_bundle(
        output_path=bundle_dir,
        protocol=build_minimal_protocol("redaction_demo"),
        deterministic=True,
        agent_tool_calls=[
            {
                "tool": "http",
                "headers": {"Authorization": f"Bearer {secret_value}"},
                "api_key": "abcd1234secret",
            }
        ],
    )

    trace_path = bundle_dir / "agent" / "tool_calls.jsonl"
    trace = trace_path.read_text(encoding="utf-8")

    assert secret_value not in trace
    assert "abcd1234secret" not in trace
    assert "[REDACTED]" in trace
