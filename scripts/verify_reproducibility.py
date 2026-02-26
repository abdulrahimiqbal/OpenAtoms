"""Verify deterministic Node B outputs across repeated runs with same seed."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "examples" / "node_b_thermo_kinetic.py"


def main() -> None:
    if importlib.util.find_spec("cantera") is None:
        print(
            "Skipping determinism check: optional dependency 'cantera' is not installed. "
            "Install with: pip install \".[sim-cantera]\""
        )
        return

    outputs: list[bytes] = []

    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "0"

    for _ in range(3):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode("utf-8", errors="replace"))
        outputs.append(result.stdout)

    if not (outputs[0] == outputs[1] == outputs[2]):
        raise AssertionError("Node B output is not deterministic across repeated runs.")

    print("Determinism check passed: Node B output identical across 3 runs.")


if __name__ == "__main__":
    main()
