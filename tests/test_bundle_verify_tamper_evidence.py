from __future__ import annotations

from pathlib import Path

import pytest

from openatoms import BundleError, create_bundle, verify_bundle

from ._bundle_test_utils import build_minimal_protocol


def test_bundle_verify_detects_protocol_tamper(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    create_bundle(
        output_path=bundle_dir,
        protocol=build_minimal_protocol("tamper_demo"),
        deterministic=True,
    )

    protocol_path = bundle_dir / "protocol.ir.json"
    raw = protocol_path.read_bytes()
    protocol_path.write_bytes(raw[:-1] + (b"0" if raw[-1:] != b"0" else b"1"))

    report = verify_bundle(bundle_dir, raise_on_error=False)
    assert report.ok is False
    assert any(error.code == "OEB002" for error in report.errors)

    with pytest.raises(BundleError) as exc_info:
        verify_bundle(bundle_dir, raise_on_error=True)

    assert exc_info.value.code == "OEB002"
