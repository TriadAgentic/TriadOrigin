"""Tests for tools/conformance_matrix.py against the REAL read-only repo.

The repository at /home/user/TriadOrigin is READ-ONLY. These tests never regenerate the
committed matrix (that would mutate the tree); instead they build the matrix in memory
(the generator is a pure function) and assert ``render()`` is byte-equal to the committed
``docs/control/conformance_matrix.v1.json`` — the same guarantee ``--verify`` gives — and
that the load-bearing accounting invariants hold.

The tool module is loaded from its file path via ``importlib.util.spec_from_file_location``
(after asserting its ``__main__`` guard), with ``sys.dont_write_bytecode`` set, so no
``__pycache__`` is written beside the source in the read-only tree.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import pathlib
import sys
from types import ModuleType

import pytest

# Never write bytecode caches while importing tools from the read-only repository tree.
sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOLS_DIR = REPO_ROOT / "tools"
CONTROL = REPO_ROOT / "docs" / "control"
MATRIX_PATH = CONTROL / "conformance_matrix.v1.json"
RC3_BUNDLE = CONTROL / "rc3_effective_control_bundle.json"
RC4_BUNDLE = CONTROL / "rc4_control_bundle.json"

# The load-bearing blocker inventory the "no blocked mandatory row counted green" law names.
OWNER_BLOCKER_PARAMS = (
    "PAR-070", "PAR-072", "PAR-076", "PAR-077", "PAR-118", "PAR-119", "PAR-120", "PAR-121",
)
RESEARCH_BLOCKER_PARAMS = (
    "RC3-PAR-STRUCT-001", "RC3-PAR-STRUCT-002", "RC3-PAR-STRUCT-003",
)
BLOCKED_FORMULAS = (
    "F01", "F03", "F05", "F06", "F07", "F08", "F10", "F11", "F12", "F13", "F16", "F17",
)
TARGET_NOT_PROVISIONED_PARAMS = ("PAR-149", "PAR-150", "PAR-151", "PAR-152")

EXPECTED_FORMULA_IDS = [f"F{i:02d}" for i in range(24)]

STDLIB_IMPORT_ALLOWLIST = frozenset(
    {"__future__", "argparse", "json", "pathlib", "sys"}
)


def _load_module(name: str, path: pathlib.Path) -> ModuleType:
    assert path.is_file(), f"tool source missing: {path}"
    text = path.read_text(encoding="utf-8")
    assert 'if __name__ == "__main__":' in text, (
        f"{path.name} lacks a __main__ guard; importing it could execute main")
    spec = importlib.util.spec_from_file_location(f"staged_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(spec.name, None)
        raise
    return module


@pytest.fixture(scope="module")
def cm() -> ModuleType:
    return _load_module("conformance_matrix", TOOLS_DIR / "conformance_matrix.py")


@pytest.fixture(scope="module")
def counter() -> ModuleType:
    return _load_module("verify_spec_control_counts", TOOLS_DIR / "verify_spec_control_counts.py")


@pytest.fixture(scope="module")
def ledger() -> ModuleType:
    return _load_module("build_ledger", TOOLS_DIR / "build_ledger.py")


@pytest.fixture(scope="module")
def rc3() -> dict:
    return json.loads(RC3_BUNDLE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rc4() -> dict:
    return json.loads(RC4_BUNDLE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def matrix(cm: ModuleType, rc3: dict, rc4: dict) -> dict:
    # Built in memory with NO evidence links — the committed / default posture.
    return cm.build_matrix(rc3, rc4)


@pytest.fixture(scope="module")
def committed() -> dict:
    assert MATRIX_PATH.is_file(), "committed conformance matrix missing"
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rows_by_id(committed: dict) -> dict[str, dict]:
    return {row["id"]: row for row in committed["rows"]}


# ---------------------------------------------------------------------------
# Byte-determinism and the --verify guarantee
# ---------------------------------------------------------------------------

def test_committed_matrix_is_byte_current(cm: ModuleType, matrix: dict) -> None:
    """render(build_matrix(...)) equals the committed file exactly (the --verify law)."""
    assert cm.render(matrix) == MATRIX_PATH.read_text(encoding="utf-8")


def test_regeneration_is_byte_deterministic(cm: ModuleType, rc3: dict, rc4: dict) -> None:
    first = cm.render(cm.build_matrix(rc3, rc4))
    second = cm.render(cm.build_matrix(rc3, rc4))
    assert first == second == MATRIX_PATH.read_text(encoding="utf-8")


def test_verify_detects_a_stale_or_poisoned_artifact(cm: ModuleType, matrix: dict) -> None:
    """A single mutated row makes the render diverge — --verify would red."""
    current = cm.render(matrix)
    poisoned = json.loads(current)
    poisoned["rows"][0]["status"] = "COVERED"
    assert cm.render(matrix) != json.dumps(poisoned, indent=1, sort_keys=True) + "\n"


# ---------------------------------------------------------------------------
# Totals reconcile with the pinned strict counter (they can never disagree)
# ---------------------------------------------------------------------------

def test_totals_agree_with_verify_spec_control_counts(
    matrix: dict, counter: ModuleType
) -> None:
    derived = counter.derive_counts(REPO_ROOT)
    totals = matrix["totals"]
    assert totals["rc1_408_preserved"] == derived["rc1_test_count"] == 408
    assert totals["rc3_effective_verifications"] == derived["rc3_effective_verification_count"] == 1523
    assert totals["rc4_fixtures"] == derived["rc4_fixture_count"] == 125
    assert totals["matrix_rows"] == 1523 + 125 == 1648


def test_row_and_population_counts_reconcile(matrix: dict) -> None:
    rows = matrix["rows"]
    assert len(rows) == matrix["totals"]["matrix_rows"]
    assert sum(matrix["status_counts"].values()) == len(rows)
    assert sum(matrix["population_counts"].values()) == len(rows)
    assert matrix["population_counts"] == {
        "RC1_408_PRESERVED": 408,
        "RC2_GENERATED": 1088,
        "RC3_NORMATIVE_OVERLAY": 27,
        "RC4_LEVER": 125,
    }


# ---------------------------------------------------------------------------
# The 408 ⊂ 1523 accounting, and the 408 ≠ 407 trap
# ---------------------------------------------------------------------------

def test_rc1_408_preserved_is_exactly_the_source_subset(matrix: dict, rc3: dict) -> None:
    source_408 = {
        v["verification_id"] for v in rc3["verifications"]
        if v.get("source") == "RC1_408_PRESERVED"
    }
    assert len(source_408) == 408
    matrix_408 = {
        row["id"] for row in matrix["rows"]
        if row["population"] == "RC1_408_PRESERVED"
    }
    assert matrix_408 == source_408


def test_408_is_not_conflated_with_the_407_scope_closure_family(
    matrix: dict, rc3: dict
) -> None:
    """The disjoint 407-row RC1_SCOPE_CLOSURE suite must never be counted as the 408."""
    suite_407 = [
        v for v in rc3["verifications"] if v.get("suite") == "RC1_SCOPE_CLOSURE"
    ]
    assert len(suite_407) == 407 != 408
    scope_ids = {v["verification_id"] for v in suite_407}
    source_ids = {
        v["verification_id"] for v in rc3["verifications"]
        if v.get("source") == "RC1_408_PRESERVED"
    }
    # The two families are disjoint, so no RC1_SCOPE_CLOSURE row is tagged RC1_408_PRESERVED.
    assert scope_ids.isdisjoint(source_ids)
    for row in matrix["rows"]:
        if row.get("suite") == "RC1_SCOPE_CLOSURE":
            assert row["population"] != "RC1_408_PRESERVED"


# ---------------------------------------------------------------------------
# Exactly one status per row, from the closed vocabulary
# ---------------------------------------------------------------------------

def test_every_row_carries_exactly_one_status_from_the_vocabulary(
    cm: ModuleType, matrix: dict
) -> None:
    vocab = set(cm.STATUS_VOCABULARY)
    assert vocab == {"COVERED", "BLOCKED", "DEFERRED", "OUT_OF_REPO"}
    for row in matrix["rows"]:
        assert row["status"] in vocab
    assert set(matrix["status_counts"]) == vocab
    assert matrix["invariants"]["exactly_one_status_per_row"] is True


# ---------------------------------------------------------------------------
# Load-bearing law: no blocked mandatory row is ever counted green
# ---------------------------------------------------------------------------

def test_no_covered_row_carries_a_blocker(matrix: dict) -> None:
    for row in matrix["rows"]:
        if row["status"] == "COVERED":
            assert row["blocked_by"] is None
    assert matrix["invariants"]["no_blocked_row_covered"] is True


def test_the_eight_owner_blocker_rows_are_blocked_never_covered(
    rows_by_id: dict[str, dict]
) -> None:
    for param in OWNER_BLOCKER_PARAMS:
        row = rows_by_id.get(f"V-{param}")
        assert row is not None, f"missing owner-blocker verification V-{param}"
        assert row["status"] == "BLOCKED"
        assert row["blocked_by"] == param


def test_the_three_research_blocker_params_are_in_the_registry(committed: dict) -> None:
    assert list(committed["blocked_registry"]["blocking_research_decision"]) == list(
        RESEARCH_BLOCKER_PARAMS
    )


def test_the_twelve_blocked_formula_verifications_are_blocked(
    matrix: dict, rc3: dict
) -> None:
    tasks = {t["id"]: t for t in rc3["tasks"]}
    status_by_id = {row["id"]: row for row in matrix["rows"]}

    def formula_of(refs: object) -> set[str]:
        out = set()
        for tok in str(refs or "").replace(";", ",").split(","):
            tok = tok.strip()
            if tok[:1] == "F" and tok[1:3].isdigit():
                out.add(tok[:3])
        return out

    for fid in BLOCKED_FORMULAS:
        hits = 0
        for v in rc3["verifications"]:
            linked = [
                x.strip() for x in str(v.get("linked_task_ids") or "").replace(";", ",").split(",")
                if x.strip()
            ]
            if any(fid in formula_of(tasks[tid].get("formula_refs"))
                   for tid in linked if tid in tasks):
                row = status_by_id[v["verification_id"]]
                assert row["status"] == "BLOCKED", (fid, v["verification_id"], row["status"])
                hits += 1
        assert hits > 0, f"blocked formula {fid} reached no verification row"


def test_blocked_registry_enumerates_the_inventory(committed: dict) -> None:
    reg = committed["blocked_registry"]
    assert list(reg["blocking_owner_decision"]) == list(OWNER_BLOCKER_PARAMS)
    assert list(reg["blocking_research_decision"]) == list(RESEARCH_BLOCKER_PARAMS)
    assert list(reg["target_not_provisioned"]) == list(TARGET_NOT_PROVISIONED_PARAMS)
    assert list(reg["blocked_formula_ids"]) == list(BLOCKED_FORMULAS)
    assert reg["proposed_param_count"] == 123
    assert reg["proposed_task_count"] == 129
    assert reg["normative_not_implemented_task_count"] == 27
    assert reg["blocked_task_count"] == 8


def test_committed_matrix_has_zero_green_rows_today(committed: dict) -> None:
    """No verification_id → pytest-node evidence link exists yet, so nothing is COVERED."""
    assert committed["status_counts"]["COVERED"] == 0


# ---------------------------------------------------------------------------
# No F24 — the formula registry is exactly F00..F23
# ---------------------------------------------------------------------------

def test_formula_registry_is_exactly_f00_to_f23(committed: dict, rc3: dict) -> None:
    reg = committed["formula_registry"]
    assert reg["formula_ids"] == EXPECTED_FORMULA_IDS
    assert reg["formula_count"] == 24
    assert reg["f24_absent"] is True
    assert committed["invariants"]["no_f24"] is True
    # Consistent with the RC3 bundle itself (mirrors test_b00c formula-registry equality).
    assert sorted(f["id"] for f in rc3["formulas"]) == EXPECTED_FORMULA_IDS


# ---------------------------------------------------------------------------
# OUT_OF_REPO rows are foreign / catalog-only; F20-F23 estate catalog boundary
# ---------------------------------------------------------------------------

def test_out_of_repo_rows_are_all_foreign_node(matrix: dict) -> None:
    for row in matrix["rows"]:
        if row["status"] == "OUT_OF_REPO":
            assert row["ownership"] == "FOREIGN"
            assert row["task_ids"], "an OUT_OF_REPO row must resolve to a foreign task"


def test_foreign_node_anchor_matches_build_ledger(cm: ModuleType, ledger: ModuleType) -> None:
    """Drift-lock: the matrix's foreign anchor is byte-identical to build_ledger.ESTATE_NODES."""
    assert set(cm.FOREIGN_NODES) == set(ledger.ESTATE_NODES)


