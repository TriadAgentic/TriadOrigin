"""The nine W25 evidence PROJECTION VIEWS (B08 — RC3 ``WIRE-W25-01..08``; contract ``evidence_view.v2``).

The read-only projection views the B08 checklist names — **offsets · watermarks · quality · lineage ·
funnel · divergence · replay · receipt · readiness** — each a bounded, honest-null read-only
projection over already-computed ledger / journal / checkpoint / receipt / comparator state into the
ONE shared :class:`triad_origin.read_faces.envelope.ReadFaceEnvelope`. They are DISTINCT from the six
RC4 §L6 read faces (:mod:`triad_origin.read_faces.faces`): the faces project the four-plane LEVER
substrate; these views project the EVIDENCE substrate (the tape offsets, the watermarks, the
lineage, the candidate funnel, the divergence records, the replay/evidence receipts, and the
bootstrap readiness).

**THE W25 FAILURE LAW** (``docs/control/rc3_effective_control_bundle.json`` W25, verbatim):
"Unavailable dependency returns unavailable; no empty green and no control side effect." and
(``ordering_idempotency``) "Projection rebuilds from ledgers; response names plane, source, freshness
and completeness." Every view therefore returns the shared envelope, which NAMES its :attr:`source`,
its freshness (:attr:`as_of_us` snapshot instant + honest-null :attr:`watermark_us`), its
:attr:`completeness`, and its :attr:`plane`; an absent dependency is an ``UNAVAILABLE`` envelope
(never a fabricated zero), and a present-but-silent fact is ``NOT_MEASURABLE`` (RC3
``RC3-AC-WIRE-W08A-05`` / ``WIRE-W20-05``: "Missing lineage produces NOT_MEASURABLE, never estimated
win/loss") — the two are deliberately distinct.

**THE NINE VIEWS:**

* **offsets** (:func:`get_offsets_view`) — per-partition input/output segment offsets + state sequence
  (from :class:`triad_origin.journal.ReplayContext` / :class:`triad_origin.checkpoint.Checkpoint` /
  ledger records). A missing offset field is NAMED absent, never fabricated to 0.
* **watermarks** (:func:`get_watermarks_view`) — per-partition completeness-through watermark
  (:class:`triad_origin.clock_watermark.Watermark`): an un-advanced watermark (the ``-1`` sentinel)
  is ``NOT_MEASURABLE`` ("no finalized event yet"), never a fabricated ``0`` timestamp — RC4
  ``LEV-V-0124`` "Return both timestamps and mismatch; no single green liveness claim".
* **quality** (:func:`get_quality_view`) — the caller-ATTESTED per-envelope quality dict. ORIGIN
  computes NO quality of its own (it has no quality-compute source); an absent attestation is
  ``UNAVAILABLE`` and an empty one is ``NOT_MEASURABLE`` — a quality fact is only ever what a producer
  stamped, echoed verbatim, never a computed or defaulted value.
* **lineage** (:func:`get_lineage_view`) — the structure lifecycle map
  (:class:`triad_origin.structures.lifecycle_reducer.LifecycleReducer` state). A queried structure
  with no recorded lineage is ``NOT_MEASURABLE`` (missing lineage, never estimated).
* **funnel** (:func:`get_funnel_view`) — the candidate-publication funnel over an ordered event
  stream (``CANDIDATE_PUBLISHED`` / ``CANDIDATE_PUBLICATION_REFUSED``), with a per-conjunct refusal
  breakdown over the 12 ``TRADEABILITY_REQUIREMENTS`` as NAMED ZEROS (a conjunct that never failed is
  a measured 0, honest, distinct from "not observed"). Poison-safe: a malformed event is counted
  ``unclassified``, never raised on.
* **divergence** (:func:`get_divergence_view`) — a caller-supplied ``divergence_record.v1`` stream +
  a per-class roll-up over the 8 ``DIVERGENCE_CLASSES``. An unrecognized/ambiguous class stays
  explicit ``NOT_MEASURABLE`` — RC3 ``RC3-AC-WIRE-W08A-05`` "no auto-resolution".
* **replay** (:func:`get_replay_view`) — caller-supplied ``replay_receipt.v1`` payload(s), each
  projected to its declared identity fields with missing fields NAMED.
* **receipt** (:func:`get_receipt_view`) — a caller-supplied evidence/gate receipt payload, projected
  with an honest as-of freshness fact (``expired_as_of``) — never a re-derived PASS verdict.
* **readiness** (:func:`get_readiness_view`) — **the row ``CTRL-B08-001``**: the bootstrap readiness
  PLUS the four still-open evidence dimensions (source freshness · coverage · lease validity · estate
  activation), each honest-null unless a caller supplies real evidence. The view NEVER claims more
  than ``READY_NO_AUTHORITY`` ("keep ``READY_NO_AUTHORITY`` explicitly narrow" —
  ``docs/plan/05_RC2_CONFLICT_REGISTER.md`` row ``CTRL-B08-001``): even with every evidence dimension
  supplied positively, ``authority`` stays ``NONE`` — a read face can add evidence, never authority.

**Not a vendored contract** (same documented reading judgment as the envelope —
``docs/plan/09_OPEN_QUESTIONS.md`` row E37): W25's ``contract: "evidence_view.v2"`` is a logical
binding, so these views return the INTERNAL
:class:`triad_origin.read_faces.envelope.ReadFaceEnvelope` shape whose authority is
:func:`triad_origin.read_faces.envelope.validate`, versioned by ``EVIDENCE_VIEW_VERSION`` — no
``contracts/`` JSON schema is added or re-pinned by this module.

Pure and side-effect-free: no clock, no network, no I/O, no randomness, no float, no control verb, no
credential. Every 'current' fact (``as_of_us``, ``watermark_us``, the projected state) is
caller-supplied; a view arms, activates, and switches nothing — it only projects (Doc 04 §04.17 DARK
posture).
"""

