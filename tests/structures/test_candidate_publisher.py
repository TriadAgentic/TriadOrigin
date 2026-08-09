"""B06 candidate publisher: the mandatory atomic SHADOW fork + the append-only lifecycle.

Every ``PUBLISH_CANDIDATE`` envelope produces exactly one of two outcomes in the SAME transition:
a published ``edge_candidate.v2`` row plus its ``shadow_trade.v1`` ``ACCEPTED_NOT_EXECUTED`` fork,
or a ``shadow_rejection_audit.v1`` row and no candidate at all. There is no third path.
"""

from __future__ import annotations

import copy
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import transition  # noqa: E402
from triad_origin.control.shadow_ledger import (  # noqa: E402
    MARKER_SHADOW_UNTRADEABLE,
    ORIGIN_DISPOSITIONS,
    SHADOW_REJECTION_AUDIT_RECORDED,
    SHADOW_TRADE_RECORDED,
)
from triad_origin.structures import capsules, trial_registry  # noqa: E402
from triad_origin.structures.candidate_publisher import (  # noqa: E402
    CANDIDATE_PUBLICATION_REFUSED,
    CANDIDATE_PUBLISHED,
    CANDIDATE_TRANSITIONED,
    ORIGIN_PUBLICATION_SENTINEL_REASON,
    ORIGIN_PUBLICATION_SENTINEL_STAGE,
    STATE_DATA_INVALID,
    STATE_EXPIRED,
    STATE_PUBLISHED,
    STATE_UNPUBLISHED,
    STATE_WITHDRAWN,
    CandidatePublisher,
    CandidatePublisherError,
)

CAPSULE_ID = "fvg_displacement_first_touch.v1"
TRIAL_ID = "T1"


def build_trial_registry_state(trial_id: str = TRIAL_ID, capsule: str = CAPSULE_ID) -> dict:
    result = transition.run(
        trial_registry.TrialRegistry(),
        [{"event_id": f"pre_{trial_id}", "kind": "PREREGISTER_TRIAL",
          "payload": {"trial_id": trial_id, "capsule_semantic_id": capsule,
                     "conjunct_set": ["c1"], "results_available_after_us": 1,
                     "preregistered_at_us": 0}}],
        {})
    return result.final_state


def edge_candidate(candidate_id: str = "C1", **overrides: object) -> dict:
    payload = {
        "candidate_id": candidate_id,
        "hypothesis_id": "H1",
        "opportunity_cluster_id": "CLUSTER1",
        "capsule_id": CAPSULE_ID,
        "capsule_version": "1",
        "parameter_digest": "a" * 64,
        "trial_id": TRIAL_ID,
        "source_structure_id": "S1",
        "source_reaction_id": "R1",
        "canonical_instrument_id": "INSTR1",
        "direction": "LONG",
        "horizon": "100",
        "entry_policy": "MARKET_TOUCH",
        "entry_reference_ticks": "1000",
        "natural_invalidation_ticks": "900",
        "targets": [{"target_ticks": "1200"}],
        "rr_numerator": "6",
        "rr_denominator": "3",
        "ttl_us": 5_000,
        "not_before_us": 1_000,
        "cancellation_conditions": [],
        "cost_model_id": "COST1",
        "fill_model_id": "FILL1",
        "arm": "SHADOW",
        "quality": {},
        "prerequisites": [],
        "provenance_hash": "b" * 64,
    }
    payload.update(overrides)
    return payload


def publish_envelope(
    edge_candidate_payload: dict, *, event_id: str, event_time_us: int = 10_000,
    market_watermark_us: int | None = 5_000, trial_registry_state: dict | None = None,
    evaluation_notional_quote: str = "1000000", simulator_version: str = "sim-1",
    resolver_version: str = "res-1", cost_model_version: str = "cost-1",
) -> dict:
    payload = {
        "edge_candidate": edge_candidate_payload,
        "trial_registry_state": (
            trial_registry_state if trial_registry_state is not None
            else build_trial_registry_state()),
        "event_time_us": event_time_us,
        "evaluation_notional_quote": evaluation_notional_quote,
        "simulator_version": simulator_version,
        "resolver_version": resolver_version,
        "cost_model_version": cost_model_version,
    }
    if market_watermark_us is not None:
        payload["market_watermark"] = {"watermark_us": market_watermark_us}
    return {"event_id": event_id, "kind": "PUBLISH_CANDIDATE", "payload": payload}


