import os
import subprocess
import sys
from importlib.util import find_spec
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]

EXAMPLE_CASES = [
    ("basic_compilation.py", None, "[Runner -> OpentronsAdapter]"),
    ("hello_atoms.py", None, '"ir_version": "1.1.0"'),
    ("node_a_bio_kinetic.py", None, '"simulation_success": true'),
    pytest.param(
        "node_b_thermo_kinetic.py",
        "cantera",
        "Caught ThermalExcursionError",
        marks=pytest.mark.requires_cantera,
    ),
    ("node_c_contact_kinetic.py", None, "Caught OrderingConstraintError"),
    ("openai_tool_calling.py", None, "SIMULATING LLM SELF-CORRECTION"),
    pytest.param(
        "research_loop.py",
        "cantera",
        "OpenAtoms Research Loop",
        marks=pytest.mark.requires_cantera,
    ),
]


def _run(script: str) -> str:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    result = subprocess.run(
        [sys.executable, str(ROOT / "examples" / script)],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


@pytest.mark.parametrize(("script", "optional_dep", "needle"), EXAMPLE_CASES)
def test_examples_execute(script: str, optional_dep: str | None, needle: str) -> None:
    if optional_dep and find_spec(optional_dep) is None:
        pytest.skip(f"example requires optional dependency: {optional_dep}")
    out = _run(script)
    assert needle in out
