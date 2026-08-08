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

from .canonical import canonical_json, digest_fields, sha256_hex
from .checkpoint import Checkpoint
from .transition import DeterministicMachine, Envelope, Event, Params, State


class JournalError(RuntimeError):
    pass


@dataclass
class TransitionRecord:
    state_seq: int
    previous_transition_id: str
    transition_id: str
    from_state_digest: str
    to_state_digest: str
    envelope_id: str
    events: tuple[Event, ...]


@dataclass
class StateJournal:
    """Append-only journal of transitions with compare-and-append and rebuildable projection."""

    partition: str
    _records: list[TransitionRecord] = field(default_factory=list)
    _states: list[State] = field(default_factory=list)

    @property
    def seq(self) -> int:
        return len(self._records) - 1

    def _digest(self, state: State) -> str:
        return sha256_hex(canonical_json(state))

    def append(
        self,
        expected_prev_seq: int,
        from_state: State,
        to_state: State,
        envelope_id: str,
        events: tuple[Event, ...],
    ) -> TransitionRecord:
        if expected_prev_seq != self.seq:
            raise JournalError(
                f"compare-and-append conflict: expected prev_seq {expected_prev_seq}, have {self.seq}")
        prev_id = self._records[-1].transition_id if self._records else "genesis"
        new_seq = self.seq + 1
        from_d = self._digest(from_state)
        to_d = self._digest(to_state)
        tid = "stx_" + digest_fields(
            "transition", self.partition, new_seq, prev_id, from_d, to_d, envelope_id)[:40]
        rec = TransitionRecord(
            state_seq=new_seq,
            previous_transition_id=prev_id,
            transition_id=tid,
            from_state_digest=from_d,
            to_state_digest=to_d,
            envelope_id=envelope_id,
            events=tuple(events),
        )
        self._records.append(rec)
        self._states.append(to_state)
        return rec

    def project(self) -> State:
        return dict(self._states[-1]) if self._states else {}

    def records(self) -> list[TransitionRecord]:
        return list(self._records)


def replay(
    machine: DeterministicMachine,
    inputs: list[Envelope],
    params: Params,
    *,
    partition: str = "replay",
    resume_from: Checkpoint | None = None,
) -> tuple[StateJournal, list[Event]]:
    """Deterministically run ``inputs`` through ``machine``, journaling every transition.

    ``resume_from`` seeds the initial state and skips inputs at or before the checkpoint offset,
    proving checkpoint-resume equals a cold run over the same suffix.
    """
    journal = StateJournal(partition=partition)
    state = dict(resume_from.state) if resume_from is not None else machine.initial_state()
    start_offset = resume_from.input_offset if resume_from is not None else -1
    all_events: list[Event] = []
    for offset, env in enumerate(inputs):
        if offset <= start_offset:
            continue
        result = machine.transition(state, env, params, env.get("_quality", {}))
        envelope_id = str(env.get("event_id", f"in_{offset}"))
        journal.append(journal.seq, state, result.state, envelope_id, result.events)
        state = result.state
        all_events.extend(result.events)
    return journal, all_events
