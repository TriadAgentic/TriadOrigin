"""B05 SHADOW ledger battery: tradeability gate, freeze/immutability, dedup/collision, NO_FILL,
watermark-ordering, and prefix/restart/duplicate invariance."""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import transition  # noqa: E402
from triad_origin.control import shadow_ledger as ledger  # noqa: E402
from triad_origin.control.shadow_ledger import ShadowLedger, ShadowLedgerError  # noqa: E402


def candidate(
    event_id, candidate_id, hypothesis_id, *, origin_disposition="REJECTED",
    rejection_stage="E08_RISK", rejection_reason="oversized", watermark_us=1_000,
    proposed_geometry=None, evaluation_notional_quote="1000000", simulator_version="sim-1",
    resolver_version="res-1", cost_model_version="cost-1", event_time_us=1_000, flags=None,
):
    payload = {
        "candidate_id": candidate_id,
        "hypothesis_id": hypothesis_id,
        "origin_disposition": origin_disposition,
        "rejection_stage": rejection_stage,
        "rejection_reason": rejection_reason,
        "market_watermark": {ledger.MARKET_WATERMARK_TS_KEY: watermark_us},
        "proposed_geometry": proposed_geometry or {"side": "LONG", "entry_ticks": 100},
        "evaluation_notional_quote": evaluation_notional_quote,
        "simulator_version": simulator_version,
        "resolver_version": resolver_version,
        "cost_model_version": cost_model_version,
        "event_time_us": event_time_us,
    }
    for name in ledger.TRADEABILITY_REQUIREMENTS:
        payload[name] = True
    if flags:
        payload.update(flags)
    return {"event_id": event_id, "kind": "SHADOW_CANDIDATE", "payload": payload}


def fill_model(
    event_id, shadow_trade_id, *, fill_model_result=None, terminal_outcome=None,
    evaluated_at_watermark_us=1_000,
):
    return {
        "event_id": event_id, "kind": "SHADOW_FILL_MODEL",
        "payload": {
            "shadow_trade_id": shadow_trade_id,
            "fill_model_result": fill_model_result
            if fill_model_result is not None else {"fill_px_ticks": 101},
            "terminal_outcome": terminal_outcome if terminal_outcome is not None else {"pnl_ticks": 5},
            "evaluated_at_watermark_us": evaluated_at_watermark_us,
        },
    }


def run(inputs, initial=None):
    return transition.run(ShadowLedger(), inputs, {}, initial=initial)


def kinds(events):
    return [e.get("event_kind") for e in events]


class TestValidCandidateRecorded:
    def test_valid_candidate_is_frozen_into_trades(self):
        result = run([candidate("c1", "CAND-1", "HYP-1")])
        assert kinds(result.events) == [ledger.SHADOW_TRADE_RECORDED]
        trades = result.final_state["trades"]
        assert len(trades) == 1
        row = next(iter(trades.values()))
        assert row["population"] == ledger.POPULATION_SHADOW
        assert row["shadow_activation"] == ledger.SHADOW_ACTIVATION_LIVE
        assert row["candidate_id"] == "CAND-1"
        assert row["hypothesis_id"] == "HYP-1"
        assert row["fill_model_result"] == ledger.FILL_MODEL_PENDING
        assert row["terminal_outcome"] == ledger.TERMINAL_OUTCOME_PENDING
        assert result.final_state["audits"] == {}

    def test_shadow_trade_id_is_deterministic_and_excludes_geometry(self):
        a = candidate("a", "CAND-1", "HYP-1", proposed_geometry={"side": "LONG"})
        b = candidate("b", "CAND-1", "HYP-1", proposed_geometry={"side": "SHORT"})
        id_a = ledger._shadow_trade_id(a["payload"])
        id_b = ledger._shadow_trade_id(b["payload"])
        assert id_a == id_b  # identity components identical -> same shadow_trade_id


class TestUntradeableProducesAudit:
    @pytest.mark.parametrize("failing_flag", ledger.TRADEABILITY_REQUIREMENTS)
    def test_every_tradeability_conjunct_can_fail_closed(self, failing_flag):
        result = run([candidate("c1", "CAND-1", "HYP-1", flags={failing_flag: False})])
        assert kinds(result.events) == [ledger.SHADOW_REJECTION_AUDIT_RECORDED]
        assert result.final_state["trades"] == {}
        audits = result.final_state["audits"]
        assert len(audits) == 1
        audit = next(iter(audits.values()))
        assert audit["marker"] == "SHADOW_UNTRADEABLE"
        assert failing_flag in audit["validation_failure"]
        # No fabricated geometry or trade anywhere in the audit row (LEV-0068).
        assert "proposed_geometry" not in audit
        assert "shadow_trade_id" not in audit
        assert "entry_ticks" not in audit

    def test_untradeable_event_carries_the_refusal(self):
        result = run([candidate("c1", "CAND-1", "HYP-1", flags={"horizon": False})])
        event = result.events[0]
        assert event["reason_code"] == "SHADOW_UNTRADEABLE"
        assert event["payload"]["marker"] == "SHADOW_UNTRADEABLE"

    def test_missing_flag_is_treated_as_failing_never_true(self):
        c = candidate("c1", "CAND-1", "HYP-1")
        del c["payload"]["side"]
        result = run([c])
        assert kinds(result.events) == [ledger.SHADOW_REJECTION_AUDIT_RECORDED]
        assert "side" in result.events[0]["payload"]["validation_failure"]

    def test_never_fabricates_a_trade_for_an_untradeable_candidate(self):
        result = run([candidate("c1", "CAND-1", "HYP-1", flags={"finite_numbers": False})])
        assert result.final_state["trades"] == {}


