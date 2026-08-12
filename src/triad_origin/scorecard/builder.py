"""Pure full-pipeline scorecard projector and fail-publication gate."""

from __future__ import annotations

from collections import defaultdict

from ..canonical import canonical_json, sha256_hex
from .conservation import derive_routes, reconcile_terminals
from .law import (
    ALLOWED_AUTHORITIES_BY_STAGE,
    MANDATORY_METRIC_SPECS,
    METRIC_SPECS,
    REQUIRED_EDGE_KEYS,
    canonical_stage_requirements,
    is_registered_reason,
    mapping_allows_full,
    resolve_proof,
)
from .model import (
    CandidateCohort,
    ComponentBinding,
    EdgeObservation,
    Evaluation,
    ExpectedState,
    MappingStatus,
    MetricValue,
    Population,
    Posture,
    PostureObservation,
    ProofState,
    PublicationOutcome,
    ScorecardError,
    StageId,
    StageObservation,
    TerminalRecord,
)


SCORECARD_SCHEMA = "triad.origin.full_pipeline_scorecard.diagnostic.v1"
SCORECARD_CLAIM = "DIAGNOSTIC_READ_ONLY_NO_AUTHORITY"
BASELINE_POSTURE = Posture("OFF", "OFF", "OFF", "LIVE")


def build_scorecard(
    *,
    report_id: str,
    as_of_us: int,
    components: tuple[ComponentBinding, ...],
    posture: PostureObservation,
    stage_observations: tuple[StageObservation, ...],
    edge_observations: tuple[EdgeObservation, ...],
    evaluations: tuple[Evaluation, ...],
    terminals: tuple[TerminalRecord, ...],
    metrics: tuple[MetricValue, ...],
    candidate_cohort: CandidateCohort | None = None,
) -> dict:
    """Build a deterministic artifact even when publication must be withheld.

    ``FULL`` is evidence completeness, not activation authority or profitability.  This function
    has no write/control seam and cannot change the posture it reports.
    """
    _validate_report_identity(report_id, as_of_us)
    component_issues, component_status_flags = _validate_components(components)
    topology_issues, edge_status_flags, edge_cells = _build_edge_cells(edge_observations)
    stage_issues, stage_status_flags, stage_cells = _build_stage_cells(
        components, stage_observations
    )
    posture_state, posture_reason = _resolve_posture(posture)

    routes = derive_routes(evaluations, as_of_us)
    conservation = reconcile_terminals(evaluations, routes, terminals)
    metric_issues, metric_status_flags = _validate_metrics(metrics, candidate_cohort)
    cohort_issues, cohort_status_flags = _validate_candidate_cohort(
        candidate_cohort, evaluations, as_of_us
    )

    blockers: list[dict[str, str]] = []
    status_flags: list[dict[str, str]] = []
    blockers.extend(component_issues)
    blockers.extend(topology_issues)
    blockers.extend(stage_issues)
    blockers.extend(cohort_issues)
    blockers.extend(metric_issues)
    # Diagnostic v1 parses supplied assertions but does not authenticate cross-repository
    # envelopes.  It therefore cannot issue an evidence-completeness FULL publication.
    status_flags.append({
        "code": "SCORECARD_ASSERTION_ONLY_INPUT",
        "subject": "diagnostic.v1 has no authenticated evidence-envelope verifier",
    })
    status_flags.extend(component_status_flags)
    status_flags.extend(edge_status_flags)
    status_flags.extend(stage_status_flags)
    status_flags.extend(metric_status_flags)
    status_flags.extend(cohort_status_flags)

    if posture_state is not ProofState.PROVEN:
        blockers.append({
            "code": posture_reason,
            "subject": "four_plane_posture",
        })
    if not conservation.reconciled:
        if conservation.unexplained_count:
            blockers.append({
                "code": "SCORECARD_TERMINAL_UNEXPLAINED",
                "subject": f"{conservation.unexplained_count} matured population routes",
            })
        if conservation.conflict_count or conservation.orphan_terminal_count:
            blockers.append({
                "code": "SCORECARD_TERMINAL_CONFLICT",
                "subject": (
                    f"{conservation.conflict_count} conflicts; "
                    f"{conservation.orphan_terminal_count} orphans"
                ),
            })
        if conservation.unknown_submit_population_instance_ids:
            blockers.append({
                "code": "UNKNOWN_SUBMIT_UNRECONCILED",
                "subject": (
                    f"{len(conservation.unknown_submit_population_instance_ids)} population routes"
                ),
            })
        if not conservation.multiplicity_explicit:
            blockers.append({
                "code": "SCORECARD_ROUTE_MULTIPLICITY_UNDECLARED",
                "subject": "candidate-to-evaluation cardinality",
            })
    if conservation.pending_count:
        status_flags.append({
            "code": "PENDING_WITHIN_GRACE",
            "subject": f"{conservation.pending_count} population routes",
        })
    if not any(route.matured for route in routes):
        status_flags.append({
            "code": "SCORECARD_NO_MATURED_POPULATION",
            "subject": "no matured population route is available",
        })

    blockers = _dedupe_findings(blockers)
    status_flags = _dedupe_findings(status_flags)
    if blockers:
        outcome = PublicationOutcome.WITHHELD
    elif status_flags:
        outcome = PublicationOutcome.STATUS_ONLY
    else:
        outcome = PublicationOutcome.FULL

    report = {
        "schema": SCORECARD_SCHEMA,
        "report_id": report_id,
        "as_of_us": as_of_us,
        "claim": SCORECARD_CLAIM,
        "authority_effect": "NONE",
        "evidence_trust": "UNAUTHENTICATED_ASSERTIONS",
        "desired_posture": posture.desired.to_dict(),
        "observed_posture": posture.observed.to_dict() if posture.observed is not None else None,
        "posture_proof": {
            "state": posture_state.value,
            "reason_code": posture_reason,
            "freshness": posture.freshness.value,
            "reconciliation": posture.reconciliation.value,
            "attestation": posture.attestation.value,
            "side_effect_census_complete": posture.side_effect_census_complete,
            "evidence_refs": list(posture.evidence_refs),
        },
        "components": [_component_dict(component) for component in sorted(
            components, key=lambda item: (item.stage_id.value, item.component_id)
        )],
        "candidate_cohort": _cohort_dict(candidate_cohort),
        "stage_cells": stage_cells,
        "edge_cells": edge_cells,
        "conservation": conservation.to_dict(),
        "routes": [_route_dict(route) for route in routes],
        "terminals": [_terminal_dict(record) for record in sorted(
            terminals, key=lambda item: (item.population_instance_id, item.terminal_id)
        )],
        "metrics": [_metric_dict(metric) for metric in sorted(
            metrics, key=lambda item: (
                item.metric_id,
                item.population.value if item.population is not None else "",
            )
        )],
        "candidate_traces": _candidate_traces(evaluations, routes, terminals),
        "publication": {
            "outcome": outcome.value,
            "blockers": blockers,
            "status_flags": status_flags,
            "merge_authority": "NONE",
            "deployment_authority": "NONE",
            "activation_authority": "NONE",
        },
    }
    report["content_digest"] = sha256_hex(canonical_json(report))
    return report


