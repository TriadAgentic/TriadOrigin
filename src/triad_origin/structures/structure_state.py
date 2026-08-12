"""Structure state — F08 refusal interface + F09 accepted-break detector (b03 grounding rows;
golden vector GV-008), plus the structure_atom/structure_transition payload builders.

NOTE (Formula Repair §1.5, B03C): the F09 v1 detector below (:class:`BreakDetector`,
``break.bar_close.v1``) is retired — see its class-level ``RETIRED_DEFECTIVE`` banner; the
repaired surface is ``break.bar_close.v2`` in :mod:`triad_origin.structures.break_v2`. This
module is NOT bannered as a whole: F08 (:class:`ProtectedSwingStructure`) and the payload
builders remain live law, and the v1 bytes/logic are unchanged (replay of v1 history).

**F08 (:class:`ProtectedSwingStructure`) is a REFUSAL INTERFACE, loudly and deliberately.** The
RC3 formula row reads "NO IMPLEMENTATION AUTHORIZED until exact reducer version is ratified"
(RC3-PAR-STRUCT-003, status BLOCKING_RESEARCH_DECISION, declared_value NOT_RATIFIED). There is
therefore NO dormant reducer logic in this repository — this is stronger than the F06 posture,
where the formula exists and only its max-span parameter is unratified. State is exactly
``{"structure_state": "UNINITIALIZED"}`` and never mutates; EVERY input envelope yields the named
abstention ``F08_UNAVAILABLE_REDUCER_VERSION_NOT_RATIFIED``. A caller supplying
``params["protected_swing_reducer_version"]`` with ANY value is refused with
``F08_NO_IMPLEMENTATION_AUTHORIZED`` — no ratified reducer version exists, so no supplied value
can activate anything (a value that "worked" would be a hidden experiment).

**F09 (:class:`BreakDetector`)** consumes (a) confirmed frozen level registrations and (b)
finalized-close observations carrying causal ATR14. ``up_break`` iff ``C_t >= L + b`` and
``down_break`` iff ``C_t <= L - b`` — both inclusive (PAR-009), with
``b = evaluate_declared_rational(DECLARED_BOS_CLOSE_BUFFER, ATR14_ticks)`` (PAR-043; the declared
rule string arrives as the required parameter ``break_buffer_rule`` and any other string
refuses). GV-008: ATR 20 => buffer 1; level 1000, close 1001 => break; close 1000 => no break.

F09 laws:

* Only finalized CLOSES ever enter the predicate — the BAR payload shape carries ``close_ticks``
  and no high/low field, so a wick-only cross is structurally unrepresentable here (the caller
  feeds finalized closes only; the accepted observation mode parameter admits only
  ``"FINALIZED_CLOSE"``).
* A level not yet confirmed/registered emits nothing; an unconfirmed registration is not stored.
* ONE first-breach occurrence per ``(level_id, direction)`` — a later qualifying close is refused
  idempotently (the machine keys its own breach set, beyond the driver's envelope dedup).
* Multiple levels broken by one close emit occurrences sorted by ``level_id`` (PAR-010 spirit).
* Classification: BOS = break in the trend direction of the current continuation; CHOCH = break
  against the current protected swing — but BOTH require a valid F08 structure state, and F08 is
  the refusal interface above, so every occurrence carries classification
  ``UNCLASSIFIED_STRUCTURE_STATE_UNAVAILABLE`` — never a guessed BOS/CHOCH. Even a caller-fed
  STRUCTURE_STATE input is refused with a named abstention rather than adopted, because the
  reducer semantics (RC3-PAR-STRUCT-003) are unratified.

Input envelope shapes (market_state.v2-shaped, minimal and explicit):

* LEVEL registration (a confirmed typed level from the registry)::

      {"event_id": str, "kind": "LEVEL",
       "payload": {"level_id": str, "level_ticks": int,
                   "direction": "LONG" | "SHORT", "confirmed": bool}}

* BAR observation (a finalized close + its causal F02 ATR, supplied by the caller)::

      {"event_id": str, "kind": "BAR",
       "payload": {"close_ticks": int, "atr14_ticks": int | None}}

* STRUCTURE_STATE (a would-be ratified F08 state; always refused while unratified)::

      {"event_id": str, "kind": "STRUCTURE_STATE", "payload": {"structure_state": str}}

The payload builders assemble contract-valid ``triad.structure_atom.v2`` /
``triad.structure_transition.v2`` payload bytes (identity via :mod:`triad_origin.ids`; geometry
identity via ``common.geometry_digest``); they build payloads only — the envelope metadata
belongs to an envelope producer.

Mirror law (F09): C -> -C, up <-> down, high <-> low — proven algebraically by test.
"""

