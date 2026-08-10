"""F14 — departure and first retest/touch (golden vector GV-012).

Exact RC3 formula text (``rc3_effective_control_bundle.json`` formula F14,
``semantic_version "reaction.first_touch.v1"``): *"Departure satisfied when directional distance
from near edge reaches dep_ticks and min_depart_events/time. First contact is earliest later
observation whose registered price/range intersects frozen zone after departure."*

Lifecycle: ``ELIGIBLE`` -> ``DEPARTED`` -> ``FIRST_TOUCH_CONSUMED`` or ``EXPIRED`` or
``INVALIDATED`` — a closed, append-only graph (once a zone reaches ``FIRST_TOUCH_CONSUMED``,
``EXPIRED`` or ``INVALIDATED`` no further transition is legal, mirroring
:mod:`triad_origin.structures.lifecycle_reducer`'s terminal-state law). ``EXPIRED``/
``INVALIDATED`` are reachable from EITHER non-terminal state (``ELIGIBLE`` or ``DEPARTED`` —
mirroring :mod:`triad_origin.structures.fvg_registry`, whose bar-count TTL can expire a zone that
was never touched, i.e. from its formation state directly, not only from a partially-progressed
one); the RC3 ``lifecycle_or_output`` arrow chain is the typical path, not an exhaustive edge list.

**Departure (PAR-050/166/167, ALL THREE conjuncts, each inclusive per PAR-009):**

* ``directional_distance_from_near_edge_ticks >= dep_ticks`` where
  ``dep_ticks = evaluate_declared_rational(DECLARED_MIN_DEPARTURE, ATR14_ticks)`` — PAR-050's
  declared value ``"max(2,ceil(ATR14_ticks*1/10))"`` is byte-identical to PAR-041's
  (:data:`triad_origin.structures.common.DECLARED_EQUAL_LEVEL_TOLERANCE`), so this module reuses
  the new alias :data:`triad_origin.structures.common.DECLARED_MIN_DEPARTURE` rather than
  re-declaring the ratio (the PAR-156 precedent).
* ``depart_event_count >= MIN_DEPART_EVENTS`` (PAR-166, plain int) where ``MIN_DEPART_EVENTS`` is
  admitted only at its exact ``declared_value "1"`` — "Formation bar excluded": at least one later
  finalized base bar past formation/confirmation. Like PAR-050/168 (both also
  ``PROPOSED_RC2_MUST_RATIFY``) and PAR-062, the parameter itself is byte-pinned to the exact
  declared value — any other ``min_depart_events`` is a configuration defect, refused
  (:class:`triad_origin.structures.common.StructureLawError`), never silently range-admitted.
* ``elapsed_depart_time_ms >= MIN_DEPART_TIME`` (PAR-167, plain int ms) where ``MIN_DEPART_TIME``
  is admitted only at its exact ``declared_value "60000"`` — "Exactly 60000 ms passes after
  event-count rule also passes." Same exact-declared-value pin as PAR-166 above.

The upstream caller (the owning structure's own bar-by-bar tracking) computes all three figures
as of the candidate observation; this machine only compares them against the ratified floors — it
holds no incremental departure-progress state of its own. A zone already ``DEPARTED`` or past
terminal ignores a further ``DEPARTURE_CANDIDATE`` (idempotent-shaped no-op, no re-departure); one
or more conjuncts unmet is a silent non-emission (still ``ELIGIBLE``, mirroring F10's
below-threshold silence); a missing/null causal ATR is the named abstention ``F14_NO_ATR`` (no
departure recorded, no state mutation — the warm-up-abstention law every ATR-scaled formula here
shares).

**First contact (PAR-062/168, GV-012).** ``CONTACT_PRICE_SOURCE`` (PAR-168) is a plain declared
STRING, not a rational rule: the only lawful value is the exact string
``"finalized_bar_closed_range_[low,high]"`` — both the machine's own required parameter and each
individual ``CONTACT_OBSERVATION``'s own claimed ``contact_source`` field must equal it byte-for-
byte, or the observation is refused (``StructureLawError`` — an undeclared source is a law
violation, not silent formation noise). ``FIRST_TOUCH_ORDINAL`` (PAR-062) is
``RATIFIED_RC1`` at exactly ``1`` — a caller supplying anything else is a configuration defect
and is refused; the ordinal itself needs no runtime counting because the DEPARTED-only,
one-shot ``DEPARTED`` -> ``FIRST_TOUCH_CONSUMED`` transition already IS "the first eligible
post-departure intersection consumes": a contact before departure, or any contact once a zone is
already terminal (including a second, later intersection on the SAME zone — GV-012's "second
identical touch -> no second candidate" boundary) is silently IGNORED, never a second candidate.

"Registered price/range intersects frozen zone" is the CLOSED interval intersection of
``[observed_low_ticks, observed_high_ticks]`` against the CLOSED zone interval
``[min(z_near_ticks, z_far_ticks), max(z_near_ticks, z_far_ticks)]`` — boundary price equality
counts as a touch (PAR-062's own ``boundary_rule``, PAR-009 inclusive). A non-intersecting
observation on a ``DEPARTED`` zone is a silent no-op (still ``DEPARTED``, waiting for the real
first touch). On intersection the zone moves ``DEPARTED`` -> ``FIRST_TOUCH_CONSUMED`` and emits a
``REACTION_CONFIRMED`` event carrying the raw contact fields plus a derived, stable
``source_reaction_id`` for a later F18/candidate-publisher consumer.

**``source_reaction_id`` binds the full RC3 F14 identity material** ("structure ID + departure
event + first contact event + params"): the hash material is ``{formula, semantic_version,
structure_id=zone_id, departure_event_id (the DEPARTURE_CANDIDATE that carried the zone into
DEPARTED, stored on the row at that transition), first-contact event (its ``contact_event_id`` and
the observed price/range), params_digest (the five declared F14 parameters + the semantic
version)}``. Binding the departure event and the params closes two identity collisions the earlier
``{zone_id, event_time_us, observed_low_ticks, observed_high_ticks}`` shape allowed: two zones that
departed via different departure events but touched identically, and two runs under a different F14
parameter generation with an identical touch, previously minted the SAME id.

**Golden-boundary dispositions (RC3 F14 ``golden_boundary_tests``).** Of the six named boundaries,
five are exercised by this module's battery — same-bar trap (``TestContactTiming`` /
``TestGv012``), exact edge (``TestBoundaryIntersection``), duplicate contact (``TestGv012``'s
second identical touch), invalidation precedence (``TestContactTiming``'s expiry/invalidation) and
mirror (``TestMirror``). The sixth, **"maker pre-post distinction," is undefined in the
authoritative sources** (it appears only in the F14 formula row and the REQ-F14-* acceptance rows
that repeat the identical boundary list verbatim; RC3 master, errata and the golden vectors define
no such boundary), so its disposition is DEFERRED to a ``09_OPEN_QUESTIONS`` register row rather
than guessed at in code — a meaning fabricated here would be a silent invention, forbidden.

**TTL disposition (RC3 F14 ``parameters`` names "TTL").** No F14 TTL parameter binding exists in
the bundle (the only TTL bindings are the F15-F17 ``FLOW_ATOM_TTL`` and the F21 ``MAKER_ORDER_TTL``
rows), so there is no declared value to materialize without fabrication. F14 externalizes zone
expiry as caller-supplied ``ZONE_EXPIRED`` events delivered by the owning zone registry's own
lifecycle (fvg/order-block/reclaim), which this machine consumes; the disposition is DEFERRED to a
``09_OPEN_QUESTIONS`` register row (the E15 precedent for the byte-analogous F12 TTL situation).

**Zone registration.** ``ZONE_REGISTERED`` freezes a structure zone's original geometry
(``z_near_ticks``, ``z_far_ticks``, direction, registration knowledge time) and seeds
``ELIGIBLE``. Direction-aware near/far: for ``LONG`` the near edge is the HIGHER bound (the edge
closest to price approaching the support zone from above); ``SHORT`` mirrors exactly (the near
edge is the LOWER bound, price approaching a resistance zone from below). A repeated registration
of an already-known ``zone_id`` is ignored (idempotent-shaped, no re-registration — the F13
"already excursed; ignore re-excursion" precedent); the near/far ordering matters only for the
directional-mirror proof, since intersection itself is computed via ``min``/``max`` and is
direction-agnostic.

Input envelope shapes (minimal, explicit)::

    {"event_id": str, "kind": "ZONE_REGISTERED",
     "payload": {"zone_id": str, "direction": "LONG" | "SHORT",
                 "z_near_ticks": int, "z_far_ticks": int, "knowledge_time_us": int}}

    {"event_id": str, "kind": "DEPARTURE_CANDIDATE",
     "payload": {"zone_id": str, "directional_distance_from_near_edge_ticks": int,
                 "depart_event_count": int, "elapsed_depart_time_ms": int,
                 "atr14_ticks": int | None}}

    {"event_id": str, "kind": "CONTACT_OBSERVATION",
     "payload": {"zone_id": str, "contact_source": str,
                 "observed_low_ticks": int, "observed_high_ticks": int, "event_time_us": int}}

    {"event_id": str, "kind": "ZONE_EXPIRED", "payload": {"zone_id": str}}
    {"event_id": str, "kind": "ZONE_INVALIDATED", "payload": {"zone_id": str}}

A ``zone_id`` unknown to any non-``ZONE_REGISTERED`` envelope is silently ignored throughout (the
F13 "observation on unexcursed level ignored" precedent) — there is nothing to act on and nothing
to abstain about.

Mirror law: ``C -> -C``, up <-> down, LONG <-> SHORT, near <-> far — a zone's every tick bound and
every observed price is negated and the direction flipped; the resulting reaction-state sequence
is byte-identical, proven by test via full price reflection.
"""

