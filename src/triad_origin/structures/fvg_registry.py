"""RETIRED_DEFECTIVE{defect_ref=TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12 R-F10} —
``fvg.three_bar.closed.v2`` withdrawal banner (repair spec §1.5).

DEFECT: this v2 machine evaluates existing zones for touch/fill BEFORE the sequence-gap reset
(the gap only clears the local 3-bar formation window), so a pre-gap zone can be "filled"
across missing bars; the exact INVALIDATED path, the midpoint/penetration state, the TTL
binding, and compaction are absent. Repaired as ``fvg.three_bar.closed.v3``
(:mod:`triad_origin.structures.fvg_registry_v3` — continuity-first evaluation order,
INVALIDATED{SEQUENCE_GAP}, reduced-rational penetration states, the FVG_TTL_BARS /
FVG_TOUCH_PRICE_SOURCE / FVG_INVALIDATION_RULE / FVG_MAX_OPEN_PER_PARTITION bindings and
terminal compaction). The bytes/logic below are FROZEN: never edited in place, never deleted;
rows produced under v2 keep their version tag forever (never-blend applies across formula
versions exactly as across cohorts).

F10 — three-bar fair-value gap (FVG) zone with penetration lifecycle (b03 grounding row;
golden vector GV-009).

**Geometry (RC1/RC2, retained where compatible).** For finalized bars ``i-2``, ``i-1``, ``i``:

* BULLISH gap iff ``low_i > high_{i-2}`` (strict); ``gap_ticks = low_i - high_{i-2}``; zone range
  ``[high_{i-2}, low_i]``; ``direction = LONG`` (a support zone below price at formation).
* BEARISH mirrors: ``high_i < low_{i-2}``; ``gap_ticks = low_{i-2} - high_i``; zone range
  ``[high_i, low_{i-2}]``; ``direction = SHORT``.

The middle bar ``i-1`` establishes the three-bar structural window (its own high/low never enter
the inequality) but its ``event_id`` is retained in ``origin_event_ids`` for provenance. The gap
FORMS on finalization of bar ``i`` (the third bar) — no confirmation delay, unlike F04.

**Minimum gap (PAR-044).** ``gap_ticks >= FVG_MIN_GAP`` where ``FVG_MIN_GAP =
evaluate_declared_rational(DECLARED_BOS_CLOSE_BUFFER, ATR14_ticks)`` — the exact declared string
``"max(1,ceil(ATR14_ticks*1/20))"`` is byte-identical to PAR-043 (F09's break buffer), so this
module imports and reuses ``common.DECLARED_BOS_CLOSE_BUFFER`` rather than declaring a second
rational-rule constant for the same byte-string. The declared string arrives as the required
parameter ``fvg_min_gap_rule``; any other string refuses. Both the raw-gap-existence check and the
min-gap threshold are inclusive per PAR-009: GV-009 (ATR 20, min_gap 1) — bar ``i-2`` high 100, bar
``i`` low 101 -> gap 1 >= 1 -> forms; bar ``i`` low 100 -> gap 0 -> ``low_i > high_{i-2}`` is
already false -> no formation (the strict raw-gap inequality fails before the threshold is ever
consulted). At a higher ATR the threshold itself becomes the discriminator: ATR 100 -> min_gap 5 ->
gap 4 (a real, positive, sub-threshold gap) does not form; gap 5 forms (equality passes).

**Missing ATR.** A raw geometric gap candidate (bullish or bearish inequality holds) whose bar-``i``
``atr14_ticks`` is null is the named abstention ``F10_NO_ATR`` — the min-gap threshold cannot be
evaluated, so no zone is fabricated. A bar with NO raw gap at all is silent (nothing to abstain
about — mirrors F04's tie-rejection / F06's out-of-tolerance non-emission, which are also silent).

**PAR-051 ZONE_TTL.** A plain positive integer (NOT a declared-rational rule), required as
``zone_ttl_bars``. It is bar-count based, never wall-clock: a zone's ``bars_since_formation``
starts at 0 on its formation bar and increments by exactly 1 on every subsequently PROCESSED
finalized bar (a bar_seq data gap still counts — the gap only resets the local 3-bar formation
window below, because a genuine geometric triple needs true market adjacency, but the zone's own
age counts every finalized bar this module actually sees, per the formula text "the Nth finalized
base bar"). At ``bars_since_formation == zone_ttl_bars`` (equality, PAR-009 inclusive) the zone
EXPIRES; at ``zone_ttl_bars - 1`` it does not.

**Terminal precedence.** On each bar, TTL expiry is checked BEFORE the touch/fill check for every
pre-existing, non-terminal zone (the RC3 law's explicit "apply terminal precedence before touch") —
a zone that ages into expiry this bar is never also touch-evaluated on the same bar. EXPIRED is
reachable only from a state short of full fill (the loop skips every already-terminal zone
entirely, so a FULLY_FILLED zone can never subsequently expire, and a terminal zone never re-emits
— idempotent by construction, not by a special-cased check).

**Fill law.** Each zone tracks a monotonically shrinking ``[remaining_low_ticks,
remaining_high_ticks]`` sub-interval of its immutable original ``[zone_low_ticks,
zone_high_ticks]``. A BULLISH zone empties from its top edge downward (price retraces from above);
a touching bar's ``low_ticks`` pulls ``remaining_high_ticks`` down (never below
``remaining_low_ticks``, never upward). A BEARISH zone empties from its bottom edge upward; a
touching bar's ``high_ticks`` pulls ``remaining_low_ticks`` up (never above ``remaining_high_ticks``,
never downward). A bar "touches" the zone iff its ``[low_ticks, high_ticks]`` range overlaps the
CURRENT remaining sub-interval; a touch that does not move the boundary (the bar's edge does not
reach past the already-filled boundary) yields no event. FULLY_FILLED fires when the remaining
sub-interval collapses to zero width (equality, PAR-009).

**Same-bar formation-and-touch (documented rule).** RC3 requires the gap to FORM first, then the
SAME finalizing bar's own range is checked against the newly-formed zone for a same-bar touch (the
gap could not have been touched before it existed). This module runs exactly that: emit
``ZONE_FORMED``, then immediately apply the touch check using bar ``i``'s own high/low against the
zone it just defined. **For this exact three-bar geometry the same-bar touch is ALWAYS a
zero-shrink boundary touch and never advances the zone's state**: bar ``i``'s own extreme
(``low_i`` for BULLISH, ``high_i`` for BEARISH) is *by definition* the very edge that was just used
to set ``remaining_high_ticks``/``remaining_low_ticks`` — a bar's own low cannot fall below its own
low, so it can only ever reach exactly its own newly-formed boundary, never past it. The ordering is
still exercised and asserted (structural legality + no spurious event), rather than skipped, because
a caller must be able to rely on the precedence rule running on every formation bar.

Input envelope shape (market_state.v2-shaped, minimal and explicit) — one finalized bar per input:

    {"event_id": str, "kind": "BAR",
     "payload": {"high_ticks": int, "low_ticks": int, "atr14_ticks": int | None, "bar_seq": int}}

``bar_seq`` must be strictly increasing (an equal-or-lower value refuses, mirroring F04); a
non-contiguous jump resets the local 3-bar formation window (never the already-formed zones, which
keep aging/touch-checking against every bar this module processes).

Events emitted (at most one per zone whose state actually changes on a given bar, in the order:
pre-existing zones in their formation-order first, then a newly-formed zone last):

* ``ZONE_FORMED`` — the immutable original geometry (zone bounds, gap, min_gap, ATR, origin/
  formation event ids).
* ``ZONE_TOUCHED`` — the new remaining range plus ``filled_delta_ticks`` (a partial, non-terminal
  shrink).
* ``ZONE_FULLY_FILLED`` — terminal; the closing ``filled_delta_ticks`` plus the (now equal,
  zero-width) ``remaining_low_ticks``/``remaining_high_ticks``.
* ``ZONE_EXPIRED`` — terminal; the remaining range still open at expiry.
* A ``NAMED_ABSTENTION`` (``F10_NO_ATR``) when a raw gap candidate cannot be evaluated for want of
  ATR.

Mirror law: ``C -> -C``, up <-> down, high <-> low, bullish <-> bearish, LONG <-> SHORT — proven
algebraically by test.
"""

