"""``fvg.three_bar.closed.v3`` — F10 gap-reset-first FVG lifecycle
(TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12 R-F10).

Repairs the retired ``fvg.three_bar.closed.v2`` (:mod:`triad_origin.structures.fvg_registry`,
module banner ``RETIRED_DEFECTIVE{defect_ref=TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12 R-F10}``):
v2 evaluated existing zones for touch/fill BEFORE the sequence-gap reset, so a pre-gap zone could
be "filled" across missing bars; the exact INVALIDATED path, midpoint/penetration state, TTL
binding, and compaction were absent.

**CORRECTED LAW (spec §R-F10, normative).**

Formation (unchanged v2 math) — bars ``a = t-2``, ``b = t-1``, ``c = t``, all VALID_BAR (the E01
envelope), consecutive ordinals::

    bull: gap_ticks = L_c - H_a; qualifies iff gap_ticks >= min_gap_ticks AND gap_ticks > 0;
          zone = [z0, z1] = [H_a, L_c]
    bear: gap_ticks = L_a - H_c; zone = [z0, z1] = [H_c, L_a]

Penetration (bull; touch price ``p`` = bar low per the FVG_TOUCH_PRICE_SOURCE binding)::

    pen = clamp( (z1 - min(p, z1)) / (z1 - z0), 0, 1 )     stored as a reduced rational (§1.3)
    bear mirror: pen = clamp( (max(p, z0) - z0) / (z1 - z0), 0, 1 ) with p = bar high

States (MUTUALLY EXCLUSIVE, monotone, on the bar's extreme penetration): ``FRESH`` (no
intersection) ``-> TOUCHED (pen == 0, edge contact) -> PARTIAL (0 < pen < 1/2)
-> MIDPOINT_FILLED (1/2 <= pen < 1) -> FILLED (pen = 1, terminal) | EXPIRED (terminal)
| INVALIDATED (terminal)``. Progression is monotone; a single bar may advance multiple stages
(ONE event carrying the final stage). Per the RATIFIED T4 row —
"**edge contact at z1 is TOUCHED with pen = 0**" — contact is inclusive at the near edge (bull
``p <= z1``; bear ``p >= z0``) and the ratified test row wins over the state diagram's
``TOUCHED (pen>0)`` gloss (spec §0: the ratified row is normative).

ERRATUM ERR-01 (owner decision D-21 — TRIAD-ORIGIN-V7-ERRATA-2026-08-13). The spec §R-F10 state
block as written overlapped ``TOUCHED (pen>0)`` with ``PARTIAL (0<pen<1/2)``, and its inline T4
reasoning contradicted the ``pen>0`` gloss. This module already resolves the overlap in favour of
the RATIFIED T4 reading (the mutually-exclusive predicate set above), so ``_state_for`` returns
exactly one state for every ``pen`` in ``[0, 1]``. Formally adopting the erratum onto the spec
text is the owner's signature (D-21, alongside D-1's ``RATIFY_WITH_THIS_REPAIR`` set); the code and
its property test (``test_fvg_registry_v3.TestErr01MutuallyExclusiveStates``) lock the already-
ratified behaviour, they do not adopt a new law.

EVALUATION ORDER PER EVENT (normative; RATIFY_WITH_THIS_REPAIR):

1. **CONTINUITY FIRST** — if the event carries GAP / data_revision-gap / source-sequence
   discontinuity since the last processed ordinal for this partition: every non-terminal zone
   -> ``INVALIDATED{SEQUENCE_GAP}``. STOP. No touch/fill may be computed on or across the
   discontinuity (the current bar only seeds the next 3-bar formation window).
2. **INVALIDATION** — opposing-structure invalidation per the binding rule, defining-bar
   revision. Declared in-class tie rule (§1.4: "no formula may leave a same-event tie
   undefined"): DEFINING_BAR_REVISION is checked before OPPOSING_BREAK; the first match names
   the reason.
3. **EXPIRY** — ``bars_elapsed`` since formation availability ``>= FVG_TTL_BARS`` -> EXPIRED
   (inclusive at TTL).
4. **TERMINAL FILL then progressions**, monotone by the bar's extreme penetration.
5. **FORMATION** of new zones from ``(a, b, c)`` ending at this bar. Same-bar-retest ban: bar
   ``c`` can never be its own retest; the earliest touch source is ``c+1`` or later — enforced
   STRUCTURALLY twice: formation runs AFTER the zone-step loop (the new zone is never in the
   stepped set on its own event), and the zone's ``availability_time_us`` is its formation bar's
   ``bucket_end_us``, which :func:`triad_origin.exact.availability_allows` compares against every
   testing bar's ``bucket_start_us`` (bar ``c``'s own bucket start always precedes its bucket
   end).

Same-event multi-transition precedence rides :class:`triad_origin.exact.TransitionPrecedence`
(``INVALIDATED > EXPIRED > TERMINAL > PROGRESSION``) via :func:`exact.dominant_transition` — the
§1.4 global order instantiated (spec tests T8/T9).

**BINDINGS.** Four REQUIRED authenticated capabilities; one RATIFY_WITH_THIS_REPAIR law
hardwired (the PAR-036b/F03 precedent — a value the owner ratifies by signing this repair is
module law, never a code default for a still-proposed number):

* ``PAR-044`` (FVG_MIN_GAP — existing registry row FPB-0019, BLOCKED until ratified). Only the
  exact declared byte-string ``common.DECLARED_BOS_CLEAR_BUFFER``-equal value
  ``common.DECLARED_BOS_CLOSE_BUFFER`` (``"max(1,ceil(ATR14_ticks*1/20))"``) is executable.
  KNOWN TRANSPORT INTERLOCK (the F03/PAR-036 precedent, pinned by test): the declared
  byte-string contains ``*``, which the B01C-BIND-04 wildcard-sentinel law refuses inside an
  ACTIVE row's resolved fields — the ratification train must land a loader-acceptable
  declared-value transport; if that transport re-encodes the expression, the admission gate
  here moves in the SAME train.
* ``FVG_TTL_BARS`` — PROPOSED_MUST_RATIFY (proposed 96 formation-timeframe bars; NOT hardcoded
  here — the value arrives only inside the verified capability). Boundary law: EXPIRED when
  ``bars_elapsed >= TTL`` — inclusive at TTL (T7).
* ``FVG_INVALIDATION_RULE`` — PROPOSED_MUST_RATIFY. Only the exact declared byte-string
  :data:`DECLARED_INVALIDATION_RULE` is executable. Reading implemented for the proposed rule:
  an ACCEPTED opposing F09 break whose close is STRICTLY through the zone's far edge (bull far
  edge ``z0``: ``close < z0``; bear far edge ``z1``: ``close > z1``; edge contact is not
  "through").
* ``FVG_MAX_OPEN_PER_PARTITION`` — PROPOSED_MUST_RATIFY (proposed 64; NOT hardcoded here).
  Overflow behavior ``REFUSED_CAPACITY``: the candidate zone is recorded as an AUDIT FACT
  event, never a zone, and existing zones are never silently evicted (T11).
* ``FVG_TOUCH_PRICE_SOURCE = bar_low(bull)/bar_high(bear)`` — RATIFY_WITH_THIS_REPAIR: the
  owner's signature on the repair PR ratifies it; it is hardwired as law
  (:data:`FVG_TOUCH_PRICE_SOURCE`, implemented by :func:`_touch_price`). Its registry row is an
  orchestrator follow-on (this module never edits ``docs/control``).

The three PROPOSED/BLOCKED rows carry the NAMED refusal ``BLOCKED_ON_RATIFY(<parameter_id>)``
(:class:`BlockedOnRatify`, the F03 house token): the mechanism exists, activation is ONLY via an
authenticated :class:`triad_origin.bindings.VerifiedCapability` — and TODAY no F10 capability
can be minted from the repository registry (its F10 rows are BLOCKED;
``transition.require_bundle`` refuses ``BLOCKED_BINDING_INCOMPLETE:F10``, pinned by test).
PARAMETER-ID NOTE (recorded for the orchestrator): the three new binding rows do not exist in
``binding_registry.v2.json`` yet, so this module names them by their spec row names
(``FVG_TTL_BARS`` / ``FVG_INVALIDATION_RULE`` / ``FVG_MAX_OPEN_PER_PARTITION``); the
PAR-id/registry migration (incl. the PAR-051 ZONE_TTL 120-vs-96 proposal conflict) is a
registry/ratification act, never a code default.

**Entrypoint (spec §C.3).** ``evaluate(caps, env, state, *, bar_ordinal, bucket_start_us,
bucket_end_us, ...)`` where ``caps`` maps ``parameter_id -> VerifiedCapability`` (each entry
exact-type checked; ``formula_id`` must equal ``F10`` and ``parameter_id`` must equal its key —
a hand-built dict/int/str raises a typed boundary rejection BEFORE any state transition) and
``env`` is exactly an :class:`triad_origin.e01_interface.ValidatedBar` (produced ONLY by
``require_valid_bar`` — a raw mapping raises the §1.1 quarantine). Injected event facts (never a
clock read): the partition source-sequence ordinal, the bar's UTC bucket, the causal ATR
(``None`` = warm-up -> the named abstention ``F10_NO_ATR``, v2 law retained), the explicit
``sequence_discontinuity`` channel (a GAP an ordinal alone cannot carry — e.g. a
data-revision gap, or a §1.1-quarantined bar the caller dropped: a quarantined bar invalidates
every window/path that requires it EXACTLY as a GAP does, so the caller journals the quarantine
record and stamps the NEXT delivered bar's event discontinuous), ``revised_bar_identities``
(defining-bar revision facts) and ``opposing_break`` (an accepted opposing F09 break fact).
Replay and live consumption call this ONE transition implementation; internals are a pure
deterministic machine (no clock, no I/O, no float).

**Compaction.** A zone that reaches a terminal state (FILLED / EXPIRED / INVALIDATED) emits its
terminal event and leaves the working state in the same transition — the event tape is the
record; the state carries open (non-terminal) zones only, so the capacity law counts exactly the
open set and a terminal zone can structurally never re-emit.

Every persisted/emitted integer is re-checked signed int64 (§1.2 ``QUARANTINE_OVERFLOW``); the
formula's largest derived product is ``gap_ticks`` at formation (one beyond int64 journals the
quarantine RECORD and forms no zone — no atom is emitted) and the stored ``pen`` pair (bounded
by ``gap_ticks``, re-guarded at the storage boundary). Emitted events carry
``formula_version = fvg.three_bar.closed.v3`` — never-blend across formula versions applies
exactly as across cohorts (§1.5): v2 rows keep their tag forever and :func:`evaluate` refuses a
state stamped with any other version.
"""

