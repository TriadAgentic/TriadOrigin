#!/usr/bin/env python3
"""Structural migration of all 105 formula-parameter bindings into binding.v2 (B01R).

Reads the vendored RC3 effective control bundle's ``formula_parameter_bindings`` rows and
materializes ``docs/control/binding_registry.v2.json``: one ``triad.binding.v2`` payload row per
source binding, byte-deterministic, with every source status preserved VERBATIM. Structural
migration never ratifies a value: the effective state remains 3 ``ACTIVE``, 4 ``BLOCKED``,
98 ``BLOCKED_BINDING_V2_MIGRATION`` until governance moves a row.

Each row is validated against the pinned binding.v2 payload schema + semantic law, carries its
digest identity, and drops nothing silently: the source ``rc2_source_binding`` is preserved as a
digest reference, and ``migration_state: null`` in the source maps to the honest
``NOT_APPLICABLE`` (the row was born v2-shaped), never to a fabricated migrated claim.

Usage:
  python tools/gen_binding_registry.py             # write the registry
  python tools/gen_binding_registry.py --verify    # regenerate to memory and compare (CI)
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import contracts  # noqa: E402
from triad_origin.canonical import canonical_json, sha256_hex  # noqa: E402

BUNDLE = ROOT / "docs" / "control" / "rc3_effective_control_bundle.json"
REGISTRY = ROOT / "docs" / "control" / "binding_registry.v2.json"

REGISTRY_VERSION = "origin.binding-registry.v2"

_ROW_FIELDS = (
    "binding_id", "semantic_slot", "formula_id", "parameter_id", "parameter_name",
    "declared_value", "unit", "unit_contract", "cardinality", "condition", "activation_scope",
    "precedence", "consumer", "consuming_wiring_ids", "gate", "status", "lifecycle_status",
    "failure_behavior", "boundary_rule", "operation_id", "source_binding_id",
)


def migrate_row(source: dict) -> dict:
    row = {}
    for field in _ROW_FIELDS:
        value = source.get(field)
        row[field] = value if isinstance(value, str) else ""
    row["superseded_by"] = source.get("superseded_by") or ""
    row["disposition_reason"] = source.get("disposition_reason") or ""
    migration = source.get("migration_state")
    row["migration_state"] = migration if isinstance(migration, str) else "NOT_APPLICABLE"
    rc2 = source.get("rc2_source_binding")
    if isinstance(rc2, dict):
        row["rc2_source_digest"] = sha256_hex(canonical_json(rc2))
    unsigned = dict(row)
    row["binding_digest"] = sha256_hex(canonical_json(unsigned))
    return row


def build() -> dict:
    bundle = json.loads(BUNDLE.read_text())
    sources = bundle["formula_parameter_bindings"]
    rows = [migrate_row(source) for source in sources]
    rows.sort(key=lambda r: r["binding_id"])

    # Validate every row against the pinned contract payload schema + semantic law.
    slots_active: dict[str, str] = {}
    status_counts: dict[str, int] = {}
    for row in rows:
        contracts.validate_payload("triad.binding.v2", row)
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
        if row["status"] == "ACTIVE" and not row["superseded_by"]:
            slot = row["semantic_slot"]
            if slot in slots_active:
                raise SystemExit(
                    f"OVERLAP: active bindings {slots_active[slot]} and {row['binding_id']} "
                    f"both claim semantic slot {slot!r}")
            slots_active[slot] = row["binding_id"]

    return {
        "registry_version": REGISTRY_VERSION,
        "source_bundle_digest": sha256_hex(BUNDLE.read_bytes()),
        "row_count": len(rows),
        "status_counts": dict(sorted(status_counts.items())),
        "rows": rows,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)

    registry = build()
    rendered = json.dumps(registry, indent=1, sort_keys=True) + "\n"

    expected = {"ACTIVE": 3, "BLOCKED": 4, "BLOCKED_BINDING_V2_MIGRATION": 98}
    if registry["status_counts"] != expected:
        print(f"FAIL: source statuses not preserved: {registry['status_counts']} != {expected}",
              file=sys.stderr)
        return 1

    if args.verify:
        if not REGISTRY.exists():
            print("FAIL: binding registry missing; run tools/gen_binding_registry.py",
                  file=sys.stderr)
            return 1
        if REGISTRY.read_text() != rendered:
            print("FAIL: binding registry stale; run tools/gen_binding_registry.py",
                  file=sys.stderr)
            return 1
        print(f"OK: binding registry current ({registry['row_count']} rows, "
              f"statuses preserved {registry['status_counts']})")
        return 0

    REGISTRY.write_text(rendered)
    print(f"wrote {REGISTRY} ({registry['row_count']} rows, {registry['status_counts']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
