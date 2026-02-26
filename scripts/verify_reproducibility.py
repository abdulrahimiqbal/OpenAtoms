"""Verify deterministic Node B outputs across repeated runs with same seed."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "examples" / "node_b_thermo_kinetic.py"


def _is_ci() -> bool:
    ci_flag = os.getenv("OPENATOMS_CI")
    if ci_flag is not None:
        return ci_flag.strip().lower() in {"1", "true", "yes", "on"}
    return os.getenv("CI", "").strip().lower() in {"1", "true", "yes", "on"}


def _allow_skip() -> bool:
    return os.getenv("OPENATOMS_ALLOW_SKIP", "").strip() == "1"


def _cantera_available() -> bool:
    if os.getenv("OPENATOMS_FORCE_MISSING_CANTERA", "").strip() == "1":
        return False
    return importlib.util.find_spec("cantera") is not None


def _handle_missing_cantera() -> int:
    message = (
        "Determinism check unavailable: optional dependency 'cantera' is not installed. "
        "Install with: pip install \".[sim-cantera]\"."
    )
    if _is_ci():
        print(f"{message} Failing because OPENATOMS_CI=1 requires deterministic thermo validation.")
        return 1
    if _allow_skip():
        print(f"{message} Skipping because OPENATOMS_ALLOW_SKIP=1.")
        return 0
    print(
        f"{message} Set OPENATOMS_ALLOW_SKIP=1 to skip locally, "
        "or install cantera to run the determinism check."
    )
    return 1


def main() -> None:
    if not _cantera_available():
        raise SystemExit(_handle_missing_cantera())

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
