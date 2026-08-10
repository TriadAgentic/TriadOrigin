#!/usr/bin/env python3
"""Deterministic conformance matrix for the TRIAD ORIGIN V7 B-series build.

The reconciled plan's verification law (``docs/plan/00_MASTER_PLAN.md`` §10) requires a
conformance view that *accounts for* every one of:

  * the 408 inherited RC1 tests (carried inside the RC3 effective bundle as the
    ``source == "RC1_408_PRESERVED"`` subset — NOT the disjoint 407-row
    ``RC1_SCOPE_CLOSURE`` suite, which is a different RC2-derived family), and
  * the 1,523 RC3 effective verifications, and
  * the 125 RC4 lever/four-plane/shadow fixtures,

"…each linked to task / acceptance criterion / gate / current result. Counts alone are
not evidence." This tool builds that row-level join. Every row is assigned EXACTLY ONE
status from the closed vocabulary ``{COVERED, BLOCKED, DEFERRED, OUT_OF_REPO}``, and the
status is DERIVED — never hand-set — from the bundle's own ownership + status fields plus
(when present) a curated repository test-evidence link. The bundle declares nothing green
by itself (all ``initial_status == "NOT_RUN"``); a ``COVERED`` status is therefore only
ever produced from an explicit evidence link, so today the matrix carries zero green rows.

Load-bearing law (``00_MASTER_PLAN.md`` §9.6 / ``10_MASTER_SPEC_ALIGNMENT_AUDIT.md``): a
mandatory verification may be BLOCKED but is NEVER named-deferred and counted green. The
generator fails loud rather than emit a matrix in which any row whose closure depends on a
blocked registry entry — a ``BLOCKING_OWNER_DECISION`` (8) / ``BLOCKING_RESEARCH_DECISION``
(3) / a ``BLOCKED_*`` formula (12) / a ``PROPOSED_RC2_MUST_RATIFY`` (123) or ``PROPOSED``
task (129) / a ``NORMATIVE_TARGET_NOT_IMPLEMENTED`` task (27) / a ``TARGET_NOT_PROVISIONED``
parameter (4) — carries ``COVERED``.

The estate money line (E07 decision · E08 risk/sizing/authorization · E09
command/order/fill/protection · E10 outcome, and the ``F20``..``F23`` estate formulas) is
foreign per ``docs/plan/02_TRACEABILITY.md``; its rows are ``OUT_OF_REPO`` catalog-only —
this tool imports no venue / order / risk / money-line capability to reach them.

Determinism / read-only law: stdlib only, no environment reads, no network, no wall clock,
repo root resolved from this file's own location (never the working directory). Canonical
bytes are ``json.dumps(obj, indent=1, sort_keys=True) + "\\n"`` — the build-ledger idiom.

Usage:
  python tools/conformance_matrix.py           # regenerate docs/control/conformance_matrix.v1.json
  python tools/conformance_matrix.py --verify   # regenerate to memory and byte-compare (CI/e2e)
  python tools/conformance_matrix.py --status    # print the status/population summary
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
# Optional, operator-curated evidence links (absent today ⇒ zero COVERED). Same optional
# posture as build_ledger's overrides file: adding it makes --verify demand a regenerate.
EVIDENCE_LINKS = CONTROL / "conformance_evidence_links.v1.json"
MATRIX = CONTROL / "conformance_matrix.v1.json"

SCHEMA = "triad.origin.conformance_matrix.v1"
MATRIX_VERSION = "CONFORMANCE_MATRIX_V1"

# Pinned totals, cited verbatim from the frozen audit runner v1.2.0 and
# tools/verify_spec_control_counts.py (EXPECTED_RC1/RC3/RC4). The matrix derives each count
# from the same bundle bytes and cross-checks it against these pins; any drift fails loud.
EXPECTED_RC1_408_PRESERVED = 408
EXPECTED_RC3_EFFECTIVE = 1523
EXPECTED_RC4_FIXTURES = 125

# Closed status vocabulary — every row carries exactly one.
STATUS_COVERED = "COVERED"        # ORIGIN-owned, not blocked, pinned by a real repo test id
STATUS_BLOCKED = "BLOCKED"        # closure depends on a blocked registry entry (never green)
STATUS_DEFERRED = "DEFERRED"      # in-scope ORIGIN row, owed — not proven, not green
STATUS_OUT_OF_REPO = "OUT_OF_REPO"  # foreign node / money line / estate formula — catalog only
STATUS_VOCABULARY = (STATUS_BLOCKED, STATUS_COVERED, STATUS_DEFERRED, STATUS_OUT_OF_REPO)

# Foreign (out-of-repo) node anchor. This is byte-identical to build_ledger.ESTATE_NODES;
# the subset drift-lock lives in tests/tools/test_conformance_matrix.py so the matrix never
# treats a build-ledger estate node as in-repo. ``_is_foreign_node`` is BROADER than this
# set: per CLAUDE.md / 02_TRACEABILITY the whole E00/E01/E07/E08/E09/E10 money line and the
# VGP keyholder are OUT_OF_REPO, including sub-nodes the explicit set does not enumerate
# ("E09 protection owner", "E09 reconciler", "E00", "VGP", and "Ea/Eb" compounds).
FOREIGN_NODES = frozenset({
    "E00 venue adapters", "E00 normalizer", "E01", "E07", "E08",
    "E08 reservation ledger", "E09", "E09 orchestrator", "E10", "VGP/OMS",
    "VGP fill recorder", "Venue & ingress", "Topics", "Processes",
    "Repositories", "Deployment & operations", "Deprecations",
    "Storage & data", "Security & access", "Platform", "Security", "Data",
})

# The money-line node codes: E00 venue adapters · E01 upstream (F01/F07, consumed not
# authored) · E07 decision · E08 risk/sizing/authorization · E09 command/order/fill/
# protection · E10 outcome — all OUT_OF_REPO per the repository-ownership law.
_MONEY_LINE_NODE_CODES = frozenset({"E00", "E01", "E07", "E08", "E09", "E10"})


def _is_foreign_node(node: object) -> bool:
    """A node is foreign (OUT_OF_REPO) if it is an estate anchor, a VGP keyholder node, or
    its leading node code is a money-line code (tolerant of "E09 protection owner" spacing
    and "E00/E09" compounds)."""
    name = str(node or "")
    if name in FOREIGN_NODES or name.startswith("VGP"):
        return True
    if not name:
        return False
    lead = name.split()[0].split("/")[0]
    return lead in _MONEY_LINE_NODE_CODES

# A parameter in one of these states blocks the closure of every row that depends on it.
BLOCKING_PARAM_STATUS = frozenset({
    "BLOCKING_OWNER_DECISION",       # 8 owner risk/canary decisions (PAR-070…PAR-121)
    "BLOCKING_RESEARCH_DECISION",    # 3 structure research decisions (RC3-PAR-STRUCT-00x)
    "PROPOSED_RC2_MUST_RATIFY",      # 123 DARK proposal-bundle params
    "TARGET_NOT_PROVISIONED",        # 4 JetStream infra params (PAR-149…PAR-152)
})
# A task in one of these truth states cannot be closed green.
BLOCKING_TASK_STATE = frozenset({
    "BLOCKED", "PROPOSED", "NORMATIVE_TARGET_NOT_IMPLEMENTED",
})

# The RC3 effective bundle enumerates exactly these 24 formulas (F00..F23). Asserting the
# registry equals this list is the "Assert no F24 exists" law (there is nothing past F23).
_EXPECTED_FORMULA_IDS = [f"F{i:02d}" for i in range(24)]


class MatrixError(RuntimeError):
    """The conformance matrix could not be honestly built."""


def _split_refs(value: object) -> list[str]:
    """Split a ``a;b, c`` ref string into stripped tokens (ordered, deduplicated-stable)."""
    tokens: list[str] = []
    for token in str(value or "").replace(";", ",").split(","):
        token = token.strip()
        if token and token not in tokens:
            tokens.append(token)
    return tokens


def _formula_keys(value: object) -> list[str]:
    keys: list[str] = []
    for token in _split_refs(value):
        if token[:1] == "F" and token[1:3].isdigit():
            key = token[:3]
            if key not in keys:
                keys.append(key)
    return keys


def load_json(path: pathlib.Path, label: str) -> dict:
    if not path.is_file():
        raise MatrixError(f"{label} missing at {path.as_posix()}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MatrixError(f"{label} unreadable/invalid at {path.as_posix()}: {exc}") from exc
    if not isinstance(data, dict):
        raise MatrixError(f"{label} root must be a JSON object")
    return data


def load_evidence_links(path: pathlib.Path = EVIDENCE_LINKS) -> dict[str, str]:
    """Read the optional curated evidence-link file → ``{row_id: pytest_node_id}``.

    Absent ⇒ an empty map ⇒ zero COVERED rows (today's honest, fail-closed posture). A
    present file must be a strict ``{"links": [{"id", "test_node_id"}]}`` object; a link
    with an empty id or node, or a duplicate id, is a refusal (no silent green).
    """
    if not path.is_file():
        return {}
    data = load_json(path, "conformance evidence links")
    links_raw = data.get("links")
    if not isinstance(links_raw, list):
        raise MatrixError("evidence links 'links' must be a JSON array")
    links: dict[str, str] = {}
    for entry in links_raw:
        if not isinstance(entry, dict):
            raise MatrixError("each evidence link must be a JSON object")
        row_id = str(entry.get("id") or "").strip()
        node_id = str(entry.get("test_node_id") or "").strip()
        if not row_id or not node_id:
            raise MatrixError(f"evidence link missing id/test_node_id: {entry!r}")
        if row_id in links:
            raise MatrixError(f"duplicate evidence link id {row_id!r}")
        links[row_id] = node_id
    return links


def derive_blockers(rc3: dict) -> dict[str, object]:
    """Enumerate the blocked registry entries the 'never counted green' law names."""
    params = {p["id"]: p for p in rc3["parameters"]}
    formulas = {f["id"]: f for f in rc3["formulas"]}
    tasks = {t["id"]: t for t in rc3["tasks"]}

    blocked_params = {
        pid for pid, p in params.items() if p.get("status") in BLOCKING_PARAM_STATUS
    }
    blocked_formulas = {
        fid for fid, f in formulas.items()
        if str(f.get("rc3_status") or "").startswith("BLOCKED")
    }

    def enumerate_params(status: str) -> list[str]:
        return sorted(pid for pid, p in params.items() if p.get("status") == status)

    return {
        "params": params,
        "formulas": formulas,
        "tasks": tasks,
        "blocked_params": blocked_params,
        "blocked_formulas": blocked_formulas,
        "blocking_owner_decision": enumerate_params("BLOCKING_OWNER_DECISION"),
        "blocking_research_decision": enumerate_params("BLOCKING_RESEARCH_DECISION"),
        "target_not_provisioned": enumerate_params("TARGET_NOT_PROVISIONED"),
        "proposed_params": enumerate_params("PROPOSED_RC2_MUST_RATIFY"),
        "blocked_formula_ids": sorted(blocked_formulas),
        "proposed_task_count": sum(
            1 for t in tasks.values() if t.get("truth_state") == "PROPOSED"
        ),
        "normative_not_implemented_task_count": sum(
            1 for t in tasks.values()
            if t.get("truth_state") == "NORMATIVE_TARGET_NOT_IMPLEMENTED"
        ),
        "blocked_task_count": sum(
            1 for t in tasks.values() if t.get("truth_state") == "BLOCKED"
        ),
    }


def _task_blocker(task: dict, blockers: dict[str, object]) -> str | None:
    """Return the first blocker id a task depends on (deterministic), or None."""
    if task.get("truth_state") in BLOCKING_TASK_STATE:
        # The task itself is blocked; name the task id (a parameter-declaration task shares
        # its id with the parameter — e.g. PAR-070 — so this names the owner blocker too).
        return str(task.get("id"))
    for fid in sorted(f for f in _formula_keys(task.get("formula_refs"))
                      if f in blockers["blocked_formulas"]):
        return fid
    refs = _split_refs(task.get("requirement_refs")) + _split_refs(task.get("inventory_refs"))
    for pid in sorted(r for r in refs if r in blockers["blocked_params"]):
        return pid
    return None


def classify_verification(
    verification: dict,
    blockers: dict[str, object],
    criterion_by_vid: dict[str, str],
    evidence_links: dict[str, str],
) -> dict[str, object]:
    """Assign exactly one status to an RC3 verification row (precedence: first match wins)."""
    tasks = blockers["tasks"]
    vid = verification["verification_id"]
    linked = _split_refs(verification.get("linked_task_ids"))
    resolvable = [tid for tid in linked if tid in tasks]

    if resolvable:
        nodes = sorted({str(tasks[tid].get("node") or "") for tid in resolvable})
        ownership = (
            "FOREIGN" if all(_is_foreign_node(n) for n in nodes)
            else "MIXED" if any(_is_foreign_node(n) for n in nodes)
            else "ORIGIN"
        )
    else:
        nodes = []
        ownership = "UNLINKED"

    row: dict[str, object] = {
        "population": verification.get("source", ""),
        "id": vid,
        "criticality": verification.get("criticality", ""),
        "gate": verification.get("gate", ""),
        "suite": verification.get("suite", ""),
        "ownership": ownership,
        "nodes": nodes,
        "task_ids": sorted(resolvable),
        "criterion_id": criterion_by_vid.get(vid),
        "current_result": verification.get("initial_status", ""),
        "evidence_test_id": None,
        "blocked_by": None,
    }

    # 1) BLOCKED — closure depends on a blocked registry entry. Absolute: this wins over
    #    every other status so no blocked mandatory row can ever read green.
    blocked_by = sorted(
        b for b in (_task_blocker(tasks[tid], blockers) for tid in resolvable) if b
    )
    if blocked_by:
        row["status"] = STATUS_BLOCKED
        row["blocked_by"] = blocked_by[0]
        return row

    # 2) OUT_OF_REPO — every resolvable owning node is foreign (money line / estate). A row
    #    with any ORIGIN side (MIXED) or no resolvable node (UNLINKED) is NOT out-of-repo.
    if ownership == "FOREIGN":
        row["status"] = STATUS_OUT_OF_REPO
        return row

    # 3) COVERED — an ORIGIN-owned (or MIXED-origin-side) row pinned by a real repo test id.
    node_id = evidence_links.get(vid)
    if node_id:
        row["status"] = STATUS_COVERED
        row["evidence_test_id"] = node_id
        return row

    # 4) DEFERRED — in-scope ORIGIN / MIXED-origin / UNLINKED row, owed. Non-green.
    row["status"] = STATUS_DEFERRED
    return row


def classify_fixture(
    fixture: dict, evidence_links: dict[str, str]
) -> dict[str, object]:
    """Assign a status to an RC4 lever/four-plane/shadow fixture (COVERED or DEFERRED only).

    RC4 fixtures are ORIGIN-owned lever/plane/shadow conformance (typed refusals), never
    money-line-executable and never foreign-node — so they can only be COVERED (a fixture
    replay test pins them) or DEFERRED (owed).
    """
    fid = fixture["id"]
    row: dict[str, object] = {
        "population": "RC4_LEVER",
        "id": fid,
        "criticality": "",
        "gate": "",
        "suite": fixture.get("area", ""),
        "ownership": "LEVER",
        "nodes": [],
        "task_ids": [],
        "criterion_id": None,
        "current_result": "NOT_RUN",
        "evidence_test_id": None,
        "blocked_by": None,
    }
    node_id = evidence_links.get(fid)
    if node_id:
        row["status"] = STATUS_COVERED
        row["evidence_test_id"] = node_id
    else:
        row["status"] = STATUS_DEFERRED
    return row


def build_matrix(
    rc3: dict, rc4: dict, evidence_links: dict[str, str] | None = None
) -> dict:
    """Build the full conformance matrix object (pure; deterministic)."""
    if evidence_links is None:
        evidence_links = {}
    blockers = derive_blockers(rc3)

    criterion_by_vid: dict[str, str] = {}
    for criterion in rc3.get("criteria", []):
        vid = criterion.get("verification_id")
        cid = criterion.get("criterion_id")
        if vid and cid and vid not in criterion_by_vid:
            criterion_by_vid[vid] = cid

    rows: list[dict[str, object]] = []
    for verification in rc3["verifications"]:
        rows.append(
            classify_verification(verification, blockers, criterion_by_vid, evidence_links)
        )
    for fixture in rc4["verifications"]:
        rows.append(classify_fixture(fixture, evidence_links))

    # Refuse a duplicate (population, id) — the build-ledger duplicate-id law.
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (str(row["population"]), str(row["id"]))
        if key in seen:
            raise MatrixError(f"duplicate matrix row {key}")
        seen.add(key)

    rows.sort(key=lambda r: (str(r["population"]), str(r["id"])))

    status_counts = {status: 0 for status in STATUS_VOCABULARY}
    population_counts: dict[str, int] = {}
    ownership_counts: dict[str, int] = {}
    for row in rows:
        status_counts[str(row["status"])] += 1
        population_counts[str(row["population"])] = (
            population_counts.get(str(row["population"]), 0) + 1
        )
        ownership_counts[str(row["ownership"])] = (
            ownership_counts.get(str(row["ownership"]), 0) + 1
        )

    rc1_count = population_counts.get("RC1_408_PRESERVED", 0)
    rc3_count = len(rc3["verifications"])
    rc4_count = len(rc4["verifications"])

    formula_ids = sorted(f["id"] for f in rc3["formulas"])

    matrix = {
        "schema": SCHEMA,
        "matrix_version": MATRIX_VERSION,
        "generated_by": "claude-fable-5-build-session/B09",
        "basis": (
            "00_MASTER_PLAN §10 verification law: account for the 408 RC1_408_PRESERVED "
            "subset (inside the 1523; distinct from the disjoint 407 RC1_SCOPE_CLOSURE "
            "suite), the 1523 RC3 effective verifications and the 125 RC4 fixtures — each "
            "row derived to one of {COVERED, BLOCKED, DEFERRED, OUT_OF_REPO} from bundle "
            "ownership + status fields + curated repo test evidence; no blocked row green"
        ),
        "totals": {
            "rc1_408_preserved": rc1_count,
            "rc3_effective_verifications": rc3_count,
            "rc4_fixtures": rc4_count,
            "matrix_rows": len(rows),
        },
        "status_vocabulary": list(STATUS_VOCABULARY),
        "status_counts": status_counts,
        "population_counts": dict(sorted(population_counts.items())),
        "ownership_counts": dict(sorted(ownership_counts.items())),
        "formula_registry": {
            "formula_ids": formula_ids,
            "formula_count": len(formula_ids),
            "blocked_formula_ids": blockers["blocked_formula_ids"],
            # Assert no F24 exists: the registry is exactly F00..F23, nothing past F23.
            "f24_absent": formula_ids == _EXPECTED_FORMULA_IDS,
        },
        "blocked_registry": {
            "blocking_owner_decision": blockers["blocking_owner_decision"],
            "blocking_research_decision": blockers["blocking_research_decision"],
            "target_not_provisioned": blockers["target_not_provisioned"],
            "blocked_formula_ids": blockers["blocked_formula_ids"],
            "proposed_param_count": len(blockers["proposed_params"]),
            "proposed_task_count": blockers["proposed_task_count"],
            "normative_not_implemented_task_count": blockers[
                "normative_not_implemented_task_count"
            ],
            "blocked_task_count": blockers["blocked_task_count"],
        },
        "rows": rows,
    }
    matrix["invariants"] = _compute_invariants(matrix)
    _assert_invariants(matrix)
    return matrix


def _compute_invariants(matrix: dict) -> dict[str, bool]:
    totals = matrix["totals"]
    rows = matrix["rows"]
    status_counts = matrix["status_counts"]
    return {
        "totals_reconcile": (
            totals["rc1_408_preserved"] == EXPECTED_RC1_408_PRESERVED
            and totals["rc3_effective_verifications"] == EXPECTED_RC3_EFFECTIVE
            and totals["rc4_fixtures"] == EXPECTED_RC4_FIXTURES
            and totals["matrix_rows"] == EXPECTED_RC3_EFFECTIVE + EXPECTED_RC4_FIXTURES
        ),
        "rc1_408_preserved_exact": totals["rc1_408_preserved"] == EXPECTED_RC1_408_PRESERVED,
        "exactly_one_status_per_row": all(
            row.get("status") in STATUS_VOCABULARY for row in rows
        ) and sum(status_counts.values()) == len(rows),
        "no_blocked_row_covered": not any(
            row.get("status") == STATUS_COVERED and row.get("blocked_by") is not None
            for row in rows
        ),
        "no_f24": matrix["formula_registry"]["f24_absent"]
        and matrix["formula_registry"]["formula_ids"] == _EXPECTED_FORMULA_IDS,
    }


def _assert_invariants(matrix: dict) -> None:
    failures = [name for name, ok in matrix["invariants"].items() if not ok]
    if failures:
        raise MatrixError(
            "conformance matrix invariant violation: " + ", ".join(sorted(failures))
        )


def render(matrix: dict) -> str:
    return json.dumps(matrix, indent=1, sort_keys=True) + "\n"


def generate() -> dict:
    rc3 = load_json(RC3_BUNDLE, "RC3 effective control bundle")
    rc4 = load_json(RC4_BUNDLE, "RC4 control bundle")
    return build_matrix(rc3, rc4, load_evidence_links())


def _fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="conformance_matrix.py", description=__doc__)
    parser.add_argument("--verify", action="store_true",
                        help="regenerate to memory and byte-compare the committed matrix")
    parser.add_argument("--status", action="store_true",
                        help="print the status / population summary")
    args = parser.parse_args(argv)

    try:
        matrix = generate()
    except MatrixError as exc:
        return _fail(str(exc))
    rendered = render(matrix)

    if args.status:
        totals = matrix["totals"]
        print(
            f"conformance matrix {matrix['matrix_version']}: "
            f"{totals['matrix_rows']} rows "
            f"(RC1={totals['rc1_408_preserved']} ⊂ RC3={totals['rc3_effective_verifications']}, "
            f"RC4={totals['rc4_fixtures']})"
        )
        for status, count in sorted(matrix["status_counts"].items()):
            print(f"  {status}: {count}")
        return 0

    if args.verify:
        if not MATRIX.exists():
            return _fail(f"{MATRIX.relative_to(ROOT).as_posix()} missing; run "
                         "python tools/conformance_matrix.py")
        if MATRIX.read_text(encoding="utf-8") != rendered:
            return _fail("conformance matrix is stale; run python tools/conformance_matrix.py")
        print(
            f"OK: conformance matrix current ({matrix['totals']['matrix_rows']} rows; "
            f"COVERED={matrix['status_counts'][STATUS_COVERED]}, "
            f"BLOCKED={matrix['status_counts'][STATUS_BLOCKED]}, "
            f"DEFERRED={matrix['status_counts'][STATUS_DEFERRED]}, "
            f"OUT_OF_REPO={matrix['status_counts'][STATUS_OUT_OF_REPO]})"
        )
        return 0

    MATRIX.write_text(rendered, encoding="utf-8")
    print(f"wrote {MATRIX.relative_to(ROOT).as_posix()} "
          f"({matrix['totals']['matrix_rows']} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
