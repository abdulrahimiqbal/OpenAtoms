# OpenAtoms Scientific Notes

## Physical Models Used
- **Thermo-kinetic node (H2/O2 proof of concept)**: full Cantera reactor-network ODE integration using `ReactorNet` + `IdealGasReactor`/`IdealGasConstPressureReactor` with mechanism `h2o2.yaml`.
  - Integrator: CVODE (Cantera default).
  - Solver tolerances: `rtol=1e-9`, `atol=1e-15`.
  - Trajectories record per-step solver states (`T`, `P`, species mole fractions, inferred heat-release-rate proxy) and solver/mechanism provenance (`mechanism_file`, `mechanism_hash`, `cantera_version`, tolerances, integrator).
- **Bio-kinetic node**: deterministic liquid transfer accounting with volume feasibility checks and concentration update equation:
  - `C_final = (C1*V1 + C2*V2) / (V1 + V2)`
- **Contact-kinetic node**: analytical mechanics checks (grasp stability, stress safety factors, and workspace torque/collision heuristics), with optional MuJoCo runtime availability detection.

## Validation
Published ignition-delay reference points for stoichiometric `H2/O2/N2` at `1 atm` are encoded in `openatoms/sim/validation/h2o2_ignition_data.py`:
- 1000 K: 0.18 ms
- 1100 K: 0.045 ms
- 1200 K: 0.012 ms
- 1300 K: 0.004 ms

Reference source: Slack & Grillo (1977), aligned with common GRI validation behavior for this chemistry envelope.

Acceptance bound is set to **25% relative error**. This is intentionally pragmatic for mechanism/initial-condition differences while still tight enough to reject non-physical or numerically unstable implementations.

## What `check_type` Means
- `safety_gate`: deterministic policy/safety gating output (including threshold checks over real simulation output).
- `validated_simulation`: full ODE simulator output with recorded mechanism + solver provenance.
- `not_simulated`: no applicable real simulator was available for the action set; no physics result is fabricated.

## Noise Model Basis
`openatoms/sim/noise.py` injects seeded perturbations using published instrument-scale assumptions:
- Pipette variability: ~1-3% CV (typical automated liquid handler spec range, including Opentrons-class instruments).
- Thermocouple uncertainty: ±0.5 degC (common Type K class tolerance near room temperature).
- Pressure transducer uncertainty: ±0.25% full scale (typical industrial transducer tolerance class).

## Robustness Threshold Justification (95%)
A protocol is marked research-ready when stochastic pass rate is `>=0.95`. This threshold follows common engineering validation practice where procedures with >5% failure probability are treated as operationally unstable and unsuitable for unattended execution.

## What Is Not Validated
- OpenAtoms does **not** certify mechanism truth; kinetics/thermochemistry validity depends on selected Cantera mechanism and domain assumptions.
- OpenAtoms does **not** replace hardware calibration or regulatory safety review.
- OpenAtoms does **not** model every coupled phenomenon (e.g., detailed turbulence, multiphase transport, full robot contact dynamics without MuJoCo).
