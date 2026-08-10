#!/usr/bin/env python3
"""Combined RC3+RC4 composition-DAG validator (B00C).

Validates the union of the RC3 effective control bundle (1,115 tasks / 2,249 dependency edges)
and the RC4 lever addendum bundle (135 tasks) together with the repository build ledger:

  1. **Referential closure** — every RC3 dependency endpoint names an existing RC3 task; every
     RC4 ``depends_on`` token names an existing RC4/RC3 task or a declared external root.
  2. **Cycle freedom** — the combined hard-dependency graph is acyclic.
  3. **One scheduling owner** — every bundle task appears in the build ledger exactly once
     (and the ledger contains no unknown tasks).
  4. **Source-authority preservation** — the ledger never rewrites a source task's gate,
     node/domain, or row class; scheduling metadata may add a milestone lane only.
  5. **Milestone inversions accounted** — a HARD edge whose predecessor is scheduled in a LATER
     repository milestone than its successor is a scheduling inversion. Every observed
     (pred_lane, succ_lane) pair must be covered by the reviewed table below, which names why
     the inversion is lawful (a bundle-authoritative dependency does not become false because
     scheduling metadata lands its repository artifact later — the successor row simply cannot
     CLAIM completion until the predecessor row completes, and row statuses live in the ledger,
     all ``NOT_STARTED`` until evidenced). An unlisted pair fails the run: new inversions are
     blocking until reviewed here.
  6. **Cross-lane blockers reported** — HARD edges from ESTATE/OPERATOR/RESEARCH/ACTIVATION
     lanes into B-lanes are counted and printed; they are the named external prerequisites and
     are never silently dropped.

Exit 0 only when every check passes. This tool validates composition/scheduling; it certifies
no gate and marks nothing complete.
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTROL = ROOT / "docs" / "control"

REVIEWER = "claude-fable-5-build-session/B00C"

# Declared external roots for RC4 depends_on tokens (not tasks in either bundle).
DECLARED_EXTERNAL_ROOTS = {
    "OWNER-DIRECTIVE-2026-08-09",
}

# Reviewed scheduling-inversion classes: (predecessor_lane, successor_lane) -> reason.
# A HARD bundle edge P -> S with milestone(P) after milestone(S) is lawful only if listed here.
ACCOUNTED_INVERSIONS = {
    # Gate-evaluation anchor rows (CTL-G*-03 "evaluate all required work") sit at the gate's
    # anchor milestone while contributing rows land across several later milestones; the gate
    # evaluation row cannot claim completion until every contributor row completes.
    ("B06", "B04"): "G2 evaluation anchored at B04 consumes F14/capsule-module closure rows "
                    "scheduled at B06; G2 cannot claim completion before they complete.",
    ("B07", "B04"): "G2 evaluation consumes parameter/config materialization rows scheduled "
                    "at B07 (declarations are vendored bundle data since B00).",
    ("B08", "B04"): "G2 evaluation consumes observability/read-face rows scheduled at B08.",
    ("B09", "B04"): "G2 evaluation consumes verification-consolidation rows scheduled at B09.",
    ("B07", "B06"): "G3 evaluation anchored at B06 consumes configuration/service rows "
                    "scheduled at B07.",
    ("B08", "B07"): "G4 evaluation anchored at B07 consumes read-face rows scheduled at B08.",
    ("B09", "B07"): "G4 evaluation anchored at B07 consumes test/evidence consolidation rows "
                    "scheduled at B09.",
    # Gate ENTRY confirmation rows precede work whose repository artifacts are scheduled in an
    # EARLIER milestone than the gate's anchor (the gate entry is confirmed retrospectively over
    # already-landed work; the bundle edge direction is authoritative and preserved).
    ("B04", "B03"): "CTL-G2-01 entry confirmation (anchored B04) precedes W03/W04/F02+ rows "
                    "scheduled at B03; entry is confirmed over already-landed artifacts.",
    # G0 gate-control rows anchored at B01 consume declarations/materializations scheduled
    # later; the declarations exist as vendored bundle data from B00.
    ("B02", "B01"): "G0 evaluation consumes kernel rows scheduled at B02.",
    ("B07", "B01"): "G0 evaluation consumes parameter-declaration materialization rows "
                    "scheduled at B07 (declared data vendored at B00).",
    ("B08", "B01"): "G0 evaluation consumes an observability row scheduled at B08.",
    ("B06", "B01"): "G0 evaluation consumes a capsule-scope closure row scheduled at B06.",
    ("B07", "B02"): "G1 evaluation anchored at B02 consumes configuration rows scheduled "
                    "at B07.",
    # B00 governance/cross-cutting rows are program-wide controls whose completion accrues over
    # the whole build; they depend on implementation rows from later milestones by design.
    ("B01", "B00"): "Program-wide governance rows (B00 home) depend on B01 contract rows.",
    ("B02", "B00"): "Program-wide governance rows depend on B02 kernel rows.",
    ("B04", "B00"): "Program-wide governance rows depend on B04 structure rows.",
    ("B06", "B00"): "Program-wide governance rows depend on B06 capsule/candidate rows.",
    ("B07", "B00"): "Program-wide governance rows depend on B07 config/service rows.",
    ("B08", "B00"): "Program-wide governance rows depend on B08 read-face rows.",
}

B_ORDER = {f"B{i:02d}": i for i in range(10)}


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)


def main() -> int:
    rc3 = json.loads((CONTROL / "rc3_effective_control_bundle.json").read_text())
    rc4 = json.loads((CONTROL / "rc4_control_bundle.json").read_text())
    ledger = json.loads((CONTROL / "build_ledger.json").read_text())

    rc3_tasks = {t["id"]: t for t in rc3["tasks"]}
    rc4_tasks = {t["id"]: t for t in rc4["tasks"]}
    all_ids = set(rc3_tasks) | set(rc4_tasks)
    problems = 0

    # 1 · Referential closure -----------------------------------------------------------------
    edges: list[tuple[str, str]] = []
    for dep in rc3["dependencies"]:
        pred, succ = dep["predecessor_task_id"], dep["successor_task_id"]
        for endpoint in (pred, succ):
            if endpoint not in rc3_tasks:
                fail(f"RC3 dependency {dep['edge_id']} references unknown task {endpoint}")
                problems += 1
        if dep.get("hard_or_soft") == "HARD":
            edges.append((pred, succ))
    for task in rc4["tasks"]:
        for token in str(task.get("depends_on", "")).replace(";", ",").split(","):
            token = token.strip()
            if not token:
                continue
            if token in DECLARED_EXTERNAL_ROOTS:
                continue
            if token not in all_ids:
                fail(f"RC4 task {task['id']} depends on unknown token {token!r}")
                problems += 1
            else:
                edges.append((token, task["id"]))

    # 2 · Cycle freedom (Kahn over hard edges) ------------------------------------------------
    indegree: dict[str, int] = {tid: 0 for tid in all_ids}
    adjacency: dict[str, list[str]] = {tid: [] for tid in all_ids}
    for pred, succ in edges:
        if pred in indegree and succ in indegree:
            adjacency[pred].append(succ)
            indegree[succ] += 1
    queue = [tid for tid, deg in indegree.items() if deg == 0]
    visited = 0
    while queue:
        node = queue.pop()
        visited += 1
        for nxt in adjacency[node]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    if visited != len(all_ids):
        cyclic = sorted(tid for tid, deg in indegree.items() if deg > 0)
        fail(f"combined hard-dependency graph has a cycle involving {len(cyclic)} tasks "
             f"(e.g. {cyclic[:5]})")
        problems += 1

    # 3 · One scheduling owner ----------------------------------------------------------------
    ledger_rows = ledger["tasks"]
    ledger_ids = [row["id"] for row in ledger_rows]
    if len(ledger_ids) != len(set(ledger_ids)):
        fail("build ledger schedules a task more than once")
        problems += 1
    missing = all_ids - set(ledger_ids)
    unknown = set(ledger_ids) - all_ids
    if missing:
        fail(f"{len(missing)} bundle tasks lack a scheduling owner (e.g. {sorted(missing)[:5]})")
        problems += 1
    if unknown:
        fail(f"build ledger schedules {len(unknown)} unknown tasks (e.g. {sorted(unknown)[:5]})")
        problems += 1

    # 4 · Source-authority preservation -------------------------------------------------------
    # The ledger may add a milestone lane and an exec class; it may NOT rewrite a source task's
    # authority fields. For RC3 rows the ledger preserves gate, node, row_class, and phase verbatim;
    # for RC4 lever rows the scheduling convention stamps row_class="LEVER"/phase="" (the source
    # lever carries neither), and the domain stands in for node (B00R-D10 / SRC-006).
    for row in ledger_rows:
        from_rc3 = row["id"] in rc3_tasks
        source = rc3_tasks.get(row["id"]) or rc4_tasks.get(row["id"])
        if source is None:
            continue  # reported above
        source_gate = source.get("gate", "")
        source_node = source.get("node", source.get("domain", ""))
        if row.get("gate", "") != source_gate:
            fail(f"ledger rewrote gate for {row['id']}: {row.get('gate')!r} != {source_gate!r}")
            problems += 1
        if row.get("node", "") != source_node:
            fail(f"ledger rewrote node for {row['id']}: {row.get('node')!r} != {source_node!r}")
            problems += 1
        if from_rc3:
            source_row_class = source.get("row_class", "")
            source_phase = source.get("phase", "")
            if row.get("row_class", "") != source_row_class:
                fail(f"ledger rewrote row_class for {row['id']}: "
                     f"{row.get('row_class')!r} != {source_row_class!r}")
                problems += 1
            if row.get("phase", "") != source_phase:
                fail(f"ledger rewrote phase for {row['id']}: "
                     f"{row.get('phase')!r} != {source_phase!r}")
                problems += 1
        else:
            if row.get("row_class", "") != "LEVER":
                fail(f"RC4 lever row {row['id']} lost its LEVER row_class: "
                     f"{row.get('row_class')!r}")
                problems += 1

    # 5 · Milestone inversions accounted ------------------------------------------------------
    lane = {row["id"]: row["milestone"] for row in ledger_rows}
    observed: dict[tuple[str, str], int] = {}
    cross_lane = 0
    for pred, succ in edges:
        pred_lane, succ_lane = lane.get(pred), lane.get(succ)
        if pred_lane is None or succ_lane is None:
            continue
        pred_b, succ_b = B_ORDER.get(pred_lane), B_ORDER.get(succ_lane)
        if pred_b is not None and succ_b is not None:
            if pred_b > succ_b:
                observed[(pred_lane, succ_lane)] = observed.get((pred_lane, succ_lane), 0) + 1
        elif succ_b is not None:
            cross_lane += 1
    unaccounted = sorted(set(observed) - set(ACCOUNTED_INVERSIONS))
    if unaccounted:
        for pair in unaccounted:
            fail(f"unreviewed milestone inversion {pair[0]} -> {pair[1]} "
                 f"({observed[pair]} hard edges) — add a reviewed row or re-lane")
        problems += len(unaccounted)
    stale = sorted(set(ACCOUNTED_INVERSIONS) - set(observed))

    if problems:
        fail(f"{problems} composition defects")
        return 1

    inversion_edges = sum(observed.values())
    print(f"OK: combined DAG valid — {len(all_ids)} tasks, {len(edges)} hard edges, no cycles, "
          f"one scheduling owner each, source authority preserved")
    print(f"    {inversion_edges} hard edges across {len(observed)} reviewed inversion classes "
          f"(reviewer: {REVIEWER}); {cross_lane} cross-lane blocker edges into B-lanes")
    if stale:
        print(f"    note: {len(stale)} accounted inversion classes no longer observed: {stale}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
