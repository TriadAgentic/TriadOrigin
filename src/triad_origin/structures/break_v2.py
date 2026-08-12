"""``break.bar_close.v2`` — R-F09 accepted break, first-terminal lifecycle (Formula Repair §2).

Repairs the ``break.bar_close.v1`` defects (see :class:`triad_origin.structures.structure_state.
BreakDetector`, retired ``RETIRED_DEFECTIVE``): one frozen level could record accepted first
breaks in BOTH directions; there was no availability-before-break proof, so a late-finalizing
older bar could false-trigger; BOS/CHOCH classification could run without valid F08 state.

CORRECTED LAW (spec R-F09, verbatim semantics)::

    Given frozen level L with availability_time T_L and inclusive buffer b (ticks, b >= 1):
      up_break(j)   iff C_j >= L + b
      down_break(j) iff C_j <= L - b
    ELIGIBILITY (availability law §1.4): bar j may test L only if bucket_start(j) >= T_L.
    FIRST-TERMINAL LAW (RATIFY_WITH_THIS_REPAIR):
      The level lifecycle is ARMED -> exactly one of {BROKEN_UP, BROKEN_DOWN} -> RETIRED,
      or ARMED -> EXPIRED (TTL) / INVALIDATED (defining-swing revision or GAP).
      The first accepted break in (bar availability_time, source_sequence) order
      terminates the level for BOTH directions. Every later break event on that level
      emits nothing (audit fact DUPLICATE_BREAK_IGNORED).
    BUFFER LAW: b >= 1 tick is REQUIRED. With b >= 1 a single close cannot satisfy both
      directions (C >= L+b and C <= L-b are disjoint). b = 0 is REFUSE_CONFIG.
    CLASSIFICATION GATE: BOS/CHOCH labels are emitted ONLY when F08 state is a valid,
      current, non-UNINITIALIZED structural state. Until F08 closes its refusal, v2
      emits GENERIC_BREAK occurrences with direction and no BOS/CHOCH label. No label
      is ever backfilled onto a GENERIC_BREAK after the fact.

F08 remains a refusal interface repository-wide (untouched by this repair), so this machine
carries NO structure-state input type at all: a caller-fed F08 state is structurally
unrepresentable here and every occurrence is ``GENERIC_BREAK`` — a BOS/CHOCH label cannot be
emitted by any code path in this module.

BINDINGS (consumed as C.3 verified capabilities, ``parameter_id -> VerifiedCapability``):

* ``PAR-043`` (``break_buffer_ticks`` / BOS_CLOSE_BUFFER — the existing registry row FPB-0018),
  REQUIRED. Two lawful value faces: the exact declared PAR-043 rule string
  ``max(1,ceil(ATR14_ticks*1/20))`` (evaluated per bar against the causal ATR14; the ``max(1,``
  floor makes ``b >= 1`` structural) or a direct exact-int tick value (the ``break_buffer_ticks``
  unit face). The ``b >= 1`` constraint is ``RATIFY_WITH_THIS_REPAIR`` and is enforced on BOTH
  faces: a direct ``b = 0`` (or negative) is the typed refusal ``REFUSE_CONFIG`` (T7).
* ``LEVEL_TTL_BARS`` — ``PROPOSED_MUST_RATIFY`` (the spec proposes a 500-bar value; it is never
  hardcoded as an executable constant in this module — a test asserts the absence). No registry
  row exists yet, so no real capability can be minted; the MECHANISM (age > TTL ⇒ EXPIRED) is wired
  now and the NAMED REFUSAL stands: while the capability is absent — or carries the
  ``NOT_RATIFIED`` sentinel — every bar observation yields the named abstention
  ``F09_UNAVAILABLE_LEVEL_TTL_NOT_RATIFIED`` with ZERO state mutation (SAFE_HOLD, the F06/F17
  posture; a level's expiry cannot be proven without the ratified TTL, so no break may be
  accepted either — fail closed, never a fabricated 500). Level registrations and the
  revision/INVALIDATED channel do not consume the TTL and stay live.

INPUT LAW (C.3 boundary; every violation is a TYPED rejection BEFORE any state transition):

* ``caps`` must be a plain ``dict`` mapping the parameter ids above to
  :class:`triad_origin.bindings.VerifiedCapability` handles — exact type, ``formula_id == "F09"``
  and ``entry.parameter_id`` equal to its key. A hand-built dict/int/str in place of a
  capability raises :class:`triad_origin.bindings.CapabilityForgeryError`.
* ``env`` must be exactly one of :class:`BarObservation` (which wraps an
  :class:`triad_origin.e01_interface.ValidatedBar` — the §1.1 VALID_BAR proof; only
  ``require_valid_bar`` constructs one, so an invalid bar can never reach this machine: the
  caller quarantines it, emits no atom, and the resulting ordinal hole surfaces here as a GAP),
  :class:`LevelRegistration`, or :class:`LevelRevision`. Anything else — including a raw dict or
  a subclass — raises :class:`EnvelopeRejected`.

ORDERING LAW: bars arrive in strictly increasing ``(availability_time_us, source_sequence)``
order (the first-terminal order key) with strictly increasing ``bar_ordinal``; a regression or
tie is a :class:`triad_origin.structures.common.StructureLawError`. An ordinal hole is a GAP:
every ARMED level is INVALIDATED (§1.4 precedence — INVALIDATED dominates any break the same
bar's close would imply). Same-event multi-transition ties resolve by
:func:`triad_origin.exact.dominant_transition` (INVALIDATED > EXPIRED > terminal > progression).

WIRE WIDTH (§1.2): every persisted integer crosses :func:`triad_origin.exact.guard_int64`;
overflow is ``QUARANTINE_OVERFLOW{formula_id, field, value_digest}`` — never wrap, never emit.

Replay and live consumption call the SAME transition implementation: :func:`evaluate` is the one
transition; :func:`run_break_v2` is a thin fold over it (exact-duplicate envelopes are skipped,
mirroring the estate driver's dedup law). Mirror law (T10): ``C -> -C``, ``up <-> down``,
``high <-> low`` — proven algebraically by test.
"""

