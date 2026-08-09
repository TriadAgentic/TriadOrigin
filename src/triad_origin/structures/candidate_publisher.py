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

**Trial + capsule identity are verified, not assumed — and NEVER a raise.** ``capsule_id`` must
resolve through :func:`triad_origin.structures.capsules.resolve_capsule`; ``trial_id`` must resolve
through :func:`triad_origin.structures.trial_registry.resolve_trial` against a caller-supplied,
already-current trial-registry state snapshot (``trial_registry_state`` — this publisher does not
own trial state, mirroring the one-module-one-concern law; it reads it purely, never mutates it);
and the resolved trial's OWN ``capsule_semantic_id`` must equal the candidate's ``capsule_id`` — a
candidate is never attributed to a preregistered trial of a DIFFERENT capsule, which would corrupt
that trial's own conjunct/ablation results. All three checks live inside :func:`_semantically_valid`
and feed the ``semantically_valid`` tradeability conjunct: an unresolvable capsule/trial or a
capsule/trial mismatch is a semantic FACT about a malformed or misattributed candidate — it takes
the SHADOW-audited untradeable path exactly like every other failed conjunct, never an exception
that could halt partition processing on one poison envelope. Nothing in this module's own
``PUBLISH_CANDIDATE`` handling ever raises on untrusted candidate CONTENT (a missing/wrong-typed
``candidate_id``, ``capsule_id``, ``trial_id``, or any other ``edge_candidate`` field always
resolves to a published row or a shadow audit); a raise here is reserved for a defect in the
publisher's OWN calling envelope — ``event_time_us``, ``market_watermark``, and the four
version/quote strings the publisher's own wiring supplies, never the candidate itself.
"""

from __future__ import annotations

from .. import contracts
from ..canonical import CanonicalError, canonical_json, sha256_hex, str_to_tick
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

CANDIDATE_ALREADY_PUBLISHED_DISAGREEMENT = "CANDIDATE_ALREADY_PUBLISHED_DISAGREEMENT"

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

# The PAR-061 MIN_GEOMETRIC_RR floor (declared_value "2/1"), re-asserted here as the same exact
# cross-multiplication F18 itself uses (candidate_geometry.py) — never a float division.
_MIN_GEOMETRIC_RR_FRACTION = (2, 1)


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


def _parse_tick(value: object) -> int | None:
    """A canonical tick string parsed to ``int``, or ``None`` on anything not canonical."""
    if not isinstance(value, str):
        return None
    try:
        return str_to_tick(value)
    except CanonicalError:
        return None


def _semantically_valid(edge_candidate_payload: dict, trial_registry_state: dict) -> bool:
    """Re-derive semantic validity independently of mere JSON-schema shape.

    ``schema_valid`` only proves the WIRE SHAPE is legal (required fields present, patterns match,
    no forbidden money field). This recomputes the actual geometric/referential invariants a
    schema cannot express, from the SAME frozen wire fields, mirroring F18's own "never trust,
    recompute" discipline (:mod:`triad_origin.structures.candidate_geometry`'s own
    ``ABSTAIN_NONPOSITIVE_REWARD`` re-verification): the capsule/trial identities actually resolve
    AND the trial is bound to the candidate's OWN capsule (a candidate must never be attributed to
    a preregistered trial of a DIFFERENT capsule — that would corrupt the trial's own conjunct/
    ablation results); the directional stop-side invariant (the same law
    ``candidate_geometry.evaluate_candidate_geometry`` enforces at emission time); the PAR-061 2:1
    RR floor by exact cross-multiplication; and that every declared target is a well-formed,
    positive-reward occurrence, never a hollow placeholder. Every check is defensive (no raise) —
    an unresolvable/malformed identity here is a semantic FACT about the candidate, never a crash.
    """
    direction = edge_candidate_payload.get("direction")
    if direction not in common.DIRECTIONS:
        return False

    capsule_id = edge_candidate_payload.get("capsule_id")
    try:
        capsules.resolve_capsule(capsule_id)
    except capsules.CapsuleUnavailableError:
        return False

    trial_id = edge_candidate_payload.get("trial_id")
    try:
        trial = trial_registry.resolve_trial(trial_registry_state, trial_id)
    except trial_registry.TrialUnavailableError:
        return False
    if trial.capsule_semantic_id != capsule_id:
        return False  # a candidate must be bound to a trial of its OWN capsule

    entry = _parse_tick(edge_candidate_payload.get("entry_reference_ticks"))
    stop = _parse_tick(edge_candidate_payload.get("natural_invalidation_ticks"))
    rr_numerator = _parse_tick(edge_candidate_payload.get("rr_numerator"))
    rr_denominator = _parse_tick(edge_candidate_payload.get("rr_denominator"))
    if entry is None or stop is None or rr_numerator is None or rr_denominator is None:
        return False
    if direction == common.LONG and stop >= entry:
        return False
    if direction == common.SHORT and stop <= entry:
        return False
    floor_num, floor_den = _MIN_GEOMETRIC_RR_FRACTION
    if rr_denominator <= 0 or rr_numerator * floor_den < rr_denominator * floor_num:
        return False

    targets = edge_candidate_payload.get("targets")
    if not isinstance(targets, list) or not targets:
        return False
    for raw_target in targets:
        if not isinstance(raw_target, dict):
            return False
        target_ticks = _parse_tick(raw_target.get("target_ticks"))
        if target_ticks is None:
            return False
        reward = (target_ticks - entry) if direction == common.LONG else (entry - target_ticks)
        if reward <= 0:
            return False
    return True


def _derive_tradeability_flags(
    payload: dict, edge_candidate_valid: bool, trial_registry_state: dict,
) -> dict[str, bool]:
    """Re-derive the 12 tradeability conjuncts from the payload's own content — never a blind True.

    ``schema_valid`` reflects whether ``triad.edge_candidate.v2`` validation (schema + the
    forbidden-money-field guard) already passed. ``semantically_valid`` is derived INDEPENDENTLY
    via :func:`_semantically_valid` — the two conjuncts test genuinely different things (wire shape
    vs. actual geometric/referential validity), never the same boolean twice. Every other conjunct
    is checked against the ACTUAL field the caller supplied, so a structurally-valid-but-hollow
    payload (e.g. an empty ``targets`` array) still fails the flag it should fail, never a rubber
    stamp.
    """
    flags = {
        "schema_valid": edge_candidate_valid,
        "semantically_valid": _semantically_valid(payload, trial_registry_state),
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
        # .get(), never a direct subscript: a malformed candidate that reaches this mandatory
        # SHADOW fork may be missing EITHER field entirely (the schema_valid/stable_identity
        # tradeability flags will already be False for such a payload — this write must still
        # happen, honestly carrying None, never crash the whole partition on a poison envelope).
        "candidate_id": edge_candidate_payload.get("candidate_id"),
        "hypothesis_id": edge_candidate_payload.get("hypothesis_id"),
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

        # candidate_id is read raw, never through _require_str: it is UNTRUSTED CANDIDATE CONTENT,
        # and a malformed candidate (this field missing/empty/wrong-typed among any other) must
        # never raise and halt the whole partition — it must always resolve to either a published
        # row or a shadow-audited refusal. A candidate lacking a usable identity simply fails the
        # "stable_identity" tradeability conjunct below and takes the untradeable path; nothing
        # here can ever key state["candidates"] on a non-string, since that dict is only ever
        # written in the ALL-tradeability-flags-true branch, which requires stable_identity=True.
        candidate_id = edge_candidate_payload.get("candidate_id")
        existing = state["candidates"].get(candidate_id) if isinstance(candidate_id, str) else None
        if existing is not None:
            if existing == edge_candidate_payload:
                return TransitionResult(state)  # identical redelivery: idempotent no-op
            # A disagreeing redelivery is a DATA fact about conflicting candidate content, never an
            # envelope defect — named abstention, state left untouched, mirroring
            # shadow_ledger.py's own LEV-0070 identity-collision law (never a raise).
            event = common.abstention(
                CANDIDATE_ALREADY_PUBLISHED_DISAGREEMENT, formula=FORMULA_CANDIDATE_PUBLISHER,
                detail=f"candidate_id {candidate_id!r} is already published with disagreeing "
                       "content; a published candidate's geometry is immutable",
                refs={"candidate_id": candidate_id})
            return TransitionResult(state, (event,))

        # Contract validation (schema_valid) and semantic re-verification (semantically_valid --
        # capsule/trial identity resolution AND trial<->capsule binding, the directional stop-side
        # invariant, the RR floor, non-hollow targets) are two INDEPENDENT tradeability conjuncts,
        # never the same check twice, and NEITHER can ever raise on malformed candidate content.
        try:
            contracts.validate_payload("triad.edge_candidate.v2", edge_candidate_payload)
            edge_candidate_valid = True
        except contracts.ContractError:
            edge_candidate_valid = False

        flags_payload = dict(edge_candidate_payload)
        flags_payload["_market_watermark"] = market_watermark
        tradeability_flags = _derive_tradeability_flags(
            flags_payload, edge_candidate_valid, trial_registry_state)

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
