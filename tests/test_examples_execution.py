from __future__ import annotations

import os
import subprocess
import sys
from importlib.util import find_spec
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = ROOT / "examples"
OPTIONAL_DEPS: dict[str, str] = {
    "node_b_thermo_kinetic.py": "cantera",
    "research_loop.py": "cantera",
}


def _run(script: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    return subprocess.run(
        [sys.executable, str(EXAMPLES_DIR / script)],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    "script",
    sorted(path.name for path in EXAMPLES_DIR.glob("*.py") if path.is_file()),
)
def test_examples_execute(script: str) -> None:
    optional_dep = OPTIONAL_DEPS.get(script)
    if optional_dep and find_spec(optional_dep) is None:
        pytest.skip(f"example requires optional dependency: {optional_dep}")

    result = _run(script)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() != ""
