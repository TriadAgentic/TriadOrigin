"""F11 qualified-displacement battery: GV-010, boundary equality, gap/exhaustion abstention,
missing-ATR abstention, LONG/SHORT mirror, invariance, and the exact-rational-never-float proof."""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import transition  # noqa: E402
from triad_origin.structures import common, displacement  # noqa: E402
from triad_origin.structures.common import StructureLawError  # noqa: E402
from triad_origin.structures.displacement import DISPLACEMENT_QUALIFIED, QualifiedDisplacement

PARAMS = {
    "displacement_horizon": 3,
    "displacement_min_move_rule": common.DECLARED_DISPLACEMENT_MIN_MOVE,
    "body_fraction_rule": common.DECLARED_DISPLACEMENT_BODY_FRACTION,
    "close_location_rule": common.DECLARED_DISPLACEMENT_CLOSE_LOCATION,
}


def origin(event_id, index, open_ticks, atr=10):
    return {
        "event_id": event_id,
        "kind": "ORIGIN",
        "payload": {"origin_bar_index": index, "origin_open_ticks": open_ticks,
                    "atr14_before_origin_ticks": atr},
    }


def bar(event_id, index, open_ticks, close_ticks, high_ticks, low_ticks):
    return {
        "event_id": event_id,
        "kind": "BAR",
        "payload": {"bar_index": index, "open_ticks": open_ticks, "close_ticks": close_ticks,
                    "high_ticks": high_ticks, "low_ticks": low_ticks},
    }


def run(inputs, params=None, horizon=3, initial=None):
    p = dict(params or PARAMS)
    p["displacement_horizon"] = horizon
    return transition.run(QualifiedDisplacement(), inputs, p, initial=initial)


def qualified(events):
    return [e for e in events if e.get("event_kind") == DISPLACEMENT_QUALIFIED]


def abstentions(events):
    return [e for e in events if e.get("event_kind") == "NAMED_ABSTENTION"]


# --- GV-010: D_ticks = max(5, ceil(3*10/2)) = 15; move 14 fails, move 15 passes -----------------


def test_gv010_min_move_evaluates_to_fifteen_for_atr_ten():
    assert common.evaluate_displacement_min_move(10) == 15


def test_gv010_move_fourteen_fails_move_fifteen_passes_with_all_other_conjuncts_held():
    # A full-range bull marubozu (open=0, close=move, high=move, low=0) trivially satisfies the
    # candle, body-ratio and close-location conjuncts at every move value tried here — isolating
    # the move-threshold conjunct exactly, per GV-010.
    fails = run([origin("o", 100, 0, atr=10),
                 bar("b1", 101, 0, 14, 14, 0)], horizon=1)
    assert qualified(fails.events) == []
    (event,) = abstentions(fails.events)
    assert event["reason_code"] == "F11_NO_QUALIFYING_BAR"

    passes = run([origin("o", 100, 0, atr=10),
                  bar("b1", 101, 0, 15, 15, 0)], horizon=1)
    (event,) = qualified(passes.events)
    assert event["direction"] == common.LONG
    assert event["move_ticks"] == 15
    assert event["d_ticks"] == 15
    assert event["origin_bar_index"] == 100
    assert event["qualifying_bar_index"] == 101
    assert event["confirmed_by_event_id"] == "b1"
    assert event["origin_event_id"] == "o"


# --- body-ratio (PAR-046, 13/20) equality boundary ------------------------------------------------


def test_body_ratio_equality_passes_and_one_unit_under_fails():
    # range = 15, |C-O| chosen so the ratio sits exactly on 13/20 vs one tick short of it.
    # 15 * 13/20 = 9.75, so an integer boundary needs a scaled range: use range = 20 exactly.
    # H=20, L=0, C-L must clear the close-location floor (>=4/5*20=16), so C=17 (>=16, passes).
    # body numerator |C-O|: choose O so |C-O| = 13 exactly (equality) or 12 (one under).
    at_threshold = run(
        [origin("o", 0, -1000, atr=1), bar("b1", 1, 4, 17, 20, 0)], horizon=1)
    (event,) = qualified(at_threshold.events)
    assert event["body_ratio_numerator"] == 13
    assert event["body_ratio_denominator"] == 20

    one_under = run(
        [origin("o", 0, -1000, atr=1), bar("b1", 1, 5, 17, 20, 0)], horizon=1)
    assert qualified(one_under.events) == []
    (event,) = abstentions(one_under.events)
    assert event["reason_code"] == "F11_NO_QUALIFYING_BAR"


# --- close-location (PAR-159, 4/5) equality boundary ----------------------------------------------


