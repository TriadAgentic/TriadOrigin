"""Public-codec tests for scorecard publication and closed-topology law."""

from __future__ import annotations

from copy import deepcopy

import pytest

from triad_origin.scorecard import (
    INPUT_SCHEMA,
    build_scorecard_from_dict,
    verify_report_digest,
)
from triad_origin.scorecard.model import ScorecardError


_DIGEST = "1" * 64
_TERMINAL_DIGEST = "2" * 64

_COMPONENTS = (
    ("market-source", "E00", "raw market fact producer"),
    ("canonical-state", "E01", "canonical finalized state producer"),
    ("origin", "E02", "deterministic feature structure and candidate producer"),
    ("kairos", "E03", "advisory forecast provider"),
    ("specialists", "E04", "typed advisory specialist provider"),
    ("intelligence-coordinator", "E05", "advisory fusion and calibration coordinator"),
    ("logos", "E06", "advisory language and knowledge provider"),
    ("decision", "E07", "sole admission and policy authority"),
    ("risk", "E08", "sole sizing reservation and allow deny authority"),
    ("executor", "E09", "sole venue actor and reconciliation owner"),
    ("outcomes", "E10", "outcome attribution and learning authority"),
)

_STAGES = (
    ("E00", "market-source", "main", "LIVE"),
    ("E01", "canonical-state", "main", "LIVE"),
    ("E02", "origin", "main", "LIVE"),
    ("E03", "kairos", "main", "LIVE"),
    ("E04", "specialists", "main", "LIVE"),
    ("E05", "intelligence-coordinator", "main", "LIVE"),
    ("E06", "logos", "main", "LIVE"),
    ("E07", "decision", "main", "LIVE"),
    ("E08", "risk", "main", "LIVE"),
    ("E09", "executor", "new_exposure", "OFF"),
    ("E09", "executor", "reconciliation", "LIVE"),
    ("E10", "outcomes", "main", "LIVE"),
)

_EDGES = (
    ("E00", "E01", "RAW_FACTS"),
    ("E01", "E02", "CANONICAL_STATE"),
    ("E02", "E05", "IMMUTABLE_CANDIDATE_INPUT"),
    ("E05", "E03", "ADVISORY_REQUEST"),
    ("E03", "E05", "FORECAST_ADVISORY"),
    ("E04", "E05", "SPECIALIST_ADVISORY"),
    ("E05", "E06", "ADVISORY_REQUEST"),
    ("E06", "E05", "LANGUAGE_KNOWLEDGE_ADVISORY"),
    ("E05", "E07", "FUSED_CALIBRATED_EVIDENCE"),
    ("E07", "E08", "DECISION"),
    ("E08", "E09", "RISK_AUTHORIZATION"),
    ("E09", "E10", "EXECUTION_FACTS"),
)


def _proof(evidence_id: str, *, activation: str = "LIVE") -> dict:
    return {
        "evidence_id": evidence_id,
        "source_kind": "AUTHORITATIVE_SOURCE",
        "implementation": "PRESENT",
        "absence_proven": False,
        "deployment_role": "ACTIVE_WRITER",
        "activation": activation,
        "freshness": "FRESH",
        "freshness_age_ms": 100,
        "freshness_bound_ms": 1_000,
        "reconciliation": "RECONCILED",
        "attestation": "VALID",
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
        "evidence_refs": [f"receipt:{evidence_id}"],
    }


def _zero_proof() -> dict:
    return {
        "query_digest": _DIGEST,
        "source_cut_digest": _DIGEST,
        "source_completeness": "COMPLETE",
        "watermark": "source:100",
    }


