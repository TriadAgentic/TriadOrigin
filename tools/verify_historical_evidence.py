#!/usr/bin/env python3
"""Verify immutable R00/B00-B07 receipt bytes against the audited-start Git commit.

The invalidation manifest is additive disposition metadata; it is not allowed to redefine which
historical receipts exist or what their bytes were.  This verifier therefore uses a closed path
set and resolves each original blob directly from ``audited_start_sha`` in Git, then requires the
working-tree file and manifest size/digest to match that blob exactly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = "docs/governance/B00_B07_INVALIDATION_MANIFEST.v1.json"
EXPECTED_PATHS = frozenset(
    f"evidence/receipts/{name}.json"
    for name in ("R00", "B00", "B00C", "B01", "B01R", "B02", "B03", "B04", "B05", "B06", "B07")
)
HEX40_RE = re.compile(r"[0-9a-f]{40}")
HEX64_RE = re.compile(r"[0-9a-f]{64}")


class HistoricalEvidenceError(ValueError):
    """Historical evidence no longer matches its audited Git identity."""


def _git(root: pathlib.Path, *args: str) -> bytes:
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("GIT_") or name == "GIT_CONFIG_NOSYSTEM"
    }
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    proc = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=False, env=env
    )
    if proc.returncode:
        detail = proc.stderr.decode("utf-8", errors="replace").strip()
        raise HistoricalEvidenceError(f"GIT_COMMAND_FAILED: git {' '.join(args)}: {detail}")
    return proc.stdout


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _reject_symlink_chain(root: pathlib.Path, rel: str) -> None:
    cursor = root
    for part in pathlib.PurePosixPath(rel).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise HistoricalEvidenceError(f"HISTORICAL_SYMLINK: {rel}")


def verify(root: pathlib.Path, manifest_path: pathlib.Path, audited_start: str | None) -> int:
    root = root.resolve()
    manifest_lexical = manifest_path if manifest_path.is_absolute() else root / manifest_path
    try:
        manifest_rel = manifest_lexical.absolute().relative_to(root).as_posix()
    except ValueError as exc:
        raise HistoricalEvidenceError("INVALIDATION_MANIFEST_OUTSIDE_REPOSITORY") from exc
    if manifest_rel != DEFAULT_MANIFEST:
        raise HistoricalEvidenceError(
            f"INVALIDATION_MANIFEST_PATH_NONCANONICAL: {manifest_rel}"
        )
    _reject_symlink_chain(root, manifest_rel)
    manifest_path = root / manifest_rel
    if not manifest_path.is_file():
        raise HistoricalEvidenceError("INVALIDATION_MANIFEST_MISSING")
    _git(root, "ls-files", "--error-unmatch", "--", manifest_rel)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HistoricalEvidenceError(f"INVALIDATION_MANIFEST_NOT_READABLE_JSON: {exc}") from exc

    declared_start = manifest.get("audited_start_sha")
    start = audited_start or declared_start
    if HEX40_RE.fullmatch(start or "") is None:
        raise HistoricalEvidenceError(f"AUDITED_START_NOT_CANONICAL_HEX40: {start!r}")
    if declared_start != start:
        raise HistoricalEvidenceError(
            f"AUDITED_START_MISMATCH: manifest={declared_start!r} expected={start!r}"
        )
    resolved = _git(root, "rev-parse", "--verify", f"{start}^{{commit}}").decode().strip()
    if resolved != start:
        raise HistoricalEvidenceError(f"AUDITED_START_MOVED: {resolved}!={start}")

    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise HistoricalEvidenceError("INVALIDATION_ENTRIES_NOT_ARRAY")
    if manifest.get("entry_count") != len(entries):
        raise HistoricalEvidenceError(
            f"INVALIDATION_ENTRY_COUNT_MISMATCH: {manifest.get('entry_count')!r}!={len(entries)}"
        )
    by_path: dict[str, dict] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise HistoricalEvidenceError("INVALIDATION_ENTRY_NOT_OBJECT")
        path = entry.get("path")
        if not isinstance(path, str):
            raise HistoricalEvidenceError(f"INVALIDATION_PATH_NOT_STRING: {path!r}")
        if path in by_path:
            raise HistoricalEvidenceError(f"INVALIDATION_DUPLICATE_PATH: {path}")
        by_path[path] = entry
    actual_paths = set(by_path)
    if actual_paths != EXPECTED_PATHS:
        raise HistoricalEvidenceError(
            f"INVALIDATION_MEMBERSHIP_NOT_CLOSED: "
            f"missing={sorted(EXPECTED_PATHS - actual_paths)} "
            f"extra={sorted(actual_paths - EXPECTED_PATHS)}"
        )

    vocabulary = manifest.get("disposition_vocabulary")
    if not isinstance(vocabulary, list) or not vocabulary:
        raise HistoricalEvidenceError("INVALIDATION_DISPOSITION_VOCABULARY_EMPTY")

    for rel in sorted(EXPECTED_PATHS):
        entry = by_path[rel]
        path = root / rel
        _reject_symlink_chain(root, rel)
        if not path.is_file():
            raise HistoricalEvidenceError(f"HISTORICAL_FILE_MISSING_OR_SYMLINK: {rel}")
        _git(root, "ls-files", "--error-unmatch", "--", rel)
        baseline = _git(root, "show", f"{start}:{rel}")
        current = path.read_bytes()
        if current != baseline:
            raise HistoricalEvidenceError(f"HISTORICAL_BYTES_CHANGED: {rel}")
        digest = entry.get("sha256")
        if HEX64_RE.fullmatch(digest or "") is None or digest == "0" * 64:
            raise HistoricalEvidenceError(f"HISTORICAL_DIGEST_INVALID: {rel}")
        if digest != _sha256(baseline):
            raise HistoricalEvidenceError(f"HISTORICAL_DIGEST_MISMATCH: {rel}")
        if entry.get("size") != len(baseline):
            raise HistoricalEvidenceError(f"HISTORICAL_SIZE_MISMATCH: {rel}")
        if entry.get("disposition") not in vocabulary:
            raise HistoricalEvidenceError(f"HISTORICAL_DISPOSITION_INVALID: {rel}")

    return len(EXPECTED_PATHS)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--audited-start")
    args = parser.parse_args(argv)
    root = pathlib.Path(args.root)
    manifest_path = pathlib.Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = root / manifest_path
    try:
        count = verify(root, manifest_path, args.audited_start)
    except (HistoricalEvidenceError, OSError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {count} historical receipts match immutable audited-start Git blobs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
