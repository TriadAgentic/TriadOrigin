"""Flow atoms F15/F16/F17 battery: GV-013, the F16 hand-worked vector, GV-014, mirror laws,
boundaries, invariance, and the no-future-venue-state proof."""

from __future__ import annotations

import pytest

from triad_origin import transition
from triad_origin.structures import common, flow_atoms
from triad_origin.structures.common import StructureLawError

# --- F15 fixtures -----------------------------------------------------------------------------

F15_PARAMS = {
    flow_atoms.PARAM_TFI_WINDOW_TRADES: 100,
    flow_atoms.PARAM_TFI_WINDOW_MAX_AGE_MS: 2000,
    flow_atoms.PARAM_TFI_MIN_TRADES: 2,
}


def trade(event_id, notional, side, event_time_us=0, evaluation_time_us=0):
    return {
        "event_id": event_id, "kind": "TRADE", "evaluation_time_us": evaluation_time_us,
        "payload": {"quote_notional_ticks": notional, "aggressor_side": side,
                    "event_time_us": event_time_us},
    }


def run_f15(inputs, params=None, initial=None):
    return transition.run(flow_atoms.TradeFlowImbalance(), inputs,
                           params if params is not None else F15_PARAMS, initial=initial)


# --- F16 fixtures -----------------------------------------------------------------------------

F16_PARAMS = {
    flow_atoms.PARAM_OFI_WINDOW_UPDATES: 100,
    flow_atoms.PARAM_OFI_WINDOW_MAX_AGE_MS: 1000,
    flow_atoms.PARAM_OFI_MIN_UPDATES: 2,
}


def book_update(event_id, seq, bid_price, bid_qty, ask_price, ask_qty, watermark=True):
    return {
        "event_id": event_id, "kind": "BOOK_UPDATE",
        "payload": {"best_bid_price_ticks": bid_price, "best_bid_qty_steps": bid_qty,
                    "best_ask_price_ticks": ask_price, "best_ask_qty_steps": ask_qty,
                    "sequence": seq, "watermark_complete": watermark},
    }


def run_f16(inputs, params=None, initial=None):
    return transition.run(flow_atoms.OrderFlowImbalance(), inputs,
                           params if params is not None else F16_PARAMS, initial=initial)


# --- F17 fixtures -----------------------------------------------------------------------------

# TEST-ONLY ratified stand-in for RC3-PAR-STRUCT-002 (BOOK_TILT_MIN_QUOTE_DEPTH), which remains
# NOT_RATIFIED in the registry. Chosen at 1000 so GV-014's denominator sits exactly at the
# inclusive boundary (PAR-009: denominator == minimum passes).
TEST_BOOK_TILT_MIN_QUOTE_DEPTH = 1000

F17_PARAMS = {flow_atoms.PARAM_BOOK_TILT_MIN_QUOTE_DEPTH: TEST_BOOK_TILT_MIN_QUOTE_DEPTH}


def depth(event_id, bid, ask):
    return {
        "event_id": event_id, "kind": "BOOK_DEPTH",
        "payload": {"bid_quote_depth_ticks_steps": bid, "ask_quote_depth_ticks_steps": ask},
    }


def run_f17(inputs, params=None, initial=None):
    return transition.run(flow_atoms.BookDepthTilt(), inputs,
                           params if params is not None else F17_PARAMS, initial=initial)


# --- shared helpers ---------------------------------------------------------------------------


def features(events, formula):
    return [e for e in events if e.get("event_kind") == "FEATURE" and e.get("formula") == formula]


def abstentions(events):
    return [e for e in events if e.get("event_kind") == "NAMED_ABSTENTION"]


# =================================================================================================
# F15 — trade flow imbalance
# =================================================================================================


def test_gv013_buy70_sell30_yields_raw_unreduced_40_over_100():
    result = run_f15([
        trade("t1", 70, flow_atoms.TRADE_SIDE_BUY),
        trade("t2", 30, flow_atoms.TRADE_SIDE_SELL),
    ])
    # trade 1 alone: window has 1 < tfi_min_trades(2) -> coverage abstention.
    (coverage,) = abstentions(result.events)
    assert coverage["reason_code"] == "F15_TFI_INSUFFICIENT_COVERAGE"
    # trade 2: window has 2 >= 2 -> 40/100 exact, never reduced to 2/5.
    (feat,) = features(result.events, "F15")
    assert feat["numerator"] == 40
    assert feat["denominator"] == 100
    assert feat["buy_quote_ticks"] == 70
    assert feat["sell_quote_ticks"] == 30
    assert feat["trade_count"] == 2
    assert feat["feature_version"] == flow_atoms.F15_FEATURE_VERSION


