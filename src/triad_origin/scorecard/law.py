"""Canonical topology, state-resolution, and typed-reason law for the scorecard."""

from __future__ import annotations

from dataclasses import dataclass

from ..control import lever_law
from .model import (
    Activation,
    Attestation,
    AuthorityClaim,
    DeploymentRole,
    ExpectedState,
    Freshness,
    Implementation,
    MappingStatus,
    MetricClass,
    ProofDimensions,
    ProofState,
    Reconciliation,
    ScorecardError,
    SourceKind,
    StageId,
    StageRequirement,
)


LOCAL_REASON_CODES = frozenset({
    "SCORECARD_COMPONENT_NOT_IMPLEMENTED",
    "SCORECARD_EVIDENCE_STALE",
    "SCORECARD_EVIDENCE_UNRECONCILED",
    "SCORECARD_COMPONENT_DARK",
    "SCORECARD_COMPONENT_OFF",
    "SCORECARD_PROOF_COMPLETE",
    "SCORECARD_PROOF_INCOMPLETE",
    "SCORECARD_EVIDENCE_MISSING",
    "SCORECARD_MAPPING_UNATTESTED",
    "SCORECARD_MAPPING_UNBOUND",
    "SCORECARD_MAPPING_CONFLICT",
    "SCORECARD_MIRROR_NOT_AUTHORITATIVE",
    "SCORECARD_POSTURE_MISMATCH",
    "SCORECARD_POSTURE_UNPROVEN",
    "SCORECARD_REQUIRED_EDGE_MISSING",
    "SCORECARD_EDGE_FORBIDDEN",
    "SCORECARD_ADVISORY_AUTHORITY_LEAK",
    "SCORECARD_DIRECT_PROVIDER_DEPENDENCY",
    "SCORECARD_WATERMARK_MISSING",
    "SCORECARD_DIGEST_SET_INCOMPLETE",
    "SCORECARD_OFF_CENSUS_INCOMPLETE",
    "SCORECARD_TERMINAL_UNEXPLAINED",
    "SCORECARD_TERMINAL_CONFLICT",
    "SCORECARD_TERMINAL_KIND_INVALID",
    "SCORECARD_ROUTE_MULTIPLICITY_UNDECLARED",
    "SCORECARD_POPULATION_CONTAMINATION",
    "SCORECARD_UNKNOWN_REASON_CODE",
    "SCORECARD_NULL_COERCION_FORBIDDEN",
    "SCORECARD_PERFORMANCE_NOT_MEASURABLE",
    "TOOL_TIMEOUT",
    "NOT_MEASURABLE",
    "ZERO_DENOMINATOR",
    "FEE_LINEAGE_MISSING",
    "INPUT_CUT_MISMATCH",
    "ADVISORY_AUTHORITY_LEAK",
    "POSTURE_MISMATCH",
    "PENDING_WITHIN_GRACE",
    "SCORECARD_ASSERTION_ONLY_INPUT",
    "SCORECARD_COHORT_MISSING",
    "SCORECARD_COHORT_INCOMPLETE",
    "SCORECARD_COHORT_EMPTY",
    "SCORECARD_CANDIDATE_UNEVALUATED",
    "SCORECARD_EVALUATION_ORPHAN",
    "SCORECARD_NO_MATURED_POPULATION",
    "SCORECARD_MANDATORY_METRIC_MISSING",
})


@dataclass(frozen=True)
class ResolvedProof:
    state: ProofState
    reason_code: str


