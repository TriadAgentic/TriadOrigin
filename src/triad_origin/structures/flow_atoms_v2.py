"""Flow atoms v2 — R-F15 ``flow.tfi.window.v2`` · R-F16 ``flow.ofi.best.v2`` (+ the separate
identity ``flow.ofi.best_norm.v1``, activation OFF) · R-F17 ``flow.book_tilt.band.v2``
(TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12, repair home B04C).

This is the repaired successor of ``structures/flow_atoms.py`` — whose three v1 machines are
retired together with the withdrawal banner ``defect_ref=R-F15;R-F16;R-F17`` (their bytes are
preserved by §1.5 law; nothing is relabeled). Each formula here is a pure §C.3 entrypoint
``evaluate(caps, env, state)``: ``caps`` maps ``parameter_id -> bindings.VerifiedCapability`` (the
sealed-capability handle minted only by ``transition.require_bundle``; exact-type-checked per entry,
``formula_id`` and ``parameter_id`` bound), and ``env`` is an exact-typed frozen envelope. Raw dict
parameters and raw ``transition.require`` are gone. Every boundary violation is a TYPED rejection
BEFORE any state transition; replay and live call the SAME transition; no clock, I/O, randomness or
float touches a semantic path; exact rationals are reduced ``(num, den)`` pairs (``exact.rational``)
and every persisted integer crosses ``exact.guard_int64`` (§1.2, ``QUARANTINE_OVERFLOW``).

R-F15 — event-time trade-flow imbalance, exact units::

    TFI = (Σ buy_quote − Σ sell_quote) / (Σ buy_quote + Σ sell_quote)   [reduced rational]
    Window: venue EVENT-TIME half-open [W_start, W_end); arrival order irrelevant.
    Unit (RATIFY_WITH_THIS_REPAIR): quote_notional_atoms = price_ticks × qty_steps (computed
      INSIDE from the ValidatedTrade-framed observation, never caller-asserted). The atom scale
      cancels IFF every included trade shares one metadata_revision; mixed -> NULL{METADATA_REVISION_MIX}.
    Aggressor: the venue flag only (validate_trade admits exactly {BUY,SELL}; a missing/unknown
      flag is quarantined at the E01 boundary, so it never reaches this machine — excluded, and the
      window's coverage falls short of expected_trades). Dedup: (venue, instrument, trade_id),
      any duplicate ignored regardless of adjacency. Watermark: emit only when watermark_us >= W_end;
      a late trade whose event_time lands in an already-emitted window emits a REVISION superseding
      the atom (the original is never rewritten). Zero denominator -> NULL{ZERO_DENOMINATOR}.
      Mirror: swapping buy/sell legs negates TFI exactly.

R-F16 — validated CKS OFI over sequence-continuous best-quote updates; the normalized variant is a
SEPARATE identity (``flow.ofi.best_norm.v1``) behind a default-OFF activation lever::

    VALIDITY per update: Pb < Pa strict (crossed OR locked -> invalid), Qb>0 AND Qa>0. A gap
      (seq skips ahead) -> the whole window NULL{SEQUENCE_GAP} + pairwise reset; a duplicate/stale
      seq -> ignored (count unchanged); an invalid update breaks the pair chain (no e_n across it)
      and does not extend the window.
    e_n = I(Pb_n>=Pb_prev)·Qb_n − I(Pb_n<=Pb_prev)·Qb_prev
        − I(Pa_n<=Pa_prev)·Qa_n + I(Pa_n>=Pa_prev)·Qa_prev
    OFI = Σ e_n over VALID consecutive pairs. Emission: window >= min_updates AND fresh
      (eval_time − last_update_event_time <= max_age; stale -> NULL{STALE}) AND watermark complete.
    NORMALIZED (SEPARATE IDENTITY flow.ofi.best_norm.v1, lever OFI_NORMALIZED_VARIANT_ACTIVATION ∈
      {LIVE, OFF}, default OFF): OFI_norm = OFI / D̄, D̄ = Σ(Qb_n+Qa_n)/(2·update_count); D̄ = 0 ->
      NULL. Lever OFF -> the norm identity never emits. The retired boolean PAR-170 is superseded.

  The E01 ``validate_book_update`` boundary is a per-update UNIFORM reject (it quarantines a crossed,
  locked, zero-qty, gapped, or stale update). R-F16's validity is STATE-dependent — a crossed update
  breaks the chain but the window continues (T10), a genuine sequence gap NULLs the window (T13), a
  duplicate seq is ignored (T14) — three outcomes one uniform reject cannot distinguish. So this
  machine consumes the exact-typed ``BookUpdateObservation`` (int64-guarded at its own boundary, a
  dict is refused) and applies the R-F16 validity law itself; it constructs no ValidatedInput.

R-F17 — book tilt over machine-built bands with a strictly-positive depth floor::

    tilt = (bid_quote_depth − ask_quote_depth) / (bid_quote_depth + ask_quote_depth)  [reduced]
    INPUT: the machine consumes the validated local book snapshot (uncrossed best_bid<best_ask,
      positive qty, fresh) and computes the banded quote-notional sums itself — quote depth over
      levels with |level_price − best_same_side| <= band_ticks (boundary INCLUSIVE), depth per level
      = price_ticks × qty_steps. Caller-supplied sums are REMOVED from the API (the R-F14 fix class).
    DEPTH FLOOR (binding law): BOOK_TILT_MIN_DEPTH_QUOTE_ATOMS must be ratified STRICTLY POSITIVE;
      a min <= 0 configuration is REFUSE_CONFIG. D = bid+ask; D < min_depth -> NULL{INSUFFICIENT_DEPTH}
      (covers D = 0 automatically since min > 0). Crossed/empty/stale/invalid book -> NULL, typed.

Ratification statuses: F15's atom unit + F16's activation lever + F17's band-inclusive law are
``RATIFY_WITH_THIS_REPAIR`` (owner signature on the repair PR). ``BOOK_TILT_MIN_DEPTH_QUOTE_ATOMS``
is ``PROPOSED_MUST_RATIFY`` (proposed 100 tick×step atoms; the mechanism + the named refusal are
wired, the value is NEVER hardcoded active — the refusal stands until signed).
"""

from __future__ import annotations

from dataclasses import dataclass

# ``bindings`` referenced as a MODULE (never ``from ..bindings import VerifiedCapability``): the
# exact-type capability check must track the LIVE module identity, so the contracts suite's
# importlib.reload(bindings) drill can never split the class identity between the minting path
# (``transition.require_bundle``) and this boundary (the break_v2/swing_dc_v2 house pattern).
from .. import bindings, exact
from ..canonical import CanonicalError, canonical_json, loads_canonical
from ..transition import MissingParameterError, TransitionResult
from . import common

# --- formula identity ------------------------------------------------------------------------
FORMULA_F15 = "F15"
FORMULA_F16 = "F16"
FORMULA_F17 = "F17"

