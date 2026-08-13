"""``reaction.first_touch.v2`` — F14 departure/first-retest with COMPUTED causality
(TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12 R-F14). No caller-supplied eligibility, ever.

Repairs the retired ``reaction.first_touch.v1`` (:mod:`triad_origin.structures.reaction`, banner
``RETIRED_DEFECTIVE{defect_ref=TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12 R-F14}``): v1 let a
contact at (not strictly after) zone knowledge confirm; accepted caller-precomputed
departure/count/time facts (the fabricatable-eligibility ``DEPARTURE_CANDIDATE`` envelope); had
no TTL/auto-expiry; and answered a conflicting re-registration with an abstention event instead
of a typed refusal.

**CORRECTED LAW (R-F14, breaking API change — deliberate).** The ONLY inputs are
:func:`register` (``structure_id``, ``zone=[z0, z1]``, ``side``, ``availability_time = T_know``)
plus a stream of validated observations through :func:`evaluate`. NOTHING ELSE — every
departure/count/time fact is computed INSIDE this machine:

* **STRICT ORDER** ``T_know < T_depart < T_contact`` on observation availability times. An
  observation with availability ``<= T_know`` is not a contact and not a departure input — the
  §1.4 gate (:func:`triad_origin.exact.availability_allows`) plus this formula's strict-equality
  exclusion keep it out of the eligible stream (the pre-knowledge trap, T1). The same event can
  therefore never both form/confirm the structure and be its departure or contact (T9).
* **DEPARTURE** — the earliest eligible observation at which ALL of (each inclusive at its
  boundary, the PAR-009 house law): directional distance from the NEAR edge ``>= dep_ticks``
  (bull-demand/LONG zone: ``low_ticks - z1 >= dep_ticks``; bear-supply/SHORT: ``z0 - high_ticks
  >= dep_ticks`` — the observation's whole closed range must clear the near edge, the
  conservative projection of "price" onto the declared PAR-168 range source), AND at least
  ``min_depart_events`` eligible observations (this one included), AND ``min_depart_time``
  elapsed **since T_know** (``availability - T_know >= min_depart_time_ms * 1000``). NOTE for
  the ratification record (spec-vs-RC3 clock delta): the v2 spec pseudocode measures the time
  conjunct from ``T_know``; RC3 FPB-0075's boundary prose said "after event-count rule also
  passes". Pseudocode wins (§0.1) — v2 measures from ``T_know``.
* **FIRST CONTACT** — the earliest observation with availability STRICTLY greater than
  ``T_depart`` whose closed range ``[low_ticks, high_ticks]`` intersects ``[z0, z1]`` INCLUSIVE
  at both edges (T4). A departing observation can never be the contact (strict inequality; a
  same-availability sibling observation is likewise not a lawful contact).
* **Pre-departure zone touches** are recorded audit facts only (``F14_PRE_DEPARTURE_TOUCH``) —
  they neither consume first-touch nor create candidates ("first retest" is defined strictly
  after departure, T8).
* **ATOMIC CONSUMPTION** — ``ELIGIBLE -> DEPARTED -> FIRST_TOUCH_CONSUMED`` via the CAS funnel
  :func:`_cas` (every state move compares the frozen prior state before setting; the pure fold
  makes the compare-and-set atomic and replay-exact). Second and later contacts are no-ops with
  the audit fact ``F14_DUPLICATE_CONTACT_IGNORED`` (T5).
* **TTL** — age since ``T_know``, measured in formation-timeframe BARS (= eligible observations;
  ``RETEST_TTL_CLOCK = FROM_T_KNOW``, RATIFY_WITH_THIS_REPAIR), reaching ``RETEST_TTL_BARS``
  expires the structure. T6 fixes the boundary INCLUSIVE ("TTL equality -> EXPIRED"), so the
  executable condition is ``age_bars >= RETEST_TTL_BARS`` — recorded for the ratification record
  against the law text's ``>`` prose. Expiry takes precedence over contact on the same event
  (§1.4 global order via :func:`triad_origin.exact.dominant_transition`; the losing contact is
  the audit fact ``F14_EXPIRY_OVER_CONTACT``).
* **INVALIDATED** — on structure revision (:func:`invalidate`) or GAP/quarantined bar
  (:func:`invalidate_on_gap` — §1.1: a quarantined bar invalidates the dependent reaction chain
  exactly as a GAP), precedence over everything (it arrives as its own transition and dominates
  the §1.4 order; terminal states are final and never reopened).
* **CONFLICT** — re-registration of an existing ``structure_id`` with different zone bytes is
  the TYPED error :class:`RejectConflict` (``REJECT_CONFLICT``); an identical re-registration is
  an idempotent no-op (T7). "Different zone bytes" is decided on the frozen registration's
  canonical bytes via :func:`registration_digest` (the exact-digest identity below).

**B06R EXACT-DIGEST ADOPTION (frozen HERE, adopted THERE).** The registration identity is::

    registration_digest = sha256_hex(canonical_json({
        "digest_kind": "origin.f14.registration.v2",
        "structure_id", "z0_ticks", "z1_ticks", "side", "availability_time_us"}))

and every ``REACTION_CONFIRMED`` event carries both that digest and::

    source_reaction_id = sha256_hex(canonical_json({
        "digest_kind": "origin.f14.reaction.v2",
        "registration_digest", "contact_availability_us",
        "observed_low_ticks", "observed_high_ticks"}))

These two canonicalizations are FROZEN by test in this repair. The B06R train (R-F19
clustering) ADOPTS them at the F19/candidate-consumer layer — F19 re-keys its
``source_reaction_id`` cluster predicate onto these exact digests; nothing in THIS module wires
F19 (staged posture: the digests are computed and emitted now, consumed at B06R).

**BINDINGS.** ``dep_ticks`` (PAR-050, the declared byte-string
``max(2,ceil(ATR14_ticks*1/10))``), ``min_depart_events`` (PAR-166, declared ``"1"``),
``min_depart_time`` (PAR-167, declared ``"60000"`` ms) and the contact price source (PAR-168,
declared ``"finalized_bar_closed_range_[low,high]"``) are existing bindings — every registry row
sits ``UNRESOLVED_BLOCKING`` (FPB-0025/0074/0075/0076), so evaluation without an authenticated
capability is the named refusal ``BLOCKED_ON_RATIFY(parameter_id)`` and no capability can be
minted off the repository registry today (``BLOCKED_BINDING_INCOMPLETE:F14`` at
``require_bundle``). The NEW ``RETEST_TTL_BARS`` binding is ``PROPOSED_MUST_RATIFY`` (proposed
288 formation-timeframe bars): the mechanism is implemented here, the proposed value exists ONLY
as the declared-string transport ``"288"`` reachable through an authenticated capability, and
its registry row is an orchestrator follow-on (this module never edits ``docs/control``).
``RETEST_TTL_CLOCK = FROM_T_KNOW`` is ``RATIFY_WITH_THIS_REPAIR`` — hardwired law; the owner's
signature on the repair PR ratifies it. ``FIRST_TOUCH_ORDINAL`` (PAR-062, RATIFIED_RC1 at
exactly ``1``) is STRUCTURAL in v2: the one-shot CAS ``DEPARTED -> FIRST_TOUCH_CONSUMED`` *is*
ordinal 1 — no other ordinal is expressible, so no runtime parameter exists to configure.
KNOWN TRANSPORT INTERLOCK (the F03 precedent, pinned by test): PAR-050's declared byte-string
contains ``*``, which the B01C-BIND-04 wildcard-sentinel law refuses inside an ACTIVE row's
resolved fields — the ratification train must additionally land a loader-acceptable
declared-value transport.

**Entrypoint (spec §C.3).** ``evaluate(caps, env, state, *, observation_availability_us,
atr14_ticks)`` where ``caps`` maps ``parameter_id -> triad_origin.bindings.VerifiedCapability``
(each entry exact-type checked; ``formula_id`` must equal ``F14`` and ``parameter_id`` must
equal its key — a hand-built dict/int/str raises a typed boundary rejection BEFORE any state
transition) and ``env`` is exactly an :class:`triad_origin.e01_interface.ValidatedBar` (produced
ONLY by ``require_valid_bar`` — the PAR-168 contact price source IS this envelope's closed
``[low, high]`` range; a raw mapping raises the §1.1 quarantine). ``observation_availability_us``
is the observation's E01 availability instant (boundary DATA, not an eligibility fact — the
machine computes all eligibility from it; carried as an injected keyword because
``ValidatedBar`` carries no time field today, the F03 ``atr14_ticks`` injection precedent) and
``atr14_ticks`` is the injected causal F02 dependency (``None`` = warm-up/gap → the named
abstention ``F14_NO_ATR``: no departure evaluation on that observation, never a shortened
fallback). One observation tests EVERY registered structure (deterministic sorted order).
Replay and live call this ONE transition implementation; internals are a pure deterministic
machine (no clock, no I/O, no float). Observations must arrive availability-ordered (the
ordered-input law): a regression is a typed refusal; an exact retransmission of the last
observation is an idempotent no-op.

Every persisted/emitted integer is re-checked signed int64 (§1.2 ``QUARANTINE_OVERFLOW``);
transient comparison arithmetic (distances, elapsed times, the ``min_depart_time_ms * 1000``
product) is lawfully unbounded. Emitted events carry ``semantic_version =
reaction.first_touch.v2`` — never-blend across formula versions applies exactly as across
cohorts (§1.5).
"""