class TestDuplicateAndCollision:
    def test_identical_redelivery_under_a_new_event_id_is_a_no_op(self):
        first = candidate("c1", "CAND-1", "HYP-1")
        second = candidate("c2", "CAND-1", "HYP-1")  # same content, different event_id
        result = run([first, second])
        assert kinds(result.events) == [ledger.SHADOW_TRADE_RECORDED]  # only the first recorded
        assert len(result.final_state["trades"]) == 1

    def test_colliding_identity_with_unequal_payload_is_refused_and_original_untouched(self):
        first = candidate("c1", "CAND-1", "HYP-1", proposed_geometry={"side": "LONG"})
        second = candidate("c2", "CAND-1", "HYP-1", proposed_geometry={"side": "SHORT"})
        result = run([first, second])
        assert kinds(result.events) == [ledger.SHADOW_TRADE_RECORDED, ledger.LEVER_REFUSAL]
        assert result.events[1]["reason_code"] == "SHADOW_LINEAGE_INCOMPLETE"
        trades = result.final_state["trades"]
        assert len(trades) == 1
        row = next(iter(trades.values()))
        assert row["proposed_geometry"] == {"side": "LONG"}  # the ORIGINAL row, untouched

    def test_post_freeze_replay_with_different_geometry_is_refused_not_merged(self):
        first = candidate("c1", "CAND-1", "HYP-1", proposed_geometry={"entry_ticks": 100})
        replay = candidate("c2", "CAND-1", "HYP-1", proposed_geometry={"entry_ticks": 999})
        result = run([first, replay])
        row = next(iter(result.final_state["trades"].values()))
        assert row["proposed_geometry"]["entry_ticks"] == 100
        assert result.events[-1]["reason_code"] == "SHADOW_LINEAGE_INCOMPLETE"


class TestFillModel:
    def test_no_fill_is_representable_and_distinct_from_a_real_fill(self):
        cand = candidate("c1", "CAND-1", "HYP-1")
        trade_id = ledger._shadow_trade_id(cand["payload"])
        result = run([cand, fill_model("f1", trade_id, fill_model_result={"result": "NO_FILL"})])
        row = result.final_state["trades"][trade_id]
        assert row["fill_model_result"] == {"result": "NO_FILL"}
        assert row["fill_model_result"] != {"fill_px_ticks": 101}
        assert kinds(result.events) == [ledger.SHADOW_TRADE_RECORDED, ledger.SHADOW_TRADE_RESOLVED]

    def test_real_fill_resolves_the_pending_placeholder(self):
        cand = candidate("c1", "CAND-1", "HYP-1")
        trade_id = ledger._shadow_trade_id(cand["payload"])
        result = run([cand, fill_model("f1", trade_id)])
        row = result.final_state["trades"][trade_id]
        assert row["fill_model_result"] == {"fill_px_ticks": 101}
        assert row["terminal_outcome"] == {"pnl_ticks": 5}

    def test_unknown_shadow_trade_id_is_refused_cleanly(self):
        result = run([fill_model("f1", "no-such-trade")])
        assert result.final_state["trades"] == {}
        assert kinds(result.events) == [ledger.LEVER_REFUSAL]
        assert result.events[0]["reason_code"] == "SHADOW_LINEAGE_INCOMPLETE"

    def test_second_resolution_attempt_is_refused_the_first_result_is_untouched(self):
        cand = candidate("c1", "CAND-1", "HYP-1")
        trade_id = ledger._shadow_trade_id(cand["payload"])
        first_fill = fill_model("f1", trade_id, fill_model_result={"fill_px_ticks": 101})
        second_fill = fill_model("f2", trade_id, fill_model_result={"fill_px_ticks": 202})
        result = run([cand, first_fill, second_fill])
        row = result.final_state["trades"][trade_id]
        assert row["fill_model_result"] == {"fill_px_ticks": 101}
        assert kinds(result.events) == [
            ledger.SHADOW_TRADE_RECORDED, ledger.SHADOW_TRADE_RESOLVED, ledger.LEVER_REFUSAL]
        assert result.events[-1]["reason_code"] == "SHADOW_LINEAGE_INCOMPLETE"

    def test_resolving_before_the_frozen_watermark_is_refused(self):
        cand = candidate("c1", "CAND-1", "HYP-1", watermark_us=1_000)
        trade_id = ledger._shadow_trade_id(cand["payload"])
        stale = fill_model("f1", trade_id, evaluated_at_watermark_us=999)
        result = run([cand, stale])
        row = result.final_state["trades"][trade_id]
        assert row["fill_model_result"] == ledger.FILL_MODEL_PENDING
        assert kinds(result.events) == [ledger.SHADOW_TRADE_RECORDED, ledger.LEVER_REFUSAL]
        assert result.events[-1]["reason_code"] == "SHADOW_LINEAGE_INCOMPLETE"

    def test_resolving_exactly_at_the_frozen_watermark_is_lawful_inclusive_boundary(self):
        cand = candidate("c1", "CAND-1", "HYP-1", watermark_us=1_000)
        trade_id = ledger._shadow_trade_id(cand["payload"])
        exact = fill_model("f1", trade_id, evaluated_at_watermark_us=1_000)
        result = run([cand, exact])
        row = result.final_state["trades"][trade_id]
        assert row["fill_model_result"] == {"fill_px_ticks": 101}