from __future__ import annotations

from collections.abc import Sequence

from .. import ids
from ..transition import Envelope, Params, Quality, State, TransitionResult, require
from . import common

FORMULA_F08 = "F08"
FORMULA_F09 = "F09"

PARAM_PROTECTED_SWING_REDUCER_VERSION = "protected_swing_reducer_version"
PARAM_BREAK_BUFFER_RULE = "break_buffer_rule"
PARAM_OBSERVATION_MODE = "observation_mode"

OBSERVATION_MODE_FINALIZED_CLOSE = "FINALIZED_CLOSE"

BREAK_OCCURRENCE = "BREAK_OCCURRENCE"
UP_BREAK = "up_break"
DOWN_BREAK = "down_break"
CLASSIFICATION_UNCLASSIFIED = "UNCLASSIFIED_STRUCTURE_STATE_UNAVAILABLE"

STRUCTURE_STATE_UNINITIALIZED = "UNINITIALIZED"

_F08_REFS = {"parameter": "RC3-PAR-STRUCT-003"}


def _event_identity(envelope: Envelope) -> str:
    event_id = envelope.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        raise common.StructureLawError("envelope event_id must be a non-empty string")
    return event_id


def _object_payload(envelope: Envelope, formula: str) -> dict:
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise common.StructureLawError(f"{formula} envelope payload must be an object")
    return payload


class ProtectedSwingStructure:
    """F08 — the refusal interface for directional structure / protected swing.

    NO IMPLEMENTATION AUTHORIZED (RC3 formula row F08): the exact reducer version
    RC3-PAR-STRUCT-003 is NOT_RATIFIED, so no reducer logic exists here at all. State is exactly
    ``{"structure_state": "UNINITIALIZED"}``, never mutates, and every input yields a named
    abstention. Supplying a reducer-version parameter — with any value — is itself refused:
    there is no ratified version, so no value can activate anything.
    """

    def initial_state(self) -> State:
        return {"structure_state": STRUCTURE_STATE_UNINITIALIZED}

    def transition(
        self, state: State, envelope: Envelope, params: Params, quality: Quality
    ) -> TransitionResult:
        event_id = _event_identity(envelope)
        if PARAM_PROTECTED_SWING_REDUCER_VERSION in params:
            return TransitionResult(state=state, events=(common.abstention(
                "F08_NO_IMPLEMENTATION_AUTHORIZED", formula=FORMULA_F08,
                detail="a protected-swing reducer version was supplied, but no reducer version "
                       "is ratified and no implementation is authorized; refused",
                refs=dict(_F08_REFS, event_id=event_id)),))
        return TransitionResult(state=state, events=(common.abstention(
            "F08_UNAVAILABLE_REDUCER_VERSION_NOT_RATIFIED", formula=FORMULA_F08,
            detail="RC3-PAR-STRUCT-003 PROTECTED_SWING_REDUCER_VERSION is NOT_RATIFIED; F08 "
                   "holds UNINITIALIZED with zero state mutation (SAFE_HOLD)",
            refs=dict(_F08_REFS, event_id=event_id)),))


