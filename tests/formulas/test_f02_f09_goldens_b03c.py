"""B03C milestone golden home — the F02..F09 family registry vectors.

This file is the B03C acceptance profile's REQUIRED ARTIFACT
(``docs/control/closure/closure_semantics.v1.json`` →
``tests/formulas/test_f02_f09_goldens_b03c.py``). It executes:

* **GV-004 (F02):** ATR = 8 on a flat true-range-8 tape (the pre-existing linked golden,
  re-walked at the milestone home).
* **GV-F05-01 (F05, Part D §D.5):** N = 3, highs ``[10, 12, 11]`` → ``upper_t = 12``;
  lows ``[9, 9, 10]`` → ``lower_t = 9`` (equal lows: the extreme VALUE is the value).
  Current bar t excluded by construction (its high 15 must not change ``upper_t``).
  Warm-up with only 2 prior bars → NULL. Gap in window → NULL.
* **GV-003 (F01, Part D §D.2) — the Origin consume-half.** The watermark arithmetic
  (bucket ``[12:00:00, 12:01:00)``, ``allowed_lateness = 2s`` PAR-025, FINALIZED when source
  watermark ≥ ``12:01:02``) is E01-OWNED (CLAUDE.md reconciled law: ORIGIN consumes/validates,
  never authors bar finalization). Origin's executable half is the boundary law: only a
  FINALIZED + watermark-complete + READY bar is consumable; a late-data revision APPENDS
  ``data_revision r+1`` as a new event and the original availability is never rewritten —
  in Origin terms, same-index-different-bytes is a revision CONFLICT (poison), never a rewrite.

The deep F03/F04 batteries live in ``tests/structures/test_swing_dc_v2.py`` /
``test_typed_level_registry.py``; the F09 v2 battery lands with R-F09 in this same milestone.
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import features, transition  # noqa: E402
from triad_origin.e01_interface import (  # noqa: E402
    E01_BAR_NOT_FINALIZED,
    validate_finalized_bar,
)


def bar(index, o, h, l, c, event_id=None):
    return {
        "event_id": event_id or f"bar_{index}",
        "payload": {
            "state_kind": "BAR",
            "bar_finalization_state": "FINALIZED",
            "watermark_complete": True,
            "validity": "READY",
            "bar_index": index,
            "bar_open_time_us": index * 60_000_000,
            "bar_close_time_us": (index + 1) * 60_000_000,
            "open_ticks": o,
            "high_ticks": h,
            "low_ticks": l,
            "close_ticks": c,
        },
    }


def run_ext(inputs, window):
    return transition.run(features.RollingExtreme(), inputs, {"window": window})


class TestGV004AtrEqualsEight:
    def test_flat_tr8_tape_yields_atr_8(self) -> None:
        inputs = [bar(i, 1000, 1008, 1000, 1000) for i in range(15)]
        result = transition.run(features.AtrCalculator(), inputs, {"atr_period": 14})
        feature = result.events[-1]
        assert feature["event_kind"] == "FEATURE"
        assert feature["atr_ticks"] == 8


class TestGVF0501RollingExtreme:
    def test_direct_golden_upper_12_lower_9_current_bar_excluded(self) -> None:
        inputs = [
            bar(0, 10, 10, 9, 9),    # high 10, low 9
            bar(1, 10, 12, 9, 11),   # high 12, low 9  (equal lows with bar 0)
            bar(2, 10, 11, 10, 10),  # high 11, low 10
            bar(3, 12, 15, 12, 14),  # current bar t — its high 15 must not appear
        ]
        result = run_ext(inputs, window=3)
        feature = result.events[3]
        assert feature["event_kind"] == "FEATURE"
        assert feature["upper_ticks"] == 12
        assert feature["lower_ticks"] == 9  # equal lows: the extreme value is the value
        assert feature["dependency_range"] == {"first_bar_index": 0, "last_bar_index": 2}

    def test_warmup_two_prior_bars_is_null(self) -> None:
        inputs = [bar(0, 10, 10, 9, 9), bar(1, 10, 12, 9, 11), bar(2, 10, 11, 10, 10)]
        result = run_ext(inputs, window=3)
        assert result.events[2]["event_kind"] == "NAMED_ABSTENTION"
        assert result.events[2]["reason_code"] == "F05_WARMUP"

    def test_gap_in_window_is_null(self) -> None:
        inputs = [
            bar(0, 10, 10, 9, 9),
            bar(1, 10, 12, 9, 11),
            bar(3, 10, 11, 10, 10),  # bar 2 missing — gap
            bar(4, 12, 15, 12, 14),
        ]
        result = run_ext(inputs, window=3)
        assert all(e["event_kind"] != "FEATURE" for e in result.events)


class TestGV003OriginConsumeHalf:
    def test_finalized_watermark_complete_ready_bar_is_consumable(self) -> None:
        verdict = validate_finalized_bar(bar(0, 10, 12, 9, 11))
        assert verdict["accepted"] is True
        assert verdict["bar"]["bar_index"] == 0

    def test_pre_watermark_bar_is_not_available_no_formula_evaluation(self) -> None:
        # E01 finalizes at watermark >= bucket_end + allowed_lateness; before that the bar
        # arrives non-FINALIZED and Origin must not evaluate any formula over it.
        env = bar(0, 10, 12, 9, 11)
        env["payload"]["bar_finalization_state"] = "FORMING"
        verdict = validate_finalized_bar(env)
        assert verdict["accepted"] is False
        assert verdict["event_kind"] == "QUARANTINE"
        assert verdict["reason_code"] == E01_BAR_NOT_FINALIZED

    def test_incomplete_watermark_is_not_available(self) -> None:
        env = bar(0, 10, 12, 9, 11)
        env["payload"]["watermark_complete"] = False
        verdict = validate_finalized_bar(env)
        assert verdict["accepted"] is False
        assert verdict["event_kind"] == "QUARANTINE"
        assert verdict["reason_code"] == E01_BAR_NOT_FINALIZED

    def test_late_data_revision_appends_never_rewrites(self) -> None:
        # GV-003's revision law at the Origin boundary: a late trade re-emits the bar as a NEW
        # revision event; the ORIGINAL bytes are never rewritten. Same-index-different-bytes
        # without that revision identity is therefore a CONFLICT that poisons the consumer —
        # the one behavior that would exist iff an original had been rewritten in place.
        original = bar(5, 10, 12, 9, 11, event_id="bar_5_r0")
        rewritten = bar(5, 10, 12, 9, 10, event_id="bar_5_r1")  # same index, different bytes
        result = transition.run(
            features.RollingExtreme(), [original, rewritten], {"window": 3})
        conflict = result.events[-1]
        assert conflict["event_kind"] == "QUARANTINE"
        assert conflict["reason_code"] == "E01_BAR_REVISION_CONFLICT"
