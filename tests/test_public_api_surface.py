from __future__ import annotations

import inspect
from typing import get_type_hints

import openatoms
import openatoms.api as public_api

EXPECTED_PUBLIC_API = [
    "ProtocolState",
    "SimulatorInvocation",
    "build_protocol",
    "compile_protocol",
    "create_protocol_state",
    "invoke_optional_simulator",
    "protocol_hash",
    "protocol_provenance",
    "run_dry_run",
    "serialize_ir",
    "validate_protocol_ir",
]


def test_public_api_symbols_are_explicit_and_stable() -> None:
    assert list(public_api.__all__) == EXPECTED_PUBLIC_API
    for symbol in EXPECTED_PUBLIC_API:
        assert hasattr(openatoms, symbol), f"openatoms.__init__ must re-export {symbol}"


def test_public_api_signatures_are_stable() -> None:
    build_sig = inspect.signature(public_api.build_protocol)
    assert list(build_sig.parameters) == ["name", "actions", "state"]
    assert build_sig.parameters["state"].kind is inspect.Parameter.KEYWORD_ONLY

    compile_sig = inspect.signature(public_api.compile_protocol)
    assert list(compile_sig.parameters) == ["protocol", "run_dry_run_gate", "mode"]
    assert compile_sig.parameters["run_dry_run_gate"].default is True

    validate_sig = inspect.signature(public_api.validate_protocol_ir)
    assert list(validate_sig.parameters) == ["payload", "check_invariants"]
    assert validate_sig.parameters["check_invariants"].default is True

    invoke_sig = inspect.signature(public_api.invoke_optional_simulator)
    assert list(invoke_sig.parameters) == ["protocol", "simulator"]
    assert invoke_sig.parameters["simulator"].kind is inspect.Parameter.KEYWORD_ONLY


def test_public_api_type_hints_cover_contract_functions() -> None:
    for fn_name in [
        "create_protocol_state",
        "build_protocol",
        "run_dry_run",
        "compile_protocol",
        "serialize_ir",
        "validate_protocol_ir",
        "invoke_optional_simulator",
        "protocol_hash",
        "protocol_provenance",
    ]:
        hints = get_type_hints(getattr(public_api, fn_name))
        assert "return" in hints, f"{fn_name} must expose return type hints"

