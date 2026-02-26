from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from eval.evaluate import apply_validator_repairs, evaluate_protocol
from eval.generate_protocols import generate_protocols
from eval.run_benchmark import run_benchmark


def test_benchmark_summary_is_deterministic(tmp_path: Path) -> None:
    run1 = tmp_path / "run1"
    run2 = tmp_path / "run2"

    run_benchmark(seed=123, n=50, output_dir=run1)
    run_benchmark(seed=123, n=50, output_dir=run2)

    assert (run1 / "summary.json").read_bytes() == (run2 / "summary.json").read_bytes()


def test_validators_do_not_increase_violations() -> None:
    protocols = generate_protocols(seed=99, n=40)

    baseline_violations = sum(
        int(evaluate_protocol(protocol).violating)
        for protocol in protocols
    )
    repaired_violations = sum(
        int(evaluate_protocol(apply_validator_repairs(protocol)).violating)
        for protocol in protocols
    )

    assert repaired_violations <= baseline_violations


def test_report_contains_required_fields(tmp_path: Path) -> None:
    output_dir = tmp_path / "report"
    run_benchmark(seed=7, n=12, output_dir=output_dir)
    report = (output_dir / "BENCHMARK_REPORT.md").read_text(encoding="utf-8")

    assert "- Date:" in report
    assert "- N:" in report
    assert "- Seed:" in report
    assert "- Baseline:" in report
    assert "- Schema version:" in report
    assert "- Violation definition:" in report


def test_cli_generates_artifacts(tmp_path: Path) -> None:
    output_dir = tmp_path / "cli"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "eval.run_benchmark",
            "--seed",
            "123",
            "--n",
            "20",
            "--output-dir",
            str(output_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["n"] == 20
    assert summary["seed"] == 123
    assert (output_dir / "raw_runs.jsonl").exists()
    assert (output_dir / "BENCHMARK_REPORT.md").exists()
