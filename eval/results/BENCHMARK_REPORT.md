# BENCHMARK REPORT

- Date: 2026-02-26
- N: 200
- Seed: 123
- Schema version: 1.1.0
- Baseline: Pass protocol proposals directly to execution checks without repair.
- Violation definition: A protocol is counted as violating when OpenAtoms dry_run raises a PhysicsError.

## Results

| Condition | Violations | Violation rate | 95% Wilson CI |
| --- | ---: | ---: | --- |
| baseline (no_validation) | 152 / 200 | 0.760000 | [0.696265, 0.813935] |
| with_validators | 9 / 200 | 0.045000 | [0.023852, 0.083298] |

- Relative violation reduction: 0.940789
- Git commit: 49dc8296b0d94950e12f788f8aff2749b7761e3e

## Reproduction

`python -m eval.run_benchmark --seed 123 --n 200`
