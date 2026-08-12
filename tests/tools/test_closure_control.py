from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import closure_control as cc  # noqa: E402


@pytest.fixture(scope="module")
def semantics_schema() -> dict:
    return cc.load_json_object(ROOT / cc.SEMANTICS_SCHEMA_REL)


@pytest.fixture(scope="module")
def status_schema() -> dict:
    return cc.load_json_object(ROOT / cc.STATUS_SCHEMA_REL)


@pytest.fixture(scope="module")
def status_events_schema() -> dict:
    return cc.load_json_object(ROOT / cc.STATUS_EVENTS_SCHEMA_REL)


@pytest.fixture(scope="module")
def task_binding_schema() -> dict:
    return cc.load_json_object(ROOT / cc.TASK_BINDING_SCHEMA_REL)


@pytest.fixture(scope="module")
def semantics() -> dict:
    return cc.load_canonical_object(ROOT / cc.SEMANTICS_REL)


@pytest.fixture(scope="module")
def status() -> dict:
    return cc.load_canonical_object(ROOT / cc.STATUS_REL)


@pytest.fixture(scope="module")
def status_events() -> dict:
    return cc.load_canonical_object(ROOT / cc.STATUS_EVENTS_REL)


@pytest.fixture(scope="module")
def task_bindings() -> dict:
    return cc.load_canonical_object(ROOT / cc.TASK_BINDING_REL)


@pytest.fixture(scope="module")
def policy() -> dict:
    return cc.load_json_object(ROOT / cc.B00R_POLICY_REL)


def _rehash(document: dict, domain: str) -> dict:
    document["digest"]["value"] = cc.compute_envelope_digest(document, domain)
    return document


def _error(code: str):
    return pytest.raises(cc.ClosureControlError, match=rf"^{code}:")


def _without_c0_receipt_review_slot(semantics: dict) -> dict:
    reconciled = copy.deepcopy(semantics)
    c0_identity = reconciled["payload"]["milestones"][0]["identity"]
    c0_slots = next(
        row for row in reconciled["payload"]["review_policy"]["milestone_slots"]
        if row["milestone_identity"] == c0_identity
    )
    c0_slots["slots"] = [
        slot for slot in c0_slots["slots"] if slot["role_id"] != "RECEIPT_REVIEWER"
    ]
    return _rehash(reconciled, cc.SEMANTICS_DOMAIN)


def test_repository_control_bundle_passes_and_check_is_read_only() -> None:
    paths = (
        ROOT / cc.SEMANTICS_SCHEMA_REL,
        ROOT / cc.SEMANTICS_REL,
        ROOT / cc.STATUS_SCHEMA_REL,
        ROOT / cc.STATUS_REL,
        ROOT / cc.STATUS_EVENTS_SCHEMA_REL,
        ROOT / cc.STATUS_EVENTS_REL,
        ROOT / cc.TASK_BINDING_SCHEMA_REL,
        ROOT / cc.TASK_BINDING_REL,
        ROOT / cc.STATUS_DOC_REL,
        ROOT / cc.CHECKLIST_DOC_REL,
        ROOT / cc.B00R_POLICY_REL,
    )
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    result = cc.check_all(ROOT)
    assert result["milestones"] == 14
    assert result["decisions"] == 9
    assert result["conflicts"] == 14
    assert result["profiles"] == 10
    assert result["test_layers"] == 13
    assert result["task_bindings"] == 1250
    assert result["status_events"] == 4
    assert result["open_blockers"] > 0
    assert cc.main(["--check", "--root", str(ROOT)]) == 0
    after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    assert after == before


def test_control_artifacts_are_exact_canonical_json(tmp_path: pathlib.Path, semantics: dict) -> None:
    canonical_path = tmp_path / "canonical.json"
    canonical_path.write_bytes(cc.canonical_json(semantics))
    assert cc.load_canonical_object(canonical_path) == semantics

    pretty_path = tmp_path / "pretty.json"
    pretty_path.write_text(json.dumps(semantics, indent=2), encoding="utf-8")
    with _error("NONCANONICAL_CONTROL_ARTIFACT"):
        cc.load_canonical_object(pretty_path)

    duplicate_path = tmp_path / "duplicate.json"
    duplicate_path.write_text('{"a":1,"a":2}', encoding="utf-8")
    with _error("NONCANONICAL_CONTROL_ARTIFACT"):
        cc.load_canonical_object(duplicate_path)


def test_schema_is_self_validated_as_draft_2020_12(
    semantics: dict, semantics_schema: dict
) -> None:
    broken = copy.deepcopy(semantics_schema)
    broken["properties"]["payload"]["type"] = 7
    with _error("SCHEMA_SELF_VALIDATION_FAILED"):
        cc.validate_schema(broken, semantics, "broken")

    wrong_dialect = copy.deepcopy(semantics_schema)
    wrong_dialect["$schema"] = "http://json-schema.org/draft-07/schema#"
    with _error("WRONG_JSON_SCHEMA_DIALECT"):
        cc.validate_schema(wrong_dialect, semantics, "wrong dialect")

    unknown = copy.deepcopy(semantics)
    unknown["payload"]["unknown_control"] = True
    _rehash(unknown, cc.SEMANTICS_DOMAIN)
    with _error("SCHEMA_INSTANCE_INVALID"):
        cc.validate_semantics(unknown, semantics_schema)


def test_envelope_digest_tamper_is_rejected(semantics: dict, semantics_schema: dict) -> None:
    tampered = copy.deepcopy(semantics)
    tampered["payload"]["program"] += "_TAMPER"
    with _error("SCHEMA_INSTANCE_INVALID"):
        cc.validate_semantics(tampered, semantics_schema)

    tampered = copy.deepcopy(semantics)
    tampered["payload"]["decisions"][0]["controlling_rule"] += " tamper"
    with _error("ARTIFACT_DIGEST_MISMATCH"):
        cc.validate_semantics(tampered, semantics_schema)


def test_scope_digest_and_composite_identity_are_recomputed(
    semantics: dict, semantics_schema: dict
) -> None:
    tampered = copy.deepcopy(semantics)
    b00r = tampered["payload"]["milestones"][1]
    b00r["scope"]["scope_text"] += " tamper"
    _rehash(tampered, cc.SEMANTICS_DOMAIN)
    with _error("SCOPE_DIGEST_MISMATCH"):
        cc.validate_semantics(tampered, semantics_schema)

    tampered = copy.deepcopy(semantics)
    tampered["payload"]["milestones"][1]["identity"] = "ORIGIN_REPAIR::B00R_G2::sha256:" + "a" * 64
    _rehash(tampered, cc.SEMANTICS_DOMAIN)
    with _error("COMPOSITE_IDENTITY_MISMATCH"):
        cc.validate_semantics(tampered, semantics_schema)

    uppercase = copy.deepcopy(semantics)
    uppercase["payload"]["milestones"][1]["scope_digest"]["value"] = (
        uppercase["payload"]["milestones"][1]["scope_digest"]["value"].upper()
    )
    _rehash(uppercase, cc.SEMANTICS_DOMAIN)
    with _error("SCHEMA_INSTANCE_INVALID"):
        cc.validate_semantics(uppercase, semantics_schema)


