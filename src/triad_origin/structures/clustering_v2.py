"""``opportunity_cluster.v2`` — R-F19 insertion-invariant clustering + revision law.

TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12 §R-F19 (milestone B06R). Supersedes
``opportunity_cluster.v1`` (:mod:`triad_origin.structures.clustering`, retired with the §1.5
withdrawal banner ``RETIRED_DEFECTIVE{defect_ref=...R-F19}``; its bytes are preserved and its rows
keep their version tag forever — never-blend across formula versions). The three confirmed v1
defects this module repairs:

1. **The cluster root depended on input arrival order**, not ``(availability, candidate_id)``
   order — v1 processed one occurrence per ``transition()`` call in the caller's arrival order and
   "whichever occurrence the upstream feed delivers first wins the root". A permutation delivering
   the ``(availability, id)``-larger candidate first rooted it.
2. **Revisions could change cluster-defining fields without reclustering** — v1's ``_redeliver``
   updated the row fields in place and left ``cluster_id`` untouched with NO edge re-evaluation.
3. **TTL / compaction absent** — v1 had no way for a component to expire.

CORRECTED LAW (spec R-F19, the block is normative)::

    Cluster predicate (unchanged): same instrument AND same side AND
      ( source structure/reaction IDs overlap
        OR ( entry zones intersect (integer ticks, inclusive)
             AND |availability_A - availability_B| <= cluster_window (inclusive) ) ).
    ORDERING LAW (RATIFY_WITH_THIS_REPAIR): evaluation consumes candidates strictly in
      lexicographic (availability_time, candidate_id) order. If the transport delivers out of
      order, the machine SORTS the evaluation batch before applying the frozen prospective rule.
      Arrival order can never influence any output.
    ROOT: the (availability_time, candidate_id)-minimum member of the connected component at
      formation is the root; component_id = hash(root). Because evaluation order is the sorted
      order, the first member IS the root, and NO REROOT ever occurs.
    MERGE: a bridging candidate connecting components A and B merges them; the surviving
      component_id is the id whose root is (availability,id)-minimum across the union; the other
      id becomes a permanent deterministic ALIAS record (append-only).
    LATE MEMBER: appends a member-revision to the existing component (prospective; no retro edits).
    REVISION LAW (RATIFY_WITH_THIS_REPAIR): a revision that changes any cluster-defining field
      (zone interval, source IDs, availability) emits a cluster revision event and re-evaluates
      that member's edges: fail -> member RETIRED (component survives if >= 1 member; a retired
      candidate may prospectively join/form another cluster from its revision availability
      forward); hold -> membership unchanged, revision recorded. Historical outputs never rewritten.
    TTL/COMPACTION: component EXPIRED when all members are terminal AND cluster_window has elapsed
      since the last member availability. CLUSTER_MAX_MEMBERS bound with REFUSED_CAPACITY audit
      behavior (never silent eviction).
    Long and short never cluster (unchanged). E07 selects at most one money hypothesis per risk
    cell from a component (unchanged).

**How the ORDERING LAW is realized (the defect's structural cure).** The public entrypoint
consumes a whole :class:`ClusterBatch` and SORTS its candidates by ``(availability_us,
candidate_id)`` before folding the prospective rule member by member. The sort is a total order
(``candidate_id`` is unique within a batch and breaks any availability tie), so the fold — and
therefore every emitted event and every state byte — is a pure function of the SET of candidates,
never of their arrival order. This is the T1/ACCEPTANCE permutation-invariance guarantee by
construction, not by test luck.

**ROOT identity (``component_id = hash(root)``).** The preimage binds only the root's IMMUTABLE
identity — ``{schema, instrument, side, root_candidate_id}`` — canonical-JSON SHA-256. Instrument
and side can never change (a revision that flips either is refused), and ``root_candidate_id`` is
frozen at formation and never re-rooted, so the id is stable for the life of the component. The
capsule/params digests are deliberately EXCLUDED from the preimage (they are mutable across a
revision; binding them would make identity move under a revision, which "NO REROOT" forbids). This
is a reasoned preimage decision, distinct from :func:`triad_origin.ids.opportunity_cluster_id`
(the sorted-member-hash identity used by the id-schema layer) — the two are not unified here.

**REVISION edge semantics.** A revision that changes a cluster-defining field
(``entry_zone_{low,high}_ticks`` · ``source_structure_id`` · ``source_reaction_id`` ·
``availability_us``) emits ``CLUSTER_REVISION`` and re-evaluates the member's edges =
"does the revised candidate still cluster with at least one OTHER active member of its component?"
A SINGLETON component has no other member, so there is nothing to fail — its revision HOLDS
(membership unchanged), the component surviving with its one member (the dossier's singleton
edge-case reading of "component survives if >= 1 member"). A multi-member component whose revised
member loses every edge RETIRES that member (component survives with the rest) and re-admits the
candidate prospectively (form / join / merge from its revision availability forward). The one
unsupported case is a revised member that is the component's ROOT losing every edge while other
members remain: "component_id = hash(root)" plus "NO REROOT" leaves the surviving component's frozen
identity anchored on a candidate that is no longer a member AND makes the retired root's own
re-formed component collide on ``hash(root)`` — so this is the named refusal
``F19_ROOT_REVISION_UNSUPPORTED`` (fail closed; surfaced as an open spec question, never a corrupted
or re-rooted state).

**TTL / COMPACTION inputs (no wall clock — §determinism).** Terminality and elapsed time arrive as
explicit typed envelopes, never a clock read: :class:`MemberTerminal` marks a member terminal, and
:class:`Watermark` advances the machine's monotonic time; on a watermark, every live component whose
members are ALL terminal AND whose last-member availability is more than ``cluster_window`` behind
the watermark is EXPIRED (``CLUSTER_EXPIRED``) and compacted out of the clustering scan. The
boundary is strict past the window (``watermark - last_member_availability_us > window_us``): a NEW
candidate exactly ``+cluster_window`` from the last member still clusters (inclusive predicate), so
the component must not expire before that candidate could still join.

INPUT LAW (C.3 boundary; every violation is a TYPED rejection BEFORE any state transition):

* ``caps`` maps ``parameter_id -> triad_origin.bindings.VerifiedCapability`` (exact type per entry;
  ``formula_id == "F19"``; ``entry.parameter_id`` equal to its key). A hand-built dict/int/str in
  place of a capability raises :class:`triad_origin.bindings.CapabilityForgeryError`. ``PAR-060``
  (``cluster_window``, ms) is REQUIRED; ``CLUSTER_MAX_MEMBERS`` is ``PROPOSED_MUST_RATIFY`` — its
  value is NEVER hardcoded active (a test asserts no executable ``32`` exists in this module), the
  MECHANISM (REFUSED_CAPACITY) is wired, and while its capability is absent — or carries the
  ``NOT_RATIFIED`` sentinel — every ``ClusterBatch`` yields the named abstention
  ``F19_UNAVAILABLE_CLUSTER_MAX_NOT_RATIFIED`` with ZERO state mutation (SAFE_HOLD, the F09
  LEVEL_TTL posture; the capacity bound cannot be proven, so nothing clusters — fail closed, never
  a fabricated 32). The ``MemberTerminal``/``Watermark`` channels stay live under that refusal.
* ``env`` must be exactly one of :class:`ClusterBatch`, :class:`MemberTerminal`, or
  :class:`Watermark`. Anything else — a raw dict or a subclass — raises :class:`EnvelopeRejected`.

WIRE WIDTH (§1.2): every persisted/hashed integer crosses :func:`triad_origin.exact.guard_int64`;
overflow is ``QUARANTINE_OVERFLOW{formula_id, field, value_digest}`` — never wrap, never emit.

Replay and live consumption call the SAME transition implementation: :func:`evaluate` is the one
transition; :func:`run_clustering_v2` is a thin fold over it (exact-duplicate envelopes are skipped
and counted, mirroring the estate driver's dedup law). Pure: no clock, no I/O, no randomness, no
float, no unordered output.
"""