def canonical_stage_requirements() -> tuple[StageRequirement, ...]:
    """Return the full target pipeline without assigning component product names to stages."""
    return (
        StageRequirement(StageId.E00, "main", "Market and raw data", "raw fact ingress", ExpectedState.ACTIVE),
        StageRequirement(StageId.E01, "main", "Canonical market state", "canonical-state producer", ExpectedState.ACTIVE),
        StageRequirement(StageId.E02, "main", "Origin deterministic evidence", "feature/structure/candidate producer", ExpectedState.ACTIVE),
        StageRequirement(StageId.E03, "main", "Forecast provider", "advisory forecast only", ExpectedState.ACTIVE),
        StageRequirement(StageId.E04, "main", "Specialist evidence", "typed advisory specialists only", ExpectedState.ACTIVE),
        StageRequirement(StageId.E05, "main", "Fusion and calibration coordinator", "fan-out/join/calibration only", ExpectedState.ACTIVE),
        StageRequirement(StageId.E06, "main", "Language and knowledge provider", "advisory language/knowledge only", ExpectedState.ACTIVE),
        StageRequirement(StageId.E07, "main", "Decision and policy", "sole admission and policy authority", ExpectedState.ACTIVE),
        StageRequirement(StageId.E08, "main", "Risk and governance", "sole sizing/reservation/allow-deny authority", ExpectedState.ACTIVE),
        StageRequirement(StageId.E09, "new_exposure", "Execution new exposure", "sole venue actor; new exposure path", ExpectedState.OFF),
        StageRequirement(StageId.E09, "reconciliation", "Execution safety path", "cancel/protection/reconciliation/reduction path", ExpectedState.ACTIVE),
        StageRequirement(StageId.E10, "main", "Outcomes and learning", "outcome/attribution/learning authority", ExpectedState.ACTIVE),
    )


# Channel names are semantic and deliberately exclude product names.  Kairos/Logos are mapped by
# the separate component registry, so an asserted product name can never silently become topology
# proof.
REQUIRED_EDGE_KEYS = frozenset({
    (StageId.E00, StageId.E01, "RAW_FACTS"),
    (StageId.E01, StageId.E02, "CANONICAL_STATE"),
    (StageId.E02, StageId.E05, "IMMUTABLE_CANDIDATE_INPUT"),
    (StageId.E05, StageId.E03, "ADVISORY_REQUEST"),
    (StageId.E03, StageId.E05, "FORECAST_ADVISORY"),
    (StageId.E04, StageId.E05, "SPECIALIST_ADVISORY"),
    (StageId.E05, StageId.E06, "ADVISORY_REQUEST"),
    (StageId.E06, StageId.E05, "LANGUAGE_KNOWLEDGE_ADVISORY"),
    (StageId.E05, StageId.E07, "FUSED_CALIBRATED_EVIDENCE"),
    (StageId.E07, StageId.E08, "DECISION"),
    (StageId.E08, StageId.E09, "RISK_AUTHORIZATION"),
    (StageId.E09, StageId.E10, "EXECUTION_FACTS"),
})


ALLOWED_AUTHORITIES_BY_STAGE = {
    StageId.E00: frozenset({AuthorityClaim.RAW_INGRESS}),
    StageId.E01: frozenset({AuthorityClaim.CANONICAL_STATE}),
    StageId.E02: frozenset({AuthorityClaim.ORIGIN_EVIDENCE}),
    StageId.E03: frozenset({AuthorityClaim.ADVISORY_FORECAST}),
    StageId.E04: frozenset({AuthorityClaim.ADVISORY_SPECIALIST}),
    StageId.E05: frozenset({AuthorityClaim.FUSION_CALIBRATION}),
    StageId.E06: frozenset({AuthorityClaim.LANGUAGE_KNOWLEDGE}),
    StageId.E07: frozenset({AuthorityClaim.ADMISSION_POLICY}),
    StageId.E08: frozenset({AuthorityClaim.RISK_ALLOW_DENY}),
    StageId.E09: frozenset({AuthorityClaim.EXECUTION_VENUE}),
    StageId.E10: frozenset({AuthorityClaim.OUTCOMES_LEARNING}),
}