class TestMalformedEnvelope:
    def test_unknown_kind_raises(self):
        with pytest.raises(ShadowLedgerError):
            ShadowLedger().transition(
                ShadowLedger().initial_state(), {"event_id": "x", "kind": "NOPE", "payload": {}},
                {}, {})

    def test_non_object_payload_raises(self):
        with pytest.raises(ShadowLedgerError):
            ShadowLedger().transition(
                ShadowLedger().initial_state(),
                {"event_id": "x", "kind": "SHADOW_CANDIDATE", "payload": "not-a-dict"}, {}, {})


class TestInvariance:
    def test_prefix_and_restart_and_duplicate(self):
        cand = candidate("c1", "CAND-1", "HYP-1")
        trade_id = ledger._shadow_trade_id(cand["payload"])
        full = [
            cand,
            candidate("c2", "CAND-2", "HYP-2", flags={"horizon": False}),
            fill_model("f1", trade_id),
        ]
        whole = run(full)
        prefix = run(full[:2])
        resumed = run(full[2:], initial=prefix.final_state)
        assert resumed.final_state == whole.final_state

        replayed_from_scratch = run(full + [full[-1]])  # exact duplicate final envelope
        assert replayed_from_scratch.duplicate_count == 1
        assert replayed_from_scratch.final_state == whole.final_state


class TestShadowMoneyContamination:
    """CTL-4 / LEV-0089 (LEV-V-0100/0116): a SHADOW candidate/resolution carrying a venue money
    identity anywhere is quarantined SHADOW_MONEY_CONTAMINATION — no row built, state untouched."""

    def test_candidate_geometry_with_a_venue_trade_id_is_quarantined(self):
        result = run([candidate("c1", "CAND-1", "HYP-1",
                                 proposed_geometry={"entry": 1, "venue_trade_id": "VT-9"})])
        assert kinds(result.events) == [ledger.LEVER_REFUSAL]
        assert result.events[-1]["reason_code"] == "SHADOW_MONEY_CONTAMINATION"
        assert result.final_state == ShadowLedger().initial_state()

    @pytest.mark.parametrize(
        "field", ["venue_order_id", "venue_trade_id", "account_id", "raw_" + "cred" + "entials"])
    def test_each_venue_identity_field_anywhere_in_the_candidate_refuses(self, field):
        result = run([candidate("c1", "CAND-1", "HYP-1", flags={field: "x"})])
        assert result.events[-1]["reason_code"] == "SHADOW_MONEY_CONTAMINATION"
        assert result.final_state["trades"] == {}

    def test_contaminant_nested_inside_market_watermark_is_caught(self):
        cand = candidate("c1", "CAND-1", "HYP-1")
        cand["payload"]["market_watermark"]["venue_order_id"] = "VO-1"
        result = run([cand])
        assert result.events[-1]["reason_code"] == "SHADOW_MONEY_CONTAMINATION"

    def test_a_clean_candidate_still_records_a_trade(self):
        result = run([candidate("c1", "CAND-1", "HYP-1")])
        assert kinds(result.events) == [ledger.SHADOW_TRADE_RECORDED]

    def test_fill_model_carrying_a_venue_identity_is_quarantined(self):
        cand = candidate("c1", "CAND-1", "HYP-1")
        trade_id = ledger._shadow_trade_id(cand["payload"])
        result = run([cand, fill_model("f1", trade_id,
                                       fill_model_result={"result": "FILLED",
                                                          "venue_trade_id": "VT-1"})])
        assert result.events[-1]["reason_code"] == "SHADOW_MONEY_CONTAMINATION"
        # the frozen trade row is unresolved (its pending fill-model untouched)
        row = result.final_state["trades"][trade_id]
        assert row["fill_model_result"] == ledger.FILL_MODEL_PENDING
