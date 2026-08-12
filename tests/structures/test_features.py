"""F02 ATR + F05 rolling-extreme battery: GV-004, gap poisoning, mirror, invariance, snapshot."""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import contracts, features, transition  # noqa: E402
from triad_origin.e01_interface import (  # noqa: E402
    E01_BAR_OUT_OF_ORDER,
    E01_BAR_REVISION_CONFLICT,
)
from triad_origin.structures.common import StructureLawError  # noqa: E402


def bar(index, o, h, l, c, event_id=None):
    return {
        "event_id": event_id or f"bar_{index}",
        "payload": {
            "state_kind": "BAR",
            "bar_finalization_state": "FINALIZED",
            "watermark_complete": True,
            "validity": "READY",
            "bar_index": index,
            "bar_open_time_us": index * 60_000_000,
            "bar_close_time_us": (index + 1) * 60_000_000,
            "open_ticks": o,
            "high_ticks": h,
            "low_ticks": l,
            "close_ticks": c,
        },
    }


def flat_tr8(index, event_id=None):
    return bar(index, 1000, 1008, 1000, 1000, event_id)


def reflect(env):
    p = dict(env["payload"])
    p["open_ticks"], p["close_ticks"] = -p["open_ticks"], -p["close_ticks"]
    p["high_ticks"], p["low_ticks"] = -p["low_ticks"], -p["high_ticks"]
    return {"event_id": env["event_id"], "payload": p}


ATR_PARAMS = {"atr_period": 14}


def run_atr(inputs, params=None, initial=None):
    return transition.run(features.AtrCalculator(), inputs, params or ATR_PARAMS, initial=initial)


def run_ext(inputs, window, initial=None):
    return transition.run(features.RollingExtreme(), inputs, {"window": window}, initial=initial)


def features_only(events):
    return [e for e in events if e.get("event_kind") == "FEATURE"]


# --- F02 golden vector + formula -----------------------------------------------------------------


def test_gv004_fourteen_trs_of_eight_yield_atr_exactly_eight():
    result = run_atr([flat_tr8(i) for i in range(15)])
    assert len(result.events) == 15
    last = result.events[-1]
    assert last["event_kind"] == "FEATURE"
    assert last["formula"] == "F02"
    assert last["atr_ticks"] == 8
    assert last["evaluation_origin_bar_index"] == 15
    assert last["dependency_range"] == {
        "first_tr_bar_index": 1,
        "last_tr_bar_index": 14,
        "prior_close_bar_index": 0,
    }


def test_gv004_thirteen_trs_are_a_named_warmup_abstention():
    result = run_atr([flat_tr8(i) for i in range(14)])
    last = result.events[-1]
    assert last["event_kind"] == "NAMED_ABSTENTION"
    assert last["reason_code"] == "F02_ATR_WARMUP"
    assert last["refs"] == {"bar_index": 13, "have_trs": 13, "need_trs": 14}
    assert not features_only(result.events)


def test_tr_gap_term_dominates_when_bar_jumps_beyond_prior_close():
    inputs = [flat_tr8(0), bar(1, 1015, 1020, 1015, 1016)]
    result = run_atr(inputs, {"atr_period": 1})
    assert result.events[-1]["atr_ticks"] == 20  # max(5, |1020-1000|, |1015-1000|)


def test_atr_rounds_up_via_ceil_div():
    inputs = [flat_tr8(0), bar(1, 1000, 1003, 1000, 1000), bar(2, 1000, 1004, 1000, 1000)]
    result = run_atr(inputs, {"atr_period": 2})
    assert result.events[-1]["atr_ticks"] == 4  # ceil((3+4)/2)


def test_gap_bar_poisons_the_window_until_a_full_clean_window_exists():
    params = {"atr_period": 2}
    inputs = [flat_tr8(0), flat_tr8(1), flat_tr8(2), flat_tr8(4), flat_tr8(5), flat_tr8(6)]
    result = run_atr(inputs, params)
    kinds = [e["event_kind"] for e in result.events]
    assert kinds == [
        "NAMED_ABSTENTION",  # bar 0: no prior close
        "NAMED_ABSTENTION",  # bar 1: 1 of 2 TRs
        "FEATURE",           # bar 2: 2 of 2 TRs
        "NAMED_ABSTENTION",  # bar 4: gap reseeds prior close
        "NAMED_ABSTENTION",  # bar 5: 1 of 2 TRs after the gap
        "FEATURE",           # bar 6: clean window restored
    ]
    assert result.events[3]["reason_code"] == "F02_ATR_WARMUP"


