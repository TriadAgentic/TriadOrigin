"""F10 three-bar FVG registry battery: GV-009, min-gap boundary, TTL boundary, fill lifecycle,
same-bar precedence, mirror law, invariance."""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import transition  # noqa: E402
from triad_origin.structures import common, fvg_registry as fvg  # noqa: E402
from triad_origin.structures.common import StructureLawError  # noqa: E402
from triad_origin.structures.fvg_registry import FvgZoneRegistry  # noqa: E402

PARAMS = {fvg.PARAM_MIN_GAP_RULE: common.DECLARED_BOS_CLOSE_BUFFER, fvg.PARAM_ZONE_TTL_BARS: 120}


def bar(seq, high, low, atr=20, event_id=None):
    return {"event_id": event_id or f"b{seq}", "kind": "BAR",
            "payload": {"high_ticks": high, "low_ticks": low, "atr14_ticks": atr, "bar_seq": seq}}


def run(inputs, params=None, initial=None):
    return transition.run(FvgZoneRegistry(), inputs, params or PARAMS, initial=initial)


def formed(events):
    return [e for e in events if e.get("event_kind") == fvg.ZONE_FORMED]


def touched(events):
    return [e for e in events if e.get("event_kind") == fvg.ZONE_TOUCHED]


def fully_filled(events):
    return [e for e in events if e.get("event_kind") == fvg.ZONE_FULLY_FILLED]


def expired(events):
    return [e for e in events if e.get("event_kind") == fvg.ZONE_EXPIRED]


def abstentions(events):
    return [e for e in events if e.get("event_kind") == "NAMED_ABSTENTION"]


# --- GV-009: raw-gap-existence boundary -----------------------------------------------------


def test_gv009_gap_one_forms_and_gap_zero_does_not():
    assert common.evaluate_declared_rational(common.DECLARED_BOS_CLOSE_BUFFER, 20) == 1
    forms = run([bar(0, 100, 90), bar(1, 99, 89), bar(2, 103, 101)])
    (event,) = formed(forms.events)
    assert event == {
        "event_kind": fvg.ZONE_FORMED, "formula": "F10", "zone_id": "fvg_b2",
        "kind": fvg.KIND_BULLISH, "direction": common.LONG,
        "zone_low_ticks": 100, "zone_high_ticks": 101, "gap_ticks": 1, "min_gap_ticks": 1,
        "atr14_ticks": 20, "origin_event_ids": ["b0", "b1", "b2"], "formation_event_id": "b2",
    }
    no_gap = run([bar(0, 100, 90), bar(1, 99, 89), bar(2, 102, 100)])
    assert formed(no_gap.events) == []
    assert abstentions(no_gap.events) == []
    assert no_gap.final_state["zones"] == []


def test_incomplete_window_yields_nothing():
    result = run([bar(0, 100, 90), bar(1, 103, 101)])
    assert formed(result.events) == []
    assert result.final_state["zones"] == []


# --- Min-gap threshold boundary (ATR raises the floor above 1) -------------------------------


def test_min_gap_threshold_equality_passes_one_less_fails():
    assert common.evaluate_declared_rational(common.DECLARED_BOS_CLOSE_BUFFER, 100) == 5
    below = run([bar(0, 100, 90, atr=100), bar(1, 99, 89, atr=100), bar(2, 108, 104, atr=100)])
    assert formed(below.events) == []
    assert abstentions(below.events) == []
    at_threshold = run(
        [bar(0, 100, 90, atr=100), bar(1, 99, 89, atr=100), bar(2, 109, 105, atr=100)])
    (event,) = formed(at_threshold.events)
    assert event["gap_ticks"] == 5
    assert event["min_gap_ticks"] == 5


# --- Missing ATR abstention -------------------------------------------------------------------


