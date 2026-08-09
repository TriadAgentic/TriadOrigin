"""SHADOW writer/resolver health + the LEV-0085/0086/0066 containment law (B05 substrate).

This is the pure :class:`triad_origin.transition.DeterministicMachine` that turns caller-supplied
"as-of" ages and latencies into either an accepted no-op, or a named containment/refusal event —
never by reading a clock (staleness is always ``timings.is_stale(age_ms, bound_name)`` over an
age the CALLER computed and handed in). It implements the RC4 ``shadow_law`` health rows, cited at
their exact instruction text:

* **LEV-0085** — "Emit SHADOW writer heartbeat every 1,000 ms and force venue_activation and
  paper_activation OFF after 5,000 ms stale." A ``WRITER_HEARTBEAT`` whose ``age_ms`` exceeds
  :func:`triad_origin.timings.timing_ms` ``("shadow_health_max_age_ms")`` (5,000 ms) emits
  ``HEALTH_FORCED_OFF`` carrying :func:`triad_origin.control.lever_law.containment_action` for the
  ``SHADOW_HEALTH_STALE`` code — which narrows ``venue_activation``/``paper_activation`` toward
  ``OFF`` and leaves ``shadow_activation`` at ``LIVE`` (SHADOW recovery continues; only the
  EXECUTION planes narrow — the writer being unhealthy is never a reason to stop capturing).
* **LEV-0086** — "Keep SHADOW resolver processable backlog under 60,000 ms." A ``RESOLVER_BACKLOG``
  whose ``age_ms`` exceeds ``"shadow_resolver_backlog_max_age_ms"`` (60,000 ms) emits the identical
  ``HEALTH_FORCED_OFF`` containment shape.
* **LEV-0066** — "Persist each rejected candidate within 100 ms before acknowledging the rejection
  decision." A ``PERSISTENCE_LATENCY`` whose ``latency_ms`` exceeds
  ``"shadow_rejection_persist_deadline_ms"`` (100 ms) emits
  :func:`triad_origin.control.lever_law.refuse` ``("SHADOW_REJECTION_NOT_PERSISTED")`` — the
  ``SHADOW_REJECTION_NOT_PERSISTED`` refusal's own ``minimum_action`` is the RC4-declared
  containment for a missed persistence deadline (:mod:`triad_origin.control.lever_law`'s
  ``_QUARANTINE_ACTION``); this module never re-derives that mapping, it only asks the shared
  classifier for it.
* **LEV-0089** — "Alert on any SHADOW or PAPER row carrying a venue fill identity and on any
  cross-population aggregation." ``RECORD_CONTAMINATION`` bumps the durable
  ``contamination_count`` AND emits :func:`triad_origin.control.lever_law.refuse`
  ``("SHADOW_MONEY_CONTAMINATION")`` alongside the plain counter event — a contamination finding is
  never silent, and it is never merely counted without also being refused.
* **LEV-0070** — "Dedupe at-least-once delivery and refuse identity collisions with unequal payload
  hashes." ``RECORD_DEDUPE``/``RECORD_COLLISION`` are the durable tallies :mod:`shadow_ledger`
  drives when it makes exactly those two calls — this module owns the counter, not the dedupe
  decision itself (that decision is made, per row, inside :mod:`triad_origin.control.shadow_ledger`).

Bound names are referenced by their exact declared string directly against
:mod:`triad_origin.timings` (the ONE in-repo source of the 17 RC4 timing bounds) — never restated
as a numeric literal here, and never passed through ``params`` (they are not a per-run
experimental threshold; they are the RC4 addendum's own fixed law).
"""

from __future__ import annotations

from .. import timings
from ..transition import Envelope, Params, Quality, State, TransitionResult
from . import lever_law

FORMULA_SHADOW_HEALTH = "SHADOW_HEALTH"

_KIND_WRITER_HEARTBEAT = "WRITER_HEARTBEAT"
_KIND_RESOLVER_BACKLOG = "RESOLVER_BACKLOG"
_KIND_PERSISTENCE_LATENCY = "PERSISTENCE_LATENCY"
_KIND_RECORD_DEDUPE = "RECORD_DEDUPE"
_KIND_RECORD_COLLISION = "RECORD_COLLISION"
_KIND_RECORD_CONTAMINATION = "RECORD_CONTAMINATION"

HEALTH_FORCED_OFF = "HEALTH_FORCED_OFF"
LEVER_REFUSAL = "LEVER_REFUSAL"
SHADOW_DEDUPE_RECORDED = "SHADOW_DEDUPE_RECORDED"
SHADOW_COLLISION_RECORDED = "SHADOW_COLLISION_RECORDED"
SHADOW_CONTAMINATION_RECORDED = "SHADOW_CONTAMINATION_RECORDED"

_BOUND_WRITER_HEARTBEAT = "shadow_health_max_age_ms"
_BOUND_RESOLVER_BACKLOG = "shadow_resolver_backlog_max_age_ms"
_BOUND_PERSISTENCE_LATENCY = "shadow_rejection_persist_deadline_ms"

