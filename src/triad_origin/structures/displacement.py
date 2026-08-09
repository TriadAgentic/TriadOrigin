"""Qualified displacement — F11 earliest-bar displacement search over a fixed origin window (b03
grounding row; golden vector GV-010).

A pure :class:`triad_origin.transition.DeterministicMachine` over E01-owned FINALIZED bars — like
every ORIGIN structure it consumes and validates bars, it never aggregates trades and never
authors session levels. Exact integer ticks only (``common.require_int``; bool is not an int).
Every semantic parameter arrives via ``transition.require`` — no code default, ever. The three
declared rational rules (PAR-158 for the minimum move, PAR-046 for the body fraction, PAR-159 for
the close location) each arrive as a required parameter carrying their exact declared byte-string
and are refused otherwise; the horizon (PAR-157) is a plain positive int, not a declared-value
string. A missing/gapped/exhausted search emits ``common.abstention`` — a NAMED event, never a
silent null and never a fabricated value. Thresholds are inclusive (PAR-009): ``>=`` passes on
equality, and every ratio comparison is decided by exact-integer cross-multiplication — never a
floating division, regardless of magnitude (see the equality-boundary tests for the adversarial
proof: a naive ``float(numerator) / float(denominator)`` misrounds at large enough magnitudes and
would silently flip a fail into a pass).

**One search per origin.** An ``ORIGIN`` envelope opens a fresh search window of
``displacement_horizon`` (PAR-157, ``H``) finalized bars immediately following the origin bar; a
subsequent ``ORIGIN`` envelope always supersedes whatever search was open (a new origin is new
information). ``BAR`` envelopes carry each finalized bar ``j`` in that window, walked strictly in
order (``bar_index`` == the next expected index); a ``BAR`` that arrives while no search is open
(before the first ``ORIGIN``, after a search has already qualified/exhausted/gapped, or during a
``NO_ATR`` abstention) is a structurally harmless no-op — it advances nothing and emits nothing.

Input envelope shapes (market_state.v2-shaped, minimal and explicit):

* F11 ORIGIN event (opens a fresh search from a caller-supplied finalized origin bar)::

      {"event_id": str, "kind": "ORIGIN",
       "payload": {"origin_bar_index": int, "origin_open_ticks": int,
                   "atr14_before_origin_ticks": int | None}}

* F11 BAR event (a finalized bar within the search window, carrying its own OHLC and index for
  strict-order/gap detection)::

      {"event_id": str, "kind": "BAR",
       "payload": {"bar_index": int, "open_ticks": int, "close_ticks": int,
                   "high_ticks": int, "low_ticks": int}}

The formula, per finalized bar ``j`` in ``[origin+1, origin+H]`` (PAR-157 boundary rule: the
``H``-th later bar is included, the ``(H+1)``-th is excluded — the search never reaches it):

* ``move_j = C_j - O_origin`` (signed move from the ORIGIN bar's own open);
* ``D_ticks = evaluate_displacement_min_move(ATR14_before_origin_ticks)`` (PAR-158, computed once
  at ORIGIN time — a single fixed floor for the whole search);
* ``body_ratio_j = |C_j - O_j| / max(1, H_j - L_j) >= 13/20`` (PAR-046, cross-multiplied:
  ``|C_j-O_j|*20 >= range_j*13``);
* ``close_loc_j = (C_j - L_j) / max(1, H_j - L_j) >= 4/5`` for a bull candidate (PAR-159,
  cross-multiplied: ``(C_j-L_j)*5 >= range_j*4``); the bear mirror is
  ``(H_j-C_j)*5 >= range_j*4`` (the full-price-reflection mirror law: ``C -> -C``, ``H <-> -L``,
  ``L <-> -H`` turns the bull expression into exactly this bear expression).

Bar ``j`` qualifies LONG iff ``move_j >= D_ticks`` AND ``C_j > O_j`` AND the body-ratio conjunct
AND the bull close-location conjunct — ALL FOUR, and the mirror set (``move_j <= -D_ticks``,
``C_j < O_j``, the same body-ratio conjunct, the bear close-location conjunct) qualifies SHORT.
``D_ticks`` is always ``>= 5 > 0`` so the two move conjuncts are mutually exclusive by
construction — a bar can never qualify both directions. The EARLIEST qualifying ``j`` wins and the
search stops there; no later bar in the window is ever evaluated (GV-010: ``ATR14_before_origin =
10`` gives ``D_ticks = max(5, ceil(3*10/2)) = 15``; a move of ``14`` fails, a move of ``15``
passes — equality passes, PAR-009).

* No qualifying bar anywhere in ``[origin+1, origin+H]`` -> named abstention
  ``F11_NO_QUALIFYING_BAR``; the search closes (no state left to re-evaluate).
* A gap in the finalized bar sequence inside the search window (a ``bar_index`` that skips ahead
  of the next expected index) -> named abstention ``F11_GAP_IN_SEARCH_WINDOW``; the search closes
  immediately — it never searches across the gap, and no bar past the gap is ever examined. A
  ``bar_index`` that is NOT ahead of the next expected one (an out-of-order or repeated index) is
  a structural ordering violation and raises, mirroring F04's strictly-increasing law.
* A null/absent ``ATR14_before_origin_ticks`` at ORIGIN time -> named abstention ``F11_NO_ATR``;
  no search opens at all (a later ``BAR`` is then the harmless no-op above).

On qualification exactly one ``DISPLACEMENT_QUALIFIED`` event is emitted, carrying the origin bar
index, the qualifying bar index, the direction, the signed ``move_ticks``, ``D_ticks``, and the
observed ``body_ratio``/``close_loc`` ratios each as an exact integer ``(numerator, denominator)``
pair — never a float.
"""

