"""F12 causal order block battery: opposing-predicate strict inequality, lookback boundary,
tie-break, zone geometry, BOS-horizon confirm/expire boundary, late-BOS/mismatched-direction
ignore, buffered-break boundary, LONG/SHORT mirror, invariance, fail-closed parameters."""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import transition  # noqa: E402
from triad_origin.structures import common  # noqa: E402
from triad_origin.structures import order_block_registry as ob  # noqa: E402
from triad_origin.structures.common import StructureLawError  # noqa: E402
from triad_origin.structures.order_block_registry import OrderBlockRegistry  # noqa: E402

PARAMS = {
    ob.PARAM_ORDER_BLOCK_LOOKBACK_BARS: 8,
    ob.PARAM_ORDER_BLOCK_BOS_HORIZON_BARS: 5,
    ob.PARAM_ORDER_BLOCK_BREAK_BUFFER_RULE: common.DECLARED_BOS_CLOSE_BUFFER,
}


def candidate(source_id, offset, open_ticks, close_ticks, high_ticks, low_ticks):
    return {"source_id": source_id, "offset": offset, "open_ticks": open_ticks,
            "close_ticks": close_ticks, "high_ticks": high_ticks, "low_ticks": low_ticks}


def batch(event_id, direction, candidates, origin_index=100, availability_index=100):
    return {"event_id": event_id, "kind": "ORIGIN_SEARCH_BATCH",
            "payload": {"displacement_origin_bar_index": origin_index,
                        "displacement_direction": direction,
                        "displacement_availability_bar_index": availability_index,
                        "candidates": candidates}}


def bos(event_id, bos_bar_index, bos_direction):
    return {"event_id": event_id, "kind": "LINKED_BOS",
            "payload": {"bos_bar_index": bos_bar_index, "bos_direction": bos_direction}}


def horizon_elapsed(event_id, current_bar_index):
    return {"event_id": event_id, "kind": "HORIZON_ELAPSED",
            "payload": {"current_bar_index": current_bar_index}}


def bar(event_id, close_ticks, atr=20):
    return {"event_id": event_id, "kind": "BAR",
            "payload": {"close_ticks": close_ticks, "atr14_ticks": atr}}


def run(inputs, params=None, initial=None):
    return transition.run(OrderBlockRegistry(), inputs, params or PARAMS, initial=initial)


def pending(events):
    return [e for e in events if e.get("event_kind") == ob.ORDER_BLOCK_PENDING]


def confirmed(events):
    return [e for e in events if e.get("event_kind") == ob.ORDER_BLOCK_CONFIRMED]


def expired(events):
    return [e for e in events if e.get("event_kind") == ob.ORDER_BLOCK_EXPIRED]


def broken(events):
    return [e for e in events if e.get("event_kind") == ob.ORDER_BLOCK_BROKEN]


def abstentions(events):
    return [e for e in events if e.get("event_kind") == "NAMED_ABSTENTION"]


# --- Opposing-predicate strict inequality (doji rejected), both directions -----------------------


def test_long_doji_is_never_opposing_but_a_bearish_body_qualifies():
    doji = run([batch("b1", common.LONG, [candidate("s1", 1, 1000, 1000, 1010, 990)])])
    assert pending(doji.events) == []
    (event,) = abstentions(doji.events)
    assert event["reason_code"] == "F12_NO_OPPOSING_ORIGIN_IN_LOOKBACK"

    bearish = run([batch("b1", common.LONG, [candidate("s1", 1, 1000, 990, 1010, 980)])])
    (event,) = pending(bearish.events)
    assert event["direction"] == common.LONG
    assert event["origin_source_id"] == "s1"


def test_short_doji_is_never_opposing_but_a_bullish_body_qualifies():
    doji = run([batch("b1", common.SHORT, [candidate("s1", 1, 1000, 1000, 1010, 990)])])
    assert pending(doji.events) == []
    (event,) = abstentions(doji.events)
    assert event["reason_code"] == "F12_NO_OPPOSING_ORIGIN_IN_LOOKBACK"

    bullish = run([batch("b1", common.SHORT, [candidate("s1", 1, 1000, 1010, 1020, 990)])])
    (event,) = pending(bullish.events)
    assert event["direction"] == common.SHORT
    assert event["origin_source_id"] == "s1"


# --- Lookback boundary: W=8 considers offsets 1..8 only, offset 9 excluded ------------------------


