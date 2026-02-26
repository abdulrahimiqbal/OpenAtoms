# DEV Notes

## Baseline failures

Environment date: 2026-02-26.

Commands executed:

1. `python3 -m venv .venv-baseline`
2. `. .venv-baseline/bin/activate`
3. `python -m pip install -U pip`
4. `python -m pip install -e .`

Observed failure:

```text
ERROR: Could not find a version that satisfies the requirement setuptools>=61.0 (from versions: none)
ERROR: No matching distribution found for setuptools>=61.0
ERROR: Failed to build 'file:///Users/rahim/Downloads/OpenAtoms' when installing build dependencies
```

Additional attempt:

- `python -m pip install -e . --no-build-isolation`

Observed failure:

```text
pip._vendor.pyproject_hooks._impl.BackendUnavailable: Cannot import 'setuptools.build_meta'
```

Baseline execution results from the repository `.venv`:

- `python -m pytest -q` -> `19 passed, 10 warnings`
- `python examples/hello_atoms.py` -> success
- `python scripts/verify_reproducibility.py` -> `Determinism check passed: Node B output identical across 3 runs.`

## Issue 1 updates (packaging/dependencies)

Changes made:

- Standardized dependency declarations in `pyproject.toml`.
- Added simulator extras:
  - `sim-cantera`
  - `sim-mujoco`
  - `sim-all`
- Kept `science` as a backward-compatible alias to `cantera`.
- Removed `requirements.txt` to avoid dual-source dependency drift. `pyproject.toml` is now the single source of truth.
- Added packaging/install tests:
  - `tests/test_packaging_install.py::test_editable_install_imports_in_subprocess`
  - `tests/test_packaging_install.py::test_ir_schema_is_packaged_resource`
- Added explicit setuptools package discovery config (`openatoms*`, `eval*`) to fix editable install package discovery errors.

Verification commands and outcomes:

- `. .venv/bin/activate && python -m pip install -e ".[dev]"` -> success
- `. .venv/bin/activate && python -m pytest -q` -> `21 passed, 10 warnings`

## Issue 2 updates (single IR schema system)

Inventory before refactor:

- Schema files under `openatoms/`:
  - `openatoms/ir/schema_v1_1_0.json`
  - `openatoms/schemas/ir-1.1.0.schema.json`
- Validation entrypoints:
  - `openatoms.ir.validate_ir(...)`
  - `openatoms.ir.load_ir_payload(...)`

Changes made:

- Removed duplicate schema file `openatoms/schemas/ir-1.1.0.schema.json`.
- Canonicalized IR schema interface in `openatoms.ir`:
  - `validate_ir(payload) -> dict`
  - `get_schema_version() -> str`
  - `get_schema_path() -> Path`
- Switched schema loading to `importlib.resources`.
- Added stable `IRValidationError` with error codes.
- Kept legacy entrypoints as thin wrappers:
  - `schema_path()` now warns and delegates to `get_schema_path()`.
  - `legacy_validate_ir()` now warns and delegates to `validate_ir()`.
- Added tests for:
  - legacy-vs-canonical validation parity
  - schema version/path consistency
  - stable invalid-payload code/message
  - runtime introspection that canonical schema resource is used

Verification commands and outcomes:

- `. .venv/bin/activate && python -m pytest -q` -> `24 passed, 10 warnings`
- `. .venv/bin/activate && python examples/hello_atoms.py` -> success
- `. .venv/bin/activate && python examples/basic_compilation.py` -> fails (tracked under Issue 3 API drift)
- `. .venv/bin/activate && python examples/openai_tool_calling.py` -> fails (tracked under Issue 3 API drift)
- `. .venv/bin/activate && python scripts/verify_reproducibility.py` -> success

## Issue 3 updates (API drift: examples/tests/CI sync)

Changes made:

- Updated drifted examples to current API and unit-safe quantities:
  - `examples/basic_compilation.py`
  - `examples/openai_tool_calling.py`
  - `examples/research_loop.py`
- Added comprehensive subprocess example execution test coverage for all scripts in `examples/`:
  - `tests/test_examples_execution.py` now parametrizes all examples.
  - Optional-dependency examples (`cantera`) are skipped when not installed.
- Updated reproducibility script to be optional-dependency aware:
  - `scripts/verify_reproducibility.py` now skips cleanly with install hint when `cantera` is missing.
- Simplified CI workflow and aligned it with package declarations:
  - `.github/workflows/pytest.yml` now installs with `pip install -e ".[dev]"`.
  - CI runs `ruff`, `mypy`, `pytest`, and `python scripts/verify_reproducibility.py`.
  - Removed duplicate/competing workflow setup blocks.

Verification commands and outcomes:

- `. .venv/bin/activate && python -m pytest -q` -> `28 passed, 10 warnings`
- `. .venv/bin/activate && for f in examples/*.py; do python "$f"; done` -> all examples exit `0`
- `. .venv/bin/activate && python scripts/verify_reproducibility.py` -> `Determinism check passed: Node B output identical across 3 runs.`

## Issue 4 updates (deterministic benchmark pipeline)

Changes made:

- Added deterministic benchmark pipeline under `eval/`:
  - `eval/generate_protocols.py`
  - `eval/evaluate.py`
  - `eval/baselines.py`
  - `eval/run_benchmark.py`
- Added benchmark package initializer: `eval/__init__.py`.
- Added deterministic artifact outputs:
  - `eval/results/raw_runs.jsonl`
  - `eval/results/summary.json`
  - `eval/results/BENCHMARK_REPORT.md`
- Removed stale artifact format file:
  - deleted `eval/results/benchmark_v1.json`
- Added tests:
  - deterministic summary bytes across reruns
  - validator-vs-baseline sanity (`violations_with_validators <= baseline`)
  - report required fields (N, seed, baseline, schema version, date, violation definition)
  - CLI generation path via `python -m eval.run_benchmark`

Verification commands and outcomes:

- `. .venv/bin/activate && python -m eval.run_benchmark --seed 123 --n 200` -> success
  - baseline violations: `152/200` (rate `0.760000`)
  - with_validators violations: `9/200` (rate `0.045000`)
  - relative violation reduction: `0.940789`
- `. .venv/bin/activate && python -m pytest -q` -> `32 passed, 10 warnings`
- `. .venv/bin/activate && for f in examples/*.py; do python "$f"; done` -> all examples exit `0`
- `. .venv/bin/activate && python scripts/verify_reproducibility.py` -> `Determinism check passed: Node B output identical across 3 runs.`

## Issue 5 updates (simulator scope + validation-grade tests)

Simulator audit and clarified scope:

- `openatoms/sim/registry/opentrons_sim.py`
  - Promise: deterministic pipetting/deck safety checks and error taxonomy mapping.
  - Non-claim: no full fluid dynamics / meniscus physics.
- `openatoms/sim/registry/kinetics_sim.py`
  - Promise: deterministic thermo safety gates using Cantera endpoints + interpolation.
  - Non-claim: not a full stiff ODE reactor-network fidelity model.
- `openatoms/sim/registry/robotics_sim.py`
  - Promise: deterministic analytical checks for grasp/stress/torque/collision envelopes.
  - Non-claim: no certification-grade full rigid-body dynamics claim.

Changes made:

- Added actionable optional-dependency install hints:
  - `SimulationDependencyError(..., extra="sim-cantera" | "sim-mujoco")` emits `pip install ".[...]"` remediation.
- Updated Cantera import guard:
  - `VirtualReactor._load_cantera()` now raises with `sim-cantera` install hint.
- Added explicit robotics mode selection:
  - `simulate_arm_trajectory(..., mode="auto" | "analytical" | "mujoco")`.
  - `mode="mujoco"` now raises `SimulationDependencyError` with `sim-mujoco` hint when missing.
- Added simulator contract tests (`tests/test_simulator_contracts.py`) covering:
  - deterministic outputs for OT2, VirtualReactor (mock Cantera), Robotics analytical mode
  - stable expected error codes for known-invalid inputs
  - optional Cantera golden test with tolerances (skip when unavailable)
  - MuJoCo mode behavior change and missing-dependency hint path
- Updated README with explicit simulator scope boundaries, installation extras, and benchmark reproduction commands.

Verification commands and outcomes:

- `. .venv/bin/activate && python -m pytest -q` -> `38 passed, 15 warnings`
- `. .venv/bin/activate && for f in examples/*.py; do python "$f"; done` -> all examples exit `0`
- `. .venv/bin/activate && python scripts/verify_reproducibility.py` -> `Determinism check passed: Node B output identical across 3 runs.`
- `. .venv/bin/activate && python -m eval.run_benchmark --seed 123 --n 200` -> success

## Final verification

Commands and outcomes:

- `. .venv/bin/activate && python -m pip install -e ".[dev]"` -> success
- `. .venv/bin/activate && python -m pytest -q` -> `38 passed, 15 warnings`
- `. .venv/bin/activate && for f in examples/*.py; do python "$f"; done` -> all examples exit `0`
- `. .venv/bin/activate && python scripts/verify_reproducibility.py` -> `Determinism check passed: Node B output identical across 3 runs.`
- `. .venv/bin/activate && python -m eval.run_benchmark --seed 123 --n 200` -> success
- Re-run determinism check:
  - first `summary.json` hash: `28ec46ad0b4719f5a7250d40542a7145c4c55360278ab7721038962b64c6dc9d`
  - second `summary.json` hash: `28ec46ad0b4719f5a7250d40542a7145c4c55360278ab7721038962b64c6dc9d`
  - result: identical (`byte-for-byte` determinism confirmed)
