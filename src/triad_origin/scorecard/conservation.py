"""Population-aware routing and terminal-conservation accounting.

Candidate, evaluation, and population-instance identities remain distinct.  PAPER may coexist with
one TESTNET or LIVE copy, so row totals are never treated as a sequential funnel.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..canonical import canonical_json, sha256_hex
from .law import require_registered_reason
from .model import (
    DecisionState,
    Evaluation,
    Population,
    Posture,
    RouteInstance,
    ScorecardError,
    TerminalKind,
    TerminalRecord,
)


@dataclass(frozen=True)
class ConservationResult:
    candidate_count: int
    evaluation_count: int
    population_instance_count: int
    reconciled_terminal_count: int
    pending_count: int
    unexplained_count: int
    conflict_count: int
    orphan_terminal_count: int
    idempotent_duplicate_count: int
    unexplained_population_instance_ids: tuple[str, ...]
    conflict_population_instance_ids: tuple[str, ...]
    pending_population_instance_ids: tuple[str, ...]
    orphan_terminal_ids: tuple[str, ...]
    unknown_submit_population_instance_ids: tuple[str, ...]
    multiplicity_explicit: bool
    reconciled: bool

    def to_dict(self) -> dict:
        return {
            "candidate_count": self.candidate_count,
            "evaluation_count": self.evaluation_count,
            "population_instance_count": self.population_instance_count,
            "reconciled_terminal_count": self.reconciled_terminal_count,
            "pending_count": self.pending_count,
            "unexplained_count": self.unexplained_count,
            "conflict_count": self.conflict_count,
            "orphan_terminal_count": self.orphan_terminal_count,
            "idempotent_duplicate_count": self.idempotent_duplicate_count,
            "unexplained_population_instance_ids": list(self.unexplained_population_instance_ids),
            "conflict_population_instance_ids": list(self.conflict_population_instance_ids),
            "pending_population_instance_ids": list(self.pending_population_instance_ids),
            "orphan_terminal_ids": list(self.orphan_terminal_ids),
            "unknown_submit_population_instance_ids": list(
                self.unknown_submit_population_instance_ids
            ),
            "multiplicity_explicit": self.multiplicity_explicit,
            "reconciled": self.reconciled,
        }


def derive_routes(evaluations: tuple[Evaluation, ...], as_of_us: int) -> tuple[RouteInstance, ...]:
    """Derive routes from each authenticated event-time lever cut, never current posture."""
    if isinstance(as_of_us, bool) or not isinstance(as_of_us, int) or as_of_us < 0:
        raise ScorecardError("as_of_us must be a non-negative exact integer")
    _require_unique_evaluations(evaluations)
    routes: list[RouteInstance] = []
    for evaluation in evaluations:
        if evaluation.observed_at_us > as_of_us:
            raise ScorecardError("evaluation observation cannot be in the report future")
        populations = _route_populations(evaluation, evaluation.event_posture)
        for population, terminals in populations:
            routes.append(RouteInstance(
                population_instance_id=_population_instance_id(evaluation, population),
                evaluation_id=evaluation.evaluation_id,
                candidate_id=evaluation.candidate_id,
                population=population,
                allowed_terminals=terminals,
                matured=as_of_us >= evaluation.maturity_deadline_us,
            ))
    ids = [route.population_instance_id for route in routes]
    if len(ids) != len(set(ids)):
        raise ScorecardError("derived population-instance identity collision")
    return tuple(routes)


def reconcile_terminals(
    evaluations: tuple[Evaluation, ...],
    routes: tuple[RouteInstance, ...],
    terminals: tuple[TerminalRecord, ...],
) -> ConservationResult:
    """Require exactly one terminal per matured population route.

    Byte-identical redelivery is idempotent.  Unequal-hash or unequal-kind claims for one route are
    conflicts.  A terminal for no declared route is an orphan.  An unresolved unknown submit is
    visible but can never make the result reconciled.
    """
    _require_unique_evaluations(evaluations)
    route_by_id: dict[str, RouteInstance] = {}
    for route in routes:
        if route.population_instance_id in route_by_id:
            raise ScorecardError(f"duplicate route identity: {route.population_instance_id}")
        route_by_id[route.population_instance_id] = route

    by_route: dict[str, list[TerminalRecord]] = {key: [] for key in route_by_id}
    orphans: list[str] = []
    terminal_identity_claims: dict[str, tuple[str, TerminalKind, str]] = {}
    cross_route_conflicts: set[str] = set()
    for record in terminals:
        if record.reason_code is not None:
            require_registered_reason(record.reason_code)
        claim = (record.population_instance_id, record.kind, record.payload_digest)
        prior = terminal_identity_claims.get(record.terminal_id)
        if prior is not None and prior != claim:
            cross_route_conflicts.add(record.population_instance_id)
            cross_route_conflicts.add(prior[0])
        else:
            terminal_identity_claims[record.terminal_id] = claim
        if record.population_instance_id not in route_by_id:
            orphans.append(record.terminal_id)
            continue
        by_route[record.population_instance_id].append(record)

    unexplained: list[str] = []
    conflicts = set(cross_route_conflicts)
    pending: list[str] = []
    unknown_submit: list[str] = []
    reconciled_count = 0
    duplicate_count = 0

    for route_id, route in sorted(route_by_id.items()):
        records = by_route[route_id]
        signatures = {
            (record.terminal_id, record.kind, record.payload_digest, record.reason_code,
             record.evidence_refs)
            for record in records
        }
        duplicate_count += len(records) - len(signatures)
        if not records:
            if route.matured:
                unexplained.append(route_id)
            else:
                pending.append(route_id)
            continue
        # Idempotent replay is the exact same terminal fact.  A second terminal id,
        # reason, or evidence set is a competing terminal claim even when the payload
        # happens to have the same digest.
        if len(signatures) != 1:
            conflicts.add(route_id)
            continue

        _terminal_id, kind, _digest, _reason, _refs = next(iter(signatures))
        if kind not in route.allowed_terminals:
            conflicts.add(route_id)
            continue
        if kind is TerminalKind.UNKNOWN_SUBMIT_UNRECONCILED:
            unknown_submit.append(route_id)
            continue
        if not route.matured:
            pending.append(route_id)
            continue
        reconciled_count += 1

    candidate_count = len({evaluation.candidate_id for evaluation in evaluations})
    evaluation_count = len(evaluations)
    multiplicity_explicit = all(
        evaluation.evaluation_id and evaluation.route_revision for evaluation in evaluations
    )
    reconciled = not (
        unexplained or conflicts or orphans or unknown_submit or not multiplicity_explicit
    )
    return ConservationResult(
        candidate_count=candidate_count,
        evaluation_count=evaluation_count,
        population_instance_count=len(routes),
        reconciled_terminal_count=reconciled_count,
        pending_count=len(pending),
        unexplained_count=len(unexplained),
        conflict_count=len(conflicts),
        orphan_terminal_count=len(orphans),
        idempotent_duplicate_count=duplicate_count,
        unexplained_population_instance_ids=tuple(sorted(unexplained)),
        conflict_population_instance_ids=tuple(sorted(conflicts)),
        pending_population_instance_ids=tuple(sorted(pending)),
        orphan_terminal_ids=tuple(sorted(orphans)),
        unknown_submit_population_instance_ids=tuple(sorted(unknown_submit)),
        multiplicity_explicit=multiplicity_explicit,
        reconciled=reconciled,
    )


def _route_populations(
    evaluation: Evaluation, posture: Posture
) -> tuple[tuple[Population, tuple[TerminalKind, ...]], ...]:
    if evaluation.decision_state is DecisionState.REJECTED:
        return ((Population.SHADOW, (TerminalKind.REJECTED,)),)
    if evaluation.decision_state is DecisionState.UNTRADEABLE:
        return ((Population.SHADOW, (TerminalKind.SHADOW_UNTRADEABLE,)),)

    # Mandatory SHADOW is an independent population, not a fallback.  It coexists with PAPER and
    # venue routes so every accepted evaluation retains a no-money terminal record even when a
    # separate route later reaches risk or execution.
    routed: list[tuple[Population, tuple[TerminalKind, ...]]] = [
        (Population.SHADOW, (
            TerminalKind.ACCEPTED_NOT_EXECUTED,
            TerminalKind.EXPIRED,
            TerminalKind.OUTCOME_COMPLETE,
        ))
    ]
    if posture.paper_activation == "LIVE":
        routed.append((Population.PAPER, (
            TerminalKind.EXECUTION_REJECTED,
            TerminalKind.CANCELED_NO_FILL,
            TerminalKind.OUTCOME_COMPLETE,
        )))
    if posture.venue_activation == "LIVE":
        population = Population(posture.venue_environment)
        routed.append((population, (
            TerminalKind.WITHDRAWN_PRE_SEND,
            TerminalKind.RISK_DENIED,
            TerminalKind.EXECUTION_REJECTED,
            TerminalKind.CANCELED_NO_FILL,
            TerminalKind.UNKNOWN_SUBMIT_UNRECONCILED,
            TerminalKind.PROVEN_NO_VENUE_EFFECT,
            TerminalKind.OUTCOME_COMPLETE,
        )))
    return tuple(routed)


def _population_instance_id(evaluation: Evaluation, population: Population) -> str:
    preimage = {
        "candidate_id": evaluation.candidate_id,
        "evaluation_id": evaluation.evaluation_id,
        "population": population.value,
        "route_revision": evaluation.route_revision,
    }
    return "popinst_" + sha256_hex(canonical_json(preimage))


def _require_unique_evaluations(evaluations: tuple[Evaluation, ...]) -> None:
    identities = [evaluation.evaluation_id for evaluation in evaluations]
    if len(identities) != len(set(identities)):
        raise ScorecardError("evaluation_id must be unique; multiplicity requires distinct IDs")
