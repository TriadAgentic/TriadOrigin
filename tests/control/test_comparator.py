"""B07 comparator battery: two-axis type safety (engine_cohort vs intelligence_arm never
conflated), exact precedence-ordered divergence classification (MISSING/EXTRA/RETIMED/
REIDENTIFIED/GEOMETRY/LIFECYCLE/QUALITY/DOWNSTREAM_ELIGIBILITY), schema self-validation,
side-effect-free determinism, drift-lock to the vendored divergence_class enum."""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import contracts  # noqa: E402
from triad_origin.control import comparator as c  # noqa: E402


def _control(**overrides):
    base = {
        "engine_cohort": "LEGACY_COMPARATOR",
        "intelligence_arm": "DETERMINISTIC_CONTROL",
        "candidate_id": "cand-control-1",
        "direction": "LONG",
        "entry_reference_ticks": "100",
        "natural_invalidation_ticks": "90",
        "targets": ["110"],
        "rr_numerator": "2",
        "rr_denominator": "1",
        "source_structure_id": "struct-1",
        "source_reaction_id": "reaction-1",
        "state": "PROPOSED",
        "quality": {"warm": True},
        "arm": "SHADOW",
        "provenance_hash": "a" * 64,
    }
    base.update(overrides)
    return base


def _treatment(**overrides):
    # NOTE: flips ONLY engine_cohort by default — intelligence_arm stays whatever _control()'s
    # default is (the axis NOT under test for compare_engine_cohort, which every helper/test in
    # this file that builds a matched pair via _control()/_treatment() ultimately exercises; the
    # comparator now REFUSES a pair whose non-compared axis disagrees, so holding it constant by
    # default here is load-bearing, not cosmetic). A test that wants to exercise the
    # intelligence_arm axis instead builds its pair directly from _control() overrides, holding
    # engine_cohort constant explicitly (see test_the_two_axes_produce_independently_labeled_records).
    base = _control(engine_cohort="ORIGIN_CANDIDATE",
                     candidate_id="cand-treatment-1", provenance_hash="b" * 64)
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------------------------
# Drift-lock: the local vocabulary must byte-agree with the vendored schema enum
# ---------------------------------------------------------------------------------------------


def test_divergence_classes_match_the_vendored_schema_enum():
    schema = contracts.load_schema(c.DIVERGENCE_RECORD_SCHEMA)
    enum = schema["properties"]["payload"]["properties"]["divergence_class"]["enum"]
    assert tuple(enum) == c.DIVERGENCE_CLASSES


# ---------------------------------------------------------------------------------------------
# Presence: MISSING / EXTRA / both-absent
# ---------------------------------------------------------------------------------------------


def test_identical_candidates_have_no_divergence():
    control = _control()
    treatment = _treatment(
        direction=control["direction"], entry_reference_ticks=control["entry_reference_ticks"],
        natural_invalidation_ticks=control["natural_invalidation_ticks"],
        targets=control["targets"], rr_numerator=control["rr_numerator"],
        rr_denominator=control["rr_denominator"], candidate_id=control["candidate_id"],
        source_structure_id=control["source_structure_id"],
        source_reaction_id=control["source_reaction_id"], state=control["state"],
        quality=control["quality"], arm=control["arm"])
    assert c.compare_engine_cohort(
        control, treatment, input_offset=1, evaluated_at_us=100, divergence_id="d1") is None


def test_both_absent_is_no_divergence():
    assert c.compare_engine_cohort(
        None, None, input_offset=1, evaluated_at_us=100, divergence_id="d1") is None


def test_control_only_is_missing():
    record = c.compare_engine_cohort(
        _control(), None, input_offset=1, evaluated_at_us=100, divergence_id="d1")
    assert record["divergence_class"] == "MISSING"
    assert record["control_candidate_id"] == "cand-control-1"
    assert record["treatment_candidate_id"] == ""
    assert record["treatment_ref"] == c._ABSENT_REF


def test_treatment_only_is_extra():
    record = c.compare_engine_cohort(
        None, _treatment(), input_offset=1, evaluated_at_us=100, divergence_id="d1")
    assert record["divergence_class"] == "EXTRA"
    assert record["control_candidate_id"] == ""
    assert record["control_ref"] == c._ABSENT_REF


# ---------------------------------------------------------------------------------------------
# Precedence-ordered semantic classes
# ---------------------------------------------------------------------------------------------


def _matched_pair(**treatment_overrides):
    control = _control()
    treatment = _treatment(
        direction=control["direction"], entry_reference_ticks=control["entry_reference_ticks"],
        natural_invalidation_ticks=control["natural_invalidation_ticks"],
        targets=control["targets"], rr_numerator=control["rr_numerator"],
        rr_denominator=control["rr_denominator"], candidate_id=control["candidate_id"],
        source_structure_id=control["source_structure_id"],
        source_reaction_id=control["source_reaction_id"], state=control["state"],
        quality=control["quality"], arm=control["arm"])
    treatment.update(treatment_overrides)
    return control, treatment


