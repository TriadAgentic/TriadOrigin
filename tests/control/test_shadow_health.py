"""B05 SHADOW health battery: heartbeat/backlog staleness containment, persistence-deadline
refusal, dedupe/collision/contamination tallies, and prefix/restart/duplicate invariance."""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import timings, transition  # noqa: E402
from triad_origin.control import lever_law  # noqa: E402
from triad_origin.control import shadow_health as health  # noqa: E402
from triad_origin.control.shadow_health import ShadowHealth, ShadowHealthError  # noqa: E402


def heartbeat(event_id, age_ms):
    return {"event_id": event_id, "kind": "WRITER_HEARTBEAT", "payload": {"age_ms": age_ms}}


def backlog(event_id, age_ms):
    return {"event_id": event_id, "kind": "RESOLVER_BACKLOG", "payload": {"age_ms": age_ms}}


def persist(event_id, latency_ms, shadow_trade_id=None):
    payload = {"latency_ms": latency_ms}
    if shadow_trade_id is not None:
        payload["shadow_trade_id"] = shadow_trade_id
    return {"event_id": event_id, "kind": "PERSISTENCE_LATENCY", "payload": payload}


def dedupe(event_id):
    return {"event_id": event_id, "kind": "RECORD_DEDUPE", "payload": {}}


def collision(event_id):
    return {"event_id": event_id, "kind": "RECORD_COLLISION", "payload": {}}


def contamination(event_id):
    return {"event_id": event_id, "kind": "RECORD_CONTAMINATION", "payload": {}}


def run(inputs, initial=None):
    return transition.run(ShadowHealth(), inputs, {}, initial=initial)


def kinds(events):
    return [e.get("event_kind") for e in events]


class TestHeartbeatBound:
    def test_under_bound_records_age_no_event(self):
        bound = timings.timing_ms("shadow_health_max_age_ms")
        result = run([heartbeat("h1", bound)])  # inclusive: exactly at bound is healthy
        assert result.events == []
        assert result.final_state["last_heartbeat_age_ms"] == bound

    def test_over_bound_forces_execution_planes_off(self):
        bound = timings.timing_ms("shadow_health_max_age_ms")
        result = run([heartbeat("h1", bound + 1)])
        assert kinds(result.events) == [health.HEALTH_FORCED_OFF]
        event = result.events[0]
        assert event["reason_code"] == "SHADOW_HEALTH_STALE"
        assert event["payload"]["venue_activation"] == "OFF"
        assert event["payload"]["paper_activation"] == "OFF"
        assert event["payload"]["shadow_activation"] == "LIVE"  # SHADOW recovery continues

    def test_negative_age_is_stale_by_definition(self):
        result = run([heartbeat("h1", -1)])
        assert kinds(result.events) == [health.HEALTH_FORCED_OFF]


class TestBacklogBound:
    def test_under_bound_records_age_no_event(self):
        bound = timings.timing_ms("shadow_resolver_backlog_max_age_ms")
        result = run([backlog("b1", bound)])
        assert result.events == []
        assert result.final_state["backlog_age_ms"] == bound

    def test_over_bound_forces_execution_planes_off(self):
        bound = timings.timing_ms("shadow_resolver_backlog_max_age_ms")
        result = run([backlog("b1", bound + 1)])
        assert kinds(result.events) == [health.HEALTH_FORCED_OFF]
        assert result.events[0]["payload"]["venue_activation"] == "OFF"
        assert result.events[0]["payload"]["shadow_activation"] == "LIVE"

    def test_heartbeat_and_backlog_ages_are_tracked_independently(self):
        result = run([heartbeat("h1", 10), backlog("b1", 20)])
        assert result.final_state["last_heartbeat_age_ms"] == 10
        assert result.final_state["backlog_age_ms"] == 20


class TestPersistenceLatency:
    def test_under_deadline_is_a_no_op(self):
        bound = timings.timing_ms("shadow_rejection_persist_deadline_ms")
        result = run([persist("p1", bound)])  # inclusive: exactly at deadline is compliant
        assert result.events == []

    def test_over_deadline_is_refused(self):
        bound = timings.timing_ms("shadow_rejection_persist_deadline_ms")
        result = run([persist("p1", bound + 1, shadow_trade_id="TRADE-1")])
        assert kinds(result.events) == [health.LEVER_REFUSAL]
        event = result.events[0]
        assert event["reason_code"] == "SHADOW_REJECTION_NOT_PERSISTED"
        assert event["refs"]["shadow_trade_id"] == "TRADE-1"

    def test_persistence_latency_never_mutates_health_state(self):
        bound = timings.timing_ms("shadow_rejection_persist_deadline_ms")
        result = run([persist("p1", bound + 1)])
        assert result.final_state == ShadowHealth().initial_state()


