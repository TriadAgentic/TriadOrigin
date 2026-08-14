"""RETIRED_DEFECTIVE{defect_ref=TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12 R-F12} —
``ob.displacement_bos.v1`` withdrawal banner (repair spec §1.5).

FOUR CONFIRMED DEFECTS (R-F12): (1) the origin tie-break uses the superseded larger-body rule
(mislabelled below as a "quote-notional" body term without any quantity) instead of the
RC3-effective ``LATEST_THEN_MIN_SOURCE_ID`` rule — body size never participates; (2) one
accepted ``LINKED_BOS`` confirms EVERY same-direction pending block (``_link_bos`` loops all —
the spec's ONE-BOS-ONE-LINEAGE 1:1 consumption map is absent, and the envelope carries no
``bos_occurrence_id`` at all); (3) TTL, mitigation, first-touch and lineage are absent (the
"No TTL" scoping note below is overturned by the ratified R-F12 lifecycle); (4) OHLC validity
is unenforced (``_candidate_geometry`` checks only ``low <= high``, not the §1.1 VALID_BAR
predicate). Repaired as ``ob.displacement_bos.v2``
(:mod:`triad_origin.structures.order_block_v2`; versioned successor face
:mod:`triad_origin.structures.order_block_registry_v2`). The bytes/logic below are preserved
unchanged per the §1.5 withdrawal law — never edited in place, never deleted; rows produced
under this version keep their version tag forever (never-blend across formula versions).

F12 — causal order block: opposing-origin search, BOS-linked confirmation, and a break
lifecycle (b03 grounding row; RC3 formula row F12, gate G2, ``triad.origin.v7.rc3.f12.v1``).

A pure :class:`triad_origin.transition.DeterministicMachine`. **Zero cross-module coupling by
design:** this machine never imports :mod:`displacement` (F11) or :mod:`structure_state` (F09/F08)
— it consumes their OUTPUT SHAPES as caller-supplied input-envelope fields instead, so it is
unit-tested standalone against fed-in displacement/BOS facts. Exact integer ticks only
(``common.require_int``; bool is not an int). Every semantic parameter arrives via
``transition.require`` — no code default, ever. The one declared rational rule this formula needs
(PAR-163 ``ORDER_BLOCK_BREAK``'s buffer) is byte-identical to PAR-043 (F09's break buffer), so this
module imports and reuses ``common.DECLARED_BOS_CLOSE_BUFFER`` rather than declaring a second
rational-rule constant for the same byte-string; the declared string arrives as the required
parameter ``order_block_break_buffer_rule`` and any other string refuses. A missing/unqualified/
horizon-exceeded search emits ``common.abstention`` — a NAMED event, never a silent null and never
a fabricated value. Thresholds are inclusive (PAR-009): the ``W``-th and ``H_bos``-th finalized
bars are the last ones considered; the ``(W+1)``-th and ``(H_bos+1)``-th are excluded.

**One search per displacement.** Every ``ORIGIN_SEARCH_BATCH`` opens (at most) one new order
block, keyed ``ob_<batch event_id>``; this machine tracks every block it has ever opened
simultaneously (a list, not a single slot) — a later batch never supersedes an earlier one's block,
because each is a distinct displacement occurrence. **The search is caller-fed as one complete
batch, never streamed**: the batch carries the full ordered candidate list up front (each tagged
with its own ``offset`` — the count of finalized bars back from the displacement origin, ``1`` =
the bar immediately preceding the origin, ``W`` = the ``W``-th bar back), and the machine picks the
correct origin deterministically in one shot. This keeps the search legible in a single test case
and removes any question of partial-search state.

Input envelope shapes (market_state.v2-shaped, minimal and explicit):

* ``ORIGIN_SEARCH_BATCH`` (opens a fresh order-block search from one qualified F11 displacement
  occurrence, carrying the full backward-search candidate list)::

      {"event_id": str, "kind": "ORIGIN_SEARCH_BATCH",
       "payload": {"displacement_origin_bar_index": int,
                   "displacement_direction": "LONG" | "SHORT",
                   "displacement_availability_bar_index": int,
                   "candidates": [{"source_id": str, "offset": int,
                                    "open_ticks": int, "close_ticks": int,
                                    "high_ticks": int, "low_ticks": int}, ...]}}

* ``LINKED_BOS`` (a same-direction accepted F09 BOS occurrence fact, matched against every
  still-``PENDING`` block by direction and horizon window — there is no explicit block reference;
  linkage is implicit via direction + horizon, mirroring the RC3 "linked" language)::

      {"event_id": str, "kind": "LINKED_BOS",
       "payload": {"bos_bar_index": int, "bos_direction": "LONG" | "SHORT"}}

* ``HORIZON_ELAPSED`` (a caller-supplied marker that the confirmation horizon has been checked past
  its deadline for at least one still-``PENDING`` block — the caller decides when to feed this;
  the machine never invents a wall-clock or a "current bar" on its own)::

      {"event_id": str, "kind": "HORIZON_ELAPSED", "payload": {"current_bar_index": int}}

* ``BAR`` (a finalized close + its causal F02 ATR, checked against every ``CONFIRMED`` block's far
  edge for a break)::

      {"event_id": str, "kind": "BAR",
       "payload": {"close_ticks": int, "atr14_ticks": int | None}}

**Search (PAR-047 ``ORDER_BLOCK_LOOKBACK`` = ``W``, PAR-161 ``ORDER_BLOCK_OPPOSING_PREDICATE``).**
Only candidates with ``1 <= offset <= W`` are ever considered (a batch may carry more; anything
past ``W`` is silently excluded — the search never crosses the lookback boundary). A candidate
OPPOSES the displacement direction iff, per the declared predicate ``"bull:close<open;
bear:close>open"`` (strict inequality only — a doji ``close == open`` is never an opposing origin):
for a LONG/bull displacement the candidate's body must be bearish (``close_ticks < open_ticks``);
for a SHORT/bear displacement it must be bullish (``close_ticks > open_ticks``). Among the
qualifying (opposing) candidates the LATEST wins — the smallest ``offset``, i.e. the bar closest in
time to the displacement origin. A genuine tie (more than one qualifying candidate at the same
minimal offset — a caller-supplied data-quality edge case, since a single well-formed backward walk
carries one bar per offset) breaks by body quote-notional (larger wins; documented choice, since no
quantity is modeled here: ``quote_notional = abs(close_ticks - open_ticks)`` ticks, never a
price*qty product), then by minimum immutable ``source_id`` (lexicographic string comparison). No
qualifying candidate anywhere in ``[1, W]`` -> named abstention ``F12_NO_OPPOSING_ORIGIN_IN_LOOKBACK``;
no order-block state is created for that batch at all.

**Zone geometry (PAR-161 zone convention — the RC3-declared edges, never the full bar range).**
``bull_zone = [low_origin, open_origin]`` (a demand zone, LONG); ``bear_zone = [open_origin,
high_origin]`` (a supply zone, SHORT). The "far edge" used by the break check below is the outer
edge of the zone away from where displacement moved: ``low_origin`` for a bull/LONG demand zone,
``high_origin`` for a bear/SHORT supply zone.

**Confirmation (PAR-160 ``ORDER_BLOCK_BOS_HORIZON`` = ``H_bos``).** A ``PENDING`` block confirms to
``CONFIRMED`` on the first ``LINKED_BOS`` whose ``bos_direction`` matches the block's direction
exactly AND whose ``bos_bar_index`` falls in the inclusive window
``[displacement_availability_bar_index, displacement_availability_bar_index + H_bos]`` (the
``H_bos``-th bar is included, the ``(H_bos+1)``-th is excluded — PAR-009/PAR-160 boundary rule). A
mismatched-direction BOS is silently ignored (not an error, not adopted) whether or not it falls in
the window. **Open concern, documented rather than silently assumed away:** if no matching in-horizon
``LINKED_BOS`` ever arrives, and the caller never feeds a ``HORIZON_ELAPSED`` marker either, the
block stays ``PENDING`` forever in this machine's view — the absence of a future BOS is not itself a
negative signal this module can observe; it can only react to what it is told. A block expires to
``EXPIRED`` (terminal) only when the caller explicitly reports, via ``HORIZON_ELAPSED``, a
``current_bar_index`` strictly past the horizon deadline (``> displacement_availability_bar_index +
H_bos``) while the block is still ``PENDING``. A ``LINKED_BOS`` arriving after a block has already
gone ``EXPIRED`` (or reached any other terminal state) is ignored — rejected, never adopted; a
terminal block never re-opens or re-confirms.

**Break (PAR-163 ``ORDER_BLOCK_BREAK``, reusing PAR-043's declared buffer rule).** Only a
``CONFIRMED`` block can break; ``BROKEN`` is terminal. On each ``BAR`` observation, with ``b =
evaluate_declared_rational(DECLARED_BOS_CLOSE_BUFFER, ATR14_ticks)``: a bull-demand block breaks
when ``close_ticks <= far_edge_ticks - b`` (``far_edge_ticks == low_origin``); a bear-supply block
mirrors, breaking when ``close_ticks >= far_edge_ticks + b`` (``far_edge_ticks == high_origin``) —
both inclusive (equality breaks). A null/absent ``atr14_ticks`` on a ``BAR`` observation is the
named abstention ``F12_NO_ATR`` (the buffer cannot be evaluated; no break check runs that bar).

**No TTL — a deliberate scoping decision, not an oversight.** F10's fair-value-gap zone has an
explicit bar-count TTL bound to PAR-051 ``ZONE_TTL``; F12's own formula row names no TTL parameter
at all (its generic ``inputs`` list mentions ``TTL`` only in the abstract, and the concrete PAR
table carries no order-block-specific TTL id — unlike F10's PAR-051). Rather than invent a value
never declared anywhere in the control bundle (a hidden experiment, forbidden by Doc 02 §02.15),
this implementation has exactly two terminal paths: ``PENDING -> EXPIRED`` (by BOS horizon,
above) and ``CONFIRMED -> BROKEN`` (by the buffered close, above). A ``CONFIRMED`` block that never
breaks stays ``CONFIRMED`` (informally "ACTIVE") indefinitely in this machine's view; there is no
third terminal path here. Introducing a TTL later is a new, separately-ratified PAR — not a code
default smuggled in now.

Mirror law: ``C -> -C``, up <-> down, high <-> low, LONG <-> SHORT, bull <-> bear — proven
algebraically by test (a bearish origin candle, fully price-reflected, is exactly a bullish origin
candle in the mirrored coordinate frame, and the two directions' opposing predicates swap
accordingly).
"""

