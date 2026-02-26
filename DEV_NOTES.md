# DEV Notes

## Stage 0: Baseline and invariants

### Environment
- Date: 2026-02-26
- Workspace: `/Users/rahim/Downloads/OpenAtoms`
- Python version used: `Python 3.14.3`
- OS info:
  - `Darwin Rahims-MacBook-Air.local 25.1.0 Darwin Kernel Version 25.1.0: Mon Oct 20 19:32:47 PDT 2025; root:xnu-12377.41.6~2/RELEASE_ARM64_T8103 arm64`
  - `ProductName: macOS`
  - `ProductVersion: 26.1`
  - `BuildVersion: 25B78`

### Exact install/baseline commands
1. `python3 -m venv .venv-stage0`
2. `. .venv-stage0/bin/activate`
3. `python -m pip install -U pip`
4. `python -m pip install -e ".[dev]"`
5. `pytest -q`
6. `python examples/hello_atoms.py`
7. `python scripts/verify_reproducibility.py`

### Baseline results (verbatim outputs; no paraphrasing)

#### `python -m pip install -U pip`
```text
WARNING: The directory '/Users/rahim/Library/Caches/pip' or its parent directory is not owned or is not writable by the current user. The cache has been disabled. Check the permissions and owner of that directory. If executing pip with sudo, you should use sudo's -H flag.
Requirement already satisfied: pip in ./.venv-stage0/lib/python3.14/site-packages (26.0)
WARNING: Retrying (Retry(total=4, connect=None, read=None, redirect=None, status=None)) after connection broken by 'NewConnectionError('<pip._vendor.urllib3.connection.HTTPSConnection object at 0x107c79d30>: Failed to establish a new connection: [Errno 8] nodename nor servname provided, or not known')': /simple/pip/
WARNING: Retrying (Retry(total=3, connect=None, read=None, redirect=None, status=None)) after connection broken by 'NewConnectionError('<pip._vendor.urllib3.connection.HTTPSConnection object at 0x106e76210>: Failed to establish a new connection: [Errno 8] nodename nor servname provided, or not known')': /simple/pip/
WARNING: Retrying (Retry(total=2, connect=None, read=None, redirect=None, status=None)) after connection broken by 'NewConnectionError('<pip._vendor.urllib3.connection.HTTPSConnection object at 0x106e751d0>: Failed to establish a new connection: [Errno 8] nodename nor servname provided, or not known')': /simple/pip/
WARNING: Retrying (Retry(total=1, connect=None, read=None, redirect=None, status=None)) after connection broken by 'NewConnectionError('<pip._vendor.urllib3.connection.HTTPSConnection object at 0x106e75a90>: Failed to establish a new connection: [Errno 8] nodename nor servname provided, or not known')': /simple/pip/
WARNING: Retrying (Retry(total=0, connect=None, read=None, redirect=None, status=None)) after connection broken by 'NewConnectionError('<pip._vendor.urllib3.connection.HTTPSConnection object at 0x106e75bd0>: Failed to establish a new connection: [Errno 8] nodename nor servname provided, or not known')': /simple/pip/
```

