# OpenAtoms Honest Audit

## What Is Actually Implemented
- `openatoms/core.py`
  - Defines `Matter`, `Container`, and `Environment` with float-centric properties (`mass_g`, `volume_ml`, `temp_c`) and optional lightweight unit conversion wrappers.
  - `Container.current_volume` sums stored matter volumes.
- `openatoms/units.py`
  - Implements a small internal `Quantity` dataclass with deterministic conversions for volume, temperature, and time.
  - Not a full dimensional analysis engine (no compound units, no uncertainty model, no chemistry-specific units).
- `openatoms/actions.py`
  - Implements `Move`, `Transform`, `Combine`, `Measure` with basic validation.
  - Move checks source volume and destination capacity; Transform checks min/max container temperature; Combine checks non-empty target.
- `openatoms/exceptions.py`
  - Implements structured `PhysicsError` and several subclasses with JSON serialization for agent-facing feedback.
- `openatoms/dag.py`
  - Implements a deterministic protocol graph with topological ordering, dependency checks, dry-run execution, and rollback-on-error behavior.
  - Exports deterministic JSON IR payload validated against internal schema.
- `openatoms/ir.py`, `openatoms/provenance.py`, `openatoms/replay.py`
  - Implements canonical JSON hashing, schema loading/validation, run context and provenance metadata, deterministic replay signatures.
- `openatoms/sim/harness.py`
  - Implements deterministic pseudo-simulation gating based on action count + seeded random noise.
  - Emits structured `StateObservation` payloads.
- `openatoms/sim/registry/kinetics_sim.py`
  - Integrates with Cantera for hydrogen-oxygen combustion simulation via `IdealGasReactor`.
  - Supports vessel burst-pressure check and raises structured errors.
- `openatoms/sim/registry/opentrons_sim.py`
  - Wraps `opentrons.simulate` invocation and maps some out-of-bounds errors to a structured failure.
- `openatoms/adapters/*`
  - Implements protocol translation layers for Opentrons, Viam, Bambu, Home Assistant, and Arduino Cloud.
  - Includes optional dispatch over HTTP/MQTT/SDK when env flags are enabled.
- `openatoms/runner.py`, `openatoms/policy.py`, `openatoms/profiles.py`, `openatoms/driver_conformance.py`
  - Implements execution orchestration, policy hooks, capability profile enforcement, and a conformance kit.

## What Is Claimed But Not Implemented
- README claims a fully realized “three science node” platform. Actual state:
  - Node A (Bio-Kinetic): no molarity tracking engine and no deck-footprint collision geometry model; wrapper mainly forwards to opentrons simulation and pattern-matches errors.
  - Node B (Thermo-Kinetic): only one specific combustion helper is implemented; no general reactor API for arbitrary reactant/product Gibbs feasibility checks.
  - Node C (Contact-Kinetic): not implemented (README says planned).
- README language implies robust stochastic robustness tooling and mandatory digital twin pass; current repo contains a deterministic pseudo-harness plus minimal registry wrappers, but no full robustness sweep framework with pass-rate criteria.
- README language implies a broad “physics compiler” model. Current validations are mostly container bounds and ordering checks, with limited first-principles simulation hooks.

## Physics Validation: Real or Threshold Checks?
- `Move.validate` in `openatoms/actions.py`: threshold checks only (source >= requested volume, destination <= max capacity, hazard compatibility set intersection).
- `Transform.validate`: threshold checks only (container min/max temperature bounds).
- `Combine.validate`: threshold check only (non-empty target).
- `ProtocolGraph._enforce_ordering_rules`: threshold checks only (positive move amount, positive combine duration).
- `SimulationHarness.run`: synthetic estimate model (temperature/pressure derived from step count plus seeded random perturbation), not a physical solver.
- `VirtualReactor.simulate_hydrogen_oxygen_combustion`: real Cantera ODE integration for one configured chemistry mechanism; this is real thermochemical simulation.
- `OpentronsSimValidator.validate_protocol`: real simulator call when dependency exists, but physical interpretation is limited to execute success/failure and simple out-of-bounds string matching.

## Test Coverage Summary
- `tests/test_units.py`: conversion correctness for internal `Quantity`; does not test full dimensional analysis.
- `tests/test_dag_dependencies.py`: DAG dependency ordering and unknown dependency rejection.
- `tests/test_determinism.py`: deterministic state consistency for harness/replay signatures.
- `tests/test_driver_conformance.py`: adapter interface conformance checks.
- `tests/test_ir_contract.py`: IR export schema contract and backward compatibility load path.
- `tests/test_sim_harness.py`: shape and deterministic behavior of synthetic simulation harness.
- `tests/test_adapters.py`: adapter dry-run enforcement and runner integration.
- `tests/test_adapters_sim.py`: simulated dispatch path behavior for adapters (mocked transport).
- `tests/test_sim_registry.py`: registry wrappers with monkeypatched fake simulators, including structural pressure failure mapping.
- `tests/test_runner_hardening.py`: retry/idempotency/policy behavior.
- `tests/test_linter.py`: expected physical guardrails (overflow, thermal violation, empty combine, compatibility, capability bounds).
- `tests/test_fuzz_protocols.py`: random protocol generation with fail-closed behavior (surface behavior checks).
- `tests/test_acceptance_demos.py`: end-to-end style checks for self-correction loop and thermo envelope behavior (mostly mocked dependencies).
- `tests/test_examples_docs.py`: example scripts exit-code smoke tests.
- `tests/e2e_real_world_demo.py`, `tests/hero_e2e_exothermic.py`: scenario demonstrations with significant mocking.

Assessment: tests are solid for API behavior and safety guardrail regression, but only a subset catches first-principles physics violations. Most tests are behavioral or contract-level rather than solver-accuracy verification.

## Dependency Audit
- `requirements.txt`
  - Current content: comment only (“OpenAtoms core currently relies on Python standard library only.”)
  - No concrete pinned runtime dependencies are declared here.
- `pyproject.toml` dependencies
  - `project.dependencies`: empty.
  - Optional `science`: `cantera>=3.0`, `opentrons>=7.0`.
  - Optional `dev`: `build`, `hypothesis`, `jsonschema`, `mypy`, `pytest`, `ruff`.

Usage audit against codebase:
- `cantera`: used in `openatoms/sim/registry/kinetics_sim.py`.
- `opentrons`: used in `openatoms/sim/registry/opentrons_sim.py`; also protocol script generation in adapter.
- `jsonschema`: optional usage in `openatoms/ir.py` for schema validation fallback.
- `hypothesis`, `pytest`: used in tests.
- `mypy`, `ruff`, `build`: tooling only.

Gaps and recommendations:
- Runtime dependencies needed by current/claimed core scientific path are not pinned in `requirements.txt`.
- No explicit unit-system dependency (e.g., `pint`) and no data-model validation dependency (`pydantic`) in current runtime.
- A lighter alternative to full Cantera does not exist for thermochemistry fidelity; Cantera remains appropriate for Node B.