from __future__ import annotations

from ..transition import Envelope, Params, Quality, State, TransitionResult, require
from . import common

FORMULA_F12 = "F12"

PARAM_ORDER_BLOCK_LOOKBACK_BARS = "order_block_lookback_bars"          # PAR-047 (W)
PARAM_ORDER_BLOCK_BOS_HORIZON_BARS = "order_block_bos_horizon_bars"    # PAR-160 (H_bos)
PARAM_ORDER_BLOCK_BREAK_BUFFER_RULE = "order_block_break_buffer_rule"  # PAR-163 (reuses PAR-043)

_KIND_ORIGIN_SEARCH_BATCH = "ORIGIN_SEARCH_BATCH"
_KIND_LINKED_BOS = "LINKED_BOS"
_KIND_HORIZON_ELAPSED = "HORIZON_ELAPSED"
_KIND_BAR = "BAR"
_KINDS = (_KIND_ORIGIN_SEARCH_BATCH, _KIND_LINKED_BOS, _KIND_HORIZON_ELAPSED, _KIND_BAR)

STATE_PENDING = "PENDING"
STATE_CONFIRMED = "CONFIRMED"
STATE_EXPIRED = "EXPIRED"
STATE_BROKEN = "BROKEN"
_TERMINAL_STATES = (STATE_EXPIRED, STATE_BROKEN)

