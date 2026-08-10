"""W05 generic lifecycle-reducer battery: every legal graph edge succeeds, every illegal edge
(incl. from a terminal state, incl. skipping FORMED for an unknown id) is rejected with zero state
mutation, WITHDRAWN is reachable from every non-terminal state, a repeated (same- or
different-trigger) already-achieved transition is idempotent, and prefix/restart/duplicate
invariance holds."""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import transition  # noqa: E402
from triad_origin.structures import lifecycle_reducer as lr  # noqa: E402
from triad_origin.structures.common import StructureLawError  # noqa: E402
from triad_origin.structures.lifecycle_reducer import LifecycleReducer  # noqa: E402


def req(event_id, structure_id, requested_transition, trigger_event_id):
    return {"event_id": event_id, "kind": "TRANSITION_REQUEST",
            "payload": {"structure_id": structure_id, "requested_transition": requested_transition,
                        "trigger_event_id": trigger_event_id}}


def run(inputs, initial=None):
    return transition.run(LifecycleReducer(), inputs, {}, initial=initial)


def transitioned(events):
    return [e for e in events if e.get("event_kind") == lr.LIFECYCLE_TRANSITIONED]


def illegal(events):
    return [e for e in events if e.get("event_kind") == "NAMED_ABSTENTION"]


# --- Graph shape ------------------------------------------------------------------------------


def test_terminal_states_have_no_legal_successors():
    for state in (lr.STATE_FULLY_FILLED, lr.STATE_EXPIRED, lr.STATE_WITHDRAWN, lr.STATE_BROKEN):
        assert lr._LEGAL_SUCCESSORS[state] == ()


def test_withdrawn_is_a_declared_successor_of_every_non_terminal_state():
    for state in (lr.STATE_FORMED, lr.STATE_CONFIRMED, lr.STATE_PARTIALLY_FILLED):
        assert lr.STATE_WITHDRAWN in lr._LEGAL_SUCCESSORS[state]


# --- Every legal edge succeeds ------------------------------------------------------------------

_LADDER = {
    None: [],
    lr.STATE_FORMED: [lr.STATE_FORMED],
    lr.STATE_CONFIRMED: [lr.STATE_FORMED, lr.STATE_CONFIRMED],
    lr.STATE_PARTIALLY_FILLED: [lr.STATE_FORMED, lr.STATE_CONFIRMED, lr.STATE_PARTIALLY_FILLED],
}

_LEGAL_EDGES = [
    (None, lr.STATE_FORMED),
    (lr.STATE_FORMED, lr.STATE_CONFIRMED),
    (lr.STATE_FORMED, lr.STATE_EXPIRED),
    (lr.STATE_FORMED, lr.STATE_WITHDRAWN),
    (lr.STATE_CONFIRMED, lr.STATE_PARTIALLY_FILLED),
    (lr.STATE_CONFIRMED, lr.STATE_FULLY_FILLED),
    (lr.STATE_CONFIRMED, lr.STATE_BROKEN),
    (lr.STATE_CONFIRMED, lr.STATE_WITHDRAWN),
    (lr.STATE_PARTIALLY_FILLED, lr.STATE_FULLY_FILLED),
    (lr.STATE_PARTIALLY_FILLED, lr.STATE_EXPIRED),
    (lr.STATE_PARTIALLY_FILLED, lr.STATE_WITHDRAWN),
]


@pytest.mark.parametrize("from_state,to_state", _LEGAL_EDGES)
def test_every_legal_edge_succeeds(from_state, to_state):
    structure_id = f"edge_{from_state}_{to_state}"
    reach = [req(f"{structure_id}_r{i}", structure_id, step, f"{structure_id}_t{i}")
             for i, step in enumerate(_LADDER[from_state])]
    final_req = req(f"{structure_id}_final", structure_id, to_state, f"{structure_id}_trigger")
    result = run(reach + [final_req])
    events = transitioned(result.events)
    assert events[-1]["to_state"] == to_state
    assert events[-1]["from_state"] == (from_state if from_state is not None else lr._UNSEEN)
    assert events[-1]["trigger_event_id"] == f"{structure_id}_trigger"
    assert result.final_state["structures"][structure_id]["state"] == to_state
    assert illegal(result.events) == []


