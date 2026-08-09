"""B06 — the ``edge_candidate.v2`` publisher: append-only lifecycle + the mandatory atomic SHADOW
fork.

**No candidate path without a durable SHADOW write** (the B06 acceptance-evidence law). This
module composes the outputs of F14 (:mod:`triad_origin.structures.reaction`, ``source_reaction_id``),
F18 (:mod:`triad_origin.structures.candidate_geometry`, the frozen geometry), F19
(:mod:`triad_origin.structures.clustering`, ``opportunity_cluster_id``), the semantic capsule
registry (:mod:`triad_origin.structures.capsules`), and the trial preregistration gate
(:mod:`triad_origin.structures.trial_registry`) into one atomic :class:`CandidatePublisher`
transition: EVERY ``PUBLISH_CANDIDATE`` envelope, well-formed or not, produces EXACTLY ONE of two
outcomes in the SAME transition call — a frozen ``edge_candidate.v2`` row plus its mandatory
``shadow_trade.v1`` ``ACCEPTED_NOT_EXECUTED`` fork (published path), or a
``shadow_rejection_audit.v1`` row and NO published candidate at all (untradeable path). There is
no third path; a candidate can never exist without its shadow trace, because the fork is not a
follow-up call this module might skip — it is the SAME Python call graph that decides whether the
candidate publishes at all.

**Composition, not re-derivation.** This module never re-implements SHADOW's own tradeability law
or its dedup/freeze/collision discipline — it constructs the exact envelope
:mod:`triad_origin.control.shadow_ledger`'s own ``ShadowLedger`` machine already knows how to
handle and DELEGATES to it (``ShadowLedger().transition(state["shadow"], ...)``), nesting that
machine's own state as a slice of :class:`CandidatePublisher`'s state. This is composition by
delegation, not duplication: every SHADOW law (freeze-after-write, at-least-once dedup, honest
``NO_FILL``) holds here with byte-identical semantics to the standalone module, because it IS that
module's own code running.

**Why every ORIGIN-published candidate forks ``ACCEPTED_NOT_EXECUTED``, never ``REJECTED``.**
ORIGIN holds no execution authority whatsoever (Doc's own ownership law: E07 decision / E08 risk /
E09 order are ``REFERENCE_ONLY``/``OUT_OF_REPO``). A candidate this repository publishes has, from
ORIGIN's own vantage point, definitionally reached neither PAPER nor a venue — it simply does not
yet know its downstream fate. ``ACCEPTED_NOT_EXECUTED`` is exactly LEV-0080's own case: "so the
opportunity is still measured." An UNTRADEABLE input (failed contract validation, or a
tradeability conjunct this module can itself verify being false) never reaches ``REJECTED`` either
— it is ``SHADOW_UNTRADEABLE``, because ORIGIN has not rejected a trading DECISION here; it has
refused to publish a malformed or incomplete CANDIDATE, which is a different, upstream fact.
``REJECTED`` and the reconciliation-gated ``PROVEN_NO_VENUE_EFFECT`` disposition are for a
DOWNSTREAM system (E07/E08/E09, out of this repo's scope) feeding its own verdict back through
:mod:`triad_origin.control.shadow_ledger` directly — this publisher never fabricates either.

**Honest rejection-stage sentinels.** ``triad.shadow_trade.v1`` requires non-empty
``rejection_stage``/``rejection_reason`` strings even for a disposition that is not, in fact, a
rejection. Rather than invent a plausible-sounding reason, this module stamps the literal,
self-describing sentinel :data:`ORIGIN_PUBLICATION_SENTINEL` — never a fabricated cause.

**Append-only lifecycle.** A published candidate's ``edge_candidate_transition.v1`` chain is
closed and terminal, mirroring :mod:`triad_origin.structures.lifecycle_reducer`:
``PUBLISHED -> WITHDRAWN | EXPIRED | DATA_INVALID`` (each terminal — no further transition, ever).
``state_seq``/``previous_transition_id`` chain exactly like the RC3 schema's own fields; an
illegal transition (unknown candidate, already-terminal, or a transition attempted before
publication) is refused by name, the state left unchanged.

**Trial + capsule identity are verified, not assumed.** ``capsule_id`` must resolve through
:func:`triad_origin.structures.capsules.resolve_capsule`; ``trial_id`` must resolve through
:func:`triad_origin.structures.trial_registry.resolve_trial` against a caller-supplied,
already-current trial-registry state snapshot (``trial_registry_state`` — this publisher does not
own trial state, mirroring the one-module-one-concern law; it reads it purely, never mutates it).
Either raises its own typed ``Unavailable`` error, propagated rather than swallowed — an
unregistered trial or an RC2-ordinal capsule spelling is a wiring defect, not an ordinary refusal.
"""

from __future__ import annotations