def test_foreign_predicate_is_never_narrower_than_build_ledger(
    cm: ModuleType, ledger: ModuleType
) -> None:
    """Every build_ledger estate node is foreign in the matrix (never treated as in-repo).

    The matrix predicate is BROADER (per CLAUDE.md the whole E00/E01/E07/E08/E09/E10 money
    line + VGP is OUT_OF_REPO), so it also catches money-line sub-nodes the explicit
    build_ledger set does not enumerate — but it may never be narrower.
    """
    for node in ledger.ESTATE_NODES:
        assert cm._is_foreign_node(node), node
    # The sub-nodes build_ledger's explicit set misses are still foreign here.
    for node in ("E00", "E09 protection owner", "E09 reconciler", "VGP", "E00/E09", "E10/Learning"):
        assert cm._is_foreign_node(node), node
    # A non-money node stays in-repo.
    for node in ("ORIGIN", "Edge comparator", "Contracts", "E06"):
        assert not cm._is_foreign_node(node), node


def test_f20_to_f23_estate_formula_rows_are_out_of_repo(matrix: dict, rc3: dict) -> None:
    """The estate formula catalog (F20-F23, owners E08/E09/E10) is OUT_OF_REPO, not green."""
    tasks = {t["id"]: t for t in rc3["tasks"]}
    status_by_id = {row["id"]: row for row in matrix["rows"]}
    seen = 0
    for v in rc3["verifications"]:
        linked = [
            x.strip() for x in str(v.get("linked_task_ids") or "").replace(";", ",").split(",")
            if x.strip()
        ]
        for tid in linked:
            t = tasks.get(tid)
            if t and str(t.get("formula_refs") or "")[:3] in ("F20", "F21", "F22", "F23"):
                row = status_by_id[v["verification_id"]]
                # The estate formula catalog is never money-line-executable / never green.
                assert row["status"] != "COVERED", (tid, row["status"])
                # A purely-foreign F20-F23 row is OUT_OF_REPO (or BLOCKED when its closure
                # depends on a blocker); only a MIXED-origin row may be DEFERRED.
                if row["ownership"] == "FOREIGN":
                    assert row["status"] in ("OUT_OF_REPO", "BLOCKED"), (tid, row["status"])
                seen += 1
    assert seen > 0


