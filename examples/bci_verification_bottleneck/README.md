# BCI Verification Bottleneck Worked Example

This worked example operationalizes the verification-bottleneck framing from Iqbal (2026): when neural signals are weak, throughput is limited by how efficiently priors compress the hypothesis space before verification. We reproduce the Bridge crossover claim that Bayesian fusion with an LLM prior dominates a uniform prior below the published d' regime, then run a closed-loop hypothesis generation loop where the model proposes BCI configurations and the simulator rejects/revises until constraints are satisfied.

## Run

```bash
python run_example.py --derco-path /path/to/derco
```

## What The Three Phases Demonstrate

1. **Phase 1 (reproduction):** reproduces the Bridge-vs-uniform d' crossover curve and validates against the published crossover near `d' ~= 1.7`.
2. **Phase 2 (scaling law):** measures current-model character entropy from API sampling and tests the scaling-law prediction that lower entropy implies larger Bridge speedup.
3. **Phase 3 (closed loop):** executes `AI proposal -> simulator validation -> structured error -> revised proposal` until a valid protocol is found.

## Bundle Output And Verification

The script writes a signed deterministic bundle to:

- `examples/bci_verification_bottleneck/outputs/bci_verification_bottleneck_bundle.zip`

Verify with:

```bash
openatoms verify outputs/bci_verification_bottleneck_bundle.zip
# canonical CLI form:
openatoms bundle verify --bundle outputs/bci_verification_bottleneck_bundle.zip
```

(If you signed with a custom key, set `OPENATOMS_BUNDLE_SIGNING_KEY` before verification.)

## Key Results

| Metric | Published Reference | Reproduction Target |
|---|---:|---:|
| Bridge crossover d' | 1.7 | within ±0.2 (or 15%) |
| GPT-2 character entropy | 2.2 bits | measured model entropy should be lower |
| GPT-2 speedup | 2.3x | measured model speedup should exceed this |
| GPT-4-class projection | 1.5 bits, 3.4x | empirical comparison point |
| N400 passive d' | ~0.00 | remain below practical threshold |
| N400 active d' | ~0.24 | remain below practical threshold |

## What This Demonstrates About OpenAtoms

This is a reproducible science artifact rather than a standalone script because the run emits a signed OpenAtoms bundle with deterministic seeds, protocol IR, provenance, simulator reports, and replayable result files. The artifact preserves the full hypothesis-evidence-correction trail so the scientific claim can be independently verified and audited.