def test_f15_zero_denominator_is_a_named_abstention_never_a_fabricated_zero():
    result = run_f15([
        trade("t1", 0, flow_atoms.TRADE_SIDE_BUY),
        trade("t2", 0, flow_atoms.TRADE_SIDE_SELL),
    ])
    reasons = [event["reason_code"] for event in abstentions(result.events)]
    assert reasons == ["F15_TFI_INSUFFICIENT_COVERAGE", "F15_TFI_ZERO_DENOMINATOR"]
    assert features(result.events, "F15") == []


def test_f15_insufficient_coverage_at_the_real_par054_default_of_twenty():
    params = dict(F15_PARAMS, **{flow_atoms.PARAM_TFI_MIN_TRADES: 20})
    inputs = [trade(f"t{i}", 10, flow_atoms.TRADE_SIDE_BUY) for i in range(5)]
    result = run_f15(inputs, params=params)
    assert features(result.events, "F15") == []
    reasons = [event["reason_code"] for event in abstentions(result.events)]
    assert reasons == ["F15_TFI_INSUFFICIENT_COVERAGE"] * 5
    for event in abstentions(result.events):
        assert event["refs"]["need_trades"] == 20


def test_f15_buy_sell_swap_negates_the_numerator_exactly():
    inputs = [
        trade("t1", 70, flow_atoms.TRADE_SIDE_BUY, event_time_us=100, evaluation_time_us=100),
        trade("t2", 30, flow_atoms.TRADE_SIDE_SELL, event_time_us=150, evaluation_time_us=150),
        trade("t3", 55, flow_atoms.TRADE_SIDE_SELL, event_time_us=200, evaluation_time_us=200),
        trade("t4", 12, flow_atoms.TRADE_SIDE_BUY, event_time_us=250, evaluation_time_us=250),
    ]
    swapped = []
    for env in inputs:
        payload = dict(env["payload"])
        payload["aggressor_side"] = (
            flow_atoms.TRADE_SIDE_SELL if payload["aggressor_side"] == flow_atoms.TRADE_SIDE_BUY
            else flow_atoms.TRADE_SIDE_BUY)
        swapped.append(dict(env, payload=payload))
    straight = features(run_f15(inputs).events, "F15")
    mirrored = features(run_f15(swapped).events, "F15")
    assert len(straight) == len(mirrored) > 0
    for s, m in zip(straight, mirrored):
        assert m["numerator"] == -s["numerator"]
        assert m["denominator"] == s["denominator"]
        assert m["buy_quote_ticks"] == s["sell_quote_ticks"]
        assert m["sell_quote_ticks"] == s["buy_quote_ticks"]


def test_f15_age_window_boundary_is_inclusive():
    # max_age_ms = 2000 -> max_age_us = 2_000_000; a trade exactly that old is still in-window
    # (PAR-009 inclusive) and one microsecond older is evicted.
    params = dict(F15_PARAMS, **{flow_atoms.PARAM_TFI_MIN_TRADES: 1})
    at_boundary = run_f15(
        [trade("t1", 10, flow_atoms.TRADE_SIDE_BUY, event_time_us=0, evaluation_time_us=2_000_000)],
        params=params)
    assert len(features(at_boundary.events, "F15")) == 1

    just_over = run_f15(
        [trade("t1", 10, flow_atoms.TRADE_SIDE_BUY, event_time_us=0, evaluation_time_us=2_000_001)],
        params=params)
    (event,) = abstentions(just_over.events)
    assert event["reason_code"] == "F15_TFI_INSUFFICIENT_COVERAGE"
    assert event["refs"]["have_trades"] == 0


def test_f15_missing_required_param_fails_closed():
    with pytest.raises(transition.MissingParameterError):
        run_f15([trade("t1", 10, flow_atoms.TRADE_SIDE_BUY)],
                params={flow_atoms.PARAM_TFI_WINDOW_TRADES: 100})


