# OpenAtoms

OpenAtoms is a reliability layer for LLM-driven science.

When you use an AI to accelerate research — generating hypotheses, designing protocols, exploring parameter spaces — you introduce a new bottleneck: you can't tell which AI-generated results are physically real. The outputs look plausible, the code runs, the numbers come out. But without a verification step, you're moving fast without confidence in the direction.

OpenAtoms sits between your AI and your experiment. Every AI-proposed protocol is validated against physical and empirical constraints before execution. Every run produces a signed, replayable bundle — mechanism files, solver tolerances, dependency versions, full trajectory — that anyone can reproduce exactly.

**AI proposes. OpenAtoms verifies. The bundle proves it.**

---

## Installation

Core:

```bash
pip install -e ".[dev]"
```

Optional simulator nodes:

```bash
pip install -e ".[cantera]"      # thermo-kinetic chemistry node
pip install -e ".[opentrons]"    # liquid-handling robot node
pip install -e ".[all]"          # all simulators
```

BCI worked example:

```bash
pip install -e ".[bci-example]"
export ANTHROPIC_API_KEY=sk-...
python examples/bci_verification_bottleneck/run_example.py --derco-path /path/to/derco
```

---

## Worked Example: The Verification Bottleneck

The fastest way to understand what OpenAtoms does is to see it run on a real research question.

Rahim Iqbal's paper ["The Verification Bottleneck"](https://rahimiqbal.substack.com/p/the-verification-bottleneck-why-better) showed that LLM-assisted brain-computer interfaces dramatically outperform standard approaches at consumer EEG signal quality, with a crossover point around d′ ≈ 1.7. The paper projected that GPT-4 class models would give ~3.4x speedup over a uniform prior — but that was a projection, not a measurement.

We ran it through OpenAtoms. Here's what happened:

| Metric | Published | Reproduced | Source |
|--------|-----------|------------|--------|
| Crossover d′ | ≈ 1.7 | **1.663** | Phase 1 |
| N400 passive d′ | ≈ 0.00 | **0.024** | Phase 1 (DERCo) |
| GPT-2 speedup | 2.3× | **2.35×** | Phase 2 |
| Claude entropy | projected 1.5 bits | **1.073 bits** (measured) | Phase 2 |
| Claude speedup | projected 3.4× | **4.23×** (measured) | Phase 2 |
| Closed-loop convergence | — | **2 iterations** (1 rejection → 1 acceptance) | Phase 3 |

The Claude entropy and speedup numbers are new results. They weren't in the paper. They came out of the loop — and they're better than the GPT-4 projection the paper used as its upper bound.

The entire run produced a signed bundle. Anyone can download it, run one command, and get identical numbers.

### What the three phases demonstrate

**Phase 1 — Reproduce:** The d′ crossover curve is recomputed from scratch against the DERCo dataset. The result lands within 2% of the published value. The N400 negative result replicates near-zero, exactly as the paper reports.

**Phase 2 — Extend:** Claude's actual character-level entropy is measured via API sampling — not projected from scaling laws. The empirical speedup is computed directly. This is a new data point the original paper couldn't produce.

**Phase 3 — Close the loop:** An AI agent proposes BCI protocol configurations. The simulator evaluates them. The first proposal is intentionally weak and gets rejected with a structured error. The AI revises. The second proposal is accepted. The full iteration trace — including the rejection — is recorded in the bundle.

### Running it yourself

```bash
pip install -e ".[bci-example]"
export ANTHROPIC_API_KEY=sk-...

python examples/bci_verification_bottleneck/run_example.py \
    --derco-path /path/to/derco \
    --output-bundle ./my_bundle.zip

openatoms bundle verify ./my_bundle.zip
```

---

## Building a Reliability Layer for Your Own Experiment

The BCI example is one instance of a general pattern. Any experiment where an AI generates hypotheses or protocols can be wrapped in OpenAtoms in the same way.

The pattern:

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

You implement four things: a protocol dataclass, a simulator, a closed loop, and a bundle. The framework handles IR serialization, deterministic hashing, signing, and replay.

**→ Full step-by-step walkthrough with complete example code: [SETUP.md](SETUP.md)**

The walkthrough covers defining a protocol, writing a simulator with structured error codes, building the agent loop, creating a signed bundle, and a test suite for the whole thing. Works for any domain — computational, wet lab, materials screening, or anything else where an AI is generating experimental proposals.

---

## What OpenAtoms Actually Does

