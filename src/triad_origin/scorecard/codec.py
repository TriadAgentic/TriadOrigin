"""Strict JSON-object codec for the diagnostic full-pipeline scorecard input."""

from __future__ import annotations

from typing import Any

from .builder import build_scorecard
from .model import (
    Activation,
    Attestation,
    AuthorityClaim,
    Availability,
    CandidateCohort,
    ComponentBinding,
    DecisionState,
    DeploymentRole,
    EdgeObservation,
    Evaluation,
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
    ScorecardError,
    SourceKind,
    StageId,
    StageObservation,
    TerminalKind,
    TerminalRecord,
)


INPUT_SCHEMA = "triad.origin.full_pipeline_scorecard.input.v1"


def build_scorecard_from_dict(document: dict[str, Any]) -> dict:
    """Parse a closed evidence document and build its immutable diagnostic report."""
    _closed_object(document, {
        "schema", "report_id", "as_of_us", "components", "posture", "stages", "edges",
        "cohort", "evaluations", "terminals", "metrics",
    }, "input")
    if document["schema"] != INPUT_SCHEMA:
        raise ScorecardError(f"input schema must be {INPUT_SCHEMA}")
    return build_scorecard(
        report_id=_text(document["report_id"], "report_id"),
        as_of_us=_int(document["as_of_us"], "as_of_us"),
        components=tuple(_component(row) for row in _array(document["components"], "components")),
        candidate_cohort=_cohort(document["cohort"]),
        posture=_posture_observation(document["posture"]),
        stage_observations=tuple(_stage(row) for row in _array(document["stages"], "stages")),
        edge_observations=tuple(_edge(row) for row in _array(document["edges"], "edges")),
        evaluations=tuple(
            _evaluation(row) for row in _array(document["evaluations"], "evaluations")
        ),
        terminals=tuple(_terminal(row) for row in _array(document["terminals"], "terminals")),
        metrics=tuple(_metric(row) for row in _array(document["metrics"], "metrics")),
    )


def _component(row: Any) -> ComponentBinding:
    _closed_object(row, {
        "component_id", "stage", "role", "mapping_status", "mapping_evidence_refs",
        "authority_claims",
    }, "component")
    return ComponentBinding(
        component_id=_text(row["component_id"], "component_id"),
        stage_id=_enum(StageId, row["stage"], "component stage"),
        role=_text(row["role"], "component role"),
        mapping_status=_enum(MappingStatus, row["mapping_status"], "mapping_status"),
        mapping_evidence_refs=_texts(row["mapping_evidence_refs"], "mapping_evidence_refs"),
        authority_claims=tuple(
            _enum(AuthorityClaim, value, "authority_claim")
            for value in _array(row["authority_claims"], "authority_claims")
        ),
    )


def _posture_observation(row: Any) -> PostureObservation:
    _closed_object(row, {
        "desired", "observed", "freshness", "reconciliation", "attestation",
        "side_effect_census_complete", "evidence_refs",
    }, "posture")
    observed = None if row["observed"] is None else _posture(row["observed"], "observed posture")
    return PostureObservation(
        desired=_posture(row["desired"], "desired posture"),
        observed=observed,
        freshness=_enum(Freshness, row["freshness"], "posture freshness"),
        reconciliation=_enum(Reconciliation, row["reconciliation"], "posture reconciliation"),
        attestation=_enum(Attestation, row["attestation"], "posture attestation"),
        side_effect_census_complete=_optional_bool(
            row["side_effect_census_complete"], "posture side_effect_census_complete"
        ),
        evidence_refs=_texts(row["evidence_refs"], "posture evidence_refs"),
    )


def _posture(row: Any, where: str) -> Posture:
    _closed_object(row, {
        "venue_environment", "venue_activation", "paper_activation", "shadow_activation",
    }, where)
    return Posture(
        venue_environment=_text(row["venue_environment"], f"{where} venue_environment"),
        venue_activation=_text(row["venue_activation"], f"{where} venue_activation"),
        paper_activation=_text(row["paper_activation"], f"{where} paper_activation"),
        shadow_activation=_text(row["shadow_activation"], f"{where} shadow_activation"),
    )


def _stage(row: Any) -> StageObservation:
    _closed_object(row, {"stage", "component_id", "path", "proof"}, "stage observation")
    return StageObservation(
        stage_id=_enum(StageId, row["stage"], "stage"),
        component_id=_text(row["component_id"], "stage component_id"),
        path_id=_text(row["path"], "stage path"),
        proof=_proof(row["proof"]),
    )