def test_close_location_equality_passes_and_one_unit_under_fails():
    # range = 20, close-location numerator (C-L) must clear >=16 (4/5 * 20); body ratio held
    # comfortably satisfied via a large |C-O| (open far below close), move held trivially large.
    at_threshold = run(
        [origin("o", 0, -1000, atr=1), bar("b1", 1, -100, 16, 20, 0)], horizon=1)
    (event,) = qualified(at_threshold.events)
    assert event["close_loc_numerator"] == 16
    assert event["close_loc_denominator"] == 20

    one_under = run(
        [origin("o", 0, -1000, atr=1), bar("b1", 1, -100, 15, 20, 0)], horizon=1)
    assert qualified(one_under.events) == []
    (event,) = abstentions(one_under.events)
    assert event["reason_code"] == "F11_NO_QUALIFYING_BAR"


# --- exact-rational-never-float proof: a naive float division misrounds at this magnitude --------


def test_body_ratio_boundary_holds_exactly_at_magnitudes_where_float_division_misrounds():
    scale = 10 ** 16
    range_ticks = 20 * scale
    # C - L = 4/5 * range exactly, so close-location passes comfortably and only the body-ratio
    # conjunct is in question.
    close = 16 * scale
    low = 0
    high = low + range_ticks
    at_exact_threshold_open = close - 13 * scale          # |C-O| == 13*scale (equality passes)
    one_under_open = close - (13 * scale - 1)             # |C-O| == 13*scale - 1 (fails)

    # The adversarial proof: float(13*scale - 1) / float(20*scale) misrounds to exactly 0.65,
    # which a naive `ratio >= 0.65` comparison would wrongly accept. A correct implementation
    # (exact-integer cross-multiplication) must still refuse it.
    misrounded = (13 * scale - 1) / (20 * scale)
    assert misrounded == 0.65
    assert misrounded >= 0.65  # the float trap this test exists to catch

    passes = run(
        [origin("o", 0, -10 * scale, atr=1),
         bar("b1", 1, at_exact_threshold_open, close, high, low)], horizon=1)
    (event,) = qualified(passes.events)
    assert event["body_ratio_numerator"] == 13 * scale
    assert event["body_ratio_denominator"] == 20 * scale

    fails = run(
        [origin("o", 0, -10 * scale, atr=1),
         bar("b1", 1, one_under_open, close, high, low)], horizon=1)
    assert qualified(fails.events) == []
    (event,) = abstentions(fails.events)
    assert event["reason_code"] == "F11_NO_QUALIFYING_BAR"


def test_no_division_operator_is_used_on_tick_values_in_this_module():
    import ast
    import inspect

    # ceil_div/evaluate_displacement_min_move/etc. live in common.py; the AST proof (not a text
    # grep, which would also flag "13/20" inside docstrings/comments) is that this module's own
    # code contains no true-division or floor-division operator at all — every ratio comparison
    # here is cross-multiplication.
    tree = ast.parse(inspect.getsource(displacement))
    for node in ast.walk(tree):
        assert not isinstance(node, ast.BinOp) or not isinstance(
            node.op, (ast.Div, ast.FloorDiv))


# --- earliest qualifier wins ------------------------------------------------------------------


def test_earliest_qualifying_bar_wins_and_the_search_stops():
    inputs = [
        origin("o", 100, 0, atr=10),
        bar("b1", 101, 0, 5, 5, 0),      # move=5 < D=15: fails, does not qualify
        bar("b2", 102, 0, 20, 20, 0),    # move=20 >= 15, full-range: qualifies
        bar("b3", 103, 0, 999, 999, 0),  # never evaluated: search already closed
    ]
    result = run(inputs)
    events = qualified(result.events)
    assert len(events) == 1
    assert events[0]["qualifying_bar_index"] == 102
    assert events[0]["move_ticks"] == 20
    assert abstentions(result.events) == []


# --- no qualifier in the whole window -----------------------------------------------------------


def test_no_qualifying_bar_in_the_window_yields_exactly_one_abstention():
    inputs = [
        origin("o", 100, 0, atr=10),
        bar("b1", 101, 0, 5, 5, 0),
        bar("b2", 102, 0, 3, 3, 0),
        bar("b3", 103, 0, 1, 1, 0),
    ]
    result = run(inputs)
    assert qualified(result.events) == []
    (event,) = abstentions(result.events)
    assert event["reason_code"] == "F11_NO_QUALIFYING_BAR"
    assert event["formula"] == "F11"
    assert event["refs"]["origin_bar_index"] == 100
    assert event["refs"]["horizon"] == 3


# --- gap in the search window --------------------------------------------------------------------