def test_lookback_boundary_excludes_the_ninth_offset_even_when_it_alone_would_qualify():
    non_qualifying = [candidate(f"s{i}", i, 1000, 1000, 1010, 990) for i in range(1, 9)]  # dojis
    would_qualify_but_excluded = candidate("s9", 9, 1000, 990, 1010, 980)  # bearish, opposes LONG
    result = run([batch("b1", common.LONG, non_qualifying + [would_qualify_but_excluded])])
    assert pending(result.events) == []
    (event,) = abstentions(result.events)
    assert event["reason_code"] == "F12_NO_OPPOSING_ORIGIN_IN_LOOKBACK"
    assert event["refs"]["lookback_bars"] == 8


def test_lookback_boundary_at_exactly_offset_eight_qualifies():
    result = run([batch("b1", common.LONG, [candidate("s8", 8, 1000, 990, 1010, 980)])])
    (event,) = pending(result.events)
    assert event["origin_offset"] == 8


# --- Tie-break: latest (smallest offset) wins; ties by source_id ONLY (no candle-body notional) --


def test_latest_smallest_offset_wins_over_an_earlier_larger_notional_candidate():
    later_small = candidate("s_late", 1, 1000, 999, 1010, 990)     # offset 1, notional 1
    earlier_large = candidate("s_early", 4, 1000, 500, 1010, 480)  # offset 4, notional 500
    result = run([batch("b1", common.LONG, [earlier_large, later_small])])
    (event,) = pending(result.events)
    assert event["origin_source_id"] == "s_late"
    assert event["origin_offset"] == 1


def test_offset_tie_ignores_body_notional_and_breaks_by_minimum_source_id():
    # RC3 errata removes the body quote-notional key: a smaller-body candidate whose source_id is
    # lexicographically smaller WINS over a larger-body candidate at the same offset. (The pre-fix
    # code selected "z_large" on the removed larger-notional key.)
    small_body = candidate("a_small", 3, 1000, 999, 1010, 990)   # |C-O| = 1,   source "a_small"
    large_body = candidate("z_large", 3, 1000, 900, 1010, 890)   # |C-O| = 100, source "z_large"
    result = run([batch("b1", common.LONG, [large_body, small_body])])
    (event,) = pending(result.events)
    assert event["origin_source_id"] == "a_small"


def test_offset_tie_breaks_by_minimum_source_id_regardless_of_body():
    zulu = candidate("zulu", 3, 1000, 900, 1010, 890)
    alpha = candidate("alpha", 3, 1000, 900, 1010, 890)
    result = run([batch("b1", common.LONG, [zulu, alpha])])
    (event,) = pending(result.events)
    assert event["origin_source_id"] == "alpha"


# --- Zone geometry: exact PAR-161 edges, never the full bar range ---------------------------------


def test_long_zone_is_low_origin_to_open_origin():
    result = run([batch("b1", common.LONG, [candidate("s1", 1, 1000, 990, 1010, 980)])])
    (event,) = pending(result.events)
    assert event["zone_low_ticks"] == 980   # low_origin
    assert event["zone_high_ticks"] == 1000  # open_origin


def test_short_zone_is_open_origin_to_high_origin():
    result = run([batch("b1", common.SHORT, [candidate("s1", 1, 1000, 1010, 1020, 990)])])
    (event,) = pending(result.events)
    assert event["zone_low_ticks"] == 1000   # open_origin
    assert event["zone_high_ticks"] == 1020  # high_origin


# --- BOS-horizon confirmation boundary: fifth included, sixth fails (PAR-160) ---------------------


def _long_pending_batch(event_id="b1", availability=100):
    return batch(event_id, common.LONG, [candidate("s1", 1, 1000, 990, 1010, 980)],
                 origin_index=availability, availability_index=availability)


def test_bos_confirms_at_exactly_the_fifth_bar_after_availability():
    result = run([_long_pending_batch(availability=100), bos("bos1", 105, common.LONG)])
    (event,) = confirmed(result.events)
    assert event["bos_bar_index"] == 105
    (block,) = result.final_state["order_blocks"].values()
    assert block["state"] == ob.STATE_CONFIRMED


def test_bos_does_not_confirm_at_the_sixth_bar_after_availability():
    result = run([_long_pending_batch(availability=100), bos("bos1", 106, common.LONG)])
    assert confirmed(result.events) == []
    (block,) = result.final_state["order_blocks"].values()
    assert block["state"] == ob.STATE_PENDING


