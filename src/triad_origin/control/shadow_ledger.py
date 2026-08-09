"""SHADOW candidate/trade ledger — the RC4 mandatory-capture population (B05 substrate).

This is the pure :class:`triad_origin.transition.DeterministicMachine` that turns every rejected
(or otherwise unexecuted) candidate into either a frozen ``triad.shadow_trade.v1``-payload-shaped
row, or — when the candidate itself fails the shadow-tradeability contract — a frozen
``triad.shadow_rejection_audit.v1``-payload-shaped row that names the failure and fabricates
NOTHING (no geometry, no invented trade). It implements the RC4 ``shadow_law`` bundle section and
the following task rows, cited at their exact instruction text:

* **LEV-0064/LEV-0065** — ``population`` is the immutable contract constant ``"SHADOW"`` and
  ``shadow_activation`` the immutable contract constant ``"LIVE"``; this module never accepts, and
  never even offers a code path for, setting either away from those values.
* **LEV-0067** — shadow-tradeability is defined as the conjunction of the twelve named conjuncts
  in :data:`TRADEABILITY_REQUIREMENTS` (verbatim, ``shadow_law.tradeability_requirements``); the
  caller supplies each as an explicit boolean — never inferred, never defaulted true.
* **LEV-0068** — any conjunct being false persists a ``shadow_rejection_audit.v1``-shaped row
  carrying the ``SHADOW_UNTRADEABLE`` marker instead of fabricating geometry or a trade.
* **LEV-0069** — ``shadow_trade_id`` is derived deterministically from candidate identity
  (``candidate_id``, ``hypothesis_id``), rejection revision (``rejection_stage`` — the one
  revision-like field this envelope shape carries), and simulator/resolver version
  (``simulator_version``, ``resolver_version``). Geometry is deliberately EXCLUDED from the
  identity so that two deliveries sharing identity but disagreeing on geometry collide on
  ``shadow_trade_id`` and are caught by the LEV-0070 unequal-hash refusal below, rather than
  silently minting two rows for "the same" trade.
* **LEV-0070** — at-least-once delivery is deduped by comparing the CONTENT hash
  (:data:`CONTENT_FIELDS`) of the freshly built row against the already-stored row for the same
  ``shadow_trade_id``: an exact match is a no-op (no state mutation, no event); a mismatch is a
  named identity-collision refusal (``SHADOW_LINEAGE_INCOMPLETE`` — the closed 32-code registry has
  no dedicated "colliding identity" code, and an unresolved competing claim on one identity is
  precisely what that code's meaning already covers: lineage that is "missing or ambiguous").
* **LEV-0072** — once a trade row is frozen, its symbol/side/entry/invalidation/target/horizon/
  size/rejection-stage/watermark fields are IMMUTABLE; every post-rejection mutation attempt is
  refused. This is enforced structurally: the only mutation path this machine exposes
  (``SHADOW_FILL_MODEL``) touches exactly the two fields (``fill_model_result``,
  ``terminal_outcome``) that start as the honest-null :data:`FILL_MODEL_PENDING` /
  :data:`TERMINAL_OUTCOME_PENDING` placeholders and may be written EXACTLY ONCE — see the "one
  designed exception" note below.
* **LEV-0075** — SHADOW resolves only from events available after its own frozen causal watermark;
  a ``SHADOW_FILL_MODEL`` resolution whose ``evaluated_at_watermark_us`` is earlier than the
  candidate's own frozen ``market_watermark`` timestamp would mean resolving the trade from before
  the candidate existed, so it is refused with the same ``SHADOW_LINEAGE_INCOMPLETE`` code.
* **LEV-0076** — a simulated no-fill is representable as the explicit marker
  ``{"result": "NO_FILL"}``; a rejection row is never deleted and a fill is never fabricated.

**The one designed exception to LEV-0072's immutability.** A trade's IDENTITY facts (symbol, side,
entry policy, invalidation, target, horizon, proposed geometry, rejection stage, causal watermark)
freeze at ``SHADOW_CANDIDATE`` time and can never move again — enforced structurally, because
``SHADOW_FILL_MODEL`` cannot touch them (its envelope carries no such field). But the FILL-MODEL
OUTCOME is, by construction, computed later against those same immutable frozen inputs (LEV-0073),
using only evidence at or after the frozen watermark (LEV-0075). ``fill_model_result`` and
``terminal_outcome`` therefore start as an honest-null placeholder and are written exactly once,
by the resolver, from data no earlier than the freeze — this is not a re-opening of the frozen
identity, it is the resolver depositing the one fact the identity freeze could not yet contain.

No code here reads a wall clock, opens a socket, or holds a credential — every timestamp
(``event_time_us``, ``recorded_time_us``, ``frozen_at_us``, ``observed_at_us``,
``evaluated_at_watermark_us``) is a caller-supplied "as-of" stamp, never a real clock read.
"""