from __future__ import annotations

from typing import Any

from .. import timings
from ..control import comparator, shadow_ledger
from ..health import Readiness
from ..structures import candidate_publisher
from . import envelope as ev
# The shared bounded-read + type-guard helpers are single-sourced with the six faces (defined in
# :mod:`triad_origin.read_faces.faces`) — reused here rather than duplicated, so one pagination /
# state-guard law governs every B08 surface.
from .faces import _is_plain_int, _paginate, _require_state_dict

# ---------------------------------------------------------------------------------------------
# The nine view names — the ONE in-repo spelling (checklist / e2e stage / MCP surface name the same).
# ---------------------------------------------------------------------------------------------
VIEW_OFFSETS = "offsets"
VIEW_WATERMARKS = "watermarks"
VIEW_QUALITY = "quality"
VIEW_LINEAGE = "lineage"
VIEW_FUNNEL = "funnel"
VIEW_DIVERGENCE = "divergence"
VIEW_REPLAY = "replay"
VIEW_RECEIPT = "receipt"
VIEW_READINESS = "readiness"
VIEW_NAMES = (
    VIEW_OFFSETS, VIEW_WATERMARKS, VIEW_QUALITY, VIEW_LINEAGE, VIEW_FUNNEL, VIEW_DIVERGENCE,
    VIEW_REPLAY, VIEW_RECEIPT, VIEW_READINESS,
)

# Source-identity labels (RC3 W25 "response names ... source ..."). Names of the in-repo state a view
# projects; labels, not filesystem paths.
_SRC_OFFSETS = "journal.ReplayContext / checkpoint.Checkpoint / ledger.Record offsets"
_SRC_WATERMARKS = "clock_watermark.Watermark completeness-through state"
_SRC_QUALITY = "caller-attested per-envelope _quality (ORIGIN computes no quality)"
_SRC_LINEAGE = "structures.lifecycle_reducer.LifecycleReducer.state.structures"
_SRC_FUNNEL = "structures.candidate_publisher CANDIDATE_PUBLISHED/CANDIDATE_PUBLICATION_REFUSED events"
_SRC_DIVERGENCE = "control.comparator triad.divergence_record.v1 stream"
_SRC_REPLAY = "control.replay_runner triad.replay_receipt.v1 payload(s)"
_SRC_RECEIPT = "evidence receipt payload (triad.evidence_receipt.v2 / triad.gate_receipt.v2)"
_SRC_READINESS = "health.Readiness bootstrap + the CTRL-B08-001 evidence dimensions"

