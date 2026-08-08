#!/usr/bin/env python3
"""Regenerate the contract bundle manifest and ``contracts/MANIFEST.sha256`` (Doc 03 §03.9).

The manifest pins the **exact committed bytes** of every schema, golden vector and registry index.
A version string alone never identifies a bundle (the 1.37.0 drift is why). CI
(``tools/verify_manifest.py``) recomputes and fails on any unmanifested or same-version byte change.
"""

from __future__ import annotations

import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts"
MANIFEST_JSON = CONTRACTS / "manifest" / "contract_bundle.manifest.v1.json"
MANIFEST_SHA = CONTRACTS / "MANIFEST.sha256"
BUNDLE_VERSION = "origin.contracts.1.0.0-RC1"


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bundle_files() -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    for sub in ("schemas", "golden", "registry"):
        base = CONTRACTS / sub
        if base.exists():
            files.extend(p for p in base.rglob("*.json") if p.is_file())
    return sorted(files, key=lambda p: str(p.relative_to(ROOT)))


def _media_type(path: pathlib.Path) -> str:
    return "application/schema+json" if path.suffix == ".json" else "application/octet-stream"


def build_manifest() -> dict:
    artifacts = []
    for p in bundle_files():
        rel = str(p.relative_to(ROOT))
        artifacts.append({
            "path": rel,
            "media_type": _media_type(p),
            "sha256": _sha256(p),
        })
    manifest = {
        "schema": "triad.contract_bundle.manifest.v1",
        "bundle_version": BUNDLE_VERSION,
        "artifacts": artifacts,
    }
    # Canonical manifest hash over the artifact list (sorted-key JSON, no self-reference).
    body = json.dumps({"bundle_version": BUNDLE_VERSION, "artifacts": artifacts},
                      sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    manifest["canonical_manifest_hash"] = hashlib.sha256(body).hexdigest()
    return manifest


def write_manifest() -> dict:
    manifest = build_manifest()
    MANIFEST_JSON.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_JSON.write_text(
        json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [f"{a['sha256']}  {a['path']}" for a in manifest["artifacts"]]
    lines.append(f"{manifest['canonical_manifest_hash']}  {BUNDLE_VERSION}")
    MANIFEST_SHA.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    m = write_manifest()
    print(f"manifest: {len(m['artifacts'])} artifacts | canonical_hash={m['canonical_manifest_hash']}")