from __future__ import annotations

from .. import canonical
from ..transition import Envelope, Params, Quality, State, TransitionResult
from . import lever_law

FORMULA_SHADOW_LEDGER = "SHADOW_LEDGER"

_KIND_SHADOW_CANDIDATE = "SHADOW_CANDIDATE"
_KIND_SHADOW_FILL_MODEL = "SHADOW_FILL_MODEL"

SHADOW_TRADE_RECORDED = "SHADOW_TRADE_RECORDED"
SHADOW_TRADE_RESOLVED = "SHADOW_TRADE_RESOLVED"
SHADOW_REJECTION_AUDIT_RECORDED = "SHADOW_REJECTION_AUDIT_RECORDED"
LEVER_REFUSAL = "LEVER_REFUSAL"

# The immutable RC4 contract constants (LEV-0064) — never a parameter, never overridable.
POPULATION_SHADOW = "SHADOW"
SHADOW_ACTIVATION_LIVE = "LIVE"

# shadow_law.tradeability_requirements — verbatim, RC4-declared, order-preserving (LEV-0067).
TRADEABILITY_REQUIREMENTS = (
    "schema_valid",
    "semantically_valid",
    "resolved_instrument",
    "side",
    "entry_policy",
    "invalidation",
    "target_or_terminal_rule",
    "horizon",
    "finite_numbers",
    "monotonic_clocks",
    "stable_identity",
    "causal_market_watermark",
)

# shadow_law.origin_dispositions — verbatim, closed (schema enum, triad.shadow_trade.v1).
ORIGIN_DISPOSITIONS = ("REJECTED", "ACCEPTED_NOT_EXECUTED", "PROVEN_NO_VENUE_EFFECT")

MARKER_SHADOW_UNTRADEABLE = "SHADOW_UNTRADEABLE"

# The structural key ORIGIN uses inside the opaque ``market_watermark`` object to carry the
# candidate's own frozen causal-watermark instant. The schema leaves ``market_watermark`` an
# opaque object; this is this module's own populated shape, not a schema requirement.
MARKET_WATERMARK_TS_KEY = "watermark_us"

# The honest-null placeholders a fresh trade row is frozen with (LEV-0076: never fabricate a fill;
# a trade with no resolution yet is neither a fill nor a NO_FILL — it is unresolved).
FILL_MODEL_PENDING = {"status": "PENDING"}
TERMINAL_OUTCOME_PENDING = {"status": "PENDING"}

# The shadow_trade.v1 payload fields that anchor ``shadow_trade_id`` (LEV-0069): candidate
# identity + rejection revision + simulator/resolver version. Geometry is deliberately excluded —
# see the module docstring.
SHADOW_TRADE_ID_FIELDS = (
    "candidate_id", "hypothesis_id", "rejection_stage", "simulator_version", "resolver_version",
)

# The full frozen-content subset compared for LEV-0070 dedup/collision detection. Excludes the
# bookkeeping timestamps (which are caller "as-of" stamps, not identity) and the still-pending
# fill-model fields (identical across every fresh row, so meaningless as a collision signal).
CONTENT_FIELDS = (
    "candidate_id", "hypothesis_id", "origin_disposition", "rejection_stage", "rejection_reason",
    "market_watermark", "proposed_geometry", "evaluation_notional_quote", "simulator_version",
    "resolver_version", "cost_model_version", "event_time_us",
)


class ShadowLedgerError(ValueError):
    """A malformed envelope or an internal invariant violation. Fail closed, named."""


def _require_dict(value: object, name: str) -> dict:
    if not isinstance(value, dict):
        raise ShadowLedgerError(f"{name} must be an object")
    return value


