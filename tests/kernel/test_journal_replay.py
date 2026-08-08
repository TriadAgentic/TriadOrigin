"""State journal compare-and-append + replay determinism (prefix/restart/duplicate invariance)."""

from __future__ import annotations

import pytest

from triad_origin import journal as J
from triad_origin.checkpoint import Checkpoint
from triad_origin.transition import DeterministicMachine, TransitionResult


class CounterMachine:
    """A tiny deterministic machine that counts TICK envelopes and dedupes by event_id.

    Deduping by event id gives duplicate invariance: retransmission changes no semantic state.
    """

    def initial_state(self) -> dict:
        return {"count": 0, "seen": []}

    def transition(self, state, envelope, params, quality) -> TransitionResult:
        eid = envelope.get("event_id")
        if envelope.get("kind") != "TICK" or eid in state["seen"]:
            return TransitionResult(state=state)  # no-op (duplicate or irrelevant)
        new = {"count": state["count"] + 1, "seen": [*state["seen"], eid]}
        return TransitionResult(state=new, events=({"n": new["count"]},))


def _inputs(n: int) -> list[dict]:
    return [{"event_id": f"e{i}", "kind": "TICK"} for i in range(n)]


def test_compare_and_append_conflict():
    jr = J.StateJournal(partition="p")
    jr.append(-1, {}, {"a": 1}, "e0", ())
    with pytest.raises(J.JournalError):
        jr.append(-1, {"a": 1}, {"a": 2}, "e1", ())  # wrong expected prev seq


def test_projection_rebuilds_from_journal():
    m: DeterministicMachine = CounterMachine()
    jr, events = J.replay(m, _inputs(3), {}, partition="p")
    assert jr.project()["count"] == 3
    assert [e["n"] for e in events] == [1, 2, 3]
    assert jr.seq == 2


def test_replay_is_deterministic():
    m = CounterMachine()
    a, ea = J.replay(m, _inputs(5), {})
    b, eb = J.replay(m, _inputs(5), {})
    assert [r.transition_id for r in a.records()] == [r.transition_id for r in b.records()]
    assert ea == eb


def test_duplicate_invariance():
    m = CounterMachine()
    clean = _inputs(3)
    dup = [clean[0], clean[0], clean[1], clean[2], clean[2]]
    j_clean, _ = J.replay(m, clean, {})
    j_dup, _ = J.replay(m, dup, {})
    # Duplicates are absorbed: final count is identical.
    assert j_clean.project()["count"] == j_dup.project()["count"] == 3


def test_checkpoint_resume_equals_cold_suffix():
    m = CounterMachine()
    full = _inputs(6)
    # Cold run over all six.
    cold, _ = J.replay(m, full, {})
    cold_state = cold.project()
    # Resume from a checkpoint taken after input offset 2, replay the suffix.
    mid, _ = J.replay(m, full[:3], {})
    checkpoint = Checkpoint(partition="p", state=mid.project(), input_offset=2)
    resumed, _ = J.replay(m, full, {}, resume_from=checkpoint)
    assert resumed.project() == cold_state  # restart invariance
