"""Adversarial coverage for the B00R generation-2 clean-runner semantic verifier."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import pathlib
import subprocess

import pytest

from tools import b00r_clean_runner as clean


def test_verifier_git_uses_only_canonical_config_suppressed_environment(
    tmp_path, monkeypatch
):
    seen = {}

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        seen["env"] = kwargs["env"]
        return subprocess.CompletedProcess(argv, 0, "ok\n", "")

    monkeypatch.setenv("HOME", "/ambient-home")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/ambient-config")
    monkeypatch.setattr(clean.subprocess, "run", fake_run)
    assert clean._git(tmp_path, "rev-parse", "HEAD") == "ok"
    expected = {
        name: value
        for name, value in clean.BASE_ENV.items()
        if name.startswith("GIT_") or name in {"LANG", "LC_ALL", "TZ"}
    }
    assert seen["env"] == expected
    assert "HOME" not in seen["env"]


def _canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(root: pathlib.Path, *args: str, instant: str | None = None, binary=False):
    env = dict(os.environ)
    if instant is not None:
        env["GIT_AUTHOR_DATE"] = instant
        env["GIT_COMMITTER_DATE"] = instant
    proc = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=True,
        text=not binary, env=env,
    )
    return proc.stdout if binary else proc.stdout.strip()


def _write(root: pathlib.Path, rel: str, data: bytes) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def _blob(root: pathlib.Path, commit: str, rel: str) -> bytes:
    return _git(root, "show", f"{commit}:{rel}", binary=True)


def _entry(root: pathlib.Path, rel: str, role: str, unique: bool) -> dict:
    data = (root / rel).read_bytes()
    return {
        "path": rel,
        "role": role,
        "role_unique": unique,
        "media_type": "application/json" if rel.endswith(".json") else "application/octet-stream",
        "size": len(data),
        "sha256": _sha(data),
    }


def _provider_time(root: pathlib.Path, commit: str) -> int:
    return int(_git(root, "show", "-s", "--format=%ct", commit)) * 1_000_000


def _build_valid_bundle(
    tmp_path: pathlib.Path, extra_source_files: dict[str, bytes] | None = None
) -> dict:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "clean-runner-test")
    _git(repo, "config", "user.email", "clean-runner@example.invalid")

    source_files = {
        ".github/workflows/ci.yml": b"name: CI\njobs: {}\n",
        "constraints/ci.txt": b"pytest==9.1.1\n",
        "contracts/MANIFEST.sha256": b"a" * 64 + b"  contracts/example.json\n",
        "docs/control/b00r_policy.v2.json": b'{"repair_generation":2}\n',
        "docs/control/rc3_effective_bundle_manifest.json": b"{}\n",
        "docs/control/rc4_control_bundle.json": b"{}\n",
        "pyproject.toml": (
            b"[project]\nname = \"triad-origin\"\nversion = \"7.0.0rc1.post1\"\n"
        ),
        "src/triad_origin/__init__.py": b'__version__ = "7.0.0rc1.post1"\n',
        "contracts/example.json": b"{}\n",
    }
    source_files.update(extra_source_files or {})
    for rel, data in source_files.items():
        _write(repo, rel, data)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base", instant="1970-01-01T00:00:01Z")
    _git(repo, "checkout", "-b", "source")
    _write(repo, "source-change.txt", b"corrective source\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "source", instant="1970-01-01T00:00:20Z")
    _git(repo, "checkout", "main")
    _git(
        repo, "merge", "--no-ff", "source", "-m", "merge source",
        instant="1970-01-01T00:00:30Z",
    )
    source_merge = _git(repo, "rev-parse", "HEAD")
    source_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    source_time = _provider_time(repo, source_merge)
    parents = _git(repo, "rev-list", "--parents", "-n", "1", source_merge).split()[1:]
    parent_tree = _git(repo, "rev-parse", f"{parents[0]}^{{tree}}")

    roles: dict[str, tuple[str, bool]] = {}

    def add(rel: str, data: bytes, role: str, unique: bool = True) -> None:
        _write(repo, rel, data)
        roles[rel] = (role, unique)

    workflow = _blob(repo, source_merge, ".github/workflows/ci.yml")
    contract = _blob(repo, source_merge, "contracts/MANIFEST.sha256")
    ls_tree = _git(
        repo, "ls-tree", "-r", "-z", "--full-tree", source_merge, binary=True
    )
    add(clean.SOURCE_WORKFLOW_PATH, workflow, "WORKFLOW")
    add(clean.CONTRACT_MANIFEST_PATH, contract, "CONTRACT_MANIFEST")
    add(clean.SOURCE_TREE_PATH, ls_tree, "CLEAN_RUNNER_SOURCE_TREE")
    source_identity = {
        "schema": "triad.b00r.clean_runner_source_identity.v1",
        "repository": clean.REPOSITORY,
        "source_merge_sha": source_merge,
        "source_merge_tree": source_tree,
        "source_merge_time_us": source_time,
        "parents": parents,
        "ls_tree_path": clean.SOURCE_TREE_PATH,
        "ls_tree_sha256": _sha(ls_tree),
        "workflow_path": clean.SOURCE_WORKFLOW_PATH,
        "workflow_sha256": _sha(workflow),
        "contract_manifest_path": clean.CONTRACT_MANIFEST_PATH,
        "contract_manifest_sha256": _sha(contract),
    }
    add(
        clean.SOURCE_IDENTITY_PATH, _canonical(source_identity),
        "CLEAN_RUNNER_SOURCE_IDENTITY",
    )

    run_id = "1234567890abcdef1234567890abcdef"
    checkout_root = "/tmp/triad-b00r-run/checkout"
    evidence_output_root = "/tmp/triad-b00r-run/output"
    venv_root = "/tmp/triad-b00r-run/venv"
    python_path = f"{venv_root}/bin/python"
    constraints = _blob(repo, source_merge, "constraints/ci.txt")
    facts = {
        "schema": "triad.b00r.clean_runner_facts.v1",
        "run_id": run_id,
        "repository": clean.REPOSITORY,
        "origin_url": "https://github.com/TriadAgentic/TriadOrigin.git",
        "origin_main_sha": source_merge,
        "checkout_mode": "detached",
        "head_sha": source_merge,
        "tree_sha": source_tree,
        "clone_no_local": True,
        "clone_no_tags": True,
        "clone_target_preexisted": False,
        "git_status_porcelain_z_sha256": _sha(b""),
        "git_replace_list_sha256": _sha(b""),
        "alternates_present": False,
        "is_shallow_repository": False,
        "submodule_count": 0,
        "checkout_root": checkout_root,
        "evidence_output_root": evidence_output_root,
        "constraints_path": "constraints/ci.txt",
        "constraints_sha256": _sha(constraints),
        "python_implementation": "CPython",
        "python_version": "3.11.13",
        "python_executable": python_path,
        "python_executable_sha256": "b" * 64,
        "venv": {
            "prefix": venv_root,
            "base_prefix": "/usr/local",
            "system_site_packages": False,
        },
    }
    add(clean.RUNNER_FACTS_PATH, _canonical(facts), "CLEAN_RUNNER_FACTS")

    runtime = _blob(repo, source_merge, "src/triad_origin/__init__.py")
    packages = {
        "schema": "triad.b00r.installed_packages.v1",
        "run_id": run_id,
        "source_merge_sha": source_merge,
        "constraints_path": "constraints/ci.txt",
        "constraints_sha256": _sha(constraints),
        "distributions": [
            {
                "name": "pip",
                "version": "24.0",
                "files": [{
                    "path": "pip/__init__.py", "size": 8, "sha256": "d" * 64,
                }],
            },
            {
                "name": "pytest",
                "version": "9.1.1",
                "files": [{
                    "path": "pytest/__init__.py", "size": 8, "sha256": "c" * 64,
                }],
            },
            {
                "name": "triad-origin",
                "version": "7.0.0rc1.post1",
                "files": [{
                    "path": "triad_origin/__init__.py",
                    "size": len(runtime),
                    "sha256": _sha(runtime),
                }],
            },
        ],
    }
    add(
        clean.PACKAGE_SNAPSHOT_PATH, _canonical(packages),
        "CLEAN_RUNNER_PACKAGE_SNAPSHOT",
    )

    test_ids = b"tests/test_example.py::test_ok\n"
    for seed in ("0", "1"):
        add(
            clean.TEST_IDS_PATHS[seed], test_ids,
            f"CLEAN_RUNNER_TEST_IDS_SEED{seed}",
        )
        result = {
            "schema": "triad.b00r.pytest_inventory.v1",
            "run_id": run_id,
            "source_merge_sha": source_merge,
            "seed": int(seed),
            "exit_code": 0,
            "collected": 1,
            "passed": 1,
            "skipped": 0,
            "xfailed": 0,
            "failed": 0,
            "errors": 0,
            "test_ids_path": clean.TEST_IDS_PATHS[seed],
            "test_ids_sha256": _sha(test_ids),
        }
        add(
            clean.PYTEST_RESULT_PATHS[seed], _canonical(result),
            f"CLEAN_RUNNER_PYTEST_RESULT_SEED{seed}",
        )

    stdout_by_id = {
        "pytest-seed0": b". [100%]\n1 passed in 0.01s\n",
        "pytest-seed1": b". [100%]\n1 passed in 0.01s\n",
        "collect-test-ids": test_ids,
        "verify-manifest": b"OK: 1 artifacts match manifest (aaaaaaaaaaaaaaaa...)\n",
        "validate-contract-manifest": (
            b"OK: committed contract manifest validates against "
            b"triad.contract_bundle.manifest.v1\n"
        ),
        "verify-reproducible-build": (
            b"OK: reproducible sdist=" + b"1" * 64 + b" wheel=" + b"2" * 64 + b"\n"
        ),
        "test-wheel-install": (
            b"OK: sdist-built wheel byte-matches runtime, verifies artifacts\n"
        ),
        "verify-no-forbidden-capabilities": (
            b"OK: E02 runtime has no network, credential, or venue-order capability\n"
        ),
        "e2e-audit": b"".join(
            f"PASS stage-{index:02d}: ok\n".encode() for index in range(25)
        ) + b"E2E AUDIT: all 25 stages passed\n",
        "build-ledger": b"OK: build ledger current (1 tasks; review current)\n",
        "validate-combined-dag": "OK: combined DAG valid — 1 task\n".encode(),
    }
    commands = []
    command_start = 41_000_000
    for ordinal, (command_id, argv_profile, seed) in enumerate(clean.REQUIRED_COMMANDS):
        base = f"{clean.EVIDENCE_ROOT}/commands/{ordinal:02d}-{command_id}"
        stdout_path = f"{base}/stdout.bin"
        stderr_path = f"{base}/stderr.bin"
        rc_path = f"{base}/rc.txt"
        stdout = stdout_by_id[command_id]
        add(stdout_path, stdout, "CLEAN_RUNNER_COMMAND_STDOUT", unique=False)
        add(stderr_path, b"", "CLEAN_RUNNER_COMMAND_STDERR", unique=False)
        add(rc_path, b"0\n", "CLEAN_RUNNER_COMMAND_RC", unique=False)
        env = dict(
            clean.BASE_ENV,
            PIP_CONSTRAINT=f"{checkout_root}/constraints/ci.txt",
            PYTHONHASHSEED=seed,
        )
        if command_id.startswith("pytest-seed"):
            env.update({
                "TRIAD_B00R_RUN_ID": run_id,
                "TRIAD_B00R_SOURCE_MERGE": source_merge,
                "TRIAD_B00R_TEST_IDS_PATH":
                    f"{evidence_output_root}/{clean.TEST_IDS_PATHS[seed]}",
                "TRIAD_B00R_TEST_IDS_REL": clean.TEST_IDS_PATHS[seed],
                "TRIAD_B00R_TEST_RESULT_PATH":
                    f"{evidence_output_root}/{clean.PYTEST_RESULT_PATHS[seed]}",
                "TRIAD_B00R_TEST_RESULT_REL": clean.PYTEST_RESULT_PATHS[seed],
            })
        argv = [python_path if item == "$PYTHON" else item for item in argv_profile]
        started = command_start + ordinal * 2_000_000
        commands.append({
            "ordinal": ordinal,
            "id": command_id,
            "argv": argv,
            "env": env,
            "cwd": checkout_root,
            "started_at_us": started,
            "finished_at_us": started + 1_000_000,
            "stdout_path": stdout_path,
            "stdout_sha256": _sha(stdout),
            "stdout_size": len(stdout),
            "stderr_path": stderr_path,
            "stderr_sha256": _sha(b""),
            "stderr_size": 0,
            "rc_path": rc_path,
            "rc_sha256": _sha(b"0\n"),
            "rc_size": 2,
            "exit_code": 0,
        })

    test_manifest = {
        "schema": "triad.b00r.clean_runner_tests.v1",
        "run_id": run_id,
        "source_merge_sha": source_merge,
        "collector_stdout_path":
            f"{clean.EVIDENCE_ROOT}/commands/02-collect-test-ids/stdout.bin",
        "collector_stdout_sha256": _sha(test_ids),
        "seed_runs": [{
            "seed": seed,
            "result_path": clean.PYTEST_RESULT_PATHS[seed],
            "result_sha256": _sha((repo / clean.PYTEST_RESULT_PATHS[seed]).read_bytes()),
            "test_ids_path": clean.TEST_IDS_PATHS[seed],
            "test_ids_sha256": _sha(test_ids),
        } for seed in ("0", "1")],
        "test_count": 1,
        "identical": True,
    }
    add(clean.TEST_MANIFEST_PATH, _canonical(test_manifest), "TEST_MANIFEST")

    config = {
        "schema": "triad.b00r.clean_runner_config_bundle.v1",
        "run_id": run_id,
        "source_merge_sha": source_merge,
        "activation_result": "DENIED_SAFE_HOLD",
        "levers": clean.SAFE_HOLD_LEVERS,
        "source_files": [{
            "path": path, "sha256": _sha(_blob(repo, source_merge, path)),
        } for path in clean.CONFIG_SOURCE_PATHS],
        "reproducible_sdist_sha256": "1" * 64,
        "reproducible_wheel_sha256": "2" * 64,
    }
    add(clean.CONFIG_BUNDLE_PATH, _canonical(config), "CONFIG_BUNDLE")

    add(clean.ROLLBACK_STDOUT_PATH, b"", "CLEAN_RUNNER_ROLLBACK_STDOUT")
    add(clean.ROLLBACK_STDERR_PATH, b"", "CLEAN_RUNNER_ROLLBACK_STDERR")
    add(clean.ROLLBACK_RC_PATH, b"0\n", "CLEAN_RUNNER_ROLLBACK_RC")
    rollback = {
        "schema": "triad.b00r.clean_runner_rollback_proof.v1",
        "run_id": run_id,
        "source_merge_sha": source_merge,
        "source_merge_tree": source_tree,
        "mainline_parent_sha": parents[0],
        "mainline_parent_tree": parent_tree,
        "command": ["git", "revert", "--no-commit", "-m", "1", source_merge],
        "stdout_path": clean.ROLLBACK_STDOUT_PATH,
        "stdout_sha256": _sha(b""),
        "stdout_size": 0,
        "stderr_path": clean.ROLLBACK_STDERR_PATH,
        "stderr_sha256": _sha(b""),
        "stderr_size": 0,
        "rc_path": clean.ROLLBACK_RC_PATH,
        "rc_sha256": _sha(b"0\n"),
        "rc_size": 2,
        "exit_code": 0,
        "result_tree_sha": parent_tree,
        "result": "PASS",
    }
    add(clean.ROLLBACK_PROOF_PATH, _canonical(rollback), "ROLLBACK_PROOF")

    run = {
        "schema": "triad.b00r.clean_runner_run.v1",
        "profile": clean.PROFILE,
        "repository": clean.REPOSITORY,
        "run_id": run_id,
        "source_merge_sha": source_merge,
        "source_merge_tree": source_tree,
        "source_merge_time_us": source_time,
        "started_at_us": 40_000_000,
        "finished_at_us": 70_000_000,
        "runner_facts_path": clean.RUNNER_FACTS_PATH,
        "runner_facts_sha256": _sha((repo / clean.RUNNER_FACTS_PATH).read_bytes()),
        "package_snapshot_path": clean.PACKAGE_SNAPSHOT_PATH,
        "package_snapshot_sha256": _sha((repo / clean.PACKAGE_SNAPSHOT_PATH).read_bytes()),
        "source_identity_path": clean.SOURCE_IDENTITY_PATH,
        "source_identity_sha256": _sha((repo / clean.SOURCE_IDENTITY_PATH).read_bytes()),
        "test_manifest_path": clean.TEST_MANIFEST_PATH,
        "test_manifest_sha256": _sha((repo / clean.TEST_MANIFEST_PATH).read_bytes()),
        "config_bundle_path": clean.CONFIG_BUNDLE_PATH,
        "config_bundle_sha256": _sha((repo / clean.CONFIG_BUNDLE_PATH).read_bytes()),
        "rollback_proof_path": clean.ROLLBACK_PROOF_PATH,
        "rollback_proof_sha256": _sha((repo / clean.ROLLBACK_PROOF_PATH).read_bytes()),
        "commands": commands,
        "result": "PASS",
    }
    add(clean.RUN_PATH, _canonical(run), "CLEAN_RUNNER_RUN")

    entries = [
        _entry(repo, path, role, unique)
        for path, (role, unique) in sorted(roles.items())
    ]
    by_path = {entry["path"]: entry for entry in entries}
    payload = {
        "source_merge_sha": source_merge,
        "source_merge_tree": source_tree,
        "source_merge_time_us": source_time,
        "observed_at_us": 80_000_000,
        "emitted_at_us": 90_000_000,
        "activation_result": "DENIED_SAFE_HOLD",
        "levers": copy.deepcopy(clean.SAFE_HOLD_LEVERS),
        "workflow_sha256": by_path[clean.SOURCE_WORKFLOW_PATH]["sha256"],
        "contract_manifest_sha256": by_path[clean.CONTRACT_MANIFEST_PATH]["sha256"],
        "test_manifest_sha256": by_path[clean.TEST_MANIFEST_PATH]["sha256"],
        "config_bundle_sha256": by_path[clean.CONFIG_BUNDLE_PATH]["sha256"],
        "rollback_proof_sha256": by_path[clean.ROLLBACK_PROOF_PATH]["sha256"],
    }
    _git(repo, "checkout", "-b", "receipt")
    _git(repo, "add", "evidence")
    _git(repo, "commit", "-m", "receipt evidence", instant="1970-01-01T00:01:40Z")
    head = _git(repo, "rev-parse", "HEAD")
    return {
        "root": repo,
        "entries": entries,
        "payload": payload,
        "head": head,
        "source_merge": source_merge,
        "source_tree": source_tree,
    }


@pytest.fixture()
def valid_bundle(tmp_path):
    return _build_valid_bundle(tmp_path)


def _entry_for(bundle: dict, path: str) -> dict:
    return next(entry for entry in bundle["entries"] if entry["path"] == path)


def _refresh_entry(bundle: dict, path: str) -> None:
    data = (bundle["root"] / path).read_bytes()
    entry = _entry_for(bundle, path)
    entry["size"] = len(data)
    entry["sha256"] = _sha(data)


def _refresh_run(bundle: dict, run: dict) -> None:
    _write(bundle["root"], clean.RUN_PATH, _canonical(run))
    _refresh_entry(bundle, clean.RUN_PATH)


def _commit(bundle: dict, message: str) -> None:
    _git(bundle["root"], "add", "evidence")
    _git(bundle["root"], "commit", "-m", message)
    bundle["head"] = _git(bundle["root"], "rev-parse", "HEAD")


def _validate(bundle: dict) -> None:
    clean.validate_bundle(
        bundle["root"], bundle["entries"], bundle["payload"], bundle["head"],
        now_us=100_000_000,
    )


def test_valid_bundle_binds_exact_source_runner_packages_commands_and_rollback(valid_bundle):
    _validate(valid_bundle)


@pytest.mark.parametrize(
    ("relative", "reason"),
    [
        ("pkg/__pycache__/evil.pyc", "BYTECODE_CACHE_FORBIDDEN"),
        (
            "tools/b00r_pytest_inventory/__init__.py",
            "INVENTORY_PACKAGE_SHADOW_FORBIDDEN",
        ),
        (
            "tools/b00r_pytest_inventory.cpython-311-x86_64-linux-gnu.so",
            "NATIVE_EXTENSION_FORBIDDEN",
        ),
    ],
)
def test_verifier_rejects_source_merge_the_producer_refuses(
    tmp_path, relative, reason
):
    bundle = _build_valid_bundle(tmp_path, {relative: b"tracked executable shadow"})
    with pytest.raises(clean.CleanRunnerError, match=reason):
        _validate(bundle)


@pytest.mark.parametrize(
    "raw",
    [
        b"120000 blob " + b"1" * 40 + b"\tlink\0",
        b"160000 commit " + b"1" * 40 + b"\tsubmodule\0",
        (
            b"100644 blob " + b"1" * 40 + b"\tduplicate\0"
            + b"100644 blob " + b"2" * 40 + b"\tduplicate\0"
        ),
        b"100644 blob not-an-object-id\tmodule.py\0",
        b"100644 blob " + b"1" * 40 + b"\t../escape.py\0",
    ],
)
def test_shared_source_tree_parser_rejects_unsafe_rows(raw):
    with pytest.raises(clean.CleanRunnerError, match="SOURCE_TREE"):
        clean.safe_source_tree_entries(raw)


def test_empty_stream_allowlist_is_exact_and_closed():
    expected = {
        f"{clean.EVIDENCE_ROOT}/commands/{ordinal:02d}-{command_id}/stderr.bin"
        for ordinal, (command_id, _argv, _seed) in enumerate(clean.REQUIRED_COMMANDS)
    } | {clean.ROLLBACK_STDOUT_PATH, clean.ROLLBACK_STDERR_PATH}
    assert clean.ALLOWED_EMPTY_PATHS == expected
    assert len(clean.ALLOWED_EMPTY_PATHS) == 13


def test_cli_verify_accepts_the_committed_bundle(valid_bundle, capsys):
    manifest_path = "evidence/B00R_G2/evidence_manifest.json"
    receipt_path = "evidence/receipts/B00R.g2.receipt.v3.json"
    _write(valid_bundle["root"], manifest_path, _canonical({
        "entries": valid_bundle["entries"],
    }))
    _write(valid_bundle["root"], receipt_path, _canonical({
        "payload": valid_bundle["payload"],
    }))
    _git(valid_bundle["root"], "add", "evidence")
    _git(valid_bundle["root"], "commit", "-m", "add manifest and receipt")
    head = _git(valid_bundle["root"], "rev-parse", "HEAD")
    assert clean.main([
        "verify", "--root", str(valid_bundle["root"]),
        "--manifest", manifest_path, "--receipt", receipt_path,
        "--expected-head", head, "--now-us", "100000000",
    ]) == 0
    assert "OK: B00R G2 clean-runner bundle bound" in capsys.readouterr().out


def test_clean_runner_namespace_rejects_semantically_unexpected_file(valid_bundle):
    path = f"{clean.EVIDENCE_ROOT}/claimed-extra.json"
    _write(valid_bundle["root"], path, _canonical({"result": "PASS"}))
    valid_bundle["entries"].append(
        _entry(valid_bundle["root"], path, "CLEAN_RUNNER_EXTRA", True)
    )
    _commit(valid_bundle, "add unprofiled clean runner file")
    with pytest.raises(clean.CleanRunnerError, match="PROFILE_PATHS_MISMATCH"):
        _validate(valid_bundle)


def test_runner_output_checkout_and_venv_paths_must_be_disjoint(valid_bundle):
    facts = json.loads((valid_bundle["root"] / clean.RUNNER_FACTS_PATH).read_bytes())
    facts["evidence_output_root"] = f"{facts['checkout_root']}/output"
    _write(valid_bundle["root"], clean.RUNNER_FACTS_PATH, _canonical(facts))
    _refresh_entry(valid_bundle, clean.RUNNER_FACTS_PATH)
    run = json.loads((valid_bundle["root"] / clean.RUN_PATH).read_bytes())
    run["runner_facts_sha256"] = _entry_for(
        valid_bundle, clean.RUNNER_FACTS_PATH
    )["sha256"]
    _refresh_run(valid_bundle, run)
    _commit(valid_bundle, "overlap capture paths")
    with pytest.raises(clean.CleanRunnerError, match="PATH_ISOLATION_MISMATCH"):
        _validate(valid_bundle)


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("python_version", "3.11.evil", "PYTHON_VERSION_MISMATCH"),
        ("python_executable_sha256", "0" * 64, "PYTHON_DIGEST_INVALID"),
    ],
)
def test_runner_facts_reject_malformed_runtime_identity(
    valid_bundle, field, value, reason
):
    facts = json.loads((valid_bundle["root"] / clean.RUNNER_FACTS_PATH).read_bytes())
    facts[field] = value
    _write(valid_bundle["root"], clean.RUNNER_FACTS_PATH, _canonical(facts))
    _refresh_entry(valid_bundle, clean.RUNNER_FACTS_PATH)
    run = json.loads((valid_bundle["root"] / clean.RUN_PATH).read_bytes())
    run["runner_facts_sha256"] = _entry_for(
        valid_bundle, clean.RUNNER_FACTS_PATH
    )["sha256"]
    _refresh_run(valid_bundle, run)
    _commit(valid_bundle, f"malformed runner fact {field}")
    with pytest.raises(clean.CleanRunnerError, match=reason):
        _validate(valid_bundle)


def test_pytest_raw_stdout_must_match_plugin_inventory(valid_bundle):
    run = json.loads((valid_bundle["root"] / clean.RUN_PATH).read_bytes())
    record = run["commands"][0]
    bad = b".. [100%]\n2 passed in 0.01s\n"
    _write(valid_bundle["root"], record["stdout_path"], bad)
    _refresh_entry(valid_bundle, record["stdout_path"])
    record["stdout_sha256"] = _sha(bad)
    record["stdout_size"] = len(bad)
    _refresh_run(valid_bundle, run)
    _commit(valid_bundle, "forge pytest summary")
    with pytest.raises(clean.CleanRunnerError, match="PYTEST_STDOUT_MISMATCH"):
        _validate(valid_bundle)


@pytest.mark.parametrize("role", sorted(clean.ROLE_PATHS))
def test_five_reserved_roles_reject_dummy_blobs(valid_bundle, role):
    path = clean.ROLE_PATHS[role]
    dummy = _canonical({"role": role})
    _write(valid_bundle["root"], path, dummy)
    _refresh_entry(valid_bundle, path)
    payload_field = {
        "WORKFLOW": "workflow_sha256",
        "CONTRACT_MANIFEST": "contract_manifest_sha256",
        "TEST_MANIFEST": "test_manifest_sha256",
        "CONFIG_BUNDLE": "config_bundle_sha256",
        "ROLLBACK_PROOF": "rollback_proof_sha256",
    }[role]
    valid_bundle["payload"][payload_field] = _sha(dummy)
    _commit(valid_bundle, f"dummy {role}")
    with pytest.raises(clean.CleanRunnerError):
        _validate(valid_bundle)


def test_nonzero_raw_rc_cannot_hide_behind_zero_summary(valid_bundle):
    run = json.loads((valid_bundle["root"] / clean.RUN_PATH).read_bytes())
    record = run["commands"][0]
    _write(valid_bundle["root"], record["rc_path"], b"7\n")
    _refresh_entry(valid_bundle, record["rc_path"])
    record["rc_sha256"] = _sha(b"7\n")
    record["rc_size"] = 2
    _refresh_run(valid_bundle, run)
    _commit(valid_bundle, "nonzero raw rc")
    with pytest.raises(clean.CleanRunnerError, match="COMMAND_RC_NOT_ZERO"):
        _validate(valid_bundle)


def test_required_command_reordering_is_rejected(valid_bundle):
    run = json.loads((valid_bundle["root"] / clean.RUN_PATH).read_bytes())
    run["commands"][0], run["commands"][1] = run["commands"][1], run["commands"][0]
    _refresh_run(valid_bundle, run)
    _commit(valid_bundle, "reorder commands")
    with pytest.raises(clean.CleanRunnerError, match="COMMAND_PROFILE_MISMATCH"):
        _validate(valid_bundle)


def test_seed_inventory_mismatch_is_rejected_even_when_summary_claims_identical(valid_bundle):
    changed = b"tests/test_example.py::test_different\n"
    path = clean.TEST_IDS_PATHS["1"]
    _write(valid_bundle["root"], path, changed)
    _refresh_entry(valid_bundle, path)
    result_path = clean.PYTEST_RESULT_PATHS["1"]
    result = json.loads((valid_bundle["root"] / result_path).read_bytes())
    result["test_ids_sha256"] = _sha(changed)
    _write(valid_bundle["root"], result_path, _canonical(result))
    _refresh_entry(valid_bundle, result_path)
    test_manifest = json.loads(
        (valid_bundle["root"] / clean.TEST_MANIFEST_PATH).read_bytes()
    )
    test_manifest["seed_runs"][1]["test_ids_sha256"] = _sha(changed)
    test_manifest["seed_runs"][1]["result_sha256"] = _entry_for(
        valid_bundle, result_path
    )["sha256"]
    _write(valid_bundle["root"], clean.TEST_MANIFEST_PATH, _canonical(test_manifest))
    _refresh_entry(valid_bundle, clean.TEST_MANIFEST_PATH)
    valid_bundle["payload"]["test_manifest_sha256"] = _entry_for(
        valid_bundle, clean.TEST_MANIFEST_PATH
    )["sha256"]
    run = json.loads((valid_bundle["root"] / clean.RUN_PATH).read_bytes())
    run["test_manifest_sha256"] = valid_bundle["payload"]["test_manifest_sha256"]
    _refresh_run(valid_bundle, run)
    _commit(valid_bundle, "diverge seed inventory")
    with pytest.raises(clean.CleanRunnerError, match="TEST_INVENTORIES_DIFFER"):
        _validate(valid_bundle)


def test_missing_constrained_package_is_rejected(valid_bundle):
    snapshot = json.loads(
        (valid_bundle["root"] / clean.PACKAGE_SNAPSHOT_PATH).read_bytes()
    )
    snapshot["distributions"] = [
        row for row in snapshot["distributions"] if row["name"] != "pytest"
    ]
    _write(valid_bundle["root"], clean.PACKAGE_SNAPSHOT_PATH, _canonical(snapshot))
    _refresh_entry(valid_bundle, clean.PACKAGE_SNAPSHOT_PATH)
    run = json.loads((valid_bundle["root"] / clean.RUN_PATH).read_bytes())
    run["package_snapshot_sha256"] = _entry_for(
        valid_bundle, clean.PACKAGE_SNAPSHOT_PATH
    )["sha256"]
    _refresh_run(valid_bundle, run)
    _commit(valid_bundle, "drop constrained package")
    with pytest.raises(clean.CleanRunnerError, match="CONSTRAINT_PACKAGE_MISMATCH"):
        _validate(valid_bundle)


def test_missing_required_pip_distribution_is_rejected(valid_bundle):
    snapshot = json.loads(
        (valid_bundle["root"] / clean.PACKAGE_SNAPSHOT_PATH).read_bytes()
    )
    snapshot["distributions"] = [
        row for row in snapshot["distributions"] if row["name"] != "pip"
    ]
    _write(valid_bundle["root"], clean.PACKAGE_SNAPSHOT_PATH, _canonical(snapshot))
    _refresh_entry(valid_bundle, clean.PACKAGE_SNAPSHOT_PATH)
    run = json.loads((valid_bundle["root"] / clean.RUN_PATH).read_bytes())
    run["package_snapshot_sha256"] = _entry_for(
        valid_bundle, clean.PACKAGE_SNAPSHOT_PATH
    )["sha256"]
    _refresh_run(valid_bundle, run)
    _commit(valid_bundle, "drop required pip distribution")
    with pytest.raises(clean.CleanRunnerError, match="PACKAGE_SET_MISMATCH"):
        _validate(valid_bundle)


@pytest.mark.parametrize(
    "secret",
    [
        b"tmc_1234567890abcdef1234567890abcdef",
        b"-----BEGIN PRIVATE KEY-----",
    ],
    ids=["token-pattern", "private-key-pattern"],
)
def test_valid_success_stream_with_secret_material_is_rejected(valid_bundle, secret):
    run = json.loads((valid_bundle["root"] / clean.RUN_PATH).read_bytes())
    record = run["commands"][3]
    path = record["stdout_path"]
    raw = (valid_bundle["root"] / path).read_bytes() + secret + b"\n"
    _write(valid_bundle["root"], path, raw)
    _refresh_entry(valid_bundle, path)
    record["stdout_sha256"] = _sha(raw)
    record["stdout_size"] = len(raw)
    _refresh_run(valid_bundle, run)
    _commit(valid_bundle, "embed secret in otherwise valid success stream")
    with pytest.raises(clean.CleanRunnerError, match="SECRET_MATERIAL_DETECTED"):
        _validate(valid_bundle)


def test_installed_package_snapshot_rejects_zero_file_digest(valid_bundle):
    snapshot = json.loads(
        (valid_bundle["root"] / clean.PACKAGE_SNAPSHOT_PATH).read_bytes()
    )
    snapshot["distributions"][0]["files"][0]["sha256"] = "0" * 64
    _write(valid_bundle["root"], clean.PACKAGE_SNAPSHOT_PATH, _canonical(snapshot))
    _refresh_entry(valid_bundle, clean.PACKAGE_SNAPSHOT_PATH)
    run = json.loads((valid_bundle["root"] / clean.RUN_PATH).read_bytes())
    run["package_snapshot_sha256"] = _entry_for(
        valid_bundle, clean.PACKAGE_SNAPSHOT_PATH
    )["sha256"]
    _refresh_run(valid_bundle, run)
    _commit(valid_bundle, "zero installed package file digest")
    with pytest.raises(clean.CleanRunnerError, match="PACKAGE_FILE_INVALID"):
        _validate(valid_bundle)


def test_fabricated_reproducible_build_hashes_are_rejected(valid_bundle):
    run = json.loads((valid_bundle["root"] / clean.RUN_PATH).read_bytes())
    record = run["commands"][5]
    bad = b"OK: reproducible sdist=not-a-hash wheel=also-not-a-hash\n"
    _write(valid_bundle["root"], record["stdout_path"], bad)
    _refresh_entry(valid_bundle, record["stdout_path"])
    record["stdout_sha256"] = _sha(bad)
    record["stdout_size"] = len(bad)
    _refresh_run(valid_bundle, run)
    _commit(valid_bundle, "fake build hashes")
    with pytest.raises(clean.CleanRunnerError, match="REPRODUCIBLE_BUILD_OUTPUT_INVALID"):
        _validate(valid_bundle)


def test_reproducible_build_output_rejects_zero_artifact_digest(valid_bundle):
    run = json.loads((valid_bundle["root"] / clean.RUN_PATH).read_bytes())
    record = run["commands"][5]
    bad = (
        f"OK: reproducible sdist={'0' * 64} wheel={'2' * 64}\n"
    ).encode()
    _write(valid_bundle["root"], record["stdout_path"], bad)
    _refresh_entry(valid_bundle, record["stdout_path"])
    record["stdout_sha256"] = _sha(bad)
    record["stdout_size"] = len(bad)

    config = json.loads((valid_bundle["root"] / clean.CONFIG_BUNDLE_PATH).read_bytes())
    config["reproducible_sdist_sha256"] = "0" * 64
    _write(valid_bundle["root"], clean.CONFIG_BUNDLE_PATH, _canonical(config))
    _refresh_entry(valid_bundle, clean.CONFIG_BUNDLE_PATH)
    valid_bundle["payload"]["config_bundle_sha256"] = _entry_for(
        valid_bundle, clean.CONFIG_BUNDLE_PATH
    )["sha256"]
    run["config_bundle_sha256"] = valid_bundle["payload"]["config_bundle_sha256"]
    _refresh_run(valid_bundle, run)
    _commit(valid_bundle, "zero reproducible artifact digest")
    with pytest.raises(clean.CleanRunnerError, match="REPRODUCIBLE_BUILD_OUTPUT_INVALID"):
        _validate(valid_bundle)


def test_safe_hold_config_drift_is_rejected(valid_bundle):
    config = json.loads((valid_bundle["root"] / clean.CONFIG_BUNDLE_PATH).read_bytes())
    config["levers"]["paper_activation"] = "LIVE"
    _write(valid_bundle["root"], clean.CONFIG_BUNDLE_PATH, _canonical(config))
    _refresh_entry(valid_bundle, clean.CONFIG_BUNDLE_PATH)
    valid_bundle["payload"]["config_bundle_sha256"] = _entry_for(
        valid_bundle, clean.CONFIG_BUNDLE_PATH
    )["sha256"]
    run = json.loads((valid_bundle["root"] / clean.RUN_PATH).read_bytes())
    run["config_bundle_sha256"] = valid_bundle["payload"]["config_bundle_sha256"]
    _refresh_run(valid_bundle, run)
    _commit(valid_bundle, "drift safe hold")
    with pytest.raises(clean.CleanRunnerError, match="CONFIG_BUNDLE_MISMATCH"):
        _validate(valid_bundle)


def test_rollback_result_tree_must_equal_first_parent_tree(valid_bundle):
    proof = json.loads((valid_bundle["root"] / clean.ROLLBACK_PROOF_PATH).read_bytes())
    proof["result_tree_sha"] = valid_bundle["source_tree"]
    _write(valid_bundle["root"], clean.ROLLBACK_PROOF_PATH, _canonical(proof))
    _refresh_entry(valid_bundle, clean.ROLLBACK_PROOF_PATH)
    valid_bundle["payload"]["rollback_proof_sha256"] = _entry_for(
        valid_bundle, clean.ROLLBACK_PROOF_PATH
    )["sha256"]
    run = json.loads((valid_bundle["root"] / clean.RUN_PATH).read_bytes())
    run["rollback_proof_sha256"] = valid_bundle["payload"]["rollback_proof_sha256"]
    _refresh_run(valid_bundle, run)
    _commit(valid_bundle, "forge rollback tree")
    with pytest.raises(clean.CleanRunnerError, match="ROLLBACK_PROOF_MISMATCH"):
        _validate(valid_bundle)
