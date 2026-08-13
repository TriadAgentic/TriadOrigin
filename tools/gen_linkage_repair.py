#!/usr/bin/env python3
"""CO-06 — Verification-linkage repair overlay (additive; masters never mutated).

The RC3 effective control bundle carries three OPEN linkage blockers over the 408 preserved RC1
verification rows (``rc3_extensions.unresolved_linkage_blockers``):

  * ``RC3-LINK-BLOCK-001`` — 182 rows carry a slash-delimited **composite scalar gate**
    (``G2/G3`` …) that no single-gate edge resolves.
  * ``RC3-LINK-BLOCK-002`` — 17 SEM rows carry ``linked_task_ids = "CTL-G2/G3-03"``, a task id
    that does not exist in the bundle (a corrupted mash-up of the two real gate-anchor tasks
    ``CTL-G2-03`` / ``CTL-G3-03``). The finding forbids any *inferred* blanket replacement — a
    semantic owner must select the exact task ids.
  * ``RC3-LINK-BLOCK-003`` — all 408 preserved RC1 rows are *not required by* any
    acceptance/task/gate edge (no ``criteria[].verification_id`` and no ``task.verification_refs``
    names them).

This tool reads the FROZEN masters — the RC1 verification matrix CSV, the RC3 effective control
bundle and the RC4 control bundle — and emits a SEPARATE additive overlay
(``docs/control/linkage_repair_overlay.v1.json``) that records, deterministically and without any
fabrication:

  1. the chosen composite-gate representation — the **typed multi-gate edge** ``gates[]`` per row,
     every member validated against the real gate registry (RC3-LINK-BLOCK-001);
  2. the per-row disposition of the 17 ``CTL-G2/G3-03`` danglers — each individually retired from
     the *effective* linkage and marked ``EDGE_UNRESOLVED_PRESERVED`` (task-owner selection is a
     semantic-owner authority this agent does not hold — never a guessed replacement,
     RC3-LINK-BLOCK-002);
  3. the row-level required edges for all 408 rows — the **gate edge** (unique legitimate target:
     the ``CTL-G{n}-03`` gate anchor) attached to every row; the **task edge** attached where every
     ``linked_task_ids`` token resolves to a real task (391 rows); the **acceptance edge** left
     ``EDGE_UNRESOLVED_PRESERVED`` uniformly (no unique acceptance criterion links any RC1 row and
     deriving one requires semantic-ownership review — RC3-LINK-BLOCK-003);
  4. the B09 unique-set recomputation — base ``1,648`` = 1,523 unique effective verification ids
     (the 408 RC1 rows subsumed by lineage) + 125 RC4 fixtures, WITHOUT the blind summation
     (408 + 1,523 + 125 = 2,056) that double-counts the RC1 lineage.

**Honest boundary.** The overlay is additive evidence; it NEVER mutates the RC3 bundle or any
master, and it NEVER flips an OPEN_BLOCKER to RESOLVED — the RC3 closure rule requires a signed
RESOLVED event, which this agent cannot produce. Blocker 001/003 materializations read
``MATERIALIZED_AWAITING_SIGNED_CLOSURE``; blocker 002 reads ``UNRESOLVED_SEMANTIC_OWNER_REQUIRED``.
Posture stays OFF/OFF/OFF/LIVE · DENIED_SAFE_HOLD. The tool arms nothing and reaches no
venue/network/credential/order path.

Determinism: stdlib only; canonical JSON (sorted keys); sha256; no wall clock, no randomness, no
environment read on the semantic path. Byte-stable across independent runs.

Usage::

    python tools/gen_linkage_repair.py            # verify (recompute; assert on-disk == recomputed)
    python tools/gen_linkage_repair.py --write     # (re)write the overlay
    python tools/gen_linkage_repair.py --check      # explicit verify (same as no args)

Exit 0 only when every invariant holds. This tool validates linkage; it certifies no gate and
marks nothing complete.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTROL = ROOT / "docs" / "control"
SPEC = ROOT / "docs" / "spec"

# --- FROZEN masters this tool READS (never writes) ------------------------------------------------
RC1_CSV = SPEC / "TRIAD_ORIGIN_V7_VERIFICATION_MATRIX_1.0.0_RC1.csv"
RC1_HTML = SPEC / "08_TRIAD_ORIGIN_V7_VERIFICATION_MATRIX_1.0.0_RC1.html"
RC3_BUNDLE = CONTROL / "rc3_effective_control_bundle.json"
RC4_BUNDLE = CONTROL / "rc4_control_bundle.json"
RC5_BUNDLE = CONTROL / "rc5_bundle.json"  # CO-01 dependency; OPTIONAL — may not be landed here.

# --- the SEPARATE additive overlay this tool WRITES ----------------------------------------------
OVERLAY_PATH = CONTROL / "linkage_repair_overlay.v1.json"

OVERLAY_SCHEMA = "triad.linkage_repair_overlay.v1"
CO = "CO-06"
RC1_LINEAGE = "RC1_408_PRESERVED"

POSTURE = {
    "venue_environment": "OFF",
    "venue_activation": "OFF",
    "paper_activation": "OFF",
    "shadow_activation": "LIVE",
    "activation_result": "DENIED_SAFE_HOLD",
}

# The RC3 gate-anchor task pattern: gate ``Gn`` → task ``CTL-Gn-03`` ("evaluate all required work").
_ANCHOR_FMT = "CTL-{gate}-03"


class LinkageRepairError(RuntimeError):
    """Raised when an invariant of the linkage repair is violated (fail-closed)."""


# --- pure helpers (no clock / no randomness / no env) --------------------------------------------
def _canonical_json(obj: Any) -> bytes:
    """Canonical UTF-8 JSON: sorted keys, compact separators, no NaN/Infinity, no floats."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _split_tokens(value: str) -> list[str]:
    """Split a ``;``/``,``-delimited link scalar into trimmed non-empty tokens (order preserved)."""
    out: list[str] = []
    for chunk in str(value or "").replace(",", ";").split(";"):
        tok = chunk.strip()
        if tok:
            out.append(tok)
    return out


