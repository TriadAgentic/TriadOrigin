"""Flow atoms — F15 trade-flow imbalance, F16 best-level order-flow imbalance, F17 anchored
book-depth tilt (b03 grounding rows; golden vectors GV-013 / GV-014; F16 has no linked golden
vector in the bundle, see the OPEN CONCERN below).

Every machine is a pure :class:`triad_origin.transition.DeterministicMachine`. Exact integer ticks
only (``common.require_int``; bool is not an int). Every semantic parameter arrives via
``transition.require`` — no code default, ever (this includes PAR-055 ``flow_atom_ttl_ms`` and, for
F17, PAR-059 ``book_tilt_band_bps``: both are fetched fail-closed and stamped onto every emitted
event/abstention so a declared parameter is never silently dropped — the PAR-057 precedent). A
missing/warm-up/unratified/insufficient-coverage/invalid-input dependency emits ``common.abstention``
— a NAMED event, never a silent null, never a fabricated value, and never a raise on untrusted
per-event content (the poison-envelope law: one malformed venue event must not halt the deterministic
partition). Thresholds are inclusive (PAR-009): ``>=`` / ``<=`` pass on equality. No machine here
reads a clock, performs I/O, or looks at an input it has not yet been fed (``transition.run`` drives
inputs strictly in order; no machine buffers ahead).

Input envelope shapes (market_state.v2-shaped, minimal and explicit):

* F15 TRADE event (a classified trade + the envelope's own evaluation instant)::

      {"event_id": str, "kind": "TRADE", "evaluation_time_us": int,
       "payload": {"quote_notional_ticks": int, "aggressor_side": "BUY" | "SELL",
                   "event_time_us": int}}

* F16 BOOK_UPDATE event (a best-level book snapshot + its stream sequence + watermark)::

      {"event_id": str, "kind": "BOOK_UPDATE",
       "payload": {"best_bid_price_ticks": int, "best_bid_qty_steps": int,
                   "best_ask_price_ticks": int, "best_ask_qty_steps": int,
                   "sequence": int, "watermark_complete": bool}}

* F17 BOOK_DEPTH event (pre-banded, pre-summed quote depth totals)::

      {"event_id": str, "kind": "BOOK_DEPTH",
       "payload": {"bid_quote_depth_ticks_steps": int, "ask_quote_depth_ticks_steps": int}}

**F15 (:class:`TradeFlowImbalance`, GV-013).** ``TFI = (buy_quote - sell_quote) / (buy_quote +
sell_quote)`` over a rolling window: the most recent ``tfi_window_trades`` (PAR-052, default 100)
trades whose ``event_time_us`` lies within ``tfi_window_max_age_ms`` (PAR-053, default 2000ms) of
the triggering envelope's own ``evaluation_time_us`` — the caller supplies both instants explicitly
per envelope; this machine performs no clock read, only an integer age comparison
(``event_time_us >= evaluation_time_us - max_age_us``, inclusive). A trade whose venue
``aggressor_side`` is missing/unknown is UNCLASSIFIABLE (FPB-0077: no tick-rule fallback): it is
EXCLUDED from the window and never counted toward coverage — a named abstention
``F15_TFI_UNCLASSIFIED_SIDE``, never a raise (``invalid_behavior``: "Missing side ... is null with
reason"). At least ``tfi_min_trades`` (PAR-054, default 20) classified trades must be in-window or
the machine abstains ``F15_TFI_INSUFFICIENT_COVERAGE``; if the window's buy and sell quote notional
are both zero the machine abstains ``F15_TFI_ZERO_DENOMINATOR`` — never a fabricated 0 or a
``None``-as-0. On success the emitted event carries the RAW, UNREDUCED ``numerator``/``denominator``
pair — GV-013: ``buy_quote=70, sell_quote=30`` -> ``numerator=40, denominator=100`` (never reduced
to ``2/5``; reduction is a display concern, not this machine's) — plus its exact source range
(``source_event_time_min_us``/``source_event_time_max_us``, the availability clause "stores exact
source range") and its ``freshness_deadline_us`` (``evaluation_time_us + flow_atom_ttl_ms*1000``,
PAR-055; a downstream consumer past this instant treats the atom as ``FLOW_STALE``). Swapping every
trade's ``aggressor_side`` (BUY<->SELL) negates the numerator exactly and leaves the denominator
untouched — TFI's mirror law, since TFI carries no price/direction geometry to reflect.

**F16 (:class:`OrderFlowImbalance`).** For each sequence-continuous, VALID best-book update ``n``::

    e_n = I(Pb_n>=Pb_prev)*Qb_n - I(Pb_n<=Pb_prev)*Qb_prev
        - I(Pa_n<=Pa_prev)*Qa_n + I(Pa_n>=Pa_prev)*Qa_prev

(``I()`` is the indicator function, computed here as an explicit ``1 if condition else 0`` — never
relying on Python's bool-as-int coercion). ``OFI`` is the plain exact-integer sum of ``e_n`` over the
most recent ``ofi_window_updates`` (PAR-056, default 100) terms. The formula yields null (never zero)
on every invalid-source-state alternative the RC3 row names, each a NAMED abstention (never a raise):

* a ``sequence`` that is not strictly increasing (``<=`` the last accepted sequence) is a stale or
  duplicate venue redelivery — the formula's "duplicate ambiguity" — named ``F16_DUPLICATE_AMBIGUITY``;
  it is quarantined and the already-valid continuous series is preserved untouched (a redelivery
  carries no new state);
* a crossed/invalid best book (``best_bid_price_ticks >= best_ask_price_ticks`` — no positive spread)
  is not a valid best-book state — named ``F16_INVALID_BOOK``; the window is discarded and the baseline
  dropped so no ``e_n`` ever spans an invalid state, and the next valid book re-baselines;
* a ``sequence`` that skips ahead of ``prior + 1`` is a GAP — named ``F16_SEQUENCE_GAP``; the window
  resets and this (valid) update becomes the new baseline.

Fewer than ``ofi_min_updates`` (PAR-058, default 20) accumulated ``e_n`` terms -> named abstention
``F16_INSUFFICIENT_COVERAGE`` (checked regardless of the watermark, below). Emission of the ``OFI``
feature ALSO requires the triggering envelope's own ``watermark_complete: bool`` to be exactly
``True`` — "refuse to emit if not True" per the formula row; an incomplete watermark still advances
the sequence/window state (a later, complete-watermark update still sees a correct, unbroken series)
but this cycle emits NOTHING (a silent non-emission, the F04 precedent), not an abstention. The
declared normalization variant (dividing by registered average depth) is a DISTINCT semantic version
pending its own minimum-depth ratification and is intentionally NOT implemented here — only the raw
sum, ``feature_version = "ofi.raw.v1"``.

**OPEN CONCERN (F16, reported per the task instruction, not silently resolved):** PAR-057
``ofi_window_max_age_ms`` and PAR-055 ``flow_atom_ttl_ms`` both declare a wall/event-time window, but
the RC3-specified book-update input above (unlike F15's trade envelope, which explicitly carries
``event_time_us``/``evaluation_time_us``) carries no timestamp field at all. This machine still
fetches and validates both as required positive-int semantic parameters (fail-closed presence, per
the "every declared parameter arrives via ``require``" law) and threads their validated values into
every emitted event/abstention (``declared_window_max_age_ms``/``declared_flow_atom_ttl_ms``) — so
neither fetch is silently dropped — but it cannot apply an event-time filter or a ``FLOW_STALE``
freshness gate it has no event time to filter with. The window is therefore enforced by
``ofi_window_updates`` (a COUNT cap) and sequence-continuity alone. Resolving this (assigning book
updates a caller-supplied time field, mirroring F15) is an operator/spec disposition, not a decision
this module makes silently. There is also NO golden vector linked to F16 in the bundle; the battery
below pins a hand-worked vector instead and documents its arithmetic inline.

**F17 (:class:`BookDepthTilt`, GV-014).** ``tilt = (bid_quote_depth - ask_quote_depth) /
(bid_quote_depth + ask_quote_depth)`` as an exact, unreduced ``(numerator, denominator)`` pair — the
same discipline as F15. Depth is summed by the CALLER within PAR-059 ``book_tilt_band_bps`` (5bps) of
the same-side best, in PAR-171 ``quote_notional_ticks_steps`` units; this machine performs NO
price-distance banding itself, it only consumes the two pre-summed totals — but it fetches the
declared band via ``require`` and stamps it (``declared_book_tilt_band_bps``, the identity_material
"band") onto every emitted event/abstention, so the declared parameter is never silently dropped.
Emission requires the combined depth (the denominator) to be ``>= book_tilt_min_quote_depth``
(RC3-PAR-STRUCT-002, inclusive, PAR-009); the F17 errata makes that minimum MANDATORY and POSITIVE —
a ratified value below ``1`` is refused, and a zero denominator is ALWAYS null (``F17_INSUFFICIENT_DEPTH``,
"zero denominator is null, never neutral zero"), never a fabricated neutral zero. While the parameter
is the ``common.NOT_RATIFIED`` sentinel — its real status, a ``BLOCKING_RESEARCH_DECISION`` — EVERY
input yields the named abstention ``F17_UNAVAILABLE_MIN_DEPTH_NOT_RATIFIED`` and no state mutates
(SAFE_HOLD), the exact mirror of F06's law in ``typed_level_registry``. Once ratified (a ratified
POSITIVE int, e.g. a TEST-labelled stand-in — RC3-PAR-STRUCT-002 itself is NOT ratified anywhere in
this repository), a combined depth below the minimum (zero included) -> named abstention
``F17_INSUFFICIENT_DEPTH``; GV-014: ``bid_quote_depth=600, ask_quote_depth=400`` -> ``numerator=200,
denominator=1000`` (unreduced; ``= 1/5`` only as a display concern).
"""