def _validate_report_identity(report_id: str, as_of_us: int) -> None:
    if not isinstance(report_id, str) or not report_id or report_id.strip() != report_id:
        raise ScorecardError("report_id must be non-empty canonical text")
    if isinstance(as_of_us, bool) or not isinstance(as_of_us, int) or as_of_us < 0:
        raise ScorecardError("as_of_us must be a non-negative exact integer")


def _validate_components(
    components: tuple[ComponentBinding, ...],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    blockers: list[dict[str, str]] = []
    flags: list[dict[str, str]] = []
    ids: set[str] = set()
    authority_owners: dict[object, str] = {}
    stages: dict[StageId, list[ComponentBinding]] = defaultdict(list)
    for component in components:
        if component.component_id in ids:
            raise ScorecardError(f"duplicate component_id: {component.component_id}")
        ids.add(component.component_id)
        stages[component.stage_id].append(component)
        disallowed = set(component.authority_claims) - ALLOWED_AUTHORITIES_BY_STAGE[
            component.stage_id
        ]
        if disallowed:
            names = ",".join(sorted(item.value for item in disallowed))
            raise ScorecardError(
                f"component {component.component_id} has authority outside {component.stage_id.value}: "
                f"{names}"
            )
        for claim in component.authority_claims:
            prior_owner = authority_owners.get(claim)
            if prior_owner is not None:
                raise ScorecardError(
                    f"authority claim {claim.value} has multiple components: "
                    f"{prior_owner}, {component.component_id}"
                )
            authority_owners[claim] = component.component_id
        if component.mapping_status is MappingStatus.CONFLICT:
            blockers.append({"code": "SCORECARD_MAPPING_CONFLICT", "subject": component.component_id})
        elif component.mapping_status is MappingStatus.UNBOUND:
            blockers.append({"code": "SCORECARD_MAPPING_UNBOUND", "subject": component.component_id})
        elif not mapping_allows_full(component.mapping_status):
            flags.append({
                "code": "SCORECARD_MAPPING_UNATTESTED",
                "subject": component.component_id,
            })
    for stage in StageId:
        if not stages[stage]:
            blockers.append({"code": "SCORECARD_MAPPING_UNBOUND", "subject": stage.value})
    return blockers, flags


def _build_stage_cells(
    components: tuple[ComponentBinding, ...],
    observations: tuple[StageObservation, ...],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict]]:
    blockers: list[dict[str, str]] = []
    flags: list[dict[str, str]] = []
    component_by_id = {component.component_id: component for component in components}
    obs_by_key: dict[tuple[StageId, str], StageObservation] = {}
    for observation in observations:
        key = (observation.stage_id, observation.path_id)
        if key in obs_by_key:
            raise ScorecardError(f"duplicate stage observation: {key[0].value}/{key[1]}")
        obs_by_key[key] = observation

    cells: list[dict] = []
    for requirement in canonical_stage_requirements():
        key = (requirement.stage_id, requirement.path_id)
        observation = obs_by_key.get(key)
        subject = f"{requirement.stage_id.value}/{requirement.path_id}"
        if observation is None:
            blockers.append({"code": "SCORECARD_EVIDENCE_MISSING", "subject": subject})
            cells.append({
                "stage": requirement.stage_id.value,
                "path": requirement.path_id,
                "name": requirement.name,
                "authority": requirement.authority,
                "expected_state": requirement.expected_state.value,
                "component_id": None,
                "state": ProofState.UNRECONCILED.value,
                "reason_code": "SCORECARD_EVIDENCE_MISSING",
                "dimensions": {
                    "source_present": None,
                    "formula_correct": None,
                    "authority_closed": None,
                    "runtime_attested": None,
                },
                "proof": None,
            })
            continue
        binding = component_by_id.get(observation.component_id)
        if binding is None or binding.stage_id is not observation.stage_id:
            blockers.append({"code": "SCORECARD_MAPPING_CONFLICT", "subject": subject})
        resolved = resolve_proof(observation.proof)
        if resolved.state in {ProofState.STALE, ProofState.UNRECONCILED}:
            blockers.append({"code": resolved.reason_code, "subject": subject})
        elif requirement.expected_state is ExpectedState.ACTIVE:
            if resolved.state is not ProofState.PROVEN:
                flags.append({"code": resolved.reason_code, "subject": subject})
        elif resolved.state is not ProofState.OFF:
            if resolved.state is ProofState.PROVEN:
                blockers.append({"code": "POSTURE_MISMATCH", "subject": subject})
            else:
                flags.append({"code": resolved.reason_code, "subject": subject})
        cells.append({
            "stage": requirement.stage_id.value,
            "path": requirement.path_id,
            "name": requirement.name,
            "authority": requirement.authority,
            "expected_state": requirement.expected_state.value,
            "component_id": observation.component_id,
            "state": resolved.state.value,
            "reason_code": resolved.reason_code,
            "dimensions": observation.proof.dimensions(),
            "proof": _proof_dict(observation.proof),
        })

    unexpected = sorted(
        f"{stage.value}/{path}" for stage, path in set(obs_by_key) - {
            (item.stage_id, item.path_id) for item in canonical_stage_requirements()
        }
    )
    if unexpected:
        raise ScorecardError(f"stage observations outside the closed catalog: {unexpected}")
    return blockers, flags, cells