ORDER_BLOCK_PENDING = "ORDER_BLOCK_PENDING"
ORDER_BLOCK_CONFIRMED = "ORDER_BLOCK_CONFIRMED"
ORDER_BLOCK_EXPIRED = "ORDER_BLOCK_EXPIRED"
ORDER_BLOCK_BROKEN = "ORDER_BLOCK_BROKEN"


def _positive_int(value: object, name: str) -> int:
    number = common.require_int(value, name)
    if number <= 0:
        raise common.StructureLawError(f"{name} must be a positive integer, got {number}")
    return number


def _event_identity(envelope: Envelope) -> str:
    event_id = envelope.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        raise common.StructureLawError("envelope event_id must be a non-empty string")
    return event_id


def _payload(envelope: Envelope) -> dict:
    kind = envelope.get("kind")
    if kind not in _KINDS:
        raise common.StructureLawError(
            f"F12 consumes {_KINDS} envelopes only, got {kind!r}")
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise common.StructureLawError("F12 envelope payload must be an object")
    return payload


def _candidate_geometry(raw: object) -> dict:
    if not isinstance(raw, dict):
        raise common.StructureLawError("F12 candidate must be an object")
    source_id = raw.get("source_id")
    if not isinstance(source_id, str) or not source_id:
        raise common.StructureLawError("F12 candidate source_id must be a non-empty string")
    offset = common.require_int(raw.get("offset"), "offset")
    if offset <= 0:
        raise common.StructureLawError(f"F12 candidate offset must be a positive integer, got {offset}")
    open_ticks = common.require_int(raw.get("open_ticks"), "open_ticks")
    close_ticks = common.require_int(raw.get("close_ticks"), "close_ticks")
    high_ticks = common.require_int(raw.get("high_ticks"), "high_ticks")
    low_ticks = common.require_int(raw.get("low_ticks"), "low_ticks")
    if low_ticks > high_ticks:
        raise common.StructureLawError("F12 candidate low_ticks exceeds high_ticks")
    return {
        "source_id": source_id, "offset": offset, "open_ticks": open_ticks,
        "close_ticks": close_ticks, "high_ticks": high_ticks, "low_ticks": low_ticks,
    }


