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


def test_xc01_is_explicit_and_blocks_b08_b09_bn(
    semantics: dict, semantics_schema: dict
) -> None:
    cc.validate_semantics(semantics, semantics_schema)
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
    with _error("XC01_PATH_LAW_MISMATCH"):
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
    cc.validate_semantics(semantics, semantics_schema)
    policy = semantics["payload"]["review_policy"]
    roles = {row["role_id"] for row in policy["role_registry"]}
    assert {
        "AUTHOR", "EVIDENCE_PRODUCER", "OWNER_DECISION_SIGNER", "RESULT_PRODUCER"
    } <= roles
    assert all(
        slot["binding_state"] == "UNBOUND" and slot["provider_binding"] is None
        for row in policy["milestone_slots"] for slot in row["slots"]
    )
    missing_role = copy.deepcopy(semantics)
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
    cc.validate_semantics(semantics, semantics_schema)
    control = semantics["payload"]["b10_terminal_control"]
    assert control["tasks"] and control["criteria"] and control["verifications"]
    assert len(control["audit_roles"]) == 2
    cyclic = copy.deepcopy(semantics)
    tasks = cyclic["payload"]["b10_terminal_control"]["tasks"]
    tasks[0]["dependency_task_ids"] = [tasks[-1]["task_id"]]
    _rehash(cyclic, cc.SEMANTICS_DOMAIN)
    with _error("B10_TASK_DEPENDENCY_CYCLE"):
        cc.validate_semantics(cyclic, semantics_schema)

    wrong_path = copy.deepcopy(semantics)
    wrong_path["payload"]["b10_terminal_control"]["receipt_anchor_law"]["receipt_path"] = "wrong.json"
    _rehash(wrong_path, cc.SEMANTICS_DOMAIN)
    with _error("B10_RECEIPT_ANCHOR_LAW_MISMATCH"):
        cc.validate_semantics(wrong_path, semantics_schema)

    wrong_anchor = copy.deepcopy(semantics)
    wrong_anchor["payload"]["b10_terminal_control"]["receipt_anchor_law"]["required_anchor"] = "WRONG_ANCHOR"
    _rehash(wrong_anchor, cc.SEMANTICS_DOMAIN)
    with _error("B10_RECEIPT_ANCHOR_LAW_MISMATCH"):
        cc.validate_semantics(wrong_anchor, semantics_schema)


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
        "B05-PHYSICAL-ISOLATION-SOAK", "B05-CREDENTIAL-ROTATION",
        "XC01-OWNER-RECEIPTS", "B09-CONFORMANCE-DR", "B10-FROZEN-SUBJECT",
        "B10-TWO-AUDITS", "B10-CREDENTIAL-GATE", "BN-FRESH-AGGREGATE",
    }
    assert required_blockers <= {
        row["blocker_id"] for row in status["payload"]["open_blockers"]
    }


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