from __future__ import annotations

from .. import bindings, canonical
from ..e01_interface import QuarantineInvalidBar, ValidatedBar
from ..exact import TransitionPrecedence, availability_allows, dominant_transition, guard_int64
from ..transition import TransitionResult
from . import common

FORMULA_ID = "F14"
SEMANTIC_VERSION = "reaction.first_touch.v2"
RETIRED_PREDECESSOR = "reaction.first_touch.v1"

# The authenticated-capability surface (spec §C.3 / R-F14 BINDINGS). Registry rows: PAR-050 =
# FPB-0025 · PAR-166 = FPB-0074 · PAR-167 = FPB-0075 · PAR-168 = FPB-0076 (all
# UNRESOLVED_BLOCKING today). RETEST_TTL_BARS has NO registry row yet — its row is the
# ratification train's deliverable; until then no capability can exist and the machine's named
# refusal is BLOCKED_ON_RATIFY(RETEST_TTL_BARS).
PARAMETER_MIN_DEPARTURE = "PAR-050"
PARAMETER_MIN_DEPART_EVENTS = "PAR-166"
PARAMETER_MIN_DEPART_TIME_MS = "PAR-167"
PARAMETER_CONTACT_PRICE_SOURCE = "PAR-168"
PARAMETER_RETEST_TTL_BARS = "RETEST_TTL_BARS"
REQUIRED_PARAMETERS = (
    PARAMETER_MIN_DEPARTURE,
    PARAMETER_MIN_DEPART_EVENTS,
    PARAMETER_MIN_DEPART_TIME_MS,
    PARAMETER_CONTACT_PRICE_SOURCE,
    PARAMETER_RETEST_TTL_BARS,
)