from __future__ import annotations

from dataclasses import dataclass

from .. import exact
from ..bindings import CapabilityForgeryError, VerifiedCapability
from ..canonical import CanonicalError, canonical_json, loads_canonical
from ..e01_interface import ValidatedBar
from ..transition import MissingParameterError, TransitionResult
from . import common

FORMULA_F09 = "F09"
V2_FORMULA_VERSION = "break.bar_close.v2"

# --- capability parameter ids ---------------------------------------------------------------
PARAM_BREAK_BUFFER = "PAR-043"        # break_buffer_ticks (BOS_CLOSE_BUFFER, registry FPB-0018)
PARAM_LEVEL_TTL = "LEVEL_TTL_BARS"    # PROPOSED_MUST_RATIFY — refusal stands until ratified

REFUSE_CONFIG = "REFUSE_CONFIG"

# --- occurrence / audit-fact / lifecycle event kinds ------------------------------------------
BREAK_OCCURRENCE = "BREAK_OCCURRENCE"
DUPLICATE_BREAK_IGNORED = "DUPLICATE_BREAK_IGNORED"
INELIGIBLE_PRE_AVAILABILITY = "INELIGIBLE_PRE_AVAILABILITY"
LEVEL_EXPIRED = "LEVEL_EXPIRED"
LEVEL_INVALIDATED = "LEVEL_INVALIDATED"
BREAK_VOIDED_BY_REVISION = "BREAK_VOIDED_BY_REVISION"

UP_BREAK = "up_break"
DOWN_BREAK = "down_break"
CLASSIFICATION_GENERIC = "GENERIC_BREAK"

LIFECYCLE_ARMED = "ARMED"
LIFECYCLE_RETIRED = "RETIRED"
LIFECYCLE_EXPIRED = "EXPIRED"
LIFECYCLE_INVALIDATED = "INVALIDATED"
BROKEN_UP = "BROKEN_UP"
BROKEN_DOWN = "BROKEN_DOWN"

INVALIDATION_DEFINING_SWING_REVISED = "DEFINING_SWING_REVISED"
INVALIDATION_BAR_STREAM_GAP = "BAR_STREAM_GAP"

ABSTAIN_NO_ATR = "F09_NO_ATR"
ABSTAIN_LEVEL_TTL_NOT_RATIFIED = "F09_UNAVAILABLE_LEVEL_TTL_NOT_RATIFIED"

_STATE_KEYS = ("last_bar_ordinal", "last_order_key", "levels")
_LEVEL_FACE_KEYS = (
    "level_ticks", "direction", "availability_time_us", "formation_bar_ordinal",
    "defining_swing_id", "swing_revision",
)


class EnvelopeRejected(TypeError):
    """A non-ValidatedInput object was presented at the public surface (C.3 boundary law)."""


