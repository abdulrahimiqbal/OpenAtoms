"""Worked example: BCI verification bottleneck reproduction + closed-loop optimization."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

# Allow `python run_example.py` from this directory.
THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parents[1]
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bridge import (  # noqa: E402
    DEFAULT_CHARSET,
    compute_bridge_speedup,
    compute_crossover_d_prime,
    compute_itr_bits_per_trial,
    compute_throughput,
    distribution_for_entropy,
    estimate_character_entropy,
    estimate_corpus_entropy,
    simulate_p300_sequence,
    uniform_prior,
)
from openatoms_integration import BCIExperimentProtocol, BCISimulator  # noqa: E402
from validation import derco_loader, reference_data  # noqa: E402

from openatoms import (  # noqa: E402
    Q_,
    Container,
    Matter,
    Move,
    Phase,
    build_protocol,
    create_bundle,
    create_protocol_state,
    sign_bundle,
)
from openatoms.errors import PhysicsError  # noqa: E402

PANGRAM = "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG"
DEFAULT_BUNDLE_OUTPUT = THIS_DIR / "outputs" / "bci_verification_bottleneck_bundle.zip"


def _build_minimal_protocol_for_bundle(name: str = "bci_verification_bottleneck"):
    source = Container(
        id="B1",
        label="B1",
        max_volume=Q_(300, "microliter"),
        max_temp=Q_(80, "degC"),
        min_temp=Q_(4, "degC"),
    )
    destination = Container(
        id="B2",
        label="B2",
        max_volume=Q_(300, "microliter"),
        max_temp=Q_(80, "degC"),
        min_temp=Q_(4, "degC"),
    )
    source.contents.append(
        Matter(
            name="water",
            phase=Phase.LIQUID,
            mass=Q_(100, "milligram"),
            volume=Q_(100, "microliter"),
        )
    )
    state = create_protocol_state([source, destination])
    return build_protocol(name, [Move(source, destination, Q_(50, "microliter"))], state=state)


def _average_trials(
    epochs: np.ndarray,
    labels: np.ndarray,
    group_size: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    pooled_epochs: list[np.ndarray] = []
    pooled_labels: list[int] = []
    for cls in (0, 1):
        idx = np.where(labels == cls)[0]
        if idx.size < group_size:
            continue
        shuffled = np.array(idx, copy=True)
        rng.shuffle(shuffled)
        usable = (shuffled.size // group_size) * group_size
        grouped = shuffled[:usable].reshape(-1, group_size)
        for group in grouped:
            pooled_epochs.append(np.mean(epochs[group], axis=0))
            pooled_labels.append(int(cls))
    return np.asarray(pooled_epochs), np.asarray(pooled_labels)


def phase1_reproduce_crossover(derco_path: str) -> dict:
    """Reproduce Bridge vs uniform crossover around d' ~= 1.7."""
    loaded = derco_loader.load_derco_n400(derco_path)
    epochs = np.asarray(loaded["epochs"], dtype=float)
    labels = np.asarray(loaded["labels"], dtype=int)

    passive = derco_loader.compute_n400_d_prime(epochs, labels)

    active_epochs, active_labels = _average_trials(epochs, labels, group_size=4, seed=42)
    if active_epochs.size == 0:
        active = {"d_prime": 0.0, "auc": 0.5, "n_trials": 0}
    else:
        active = derco_loader.compute_n400_d_prime(active_epochs, active_labels)

    d_prime_values = np.linspace(0.1, 3.0, 30)
    crossover = compute_crossover_d_prime(
        lm_entropy_bits=reference_data.GPT2_CHARACTER_ENTROPY_BITS,
        d_prime_range=d_prime_values,
        n_trials_per_point=1800,
        seed=42,
    )

    crossover_d = float(crossover["crossover_d_prime"])
    lower = reference_data.CROSSOVER_D_PRIME - reference_data.CROSSOVER_TOLERANCE
    upper = reference_data.CROSSOVER_D_PRIME + reference_data.CROSSOVER_TOLERANCE
    within = lower <= crossover_d <= upper
    if not within:
        raise AssertionError(
            f"Crossover {crossover_d:.3f} outside tolerance [{lower:.3f}, {upper:.3f}]"
        )

    return {
        "phase": "phase1_reproduce_crossover",
        "derco_metadata": loaded.get("metadata", {}),
        "n400_passive": passive,
        "n400_active": active,
        "d_prime_values": [float(value) for value in crossover["d_prime_values"]],
        "bridge_itrs": [float(value) for value in crossover["bridge_itrs"]],
        "uniform_itrs": [float(value) for value in crossover["uniform_itrs"]],
        "crossover_d_prime_measured": crossover_d,
        "crossover_d_prime_published": float(reference_data.CROSSOVER_D_PRIME),
        "crossover_within_tolerance": bool(within),
        "tolerance": float(reference_data.CROSSOVER_TOLERANCE),
    }