def test_bos_at_availability_itself_does_not_confirm_zero_bars_after_displacement():
    # PAR-160 unit is "finalized bars AFTER displacement": a BOS on the availability bar itself is
    # zero bars after and is OUTSIDE the window. (The pre-fix code confirmed here off the
    # inclusive lower edge.)
    result = run([_long_pending_batch(availability=100), bos("bos1", 100, common.LONG)])
    assert confirmed(result.events) == []
    (block,) = result.final_state["order_blocks"].values()
    assert block["state"] == ob.STATE_PENDING


def test_bos_confirms_at_the_first_bar_after_availability():
    result = run([_long_pending_batch(availability=100), bos("bos1", 101, common.LONG)])
    (event,) = confirmed(result.events)
    assert event["bos_bar_index"] == 101


# --- Mismatched-direction BOS is ignored, not an error --------------------------------------------


def test_mismatched_direction_bos_is_ignored_and_block_stays_pending():
    result = run([_long_pending_batch(), bos("bos1", 102, common.SHORT)])
    assert confirmed(result.events) == []
    assert abstentions(result.events) == []
    (block,) = result.final_state["order_blocks"].values()
    assert block["state"] == ob.STATE_PENDING


# --- PENDING -> EXPIRED on horizon elapsed with no BOS ---------------------------------------------


def test_horizon_elapsed_expires_a_pending_block_with_no_confirming_bos():
    result = run([_long_pending_batch(availability=100), horizon_elapsed("h1", 106)])
    (event,) = expired(result.events)
    assert event["bos_horizon_deadline_bar_index"] == 105
    (block,) = result.final_state["order_blocks"].values()
    assert block["state"] == ob.STATE_EXPIRED


def test_horizon_elapsed_at_exactly_the_deadline_does_not_expire():
    result = run([_long_pending_batch(availability=100), horizon_elapsed("h1", 105)])
    assert expired(result.events) == []
    (block,) = result.final_state["order_blocks"].values()
    assert block["state"] == ob.STATE_PENDING


def test_no_bos_and_no_horizon_elapsed_marker_stays_pending_forever_in_this_view():
    # Open concern, exercised directly: absence of a future BOS is not itself observed as a
    # negative signal — this machine reacts only to what it is explicitly told.
    result = run([_long_pending_batch()])
    (block,) = result.final_state["order_blocks"].values()
    assert block["state"] == ob.STATE_PENDING


# --- Late BOS after expiry is ignored, never adopted ------------------------------------------------


def test_late_bos_after_expiry_is_ignored():
    result = run([
        _long_pending_batch(availability=100),
        horizon_elapsed("h1", 106),
        bos("bos1", 103, common.LONG),   # would have been in-horizon, but the block is EXPIRED
    ])
    assert confirmed(result.events) == []
    (block,) = result.final_state["order_blocks"].values()
    assert block["state"] == ob.STATE_EXPIRED


# --- CONFIRMED -> BROKEN exact buffer boundary (ATR 20 => buffer 1, PAR-163/PAR-043) ---------------


def test_long_block_breaks_exactly_at_far_edge_minus_buffer_not_at_the_edge():
    inputs = [
        _long_pending_batch(availability=100),  # far_edge = low_origin = 980
        bos("bos1", 103, common.LONG),
    ]
    at_edge = run(inputs + [bar("bar1", 980)])
    assert broken(at_edge.events) == []
    one_under = run(inputs + [bar("bar1", 979)])
    (event,) = broken(one_under.events)
    assert event["far_edge_ticks"] == 980
    assert event["buffer_ticks"] == 1
    assert event["close_ticks"] == 979
    (block,) = one_under.final_state["order_blocks"].values()
    assert block["state"] == ob.STATE_BROKEN


def test_short_block_breaks_exactly_at_far_edge_plus_buffer_not_at_the_edge():
    inputs = [
        batch("b1", common.SHORT, [candidate("s1", 1, 1000, 1010, 1020, 990)],
              origin_index=100, availability_index=100),  # far_edge = high_origin = 1020
        bos("bos1", 103, common.SHORT),
    ]
    at_edge = run(inputs + [bar("bar1", 1020)])
    assert broken(at_edge.events) == []
    one_over = run(inputs + [bar("bar1", 1021)])
    (event,) = broken(one_over.events)
    assert event["far_edge_ticks"] == 1020
    assert event["buffer_ticks"] == 1
    assert event["close_ticks"] == 1021