def test_bare_milestone_identifier_is_refused(semantics: dict, semantics_schema: dict) -> None:
    tampered = copy.deepcopy(semantics)
    tampered["payload"]["milestones"][1]["identity"] = "B00R"
    _rehash(tampered, cc.SEMANTICS_DOMAIN)
    with _error("SCHEMA_INSTANCE_INVALID"):
        cc.validate_semantics(tampered, semantics_schema)


def test_milestone_set_predecessors_and_dag_are_closed(
    semantics: dict, semantics_schema: dict
) -> None:
    duplicate = copy.deepcopy(semantics)
    duplicate["payload"]["milestones"][2] = copy.deepcopy(duplicate["payload"]["milestones"][1])
    _rehash(duplicate, cc.SEMANTICS_DOMAIN)
    with _error("DUPLICATE_MILESTONE"):
        cc.validate_semantics(duplicate, semantics_schema)

    wrong_predecessor = copy.deepcopy(semantics)
    wrong_predecessor["payload"]["milestones"][2]["predecessor_identity"] = wrong_predecessor[
        "payload"
    ]["milestones"][0]["identity"]
    _rehash(wrong_predecessor, cc.SEMANTICS_DOMAIN)
    with _error("PREDECESSOR_CHAIN_MISMATCH"):
        cc.validate_semantics(wrong_predecessor, semantics_schema)

    cyclic = copy.deepcopy(semantics)
    first = cyclic["payload"]["milestones"][0]
    last_identity = cyclic["payload"]["milestones"][-1]["identity"]
    first["dependency_identities"] = [last_identity]
    _rehash(cyclic, cc.SEMANTICS_DOMAIN)
    with _error("MILESTONE_DEPENDENCY_CYCLE"):
        cc.validate_semantics(cyclic, semantics_schema)

    redirected = copy.deepcopy(semantics)
    b10 = redirected["payload"]["milestones"][-2]
    b10["path_law"] = {
        "adoption_manifest": "attacker/B10.manifest.v1.json",
        "anchor": "ATTACKER_B10_ANCHOR",
        "source_receipt": "attacker/B10.receipt.v4.json",
    }
    b10_control = redirected["payload"]["b10_terminal_control"]["receipt_anchor_law"]
    b10_control["receipt_path"] = b10["path_law"]["source_receipt"]
    b10_control["required_anchor"] = b10["path_law"]["anchor"]
    b10_profile = next(
        row for row in redirected["payload"]["acceptance_profiles"]
        if row["profile_id"] == "B10_ACCEPTANCE_PROFILE_V1"
    )
    b10_profile["adoption_manifest"] = b10["path_law"]["adoption_manifest"]
    with _error("MILESTONE_PATH_LAW_DIGEST_MISMATCH"):
        cc.validate_milestones(redirected)


def test_decisions_d01_through_d09_are_exact_and_not_cryptographically_overclaimed(
    semantics: dict, semantics_schema: dict
) -> None:
    duplicate = copy.deepcopy(semantics)
    duplicate["payload"]["decisions"][-1]["decision_id"] = "D-08"
    _rehash(duplicate, cc.SEMANTICS_DOMAIN)
    with _error("DECISION_SET_OR_ORDER_MISMATCH"):
        cc.validate_semantics(duplicate, semantics_schema)

    overclaim = copy.deepcopy(semantics)
    overclaim["payload"]["authority"]["cryptographic_authentication"] = "AUTHENTICATED"
    _rehash(overclaim, cc.SEMANTICS_DOMAIN)
    with _error("SCHEMA_INSTANCE_INVALID"):
        cc.validate_semantics(overclaim, semantics_schema)


def test_p0_p1_non_waiver_law_is_mandatory(semantics: dict, semantics_schema: dict) -> None:
    tampered = copy.deepcopy(semantics)
    tampered["payload"]["state_machine"]["blocked_rule"] = "Ordinary summary counts decide."
    _rehash(tampered, cc.SEMANTICS_DOMAIN)
    with _error("P0_P1_NON_WAIVER_LAW_MISSING"):
        cc.validate_semantics(tampered, semantics_schema)


def test_acceptance_profiles_have_closed_work_and_attack_sets(
    semantics: dict, semantics_schema: dict
) -> None:
    duplicate = copy.deepcopy(semantics)
    duplicate["payload"]["acceptance_profiles"][-1]["profile_id"] = duplicate["payload"][
        "acceptance_profiles"
    ][-2]["profile_id"]
    _rehash(duplicate, cc.SEMANTICS_DOMAIN)
    with _error("ACCEPTANCE_PROFILE_SET_MISMATCH"):
        cc.validate_semantics(duplicate, semantics_schema)

    unsorted = copy.deepcopy(semantics)
    profile = unsorted["payload"]["acceptance_profiles"][0]
    profile["work_packages"] = list(reversed(profile["work_packages"]))
    if profile["work_packages"] == sorted(set(profile["work_packages"])):
        profile["work_packages"].append(profile["work_packages"][0])
    _rehash(unsorted, cc.SEMANTICS_DOMAIN)
    with _error("SET_FIELD_NOT_CANONICAL"):
        cc.validate_semantics(unsorted, semantics_schema)

    b10 = copy.deepcopy(semantics)
    b10["payload"]["acceptance_profiles"][-1]["required_independent_reviews"] = 1
    _rehash(b10, cc.SEMANTICS_DOMAIN)
    with _error("PROFILE_REVIEW_QUORUM_MISMATCH"):
        cc.validate_semantics(b10, semantics_schema)

    milestones = cc.validate_milestones(semantics)
    cc.validate_profiles(semantics, milestones)
    b10_rewrite = copy.deepcopy(semantics)
    b10_profile = next(
        row for row in b10_rewrite["payload"]["acceptance_profiles"]
        if row["profile_id"] == "B10_ACCEPTANCE_PROFILE_V1"
    )
    b10_profile["attack_vectors"][0] = "provider chronology and evidence tampering"
    with _error("B10_ACCEPTANCE_PROFILE_DIGEST_MISMATCH"):
        cc.validate_profiles(b10_rewrite, milestones)


@pytest.mark.parametrize(
    "bad_path",
    ("/absolute/artifact.json", "../escape.json", "", "contracts//not-canonical.json"),
)
def test_profile_required_artifact_paths_are_canonical_repo_relative(
    semantics: dict, bad_path: str
) -> None:
    tampered = copy.deepcopy(semantics)
    tampered["payload"]["acceptance_profiles"][0]["required_artifacts"][0] = bad_path
    milestones = cc.validate_milestones(tampered)
    with _error("PROFILE_REQUIRED_ARTIFACT_PATH_INVALID"):
        cc.validate_profiles(tampered, milestones)


