import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


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


def test_hello_atoms_runs() -> None:
    out = _run("hello_atoms.py")
    assert '"ir_version": "1.1.0"' in out


def test_node_a_demo_runs() -> None:
    out = _run("node_a_bio_kinetic.py")
    assert "remediation_hint" in out
    assert '"simulation_success": true' in out.lower()


def test_node_c_demo_runs() -> None:
    out = _run("node_c_contact_kinetic.py")
    assert "Caught OrderingConstraintError" in out