from __future__ import annotations

from ..transition import Envelope, Params, Quality, State, TransitionResult, require
from . import common

FORMULA_F11 = "F11"

PARAM_DISPLACEMENT_HORIZON = "displacement_horizon"
PARAM_DISPLACEMENT_MIN_MOVE_RULE = "displacement_min_move_rule"
PARAM_BODY_FRACTION_RULE = "body_fraction_rule"
PARAM_CLOSE_LOCATION_RULE = "close_location_rule"

DISPLACEMENT_QUALIFIED = "DISPLACEMENT_QUALIFIED"

_KIND_ORIGIN = "ORIGIN"
_KIND_BAR = "BAR"


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
    if kind not in (_KIND_ORIGIN, _KIND_BAR):
        raise common.StructureLawError(
            f"F11 consumes {_KIND_ORIGIN!r} or {_KIND_BAR!r} envelopes only, got {kind!r}")
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise common.StructureLawError("F11 envelope payload must be an object")
    return payload


def _bar_geometry(payload: dict) -> tuple[int, int, int, int]:
    open_ticks = common.require_int(payload.get("open_ticks"), "open_ticks")
    close_ticks = common.require_int(payload.get("close_ticks"), "close_ticks")
    high_ticks = common.require_int(payload.get("high_ticks"), "high_ticks")
    low_ticks = common.require_int(payload.get("low_ticks"), "low_ticks")
    if low_ticks > high_ticks:
        raise common.StructureLawError("bar low_ticks exceeds high_ticks")
    return open_ticks, close_ticks, high_ticks, low_ticks


