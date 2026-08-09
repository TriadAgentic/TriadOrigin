"""F13 — frozen-level excursion and timed reclaim (golden vector GV-011).

After a frozen level is EXCURSED (a finalized bar's high/low crosses beyond the level by at
least PAR-048 ``EXCURSION_MIN``, the same declared rule byte-string as F09's break buffer — see
:data:`triad_origin.structures.common.DECLARED_BOS_CLOSE_BUFFER`), the machine watches a bounded
horizon of ordinals 0..PAR-049 (``RECLAIM_HORIZON`` = 3) for a **reclaim**: the
FIRST qualifying finalized close (beyond the level by the reclaim buffer, PAR-164, the same
declared rule) moves the state to ``RECLAIM_PENDING``; the SECOND CONSECUTIVE qualifying close
(``PAR-165 RECLAIM_HOLD_BARS`` = 2, a plain required int — not a declared-rational rule) confirms
``CONFIRMED``. Any non-qualifying close in between resets the hold count to zero (the pending
state is lost, not merely paused — a fresh ``RECLAIM_PENDING`` must restart from a new qualifying
close). An ordinal that falls after the horizon elapses without confirmation is
``RECLAIM_EXPIRED`` (terminal, GV-011's ``ordinal3 outside horizon`` boundary).

GV-011: qualifying finalized closes at ordinals 1 and 2 after excursion -> ordinal 1
``RECLAIM_PENDING``, ordinal 2 ``CONFIRMED`` (consecutive); a nonqualifying close at any ordinal
resets the hold count to zero; an ordinal outside ``[0, RECLAIM_HORIZON]`` never confirms
(``RECLAIM_EXPIRED`` once the horizon closes with no confirmation).

Every semantic parameter arrives via :func:`triad_origin.transition.require` — no code default,
ever. Thresholds are inclusive (PAR-009). A missing/null causal ATR at excursion-candidate time
emits the named abstention ``F13_NO_ATR`` (no excursion is recorded). An unmet dependency, an
already-excursed level receiving a second excursion input, or a bar arriving after a terminal
state is refused/ignored, never silently re-applied.

Input envelope shapes (minimal, explicit)::

    # Candidate excursion bar (finalized high/low + causal ATR).
    {"event_id": str, "kind": "EXCURSION_CANDIDATE",
     "payload": {"level_id": str, "level_ticks": int, "direction": "LONG" | "SHORT",
                 "high_ticks": int, "low_ticks": int, "atr14_ticks": int | None}}

    # Post-excursion finalized close, tagged with its ordinal relative to the excursion bar
    # (ordinal 0 = the excursion bar's own close; 1, 2, ... = subsequent finalized bars).
    {"event_id": str, "kind": "RECLAIM_OBSERVATION",
     "payload": {"level_id": str, "ordinal": int, "close_ticks": int, "atr14_ticks": int}}

``direction`` names the LEVEL's own side: a ``LONG`` level excurses on a high beyond the level
(price moved above a support/demand level) and reclaims on a close back below it (buffer beyond,
toward the level's protected side); ``SHORT`` mirrors exactly (excursion below via low, reclaim
close back above). This is the algebraic mirror the LONG/SHORT test proves via full price
reflection (``O'=-O, H'=-L, L'=-H, C'=-C``, ``level' = -level``, direction swapped).
"""

from __future__ import annotations

from ..transition import Envelope, Params, Quality, State, TransitionResult, require
from . import common
from .common import DECLARED_BOS_CLOSE_BUFFER, LONG, SHORT, StructureLawError, abstention

FORMULA_F13 = "F13"

PARAM_EXCURSION_MIN_RULE = "excursion_min_rule"
PARAM_RECLAIM_HORIZON = "reclaim_horizon"
PARAM_RECLAIM_CLOSE_BUFFER_RULE = "reclaim_close_buffer_rule"
PARAM_RECLAIM_HOLD_BARS = "reclaim_hold_bars"

RECLAIM_STATE_CHANGED = "RECLAIM_STATE_CHANGED"

EXCURSED = "EXCURSED"
RECLAIM_PENDING = "RECLAIM_PENDING"
CONFIRMED = "CONFIRMED"
RECLAIM_EXPIRED = "RECLAIM_EXPIRED"

_TERMINAL = (CONFIRMED, RECLAIM_EXPIRED)


def _excurses(direction: str, level_ticks: int, high: int, low: int, min_excursion: int) -> bool:
    if direction == LONG:
        return high >= level_ticks + min_excursion
    return low <= level_ticks - min_excursion


def _reclaims(direction: str, level_ticks: int, close: int, buffer: int) -> bool:
    # Reclaim moves back TOWARD the level's protected side, beyond the level by the buffer.
    if direction == LONG:
        return close <= level_ticks - buffer
    return close >= level_ticks + buffer