def _read_csv_rows(path: pathlib.Path) -> list[dict[str, str]]:
    """Minimal stdlib CSV read of the frozen RC1 matrix (id → row), in frozen master order."""
    import csv

    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# --- overlay construction ------------------------------------------------------------------------
def build_overlay() -> dict[str, Any]:
    """Build the deterministic linkage-repair overlay dict from the frozen masters."""
    if not RC3_BUNDLE.is_file():
        raise LinkageRepairError(f"RC3 effective control bundle missing: {RC3_BUNDLE}")
    if not RC1_CSV.is_file():
        raise LinkageRepairError(f"RC1 verification matrix master missing: {RC1_CSV}")
    if not RC4_BUNDLE.is_file():
        raise LinkageRepairError(f"RC4 control bundle missing: {RC4_BUNDLE}")

    bundle = json.loads(RC3_BUNDLE.read_text(encoding="utf-8"))
    rc4 = json.loads(RC4_BUNDLE.read_text(encoding="utf-8"))

    real_tasks = {t["id"] for t in bundle["tasks"]}
    real_criteria = {c["criterion_id"] for c in bundle["criteria"]}
    real_gates = {g["gate"] for g in bundle["gates"]}

    verifications = bundle["verifications"]
    by_id = {v["verification_id"]: v for v in verifications}
    unique_verification_ids = sorted(by_id)
    rc1_rows = {vid: v for vid, v in by_id.items() if v.get("source") == RC1_LINEAGE}

    # Cross-check the frozen CSV master against the bundle's RC1 rows (drift detection): the tool
    # must READ the master and prove agreement, never quietly diverge from it.
    csv_rows = _read_csv_rows(RC1_CSV)
    csv_ids = [r["id"] for r in csv_rows]
    csv_gate = {r["id"]: r["gate"] for r in csv_rows}
    if set(csv_ids) != set(rc1_rows):
        raise LinkageRepairError(
            "RC1 master CSV ids disagree with the bundle RC1_408_PRESERVED rows — "
            "master/bundle drift; refusing to guess."
        )
    for vid in csv_ids:
        if csv_gate[vid] != rc1_rows[vid]["gate"]:
            raise LinkageRepairError(
                f"RC1 gate disagreement for {vid}: csv={csv_gate[vid]!r} "
                f"bundle={rc1_rows[vid]['gate']!r}"
            )

    # Per-row dispositions, iterated in FROZEN master (CSV) order for byte-stability.
    dispositions: list[dict[str, Any]] = []
    composite_count = 0
    resolved_task_count = 0
    edge_unresolved_count = 0
    retired_disposition_count = 0
    for vid in csv_ids:
        row = rc1_rows[vid]
        gate_scalar = row["gate"]
        gates = gate_scalar.split("/")
        bad_members = [m for m in gates if m not in real_gates]
        if bad_members:
            raise LinkageRepairError(
                f"{vid}: gate member(s) {bad_members} not in the real gate registry"
            )
        gate_edges = []
        for m in gates:
            anchor = _ANCHOR_FMT.format(gate=m)
            if anchor not in real_tasks:
                raise LinkageRepairError(
                    f"{vid}: gate anchor {anchor} for member {m} is not a real task"
                )
            gate_edges.append(anchor)
        composite = len(gates) > 1
        if composite:
            composite_count += 1

        tokens = _split_tokens(row.get("linked_task_ids", ""))
        task_edges = [t for t in tokens if t in real_tasks]
        retired = [t for t in tokens if t not in real_tasks]

        if retired:
            task_edge_status = "TASK_LINK_RETIRED_UNRESOLVED"
            row_disposition = "EDGE_UNRESOLVED_PRESERVED"
            conformance_countable = False
            edge_unresolved_count += 1
            retired_disposition_count += 1
            # each retired link carries an individual, typed reason (blocker 002).
            retired_records = [
                {
                    "retired_task_id": t,
                    "reason": (
                        "task id does not exist in the RC3 effective control bundle; "
                        "RC3-LINK-BLOCK-002 forbids an inferred replacement — a semantic owner "
                        "must select the exact existing task ids in a signed event."
                    ),
                    "disposition": "RETIRED_FROM_EFFECTIVE_LINKAGE_PENDING_SEMANTIC_OWNER",
                }
                for t in retired
            ]
        else:
            task_edge_status = "RESOLVED"
            row_disposition = "REQUIRED_EDGES_RESOLVED"
            conformance_countable = True
            resolved_task_count += 1
            retired_records = []

        dispositions.append(
            {
                "verification_id": vid,
                "source_lineage": RC1_LINEAGE,
                "gate_scalar": gate_scalar,
                "gates": gates,
                "composite": composite,
                "gate_edge_target_tasks": gate_edges,
                "gate_edge_status": "RESOLVED",
                "linked_task_ids_scalar": row.get("linked_task_ids", ""),
                "task_edge_target_tasks": task_edges,
                "task_edge_status": task_edge_status,
                "retired_task_links": retired_records,
                "acceptance_edge_target_criteria": [],
                "acceptance_edge_status": "EDGE_UNRESOLVED_PRESERVED",
                "acceptance_edge_reason": (
                    "no acceptance criterion in the RC3 bundle names this verification_id and no "
                    "task.verification_refs requires it; a unique acceptance owner cannot be "
                    "derived without semantic-ownership review — RC3-LINK-BLOCK-003."
                ),
                "row_disposition": row_disposition,
                "conformance_countable": conformance_countable,
            }
        )

    if len(dispositions) != 408:
        raise LinkageRepairError(f"expected 408 RC1 dispositions, built {len(dispositions)}")

    # Effective (post-overlay) linkage dangling check: every materialized edge must resolve to a
    # real target; retired links are NOT materialized as edges.
    effective_targets: set[str] = set()
    for d in dispositions:
        effective_targets.update(d["gate_edge_target_tasks"])
        effective_targets.update(d["task_edge_target_tasks"])
        effective_targets.update(d["acceptance_edge_target_criteria"])
    dangling = sorted(t for t in effective_targets if t not in (real_tasks | real_criteria))
    if dangling:
        raise LinkageRepairError(f"effective linkage still has dangling references: {dangling}")

    # Pre-overlay dangling references over the raw RC1 linked_task_ids (evidence the repair removed).
    pre_dangling: dict[str, int] = {}
    for row in rc1_rows.values():
        for t in _split_tokens(row.get("linked_task_ids", "")):
            if t not in real_tasks:
                pre_dangling[t] = pre_dangling.get(t, 0) + 1

    # B09 unique-set recomputation (by id and lineage), base 1,648 — no blind summation of the 408.
    rc4_fixtures = len(rc4["verifications"])
    unique_count = len(unique_verification_ids)
    rc1_count = len(rc1_rows)
    base_unique_population = unique_count + rc4_fixtures
    blind_summation = rc1_count + unique_count + rc4_fixtures
    conformance_denominator = base_unique_population - edge_unresolved_count

    reads = {
        "rc1_matrix_csv": {"path": _rel(RC1_CSV), "sha256": _sha256_file(RC1_CSV)},
        "rc1_matrix_html": {"path": _rel(RC1_HTML), "sha256": _sha256_file(RC1_HTML)}
        if RC1_HTML.is_file()
        else {"path": _rel(RC1_HTML), "sha256": None, "status": "ABSENT"},
        "rc3_effective_control_bundle": {
            "path": _rel(RC3_BUNDLE),
            "sha256": _sha256_file(RC3_BUNDLE),
        },
        "rc4_control_bundle": {"path": _rel(RC4_BUNDLE), "sha256": _sha256_file(RC4_BUNDLE)},
    }
    if RC5_BUNDLE.is_file():
        reads["rc5_bundle"] = {"path": _rel(RC5_BUNDLE), "sha256": _sha256_file(RC5_BUNDLE)}
    else:
        reads["rc5_bundle"] = {
            "path": _rel(RC5_BUNDLE),
            "sha256": None,
            "status": "ABSENT_DEPENDENCY_NOT_LANDED",
            "note": (
                "CO-01 rc5 consolidation is not present in this base; the linkage repair derives "
                "entirely from the RC1 master + RC3 machine registries, so rc5 is not required "
                "for resolution. Recorded honestly rather than fabricated."
            ),
        }

    gate_edge_map = {
        m: _ANCHOR_FMT.format(gate=m)
        for m in sorted(real_gates)
        if _ANCHOR_FMT.format(gate=m) in real_tasks
    }

    overlay = {
        "schema": OVERLAY_SCHEMA,
        "change_order": CO,
        "kind": "ADDITIVE_LINKAGE_REPAIR_EVIDENCE",
        "mutates_masters": False,
        "posture": POSTURE,
        "reads": reads,
        "composite_gate_representation": {
            "chosen": "TYPED_MULTI_GATE_EDGE",
            "field": "gates",
            "retired_scalar_delimiter": "/",
            "rationale": (
                "One representation applied uniformly: each row's scalar gate is materialized as a "
                "typed gates[] array (split on '/'), and every member is validated against the "
                "real gate registry. A composite is then a first-class multi-gate edge, not a "
                "string no single-gate edge can resolve (RC3-LINK-BLOCK-001)."
            ),
            "composite_rows": composite_count,
            "single_gate_rows": len(dispositions) - composite_count,
        },
        "gate_edge_map": gate_edge_map,
        "blocker_resolutions": {
            "RC3-LINK-BLOCK-001": {
                "defect": "slash-delimited composite scalar gates",
                "population": 182,
                "action": "materialize gates[] typed multi-gate edge per row; validate every member",
                "members_all_valid": True,
                "effective_status": "MATERIALIZED_AWAITING_SIGNED_CLOSURE",
                "note": (
                    "Materialization is deterministic and complete; the RC3 finding stays "
                    "OPEN_BLOCKER until a signed RESOLVED event per its closure rule. This overlay "
                    "does not mutate the finding in place."
                ),
            },
            "RC3-LINK-BLOCK-002": {
                "defect": "linked_task_ids points to nonexistent CTL-G2/G3-03",
                "population": edge_unresolved_count,
                "action": (
                    "retire the dangling task id from the effective linkage per row; mark the row "
                    "EDGE_UNRESOLVED_PRESERVED; DO NOT infer a replacement"
                ),
                "effective_status": "UNRESOLVED_SEMANTIC_OWNER_REQUIRED",
                "note": (
                    "The finding forbids an inferred blanket replacement; a semantic owner must "
                    "select the exact existing task ids in a signed event. Each of the "
                    f"{edge_unresolved_count} rows is individually recorded below."
                ),
                "affected_verification_ids": sorted(
                    d["verification_id"]
                    for d in dispositions
                    if d["task_edge_status"] == "TASK_LINK_RETIRED_UNRESOLVED"
                ),
            },
            "RC3-LINK-BLOCK-003": {
                "defect": "not required by an acceptance/task/gate edge",
                "population": 408,
                "action": (
                    "materialize row-level required edges: gate edge for all 408 (unique gate "
                    "anchor); task edge for rows whose links all resolve (391); acceptance edge "
                    "left EDGE_UNRESOLVED_PRESERVED uniformly (no unique acceptance owner)"
                ),
                "rows_required_by_gate_edge": 408,
                "rows_required_by_task_edge": resolved_task_count,
                "rows_edge_unresolved_preserved": edge_unresolved_count,
                "acceptance_edge_status": "EDGE_UNRESOLVED_PRESERVED_ALL",
                "effective_status": "MATERIALIZED_AWAITING_SIGNED_CLOSURE",
                "note": (
                    "408/408 rows are now required by at least a gate edge (a unique legitimate "
                    "target present on the row). The finer acceptance ownership is a uniform named "
                    "gap; the finding stays OPEN_BLOCKER until a signed RESOLVED event."
                ),
            },
        },
        "b09_unique_set": {
            "unique_verification_ids": unique_count,
            "rc4_fixtures": rc4_fixtures,
            "rc1_lineage_rows": rc1_count,
            "base_unique_population": base_unique_population,
            "blind_summation_rejected": blind_summation,
            "edge_unresolved_preserved_count": edge_unresolved_count,
            "conformance_denominator": conformance_denominator,
            "rule": (
                "The 408 RC1 rows are subsumed within the 1,523 effective verifications by lineage "
                "(source RC1_408_PRESERVED); the unique set adds only the RC4 fixtures. Adding the "
                "408 again (408 + 1,523 + 125 = 2,056) is the blind summation this recomputation "
                "rejects. EDGE_UNRESOLVED_PRESERVED rows are evidence, never coverage, and are "
                "excluded from the conformance denominator until resolved."
            ),
        },
        "pre_overlay_dangling_references": pre_dangling,
        "effective_dangling_references": dangling,
        "counts": {
            "rc1_dispositions": len(dispositions),
            "composite_rows": composite_count,
            "task_edge_resolved_rows": resolved_task_count,
            "edge_unresolved_preserved_rows": edge_unresolved_count,
            "retired_link_dispositions": retired_disposition_count,
        },
        "row_dispositions": dispositions,
    }
    return overlay