class BreakDetector:
    """RETIRED_DEFECTIVE{defect_ref=TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12 §2 R-F09} —
    ``break.bar_close.v1`` is WITHDRAWN; the repaired surface is ``break.bar_close.v2``
    (:mod:`triad_origin.structures.break_v2`).

    DEFECT (spec R-F09, verbatim): one frozen level can record accepted first breaks in BOTH
    directions (the ``(level_id, direction)`` dedup key below); there is no
    availability-before-break proof, so a late-finalizing older bar can false-trigger; BOS/CHOCH
    classification can run without valid F08 state.

    §1.5 withdrawal discipline: the bytes and logic below are otherwise UNCHANGED — retained for
    replay of history produced under v1; SHADOW rows produced under this version keep their
    version tag forever (never-blend applies across formula versions exactly as across cohorts).
    No new consumer may invoke this machine.

    F09 v1 — accepted close break over confirmed frozen levels (GV-008).

    ``up_break`` iff ``close >= level + buffer``; ``down_break`` iff ``close <= level - buffer``
    (equality passes, PAR-009). One first-breach occurrence per ``(level_id, direction)``. Every
    occurrence is ``UNCLASSIFIED_STRUCTURE_STATE_UNAVAILABLE`` — F08 is a refusal interface, so
    a BOS/CHOCH label is never guessed and a supplied structure state is refused, not adopted.
    """

    def initial_state(self) -> State:
        return {"last_event_id": None, "levels": {}, "breached": []}

    def transition(
        self, state: State, envelope: Envelope, params: Params, quality: Quality
    ) -> TransitionResult:
        rule = require(params, PARAM_BREAK_BUFFER_RULE)
        if rule != common.DECLARED_BOS_CLOSE_BUFFER:
            raise common.StructureLawError(
                f"F09 admits only the declared PAR-043 rule "
                f"{common.DECLARED_BOS_CLOSE_BUFFER!r}, got {rule!r}")
        mode = require(params, PARAM_OBSERVATION_MODE)
        if mode != OBSERVATION_MODE_FINALIZED_CLOSE:
            raise common.StructureLawError(
                f"F09 accepted observation mode is {OBSERVATION_MODE_FINALIZED_CLOSE!r} only, "
                f"got {mode!r}")
        event_id = _event_identity(envelope)
        if event_id == state.get("last_event_id"):
            return TransitionResult(state=state)
        kind = envelope.get("kind")
        payload = _object_payload(envelope, FORMULA_F09)
        if kind == "LEVEL":
            return self._register(state, event_id, payload)
        if kind == "BAR":
            return self._observe(state, event_id, payload, rule)
        if kind == "STRUCTURE_STATE":
            return TransitionResult(state=state, events=(common.abstention(
                "F09_CLASSIFICATION_UNAVAILABLE_REDUCER_NOT_RATIFIED", formula=FORMULA_F09,
                detail="a structure state was supplied, but RC3-PAR-STRUCT-003 reducer "
                       "semantics are unratified; F09 refuses to classify and never adopts it",
                refs=dict(_F08_REFS, event_id=event_id)),))
        raise common.StructureLawError(
            f"F09 consumes LEVEL, BAR or STRUCTURE_STATE envelopes only, got {kind!r}")

    def _register(self, state: State, event_id: str, payload: dict) -> TransitionResult:
        level_id = payload.get("level_id")
        if not isinstance(level_id, str) or not level_id:
            raise common.StructureLawError("F09 level_id must be a non-empty string")
        confirmed = payload.get("confirmed")
        if not isinstance(confirmed, bool):
            raise common.StructureLawError("F09 level confirmed marker must be a bool")
        if not confirmed:
            return TransitionResult(state=state)
        record = {
            "level_ticks": common.require_int(payload.get("level_ticks"), "level_ticks"),
            "direction": common.require_direction(payload.get("direction")),
        }
        levels = {key: dict(value) for key, value in state["levels"].items()}
        existing = levels.get(level_id)
        if existing == record:
            return TransitionResult(state=state)
        if existing is not None:
            raise common.StructureLawError(
                f"F09 level {level_id!r} re-registered with conflicting geometry")
        levels[level_id] = record
        return TransitionResult(state={
            "last_event_id": event_id, "levels": levels,
            "breached": list(state["breached"])})

    def _observe(self, state: State, event_id: str, payload: dict, rule: str
                 ) -> TransitionResult:
        close = common.require_int(payload.get("close_ticks"), "close_ticks")
        atr = payload.get("atr14_ticks")
        if atr is None:
            return TransitionResult(state=state, events=(common.abstention(
                "F09_NO_ATR", formula=FORMULA_F09,
                detail="causal ATR14 is null (warm-up/gap); break buffer is unavailable",
                refs={"event_id": event_id}),))
        buffer = common.evaluate_declared_rational(
            rule, common.require_int(atr, "atr14_ticks"))
        breached = set(state["breached"])
        events: tuple[dict, ...] = ()
        for level_id in sorted(state["levels"]):
            level = state["levels"][level_id]
            level_ticks = level["level_ticks"]
            for direction, broke in (
                (UP_BREAK, close >= level_ticks + buffer),
                (DOWN_BREAK, close <= level_ticks - buffer),
            ):
                key = f"{level_id}|{direction}"
                if not broke or key in breached:
                    continue
                breached.add(key)
                events += ({
                    "event_kind": BREAK_OCCURRENCE,
                    "formula": FORMULA_F09,
                    "level_id": level_id,
                    "direction": direction,
                    "level_direction": level["direction"],
                    "level_ticks": level_ticks,
                    "buffer_ticks": buffer,
                    "close_ticks": close,
                    "classification": CLASSIFICATION_UNCLASSIFIED,
                    "breach_event_id": event_id,
                },)
        return TransitionResult(state={
            "last_event_id": event_id,
            "levels": {key: dict(value) for key, value in state["levels"].items()},
            "breached": sorted(breached)}, events=events)