# PAR-062 FIRST_TOUCH_ORDINAL — RATIFIED_RC1 at exactly 1; STRUCTURAL in v2 (the one-shot CAS).
FIRST_TOUCH_ORDINAL = 1

# RETEST_TTL_CLOCK — RATIFY_WITH_THIS_REPAIR: the TTL ages from T_know, hardwired as law.
RETEST_TTL_CLOCK = "FROM_T_KNOW"

# Declared value byte-strings (the ONLY executable transports; the F03 _DECLARED_RULE_TERMS
# pattern — a capability whose value is not the exact declared string is refused).
DECLARED_MIN_DEPART_EVENTS = "1"                                    # PAR-166
DECLARED_MIN_DEPART_TIME_MS = "60000"                               # PAR-167 (milliseconds)
DECLARED_CONTACT_PRICE_SOURCE = "finalized_bar_closed_range_[low,high]"   # PAR-168
DECLARED_RETEST_TTL_BARS = "288"    # PROPOSED_MUST_RATIFY transport — active ONLY via capability

_DECLARED_EXECUTABLE = {
    PARAMETER_MIN_DEPARTURE: {common.DECLARED_MIN_DEPARTURE: common.DECLARED_MIN_DEPARTURE},
    PARAMETER_MIN_DEPART_EVENTS: {DECLARED_MIN_DEPART_EVENTS: 1},
    PARAMETER_MIN_DEPART_TIME_MS: {DECLARED_MIN_DEPART_TIME_MS: 60000},
    PARAMETER_CONTACT_PRICE_SOURCE: {
        DECLARED_CONTACT_PRICE_SOURCE: DECLARED_CONTACT_PRICE_SOURCE},
    PARAMETER_RETEST_TTL_BARS: {DECLARED_RETEST_TTL_BARS: 288},
}

# Event vocabulary.
REACTION_REGISTERED = "REACTION_REGISTERED"
REACTION_STATE_CHANGED = "REACTION_STATE_CHANGED"
REACTION_CONFIRMED = "REACTION_CONFIRMED"

# Audit facts (UPPER_SNAKE per common.abstention law; spec tokens repo-prefixed, F03 precedent).
PRE_KNOWLEDGE_OBSERVATION = "F14_PRE_KNOWLEDGE_OBSERVATION"     # T1 — the pre-knowledge trap
PRE_DEPARTURE_TOUCH = "F14_PRE_DEPARTURE_TOUCH"                 # T8 — audit only
DUPLICATE_CONTACT_IGNORED = "F14_DUPLICATE_CONTACT_IGNORED"     # T5 — spec: DUPLICATE_CONTACT_IGNORED
EXPIRY_OVER_CONTACT = "F14_EXPIRY_OVER_CONTACT"                 # T6 — same-event precedence audit
NO_ATR = "F14_NO_ATR"                                           # warm-up/gap abstention

# Lifecycle states (closed, append-only graph; terminal is final).
ELIGIBLE = "ELIGIBLE"
DEPARTED = "DEPARTED"
FIRST_TOUCH_CONSUMED = "FIRST_TOUCH_CONSUMED"
EXPIRED = "EXPIRED"
INVALIDATED = "INVALIDATED"
_TERMINAL = (FIRST_TOUCH_CONSUMED, EXPIRED, INVALIDATED)

_STATE_KEYS = ("last_observation", "structures")
_ROW_KEYS = (
    "z0_ticks", "z1_ticks", "side", "availability_time_us", "registration_digest",
    "reaction_state", "observation_count", "departure_availability_us",
)

# The frozen B06R exact-digest canonicalization kinds (see the module docstring).
REGISTRATION_DIGEST_KIND = "origin.f14.registration.v2"
REACTION_DIGEST_KIND = "origin.f14.reaction.v2"