def test_out_of_order_bar_is_rejected_without_touching_the_window():
    params = {"atr_period": 2}
    inputs = [flat_tr8(0), flat_tr8(1), flat_tr8(2), flat_tr8(1, "stale"), flat_tr8(3)]
    result = run_atr(inputs, params)
    assert result.events[3]["reason_code"] == E01_BAR_OUT_OF_ORDER
    assert result.events[4]["event_kind"] == "FEATURE"


def test_same_index_different_bytes_is_a_revision_conflict_and_poisons():
    params = {"atr_period": 1}
    inputs = [flat_tr8(0), flat_tr8(1), bar(1, 1000, 1009, 1000, 1000, "rev"), flat_tr8(2)]
    result = run_atr(inputs, params)
    assert result.events[2]["reason_code"] == E01_BAR_REVISION_CONFLICT
    assert result.events[3]["event_kind"] == "NAMED_ABSTENTION"  # window restarted at bar 2


def test_rejected_input_emits_its_quarantine_rejection():
    forming = flat_tr8(0)
    forming["payload"] = dict(forming["payload"], bar_finalization_state="FORMING")
    result = run_atr([forming])
    assert result.events[0]["event_kind"] == "QUARANTINE"
    assert result.events[0]["reason_code"] == "E01_BAR_NOT_FINALIZED"


# --- F05 rolling extreme -------------------------------------------------------------------------


def _ext_bars():
    return [
        bar(0, 5, 10, 1, 5),
        bar(1, 5, 12, 3, 5),
        bar(2, 5, 11, 2, 5),
        bar(3, 50, 100, 0, 50),
        bar(4, 4, 5, 4, 4),
    ]


def test_f05_current_bar_is_excluded_from_its_own_extreme():
    result = run_ext(_ext_bars(), 3)
    feats = features_only(result.events)
    assert feats[0]["bar_index"] == 3
    assert feats[0]["upper_ticks"] == 12 and feats[0]["lower_ticks"] == 1  # bar 3's 100/0 excluded
    assert feats[0]["dependency_range"] == {"first_bar_index": 0, "last_bar_index": 2}
    assert feats[1]["bar_index"] == 4
    assert feats[1]["upper_ticks"] == 100 and feats[1]["lower_ticks"] == 0


def test_f05_warmup_boundary_is_exactly_n_prior_bars():
    result = run_ext(_ext_bars()[:3], 3)
    assert [e["event_kind"] for e in result.events] == ["NAMED_ABSTENTION"] * 3
    assert result.events[-1]["reason_code"] == "F05_WARMUP"
    assert result.events[-1]["refs"] == {"bar_index": 2, "have_bars": 2, "need_bars": 3}


def test_f05_gap_resets_the_window():
    inputs = _ext_bars()[:4] + [bar(6, 5, 9, 4, 5), bar(7, 5, 8, 3, 5), bar(8, 5, 7, 5, 5)]
    result = run_ext(inputs, 2)
    feats = features_only(result.events)
    assert [f["bar_index"] for f in feats] == [2, 3, 8]
    assert feats[-1]["upper_ticks"] == 9 and feats[-1]["lower_ticks"] == 3


# --- mirror law ----------------------------------------------------------------------------------


def test_f05_upper_lower_mirror_is_exact():
    inputs = _ext_bars()
    forward = features_only(run_ext(inputs, 3).events)
    mirrored = features_only(run_ext([reflect(e) for e in inputs], 3).events)
    assert len(forward) == len(mirrored) == 2
    for f, m in zip(forward, mirrored):
        assert m["upper_ticks"] == -f["lower_ticks"]
        assert m["lower_ticks"] == -f["upper_ticks"]
        assert m["bar_index"] == f["bar_index"]


