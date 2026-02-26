from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from hypothesis import given, settings, strategies as st

from eval.evaluate import apply_validator_repairs, evaluate_protocol
from eval.generate_protocols import generate_protocol_batch
from eval.run_benchmark import run_benchmark


def _run_benchmark_cli(seed: int, n: int, suite: str, output_dir: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "eval.run_benchmark",
            "--seed",
            str(seed),
            "--n",
            str(n),
            "--suite",
            suite,
            "--outdir",
            str(output_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_benchmark_regeneration_deterministic(tmp_path: Path) -> None:
    run1 = tmp_path / "run1"
    run2 = tmp_path / "run2"

    _run_benchmark_cli(seed=123, n=200, suite="realistic", output_dir=run1)
    _run_benchmark_cli(seed=123, n=200, suite="realistic", output_dir=run2)

    assert (run1 / "summary.json").read_bytes() == (run2 / "summary.json").read_bytes()
    assert (run1 / "BENCHMARK_REPORT.md").read_bytes() == (run2 / "BENCHMARK_REPORT.md").read_bytes()
    assert (run1 / "raw_runs.jsonl").read_bytes() == (run2 / "raw_runs.jsonl").read_bytes()


def test_report_matches_summary(tmp_path: Path) -> None:
    output_dir = tmp_path / "consistency"
    run_benchmark(seed=321, n=30, suite="realistic", violation_probability=0.15, output_dir=output_dir)

    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    report = (output_dir / "BENCHMARK_REPORT.md").read_text(encoding="utf-8")

    baseline_match = re.search(
        r"\| baseline \([^)]+\) \| \d+ / \d+ \| ([0-9.]+) \| \[([0-9.]+), ([0-9.]+)\] \|",
        report,
    )
    validated_match = re.search(
        r"\| with_validators \| \d+ / \d+ \| ([0-9.]+) \| \[([0-9.]+), ([0-9.]+)\] \|",
        report,
    )

    assert baseline_match is not None
    assert validated_match is not None
    assert baseline_match.group(1) == f"{summary['baseline']['violation_rate']:.6f}"
    assert baseline_match.group(2) == f"{summary['baseline']['violation_rate_ci95'][0]:.6f}"
    assert baseline_match.group(3) == f"{summary['baseline']['violation_rate_ci95'][1]:.6f}"
    assert validated_match.group(1) == f"{summary['with_validators']['violation_rate']:.6f}"
    assert validated_match.group(2) == f"{summary['with_validators']['violation_rate_ci95'][0]:.6f}"
    assert validated_match.group(3) == f"{summary['with_validators']['violation_rate_ci95'][1]:.6f}"
    assert f"- N: {summary['n']}" in report
    assert f"- Seed: {summary['seed']}" in report
    assert f"- Suite: {summary['suite']['name']}" in report


def test_validators_do_not_increase_violations() -> None:
    batch = generate_protocol_batch(seed=99, n=40, suite="stress")
    baseline_violations = sum(int(evaluate_protocol(protocol).violating) for protocol in batch.protocols)
    repaired_violations = sum(
        int(evaluate_protocol(apply_validator_repairs(protocol)).violating) for protocol in batch.protocols
    )
    assert repaired_violations <= baseline_violations


def test_report_contains_required_stage4_fields(tmp_path: Path) -> None:
    output_dir = tmp_path / "report"
    run_benchmark(seed=7, n=12, suite="realistic", violation_probability=0.1, output_dir=output_dir)
    report = (output_dir / "BENCHMARK_REPORT.md").read_text(encoding="utf-8")

    assert "- N:" in report
    assert "- Seed:" in report
    assert "- Suite definition:" in report
    assert "- Injection probability:" in report
    assert "- Schema version:" in report
    assert "- Timestamp (UTC):" in report
    assert "- Repo commit:" in report
    assert "- Baseline:" in report
    assert "## Detection" in report
    assert "## Correction" in report


def test_cli_generates_artifacts_with_suite_metadata(tmp_path: Path) -> None:
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
            "--suite",
            "stress",
            "--violation-probability",
            "0.3",
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
    assert summary["injection_probability"] == 0.3
    assert summary["suite"]["name"] == "stress"
    assert summary["suite"]["injection_probability"] == 0.3
    assert "repo_commit" in summary
    assert "timestamp_utc" in summary
    assert (output_dir / "raw_runs.jsonl").exists()
    assert (output_dir / "BENCHMARK_REPORT.md").exists()


def test_no_absolute_paths_in_outputs(tmp_path: Path) -> None:
    output_dir = tmp_path / "paths"
    run_benchmark(seed=11, n=24, suite="realistic", output_dir=output_dir)

    summary_text = (output_dir / "summary.json").read_text(encoding="utf-8")
    report_text = (output_dir / "BENCHMARK_REPORT.md").read_text(encoding="utf-8")
    combined = summary_text + "\n" + report_text
    repo_root = str(Path(__file__).resolve().parents[1])

    assert "/home/" not in combined
    assert "C:\\" not in combined
    assert repo_root not in combined


@given(seed=st.integers(min_value=0, max_value=10_000), n=st.integers(min_value=1, max_value=12))
@settings(max_examples=20, deadline=None)
def test_fuzz_suite_property_repair_produces_nonviolating_protocol(seed: int, n: int) -> None:
    batch = generate_protocol_batch(seed=seed, n=n, suite="fuzz")
    for protocol in batch.protocols:
        repaired = apply_validator_repairs(protocol)
        assert evaluate_protocol(repaired).violating is False