def _edge(row: Any) -> EdgeObservation:
    _closed_object(row, {"source_stage", "target_stage", "channel", "proof"}, "edge")
    return EdgeObservation(
        source_stage=_enum(StageId, row["source_stage"], "edge source_stage"),
        target_stage=_enum(StageId, row["target_stage"], "edge target_stage"),
        channel=_text(row["channel"], "edge channel"),
        proof=_proof(row["proof"]),
    )


def _proof(row: Any) -> ProofDimensions:
    required = {
        "evidence_id", "source_kind", "implementation", "absence_proven", "deployment_role",
        "activation", "freshness", "freshness_age_ms", "freshness_bound_ms", "reconciliation",
        "attestation", "source_present", "formula_correct", "authority_closed",
        "runtime_attested", "source_watermark", "consumer_watermark", "build_digest",
        "config_digest", "contract_digest", "binding_digest", "side_effect_census_complete",
        "reason_code", "evidence_refs",
    }
    _closed_object(row, required, "proof")
    return ProofDimensions(
        evidence_id=_text(row["evidence_id"], "proof evidence_id"),
        source_kind=_enum(SourceKind, row["source_kind"], "source_kind"),
        implementation=_enum(Implementation, row["implementation"], "implementation"),
        absence_proven=_bool(row["absence_proven"], "absence_proven"),
        deployment_role=_enum(DeploymentRole, row["deployment_role"], "deployment_role"),
        activation=_enum(Activation, row["activation"], "activation"),
        freshness=_enum(Freshness, row["freshness"], "freshness"),
        freshness_age_ms=_optional_int(row["freshness_age_ms"], "freshness_age_ms"),
        freshness_bound_ms=_optional_int(row["freshness_bound_ms"], "freshness_bound_ms"),
        reconciliation=_enum(Reconciliation, row["reconciliation"], "reconciliation"),
        attestation=_enum(Attestation, row["attestation"], "attestation"),
        source_present=_optional_bool(row["source_present"], "source_present"),
        formula_correct=_optional_bool(row["formula_correct"], "formula_correct"),
        authority_closed=_optional_bool(row["authority_closed"], "authority_closed"),
        runtime_attested=_optional_bool(row["runtime_attested"], "runtime_attested"),
        source_watermark=_optional_text(row["source_watermark"], "source_watermark"),
        consumer_watermark=_optional_text(row["consumer_watermark"], "consumer_watermark"),
        build_digest=_optional_text(row["build_digest"], "build_digest"),
        config_digest=_optional_text(row["config_digest"], "config_digest"),
        contract_digest=_optional_text(row["contract_digest"], "contract_digest"),
        binding_digest=_optional_text(row["binding_digest"], "binding_digest"),
        side_effect_census_complete=_optional_bool(
            row["side_effect_census_complete"], "side_effect_census_complete"
        ),
        reason_code=_optional_text(row["reason_code"], "proof reason_code"),
        evidence_refs=_texts(row["evidence_refs"], "proof evidence_refs"),
    )


def _evaluation(row: Any) -> Evaluation:
    _closed_object(row, {
        "evaluation_id", "candidate_id", "decision_state", "route_revision", "observed_at_us",
        "maturity_deadline_us", "event_posture",
    }, "evaluation")
    return Evaluation(
        evaluation_id=_text(row["evaluation_id"], "evaluation_id"),
        candidate_id=_text(row["candidate_id"], "candidate_id"),
        decision_state=_enum(DecisionState, row["decision_state"], "decision_state"),
        route_revision=_text(row["route_revision"], "route_revision"),
        observed_at_us=_int(row["observed_at_us"], "evaluation observed_at_us"),
        maturity_deadline_us=_int(
            row["maturity_deadline_us"], "evaluation maturity_deadline_us"
        ),
        event_posture=_posture(row["event_posture"], "evaluation event_posture"),
    )


