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

from dataclasses import dataclass

from .canonical import INT64_MAX, INT64_MIN
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


# =================================================================================================
# TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12 — Part A §1.1 VALID_BAR + Part C §C.3 boundary
# validators (B02C). Additive: nothing above this line changed; validate_finalized_bar /
# validate_session_level callers are untouched.
#
# ValidatedBar / ValidatedTrade / ValidatedBookUpdate are the C.3 `ValidatedInput` types. They
# are frozen dataclasses defined ONLY in this module; the later CI static gate enforces
# construction-locality by scan ("construction of ValidatedInput outside the e01_interface
# module" fails the build). Deliberately NO token mechanism — a Python object is never a
# security boundary; the scan is the wall.
#
# Failure behavior is a TYPED quarantine exception (fail-closed): the consuming formula emits
# no atom and journals the exception's `.record()` (quarantine-shaped, mirroring `rejection()`).
# A quarantined bar invalidates any path/window that requires it, exactly as a GAP does (§1.1).
# =================================================================================================

QUARANTINE_INVALID_BAR = "QUARANTINE_INVALID_BAR"
QUARANTINE_INVALID_TRADE = "QUARANTINE_INVALID_TRADE"
QUARANTINE_INVALID_BOOK_UPDATE = "QUARANTINE_INVALID_BOOK_UPDATE"

# The venue-provided aggressor flag vocabulary (R-F15 law: venue aggressor flag only; the
# existing per-formula twin is structures.flow_atoms.TRADE_SIDES — kept byte-equal, re-homing
# the formula constant onto this boundary constant is the §C.3 conversion train's edit).
TRADE_AGGRESSOR_SIDES = ("BUY", "SELL")

_VALID_BAR_PRICE_FIELDS = ("open_ticks", "high_ticks", "low_ticks", "close_ticks")
_VALID_BAR_COUNT_FIELDS = ("base_volume", "quote_volume", "trade_count")
_VALID_BAR_FIELDS = _VALID_BAR_PRICE_FIELDS + _VALID_BAR_COUNT_FIELDS


class QuarantineInvalidBar(ValueError):
    """§1.1 failure: ``QUARANTINE_INVALID_BAR{bar_identity, reason}``.

    The consuming formula emits NO atom and records this quarantine; the bar invalidates any
    path/window that requires it (F11 path, F02 window, F13 hold chain), exactly as a GAP does.
    ``bar_identity`` is the extractable identity or ``None`` when the input carries none —
    never a fabricated placeholder.
    """

    def __init__(self, *, bar_identity: str | None, reason: str) -> None:
        super().__init__(f"{QUARANTINE_INVALID_BAR}:{bar_identity!r}:{reason}")
        self.bar_identity = bar_identity
        self.reason = reason

    def record(self) -> dict:
        return {
            "event_kind": "QUARANTINE",
            "accepted": False,
            "reason_code": QUARANTINE_INVALID_BAR,
            "bar_identity": self.bar_identity,
            "reason": self.reason,
        }


class QuarantineInvalidTrade(ValueError):
    """§C.3 trade-boundary failure: typed, fail-closed; ``trade_id`` is best-effort or None."""

    def __init__(self, *, trade_id: str | None, reason: str) -> None:
        super().__init__(f"{QUARANTINE_INVALID_TRADE}:{trade_id!r}:{reason}")
        self.trade_id = trade_id
        self.reason = reason

    def record(self) -> dict:
        return {
            "event_kind": "QUARANTINE",
            "accepted": False,
            "reason_code": QUARANTINE_INVALID_TRADE,
            "trade_id": self.trade_id,
            "reason": self.reason,
        }


