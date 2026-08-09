"""Typed level machines F03/F04/F06 — golden vectors, boundaries, mirror, invariance."""

from __future__ import annotations

import pytest

from triad_origin import transition
from triad_origin.structures import common
from triad_origin.structures import typed_level_registry as tlr

F03_PARAMS = {tlr.PARAM_DC_REVERSAL_RULE: common.DECLARED_DC_REVERSAL}
F04_PARAMS = {tlr.PARAM_FRACTAL_LEFT: 2, tlr.PARAM_FRACTAL_RIGHT: 2}

# TEST-ONLY ratified stand-in for RC3-PAR-STRUCT-001 (EQUAL_LEVEL_MAX_SPAN), which remains
# NOT_RATIFIED in the registry. Chosen at 4 so a span breach is actually exercisable while the
# PAR-009 inclusive law (span == max_span passes) still holds.
TEST_EQUAL_LEVEL_MAX_SPAN = 4

F06_PARAMS = {
    tlr.PARAM_EQUAL_LEVEL_TOLERANCE_RULE: common.DECLARED_EQUAL_LEVEL_TOLERANCE,
    tlr.PARAM_EQUAL_LEVEL_MIN_TOUCHES: 2,
    tlr.PARAM_EQUAL_LEVEL_MAX_SPAN: TEST_EQUAL_LEVEL_MAX_SPAN,
}


def bar(index, high, low, atr=None, seq=None, event_id=None):
    payload = {"high_ticks": high, "low_ticks": low}
    if atr is not None or seq is None:
        payload["atr14_ticks"] = atr
    if seq is not None:
        payload["bar_seq"] = seq
    return {"event_id": event_id or f"b{index}", "kind": "BAR", "payload": payload}


def pivot(index, level, kind=tlr.PIVOT_HIGH, atr=30):
    return {"event_id": f"p{index}", "kind": "PIVOT",
            "payload": {"pivot_kind": kind, "level_ticks": level, "atr14_ticks": atr}}


def mirror_envelope(envelope):
    payload = dict(envelope["payload"])
    if "high_ticks" in payload:
        high, low = payload["high_ticks"], payload["low_ticks"]
        payload["high_ticks"], payload["low_ticks"] = -low, -high
    if "level_ticks" in payload:
        payload["level_ticks"] = -payload["level_ticks"]
    if "pivot_kind" in payload:
        payload["pivot_kind"] = _MIRROR_KIND[payload["pivot_kind"]]
    return dict(envelope, payload=payload)


_MIRROR_KIND = {
    tlr.SWING_HIGH: tlr.SWING_LOW, tlr.SWING_LOW: tlr.SWING_HIGH,
    tlr.PIVOT_HIGH: tlr.PIVOT_LOW, tlr.PIVOT_LOW: tlr.PIVOT_HIGH,
    tlr.EQUAL_LEVEL_HIGH: tlr.EQUAL_LEVEL_LOW, tlr.EQUAL_LEVEL_LOW: tlr.EQUAL_LEVEL_HIGH,
}


def mirror_event(event):
    if event.get("event_kind") != tlr.TYPED_LEVEL:
        return dict(event)
    mirrored = dict(event)
    mirrored["kind"] = _MIRROR_KIND[event["kind"]]
    if "direction" in event:
        mirrored["direction"] = common.opposite(event["direction"])
    for key in ("level_ticks", "anchor_ticks"):
        if key in event:
            mirrored[key] = -event[key]
    if "member_levels" in event:
        mirrored["member_levels"] = [-level for level in event["member_levels"]]
    return mirrored


def typed_levels(result):
    return [event for event in result.events if event.get("event_kind") == tlr.TYPED_LEVEL]


def abstentions(result):
    return [event for event in result.events if event.get("event_kind") == "NAMED_ABSTENTION"]


# ---------------------------------------------------------------------------------------------
# F03 — DirectionalChangeSwing
# ---------------------------------------------------------------------------------------------

GV005_BARS = [
    bar(0, 1000, 998, atr=20),
    bar(1, 999, 996, atr=20),   # reversal difference 4 < 5: no confirmation (one-unit short)
    bar(2, 999, 995, atr=20),   # reversal difference 5 == delta 5: equality confirms
]


