"""Focused falsification tests for the scorecard evidence-resolution law."""

from __future__ import annotations

from dataclasses import replace

import pytest

from triad_origin.scorecard.law import (
    is_registered_reason,
    require_registered_reason,
    resolve_proof,
)
from triad_origin.scorecard.model import (
    Activation,
    Attestation,
    Availability,
    CandidateCohort,
    ComponentBinding,
    DeploymentRole,
    Freshness,
    Implementation,
    MappingStatus,
    MetricClass,
    MetricValue,
    ProofDimensions,
    ProofState,
    Reconciliation,
    ScorecardError,
    SourceKind,
    StageId,
)


_DIGEST = "1" * 64


def _complete_proof(**changes: object) -> ProofDimensions:
    values: dict[str, object] = {
        "evidence_id": "proof:E03:kairos:1",
        "source_kind": SourceKind.AUTHORITATIVE_SOURCE,
        "implementation": Implementation.PRESENT,
        "absence_proven": False,
        "deployment_role": DeploymentRole.ACTIVE_WRITER,
        "activation": Activation.LIVE,
        "freshness": Freshness.FRESH,
        "freshness_age_ms": 100,
        "freshness_bound_ms": 1_000,
        "reconciliation": Reconciliation.RECONCILED,
        "attestation": Attestation.VALID,
        "source_present": True,
        "formula_correct": True,
        "authority_closed": True,
        "runtime_attested": True,
        "source_watermark": "source:100",
        "consumer_watermark": "consumer:100",
        "build_digest": _DIGEST,
        "config_digest": _DIGEST,
        "contract_digest": _DIGEST,
        "binding_digest": _DIGEST,
        "side_effect_census_complete": True,
        "reason_code": None,
        "evidence_refs": ("receipt:proof:1",),
    }
    values.update(changes)
    return ProofDimensions(**values)  # type: ignore[arg-type]


def _zero_proof() -> dict[str, str]:
    return {
        "query_digest": _DIGEST,
        "source_cut_digest": _DIGEST,
        "source_completeness": "COMPLETE",
        "watermark": "source:100",
    }


def test_missing_proof_dimensions_remain_unknown_not_false_or_zero() -> None:
    proof = _complete_proof(
        source_present=None,
        formula_correct=None,
        authority_closed=None,
        runtime_attested=None,
    )

    assert proof.dimensions() == {
        "source_present": None,
        "formula_correct": None,
        "authority_closed": None,
        "runtime_attested": None,
    }
    assert resolve_proof(proof).state is ProofState.UNRECONCILED


def test_missing_metric_is_distinct_from_an_observed_zero() -> None:
    missing = MetricValue(
        metric_id="stage:E03:outputs",
        metric_class=MetricClass.COUNT,
        population=None,
        value_type="INTEGER",
        value=None,
        unit="COUNT",
        availability=Availability.MISSING,
        reason_code="SCORECARD_EVIDENCE_MISSING",
        zero_proof=None,
        evidence_refs=(),
    )
    assert missing.value is None
    assert missing.availability is Availability.MISSING

    with pytest.raises(ScorecardError, match="observed numeric zero requires zero_proof"):
        replace(
            missing,
            value=0,
            availability=Availability.OBSERVED,
            reason_code=None,
        )

    observed_zero = replace(
        missing,
        value=0,
        availability=Availability.OBSERVED,
        reason_code=None,
        zero_proof=_zero_proof(),
        evidence_refs=("query:zero:1",),
    )
    assert observed_zero.value == 0
    assert observed_zero.zero_proof == _zero_proof()


def test_stale_evidence_precedes_mirror_dark_off_and_reconciliation_states() -> None:
    proof = _complete_proof(
        source_kind=SourceKind.MIRROR,
        deployment_role=DeploymentRole.DARK,
        activation=Activation.OFF,
        freshness=Freshness.STALE,
        freshness_age_ms=1_001,
        freshness_bound_ms=1_000,
        reconciliation=Reconciliation.UNRECONCILED,
        attestation=Attestation.INVALID,
        side_effect_census_complete=False,
    )

    resolved = resolve_proof(proof)
    assert resolved.state is ProofState.STALE
    assert resolved.reason_code == "SCORECARD_EVIDENCE_STALE"


