"""Regression: a non-editable wheel carries and loads its contract bundle."""

from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_installed_wheel_loads_packaged_contracts():
    completed = subprocess.run(
        [sys.executable, "tools/test_wheel_install.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
