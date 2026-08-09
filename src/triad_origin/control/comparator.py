"""Side-effect-free control/treatment candidate comparator (B07 — RC3-WOP-003).

Compares two labeled candidate payloads at a matching input offset and classifies any divergence
per the closed :data:`triad.divergence_record.v1` taxonomy — exactly one of MISSING, EXTRA,
RETIMED, REIDENTIFIED, GEOMETRY, LIFECYCLE, QUALITY, DOWNSTREAM_ELIGIBILITY, checked in that
fixed precedence order (the first difference found wins; a divergence record never claims more
than one class even when several fields disagree — the caller's ``detail`` string names every
field this run actually compared).

**Two independent axes** (RC3-WOP-001/002's ``required_typing``; the materialized
``RC3-PAR-EXP-001``/``RC3-PAR-EXP-002`` parameters):

  * ``engine_cohort`` ∈ {LEGACY_COMPARATOR, ORIGIN_CANDIDATE} — WHICH PRODUCER emitted a
    candidate.
  * ``intelligence_arm`` ∈ {DETERMINISTIC_CONTROL, INTELLIGENCE_TREATMENT} — WHICH TREATMENT
    policy governed it.

A real candidate carries both tags independently (an ``ORIGIN_CANDIDATE`` may run under either
arm), so this module NEVER conflates them: :func:`compare_engine_cohort` and
:func:`compare_intelligence_arm` are separate entry points, each validating its OWN candidates
carry the labels IT expects (a candidate mislabeled for the axis being compared is refused, never
silently accepted) and stamping its own ``comparison_axis`` (the closed pair
:data:`COMPARISON_AXES`, matching RC3-WOP-003) as an additive field on the emitted
``divergence_record.v1`` payload — additive fields are compatibility-preserved by the vendored
schema's own ``additionalProperties: true`` law.

Pure and side-effect-free: no clock, no I/O, no network, no randomness. ``evaluated_at_us`` and
``divergence_id`` are always caller-supplied.
"""

from __future__ import annotations

from .. import contracts
from ..canonical import canonical_json

DIVERGENCE_RECORD_SCHEMA = "triad.divergence_record.v1"

# The closed divergence_class vocabulary, checked in this fixed precedence order.
DIVERGENCE_CLASSES = (
    "MISSING", "EXTRA", "RETIMED", "REIDENTIFIED", "GEOMETRY", "LIFECYCLE", "QUALITY",
    "DOWNSTREAM_ELIGIBILITY",
)

ENGINE_COHORTS = ("LEGACY_COMPARATOR", "ORIGIN_CANDIDATE")
INTELLIGENCE_ARMS = ("DETERMINISTIC_CONTROL", "INTELLIGENCE_TREATMENT")
COMPARISON_AXES = ("ENGINE_COHORT", "INTELLIGENCE_ARM")

_ABSENT_REF = "ABSENT"

# Fields compared for each divergence class, in the fixed precedence order above (after the
# MISSING/EXTRA presence check). A candidate lacking a field compares as ``None`` for that field
# — an honest absence, never a fabricated default.
_GEOMETRY_FIELDS = (
    "direction", "entry_reference_ticks", "natural_invalidation_ticks", "targets",
    "rr_numerator", "rr_denominator",
)
_IDENTITY_FIELDS = ("candidate_id",)
_TIMING_FIELDS = ("source_structure_id", "source_reaction_id")
_LIFECYCLE_FIELDS = ("state",)
_QUALITY_FIELDS = ("quality",)
_ELIGIBILITY_FIELDS = ("arm",)


class ComparatorError(RuntimeError):
    """A comparison could not be performed as requested — fail closed, never a guessed verdict."""


def require_engine_cohort(value: object) -> str:
    if value not in ENGINE_COHORTS:
        raise ComparatorError(f"unknown engine_cohort: {value!r}")
    return value  # type: ignore[return-value]


def require_intelligence_arm(value: object) -> str:
    if value not in INTELLIGENCE_ARMS:
        raise ComparatorError(f"unknown intelligence_arm: {value!r}")
    return value  # type: ignore[return-value]


def _ref(candidate: dict | None) -> str:
    if candidate is None:
        return _ABSENT_REF
    provenance = candidate.get("provenance_hash")
    if isinstance(provenance, str) and provenance:
        return provenance
    candidate_id = candidate.get("candidate_id")
    return candidate_id if isinstance(candidate_id, str) and candidate_id else _ABSENT_REF