def test_f20_rollout_invariance_fixture_is_accounted(rows_by_id: dict[str, dict]) -> None:
    """LEV-V-0120 (F20 rollout-metadata byte-invariance) is accounted, never money-line."""
    row = rows_by_id.get("LEV-V-0120")
    assert row is not None
    assert row["population"] == "RC4_LEVER"
    assert row["status"] in ("COVERED", "DEFERRED")


# ---------------------------------------------------------------------------
# RC4 fixtures are lever/plane/shadow conformance — COVERED or DEFERRED only
# ---------------------------------------------------------------------------

def test_rc4_fixtures_are_only_covered_or_deferred(matrix: dict) -> None:
    rc4_rows = [row for row in matrix["rows"] if row["population"] == "RC4_LEVER"]
    assert len(rc4_rows) == 125
    for row in rc4_rows:
        assert row["status"] in ("COVERED", "DEFERRED")
        assert row["blocked_by"] is None
        assert row["ownership"] == "LEVER"


# ---------------------------------------------------------------------------
# The COVERED mechanism: an evidence link promotes only an in-scope non-blocked row
# ---------------------------------------------------------------------------

def _first_id(matrix: dict, *, status: str, ownership: str | None = None,
              population: str | None = None) -> str:
    for row in matrix["rows"]:
        if row["status"] != status:
            continue
        if ownership is not None and row["ownership"] != ownership:
            continue
        if population is not None and row["population"] != population:
            continue
        return str(row["id"])
    raise AssertionError(f"no row with status={status} ownership={ownership}")