from __future__ import annotations

from ..transition import Envelope, Params, Quality, State, TransitionResult, require
from . import common

FORMULA_F15 = "F15"
FORMULA_F16 = "F16"
FORMULA_F17 = "F17"

PARAM_TFI_WINDOW_TRADES = "tfi_window_trades"
PARAM_TFI_WINDOW_MAX_AGE_MS = "tfi_window_max_age_ms"
PARAM_TFI_MIN_TRADES = "tfi_min_trades"

PARAM_OFI_WINDOW_UPDATES = "ofi_window_updates"
PARAM_OFI_WINDOW_MAX_AGE_MS = "ofi_window_max_age_ms"
PARAM_OFI_MIN_UPDATES = "ofi_min_updates"

PARAM_BOOK_TILT_MIN_QUOTE_DEPTH = "book_tilt_min_quote_depth"
PARAM_BOOK_TILT_BAND_BPS = "book_tilt_band_bps"

# PAR-055 FLOW_ATOM_TTL (ms) — declared for F15/F16/F17 alike (FPB-0029/0030/0031). Fetched
# fail-closed and stamped; the FLOW_STALE freshness gate is evaluated where a time basis exists.
PARAM_FLOW_ATOM_TTL_MS = "flow_atom_ttl_ms"

_KIND_TRADE = "TRADE"
_KIND_BOOK_UPDATE = "BOOK_UPDATE"
_KIND_BOOK_DEPTH = "BOOK_DEPTH"

