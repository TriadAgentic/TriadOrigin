"""F13 excursion/reclaim battery: GV-011, horizon boundary, mirror, invariance."""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import transition  # noqa: E402
from triad_origin.structures import common  # noqa: E402
from triad_origin.structures.common import StructureLawError  # noqa: E402
from triad_origin.structures.excursion_reclaim_registry import (  # noqa: E402
    CONFIRMED,
    EXCURSED,
    RECLAIM_EXPIRED,
    RECLAIM_PENDING,
    ExcursionReclaimTracker,
)

PARAMS = {
    "excursion_min_rule": common.DECLARED_BOS_CLOSE_BUFFER,
    "reclaim_close_buffer_rule": common.DECLARED_BOS_CLOSE_BUFFER,
    "reclaim_horizon": 3,
    "reclaim_hold_bars": 2,
}


def excursion(level_id, direction, level, high, low, atr=20, event_id=None):
    return {"event_id": event_id or f"exc_{level_id}", "kind": "EXCURSION_CANDIDATE",
            "payload": {"level_id": level_id, "direction": direction, "level_ticks": level,
                       "high_ticks": high, "low_ticks": low, "atr14_ticks": atr}}


def observation(level_id, ordinal, close, atr=20, event_id=None):
    return {"event_id": event_id or f"obs_{level_id}_{ordinal}", "kind": "RECLAIM_OBSERVATION",
            "payload": {"level_id": level_id, "ordinal": ordinal, "close_ticks": close,
                       "atr14_ticks": atr}}


def run(inputs, params=None, initial=None):
    return transition.run(ExcursionReclaimTracker(), inputs, params or PARAMS, initial=initial)


def states_of(row_id, result):
    return [e["to_state"] for e in result.events
            if e.get("event_kind") == "RECLAIM_STATE_CHANGED" and e["level_id"] == row_id]


class TestGv011:
    # ATR=20, buffer=max(1,ceil(20/20))=1. Under the RC2/GV-011 convention a LONG level excurses
    # on a LOW piercing below (low<=999) and reclaims on a close back ABOVE (close>=1001).
    def test_two_consecutive_qualifying_closes_confirm(self):
        inputs = [
            excursion("L1", common.LONG, 1000, high=1000, low=999),  # low 999 <= 999: excurses
            observation("L1", 1, close=1002),  # >= 1000+1: qualifies -> RECLAIM_PENDING
            observation("L1", 2, close=1003),  # second consecutive -> CONFIRMED
        ]
        result = run(inputs)
        assert states_of("L1", result) == [RECLAIM_PENDING, CONFIRMED]

    def test_nonqualifying_close_resets_hold_count(self):
        # horizon widened to 5 so the reset/re-qualify sequence stays inside the window and the
        # boundary is not what this test is measuring.
        params = dict(PARAMS, reclaim_horizon=5)
        inputs = [
            excursion("L1", common.LONG, 1000, high=1000, low=999),
            observation("L1", 1, close=1002),  # qualifies -> PENDING, hold=1
            observation("L1", 2, close=995),   # does not qualify -> reset to EXCURSED
            observation("L1", 3, close=1002),  # qualifies again, hold restarts at 1 -> PENDING
        ]
        result = run(inputs, params=params)
        assert states_of("L1", result) == [RECLAIM_PENDING, RECLAIM_PENDING]

    def test_ordinal_past_horizon_expires(self):
        inputs = [
            excursion("L1", common.LONG, 1000, high=1000, low=999),
            observation("L1", 1, close=1002),  # PENDING
            observation("L1", 4, close=1003),  # ordinal 4 >= horizon 3 -> EXPIRED (never confirms)
        ]
        result = run(inputs)
        assert states_of("L1", result) == [RECLAIM_PENDING, RECLAIM_EXPIRED]

    def test_ordinal_exactly_at_horizon_is_outside_and_expires(self):
        # GV-011 / FPB-0024 P0 boundary: RECLAIM_HORIZON=3, so ordinal 3 is OUTSIDE the half-open
        # window and can NEVER confirm — it expires. (The pre-fix code confirmed here off `>`.)
        inputs = [
            excursion("L1", common.LONG, 1000, high=1000, low=999),
            observation("L1", 2, close=1002),  # ordinal 2 (< horizon): qualifies -> PENDING
            observation("L1", 3, close=1003),  # ordinal 3 == horizon: OUTSIDE -> EXPIRED
        ]
        result = run(inputs)
        assert states_of("L1", result) == [RECLAIM_PENDING, RECLAIM_EXPIRED]

    def test_second_close_at_last_inside_ordinal_confirms(self):
        # The complement of the boundary: ordinals 1 and 2 (both < horizon 3) confirm; only
        # ordinal 3 falls outside. Together these two vectors pin the exact [0, horizon) edge.
        inputs = [
            excursion("L1", common.LONG, 1000, high=1000, low=999),
            observation("L1", 1, close=1002),  # PENDING
            observation("L1", 2, close=1003),  # ordinal 2 (< horizon 3): CONFIRMED
        ]
        result = run(inputs)
        assert states_of("L1", result) == [RECLAIM_PENDING, CONFIRMED]


