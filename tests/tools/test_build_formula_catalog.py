"""Tests for tools/build_formula_catalog.py against the REAL read-only repo.

The B09 estate formula catalog (F20-F23) is a G6 interface subset: ORIGIN vendors the
money-line formulas' CONTRACT SHAPE + golden vectors + the FORM-Fxx-01..07 boundary rows,
never the executable sizing/maker/IOC/PnL logic (which is OUT_OF_REPO). These tests:

  * assert the committed ``docs/control/formula_catalog.v1.json`` is byte-current with the
    pure generator (the ``--verify`` guarantee) and byte-deterministic;
  * assert the "Assert no F24 exists" registry equality (F00..F23) and that F20-F23 are the
    only IN_REPO_CATALOG estate-economics entries, owners E08/E09/E10, drift-locked to
    ``build_ledger``'s classification and to the 28 REVIEWED_ACCEPT FORM rows;
  * assert the golden vectors GV-017..020 are vendored VERBATIM from the RC3 bundle and
    REPLAY each golden boundary vector's arithmetic (exact ``fractions``) to prove the
    vendored ``expected`` is consistent with the (corrected) formula;
  * assert the F20 special law — the corrected form carries NO activation_mode/rollout branch,
    rollout metadata is byte-invariant to the sizing dependency projection (LEV-V-0120), and a
    missing/invalid selected policy DENIES;
  * assert the capability boundary — the generator imports only stdlib, and no
    ``src/triad_origin`` module implements F20-F23 sizing/maker/IOC/PnL (the reservation the
    F00 ``qty_to_steps`` ingress already enforces).

The tool module is loaded from its file path via ``importlib.util.spec_from_file_location``
(after asserting its ``__main__`` guard), with ``sys.dont_write_bytecode`` set, so no
``__pycache__`` is written beside the source in the read-only tree.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import pathlib
import re
import sys
from fractions import Fraction
from types import ModuleType

import pytest

# Never write bytecode caches while importing tools from the read-only repository tree.
sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOLS_DIR = REPO_ROOT / "tools"
CONTROL = REPO_ROOT / "docs" / "control"
CATALOG_PATH = CONTROL / "formula_catalog.v1.json"
RC3_BUNDLE = CONTROL / "rc3_effective_control_bundle.json"
RC4_BUNDLE = CONTROL / "rc4_control_bundle.json"
LEDGER_REVIEW = CONTROL / "build_ledger_review.v1.json"
RUNTIME = REPO_ROOT / "src" / "triad_origin"

EXPECTED_FORMULA_IDS = [f"F{i:02d}" for i in range(24)]
ESTATE_FORMULA_IDS = ("F20", "F21", "F22", "F23")
ESTATE_OWNERS = {"F20": "E08", "F21": "E09", "F22": "E09", "F23": "E10"}
GOLDEN_VECTOR_BY_FORMULA = {"F20": "GV-017", "F21": "GV-018", "F22": "GV-019", "F23": "GV-020"}

STDLIB_IMPORT_ALLOWLIST = frozenset({"__future__", "argparse", "json", "pathlib", "sys"})

# Unambiguous money-line names: a `def` of any of these under src/triad_origin would be
# executable sizing / maker / IOC / PnL logic — forbidden here (OUT_OF_REPO).
FORBIDDEN_MONEY_LINE_DEF = re.compile(
    r"\bdef\s+[A-Za-z0-9_]*"
    r"(qty_budget|maker_gtx|maker_first|emergency_ioc|worst_price|entry_vwap|exit_vwap|"
    r"markout|pnl|size_position|compile_order|risk_budget_size)"
    r"[A-Za-z0-9_]*\s*\("
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
def fc() -> ModuleType:
    return _load_module("build_formula_catalog", TOOLS_DIR / "build_formula_catalog.py")


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
def catalog(fc: ModuleType, rc3: dict, rc4: dict) -> dict:
    return fc.build_catalog(rc3, rc4)


@pytest.fixture(scope="module")
def committed() -> dict:
    assert CATALOG_PATH.is_file(), "committed formula catalog missing"
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Byte-determinism and the --verify guarantee
# ---------------------------------------------------------------------------

def test_committed_catalog_is_byte_current(fc: ModuleType, catalog: dict) -> None:
    assert fc.render(catalog) == CATALOG_PATH.read_text(encoding="utf-8")


def test_regeneration_is_byte_deterministic(fc: ModuleType, rc3: dict, rc4: dict) -> None:
    first = fc.render(fc.build_catalog(rc3, rc4))
    second = fc.render(fc.build_catalog(rc3, rc4))
    assert first == second == CATALOG_PATH.read_text(encoding="utf-8")


def test_verify_and_status_cli_are_read_only(fc: ModuleType) -> None:
    before = CATALOG_PATH.read_bytes()
    assert fc.main(["--status"]) == 0
    assert fc.main(["--verify"]) == 0
    assert CATALOG_PATH.read_bytes() == before


# ---------------------------------------------------------------------------
# No F24 — the registry is exactly F00..F23
# ---------------------------------------------------------------------------

def test_formula_registry_is_exactly_f00_to_f23(committed: dict, rc3: dict) -> None:
    reg = committed["formula_registry"]
    assert reg["formula_ids"] == EXPECTED_FORMULA_IDS
    assert reg["formula_count"] == 24
    assert reg["f24_absent"] is True
    assert committed["invariants"]["no_f24"] is True
    # Consistent with the RC3 bundle itself (mirrors test_b00c formula-registry equality).
    assert sorted(f["id"] for f in rc3["formulas"]) == EXPECTED_FORMULA_IDS
    assert "F24" not in reg["formula_ids"]


# ---------------------------------------------------------------------------
# F20-F23 estate catalog: IN_REPO_CATALOG, ESTATE owner, seven boundary rows
# ---------------------------------------------------------------------------

def test_estate_catalog_is_exactly_f20_to_f23(committed: dict) -> None:
    assert committed["estate_formula_ids"] == list(ESTATE_FORMULA_IDS)
    assert sorted(committed["estate_catalog"]) == list(ESTATE_FORMULA_IDS)
    assert committed["invariants"]["estate_catalog_is_f20_to_f23"] is True


def test_each_estate_entry_is_out_of_repo_catalog_with_its_owner(committed: dict) -> None:
    for fid, entry in committed["estate_catalog"].items():
        assert entry["owner_node"] == ESTATE_OWNERS[fid]
        assert entry["ownership"] == "ESTATE"
        assert entry["exec_class"] == "IN_REPO_CATALOG"
        assert entry["milestone"] == "B09"
        assert entry["gate"] == "G6"
        assert entry["implementation_is_out_of_repo"] is True
    assert committed["invariants"]["every_estate_formula_out_of_repo_catalog"] is True


def test_exec_class_classification_drift_locks_to_build_ledger(
    fc: ModuleType, ledger: ModuleType, rc3: dict
) -> None:
    """The catalog's per-formula exec_class must agree with build_ledger's classify_rc3."""
    tasks_by_formula: dict[str, dict] = {}
    for task in rc3["tasks"]:
        if task.get("row_class") == "FORMULA_ATOMIC":
            key = ledger._formula_key(task)
            if key and key not in tasks_by_formula:
                tasks_by_formula[key] = task
    for fid in EXPECTED_FORMULA_IDS:
        cat_exec, _ = fc.classify_formula(fid)
        task = tasks_by_formula.get(fid)
        assert task is not None, f"no FORMULA_ATOMIC task for {fid}"
        _, ledger_exec, _ = ledger.classify_rc3(task)
        assert cat_exec == ledger_exec, (fid, cat_exec, ledger_exec)


def test_every_estate_entry_binds_its_seven_form_rows(committed: dict) -> None:
    for fid, entry in committed["estate_catalog"].items():
        assert entry["ledger_rows"] == [f"FORM-{fid}-{i:02d}" for i in range(1, 8)]
    assert committed["invariants"]["every_estate_formula_has_seven_boundary_rows"] is True


def test_the_28_form_rows_are_reviewed_accept_in_the_ledger(committed: dict) -> None:
    """All 28 FORM-F2x-01..07 rows the catalog binds exist REVIEWED_ACCEPT in the ledger."""
    review = json.loads(LEDGER_REVIEW.read_text(encoding="utf-8"))
    disposition: dict[str, str] = {}

    def walk(obj: object) -> None:
        if isinstance(obj, dict):
            rid = obj.get("id") or obj.get("row_id")
            disp = obj.get("disposition") or obj.get("review") or obj.get("status")
            if isinstance(rid, str) and re.fullmatch(r"FORM-F2[0-3]-0[1-7]", rid):
                disposition[rid] = str(disp)
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)

    walk(review)
    catalog_rows = [
        rid for entry in committed["estate_catalog"].values() for rid in entry["ledger_rows"]
    ]
    assert len(catalog_rows) == 28
    for rid in catalog_rows:
        assert disposition.get(rid) == "REVIEWED_ACCEPT", (rid, disposition.get(rid))


def test_boundary_classes_are_the_seven_form_classes(fc: ModuleType) -> None:
    assert fc.BOUNDARY_CLASSES == (
        "Equality", "one-unit-short/over", "invalid-input", "prefix",
        "restart", "duplicate", "directional-mirror",
    )


# ---------------------------------------------------------------------------
# Golden vectors GV-017..020 vendored VERBATIM and replayed
# ---------------------------------------------------------------------------

def test_golden_vectors_are_vendored_verbatim(committed: dict, rc3: dict) -> None:
    bundle = {g.get("id"): g for g in rc3["golden_vectors"]}
    for fid, entry in committed["estate_catalog"].items():
        gv_id = GOLDEN_VECTOR_BY_FORMULA[fid]
        vendored = entry["golden_vectors"]
        assert len(vendored) == 1
        assert vendored[0]["id"] == gv_id
        # Byte-shape: the catalog carries the bundle's vector unchanged (a pure copy).
        assert vendored[0] == bundle[gv_id]
        assert fid in str(vendored[0].get("linked") or "")
    assert committed["invariants"]["every_estate_formula_vendors_its_golden_vector"] is True


def _floor_to_step(value: Fraction, step: Fraction) -> Fraction:
    return (value / step).__floor__() * step


def test_gv017_f20_selected_budget_isolated_cost_replays(committed: dict) -> None:
    """GV-017: apply the RC4-CORRECTED F20 formula exactly to the vendored inputs."""
    gv = committed["estate_catalog"]["F20"]["golden_vectors"][0]
    # Inputs: B=1; E=100; S=99; m=1; r_entry=r_exit=0; b=2/10000 per side; step=.001
    B, E, S, m = Fraction(1), Fraction(100), Fraction(99), Fraction(1)
    r_e = r_x = Fraction(0)
    b = Fraction(2, 10000)
    step = Fraction(1, 1000)
    n_e, n_x = m * abs(E), m * abs(S)
    entry_cost = n_e * (r_e + b)
    exit_cost = n_x * (r_x + b)
    unit_loss = m * abs(E - S) + entry_cost + exit_cost
    assert unit_loss > 0
    qty_raw = B / unit_loss
    qty = _floor_to_step(qty_raw, step)
    assert entry_cost == Fraction(2, 100)          # .02
    assert exit_cost == Fraction(198, 10000)        # .0198
    assert unit_loss == Fraction(10398, 10000)      # 1.0398
    assert qty == Fraction(961, 1000)               # floor_to_step=.961, never rounded up
    # The vendored expected string is consistent with this replay.
    exp = gv["expected"]
    assert "entry cost=.02" in exp and "exit cost=.0198" in exp
    assert "1.0398" in exp and "floor_to_step=.961" in exp


def test_gv018_f21_maker_limit_inside_zone_replays(committed: dict) -> None:
    """GV-018: BUY selects min(zone_max, best_bid) inside the frozen zone; no taker fallback."""
    gv = committed["estate_catalog"]["F21"]["golden_vectors"][0]
    zone_min, zone_max, best_bid = 1000, 1005, 1002
    buy_limit = min(zone_max, best_bid)
    assert buy_limit == 1002
    assert "1002 GTX" in gv["expected"]
    assert "no taker fallback" in gv["boundary"]


def test_gv019_f22_emergency_ioc_worst_price_replays(committed: dict) -> None:
    """GV-019: long SELL worst_price=floor_to_tick(best_bid*(1-s_bps/10000)); qty<=residual."""
    gv = committed["estate_catalog"]["F22"]["golden_vectors"][0]
    best_bid = Fraction(10000)
    s_bps = Fraction(10)
    worst = (best_bid * (1 - s_bps / 10000)).__floor__()  # floor to 1-tick grid
    residual = Fraction(5, 2)  # 2.5
    assert worst == 9990
    assert residual == Fraction(5, 2)
    assert "9990" in gv["expected"]
    # Reduction-only: a qty over the residual or a sign flip is rejected.
    assert "sign flip -> reject" in gv["boundary"]


def test_gv020_f23_pnl_gross_net_replays(committed: dict) -> None:
    """GV-020: gross=dir*qty*m*(exit-entry); net=gross-fees+rebates+funding; missing fee UNRESOLVED."""
    gv = committed["estate_catalog"]["F23"]["golden_vectors"][0]
    dir_sign, qty, m = Fraction(1), Fraction(2), Fraction(1)
    entry, exit_ = Fraction(100), Fraction(103)
    fees, rebates, funding = Fraction(1), Fraction(2, 10), Fraction(-1, 10)
    gross = dir_sign * qty * m * (exit_ - entry)
    net = gross - fees + rebates + funding
    assert gross == Fraction(6)
    assert net == Fraction(51, 10)  # 5.1
    assert "gross=6" in gv["expected"] and "5.1" in gv["expected"]
    assert "missing fee -> net=null/UNRESOLVED" in gv["boundary"]


# ---------------------------------------------------------------------------
# F20 special law: no activation_mode/rollout branch; rollout byte-invariance; DENY policy
# ---------------------------------------------------------------------------

def test_f20_corrected_inputs_carry_no_activation_mode_or_rollout_branch(committed: dict) -> None:
    law = committed["estate_catalog"]["F20"]["f20_law"]
    corrected = law["corrected_inputs"]
    # The one selected signed policy replaces the vague budget token; activation_mode is gone.
    assert "one already-selected signed risk-budget policy" in corrected
    joined = " ".join(corrected).lower()
    for banned in ("activation_mode", "rollout", "environment", "canary", "production"):
        assert banned not in joined, banned
    for param in ("PAR-069", "PAR-070"):
        assert all(param not in tok for tok in corrected), param
    assert law["removed_branch_params"] == ["PAR-069", "PAR-070"]
    assert law["activation_mode_removed"] is True
    assert law["rollout_metadata_in_dependencies"] == []
    assert law["rollout_reaches_sizing"] is False
    assert committed["invariants"]["f20_activation_mode_removed"] is True
    assert committed["invariants"]["f20_rollout_absent_from_sizing"] is True


def test_f20_controlling_source_is_the_rc4_supersession_not_the_retained_rc3_text(
    committed: dict, rc3: dict
) -> None:
    """The catalog cites RC4 as controlling; the raw RC3 formula text still carries the branch."""
    law = committed["estate_catalog"]["F20"]["f20_law"]
    src = law["controlling_source"]
    assert src["rc4_supersession_record"] == "F20"
    assert src["task"] == "LEV-0044"
    assert src["fixture"] == "LEV-V-0120"
    assert "one already selected signed risk-budget policy" in src["replacement"]
    # The raw RC3 formula string retains the superseded branch — this is the drift the catalog
    # corrects, and its verbatim provenance is preserved.
    f20_rc3 = next(f for f in rc3["formulas"] if f["id"] == "F20")
    assert "activation_mode" in f20_rc3["formula"]
    assert law["raw_rc3_inputs"] == f20_rc3["inputs"]


def test_f20_rollout_metadata_is_byte_invariant_to_the_sizing_projection(
    fc: ModuleType, committed: dict
) -> None:
    """LEV-V-0120: change rollout metadata, identical signed budget/inputs → identical bytes."""
    tokens = committed["estate_catalog"]["F20"]["f20_law"]["corrected_inputs"]
    policy = {"policy_ref": "POL-1", "signed": True}
    base = {
        "one already-selected signed risk-budget policy": policy,
        "entry/stop prices": {"E": "100", "S": "99"},
        "PAR-078 current account fee snapshot": {"maker": "0"},
    }
    inputs_a = dict(base, rollout_metadata="CANARY", activation_mode="CANARY")
    inputs_b = dict(base, rollout_metadata="PRODUCTION", activation_mode="PRODUCTION")
    proj_a = fc.sizing_dependency_projection(inputs_a, tokens)
    proj_b = fc.sizing_dependency_projection(inputs_b, tokens)
    # Rollout metadata is not a declared dependency ⇒ dropped ⇒ byte-identical projection.
    assert "rollout_metadata" not in proj_a and "activation_mode" not in proj_a
    assert json.dumps(proj_a, sort_keys=True) == json.dumps(proj_b, sort_keys=True)
    # And the projection is exactly the declared, present dependency subset.
    assert set(proj_a) == set(base)


def test_f20_denies_a_missing_or_invalid_selected_policy(fc: ModuleType) -> None:
    assert fc.f20_selected_policy_deny_reason(None) == "MISSING_SELECTED_POLICY"
    assert fc.f20_selected_policy_deny_reason({}) == "MISSING_SELECTED_POLICY"
    assert fc.f20_selected_policy_deny_reason("POL-1") == "INVALID_SELECTED_POLICY"
    assert fc.f20_selected_policy_deny_reason({"policy_ref": "P"}) == "UNSIGNED_SELECTED_POLICY"
    assert fc.f20_selected_policy_deny_reason(
        {"policy_ref": "P", "signed": True, "stale": True}
    ) == "STALE_SELECTED_POLICY"
    # A present, signed, current policy is accepted (no DENY reason).
    assert fc.f20_selected_policy_deny_reason({"policy_ref": "P", "signed": True}) is None


def test_f20_rollout_invariance_fixture_is_vendored_verbatim(committed: dict, rc4: dict) -> None:
    fixture = committed["f20_rollout_invariance_fixture"]
    bundle = next(v for v in rc4["verifications"] if v.get("id") == "LEV-V-0120")
    assert fixture == bundle
    assert fixture["area"] == "F20"
    assert "rollout metadata is absent from formula dependencies" in fixture["expected"]


# ---------------------------------------------------------------------------
# Capability boundary: catalog-only, no executable money-line logic
# ---------------------------------------------------------------------------

def test_generator_imports_only_stdlib(fc: ModuleType) -> None:
    source = (TOOLS_DIR / "build_formula_catalog.py").read_text(encoding="utf-8")
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
        f"build_formula_catalog.py imports beyond the stdlib allowlist: "
        f"{sorted(roots - STDLIB_IMPORT_ALLOWLIST)}")


def test_no_money_line_sizing_maker_ioc_pnl_ships_in_runtime() -> None:
    """No src/triad_origin module implements F20-F23 sizing/maker/IOC/PnL (OUT_OF_REPO)."""
    offenders: list[str] = []
    for path in sorted(RUNTIME.rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in FORBIDDEN_MONEY_LINE_DEF.finditer(text):
            offenders.append(f"{path.relative_to(REPO_ROOT)}: {match.group(0)}")
    assert offenders == [], f"money-line def(s) leaked into the runtime: {offenders}"


def test_f00_qty_ingress_reservation_to_f20_f22_remains(fc: ModuleType) -> None:
    """The F00 ingress still refuses order-quantity floor-to-step (reserved to F20/F22).

    The catalog exists BECAUSE ORIGIN refuses to size: this pins the code-level boundary the
    catalog documents (a read-only assertion; the reservation is never relaxed by B09).
    """
    text = (RUNTIME / "instrument_math.py").read_text(encoding="utf-8")
    assert "quantity floor-to-step belongs to F20/F22" in text
    # And the catalog names F20/F22 as the (out-of-repo) owners of that quantity step.
    for fid in ("F20", "F22"):
        assert fid in fc.ESTATE_FORMULA_IDS
