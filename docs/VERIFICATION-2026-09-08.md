# Verification record — September 8, 2026

This records executed software checks, not scientific-validity certification.

## Scope and repair

The starting source was `8ef6f1047d98766dd719d9f4a57fa2abf9c29f9d`.
GitHub rejected the CI workflow before running jobs because the ignition-delay
command contained YAML-significant `: ` text in an unquoted scalar. That command
now uses a block scalar. The workflow also supports manual dispatch.

A clean local environment exposed a second issue: the packaging test builds with
`--no-isolation`, but the development extra did not install its build backend.
`setuptools` and `wheel` are now explicit development dependencies. No scientific
results or numerical assertions were altered to make this pass.

The first hosted run then exposed a pre-existing Python-version mismatch:
Pint 0.25 requires Python 3.11, while the package and CI support Python 3.10.
Dependency markers now select Pint 0.24.4 on Python 3.10 and Pint 0.25+ on newer
Python. This preserves the declared Python floor; the hosted Python 3.10 jobs
are the verification for that compatibility path.

The core-only hosted environment also exposed the BCI tests' direct NumPy
import. NumPy is now declared in the development extra instead of being supplied
incidentally by Cantera. Optional simulator installation is still not required
for the core package.

Hosted pytest also exposed environment-dependent tests: local-mode subprocess
tests inherited GitHub's `CI=true`, and one Cantera test lacked the optional
dependency guard used by the other simulator tests. The subprocess helper now
isolates the four mode flags, with an added assertion that generic CI cannot
skip missing Cantera. The simulator test skips only when Cantera is absent and
is explicitly included in the required Cantera job, where its original physical
assertions still execute. This keeps the minimal installation genuinely minimal.

Finally, the wheel-install smoke command used a shell double-quoted Python
string containing the JSON Schema key `$id`. The shell expanded that key before
Python saw it. The command now uses a quoted heredoc and Python isolated mode,
preserving the key and checking the installed wheel rather than local source.

## Executed locally

macOS arm64, Python 3.14.5; an isolated environment installed with
`python -m pip install -e '.[dev,cantera]'`.

| Check | Result |
| --- | --- |
| Full `CI=true pytest -q` suite | 95 passed; 31 deprecation warnings; 59.08 seconds |
| CI's selected Ruff checks | Passed |
| `mypy --follow-imports=skip openatoms/api.py openatoms/ir/__init__.py` | Passed |
| `OPENATOMS_CI=1 python scripts/verify_reproducibility.py` | Passed; identical Node B outputs across three runs |
| Workflow YAML parse | Passed; three jobs recognized |

Relevant installed versions: Cantera 3.2.0, Pydantic 2.13.5, Pint 0.25.3,
pytest 9.1.1, Ruff 0.16.6, mypy 2.3.1. These are an environment record,
not a dependency lock or a guarantee for every future dependency resolution.

## Executed on GitHub

Source revision `1227448ba2b9a4e49255d21220b47c03002f9424` passed
[CI run 34251014702](https://github.com/abdulrahimiqbal/OpenAtoms/actions/runs/34251014702)
on Ubuntu with Python 3.10.21:

- Required core job: passed. Main pytest invocation: 81 passed, 14 skipped.
  Lint, public-surface typing, bundle checks, examples, minimal installation,
  source/wheel build, and isolated wheel schema validation also passed.
- Required Cantera job: passed. Three-run output reproducibility, 13 integration
  and simulator tests, and the ignition-delay smoke check passed.
- Optional all-extras import smoke: passed; this is not full behavioral testing
  of every hardware integration.

[CodeQL run 34251014739](https://github.com/abdulrahimiqbal/OpenAtoms/actions/runs/34251014739)
also passed on that revision. A successful scan is not a security certification.
These hosted results apply to the linked source revision; this section is a
later documentation-only update recording those results.

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