# --- Every illegal edge is rejected with zero state mutation --------------------------------------

_ILLEGAL_CASES = [
    ([], lr.STATE_CONFIRMED),                                     # unknown id, non-FORMED first
    ([], lr.STATE_PARTIALLY_FILLED),                              # unknown id, non-FORMED first
    ([lr.STATE_FORMED], lr.STATE_PARTIALLY_FILLED),                # FORMED has no such edge
    ([lr.STATE_FORMED, lr.STATE_CONFIRMED], lr.STATE_EXPIRED),     # CONFIRMED has no such edge
    ([lr.STATE_FORMED, lr.STATE_CONFIRMED, lr.STATE_PARTIALLY_FILLED],
     lr.STATE_CONFIRMED),                                          # PARTIALLY_FILLED can't go back
    ([lr.STATE_FORMED, lr.STATE_CONFIRMED, lr.STATE_FULLY_FILLED],
     lr.STATE_WITHDRAWN),                                          # from a terminal state
    ([lr.STATE_FORMED, lr.STATE_EXPIRED], lr.STATE_CONFIRMED),     # from a terminal state
    ([lr.STATE_FORMED, lr.STATE_WITHDRAWN], lr.STATE_CONFIRMED),   # from a terminal state
    ([lr.STATE_FORMED, lr.STATE_CONFIRMED, lr.STATE_BROKEN],
     lr.STATE_WITHDRAWN),                                          # from a terminal state
]


def test_every_illegal_edge_is_rejected_with_zero_state_mutation():
    for index, (path, illegal_target) in enumerate(_ILLEGAL_CASES):
        structure_id = f"bad_{index}"
        reach = [req(f"{structure_id}_r{i}", structure_id, step, f"{structure_id}_t{i}")
                 for i, step in enumerate(path)]
        pre = run(reach)
        attempt = req(
            f"{structure_id}_bad", structure_id, illegal_target, f"{structure_id}_trigger_bad")
        result = run(reach + [attempt])
        rejected = illegal(result.events)
        assert len(rejected) == 1, f"case {index}: expected exactly one rejection"
        assert rejected[0]["reason_code"] == lr.LIFECYCLE_ILLEGAL_TRANSITION
        assert rejected[0]["formula"] == lr.FORMULA_W05
        assert rejected[0]["refs"]["structure_id"] == structure_id
        assert rejected[0]["refs"]["requested_transition"] == illegal_target
        before = pre.final_state["structures"].get(structure_id)
        after = result.final_state["structures"].get(structure_id)
        assert after == before, f"case {index}: structure state mutated on an illegal request"


def test_unknown_structure_id_first_request_must_be_formed():
    result = run([req("r1", "never_seen", lr.STATE_CONFIRMED, "trg")])
    (event,) = illegal(result.events)
    assert event["refs"]["from_state"] == lr._UNSEEN
    assert result.final_state["structures"] == {}


# --- Idempotency: same or different trigger targeting the already-achieved state --------------


def test_idempotent_repeat_with_the_same_trigger_is_a_no_op():
    reach = [req("r0", "s1", lr.STATE_FORMED, "trg0")]
    once = run(reach)
    repeated = run(reach + [req("r0_repeat", "s1", lr.STATE_FORMED, "trg0")])
    assert len(transitioned(repeated.events)) == 1
    assert illegal(repeated.events) == []
    assert repeated.final_state == once.final_state


def test_idempotent_repeat_with_a_different_trigger_is_also_a_no_op():
    reach = [req("r0", "s1", lr.STATE_FORMED, "trg0")]
    once = run(reach)
    repeated = run(reach + [req("r0_again", "s1", lr.STATE_FORMED, "trg_DIFFERENT")])
    assert len(transitioned(repeated.events)) == 1
    assert illegal(repeated.events) == []
    assert repeated.final_state == once.final_state


