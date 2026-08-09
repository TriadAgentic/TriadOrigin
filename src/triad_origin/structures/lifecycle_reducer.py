"""W05 — the generic append-only structure-lifecycle reducer.

A pure :class:`triad_origin.transition.DeterministicMachine`. This is the ONE closed-graph ledger
of "what state is structure ``X`` in right now, and was every transition it went through legal" —
it is deliberately generic over ANY structure atom's confirmation events (F03/F04/F09/F10/F12/etc),
consuming a minimal, opaque request envelope rather than importing any other structures module
(zero cross-module coupling, matching :mod:`order_block_registry`'s posture). A formula whose OWN
lifecycle needs a transition outside this graph (F10's bar-count TTL fill/expiry, F12's
BOS-horizon/break lifecycle) implements that internally in its own machine, per the RC3 formula
row's own rules — this reducer is not a re-implementation of any formula's specific rules; it is
the shared safety net that catches an illegal transition attempt on ANY structure and refuses it
loudly, never silently.

Input envelope shape (minimal and explicit; note the deliberate ABSENCE of any geometry field past
formation — see "frozen original geometry" below)::

    {"event_id": str, "kind": "TRANSITION_REQUEST",
     "payload": {"structure_id": str, "requested_transition": str, "trigger_event_id": str}}

**The closed legal-transition graph** (mirrors F10's bar-count fill lifecycle and F12's
pending/confirmed/broken lifecycle as two INSTANCES of one generic shape — not a re-derivation of
either)::

    (unseen)          -> {FORMED}
    FORMED            -> {CONFIRMED, EXPIRED, WITHDRAWN}
    CONFIRMED         -> {PARTIALLY_FILLED, FULLY_FILLED, BROKEN, WITHDRAWN}
    PARTIALLY_FILLED  -> {FULLY_FILLED, EXPIRED, WITHDRAWN}
    FULLY_FILLED, EXPIRED, WITHDRAWN, BROKEN -> {}  (terminal — no further transitions, ever)

``WITHDRAWN`` is a first-class transition reachable from every non-terminal state (an
operator/upstream withdrawal is always legal, modeled explicitly rather than left implicit).
**A structure with no ``FORMED`` yet cannot receive any other transition** — the reducer never
invents an initial state for an unseen ``structure_id``; the FIRST request for any given id must
itself be ``FORMED`` or it is rejected exactly like any other illegal transition (unknown-state ->
non-``FORMED`` is simply absent from the graph's successor set for the unseen pseudo-state).

**The safety law (money-adjacent): an illegal transition NEVER silently applies.** A request whose
target is not in the current state's legal-successor set — including any request FROM an already-
terminal state, and including a non-``FORMED`` first request for an unseen id — is REJECTED: the
reducer emits a named rejection event (``common.abstention``, reason_code
``LIFECYCLE_ILLEGAL_TRANSITION``) and the structure's recorded state is left EXACTLY as it was; no
partial mutation, ever.

**Idempotency (a documented choice, not an omission).** A transition request whose target already
equals the structure's CURRENT state is a no-op: no state mutation, no event, and the machine
returns the untouched prior ``state`` object unchanged (mirroring F09's identical-re-registration
no-op). This holds regardless of ``trigger_event_id`` — a REPEATED identical request (same
structure_id, same requested_transition, same trigger_event_id) is idempotent by this same rule,
and so is a DIFFERENT trigger_event_id re-requesting the transition the structure has already made:
"already in that state" is the one idempotency test, deliberately not keyed on which trigger asked
for it. This is simpler than tracking a request/trigger history and gives the same observable
guarantee: replaying (or re-deriving) a transition the structure already completed never produces a
second event and never re-applies anything.

**Frozen original geometry — enforced structurally, not by a runtime check.** Once a structure
reaches ``CONFIRMED`` its identity/geometry fields (whatever the OWNING formula captured at
``FORMED``, preserved verbatim by that formula's own machine) can never be altered by a later
transition here, because the ``TRANSITION_REQUEST`` envelope shape above carries no geometry field
at all, past formation or otherwise — there is structurally nothing for a later transition to
overwrite. This reducer never even sees a structure's geometry; it only ever sees
``(structure_id, requested_transition, trigger_event_id)``.

Mirror law: none — this reducer holds no price/direction fields, so directional mirror symmetry
does not apply to it (it is proven instead by prefix/restart/duplicate invariance, per Doc 02
§02.16, and by graph-edge exhaustiveness).
"""

from __future__ import annotations

from ..transition import Envelope, Params, Quality, State, TransitionResult
from . import common

FORMULA_W05 = "W05"

_KIND_TRANSITION_REQUEST = "TRANSITION_REQUEST"