def test_gap_in_search_window_is_a_named_abstention_and_never_searches_across_it():
    inputs = [
        origin("o", 100, 0, atr=10),
        bar("b1", 101, 0, 5, 5, 0),       # non-qualifying, examined=1
        bar("b2", 103, 0, 999, 999, 0),   # skips 102: gap, would otherwise qualify
    ]
    result = run(inputs)
    assert qualified(result.events) == []
    (event,) = abstentions(result.events)
    assert event["reason_code"] == "F11_GAP_IN_SEARCH_WINDOW"
    assert event["refs"]["expected_bar_index"] == 102
    assert event["refs"]["got_bar_index"] == 103


def test_bar_after_a_gap_abstention_is_a_harmless_no_op():
    inputs = [
        origin("o", 100, 0, atr=10),
        bar("b1", 101, 0, 5, 5, 0),
        bar("b2", 103, 0, 999, 999, 0),   # gap: closes the search
    ]
    result = run(inputs)
    assert result.final_state["search"] is None
    stray = run([bar("b3", 104, 0, 999, 999, 0)], initial=result.final_state)
    assert stray.events == []
    assert stray.final_state["search"] is None


def test_backward_bar_index_is_a_structural_ordering_violation():
    with pytest.raises(StructureLawError):
        run([origin("o", 100, 0, atr=10),
             bar("b1", 101, 0, 5, 5, 0),
             bar("b2", 101, 0, 5, 5, 0)])


# --- no active search: BAR-before-ORIGIN is a no-op -----------------------------------------------


def test_bar_before_any_origin_is_a_harmless_no_op():
    result = run([bar("b1", 1, 0, 20, 20, 0)])
    assert result.events == []
    assert result.final_state["search"] is None


# --- missing ATR abstains and never opens a search  --


def test_missing_atr_before_origin_is_a_named_abstention_and_opens_no_search():
    result = run([origin("o", 100, 0, atr=None),
                  bar("b1", 101, 0, 20, 20, 0)])
    assert qualified(result.events) == []
    (event,) = abstentions(result.events)
    assert event["reason_code"] == "F11_NO_ATR"
    assert event["formula"] == "F11"
    assert result.final_state["search"] is None


# --- a later ORIGIN always supersedes a still-open search -----------------------------------------


def test_a_new_origin_always_supersedes_a_still_open_search():
    result = run([
        origin("o1", 100, 0, atr=10),
        bar("b1", 101, 0, 5, 5, 0),          # non-qualifying, examined=1 for origin 100
        origin("o2", 200, 0, atr=10),        # supersedes: fresh window from origin 200
        bar("b2", 201, 0, 20, 20, 0),        # qualifies against the new origin
    ])
    (event,) = qualified(result.events)
    assert event["origin_bar_index"] == 200
    assert event["qualifying_bar_index"] == 201
    assert abstentions(result.events) == []


# --- only the declared rules and a positive horizon are admitted ----------------------------------


def test_only_the_declared_rules_and_a_positive_horizon_are_admitted():
    bad_min_move = dict(PARAMS, displacement_min_move_rule="max(5,ceil(ATR14_ticks*1/4))")
    with pytest.raises(StructureLawError):
        run([origin("o", 100, 0, atr=10)], params=bad_min_move)
    bad_body = dict(PARAMS, body_fraction_rule="1/2")
    with pytest.raises(StructureLawError):
        run([origin("o", 100, 0, atr=10)], params=bad_body)
    bad_close_loc = dict(PARAMS, close_location_rule="1/2")
    with pytest.raises(StructureLawError):
        run([origin("o", 100, 0, atr=10)], params=bad_close_loc)
    with pytest.raises(StructureLawError):
        run([origin("o", 100, 0, atr=10)], horizon=0)
    with pytest.raises(transition.MissingParameterError):
        run([origin("o", 100, 0, atr=10)],
            params={"displacement_horizon": 3,
                     "displacement_min_move_rule": common.DECLARED_DISPLACEMENT_MIN_MOVE,
                     "body_fraction_rule": common.DECLARED_DISPLACEMENT_BODY_FRACTION})


# --- LONG/SHORT mirror law: full price reflection  --