def test_xc01_is_explicit_and_blocks_b08_b09_bn(
    semantics: dict, semantics_schema: dict
) -> None:
    cc.validate_semantics(_without_c0_receipt_review_slot(semantics), semantics_schema)
    rows = {row["scope"]["milestone_id"]: row for row in semantics["payload"]["milestones"]}
    xc01 = rows["XC01"]
    assert xc01["scope"]["track_id"] == "ESTATE_CROSS_REPO"
    assert rows["B08"]["predecessor_identity"] == xc01["identity"]
    assert xc01["identity"] in rows["B09"]["dependency_identities"]
    assert xc01["identity"] in rows["BN"]["dependency_identities"]
    profile = next(
        row for row in semantics["payload"]["acceptance_profiles"]
        if row["profile_id"] == "XC01_ACCEPTANCE_PROFILE_V1"
    )
    assert {slot["receipt_slot_id"] for slot in profile["owner_repo_receipt_slots"]} == {
        "XC01-E08-F20", "XC01-E09-F21-F22", "XC01-E10-F23",
    }
    assert all(slot["provider_binding_state"] == "UNBOUND" for slot in profile["owner_repo_receipt_slots"])
    assert all(slot["attestation_state"] == "NOT_ATTESTED" for slot in profile["owner_repo_receipt_slots"])

    missing_direct_dependency = copy.deepcopy(semantics)
    mutated_rows = {
        row["scope"]["milestone_id"]: row
        for row in missing_direct_dependency["payload"]["milestones"]
    }
    mutated_rows["B09"]["dependency_identities"] = [mutated_rows["B08"]["identity"]]
    _rehash(missing_direct_dependency, cc.SEMANTICS_DOMAIN)
    with _error("XC01_DIRECT_DEPENDENCY_LAW_MISMATCH"):
        cc.validate_semantics(missing_direct_dependency, semantics_schema)

    wrong_receipt = copy.deepcopy(semantics)
    wrong_rows = {
        row["scope"]["milestone_id"]: row
        for row in wrong_receipt["payload"]["milestones"]
    }
    wrong_rows["XC01"]["path_law"]["source_receipt"] = "evidence/receipts/wrong.json"
    _rehash(wrong_receipt, cc.SEMANTICS_DOMAIN)
    with _error("MILESTONE_PATH_LAW_DIGEST_MISMATCH"):
        cc.validate_semantics(wrong_receipt, semantics_schema)

    wrong_bn_aggregate = copy.deepcopy(semantics)
    wrong_rows = {
        row["scope"]["milestone_id"]: row
        for row in wrong_bn_aggregate["payload"]["milestones"]
    }
    wrong_rows["BN"]["aggregate_receipt_dependencies"][0]["anchor"] = "WRONG_ANCHOR"
    _rehash(wrong_bn_aggregate, cc.SEMANTICS_DOMAIN)
    with _error("BN_XC01_RECEIPT_AGGREGATE_MISMATCH"):
        cc.validate_semantics(wrong_bn_aggregate, semantics_schema)


def test_review_policy_is_closed_and_unbound(semantics: dict, semantics_schema: dict) -> None:
    reconciled = _without_c0_receipt_review_slot(semantics)
    cc.validate_semantics(reconciled, semantics_schema)
    policy = reconciled["payload"]["review_policy"]
    roles = {row["role_id"] for row in policy["role_registry"]}
    assert {
        "AUTHOR", "EVIDENCE_PRODUCER", "OWNER_DECISION_SIGNER", "RESULT_PRODUCER"
    } <= roles
    assert all(
        slot["binding_state"] == "UNBOUND" and slot["provider_binding"] is None
        for row in policy["milestone_slots"] for slot in row["slots"]
    )
    c0_identity = reconciled["payload"]["milestones"][0]["identity"]
    c0_slots = next(
        row["slots"] for row in policy["milestone_slots"]
        if row["milestone_identity"] == c0_identity
    )
    assert {slot["role_id"] for slot in c0_slots} == {
        "C0_OWNER_AUTHENTICATOR", "SOURCE_REVIEWER",
    }

    stale_c0_receipt_slot = copy.deepcopy(reconciled)
    stale_slots = next(
        row["slots"]
        for row in stale_c0_receipt_slot["payload"]["review_policy"]["milestone_slots"]
        if row["milestone_identity"] == c0_identity
    )
    stale_slots.append({
        "binding_state": "UNBOUND",
        "eligible_hint": None,
        "provider_binding": None,
        "role_id": "RECEIPT_REVIEWER",
    })
    with _error("REVIEW_SLOT_ROLE_SET_INVALID"):
        cc.validate_review_policy(stale_c0_receipt_slot, cc.validate_milestones(stale_c0_receipt_slot))

    missing_receipt_slot = copy.deepcopy(reconciled)
    b00r_slots = missing_receipt_slot["payload"]["review_policy"]["milestone_slots"][1]
    b00r_slots["slots"] = [
        slot for slot in b00r_slots["slots"] if slot["role_id"] != "RECEIPT_REVIEWER"
    ]
    with _error("REVIEW_SLOT_ROLE_SET_INVALID"):
        cc.validate_review_policy(missing_receipt_slot, cc.validate_milestones(missing_receipt_slot))

    missing_role = copy.deepcopy(reconciled)
    missing_role["payload"]["review_policy"]["role_registry"] = missing_role["payload"]["review_policy"]["role_registry"][:-1]
    _rehash(missing_role, cc.SEMANTICS_DOMAIN)
    with _error("SCHEMA_INSTANCE_INVALID"):
        cc.validate_semantics(missing_role, semantics_schema)
    with _error("REVIEW_CONTROLLING_ENTITY_ALIAS"):
        cc.validate_role_identity_bindings(
            policy,
            {"OWNER_DECISION_SIGNER": "provider-account-17", "SOURCE_REVIEWER": "provider-account-17"},
        )
    with _error("REVIEW_CONTROLLING_ENTITY_ALIAS"):
        cc.validate_role_identity_bindings(
            policy,
            {"RESULT_PRODUCER": "provider-account-23", "B10_RUNTIME_SIDE_EFFECT_AUDITOR": "provider-account-23"},
        )