from __future__ import annotations

from .. import canonical
from ..transition import Envelope, Params, Quality, State, TransitionResult, require
from . import common
from .common import LONG, SHORT, StructureLawError, abstention  # noqa: F401  (re-export parity)

FORMULA_F14 = "F14"

# The F14 formula's own semantic version (rc3 formula F14). Bound into ``source_reaction_id`` so a
# future generation of the reaction formula never collides identities with this one.
SEMANTIC_VERSION = "reaction.first_touch.v1"

PARAM_MIN_DEPARTURE_RULE = "min_departure_rule"
PARAM_MIN_DEPART_EVENTS = "min_depart_events"
PARAM_MIN_DEPART_TIME_MS = "min_depart_time_ms"
PARAM_CONTACT_PRICE_SOURCE = "contact_price_source"
PARAM_FIRST_TOUCH_ORDINAL = "first_touch_ordinal"

# PAR-168's only lawful declared value — a plain enum string, not a rational-rule shape, so it
# lives here rather than in common.py's rational-rule table.
DECLARED_CONTACT_PRICE_SOURCE = "finalized_bar_closed_range_[low,high]"

# PAR-166/PAR-167 exact declared values. Even though both are still PROPOSED_RC2_MUST_RATIFY (like
# PAR-050 and PAR-168), the module admits ONLY the exact declared byte value, mirroring the
# exact-declared-value discipline it already applies to PAR-050/168/062 — never a >=1/>=0 range.
DECLARED_MIN_DEPART_EVENTS = 1  # PAR-166, declared_value "1"
DECLARED_MIN_DEPART_TIME_MS = 60_000  # PAR-167, declared_value "60000"