from __future__ import annotations

from ..transition import Envelope, Params, Quality, State, TransitionResult, require
from . import common

FORMULA_F10 = "F10"

PARAM_MIN_GAP_RULE = "fvg_min_gap_rule"
PARAM_ZONE_TTL_BARS = "zone_ttl_bars"

KIND_BULLISH = "bullish"
KIND_BEARISH = "bearish"

STATE_FORMED = "FORMED"
STATE_PARTIALLY_FILLED = "PARTIALLY_FILLED"
STATE_FULLY_FILLED = "FULLY_FILLED"
STATE_EXPIRED = "EXPIRED"
_TERMINAL_STATES = (STATE_FULLY_FILLED, STATE_EXPIRED)

ZONE_FORMED = "ZONE_FORMED"
ZONE_TOUCHED = "ZONE_TOUCHED"
ZONE_FULLY_FILLED = "ZONE_FULLY_FILLED"
ZONE_EXPIRED = "ZONE_EXPIRED"


def _event_identity(envelope: Envelope) -> str:
    event_id = envelope.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        raise common.StructureLawError("envelope event_id must be a non-empty string")
    return event_id


def _bar_payload(envelope: Envelope) -> dict:
    if envelope.get("kind") != "BAR":
        raise common.StructureLawError(
            f"{FORMULA_F10} consumes BAR envelopes only, got {envelope.get('kind')!r}")
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise common.StructureLawError(f"{FORMULA_F10} envelope payload must be an object")
    return payload