class TestConsecutiveness:
    """The 'second CONSECUTIVE qualifying close' law is structural, not incidental."""

    def test_gapped_qualifying_closes_do_not_confirm(self):
        # horizon=5 so both ordinals are inside; ordinal 3 skips ordinal 2, so the two qualifying
        # closes are NOT consecutive and must not confirm — the second starts a fresh run of one.
        params = dict(PARAMS, reclaim_horizon=5)
        inputs = [
            excursion("L1", common.LONG, 1000, high=1000, low=999),
            observation("L1", 1, close=1002),  # PENDING, hold=1, last_ordinal=1
            observation("L1", 3, close=1003),  # gap (ordinal 2 unseen): fresh run -> PENDING
        ]
        result = run(inputs, params=params)
        assert states_of("L1", result) == [RECLAIM_PENDING, RECLAIM_PENDING]

    def test_duplicate_ordinal_is_refused_not_double_counted(self):
        params = dict(PARAMS, reclaim_horizon=5)
        inputs = [
            excursion("L1", common.LONG, 1000, high=1000, low=999),
            observation("L1", 1, close=1002, event_id="obs_a"),  # PENDING, hold=1
            observation("L1", 1, close=1003, event_id="obs_b"),  # same ordinal, distinct event
        ]
        result = run(inputs, params=params)
        assert states_of("L1", result) == [RECLAIM_PENDING]  # never CONFIRMED off a duplicate
        abstain = [e for e in result.events if e.get("event_kind") == "NAMED_ABSTENTION"]
        assert [e["reason_code"] for e in abstain] == ["F13_ORDINAL_NOT_INCREASING"]

    def test_regressing_ordinal_is_refused(self):
        params = dict(PARAMS, reclaim_horizon=5)
        inputs = [
            excursion("L1", common.LONG, 1000, high=1000, low=999),
            observation("L1", 2, close=1002),  # PENDING, hold=1, last_ordinal=2
            observation("L1", 1, close=1003),  # ordinal regresses -> refused
        ]
        result = run(inputs, params=params)
        assert states_of("L1", result) == [RECLAIM_PENDING]
        abstain = [e for e in result.events if e.get("event_kind") == "NAMED_ABSTENTION"]
        assert [e["reason_code"] for e in abstain] == ["F13_ORDINAL_NOT_INCREASING"]


