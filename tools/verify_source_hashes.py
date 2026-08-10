#!/usr/bin/env python3
"""Strictly verify ``docs/control/SOURCE_HASHES.sha256`` (B00R-D06 / SRC-001 / SRC-002).

Until B00R this inventory existed but CI never recomputed it. This tool:

  1. strictly parses the file (lowercase nonzero hex, canonical relative paths, no duplicates, no
     path escape) via :func:`triad_origin.governance.parse_source_hashes`;
  2. recomputes every listed file's SHA-256 from bytes and fails on any mismatch or missing file;
  3. verifies the RC3 embedded composition manifest digests (effective bundle / overlay / overlay
     schema) against the actual bytes — a self-updating source + in-tree hash cannot bypass the
     embedded composition identity; and
  4. proves complete expected membership: every controlling authority/decision/policy/schema/
     generated-bundle artifact below must be pinned.

Exit 0 iff every check passes. This is an inventory verifier; it certifies no gate.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from triad_origin import governance  # noqa: E402

SOURCE_HASHES = ROOT / "docs" / "control" / "SOURCE_HASHES.sha256"

# Controlling artifacts that MUST be pinned (complete expected membership). A new controlling
# artifact that is not pinned here fails the run.
REQUIRED_MEMBERSHIP = [
    "docs/control/rc3_effective_control_bundle.json",
    "docs/control/rc3_normative_overlay.json",
    "docs/control/rc3_overlay_schema.json",
    "docs/control/rc3_effective_bundle_manifest.json",
    "docs/control/rc4_control_bundle.json",
    "docs/control/b00r_policy.v1.json",
    "docs/governance/B00_B07_INVALIDATION_MANIFEST.v1.json",
    "contracts/schemas/triad.evidence_receipt.v3.schema.json",
    "contracts/schemas/triad.receipt_trust_registry.v1.schema.json",
    "contracts/schemas/triad.governance_decision.v1.schema.json",
    "contracts/schemas/triad.governance_snapshot.v1.schema.json",
    "contracts/schemas/triad.evidence_manifest.v1.schema.json",
]


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_rc3_composition(problems: list[str]) -> None:
    manifest_path = ROOT / "docs/control/rc3_effective_bundle_manifest.json"
    if not manifest_path.exists():
        problems.append("rc3 composition manifest missing")
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checks = {
        "effective_bundle_sha256": "docs/control/rc3_effective_control_bundle.json",
        "overlay_sha256": "docs/control/rc3_normative_overlay.json",
        "overlay_schema_sha256": "docs/control/rc3_overlay_schema.json",
    }
    for field, rel in checks.items():
        declared = manifest.get(field)
        actual = _sha256(ROOT / rel)
        if declared != actual:
            problems.append(f"rc3 composition {field} mismatch: declared {str(declared)[:16]} "
                            f"!= actual {actual[:16]} ({rel})")


def main() -> int:
    if not SOURCE_HASHES.exists():
        print("FAIL: docs/control/SOURCE_HASHES.sha256 missing", file=sys.stderr)
        return 1
    try:
        pins = governance.parse_source_hashes(SOURCE_HASHES.read_text(encoding="utf-8"))
    except governance.GovernanceError as exc:
        print(f"FAIL: SOURCE_HASHES parse: {exc}", file=sys.stderr)
        return 1

    problems: list[str] = []
    for rel, digest in sorted(pins.items()):
        path = ROOT / rel
        if not path.is_file():
            problems.append(f"pinned file missing: {rel}")
            continue
        actual = _sha256(path)
        if actual != digest:
            problems.append(f"byte change vs pin: {rel} ({actual[:16]} != {digest[:16]})")

    for rel in REQUIRED_MEMBERSHIP:
        if rel not in pins:
            problems.append(f"controlling artifact not pinned: {rel}")

    _verify_rc3_composition(problems)

    if problems:
        for p in problems:
            print(f"FAIL: {p}", file=sys.stderr)
        return 1
    print(f"OK: {len(pins)} source hashes verified; RC3 composition manifest consistent; "
          f"{len(REQUIRED_MEMBERSHIP)} required artifacts pinned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
