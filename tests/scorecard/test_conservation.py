"""Adversarial tests for population routing and terminal conservation."""

from __future__ import annotations

from dataclasses import replace

from triad_origin.scorecard.builder import build_scorecard
from triad_origin.scorecard.conservation import derive_routes, reconcile_terminals
from triad_origin.scorecard.law import REQUIRED_EDGE_KEYS, canonical_stage_requirements
from triad_origin.scorecard.model import (
    Activation,
    Attestation,
    Availability,
    CandidateCohort,
    ComponentBinding,
    DecisionState,
    DeploymentRole,
    EdgeObservation,
    Evaluation,
    ExpectedState,
    Freshness,
    Implementation,
    MappingStatus,
    MetricClass,
    MetricValue,
    Population,
    Posture,
    PostureObservation,
    ProofDimensions,
    Reconciliation,
    SourceKind,
    StageId,
    StageObservation,
    TerminalKind,
    TerminalRecord,
)


_DIGEST = "1" * 64
_BASELINE = Posture("OFF", "OFF", "OFF", "LIVE")
_AS_OF_US = 1_000_000


def _evaluation(
    *,
    decision_state: DecisionState = DecisionState.ACCEPTED,
    matured: bool = True,
    evaluation_id: str = "evaluation:1",
    candidate_id: str = "candidate:1",
    event_posture: Posture = _BASELINE,
) -> Evaluation:
    return Evaluation(
        evaluation_id=evaluation_id,
        candidate_id=candidate_id,
        decision_state=decision_state,
        route_revision="route:1",
        observed_at_us=100,
        maturity_deadline_us=200 if matured else _AS_OF_US + 1,
        event_posture=event_posture,
    )


def _terminal(
    population_instance_id: str,
    *,
    terminal_id: str = "terminal:1",
    kind: TerminalKind = TerminalKind.ACCEPTED_NOT_EXECUTED,
    payload_digest: str = _DIGEST,
    reason_code: str | None = None,
) -> TerminalRecord:
    return TerminalRecord(
        terminal_id=terminal_id,
        population_instance_id=population_instance_id,
        kind=kind,
        payload_digest=payload_digest,
        reason_code=reason_code,
        evidence_refs=("evidence:terminal:1",),
    )


def _proof(*, activation: Activation = Activation.LIVE) -> ProofDimensions:
    return ProofDimensions(
        evidence_id="evidence:proof:1",
        source_kind=SourceKind.AUTHORITATIVE_SOURCE,
        implementation=Implementation.PRESENT,
        absence_proven=False,
        deployment_role=DeploymentRole.ACTIVE_WRITER,
        activation=activation,
        freshness=Freshness.FRESH,
        freshness_age_ms=0,
        freshness_bound_ms=1_000,
        reconciliation=Reconciliation.RECONCILED,
        attestation=Attestation.VALID,
        source_present=True,
        formula_correct=True,
        authority_closed=True,
        runtime_attested=True,
        source_watermark="source:1",
        consumer_watermark="consumer:1",
        build_digest=_DIGEST,
        config_digest=_DIGEST,
        contract_digest=_DIGEST,
        binding_digest=_DIGEST,
        side_effect_census_complete=True,
        reason_code=None,
        evidence_refs=("evidence:proof:1",),
    )


def _candidate_cohort(evaluations: tuple[Evaluation, ...]) -> CandidateCohort:
    candidate_ids = tuple(sorted({evaluation.candidate_id for evaluation in evaluations}))
    zero_proof = None
    if not candidate_ids:
        zero_proof = {
            "query_digest": _DIGEST,
            "source_cut_digest": _DIGEST,
            "source_completeness": "COMPLETE",
            "watermark": "source:cohort:1",
        }
    return CandidateCohort(
        cohort_id="cohort:1",
        window_start_us=0,
        window_end_us=500,
        source_watermark="source:cohort:1",
        source_cut_digest=_DIGEST,
        complete=True,
        candidate_ids=candidate_ids,
        zero_proof=zero_proof,
        evidence_refs=("evidence:cohort:1",),
    )


