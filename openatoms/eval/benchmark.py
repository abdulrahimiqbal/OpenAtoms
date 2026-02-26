"""Benchmark harness for protocol-generation quality with/without OpenAtoms feedback.

Example:
    >>> from openatoms.eval.mock_llm import MockLLM
    >>> benchmark = ProtocolBenchmark()
    >>> baseline = benchmark.evaluate_baseline(MockLLM(seed=1), model="mock", n_protocols=5, seed=1)
    >>> enhanced = benchmark.evaluate_with_openatoms(MockLLM(seed=1), model="mock", n_protocols=5, seed=1)
    >>> baseline.total == 5 and enhanced.total == 5
    True
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..actions import Move, Transform
from ..core import Container, Matter, Phase
from ..dag import ProtocolGraph
from ..errors import PhysicsError
from ..sim.registry.robotics_sim import RoboticsSimulator
from ..units import Q_


@dataclass
class BenchmarkResult:
    """Aggregate benchmark metrics for one evaluation condition."""

    model: str
    condition: str
    total: int
    valid: int
    invalid: int
    violation_rate: float
    violations_by_type: dict[str, int]
    rounds_per_protocol: list[int] = field(default_factory=list)
    token_cost_estimate: float = 0.0


@dataclass
class ComparisonReport:
    """Comparison of baseline and OpenAtoms-feedback benchmark conditions."""

    baseline_violation_rate: float
    enhanced_violation_rate: float
    relative_violation_reduction: float
    chi_squared: float
    p_value: float
    cohens_h: float
    cost_per_valid_protocol: float

    def to_markdown(self) -> str:
        """Return publication-ready Markdown table."""
        return "\n".join(
            [
                "| Metric | Value |",
                "| --- | --- |",
                f"| Baseline violation rate | {self.baseline_violation_rate:.4f} |",
                f"| OpenAtoms violation rate | {self.enhanced_violation_rate:.4f} |",
                f"| Relative violation reduction | {self.relative_violation_reduction:.4f} |",
                f"| Chi-squared (df=1) | {self.chi_squared:.4f} |",
                f"| p-value | {self.p_value:.6f} |",
                f"| Cohen's h | {self.cohens_h:.4f} |",
                f"| Cost per valid protocol | {self.cost_per_valid_protocol:.2f} |",
            ]
        )


class ProtocolBenchmark:
    """Evaluate LLM protocol validity baseline vs OpenAtoms-guided correction."""

    chemistry_protocols = [
        {"id": f"chem_{i}", "domain": "chemistry", "prompt": f"Chemistry protocol {i}"}
        for i in range(1, 21)
    ]
    pipetting_protocols = [
        {"id": f"pipette_{i}", "domain": "pipetting", "prompt": f"Pipetting protocol {i}"}
        for i in range(1, 21)
    ]
    robotics_protocols = [
        {"id": f"robot_{i}", "domain": "robotics", "prompt": f"Robotics protocol {i}"}
        for i in range(1, 11)
    ]

    BENCHMARK_PROTOCOLS = chemistry_protocols + pipetting_protocols + robotics_protocols

    def _validate_generated_protocol(self, protocol: dict[str, Any]) -> tuple[bool, str | None]:
        domain = protocol.get("domain")
        actions = protocol.get("actions", [])

        if domain in {"chemistry", "pipetting"}:
            a = Container(id="A", label="A", max_volume=Q_(500, "microliter"), max_temp=Q_(120, "degC"), min_temp=Q_(-20, "degC"))
            b = Container(id="B", label="B", max_volume=Q_(500, "microliter"), max_temp=Q_(120, "degC"), min_temp=Q_(-20, "degC"))
            a.contents.append(Matter(name="water", phase=Phase.LIQUID, mass=Q_(300, "milligram"), volume=Q_(300, "microliter")))

            graph = ProtocolGraph(protocol.get("id", "benchmark_protocol"))
            for action in actions:
                if action["action"] == "move":
                    amount_ul = action.get("amount_ul", 0)
                    source = a if action.get("source") == "A" else b
                    destination = a if action.get("destination") == "A" else b
                    graph.add_step(Move(source, destination, Q_(amount_ul, "microliter")))
                elif action["action"] == "heat":
                    graph.add_step(
                        Transform(
                            target=b,
                            parameter="temperature",
                            target_value=Q_(action.get("temperature_c", 25), "degC"),
                            duration=Q_(action.get("duration_s", 10), "second"),
                        )
                    )

            try:
                graph.dry_run()
                return True, None
            except PhysicsError as exc:
                return False, exc.constraint_type

        if domain == "robotics":
            sim = RoboticsSimulator()
            for action in actions:
                if action["action"] == "grip":
                    grip = sim.check_grasp_force(
                        Q_(action.get("object_mass_kg", 0.1), "kilogram"),
                        Q_(action.get("gripper_force_n", 10), "newton"),
                        float(action.get("mu", 0.4)),
                    )
                    if not grip.stable:
                        return False, "ordering"
                elif action["action"] == "vial":
                    err = sim.check_vial_integrity(
                        action.get("material", "glass"),
                        Q_(action.get("force_n", 10), "newton"),
                        Q_(action.get("area_cm2", 2), "centimeter**2"),
                    )
                    if err is not None:
                        return False, err.constraint_type
            return True, None

        return False, "ordering"

    def evaluate_baseline(
        self,
        llm_client: Any,
        model: str,
        n_protocols: int = 50,
        seed: int = 42,
    ) -> BenchmarkResult:
        """Condition A: direct generation without OpenAtoms correction feedback."""
        rng = random.Random(seed)
        candidates = list(self.BENCHMARK_PROTOCOLS)
        rng.shuffle(candidates)
        selected = candidates[:n_protocols]

        valid = 0
        invalid = 0
        violations: dict[str, int] = {}

        for item in selected:
            generated = llm_client.generate_protocol(item, feedback=None)
            ok, violation = self._validate_generated_protocol(generated)
            if ok:
                valid += 1
            else:
                invalid += 1
                key = violation or "unknown"
                violations[key] = violations.get(key, 0) + 1

        return BenchmarkResult(
            model=model,
            condition="baseline",
            total=len(selected),
            valid=valid,
            invalid=invalid,
            violation_rate=invalid / max(len(selected), 1),
            violations_by_type=violations,
            token_cost_estimate=float(len(selected) * 800),
        )

    def evaluate_with_openatoms(
        self,
        llm_client: Any,
        model: str,
        max_correction_rounds: int = 3,
        n_protocols: int = 50,
        seed: int = 42,
    ) -> BenchmarkResult:
        """Condition B: iterative correction loop using remediation feedback."""
        rng = random.Random(seed)
        candidates = list(self.BENCHMARK_PROTOCOLS)
        rng.shuffle(candidates)
        selected = candidates[:n_protocols]

        valid = 0
        invalid = 0
        violations: dict[str, int] = {}
        rounds: list[int] = []
        token_cost = 0.0

        for item in selected:
            feedback = None
            resolved = False
            used_rounds = 0

            for round_idx in range(1, max_correction_rounds + 1):
                generated = llm_client.generate_protocol(item, feedback=feedback)
                token_cost += 900
                ok, violation = self._validate_generated_protocol(generated)
                used_rounds = round_idx
                if ok:
                    resolved = True
                    valid += 1
                    break
                feedback = {
                    "constraint_type": violation,
                    "remediation_hint": f"Fix {violation} violation in generated protocol.",
                }

            if not resolved:
                invalid += 1
                key = (feedback or {}).get("constraint_type", "unknown")
                violations[key] = violations.get(key, 0) + 1
            rounds.append(used_rounds)

        return BenchmarkResult(
            model=model,
            condition="openatoms_feedback",
            total=len(selected),
            valid=valid,
            invalid=invalid,
            violation_rate=invalid / max(len(selected), 1),
            violations_by_type=violations,
            rounds_per_protocol=rounds,
            token_cost_estimate=token_cost,
        )

    def compare(self, baseline: BenchmarkResult, enhanced: BenchmarkResult) -> ComparisonReport:
        """Compute relative impact and significance for two benchmark conditions."""
        b_invalid = baseline.invalid
        b_valid = baseline.valid
        e_invalid = enhanced.invalid
        e_valid = enhanced.valid

        total = baseline.total + enhanced.total
        if total == 0:
            raise ValueError("Cannot compare empty benchmark results.")

        row1 = b_invalid + b_valid
        row2 = e_invalid + e_valid
        col1 = b_invalid + e_invalid
        col2 = b_valid + e_valid

        expected_b_invalid = row1 * col1 / total
        expected_b_valid = row1 * col2 / total
        expected_e_invalid = row2 * col1 / total
        expected_e_valid = row2 * col2 / total

        def _safe_term(obs: float, exp: float) -> float:
            if exp <= 0:
                return 0.0
            return (obs - exp) ** 2 / exp

        chi_squared = (
            _safe_term(b_invalid, expected_b_invalid)
            + _safe_term(b_valid, expected_b_valid)
            + _safe_term(e_invalid, expected_e_invalid)
            + _safe_term(e_valid, expected_e_valid)
        )
        # For df=1: p = erfc(sqrt(chi2 / 2)).
        p_value = math.erfc(math.sqrt(max(chi_squared, 0.0) / 2.0))

        p1 = baseline.violation_rate
        p2 = enhanced.violation_rate
        cohens_h = 2 * (math.asin(math.sqrt(max(p1, 0.0))) - math.asin(math.sqrt(max(p2, 0.0))))

        reduction = 0.0
        if p1 > 0:
            reduction = (p1 - p2) / p1

        cost_per_valid = enhanced.token_cost_estimate / max(enhanced.valid, 1)

        return ComparisonReport(
            baseline_violation_rate=p1,
            enhanced_violation_rate=p2,
            relative_violation_reduction=reduction,
            chi_squared=chi_squared,
            p_value=p_value,
            cohens_h=cohens_h,
            cost_per_valid_protocol=cost_per_valid,
        )


def run_and_save(
    llm_client: Any,
    model: str,
    n_protocols: int,
    max_correction_rounds: int,
    output_json: Path,
    output_markdown: Path,
) -> tuple[BenchmarkResult, BenchmarkResult, ComparisonReport]:
    """Execute baseline/enhanced benchmark and persist report artifacts."""
    benchmark = ProtocolBenchmark()
    baseline = benchmark.evaluate_baseline(llm_client, model=model, n_protocols=n_protocols)
    enhanced = benchmark.evaluate_with_openatoms(
        llm_client,
        model=model,
        max_correction_rounds=max_correction_rounds,
        n_protocols=n_protocols,
    )
    comparison = benchmark.compare(baseline, enhanced)

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_markdown.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "baseline": asdict(baseline),
        "enhanced": asdict(enhanced),
        "comparison": asdict(comparison),
    }
    output_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    output_markdown.write_text(
        "# Benchmark Report\n\n" + comparison.to_markdown() + "\n",
        encoding="utf-8",
    )
    return baseline, enhanced, comparison
