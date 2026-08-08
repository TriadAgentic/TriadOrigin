"""Append-only state journal + replay adapter (MOD-016 / MOD-018, Doc 04 §04.1).

Every transition is journaled with its prior ``state_seq`` and previous transition id using
**compare-and-append** semantics: two conflicting transitions can never both commit. Any projection
can be rebuilt from the journal and matches the authoritative checksum (Doc 04 §04.18).

The replay adapter drives an ordered input list through a machine identically live and in replay,
optionally resuming from a checkpoint — the same code path, so restart/prefix/duplicate invariance
holds by construction (Doc 02 §02.16).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Iterable

from .canonical import CanonicalError, canonical_json, digest_fields, loads_canonical, nfc, sha256_hex
from .checkpoint import Checkpoint, validate_for_restore
from .transition import (
    DeterministicMachine,
    Envelope,
    Event,
    InputIdentityError,
    Params,
    State,
    TransitionResult,
    register_input,
)


class JournalError(RuntimeError):
    pass


@dataclass(frozen=True)
class TransitionRecord:
    """An immutable, self-contained transition record.

    Canonical state/event bytes are stored instead of caller-owned dictionaries.  Accessors decode
    fresh values, so a consumer cannot mutate the journal head through a returned record.
    """

    state_seq: int
    previous_transition_id: str
    transition_id: str
    from_state_digest: str
    to_state_digest: str
    envelope_id: str
    events_digest: str
    to_state_canonical: bytes = field(repr=False)
    events_canonical: tuple[bytes, ...] = field(repr=False)

    @property
    def to_state(self) -> State:
        value = loads_canonical(self.to_state_canonical)
        if not isinstance(value, dict):  # pragma: no cover - constructor invariant
            raise JournalError("transition record state is not an object")
        return value

    @property
    def events(self) -> tuple[Event, ...]:
        values = tuple(loads_canonical(value) for value in self.events_canonical)
        if any(not isinstance(value, dict) for value in values):  # pragma: no cover
            raise JournalError("transition record event is not an object")
        return values


@dataclass
class StateJournal:
    """Append-only journal of transitions with compare-and-append and rebuildable projection."""

    partition: str
    _base_seq: int = -1
    _base_transition_id: str = "genesis"
    _base_state: State = field(default_factory=dict)
    _records: list[TransitionRecord] = field(default_factory=list)
    _base_state_canonical: bytes = field(init=False, repr=False)
    _head_state_digest: str = field(init=False, repr=False)
    _head_transition_id: str = field(init=False, repr=False)
    _duplicate_count: int = field(default=0, init=False, repr=False)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False, compare=False)
    _partition_sealed: bool = field(default=False, init=False, repr=False, compare=False)

    def __setattr__(self, name: str, value: object) -> None:
        if name == "partition" and self.__dict__.get("_partition_sealed", False):
            raise JournalError("journal partition identity is immutable")
        object.__setattr__(self, name, value)

    def __post_init__(self) -> None:
        if not isinstance(self.partition, str) or not self.partition:
            raise JournalError("journal partition must be a non-empty string")
        normalized_partition = nfc(self.partition)
        try:
            canonical_json(normalized_partition)
        except (CanonicalError, UnicodeError, RecursionError) as exc:
            raise JournalError("journal partition is not canonical-wire encodable") from exc
        self.partition = normalized_partition
        self._partition_sealed = True
        if not isinstance(self._base_state, dict):
            raise JournalError("journal base state must be an object")
        self._base_state_canonical = canonical_json(self._base_state)
        self._head_state_digest = sha256_hex(self._base_state_canonical)
        self._head_transition_id = self._base_transition_id

    @property
    def seq(self) -> int:
        with self._lock:
            return self._base_seq + len(self._records)

    @property
    def duplicate_count(self) -> int:
        with self._lock:
            return self._duplicate_count

    def _digest(self, state: State) -> str:
        return sha256_hex(canonical_json(state))

    def append(
        self,
        expected_prev_seq: int,
        from_state: State,
        to_state: State,
        envelope_id: str,
        events: tuple[Event, ...],
    ) -> TransitionRecord | None:
        with self._lock:
            if not isinstance(from_state, dict) or not isinstance(to_state, dict):
                raise JournalError("journal transition states must be objects")
            if not isinstance(envelope_id, str) or not envelope_id:
                raise JournalError("journal envelope_id must be a non-empty string")
            if not isinstance(events, tuple) or any(not isinstance(event, dict) for event in events):
                raise JournalError("journal events must be a tuple of objects")
            current_seq = self._base_seq + len(self._records)
            if expected_prev_seq != current_seq:
                raise JournalError(
                    f"compare-and-append conflict: expected prev_seq {expected_prev_seq}, "
                    f"have {current_seq}")
            from_bytes = canonical_json(from_state)
            from_d = sha256_hex(from_bytes)
            if from_d != self._head_state_digest:
                raise JournalError("compare-and-append state continuity mismatch")
            to_bytes = canonical_json(to_state)
            to_d = sha256_hex(to_bytes)
            event_bytes = tuple(canonical_json(event) for event in events)
            events_d = sha256_hex(canonical_json([loads_canonical(event) for event in event_bytes]))
            # A semantic no-op is not a transition. This keeps exact duplicate/irrelevant input
            # from perturbing the journal sequence or every subsequent transition identity.
            if to_d == from_d and not event_bytes:
                return None
            prev_id = self._head_transition_id
            new_seq = current_seq + 1
            tid = "stx_" + digest_fields(
                "transition", self.partition, new_seq, prev_id, from_d, to_d, envelope_id,
                events_d)[:40]
            rec = TransitionRecord(
                state_seq=new_seq,
                previous_transition_id=prev_id,
                transition_id=tid,
                from_state_digest=from_d,
                to_state_digest=to_d,
                envelope_id=envelope_id,
                events_digest=events_d,
                to_state_canonical=to_bytes,
                events_canonical=event_bytes,
            )
            self._records.append(rec)
            self._head_state_digest = to_d
            self._head_transition_id = tid
            return rec

    def project(self) -> State:
        with self._lock:
            records = list(self._records)
            base = self._base_state_canonical
        if not records:
            value = loads_canonical(base)
            if not isinstance(value, dict):  # pragma: no cover - constructor invariant
                raise JournalError("journal base state is not an object")
            return value
        return rebuild_projection(self.partition, records)

    def records(self) -> list[TransitionRecord]:
        with self._lock:
            return list(self._records)

    def _note_duplicate(self) -> None:
        with self._lock:
            self._duplicate_count += 1


def rebuild_projection(partition: str, records: Iterable[TransitionRecord]) -> State:
    """Rebuild and authenticate the final projection from exported records alone."""
    materialized = list(records)
    if not materialized:
        raise JournalError("cannot rebuild a projection from an empty record set")
    previous_seq = materialized[0].state_seq - 1
    previous_id = materialized[0].previous_transition_id
    previous_state_digest = materialized[0].from_state_digest
    projection: State = {}
    for record in materialized:
        if record.state_seq != previous_seq + 1:
            raise JournalError("journal record sequence discontinuity")
        if record.previous_transition_id != previous_id:
            raise JournalError("journal transition-id chain discontinuity")
        if record.from_state_digest != previous_state_digest:
            raise JournalError("journal state-digest chain discontinuity")
        projection = record.to_state
        if sha256_hex(record.to_state_canonical) != record.to_state_digest:
            raise JournalError("journal record state bytes do not match digest")
        event_values = [loads_canonical(event) for event in record.events_canonical]
        events_digest = sha256_hex(canonical_json(event_values))
        if events_digest != record.events_digest:
            raise JournalError("journal record event bytes do not match digest")
        expected_id = "stx_" + digest_fields(
            "transition", partition, record.state_seq, record.previous_transition_id,
            record.from_state_digest, record.to_state_digest, record.envelope_id,
            record.events_digest)[:40]
        if record.transition_id != expected_id:
            raise JournalError("journal transition identity mismatch")
        previous_seq = record.state_seq
        previous_id = record.transition_id
        previous_state_digest = record.to_state_digest
    return projection


@dataclass(frozen=True)
class ReplayContext:
    """Expected current transport/build identity supplied independently of a checkpoint."""

    input_segment: str
    input_prefix_digest: str
    output_segment: str
    output_offset: int
    highest_producer_epoch: int
    state_seq: int
    last_transition_id: str
    projection_checksum: str
    digests: dict[str, str]


def replay(
    machine: DeterministicMachine,
    inputs: list[Envelope],
    params: Params,
    *,
    partition: str = "replay",
    resume_from: Checkpoint | None = None,
    resume_context: ReplayContext | None = None,
) -> tuple[StateJournal, list[Event]]:
    """Deterministically run ``inputs`` through ``machine``, journaling every transition.

    ``resume_from`` seeds the initial state and skips inputs at or before the checkpoint offset,
    proving checkpoint-resume equals a cold run over the same suffix.
    """
    if not isinstance(partition, str) or not partition:
        raise JournalError("replay partition must be a non-empty string")
    partition = nfc(partition)
    try:
        canonical_json(partition)
    except (CanonicalError, UnicodeError, RecursionError) as exc:
        raise JournalError("replay partition is not canonical-wire encodable") from exc
    if resume_from is not None:
        validate_for_restore(resume_from)
        if resume_context is None:
            raise JournalError("checkpoint resume requires an independently supplied context")
        if resume_from.partition != partition:
            raise JournalError("checkpoint partition does not match requested replay partition")
        if resume_from.input_offset >= len(inputs):
            raise JournalError("checkpoint input offset lies outside the supplied input segment")
        if resume_from.input_offset >= 0:
            actual_event_id = inputs[resume_from.input_offset].get("event_id")
            if actual_event_id != resume_from.last_domain_event_id:
                raise JournalError("checkpoint last domain event does not match supplied input")
        actual_prefix_digest = sha256_hex(
            canonical_json(inputs[: resume_from.input_offset + 1])
        )
        if actual_prefix_digest != resume_from.input_prefix_digest:
            raise JournalError("checkpoint input prefix digest does not match supplied tape")
        expected_context = ReplayContext(
            input_segment=resume_from.input_segment,
            input_prefix_digest=resume_from.input_prefix_digest,
            output_segment=resume_from.output_segment,
            output_offset=resume_from.output_offset,
            highest_producer_epoch=resume_from.highest_producer_epoch,
            state_seq=resume_from.state_seq,
            last_transition_id=resume_from.last_transition_id,
            projection_checksum=resume_from.projection_checksum,
            digests=resume_from.digests,
        )
        if resume_context != expected_context:
            raise JournalError("checkpoint does not match the requested replay/build context")
    elif resume_context is not None:
        raise JournalError("resume context supplied without a checkpoint")
    state = _canonical_object(
        resume_from.state if resume_from is not None else machine.initial_state(),
        "machine state",
    )
    params_canonical = canonical_json(_canonical_object(params, "parameter bundle"))
    journal = StateJournal(
        partition=partition,
        _base_seq=resume_from.state_seq if resume_from is not None else -1,
        _base_transition_id=(
            resume_from.last_transition_id if resume_from is not None else "genesis"
        ),
        _base_state=dict(state),
    )
    start_offset = resume_from.input_offset if resume_from is not None else -1
    all_events: list[Event] = []
    seen_inputs: dict[tuple[str, bytes], str] = {}
    seen_fingerprints: set[str] = set()
    for offset, env in enumerate(inputs[:start_offset + 1]):
        normalized_env = _canonical_object(env, "input envelope")
        try:
            register_input(normalized_env, offset, seen_inputs, seen_fingerprints)
        except InputIdentityError as exc:
            raise JournalError(str(exc)) from exc
    for offset, env in enumerate(inputs):
        if offset <= start_offset:
            continue
        normalized_env = _canonical_object(env, "input envelope")
        try:
            duplicate = register_input(
                normalized_env, offset, seen_inputs, seen_fingerprints
            )
        except InputIdentityError as exc:
            raise JournalError(str(exc)) from exc
        if duplicate:
            journal._note_duplicate()
            continue
        quality = _canonical_object(normalized_env.get("_quality", {}), "quality snapshot")
        result = machine.transition(
            _canonical_object(state, "machine state"),
            _canonical_object(normalized_env, "input envelope"),
            _canonical_object(loads_canonical(params_canonical), "parameter bundle"),
            quality,
        )
        if not isinstance(result, TransitionResult):
            raise JournalError("machine transition returned an invalid result")
        if not isinstance(result.events, tuple) or any(
            not isinstance(event, dict) for event in result.events
        ):
            raise JournalError("machine transition events must be a tuple of objects")
        result_state = _canonical_object(result.state, "transition state")
        result_events = tuple(
            _canonical_object(event, "transition event") for event in result.events
        )
        envelope_id = normalized_env.get("event_id", f"in_{offset}")
        if not isinstance(envelope_id, str) or not envelope_id:
            raise JournalError("input event_id must be a non-empty string when supplied")
        record = journal.append(
            journal.seq, state, result_state, envelope_id, result_events
        )
        if record is not None:
            state = record.to_state
            all_events.extend(record.events)
        else:
            # Canonical round-trip prevents a no-op machine from retaining a mutable alias.
            state = result_state
    return journal, all_events


def _canonical_object(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise JournalError(f"{label} must be an object")
    normalized = loads_canonical(canonical_json(value))
    if not isinstance(normalized, dict):  # pragma: no cover - checked above
        raise JournalError(f"{label} must be an object")
    return normalized
