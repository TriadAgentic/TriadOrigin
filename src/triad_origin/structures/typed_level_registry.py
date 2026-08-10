"""Typed level machines — F03 directional-change swing, F04 closed fractal pivot, F06 anchored
equal-level cluster (b03 grounding rows; golden vectors GV-005 / GV-006 / GV-007).

Every machine is a pure :class:`triad_origin.transition.DeterministicMachine` over E01-owned
FINALIZED inputs — ORIGIN consumes and validates bars, it never aggregates trades into bars and
never authors session levels. Exact integer ticks only (``common.require_int``; bool is not an
int). Every semantic parameter arrives via ``transition.require`` — no code default, ever. The
declared rational rules (PAR-036 for F03, PAR-041 for F06) evaluate ONLY through
``common.evaluate_declared_rational`` with the exact declared byte-string, which each machine
takes as a required parameter and refuses otherwise. A missing/warm-up/unratified dependency
emits ``common.abstention`` — a NAMED event, never a silent null and never a fabricated value.
Thresholds are inclusive (PAR-009): ``>=`` / ``<=`` pass on equality.

Input envelope shapes (market_state.v2-shaped, minimal and explicit):

* F03 BAR event (finalized bar + its causal F02 ATR, supplied by the caller)::

      {"event_id": str, "kind": "BAR",
       "payload": {"high_ticks": int, "low_ticks": int, "atr14_ticks": int | None}}

* F04 BAR event (finalized bar + monotone finalized-bar sequence for gap detection)::

      {"event_id": str, "kind": "BAR",
       "payload": {"high_ticks": int, "low_ticks": int, "bar_seq": int}}

* F06 PIVOT event (a confirmed typed pivot + the causal ATR current at its confirmation)::

      {"event_id": str, "kind": "PIVOT",
       "payload": {"pivot_kind": "pivot_high" | "pivot_low", "level_ticks": int,
                   "atr14_ticks": int | None}}

F03 confirmation is a LATER-bar fact — formation and confirmation never collapse onto one bar
(RC2 retained law ``confirm high when later L<=H_x-delta_x``; availability ``confirmation ... is
the later reversal bar``; the RC3 errata scope is only "remove the undeclared reversal_bps/k_vol
terms" and does not repeal "later"). In a leg the reversal is checked against the extreme frozen
from PRIOR bars BEFORE this bar's own new extreme is admitted (check-then-freeze): a leg bar that
sets a strictly better one-sided provisional extreme therefore holds and can never confirm on its
own bar (``origin_event_id != confirmed_by_event_id`` always). In the two-sided SEED phase the
freeze happens first (a strictly better extreme re-freezes level + delta + origin; an equal
extreme does not re-freeze), then BOTH reversals are checked: a bar on which both confirm is an
ambiguous boundary that emits the named abstention ``F03_AMBIGUOUS_SEED_REVERSAL`` and re-seeds
from that bar — never a side-preferring guess, which would break the LONG/SHORT mirror law. The
seed cannot collapse formation onto one bar either: a same-bar re-frozen extreme wide enough to
reverse necessarily co-triggers the opposite reversal and abstains. (The within-bar order reading
is a disposition-register item — see ``docs/plan/09_OPEN_QUESTIONS.md`` — not a silent code
choice.)

F04 publishes only when the second right bar finalizes (delayed benchmark, never early); a tie
on either side rejects (strict unique extreme); an incomplete right window yields no pivot
(silent non-emission per the formula row); a detected ``bar_seq`` gap resets the window cleanly.

F06 is fail-closed on RC3-PAR-STRUCT-001: while ``equal_level_max_span`` is the
``common.NOT_RATIFIED`` sentinel every pivot input yields the named abstention
``F06_UNAVAILABLE_MAX_SPAN_NOT_RATIFIED`` and no cluster state mutates (SAFE_HOLD). The anchor
is the immutable first member — it never drifts, and transitive neighbor chaining is impossible
because distance is always measured from the anchor. When several clusters accept, the winner is
minimal anchor distance, then earliest cluster origin (RC2 tie rule). A cluster emits its
equal-level atom EXACTLY ONCE, at the ``min_touches``-th member; a later accepted member refines
the checkpointed member set (``member_levels``/``member_event_ids``) but emits no further event —
in v1 a post-publication member-set revision is visible only via checkpoint state. Whether such a
revision must also emit a TYPED_LEVEL is a pending RC3-PAR-STRUCT-001 emission disposition
(``docs/plan/09_OPEN_QUESTIONS.md``), not a silent code choice.
"""

