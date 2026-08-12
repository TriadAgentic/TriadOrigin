"""Adversarial tests for the truthful B00R generation-2 clean-runner producer."""

from __future__ import annotations

import os
import pathlib
import py_compile
import stat
import subprocess
import sys

import pytest

from tools import b00r_clean_runner as clean
from tools import b00r_clean_runner_capture as capture


SOURCE = "1" * 40
TREE = "2" * 40
PARENT0 = "3" * 40
PARENT1 = "4" * 40


def test_capture_roots_must_be_absent_canonical_and_pairwise_disjoint(tmp_path):
    clone = tmp_path / "clone"
    venv = tmp_path / "venv"
    output = tmp_path / "output"
    assert capture.prepare_roots(clone, venv, output) == (clone, venv, output)

    clone.mkdir()
    with pytest.raises(capture.CleanRunnerCaptureError, match="CLONE_ROOT_PREEXISTS"):
        capture.prepare_roots(clone, venv, output)

    with pytest.raises(capture.CleanRunnerCaptureError, match="CAPTURE_ROOTS_OVERLAP"):
        capture.prepare_roots(tmp_path / "new", tmp_path / "new" / "venv", output)

    with pytest.raises(capture.CleanRunnerCaptureError, match="NOT_CANONICAL_ABSOLUTE"):
        capture.prepare_roots("relative-clone", venv, output)


def test_capture_roots_reject_even_broken_symlink_targets(tmp_path):
    clone = tmp_path / "clone"
    venv = tmp_path / "venv"
    output = tmp_path / "output"
    output.symlink_to(tmp_path / "absent-target", target_is_directory=True)
    assert os.path.lexists(output)
    with pytest.raises(capture.CleanRunnerCaptureError, match="OUTPUT_ROOT_SYMLINK"):
        capture.prepare_roots(clone, venv, output)


def _source_git_response(args: tuple[str, ...], *, origin_main: str = SOURCE, parents=2):
    mapping = {
        ("remote", "get-url", "origin"): (capture.ORIGIN_URL + "\n").encode(),
        ("config", "--get", "remote.origin.tagOpt"): b"--no-tags\n",
        ("tag", "--list"): b"",
        ("rev-parse", "refs/remotes/origin/main"): (origin_main + "\n").encode(),
        ("rev-parse", "HEAD"): (SOURCE + "\n").encode(),
        ("rev-parse", "--abbrev-ref", "HEAD"): b"HEAD\n",
        ("rev-parse", f"{SOURCE}^{{tree}}"): (TREE + "\n").encode(),
        ("status", "--porcelain=v1", "-z", "--untracked-files=all"): b"",
        (
            "status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignored=matching",
        ): b"",
        ("replace", "-l"): b"",
        ("rev-parse", "--is-shallow-repository"): b"false\n",
        ("ls-tree", "-r", "-z", "--full-tree", SOURCE): (
            b"100644 blob " + b"5" * 40 + b"\ttracked.txt\0"
        ),
        ("show", "-s", "--format=%ct", SOURCE): b"1\n",
    }
    parent_values = [PARENT0, PARENT1][:parents]
    mapping[("cat-file", "-p", SOURCE)] = (
        "tree " + TREE + "\n"
        + "".join(f"parent {parent}\n" for parent in parent_values)
        + "author Capture Test <capture@example.invalid> 1 +0000\n"
        + "committer Capture Test <capture@example.invalid> 1 +0000\n\nmerge\n"
    ).encode()
    return mapping[args]


@pytest.mark.parametrize(
    ("origin_main", "parents", "reason"),
    [
        ("9" * 40, 2, "SOURCE_NOT_LIVE_ORIGIN_MAIN"),
        (SOURCE, 1, "SOURCE_NOT_RAW_TWO_PARENT_MERGE"),
    ],
)
def test_source_identity_rejects_stale_main_and_nonmerge(
    tmp_path, monkeypatch, origin_main, parents, reason
):
    def git_response(_root, *args):
        if args == ("rev-parse", "--show-toplevel"):
            return f"{tmp_path}\n".encode()
        if args == ("rev-parse", "--absolute-git-dir"):
            return f"{tmp_path / '.git'}\n".encode()
        if args == ("rev-parse", "--path-format=absolute", "--git-common-dir"):
            return f"{tmp_path / '.git'}\n".encode()
        return _source_git_response(
            tuple(args), origin_main=origin_main, parents=parents
        )

    monkeypatch.setattr(
        capture,
        "_git_stdout",
        git_response,
    )
    monkeypatch.setattr(
        capture, "_bound_local_git_config", lambda *_args, **_kwargs: (b"config", "0" * 64)
    )
    monkeypatch.setattr(
        capture, "_bound_git_control_surface", lambda *_args, **_kwargs: "1" * 64
    )
    monkeypatch.setattr(capture, "_assert_git_objects_intact", lambda *_args: None)
    monkeypatch.setattr(capture, "_assert_source_refs_direct", lambda *_args: None)
    monkeypatch.setattr(capture, "_assert_source_checkout_closed", lambda *_args: 1)
    with pytest.raises(capture.CleanRunnerCaptureError, match=reason):
        capture.assert_source_identity(tmp_path, SOURCE)