def _new_zone(
    kind: str, zone_low: int, zone_high: int, gap_ticks: int, min_gap_ticks: int, atr: int,
    origin_event_ids: list[str], formation_event_id: str,
) -> dict:
    return {
        "zone_id": f"fvg_{formation_event_id}",
        "kind": kind,
        "direction": common.LONG if kind == KIND_BULLISH else common.SHORT,
        "zone_low_ticks": zone_low,
        "zone_high_ticks": zone_high,
        "gap_ticks": gap_ticks,
        "min_gap_ticks": min_gap_ticks,
        "atr14_ticks": atr,
        "remaining_low_ticks": zone_low,
        "remaining_high_ticks": zone_high,
        "state": STATE_FORMED,
        "bars_since_formation": 0,
        "origin_event_ids": list(origin_event_ids),
        "formation_event_id": formation_event_id,
    }


def _formation_candidate(bar_a: dict, high: int, low: int) -> tuple[str, int, int, int] | None:
    """``bar_a`` is bar ``i-2``; ``high``/``low`` are the current (bar ``i``) range."""
    if low > bar_a["high_ticks"]:
        return KIND_BULLISH, bar_a["high_ticks"], low, low - bar_a["high_ticks"]
    if high < bar_a["low_ticks"]:
        return KIND_BEARISH, high, bar_a["low_ticks"], bar_a["low_ticks"] - high
    return None


def _apply_touch(zone: dict, bar_high: int, bar_low: int) -> tuple[dict | None, int]:
    """Overlap-shrink the zone's remaining range against one bar's range.

    Returns ``(updated_zone, filled_delta_ticks)`` when the remaining range strictly shrank, else
    ``(None, 0)``. Never widens; never crosses past the fixed far edge.
    """
    remaining_low = zone["remaining_low_ticks"]
    remaining_high = zone["remaining_high_ticks"]
    if remaining_low >= remaining_high:
        return None, 0  # already zero-width; defensive (terminal zones never reach here)
    if zone["kind"] == KIND_BULLISH:
        if bar_high < remaining_low or bar_low > remaining_high:
            return None, 0
        new_high = max(remaining_low, min(remaining_high, bar_low))
        if new_high == remaining_high:
            return None, 0
        return dict(zone, remaining_high_ticks=new_high), remaining_high - new_high
    if bar_low > remaining_high or bar_high < remaining_low:
        return None, 0
    new_low = min(remaining_high, max(remaining_low, bar_high))
    if new_low == remaining_low:
        return None, 0
    return dict(zone, remaining_low_ticks=new_low), new_low - remaining_low