class RefuseConfig(ValueError):
    """The typed ``REFUSE_CONFIG`` refusal (BUFFER LAW b >= 1; malformed parameter faces)."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"{REFUSE_CONFIG}: {detail}")
        self.reason = REFUSE_CONFIG
        self.detail = detail


# ---------------------------------------------------------------------------------------------
# Typed input envelopes (exact-type-checked at the public surface)
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class BarObservation:
    """One finalized bar j, framed for F09 v2.

    ``bar`` is the §1.1 VALID_BAR proof (an :class:`~triad_origin.e01_interface.ValidatedBar`,
    constructible only by ``require_valid_bar``). The timing/order facts are E01-owned:
    ``bucket_start_us`` is ``bucket_start(j)`` (the §1.4 eligibility key), ``availability_time_us``
    is the bar's watermark-passage instant and ``source_sequence`` its per-source sequence — the
    pair is the first-terminal ORDER KEY; ``bar_ordinal`` is the consecutive
    per-(instrument, timeframe) ordinal (TTL age + GAP detection). ``atr14_ticks`` is the causal
    F02 ATR at j (``None`` = warm-up/gap — honest null, never zero).
    """

    bar: ValidatedBar
    bucket_start_us: int
    availability_time_us: int
    source_sequence: int
    bar_ordinal: int
    atr14_ticks: int | None
    source_event_id: str


@dataclass(frozen=True)
class LevelRegistration:
    """A confirmed frozen typed level entering the F09 book (ARMED).

    ``availability_time_us`` is ``T_L`` — the instant the level became knowable (§1.4);
    ``formation_bar_ordinal`` anchors the TTL age in formation-timeframe bars;
    ``defining_swing_id``/``swing_revision`` bind the level to the swing whose revision
    INVALIDATES it (spec step 6).
    """

    level_id: str
    level_ticks: int
    direction: str
    availability_time_us: int
    formation_bar_ordinal: int
    defining_swing_id: str
    swing_revision: int
    source_event_id: str


@dataclass(frozen=True)
class LevelRevision:
    """A revision of a defining swing (spec step 6 / T8).

    Every level registered under ``defining_swing_id`` with ``swing_revision < new_revision``
    is INVALIDATED; a recorded break under the now-invalid revision is voided by an APPENDED
    ``BREAK_VOIDED_BY_REVISION`` event — the original occurrence is never rewritten.
    """

    defining_swing_id: str
    new_revision: int
    source_event_id: str


def initial_state() -> dict:
    """The cold v2 state: no bars consumed, an empty level book."""
    return {"last_bar_ordinal": None, "last_order_key": None, "levels": {}}


# ---------------------------------------------------------------------------------------------
# Boundary validation (typed rejections BEFORE any state transition)
# ---------------------------------------------------------------------------------------------


def _validated_caps(caps: object) -> tuple:
    """Validate the capability mapping; return ``(buffer_face, ttl_face)``.

    ``buffer_face``  is ``("rule", declared_rule)`` or ``("direct", b)`` with ``b >= 1``.
    ``ttl_face``     is ``("ratified", ttl)`` with ``ttl >= 1``, or ``("unratified", None)``.
    """
    if type(caps) is not dict:
        raise EnvelopeRejected(
            "caps must be a dict mapping parameter_id -> VerifiedCapability, got "
            f"{type(caps).__name__}")
    unknown = sorted(set(caps) - {PARAM_BREAK_BUFFER, PARAM_LEVEL_TTL})
    if unknown:
        raise RefuseConfig(f"unknown capability key {unknown[0]!r} — F09 v2 consumes exactly "
                           f"{PARAM_BREAK_BUFFER!r} (required) and {PARAM_LEVEL_TTL!r} (optional)")
    if PARAM_BREAK_BUFFER not in caps:
        raise MissingParameterError(
            f"required capability {PARAM_BREAK_BUFFER!r} (break_buffer_ticks) is absent; "
            "F09 v2 fails closed (no code default)")
    for key in sorted(caps):
        cap = caps[key]
        if type(cap) is not VerifiedCapability:
            raise CapabilityForgeryError(
                f"caps[{key!r}] must be a VerifiedCapability minted by require_bundle, got "
                f"{type(cap).__name__} — a hand-built parameter cannot enter a production "
                "formula path")
        if cap.formula_id != FORMULA_F09:
            raise CapabilityForgeryError(
                f"caps[{key!r}] was minted for formula {cap.formula_id!r}; F09 v2 spends only "
                "F09 capabilities")
        if cap.parameter_id != key:
            raise CapabilityForgeryError(
                f"caps[{key!r}] carries parameter_id {cap.parameter_id!r}; the key and the "
                "capability identity must agree")
    return (
        _buffer_face(caps[PARAM_BREAK_BUFFER].value),
        _ttl_face(caps[PARAM_LEVEL_TTL].value) if PARAM_LEVEL_TTL in caps
        else ("unratified", None),
    )


def _buffer_face(value: object) -> tuple:
    """The PAR-043 value: the declared rule string, or a direct tick int with ``b >= 1``."""
    if isinstance(value, bool):
        raise RefuseConfig(f"break_buffer_ticks must be an exact int or the declared rule "
                           f"string, got bool {value!r}")
    if isinstance(value, int):
        b = exact.guard_int64(value, formula_id=FORMULA_F09, field="break_buffer_ticks")
        if b < 1:
            raise RefuseConfig(
                f"break_buffer_ticks b = {b} violates the BUFFER LAW b >= 1 "
                "(RATIFY_WITH_THIS_REPAIR); b = 0 is REFUSE_CONFIG")
        return ("direct", b)
    if value == common.DECLARED_BOS_CLOSE_BUFFER:
        return ("rule", value)
    raise RefuseConfig(
        f"F09 v2 admits only the declared PAR-043 rule "
        f"{common.DECLARED_BOS_CLOSE_BUFFER!r} or a direct exact-int tick value, got {value!r}")


def _ttl_face(value: object) -> tuple:
    """The LEVEL_TTL_BARS value: a ratified exact int >= 1, or the NOT_RATIFIED sentinel."""
    if value == common.NOT_RATIFIED:
        return ("unratified", None)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RefuseConfig(
            f"LEVEL_TTL_BARS must be an exact int >= 1 or the {common.NOT_RATIFIED!r} "
            f"sentinel, got {value!r}")
    ttl = exact.guard_int64(value, formula_id=FORMULA_F09, field="level_ttl_bars")
    if ttl < 1:
        raise RefuseConfig(f"LEVEL_TTL_BARS must be >= 1 formation-timeframe bars, got {ttl}")
    return ("ratified", ttl)


def _nonempty_str(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise EnvelopeRejected(f"{name} must be a non-empty string")
    return value


def _guarded_int(value: object, field: str, *, minimum: int | None = None) -> int:
    """An exact signed-int64 envelope field (§1.2), optionally floor-bounded."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise EnvelopeRejected(f"{field} must be an exact int, got {type(value).__name__}")
    guarded = exact.guard_int64(value, formula_id=FORMULA_F09, field=field)
    if minimum is not None and guarded < minimum:
        raise EnvelopeRejected(f"{field} must be >= {minimum}, got {guarded}")
    return guarded