def test_evidence_link_covers_an_origin_deferred_row(
    cm: ModuleType, rc3: dict, rc4: dict, matrix: dict
) -> None:
    target = _first_id(matrix, status="DEFERRED", ownership="ORIGIN")
    node_id = "tests/tools/test_conformance_matrix.py::test_evidence_link_covers_an_origin_deferred_row"
    linked = cm.build_matrix(rc3, rc4, {target: node_id})
    row = next(r for r in linked["rows"] if r["id"] == target)
    assert row["status"] == "COVERED"
    assert row["evidence_test_id"] == node_id
    assert linked["invariants"]["no_blocked_row_covered"] is True


def test_evidence_link_never_greens_a_blocked_row(
    cm: ModuleType, rc3: dict, rc4: dict, matrix: dict
) -> None:
    target = _first_id(matrix, status="BLOCKED")
    linked = cm.build_matrix(rc3, rc4, {target: "tests/x::fake"})
    row = next(r for r in linked["rows"] if r["id"] == target)
    assert row["status"] == "BLOCKED"
    assert row["evidence_test_id"] is None
    assert linked["invariants"]["no_blocked_row_covered"] is True


def test_evidence_link_never_greens_an_out_of_repo_row(
    cm: ModuleType, rc3: dict, rc4: dict, matrix: dict
) -> None:
    target = _first_id(matrix, status="OUT_OF_REPO")
    linked = cm.build_matrix(rc3, rc4, {target: "tests/x::fake"})
    row = next(r for r in linked["rows"] if r["id"] == target)
    assert row["status"] == "OUT_OF_REPO"
    assert row["evidence_test_id"] is None