from __future__ import annotations

from dataclasses import dataclass

# ``bindings`` is referenced as a MODULE (the break_v2 / swing_dc_v2 house pattern), never by
# importing its classes: the exact-type capability check must track the LIVE module identity, so a
# module reload (the sealed-bundle "reload launders nothing" drill) can never split the class
# identity between the minting path (``transition.require_bundle``) and this boundary.
from .. import bindings, canonical, exact
from ..canonical import CanonicalError, canonical_json, loads_canonical
from ..transition import MissingParameterError, TransitionResult
from . import common

FORMULA_F19 = "F19"
V2_FORMULA_VERSION = "opportunity_cluster.v2"
RETIRED_PREDECESSOR = "opportunity_cluster.v1"

# --- capability parameter ids ---------------------------------------------------------------------
PARAM_CLUSTER_WINDOW = "PAR-060"           # OPPORTUNITY_CLUSTER_WINDOW, ms (FPB-0036) — REQUIRED
PARAM_CLUSTER_MAX = "CLUSTER_MAX_MEMBERS"  # PROPOSED_MUST_RATIFY (proposed 32) — no registry row

REFUSE_CONFIG = "REFUSE_CONFIG"

# --- event / audit-fact / abstention kinds --------------------------------------------------------
CLUSTER_FORMED = "CLUSTER_FORMED"
CLUSTER_JOINED = "CLUSTER_JOINED"
CLUSTER_MERGED = "CLUSTER_MERGED"
CLUSTER_REVISION = "CLUSTER_REVISION"
MEMBER_RETIRED = "MEMBER_RETIRED"
MEMBER_TERMINAL = "MEMBER_TERMINAL"
CLUSTER_EXPIRED = "CLUSTER_EXPIRED"
REFUSED_CAPACITY = "REFUSED_CAPACITY"

ABSTAIN_CONTENT_MISMATCH = "F19_CANDIDATE_CONTENT_MISMATCH"
ABSTAIN_CLUSTER_MAX_NOT_RATIFIED = "F19_UNAVAILABLE_CLUSTER_MAX_NOT_RATIFIED"

REVISION_OUTCOME_HELD = "held"
REVISION_OUTCOME_RETIRED = "retired"

STATUS_ACTIVE = "ACTIVE"
STATUS_RETIRED = "RETIRED"

# The candidate fields that define clustering (a revision touching any of these re-evaluates edges).
_CLUSTER_DEFINING_FIELDS = (
    "entry_zone_low_ticks", "entry_zone_high_ticks",
    "source_structure_id", "source_reaction_id", "availability_us",
)
# The full received semantic field set (excludes candidate_id — the map key — and machine fields).
_SEMANTIC_FIELDS = (
    "instrument", "side", "source_structure_id", "source_reaction_id",
    "entry_zone_low_ticks", "entry_zone_high_ticks", "availability_us",
    "occurrence_version", "capsule_id", "capsule_params_digest",
)
_STATE_KEYS = ("formula_version", "candidates", "components", "aliases", "watermark_us")


class EnvelopeRejected(TypeError):
    """A non-envelope object was presented at the public surface (C.3 boundary law)."""