# Named absence reasons — every honest-null facet NAMES its reason; never a fabricated value.
_REASON_NO_OFFSET_SOURCE = "NO_PARTITION_OFFSET_SOURCE_SUPPLIED"
_REASON_NO_WATERMARK_SOURCE = "NO_WATERMARK_SOURCE_SUPPLIED"
_REASON_WATERMARK_NOT_ADVANCED = "WATERMARK_NOT_YET_ADVANCED_NO_FINALIZED_EVENT"
_REASON_QUALITY_NOT_STAMPED = "QUALITY_ATTESTATION_ABSENT_ORIGIN_COMPUTES_NO_QUALITY"
_REASON_QUALITY_EMPTY = "QUALITY_ATTESTATION_PRESENT_BUT_EMPTY_NO_QUALITY_FACT"
_REASON_NO_LINEAGE_SOURCE = "NO_STRUCTURE_LIFECYCLE_SOURCE_SUPPLIED"
_REASON_STRUCTURE_NO_LINEAGE = "STRUCTURE_HAS_NO_RECORDED_LINEAGE_NOT_MEASURABLE"
_REASON_NO_FUNNEL_SOURCE = "NO_CANDIDATE_EVENT_STREAM_SUPPLIED"
_REASON_NO_DIVERGENCE_SOURCE = "NO_DIVERGENCE_RECORD_STREAM_SUPPLIED"
_REASON_DIVERGENCE_UNCLASSIFIED = "DIVERGENCE_CLASS_UNRECOGNIZED_NOT_MEASURABLE_NO_AUTO_RESOLUTION"
_REASON_NO_REPLAY_SOURCE = "NO_REPLAY_RECEIPT_SUPPLIED"
_REASON_NO_RECEIPT_SOURCE = "NO_EVIDENCE_RECEIPT_SUPPLIED"
_REASON_RECEIPT_EXPIRY_UNKNOWN = "RECEIPT_EXPIRY_OR_AS_OF_NOT_AN_INTEGER_FRESHNESS_NOT_MEASURABLE"
_REASON_NO_READINESS_SOURCE = "NO_BOOTSTRAP_READINESS_SUPPLIED"
_REASON_READINESS_UNRECOGNIZED = "BOOTSTRAP_READINESS_NOT_A_KNOWN_READINESS_VALUE"
# The four CTRL-B08-001 still-open evidence dimensions — each honest-null unless a caller supplies it.
_REASON_FRESHNESS_ABSENT = "SOURCE_FRESHNESS_EVIDENCE_NOT_SUPPLIED_CTRL_B08_001"
_REASON_FRESHNESS_UNKNOWN_BOUND = "SOURCE_FRESHNESS_BOUND_NOT_A_KNOWN_TIMING_NOT_MEASURABLE"
_REASON_COVERAGE_ABSENT = "COVERAGE_EVIDENCE_NOT_SUPPLIED_CTRL_B08_001"
_REASON_COVERAGE_MALFORMED = "COVERAGE_PAIR_NOT_TWO_NON_NEGATIVE_INTEGERS_NOT_MEASURABLE"
_REASON_LEASE_ABSENT = "LEASE_VALIDITY_EVIDENCE_NOT_SUPPLIED_CTRL_B08_001"
_REASON_ESTATE_ABSENT = "ESTATE_ACTIVATION_NOT_OBSERVED_HERE_CTRL_B08_001"

# Reuse the ONE honest status vocabulary (no drift) for facet sub-statuses inside a value dict.
_AVAILABLE = ev.STATUS_AVAILABLE
_UNAVAILABLE = ev.STATUS_UNAVAILABLE
_NOT_MEASURABLE = ev.STATUS_NOT_MEASURABLE

# The fixed, deterministically-ordered offset fields a partition offset fact may carry.
_OFFSET_FIELDS = (
    "input_segment", "input_offset", "output_segment", "output_offset", "state_seq",
    "last_transition_id",
)

# ORIGIN's structural readiness ceiling — a read view can add EVIDENCE, never AUTHORITY (CLAUDE.md:
# "A healthy current build reaches only READY_NO_AUTHORITY"; CTRL-B08-001 "keep it explicitly narrow").
_READY_CEILING = Readiness.READY_NO_AUTHORITY.value
_KNOWN_READINESS = tuple(r.value for r in Readiness)


def _unavailable_facet(reason: str) -> dict:
    return {"status": _UNAVAILABLE, "reason": reason}


def _not_measurable_facet(reason: str) -> dict:
    return {"status": _NOT_MEASURABLE, "reason": reason}


def _require_ordered(name: str, value: object) -> list:
    """The caller's OWN envelope shape — a stream must be an ordered list/tuple. (Raising here is
    the caller-envelope defect the poison-envelope law permits; row CONTENT never raises.)"""
    if not isinstance(value, (list, tuple)):
        raise ev.ReadFaceEnvelopeError(
            f"{name} must be an ordered list/tuple or None; got {type(value).__name__}")
    return list(value)


# ---------------------------------------------------------------------------------------------
# offsets · WIRE-W25 · input/output segment offsets + state sequence
# ---------------------------------------------------------------------------------------------
def _offset_row(partition: str, fact: object) -> dict:
    if not isinstance(fact, dict):
        raise ev.ReadFaceEnvelopeError(
            f"partitions[{partition!r}] must be a dict of offset facts; got {type(fact).__name__}")
    offsets = {field: fact.get(field) for field in _OFFSET_FIELDS}
    missing = [field for field in _OFFSET_FIELDS if fact.get(field) is None]
    return {"partition": partition, "offsets": offsets, "missing_fields": missing}


def get_offsets_view(
    *,
    partitions: dict | None,
    as_of_us: int,
    watermark_us: int | None = None,
    limit: int | None = None,
    after: str | None = None,
) -> ev.ReadFaceEnvelope:
    """Project per-partition tape offsets (input/output segment + state sequence). A missing offset
    field is NAMED absent, never fabricated to 0; an absent source is ``UNAVAILABLE``."""
    if partitions is None:
        return ev.unavailable(
            face=VIEW_OFFSETS, source=_SRC_OFFSETS, as_of_us=as_of_us, watermark_us=watermark_us,
            plane=ev.CONTROL_PLANE, reason=_REASON_NO_OFFSET_SOURCE)
    _require_state_dict(partitions, "partitions")
    ordered = sorted((name, partitions[name]) for name in partitions)
    page, cursor = _paginate(ordered, limit=limit, after=after)
    rows = [_offset_row(name, fact) for name, fact in page]
    value = {"partitions": rows, "partition_count": len(partitions), "offset_fields": list(_OFFSET_FIELDS)}
    return ev.available(
        face=VIEW_OFFSETS, source=_SRC_OFFSETS, as_of_us=as_of_us, watermark_us=watermark_us,
        plane=ev.CONTROL_PLANE, value=value, returned=len(rows), limit=limit, cursor=cursor)