def _build_edge_cells(
    observations: tuple[EdgeObservation, ...],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict]]:
    blockers: list[dict[str, str]] = []
    flags: list[dict[str, str]] = []
    by_key: dict[tuple[StageId, StageId, str], EdgeObservation] = {}
    for observation in observations:
        if observation.key in by_key:
            raise ScorecardError(
                f"duplicate edge: {observation.source_stage.value}->{observation.target_stage.value}"
            )
        by_key[observation.key] = observation

    unexpected_keys = set(by_key) - REQUIRED_EDGE_KEYS
    if unexpected_keys:
        rendered = sorted(
            f"{source.value}->{target.value}:{channel}"
            for source, target, channel in unexpected_keys
        )
        raise ScorecardError(f"edges outside the closed topology catalog: {rendered}")

    for source, target, channel in sorted(
        REQUIRED_EDGE_KEYS - set(by_key), key=lambda item: (item[0].value, item[1].value, item[2])
    ):
        blockers.append({
            "code": "SCORECARD_REQUIRED_EDGE_MISSING",
            "subject": f"{source.value}->{target.value}:{channel}",
        })

    for key in by_key:
        source, target, channel = key
        if {source, target} == {StageId.E03, StageId.E06}:
            blockers.append({
                "code": "SCORECARD_DIRECT_PROVIDER_DEPENDENCY",
                "subject": f"{source.value}->{target.value}:{channel}",
            })
        if source in {StageId.E03, StageId.E05, StageId.E06} and target in {
            StageId.E08, StageId.E09, StageId.E10,
        }:
            blockers.append({
                "code": "SCORECARD_EDGE_FORBIDDEN",
                "subject": f"{source.value}->{target.value}:{channel}",
            })
        if source is StageId.E02 and target in {StageId.E03, StageId.E06}:
            blockers.append({
                "code": "SCORECARD_EDGE_FORBIDDEN",
                "subject": f"{source.value}->{target.value}:{channel}",
            })

    cells: list[dict] = []
    for key, observation in sorted(
        by_key.items(), key=lambda item: (item[0][0].value, item[0][1].value, item[0][2])
    ):
        resolved = resolve_proof(observation.proof)
        subject = f"{key[0].value}->{key[1].value}:{key[2]}"
        if resolved.state in {ProofState.STALE, ProofState.UNRECONCILED}:
            blockers.append({"code": resolved.reason_code, "subject": subject})
        elif resolved.state is not ProofState.PROVEN:
            flags.append({"code": resolved.reason_code, "subject": subject})
        cells.append({
            "source_stage": key[0].value,
            "target_stage": key[1].value,
            "channel": key[2],
            "state": resolved.state.value,
            "reason_code": resolved.reason_code,
            "dimensions": observation.proof.dimensions(),
            "proof": _proof_dict(observation.proof),
        })
    return blockers, flags, cells