def test_idempotent_repeat_holds_past_formation_too():
    reach = [req("r0", "s1", lr.STATE_FORMED, "t0"),
             req("r1", "s1", lr.STATE_CONFIRMED, "t1")]
    once = run(reach)
    repeated = run(reach + [req("r1_again", "s1", lr.STATE_CONFIRMED, "t1_DIFFERENT")])
    assert len(transitioned(repeated.events)) == 2
    assert illegal(repeated.events) == []
    assert repeated.final_state == once.final_state


# --- Frozen shape: the envelope carries no geometry field, structurally -----------------------


def test_transition_request_envelope_shape_carries_no_geometry_field():
    envelope = req("r0", "s1", lr.STATE_FORMED, "t0")
    assert set(envelope["payload"]) == {"structure_id", "requested_transition", "trigger_event_id"}


# --- Prefix / restart / duplicate invariance -----------------------------------------------------


def _full_lifecycle():
    return [
        req("r0", "s1", lr.STATE_FORMED, "t0"),
        req("r1", "s1", lr.STATE_CONFIRMED, "t1"),
        req("r2", "s1", lr.STATE_PARTIALLY_FILLED, "t2"),
        req("r3", "s1", lr.STATE_FULLY_FILLED, "t3"),
    ]


def test_prefix_and_restart_invariance_across_every_cut_point():
    inputs = _full_lifecycle()
    full = run(inputs)
    for cut in range(1, len(inputs)):
        head = run(inputs[:cut])
        tail = run(inputs[cut:], initial=head.final_state)
        assert head.events + tail.events == full.events
        assert tail.final_state == full.final_state


def test_prefix_and_restart_invariance_on_an_illegal_transition():
    inputs = [
        req("r0", "s1", lr.STATE_FORMED, "t0"),
        req("r1", "s1", lr.STATE_PARTIALLY_FILLED, "t1"),  # illegal: FORMED has no such edge
        req("r2", "s1", lr.STATE_CONFIRMED, "t2"),          # legal, from the still-FORMED state
    ]
    full = run(inputs)
    for cut in range(1, len(inputs)):
        head = run(inputs[:cut])
        tail = run(inputs[cut:], initial=head.final_state)
        assert head.events + tail.events == full.events
        assert tail.final_state == full.final_state


def test_exact_duplicate_envelope_is_deduped_by_the_driver():
    repeated = req("r0", "s1", lr.STATE_FORMED, "t0")
    result = run([repeated, repeated])
    assert result.duplicate_count == 1


# --- Fail-closed envelope shape law ---------------------------------------------------------------


def test_wrong_kind_refuses():
    with pytest.raises(StructureLawError):
        run([{"event_id": "e1", "kind": "BAR", "payload": {}}])


def test_non_object_payload_refuses():
    with pytest.raises(StructureLawError):
        run([{"event_id": "e1", "kind": "TRANSITION_REQUEST", "payload": "not a dict"}])


def test_missing_structure_id_refuses():
    with pytest.raises(StructureLawError):
        run([{"event_id": "e1", "kind": "TRANSITION_REQUEST",
              "payload": {"requested_transition": lr.STATE_FORMED, "trigger_event_id": "t"}}])


def test_missing_trigger_event_id_refuses():
    with pytest.raises(StructureLawError):
        run([{"event_id": "e1", "kind": "TRANSITION_REQUEST",
              "payload": {"structure_id": "s1", "requested_transition": lr.STATE_FORMED}}])


def test_unknown_requested_transition_refuses():
    with pytest.raises(StructureLawError):
        run([req("e1", "s1", "NOT_A_REAL_STATE", "t1")])


# --- W05 transition identity (RC3 WIRE-W05 monotonic-state-machine law) --------------------------


