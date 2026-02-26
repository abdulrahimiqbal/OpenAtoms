# Upgrade Notes

## Upgrading to 0.2.0

### IR Contract

- Exported protocol payloads now include `ir_version` and may include node metadata.
- Consumers should read `schema_version`/`ir_version` instead of assuming fixed payload shape.

### Error Contract

- Structured errors now include `error_contract_version`.
- Agents should key self-correction logic on `error_type` + `error_contract_version`.

### Runner Output

- `ProtocolRunner.run(...)` returns deterministic run metadata (`run_id`, timestamps, IR hash, and adapter metadata) alongside adapter output.

### Adapter Contract

- Adapters now expose:
  - `discover_capabilities()`
  - `health_check()`
  - `secure_config_schema()`

Existing code that only calls `execute(...)` remains supported.
