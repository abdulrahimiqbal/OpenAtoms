# Verification record — September 8, 2026

This records executed software checks, not scientific-validity certification.

## Scope and repair

The starting source was `8ef6f1047d98766dd719d9f4a57fa2abf9c29f9d`.
GitHub rejected the CI workflow before running jobs because the ignition-delay
command contained YAML-significant `: ` text in an unquoted scalar. That command
now uses a block scalar. The workflow also supports manual dispatch.

A clean local environment exposed a second issue: the packaging test builds with
`--no-isolation`, but the development extra did not install its build backend.
`setuptools` and `wheel` are now explicit development dependencies. No tests were
disabled, assertions weakened, or scientific results altered to make this pass.

## Executed locally

macOS arm64, Python 3.14.5; an isolated environment installed with
`python -m pip install -e '.[dev,cantera]'`.

| Check | Result |
| --- | --- |
| Full `pytest -q` suite | 94 passed; 31 deprecation warnings; 135.79 seconds |
| CI's selected Ruff checks | Passed |
| `mypy --follow-imports=skip openatoms/api.py openatoms/ir/__init__.py` | Passed |
| `OPENATOMS_CI=1 python scripts/verify_reproducibility.py` | Passed; identical Node B outputs across three runs |
| Workflow YAML parse | Passed; three jobs recognized |

Relevant installed versions: Cantera 3.2.0, Pydantic 2.13.5, Pint 0.25.3,
pytest 9.1.1, Ruff 0.16.6, mypy 2.3.1. These are an environment record,
not a dependency lock or a guarantee for every future dependency resolution.

## Reproduce and inspect

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev,cantera]'
pytest -q
OPENATOMS_CI=1 python scripts/verify_reproducibility.py
```

For the exact hosted run, use [GitHub Actions](https://github.com/abdulrahimiqbal/OpenAtoms/actions/workflows/pytest.yml)
and inspect its commit, job results, Python version and logs. Local macOS checks
do not establish that Ubuntu/Python 3.10 CI passed. The all-extras job remains
optional and must not be conflated with the required core and Cantera jobs.

The [bundle reproduction guide](REPRODUCIBILITY.md) documents compilation,
verification, replay, tamper-evidence signing and explicit non-guarantees.
Existing Pydantic and Cantera deprecation warnings remain follow-up work.

Checks and this repair were performed with Codex assistance. Passing software
tests does not independently validate scientific outputs, physical safety,
hardware integrations, or unaided authorship.