# Diagnostic-v1 profile.  Product names remain in the component registry; metric identities use
# stage roles so an operator assertion cannot silently ratify Kairos↔E03 or Logos↔E06.
MANDATORY_METRIC_SPECS = {
    metric_id: (
        MetricClass.COUNT,
        "INTEGER",
        "COUNT",
        metric_id.startswith(("e08.", "e09.", "e10.")),
        False,
    )
    for metric_id in (
        "e00.raw_events.count",
        "e01.canonical_updates.count",
        "e02.candidates.count",
        "e03.forecast.requests.count",
        "e03.forecast.outputs.count",
        "e03.forecast.refusals.count",
        "e04.specialist.outputs.count",
        "e05.coordinator.inputs.count",
        "e05.coordinator.fused.count",
        "e06.language_knowledge.requests.count",
        "e06.language_knowledge.outputs.count",
        "e06.language_knowledge.refusals.count",
        "e07.decisions.accepted.count",
        "e07.decisions.rejected.count",
        "e08.risk.allowed.count",
        "e08.risk.denied.count",
        "e09.execution.commands.count",
        "e09.execution.fills.count",
        "e09.execution.unknown_submit.count",
        "e10.outcomes.complete.count",
        "e10.outcomes.unresolved.count",
    )
}


MANDATORY_METRIC_SPECS.update({
    metric_id: (
        MetricClass.HEALTH,
        "DECIMAL",
        "MILLISECOND",
        metric_id.startswith(("e08.", "e09.")),
        False,
    )
    for metric_id in (
        "e00.data_freshness.p95_ms",
        "e03.forecast.latency.p95_ms",
        "e05.coordinator.latency.p95_ms",
        "e06.language_knowledge.latency.p95_ms",
        "e07.decision.latency.p95_ms",
        "e08.risk.latency.p95_ms",
        "e09.execution.ack_latency.p95_ms",
    )
})


OPTIONAL_METRIC_SPECS = {
    "e09.execution.fill_rate": (MetricClass.ECONOMIC, "DECIMAL", "RATIO", True, False),
    "e09.execution.slippage.mean_bps": (MetricClass.ECONOMIC, "DECIMAL", "BPS", True, True),
    "e10.outcomes.net_pnl.quote": (MetricClass.ECONOMIC, "DECIMAL", "QUOTE", True, True),
    "e10.outcomes.net_r_multiple": (
        MetricClass.ECONOMIC, "DECIMAL", "R_MULTIPLE", True, True
    ),
    "e10.outcomes.win_rate": (MetricClass.ECONOMIC, "DECIMAL", "RATIO", True, False),
    "e10.outcomes.profit_factor": (MetricClass.ECONOMIC, "DECIMAL", "RATIO", True, False),
    "e10.outcomes.max_drawdown.quote": (
        MetricClass.ECONOMIC, "DECIMAL", "QUOTE", True, False
    ),
}


METRIC_SPECS = {**MANDATORY_METRIC_SPECS, **OPTIONAL_METRIC_SPECS}


def is_registered_reason(code: str | None) -> bool:
    if not isinstance(code, str) or not code or code.lower() == "unknown":
        return False
    if code in LOCAL_REASON_CODES:
        return True
    try:
        lever_law.refuse(code)
    except lever_law.LeverLawError:
        return False
    return True


def require_registered_reason(code: str | None) -> str:
    if not is_registered_reason(code):
        raise ScorecardError(f"unregistered scorecard reason code: {code!r}")
    return code


