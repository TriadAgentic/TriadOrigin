"""F10 — ``fvg.three_bar.closed.v3`` — the gap-reset-first FVG lifecycle (repair R-F10).

TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12 §R-F10. Supersedes ``fvg.three_bar.closed.v2``
(:mod:`triad_origin.structures.fvg_registry`, retired with a ``RETIRED_DEFECTIVE{defect_ref=R-F10}``
banner; bytes preserved). NEVER-BLEND: v2 rows keep their version tag forever; every v3 zone,
event and state row carries :data:`FORMULA_VERSION`, and :func:`evaluate` refuses a state stamped
with any other version.

**The defect this repairs.** v2 evaluated existing zones for touch/fill BEFORE the sequence-gap
reset, so a pre-gap zone could be "filled" across missing bars. The exact INVALIDATED path, the
midpoint/penetration state, the TTL binding and compaction were absent.

**CORRECTED LAW (spec §R-F10, normative).**

Formation (unchanged v2 math) — bars ``a = t-2``, ``b = t-1``, ``c = t``, all VALID_BAR,
consecutive ordinals::

    bull: gap_ticks = L_c - H_a; qualifies iff gap_ticks >= min_gap_ticks AND gap_ticks > 0;
          zone = [z0, z1] = [H_a, L_c]
    bear: gap_ticks = L_a - H_c; zone = [z0, z1] = [H_c, L_a]

Penetration (bull; touch price ``p`` = bar low per the FVG_TOUCH_PRICE_SOURCE binding)::

    pen = clamp( (z1 - min(p, z1)) / (z1 - z0), 0, 1 )     stored as a reduced rational
    bear mirror: pen = clamp( (max(p, z0) - z0) / (z1 - z0), 0, 1 ) with p = bar high

States: ``FRESH -> TOUCHED -> PARTIAL (0 < pen < 1/2) -> MIDPOINT_FILLED (pen >= 1/2)
-> FILLED (pen = 1, terminal) | EXPIRED (terminal) | INVALIDATED (terminal)``. Progression is
monotone; a single bar may advance multiple stages (one event carrying the final state). Per the
ratified T4 row, **edge contact is TOUCHED with pen = 0** (bull: ``p <= z1`` inclusive; bear:
``p >= z0`` inclusive) — the ratified test row wins over the diagram's ``TOUCHED (pen>0)`` gloss.

EVALUATION ORDER PER EVENT (normative; RATIFY_WITH_THIS_REPAIR):

1. **CONTINUITY FIRST** — if the event carries GAP / data_revision-gap / source-sequence
   discontinuity since the last processed ordinal for this partition: every non-terminal zone
   -> ``INVALIDATED{SEQUENCE_GAP}``. STOP. No touch/fill may be computed on or across the
   discontinuity (the current bar only seeds the next 3-bar window).
2. **INVALIDATION** — opposing-structure invalidation per the binding rule, defining-bar
   revision. Inside the INVALIDATED class the declared tie rule is: DEFINING_BAR_REVISION is
   checked before OPPOSING_BREAK (first match names the reason).
3. **EXPIRY** — ``bars_elapsed`` since formation availability ``>= FVG_TTL_BARS`` -> EXPIRED
   (inclusive at TTL).
4. **TERMINAL FILL then progressions**, monotone by the bar's extreme penetration.
5. **FORMATION** of new zones from ``(a, b, c)`` ending at this bar. Same-bar-retest ban: bar
   ``c`` can never be its own retest; the earliest touch source is ``c+1`` or later — enforced
   STRUCTURALLY by the §1.4 availability law (a zone's ``availability_time_us`` is its formation
   bar's ``bucket_end_us``, and ``exact.availability_allows`` refuses any bar whose bucket start
   precedes it — bar ``c``'s own bucket start always does).

Same-event multi-transition precedence rides :class:`triad_origin.exact.TransitionPrecedence`
(``INVALIDATED > EXPIRED > TERMINAL > PROGRESSION``) via :func:`exact.dominant_transition` — the
§1.4 global order instantiated (spec tests T8/T9).

**BINDINGS (all five REQUIRED as verified capabilities — the ratification posture).**
:func:`evaluate` consumes an authenticated capability per parameter; no value below is ever a
code default. A missing capability is the NAMED refusal ``F10_BINDING_NOT_RATIFIED{parameter}``
— the mechanism exists, the value activates only through ratification (spec §0 rule 1):

* ``PAR-044`` (FVG_MIN_GAP, existing) — the declared rational rule; only the exact declared
  byte-string ``common.DECLARED_BOS_CLOSE_BUFFER`` is admitted, presented either as the plain
  string or wrapped as ``{"declared_rule": <the same bytes>}`` (the wrapper form exists because
  the bindings sentinel law treats a bare ``*`` in an ACTIVE ``declared_value`` as a wildcard —
  a registry-migration decision recorded for the orchestrator; both admitted forms denote the
  ONE declared rule and anything else refuses).
* ``FVG_TTL_BARS`` — PROPOSED_MUST_RATIFY (proposed 96 formation-timeframe bars; NOT hardcoded
  here). Boundary law: EXPIRED when ``bars_elapsed >= TTL`` — inclusive at TTL.
* ``FVG_TOUCH_PRICE_SOURCE`` — RATIFY_WITH_THIS_REPAIR; only the exact declared byte-string
  :data:`DECLARED_TOUCH_PRICE_SOURCE` (``bar_low(bull)/bar_high(bear)``) is admitted.
* ``FVG_INVALIDATION_RULE`` — PROPOSED_MUST_RATIFY; only the exact declared byte-string
  :data:`DECLARED_INVALIDATION_RULE` is admitted. Reading implemented for the proposed rule: an
  ACCEPTED opposing F09 break whose close is STRICTLY through the zone's far edge (bull far edge
  ``z0``: ``close < z0``; bear far edge ``z1``: ``close > z1``; edge contact is not "through").
* ``FVG_MAX_OPEN_PER_PARTITION`` — PROPOSED_MUST_RATIFY (proposed 64; NOT hardcoded here).
  Overflow behavior ``REFUSED_CAPACITY``: the candidate zone is recorded as an AUDIT FACT event,
  never a zone, and existing zones are never silently evicted.

**§C.3 entrypoint law.** ``evaluate(caps, env, state, ...)`` where ``caps`` maps
``parameter_id -> triad_origin.bindings.VerifiedCapability`` (exact-type check per entry; the
entry's ``formula_id`` must equal ``F10`` and its ``parameter_id`` the key) and ``env`` is the
E01 boundary type ValidatedBar (exact-type check). A hand-built dict/int in either seat raises a
typed rejection BEFORE any state transition. Raw-dict parameters and the raw test/replay
parameter accessor of :mod:`triad_origin.transition` never appear on this path.

**Universal laws.** §1.1 — only bars that passed VALID_BAR (the E01 boundary) enter; a
quarantined bar is dropped by the caller (journaling the quarantine record) and acts EXACTLY as
a GAP: the machine sees a non-consecutive ordinal (or an explicit ``sequence_discontinuity``)
and order step (1) invalidates every open zone before any touch. §1.2 — every persisted integer
is int64-guarded; the formula's largest derived product is ``gap_ticks`` (guarded at formation —
one beyond int64 is the ``QUARANTINE_OVERFLOW`` record, no zone) and the stored ``pen`` pair
(re-guarded at the storage boundary; ``bars_elapsed`` is structurally bounded by the int64 TTL
because a zone expires at TTL). §1.3 — ``pen`` is a reduced rational pair with ``den > 0``, all
comparisons by integer cross-multiplication (:mod:`triad_origin.exact`); no float exists on any
path here. §1.4 — availability gating via :func:`exact.availability_allows`, precedence via
:class:`exact.TransitionPrecedence`. No clock is read: ``bucket_start_us`` / ``bucket_end_us``
are injected event facts.

**Compaction.** A zone that reaches a terminal state (FILLED / EXPIRED / INVALIDATED) emits its
terminal event and leaves the working state in the same transition — the event tape is the
record; the state carries open (non-terminal) zones only, so the capacity law counts exactly the
open set and a terminal zone can structurally never re-emit.

**Determinism / replay.** :func:`evaluate` is the ONE transition implementation: a pure function
of ``(caps values, env, state, injected event facts)``. Live and replay call it identically;
restart = resume from any canonical-JSON state snapshot (prefix/restart parity is test-pinned).
Missing-ATR on a raw gap candidate stays the NAMED abstention ``F10_NO_ATR`` (v2 law retained).
"""