def _resolve_posture(observation: PostureObservation) -> tuple[ProofState, str]:
    if observation.freshness.value == "STALE":
        return ProofState.STALE, "SCORECARD_EVIDENCE_STALE"
    if observation.freshness.value != "FRESH":
        return ProofState.UNRECONCILED, "SCORECARD_POSTURE_UNPROVEN"
    if (
        observation.observed is None
        or observation.reconciliation.value != "RECONCILED"
        or observation.attestation.value != "VALID"
        or not observation.evidence_refs
        or observation.side_effect_census_complete is not True
    ):
        return ProofState.UNRECONCILED, "SCORECARD_POSTURE_UNPROVEN"
    if observation.desired != observation.observed:
        return ProofState.UNRECONCILED, "SCORECARD_POSTURE_MISMATCH"
    if observation.desired != BASELINE_POSTURE:
        return ProofState.UNRECONCILED, "SCORECARD_POSTURE_MISMATCH"
    return ProofState.PROVEN, "SCORECARD_PROOF_COMPLETE"


def _validate_candidate_cohort(
    cohort: CandidateCohort | None,
    evaluations: tuple[Evaluation, ...],
    as_of_us: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    blockers: list[dict[str, str]] = []
    flags: list[dict[str, str]] = []
    if cohort is None:
        blockers.append({"code": "SCORECARD_COHORT_MISSING", "subject": "E02 candidate cohort"})
        return blockers, flags
    if cohort.window_end_us > as_of_us:
        raise ScorecardError("candidate cohort window cannot end in the report future")
    if not cohort.complete:
        blockers.append({
            "code": "SCORECARD_COHORT_INCOMPLETE",
            "subject": cohort.cohort_id,
        })
    cohort_ids = set(cohort.candidate_ids)
    evaluation_ids = {evaluation.candidate_id for evaluation in evaluations}
    for candidate_id in sorted(cohort_ids - evaluation_ids):
        blockers.append({
            "code": "SCORECARD_CANDIDATE_UNEVALUATED",
            "subject": candidate_id,
        })
    for candidate_id in sorted(evaluation_ids - cohort_ids):
        blockers.append({
            "code": "SCORECARD_EVALUATION_ORPHAN",
            "subject": candidate_id,
        })
    if not cohort.candidate_ids:
        flags.append({"code": "SCORECARD_COHORT_EMPTY", "subject": cohort.cohort_id})
    return blockers, flags


def _validate_metrics(
    metrics: tuple[MetricValue, ...],
    cohort: CandidateCohort | None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    blockers: list[dict[str, str]] = []
    flags: list[dict[str, str]] = []
    identities: set[tuple[str, str]] = set()
    for metric in metrics:
        identity = (
            metric.metric_id,
            metric.population.value if metric.population is not None else "NO_POPULATION",
        )
        if identity in identities:
            raise ScorecardError(f"duplicate metric identity: {identity}")
        identities.add(identity)
        specification = METRIC_SPECS.get(metric.metric_id)
        if specification is None:
            raise ScorecardError(f"metric_id is outside the closed diagnostic profile: {metric.metric_id}")
        (
            expected_class,
            expected_type,
            expected_unit,
            population_required,
            signed_allowed,
        ) = specification
        if (
            metric.metric_class is not expected_class
            or metric.value_type != expected_type
            or metric.unit != expected_unit
            or population_required != (metric.population is not None)
        ):
            raise ScorecardError(f"metric shape conflicts with profile: {metric.metric_id}")
        if (
            metric.value_type == "DECIMAL"
            and isinstance(metric.value, str)
            and metric.value.startswith("-")
            and not signed_allowed
        ):
            raise ScorecardError(f"negative metric forbidden by profile: {metric.metric_id}")
        if metric.reason_code is not None and not is_registered_reason(metric.reason_code):
            raise ScorecardError(f"unregistered metric reason: {metric.reason_code}")
        if metric.value is None:
            flags.append({
                "code": "SCORECARD_PERFORMANCE_NOT_MEASURABLE",
                "subject": f"{identity[0]}/{identity[1]}:{metric.reason_code}",
            })
        if (
            metric.metric_id == "e02.candidates.count"
            and cohort is not None
            and metric.value is not None
            and metric.value != len(cohort.candidate_ids)
        ):
            blockers.append({
                "code": "INPUT_CUT_MISMATCH",
                "subject": "e02.candidates.count does not equal cohort candidate_ids",
            })
    mandatory_identities: set[tuple[str, str]] = set()
    for metric_id, specification in MANDATORY_METRIC_SPECS.items():
        if specification[3]:
            mandatory_identities.update(
                (metric_id, population.value) for population in Population
            )
        else:
            mandatory_identities.add((metric_id, "NO_POPULATION"))
    for metric_id, population in sorted(mandatory_identities - identities):
        flags.append({
            "code": "SCORECARD_MANDATORY_METRIC_MISSING",
            "subject": f"{metric_id}/{population}",
        })
    return blockers, flags


def _proof_dict(proof) -> dict:
    return {
        "evidence_id": proof.evidence_id,
        "source_kind": proof.source_kind.value,
        "implementation": proof.implementation.value,
        "absence_proven": proof.absence_proven,
        "deployment_role": proof.deployment_role.value,
        "activation": proof.activation.value,
        "freshness": proof.freshness.value,
        "freshness_age_ms": proof.freshness_age_ms,
        "freshness_bound_ms": proof.freshness_bound_ms,
        "reconciliation": proof.reconciliation.value,
        "attestation": proof.attestation.value,
        "source_watermark": proof.source_watermark,
        "consumer_watermark": proof.consumer_watermark,
        "build_digest": proof.build_digest,
        "config_digest": proof.config_digest,
        "contract_digest": proof.contract_digest,
        "binding_digest": proof.binding_digest,
        "side_effect_census_complete": proof.side_effect_census_complete,
        "input_reason_code": proof.reason_code,
        "evidence_refs": list(proof.evidence_refs),
    }


def _component_dict(component: ComponentBinding) -> dict:
    return {
        "component_id": component.component_id,
        "stage": component.stage_id.value,
        "role": component.role,
        "mapping_status": component.mapping_status.value,
        "mapping_evidence_refs": list(component.mapping_evidence_refs),
        "authority_claims": [claim.value for claim in component.authority_claims],
    }


def _cohort_dict(cohort: CandidateCohort | None) -> dict | None:
    if cohort is None:
        return None
    return {
        "cohort_id": cohort.cohort_id,
        "window_start_us": cohort.window_start_us,
        "window_end_us": cohort.window_end_us,
        "source_watermark": cohort.source_watermark,
        "source_cut_digest": cohort.source_cut_digest,
        "complete": cohort.complete,
        "candidate_ids": list(cohort.candidate_ids),
        "zero_proof": dict(cohort.zero_proof) if cohort.zero_proof is not None else None,
        "evidence_refs": list(cohort.evidence_refs),
    }


def _route_dict(route) -> dict:
    return {
        "population_instance_id": route.population_instance_id,
        "evaluation_id": route.evaluation_id,
        "candidate_id": route.candidate_id,
        "population": route.population.value,
        "allowed_terminals": [kind.value for kind in route.allowed_terminals],
        "matured": route.matured,
    }


def _terminal_dict(record: TerminalRecord) -> dict:
    return {
        "terminal_id": record.terminal_id,
        "population_instance_id": record.population_instance_id,
        "kind": record.kind.value,
        "payload_digest": record.payload_digest,
        "reason_code": record.reason_code,
        "evidence_refs": list(record.evidence_refs),
    }


def _metric_dict(metric: MetricValue) -> dict:
    return {
        "metric_id": metric.metric_id,
        "metric_class": metric.metric_class.value,
        "population": metric.population.value if metric.population is not None else None,
        "value_type": metric.value_type,
        "value": metric.value,
        "unit": metric.unit,
        "availability": metric.availability.value,
        "reason_code": metric.reason_code,
        "zero_proof": dict(metric.zero_proof) if metric.zero_proof is not None else None,
        "evidence_refs": list(metric.evidence_refs),
    }


def _candidate_traces(evaluations, routes, terminals) -> list[dict]:
    evaluations_by_candidate: dict[str, list] = defaultdict(list)
    routes_by_evaluation: dict[str, list] = defaultdict(list)
    terminal_by_route: dict[str, list] = defaultdict(list)
    for evaluation in evaluations:
        evaluations_by_candidate[evaluation.candidate_id].append(evaluation)
    for route in routes:
        routes_by_evaluation[route.evaluation_id].append(route)
    for terminal in terminals:
        terminal_by_route[terminal.population_instance_id].append(terminal)
    traces: list[dict] = []
    for candidate_id, candidate_evaluations in sorted(evaluations_by_candidate.items()):
        evaluation_rows: list[dict] = []
        for evaluation in sorted(candidate_evaluations, key=lambda item: item.evaluation_id):
            route_rows = []
            for route in sorted(
                routes_by_evaluation[evaluation.evaluation_id],
                key=lambda item: item.population_instance_id,
            ):
                route_rows.append({
                    "population_instance_id": route.population_instance_id,
                    "population": route.population.value,
                    "terminals": [
                        _terminal_dict(item) for item in sorted(
                            terminal_by_route[route.population_instance_id],
                            key=lambda terminal: terminal.terminal_id,
                        )
                    ],
                })
            evaluation_rows.append({
                "evaluation_id": evaluation.evaluation_id,
                "decision_state": evaluation.decision_state.value,
                "route_revision": evaluation.route_revision,
                "observed_at_us": evaluation.observed_at_us,
                "maturity_deadline_us": evaluation.maturity_deadline_us,
                "event_posture": evaluation.event_posture.to_dict(),
                "matured": bool(route_rows) and all(
                    route.matured for route in routes_by_evaluation[evaluation.evaluation_id]
                ),
                "routes": route_rows,
            })
        traces.append({"candidate_id": candidate_id, "evaluations": evaluation_rows})
    return traces


def _dedupe_findings(findings: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {"code": code, "subject": subject}
        for code, subject in sorted({(item["code"], item["subject"]) for item in findings})
    ]