def resolve_proof(proof: ProofDimensions) -> ResolvedProof:
    """Resolve a visible proof state using the fail-closed precedence.

    Silence never proves absence, no activity never proves OFF, a mirror never proves current
    writer/control state, and a stale DARK/OFF assertion remains STALE.
    """
    if proof.reason_code is not None:
        require_registered_reason(proof.reason_code)

    if proof.freshness is Freshness.STALE:
        return ResolvedProof(ProofState.STALE, "SCORECARD_EVIDENCE_STALE")

    if proof.freshness is Freshness.UNKNOWN:
        return ResolvedProof(ProofState.UNRECONCILED, "SCORECARD_EVIDENCE_UNRECONCILED")

    if proof.source_kind is not SourceKind.AUTHORITATIVE_SOURCE:
        return ResolvedProof(ProofState.UNRECONCILED, "SCORECARD_MIRROR_NOT_AUTHORITATIVE")

    if (
        proof.reconciliation is Reconciliation.UNRECONCILED
        or proof.attestation is not Attestation.VALID
    ):
        return ResolvedProof(ProofState.UNRECONCILED, "SCORECARD_EVIDENCE_UNRECONCILED")

    if proof.implementation is Implementation.ABSENT and proof.absence_proven:
        if not proof.evidence_refs or proof.side_effect_census_complete is not True:
            return ResolvedProof(ProofState.UNRECONCILED, "SCORECARD_PROOF_INCOMPLETE")
        return ResolvedProof(ProofState.NOT_IMPLEMENTED, "SCORECARD_COMPONENT_NOT_IMPLEMENTED")

    if (
        proof.implementation is Implementation.UNKNOWN
        or proof.deployment_role in {DeploymentRole.MIRROR, DeploymentRole.REPLICA, DeploymentRole.UNKNOWN}
    ):
        return ResolvedProof(ProofState.UNRECONCILED, "SCORECARD_EVIDENCE_UNRECONCILED")

    if proof.deployment_role in {DeploymentRole.DARK, DeploymentRole.RETIRED}:
        return ResolvedProof(ProofState.DARK, "SCORECARD_COMPONENT_DARK")

    if proof.activation is Activation.OFF:
        if proof.side_effect_census_complete is not True:
            return ResolvedProof(ProofState.UNRECONCILED, "SCORECARD_OFF_CENSUS_INCOMPLETE")
        if not _complete_proof(proof):
            return ResolvedProof(ProofState.UNRECONCILED, "SCORECARD_PROOF_INCOMPLETE")
        return ResolvedProof(ProofState.OFF, "SCORECARD_COMPONENT_OFF")

    if proof.activation is Activation.UNVERIFIED:
        return ResolvedProof(ProofState.UNRECONCILED, "SCORECARD_EVIDENCE_UNRECONCILED")

    if proof.activation is not Activation.LIVE:
        return ResolvedProof(ProofState.UNRECONCILED, "SCORECARD_EVIDENCE_UNRECONCILED")

    if not _complete_proof(proof):
        if proof.source_watermark is None or proof.consumer_watermark is None:
            return ResolvedProof(ProofState.UNRECONCILED, "SCORECARD_WATERMARK_MISSING")
        if not _digests_complete(proof):
            return ResolvedProof(ProofState.UNRECONCILED, "SCORECARD_DIGEST_SET_INCOMPLETE")
        return ResolvedProof(ProofState.UNRECONCILED, "SCORECARD_PROOF_INCOMPLETE")

    return ResolvedProof(ProofState.PROVEN, "SCORECARD_PROOF_COMPLETE")


def mapping_allows_full(status: MappingStatus) -> bool:
    return status is MappingStatus.RATIFIED


def _complete_proof(proof: ProofDimensions) -> bool:
    return (
        proof.implementation is Implementation.PRESENT
        and proof.source_present is True
        and proof.formula_correct is True
        and proof.authority_closed is True
        and proof.runtime_attested is True
        and proof.freshness is Freshness.FRESH
        and proof.reconciliation in {Reconciliation.RECONCILED, Reconciliation.NOT_APPLICABLE}
        and proof.attestation is Attestation.VALID
        and proof.source_watermark is not None
        and proof.consumer_watermark is not None
        and _digests_complete(proof)
        and bool(proof.evidence_refs)
    )


def _digests_complete(proof: ProofDimensions) -> bool:
    return all((proof.build_digest, proof.config_digest, proof.contract_digest, proof.binding_digest))