from __future__ import annotations

from dataclasses import dataclass

from .. import exact
from ..bindings import VerifiedCapability
from ..canonical import INT64_MAX
from ..e01_interface import ValidatedBar
from ..transition import State, TransitionResult
from . import common

FORMULA_F10 = "F10"
FORMULA_VERSION = "fvg.three_bar.closed.v3"
RETIRED_PREDECESSOR_VERSION = "fvg.three_bar.closed.v2"

# --- the five binding parameters (capability keys) ------------------------------------------------
PARAM_MIN_GAP_RULE = "PAR-044"                       # existing registry row (FVG_MIN_GAP)
PARAM_TTL_BARS = "FVG_TTL_BARS"                      # PROPOSED_MUST_RATIFY (proposed 96)
PARAM_TOUCH_PRICE_SOURCE = "FVG_TOUCH_PRICE_SOURCE"  # RATIFY_WITH_THIS_REPAIR
PARAM_INVALIDATION_RULE = "FVG_INVALIDATION_RULE"    # PROPOSED_MUST_RATIFY
PARAM_MAX_OPEN_PER_PARTITION = "FVG_MAX_OPEN_PER_PARTITION"  # PROPOSED_MUST_RATIFY (proposed 64)
REQUIRED_PARAMETERS = (
    PARAM_MIN_GAP_RULE,
    PARAM_TTL_BARS,
    PARAM_TOUCH_PRICE_SOURCE,
    PARAM_INVALIDATION_RULE,
    PARAM_MAX_OPEN_PER_PARTITION,
)