def test_f15_unknown_aggressor_side_raises():
    with pytest.raises(StructureLawError):
        run_f15([trade("t1", 10, "CROSS")])


def test_f15_trade_after_evaluation_time_raises():
    with pytest.raises(StructureLawError):
        run_f15([trade("t1", 10, flow_atoms.TRADE_SIDE_BUY, event_time_us=100,
                        evaluation_time_us=99)])


def test_f15_exact_duplicate_envelope_is_deduped_by_the_driver():
    t = trade("t1", 10, flow_atoms.TRADE_SIDE_BUY)
    result = run_f15([t, t])
    assert result.duplicate_count == 1
    assert result.events == run_f15([t]).events


def test_f15_prefix_and_restart_invariance():
    inputs = [
        trade(f"t{i}", 10 * (i + 1),
              flow_atoms.TRADE_SIDE_BUY if i % 2 == 0 else flow_atoms.TRADE_SIDE_SELL,
              event_time_us=i * 10, evaluation_time_us=i * 10)
        for i in range(6)
    ]
    full = run_f15(inputs)
    for cut in range(1, len(inputs)):
        head = run_f15(inputs[:cut])
        tail = run_f15(inputs[cut:], initial=head.final_state)
        assert head.events + tail.events == full.events
        assert tail.final_state == full.final_state


def test_f15_never_reaches_into_future_input():
    inputs = [
        trade(f"t{i}", 10,
              flow_atoms.TRADE_SIDE_BUY if i % 2 == 0 else flow_atoms.TRADE_SIDE_SELL,
              event_time_us=i, evaluation_time_us=i)
        for i in range(5)
    ]
    state = None
    collected = []
    machine = flow_atoms.TradeFlowImbalance()
    for env in inputs:
        result = transition.run(machine, [env], F15_PARAMS, initial=state)
        collected.extend(result.events)
        state = result.final_state
    batched = run_f15(inputs)
    assert collected == batched.events
    assert state == batched.final_state


# =================================================================================================
# F16 — best-level order-flow imbalance
# =================================================================================================


def test_f16_hand_worked_vector_after_three_updates_ofi_is_minus_one():
    """No golden vector is linked to F16 in the bundle; hand-worked here instead.

    seq1 (baseline): Pb=100 Qb=5  Pa=101 Qa=7  (no e_n — establishes prev only)
    seq2:            Pb=100 Qb=8  Pa=101 Qa=4
      e_2 = I(100>=100)*8 - I(100<=100)*5 - I(101<=101)*4 + I(101>=101)*7 = 8-5-4+7 = 6
    seq3:            Pb=102 Qb=3  Pa=99  Qa=10
      e_3 = I(102>=100)*3 - I(102<=100)*8 - I(99<=101)*10 + I(99>=101)*4 = 3-0-10+0 = -7
    OFI over the {e_2, e_3} window = 6 + (-7) = -1.
    """
    result = run_f16([
        book_update("u1", 1, 100, 5, 101, 7),
        book_update("u2", 2, 100, 8, 101, 4),
        book_update("u3", 3, 102, 3, 99, 10),
    ])
    reasons = [event["reason_code"] for event in abstentions(result.events)]
    assert reasons == ["F16_INSUFFICIENT_COVERAGE", "F16_INSUFFICIENT_COVERAGE"]
    (feat,) = features(result.events, "F16")
    assert feat["ofi_value"] == -1
    assert feat["window_size"] == 2
    assert feat["sequence"] == 3
    assert feat["feature_version"] == "ofi.raw.v1"
    assert feat["declared_window_max_age_ms"] == 1000


def test_f16_sequence_gap_emits_abstention_and_resets_the_window():
    result = run_f16([
        book_update("u1", 1, 100, 5, 101, 7),
        book_update("u2", 2, 100, 8, 101, 4),  # e_2 accumulates: window=[6]
        book_update("u3", 5, 105, 2, 106, 2),  # gap: expected 3, got 5
    ])
    gap = [e for e in abstentions(result.events) if e["reason_code"] == "F16_SEQUENCE_GAP"]
    (gap_event,) = gap
    assert gap_event["refs"]["expected_sequence"] == 3
    assert gap_event["refs"]["got_sequence"] == 5
    assert result.final_state["window"] == []
    assert result.final_state["prev"]["sequence"] == 5

    resumed = run_f16([book_update("u4", 6, 105, 4, 106, 6)], initial=result.final_state)
    reasons = [event["reason_code"] for event in abstentions(resumed.events)]
    assert reasons == ["F16_INSUFFICIENT_COVERAGE"]  # continuous 5->6, not a second gap