def _validated_env(env: object) -> type:
    """Exact-type + field law over the envelope; returns the envelope's type."""
    kind = type(env)
    if kind is BarObservation:
        if type(env.bar) is not ValidatedBar:
            raise EnvelopeRejected(
                "BarObservation.bar must be an e01_interface.ValidatedBar (constructed only "
                f"by require_valid_bar), got {type(env.bar).__name__}")
        bucket_start = _guarded_int(env.bucket_start_us, "bucket_start_us", minimum=0)
        availability = _guarded_int(env.availability_time_us, "availability_time_us", minimum=0)
        if not availability > bucket_start:
            raise EnvelopeRejected(
                "bar availability_time_us must be strictly after bucket_start_us (a bar "
                "finalizes only after its bucket ends — E01/F01 watermark law)")
        _guarded_int(env.source_sequence, "source_sequence", minimum=0)
        _guarded_int(env.bar_ordinal, "bar_ordinal", minimum=0)
        if env.atr14_ticks is not None:
            _guarded_int(env.atr14_ticks, "atr14_ticks")
        _nonempty_str(env.source_event_id, "source_event_id")
        return kind
    if kind is LevelRegistration:
        _nonempty_str(env.level_id, "level_id")
        _guarded_int(env.level_ticks, "level_ticks")
        if env.direction not in common.DIRECTIONS:
            raise EnvelopeRejected(
                f"level direction must be one of {common.DIRECTIONS}, got {env.direction!r}")
        _guarded_int(env.availability_time_us, "availability_time_us", minimum=0)
        _guarded_int(env.formation_bar_ordinal, "formation_bar_ordinal", minimum=0)
        _nonempty_str(env.defining_swing_id, "defining_swing_id")
        _guarded_int(env.swing_revision, "swing_revision", minimum=0)
        _nonempty_str(env.source_event_id, "source_event_id")
        return kind
    if kind is LevelRevision:
        _nonempty_str(env.defining_swing_id, "defining_swing_id")
        _guarded_int(env.new_revision, "new_revision", minimum=0)
        _nonempty_str(env.source_event_id, "source_event_id")
        return kind
    raise EnvelopeRejected(
        "F09 v2 consumes exactly BarObservation | LevelRegistration | LevelRevision "
        f"(exact types), got {type(env).__name__}")


