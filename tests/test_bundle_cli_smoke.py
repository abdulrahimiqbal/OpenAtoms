from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from openatoms import compile_protocol

from ._bundle_test_utils import build_minimal_protocol

ROOT = Path(__file__).resolve().parents[1]


def _run(
    args: list[str], cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    merged_env = dict(os.environ)
    merged_env["PYTHONPATH"] = str(ROOT)
    if env:
        merged_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "openatoms.cli", *args],
        cwd=cwd,
        env=merged_env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_bundle_cli_create_verify_replay_sign(tmp_path: Path) -> None:
    payload = compile_protocol(build_minimal_protocol("cli_demo"))
    ir_path = tmp_path / "protocol.ir.json"
    ir_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")

    bundle_path = tmp_path / "bundle"
    create = _run(
        [
            "bundle",
            "create",
            "--ir",
            str(ir_path),
            "--output",
            str(bundle_path),
            "--deterministic",
            "--json",
        ],
        cwd=tmp_path,
    )
    assert create.returncode == 0, create.stderr

    verify = _run(["bundle", "verify", "--bundle", str(bundle_path), "--json"], cwd=tmp_path)
    assert verify.returncode == 0, verify.stderr

    replay = _run(
        ["bundle", "replay", "--bundle", str(bundle_path), "--strict", "--json"],
        cwd=tmp_path,
    )
    assert replay.returncode == 0, replay.stderr

    sign = _run(
        ["bundle", "sign", "--bundle", str(bundle_path), "--json"],
        cwd=tmp_path,
        env={"OPENATOMS_BUNDLE_SIGNING_KEY": "cli-test-secret"},
    )
    assert sign.returncode == 0, sign.stderr

    verify_sig = _run(
        ["bundle", "verify-signature", "--bundle", str(bundle_path), "--json"],
        cwd=tmp_path,
        env={"OPENATOMS_BUNDLE_SIGNING_KEY": "cli-test-secret"},
    )
    assert verify_sig.returncode == 0, verify_sig.stderr
