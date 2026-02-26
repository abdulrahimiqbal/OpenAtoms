from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from importlib import resources
from pathlib import Path

import jsonschema

from openatoms.ir import get_schema_resource_name, validate_ir


def _known_good_payload() -> dict[str, object]:
    return {
        "ir_version": "1.1.0",
        "protocol_id": "00000000-0000-0000-0000-000000000000",
        "correlation_id": "00000000-0000-0000-0000-000000000001",
        "created_at": "2026-01-01T00:00:00+00:00",
        "steps": [
            {
                "step": 1,
                "step_id": "s1",
                "action_type": "Move",
                "parameters": {"amount": {"value": 1, "unit": "microliter"}},
                "depends_on": [],
                "resources": [],
            }
        ],
        "provenance": {
            "ir_hash": "0" * 64,
            "simulator_versions": {},
            "noise_seed": None,
            "validator_version": "1.1.0",
        },
    }


def _host_site_packages() -> str:
    for entry in sys.path:
        candidate = Path(entry)
        if candidate.name == "site-packages" and (candidate / "pydantic").exists():
            return str(candidate)
    raise AssertionError("expected host site-packages with dependencies")


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
    schema_resource = resources.files("openatoms.ir").joinpath(get_schema_resource_name())
    schema = json.loads(schema_resource.read_text(encoding="utf-8"))
    assert schema["title"] == "OpenAtoms Protocol IR"


def test_minimal_known_good_ir_validates() -> None:
    schema_resource = resources.files("openatoms.ir").joinpath(get_schema_resource_name())
    schema = json.loads(schema_resource.read_text(encoding="utf-8"))
    payload = _known_good_payload()
    jsonschema.validate(instance=payload, schema=schema)
    assert validate_ir(payload) == payload


def test_wheel_install_smoke_schema_and_validation(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(dist_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
    )

    wheels = sorted(dist_dir.glob("openatoms-*.whl"))
    assert wheels, "expected built wheel artifact"
    wheel_path = wheels[-1]

    venv_dir = tmp_path / "wheel-env"
    subprocess.run(
        [sys.executable, "-m", "venv", "--system-site-packages", str(venv_dir)],
        check=True,
    )
    python_exe = venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    pip_exe = venv_dir / ("Scripts/pip.exe" if os.name == "nt" else "bin/pip")

    subprocess.run(
        [str(pip_exe), "install", "--no-deps", str(wheel_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    check_script = textwrap.dedent(
        """
        from openatoms.ir import load_schema, validate_ir

        payload = {
            "ir_version": "1.1.0",
            "protocol_id": "00000000-0000-0000-0000-000000000000",
            "correlation_id": "00000000-0000-0000-0000-000000000001",
            "created_at": "2026-01-01T00:00:00+00:00",
            "steps": [
                {
                    "step": 1,
                    "step_id": "s1",
                    "action_type": "Move",
                    "parameters": {"amount": {"value": 1, "unit": "microliter"}},
                    "depends_on": [],
                    "resources": [],
                }
            ],
            "provenance": {
                "ir_hash": "0" * 64,
                "simulator_versions": {},
                "noise_seed": None,
                "validator_version": "1.1.0",
            },
        }

        print(load_schema()["$id"])
        assert validate_ir(payload) == payload
        """
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = _host_site_packages()
    run = subprocess.run(
        [str(python_exe), "-c", check_script],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert "https://openatoms.org/ir/v1.1.0/schema.json" in run.stdout
