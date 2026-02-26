from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_interface_report_is_up_to_date() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    report_path = repo_root / "docs" / "INTERFACE.md"
    script_path = repo_root / "scripts" / "generate_interface_report.py"

    committed = report_path.read_text(encoding="utf-8")
    subprocess.run([sys.executable, str(script_path)], cwd=repo_root, check=True)
    regenerated = report_path.read_text(encoding="utf-8")

    assert regenerated == committed, (
        "docs/INTERFACE.md is out of date. "
        "Regenerate with: python scripts/generate_interface_report.py"
    )

