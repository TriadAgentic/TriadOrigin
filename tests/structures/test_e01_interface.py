"""E01 consume-only validators: accept/reject classes, UTC purity, authorship refusal."""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import e01_interface as e01  # noqa: E402


def good_bar(**overrides):
    payload = {
        "state_kind": "BAR",
        "bar_finalization_state": "FINALIZED",
        "watermark_complete": True,
        "validity": "READY",
        "bar_index": 7,
        "bar_open_time_us": 420_000_000,
        "bar_close_time_us": 480_000_000,
        "open_ticks": 1002,
        "high_ticks": 1010,
        "low_ticks": 1000,
        "close_ticks": 1005,
    }
    payload.update(overrides)
    return {"event_id": "bar_7", "payload": payload}


def good_session(**overrides):
    start = 20_000 * e01.DAY_US
    payload = {
        "state_kind": "SESSION_LEVEL",
        "calendar_id": "utc_daily.v1",
        "calendar_row": {
            "calendar_id": "utc_daily.v1",
            "utc_day_offset_us": 0,
            "session_length_us": e01.DAY_US,
        },
        "session_start_us": start,
        "session_end_us": start + e01.DAY_US,
        "final": False,
        "session_open_ticks": 105,
        "session_high_ticks": 110,
        "session_low_ticks": 100,
    }
    payload.update(overrides)
    return {"event_id": "sess_1", "payload": payload}


# --- finalized bar -------------------------------------------------------------------------------


def test_good_finalized_bar_is_accepted_with_normalized_fields():
    verdict = e01.validate_finalized_bar(good_bar())
    assert verdict["accepted"] is True and verdict["kind"] == "BAR"
    assert verdict["bar"] == {
        "bar_index": 7,
        "bar_open_time_us": 420_000_000,
        "bar_close_time_us": 480_000_000,
        "open_ticks": 1002,
        "high_ticks": 1010,
        "low_ticks": 1000,
        "close_ticks": 1005,
    }


def test_forming_bar_and_incomplete_watermark_and_non_ready_reject_not_finalized():
    for overrides in (
        {"bar_finalization_state": "FORMING"},
        {"watermark_complete": False},
        {"validity": "SYNCING"},
    ):
        verdict = e01.validate_finalized_bar(good_bar(**overrides))
        assert verdict["accepted"] is False
        assert verdict["event_kind"] == "QUARANTINE"
        assert verdict["reason_code"] == e01.E01_BAR_NOT_FINALIZED


def test_malformed_bars_reject_never_repair():
    cases = [
        {"state_kind": "BOOK"},
        {"watermark_complete": 1},
        {"open_ticks": 999},          # open below low
        {"close_ticks": 1011},        # close above high
        {"low_ticks": 1011},          # low above high
        {"high_ticks": 1010.0},       # float on the semantic path
        {"bar_index": -1},
        {"bar_close_time_us": 420_000_000},  # not after open time
        {"close_ticks": None},
    ]
    for overrides in cases:
        verdict = e01.validate_finalized_bar(good_bar(**overrides))
        assert verdict["accepted"] is False, overrides
        assert verdict["reason_code"] == e01.E01_BAR_MALFORMED, overrides
    assert e01.validate_finalized_bar(None)["reason_code"] == e01.E01_BAR_MALFORMED
    assert e01.validate_finalized_bar({"payload": []})["reason_code"] == e01.E01_BAR_MALFORMED


# --- session level -------------------------------------------------------------------------------


def test_good_provisional_and_final_sessions_are_accepted():
    provisional = e01.validate_session_level(good_session())
    assert provisional["accepted"] is True and provisional["session"]["final"] is False
    final = e01.validate_session_level(good_session(
        final=True, session_end_watermark_us=20_001 * e01.DAY_US))
    assert final["accepted"] is True and final["session"]["final"] is True


def test_offset_calendar_row_alignment_is_honored():
    start = 20_000 * e01.DAY_US + 3_600_000_000
    verdict = e01.validate_session_level(good_session(
        calendar_row={
            "calendar_id": "utc_daily.v1",
            "utc_day_offset_us": 3_600_000_000,
            "session_length_us": e01.DAY_US,
        },
        session_start_us=start,
        session_end_us=start + e01.DAY_US,
    ))
    assert verdict["accepted"] is True


def test_non_utc_aligned_session_rejects_calendar_mismatch():
    cases = [
        {"session_start_us": 20_000 * e01.DAY_US + 1,
         "session_end_us": 20_001 * e01.DAY_US + 1},
        {"session_end_us": 20_001 * e01.DAY_US - 5},  # length disagrees with the declared row
        {"calendar_id": "other.v1"},
    ]
    for overrides in cases:
        verdict = e01.validate_session_level(good_session(**overrides))
        assert verdict["accepted"] is False, overrides
        assert verdict["reason_code"] == e01.E01_SESSION_CALENDAR_MISMATCH, overrides


def test_final_flag_before_session_end_watermark_rejects():
    verdict = e01.validate_session_level(good_session(
        final=True, session_end_watermark_us=20_001 * e01.DAY_US - 1))
    assert verdict["reason_code"] == e01.E01_SESSION_FINAL_BEFORE_WATERMARK
    missing = e01.validate_session_level(good_session(final=True))
    assert missing["reason_code"] == e01.E01_SESSION_MALFORMED


def test_malformed_sessions_reject():
    cases = [
        {"state_kind": "BAR"},
        {"final": 1},
        {"session_start_us": 20_001 * e01.DAY_US, "session_end_us": 20_000 * e01.DAY_US},
        {"session_open_ticks": 99},  # open below low
        {"calendar_row": "utc_daily.v1"},
        {"session_high_ticks": 110.5},
    ]
    for overrides in cases:
        verdict = e01.validate_session_level(good_session(**overrides))
        assert verdict["accepted"] is False, overrides
        assert verdict["reason_code"] == e01.E01_SESSION_MALFORMED, overrides


def test_host_timezone_is_structurally_irrelevant(monkeypatch):
    baseline_bar = e01.validate_finalized_bar(good_bar())
    baseline_sess = e01.validate_session_level(good_session())
    for tz in ("UTC", "America/New_York", "Asia/Tokyo", "Pacific/Kiritimati"):
        monkeypatch.setenv("TZ", tz)
        assert e01.validate_finalized_bar(good_bar()) == baseline_bar
        assert e01.validate_session_level(good_session()) == baseline_sess


# --- authorship refusal --------------------------------------------------------------------------


def test_module_exposes_no_bar_or_session_constructor():
    public_callables = {
        name for name in dir(e01)
        if not name.startswith("_")
        and callable(getattr(e01, name))
        and getattr(getattr(e01, name), "__module__", None) == e01.__name__
    }
    # B02C (TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12 Part A §1.1 / Part C §C.3) added the
    # boundary validators + the ValidatedInput types + their typed quarantines. All remain
    # VALIDATORS of consumed facts — none authors a bar/session/trade/book from raw trades.
    assert public_callables == {
        "validate_finalized_bar", "validate_session_level", "rejection",
        "require_valid_bar", "validate_trade", "validate_book_update",
        "ValidatedBar", "ValidatedTrade", "ValidatedBookUpdate",
        "QuarantineInvalidBar", "QuarantineInvalidTrade", "QuarantineInvalidBookUpdate",
    }
    for name in public_callables:
        lowered = name.lower()
        assert not any(verb in lowered for verb in ("build", "aggregate", "make", "synthes"))