@pytest.mark.parametrize("source_kind", [SourceKind.MIRROR, SourceKind.EXPORT])
def test_non_authoritative_projection_cannot_prove_runtime_state(
    source_kind: SourceKind,
) -> None:
    resolved = resolve_proof(_complete_proof(source_kind=source_kind))

    assert resolved.state is ProofState.UNRECONCILED
    assert resolved.reason_code == "SCORECARD_MIRROR_NOT_AUTHORITATIVE"


@pytest.mark.parametrize("census", [None, False])
def test_off_requires_an_explicit_complete_side_effect_census(
    census: bool | None,
) -> None:
    resolved = resolve_proof(
        _complete_proof(
            activation=Activation.OFF,
            side_effect_census_complete=census,
        )
    )

    assert resolved.state is ProofState.UNRECONCILED
    assert resolved.reason_code == "SCORECARD_OFF_CENSUS_INCOMPLETE"


def test_off_is_visible_only_after_complete_proof_and_side_effect_census() -> None:
    resolved = resolve_proof(
        _complete_proof(
            activation=Activation.OFF,
            side_effect_census_complete=True,
        )
    )

    assert resolved.state is ProofState.OFF
    assert resolved.reason_code == "SCORECARD_COMPONENT_OFF"


def test_ratified_component_mapping_requires_evidence() -> None:
    with pytest.raises(ScorecardError, match="RATIFIED component mapping requires evidence"):
        ComponentBinding(
            component_id="kairos",
            stage_id=StageId.E03,
            role="advisory forecast provider",
            mapping_status=MappingStatus.RATIFIED,
            mapping_evidence_refs=(),
            authority_claims=(),
        )

    binding = ComponentBinding(
        component_id="kairos",
        stage_id=StageId.E03,
        role="advisory forecast provider",
        mapping_status=MappingStatus.RATIFIED,
        mapping_evidence_refs=("adr:kairos-e03:1",),
        authority_claims=(),
    )
    assert binding.mapping_evidence_refs == ("adr:kairos-e03:1",)


def test_reason_registry_accepts_local_and_rc4_codes_but_rejects_unknowns() -> None:
    assert is_registered_reason("SCORECARD_EVIDENCE_STALE")
    assert is_registered_reason("PRIVATE_STATE_STALE")
    assert require_registered_reason("PRIVATE_STATE_STALE") == "PRIVATE_STATE_STALE"

    for code in (None, "", "unknown", "UNKNOWN", "UNREGISTERED_REASON"):
        assert not is_registered_reason(code)
        with pytest.raises(ScorecardError, match="unregistered scorecard reason code"):
            require_registered_reason(code)


def test_resolve_proof_refuses_an_unregistered_caller_reason() -> None:
    proof = _complete_proof(reason_code="UNREGISTERED_REASON")

    with pytest.raises(ScorecardError, match="unregistered scorecard reason code"):
        resolve_proof(proof)


def test_not_applicable_activation_cannot_prove_a_present_active_component() -> None:
    resolved = resolve_proof(_complete_proof(activation=Activation.NOT_APPLICABLE))

    assert resolved.state is ProofState.UNRECONCILED


@pytest.mark.parametrize("role", [DeploymentRole.DARK, DeploymentRole.RETIRED])
def test_dark_or_retired_deployment_cannot_claim_live_activation(
    role: DeploymentRole,
) -> None:
    with pytest.raises(ScorecardError, match="cannot claim LIVE activation"):
        _complete_proof(deployment_role=role)


def test_incomplete_empty_cohort_does_not_require_or_allow_zero_proof() -> None:
    cohort = CandidateCohort(
        cohort_id="cohort:incomplete:1",
        window_start_us=0,
        window_end_us=1,
        source_watermark="source:partial:1",
        source_cut_digest=_DIGEST,
        complete=False,
        candidate_ids=(),
        zero_proof=None,
        evidence_refs=("evidence:partial:1",),
    )

    assert not cohort.complete
    with pytest.raises(ScorecardError, match="incomplete empty cohort cannot claim zero proof"):
        replace(cohort, zero_proof=_zero_proof())