#### `python -m pip install -e ".[dev]"`
```text
WARNING: The directory '/Users/rahim/Library/Caches/pip' or its parent directory is not owned or is not writable by the current user. The cache has been disabled. Check the permissions and owner of that directory. If executing pip with sudo, you should use sudo's -H flag.
Obtaining file:///Users/rahim/Downloads/OpenAtoms
  Installing build dependencies: started
  Installing build dependencies: finished with status 'error'
  error: subprocess-exited-with-error
  
  × installing build dependencies did not run successfully.
  │ exit code: 1
  ╰─> [8 lines of output]
      WARNING: The directory '/Users/rahim/Library/Caches/pip' or its parent directory is not owned or is not writable by the current user. The cache has been disabled. Check the permissions and owner of that directory. If executing pip with sudo, you should use sudo's -H flag.
      WARNING: Retrying (Retry(total=4, connect=None, read=None, redirect=None, status=None)) after connection broken by 'NewConnectionError('<pip._vendor.urllib3.connection.HTTPSConnection object at 0x109c46120>: Failed to establish a new connection: [Errno 8] nodename nor servname provided, or not known')': /simple/setuptools/
      WARNING: Retrying (Retry(total=3, connect=None, read=None, redirect=None, status=None)) after connection broken by 'NewConnectionError('<pip._vendor.urllib3.connection.HTTPSConnection object at 0x108e7de50>: Failed to establish a new connection: [Errno 8] nodename nor servname provided, or not known')': /simple/setuptools/
      WARNING: Retrying (Retry(total=2, connect=None, read=None, redirect=None, status=None)) after connection broken by 'NewConnectionError('<pip._vendor.urllib3.connection.HTTPSConnection object at 0x108e7df90>: Failed to establish a new connection: [Errno 8] nodename nor servname provided, or not known')': /simple/setuptools/
      WARNING: Retrying (Retry(total=1, connect=None, read=None, redirect=None, status=None)) after connection broken by 'NewConnectionError('<pip._vendor.urllib3.connection.HTTPSConnection object at 0x108e7e210>: Failed to establish a new connection: [Errno 8] nodename nor servname provided, or not known')': /simple/setuptools/
      WARNING: Retrying (Retry(total=0, connect=None, read=None, redirect=None, status=None)) after connection broken by 'NewConnectionError('<pip._vendor.urllib3.connection.HTTPSConnection object at 0x108e7d1d0>: Failed to establish a new connection: [Errno 8] nodename nor servname provided, or not known')': /simple/setuptools/
      ERROR: Could not find a version that satisfies the requirement setuptools>=61.0 (from versions: none)
      ERROR: No matching distribution found for setuptools>=61.0
      [end of output]
  
  note: This error originates from a subprocess, and is likely not a problem with pip.
ERROR: Failed to build 'file:///Users/rahim/Downloads/OpenAtoms' when installing build dependencies
```

#### `pytest -q`
```text
zsh:1: command not found: pytest
```

#### `python examples/hello_atoms.py`
```text
Traceback (most recent call last):
  File "/Users/rahim/Downloads/OpenAtoms/examples/hello_atoms.py", line 3, in <module>
    from openatoms.actions import Move
ModuleNotFoundError: No module named 'openatoms'
```

#### `python scripts/verify_reproducibility.py`
```text
Skipping determinism check: optional dependency 'cantera' is not installed. Install with: pip install ".[sim-cantera]"
```

### Production invariants
- Deterministic IR serialization and hashing.
- Single IR schema + single validator path.
- Installable wheel contains schemas.
- Examples are executable and tested.
- CI covers: core, schemas, determinism, and optional sim extras.
- Clear safety contract for validators vs simulators.

## Stage 1: Packaging and install reproducibility

### Changes
- `pyproject.toml`
  - `requires-python` set to `>=3.10`.
  - runtime deps explicitly include `pint`, `pydantic`, `jsonschema`.
  - extras confirmed:
    - `dev`: `pytest`, `ruff`, `mypy`, `hypothesis`, `build`, `twine` (+ `pytest-cov`).
    - `sim-cantera`, `sim-mujoco`, `sim-all`.
  - schema packaging via `[tool.setuptools.package-data]` (`openatoms = ["ir/*.json"]`).
- `requirements.txt` is intentionally absent; `pyproject.toml` is the single dependency source.
- Added/expanded installation smoke tests in `tests/test_packaging_install.py`:
  - import smoke for `openatoms` and `openatoms.ir`,
  - schema load via `importlib.resources`,
  - known-good IR validation,
  - local wheel build + temp venv install + schema/validation smoke.

### Verification
- `. .venv/bin/activate && pytest -q` -> `47 passed, 15 warnings`
- `. .venv/bin/activate && python -m build --no-isolation` -> success
- Wheel smoke install and IR validation command -> `wheel-smoke-ok`

## Stage 2: Single source of truth for IR

