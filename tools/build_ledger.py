#!/usr/bin/env python3
"""Deterministic build ledger for the TRIAD ORIGIN V7 B-series build.

Partitions every effective control task (RC3 effective control bundle, 1,115 rows +
RC4 lever addendum bundle, 135 rows) into:

  * a build milestone (``B00``..``B10``) when the task is executable inside this
    repository, or a named non-repo lane (``ESTATE``, ``OPERATOR``, ``RESEARCH``,
    ``ACTIVATION``) when it is not; and
  * an executability class describing *why* it landed there.

The current partition is CANDIDATE_V3: the transparent, deterministic rule table
(corrected at B00C to the reconciled plan — F01/F07 are E01-owned, the four-plane
substrate is B05, capsules/candidates are B06) applied in order (first match wins),
plus a reviewed override file
(``docs/control/build_ledger_overrides.json``) that takes precedence over every
rule. The historical row-level review in
``docs/control/build_ledger_review.v1.json`` applies only to the exact frozen
``REVIEWED_V2`` ledger under ``docs/control/closure/predecessors``. ``--verify``
proves that historical relationship and reports every current row changed since
that review subject; it never upgrades those rows to reviewed by implication.

Nothing here marks a task complete. Task status remains NOT_STARTED until the
owning milestone PR records evidence; completion claims live in milestone receipts,
not in this ledger.

Usage:
  python tools/build_ledger.py             # regenerate docs/control/build_ledger.json
  python tools/build_ledger.py --verify    # regenerate to memory and compare (CI)
  python tools/build_ledger.py --status    # print partition summary
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTROL = ROOT / "docs" / "control"
RC3_BUNDLE = CONTROL / "rc3_effective_control_bundle.json"
RC4_BUNDLE = CONTROL / "rc4_control_bundle.json"
OVERRIDES = CONTROL / "build_ledger_overrides.json"
REVIEW = CONTROL / "build_ledger_review.v1.json"
REVIEW_V2 = CONTROL / "build_ledger_review.v2.json"
REVIEW_SUBJECT = CONTROL / "closure" / "predecessors" / "build_ledger.REVIEWED_V2.json"
LEDGER = CONTROL / "build_ledger.json"

LEDGER_VERSION = "CANDIDATE_V3"
REVIEW_SUBJECT_VERSION = "REVIEWED_V2"
REVIEW_SUBJECT_SHA256 = "78f6ce7254390997d54ce6732a46e138f24a56502677ba469dff22bf92f2b51e"

# CO-05 ledger-review rebinding. The v1 review binds only the frozen REVIEWED_V2 subject and the
# v1 --verify compares only ID + milestone, so 94 rows whose `rule` field drifted
# (R8_DEFAULT -> R8_GOVERNANCE_CLOSURE) escaped re-review. The v2 review binds (a) the exact
# SHA-256 of the full CURRENT ledger bytes and (b) a per-row digest over every safety-significant
# field of each row; --verify recomputes and compares both. Mutating any single row field without a
# fresh (re-pinned) v2 review changes a digest and fails the build.
REVIEW_V2_VERSION = "build-ledger-review.v2"
# The safety-significant fields of a ledger row. The per-row digest is taken over the WHOLE row
# (sorted keys), which is a superset of these — so a mutation to any field, named here or not,
# changes the digest. This tuple documents the exact set the current ledger rows carry; --verify
# fails closed if a row's key set ever differs from it (an added/removed field is itself a change
# that must be re-reviewed).
REVIEW_V2_SAFETY_SIGNIFICANT_FIELDS = (
    "id", "source", "row_class", "gate", "phase", "node",
    "milestone", "exec_class", "rule", "status",
)
REVIEW_V2_ROW_DIGEST_ALGORITHM = (
    "sha256(json.dumps(row, sort_keys=True, separators=(',', ':')))"
)

# Allowed override destinations (in-repo milestones + named non-repo lanes). An override may not
# invent a lane outside this closed set (B00R-D05 / SRC-004).
ALLOWED_OVERRIDE_MILESTONES = {f"B{i:02d}" for i in range(10)} | {
    "ESTATE", "OPERATOR", "RESEARCH", "ACTIVATION",
}


class LedgerClassificationError(Exception):
    """A source task matched no classification rule and no reviewed override (fail closed).

    B00R-D05: the old ``R8_DEFAULT -> B00`` silently swept every unmatched row into governance.
    Unknown work now refuses by a named error; a legitimately new/edge row is placed only by an
    explicit, unique, source-bound, reviewed, reasoned override in
    ``docs/control/build_ledger_overrides.json``.
    """

# Non-repo lanes.
ESTATE = "ESTATE"          # owned by another Triad repo / the live estate
OPERATOR = "OPERATOR"      # owner/governance ceremony or on-box act
RESEARCH = "RESEARCH"      # blocked on a named research decision
ACTIVATION = "ACTIVATION"  # blocked on ratified activation values (stays fail-closed)

ESTATE_NODES = {
    "E00 venue adapters", "E00 normalizer", "E01", "E07", "E08",
    "E08 reservation ledger", "E09", "E09 orchestrator", "E10", "VGP/OMS",
    "VGP fill recorder", "Venue & ingress", "Topics", "Processes",
    "Repositories", "Deployment & operations", "Deprecations",
    "Storage & data", "Security & access", "Platform", "Security", "Data",
}

ORIGIN_NODE_MILESTONE = {
    "ORIGIN feature primitives": "B03",
    "ORIGIN structure registry": "B03",
    "ORIGIN lifecycle reducer": "B04",
    "ORIGIN capsule host": "B06",
    "ORIGIN modules": "B06",
    "ORIGIN": "B06",
    "Contracts": "B01",
    "Edge comparator": "B07",
    "Frozen legacy bridge": "B07",
    "Authority router": "B07",
    "Configuration": "B07",
    "MCP & evidence UI": "B08",
    "Observability": "B08",
    "Tests & evidence": "B09",
    "Validation": "B09",
    "Governance": "B00",
    "Cross-cutting": "B00",
}

GATE_MILESTONE = {
    "G-1": OPERATOR, "G0": "B01", "G1": "B02", "G2": "B04", "G3": "B06",
    "G4": "B07", "G5": "B08", "G6": ESTATE, "G7": OPERATOR, "G8": OPERATOR,
    "G9": OPERATOR,
}

# Effective-bundle formula ids are F00..F23 (F00 tick/step … F23 campaign PnL).
FORMULA_MILESTONE = {
    "F00": "B02",
    # F01 finalized bars and F07 UTC session levels are E01-owned (alignment audit
    # P0): ORIGIN consumes/validates only — implementation rows are estate lane.
    "F01": ESTATE, "F07": ESTATE,
    "F02": "B03", "F03": "B03", "F04": "B03", "F05": "B03",
    "F06": "B03", "F08": "B03", "F09": "B03",
    "F10": "B04", "F11": "B04", "F12": "B04", "F13": "B04",
    "F15": "B04", "F16": "B04", "F17": "B04",
    "F14": "B06", "F18": "B06", "F19": "B06",
    # Estate-owned economics (G6): contracts + golden vectors only in this repo.
    "F20": "B09", "F21": "B09", "F22": "B09", "F23": "B09",
}
FORMULA_IDS = tuple(f"F{number:02d}" for number in range(24))
FORMULA_TASK_IDS = frozenset(
    f"FORM-{formula_id}-{ordinal:02d}"
    for formula_id in FORMULA_IDS
    for ordinal in range(1, 8)
)
FORMULA_TASK_ID_RE = re.compile(r"FORM-(F(?:0[0-9]|1[0-9]|2[0-3]))-(0[1-7])\Z")

WIRING_MILESTONE = {
    "W03": "B03", "W04": "B03", "W05": "B04", "W06": "B06",
    "W07": "B07", "W08": "B07", "W08A": "B07", "W09": "B07",
    "W22": "B02", "W23": "B08", "W24": "B02", "W25": "B08",
}

RC4_GATE_MILESTONE = {
    "L0": "B05", "L1": ESTATE, "L2": "B05", "L3": "B05",
    "L4": "B05", "L5": "B05", "L6": "B08", "L7": ESTATE,
}

PARAM_STATUS_LANE = {
    "BLOCKING_OWNER_DECISION": ACTIVATION,
    "BLOCKING_RESEARCH_DECISION": RESEARCH,
}


def _formula_key(task: dict) -> str | None:
    refs = str(task.get("formula_refs") or "")
    for token in refs.replace(";", ",").split(","):
        token = token.strip()
        if token.startswith("F") and token[1:3].isdigit():
            return token[:3]
    return None


def _wiring_key(task: dict) -> str | None:
    refs = str(task.get("wiring_refs") or "")
    for token in refs.replace(";", ",").split(","):
        token = token.strip()
        if token.startswith("W08A"):
            return "W08A"
        if token.startswith("W") and token[1:3].isdigit():
            return token[:3]
    return None


_ESTATE_HINTS = (
    "E09", "VGP", "venue session", "venue credential", "credential", "E07", "E08",
    "E10", "executor", "keyholder", "listen key", "live account",
)


def classify_rc3(task: dict) -> tuple[str, str, str]:
    """Return (milestone_or_lane, exec_class, rule_id) for an RC3 effective task."""
    row_class = task.get("row_class", "")
    node = task.get("node", "")
    gate = task.get("gate", "")
    phase = task.get("phase", "")

    if row_class == "GATE_CONTROL":
        target = GATE_MILESTONE.get(gate, OPERATOR)
        lane = "GOVERNANCE_RECEIPT" if target in (OPERATOR, ESTATE) else "IN_REPO_GATE"
        return target, lane, "R1_GATE"

    if row_class == "PARAMETER_DECLARATION":
        status = task.get("truth_state", "")
        # Parameter registry rows materialize with the signed config artifacts.
        return "B07", "IN_REPO_CONFIG", "R5_PARAM"

    if row_class == "FORMULA_ATOMIC":
        key = _formula_key(task)
        match = FORMULA_TASK_ID_RE.fullmatch(str(task.get("id", "")))
        if match is None or key != match.group(1) or key not in FORMULA_MILESTONE:
            raise LedgerClassificationError(
                f"FORMULA_NAMESPACE_INVALID {task.get('id')!r}: expected exact FORM-F00..F23-01..07 "
                f"with matching formula_refs, got {key!r}")
        m = FORMULA_MILESTONE[key]
        if m == ESTATE:
            return m, "ESTATE_FORMULA", "R3_FORMULA_ESTATE"
        lane = "IN_REPO_CODE" if m not in ("B09",) else "IN_REPO_CATALOG"
        return m, lane, "R3_FORMULA"

    if row_class == "WIRING_ATOMIC":
        key = _wiring_key(task)
        if key and key in WIRING_MILESTONE:
            return WIRING_MILESTONE[key], "IN_REPO_CODE", "R4_WIRING"
        return ESTATE, "ESTATE_WIRING", "R4_WIRING_ESTATE"

    if node == "Research":
        return RESEARCH, "RESEARCH_PROGRAM", "R6_RESEARCH"

    if node in ESTATE_NODES:
        return ESTATE, "ESTATE_NODE", "R6_ESTATE_NODE"

    if node in ORIGIN_NODE_MILESTONE:
        return ORIGIN_NODE_MILESTONE[node], "IN_REPO_CODE", "R6_NODE"

    if phase in ("P6", "P7", "P8", "P9"):
        return OPERATOR, "LIVE_STAGE", "R7_LATE_PHASE"

    # Program-wide governance/scope-closure/overlay-control rows are owned at the governance
    # milestone. This is an EXPLICIT, enumerated named rule (not the old anonymous B00 default):
    # each class below was reviewed to B00 at B00C; a truly unknown row_class now falls through to
    # the fail-closed raise below rather than being swept into B00 (B00R-D05).
    GOVERNANCE_CLOSURE_CLASSES = (
        "GAP_CLOSURE",              # cross-cutting gap-closure controls
        "RC1_SCOPE_CLOSURE",        # baseline scope-closure (SCP-*) controls
        "ATOMIC_RC3_OVERLAY_CONTROL",  # e.g. the G0 reproducible-source-bundle overlay control
    )
    if row_class in GOVERNANCE_CLOSURE_CLASSES:
        return "B00", "IN_REPO_GOVERNANCE", "R8_GOVERNANCE_CLOSURE"

    raise LedgerClassificationError(
        f"UNCLASSIFIED_TASK {task.get('id')!r}: row_class={row_class!r} node={node!r} "
        f"gate={gate!r} phase={phase!r} — no rule matched and no reviewed override exists; "
        "add an explicit reviewed source-bound override in "
        "docs/control/build_ledger_overrides.json (no B00 fallback).")


def classify_rc4(task: dict) -> tuple[str, str, str]:
    gate = task.get("gate", "")
    text = (str(task.get("instruction", "")) + " " + str(task.get("domain", ""))).lower()
    if gate not in RC4_GATE_MILESTONE:
        raise LedgerClassificationError(
            f"UNCLASSIFIED_LEVER {task.get('id')!r}: gate={gate!r} is not a known lever gate "
            "(L0..L7); no B05 fallback — add the gate mapping or a reviewed override.")
    target = RC4_GATE_MILESTONE[gate]
    if target not in (ESTATE, OPERATOR):
        if any(h.lower() in text for h in _ESTATE_HINTS):
            return ESTATE, "ESTATE_LEVER", "L2_ESTATE_HINT"
        return target, "IN_REPO_CODE", "L1_GATE"
    return target, "ESTATE_LEVER" if target == ESTATE else "LIVE_STAGE", "L1_GATE"


# --------------------------------------------------------------------------------------------------
# CO-05: ledger-review rebinding (make a stale review impossible)
# --------------------------------------------------------------------------------------------------

def row_digest(row: dict) -> str:
    """SHA-256 over the whole row (sorted keys, compact separators).

    Deterministic and independent of dict insertion order. Covers every field of the row — a
    superset of ``REVIEW_V2_SAFETY_SIGNIFICANT_FIELDS`` — so mutating any single field changes it.
    """
    return hashlib.sha256(
        json.dumps(row, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def compute_row_digests(ledger: dict) -> dict[str, str]:
    """Map of ``id -> row_digest`` for every ledger row (sorted by id)."""
    return {
        row["id"]: row_digest(row)
        for row in sorted(ledger["tasks"], key=lambda r: r["id"])
    }


def verify_review_v2(ledger_bytes: bytes, ledger: dict, review_v2: dict) -> list[str]:
    """Pure check that a v2 review artifact binds the given ledger.

    Returns a (possibly empty) list of problem strings. Empty means the binding holds: the review's
    full-bytes digest equals the SHA-256 of ``ledger_bytes``, and its per-row digest map equals the
    per-row digests recomputed from ``ledger``. This is the CO-05 assertion layer; it never inspects
    the re-review dispositions (those are owner content — see ``build_review_v2``), only the digest
    binding. Any mismatch is a defect the caller turns into a failing exit.
    """
    problems: list[str] = []

    if review_v2.get("review_version") != REVIEW_V2_VERSION:
        problems.append(
            f"v2 review does not declare review_version {REVIEW_V2_VERSION!r} "
            f"(got {review_v2.get('review_version')!r})")
    if not review_v2.get("reviewer"):
        problems.append("v2 review carries no reviewer/generator identity")
    if review_v2.get("ledger_version") != ledger.get("ledger_version"):
        problems.append(
            f"v2 review binds ledger_version {review_v2.get('ledger_version')!r} "
            f"but current ledger is {ledger.get('ledger_version')!r}")
    if review_v2.get("row_digest_algorithm") != REVIEW_V2_ROW_DIGEST_ALGORITHM:
        problems.append("v2 review declares an unexpected row_digest_algorithm")

    # (a) full-bytes digest of the current ledger.
    expected_full = review_v2.get("binds_ledger_sha256")
    actual_full = hashlib.sha256(ledger_bytes).hexdigest()
    if not expected_full:
        problems.append("v2 review does not bind a full-ledger sha256 (binds_ledger_sha256)")
    elif expected_full != actual_full:
        problems.append(
            f"v2 full-ledger digest mismatch: current {actual_full} "
            f"!= reviewed {expected_full} (the ledger changed without a fresh review)")

    # Fail closed if any row carries a field set other than the reviewed safety-significant set: an
    # added or removed field is itself an unreviewed change.
    expected_fields = set(REVIEW_V2_SAFETY_SIGNIFICANT_FIELDS)
    for row in ledger["tasks"]:
        if set(row) != expected_fields:
            problems.append(
                f"row {row.get('id')!r} field set {sorted(row)} differs from the reviewed "
                f"safety-significant field set {sorted(expected_fields)}")
            break

    # (b) per-row digests.
    reviewed = review_v2.get("row_digests", {})
    if not isinstance(reviewed, dict):
        problems.append("v2 review row_digests is not an object")
        reviewed = {}
    current = compute_row_digests(ledger)
    missing = sorted(set(current) - set(reviewed))
    extra = sorted(set(reviewed) - set(current))
    if missing:
        problems.append(f"v2 review omits row digests for current tasks: {missing[:5]}")
    if extra:
        problems.append(f"v2 review carries row digests for unknown tasks: {extra[:5]}")
    mismatched = sorted(
        rid for rid in (set(reviewed) & set(current)) if reviewed[rid] != current[rid]
    )
    if mismatched:
        problems.append(
            f"{len(mismatched)} row digest(s) mismatch — a safety-significant field changed "
            f"without a fresh review: {mismatched[:5]}")

    return problems


def build_review_v2(ledger_bytes: bytes, ledger: dict, subject: dict,
                    reviewer: str, reviewed_at: str, review_basis: str) -> dict:
    """Regenerate the v2 review artifact from the CURRENT ledger and the frozen REVIEWED_V2 subject.

    The digests are mechanical (derived from the current ledger bytes/rows). The drift change-log is
    the exact per-field diff of every row that changed since REVIEWED_V2; each drifted row's
    disposition is ``REVIEW_PENDING`` — the fresh full-row re-review of those rows is owner/reviewer
    judgment, not agent content, so it is documented and left honestly pending. Deterministic: no
    wall clock, sorted output.
    """
    subject_rows = {row["id"]: row for row in subject.get("tasks", [])}
    current_rows = {row["id"]: row for row in ledger["tasks"]}
    change_log = []
    for rid in sorted(current_rows):
        cur = current_rows[rid]
        sub = subject_rows.get(rid)
        if sub is None:
            change_log.append({
                "id": rid,
                "kind": "ROW_ABSENT_IN_REVIEWED_V2",
                "changed_fields": [],
                "disposition": "REVIEW_PENDING",
            })
            continue
        changed_fields = [
            {
                "field": field,
                "reviewed_v2_value": sub.get(field),
                "current_v3_value": cur.get(field),
            }
            for field in sorted(set(cur) | set(sub))
            if cur.get(field) != sub.get(field)
        ]
        if changed_fields:
            change_log.append({
                "id": rid,
                "kind": "ROW_FIELD_DRIFT",
                "changed_fields": changed_fields,
                "disposition": "REVIEW_PENDING",
            })
    return {
        "review_version": REVIEW_V2_VERSION,
        "supersedes": "build-ledger-review.v1",
        "ledger_version": ledger.get("ledger_version"),
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "review_basis": review_basis,
        "binding_disposition": "MECHANICAL_DIGEST_BOUND",
        "row_rereview_disposition": "REVIEW_PENDING",
        "note": (
            "The full-bytes and per-row digest binding is mechanically authenticated and enforced "
            "by build_ledger.py --verify. The re-review dispositions for the rows that drifted from "
            "REVIEWED_V2 are REVIEW_PENDING and require owner/reviewer judgment; the exact drift is "
            "documented in drift_from_reviewed_v2.change_log."),
        "binds_ledger_sha256": hashlib.sha256(ledger_bytes).hexdigest(),
        "row_digest_algorithm": REVIEW_V2_ROW_DIGEST_ALGORITHM,
        "safety_significant_fields": list(REVIEW_V2_SAFETY_SIGNIFICANT_FIELDS),
        "row_count": len(current_rows),
        "row_digests": compute_row_digests(ledger),
        "drift_from_reviewed_v2": {
            "predecessor_subject": "docs/control/closure/predecessors/build_ledger.REVIEWED_V2.json",
            "predecessor_subject_sha256": REVIEW_SUBJECT_SHA256,
            "changed_row_count": len(change_log),
            "dispositions_state": "REVIEW_PENDING",
            "change_log": change_log,
        },
    }


def build() -> dict:
    rc3 = json.loads(RC3_BUNDLE.read_text())
    rc4 = json.loads(RC4_BUNDLE.read_text())
    declared_formula_ids = tuple(sorted(row.get("id") for row in rc3.get("formulas", [])))
    if declared_formula_ids != FORMULA_IDS:
        raise LedgerClassificationError(
            f"FORMULA_REGISTRY_INVALID: expected {FORMULA_IDS!r}, got {declared_formula_ids!r}")
    source_formula_task_ids = {
        str(task.get("id")) for task in rc3.get("tasks", [])
        if task.get("row_class") == "FORMULA_ATOMIC"
    }
    if source_formula_task_ids != FORMULA_TASK_IDS:
        missing = sorted(FORMULA_TASK_IDS - source_formula_task_ids)
        extra = sorted(source_formula_task_ids - FORMULA_TASK_IDS)
        raise LedgerClassificationError(
            f"FORMULA_TASK_SET_INVALID: missing={missing[:5]!r} extra={extra[:5]!r}")
    overrides: dict[str, dict] = {}
    if OVERRIDES.exists():
        overrides = json.loads(OVERRIDES.read_text()).get("overrides", {})

    rows = []
    for task in rc3["tasks"]:
        milestone, lane, rule = classify_rc3(task)
        rows.append({
            "id": task["id"],
            "source": "RC3_EFFECTIVE",
            "row_class": task.get("row_class", ""),
            "gate": task.get("gate", ""),
            "phase": task.get("phase", ""),
            "node": task.get("node", ""),
            "milestone": milestone,
            "exec_class": lane,
            "rule": rule,
            "status": "NOT_STARTED",
        })
    for task in rc4["tasks"]:
        milestone, lane, rule = classify_rc4(task)
        rows.append({
            "id": task["id"],
            "source": "RC4_ADDENDUM",
            "row_class": "LEVER",
            "gate": task.get("gate", ""),
            "phase": "",
            "node": task.get("domain", ""),
            "milestone": milestone,
            "exec_class": lane,
            "rule": rule,
            "status": "NOT_STARTED",
        })

    # Override validation (B00R SRC-004): every override must be explicit, unique, source-bound,
    # reviewed, reasoned, and limited to an allowed destination. An override for an unknown task id
    # fails closed rather than being silently ignored.
    row_ids = {row["id"] for row in rows}
    for oid, patch in overrides.items():
        if oid not in row_ids:
            raise LedgerClassificationError(
                f"OVERRIDE_FOR_UNKNOWN_TASK {oid!r}: no source task with this id")
        if not isinstance(patch, dict):
            raise LedgerClassificationError(f"OVERRIDE_MALFORMED {oid!r}: not an object")
        if not patch.get("reviewer") or not patch.get("reason"):
            raise LedgerClassificationError(
                f"OVERRIDE_UNREVIEWED {oid!r}: must carry a reviewer identity and a reason")
        if "milestone" in patch and patch["milestone"] not in ALLOWED_OVERRIDE_MILESTONES:
            raise LedgerClassificationError(
                f"OVERRIDE_BAD_DESTINATION {oid!r}: milestone {patch['milestone']!r} "
                f"is not an allowed lane")

    seen = set()
    for row in rows:
        if row["id"] in seen:
            raise SystemExit(f"duplicate task id in bundles: {row['id']}")
        seen.add(row["id"])
        if row["id"] in overrides:
            patch = overrides[row["id"]]
            for key in ("milestone", "exec_class", "status"):
                if key in patch:
                    row[key] = patch[key]
            row["rule"] = "OVERRIDE"

    rows.sort(key=lambda r: (r["source"], r["id"]))
    summary: dict[str, int] = {}
    for row in rows:
        summary[row["milestone"]] = summary.get(row["milestone"], 0) + 1
    return {
        "ledger_version": LEDGER_VERSION,
        "task_count": len(rows),
        "milestone_counts": dict(sorted(summary.items())),
        "tasks": rows,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument(
        "--emit-review-v2", action="store_true",
        help="regenerate docs/control/build_ledger_review.v2.json (CO-05 digest-binding review) "
             "from the current ledger and the frozen REVIEWED_V2 subject; dispositions stay "
             "REVIEW_PENDING (owner content)")
    parser.add_argument(
        "--review", metavar="PREVIOUS_LEDGER",
        help="refused: the historical REVIEWED_V2 review artifact is immutable")
    args = parser.parse_args(argv)

    if args.review:
        print(
            "FAIL: build_ledger_review.v1.json is the immutable historical REVIEWED_V2 review; "
            "a current candidate review requires a new independently authenticated artifact",
            file=sys.stderr,
        )
        return 2

    ledger = build()
    rendered = json.dumps(ledger, indent=1, sort_keys=True) + "\n"

    if args.status:
        print(f"build ledger {ledger['ledger_version']}: {ledger['task_count']} tasks")
        for milestone, count in ledger["milestone_counts"].items():
            print(f"  {milestone}: {count}")
        return 0

    if args.emit_review_v2:
        if LEDGER.read_text() != rendered:
            print("FAIL: regenerate docs/control/build_ledger.json first "
                  "(python tools/build_ledger.py) before emitting the v2 review",
                  file=sys.stderr)
            return 1
        if not REVIEW_SUBJECT.exists():
            print("FAIL: frozen REVIEWED_V2 review subject missing", file=sys.stderr)
            return 1
        subject = json.loads(REVIEW_SUBJECT.read_bytes())
        review_v2 = build_review_v2(
            LEDGER.read_bytes(), ledger, subject,
            reviewer="co05-ledger-review-rebinding-session",
            reviewed_at="2026-08-12",
            review_basis=(
                "CO-05 ledger review rebinding: the v2 review binds the exact SHA-256 of the full "
                "current CANDIDATE_V3 ledger bytes plus a per-row digest over every safety-"
                "significant field of each row; --verify recomputes and compares both. Digests are "
                "mechanical; the re-review dispositions for the rows that drifted from REVIEWED_V2 "
                "are REVIEW_PENDING (owner/reviewer judgment)."),
        )
        REVIEW_V2.write_text(json.dumps(review_v2, indent=1, sort_keys=True) + "\n")
        drift = review_v2["drift_from_reviewed_v2"]["changed_row_count"]
        print(f"wrote {REVIEW_V2} ({review_v2['row_count']} row digests; "
              f"{drift} rows drifted from REVIEWED_V2, dispositions REVIEW_PENDING)")
        return 0

    if args.verify:
        if not LEDGER.exists():
            print("FAIL: docs/control/build_ledger.json missing", file=sys.stderr)
            return 1
        if LEDGER.read_text() != rendered:
            print("FAIL: build ledger is stale; run python tools/build_ledger.py", file=sys.stderr)
            return 1
        if not REVIEW.exists():
            print("FAIL: row-level review record missing "
                  "(docs/control/build_ledger_review.v1.json)", file=sys.stderr)
            return 1
        if not REVIEW_SUBJECT.exists():
            print("FAIL: frozen REVIEWED_V2 review subject missing "
                  "(docs/control/closure/predecessors/build_ledger.REVIEWED_V2.json)",
                  file=sys.stderr)
            return 1
        subject_bytes = REVIEW_SUBJECT.read_bytes()
        subject_sha256 = hashlib.sha256(subject_bytes).hexdigest()
        if subject_sha256 != REVIEW_SUBJECT_SHA256:
            print("FAIL: frozen REVIEWED_V2 review subject byte digest mismatch: "
                  f"{subject_sha256} != {REVIEW_SUBJECT_SHA256}", file=sys.stderr)
            return 1
        subject = json.loads(subject_bytes)
        review = json.loads(REVIEW.read_text())
        reviewed = {row["id"]: row for row in review.get("rows", [])}
        if not review.get("reviewer"):
            print("FAIL: review record carries no reviewer identity", file=sys.stderr)
            return 1
        if subject.get("ledger_version") != REVIEW_SUBJECT_VERSION:
            print("FAIL: frozen review subject is not REVIEWED_V2", file=sys.stderr)
            return 1
        if review.get("ledger_version") != REVIEW_SUBJECT_VERSION:
            print("FAIL: review record does not bind REVIEWED_V2", file=sys.stderr)
            return 1
        subject_rows = {row["id"]: row for row in subject.get("tasks", [])}
        current_rows = {row["id"]: row for row in ledger["tasks"]}
        problems = []
        if len(subject_rows) != 1250 or set(subject_rows) != set(current_rows):
            problems.append("frozen review subject task IDs differ from current candidate")
        for row in subject.get("tasks", []):
            rrow = reviewed.get(row["id"])
            if rrow is None:
                problems.append(f"historical review omits subject task {row['id']}")
            elif rrow["milestone"] != row["milestone"]:
                problems.append(
                    f"historical review disagrees with REVIEWED_V2 for {row['id']}: "
                    f"{rrow['milestone']} != {row['milestone']}")
        extra = set(reviewed) - set(subject_rows)
        if extra:
            problems.append(f"historical review rows for unknown subject tasks: {sorted(extra)[:5]}")
        if problems:
            for problem in problems[:10]:
                print(f"FAIL: {problem}", file=sys.stderr)
            print(f"FAIL: {len(problems)} review defects", file=sys.stderr)
            return 1
        changed_ids = sorted(
            task_id for task_id in current_rows
            if current_rows[task_id] != subject_rows[task_id]
        )
        unchanged = len(current_rows) - len(changed_ids)
        print(f"OK: build ledger {LEDGER_VERSION} structurally current "
              f"({ledger['task_count']} tasks); historical REVIEWED_V2 subject authenticated "
              f"({unchanged} unchanged rows; {len(changed_ids)} changed rows require review)")

        # CO-05: the NEW v2 digest-binding assertion layer (additive; the two OK lines above are
        # unchanged). The v1 checks above only compare ID + milestone, so a `rule`/`exec_class`/
        # etc. drift escapes them; the v2 review binds the full-bytes + per-row digests so any such
        # drift fails until a fresh (re-pinned) v2 review is issued.
        if not REVIEW_V2.exists():
            print("FAIL: v2 digest-binding review missing "
                  "(docs/control/build_ledger_review.v2.json); "
                  "run python tools/build_ledger.py --emit-review-v2", file=sys.stderr)
            return 1
        review_v2 = json.loads(REVIEW_V2.read_text())
        v2_problems = verify_review_v2(LEDGER.read_bytes(), ledger, review_v2)
        if v2_problems:
            for problem in v2_problems[:10]:
                print(f"FAIL: {problem}", file=sys.stderr)
            print(f"FAIL: {len(v2_problems)} v2 review-binding defects", file=sys.stderr)
            return 1
        drift = review_v2.get("drift_from_reviewed_v2", {})
        print(f"OK: build_ledger_review.v2 binding authenticated "
              f"(full-bytes + {review_v2.get('row_count')} per-row digests match current "
              f"{LEDGER_VERSION}; {drift.get('changed_row_count')} rows drifted from REVIEWED_V2, "
              f"dispositions {drift.get('dispositions_state')})")
        return 0

    LEDGER.write_text(rendered)
    print(f"wrote {LEDGER} ({ledger['task_count']} tasks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