# The exact declared byte-strings this module can execute (any other value refuses — the
# declared-string discipline of structures.common; the min-gap rule reuses the common constant).
DECLARED_TOUCH_PRICE_SOURCE = "bar_low(bull)/bar_high(bear)"
DECLARED_INVALIDATION_RULE = "accepted opposing F09 break through the zone's far edge"

KIND_BULLISH = "bullish"
KIND_BEARISH = "bearish"

STATE_FRESH = "FRESH"
STATE_TOUCHED = "TOUCHED"
STATE_PARTIAL = "PARTIAL"
STATE_MIDPOINT_FILLED = "MIDPOINT_FILLED"
STATE_FILLED = "FILLED"
STATE_EXPIRED = "EXPIRED"
STATE_INVALIDATED = "INVALIDATED"
_PROGRESSION_RANK = {
    STATE_FRESH: 0,
    STATE_TOUCHED: 1,
    STATE_PARTIAL: 2,
    STATE_MIDPOINT_FILLED: 3,
    STATE_FILLED: 4,
}

ZONE_FORMED = "ZONE_FORMED"
ZONE_PROGRESSED = "ZONE_PROGRESSED"
ZONE_FILLED = "ZONE_FILLED"
ZONE_EXPIRED = "ZONE_EXPIRED"
ZONE_INVALIDATED = "ZONE_INVALIDATED"
REFUSED_CAPACITY = "REFUSED_CAPACITY"

REASON_SEQUENCE_GAP = "SEQUENCE_GAP"
REASON_DEFINING_BAR_REVISION = "DEFINING_BAR_REVISION"
REASON_OPPOSING_BREAK = "OPPOSING_BREAK"

REFUSAL_NOT_RATIFIED = "F10_BINDING_NOT_RATIFIED"
REFUSAL_UNDECLARED_VALUE = "F10_UNDECLARED_BINDING_VALUE"

_ZERO = (0, 1)
_HALF = (1, 2)
_ONE = (1, 1)


