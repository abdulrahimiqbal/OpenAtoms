from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_reproducibility.py"


def _run(env_overrides: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_verify_reproducibility_ci_fails_without_cantera() -> None:
    result = _run({"OPENATOMS_CI": "1", "OPENATOMS_FORCE_MISSING_CANTERA": "1"})
    assert result.returncode != 0
    assert "Install with: pip install \".[cantera]\"." in result.stdout
    assert "OPENATOMS_CI=1 requires deterministic thermo validation." in result.stdout


def test_verify_reproducibility_local_can_skip() -> None:
    result = _run({"OPENATOMS_ALLOW_SKIP": "1", "OPENATOMS_FORCE_MISSING_CANTERA": "1"})
    assert result.returncode == 0
    assert "Skipping because OPENATOMS_ALLOW_SKIP=1." in result.stdout


def test_missing_cantera_fails_locally_without_skip_flag() -> None:
    result = _run({"OPENATOMS_FORCE_MISSING_CANTERA": "1"})
    assert result.returncode == 1
    assert "Set OPENATOMS_ALLOW_SKIP=1 to skip locally" in result.stdout