def _rel(path: pathlib.Path) -> str:
    return str(path.relative_to(ROOT))


# --- effective-linkage checks (public, for tests) -------------------------------------------------
def effective_dangling_references(overlay: dict[str, Any]) -> list[str]:
    """Return materialized edge targets in the overlay that resolve to no real task/criterion."""
    bundle = json.loads(RC3_BUNDLE.read_text(encoding="utf-8"))
    real = {t["id"] for t in bundle["tasks"]} | {c["criterion_id"] for c in bundle["criteria"]}
    targets: set[str] = set()
    for d in overlay["row_dispositions"]:
        targets.update(d["gate_edge_target_tasks"])
        targets.update(d["task_edge_target_tasks"])
        targets.update(d["acceptance_edge_target_criteria"])
    return sorted(t for t in targets if t not in real)


def recompute_b09(overlay: dict[str, Any]) -> dict[str, int]:
    """Return the B09 unique-set integers recomputed straight from the frozen masters."""
    bundle = json.loads(RC3_BUNDLE.read_text(encoding="utf-8"))
    rc4 = json.loads(RC4_BUNDLE.read_text(encoding="utf-8"))
    unique = len({v["verification_id"] for v in bundle["verifications"]})
    rc1 = len([v for v in bundle["verifications"] if v.get("source") == RC1_LINEAGE])
    fixtures = len(rc4["verifications"])
    unresolved = sum(
        1 for d in overlay["row_dispositions"] if not d["conformance_countable"]
    )
    return {
        "unique_verification_ids": unique,
        "rc4_fixtures": fixtures,
        "rc1_lineage_rows": rc1,
        "base_unique_population": unique + fixtures,
        "blind_summation_rejected": rc1 + unique + fixtures,
        "edge_unresolved_preserved_count": unresolved,
        "conformance_denominator": unique + fixtures - unresolved,
    }