def _opposes(candidate: dict, direction: str) -> bool:
    if direction == common.LONG:
        return candidate["close_ticks"] < candidate["open_ticks"]
    return candidate["close_ticks"] > candidate["open_ticks"]


def _select_origin(candidates: list[dict], direction: str, lookback: int) -> dict | None:
    """The LATEST (smallest-offset) opposing candidate within ``[1, lookback]``.

    Ties (same minimal offset) break by larger body quote-notional, then minimum ``source_id``.
    """
    in_window = [c for c in candidates if 1 <= c["offset"] <= lookback]
    qualifying = [c for c in in_window if _opposes(c, direction)]
    if not qualifying:
        return None

    def sort_key(candidate: dict) -> tuple[int, int, str]:
        notional = abs(candidate["close_ticks"] - candidate["open_ticks"])
        return (candidate["offset"], -notional, candidate["source_id"])

    return min(qualifying, key=sort_key)


def _zone_geometry(direction: str, origin: dict) -> tuple[int, int, int]:
    """``(zone_low_ticks, zone_high_ticks, far_edge_ticks)`` per the PAR-161 zone convention."""
    if direction == common.LONG:
        return origin["low_ticks"], origin["open_ticks"], origin["low_ticks"]
    return origin["open_ticks"], origin["high_ticks"], origin["high_ticks"]


def _new_block(
    order_block_id: str, direction: str, batch_event_id: str,
    displacement_origin_bar_index: int, displacement_availability_bar_index: int,
    bos_horizon_bars: int, origin: dict,
) -> dict:
    zone_low, zone_high, far_edge = _zone_geometry(direction, origin)
    return {
        "order_block_id": order_block_id,
        "direction": direction,
        "state": STATE_PENDING,
        "displacement_origin_bar_index": displacement_origin_bar_index,
        "displacement_availability_bar_index": displacement_availability_bar_index,
        "bos_horizon_deadline_bar_index": displacement_availability_bar_index + bos_horizon_bars,
        "origin_source_id": origin["source_id"],
        "origin_offset": origin["offset"],
        "origin_open_ticks": origin["open_ticks"],
        "origin_close_ticks": origin["close_ticks"],
        "origin_high_ticks": origin["high_ticks"],
        "origin_low_ticks": origin["low_ticks"],
        "zone_low_ticks": zone_low,
        "zone_high_ticks": zone_high,
        "far_edge_ticks": far_edge,
        "batch_event_id": batch_event_id,
    }


