#!/usr/bin/env python3
"""Produce the B00R generation-2 clean-runner evidence bundle.

This is deliberately separate from :mod:`tools.b00r_clean_runner`, whose job is to verify bytes
after they have been committed on the receipt branch.  The producer creates its own canonical
HTTPS clone, virtual environment, and output root, then records the verifier's exact 50-file
profile.  It never accepts an existing checkout or virtual environment and never writes evidence
inside the source clone.

The output root contains the canonical ``evidence/B00R_G2/clean_runner`` subtree plus one
``clean_runner.spec-fragment.v1.json`` file.  The latter is an input fragment for the later closed
receipt build spec; it is intentionally outside the 50-file evidence namespace.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import pathlib
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import types
from typing import Any, Callable


class CleanRunnerCaptureError(RuntimeError):
    """The requested bounded capture is unsafe or produced a non-PASS observation."""


_CAPTURE_SOURCE_PATH = pathlib.Path(__file__).absolute()
ROOT = _CAPTURE_SOURCE_PATH.parent.parent


def _read_controller_source(path: pathlib.Path, label: str) -> bytes:
    if not path.is_absolute():
        raise CleanRunnerCaptureError(f"{label}_PATH_NOT_ABSOLUTE")
    cursor = pathlib.Path(path.anchor)
    for part in path.parts[1:]:
        cursor = cursor / part
        try:
            observed = cursor.lstat()
        except OSError as exc:
            raise CleanRunnerCaptureError(f"{label}_PATH_UNREADABLE:{cursor}") from exc
        if stat.S_ISLNK(observed.st_mode):
            raise CleanRunnerCaptureError(f"{label}_PATH_SYMLINK:{cursor}")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise CleanRunnerCaptureError(f"{label}_FILE_UNSAFE")
        blocks: list[bytes] = []
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            blocks.append(block)
        after = os.fstat(descriptor)
        path_after = path.lstat()
        identity_before = (
            before.st_dev, before.st_ino, before.st_mode, before.st_nlink,
            before.st_size, before.st_mtime_ns, before.st_ctime_ns,
        )
        identity_after = (
            after.st_dev, after.st_ino, after.st_mode, after.st_nlink,
            after.st_size, after.st_mtime_ns, after.st_ctime_ns,
        )
        if (
            identity_after != identity_before
            or (path_after.st_dev, path_after.st_ino) != (after.st_dev, after.st_ino)
        ):
            raise CleanRunnerCaptureError(f"{label}_FILE_RACED")
        raw = b"".join(blocks)
        if len(raw) != before.st_size:
            raise CleanRunnerCaptureError(f"{label}_FILE_SHORT_READ")
        return raw
    finally:
        os.close(descriptor)


def _compile_source_module(
    path: pathlib.Path, module_name: str, raw: bytes | None = None
) -> tuple[types.ModuleType, bytes]:
    """Execute exact source bytes directly; never consult import bytecode caches."""
    if raw is None:
        raw = _read_controller_source(path, "CONTROLLER_MODULE")
    module = types.ModuleType(module_name)
    module.__file__ = str(path)
    module.__package__ = module_name.rpartition(".")[0]
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module, raw


_CLEAN_SOURCE_PATH = ROOT / "tools" / "b00r_clean_runner.py"
_INVENTORY_SOURCE_PATH = ROOT / "tools" / "b00r_pytest_inventory.py"
_CAPTURE_SOURCE_BYTES = _read_controller_source(
    _CAPTURE_SOURCE_PATH, "CONTROLLER_CAPTURE_SOURCE"
)
_CLEAN_SOURCE_BYTES = _read_controller_source(
    _CLEAN_SOURCE_PATH, "CONTROLLER_VERIFIER_SOURCE"
)
_INVENTORY_SOURCE_BYTES = _read_controller_source(
    _INVENTORY_SOURCE_PATH, "CONTROLLER_INVENTORY_SOURCE"
)
clean, _executed_clean_source = _compile_source_module(
    _CLEAN_SOURCE_PATH, "tools.b00r_clean_runner", _CLEAN_SOURCE_BYTES
)
if _executed_clean_source != _CLEAN_SOURCE_BYTES:  # pragma: no cover - construction invariant
    raise CleanRunnerCaptureError("CONTROLLER_VERIFIER_EXECUTED_BYTES_MISMATCH")


ORIGIN_URL = "https://github.com/TriadAgentic/TriadOrigin.git"
SPEC_FRAGMENT_NAME = "clean_runner.spec-fragment.v1.json"
_HEX40 = re.compile(r"[0-9a-f]{40}")


def _now_us() -> int:
    return time.time_ns() // 1_000


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _lexical_absolute(value: pathlib.Path | str, label: str) -> pathlib.Path:
    raw = os.fspath(value)
    candidate = pathlib.Path(raw)
    if (
        not candidate.is_absolute()
        or candidate == pathlib.Path("/")
        or ".." in candidate.parts
        or "." in candidate.parts
        or os.path.normpath(raw) != raw
    ):
        raise CleanRunnerCaptureError(f"{label}_ROOT_NOT_CANONICAL_ABSOLUTE")
    return candidate


def _path_chain(path: pathlib.Path):
    cursor = pathlib.Path(path.anchor)
    yield cursor
    for part in path.parts[1:]:
        cursor = cursor / part
        yield cursor


def _reject_symlink_chain(path: pathlib.Path, label: str) -> None:
    for candidate in _path_chain(path):
        if candidate.is_symlink():
            raise CleanRunnerCaptureError(f"{label}_ROOT_SYMLINK:{candidate}")


def _paths_overlap(left: pathlib.Path, right: pathlib.Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def prepare_roots(
    clone_root: pathlib.Path | str,
    venv_root: pathlib.Path | str,
    output_root: pathlib.Path | str,
) -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
    """Validate three absent, canonical, pairwise-disjoint capture roots without creating them."""
    labelled = {
        "CLONE": _lexical_absolute(clone_root, "CLONE"),
        "VENV": _lexical_absolute(venv_root, "VENV"),
        "OUTPUT": _lexical_absolute(output_root, "OUTPUT"),
    }
    rows = list(labelled.items())
    for index, (left_label, left) in enumerate(rows):
        for right_label, right in rows[index + 1:]:
            if _paths_overlap(left, right):
                raise CleanRunnerCaptureError(
                    f"CAPTURE_ROOTS_OVERLAP:{left_label}:{right_label}"
                )
    for label, path in rows:
        _reject_symlink_chain(path, label)
        if os.path.lexists(path):
            raise CleanRunnerCaptureError(f"{label}_ROOT_PREEXISTS:{path}")
        if not path.parent.is_dir():
            raise CleanRunnerCaptureError(f"{label}_ROOT_PARENT_MISSING:{path.parent}")
    return labelled["CLONE"], labelled["VENV"], labelled["OUTPUT"]


def _write_new(path: pathlib.Path, data: bytes) -> None:
    if os.path.lexists(path):
        raise CleanRunnerCaptureError(f"CAPTURE_OUTPUT_PREEXISTS:{path}")
    _reject_symlink_chain(path.parent, "CAPTURE_OUTPUT")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(data)


def _write_json(path: pathlib.Path, value: Any) -> bytes:
    raw = _canonical_json(value)
    _write_new(path, raw)
    return raw


def _process(
    argv: list[str],
    *,
    cwd: pathlib.Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        argv,
        cwd=None if cwd is None else str(cwd),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _require_success(
    result: subprocess.CompletedProcess[bytes], label: str
) -> subprocess.CompletedProcess[bytes]:
    if result.returncode != 0:
        raise CleanRunnerCaptureError(f"{label}_FAILED:rc={result.returncode}")
    return result


def _git_env() -> dict[str, str]:
    return {
        "GIT_CONFIG_COUNT": clean.BASE_ENV["GIT_CONFIG_COUNT"],
        "GIT_CONFIG_GLOBAL": clean.BASE_ENV["GIT_CONFIG_GLOBAL"],
        "GIT_CONFIG_KEY_0": clean.BASE_ENV["GIT_CONFIG_KEY_0"],
        "GIT_CONFIG_KEY_1": clean.BASE_ENV["GIT_CONFIG_KEY_1"],
        "GIT_CONFIG_KEY_2": clean.BASE_ENV["GIT_CONFIG_KEY_2"],
        "GIT_CONFIG_NOSYSTEM": clean.BASE_ENV["GIT_CONFIG_NOSYSTEM"],
        "GIT_CONFIG_SYSTEM": clean.BASE_ENV["GIT_CONFIG_SYSTEM"],
        "GIT_CONFIG_VALUE_0": clean.BASE_ENV["GIT_CONFIG_VALUE_0"],
        "GIT_CONFIG_VALUE_1": clean.BASE_ENV["GIT_CONFIG_VALUE_1"],
        "GIT_CONFIG_VALUE_2": clean.BASE_ENV["GIT_CONFIG_VALUE_2"],
        "GIT_NO_REPLACE_OBJECTS": clean.BASE_ENV["GIT_NO_REPLACE_OBJECTS"],
        "GIT_TERMINAL_PROMPT": clean.BASE_ENV["GIT_TERMINAL_PROMPT"],
        "LANG": clean.BASE_ENV["LANG"],
        "LC_ALL": clean.BASE_ENV["LC_ALL"],
        "TZ": clean.BASE_ENV["TZ"],
    }


def _git(
    root: pathlib.Path,
    *args: str,
    allow: frozenset[int] = frozenset({0}),
) -> subprocess.CompletedProcess[bytes]:
    result = _process(["git", "-C", str(root), *args], env=_git_env())
    if result.returncode not in allow:
        raise CleanRunnerCaptureError(
            f"GIT_COMMAND_FAILED:{' '.join(args)}:rc={result.returncode}"
        )
    return result


def _git_stdout(root: pathlib.Path, *args: str) -> bytes:
    return _git(root, *args).stdout


def _decode_line(data: bytes, label: str) -> str:
    try:
        value = data.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise CleanRunnerCaptureError(f"{label}_NOT_UTF8") from exc
    if "\n" in value or "\r" in value:
        raise CleanRunnerCaptureError(f"{label}_NOT_SINGLE_LINE")
    return value


def _source_tree_rows(root: pathlib.Path, source_merge: str) -> list[bytes]:
    raw = _git_stdout(root, "ls-tree", "-r", "-z", "--full-tree", source_merge)
    rows = [row for row in raw.split(b"\0") if row]
    if not rows:
        raise CleanRunnerCaptureError("SOURCE_TREE_EMPTY")
    return rows


def _source_tree_entries(
    root: pathlib.Path, source_merge: str
) -> dict[bytes, tuple[bytes, bytes]]:
    raw = _git_stdout(root, "ls-tree", "-r", "-z", "--full-tree", source_merge)
    try:
        return clean.safe_source_tree_entries(raw)
    except clean.CleanRunnerError as exc:
        raise CleanRunnerCaptureError(str(exc)) from exc


def _worktree_path(root: pathlib.Path, raw_rel: bytes) -> pathlib.Path:
    rel_text = os.fsdecode(raw_rel)
    if os.fsencode(rel_text) != raw_rel:
        raise CleanRunnerCaptureError("SOURCE_PATH_NOT_FILESYSTEM_ROUNDTRIPPABLE")
    rel = pathlib.PurePosixPath(rel_text)
    if (
        rel.is_absolute()
        or not rel.parts
        or any(part in {"", ".", ".."} for part in rel.parts)
    ):
        raise CleanRunnerCaptureError("SOURCE_PATH_UNSAFE")
    return root.joinpath(*rel.parts)


def _assert_lexical_checkout_namespace(
    root: pathlib.Path, tree_entries: dict[bytes, tuple[bytes, bytes]]
) -> None:
    """Close the lexical checkout independently of Git's configurable worktree view."""
    expected_files = set(tree_entries)
    expected_dirs: set[bytes] = set()
    for raw_rel in expected_files:
        parts = raw_rel.split(b"/")
        if any(not part or part in {b".", b".."} for part in parts):
            raise CleanRunnerCaptureError("SOURCE_TREE_PATH_UNSAFE")
        for width in range(1, len(parts)):
            expected_dirs.add(b"/".join(parts[:width]))

    actual_files: set[bytes] = set()
    actual_dirs: set[bytes] = set()

    def visit(directory: bytes, prefix: bytes) -> None:
        try:
            with os.scandir(directory) as entries:
                rows = list(entries)
        except OSError as exc:
            raise CleanRunnerCaptureError("SOURCE_LEXICAL_NAMESPACE_UNREADABLE") from exc
        for entry in rows:
            name = entry.name
            if not isinstance(name, bytes):  # pragma: no cover - bytes input guarantees bytes
                raise CleanRunnerCaptureError("SOURCE_LEXICAL_PATH_TYPE_INVALID")
            if not prefix and name == b".git":
                continue
            if not name or name in {b".", b".."} or b"/" in name:
                raise CleanRunnerCaptureError("SOURCE_LEXICAL_PATH_UNSAFE")
            rel = name if not prefix else prefix + b"/" + name
            try:
                observed = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise CleanRunnerCaptureError("SOURCE_LEXICAL_PATH_RACED") from exc
            if entry.is_symlink():
                raise CleanRunnerCaptureError(
                    f"SOURCE_LEXICAL_SYMLINK:{os.fsdecode(rel)}"
                )
            if stat.S_ISDIR(observed.st_mode):
                actual_dirs.add(rel)
                visit(os.path.join(directory, name), rel)
            elif stat.S_ISREG(observed.st_mode):
                actual_files.add(rel)
            else:
                raise CleanRunnerCaptureError(
                    f"SOURCE_LEXICAL_NONREGULAR:{os.fsdecode(rel)}"
                )

    visit(os.fsencode(root), b"")
    if actual_files != expected_files or actual_dirs != expected_dirs:
        raise CleanRunnerCaptureError(
            "SOURCE_LEXICAL_NAMESPACE_NOT_CLOSED:"
            f"missing_files={sorted(os.fsdecode(path) for path in expected_files-actual_files)}:"
            f"extra_files={sorted(os.fsdecode(path) for path in actual_files-expected_files)}:"
            f"missing_dirs={sorted(os.fsdecode(path) for path in expected_dirs-actual_dirs)}:"
            f"extra_dirs={sorted(os.fsdecode(path) for path in actual_dirs-expected_dirs)}"
        )