class FvgEntrypointRejection(TypeError):
    """§C.3 boundary rejection at the ``evaluate`` surface — BEFORE any state transition.

    Raised for a hand-built dict/int (or any non-capability object) in a ``caps`` seat, a raw
    dict (or any non-boundary object) in the ``env`` seat, a capability whose ``formula_id`` /
    ``parameter_id`` does not match, an unknown parameter key, or a malformed opposing-break
    fact. Typed and fail-closed; the machine never sees the event.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(f"F10_ENTRYPOINT_REJECTED: {detail}")
        self.detail = detail


class FvgBindingRefusal(ValueError):
    """The NAMED binding refusal (spec §0 rule 1 — the refusal that stands until ratified).

    ``F10_BINDING_NOT_RATIFIED{parameter}`` when a required capability is absent from ``caps``
    (nothing here defaults a proposed value into activity), and
    ``F10_UNDECLARED_BINDING_VALUE{parameter}`` when a presented capability carries a value this
    module does not implement (only the exact declared byte-strings / exact positive integers
    are executable — a different value is a different law and refuses).
    """

    def __init__(self, reason_code: str, parameter_id: str, detail: str) -> None:
        super().__init__(f"{reason_code}:{parameter_id}: {detail}")
        self.reason_code = reason_code
        self.parameter_id = parameter_id
        self.detail = detail


@dataclass(frozen=True)
class OpposingBreak:
    """An ACCEPTED F09 break fact presented to evaluation-order step (2).

    ``direction`` is the break's direction (``LONG``/``SHORT``); ``close_ticks`` the accepted
    break close. Only an accepted break is ever presented — the producer (F09,
    ``break.bar_close.v2``) owns acceptance. Validated at construction: an unknown direction or
    a non-int64 close fails closed before the fact can reach any zone.
    """

    direction: str
    close_ticks: int

    def __post_init__(self) -> None:
        common.require_direction(self.direction)
        exact.guard_int64(
            common.require_int(self.close_ticks, "opposing_break.close_ticks"),
            formula_id=FORMULA_F10, field="opposing_break.close_ticks")


# =================================================================================================
# §C.3 boundary checks — every rejection is typed and fires before any state transition.
# =================================================================================================


def _require_caps(caps: object) -> dict:
    """Exact-shape check of the capability map: a plain dict of exactly the five required
    parameter ids, each seat holding a :class:`VerifiedCapability` (exact type — a subclass, a
    look-alike dataclass, a dict or an int is rejected) whose ``formula_id`` is ``F10`` and
    whose ``parameter_id`` equals its key."""
    if type(caps) is not dict:
        raise FvgEntrypointRejection(
            f"caps must be a dict mapping parameter_id -> verified capability, "
            f"got {type(caps).__name__}")
    unknown = sorted(set(caps) - set(REQUIRED_PARAMETERS))
    if unknown:
        raise FvgEntrypointRejection(f"unknown parameter keys for F10: {unknown}")
    entries: dict = {}
    for parameter_id in REQUIRED_PARAMETERS:
        if parameter_id not in caps:
            raise FvgBindingRefusal(
                REFUSAL_NOT_RATIFIED, parameter_id,
                "the required binding is not present as a verified capability; the F10 "
                "mechanism is built but the value activates only through ratification "
                "(spec §0 rule 1 — never a code default)")
        entry = caps[parameter_id]
        if type(entry) is not VerifiedCapability:
            raise FvgEntrypointRejection(
                f"caps[{parameter_id!r}] must be a VerifiedCapability minted by "
                f"transition.require_bundle, got {type(entry).__name__}")
        if entry.formula_id != FORMULA_F10:
            raise FvgEntrypointRejection(
                f"caps[{parameter_id!r}] was verified for formula {entry.formula_id!r}, "
                f"not {FORMULA_F10!r}")
        if entry.parameter_id != parameter_id:
            raise FvgEntrypointRejection(
                f"caps[{parameter_id!r}] resolves parameter {entry.parameter_id!r} — the key "
                f"and the verified parameter must agree")
        entries[parameter_id] = entry
    return entries


def _require_env(env: object) -> ValidatedBar:
    if type(env) is not ValidatedBar:
        raise FvgEntrypointRejection(
            f"env must be the E01 boundary type ValidatedBar, got {type(env).__name__} "
            f"(raw market data never enters a formula — spec §C.3)")
    return env


def _min_gap_rule_value(entry: VerifiedCapability) -> str:
    value = entry.value
    if isinstance(value, str) and value == common.DECLARED_BOS_CLOSE_BUFFER:
        return common.DECLARED_BOS_CLOSE_BUFFER
    if (type(value) is dict and sorted(value) == ["declared_rule"]
            and value["declared_rule"] == common.DECLARED_BOS_CLOSE_BUFFER):
        return common.DECLARED_BOS_CLOSE_BUFFER
    raise FvgBindingRefusal(
        REFUSAL_UNDECLARED_VALUE, PARAM_MIN_GAP_RULE,
        f"only the exact declared rule {common.DECLARED_BOS_CLOSE_BUFFER!r} is executable "
        f"(plain or wrapped as {{'declared_rule': ...}}); got {value!r}")


def _positive_int64_value(entry: VerifiedCapability, parameter_id: str) -> int:
    """A ratified count value: an exact positive int64, presented as an exact int or as the
    canonical decimal-integer string a registry ``declared_value`` conventionally carries."""
    value = entry.value
    if isinstance(value, str):
        if not value.isdigit() or (len(value) > 1 and value.startswith("0")):
            raise FvgBindingRefusal(
                REFUSAL_UNDECLARED_VALUE, parameter_id,
                f"declared value must be a canonical decimal integer, got {value!r}")
        number = int(value)
    elif isinstance(value, bool) or not isinstance(value, int):
        raise FvgBindingRefusal(
            REFUSAL_UNDECLARED_VALUE, parameter_id,
            f"declared value must be an exact positive integer, got {type(value).__name__}")
    else:
        number = value
    if number <= 0 or number > INT64_MAX:
        raise FvgBindingRefusal(
            REFUSAL_UNDECLARED_VALUE, parameter_id,
            f"declared value must be a positive signed int64, got {number}")
    return number


def _exact_declared_string(entry: VerifiedCapability, parameter_id: str, declared: str) -> str:
    if isinstance(entry.value, str) and entry.value == declared:
        return declared
    raise FvgBindingRefusal(
        REFUSAL_UNDECLARED_VALUE, parameter_id,
        f"only the exact declared byte-string {declared!r} is executable, got {entry.value!r}")


def _require_state(state: object) -> State:
    if state is None:
        return initial_state()
    if not isinstance(state, dict):
        raise common.StructureLawError(
            f"F10 state must be an object or None, got {type(state).__name__}")
    version = state.get("formula_version")
    if version != FORMULA_VERSION:
        raise common.StructureLawError(
            f"never-blend: state carries formula_version {version!r}; {FORMULA_VERSION} "
            f"consumes only its own state rows (v2 rows keep their tag forever)")
    for key in ("last_ordinal", "last_bar_identity", "recent", "zones"):
        if key not in state:
            raise common.StructureLawError(f"F10 state is missing required key {key!r}")
    return state


def _require_identities(value: object) -> set:
    if not isinstance(value, (tuple, list)):
        raise common.StructureLawError(
            f"revised_bar_identities must be a tuple/list of bar identities, "
            f"got {type(value).__name__}")
    out: set = set()
    for item in value:
        if not isinstance(item, str) or not item:
            raise common.StructureLawError(
                "revised_bar_identities entries must be non-empty strings")
        out.add(item)
    return out


# =================================================================================================
# Pure lifecycle pieces.
# =================================================================================================


def initial_state() -> State:
    return {
        "formula_version": FORMULA_VERSION,
        "last_ordinal": None,
        "last_bar_identity": None,
        "recent": [],
        "zones": [],
    }


def _touch_price(kind: str, bar: ValidatedBar) -> int:
    """FVG_TOUCH_PRICE_SOURCE = bar_low(bull)/bar_high(bear)."""
    return bar.low_ticks if kind == KIND_BULLISH else bar.high_ticks


def _contact(kind: str, z0: int, z1: int, price: int) -> bool:
    """T4 ratified law: edge contact is TOUCHED with pen = 0 — inclusive at the near edge."""
    return price <= z1 if kind == KIND_BULLISH else price >= z0


def _bar_pen(kind: str, z0: int, z1: int, price: int) -> tuple:
    """The clamped penetration of one bar's touch price, as a reduced rational (§1.3)."""
    den = z1 - z0  # > 0 by formation law (gap_ticks > 0)
    if kind == KIND_BULLISH:
        num = z1 - min(price, z1)
    else:
        num = max(price, z0) - z0
    if num > den:
        num = den  # clamp(..., 0, 1); the lower clamp is structural (min/max above)
    return exact.rational(num, den)