class QuarantineInvalidBookUpdate(ValueError):
    """§C.3 book-boundary failure: typed, fail-closed; ``sequence`` is best-effort or None."""

    def __init__(self, *, sequence: int | None, reason: str) -> None:
        super().__init__(f"{QUARANTINE_INVALID_BOOK_UPDATE}:{sequence!r}:{reason}")
        self.sequence = sequence
        self.reason = reason

    def record(self) -> dict:
        return {
            "event_kind": "QUARANTINE",
            "accepted": False,
            "reason_code": QUARANTINE_INVALID_BOOK_UPDATE,
            "sequence": self.sequence,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ValidatedBar:
    """A bar that passed the §1.1 VALID_BAR predicate. Constructed ONLY by require_valid_bar."""

    bar_identity: str
    metadata_revision: str
    open_ticks: int
    high_ticks: int
    low_ticks: int
    close_ticks: int
    base_volume: int
    quote_volume: int
    trade_count: int


@dataclass(frozen=True)
class ValidatedTrade:
    """A trade that passed the §C.3 boundary. Constructed ONLY by validate_trade."""

    trade_id: str
    revision: str
    event_time_us: int
    aggressor_side: str


@dataclass(frozen=True)
class ValidatedBookUpdate:
    """A best-quote update that passed the §C.3 boundary. Constructed ONLY by
    validate_book_update."""

    sequence: int
    event_time_us: int
    best_bid_price_ticks: int
    best_bid_qty_steps: int
    best_ask_price_ticks: int
    best_ask_qty_steps: int


def _identity_str_or_none(payload: dict, key: str) -> str | None:
    value = payload.get(key)
    if isinstance(value, str) and value:
        return value
    return None


def _bar_int64(payload: dict, name: str, *, bar_identity: str | None) -> int:
    """An exact signed-int64 VALID_BAR field, else QuarantineInvalidBar (fail closed)."""
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise QuarantineInvalidBar(
            bar_identity=bar_identity,
            reason=f"{name} must be an exact int, got {type(value).__name__}")
    if value < INT64_MIN or value > INT64_MAX:
        raise QuarantineInvalidBar(
            bar_identity=bar_identity,
            reason=f"{name} is outside the signed int64 domain (PAR-INT-01)")
    return value


def require_valid_bar(bar: object) -> ValidatedBar:
    """The §1.1 VALID_BAR predicate, verbatim; returns a ValidatedBar or raises
    QuarantineInvalidBar.

    ``VALID_BAR(b) := open, high, low, close, base_volume, quote_volume, trade_count all
    present AND all price fields are checked signed int64 ticks under the bar's
    metadata_revision AND low <= min(open, close) AND max(open, close) <= high AND
    low <= high (implied; asserted anyway) AND base_volume >= 0 AND quote_volume >= 0
    AND trade_count >= 0.``

    Input is a mapping carrying ``bar_identity`` (non-empty str), ``metadata_revision``
    (non-empty str — the revision the int64 tick check is made under), the four ``*_ticks``
    price fields and the three volume/count fields. Never repairs, never synthesizes.
    """
    if not isinstance(bar, dict):
        raise QuarantineInvalidBar(bar_identity=None, reason="bar is not an object")
    bar_identity = _identity_str_or_none(bar, "bar_identity")
    if bar_identity is None:
        raise QuarantineInvalidBar(
            bar_identity=None, reason="bar_identity must be a non-empty str")
    revision = bar.get("metadata_revision")
    if not isinstance(revision, str) or not revision:
        raise QuarantineInvalidBar(
            bar_identity=bar_identity, reason="metadata_revision must be a non-empty str")
    # Clause 1 — all seven fields present (None is absent, never a value).
    for name in _VALID_BAR_FIELDS:
        if bar.get(name) is None:
            raise QuarantineInvalidBar(bar_identity=bar_identity, reason=f"{name} is missing")
    # Clause 2 — price fields are exact signed int64 ticks under metadata_revision. The three
    # count fields are persisted integers too, so they carry the same §1.2 boundary check.
    values = {
        name: _bar_int64(bar, name, bar_identity=bar_identity) for name in _VALID_BAR_FIELDS
    }
    open_ticks = values["open_ticks"]
    high_ticks = values["high_ticks"]
    low_ticks = values["low_ticks"]
    close_ticks = values["close_ticks"]
    # Clause 3 — low <= min(open, close).
    if not low_ticks <= min(open_ticks, close_ticks):
        raise QuarantineInvalidBar(
            bar_identity=bar_identity, reason="low_ticks must satisfy low <= min(open, close)")
    # Clause 4 — max(open, close) <= high.
    if not max(open_ticks, close_ticks) <= high_ticks:
        raise QuarantineInvalidBar(
            bar_identity=bar_identity, reason="high_ticks must satisfy max(open, close) <= high")
    # Clause 5 — low <= high: implied by clauses 3+4; asserted anyway (spec: "assert anyway").
    if not low_ticks <= high_ticks:  # pragma: no cover - unreachable when clauses 3+4 hold
        raise QuarantineInvalidBar(
            bar_identity=bar_identity, reason="low_ticks must satisfy low <= high")
    # Clause 6 — volumes and trade count are non-negative.
    for name in _VALID_BAR_COUNT_FIELDS:
        if values[name] < 0:
            raise QuarantineInvalidBar(
                bar_identity=bar_identity, reason=f"{name} must be >= 0")
    return ValidatedBar(
        bar_identity=bar_identity,
        metadata_revision=revision,
        open_ticks=open_ticks,
        high_ticks=high_ticks,
        low_ticks=low_ticks,
        close_ticks=close_ticks,
        base_volume=values["base_volume"],
        quote_volume=values["quote_volume"],
        trade_count=values["trade_count"],
    )


def _trade_int64(payload: dict, name: str, *, trade_id: str | None) -> int:
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise QuarantineInvalidTrade(
            trade_id=trade_id, reason=f"{name} must be an exact int, got {type(value).__name__}")
    if value < INT64_MIN or value > INT64_MAX:
        raise QuarantineInvalidTrade(
            trade_id=trade_id, reason=f"{name} is outside the signed int64 domain (PAR-INT-01)")
    return value


def validate_trade(trade: object) -> ValidatedTrade:
    """§C.3 trade boundary: requires event_time, aggressor flag, trade_id, revision.

    Fail-closed typed rejection (:class:`QuarantineInvalidTrade`) on any missing or malformed
    requirement. The aggressor flag is the venue-provided side, exactly one of
    ``TRADE_AGGRESSOR_SIDES`` — a trade with a missing/unknown flag never crosses the boundary
    (R-F15: excluded, never guessed).
    """
    if not isinstance(trade, dict):
        raise QuarantineInvalidTrade(trade_id=None, reason="trade is not an object")
    trade_id = _identity_str_or_none(trade, "trade_id")
    if trade_id is None:
        raise QuarantineInvalidTrade(trade_id=None, reason="trade_id must be a non-empty str")
    revision = trade.get("revision")
    if not isinstance(revision, str) or not revision:
        raise QuarantineInvalidTrade(
            trade_id=trade_id, reason="revision must be a non-empty str")
    event_time_us = _trade_int64(trade, "event_time_us", trade_id=trade_id)
    if event_time_us < 0:
        raise QuarantineInvalidTrade(trade_id=trade_id, reason="event_time_us must be >= 0")
    aggressor_side = trade.get("aggressor_side")
    if not isinstance(aggressor_side, str) or aggressor_side not in TRADE_AGGRESSOR_SIDES:
        raise QuarantineInvalidTrade(
            trade_id=trade_id,
            reason=f"aggressor_side must be one of {TRADE_AGGRESSOR_SIDES}, "
                   f"got {aggressor_side!r}")
    return ValidatedTrade(
        trade_id=trade_id,
        revision=revision,
        event_time_us=event_time_us,
        aggressor_side=aggressor_side,
    )


def _book_int64(payload: dict, name: str, *, sequence: int | None) -> int:
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise QuarantineInvalidBookUpdate(
            sequence=sequence,
            reason=f"{name} must be an exact int, got {type(value).__name__}")
    if value < INT64_MIN or value > INT64_MAX:
        raise QuarantineInvalidBookUpdate(
            sequence=sequence,
            reason=f"{name} is outside the signed int64 domain (PAR-INT-01)")
    return value


def validate_book_update(
    update: object,
    *,
    prior_seq: int | None,
    now_us: int,
    freshness_bound_us: int,
) -> ValidatedBookUpdate:
    """§C.3 book boundary: seq continuity vs prior seq, uncrossed bid<ask, positive qty,
    event_time, freshness bound.

    Fail-closed typed rejection (:class:`QuarantineInvalidBookUpdate`) on any violation:

    * ``sequence`` continuity — with a known ``prior_seq`` the update must carry EXACTLY
      ``prior_seq + 1`` (a duplicate, backward, or gapped sequence is rejected); the first
      update (``prior_seq is None``) has no continuity to check.
    * ``best_bid_price_ticks < best_ask_price_ticks`` — strictly uncrossed (a locked book is
      rejected too).
    * both quantities strictly positive.
    * ``event_time_us`` present, and fresh under the injected clock: not in the future of
      ``now_us`` and ``now_us - event_time_us <= freshness_bound_us`` (inclusive at the bound).

    ``now_us`` is INJECTED — nothing here reads a wall clock.
    """
    if not isinstance(update, dict):
        raise QuarantineInvalidBookUpdate(sequence=None, reason="book update is not an object")
    sequence = _book_int64(update, "sequence", sequence=None)
    if sequence < 0:
        raise QuarantineInvalidBookUpdate(sequence=sequence, reason="sequence must be >= 0")
    event_time_us = _book_int64(update, "event_time_us", sequence=sequence)
    if event_time_us < 0:
        raise QuarantineInvalidBookUpdate(
            sequence=sequence, reason="event_time_us must be >= 0")
    bid_price = _book_int64(update, "best_bid_price_ticks", sequence=sequence)
    bid_qty = _book_int64(update, "best_bid_qty_steps", sequence=sequence)
    ask_price = _book_int64(update, "best_ask_price_ticks", sequence=sequence)
    ask_qty = _book_int64(update, "best_ask_qty_steps", sequence=sequence)
    if prior_seq is not None:
        prior = require_int(prior_seq, "prior_seq")
        if sequence != prior + 1:
            raise QuarantineInvalidBookUpdate(
                sequence=sequence,
                reason=f"sequence discontinuity: expected {prior + 1}, got {sequence}")
    if not bid_price < ask_price:
        raise QuarantineInvalidBookUpdate(
            sequence=sequence,
            reason="book is crossed or locked: require best_bid_price_ticks < "
                   "best_ask_price_ticks")
    if bid_qty <= 0 or ask_qty <= 0:
        raise QuarantineInvalidBookUpdate(
            sequence=sequence, reason="best-quote quantities must be strictly positive")
    clock_now = require_int(now_us, "now_us")
    bound = require_int(freshness_bound_us, "freshness_bound_us")
    if bound < 0:
        raise StructureLawError("freshness_bound_us must be >= 0")
    if event_time_us > clock_now:
        raise QuarantineInvalidBookUpdate(
            sequence=sequence, reason="event_time_us is in the future of now_us")
    if clock_now - event_time_us > bound:
        raise QuarantineInvalidBookUpdate(
            sequence=sequence,
            reason=f"stale book update: age {clock_now - event_time_us}us exceeds "
                   f"freshness bound {bound}us")
    return ValidatedBookUpdate(
        sequence=sequence,
        event_time_us=event_time_us,
        best_bid_price_ticks=bid_price,
        best_bid_qty_steps=bid_qty,
        best_ask_price_ticks=ask_price,
        best_ask_qty_steps=ask_qty,
    )