class TestDirectionalChangeSwing:
    def test_gv005_delta_five_reversal_four_fails_five_passes(self):
        result = transition.run(tlr.DirectionalChangeSwing(), GV005_BARS, F03_PARAMS)
        levels = typed_levels(result)
        assert levels == [{
            "event_kind": tlr.TYPED_LEVEL, "formula": "F03", "kind": tlr.SWING_HIGH,
            "direction": common.LONG, "level_ticks": 1000, "delta_ticks": 5,
            "origin_event_id": "b0", "confirmed_by_event_id": "b2",
        }]
        prefix = transition.run(tlr.DirectionalChangeSwing(), GV005_BARS[:2], F03_PARAMS)
        assert typed_levels(prefix) == []

    def test_leg_alternation_confirms_the_mirror_swing_next(self):
        bars = GV005_BARS + [bar(3, 1000, 996, atr=20)]  # 1000 - 995 == 5: down leg reverses
        result = transition.run(tlr.DirectionalChangeSwing(), bars, F03_PARAMS)
        levels = typed_levels(result)
        assert [event["kind"] for event in levels] == [tlr.SWING_HIGH, tlr.SWING_LOW]
        assert levels[1] == {
            "event_kind": tlr.TYPED_LEVEL, "formula": "F03", "kind": tlr.SWING_LOW,
            "direction": common.SHORT, "level_ticks": 995, "delta_ticks": 5,
            "origin_event_id": "b2", "confirmed_by_event_id": "b3",
        }

    def test_equal_extreme_does_not_refreeze_strictly_better_does(self):
        machine = tlr.DirectionalChangeSwing()
        bars = [
            bar(0, 1000, 998, atr=20),
            bar(1, 1000, 998, atr=40),  # equal extreme: no re-freeze, delta stays 5, origin b0
            bar(2, 1001, 999, atr=40),  # strictly better: re-freeze, delta 10, origin b2
        ]
        after_equal = transition.run(machine, bars[:2], F03_PARAMS).final_state
        assert after_equal["prov_high"] == {
            "extreme_ticks": 1000, "delta_ticks": 5, "origin_event_id": "b0"}
        after_better = transition.run(machine, bars, F03_PARAMS).final_state
        assert after_better["prov_high"] == {
            "extreme_ticks": 1001, "delta_ticks": 10, "origin_event_id": "b2"}
        tail = [bar(3, 1000, 992, atr=40), bar(4, 1000, 991, atr=40)]
        result = transition.run(machine, bars + tail, F03_PARAMS)
        levels = typed_levels(result)
        assert levels == [{
            "event_kind": tlr.TYPED_LEVEL, "formula": "F03", "kind": tlr.SWING_HIGH,
            "direction": common.LONG, "level_ticks": 1001, "delta_ticks": 10,
            "origin_event_id": "b2", "confirmed_by_event_id": "b4",
        }]

    def test_null_atr_is_a_named_abstention_with_zero_mutation(self):
        machine = tlr.DirectionalChangeSwing()
        result = transition.run(machine, [bar(0, 1000, 998, atr=None)], F03_PARAMS)
        assert result.final_state == machine.initial_state()
        (event,) = abstentions(result)
        assert event["reason_code"] == "F03_NO_ATR"
        assert event["formula"] == "F03"

    def test_mirror_law_exact_algebraic_symmetry(self):
        bars = GV005_BARS + [bar(3, 1000, 996, atr=20)]
        forward = transition.run(tlr.DirectionalChangeSwing(), bars, F03_PARAMS)
        mirrored = transition.run(
            tlr.DirectionalChangeSwing(), [mirror_envelope(env) for env in bars], F03_PARAMS)
        assert mirrored.events == [mirror_event(event) for event in forward.events]

    def test_prefix_restart_duplicate_invariance(self):
        bars = GV005_BARS + [bar(3, 1000, 996, atr=20)]
        machine = tlr.DirectionalChangeSwing()
        full = transition.run(machine, bars, F03_PARAMS)
        prefix = transition.run(machine, bars[:2], F03_PARAMS)
        resumed = transition.run(machine, bars[2:], F03_PARAMS, initial=prefix.final_state)
        assert prefix.events + resumed.events == full.events
        assert resumed.final_state == full.final_state
        duplicated = transition.run(machine, bars[:2] + [bars[1]] + bars[2:], F03_PARAMS)
        assert duplicated.duplicate_count == 1
        assert duplicated.events == full.events
        assert duplicated.final_state == full.final_state

    def test_machine_level_idempotency_for_repeated_event_id(self):
        machine = tlr.DirectionalChangeSwing()
        state = machine.initial_state()
        first = machine.transition(state, GV005_BARS[0], F03_PARAMS, {})
        again = machine.transition(first.state, GV005_BARS[0], F03_PARAMS, {})
        assert again.state == first.state
        assert again.events == ()

    def test_foreign_declared_rule_string_refuses(self):
        machine = tlr.DirectionalChangeSwing()
        params = {tlr.PARAM_DC_REVERSAL_RULE: common.DECLARED_EQUAL_LEVEL_TOLERANCE}
        with pytest.raises(common.StructureLawError):
            machine.transition(machine.initial_state(), GV005_BARS[0], params, {})

    def test_missing_rule_param_fails_closed(self):
        machine = tlr.DirectionalChangeSwing()
        with pytest.raises(transition.MissingParameterError):
            machine.transition(machine.initial_state(), GV005_BARS[0], {}, {})

    def test_ambiguous_seed_reversal_abstains_and_reseeds(self):
        machine = tlr.DirectionalChangeSwing()
        bars = [bar(0, 1000, 998, atr=20), bar(1, 1010, 990, atr=20)]
        result = transition.run(machine, bars, F03_PARAMS)
        assert typed_levels(result) == []
        (event,) = abstentions(result)
        assert event["reason_code"] == "F03_AMBIGUOUS_SEED_REVERSAL"
        assert result.final_state["mode"] == "SEED"
        assert result.final_state["prov_high"]["origin_event_id"] == "b1"