F15_FORMULA_VERSION = "flow.tfi.window.v2"
F16_FORMULA_VERSION = "flow.ofi.best.v2"
F16_NORM_FORMULA_VERSION = "flow.ofi.best_norm.v1"   # SEPARATE identity, activation OFF
F17_FORMULA_VERSION = "flow.book_tilt.band.v2"

# --- capability parameter ids (keys of the caps mapping) -------------------------------------
# Existing registry parameter ids are kept verbatim (PAR-05x); the renamed/new ones carry the
# spec name (the break_v2 PAR-043 vs LEVEL_TTL_BARS precedent).
PARAM_TFI_WINDOW_TRADES = "PAR-052"       # TFI_WINDOW_TRADES (window cap)
PARAM_TFI_WINDOW_MAX_AGE = "PAR-053"      # TFI_WINDOW_MAX_AGE (freshness TTL, ms)
PARAM_TFI_MIN_TRADES = "PAR-054"          # TFI_MIN_TRADES (included-trade floor)

PARAM_OFI_WINDOW_UPDATES = "PAR-056"      # OFI_WINDOW_UPDATES (window cap)
PARAM_OFI_WINDOW_MAX_AGE = "PAR-057"      # OFI_WINDOW_MAX_AGE (staleness bound, ms)
PARAM_OFI_MIN_UPDATES = "PAR-058"         # OFI_MIN_UPDATES (window floor)
PARAM_OFI_NORM_ACTIVATION = "OFI_NORMALIZED_VARIANT_ACTIVATION"  # enum LIVE/OFF, retires PAR-170

PARAM_BOOK_TILT_MIN_DEPTH = "BOOK_TILT_MIN_DEPTH_QUOTE_ATOMS"    # PROPOSED_MUST_RATIFY (supersedes
#                                                                 RC3-PAR-STRUCT-002)
PARAM_BOOK_TILT_BAND = "BOOK_TILT_BAND_TICKS"                    # band, boundary-inclusive
PARAM_BOOK_TILT_TTL = "BOOK_TILT_TTL"                            # PROPOSED_MUST_RATIFY (optional)

# --- lever enum values ------------------------------------------------------------------------
NORM_ACTIVATION_OFF = "OFF"
NORM_ACTIVATION_LIVE = "LIVE"
_NORM_ACTIVATION_VALUES = (NORM_ACTIVATION_OFF, NORM_ACTIVATION_LIVE)

# --- typed refusal / abstention / event vocabulary -------------------------------------------
REFUSE_CONFIG = "REFUSE_CONFIG"

FEATURE = "FEATURE"
TFI_REVISION = "TFI_REVISION"

# F15 reason codes
F15_WATERMARK_PENDING = "F15_TFI_WATERMARK_PENDING"
F15_METADATA_REVISION_MIX = "F15_TFI_METADATA_REVISION_MIX"
F15_INSUFFICIENT_COVERAGE = "F15_TFI_INSUFFICIENT_COVERAGE"
F15_COVERAGE = "F15_TFI_COVERAGE"
F15_ZERO_DENOMINATOR = "F15_TFI_ZERO_DENOMINATOR"

# F16 reason codes
F16_SEQUENCE_GAP = "F16_SEQUENCE_GAP"
F16_INVALID_UPDATE = "F16_INVALID_UPDATE"
F16_INSUFFICIENT_COVERAGE = "F16_INSUFFICIENT_COVERAGE"
F16_STALE = "F16_STALE"
F16_NORM_ZERO_DEPTH = "F16_NORM_ZERO_DEPTH"

# F17 reason codes
F17_UNAVAILABLE_MIN_DEPTH = "F17_UNAVAILABLE_MIN_DEPTH_NOT_RATIFIED"
F17_INSUFFICIENT_DEPTH = "F17_INSUFFICIENT_DEPTH"
F17_ZERO_DENOMINATOR = "F17_ZERO_DENOMINATOR"
F17_CROSSED_BOOK = "F17_CROSSED_BOOK"
F17_EMPTY_BOOK = "F17_EMPTY_BOOK"
F17_INVALID_BOOK = "F17_INVALID_BOOK"
F17_STALE = "F17_STALE"

TRADE_SIDE_BUY = "BUY"
TRADE_SIDE_SELL = "SELL"


class EnvelopeRejected(TypeError):
    """A non-typed / wrong-type object was presented at the public surface (C.3 boundary law)."""


class RefuseConfig(ValueError):
    """The typed ``REFUSE_CONFIG`` refusal (F17 depth-floor min <= 0; malformed capability faces)."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"{REFUSE_CONFIG}: {detail}")
        self.reason = REFUSE_CONFIG
        self.detail = detail


def _indicator(condition: bool) -> int:
    """The RC3 indicator ``I()`` made explicit — never Python's bool-as-int coercion."""
    return 1 if condition else 0


# ---------------------------------------------------------------------------------------------
# Shared boundary validation
# ---------------------------------------------------------------------------------------------


def _validated_caps(caps: object, *, formula_id: str, required: tuple, optional: tuple) -> dict:
    """Validate the capability mapping (exact type, formula id, key==parameter_id)."""
    if type(caps) is not dict:
        raise EnvelopeRejected(
            "caps must be a dict mapping parameter_id -> VerifiedCapability, got "
            f"{type(caps).__name__}")
    allowed = set(required) | set(optional)
    unknown = sorted(set(caps) - allowed)
    if unknown:
        raise RefuseConfig(
            f"unknown capability key {unknown[0]!r} — {formula_id} v2 consumes exactly "
            f"required={sorted(required)} optional={sorted(optional)}")
    for req in required:
        if req not in caps:
            raise MissingParameterError(
                f"required capability {req!r} is absent; {formula_id} v2 fails closed (no code "
                "default)")
    for key in sorted(caps):
        cap = caps[key]
        if type(cap) is not bindings.VerifiedCapability:
            raise bindings.CapabilityForgeryError(
                f"caps[{key!r}] must be a VerifiedCapability minted by require_bundle, got "
                f"{type(cap).__name__} — a hand-built parameter cannot enter a production formula "
                "path")
        if cap.formula_id != formula_id:
            raise bindings.CapabilityForgeryError(
                f"caps[{key!r}] was minted for formula {cap.formula_id!r}; {formula_id} v2 spends "
                f"only {formula_id} capabilities")
        if cap.parameter_id != key:
            raise bindings.CapabilityForgeryError(
                f"caps[{key!r}] carries parameter_id {cap.parameter_id!r}; the key and the "
                "capability identity must agree")
    return caps