def test_b10_control_is_nonzero_closed_and_acyclic(
    semantics: dict, semantics_schema: dict
) -> None:
    milestones = cc.validate_milestones(semantics)
    cc.validate_b10_terminal_control(semantics, milestones)
    control = semantics["payload"]["b10_terminal_control"]
    assert control["tasks"] and control["criteria"] and control["verifications"]
    assert len(control["audit_roles"]) == 2
    cyclic = copy.deepcopy(semantics)
    tasks = cyclic["payload"]["b10_terminal_control"]["tasks"]
    tasks[0]["dependency_task_ids"] = [tasks[-1]["task_id"]]
    with _error("B10_TASK_DEPENDENCY_CYCLE"):
        cc.validate_b10_terminal_control(cyclic, milestones)

    criterion_reused = copy.deepcopy(semantics)
    criterion_tasks = criterion_reused["payload"]["b10_terminal_control"]["tasks"]
    criterion_tasks[1]["criterion_ids"] = list(criterion_tasks[0]["criterion_ids"])
    with _error("B10_TASK_CRITERION_CONSUMPTION_MISMATCH"):
        cc.validate_b10_terminal_control(criterion_reused, milestones)

    verification_reused = copy.deepcopy(semantics)
    verification_tasks = verification_reused["payload"]["b10_terminal_control"]["tasks"]
    verification_tasks[1]["verification_ids"] = list(verification_tasks[0]["verification_ids"])
    with _error("B10_TASK_VERIFICATION_CONSUMPTION_MISMATCH"):
        cc.validate_b10_terminal_control(verification_reused, milestones)

    verification_criterion_reused = copy.deepcopy(semantics)
    verifications = verification_criterion_reused["payload"]["b10_terminal_control"][
        "verifications"
    ]
    verifications[1]["criterion_ids"] = list(verifications[0]["criterion_ids"])
    with _error("B10_VERIFICATION_CRITERION_CONSUMPTION_MISMATCH"):
        cc.validate_b10_terminal_control(verification_criterion_reused, milestones)

    multiple_terminals = copy.deepcopy(semantics)
    multiple_terminals["payload"]["b10_terminal_control"]["tasks"][-1][
        "dependency_task_ids"
    ] = []
    with _error("B10_TERMINAL_TASK_SET_MISMATCH"):
        cc.validate_b10_terminal_control(multiple_terminals, milestones)

    wrong_path = copy.deepcopy(semantics)
    wrong_path["payload"]["b10_terminal_control"]["receipt_anchor_law"]["receipt_path"] = "wrong.json"
    with _error("B10_RECEIPT_ANCHOR_LAW_MISMATCH"):
        cc.validate_b10_terminal_control(wrong_path, milestones)

    wrong_anchor = copy.deepcopy(semantics)
    wrong_anchor["payload"]["b10_terminal_control"]["receipt_anchor_law"]["required_anchor"] = "WRONG_ANCHOR"
    with _error("B10_RECEIPT_ANCHOR_LAW_MISMATCH"):
        cc.validate_b10_terminal_control(wrong_anchor, milestones)

    text_rewrite = copy.deepcopy(semantics)
    text_rewrite["payload"]["b10_terminal_control"]["criteria"][0]["text"] += " rewritten"
    with _error("B10_TERMINAL_CONTROL_DIGEST_MISMATCH"):
        cc.validate_b10_terminal_control(text_rewrite, milestones)


def test_blocker_catalog_is_an_exact_nonerasable_control_set(
    semantics: dict, semantics_schema: dict
) -> None:
    for blocker_id in (
        "LEGACY_B00_REALLOCATION_REQUIRED", "B00R-G2-AUTHORITY-PINS",
        "B05-AUTHORIZATION", "BN-FRESH-AGGREGATE",
    ):
        deleted = copy.deepcopy(semantics)
        deleted["payload"]["blocker_catalog"] = [
            row for row in deleted["payload"]["blocker_catalog"]
            if row["blocker_id"] != blocker_id
        ]
        _rehash(deleted, cc.SEMANTICS_DOMAIN)
        with _error("BLOCKER_CATALOG_SET_MISMATCH"):
            cc.validate_semantics(deleted, semantics_schema)

    changed = copy.deepcopy(semantics)
    row = next(
        item for item in changed["payload"]["blocker_catalog"]
        if item["blocker_id"] == "B05-AUTHORIZATION"
    )
    row["provenance_ref"] = "lower-precedence narrative"
    _rehash(changed, cc.SEMANTICS_DOMAIN)
    with _error("BLOCKER_CATALOG_SPEC_MISMATCH"):
        cc.validate_semantics(changed, semantics_schema)

    owner_changed = copy.deepcopy(semantics)
    row = next(
        item for item in owner_changed["payload"]["blocker_catalog"]
        if item["blocker_id"] == "BN-FRESH-AGGREGATE"
    )
    row["owner_identity"] = owner_changed["payload"]["milestones"][0]["identity"]
    _rehash(owner_changed, cc.SEMANTICS_DOMAIN)
    with _error("BLOCKER_CATALOG_SPEC_MISMATCH"):
        cc.validate_semantics(owner_changed, semantics_schema)


def test_test_matrix_is_complete_for_every_milestone_and_profile(
    semantics: dict, semantics_schema: dict
) -> None:
    empty_row = copy.deepcopy(semantics)
    empty_row["payload"]["test_layer_matrix"][0]["layers"] = {
        layer: "NOT_APPLICABLE" for layer in cc.EXPECTED_TEST_LAYERS
    }
    _rehash(empty_row, cc.SEMANTICS_DOMAIN)
    with _error("TEST_MATRIX_EMPTY_ROW"):
        cc.validate_semantics(empty_row, semantics_schema)

    no_external = copy.deepcopy(semantics)
    profile_identity = no_external["payload"]["acceptance_profiles"][0]["milestone_identity"]
    row = next(
        item
        for item in no_external["payload"]["test_layer_matrix"]
        if item["milestone_identity"] == profile_identity
    )
    row["layers"] = {
        layer: ("CUMULATIVE" if mode == "EXTERNAL" else mode)
        for layer, mode in row["layers"].items()
    }
    _rehash(no_external, cc.SEMANTICS_DOMAIN)
    with _error("PROFILE_TEST_MATRIX_MISMATCH"):
        cc.validate_semantics(no_external, semantics_schema)

    reduced = copy.deepcopy(semantics)
    b09 = next(
        profile
        for profile in reduced["payload"]["acceptance_profiles"]
        if profile["profile_id"] == "B09_ACCEPTANCE_PROFILE_V1"
    )
    b09["targeted_tests"] = ["T0"]
    _rehash(reduced, cc.SEMANTICS_DOMAIN)
    with _error("PROFILE_TEST_MATRIX_MISMATCH"):
        cc.validate_semantics(reduced, semantics_schema)

    unknown = copy.deepcopy(semantics)
    unknown["payload"]["acceptance_profiles"][0]["targeted_tests"] = ["Z_NOT_A_LAYER"]
    _rehash(unknown, cc.SEMANTICS_DOMAIN)
    with _error("SCHEMA_INSTANCE_INVALID"):
        cc.validate_semantics(unknown, semantics_schema)

    external_reduction = copy.deepcopy(semantics)
    profile = external_reduction["payload"]["acceptance_profiles"][0]
    profile["external_tests"] = profile["external_tests"][:-1]
    _rehash(external_reduction, cc.SEMANTICS_DOMAIN)
    with _error("PROFILE_TEST_MATRIX_MISMATCH"):
        cc.validate_semantics(external_reduction, semantics_schema)

    receipt_layer_mismatch = copy.deepcopy(semantics)
    receipt_layer_mismatch["payload"]["test_layer_matrix"][0]["layers"]["T7"] = "EXTERNAL"
    _rehash(receipt_layer_mismatch, cc.SEMANTICS_DOMAIN)
    with _error("RECEIPT_APPLICABILITY_MISMATCH"):
        cc.validate_semantics(receipt_layer_mismatch, semantics_schema)

    receipt_path_mismatch = copy.deepcopy(semantics)
    receipt_path_mismatch["payload"]["milestones"][0]["path_law"]["source_receipt"] = (
        "evidence/receipts/C0.receipt.v1.json"
    )
    _rehash(receipt_path_mismatch, cc.SEMANTICS_DOMAIN)
    with _error("MILESTONE_PATH_LAW_DIGEST_MISMATCH"):
        cc.validate_semantics(receipt_path_mismatch, semantics_schema)