def _candidate_id(candidate: dict | None) -> str:
    if candidate is None:
        return ""
    value = candidate.get("candidate_id")
    return value if isinstance(value, str) else ""


def _subset(candidate: dict, fields: tuple) -> dict:
    return {f: candidate.get(f) for f in fields}


def _detail(divergence_class: str, **fields) -> str:
    """A deterministic, canonical-JSON string summary of exactly what this class compared."""
    return canonical_json({"divergence_class": divergence_class, **fields}).decode("utf-8")


def _record(
    *, divergence_id: str, input_offset: int, control: dict | None, treatment: dict | None,
    divergence_class: str, detail: str, evaluated_at_us: int, comparison_axis: str,
) -> dict:
    payload = {
        "divergence_id": divergence_id,
        "input_offset": str(input_offset),
        "control_candidate_id": _candidate_id(control),
        "treatment_candidate_id": _candidate_id(treatment),
        "divergence_class": divergence_class,
        "detail": detail,
        "control_ref": _ref(control),
        "treatment_ref": _ref(treatment),
        "evaluated_at_us": evaluated_at_us,
        "comparison_axis": comparison_axis,
    }
    try:
        contracts.validate_payload(DIVERGENCE_RECORD_SCHEMA, payload)
    except contracts.ContractError as exc:
        raise ComparatorError(f"constructed divergence record failed schema validation: {exc}") \
            from exc
    return payload


def _compare(
    control: dict | None, treatment: dict | None, *, input_offset: int, evaluated_at_us: int,
    divergence_id: str, comparison_axis: str,
) -> dict | None:
    """Pure candidate diff. Returns a validated divergence_record.v1 PAYLOAD, or ``None`` when
    nothing diverges (including when both sides are absent)."""
    if not isinstance(input_offset, int) or isinstance(input_offset, bool) or input_offset < 0:
        raise ComparatorError("input_offset must be a non-negative int")
    if not isinstance(evaluated_at_us, int) or isinstance(evaluated_at_us, bool):
        raise ComparatorError("evaluated_at_us must be an int")
    if not isinstance(divergence_id, str) or not divergence_id:
        raise ComparatorError("divergence_id must be a non-empty string")

    if control is None and treatment is None:
        return None
    if control is None:
        return _record(
            divergence_id=divergence_id, input_offset=input_offset, control=None,
            treatment=treatment, divergence_class="EXTRA",
            detail=_detail("EXTRA", treatment_candidate_id=_candidate_id(treatment)),
            evaluated_at_us=evaluated_at_us, comparison_axis=comparison_axis)
    if treatment is None:
        return _record(
            divergence_id=divergence_id, input_offset=input_offset, control=control,
            treatment=None, divergence_class="MISSING",
            detail=_detail("MISSING", control_candidate_id=_candidate_id(control)),
            evaluated_at_us=evaluated_at_us, comparison_axis=comparison_axis)

    control_geometry = _subset(control, _GEOMETRY_FIELDS)
    treatment_geometry = _subset(treatment, _GEOMETRY_FIELDS)
    if control_geometry != treatment_geometry:
        return _record(
            divergence_id=divergence_id, input_offset=input_offset, control=control,
            treatment=treatment, divergence_class="GEOMETRY",
            detail=_detail("GEOMETRY", control=control_geometry, treatment=treatment_geometry),
            evaluated_at_us=evaluated_at_us, comparison_axis=comparison_axis)

    control_identity = _subset(control, _IDENTITY_FIELDS)
    treatment_identity = _subset(treatment, _IDENTITY_FIELDS)
    if control_identity != treatment_identity:
        return _record(
            divergence_id=divergence_id, input_offset=input_offset, control=control,
            treatment=treatment, divergence_class="REIDENTIFIED",
            detail=_detail("REIDENTIFIED", control=control_identity,
                            treatment=treatment_identity),
            evaluated_at_us=evaluated_at_us, comparison_axis=comparison_axis)

    control_timing = _subset(control, _TIMING_FIELDS)
    treatment_timing = _subset(treatment, _TIMING_FIELDS)
    if control_timing != treatment_timing:
        return _record(
            divergence_id=divergence_id, input_offset=input_offset, control=control,
            treatment=treatment, divergence_class="RETIMED",
            detail=_detail("RETIMED", control=control_timing, treatment=treatment_timing),
            evaluated_at_us=evaluated_at_us, comparison_axis=comparison_axis)

    control_lifecycle = _subset(control, _LIFECYCLE_FIELDS)
    treatment_lifecycle = _subset(treatment, _LIFECYCLE_FIELDS)
    if control_lifecycle != treatment_lifecycle:
        return _record(
            divergence_id=divergence_id, input_offset=input_offset, control=control,
            treatment=treatment, divergence_class="LIFECYCLE",
            detail=_detail("LIFECYCLE", control=control_lifecycle,
                            treatment=treatment_lifecycle),
            evaluated_at_us=evaluated_at_us, comparison_axis=comparison_axis)

    control_quality = _subset(control, _QUALITY_FIELDS)
    treatment_quality = _subset(treatment, _QUALITY_FIELDS)
    if control_quality != treatment_quality:
        return _record(
            divergence_id=divergence_id, input_offset=input_offset, control=control,
            treatment=treatment, divergence_class="QUALITY",
            detail=_detail("QUALITY", control=control_quality, treatment=treatment_quality),
            evaluated_at_us=evaluated_at_us, comparison_axis=comparison_axis)

    control_eligibility = _subset(control, _ELIGIBILITY_FIELDS)
    treatment_eligibility = _subset(treatment, _ELIGIBILITY_FIELDS)
    if control_eligibility != treatment_eligibility:
        return _record(
            divergence_id=divergence_id, input_offset=input_offset, control=control,
            treatment=treatment, divergence_class="DOWNSTREAM_ELIGIBILITY",
            detail=_detail("DOWNSTREAM_ELIGIBILITY", control=control_eligibility,
                            treatment=treatment_eligibility),
            evaluated_at_us=evaluated_at_us, comparison_axis=comparison_axis)

    return None  # every compared field agrees — no divergence


