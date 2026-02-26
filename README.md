# OpenAtoms

## What It Does
OpenAtoms takes an AI-generated protocol plan, compiles it into a deterministic `ProtocolGraph`, validates hard physical invariants (volume, thermal safety, and mass conservation), optionally runs domain simulators (bio-kinetic, thermo-kinetic, contact-kinetic), and emits versioned, hash-addressable IR JSON for reproducible execution and agent feedback loops.

## Why It Matters
Example: an agent proposes aspirating `200 uL` from a well that contains `150 uL`. Without validation this becomes a runtime liquid-handling fault; OpenAtoms catches it in dry-run, returns a structured `PhysicsError` with an actionable remediation hint, and the corrected transfer volume then passes simulation.

## Architecture
```text
LLM / Tool Agent
      |
      v
ProtocolGraph (typed actions + dependencies)
      |
      v
Deterministic Validators
(volume, thermal, mass, ordering)
      |
      v
Simulation Registry
  - Node A: OT2Simulator
  - Node B: VirtualReactor (Cantera-backed thermodynamics)
  - Node C: RoboticsSimulator (MuJoCo-aware fallback)
      |
      v
StateObservation + PhysicsError(remediation_hint)
      |
      v
LLM correction loop / exported IR JSON (v1.1.0)
```

## Three Simulation Nodes
Node A (`openatoms/sim/registry/opentrons_sim.py`) validates pipetting protocols against aspiration availability, deck layout collisions, and per-well dispense accounting; concentrations can be tracked with `MolarityTracker` in [`examples/node_a_bio_kinetic.py`](examples/node_a_bio_kinetic.py).

Node B (`openatoms/sim/registry/kinetics_sim.py`) provides thermo-kinetic trajectory generation, thermal runaway detection (`dT/dt` thresholding), and Gibbs-feasibility checks; demonstrations are in [`examples/node_b_thermo_kinetic.py`](examples/node_b_thermo_kinetic.py).

Node C (`openatoms/sim/registry/robotics_sim.py`) checks grasp force feasibility, vial contact stress vs. material yield limits, and trajectory torque/collision risks with MuJoCo-aware fallback behavior; demonstrations are in [`examples/node_c_contact_kinetic.py`](examples/node_c_contact_kinetic.py).

## Benchmark Results
Source: [`eval/results/BENCHMARK_REPORT.md`](eval/results/BENCHMARK_REPORT.md)

| Metric | Value |
| --- | --- |
| Baseline violation rate | 0.8000 |
| OpenAtoms violation rate | 0.0000 |
| Relative violation reduction | 1.0000 |
| Chi-squared (df=1) | 26.6667 |
| p-value | 0.000000 |
| Cohen's h | 2.2143 |
| Cost per valid protocol | 1620.00 |

## Quick Start
```bash
python examples/hello_atoms.py
```

## Current Limitations
- Thermo node currently uses deterministic Cantera-backed endpoint interpolation for performance; it is not a full stiff ODE reactor net in this environment.
- MuJoCo integration is optional; when unavailable, Node C falls back to analytical dynamics checks.
- Gibbs feasibility is mechanism-dependent; if species are absent in the selected Cantera mechanism, OpenAtoms returns a reaction-feasibility error.
- Hardware adapters are translation-focused in this repo; production deployments still require environment-specific credentials and device-side validation.

## Citation
```bibtex
@misc{openatoms2026,
  title        = {OpenAtoms: Deterministic Validation Layer for AI-Generated Physical Protocols},
  author       = {OpenAtoms Contributors},
  year         = {2026},
  howpublished = {\url{https://github.com/abdulrahimiqbal/OpenAtoms}},
  note         = {Version 0.2.0}
}
```

## Release and DOI
- Release checklist: [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md)
- Zenodo setup guide: [`docs/ZENODO.md`](docs/ZENODO.md)
- Citation metadata: [`CITATION.cff`](CITATION.cff), [`.zenodo.json`](.zenodo.json)