def transition_envelope(
    kind: str, candidate_id: str, *, event_id: str, reason: str = "TEST_REASON",
    event_time_us: int = 20_000,
) -> dict:
    return {"event_id": event_id, "kind": kind,
            "payload": {"candidate_id": candidate_id, "reason": reason,
                       "event_time_us": event_time_us}}


def run(inputs: list[dict], initial: dict | None = None) -> transition.RunResult:
    return transition.run(CandidatePublisher(), inputs, {}, initial=initial)


class TestPublishHappyPath:
    def test_successful_publish_forks_an_atomic_shadow_trade(self):
        candidate = edge_candidate("C1")
        result = run([publish_envelope(candidate, event_id="pub1")])

        assert [e["event_kind"] for e in result.events] == [
            CANDIDATE_PUBLISHED, SHADOW_TRADE_RECORDED]
        assert result.final_state["candidates"]["C1"] == candidate

        trades = list(result.final_state["shadow"]["trades"].values())
        assert len(trades) == 1
        trade = trades[0]
        assert trade["candidate_id"] == "C1"
        assert trade["hypothesis_id"] == "H1"
        assert trade["origin_disposition"] == "ACCEPTED_NOT_EXECUTED"
        assert trade["origin_disposition"] in ORIGIN_DISPOSITIONS
        assert trade["rejection_stage"] == ORIGIN_PUBLICATION_SENTINEL_STAGE
        assert trade["rejection_reason"] == ORIGIN_PUBLICATION_SENTINEL_REASON

        transitions = list(result.final_state["transitions"].values())
        assert len(transitions) == 1
        row = transitions[0]
        assert row["candidate_id"] == "C1"
        assert row["from_state"] == STATE_UNPUBLISHED
        assert row["to_state"] == STATE_PUBLISHED
        assert row["state_seq"] == "0"
        assert row["previous_transition_id"] == ""

    def test_shadow_audit_dict_never_empty_on_success(self):
        # The mandatory fork writes exactly one shadow event alongside the publish event — the
        # audits map stays empty (there was no rejection), the trades map gains exactly one row.
        result = run([publish_envelope(edge_candidate("C1"), event_id="pub1")])
        assert result.final_state["shadow"]["audits"] == {}
        assert len(result.final_state["shadow"]["trades"]) == 1


class TestUntradeablePath:
    def test_empty_targets_is_untradeable_no_candidate_published(self):
        # Schema-valid (targets is a well-typed empty array) but semantically hollow: the
        # target_or_terminal_rule conjunct fails, so this is the untradeable path, never a crash.
        candidate = edge_candidate("C2", targets=[])
        result = run([publish_envelope(candidate, event_id="pub2")])

        assert [e["event_kind"] for e in result.events] == [
            CANDIDATE_PUBLICATION_REFUSED, SHADOW_REJECTION_AUDIT_RECORDED]
        refusal = result.events[0]
        assert refusal["reason_code"] == "SHADOW_UNTRADEABLE"
        assert refusal["reason_code"] == MARKER_SHADOW_UNTRADEABLE
        assert "target_or_terminal_rule" in refusal["failed_conjuncts"]

        assert result.final_state["candidates"] == {}
        assert result.final_state["transitions"] == {}
        assert result.final_state["shadow"]["trades"] == {}
        assert len(result.final_state["shadow"]["audits"]) == 1
        audit = next(iter(result.final_state["shadow"]["audits"].values()))
        assert audit["marker"] == MARKER_SHADOW_UNTRADEABLE
        assert audit["attempt_identity"] == {"candidate_id": "C2", "hypothesis_id": "H1"}

    def test_malformed_schema_is_untradeable_no_candidate_published(self):
        # cost_model_id is a required edge_candidate.v2 payload field, and no tradeability flag
        # reads it directly — omitting it fails ONLY schema_valid/semantically_valid, proving the
        # contract-validation result itself (not a coincidentally-also-false content flag) routes
        # a malformed candidate to the untradeable path.
        candidate = edge_candidate("C3")
        del candidate["cost_model_id"]
        result = run([publish_envelope(candidate, event_id="pub3")])

        refusal = result.events[0]
        assert refusal["event_kind"] == CANDIDATE_PUBLICATION_REFUSED
        assert set(refusal["failed_conjuncts"]) == {"schema_valid", "semantically_valid"}
        assert result.final_state["candidates"] == {}

    def test_forbidden_money_field_is_untradeable_never_published(self):
        # A candidate carrying a constitutionally forbidden money field fails contract validation
        # (the false-schema/assert_no_forbidden_candidate_fields guard) and therefore routes to
        # the untradeable SHADOW-only path — the money-authority wall is reachable even through
        # this composed publisher, not only through a direct contracts.validate() call.
        candidate = edge_candidate("C4", account_id="acct-should-never-appear")
        result = run([publish_envelope(candidate, event_id="pub4")])

        refusal = result.events[0]
        assert refusal["event_kind"] == CANDIDATE_PUBLICATION_REFUSED
        assert "schema_valid" in refusal["failed_conjuncts"]
        assert result.final_state["candidates"] == {}
        assert result.final_state["shadow"]["trades"] == {}

    def test_market_watermark_missing_key_raises(self):
        with pytest.raises(CandidatePublisherError):
            transition.run(
                CandidatePublisher(),
                [publish_envelope(edge_candidate("C5"), event_id="pub5", market_watermark_us=None)],
                {})


