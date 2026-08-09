"""B07 authority-fact-verifier battery: verify-only law (never admits/issues/selects money
authority), the ordering law (highest valid token wins exact scope), the three mandatory edge
behaviors (stale/duplicate/wildcard refuse; split brain latches and stops new entries until an
explicit proof-bearing clear), narrowed readiness, and the rollback comparison."""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin.control import authority_fact_verifier as afv  # noqa: E402


def _fact(**overrides):
    base = {
        "authority_id": "auth-1",
        "authoritative_topic": "edge.authority.v1",
        "scope": {"instrument": "BTCUSDT", "account": "primary"},
        "selected_engine_cohort": "ORIGIN_CANDIDATE",
        "fencing_token": "5",
        "epoch": "1",
        "issued_at_us": 1000,
        "not_before_us": 1000,
        "expires_at_us": 5000,
        "revoked_at_us": 1000,
        "renewed_at_us": 1000,
        "activation_manifest_id": "am-1",
        "issuer": "governance-lease-issuer",
        "state": "ACTIVE",
        "allocation": {},
        "conflicts": [],
        "signature": "sig-1",
    }
    base.update(overrides)
    return base


def _lease(**overrides):
    base = {
        "lease_id": "lease-1",
        "authoritative_topic": "edge.authority.v1",
        "scope": {"instrument": "BTCUSDT"},
        "producer_service": "svc-1",
        "producer_instance_id": "i-1",
        "fencing_token": "5",
        "issued_at_us": 1000,
        "not_before_us": 1000,
        "expires_at_us": 5000,
        "revoked_at_us": 1000,
        "activation_manifest_id": "am-1",
        "issuer": "lease-coordinator",
        "state": "ACTIVE",
        "signature": "sig-1",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------------------------
# Fact-shape verification (schema + wildcard)
# ---------------------------------------------------------------------------------------------


def test_a_well_formed_fact_verifies():
    verified = afv.verify_candidate_authority(_fact(), now_us=1100)
    assert verified["authority_id"] == "auth-1"


def test_schema_violation_refuses():
    broken = _fact()
    del broken["signature"]
    with pytest.raises(afv.AuthorityFactError):
        afv.verify_candidate_authority(broken, now_us=1100)


@pytest.mark.parametrize("scope", [{}, {"instrument": "*"}, {"instrument": "BTC", "account": "*"}])
def test_wildcard_scope_refuses(scope):
    with pytest.raises(afv.AuthorityFactError):
        afv.verify_candidate_authority(_fact(scope=scope), now_us=1100)


def test_exact_scope_is_accepted():
    verified = afv.verify_candidate_authority(
        _fact(scope={"instrument": "BTCUSDT"}), now_us=1100)
    assert verified["scope"] == {"instrument": "BTCUSDT"}


# ---------------------------------------------------------------------------------------------
# Currency: state is authoritative, not revoked_at_us presence
# ---------------------------------------------------------------------------------------------


def test_active_state_within_window_is_currently_valid():
    assert afv.is_currently_valid_authority(_fact(), now_us=1100)


def test_active_state_expired_is_not_currently_valid():
    assert not afv.is_currently_valid_authority(_fact(), now_us=9999)


def test_active_state_before_not_before_is_not_currently_valid():
    assert not afv.is_currently_valid_authority(_fact(), now_us=500)


@pytest.mark.parametrize("state", ["ISSUED", "REVOKED", "EXPIRED", "SUPERSEDED"])
def test_non_active_states_are_never_currently_valid(state):
    assert not afv.is_currently_valid_authority(_fact(state=state), now_us=1100)


def test_revoked_at_us_value_alone_does_not_drive_currency():
    # revoked_at_us is a REQUIRED, always-present integer on this schema; a real (but not
    # semantically meaningful outside state=REVOKED) value must not itself flip currency.
    still_valid = afv.is_currently_valid_authority(
        _fact(state="ACTIVE", revoked_at_us=999999), now_us=1100)
    assert still_valid


# ---------------------------------------------------------------------------------------------
# The ordering law + mandatory edge behavior: stale / duplicate / split brain
# ---------------------------------------------------------------------------------------------


def test_first_admission_for_a_scope_is_accepted():
    ledger = afv.AuthorityLedger()
    result = ledger.admit_fact(_fact(), now_us=1100)
    assert result.accepted
    assert result.reason == afv.ACCEPTED


def test_a_lower_token_is_stale_and_refuses():
    ledger = afv.AuthorityLedger()
    ledger.admit_fact(_fact(fencing_token="5"), now_us=1100)
    result = ledger.admit_fact(_fact(fencing_token="3"), now_us=1200)
    assert not result.accepted
    assert result.reason == afv.REFUSED_STALE


def test_a_higher_token_advances_authority():
    ledger = afv.AuthorityLedger()
    ledger.admit_fact(_fact(fencing_token="5"), now_us=1100)
    result = ledger.admit_fact(_fact(fencing_token="6"), now_us=1200)
    assert result.accepted
    assert ledger.current_for_scope(_fact()["scope"])["fencing_token"] == "6"


def test_identical_redelivery_at_the_same_token_is_idempotent():
    ledger = afv.AuthorityLedger()
    ledger.admit_fact(_fact(fencing_token="5"), now_us=1100)
    result = ledger.admit_fact(_fact(fencing_token="5"), now_us=1200)
    assert result.accepted
    assert result.reason == afv.ACCEPTED_DUPLICATE_REDELIVERY
    assert not ledger.is_split_brain(_fact()["scope"])


def test_disagreeing_content_at_the_same_token_is_a_conflict_and_latches_split_brain():
    ledger = afv.AuthorityLedger()
    ledger.admit_fact(_fact(fencing_token="5", issuer="issuer-a"), now_us=1100)
    result = ledger.admit_fact(_fact(fencing_token="5", issuer="issuer-b"), now_us=1200)
    assert not result.accepted
    assert result.reason == afv.REFUSED_DUPLICATE_TOKEN_CONFLICT
    assert result.split_brain
    assert ledger.is_split_brain(_fact()["scope"])


def test_split_brain_blocks_even_a_strictly_higher_token():
    ledger = afv.AuthorityLedger()
    ledger.admit_fact(_fact(fencing_token="5", issuer="issuer-a"), now_us=1100)
    ledger.admit_fact(_fact(fencing_token="5", issuer="issuer-b"), now_us=1200)  # latches
    result = ledger.admit_fact(_fact(fencing_token="99"), now_us=1300)
    assert not result.accepted
    assert result.reason == afv.REFUSED_SPLIT_BRAIN_ACTIVE


def test_current_for_scope_is_none_during_split_brain():
    ledger = afv.AuthorityLedger()
    ledger.admit_fact(_fact(fencing_token="5", issuer="issuer-a"), now_us=1100)
    ledger.admit_fact(_fact(fencing_token="5", issuer="issuer-b"), now_us=1200)
    assert ledger.current_for_scope(_fact()["scope"]) is None


def test_clear_split_brain_requires_a_non_empty_proof():
    ledger = afv.AuthorityLedger()
    ledger.admit_fact(_fact(fencing_token="5", issuer="issuer-a"), now_us=1100)
    ledger.admit_fact(_fact(fencing_token="5", issuer="issuer-b"), now_us=1200)
    with pytest.raises(afv.AuthorityFactError):
        ledger.clear_split_brain(_fact()["scope"], proof="")


def test_clear_split_brain_lifts_the_latch_and_admission_resumes():
    ledger = afv.AuthorityLedger()
    ledger.admit_fact(_fact(fencing_token="5", issuer="issuer-a"), now_us=1100)
    ledger.admit_fact(_fact(fencing_token="5", issuer="issuer-b"), now_us=1200)
    ledger.clear_split_brain(_fact()["scope"], proof="operator reconciled offline")
    assert not ledger.is_split_brain(_fact()["scope"])
    result = ledger.admit_fact(_fact(fencing_token="99"), now_us=1300)
    assert result.accepted
    assert ledger.current_for_scope(_fact()["scope"])["fencing_token"] == "99"


def test_different_scopes_are_tracked_independently():
    ledger = afv.AuthorityLedger()
    r1 = ledger.admit_fact(_fact(scope={"instrument": "BTCUSDT"}, fencing_token="5"),
                            now_us=1100)
    r2 = ledger.admit_fact(_fact(scope={"instrument": "ETHUSDT"}, fencing_token="1"),
                            now_us=1100)
    assert r1.accepted and r2.accepted
    assert ledger.current_for_scope({"instrument": "BTCUSDT"})["fencing_token"] == "5"
    assert ledger.current_for_scope({"instrument": "ETHUSDT"})["fencing_token"] == "1"


def test_unknown_scope_returns_none():
    ledger = afv.AuthorityLedger()
    assert ledger.current_for_scope({"instrument": "NEVERSEEN"}) is None


# ---------------------------------------------------------------------------------------------
# Producer lease verification
# ---------------------------------------------------------------------------------------------


def test_lease_verifies_and_is_active_within_window():
    verified = afv.verify_producer_lease(_lease(), now_us=2000)
    assert afv.is_currently_active_lease(verified, now_us=2000)


def test_lease_expired_is_not_active():
    verified = afv.verify_producer_lease(_lease(), now_us=2000)
    assert not afv.is_currently_active_lease(verified, now_us=9999)


@pytest.mark.parametrize("state", ["ISSUED", "REVOKED", "EXPIRED", "SUPERSEDED"])
def test_lease_non_active_state_is_never_active(state):
    verified = afv.verify_producer_lease(_lease(state=state), now_us=2000)
    assert not afv.is_currently_active_lease(verified, now_us=2000)


def test_lease_schema_violation_refuses():
    broken = _lease()
    del broken["lease_id"]
    with pytest.raises(afv.AuthorityFactError):
        afv.verify_producer_lease(broken, now_us=2000)


# ---------------------------------------------------------------------------------------------
# Readiness (narrowed to what this module owns)
# ---------------------------------------------------------------------------------------------


def test_readiness_true_when_authority_and_lease_are_both_current():
    result = afv.readiness(
        {"instrument": "BTCUSDT"}, _fact(scope={"instrument": "BTCUSDT"}), _lease(),
        now_us=1700)
    assert result["ready"] is True
    assert result["producer_attestation"] == "NOT_OWNED_HERE"


def test_readiness_false_when_authority_fact_absent():
    result = afv.readiness({"instrument": "BTCUSDT"}, None, _lease(), now_us=1700)
    assert result["ready"] is False
    assert result["authority_fact_present"] is False


def test_readiness_false_when_lease_absent():
    result = afv.readiness(
        {"instrument": "BTCUSDT"}, _fact(scope={"instrument": "BTCUSDT"}), None, now_us=1700)
    assert result["ready"] is False
    assert result["lease_present"] is False


def test_readiness_false_when_lease_not_active():
    result = afv.readiness(
        {"instrument": "BTCUSDT"}, _fact(scope={"instrument": "BTCUSDT"}),
        _lease(state="EXPIRED"), now_us=1700)
    assert result["ready"] is False
    assert result["lease_active"] is False


def test_readiness_false_when_activation_manifest_id_missing():
    result = afv.readiness(
        {"instrument": "BTCUSDT"},
        _fact(scope={"instrument": "BTCUSDT"}, activation_manifest_id=""), _lease(),
        now_us=1700)
    assert result["ready"] is False
    assert result["activation_manifest_named"] is False


def test_readiness_never_returns_a_bare_boolean_for_producer_attestation():
    result = afv.readiness(
        {"instrument": "BTCUSDT"}, _fact(scope={"instrument": "BTCUSDT"}), _lease(),
        now_us=1700)
    assert isinstance(result["producer_attestation"], str)
    assert result["producer_attestation"] == "NOT_OWNED_HERE"


# ---------------------------------------------------------------------------------------------
# The rollback comparison (strictly-higher-token proof)
# ---------------------------------------------------------------------------------------------


def test_strictly_higher_token_accepted():
    assert afv.assert_strictly_higher_token(99, "100") == 100
    assert afv.assert_strictly_higher_token(99, 100) == 100


def test_equal_token_refuses():
    with pytest.raises(afv.AuthorityFactError):
        afv.assert_strictly_higher_token(99, "99")


def test_lower_token_refuses():
    with pytest.raises(afv.AuthorityFactError):
        afv.assert_strictly_higher_token(99, "50")


def test_malformed_proposed_token_refuses():
    with pytest.raises(afv.AuthorityFactError):
        afv.assert_strictly_higher_token(99, "not-a-number")


def test_negative_current_token_refuses():
    with pytest.raises(afv.AuthorityFactError):
        afv.assert_strictly_higher_token(-1, "5")


# ---------------------------------------------------------------------------------------------
# Never admits/issues/selects money authority — this module holds NO write path
# ---------------------------------------------------------------------------------------------


def test_module_exposes_no_issuance_or_admission_verb():
    import triad_origin.control.authority_fact_verifier as module
    banned_prefixes = ("issue_", "admit_candidate", "select_authority", "arm_", "activate_")
    public_names = [name for name in dir(module) if not name.startswith("_")]
    for name in public_names:
        for banned in banned_prefixes:
            assert not name.startswith(banned), f"unexpected write-shaped export: {name}"


def test_now_us_must_be_supplied_no_clock_read():
    import inspect
    sig = inspect.signature(afv.verify_candidate_authority)
    assert "now_us" in sig.parameters
    assert sig.parameters["now_us"].default is inspect.Parameter.empty