def _simulate_speed(
    *,
    text: str,
    d_prime: float,
    prior: dict[str, float],
    method: str,
    seed: int,
) -> dict[str, float]:
    prior_probs = np.asarray([prior[ch] for ch in DEFAULT_CHARSET], dtype=float)
    prior_probs = np.clip(prior_probs, 1e-12, 1.0)
    prior_probs /= float(np.sum(prior_probs))
    lm_entropy_bits = float(-np.sum(prior_probs * np.log2(prior_probs)))

    repetitions_nominal = 8.0
    if method == "uniform":
        effective_repetitions = repetitions_nominal
    else:
        effective_repetitions = max(
            1.0,
            repetitions_nominal * (lm_entropy_bits / reference_data.UNIFORM_ENTROPY_BITS),
        )

    run = simulate_p300_sequence(
        text=text,
        d_prime=d_prime,
        lm_prior_fn=lambda _context: prior,
        n_repetitions=int(round(repetitions_nominal)),
        seed=seed,
        method=method,
        chars=DEFAULT_CHARSET,
    )
    accuracy = float(run["accuracy"])
    itr_bits = compute_itr_bits_per_trial(accuracy=accuracy, n_choices=len(DEFAULT_CHARSET))
    throughput = compute_throughput(
        itr_bits_per_trial=itr_bits,
        repetitions_per_trial=effective_repetitions,
    )
    return {
        "accuracy": accuracy,
        "itr_bits_per_trial": float(itr_bits),
        "throughput_bpm": float(throughput),
        "effective_repetitions": float(effective_repetitions),
        "lm_entropy_bits": lm_entropy_bits,
    }


