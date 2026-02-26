# OpenAtoms Release Checklist

Use this checklist before creating a GitHub release tag.

## 1) Pre-release Validation
- [ ] Confirm working tree is clean: `git status --short`
- [ ] Run unit/integration tests with coverage:
  - `pytest tests/ --cov=openatoms --cov-report=xml --cov-fail-under=80`
- [ ] Run doctests:
  - `python -m pytest --doctest-modules openatoms/`
- [ ] Run examples:
  - `python examples/hello_atoms.py`
  - `python examples/node_a_bio_kinetic.py`
  - `python examples/node_b_thermo_kinetic.py`
  - `python examples/node_c_contact_kinetic.py`
- [ ] Verify reproducibility script:
  - `python scripts/verify_reproducibility.py`

## 2) Versioning and Changelog
- [ ] Update version in `pyproject.toml`.
- [ ] Update `CHANGELOG.md` with release notes and date.
- [ ] Add explicit `Breaking changes / deprecations` subsection in `CHANGELOG.md` (or state `None`).
- [ ] Ensure `README.md` citation version matches release version.

## 3) Build Artifacts
- [ ] Build source and wheel:
  - `python -m build`
- [ ] Smoke-test local install from wheel:
  - `python -m venv /tmp/openatoms-release-test`
  - `/tmp/openatoms-release-test/bin/pip install dist/*.whl`
  - `/tmp/openatoms-release-test/bin/python -c "import openatoms; print(openatoms.__all__[0])"`

## 4) GitHub Release
- [ ] Commit release prep changes.
- [ ] Create annotated tag:
  - `git tag -a vX.Y.Z -m "OpenAtoms vX.Y.Z"`
- [ ] Push branch and tag:
  - `git push origin main`
  - `git push origin vX.Y.Z`
- [ ] Confirm `.github/workflows/release.yml` ran and attached artifacts.
- [ ] Confirm CI matrix artifacts built successfully (`core`, `sim-cantera`, optional `sim-mujoco`).

## 5) DOI and Citation
- [ ] Ensure `.zenodo.json` metadata is accurate.
- [ ] Ensure `CITATION.cff` metadata/version is accurate.
- [ ] Create or confirm Zenodo archive for the release tag.
- [ ] Add DOI badge to `README.md` once DOI is minted.

## 6) Optional PyPI Publication
- [ ] Publish signed artifacts to PyPI.
- [ ] Verify `pip install openatoms==X.Y.Z` works in clean environment.