TRADE_SIDE_BUY = "BUY"
TRADE_SIDE_SELL = "SELL"
TRADE_SIDES = (TRADE_SIDE_BUY, TRADE_SIDE_SELL)

F15_FEATURE_VERSION = "tfi.trade_flow_imbalance.v1"
F16_FEATURE_VERSION = "ofi.raw.v1"
F17_FEATURE_VERSION = "book_tilt.quote_depth.v1"


def _event_identity(envelope: Envelope) -> str:
    event_id = envelope.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        raise common.StructureLawError("envelope event_id must be a non-empty string")
    return event_id


def _positive_int(value: object, name: str) -> int:
    number = common.require_int(value, name)
    if number <= 0:
        raise common.StructureLawError(f"{name} must be a positive integer, got {number}")
    return number


def _nonneg_int(value: object, name: str) -> int:
    number = common.require_int(value, name)
    if number < 0:
        raise common.StructureLawError(f"{name} must be a non-negative integer, got {number}")
    return number


def _indicator(condition: bool) -> int:
    """The RC3 indicator function ``I()`` made explicit — never Python's bool-as-int coercion."""
    return 1 if condition else 0


def _typed_payload(envelope: Envelope, kind: str, formula: str) -> tuple[str, dict]:
    event_id = _event_identity(envelope)
    if envelope.get("kind") != kind:
        raise common.StructureLawError(
            f"{formula} consumes {kind} envelopes only, got {envelope.get('kind')!r}")
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise common.StructureLawError(f"{formula} envelope payload must be an object")
    return event_id, payload


