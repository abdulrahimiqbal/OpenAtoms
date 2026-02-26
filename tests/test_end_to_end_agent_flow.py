from __future__ import annotations

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
    invoke_optional_simulator,
    protocol_hash,
    protocol_provenance,
    run_dry_run,
    serialize_ir,
    validate_protocol_ir,
)


def _build_minimal_protocol():
    source = Container(
        id="A1",
        label="A1",
        max_volume=Q_(300, "microliter"),
        max_temp=Q_(80, "degC"),
        min_temp=Q_(4, "degC"),
    )
    destination = Container(
        id="A2",
        label="A2",
        max_volume=Q_(300, "microliter"),
        max_temp=Q_(80, "degC"),
        min_temp=Q_(4, "degC"),
    )
    source.contents.append(
        Matter(
            name="water",
            phase=Phase.LIQUID,
            mass=Q_(100, "milligram"),
            volume=Q_(100, "microliter"),
        )
    )
    state = create_protocol_state([source, destination])
    protocol = build_protocol(
        "agent_e2e",
        [Move(source, destination, Q_(50, "microliter"))],
        state=state,
    )
    return protocol


def test_end_to_end_agent_contract_flow() -> None:
    protocol = _build_minimal_protocol()
    assert run_dry_run(protocol) is True

    payload = compile_protocol(protocol)
    validated = validate_protocol_ir(payload)
    assert validated == payload

    ir_json = serialize_ir(protocol)
    payload_from_json = json.loads(ir_json)
    assert validate_protocol_ir(payload_from_json) == payload_from_json

    first_hash = protocol_hash(payload)
    second_hash = protocol_hash(payload_from_json)
    assert first_hash == second_hash
    assert protocol_provenance(payload)["ir_hash"] == first_hash

    protocol_repeat = _build_minimal_protocol()
    repeat_payload = compile_protocol(protocol_repeat)
    assert serialize_ir(protocol_repeat) == ir_json
    assert protocol_hash(repeat_payload) == first_hash

    opentrons_result = invoke_optional_simulator(protocol, simulator="opentrons")
    assert opentrons_result.status == "ok"

    cantera_result = invoke_optional_simulator(protocol, simulator="cantera")
    assert cantera_result.status in {"ok", "skipped"}
    if cantera_result.status == "skipped":
        assert cantera_result.reason is not None
        assert "pip install" in cantera_result.reason

    mujoco_result = invoke_optional_simulator(protocol, simulator="mujoco")
    assert mujoco_result.status in {"ok", "skipped"}
    if mujoco_result.status == "skipped":
        assert mujoco_result.reason is not None
        assert "pip install" in mujoco_result.reason