def _build_report(evaluations: tuple[Evaluation, ...], terminals: tuple[TerminalRecord, ...]) -> dict:
    components = tuple(
        ComponentBinding(
            component_id=f"component:{stage.value}",
            stage_id=stage,
            role="scorecard subject",
            mapping_status=MappingStatus.RATIFIED,
            mapping_evidence_refs=(f"mapping:{stage.value}",),
            authority_claims=(),
        )
        for stage in StageId
    )
    stages = tuple(
        StageObservation(
            stage_id=requirement.stage_id,
            component_id=f"component:{requirement.stage_id.value}",
            path_id=requirement.path_id,
            proof=_proof(
                activation=(
                    Activation.OFF
                    if requirement.expected_state is ExpectedState.OFF
                    else Activation.LIVE
                )
            ),
        )
        for requirement in canonical_stage_requirements()
    )
    edges = tuple(
        EdgeObservation(source_stage=source, target_stage=target, channel=channel, proof=_proof())
        for source, target, channel in REQUIRED_EDGE_KEYS
    )
    posture = PostureObservation(
        desired=_BASELINE,
        observed=_BASELINE,
        freshness=Freshness.FRESH,
        reconciliation=Reconciliation.RECONCILED,
        attestation=Attestation.VALID,
        side_effect_census_complete=True,
        evidence_refs=("evidence:posture:1",),
    )
    metric = MetricValue(
        metric_id="e02.candidates.count",
        metric_class=MetricClass.COUNT,
        population=None,
        value_type="INTEGER",
        value=len({evaluation.candidate_id for evaluation in evaluations}),
        unit="COUNT",
        availability=Availability.OBSERVED,
        reason_code=None,
        zero_proof=(
            None
            if evaluations
            else {
                "query_digest": _DIGEST,
                "source_cut_digest": _DIGEST,
                "source_completeness": "COMPLETE",
                "watermark": "source:cohort:1",
            }
        ),
        evidence_refs=("evidence:metric:1",),
    )
    return build_scorecard(
        report_id="scorecard:test:1",
        as_of_us=_AS_OF_US,
        components=components,
        posture=posture,
        stage_observations=stages,
        edge_observations=edges,
        evaluations=evaluations,
        terminals=terminals,
        metrics=(metric,),
        candidate_cohort=_candidate_cohort(evaluations),
    )


def test_matured_route_without_terminal_is_unexplained() -> None:
    evaluations = (_evaluation(),)
    routes = derive_routes(evaluations, _AS_OF_US)

    result = reconcile_terminals(evaluations, routes, ())

    assert result.unexplained_count == 1
    assert result.unexplained_population_instance_ids == (routes[0].population_instance_id,)
    assert not result.reconciled


def test_exact_duplicate_terminal_replay_is_idempotent() -> None:
    evaluations = (_evaluation(),)
    routes = derive_routes(evaluations, _AS_OF_US)
    terminal = _terminal(routes[0].population_instance_id)

    result = reconcile_terminals(evaluations, routes, (terminal, terminal))

    assert result.idempotent_duplicate_count == 1
    assert result.conflict_count == 0
    assert result.reconciled_terminal_count == 1
    assert result.reconciled


def test_same_payload_digest_under_different_terminal_ids_is_a_conflict() -> None:
    evaluations = (_evaluation(),)
    routes = derive_routes(evaluations, _AS_OF_US)
    first = _terminal(routes[0].population_instance_id, terminal_id="terminal:1")
    second = replace(first, terminal_id="terminal:2")

    result = reconcile_terminals(evaluations, routes, (first, second))

    assert result.conflict_count == 1
    assert result.conflict_population_instance_ids == (routes[0].population_instance_id,)
    assert not result.reconciled


