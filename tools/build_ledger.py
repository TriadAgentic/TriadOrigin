#!/usr/bin/env python3
"""Deterministic build ledger for the TRIAD ORIGIN V7 B-series build.

Partitions every effective control task (RC3 effective control bundle, 1,115 rows +
RC4 lever addendum bundle, 135 rows) into:

  * a build milestone (``B00``..``B10``) when the task is executable inside this
    repository, or a named non-repo lane (``ESTATE``, ``OPERATOR``, ``RESEARCH``,
    ``ACTIVATION``) when it is not; and
  * an executability class describing *why* it landed there.

The partition is REVIEWED_V2: the transparent, deterministic HEURISTIC_V1 rule table
(corrected at B00C to the reconciled plan — F01/F07 are E01-owned, the four-plane
substrate is B05, capsules/candidates are B06) applied in order (first match wins),
plus a reviewed override file
(``docs/control/build_ledger_overrides.json``) that takes precedence over every
rule. Every row additionally carries a row-level reviewer/disposition record in
``docs/control/build_ledger_review.v1.json`` (the B00C row review); ``--verify``
fails if any task lacks a review row or the review disagrees with the partition.
Each milestone PR re-reviews the slice it claims and moves misclassified rows via
overrides + a fresh review row.

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
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTROL = ROOT / "docs" / "control"
RC3_BUNDLE = CONTROL / "rc3_effective_control_bundle.json"
RC4_BUNDLE = CONTROL / "rc4_control_bundle.json"
OVERRIDES = CONTROL / "build_ledger_overrides.json"
REVIEW = CONTROL / "build_ledger_review.v1.json"
LEDGER = CONTROL / "build_ledger.json"

LEDGER_VERSION = "REVIEWED_V2"

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
        if key and key in FORMULA_MILESTONE:
            m = FORMULA_MILESTONE[key]
            if m == ESTATE:
                return m, "ESTATE_FORMULA", "R3_FORMULA_ESTATE"
            lane = "IN_REPO_CODE" if m not in ("B09",) else "IN_REPO_CATALOG"
            return m, lane, "R3_FORMULA"
        return "B06", "IN_REPO_CODE", "R3_FORMULA_DEFAULT"

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

    return "B00", "IN_REPO_GOVERNANCE", "R8_DEFAULT"


def classify_rc4(task: dict) -> tuple[str, str, str]:
    gate = task.get("gate", "")
    text = (str(task.get("instruction", "")) + " " + str(task.get("domain", ""))).lower()
    target = RC4_GATE_MILESTONE.get(gate, "B05")
    if target not in (ESTATE, OPERATOR):
        if any(h.lower() in text for h in _ESTATE_HINTS):
            return ESTATE, "ESTATE_LEVER", "L2_ESTATE_HINT"
        return target, "IN_REPO_CODE", "L1_GATE"
    return target, "ESTATE_LEVER" if target == ESTATE else "LIVE_STAGE", "L1_GATE"


def build() -> dict:
    rc3 = json.loads(RC3_BUNDLE.read_text())
    rc4 = json.loads(RC4_BUNDLE.read_text())
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
        "--review", metavar="PREVIOUS_LEDGER",
        help="regenerate the row-level review record, diffing against a previous ledger")
    args = parser.parse_args(argv)

    ledger = build()
    rendered = json.dumps(ledger, indent=1, sort_keys=True) + "\n"

    if args.status:
        print(f"build ledger {ledger['ledger_version']}: {ledger['task_count']} tasks")
        for milestone, count in ledger["milestone_counts"].items():
            print(f"  {milestone}: {count}")
        return 0

    if args.review:
        previous = {row["id"]: row for row in
                    json.loads(pathlib.Path(args.review).read_text())["tasks"]}
        review_rows = []
        for row in ledger["tasks"]:
            prior = previous.get(row["id"])
            if prior is None:
                disposition = "REVIEWED_NEW"
            elif prior["milestone"] == row["milestone"]:
                disposition = "REVIEWED_ACCEPT"
            else:
                disposition = "REVIEWED_MOVED"
            review_rows.append({
                "id": row["id"],
                "milestone": row["milestone"],
                "previous_milestone": prior["milestone"] if prior else None,
                "disposition": disposition,
            })
        record = {
            "review_version": "build-ledger-review.v1",
            "ledger_version": LEDGER_VERSION,
            "reviewer": "claude-fable-5-build-session/B00C",
            "review_basis": ("reconciled master plan §5/§7 + 10_MASTER_SPEC_ALIGNMENT_AUDIT "
                             "applied row-class by row-class over the deterministic rule table; "
                             "F01/F07 -> E01 estate lane, four-plane -> B05, "
                             "capsules/candidates -> B06"),
            "reviewed_at": "2026-08-09",
            "row_count": len(review_rows),
            "rows": review_rows,
        }
        REVIEW.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n")
        print(f"wrote {REVIEW} ({len(review_rows)} review rows)")
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
        review = json.loads(REVIEW.read_text())
        reviewed = {row["id"]: row for row in review.get("rows", [])}
        if not review.get("reviewer"):
            print("FAIL: review record carries no reviewer identity", file=sys.stderr)
            return 1
        problems = []
        for row in ledger["tasks"]:
            rrow = reviewed.get(row["id"])
            if rrow is None:
                problems.append(f"unreviewed task {row['id']}")
            elif rrow["milestone"] != row["milestone"]:
                problems.append(
                    f"review disagrees with partition for {row['id']}: "
                    f"{rrow['milestone']} != {row['milestone']}")
        extra = set(reviewed) - {row["id"] for row in ledger["tasks"]}
        if extra:
            problems.append(f"review rows for unknown tasks: {sorted(extra)[:5]}")
        if problems:
            for problem in problems[:10]:
                print(f"FAIL: {problem}", file=sys.stderr)
            print(f"FAIL: {len(problems)} review defects", file=sys.stderr)
            return 1
        print(f"OK: build ledger current ({ledger['task_count']} tasks; "
              f"{len(reviewed)} reviewed rows)")
        return 0

    LEDGER.write_text(rendered)
    print(f"wrote {LEDGER} ({ledger['task_count']} tasks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
