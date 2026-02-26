# OpenAtoms Safety Boundaries

OpenAtoms is a software safety gate for protocol validation. It is not a replacement for trained operators, validated SOPs, or certified hardware safety systems.

## Operational Scope

OpenAtoms is designed to:
- enforce deterministic protocol validation before execution,
- return structured machine-readable error taxonomy and remediation hints,
- provide optional simulator checks for specific risk classes.

OpenAtoms does not:
- guarantee biological, chemical, or mechanical process success,
- certify sterility, contamination control, or regulatory compliance,
- substitute emergency interlocks, E-stops, fume handling, or PPE.

## Required Human Oversight

Production usage requires:
- qualified operator review of each generated protocol,
- approval gates for hazardous operations,
- environment-specific preflight checks (hardware status, consumables, containment),
- post-run audit of logs and anomalies.

## Simulator Safety Contracts

- `OT2Simulator`: pipetting/deck collision/volume gates only.
- `VirtualReactor`: thermo feasibility and runaway/limit checks; mechanism coverage required.
- `RoboticsSimulator`: deterministic analytical collision/torque/stress checks with optional MuJoCo mode.

None of these simulators are calibration substitutes for physical instruments.

## Safe Defaults and Dependency Handling

- Optional simulator dependencies are explicit extras:
  - `pip install ".[sim-cantera]"`
  - `pip install ".[sim-mujoco]"`
- Missing optional dependencies must fail closed for CI reproducibility checks.
- Undocumented chemistry heuristics are not enabled in production mode.

## Hardware Disclaimers

Before any real-world execution:
- validate adapter mappings to the exact hardware model and firmware,
- verify unit conversions and deck coordinates against manufacturer references,
- run dry-runs in non-hazard mode,
- maintain operator-controlled abort paths.

## Incident Handling

If a potentially unsafe behavior is observed:
1. Stop execution immediately.
2. Preserve logs/artifacts (IR payload, simulator outputs, benchmark traces).
3. File a security/safety report via [SECURITY.md](SECURITY.md) and internal incident channels.
