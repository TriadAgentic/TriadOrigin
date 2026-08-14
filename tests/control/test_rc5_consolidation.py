"""CO-01 — the post-RC4 effective-law compiler ``RC5_EFFECTIVE_CONSOLIDATION``.

TRIAD-ORIGIN-V7-CHANGE-ORDERS-2026-08-12 / CO-01. These tests are the acceptance +
Step-6 evidence for the compiler in ``docs/control/rc5_effective_consolidation.py``:

  * it is a SEPARATE artifact set that never mutates the RC3/RC4 bytes,
  * it applies exactly the ten RC4 supersessions as typed operations,
  * the three §5 build-fail assertions pass and the lever fields carry exactly the RC4 enums,
  * the conflict report covers exactly the ten families with before/after digests,
  * output is byte-stable across two independent runs (independent regeneration),
  * a planted superseded record is neutralized in RC5 (the downstream-safety proof),
  * a genuinely ambiguous supersession HALTS with a typed conflict while the other nine land,
  * it is DARK and arms nothing (posture OFF/OFF/OFF/LIVE, DENIED_SAFE_HOLD).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
from copy import deepcopy

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "docs" / "control" / "rc5_effective_consolidation.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("rc5_effective_consolidation", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


m = _load_module()


def _sha_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _compiled():
    return m.compile_rc5()  # (rc5, manifest, conflict, schema)


# --------------------------------------------------------------------------- #
# Separation + DARK posture.                                                   #
# --------------------------------------------------------------------------- #


def test_never_mutates_rc3_or_rc4_bytes() -> None:
    """CO-01 stop rule: RC3/RC4 bytes are read-only inputs; compiling touches neither."""
    rc3_before = _sha_file(m.RC3_BUNDLE_PATH)
    rc4_before = _sha_file(m.RC4_BUNDLE_PATH)
    m.compile_rc5()
    m.main()  # writes the rc5_* outputs
    assert _sha_file(m.RC3_BUNDLE_PATH) == rc3_before
    assert _sha_file(m.RC4_BUNDLE_PATH) == rc4_before


def test_bundle_is_dark_and_arms_nothing() -> None:
    rc5, _, _, _ = _compiled()
    prov = rc5["rc5_provenance"]
    assert prov["change_order"] == "CO-01"
    assert prov["posture"] == "OFF/OFF/OFF/LIVE"
    assert prov["activation_result"] == "DENIED_SAFE_HOLD"
    assert "DOES_NOT_ARM" in prov["authority"]
    assert "DOES_NOT_MUTATE_RC3_OR_RC4_BYTES" in prov["authority"]
    assert prov["consumption"] == "GATED_BEHIND_B01C"


def test_apply_does_not_mutate_its_inputs() -> None:
    rc3, rc4 = m.load_inputs()
    rc3_snapshot = m.canonical(rc3)
    rc4_snapshot = m.canonical(rc4)
    m.apply(rc3, rc4)
    assert m.canonical(rc3) == rc3_snapshot
    assert m.canonical(rc4) == rc4_snapshot


# --------------------------------------------------------------------------- #
# Preimages, families, assertions.                                            #
# --------------------------------------------------------------------------- #


def test_input_preimage_digests_are_recorded() -> None:
    _, manifest, _, _ = _compiled()
    pre = manifest["input_preimages"]
    assert pre["rc3_master_html"]["sha256"] == (
        "1a7f57265b707dceaa29fe09582cf6067dd5c438dcc4306de7d6900d4348f2c2"
    )
    assert pre["rc4_addendum_html"]["sha256"] == (
        "5db46aa6db02721b68fbf7c640a44db0b7a9ae2fac7423c80452a671fd9a7ff1"
    )
    # And they match the on-disk master bytes.
    assert _sha_file(m.RC3_HTML_PATH) == pre["rc3_master_html"]["sha256"]
    assert _sha_file(m.RC4_HTML_PATH) == pre["rc4_addendum_html"]["sha256"]


def test_all_ten_families_applied_zero_halted() -> None:
    _, manifest, conflict, _ = _compiled()
    assert manifest["supersession_families_expected"] == 10
    assert manifest["supersession_families_applied"] == 10
    assert manifest["supersession_families_halted"] == 0
    assert conflict["families_expected"] == 10
    assert len(conflict["families"]) == 10
    assert all(f["status"] == "APPLIED" for f in conflict["families"])


def test_conflict_report_covers_exactly_the_ten_families() -> None:
    _, _, conflict, _ = _compiled()
    families = {f["family"] for f in conflict["families"]}
    assert families == {
        "ADR-005-ENV-ENUM",
        "DEP-010-ALIAS-RETIREMENT",
        "GAP-006-MISMATCH-ONLY",
        "SEC-015-EXACT-BINDING",
        "F20-SINGLE-POLICY-SLOT",
        "C-027-ENGINE-CONTROL-MANIFEST-V2",
        "RC2-RECEIPT-SCHEMAS-STRICT-V2",
        "W06-G5-LEVER-VOCABULARY",
        "PAR-170-RENAME-ACTIVATION",
        "MCP-FAMILY-ACTIVATION-ENUM",
    }
    # every touched record carries distinct before/after digests
    for fam in conflict["families"]:
        for row in fam["records"]:
            assert len(row["before_digest"]) == 64
            assert len(row["after_digest"]) == 64
            assert row["before_digest"] != row["after_digest"]


def test_each_family_uses_a_typed_operation() -> None:
    _, _, conflict, _ = _compiled()
    typed = {
        m.OP_REPLACE_RECORD,
        m.OP_RENAME_PARAMETER,
        m.OP_REPLACE_SCHEMA,
        m.OP_RETIRE_VOCABULARY,
    }
    for fam in conflict["families"]:
        assert fam["operation"] in typed


def test_section5_assertions_all_pass() -> None:
    rc5, _, _, _ = _compiled()
    results = {a["assertion"]: a["result"] for a in rc5["rc5_provenance"]["assertions"]}
    assert results == {
        "no_activation_mode_budget_branch": "PASS",
        "no_ofi_variant_enabled_boolean": "PASS",
        "no_dark_vocabulary": "PASS",
        "lever_fields_exact_rc4_enums": "PASS",
    }


def test_no_superseded_token_survives_in_effective_fields() -> None:
    rc5, _, _, _ = _compiled()
    assert m._scan_effective(
        rc5, lambda s: "activation_mode" in s and ("CANARY" in s or "PRODUCTION" in s)
    ) == []
    assert m._scan_effective(rc5, lambda s: "OFI_NORMALIZED_VARIANT_ENABLED" in s) == []
    dark = ("connected-dark", "connected_dark", "prospective-dark", "prospective_dark")
    assert m._scan_effective(rc5, lambda s: any(t in s for t in dark)) == []


# --------------------------------------------------------------------------- #
# Per-supersession semantics.                                                  #
# --------------------------------------------------------------------------- #


def test_f20_branch_removed_but_budget_parameters_preserved() -> None:
    rc5, _, _, _ = _compiled()
    f20 = next(r for r in rc5["formulas"] if r["id"] == "F20")
    assert "activation_mode" not in f20["formula"]
    assert "already-selected signed risk-budget policy" in f20["formula"]
    # the original superseded text is preserved as evidence, not lost
    assert "activation_mode" in f20["rc5_superseded_evidence"]["formula"]
    assert f20["rc5_supersession"]["operation"] == m.OP_REPLACE_RECORD
    # the named budget PARAMETERS themselves are NOT deleted (only the selection branch)
    par069 = next(r for r in rc5["parameters"] if r["id"] == "PAR-069")
    assert "CANARY" in par069["name"]  # the budget policy still exists to be passed


def test_par170_renamed_value_off_ratification_preserved() -> None:
    rc5, _, _, _ = _compiled()
    par = next(r for r in rc5["parameters"] if r["id"] == "PAR-170")
    assert par["name"] == "OFI_NORMALIZED_VARIANT_ACTIVATION"
    assert par["symbol"] == "OFI_NORMALIZED_VARIANT_ACTIVATION"
    assert par["declared_value"] == "OFF"
    assert par["value_type"] == "lever_activation_enum(LIVE|OFF)"
    # separate ratification state is preserved verbatim
    assert par["status"] == "PROPOSED_RC2_MUST_RATIFY"
    assert par["rc5_supersession"]["operation"] == m.OP_RENAME_PARAMETER
    fpb = next(r for r in rc5["formula_parameter_bindings"] if r["binding_id"] == "FPB-0078")
    assert fpb["parameter_name"] == "OFI_NORMALIZED_VARIANT_ACTIVATION"


def test_c027_schema_rename_in_records_and_contract_union() -> None:
    rc5, _, _, _ = _compiled()
    scp = next(r for r in rc5["tasks"] if r["id"] == "SCP-0089")
    assert "activation_manifest.v1" not in scp["task"]
    assert "engine_control_manifest.v2" in scp["task"]
    union = rc5["rc3_extensions"]["contract_union"]
    assert "activation_manifest.v1" not in union
    assert "engine_control_manifest.v2" in union


def test_lever_vocabulary_installed_exactly_from_rc4() -> None:
    rc5, _, _, _ = _compiled()
    _, rc4 = m.load_inputs()
    lever = rc5["rc5_schema_installs"]["rc5_lever_vocabulary"]["effective"]
    assert lever["venue_environment_enum"] == rc4["lever_law"]["venue_environment_enum"]
    assert lever["activation_enum"] == rc4["lever_law"]["activation_enum"]
    assert lever["venue_environment_enum"] == ["LIVE", "TESTNET", "OFF"]
    assert lever["activation_enum"] == ["LIVE", "OFF"]


def test_mcp_family_target_enum_installed_history_preserved() -> None:
    rc5, _, _, _ = _compiled()
    mcp = rc5["rc5_schema_installs"]["rc5_mcp_family_activation"]["effective"]
    assert mcp["target_activation_enum"] == ["LIVE", "OFF"]
    assert mcp["legacy_booleans"] == "HISTORICAL_RAW_EVIDENCE_ONLY"
    assert "historical_live_mcp_snapshot" in mcp  # RC4 evidence retained


def test_receipt_schema_binding_is_strict_v2() -> None:
    rc5, _, _, _ = _compiled()
    binding = rc5["rc5_schema_installs"]["rc5_receipt_schema_binding"]["effective"]
    assert binding["authoritative"] == "strict_v2"
    assert binding["semantic_combination_validation"] is True


# --------------------------------------------------------------------------- #
# Determinism, on-disk parity, schema.                                        #
# --------------------------------------------------------------------------- #


def test_independent_regeneration_is_byte_stable() -> None:
    """CO-01 Step 6: two independent runs reproduce an identical output digest."""
    rc5_a, man_a, con_a, sch_a = m.compile_rc5()
    rc5_b, man_b, con_b, sch_b = m.compile_rc5()
    assert m.canonical(rc5_a) == m.canonical(rc5_b)
    assert man_a["output_digest"] == man_b["output_digest"]
    assert m.canonical(con_a) == m.canonical(con_b)
    assert m.canonical(sch_a) == m.canonical(sch_b)


def test_on_disk_outputs_match_in_memory_compile() -> None:
    m.main()
    rc5, manifest, conflict, schema = m.compile_rc5()
    assert json.loads(m.OUT_BUNDLE.read_text(encoding="utf-8")) == rc5
    assert json.loads(m.OUT_MANIFEST.read_text(encoding="utf-8")) == manifest
    assert json.loads(m.OUT_CONFLICT.read_text(encoding="utf-8")) == conflict
    assert json.loads(m.OUT_SCHEMA.read_text(encoding="utf-8")) == schema


def test_schema_is_draft_2020_12_with_required_keys() -> None:
    schema = m.build_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    for key in ("rc5_provenance", "rc5_schema_installs", "formulas", "parameters"):
        assert key in schema["required"]
    prov = schema["properties"]["rc5_provenance"]["properties"]
    assert prov["posture"]["const"] == "OFF/OFF/OFF/LIVE"
    assert prov["activation_result"]["const"] == "DENIED_SAFE_HOLD"
    assert prov["supersession_families_expected"]["const"] == 10


# --------------------------------------------------------------------------- #
# Step 6a — plant a superseded record and observe it neutralized.             #
# --------------------------------------------------------------------------- #


def test_planted_superseded_record_is_neutralized_in_rc5() -> None:
    """The downstream-safety proof: a fixture RC3 carrying superseded content is
    neutralized in the compiled RC5, with the original preserved as evidence."""
    rc3, rc4 = m.load_inputs()
    fixture = deepcopy(rc3)
    fixture["tasks"].append(
        {
            "id": "PLANT-F20-01",
            "task": "Planted superseded F20 branch",
            "implementation_instruction": (
                "Select B by activation_mode: CANARY->PAR-069, PRODUCTION->PAR-070, "
                "otherwise DENY. Then size."
            ),
        }
    )
    fixture["parameters"].append(
        {
            "id": "PLANT-PAR-01",
            "name": "OFI_NORMALIZED_VARIANT_ENABLED",
            "symbol": "OFI_NORMALIZED_VARIANT_ENABLED",
            "declared_value": "false",
            "unit": "boolean",
            "value_type": "boolean",
            "status": "PROPOSED_RC2_MUST_RATIFY",
        }
    )
    fixture["tasks"].append(
        {
            "id": "PLANT-W06-01",
            "task": "Planted dark vocabulary",
            "implementation_instruction": "Route via connected-dark exposure until promotion.",
        }
    )

    rc5, manifest, conflict = m.apply(fixture, rc4)
    assert manifest["supersession_families_halted"] == 0

    planted_f20 = next(r for r in rc5["tasks"] if r["id"] == "PLANT-F20-01")
    assert "activation_mode" not in planted_f20["implementation_instruction"]
    assert "activation_mode" in planted_f20["rc5_superseded_evidence"]["implementation_instruction"]

    planted_par = next(r for r in rc5["parameters"] if r["id"] == "PLANT-PAR-01")
    assert "OFI_NORMALIZED_VARIANT_ENABLED" not in m.canonical(
        {k: v for k, v in planted_par.items() if not m._is_historical_key(k)}
    )
    assert planted_par["name"] == "OFI_NORMALIZED_VARIANT_ACTIVATION"

    planted_w06 = next(r for r in rc5["tasks"] if r["id"] == "PLANT-W06-01")
    assert "connected-dark" not in planted_w06["implementation_instruction"]

    # And the whole bundle is clean under the §5 scans.
    assert m._scan_effective(rc5, lambda s: "OFI_NORMALIZED_VARIANT_ENABLED" in s) == []


# --------------------------------------------------------------------------- #
# Step (stop rule) — a genuinely ambiguous supersession HALTS, nine still land.#
# --------------------------------------------------------------------------- #


def test_ambiguous_supersession_halts_with_typed_conflict_nine_still_land() -> None:
    """CO-01 stop rule: an F20-triggered record whose exact superseded phrase is absent
    cannot be safely rewritten — its family HALTS with a typed conflict, the whole family
    rolls back, and the other nine supersessions still land."""
    rc3, rc4 = m.load_inputs()
    fixture = deepcopy(rc3)
    fixture["tasks"].append(
        {
            "id": "PLANT-AMBIG-01",
            "task": "Ambiguous activation_mode use with no known superseded phrase",
            "implementation_instruction": "Toggle activation_mode CANARY via an unknown route.",
        }
    )

    rc5, manifest, conflict = m.apply(fixture, rc4)

    assert manifest["supersession_families_halted"] == 1
    assert manifest["supersession_families_applied"] == 9
    halted = {h["family"] for h in manifest["halted_families"]}
    assert halted == {"F20-SINGLE-POLICY-SLOT"}

    fam = next(f for f in conflict["families"] if f["family"] == "F20-SINGLE-POLICY-SLOT")
    assert fam["status"] == "HALTED_TYPED_CONFLICT"
    assert "trigger token survives" in fam["conflict"]
    assert "PLANT-AMBIG-01" in fam["conflict"]
    assert fam["records_touched"] == 0

    # The other nine still applied.
    applied = {f["family"] for f in conflict["families"] if f["status"] == "APPLIED"}
    assert len(applied) == 9

    # The F20 family rolled back entirely — the real FORM-F20 records were NOT superseded.
    form = next(r for r in rc5["tasks"] if r["id"] == "FORM-F20-01")
    assert "rc5_supersession" not in form
    assert "activation_mode" in form["implementation_instruction"]

    # The halted family's §5 assertion is reported HALTED (not raised) — compiler lands.
    results = {a["assertion"]: a["result"] for a in rc5["rc5_provenance"]["assertions"]}
    assert results["no_activation_mode_budget_branch"] == "HALTED"
    # the other §5 assertions still PASS
    assert results["no_ofi_variant_enabled_boolean"] == "PASS"
    assert results["no_dark_vocabulary"] == "PASS"
    assert results["lever_fields_exact_rc4_enums"] == "PASS"


# --------------------------------------------------------------------------- #
# CO-03 additive-major contracts carried by RC5 (contract-union completeness). #
# --------------------------------------------------------------------------- #


def test_co03_additive_contracts_are_in_the_effective_union() -> None:
    rc5, _manifest, _conflict, _schema = _compiled()
    union = rc5["rc3_extensions"]["contract_union"]
    # The two CO-03 contracts that were declared as schemas but not yet folded into the union.
    assert "venue_execution_plan.v1" in union
    assert "transport_bindings.v1" in union
    # The four other CO-03 union schemas remain present.
    for c in ("evidence_view.v2", "raw_venue_event.v2",
              "runtime_lifecycle.v2", "signed_recommendation.v1"):
        assert c in union, c
    # It is recorded as a SEPARATE additive layer, never as an eleventh RC4 family.
    rec = rc5["rc3_extensions"]["rc5_co03_additive_contract_union"]
    assert rec["change_order"] == "CO-03"
    assert rec["layer"] == "ADDITIVE_MAJOR_NOT_AN_RC4_SUPERSESSION"
    assert set(rec["added"]) == {"venue_execution_plan.v1", "transport_bindings.v1"}
    prov = rc5["rc5_provenance"]
    assert set(prov["co03_additive_contracts_carried"]) == {
        "venue_execution_plan.v1", "transport_bindings.v1"}
    # The ten-family invariant is untouched by the additive layer.
    assert prov["supersession_families_expected"] == 10
    assert prov["supersession_families_applied"] == 10