def _formed_event(zone: dict) -> dict:
    return {
        "event_kind": ZONE_FORMED, "formula": FORMULA_F10,
        "zone_id": zone["zone_id"], "kind": zone["kind"], "direction": zone["direction"],
        "zone_low_ticks": zone["zone_low_ticks"], "zone_high_ticks": zone["zone_high_ticks"],
        "gap_ticks": zone["gap_ticks"], "min_gap_ticks": zone["min_gap_ticks"],
        "atr14_ticks": zone["atr14_ticks"],
        "origin_event_ids": list(zone["origin_event_ids"]),
        "formation_event_id": zone["formation_event_id"],
    }


def _touched_event(zone: dict, touched_by_event_id: str, delta: int) -> dict:
    return {
        "event_kind": ZONE_TOUCHED, "formula": FORMULA_F10, "zone_id": zone["zone_id"],
        "touched_by_event_id": touched_by_event_id,
        "remaining_low_ticks": zone["remaining_low_ticks"],
        "remaining_high_ticks": zone["remaining_high_ticks"],
        "filled_delta_ticks": delta,
        "bars_since_formation": zone["bars_since_formation"],
    }


def _fully_filled_event(zone: dict, touched_by_event_id: str, delta: int) -> dict:
    return {
        "event_kind": ZONE_FULLY_FILLED, "formula": FORMULA_F10, "zone_id": zone["zone_id"],
        "touched_by_event_id": touched_by_event_id,
        "remaining_low_ticks": zone["remaining_low_ticks"],
        "remaining_high_ticks": zone["remaining_high_ticks"],
        "filled_delta_ticks": delta,
        "bars_since_formation": zone["bars_since_formation"],
    }


def _expired_event(zone: dict, expired_at_event_id: str) -> dict:
    return {
        "event_kind": ZONE_EXPIRED, "formula": FORMULA_F10, "zone_id": zone["zone_id"],
        "expired_at_event_id": expired_at_event_id,
        "bars_since_formation": zone["bars_since_formation"],
        "remaining_low_ticks": zone["remaining_low_ticks"],
        "remaining_high_ticks": zone["remaining_high_ticks"],
    }


def _touch_or_expire(zone: dict, ttl: int, bar_high: int, bar_low: int, event_id: str
                      ) -> tuple[dict, dict | None]:
    """Age one non-terminal zone against the current bar; terminal precedence before touch."""
    age = zone["bars_since_formation"] + 1
    if age >= ttl:
        expired = dict(zone, state=STATE_EXPIRED, bars_since_formation=age)
        return expired, _expired_event(expired, event_id)
    touched, delta = _apply_touch(zone, bar_high, bar_low)
    if touched is None:
        return dict(zone, bars_since_formation=age), None
    fully = touched["remaining_low_ticks"] == touched["remaining_high_ticks"]
    touched = dict(
        touched, bars_since_formation=age,
        state=STATE_FULLY_FILLED if fully else STATE_PARTIALLY_FILLED)
    event = (_fully_filled_event(touched, event_id, delta) if fully
             else _touched_event(touched, event_id, delta))
    return touched, event