def test_legacy_crosswalk_rejects_duplicate_legacy_and_unknown_current_identity(
    semantics: dict, semantics_schema: dict
) -> None:
    tampered = copy.deepcopy(semantics)
    tampered["payload"]["legacy_crosswalk"][1]["legacy_ref"] = tampered["payload"][
        "legacy_crosswalk"
    ][0]["legacy_ref"]
    _rehash(tampered, cc.SEMANTICS_DOMAIN)
    with _error("LEGACY_CROSSWALK_SET_OR_ORDER_MISMATCH"):
        cc.validate_semantics(tampered, semantics_schema)

    tampered = copy.deepcopy(semantics)
    tampered["payload"]["legacy_crosswalk"][1]["current_identity"] = (
        "ORIGIN_REPAIR::B01C::sha256:" + "a" * 64
    )
    _rehash(tampered, cc.SEMANTICS_DOMAIN)
    with _error("LEGACY_CROSSWALK_TARGET_INVALID"):
        cc.validate_semantics(tampered, semantics_schema)


def test_legacy_crosswalk_is_complete_and_receipts_are_machine_bound(
    semantics: dict, semantics_schema: dict
) -> None:
    rows = semantics["payload"]["legacy_crosswalk"]
    assert [row["legacy_ref"] for row in rows] == list(cc.EXPECTED_LEGACY_BINDINGS)
    assert {"B08", "B09", "B10"} <= {row["legacy_ref"] for row in rows}
    assert sum(row["historical_receipt_path"] is not None for row in rows) == 12

    receipt_tamper = copy.deepcopy(semantics)
    row = next(item for item in receipt_tamper["payload"]["legacy_crosswalk"] if item["legacy_ref"] == "B07")
    row["historical_receipt_sha256"] = "a" * 64
    _rehash(receipt_tamper, cc.SEMANTICS_DOMAIN)
    with _error("LEGACY_RECEIPT_BINDING_MISMATCH"):
        cc.validate_semantics(receipt_tamper, semantics_schema)

    valid_identity_alias = copy.deepcopy(semantics)
    rows_by_ref = {
        item["legacy_ref"]: item for item in valid_identity_alias["payload"]["legacy_crosswalk"]
    }
    rows_by_ref["B01"]["current_identity"] = rows_by_ref["BN"]["current_identity"]
    _rehash(valid_identity_alias, cc.SEMANTICS_DOMAIN)
    with _error("LEGACY_CROSSWALK_TARGET_INVALID"):
        cc.validate_semantics(valid_identity_alias, semantics_schema)

    missing_b10 = copy.deepcopy(semantics)
    missing_b10["payload"]["legacy_crosswalk"] = [
        row for row in missing_b10["payload"]["legacy_crosswalk"] if row["legacy_ref"] != "B10"
    ]
    _rehash(missing_b10, cc.SEMANTICS_DOMAIN)
    with _error("SCHEMA_INSTANCE_INVALID"):
        cc.validate_semantics(missing_b10, semantics_schema)


def test_status_is_bound_to_semantics_and_has_zero_closed_claims(
    status: dict, status_schema: dict, semantics: dict
) -> None:
    semantics_digest = cc.compute_envelope_digest(semantics, cc.SEMANTICS_DOMAIN)
    wrong_reference = copy.deepcopy(status)
    wrong_reference["payload"]["semantics_reference"]["digest_sha256"] = "a" * 64
    _rehash(wrong_reference, cc.STATUS_DOMAIN)
    with _error("STATUS_SEMANTICS_DIGEST_MISMATCH"):
        cc.validate_status(wrong_reference, status_schema, semantics, semantics_digest)

    closed = copy.deepcopy(status)
    closed["payload"]["closed_claims"] = ["C0"]
    _rehash(closed, cc.STATUS_DOMAIN)
    with _error("SCHEMA_INSTANCE_INVALID"):
        cc.validate_status(closed, status_schema, semantics, semantics_digest)


def test_status_work_gate_runtime_and_activation_remain_safe_hold(
    status: dict, status_schema: dict, semantics: dict
) -> None:
    semantics_digest = cc.compute_envelope_digest(semantics, cc.SEMANTICS_DOMAIN)
    wrong_work = copy.deepcopy(status)
    wrong_work["payload"]["milestones"][0]["work_state"] = "NOT_STARTED"
    _rehash(wrong_work, cc.STATUS_DOMAIN)
    with _error("STATUS_WORK_STATE_MISMATCH"):
        cc.validate_status(wrong_work, status_schema, semantics, semantics_digest)

    activation = copy.deepcopy(status)
    activation["payload"]["activation_posture"]["venue_activation"] = "LIVE"
    _rehash(activation, cc.STATUS_DOMAIN)
    with _error("SCHEMA_INSTANCE_INVALID"):
        cc.validate_status(activation, status_schema, semantics, semantics_digest)


def test_task_bindings_cover_all_1250_rows_exactly_once(
    task_bindings: dict, task_binding_schema: dict, semantics: dict
) -> None:
    cc.validate_task_bindings(task_bindings, task_binding_schema, semantics, ROOT)
    rows = task_bindings["payload"]["rows"]
    assert len(rows) == len({row["legacy_task_id"] for row in rows}) == 1250
    assert not any(
        "::C0::" in str(row["target"]) or "::B00R_G2::" in str(row["target"])
        for row in rows
    )
    assert all(
        row["target"] == {
            "disposition_id": "LEGACY_B00_REALLOCATION_REQUIRED",
            "kind": "BLOCKING_DISPOSITION",
        }
        for row in rows if row["legacy_milestone"] == "B00"
    )
    payload = task_bindings["payload"]
    assert payload["review_subject_ledger"] == {
        "byte_sha256": cc.EXPECTED_REVIEW_SUBJECT_SHA256,
        "ledger_version": "REVIEWED_V2",
        "path": "docs/control/closure/predecessors/build_ledger.REVIEWED_V2.json",
        "row_count": 1250,
        "source_commit": cc.EXPECTED_REVIEW_SUBJECT_COMMIT,
    }
    assert payload["review_coverage"]["changed_row_count"] == 94
    assert payload["review_coverage"]["unchanged_row_count"] == 1156
    assert payload["review_coverage"]["current_ledger_review_state"] == "UNBOUND"
    assert payload["allocation_summary"]["unallocated_task_count"] == 97
    assert payload["allocation_summary"]["target_allocation_review_state"] == "UNBOUND"

    duplicate = copy.deepcopy(task_bindings)
    duplicate["payload"]["rows"][1] = copy.deepcopy(duplicate["payload"]["rows"][0])
    _rehash(duplicate, cc.TASK_BINDING_DOMAIN)
    with _error("TASK_BINDING_EXACTLY_ONCE_SET_MISMATCH"):
        cc.validate_task_bindings(duplicate, task_binding_schema, semantics, ROOT)

    digest_tamper = copy.deepcopy(task_bindings)
    digest_tamper["payload"]["rows"][0]["source_row_digest"] = "a" * 64
    _rehash(digest_tamper, cc.TASK_BINDING_DOMAIN)
    with _error("TASK_BINDING_SOURCE_ROW_DIGEST_MISMATCH"):
        cc.validate_task_bindings(digest_tamper, task_binding_schema, semantics, ROOT)

    changed_review_overclaim = copy.deepcopy(task_bindings)
    changed_row = next(
        row for row in changed_review_overclaim["payload"]["rows"]
        if row["source_review_state"] == "CHANGED_REVIEW_REQUIRED"
    )
    changed_row["source_review_state"] = "UNCHANGED_SINCE_REVIEW_SUBJECT"
    _rehash(changed_review_overclaim, cc.TASK_BINDING_DOMAIN)
    with _error("TASK_BINDING_ROW_REVIEW_STATE_MISMATCH"):
        cc.validate_task_bindings(
            changed_review_overclaim, task_binding_schema, semantics, ROOT
        )