def _unreconciled_document() -> dict:
    posture = {
        "venue_environment": "OFF",
        "venue_activation": "OFF",
        "paper_activation": "OFF",
        "shadow_activation": "LIVE",
    }
    return {
        "schema": INPUT_SCHEMA,
        "report_id": "scorecard:test:1",
        "as_of_us": 1_786_500_000_000_000,
        "components": [
            {
                "component_id": component_id,
                "stage": stage,
                "role": role,
                "mapping_status": "RATIFIED",
                "mapping_evidence_refs": [f"adr:{component_id}:1"],
                "authority_claims": [],
            }
            for component_id, stage, role in _COMPONENTS
        ],
        "posture": {
            "desired": deepcopy(posture),
            "observed": deepcopy(posture),
            "freshness": "FRESH",
            "reconciliation": "RECONCILED",
            "attestation": "VALID",
            "side_effect_census_complete": True,
            "evidence_refs": ["receipt:posture:1"],
        },
        "stages": [
            {
                "stage": stage,
                "component_id": component_id,
                "path": path,
                "proof": _proof(f"proof:stage:{stage}:{path}", activation=activation),
            }
            for stage, component_id, path, activation in _STAGES
        ],
        "edges": [
            {
                "source_stage": source,
                "target_stage": target,
                "channel": channel,
                "proof": _proof(f"proof:edge:{source}:{target}:{channel}"),
            }
            for source, target, channel in _EDGES
        ],
        "cohort": {
            "cohort_id": "cohort:origin:1",
            "window_start_us": 1_786_499_999_000_000,
            "window_end_us": 1_786_499_999_999_000,
            "source_watermark": "source:100",
            "source_cut_digest": _DIGEST,
            "complete": True,
            "candidate_ids": ["candidate:1"],
            "zero_proof": None,
            "evidence_refs": ["receipt:cohort:1"],
        },
        "evaluations": [
            {
                "evaluation_id": "evaluation:rejected:1",
                "candidate_id": "candidate:1",
                "decision_state": "REJECTED",
                "route_revision": "route:1",
                "observed_at_us": 1_786_499_999_998_000,
                "maturity_deadline_us": 1_786_499_999_999_000,
                "event_posture": deepcopy(posture),
            }
        ],
        "terminals": [],
        "metrics": [
            {
                "metric_id": "e02.candidates.count",
                "metric_class": "COUNT",
                "population": None,
                "value_type": "INTEGER",
                "value": 1,
                "unit": "COUNT",
                "availability": "OBSERVED",
                "reason_code": None,
                "zero_proof": None,
                "evidence_refs": ["query:shadow:1"],
            }
        ],
    }


def _document() -> dict:
    """Create a reconciled fixture through the public codec, including route identity."""
    document = _unreconciled_document()
    seed_report = build_scorecard_from_dict(deepcopy(document))
    route_id = seed_report["routes"][0]["population_instance_id"]
    document["terminals"] = [
        {
            "terminal_id": "terminal:rejected:1",
            "population_instance_id": route_id,
            "kind": "REJECTED",
            "payload_digest": _TERMINAL_DIGEST,
            "reason_code": "SCORECARD_COMPONENT_OFF",
            "evidence_refs": ["receipt:terminal:1"],
        }
    ]
    return document


def _component(document: dict, component_id: str) -> dict:
    return next(
        row for row in document["components"] if row["component_id"] == component_id
    )


def test_unknown_posture_freshness_withholds_publication() -> None:
    document = _document()
    document["posture"]["freshness"] = "UNKNOWN"

    report = build_scorecard_from_dict(document)

    assert report["posture_proof"]["state"] == "UNRECONCILED"
    assert report["publication"]["outcome"] == "WITHHELD"


def test_asserted_evidence_can_never_publish_full() -> None:
    report = build_scorecard_from_dict(_document())

    assert report["publication"]["blockers"] == []
    assert report["publication"]["outcome"] == "STATUS_ONLY"
    assert report["authority_effect"] == "NONE"


def test_zero_proved_empty_cohort_is_status_only() -> None:
    document = _document()
    document["cohort"]["candidate_ids"] = []
    document["cohort"]["zero_proof"] = _zero_proof()
    document["evaluations"] = []
    document["terminals"] = []
    document["metrics"][0]["value"] = 0
    document["metrics"][0]["zero_proof"] = _zero_proof()

    report = build_scorecard_from_dict(document)

    assert report["publication"]["outcome"] == "STATUS_ONLY"
    assert {row["code"] for row in report["publication"]["status_flags"]} >= {
        "SCORECARD_COHORT_EMPTY",
        "SCORECARD_NO_MATURED_POPULATION",
    }


