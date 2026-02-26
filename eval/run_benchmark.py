from __future__ import annotations

import argparse
import json
import math
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

from openatoms.ir import schema_resource_name, schema_version

from .baselines import NO_VALIDATION_BASELINE, apply_no_validation
from .evaluate import apply_validator_repairs, evaluate_protocol, intent_proxy_preserved
from .generate_protocols import SUITES, generate_protocol_batch


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


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _write_report(path: Path, summary: dict[str, Any]) -> None:
    baseline = summary["baseline"]
    validated = summary["with_validators"]
    detection = summary["detection"]
    correction = summary["correction"]
    lines = [
        "# BENCHMARK REPORT",
        "",
        f"- Date: {summary['date']}",
        f"- N: {summary['n']}",
        f"- Seed: {summary['seed']}",
        f"- Suite: {summary['suite']['name']}",
        f"- Suite definition: {summary['suite']['description']}",
        f"- Injection probability: {summary['suite']['injection_probability']}",
        f"- Injection method: {summary['suite']['injection_method']}",
        f"- Schema version: {summary['schema_version']}",
        f"- Schema resource: {summary['schema_resource']}",
        f"- Baseline: {baseline['description']}",
        f"- Violation definition: {summary['violation_definition']}",
        "",
        "## Violation Rates",
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
        "## Detection",
        "",
        f"- TP: {detection['tp']}",
        f"- FP: {detection['fp']}",
        f"- FN: {detection['fn']}",
        f"- TN: {detection['tn']}",
        f"- TP rate: {detection['tp_rate']:.6f} (95% CI [{detection['tp_rate_ci95'][0]:.6f}, {detection['tp_rate_ci95'][1]:.6f}])",
        f"- FP rate: {detection['fp_rate']:.6f} (95% CI [{detection['fp_rate_ci95'][0]:.6f}, {detection['fp_rate_ci95'][1]:.6f}])",
        "",
        "## Correction",
        "",
        f"- Attempts: {correction['attempts']}",
        f"- Successful (valid + intent-preserving): {correction['successes']}",
        f"- Success rate: {correction['success_rate']:.6f} (95% CI [{correction['success_rate_ci95'][0]:.6f}, {correction['success_rate_ci95'][1]:.6f}])",
        f"- Intent-preservation rate: {correction['intent_preservation_rate']:.6f} (95% CI [{correction['intent_preservation_rate_ci95'][0]:.6f}, {correction['intent_preservation_rate_ci95'][1]:.6f}])",
        "",
        f"- Relative violation reduction: {summary['relative_violation_reduction']:.6f}",
        f"- Git commit: {summary['git_commit']}",
        "",
        "## Reproduction",
        "",
        (
            "`python -m eval.run_benchmark "
            f"--seed {summary['seed']} --n {summary['n']} "
            f"--suite {summary['suite']['name']} "
            f"--violation-probability {summary['suite']['injection_probability']}`"
        ),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_benchmark(
    seed: int,
    n: int,
    output_dir: Path,
    suite: str = "realistic",
    violation_probability: float | None = None,
) -> dict[str, Any]:
    generation = generate_protocol_batch(
        seed=seed,
        n=n,
        suite=suite,
        violation_probability=violation_probability,
    )
    protocols = generation.protocols
    repo_root = Path(__file__).resolve().parents[1]
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_runs: list[dict[str, Any]] = []
    baseline_violations = 0
    validated_violations = 0
    detection_tp = 0
    detection_fp = 0
    detection_fn = 0
    detection_tn = 0
    correction_attempts = 0
    correction_successes = 0
    intent_preserved_count = 0

    for protocol in protocols:
        baseline_protocol = apply_no_validation(protocol)
        baseline_outcome = evaluate_protocol(baseline_protocol)

        repaired_protocol = apply_validator_repairs(protocol)
        validated_outcome = evaluate_protocol(repaired_protocol)
        intent_ok = intent_proxy_preserved(protocol, repaired_protocol)

        expected_violation = bool(protocol.get("expected_violation", False))
        baseline_is_violation = bool(baseline_outcome.violating)
        baseline_violations += int(baseline_is_violation)
        validated_violations += int(validated_outcome.violating)

        if expected_violation and baseline_is_violation:
            detection_tp += 1
        elif expected_violation and not baseline_is_violation:
            detection_fn += 1
        elif (not expected_violation) and baseline_is_violation:
            detection_fp += 1
        else:
            detection_tn += 1

        if expected_violation:
            correction_attempts += 1
            if (not validated_outcome.violating) and intent_ok:
                correction_successes += 1
        if intent_ok:
            intent_preserved_count += 1

        raw_runs.append(
            {
                "baseline": baseline_outcome.to_dict(),
                "expected_violation": expected_violation,
                "injected_violation_type": protocol.get("injected_violation_type"),
                "intent_proxy_preserved": intent_ok,
                "protocol": protocol,
                "repaired_protocol": repaired_protocol,
                "with_validators": validated_outcome.to_dict(),
            }
        )

    baseline_rate = _safe_rate(baseline_violations, n)
    validated_rate = _safe_rate(validated_violations, n)
    reduction = 0.0
    if baseline_rate > 0:
        reduction = (baseline_rate - validated_rate) / baseline_rate

    expected_total = detection_tp + detection_fn
    expected_non_total = detection_fp + detection_tn
    tp_rate = _safe_rate(detection_tp, expected_total)
    fp_rate = _safe_rate(detection_fp, expected_non_total)
    correction_success_rate = _safe_rate(correction_successes, correction_attempts)
    intent_preservation_rate = _safe_rate(intent_preserved_count, n)

    git_commit, commit_date = _git_info(repo_root)
    summary = {
        "baseline": {
            "description": NO_VALIDATION_BASELINE.description,
            "name": NO_VALIDATION_BASELINE.name,
            "violations": baseline_violations,
            "violation_rate": round(baseline_rate, 6),
            "violation_rate_ci95": _rounded_pair(wilson_interval(baseline_violations, n)),
        },
        "correction": {
            "attempts": correction_attempts,
            "intent_preservation_rate": round(intent_preservation_rate, 6),
            "intent_preservation_rate_ci95": _rounded_pair(wilson_interval(intent_preserved_count, n)),
            "success_rate": round(correction_success_rate, 6),
            "success_rate_ci95": _rounded_pair(wilson_interval(correction_successes, correction_attempts)),
            "successes": correction_successes,
        },
        "date": commit_date,
        "detection": {
            "fn": detection_fn,
            "fp": detection_fp,
            "fp_rate": round(fp_rate, 6),
            "fp_rate_ci95": _rounded_pair(wilson_interval(detection_fp, expected_non_total)),
            "tn": detection_tn,
            "tp": detection_tp,
            "tp_rate": round(tp_rate, 6),
            "tp_rate_ci95": _rounded_pair(wilson_interval(detection_tp, expected_total)),
        },
        "git_commit": git_commit,
        "n": n,
        "relative_violation_reduction": round(reduction, 6),
        "schema_resource": schema_resource_name(),
        "schema_version": schema_version(),
        "seed": seed,
        "suite": {
            "description": generation.suite_description,
            "injection_method": generation.injection_method,
            "injection_probability": generation.violation_probability,
            "name": generation.suite_name,
        },
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
    parser.add_argument("--suite", choices=sorted(SUITES.keys()), default="realistic")
    parser.add_argument("--violation-probability", type=float, default=None)
    parser.add_argument("--output-dir", type=Path, default=Path("eval/results"))
    args = parser.parse_args()

    summary = run_benchmark(
        seed=args.seed,
        n=args.n,
        suite=args.suite,
        violation_probability=args.violation_probability,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