from __future__ import annotations

from dataclasses import dataclass

from .. import bindings, exact
from ..canonical import INT64_MAX
from ..e01_interface import QuarantineInvalidBar, ValidatedBar
from ..transition import State, TransitionResult
from . import common

FORMULA_F10 = "F10"
FORMULA_VERSION = "fvg.three_bar.closed.v3"
RETIRED_PREDECESSOR_VERSION = "fvg.three_bar.closed.v2"

# --- the four required binding parameters (capability keys) -----------------------------------
PARAM_MIN_GAP_RULE = "PAR-044"                       # existing registry row (FVG_MIN_GAP)
PARAM_TTL_BARS = "FVG_TTL_BARS"                      # PROPOSED_MUST_RATIFY (proposed 96)
PARAM_INVALIDATION_RULE = "FVG_INVALIDATION_RULE"    # PROPOSED_MUST_RATIFY
PARAM_MAX_OPEN_PER_PARTITION = "FVG_MAX_OPEN_PER_PARTITION"  # PROPOSED_MUST_RATIFY (proposed 64)
REQUIRED_PARAMETERS = (
    PARAM_MIN_GAP_RULE,
    PARAM_TTL_BARS,
    PARAM_INVALIDATION_RULE,
    PARAM_MAX_OPEN_PER_PARTITION,
)