# ---------------------------------------------------------------------------------------------
# watermarks · WIRE-W25 · completeness-through watermark (both timestamps, never one green claim)
# ---------------------------------------------------------------------------------------------
def _watermark_row(partition: str, fact: object) -> dict:
    if not isinstance(fact, dict):
        raise ev.ReadFaceEnvelopeError(
            f"watermarks[{partition!r}] must be a dict; got {type(fact).__name__}")
    completed = fact.get("completed_through_us")
    allowed = fact.get("allowed_lateness_us")
    # The Watermark ``-1`` sentinel (or an absent value) means "no finalized event yet" — that is
    # NOT_MEASURABLE, never a fabricated 0 timestamp (LEV-V-0124 / no empty green).
    if _is_plain_int(completed) and completed >= 0:
        completed_facet = {"status": _AVAILABLE, "value": completed}
        advanced = True
    else:
        completed_facet = _not_measurable_facet(_REASON_WATERMARK_NOT_ADVANCED)
        advanced = False
    return {
        "partition": partition,
        "completed_through_us": completed_facet,
        "allowed_lateness_us": allowed if _is_plain_int(allowed) else None,
        "advanced": advanced,
        # The causal clocks, echoed verbatim when supplied (never re-derived).
        "clocks": fact.get("clocks"),
    }


def get_watermarks_view(
    *,
    watermarks: dict | None,
    as_of_us: int,
    watermark_us: int | None = None,
    limit: int | None = None,
    after: str | None = None,
) -> ev.ReadFaceEnvelope:
    """Project per-partition completeness-through watermarks. An un-advanced watermark is
    ``NOT_MEASURABLE`` (no finalized event), never a fabricated 0; an absent source is
    ``UNAVAILABLE``."""
    if watermarks is None:
        return ev.unavailable(
            face=VIEW_WATERMARKS, source=_SRC_WATERMARKS, as_of_us=as_of_us, watermark_us=watermark_us,
            plane=ev.CONTROL_PLANE, reason=_REASON_NO_WATERMARK_SOURCE)
    _require_state_dict(watermarks, "watermarks")
    ordered = sorted((name, watermarks[name]) for name in watermarks)
    page, cursor = _paginate(ordered, limit=limit, after=after)
    rows = [_watermark_row(name, fact) for name, fact in page]
    value = {"partitions": rows, "partition_count": len(watermarks)}
    return ev.available(
        face=VIEW_WATERMARKS, source=_SRC_WATERMARKS, as_of_us=as_of_us, watermark_us=watermark_us,
        plane=ev.CONTROL_PLANE, value=value, returned=len(rows), limit=limit, cursor=cursor)


# ---------------------------------------------------------------------------------------------
# quality · WIRE-W25 · caller-ATTESTED quality (ORIGIN computes no quality)
# ---------------------------------------------------------------------------------------------
def get_quality_view(
    *,
    quality: dict | None,
    as_of_us: int,
    plane: str | None = None,
    watermark_us: int | None = None,
) -> ev.ReadFaceEnvelope:
    """Project the caller-ATTESTED per-envelope quality dict verbatim. ORIGIN has no quality-compute
    source, so an absent attestation is ``UNAVAILABLE`` and an empty one is ``NOT_MEASURABLE`` — a
    quality fact is only ever what a producer stamped, never a computed or defaulted value."""
    if quality is None:
        return ev.unavailable(
            face=VIEW_QUALITY, source=_SRC_QUALITY, as_of_us=as_of_us, watermark_us=watermark_us,
            plane=plane, reason=_REASON_QUALITY_NOT_STAMPED)
    _require_state_dict(quality, "quality")
    if len(quality) == 0:
        return ev.not_measurable(
            face=VIEW_QUALITY, source=_SRC_QUALITY, as_of_us=as_of_us, watermark_us=watermark_us,
            plane=plane, reason=_REASON_QUALITY_EMPTY)
    value = {
        "attested_quality": quality,
        "attested_keys": sorted(quality),
        # The load-bearing honesty: ORIGIN reports the producer's stamp; it computes no quality itself.
        "attested_not_computed": True,
    }
    return ev.available(
        face=VIEW_QUALITY, source=_SRC_QUALITY, as_of_us=as_of_us, watermark_us=watermark_us,
        plane=plane, value=value, returned=1)


