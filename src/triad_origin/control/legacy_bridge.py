"""Frozen legacy candidate bridge (B07 — RC3-WOP-002; row F2).

The exact legacy ``candidate.v1`` source topic/ledger path is an OPEN operator decision (row F2,
``docs/plan/09_OPEN_QUESTIONS.md``) — this module builds the MECHANISM generically, over any
caller-supplied byte source, never a hardcoded path or an assumed legacy schema shape.

**THE FREEZE LAW** (RC3-WOP-002, verbatim): "frozen comparator writer only; no ORIGIN or
intelligence alias inference." This bridge:

  * NEVER repairs, backfills, reshapes, or infers a missing field on a legacy record — every
    field the source carries (or omits) passes through byte-identical, verified by a
    content-digest round-trip (:func:`verify_byte_preservation`);
  * NEVER infers an ``engine_cohort``/``intelligence_arm`` label from the record's own content —
    it stamps EXACTLY the caller-declared labels, and refuses outright if asked to stamp anything
    other than ``LEGACY_COMPARATOR`` (this bridge has exactly one lawful cohort to write as);
  * publishes the bridged record as a SEPARATE routing envelope wrapping the original bytes under
    ``legacy_payload`` — never merged/mutated into one indistinguishable blob, so an auditor can
    always recover exactly what the legacy source said, unmodified.

**RESTART/OMISSION LAW**: :class:`LegacyBridgeState` tracks the highest bridged offset PER
``source_topic``. A restart queries :meth:`LegacyBridgeState.resume_from_offset` and continues
from there — no gap, no silent reprocessing. Re-bridging the SAME offset with byte-identical
content is idempotent (returns the cached envelope); re-bridging the same offset with DIFFERENT
content refuses (mirrors :mod:`authority_fact_verifier`'s duplicate-conflict law — a bridged
record's identity is pinned to its offset, never silently overwritten). A field the legacy record
never carried stays absent in ``legacy_payload`` forever — never defaulted to a fabricated value.

Pure and side-effect-free: no clock, no I/O, no network. The caller supplies the raw legacy
record and every stamped label/offset/timestamp explicitly.
"""

from __future__ import annotations

from ..canonical import canonical_json, sha256_hex

LEGACY_ENGINE_COHORT = "LEGACY_COMPARATOR"
_VALID_INTELLIGENCE_ARMS = ("DETERMINISTIC_CONTROL", "INTELLIGENCE_TREATMENT")


class LegacyBridgeError(RuntimeError):
    """A legacy record could not be bridged as requested — fail closed, never a repaired guess."""


def bridge_legacy_record(
    raw_record: dict,
    *,
    intelligence_arm: str,
    source_topic: str,
    input_offset: int,
    bridged_at_us: int,
) -> dict:
    """Wrap ``raw_record`` (an opaque legacy dict, any shape) into a routing envelope.

    Never inspects or repairs ``raw_record``'s own fields — it is carried byte-identical under
    ``legacy_payload``, alongside a content digest any later hop can use to prove nothing was
    silently mutated (:func:`verify_byte_preservation`). Always stamps
    ``engine_cohort=LEGACY_COMPARATOR`` — this bridge writes exactly one cohort, per the freeze
    law; a caller wanting a different cohort wants a different module.
    """
    if not isinstance(raw_record, dict):
        raise LegacyBridgeError("raw_record must be an object")
    if intelligence_arm not in _VALID_INTELLIGENCE_ARMS:
        raise LegacyBridgeError(f"unknown intelligence_arm: {intelligence_arm!r}")
    if not isinstance(source_topic, str) or not source_topic:
        raise LegacyBridgeError("source_topic must be a non-empty string")
    if (isinstance(input_offset, bool) or not isinstance(input_offset, int)
            or input_offset < 0):
        raise LegacyBridgeError("input_offset must be a non-negative int")
    if not isinstance(bridged_at_us, int) or isinstance(bridged_at_us, bool):
        raise LegacyBridgeError("bridged_at_us must be an int")

    frozen_bytes = canonical_json(raw_record)
    return {
        "engine_cohort": LEGACY_ENGINE_COHORT,
        "intelligence_arm": intelligence_arm,
        "source_topic": source_topic,
        "input_offset": input_offset,
        "bridged_at_us": bridged_at_us,
        "legacy_payload_digest": sha256_hex(frozen_bytes),
        "legacy_payload": raw_record,
    }


def verify_byte_preservation(envelope: dict) -> bool:
    """Recompute ``legacy_payload``'s digest and compare — proves the bridge (or any later hop)
    never mutated the frozen bytes. Never trusts the stored digest alone (never trust, recompute)."""
    if not isinstance(envelope, dict):
        return False
    payload = envelope.get("legacy_payload")
    if not isinstance(payload, dict):
        return False
    return sha256_hex(canonical_json(payload)) == envelope.get("legacy_payload_digest")


class LegacyBridgeState:
    """Per-``source_topic`` restart/idempotency tracking over :func:`bridge_legacy_record`.

    Not itself durable — a thin, testable in-memory law over a caller-owned instance, mirroring
    :class:`triad_origin.control.authority_fact_verifier.AuthorityLedger`'s posture. Persisting
    this state is the estate's deployment decision.
    """

    def __init__(self) -> None:
        self._by_topic: dict[str, dict[int, dict]] = {}

    def resume_from_offset(self, source_topic: str) -> int:
        """The next offset to process for ``source_topic`` after a restart — the highest bridged
        offset plus one, or ``0`` if nothing has been bridged yet. A caller resumes its tape read
        from exactly this position: no gap, no reprocessing."""
        offsets = self._by_topic.get(source_topic)
        if not offsets:
            return 0
        return max(offsets) + 1

    def bridge(
        self, raw_record: dict, *, intelligence_arm: str, source_topic: str, input_offset: int,
        bridged_at_us: int,
    ) -> dict:
        """Bridge ``raw_record`` and record it against ``(source_topic, input_offset)``.

        A byte-identical redelivery at an already-bridged offset returns the SAME cached
        envelope (idempotent). A DIFFERENT record at an already-bridged offset refuses
        (:class:`LegacyBridgeError`) — an offset's bridged identity is pinned once set, never
        silently overwritten.
        """
        envelope = bridge_legacy_record(
            raw_record, intelligence_arm=intelligence_arm, source_topic=source_topic,
            input_offset=input_offset, bridged_at_us=bridged_at_us)
        topic_offsets = self._by_topic.setdefault(source_topic, {})
        existing = topic_offsets.get(input_offset)
        if existing is not None:
            if existing["legacy_payload_digest"] == envelope["legacy_payload_digest"]:
                return dict(existing)
            raise LegacyBridgeError(
                f"offset {input_offset} for topic {source_topic!r} is already bridged with "
                f"disagreeing content — an offset's bridged identity is pinned once set")
        topic_offsets[input_offset] = envelope
        return dict(envelope)

    def bridged_at(self, source_topic: str, input_offset: int) -> dict | None:
        """The verbatim previously-bridged envelope, if any — a read of record."""
        offsets = self._by_topic.get(source_topic)
        if offsets is None:
            return None
        entry = offsets.get(input_offset)
        return dict(entry) if entry is not None else None
