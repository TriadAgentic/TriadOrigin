"""E01 interface validators (B02 gap): ORIGIN consumes F01 bars and F07 session levels.

F01 finalized bars and F07 UTC session levels are **E01-owned** facts (reconciled plan law).
ORIGIN validates the consumed event shape and refuses everything else with a quarantine-shaped
rejection dict; it NEVER repairs a bar, synthesizes a bar, or authors a session level — this
module deliberately exposes no constructor that could build either fact from trades.

Consumed BAR event (market_state.v2-shaped; the exact payload fields ORIGIN reads):

* ``payload.state_kind == "BAR"``
* ``payload.bar_finalization_state == "FINALIZED"`` (forming/corrected bars refuse)
* ``payload.watermark_complete is True`` (the exact bool — an int ``1`` is malformed)
* ``payload.validity == "READY"``
* ``payload.bar_index`` — exact int >= 0 (monotonicity across bars is the consumer's law)
* ``payload.bar_open_time_us`` / ``payload.bar_close_time_us`` — exact ints, open < close
* ``payload.open_ticks/high_ticks/low_ticks/close_ticks`` — exact ints with
  ``low <= open <= high`` and ``low <= close <= high`` (hence ``low <= high``)

Consumed SESSION_LEVEL event (F07; the exact payload fields ORIGIN reads):

* ``payload.state_kind == "SESSION_LEVEL"``
* ``payload.calendar_id`` — non-empty str, equal to ``payload.calendar_row.calendar_id``
* ``payload.calendar_row`` — the declared calendar row:
  ``{calendar_id, utc_day_offset_us in [0, DAY_US), session_length_us in (0, DAY_US]}``
* ``payload.session_start_us`` / ``payload.session_end_us`` — exact ints defining the declared
  UTC interval ``[start, end)`` with ``end - start == session_length_us`` and
  ``(start - utc_day_offset_us) % DAY_US == 0`` (UTC-day alignment per the declared row)
* ``payload.final`` — exact bool; ``True`` is lawful only with
  ``payload.session_end_watermark_us >= session_end_us``
* ``payload.session_open_ticks/session_high_ticks/session_low_ticks`` — exact ints with
  ``low <= open <= high``

Host timezone is structurally irrelevant: every check is a pure function of the event's integer
fields — nothing here reads a clock, an environment variable, or any calendar library.
"""

from __future__ import annotations

from .structures.common import StructureLawError, require_int

DAY_US = 86_400_000_000

E01_BAR_MALFORMED = "E01_BAR_MALFORMED"
E01_BAR_NOT_FINALIZED = "E01_BAR_NOT_FINALIZED"
E01_BAR_REVISION_CONFLICT = "E01_BAR_REVISION_CONFLICT"
E01_BAR_OUT_OF_ORDER = "E01_BAR_OUT_OF_ORDER"
E01_SESSION_MALFORMED = "E01_SESSION_MALFORMED"
E01_SESSION_CALENDAR_MISMATCH = "E01_SESSION_CALENDAR_MISMATCH"
E01_SESSION_FINAL_BEFORE_WATERMARK = "E01_SESSION_FINAL_BEFORE_WATERMARK"

_BAR_TICK_FIELDS = ("open_ticks", "high_ticks", "low_ticks", "close_ticks")


def rejection(reason_code: str, *, formula: str, detail: str) -> dict:
    """A quarantine-shaped rejection: reason-coded raw refusal, never a repaired fact."""
    return {
        "event_kind": "QUARANTINE",
        "accepted": False,
        "reason_code": reason_code,
        "formula": formula,
        "detail": detail,
    }


def _payload_of(event: object) -> dict | None:
    if not isinstance(event, dict):
        return None
    payload = event.get("payload")
    if not isinstance(payload, dict):
        return None
    return payload


def validate_finalized_bar(event: object) -> dict:
    """Accept an E01 F01 finalized-bar event or return a quarantine-shaped rejection.

    On acceptance returns ``{"accepted": True, "kind": "BAR", "bar": {...}}`` where ``bar``
    carries exactly the normalized fields ORIGIN consumes. Never repairs, never synthesizes.
    """
    payload = _payload_of(event)
    if payload is None:
        return rejection(E01_BAR_MALFORMED, formula="F01", detail="event/payload is not an object")
    if payload.get("state_kind") != "BAR":
        return rejection(
            E01_BAR_MALFORMED, formula="F01",
            detail=f"state_kind must be 'BAR', got {payload.get('state_kind')!r}")
    if payload.get("bar_finalization_state") != "FINALIZED":
        return rejection(
            E01_BAR_NOT_FINALIZED, formula="F01",
            detail=f"bar_finalization_state={payload.get('bar_finalization_state')!r}")
    watermark = payload.get("watermark_complete")
    if not isinstance(watermark, bool):
        return rejection(
            E01_BAR_MALFORMED, formula="F01", detail="watermark_complete must be an exact bool")
    if watermark is not True:
        return rejection(
            E01_BAR_NOT_FINALIZED, formula="F01", detail="watermark_complete is False")
    if payload.get("validity") != "READY":
        return rejection(
            E01_BAR_NOT_FINALIZED, formula="F01",
            detail=f"validity={payload.get('validity')!r} is not READY")
    try:
        bar_index = require_int(payload.get("bar_index"), "bar_index")
        open_time = require_int(payload.get("bar_open_time_us"), "bar_open_time_us")
        close_time = require_int(payload.get("bar_close_time_us"), "bar_close_time_us")
        ticks = {name: require_int(payload.get(name), name) for name in _BAR_TICK_FIELDS}
    except StructureLawError as exc:
        return rejection(E01_BAR_MALFORMED, formula="F01", detail=str(exc))
    if bar_index < 0:
        return rejection(E01_BAR_MALFORMED, formula="F01", detail="bar_index must be >= 0")
    if not open_time < close_time:
        return rejection(
            E01_BAR_MALFORMED, formula="F01",
            detail="bar time fields must satisfy bar_open_time_us < bar_close_time_us")
    low, high = ticks["low_ticks"], ticks["high_ticks"]
    if not (low <= ticks["open_ticks"] <= high and low <= ticks["close_ticks"] <= high):
        return rejection(
            E01_BAR_MALFORMED, formula="F01",
            detail="OHLC ordering violated: require low<=open<=high and low<=close<=high")
    return {
        "accepted": True,
        "kind": "BAR",
        "bar": {
            "bar_index": bar_index,
            "bar_open_time_us": open_time,
            "bar_close_time_us": close_time,
            **ticks,
        },
    }


