Steps to complete (build plan)

Repo + “trust signals” baseline

Add SECURITY.md, contribution guidelines, support policy.

Enable GitHub dependency graph + basic security tooling.

Add CI workflows (tests, lint, type-check, packaging checks).

Publish versioned releases + changelog + upgrade notes.

Lock down the OpenAtoms “IR” (Intermediate Representation)

Define a versioned, schema-first protocol spec (JSON Schema / generated schema).

Add stable IDs + references (containers, labware, devices, materials).

Introduce a units system (typed quantities + conversions) across the core model.

Production-grade validation (“deterministic linter”)

Expand constraints beyond today’s basics (capacity/temp) into:

ordering rules, compatibility, hazard classes, device capability bounds

Add capability profiles (compile/validate against a target’s declared limits).

Version the error payload contract (so agents can reliably self-correct).

Runtime + executor hardening

Upgrade “DAG” from an ordered list to real dependency semantics (resources/locks).

Define idempotency + retries + failure modes (fail-closed defaults).

Add policy hooks (approvals for risky actions, rate limits, safety profiles).

Simulation becomes a mandatory gate

Build a simulation harness with:

deterministic seeds, pass/fail thresholds, regression datasets

Standardize StateObservation artifacts + storage format for provenance.

Drivers/adapters become a real ecosystem

Standard driver contract: capability discovery, health checks, secure config, retries.

Make every adapter mockable (so you can test without real hardware).

Add a “driver conformance kit” so third parties can implement safely.

Observability + provenance (platform-grade)

Every run produces: IR hash, simulator version, driver versions, timestamps, outcomes.

Correlation IDs everywhere (errors, state observations, execution logs).

Replay tooling: “same IR + same sim version + same seed ⇒ same result”.

Docs that match reality

Fix README/API mismatches.

Turn examples into “executable docs” that CI runs.

Add onboarding paths: “hello world” → “simulated run” → “real device run”.

Package the proof demos

Ship 2–4 polished, repeatable “state-of-the-art” end-to-end demos as acceptance tests.

Tests to complete (verification plan)
A) Core correctness + safety

Unit tests for all physics/constraint rules

overflow, overheating, invalid sequencing, incompatible transfers, etc.

Rollback integrity tests

ensure dry_run() restores container state on every failure (already started—expand coverage).

Negative tests

“unsafe protocols must fail closed” (no partial execution).

B) IR + schema contract

Schema validation tests

every exported IR validates against the versioned schema.

Backward/forward compatibility tests

“old IR versions still load” (within declared support window).

Golden file tests

fixed IR inputs produce byte-for-byte stable exports (or stable canonical form).

C) Units + dimensions

Unit conversion tests

mL↔L, °C↔K (if supported), time units, etc.

Dimensional analysis tests

invalid operations rejected (e.g., adding volume to temperature).

D) Determinism + reproducibility

Deterministic simulation tests

same IR + seed + sim version ⇒ same StateObservation + pass/fail.

Replay tests

stored provenance can reproduce the same decision outcome.

E) Simulation contract + regression

Simulation harness contract tests

simulator adapters conform to required inputs/outputs (including StateObservation format).

Regression suite

curated scenarios that must never flip from pass→fail (or vice versa) without an intentional version bump.

F) Property-based / fuzz testing

Random protocol generation

fuzz actions/parameters to ensure:

no crashes

consistent error typing

fail-closed behavior under weird inputs

G) Adapter/driver integration (no real hardware)

Mock server tests for HTTP/MQTT-based adapters

retries, timeouts, idempotency keys, auth failures, malformed responses.

Capability profile enforcement tests

compile/execute must refuse when target can’t satisfy requirements.

H) Driver conformance suite (ecosystem test)

A standardized test pack that any driver must pass:

discovery, limits enforcement, safe defaults, error mapping, cancellation behavior.

I) Hardware-in-the-loop (HIL) gates (when you’re ready)

Smoke HIL

minimal safe protocols on real devices (Opentrons, etc.) with strict interlocks.

Soak / stability

repeated runs to catch flaky networking, drift, timing issues.

J) CI/CD + release quality gates

Lint + type-check + unit tests + coverage thresholds.

Packaging/install tests (clean env install, optional “science” extras).

“Examples run in CI” tests (docs-as-tests).

K) Security + supply chain

OpenSSF Scorecard in CI + badge target.

Dependency scanning enabled + policy for vulnerability response.

SLSA-aligned build checks (artifact integrity, provenance for releases).

L) End-to-end acceptance tests (your “proof” demos)

Self-correcting agent loop: unsafe proposals rejected with machine-readable errors → corrected protocol passes sim gate.

One IR → multiple targets: same IR executes (or compiles) to two adapters with consistent provenance.

Thermo safety envelope demo: simulation blocks an unsafe exothermic/pressure-risk scenario with a stored observation artifact.
