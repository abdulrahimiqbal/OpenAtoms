# OpenAtoms Honest Audit

## What Is Implemented
- `openatoms/sim/registry/kinetics_sim.py`
  - `VirtualReactor.simulate_reaction` performs real Cantera stiff ODE integration through `ReactorNet` (CVODE).
  - Trajectories include solver tolerances, mechanism filename/hash, integrator, and Cantera version.
  - `VirtualReactor.compute_ignition_delay` computes ignition delay as the time of peak `dT/dt`.
  - `VirtualReactor.simulate_hydrogen_oxygen_combustion` is now a real ODE-backed helper (not interpolated endpoints).
- `openatoms/sim/harness.py`
  - `SimulationHarness` routes by DAG action types.
  - For unsupported action sets it returns `status="not_simulated"` with `check_type="not_simulated"`.
  - It never fabricates arithmetic pseudo-physics.
  - When a real simulator runs, threshold checks are applied as `check_type="safety_gate"`.
- `openatoms/bundle.py`
  - Dry-run and simulator reports now carry `check_type`.
  - Cantera reports include `mechanism_file` and `mechanism_hash`.
  - Bundle `manifest.json` now includes `physics_inputs` for simulator-critical inputs.

## What Is Explicitly Not Claimed
- OpenAtoms does not claim regulatory-grade certification.
- OpenAtoms does not claim universal chemistry coverage; this proof-of-concept path is hydrogen/oxygen using `h2o2.yaml`.
- OpenAtoms does not claim full multiphysics closure beyond represented models.

## Removed Legacy Behavior
- The previous deterministic interpolation shortcut in thermo kinetics is removed from the active simulation path.
- The previous arithmetic simulation harness estimate (`20 + steps*5 + noise`) is removed.