def _string_list(values: object, name: str) -> list[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise common.StructureLawError(f"{name} must be an ordered sequence of strings")
    out = []
    for value in values:
        if not isinstance(value, str) or not value:
            raise common.StructureLawError(f"{name} entries must be non-empty strings")
        out.append(value)
    return out


def _nonempty_str(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise common.StructureLawError(f"{name} must be a non-empty string")
    return value


def _base10(value: object, name: str) -> str:
    number = common.require_int(value, name)
    if number < 0:
        raise common.StructureLawError(f"{name} must be a non-negative integer, got {number}")
    return str(number)


def build_structure_atom_payload(
    *,
    structure_kind: str,
    structure_subtype: str,
    direction: str,
    canonical_instrument_id: str,
    venue_model: str,
    timeframe: str,
    formula_version: str,
    parameter_set_id: str,
    parameter_digest: str,
    original_geometry: dict,
    origin_source_ids: Sequence[str],
    confirmation_source_ids: Sequence[str],
    origin_time_us: int,
    confirmation_time_us: int,
    availability_time_us: int,
    knowledge_time_us: int,
    reference_level_ids: Sequence[str],
    source_offset_range: Sequence[str],
    dependency_quality: dict,
    build_commit: str,
    config_bundle_sha256: str,
    instrument_digest: str,
    predecessor_structure_ids: Sequence[str] = (),
) -> dict:
    """Assemble a contract-valid ``triad.structure_atom.v2`` payload (state ``CONFIRMED``).

    Identity is derived, never supplied: ``semantic_instance_id`` from the formula/parameter/
    venue/timeframe tuple and ``structure_id`` from the identity hierarchy over the immutable
    origin source ids and the ``original_geometry`` digest (:mod:`triad_origin.ids`).
    """
    dir_value = common.require_direction(direction)
    geometry_digest = common.geometry_digest(original_geometry)
    origin_ids = _string_list(origin_source_ids, "origin_source_ids")
    semantic = ids.semantic_instance_id(
        _nonempty_str(formula_version, "formula_version"),
        _nonempty_str(parameter_digest, "parameter_digest"),
        _nonempty_str(venue_model, "venue_model"),
        _nonempty_str(timeframe, "timeframe"),
    )
    sid = ids.structure_id(
        _nonempty_str(canonical_instrument_id, "canonical_instrument_id"),
        venue_model,
        _nonempty_str(structure_kind, "structure_kind"),
        semantic,
        dir_value,
        origin_ids,
        geometry_digest,
    )
    if not isinstance(dependency_quality, dict):
        raise common.StructureLawError("dependency_quality must be an object")
    return {
        "structure_id": sid,
        "semantic_instance_id": semantic,
        "structure_kind": structure_kind,
        "structure_subtype": _nonempty_str(structure_subtype, "structure_subtype"),
        "canonical_instrument_id": canonical_instrument_id,
        "venue_model": venue_model,
        "timeframe": timeframe,
        "direction": dir_value,
        "origin_source_ids": origin_ids,
        "confirmation_source_ids": _string_list(
            confirmation_source_ids, "confirmation_source_ids"),
        "origin_time_us": common.require_int(origin_time_us, "origin_time_us"),
        "confirmation_time_us": common.require_int(
            confirmation_time_us, "confirmation_time_us"),
        "availability_time_us": common.require_int(
            availability_time_us, "availability_time_us"),
        "knowledge_time_us": common.require_int(knowledge_time_us, "knowledge_time_us"),
        "original_geometry": dict(original_geometry),
        "original_geometry_digest": geometry_digest,
        "reference_level_ids": _string_list(reference_level_ids, "reference_level_ids"),
        "source_offset_range": _string_list(source_offset_range, "source_offset_range"),
        "dependency_quality": dict(dependency_quality),
        "formula_version": formula_version,
        "parameter_set_id": _nonempty_str(parameter_set_id, "parameter_set_id"),
        "parameter_digest": parameter_digest,
        "build_commit": _nonempty_str(build_commit, "build_commit"),
        "config_bundle_sha256": _nonempty_str(config_bundle_sha256, "config_bundle_sha256"),
        "instrument_digest": _nonempty_str(instrument_digest, "instrument_digest"),
        "state": "CONFIRMED",
        "predecessor_structure_ids": _string_list(
            predecessor_structure_ids, "predecessor_structure_ids"),
    }


def build_structure_transition_payload(
    *,
    transition_id: str,
    structure_id: str,
    state_seq: int,
    previous_transition_id: str,
    from_state: str,
    to_state: str,
    transition_reason: str,
    geometry_revision: int,
    current_geometry: dict,
    event_time_us: int,
    receipt_time_us: int,
    knowledge_at_us: int,
    publication_time_us: int,
    source_event_ids: Sequence[str],
    reference_ids: Sequence[str],
    watermark_complete: bool,
    quality_snapshot: dict,
    provenance_hash: str,
) -> dict:
    """Assemble a contract-valid ``triad.structure_transition.v2`` payload.

    ``state_seq``/``geometry_revision`` arrive as exact non-negative ints and are rendered as the
    schema's base-10 strings; ``watermark_complete`` must be an exact bool.
    """
    if not isinstance(watermark_complete, bool):
        raise common.StructureLawError("watermark_complete must be an exact bool")
    if not isinstance(current_geometry, dict) or not isinstance(quality_snapshot, dict):
        raise common.StructureLawError(
            "current_geometry and quality_snapshot must be objects")
    return {
        "transition_id": _nonempty_str(transition_id, "transition_id"),
        "structure_id": _nonempty_str(structure_id, "structure_id"),
        "state_seq": _base10(state_seq, "state_seq"),
        "previous_transition_id": _nonempty_str(
            previous_transition_id, "previous_transition_id"),
        "from_state": _nonempty_str(from_state, "from_state"),
        "to_state": _nonempty_str(to_state, "to_state"),
        "transition_reason": _nonempty_str(transition_reason, "transition_reason"),
        "geometry_revision": _base10(geometry_revision, "geometry_revision"),
        "current_geometry": dict(current_geometry),
        "event_time_us": common.require_int(event_time_us, "event_time_us"),
        "receipt_time_us": common.require_int(receipt_time_us, "receipt_time_us"),
        "knowledge_at_us": common.require_int(knowledge_at_us, "knowledge_at_us"),
        "publication_time_us": common.require_int(
            publication_time_us, "publication_time_us"),
        "source_event_ids": _string_list(source_event_ids, "source_event_ids"),
        "reference_ids": _string_list(reference_ids, "reference_ids"),
        "watermark_complete": watermark_complete,
        "quality_snapshot": dict(quality_snapshot),
        "provenance_hash": _nonempty_str(provenance_hash, "provenance_hash"),
    }