REACTION_STATE_CHANGED = "REACTION_STATE_CHANGED"
REACTION_CONFIRMED = "REACTION_CONFIRMED"

ELIGIBLE = "ELIGIBLE"
DEPARTED = "DEPARTED"
FIRST_TOUCH_CONSUMED = "FIRST_TOUCH_CONSUMED"
EXPIRED = "EXPIRED"
INVALIDATED = "INVALIDATED"

_TERMINAL = (FIRST_TOUCH_CONSUMED, EXPIRED, INVALIDATED)


def _event_identity(envelope: Envelope) -> str:
    event_id = envelope.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        raise StructureLawError("F14 envelope event_id must be a non-empty string")
    return event_id


def _nonempty_str(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise StructureLawError(f"F14 {name} must be a non-empty string")
    return value


def _zone_id(payload: dict) -> str:
    return _nonempty_str(payload.get("zone_id"), "zone_id")


def _state_changed_event(zone_id: str, from_state: str, to_state: str, envelope: Envelope) -> dict:
    return {
        "event_kind": REACTION_STATE_CHANGED, "formula": FORMULA_F14, "zone_id": zone_id,
        "from_state": from_state, "to_state": to_state,
        "trigger_event_id": _event_identity(envelope),
    }


class DepartureAndFirstTouch:
    """F14 — departure -> first retest/touch (:class:`triad_origin.transition.DeterministicMachine`)."""

    def initial_state(self) -> State:
        return {"zones": {}}

    def transition(
        self, state: State, envelope: Envelope, params: Params, quality: Quality
    ) -> TransitionResult:
        min_departure_rule = require(params, PARAM_MIN_DEPARTURE_RULE)
        min_depart_events = common.require_int(
            require(params, PARAM_MIN_DEPART_EVENTS), PARAM_MIN_DEPART_EVENTS)
        min_depart_time_ms = common.require_int(
            require(params, PARAM_MIN_DEPART_TIME_MS), PARAM_MIN_DEPART_TIME_MS)
        contact_price_source = require(params, PARAM_CONTACT_PRICE_SOURCE)
        first_touch_ordinal = common.require_int(
            require(params, PARAM_FIRST_TOUCH_ORDINAL), PARAM_FIRST_TOUCH_ORDINAL)

        if min_departure_rule != common.DECLARED_MIN_DEPARTURE:
            raise StructureLawError(
                f"undeclared min_departure rule: {min_departure_rule!r} (PAR-050)")
        if min_depart_events != DECLARED_MIN_DEPART_EVENTS:
            raise StructureLawError(
                "PAR-166 MIN_DEPART_EVENTS is declared at exactly "
                f"{DECLARED_MIN_DEPART_EVENTS}, got {min_depart_events!r}")
        if min_depart_time_ms != DECLARED_MIN_DEPART_TIME_MS:
            raise StructureLawError(
                "PAR-167 MIN_DEPART_TIME is declared at exactly "
                f"{DECLARED_MIN_DEPART_TIME_MS} ms, got {min_depart_time_ms!r}")
        if contact_price_source != DECLARED_CONTACT_PRICE_SOURCE:
            raise StructureLawError(
                f"undeclared contact_price_source: {contact_price_source!r} (PAR-168)")
        if first_touch_ordinal != 1:
            raise StructureLawError(
                "PAR-062 FIRST_TOUCH_ORDINAL is ratified at exactly 1, got "
                f"{first_touch_ordinal!r}")

        kind = envelope.get("kind")
        payload = envelope.get("payload", {})
        if not isinstance(payload, dict):
            raise StructureLawError("F14 envelope payload must be an object")
        zones = dict(state["zones"])

        if kind == "ZONE_REGISTERED":
            zone_id = _zone_id(payload)
            if zone_id in zones:
                return TransitionResult(state)  # already registered; ignore re-registration
            direction = common.require_direction(payload.get("direction"))
            z_near = common.require_int(payload.get("z_near_ticks"), "z_near_ticks")
            z_far = common.require_int(payload.get("z_far_ticks"), "z_far_ticks")
            knowledge_time_us = common.require_int(
                payload.get("knowledge_time_us"), "knowledge_time_us")
            zones[zone_id] = {
                "direction": direction, "z_near_ticks": z_near, "z_far_ticks": z_far,
                "knowledge_time_us": knowledge_time_us, "reaction_state": ELIGIBLE,
            }
            return TransitionResult({"zones": zones})

        if kind == "DEPARTURE_CANDIDATE":
            zone_id = _zone_id(payload)
            row = zones.get(zone_id)
            if row is None or row["reaction_state"] != ELIGIBLE:
                return TransitionResult(state)  # unregistered / already departed / terminal
            atr = payload.get("atr14_ticks")
            if atr is None:
                event = abstention(
                    "F14_NO_ATR", formula=FORMULA_F14,
                    detail="no causal ATR at departure-candidate time; no departure recorded",
                    refs={"zone_id": zone_id})
                return TransitionResult(state, (event,))
            dep_ticks = common.evaluate_declared_rational(min_departure_rule, atr)
            distance = common.require_int(
                payload.get("directional_distance_from_near_edge_ticks"),
                "directional_distance_from_near_edge_ticks")
            depart_event_count = common.require_int(
                payload.get("depart_event_count"), "depart_event_count")
            elapsed_depart_time_ms = common.require_int(
                payload.get("elapsed_depart_time_ms"), "elapsed_depart_time_ms")
            if not (
                distance >= dep_ticks
                and depart_event_count >= min_depart_events
                and elapsed_depart_time_ms >= min_depart_time_ms
            ):
                return TransitionResult(state)  # one or more conjuncts unmet; still ELIGIBLE
            # The departure event is F14 identity material — stamp it on the row so the later
            # first-touch can fold it into source_reaction_id (RC3 F14 identity_material).
            zones[zone_id] = dict(
                row, reaction_state=DEPARTED, departure_event_id=_event_identity(envelope))
            event = _state_changed_event(zone_id, ELIGIBLE, DEPARTED, envelope)
            return TransitionResult({"zones": zones}, (event,))

        if kind == "CONTACT_OBSERVATION":
            contact_source = payload.get("contact_source")
            if contact_source != DECLARED_CONTACT_PRICE_SOURCE:
                raise StructureLawError(
                    f"contact_source must be the declared PAR-168 source, got {contact_source!r}")
            zone_id = _zone_id(payload)
            row = zones.get(zone_id)
            if row is None or row["reaction_state"] != DEPARTED:
                return TransitionResult(state)  # not yet departed, or already terminal: ignored
            observed_low = common.require_int(
                payload.get("observed_low_ticks"), "observed_low_ticks")
            observed_high = common.require_int(
                payload.get("observed_high_ticks"), "observed_high_ticks")
            if observed_low > observed_high:
                raise StructureLawError("observed_low_ticks exceeds observed_high_ticks")
            event_time_us = common.require_int(payload.get("event_time_us"), "event_time_us")
            zone_lo = min(row["z_near_ticks"], row["z_far_ticks"])
            zone_hi = max(row["z_near_ticks"], row["z_far_ticks"])
            if not (observed_low <= zone_hi and zone_lo <= observed_high):
                return TransitionResult(state)  # no intersection; still DEPARTED, waiting
            contact_event_id = _event_identity(envelope)
            # The four declared identity-material members: structure ID (zone_id), departure event,
            # first contact event, and params (a digest of the five declared F14 parameters, so a
            # different parameter generation never collides with this one).
            params_digest = canonical.sha256_hex(canonical.canonical_json({
                "min_departure_rule": min_departure_rule,
                "min_depart_events": min_depart_events,
                "min_depart_time_ms": min_depart_time_ms,
                "contact_price_source": contact_price_source,
                "first_touch_ordinal": first_touch_ordinal,
            }))
            source_reaction_id = canonical.sha256_hex(canonical.canonical_json({
                "formula": FORMULA_F14, "semantic_version": SEMANTIC_VERSION,
                "structure_id": zone_id, "departure_event_id": row["departure_event_id"],
                "contact_event_id": contact_event_id, "event_time_us": event_time_us,
                "observed_low_ticks": observed_low, "observed_high_ticks": observed_high,
                "params_digest": params_digest,
            }))
            zones[zone_id] = dict(row, reaction_state=FIRST_TOUCH_CONSUMED)
            event = {
                "event_kind": REACTION_CONFIRMED, "formula": FORMULA_F14, "zone_id": zone_id,
                "from_state": DEPARTED, "to_state": FIRST_TOUCH_CONSUMED,
                "direction": row["direction"], "contact_event_id": contact_event_id,
                "observed_low_ticks": observed_low, "observed_high_ticks": observed_high,
                "event_time_us": event_time_us, "source_reaction_id": source_reaction_id,
            }
            return TransitionResult({"zones": zones}, (event,))

        if kind in ("ZONE_EXPIRED", "ZONE_INVALIDATED"):
            zone_id = _zone_id(payload)
            row = zones.get(zone_id)
            if row is None or row["reaction_state"] in _TERMINAL:
                return TransitionResult(state)  # unregistered or already terminal: ignored
            from_state = row["reaction_state"]
            to_state = EXPIRED if kind == "ZONE_EXPIRED" else INVALIDATED
            zones[zone_id] = dict(row, reaction_state=to_state)
            event = _state_changed_event(zone_id, from_state, to_state, envelope)
            return TransitionResult({"zones": zones}, (event,))

        raise StructureLawError(f"unknown F14 envelope kind: {kind!r}")