def _require_str(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ShadowLedgerError(f"{name} must be a non-empty string")
    return value


def _require_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ShadowLedgerError(f"{name} must be an exact int, got {type(value).__name__}")
    return value


def _failing_requirements(payload: dict) -> list[str]:
    """Every tradeability conjunct not supplied as the literal ``True`` (LEV-0067)."""
    return [name for name in TRADEABILITY_REQUIREMENTS if payload.get(name) is not True]


def _content_hash(row: dict) -> str:
    content = {key: row[key] for key in CONTENT_FIELDS}
    return canonical.sha256_hex(canonical.canonical_json(content))


def _shadow_trade_id(payload: dict) -> str:
    fields = [payload.get(name) for name in SHADOW_TRADE_ID_FIELDS]
    return canonical.digest_fields("shadow_trade_id", *fields)


def _audit_id(candidate_id: object, hypothesis_id: object, validation_failure: str,
              observed_at_us: int) -> str:
    return canonical.digest_fields(
        "shadow_rejection_audit_id", candidate_id, hypothesis_id, validation_failure,
        observed_at_us)


def _lever_event(resolution: lever_law.LeverResolution, *, refs: dict | None = None) -> dict:
    event = {
        "event_kind": LEVER_REFUSAL,
        "formula": FORMULA_SHADOW_LEDGER,
        "reason_code": resolution.refusal_code,
        "meaning": resolution.meaning,
        "minimum_action": dict(sorted(resolution.minimum_action.items())),
    }
    if refs:
        event["refs"] = dict(sorted(refs.items()))
    return event


def _build_untradeable_audit(payload: dict, failing: list[str]) -> dict:
    candidate_id = payload.get("candidate_id")
    hypothesis_id = payload.get("hypothesis_id")
    observed_at_us = _require_int(payload.get("event_time_us"), "event_time_us")
    validation_failure = ",".join(sorted(failing))
    audit_id = _audit_id(candidate_id, hypothesis_id, validation_failure, observed_at_us)
    return {
        "audit_id": audit_id,
        "attempt_identity": {"candidate_id": candidate_id, "hypothesis_id": hypothesis_id},
        "raw_source_evidence": dict(payload),
        "validation_failure": validation_failure,
        "marker": MARKER_SHADOW_UNTRADEABLE,
        "observed_at_us": observed_at_us,
    }


def _build_trade_row(payload: dict) -> dict:
    candidate_id = _require_str(payload.get("candidate_id"), "candidate_id")
    hypothesis_id = _require_str(payload.get("hypothesis_id"), "hypothesis_id")
    origin_disposition = payload.get("origin_disposition")
    if origin_disposition not in ORIGIN_DISPOSITIONS:
        raise ShadowLedgerError(
            f"origin_disposition must be one of {ORIGIN_DISPOSITIONS}, got {origin_disposition!r}")
    rejection_stage = _require_str(payload.get("rejection_stage"), "rejection_stage")
    rejection_reason = _require_str(payload.get("rejection_reason"), "rejection_reason")
    market_watermark = _require_dict(payload.get("market_watermark"), "market_watermark")
    _require_int(market_watermark.get(MARKET_WATERMARK_TS_KEY), MARKET_WATERMARK_TS_KEY)
    proposed_geometry = _require_dict(payload.get("proposed_geometry"), "proposed_geometry")
    evaluation_notional_quote = payload.get("evaluation_notional_quote")
    if not isinstance(evaluation_notional_quote, str):
        raise ShadowLedgerError("evaluation_notional_quote must be a canonical integer string")
    canonical.str_to_tick(evaluation_notional_quote)  # fail closed on a non-canonical string
    simulator_version = _require_str(payload.get("simulator_version"), "simulator_version")
    resolver_version = _require_str(payload.get("resolver_version"), "resolver_version")
    cost_model_version = _require_str(payload.get("cost_model_version"), "cost_model_version")
    event_time_us = _require_int(payload.get("event_time_us"), "event_time_us")

    row = {
        "shadow_trade_id": None,  # filled below, once the identity fields are validated
        "candidate_id": candidate_id,
        "hypothesis_id": hypothesis_id,
        # frozen_at_us/recorded_time_us are stamped from the caller's own event_time_us — this
        # module reads no clock, so "when it froze" and "when it was recorded" are the same
        # caller-supplied as-of instant as "when the candidate happened" absent any other input.
        "frozen_at_us": event_time_us,
        "origin_disposition": origin_disposition,
        "rejection_stage": rejection_stage,
        "rejection_reason": rejection_reason,
        "population": POPULATION_SHADOW,
        "shadow_activation": SHADOW_ACTIVATION_LIVE,
        "market_watermark": market_watermark,
        "proposed_geometry": proposed_geometry,
        "evaluation_notional_quote": evaluation_notional_quote,
        "simulator_version": simulator_version,
        "resolver_version": resolver_version,
        "cost_model_version": cost_model_version,
        "event_time_us": event_time_us,
        "recorded_time_us": event_time_us,
        "fill_model_result": dict(FILL_MODEL_PENDING),
        "terminal_outcome": dict(TERMINAL_OUTCOME_PENDING),
    }
    row["shadow_trade_id"] = _shadow_trade_id(row)
    return row


class ShadowLedger:
    """SHADOW candidate intake + trade lifecycle (:class:`triad_origin.transition.DeterministicMachine`)."""

    def initial_state(self) -> State:
        return {"trades": {}, "audits": {}}

    def transition(
        self, state: State, envelope: Envelope, params: Params, quality: Quality
    ) -> TransitionResult:
        kind = envelope.get("kind")
        payload = _require_dict(envelope.get("payload", {}), "payload")

        if kind == _KIND_SHADOW_CANDIDATE:
            return self._on_candidate(state, payload)
        if kind == _KIND_SHADOW_FILL_MODEL:
            return self._on_fill_model(state, payload)
        raise ShadowLedgerError(f"unknown SHADOW envelope kind: {kind!r}")

    # -- SHADOW_CANDIDATE -----------------------------------------------------------------------

    def _on_candidate(self, state: State, payload: dict) -> TransitionResult:
        failing = _failing_requirements(payload)
        if failing:
            audit = _build_untradeable_audit(payload, failing)
            audits = dict(state["audits"])
            audits[audit["audit_id"]] = audit
            resolution = lever_law.refuse(MARKER_SHADOW_UNTRADEABLE)
            event = {
                "event_kind": SHADOW_REJECTION_AUDIT_RECORDED, "formula": FORMULA_SHADOW_LEDGER,
                "reason_code": resolution.refusal_code, "meaning": resolution.meaning,
                "audit_id": audit["audit_id"], "payload": audit,
            }
            return TransitionResult(
                {"trades": state["trades"], "audits": audits}, (event,))

        row = _build_trade_row(payload)
        shadow_trade_id = row["shadow_trade_id"]
        trades = dict(state["trades"])
        existing = trades.get(shadow_trade_id)
        if existing is not None:
            if _content_hash(existing) == _content_hash(row):
                return TransitionResult(state)  # exact at-least-once redelivery: no-op (LEV-0070)
            resolution = lever_law.refuse("SHADOW_LINEAGE_INCOMPLETE")
            event = _lever_event(resolution, refs={"shadow_trade_id": shadow_trade_id})
            return TransitionResult(state, (event,))  # colliding identity: state UNTOUCHED

        trades[shadow_trade_id] = row
        event = {
            "event_kind": SHADOW_TRADE_RECORDED, "formula": FORMULA_SHADOW_LEDGER,
            "shadow_trade_id": shadow_trade_id, "payload": row,
        }
        return TransitionResult({"trades": trades, "audits": state["audits"]}, (event,))

    # -- SHADOW_FILL_MODEL ------------------------------------------------------------------------

    def _on_fill_model(self, state: State, payload: dict) -> TransitionResult:
        shadow_trade_id = _require_str(payload.get("shadow_trade_id"), "shadow_trade_id")
        row = state["trades"].get(shadow_trade_id)
        if row is None:
            resolution = lever_law.refuse("SHADOW_LINEAGE_INCOMPLETE")
            event = _lever_event(resolution, refs={"shadow_trade_id": shadow_trade_id})
            return TransitionResult(state, (event,))

        already_resolved = (
            row["fill_model_result"] != FILL_MODEL_PENDING
            or row["terminal_outcome"] != TERMINAL_OUTCOME_PENDING
        )
        if already_resolved:
            resolution = lever_law.refuse("SHADOW_LINEAGE_INCOMPLETE")  # LEV-0072: no re-mutation
            event = _lever_event(resolution, refs={"shadow_trade_id": shadow_trade_id})
            return TransitionResult(state, (event,))

        evaluated_at_watermark_us = _require_int(
            payload.get("evaluated_at_watermark_us"), "evaluated_at_watermark_us")
        frozen_watermark_us = row["market_watermark"][MARKET_WATERMARK_TS_KEY]
        if evaluated_at_watermark_us < frozen_watermark_us:
            # LEV-0075: resolving before the candidate's own frozen causal watermark would mean
            # resolving from evidence that predates the candidate's existence. Threshold is
            # inclusive (PAR-009): exactly at the frozen watermark is lawful.
            resolution = lever_law.refuse("SHADOW_LINEAGE_INCOMPLETE")
            event = _lever_event(resolution, refs={"shadow_trade_id": shadow_trade_id})
            return TransitionResult(state, (event,))

        fill_model_result = _require_dict(payload.get("fill_model_result"), "fill_model_result")
        terminal_outcome = _require_dict(payload.get("terminal_outcome"), "terminal_outcome")

        new_row = dict(row)
        new_row["fill_model_result"] = fill_model_result
        new_row["terminal_outcome"] = terminal_outcome
        trades = dict(state["trades"])
        trades[shadow_trade_id] = new_row
        event = {
            "event_kind": SHADOW_TRADE_RESOLVED, "formula": FORMULA_SHADOW_LEDGER,
            "shadow_trade_id": shadow_trade_id, "payload": new_row,
        }
        return TransitionResult({"trades": trades, "audits": state["audits"]}, (event,))