def test_f16_non_increasing_sequence_raises():
    with pytest.raises(StructureLawError):
        run_f16([book_update("u1", 1, 100, 5, 101, 7), book_update("u2", 1, 100, 5, 101, 7)])
    with pytest.raises(StructureLawError):
        run_f16([book_update("u1", 1, 100, 5, 101, 7), book_update("u2", 0, 100, 5, 101, 7)])


def test_f16_watermark_incomplete_suppresses_emission_but_state_still_advances():
    params = dict(F16_PARAMS, **{flow_atoms.PARAM_OFI_MIN_UPDATES: 1})
    incomplete = run_f16([
        book_update("u1", 1, 100, 5, 101, 7),
        book_update("u2", 2, 100, 8, 101, 4, watermark=False),
    ], params=params)
    # u1: window=[] (0 < 1) -> coverage abstention. u2: window=[6] (1 >= 1) but watermark False
    # -> "refuse to emit if not True": no event at all for u2 (silent, the F04 precedent).
    assert len(incomplete.events) == 1
    assert incomplete.events[0]["reason_code"] == "F16_INSUFFICIENT_COVERAGE"

    # The incomplete-watermark update still advanced prev/window (it is not discarded), so the
    # next continuous update's OFI correctly folds in its e_n term.
    resumed = run_f16([book_update("u3", 3, 100, 8, 101, 4)], params=params,
                       initial=incomplete.final_state)
    (feat,) = features(resumed.events, "F16")
    # e_3 = I(100>=100)*8 - I(100<=100)*8 - I(101<=101)*4 + I(101>=101)*4 = 8-8-4+4 = 0
    # OFI = e_2(6) + e_3(0) = 6.
    assert feat["ofi_value"] == 6
    assert feat["window_size"] == 2


def test_f16_watermark_incomplete_marker_must_be_an_exact_bool():
    with pytest.raises(StructureLawError):
        run_f16([{
            "event_id": "u1", "kind": "BOOK_UPDATE",
            "payload": {"best_bid_price_ticks": 100, "best_bid_qty_steps": 5,
                        "best_ask_price_ticks": 101, "best_ask_qty_steps": 7,
                        "sequence": 1, "watermark_complete": 1}}])


def test_f16_missing_required_param_fails_closed():
    with pytest.raises(transition.MissingParameterError):
        run_f16([book_update("u1", 1, 100, 5, 101, 7)],
                params={flow_atoms.PARAM_OFI_WINDOW_UPDATES: 100})


def test_f16_exact_duplicate_envelope_is_deduped_by_the_driver():
    u = book_update("u1", 1, 100, 5, 101, 7)
    result = run_f16([u, u])
    assert result.duplicate_count == 1


def test_f16_prefix_and_restart_invariance():
    inputs = [
        book_update(f"u{i}", i + 1, 100 + i, 5 + i, 101 + i, 7 - (i % 3))
        for i in range(6)
    ]
    full = run_f16(inputs)
    for cut in range(1, len(inputs)):
        head = run_f16(inputs[:cut])
        tail = run_f16(inputs[cut:], initial=head.final_state)
        assert head.events + tail.events == full.events
        assert tail.final_state == full.final_state


def test_f16_never_reaches_into_future_input():
    inputs = [
        book_update(f"u{i}", i + 1, 100 + i, 5 + i, 101 + i, 7 - (i % 3))
        for i in range(6)
    ]
    state = None
    collected = []
    machine = flow_atoms.OrderFlowImbalance()
    for env in inputs:
        result = transition.run(machine, [env], F16_PARAMS, initial=state)
        collected.extend(result.events)
        state = result.final_state
    batched = run_f16(inputs)
    assert collected == batched.events
    assert state == batched.final_state


# =================================================================================================
# F17 — anchored book-depth tilt
# =================================================================================================