from __future__ import annotations

from ..transition import Envelope, Params, Quality, State, TransitionResult, require
from . import common

FORMULA_F03 = "F03"
FORMULA_F04 = "F04"
FORMULA_F06 = "F06"

PARAM_DC_REVERSAL_RULE = "dc_reversal_rule"
PARAM_FRACTAL_LEFT = "fractal_left_bars"
PARAM_FRACTAL_RIGHT = "fractal_right_bars"
PARAM_EQUAL_LEVEL_TOLERANCE_RULE = "equal_level_tolerance_rule"
PARAM_EQUAL_LEVEL_MIN_TOUCHES = "equal_level_min_touches"
PARAM_EQUAL_LEVEL_MAX_SPAN = "equal_level_max_span"

TYPED_LEVEL = "TYPED_LEVEL"
SWING_HIGH = "swing_high"
SWING_LOW = "swing_low"
PIVOT_HIGH = "pivot_high"
PIVOT_LOW = "pivot_low"
EQUAL_LEVEL_HIGH = "equal_level_high"
EQUAL_LEVEL_LOW = "equal_level_low"

_SEED = "SEED"
_UP = "UP"
_DOWN = "DOWN"


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


def _typed_payload(envelope: Envelope, kind: str, formula: str) -> tuple[str, dict]:
    event_id = _event_identity(envelope)
    if envelope.get("kind") != kind:
        raise common.StructureLawError(
            f"{formula} consumes {kind} envelopes only, got {envelope.get('kind')!r}")
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise common.StructureLawError(f"{formula} envelope payload must be an object")
    return event_id, payload


def _bar_range(payload: dict) -> tuple[int, int]:
    high = common.require_int(payload.get("high_ticks"), "high_ticks")
    low = common.require_int(payload.get("low_ticks"), "low_ticks")
    if low > high:
        raise common.StructureLawError("bar low_ticks exceeds high_ticks")
    return high, low


def _frozen(extreme_ticks: int, delta_ticks: int, origin_event_id: str) -> dict:
    return {
        "extreme_ticks": extreme_ticks,
        "delta_ticks": delta_ticks,
        "origin_event_id": origin_event_id,
    }