def _state_snapshot(state: object) -> dict:
    """A detached canonical copy of the prior state (the machine never mutates the caller's)."""
    if not isinstance(state, dict):
        raise EnvelopeRejected(f"state must be an object, got {type(state).__name__}")
    if sorted(state) != sorted(_STATE_KEYS):
        raise EnvelopeRejected(
            f"state must carry exactly the keys {sorted(_STATE_KEYS)}, got {sorted(state)}")
    try:
        snapshot = loads_canonical(canonical_json(state))
    except CanonicalError as exc:
        raise EnvelopeRejected(f"state is not canonical data: {exc}") from exc
    if not isinstance(snapshot.get("levels"), dict):
        raise EnvelopeRejected("state.levels must be an object")
    return snapshot


# ---------------------------------------------------------------------------------------------
# The public entrypoint — the ONE transition implementation (live == replay)
# ---------------------------------------------------------------------------------------------


def evaluate(caps: object, env: object, state: object) -> TransitionResult:
    """``evaluate(caps, env, state)`` — the C.3 production entrypoint for F09 v2.

    ``caps``  — ``{parameter_id: VerifiedCapability}`` (see the module docstring's INPUT LAW).
    ``env``   — exactly one of BarObservation | LevelRegistration | LevelRevision.
    ``state`` — the prior state object (:func:`initial_state` for a cold start).

    Every boundary violation raises its typed rejection BEFORE any state transition; the
    returned :class:`~triad_origin.transition.TransitionResult` carries a detached state and an
    ordered event tuple. Pure: no clock, no I/O, no randomness, no float.
    """
    buffer_face, ttl_face = _validated_caps(caps)
    kind = _validated_env(env)
    prior = _state_snapshot(state)
    if kind is LevelRegistration:
        return _register(prior, env)
    if kind is LevelRevision:
        return _revise(prior, env)
    return _observe(prior, env, buffer_face, ttl_face)


def _level_face(reg: LevelRegistration) -> dict:
    return {
        "level_ticks": reg.level_ticks,
        "direction": reg.direction,
        "availability_time_us": reg.availability_time_us,
        "formation_bar_ordinal": reg.formation_bar_ordinal,
        "defining_swing_id": reg.defining_swing_id,
        "swing_revision": reg.swing_revision,
    }


def _register(state: dict, reg: LevelRegistration) -> TransitionResult:
    """ARMED registration: idempotent on an identical face; a bare conflict refuses.

    A GENUINE geometry change travels the revision channel (:class:`LevelRevision`), never a
    silent re-registration — a conflicting face under the same ``level_id`` is refused loudly
    (the v1 law, retained).
    """
    face = _level_face(reg)
    existing = state["levels"].get(reg.level_id)
    if existing is not None:
        if {key: existing[key] for key in _LEVEL_FACE_KEYS} == face:
            return TransitionResult(state=state)  # idempotent re-send, no event
        raise common.StructureLawError(
            f"F09 level {reg.level_id!r} re-registered with conflicting geometry; a defining-"
            "swing change must arrive as a LevelRevision, never a silent re-registration")
    record = dict(face)
    record.update({
        "lifecycle": LIFECYCLE_ARMED,
        "terminal": None,
        "break": None,
        "break_voided": False,
        "invalidated_by_revision": None,
        "registration_event_id": reg.source_event_id,
    })
    state["levels"][reg.level_id] = record
    return TransitionResult(state=state)