def _state_for(pen: tuple, contacted: bool) -> str:
    if exact.rational_ge(pen, _ONE):
        return STATE_FILLED
    if exact.rational_ge(pen, _HALF):
        return STATE_MIDPOINT_FILLED
    if exact.rational_gt(pen, _ZERO):
        return STATE_PARTIAL
    return STATE_TOUCHED if contacted else STATE_FRESH


def _break_through_far_edge(zone: dict, brk: OpposingBreak) -> bool:
    """The proposed FVG_INVALIDATION_RULE reading: an accepted OPPOSING break whose close is
    STRICTLY through the zone's far edge (bull far edge z0, bear far edge z1)."""
    if brk.direction != common.opposite(zone["direction"]):
        return False
    if zone["kind"] == KIND_BULLISH:
        return brk.close_ticks < zone["z0_ticks"]
    return brk.close_ticks > zone["z1_ticks"]


def _stored_pen(pen: tuple) -> list:
    """§1.2 re-check at the storage boundary; state stores the pair as a two-element list."""
    num = exact.guard_int64(pen[0], formula_id=FORMULA_F10, field="pen.num")
    den = exact.guard_int64(pen[1], formula_id=FORMULA_F10, field="pen.den")
    return [num, den]


def _new_zone(kind: str, z0: int, z1: int, gap_ticks: int, min_gap_ticks: int, atr: int,
              origin_bar_identities: list, formation_ordinal: int,
              availability_time_us: int) -> dict:
    return {
        "zone_id": f"fvg3:{origin_bar_identities[-1]}:{formation_ordinal}:{kind}",
        "formula_version": FORMULA_VERSION,
        "kind": kind,
        "direction": common.LONG if kind == KIND_BULLISH else common.SHORT,
        "z0_ticks": z0,
        "z1_ticks": z1,
        "gap_ticks": gap_ticks,
        "min_gap_ticks": min_gap_ticks,
        "atr14_ticks": atr,
        "pen": [0, 1],
        "state": STATE_FRESH,
        "bars_elapsed": 0,
        "availability_time_us": availability_time_us,
        "origin_bar_identities": list(origin_bar_identities),
        "formation_ordinal": formation_ordinal,
    }