def test_gv014_bid600_ask400_yields_raw_unreduced_200_over_1000():
    result = run_f17([depth("d1", 600, 400)])
    (feat,) = features(result.events, "F17")
    assert feat["numerator"] == 200
    assert feat["denominator"] == 1000
    assert feat["bid_quote_depth_ticks_steps"] == 600
    assert feat["ask_quote_depth_ticks_steps"] == 400
    assert feat["feature_version"] == flow_atoms.F17_FEATURE_VERSION


def test_f17_not_ratified_yields_named_abstention_and_never_mutates_state():
    machine = flow_atoms.BookDepthTilt()
    params = {flow_atoms.PARAM_BOOK_TILT_MIN_QUOTE_DEPTH: common.NOT_RATIFIED}
    inputs = [depth("d1", 600, 400), depth("d2", 900, 100)]
    result = transition.run(machine, inputs, params)
    assert result.final_state == machine.initial_state()
    reasons = [event["reason_code"] for event in abstentions(result.events)]
    assert reasons == ["F17_UNAVAILABLE_MIN_DEPTH_NOT_RATIFIED"] * 2
    assert all(event["refs"]["parameter"] == "RC3-PAR-STRUCT-002"
               for event in abstentions(result.events))
    assert features(result.events, "F17") == []


def test_f17_zero_and_below_minimum_depth_is_insufficient_never_a_crash():
    below = run_f17([depth("d1", 500, 400)])  # denominator 900 < 1000
    (event,) = abstentions(below.events)
    assert event["reason_code"] == "F17_INSUFFICIENT_DEPTH"
    zero = run_f17([depth("d1", 0, 0)])
    (event,) = abstentions(zero.events)
    assert event["reason_code"] == "F17_INSUFFICIENT_DEPTH"
    assert features(below.events, "F17") == features(zero.events, "F17") == []


def test_f17_denominator_equal_to_the_minimum_is_inclusive():
    at_minimum = run_f17([depth("d1", 500, 500)])  # denominator == 1000
    assert len(features(at_minimum.events, "F17")) == 1
    below_minimum = run_f17([depth("d1", 500, 499)])  # denominator == 999
    (event,) = abstentions(below_minimum.events)
    assert event["reason_code"] == "F17_INSUFFICIENT_DEPTH"


def test_f17_bid_ask_swap_negates_the_numerator():
    straight = run_f17([depth("d1", 600, 400)])
    swapped = run_f17([depth("d1", 400, 600)])
    (s,) = features(straight.events, "F17")
    (m,) = features(swapped.events, "F17")
    assert m["numerator"] == -s["numerator"]
    assert m["denominator"] == s["denominator"]


def test_f17_missing_min_depth_param_fails_closed():
    with pytest.raises(transition.MissingParameterError):
        run_f17([depth("d1", 500, 500)], params={})


def test_f17_bad_ratified_min_depth_raises():
    for bad in (True, -1, "1000"):
        with pytest.raises(StructureLawError):
            run_f17([depth("d1", 500, 500)],
                    params={flow_atoms.PARAM_BOOK_TILT_MIN_QUOTE_DEPTH: bad})


def test_f17_exact_duplicate_envelope_is_deduped_by_the_driver():
    d = depth("d1", 600, 400)
    result = run_f17([d, d])
    assert result.duplicate_count == 1
    assert len(features(result.events, "F17")) == 1


def test_f17_prefix_and_restart_invariance():
    inputs = [depth(f"d{i}", 500 + i * 10, 500 - i * 5) for i in range(5)]
    full = run_f17(inputs)
    for cut in range(1, len(inputs)):
        head = run_f17(inputs[:cut])
        tail = run_f17(inputs[cut:], initial=head.final_state)
        assert head.events + tail.events == full.events
        assert tail.final_state == full.final_state


def test_f17_never_reaches_into_future_input():
    inputs = [depth(f"d{i}", 500 + i * 10, 500 - i * 5) for i in range(5)]
    state = None
    collected = []
    machine = flow_atoms.BookDepthTilt()
    for env in inputs:
        result = transition.run(machine, [env], F17_PARAMS, initial=state)
        collected.extend(result.events)
        state = result.final_state
    batched = run_f17(inputs)
    assert collected == batched.events
    assert state == batched.final_state