class DirectionalChangeSwing:
    """F03 — directional-change swing over finalized bars carrying causal ATR14 (GV-005).

    ``delta_ticks = evaluate_declared_rational(DECLARED_DC_REVERSAL, atr)`` with the declared
    string arriving as the required parameter ``dc_reversal_rule`` (any other string refuses).
    Freeze at each provisional extreme; a reversal difference ``>= delta`` (equality passes)
    confirms the swing and flips the leg. Null ATR abstains (``F03_NO_ATR``); no state mutates.
    """

    def initial_state(self) -> State:
        return {"last_event_id": None, "mode": _SEED, "prov_high": None, "prov_low": None}

    def transition(
        self, state: State, envelope: Envelope, params: Params, quality: Quality
    ) -> TransitionResult:
        rule = require(params, PARAM_DC_REVERSAL_RULE)
        if rule != common.DECLARED_DC_REVERSAL:
            raise common.StructureLawError(
                f"F03 admits only the declared PAR-036 rule {common.DECLARED_DC_REVERSAL!r}, "
                f"got {rule!r}")
        event_id, payload = _typed_payload(envelope, "BAR", FORMULA_F03)
        if event_id == state.get("last_event_id"):
            return TransitionResult(state=state)
        atr = payload.get("atr14_ticks")
        if atr is None:
            return TransitionResult(state=state, events=(common.abstention(
                "F03_NO_ATR", formula=FORMULA_F03,
                detail="causal ATR14 is null (warm-up/gap); no swing evaluation",
                refs={"event_id": event_id}),))
        high, low = _bar_range(payload)
        delta = common.evaluate_declared_rational(rule, common.require_int(atr, "atr14_ticks"))
        if state["mode"] == _SEED:
            return self._seed(state, event_id, high, low, delta)
        return self._leg(state, event_id, high, low, delta)

    def _seed(self, state: State, event_id: str, high: int, low: int, delta: int
              ) -> TransitionResult:
        prov_high, prov_low = state["prov_high"], state["prov_low"]
        if prov_high is None:
            return TransitionResult(state=self._seed_state(event_id, high, low, delta))
        if high > prov_high["extreme_ticks"]:
            prov_high = _frozen(high, delta, event_id)
        if low < prov_low["extreme_ticks"]:
            prov_low = _frozen(low, delta, event_id)
        high_reversal = prov_high["extreme_ticks"] - low >= prov_high["delta_ticks"]
        low_reversal = high - prov_low["extreme_ticks"] >= prov_low["delta_ticks"]
        if high_reversal and low_reversal:
            return TransitionResult(
                state=self._seed_state(event_id, high, low, delta),
                events=(common.abstention(
                    "F03_AMBIGUOUS_SEED_REVERSAL", formula=FORMULA_F03,
                    detail="both seed reversals confirm on one bar; re-seeding from this bar",
                    refs={"event_id": event_id}),))
        if high_reversal:
            return self._confirm(SWING_HIGH, prov_high, event_id, low, delta)
        if low_reversal:
            return self._confirm(SWING_LOW, prov_low, event_id, high, delta)
        return TransitionResult(state={
            "last_event_id": event_id, "mode": _SEED,
            "prov_high": prov_high, "prov_low": prov_low})

    def _leg(self, state: State, event_id: str, high: int, low: int, delta: int
             ) -> TransitionResult:
        # Check-then-freeze: the reversal is evaluated against the extreme frozen on PRIOR bars
        # BEFORE this bar's own new extreme is admitted, so confirmation is always a later-bar
        # fact (RC2 "confirm high when later L<=H_x-delta_x") and a leg bar that sets a new
        # one-sided provisional extreme never confirms on its own bar.
        if state["mode"] == _UP:
            prov = state["prov_high"]
            if prov["extreme_ticks"] - low >= prov["delta_ticks"]:
                return self._confirm(SWING_HIGH, prov, event_id, low, delta)
            if high > prov["extreme_ticks"]:
                prov = _frozen(high, delta, event_id)
            return TransitionResult(state={
                "last_event_id": event_id, "mode": _UP, "prov_high": prov, "prov_low": None})
        prov = state["prov_low"]
        if high - prov["extreme_ticks"] >= prov["delta_ticks"]:
            return self._confirm(SWING_LOW, prov, event_id, high, delta)
        if low < prov["extreme_ticks"]:
            prov = _frozen(low, delta, event_id)
        return TransitionResult(state={
            "last_event_id": event_id, "mode": _DOWN, "prov_high": None, "prov_low": prov})

    def _confirm(self, kind: str, prov: dict, event_id: str, opposite_extreme: int, delta: int
                 ) -> TransitionResult:
        event = {
            "event_kind": TYPED_LEVEL,
            "formula": FORMULA_F03,
            "kind": kind,
            "direction": common.LONG if kind == SWING_HIGH else common.SHORT,
            "level_ticks": prov["extreme_ticks"],
            "delta_ticks": prov["delta_ticks"],
            "origin_event_id": prov["origin_event_id"],
            "confirmed_by_event_id": event_id,
        }
        next_leg = _frozen(opposite_extreme, delta, event_id)
        if kind == SWING_HIGH:
            state = {"last_event_id": event_id, "mode": _DOWN,
                     "prov_high": None, "prov_low": next_leg}
        else:
            state = {"last_event_id": event_id, "mode": _UP,
                     "prov_high": next_leg, "prov_low": None}
        return TransitionResult(state=state, events=(event,))

    @staticmethod
    def _seed_state(event_id: str, high: int, low: int, delta: int) -> State:
        return {"last_event_id": event_id, "mode": _SEED,
                "prov_high": _frozen(high, delta, event_id),
                "prov_low": _frozen(low, delta, event_id)}