class TestCounters:
    def test_dedupe_and_collision_tallies_accumulate(self):
        result = run([dedupe("d1"), dedupe("d2"), collision("c1")])
        assert result.final_state["dedupe_count"] == 2
        assert result.final_state["collision_count"] == 1
        assert kinds(result.events) == [
            health.SHADOW_DEDUPE_RECORDED, health.SHADOW_DEDUPE_RECORDED,
            health.SHADOW_COLLISION_RECORDED]

    def test_contamination_bumps_the_tally_and_always_refuses(self):
        result = run([contamination("x1")])
        assert result.final_state["contamination_count"] == 1
        assert kinds(result.events) == [
            health.SHADOW_CONTAMINATION_RECORDED, health.LEVER_REFUSAL]
        refusal = result.events[1]
        assert refusal["reason_code"] == "SHADOW_MONEY_CONTAMINATION"

    def test_contamination_refusal_matches_the_registered_lever_law_code(self):
        result = run([contamination("x1")])
        refusal = result.events[1]
        expected = lever_law.refuse("SHADOW_MONEY_CONTAMINATION")
        assert refusal["meaning"] == expected.meaning
        assert refusal["minimum_action"] == dict(sorted(expected.minimum_action.items()))


class TestMalformedEnvelope:
    def test_unknown_kind_raises(self):
        with pytest.raises(ShadowHealthError):
            ShadowHealth().transition(
                ShadowHealth().initial_state(), {"event_id": "x", "kind": "NOPE", "payload": {}},
                {}, {})

    def test_missing_age_ms_raises(self):
        with pytest.raises(ShadowHealthError):
            ShadowHealth().transition(
                ShadowHealth().initial_state(),
                {"event_id": "x", "kind": "WRITER_HEARTBEAT", "payload": {}}, {}, {})

    def test_bool_is_not_an_accepted_int(self):
        with pytest.raises(ShadowHealthError):
            ShadowHealth().transition(
                ShadowHealth().initial_state(),
                {"event_id": "x", "kind": "WRITER_HEARTBEAT", "payload": {"age_ms": True}}, {}, {})


class TestInvariance:
    def test_prefix_and_restart_and_duplicate(self):
        bound = timings.timing_ms("shadow_health_max_age_ms")
        full = [
            heartbeat("h1", 10),
            backlog("b1", 20),
            heartbeat("h2", bound + 1),
            dedupe("d1"),
            contamination("x1"),
        ]
        whole = run(full)
        prefix = run(full[:2])
        resumed = run(full[2:], initial=prefix.final_state)
        assert resumed.final_state == whole.final_state

        replayed_from_scratch = run(full + [full[-1]])
        assert replayed_from_scratch.duplicate_count == 1
        assert replayed_from_scratch.final_state == whole.final_state


def test_dedupe_tally_is_caller_driven_over_the_ledgers_silent_no_op():
    # CTL-8: the LEV-0070 dedupe half is a COMPOSITION contract, not a ledger event. The
    # shadow_ledger exact-redelivery path is a SILENT no-op (no event, state unchanged); a
    # composing caller detects that silence and drives RECORD_DEDUPE, which this module owns as a
    # pure counter. This pins both halves of the corrected docstring's law.
    from triad_origin.control import shadow_ledger as ledger

    cand = {
        "event_id": "s1", "kind": "SHADOW_CANDIDATE",
        "payload": {
            "candidate_id": "CAND-1", "hypothesis_id": "HYP-1", "origin_disposition": "REJECTED",
            "rejection_stage": "E08_RISK", "rejection_reason": "oversized",
            "market_watermark": {ledger.MARKET_WATERMARK_TS_KEY: 1_000},
            "proposed_geometry": {"side": "LONG", "entry_ticks": 100},
            "evaluation_notional_quote": "1000000", "simulator_version": "sim-1",
            "resolver_version": "res-1", "cost_model_version": "cost-1", "event_time_us": 1_000,
        },
    }
    for name in ledger.TRADEABILITY_REQUIREMENTS:
        cand["payload"][name] = True
    redelivery = dict(cand, event_id="s2")  # NEW event_id, byte-identical content
    ledger_result = transition.run(ledger.ShadowLedger(), [cand, redelivery], {})
    # the redelivery emitted NOTHING and did not double-advance duplicate_count (new event_id)
    assert len(ledger_result.events) == 1
    assert ledger_result.duplicate_count == 0

    # the composing caller, seeing the ledger's silence, drives RECORD_DEDUPE on shadow_health
    health_result = run([dedupe("d1")])
    assert health_result.final_state["dedupe_count"] == 1
    assert health_result.events[0]["event_kind"] == health.SHADOW_DEDUPE_RECORDED
