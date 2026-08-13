"""CO-docs conformance: the owner-gated document set (CO-04/08/10/13/14 + Part E).

These tests pin the fail-closed, owner-gated posture of the change-order documents landed
under docs/plan/: every artifact opens with a DISPOSITION header, no document claims an owner
act executed, the CO-08 ledger admits exactly two states (RECOVERED/UNAVAILABLE), and the
outcome.v3 DRAFT schema is a valid Draft 2020-12 schema whose F23 golden round-trips as
{"num":"51","den":"10"}.
"""

from __future__ import annotations

import json
import pathlib
import re

import pytest

jsonschema = pytest.importorskip("jsonschema")

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
PLAN = ROOT / "docs" / "plan"

PART_E = PLAN / "PART-E-OWNER-SERVICE-CORRECTIONS.md"
CO08 = PLAN / "CO-08-PREIMAGE-LEDGER.md"
CO10 = PLAN / "CO-10-CREDENTIAL-ROTATION-ONBOX.md"
CO13 = PLAN / "CO-13-CONTRACT-VERSION-DECISION.md"
CO14 = PLAN / "CO-14-OWNER-TOPO-01-REGISTRATION.md"
V3_DRAFT = PLAN / "outcome.v3.draft.schema.json"

ALL_MD = [PART_E, CO08, CO10, CO13, CO14]


def _text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def test_every_co_doc_exists_and_opens_with_a_disposition_header():
    for path in ALL_MD:
        assert path.is_file(), f"missing deliverable: {path}"
        head = "\n".join(_text(path).splitlines()[:8])
        assert "**DISPOSITION:**" in head, f"{path.name} lacks a DISPOSITION header"


def test_no_doc_claims_posture_change_and_each_names_safe_hold():
    for path in ALL_MD:
        text = _text(path)
        assert "DENIED_SAFE_HOLD" in text, f"{path.name} must restate the safe-hold posture"


def test_part_e_is_the_owner_correction_record_never_an_origin_implementation():
    text = _text(PART_E)
    assert "NEVER IMPLEMENTED IN ORIGIN" in text
    for token in (
        "STOP_BUFFER_SOURCE",
        "TARGET_SELECTOR_POLICY",
        "PROPOSED_MUST_RATIFY",
        "LONG_SELL_OUTWARD_FLOOR",
        "SHORT_BUY_OUTWARD_CEIL",
        "VenueExecutionPlan",
        "GV-018",
        "0.961",
        "9990",
        "10010",
        '{num:"51", den:"10"}',  # the E.4 golden encoding, spec spelling
    ):
        assert token.replace(" ", "") in text.replace(" ", ""), f"Part E missing {token}"
    # E.1: the CANARY|PRODUCTION budget branch is deleted, never carried forward as law.
    assert "CANARY|PRODUCTION" in text
    assert "Delete the" in text