class FractalPivot:
    """F04 — closed L/R fractal pivot benchmark over finalized bars (GV-006).

    ``pivot_high`` at the candidate iff its high is the STRICT unique maximum over the closed
    window (any tie rejects); mirror for ``pivot_low``. Publishes only when the second right bar
    finalizes. An incomplete right window yields no pivot (silent non-emission per the formula
    row); a detected ``bar_seq`` gap resets the window cleanly; out-of-order input refuses.
    """

    def initial_state(self) -> State:
        return {"last_event_id": None, "window": []}

    def transition(
        self, state: State, envelope: Envelope, params: Params, quality: Quality
    ) -> TransitionResult:
        left = _positive_int(require(params, PARAM_FRACTAL_LEFT), PARAM_FRACTAL_LEFT)
        right = _positive_int(require(params, PARAM_FRACTAL_RIGHT), PARAM_FRACTAL_RIGHT)
        event_id, payload = _typed_payload(envelope, "BAR", FORMULA_F04)
        if event_id == state.get("last_event_id"):
            return TransitionResult(state=state)
        seq = common.require_int(payload.get("bar_seq"), "bar_seq")
        high, low = _bar_range(payload)
        window = [dict(bar) for bar in state["window"]]
        if window:
            last_seq = window[-1]["bar_seq"]
            if seq <= last_seq:
                raise common.StructureLawError(
                    f"bar_seq must be strictly increasing: got {seq} after {last_seq}")
            if seq != last_seq + 1:
                window = []
        window.append({"event_id": event_id, "bar_seq": seq,
                       "high_ticks": high, "low_ticks": low})
        length = left + 1 + right
        events: tuple[dict, ...] = ()
        if len(window) == length:
            candidate = window[left]
            others = [bar for index, bar in enumerate(window) if index != left]
            if all(candidate["high_ticks"] > bar["high_ticks"] for bar in others):
                events += (self._pivot_event(PIVOT_HIGH, candidate, event_id),)
            if all(candidate["low_ticks"] < bar["low_ticks"] for bar in others):
                events += (self._pivot_event(PIVOT_LOW, candidate, event_id),)
            window = window[1:]
        return TransitionResult(
            state={"last_event_id": event_id, "window": window}, events=events)

    @staticmethod
    def _pivot_event(kind: str, candidate: dict, confirmed_by: str) -> dict:
        level = candidate["high_ticks"] if kind == PIVOT_HIGH else candidate["low_ticks"]
        return {
            "event_kind": TYPED_LEVEL,
            "formula": FORMULA_F04,
            "kind": kind,
            "level_ticks": level,
            "origin_event_id": candidate["event_id"],
            "origin_bar_seq": candidate["bar_seq"],
            "confirmed_by_event_id": confirmed_by,
        }