def compare_engine_cohort(
    control: dict | None, treatment: dict | None, *, input_offset: int, evaluated_at_us: int,
    divergence_id: str,
) -> dict | None:
    """Compare a LEGACY_COMPARATOR candidate against an ORIGIN_CANDIDATE candidate.

    Refuses (:class:`ComparatorError`) if either present candidate does not carry its expected
    ``engine_cohort`` label — a caller cannot silently feed intelligence_arm-differentiated
    candidates through the engine_cohort axis.
    """
    if control is not None:
        cohort = require_engine_cohort(control.get("engine_cohort"))
        if cohort != "LEGACY_COMPARATOR":
            raise ComparatorError(
                f"control candidate for compare_engine_cohort must carry engine_cohort="
                f"LEGACY_COMPARATOR, got {cohort!r}")
    if treatment is not None:
        cohort = require_engine_cohort(treatment.get("engine_cohort"))
        if cohort != "ORIGIN_CANDIDATE":
            raise ComparatorError(
                f"treatment candidate for compare_engine_cohort must carry engine_cohort="
                f"ORIGIN_CANDIDATE, got {cohort!r}")
    return _compare(
        control, treatment, input_offset=input_offset, evaluated_at_us=evaluated_at_us,
        divergence_id=divergence_id, comparison_axis="ENGINE_COHORT")


def compare_intelligence_arm(
    control: dict | None, treatment: dict | None, *, input_offset: int, evaluated_at_us: int,
    divergence_id: str,
) -> dict | None:
    """Compare a DETERMINISTIC_CONTROL candidate against an INTELLIGENCE_TREATMENT candidate.

    Refuses (:class:`ComparatorError`) if either present candidate does not carry its expected
    ``intelligence_arm`` label — a caller cannot silently feed engine_cohort-differentiated
    candidates through the intelligence_arm axis.
    """
    if control is not None:
        arm = require_intelligence_arm(control.get("intelligence_arm"))
        if arm != "DETERMINISTIC_CONTROL":
            raise ComparatorError(
                f"control candidate for compare_intelligence_arm must carry intelligence_arm="
                f"DETERMINISTIC_CONTROL, got {arm!r}")
    if treatment is not None:
        arm = require_intelligence_arm(treatment.get("intelligence_arm"))
        if arm != "INTELLIGENCE_TREATMENT":
            raise ComparatorError(
                f"treatment candidate for compare_intelligence_arm must carry intelligence_arm="
                f"INTELLIGENCE_TREATMENT, got {arm!r}")
    return _compare(
        control, treatment, input_offset=input_offset, evaluated_at_us=evaluated_at_us,
        divergence_id=divergence_id, comparison_axis="INTELLIGENCE_ARM")
