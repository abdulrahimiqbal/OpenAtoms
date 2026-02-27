# Building a Reliability Layer for Your Own Experiment

The BCI example is one instance of a general pattern. Any experiment where an AI generates hypotheses or protocols can be wrapped in OpenAtoms. This is a complete walkthrough — copy, adapt, run.

## How it works

```
AI generates candidate
        ↓
OpenAtoms validates against your constraints
        ↓
Pass → execute, record result
Fail → structured PhysicsError with remediation_hint → back to AI
        ↓
Every outcome → signed bundle with full provenance
```

You implement four things: a protocol, a simulator, a loop, and a bundle. The framework handles IR serialization, deterministic hashing, signing, and replay.

---

## Step 1: Install and set up

```bash
pip install -e ".[dev]"
export ANTHROPIC_API_KEY=sk-...
```

Create a directory for your experiment:

```
my_experiment/
├── protocol.py          # your Protocol dataclass
├── simulator.py         # your Simulator class
├── run.py               # the closed loop + bundle
└── outputs/             # signed bundles land here
```

---

## Step 2: Define your protocol

A protocol is a plain dataclass. It captures every parameter that affects your experimental outcome — think of it as the complete specification that, given the same values, should always produce the same result.

```python
# protocol.py
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class MyProtocol:
    # --- inputs: everything the AI proposes ---
    hypothesis_id: str          # unique ID for this proposal
    condition_a: float          # e.g. concentration, temperature, dose
    condition_b: float          # e.g. duration, threshold, ratio
    method: str                 # e.g. "standard" | "variant_x"
    seed: int = 42

    # --- outputs: filled in after simulation ---
    result_score: float | None = None
    result_accepted: bool = False
    result_iteration: int | None = None
    check_type: str = "validated_simulation"
```

**Rule:** if changing a value would change the experimental outcome, it belongs in the protocol. This is what makes bundles reproducible — the protocol is the complete state.

---

## Step 3: Write a simulator

The simulator is the heart of the reliability layer. It takes a protocol, evaluates it against your domain's constraints, and either returns a result or raises a `PhysicsError` with enough information for the AI to self-correct.

What "evaluate" means is entirely up to you:

| Your domain | What the simulator does |
|-------------|------------------------|
| Computational / ML | Runs the computation, checks output against published benchmarks or known bounds |
| Wet lab protocol | Validates parameters for physical feasibility before any hardware is touched |
| Drug / materials screening | Checks AI-proposed candidates against synthesizability, safety, or property filters |
| Statistical analysis | Validates that proposed methods satisfy power, sample size, or distributional assumptions |
| Any domain | Checks AI-generated outputs against whatever ground truth you have |

