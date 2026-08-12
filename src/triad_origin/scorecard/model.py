"""Closed, read-only data model for the TRIAD full-pipeline scorecard.

The scorecard observes E00--E10 but does not transfer authority into ORIGIN.  All clocks,
freshness ages, digests, mappings, and dispositions are caller-supplied evidence.  No value is
read from the environment or a wall clock, and no missing measurement is coerced to zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from ..canonical import is_sha256_hex


class ScorecardError(ValueError):
    """A scorecard input violates the closed evidence model."""


class StageId(str, Enum):
    E00 = "E00"
    E01 = "E01"
    E02 = "E02"
    E03 = "E03"
    E04 = "E04"
    E05 = "E05"
    E06 = "E06"
    E07 = "E07"
    E08 = "E08"
    E09 = "E09"
    E10 = "E10"


class ProofState(str, Enum):
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    DARK = "DARK"
    OFF = "OFF"
    STALE = "STALE"
    UNRECONCILED = "UNRECONCILED"
    PROVEN = "PROVEN"


class Implementation(str, Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    UNKNOWN = "UNKNOWN"


class DeploymentRole(str, Enum):
    ACTIVE_WRITER = "ACTIVE_WRITER"
    REPLICA = "REPLICA"
    MIRROR = "MIRROR"
    DARK = "DARK"
    RETIRED = "RETIRED"
    UNKNOWN = "UNKNOWN"


class Activation(str, Enum):
    LIVE = "LIVE"
    OFF = "OFF"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNVERIFIED = "UNVERIFIED"


class Freshness(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class Reconciliation(str, Enum):
    RECONCILED = "RECONCILED"
    UNRECONCILED = "UNRECONCILED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class Attestation(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    MISSING = "MISSING"


class SourceKind(str, Enum):
    AUTHORITATIVE_SOURCE = "AUTHORITATIVE_SOURCE"
    MIRROR = "MIRROR"
    EXPORT = "EXPORT"


class Population(str, Enum):
    SHADOW = "SHADOW"
    PAPER = "PAPER"
    TESTNET = "TESTNET"
    LIVE = "LIVE"


class MappingStatus(str, Enum):
    RATIFIED = "RATIFIED"
    OPERATOR_ASSERTED_UNATTESTED = "OPERATOR_ASSERTED_UNATTESTED"
    UNBOUND = "UNBOUND"
    CONFLICT = "CONFLICT"


class ExpectedState(str, Enum):
    ACTIVE = "ACTIVE"
    OFF = "OFF"


class DecisionState(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    UNTRADEABLE = "UNTRADEABLE"


class TerminalKind(str, Enum):
    ABSTAINED = "ABSTAINED"
    REJECTED = "REJECTED"
    SHADOW_UNTRADEABLE = "SHADOW_UNTRADEABLE"
    EXPIRED = "EXPIRED"
    WITHDRAWN_PRE_SEND = "WITHDRAWN_PRE_SEND"
    RISK_DENIED = "RISK_DENIED"
    ACCEPTED_NOT_EXECUTED = "ACCEPTED_NOT_EXECUTED"
    EXECUTION_REJECTED = "EXECUTION_REJECTED"
    CANCELED_NO_FILL = "CANCELED_NO_FILL"
    PROVEN_NO_VENUE_EFFECT = "PROVEN_NO_VENUE_EFFECT"
    OUTCOME_COMPLETE = "OUTCOME_COMPLETE"
    UNKNOWN_SUBMIT_UNRECONCILED = "UNKNOWN_SUBMIT_UNRECONCILED"


class Availability(str, Enum):
    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"
    MISSING = "MISSING"
    NOT_MEASURABLE = "NOT_MEASURABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    ERROR = "ERROR"


class MetricClass(str, Enum):
    HEALTH = "HEALTH"
    COUNT = "COUNT"
    ECONOMIC = "ECONOMIC"


class PublicationOutcome(str, Enum):
    WITHHELD = "WITHHELD"
    STATUS_ONLY = "STATUS_ONLY"
    FULL = "FULL"


class AuthorityClaim(str, Enum):
    RAW_INGRESS = "RAW_INGRESS"
    CANONICAL_STATE = "CANONICAL_STATE"
    ORIGIN_EVIDENCE = "ORIGIN_EVIDENCE"
    ADVISORY_FORECAST = "ADVISORY_FORECAST"
    ADVISORY_SPECIALIST = "ADVISORY_SPECIALIST"
    FUSION_CALIBRATION = "FUSION_CALIBRATION"
    LANGUAGE_KNOWLEDGE = "LANGUAGE_KNOWLEDGE"
    ADMISSION_POLICY = "ADMISSION_POLICY"
    RISK_ALLOW_DENY = "RISK_ALLOW_DENY"
    EXECUTION_VENUE = "EXECUTION_VENUE"
    OUTCOMES_LEARNING = "OUTCOMES_LEARNING"


@dataclass(frozen=True)
class Posture:
    venue_environment: str
    venue_activation: str
    paper_activation: str
    shadow_activation: str

    def __post_init__(self) -> None:
        if self.venue_environment not in {"LIVE", "TESTNET", "OFF"}:
            raise ScorecardError("venue_environment must be LIVE, TESTNET, or OFF")
        if self.venue_activation not in {"LIVE", "OFF"}:
            raise ScorecardError("venue_activation must be LIVE or OFF")
        if self.paper_activation not in {"LIVE", "OFF"}:
            raise ScorecardError("paper_activation must be LIVE or OFF")
        if self.shadow_activation != "LIVE":
            raise ScorecardError("shadow_activation is fixed LIVE")
        if self.venue_environment == "OFF" and self.venue_activation != "OFF":
            raise ScorecardError("OFF venue environment requires venue_activation OFF")

    def to_dict(self) -> dict[str, str]:
        return {
            "venue_environment": self.venue_environment,
            "venue_activation": self.venue_activation,
            "paper_activation": self.paper_activation,
            "shadow_activation": self.shadow_activation,
        }


@dataclass(frozen=True)
class PostureObservation:
    desired: Posture
    observed: Posture | None
    freshness: Freshness
    reconciliation: Reconciliation
    attestation: Attestation
    side_effect_census_complete: bool | None
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_optional_bool(self.side_effect_census_complete, "side_effect_census_complete")
        _validate_texts(self.evidence_refs, "posture evidence_refs")


@dataclass(frozen=True)
class ComponentBinding:
    component_id: str
    stage_id: StageId
    role: str
    mapping_status: MappingStatus
    mapping_evidence_refs: tuple[str, ...]
    authority_claims: tuple[AuthorityClaim, ...]

    def __post_init__(self) -> None:
        _validate_text(self.component_id, "component_id")
        _validate_text(self.role, "component role")
        _validate_texts(self.mapping_evidence_refs, "mapping_evidence_refs", allow_empty=True)
        if not isinstance(self.authority_claims, tuple):
            raise ScorecardError("authority_claims must be an immutable tuple")
        if len(set(self.authority_claims)) != len(self.authority_claims):
            raise ScorecardError("authority_claims must not contain duplicates")
        if not all(isinstance(item, AuthorityClaim) for item in self.authority_claims):
            raise ScorecardError("authority_claims must use the closed AuthorityClaim enum")
        if self.mapping_status is MappingStatus.RATIFIED and not self.mapping_evidence_refs:
            raise ScorecardError("a RATIFIED component mapping requires evidence")


@dataclass(frozen=True)
class ProofDimensions:
    evidence_id: str
    source_kind: SourceKind
    implementation: Implementation
    absence_proven: bool
    deployment_role: DeploymentRole
    activation: Activation
    freshness: Freshness
    freshness_age_ms: int | None
    freshness_bound_ms: int | None
    reconciliation: Reconciliation
    attestation: Attestation
    source_present: bool | None
    formula_correct: bool | None
    authority_closed: bool | None
    runtime_attested: bool | None
    source_watermark: str | None
    consumer_watermark: str | None
    build_digest: str | None
    config_digest: str | None
    contract_digest: str | None
    binding_digest: str | None
    side_effect_census_complete: bool | None
    reason_code: str | None
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_text(self.evidence_id, "evidence_id")
        _validate_optional_bool(self.absence_proven, "absence_proven")
        for name, value in (
            ("source_present", self.source_present),
            ("formula_correct", self.formula_correct),
            ("authority_closed", self.authority_closed),
            ("runtime_attested", self.runtime_attested),
            ("side_effect_census_complete", self.side_effect_census_complete),
        ):
            _validate_optional_bool(value, name)
        for name, value in (
            ("freshness_age_ms", self.freshness_age_ms),
            ("freshness_bound_ms", self.freshness_bound_ms),
        ):
            if value is not None:
                _validate_nonnegative_int(value, name)
        if self.freshness is Freshness.FRESH:
            if self.freshness_age_ms is None or self.freshness_bound_ms is None:
                raise ScorecardError("FRESH evidence requires age and bound")
            if self.freshness_age_ms > self.freshness_bound_ms:
                raise ScorecardError("FRESH evidence exceeds its freshness bound")
        if self.freshness is Freshness.STALE:
            if self.freshness_age_ms is None or self.freshness_bound_ms is None:
                raise ScorecardError("STALE evidence requires age and bound")
            if self.freshness_age_ms <= self.freshness_bound_ms:
                raise ScorecardError("STALE evidence has not exceeded its freshness bound")
        if self.implementation is Implementation.ABSENT and not self.absence_proven:
            raise ScorecardError("ABSENT implementation requires explicit absence proof")
        if self.implementation is Implementation.ABSENT:
            if self.deployment_role is not DeploymentRole.RETIRED:
                raise ScorecardError("ABSENT implementation must use RETIRED deployment role")
            if self.activation is not Activation.NOT_APPLICABLE:
                raise ScorecardError("ABSENT implementation must use NOT_APPLICABLE activation")
            if self.source_present is not False:
                raise ScorecardError("ABSENT implementation requires source_present false")
        elif self.absence_proven:
            raise ScorecardError("absence_proven is legal only for ABSENT implementation")
        if (
            self.deployment_role in {DeploymentRole.DARK, DeploymentRole.RETIRED}
            and self.activation is Activation.LIVE
        ):
            raise ScorecardError("DARK/RETIRED deployment cannot claim LIVE activation")
        for name, value in (
            ("source_watermark", self.source_watermark),
            ("consumer_watermark", self.consumer_watermark),
            ("reason_code", self.reason_code),
        ):
            if value is not None:
                _validate_text(value, name)
        for name, value in (
            ("build_digest", self.build_digest),
            ("config_digest", self.config_digest),
            ("contract_digest", self.contract_digest),
            ("binding_digest", self.binding_digest),
        ):
            if value is not None and (not is_sha256_hex(value) or value == "0" * 64):
                raise ScorecardError(f"{name} must be nonzero lowercase sha256 or null")
        _validate_texts(self.evidence_refs, "proof evidence_refs", allow_empty=True)

    def dimensions(self) -> dict[str, bool | None]:
        return {
            "source_present": self.source_present,
            "formula_correct": self.formula_correct,
            "authority_closed": self.authority_closed,
            "runtime_attested": self.runtime_attested,
        }


@dataclass(frozen=True)
class StageRequirement:
    stage_id: StageId
    path_id: str
    name: str
    authority: str
    expected_state: ExpectedState

    def __post_init__(self) -> None:
        _validate_text(self.path_id, "path_id")
        _validate_text(self.name, "stage name")
        _validate_text(self.authority, "stage authority")


@dataclass(frozen=True)
class StageObservation:
    stage_id: StageId
    component_id: str
    path_id: str
    proof: ProofDimensions

    def __post_init__(self) -> None:
        _validate_text(self.component_id, "stage component_id")
        _validate_text(self.path_id, "stage path_id")


@dataclass(frozen=True)
class EdgeObservation:
    source_stage: StageId
    target_stage: StageId
    channel: str
    proof: ProofDimensions

    def __post_init__(self) -> None:
        _validate_text(self.channel, "edge channel")

    @property
    def key(self) -> tuple[StageId, StageId, str]:
        return (self.source_stage, self.target_stage, self.channel)


@dataclass(frozen=True)
class Evaluation:
    evaluation_id: str
    candidate_id: str
    decision_state: DecisionState
    route_revision: str
    observed_at_us: int
    maturity_deadline_us: int
    event_posture: Posture

    def __post_init__(self) -> None:
        _validate_text(self.evaluation_id, "evaluation_id")
        _validate_text(self.candidate_id, "candidate_id")
        _validate_text(self.route_revision, "route_revision")
        _validate_nonnegative_int(self.observed_at_us, "evaluation observed_at_us")
        _validate_nonnegative_int(self.maturity_deadline_us, "evaluation maturity_deadline_us")
        if self.maturity_deadline_us < self.observed_at_us:
            raise ScorecardError("maturity deadline cannot precede evaluation observation")


@dataclass(frozen=True)
class CandidateCohort:
    cohort_id: str
    window_start_us: int
    window_end_us: int
    source_watermark: str
    source_cut_digest: str
    complete: bool
    candidate_ids: tuple[str, ...]
    zero_proof: dict[str, Any] | None
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_text(self.cohort_id, "cohort_id")
        _validate_nonnegative_int(self.window_start_us, "cohort window_start_us")
        _validate_nonnegative_int(self.window_end_us, "cohort window_end_us")
        if self.window_end_us < self.window_start_us:
            raise ScorecardError("cohort window end cannot precede its start")
        _validate_text(self.source_watermark, "cohort source_watermark")
        if not is_sha256_hex(self.source_cut_digest) or self.source_cut_digest == "0" * 64:
            raise ScorecardError("cohort source_cut_digest must be nonzero lowercase sha256")
        if type(self.complete) is not bool:
            raise ScorecardError("cohort complete must be an exact boolean")
        _validate_texts(self.candidate_ids, "cohort candidate_ids", allow_empty=True)
        _validate_texts(self.evidence_refs, "cohort evidence_refs")
        if self.candidate_ids:
            if self.zero_proof is not None:
                raise ScorecardError("a nonempty cohort cannot carry zero_proof")
        elif self.complete:
            _validate_zero_proof(self.zero_proof)
        elif self.zero_proof is not None:
            raise ScorecardError("an incomplete empty cohort cannot claim zero proof")


@dataclass(frozen=True)
class RouteInstance:
    population_instance_id: str
    evaluation_id: str
    candidate_id: str
    population: Population
    allowed_terminals: tuple[TerminalKind, ...]
    matured: bool

    def __post_init__(self) -> None:
        _validate_text(self.population_instance_id, "population_instance_id")
        _validate_text(self.evaluation_id, "route evaluation_id")
        _validate_text(self.candidate_id, "route candidate_id")
        if not self.allowed_terminals:
            raise ScorecardError("route requires at least one allowed terminal")
        if len(set(self.allowed_terminals)) != len(self.allowed_terminals):
            raise ScorecardError("route allowed terminals must be unique")
        if type(self.matured) is not bool:
            raise ScorecardError("route matured must be an exact boolean")


@dataclass(frozen=True)
class TerminalRecord:
    terminal_id: str
    population_instance_id: str
    kind: TerminalKind
    payload_digest: str
    reason_code: str | None
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_text(self.terminal_id, "terminal_id")
        _validate_text(self.population_instance_id, "terminal population_instance_id")
        if not is_sha256_hex(self.payload_digest) or self.payload_digest == "0" * 64:
            raise ScorecardError("terminal payload_digest must be nonzero lowercase sha256")
        if self.reason_code is not None:
            _validate_text(self.reason_code, "terminal reason_code")
        if self.kind in {
            TerminalKind.ABSTAINED,
            TerminalKind.REJECTED,
            TerminalKind.SHADOW_UNTRADEABLE,
            TerminalKind.EXPIRED,
            TerminalKind.WITHDRAWN_PRE_SEND,
            TerminalKind.RISK_DENIED,
            TerminalKind.EXECUTION_REJECTED,
            TerminalKind.CANCELED_NO_FILL,
            TerminalKind.UNKNOWN_SUBMIT_UNRECONCILED,
        } and self.reason_code is None:
            raise ScorecardError("refusal/unresolved terminal requires a typed reason_code")
        _validate_texts(self.evidence_refs, "terminal evidence_refs")


@dataclass(frozen=True)
class MetricValue:
    metric_id: str
    metric_class: MetricClass
    population: Population | None
    value_type: str
    value: str | int | None
    unit: str
    availability: Availability
    reason_code: str | None
    zero_proof: dict[str, Any] | None
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_text(self.metric_id, "metric_id")
        _validate_text(self.value_type, "value_type")
        _validate_text(self.unit, "metric unit")
        if isinstance(self.value, bool) or isinstance(self.value, float):
            raise ScorecardError("metric values must be exact int, canonical string, or null")
        if self.value is not None and not isinstance(self.value, (str, int)):
            raise ScorecardError("metric value has an unsupported type")
        if isinstance(self.value, str) and not self.value:
            raise ScorecardError("metric string value must not be empty")
        if self.value_type not in {"INTEGER", "DECIMAL", "TEXT"}:
            raise ScorecardError("metric value_type must be INTEGER, DECIMAL, or TEXT")
        if self.value is not None:
            _validate_metric_representation(self.value, self.value_type)
        if self.metric_class is MetricClass.COUNT and (
            self.value_type != "INTEGER" or self.unit != "COUNT"
        ):
            raise ScorecardError("COUNT metrics require INTEGER value_type and COUNT unit")
        if self.metric_class is MetricClass.ECONOMIC and self.population is None:
            raise ScorecardError("economic metrics require one explicit population")
        if self.value is None:
            if self.availability in {Availability.OBSERVED, Availability.DERIVED}:
                raise ScorecardError("observed/derived metric cannot carry a null value")
            if self.reason_code is None:
                raise ScorecardError("null metric requires a typed reason_code")
        elif self.availability not in {Availability.OBSERVED, Availability.DERIVED}:
            raise ScorecardError("non-null metric requires OBSERVED or DERIVED availability")
        if self.reason_code is not None:
            _validate_text(self.reason_code, "metric reason_code")
        numeric_zero = self.value_type in {"INTEGER", "DECIMAL"} and _is_zero(self.value)
        if numeric_zero:
            _validate_zero_proof(self.zero_proof)
        elif self.zero_proof is not None:
            raise ScorecardError("zero_proof is legal only for an observed numeric zero")
        _validate_texts(
            self.evidence_refs,
            "metric evidence_refs",
            allow_empty=self.availability not in {Availability.OBSERVED, Availability.DERIVED},
        )


def _validate_text(value: object, name: str) -> None:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ScorecardError(f"{name} must be non-empty canonical text")


def _validate_texts(values: tuple[str, ...], name: str, *, allow_empty: bool = False) -> None:
    if not isinstance(values, tuple):
        raise ScorecardError(f"{name} must be an immutable tuple")
    if not values and not allow_empty:
        raise ScorecardError(f"{name} must not be empty")
    for value in values:
        _validate_text(value, name)
    if len(set(values)) != len(values):
        raise ScorecardError(f"{name} must not contain duplicates")


def _validate_optional_bool(value: object, name: str) -> None:
    if value is not None and type(value) is not bool:
        raise ScorecardError(f"{name} must be an exact boolean or null")


def _validate_nonnegative_int(value: object, name: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
        or value > 2**63 - 1
    ):
        raise ScorecardError(f"{name} must be a signed-64 non-negative exact integer")


def _validate_metric_representation(value: str | int, value_type: str) -> None:
    if value_type == "INTEGER":
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
            or value > 2**63 - 1
        ):
            raise ScorecardError("INTEGER metric must be a signed-64 non-negative exact integer")
        return
    if value_type == "DECIMAL":
        if not isinstance(value, str) or not _is_canonical_decimal(value):
            raise ScorecardError("DECIMAL metric must be a canonical non-exponent decimal string")
        return
    if not isinstance(value, str):
        raise ScorecardError("TEXT metric must be a string")


def _is_canonical_decimal(value: str) -> bool:
    negative = value.startswith("-")
    body = value[1:] if negative else value
    if not body or "e" in body.lower() or "+" in body or body.count(".") > 1:
        return False
    whole, separator, fraction = body.partition(".")
    if not whole or any(character not in "0123456789" for character in whole):
        return False
    if len(whole) > 1 and whole.startswith("0"):
        return False
    if separator:
        if not fraction or any(character not in "0123456789" for character in fraction):
            return False
        if fraction.endswith("0"):
            return False
    if negative and set(whole + fraction) == {"0"}:
        return False
    return True


def _is_zero(value: str | int | None) -> bool:
    if value == 0:
        return True
    if not isinstance(value, str):
        return False
    if value.startswith("-"):
        value = value[1:]
    if not value:
        return False
    if "." in value:
        whole, fraction = value.split(".", 1)
        return bool(whole) and bool(fraction) and set(whole + fraction) == {"0"}
    return set(value) == {"0"}


def _validate_zero_proof(proof: dict[str, Any] | None) -> None:
    if not isinstance(proof, dict):
        raise ScorecardError("observed numeric zero requires zero_proof")
    expected = {"query_digest", "source_cut_digest", "source_completeness", "watermark"}
    if set(proof) != expected:
        raise ScorecardError("zero_proof fields are not the closed required set")
    for name in ("query_digest", "source_cut_digest"):
        value = proof[name]
        if not is_sha256_hex(value) or value == "0" * 64:
            raise ScorecardError(f"zero_proof {name} must be nonzero lowercase sha256")
    if proof["source_completeness"] != "COMPLETE":
        raise ScorecardError("zero_proof source_completeness must be COMPLETE")
    _validate_text(proof["watermark"], "zero_proof watermark")