def _revise(state: dict, rev: LevelRevision) -> TransitionResult:
    """Spec step 6 / T8: defining-swing revision -> INVALIDATED (+ append-only break void).

    Only a strictly NEWER revision (``new_revision > registered swing_revision``) invalidates;
    a stale or equal echo is a deterministic no-op. Already-INVALIDATED levels are left alone
    (nothing further to void). The recorded break occurrence is never rewritten — the void is
    an APPENDED event and a state marker.
    """
    events: tuple = ()
    for level_id in sorted(state["levels"]):
        record = state["levels"][level_id]
        if record["defining_swing_id"] != rev.defining_swing_id:
            continue
        if record["swing_revision"] >= rev.new_revision:
            continue
        if record["lifecycle"] == LIFECYCLE_INVALIDATED:
            continue
        prior_lifecycle = record["lifecycle"]
        record["lifecycle"] = LIFECYCLE_INVALIDATED
        record["invalidated_by_revision"] = rev.new_revision
        events += ({
            "event_kind": LEVEL_INVALIDATED,
            "formula": FORMULA_F09,
            "formula_version": V2_FORMULA_VERSION,
            "level_id": level_id,
            "reason": INVALIDATION_DEFINING_SWING_REVISED,
            "prior_lifecycle": prior_lifecycle,
            "defining_swing_id": rev.defining_swing_id,
            "registered_revision": record["swing_revision"],
            "revised_to": rev.new_revision,
            "source_event_id": rev.source_event_id,
        },)
        if record["break"] is not None:
            record["break_voided"] = True
            events += ({
                "event_kind": BREAK_VOIDED_BY_REVISION,
                "formula": FORMULA_F09,
                "formula_version": V2_FORMULA_VERSION,
                "level_id": level_id,
                "voided_direction": record["break"]["direction"],
                "first_breach_source": record["break"]["first_breach_source"],
                "defining_swing_id": rev.defining_swing_id,
                "registered_revision": record["swing_revision"],
                "revised_to": rev.new_revision,
                "source_event_id": rev.source_event_id,
            },)
    return TransitionResult(state=state, events=events)


def _bar_buffer(obs: BarObservation, buffer_face: tuple) -> int | None:
    """Resolve b for this bar. ``None`` means honest-null (rule face with ATR in warm-up)."""
    face, value = buffer_face
    if face == "direct":
        return value
    if obs.atr14_ticks is None:
        return None
    b = common.evaluate_declared_rational(value, obs.atr14_ticks)
    if b < 1:  # unreachable under the declared max(1, ...) rule — defense in depth (BUFFER LAW)
        raise RefuseConfig(f"evaluated break buffer b = {b} violates the BUFFER LAW b >= 1")
    return b


def _break_direction(close: int, level: int, b: int) -> str | None:
    """The close-based predicates. With b >= 1 the two arms are disjoint (BUFFER LAW)."""
    if close >= level + b:
        return UP_BREAK
    if close <= level - b:
        return DOWN_BREAK
    return None


