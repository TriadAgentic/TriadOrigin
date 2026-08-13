"""The Part D formula-repair overlay artifact is well-formed and honest.

TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12 Part D + Part F exit criterion 3: every Part D
golden-vector row is replaced/added with a direct formula link, and the §1.5 version map names a
real repaired module for every repaired formula. This overlay is a SEPARATE artifact — CO-01: it
never mutates the RC3 effective control bundle bytes, and it arms nothing.
"""

from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
OVERLAY = ROOT / "docs" / "control" / "formula_repair_overlay.v1.json"
BUNDLE = ROOT / "docs" / "control" / "rc3_effective_control_bundle.json"

_FORMULA_ID = re.compile(r"^F[0-9]{2}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _overlay() -> dict:
    return json.loads(OVERLAY.read_text(encoding="utf-8"))


def test_overlay_is_a_separate_non_arming_artifact() -> None:
    o = _overlay()
    assert o["schema"] == "triad.origin.v7.formula_repair_overlay.v1"
    assert o["document_id"] == "TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12"
    assert "DOES_NOT_ARM" in o["authority"]
    assert "DOES_NOT_MUTATE_THE_RC3_EFFECTIVE_BUNDLE" in o["authority"]
    assert o["status"] == "REPAIR_CANDIDATE_NOT_ARMED"
    assert o["applies_to"]["mutates_base_bytes"] is False


def test_every_part_d_row_carries_a_direct_formula_link() -> None:
    ops = _overlay()["golden_vector_operations"]
    # Part D §D.1..D.6 — the exact repaired set.
    expected_ids = {
        "FR-GVOP-001a", "FR-GVOP-001b", "FR-GVOP-003", "FR-GVOP-013",
        "FR-GVOP-018", "FR-GVOP-F05-01", "FR-GVOP-F12-01", "FR-GVOP-F16-01",
    }
    assert {op["id"] for op in ops} == expected_ids
    for op in ops:
        assert _FORMULA_ID.match(op["linked_formula"]), op
        assert op["operation"] in {"SPLIT_FROM", "REPLACE", "ADD"}
        assert op["inputs"] and op["expected"]
        assert op["part_d_ref"].startswith("D.")
        # A REPLACE/SPLIT names its base row; an ADD must not.
        if op["operation"] == "ADD":
            assert op["source_vector_id"] is None
        else:
            assert op["source_vector_id"] and op["source_vector_id"].startswith("GV-")


def test_split_and_replace_source_ids_exist_in_the_base_bundle() -> None:
    bundle = json.loads(BUNDLE.read_text(encoding="utf-8"))
    base_ids = {row["id"] for row in bundle["golden_vectors"]}
    for op in _overlay()["golden_vector_operations"]:
        if op["source_vector_id"] is not None:
            assert op["source_vector_id"] in base_ids, \
                f"{op['id']} names {op['source_vector_id']} which is not a base golden row"


def test_the_repaired_set_covers_the_formulas_part_d_names() -> None:
    linked = {op["linked_formula"] for op in _overlay()["golden_vector_operations"]}
    # §D.1 F00, §D.2 F01, §D.3 F15, §D.4 F21, §D.5 F05, §D.6 F12 + F16.
    assert {"F00", "F01", "F05", "F12", "F15", "F16", "F21"} <= linked


def test_version_map_names_a_real_repaired_module_per_row() -> None:
    o = _overlay()
    rows = o["version_map"]
    formulas = {r["formula"] for r in rows}
    # Every §1.5 repaired formula id.
    assert {"F00", "F03", "F04", "F09", "F10", "F11",
            "F12", "F13", "F14", "F15", "F16", "F17", "F19"} <= formulas
    for r in rows:
        assert _FORMULA_ID.match(r["formula"]), r
        # An IMPLEMENTED row's repaired module must exist on disk.
        if r["status"] == "IMPLEMENTED":
            module_field = r["repaired_module"].split(" ")[0]  # strip parenthetical notes
            assert (ROOT / module_field).exists(), \
                f"{r['formula']} IMPLEMENTED but repaired module {module_field} is absent"


def test_the_normalized_ofi_identity_is_activation_off() -> None:
    # The one new separate identity created by Part D must be recorded activation-OFF (spec §0
    # rule 7 / R-F16): flow.ofi.best_norm.v1 is a research identity, never armed by this overlay.
    f16 = next(r for r in _overlay()["version_map"] if r["formula"] == "F16")
    assert "flow.ofi.best_norm.v1" in f16["repaired"]
    assert "activation OFF" in f16["repaired"]


def test_gv001b_and_gv018_are_owner_scoped_never_origin_executable() -> None:
    # F21 side-snap / observed-ladder are E09-owned; the overlay must never claim an Origin
    # executable home for them (order verbs are a forbidden capability in this repo).
    ops = {op["id"]: op for op in _overlay()["golden_vector_operations"]}
    assert ops["FR-GVOP-018"]["owner"] == "E09"
    assert "NONE_IN_ORIGIN" in ops["FR-GVOP-018"]["executable_home"]
    assert ops["FR-GVOP-001b"]["owner"] == "E09"


def test_gv003_watermark_arithmetic_stays_e01_owned() -> None:
    op = next(o for o in _overlay()["golden_vector_operations"] if o["id"] == "FR-GVOP-003")
    assert op["owner"] == "E01"
    assert "ORIGIN consumes/validates, never authors" in op["note"]


def test_version_map_strings_match_the_code_version_constants() -> None:
    """Drift-lock: an IMPLEMENTED row's `repaired`/`retired` version STRING must equal the
    repaired module's actual version constant — the F10 mislabel ('fvg.gap.v3' vs the real
    'fvg.three_bar.closed.v3') is the class this guard closes."""
    from triad_origin.structures import fvg_registry_v3, order_block_v2, reaction_v2
    from triad_origin.structures import break_v2, clustering_v2, flow_atoms_v2
    from triad_origin.structures import excursion_reclaim_v2
    rows = {r["formula"]: r for r in _overlay()["version_map"]}
    # (formula -> repaired-version-constant) for the modules that expose one cleanly.
    expected = {
        "F10": fvg_registry_v3.FORMULA_VERSION,          # fvg.three_bar.closed.v3
        "F09": break_v2.V2_FORMULA_VERSION,              # break.bar_close.v2
        "F12": order_block_v2.VERSION,                   # ob.displacement_bos.v2
        "F13": excursion_reclaim_v2.VERSION,             # level_excursion_reclaim.closed.v2
        "F14": reaction_v2.SEMANTIC_VERSION,             # reaction.first_touch.v2
        "F15": flow_atoms_v2.F15_FORMULA_VERSION,        # flow.tfi.window.v2
        "F16": flow_atoms_v2.F16_FORMULA_VERSION,        # flow.ofi.best.v2
        "F17": flow_atoms_v2.F17_FORMULA_VERSION,        # flow.book_tilt.band.v2
        "F19": clustering_v2.V2_FORMULA_VERSION,         # opportunity_cluster.v2
    }
    for fid, version in expected.items():
        # the overlay's `repaired` field leads with the version string (may carry a note after it)
        assert rows[fid]["repaired"].startswith(version), (
            fid, rows[fid]["repaired"], "!= code", version)
    # F10 retired must equal the repaired module's recorded predecessor.
    assert rows["F10"]["retired"] == fvg_registry_v3.RETIRED_PREDECESSOR_VERSION
