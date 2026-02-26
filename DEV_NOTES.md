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
