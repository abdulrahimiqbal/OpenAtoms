# BENCHMARK REPORT (EXAMPLE)

This file is an example format only. Regenerate real artifacts locally with:

```bash
python -m eval.run_benchmark --seed 123 --n 200 --suite realistic --violation-probability 0.1
```

## Required Metadata

- Date: 2026-02-26
- N: 200
- Seed: 123
- Suite: realistic
- Injection probability: 0.1
- Schema version: 1.1.0
- Schema resource: schema_v1_1_0.json
- Timestamp (UTC): 2026-02-26T12:00:00+00:00
- Repo commit: 0123456789abcdef0123456789abcdef01234567

## Violation Rates

| Condition | Violations | Violation rate | 95% Wilson CI |
| --- | ---: | ---: | --- |
| baseline (no_validation) | 27 / 200 | 0.135000 | [0.094465, 0.189293] |
| with_validators | 0 / 200 | 0.000000 | [0.000000, 0.018846] |
