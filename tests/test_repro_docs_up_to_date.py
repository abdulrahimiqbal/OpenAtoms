from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_interface_report_and_repro_docs_are_current() -> None:
    interface_path = ROOT / "docs" / "INTERFACE.md"
    script_path = ROOT / "scripts" / "generate_interface_report.py"

    committed = interface_path.read_text(encoding="utf-8")
    subprocess.run([sys.executable, str(script_path)], cwd=ROOT, check=True)
    regenerated = interface_path.read_text(encoding="utf-8")
    assert regenerated == committed, "docs/INTERFACE.md is out of date"

    reproducibility_doc = (ROOT / "docs" / "REPRODUCIBILITY.md").read_text(encoding="utf-8")
    bundle_spec_doc = (ROOT / "docs" / "BUNDLE_SPEC.md").read_text(encoding="utf-8")

    assert "openatoms bundle create" in reproducibility_doc
    assert "openatoms bundle verify" in reproducibility_doc
    assert "openatoms bundle replay" in reproducibility_doc
    assert "openatoms bundle sign" in reproducibility_doc

    for code in ["OEB001", "OEB002", "OEB003", "OEB004", "OEB005"]:
        assert code in reproducibility_doc
        assert code in bundle_spec_doc