@pytest.mark.parametrize("cohort_state", ["INCOMPLETE", "MISSING_TERMINAL"])
def test_incomplete_cohort_or_missing_terminal_withholds(cohort_state: str) -> None:
    document = _document()
    if cohort_state == "INCOMPLETE":
        document["cohort"]["complete"] = False
    else:
        document["terminals"] = []

    report = build_scorecard_from_dict(document)

    assert report["publication"]["outcome"] == "WITHHELD"


def test_structurally_missing_cohort_is_rejected_by_closed_codec() -> None:
    document = _document()
    del document["cohort"]

    with pytest.raises(ScorecardError, match="input fields mismatch"):
        build_scorecard_from_dict(document)


def test_unratified_kairos_and_logos_are_status_only() -> None:
    document = _document()
    for component_id in ("kairos", "logos"):
        row = _component(document, component_id)
        row["mapping_status"] = "OPERATOR_ASSERTED_UNATTESTED"
        row["mapping_evidence_refs"] = []

    report = build_scorecard_from_dict(document)

    flags = {
        (row["code"], row["subject"])
        for row in report["publication"]["status_flags"]
    }
    assert report["publication"]["outcome"] == "STATUS_ONLY"
    assert ("SCORECARD_MAPPING_UNATTESTED", "kairos") in flags
    assert ("SCORECARD_MAPPING_UNATTESTED", "logos") in flags


@pytest.mark.parametrize(
    ("source", "target", "channel"),
    [
        ("E03", "E06", "DIRECT_PROVIDER_CALL"),
        ("E06", "E03", "DIRECT_PROVIDER_CALL"),
        ("E00", "E02", "NONCANONICAL_SHORTCUT"),
    ],
)
def test_noncanonical_extra_edges_are_rejected(
    source: str,
    target: str,
    channel: str,
) -> None:
    document = _document()
    document["edges"].append({
        "source_stage": source,
        "target_stage": target,
        "channel": channel,
        "proof": _proof(f"proof:edge:{source}:{target}:{channel}"),
    })

    with pytest.raises(ScorecardError):
        build_scorecard_from_dict(document)


@pytest.mark.parametrize("claim", ["execution", "VENUE_BROKER", "UNREGISTERED_CLAIM"])
def test_advisory_authority_aliases_and_unknown_claims_are_rejected(claim: str) -> None:
    document = _document()
    _component(document, "kairos")["authority_claims"] = [claim]

    with pytest.raises(ScorecardError):
        build_scorecard_from_dict(document)


def test_report_and_content_digest_are_deterministic() -> None:
    document = _document()

    first = build_scorecard_from_dict(deepcopy(document))
    second = build_scorecard_from_dict(deepcopy(document))

    assert first == second
    assert first["content_digest"] == second["content_digest"]
    verify_report_digest(first)
    verify_report_digest(second)


def test_duplicate_e07_admission_authority_claimants_are_rejected() -> None:
    document = _document()
    decision = _component(document, "decision")
    decision["authority_claims"] = ["ADMISSION_POLICY"]
    duplicate = deepcopy(decision)
    duplicate["component_id"] = "decision:split-brain"
    duplicate["mapping_evidence_refs"] = ["adr:decision:split-brain:1"]
    document["components"].append(duplicate)

    with pytest.raises(ScorecardError, match="ADMISSION_POLICY has multiple components"):
        build_scorecard_from_dict(document)


def test_unknown_submit_is_an_execution_terminal_not_an_e07_decision() -> None:
    document = _document()
    document["evaluations"][0]["decision_state"] = "UNKNOWN_SUBMIT"

    with pytest.raises(ScorecardError, match="invalid closed-enum value"):
        build_scorecard_from_dict(document)
