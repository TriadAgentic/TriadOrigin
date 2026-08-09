"""Causal feature primitives F02 (trailing ATR) and F05 (trailing rolling extreme).

The law (docs/control/b03_grounding.tmp.json):

* **F02** — ``TR_i = max(H_i - L_i, |H_i - C_{i-1}|, |L_i - C_{i-1}|)``;
  ``ATR_N(x) = ceil_div(sum(TR_{x-N} .. TR_{x-1}), N)`` over finalized bars STRICTLY BEFORE the
  evaluation origin (the most recent finalized bar contributes ``TR_{x-1}``). Parameter:
  ``atr_period`` (PAR-035, fetched with :func:`triad_origin.transition.require` — no code
  default). Fewer than N clean consecutive TRs is the NAMED abstention ``F02_ATR_WARMUP``
  (GV-004: 13 TRs abstain; 14 TRs all 8 yield ATR exactly 8). A GAP bar (missing prior close or
  a non-contiguous bar index) poisons the window: ATR abstains until a full clean window exists
  after the gap. Side-neutral.

* **F05** — ``upper_t = max(H[t-N:t])``; ``lower_t = min(L[t-N:t])``; the CURRENT bar is
  excluded. Parameter: ``window`` (PAR-039). Warm-up abstains ``F05_WARMUP`` until exactly N
  complete contiguous prior bars exist; a gap resets the window. Upper/lower mirror.

Input envelopes are the market_state.v2-shaped finalized BAR events accepted by
:func:`triad_origin.e01_interface.validate_finalized_bar` (E01-owned facts — this module never
aggregates trades into bars). Each accepted bar yields exactly one event: a ``FEATURE`` event or
a NAMED abstention. A rejected input emits its quarantine rejection verbatim and poisons window
continuity; an exact semantic duplicate of the last consumed bar is a no-op; a same-index bar
with different bytes is a revision conflict (rejected + poison); an older bar index is rejected
out-of-order without touching the window. Both machines are pure: no clock, no I/O, no floats.
"""

from __future__ import annotations

from . import canonical
from .e01_interface import (
    E01_BAR_OUT_OF_ORDER,
    E01_BAR_REVISION_CONFLICT,
    rejection,
    validate_finalized_bar,
)
from .structures.common import StructureLawError, abstention, ceil_div, require_int
from .transition import Envelope, Params, Quality, State, TransitionResult, require

F02_FEATURE_VERSION = "atr.sma.closed.v1"
F05_FEATURE_VERSION = "rolling_extreme.v1"

WARMUP_STATUSES = ("WARMING", "COMPLETE")


def _bar_digest(bar: dict) -> str:
    return canonical.sha256_hex(canonical.canonical_json(bar))


def _classify(state: State, bar: dict) -> tuple[str, dict | None]:
    """Order/continuity verdict for an accepted bar: ok | first | gap | duplicate | reject."""
    last_index = state["last_bar_index"]
    if last_index is None:
        return "first", None
    index = bar["bar_index"]
    if index == last_index:
        if _bar_digest(bar) == state["last_bar_digest"]:
            return "duplicate", None
        return "reject", rejection(
            E01_BAR_REVISION_CONFLICT, formula="F01",
            detail=f"bar_index {index} re-delivered with different canonical bytes")
    if index < last_index:
        return "reject", rejection(
            E01_BAR_OUT_OF_ORDER, formula="F01",
            detail=f"bar_index {index} arrived after {last_index}")
    if index > last_index + 1:
        return "gap", None
    return "ok", None


class AtrCalculator:
    """F02 — true range and trailing simple-mean ATR in exact ticks (DeterministicMachine)."""

    def initial_state(self) -> State:
        return {
            "last_bar_index": None,
            "last_bar_digest": None,
            "prior_close": None,
            "trs": [],
        }

    def transition(
        self, state: State, envelope: Envelope, params: Params, quality: Quality
    ) -> TransitionResult:
        period = require_int(require(params, "atr_period"), "atr_period")
        if period <= 0:
            raise StructureLawError("atr_period must be a positive exact int (PAR-035)")
        verdict = validate_finalized_bar(envelope)
        if not verdict["accepted"]:
            return TransitionResult(self.initial_state(), (verdict,))
        bar = verdict["bar"]
        kind, reject_event = _classify(state, bar)
        if kind == "duplicate":
            return TransitionResult(state)
        if kind == "reject":
            if reject_event["reason_code"] == E01_BAR_OUT_OF_ORDER:
                return TransitionResult(state, (reject_event,))
            return TransitionResult(self.initial_state(), (reject_event,))
        index = bar["bar_index"]
        prior_close = None if kind in ("first", "gap") else state["prior_close"]
        trs = [] if kind in ("first", "gap") else list(state["trs"])
        if prior_close is None:
            event = abstention(
                "F02_ATR_WARMUP", formula="F02",
                detail="no prior close: the window (re)starts at this bar",
                refs={"bar_index": index, "have_trs": 0, "need_trs": period})
        else:
            high, low, close = bar["high_ticks"], bar["low_ticks"], bar["close_ticks"]
            tr = max(high - low, abs(high - prior_close), abs(low - prior_close))
            trs.append(tr)
            trs = trs[-period:]
            if len(trs) >= period:
                atr = ceil_div(sum(trs), period)
                event = {
                    "event_kind": "FEATURE",
                    "formula": "F02",
                    "feature_version": F02_FEATURE_VERSION,
                    "evaluation_origin_bar_index": index + 1,
                    "atr_ticks": atr,
                    "dependency_range": {
                        "first_tr_bar_index": index - period + 1,
                        "last_tr_bar_index": index,
                        "prior_close_bar_index": index - period,
                    },
                }
            else:
                event = abstention(
                    "F02_ATR_WARMUP", formula="F02",
                    detail=f"{len(trs)} of {period} clean consecutive TRs",
                    refs={"bar_index": index, "have_trs": len(trs), "need_trs": period})
        new_state = {
            "last_bar_index": index,
            "last_bar_digest": _bar_digest(bar),
            "prior_close": bar["close_ticks"],
            "trs": trs,
        }
        return TransitionResult(new_state, (event,))


