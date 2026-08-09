"""F19 — opportunity clustering and alias control (golden vector GV-016).

Exact RC3 formula text (F19)::

    cluster_id=hash(version,params,instrument,side,root_candidate_id); root fixed at creation by
    min(availability,candidate_id); later members append revisions and never re-root.

RC3's own "RC2 source preserved" note keeps the RC2 membership predicate as the still-governing
alias/clustering rule (``rc2_source_formula``, mirrored verbatim by the ``PAR-060`` control-bundle
row's ``exact_rule``)::

    Two candidates cluster iff same instrument/side and their source structure/reaction IDs
    overlap OR entry zones intersect and availability distance<=cluster_window.

**Mirror law (absolute, no exceptions): "Long and short never cluster together in baseline."** A
``LONG`` and a ``SHORT`` candidate never cluster, full stop — this is checked BEFORE the RC2
predicate is even evaluated, never merely as one clause among several.

**GV-016.** Same instrument/side, zones touching at exactly one tick, availability delta = 30000ms
-> SAME cluster (the closed-interval intersection test treats touching endpoints as intersecting,
and the availability-distance bound is PAR-009 inclusive — equality passes). The stated boundary
case, "delta=30001ms with no source overlap -> separate", fixes the window as INCLUSIVE at exactly
``cluster_window`` and EXCLUSIVE one unit past it; it also shows that zone-touching alone, with no
source overlap, still needs the availability-distance conjunct to hold — the RC2 predicate is
``source_overlap OR (zones_intersect AND availability_distance<=cluster_window)``, not
``source_overlap OR zones_intersect``.

**Unit law (PAR-060, load-bearing).** ``PAR-060 OPPORTUNITY_CLUSTER_WINDOW`` is declared in
MILLISECONDS (``declared_value "30000"``, ``unit "ms"``); the candidate occurrence's
``availability_us`` field is in MICROSECONDS. This module converts the parameter to microseconds
exactly once, at the top of :meth:`OpportunityClusterRegistry.transition`
(``window_us = cluster_window_ms * 1000``), and every downstream comparison operates on
microseconds only — an accidental unit mismatch is the single easiest way to silently move GV-016's
boundary. PAR-060's control-bundle row carries status ``PROPOSED_RC2_MUST_RATIFY`` /
``lifecycle_status BLOCKED_BINDING_V2_MIGRATION`` (ratification is an operator/activation fact, not
a code fact — see ``docs/control/rc3_effective_control_bundle.json``); this machine, per the
2026-08-09 operator directive, consumes it as a PLAIN required int (``transition.require`` — fail
closed on absence, never a code default), not as a ``common.NOT_RATIFIED``-sentinel-gated value the
way F06's ``equal_level_max_span`` is — that gating pattern is specific to the RC3-PAR-STRUCT-001
row F06 cites and is not asked for, and is not invented, here.

**``cluster_id`` field binding (reasoned, not guessed).** The formula's ``version`` and ``params``
terms bind to the ONLY two candidate-occurrence fields that represent an identity/parameter-set
concept: ``capsule_id`` (the semantic capsule identity that produced this candidate — "version") and
``capsule_params_digest`` (the digest of the exact parameter set that capsule used — "params"). No
other candidate field represents either concept, so the bind is by elimination as well as by name,
mirroring :mod:`capsules`'s evidence-cited binding discipline. ``root_candidate_id`` is always the
candidate_id of the occurrence that roots the cluster — see the connected-components law below.

**Connected-components law (transitive, never root-only).** A new candidate_id is compared against
EVERY existing same-instrument/same-side candidate row, and a match against ANY member of an
existing cluster — root or not — puts that cluster's id in the matched set (this is what makes a
third candidate joining only through a non-root member still land in the right cluster). Exactly one
matched cluster -> join it (append-only; ``root_candidate_id`` NEVER changes once a cluster exists —
"never re-root"). Zero matched clusters -> this occurrence roots a brand-new cluster
(``root_candidate_id = candidate_id``). **Two or more matched clusters simultaneously is a genuine
conflict the formula's "never re-root" law forbids resolving by picking one or by fabricating a
merge** (merging would require moving one cluster's members under the other's root, i.e. re-rooting
it) — this occurrence is refused with the named abstention ``F19_AMBIGUOUS_CLUSTER_MERGE``: no
candidate row is written, no cluster is touched, the conflict is named, not silently picked.

**``root fixed at creation by min(availability,candidate_id)`` — how it is realized here.** This
machine processes one envelope per ``transition()`` call, in the caller's deterministic partition
order (Doc 02 §02.16); it never evaluates two occurrences "at once". Two candidates that would each
independently root a new cluster, but that actually match each other, are therefore never compared
simultaneously — the FIRST of the two to arrive roots the cluster, and the SECOND joins it through
the ordinary "exactly one matched cluster" path above. This is exactly what ``min(availability,
candidate_id)`` reduces to under processing order: whichever occurrence the upstream, ordered feed
delivers first wins the root, and no separate tie-break comparison is coded here.

**Redelivery and revision law (content-hash comparison, mirroring ``shadow_ledger.py``'s dedup
law).** A ``CANDIDATE_OCCURRENCE`` for a ``candidate_id`` already on file is one of exactly three
things, decided by exact field comparison — never guessed:

* the identical full payload (every field, including ``occurrence_version``) -> idempotent no-op:
  no state mutation, no event;
* a payload with a STRICTLY GREATER ``occurrence_version`` -> a genuine revision: the candidate
  row's own fields update in place (``cluster_id`` is untouched — a revision is never a re-root,
  by the same law that forbids merging two clusters) and a ``CANDIDATE_REVISED`` event is emitted;
* anything else (a same-or-lower ``occurrence_version`` carrying different content) -> a content
  collision on an unrevised delivery, refused with the named abstention
  ``F19_CANDIDATE_CONTENT_MISMATCH``: the stored row is left exactly as it was, never silently
  overwritten.

A revision may never change ``instrument`` or ``side`` — doing so on an already-clustered candidate
would silently corrupt that cluster's same-instrument/same-side homogeneity invariant (the exact
invariant the mirror law depends on), so this is refused loudly (``StructureLawError``) rather than
accepted as a normal revision.

The candidate row this module stores extends the task's minimal shape
(``instrument``/``side``/``source_structure_id``/``source_reaction_id``/``entry_zone_low_ticks``/
``entry_zone_high_ticks``/``availability_us``/``cluster_id``) with ``occurrence_version``,
``capsule_id`` and ``capsule_params_digest`` — required to implement the redelivery/revision law
above and the ``cluster_id`` hash inputs; this is the semantic core the task describes, not a
literal exhaustive key list.

Input envelope shape (minimal, explicit)::

    {"event_id": str, "kind": "CANDIDATE_OCCURRENCE",
     "payload": {"candidate_id": str, "instrument": str, "side": "LONG" | "SHORT",
                 "source_structure_id": str, "source_reaction_id": str,
                 "entry_zone_low_ticks": int, "entry_zone_high_ticks": int,
                 "availability_us": int, "occurrence_version": int,
                 "capsule_id": str, "capsule_params_digest": str}}

Every semantic parameter arrives via :func:`triad_origin.transition.require` — no code default,
ever. Thresholds are inclusive (PAR-009).
"""

