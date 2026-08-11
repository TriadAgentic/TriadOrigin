"""Regression: a non-editable wheel carries and loads its contract bundle."""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_installed_wheel_loads_packaged_contracts():
    env = os.environ.copy()
    # Regression: the documented repository-relative constraint must remain valid after the
    # wheel verifier deliberately changes cwd for isolated build/install subprocesses.
    env["PIP_CONSTRAINT"] = "constraints/ci.txt"
    completed = subprocess.run(
        [sys.executable, "tools/test_wheel_install.py"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
