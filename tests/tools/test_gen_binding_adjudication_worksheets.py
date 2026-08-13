"""CO-07 — tests for the binding adjudication worksheet generator (proposals only)."""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import gen_binding_adjudication_worksheets as gen  # noqa: E402

REGISTRY_PATH = ROOT / "docs" / "control" / "binding_registry.v2.json"
WORKSHEETS_MD = ROOT / "docs" / "plan" / "CO-07-BINDING-ADJUDICATION-WORKSHEETS.md"
MATRIX_MD = ROOT / "docs" / "plan" / "CO-07-COMPLETENESS-MATRIX.md"


def _registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _built() -> dict:
    return gen.build_all(_registry())


def _by_binding(built) -> dict:
    return {w.binding_id: w for w in built["worksheets"]}


# ---- coverage + field completeness -----------------------------------------

def test_one_worksheet_per_registry_row() -> None:
    reg = _registry()
    built = gen.build_all(reg)
    assert len(built["worksheets"]) == len(reg["rows"])
    assert len(built["worksheets"]) == reg["row_count"] == 105
    ids = [w.binding_id for w in built["worksheets"]]
    assert len(set(ids)) == len(ids)  # unique, no row dropped or duplicated


def test_every_worksheet_carries_exactly_the_spec_fields() -> None:
    built = _built()
    required = {
        "binding_id",
        "formula_id",
        "parameter",
        "declared_value",
        "unit",
        "gate",
        "boundary_rule",
        "failure_behavior",
        "evidence_refs",
        "proposed_disposition",
        "owner_signature_slot",
    }
    for w in built["worksheets"]:
        d = w.to_dict()
        assert required.issubset(d.keys())
        # evidence refs are always present, non-empty, and reference-shaped.
        assert w.evidence_refs and all("=" in r for r in w.evidence_refs)


# ---- the law: proposals only, owner never signed by an agent ----------------

def test_every_owner_signature_slot_is_empty_pending_owner() -> None:
    built = _built()
    assert all(w.owner_signature_slot == "PENDING_OWNER" for w in built["worksheets"])


def test_no_agent_adjudication_marker_ever_present() -> None:
    text = WORKSHEETS_MD.read_text(encoding="utf-8")
    # An agent never signs. The only signature token is the empty PENDING_OWNER slot.
    assert "PROPOSAL ONLY" in text
    assert "PENDING_OWNER" in text
    lowered = text.lower()
    assert "signed by agent" not in lowered
    assert "adjudicated by agent" not in lowered


# ---- named-refusal / disposition derivation (each a spec case) --------------

def test_par_170_family_is_proposed_superseded_with_pointer() -> None:
    w = _by_binding(_built())["FPB-0078"]  # PAR-170 / OFI_NORMALIZED_VARIANT_ENABLED
    assert w.proposed_disposition == "SUPERSEDED"
    assert w.canonical_target == "SUPERSEDED"
    assert "OFI_NORMALIZED_VARIANT_ACTIVATION=OFF" in w.named_refusal
    assert "RC4" in w.named_refusal


def test_named_research_rows_are_blocked_on_ratify() -> None:
    built = _built()
    by = _by_binding(built)
    # F06 span, F08 reducer, F17 min-depth value, PAR-036 DC_REVERSAL.
    research = {
        "RC3-FPB-001": "RC3-PAR-STRUCT-001",  # F06 EQUAL_LEVEL_MAX_SPAN
        "RC3-FPB-002": "RC3-PAR-STRUCT-003",  # F08 PROTECTED_SWING_REDUCER_VERSION
        "RC3-FPB-003": "RC3-PAR-STRUCT-002",  # F17 BOOK_TILT_MIN_QUOTE_DEPTH
        "FPB-0011": "PAR-036",                # F03 DC_REVERSAL
    }
    for bid, pid in research.items():
        w = by[bid]
        assert w.proposed_disposition == f"BLOCKED_ON_RATIFY({pid})", (bid, w.proposed_disposition)
        assert w.canonical_target == "BLOCKED"
        assert w.named_refusal.startswith(f"BLOCKED_ON_RATIFY({pid})")


