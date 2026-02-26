from __future__ import annotations

import json
from pathlib import Path

from openatoms import create_bundle, sign_bundle, verify_signature

from ._bundle_test_utils import build_minimal_protocol


def test_bundle_signature_roundtrip_and_manifest_tamper(tmp_path: Path, monkeypatch) -> None:
    bundle_dir = tmp_path / "bundle"
    create_bundle(
        output_path=bundle_dir,
        protocol=build_minimal_protocol("sig_demo"),
        deterministic=True,
    )

    monkeypatch.setenv("OPENATOMS_BUNDLE_SIGNING_KEY", "unit-test-signing-secret")
    sign_bundle(bundle_dir, deterministic=True)

    verified = verify_signature(bundle_dir, raise_on_error=False)
    assert verified.ok is True

    manifest_path = bundle_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["openatoms_version"] = "tampered"
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )

    tampered = verify_signature(bundle_dir, raise_on_error=False)
    assert tampered.ok is False
    assert any(error.code == "OEB004" for error in tampered.errors)


def test_bundle_signature_fails_when_tracked_file_changes(tmp_path: Path, monkeypatch) -> None:
    bundle_dir = tmp_path / "bundle"
    create_bundle(
        output_path=bundle_dir,
        protocol=build_minimal_protocol("sig_file_demo"),
        deterministic=True,
    )

    monkeypatch.setenv("OPENATOMS_BUNDLE_SIGNING_KEY", "unit-test-signing-secret")
    sign_bundle(bundle_dir, deterministic=True)

    protocol_path = bundle_dir / "protocol.ir.json"
    raw = protocol_path.read_bytes()
    protocol_path.write_bytes(raw[:-1] + (b"0" if raw[-1:] != b"0" else b"1"))

    tampered = verify_signature(bundle_dir, raise_on_error=False)
    assert tampered.ok is False
    assert any(error.code == "OEB004" for error in tampered.errors)