def test_geometry_divergence_wins_first():
    control, treatment = _matched_pair(entry_reference_ticks="999")
    record = c.compare_engine_cohort(
        control, treatment, input_offset=1, evaluated_at_us=100, divergence_id="d1")
    assert record["divergence_class"] == "GEOMETRY"


def test_geometry_divergence_beats_a_simultaneous_identity_divergence():
    # Both geometry AND identity differ — GEOMETRY (checked first) must win, never REIDENTIFIED.
    control, treatment = _matched_pair(
        entry_reference_ticks="999", candidate_id="some-other-id")
    record = c.compare_engine_cohort(
        control, treatment, input_offset=1, evaluated_at_us=100, divergence_id="d1")
    assert record["divergence_class"] == "GEOMETRY"


def test_reidentified_when_only_identity_differs():
    control, treatment = _matched_pair(candidate_id="a-different-id")
    record = c.compare_engine_cohort(
        control, treatment, input_offset=1, evaluated_at_us=100, divergence_id="d1")
    assert record["divergence_class"] == "REIDENTIFIED"


def test_retimed_when_only_timing_differs():
    control, treatment = _matched_pair(source_reaction_id="a-different-reaction")
    record = c.compare_engine_cohort(
        control, treatment, input_offset=1, evaluated_at_us=100, divergence_id="d1")
    assert record["divergence_class"] == "RETIMED"


def test_identity_divergence_beats_a_simultaneous_timing_divergence():
    # CTL-7: the docstring's CORRECTED check precedence is geometry > identity > timing (distinct
    # from the schema enum listing). A pair diverging on BOTH identity and timing must classify
    # REIDENTIFIED, never RETIMED — this pins the middle rung of the stated precedence chain.
    control, treatment = _matched_pair(
        candidate_id="a-different-id", source_reaction_id="a-different-reaction")
    record = c.compare_engine_cohort(
        control, treatment, input_offset=1, evaluated_at_us=100, divergence_id="d1")
    assert record["divergence_class"] == "REIDENTIFIED"


def test_lifecycle_when_only_state_differs():
    control, treatment = _matched_pair(state="WITHDRAWN")
    record = c.compare_engine_cohort(
        control, treatment, input_offset=1, evaluated_at_us=100, divergence_id="d1")
    assert record["divergence_class"] == "LIFECYCLE"


def test_quality_when_only_quality_differs():
    control, treatment = _matched_pair(quality={"warm": False})
    record = c.compare_engine_cohort(
        control, treatment, input_offset=1, evaluated_at_us=100, divergence_id="d1")
    assert record["divergence_class"] == "QUALITY"


def test_downstream_eligibility_when_only_arm_differs():
    control, treatment = _matched_pair(arm="TREATMENT")
    record = c.compare_engine_cohort(
        control, treatment, input_offset=1, evaluated_at_us=100, divergence_id="d1")
    assert record["divergence_class"] == "DOWNSTREAM_ELIGIBILITY"


# ---------------------------------------------------------------------------------------------
# Two-axis type safety
# ---------------------------------------------------------------------------------------------


def test_compare_engine_cohort_refuses_a_control_with_the_wrong_cohort():
    wrong = _control(engine_cohort="ORIGIN_CANDIDATE")
    with pytest.raises(c.ComparatorError):
        c.compare_engine_cohort(wrong, None, input_offset=1, evaluated_at_us=1,
                                 divergence_id="d1")


def test_compare_engine_cohort_refuses_a_treatment_with_the_wrong_cohort():
    wrong = _treatment(engine_cohort="LEGACY_COMPARATOR")
    with pytest.raises(c.ComparatorError):
        c.compare_engine_cohort(None, wrong, input_offset=1, evaluated_at_us=1,
                                 divergence_id="d1")


def test_compare_engine_cohort_refuses_a_candidate_missing_the_cohort_label():
    no_label = dict(_control())
    del no_label["engine_cohort"]
    with pytest.raises(c.ComparatorError):
        c.compare_engine_cohort(no_label, None, input_offset=1, evaluated_at_us=1,
                                 divergence_id="d1")


def test_compare_intelligence_arm_refuses_a_control_with_the_wrong_arm():
    wrong = _control(intelligence_arm="INTELLIGENCE_TREATMENT")
    with pytest.raises(c.ComparatorError):
        c.compare_intelligence_arm(wrong, None, input_offset=1, evaluated_at_us=1,
                                    divergence_id="d1")


def test_compare_intelligence_arm_refuses_a_treatment_with_the_wrong_arm():
    wrong = _treatment(intelligence_arm="DETERMINISTIC_CONTROL")
    with pytest.raises(c.ComparatorError):
        c.compare_intelligence_arm(None, wrong, input_offset=1, evaluated_at_us=1,
                                    divergence_id="d1")