### Changes
- Canonical IR API in `openatoms/ir/__init__.py` now exposes:
  - `validate_ir(payload: dict) -> dict`
  - `schema_version() -> str`
  - `schema_resource_name() -> str`
  - `load_schema() -> dict`
- Legacy entrypoints preserved with `DeprecationWarning`:
  - `get_schema_version()`
  - `get_schema_path()`
  - `schema_path()`
  - `legacy_validate_ir()`
- Schema validation now normalizes invalid schema payloads to stable `IRValidationError(code="IR_SCHEMA_VALIDATION")`.
- Runtime benchmark path switched to canonical schema API (`schema_version`, `schema_resource_name`).

### Hard tests added/updated
- Single schema resource assertion and duplicate-schema absence checks.
- Legacy-vs-canonical entrypoint parity tests.
- Stable invalid payload error code/type checks.

### Verification
- `rg -n "schema_v1_1_0\\.json|schema_resource_name\\(|load_schema\\(|validate_ir\\(" openatoms eval scripts`
  - runtime references resolve to `openatoms/ir/schema_v1_1_0.json` only.
- `find openatoms -name "*.json"` -> `openatoms/ir/schema_v1_1_0.json`
- `. .venv/bin/activate && pytest -q` -> `47 passed, 15 warnings`

## Stage 3: CI hardening and determinism coverage

### Changes
- `.github/workflows/pytest.yml` now runs matrix jobs:
  - `core`
  - `sim-cantera`
  - `sim-mujoco` (optional/allow-failure)
- CI now executes:
  - full `pytest -q`,
  - examples test pass (`tests/test_examples_execution.py`),
  - reproducibility script,
  - simulator-specific subsets for cantera/mujoco,
  - wheel build + wheel smoke.
- `scripts/verify_reproducibility.py` behavior:
  - if cantera missing in CI: explicit message + nonzero exit.
  - local skip allowed only with `OPENATOMS_ALLOW_SKIP=1`.
- Added `tests/test_verify_reproducibility_script.py` for CI/local skip semantics.
- Added explicit pytest marker for cantera-required examples (`requires_cantera`).

### Verification
- `. .venv/bin/activate && pytest -q tests/test_verify_reproducibility_script.py` -> pass
- `. .venv/bin/activate && python scripts/verify_reproducibility.py` -> `Determinism check passed: Node B output identical across 3 runs.`

## Stage 4: Scientifically interpretable benchmark redesign

### Changes
- Replaced structural `%4` violation forcing with Bernoulli injection:
  - `eval/generate_protocols.py` now supports suites:
    - `realistic`
    - `stress`
    - `fuzz` (edge-biased fuzz generation)
  - configurable injection probability `p` with metadata.
- `eval/run_benchmark.py` now reports:
  - suite metadata (definition, injection probability, injection method),
  - detection metrics (`TP`, `FP`, `FN`, `TN`, rates + Wilson CIs),
  - correction metrics (success + intent-proxy preservation, with CIs),
  - deterministic artifact outputs:
    - `raw_runs.jsonl`
    - `summary.json`
    - `BENCHMARK_REPORT.md`
- Added property-style fuzz test coverage (Hypothesis) with shrinking.

### Verification
- `. .venv/bin/activate && python -m eval.run_benchmark --seed 123 --n 200 --suite realistic --violation-probability 0.1 --output-dir eval/results` -> success
- Re-run same command and compare hashes:
  - `summary.json`: `c93aacd8727cd163f55aed5d46bab12bd6650057d7839b0b78224f30fb2943b0` (identical)
  - `BENCHMARK_REPORT.md`: `1fa560f4d6e653f29ca5cafa257e9fbdef1652fd314afd65f00c516599d296e8` (identical)
  - `raw_runs.jsonl`: `58d500f5f2e76c36d595498e910f9da580e3f82574bb499c218db32c6da86c13` (identical)

## Stage 5: Simulator contracts and safe defaults