class TestIdentityVerification:
    def test_unknown_capsule_id_propagates_as_wiring_defect(self):
        candidate = edge_candidate("C6", capsule_id="CAP01_OB_ENTRY")  # RC2 ordinal spelling
        with pytest.raises(capsules.CapsuleUnavailableError):
            transition.run(
                CandidatePublisher(), [publish_envelope(candidate, event_id="pub6")], {})

    def test_unknown_trial_id_propagates_as_wiring_defect(self):
        candidate = edge_candidate("C7", trial_id="never_preregistered")
        with pytest.raises(trial_registry.TrialUnavailableError):
            transition.run(
                CandidatePublisher(), [publish_envelope(candidate, event_id="pub7")], {})

    def test_valid_capsule_and_trial_publish_cleanly(self):
        for capsule_id in capsules.CANONICAL_SEMANTIC_IDS:
            trial_state = build_trial_registry_state(trial_id="TX", capsule=capsule_id)
            candidate = edge_candidate("C8", capsule_id=capsule_id, trial_id="TX")
            result = run([
                publish_envelope(candidate, event_id="pub8", trial_registry_state=trial_state)])
            assert result.events[0]["event_kind"] == CANDIDATE_PUBLISHED


class TestRedelivery:
    def test_identical_redelivery_with_a_different_event_id_is_idempotent_noop(self):
        # A distinct event_id keeps the driver's own retransmission dedup from short-circuiting
        # before the machine ever runs, so this genuinely exercises the publisher's own
        # existing-payload-equality no-op branch, not merely the run() envelope-fingerprint dedup.
        candidate = edge_candidate("C9")
        result = run([
            publish_envelope(candidate, event_id="pub9a"),
            publish_envelope(candidate, event_id="pub9b"),
        ])
        assert [e["event_kind"] for e in result.events] == [
            CANDIDATE_PUBLISHED, SHADOW_TRADE_RECORDED]
        assert len(result.final_state["candidates"]) == 1
        assert len(result.final_state["shadow"]["trades"]) == 1

    def test_disagreeing_redelivery_raises(self):
        candidate = edge_candidate("C10", direction="LONG")
        disagreeing = edge_candidate("C10", direction="SHORT")
        with pytest.raises(CandidatePublisherError):
            transition.run(
                CandidatePublisher(),
                [publish_envelope(candidate, event_id="pub10a"),
                 publish_envelope(disagreeing, event_id="pub10b")],
                {})