```python
# simulator.py
from __future__ import annotations
from dataclasses import dataclass
from openatoms.errors import PhysicsError
from protocol import MyProtocol


@dataclass
class SimResult:
    accepted: bool
    score: float
    payload: dict
    check_type: str = "validated_simulation"


# Your domain-specific evaluation function.
# Replace this with whatever actually computes your result.
def _evaluate(condition_a: float, condition_b: float, method: str, seed: int) -> dict:
    import numpy as np
    rng = np.random.default_rng(seed)
    # --- substitute your real computation here ---
    score = condition_a * 0.6 - condition_b * 0.3 + rng.normal(0, 0.05)
    return {"score": float(score), "method": method}


class MySimulator:
    SCORE_THRESHOLD = 0.4      # acceptance criterion — set this for your domain
    CONDITION_A_MAX = 2.0      # hard physical/logical upper bound
    CONDITION_B_MIN = 0.1      # hard physical/logical lower bound

    def run(self, protocol: MyProtocol) -> SimResult:
        # --- hard constraint checks first (before any computation) ---
        if protocol.condition_a > self.CONDITION_A_MAX:
            raise PhysicsError(
                error_code="EXP_001",
                constraint_type="parameter_bounds",
                description="condition_a exceeds the maximum permitted value.",
                actual_value={"condition_a": protocol.condition_a},
                limit_value={"condition_a_max": self.CONDITION_A_MAX},
                remediation_hint=(
                    f"Set condition_a to a value at or below {self.CONDITION_A_MAX}. "
                    "Values above this bound are outside the validated operating range."
                ),
            )

        if protocol.condition_b < self.CONDITION_B_MIN:
            raise PhysicsError(
                error_code="EXP_002",
                constraint_type="parameter_bounds",
                description="condition_b is below the minimum permitted value.",
                actual_value={"condition_b": protocol.condition_b},
                limit_value={"condition_b_min": self.CONDITION_B_MIN},
                remediation_hint=(
                    f"Set condition_b to a value at or above {self.CONDITION_B_MIN}."
                ),
            )

        # --- run the actual evaluation ---
        result = _evaluate(
            protocol.condition_a,
            protocol.condition_b,
            protocol.method,
            protocol.seed,
        )

        # --- outcome check ---
        if result["score"] < self.SCORE_THRESHOLD:
            raise PhysicsError(
                error_code="EXP_003",
                constraint_type="outcome_threshold",
                description="Simulated outcome did not meet the acceptance threshold.",
                actual_value={"score": result["score"]},
                limit_value={"score_min": self.SCORE_THRESHOLD},
                remediation_hint=(
                    f"Score was {result['score']:.3f}, threshold is {self.SCORE_THRESHOLD}. "
                    "Try increasing condition_a (positive effect) or decreasing condition_b "
                    "(negative effect). Switching method to 'variant_x' may also help."
                ),
            )

        return SimResult(accepted=True, score=result["score"], payload=result)
```

Two things to get right in your simulator:

1. **Hard bounds before computation.** Check parameter ranges before running anything expensive. A rejected proposal should fail fast.
2. **Specific `remediation_hint`.** This string goes back to the AI verbatim. "Try increasing X" is useful. "Invalid input" is not. The more specific the hint, the fewer iterations the loop needs.

---

## Step 4: Build the closed loop

The loop runs until a proposal is accepted or the iteration limit is hit. Every proposal — including rejected ones — is recorded. The rejection trace is part of the scientific record.

```python
# run.py
from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

import anthropic
from openatoms.errors import PhysicsError
from protocol import MyProtocol
from simulator import MySimulator


SYSTEM_PROMPT = """\
You are optimizing an experiment protocol. Your goal is to find parameter values
that maximize the experimental outcome score.

You will receive structured error feedback when a proposal is rejected.
Each error includes:
  - error_code: the type of constraint violated
  - actual_value: what you proposed
  - limit_value: the constraint boundary
  - remediation_hint: specific guidance on how to fix it

Always return valid JSON with exactly these fields:
{
    "condition_a": <float between 0.0 and 2.0>,
    "condition_b": <float between 0.1 and 5.0>,
    "method": <"standard" or "variant_x">,
    "reasoning": <one sentence explaining your choice>
}
Return JSON only. No preamble, no markdown fences.\
"""


def propose(
    client: anthropic.Anthropic,
    last_error: dict[str, Any] | None,
    iteration: int,
) -> dict[str, Any]:
    """Ask the AI for a protocol proposal, optionally with error feedback."""
    if last_error is None:
        user_content = (
            "Propose an initial experiment configuration to maximize the outcome score."
        )
    else:
        user_content = (
            f"Iteration {iteration}. Your previous proposal was rejected.\n\n"
            f"Structured error:\n{json.dumps(last_error, indent=2)}\n\n"
            "Propose a revised configuration that addresses the error above."
        )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    raw = response.content[0].text.strip()
    # Strip markdown fences if the model adds them despite instructions.
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def run_loop(
    *,
    max_iterations: int = 10,
    seed: int = 42,
) -> dict[str, Any]:
    client = anthropic.Anthropic()
    simulator = MySimulator()

    iterations: list[dict[str, Any]] = []
    last_error: dict[str, Any] | None = None
    accepted_protocol: MyProtocol | None = None

    for i in range(1, max_iterations + 1):
        # 1. Get proposal from AI
        raw_proposal = propose(client, last_error, i)

        protocol = MyProtocol(
            hypothesis_id=f"h{i:03d}",
            condition_a=float(raw_proposal.get("condition_a", 1.0)),
            condition_b=float(raw_proposal.get("condition_b", 1.0)),
            method=str(raw_proposal.get("method", "standard")),
            seed=seed,
        )

        # 2. Evaluate with simulator
        error_payload: dict[str, Any] | None = None
        sim_result = None

        try:
            sim_result = simulator.run(protocol)
            protocol.result_score = sim_result.score
            protocol.result_accepted = True
            protocol.result_iteration = i
            accepted_protocol = protocol
            last_error = None
        except PhysicsError as exc:
            error_payload = exc.to_dict()
            last_error = error_payload

        # 3. Record everything — accepted and rejected
        iterations.append({
            "iteration": i,
            "proposal": asdict(protocol),
            "ai_reasoning": raw_proposal.get("reasoning", ""),
            "accepted": sim_result is not None,
            "score": sim_result.score if sim_result else None,
            "error": error_payload,
        })

        if accepted_protocol is not None:
            break

    if accepted_protocol is None:
        raise RuntimeError(
            f"Loop did not converge within {max_iterations} iterations. "
            "Review the rejection trace in the iterations list."
        )

    return {
        "accepted_protocol": asdict(accepted_protocol),
        "iterations": iterations,
        "total_iterations": len(iterations),
        "rejections": sum(1 for it in iterations if not it["accepted"]),
    }
```

