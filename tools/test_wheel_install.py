#!/usr/bin/env python3
"""Build, install, and smoke-test an isolated wheel without source-tree fallback."""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tarfile
import tempfile
import venv

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _run(args: list[str], *, cwd: pathlib.Path) -> None:
    completed = subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)
    if completed.returncode:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(args)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )


def main() -> int:
    try:
        with tempfile.TemporaryDirectory(prefix="triad-origin-wheel-") as tmp_name:
            tmp = pathlib.Path(tmp_name)
            sdist_dir = tmp / "sdist"
            dist = tmp / "dist"
            _run(
                [
                    sys.executable,
                    "setup.py",
                    "--quiet",
                    "sdist",
                    "--dist-dir",
                    str(sdist_dir),
                ],
                cwd=ROOT,
            )
            sdists = sorted(sdist_dir.glob("triad_origin-*.tar.gz"))
            if len(sdists) != 1:
                raise RuntimeError(f"expected one source distribution, found: {sdists}")
            with tarfile.open(sdists[0], mode="r:gz") as archive:
                names = archive.getnames()
            if not any(name.endswith("/contracts/registry/index.json") for name in names):
                raise RuntimeError("source distribution omits the contract registry")
            if not any(name.endswith("/contracts/MANIFEST.sha256") for name in names):
                raise RuntimeError("source distribution omits the contract byte manifest")
            _run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "wheel",
                    "--no-cache-dir",
                    str(sdists[0]),
                    "--no-deps",
                    "--no-build-isolation",
                    "--wheel-dir",
                    str(dist),
                ],
                cwd=ROOT,
            )
            wheels = sorted(dist.glob("triad_origin-*.whl"))
            if len(wheels) != 1:
                raise RuntimeError(f"expected one wheel, found: {wheels}")

            env_dir = tmp / "venv"
            venv.EnvBuilder(with_pip=True).create(env_dir)
            python = env_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
            _run(
                [
                    str(python),
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "--no-cache-dir",
                    "--no-index",
                    "--no-deps",
                    str(wheels[0]),
                ],
                cwd=tmp,
            )
            probe = """
import json
from triad_origin import contracts
assert len(contracts.known_contracts()) == 30
schema = contracts.load_schema('triad.edge_candidate.v2')
assert schema['title'] == 'triad.edge_candidate.v2'
assert contracts._CONTRACTS_DIR.name == '_contracts'
golden = contracts._CONTRACTS_DIR / 'golden' / 'triad.edge_candidate.v2' / 'valid.json'
event = json.loads(golden.read_text(encoding='utf-8'))
contracts.validate(event)  # fresh wheel has no jsonschema: exercises the stdlib path
event['producer_service'] = ''
try:
    contracts.validate(event)
except contracts.ContractError:
    pass
else:
    raise AssertionError('stdlib validator accepted a minLength violation')
"""
            _run([str(python), "-I", "-c", probe], cwd=tmp)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"FAIL: isolated wheel smoke failed: {exc}", file=sys.stderr)
        return 1
    print("OK: sdist-built isolated wheel loads all 30 packaged contracts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