def test_evidence_link_covers_an_rc4_fixture(
    cm: ModuleType, rc3: dict, rc4: dict, matrix: dict
) -> None:
    target = _first_id(matrix, status="DEFERRED", population="RC4_LEVER")
    node_id = "tests/control/test_lever_law.py::test_something"
    linked = cm.build_matrix(rc3, rc4, {target: node_id})
    row = next(r for r in linked["rows"] if r["id"] == target)
    assert row["status"] == "COVERED"
    assert row["evidence_test_id"] == node_id


def test_generator_refuses_a_matrix_that_greens_a_blocked_row(
    cm: ModuleType, matrix: dict
) -> None:
    """_assert_invariants fails loud if a blocked row is ever hand-forced to COVERED."""
    poisoned = json.loads(cm.render(matrix))
    blocked = next(r for r in poisoned["rows"] if r["status"] == "BLOCKED")
    blocked["status"] = "COVERED"  # keep blocked_by set — a fabricated green
    poisoned["invariants"] = cm._compute_invariants(poisoned)
    assert poisoned["invariants"]["no_blocked_row_covered"] is False
    with pytest.raises(cm.MatrixError):
        cm._assert_invariants(poisoned)


# ---------------------------------------------------------------------------
# Capability discipline: the matrix tool imports only stdlib (no money line)
# ---------------------------------------------------------------------------

def test_generator_imports_only_stdlib(cm: ModuleType) -> None:
    source = (TOOLS_DIR / "conformance_matrix.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
    assert roots <= STDLIB_IMPORT_ALLOWLIST, (
        f"conformance_matrix.py imports beyond the stdlib allowlist: "
        f"{sorted(roots - STDLIB_IMPORT_ALLOWLIST)}")


# ---------------------------------------------------------------------------
# Read-only discipline: the CLI --verify / --status paths write nothing
# ---------------------------------------------------------------------------

def test_verify_and_status_cli_are_read_only(cm: ModuleType, capsys) -> None:
    before = MATRIX_PATH.read_bytes()
    assert cm.main(["--status"]) == 0
    assert cm.main(["--verify"]) == 0
    assert MATRIX_PATH.read_bytes() == before