def _git_blob_oid(path: pathlib.Path, expected_size: int) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise CleanRunnerCaptureError(f"SOURCE_WORKTREE_FILE_OPEN_FAILED:{path}") from exc
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size != expected_size
        ):
            raise CleanRunnerCaptureError(f"SOURCE_WORKTREE_FILE_UNSAFE:{path}")
        digest = hashlib.sha1()
        digest.update(f"blob {before.st_size}\0".encode("ascii"))
        read_size = 0
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            read_size += len(block)
            digest.update(block)
        after = os.fstat(descriptor)
        before_identity = (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_nlink,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        after_identity = (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_nlink,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if read_size != before.st_size or after_identity != before_identity:
            raise CleanRunnerCaptureError(f"SOURCE_WORKTREE_FILE_RACED:{path}")
        return digest.hexdigest().encode("ascii")
    finally:
        os.close(descriptor)


def _assert_source_checkout_closed(root: pathlib.Path, source_merge: str) -> int:
    """Bind ref, index, and every worktree byte without trusting Git's stat cache."""
    tree_entries = _source_tree_entries(root, source_merge)

    flag_rows = [
        row for row in _git_stdout(root, "ls-files", "-v", "-z").split(b"\0") if row
    ]
    flagged_paths: set[bytes] = set()
    for row in flag_rows:
        if not row.startswith(b"H ") or not row[2:] or row[2:] in flagged_paths:
            raise CleanRunnerCaptureError("SOURCE_INDEX_FLAGS_NONNORMAL")
        flagged_paths.add(row[2:])
    if flagged_paths != set(tree_entries):
        raise CleanRunnerCaptureError("SOURCE_INDEX_FLAG_PATH_SET_MISMATCH")

    index_entries: dict[bytes, tuple[bytes, bytes]] = {}
    index_rows = [
        row
        for row in _git_stdout(root, "ls-files", "--stage", "-z").split(b"\0")
        if row
    ]
    for row in index_rows:
        try:
            metadata, rel = row.split(b"\t", 1)
            mode, object_id, stage = metadata.split()
        except ValueError as exc:
            raise CleanRunnerCaptureError("SOURCE_INDEX_ROW_MALFORMED") from exc
        if not rel or rel in index_entries or stage != b"0":
            raise CleanRunnerCaptureError("SOURCE_INDEX_NOT_UNIQUE_STAGE_ZERO")
        index_entries[rel] = (mode, object_id)
    if index_entries != tree_entries:
        raise CleanRunnerCaptureError("SOURCE_INDEX_TREE_MISMATCH")

    _assert_lexical_checkout_namespace(root, tree_entries)

    untracked = _git_stdout(root, "ls-files", "--others", "--exclude-standard", "-z")
    ignored = _git_stdout(
        root, "ls-files", "--others", "--ignored", "--exclude-standard", "-z"
    )
    if untracked or ignored:
        raise CleanRunnerCaptureError("SOURCE_UNTRACKED_OR_IGNORED_RESIDUE")

    for raw_rel, (expected_mode, expected_oid) in tree_entries.items():
        candidate = _worktree_path(root, raw_rel)
        _reject_symlink_chain(candidate, "SOURCE_WORKTREE")
        try:
            observed = candidate.lstat()
        except OSError as exc:
            raise CleanRunnerCaptureError(
                f"SOURCE_WORKTREE_FILE_MISSING:{os.fsdecode(raw_rel)}"
            ) from exc
        if not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1:
            raise CleanRunnerCaptureError(
                f"SOURCE_WORKTREE_FILE_UNSAFE:{os.fsdecode(raw_rel)}"
            )
        observed_mode = b"100755" if observed.st_mode & 0o111 else b"100644"
        if observed_mode != expected_mode:
            raise CleanRunnerCaptureError(
                f"SOURCE_WORKTREE_MODE_MISMATCH:{os.fsdecode(raw_rel)}"
            )
        if _git_blob_oid(candidate, observed.st_size) != expected_oid:
            raise CleanRunnerCaptureError(
                f"SOURCE_WORKTREE_BLOB_MISMATCH:{os.fsdecode(raw_rel)}"
            )
    return len(tree_entries)


def _bound_local_git_config(
    root: pathlib.Path, expected_sha256: str | None = None
) -> tuple[bytes, str]:
    """Read and bind the fresh clone's exact, minimal repository-local Git config."""
    _reject_symlink_chain(root, "SOURCE")
    git_dir = root / ".git"
    config = git_dir / "config"
    grafts = git_dir / "info" / "grafts"
    commondir = git_dir / "commondir"
    if (
        root.is_symlink()
        or not root.is_dir()
        or git_dir.is_symlink()
        or not git_dir.is_dir()
        or config.is_symlink()
        or not config.is_file()
        or config.stat().st_nlink != 1
    ):
        raise CleanRunnerCaptureError("SOURCE_LOCAL_GIT_CONFIG_UNSAFE")
    if os.path.lexists(grafts):
        raise CleanRunnerCaptureError("SOURCE_LEGACY_GRAFTS_PRESENT")
    if os.path.lexists(commondir):
        raise CleanRunnerCaptureError("SOURCE_GIT_COMMONDIR_REDIRECT_PRESENT")
    raw = config.read_bytes()
    digest = _sha256(raw)
    if expected_sha256 is not None and digest != expected_sha256:
        raise CleanRunnerCaptureError("SOURCE_LOCAL_GIT_CONFIG_CHANGED")
    parsed = _require_success(
        _process(
            ["git", "config", "--file", str(config), "--null", "--list"],
            env=_git_env(),
        ),
        "PARSE_SOURCE_LOCAL_GIT_CONFIG",
    ).stdout
    rows: dict[str, str] = {}
    try:
        records = [row for row in parsed.split(b"\0") if row]
        for record in records:
            key_raw, value_raw = record.split(b"\n", 1)
            key = key_raw.decode("utf-8")
            value = value_raw.decode("utf-8")
            if key in rows:
                raise CleanRunnerCaptureError("SOURCE_LOCAL_GIT_CONFIG_DUPLICATE_KEY")
            rows[key] = value
    except (UnicodeDecodeError, ValueError) as exc:
        raise CleanRunnerCaptureError("SOURCE_LOCAL_GIT_CONFIG_MALFORMED") from exc
    expected = {
        "core.repositoryformatversion": "0",
        "core.filemode": "true",
        "core.bare": "false",
        "core.logallrefupdates": "true",
        "remote.origin.url": ORIGIN_URL,
        "remote.origin.fetch": "+refs/heads/main:refs/remotes/origin/main",
        "remote.origin.tagopt": "--no-tags",
        "branch.main.remote": "origin",
        "branch.main.merge": "refs/heads/main",
    }
    if rows != expected:
        raise CleanRunnerCaptureError("SOURCE_LOCAL_GIT_CONFIG_NONCANONICAL")
    return raw, digest


def _bound_git_control_surface(
    root: pathlib.Path, expected_sha256: str | None = None
) -> str:
    """Bind hook and info namespaces that can change later Git command semantics."""
    git_dir = root / ".git"
    rows: list[dict[str, Any]] = []
    for relative_root in (pathlib.Path("hooks"), pathlib.Path("info")):
        namespace = git_dir / relative_root
        _reject_symlink_chain(namespace, "SOURCE_GIT_CONTROL")
        if namespace.is_symlink() or not namespace.is_dir():
            raise CleanRunnerCaptureError("SOURCE_GIT_CONTROL_NAMESPACE_UNSAFE")
        candidates = [namespace, *sorted(namespace.rglob("*"))]
        for candidate in candidates:
            rel = candidate.relative_to(git_dir).as_posix()
            if candidate.is_symlink():
                raise CleanRunnerCaptureError(f"SOURCE_GIT_CONTROL_SYMLINK:{rel}")
            observed = candidate.lstat()
            if stat.S_ISDIR(observed.st_mode):
                rows.append({"path": rel, "kind": "directory", "mode": observed.st_mode & 0o777})
                continue
            if not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1:
                raise CleanRunnerCaptureError(f"SOURCE_GIT_CONTROL_FILE_UNSAFE:{rel}")
            data = candidate.read_bytes()
            rows.append(
                {
                    "path": rel,
                    "kind": "file",
                    "mode": observed.st_mode & 0o777,
                    "size": len(data),
                    "sha256": _sha256(data),
                }
            )
    digest = _sha256(_canonical_json(rows))
    if expected_sha256 is not None and digest != expected_sha256:
        raise CleanRunnerCaptureError("SOURCE_GIT_CONTROL_SURFACE_CHANGED")
    return digest


def _raw_commit_identity(root: pathlib.Path, source_merge: str) -> tuple[str, list[str]]:
    raw = _git_stdout(root, "cat-file", "-p", source_merge)
    headers = raw.split(b"\n\n", 1)[0].splitlines()
    tree_rows = [row[5:] for row in headers if row.startswith(b"tree ")]
    parent_rows = [row[7:] for row in headers if row.startswith(b"parent ")]
    try:
        tree_values = [value.decode("ascii") for value in tree_rows]
        parent_values = [value.decode("ascii") for value in parent_rows]
    except UnicodeDecodeError as exc:
        raise CleanRunnerCaptureError("SOURCE_RAW_COMMIT_IDENTITY_INVALID") from exc
    if (
        len(tree_values) != 1
        or len(parent_values) != 2
        or any(_HEX40.fullmatch(value) is None for value in tree_values + parent_values)
    ):
        raise CleanRunnerCaptureError("SOURCE_NOT_RAW_TWO_PARENT_MERGE")
    return tree_values[0], parent_values


def _assert_git_objects_intact(root: pathlib.Path) -> None:
    _git(root, "fsck", "--strict", "--full", "--no-dangling")


def _assert_source_refs_direct(root: pathlib.Path) -> None:
    for ref in ("HEAD", "refs/remotes/origin/main"):
        result = _git(
            root,
            "symbolic-ref",
            "-q",
            ref,
            allow=frozenset({0, 1}),
        )
        if result.returncode != 1 or result.stdout or result.stderr:
            raise CleanRunnerCaptureError(f"SOURCE_REF_NOT_DIRECT:{ref}")


def assert_source_identity(
    root: pathlib.Path,
    source_merge: str,
    *,
    expected_git_config_sha256: str | None = None,
    expected_git_control_sha256: str | None = None,
) -> dict[str, Any]:
    """Revalidate that the detached checkout remains exact live ``origin/main`` source."""
    if _HEX40.fullmatch(source_merge) is None or source_merge == "0" * 40:
        raise CleanRunnerCaptureError("SOURCE_MERGE_INVALID")
    _config_raw, config_sha256 = _bound_local_git_config(
        root, expected_git_config_sha256
    )
    control_sha256 = _bound_git_control_surface(root, expected_git_control_sha256)
    top = pathlib.Path(
        _decode_line(_git_stdout(root, "rev-parse", "--show-toplevel"), "SOURCE_TOPLEVEL")
    )
    git_dir = pathlib.Path(
        _decode_line(
            _git_stdout(root, "rev-parse", "--absolute-git-dir"), "SOURCE_GIT_DIR"
        )
    )
    common_dir = pathlib.Path(
        _decode_line(
            _git_stdout(
                root, "rev-parse", "--path-format=absolute", "--git-common-dir"
            ),
            "SOURCE_GIT_COMMON_DIR",
        )
    )
    if top != root or git_dir != root / ".git" or common_dir != root / ".git":
        raise CleanRunnerCaptureError("SOURCE_GIT_PATHS_NONCANONICAL")
    _assert_git_objects_intact(root)
    _assert_source_refs_direct(root)
    origin_url = _decode_line(_git_stdout(root, "remote", "get-url", "origin"), "ORIGIN_URL")
    if origin_url != ORIGIN_URL:
        raise CleanRunnerCaptureError("ORIGIN_URL_NONCANONICAL")
    tag_option = _decode_line(
        _git_stdout(root, "config", "--get", "remote.origin.tagOpt"),
        "ORIGIN_TAG_OPTION",
    )
    if tag_option != "--no-tags" or _git_stdout(root, "tag", "--list"):
        raise CleanRunnerCaptureError("CLONE_TAGS_PRESENT_OR_ENABLED")
    origin_main = _decode_line(
        _git_stdout(root, "rev-parse", "refs/remotes/origin/main"), "ORIGIN_MAIN"
    )
    head = _decode_line(_git_stdout(root, "rev-parse", "HEAD"), "HEAD")
    if origin_main != source_merge or head != source_merge:
        raise CleanRunnerCaptureError("SOURCE_NOT_LIVE_ORIGIN_MAIN")
    if _decode_line(_git_stdout(root, "rev-parse", "--abbrev-ref", "HEAD"), "HEAD_MODE") != "HEAD":
        raise CleanRunnerCaptureError("SOURCE_CHECKOUT_NOT_DETACHED")
    tree = _decode_line(
        _git_stdout(root, "rev-parse", f"{source_merge}^{{tree}}"), "SOURCE_TREE"
    )
    if _HEX40.fullmatch(tree) is None:
        raise CleanRunnerCaptureError("SOURCE_TREE_INVALID")
    raw_tree, parents = _raw_commit_identity(root, source_merge)
    if raw_tree != tree:
        raise CleanRunnerCaptureError("SOURCE_RAW_COMMIT_TREE_MISMATCH")
    status = _git_stdout(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    replace = _git_stdout(root, "replace", "-l")
    if status or replace:
        raise CleanRunnerCaptureError("SOURCE_CHECKOUT_DIRTY_OR_REPLACED")
    _assert_source_checkout_closed(root, source_merge)
    shallow = _decode_line(
        _git_stdout(root, "rev-parse", "--is-shallow-repository"), "SOURCE_SHALLOW"
    )
    if shallow != "false":
        raise CleanRunnerCaptureError("SOURCE_SHALLOW_REPOSITORY")
    alternates = root / ".git" / "objects" / "info" / "alternates"
    if os.path.lexists(alternates):
        raise CleanRunnerCaptureError("SOURCE_ALTERNATES_PRESENT")
    submodules = 0
    for row in _source_tree_rows(root, source_merge):
        try:
            metadata, _path = row.split(b"\t", 1)
            _mode, kind, _object_id = metadata.split()
        except ValueError as exc:
            raise CleanRunnerCaptureError("SOURCE_TREE_ROW_MALFORMED") from exc
        if kind == b"commit":
            submodules += 1
    if submodules:
        raise CleanRunnerCaptureError("SOURCE_SUBMODULES_PRESENT")
    source_time = int(
        _decode_line(
            _git_stdout(root, "show", "-s", "--format=%ct", source_merge),
            "SOURCE_TIME",
        )
    ) * 1_000_000
    return {
        "source_merge_sha": source_merge,
        "source_merge_tree": tree,
        "source_merge_time_us": source_time,
        "parents": parents,
        "status": status,
        "replace": replace,
        "submodule_count": submodules,
        "git_config_sha256": config_sha256,
        "git_control_sha256": control_sha256,
    }


def clone_source(clone_root: pathlib.Path, source_merge: str) -> dict[str, Any]:
    result = _process(
        [
            "git", "clone", "--no-local", "--no-tags", "--single-branch",
            "--branch", "main", "--", ORIGIN_URL, str(clone_root),
        ],
        env=_git_env(),
    )
    _require_success(result, "CANONICAL_HTTPS_CLONE")
    _require_success(
        _git(clone_root, "checkout", "--detach", source_merge), "DETACH_SOURCE_MERGE"
    )
    return assert_source_identity(clone_root, source_merge)


def refresh_live_main(
    clone_root: pathlib.Path,
    source_merge: str,
    expected_git_config_sha256: str,
    expected_git_control_sha256: str,
) -> dict[str, Any]:
    _require_success(
        _git(
            clone_root,
            "fetch", "--no-tags", "origin",
            "+refs/heads/main:refs/remotes/origin/main",
        ),
        "REFRESH_ORIGIN_MAIN",
    )
    return assert_source_identity(
        clone_root,
        source_merge,
        expected_git_config_sha256=expected_git_config_sha256,
        expected_git_control_sha256=expected_git_control_sha256,
    )


def _executing_source_paths() -> dict[str, pathlib.Path]:
    return {
        "tools/b00r_clean_runner_capture.py": _CAPTURE_SOURCE_PATH,
        "tools/b00r_clean_runner.py": _CLEAN_SOURCE_PATH,
        "tools/b00r_pytest_inventory.py": _INVENTORY_SOURCE_PATH,
    }


def _retained_executing_source_bytes() -> dict[str, bytes]:
    return {
        "tools/b00r_clean_runner_capture.py": _CAPTURE_SOURCE_BYTES,
        "tools/b00r_clean_runner.py": _CLEAN_SOURCE_BYTES,
        "tools/b00r_pytest_inventory.py": _INVENTORY_SOURCE_BYTES,
    }


def assert_executing_source_bytes(clone_root: pathlib.Path, source_merge: str) -> None:
    """Bind every capture-profile implementation byte to the claimed source merge."""
    paths = _executing_source_paths()
    retained = _retained_executing_source_bytes()
    if set(paths) != set(retained):
        raise CleanRunnerCaptureError("EXECUTING_SOURCE_BINDING_SET_MISMATCH")
    for rel, lexical in paths.items():
        expected_lexical = ROOT.joinpath(*pathlib.PurePosixPath(rel).parts)
        if lexical.absolute() != expected_lexical.absolute():
            raise CleanRunnerCaptureError(f"EXECUTING_SOURCE_PATH_NONCANONICAL:{rel}")
        _reject_symlink_chain(lexical, "EXECUTING_SOURCE")
        if lexical.is_symlink() or not lexical.is_file():
            raise CleanRunnerCaptureError(f"EXECUTING_SOURCE_NOT_REGULAR:{rel}")
        if lexical.read_bytes() != retained[rel]:
            raise CleanRunnerCaptureError(f"EXECUTING_SOURCE_CHANGED_AFTER_LOAD:{rel}")
        committed = _git_stdout(clone_root, "show", f"{source_merge}:{rel}")
        if retained[rel] != committed:
            raise CleanRunnerCaptureError(f"EXECUTING_SOURCE_BYTES_MISMATCH:{rel}")


def _python_probe(python: pathlib.Path) -> dict[str, Any]:
    code = (
        "import json,os,platform,sys,sysconfig;"
        "base_vars={'base':sys.base_prefix,'platbase':sys.base_exec_prefix};"
        "base_site=sysconfig.get_path('purelib',vars=base_vars);"
        "print(json.dumps({'implementation':platform.python_implementation(),"
        "'version':platform.python_version(),'executable':sys.executable,"
        "'prefix':sys.prefix,'base_prefix':sys.base_prefix,"
        "'purelib':sysconfig.get_path('purelib'),'platlib':sysconfig.get_path('platlib'),"
        "'base_site_packages':base_site,'sys_path':[os.path.realpath(p) for p in sys.path],"
        "'system_site_packages':os.path.realpath(base_site) in "
        "[os.path.realpath(p) for p in sys.path]},"
        "sort_keys=True,separators=(',',':')))"
    )
    env = dict(clean.BASE_ENV, PYTHONHASHSEED="0")
    result = _require_success(
        _process([str(python), "-I", "-c", code], env=env), "PYTHON_IDENTITY_PROBE"
    )
    try:
        value = json.loads(result.stdout)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CleanRunnerCaptureError("PYTHON_IDENTITY_PROBE_NOT_JSON") from exc
    if not isinstance(value, dict):
        raise CleanRunnerCaptureError("PYTHON_IDENTITY_PROBE_NOT_OBJECT")
    return value


def create_venv(bootstrap_python: pathlib.Path, venv_root: pathlib.Path) -> dict[str, Any]:
    bootstrap_python = _lexical_absolute(bootstrap_python, "BOOTSTRAP_PYTHON")
    _reject_symlink_chain(bootstrap_python, "BOOTSTRAP_PYTHON")
    if not bootstrap_python.is_file() or bootstrap_python.is_symlink():
        raise CleanRunnerCaptureError("BOOTSTRAP_PYTHON_NOT_REGULAR_FILE")
    bootstrap = _python_probe(bootstrap_python)
    if (
        bootstrap.get("implementation") != "CPython"
        or not isinstance(bootstrap.get("version"), str)
        or re.fullmatch(r"3\.11\.[0-9]+", bootstrap["version"]) is None
        or bootstrap.get("executable") != str(bootstrap_python)
        or bootstrap.get("prefix") != bootstrap.get("base_prefix")
    ):
        raise CleanRunnerCaptureError("BOOTSTRAP_PYTHON_NOT_SYSTEM_CPYTHON_3_11")
    _require_success(
        _process(
            [str(bootstrap_python), "-I", "-m", "venv", "--copies", str(venv_root)],
            env=dict(clean.BASE_ENV, PYTHONHASHSEED="0"),
        ),
        "CREATE_FRESH_VENV",
    )
    python = venv_root / "bin" / "python"
    _reject_symlink_chain(python, "FRESH_VENV_PYTHON")
    if python.is_symlink() or not python.is_file() or python.stat().st_nlink != 1:
        raise CleanRunnerCaptureError("FRESH_VENV_PYTHON_NOT_REGULAR_COPY")
    probe = _python_probe(python)
    if (
        probe.get("implementation") != "CPython"
        or not isinstance(probe.get("version"), str)
        or re.fullmatch(r"3\.11\.[0-9]+", probe["version"]) is None
        or probe.get("prefix") != str(venv_root)
        or probe.get("base_prefix") == probe.get("prefix")
        or probe.get("system_site_packages") is not False
        or probe.get("executable") != str(python)
    ):
        raise CleanRunnerCaptureError("FRESH_VENV_IDENTITY_MISMATCH")
    venv_config = venv_root / "pyvenv.cfg"
    if (
        venv_config.is_symlink()
        or not venv_config.is_file()
        or venv_config.lstat().st_nlink != 1
    ):
        raise CleanRunnerCaptureError("FRESH_VENV_CONFIG_UNSAFE")
    try:
        config_lines = {
            key.strip().lower(): value.strip().lower()
            for line in venv_config.read_text(encoding="utf-8").splitlines()
            if "=" in line
            for key, value in [line.split("=", 1)]
        }
    except (OSError, UnicodeError) as exc:
        raise CleanRunnerCaptureError("FRESH_VENV_CONFIG_UNREADABLE") from exc
    if config_lines.get("include-system-site-packages") != "false":
        raise CleanRunnerCaptureError("FRESH_VENV_SYSTEM_SITE_PACKAGES_ENABLED")
    base_site = probe.get("base_site_packages")
    sys_path = probe.get("sys_path")
    if (
        not isinstance(base_site, str)
        or not isinstance(sys_path, list)
        or not all(isinstance(path, str) for path in sys_path)
        or os.path.realpath(base_site) in {os.path.realpath(path) for path in sys_path}
    ):
        raise CleanRunnerCaptureError("FRESH_VENV_SYSTEM_SITE_PATH_PRESENT")
    library_paths = {
        "purelib": pathlib.Path(probe.get("purelib", "")),
        "platlib": pathlib.Path(probe.get("platlib", "")),
    }
    for label, library in library_paths.items():
        try:
            library.relative_to(venv_root)
        except ValueError as exc:
            raise CleanRunnerCaptureError(
                f"FRESH_VENV_{label.upper()}_NONCANONICAL"
            ) from exc
        _reject_symlink_chain(library, f"FRESH_VENV_{label.upper()}")
        if (
            not library.is_absolute()
            or library.name != "site-packages"
            or not library.is_dir()
        ):
            raise CleanRunnerCaptureError(f"FRESH_VENV_{label.upper()}_NONCANONICAL")
    purelib = library_paths["purelib"]
    if library_paths["platlib"] != purelib:
        raise CleanRunnerCaptureError("FRESH_VENV_PURELIB_PLATLIB_DIVERGE")
    probe["python_path"] = python
    probe["purelib_path"] = purelib
    probe["platlib_path"] = library_paths["platlib"]
    return probe


def _install_env(clone_root: pathlib.Path) -> dict[str, str]:
    return dict(
        clean.BASE_ENV,
        PIP_CONSTRAINT=str(clone_root / "constraints" / "ci.txt"),
        PYTHONHASHSEED="0",
    )


def _extract_git_archive(archive: pathlib.Path, destination: pathlib.Path) -> None:
    destination.mkdir()
    with tarfile.open(archive, mode="r:") as bundle:
        for member in bundle.getmembers():
            rel = pathlib.PurePosixPath(member.name)
            if (
                not member.name
                or rel.is_absolute()
                or any(part in ("", ".", "..") for part in rel.parts)
                or not (member.isdir() or member.isfile())
            ):
                raise CleanRunnerCaptureError(f"SOURCE_ARCHIVE_MEMBER_UNSAFE:{member.name}")
            target = destination.joinpath(*rel.parts)
            _reject_symlink_chain(target.parent, "SOURCE_ARCHIVE")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=False)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = bundle.extractfile(member)
            if source is None:
                raise CleanRunnerCaptureError(f"SOURCE_ARCHIVE_FILE_UNREADABLE:{member.name}")
            with source, target.open("xb") as handle:
                shutil.copyfileobj(source, handle)
            target.chmod(member.mode & 0o777)


def install_locked_wheel(
    clone_root: pathlib.Path,
    venv_root: pathlib.Path,
    python: pathlib.Path,
    source_merge: str,
) -> None:
    """Install every exact CI requirement, then install a non-editable exact-source wheel."""
    env = _install_env(clone_root)
    constraints = clone_root / "constraints" / "ci.txt"
    _require_success(
        _process(
            [
                str(python), "-m", "pip", "install", "--disable-pip-version-check",
                "--no-cache-dir", "--no-compile", "--no-deps", "--requirement",
                str(constraints),
            ],
            cwd=venv_root,
            env=env,
        ),
        "INSTALL_EXACT_CONSTRAINTS",
    )
    with tempfile.TemporaryDirectory(prefix="b00r-wheel-", dir=str(venv_root)) as temp_name:
        temporary = pathlib.Path(temp_name)
        archive = temporary / "source.tar"
        archive_result = _git(
            clone_root,
            "archive", "--format=tar", f"--output={archive}", source_merge,
        )
        _require_success(archive_result, "ARCHIVE_EXACT_SOURCE")
        build_source = temporary / "source"
        wheelhouse = temporary / "wheelhouse"
        _extract_git_archive(archive, build_source)
        wheelhouse.mkdir()
        _require_success(
            _process(
                [
                    str(python), "-m", "pip", "wheel", "--disable-pip-version-check",
                    "--no-cache-dir", "--no-index", "--no-deps", "--no-build-isolation",
                    "--wheel-dir", str(wheelhouse), str(build_source),
                ],
                cwd=build_source,
                env=env,
            ),
            "BUILD_EXACT_SOURCE_WHEEL",
        )
        wheels = sorted(wheelhouse.glob("triad_origin-*.whl"))
        if len(wheels) != 1 or wheels[0].is_symlink() or not wheels[0].is_file():
            raise CleanRunnerCaptureError("EXACT_SOURCE_WHEEL_COUNT_MISMATCH")
        _require_success(
            _process(
                [
                    str(python), "-m", "pip", "install", "--disable-pip-version-check",
                    "--no-cache-dir", "--no-compile", "--no-index", "--no-deps",
                    str(wheels[0]),
                ],
                cwd=venv_root,
                env=env,
            ),
            "INSTALL_NONEDITABLE_PROJECT_WHEEL",
        )


def _safe_installed_file(
    purelib: pathlib.Path, venv_root: pathlib.Path, candidate: pathlib.Path
) -> str | None:
    resolved_root = purelib.resolve(strict=True)
    _reject_symlink_chain(candidate, "INSTALLED_FILE")
    if candidate.is_symlink():
        raise CleanRunnerCaptureError(f"INSTALLED_FILE_UNSAFE:{candidate}")
    try:
        resolved_unchecked = candidate.resolve(strict=False)
    except RuntimeError as exc:
        raise CleanRunnerCaptureError(f"INSTALLED_FILE_RESOLUTION_FAILED:{candidate}") from exc
    try:
        resolved_unchecked.relative_to(resolved_root)
    except ValueError:
        # Distribution console scripts are RECORD members but live in exact ``venv/bin`` rather
        # than the Python import surface. Permit only a direct regular launcher in that directory.
        try:
            bin_rel = resolved_unchecked.relative_to((venv_root / "bin").resolve(strict=True))
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise CleanRunnerCaptureError(
                f"INSTALLED_RECORD_PATH_OUTSIDE_VENV:{candidate}"
            ) from exc
        if (
            len(bin_rel.parts) != 1
            or not resolved_unchecked.is_file()
            or resolved_unchecked.is_symlink()
            or resolved_unchecked.stat().st_nlink != 1
        ):
            raise CleanRunnerCaptureError(f"INSTALLED_CONSOLE_SCRIPT_UNSAFE:{candidate}")
        return None
    try:
        resolved = candidate.resolve(strict=True)
        rel = resolved.relative_to(resolved_root).as_posix()
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise CleanRunnerCaptureError(
            f"INSTALLED_FILE_MISSING_OR_ESCAPED:{candidate}"
        ) from exc
    if (
        not candidate.is_file()
        or candidate.stat().st_nlink != 1
        or not clean._safe_relpath(rel)
    ):
        raise CleanRunnerCaptureError(f"INSTALLED_FILE_UNSAFE:{candidate}")
    return rel


def _assert_purelib_closed(purelib: pathlib.Path, owned_paths: set[str]) -> None:
    _reject_symlink_chain(purelib, "PURELIB")
    if purelib.is_symlink() or not purelib.is_dir():
        raise CleanRunnerCaptureError("PURELIB_ROOT_UNSAFE")
    actual: set[str] = set()
    actual_dirs: set[str] = set()
    for candidate in purelib.rglob("*"):
        rel = candidate.relative_to(purelib).as_posix()
        if candidate.is_symlink():
            raise CleanRunnerCaptureError(f"PURELIB_SYMLINK_FORBIDDEN:{rel}")
        if candidate.is_dir():
            actual_dirs.add(rel)
            continue
        if not candidate.is_file():
            raise CleanRunnerCaptureError(f"PURELIB_NONREGULAR_FILE:{rel}")
        actual.add(rel)
    if actual != owned_paths:
        raise CleanRunnerCaptureError(
            f"PURELIB_NOT_RECORD_CLOSED:unowned={sorted(actual-owned_paths)}:"
            f"missing={sorted(owned_paths-actual)}"
        )
    expected_dirs: set[str] = set()
    for rel in owned_paths:
        parent = pathlib.PurePosixPath(rel).parent
        while parent != pathlib.PurePosixPath("."):
            expected_dirs.add(parent.as_posix())
            parent = parent.parent
    if actual_dirs != expected_dirs:
        raise CleanRunnerCaptureError(
            f"PURELIB_DIRECTORY_NAMESPACE_NOT_CLOSED:unowned={sorted(actual_dirs-expected_dirs)}:"
            f"missing={sorted(expected_dirs-actual_dirs)}"
        )


def build_package_snapshot(
    clone_root: pathlib.Path,
    venv_root: pathlib.Path,
    purelib: pathlib.Path,
    run_id: str,
    source_merge: str,
) -> dict[str, Any]:
    constraints_raw = (clone_root / "constraints" / "ci.txt").read_bytes()
    constraints = clean._parse_constraints(constraints_raw)
    distributions: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    all_paths: set[str] = set()
    for dist in importlib.metadata.distributions(path=[str(purelib)]):
        raw_name = dist.metadata.get("Name")
        if not isinstance(raw_name, str) or not raw_name:
            raise CleanRunnerCaptureError("INSTALLED_DISTRIBUTION_NAME_MISSING")
        name = clean._normalise_name(raw_name)
        if name in seen_names:
            raise CleanRunnerCaptureError(f"INSTALLED_DISTRIBUTION_DUPLICATE:{name}")
        seen_names.add(name)
        version = dist.version
        if not isinstance(version, str) or clean._VERSION.fullmatch(version) is None:
            raise CleanRunnerCaptureError(f"INSTALLED_DISTRIBUTION_VERSION_INVALID:{name}")
        rows: list[dict[str, Any]] = []
        for package_path in dist.files or ():
            candidate = pathlib.Path(dist.locate_file(package_path))
            rel = _safe_installed_file(purelib, venv_root, candidate)
            if rel is None:
                # Console scripts live outside site-packages and are deliberately outside this
                # content snapshot. Missing/broken records inside site-packages fail below when
                # the constrained distribution has no verifiable file.
                continue
            if rel in all_paths:
                raise CleanRunnerCaptureError(f"INSTALLED_FILE_OWNERSHIP_DUPLICATE:{rel}")
            all_paths.add(rel)
            data = candidate.read_bytes()
            rows.append({"path": rel, "size": len(data), "sha256": _sha256(data)})
        rows.sort(key=lambda row: row["path"])
        if not rows:
            raise CleanRunnerCaptureError(f"INSTALLED_DISTRIBUTION_FILES_EMPTY:{name}")
        distributions.append({"name": name, "version": version, "files": rows})
    distributions.sort(key=lambda row: row["name"])
    by_name = {row["name"]: row for row in distributions}
    allowed = set(constraints) | {"pip", "triad-origin"}
    unexpected = sorted(set(by_name) - allowed)
    if unexpected:
        raise CleanRunnerCaptureError(f"INSTALLED_UNCONTROLLED_PACKAGES:{unexpected}")
    for name, version in constraints.items():
        if by_name.get(name, {}).get("version") != version:
            raise CleanRunnerCaptureError(f"INSTALLED_CONSTRAINT_MISMATCH:{name}")
    if "pip" not in by_name or "triad-origin" not in by_name:
        raise CleanRunnerCaptureError("INSTALLED_REQUIRED_DISTRIBUTION_MISSING")

    triad = by_name["triad-origin"]
    installed_runtime = {
        row["path"]: (row["size"], row["sha256"])
        for row in triad["files"]
        if row["path"].startswith("triad_origin/")
    }
    source_runtime = clean._source_runtime_files(clone_root, source_merge)
    if installed_runtime != source_runtime:
        raise CleanRunnerCaptureError("INSTALLED_PROJECT_RUNTIME_SOURCE_MISMATCH")
    _assert_purelib_closed(purelib, all_paths)
    return {
        "schema": "triad.b00r.installed_packages.v1",
        "run_id": run_id,
        "source_merge_sha": source_merge,
        "constraints_path": "constraints/ci.txt",
        "constraints_sha256": _sha256(constraints_raw),
        "distributions": distributions,
    }


def assert_runtime_state_unchanged(
    *,
    clone_root: pathlib.Path,
    venv_root: pathlib.Path,
    python: pathlib.Path,
    purelib: pathlib.Path,
    run_id: str,
    source_merge: str,
    expected_probe: dict[str, Any],
    expected_python_sha256: str,
    expected_venv_config_sha256: str,
    expected_packages: bytes,
) -> None:
    _reject_symlink_chain(python, "FRESH_VENV_PYTHON")
    if python.is_symlink() or not python.is_file() or python.stat().st_nlink != 1:
        raise CleanRunnerCaptureError("RUNTIME_PYTHON_NOT_REGULAR_COPY")
    if _sha256(python.read_bytes()) != expected_python_sha256:
        raise CleanRunnerCaptureError("RUNTIME_PYTHON_BYTES_CHANGED")
    if _python_probe(python) != expected_probe:
        raise CleanRunnerCaptureError("RUNTIME_PYTHON_PROBE_CHANGED")
    config = venv_root / "pyvenv.cfg"
    if (
        config.is_symlink()
        or not config.is_file()
        or config.lstat().st_nlink != 1
        or _sha256(config.read_bytes()) != expected_venv_config_sha256
    ):
        raise CleanRunnerCaptureError("RUNTIME_VENV_CONFIG_CHANGED")
    observed_packages = _canonical_json(
        build_package_snapshot(clone_root, venv_root, purelib, run_id, source_merge)
    )
    if observed_packages != expected_packages:
        raise CleanRunnerCaptureError("RUNTIME_PACKAGE_SNAPSHOT_CHANGED")


def _output_path(output_root: pathlib.Path, rel: str) -> pathlib.Path:
    if not clean._safe_relpath(rel):
        raise CleanRunnerCaptureError(f"CAPTURE_RELATIVE_PATH_UNSAFE:{rel}")
    target = output_root.joinpath(*pathlib.PurePosixPath(rel).parts)
    try:
        target.relative_to(output_root)
    except ValueError as exc:  # pragma: no cover - guarded by _safe_relpath
        raise CleanRunnerCaptureError(f"CAPTURE_RELATIVE_PATH_ESCAPES:{rel}") from exc
    return target


def _command_env(
    clone_root: pathlib.Path,
    output_root: pathlib.Path,
    run_id: str,
    source_merge: str,
    command_id: str,
    seed: str,
) -> dict[str, str]:
    env = dict(
        clean.BASE_ENV,
        PIP_CONSTRAINT=str(clone_root / "constraints" / "ci.txt"),
        PYTHONHASHSEED=seed,
    )
    if command_id.startswith("pytest-seed"):
        env.update(
            {
                "TRIAD_B00R_RUN_ID": run_id,
                "TRIAD_B00R_SOURCE_MERGE": source_merge,
                "TRIAD_B00R_TEST_IDS_PATH": str(
                    _output_path(output_root, clean.TEST_IDS_PATHS[seed])
                ),
                "TRIAD_B00R_TEST_IDS_REL": clean.TEST_IDS_PATHS[seed],
                "TRIAD_B00R_TEST_RESULT_PATH": str(
                    _output_path(output_root, clean.PYTEST_RESULT_PATHS[seed])
                ),
                "TRIAD_B00R_TEST_RESULT_REL": clean.PYTEST_RESULT_PATHS[seed],
            }
        )
    return env


def run_required_commands(
    clone_root: pathlib.Path,
    output_root: pathlib.Path,
    python: pathlib.Path,
    run_id: str,
    source_merge: str,
    state_guard: Callable[[], None],
) -> tuple[list[dict[str, Any]], dict[str, bytes], dict[str, bytes]]:
    records: list[dict[str, Any]] = []
    stdout_by_id: dict[str, bytes] = {}
    expected_bytes: dict[str, bytes] = {}
    state_guard()
    for ordinal, (command_id, argv_profile, seed) in enumerate(clean.REQUIRED_COMMANDS):
        argv = [str(python) if item == "$PYTHON" else item for item in argv_profile]
        env = _command_env(
            clone_root, output_root, run_id, source_merge, command_id, seed
        )
        started_at_us = _now_us()
        result = _process(argv, cwd=clone_root, env=env)
        finished_at_us = _now_us()
        base = f"{clean.EVIDENCE_ROOT}/commands/{ordinal:02d}-{command_id}"
        stdout_path = f"{base}/stdout.bin"
        stderr_path = f"{base}/stderr.bin"
        rc_path = f"{base}/rc.txt"
        rc_raw = f"{result.returncode}\n".encode("ascii")
        _write_new(_output_path(output_root, stdout_path), result.stdout)
        _write_new(_output_path(output_root, stderr_path), result.stderr)
        _write_new(_output_path(output_root, rc_path), rc_raw)
        expected_bytes.update(
            {stdout_path: result.stdout, stderr_path: result.stderr, rc_path: rc_raw}
        )
        record = {
            "ordinal": ordinal,
            "id": command_id,
            "argv": argv,
            "env": env,
            "cwd": str(clone_root),
            "started_at_us": started_at_us,
            "finished_at_us": finished_at_us,
            "stdout_path": stdout_path,
            "stdout_sha256": _sha256(result.stdout),
            "stdout_size": len(result.stdout),
            "stderr_path": stderr_path,
            "stderr_sha256": _sha256(result.stderr),
            "stderr_size": len(result.stderr),
            "rc_path": rc_path,
            "rc_sha256": _sha256(rc_raw),
            "rc_size": len(rc_raw),
            "exit_code": result.returncode,
        }
        records.append(record)
        stdout_by_id[command_id] = result.stdout
        if result.returncode != 0:
            raise CleanRunnerCaptureError(
                f"REQUIRED_COMMAND_NONZERO:{ordinal}:{command_id}:rc={result.returncode}:"
                f"stdout={stdout_path}:stderr={stderr_path}"
            )
        if command_id.startswith("pytest-seed"):
            for rel in (clean.TEST_IDS_PATHS[seed], clean.PYTEST_RESULT_PATHS[seed]):
                path = _output_path(output_root, rel)
                if path.is_symlink() or not path.is_file():
                    raise CleanRunnerCaptureError(f"PYTEST_PLUGIN_OUTPUT_MISSING:{seed}:{rel}")
                expected_bytes[rel] = path.read_bytes()
        state_guard()
    return records, stdout_by_id, expected_bytes


def assert_command_chronology(
    started_at_us: int, commands: list[dict[str, Any]], finished_at_us: int
) -> None:
    previous = started_at_us
    if not commands or finished_at_us < started_at_us:
        raise CleanRunnerCaptureError("CAPTURE_COMMAND_CHRONOLOGY_INVALID")
    for record in commands:
        started = record.get("started_at_us")
        finished = record.get("finished_at_us")
        if (
            not isinstance(started, int)
            or isinstance(started, bool)
            or not isinstance(finished, int)
            or isinstance(finished, bool)
            or started < previous
            or finished < started
        ):
            raise CleanRunnerCaptureError(
                f"CAPTURE_COMMAND_CHRONOLOGY_INVALID:{record.get('id')}"
            )
        previous = finished
    if previous > finished_at_us:
        raise CleanRunnerCaptureError("CAPTURE_FINISHED_BEFORE_LAST_COMMAND")


def build_test_manifest(
    output_root: pathlib.Path,
    run_id: str,
    source_merge: str,
    collector_stdout: bytes,
) -> dict[str, Any]:
    collector_ids = clean._parse_test_ids(collector_stdout, "CAPTURE_COLLECTOR_TEST_IDS")
    seed_rows: list[dict[str, Any]] = []
    inventories: list[list[str]] = []
    for seed in ("0", "1"):
        ids_path = _output_path(output_root, clean.TEST_IDS_PATHS[seed])
        result_path = _output_path(output_root, clean.PYTEST_RESULT_PATHS[seed])
        if ids_path.is_symlink() or result_path.is_symlink():
            raise CleanRunnerCaptureError(f"PYTEST_PLUGIN_OUTPUT_SYMLINK:{seed}")
        try:
            ids_raw = ids_path.read_bytes()
            result_raw = result_path.read_bytes()
        except OSError as exc:
            raise CleanRunnerCaptureError(f"PYTEST_PLUGIN_OUTPUT_MISSING:{seed}") from exc
        ids = clean._parse_test_ids(ids_raw, f"CAPTURE_TEST_IDS_SEED{seed}")
        try:
            result = json.loads(result_raw)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise CleanRunnerCaptureError(f"PYTEST_RESULT_NOT_JSON:{seed}") from exc
        expected_result = {
            "schema": "triad.b00r.pytest_inventory.v1",
            "run_id": run_id,
            "source_merge_sha": source_merge,
            "seed": int(seed),
            "exit_code": 0,
            "collected": len(ids),
            "passed": len(ids),
            "skipped": 0,
            "xfailed": 0,
            "failed": 0,
            "errors": 0,
            "test_ids_path": clean.TEST_IDS_PATHS[seed],
            "test_ids_sha256": _sha256(ids_raw),
        }
        if result_raw != _canonical_json(result) or result != expected_result:
            raise CleanRunnerCaptureError(f"PYTEST_RESULT_SEMANTICS_MISMATCH:{seed}")
        inventories.append(ids)
        seed_rows.append(
            {
                "seed": seed,
                "result_path": clean.PYTEST_RESULT_PATHS[seed],
                "result_sha256": _sha256(result_raw),
                "test_ids_path": clean.TEST_IDS_PATHS[seed],
                "test_ids_sha256": _sha256(ids_raw),
            }
        )
    if inventories[0] != inventories[1] or inventories[0] != collector_ids:
        raise CleanRunnerCaptureError("PYTEST_INVENTORIES_DIFFER")
    return {
        "schema": "triad.b00r.clean_runner_tests.v1",
        "run_id": run_id,
        "source_merge_sha": source_merge,
        "collector_stdout_path": (
            f"{clean.EVIDENCE_ROOT}/commands/02-collect-test-ids/stdout.bin"
        ),
        "collector_stdout_sha256": _sha256(collector_stdout),
        "seed_runs": seed_rows,
        "test_count": len(collector_ids),
        "identical": True,
    }


def capture_rollback(
    clone_root: pathlib.Path,
    output_root: pathlib.Path,
    run_id: str,
    source: dict[str, Any],
) -> dict[str, Any]:
    source_merge = source["source_merge_sha"]
    source_tree = source["source_merge_tree"]
    parent = source["parents"][0]
    parent_tree = _decode_line(
        _git_stdout(clone_root, "rev-parse", f"{parent}^{{tree}}"), "MAINLINE_PARENT_TREE"
    )
    command = ["git", "revert", "--no-commit", "-m", "1", source_merge]
    result = _process(command, cwd=clone_root, env=_git_env())
    stdout_path = clean.ROLLBACK_STDOUT_PATH
    stderr_path = clean.ROLLBACK_STDERR_PATH
    rc_path = clean.ROLLBACK_RC_PATH
    rc_raw = f"{result.returncode}\n".encode("ascii")
    _write_new(_output_path(output_root, stdout_path), result.stdout)
    _write_new(_output_path(output_root, stderr_path), result.stderr)
    _write_new(_output_path(output_root, rc_path), rc_raw)
    result_tree = ""
    if result.returncode == 0:
        result_tree = _decode_line(_git_stdout(clone_root, "write-tree"), "ROLLBACK_TREE")
    # Restore only the producer-created fresh clone. This is necessary so the final identity check
    # observes the source merge rather than the deliberately reverted worktree.
    reset = _git(clone_root, "reset", "--hard", source_merge)
    if reset.returncode != 0:
        raise CleanRunnerCaptureError(f"ROLLBACK_RESTORE_FAILED:rc={reset.returncode}")
    if result.returncode != 0:
        raise CleanRunnerCaptureError(f"ROLLBACK_COMMAND_NONZERO:rc={result.returncode}")
    if result_tree != parent_tree:
        raise CleanRunnerCaptureError("ROLLBACK_RESULT_TREE_MISMATCH")
    return {
        "schema": "triad.b00r.clean_runner_rollback_proof.v1",
        "run_id": run_id,
        "source_merge_sha": source_merge,
        "source_merge_tree": source_tree,
        "mainline_parent_sha": parent,
        "mainline_parent_tree": parent_tree,
        "command": command,
        "stdout_path": stdout_path,
        "stdout_sha256": _sha256(result.stdout),
        "stdout_size": len(result.stdout),
        "stderr_path": stderr_path,
        "stderr_sha256": _sha256(result.stderr),
        "stderr_size": len(result.stderr),
        "rc_path": rc_path,
        "rc_sha256": _sha256(rc_raw),
        "rc_size": len(rc_raw),
        "exit_code": 0,
        "result_tree_sha": result_tree,
        "result": "PASS",
    }


def spec_entries() -> list[dict[str, Any]]:
    entries = [
        {"path": path, "role": role, "role_unique": True}
        for path, role in clean.FIXED_FILE_ROLES.items()
    ]
    stream_roles = {
        "stdout.bin": "CLEAN_RUNNER_COMMAND_STDOUT",
        "stderr.bin": "CLEAN_RUNNER_COMMAND_STDERR",
        "rc.txt": "CLEAN_RUNNER_COMMAND_RC",
    }
    for ordinal, (command_id, _argv, _seed) in enumerate(clean.REQUIRED_COMMANDS):
        base = f"{clean.EVIDENCE_ROOT}/commands/{ordinal:02d}-{command_id}"
        entries.extend(
            {
                "path": f"{base}/{filename}",
                "role": role,
                "role_unique": False,
            }
            for filename, role in stream_roles.items()
        )
    entries.sort(key=lambda entry: entry["path"])
    expected = clean._expected_clean_runner_paths()
    if len(entries) != 50 or {entry["path"] for entry in entries} != expected:
        raise CleanRunnerCaptureError("INTERNAL_SPEC_PROFILE_MISMATCH")
    return entries


def _expected_output_dirs(expected_files: set[str]) -> set[str]:
    directories: set[str] = set()
    for rel in expected_files:
        parent = pathlib.PurePosixPath(rel).parent
        while parent != pathlib.PurePosixPath("."):
            directories.add(parent.as_posix())
            parent = parent.parent
    return directories


def _assert_capture_tree(output_root: pathlib.Path, entries: list[dict[str, Any]]) -> None:
    _reject_symlink_chain(output_root, "CAPTURE_OUTPUT")
    if output_root.is_symlink() or not output_root.is_dir():
        raise CleanRunnerCaptureError("CAPTURE_OUTPUT_ROOT_UNSAFE")
    expected_files = {entry["path"] for entry in entries} | {SPEC_FRAGMENT_NAME}
    expected_dirs = _expected_output_dirs(expected_files)
    actual_files: set[str] = set()
    actual_dirs: set[str] = set()
    for candidate in output_root.rglob("*"):
        rel = candidate.relative_to(output_root).as_posix()
        if candidate.is_symlink():
            raise CleanRunnerCaptureError(f"CAPTURE_OUTPUT_SYMLINK:{rel}")
        if candidate.is_dir():
            actual_dirs.add(rel)
            continue
        if not candidate.is_file():
            raise CleanRunnerCaptureError(f"CAPTURE_OUTPUT_NOT_REGULAR:{rel}")
        if candidate.lstat().st_nlink != 1:
            raise CleanRunnerCaptureError(f"CAPTURE_OUTPUT_MULTILINKED:{rel}")
        actual_files.add(rel)
        data = candidate.read_bytes()
        if not data and rel not in clean.ALLOWED_EMPTY_PATHS:
            raise CleanRunnerCaptureError(f"CAPTURE_UNLAWFUL_EMPTY_FILE:{rel}")
    if actual_files != expected_files or actual_dirs != expected_dirs:
        raise CleanRunnerCaptureError(
            f"CAPTURE_PROFILE_NOT_CLOSED:missing_files={sorted(expected_files-actual_files)}:"
            f"extra_files={sorted(actual_files-expected_files)}:"
            f"missing_dirs={sorted(expected_dirs-actual_dirs)}:"
            f"extra_dirs={sorted(actual_dirs-expected_dirs)}"
        )


def _assert_no_secrets(output_root: pathlib.Path, relative_paths: set[str]) -> None:
    for rel in sorted(relative_paths):
        data = _output_path(output_root, rel).read_bytes()
        try:
            clean.reject_secret_material(data, rel)
        except clean.CleanRunnerError as exc:
            raise CleanRunnerCaptureError(str(exc)) from exc


def assert_final_bindings(
    output_root: pathlib.Path, expected_bytes: dict[str, bytes]
) -> None:
    expected_paths = clean._expected_clean_runner_paths()
    if set(expected_bytes) != expected_paths:
        raise CleanRunnerCaptureError(
            f"FINAL_BINDING_SET_MISMATCH:missing={sorted(expected_paths-set(expected_bytes))}:"
            f"extra={sorted(set(expected_bytes)-expected_paths)}"
        )
    for rel, expected in expected_bytes.items():
        path = _output_path(output_root, rel)
        if (
            path.is_symlink()
            or not path.is_file()
            or path.lstat().st_nlink != 1
            or path.read_bytes() != expected
        ):
            raise CleanRunnerCaptureError(f"FINAL_EVIDENCE_BYTES_CHANGED:{rel}")


def capture(
    *,
    source_merge: str,
    clone_root: pathlib.Path | str,
    venv_root: pathlib.Path | str,
    output_root: pathlib.Path | str,
    bootstrap_python: pathlib.Path | str,
) -> dict[str, Any]:
    clone_root, venv_root, output_root = prepare_roots(
        clone_root, venv_root, output_root
    )
    bootstrap_python = _lexical_absolute(bootstrap_python, "BOOTSTRAP_PYTHON")
    source = clone_source(clone_root, source_merge)
    git_config_sha256 = source["git_config_sha256"]
    git_control_sha256 = source["git_control_sha256"]
    assert_executing_source_bytes(clone_root, source_merge)
    venv = create_venv(bootstrap_python, venv_root)
    python: pathlib.Path = venv["python_path"]
    install_locked_wheel(clone_root, venv_root, python, source_merge)
    created_probe = {
        key: value for key, value in venv.items()
        if key not in {"python_path", "purelib_path", "platlib_path"}
    }
    pre_command_probe = _python_probe(python)
    if pre_command_probe != created_probe:
        raise CleanRunnerCaptureError("PACKAGE_INSTALL_CHANGED_PYTHON_IMPORT_SURFACE")
    python_sha256 = _sha256(python.read_bytes())
    venv_config_sha256 = _sha256((venv_root / "pyvenv.cfg").read_bytes())
    run_id = secrets.token_hex(16)
    packages = build_package_snapshot(
        clone_root, venv_root, venv["purelib_path"], run_id, source_merge
    )
    packages_raw = _canonical_json(packages)

    def state_guard() -> None:
        assert_source_identity(
            clone_root,
            source_merge,
            expected_git_config_sha256=git_config_sha256,
            expected_git_control_sha256=git_control_sha256,
        )
        assert_runtime_state_unchanged(
            clone_root=clone_root,
            venv_root=venv_root,
            python=python,
            purelib=venv["purelib_path"],
            run_id=run_id,
            source_merge=source_merge,
            expected_probe=pre_command_probe,
            expected_python_sha256=python_sha256,
            expected_venv_config_sha256=venv_config_sha256,
            expected_packages=packages_raw,
        )

    state_guard()
    # Package installation uses an archive of exact Git bytes and must not change the evidence
    # checkout. Revalidate before producing any PASS record.
    source = assert_source_identity(
        clone_root,
        source_merge,
        expected_git_config_sha256=git_config_sha256,
        expected_git_control_sha256=git_control_sha256,
    )

    output_root.mkdir()
    expected_bytes: dict[str, bytes] = {}
    source_tree_raw = _git_stdout(
        clone_root, "ls-tree", "-r", "-z", "--full-tree", source_merge
    )
    workflow = _git_stdout(
        clone_root, "show", f"{source_merge}:.github/workflows/ci.yml"
    )
    contract_manifest = _git_stdout(
        clone_root, "show", f"{source_merge}:contracts/MANIFEST.sha256"
    )
    _write_new(_output_path(output_root, clean.SOURCE_TREE_PATH), source_tree_raw)
    _write_new(_output_path(output_root, clean.SOURCE_WORKFLOW_PATH), workflow)
    _write_new(
        _output_path(output_root, clean.CONTRACT_MANIFEST_PATH), contract_manifest
    )
    expected_bytes.update(
        {
            clean.SOURCE_TREE_PATH: source_tree_raw,
            clean.SOURCE_WORKFLOW_PATH: workflow,
            clean.CONTRACT_MANIFEST_PATH: contract_manifest,
        }
    )
    source_identity = {
        "schema": "triad.b00r.clean_runner_source_identity.v1",
        "repository": clean.REPOSITORY,
        "source_merge_sha": source_merge,
        "source_merge_tree": source["source_merge_tree"],
        "source_merge_time_us": source["source_merge_time_us"],
        "parents": source["parents"],
        "ls_tree_path": clean.SOURCE_TREE_PATH,
        "ls_tree_sha256": _sha256(source_tree_raw),
        "workflow_path": clean.SOURCE_WORKFLOW_PATH,
        "workflow_sha256": _sha256(workflow),
        "contract_manifest_path": clean.CONTRACT_MANIFEST_PATH,
        "contract_manifest_sha256": _sha256(contract_manifest),
    }
    source_identity_raw = _write_json(
        _output_path(output_root, clean.SOURCE_IDENTITY_PATH), source_identity
    )
    expected_bytes[clean.SOURCE_IDENTITY_PATH] = source_identity_raw
    _write_new(_output_path(output_root, clean.PACKAGE_SNAPSHOT_PATH), packages_raw)
    expected_bytes[clean.PACKAGE_SNAPSHOT_PATH] = packages_raw
    facts = {
        "schema": "triad.b00r.clean_runner_facts.v1",
        "run_id": run_id,
        "repository": clean.REPOSITORY,
        "origin_url": ORIGIN_URL,
        "origin_main_sha": source_merge,
        "checkout_mode": "detached",
        "head_sha": source_merge,
        "tree_sha": source["source_merge_tree"],
        "clone_no_local": True,
        "clone_no_tags": True,
        "clone_target_preexisted": False,
        "git_status_porcelain_z_sha256": _sha256(source["status"]),
        "git_replace_list_sha256": _sha256(source["replace"]),
        "alternates_present": False,
        "is_shallow_repository": False,
        "submodule_count": source["submodule_count"],
        "checkout_root": str(clone_root),
        "evidence_output_root": str(output_root),
        "constraints_path": "constraints/ci.txt",
        "constraints_sha256": _sha256(
            (clone_root / "constraints" / "ci.txt").read_bytes()
        ),
        "python_implementation": pre_command_probe["implementation"],
        "python_version": pre_command_probe["version"],
        "python_executable": str(python),
        "python_executable_sha256": python_sha256,
        "venv": {
            "prefix": pre_command_probe["prefix"],
            "base_prefix": pre_command_probe["base_prefix"],
            "system_site_packages": pre_command_probe["system_site_packages"],
        },
    }
    facts_raw = _write_json(
        _output_path(output_root, clean.RUNNER_FACTS_PATH), facts
    )
    expected_bytes[clean.RUNNER_FACTS_PATH] = facts_raw
    tests_directory = _output_path(
        output_root, pathlib.PurePosixPath(clean.TEST_IDS_PATHS["0"]).parent.as_posix()
    )
    tests_directory.mkdir(parents=True)
    _reject_symlink_chain(tests_directory, "CAPTURE_TESTS_DIRECTORY")

    started_at_us = _now_us()
    if source["source_merge_time_us"] >= started_at_us:
        raise CleanRunnerCaptureError("SOURCE_MERGE_TIME_NOT_BEFORE_CAPTURE")
    commands, command_stdout, command_bytes = run_required_commands(
        clone_root, output_root, python, run_id, source_merge, state_guard
    )
    expected_bytes.update(command_bytes)
    test_manifest = build_test_manifest(
        output_root, run_id, source_merge, command_stdout["collect-test-ids"]
    )
    test_manifest_raw = _write_json(
        _output_path(output_root, clean.TEST_MANIFEST_PATH), test_manifest
    )
    expected_bytes[clean.TEST_MANIFEST_PATH] = test_manifest_raw
    try:
        sdist_sha, wheel_sha = clean._validate_output_semantics(command_stdout)
    except clean.CleanRunnerError as exc:
        raise CleanRunnerCaptureError(f"COMMAND_OUTPUT_SEMANTICS_INVALID:{exc}") from exc
    config = {
        "schema": "triad.b00r.clean_runner_config_bundle.v1",
        "run_id": run_id,
        "source_merge_sha": source_merge,
        "activation_result": "DENIED_SAFE_HOLD",
        "levers": clean.SAFE_HOLD_LEVERS,
        "source_files": [
            {
                "path": path,
                "sha256": _sha256(_git_stdout(clone_root, "show", f"{source_merge}:{path}")),
            }
            for path in clean.CONFIG_SOURCE_PATHS
        ],
        "reproducible_sdist_sha256": sdist_sha,
        "reproducible_wheel_sha256": wheel_sha,
    }
    config_raw = _write_json(
        _output_path(output_root, clean.CONFIG_BUNDLE_PATH), config
    )
    expected_bytes[clean.CONFIG_BUNDLE_PATH] = config_raw

    # Every required command must leave tracked/untracked source state clean. Re-fetching main here
    # makes a concurrent main movement a hard identity drift rather than stale evidence.
    source = refresh_live_main(
        clone_root, source_merge, git_config_sha256, git_control_sha256
    )
    rollback = capture_rollback(clone_root, output_root, run_id, source)
    for rel in (
        clean.ROLLBACK_STDOUT_PATH, clean.ROLLBACK_STDERR_PATH, clean.ROLLBACK_RC_PATH
    ):
        expected_bytes[rel] = _output_path(output_root, rel).read_bytes()
    rollback_raw = _write_json(
        _output_path(output_root, clean.ROLLBACK_PROOF_PATH), rollback
    )
    expected_bytes[clean.ROLLBACK_PROOF_PATH] = rollback_raw
    state_guard()
    source = refresh_live_main(
        clone_root, source_merge, git_config_sha256, git_control_sha256
    )
    finished_at_us = _now_us()
    assert_command_chronology(started_at_us, commands, finished_at_us)

    run = {
        "schema": "triad.b00r.clean_runner_run.v1",
        "profile": clean.PROFILE,
        "repository": clean.REPOSITORY,
        "run_id": run_id,
        "source_merge_sha": source_merge,
        "source_merge_tree": source["source_merge_tree"],
        "source_merge_time_us": source["source_merge_time_us"],
        "started_at_us": started_at_us,
        "finished_at_us": finished_at_us,
        "runner_facts_path": clean.RUNNER_FACTS_PATH,
        "runner_facts_sha256": _sha256(facts_raw),
        "package_snapshot_path": clean.PACKAGE_SNAPSHOT_PATH,
        "package_snapshot_sha256": _sha256(packages_raw),
        "source_identity_path": clean.SOURCE_IDENTITY_PATH,
        "source_identity_sha256": _sha256(source_identity_raw),
        "test_manifest_path": clean.TEST_MANIFEST_PATH,
        "test_manifest_sha256": _sha256(test_manifest_raw),
        "config_bundle_path": clean.CONFIG_BUNDLE_PATH,
        "config_bundle_sha256": _sha256(config_raw),
        "rollback_proof_path": clean.ROLLBACK_PROOF_PATH,
        "rollback_proof_sha256": _sha256(rollback_raw),
        "commands": commands,
        "result": "PASS",
    }
    run_raw = _write_json(_output_path(output_root, clean.RUN_PATH), run)
    expected_bytes[clean.RUN_PATH] = run_raw
    entries = spec_entries()
    assert_final_bindings(output_root, expected_bytes)
    fragment = {
        "schema": "triad.b00r.clean_runner_spec_fragment.v1",
        "profile": clean.PROFILE,
        "source_merge_sha": source_merge,
        "entry_count": len(entries),
        "entries": entries,
    }
    fragment_path = output_root / SPEC_FRAGMENT_NAME
    fragment_raw = _write_json(fragment_path, fragment)
    _assert_capture_tree(output_root, entries)
    _assert_no_secrets(
        output_root, clean._expected_clean_runner_paths() | {SPEC_FRAGMENT_NAME}
    )
    root_members = sorted(path.name for path in output_root.iterdir())
    if root_members != [SPEC_FRAGMENT_NAME, "evidence"]:
        raise CleanRunnerCaptureError(f"CAPTURE_OUTPUT_ROOT_NOT_CLOSED:{root_members}")
    assert_final_bindings(output_root, expected_bytes)
    if (
        fragment_path.is_symlink()
        or not fragment_path.is_file()
        or fragment_path.lstat().st_nlink != 1
        or fragment_path.read_bytes() != fragment_raw
    ):
        raise CleanRunnerCaptureError("FINAL_SPEC_FRAGMENT_BYTES_CHANGED")
    return {
        "source_merge_sha": source_merge,
        "source_merge_tree": source["source_merge_tree"],
        "run_id": run_id,
        "run_sha256": _sha256(run_raw),
        "finished_at_us": finished_at_us,
        "output_root": str(output_root),
        "evidence_root": str(_output_path(output_root, clean.EVIDENCE_ROOT)),
        "spec_fragment": str(fragment_path),
        "spec_fragment_sha256": _sha256(fragment_raw),
        "entry_count": len(entries),
        "result": "PASS_CAPTURE_ONLY",
    }


def main(argv: list[str]) -> int:
    if not sys.flags.isolated:
        print(
            "FAIL: B00R_CLEAN_RUNNER_CAPTURE:CONTROLLER_PYTHON_NOT_ISOLATED",
            file=sys.stderr,
        )
        return 1
    parser = argparse.ArgumentParser(
        description="Produce a bounded B00R G2 clean-runner capture."
    )
    parser.add_argument("--source-merge", required=True)
    parser.add_argument("--clone-root", required=True)
    parser.add_argument("--venv-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--python", required=True, dest="bootstrap_python")
    args = parser.parse_args(argv)
    if pathlib.Path(sys.executable) != pathlib.Path(args.bootstrap_python):
        print(
            "FAIL: B00R_CLEAN_RUNNER_CAPTURE:CONTROLLER_BOOTSTRAP_PYTHON_MISMATCH",
            file=sys.stderr,
        )
        return 1
    try:
        result = capture(
            source_merge=args.source_merge,
            clone_root=args.clone_root,
            venv_root=args.venv_root,
            output_root=args.output_root,
            bootstrap_python=args.bootstrap_python,
        )
    except (CleanRunnerCaptureError, OSError, ValueError) as exc:
        print(f"FAIL: B00R_CLEAN_RUNNER_CAPTURE:{exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
