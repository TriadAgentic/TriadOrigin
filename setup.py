"""Build hook that packages the byte-pinned contract bundle with ``triad_origin``.

The repository keeps one authoritative contract tree at ``contracts/``. A normal wheel must carry
that same tree; editable installs continue to read the repository copy.
"""

from __future__ import annotations

import pathlib
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py

ROOT = pathlib.Path(__file__).resolve().parent


class BuildPyWithContracts(build_py):
    def run(self) -> None:
        super().run()
        target = pathlib.Path(self.build_lib) / "triad_origin" / "_contracts"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(ROOT / "contracts", target)


setup(cmdclass={"build_py": BuildPyWithContracts})