class TestLifecycleTransitions:
    def test_withdraw_after_publish(self):
        candidate = edge_candidate("C11")
        result = run([
            publish_envelope(candidate, event_id="pub11"),
            transition_envelope("WITHDRAW_CANDIDATE", "C11", event_id="wd11"),
        ])
        assert result.events[-1]["event_kind"] == CANDIDATE_TRANSITIONED
        assert result.events[-1]["to_state"] == STATE_WITHDRAWN
        rows = [r for r in result.final_state["transitions"].values() if r["candidate_id"] == "C11"]
        assert len(rows) == 2
        withdraw_row = next(r for r in rows if r["to_state"] == STATE_WITHDRAWN)
        assert withdraw_row["state_seq"] == "1"
        assert withdraw_row["from_state"] == STATE_PUBLISHED

    def test_expire_after_publish(self):
        candidate = edge_candidate("C12")
        result = run([
            publish_envelope(candidate, event_id="pub12"),
            transition_envelope("EXPIRE_CANDIDATE", "C12", event_id="ex12"),
        ])
        assert result.events[-1]["to_state"] == STATE_EXPIRED

    def test_data_invalid_after_publish(self):
        candidate = edge_candidate("C13")
        result = run([
            publish_envelope(candidate, event_id="pub13"),
            transition_envelope("DATA_INVALID_CANDIDATE", "C13", event_id="dv13"),
        ])
        assert result.events[-1]["to_state"] == STATE_DATA_INVALID

    def test_transition_on_unknown_candidate_refused(self):
        result = run([transition_envelope("WITHDRAW_CANDIDATE", "ghost", event_id="wd_ghost")])
        assert result.events[-1]["reason_code"] == "CANDIDATE_TRANSITION_UNKNOWN_CANDIDATE"

    def test_transition_already_terminal_refused(self):
        candidate = edge_candidate("C14")
        result = run([
            publish_envelope(candidate, event_id="pub14"),
            transition_envelope("WITHDRAW_CANDIDATE", "C14", event_id="wd14"),
            transition_envelope("EXPIRE_CANDIDATE", "C14", event_id="ex14"),
        ])
        assert result.events[-1]["reason_code"] == "CANDIDATE_TRANSITION_ALREADY_TERMINAL"
        rows = [r for r in result.final_state["transitions"].values() if r["candidate_id"] == "C14"]
        assert len(rows) == 2  # the second terminal attempt never appended a third row

    def test_untradeable_candidate_has_no_lifecycle_to_transition(self):
        candidate = edge_candidate("C15", targets=[])
        result = run([
            publish_envelope(candidate, event_id="pub15"),
            transition_envelope("WITHDRAW_CANDIDATE", "C15", event_id="wd15"),
        ])
        assert result.events[-1]["reason_code"] == "CANDIDATE_TRANSITION_UNKNOWN_CANDIDATE"


class TestInvariance:
    def test_prefix_and_restart_and_duplicate(self):
        candidate = edge_candidate("C16")
        full = [
            publish_envelope(candidate, event_id="pub16"),
            transition_envelope("WITHDRAW_CANDIDATE", "C16", event_id="wd16"),
        ]
        whole = run(full)
        prefix = run(full[:1])
        resumed = run(full[1:], initial=prefix.final_state)
        assert resumed.final_state == whole.final_state

        dup = run(full + [full[-1]])
        assert dup.final_state == whole.final_state

    def test_caller_supplied_dicts_are_never_mutated(self):
        # The publisher must never mutate its caller's own edge_candidate/trial_registry_state
        # objects in place — every stored copy is the machine's own.
        candidate = edge_candidate("C17")
        trial_state = build_trial_registry_state(trial_id="TX17")
        candidate["trial_id"] = "TX17"
        before_candidate = copy.deepcopy(candidate)
        before_trial_state = copy.deepcopy(trial_state)
        run([publish_envelope(candidate, event_id="pub17", trial_registry_state=trial_state)])
        assert candidate == before_candidate
        assert trial_state == before_trial_state


class TestFailClosed:
    def test_unknown_envelope_kind_raises(self):
        with pytest.raises(CandidatePublisherError):
            transition.run(
                CandidatePublisher(),
                [{"event_id": "e1", "kind": "BOGUS", "payload": {}}], {})

    def test_missing_event_time_us_raises(self):
        envelope = publish_envelope(edge_candidate("C18"), event_id="pub18")
        del envelope["payload"]["event_time_us"]
        with pytest.raises(CandidatePublisherError):
            transition.run(CandidatePublisher(), [envelope], {})

    def test_transition_missing_reason_raises(self):
        envelope = transition_envelope("WITHDRAW_CANDIDATE", "ghost", event_id="wd_bad")
        del envelope["payload"]["reason"]
        with pytest.raises(CandidatePublisherError):
            transition.run(CandidatePublisher(), [envelope], {})