def test_formula_tasks_have_one_canonical_owner(
    task_bindings: dict, task_binding_schema: dict, semantics: dict
) -> None:
    cc.validate_task_bindings(task_bindings, task_binding_schema, semantics, ROOT)
    formula_targets: dict[str, set[str]] = {f"F{number:02d}": set() for number in range(24)}
    for row in task_bindings["payload"]["rows"]:
        match = cc.re.fullmatch(r"FORM-(F(?:0[0-9]|1[0-9]|2[0-3]))-[0-9]+", row["legacy_task_id"])
        if match:
            formula_targets[match.group(1)].add(str(row["target"]))
    assert all(len(targets) == 1 for targets in formula_targets.values())

    by_id = {row["legacy_task_id"]: row["target"] for row in task_bindings["payload"]["rows"]}
    identity_by_id = {
        row["scope"]["milestone_id"]: row["identity"]
        for row in semantics["payload"]["milestones"]
    }
    assert by_id["FORM-F01-01"] == {
        "attestation_state": "NOT_ATTESTED",
        "conformance_milestone_identity": identity_by_id["B02C"],
        "formula_id": "F01",
        "kind": "FORMULA_EXTERNAL_OWNER_RECEIPT",
        "owner_engine": "E01",
        "owner_receipt_slot_id": "B02C-E01-F01",
        "provider_binding_state": "UNBOUND",
        "receipt_milestone_identity": identity_by_id["B02C"],
    }
    assert by_id["FORM-F07-01"]["owner_receipt_slot_id"] == "B03C-E01-F07"
    assert by_id["FORM-F20-01"]["receipt_milestone_identity"] == identity_by_id["XC01"]
    assert by_id["FORM-F20-01"]["conformance_milestone_identity"] == identity_by_id["B09"]
    assert by_id["FORM-F14-01"]["implementation_milestone_identity"] == identity_by_id["B04C"]
    assert by_id["FORM-F14-01"]["consumer_milestone_identities"] == [identity_by_id["B06R"]]

    wrong_owner = copy.deepcopy(task_bindings)
    row = next(
        item for item in wrong_owner["payload"]["rows"]
        if item["legacy_task_id"] == "FORM-F01-01"
    )
    row["target"]["owner_engine"] = "E08"
    _rehash(wrong_owner, cc.TASK_BINDING_DOMAIN)
    with _error("TASK_BINDING_TARGET_MISMATCH"):
        cc.validate_task_bindings(wrong_owner, task_binding_schema, semantics, ROOT)

    with _error("FORMULA_TASK_NAMESPACE_INVALID"):
        cc._formula_task_identity({
            "id": "FORM-F24-01", "row_class": "FORMULA_ATOMIC", "milestone": "B06"
        })


def test_status_event_chain_and_state_machine_fail_closed(
    status_events: dict, status_events_schema: dict, semantics: dict
) -> None:
    semantics_digest = cc.compute_envelope_digest(semantics, cc.SEMANTICS_DOMAIN)
    _, states = cc.validate_status_events(
        status_events, status_events_schema, semantics, semantics_digest
    )
    identities = [row["identity"] for row in semantics["payload"]["milestones"]]
    assert [states[identity] for identity in identities[:2]] == [
        "SOURCE_IN_PROGRESS", "SOURCE_IN_PROGRESS"
    ]
    assert all(states[identity] == "NOT_STARTED" for identity in identities[2:])

    rewritten = copy.deepcopy(status_events)
    rewritten["payload"]["events"][1]["previous_event_digest"] = "a" * 64
    _rehash(rewritten, cc.STATUS_EVENTS_DOMAIN)
    with _error("STATUS_EVENT_CHAIN_MISMATCH"):
        cc.validate_status_events(rewritten, status_events_schema, semantics, semantics_digest)

    rechained = copy.deepcopy(status_events)
    rechained["payload"]["events"][0]["evidence_refs"] = ["rewritten diagnostic evidence"]
    previous = None
    for event in rechained["payload"]["events"]:
        event["previous_event_digest"] = previous
        event["event_digest"] = cc._status_event_digest(event)
        previous = event["event_digest"]
    rechained["payload"]["chain_head_sha256"] = previous
    _rehash(rechained, cc.STATUS_EVENTS_DOMAIN)
    with _error("STATUS_EVENT_FROZEN_PREFIX_REWRITTEN"):
        cc.validate_status_events(rechained, status_events_schema, semantics, semantics_digest)

    co_mutated_semantics = copy.deepcopy(semantics)
    co_mutated_events = copy.deepcopy(rechained)
    rewritten_digests = [
        event["event_digest"] for event in co_mutated_events["payload"]["events"]
    ]
    anchor = co_mutated_semantics["payload"]["status_event_prefix_anchor"]
    anchor["event_digests"] = rewritten_digests
    anchor["chain_head_sha256"] = rewritten_digests[-1]
    _rehash(co_mutated_semantics, cc.SEMANTICS_DOMAIN)
    co_mutated_events["payload"]["semantics_digest_sha256"] = co_mutated_semantics["digest"]["value"]
    _rehash(co_mutated_events, cc.STATUS_EVENTS_DOMAIN)
    with _error("STATUS_EVENT_PREFIX_ANCHOR_INVALID"):
        cc.validate_semantics(co_mutated_semantics, cc.load_json_object(ROOT / cc.SEMANTICS_SCHEMA_REL))

    illegal = copy.deepcopy(status_events)
    event = {
        "event_digest": "",
        "event_type": "WORK_TRANSITION",
        "evidence_refs": ["illegal close attempt"],
        "from_state": "SOURCE_IN_PROGRESS",
        "milestone_identity": identities[0],
        "previous_event_digest": illegal["payload"]["chain_head_sha256"],
        "satisfied_requirements": ["receipt merged anchor published and terminal gate passes"],
        "sequence": 4,
        "to_state": "CLOSED",
    }
    event["event_digest"] = cc._status_event_digest(event)
    illegal["payload"]["events"].append(event)
    illegal["payload"]["event_count"] = 5
    illegal["payload"]["chain_head_sha256"] = event["event_digest"]
    _rehash(illegal, cc.STATUS_EVENTS_DOMAIN)
    with _error("STATUS_EVENT_ILLEGAL_TRANSITION"):
        cc.validate_status_events(illegal, status_events_schema, semantics, semantics_digest)

    placeholder = copy.deepcopy(status_events)
    placeholder["payload"]["events"][0]["evidence_refs"] = ["PLACEHOLDER"]
    _rehash(placeholder, cc.STATUS_EVENTS_DOMAIN)
    with _error("SCHEMA_INSTANCE_INVALID"):
        cc.validate_status_events(placeholder, status_events_schema, semantics, semantics_digest)


