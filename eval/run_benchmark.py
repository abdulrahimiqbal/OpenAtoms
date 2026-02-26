from __future__ import annotations

import argparse
import json
import math
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

from openatoms.ir import get_schema_path, get_schema_version

from .baselines import NO_VALIDATION_BASELINE, apply_no_validation
from .evaluate import apply_validator_repairs, evaluate_protocol
from .generate_protocols import generate_protocols


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Return Wilson confidence interval for a binomial success rate."""
    if total <= 0:
        return (0.0, 0.0)
    p_hat = successes / total
    denom = 1 + (z * z / total)
    center = p_hat + (z * z) / (2 * total)
    margin = z * math.sqrt((p_hat * (1 - p_hat) + (z * z) / (4 * total)) / total)
    low = (center - margin) / denom
    high = (center + margin) / denom
    return (max(0.0, low), min(1.0, high))


def _git_info(repo_root: Path) -> tuple[str, str]:
    commit = "unknown"
    commit_date = date(1970, 1, 1).isoformat()
    commit_cmd = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if commit_cmd.returncode == 0:
        commit = commit_cmd.stdout.strip() or commit

    date_cmd = subprocess.run(
        ["git", "show", "-s", "--format=%cs", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if date_cmd.returncode == 0:
        parsed = date_cmd.stdout.strip()
        if parsed:
            commit_date = parsed
    return commit, commit_date


def _rounded_pair(values: tuple[float, float]) -> list[float]:
    return [round(values[0], 6), round(values[1], 6)]


def _write_report(path: Path, summary: dict[str, Any]) -> None:
    baseline = summary["baseline"]
    validated = summary["with_validators"]
    lines = [
        "# BENCHMARK REPORT",
        "",
        f"- Date: {summary['date']}",
        f"- N: {summary['n']}",
        f"- Seed: {summary['seed']}",
        f"- Schema version: {summary['schema_version']}",
        f"- Baseline: {baseline['description']}",
        f"- Violation definition: {summary['violation_definition']}",
        "",
        "## Results",
        "",
        "| Condition | Violations | Violation rate | 95% Wilson CI |",
        "| --- | ---: | ---: | --- |",
        (
            f"| baseline ({baseline['name']}) | {baseline['violations']} / {summary['n']} | "
            f"{baseline['violation_rate']:.6f} | "
            f"[{baseline['violation_rate_ci95'][0]:.6f}, {baseline['violation_rate_ci95'][1]:.6f}] |"
        ),
        (
            f"| with_validators | {validated['violations']} / {summary['n']} | "
            f"{validated['violation_rate']:.6f} | "
            f"[{validated['violation_rate_ci95'][0]:.6f}, {validated['violation_rate_ci95'][1]:.6f}] |"
        ),
        "",
        f"- Relative violation reduction: {summary['relative_violation_reduction']:.6f}",
        f"- Git commit: {summary['git_commit']}",
        "",
        "## Reproduction",
        "",
        f"`python -m eval.run_benchmark --seed {summary['seed']} --n {summary['n']}`",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_benchmark(seed: int, n: int, output_dir: Path) -> dict[str, Any]:
    protocols = generate_protocols(seed=seed, n=n)
    repo_root = Path(__file__).resolve().parents[1]
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_runs: list[dict[str, Any]] = []
    baseline_violations = 0
    validated_violations = 0

    for protocol in protocols:
        baseline_protocol = apply_no_validation(protocol)
        baseline_outcome = evaluate_protocol(baseline_protocol)

        repaired_protocol = apply_validator_repairs(protocol)
        validated_outcome = evaluate_protocol(repaired_protocol)

        baseline_violations += int(baseline_outcome.violating)
        validated_violations += int(validated_outcome.violating)
        raw_runs.append(
            {
                "baseline": baseline_outcome.to_dict(),
                "protocol": protocol,
                "repaired_protocol": repaired_protocol,
                "with_validators": validated_outcome.to_dict(),
            }
        )

    baseline_rate = baseline_violations / max(n, 1)
    validated_rate = validated_violations / max(n, 1)
    reduction = 0.0
    if baseline_rate > 0:
        reduction = (baseline_rate - validated_rate) / baseline_rate

    git_commit, commit_date = _git_info(repo_root)
    summary = {
        "baseline": {
            "name": NO_VALIDATION_BASELINE.name,
            "description": NO_VALIDATION_BASELINE.description,
            "violations": baseline_violations,
            "violation_rate": round(baseline_rate, 6),
            "violation_rate_ci95": _rounded_pair(wilson_interval(baseline_violations, n)),
        },
        "date": commit_date,
        "git_commit": git_commit,
        "n": n,
        "relative_violation_reduction": round(reduction, 6),
        "schema_path": str(get_schema_path()),
        "schema_version": get_schema_version(),
        "seed": seed,
        "violation_definition": (
            "A protocol is counted as violating when OpenAtoms dry_run raises a PhysicsError."
        ),
        "with_validators": {
            "violations": validated_violations,
            "violation_rate": round(validated_rate, 6),
            "violation_rate_ci95": _rounded_pair(wilson_interval(validated_violations, n)),
        },
    }

    raw_runs_path = output_dir / "raw_runs.jsonl"
    summary_path = output_dir / "summary.json"
    report_path = output_dir / "BENCHMARK_REPORT.md"

    with raw_runs_path.open("w", encoding="utf-8") as handle:
        for row in raw_runs:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")

    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(report_path, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic OpenAtoms benchmark.")
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--output-dir", type=Path, default=Path("eval/results"))
    args = parser.parse_args()

    summary = run_benchmark(seed=args.seed, n=args.n, output_dir=args.output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