class TestExcursionBoundary:
    def test_excursion_requires_exact_buffer(self):
        # ATR=20 -> min_excursion=1. LONG excurses on low<=999: low=1000 (== level) does not,
        # low=999 does (equality passes, PAR-009 inclusive).
        no_exc = run([excursion("L1", common.LONG, 1000, high=1000, low=1000)])
        assert no_exc.final_state == {"levels": {}}
        exc = run([excursion("L1", common.LONG, 1000, high=1000, low=999)])
        assert "L1" in exc.final_state["levels"]

    def test_reexcursion_of_already_excursed_level_ignored(self):
        inputs = [
            excursion("L1", common.LONG, 1000, high=1000, low=999),
            excursion("L1", common.LONG, 1000, high=1000, low=950, event_id="exc_L1_again"),
        ]
        result = run(inputs)
        assert result.final_state["levels"]["L1"]["reclaim_state"] == EXCURSED

    def test_observation_on_unexcursed_level_ignored(self):
        result = run([observation("ghost", 0, close=1)])
        assert result.final_state == {"levels": {}}
        assert list(result.events) == []

    def test_observation_after_terminal_state_ignored(self):
        inputs = [
            excursion("L1", common.LONG, 1000, high=1000, low=999),
            observation("L1", 1, close=1002),
            observation("L1", 2, close=1003),  # CONFIRMED
            observation("L1", 3, close=1004),  # post-terminal: ignored
        ]
        result = run(inputs)
        assert states_of("L1", result) == [RECLAIM_PENDING, CONFIRMED]
        assert result.final_state["levels"]["L1"]["reclaim_state"] == CONFIRMED

    def test_missing_atr_abstains_on_excursion_and_observation(self):
        exc = run([excursion("L1", common.LONG, 1000, high=1000, low=999, atr=None)])
        assert exc.events[0]["reason_code"] == "F13_NO_ATR"
        assert exc.final_state == {"levels": {}}
        setup = run([excursion("L1", common.LONG, 1000, high=1000, low=999)])
        obs = run([observation("L1", 1, close=1002, atr=None)], initial=setup.final_state)
        assert obs.events[0]["reason_code"] == "F13_NO_ATR"
        assert obs.final_state == setup.final_state


class TestFailClosed:
    def test_missing_param_fails_closed(self):
        with pytest.raises(transition.MissingParameterError):
            transition.run(ExcursionReclaimTracker(),
                           [excursion("L1", common.LONG, 1000, 1001, 999)], {})

    def test_undeclared_rule_string_refused(self):
        bad = dict(PARAMS, excursion_min_rule="max(1,ceil(ATR14_ticks*1/10))")
        with pytest.raises(StructureLawError, match="undeclared excursion_min rule"):
            transition.run(ExcursionReclaimTracker(),
                           [excursion("L1", common.LONG, 1000, 1001, 999)], bad)


class TestMirror:
    def test_long_short_full_reflection(self):
        # Full price reflection O'=-O, H'=-L, L'=-H, C'=-C, level'=-level, direction swapped.
        long_inputs = [
            excursion("L1", common.LONG, 1000, high=1000, low=999),   # low 999 <= 999
            observation("L1", 1, close=1002),
            observation("L1", 2, close=1003),
        ]
        short_inputs = [
            excursion("L1", common.SHORT, -1000, high=-999, low=-1000),  # high -999 >= -999
            observation("L1", 1, close=-1002),
            observation("L1", 2, close=-1003),
        ]
        long_result = run(long_inputs)
        short_result = run(short_inputs)
        assert states_of("L1", long_result) == states_of("L1", short_result) == \
            [RECLAIM_PENDING, CONFIRMED]


class TestInvariance:
    def test_prefix_and_restart_and_duplicate(self):
        full = [
            excursion("L1", common.LONG, 1000, high=1000, low=999),
            observation("L1", 1, close=1002),
            observation("L1", 2, close=1003),
        ]
        whole = run(full)
        prefix = run(full[:2])
        assert states_of("L1", prefix) == [RECLAIM_PENDING]
        resumed = run(full[2:], initial=prefix.final_state)
        assert resumed.final_state == whole.final_state
        dup = run(full + [full[-1]])
        assert dup.final_state == whole.final_state
