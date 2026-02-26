# OpenAtoms Scientific Notes

## Physical Models Used
- **Thermo-kinetic node**: Cantera gas-phase thermodynamic state calculations with mechanism files (default `h2o2.yaml`).
  - Reactor trajectories are generated from Cantera initial/equilibrium endpoints with deterministic time interpolation.
  - Thermal-runaway detection uses explicit `dT/dt` threshold logic (`>100 K/s` sustained for `>=0.1 s`).
- **Bio-kinetic node**: deterministic liquid transfer accounting with volume feasibility checks and concentration update equation:
  - `C_final = (C1*V1 + C2*V2) / (V1 + V2)`
- **Contact-kinetic node**: analytical mechanics checks (grasp stability, stress safety factors, and workspace torque/collision heuristics), with optional MuJoCo runtime availability detection.

## Approximations and Why They Exist
- Thermo trajectories currently use endpoint-informed interpolation rather than full stiff ODE integration in this environment for deterministic runtime stability.
- Contact node collision checks use geometric approximations (deck proximity/workspace bounds) when MuJoCo is unavailable.
- Solubility checks use fixed lookup limits at nominal conditions, not full temperature-dependent activity models.

These approximations are explicit so users can decide when higher-fidelity simulators are required.

## Noise Model Basis
`openatoms/sim/noise.py` injects seeded perturbations using published instrument-scale assumptions:
- Pipette variability: ~1-3% CV (typical automated liquid handler spec range, including Opentrons-class instruments).
- Thermocouple uncertainty: ±0.5 degC (common Type K class tolerance near room temperature).
- Pressure transducer uncertainty: ±0.25% full scale (typical industrial transducer tolerance class).

## Robustness Threshold Justification (95%)
A protocol is marked research-ready when stochastic pass rate is `>=0.95`. This threshold follows common engineering validation practice where procedures with >5% failure probability are treated as operationally unstable and unsuitable for unattended execution.

## What Is Not Validated
- OpenAtoms does **not** certify underlying mechanism truth; kinetics/thermochemistry validity depends on the selected Cantera mechanism file.
- OpenAtoms does **not** replace hardware calibration or regulatory safety review.
- OpenAtoms does **not** model every coupled phenomenon (e.g., detailed turbulence, multiphase transport, full robot contact dynamics without MuJoCo).

The intended use is deterministic protocol sanity filtering and correction-loop guidance before hardware execution.