# FVG_TOUCH_PRICE_SOURCE — RATIFY_WITH_THIS_REPAIR: hardwired law (the PAR-036b precedent).
FVG_TOUCH_PRICE_SOURCE = "bar_low(bull)/bar_high(bear)"

# The exact declared byte-string the FVG_INVALIDATION_RULE capability must carry (any other
# value is a different law and refuses — the declared-string discipline of structures.common).
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
_OPEN_STATES = (STATE_FRESH, STATE_TOUCHED, STATE_PARTIAL, STATE_MIDPOINT_FILLED)

ZONE_FORMED = "ZONE_FORMED"
ZONE_PROGRESSED = "ZONE_PROGRESSED"
ZONE_FILLED = "ZONE_FILLED"
ZONE_EXPIRED = "ZONE_EXPIRED"
ZONE_INVALIDATED = "ZONE_INVALIDATED"
REFUSED_CAPACITY = "REFUSED_CAPACITY"

REASON_SEQUENCE_GAP = "SEQUENCE_GAP"
REASON_DEFINING_BAR_REVISION = "DEFINING_BAR_REVISION"
REASON_OPPOSING_BREAK = "OPPOSING_BREAK"

NO_ATR = "F10_NO_ATR"

_ZERO = (0, 1)
_HALF = (1, 2)
_ONE = (1, 1)