class EqualLevelCluster:
    """F06 — anchored equal-level cluster over confirmed pivot inputs (GV-007).

    Accept ``p`` iff ``|p - anchor| <= tolerance`` and ``span(members ∪ p) <= max_span`` (both
    inclusive); the anchor is the immutable first member. The cluster becomes an equal-level
    atom at the ``min_touches``-th qualifying pivot and publishes exactly once there; a later
    accepted member refines the checkpointed member set without re-emitting (v1 publish-once —
    revision emission is a pending RC3-PAR-STRUCT-001 disposition). While ``equal_level_max_span``
    is the ``NOT_RATIFIED`` sentinel (RC3-PAR-STRUCT-001) every pivot yields the named abstention
    and no cluster state mutates (SAFE_HOLD).
    """

    def initial_state(self) -> State:
        return {"last_event_id": None, "clusters": []}

    def transition(
        self, state: State, envelope: Envelope, params: Params, quality: Quality
    ) -> TransitionResult:
        rule = require(params, PARAM_EQUAL_LEVEL_TOLERANCE_RULE)
        if rule != common.DECLARED_EQUAL_LEVEL_TOLERANCE:
            raise common.StructureLawError(
                f"F06 admits only the declared PAR-041 rule "
                f"{common.DECLARED_EQUAL_LEVEL_TOLERANCE!r}, got {rule!r}")
        min_touches = _positive_int(
            require(params, PARAM_EQUAL_LEVEL_MIN_TOUCHES), PARAM_EQUAL_LEVEL_MIN_TOUCHES)
        max_span = require(params, PARAM_EQUAL_LEVEL_MAX_SPAN)
        event_id, payload = _typed_payload(envelope, "PIVOT", FORMULA_F06)
        if max_span == common.NOT_RATIFIED:
            return TransitionResult(state=state, events=(common.abstention(
                "F06_UNAVAILABLE_MAX_SPAN_NOT_RATIFIED", formula=FORMULA_F06,
                detail="RC3-PAR-STRUCT-001 EQUAL_LEVEL_MAX_SPAN is NOT_RATIFIED; "
                       "equal-level clustering holds SAFE_HOLD with zero state mutation",
                refs={"event_id": event_id, "parameter": "RC3-PAR-STRUCT-001"}),))
        if not common.is_ratified_int(max_span):
            raise common.StructureLawError(
                f"{PARAM_EQUAL_LEVEL_MAX_SPAN} must be a ratified non-negative int or "
                f"NOT_RATIFIED, got {max_span!r}")
        if event_id == state.get("last_event_id"):
            return TransitionResult(state=state)
        if any(event_id in cluster["member_event_ids"] for cluster in state["clusters"]):
            return TransitionResult(state=state)
        pivot_kind = payload.get("pivot_kind")
        if pivot_kind not in (PIVOT_HIGH, PIVOT_LOW):
            raise common.StructureLawError(
                f"F06 pivot_kind must be {PIVOT_HIGH!r} or {PIVOT_LOW!r}, got {pivot_kind!r}")
        atr = payload.get("atr14_ticks")
        if atr is None:
            return TransitionResult(state=state, events=(common.abstention(
                "F06_NO_ATR", formula=FORMULA_F06,
                detail="causal ATR14 is null on the pivot input; tolerance is unavailable",
                refs={"event_id": event_id}),))
        tolerance = common.evaluate_declared_rational(
            rule, common.require_int(atr, "atr14_ticks"))
        level = common.require_int(payload.get("level_ticks"), "level_ticks")
        clusters = [dict(cluster,
                         member_levels=list(cluster["member_levels"]),
                         member_event_ids=list(cluster["member_event_ids"]))
                    for cluster in state["clusters"]]
        accepting: list[tuple[int, int]] = []
        for index, cluster in enumerate(clusters):
            if cluster["kind"] != pivot_kind:
                continue
            distance = abs(level - cluster["anchor_ticks"])
            if distance > tolerance:
                continue
            joined = cluster["member_levels"] + [level]
            if max(joined) - min(joined) > max_span:
                continue
            accepting.append((distance, index))
        events: tuple[dict, ...] = ()
        if accepting:
            _, index = min(accepting)
            cluster = clusters[index]
            cluster["member_levels"].append(level)
            cluster["member_event_ids"].append(event_id)
            if not cluster["published"] and len(cluster["member_event_ids"]) >= min_touches:
                cluster["published"] = True
                events = ({
                    "event_kind": TYPED_LEVEL,
                    "formula": FORMULA_F06,
                    "kind": EQUAL_LEVEL_HIGH if pivot_kind == PIVOT_HIGH else EQUAL_LEVEL_LOW,
                    "anchor_ticks": cluster["anchor_ticks"],
                    "member_levels": list(cluster["member_levels"]),
                    "member_event_ids": list(cluster["member_event_ids"]),
                    "confirmed_by_event_id": event_id,
                },)
        else:
            clusters.append({"kind": pivot_kind, "anchor_ticks": level,
                             "member_levels": [level], "member_event_ids": [event_id],
                             "published": False})
        return TransitionResult(
            state={"last_event_id": event_id, "clusters": clusters}, events=events)
