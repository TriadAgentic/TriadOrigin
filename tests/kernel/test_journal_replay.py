"""State journal compare-and-append + replay determinism (prefix/restart/duplicate invariance)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from threading import Barrier

import pytest

from triad_origin import journal as J
from triad_origin import transition as T
from triad_origin.canonical import canonical_json, sha256_hex
from triad_origin.checkpoint import Checkpoint, CheckpointError, REQUIRED_DIGEST_KEYS
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


def _resume_checkpoint(
    state: dict,
    input_offset: int,
    *,
    state_seq: int,
    last_transition_id: str,
) -> Checkpoint:
    return Checkpoint(
        partition="p",
        state=state,
        input_segment="input-000001",
        input_offset=input_offset,
        input_prefix_digest=sha256_hex(canonical_json(_inputs(input_offset + 1))),
        last_domain_event_id=f"e{input_offset}",
        highest_producer_epoch=1,
        projection_checksum=sha256_hex(canonical_json(state)),
        output_segment="output-000001",
        output_offset=input_offset,
        state_seq=state_seq,
        last_transition_id=last_transition_id,
        digests={name: sha256_hex(name.encode("utf-8")) for name in REQUIRED_DIGEST_KEYS},
    )


def _resume_context(checkpoint: Checkpoint) -> J.ReplayContext:
    return J.ReplayContext(
        input_segment=checkpoint.input_segment,
        input_prefix_digest=checkpoint.input_prefix_digest,
        output_segment=checkpoint.output_segment,
        output_offset=checkpoint.output_offset,
        highest_producer_epoch=checkpoint.highest_producer_epoch,
        state_seq=checkpoint.state_seq,
        last_transition_id=checkpoint.last_transition_id,
        projection_checksum=checkpoint.projection_checksum,
        digests=checkpoint.digests,
    )


def test_compare_and_append_conflict():
    jr = J.StateJournal(partition="p")
    jr.append(-1, {}, {"a": 1}, "e0", ())
    with pytest.raises(J.JournalError):
        jr.append(-1, {"a": 1}, {"a": 2}, "e1", ())  # wrong expected prev seq


def test_journal_partition_identity_is_immutable_after_construction():
    journal = J.StateJournal(partition="e\u0301")
    assert journal.partition == "é"
    with pytest.raises(J.JournalError, match="immutable"):
        journal.partition = "other"


def test_compare_and_append_is_atomic_under_concurrency():
    journal = J.StateJournal(partition="p")
    barrier = Barrier(2)

    def append(index):
        barrier.wait()
        try:
            journal.append(-1, {}, {"winner": index}, f"e{index}", ())
        except J.JournalError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(append, [1, 2]))
    assert sorted(outcomes) == [False, True]
    assert len(journal.records()) == 1
    assert journal.project()["winner"] in {1, 2}


def test_compare_and_append_rejects_state_discontinuity():
    jr = J.StateJournal(partition="p")
    jr.append(-1, {}, {"x": 1}, "e0", ())
    with pytest.raises(J.JournalError, match="continuity"):
        jr.append(0, {"attacker": 1}, {"x": 2}, "e1", ())


def test_returned_records_cannot_mutate_internal_chain():
    jr = J.StateJournal(partition="p")
    record = jr.append(-1, {}, {"x": 1}, "e0", ({"out": 1},))
    assert record is not None
    with pytest.raises(FrozenInstanceError):
        record.to_state_digest = sha256_hex(canonical_json({"owned": True}))
    projected = record.to_state
    projected["owned"] = True
    returned_event = record.events[0]
    returned_event["out"] = 999
    assert jr.project() == {"x": 1}
    assert jr.records()[0].events == ({"out": 1},)
    with pytest.raises(J.JournalError, match="continuity"):
        jr.append(0, {"owned": True}, {"x": 2}, "e1", ())


def test_exported_records_rebuild_and_authenticate_projection():
    jr, _ = J.replay(CounterMachine(), _inputs(3), {}, partition="p")
    exported = jr.records()
    assert J.rebuild_projection("p", exported) == jr.project()
    corrupted = [*exported[:-1], replace(exported[-1], events_digest="0" * 64)]
    with pytest.raises(J.JournalError, match="event bytes"):
        J.rebuild_projection("p", corrupted)


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


def test_live_and_replay_drivers_snapshot_envelope_params_and_result_aliases():
    class MutatingMachine:
        def initial_state(self):
            return {"seen": []}

        def transition(self, state, envelope, params, quality):
            state["seen"].append({
                "event_id": envelope["event_id"],
                "shape": type(envelope["shape"]).__name__,
                "parameter": params["x"],
            })
            params["x"] = 999
            envelope["event_id"] = "forged"
            return TransitionResult(state, ({"value": state["seen"][-1]["parameter"]},))

    inputs = [
        {"event_id": "e1", "shape": (1, 2)},
        {"event_id": "e2", "shape": [1, 2]},
    ]
    live = T.run(MutatingMachine(), inputs, {"x": 7})
    replayed, replay_events = J.replay(MutatingMachine(), inputs, {"x": 7})
    assert live.final_state == replayed.project()
    assert live.events == replay_events == [{"value": 7}, {"value": 7}]
    assert [record.envelope_id for record in replayed.records()] == ["e1", "e2"]
    assert [item["shape"] for item in live.final_state["seen"]] == ["list", "list"]


def test_drivers_use_only_recorded_quality_and_reject_non_tuple_events():
    class ObservingMachine:
        def initial_state(self):
            return {"quality": None, "value": None}

        def transition(self, state, envelope, params, quality):
            state["value"] = envelope["value"]
            state["quality"] = quality.get("grade")
            return TransitionResult(state)

    inputs = [{"event_id": "e", "value": 1, "_quality": {"grade": "GOOD"}}]
    result = T.run(ObservingMachine(), inputs, {})
    replayed, _ = J.replay(ObservingMachine(), inputs, {})
    assert result.final_state == replayed.project() == {"quality": "GOOD", "value": 1}
    with pytest.raises(TypeError, match="recorded"):
        T.run(ObservingMachine(), inputs, {}, quality_of=lambda envelope: {})

    class BadEvents(ObservingMachine):
        def transition(self, state, envelope, params, quality):
            return TransitionResult(state, [])

    with pytest.raises(TypeError, match="tuple"):
        T.run(BadEvents(), [{"event_id": "e", "value": 1}], {})


def test_duplicate_invariance():
    m = CounterMachine()
    clean = _inputs(3)
    dup = [clean[0], clean[0], clean[1], clean[2], clean[2]]
    j_clean, clean_events = J.replay(m, clean, {})
    j_dup, dup_events = J.replay(m, dup, {})
    # Exact retransmissions are absorbed before the machine and perturb neither sequence nor IDs.
    assert j_clean.project()["count"] == j_dup.project()["count"] == 3
    assert j_dup.duplicate_count == 2
    assert dup_events == clean_events
    assert [r.transition_id for r in j_dup.records()] == [
        r.transition_id for r in j_clean.records()
    ]


def test_live_and_replay_absorb_duplicate_before_non_deduping_machine():
    class CountsEveryCall:
        def initial_state(self):
            return {"count": 0}

        def transition(self, state, envelope, params, quality):
            state["count"] += 1
            return TransitionResult(state, ({"count": state["count"]},))

    event = {"event_id": "same", "revision": 0, "kind": "TICK"}
    live = T.run(CountsEveryCall(), [event, event], {})
    replayed, replay_events = J.replay(CountsEveryCall(), [event, event], {})
    assert live.final_state == replayed.project() == {"count": 1}
    assert live.events == replay_events == [{"count": 1}]
    assert live.duplicate_count == replayed.duplicate_count == 1


def test_same_event_revision_with_different_bytes_fails_closed():
    conflicting = [
        {"event_id": "e0", "revision": 1, "kind": "TICK", "value": 1},
        {"event_id": "e0", "revision": 1, "kind": "TICK", "value": 2},
    ]
    with pytest.raises(J.JournalError, match="conflicting canonical bytes"):
        J.replay(CounterMachine(), conflicting, {})


def test_semantic_noop_is_not_journaled():
    journal, events = J.replay(
        CounterMachine(), [{"event_id": "noop", "kind": "OTHER"}], {}
    )
    assert journal.seq == -1
    assert journal.records() == []
    assert events == []


def test_checkpoint_resume_equals_cold_suffix():
    m = CounterMachine()
    full = _inputs(6)
    # Cold run over all six.
    cold, _ = J.replay(m, full, {}, partition="p")
    cold_state = cold.project()
    # Resume from a checkpoint taken after input offset 2, replay the suffix.
    mid, _ = J.replay(m, full[:3], {}, partition="p")
    checkpoint = _resume_checkpoint(
        mid.project(),
        2,
        state_seq=mid.seq,
        last_transition_id=mid.records()[-1].transition_id,
    ).sealed()
    resumed, _ = J.replay(
        m,
        full,
        {},
        partition="p",
        resume_from=checkpoint,
        resume_context=_resume_context(checkpoint),
    )
    assert resumed.project() == cold_state  # restart invariance
    assert [record.transition_id for record in resumed.records()] == [
        record.transition_id for record in cold.records()[3:]
    ]


def test_checkpoint_resume_normalizes_canonical_partition_identity():
    inputs = _inputs(2)
    decomposed = "e\u0301"
    cold, _ = J.replay(CounterMachine(), inputs[:1], {}, partition=decomposed)
    checkpoint = Checkpoint(
        partition=decomposed,
        state=cold.project(),
        input_segment="input-000001",
        input_offset=0,
        input_prefix_digest=sha256_hex(canonical_json(inputs[:1])),
        last_domain_event_id="e0",
        highest_producer_epoch=1,
        projection_checksum=sha256_hex(canonical_json(cold.project())),
        output_segment="output-000001",
        output_offset=0,
        state_seq=cold.seq,
        last_transition_id=cold.records()[-1].transition_id,
        digests={name: sha256_hex(name.encode()) for name in REQUIRED_DIGEST_KEYS},
    ).sealed()
    resumed, _ = J.replay(
        CounterMachine(), inputs, {}, partition=decomposed,
        resume_from=checkpoint, resume_context=_resume_context(checkpoint),
    )
    assert resumed.partition == "é"


def test_replay_rejects_unsealed_checkpoint_object():
    checkpoint = _resume_checkpoint(
        {"count": 1, "seen": ["e0"]},
        0,
        state_seq=0,
        last_transition_id="stx_fixture",
    )
    with pytest.raises(CheckpointError, match="state_checksum"):
        J.replay(
            CounterMachine(),
            _inputs(2),
            {},
            partition="p",
            resume_from=checkpoint,
            resume_context=_resume_context(checkpoint),
        )


def test_replay_binds_checkpoint_to_partition_tape_and_context():
    inputs = _inputs(3)
    mid, _ = J.replay(CounterMachine(), inputs[:2], {}, partition="p")
    checkpoint = _resume_checkpoint(
        mid.project(),
        1,
        state_seq=mid.seq,
        last_transition_id=mid.records()[-1].transition_id,
    ).sealed()
    context = _resume_context(checkpoint)

    with pytest.raises(J.JournalError, match="partition"):
        J.replay(
            CounterMachine(), inputs, {}, partition="other",
            resume_from=checkpoint, resume_context=context,
        )

    wrong_tape = list(inputs)
    wrong_tape[1] = {"event_id": "different", "kind": "TICK"}
    with pytest.raises(J.JournalError, match="last domain event"):
        J.replay(
            CounterMachine(), wrong_tape, {}, partition="p",
            resume_from=checkpoint, resume_context=context,
        )

    changed_prefix = list(inputs)
    changed_prefix[0] = {**changed_prefix[0], "kind": "OTHER"}
    with pytest.raises(J.JournalError, match="input prefix digest"):
        J.replay(
            CounterMachine(), changed_prefix, {}, partition="p",
            resume_from=checkpoint, resume_context=context,
        )

    with pytest.raises(J.JournalError, match="replay/build context"):
        J.replay(
            CounterMachine(), inputs, {}, partition="p", resume_from=checkpoint,
            resume_context=replace(context, input_segment="other-input"),
        )

    with pytest.raises(J.JournalError, match="independently supplied context"):
        J.replay(CounterMachine(), inputs, {}, partition="p", resume_from=checkpoint)


def test_replay_rejects_checkpoint_offset_outside_input_segment():
    checkpoint = _resume_checkpoint(
        {"count": 4, "seen": ["e0", "e1", "e2", "e3"]},
        3,
        state_seq=3,
        last_transition_id="stx_fixture",
    ).sealed()
    with pytest.raises(J.JournalError, match="outside"):
        J.replay(
            CounterMachine(), _inputs(3), {}, partition="p",
            resume_from=checkpoint, resume_context=_resume_context(checkpoint),
        )