from .. import contracts
from ..canonical import canonical_json, sha256_hex
from ..control.shadow_ledger import ShadowLedger
from ..transition import Envelope, Params, Quality, State, TransitionResult
from . import capsules, common, trial_registry

FORMULA_CANDIDATE_PUBLISHER = "CANDIDATE_PUBLISHER"

_KIND_PUBLISH_CANDIDATE = "PUBLISH_CANDIDATE"
_KIND_WITHDRAW_CANDIDATE = "WITHDRAW_CANDIDATE"
_KIND_EXPIRE_CANDIDATE = "EXPIRE_CANDIDATE"
_KIND_DATA_INVALID_CANDIDATE = "DATA_INVALID_CANDIDATE"

CANDIDATE_PUBLISHED = "CANDIDATE_PUBLISHED"
CANDIDATE_PUBLICATION_REFUSED = "CANDIDATE_PUBLICATION_REFUSED"
CANDIDATE_TRANSITIONED = "CANDIDATE_TRANSITIONED"
CANDIDATE_TRANSITION_REFUSED = "CANDIDATE_TRANSITION_REFUSED"

STATE_UNPUBLISHED = "UNPUBLISHED"
STATE_PUBLISHED = "PUBLISHED"
STATE_WITHDRAWN = "WITHDRAWN"
STATE_EXPIRED = "EXPIRED"
STATE_DATA_INVALID = "DATA_INVALID"
_TERMINAL_STATES = (STATE_WITHDRAWN, STATE_EXPIRED, STATE_DATA_INVALID)

_KIND_TO_TO_STATE = {
    _KIND_WITHDRAW_CANDIDATE: STATE_WITHDRAWN,
    _KIND_EXPIRE_CANDIDATE: STATE_EXPIRED,
    _KIND_DATA_INVALID_CANDIDATE: STATE_DATA_INVALID,
}

ORIGIN_PUBLICATION_SENTINEL_STAGE = "N/A_ORIGIN_PUBLICATION"
ORIGIN_PUBLICATION_SENTINEL_REASON = (
    "not_a_rejection_this_is_the_mandatory_shadow_fork_of_an_origin_publication")

# The twelve TRADEABILITY_REQUIREMENTS this module can itself re-derive from the already-validated
# edge_candidate.v2 payload (RC4 shadow_law.tradeability_requirements, same order as
# shadow_ledger.TRADEABILITY_REQUIREMENTS).
_REQUIRED_STRING_FIELDS_FOR_FLAGS = {
    "resolved_instrument": "canonical_instrument_id",
    "side": "direction",
    "entry_policy": "entry_policy",
    "invalidation": "natural_invalidation_ticks",
    "horizon": "horizon",
    "stable_identity": "candidate_id",
}


class CandidatePublisherError(ValueError):
    """A candidate-publisher usage error (fail closed, named)."""