def test_missing_atr_on_a_real_gap_candidate_abstains_and_forms_nothing():
    result = run([bar(0, 100, 90), bar(1, 99, 89), bar(2, 103, 101, atr=None)])
    assert formed(result.events) == []
    (event,) = abstentions(result.events)
    assert event["reason_code"] == "F10_NO_ATR"
    assert event["formula"] == "F10"
    assert event["refs"]["event_id"] == "b2"
    assert result.final_state["zones"] == []


# --- Same-bar formation-and-touch precedence (documented: always zero-shrink) -----------------


def test_same_bar_formation_and_touch_is_legal_and_structurally_zero_shrink():
    result = run([bar(0, 100, 90), bar(1, 99, 89), bar(2, 103, 101)])
    assert len(formed(result.events)) == 1
    assert touched(result.events) == []
    assert fully_filled(result.events) == []
    (zone,) = result.final_state["zones"]
    assert zone["state"] == fvg.STATE_FORMED
    assert zone["remaining_low_ticks"] == 100
    assert zone["remaining_high_ticks"] == 101


# --- Partial-then-full fill sequence with monotonic shrink -------------------------------------


def _partial_then_full_fill_bars():
    return [
        bar(0, 100, 90, atr=100),
        bar(1, 1000, -1000, atr=100),   # wide guard: never a formation reference downstream
        bar(2, 110, 105, atr=100),      # forms zone [100, 105]; same-bar touch is degenerate
        bar(3, 103, 102, atr=100),      # partial: remaining_high 105 -> 102 (delta 3)
        bar(4, 101, 100, atr=100),      # full: remaining_high 102 -> 100 (delta 2)
    ]


def test_partial_then_full_fill_shrinks_monotonically():
    result = run(_partial_then_full_fill_bars())
    (form_event,) = formed(result.events)
    assert form_event["zone_low_ticks"] == 100
    assert form_event["zone_high_ticks"] == 105
    (touch_event,) = touched(result.events)
    assert touch_event["remaining_low_ticks"] == 100
    assert touch_event["remaining_high_ticks"] == 102
    assert touch_event["filled_delta_ticks"] == 3
    assert touch_event["touched_by_event_id"] == "b3"
    (fill_event,) = fully_filled(result.events)
    assert fill_event["filled_delta_ticks"] == 2
    assert fill_event["touched_by_event_id"] == "b4"
    (zone,) = result.final_state["zones"]
    assert zone["state"] == fvg.STATE_FULLY_FILLED
    assert zone["remaining_low_ticks"] == zone["remaining_high_ticks"] == 100


# --- A zone that is never touched expires cleanly ----------------------------------------------


def test_untouched_zone_expires_cleanly_with_its_full_original_range():
    params = dict(PARAMS, **{fvg.PARAM_ZONE_TTL_BARS: 3})
    bars = [
        bar(0, 100, 90, atr=20),
        bar(1, 1000, -1000, atr=20),      # wide guard
        bar(2, 103, 101, atr=20),         # forms zone [100, 101]
        bar(3, 103, 101, atr=20, event_id="f3"),  # grazes the boundary only; never shrinks
        bar(4, 103, 101, atr=20, event_id="f4"),
        bar(5, 103, 101, atr=20, event_id="f5"),  # age 3 == ttl 3: expires here
    ]
    result = run(bars, params)
    assert touched(result.events) == []
    assert fully_filled(result.events) == []
    (expire_event,) = expired(result.events)
    assert expire_event["expired_at_event_id"] == "f5"
    assert expire_event["bars_since_formation"] == 3
    assert expire_event["remaining_low_ticks"] == 100
    assert expire_event["remaining_high_ticks"] == 101
    (zone,) = result.final_state["zones"]
    assert zone["state"] == fvg.STATE_EXPIRED
    assert zone["remaining_low_ticks"] == 100
    assert zone["remaining_high_ticks"] == 101


# --- TTL exact-bar-120 vs 119 boundary (PAR-051) ------------------------------------------------


def _ttl_120_bars():
    bars = [bar(0, 100, 90), bar(1, 1000, -1000), bar(2, 103, 101)]
    bars += [bar(3 + i, 103, 101, event_id=f"f{i}") for i in range(120)]
    return bars


