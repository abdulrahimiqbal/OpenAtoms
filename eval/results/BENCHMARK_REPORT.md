# BENCHMARK REPORT

- Date: 2026-02-26
- N: 200
- Seed: 123
- Suite: realistic
- Suite definition: Plausible protocol envelopes with low-rate injected violations.
- Injection probability: 0.1
- Injection method: Violations are injected independently per protocol with Bernoulli(p), then sampled uniformly from {source_depletion, destination_overflow, thermal_limit}.
- Schema version: 1.1.0
- Schema resource: schema_v1_1_0.json
- Baseline: Pass protocol proposals directly to execution checks without repair.
- Violation definition: A protocol is counted as violating when OpenAtoms dry_run raises a PhysicsError.

## Violation Rates

| Condition | Violations | Violation rate | 95% Wilson CI |
| --- | ---: | ---: | --- |
| baseline (no_validation) | 27 / 200 | 0.135000 | [0.094465, 0.189293] |
| with_validators | 0 / 200 | 0.000000 | [0.000000, 0.018846] |

## Detection

- TP: 27
- FP: 0
- FN: 0
- TN: 173
- TP rate: 1.000000 (95% CI [0.875441, 1.000000])
- FP rate: 0.000000 (95% CI [0.000000, 0.021723])

## Correction

- Attempts: 27
- Successful (valid + intent-preserving): 6
- Success rate: 0.222222 (95% CI [0.106071, 0.407573])
- Intent-preservation rate: 0.895000 (95% CI [0.844819, 0.930293])

- Relative violation reduction: 1.000000
- Git commit: 5c49bad9a07841ae8d442dd14e74db89d6a3c88c

## Reproduction

`python -m eval.run_benchmark --seed 123 --n 200 --suite realistic --violation-probability 0.1`