def test_compare_engine_cohort_refuses_when_the_non_compared_arm_axis_disagrees():
    # Both sides carry the CORRECT engine_cohort label for their position, but the
    # non-compared intelligence_arm axis disagrees between them — a divergence attributed to
    # engine_cohort alone here could actually be confounded by a simultaneous arm change, so
    # this must refuse rather than silently emit a possibly-misattributed record.
    control = _control(intelligence_arm="DETERMINISTIC_CONTROL")
    treatment = _treatment(intelligence_arm="INTELLIGENCE_TREATMENT")
    with pytest.raises(c.ComparatorError):
        c.compare_engine_cohort(control, treatment, input_offset=1, evaluated_at_us=1,
                                 divergence_id="d1")


def test_compare_intelligence_arm_refuses_when_the_non_compared_cohort_axis_disagrees():
    # Symmetric: both sides carry the correct intelligence_arm label, but engine_cohort
    # disagrees between them.
    control = _control(engine_cohort="LEGACY_COMPARATOR", intelligence_arm="DETERMINISTIC_CONTROL")
    treatment = _control(
        engine_cohort="ORIGIN_CANDIDATE", intelligence_arm="INTELLIGENCE_TREATMENT",
        candidate_id="cand-treatment-1", provenance_hash="b" * 64)
    with pytest.raises(c.ComparatorError):
        c.compare_intelligence_arm(control, treatment, input_offset=1, evaluated_at_us=1,
                                    divergence_id="d1")


def test_the_two_axes_produce_independently_labeled_records():
    control_cohort = _control()
    treatment_cohort = _treatment(
        direction=control_cohort["direction"],
        entry_reference_ticks="999",  # force a real divergence
    )
    cohort_record = c.compare_engine_cohort(
        control_cohort, treatment_cohort, input_offset=1, evaluated_at_us=1,
        divergence_id="d-cohort")
    assert cohort_record["comparison_axis"] == "ENGINE_COHORT"

    # Exercising the intelligence_arm axis: engine_cohort must be held CONSTANT across both
    # sides (the comparator now refuses otherwise) while intelligence_arm differs.
    control_arm = _control(engine_cohort="LEGACY_COMPARATOR", intelligence_arm="DETERMINISTIC_CONTROL")
    treatment_arm = _control(
        engine_cohort="LEGACY_COMPARATOR", intelligence_arm="INTELLIGENCE_TREATMENT",
        candidate_id="cand-treatment-1", provenance_hash="b" * 64,
        entry_reference_ticks="999")
    arm_record = c.compare_intelligence_arm(
        control_arm, treatment_arm, input_offset=1, evaluated_at_us=1, divergence_id="d-arm")
    assert arm_record["comparison_axis"] == "INTELLIGENCE_ARM"


def test_require_engine_cohort_and_require_intelligence_arm_refuse_unknown_values():
    with pytest.raises(c.ComparatorError):
        c.require_engine_cohort("SOMETHING_ELSE")
    with pytest.raises(c.ComparatorError):
        c.require_intelligence_arm("SOMETHING_ELSE")


# ---------------------------------------------------------------------------------------------
# Schema validation + determinism + fail-closed inputs
# ---------------------------------------------------------------------------------------------


def test_every_emitted_record_is_schema_valid():
    control, treatment = _matched_pair(entry_reference_ticks="999")
    record = c.compare_engine_cohort(
        control, treatment, input_offset=1, evaluated_at_us=100, divergence_id="d1")
    contracts.validate_payload(c.DIVERGENCE_RECORD_SCHEMA, record)  # raises if invalid


def test_comparison_is_deterministic():
    control, treatment = _matched_pair(entry_reference_ticks="999")
    r1 = c.compare_engine_cohort(
        control, treatment, input_offset=1, evaluated_at_us=100, divergence_id="d1")
    r2 = c.compare_engine_cohort(
        dict(control), dict(treatment), input_offset=1, evaluated_at_us=100,
        divergence_id="d1")
    assert r1 == r2


def test_negative_input_offset_refuses():
    with pytest.raises(c.ComparatorError):
        c.compare_engine_cohort(
            _control(), None, input_offset=-1, evaluated_at_us=1, divergence_id="d1")


def test_empty_divergence_id_refuses():
    with pytest.raises(c.ComparatorError):
        c.compare_engine_cohort(
            _control(), None, input_offset=1, evaluated_at_us=1, divergence_id="")


def test_detail_is_a_string_not_an_object():
    control, treatment = _matched_pair(entry_reference_ticks="999")
    record = c.compare_engine_cohort(
        control, treatment, input_offset=1, evaluated_at_us=100, divergence_id="d1")
    assert isinstance(record["detail"], str)
    assert isinstance(record["input_offset"], str)