def test_f02_atr_is_side_neutral_under_reflection():
    inputs = [flat_tr8(0), bar(1, 1015, 1020, 1015, 1016), bar(2, 1010, 1016, 1008, 1009)]
    forward = run_atr(inputs, {"atr_period": 2}).events
    mirrored = run_atr([reflect(e) for e in inputs], {"atr_period": 2}).events
    assert [e.get("atr_ticks") for e in forward] == [e.get("atr_ticks") for e in mirrored]


# --- prefix / restart / duplicate invariance -----------------------------------------------------


def test_prefix_invariance_events_are_a_prefix_of_the_full_run():
    inputs = [flat_tr8(i) for i in range(16)]
    full = run_atr(inputs)
    for cut in (1, 7, 15):
        assert run_atr(inputs[:cut]).events == full.events[:cut]


def test_restart_from_mid_stream_state_yields_the_same_tail():
    inputs = [flat_tr8(i) for i in range(16)]
    full = run_atr(inputs)
    head = run_atr(inputs[:9])
    tail = run_atr(inputs[9:], initial=head.final_state)
    assert head.events + tail.events == full.events
    assert tail.events[-1] == full.events[-1]
    ext_full = run_ext(_ext_bars(), 3)
    ext_head = run_ext(_ext_bars()[:2], 3)
    ext_tail = run_ext(_ext_bars()[2:], 3, initial=ext_head.final_state)
    assert ext_head.events + ext_tail.events == ext_full.events


def test_exact_duplicate_envelope_is_deduped_by_the_driver():
    inputs = [flat_tr8(0), flat_tr8(1), flat_tr8(1), flat_tr8(2)]
    result = run_atr(inputs, {"atr_period": 1})
    assert result.duplicate_count == 1
    assert result.events == run_atr([flat_tr8(0), flat_tr8(1), flat_tr8(2)],
                                    {"atr_period": 1}).events


def test_semantic_duplicate_with_a_fresh_event_id_is_a_machine_no_op():
    dup = flat_tr8(1, event_id="retransmit_other_id")
    inputs = [flat_tr8(0), flat_tr8(1), dup, flat_tr8(2)]
    result = run_atr(inputs, {"atr_period": 1})
    assert result.duplicate_count == 0
    assert len(result.events) == 3
    ext = run_ext(inputs, 1)
    assert len(ext.events) == 3


# --- fail-closed parameters ----------------------------------------------------------------------


def test_missing_semantic_parameter_fails_closed():
    machine = features.AtrCalculator()
    with pytest.raises(transition.MissingParameterError):
        machine.transition(machine.initial_state(), flat_tr8(0), {}, {})
    ext = features.RollingExtreme()
    with pytest.raises(transition.MissingParameterError):
        ext.transition(ext.initial_state(), flat_tr8(0), {}, {})


def test_non_int_or_non_positive_parameter_is_refused():
    machine = features.AtrCalculator()
    for bad in (True, 0, -3):
        with pytest.raises(StructureLawError):
            machine.transition(machine.initial_state(), flat_tr8(0), {"atr_period": bad}, {})
    ext = features.RollingExtreme()
    with pytest.raises(StructureLawError):
        ext.transition(ext.initial_state(), flat_tr8(0), {"window": 0}, {})


# --- feature snapshot payload --------------------------------------------------------------------


def _snapshot_kwargs(**overrides):
    kwargs = dict(
        feature_set="origin.features.f02",
        feature_version=features.F02_FEATURE_VERSION,
        partition_key={"canonical_instrument_id": "BTCUSDT.PERP", "timeframe": "1m"},
        as_of_state_revision_id="rev_14",
        feature_values={"atr_ticks": 8},
        dependency_ranges={"atr_ticks": {
            "first_tr_bar_index": 1, "last_tr_bar_index": 14, "prior_close_bar_index": 0}},
        formula_text="TR_i=max(H_i-L_i,abs(H_i-C_{i-1}),abs(L_i-C_{i-1}));"
                     "ATR_N(x)=ceil_div(sum(TR_{x-N}..TR_{x-1}),N)",
        params={"atr_period": 14},
        warmup_status="COMPLETE",
        source_time_us=1_000,
        knowledge_time_us=1_500,
        evaluation_time_us=1_500,
        publication_time_us=2_000,
    )
    kwargs.update(overrides)
    return kwargs