STATE_FORMED = "FORMED"
STATE_CONFIRMED = "CONFIRMED"
STATE_PARTIALLY_FILLED = "PARTIALLY_FILLED"
STATE_FULLY_FILLED = "FULLY_FILLED"
STATE_EXPIRED = "EXPIRED"
STATE_WITHDRAWN = "WITHDRAWN"
STATE_BROKEN = "BROKEN"

_ALL_STATES = (
    STATE_FORMED, STATE_CONFIRMED, STATE_PARTIALLY_FILLED, STATE_FULLY_FILLED,
    STATE_EXPIRED, STATE_WITHDRAWN, STATE_BROKEN,
)

_LEGAL_SUCCESSORS = {
    STATE_FORMED: (STATE_CONFIRMED, STATE_EXPIRED, STATE_WITHDRAWN),
    STATE_CONFIRMED: (STATE_PARTIALLY_FILLED, STATE_FULLY_FILLED, STATE_BROKEN, STATE_WITHDRAWN),
    STATE_PARTIALLY_FILLED: (STATE_FULLY_FILLED, STATE_EXPIRED, STATE_WITHDRAWN),
    STATE_FULLY_FILLED: (),
    STATE_EXPIRED: (),
    STATE_WITHDRAWN: (),
    STATE_BROKEN: (),
}
_UNSEEN = "UNSEEN"
_UNSEEN_SUCCESSORS = (STATE_FORMED,)

LIFECYCLE_TRANSITIONED = "LIFECYCLE_TRANSITIONED"
LIFECYCLE_ILLEGAL_TRANSITION = "LIFECYCLE_ILLEGAL_TRANSITION"


def _event_identity(envelope: Envelope) -> str:
    event_id = envelope.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        raise common.StructureLawError("envelope event_id must be a non-empty string")
    return event_id


def _nonempty_str(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise common.StructureLawError(f"W05 {name} must be a non-empty string")
    return value


class LifecycleReducer:
    """W05 — the generic, closed-graph, append-only structure-lifecycle machine.

    See the module docstring for the full graph, the illegal-transition safety law, the
    idempotency rule, and the frozen-geometry-by-omission law.
    """

    def initial_state(self) -> State:
        return {"last_event_id": None, "structures": {}}

    def transition(
        self, state: State, envelope: Envelope, params: Params, quality: Quality
    ) -> TransitionResult:
        event_id = _event_identity(envelope)
        if event_id == state.get("last_event_id"):
            return TransitionResult(state=state)
        if envelope.get("kind") != _KIND_TRANSITION_REQUEST:
            raise common.StructureLawError(
                f"W05 consumes {_KIND_TRANSITION_REQUEST!r} envelopes only, "
                f"got {envelope.get('kind')!r}")
        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            raise common.StructureLawError("W05 envelope payload must be an object")

        structure_id = _nonempty_str(payload.get("structure_id"), "structure_id")
        trigger_event_id = _nonempty_str(payload.get("trigger_event_id"), "trigger_event_id")
        requested = payload.get("requested_transition")
        if requested not in _ALL_STATES:
            raise common.StructureLawError(
                f"W05 requested_transition must be one of {_ALL_STATES}, got {requested!r}")

        record = state["structures"].get(structure_id)
        current_state = record["state"] if record is not None else None

        if current_state == requested:
            # Idempotent: the structure is already in the requested state. No mutation, no event,
            # regardless of trigger_event_id (see the module docstring's idempotency law).
            return TransitionResult(state=state)

        legal = _LEGAL_SUCCESSORS[current_state] if current_state is not None else _UNSEEN_SUCCESSORS
        if requested not in legal:
            return TransitionResult(
                state={"last_event_id": event_id, "structures": state["structures"]},
                events=(common.abstention(
                    LIFECYCLE_ILLEGAL_TRANSITION, formula=FORMULA_W05,
                    detail=f"{current_state or _UNSEEN} -> {requested} is not a legal lifecycle "
                           "transition; the structure's recorded state is unchanged",
                    refs={"event_id": event_id, "structure_id": structure_id,
                          "from_state": current_state or _UNSEEN, "requested_transition": requested,
                          "trigger_event_id": trigger_event_id}),))

        structures = {key: dict(value) for key, value in state["structures"].items()}
        structures[structure_id] = {"state": requested}
        event = {
            "event_kind": LIFECYCLE_TRANSITIONED, "formula": FORMULA_W05,
            "structure_id": structure_id, "from_state": current_state or _UNSEEN,
            "to_state": requested, "trigger_event_id": trigger_event_id,
        }
        return TransitionResult(
            state={"last_event_id": event_id, "structures": structures}, events=(event,))