_STATE_KEYS = ("formula_version", "last_ordinal", "last_bar_identity", "recent", "zones")
_RECENT_KEYS = ("bar_identity", "ordinal", "high_ticks", "low_ticks")
_ZONE_KEYS = (
    "zone_id", "formula_version", "kind", "direction", "z0_ticks", "z1_ticks", "gap_ticks",
    "min_gap_ticks", "atr14_ticks", "pen", "state", "bars_elapsed", "availability_time_us",
    "origin_bar_identities", "formation_ordinal",
)


class BlockedOnRatify(RuntimeError):
    """The NAMED refusal ``BLOCKED_ON_RATIFY(<parameter_id>)`` (R-F10 BINDINGS; F03 house token).

    Raised when evaluation is attempted without an authenticated
    :class:`~triad_origin.bindings.VerifiedCapability` for a required parameter. The mechanism
    exists; activation is ONLY via authenticated binding — no proposed value (96-bar TTL, 64-zone
    cap, the invalidation rule) is ever hardcoded as active (spec §0 rule 1).
    """

    def __init__(self, parameter_id: str) -> None:
        super().__init__(f"BLOCKED_ON_RATIFY({parameter_id})")
        self.parameter_id = parameter_id


@dataclass(frozen=True)
class OpposingBreak:
    """An ACCEPTED F09 break fact presented to evaluation-order step (2).

    ``direction`` is the break's direction (``LONG``/``SHORT``); ``close_ticks`` the accepted
    break close. Only an accepted break is ever presented — the producer (F09,
    ``break.bar_close.v2``) owns acceptance; this module never re-derives it. Validated at
    construction: an unknown direction or a non-int64 close fails closed before the fact can
    reach any zone.
    """

    direction: str
    close_ticks: int

    def __post_init__(self) -> None:
        common.require_direction(self.direction)
        exact.guard_int64(
            self.close_ticks, formula_id=FORMULA_F10, field="opposing_break.close_ticks")


# ===============================================================================================
# Boundary law (spec §C.3): authenticated capabilities + E01-validated bar + lawful state —
# every rejection is typed and fires BEFORE any state transition.
# ===============================================================================================