# ---------------------------------------------------------------------------------------------
# lineage · WIRE-W25 · structure lifecycle (missing lineage -> NOT_MEASURABLE)
# ---------------------------------------------------------------------------------------------
def get_lineage_view(
    *,
    structures_state: dict | None,
    as_of_us: int,
    structure_id: str | None = None,
    watermark_us: int | None = None,
    limit: int | None = None,
    after: str | None = None,
) -> ev.ReadFaceEnvelope:
    """Project the structure lifecycle map. A queried ``structure_id`` with no recorded lineage is
    ``NOT_MEASURABLE`` (missing lineage, never estimated — WIRE-W20-05); an absent source is
    ``UNAVAILABLE``."""
    if structures_state is None:
        return ev.unavailable(
            face=VIEW_LINEAGE, source=_SRC_LINEAGE, as_of_us=as_of_us, watermark_us=watermark_us,
            plane=ev.CONTROL_PLANE, reason=_REASON_NO_LINEAGE_SOURCE)
    _require_state_dict(structures_state, "structures_state")
    structures = structures_state.get("structures", {})
    if not isinstance(structures, dict):
        raise ev.ReadFaceEnvelopeError("structures_state['structures'] must be a dict")

    if structure_id is not None:
        if not isinstance(structure_id, str) or structure_id == "":
            raise ev.ReadFaceEnvelopeError("structure_id must be a non-empty string or None")
        lineage = structures.get(structure_id)
        if lineage is None:
            # The source IS present; this structure simply has no recorded lineage — missing lineage
            # is NOT_MEASURABLE, never an estimated / default state.
            return ev.not_measurable(
                face=VIEW_LINEAGE, source=_SRC_LINEAGE, as_of_us=as_of_us, watermark_us=watermark_us,
                plane=ev.CONTROL_PLANE, reason=_REASON_STRUCTURE_NO_LINEAGE)
        value = {
            "structure_id": structure_id, "lineage": lineage,
            "last_event_id": structures_state.get("last_event_id")}
        return ev.available(
            face=VIEW_LINEAGE, source=_SRC_LINEAGE, as_of_us=as_of_us, watermark_us=watermark_us,
            plane=ev.CONTROL_PLANE, value=value, returned=1)

    ordered = sorted((sid, structures[sid]) for sid in structures)
    page, cursor = _paginate(ordered, limit=limit, after=after)
    rows = [{"structure_id": sid, "lineage": lineage} for sid, lineage in page]
    value = {
        "structures": rows,
        "structure_count": len(structures),
        "last_event_id": structures_state.get("last_event_id"),
    }
    return ev.available(
        face=VIEW_LINEAGE, source=_SRC_LINEAGE, as_of_us=as_of_us, watermark_us=watermark_us,
        plane=ev.CONTROL_PLANE, value=value, returned=len(rows), limit=limit, cursor=cursor)


# ---------------------------------------------------------------------------------------------
# funnel · WIRE-W25 · candidate-publication funnel + named zeros (poison-safe)
# ---------------------------------------------------------------------------------------------
def get_funnel_view(
    *,
    events: list | None,
    as_of_us: int,
    plane: str | None = None,
    watermark_us: int | None = None,
) -> ev.ReadFaceEnvelope:
    """Project the candidate-publication funnel over an ordered event stream, with a per-conjunct
    refusal breakdown over the 12 ``TRADEABILITY_REQUIREMENTS`` as NAMED ZEROS (a conjunct that never
    failed is a measured 0, honest). An empty (present) stream is a measured zero funnel; an absent
    stream is ``UNAVAILABLE``. Poison-safe: a malformed event is counted ``unclassified``, never
    raised on (only the caller's own envelope shape may raise)."""
    if events is None:
        return ev.unavailable(
            face=VIEW_FUNNEL, source=_SRC_FUNNEL, as_of_us=as_of_us, watermark_us=watermark_us,
            plane=plane, reason=_REASON_NO_FUNNEL_SOURCE)
    ordered = _require_ordered("events", events)

    published = 0
    refused = 0
    shadow_untradeable = 0
    unclassified = 0
    # Every conjunct is a NAMED key initialised to 0 — a conjunct that never fails is a measured zero,
    # never an omission (RC3 "no empty green"; the candidate funnel's named-zeros law).
    failed_by_conjunct = {name: 0 for name in shadow_ledger.TRADEABILITY_REQUIREMENTS}
    for event in ordered:
        if not isinstance(event, dict):
            unclassified += 1
            continue
        kind = event.get("event_kind")
        if kind == candidate_publisher.CANDIDATE_PUBLISHED:
            published += 1
        elif kind == candidate_publisher.CANDIDATE_PUBLICATION_REFUSED:
            refused += 1
            if event.get("reason_code") == shadow_ledger.MARKER_SHADOW_UNTRADEABLE:
                shadow_untradeable += 1
            failed = event.get("failed_conjuncts")
            if isinstance(failed, (list, tuple)):
                for conjunct in failed:
                    if conjunct in failed_by_conjunct:
                        failed_by_conjunct[conjunct] += 1
        else:
            unclassified += 1

    value = {
        "events_considered": len(ordered),
        "published": published,
        "refused": refused,
        "shadow_untradeable_refusals": shadow_untradeable,
        "unclassified": unclassified,
        "failed_by_conjunct": failed_by_conjunct,
        "conjunct_order": list(shadow_ledger.TRADEABILITY_REQUIREMENTS),
        # A refusal here is the mandatory SHADOW fork of an ORIGIN publication, never a rejected
        # trading decision — named, so the funnel is never misread as a money verdict.
        "shadow_fork_reason": candidate_publisher.ORIGIN_PUBLICATION_SENTINEL_REASON,
    }
    return ev.available(
        face=VIEW_FUNNEL, source=_SRC_FUNNEL, as_of_us=as_of_us, watermark_us=watermark_us,
        plane=plane, value=value, returned=1)