class FvgZoneRegistry:
    """F10 — three-bar fair-value gap zones with a bar-count TTL and a shrinking-fill lifecycle
    (GV-009). See the module docstring for the full geometry, TTL, fill, and same-bar-precedence
    laws.
    """

    def initial_state(self) -> State:
        return {"last_event_id": None, "last_bar_seq": None, "recent": [], "zones": []}

    def transition(
        self, state: State, envelope: Envelope, params: Params, quality: Quality
    ) -> TransitionResult:
        rule = require(params, PARAM_MIN_GAP_RULE)
        if rule != common.DECLARED_BOS_CLOSE_BUFFER:
            raise common.StructureLawError(
                f"F10 admits only the declared PAR-044 rule "
                f"{common.DECLARED_BOS_CLOSE_BUFFER!r}, got {rule!r}")
        ttl = common.require_int(require(params, PARAM_ZONE_TTL_BARS), PARAM_ZONE_TTL_BARS)
        if ttl <= 0:
            raise common.StructureLawError("zone_ttl_bars must be a positive integer (PAR-051)")
        event_id = _event_identity(envelope)
        if event_id == state.get("last_event_id"):
            return TransitionResult(state=state)
        payload = _bar_payload(envelope)
        high = common.require_int(payload.get("high_ticks"), "high_ticks")
        low = common.require_int(payload.get("low_ticks"), "low_ticks")
        if low > high:
            raise common.StructureLawError("bar low_ticks exceeds high_ticks")
        atr = payload.get("atr14_ticks")
        bar_seq = common.require_int(payload.get("bar_seq"), "bar_seq")

        last_seq = state.get("last_bar_seq")
        if last_seq is not None and bar_seq <= last_seq:
            raise common.StructureLawError(
                f"bar_seq must be strictly increasing: got {bar_seq} after {last_seq}")
        gapped = last_seq is not None and bar_seq != last_seq + 1
        recent = [] if gapped else [dict(entry) for entry in state["recent"]]

        events: tuple[dict, ...] = ()
        zones: list[dict] = []
        for zone in (dict(z) for z in state["zones"]):
            if zone["state"] in _TERMINAL_STATES:
                zones.append(zone)
                continue
            updated, event = _touch_or_expire(zone, ttl, high, low, event_id)
            zones.append(updated)
            if event is not None:
                events += (event,)

        if len(recent) == 2:
            candidate = _formation_candidate(recent[0], high, low)
            if candidate is not None:
                kind, zone_low, zone_high, gap_ticks = candidate
                if atr is None:
                    events += (common.abstention(
                        "F10_NO_ATR", formula=FORMULA_F10,
                        detail="a raw gap candidate exists but causal ATR14 is null; the "
                               "PAR-044 minimum-gap threshold cannot be evaluated",
                        refs={"event_id": event_id}),)
                else:
                    atr_ticks = common.require_int(atr, "atr14_ticks")
                    min_gap = common.evaluate_declared_rational(rule, atr_ticks)
                    if gap_ticks >= min_gap:
                        zone = _new_zone(
                            kind, zone_low, zone_high, gap_ticks, min_gap, atr_ticks,
                            origin_event_ids=[recent[0]["event_id"], recent[1]["event_id"],
                                               event_id],
                            formation_event_id=event_id)
                        events += (_formed_event(zone),)
                        touched, delta = _apply_touch(zone, high, low)
                        if touched is not None:
                            fully = (touched["remaining_low_ticks"]
                                     == touched["remaining_high_ticks"])
                            touched = dict(
                                touched,
                                state=STATE_FULLY_FILLED if fully else STATE_PARTIALLY_FILLED)
                            events += ((_fully_filled_event(touched, event_id, delta) if fully
                                        else _touched_event(touched, event_id, delta)),)
                            zone = touched
                        zones.append(zone)
                    # else: a real, positive gap below the ratified floor — checked and
                    # rejected, silent (mirrors F04's tie-rejection / F06's out-of-tolerance).
            # else: no raw geometric gap at all — silent (not a candidate).

        recent = (recent + [{"event_id": event_id, "high_ticks": high, "low_ticks": low}])[-2:]
        return TransitionResult(
            state={
                "last_event_id": event_id, "last_bar_seq": bar_seq,
                "recent": recent, "zones": zones,
            },
            events=events)