### Changes
- Removed undocumented chemistry fallback heuristic in `VirtualReactor.check_gibbs_feasibility` for `N2 -> N`.
- Unsupported species now consistently raise `ReactionFeasibilityError` (fail-closed).
- Added simulator dependency contract test for missing cantera install hint:
  - `pip install ".[sim-cantera]"` remediation path asserted.
- Updated Node B example to demonstrate explicit unsupported-species error handling plus supported Gibbs check.

### Verification
- `. .venv/bin/activate && pytest -q tests/test_simulator_contracts.py -k cantera` -> pass
- `. .venv/bin/activate && pytest -q tests/test_simulator_contracts.py -k mujoco` -> pass (with deselection as applicable)
- `. .venv/bin/activate && pytest -q` -> `47 passed, 15 warnings`

## Stage 6: Production docs and release readiness

### Changes
- `README.md` rewritten with:
  - core vs extras install commands,
  - copy/paste minimal hello protocol,
  - IR schema versioning policy,
  - determinism guarantees and verification command,
  - benchmark reproduction commands and interpretation limits.
- Added `SAFETY.md` (operational boundaries, oversight, hardware disclaimers).
- Updated `RELEASE_CHECKLIST.md` to require explicit breaking/deprecation notes and CI artifact checks.
- Updated `CHANGELOG.md` with new release section including `Breaking changes / deprecations`.

## Final Definition-of-Done verification

- `pip install -e ".[dev]"` works in maintained dev environment.
- `python -m build --no-isolation` produces wheel containing schema resources.
- `pytest -q` passes (`47 passed`).
- Examples execute under tests (`tests/test_examples_execution.py`: `7 passed`).
- `scripts/verify_reproducibility.py` enforces CI non-skip behavior and passes with cantera installed.
- Exactly one runtime IR schema resource is used: `openatoms/ir/schema_v1_1_0.json`.
- Benchmarks are deterministic and include suite/injection metadata + interpretable metrics.
- Simulator contracts are explicit, deterministic, and default to documented fail-closed behavior.

## Stage 7: Four production blockers remediation (2026-02-26)

### Blocker 1 — Unified IR runtime contract

#### IR/schema inventory
- `rg -n "schema|validate|jsonschema|openatoms/schemas|schema_v1_1_0" ...` call sites include:
  - `openatoms/ir/__init__.py` (canonical load/validate path)
  - `eval/run_benchmark.py` (schema metadata)
  - `tests/test_ir_and_provenance.py`, `tests/test_packaging_install.py` (schema contract tests)
- `openatoms/schemas/` does not exist.
- `openatoms/ir.py` does not exist.

#### Changes
- Added canonical API function `get_schema_resource_name()` to `openatoms/ir/__init__.py`.
- Kept `schema_resource_name()` as deprecated forwarding alias (DeprecationWarning).
- Updated runtime call site in `eval/run_benchmark.py` to use `get_schema_resource_name()`.
- Added/updated IR tests:
  - `test_ir_schema_is_packaged()`
  - `test_ir_single_source_of_truth()`
  - legacy forwarding assertions via deprecation wrappers
- Wheel smoke test now executes:
  - `from openatoms.ir import load_schema, validate_ir`
  - `print(load_schema()['$id'])`

### Blocker 2 — Determinism CI enforcement

#### Changes
- Updated `scripts/verify_reproducibility.py`:
  - honors `OPENATOMS_CI=1` as strict CI mode.
  - missing cantera in strict CI returns nonzero with install hint.
  - local skip remains explicit via `OPENATOMS_ALLOW_SKIP=1`.
- Updated tests in `tests/test_verify_reproducibility_script.py`:
  - `test_verify_reproducibility_ci_fails_without_cantera`
  - `test_verify_reproducibility_local_can_skip`
- Updated CI workflow `.github/workflows/pytest.yml`:
  - `core` job installs `.[dev]`.
  - new `determinism-cantera` job installs `.[dev,sim-cantera]`, sets `OPENATOMS_CI=1`, runs reproducibility script.

### Blocker 3 — Benchmark artifact determinism + policy

#### Changes
- `eval/run_benchmark.py` now records stable metadata:
  - `schema_resource`, `schema_version`, `repo_commit`, `timestamp_utc`, `date`.