def test_generated_status_and_documents_are_exact_projections(
    status: dict, status_events: dict, status_events_schema: dict,
    task_bindings: dict, task_binding_schema: dict, semantics: dict,
) -> None:
    semantics_digest = cc.compute_envelope_digest(semantics, cc.SEMANTICS_DOMAIN)
    task_digest = cc.validate_task_bindings(task_bindings, task_binding_schema, semantics, ROOT)
    events_digest, states = cc.validate_status_events(
        status_events, status_events_schema, semantics, semantics_digest
    )
    expected = cc.derive_status_projection(
        semantics, semantics_digest, status_events, events_digest,
        task_bindings, task_digest, states,
    )
    assert status == expected
    assert (ROOT / cc.STATUS_DOC_REL).read_bytes() == cc.render_status_document(expected)
    assert (ROOT / cc.CHECKLIST_DOC_REL).read_bytes() == cc.render_checklist_document(expected)
    required_blockers = {
        "LEGACY_B00_REALLOCATION_REQUIRED", "B00R-G2-EXACT-HEAD-REVIEW",
        "B00R-G2-AUTHORITY-PINS", "B00R-G2-RULESET", "B00R-G2-CANARY",
        "B00R-G2-RECEIPT-ANCHOR", "B05-AUTHORIZATION",
        "B02C-E01-OWNER-RECEIPT", "B03C-E01-OWNER-RECEIPT",
        "C0-CURRENT-LEDGER-REVIEW", "C0-TARGET-ALLOCATION-REVIEW",
        "B05-PHYSICAL-ISOLATION-SOAK", "B05-CREDENTIAL-ROTATION",
        "XC01-OWNER-RECEIPTS", "B09-CONFORMANCE-DR", "B10-FROZEN-SUBJECT",
        "B10-TWO-AUDITS", "B10-CREDENTIAL-GATE", "BN-FRESH-AGGREGATE",
    }
    assert required_blockers <= {
        row["blocker_id"] for row in status["payload"]["open_blockers"]
    }


def test_status_projection_obeys_t7_t8_applicability_and_preserves_safe_hold(
    status_events: dict, status_events_schema: dict,
    task_bindings: dict, semantics: dict,
) -> None:
    semantics_digest = cc.compute_envelope_digest(semantics, cc.SEMANTICS_DOMAIN)
    task_digest = cc.compute_envelope_digest(task_bindings, cc.TASK_BINDING_DOMAIN)
    events_digest, states = cc.validate_status_events(
        status_events, status_events_schema, semantics, semantics_digest
    )
    projection = cc.derive_status_projection(
        semantics, semantics_digest, status_events, events_digest,
        task_bindings, task_digest, states,
    )
    rows = {
        row["identity"].split("::")[1]: row
        for row in projection["payload"]["milestones"]
    }
    blockers = {row["blocker_id"] for row in projection["payload"]["open_blockers"]}

    assert projection["payload"]["activation_posture"] == {
        "paper_activation": "OFF",
        "shadow_activation": "LIVE",
        "venue_activation": "OFF",
        "venue_environment": "OFF",
    }
    assert rows["B00R_G2"]["runtime_state"] == "NOT_APPLICABLE"
    assert rows["B01C"]["runtime_state"] == "NOT_APPLICABLE"
    assert "RUNTIME::B00R_G2" not in blockers
    assert "RUNTIME::B01C" not in blockers
    assert rows["B02C"]["runtime_state"] == "NOT_ATTESTED"
    assert "RUNTIME::B02C" in blockers
    assert rows["C0"]["receipt_state"] == "NOT_APPLICABLE"
    assert rows["B00R_G2"]["receipt_state"] == "BLOCKED"

    assert {
        "RECEIPT::C0",
        "ANCHOR::C0",
        "REVIEW-SLOT::C0::RECEIPT_REVIEWER",
    }.isdisjoint(blockers)
    assert {
        "C0-OWNER-AUTH",
        "C0-EXACT-HEAD-REVIEW",
        "REVIEW-SLOT::C0::C0_OWNER_AUTHENTICATOR",
        "REVIEW-SLOT::C0::SOURCE_REVIEWER",
    } <= blockers
    assert {
        "RECEIPT::B00R_G2",
        "ANCHOR::B00R_G2",
        "REVIEW-SLOT::B00R_G2::RECEIPT_REVIEWER",
    } <= blockers
    task_ref = projection["payload"]["task_binding_reference"]
    assert task_ref["changed_review_required_rows"] == 94
    assert task_ref["unchanged_review_subject_rows"] == 1156
    assert task_ref["classified_target_task_count"] == 1153
    assert task_ref["unallocated_task_count"] == 97
    assert task_ref["source_ledger_review_state"] == "UNBOUND"
    assert task_ref["target_allocation_review_state"] == "UNBOUND"


def test_require_closure_ready_is_distinct_from_structural_check(capsys) -> None:
    assert cc.main(["--check", "--root", str(ROOT)]) == 0
    structural = capsys.readouterr()
    assert "102 open blockers" in structural.out
    assert "no closure claim" in structural.out

    assert cc.main(["--require-closure-ready", "--root", str(ROOT)]) == 2
    strict = capsys.readouterr()
    assert "CLOSURE_NOT_READY: 102 open blockers; no closure claim" in strict.err


def test_status_projection_fails_closed_when_t8_becomes_applicable(
    status_events: dict, status_events_schema: dict,
    task_bindings: dict, semantics: dict,
) -> None:
    changed = copy.deepcopy(semantics)
    b00r_identity = changed["payload"]["milestones"][1]["identity"]
    matrix_row = next(
        row for row in changed["payload"]["test_layer_matrix"]
        if row["milestone_identity"] == b00r_identity
    )
    matrix_row["layers"]["T8"] = "EXTERNAL"
    _rehash(changed, cc.SEMANTICS_DOMAIN)
    semantics_digest = cc.compute_envelope_digest(changed, cc.SEMANTICS_DOMAIN)
    task_digest = cc.compute_envelope_digest(task_bindings, cc.TASK_BINDING_DOMAIN)
    changed_events = copy.deepcopy(status_events)
    changed_events["payload"]["semantics_digest_sha256"] = semantics_digest
    _rehash(changed_events, cc.STATUS_EVENTS_DOMAIN)
    events_digest, states = cc.validate_status_events(
        changed_events, status_events_schema, changed, semantics_digest
    )
    projection = cc.derive_status_projection(
        changed, semantics_digest, changed_events, events_digest,
        task_bindings, task_digest, states,
    )
    b00r = next(
        row for row in projection["payload"]["milestones"]
        if row["identity"] == b00r_identity
    )
    blockers = {row["blocker_id"] for row in projection["payload"]["open_blockers"]}
    assert b00r["runtime_state"] == "NOT_ATTESTED"
    assert "RUNTIME::B00R_G2" in blockers