def master_digests() -> dict[str, str]:
    """SHA-256 of every frozen master this tool reads (for the never-mutate assertion)."""
    out = {_rel(RC1_CSV): _sha256_file(RC1_CSV), _rel(RC3_BUNDLE): _sha256_file(RC3_BUNDLE),
           _rel(RC4_BUNDLE): _sha256_file(RC4_BUNDLE)}
    if RC1_HTML.is_file():
        out[_rel(RC1_HTML)] = _sha256_file(RC1_HTML)
    return out


# --- CLI -----------------------------------------------------------------------------------------
def _write(overlay: dict[str, Any]) -> None:
    OVERLAY_PATH.write_bytes(_canonical_json(overlay))


def _verify() -> int:
    problems: list[str] = []
    overlay = build_overlay()
    recomputed = _canonical_json(overlay)

    if not OVERLAY_PATH.is_file():
        problems.append(f"overlay missing: {_rel(OVERLAY_PATH)} (run with --write)")
    else:
        on_disk = OVERLAY_PATH.read_bytes()
        if on_disk != recomputed:
            problems.append("on-disk overlay is not byte-identical to the recomputed overlay")

    # byte-stability across two independent builds
    if _canonical_json(build_overlay()) != recomputed:
        problems.append("overlay is not byte-stable across two builds")

    dangling = effective_dangling_references(overlay)
    if dangling:
        problems.append(f"effective linkage dangling references remain: {dangling}")

    b09 = recompute_b09(overlay)
    if b09["base_unique_population"] != 1648:
        problems.append(f"B09 base unique population != 1648 (got {b09['base_unique_population']})")
    if b09 != {k: overlay["b09_unique_set"][k] for k in b09}:
        problems.append("overlay b09_unique_set disagrees with the recomputation")
    if b09["base_unique_population"] == b09["blind_summation_rejected"]:
        problems.append("base population equals the blind summation (408 double-counted)")

    if overlay["posture"] != POSTURE:
        problems.append("posture drift (must be OFF/OFF/OFF/LIVE · DENIED_SAFE_HOLD)")

    if problems:
        for p in problems:
            print(f"FAIL: {p}", file=sys.stderr)
        return 1

    c = overlay["counts"]
    print(
        "OK: linkage repair overlay valid — "
        f"{c['rc1_dispositions']} RC1 dispositions "
        f"({c['composite_rows']} composite, {c['task_edge_resolved_rows']} task-resolved, "
        f"{c['edge_unresolved_preserved_rows']} EDGE_UNRESOLVED_PRESERVED); "
        f"zero effective dangling refs; B09 base {b09['base_unique_population']} "
        f"(blind-summation {b09['blind_summation_rejected']} rejected); "
        f"conformance denominator {b09['conformance_denominator']}."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CO-06 verification-linkage repair overlay.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true", help="(re)write the overlay to disk")
    group.add_argument("--check", action="store_true", help="verify (default)")
    args = parser.parse_args(argv)

    if args.write:
        _write(build_overlay())
        print(f"WROTE: {_rel(OVERLAY_PATH)}")
        return 0
    return _verify()


if __name__ == "__main__":
    raise SystemExit(main())