def _observe(state: dict, obs: BarObservation, buffer_face: tuple, ttl_face: tuple
             ) -> TransitionResult:
    # LEVEL_TTL_BARS refusal posture (PROPOSED_MUST_RATIFY): SAFE_HOLD — the named abstention,
    # zero state mutation, no break, no expiry, no bar consumption. Never a fabricated TTL.
    if ttl_face[0] != "ratified":
        return TransitionResult(state=state, events=(common.abstention(
            ABSTAIN_LEVEL_TTL_NOT_RATIFIED, formula=FORMULA_F09,
            detail="LEVEL_TTL_BARS is PROPOSED_MUST_RATIFY and not ratified; the TTL check "
                   "cannot run, so no bar may be consumed (SAFE_HOLD — fail closed, never a "
                   "fabricated TTL)",
            refs={"source_event_id": obs.source_event_id}),))
    ttl = ttl_face[1]

    # ORDER LAW: strictly increasing (availability_time_us, source_sequence); strictly
    # increasing bar_ordinal; an ordinal hole is a GAP (INVALIDATED channel).
    order_key = [obs.availability_time_us, obs.source_sequence]
    prior_key = state["last_order_key"]
    if prior_key is not None and not (
        (order_key[0], order_key[1]) > (prior_key[0], prior_key[1])
    ):
        raise common.StructureLawError(
            f"F09 bar order regression: (availability_time_us, source_sequence) {order_key} "
            f"does not strictly follow {prior_key}")
    prior_ordinal = state["last_bar_ordinal"]
    if prior_ordinal is not None and obs.bar_ordinal <= prior_ordinal:
        raise common.StructureLawError(
            f"F09 bar_ordinal regression: {obs.bar_ordinal} does not strictly follow "
            f"{prior_ordinal}")
    gap = prior_ordinal is not None and obs.bar_ordinal > prior_ordinal + 1

    b = _bar_buffer(obs, buffer_face)
    close = obs.bar.close_ticks
    events: tuple = ()
    if b is None:
        events += (common.abstention(
            ABSTAIN_NO_ATR, formula=FORMULA_F09,
            detail="causal ATR14 is null (warm-up/gap); break buffer is unavailable",
            refs={"source_event_id": obs.source_event_id}),)

    for level_id in sorted(state["levels"]):
        record = state["levels"][level_id]
        lifecycle = record["lifecycle"]
        if lifecycle in (LIFECYCLE_EXPIRED, LIFECYCLE_INVALIDATED):
            continue
        level_ticks = record["level_ticks"]
        eligible = exact.availability_allows(
            record["availability_time_us"], obs.bucket_start_us)

        if lifecycle == LIFECYCLE_RETIRED:
            # FIRST-TERMINAL LAW: every later break event on this level emits nothing but the
            # audit fact DUPLICATE_BREAK_IGNORED (T4). Testing still requires eligibility (§1.4).
            if eligible and b is not None:
                ignored = _break_direction(close, level_ticks, b)
                if ignored is not None:
                    events += ({
                        "event_kind": DUPLICATE_BREAK_IGNORED,
                        "formula": FORMULA_F09,
                        "formula_version": V2_FORMULA_VERSION,
                        "level_id": level_id,
                        "ignored_direction": ignored,
                        "terminal": record["terminal"],
                        "close_ticks": close,
                        "buffer_ticks": b,
                        "source_event_id": obs.source_event_id,
                        "bar_identity": obs.bar.bar_identity,
                    },)
            continue

        # ARMED — collect this event's candidate transition classes; §1.4 precedence decides.
        candidates = []
        direction = None
        if gap:
            candidates.append(exact.TransitionPrecedence.INVALIDATED)
        if eligible:
            age = obs.bar_ordinal - record["formation_bar_ordinal"]
            if age > ttl:
                candidates.append(exact.TransitionPrecedence.EXPIRED)
            if b is not None:
                # Wick-only guard (step 3) is structural: the predicates read the CLOSE only —
                # H_j >= L + b with C_j < L + b emits nothing by construction.
                direction = _break_direction(close, level_ticks, b)
                if direction is not None:
                    candidates.append(exact.TransitionPrecedence.TERMINAL)
        elif obs.bar.low_ticks <= level_ticks <= obs.bar.high_ticks:
            # Step 1 forensic aid: the ineligible bar intersects the level price.
            events += ({
                "event_kind": INELIGIBLE_PRE_AVAILABILITY,
                "formula": FORMULA_F09,
                "formula_version": V2_FORMULA_VERSION,
                "level_id": level_id,
                "level_ticks": level_ticks,
                "level_availability_time_us": record["availability_time_us"],
                "bar_bucket_start_us": obs.bucket_start_us,
                "source_event_id": obs.source_event_id,
                "bar_identity": obs.bar.bar_identity,
            },)
        if not candidates:
            continue
        dominant = exact.dominant_transition(candidates)
        if dominant is exact.TransitionPrecedence.INVALIDATED:
            record["lifecycle"] = LIFECYCLE_INVALIDATED
            events += ({
                "event_kind": LEVEL_INVALIDATED,
                "formula": FORMULA_F09,
                "formula_version": V2_FORMULA_VERSION,
                "level_id": level_id,
                "reason": INVALIDATION_BAR_STREAM_GAP,
                "prior_lifecycle": LIFECYCLE_ARMED,
                "source_event_id": obs.source_event_id,
            },)
        elif dominant is exact.TransitionPrecedence.EXPIRED:
            record["lifecycle"] = LIFECYCLE_EXPIRED
            events += ({
                "event_kind": LEVEL_EXPIRED,
                "formula": FORMULA_F09,
                "formula_version": V2_FORMULA_VERSION,
                "level_id": level_id,
                "age_bars": obs.bar_ordinal - record["formation_bar_ordinal"],
                "level_ttl_bars": ttl,
                "source_event_id": obs.source_event_id,
            },)
        else:
            # Step 4: atomically CAS ARMED -> BROKEN_{dir} -> RETIRED; the first accepted break
            # terminates the level for BOTH directions. Step 5: F08 is a refusal interface, so
            # the classification is GENERIC_BREAK — no BOS/CHOCH label exists in this module.
            terminal = BROKEN_UP if direction == UP_BREAK else BROKEN_DOWN
            record["lifecycle"] = LIFECYCLE_RETIRED
            record["terminal"] = terminal
            record["break"] = {
                "direction": direction,
                "first_breach_source": obs.source_event_id,
                "acceptance_source": obs.source_event_id,
                "bar_availability_time_us": obs.availability_time_us,
                "source_sequence": obs.source_sequence,
            }
            events += ({
                "event_kind": BREAK_OCCURRENCE,
                "formula": FORMULA_F09,
                "formula_version": V2_FORMULA_VERSION,
                "level_id": level_id,
                "direction": direction,
                "terminal": terminal,
                "level_direction": record["direction"],
                "level_ticks": level_ticks,
                "buffer_ticks": b,
                "close_ticks": close,
                "classification": CLASSIFICATION_GENERIC,
                "first_breach_source": obs.source_event_id,
                "acceptance_source": obs.source_event_id,
                "bar_identity": obs.bar.bar_identity,
                "bar_availability_time_us": obs.availability_time_us,
                "source_sequence": obs.source_sequence,
                "bar_ordinal": obs.bar_ordinal,
            },)

    state["last_order_key"] = order_key
    state["last_bar_ordinal"] = obs.bar_ordinal
    return TransitionResult(state=state, events=events)