def _require_str(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise CandidatePublisherError(f"{name} must be a non-empty string")
    return value


def _require_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CandidatePublisherError(f"{name} must be an exact int")
    return value


def _derive_tradeability_flags(payload: dict, edge_candidate_valid: bool) -> dict[str, bool]:
    """Re-derive the 12 tradeability conjuncts from the payload's own content — never a blind True.

    ``schema_valid``/``semantically_valid`` reflect whether ``triad.edge_candidate.v2`` validation
    (schema + the forbidden-money-field guard) already passed. Every other conjunct is checked
    against the ACTUAL field the caller supplied, so a structurally-valid-but-hollow payload (e.g.
    an empty ``targets`` array) still fails the flag it should fail, never a rubber stamp.
    """
    flags = {
        "schema_valid": edge_candidate_valid,
        "semantically_valid": edge_candidate_valid,
    }
    for flag_name, field_name in _REQUIRED_STRING_FIELDS_FOR_FLAGS.items():
        value = payload.get(field_name)
        flags[flag_name] = bool(value) if not isinstance(value, bool) else False
    flags["target_or_terminal_rule"] = bool(payload.get("targets"))
    finite_fields = ("entry_reference_ticks", "natural_invalidation_ticks", "rr_numerator",
                     "rr_denominator")
    flags["finite_numbers"] = all(
        isinstance(payload.get(f), str) and payload.get(f).lstrip("-").isdigit()
        for f in finite_fields)
    not_before_us = payload.get("not_before_us")
    ttl_us = payload.get("ttl_us")
    flags["monotonic_clocks"] = (
        isinstance(not_before_us, int) and not isinstance(not_before_us, bool)
        and isinstance(ttl_us, int) and not isinstance(ttl_us, bool) and ttl_us > 0)
    market_watermark = payload.get("_market_watermark")
    flags["causal_market_watermark"] = (
        isinstance(market_watermark, dict) and "watermark_us" in market_watermark
        and isinstance(market_watermark["watermark_us"], int)
        and not isinstance(market_watermark["watermark_us"], bool))
    return flags


def _shadow_candidate_envelope(
    edge_candidate_payload: dict, event_id: str, *, event_time_us: int,
    market_watermark: dict, evaluation_notional_quote: str, simulator_version: str,
    resolver_version: str, cost_model_version: str, tradeability_flags: dict[str, bool],
) -> Envelope:
    payload = dict(tradeability_flags)
    payload.update({
        "candidate_id": edge_candidate_payload["candidate_id"],
        "hypothesis_id": edge_candidate_payload["hypothesis_id"],
        "origin_disposition": "ACCEPTED_NOT_EXECUTED",
        "rejection_stage": ORIGIN_PUBLICATION_SENTINEL_STAGE,
        "rejection_reason": ORIGIN_PUBLICATION_SENTINEL_REASON,
        "market_watermark": market_watermark,
        "proposed_geometry": {
            "direction": edge_candidate_payload.get("direction"),
            "entry_reference_ticks": edge_candidate_payload.get("entry_reference_ticks"),
            "natural_invalidation_ticks": edge_candidate_payload.get("natural_invalidation_ticks"),
            "targets": edge_candidate_payload.get("targets"),
        },
        "evaluation_notional_quote": evaluation_notional_quote,
        "simulator_version": simulator_version,
        "resolver_version": resolver_version,
        "cost_model_version": cost_model_version,
        "event_time_us": event_time_us,
    })
    return {"event_id": event_id, "kind": "SHADOW_CANDIDATE", "payload": payload}


class CandidatePublisher:
    """The ``edge_candidate.v2`` append-only publisher with the mandatory atomic SHADOW fork."""

    def initial_state(self) -> State:
        return {"candidates": {}, "transitions": {}, "shadow": ShadowLedger().initial_state()}

    def transition(
        self, state: State, envelope: Envelope, params: Params, quality: Quality
    ) -> TransitionResult:
        kind = envelope.get("kind")
        payload = envelope.get("payload", {})
        if kind == _KIND_PUBLISH_CANDIDATE:
            return self._publish(state, envelope.get("event_id"), payload)
        if kind in _KIND_TO_TO_STATE:
            return self._transition_candidate(state, envelope.get("event_id"), payload,
                                               _KIND_TO_TO_STATE[kind])
        raise CandidatePublisherError(f"unknown candidate-publisher envelope kind: {kind!r}")

    # -- PUBLISH_CANDIDATE ------------------------------------------------------------------------

    def _publish(self, state: State, event_id: str, payload: dict) -> TransitionResult:
        edge_candidate_payload = payload.get("edge_candidate", {})
        trial_registry_state = payload.get("trial_registry_state", {})
        event_time_us = _require_int(payload.get("event_time_us"), "event_time_us")
        market_watermark = payload.get("market_watermark")
        if not isinstance(market_watermark, dict) or "watermark_us" not in market_watermark:
            raise CandidatePublisherError("market_watermark must carry a watermark_us key")
        evaluation_notional_quote = _require_str(
            payload.get("evaluation_notional_quote"), "evaluation_notional_quote")
        simulator_version = _require_str(payload.get("simulator_version"), "simulator_version")
        resolver_version = _require_str(payload.get("resolver_version"), "resolver_version")
        cost_model_version = _require_str(payload.get("cost_model_version"), "cost_model_version")

        candidate_id = _require_str(edge_candidate_payload.get("candidate_id"), "candidate_id")
        if candidate_id in state["candidates"]:
            existing = state["candidates"][candidate_id]
            if existing == edge_candidate_payload:
                return TransitionResult(state)  # identical redelivery: idempotent no-op
            raise CandidatePublisherError(
                f"candidate_id {candidate_id!r} already published with a disagreeing payload — "
                "a published candidate's geometry is immutable")

        # Identity verification: an unresolvable capsule/trial is a wiring defect, propagated.
        capsule_id = edge_candidate_payload.get("capsule_id")
        capsules.resolve_capsule(capsule_id)
        trial_id = edge_candidate_payload.get("trial_id")
        trial_registry.resolve_trial(trial_registry_state, trial_id)

        try:
            contracts.validate_payload("triad.edge_candidate.v2", edge_candidate_payload)
            edge_candidate_valid = True
        except contracts.ContractError:
            edge_candidate_valid = False

        flags_payload = dict(edge_candidate_payload)
        flags_payload["_market_watermark"] = market_watermark
        tradeability_flags = _derive_tradeability_flags(flags_payload, edge_candidate_valid)

        shadow_envelope = _shadow_candidate_envelope(
            edge_candidate_payload, f"shadow_{event_id}", event_time_us=event_time_us,
            market_watermark=market_watermark, evaluation_notional_quote=evaluation_notional_quote,
            simulator_version=simulator_version, resolver_version=resolver_version,
            cost_model_version=cost_model_version, tradeability_flags=tradeability_flags)
        shadow_result = ShadowLedger().transition(state["shadow"], shadow_envelope, {}, {})

        if not all(tradeability_flags.values()):
            # Untradeable: the mandatory fork wrote a shadow_rejection_audit row; no candidate
            # publishes. No candidate path without a durable SHADOW write — this IS that write.
            event = {
                "event_kind": CANDIDATE_PUBLICATION_REFUSED, "formula": FORMULA_CANDIDATE_PUBLISHER,
                "candidate_id": candidate_id, "reason_code": "SHADOW_UNTRADEABLE",
                "failed_conjuncts": sorted(k for k, v in tradeability_flags.items() if not v),
            }
            new_state = {"candidates": state["candidates"], "transitions": state["transitions"],
                        "shadow": shadow_result.state}
            return TransitionResult(new_state, (event, *shadow_result.events))

        candidates = dict(state["candidates"])
        candidates[candidate_id] = dict(edge_candidate_payload)
        transition_id = sha256_hex(canonical_json(
            {"candidate_id": candidate_id, "state_seq": 0, "to_state": STATE_PUBLISHED}))
        transitions = dict(state["transitions"])
        transitions[transition_id] = {
            "transition_id": transition_id, "candidate_id": candidate_id, "state_seq": "0",
            "previous_transition_id": "", "from_state": STATE_UNPUBLISHED,
            "to_state": STATE_PUBLISHED, "reason": "PUBLISHED",
            "source_transition_id": transition_id, "event_time_us": event_time_us,
            "knowledge_at_us": event_time_us,
        }
        new_state = {"candidates": candidates, "transitions": transitions,
                    "shadow": shadow_result.state}
        publish_event = {
            "event_kind": CANDIDATE_PUBLISHED, "formula": FORMULA_CANDIDATE_PUBLISHER,
            "candidate_id": candidate_id, "transition_id": transition_id,
        }
        return TransitionResult(new_state, (publish_event, *shadow_result.events))

    # -- WITHDRAW / EXPIRE / DATA_INVALID ----------------------------------------------------------

    def _transition_candidate(
        self, state: State, event_id: str, payload: dict, to_state: str
    ) -> TransitionResult:
        candidate_id = _require_str(payload.get("candidate_id"), "candidate_id")
        reason = _require_str(payload.get("reason"), "reason")
        event_time_us = _require_int(payload.get("event_time_us"), "event_time_us")

        latest = self._latest_transition(state, candidate_id)
        if latest is None:
            event = common.abstention(
                "CANDIDATE_TRANSITION_UNKNOWN_CANDIDATE", formula=FORMULA_CANDIDATE_PUBLISHER,
                detail=f"candidate_id {candidate_id!r} has never been published",
                refs={"candidate_id": candidate_id})
            return TransitionResult(state, (event,))
        if latest["to_state"] in _TERMINAL_STATES:
            event = common.abstention(
                "CANDIDATE_TRANSITION_ALREADY_TERMINAL", formula=FORMULA_CANDIDATE_PUBLISHER,
                detail=f"candidate {candidate_id!r} is already {latest['to_state']} (terminal)",
                refs={"candidate_id": candidate_id, "from_state": latest["to_state"]})
            return TransitionResult(state, (event,))

        state_seq = int(latest["state_seq"]) + 1
        transition_id = sha256_hex(canonical_json(
            {"candidate_id": candidate_id, "state_seq": state_seq, "to_state": to_state}))
        transitions = dict(state["transitions"])
        transitions[transition_id] = {
            "transition_id": transition_id, "candidate_id": candidate_id,
            "state_seq": str(state_seq), "previous_transition_id": latest["transition_id"],
            "from_state": latest["to_state"], "to_state": to_state, "reason": reason,
            "source_transition_id": transition_id, "event_time_us": event_time_us,
            "knowledge_at_us": event_time_us,
        }
        new_state = {"candidates": state["candidates"], "transitions": transitions,
                    "shadow": state["shadow"]}
        event = {
            "event_kind": CANDIDATE_TRANSITIONED, "formula": FORMULA_CANDIDATE_PUBLISHER,
            "candidate_id": candidate_id, "from_state": latest["to_state"], "to_state": to_state,
            "transition_id": transition_id,
        }
        return TransitionResult(new_state, (event,))

    @staticmethod
    def _latest_transition(state: State, candidate_id: str) -> dict | None:
        rows = [row for row in state["transitions"].values() if row["candidate_id"] == candidate_id]
        if not rows:
            return None
        return max(rows, key=lambda row: int(row["state_seq"]))