---

## Step 5: Save results and create a signed bundle

```python
# (continued in run.py)
from openatoms import (
    Q_, Container, Matter, Move, Phase,
    build_protocol, create_bundle, create_protocol_state, sign_bundle,
)


def _minimal_openatoms_protocol(name: str):
    """
    OpenAtoms bundles anchor to a ProtocolGraph IR.
    For experiments that don't use the liquid-handling primitives directly,
    create a minimal single-step protocol as the IR anchor.
    The actual experimental results travel as attached result files.
    """
    src = Container(
        id="S1", label="S1",
        max_volume=Q_(1000, "microliter"),
        max_temp=Q_(100, "degC"),
        min_temp=Q_(0, "degC"),
    )
    dst = Container(
        id="D1", label="D1",
        max_volume=Q_(1000, "microliter"),
        max_temp=Q_(100, "degC"),
        min_temp=Q_(0, "degC"),
    )
    src.contents.append(
        Matter(name="sample", phase=Phase.LIQUID,
               mass=Q_(100, "milligram"), volume=Q_(100, "microliter"))
    )
    state = create_protocol_state([src, dst])
    return build_protocol(name, [Move(src, dst, Q_(50, "microliter"))], state=state)


def main():
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)

    # Run the closed loop
    loop_result = run_loop(max_iterations=10, seed=42)

    # Save results to JSON
    results_path = output_dir / "results.json"
    results_path.write_text(json.dumps(loop_result, indent=2, sort_keys=True))

    print(f"Accepted on iteration {loop_result['total_iterations']} "
          f"({loop_result['rejections']} rejection(s))")
    print(f"Final score: {loop_result['accepted_protocol']['result_score']:.4f}")

    # Build and sign the bundle
    protocol = _minimal_openatoms_protocol("my_experiment")
    bundle_path = create_bundle(
        output_path=output_dir / "my_experiment_bundle.zip",
        protocol=protocol,
        results_paths=[results_path],
        metadata={
            "experiment": "my_experiment",
            "check_type": "validated_simulation",
            "accepted_on_iteration": loop_result["total_iterations"],
            "total_rejections": loop_result["rejections"],
            "final_score": loop_result["accepted_protocol"]["result_score"],
        },
        seeds={"numpy": 42},
        deterministic=True,
        zip_output=True,
    )

    signing_key = os.getenv("OPENATOMS_SIGNING_KEY", "my-experiment-signing-key")
    sign_bundle(bundle_path, key=signing_key, deterministic=True)

    print(f"\nBundle written to: {bundle_path}")
    print("Verify with: openatoms bundle verify outputs/my_experiment_bundle.zip")


if __name__ == "__main__":
    main()
```