def test_feature_snapshot_payload_validates_against_the_contract():
    payload = features.build_feature_snapshot_payload(**_snapshot_kwargs())
    contracts.validate_payload("triad.feature_snapshot.v2", payload)
    assert payload["warmup_status"] == "COMPLETE"
    assert len(payload["output_hash"]) == 64


def test_feature_snapshot_warming_is_honest_both_directions():
    warming = features.build_feature_snapshot_payload(**_snapshot_kwargs(
        feature_values={"atr_ticks": None}, warmup_status="WARMING"))
    contracts.validate_payload("triad.feature_snapshot.v2", warming)
    with pytest.raises(StructureLawError):
        features.build_feature_snapshot_payload(**_snapshot_kwargs(
            feature_values={"atr_ticks": None}, warmup_status="COMPLETE"))
    with pytest.raises(StructureLawError):
        features.build_feature_snapshot_payload(**_snapshot_kwargs(warmup_status="WARMING"))


def test_feature_snapshot_refuses_acausal_time_order_and_unknown_status():
    with pytest.raises(StructureLawError):
        features.build_feature_snapshot_payload(**_snapshot_kwargs(publication_time_us=0))
    with pytest.raises(StructureLawError):
        features.build_feature_snapshot_payload(**_snapshot_kwargs(warmup_status="DONE"))


# --- GV-F05-01 — the missing direct F05 golden (Formula Repair spec §D.5, milestone B03C) --------
def test_gv_f05_01_direct_golden_upper_and_lower():
    """N=3, highs [10,12,11] over bars t-3..t-1 → upper_t = 12; lows [9,9,10] → lower_t = 9.

    Equal lows (9 at t-3 and t-2): the extreme VALUE is the value — 9 — per the tie law (identity
    carries the earliest source; the emitted feature is the value, unchanged by the tie). The
    current bar t is excluded by construction: its high 15 must not change upper_t.
    """
    inputs = [
        bar(0, 9, 10, 9, 10),    # t-3: high 10, low 9
        bar(1, 10, 12, 9, 11),   # t-2: high 12, low 9  (equal low with t-3)
        bar(2, 11, 11, 10, 10),  # t-1: high 11, low 10
        bar(3, 12, 15, 12, 14),  # t: high 15 — MUST NOT enter upper_t
    ]
    result = run_ext(inputs, window=3)
    final = result.events[-1]
    assert final["event_kind"] == "FEATURE"
    assert final["formula"] == "F05"
    assert final["bar_index"] == 3
    assert final["upper_ticks"] == 12   # not 15 — current bar excluded
    assert final["lower_ticks"] == 9    # the tied extreme value
    assert final["dependency_range"] == {"first_bar_index": 0, "last_bar_index": 2}


def test_gv_f05_01_warmup_two_prior_bars_is_null():
    """With only 2 prior bars the feature is NULL (a named warm-up abstention, never a value)."""
    inputs = [bar(0, 9, 10, 9, 10), bar(1, 10, 12, 9, 11), bar(2, 11, 11, 10, 10)]
    result = run_ext(inputs, window=3)
    final = result.events[-1]
    assert final["event_kind"] == "NAMED_ABSTENTION"
    assert final["reason_code"] == "F05_WARMUP"


def test_gv_f05_01_gap_in_window_is_null():
    """A gap inside the trailing window voids it: the next emission is NULL, never a blend."""
    inputs = [
        bar(0, 9, 10, 9, 10),
        bar(1, 10, 12, 9, 11),
        bar(2, 11, 11, 10, 10),
        bar(4, 12, 15, 12, 14),  # bar 3 missing — gap
    ]
    result = run_ext(inputs, window=3)
    final = result.events[-1]
    assert final["event_kind"] == "NAMED_ABSTENTION"
    # The gap resets the window, so the abstention reads as a fresh warm-up — a NULL, never a
    # value blended across the gap (the D.5 law is "gap in window → NULL"; the reason code names
    # the post-reset warm-up state).
    assert final["reason_code"] == "F05_WARMUP"
    assert not any(
        e.get("event_kind") == "FEATURE" and e.get("bar_index") == 4 for e in result.events
    )
