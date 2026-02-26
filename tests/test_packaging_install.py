from __future__ import annotations

import json
import os
import subprocess
import sys
from importlib import resources


def test_editable_install_imports_in_subprocess(tmp_path) -> None:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "-c", "import openatoms; import openatoms.ir"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_ir_schema_is_packaged_resource() -> None:
    schema_resource = resources.files("openatoms.ir").joinpath("schema_v1_1_0.json")
    schema = json.loads(schema_resource.read_text(encoding="utf-8"))
    assert schema["title"] == "OpenAtoms Protocol IR"