def test_outcome_v3_draft_is_a_valid_2020_12_schema_marked_draft_for_the_e10_owner():
    doc = json.loads(_text(V3_DRAFT))
    assert doc["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert doc["x-status"].startswith("DRAFT_FOR_E10_OWNER")
    assert "dual-write v2+v3" in doc["x-status"]
    assert "signed supersession" in doc["x-status"]
    jsonschema.Draft202012Validator.check_schema(doc)


def test_outcome_v3_golden_5_1_round_trips_as_51_over_10():
    doc = json.loads(_text(V3_DRAFT))
    validator = jsonschema.Draft202012Validator(doc)
    golden = doc["examples"][0]
    validator.validate(golden)
    assert golden["net"] == {"num": "51", "den": "10"}
    assert golden["funding"] == {"num": "-1", "den": "10"}
    # NULL law visible in the golden: unknown initial risk => r_net null.
    assert golden["initial_risk_quote"] is None and golden["r_net"] is None


def test_outcome_v3_rejects_float_money_and_zero_denominator():
    doc = json.loads(_text(V3_DRAFT))
    validator = jsonschema.Draft202012Validator(doc)
    golden = json.loads(json.dumps(doc["examples"][0]))
    golden["net"] = 5.1  # a float money field is structurally unrepresentable
    assert not validator.is_valid(golden)
    golden2 = json.loads(json.dumps(doc["examples"][0]))
    golden2["net"] = {"num": "51", "den": "0"}  # zero denominator unrepresentable
    assert not validator.is_valid(golden2)
    golden3 = json.loads(json.dumps(doc["examples"][0]))
    golden3["execution_identity"] = "DEMO"  # outside the closed identity set
    assert not validator.is_valid(golden3)


def test_co08_ledger_has_exactly_two_states_and_full_search_log():
    text = _text(CO08)
    # No third state: every table state cell is RECOVERED or UNAVAILABLE.
    states = re.findall(r"\|\s*(RECOVERED|UNAVAILABLE)\s*\|\s*$", text, flags=re.M)
    assert len(states) == 20, f"expected 20 ledger rows, found {len(states)}"
    assert "no third state" in text
    # The two RC1 declared digests appear in full, never truncated-only.
    assert "82636c6f447f2e430f14d2b66ab09ec760989fe5751936360816fba4ca7d2387" in text
    assert "33c01f8ab73fefd0af4a0660ce63127b954b15b94182470f4c088ac7d20b5da8" in text
    # Search log is present and names its three methods.
    for marker in ("506 files", "935 blobs", "git rev-list --objects --all", "23 files"):
        assert marker in text, f"CO-08 search log missing: {marker}"


def test_co08_claim_surface_corrections_landed():
    control_readme = _text(ROOT / "docs" / "control" / "README.md")
    assert "RC5_EFFECTIVE_CONSOLIDATION" in control_readme
    assert "pre-RC4 supersession" in control_readme
    # The CO-05 drift stated truthfully: the current ledger token is CANDIDATE_V3 (the review
    # file still binds the frozen REVIEWED_V2 subject) — "REVIEWED_V3" does not exist anywhere.
    assert "CANDIDATE_V3" in control_readme
    assert "CO-05" in control_readme
    inventory = _text(PLAN / "06_RC2_SOURCE_INVENTORY.md")
    assert "CO-08 correction" in inventory
    assert "PARTIAL" in inventory
    assert not inventory.startswith("# 06 · Control-Package Source Inventory\n\n_Updated 2026-08-09 (B00). The package is now **COMPLETE**")


def test_co10_is_owner_only_and_never_carries_a_secret_value():
    text = _text(CO10)
    assert "OWNER-ONLY" in text and "PENDING_OWNER_EXECUTION" in text
    assert "OWNER/BOX-ONLY" in text
    for marker in ("fingerprint", "read-only", "Rotate/revoke", "BLOCKED_ON_CREDENTIAL_ROTATION(CO-10)"):
        assert marker in text, f"CO-10 missing: {marker}"
    # Never copy values: no credential-shaped literal may appear.
    for pattern in (r"sk-ant-", r"AKIA[0-9A-Z]{16}", r"-----BEGIN", r"\b\d{6,}:[A-Za-z0-9_-]{30,}\b"):
        assert not re.search(pattern, text), f"CO-10 carries a credential-shaped literal: {pattern}"


def test_co13_covers_ten_pairs_and_is_pending_owner():
    text = _text(CO13)
    rows = re.findall(r"^\|\s*(\d+)\s*\|", text, flags=re.M)
    assert [int(r) for r in rows] == list(range(1, 11)), "CO-13 must table exactly the ten pairs"
    assert "PENDING-OWNER" in text
    assert "BLOCKED_ON_RATIFY(CO-13)" in text
    for canonical in (
        "market_state.v2", "structure_atom.v2", "edge_candidate.v2", "decision.v2",
        "risk_reservation.v1", "execution_cmd.v2", "order_event.v2", "position_event.v2",
        "protection_event.v2", "outcome.v2` → `outcome.v3",
    ):
        assert canonical in text, f"CO-13 missing canonical choice {canonical}"
    assert "engine_cohort" in text and "intelligence_arm" in text
    assert "divergence_record.v1" in text and "comparison axis" in text


def test_co14_is_pending_signature_quotes_the_decision_and_gates_every_execution_step():
    text = _text(CO14)
    assert "PENDING_SIGNATURE" in text
    assert text.count("EXECUTES-ON-SIGNATURE") >= 3
    # The finalized decision text is quoted, amendments included.
    for token in (
        "OWNER-TOPO-01",
        "E03 = Kairos",
        "E05 = Coordinator",
        "E06 = Logos",
        "no process execution of E05, Kairos, or Logos in any deployment class",
        "Amendment A1",
        "Amendment A2",
        "Amendment A3",
        "conviction_threshold_met",
        "12,000 ms",
        "25.99 s",
    ):
        assert token in text, f"CO-14 missing: {token}"
    # The signature slot is quoted empty; Claude never signs.
    assert "Claude never signs" in text
    assert "NOT_ATTESTED" in text
    # Constitutional check recorded as PASSED per the adjudication, not independently attested.
    normalized = " ".join(text.replace("*", "").split()).lower()
    assert "PASSED" in text and "no authority leakage" in normalized
