#!/usr/bin/env python3
"""Build, install, and smoke-test an isolated wheel without source-tree fallback."""

from __future__ import annotations

import hashlib
import os
import pathlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import venv

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _subprocess_env() -> dict[str, str]:
    """Return an environment whose repository constraint survives cwd changes."""

    env = os.environ.copy()
    raw_constraint = env.get("PIP_CONSTRAINT")
    if raw_constraint:
        constraint = pathlib.Path(raw_constraint)
        if not constraint.is_absolute():
            constraint = ROOT / constraint
        if not constraint.is_file():
            raise RuntimeError(f"PIP_CONSTRAINT is not a file: {constraint}")
        env["PIP_CONSTRAINT"] = str(constraint.resolve())
    return env


def _run(args: list[str], *, cwd: pathlib.Path, env: dict[str, str]) -> None:
    completed = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(args)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )


def main() -> int:
    try:
        env = _subprocess_env()
        with tempfile.TemporaryDirectory(prefix="triad-origin-wheel-") as tmp_name:
            tmp = pathlib.Path(tmp_name)
            source = tmp / "source"
            shutil.copytree(
                ROOT,
                source,
                ignore=shutil.ignore_patterns(
                    ".git", ".pytest_cache", ".venv", "__pycache__", "*.egg-info",
                    "build", "dist",
                ),
            )
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
                cwd=source,
                env=env,
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
            if not any(name.endswith("/constraints/ci.txt") for name in names):
                raise RuntimeError("source distribution omits the exact dependency snapshot")
            source_legacy_manifest_json_sha = hashlib.sha256(
                (ROOT / "contracts" / "manifest" / "contract_bundle.manifest.v1.json").read_bytes()
            ).hexdigest()
            source_r00_manifest_json_sha = hashlib.sha256(
                (ROOT / "contracts" / "manifest" / "contract_bundle.manifest.r00.v1.json").read_bytes()
            ).hexdigest()
            source_manifest_json_sha = hashlib.sha256(
                (ROOT / "contracts" / "manifest" / "contract_bundle.manifest.b01.v2.json").read_bytes()
            ).hexdigest()
            source_manifest_text_sha = hashlib.sha256(
                (ROOT / "contracts" / "MANIFEST.sha256").read_bytes()
            ).hexdigest()
            source_runtime = {
                str(path.relative_to(ROOT / "src" / "triad_origin")): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in sorted((ROOT / "src" / "triad_origin").rglob("*.py"))
            }
            _run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "wheel",
                    "--no-cache-dir",
                    "--no-index",
                    str(sdists[0]),
                    "--no-deps",
                    "--no-build-isolation",
                    "--wheel-dir",
                    str(dist),
                ],
                cwd=source,
                env=env,
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
                env=env,
            )
            probe = f"""
import hashlib
import json
import pathlib
import triad_origin
from triad_origin import contracts, bindings
assert len(contracts.known_contracts()) == 56
assert contracts._CONTRACTS_DIR.name == '_contracts'

# B01C-BIND-03: the binding bundle resolves to the packaged resource, never a repo-relative path.
assert bindings._PACKAGED_REGISTRY.is_file(), bindings._PACKAGED_REGISTRY
assert bindings.DEFAULT_REGISTRY_PATH == bindings._PACKAGED_REGISTRY
assert not bindings._SOURCE_REGISTRY.exists(), 'installed wheel must not see docs/control'
# B01C-CON-03 end to end: the loader validates every row with the full validator, which is absent
# in this --no-deps wheel, so load_registry() fails closed (never a fallback PASS) even though the
# packaged bundle bytes are present and readable.
import json as _json
assert _json.loads(bindings._PACKAGED_REGISTRY.read_text())['row_count'] == 105
try:
    bindings.load_registry()
except contracts.SchemaValidatorUnavailable:
    pass
else:
    raise AssertionError('binding loader validated rows without the full validator')
root = contracts._CONTRACTS_DIR
manifest_text = root / 'MANIFEST.sha256'
legacy_manifest_json = root / 'manifest' / 'contract_bundle.manifest.v1.json'
r00_manifest_json = root / 'manifest' / 'contract_bundle.manifest.r00.v1.json'
manifest_json = root / 'manifest' / 'contract_bundle.manifest.b01.v2.json'
assert hashlib.sha256(manifest_text.read_bytes()).hexdigest() == {source_manifest_text_sha!r}
assert hashlib.sha256(legacy_manifest_json.read_bytes()).hexdigest() == {source_legacy_manifest_json_sha!r}
assert hashlib.sha256(r00_manifest_json.read_bytes()).hexdigest() == {source_r00_manifest_json_sha!r}
assert hashlib.sha256(manifest_json.read_bytes()).hexdigest() == {source_manifest_json_sha!r}

runtime_root = pathlib.Path(triad_origin.__file__).resolve().parent
installed_runtime = {{
    str(path.relative_to(runtime_root)): hashlib.sha256(path.read_bytes()).hexdigest()
    for path in sorted(runtime_root.rglob('*.py'))
}}
assert installed_runtime == {source_runtime!r}, (installed_runtime, {source_runtime!r})

entries = []
for line in manifest_text.read_text(encoding='utf-8').splitlines():
    digest, name = line.split('  ', 1)
    if name.startswith('contracts/'):
        relative = name.removeprefix('contracts/')
        target = root / relative
        assert target.is_file(), name
        assert hashlib.sha256(target.read_bytes()).hexdigest() == digest, name
        entries.append(relative)
assert len(entries) == 184
actual = {{str(path.relative_to(root)) for path in root.rglob('*') if path.is_file()}}
expected = set(entries) | {{
    'MANIFEST.sha256',
    'manifest/contract_bundle.manifest.v1.json',
    'manifest/contract_bundle.manifest.r00.v1.json',
    'manifest/contract_bundle.manifest.b01.v2.json',
}}
assert actual == expected, (sorted(actual - expected), sorted(expected - actual))

# B01C-CON-03: this isolated wheel has NO jsonschema (installed --no-deps), so the AUTHORITATIVE
# path must fail closed (SCHEMA_VALIDATOR_UNAVAILABLE) for every golden — never a fallback PASS.
# The packaged schema/golden bytes are proven intact via the non-authoritative diagnostic, which
# still distinguishes valid from invalid.
for schema_id in contracts.known_contracts():
    schema = contracts.load_schema(schema_id)
    assert schema['title'] == schema_id
    golden_dir = root / 'golden' / schema_id
    valid = json.loads((golden_dir / 'valid.json').read_text(encoding='utf-8'))
    invalid = json.loads((golden_dir / 'invalid.json').read_text(encoding='utf-8'))
    for vector in (valid, invalid):
        try:
            contracts.validate(vector, schema_id=schema_id)
        except contracts.SchemaValidatorUnavailable:
            pass
        else:
            raise AssertionError(f'authoritative validate passed without full validator for {{schema_id}}')
    contracts.diagnostic_validate(schema_id, valid)
    try:
        contracts.diagnostic_validate(schema_id, invalid)
    except contracts.ContractError:
        pass
    else:
        raise AssertionError(f'diagnostic accepted invalid golden for {{schema_id}}')
"""
            _run([str(python), "-I", "-c", probe], cwd=tmp, env=env)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"FAIL: isolated wheel smoke failed: {exc}", file=sys.stderr)
        return 1
    print(
        "OK: sdist-built wheel byte-matches runtime, verifies 184 artifacts, fails closed without "
        "the full validator, and diagnoses all 56 goldens"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