def _pending_event(block: dict) -> dict:
    return {
        "event_kind": ORDER_BLOCK_PENDING, "formula": FORMULA_F12,
        "order_block_id": block["order_block_id"], "direction": block["direction"],
        "displacement_origin_bar_index": block["displacement_origin_bar_index"],
        "displacement_availability_bar_index": block["displacement_availability_bar_index"],
        "bos_horizon_deadline_bar_index": block["bos_horizon_deadline_bar_index"],
        "origin_source_id": block["origin_source_id"], "origin_offset": block["origin_offset"],
        "origin_open_ticks": block["origin_open_ticks"],
        "origin_close_ticks": block["origin_close_ticks"],
        "origin_high_ticks": block["origin_high_ticks"],
        "origin_low_ticks": block["origin_low_ticks"],
        "zone_low_ticks": block["zone_low_ticks"], "zone_high_ticks": block["zone_high_ticks"],
        "formed_by_event_id": block["batch_event_id"],
    }


def _confirmed_event(block: dict, bos_bar_index: int, confirmed_by_event_id: str) -> dict:
    return {
        "event_kind": ORDER_BLOCK_CONFIRMED, "formula": FORMULA_F12,
        "order_block_id": block["order_block_id"], "direction": block["direction"],
        "bos_bar_index": bos_bar_index, "confirmed_by_event_id": confirmed_by_event_id,
    }


def _expired_event(block: dict, expired_at_event_id: str) -> dict:
    return {
        "event_kind": ORDER_BLOCK_EXPIRED, "formula": FORMULA_F12,
        "order_block_id": block["order_block_id"], "direction": block["direction"],
        "bos_horizon_deadline_bar_index": block["bos_horizon_deadline_bar_index"],
        "expired_at_event_id": expired_at_event_id,
    }


def _broken_event(
    block: dict, close_ticks: int, buffer_ticks: int, broken_by_event_id: str,
) -> dict:
    return {
        "event_kind": ORDER_BLOCK_BROKEN, "formula": FORMULA_F12,
        "order_block_id": block["order_block_id"], "direction": block["direction"],
        "far_edge_ticks": block["far_edge_ticks"], "buffer_ticks": buffer_ticks,
        "close_ticks": close_ticks, "broken_by_event_id": broken_by_event_id,
    }