def test_status_validator_rejects_applicability_blocker_injection_and_removal(
    status_events: dict, status_events_schema: dict, status_schema: dict,
    task_bindings: dict, semantics: dict,
) -> None:
    semantics_digest = cc.compute_envelope_digest(semantics, cc.SEMANTICS_DOMAIN)
    task_digest = cc.compute_envelope_digest(task_bindings, cc.TASK_BINDING_DOMAIN)
    events_digest, states = cc.validate_status_events(
        status_events, status_events_schema, semantics, semantics_digest
    )
    projection = cc.derive_status_projection(
        semantics, semantics_digest, status_events, events_digest,
        task_bindings, task_digest, states,
    )

    injected_runtime = copy.deepcopy(projection)
    b00r = injected_runtime["payload"]["milestones"][1]
    b00r["runtime_state"] = "NOT_ATTESTED"
    _rehash(injected_runtime, cc.STATUS_DOMAIN)
    with _error("STATUS_RUNTIME_STATE_MISMATCH"):
        cc.validate_status(injected_runtime, status_schema, semantics, semantics_digest)

    injected_runtime_blocker = copy.deepcopy(projection)
    b00r = injected_runtime_blocker["payload"]["milestones"][1]
    blocker = {
        "blocker_id": "RUNTIME::B00R_G2",
        "owner_identity": b00r["identity"],
        "provenance_kind": "TEST_LAYER",
        "provenance_ref": "T8",
        "reason": "applicable identical-subject runtime proof is NOT_ATTESTED",
        "severity": "P0",
        "status": "OPEN",
    }
    injected_runtime_blocker["payload"]["open_blockers"].append(blocker)
    injected_runtime_blocker["payload"]["open_blockers"].sort(
        key=lambda row: row["blocker_id"]
    )
    b00r["blocking_reasons"].append("RUNTIME::B00R_G2")
    b00r["blocking_reasons"].sort()
    _rehash(injected_runtime_blocker, cc.STATUS_DOMAIN)
    with _error("STATUS_RUNTIME_BLOCKER_APPLICABILITY_MISMATCH"):
        cc.validate_status(injected_runtime_blocker, status_schema, semantics, semantics_digest)

    removed_runtime = copy.deepcopy(projection)
    removed_runtime["payload"]["open_blockers"] = [
        row for row in removed_runtime["payload"]["open_blockers"]
        if row["blocker_id"] != "RUNTIME::B02C"
    ]
    b02c = removed_runtime["payload"]["milestones"][3]
    b02c["blocking_reasons"].remove("RUNTIME::B02C")
    _rehash(removed_runtime, cc.STATUS_DOMAIN)
    with _error("STATUS_RUNTIME_BLOCKER_APPLICABILITY_MISMATCH"):
        cc.validate_status(removed_runtime, status_schema, semantics, semantics_digest)

    injected_c0_receipt = copy.deepcopy(projection)
    c0 = injected_c0_receipt["payload"]["milestones"][0]
    blocker = {
        "blocker_id": "RECEIPT::C0",
        "owner_identity": c0["identity"],
        "provenance_kind": "PATH_LAW",
        "provenance_ref": cc.NOT_APPLICABLE_CONTROL_FREEZE_RECEIPT,
        "reason": "required evidence-only receipt is not merged",
        "severity": "P0",
        "status": "OPEN",
    }
    injected_c0_receipt["payload"]["open_blockers"].append(blocker)
    injected_c0_receipt["payload"]["open_blockers"].sort(key=lambda row: row["blocker_id"])
    c0["blocking_reasons"].append("RECEIPT::C0")
    c0["blocking_reasons"].sort()
    _rehash(injected_c0_receipt, cc.STATUS_DOMAIN)
    with _error("STATUS_RECEIPT_BLOCKER_APPLICABILITY_MISMATCH"):
        cc.validate_status(injected_c0_receipt, status_schema, semantics, semantics_digest)


def test_write_mode_changes_only_generated_outputs() -> None:
    generated = {ROOT / cc.STATUS_REL, ROOT / cc.STATUS_DOC_REL, ROOT / cc.CHECKLIST_DOC_REL}
    immutable_inputs = {
        ROOT / cc.SEMANTICS_REL, ROOT / cc.STATUS_EVENTS_REL, ROOT / cc.TASK_BINDING_REL,
        ROOT / cc.SEMANTICS_SCHEMA_REL, ROOT / cc.STATUS_EVENTS_SCHEMA_REL,
        ROOT / cc.TASK_BINDING_SCHEMA_REL, ROOT / cc.STATUS_SCHEMA_REL,
    }
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in immutable_inputs}
    generated_before = {path: path.read_bytes() for path in generated}
    assert cc.main(["--write", "--root", str(ROOT)]) == 0
    assert {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in immutable_inputs} == before
    assert {path: path.read_bytes() for path in generated} == generated_before


def test_secret_material_is_rejected() -> None:
    with _error("SECRET_PATTERN_DETECTED"):
        cc.validate_no_secrets(
            {"operator_note": "github_pat_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"},
            "fixture",
        )
    cc.validate_no_secrets(
        {"external_pin_name": "AUTHORITY_BUNDLE_G2_DECISION_SHA256"},
        "fixture",
    )
    with _error("SECRET_PATTERN_DETECTED"):
        cc.validate_no_secrets({"url": "https://example.invalid/?token=abcdefghijklmnop"}, "fixture")
    with _error("SECRET_PATTERN_DETECTED"):
        cc.validate_no_secrets({"credential": "tmc_abcdefghijklmnop"}, "fixture")


def test_b00r_policy_is_bound_to_the_exact_composite_scope(policy: dict, semantics: dict) -> None:
    cc.validate_b00r_policy(policy, semantics)

    pending = copy.deepcopy(policy)
    pending["pr_role_law"]["source_pr"]["composite_scope_binding"]["scope_digest"] = (
        "PENDING_C0_CONTROL_FREEZE"
    )
    with _error("B00R_SCOPE_BINDING_MISMATCH"):
        cc.validate_b00r_policy(pending, semantics)

    armed = copy.deepcopy(policy)
    armed["levers"]["venue_activation"] = "LIVE"
    with _error("B00R_POLICY_ACTIVATION_POSTURE_MISMATCH"):
        cc.validate_b00r_policy(armed, semantics)