class RollingExtreme:
    """F05 — trailing rolling extreme over the N prior bars, current bar excluded."""

    def initial_state(self) -> State:
        return {
            "last_bar_index": None,
            "last_bar_digest": None,
            "window": [],
        }

    def transition(
        self, state: State, envelope: Envelope, params: Params, quality: Quality
    ) -> TransitionResult:
        window_n = require_int(require(params, "window"), "window")
        if window_n <= 0:
            raise StructureLawError("window must be a positive exact int (PAR-039)")
        verdict = validate_finalized_bar(envelope)
        if not verdict["accepted"]:
            return TransitionResult(self.initial_state(), (verdict,))
        bar = verdict["bar"]
        kind, reject_event = _classify(state, bar)
        if kind == "duplicate":
            return TransitionResult(state)
        if kind == "reject":
            if reject_event["reason_code"] == E01_BAR_OUT_OF_ORDER:
                return TransitionResult(state, (reject_event,))
            return TransitionResult(self.initial_state(), (reject_event,))
        index = bar["bar_index"]
        window = [] if kind in ("first", "gap") else list(state["window"])
        if len(window) >= window_n:
            upper = max(entry[0] for entry in window)
            lower = min(entry[1] for entry in window)
            event = {
                "event_kind": "FEATURE",
                "formula": "F05",
                "feature_version": F05_FEATURE_VERSION,
                "bar_index": index,
                "upper_ticks": upper,
                "lower_ticks": lower,
                "dependency_range": {
                    "first_bar_index": index - window_n,
                    "last_bar_index": index - 1,
                },
            }
        else:
            event = abstention(
                "F05_WARMUP", formula="F05",
                detail=f"{len(window)} of {window_n} complete prior bars",
                refs={"bar_index": index, "have_bars": len(window), "need_bars": window_n})
        window.append([bar["high_ticks"], bar["low_ticks"]])
        window = window[-window_n:]
        new_state = {
            "last_bar_index": index,
            "last_bar_digest": _bar_digest(bar),
            "window": window,
        }
        return TransitionResult(new_state, (event,))


def build_feature_snapshot_payload(
    *,
    feature_set: str,
    feature_version: str,
    partition_key: dict,
    as_of_state_revision_id: str,
    feature_values: dict,
    dependency_ranges: dict,
    formula_text: str,
    params: dict,
    warmup_status: str,
    source_time_us: int,
    knowledge_time_us: int,
    evaluation_time_us: int,
    publication_time_us: int,
) -> dict:
    """Assemble a ``triad.feature_snapshot.v2`` payload from emitted feature values.

    Digests are computed here from the canonical bytes of the declared formula text, the exact
    parameter bundle, and the output values. ``warmup_status`` must be HONEST: ``COMPLETE`` iff
    ``feature_values`` is non-empty and carries no null; anything else is ``WARMING``.
    """
    for name, value in (
        ("feature_set", feature_set), ("feature_version", feature_version),
        ("as_of_state_revision_id", as_of_state_revision_id), ("formula_text", formula_text),
    ):
        if not isinstance(value, str) or not value:
            raise StructureLawError(f"{name} must be a non-empty str")
    for name, value in (
        ("partition_key", partition_key), ("feature_values", feature_values),
        ("dependency_ranges", dependency_ranges), ("params", params),
    ):
        if not isinstance(value, dict):
            raise StructureLawError(f"{name} must be a dict")
    times = {
        "source_time_us": require_int(source_time_us, "source_time_us"),
        "knowledge_time_us": require_int(knowledge_time_us, "knowledge_time_us"),
        "evaluation_time_us": require_int(evaluation_time_us, "evaluation_time_us"),
        "publication_time_us": require_int(publication_time_us, "publication_time_us"),
    }
    if not (
        times["source_time_us"] <= times["knowledge_time_us"]
        <= times["evaluation_time_us"] <= times["publication_time_us"]
    ):
        raise StructureLawError(
            "causal time order: source <= knowledge <= evaluation <= publication")
    if warmup_status not in WARMUP_STATUSES:
        raise StructureLawError(f"warmup_status must be one of {WARMUP_STATUSES}")
    honest = "COMPLETE" if (
        feature_values and all(value is not None for value in feature_values.values())
    ) else "WARMING"
    if warmup_status != honest:
        raise StructureLawError(
            f"warmup_status {warmup_status!r} is dishonest: the values say {honest!r}")
    formula_digest = canonical.sha256_hex(
        canonical.canonical_json({"formula_text": formula_text}))
    parameter_digest = canonical.sha256_hex(canonical.canonical_json(params))
    output_hash = canonical.sha256_hex(canonical.canonical_json(
        {"dependency_ranges": dependency_ranges, "feature_values": feature_values}))
    return {
        "feature_set": feature_set,
        "feature_version": feature_version,
        "partition_key": partition_key,
        "as_of_state_revision_id": as_of_state_revision_id,
        "feature_values": feature_values,
        "dependency_ranges": dependency_ranges,
        "formula_digest": formula_digest,
        "parameter_digest": parameter_digest,
        "warmup_status": warmup_status,
        "output_hash": output_hash,
        **times,
    }
