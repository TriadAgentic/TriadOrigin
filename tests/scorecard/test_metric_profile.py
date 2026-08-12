"""Adversarial tests for exact scorecard metric representation and profile law."""

from __future__ import annotations

from copy import deepcopy

import pytest

from triad_origin.scorecard import INPUT_SCHEMA, build_scorecard_from_dict
from triad_origin.scorecard.model import (
    Availability,
    MetricClass,
    MetricValue,
    Population,
    ScorecardError,
)


_DIGEST = "1" * 64


def _zero_proof() -> dict[str, str]:
    return {
        "query_digest": _DIGEST,
        "source_cut_digest": _DIGEST,
        "source_completeness": "COMPLETE",
        "watermark": "source:metric:1",
    }


def _decimal_metric(
    value: str,
    *,
    zero_proof: dict[str, str] | None = None,
    evidence_refs: tuple[str, ...] = ("evidence:metric:1",),
) -> MetricValue:
    return MetricValue(
        metric_id="e10.outcomes.net_pnl.quote",
        metric_class=MetricClass.ECONOMIC,
        population=Population.SHADOW,
        value_type="DECIMAL",
        value=value,
        unit="QUOTE",
        availability=Availability.OBSERVED,
        reason_code=None,
        zero_proof=zero_proof,
        evidence_refs=evidence_refs,
    )


def _count_metric(
    value: int,
    *,
    zero_proof: dict[str, str] | None = None,
    evidence_refs: tuple[str, ...] = ("evidence:metric:1",),
) -> MetricValue:
    return MetricValue(
        metric_id="e02.candidates.count",
        metric_class=MetricClass.COUNT,
        population=None,
        value_type="INTEGER",
        value=value,
        unit="COUNT",
        availability=Availability.OBSERVED,
        reason_code=None,
        zero_proof=zero_proof,
        evidence_refs=evidence_refs,
    )


def _metric_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "metric_id": "e02.candidates.count",
        "metric_class": "COUNT",
        "population": None,
        "value_type": "INTEGER",
        "value": 1,
        "unit": "COUNT",
        "availability": "OBSERVED",
        "reason_code": None,
        "zero_proof": None,
        "evidence_refs": ["evidence:metric:1"],
    }
    row.update(overrides)
    return row


def _document() -> dict[str, object]:
    posture = {
        "venue_environment": "OFF",
        "venue_activation": "OFF",
        "paper_activation": "OFF",
        "shadow_activation": "LIVE",
    }
    return {
        "schema": INPUT_SCHEMA,
        "report_id": "scorecard:test:metric-profile",
        "as_of_us": 1_000_000,
        "components": [],
        "cohort": {
            "cohort_id": "cohort:empty:1",
            "window_start_us": 0,
            "window_end_us": 999_999,
            "source_watermark": "source:cohort:1",
            "source_cut_digest": _DIGEST,
            "complete": True,
            "candidate_ids": [],
            "zero_proof": _zero_proof(),
            "evidence_refs": ["evidence:cohort:1"],
        },
        "posture": {
            "desired": deepcopy(posture),
            "observed": deepcopy(posture),
            "freshness": "FRESH",
            "reconciliation": "RECONCILED",
            "attestation": "VALID",
            "side_effect_census_complete": True,
            "evidence_refs": ["evidence:posture:1"],
        },
        "stages": [],
        "edges": [],
        "evaluations": [],
        "terminals": [],
        "metrics": [],
    }


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("0e0", id="exponent-zero"),
        pytest.param("+0", id="leading-plus"),
        pytest.param("-0e+10", id="negative-exponent-zero"),
        pytest.param("NaN", id="nan"),
        pytest.param("Infinity", id="infinity"),
        pytest.param("1.230", id="trailing-zero"),
    ],
)
def test_decimal_metrics_reject_noncanonical_representations(value: str) -> None:
    with pytest.raises(ScorecardError, match="canonical non-exponent decimal"):
        _decimal_metric(value)


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(-1, id="negative"),
        pytest.param(2**63, id="signed-64-overflow"),
    ],
)
def test_counts_reject_negative_and_oversized_integers(value: int) -> None:
    with pytest.raises(ScorecardError, match="signed-64 non-negative exact integer"):
        _count_metric(value)