class TradeFlowImbalance:
    """F15 — trade flow imbalance over a rolling, age- and count-bounded trade window (GV-013).

    Every classified trade is folded into the window in arrival order; on each envelope the window
    is evicted (relative to THAT envelope's own ``evaluation_time_us`` — no clock read) and capped
    to ``tfi_window_trades`` most-recent entries before the coverage/denominator checks run. A trade
    whose venue aggressor side is missing/unknown is excluded (never counted), a named abstention,
    never a raise.
    """

    def initial_state(self) -> State:
        return {"last_event_id": None, "window": []}

    def transition(
        self, state: State, envelope: Envelope, params: Params, quality: Quality
    ) -> TransitionResult:
        window_trades = _positive_int(
            require(params, PARAM_TFI_WINDOW_TRADES), PARAM_TFI_WINDOW_TRADES)
        max_age_ms = _positive_int(
            require(params, PARAM_TFI_WINDOW_MAX_AGE_MS), PARAM_TFI_WINDOW_MAX_AGE_MS)
        min_trades = _positive_int(
            require(params, PARAM_TFI_MIN_TRADES), PARAM_TFI_MIN_TRADES)
        ttl_ms = _positive_int(
            require(params, PARAM_FLOW_ATOM_TTL_MS), PARAM_FLOW_ATOM_TTL_MS)
        event_id, payload = _typed_payload(envelope, _KIND_TRADE, FORMULA_F15)
        if event_id == state.get("last_event_id"):
            return TransitionResult(state=state)

        evaluation_time_us = common.require_int(
            envelope.get("evaluation_time_us"), "evaluation_time_us")
        event_time_us = common.require_int(payload.get("event_time_us"), "event_time_us")
        if event_time_us > evaluation_time_us:
            raise common.StructureLawError(
                "F15 trade event_time_us must not be after evaluation_time_us")
        notional = _nonneg_int(payload.get("quote_notional_ticks"), "quote_notional_ticks")
        side = payload.get("aggressor_side")
        if side not in TRADE_SIDES:
            # An unclassified aggressor side (missing/unknown) has no tick-rule fallback (FPB-0077):
            # the trade is EXCLUDED — never folded, never counted — and this envelope is a named
            # null, never a raise (the poison-envelope law). The existing window is preserved.
            new_state = {"last_event_id": event_id, "window": state["window"]}
            return TransitionResult(state=new_state, events=(common.abstention(
                "F15_TFI_UNCLASSIFIED_SIDE", formula=FORMULA_F15,
                detail="the venue did not classify the trade aggressor side (missing/unknown); the "
                       "trade is excluded from the window, never counted (no tick-rule fallback)",
                refs={"event_id": event_id, "got_side": repr(side),
                      "declared_flow_atom_ttl_ms": ttl_ms}),))

        threshold = evaluation_time_us - (max_age_ms * 1000)
        window = [dict(trade) for trade in state["window"]]
        window.append({
            "event_time_us": event_time_us, "quote_notional_ticks": notional,
            "aggressor_side": side})
        window = [trade for trade in window if trade["event_time_us"] >= threshold]
        window = window[-window_trades:]

        events: tuple[dict, ...] = ()
        if len(window) < min_trades:
            events = (common.abstention(
                "F15_TFI_INSUFFICIENT_COVERAGE", formula=FORMULA_F15,
                detail=f"{len(window)} of {min_trades} classified trades in the age/count "
                       "window",
                refs={"event_id": event_id, "have_trades": len(window),
                      "need_trades": min_trades, "declared_flow_atom_ttl_ms": ttl_ms}),)
        else:
            buy_quote = sum(
                trade["quote_notional_ticks"] for trade in window
                if trade["aggressor_side"] == TRADE_SIDE_BUY)
            sell_quote = sum(
                trade["quote_notional_ticks"] for trade in window
                if trade["aggressor_side"] == TRADE_SIDE_SELL)
            denominator = buy_quote + sell_quote
            if denominator == 0:
                events = (common.abstention(
                    "F15_TFI_ZERO_DENOMINATOR", formula=FORMULA_F15,
                    detail="buy and sell quote notional in the window are both zero",
                    refs={"event_id": event_id, "trade_count": len(window),
                          "declared_flow_atom_ttl_ms": ttl_ms}),)
            else:
                events = ({
                    "event_kind": "FEATURE",
                    "formula": FORMULA_F15,
                    "feature_version": F15_FEATURE_VERSION,
                    "evaluation_time_us": evaluation_time_us,
                    "numerator": buy_quote - sell_quote,
                    "denominator": denominator,
                    "buy_quote_ticks": buy_quote,
                    "sell_quote_ticks": sell_quote,
                    "trade_count": len(window),
                    "source_event_time_min_us": min(
                        trade["event_time_us"] for trade in window),
                    "source_event_time_max_us": max(
                        trade["event_time_us"] for trade in window),
                    "freshness_deadline_us": evaluation_time_us + ttl_ms * 1000,
                    "declared_flow_atom_ttl_ms": ttl_ms,
                    "confirmed_by_event_id": event_id,
                },)
        new_state = {"last_event_id": event_id, "window": window}
        return TransitionResult(state=new_state, events=events)