class BlockedOnRatify(RuntimeError):
    """The named refusal ``BLOCKED_ON_RATIFY(parameter_id)`` (R-F14 BINDINGS).

    Raised when evaluation is attempted without an authenticated ``VerifiedCapability`` for a
    required parameter. The mechanism exists; activation is ONLY via authenticated binding — a
    proposed value is never hardcoded as active (spec §0 rule 1).
    """

    def __init__(self, parameter_id: str) -> None:
        super().__init__(f"BLOCKED_ON_RATIFY({parameter_id})")
        self.parameter_id = parameter_id


class RejectConflict(common.StructureLawError):
    """R-F14 ``REJECT_CONFLICT`` — a re-registration under a known ``structure_id`` whose frozen
    registration bytes differ (typed error, raised at the register seam BEFORE any mutation;
    the append-only observation replay path never raises it)."""

    def __init__(self, *, structure_id: str, frozen_digest: str, incoming_digest: str) -> None:
        super().__init__(
            f"REJECT_CONFLICT:{structure_id}: re-registration bytes differ from the frozen "
            f"registration (frozen {frozen_digest} != incoming {incoming_digest})")
        self.structure_id = structure_id
        self.frozen_digest = frozen_digest
        self.incoming_digest = incoming_digest


# ---------------------------------------------------------------------------------------------
# The frozen exact-digest identities (B06R adoption surface)
# ---------------------------------------------------------------------------------------------

def registration_digest(
    *, structure_id: str, z0_ticks: int, z1_ticks: int, side: str, availability_time_us: int,
) -> str:
    """The FROZEN canonical identity of a registration — the R-F14 "zone bytes".

    ``sha256_hex(canonical_json({digest_kind, structure_id, z0_ticks, z1_ticks, side,
    availability_time_us}))``. The conflict law compares registrations on exactly this digest;
    B06R (R-F19) adopts it as the exact-digest identity at the candidate-consumer layer.
    """
    return canonical.sha256_hex(canonical.canonical_json({
        "digest_kind": REGISTRATION_DIGEST_KIND,
        "structure_id": structure_id,
        "z0_ticks": z0_ticks,
        "z1_ticks": z1_ticks,
        "side": side,
        "availability_time_us": availability_time_us,
    }))


def source_reaction_id(
    *,
    registration_digest_hex: str,
    contact_availability_us: int,
    observed_low_ticks: int,
    observed_high_ticks: int,
) -> str:
    """The FROZEN consumed-contact identity carried on ``REACTION_CONFIRMED`` (B06R surface)."""
    return canonical.sha256_hex(canonical.canonical_json({
        "digest_kind": REACTION_DIGEST_KIND,
        "registration_digest": registration_digest_hex,
        "contact_availability_us": contact_availability_us,
        "observed_low_ticks": observed_low_ticks,
        "observed_high_ticks": observed_high_ticks,
    }))


# ---------------------------------------------------------------------------------------------
# Boundary law (spec §C.3): authenticated capabilities + E01-validated observation, nothing else
# ---------------------------------------------------------------------------------------------

def _require_caps(caps: object) -> dict:
    """Admit the capability mapping; return the resolved executable values, else typed refusal.

    THE ACCEPTANCE SCAN'S SUBSTANCE: no entry here can carry a departure/contact/eligibility
    fact — each capability resolves ONLY to one of the closed declared-value transports in
    ``_DECLARED_EXECUTABLE`` (ratified floors and sources, never per-observation facts).
    """
    if not isinstance(caps, dict):
        raise bindings.CapabilityForgeryError(
            "F14 caps must be a mapping parameter_id -> VerifiedCapability; "
            f"got {type(caps).__name__}")
    unknown = [key for key in caps if key not in REQUIRED_PARAMETERS]
    if unknown:
        raise bindings.CapabilityForgeryError(
            f"F14 admits only the parameters {REQUIRED_PARAMETERS}; unknown key {unknown[0]!r}")
    resolved: dict = {}
    for parameter_id in REQUIRED_PARAMETERS:
        if parameter_id not in caps:
            # The R-F14 named refusal: no authenticated binding, no machine.
            raise BlockedOnRatify(parameter_id)
        cap = caps[parameter_id]
        if type(cap) is not bindings.VerifiedCapability:
            raise bindings.CapabilityForgeryError(
                "F14 parameters require a VerifiedCapability produced by require_bundle; "
                f"got {type(cap).__name__} for {parameter_id!r}")
        if cap.formula_id != FORMULA_ID:
            raise bindings.CapabilityForgeryError(
                f"capability formula_id {cap.formula_id!r} is not {FORMULA_ID!r}")
        if cap.parameter_id != parameter_id:
            raise bindings.CapabilityForgeryError(
                f"capability parameter_id {cap.parameter_id!r} does not equal its mapping key "
                f"{parameter_id!r}")
        table = _DECLARED_EXECUTABLE[parameter_id]
        if cap.value not in table:
            raise common.StructureLawError(
                f"F14 admits only the declared {parameter_id} value "
                f"{tuple(table)[0]!r}, got {cap.value!r}")
        resolved[parameter_id] = table[cap.value]
    return resolved