def _zone_event(event_kind: str, zone: dict, bar: ValidatedBar, ordinal: int,
                bars_elapsed: int, **extra: object) -> dict:
    event = {
        "event_kind": event_kind,
        "formula": FORMULA_F10,
        "formula_version": FORMULA_VERSION,
        "zone_id": zone["zone_id"],
        "kind": zone["kind"],
        "direction": zone["direction"],
        "bar_identity": bar.bar_identity,
        "bar_ordinal": ordinal,
        "bars_elapsed": bars_elapsed,
        "pen": list(zone["pen"]),
    }
    event.update(extra)
    return event


def _step_zone(zone: dict, bar: ValidatedBar, ordinal: int, bucket_start_us: int, ttl: int,
               revised: set, brk: "OpposingBreak | None") -> tuple:
    """Order steps (2)-(4) for ONE open zone on ONE in-continuity event.

    Returns ``(zone_or_None, event_or_None)`` — ``None`` zone means the zone went terminal and
    compacts out of the working state. The winning transition class on a same-event tie is
    resolved through the §1.4 global order (:func:`exact.dominant_transition`).
    """
    # (2) invalidation candidates — declared in-class tie rule: revision before opposing break.
    reason = None
    if revised and revised & set(zone["origin_bar_identities"]):
        reason = REASON_DEFINING_BAR_REVISION
    elif brk is not None and _break_through_far_edge(zone, brk):
        reason = REASON_OPPOSING_BREAK
    aged = zone["bars_elapsed"] + 1
    classes = []
    if reason is not None:
        classes.append(exact.TransitionPrecedence.INVALIDATED)
    # (3) expiry — inclusive at TTL: bars_elapsed >= FVG_TTL_BARS.
    if aged >= ttl:
        classes.append(exact.TransitionPrecedence.EXPIRED)
    # (4) fill / progression — only for a bar the §1.4 availability law admits.
    touch = None
    if exact.availability_allows(zone["availability_time_us"], bucket_start_us):
        price = _touch_price(zone["kind"], bar)
        if _contact(zone["kind"], zone["z0_ticks"], zone["z1_ticks"], price):
            old_pen = (zone["pen"][0], zone["pen"][1])
            bar_pen = _bar_pen(zone["kind"], zone["z0_ticks"], zone["z1_ticks"], price)
            new_pen = bar_pen if exact.rational_gt(bar_pen, old_pen) else old_pen
            new_state = _state_for(new_pen, contacted=True)
            if _PROGRESSION_RANK[new_state] < _PROGRESSION_RANK[zone["state"]]:
                new_state = zone["state"]  # monotone — a lesser derived stage never regresses
            if new_state == STATE_FILLED:
                touch = (exact.TransitionPrecedence.TERMINAL, new_pen, new_state, price)
            elif (_PROGRESSION_RANK[new_state] > _PROGRESSION_RANK[zone["state"]]
                    or exact.rational_gt(new_pen, old_pen)):
                touch = (exact.TransitionPrecedence.PROGRESSION, new_pen, new_state, price)
    if touch is not None:
        classes.append(touch[0])
    if not classes:
        return dict(zone, bars_elapsed=aged), None
    winner = exact.dominant_transition(classes)
    if winner is exact.TransitionPrecedence.INVALIDATED:
        gone = dict(zone, bars_elapsed=aged, state=STATE_INVALIDATED)
        return None, _zone_event(
            ZONE_INVALIDATED, gone, bar, ordinal, aged, state=STATE_INVALIDATED,
            reason_code=reason)
    if winner is exact.TransitionPrecedence.EXPIRED:
        gone = dict(zone, bars_elapsed=aged, state=STATE_EXPIRED)
        return None, _zone_event(
            ZONE_EXPIRED, gone, bar, ordinal, aged, state=STATE_EXPIRED)
    _class, new_pen, new_state, price = touch
    prior_state = zone["state"]
    updated = dict(zone, bars_elapsed=aged, pen=_stored_pen(new_pen), state=new_state)
    if new_state == STATE_FILLED:
        return None, _zone_event(
            ZONE_FILLED, updated, bar, ordinal, aged, state=STATE_FILLED,
            from_state=prior_state, touch_price_ticks=price)
    if _PROGRESSION_RANK[new_state] > _PROGRESSION_RANK[prior_state]:
        return updated, _zone_event(
            ZONE_PROGRESSED, updated, bar, ordinal, aged, state=new_state,
            from_state=prior_state, touch_price_ticks=price)
    return updated, None  # a deeper penetration inside one stage updates pen silently


