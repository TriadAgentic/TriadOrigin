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
def semantics() -> dict:
    return cc.load_canonical_object(ROOT / cc.SEMANTICS_REL)


@pytest.fixture(scope="module")
def status() -> dict:
    return cc.load_canonical_object(ROOT / cc.STATUS_REL)


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
        ROOT / cc.B00R_POLICY_REL,
    )
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    result = cc.check_all(ROOT)
    assert result["milestones"] == 13
    assert result["decisions"] == 9
    assert result["conflicts"] == 14
    assert result["profiles"] == 9
    assert result["test_layers"] == 13
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
    with _error("TEST_MATRIX_PROFILE_MODE_MISSING"):
        cc.validate_semantics(no_external, semantics_schema)


def test_legacy_crosswalk_rejects_duplicate_legacy_and_unknown_current_identity(
    semantics: dict, semantics_schema: dict
) -> None:
    tampered = copy.deepcopy(semantics)
    tampered["payload"]["legacy_crosswalk"][1]["legacy_ref"] = tampered["payload"][
        "legacy_crosswalk"
    ][0]["legacy_ref"]
    _rehash(tampered, cc.SEMANTICS_DOMAIN)
    with _error("LEGACY_CROSSWALK_DUPLICATE"):
        cc.validate_semantics(tampered, semantics_schema)

    tampered = copy.deepcopy(semantics)
    tampered["payload"]["legacy_crosswalk"][1]["current_identity"] = (
        "ORIGIN_REPAIR::B01C::sha256:" + "a" * 64
    )
    _rehash(tampered, cc.SEMANTICS_DOMAIN)
    with _error("LEGACY_CROSSWALK_TARGET_INVALID"):
        cc.validate_semantics(tampered, semantics_schema)


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