_REFUSAL_HEALTH_STALE = "SHADOW_HEALTH_STALE"
_REFUSAL_NOT_PERSISTED = "SHADOW_REJECTION_NOT_PERSISTED"
_REFUSAL_CONTAMINATION = "SHADOW_MONEY_CONTAMINATION"


class ShadowHealthError(ValueError):
    """A malformed envelope. Fail closed, named."""


def _require_dict(value: object, name: str) -> dict:
    if not isinstance(value, dict):
        raise ShadowHealthError(f"{name} must be an object")
    return value


def _require_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ShadowHealthError(f"{name} must be an exact int, got {type(value).__name__}")
    return value


def _forced_off_event(*, source: str, age_ms: int) -> dict:
    resolution = lever_law.refuse(_REFUSAL_HEALTH_STALE)
    return {
        "event_kind": HEALTH_FORCED_OFF,
        "formula": FORMULA_SHADOW_HEALTH,
        "reason_code": resolution.refusal_code,
        "meaning": resolution.meaning,
        "source": source,
        "age_ms": age_ms,
        "payload": lever_law.containment_action(_REFUSAL_HEALTH_STALE, lever_law.BASELINE_MANIFEST),
    }


def _refusal_event(code: str, *, refs: dict | None = None) -> dict:
    resolution = lever_law.refuse(code)
    event = {
        "event_kind": LEVER_REFUSAL,
        "formula": FORMULA_SHADOW_HEALTH,
        "reason_code": resolution.refusal_code,
        "meaning": resolution.meaning,
        "minimum_action": dict(sorted(resolution.minimum_action.items())),
    }
    if refs:
        event["refs"] = dict(sorted(refs.items()))
    return event


class ShadowHealth:
    """SHADOW writer/resolver freshness + persistence-deadline law
    (:class:`triad_origin.transition.DeterministicMachine`)."""

    def initial_state(self) -> State:
        return {
            "last_heartbeat_age_ms": None,
            "backlog_age_ms": None,
            "dedupe_count": 0,
            "collision_count": 0,
            "contamination_count": 0,
        }

    def transition(
        self, state: State, envelope: Envelope, params: Params, quality: Quality
    ) -> TransitionResult:
        kind = envelope.get("kind")
        payload = _require_dict(envelope.get("payload", {}), "payload")

        if kind == _KIND_WRITER_HEARTBEAT:
            age_ms = _require_int(payload.get("age_ms"), "age_ms")
            new_state = dict(state, last_heartbeat_age_ms=age_ms)
            if timings.is_stale(age_ms, _BOUND_WRITER_HEARTBEAT):
                return TransitionResult(
                    new_state, (_forced_off_event(source=_KIND_WRITER_HEARTBEAT, age_ms=age_ms),))
            return TransitionResult(new_state)

        if kind == _KIND_RESOLVER_BACKLOG:
            age_ms = _require_int(payload.get("age_ms"), "age_ms")
            new_state = dict(state, backlog_age_ms=age_ms)
            if timings.is_stale(age_ms, _BOUND_RESOLVER_BACKLOG):
                return TransitionResult(
                    new_state, (_forced_off_event(source=_KIND_RESOLVER_BACKLOG, age_ms=age_ms),))
            return TransitionResult(new_state)

        if kind == _KIND_PERSISTENCE_LATENCY:
            latency_ms = _require_int(payload.get("latency_ms"), "latency_ms")
            if timings.is_stale(latency_ms, _BOUND_PERSISTENCE_LATENCY):
                refs = {"latency_ms": latency_ms}
                shadow_trade_id = payload.get("shadow_trade_id")
                if isinstance(shadow_trade_id, str) and shadow_trade_id:
                    refs["shadow_trade_id"] = shadow_trade_id
                return TransitionResult(state, (_refusal_event(_REFUSAL_NOT_PERSISTED, refs=refs),))
            return TransitionResult(state)

        if kind == _KIND_RECORD_DEDUPE:
            count = state["dedupe_count"] + 1
            new_state = dict(state, dedupe_count=count)
            event = {
                "event_kind": SHADOW_DEDUPE_RECORDED, "formula": FORMULA_SHADOW_HEALTH,
                "dedupe_count": count,
            }
            return TransitionResult(new_state, (event,))

        if kind == _KIND_RECORD_COLLISION:
            count = state["collision_count"] + 1
            new_state = dict(state, collision_count=count)
            event = {
                "event_kind": SHADOW_COLLISION_RECORDED, "formula": FORMULA_SHADOW_HEALTH,
                "collision_count": count,
            }
            return TransitionResult(new_state, (event,))

        if kind == _KIND_RECORD_CONTAMINATION:
            count = state["contamination_count"] + 1
            new_state = dict(state, contamination_count=count)
            counter_event = {
                "event_kind": SHADOW_CONTAMINATION_RECORDED, "formula": FORMULA_SHADOW_HEALTH,
                "contamination_count": count,
            }
            return TransitionResult(
                new_state, (counter_event, _refusal_event(_REFUSAL_CONTAMINATION)))

        raise ShadowHealthError(f"unknown SHADOW health envelope kind: {kind!r}")