- Benchmark report generation remains single-source from `summary` object and now includes:
  - N, seed, suite, injection probability, schema version/resource, timestamp, repo commit.
- Deterministic writing preserved:
  - `raw_runs.jsonl` line-wise canonical JSON
  - `summary.json` sorted keys + stable indent + newline
  - report deterministic markdown + trailing newline
- Added tests:
  - `test_benchmark_determinism`
  - `test_benchmark_report_consistency`
- Artifact policy switched to **Option A** (do not commit generated results):
  - removed tracked `eval/results/summary.json` and `eval/results/BENCHMARK_REPORT.md`
  - ignored generated benchmark files in `.gitignore`
  - added docs example: `docs/BENCHMARK_REPORT_EXAMPLE.md`

### Blocker 4 — Docs/examples drift

#### Changes
- Examples harness rewritten to enumerate and run all `examples/*.py` dynamically:
  - `tests/test_examples_execution.py`
  - dependency-aware skip for cantera examples.
- README canonicalized to IR API name `get_schema_resource_name` and clarifies benchmark artifact policy.

## Final verification command outputs

Note: this environment does not provide `python` on PATH; commands were run via `.venv/bin/python` equivalent.

### 1) `python -m pip install -e ".[dev]"`

Command output (`stage0_logs/21_final_install_as_requested.log`):

```text
Obtaining file:///Users/rahim/Downloads/OpenAtoms
Installing build dependencies: finished with status 'error'
ERROR: Could not find a version that satisfies the requirement setuptools>=61.0
ERROR: No matching distribution found for setuptools>=61.0
exit_code=1
```

Offline-safe fallback executed:

```text
.venv/bin/python -m pip install -e ".[dev]" --no-build-isolation
...
Successfully installed openatoms-0.2.0
exit_code=0
```

### 2) `pytest -q`

Command output (`stage0_logs/22_final_pytest_q.log`):

```text
..................................................                       [100%]
50 passed, 15 warnings in 21.40s
exit_code=0
```

### 3) `python examples/hello_atoms.py`

Command output (`stage0_logs/23_final_hello_atoms.log`):

```text
{
  "ir_version": "1.1.0",
  "protocol_name": "Hello_Atoms",
  ...
  "schema_version": "1.1.0"
}
exit_code=0
```

### 4) `python -m build`

Command output (`stage0_logs/24_final_build_as_requested.log`):

```text
* Creating isolated environment: venv+pip...
ERROR: Could not find a version that satisfies the requirement setuptools>=61.0
ERROR: No matching distribution found for setuptools>=61.0
exit_code=1
```

Offline-safe fallback executed:

```text
.venv/bin/python -m build --no-isolation
...
Successfully built openatoms-0.2.0.tar.gz and openatoms-0.2.0-py3-none-any.whl
exit_code=0
```

### 5) Wheel smoke install test

Automated command output (`stage0_logs/25_final_wheel_smoke.log`):

```text
.                                                                        [100%]
1 passed, 10 warnings in 3.39s
exit_code=0
```

### 6) `python -m eval.run_benchmark --seed 123 --n 200 --suite realistic`

Command output (`stage0_logs/26_final_benchmark.log`):

```text
{
  "n": 200,
  "seed": 123,
  "suite": {
    "name": "realistic",
    "injection_probability": 0.1
  },
  "schema_version": "1.1.0",
  "schema_resource": "schema_v1_1_0.json",
  "repo_commit": "135d6f24bc099504dcd1b0e957551f67a631933a",
  "timestamp_utc": "2026-02-26T13:09:39-05:00",
  "with_validators": {
    "violation_rate": 0.0
  }
}
exit_code=0
```

### 7) CI determinism enforcement

- Workflow updated at `.github/workflows/pytest.yml` with required job:
  - `determinism-cantera`
  - installs `pip install -e ".[dev,sim-cantera]"`
  - sets `OPENATOMS_CI=1`
  - runs `python scripts/verify_reproducibility.py`