def test_pending_block_never_break_checked_only_confirmed_ones_are():
    result = run([_long_pending_batch(availability=100), bar("bar1", 1)])
    assert broken(result.events) == []
    (block,) = result.final_state["order_blocks"].values()
    assert block["state"] == ob.STATE_PENDING


def test_missing_atr_on_a_bar_observation_abstains_and_checks_no_break():
    inputs = [_long_pending_batch(availability=100), bos("bos1", 103, common.LONG)]
    result = run(inputs + [bar("bar1", 1, atr=None)])
    assert broken(result.events) == []
    (event,) = abstentions(result.events)
    assert event["reason_code"] == "F12_NO_ATR"
    (block,) = result.final_state["order_blocks"].values()
    assert block["state"] == ob.STATE_CONFIRMED


def test_broken_block_never_re_evaluated():
    inputs = [
        _long_pending_batch(availability=100),
        bos("bos1", 103, common.LONG),
        bar("bar1", 979),  # breaks
    ]
    broken_once = run(inputs)
    (b1,) = broken(broken_once.events)
    again = run(inputs + [bar("bar2", 1)])  # would trivially "break" again if re-evaluated
    assert len(broken(again.events)) == 1
    (b2,) = broken(again.events)
    assert b1 == b2  # the second BAR never produced a second BROKEN event


# --- LONG/SHORT mirror: full price reflection through PENDING -> CONFIRMED -> BROKEN --------------


def reflect_candidate(cand):
    return {"source_id": cand["source_id"], "offset": cand["offset"],
            "open_ticks": -cand["open_ticks"], "close_ticks": -cand["close_ticks"],
            "high_ticks": -cand["low_ticks"], "low_ticks": -cand["high_ticks"]}


def reflect_envelope(env):
    kind = env["kind"]
    payload = dict(env["payload"])
    if kind == "ORIGIN_SEARCH_BATCH":
        payload["displacement_direction"] = common.opposite(payload["displacement_direction"])
        payload["candidates"] = [reflect_candidate(c) for c in payload["candidates"]]
    elif kind == "LINKED_BOS":
        payload["bos_direction"] = common.opposite(payload["bos_direction"])
    elif kind == "BAR":
        payload["close_ticks"] = -payload["close_ticks"]
    return {"event_id": env["event_id"], "kind": kind, "payload": payload}


def mirror_event(event):
    kind = event.get("event_kind")
    if kind == ob.ORDER_BLOCK_PENDING:
        return dict(
            event, direction=common.opposite(event["direction"]),
            origin_open_ticks=-event["origin_open_ticks"],
            origin_close_ticks=-event["origin_close_ticks"],
            origin_high_ticks=-event["origin_low_ticks"],
            origin_low_ticks=-event["origin_high_ticks"],
            zone_low_ticks=-event["zone_high_ticks"],
            zone_high_ticks=-event["zone_low_ticks"])
    if kind in (ob.ORDER_BLOCK_CONFIRMED, ob.ORDER_BLOCK_EXPIRED):
        return dict(event, direction=common.opposite(event["direction"]))
    if kind == ob.ORDER_BLOCK_BROKEN:
        return dict(
            event, direction=common.opposite(event["direction"]),
            far_edge_ticks=-event["far_edge_ticks"], close_ticks=-event["close_ticks"])
    return dict(event)


def _straight_flow():
    return [
        batch("b1", common.LONG, [candidate("s1", 1, 1000, 990, 1010, 980)],
              origin_index=100, availability_index=100),
        bos("bos1", 103, common.LONG),
        bar("bar1", 979),  # breaks: far_edge(980) - buffer(1) = 979
    ]


def test_mirror_law_exact_algebraic_symmetry_through_the_full_lifecycle():
    straight = _straight_flow()
    forward = run(straight)
    mirrored = run([reflect_envelope(env) for env in straight])
    assert mirrored.events == [mirror_event(event) for event in forward.events]
    assert broken(forward.events)[0]["direction"] == common.LONG
    assert broken(mirrored.events)[0]["direction"] == common.SHORT


# --- Prefix / restart / duplicate invariance --------------------------------------------------------


def test_prefix_and_restart_invariance_across_every_cut_point():
    inputs = _straight_flow()
    full = run(inputs)
    for cut in range(1, len(inputs)):
        head = run(inputs[:cut])
        tail = run(inputs[cut:], initial=head.final_state)
        assert head.events + tail.events == full.events
        assert tail.final_state == full.final_state


