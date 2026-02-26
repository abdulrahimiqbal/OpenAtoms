# OpenAtoms Reproducibility Layer

This document defines the OpenAtoms reproducibility contract for AI-driven science workflows.

## What OpenAtoms Guarantees

- Deterministic IR generation for equal inputs and seeds.
- Deterministic, auditable Experiment Bundles (OEB) with explicit file hashes.
- Re-runnable deterministic checks (`validate`, IR-level `dry_run`, optional simulators).
- Stable verification/replay error codes (`OEB001`-`OEB006`).
- Optional tamper-evident signing for CI/internal provenance (`hmac-sha256`).

## What OpenAtoms Does Not Guarantee

- Scientific validity certification of simulation outputs.
- Regulatory, clinical, or safety certification.
- Replacement for calibrated instruments, SOPs, or human oversight.

Simulator outputs are heuristic unless independently validated for the target domain.

## Recommended Workflows

- AI agent gating:
  - Compile IR, run deterministic checks, create/sign OEB, block downstream execution on verify failure.
- Paper artifact bundle:
  - Attach OEB directory or zip to publication supplements for independent audit.
- Regression suite:
  - Store known-good OEBs in CI and replay in strict mode.
- Multi-site replay:
  - Share signed OEBs and compare replay reports across sites.

## End-to-End Example

### 1) Build deterministic IR through the public API

```bash
python - <<'PY'
import json
from openatoms import (
    Q_,
    Container,
    Matter,
    Move,
    Phase,
    build_protocol,
    compile_protocol,
    create_protocol_state,
)

source = Container(id="A1", label="A1", max_volume=Q_(300, "microliter"), max_temp=Q_(80, "degC"), min_temp=Q_(4, "degC"))
dest = Container(id="A2", label="A2", max_volume=Q_(300, "microliter"), max_temp=Q_(80, "degC"), min_temp=Q_(4, "degC"))
source.contents.append(Matter(name="water", phase=Phase.LIQUID, mass=Q_(100, "milligram"), volume=Q_(100, "microliter")))
state = create_protocol_state([source, dest])
protocol = build_protocol("oeb_demo", [Move(source, dest, Q_(50, "microliter"))], state=state)
payload = compile_protocol(protocol)
with open("protocol.ir.json", "w", encoding="utf-8") as fh:
    json.dump(payload, fh, sort_keys=True, separators=(",", ":"))
PY
```

### 2) Create and verify a deterministic bundle

```bash
openatoms bundle create \
  --ir protocol.ir.json \
  --output ./oeb_demo \
  --deterministic \
  --seed python_random=7 \
  --seed numpy=7 \
  --seed openatoms_internal=7

openatoms bundle verify --bundle ./oeb_demo
openatoms bundle replay --bundle ./oeb_demo --strict
```

### 3) Sign and verify signature

```bash
export OPENATOMS_BUNDLE_SIGNING_KEY="replace-with-ci-secret"
openatoms bundle sign --bundle ./oeb_demo --key-env OPENATOMS_BUNDLE_SIGNING_KEY
openatoms bundle verify-signature --bundle ./oeb_demo --key-env OPENATOMS_BUNDLE_SIGNING_KEY
```

### 4) JSON-mode automation friendly output

```bash
openatoms bundle verify --bundle ./oeb_demo --json
openatoms bundle replay --bundle ./oeb_demo --strict --json
```

## Error Taxonomy

- `OEB001`: Missing required file/path.
- `OEB002`: Hash mismatch / tamper evidence failure.
- `OEB003`: Bundle or schema incompatibility.
- `OEB004`: Signature invalid or unverifiable.
- `OEB005`: Replay mismatch.
- `OEB006`: Bundle manifest/structure invalid.