Run it:

```bash
python run.py
# → Accepted on iteration 2 (1 rejection)
# → Final score: 0.4712
# → Bundle written to: outputs/my_experiment_bundle.zip

openatoms bundle verify outputs/my_experiment_bundle.zip
```

The bundle contains the full iteration trace including rejected proposals, the accepted protocol parameters, the final score, every dependency pinned, and a cryptographic signature. It is the complete, replayable record of the experiment.

---

## Step 6: Add tests

The loop is non-trivial. Test it.

```python
# test_my_experiment.py
import pytest
from simulator import MySimulator, MyProtocol
from openatoms.errors import PhysicsError


def test_simulator_accepts_valid_protocol():
    sim = MySimulator()
    result = sim.run(MyProtocol(
        hypothesis_id="test_001",
        condition_a=1.5, condition_b=0.5,
        method="standard", seed=42,
    ))
    assert result.accepted
    assert result.score >= MySimulator.SCORE_THRESHOLD


def test_simulator_rejects_out_of_bounds():
    sim = MySimulator()
    with pytest.raises(PhysicsError) as exc_info:
        sim.run(MyProtocol(
            hypothesis_id="test_002",
            condition_a=99.0,  # above bound
            condition_b=1.0, method="standard", seed=42,
        ))
    assert exc_info.value.error_code == "EXP_001"
    assert "remediation_hint" in exc_info.value.to_dict()


def test_simulator_rejects_low_score():
    sim = MySimulator()
    with pytest.raises(PhysicsError) as exc_info:
        sim.run(MyProtocol(
            hypothesis_id="test_003",
            condition_a=0.0,  # score will be below threshold
            condition_b=4.0, method="standard", seed=42,
        ))
    assert exc_info.value.error_code == "EXP_003"


def test_loop_converges(monkeypatch):
    call_count = {"n": 0}
    bad  = {"condition_a": 99.0, "condition_b": 1.0, "method": "standard", "reasoning": "bad"}
    good = {"condition_a": 1.5,  "condition_b": 0.5, "method": "standard", "reasoning": "good"}

    import run as run_module
    def mock_propose(client, last_error, iteration):
        call_count["n"] += 1
        return bad if call_count["n"] == 1 else good

    monkeypatch.setattr(run_module, "propose", mock_propose)
    monkeypatch.setattr(run_module, "anthropic", type("M", (), {"Anthropic": lambda: None})())

    result = run_module.run_loop(max_iterations=5, seed=42)
    assert result["total_iterations"] == 2
    assert result["rejections"] == 1
    assert result["accepted_protocol"]["result_accepted"] is True


def test_simulation_is_deterministic():
    sim = MySimulator()
    p = MyProtocol(hypothesis_id="det", condition_a=1.2,
                   condition_b=0.8, method="standard", seed=42)
    assert sim.run(p).score == sim.run(p).score
```

---

## What domains fit this pattern

The pattern works for any research where an AI generates candidates that need to be checked against empirical or physical constraints before being trusted, and where reproducibility of the computational layer matters for publication or collaboration.

The key question: **can you write a simulator that returns pass/fail for a given set of parameters?** If yes, you can build a reliability layer with OpenAtoms.

Strong fits: computational biology (parameter sweeps against experimental data), materials screening (AI-proposed compositions validated against DFT or MD), drug discovery (generated molecules checked for synthesizability), automated synthesis (AI protocols validated before robot execution), any domain where you're already using an LLM to propose experiments and want to close the loop reliably.

**Adding a new simulation node** to the registry means implementing the `StateObservation` interface. The existing chemistry (`kinetics_sim.py`) and liquid-handling (`opentrons_sim.py`) nodes are the reference implementations — both under 400 lines.