# =================================================================================================
# The §C.3 entrypoint — the ONE transition implementation for live and replay.
# =================================================================================================


def evaluate(caps: "dict[str, VerifiedCapability]", env: ValidatedBar, state: "State | None", *,
             bar_ordinal: int,
             bucket_start_us: int,
             bucket_end_us: int,
             atr14_ticks: "int | None" = None,
             sequence_discontinuity: bool = False,
             revised_bar_identities: "tuple[str, ...] | list[str]" = (),
             opposing_break: "OpposingBreak | None" = None) -> TransitionResult:
    """Advance the F10 v3 registry by ONE finalized-bar event (spec §R-F10, order (1)-(5)).

    ``caps`` — the five required verified capabilities (see module docstring). ``env`` — the
    E01-validated bar (exact type). ``state`` — the prior v3 state object or ``None`` for the
    cold start. Injected event facts (never a clock read): ``bar_ordinal`` (the partition's
    source-sequence ordinal, strictly increasing), ``bucket_start_us``/``bucket_end_us`` (the
    bar's UTC bucket), ``atr14_ticks`` (causal ATR or ``None`` — warm-up abstains),
    ``sequence_discontinuity`` (the explicit GAP / data_revision-gap channel for a
    discontinuity an ordinal alone cannot carry), ``revised_bar_identities`` (defining-bar
    revision facts) and ``opposing_break`` (an accepted opposing F09 break fact).

    Returns a :class:`TransitionResult`; the same call drives live and replay.
    """
    entries = _require_caps(caps)
    min_gap_rule = _min_gap_rule_value(entries[PARAM_MIN_GAP_RULE])
    ttl = _positive_int64_value(entries[PARAM_TTL_BARS], PARAM_TTL_BARS)
    _exact_declared_string(
        entries[PARAM_TOUCH_PRICE_SOURCE], PARAM_TOUCH_PRICE_SOURCE,
        DECLARED_TOUCH_PRICE_SOURCE)
    _exact_declared_string(
        entries[PARAM_INVALIDATION_RULE], PARAM_INVALIDATION_RULE,
        DECLARED_INVALIDATION_RULE)
    max_open = _positive_int64_value(
        entries[PARAM_MAX_OPEN_PER_PARTITION], PARAM_MAX_OPEN_PER_PARTITION)
    bar = _require_env(env)
    prior = _require_state(state)
    ordinal = exact.guard_int64(
        common.require_int(bar_ordinal, "bar_ordinal"),
        formula_id=FORMULA_F10, field="bar_ordinal")
    start_us = exact.guard_int64(
        common.require_int(bucket_start_us, "bucket_start_us"),
        formula_id=FORMULA_F10, field="bucket_start_us")
    end_us = exact.guard_int64(
        common.require_int(bucket_end_us, "bucket_end_us"),
        formula_id=FORMULA_F10, field="bucket_end_us")
    if start_us >= end_us:
        raise common.StructureLawError("bar bucket must satisfy bucket_start_us < bucket_end_us")
    atr = None
    if atr14_ticks is not None:
        atr = exact.guard_int64(
            common.require_int(atr14_ticks, "atr14_ticks"),
            formula_id=FORMULA_F10, field="atr14_ticks")
    if not isinstance(sequence_discontinuity, bool):
        raise common.StructureLawError("sequence_discontinuity must be an exact bool")
    revised = _require_identities(revised_bar_identities)
    if opposing_break is not None and type(opposing_break) is not OpposingBreak:
        raise FvgEntrypointRejection(
            f"opposing_break must be an OpposingBreak fact, "
            f"got {type(opposing_break).__name__}")

    # -- transition ------------------------------------------------------------------------------
    last_ordinal = prior["last_ordinal"]
    if bar.bar_identity == prior["last_bar_identity"] and ordinal == last_ordinal:
        return TransitionResult(state=prior)  # adjacent duplicate: no-op
    if last_ordinal is not None and ordinal <= last_ordinal:
        raise common.StructureLawError(
            f"bar_ordinal must be strictly increasing: got {ordinal} after {last_ordinal}")
    gapped = sequence_discontinuity or (
        last_ordinal is not None and ordinal != last_ordinal + 1)

    events: tuple = ()
    survivors: list = []
    if gapped:
        # (1) CONTINUITY FIRST: every non-terminal zone -> INVALIDATED{SEQUENCE_GAP}; STOP.
        # No touch/fill/expiry/formation on or across the discontinuity; the current bar only
        # seeds the next 3-bar window.
        for zone in (dict(z) for z in prior["zones"]):
            gone = dict(zone, state=STATE_INVALIDATED)
            events += (_zone_event(
                ZONE_INVALIDATED, gone, bar, ordinal, zone["bars_elapsed"],
                state=STATE_INVALIDATED, reason_code=REASON_SEQUENCE_GAP),)
        recent: list = []
    else:
        recent = [dict(entry) for entry in prior["recent"]]
        for zone in (dict(z) for z in prior["zones"]):
            updated, event = _step_zone(
                zone, bar, ordinal, start_us, ttl, revised, opposing_break)
            if updated is not None:
                survivors.append(updated)
            if event is not None:
                events += (event,)
        # (5) FORMATION from (a, b, c) ending at this bar — the unchanged v2 math.
        if len(recent) == 2:
            a = recent[0]
            candidate = None
            if bar.low_ticks > a["high_ticks"]:
                candidate = (KIND_BULLISH, a["high_ticks"], bar.low_ticks)
            elif bar.high_ticks < a["low_ticks"]:
                candidate = (KIND_BEARISH, bar.high_ticks, a["low_ticks"])
            if candidate is not None:
                kind, z0, z1 = candidate
                try:
                    gap_ticks = exact.guard_int64(
                        z1 - z0, formula_id=FORMULA_F10, field="gap_ticks")
                except exact.QuarantineOverflow as quarantine:
                    events += (quarantine.record(),)  # §1.2: never wrap, never emit a zone
                else:
                    if atr is None:
                        events += (common.abstention(
                            "F10_NO_ATR", formula=FORMULA_F10,
                            detail="a raw gap candidate exists but causal ATR14 is null; the "
                                   "PAR-044 minimum-gap threshold cannot be evaluated",
                            refs={"bar_identity": bar.bar_identity}),)
                    else:
                        min_gap = common.evaluate_declared_rational(min_gap_rule, atr)
                        if gap_ticks >= min_gap:
                            origin = [a["bar_identity"], recent[1]["bar_identity"],
                                      bar.bar_identity]
                            if len(survivors) >= max_open:
                                # REFUSED_CAPACITY: an audit fact, never a zone; existing
                                # zones are never silently evicted.
                                events += ({
                                    "event_kind": REFUSED_CAPACITY,
                                    "formula": FORMULA_F10,
                                    "formula_version": FORMULA_VERSION,
                                    "reason_code": REFUSED_CAPACITY,
                                    "candidate_kind": kind,
                                    "candidate_z0_ticks": z0,
                                    "candidate_z1_ticks": z1,
                                    "candidate_gap_ticks": gap_ticks,
                                    "origin_bar_identities": origin,
                                    "bar_identity": bar.bar_identity,
                                    "bar_ordinal": ordinal,
                                    "open_zone_count": len(survivors),
                                    "max_open_per_partition": max_open,
                                },)
                            else:
                                zone = _new_zone(
                                    kind, z0, z1, gap_ticks, min_gap, atr,
                                    origin_bar_identities=origin,
                                    formation_ordinal=ordinal,
                                    availability_time_us=end_us)
                                survivors.append(zone)
                                events += (_zone_event(
                                    ZONE_FORMED, zone, bar, ordinal, 0, state=STATE_FRESH,
                                    z0_ticks=z0, z1_ticks=z1, gap_ticks=gap_ticks,
                                    min_gap_ticks=min_gap, atr14_ticks=atr,
                                    availability_time_us=end_us,
                                    origin_bar_identities=origin,
                                    formation_ordinal=ordinal),)

    current = {
        "bar_identity": bar.bar_identity,
        "ordinal": ordinal,
        "high_ticks": bar.high_ticks,
        "low_ticks": bar.low_ticks,
    }
    recent = (recent + [current])[-2:]
    return TransitionResult(
        state={
            "formula_version": FORMULA_VERSION,
            "last_ordinal": ordinal,
            "last_bar_identity": bar.bar_identity,
            "recent": recent,
            "zones": survivors,
        },
        events=events)
