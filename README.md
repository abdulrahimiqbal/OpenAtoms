# OpenAtoms

OpenAtoms compiles AI-proposed lab actions into deterministic protocol IR, validates hard safety invariants, and executes optional simulator safety gates before hardware execution.

## Installation

Core + developer tooling:

```bash
python -m pip install -e ".[dev]"
```

Optional simulator extras:

```bash
python -m pip install -e ".[sim-cantera]"   # thermo-kinetic node
python -m pip install -e ".[sim-mujoco]"    # robotics node
python -m pip install -e ".[sim-all]"       # all optional simulators
```

## Minimal Hello Protocol

```bash
python - <<'PY'
from openatoms.actions import Move
from openatoms.core import Container, Matter, Phase
from openatoms.dag import ProtocolGraph
from openatoms.units import Q_

a = Container(id="A", label="A", max_volume=Q_(500, "microliter"), max_temp=Q_(100, "degC"), min_temp=Q_(0, "degC"))
b = Container(id="B", label="B", max_volume=Q_(500, "microliter"), max_temp=Q_(100, "degC"), min_temp=Q_(0, "degC"))
a.contents.append(Matter(name="H2O", phase=Phase.LIQUID, mass=Q_(200, "milligram"), volume=Q_(200, "microliter")))

g = ProtocolGraph("hello_protocol")
g.add_step(Move(a, b, Q_(100, "microliter")))
g.dry_run()
print(g.export_json())
PY
```

## IR Schema and Validation Contract

- Canonical runtime interface: `openatoms.ir.validate_ir`, `openatoms.ir.load_schema`, `openatoms.ir.schema_version`, `openatoms.ir.schema_resource_name`.
- Canonical schema resource: `openatoms/ir/schema_v1_1_0.json`.
- Legacy schema helpers (`get_schema_version`, `get_schema_path`, `schema_path`) are deprecated wrappers.
- Invalid payloads return stable `IRValidationError` codes (`IR_TYPE`, `IR_VERSION`, `IR_MISSING_FIELD`, `IR_SCHEMA_VALIDATION`).

### Versioning policy

- Backward-incompatible IR changes require a new schema version and resource filename.
- Runtime code must reference exactly one canonical schema resource.
- Deprecations keep wrapper entrypoints for one minor line before removal.

## Determinism Guarantees

- IR serialization is canonical (`sorted keys`, compact separators, stable SHA-256 hashing).
- Benchmark artifacts are deterministic for fixed `(seed, n, suite, injection_probability)`:
  - `raw_runs.jsonl`
  - `summary.json`
  - `BENCHMARK_REPORT.md`
- Reproducibility check:

```bash
python scripts/verify_reproducibility.py
```

If `cantera` is missing:
- CI exits nonzero.
- Local runs may skip only with `OPENATOMS_ALLOW_SKIP=1`.

## Simulator Safety Contracts

- Node A (`OT2Simulator`): guarantees deterministic pipetting/deck safety checks; does **not** model meniscus/fluid dynamics.
- Node B (`VirtualReactor`): guarantees deterministic thermo safety gating from Cantera-backed endpoints; does **not** claim full publication-grade reactor-network fidelity.
- Node C (`RoboticsSimulator`): guarantees deterministic analytical grasp/stress/torque/collision checks; MuJoCo mode is optional and not a certification claim.

## Benchmark Reproduction

```bash
python -m eval.run_benchmark --seed 123 --n 200 --suite realistic --violation-probability 0.1
```

Benchmark suites:
- `realistic`: plausible operating ranges, low violation injection.
- `stress`: edge-heavy ranges, higher violation injection.
- `fuzz`: edge-biased deterministic fuzz ranges.

### What benchmark metrics mean

- Detection: TP/FP/FN/TN and Wilson confidence intervals.
- Correction: successful remediation rate (valid + intent-proxy preserving) and confidence intervals.

### What benchmark metrics do not mean

- They are not hardware calibration accuracy.
- They are not proof of end-to-end robotic execution safety.
- They are not substitutes for human review, SOP checks, or interlock validation.

## Security, Safety, and Release

- Security reporting: [SECURITY.md](SECURITY.md)
- Operational safety boundaries: [SAFETY.md](SAFETY.md)
- Release process: [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)
- Change history: [CHANGELOG.md](CHANGELOG.md)