# ---------------------------------------------------------------------------------------------
# divergence · WIRE-W25 (RC3-WOP-004) · classified stream + per-class roll-up (no auto-resolution)
# ---------------------------------------------------------------------------------------------
def _divergence_row(record: object) -> dict:
    if not isinstance(record, dict):
        # Ambiguous / unparseable content stays explicit NOT_MEASURABLE — never dropped, never
        # auto-resolved (RC3-AC-WIRE-W08A-05).
        return {"status": _NOT_MEASURABLE, "reason": _REASON_DIVERGENCE_UNCLASSIFIED, "record": None}
    klass = record.get("divergence_class")
    if klass not in comparator.DIVERGENCE_CLASSES:
        return {
            "status": _NOT_MEASURABLE, "reason": _REASON_DIVERGENCE_UNCLASSIFIED,
            "divergence_id": record.get("divergence_id"), "divergence_class": klass}
    return {
        "status": _AVAILABLE,
        "divergence_id": record.get("divergence_id"),
        "divergence_class": klass,
        "comparison_axis": record.get("comparison_axis"),
        "input_offset": record.get("input_offset"),
        "control_ref": record.get("control_ref"),
        "treatment_ref": record.get("treatment_ref"),
        "detail": record.get("detail"),
    }


def get_divergence_view(
    *,
    records: list | None,
    as_of_us: int,
    plane: str | None = None,
    watermark_us: int | None = None,
    limit: int | None = None,
    after: str | None = None,
) -> ev.ReadFaceEnvelope:
    """Project a ``divergence_record.v1`` stream + a per-class roll-up over the 8
    ``DIVERGENCE_CLASSES`` (named zeros). An unrecognized/ambiguous class stays explicit
    ``NOT_MEASURABLE`` ("no auto-resolution"); an absent source is ``UNAVAILABLE``."""
    if records is None:
        return ev.unavailable(
            face=VIEW_DIVERGENCE, source=_SRC_DIVERGENCE, as_of_us=as_of_us, watermark_us=watermark_us,
            plane=plane, reason=_REASON_NO_DIVERGENCE_SOURCE)
    ordered = _require_ordered("records", records)

    # The roll-up is computed over the WHOLE stream (never just the page) — the inventory-face
    # precedent. Every class is a NAMED key at 0 (a class never seen is a measured zero).
    by_class = {name: 0 for name in comparator.DIVERGENCE_CLASSES}
    not_measurable = 0
    projected = [_divergence_row(record) for record in ordered]
    for row in projected:
        if row["status"] == _AVAILABLE:
            by_class[row["divergence_class"]] += 1
        else:
            not_measurable += 1

    page, cursor = _paginate(projected, limit=limit, after=after)
    value = {
        "records": page,
        "records_considered": len(ordered),
        "by_class": by_class,
        "class_order": list(comparator.DIVERGENCE_CLASSES),
        "not_measurable": not_measurable,
    }
    return ev.available(
        face=VIEW_DIVERGENCE, source=_SRC_DIVERGENCE, as_of_us=as_of_us, watermark_us=watermark_us,
        plane=plane, value=value, returned=len(page), limit=limit, cursor=cursor)


# ---------------------------------------------------------------------------------------------
# replay · WIRE-W25 · replay_receipt.v1 identity fields (missing fields NAMED)
# ---------------------------------------------------------------------------------------------
_REPLAY_FIELDS = (
    "receipt_id", "fidelity_class", "input_offsets", "checkpoint_identity", "run_seed", "platform",
    "state_checksums", "signer",
)
_REPLAY_COUNT_FIELDS = ("input_segment_hashes", "output_segment_hashes", "divergence_links")


def _replay_row(receipt: object) -> dict:
    if not isinstance(receipt, dict):
        return {"status": _NOT_MEASURABLE, "reason": _REASON_NO_REPLAY_SOURCE, "receipt": None}
    projected: dict[str, Any] = {field: receipt.get(field) for field in _REPLAY_FIELDS}
    for field in _REPLAY_COUNT_FIELDS:
        seq = receipt.get(field)
        projected[f"{field}_count"] = len(seq) if isinstance(seq, (list, tuple)) else None
    projected["test_suite_result_present"] = isinstance(receipt.get("test_suite_result"), dict)
    projected["missing_fields"] = [
        field for field in _REPLAY_FIELDS if receipt.get(field) is None]
    projected["status"] = _AVAILABLE
    return projected