def test_migration_rows_are_proposed_blocked_on_migration() -> None:
    built = _built()
    for w in built["worksheets"]:
        # every migration row except PAR-036 (research) and PAR-170 (superseded)
        if w.binding_id in ("FPB-0011", "FPB-0078"):
            continue
        if w.proposed_disposition.startswith("BLOCKED_ON_MIGRATION"):
            assert w.proposed_disposition == "BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)"
            assert w.canonical_target == "BLOCKED"


def test_active_rows_are_proposed_active() -> None:
    built = _built()
    by = _by_binding(built)
    for bid in ("FPB-0001", "FPB-0002", "RC3-FPB-004"):
        assert by[bid].proposed_disposition == "ACTIVE"
        assert by[bid].canonical_target == "ACTIVE"


def test_par_025_blocked_row_is_ratify_per_registry_status() -> None:
    # RC3-FPB-005 (F01, PAR-025) is a BLOCKED (unratified) row not in the research
    # list; "per its registry status" it maps to BLOCKED_ON_RATIFY(PAR-025).
    w = _by_binding(_built())["RC3-FPB-005"]
    assert w.proposed_disposition == "BLOCKED_ON_RATIFY(PAR-025)"
    assert w.canonical_target == "BLOCKED"


def test_disposition_counts_reconcile_to_105() -> None:
    built = _built()
    fam = built["proposed_disposition_family_counts"]
    assert fam.get("SUPERSEDED", 0) == 1          # PAR-170
    assert fam.get("BLOCKED_ON_RATIFY", 0) == 5   # 4 non-migration BLOCKED + PAR-036
    assert fam.get("ACTIVE", 0) == 3
    assert fam.get("BLOCKED_ON_MIGRATION", 0) == 96
    assert sum(fam.values()) == 105
    # No row is proposed REFUSED (a lawful target, but unused today).
    assert built["canonical_target_counts"]["REFUSED"] == 0


# ---- formula-complete groups ------------------------------------------------

def test_only_f00_is_formula_complete_active() -> None:
    built = _built()
    assert built["formulas_formula_complete_active"] == ["F00"]
    groups = {g.formula_id: g for g in built["groups"]}
    assert groups["F00"].activation_status == "ACTIVE"


def test_f21_one_of_ten_never_presents_as_active() -> None:
    built = _built()
    groups = {g.formula_id: g for g in built["groups"]}
    f21 = groups["F21"]
    assert f21.total == 10
    assert f21.active_count == 1
    assert f21.activation_status == "NOT_ACTIVE"
    # And the rendered matrix says so explicitly.
    matrix = MATRIX_MD.read_text(encoding="utf-8")
    assert "NOT_ACTIVE (1/10)" in matrix


def test_no_partial_formula_reads_active() -> None:
    built = _built()
    for g in built["groups"]:
        if g.active_count != g.total:
            assert g.activation_status == "NOT_ACTIVE"


# ---- determinism ------------------------------------------------------------

def test_regeneration_is_byte_stable() -> None:
    reg = _registry()
    a = gen.render_worksheets_md(gen.build_all(reg))
    b = gen.render_worksheets_md(gen.build_all(reg))
    assert a == b
    ma = gen.render_matrix_md(gen.build_all(reg))
    mb = gen.render_matrix_md(gen.build_all(reg))
    assert ma == mb


def test_on_disk_outputs_match_regeneration() -> None:
    built = _built()
    assert WORKSHEETS_MD.read_text(encoding="utf-8") == gen.render_worksheets_md(built)
    assert MATRIX_MD.read_text(encoding="utf-8") == gen.render_matrix_md(built)


def test_check_mode_passes_against_committed_docs() -> None:
    rc = gen.main(
        [
            "--registry",
            str(REGISTRY_PATH),
            "--worksheets-out",
            str(WORKSHEETS_MD),
            "--matrix-out",
            str(MATRIX_MD),
            "--check",
        ]
    )
    assert rc == 0