def test_ttl_expires_at_exactly_bar_120_not_119():
    bars = _ttl_120_bars()
    at_119 = run(bars[:-1])   # the zone plus only the first 119 filler bars
    assert expired(at_119.events) == []
    (zone_119,) = at_119.final_state["zones"]
    assert zone_119["state"] == fvg.STATE_FORMED
    assert zone_119["bars_since_formation"] == 119
    at_120 = run(bars)
    (expire_event,) = expired(at_120.events)
    assert expire_event["bars_since_formation"] == 120
    assert expire_event["expired_at_event_id"] == "f119"
    (zone_120,) = at_120.final_state["zones"]
    assert zone_120["state"] == fvg.STATE_EXPIRED


# --- Gap in bar_seq resets the local formation window, never a mid-air triple ------------------


def test_bar_seq_gap_resets_the_formation_window():
    bars = [bar(0, 100, 90), bar(1, 99, 89), bar(2, 103, 101, event_id="jump")]
    bars[2]["payload"]["bar_seq"] = 5  # jumps past 1 -> 5; would spuriously gap vs bar0 if kept
    result = run(bars)
    assert formed(result.events) == []
    assert result.final_state["zones"] == []
    assert result.final_state["recent"] == [
        {"event_id": "jump", "high_ticks": 103, "low_ticks": 101}]


def test_out_of_order_bar_seq_refuses():
    machine = FvgZoneRegistry()
    state = machine.transition(machine.initial_state(), bar(3, 100, 90), PARAMS, {}).state
    with pytest.raises(StructureLawError):
        machine.transition(state, bar(3, 101, 91, event_id="dup"), PARAMS, {})
    with pytest.raises(StructureLawError):
        machine.transition(state, bar(2, 101, 91, event_id="before"), PARAMS, {})


def test_low_exceeds_high_refuses():
    with pytest.raises(StructureLawError):
        run([bar(0, 90, 100)])


# --- Terminal idempotency: no double-terminal, no re-mutation after terminal -------------------


def test_terminal_zone_never_re_emits_and_stays_frozen():
    bars = _partial_then_full_fill_bars()
    full = run(bars)
    (zone_before,) = full.final_state["zones"]
    zone_id = zone_before["zone_id"]
    # Overlaps the fully-filled point [100, 100] and forms no new candidate (recent window at
    # this point is [b3(103,102), b4(101,100)]; high>=102 and low<=103 keeps it non-forming).
    later = bar(5, 105, 95, atr=100)
    result = run(bars + [later])
    assert result.events[: len(full.events)] == full.events
    new_events = result.events[len(full.events):]
    assert all(event.get("zone_id") != zone_id for event in new_events)
    (zone_after,) = [z for z in result.final_state["zones"] if z["zone_id"] == zone_id]
    assert zone_after == zone_before


def test_machine_level_idempotency_for_repeated_event_id():
    machine = FvgZoneRegistry()
    bars = _partial_then_full_fill_bars()
    state = machine.initial_state()
    for envelope in bars:
        state = machine.transition(state, envelope, PARAMS, {}).state
    again = machine.transition(state, bars[-1], PARAMS, {})
    assert again.state == state
    assert again.events == ()


# --- LONG/SHORT mirror: exact algebraic symmetry ------------------------------------------------


def mirror_envelope(envelope):
    payload = dict(envelope["payload"])
    high, low = payload["high_ticks"], payload["low_ticks"]
    payload["high_ticks"], payload["low_ticks"] = -low, -high
    return dict(envelope, payload=payload)


def mirror_event(event):
    kind = event.get("event_kind")
    if kind == fvg.ZONE_FORMED:
        flipped_kind = fvg.KIND_BEARISH if event["kind"] == fvg.KIND_BULLISH else fvg.KIND_BULLISH
        return dict(
            event, kind=flipped_kind, direction=common.opposite(event["direction"]),
            zone_low_ticks=-event["zone_high_ticks"], zone_high_ticks=-event["zone_low_ticks"])
    if kind in (fvg.ZONE_TOUCHED, fvg.ZONE_FULLY_FILLED, fvg.ZONE_EXPIRED):
        return dict(
            event, remaining_low_ticks=-event["remaining_high_ticks"],
            remaining_high_ticks=-event["remaining_low_ticks"])
    return dict(event)