def get_replay_view(
    *,
    receipts: list | None,
    as_of_us: int,
    watermark_us: int | None = None,
    limit: int | None = None,
    after: str | None = None,
) -> ev.ReadFaceEnvelope:
    """Project ``replay_receipt.v1`` payload(s) to their declared identity fields, with missing
    fields NAMED. An absent source is ``UNAVAILABLE``; an empty (present) list is a measured zero."""
    if receipts is None:
        return ev.unavailable(
            face=VIEW_REPLAY, source=_SRC_REPLAY, as_of_us=as_of_us, watermark_us=watermark_us,
            plane=ev.CONTROL_PLANE, reason=_REASON_NO_REPLAY_SOURCE)
    ordered = _require_ordered("receipts", receipts)
    page, cursor = _paginate([_replay_row(r) for r in ordered], limit=limit, after=after)
    value = {"receipts": page, "receipts_considered": len(ordered)}
    return ev.available(
        face=VIEW_REPLAY, source=_SRC_REPLAY, as_of_us=as_of_us, watermark_us=watermark_us,
        plane=ev.CONTROL_PLANE, value=value, returned=len(page), limit=limit, cursor=cursor)


# ---------------------------------------------------------------------------------------------
# receipt · WIRE-W25 · evidence/gate receipt fields + as-of freshness (never a re-derived PASS)
# ---------------------------------------------------------------------------------------------
def get_receipt_view(
    *,
    receipt: dict | None,
    as_of_us: int,
    watermark_us: int | None = None,
) -> ev.ReadFaceEnvelope:
    """Project a caller-supplied evidence/gate receipt's declared fields + an honest as-of freshness
    fact (``expired_as_of``). It projects the receipt's DECLARED ``result``; it does NOT re-derive a
    PASS verdict (that is the contract validator's job). An absent receipt is ``UNAVAILABLE``."""
    if receipt is None:
        return ev.unavailable(
            face=VIEW_RECEIPT, source=_SRC_RECEIPT, as_of_us=as_of_us, watermark_us=watermark_us,
            plane=ev.CONTROL_PLANE, reason=_REASON_NO_RECEIPT_SOURCE)
    _require_state_dict(receipt, "receipt")

    evidence_ids = receipt.get("evidence_ids")
    evidence_sha256s = receipt.get("evidence_sha256s")
    expires = receipt.get("expires_at_us")
    observed = receipt.get("observed_at_us")
    builder = receipt.get("builder")
    reviewer = receipt.get("reviewer")

    # An honest freshness value-add (the CTRL-B08-001 spirit): is this receipt expired AT the
    # caller-supplied snapshot instant? NOT_MEASURABLE when either bound is not an integer.
    if _is_plain_int(expires) and _is_plain_int(as_of_us):
        expired_facet = {"status": _AVAILABLE, "value": as_of_us > expires}
    else:
        expired_facet = _not_measurable_facet(_REASON_RECEIPT_EXPIRY_UNKNOWN)

    value = {
        "receipt_id": receipt.get("receipt_id"),
        "scope": receipt.get("scope"),
        # The DECLARED result — echoed, never a re-derived verdict.
        "declared_result": receipt.get("result"),
        "builder": builder,
        "reviewer": reviewer,
        # A pure, honest comparison (the independent-review discipline) — never an authority claim.
        "builder_reviewer_distinct": (
            None if builder is None or reviewer is None else builder != reviewer),
        "evidence_ids_count": len(evidence_ids) if isinstance(evidence_ids, (list, tuple)) else None,
        "evidence_sha256s_count": (
            len(evidence_sha256s) if isinstance(evidence_sha256s, (list, tuple)) else None),
        "observed_at_us": observed if _is_plain_int(observed) else None,
        "expires_at_us": expires if _is_plain_int(expires) else None,
        "signature_present": bool(receipt.get("signature")),
        "expired_as_of": expired_facet,
    }
    return ev.available(
        face=VIEW_RECEIPT, source=_SRC_RECEIPT, as_of_us=as_of_us, watermark_us=watermark_us,
        plane=ev.CONTROL_PLANE, value=value, returned=1)


# ---------------------------------------------------------------------------------------------
# readiness · WIRE-W25 · the CTRL-B08-001 row: bootstrap + four evidence dims, never wider authority
# ---------------------------------------------------------------------------------------------
def _freshness_dim(freshness: object) -> dict:
    if freshness is None:
        return _unavailable_facet(_REASON_FRESHNESS_ABSENT)
    if not isinstance(freshness, dict):
        raise ev.ReadFaceEnvelopeError("source_freshness must be a dict or None")
    age_ms = freshness.get("age_ms")
    bound = freshness.get("bound")
    # A known timing bound + an integer age is measurable; anything else is NOT_MEASURABLE (never
    # raised on — the bound name is caller content). Membership is checked without raising.
    if isinstance(bound, str) and bound in timings.timings_ms() and _is_plain_int(age_ms):
        return {
            "status": _AVAILABLE, "age_ms": age_ms, "bound": bound,
            "bound_ms": timings.timing_ms(bound), "stale": timings.is_stale(age_ms, bound)}
    return {"status": _NOT_MEASURABLE, "reason": _REASON_FRESHNESS_UNKNOWN_BOUND,
            "age_ms": age_ms if _is_plain_int(age_ms) else None, "bound": bound}