### Protocol IR

Every experiment is compiled into a versioned, deterministic IR (Intermediate Representation) — a JSON document that captures the full protocol as a dependency graph. The IR is schema-validated and content-hashed before any simulation or execution runs.

```python
from openatoms.actions import Move
from openatoms.core import Container, Matter, Phase
from openatoms.dag import ProtocolGraph
from openatoms.units import Q_

src = Container(id="A", label="A", max_volume=Q_(500, "microliter"),
                max_temp=Q_(100, "degC"), min_temp=Q_(0, "degC"))
dst = Container(id="B", label="B", max_volume=Q_(500, "microliter"),
                max_temp=Q_(100, "degC"), min_temp=Q_(0, "degC"))
src.contents.append(Matter(name="H2O", phase=Phase.LIQUID,
                            mass=Q_(200, "milligram"), volume=Q_(200, "microliter")))

graph = ProtocolGraph("example")
graph.add_step(Move(src, dst, Q_(100, "microliter")))
graph.dry_run()
print(graph.export_json())
```

### Physics validation

Before any simulation runs, protocols are validated for physical feasibility: volume overflow, thermal limits, mass conservation, ordering constraints. Violations return structured `PhysicsError` payloads with `remediation_hint` fields — machine-readable, designed for agent self-correction loops.

### Simulation nodes

| Node | Domain | What it does |
|------|--------|-------------|
| **Thermo-kinetic** | Chemistry | Cantera CVODE ODE integration for H₂/O₂ and other mechanisms. Real ignition delay computation, calibrated against published experimental data. Thermal runaway detection from trajectory dT/dt. |
| **Bio-kinetic** | Liquid handling | Opentrons-compatible pipetting simulation. Volume tracking, deck geometry checks, collision detection. Optional `opentrons.simulate` integration. |

Both nodes emit `StateObservation` payloads. Both can be used without hardware.

### Simulation contracts (what we claim and don't claim)

- **Thermo-kinetic node:** Deterministic thermo safety gating from Cantera-backed ODE integration, calibrated against Slack & Grillo (1977) ignition data. Does not claim publication-grade reactor-network fidelity for all mechanisms or operating conditions.
- **Bio-kinetic node:** Deterministic pipetting and deck safety checks. Does not model meniscus dynamics or fluid physics.

### Experiment bundles

Every run produces a signed `.zip` bundle containing the protocol IR, simulation outputs, result files, dependency manifest, and a cryptographic signature. The bundle format is the reproducibility artifact — it is the methods section.

```bash
openatoms bundle create --ir protocol.ir.json --output ./bundle --deterministic
openatoms bundle verify --bundle ./bundle
openatoms bundle replay --bundle ./bundle --strict
openatoms bundle sign --bundle ./bundle
openatoms bundle verify-signature --bundle ./bundle
```

Full spec: [`docs/BUNDLE_SPEC.md`](docs/BUNDLE_SPEC.md)

### Determinism guarantees

- IR serialization is canonical (sorted keys, stable SHA-256 hashing).
- Benchmark artifacts are deterministic for fixed `(seed, n, suite, injection_probability)`.
- Reproducibility check: `python scripts/verify_reproducibility.py`

---

## Benchmark

```bash
python -m eval.run_benchmark --seed 123 --n 200 --suite realistic --violation-probability 0.1
```

Suites: `realistic` (low violation injection), `stress` (edge-heavy), `fuzz` (deterministic edge-biased).

Benchmark metrics measure whether the validator correctly detects and remediates injected violations — with Wilson confidence intervals. They are not hardware calibration accuracy and are not substitutes for human review or interlock validation.

---

## Repository Layout

```
openatoms/                             # Core compiler, actions, validators, IR
openatoms/sim/registry/                # Simulation nodes (Cantera, Opentrons)
examples/bci_verification_bottleneck/  # Worked example: BCI research reproduction
eval/                                  # Benchmark pipeline
tests/                                 # Test suite
docs/                                  # Bundle spec, reproducibility contract
```

---

## Security and Safety

- Security reporting: [SECURITY.md](SECURITY.md)
- Operational safety boundaries: [SAFETY.md](SAFETY.md)
- Release process: [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)
- Change history: [CHANGELOG.md](CHANGELOG.md)

OpenAtoms simulation nodes are safety-gating tools, not hardware certification systems. A simulation pass is not a substitute for qualified human review, standard operating procedures, or physical interlocks before execution on real equipment.