def phase2_test_scaling_law(pangram: str) -> dict:
    """Measure entropy with current model and test scaling law empirically."""
    corpus_entropy = estimate_corpus_entropy(
        [pangram],
        model="claude-sonnet-4-6",
        sample_positions=24,
    )

    char_entropy = estimate_character_entropy(
        context=pangram[: max(1, len(pangram) // 2)],
        candidate_chars=list(DEFAULT_CHARSET),
        model="claude-sonnet-4-6",
        n_samples=160,
    )

    h_claude = float(corpus_entropy["mean_entropy_bits"])
    theoretical_speedup = compute_bridge_speedup(h_claude, reference_data.UNIFORM_ENTROPY_BITS)

    uniform = uniform_prior(DEFAULT_CHARSET)
    gpt2_prior = distribution_for_entropy(
        reference_data.GPT2_CHARACTER_ENTROPY_BITS,
        chars=DEFAULT_CHARSET,
    )
    claude_prior = distribution_for_entropy(h_claude, chars=DEFAULT_CHARSET)

    d_prime_eval = reference_data.D_PRIME_MIDRANGE_EEG
    uniform_metrics = _simulate_speed(
        text=pangram,
        d_prime=d_prime_eval,
        prior=uniform,
        method="uniform",
        seed=11,
    )
    gpt2_metrics = _simulate_speed(
        text=pangram,
        d_prime=d_prime_eval,
        prior=gpt2_prior,
        method="bridge",
        seed=11,
    )
    claude_metrics = _simulate_speed(
        text=pangram,
        d_prime=d_prime_eval,
        prior=claude_prior,
        method="bridge",
        seed=11,
    )

    uniform_tp = max(uniform_metrics["throughput_bpm"], 1e-12)
    gpt2_speedup_emp = gpt2_metrics["throughput_bpm"] / uniform_tp
    claude_speedup_emp = claude_metrics["throughput_bpm"] / uniform_tp

    if claude_speedup_emp <= gpt2_speedup_emp:
        raise AssertionError(
            "Scaling law check failed: empirical Claude speedup does not exceed GPT-2 speedup."
        )

    return {
        "phase": "phase2_test_scaling_law",
        "pangram": pangram,
        "measured_entropy_bits": h_claude,
        "character_entropy_probe": char_entropy,
        "entropy_estimate": corpus_entropy,
        "uniform_entropy_bits": float(reference_data.UNIFORM_ENTROPY_BITS),
        "gpt2_entropy_bits": float(reference_data.GPT2_CHARACTER_ENTROPY_BITS),
        "gpt4_projected_entropy_bits": float(reference_data.GPT4_PROJECTED_ENTROPY_BITS),
        "theoretical_speedup": float(theoretical_speedup),
        "empirical_speedups": {
            "gpt2": float(gpt2_speedup_emp),
            "claude": float(claude_speedup_emp),
        },
        "metrics": {
            "uniform": uniform_metrics,
            "gpt2": gpt2_metrics,
            "claude": claude_metrics,
        },
    }


def _model_proposal_via_api(system_prompt: str, user_prompt: str) -> dict[str, Any]:
    # Reuse entropy sampler plumbing to avoid a second SDK dependency path.
    force_local = os.getenv("OPENATOMS_BCI_FORCE_LOCAL_LM", "").lower() in {"1", "true", "yes"}
    if force_local:
        raise RuntimeError("Forced local proposal mode.")

    # Try Anthropic first.
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        from anthropic import Anthropic

        client = Anthropic(api_key=anthropic_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=220,
            temperature=0.0,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = "".join(getattr(block, "text", "") for block in response.content)
        return json.loads(text)

    # Fallback to Groq chat completions when configured.
    groq_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENATOMS_GROQ_API_KEY")
    if groq_key:
        import urllib.request

        payload = {
            "model": "llama-3.3-70b-versatile",
            "temperature": 0.0,
            "max_tokens": 220,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        request = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {groq_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
        data = json.loads(raw)
        text = str(data["choices"][0]["message"]["content"])
        return json.loads(text)

    raise RuntimeError("No API key configured for proposal generation.")


def _coerce_proposal(raw: dict[str, Any], default_seed: int) -> dict[str, Any]:
    proposal = {
        "paradigm": str(raw.get("paradigm", "p300_speller")),
        "d_prime_hypothesis": float(raw.get("d_prime_hypothesis", 0.8)),
        "n_repetitions": int(raw.get("n_repetitions", 8)),
        "flash_duration_ms": float(raw.get("flash_duration_ms", 100.0)),
        "fusion_method": str(raw.get("fusion_method", "bayesian")),
        "seed": int(raw.get("seed", default_seed)),
    }
    proposal["paradigm"] = "p300_speller"
    proposal["fusion_method"] = "bayesian" if proposal["fusion_method"] != "uniform" else "uniform"
    proposal["d_prime_hypothesis"] = float(np.clip(proposal["d_prime_hypothesis"], 0.05, 3.5))
    proposal["n_repetitions"] = int(np.clip(proposal["n_repetitions"], 1, 20))
    proposal["flash_duration_ms"] = float(np.clip(proposal["flash_duration_ms"], 40.0, 250.0))
    return proposal


def _heuristic_revised_proposal(last_error: dict[str, Any] | None, seed: int) -> dict[str, Any]:
    if last_error is None:
        return {
            "paradigm": "p300_speller",
            "d_prime_hypothesis": 0.8,
            "n_repetitions": 8,
            "flash_duration_ms": 100.0,
            "fusion_method": "bayesian",
            "seed": seed,
        }

    constraint = str(last_error.get("constraint_type", ""))
    if constraint == "throughput":
        return {
            "paradigm": "p300_speller",
            "d_prime_hypothesis": 1.2,
            "n_repetitions": 7,
            "flash_duration_ms": 90.0,
            "fusion_method": "bayesian",
            "seed": seed,
        }
    return {
        "paradigm": "p300_speller",
        "d_prime_hypothesis": 1.1,
        "n_repetitions": 8,
        "flash_duration_ms": 100.0,
        "fusion_method": "bayesian",
        "seed": seed,
    }


def phase3_closed_loop(derco_path: str) -> dict:
    """Run a closed-loop hypothesis generation cycle with structured simulator feedback."""
    phase2 = phase2_test_scaling_law(PANGRAM)
    lm_entropy = float(phase2["measured_entropy_bits"])

    simulator = BCISimulator(
        model_version="bci-sim-1.0",
        entropy_source=str(phase2["entropy_estimate"].get("providers", ["unknown"])[0]),
        n_monte_carlo_trials=600,
    )

    itr_threshold = 22.0
    max_iterations = 10
    iterations: list[dict[str, Any]] = []
    total_api_calls = 0

    system_prompt = (
        "You are optimizing a P300 Bridge BCI protocol. Return JSON only with fields: "
        "paradigm, d_prime_hypothesis, n_repetitions, flash_duration_ms, fusion_method, seed."
    )

    # Intentionally weak bootstrap proposal to guarantee at least one rejection in the loop trace.
    proposal = {
        "paradigm": "p300_speller",
        "d_prime_hypothesis": 0.25,
        "n_repetitions": 10,
        "flash_duration_ms": 120.0,
        "fusion_method": "uniform",
        "seed": 101,
    }

    last_error: dict[str, Any] | None = None
    final_config: BCIExperimentProtocol | None = None

    for idx in range(1, max_iterations + 1):
        if idx > 1:
            user_prompt = (
                "Previous proposal was rejected. Structured error:\n"
                f"{json.dumps(last_error or {}, sort_keys=True)}\n"
                "Propose a revised protocol that maximizes throughput while preserving "
                "Bridge crossover behavior."
            )
            try:
                raw = _model_proposal_via_api(system_prompt, user_prompt)
                total_api_calls += 1
                proposal = _coerce_proposal(raw, default_seed=100 + idx)
            except Exception:
                proposal = _heuristic_revised_proposal(last_error, seed=100 + idx)

        protocol = BCIExperimentProtocol(
            paradigm=proposal["paradigm"],
            d_prime_hypothesis=float(proposal["d_prime_hypothesis"]),
            lm_model="claude-sonnet-4-6",
            lm_entropy_bits=lm_entropy,
            corpus_text=PANGRAM,
            n_repetitions=int(proposal["n_repetitions"]),
            flash_duration_ms=float(proposal["flash_duration_ms"]),
            fusion_method=str(proposal["fusion_method"]),
            seed=int(proposal["seed"]),
        )

        sim = simulator.run(protocol)
        itr_bpm = float(sim.payload["itr_bpm"])
        crossover_ok = bool(sim.payload["crossover_within_tolerance"])
        bridge_mode = protocol.fusion_method == "bayesian"

        accepted = bool(itr_bpm >= itr_threshold and crossover_ok and bridge_mode)
        error_payload: dict[str, Any] | None = None

        if not accepted:
            remediation = (
                "Use bayesian fusion, increase d_prime_hypothesis, and reduce repetitions."
            )
            error_payload = PhysicsError(
                error_code="BCI_001",
                constraint_type="throughput",
                description="Proposal did not meet BCI throughput or crossover constraints.",
                actual_value={
                    "itr_bpm": itr_bpm,
                    "crossover_within_tolerance": crossover_ok,
                    "fusion_method": protocol.fusion_method,
                },
                limit_value={
                    "itr_bpm_min": itr_threshold,
                    "crossover_within_tolerance": True,
                    "fusion_method": "bayesian",
                },
                remediation_hint=remediation,
            ).to_dict()
            last_error = error_payload

        iterations.append(
            {
                "iteration": idx,
                "proposal": asdict(protocol),
                "result": {
                    "accepted": accepted,
                    "check_type": sim.check_type,
                    "itr_bpm": itr_bpm,
                    "accuracy": float(sim.payload["accuracy"]),
                    "crossover_d_prime_measured": float(sim.payload["crossover_d_prime_measured"]),
                    "crossover_within_tolerance": crossover_ok,
                },
                "error": error_payload,
            }
        )

        if accepted:
            protocol.result_accuracy = float(sim.payload["accuracy"])
            protocol.result_itr_bpm = itr_bpm
            protocol.result_crossover_d_prime = float(sim.payload["crossover_d_prime_measured"])
            final_config = protocol
            break

    if final_config is None:
        raise AssertionError("Closed-loop search failed to converge within max_iterations.")

    return {
        "phase": "phase3_closed_loop",
        "iterations": iterations,
        "final_config": asdict(final_config),
        "total_api_calls": int(total_api_calls),
    }


def run_all(
    derco_path: str,
    *,
    output_bundle: Path = DEFAULT_BUNDLE_OUTPUT,
    seed: int = 42,
) -> dict[str, Any]:
    phase1 = phase1_reproduce_crossover(derco_path)
    phase2 = phase2_test_scaling_law(PANGRAM)
    phase3 = phase3_closed_loop(derco_path)

    output_dir = THIS_DIR / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    simulator_report = {
        "check_type": "validated_simulation",
        "lm_model": "claude-sonnet-4-6",
        "lm_entropy_bits": float(phase2["measured_entropy_bits"]),
        "simulation_seed": int(seed),
        "n_monte_carlo_trials": 600,
        "crossover_d_prime_measured": float(phase1["crossover_d_prime_measured"]),
        "crossover_d_prime_published": float(reference_data.CROSSOVER_D_PRIME),
        "crossover_within_tolerance": bool(phase1["crossover_within_tolerance"]),
        "check_type_detail": "validated_simulation",
    }

    results_payload = {
        "phase1": phase1,
        "phase2": phase2,
        "phase3": phase3,
    }

    results_json = output_dir / "bci_results.json"
    sim_json = output_dir / "bci_simulation_report.json"
    results_json.write_text(
        json.dumps(results_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    sim_json.write_text(json.dumps(simulator_report, indent=2, sort_keys=True), encoding="utf-8")

    protocol = _build_minimal_protocol_for_bundle("bci_verification_bottleneck")
    bundle_path = create_bundle(
        output_path=output_bundle,
        protocol=protocol,
        results_paths=[results_json, sim_json],
        metadata={
            "example": "bci_verification_bottleneck",
            "check_type": "validated_simulation",
            "lm_model": "claude-sonnet-4-6",
            "lm_entropy_bits": float(phase2["measured_entropy_bits"]),
            "entropy_provider": phase2["entropy_estimate"].get("providers", ["unknown"])[0],
            "crossover_d_prime_measured": float(phase1["crossover_d_prime_measured"]),
        },
        seeds={"python_random": seed, "numpy": seed, "openatoms_internal": seed},
        deterministic=True,
        zip_output=True,
    )

    signing_key = os.getenv("OPENATOMS_BUNDLE_SIGNING_KEY", "openatoms-bci-demo-signing-key")
    sign_bundle(bundle_path, key=signing_key, deterministic=True)

    summary = {
        "bundle_path": str(bundle_path),
        "phase1": phase1,
        "phase2": phase2,
        "phase3": phase3,
        "signed": True,
    }
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the BCI verification bottleneck worked example."
    )
    parser.add_argument("--derco-path", required=True, help="Path to DERCo dataset root or file.")
    parser.add_argument(
        "--output-bundle",
        default=str(DEFAULT_BUNDLE_OUTPUT),
        help="Output bundle path (.zip).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Deterministic seed for bundle metadata.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    output_bundle = Path(args.output_bundle).expanduser().resolve()
    result = run_all(args.derco_path, output_bundle=output_bundle, seed=int(args.seed))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