def test_clone_command_is_fixed_canonical_https_no_local_no_tags(monkeypatch, tmp_path):
    calls = []

    def fake_process(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    monkeypatch.setattr(capture, "_process", fake_process)
    monkeypatch.setattr(
        capture,
        "assert_source_identity",
        lambda root, source: {"source_merge_sha": source, "root": str(root)},
    )
    result = capture.clone_source(tmp_path / "clone", SOURCE)
    assert result["source_merge_sha"] == SOURCE
    assert calls[0][0] == [
        "git", "clone", "--no-local", "--no-tags", "--single-branch", "--branch",
        "main", "--", capture.ORIGIN_URL, str(tmp_path / "clone"),
    ]
    assert "token" not in " ".join(calls[0][0]).lower()
    assert calls[1][0][-3:] == ["checkout", "--detach", SOURCE]


def test_executing_capture_profile_bytes_must_equal_source_merge(
    monkeypatch, tmp_path
):
    invoking = tmp_path / "invoking"
    tools = invoking / "tools"
    tools.mkdir(parents=True)
    paths = {
        "tools/__init__.py": tools / "__init__.py",
        "tools/b00r_clean_runner_capture.py": tools / "b00r_clean_runner_capture.py",
        "tools/b00r_clean_runner.py": tools / "b00r_clean_runner.py",
        "tools/b00r_pytest_inventory.py": tools / "b00r_pytest_inventory.py",
    }
    for index, path in enumerate(paths.values()):
        path.write_bytes(f"profile-{index}\n".encode())
    monkeypatch.setattr(capture, "ROOT", invoking)
    monkeypatch.setattr(capture, "_executing_source_paths", lambda: paths)
    monkeypatch.setattr(
        capture,
        "_retained_executing_source_bytes",
        lambda: {rel: path.read_bytes() for rel, path in paths.items()},
    )
    monkeypatch.setattr(
        capture,
        "_git_stdout",
        lambda _root, *args: paths[args[-1].split(":", 1)[1]].read_bytes(),
    )
    capture.assert_executing_source_bytes(tmp_path / "clone", SOURCE)


@pytest.mark.parametrize(
    "mismatch_rel",
    [
        "tools/b00r_clean_runner_capture.py",
        "tools/b00r_clean_runner.py",
        "tools/b00r_pytest_inventory.py",
    ],
)
def test_each_executing_profile_file_one_byte_mismatch_fails_closed(
    monkeypatch, tmp_path, mismatch_rel
):
    invoking = tmp_path / "invoking"
    tools = invoking / "tools"
    tools.mkdir(parents=True)
    paths = {
        rel: tools / pathlib.PurePosixPath(rel).name
        for rel in (
            "tools/b00r_clean_runner_capture.py",
            "tools/b00r_clean_runner.py",
            "tools/b00r_pytest_inventory.py",
        )
    }
    for path in paths.values():
        path.write_bytes(b"exact-profile\n")
    monkeypatch.setattr(capture, "ROOT", invoking)
    monkeypatch.setattr(capture, "_executing_source_paths", lambda: paths)
    monkeypatch.setattr(
        capture,
        "_retained_executing_source_bytes",
        lambda: {rel: path.read_bytes() for rel, path in paths.items()},
    )

    def committed_blob(_root, *args):
        rel = args[-1].split(":", 1)[1]
        data = paths[rel].read_bytes()
        return data + b"x" if rel == mismatch_rel else data

    monkeypatch.setattr(capture, "_git_stdout", committed_blob)
    with pytest.raises(capture.CleanRunnerCaptureError, match="BYTES_MISMATCH"):
        capture.assert_executing_source_bytes(tmp_path / "clone", SOURCE)


def test_executing_source_change_after_retention_fails_closed(monkeypatch, tmp_path):
    invoking = tmp_path / "invoking"
    tools = invoking / "tools"
    tools.mkdir(parents=True)
    paths = {
        rel: tools / pathlib.PurePosixPath(rel).name
        for rel in (
            "tools/b00r_clean_runner_capture.py",
            "tools/b00r_clean_runner.py",
            "tools/b00r_pytest_inventory.py",
        )
    }
    for path in paths.values():
        path.write_bytes(b"retained-profile\n")
    retained = {rel: path.read_bytes() for rel, path in paths.items()}
    paths["tools/b00r_clean_runner.py"].write_bytes(b"changed-after-load\n")
    monkeypatch.setattr(capture, "ROOT", invoking)
    monkeypatch.setattr(capture, "_executing_source_paths", lambda: paths)
    monkeypatch.setattr(capture, "_retained_executing_source_bytes", lambda: retained)
    monkeypatch.setattr(
        capture,
        "_git_stdout",
        lambda _root, *args: retained[args[-1].split(":", 1)[1]],
    )
    with pytest.raises(capture.CleanRunnerCaptureError, match="CHANGED_AFTER_LOAD"):
        capture.assert_executing_source_bytes(tmp_path / "clone", SOURCE)


def _write_matching_malicious_cache(root: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    source = root / "cached_module.py"
    cache = root / "__pycache__/cached_module.cpython-311.pyc"
    cache.parent.mkdir(parents=True)
    timestamp = 1_700_000_000
    source.write_bytes(b"VALUE = 'evil'\n")
    os.utime(source, (timestamp, timestamp))
    py_compile.compile(str(source), cfile=str(cache), doraise=True)
    source.write_bytes(b"VALUE = 'good'\n")
    os.utime(source, (timestamp, timestamp))
    return source, cache


def test_explicit_controller_module_load_ignores_valid_malicious_pyc(tmp_path):
    source, cache = _write_matching_malicious_cache(tmp_path)
    assert cache.is_file()
    module, retained = capture._compile_source_module(source, "cached_module")
    assert retained == b"VALUE = 'good'\n"
    assert module.VALUE == "good"


def test_source_tree_rejects_even_tracked_valid_bytecode_cache(tmp_path):
    repo, _source = _closed_source_repo(tmp_path)
    module_source, cache = _write_matching_malicious_cache(repo / "package")
    _git_test(repo, "add", str(module_source.relative_to(repo)))
    _git_test(repo, "add", "-f", str(cache.relative_to(repo)))
    _git_test(repo, "commit", "-m", "tracked malicious cache")
    source = _git_test(repo, "rev-parse", "HEAD")
    with pytest.raises(capture.CleanRunnerCaptureError, match="BYTECODE_CACHE_FORBIDDEN"):
        capture._source_tree_entries(repo, source)


@pytest.mark.parametrize(
    ("relative", "reason"),
    [
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
def test_source_tree_rejects_inventory_package_or_native_shadow(
    tmp_path, relative, reason
):
    repo, _source = _closed_source_repo(tmp_path)
    shadow = repo / relative
    shadow.parent.mkdir(parents=True, exist_ok=True)
    shadow.write_bytes(b"shadow")
    _git_test(repo, "add", relative)
    _git_test(repo, "commit", "-m", "tracked inventory shadow")
    source = _git_test(repo, "rev-parse", "HEAD")
    with pytest.raises(capture.CleanRunnerCaptureError, match=reason):
        capture._source_tree_entries(repo, source)


def test_bootstrap_python_path_is_bound_and_may_not_be_a_symlink(
    tmp_path, monkeypatch
):
    real = tmp_path / "python3.11-real"
    real.write_bytes(b"binary")
    alias = tmp_path / "python3.11"
    alias.symlink_to(real)
    with pytest.raises(capture.CleanRunnerCaptureError, match="ROOT_SYMLINK"):
        capture.create_venv(alias, tmp_path / "venv")

    monkeypatch.setattr(
        capture,
        "_python_probe",
        lambda _path: {
            "implementation": "CPython",
            "version": "3.11.13",
            "executable": "/different/python",
            "prefix": "/usr",
            "base_prefix": "/usr",
        },
    )
    with pytest.raises(capture.CleanRunnerCaptureError, match="NOT_SYSTEM_CPYTHON_3_11"):
        capture.create_venv(real, tmp_path / "venv")


def test_required_command_uses_only_declared_env_and_preserves_nonzero_streams(
    tmp_path, monkeypatch
):
    clone = tmp_path / "clone"
    output = tmp_path / "output"
    clone.mkdir()
    output.mkdir()
    seen = {}

    def fail_first(argv, **kwargs):
        seen["argv"] = argv
        seen["env"] = kwargs["env"]
        return subprocess.CompletedProcess(argv, 7, b"raw-stdout\n", b"raw-stderr\n")

    monkeypatch.setattr(capture, "_process", fail_first)
    with pytest.raises(capture.CleanRunnerCaptureError, match="REQUIRED_COMMAND_NONZERO"):
        capture.run_required_commands(
            clone,
            output,
            pathlib.Path("/fresh/venv/bin/python"),
            "a" * 32,
            SOURCE,
            lambda: None,
        )
    expected_env = capture._command_env(
        clone, output, "a" * 32, SOURCE, "pytest-seed0", "0"
    )
    assert seen["env"] == expected_env
    assert "HOME" not in seen["env"]
    base = output / clean.EVIDENCE_ROOT / "commands" / "00-pytest-seed0"
    assert (base / "stdout.bin").read_bytes() == b"raw-stdout\n"
    assert (base / "stderr.bin").read_bytes() == b"raw-stderr\n"
    assert (base / "rc.txt").read_bytes() == b"7\n"


def test_declared_command_and_install_env_disable_pip_config_and_prompts(tmp_path):
    assert clean.BASE_ENV["PIP_CONFIG_FILE"] == "/dev/null"
    assert clean.BASE_ENV["PIP_NO_INPUT"] == "1"
    env = capture._install_env(tmp_path / "clone")
    assert env["PIP_CONFIG_FILE"] == "/dev/null"
    assert env["PIP_NO_INPUT"] == "1"
    assert env["PIP_NO_COMPILE"] == "1"
    assert env["PYTHONDONTWRITEBYTECODE"] == "1"
    assert env["PYTHONSAFEPATH"] == "1"
    assert env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
    assert env["GIT_CONFIG_COUNT"] == "3"
    assert env["GIT_CONFIG_KEY_0"] == "core.hooksPath"
    assert env["GIT_CONFIG_VALUE_0"] == "/dev/null"
    assert env["GIT_CONFIG_KEY_1"] == "core.commitGraph"
    assert env["GIT_CONFIG_VALUE_1"] == "false"
    assert env["GIT_CONFIG_KEY_2"] == "core.multiPackIndex"
    assert env["GIT_CONFIG_VALUE_2"] == "false"


def test_required_python_launches_use_safe_path_and_direct_inventory_script():
    assert clean.PYTEST_ARGV == [
        "$PYTHON", "-P", "tools/b00r_pytest_inventory.py"
    ]
    assert all(argv[1] == "-P" for _name, argv, _seed in clean.REQUIRED_COMMANDS)


def test_complete_canonical_collector_ids_pass_shared_secret_scanner():
    root = pathlib.Path(__file__).resolve().parents[2]
    env = dict(
        clean.BASE_ENV,
        PIP_CONSTRAINT=str(root / "constraints/ci.txt"),
        PYTHONHASHSEED="0",
    )
    result = subprocess.run(
        [sys.executable, "-P", "tools/collect_test_ids.py"],
        cwd=root,
        env=env,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    clean.reject_secret_material(result.stdout, "CANONICAL_COLLECTED_TEST_IDS")


@pytest.mark.parametrize(
    "script",
    [
        "tools/build_evidence_manifest.py",
        "tools/validate_b00r_anchor.py",
        "tools/validate_b00r_tag_ruleset.py",
        "tools/validate_b_receipt.py",
        "tools/validate_governance_snapshot.py",
        "tools/verify_b01c_entry.py",
        "tools/verify_codeowners.py",
    ],
)
def test_direct_governance_tools_bootstrap_under_declared_safe_path(script):
    root = pathlib.Path(__file__).resolve().parents[2]
    env = dict(
        clean.BASE_ENV,
        PIP_CONSTRAINT=str(root / "constraints/ci.txt"),
        PYTHONHASHSEED="0",
    )
    result = subprocess.run(
        [sys.executable, "-P", script, "--help"],
        cwd=root,
        env=env,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")


def test_command_chronology_fails_on_clock_regression():
    commands = [
        {"id": "first", "started_at_us": 101, "finished_at_us": 110},
        {"id": "second", "started_at_us": 109, "finished_at_us": 120},
    ]
    with pytest.raises(capture.CleanRunnerCaptureError, match="CHRONOLOGY_INVALID:second"):
        capture.assert_command_chronology(100, commands, 130)


def test_spec_fragment_profile_is_exactly_the_verifiers_50_files():
    entries = capture.spec_entries()
    assert len(entries) == 50
    assert {entry["path"] for entry in entries} == clean._expected_clean_runner_paths()
    by_path = {entry["path"]: entry for entry in entries}
    assert all(by_path[path]["role_unique"] is True for path in clean.FIXED_FILE_ROLES)
    command_entries = [
        entry for entry in entries if "/commands/" in entry["path"]
    ]
    assert len(command_entries) == 33
    assert all(entry["role_unique"] is False for entry in command_entries)


def test_handoff_routes_clean_runner_through_truthful_producer():
    handoff = (
        pathlib.Path(__file__).resolve().parents[2]
        / "docs/governance/B00R_EXTERNAL_AUTHORITY_AND_CLEAN_RUNNER_HANDOFF.md"
    ).read_text(encoding="utf-8")
    assert '"$CONTROLLER_PYTHON" -I tools/b00r_clean_runner_capture.py' in handoff
    assert "PASS_CAPTURE_ONLY" in handoff
    assert "does not yet contain the corresponding truthful capture producer" not in handoff


def test_cli_refuses_nonisolated_controller_python():
    script = pathlib.Path(capture.__file__)
    result = subprocess.run(
        [sys.executable, str(script)], text=True, capture_output=True, check=False
    )
    assert result.returncode == 1
    assert "CONTROLLER_PYTHON_NOT_ISOLATED" in result.stderr


def _git_test(root: pathlib.Path, *args: str, env=None) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def _closed_source_repo(tmp_path: pathlib.Path) -> tuple[pathlib.Path, str]:
    repo = tmp_path / "closed-source"
    repo.mkdir()
    _git_test(repo, "init", "-b", "main")
    _git_test(repo, "config", "user.name", "capture-test")
    _git_test(repo, "config", "user.email", "capture@example.invalid")
    (repo / ".gitignore").write_text("*.pyc\n", encoding="utf-8")
    (repo / "tracked.txt").write_text("committed\n", encoding="utf-8")
    _git_test(repo, "add", ".")
    _git_test(repo, "commit", "-m", "closed source")
    return repo, _git_test(repo, "rev-parse", "HEAD")


def test_source_checkout_closure_binds_normal_index_and_worktree_bytes(tmp_path):
    repo, source = _closed_source_repo(tmp_path)
    assert capture._assert_source_checkout_closed(repo, source) == 2


def test_source_checkout_closure_rejects_assume_unchanged_mutation(tmp_path):
    repo, source = _closed_source_repo(tmp_path)
    _git_test(repo, "update-index", "--assume-unchanged", "tracked.txt")
    (repo / "tracked.txt").write_text("mutated behind stat cache\n", encoding="utf-8")
    with pytest.raises(capture.CleanRunnerCaptureError, match="INDEX_FLAGS_NONNORMAL"):
        capture._assert_source_checkout_closed(repo, source)


def test_source_checkout_closure_rejects_skip_worktree_flag(tmp_path):
    repo, source = _closed_source_repo(tmp_path)
    _git_test(repo, "update-index", "--skip-worktree", "tracked.txt")
    with pytest.raises(capture.CleanRunnerCaptureError, match="INDEX_FLAGS_NONNORMAL"):
        capture._assert_source_checkout_closed(repo, source)


def test_source_checkout_closure_rejects_stage_zero_index_oid_drift(tmp_path):
    repo, source = _closed_source_repo(tmp_path)
    other_oid = _git_test(repo, "rev-parse", f"{source}:.gitignore")
    _git_test(repo, "update-index", "--cacheinfo", "100644", other_oid, "tracked.txt")
    with pytest.raises(capture.CleanRunnerCaptureError, match="INDEX_TREE_MISMATCH"):
        capture._assert_source_checkout_closed(repo, source)


def test_source_checkout_closure_rejects_ignored_pyc_residue(tmp_path):
    repo, source = _closed_source_repo(tmp_path)
    (repo / "rogue.pyc").write_bytes(b"import-affecting residue")
    with pytest.raises(capture.CleanRunnerCaptureError, match="NAMESPACE_NOT_CLOSED"):
        capture._assert_source_checkout_closed(repo, source)


def test_source_checkout_closure_hashes_tracked_bytes_independently(tmp_path):
    repo, source = _closed_source_repo(tmp_path)
    (repo / "tracked.txt").write_text("unindexed mutation\n", encoding="utf-8")
    with pytest.raises(capture.CleanRunnerCaptureError, match="WORKTREE_BLOB_MISMATCH"):
        capture._assert_source_checkout_closed(repo, source)


def test_source_checkout_closure_rejects_tracked_worktree_symlink(tmp_path):
    repo, source = _closed_source_repo(tmp_path)
    tracked = repo / "tracked.txt"
    tracked.unlink()
    tracked.symlink_to(".gitignore")
    with pytest.raises(capture.CleanRunnerCaptureError, match="SOURCE_LEXICAL_SYMLINK"):
        capture._assert_source_checkout_closed(repo, source)


def test_lexical_source_closure_cannot_be_redirected_by_core_worktree(tmp_path):
    repo, source = _closed_source_repo(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    _git_test(repo, "config", "core.worktree", str(elsewhere))
    (repo / "rogue.py").write_bytes(b"rogue lexical module")
    tree_entries = capture._source_tree_entries(repo, source)
    with pytest.raises(capture.CleanRunnerCaptureError, match="NAMESPACE_NOT_CLOSED"):
        capture._assert_lexical_checkout_namespace(repo, tree_entries)


def test_local_git_controls_reject_grafts_and_core_worktree_tampering(tmp_path):
    source_repo, _source = _closed_source_repo(tmp_path)
    clone = tmp_path / "canonical-clone"
    subprocess.run(
        [
            "git", "clone", "--no-local", "--no-tags", "--single-branch",
            "--branch", "main", "--", str(source_repo), str(clone),
        ],
        capture_output=True,
        check=True,
    )
    _git_test(clone, "config", "remote.origin.url", capture.ORIGIN_URL)
    _raw, expected_sha256 = capture._bound_local_git_config(clone)
    grafts = clone / ".git/info/grafts"
    grafts.write_text("0" * 40 + " " + "1" * 40 + "\n", encoding="ascii")
    with pytest.raises(capture.CleanRunnerCaptureError, match="LEGACY_GRAFTS_PRESENT"):
        capture._bound_local_git_config(clone, expected_sha256)
    grafts.unlink()
    _git_test(clone, "config", "core.worktree", str(tmp_path / "redirected"))
    with pytest.raises(capture.CleanRunnerCaptureError, match="GIT_CONFIG_CHANGED"):
        capture._bound_local_git_config(clone, expected_sha256)


def test_git_hooks_are_disabled_and_control_surface_mutation_is_detected(tmp_path):
    source_repo, _source = _closed_source_repo(tmp_path)
    clone = tmp_path / "hook-clone"
    subprocess.run(
        [
            "git", "clone", "--no-local", "--no-tags", "--single-branch",
            "--branch", "main", "--", str(source_repo), str(clone),
        ],
        capture_output=True,
        check=True,
    )
    expected = capture._bound_git_control_surface(clone)
    hook = clone / ".git/hooks/reference-transaction"
    hook.write_text("#!/bin/sh\nexit 99\n", encoding="ascii")
    hook.chmod(0o755)
    # Every controller Git call receives core.hooksPath=/dev/null, so even a final ref update
    # cannot be vetoed or rewritten by this persisted repository-local hook.
    head = _git_test(clone, "rev-parse", "HEAD")
    capture._git(clone, "update-ref", "refs/heads/hook-probe", head)
    assert _git_test(clone, "rev-parse", "refs/heads/hook-probe") == head
    with pytest.raises(capture.CleanRunnerCaptureError, match="CONTROL_SURFACE_CHANGED"):
        capture._bound_git_control_surface(clone, expected)


def test_strict_git_object_check_rejects_tampered_loose_commit(tmp_path):
    repo, source = _closed_source_repo(tmp_path)
    loose = repo / ".git/objects" / source[:2] / source[2:]
    corrupted = bytearray(loose.read_bytes())
    corrupted[-1] ^= 1
    # Git may create loose objects without owner-write permission.  This disposable attack
    # fixture must make its target writable explicitly before corrupting it; the production
    # verifier still receives the same malformed object bytes.
    original_mode = stat.S_IMODE(loose.stat().st_mode)
    loose.chmod(original_mode | stat.S_IWUSR)
    try:
        loose.write_bytes(corrupted)
    finally:
        loose.chmod(original_mode)
    with pytest.raises(capture.CleanRunnerCaptureError, match="GIT_COMMAND_FAILED:fsck"):
        capture._assert_git_objects_intact(repo)


def test_source_head_and_remote_main_refs_must_both_be_direct(tmp_path):
    repo, source = _closed_source_repo(tmp_path)
    _git_test(repo, "update-ref", "refs/remotes/origin/main", source)
    with pytest.raises(capture.CleanRunnerCaptureError, match="SOURCE_REF_NOT_DIRECT:HEAD"):
        capture._assert_source_refs_direct(repo)

    _git_test(repo, "checkout", "--detach", source)
    capture._assert_source_refs_direct(repo)
    _git_test(repo, "symbolic-ref", "refs/remotes/origin/main", "refs/heads/main")
    with pytest.raises(
        capture.CleanRunnerCaptureError,
        match="SOURCE_REF_NOT_DIRECT:refs/remotes/origin/main",
    ):
        capture._assert_source_refs_direct(repo)


def test_rollback_capture_executes_real_mainline_revert_and_restores_source(tmp_path):
    repo = tmp_path / "repo"
    output = tmp_path / "output"
    repo.mkdir()
    output.mkdir()
    _git_test(repo, "init", "-b", "main")
    _git_test(repo, "config", "user.name", "capture-test")
    _git_test(repo, "config", "user.email", "capture@example.invalid")
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    _git_test(repo, "add", ".")
    _git_test(repo, "commit", "-m", "base")
    parent = _git_test(repo, "rev-parse", "HEAD")
    _git_test(repo, "checkout", "-b", "source")
    (repo / "source.txt").write_text("source\n", encoding="utf-8")
    _git_test(repo, "add", ".")
    _git_test(repo, "commit", "-m", "source")
    _git_test(repo, "checkout", "main")
    _git_test(repo, "merge", "--no-ff", "source", "-m", "merge source")
    source = _git_test(repo, "rev-parse", "HEAD")
    source_tree = _git_test(repo, "rev-parse", "HEAD^{tree}")
    proof = capture.capture_rollback(
        repo,
        output,
        "b" * 32,
        {
            "source_merge_sha": source,
            "source_merge_tree": source_tree,
            "parents": [parent, _git_test(repo, "rev-parse", "source")],
        },
    )
    assert proof["result"] == "PASS"
    assert proof["result_tree_sha"] == _git_test(repo, "rev-parse", f"{parent}^{{tree}}")
    assert (output / clean.ROLLBACK_RC_PATH).read_bytes() == b"0\n"
    assert _git_test(repo, "rev-parse", "HEAD") == source
    assert _git_test(repo, "status", "--porcelain=v1", "--untracked-files=all") == ""


def test_secret_scanner_rejects_token_or_private_key_material(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    entries = capture.spec_entries()
    for entry in entries:
        target = output / entry["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"safe\n")
    infected = output / entries[0]["path"]
    infected.write_bytes(b"tmc_1234567890abcdef1234567890abcdef\n")
    with pytest.raises(capture.CleanRunnerCaptureError, match="SECRET_MATERIAL_DETECTED"):
        capture._assert_no_secrets(output, {entry["path"] for entry in entries})


def test_purelib_closure_rejects_unowned_pyc_and_hardlinks(tmp_path):
    purelib = tmp_path / "venv/lib/python3.11/site-packages"
    owned = purelib / "package/__init__.py"
    owned.parent.mkdir(parents=True)
    owned.write_bytes(b"package\n")
    capture._assert_purelib_closed(purelib, {"package/__init__.py"})

    rogue = purelib / "package/__pycache__/__init__.cpython-311.pyc"
    rogue.parent.mkdir()
    rogue.write_bytes(b"rogue-pyc")
    with pytest.raises(capture.CleanRunnerCaptureError, match="PURELIB_NOT_RECORD_CLOSED"):
        capture._assert_purelib_closed(purelib, {"package/__init__.py"})


def test_purelib_closure_rejects_empty_namespace_package_directory(tmp_path):
    purelib = tmp_path / "venv/lib/python3.11/site-packages"
    owned = purelib / "package/__init__.py"
    owned.parent.mkdir(parents=True)
    owned.write_bytes(b"package\n")
    (purelib / "rogue_namespace").mkdir()
    with pytest.raises(capture.CleanRunnerCaptureError, match="DIRECTORY_NAMESPACE_NOT_CLOSED"):
        capture._assert_purelib_closed(purelib, {"package/__init__.py"})


def test_output_closure_rejects_evidence_sibling_outside_clean_runner(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    entries = capture.spec_entries()
    for entry in entries:
        path = output / entry["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"bound\n")
    (output / capture.SPEC_FRAGMENT_NAME).write_bytes(b"{}")
    rogue = output / "evidence/B00R_G2/outside-clean-runner.bin"
    rogue.parent.mkdir(parents=True, exist_ok=True)
    rogue.write_bytes(b"rogue")
    with pytest.raises(capture.CleanRunnerCaptureError, match="PROFILE_NOT_CLOSED"):
        capture._assert_capture_tree(output, entries)


def test_output_closure_rejects_external_hardlink_alias(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    entries = capture.spec_entries()
    for entry in entries:
        path = output / entry["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"bound\n")
    (output / capture.SPEC_FRAGMENT_NAME).write_bytes(b"{}")
    os.link(output / entries[0]["path"], tmp_path / "external-alias")
    with pytest.raises(capture.CleanRunnerCaptureError, match="OUTPUT_MULTILINKED"):
        capture._assert_capture_tree(output, entries)


def test_final_binding_rejects_later_command_mutation_of_prior_stream(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    expected = {}
    for rel in clean._expected_clean_runner_paths():
        path = output / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"original")
        expected[rel] = b"original"
    changed = next(rel for rel in expected if "/commands/00-" in rel)
    (output / changed).write_bytes(b"mutated-by-later-command")
    with pytest.raises(capture.CleanRunnerCaptureError, match="FINAL_EVIDENCE_BYTES_CHANGED"):
        capture.assert_final_bindings(output, expected)


def test_state_guard_runs_before_and_after_every_successful_command(tmp_path, monkeypatch):
    clone = tmp_path / "clone"
    output = tmp_path / "output"
    clone.mkdir()
    output.mkdir()
    calls = []

    def successful(argv, **kwargs):
        env = kwargs["env"]
        if "TRIAD_B00R_TEST_IDS_PATH" in env:
            ids = pathlib.Path(env["TRIAD_B00R_TEST_IDS_PATH"])
            result = pathlib.Path(env["TRIAD_B00R_TEST_RESULT_PATH"])
            ids.parent.mkdir(parents=True, exist_ok=True)
            ids.write_bytes(b"tests/test_example.py::test_ok\n")
            result.write_bytes(b"{}")
        return subprocess.CompletedProcess(argv, 0, b"ok\n", b"")

    monkeypatch.setattr(capture, "_process", successful)
    capture.run_required_commands(
        clone,
        output,
        pathlib.Path("/fresh/venv/bin/python"),
        "a" * 32,
        SOURCE,
        lambda: calls.append("guard"),
    )
    assert len(calls) == len(clean.REQUIRED_COMMANDS) + 1


def test_command_cannot_mutate_later_source_tool_before_next_command(tmp_path, monkeypatch):
    clone = tmp_path / "clone"
    output = tmp_path / "output"
    clone.mkdir()
    output.mkdir()
    protected = clone / "tools/later.py"
    protected.parent.mkdir()
    protected.write_bytes(b"committed")

    def mutate_source(argv, **kwargs):
        env = kwargs["env"]
        ids = pathlib.Path(env["TRIAD_B00R_TEST_IDS_PATH"])
        result = pathlib.Path(env["TRIAD_B00R_TEST_RESULT_PATH"])
        ids.parent.mkdir(parents=True, exist_ok=True)
        ids.write_bytes(b"tests/test_example.py::test_ok\n")
        result.write_bytes(b"{}")
        protected.write_bytes(b"mutated")
        return subprocess.CompletedProcess(argv, 0, b"ok\n", b"")

    def guard():
        if protected.read_bytes() != b"committed":
            raise capture.CleanRunnerCaptureError("SOURCE_CHECKOUT_DIRTY_OR_REPLACED")

    monkeypatch.setattr(capture, "_process", mutate_source)
    with pytest.raises(capture.CleanRunnerCaptureError, match="DIRTY_OR_REPLACED"):
        capture.run_required_commands(
            clone,
            output,
            pathlib.Path("/fresh/venv/bin/python"),
            "a" * 32,
            SOURCE,
            guard,
        )