def test_observed_metric_requires_evidence() -> None:
    with pytest.raises(ScorecardError, match="metric evidence_refs must not be empty"):
        _count_metric(1, evidence_refs=())


def test_observed_zero_requires_closed_zero_proof() -> None:
    with pytest.raises(ScorecardError, match="observed numeric zero requires zero_proof"):
        _count_metric(0)

    metric = _count_metric(0, zero_proof=_zero_proof())

    assert metric.value == 0
    assert metric.zero_proof == _zero_proof()


def test_zero_proof_is_forbidden_on_a_nonzero_measurement() -> None:
    with pytest.raises(ScorecardError, match="zero_proof is legal only"):
        _count_metric(1, zero_proof=_zero_proof())


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {"metric_id": "operator.asserted.metric"},
            "metric_id is outside the closed diagnostic profile",
        ),
        ({"metric_class": "HEALTH"}, "metric shape conflicts with profile"),
        ({"population": "SHADOW"}, "metric shape conflicts with profile"),
    ],
    ids=("unknown-id", "wrong-shape", "forbidden-population"),
)
def test_builder_rejects_metrics_outside_the_closed_profile(
    overrides: dict[str, object],
    message: str,
) -> None:
    document = _document()
    document["metrics"] = [_metric_row(**overrides)]

    with pytest.raises(ScorecardError, match=message):
        build_scorecard_from_dict(document)


def test_cohort_count_mismatch_withholds_publication() -> None:
    document = _document()
    cohort = document["cohort"]
    assert isinstance(cohort, dict)
    cohort["candidate_ids"] = ["candidate:1"]
    cohort["zero_proof"] = None
    document["metrics"] = [_metric_row(value=2)]

    report = build_scorecard_from_dict(document)

    assert report["publication"]["outcome"] == "WITHHELD"
    assert {
        (finding["code"], finding["subject"])
        for finding in report["publication"]["blockers"]
    } >= {
        (
            "INPUT_CUT_MISMATCH",
            "e02.candidates.count does not equal cohort candidate_ids",
        )
    }


def test_e10_economic_metric_requires_an_explicit_population() -> None:
    document = _document()
    document["metrics"] = [
        _metric_row(
            metric_id="e10.outcomes.net_pnl.quote",
            metric_class="ECONOMIC",
            population=None,
            value_type="DECIMAL",
            value="1.25",
            unit="QUOTE",
        )
    ]

    with pytest.raises(ScorecardError, match="economic metrics require one explicit population"):
        build_scorecard_from_dict(document)


def test_e10_economic_metrics_preserve_population_separation() -> None:
    document = _document()
    document["metrics"] = [
        _metric_row(
            metric_id="e10.outcomes.net_pnl.quote",
            metric_class="ECONOMIC",
            population="SHADOW",
            value_type="DECIMAL",
            value="1.25",
            unit="QUOTE",
        ),
        _metric_row(
            metric_id="e10.outcomes.net_pnl.quote",
            metric_class="ECONOMIC",
            population="LIVE",
            value_type="DECIMAL",
            value="-0.5",
            unit="QUOTE",
        ),
    ]

    report = build_scorecard_from_dict(document)

    economic_rows = [
        row
        for row in report["metrics"]
        if row["metric_id"] == "e10.outcomes.net_pnl.quote"
    ]
    assert len(economic_rows) == 2
    assert {(row["population"], row["value"]) for row in economic_rows} == {
        ("SHADOW", "1.25"),
        ("LIVE", "-0.5"),
    }