def test_prefix_and_restart_invariance_on_an_abstention_path():
    inputs = [
        batch("b1", common.LONG, [candidate("s1", 1, 1000, 1000, 1010, 990)]),  # doji: abstains
        batch("b2", common.LONG, [candidate("s2", 1, 1000, 990, 1010, 980)]),   # qualifies
    ]
    full = run(inputs)
    for cut in range(1, len(inputs)):
        head = run(inputs[:cut])
        tail = run(inputs[cut:], initial=head.final_state)
        assert head.events + tail.events == full.events
        assert tail.final_state == full.final_state


def test_exact_duplicate_envelope_is_deduped_by_the_driver():
    repeated = bos("bos1", 103, common.LONG)
    result = run([_long_pending_batch(), repeated, repeated])
    assert result.duplicate_count == 1


def test_machine_level_idempotency_for_repeated_event_id():
    machine = OrderBlockRegistry()
    inputs = _straight_flow()
    state = machine.initial_state()
    for envelope in inputs:
        state = machine.transition(state, envelope, PARAMS, {}).state
    again = machine.transition(state, inputs[-1], PARAMS, {})
    assert again.state == state
    assert again.events == ()


# --- Fail-closed parameter and shape law ------------------------------------------------------------


def test_missing_required_params_fail_closed():
    with pytest.raises(transition.MissingParameterError):
        run([_long_pending_batch()], params={
            ob.PARAM_ORDER_BLOCK_BOS_HORIZON_BARS: 5,
            ob.PARAM_ORDER_BLOCK_BREAK_BUFFER_RULE: common.DECLARED_BOS_CLOSE_BUFFER})
    with pytest.raises(transition.MissingParameterError):
        run([_long_pending_batch()], params={
            ob.PARAM_ORDER_BLOCK_LOOKBACK_BARS: 8,
            ob.PARAM_ORDER_BLOCK_BREAK_BUFFER_RULE: common.DECLARED_BOS_CLOSE_BUFFER})
    with pytest.raises(transition.MissingParameterError):
        run([_long_pending_batch()], params={
            ob.PARAM_ORDER_BLOCK_LOOKBACK_BARS: 8,
            ob.PARAM_ORDER_BLOCK_BOS_HORIZON_BARS: 5})


def test_foreign_break_buffer_rule_string_refuses():
    with pytest.raises(StructureLawError):
        run([_long_pending_batch()], params=dict(
            PARAMS, **{ob.PARAM_ORDER_BLOCK_BREAK_BUFFER_RULE: common.DECLARED_EQUAL_LEVEL_TOLERANCE}))


@pytest.mark.parametrize("bad", [0, -1, True])
def test_non_positive_lookback_or_horizon_refuses(bad):
    with pytest.raises(StructureLawError):
        run([_long_pending_batch()], params=dict(
            PARAMS, **{ob.PARAM_ORDER_BLOCK_LOOKBACK_BARS: bad}))
    with pytest.raises(StructureLawError):
        run([_long_pending_batch()], params=dict(
            PARAMS, **{ob.PARAM_ORDER_BLOCK_BOS_HORIZON_BARS: bad}))


def test_unknown_displacement_direction_refuses():
    with pytest.raises(StructureLawError):
        run([batch("b1", "UP", [candidate("s1", 1, 1000, 990, 1010, 980)])])


def test_candidates_must_be_a_list():
    bad = batch("b1", common.LONG, [])
    bad["payload"]["candidates"] = "not a list"
    with pytest.raises(StructureLawError):
        run([bad])


def test_candidate_low_exceeds_high_refuses():
    with pytest.raises(StructureLawError):
        run([batch("b1", common.LONG, [candidate("s1", 1, 1000, 990, 980, 1010)])])


def test_candidate_missing_source_id_refuses():
    bad = candidate("s1", 1, 1000, 990, 1010, 980)
    bad["source_id"] = ""
    with pytest.raises(StructureLawError):
        run([batch("b1", common.LONG, [bad])])


def test_wrong_kind_and_non_object_payload_refuse():
    with pytest.raises(StructureLawError):
        run([{"event_id": "e1", "kind": "PIVOT", "payload": {}}])
    with pytest.raises(StructureLawError):
        run([{"event_id": "e1", "kind": "BAR", "payload": "not a dict"}])