class OrderFlowImbalance:
    """F16 — best-level order-flow imbalance over sequence-continuous, VALID book updates.

    See the module OPEN CONCERN above: ``ofi_window_max_age_ms``/``flow_atom_ttl_ms`` are fetched and
    validated (never silently dropped) but this input contract carries no per-update time field to
    filter by, so the window here is enforced by count (``ofi_window_updates``) and sequence
    continuity only. A stale/duplicate redelivery, a crossed/invalid book, and a sequence gap are
    each a NAMED null (never a raise), per the RC3 row.
    """

    def initial_state(self) -> State:
        return {"last_event_id": None, "prev": None, "window": []}

    def transition(
        self, state: State, envelope: Envelope, params: Params, quality: Quality
    ) -> TransitionResult:
        window_updates = _positive_int(
            require(params, PARAM_OFI_WINDOW_UPDATES), PARAM_OFI_WINDOW_UPDATES)
        max_age_ms = _positive_int(
            require(params, PARAM_OFI_WINDOW_MAX_AGE_MS), PARAM_OFI_WINDOW_MAX_AGE_MS)
        min_updates = _positive_int(
            require(params, PARAM_OFI_MIN_UPDATES), PARAM_OFI_MIN_UPDATES)
        ttl_ms = _positive_int(
            require(params, PARAM_FLOW_ATOM_TTL_MS), PARAM_FLOW_ATOM_TTL_MS)
        event_id, payload = _typed_payload(envelope, _KIND_BOOK_UPDATE, FORMULA_F16)
        if event_id == state.get("last_event_id"):
            return TransitionResult(state=state)

        seq = common.require_int(payload.get("sequence"), "sequence")
        bid_price = common.require_int(payload.get("best_bid_price_ticks"), "best_bid_price_ticks")
        bid_qty = _nonneg_int(payload.get("best_bid_qty_steps"), "best_bid_qty_steps")
        ask_price = common.require_int(payload.get("best_ask_price_ticks"), "best_ask_price_ticks")
        ask_qty = _nonneg_int(payload.get("best_ask_qty_steps"), "best_ask_qty_steps")
        watermark_complete = payload.get("watermark_complete")
        if not isinstance(watermark_complete, bool):
            raise common.StructureLawError("F16 watermark_complete must be an exact bool")
        current = {"sequence": seq, "bid_price": bid_price, "bid_qty": bid_qty,
                   "ask_price": ask_price, "ask_qty": ask_qty}
        declared = {"declared_window_max_age_ms": max_age_ms,
                    "declared_flow_atom_ttl_ms": ttl_ms}

        prev = state.get("prev")
        # A non-increasing sequence is a stale/duplicate venue redelivery (the formula's "duplicate
        # ambiguity"): null, never zero, never a raise. Checked FIRST so a stale redelivery never
        # disturbs the already-valid continuous series (its window/prev are preserved untouched).
        if prev is not None and seq <= prev["sequence"]:
            new_state = {"last_event_id": event_id, "prev": prev,
                         "window": list(state["window"])}
            return TransitionResult(state=new_state, events=(common.abstention(
                "F16_DUPLICATE_AMBIGUITY", formula=FORMULA_F16,
                detail="a book update repeated or preceded the last accepted sequence (a stale or "
                       "duplicate venue redelivery); it is quarantined and the valid series is "
                       "preserved",
                refs={"event_id": event_id, "last_sequence": prev["sequence"],
                      "got_sequence": seq, **declared}),))

        # A crossed/invalid best book (no positive spread) is not a valid best-book state: null,
        # never zero. The window is discarded and the baseline dropped so no e_n spans the invalid
        # state; the next valid book re-baselines. (This is also correct at cold start.)
        if bid_price >= ask_price:
            new_state = {"last_event_id": event_id, "prev": None, "window": []}
            return TransitionResult(state=new_state, events=(common.abstention(
                "F16_INVALID_BOOK", formula=FORMULA_F16,
                detail="a crossed/invalid best book (best_bid_price_ticks >= best_ask_price_ticks) "
                       "is not a valid update; the window resets and no e_n spans the invalid state",
                refs={"event_id": event_id, "best_bid_price_ticks": bid_price,
                      "best_ask_price_ticks": ask_price, "got_sequence": seq, **declared}),))

        if prev is not None and seq != prev["sequence"] + 1:
            new_state = {"last_event_id": event_id, "prev": current, "window": []}
            return TransitionResult(state=new_state, events=(common.abstention(
                "F16_SEQUENCE_GAP", formula=FORMULA_F16,
                detail="a book update skipped ahead of the next expected sequence; the "
                       "window never crosses the gap and this update becomes the new "
                       "baseline",
                refs={"event_id": event_id, "expected_sequence": prev["sequence"] + 1,
                      "got_sequence": seq, **declared}),))

        window = list(state["window"])
        if prev is not None:
            e_n = (
                _indicator(bid_price >= prev["bid_price"]) * bid_qty
                - _indicator(bid_price <= prev["bid_price"]) * prev["bid_qty"]
                - _indicator(ask_price <= prev["ask_price"]) * ask_qty
                + _indicator(ask_price >= prev["ask_price"]) * prev["ask_qty"]
            )
            window.append(e_n)
            window = window[-window_updates:]

        events: tuple[dict, ...] = ()
        if len(window) < min_updates:
            events = (common.abstention(
                "F16_INSUFFICIENT_COVERAGE", formula=FORMULA_F16,
                detail=f"{len(window)} of {min_updates} sequence-valid updates accumulated",
                refs={"event_id": event_id, "have_updates": len(window),
                      "need_updates": min_updates, **declared}),)
        elif watermark_complete:
            events = ({
                "event_kind": "FEATURE",
                "formula": FORMULA_F16,
                "feature_version": F16_FEATURE_VERSION,
                "ofi_value": sum(window),
                "window_size": len(window),
                "sequence": seq,
                "declared_window_max_age_ms": max_age_ms,
                "declared_flow_atom_ttl_ms": ttl_ms,
                "confirmed_by_event_id": event_id,
            },)
        new_state = {"last_event_id": event_id, "prev": current, "window": window}
        return TransitionResult(state=new_state, events=events)