class OrderBlockRegistry:
    """F12 — causal order block over a caller-fed opposing-origin search batch, BOS-linked
    confirmation, and a buffered break lifecycle. See the module docstring for the full law.
    """

    def initial_state(self) -> State:
        return {"last_event_id": None, "order_blocks": {}}

    def transition(
        self, state: State, envelope: Envelope, params: Params, quality: Quality
    ) -> TransitionResult:
        lookback = _positive_int(
            require(params, PARAM_ORDER_BLOCK_LOOKBACK_BARS), PARAM_ORDER_BLOCK_LOOKBACK_BARS)
        bos_horizon = _positive_int(
            require(params, PARAM_ORDER_BLOCK_BOS_HORIZON_BARS), PARAM_ORDER_BLOCK_BOS_HORIZON_BARS)
        buffer_rule = require(params, PARAM_ORDER_BLOCK_BREAK_BUFFER_RULE)
        if buffer_rule != common.DECLARED_BOS_CLOSE_BUFFER:
            raise common.StructureLawError(
                f"F12 admits only the declared PAR-163/PAR-043 rule "
                f"{common.DECLARED_BOS_CLOSE_BUFFER!r}, got {buffer_rule!r}")

        event_id = _event_identity(envelope)
        if event_id == state.get("last_event_id"):
            return TransitionResult(state=state)
        payload = _payload(envelope)
        blocks = {key: dict(value) for key, value in state["order_blocks"].items()}
        kind = envelope.get("kind")

        if kind == _KIND_ORIGIN_SEARCH_BATCH:
            return self._search(blocks, event_id, payload, lookback, bos_horizon)
        if kind == _KIND_LINKED_BOS:
            return self._link_bos(blocks, event_id, payload)
        if kind == _KIND_HORIZON_ELAPSED:
            return self._horizon_elapsed(blocks, event_id, payload)
        return self._break_check(blocks, event_id, payload, buffer_rule)

    def _search(
        self, blocks: dict, event_id: str, payload: dict, lookback: int, bos_horizon: int,
    ) -> TransitionResult:
        origin_bar_index = common.require_int(
            payload.get("displacement_origin_bar_index"), "displacement_origin_bar_index")
        direction = common.require_direction(payload.get("displacement_direction"))
        availability_bar_index = common.require_int(
            payload.get("displacement_availability_bar_index"),
            "displacement_availability_bar_index")
        raw_candidates = payload.get("candidates")
        if not isinstance(raw_candidates, list):
            raise common.StructureLawError("F12 ORIGIN_SEARCH_BATCH candidates must be a list")
        candidates = [_candidate_geometry(raw) for raw in raw_candidates]

        winner = _select_origin(candidates, direction, lookback)
        if winner is None:
            return TransitionResult(
                state={"last_event_id": event_id, "order_blocks": blocks},
                events=(common.abstention(
                    "F12_NO_OPPOSING_ORIGIN_IN_LOOKBACK", formula=FORMULA_F12,
                    detail="no opposing-body candidate qualified within the W-bar lookback "
                           "window; no order-block candidate is created for this batch",
                    refs={"event_id": event_id, "displacement_origin_bar_index": origin_bar_index,
                          "lookback_bars": lookback}),))

        order_block_id = f"ob_{event_id}"
        block = _new_block(
            order_block_id, direction, event_id, origin_bar_index, availability_bar_index,
            bos_horizon, winner)
        blocks[order_block_id] = block
        return TransitionResult(
            state={"last_event_id": event_id, "order_blocks": blocks},
            events=(_pending_event(block),))

    def _link_bos(self, blocks: dict, event_id: str, payload: dict) -> TransitionResult:
        bos_bar_index = common.require_int(payload.get("bos_bar_index"), "bos_bar_index")
        bos_direction = common.require_direction(payload.get("bos_direction"))
        events: tuple[dict, ...] = ()
        for order_block_id in sorted(blocks):
            block = blocks[order_block_id]
            if block["state"] != STATE_PENDING or block["direction"] != bos_direction:
                continue
            if not (block["displacement_availability_bar_index"]
                    <= bos_bar_index <= block["bos_horizon_deadline_bar_index"]):
                continue
            block["state"] = STATE_CONFIRMED
            events += (_confirmed_event(block, bos_bar_index, event_id),)
        return TransitionResult(
            state={"last_event_id": event_id, "order_blocks": blocks}, events=events)

    def _horizon_elapsed(self, blocks: dict, event_id: str, payload: dict) -> TransitionResult:
        current_bar_index = common.require_int(
            payload.get("current_bar_index"), "current_bar_index")
        events: tuple[dict, ...] = ()
        for order_block_id in sorted(blocks):
            block = blocks[order_block_id]
            if block["state"] != STATE_PENDING:
                continue
            if current_bar_index > block["bos_horizon_deadline_bar_index"]:
                block["state"] = STATE_EXPIRED
                events += (_expired_event(block, event_id),)
        return TransitionResult(
            state={"last_event_id": event_id, "order_blocks": blocks}, events=events)

    def _break_check(
        self, blocks: dict, event_id: str, payload: dict, buffer_rule: str,
    ) -> TransitionResult:
        close_ticks = common.require_int(payload.get("close_ticks"), "close_ticks")
        atr = payload.get("atr14_ticks")
        if atr is None:
            return TransitionResult(
                state={"last_event_id": event_id, "order_blocks": blocks},
                events=(common.abstention(
                    "F12_NO_ATR", formula=FORMULA_F12,
                    detail="causal ATR14 is null (warm-up/gap); the break buffer is unavailable "
                           "so no confirmed order block is checked for a break this bar",
                    refs={"event_id": event_id}),))
        buffer = common.evaluate_declared_rational(
            buffer_rule, common.require_int(atr, "atr14_ticks"))
        events: tuple[dict, ...] = ()
        for order_block_id in sorted(blocks):
            block = blocks[order_block_id]
            if block["state"] != STATE_CONFIRMED:
                continue
            if block["direction"] == common.LONG:
                broke = close_ticks <= block["far_edge_ticks"] - buffer
            else:
                broke = close_ticks >= block["far_edge_ticks"] + buffer
            if broke:
                block["state"] = STATE_BROKEN
                events += (_broken_event(block, close_ticks, buffer, event_id),)
        return TransitionResult(
            state={"last_event_id": event_id, "order_blocks": blocks}, events=events)
