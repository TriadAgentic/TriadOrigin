#!/usr/bin/env python3
"""Verify the contract bundle byte-integrity (Doc 03 §03.12). Exit 0 iff every artifact matches.

Fails on: an unmanifested bundle file, a manifest entry whose bytes changed, a stale canonical
manifest hash, a frozen historical descriptor whose bytes moved, or an RC1 artifact whose bytes
changed without a declared version bump. This is the CI gate that makes
"same version string => byte-identical bytes" true.

B01 additive law (CTRL-B01-001): the RC1/R00 descriptors are immutable history; the living
descriptor is ``contract_bundle.manifest.b01.v2.json``. RC1 artifact paths must remain a subset of
the current bundle with unchanged bytes — except paths listed in ``SUPERSEDED_RC1_PATHS``, each of
which must declare a schema_version different from its frozen RC1 version (the lawful
version-bump escape, recorded per path).
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from gen_manifest import (  # noqa: E402
    LEGACY_MANIFEST_JSON,
    MANIFEST_JSON,
    MANIFEST_SHA,
    R00_MANIFEST_JSON,
    ROOT,
    build_manifest,
    build_manifest_sha_text,
    bundle_files,
)

LEGACY_MANIFEST_SHA256 = "a4184b29288e58cd9ac65738c2ecc02b1ee1f21481c3698542b9de0ae1bf8ab6"
R00_MANIFEST_SHA256 = "600de537734e93eb5f4d2c06184649311b555b02a146c1d0c114f7b6a8379e86"

# RC1 paths lawfully changed by a recorded version bump (path -> (old_version, new_version)).
SUPERSEDED_RC1_PATHS = {
    # RC4 four-plane law: environment widened LIVE -> LIVE|TESTNET (B01).
    "contracts/schemas/triad.fill.v3.schema.json": ("3.0.0", "3.1.0"),
    "contracts/golden/triad.fill.v3/valid.json": ("3.0.0", "3.1.0"),
    "contracts/golden/triad.fill.v3/invalid.json": ("3.0.0", "3.1.0"),
    # RC4: commands name exact environment + accepted activation revision (B01).
    "contracts/schemas/triad.execution_cmd.v2.schema.json": ("2.0.0", "2.1.0"),
    "contracts/golden/triad.execution_cmd.v2/valid.json": ("2.0.0", "2.1.0"),
    "contracts/golden/triad.execution_cmd.v2/invalid.json": ("2.0.0", "2.1.0"),
    # Registry index: additive B01 entries + identity v2 declaration (not a versioned contract).
    "contracts/registry/index.json": (None, None),
}


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _declared_version(path: pathlib.Path) -> str | None:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(doc, dict):
        # Schemas carry the version in properties.schema_version.const; goldens in the envelope.
        props = doc.get("properties")
        if isinstance(props, dict):
            sv = props.get("schema_version")
            if isinstance(sv, dict) and isinstance(sv.get("const"), str):
                return sv["const"]
        if isinstance(doc.get("schema_version"), str):
            return doc["schema_version"]
    return None


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
    new_by_path = {a["path"]: a["sha256"] for a in expected_payload["artifacts"]}
    problems = []

    # Frozen historical descriptors.
    for frozen_path, frozen_sha, label in (
        (LEGACY_MANIFEST_JSON, LEGACY_MANIFEST_SHA256, "immutable RC1 bundle descriptor"),
        (R00_MANIFEST_JSON, R00_MANIFEST_SHA256, "frozen R00 bundle descriptor"),
    ):
        if not frozen_path.exists():
            problems.append(f"{label} is missing")
        elif _sha256_bytes(frozen_path.read_bytes()) != frozen_sha:
            problems.append(f"{label} bytes changed")

    # Additive law over the RC1 baseline: every RC1 path still exists; bytes unchanged unless a
    # recorded version bump covers the path.
    if LEGACY_MANIFEST_JSON.exists():
        legacy = json.loads(LEGACY_MANIFEST_JSON.read_text(encoding="utf-8"))
        legacy_by_path = {a["path"]: a["sha256"] for a in legacy.get("artifacts", [])}
        for path in sorted(set(legacy_by_path) - actual_paths):
            problems.append(f"RC1 artifact removed from bundle: {path}")
        for path in sorted(set(legacy_by_path) & actual_paths):
            if legacy_by_path[path] == new_by_path[path]:
                continue
            if path not in SUPERSEDED_RC1_PATHS:
                problems.append(f"RC1 artifact bytes changed without a recorded supersession: "
                                f"{path}")
                continue
            old_version, new_version = SUPERSEDED_RC1_PATHS[path]
            if old_version is None:
                continue  # registry index: additive, not a versioned contract document
            declared = _declared_version(ROOT / path)
            if declared != new_version:
                problems.append(
                    f"superseded RC1 artifact {path} declares version {declared!r}, "
                    f"expected {new_version!r}")
            elif declared == old_version:
                problems.append(
                    f"superseded RC1 artifact {path} still declares its frozen version "
                    f"{old_version!r}")

    for extra in sorted(actual_paths - disk_paths):
        problems.append(f"unmanifested bundle file: {extra}")
    for missing in sorted(disk_paths - actual_paths):
        problems.append(f"manifest references missing file: {missing}")

    disk_by_path = {a["path"]: a["sha256"] for a in on_payload.get("artifacts", [])}
    for path in sorted(disk_paths & actual_paths):
        if disk_by_path[path] != new_by_path.get(path):
            problems.append(f"byte change without manifest update: {path}")

    # CTRL-B01-001: the living descriptor must label media types correctly.
    for artifact in on_payload.get("artifacts", []):
        path = artifact["path"]
        is_schema = path.endswith(".schema.json")
        expected_media = "application/schema+json" if is_schema else "application/json"
        if artifact.get("media_type") != expected_media:
            problems.append(f"descriptor media_type wrong for {path}: "
                            f"{artifact.get('media_type')!r} != {expected_media!r}")

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
