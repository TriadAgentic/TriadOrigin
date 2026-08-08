#!/usr/bin/env python3
"""Verify the contract bundle byte-integrity (Doc 03 §03.12). Exit 0 iff every artifact matches.

Fails on: an unmanifested bundle file, a manifest entry whose bytes changed, or a stale canonical
manifest hash. This is the CI gate that makes "same version string => byte-identical bytes" true.
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from gen_manifest import (  # noqa: E402
    MANIFEST_JSON,
    MANIFEST_SHA,
    ROOT,
    build_manifest,
    build_manifest_sha_text,
    bundle_files,
)


def main() -> int:
    if not MANIFEST_JSON.exists():
        print("FAIL: manifest missing; run tools/gen_manifest.py", file=sys.stderr)
        return 1
    on_disk = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
    recomputed = build_manifest()
    on_payload = on_disk.get("payload", {})
    expected_payload = recomputed["payload"]

    disk_paths = {a["path"] for a in on_payload.get("artifacts", [])}
    actual_paths = {str(p.relative_to(ROOT)) for p in bundle_files()}
    problems = []

    for extra in sorted(actual_paths - disk_paths):
        problems.append(f"unmanifested bundle file: {extra}")
    for missing in sorted(disk_paths - actual_paths):
        problems.append(f"manifest references missing file: {missing}")

    disk_by_path = {a["path"]: a["sha256"] for a in on_payload.get("artifacts", [])}
    new_by_path = {a["path"]: a["sha256"] for a in expected_payload["artifacts"]}
    for path in sorted(disk_paths & actual_paths):
        if disk_by_path[path] != new_by_path.get(path):
            problems.append(f"byte change without manifest update: {path}")

    if on_payload.get("canonical_manifest_hash") != expected_payload["canonical_manifest_hash"]:
        problems.append("canonical_manifest_hash is stale")
    if on_disk != recomputed:
        problems.append("contract manifest envelope or deterministic metadata drift")
    if not MANIFEST_SHA.exists():
        problems.append("contracts/MANIFEST.sha256 is missing")
    elif MANIFEST_SHA.read_text(encoding="utf-8") != build_manifest_sha_text(recomputed):
        problems.append("contracts/MANIFEST.sha256 bytes are stale or tampered")

    if problems:
        for p in problems:
            print(f"FAIL: {p}", file=sys.stderr)
        return 1
    print(f"OK: {len(expected_payload['artifacts'])} artifacts match manifest "
          f"({expected_payload['canonical_manifest_hash'][:16]}...)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