def _require_caps(caps: object) -> dict:
    """Admit the capability mapping; return the resolved values, else a typed refusal.

    Exactly the four required parameter ids; each seat holds a
    :class:`~triad_origin.bindings.VerifiedCapability` (exact type — a subclass, a look-alike
    dataclass, a dict or an int is rejected) whose ``formula_id`` is ``F10`` and whose
    ``parameter_id`` equals its key. A missing required parameter is the named
    :class:`BlockedOnRatify` refusal; a value this module does not implement refuses
    (:class:`~triad_origin.structures.common.StructureLawError` — a different value is a
    different law, never a silently substituted semantics).
    """
    if not isinstance(caps, dict):
        raise bindings.CapabilityForgeryError(
            "F10 caps must be a mapping parameter_id -> VerifiedCapability; "
            f"got {type(caps).__name__}")
    unknown = [key for key in caps if key not in REQUIRED_PARAMETERS]
    if unknown:
        raise bindings.CapabilityForgeryError(
            f"F10 admits only the parameters {REQUIRED_PARAMETERS}; unknown key {unknown[0]!r}")
    entries: dict = {}
    for parameter_id in REQUIRED_PARAMETERS:
        if parameter_id not in caps:
            raise BlockedOnRatify(parameter_id)
        cap = caps[parameter_id]
        if type(cap) is not bindings.VerifiedCapability:
            raise bindings.CapabilityForgeryError(
                "F10 parameters require a VerifiedCapability produced by require_bundle; "
                f"got {type(cap).__name__} for {parameter_id!r}")
        if cap.formula_id != FORMULA_F10:
            raise bindings.CapabilityForgeryError(
                f"capability formula_id {cap.formula_id!r} is not {FORMULA_F10!r}")
        if cap.parameter_id != parameter_id:
            raise bindings.CapabilityForgeryError(
                f"capability parameter_id {cap.parameter_id!r} does not equal its mapping key "
                f"{parameter_id!r}")
        entries[parameter_id] = cap
    rule = entries[PARAM_MIN_GAP_RULE].value
    if rule != common.DECLARED_BOS_CLOSE_BUFFER:
        raise common.StructureLawError(
            f"F10 admits only the declared PAR-044 rule "
            f"{common.DECLARED_BOS_CLOSE_BUFFER!r}, got {rule!r}")
    inv_rule = entries[PARAM_INVALIDATION_RULE].value
    if inv_rule != DECLARED_INVALIDATION_RULE:
        raise common.StructureLawError(
            f"F10 admits only the declared FVG_INVALIDATION_RULE "
            f"{DECLARED_INVALIDATION_RULE!r}, got {inv_rule!r}")
    return {
        "min_gap_rule": rule,
        "ttl_bars": _ratified_count(entries[PARAM_TTL_BARS].value, PARAM_TTL_BARS),
        "invalidation_rule": inv_rule,
        "max_open": _ratified_count(
            entries[PARAM_MAX_OPEN_PER_PARTITION].value, PARAM_MAX_OPEN_PER_PARTITION),
    }


def _ratified_count(value: object, parameter_id: str) -> int:
    """A ratified count value: an exact positive int64, presented as an exact int or as the
    canonical ASCII decimal-integer string a registry ``declared_value`` carries (the binding
    schema types ``declared_value`` as a string)."""
    if isinstance(value, str):
        if (not value or any(ch not in "0123456789" for ch in value)
                or (len(value) > 1 and value.startswith("0"))):
            raise common.StructureLawError(
                f"{parameter_id} declared value must be a canonical ASCII decimal integer, "
                f"got {value!r}")
        number = int(value)
    elif isinstance(value, bool) or not isinstance(value, int):
        raise common.StructureLawError(
            f"{parameter_id} declared value must be an exact positive integer, "
            f"got {type(value).__name__}")
    else:
        number = value
    if number <= 0 or number > INT64_MAX:
        raise common.StructureLawError(
            f"{parameter_id} declared value must be a positive signed int64, got {number}")
    return number


def _require_env(env: object) -> ValidatedBar:
    """Exactly an e01 ValidatedBar — a raw mapping/subclass never crosses the boundary (§1.1)."""
    if type(env) is not ValidatedBar:
        raise QuarantineInvalidBar(
            bar_identity=None,
            reason="F10 env must be an e01_interface.ValidatedBar produced by "
                   f"require_valid_bar; got {type(env).__name__}")
    return env


def _require_pen(value: object, name: str) -> list:
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise common.StructureLawError(f"{name} must be a (num, den) rational pair")
    num = exact.guard_int64(value[0], formula_id=FORMULA_F10, field=f"{name}.num")
    den = exact.guard_int64(value[1], formula_id=FORMULA_F10, field=f"{name}.den")
    if den <= 0 or num < 0 or num > den:
        raise common.StructureLawError(
            f"{name} must satisfy 0 <= num <= den and den > 0 (a stored pen is in [0, 1])")
    return [num, den]


