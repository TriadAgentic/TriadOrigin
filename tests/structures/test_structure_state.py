"""F08 refusal-interface + F09 break-detector battery: GV-008, mirror, invariance, payloads.

RETIRED-VERSION REPLAY EVIDENCE (Formula Repair §1.5, B03C): the F09 half of this battery pins
``break.bar_close.v1`` — now ``RETIRED_DEFECTIVE`` (see the :class:`BreakDetector` class banner)
and superseded by ``break.bar_close.v2`` (``tests/structures/test_break_v2.py``). The v1 bytes
and behavior are deliberately UNCHANGED (replay of history produced under v1; SHADOW rows keep
their version tag forever — never-blend), so these tests keep pinning the v1 machine exactly as
it was, including its retired per-``(level_id, direction)`` dedup defect. F08 and the payload
builders remain live law.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import contracts, transition  # noqa: E402
from triad_origin.journal import StateJournal, rebuild_projection  # noqa: E402
from triad_origin.structures import common, structure_state  # noqa: E402
from triad_origin.structures.common import StructureLawError  # noqa: E402
from triad_origin.structures.structure_state import (  # noqa: E402
    BreakDetector,
    ProtectedSwingStructure,
    build_structure_atom_payload,
    build_structure_transition_payload,
)

BREAK_PARAMS = {
    "break_buffer_rule": common.DECLARED_BOS_CLOSE_BUFFER,
    "observation_mode": "FINALIZED_CLOSE",
}

HEX64 = "0" * 64


def level(event_id, level_id, ticks, direction=common.LONG, confirmed=True):
    return {
        "event_id": event_id,
        "kind": "LEVEL",
        "payload": {"level_id": level_id, "level_ticks": ticks,
                    "direction": direction, "confirmed": confirmed},
    }


def close_bar(event_id, close, atr=20):
    return {
        "event_id": event_id,
        "kind": "BAR",
        "payload": {"close_ticks": close, "atr14_ticks": atr},
    }


def run_break(inputs, params=None, initial=None):
    return transition.run(BreakDetector(), inputs, params or BREAK_PARAMS, initial=initial)


def breaks(events):
    return [e for e in events if e.get("event_kind") == structure_state.BREAK_OCCURRENCE]


def abstentions(events):
    return [e for e in events if e.get("event_kind") == "NAMED_ABSTENTION"]


# --- F08: the refusal interface ------------------------------------------------------------------


def test_f08_every_input_yields_the_named_abstention_and_never_mutates_state():
    machine = ProtectedSwingStructure()
    inputs = [
        {"event_id": "e1", "kind": "BAR", "payload": {"close_ticks": 1}},
        {"event_id": "e2", "kind": "LEVEL", "payload": {"level_id": "L1"}},
        {"event_id": "e3", "payload": {}},
    ]
    result = transition.run(machine, inputs, {})
    assert result.final_state == {"structure_state": "UNINITIALIZED"}
    assert result.final_state == machine.initial_state()
    events = result.events
    assert len(events) == 3
    for event in events:
        assert event["event_kind"] == "NAMED_ABSTENTION"
        assert event["reason_code"] == "F08_UNAVAILABLE_REDUCER_VERSION_NOT_RATIFIED"
        assert event["formula"] == "F08"
        assert event["refs"]["parameter"] == "RC3-PAR-STRUCT-003"


@pytest.mark.parametrize("supplied", ["protected_dc.v1", 1, common.NOT_RATIFIED])
def test_f08_supplied_reducer_version_with_any_value_is_refused(supplied):
    result = transition.run(
        ProtectedSwingStructure(),
        [{"event_id": "e1", "kind": "BAR", "payload": {}}],
        {"protected_swing_reducer_version": supplied},
    )
    assert result.final_state == {"structure_state": "UNINITIALIZED"}
    (event,) = result.events
    assert event["reason_code"] == "F08_NO_IMPLEMENTATION_AUTHORIZED"
    assert event["refs"]["parameter"] == "RC3-PAR-STRUCT-003"


def test_f08_refusal_is_prefix_and_restart_invariant():
    inputs = [{"event_id": f"e{i}", "kind": "BAR", "payload": {}} for i in range(4)]
    full = transition.run(ProtectedSwingStructure(), inputs, {})
    head = transition.run(ProtectedSwingStructure(), inputs[:2], {})
    tail = transition.run(
        ProtectedSwingStructure(), inputs[2:], {}, initial=head.final_state)
    assert head.events + tail.events == full.events
    assert tail.final_state == full.final_state


# --- §1.5 withdrawal discipline: the v1 detector is retired-in-place, never edited ----------------


def test_v1_break_detector_carries_the_retired_defective_banner():
    doc = BreakDetector.__doc__
    assert doc is not None
    assert doc.lstrip().startswith("RETIRED_DEFECTIVE{")
    assert "TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12" in doc  # the defect_ref
    assert "break.bar_close.v2" in doc  # names its successor
    # The banner is CLASS-level only: the module still hosts live law (F08 + the payload
    # builders), so neither the module docstring nor F08 may read as withdrawn.
    assert not structure_state.__doc__.lstrip().startswith("RETIRED_DEFECTIVE")
    assert "RETIRED_DEFECTIVE" not in ProtectedSwingStructure.__doc__


def test_v2_successor_module_exists_and_is_a_distinct_identity():
    from triad_origin.structures import break_v2

    assert break_v2.V2_FORMULA_VERSION == "break.bar_close.v2"
    assert break_v2.FORMULA_F09 == structure_state.FORMULA_F09 == "F09"


# --- F09: GV-008 + boundaries --------------------------------------------------------------------


def test_gv008_atr20_buffer1_level_1000_close_1001_breaks_and_close_1000_does_not():
    assert common.evaluate_declared_rational(common.DECLARED_BOS_CLOSE_BUFFER, 20) == 1
    no_break = run_break([level("l1", "LV1", 1000), close_bar("c1", 1000)])
    assert breaks(no_break.events) == []
    broke = run_break([level("l1", "LV1", 1000), close_bar("c1", 1001)])
    (occurrence,) = breaks(broke.events)
    assert occurrence["direction"] == structure_state.UP_BREAK
    assert occurrence["level_id"] == "LV1"
    assert occurrence["level_ticks"] == 1000
    assert occurrence["buffer_ticks"] == 1
    assert occurrence["close_ticks"] == 1001
    assert occurrence["breach_event_id"] == "c1"


def test_equality_boundary_is_inclusive_and_one_tick_short_is_not():
    # ATR 40 => buffer = max(1, ceil(40/20)) = 2; equality at level+buffer passes (PAR-009).
    at_threshold = run_break(
        [level("l1", "LV1", 1000), close_bar("c1", 1002, atr=40)])
    assert len(breaks(at_threshold.events)) == 1
    one_short = run_break(
        [level("l1", "LV1", 1000), close_bar("c1", 1001, atr=40)])
    assert breaks(one_short.events) == []


def test_duplicate_break_is_idempotent_per_level_and_direction():
    result = run_break([
        level("l1", "LV1", 1000),
        close_bar("c1", 1001),
        close_bar("c2", 1005),
    ])
    assert len(breaks(result.events)) == 1


def test_exact_duplicate_envelope_is_deduped_by_the_driver():
    repeated = close_bar("c1", 1001)
    result = run_break([level("l1", "LV1", 1000), repeated, repeated])
    assert result.duplicate_count == 1
    assert len(breaks(result.events)) == 1


def test_multi_level_break_emits_in_deterministic_level_id_order():
    result = run_break([
        level("l1", "LV_B", 1000),
        level("l2", "LV_A", 990),
        level("l3", "LV_C", 995),
        close_bar("c1", 1001),
    ])
    occurred = breaks(result.events)
    assert [o["level_id"] for o in occurred] == ["LV_A", "LV_B", "LV_C"]
    assert all(o["direction"] == structure_state.UP_BREAK for o in occurred)


def test_unregistered_and_unconfirmed_levels_emit_nothing():
    before_registration = run_break([close_bar("c1", 1001)])
    assert breaks(before_registration.events) == []
    unconfirmed = run_break([
        level("l1", "LV1", 1000, confirmed=False),
        close_bar("c1", 1001),
    ])
    assert breaks(unconfirmed.events) == []
    assert unconfirmed.final_state["levels"] == {}


def test_null_atr_is_a_named_abstention_never_a_zero_buffer():
    result = run_break([level("l1", "LV1", 1000), close_bar("c1", 2000, atr=None)])
    assert breaks(result.events) == []
    (event,) = abstentions(result.events)
    assert event["reason_code"] == "F09_NO_ATR"
    assert event["formula"] == "F09"


def test_only_the_declared_par043_rule_and_finalized_close_mode_are_admitted():
    with pytest.raises(StructureLawError):
        run_break([close_bar("c1", 1000)],
                  params={"break_buffer_rule": "max(1,ceil(ATR14_ticks*1/10))",
                          "observation_mode": "FINALIZED_CLOSE"})
    with pytest.raises(StructureLawError):
        run_break([close_bar("c1", 1000)],
                  params={"break_buffer_rule": common.DECLARED_BOS_CLOSE_BUFFER,
                          "observation_mode": "TICK"})
    with pytest.raises(transition.MissingParameterError):
        run_break([close_bar("c1", 1000)],
                  params={"break_buffer_rule": common.DECLARED_BOS_CLOSE_BUFFER})


def test_conflicting_level_reregistration_refuses_and_identical_is_idempotent():
    idempotent = run_break([
        level("l1", "LV1", 1000),
        level("l2", "LV1", 1000),
        close_bar("c1", 1001),
    ])
    assert len(breaks(idempotent.events)) == 1
    with pytest.raises(StructureLawError):
        run_break([level("l1", "LV1", 1000), level("l2", "LV1", 999)])


# --- F09 mirror law ------------------------------------------------------------------------------


def test_bearish_level_mirror_close_999_breaks_down_and_close_1000_does_not():
    down = run_break(
        [level("l1", "LV1", 1000, direction=common.SHORT), close_bar("c1", 999)])
    (occurrence,) = breaks(down.events)
    assert occurrence["direction"] == structure_state.DOWN_BREAK
    assert occurrence["level_direction"] == common.SHORT
    none = run_break(
        [level("l1", "LV1", 1000, direction=common.SHORT), close_bar("c1", 1000)])
    assert breaks(none.events) == []


def test_long_short_mirror_is_exact_algebraic_symmetry():
    inputs = [
        level("l1", "LV1", 1000, direction=common.LONG),
        level("l2", "LV2", 980, direction=common.SHORT),
        close_bar("c1", 1001),
        close_bar("c2", 978),
    ]
    mirrored = []
    for env in inputs:
        payload = dict(env["payload"])
        if env["kind"] == "LEVEL":
            payload["level_ticks"] = -payload["level_ticks"]
            payload["direction"] = common.opposite(payload["direction"])
        else:
            payload["close_ticks"] = -payload["close_ticks"]
        mirrored.append({"event_id": env["event_id"], "kind": env["kind"],
                         "payload": payload})
    straight = breaks(run_break(inputs).events)
    reflected = breaks(run_break(mirrored).events)
    assert len(straight) == len(reflected) > 0
    flip = {structure_state.UP_BREAK: structure_state.DOWN_BREAK,
            structure_state.DOWN_BREAK: structure_state.UP_BREAK}
    for s, r in zip(straight, reflected):
        assert r["direction"] == flip[s["direction"]]
        assert r["level_direction"] == common.opposite(s["level_direction"])
        assert r["level_ticks"] == -s["level_ticks"]
        assert r["close_ticks"] == -s["close_ticks"]
        assert r["buffer_ticks"] == s["buffer_ticks"]
        assert r["level_id"] == s["level_id"]


# --- F09 classification law ----------------------------------------------------------------------


def test_every_occurrence_is_unclassified_because_f08_is_a_refusal_interface():
    result = run_break([
        level("l1", "LV1", 1000, direction=common.LONG),
        level("l2", "LV2", 2000, direction=common.SHORT),
        close_bar("c1", 1001),
        close_bar("c2", 1998),
    ])
    occurred = breaks(result.events)
    assert len(occurred) == 2
    for occurrence in occurred:
        assert occurrence["classification"] == (
            "UNCLASSIFIED_STRUCTURE_STATE_UNAVAILABLE")


def test_supplied_structure_state_is_refused_never_adopted_for_classification():
    result = run_break([
        level("l1", "LV1", 1000),
        {"event_id": "s1", "kind": "STRUCTURE_STATE",
         "payload": {"structure_state": "BULLISH"}},
        close_bar("c1", 1001),
    ])
    (refusal,) = abstentions(result.events)
    assert refusal["reason_code"] == "F09_CLASSIFICATION_UNAVAILABLE_REDUCER_NOT_RATIFIED"
    assert refusal["refs"]["parameter"] == "RC3-PAR-STRUCT-003"
    (occurrence,) = breaks(result.events)
    assert occurrence["classification"] == "UNCLASSIFIED_STRUCTURE_STATE_UNAVAILABLE"
    assert "structure_state" not in result.final_state


# --- F09 prefix/restart invariance ---------------------------------------------------------------


def test_break_detector_prefix_and_restart_invariance():
    inputs = [
        level("l1", "LV1", 1000),
        close_bar("c1", 999),
        level("l2", "LV2", 980, direction=common.SHORT),
        close_bar("c2", 1001),
        close_bar("c3", 978),
        close_bar("c4", 1005),
    ]
    full = run_break(inputs)
    for cut in range(1, len(inputs)):
        head = run_break(inputs[:cut])
        tail = run_break(inputs[cut:], initial=head.final_state)
        assert head.events + tail.events == full.events
        assert tail.final_state == full.final_state


def test_restart_after_a_break_never_double_counts_the_same_breach():
    inputs = [level("l1", "LV1", 1000), close_bar("c1", 1001)]
    head = run_break(inputs)
    assert len(breaks(head.events)) == 1
    tail = run_break([close_bar("c2", 1010)], initial=head.final_state)
    assert breaks(tail.events) == []


# --- Payload builders ----------------------------------------------------------------------------


def atom_payload():
    return build_structure_atom_payload(
        structure_kind="accepted_break",
        structure_subtype="up_break",
        direction=common.LONG,
        canonical_instrument_id="binance_usdm:BTCUSDT",
        venue_model="binance_usdm.v1",
        timeframe="1m",
        formula_version="triad.origin.v7.rc3.f09.v1",
        parameter_set_id="par_set_f09",
        parameter_digest=HEX64,
        original_geometry={"level_ticks": 1000, "buffer_ticks": 1, "close_ticks": 1001},
        origin_source_ids=["evt_level_1"],
        confirmation_source_ids=["evt_close_1"],
        origin_time_us=1_786_156_800_000_000,
        confirmation_time_us=1_786_156_860_000_000,
        availability_time_us=1_786_156_862_000_000,
        knowledge_time_us=1_786_156_862_000_000,
        reference_level_ids=["LV1"],
        source_offset_range=["0", "2"],
        dependency_quality={"atr": "READY"},
        build_commit="deadbeef",
        config_bundle_sha256=HEX64,
        instrument_digest=HEX64,
    )


def test_structure_atom_payload_is_contract_valid_and_identity_derived():
    payload = atom_payload()
    contracts.validate_payload("triad.structure_atom.v2", payload)
    assert payload["state"] == "CONFIRMED"
    assert payload["structure_id"].startswith("str_")
    assert payload["semantic_instance_id"].startswith("sinst_")
    assert payload["original_geometry_digest"] == common.geometry_digest(
        payload["original_geometry"])
    assert atom_payload() == payload


def test_structure_transition_payload_is_contract_valid():
    payload = build_structure_transition_payload(
        transition_id="stx_" + "a" * 40,
        structure_id="str_" + "b" * 40,
        state_seq=0,
        previous_transition_id="genesis",
        from_state="UNINITIALIZED",
        to_state="CONFIRMED",
        transition_reason="accepted_break",
        geometry_revision=0,
        current_geometry={"level_ticks": 1000},
        event_time_us=1,
        receipt_time_us=2,
        knowledge_at_us=3,
        publication_time_us=4,
        source_event_ids=["evt_close_1"],
        reference_ids=["LV1"],
        watermark_complete=True,
        quality_snapshot={"validity": "READY"},
        provenance_hash=HEX64,
    )
    contracts.validate_payload("triad.structure_transition.v2", payload)
    assert payload["state_seq"] == "0"
    assert payload["geometry_revision"] == "0"


def test_builders_fail_closed_on_wrong_shapes():
    with pytest.raises(StructureLawError):
        build_structure_transition_payload(
            transition_id="t", structure_id="s", state_seq=-1,
            previous_transition_id="genesis", from_state="a", to_state="b",
            transition_reason="r", geometry_revision=0, current_geometry={},
            event_time_us=1, receipt_time_us=2, knowledge_at_us=3,
            publication_time_us=4, source_event_ids=[], reference_ids=[],
            watermark_complete=True, quality_snapshot={}, provenance_hash=HEX64)
    with pytest.raises(StructureLawError):
        build_structure_transition_payload(
            transition_id="t", structure_id="s", state_seq=0,
            previous_transition_id="genesis", from_state="a", to_state="b",
            transition_reason="r", geometry_revision=0, current_geometry={},
            event_time_us=1, receipt_time_us=2, knowledge_at_us=3,
            publication_time_us=4, source_event_ids=[], reference_ids=[],
            watermark_complete=1, quality_snapshot={}, provenance_hash=HEX64)
    with pytest.raises(StructureLawError):
        atom = atom_payload()
        build_structure_atom_payload(
            structure_kind="accepted_break", structure_subtype="up_break",
            direction="UP", canonical_instrument_id="i", venue_model="v",
            timeframe="1m", formula_version="f", parameter_set_id="p",
            parameter_digest=HEX64, original_geometry=atom["original_geometry"],
            origin_source_ids=["e"], confirmation_source_ids=["e"],
            origin_time_us=1, confirmation_time_us=2, availability_time_us=3,
            knowledge_time_us=4, reference_level_ids=[], source_offset_range=[],
            dependency_quality={}, build_commit="c",
            config_bundle_sha256=HEX64, instrument_digest=HEX64)


# --- Journal round-trip --------------------------------------------------------------------------


def test_built_atom_payload_round_trips_through_the_state_journal():
    payload = atom_payload()
    atom_event = {"event_kind": "STRUCTURE_CONFIRMED", "payload": payload}
    journal = StateJournal(partition="structure_atoms")
    record = journal.append(
        journal.seq, {}, {"last_atom": payload}, "evt_atom_append", (atom_event,))
    assert record is not None
    projection = journal.project()
    assert projection == {"last_atom": payload}
    rebuilt = rebuild_projection(journal.partition, journal.records())
    assert rebuilt == {"last_atom": payload}
    (round_tripped,) = record.events
    assert round_tripped["payload"] == payload
    contracts.validate_payload("triad.structure_atom.v2", round_tripped["payload"])
    transition_payload = build_structure_transition_payload(
        transition_id=record.transition_id,
        structure_id=payload["structure_id"],
        state_seq=record.state_seq,
        previous_transition_id=record.previous_transition_id,
        from_state="UNINITIALIZED",
        to_state="CONFIRMED",
        transition_reason="accepted_break",
        geometry_revision=0,
        current_geometry=payload["original_geometry"],
        event_time_us=payload["confirmation_time_us"],
        receipt_time_us=payload["availability_time_us"],
        knowledge_at_us=payload["knowledge_time_us"],
        publication_time_us=payload["availability_time_us"],
        source_event_ids=list(payload["confirmation_source_ids"]),
        reference_ids=list(payload["reference_level_ids"]),
        watermark_complete=True,
        quality_snapshot=payload["dependency_quality"],
        provenance_hash=record.to_state_digest,
    )
    contracts.validate_payload("triad.structure_transition.v2", transition_payload)