class ExcursionReclaimTracker:
    """F13 — excursion -> timed reclaim (:class:`triad_origin.transition.DeterministicMachine`)."""

    def initial_state(self) -> State:
        return {"levels": {}}

    def transition(
        self, state: State, envelope: Envelope, params: Params, quality: Quality
    ) -> TransitionResult:
        excursion_rule = require(params, PARAM_EXCURSION_MIN_RULE)
        reclaim_rule = require(params, PARAM_RECLAIM_CLOSE_BUFFER_RULE)
        horizon = common.require_int(
            require(params, PARAM_RECLAIM_HORIZON), PARAM_RECLAIM_HORIZON)
        hold_bars = common.require_int(
            require(params, PARAM_RECLAIM_HOLD_BARS), PARAM_RECLAIM_HOLD_BARS)
        if excursion_rule != DECLARED_BOS_CLOSE_BUFFER:
            raise StructureLawError(
                f"undeclared excursion_min rule: {excursion_rule!r} (PAR-048)")
        if reclaim_rule != DECLARED_BOS_CLOSE_BUFFER:
            raise StructureLawError(
                f"undeclared reclaim_close_buffer rule: {reclaim_rule!r} (PAR-164)")
        if horizon < 0 or hold_bars <= 0:
            raise StructureLawError("reclaim_horizon must be >= 0 and hold_bars must be > 0")

        kind = envelope.get("kind")
        payload = envelope.get("payload", {})
        levels = dict(state["levels"])

        if kind == "EXCURSION_CANDIDATE":
            level_id = payload["level_id"]
            if level_id in levels:
                return TransitionResult(state)  # already excursed; ignore re-excursion
            direction = common.require_direction(payload["direction"])
            level_ticks = common.require_int(payload["level_ticks"], "level_ticks")
            high, low = (common.require_int(payload["high_ticks"], "high_ticks"),
                        common.require_int(payload["low_ticks"], "low_ticks"))
            atr = payload.get("atr14_ticks")
            if atr is None:
                event = abstention(
                    "F13_NO_ATR", formula=FORMULA_F13,
                    detail="no causal ATR at excursion-candidate time",
                    refs={"level_id": level_id})
                return TransitionResult(state, (event,))
            min_excursion = common.evaluate_declared_rational(excursion_rule, atr)
            if not _excurses(direction, level_ticks, high, low, min_excursion):
                return TransitionResult(state)  # no excursion this bar; silent non-emission
            levels[level_id] = {
                "direction": direction, "level_ticks": level_ticks,
                "reclaim_state": EXCURSED, "hold_count": 0,
            }
            return TransitionResult({"levels": levels})

        if kind == "RECLAIM_OBSERVATION":
            level_id = payload["level_id"]
            row = levels.get(level_id)
            if row is None or row["reclaim_state"] in _TERMINAL:
                return TransitionResult(state)  # unexcursed or already-terminal: refused
            ordinal = common.require_int(payload["ordinal"], "ordinal")
            close = common.require_int(payload["close_ticks"], "close_ticks")
            atr = payload.get("atr14_ticks")
            if atr is None:
                event = abstention(
                    "F13_NO_ATR", formula=FORMULA_F13,
                    detail="no causal ATR at reclaim-observation time",
                    refs={"level_id": level_id, "ordinal": ordinal})
                return TransitionResult(state, (event,))
            if ordinal > horizon:
                row = dict(row)
                row["reclaim_state"] = RECLAIM_EXPIRED
                levels[level_id] = row
                event = {
                    "event_kind": RECLAIM_STATE_CHANGED, "formula": FORMULA_F13,
                    "level_id": level_id, "to_state": RECLAIM_EXPIRED, "ordinal": ordinal,
                }
                return TransitionResult({"levels": levels}, (event,))
            buffer = common.evaluate_declared_rational(reclaim_rule, atr)
            row = dict(row)
            if not _reclaims(row["direction"], row["level_ticks"], close, buffer):
                row["hold_count"] = 0
                row["reclaim_state"] = EXCURSED
                levels[level_id] = row
                return TransitionResult({"levels": levels})
            row["hold_count"] += 1
            if row["hold_count"] >= hold_bars:
                row["reclaim_state"] = CONFIRMED
                levels[level_id] = row
                event = {
                    "event_kind": RECLAIM_STATE_CHANGED, "formula": FORMULA_F13,
                    "level_id": level_id, "to_state": CONFIRMED, "ordinal": ordinal,
                }
                return TransitionResult({"levels": levels}, (event,))
            row["reclaim_state"] = RECLAIM_PENDING
            levels[level_id] = row
            event = {
                "event_kind": RECLAIM_STATE_CHANGED, "formula": FORMULA_F13,
                "level_id": level_id, "to_state": RECLAIM_PENDING, "ordinal": ordinal,
            }
            return TransitionResult({"levels": levels}, (event,))

        raise StructureLawError(f"unknown F13 envelope kind: {kind!r}")