def _cohort(row: Any) -> CandidateCohort:
    _closed_object(row, {
        "cohort_id", "window_start_us", "window_end_us", "source_watermark",
        "source_cut_digest", "complete", "candidate_ids", "zero_proof", "evidence_refs",
    }, "cohort")
    zero_proof = row["zero_proof"]
    if zero_proof is not None and not isinstance(zero_proof, dict):
        raise ScorecardError("cohort zero_proof must be an object or null")
    return CandidateCohort(
        cohort_id=_text(row["cohort_id"], "cohort_id"),
        window_start_us=_int(row["window_start_us"], "cohort window_start_us"),
        window_end_us=_int(row["window_end_us"], "cohort window_end_us"),
        source_watermark=_text(row["source_watermark"], "cohort source_watermark"),
        source_cut_digest=_text(row["source_cut_digest"], "cohort source_cut_digest"),
        complete=_bool(row["complete"], "cohort complete"),
        candidate_ids=_texts(row["candidate_ids"], "cohort candidate_ids"),
        zero_proof=zero_proof,
        evidence_refs=_texts(row["evidence_refs"], "cohort evidence_refs"),
    )


def _terminal(row: Any) -> TerminalRecord:
    _closed_object(row, {
        "terminal_id", "population_instance_id", "kind", "payload_digest", "reason_code",
        "evidence_refs",
    }, "terminal")
    return TerminalRecord(
        terminal_id=_text(row["terminal_id"], "terminal_id"),
        population_instance_id=_text(row["population_instance_id"], "population_instance_id"),
        kind=_enum(TerminalKind, row["kind"], "terminal kind"),
        payload_digest=_text(row["payload_digest"], "terminal payload_digest"),
        reason_code=_optional_text(row["reason_code"], "terminal reason_code"),
        evidence_refs=_texts(row["evidence_refs"], "terminal evidence_refs"),
    )


def _metric(row: Any) -> MetricValue:
    _closed_object(row, {
        "metric_id", "metric_class", "population", "value_type", "value", "unit",
        "availability", "reason_code", "zero_proof", "evidence_refs",
    }, "metric")
    population = None if row["population"] is None else _enum(
        Population, row["population"], "metric population"
    )
    zero_proof = row["zero_proof"]
    if zero_proof is not None and not isinstance(zero_proof, dict):
        raise ScorecardError("metric zero_proof must be an object or null")
    return MetricValue(
        metric_id=_text(row["metric_id"], "metric_id"),
        metric_class=_enum(MetricClass, row["metric_class"], "metric_class"),
        population=population,
        value_type=_text(row["value_type"], "metric value_type"),
        value=_metric_value(row["value"]),
        unit=_text(row["unit"], "metric unit"),
        availability=_enum(Availability, row["availability"], "availability"),
        reason_code=_optional_text(row["reason_code"], "metric reason_code"),
        zero_proof=zero_proof,
        evidence_refs=_texts(row["evidence_refs"], "metric evidence_refs"),
    )


def _closed_object(value: Any, required: set[str], where: str) -> None:
    if not isinstance(value, dict):
        raise ScorecardError(f"{where} must be an object")
    actual = set(value)
    if actual != required:
        raise ScorecardError(
            f"{where} fields mismatch: missing={sorted(required - actual)} "
            f"unknown={sorted(actual - required)}"
        )


def _array(value: Any, where: str) -> list:
    if not isinstance(value, list):
        raise ScorecardError(f"{where} must be an array")
    return value


def _texts(value: Any, where: str) -> tuple[str, ...]:
    return tuple(_text(item, where) for item in _array(value, where))


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ScorecardError(f"{where} must be non-empty canonical text")
    return value


def _optional_text(value: Any, where: str) -> str | None:
    return None if value is None else _text(value, where)


def _int(value: Any, where: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
        or value > 2**63 - 1
    ):
        raise ScorecardError(f"{where} must be a signed-64 non-negative exact integer")
    return value


def _optional_int(value: Any, where: str) -> int | None:
    return None if value is None else _int(value, where)


def _bool(value: Any, where: str) -> bool:
    if type(value) is not bool:
        raise ScorecardError(f"{where} must be an exact boolean")
    return value


def _optional_bool(value: Any, where: str) -> bool | None:
    return None if value is None else _bool(value, where)


def _enum(enum_class, value: Any, where: str):
    try:
        return enum_class(value)
    except (TypeError, ValueError) as exc:
        raise ScorecardError(f"{where} has an invalid closed-enum value: {value!r}") from exc


def _metric_value(value: Any) -> str | int | None:
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, bool) or not isinstance(value, int):
        raise ScorecardError("metric value must be exact int, canonical string, or null")
    return value