def test_mirror_law_exact_algebraic_symmetry():
    bars = _partial_then_full_fill_bars()
    forward = run(bars)
    mirrored = run([mirror_envelope(env) for env in bars])
    assert mirrored.events == [mirror_event(event) for event in forward.events]
    (forward_zone,) = forward.final_state["zones"]
    (mirrored_zone,) = mirrored.final_state["zones"]
    assert mirrored_zone["kind"] == fvg.KIND_BEARISH
    assert mirrored_zone["direction"] == common.SHORT
    assert mirrored_zone["zone_low_ticks"] == -forward_zone["zone_high_ticks"]
    assert mirrored_zone["zone_high_ticks"] == -forward_zone["zone_low_ticks"]


def test_bearish_gv009_mirror_forms_a_short_zone():
    mirrored = run([mirror_envelope(bar(0, 100, 90)), mirror_envelope(bar(1, 99, 89)),
                     mirror_envelope(bar(2, 103, 101))])
    (event,) = formed(mirrored.events)
    assert event["kind"] == fvg.KIND_BEARISH
    assert event["direction"] == common.SHORT
    assert event["zone_low_ticks"] == -101
    assert event["zone_high_ticks"] == -100
    assert event["gap_ticks"] == 1


# --- Prefix / restart / duplicate invariance -----------------------------------------------------


def test_prefix_restart_duplicate_invariance():
    bars = _partial_then_full_fill_bars()
    machine = FvgZoneRegistry()
    full = transition.run(machine, bars, PARAMS)
    for cut in range(1, len(bars)):
        head = transition.run(machine, bars[:cut], PARAMS)
        tail = transition.run(machine, bars[cut:], PARAMS, initial=head.final_state)
        assert head.events + tail.events == full.events
        assert tail.final_state == full.final_state
    duplicated = transition.run(machine, bars[:2] + [bars[1]] + bars[2:], PARAMS)
    assert duplicated.duplicate_count == 1
    assert duplicated.events == full.events
    assert duplicated.final_state == full.final_state


# --- Fail-closed parameter law ---------------------------------------------------------------


def test_missing_min_gap_rule_param_fails_closed():
    with pytest.raises(transition.MissingParameterError):
        run([bar(0, 100, 90)], params={fvg.PARAM_ZONE_TTL_BARS: 120})


def test_foreign_min_gap_rule_string_refuses():
    with pytest.raises(StructureLawError):
        run([bar(0, 100, 90)], params={
            fvg.PARAM_MIN_GAP_RULE: common.DECLARED_EQUAL_LEVEL_TOLERANCE,
            fvg.PARAM_ZONE_TTL_BARS: 120})


def test_missing_zone_ttl_param_fails_closed():
    with pytest.raises(transition.MissingParameterError):
        run([bar(0, 100, 90)], params={fvg.PARAM_MIN_GAP_RULE: common.DECLARED_BOS_CLOSE_BUFFER})


@pytest.mark.parametrize("bad", [0, -1, True])
def test_invalid_zone_ttl_refuses(bad):
    with pytest.raises(StructureLawError):
        run([bar(0, 100, 90)], params={
            fvg.PARAM_MIN_GAP_RULE: common.DECLARED_BOS_CLOSE_BUFFER,
            fvg.PARAM_ZONE_TTL_BARS: bad})


def test_wrong_kind_and_non_object_payload_refuse():
    with pytest.raises(StructureLawError):
        run([{"event_id": "e1", "kind": "PIVOT", "payload": {}}])
    with pytest.raises(StructureLawError):
        run([{"event_id": "e1", "kind": "BAR", "payload": "not a dict"}])
