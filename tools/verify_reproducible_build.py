#!/usr/bin/env python3
"""Build two isolated source copies and require byte-identical sdist and wheel artifacts."""

from __future__ import annotations

import hashlib
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE_DATE_EPOCH = "1700000000"


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(args: list[str], *, cwd: pathlib.Path, env: dict[str, str]) -> None:
    completed = subprocess.run(
        args, cwd=cwd, env=env, text=True, capture_output=True, check=False
    )
    if completed.returncode:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(args)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )


def _build(copy_root: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    source = copy_root / "source"
    dist = copy_root / "dist"
    shutil.copytree(
        ROOT,
        source,
        ignore=shutil.ignore_patterns(
            ".git", ".pytest_cache", "__pycache__", "*.egg-info", "build", "dist"
        ),
    )
    dist.mkdir()
    env = dict(os.environ)
    env.update(
        {
            "SOURCE_DATE_EPOCH": SOURCE_DATE_EPOCH,
            "PYTHONHASHSEED": "0",
            "TZ": "UTC",
            "LC_ALL": "C.UTF-8",
            "LANG": "C.UTF-8",
        }
    )
    _run(
        [sys.executable, "setup.py", "--quiet", "sdist", "--dist-dir", str(dist)],
        cwd=source,
        env=env,
    )
    sdists = sorted(dist.glob("triad_origin-*.tar.gz"))
    if len(sdists) != 1:
        raise RuntimeError(f"expected one sdist, found {sdists}")
    _run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--disable-pip-version-check",
            "--no-cache-dir",
            "--no-index",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(dist),
            str(sdists[0]),
        ],
        cwd=source,
        env=env,
    )
    wheels = sorted(dist.glob("triad_origin-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"expected one wheel, found {wheels}")
    return sdists[0], wheels[0]


def main() -> int:
    try:
        with tempfile.TemporaryDirectory(prefix="triad-origin-repro-") as tmp_name:
            tmp = pathlib.Path(tmp_name)
            first_sdist, first_wheel = _build(tmp / "first")
            second_sdist, second_wheel = _build(tmp / "second")
            first = (_sha256(first_sdist), _sha256(first_wheel))
            second = (_sha256(second_sdist), _sha256(second_wheel))
            if first != second:
                raise RuntimeError(
                    "build artifacts are not reproducible: "
                    f"first sdist/wheel={first}, second={second}"
                )
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"FAIL: reproducible build verification failed: {exc}", file=sys.stderr)
        return 1
    print(f"OK: reproducible sdist={first[0]} wheel={first[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