def _require_zone(zone: object, index: int) -> dict:
    name = f"state zones[{index}]"
    if not isinstance(zone, dict) or sorted(zone) != sorted(_ZONE_KEYS):
        raise common.StructureLawError(f"{name} must carry exactly the keys {_ZONE_KEYS}")
    if zone["formula_version"] != FORMULA_VERSION:
        raise common.StructureLawError(
            f"never-blend: {name} carries formula_version {zone['formula_version']!r}; "
            f"{FORMULA_VERSION} consumes only its own rows")
    if zone["kind"] not in (KIND_BULLISH, KIND_BEARISH):
        raise common.StructureLawError(f"{name} kind must be bullish/bearish")
    common.require_direction(zone["direction"])
    if zone["state"] not in _OPEN_STATES:
        raise common.StructureLawError(
            f"{name} state {zone['state']!r} is not an open state — a terminal zone compacts "
            f"out of the working state and can never persist")
    out = dict(zone)
    for field in ("z0_ticks", "z1_ticks", "gap_ticks", "min_gap_ticks", "atr14_ticks",
                  "bars_elapsed", "availability_time_us", "formation_ordinal"):
        out[field] = exact.guard_int64(zone[field], formula_id=FORMULA_F10, field=field)
    if out["z0_ticks"] >= out["z1_ticks"]:
        raise common.StructureLawError(f"{name} must satisfy z0_ticks < z1_ticks")
    if out["bars_elapsed"] < 0:
        raise common.StructureLawError(f"{name} bars_elapsed must be >= 0")
    out["pen"] = _require_pen(zone["pen"], f"{name}.pen")
    origins = zone["origin_bar_identities"]
    if (not isinstance(origins, (tuple, list)) or len(origins) != 3
            or any(not isinstance(o, str) or not o for o in origins)):
        raise common.StructureLawError(
            f"{name} origin_bar_identities must be the three formation bar identities")
    out["origin_bar_identities"] = list(origins)
    if not isinstance(zone["zone_id"], str) or not zone["zone_id"]:
        raise common.StructureLawError(f"{name} zone_id must be a non-empty str")
    return out


def _require_state(state: object) -> State:
    if state is None:
        return initial_state()
    if not isinstance(state, dict) or sorted(state) != sorted(_STATE_KEYS):
        raise common.StructureLawError(f"F10 state must carry exactly the keys {_STATE_KEYS}")
    if state["formula_version"] != FORMULA_VERSION:
        raise common.StructureLawError(
            f"never-blend: state carries formula_version {state['formula_version']!r}; "
            f"{FORMULA_VERSION} consumes only its own state rows (v2 rows keep their tag "
            f"forever)")
    last_ordinal = state["last_ordinal"]
    if last_ordinal is not None:
        last_ordinal = exact.guard_int64(
            last_ordinal, formula_id=FORMULA_F10, field="last_ordinal")
    last_identity = state["last_bar_identity"]
    if last_identity is not None and (not isinstance(last_identity, str) or not last_identity):
        raise common.StructureLawError(
            "F10 state last_bar_identity must be None or a non-empty str")
    recent = state["recent"]
    if not isinstance(recent, list) or len(recent) > 2:
        raise common.StructureLawError("F10 state recent must be a list of at most 2 entries")
    checked_recent = []
    for entry in recent:
        if not isinstance(entry, dict) or sorted(entry) != sorted(_RECENT_KEYS):
            raise common.StructureLawError(
                f"F10 state recent entries must carry exactly the keys {_RECENT_KEYS}")
        if not isinstance(entry["bar_identity"], str) or not entry["bar_identity"]:
            raise common.StructureLawError("F10 recent bar_identity must be a non-empty str")
        checked = dict(entry)
        for field in ("ordinal", "high_ticks", "low_ticks"):
            checked[field] = exact.guard_int64(
                entry[field], formula_id=FORMULA_F10, field=f"recent.{field}")
        checked_recent.append(checked)
    zones = state["zones"]
    if not isinstance(zones, list):
        raise common.StructureLawError("F10 state zones must be a list")
    return {
        "formula_version": FORMULA_VERSION,
        "last_ordinal": last_ordinal,
        "last_bar_identity": last_identity,
        "recent": checked_recent,
        "zones": [_require_zone(zone, i) for i, zone in enumerate(zones)],
    }


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


# ===============================================================================================
# Pure lifecycle pieces.
# ===============================================================================================


def initial_state() -> State:
    """The cold state: no processed ordinal, empty formation window, no open zones."""
    return {
        "formula_version": FORMULA_VERSION,
        "last_ordinal": None,
        "last_bar_identity": None,
        "recent": [],
        "zones": [],
    }


def _touch_price(kind: str, bar: ValidatedBar) -> int:
    """FVG_TOUCH_PRICE_SOURCE = bar_low(bull)/bar_high(bear) — RATIFY_WITH_THIS_REPAIR law."""
    return bar.low_ticks if kind == KIND_BULLISH else bar.high_ticks