def _require_env(env: object) -> ValidatedBar:
    """Exactly an e01 ValidatedBar — a raw mapping/subclass never crosses the boundary (§1.1).

    The PAR-168 contact price source (``finalized_bar_closed_range_[low,high]``) is satisfied BY
    CONSTRUCTION: the only lawful envelope is the finalized-bar type whose closed range this
    machine reads — no caller-supplied source string exists in v2.
    """
    if type(env) is not ValidatedBar:
        raise QuarantineInvalidBar(
            bar_identity=None,
            reason="F14 env must be an e01_interface.ValidatedBar produced by "
                   f"require_valid_bar; got {type(env).__name__}")
    return env


def _nonempty_str(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise common.StructureLawError(f"F14 {name} must be a non-empty string")
    return value


def _require_row(row: object, structure_id: str) -> dict:
    if not isinstance(row, dict) or sorted(row) != sorted(_ROW_KEYS):
        raise common.StructureLawError(
            f"F14 structure row {structure_id!r} must carry exactly the keys {_ROW_KEYS}")
    z0 = guard_int64(row["z0_ticks"], formula_id=FORMULA_ID, field="z0_ticks")
    z1 = guard_int64(row["z1_ticks"], formula_id=FORMULA_ID, field="z1_ticks")
    if z0 > z1:
        raise common.StructureLawError(f"F14 structure row {structure_id!r} zone z0 > z1")
    side = common.require_direction(row["side"])
    t_know = guard_int64(
        row["availability_time_us"], formula_id=FORMULA_ID, field="availability_time_us")
    digest = row["registration_digest"]
    if not canonical.is_sha256_hex(digest):
        raise common.StructureLawError(
            f"F14 structure row {structure_id!r} registration_digest must be sha256 hex64")
    reaction_state = row["reaction_state"]
    if reaction_state not in (ELIGIBLE, DEPARTED) + _TERMINAL:
        raise common.StructureLawError(
            f"F14 structure row {structure_id!r} unknown reaction_state {reaction_state!r}")
    count = guard_int64(
        row["observation_count"], formula_id=FORMULA_ID, field="observation_count")
    if count < 0:
        raise common.StructureLawError(
            f"F14 structure row {structure_id!r} observation_count must be >= 0")
    departed_at = row["departure_availability_us"]
    if departed_at is not None:
        departed_at = guard_int64(
            departed_at, formula_id=FORMULA_ID, field="departure_availability_us")
    if reaction_state == ELIGIBLE and departed_at is not None:
        raise common.StructureLawError(
            f"F14 structure row {structure_id!r} is ELIGIBLE but carries a departure time")
    if reaction_state in (DEPARTED, FIRST_TOUCH_CONSUMED) and departed_at is None:
        raise common.StructureLawError(
            f"F14 structure row {structure_id!r} is {reaction_state} without a departure time")
    return {
        "z0_ticks": z0, "z1_ticks": z1, "side": side, "availability_time_us": t_know,
        "registration_digest": digest, "reaction_state": reaction_state,
        "observation_count": count, "departure_availability_us": departed_at,
    }


def _require_state(state: object) -> dict:
    if not isinstance(state, dict) or sorted(state) != sorted(_STATE_KEYS):
        raise common.StructureLawError(f"F14 state must carry exactly the keys {_STATE_KEYS}")
    last = state["last_observation"]
    if last is not None:
        if not isinstance(last, dict) or sorted(last) != ["availability_us", "bar_identity"]:
            raise common.StructureLawError(
                "F14 state last_observation must be None or {bar_identity, availability_us}")
        _nonempty_str(last["bar_identity"], "last_observation.bar_identity")
        last = {
            "bar_identity": last["bar_identity"],
            "availability_us": guard_int64(
                last["availability_us"], formula_id=FORMULA_ID,
                field="last_observation.availability_us"),
        }
    structures = state["structures"]
    if not isinstance(structures, dict):
        raise common.StructureLawError("F14 state structures must be an object")
    rows = {}
    for structure_id in structures:
        rows[_nonempty_str(structure_id, "structure_id")] = _require_row(
            structures[structure_id], structure_id)
    return {"last_observation": last, "structures": rows}


def _cas(row: dict, structure_id: str, expected: str, new_state: str) -> dict:
    """The atomic compare-and-set funnel: EVERY lifecycle move passes through here.

    In the pure fold the compare-and-set is atomic by construction (no interleaving exists);
    the compare is still ENFORCED so a same-event double-transition or a replay divergence is a
    loud invariant violation, never a silent overwrite.
    """
    if row["reaction_state"] != expected:
        raise common.StructureLawError(
            f"F14 CAS violation on {structure_id!r}: expected {expected!r}, "
            f"found {row['reaction_state']!r}")
    return dict(row, reaction_state=new_state)


# ---------------------------------------------------------------------------------------------
# The pure machine
# ---------------------------------------------------------------------------------------------

def initial_state() -> dict:
    """The cold state: no observations seen, no structures registered."""
    return {"last_observation": None, "structures": {}}


def register(
    state: dict,
    *,
    structure_id: str,
    zone,
    side: str,
    availability_time_us: int,
) -> TransitionResult:
    """The ONLY structure-intake seam: ``register(structure_id, zone=[z0, z1], side, T_know)``.

    * malformed inputs are typed refusals (no partial registration);
    * a NEW ``structure_id`` freezes the registration, seeds ``ELIGIBLE`` and emits
      ``REACTION_REGISTERED`` carrying the frozen :func:`registration_digest`;
    * an IDENTICAL re-registration (same digest) is an idempotent no-op (T7);
    * a DIFFERING re-registration is the typed error :class:`RejectConflict` (T7) — raised
      BEFORE any state mutation, so a conflicting feed can never corrupt the frozen original.

    No departure/count/time/eligibility fact is expressible here — identity, geometry, side and
    the knowledge instant only.
    """
    st = _require_state(state)
    sid = _nonempty_str(structure_id, "structure_id")
    direction = common.require_direction(side)
    if not isinstance(zone, (list, tuple)) or len(zone) != 2:
        raise common.StructureLawError("F14 zone must be a [z0, z1] pair")
    z0 = guard_int64(
        common.require_int(zone[0], "zone[0]"), formula_id=FORMULA_ID, field="z0_ticks")
    z1 = guard_int64(
        common.require_int(zone[1], "zone[1]"), formula_id=FORMULA_ID, field="z1_ticks")
    if z0 > z1:
        raise common.StructureLawError("F14 zone must satisfy z0 <= z1")
    t_know = guard_int64(
        common.require_int(availability_time_us, "availability_time_us"),
        formula_id=FORMULA_ID, field="availability_time_us")
    digest = registration_digest(
        structure_id=sid, z0_ticks=z0, z1_ticks=z1, side=direction,
        availability_time_us=t_know)
    existing = st["structures"].get(sid)
    if existing is not None:
        if existing["registration_digest"] != digest:
            raise RejectConflict(
                structure_id=sid, frozen_digest=existing["registration_digest"],
                incoming_digest=digest)
        return TransitionResult(state=st)  # identical re-registration: idempotent no-op
    structures = dict(st["structures"])
    structures[sid] = {
        "z0_ticks": z0, "z1_ticks": z1, "side": direction, "availability_time_us": t_know,
        "registration_digest": digest, "reaction_state": ELIGIBLE,
        "observation_count": 0, "departure_availability_us": None,
    }
    event = {
        "event_kind": REACTION_REGISTERED, "formula": FORMULA_ID,
        "semantic_version": SEMANTIC_VERSION, "structure_id": sid,
        "registration_digest": digest, "z0_ticks": z0, "z1_ticks": z1, "side": direction,
        "availability_time_us": t_know, "reaction_state": ELIGIBLE,
    }
    return TransitionResult(
        state={"last_observation": st["last_observation"], "structures": structures},
        events=(event,))


def evaluate(
    caps: dict,
    env: ValidatedBar,
    state: dict,
    *,
    observation_availability_us: int,
    atr14_ticks: int | None,
) -> TransitionResult:
    """The ONE ``reaction.first_touch.v2`` observation transition — identical live and replay.

    Boundary order (all BEFORE any state transition): capability law -> E01 envelope law ->
    state-shape law -> ordering law. One validated observation tests EVERY registered structure
    in deterministic sorted order; all departure/count/time facts are computed here from the
    observation stream (the R-F14 corrected law).
    """
    resolved = _require_caps(caps)
    bar = _require_env(env)
    st = _require_state(state)
    avail = guard_int64(
        common.require_int(observation_availability_us, "observation_availability_us"),
        formula_id=FORMULA_ID, field="observation_availability_us")
    atr = None
    if atr14_ticks is not None:
        atr = guard_int64(
            common.require_int(atr14_ticks, "atr14_ticks"),
            formula_id=FORMULA_ID, field="atr14_ticks")

    # Ordered-input law: availability never regresses; an exact retransmission of the LAST
    # observation is an idempotent no-op; one bar identity has ONE availability.
    last = st["last_observation"]
    if last is not None:
        if bar.bar_identity == last["bar_identity"]:
            if avail == last["availability_us"]:
                return TransitionResult(state=st)  # exact retransmission: idempotent no-op
            raise common.StructureLawError(
                f"F14 observation {bar.bar_identity!r} retransmitted with a different "
                "availability time")
        if avail < last["availability_us"]:
            raise common.StructureLawError(
                "F14 observations must arrive availability-ordered; "
                f"{bar.bar_identity!r} at {avail} regresses behind {last['availability_us']}")

    structures = dict(st["structures"])
    events: list = []
    for sid in sorted(structures):
        row, row_events = _observe_structure(sid, structures[sid], bar, avail, atr, resolved)
        structures[sid] = row
        events.extend(row_events)
    new_state = {
        "last_observation": {"bar_identity": bar.bar_identity, "availability_us": avail},
        "structures": structures,
    }
    return TransitionResult(state=new_state, events=tuple(events))


def _audit(reason: str, detail: str, refs: dict) -> dict:
    return common.abstention(reason, formula=FORMULA_ID, detail=detail, refs=refs)


def _state_changed(sid: str, from_state: str, to_state: str, trigger: str, avail: int | None,
                   ) -> dict:
    event = {
        "event_kind": REACTION_STATE_CHANGED, "formula": FORMULA_ID,
        "semantic_version": SEMANTIC_VERSION, "structure_id": sid,
        "from_state": from_state, "to_state": to_state, "trigger": trigger,
    }
    if avail is not None:
        event["observation_availability_us"] = guard_int64(
            avail, formula_id=FORMULA_ID, field="observation_availability_us")
    return event


def _observe_structure(
    sid: str, row: dict, bar: ValidatedBar, avail: int, atr: int | None, resolved: dict,
) -> tuple:
    """Apply ONE eligible-stream observation to ONE structure; returns (row', events)."""
    t_know = row["availability_time_us"]
    z0, z1 = row["z0_ticks"], row["z1_ticks"]
    intersects = bar.low_ticks <= z1 and z0 <= bar.high_ticks  # closed, inclusive both edges
    refs = {"structure_id": sid, "bar_identity": bar.bar_identity,
            "observation_availability_us": avail}

    if row["reaction_state"] in _TERMINAL:
        if row["reaction_state"] == FIRST_TOUCH_CONSUMED and intersects:
            return row, (_audit(
                DUPLICATE_CONTACT_IGNORED,
                "a later contact on a consumed structure is a no-op; first-touch was "
                "consumed exactly once (PAR-062 ordinal 1, structural)",
                refs),)
        return row, ()

    # STRICT ORDER / §1.4: availability <= T_know never reaches the eligible stream (T1).
    if (not availability_allows(t_know, avail)) or avail == t_know:
        return row, (_audit(
            PRE_KNOWLEDGE_OBSERVATION,
            "observation availability <= T_know: not a contact, not a departure input "
            "(strict order T_know < T_depart < T_contact)",
            refs),)

    # This observation ages the structure: one eligible observation = one formation bar.
    count = guard_int64(
        row["observation_count"] + 1, formula_id=FORMULA_ID, field="observation_count")
    row = dict(row, observation_count=count)

    events: list = []
    candidates: list = []

    # TTL (RETEST_TTL_CLOCK = FROM_T_KNOW): age in bars since T_know; T6 fixes the boundary
    # inclusive — age reaching RETEST_TTL_BARS expires.
    ttl_expired = count >= resolved[PARAMETER_RETEST_TTL_BARS]
    if ttl_expired:
        candidates.append(TransitionPrecedence.EXPIRED)

    # First contact: DEPARTED, availability STRICTLY after T_depart, inclusive-edge intersection.
    contact_ok = (
        row["reaction_state"] == DEPARTED
        and intersects
        and avail > row["departure_availability_us"]
    )
    if contact_ok:
        candidates.append(TransitionPrecedence.TERMINAL)

    # Departure: computed INSIDE the machine from the eligible stream (never caller-supplied).
    departure_ok = False
    no_atr = False
    if row["reaction_state"] == ELIGIBLE:
        if atr is None:
            no_atr = True
        else:
            dep_ticks = common.evaluate_declared_rational(
                resolved[PARAMETER_MIN_DEPARTURE], atr)
            if row["side"] == common.LONG:
                distance = bar.low_ticks - z1     # bull-demand: whole range above the near edge
            else:
                distance = z0 - bar.high_ticks    # bear-supply mirror (near/far edges swap)
            elapsed_us = avail - t_know           # transient arithmetic — lawfully unbounded
            departure_ok = (
                distance >= dep_ticks
                and count >= resolved[PARAMETER_MIN_DEPART_EVENTS]
                and elapsed_us >= resolved[PARAMETER_MIN_DEPART_TIME_MS] * 1000
            )
            if departure_ok:
                candidates.append(TransitionPrecedence.PROGRESSION)

    if candidates:
        winner = dominant_transition(candidates)
        if winner is TransitionPrecedence.EXPIRED:
            from_state = row["reaction_state"]
            row = _cas(row, sid, from_state, EXPIRED)
            events.append(_state_changed(sid, from_state, EXPIRED, bar.bar_identity, avail))
            if contact_ok:
                events.append(_audit(
                    EXPIRY_OVER_CONTACT,
                    "expiry and contact met on the same event; expiry takes precedence "
                    "(§1.4 global order) — the contact is not consumed",
                    refs))
            return row, tuple(events)
        if winner is TransitionPrecedence.TERMINAL:
            departed_at = row["departure_availability_us"]
            # The acceptance property, asserted structurally on EVERY consumption.
            if not (avail > departed_at > t_know):
                raise common.StructureLawError(
                    f"F14 invariant violated on {sid!r}: consumed contact availability must "
                    "be strictly greater than T_depart strictly greater than T_know")
            row = _cas(row, sid, DEPARTED, FIRST_TOUCH_CONSUMED)
            reaction_id = source_reaction_id(
                registration_digest_hex=row["registration_digest"],
                contact_availability_us=avail,
                observed_low_ticks=bar.low_ticks,
                observed_high_ticks=bar.high_ticks)
            events.append({
                "event_kind": REACTION_CONFIRMED, "formula": FORMULA_ID,
                "semantic_version": SEMANTIC_VERSION, "structure_id": sid,
                "from_state": DEPARTED, "to_state": FIRST_TOUCH_CONSUMED,
                "side": row["side"],
                "contact_bar_identity": bar.bar_identity,
                "contact_availability_us": guard_int64(
                    avail, formula_id=FORMULA_ID, field="contact_availability_us"),
                "departure_availability_us": guard_int64(
                    departed_at, formula_id=FORMULA_ID, field="departure_availability_us"),
                "knowledge_time_us": guard_int64(
                    t_know, formula_id=FORMULA_ID, field="knowledge_time_us"),
                "observed_low_ticks": guard_int64(
                    bar.low_ticks, formula_id=FORMULA_ID, field="observed_low_ticks"),
                "observed_high_ticks": guard_int64(
                    bar.high_ticks, formula_id=FORMULA_ID, field="observed_high_ticks"),
                "first_touch_ordinal": FIRST_TOUCH_ORDINAL,
                "registration_digest": row["registration_digest"],
                "source_reaction_id": reaction_id,
            })
            return row, tuple(events)
        # PROGRESSION — departure: T_depart := this observation's availability.
        row = _cas(row, sid, ELIGIBLE, DEPARTED)
        row = dict(row, departure_availability_us=avail)
        events.append(_state_changed(sid, ELIGIBLE, DEPARTED, bar.bar_identity, avail))
        return row, tuple(events)

    # No transition. Pre-departure zone touches are audit facts only (T8); a missing causal ATR
    # is the named warm-up abstention (departure unevaluable on this observation).
    if row["reaction_state"] == ELIGIBLE and intersects:
        events.append(_audit(
            PRE_DEPARTURE_TOUCH,
            "zone touch before departure: recorded audit fact; neither consumes first-touch "
            "nor creates a candidate (first retest is defined strictly after departure)",
            refs))
    if no_atr:
        events.append(_audit(
            NO_ATR,
            "no causal ATR at this observation; departure not evaluated, no shortened fallback",
            refs))
    return row, tuple(events)


def invalidate(state: dict, *, structure_id: str, trigger_id: str, reason: str,
               ) -> TransitionResult:
    """Structure revision → ``INVALIDATED`` (precedence over everything; terminal is final).

    A revision naming an unregistered ``structure_id`` is a typed refusal (wiring defect, never
    silent); a revision on an already-terminal structure is a no-op (the closed append-only
    graph never reopens a terminal state — the revision arrived after the fact).
    """
    st = _require_state(state)
    sid = _nonempty_str(structure_id, "structure_id")
    trigger = _nonempty_str(trigger_id, "trigger_id")
    _nonempty_str(reason, "reason")
    row = st["structures"].get(sid)
    if row is None:
        raise common.StructureLawError(
            f"F14 invalidation names an unregistered structure_id {sid!r}")
    if row["reaction_state"] in _TERMINAL:
        return TransitionResult(state=st)
    from_state = row["reaction_state"]
    structures = dict(st["structures"])
    structures[sid] = _cas(row, sid, from_state, INVALIDATED)
    event = _state_changed(sid, from_state, INVALIDATED, trigger, None)
    event["reason"] = reason
    return TransitionResult(
        state={"last_observation": st["last_observation"], "structures": structures},
        events=(event,))


def invalidate_on_gap(state: dict, *, trigger_id: str, reason: str) -> TransitionResult:
    """GAP / quarantined-bar law (§1.1): EVERY non-terminal structure → ``INVALIDATED``.

    The caller whose boundary quarantined a bar (``require_valid_bar`` raised) invokes this —
    an invalid bar invalidates the dependent reaction chains exactly as a GAP does. Terminal
    structures are untouched (final); the sweep is deterministic (sorted structure order).
    """
    st = _require_state(state)
    trigger = _nonempty_str(trigger_id, "trigger_id")
    _nonempty_str(reason, "reason")
    structures = dict(st["structures"])
    events: list = []
    for sid in sorted(structures):
        row = structures[sid]
        if row["reaction_state"] in _TERMINAL:
            continue
        from_state = row["reaction_state"]
        structures[sid] = _cas(row, sid, from_state, INVALIDATED)
        event = _state_changed(sid, from_state, INVALIDATED, trigger, None)
        event["reason"] = reason
        events.append(event)
    return TransitionResult(
        state={"last_observation": st["last_observation"], "structures": structures},
        events=tuple(events))