def test_same_terminal_id_with_a_different_payload_is_a_conflict() -> None:
    evaluations = (_evaluation(),)
    routes = derive_routes(evaluations, _AS_OF_US)
    first = _terminal(routes[0].population_instance_id)
    second = replace(first, payload_digest="2" * 64)

    result = reconcile_terminals(evaluations, routes, (first, second))

    assert result.conflict_count == 1
    assert result.conflict_population_instance_ids == (routes[0].population_instance_id,)
    assert not result.reconciled


def test_pending_route_is_separate_but_cannot_make_builder_full() -> None:
    evaluations = (_evaluation(matured=False),)
    routes = derive_routes(evaluations, _AS_OF_US)
    result = reconcile_terminals(evaluations, routes, ())

    assert result.pending_count == 1
    assert result.unexplained_count == 0

    report = _build_report(evaluations, ())
    assert report["conservation"]["pending_count"] == 1
    assert report["publication"]["outcome"] != "FULL"


def test_empty_evaluation_population_cannot_vacuously_make_builder_full() -> None:
    report = _build_report((), ())

    assert report["conservation"]["candidate_count"] == 0
    assert report["conservation"]["population_instance_count"] == 0
    assert report["publication"]["outcome"] != "FULL"


def test_shadow_paper_and_testnet_are_three_explicit_population_routes() -> None:
    posture = Posture("TESTNET", "LIVE", "LIVE", "LIVE")
    evaluations = (_evaluation(event_posture=posture),)
    routes = derive_routes(evaluations, _AS_OF_US)

    assert {route.population for route in routes} == {
        Population.SHADOW,
        Population.PAPER,
        Population.TESTNET,
    }
    assert len({route.population_instance_id for route in routes}) == 3

    terminals = tuple(
        _terminal(
            route.population_instance_id,
            terminal_id=f"terminal:{route.population.value}",
            kind=TerminalKind.OUTCOME_COMPLETE,
        )
        for route in routes
    )
    result = reconcile_terminals(evaluations, routes, terminals)

    assert result.population_instance_count == 3
    assert result.reconciled_terminal_count == 3
    assert result.reconciled


def test_unknown_submit_under_current_off_remains_visible_and_unreconciled() -> None:
    event_posture = Posture("LIVE", "LIVE", "OFF", "LIVE")
    evaluations = (_evaluation(
        decision_state=DecisionState.ACCEPTED,
        event_posture=event_posture,
    ),)
    routes = derive_routes(evaluations, _AS_OF_US)

    assert {route.population for route in routes} == {Population.SHADOW, Population.LIVE}
    live_route = next(route for route in routes if route.population is Population.LIVE)
    terminal = _terminal(
        live_route.population_instance_id,
        kind=TerminalKind.UNKNOWN_SUBMIT_UNRECONCILED,
        reason_code="UNKNOWN_SUBMIT_UNRECONCILED",
    )
    result = reconcile_terminals(evaluations, routes, (terminal,))

    assert result.unknown_submit_population_instance_ids == (
        live_route.population_instance_id,
    )
    assert not result.reconciled


def test_risk_denied_venue_route_cannot_erase_mandatory_shadow_capture() -> None:
    event_posture = Posture("TESTNET", "LIVE", "OFF", "LIVE")
    evaluations = (_evaluation(event_posture=event_posture),)
    routes = derive_routes(evaluations, _AS_OF_US)

    assert {route.population for route in routes} == {Population.SHADOW, Population.TESTNET}
    shadow = next(route for route in routes if route.population is Population.SHADOW)
    venue = next(route for route in routes if route.population is Population.TESTNET)
    terminals = (
        _terminal(shadow.population_instance_id, terminal_id="terminal:shadow"),
        _terminal(
            venue.population_instance_id,
            terminal_id="terminal:risk-denied",
            kind=TerminalKind.RISK_DENIED,
            reason_code="VENUE_ENVIRONMENT_UNVERIFIED",
        ),
    )

    result = reconcile_terminals(evaluations, routes, terminals)

    assert result.reconciled_terminal_count == 2
    assert result.reconciled