from __future__ import annotations

from .. import canonical
from ..transition import Envelope, Params, Quality, State, TransitionResult, require
from . import common

FORMULA_F19 = "F19"

PARAM_CLUSTER_WINDOW_MS = "cluster_window_ms"

_KIND_CANDIDATE_OCCURRENCE = "CANDIDATE_OCCURRENCE"

CLUSTER_FORMED = "CLUSTER_FORMED"
CLUSTER_JOINED = "CLUSTER_JOINED"
CANDIDATE_REVISED = "CANDIDATE_REVISED"

F19_AMBIGUOUS_CLUSTER_MERGE = "F19_AMBIGUOUS_CLUSTER_MERGE"
F19_CANDIDATE_CONTENT_MISMATCH = "F19_CANDIDATE_CONTENT_MISMATCH"

# The candidate row fields compared for the redelivery/revision law (see module docstring). This
# intentionally excludes ``candidate_id`` (the dict key, not a row field) and ``cluster_id`` (a
# derived field the machine assigns, never part of the received payload).
_SEMANTIC_FIELDS = (
    "instrument", "side", "source_structure_id", "source_reaction_id",
    "entry_zone_low_ticks", "entry_zone_high_ticks", "availability_us",
    "occurrence_version", "capsule_id", "capsule_params_digest",
)


def _event_identity(envelope: Envelope) -> str:
    event_id = envelope.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        raise common.StructureLawError("envelope event_id must be a non-empty string")
    return event_id


