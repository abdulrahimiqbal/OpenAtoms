from __future__ import annotations

import json
from pathlib import Path

from openatoms import create_bundle

from ._bundle_test_utils import build_minimal_protocol


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_bundle_roundtrip_determinism(tmp_path: Path) -> None:
    seeds = {"python_random": 7, "numpy": 7, "openatoms_internal": 7}

    bundle_a = tmp_path / "bundle_a"
    bundle_b = tmp_path / "bundle_b"

    create_bundle(
        output_path=bundle_a,
        protocol=build_minimal_protocol("deterministic_demo"),
        seeds=seeds,
        deterministic=True,
    )
    create_bundle(
        output_path=bundle_b,
        protocol=build_minimal_protocol("deterministic_demo"),
        seeds=seeds,
        deterministic=True,
    )

    protocol_a = (bundle_a / "protocol.ir.json").read_bytes()
    protocol_b = (bundle_b / "protocol.ir.json").read_bytes()
    assert protocol_a == protocol_b

    manifest_a = _read_json(bundle_a / "manifest.json")
    manifest_b = _read_json(bundle_b / "manifest.json")

    assert manifest_a["created_at"] == "2026-01-01T00:00:00Z"
    assert manifest_b["created_at"] == "2026-01-01T00:00:00Z"
    assert manifest_a["protocol_ir_hash"] == manifest_b["protocol_ir_hash"]
    assert manifest_a["file_hashes"] == manifest_b["file_hashes"]
