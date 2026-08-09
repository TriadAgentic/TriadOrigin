"""B06 — preregistered trial family + leave-one-conjunct ablations, gating result access.

"Preregistered trial family and leave-one-conjunct ablations before result access"
(``docs/plan/01_MILESTONE_BREAKDOWN.md`` B06 deliverable) is a research-integrity control: a
trial's evaluated conjunct set, its ablation variants, and the earliest instant its results may be
inspected are all declared BEFORE any candidate is ever published under it — never chosen or
widened after seeing outcomes (the same "no hidden experiment" law
:mod:`triad_origin.timings` states for time bounds, applied here to trial DESIGN). This module is
the pure :class:`triad_origin.transition.DeterministicMachine` gate a candidate publisher
consults: no ``trial_id`` may appear on a published ``edge_candidate.v2`` unless it names a
registered :class:`TrialDefinition`, and no result-access request succeeds before the trial's own
declared ``results_available_after_us``.

**Preregistration is append-only and immutable.** Once a ``trial_id`` is registered, its
``conjunct_set`` (the full named list of gating conditions this trial's capsule evaluates) and its
``results_available_after_us`` bound are FROZEN — a second ``PREREGISTER_TRIAL`` for the same
``trial_id`` is refused if any field disagrees with the stored one (never silently overwritten),
and is an idempotent no-op if it agrees exactly (at-least-once redelivery, mirroring
:mod:`triad_origin.control.shadow_ledger`'s dedup law).

**Leave-one-conjunct ablations are auto-derived, never hand-picked.** For a trial with conjunct
set ``{c1, c2, ..., cN}`` (N >= 1), :func:`_derive_ablations` mechanically produces exactly N
ablation variants, each omitting exactly one conjunct — ``ablation_id`` is a stable digest of
``(trial_id, omitted_conjunct)``, so the SAME trial always derives the SAME ablation ids, and a
human can never quietly add or drop an ablation arm after the fact (the set is a pure function of
the registered conjunct set alone).

**Result access is refused before its declared instant, structurally.** ``REQUEST_RESULT_ACCESS``
never reads a clock — the caller supplies ``requested_at_us`` (an explicit "as of" stamp, exactly
like every other module's causal-time convention) and the gate is a plain integer comparison
against the trial's own frozen bound; an unregistered ``trial_id`` is refused by name, never
treated as "not yet ready" (those are different facts: one never existed, the other exists but is
early).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..canonical import canonical_json, sha256_hex
from ..transition import Envelope, Params, Quality, State, TransitionResult
from . import common

FORMULA_TRIAL_REGISTRY = "TRIAL_REGISTRY"

_KIND_PREREGISTER_TRIAL = "PREREGISTER_TRIAL"
_KIND_REQUEST_RESULT_ACCESS = "REQUEST_RESULT_ACCESS"

TRIAL_PREREGISTERED = "TRIAL_PREREGISTERED"
RESULT_ACCESS_GRANTED = "RESULT_ACCESS_GRANTED"

TRIAL_ALREADY_REGISTERED_DISAGREEMENT = "TRIAL_ALREADY_REGISTERED_DISAGREEMENT"
TRIAL_NOT_PREREGISTERED = "TRIAL_NOT_PREREGISTERED"
RESULT_ACCESS_TOO_EARLY = "RESULT_ACCESS_TOO_EARLY"


class TrialRegistryError(ValueError):
    """A trial-registry usage error (fail closed, named — never a silent default)."""


class TrialUnavailableError(TrialRegistryError):
    """The requested trial_id has no registered, ratifiable definition."""


@dataclass(frozen=True)
class TrialDefinition:
    trial_id: str
    capsule_semantic_id: str
    conjunct_set: tuple[str, ...]
    results_available_after_us: int
    preregistered_at_us: int
    ablation_ids: tuple[str, ...]


def _ablation_id(trial_id: str, omitted_conjunct: str) -> str:
    return sha256_hex(canonical_json({"trial_id": trial_id, "omitted_conjunct": omitted_conjunct}))


def _derive_ablations(trial_id: str, conjunct_set: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(_ablation_id(trial_id, conjunct) for conjunct in conjunct_set)


def _require_str(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise TrialRegistryError(f"{name} must be a non-empty string")
    return value


def _require_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TrialRegistryError(f"{name} must be an exact int")
    return value


def _require_conjunct_set(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not value:
        raise TrialRegistryError("conjunct_set must be a non-empty list of named conjuncts")
    if len(set(value)) != len(value):
        raise TrialRegistryError("conjunct_set must not contain a duplicated conjunct name")
    for item in value:
        if not isinstance(item, str) or not item:
            raise TrialRegistryError("every conjunct name must be a non-empty string")
    return tuple(value)


class TrialRegistry:
    """The append-only, immutable-once-set preregistered-trial gate."""

    def initial_state(self) -> State:
        return {"trials": {}}

    def transition(
        self, state: State, envelope: Envelope, params: Params, quality: Quality
    ) -> TransitionResult:
        kind = envelope.get("kind")
        payload = envelope.get("payload", {})
        if kind == _KIND_PREREGISTER_TRIAL:
            return self._preregister(state, payload)
        if kind == _KIND_REQUEST_RESULT_ACCESS:
            return self._request_access(state, payload)
        raise TrialRegistryError(f"unknown trial-registry envelope kind: {kind!r}")

    def _preregister(self, state: State, payload: dict) -> TransitionResult:
        trial_id = _require_str(payload.get("trial_id"), "trial_id")
        capsule_semantic_id = _require_str(payload.get("capsule_semantic_id"), "capsule_semantic_id")
        conjunct_set = _require_conjunct_set(payload.get("conjunct_set"))
        results_available_after_us = _require_int(
            payload.get("results_available_after_us"), "results_available_after_us")
        preregistered_at_us = _require_int(payload.get("preregistered_at_us"), "preregistered_at_us")
        if results_available_after_us < preregistered_at_us:
            raise TrialRegistryError(
                "results_available_after_us must not precede preregistered_at_us — a trial can "
                "never declare its own results visible before it was even registered")

        ablation_ids = _derive_ablations(trial_id, conjunct_set)
        new_row = {
            "trial_id": trial_id, "capsule_semantic_id": capsule_semantic_id,
            "conjunct_set": conjunct_set, "results_available_after_us": results_available_after_us,
            "preregistered_at_us": preregistered_at_us, "ablation_ids": ablation_ids,
        }

        existing = state["trials"].get(trial_id)
        if existing is not None:
            if existing == new_row:
                return TransitionResult(state)  # identical redelivery: idempotent no-op
            event = common.abstention(
                TRIAL_ALREADY_REGISTERED_DISAGREEMENT, formula=FORMULA_TRIAL_REGISTRY,
                detail=f"trial_id {trial_id!r} is already registered with disagreeing fields; "
                       "a preregistered trial's design is immutable",
                refs={"trial_id": trial_id})
            return TransitionResult(state, (event,))

        trials = dict(state["trials"])
        trials[trial_id] = new_row
        event = {
            "event_kind": TRIAL_PREREGISTERED, "formula": FORMULA_TRIAL_REGISTRY,
            "trial_id": trial_id, "ablation_ids": list(ablation_ids),
        }
        return TransitionResult({"trials": trials}, (event,))

    def _request_access(self, state: State, payload: dict) -> TransitionResult:
        trial_id = _require_str(payload.get("trial_id"), "trial_id")
        requested_at_us = _require_int(payload.get("requested_at_us"), "requested_at_us")

        row = state["trials"].get(trial_id)
        if row is None:
            event = common.abstention(
                TRIAL_NOT_PREREGISTERED, formula=FORMULA_TRIAL_REGISTRY,
                detail=f"trial_id {trial_id!r} was never preregistered; result access refused",
                refs={"trial_id": trial_id})
            return TransitionResult(state, (event,))

        if requested_at_us < row["results_available_after_us"]:
            event = common.abstention(
                RESULT_ACCESS_TOO_EARLY, formula=FORMULA_TRIAL_REGISTRY,
                detail=(f"result access requested at {requested_at_us} before the trial's own "
                        f"declared results_available_after_us={row['results_available_after_us']}"),
                refs={"trial_id": trial_id})
            return TransitionResult(state, (event,))

        event = {
            "event_kind": RESULT_ACCESS_GRANTED, "formula": FORMULA_TRIAL_REGISTRY,
            "trial_id": trial_id, "requested_at_us": requested_at_us,
        }
        return TransitionResult(state, (event,))


def resolve_trial(state: State, trial_id: str) -> TrialDefinition:
    """Read-only helper: resolve a registered trial's frozen definition from a registry state."""
    row = state.get("trials", {}).get(trial_id)
    if row is None:
        raise TrialUnavailableError(f"trial_id {trial_id!r} is not preregistered")
    return TrialDefinition(
        trial_id=row["trial_id"], capsule_semantic_id=row["capsule_semantic_id"],
        conjunct_set=tuple(row["conjunct_set"]),
        results_available_after_us=row["results_available_after_us"],
        preregistered_at_us=row["preregistered_at_us"],
        ablation_ids=tuple(row["ablation_ids"]))