# ---------------------------------------------------------------------------------------------
# The fold used identically for live and replay (one transition implementation: evaluate)
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class BreakRunResult:
    """Detached fold result: final state, ordered events, exact-duplicate count."""

    final_state: dict
    events: tuple
    duplicate_count: int


def _env_fingerprint(env: object) -> bytes | None:
    """Canonical identity bytes for exact-duplicate dedup (None => let evaluate reject it)."""
    if type(env) is BarObservation:
        if type(env.bar) is not ValidatedBar:
            return None  # malformed — never dedup it away; evaluate owns the typed rejection
        body = {
            "kind": "BAR", "bar": {
                "bar_identity": env.bar.bar_identity,
                "metadata_revision": env.bar.metadata_revision,
                "open_ticks": env.bar.open_ticks, "high_ticks": env.bar.high_ticks,
                "low_ticks": env.bar.low_ticks, "close_ticks": env.bar.close_ticks,
                "base_volume": env.bar.base_volume, "quote_volume": env.bar.quote_volume,
                "trade_count": env.bar.trade_count,
            },
            "bucket_start_us": env.bucket_start_us,
            "availability_time_us": env.availability_time_us,
            "source_sequence": env.source_sequence,
            "bar_ordinal": env.bar_ordinal,
            "atr14_ticks": env.atr14_ticks,
            "source_event_id": env.source_event_id,
        }
    elif type(env) is LevelRegistration:
        body = {"kind": "LEVEL", "level_id": env.level_id, "level_ticks": env.level_ticks,
                "direction": env.direction, "availability_time_us": env.availability_time_us,
                "formation_bar_ordinal": env.formation_bar_ordinal,
                "defining_swing_id": env.defining_swing_id,
                "swing_revision": env.swing_revision,
                "source_event_id": env.source_event_id}
    elif type(env) is LevelRevision:
        body = {"kind": "REVISION", "defining_swing_id": env.defining_swing_id,
                "new_revision": env.new_revision, "source_event_id": env.source_event_id}
    else:
        return None
    try:
        return canonical_json(body)
    except (CanonicalError, TypeError):
        return None  # a non-canonical field — evaluate's boundary owns the typed rejection


def run_break_v2(caps: object, inputs: list, initial: dict | None = None) -> BreakRunResult:
    """Fold ``inputs`` (already in deterministic order) through :func:`evaluate`.

    Used identically for live and replay; ``initial`` resumes from a checkpoint state. Exact
    byte-duplicate envelopes are skipped and counted (the estate driver's dedup law); every
    envelope still crosses the full :func:`evaluate` boundary.
    """
    state = initial if initial is not None else initial_state()
    state = _state_snapshot(state)
    events: list = []
    seen: set = set()
    duplicate_count = 0
    for env in inputs:
        fingerprint = _env_fingerprint(env)
        if fingerprint is not None and fingerprint in seen:
            duplicate_count += 1
            continue
        if fingerprint is not None:
            seen.add(fingerprint)
        result = evaluate(caps, env, state)
        state = result.state
        events.extend(result.events)
    return BreakRunResult(
        final_state=loads_canonical(canonical_json(state)),
        events=tuple(events),
        duplicate_count=duplicate_count,
    )