# ---------------------------------------------------------------------------------------------
# F04 — FractalPivot
# ---------------------------------------------------------------------------------------------


def f04_bars(highs, lows=None, start_seq=0):
    lows = lows or [high - 7 for high in highs]
    return [bar(index, high, low, seq=start_seq + index)
            for index, (high, low) in enumerate(zip(highs, lows))]


class TestFractalPivot:
    def test_gv006_pivot_high_publishes_on_the_fifth_bar(self):
        bars = f04_bars([8, 9, 12, 11, 10])
        result = transition.run(tlr.FractalPivot(), bars, F04_PARAMS)
        levels = typed_levels(result)
        assert levels == [{
            "event_kind": tlr.TYPED_LEVEL, "formula": "F04", "kind": tlr.PIVOT_HIGH,
            "level_ticks": 12, "origin_event_id": "b2", "origin_bar_seq": 2,
            "confirmed_by_event_id": "b4",
        }]
        early = transition.run(tlr.FractalPivot(), bars[:4], F04_PARAMS)
        assert typed_levels(early) == []  # never published before the second right bar

    def test_gv006_right_tie_rejects(self):
        bars = f04_bars([8, 9, 12, 11, 12])
        result = transition.run(tlr.FractalPivot(), bars, F04_PARAMS)
        assert typed_levels(result) == []

    def test_left_tie_rejects(self):
        bars = f04_bars([12, 9, 12, 11, 10])
        result = transition.run(tlr.FractalPivot(), bars, F04_PARAMS)
        assert typed_levels(result) == []

    def test_pivot_low_mirror_exact(self):
        bars = f04_bars([8, 9, 12, 11, 10])
        forward = transition.run(tlr.FractalPivot(), bars, F04_PARAMS)
        mirrored = transition.run(
            tlr.FractalPivot(), [mirror_envelope(env) for env in bars], F04_PARAMS)
        assert mirrored.events == [mirror_event(event) for event in forward.events]
        assert typed_levels(mirrored)[0]["kind"] == tlr.PIVOT_LOW
        assert typed_levels(mirrored)[0]["level_ticks"] == -12

    def test_gap_mid_window_resets_cleanly_and_yields_no_pivot(self):
        highs = [8, 9, 12, 11, 10, 9]
        seqs = [0, 1, 2, 3, 5, 6]  # gap between seq 3 and 5 breaks the closed window
        bars = [bar(index, high, high - 7, seq=seq)
                for index, (high, seq) in enumerate(zip(highs, seqs))]
        result = transition.run(tlr.FractalPivot(), bars, F04_PARAMS)
        assert typed_levels(result) == []
        assert [entry["bar_seq"] for entry in result.final_state["window"]] == [5, 6]

    def test_out_of_order_bar_seq_refuses(self):
        machine = tlr.FractalPivot()
        state = machine.transition(
            machine.initial_state(), bar(0, 8, 1, seq=3), F04_PARAMS, {}).state
        with pytest.raises(common.StructureLawError):
            machine.transition(state, bar(1, 9, 2, seq=3), F04_PARAMS, {})

    def test_prefix_restart_duplicate_invariance(self):
        bars = f04_bars([8, 9, 12, 11, 10, 9, 8])
        machine = tlr.FractalPivot()
        full = transition.run(machine, bars, F04_PARAMS)
        prefix = transition.run(machine, bars[:3], F04_PARAMS)
        resumed = transition.run(machine, bars[3:], F04_PARAMS, initial=prefix.final_state)
        assert prefix.events + resumed.events == full.events
        assert resumed.final_state == full.final_state
        duplicated = transition.run(machine, bars[:3] + [bars[2]] + bars[3:], F04_PARAMS)
        assert duplicated.duplicate_count == 1
        assert duplicated.events == full.events

    def test_missing_radius_params_fail_closed(self):
        machine = tlr.FractalPivot()
        with pytest.raises(transition.MissingParameterError):
            machine.transition(
                machine.initial_state(), bar(0, 8, 1, seq=0),
                {tlr.PARAM_FRACTAL_LEFT: 2}, {})


