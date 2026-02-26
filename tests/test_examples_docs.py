import os
import subprocess
import sys
from pathlib import Path


def test_examples_are_executable_docs():
    root = Path(__file__).resolve().parents[1]
    examples = [
        root / "examples" / "hello_atoms.py",
        root / "examples" / "basic_compilation.py",
        root / "examples" / "openai_tool_calling.py",
    ]
    for script in examples:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(root)
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"{script.name} failed: {result.stderr}"