class TestTransitionIdentity:
    """Every legal transition carries a per-structure monotonic ordinal, a deterministic
    transition id derived from EXACTLY the wiring row's field list (structure id, from/to state,
    trigger event, ordinal), and the previous transition id chaining the structure's history."""

    def test_first_transition_is_ordinal_zero_with_an_empty_previous_id(self):
        result = run([req("r0", "s1", lr.STATE_FORMED, "t0")])
        (event,) = transitioned(result.events)
        assert event["state_seq"] == "0"
        assert event["previous_transition_id"] == ""
        assert event["transition_id"] == lr._transition_id(
            "s1", lr._UNSEEN, lr.STATE_FORMED, "t0", 0)
        record = result.final_state["structures"]["s1"]
        assert record["state_seq"] == 0
        assert record["transition_id"] == event["transition_id"]

    def test_ordinal_is_per_structure_monotonic_and_previous_chains(self):
        inputs = [
            req("r0", "s1", lr.STATE_FORMED, "t0"),
            req("r1", "s1", lr.STATE_CONFIRMED, "t1"),
            req("r2", "s1", lr.STATE_PARTIALLY_FILLED, "t2"),
            req("r3", "s1", lr.STATE_FULLY_FILLED, "t3"),
        ]
        events = transitioned(run(inputs).events)
        assert [e["state_seq"] for e in events] == ["0", "1", "2", "3"]
        assert events[0]["previous_transition_id"] == ""
        for prev, cur in zip(events, events[1:]):
            assert cur["previous_transition_id"] == prev["transition_id"]
        # Every id is derived from EXACTLY the wiring row's own five fields.
        from_states = [lr._UNSEEN, lr.STATE_FORMED, lr.STATE_CONFIRMED, lr.STATE_PARTIALLY_FILLED]
        to_states = [lr.STATE_FORMED, lr.STATE_CONFIRMED, lr.STATE_PARTIALLY_FILLED,
                     lr.STATE_FULLY_FILLED]
        for i, event in enumerate(events):
            assert event["transition_id"] == lr._transition_id(
                "s1", from_states[i], to_states[i], f"t{i}", i)

    def test_transition_ids_are_unique_across_a_chain(self):
        inputs = [
            req("r0", "s1", lr.STATE_FORMED, "t0"),
            req("r1", "s1", lr.STATE_CONFIRMED, "t1"),
            req("r2", "s1", lr.STATE_BROKEN, "t2"),
        ]
        ids = [e["transition_id"] for e in transitioned(run(inputs).events)]
        assert len(set(ids)) == len(ids)

    def test_trigger_event_id_is_part_of_the_transition_identity(self):
        # The wiring row names the trigger event an identity field: the SAME
        # (structure, from, to, ordinal) under a different trigger is a different id.
        assert (lr._transition_id("s1", lr._UNSEEN, lr.STATE_FORMED, "tA", 0)
                != lr._transition_id("s1", lr._UNSEEN, lr.STATE_FORMED, "tB", 0))

    def test_idempotent_noop_neither_advances_the_ordinal_nor_mints_an_id(self):
        reach = [req("r0", "s1", lr.STATE_FORMED, "t0"),
                 req("r1", "s1", lr.STATE_CONFIRMED, "t1")]
        once = run(reach)
        repeated = run(reach + [req("r2", "s1", lr.STATE_CONFIRMED, "t_DIFFERENT")])
        assert repeated.final_state["structures"]["s1"] == once.final_state["structures"]["s1"]
        assert len(transitioned(repeated.events)) == 2

    def test_illegal_transition_neither_advances_the_ordinal_nor_mints_an_id(self):
        reach = [req("r0", "s1", lr.STATE_FORMED, "t0")]
        legal = run(reach)
        result = run(reach + [req("r1", "s1", lr.STATE_PARTIALLY_FILLED, "t1")])  # illegal edge
        assert result.final_state["structures"]["s1"] == legal.final_state["structures"]["s1"]
        assert result.final_state["structures"]["s1"]["state_seq"] == 0

    def test_restart_continues_the_same_ordinal_chain(self):
        head = run([req("r0", "s1", lr.STATE_FORMED, "t0")])
        tail = run([req("r1", "s1", lr.STATE_CONFIRMED, "t1")], initial=head.final_state)
        (confirmed,) = transitioned(tail.events)
        assert confirmed["state_seq"] == "1"
        assert (confirmed["previous_transition_id"]
                == head.final_state["structures"]["s1"]["transition_id"])
        assert tail.final_state["structures"]["s1"]["state_seq"] == 1
