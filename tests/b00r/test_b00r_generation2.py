"""Focused invariants for the B00R generation-1 to generation-2 correction."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import subprocess
import sys

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import governance  # noqa: E402
from tools import validate_authority_root as authority  # noqa: E402


GENERATION_1_RECEIPT = "evidence/receipts/B00R.receipt.v3.json"
GENERATION_1_TRUST = "evidence/B00R/receipt_trust_registry.v1.json"
GENERATION_LEDGER = "docs/governance/B00R_GENERATION_LEDGER.v1.json"
POLICY_V2 = "docs/control/b00r_policy.v2.json"
PROFILE_1 = "docs/governance/decisions/DEC-RECEIPT-PROFILE-001.template.json"
PROFILE_2 = "docs/governance/decisions/DEC-RECEIPT-PROFILE-002.template.json"
REPAIR_2 = "docs/governance/decisions/DEC-B00-REPAIR-002.template.json"
AUTHORITY_2 = "docs/governance/decisions/DEC-AUTHORITY-BUNDLE-002.template.json"
TRUST_2_TEMPLATE = "docs/governance/trust/receipt_trust_registry.g2.v1.template.json"


def _json(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def _sha256(relative_path: str) -> str:
    return hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest()


def _git_rev_parse(revision: str) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", revision], cwd=ROOT, text=True,
    ).strip()


def _validate_generation_1_receipt(receipt: dict, **kwargs) -> tuple[str, str]:
    trust = governance.validate_trust_registry(_json(GENERATION_1_TRUST))
    return governance.validate_receipt_v3(
        receipt,
        milestone="B00R",
        trust=trust,
        now_us=receipt["payload"]["emitted_at_us"],
        verify_fn=authority.ed25519_verify,
        **kwargs,
    )


def test_generation_1_receipt_requires_explicit_generation_1_expectation():
    receipt = _json(GENERATION_1_RECEIPT)

    assert _validate_generation_1_receipt(
        receipt, expected_root_generation=1,
    ) == (governance.RESULT_PASS, "OK")

    # Generation 2 is the validator default; the mechanically authentic historical receipt is no
    # longer eligible to close the current B00R repair.
    assert _validate_generation_1_receipt(receipt) == (
        "FAIL", "ROOT_REPAIR_GENERATION_MISMATCH",
    )
    assert _validate_generation_1_receipt(
        receipt, expected_root_generation=2,
    ) == ("FAIL", "ROOT_REPAIR_GENERATION_MISMATCH")


def test_generation_2_receipt_shape_cannot_be_accepted_as_generation_1():
    generation_2 = copy.deepcopy(_json(GENERATION_1_RECEIPT))
    generation_2["payload"]["repair_generation"] = 2

    assert _validate_generation_1_receipt(
        generation_2, expected_root_generation=1,
    ) == ("FAIL", "ROOT_REPAIR_GENERATION_MISMATCH")


def test_generation_1_receipt_profile_cannot_be_reused_for_generation_2():
    with pytest.raises(
        governance.GovernanceError,
        match="RECEIPT_PROFILE_TRUST_PATH_MISMATCH",
    ):
        governance.receipt_profile_from_decision(
            _json(PROFILE_1), repair_generation=2,
        )


def test_generation_2_profile_has_exact_receipt_root_and_anchor():
    profile = _json(PROFILE_2)
    scope = profile["scope"]

    assert profile["decision_id"] == "DEC-RECEIPT-PROFILE-002"
    assert profile["supersedes"] == ["DEC-RECEIPT-PROFILE-001"]
    assert scope["repair_generation"] == 2
    assert scope["receipt_path"] == "evidence/receipts/B00R.g2.receipt.v3.json"
    assert scope["evidence_root"] == "evidence/B00R_G2"
    assert scope["trust_registry"] == \
        "docs/governance/trust/receipt_trust_registry.g2.v1.json"
    assert scope["closure_anchor_mechanism"] == (
        "protected annotated tag B00R_RECEIPT_ANCHOR_G2 plus externally pinned active "
        "no-update/no-delete/no-bypass tag ruleset"
    )
    assert governance.receipt_profile_from_decision(
        profile, repair_generation=2,
    ) == (2, ("EVIDENCE_PRODUCER", "INDEPENDENT_COUNTERSIGNER"), "ed25519")


def test_generation_2_authority_profile_selects_generation_2_decisions_and_pins():
    subjects, canonical_paths = authority._authority_profile(2)  # noqa: SLF001

    assert subjects["authority_bundle"][:2] == (
        "AUTHORITY_BUNDLE_G2_DECISION_SHA256",
        "DEC-AUTHORITY-BUNDLE-002",
    )
    assert subjects["authority_bundle"][3] == ROOT / AUTHORITY_2

    assert subjects["receipt_profile"][:2] == (
        "RECEIPT_PROFILE_G2_DECISION_SHA256",
        "DEC-RECEIPT-PROFILE-002",
    )
    assert subjects["b00_repair"][:2] == (
        "B00R_G2_REPAIR_DECISION_SHA256",
        "DEC-B00-REPAIR-002",
    )
    assert subjects["trust_registry"][0] == "RECEIPT_G2_TRUST_REGISTRY_SHA256"
    assert subjects["trust_registry"][3] == ROOT / TRUST_2_TEMPLATE
    assert canonical_paths["receipt_profile"] == (
        "docs/governance/decisions/DEC-RECEIPT-PROFILE-002.json"
    )
    assert canonical_paths["b00_repair"] == (
        "docs/governance/decisions/DEC-B00-REPAIR-002.json"
    )
    assert canonical_paths["authority_bundle"] == (
        "docs/governance/decisions/DEC-AUTHORITY-BUNDLE-002.json"
    )
    assert subjects["authority_bundle"][0] != authority.SUBJECTS["authority_bundle"][0]
    assert subjects["receipt_profile"][0] != authority.SUBJECTS["receipt_profile"][0]
    assert subjects["b00_repair"][0] != authority.SUBJECTS["b00_repair"][0]
    g2_trust = _json(TRUST_2_TEMPLATE)
    owner = next(key for key in g2_trust["keys"] if key["role"] == "AUTHORITY_OWNER")
    assert owner["scope"] == (
        "DEC-AUTHORITY-BUNDLE-002,DEC-RECEIPT-PROFILE-002,DEC-B00-REPAIR-002"
    )


def test_policy_ledger_and_generation_1_immutable_bindings_are_consistent():
    policy = _json(POLICY_V2)
    ledger = _json(GENERATION_LEDGER)
    repair = _json(REPAIR_2)
    profile = _json(PROFILE_2)
    old_receipt = _json(GENERATION_1_RECEIPT)
    generation_1 = ledger["generation_1"]
    generation_2 = ledger["generation_2"]
    repair_subjects = repair["subject_sha256s"]

    old_receipt_digest = _sha256(GENERATION_1_RECEIPT)
    old_anchor_object = _git_rev_parse("B00R_RECEIPT_ANCHOR")
    old_anchor_target = _git_rev_parse("B00R_RECEIPT_ANCHOR^{}")

    assert policy["schema"] == "triad.origin.b00r_policy.v2"
    assert policy["repair_generation"] == 2
    assert policy["generation_1_disposition"] == generation_1["disposition"] \
        == "MERGED_UNVERIFIED"
    assert policy["generation_ledger"] == GENERATION_LEDGER
    assert repair_subjects["generation_ledger"] == _sha256(GENERATION_LEDGER)
    assert repair_subjects["policy_v2"] == _sha256(POLICY_V2)
    assert policy["main_ruleset_law"] == {
        "allowed_merge_methods": ["merge"],
        "bypass_actors": [],
        "current_user_can_bypass": "never",
        "do_not_enforce_on_create": False,
        "excluded_refs": [],
        "provider": "github",
        "pull_request_required": True,
        "required_status_check_context": "test-and-verify",
        "required_status_check_integration_id": 15368,
        "repository": "TriadAgentic/TriadOrigin",
        "strict_required_status_checks_policy": True,
        "target_refs": ["refs/heads/main", "refs/heads/b00r-ruleset-canary"],
    }

    assert old_receipt["payload"]["repair_generation"] == 1
    assert old_receipt_digest == generation_1["receipt_sha256"] \
        == repair_subjects["generation_1_receipt_sha256"]
    assert old_receipt["payload"]["source_pr"] == 27
    assert generation_1["source_pr"] == 31
    assert "RECEIPT_SOURCE_PR_MISMATCH" in generation_1["reason_codes"]

    assert old_anchor_object == generation_1["anchor_tag_object_sha"] \
        == repair_subjects["generation_1_anchor_object_sha"]
    assert old_anchor_target == generation_1["anchor_target_sha"] \
        == generation_1["receipt_merge_sha"]
    assert repair["scope"]["generation_1_anchor"] == (
        f"B00R_RECEIPT_ANCHOR@{old_anchor_target}"
    )

    assert policy["audited_start_sha"] == generation_2["audited_start_sha"] \
        == repair_subjects["audited_start_sha"] == old_anchor_target
    assert repair["scope"]["audited_start"] == f"main@{old_anchor_target}"
    assert policy["closure_anchor"]["id"] == generation_2["anchor_tag"] \
        == "B00R_RECEIPT_ANCHOR_G2"
    assert policy["closure_anchor"]["receipt_path"] == generation_2["receipt_path"] \
        == profile["scope"]["receipt_path"]
    assert policy["closure_anchor"]["evidence_root"] == generation_2["evidence_root"] \
        == profile["scope"]["evidence_root"]
