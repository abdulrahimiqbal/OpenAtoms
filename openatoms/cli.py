"""OpenAtoms command line interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .bundle import (
    BundleError,
    create_bundle,
    replay_bundle,
    sign_bundle,
    verify_bundle,
    verify_signature,
)


def _parse_seed_pairs(items: list[str] | None) -> dict[str, int] | None:
    if not items:
        return None
    seeds: dict[str, int] = {}
    for item in items:
        if "=" not in item:
            raise BundleError("OEB006", f"Invalid seed format '{item}'. Expected key=value.")
        key, value = item.split("=", 1)
        seeds[key.strip()] = int(value.strip())
    return seeds


def _load_optional_json_file(path: str | None) -> dict[str, Any] | None:
    if path is None:
        return None
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BundleError("OEB006", f"Expected JSON object in {path}.")
    return payload


def _print_output(payload: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, sort_keys=True))
        return

    if "ok" in payload:
        print(f"ok: {payload['ok']}")
    if "bundle_path" in payload:
        print(f"bundle: {payload['bundle_path']}")
    if "bundle_version" in payload and payload["bundle_version"] is not None:
        print(f"bundle_version: {payload['bundle_version']}")
    if "schema_version" in payload and payload["schema_version"] is not None:
        print(f"schema_version: {payload['schema_version']}")
    if "output_path" in payload:
        print(f"output_path: {payload['output_path']}")
    if "signature" in payload:
        print("signature: present")

    errors = payload.get("errors")
    if isinstance(errors, list) and errors:
        print("errors:")
        for item in errors:
            code = item.get("code", "<unknown>")
            message = item.get("message", "")
            path = item.get("path")
            if path:
                print(f"  - {code} ({path}): {message}")
            else:
                print(f"  - {code}: {message}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="openatoms")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bundle_parser = subparsers.add_parser("bundle", help="Experiment bundle commands")
    bundle_subparsers = bundle_parser.add_subparsers(dest="bundle_command", required=True)

    create_parser = bundle_subparsers.add_parser("create", help="Create an experiment bundle")
    create_parser.add_argument("--ir", required=True, help="Path to protocol IR JSON file")
    create_parser.add_argument(
        "--output", required=True, help="Output bundle directory or .zip path"
    )
    create_parser.add_argument("--tool-calls", help="Optional tool call trace JSONL path")
    create_parser.add_argument("--prompts", help="Optional prompts JSON path")
    create_parser.add_argument("--model", help="Optional model metadata JSON path")
    create_parser.add_argument(
        "--result", dest="results", action="append", help="Optional result path"
    )
    create_parser.add_argument(
        "--simulator",
        dest="simulators",
        action="append",
        choices=["opentrons", "cantera", "mujoco"],
        help="Optional simulator names",
    )
    create_parser.add_argument(
        "--seed", dest="seeds", action="append", help="Seed in key=value form"
    )
    create_parser.add_argument("--metadata", help="Optional metadata JSON path")
    create_parser.add_argument(
        "--zip", dest="zip_output", action="store_true", help="Write zip output"
    )
    create_parser.add_argument(
        "--deterministic", action="store_true", help="Enable deterministic mode"
    )
    create_parser.add_argument("--json", action="store_true", help="Emit JSON output")

    verify_parser = bundle_subparsers.add_parser("verify", help="Verify bundle integrity")
    verify_parser.add_argument("--bundle", required=True, help="Bundle directory or .zip path")
    verify_parser.add_argument("--key-env", default="OPENATOMS_BUNDLE_SIGNING_KEY")
    verify_parser.add_argument("--json", action="store_true", help="Emit JSON output")

    replay_parser = bundle_subparsers.add_parser("replay", help="Replay bundle checks")
    replay_parser.add_argument("--bundle", required=True, help="Bundle directory or .zip path")
    replay_parser.add_argument(
        "--simulator",
        dest="simulators",
        action="append",
        choices=["opentrons", "cantera", "mujoco"],
        help="Optional simulator names",
    )
    replay_parser.add_argument("--strict", action="store_true", help="Fail on any replay mismatch")
    replay_parser.add_argument("--output", help="Optional replay checks output directory")
    replay_parser.add_argument("--json", action="store_true", help="Emit JSON output")

    sign_parser = bundle_subparsers.add_parser("sign", help="Sign bundle manifest")
    sign_parser.add_argument("--bundle", required=True, help="Bundle directory or .zip path")
    sign_parser.add_argument("--key-env", default="OPENATOMS_BUNDLE_SIGNING_KEY")
    sign_parser.add_argument("--key-id", help="Logical key identifier")
    sign_parser.add_argument(
        "--deterministic", action="store_true", help="Deterministic signed_at timestamp"
    )
    sign_parser.add_argument("--json", action="store_true", help="Emit JSON output")

    verify_sig_parser = bundle_subparsers.add_parser(
        "verify-signature", help="Verify manifest signature"
    )
    verify_sig_parser.add_argument("--bundle", required=True, help="Bundle directory or .zip path")
    verify_sig_parser.add_argument("--key-env", default="OPENATOMS_BUNDLE_SIGNING_KEY")
    verify_sig_parser.add_argument("--json", action="store_true", help="Emit JSON output")

    return parser


def _run(args: argparse.Namespace) -> int:
    if args.command != "bundle":
        raise BundleError("OEB006", f"Unsupported command: {args.command}")

    if args.bundle_command == "create":
        metadata = _load_optional_json_file(args.metadata)
        bundle_path = create_bundle(
            output_path=args.output,
            ir_payload=Path(args.ir),
            agent_tool_calls=args.tool_calls,
            agent_prompts=args.prompts,
            agent_model=args.model,
            results_paths=args.results,
            simulators=args.simulators,
            metadata=metadata,
            seeds=_parse_seed_pairs(args.seeds),
            deterministic=bool(args.deterministic),
            zip_output=bool(args.zip_output),
        )
        payload = {
            "ok": True,
            "output_path": str(bundle_path),
        }
        _print_output(payload, as_json=bool(args.json))
        return 0

    if args.bundle_command == "verify":
        report = verify_bundle(
            args.bundle,
            verify_manifest_signature=True,
            key_env=args.key_env,
            raise_on_error=False,
        )
        payload = report.to_dict()
        _print_output(payload, as_json=bool(args.json))
        return 0 if report.ok else 1

    if args.bundle_command == "replay":
        report = replay_bundle(
            args.bundle,
            simulators=args.simulators,
            strict=bool(args.strict),
            output_path=args.output,
            raise_on_error=False,
        )
        payload = report.to_dict()
        _print_output(payload, as_json=bool(args.json))
        return 0 if report.ok else 1

    if args.bundle_command == "sign":
        signature = sign_bundle(
            args.bundle,
            key_env=args.key_env,
            key_id=args.key_id,
            deterministic=bool(args.deterministic),
        )
        payload = {"ok": True, "signature": signature, "bundle_path": str(args.bundle)}
        _print_output(payload, as_json=bool(args.json))
        return 0

    if args.bundle_command == "verify-signature":
        report = verify_signature(
            args.bundle,
            key_env=args.key_env,
            raise_on_error=False,
        )
        payload = report.to_dict()
        _print_output(payload, as_json=bool(args.json))
        return 0 if report.ok else 1

    raise BundleError("OEB006", f"Unsupported bundle command: {args.bundle_command}")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except BundleError as exc:
        payload = {
            "ok": False,
            "errors": [{"code": exc.code, "message": str(exc), "path": exc.path}],
        }
        as_json = bool(getattr(args, "json", False))
        _print_output(payload, as_json=as_json)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