class BookDepthTilt:
    """F17 — anchored book-depth tilt over pre-banded, pre-summed quote depth totals (GV-014).

    RC3-PAR-STRUCT-002 ``BOOK_TILT_MIN_QUOTE_DEPTH`` is a ``BLOCKING_RESEARCH_DECISION``, currently
    ``NOT_RATIFIED`` everywhere in this repository — the exact F06 posture. While it stays
    ``NOT_RATIFIED`` every input yields the named abstention
    ``F17_UNAVAILABLE_MIN_DEPTH_NOT_RATIFIED`` and state never mutates (SAFE_HOLD). The F17 errata
    makes the ratified minimum MANDATORY and POSITIVE (``>= 1``); a zero denominator is always null,
    never a neutral zero.
    """

    def initial_state(self) -> State:
        return {"last_event_id": None}

    def transition(
        self, state: State, envelope: Envelope, params: Params, quality: Quality
    ) -> TransitionResult:
        min_depth = require(params, PARAM_BOOK_TILT_MIN_QUOTE_DEPTH)
        band_bps = _positive_int(
            require(params, PARAM_BOOK_TILT_BAND_BPS), PARAM_BOOK_TILT_BAND_BPS)
        ttl_ms = _positive_int(
            require(params, PARAM_FLOW_ATOM_TTL_MS), PARAM_FLOW_ATOM_TTL_MS)
        event_id, payload = _typed_payload(envelope, _KIND_BOOK_DEPTH, FORMULA_F17)
        declared = {"declared_book_tilt_band_bps": band_bps,
                    "declared_flow_atom_ttl_ms": ttl_ms}
        if min_depth == common.NOT_RATIFIED:
            return TransitionResult(state=state, events=(common.abstention(
                "F17_UNAVAILABLE_MIN_DEPTH_NOT_RATIFIED", formula=FORMULA_F17,
                detail="RC3-PAR-STRUCT-002 BOOK_TILT_MIN_QUOTE_DEPTH is NOT_RATIFIED; F17 holds "
                       "SAFE_HOLD with zero state mutation",
                refs={"event_id": event_id, "parameter": "RC3-PAR-STRUCT-002", **declared}),))
        # The F17 errata: "Tilt is null unless total registered quote depth meets a declared POSITIVE
        # minimum." A ratified minimum below 1 is errata-forbidden and fails closed (a misconfigured
        # threshold, the same posture as a bad-type minimum). The short-circuit keeps a non-int
        # (e.g. NOT_RATIFIED already handled, or a stray string) out of the ``< 1`` comparison.
        if not common.is_ratified_int(min_depth) or min_depth < 1:
            raise common.StructureLawError(
                f"{PARAM_BOOK_TILT_MIN_QUOTE_DEPTH} must be a ratified positive int (>= 1) or "
                f"NOT_RATIFIED, got {min_depth!r}")
        if event_id == state.get("last_event_id"):
            return TransitionResult(state=state)

        bid_depth = _nonneg_int(
            payload.get("bid_quote_depth_ticks_steps"), "bid_quote_depth_ticks_steps")
        ask_depth = _nonneg_int(
            payload.get("ask_quote_depth_ticks_steps"), "ask_quote_depth_ticks_steps")
        denominator = bid_depth + ask_depth
        new_state = {"last_event_id": event_id}
        # "Zero denominator is null, never neutral zero" (F17 errata) — held unconditionally, not
        # merely as a consequence of the positive-minimum gate below.
        if denominator == 0:
            return TransitionResult(state=new_state, events=(common.abstention(
                "F17_INSUFFICIENT_DEPTH", formula=FORMULA_F17,
                detail="combined quote depth is zero; zero denominator is null, never a neutral "
                       "zero",
                refs={"event_id": event_id, "denominator": 0, "min_depth": min_depth,
                      **declared}),))
        if denominator < min_depth:
            return TransitionResult(state=new_state, events=(common.abstention(
                "F17_INSUFFICIENT_DEPTH", formula=FORMULA_F17,
                detail=f"combined quote depth {denominator} is below the ratified minimum "
                       f"{min_depth}",
                refs={"event_id": event_id, "denominator": denominator,
                      "min_depth": min_depth, **declared}),))
        event = {
            "event_kind": "FEATURE",
            "formula": FORMULA_F17,
            "feature_version": F17_FEATURE_VERSION,
            "numerator": bid_depth - ask_depth,
            "denominator": denominator,
            "bid_quote_depth_ticks_steps": bid_depth,
            "ask_quote_depth_ticks_steps": ask_depth,
            "declared_book_tilt_band_bps": band_bps,
            "declared_flow_atom_ttl_ms": ttl_ms,
            "confirmed_by_event_id": event_id,
        }
        return TransitionResult(state=new_state, events=(event,))