def test_long_short_mirror_is_exact_algebraic_symmetry():
    straight = [
        origin("o", 100, 0, atr=10),
        bar("b1", 101, 0, 5, 5, 0),       # non-qualifying filler
        bar("b2", 102, 0, 20, 20, 0),     # qualifies LONG
    ]

    def reflect(env):
        payload = dict(env["payload"])
        if env["kind"] == "ORIGIN":
            payload["origin_open_ticks"] = -payload["origin_open_ticks"]
        else:
            open_ticks, close_ticks = payload["open_ticks"], payload["close_ticks"]
            high_ticks, low_ticks = payload["high_ticks"], payload["low_ticks"]
            payload["open_ticks"] = -open_ticks
            payload["close_ticks"] = -close_ticks
            payload["high_ticks"] = -low_ticks
            payload["low_ticks"] = -high_ticks
        return {"event_id": env["event_id"], "kind": env["kind"], "payload": payload}

    mirrored = [reflect(env) for env in straight]
    straight_result = qualified(run(straight).events)
    mirrored_result = qualified(run(mirrored).events)
    assert len(straight_result) == len(mirrored_result) == 1
    s, m = straight_result[0], mirrored_result[0]
    assert s["direction"] == common.LONG
    assert m["direction"] == common.SHORT
    assert m["move_ticks"] == -s["move_ticks"]
    assert m["d_ticks"] == s["d_ticks"]
    assert m["qualifying_bar_index"] == s["qualifying_bar_index"]
    assert m["origin_bar_index"] == s["origin_bar_index"]
    assert m["body_ratio_numerator"] == s["body_ratio_numerator"]
    assert m["body_ratio_denominator"] == s["body_ratio_denominator"]
    assert m["close_loc_numerator"] == s["close_loc_numerator"]
    assert m["close_loc_denominator"] == s["close_loc_denominator"]


def test_bear_close_location_mirror_boundary_is_exact():
    # Bear mirror of the close-location boundary test above: (H-C)*5 >= range*4.
    at_threshold = run(
        [origin("o", 0, 1000, atr=1), bar("b1", 1, 100, 4, 20, 0)], horizon=1)
    (event,) = qualified(at_threshold.events)
    assert event["direction"] == common.SHORT
    assert event["close_loc_numerator"] == 16  # H - C = 20 - 4
    assert event["close_loc_denominator"] == 20

    one_under = run(
        [origin("o", 0, 1000, atr=1), bar("b1", 1, 100, 5, 20, 0)], horizon=1)
    assert qualified(one_under.events) == []
    (event,) = abstentions(one_under.events)
    assert event["reason_code"] == "F11_NO_QUALIFYING_BAR"


# --- prefix / restart / duplicate invariance  --


def test_prefix_and_restart_invariance_across_every_cut_point():
    inputs = [
        origin("o", 100, 0, atr=10),
        bar("b1", 101, 0, 5, 5, 0),
        bar("b2", 102, 0, 20, 20, 0),
    ]
    full = run(inputs)
    for cut in range(1, len(inputs)):
        head = run(inputs[:cut])
        tail = run(inputs[cut:], initial=head.final_state)
        assert head.events + tail.events == full.events
        assert tail.final_state == full.final_state


def test_prefix_and_restart_invariance_on_a_no_qualifying_bar_abstention():
    inputs = [
        origin("o", 100, 0, atr=10),
        bar("b1", 101, 0, 5, 5, 0),
        bar("b2", 102, 0, 3, 3, 0),
        bar("b3", 103, 0, 1, 1, 0),
    ]
    full = run(inputs)
    for cut in range(1, len(inputs)):
        head = run(inputs[:cut])
        tail = run(inputs[cut:], initial=head.final_state)
        assert head.events + tail.events == full.events
        assert tail.final_state == full.final_state


def test_exact_duplicate_envelope_is_deduped_by_the_driver():
    repeated = bar("b1", 101, 0, 5, 5, 0)
    result = run([origin("o", 100, 0, atr=10), repeated, repeated])
    assert result.duplicate_count == 1


def test_restart_after_qualification_never_double_emits():
    inputs = [origin("o", 100, 0, atr=10), bar("b1", 101, 0, 20, 20, 0)]
    head = run(inputs)
    assert len(qualified(head.events)) == 1
    tail = run([bar("b2", 102, 0, 20, 20, 0)], initial=head.final_state)
    assert tail.events == []


def test_bar_close_above_high_is_refused():
    # F11 close-in-range validity: a finalized bar whose close exceeds high is invalid market data
    # and must be refused, never allowed to over-satisfy the close-location conjunct.
    with pytest.raises(StructureLawError, match="close_ticks outside"):
        run([origin("o", 0, 1000, atr=1), bar("b1", 1, 10, 25, 20, 0)], horizon=1)


def test_bar_close_below_low_is_refused():
    with pytest.raises(StructureLawError, match="close_ticks outside"):
        run([origin("o", 0, 1000, atr=1), bar("b1", 1, 10, -5, 20, 0)], horizon=1)