def _coverage_dim(coverage: object) -> dict:
    if coverage is None:
        return _unavailable_facet(_REASON_COVERAGE_ABSENT)
    if not isinstance(coverage, dict):
        raise ev.ReadFaceEnvelopeError("coverage must be a dict or None")
    reconciled = coverage.get("reconciled")
    presented = coverage.get("presented")
    if _is_plain_int(reconciled) and reconciled >= 0 and _is_plain_int(presented) and presented >= 0:
        # An EXACT integer comparison — no float ratio (determinism law).
        return {"status": _AVAILABLE, "reconciled": reconciled, "presented": presented,
                "fully_reconciled": reconciled == presented}
    return {"status": _NOT_MEASURABLE, "reason": _REASON_COVERAGE_MALFORMED}


def _lease_dim(lease: object) -> dict:
    if lease is None:
        return _unavailable_facet(_REASON_LEASE_ABSENT)
    if not isinstance(lease, dict):
        raise ev.ReadFaceEnvelopeError("lease_validity must be a dict or None")
    # ORIGIN VERIFIES a lease, it never issues one — the caller's lease fact is echoed and marked
    # verify-only + not-owned-here (the authority-fact-verifier discipline).
    return {"status": _AVAILABLE, "lease": lease, "verify_only": True,
            "producer_attestation": "NOT_OWNED_HERE"}


def _estate_dim(estate: object) -> dict:
    if estate is None:
        # ORIGIN holds no estate/venue truth (DARK) — an absent estate-activation fact is honest
        # UNAVAILABLE, never an inferred value.
        return _unavailable_facet(_REASON_ESTATE_ABSENT)
    if not isinstance(estate, dict):
        raise ev.ReadFaceEnvelopeError("estate_activation must be a dict or None")
    return {"status": _AVAILABLE, "estate_activation": estate, "attested_not_observed": True}


def get_readiness_view(
    *,
    bootstrap_readiness: str | None,
    as_of_us: int,
    watermark_us: int | None = None,
    source_freshness: dict | None = None,
    coverage: dict | None = None,
    lease_validity: dict | None = None,
    estate_activation: dict | None = None,
) -> ev.ReadFaceEnvelope:
    """The CTRL-B08-001 view — project the bootstrap readiness PLUS the four still-open evidence
    dimensions (source freshness · coverage · lease validity · estate activation), each honest-null
    unless a caller supplies real evidence.

    **THE NARROWNESS LAW** (``docs/plan/05_RC2_CONFLICT_REGISTER.md`` row CTRL-B08-001 + CLAUDE.md):
    this view NEVER claims more than ``READY_NO_AUTHORITY``. ``authority`` is always ``"NONE"`` and
    ``operational_readiness_claimed`` always ``False`` — even when every evidence dimension is
    supplied positively: a read face ADDS evidence, never AUTHORITY. An absent bootstrap readiness is
    ``UNAVAILABLE``.
    """
    if bootstrap_readiness is None:
        return ev.unavailable(
            face=VIEW_READINESS, source=_SRC_READINESS, as_of_us=as_of_us, watermark_us=watermark_us,
            plane=ev.CONTROL_PLANE, reason=_REASON_NO_READINESS_SOURCE)
    if not isinstance(bootstrap_readiness, str) or bootstrap_readiness == "":
        raise ev.ReadFaceEnvelopeError("bootstrap_readiness must be a non-empty string or None")

    if bootstrap_readiness in _KNOWN_READINESS:
        bootstrap_facet = {"status": _AVAILABLE, "value": bootstrap_readiness}
    else:
        # A caller-supplied string that is not a known Readiness value is content, not a crash —
        # NOT_MEASURABLE, never coerced to a recognized state.
        bootstrap_facet = {"status": _NOT_MEASURABLE, "reason": _REASON_READINESS_UNRECOGNIZED,
                           "raw": bootstrap_readiness}

    value = {
        "bootstrap_readiness": bootstrap_facet,
        # The four still-open CTRL-B08-001 evidence dimensions — honest-null unless supplied.
        "evidence_dimensions": {
            "source_freshness": _freshness_dim(source_freshness),
            "coverage": _coverage_dim(coverage),
            "lease_validity": _lease_dim(lease_validity),
            "estate_activation": _estate_dim(estate_activation),
        },
        # THE NARROWNESS INVARIANT — a read face adds evidence, never authority; the ceiling holds
        # regardless of the evidence dimensions above.
        "authority": "NONE",
        "ceiling": _READY_CEILING,
        "operational_readiness_claimed": False,
    }
    return ev.available(
        face=VIEW_READINESS, source=_SRC_READINESS, as_of_us=as_of_us, watermark_us=watermark_us,
        plane=ev.CONTROL_PLANE, value=value, returned=1)
