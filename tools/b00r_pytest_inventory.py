"""Observation-only pytest plugin for B00R clean-runner seeded test inventories.

Execute directly with ``python -P tools/b00r_pytest_inventory.py``. The script registers its exact
source module as a pytest plugin, then writes the collected node-ID inventory plus outcome counts.
It never changes collection, ordering, selection, or test outcomes.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import secrets
import sys

import pytest


_HEX40 = re.compile(r"[0-9a-f]{40}")
_RUN_ID = re.compile(r"[0-9a-f]{32,64}")
_node_ids: list[str] = []
_outcomes = {"passed": 0, "skipped": 0, "xfailed": 0, "failed": 0, "errors": 0}
_context: dict[str, object] = {}


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise pytest.UsageError(f"{name} is required by the B00R inventory plugin")
    return value


def _reject_symlink_chain(path: pathlib.Path) -> None:
    cursor = pathlib.Path(path.anchor)
    for part in path.parts[1:]:
        cursor = cursor / part
        if cursor.is_symlink():
            raise pytest.UsageError(f"B00R inventory path contains symlink: {path}")


def _canonical_absolute(value: str, label: str) -> pathlib.Path:
    path = pathlib.Path(value)
    if (
        not path.is_absolute()
        or ".." in path.parts
        or "." in path.parts
        or os.path.normpath(value) != value
    ):
        raise pytest.UsageError(f"{label} must be canonical absolute")
    _reject_symlink_chain(path)
    return path


def _output_root(path: pathlib.Path, rel: str) -> pathlib.Path:
    rel_parts = pathlib.PurePosixPath(rel).parts
    if not rel_parts or tuple(path.parts[-len(rel_parts):]) != rel_parts:
        raise pytest.UsageError("B00R inventory absolute/relative output mismatch")
    root = path
    for _part in rel_parts:
        root = root.parent
    _reject_symlink_chain(root)
    if not root.is_dir():
        raise pytest.UsageError("B00R inventory output root does not exist")
    return root


def _directory_identity(path: pathlib.Path) -> tuple[int, int]:
    status = path.stat(follow_symlinks=False)
    return status.st_dev, status.st_ino


def _verify_directory_binding(
    directory_fd: int, directory_path: pathlib.Path, identity: tuple[int, int]
) -> None:
    descriptor_status = os.fstat(directory_fd)
    try:
        path_identity = _directory_identity(directory_path)
    except OSError as exc:
        raise pytest.UsageError("B00R inventory output directory moved") from exc
    if (
        (descriptor_status.st_dev, descriptor_status.st_ino) != identity
        or path_identity != identity
    ):
        raise pytest.UsageError("B00R inventory output directory identity changed")


def _atomic_write_at(
    directory_fd: int,
    directory_path: pathlib.Path,
    identity: tuple[int, int],
    filename: str,
    data: bytes,
) -> None:
    if pathlib.PurePath(filename).name != filename or filename in ("", ".", ".."):
        raise pytest.UsageError("B00R inventory output filename is unsafe")
    _verify_directory_binding(directory_fd, directory_path, identity)
    try:
        os.stat(filename, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        pass
    else:
        raise pytest.UsageError(f"B00R inventory output already exists: {filename}")
    temporary = f".{filename}.tmp-{secrets.token_hex(16)}"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = None
    try:
        descriptor = os.open(temporary, flags, 0o600, dir_fd=directory_fd)
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:  # pragma: no cover - defensive OS contract check
                raise OSError("short write")
            view = view[written:]
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        # Hard-linking is an atomic no-replace publication: an existing regular file or even a
        # broken symlink makes this fail rather than being followed or overwritten.
        os.link(
            temporary,
            filename,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
            follow_symlinks=False,
        )
        os.fsync(directory_fd)
        _verify_directory_binding(directory_fd, directory_path, identity)
    except OSError as exc:
        raise pytest.UsageError(f"B00R inventory atomic write failed: {filename}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            os.unlink(temporary, dir_fd=directory_fd)
        except FileNotFoundError:
            pass


def _atomic_write(path: pathlib.Path, data: bytes) -> None:
    """Testable one-shot wrapper; the live plugin freezes one directory fd at configure time."""
    if not path.parent.is_dir():
        raise pytest.UsageError("B00R inventory output parent does not exist")
    _reject_symlink_chain(path.parent)
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    directory_fd = os.open(path.parent, flags)
    try:
        identity = _directory_identity(path.parent)
        _atomic_write_at(directory_fd, path.parent, identity, path.name, data)
    finally:
        os.close(directory_fd)


def pytest_configure(config) -> None:
    global _node_ids, _outcomes, _context
    del config
    _node_ids = []
    _outcomes = {"passed": 0, "skipped": 0, "xfailed": 0, "failed": 0, "errors": 0}
    prior_fd = _context.get("directory_fd")
    if isinstance(prior_fd, int) and prior_fd >= 0:
        try:
            os.close(prior_fd)
        except OSError:
            # A prior failed test harness may already have closed its frozen descriptor. The live
            # plugin configures once per fresh process; either way, discard all prior context.
            pass
    _context = {}
    run_id = _required("TRIAD_B00R_RUN_ID")
    source_merge = _required("TRIAD_B00R_SOURCE_MERGE")
    seed = os.environ.get("PYTHONHASHSEED")
    if _RUN_ID.fullmatch(run_id) is None or _HEX40.fullmatch(source_merge) is None:
        raise pytest.UsageError("B00R inventory run/source identity is malformed")
    if seed not in {"0", "1"}:
        raise pytest.UsageError("B00R inventory requires PYTHONHASHSEED=0 or 1")
    ids_rel = _required("TRIAD_B00R_TEST_IDS_REL")
    result_rel = _required("TRIAD_B00R_TEST_RESULT_REL")
    expected_ids_rel = (
        f"evidence/B00R_G2/clean_runner/tests/test_ids.seed{seed}.txt"
    )
    expected_result_rel = (
        f"evidence/B00R_G2/clean_runner/tests/pytest.seed{seed}.v1.json"
    )
    if ids_rel != expected_ids_rel or result_rel != expected_result_rel:
        raise pytest.UsageError("B00R inventory relative output path is noncanonical")
    ids_path = _canonical_absolute(_required("TRIAD_B00R_TEST_IDS_PATH"), "TEST_IDS_PATH")
    result_path = _canonical_absolute(
        _required("TRIAD_B00R_TEST_RESULT_PATH"), "TEST_RESULT_PATH"
    )
    ids_root = _output_root(ids_path, ids_rel)
    result_root = _output_root(result_path, result_rel)
    if ids_root != result_root:
        raise pytest.UsageError("B00R inventory outputs do not share one output root")
    if ids_path.parent != result_path.parent or not ids_path.parent.is_dir():
        raise pytest.UsageError("B00R inventory tests directory was not precreated")
    if os.path.lexists(ids_path) or os.path.lexists(result_path):
        raise pytest.UsageError("B00R inventory output already exists")
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        directory_flags |= os.O_NOFOLLOW
    try:
        directory_fd = os.open(ids_path.parent, directory_flags)
    except OSError as exc:
        raise pytest.UsageError("B00R inventory tests directory cannot be bound") from exc
    identity = _directory_identity(ids_path.parent)
    descriptor_status = os.fstat(directory_fd)
    if (descriptor_status.st_dev, descriptor_status.st_ino) != identity:
        os.close(directory_fd)
        raise pytest.UsageError("B00R inventory tests directory identity changed")
    _context = {
        "run_id": run_id,
        "source_merge": source_merge,
        "seed": seed,
        "ids_path": ids_path,
        "result_path": result_path,
        "ids_rel": ids_rel,
        "result_rel": result_rel,
        "output_root": ids_root,
        "directory_path": ids_path.parent,
        "directory_fd": directory_fd,
        "directory_identity": identity,
    }


def pytest_collection_finish(session) -> None:
    global _node_ids
    _node_ids = [item.nodeid for item in session.items]


def pytest_runtest_logreport(report) -> None:
    if report.when == "call":
        if hasattr(report, "wasxfail"):
            # Both XFAIL and non-strict XPASS are non-clean outcomes for this ceremony.
            _outcomes["xfailed"] += 1
        elif report.skipped:
            _outcomes["skipped"] += 1
        elif report.failed:
            _outcomes["failed"] += 1
        elif report.passed:
            _outcomes["passed"] += 1
    elif report.failed:
        _outcomes["errors"] += 1


def pytest_sessionfinish(session, exitstatus) -> None:
    del session
    if not _context:
        raise pytest.UsageError("B00R inventory context was not configured")
    if not _node_ids or len(_node_ids) != len(set(_node_ids)):
        raise pytest.UsageError("B00R pytest inventory is empty or contains duplicate node IDs")
    ids_raw = ("\n".join(_node_ids) + "\n").encode("utf-8")
    ids_path = _context["ids_path"]
    result_path = _context["result_path"]
    directory_path = _context["directory_path"]
    directory_fd = _context["directory_fd"]
    identity = _context["directory_identity"]
    assert (
        isinstance(ids_path, pathlib.Path)
        and isinstance(result_path, pathlib.Path)
        and isinstance(directory_path, pathlib.Path)
        and isinstance(directory_fd, int)
        and isinstance(identity, tuple)
    )
    try:
        _atomic_write_at(directory_fd, directory_path, identity, ids_path.name, ids_raw)
        result = {
            "schema": "triad.b00r.pytest_inventory.v1",
            "run_id": _context["run_id"],
            "source_merge_sha": _context["source_merge"],
            "seed": int(str(_context["seed"])),
            "exit_code": int(exitstatus),
            "collected": len(_node_ids),
            **_outcomes,
            "test_ids_path": _context["ids_rel"],
            "test_ids_sha256": hashlib.sha256(ids_raw).hexdigest(),
        }
        raw = json.dumps(
            result, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        _atomic_write_at(directory_fd, directory_path, identity, result_path.name, raw)
    finally:
        os.close(directory_fd)
        _context["directory_fd"] = -1


def main() -> int:
    """Run pytest with this exact script module registered as the observation plugin."""
    return int(
        pytest.main(["-p", "no:cacheprovider"], plugins=[sys.modules[__name__]])
    )


if __name__ == "__main__":
    raise SystemExit(main())