class QualifiedDisplacement:
    """F11 — earliest qualifying displacement bar over a fixed origin window (GV-010).

    ``D_ticks`` is computed once, at ORIGIN time, from
    ``common.evaluate_displacement_min_move``; every bar in the window is then checked, in
    strict order, against all four conjuncts (move, candle direction, body ratio, close
    location) for both directions — mutually exclusive by construction since ``D_ticks > 0``.
    The first bar to qualify either direction wins and the search stops; every ratio comparison
    is exact-integer cross-multiplication, never a float.
    """

    def initial_state(self) -> State:
        return {"last_event_id": None, "search": None}

    def transition(
        self, state: State, envelope: Envelope, params: Params, quality: Quality
    ) -> TransitionResult:
        horizon = _positive_int(
            require(params, PARAM_DISPLACEMENT_HORIZON), PARAM_DISPLACEMENT_HORIZON)
        min_move_rule = require(params, PARAM_DISPLACEMENT_MIN_MOVE_RULE)
        if min_move_rule != common.DECLARED_DISPLACEMENT_MIN_MOVE:
            raise common.StructureLawError(
                f"F11 admits only the declared PAR-158 rule "
                f"{common.DECLARED_DISPLACEMENT_MIN_MOVE!r}, got {min_move_rule!r}")
        body_rule = require(params, PARAM_BODY_FRACTION_RULE)
        if body_rule != common.DECLARED_DISPLACEMENT_BODY_FRACTION:
            raise common.StructureLawError(
                f"F11 admits only the declared PAR-046 rule "
                f"{common.DECLARED_DISPLACEMENT_BODY_FRACTION!r}, got {body_rule!r}")
        body_num, body_den = common.declared_fraction(body_rule)
        close_loc_rule = require(params, PARAM_CLOSE_LOCATION_RULE)
        if close_loc_rule != common.DECLARED_DISPLACEMENT_CLOSE_LOCATION:
            raise common.StructureLawError(
                f"F11 admits only the declared PAR-159 rule "
                f"{common.DECLARED_DISPLACEMENT_CLOSE_LOCATION!r}, got {close_loc_rule!r}")
        close_num, close_den = common.declared_fraction(close_loc_rule)

        event_id = _event_identity(envelope)
        if event_id == state.get("last_event_id"):
            return TransitionResult(state=state)
        payload = _payload(envelope)

        if envelope.get("kind") == _KIND_ORIGIN:
            return self._origin(state, event_id, payload, horizon)
        return self._bar(
            state, event_id, payload, body_num, body_den, close_num, close_den)

    def _origin(self, state: State, event_id: str, payload: dict, horizon: int
                ) -> TransitionResult:
        origin_bar_index = common.require_int(
            payload.get("origin_bar_index"), "origin_bar_index")
        origin_open_ticks = common.require_int(
            payload.get("origin_open_ticks"), "origin_open_ticks")
        atr = payload.get("atr14_before_origin_ticks")
        if atr is None:
            return TransitionResult(state={"last_event_id": event_id, "search": None},
                                     events=(common.abstention(
                "F11_NO_ATR", formula=FORMULA_F11,
                detail="causal ATR14_before_origin is null (warm-up/gap); no displacement "
                       "search opens for this origin",
                refs={"event_id": event_id, "origin_bar_index": origin_bar_index}),))
        d_ticks = common.evaluate_displacement_min_move(
            common.require_int(atr, "atr14_before_origin_ticks"))
        search = {
            "origin_event_id": event_id,
            "origin_bar_index": origin_bar_index,
            "origin_open_ticks": origin_open_ticks,
            "d_ticks": d_ticks,
            "horizon": horizon,
            "next_bar_index": origin_bar_index + 1,
            "examined": 0,
        }
        return TransitionResult(state={"last_event_id": event_id, "search": search})

    def _bar(
        self, state: State, event_id: str, payload: dict,
        body_num: int, body_den: int, close_num: int, close_den: int,
    ) -> TransitionResult:
        search = state.get("search")
        if search is None:
            return TransitionResult(state={"last_event_id": event_id, "search": None})
        search = dict(search)
        bar_index = common.require_int(payload.get("bar_index"), "bar_index")
        expected = search["next_bar_index"]
        if bar_index < expected:
            raise common.StructureLawError(
                f"F11 bar_index must not precede the expected search index: "
                f"got {bar_index}, expected {expected}")
        if bar_index > expected:
            return TransitionResult(state={"last_event_id": event_id, "search": None},
                                     events=(common.abstention(
                "F11_GAP_IN_SEARCH_WINDOW", formula=FORMULA_F11,
                detail="a finalized bar was skipped inside the search window; the search "
                       "never crosses a gap and closes without a qualifying result",
                refs={"event_id": event_id, "expected_bar_index": expected,
                      "got_bar_index": bar_index}),))

        open_ticks, close_ticks, high_ticks, low_ticks = _bar_geometry(payload)
        move_ticks = close_ticks - search["origin_open_ticks"]
        d_ticks = search["d_ticks"]
        range_ticks = max(1, high_ticks - low_ticks)
        body_ok = abs(close_ticks - open_ticks) * body_den >= range_ticks * body_num
        long_close_loc_ok = (close_ticks - low_ticks) * close_den >= range_ticks * close_num
        short_close_loc_ok = (high_ticks - close_ticks) * close_den >= range_ticks * close_num
        qualifies_long = (
            move_ticks >= d_ticks and close_ticks > open_ticks and body_ok
            and long_close_loc_ok)
        qualifies_short = (
            move_ticks <= -d_ticks and close_ticks < open_ticks and body_ok
            and short_close_loc_ok)

        if qualifies_long or qualifies_short:
            direction = common.LONG if qualifies_long else common.SHORT
            close_loc_numerator = (
                (close_ticks - low_ticks) if qualifies_long else (high_ticks - close_ticks))
            event = {
                "event_kind": DISPLACEMENT_QUALIFIED,
                "formula": FORMULA_F11,
                "direction": direction,
                "origin_bar_index": search["origin_bar_index"],
                "qualifying_bar_index": bar_index,
                "move_ticks": move_ticks,
                "d_ticks": d_ticks,
                "body_ratio_numerator": abs(close_ticks - open_ticks),
                "body_ratio_denominator": range_ticks,
                "close_loc_numerator": close_loc_numerator,
                "close_loc_denominator": range_ticks,
                "origin_event_id": search["origin_event_id"],
                "confirmed_by_event_id": event_id,
            }
            return TransitionResult(
                state={"last_event_id": event_id, "search": None}, events=(event,))

        examined = search["examined"] + 1
        if examined >= search["horizon"]:
            return TransitionResult(state={"last_event_id": event_id, "search": None},
                                     events=(common.abstention(
                "F11_NO_QUALIFYING_BAR", formula=FORMULA_F11,
                detail="no bar in the search window satisfied all four qualification "
                       "conjuncts in either direction",
                refs={"event_id": event_id,
                      "origin_bar_index": search["origin_bar_index"],
                      "horizon": search["horizon"]}),))
        search["examined"] = examined
        search["next_bar_index"] = expected + 1
        return TransitionResult(state={"last_event_id": event_id, "search": search})