def _nonempty_str(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise common.StructureLawError(f"F19 {name} must be a non-empty string")
    return value


def _str_field(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise common.StructureLawError(f"F19 {name} must be a string")
    return value


def _typed_payload(envelope: Envelope) -> tuple[str, dict]:
    event_id = _event_identity(envelope)
    if envelope.get("kind") != _KIND_CANDIDATE_OCCURRENCE:
        raise common.StructureLawError(
            f"F19 consumes {_KIND_CANDIDATE_OCCURRENCE!r} envelopes only, "
            f"got {envelope.get('kind')!r}")
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise common.StructureLawError("F19 envelope payload must be an object")
    return event_id, payload


def _parse_candidate(payload: dict) -> dict:
    candidate_id = _nonempty_str(payload.get("candidate_id"), "candidate_id")
    instrument = _nonempty_str(payload.get("instrument"), "instrument")
    side = common.require_direction(payload.get("side"))
    source_structure_id = _str_field(payload.get("source_structure_id"), "source_structure_id")
    source_reaction_id = _str_field(payload.get("source_reaction_id"), "source_reaction_id")
    zone_low = common.require_int(payload.get("entry_zone_low_ticks"), "entry_zone_low_ticks")
    zone_high = common.require_int(payload.get("entry_zone_high_ticks"), "entry_zone_high_ticks")
    if zone_low > zone_high:
        raise common.StructureLawError("entry_zone_low_ticks exceeds entry_zone_high_ticks")
    availability_us = common.require_int(payload.get("availability_us"), "availability_us")
    occurrence_version = common.require_int(
        payload.get("occurrence_version"), "occurrence_version")
    capsule_id = _nonempty_str(payload.get("capsule_id"), "capsule_id")
    capsule_params_digest = _nonempty_str(
        payload.get("capsule_params_digest"), "capsule_params_digest")
    return {
        "candidate_id": candidate_id, "instrument": instrument, "side": side,
        "source_structure_id": source_structure_id, "source_reaction_id": source_reaction_id,
        "entry_zone_low_ticks": zone_low, "entry_zone_high_ticks": zone_high,
        "availability_us": availability_us, "occurrence_version": occurrence_version,
        "capsule_id": capsule_id, "capsule_params_digest": capsule_params_digest,
    }


def _source_overlap(a: dict, b: dict) -> bool:
    if a["source_structure_id"] and b["source_structure_id"] \
            and a["source_structure_id"] == b["source_structure_id"]:
        return True
    if a["source_reaction_id"] and b["source_reaction_id"] \
            and a["source_reaction_id"] == b["source_reaction_id"]:
        return True
    return False


def _zones_intersect(a: dict, b: dict) -> bool:
    # Closed-interval intersection (PAR-009 inclusive): zones touching at one tick intersect.
    return a["entry_zone_low_ticks"] <= b["entry_zone_high_ticks"] \
        and b["entry_zone_low_ticks"] <= a["entry_zone_high_ticks"]


def _availability_within_window(a: dict, b: dict, window_us: int) -> bool:
    # window_us is already the caller-converted PAR-060 bound (ms -> us); both sides of this
    # comparison share units by construction (see the module docstring's unit law).
    return abs(a["availability_us"] - b["availability_us"]) <= window_us


def _clusters_together(a: dict, b: dict, window_us: int) -> bool:
    if _source_overlap(a, b):
        return True
    return _zones_intersect(a, b) and _availability_within_window(a, b, window_us)


def _cluster_id(parsed: dict) -> str:
    payload = {
        "version": parsed["capsule_id"],
        "params": parsed["capsule_params_digest"],
        "instrument": parsed["instrument"],
        "side": parsed["side"],
        "root_candidate_id": parsed["candidate_id"],
    }
    return canonical.sha256_hex(canonical.canonical_json(payload))


class OpportunityClusterRegistry:
    """F19 — opportunity clustering and alias control
    (:class:`triad_origin.transition.DeterministicMachine`).

    See the module docstring for the RC3/RC2 formula text, the mirror law, the unit conversion,
    the connected-components join/root/ambiguous-merge law and the redelivery/revision law.
    """

    def initial_state(self) -> State:
        return {"candidates": {}, "clusters": {}}

    def transition(
        self, state: State, envelope: Envelope, params: Params, quality: Quality
    ) -> TransitionResult:
        window_ms = common.require_int(
            require(params, PARAM_CLUSTER_WINDOW_MS), PARAM_CLUSTER_WINDOW_MS)
        if window_ms < 0:
            raise common.StructureLawError(
                f"{PARAM_CLUSTER_WINDOW_MS} must be >= 0, got {window_ms}")
        window_us = window_ms * 1000

        event_id, payload = _typed_payload(envelope)
        parsed = _parse_candidate(payload)
        candidate_id = parsed["candidate_id"]

        existing = state["candidates"].get(candidate_id)
        if existing is not None:
            return self._redeliver(state, existing, parsed, event_id)
        return self._admit_new(state, parsed, event_id, window_us)

    def _redeliver(
        self, state: State, existing: dict, parsed: dict, event_id: str
    ) -> TransitionResult:
        candidate_id = parsed["candidate_id"]
        new_fields = {key: parsed[key] for key in _SEMANTIC_FIELDS}
        old_fields = {key: existing[key] for key in _SEMANTIC_FIELDS}
        if new_fields == old_fields:
            return TransitionResult(state=state)  # identical redelivery: idempotent no-op

        if parsed["instrument"] != existing["instrument"] or parsed["side"] != existing["side"]:
            raise common.StructureLawError(
                f"F19 candidate {candidate_id!r}: a revision may not change instrument or side "
                "(would corrupt an already-clustered candidate's homogeneity invariant)")

        old_version = existing["occurrence_version"]
        new_version = parsed["occurrence_version"]
        if new_version <= old_version:
            event = common.abstention(
                F19_CANDIDATE_CONTENT_MISMATCH, formula=FORMULA_F19,
                detail="a same-or-lower occurrence_version carries different content than the "
                       "stored candidate row; refused, never silently overwritten",
                refs={"event_id": event_id, "candidate_id": candidate_id,
                      "stored_occurrence_version": old_version,
                      "received_occurrence_version": new_version})
            return TransitionResult(state=state, events=(event,))

        row = dict(existing)
        for key in _SEMANTIC_FIELDS:
            row[key] = parsed[key]
        candidates = dict(state["candidates"])
        candidates[candidate_id] = row
        event = {
            "event_kind": CANDIDATE_REVISED, "formula": FORMULA_F19,
            "candidate_id": candidate_id, "cluster_id": row["cluster_id"],
            "from_occurrence_version": old_version, "to_occurrence_version": new_version,
        }
        return TransitionResult(
            state={"candidates": candidates, "clusters": state["clusters"]}, events=(event,))

    def _admit_new(
        self, state: State, parsed: dict, event_id: str, window_us: int
    ) -> TransitionResult:
        candidate_id = parsed["candidate_id"]
        matched_cluster_ids: set[str] = set()
        for other_row in state["candidates"].values():
            if other_row["instrument"] != parsed["instrument"]:
                continue
            if other_row["side"] != parsed["side"]:
                continue  # LONG and SHORT never cluster together — absolute, checked first.
            if _clusters_together(parsed, other_row, window_us):
                matched_cluster_ids.add(other_row["cluster_id"])

        if len(matched_cluster_ids) > 1:
            event = common.abstention(
                F19_AMBIGUOUS_CLUSTER_MERGE, formula=FORMULA_F19,
                detail="candidate matches members of two or more existing clusters at once; a "
                       "cluster root is fixed at creation and never re-rooted, so no merge is "
                       "performed and this occurrence is refused",
                refs={"event_id": event_id, "candidate_id": candidate_id,
                      "matched_cluster_ids": sorted(matched_cluster_ids)})
            return TransitionResult(state=state, events=(event,))

        candidates = dict(state["candidates"])
        clusters = dict(state["clusters"])
        row = {key: parsed[key] for key in _SEMANTIC_FIELDS}

        if len(matched_cluster_ids) == 1:
            cluster_id = next(iter(matched_cluster_ids))
            cluster = state["clusters"][cluster_id]
            clusters[cluster_id] = {
                "root_candidate_id": cluster["root_candidate_id"],
                "member_candidate_ids": list(cluster["member_candidate_ids"]) + [candidate_id],
            }
            row["cluster_id"] = cluster_id
            candidates[candidate_id] = row
            event = {
                "event_kind": CLUSTER_JOINED, "formula": FORMULA_F19,
                "cluster_id": cluster_id, "root_candidate_id": cluster["root_candidate_id"],
                "candidate_id": candidate_id,
            }
            return TransitionResult(
                state={"candidates": candidates, "clusters": clusters}, events=(event,))

        cluster_id = _cluster_id(parsed)
        clusters[cluster_id] = {
            "root_candidate_id": candidate_id, "member_candidate_ids": [candidate_id]}
        row["cluster_id"] = cluster_id
        candidates[candidate_id] = row
        event = {
            "event_kind": CLUSTER_FORMED, "formula": FORMULA_F19,
            "cluster_id": cluster_id, "root_candidate_id": candidate_id,
        }
        return TransitionResult(
            state={"candidates": candidates, "clusters": clusters}, events=(event,))