def validate_session_level(event: object) -> dict:
    """Accept an E01 F07 session-level event or return a quarantine-shaped rejection.

    On acceptance returns ``{"accepted": True, "kind": "SESSION_LEVEL", "session": {...}}``.
    The ``final`` flag is lawful only after the session-end watermark; a session whose bounds do
    not align to the declared UTC calendar row rejects ``E01_SESSION_CALENDAR_MISMATCH``.
    """
    payload = _payload_of(event)
    if payload is None:
        return rejection(
            E01_SESSION_MALFORMED, formula="F07", detail="event/payload is not an object")
    if payload.get("state_kind") != "SESSION_LEVEL":
        return rejection(
            E01_SESSION_MALFORMED, formula="F07",
            detail=f"state_kind must be 'SESSION_LEVEL', got {payload.get('state_kind')!r}")
    calendar_id = payload.get("calendar_id")
    if not isinstance(calendar_id, str) or not calendar_id:
        return rejection(
            E01_SESSION_MALFORMED, formula="F07", detail="calendar_id must be a non-empty str")
    row = payload.get("calendar_row")
    if not isinstance(row, dict):
        return rejection(
            E01_SESSION_MALFORMED, formula="F07", detail="calendar_row must be an object")
    try:
        offset = require_int(row.get("utc_day_offset_us"), "utc_day_offset_us")
        length = require_int(row.get("session_length_us"), "session_length_us")
        start = require_int(payload.get("session_start_us"), "session_start_us")
        end = require_int(payload.get("session_end_us"), "session_end_us")
        open_ticks = require_int(payload.get("session_open_ticks"), "session_open_ticks")
        high_ticks = require_int(payload.get("session_high_ticks"), "session_high_ticks")
        low_ticks = require_int(payload.get("session_low_ticks"), "session_low_ticks")
    except StructureLawError as exc:
        return rejection(E01_SESSION_MALFORMED, formula="F07", detail=str(exc))
    final = payload.get("final")
    if not isinstance(final, bool):
        return rejection(
            E01_SESSION_MALFORMED, formula="F07", detail="final must be an exact bool")
    if not (0 <= offset < DAY_US and 0 < length <= DAY_US):
        return rejection(
            E01_SESSION_MALFORMED, formula="F07",
            detail="calendar_row bounds: utc_day_offset_us in [0,DAY), session_length_us in (0,DAY]")
    if not start < end:
        return rejection(
            E01_SESSION_MALFORMED, formula="F07",
            detail="session interval must satisfy session_start_us < session_end_us")
    if row.get("calendar_id") != calendar_id:
        return rejection(
            E01_SESSION_CALENDAR_MISMATCH, formula="F07",
            detail="payload calendar_id does not match the declared calendar_row")
    if (start - offset) % DAY_US != 0 or end - start != length:
        return rejection(
            E01_SESSION_CALENDAR_MISMATCH, formula="F07",
            detail="session bounds are not UTC-day-aligned per the declared calendar row")
    if not (low_ticks <= open_ticks <= high_ticks):
        return rejection(
            E01_SESSION_MALFORMED, formula="F07",
            detail="session levels violate low<=open<=high")
    if final:
        watermark = payload.get("session_end_watermark_us")
        try:
            watermark_us = require_int(watermark, "session_end_watermark_us")
        except StructureLawError as exc:
            return rejection(E01_SESSION_MALFORMED, formula="F07", detail=str(exc))
        if watermark_us < end:
            return rejection(
                E01_SESSION_FINAL_BEFORE_WATERMARK, formula="F07",
                detail="final=True before the session-end watermark")
    return {
        "accepted": True,
        "kind": "SESSION_LEVEL",
        "session": {
            "calendar_id": calendar_id,
            "session_start_us": start,
            "session_end_us": end,
            "final": final,
            "session_open_ticks": open_ticks,
            "session_high_ticks": high_ticks,
            "session_low_ticks": low_ticks,
        },
    }