def _contact(kind: str, z0: int, z1: int, price: int) -> bool:
    """T4 RATIFIED law: edge contact is TOUCHED with pen = 0 — inclusive at the near edge."""
    return price <= z1 if kind == KIND_BULLISH else price >= z0


def _bar_pen(kind: str, z0: int, z1: int, price: int) -> tuple:
    """The clamped penetration of one bar's touch price, as a reduced rational (§1.3)."""
    den = z1 - z0  # > 0 by formation law (gap_ticks > 0) and by the state-shape law
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
    """The declared FVG_INVALIDATION_RULE reading: an accepted OPPOSING break whose close is
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

    Returns ``(zone_or_None, event_or_None)`` — a ``None`` zone means the zone went terminal
    and compacts out of the working state. The winning transition class on a same-event tie is
    resolved through the §1.4 global order (:func:`exact.dominant_transition`), so T8
    (expiry beats touch) and T9 (invalidation beats fill) hold structurally.
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
    # (3) expiry — inclusive at TTL: bars_elapsed >= FVG_TTL_BARS (T7).
    if aged >= ttl:
        classes.append(exact.TransitionPrecedence.EXPIRED)
    # (4) fill / progression — only for a bar the §1.4 availability law admits (the same-bar-
    # retest ban's second wall: a bucket that opens before the zone's availability never tests).
    touch = None
    if exact.availability_allows(zone["availability_time_us"], bucket_start_us):
        price = _touch_price(zone["kind"], bar)
        if _contact(zone["kind"], zone["z0_ticks"], zone["z1_ticks"], price):
            old_pen = (zone["pen"][0], zone["pen"][1])
            bar_pen = _bar_pen(zone["kind"], zone["z0_ticks"], zone["z1_ticks"], price)
            # Monotone penetration: a lesser touch never regresses the recorded extreme.
            new_pen = bar_pen if exact.rational_gt(bar_pen, old_pen) else old_pen
            new_state = _state_for(new_pen, contacted=True)
            if _PROGRESSION_RANK[new_state] < _PROGRESSION_RANK[zone["state"]]:
                new_state = zone["state"]  # monotone — a derived lesser stage never regresses
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
    prior_state = zone["state"]
    if winner is exact.TransitionPrecedence.INVALIDATED:
        gone = dict(zone, bars_elapsed=aged, state=STATE_INVALIDATED)
        return None, _zone_event(
            ZONE_INVALIDATED, gone, bar, ordinal, aged, state=STATE_INVALIDATED,
            from_state=prior_state, reason_code=reason)
    if winner is exact.TransitionPrecedence.EXPIRED:
        gone = dict(zone, bars_elapsed=aged, state=STATE_EXPIRED)
        return None, _zone_event(
            ZONE_EXPIRED, gone, bar, ordinal, aged, state=STATE_EXPIRED,
            from_state=prior_state)
    _class, new_pen, new_state, price = touch
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


# ===============================================================================================
# The §C.3 entrypoint — the ONE transition implementation for live and replay.
# ===============================================================================================


def evaluate(caps: dict, env: ValidatedBar, state: "State | None", *,
             bar_ordinal: int,
             bucket_start_us: int,
             bucket_end_us: int,
             atr14_ticks: "int | None" = None,
             sequence_discontinuity: bool = False,
             revised_bar_identities: "tuple | list" = (),
             opposing_break: "OpposingBreak | None" = None) -> TransitionResult:
    """Advance the F10 v3 registry by ONE finalized-bar event (spec §R-F10, order (1)-(5)).

    Boundary order (all BEFORE any state transition): capability law -> E01 envelope law ->
    state-shape law -> injected-fact law. ``state`` is the prior v3 state object or ``None``
    for the cold start. Injected event facts (never a clock read): ``bar_ordinal`` (the
    partition's source-sequence ordinal, strictly increasing), ``bucket_start_us`` /
    ``bucket_end_us`` (the bar's UTC bucket), ``atr14_ticks`` (causal ATR or ``None`` — a raw
    gap candidate then abstains ``F10_NO_ATR``), ``sequence_discontinuity`` (the explicit GAP /
    data_revision-gap / quarantined-bar channel for a discontinuity an ordinal alone cannot
    carry), ``revised_bar_identities`` (defining-bar revision facts) and ``opposing_break``
    (an accepted opposing F09 break fact).

    Returns a :class:`~triad_origin.transition.TransitionResult`; the same call drives live
    and replay, and restart resumes from any canonical-JSON state snapshot.
    """
    values = _require_caps(caps)
    ttl = values["ttl_bars"]
    max_open = values["max_open"]
    min_gap_rule = values["min_gap_rule"]
    bar = _require_env(env)
    prior = _require_state(state)
    ordinal = exact.guard_int64(bar_ordinal, formula_id=FORMULA_F10, field="bar_ordinal")
    start_us = exact.guard_int64(
        bucket_start_us, formula_id=FORMULA_F10, field="bucket_start_us")
    end_us = exact.guard_int64(bucket_end_us, formula_id=FORMULA_F10, field="bucket_end_us")
    if start_us >= end_us:
        raise common.StructureLawError(
            "bar bucket must satisfy bucket_start_us < bucket_end_us")
    atr = None
    if atr14_ticks is not None:
        atr = exact.guard_int64(atr14_ticks, formula_id=FORMULA_F10, field="atr14_ticks")
    if not isinstance(sequence_discontinuity, bool):
        raise common.StructureLawError("sequence_discontinuity must be an exact bool")
    revised = _require_identities(revised_bar_identities)
    if opposing_break is not None and type(opposing_break) is not OpposingBreak:
        raise common.StructureLawError(
            f"opposing_break must be an OpposingBreak fact, "
            f"got {type(opposing_break).__name__}")

    # -- transition -----------------------------------------------------------------------------
    last_ordinal = prior["last_ordinal"]
    if bar.bar_identity == prior["last_bar_identity"] and ordinal == last_ordinal:
        return TransitionResult(state=prior)  # adjacent exact retransmission: idempotent no-op
    if last_ordinal is not None and ordinal <= last_ordinal:
        raise common.StructureLawError(
            f"bar_ordinal must be strictly increasing: got {ordinal} after {last_ordinal}")
    gapped = sequence_discontinuity or (
        last_ordinal is not None and ordinal != last_ordinal + 1)

    events: tuple = ()
    survivors: list = []
    if gapped:
        # (1) CONTINUITY FIRST: every non-terminal zone -> INVALIDATED{SEQUENCE_GAP}; STOP.
        # No touch/fill/expiry/formation is computed on or across the discontinuity; the
        # current bar only seeds the next 3-bar formation window.
        for zone in prior["zones"]:
            gone = dict(zone, state=STATE_INVALIDATED)
            events += (_zone_event(
                ZONE_INVALIDATED, gone, bar, ordinal, zone["bars_elapsed"],
                state=STATE_INVALIDATED, from_state=zone["state"],
                reason_code=REASON_SEQUENCE_GAP),)
        recent: list = []
    else:
        recent = [dict(entry) for entry in prior["recent"]]
        for zone in prior["zones"]:
            updated, event = _step_zone(
                zone, bar, ordinal, start_us, ttl, revised, opposing_break)
            if updated is not None:
                survivors.append(updated)
            if event is not None:
                events += (event,)
        # (5) FORMATION from (a, b, c) ending at this bar — the unchanged v2 math. The window
        # holds consecutive ordinals by construction: any non-consecutive event is `gapped`
        # above and reseeds it, so (a, b, c) are always three consecutive VALID_BAR bars.
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
                            NO_ATR, formula=FORMULA_F10,
                            detail="a raw gap candidate exists but causal ATR14 is null; the "
                                   "PAR-044 minimum-gap threshold cannot be evaluated",
                            refs={"bar_identity": bar.bar_identity,
                                  "formula_version": FORMULA_VERSION}),)
                    else:
                        min_gap = common.evaluate_declared_rational(min_gap_rule, atr)
                        if gap_ticks >= min_gap:  # inclusive (PAR-009); gap > 0 is structural
                            origin = [a["bar_identity"], recent[1]["bar_identity"],
                                      bar.bar_identity]
                            if len(survivors) >= max_open:
                                # REFUSED_CAPACITY: an audit fact, never a zone; existing
                                # zones are never silently evicted (T11).
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