# ---------------------------------------------------------------------------------------------
# F06 — EqualLevelCluster
# ---------------------------------------------------------------------------------------------


class TestEqualLevelCluster:
    def test_gv007_second_touch_publishes_and_1004_starts_a_new_cluster(self):
        pivots = [pivot(0, 1000), pivot(1, 1003), pivot(2, 1004)]
        result = transition.run(tlr.EqualLevelCluster(), pivots, F06_PARAMS)
        levels = typed_levels(result)
        assert levels == [{
            "event_kind": tlr.TYPED_LEVEL, "formula": "F06", "kind": tlr.EQUAL_LEVEL_HIGH,
            "anchor_ticks": 1000, "member_levels": [1000, 1003],
            "member_event_ids": ["p0", "p1"], "confirmed_by_event_id": "p1",
        }]
        clusters = result.final_state["clusters"]
        assert [cluster["anchor_ticks"] for cluster in clusters] == [1000, 1004]
        assert clusters[1]["member_levels"] == [1004]  # tolerance 3: distance 4 does not join

    def test_span_law_inclusive_boundary_and_breach(self):
        # ATR 50 -> tolerance 5, so span is the only discriminator against max_span 4.
        pivots = [pivot(0, 1000, atr=50), pivot(1, 1003, atr=50),
                  pivot(2, 1004, atr=50), pivot(3, 1005, atr=50)]
        result = transition.run(tlr.EqualLevelCluster(), pivots, F06_PARAMS)
        clusters = result.final_state["clusters"]
        # 1004: span 4 == max_span 4 -> inclusive equality joins; 1005: span 5 > 4 -> refused.
        assert clusters[0]["member_levels"] == [1000, 1003, 1004]
        assert [cluster["anchor_ticks"] for cluster in clusters] == [1000, 1005]

    def test_anchor_never_drifts_no_transitive_chaining(self):
        # 1006 is within tolerance 5 of member 1003 but 6 from the immutable anchor: refused.
        pivots = [pivot(0, 1000, atr=50), pivot(1, 1003, atr=50), pivot(2, 1006, atr=50)]
        result = transition.run(tlr.EqualLevelCluster(), pivots, F06_PARAMS)
        clusters = result.final_state["clusters"]
        assert clusters[0]["anchor_ticks"] == 1000
        assert clusters[0]["member_levels"] == [1000, 1003]
        assert [cluster["anchor_ticks"] for cluster in clusters] == [1000, 1006]

    def test_not_ratified_max_span_is_named_abstention_with_zero_mutation(self):
        machine = tlr.EqualLevelCluster()
        params = dict(F06_PARAMS, equal_level_max_span=common.NOT_RATIFIED)
        result = transition.run(machine, [pivot(0, 1000), pivot(1, 1003)], params)
        assert result.final_state == machine.initial_state()
        assert typed_levels(result) == []
        reasons = [event["reason_code"] for event in abstentions(result)]
        assert reasons == ["F06_UNAVAILABLE_MAX_SPAN_NOT_RATIFIED"] * 2
        assert all(event["refs"]["parameter"] == "RC3-PAR-STRUCT-001"
                   for event in abstentions(result))

    def test_missing_max_span_param_fails_closed(self):
        machine = tlr.EqualLevelCluster()
        params = {key: value for key, value in F06_PARAMS.items()
                  if key != tlr.PARAM_EQUAL_LEVEL_MAX_SPAN}
        with pytest.raises(transition.MissingParameterError):
            machine.transition(machine.initial_state(), pivot(0, 1000), params, {})

    def test_unratified_non_int_max_span_refuses(self):
        machine = tlr.EqualLevelCluster()
        for bad in (True, -1, "5"):
            params = dict(F06_PARAMS, equal_level_max_span=bad)
            with pytest.raises(common.StructureLawError):
                machine.transition(machine.initial_state(), pivot(0, 1000), params, {})

    def test_foreign_tolerance_rule_string_refuses(self):
        machine = tlr.EqualLevelCluster()
        params = dict(F06_PARAMS, equal_level_tolerance_rule=common.DECLARED_DC_REVERSAL)
        with pytest.raises(common.StructureLawError):
            machine.transition(machine.initial_state(), pivot(0, 1000), params, {})

    def test_null_atr_pivot_abstains_without_mutation(self):
        machine = tlr.EqualLevelCluster()
        result = transition.run(machine, [pivot(0, 1000, atr=None)], F06_PARAMS)
        assert result.final_state == machine.initial_state()
        (event,) = abstentions(result)
        assert event["reason_code"] == "F06_NO_ATR"

    def test_cross_type_pivot_never_joins(self):
        pivots = [pivot(0, 1000, kind=tlr.PIVOT_HIGH), pivot(1, 1000, kind=tlr.PIVOT_LOW)]
        result = transition.run(tlr.EqualLevelCluster(), pivots, F06_PARAMS)
        assert typed_levels(result) == []
        kinds = [cluster["kind"] for cluster in result.final_state["clusters"]]
        assert kinds == [tlr.PIVOT_HIGH, tlr.PIVOT_LOW]

    def test_mirror_law_exact(self):
        pivots = [pivot(0, 1000), pivot(1, 1003), pivot(2, 1004)]
        forward = transition.run(tlr.EqualLevelCluster(), pivots, F06_PARAMS)
        mirrored = transition.run(
            tlr.EqualLevelCluster(), [mirror_envelope(env) for env in pivots], F06_PARAMS)
        assert mirrored.events == [mirror_event(event) for event in forward.events]

    def test_prefix_restart_duplicate_invariance(self):
        pivots = [pivot(0, 1000), pivot(1, 1003), pivot(2, 1004), pivot(3, 1005)]
        machine = tlr.EqualLevelCluster()
        full = transition.run(machine, pivots, F06_PARAMS)
        prefix = transition.run(machine, pivots[:2], F06_PARAMS)
        resumed = transition.run(machine, pivots[2:], F06_PARAMS, initial=prefix.final_state)
        assert prefix.events + resumed.events == full.events
        assert resumed.final_state == full.final_state
        duplicated = transition.run(machine, pivots[:2] + [pivots[1]] + pivots[2:], F06_PARAMS)
        assert duplicated.duplicate_count == 1
        assert duplicated.events == full.events

    def test_machine_level_idempotency_for_a_member_event_id(self):
        machine = tlr.EqualLevelCluster()
        state = machine.initial_state()
        state = machine.transition(state, pivot(0, 1000), F06_PARAMS, {}).state
        state = machine.transition(state, pivot(1, 1003), F06_PARAMS, {}).state
        replay = machine.transition(state, pivot(0, 1000), F06_PARAMS, {})
        assert replay.state == state
        assert replay.events == ()