class RefuseConfig(ValueError):
    """The typed ``REFUSE_CONFIG`` refusal (malformed capability faces / unknown keys)."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"{REFUSE_CONFIG}: {detail}")
        self.reason = REFUSE_CONFIG
        self.detail = detail


# ==================================================================================================
# Typed input envelopes (exact-type-checked at the public surface)
# ==================================================================================================


@dataclass(frozen=True)
class CandidateOccurrence:
    """One candidate occurrence (an ORIGIN-internal record, not E01 market data).

    ``availability_us`` is the instant the candidate became knowable; the ``(availability_us,
    candidate_id)`` pair is the ORDERING-LAW key. ``occurrence_version`` disambiguates a revision
    from a redelivery. ``capsule_id``/``capsule_params_digest`` identify the producing capsule.
    """

    candidate_id: str
    instrument: str
    side: str
    source_structure_id: str
    source_reaction_id: str
    entry_zone_low_ticks: int
    entry_zone_high_ticks: int
    availability_us: int
    occurrence_version: int
    capsule_id: str
    capsule_params_digest: str
    source_event_id: str


@dataclass(frozen=True)
class ClusterBatch:
    """A delivery batch of candidate occurrences (arrival order is irrelevant — the machine sorts).

    ``candidates`` is a tuple of :class:`CandidateOccurrence`; a candidate_id appears at most once
    per batch (a within-batch duplicate is refused loudly — redeliveries/revisions arrive as their
    own later batch).
    """

    candidates: tuple
    source_event_id: str


@dataclass(frozen=True)
class MemberTerminal:
    """A member becomes terminal (WITHDRAWN/EXPIRED/DATA_INVALID downstream) — the TTL input.

    ``terminal_time_us`` records when terminality became knowable (kept for audit; the elapsed-time
    test uses the component's last-member availability against the :class:`Watermark`, never a clock).
    """

    candidate_id: str
    terminal_time_us: int
    source_event_id: str


@dataclass(frozen=True)
class Watermark:
    """A monotonic time advance (the only source of "now" — never a wall clock).

    On a watermark every live component whose members are ALL terminal and whose last-member
    availability is strictly more than ``cluster_window`` behind ``watermark_us`` is EXPIRED and
    compacted out of the clustering scan.
    """

    watermark_us: int
    source_event_id: str


def initial_state() -> dict:
    """The cold v2 state: no candidates, no components, no aliases, no watermark."""
    return {
        "formula_version": V2_FORMULA_VERSION,
        "candidates": {},
        "components": {},
        "aliases": {},
        "watermark_us": None,
    }


# ==================================================================================================
# Boundary validation (typed rejections BEFORE any state transition)
# ==================================================================================================


def _validated_caps(caps: object) -> tuple:
    """Validate the capability mapping; return ``(window_us, max_face)``.

    ``window_us`` is the PAR-060 cluster window converted ms -> us (REQUIRED, non-negative).
    ``max_face`` is ``("ratified", n)`` with ``n >= 1``, or ``("unratified", None)``.
    """
    if type(caps) is not dict:
        raise EnvelopeRejected(
            "caps must be a dict mapping parameter_id -> VerifiedCapability, got "
            f"{type(caps).__name__}")
    unknown = sorted(set(caps) - {PARAM_CLUSTER_WINDOW, PARAM_CLUSTER_MAX})
    if unknown:
        raise RefuseConfig(
            f"unknown capability key {unknown[0]!r} — F19 v2 consumes exactly "
            f"{PARAM_CLUSTER_WINDOW!r} (required) and {PARAM_CLUSTER_MAX!r} (optional)")
    if PARAM_CLUSTER_WINDOW not in caps:
        raise MissingParameterError(
            f"required capability {PARAM_CLUSTER_WINDOW!r} (cluster_window) is absent; "
            "F19 v2 fails closed (no code default)")
    for key in sorted(caps):
        cap = caps[key]
        if type(cap) is not bindings.VerifiedCapability:
            raise bindings.CapabilityForgeryError(
                f"caps[{key!r}] must be a VerifiedCapability minted by require_bundle, got "
                f"{type(cap).__name__} — a hand-built parameter cannot enter a production "
                "formula path")
        if cap.formula_id != FORMULA_F19:
            raise bindings.CapabilityForgeryError(
                f"caps[{key!r}] was minted for formula {cap.formula_id!r}; F19 v2 spends only "
                "F19 capabilities")
        if cap.parameter_id != key:
            raise bindings.CapabilityForgeryError(
                f"caps[{key!r}] carries parameter_id {cap.parameter_id!r}; the key and the "
                "capability identity must agree")
    window_us = _window_us(caps[PARAM_CLUSTER_WINDOW].value)
    max_face = (
        _max_face(caps[PARAM_CLUSTER_MAX].value) if PARAM_CLUSTER_MAX in caps
        else ("unratified", None))
    return window_us, max_face


def _capability_nonneg_int(value: object, *, field: str) -> int:
    """A capability declared value as an exact non-negative int (int or canonical decimal string)."""
    if isinstance(value, bool):
        raise RefuseConfig(f"{field} must be an exact non-negative integer, got bool {value!r}")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and value and (value == "0" or (
            value[0] in "123456789" and all(ch in "0123456789" for ch in value))):
        result = int(value)
    else:
        raise RefuseConfig(
            f"{field} must be an exact non-negative integer or its canonical decimal string, "
            f"got {value!r}")
    guarded = exact.guard_int64(result, formula_id=FORMULA_F19, field=field)
    if guarded < 0:
        raise RefuseConfig(f"{field} must be >= 0, got {guarded}")
    return guarded


def _window_us(value: object) -> int:
    """PAR-060: cluster window in ms -> us (converted exactly once, non-negative)."""
    window_ms = _capability_nonneg_int(value, field="cluster_window_ms")
    return exact.guard_int64(window_ms * 1000, formula_id=FORMULA_F19, field="cluster_window_us")


def _max_face(value: object) -> tuple:
    """CLUSTER_MAX_MEMBERS: a ratified exact int >= 1, or the NOT_RATIFIED sentinel."""
    if value == common.NOT_RATIFIED:
        return ("unratified", None)
    n = _capability_nonneg_int(value, field="cluster_max_members")
    if n < 1:
        raise RefuseConfig(f"CLUSTER_MAX_MEMBERS must be >= 1, got {n}")
    return ("ratified", n)


def _nonempty_str(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise EnvelopeRejected(f"{name} must be a non-empty string")
    return value


def _str_field(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise EnvelopeRejected(f"{name} must be a string")
    return value


def _guarded_int(value: object, field: str) -> int:
    """An exact signed-int64 envelope field (§1.2)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise EnvelopeRejected(f"{field} must be an exact int, got {type(value).__name__}")
    return exact.guard_int64(value, formula_id=FORMULA_F19, field=field)


def _validated_occurrence(cand: object) -> dict:
    """Exact-type + field law over one candidate occurrence; returns its parsed row fields."""
    if type(cand) is not CandidateOccurrence:
        raise EnvelopeRejected(
            "ClusterBatch.candidates must each be a CandidateOccurrence (exact type), got "
            f"{type(cand).__name__}")
    candidate_id = _nonempty_str(cand.candidate_id, "candidate_id")
    instrument = _nonempty_str(cand.instrument, "instrument")
    side = common.require_direction(cand.side)
    source_structure_id = _str_field(cand.source_structure_id, "source_structure_id")
    source_reaction_id = _str_field(cand.source_reaction_id, "source_reaction_id")
    zone_low = _guarded_int(cand.entry_zone_low_ticks, "entry_zone_low_ticks")
    zone_high = _guarded_int(cand.entry_zone_high_ticks, "entry_zone_high_ticks")
    if zone_low > zone_high:
        raise common.StructureLawError("entry_zone_low_ticks exceeds entry_zone_high_ticks")
    availability_us = _guarded_int(cand.availability_us, "availability_us")
    occurrence_version = _guarded_int(cand.occurrence_version, "occurrence_version")
    if occurrence_version < 1:
        raise EnvelopeRejected("occurrence_version must be >= 1")
    capsule_id = _nonempty_str(cand.capsule_id, "capsule_id")
    capsule_params_digest = _nonempty_str(cand.capsule_params_digest, "capsule_params_digest")
    _nonempty_str(cand.source_event_id, "source_event_id")
    return {
        "candidate_id": candidate_id, "instrument": instrument, "side": side,
        "source_structure_id": source_structure_id, "source_reaction_id": source_reaction_id,
        "entry_zone_low_ticks": zone_low, "entry_zone_high_ticks": zone_high,
        "availability_us": availability_us, "occurrence_version": occurrence_version,
        "capsule_id": capsule_id, "capsule_params_digest": capsule_params_digest,
        "source_event_id": cand.source_event_id,
    }


def _validated_env(env: object) -> type:
    """Exact-type + field law over the envelope; returns the envelope's type."""
    kind = type(env)
    if kind is ClusterBatch:
        if not isinstance(env.candidates, tuple):
            raise EnvelopeRejected("ClusterBatch.candidates must be a tuple")
        _nonempty_str(env.source_event_id, "source_event_id")
        return kind
    if kind is MemberTerminal:
        _nonempty_str(env.candidate_id, "candidate_id")
        _guarded_int(env.terminal_time_us, "terminal_time_us")
        _nonempty_str(env.source_event_id, "source_event_id")
        return kind
    if kind is Watermark:
        _guarded_int(env.watermark_us, "watermark_us")
        _nonempty_str(env.source_event_id, "source_event_id")
        return kind
    raise EnvelopeRejected(
        "F19 v2 consumes exactly ClusterBatch | MemberTerminal | Watermark (exact types), "
        f"got {type(env).__name__}")


def _state_snapshot(state: object) -> dict:
    """A detached canonical copy of the prior state (the machine never mutates the caller's)."""
    if not isinstance(state, dict):
        raise EnvelopeRejected(f"state must be an object, got {type(state).__name__}")
    if sorted(state) != sorted(_STATE_KEYS):
        raise EnvelopeRejected(
            f"state must carry exactly the keys {sorted(_STATE_KEYS)}, got {sorted(state)}")
    if state.get("formula_version") != V2_FORMULA_VERSION:
        raise EnvelopeRejected(
            f"state carries formula_version {state.get('formula_version')!r}, this machine is "
            f"{V2_FORMULA_VERSION!r} (never-blend across formula versions)")
    try:
        snapshot = loads_canonical(canonical_json(state))
    except CanonicalError as exc:
        raise EnvelopeRejected(f"state is not canonical data: {exc}") from exc
    for name in ("candidates", "components", "aliases"):
        if not isinstance(snapshot.get(name), dict):
            raise EnvelopeRejected(f"state.{name} must be an object")
    return snapshot


# ==================================================================================================
# The clustering predicate (unchanged from v1 — spec: "unchanged")
# ==================================================================================================


def _source_overlap(a: dict, b: dict) -> bool:
    if a["source_structure_id"] and a["source_structure_id"] == b["source_structure_id"]:
        return True
    if a["source_reaction_id"] and a["source_reaction_id"] == b["source_reaction_id"]:
        return True
    return False


def _zones_intersect(a: dict, b: dict) -> bool:
    # Closed-interval intersection (integer ticks, inclusive): zones touching at one tick intersect.
    return (a["entry_zone_low_ticks"] <= b["entry_zone_high_ticks"]
            and b["entry_zone_low_ticks"] <= a["entry_zone_high_ticks"])


def _availability_within_window(a: dict, b: dict, window_us: int) -> bool:
    # Both sides are µs by construction (the caps face converted PAR-060 ms -> µs). Inclusive.
    delta = a["availability_us"] - b["availability_us"]
    if delta < 0:
        delta = -delta
    return delta <= window_us


def _clusters_together(a: dict, b: dict, window_us: int) -> bool:
    # Same instrument AND same side is checked by the caller before this predicate is evaluated
    # (long and short never cluster — absolute, checked first, never one clause among several).
    if _source_overlap(a, b):
        return True
    return _zones_intersect(a, b) and _availability_within_window(a, b, window_us)


def _component_id(instrument: str, side: str, root_candidate_id: str) -> str:
    """``component_id = hash(root)`` — over the root's IMMUTABLE identity only (see module docstring)."""
    return canonical.sha256_hex(canonical.canonical_json({
        "schema": "opportunity_cluster.v2.component_id",
        "instrument": instrument,
        "side": side,
        "root_candidate_id": root_candidate_id,
    }))


def _resolve_alias(aliases: dict, component_id: str) -> str:
    """Resolve a stored ``component_id`` through the append-only alias chain to the live winner."""
    seen: set = set()
    current = component_id
    while current in aliases:
        if current in seen:
            raise common.StructureLawError(
                f"F19 v2 component alias cycle at {current!r} — an invariant was broken")
        seen.add(current)
        current = aliases[current]
    return current


def resolve_canonical_component_id(state: dict, component_id: str) -> str:
    """Public read helper: the canonical (winner) component id for any stored ``component_id``."""
    return _resolve_alias(state.get("aliases", {}), component_id)


def _member_sort_key(work: dict, candidate_id: str) -> tuple:
    row = work["candidates"][candidate_id]
    return (row["availability_us"], candidate_id)


def _sorted_members(work: dict, member_ids: object) -> list:
    """Member ids ordered by ``(availability_us, candidate_id)`` — a canonical, arrival-free order."""
    return sorted(member_ids, key=lambda cid: _member_sort_key(work, cid))


def _last_member_availability(work: dict, member_ids: object) -> int:
    return max(work["candidates"][cid]["availability_us"] for cid in member_ids)


def _live_component(work: dict, component_id: str) -> dict | None:
    comp = work["components"].get(component_id)
    if comp is None or comp["expired"]:
        return None
    return comp


def _other_active_members(work: dict, comp: dict, exclude_id: str) -> list:
    out = []
    for cid in comp["member_candidate_ids"]:
        if cid == exclude_id:
            continue
        row = work["candidates"].get(cid)
        if row is not None and row["status"] == STATUS_ACTIVE and not row["terminal"]:
            out.append(cid)
    return out


# ==================================================================================================
# The public entrypoint — the ONE transition implementation (live == replay)
# ==================================================================================================


def evaluate(caps: object, env: object, state: object) -> TransitionResult:
    """``evaluate(caps, env, state)`` — the C.3 production entrypoint for F19 v2.

    ``caps``  — ``{parameter_id: VerifiedCapability}`` (see the module docstring's INPUT LAW).
    ``env``   — exactly one of ClusterBatch | MemberTerminal | Watermark.
    ``state`` — the prior state object (:func:`initial_state` for a cold start).

    Every boundary violation raises its typed rejection BEFORE any state transition; the returned
    :class:`~triad_origin.transition.TransitionResult` carries a detached state and an ordered
    event tuple. Pure: no clock, no I/O, no randomness, no float.
    """
    window_us, max_face = _validated_caps(caps)
    kind = _validated_env(env)
    prior = _state_snapshot(state)
    if kind is MemberTerminal:
        return _mark_terminal(prior, env)
    if kind is Watermark:
        return _advance_watermark(prior, env, window_us)
    # ClusterBatch — CLUSTER_MAX_MEMBERS refusal posture (PROPOSED_MUST_RATIFY): SAFE_HOLD.
    if max_face[0] != "ratified":
        return TransitionResult(state=prior, events=(common.abstention(
            ABSTAIN_CLUSTER_MAX_NOT_RATIFIED, formula=FORMULA_F19,
            detail="CLUSTER_MAX_MEMBERS is PROPOSED_MUST_RATIFY and not ratified; the capacity "
                   "bound cannot be enforced, so no candidate may cluster (SAFE_HOLD — fail "
                   "closed, never a fabricated 32)",
            refs={"source_event_id": env.source_event_id}),))
    return _admit_batch(prior, env, window_us, max_face[1])


# --- ClusterBatch admission -----------------------------------------------------------------------


def _admit_batch(work: dict, batch: ClusterBatch, window_us: int, max_members: int
                 ) -> TransitionResult:
    parsed = [_validated_occurrence(cand) for cand in batch.candidates]
    seen: set = set()
    for row in parsed:
        if row["candidate_id"] in seen:
            raise common.StructureLawError(
                f"F19 v2 batch carries candidate_id {row['candidate_id']!r} twice; a redelivery "
                "or revision arrives as its own later batch")
        seen.add(row["candidate_id"])

    # THE ORDERING LAW: sort the batch by (availability_us, candidate_id) before the frozen
    # prospective rule. Arrival order can never influence any output.
    ordered = sorted(parsed, key=lambda r: (r["availability_us"], r["candidate_id"]))

    events: list = []
    for row in ordered:
        existing = work["candidates"].get(row["candidate_id"])
        if existing is None:
            events.extend(_admit_new(work, row, window_us, max_members))
        else:
            events.extend(_redeliver(work, existing, row, window_us, max_members))
    return TransitionResult(state=work, events=tuple(events))


def _matched_components(work: dict, row: dict, window_us: int) -> list:
    """The live component ids whose ACTIVE members cluster with ``row`` (same instrument/side).

    Long and short never cluster — the side/instrument gate is applied FIRST, before the predicate.
    Returned sorted for determinism.
    """
    matched: set = set()
    for other_id, other in work["candidates"].items():
        if other_id == row["candidate_id"]:
            continue
        if other["status"] != STATUS_ACTIVE or other["terminal"]:
            continue
        if other["instrument"] != row["instrument"] or other["side"] != row["side"]:
            continue  # long and short never cluster together — absolute, checked first.
        comp = _live_component(work, other["component_id"])
        if comp is None:
            continue
        if _clusters_together(row, other, window_us):
            matched.add(other["component_id"])
    return sorted(matched)


def _store_candidate(work: dict, row: dict, *, component_id: str | None, status: str) -> None:
    stored = {key: row[key] for key in ("candidate_id",) + _SEMANTIC_FIELDS}
    stored["component_id"] = component_id
    stored["status"] = status
    stored["terminal"] = False
    work["candidates"][row["candidate_id"]] = stored


def _admit_new(work: dict, row: dict, window_us: int, max_members: int) -> list:
    """Admit a candidate not yet on file: form / join / merge (or REFUSED_CAPACITY)."""
    candidate_id = row["candidate_id"]
    matched = _matched_components(work, row, window_us)

    if not matched:
        return _form_component(work, row)
    if len(matched) == 1:
        return _join_component(work, row, matched[0], max_members)
    return _merge_components(work, row, matched, max_members)


def _form_component(work: dict, row: dict) -> list:
    """Zero matches: this candidate roots a brand-new component (``component_id = hash(root)``)."""
    candidate_id = row["candidate_id"]
    component_id = _component_id(row["instrument"], row["side"], candidate_id)
    if component_id in work["components"]:
        # The only way a fresh root collides on hash(root) is a retired root re-forming while its
        # frozen ghost component survives — the unsupported case (see the module docstring).
        raise common.StructureLawError(
            f"F19_ROOT_REVISION_UNSUPPORTED: candidate {candidate_id!r} would re-form component "
            f"{component_id!r} which already exists (a retired root cannot re-anchor its own "
            "surviving component's frozen identity)")
    _store_candidate(work, row, component_id=component_id, status=STATUS_ACTIVE)
    work["components"][component_id] = {
        "component_id": component_id,
        "root_candidate_id": candidate_id,
        "member_candidate_ids": [candidate_id],
        "last_member_availability_us": row["availability_us"],
        "expired": False,
    }
    return [{
        "event_kind": CLUSTER_FORMED, "formula": FORMULA_F19,
        "formula_version": V2_FORMULA_VERSION,
        "component_id": component_id, "root_candidate_id": candidate_id,
        "candidate_id": candidate_id, "source_event_id": row["source_event_id"],
    }]


def _join_component(work: dict, row: dict, component_id: str, max_members: int) -> list:
    """One match: append the candidate to the existing component (prospective; no re-root)."""
    candidate_id = row["candidate_id"]
    comp = work["components"][component_id]
    if len(comp["member_candidate_ids"]) + 1 > max_members:
        return [_refused_capacity_event(row, [component_id], len(comp["member_candidate_ids"]) + 1,
                                        max_members)]
    _store_candidate(work, row, component_id=component_id, status=STATUS_ACTIVE)
    members = comp["member_candidate_ids"] + [candidate_id]
    comp["member_candidate_ids"] = _sorted_members(work, members)
    comp["last_member_availability_us"] = _last_member_availability(work, members)
    return [{
        "event_kind": CLUSTER_JOINED, "formula": FORMULA_F19,
        "formula_version": V2_FORMULA_VERSION,
        "component_id": component_id, "root_candidate_id": comp["root_candidate_id"],
        "candidate_id": candidate_id, "source_event_id": row["source_event_id"],
    }]


def _merge_components(work: dict, row: dict, matched: list, max_members: int) -> list:
    """>= 2 matches: a bridging candidate MERGES the components into the min-root winner."""
    candidate_id = row["candidate_id"]
    union_members: list = [candidate_id]
    for component_id in matched:
        union_members.extend(work["components"][component_id]["member_candidate_ids"])
    if len(union_members) > max_members:
        return [_refused_capacity_event(row, matched, len(union_members), max_members)]

    winner_id = _min_root_component(work, matched)
    loser_ids = [cid for cid in matched if cid != winner_id]
    winner = work["components"][winner_id]

    _store_candidate(work, row, component_id=winner_id, status=STATUS_ACTIVE)
    for loser_id in loser_ids:
        loser = work["components"][loser_id]
        for member_id in loser["member_candidate_ids"]:
            work["candidates"][member_id]["component_id"] = winner_id
        work["aliases"][loser_id] = winner_id  # append-only alias record (never a re-root)
        del work["components"][loser_id]        # COMPACTION: one live component after a merge

    winner["member_candidate_ids"] = _sorted_members(work, union_members)
    winner["last_member_availability_us"] = _last_member_availability(work, union_members)
    return [{
        "event_kind": CLUSTER_MERGED, "formula": FORMULA_F19,
        "formula_version": V2_FORMULA_VERSION,
        "component_id": winner_id, "root_candidate_id": winner["root_candidate_id"],
        "candidate_id": candidate_id, "aliased_component_ids": sorted(loser_ids),
        "source_event_id": row["source_event_id"],
    }]


def _min_root_component(work: dict, component_ids: list) -> str:
    """The component whose OWN root is ``(availability_us, candidate_id)``-minimum across the union."""
    def sort_key(component_id: str) -> tuple:
        root_id = work["components"][component_id]["root_candidate_id"]
        root_row = work["candidates"][root_id]
        return (root_row["availability_us"], root_id)
    return min(component_ids, key=sort_key)


def _refused_capacity_event(row: dict, component_ids: list, resulting_count: int, max_members: int
                            ) -> dict:
    """The REFUSED_CAPACITY audit fact — the candidate is NOT admitted; never a silent eviction."""
    return {
        "event_kind": REFUSED_CAPACITY, "formula": FORMULA_F19,
        "formula_version": V2_FORMULA_VERSION,
        "candidate_id": row["candidate_id"],
        "component_ids": sorted(component_ids),
        "resulting_member_count": resulting_count,
        "cluster_max_members": max_members,
        "source_event_id": row["source_event_id"],
    }


# --- redelivery / revision ------------------------------------------------------------------------


def _redeliver(work: dict, existing: dict, row: dict, window_us: int, max_members: int) -> list:
    """A candidate already on file: idempotent redelivery, content mismatch, or revision."""
    candidate_id = row["candidate_id"]
    new_fields = {key: row[key] for key in _SEMANTIC_FIELDS}
    old_fields = {key: existing[key] for key in _SEMANTIC_FIELDS}
    if new_fields == old_fields:
        return []  # identical redelivery: idempotent no-op (T11)

    if row["instrument"] != existing["instrument"] or row["side"] != existing["side"]:
        raise common.StructureLawError(
            f"F19 v2 candidate {candidate_id!r}: a revision may not change instrument or side "
            "(would corrupt an already-clustered component's homogeneity invariant)")

    old_version = existing["occurrence_version"]
    new_version = row["occurrence_version"]
    if new_version <= old_version:
        return [common.abstention(
            ABSTAIN_CONTENT_MISMATCH, formula=FORMULA_F19,
            detail="a same-or-lower occurrence_version carries different content than the stored "
                   "candidate row; refused, never silently overwritten",
            refs={"source_event_id": row["source_event_id"], "candidate_id": candidate_id,
                  "stored_occurrence_version": old_version,
                  "received_occurrence_version": new_version})]

    defining_changed = any(existing[key] != row[key] for key in _CLUSTER_DEFINING_FIELDS)

    # A retired-and-unplaced candidate (component_id is None) is re-admitted fresh under a revision.
    if existing["status"] == STATUS_RETIRED or existing["component_id"] is None:
        return _revise_retired(work, existing, row, window_us, max_members, defining_changed)

    component_id = existing["component_id"]
    comp = _live_component(work, component_id)
    if comp is None:
        # The candidate's component was compacted (TTL EXPIRED) — treat the revision as a fresh
        # prospective re-admission from its revision availability forward.
        return _revise_retired(work, existing, row, window_us, max_members, defining_changed)

    if not defining_changed:
        # A non-defining revision (only occurrence_version / capsule fields moved): record the new
        # row; edges are unchanged so membership never moves.
        return _record_revision(work, existing, row, comp, defining_changed=False,
                                outcome=REVISION_OUTCOME_HELD)

    others = _other_active_members(work, comp, candidate_id)
    revised_view = {**existing, **{key: row[key] for key in _SEMANTIC_FIELDS}}
    edges_hold = any(
        _clusters_together(revised_view, work["candidates"][other_id], window_us)
        for other_id in others)

    if not others or edges_hold:
        # Singleton (nothing to fail — the component survives with its one member) OR the revised
        # member still clusters with a peer: membership unchanged, revision recorded.
        return _record_revision(work, existing, row, comp, defining_changed=True,
                                outcome=REVISION_OUTCOME_HELD)

    # Edges fail on a multi-member component: RETIRE the member, then re-admit prospectively.
    if candidate_id == comp["root_candidate_id"]:
        raise common.StructureLawError(
            f"F19_ROOT_REVISION_UNSUPPORTED: candidate {candidate_id!r} is the root of surviving "
            f"component {component_id!r} and its revision breaks every edge; component_id = "
            "hash(root) + NO REROOT leaves no lawful re-identity (fail closed — a spec question)")
    return _retire_and_readmit(work, existing, row, comp, window_us, max_members)


def _record_revision(work: dict, existing: dict, row: dict, comp: dict, *,
                     defining_changed: bool, outcome: str) -> list:
    """Update the stored row (membership unchanged) and emit CLUSTER_REVISION."""
    candidate_id = row["candidate_id"]
    stored = dict(existing)
    for key in _SEMANTIC_FIELDS:
        stored[key] = row[key]
    work["candidates"][candidate_id] = stored
    # An availability revision can move the component's last-member availability (TTL input).
    comp["last_member_availability_us"] = _last_member_availability(
        work, comp["member_candidate_ids"])
    comp["member_candidate_ids"] = _sorted_members(work, comp["member_candidate_ids"])
    return [{
        "event_kind": CLUSTER_REVISION, "formula": FORMULA_F19,
        "formula_version": V2_FORMULA_VERSION,
        "candidate_id": candidate_id, "component_id": comp["component_id"],
        "from_occurrence_version": existing["occurrence_version"],
        "to_occurrence_version": row["occurrence_version"],
        "cluster_defining_change": defining_changed,
        "outcome": outcome, "source_event_id": row["source_event_id"],
    }]


def _retire_and_readmit(work: dict, existing: dict, row: dict, comp: dict, window_us: int,
                        max_members: int) -> list:
    """Edges failed: retire the member from its component (it survives), then re-admit prospectively."""
    candidate_id = row["candidate_id"]
    component_id = comp["component_id"]
    remaining = [cid for cid in comp["member_candidate_ids"] if cid != candidate_id]
    comp["member_candidate_ids"] = _sorted_members(work, remaining)
    comp["last_member_availability_us"] = _last_member_availability(work, remaining)
    component_survives = len(remaining) >= 1
    if not component_survives:  # structurally unreachable: a singleton HOLDS above, never retires
        del work["components"][component_id]  # pragma: no cover

    # Update the row to the revised fields and detach it from the old component (RETIRED, unplaced).
    stored = dict(existing)
    for key in _SEMANTIC_FIELDS:
        stored[key] = row[key]
    stored["status"] = STATUS_RETIRED
    stored["component_id"] = None
    work["candidates"][candidate_id] = stored

    events: list = [
        {
            "event_kind": CLUSTER_REVISION, "formula": FORMULA_F19,
            "formula_version": V2_FORMULA_VERSION,
            "candidate_id": candidate_id, "component_id": component_id,
            "from_occurrence_version": existing["occurrence_version"],
            "to_occurrence_version": row["occurrence_version"],
            "cluster_defining_change": True, "outcome": REVISION_OUTCOME_RETIRED,
            "source_event_id": row["source_event_id"],
        },
        {
            "event_kind": MEMBER_RETIRED, "formula": FORMULA_F19,
            "formula_version": V2_FORMULA_VERSION,
            "candidate_id": candidate_id, "component_id": component_id,
            "remaining_member_count": len(remaining),
            "component_survives": component_survives,
            "source_event_id": row["source_event_id"],
        },
    ]
    # Prospective re-clustering from the revision availability forward.
    events.extend(_admit_new(work, row, window_us, max_members))
    return events


def _revise_retired(work: dict, existing: dict, row: dict, window_us: int, max_members: int,
                    defining_changed: bool) -> list:
    """A revision of an unplaced (RETIRED / compacted) candidate: update fields + re-admit prospectively."""
    candidate_id = row["candidate_id"]
    stored = dict(existing)
    for key in _SEMANTIC_FIELDS:
        stored[key] = row[key]
    stored["status"] = STATUS_RETIRED
    stored["component_id"] = None
    work["candidates"][candidate_id] = stored
    events: list = [{
        "event_kind": CLUSTER_REVISION, "formula": FORMULA_F19,
        "formula_version": V2_FORMULA_VERSION,
        "candidate_id": candidate_id, "component_id": None,
        "from_occurrence_version": existing["occurrence_version"],
        "to_occurrence_version": row["occurrence_version"],
        "cluster_defining_change": defining_changed, "outcome": REVISION_OUTCOME_RETIRED,
        "source_event_id": row["source_event_id"],
    }]
    events.extend(_admit_new(work, row, window_us, max_members))
    return events


# --- MemberTerminal / Watermark (TTL inputs; live under the CLUSTER_MAX refusal) ------------------


def _mark_terminal(work: dict, env: MemberTerminal) -> TransitionResult:
    """Mark a member terminal (a TTL input). An unknown candidate refuses; a repeat is a no-op."""
    candidate_id = _nonempty_str(env.candidate_id, "candidate_id")
    row = work["candidates"].get(candidate_id)
    if row is None:
        raise common.StructureLawError(
            f"F19 v2 MemberTerminal for unknown candidate {candidate_id!r} (never fabricated)")
    if row["terminal"]:
        return TransitionResult(state=work)  # idempotent
    row["terminal"] = True
    return TransitionResult(state=work, events=({
        "event_kind": MEMBER_TERMINAL, "formula": FORMULA_F19,
        "formula_version": V2_FORMULA_VERSION,
        "candidate_id": candidate_id, "component_id": row["component_id"],
        "terminal_time_us": env.terminal_time_us, "source_event_id": env.source_event_id,
    },))


def _advance_watermark(work: dict, env: Watermark, window_us: int) -> TransitionResult:
    """Advance the monotonic watermark; EXPIRE + compact every all-terminal, window-elapsed component."""
    watermark = _guarded_int(env.watermark_us, "watermark_us")
    prior = work["watermark_us"]
    if prior is not None and watermark < prior:
        raise common.StructureLawError(
            f"F19 v2 watermark regression: {watermark} does not follow {prior}")
    work["watermark_us"] = watermark
    events: list = []
    for component_id in sorted(work["components"]):
        comp = work["components"][component_id]
        if comp["expired"] or not comp["member_candidate_ids"]:
            continue
        all_terminal = all(
            work["candidates"][cid]["terminal"] for cid in comp["member_candidate_ids"])
        if not all_terminal:
            continue
        # Strict: a candidate exactly +cluster_window from the last member still clusters, so the
        # component must not expire before that candidate could still join.
        if watermark - comp["last_member_availability_us"] <= window_us:
            continue
        comp["expired"] = True
        events.append({
            "event_kind": CLUSTER_EXPIRED, "formula": FORMULA_F19,
            "formula_version": V2_FORMULA_VERSION,
            "component_id": component_id, "root_candidate_id": comp["root_candidate_id"],
            "member_count": len(comp["member_candidate_ids"]),
            "last_member_availability_us": comp["last_member_availability_us"],
            "watermark_us": watermark, "source_event_id": env.source_event_id,
        })
    return TransitionResult(state=work, events=tuple(events))


# ==================================================================================================
# The fold used identically for live and replay (one transition implementation: evaluate)
# ==================================================================================================


@dataclass(frozen=True)
class ClusteringRunResult:
    """Detached fold result: final state, ordered events, exact-duplicate count."""

    final_state: dict
    events: tuple
    duplicate_count: int


def _occurrence_body(cand: CandidateOccurrence) -> dict:
    """A fixed, closed field projection of one occurrence for dedup fingerprinting."""
    return {
        "candidate_id": cand.candidate_id, "instrument": cand.instrument, "side": cand.side,
        "source_structure_id": cand.source_structure_id,
        "source_reaction_id": cand.source_reaction_id,
        "entry_zone_low_ticks": cand.entry_zone_low_ticks,
        "entry_zone_high_ticks": cand.entry_zone_high_ticks,
        "availability_us": cand.availability_us, "occurrence_version": cand.occurrence_version,
        "capsule_id": cand.capsule_id, "capsule_params_digest": cand.capsule_params_digest,
        "source_event_id": cand.source_event_id,
    }


def _env_fingerprint(env: object) -> bytes | None:
    """Canonical identity bytes for exact-duplicate dedup (None => let evaluate reject it)."""
    if type(env) is ClusterBatch:
        if not isinstance(env.candidates, tuple):
            return None
        cands = []
        for cand in env.candidates:
            if type(cand) is not CandidateOccurrence:
                return None
            cands.append(_occurrence_body(cand))
        body = {"kind": "BATCH", "candidates": cands, "source_event_id": env.source_event_id}
    elif type(env) is MemberTerminal:
        body = {"kind": "TERMINAL", "candidate_id": env.candidate_id,
                "terminal_time_us": env.terminal_time_us, "source_event_id": env.source_event_id}
    elif type(env) is Watermark:
        body = {"kind": "WATERMARK", "watermark_us": env.watermark_us,
                "source_event_id": env.source_event_id}
    else:
        return None
    try:
        return canonical_json(body)
    except (CanonicalError, TypeError):
        return None


def run_clustering_v2(caps: object, inputs: list, initial: dict | None = None
                      ) -> ClusteringRunResult:
    """Fold ``inputs`` (already in deterministic delivery order) through :func:`evaluate`.

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
    return ClusteringRunResult(
        final_state=loads_canonical(canonical_json(state)),
        events=tuple(events),
        duplicate_count=duplicate_count,
    )
