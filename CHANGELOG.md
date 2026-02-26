# Changelog

All notable changes to this project are documented in this file.

## [Unreleased] - 2026-02-26

### Added

- Wheel/install smoke tests that build local wheels and validate packaged IR schema loading/validation.
- CI matrix jobs for `core`, `sim-cantera`, and optional `sim-mujoco`.
- Reproducibility script behavior tests for CI fail-closed and local skip gating.
- Benchmark suite redesign (`realistic`, `stress`, `fuzz`) with probabilistic violation injection and deterministic artifacts.
- Detection/correction benchmark metrics with confidence intervals.
- `SAFETY.md` with operational safety boundaries and required human oversight.

### Changed

- Canonical IR API now exposes `schema_version()` and `schema_resource_name()` in `openatoms.ir`.
- Runtime benchmark metadata now records schema resource name and suite/injection definitions.
- `verify_reproducibility.py` now fails in CI when Cantera is unavailable and only allows local skip via `OPENATOMS_ALLOW_SKIP=1`.
- Gibbs feasibility no longer relies on undocumented `N2 -> N` fallback behavior.

### Breaking changes / deprecations

- Deprecated wrappers: `openatoms.ir.get_schema_version()` and `openatoms.ir.get_schema_path()`. Use `schema_version()` and `schema_resource_name()`.
- Removed undocumented chemistry fallback for unsupported species in Gibbs feasibility checks; unsupported species now raise `ReactionFeasibilityError`.

### Verification

- `pytest -q`: passed
- `python examples/hello_atoms.py`: passed
- `python scripts/verify_reproducibility.py`: passed
- `python -m build`: passed

## [0.2.0] - 2026-02-26

### Added

- Trust/safety baseline documents:
  - `SECURITY.md`
  - `CONTRIBUTING.md`
  - `SUPPORT.md`
  - `UPGRADE.md`
- Versioned IR contract:
  - `openatoms/ir.py` with `ir_version=1.1.0`
  - JSON Schema at `openatoms/schemas/ir-1.1.0.schema.json`
  - Backward-load path for `1.0.0` payloads via `load_ir_payload(...)`
- Stable IDs and reference tables:
  - deterministic IDs (`openatoms/ids.py`)
  - container/material reference export in protocol payload
- Typed units + conversions:
  - `Quantity` support for `volume`, `temperature`, `time` (`openatoms/units.py`)
  - conversion helpers consumed by core model and action constructors
- Capability profiles and deterministic validation:
  - `CapabilityProfile` (`openatoms/profiles.py`)
  - ordering rules + capability bound checks integrated in `ProtocolGraph.dry_run(...)`
- Runtime policy/provenance/replay:
  - policy hooks + hazard approval policy (`openatoms/policy.py`)
  - run provenance envelope (`openatoms/provenance.py`)
  - replay signature tooling (`openatoms/replay.py`)
- Simulation gate primitives:
  - deterministic simulation harness + threshold checks (`openatoms/sim/harness.py`)
  - standardized StateObservation schema version field
- Driver ecosystem hardening:
  - adapter contract methods (`discover_capabilities`, `health_check`, `secure_config_schema`)
  - conformance kit (`openatoms/driver_conformance.py`)
  - adapter mockability hooks for HTTP/MQTT clients
- CI/security/release automation:
  - expanded CI workflow (`.github/workflows/pytest.yml`)
  - security workflow (`.github/workflows/security.yml`)
  - CodeQL workflow (`.github/workflows/codeql.yml`)
  - release workflow (`.github/workflows/release.yml`)
  - Dependabot config (`.github/dependabot.yml`)
- Verification coverage expansion:
  - IR/schema tests
  - units/dimensions tests
  - DAG dependency semantics tests
  - determinism/replay tests
  - simulation harness/regression artifact tests
  - property-style fuzz safety tests
  - runner hardening/idempotency tests
  - driver conformance suite tests
  - acceptance demo tests
  - examples-as-tests execution

### Changed

- `ProtocolGraph` moved from ordered-list execution to dependency-aware node semantics with topological validation.
- `ProtocolGraph.export_json()` now emits deterministic, schema-validated IR payloads with `ir_version`, `schema_version`, and references.
- `Action` base class now carries simulation observation metadata for science-mode validation flows.
- `ProtocolRunner` now enforces fail-closed behavior with retry bounds, simulation gating, policy hooks, idempotency cache, and provenance output.
- Adapter implementations now expose capability/health/config discovery endpoints and retain dry-run-first execution guarantees.
- README onboarding updated to align with executable examples and current runtime behavior.

### Verification

- `pytest`: `45 passed`
- `ruff check .`: passed
- `mypy openatoms`: passed

### Notes

- See `UPGRADE.md` for compatibility guidance.