def _positive_int_face(value: object, name: str, formula_id: str) -> int:
    """A ratified strictly-positive exact-int64 capability value, else REFUSE_CONFIG."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise RefuseConfig(f"{name} must be an exact int, got {type(value).__name__}")
    guarded = exact.guard_int64(value, formula_id=formula_id, field=name)
    if guarded <= 0:
        raise RefuseConfig(f"{name} must be a strictly-positive integer, got {guarded}")
    return guarded


def _nonneg_int(value: object, field: str, formula_id: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EnvelopeRejected(f"{field} must be an exact int, got {type(value).__name__}")
    guarded = exact.guard_int64(value, formula_id=formula_id, field=field)
    if guarded < 0:
        raise EnvelopeRejected(f"{field} must be >= 0, got {guarded}")
    return guarded


def _guarded_int(value: object, field: str, formula_id: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EnvelopeRejected(f"{field} must be an exact int, got {type(value).__name__}")
    return exact.guard_int64(value, formula_id=formula_id, field=field)


def _nonempty_str(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise EnvelopeRejected(f"{name} must be a non-empty string")
    return value


def _state_snapshot(state: object, expected_keys: tuple) -> dict:
    """A detached canonical copy of the prior state (the machine never mutates the caller's)."""
    if not isinstance(state, dict):
        raise EnvelopeRejected(f"state must be an object, got {type(state).__name__}")
    if sorted(state) != sorted(expected_keys):
        raise EnvelopeRejected(
            f"state must carry exactly the keys {sorted(expected_keys)}, got {sorted(state)}")
    try:
        return loads_canonical(canonical_json(state))
    except CanonicalError as exc:
        raise EnvelopeRejected(f"state is not canonical data: {exc}") from exc


# =================================================================================================
# R-F15 — flow.tfi.window.v2
# =================================================================================================


@dataclass(frozen=True)
class TradeObservation:
    """One classified trade, framed for F15 v2 over the E01 trade boundary.

    ``trade`` is the §C.3 VALIDATED trade (an :class:`~triad_origin.e01_interface.ValidatedTrade`,
    constructible only by ``validate_trade`` — so ``aggressor_side`` is a real venue flag and
    ``event_time_us``/``trade_id`` are present). ``price_ticks``/``qty_steps`` are the quote-atom
    inputs (the machine computes ``price_ticks × qty_steps`` itself — never a caller-asserted
    notional); ``metadata_revision`` is the instrument-metadata revision under which the atom scale
    is denominated (the mixed-revision guard); ``venue``/``instrument`` complete the dedup key.
    """

    trade: object   # e01_interface.ValidatedTrade (exact-type-checked at the boundary)
    venue: str
    instrument: str
    price_ticks: int
    qty_steps: int
    metadata_revision: str
    source_event_id: str


@dataclass(frozen=True)
class WindowClose:
    """A venue event-time window close: emit TFI over trades with event_time in [w_start, w_end).

    ``expected_trades`` is the venue's count of trades in the window (an E01/window fact, not a
    policy threshold) against which coverage is reconciled; ``watermark_us`` is the min contributing
    source watermark (emission requires ``watermark_us >= w_end``).
    """

    w_start: int
    w_end: int
    expected_trades: int
    watermark_us: int
    source_event_id: str


_F15_STATE_KEYS = ("buffer", "emitted", "watermark_us")


def f15_initial_state() -> dict:
    """Cold F15 state: no buffered trades, no emitted windows, no watermark."""
    return {"buffer": {}, "emitted": {}, "watermark_us": None}


def _validate_validated_trade(trade: object) -> object:
    # Exact-type check without importing the class name at module top (reload-immunity is only
    # required for the capability class; the trade type is imported lazily here).
    from ..e01_interface import ValidatedTrade
    if type(trade) is not ValidatedTrade:
        raise EnvelopeRejected(
            "TradeObservation.trade must be an e01_interface.ValidatedTrade (constructed only by "
            f"validate_trade), got {type(trade).__name__}")
    return trade


def _validated_f15_env(env: object) -> type:
    kind = type(env)
    if kind is TradeObservation:
        _validate_validated_trade(env.trade)
        _nonempty_str(env.venue, "venue")
        _nonempty_str(env.instrument, "instrument")
        _guarded_int(env.price_ticks, "price_ticks", FORMULA_F15)
        _nonneg_int(env.qty_steps, "qty_steps", FORMULA_F15)
        _nonempty_str(env.metadata_revision, "metadata_revision")
        _nonempty_str(env.source_event_id, "source_event_id")
        return kind
    if kind is WindowClose:
        w_start = _nonneg_int(env.w_start, "w_start", FORMULA_F15)
        w_end = _nonneg_int(env.w_end, "w_end", FORMULA_F15)
        if not w_start < w_end:
            raise EnvelopeRejected("WindowClose requires w_start < w_end (a half-open window)")
        _nonneg_int(env.expected_trades, "expected_trades", FORMULA_F15)
        _nonneg_int(env.watermark_us, "watermark_us", FORMULA_F15)
        _nonempty_str(env.source_event_id, "source_event_id")
        return kind
    raise EnvelopeRejected(
        "F15 v2 consumes exactly TradeObservation | WindowClose (exact types), got "
        f"{type(env).__name__}")


def _dedup_key(venue: str, instrument: str, trade_id: str) -> str:
    return canonical_json([venue, instrument, trade_id]).decode("utf-8")


def _atoms_of(obs: TradeObservation) -> int:
    """quote_notional_atoms = price_ticks × qty_steps, re-guarded to signed int64 (§1.2)."""
    product = obs.price_ticks * obs.qty_steps
    return exact.guard_int64(product, formula_id=FORMULA_F15, field="quote_notional_atoms")


def _window_key(w_start: int, w_end: int) -> str:
    return f"{w_start}:{w_end}"


def _tfi_over(buy_atoms: int, sell_atoms: int) -> tuple:
    """The reduced (num, den) TFI over already-summed buy/sell atoms; caller handles zero-den."""
    numerator = exact.guard_int64(
        buy_atoms - sell_atoms, formula_id=FORMULA_F15, field="tfi_numerator")
    denominator = exact.guard_int64(
        buy_atoms + sell_atoms, formula_id=FORMULA_F15, field="tfi_denominator")
    return exact.rational(numerator, denominator)


def evaluate_f15(caps: object, env: object, state: object) -> TransitionResult:
    """F15 v2 §C.3 entrypoint — event-time trade-flow imbalance (exact quote-atom units)."""
    caps = _validated_caps(
        caps, formula_id=FORMULA_F15,
        required=(PARAM_TFI_WINDOW_TRADES, PARAM_TFI_WINDOW_MAX_AGE, PARAM_TFI_MIN_TRADES),
        optional=())
    window_cap = _positive_int_face(
        caps[PARAM_TFI_WINDOW_TRADES].value, "tfi_window_trades", FORMULA_F15)
    max_age_ms = _positive_int_face(
        caps[PARAM_TFI_WINDOW_MAX_AGE].value, "tfi_window_max_age_ms", FORMULA_F15)
    min_trades = _positive_int_face(
        caps[PARAM_TFI_MIN_TRADES].value, "tfi_min_trades", FORMULA_F15)
    kind = _validated_f15_env(env)
    prior = _state_snapshot(state, _F15_STATE_KEYS)
    if kind is TradeObservation:
        return _f15_on_trade(prior, env)
    return _f15_on_window(prior, env, window_cap, max_age_ms, min_trades)


def _late_trade_window(state: dict, event_time_us: int):
    """The emitted window (if any) whose half-open range contains ``event_time_us``."""
    for window_key in sorted(state["emitted"]):
        rec = state["emitted"][window_key]
        if rec["w_start"] <= event_time_us < rec["w_end"]:
            return window_key, rec
    return None, None


def _f15_on_trade(state: dict, obs: TradeObservation) -> TransitionResult:
    key = _dedup_key(obs.venue, obs.instrument, obs.trade.trade_id)
    # Dedup: (venue, instrument, trade_id), any duplicate ignored regardless of adjacency —
    # in the pending buffer OR already a member of an emitted window.
    if key in state["buffer"]:
        return TransitionResult(state=state)
    for window_key in state["emitted"]:
        if key in state["emitted"][window_key]["members"]:
            return TransitionResult(state=state)

    atoms = _atoms_of(obs)
    record = {
        "event_time_us": obs.trade.event_time_us,
        "aggressor_side": obs.trade.aggressor_side,
        "atoms": atoms,
        "metadata_revision": obs.metadata_revision,
    }
    window_key, emitted = _late_trade_window(state, obs.trade.event_time_us)
    if emitted is not None:
        # A late trade inside an already-emitted window: recompute and emit a REVISION superseding
        # the atom. The original atom is never rewritten (append-only — the break_v2 void precedent).
        emitted["members"][key] = record
        if obs.trade.aggressor_side == TRADE_SIDE_BUY:
            emitted["buy_atoms"] = exact.guard_int64(
                emitted["buy_atoms"] + atoms, formula_id=FORMULA_F15, field="tfi_buy_atoms")
        elif obs.trade.aggressor_side == TRADE_SIDE_SELL:
            emitted["sell_atoms"] = exact.guard_int64(
                emitted["sell_atoms"] + atoms, formula_id=FORMULA_F15, field="tfi_sell_atoms")
        emitted["trade_count"] += 1
        emitted["metadata_revisions"] = sorted(
            set(emitted["metadata_revisions"]) | {obs.metadata_revision})
        prior_revision_id = emitted["revision_id"]
        emitted["revision"] += 1
        emitted["revision_id"] = f"{window_key}#r{emitted['revision']}"
        event = {
            "event_kind": TFI_REVISION,
            "formula": FORMULA_F15,
            "formula_version": F15_FORMULA_VERSION,
            "window_start": emitted["w_start"],
            "window_end": emitted["w_end"],
            "superseded_revision_id": prior_revision_id,
            "revision_id": emitted["revision_id"],
            "late_trade_id": obs.trade.trade_id,
            "trade_count": emitted["trade_count"],
            "source_event_id": obs.source_event_id,
        }
        if len(emitted["metadata_revisions"]) > 1:
            event["superseded_by_reason"] = F15_METADATA_REVISION_MIX
        elif emitted["buy_atoms"] + emitted["sell_atoms"] == 0:
            event["superseded_by_reason"] = F15_ZERO_DENOMINATOR
        else:
            event["tfi"] = list(_tfi_over(emitted["buy_atoms"], emitted["sell_atoms"]))
            event["buy_atoms"] = emitted["buy_atoms"]
            event["sell_atoms"] = emitted["sell_atoms"]
        return TransitionResult(state=state, events=(event,))

    state["buffer"][key] = record
    return TransitionResult(state=state)


def _f15_on_window(state: dict, close: WindowClose, window_cap: int, max_age_ms: int,
                   min_trades: int) -> TransitionResult:
    # Monotone watermark; a window may emit only once its whole range is behind the watermark.
    prior_watermark = state["watermark_us"]
    watermark = close.watermark_us if prior_watermark is None else max(prior_watermark,
                                                                       close.watermark_us)
    if watermark < close.w_end:
        return TransitionResult(state=state, events=(common.abstention(
            F15_WATERMARK_PENDING, formula=FORMULA_F15,
            detail="the window watermark has not passed W_end; emission is deferred",
            refs={"source_event_id": close.source_event_id, "watermark_us": watermark,
                  "window_end": close.w_end}),))
    state["watermark_us"] = watermark

    window_key = _window_key(close.w_start, close.w_end)
    members: dict = {}
    for key in sorted(state["buffer"]):
        trade = state["buffer"][key]
        if close.w_start <= trade["event_time_us"] < close.w_end:  # half-open [W_start, W_end)
            members[key] = trade
    for key in members:
        del state["buffer"][key]
    # Newest-first cap: the most recent ``window_cap`` trades by (event_time, dedup key).
    ordered = sorted(members, key=lambda k: (members[k]["event_time_us"], k))
    if len(ordered) > window_cap:
        for key in ordered[:-window_cap]:
            del members[key]

    included = len(members)
    revisions = sorted({members[k]["metadata_revision"] for k in members})
    buy_atoms = sum(members[k]["atoms"] for k in members
                    if members[k]["aggressor_side"] == TRADE_SIDE_BUY)
    sell_atoms = sum(members[k]["atoms"] for k in members
                     if members[k]["aggressor_side"] == TRADE_SIDE_SELL)
    buy_atoms = exact.guard_int64(buy_atoms, formula_id=FORMULA_F15, field="tfi_buy_atoms")
    sell_atoms = exact.guard_int64(sell_atoms, formula_id=FORMULA_F15, field="tfi_sell_atoms")
    # Record the emitted window so a later late trade can revise it (append-only).
    state["emitted"][window_key] = {
        "w_start": close.w_start, "w_end": close.w_end, "members": members,
        "buy_atoms": buy_atoms, "sell_atoms": sell_atoms, "trade_count": included,
        "metadata_revisions": revisions, "revision": 1,
        "revision_id": f"{window_key}#r1",
    }

    freshness_ttl_us = max_age_ms * 1000
    refs = {"source_event_id": close.source_event_id, "window_start": close.w_start,
            "window_end": close.w_end}
    if len(revisions) > 1:
        return TransitionResult(state=state, events=(common.abstention(
            F15_METADATA_REVISION_MIX, formula=FORMULA_F15,
            detail="the window mixes instrument metadata revisions; the atom scale does not "
                   "cancel — never a blended TFI",
            refs=refs),))
    if included < min_trades:
        return TransitionResult(state=state, events=(common.abstention(
            F15_INSUFFICIENT_COVERAGE, formula=FORMULA_F15,
            detail=f"{included} of {min_trades} included trades in the window",
            refs={**refs, "have_trades": included, "need_trades": min_trades}),))
    if included < close.expected_trades:
        return TransitionResult(state=state, events=(common.abstention(
            F15_COVERAGE, formula=FORMULA_F15,
            detail=f"coverage shortfall: {included} included of {close.expected_trades} expected "
                   "(a trade was excluded — e.g. a missing aggressor flag quarantined at the "
                   "boundary); the atom is fail-closed",
            refs={**refs, "included_trades": included,
                  "expected_trades": close.expected_trades}),))
    if buy_atoms + sell_atoms == 0:
        return TransitionResult(state=state, events=(common.abstention(
            F15_ZERO_DENOMINATOR, formula=FORMULA_F15,
            detail="buy and sell quote atoms in the window are both zero",
            refs={**refs, "trade_count": included}),))
    tfi = _tfi_over(buy_atoms, sell_atoms)
    event = {
        "event_kind": FEATURE,
        "formula": FORMULA_F15,
        "formula_version": F15_FORMULA_VERSION,
        "tfi": list(tfi),
        "buy_atoms": buy_atoms,
        "sell_atoms": sell_atoms,
        "trade_count": included,
        "window_start": close.w_start,
        "window_end": close.w_end,
        "watermark_us": watermark,
        "freshness_ttl_us": freshness_ttl_us,
        "revision_id": f"{window_key}#r1",
        "metadata_revision": revisions[0],
        "confirmed_by_event_id": close.source_event_id,
    }
    return TransitionResult(state=state, events=(event,))


# =================================================================================================
# R-F16 — flow.ofi.best.v2 (+ flow.ofi.best_norm.v1, activation OFF)
# =================================================================================================


@dataclass(frozen=True)
class BookUpdateObservation:
    """One best-quote update ``u_n = (Pb, Qb, Pa, Qa, seq, event_time)`` on one venue partition.

    A raw-typed frame (int64-guarded at the boundary), NOT a ValidatedBookUpdate: R-F16's validity
    is state-dependent (see the module docstring), so this machine applies the validity law itself.
    ``eval_time_us`` is the injected evaluation instant (the staleness clock; no wall clock here);
    ``watermark_complete`` gates emission exactly like the v1 precedent.
    """

    sequence: int
    event_time_us: int
    eval_time_us: int
    best_bid_price_ticks: int
    best_bid_qty_steps: int
    best_ask_price_ticks: int
    best_ask_qty_steps: int
    watermark_complete: bool
    source_event_id: str


_F16_STATE_KEYS = ("prev_valid", "last_seq", "window")


def f16_initial_state() -> dict:
    """Cold F16 state: no baseline, no delivered seq, an empty window."""
    return {"prev_valid": None, "last_seq": None, "window": []}


def _validated_f16_env(env: object) -> BookUpdateObservation:
    if type(env) is not BookUpdateObservation:
        raise EnvelopeRejected(
            "F16 v2 consumes exactly a BookUpdateObservation (exact type), got "
            f"{type(env).__name__}")
    _nonneg_int(env.sequence, "sequence", FORMULA_F16)
    _nonneg_int(env.event_time_us, "event_time_us", FORMULA_F16)
    _nonneg_int(env.eval_time_us, "eval_time_us", FORMULA_F16)
    _guarded_int(env.best_bid_price_ticks, "best_bid_price_ticks", FORMULA_F16)
    _guarded_int(env.best_bid_qty_steps, "best_bid_qty_steps", FORMULA_F16)
    _guarded_int(env.best_ask_price_ticks, "best_ask_price_ticks", FORMULA_F16)
    _guarded_int(env.best_ask_qty_steps, "best_ask_qty_steps", FORMULA_F16)
    if not isinstance(env.watermark_complete, bool):
        raise EnvelopeRejected("F16 watermark_complete must be an exact bool")
    _nonempty_str(env.source_event_id, "source_event_id")
    # §1.2: the largest product the formula persists is price_ticks × qty_steps (the norm depth
    # sum's per-term magnitude bound) — re-guard both sides.
    exact.guard_int64(env.best_bid_price_ticks * env.best_bid_qty_steps,
                      formula_id=FORMULA_F16, field="bid_quote_atoms")
    exact.guard_int64(env.best_ask_price_ticks * env.best_ask_qty_steps,
                      formula_id=FORMULA_F16, field="ask_quote_atoms")
    return env


def _f16_invalid_reason(env: BookUpdateObservation) -> str | None:
    if not env.best_bid_price_ticks < env.best_ask_price_ticks:
        return "crossed_or_locked_book"
    if env.best_bid_qty_steps <= 0:
        return "non_positive_bid_qty"
    if env.best_ask_qty_steps <= 0:
        return "non_positive_ask_qty"
    return None


def _norm_activation(caps: dict) -> str:
    """Resolve the OFI_NORMALIZED_VARIANT_ACTIVATION lever (default OFF when the cap is absent)."""
    if PARAM_OFI_NORM_ACTIVATION not in caps:
        return NORM_ACTIVATION_OFF
    value = caps[PARAM_OFI_NORM_ACTIVATION].value
    if value not in _NORM_ACTIVATION_VALUES:
        raise RefuseConfig(
            f"{PARAM_OFI_NORM_ACTIVATION} must be one of {_NORM_ACTIVATION_VALUES} — the retired "
            f"boolean PAR-170 (OFI_NORMALIZED_VARIANT_ENABLED) is superseded, got {value!r}")
    return value


def _f16_valid_record(obs: BookUpdateObservation) -> dict:
    return {"sequence": obs.sequence, "event_time_us": obs.event_time_us,
            "bid_price": obs.best_bid_price_ticks, "bid_qty": obs.best_bid_qty_steps,
            "ask_price": obs.best_ask_price_ticks, "ask_qty": obs.best_ask_qty_steps}


def evaluate_f16(caps: object, env: object, state: object) -> TransitionResult:
    """F16 v2 §C.3 entrypoint — validated CKS OFI (+ the separate norm identity, lever OFF)."""
    caps = _validated_caps(
        caps, formula_id=FORMULA_F16,
        required=(PARAM_OFI_WINDOW_UPDATES, PARAM_OFI_WINDOW_MAX_AGE, PARAM_OFI_MIN_UPDATES),
        optional=(PARAM_OFI_NORM_ACTIVATION,))
    window_cap = _positive_int_face(
        caps[PARAM_OFI_WINDOW_UPDATES].value, "ofi_window_updates", FORMULA_F16)
    max_age_ms = _positive_int_face(
        caps[PARAM_OFI_WINDOW_MAX_AGE].value, "ofi_window_max_age_ms", FORMULA_F16)
    min_updates = _positive_int_face(
        caps[PARAM_OFI_MIN_UPDATES].value, "ofi_min_updates", FORMULA_F16)
    norm_activation = _norm_activation(caps)
    obs = _validated_f16_env(env)
    state = _state_snapshot(state, _F16_STATE_KEYS)

    last_seq = state["last_seq"]
    refs = {"source_event_id": obs.source_event_id, "sequence": obs.sequence,
            "declared_window_max_age_ms": max_age_ms}

    # Duplicate / stale sequence -> ignored, count unchanged (T14).
    if last_seq is not None and obs.sequence <= last_seq:
        return TransitionResult(state=state)

    # Sequence gap -> the WHOLE window is NULL + pairwise reset (T13); this update becomes the new
    # baseline (valid) or leaves the chain broken (invalid).
    if last_seq is not None and obs.sequence > last_seq + 1:
        state["window"] = []
        state["last_seq"] = obs.sequence
        state["prev_valid"] = _f16_valid_record(obs) if _f16_invalid_reason(obs) is None else None
        return TransitionResult(state=state, events=(common.abstention(
            F16_SEQUENCE_GAP, formula=FORMULA_F16,
            detail="a book update skipped ahead of the next expected sequence; the whole window "
                   "is void and pairwise state resets",
            refs={**refs, "expected_sequence": last_seq + 1}),))

    state["last_seq"] = obs.sequence
    invalid = _f16_invalid_reason(obs)
    if invalid is not None:
        # An invalid update breaks the pair chain (no e_n across it) and does not extend the
        # window — the window CONTINUES (never a gap-NULL). T10/T11/T12.
        state["prev_valid"] = None
        return TransitionResult(state=state, events=(common.abstention(
            F16_INVALID_UPDATE, formula=FORMULA_F16,
            detail="an invalid best-quote update (crossed/locked book or non-positive quantity) "
                   "breaks the pair chain; the window is unchanged",
            refs={**refs, "invalid_reason": invalid}),))

    prev = state["prev_valid"]
    if prev is not None:
        e_n = (
            _indicator(obs.best_bid_price_ticks >= prev["bid_price"]) * obs.best_bid_qty_steps
            - _indicator(obs.best_bid_price_ticks <= prev["bid_price"]) * prev["bid_qty"]
            - _indicator(obs.best_ask_price_ticks <= prev["ask_price"]) * obs.best_ask_qty_steps
            + _indicator(obs.best_ask_price_ticks >= prev["ask_price"]) * prev["ask_qty"]
        )
        e_n = exact.guard_int64(e_n, formula_id=FORMULA_F16, field="ofi_e_n")
        depth = exact.guard_int64(
            obs.best_bid_qty_steps + obs.best_ask_qty_steps,
            formula_id=FORMULA_F16, field="ofi_update_depth")
        window = list(state["window"])
        window.append({"depth": depth, "e": e_n})
        state["window"] = window[-window_cap:]
    state["prev_valid"] = _f16_valid_record(obs)

    window = state["window"]
    if len(window) < min_updates:
        return TransitionResult(state=state, events=(common.abstention(
            F16_INSUFFICIENT_COVERAGE, formula=FORMULA_F16,
            detail=f"{len(window)} of {min_updates} valid consecutive-pair updates accumulated",
            refs={**refs, "have_updates": len(window), "need_updates": min_updates}),))
    if obs.eval_time_us - obs.event_time_us > max_age_ms * 1000:
        return TransitionResult(state=state, events=(common.abstention(
            F16_STALE, formula=FORMULA_F16,
            detail="the last update's event_time is older than the max-age bound; the OFI is stale",
            refs={**refs, "age_us": obs.eval_time_us - obs.event_time_us,
                  "max_age_us": max_age_ms * 1000}),))
    if not obs.watermark_complete:
        # Silent non-emission: the window/sequence state has advanced (a later, complete-watermark
        # update still sees the unbroken series) — the v1/F04 precedent.
        return TransitionResult(state=state)

    ofi_value = exact.guard_int64(
        sum(entry["e"] for entry in window), formula_id=FORMULA_F16, field="ofi_value")
    events: tuple = ({
        "event_kind": FEATURE,
        "formula": FORMULA_F16,
        "formula_version": F16_FORMULA_VERSION,
        "ofi_value": ofi_value,
        "window_size": len(window),
        "sequence": obs.sequence,
        "declared_window_max_age_ms": max_age_ms,
        "confirmed_by_event_id": obs.source_event_id,
    },)
    if norm_activation == NORM_ACTIVATION_LIVE:
        sum_depth = exact.guard_int64(
            sum(entry["depth"] for entry in window),
            formula_id=FORMULA_F16, field="ofi_norm_sum_depth")
        if sum_depth == 0:
            events += (common.abstention(
                F16_NORM_ZERO_DEPTH, formula=FORMULA_F16,
                detail="mean best-quote depth D-bar is zero; the normalized OFI is undefined",
                refs={**refs, "window_size": len(window)}),)
        else:
            count = len(window)
            dbar = exact.rational(sum_depth, 2 * count)
            ofi_norm = exact.rational(ofi_value * 2 * count, sum_depth)  # OFI / D-bar, exact
            events += ({
                "event_kind": FEATURE,
                "formula": FORMULA_F16,
                "formula_version": F16_NORM_FORMULA_VERSION,
                "ofi_norm": list(ofi_norm),
                "mean_depth": list(dbar),
                "ofi_value": ofi_value,
                "window_size": count,
                "sequence": obs.sequence,
                "confirmed_by_event_id": obs.source_event_id,
            },)
    return TransitionResult(state=state, events=events)


# =================================================================================================
# R-F17 — flow.book_tilt.band.v2
# =================================================================================================


@dataclass(frozen=True)
class BookSnapshotObservation:
    """A validated local book snapshot for F17 v2: the machine bands + sums it INTERNALLY.

    ``bid_levels``/``ask_levels`` are tuples of ``(price_ticks, qty_steps)`` pairs (raw-typed,
    int64-guarded at the boundary — never caller-supplied pre-banded sums). ``sequence`` is the
    book-sequence identity stamped on the atom; ``event_time_us``/``eval_time_us`` drive the
    optional freshness (BOOK_TILT_TTL) check.
    """

    bid_levels: tuple
    ask_levels: tuple
    sequence: int
    event_time_us: int
    eval_time_us: int
    source_event_id: str


_F17_STATE_KEYS = ("last_seq",)


def f17_initial_state() -> dict:
    """Cold F17 state: no prior book sequence."""
    return {"last_seq": None}


def _min_depth_face(value: object) -> tuple:
    """BOOK_TILT_MIN_DEPTH_QUOTE_ATOMS: NOT_RATIFIED sentinel, or a ratified STRICTLY-positive int.

    The depth-floor binding law is ``min > 0``: a ratified ``min <= 0`` is REFUSE_CONFIG (never a
    silent admission of a zero denominator); the proposed value is never hardcoded active here.
    """
    if value == common.NOT_RATIFIED:
        return ("unratified", None)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RefuseConfig(
            f"{PARAM_BOOK_TILT_MIN_DEPTH} must be a ratified exact int > 0 or the "
            f"{common.NOT_RATIFIED!r} sentinel, got {value!r}")
    guarded = exact.guard_int64(value, formula_id=FORMULA_F17, field="book_tilt_min_depth")
    if guarded <= 0:
        raise RefuseConfig(
            f"{PARAM_BOOK_TILT_MIN_DEPTH} must be ratified STRICTLY POSITIVE (the depth-floor "
            f"binding law); min <= 0 is REFUSE_CONFIG, got {guarded}")
    return ("ratified", guarded)


def _band_face(value: object) -> int:
    """BOOK_TILT_BAND_TICKS: a ratified exact int >= 0 (0 = only the best level)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise RefuseConfig(
            f"{PARAM_BOOK_TILT_BAND} must be an exact int >= 0, got {value!r}")
    guarded = exact.guard_int64(value, formula_id=FORMULA_F17, field="book_tilt_band_ticks")
    if guarded < 0:
        raise RefuseConfig(f"{PARAM_BOOK_TILT_BAND} must be >= 0, got {guarded}")
    return guarded


def _ttl_face(value: object) -> tuple:
    """BOOK_TILT_TTL (optional, PROPOSED_MUST_RATIFY): ratified int > 0, or unratified."""
    if value == common.NOT_RATIFIED:
        return ("unratified", None)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RefuseConfig(
            f"{PARAM_BOOK_TILT_TTL} must be a ratified exact int > 0 or the "
            f"{common.NOT_RATIFIED!r} sentinel, got {value!r}")
    guarded = exact.guard_int64(value, formula_id=FORMULA_F17, field="book_tilt_ttl_us")
    if guarded <= 0:
        raise RefuseConfig(f"{PARAM_BOOK_TILT_TTL} must be > 0, got {guarded}")
    return ("ratified", guarded)


def _validated_levels(levels: object, name: str) -> tuple:
    if not isinstance(levels, (tuple, list)):
        raise EnvelopeRejected(f"{name} must be a tuple of (price_ticks, qty_steps) pairs")
    out = []
    for level in levels:
        if not isinstance(level, (tuple, list)) or len(level) != 2:
            raise EnvelopeRejected(f"{name} entries must be (price_ticks, qty_steps) pairs")
        price = _guarded_int(level[0], f"{name}.price_ticks", FORMULA_F17)
        qty = _guarded_int(level[1], f"{name}.qty_steps", FORMULA_F17)
        out.append((price, qty))
    return tuple(out)


def _validated_f17_env(env: object) -> BookSnapshotObservation:
    if type(env) is not BookSnapshotObservation:
        raise EnvelopeRejected(
            "F17 v2 consumes exactly a BookSnapshotObservation (exact type), got "
            f"{type(env).__name__}")
    _validated_levels(env.bid_levels, "bid_levels")
    _validated_levels(env.ask_levels, "ask_levels")
    _nonneg_int(env.sequence, "sequence", FORMULA_F17)
    _nonneg_int(env.event_time_us, "event_time_us", FORMULA_F17)
    _nonneg_int(env.eval_time_us, "eval_time_us", FORMULA_F17)
    _nonempty_str(env.source_event_id, "source_event_id")
    return env


def _banded_depth(levels: tuple, best_price: int, band_ticks: int) -> int:
    """Sum price_ticks x qty_steps over levels within ``band_ticks`` of ``best_price`` (inclusive)."""
    total = 0
    for price, qty in levels:
        if abs(price - best_price) <= band_ticks:  # boundary INCLUSIVE
            total += exact.guard_int64(price * qty, formula_id=FORMULA_F17, field="level_atoms")
    return exact.guard_int64(total, formula_id=FORMULA_F17, field="banded_depth")


def evaluate_f17(caps: object, env: object, state: object) -> TransitionResult:
    """F17 v2 §C.3 entrypoint — book tilt over machine-built bands, positive depth floor."""
    caps = _validated_caps(
        caps, formula_id=FORMULA_F17,
        required=(PARAM_BOOK_TILT_MIN_DEPTH, PARAM_BOOK_TILT_BAND),
        optional=(PARAM_BOOK_TILT_TTL,))
    min_depth_face = _min_depth_face(caps[PARAM_BOOK_TILT_MIN_DEPTH].value)
    band_ticks = _band_face(caps[PARAM_BOOK_TILT_BAND].value)
    ttl_face = (_ttl_face(caps[PARAM_BOOK_TILT_TTL].value)
                if PARAM_BOOK_TILT_TTL in caps else ("unratified", None))
    obs = _validated_f17_env(env)

    # PROPOSED_MUST_RATIFY refusal posture (SAFE_HOLD): the depth floor is not ratified, so the
    # division may not run and NO state mutates — never a fabricated minimum (the F06/F09 posture).
    if min_depth_face[0] != "ratified":
        return TransitionResult(state=state, events=(common.abstention(
            F17_UNAVAILABLE_MIN_DEPTH, formula=FORMULA_F17,
            detail=f"{PARAM_BOOK_TILT_MIN_DEPTH} is PROPOSED_MUST_RATIFY and not ratified; F17 "
                   "holds SAFE_HOLD with zero state mutation",
            refs={"source_event_id": obs.source_event_id,
                  "parameter": PARAM_BOOK_TILT_MIN_DEPTH}),))
    min_depth = min_depth_face[1]

    state = _state_snapshot(state, _F17_STATE_KEYS)
    prior_seq = state["last_seq"]
    if prior_seq is not None and obs.sequence <= prior_seq:
        raise common.StructureLawError(
            f"F17 book sequence must strictly increase: got {obs.sequence} after {prior_seq}")

    refs = {"source_event_id": obs.source_event_id, "book_sequence": obs.sequence}
    # A truly empty book (no levels either side) is undefined; a ONE-sided book is not empty — it
    # is fully tilted (all-bid -> +1, all-ask -> -1).
    if not obs.bid_levels and not obs.ask_levels:
        state["last_seq"] = obs.sequence
        return TransitionResult(state=state, events=(common.abstention(
            F17_EMPTY_BOOK, formula=FORMULA_F17,
            detail="the book has no levels on either side; tilt is undefined (empty book)",
            refs=refs),))
    for price, qty in tuple(obs.bid_levels) + tuple(obs.ask_levels):
        if qty <= 0:
            state["last_seq"] = obs.sequence
            return TransitionResult(state=state, events=(common.abstention(
                F17_INVALID_BOOK, formula=FORMULA_F17,
                detail="a book level carries a non-positive quantity (invalid book)", refs=refs),))
    best_bid = max((price for price, _ in obs.bid_levels), default=None)
    best_ask = min((price for price, _ in obs.ask_levels), default=None)
    if best_bid is not None and best_ask is not None and not best_bid < best_ask:
        state["last_seq"] = obs.sequence
        return TransitionResult(state=state, events=(common.abstention(
            F17_CROSSED_BOOK, formula=FORMULA_F17,
            detail="the book is crossed or locked (best_bid >= best_ask)", refs=refs),))
    if ttl_face[0] == "ratified" and obs.eval_time_us - obs.event_time_us > ttl_face[1]:
        state["last_seq"] = obs.sequence
        return TransitionResult(state=state, events=(common.abstention(
            F17_STALE, formula=FORMULA_F17,
            detail="the book snapshot is older than BOOK_TILT_TTL; tilt is stale",
            refs={**refs, "age_us": obs.eval_time_us - obs.event_time_us,
                  "book_tilt_ttl_us": ttl_face[1]}),))

    bid_depth = _banded_depth(obs.bid_levels, best_bid, band_ticks) if best_bid is not None else 0
    ask_depth = _banded_depth(obs.ask_levels, best_ask, band_ticks) if best_ask is not None else 0
    denominator = exact.guard_int64(
        bid_depth + ask_depth, formula_id=FORMULA_F17, field="book_tilt_denominator")
    state["last_seq"] = obs.sequence
    if denominator < min_depth:
        return TransitionResult(state=state, events=(common.abstention(
            F17_INSUFFICIENT_DEPTH, formula=FORMULA_F17,
            detail=f"combined banded quote depth {denominator} is below the ratified minimum "
                   f"{min_depth}",
            refs={**refs, "denominator": denominator, "min_depth": min_depth}),))
    if denominator <= 0:  # unreachable while min_depth > 0; defense in depth (the floor ran first)
        return TransitionResult(state=state, events=(common.abstention(
            F17_ZERO_DENOMINATOR, formula=FORMULA_F17,
            detail="combined quote depth is zero; no ratified minimum may admit a zero denominator",
            refs={**refs, "denominator": denominator}),))
    numerator = exact.guard_int64(
        bid_depth - ask_depth, formula_id=FORMULA_F17, field="book_tilt_numerator")
    tilt = exact.rational(numerator, denominator)
    event = {
        "event_kind": FEATURE,
        "formula": FORMULA_F17,
        "formula_version": F17_FORMULA_VERSION,
        "tilt": list(tilt),
        "bid_quote_depth": bid_depth,
        "ask_quote_depth": ask_depth,
        "band_ticks": band_ticks,
        "book_sequence": obs.sequence,
        "confirmed_by_event_id": obs.source_event_id,
    }
    return TransitionResult(state=state, events=(event,))


# =================================================================================================
# The fold used identically for live and replay (one transition implementation per formula)
# =================================================================================================


@dataclass(frozen=True)
class FlowRunResult:
    """Detached fold result: final state, ordered events, exact-duplicate count."""

    final_state: dict
    events: tuple
    duplicate_count: int


def _f15_fingerprint(env: object) -> bytes | None:
    if type(env) is TradeObservation:
        from ..e01_interface import ValidatedTrade
        if type(env.trade) is not ValidatedTrade:
            return None
        body = {"kind": "TRADE", "trade_id": env.trade.trade_id,
                "revision": env.trade.revision, "event_time_us": env.trade.event_time_us,
                "aggressor_side": env.trade.aggressor_side, "venue": env.venue,
                "instrument": env.instrument, "price_ticks": env.price_ticks,
                "qty_steps": env.qty_steps, "metadata_revision": env.metadata_revision,
                "source_event_id": env.source_event_id}
    elif type(env) is WindowClose:
        body = {"kind": "WINDOW", "w_start": env.w_start, "w_end": env.w_end,
                "expected_trades": env.expected_trades, "watermark_us": env.watermark_us,
                "source_event_id": env.source_event_id}
    else:
        return None
    try:
        return canonical_json(body)
    except (CanonicalError, TypeError):
        return None


def _f16_fingerprint(env: object) -> bytes | None:
    if type(env) is not BookUpdateObservation:
        return None
    body = {"sequence": env.sequence, "event_time_us": env.event_time_us,
            "eval_time_us": env.eval_time_us, "best_bid_price_ticks": env.best_bid_price_ticks,
            "best_bid_qty_steps": env.best_bid_qty_steps,
            "best_ask_price_ticks": env.best_ask_price_ticks,
            "best_ask_qty_steps": env.best_ask_qty_steps,
            "watermark_complete": env.watermark_complete, "source_event_id": env.source_event_id}
    try:
        return canonical_json(body)
    except (CanonicalError, TypeError):
        return None


def _f17_fingerprint(env: object) -> bytes | None:
    if type(env) is not BookSnapshotObservation:
        return None
    body = {"bid_levels": [list(x) for x in env.bid_levels],
            "ask_levels": [list(x) for x in env.ask_levels], "sequence": env.sequence,
            "event_time_us": env.event_time_us, "eval_time_us": env.eval_time_us,
            "source_event_id": env.source_event_id}
    try:
        return canonical_json(body)
    except (CanonicalError, TypeError):
        return None


def _fold(evaluate_fn, initial_state_fn, fingerprint_fn, state_keys, caps, inputs, initial):
    state = initial if initial is not None else initial_state_fn()
    state = _state_snapshot(state, state_keys)
    events: list = []
    seen: set = set()
    duplicate_count = 0
    for env in inputs:
        fingerprint = fingerprint_fn(env)
        if fingerprint is not None and fingerprint in seen:
            duplicate_count += 1
            continue
        if fingerprint is not None:
            seen.add(fingerprint)
        result = evaluate_fn(caps, env, state)
        state = result.state
        events.extend(result.events)
    return FlowRunResult(
        final_state=loads_canonical(canonical_json(state)),
        events=tuple(events),
        duplicate_count=duplicate_count,
    )


def run_f15(caps: object, inputs: list, initial: dict | None = None) -> FlowRunResult:
    """Fold F15 inputs through :func:`evaluate_f15` (live == replay); exact duplicates skipped."""
    return _fold(evaluate_f15, f15_initial_state, _f15_fingerprint, _F15_STATE_KEYS,
                 caps, inputs, initial)


def run_f16(caps: object, inputs: list, initial: dict | None = None) -> FlowRunResult:
    """Fold F16 inputs through :func:`evaluate_f16` (live == replay); exact duplicates skipped."""
    return _fold(evaluate_f16, f16_initial_state, _f16_fingerprint, _F16_STATE_KEYS,
                 caps, inputs, initial)


def run_f17(caps: object, inputs: list, initial: dict | None = None) -> FlowRunResult:
    """Fold F17 inputs through :func:`evaluate_f17` (live == replay); exact duplicates skipped."""
    return _fold(evaluate_f17, f17_initial_state, _f17_fingerprint, _F17_STATE_KEYS,
                 caps, inputs, initial)
