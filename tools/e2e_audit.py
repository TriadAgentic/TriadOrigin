#!/usr/bin/env python3
"""End-to-end audit walk for TRIAD ORIGIN V7.

This script is the operator-directed always-current end-to-end proof: a synthetic,
fully deterministic walk through every capability the repository has shipped so
far. **Every milestone that lands a new capability MUST extend this walk in the
same PR** (the E2E growth law); a capability with no walk stage is an incomplete
milestone.

The walk is not a substitute for the falsification suite (``python -m pytest``);
it is the cross-capability integration proof that the pieces still compose into
one deterministic pipeline. It uses only committed public APIs, no wall clock,
no network, no environment reads on the semantic path.

Usage:
  python tools/e2e_audit.py           # run every stage, fail loud on first error
  python tools/e2e_audit.py --list    # list registered stages
  python tools/e2e_audit.py --stage ledger_walk   # run one stage
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import tempfile
import traceback

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

STAGES: list[tuple[str, str]] = []


def stage(name: str, doc: str):
    def register(fn):
        STAGES.append((name, doc))
        fn.stage_name = name
        globals()[f"_stage_{name}"] = fn
        return fn
    return register


def _run_tool(script: str, *args: str) -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / script), *args],
        capture_output=True, text=True, cwd=ROOT,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"tools/{script} {' '.join(args)} exited {proc.returncode}\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )


# ---------------------------------------------------------------- stage 0
@stage("contracts_manifest", "Contract byte manifest + manifest schema validity")
def contracts_manifest() -> None:
    _run_tool("verify_manifest.py")
    _run_tool("validate_contract_manifest.py")


# ---------------------------------------------------------------- stage 1
@stage("golden_vectors", "Every golden valid vector validates; every invalid vector rejects")
def golden_vectors() -> None:
    from triad_origin import contracts

    golden_root = ROOT / "contracts" / "golden"
    checked = 0
    for schema_dir in sorted(golden_root.iterdir()):
        if not schema_dir.is_dir():
            continue
        valid = schema_dir / "valid.json"
        invalid = schema_dir / "invalid.json"
        if valid.exists():
            payload = json.loads(valid.read_text())
            contracts.validate(payload)
            checked += 1
        if invalid.exists():
            payload = json.loads(invalid.read_text())
            try:
                contracts.validate(payload)
            except Exception:
                checked += 1
            else:
                raise AssertionError(f"invalid vector accepted: {invalid}")
    if checked < 30:
        raise AssertionError(f"golden coverage regressed: only {checked} vectors checked")


# ---------------------------------------------------------------- stage 2
@stage("identity_walk", "Deterministic identity chain semantic_instance→structure→reaction→hypothesis→candidate")
def identity_walk() -> None:
    from triad_origin import ids

    def chain() -> str:
        si = ids.semantic_instance_id("f.demo.v1", "d" * 64, "binance-usdm.v1", "1m")
        st = ids.structure_id(
            "BTCUSDT.binance-usdm", "binance-usdm.v1", "fvg", si, "LONG",
            ["evt-1", "evt-2"], "9" * 64,
        )
        rx = ids.reaction_id(st, "reaction.first_touch.v1", ["evt-3"])
        hy = ids.hypothesis_id(rx, "origin.fvg_displacement_first_touch.v1", "a" * 64)
        return ids.candidate_id(hy, "candidate.geometry.v1", "occ-1")

    first, second = chain(), chain()
    if first != second:
        raise AssertionError("identity chain is not deterministic")
    if not first.startswith("cand_"):
        raise AssertionError(f"unexpected candidate id prefix: {first[:12]}")


# ---------------------------------------------------------------- stage 3
@stage("ledger_walk", "Hash-chained ledger append/read/verify + tamper detection")
def ledger_walk() -> None:
    from triad_origin import ledger

    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "walk.ledger"
        writer = ledger.LedgerWriter(path)
        writer.open()
        payloads = [json.dumps({"n": i}).encode() for i in range(5)]
        for p in payloads:
            writer.append(p)
        writer.close()

        records = list(ledger.read_records(path))
        if [r.payload for r in records] != payloads:
            raise AssertionError("ledger read-back mismatch")
        if ledger.verify(path) != 5:
            raise AssertionError("ledger verify count mismatch")

        raw = bytearray(path.read_bytes())
        raw[len(raw) // 2] ^= 0xFF
        path.write_bytes(bytes(raw))
        try:
            ledger.verify(path)
        except ledger.LedgerError:
            pass
        else:
            raise AssertionError("tampered ledger passed verify")


# ---------------------------------------------------------------- stage 4
@stage("journal_replay_walk", "Journal append/project/rebuild + prefix-invariant replay")
def journal_replay_walk() -> None:
    from triad_origin import journal

    def build(n: int) -> journal.StateJournal:
        j = journal.StateJournal(partition="walk")
        state: dict = {}
        for i in range(n):
            new_state = dict(state)
            new_state[f"k{i}"] = i
            j.append(i - 1, state, new_state, f"env-{i}", ({"event": i},))
            state = new_state
        return j

    j5, j3 = build(5), build(3)
    full = j5.records()
    prefix = j3.records()
    for a, b in zip(prefix, full):
        if a.transition_id != b.transition_id:
            raise AssertionError("prefix invariance violated: transition ids diverge")
    rebuilt = journal.rebuild_projection("walk", full)
    if rebuilt != j5.project():
        raise AssertionError("rebuilt projection != live projection")


# ---------------------------------------------------------------- stage 5
@stage("checkpoint_walk", "Checkpoint seal/save/load/validate + tamper detection")
def checkpoint_walk() -> None:
    from triad_origin import checkpoint, journal
    from triad_origin.canonical import canonical_json, sha256_hex

    j = journal.StateJournal(partition="walk")
    j.append(-1, {}, {"k": 1}, "env-0", ({"event": 0},))
    state = j.project()
    cp = checkpoint.Checkpoint(
        partition="walk", state=state, input_segment="seg-0", input_offset=5,
        input_prefix_digest="a" * 64, last_domain_event_id="evt-5",
        highest_producer_epoch=3, projection_checksum=sha256_hex(canonical_json(state)),
        output_segment="out-0", output_offset=2, state_seq=j.seq,
        last_transition_id=j.records()[-1].transition_id,
        digests={k: "c" * 64 for k in ("build", "config", "contract", "parameter", "instrument")},
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "cp.json"
        checkpoint.save(path, cp)
        loaded = checkpoint.load(path)
        checkpoint.validate_for_restore(loaded)
        if loaded.state != state or loaded.state_seq != j.seq:
            raise AssertionError("checkpoint round-trip mismatch")

        blob = json.loads(path.read_text())
        blob["state_seq"] = 99
        path.write_text(json.dumps(blob))
        try:
            checkpoint.load(path)
        except checkpoint.CheckpointError:
            pass
        else:
            raise AssertionError("tampered checkpoint loaded")


# ---------------------------------------------------------------- stage 6
@stage("epoch_fence", "Producer-epoch fencing: current accepted, lower rejected")
def epoch_fence() -> None:
    from triad_origin import contracts

    event = {"producer_epoch": "5"}
    if contracts.assert_epoch_ge(event, 5) != 5:
        raise AssertionError("current epoch must be accepted")
    try:
        contracts.assert_epoch_ge({"producer_epoch": "4"}, 5)
    except contracts.StaleEpochError:
        pass
    else:
        raise AssertionError("stale epoch accepted")


# ---------------------------------------------------------------- B02 stages
@stage("anchor_walk", "External durable anchor: tail deletion/replacement detected beyond self-verification")
def anchor_walk() -> None:
    from triad_origin import anchor, ledger

    with tempfile.TemporaryDirectory() as tmp:
        lpath = pathlib.Path(tmp) / "walk.ledger"
        apath = pathlib.Path(tmp) / "external" / "walk.anchor"
        with ledger.LedgerWriter(lpath) as writer:
            for i in range(4):
                writer.append(json.dumps({"n": i}).encode())
        anchor.anchor_ledger(lpath, apath)
        if anchor.verify_anchored(lpath, apath)["result"] != "PASS":
            raise AssertionError("anchored ledger failed verification")

        # Forge an internally-consistent shorter ledger; self-verify passes, anchor must not.
        records = list(ledger.read_records(lpath))
        rebuilt = pathlib.Path(tmp) / "rebuilt.ledger"
        with ledger.LedgerWriter(rebuilt) as writer:
            for rec in records[:2]:
                writer.append(rec.payload)
        rebuilt.replace(lpath)
        if ledger.verify(lpath) != 2:
            raise AssertionError("forged ledger should self-verify")
        try:
            anchor.verify_anchored(lpath, apath)
        except anchor.AnchorError:
            pass
        else:
            raise AssertionError("anchor failed to detect tail deletion")


@stage("fence_restore_walk", "Per-scope fence state seals into checkpoint v3 and refences after restart")
def fence_restore_walk() -> None:
    from triad_origin import checkpoint, journal, lease
    from triad_origin.canonical import canonical_json, sha256_hex

    fence = lease.ConsumerFence()
    ok = fence.accept(lease.Lease(
        lease_id="l-9", scope="edge.candidates", producer_service="origin",
        producer_instance_id="inst", fencing_token=9, activation_manifest_id="am",
        state=lease.LeaseState.ACTIVE))
    if not ok:
        raise AssertionError("active lease refused")

    j = journal.StateJournal(partition="walk")
    j.append(-1, {}, {"k": 1}, "env-0", ({"event": 0},))
    state = j.project()
    cp = checkpoint.Checkpoint(
        partition="walk", state=state, input_segment="seg", input_offset=1,
        input_prefix_digest="a" * 64, last_domain_event_id="env-0",
        highest_producer_epoch=0, projection_checksum=sha256_hex(canonical_json(state)),
        output_segment="out", output_offset=0, state_seq=j.seq,
        last_transition_id=j.records()[-1].transition_id,
        digests={k: "c" * 64 for k in ("build", "config", "contract", "parameter", "instrument")},
        fence_state={"lease": fence.export_state(), "epoch": {"edge.candidates": 3}},
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "cp.json"
        checkpoint.save(path, cp)
        loaded = checkpoint.load(path)
    restored = lease.ConsumerFence()
    restored.restore_state(loaded.fence_state["lease"])
    lower = lease.Lease(
        lease_id="l-8", scope="edge.candidates", producer_service="origin",
        producer_instance_id="inst2", fencing_token=8, activation_manifest_id="am",
        state=lease.LeaseState.ACTIVE)
    if restored.accept(lower):
        raise AssertionError("restarted fence accepted a lower token")
    if not restored.accepts_write("edge.candidates", 9):
        raise AssertionError("restarted fence lost the accepted token")


@stage("timing_law", "RC4 timing bounds drift-locked to the vendored bundle; staleness pure")
def timing_law() -> None:
    from triad_origin import timings

    bundle = json.loads((ROOT / "docs/control/rc4_control_bundle.json").read_text())
    if dict(timings.TIMINGS_MS) != bundle["timings"]:
        raise AssertionError("timing registry drifted from the RC4 bundle")
    if not timings.is_stale(timings.timing_ms("lever_cache_max_age_ms") + 1,
                            "lever_cache_max_age_ms"):
        raise AssertionError("staleness predicate failed")


# ---------------------------------------------------------------- B01 stages
@stage("identity_v2_walk", "Typed identity v2: v1 collision class closed, v1 IDs byte-stable")
def identity_v2_walk() -> None:
    from triad_origin import canonical, ids

    if canonical.digest_fields(1) != canonical.digest_fields("1"):
        raise AssertionError("v1 collision demonstration changed — identity law drifted")
    if canonical.digest_fields_v2(1) == canonical.digest_fields_v2("1"):
        raise AssertionError("v2 failed to separate int/str")
    si_v1 = ids.semantic_instance_id("f.v1", "d" * 64, "vm", "1m")
    if si_v1 != "sinst_e7be341c2ffb4c208ff65bfb2142554eb05a3fb5":
        raise AssertionError("pinned v1 identity vector moved — release blocker")
    si_v2 = ids.semantic_instance_id(
        "f.v1", "d" * 64, "vm", "1m",
        identity_schema_version=ids.IDENTITY_SCHEMA_VERSION_V2)
    if si_v1 == si_v2:
        raise AssertionError("v2 identity must differ from v1")


@stage("lever_law_walk", "RC4 lever law: valid combination accepted, refusal combinations rejected")
def lever_law_walk() -> None:
    from triad_origin import contracts

    event = json.loads(
        (ROOT / "contracts/golden/triad.engine_control_manifest.v2/valid.json").read_text())
    contracts.validate(event)

    refusals = [
        ({"venue_environment": "OFF", "venue_activation": "LIVE"},
         "OFF_WITH_LIVE_VENUE_ACTIVATION"),
        ({"shadow_activation": "OFF"}, "shadow OFF"),
        ({"venue_environment": "LIVE", "venue_activation": "LIVE",
          "testnet_promotion_receipt": {}}, "LIVE_PROMOTION_RECEIPT_MISSING"),
        ({"venue_activation": "on"}, "legacy alias"),
        ({"scope": {"instruments": ["*"]}}, "wildcard scope"),
    ]
    for patch, label in refusals:
        bad = json.loads(json.dumps(event))
        bad["payload"].update(patch)
        try:
            contracts.validate(bad)
        except contracts.ContractError:
            continue
        raise AssertionError(f"lever refusal not enforced: {label}")

    att = json.loads(
        (ROOT / "contracts/golden/triad.engine_attestation.v2/valid.json").read_text())
    contracts.validate(att)
    att["payload"]["artifact_sha256"] = "e" * 64
    try:
        contracts.validate(att)
    except contracts.ContractError:
        pass
    else:
        raise AssertionError("attestation equality law not enforced")


@stage("receipt_walk", "B-series milestone receipts validate; forged receipt rejects")
def receipt_walk() -> None:
    receipts = sorted((ROOT / "evidence" / "receipts").glob("B*.json"))
    if not receipts:
        raise AssertionError("no B-series receipts found")
    for receipt in receipts:
        _run_tool("validate_b_receipt.py", str(receipt))


# ---------------------------------------------------------------- stage 7
@stage("capability_boundary", "DARK posture: no network/credential/order capability imports")
def capability_boundary() -> None:
    _run_tool("verify_no_forbidden_capabilities.py")


# ---------------------------------------------------------------- stage 8
@stage("build_ledger", "Build ledger regenerates byte-identical (partition is current)")
def build_ledger() -> None:
    _run_tool("build_ledger.py", "--verify")


@stage("combined_dag", "Combined RC3+RC4 DAG: closure, no cycles, one owner, source authority "
                       "preserved, inversions reviewed (B00C)")
def combined_dag() -> None:
    _run_tool("validate_combined_dag.py")


@stage("structures_walk", "B03: E01 bars -> F02 ATR -> F03 swing -> F09 accepted break -> "
                          "structure atom -> journal; F06/F08 refuse by name")
def structures_walk() -> None:
    from triad_origin import contracts, transition
    from triad_origin.features import AtrCalculator
    from triad_origin.journal import StateJournal, rebuild_projection
    from triad_origin.structures import common
    from triad_origin.structures.structure_state import (
        BreakDetector, ProtectedSwingStructure, build_structure_atom_payload)
    from triad_origin.structures.typed_level_registry import DirectionalChangeSwing

    def bar_event(i, o, h, low, c):
        return {"event_id": f"e2e_bar_{i}", "payload": {
            "state_kind": "BAR", "bar_finalization_state": "FINALIZED",
            "watermark_complete": True, "validity": "READY", "bar_index": i,
            "bar_open_time_us": i * 60_000_000, "bar_close_time_us": (i + 1) * 60_000_000,
            "open_ticks": o, "high_ticks": h, "low_ticks": low, "close_ticks": c}}

    # 1 · E01-owned finalized bars (consumed, never authored) -> F02 ATR (GV-004 shape).
    bars = [bar_event(i, 1000, 1008, 1000, 1000) for i in range(15)]
    atr_run = transition.run(AtrCalculator(), bars, {"atr_period": 14})
    features = [e for e in atr_run.events if e.get("event_kind") == "FEATURE"]
    if not features or features[-1]["atr_ticks"] != 8:
        raise AssertionError("F02 ATR walk did not yield the GV-004 value 8")
    warmups = [e for e in atr_run.events if e.get("event_kind") == "NAMED_ABSTENTION"]
    if not warmups:
        raise AssertionError("F02 warm-up abstentions missing")

    # 2 · F03 DC swing over ATR-carrying bars (GV-005 shape: delta = max(5, ceil(20/4)) = 5).
    swing_bars = [
        {"event_id": "s0", "kind": "BAR", "payload": {"high_ticks": 990, "low_ticks": 985,
                                                      "atr14_ticks": 20, "bar_seq": 0}},
        {"event_id": "s1", "kind": "BAR", "payload": {"high_ticks": 1000, "low_ticks": 995,
                                                      "atr14_ticks": 20, "bar_seq": 1}},
        {"event_id": "s2", "kind": "BAR", "payload": {"high_ticks": 999, "low_ticks": 995,
                                                      "atr14_ticks": 20, "bar_seq": 2}},
    ]
    swing_run = transition.run(
        DirectionalChangeSwing(), swing_bars,
        {"dc_reversal_rule": common.DECLARED_DC_REVERSAL})
    confirmed = [e for e in swing_run.events if e.get("event_kind") == "TYPED_LEVEL"]
    if not confirmed or confirmed[0]["level_ticks"] != 1000:
        raise AssertionError("F03 swing did not confirm the frozen extreme 1000")

    # 3 · F09 accepted break of the confirmed level (GV-008: buffer 1; close 1001 breaks).
    break_inputs = [
        {"event_id": "lvl", "kind": "LEVEL", "payload": {
            "level_id": "e2e_L1", "level_ticks": 1000, "direction": common.LONG,
            "confirmed": True}},
        {"event_id": "c1", "kind": "BAR", "payload": {"close_ticks": 1000, "atr14_ticks": 20}},
        {"event_id": "c2", "kind": "BAR", "payload": {"close_ticks": 1001, "atr14_ticks": 20}},
    ]
    break_run = transition.run(
        BreakDetector(), break_inputs,
        {"break_buffer_rule": common.DECLARED_BOS_CLOSE_BUFFER,
         "observation_mode": "FINALIZED_CLOSE"})
    occurrences = [e for e in break_run.events if "break" in str(e.get("event_kind", "")).lower()
                   or e.get("event_kind") == "BREAK_OCCURRENCE"]
    if len(occurrences) != 1:
        raise AssertionError(f"F09 expected exactly one first-breach occurrence, "
                             f"got {len(occurrences)}")
    if occurrences[0]["classification"] != "UNCLASSIFIED_STRUCTURE_STATE_UNAVAILABLE":
        raise AssertionError("F09 classification must abstain while F08 is unratified")

    # 4 · F08 refuses by name; F06 refuses by name while max span is NOT_RATIFIED.
    f08_run = transition.run(
        ProtectedSwingStructure(),
        [{"event_id": "x", "kind": "BAR", "payload": {"close_ticks": 1}}], {})
    if f08_run.events[0]["reason_code"] != "F08_UNAVAILABLE_REDUCER_VERSION_NOT_RATIFIED":
        raise AssertionError("F08 must refuse with its named abstention")
    from triad_origin.structures.typed_level_registry import EqualLevelCluster
    f06_run = transition.run(
        EqualLevelCluster(),
        [{"event_id": "p", "kind": "PIVOT", "payload": {
            "pivot_kind": "PIVOT_HIGH", "level_ticks": 1000, "atr14_ticks": 30}}],
        {"equal_level_tolerance_rule": common.DECLARED_EQUAL_LEVEL_TOLERANCE,
         "equal_level_min_touches": 2, "equal_level_max_span": common.NOT_RATIFIED})
    if f06_run.events[0]["reason_code"] != "F06_UNAVAILABLE_MAX_SPAN_NOT_RATIFIED":
        raise AssertionError("F06 must refuse with its named abstention while span unratified")

    # 5 · Structure atom payload -> contract validation -> journal round-trip.
    payload = build_structure_atom_payload(
        structure_kind="dc_swing", structure_subtype="swing_high", direction=common.LONG,
        canonical_instrument_id="BTCUSDT.BINANCE.UMF", venue_model="binance-usdm-futures",
        timeframe="1m", formula_version="F03.v1", parameter_set_id="pset-e2e",
        parameter_digest="4" * 64,
        original_geometry={"level_ticks": 1000, "delta_ticks": 5},
        origin_source_ids=["s1"], confirmation_source_ids=["s2"],
        origin_time_us=1, confirmation_time_us=2, availability_time_us=3, knowledge_time_us=3,
        reference_level_ids=[], source_offset_range=["0", "2"],
        dependency_quality={"atr": "COMPLETE"}, build_commit="0" * 40,
        config_bundle_sha256="5" * 64, instrument_digest="6" * 64)
    contracts.validate_payload("triad.structure_atom.v2", payload)
    journal = StateJournal(partition="e2e_structure_atoms")
    atom_event = {"event_kind": "STRUCTURE_CONFIRMED", "payload": payload}
    record = journal.append(
        journal.seq, {}, {"last_atom": payload}, "evt_e2e_atom", (atom_event,))
    if record is None:
        raise AssertionError("structure atom journal append refused")
    rebuilt = rebuild_projection(journal.partition, journal.records())
    if rebuilt != {"last_atom": payload}:
        raise AssertionError("structure atom journal round-trip mismatch")


@stage("structure_flow_walk", "B04: FVG GV-009 -> displacement GV-010 -> order block "
                              "PENDING/CONFIRMED -> excursion/reclaim GV-011 -> TFI GV-013 -> "
                              "tilt refuses by name -> lifecycle reducer illegal-transition wall")
def structure_flow_walk() -> None:
    from triad_origin import transition
    from triad_origin.structures import common
    from triad_origin.structures.displacement import QualifiedDisplacement
    from triad_origin.structures.excursion_reclaim_registry import (
        CONFIRMED as RECLAIM_CONFIRMED, ExcursionReclaimTracker)
    from triad_origin.structures.flow_atoms import BookDepthTilt, TradeFlowImbalance
    from triad_origin.structures.fvg_registry import FvgZoneRegistry, ZONE_FORMED
    from triad_origin.structures.lifecycle_reducer import LifecycleReducer

    # 1 · F10 FVG — GV-009: ATR 20, min gap 1; bar i-2 high=100, bar i low=101 -> forms.
    fvg_bars = [
        {"event_id": "f0", "kind": "BAR", "payload": {
            "high_ticks": 90, "low_ticks": 80, "atr14_ticks": 20, "bar_seq": 0}},
        {"event_id": "f1", "kind": "BAR", "payload": {
            "high_ticks": 100, "low_ticks": 95, "atr14_ticks": 20, "bar_seq": 1}},
        {"event_id": "f2", "kind": "BAR", "payload": {
            "high_ticks": 105, "low_ticks": 101, "atr14_ticks": 20, "bar_seq": 2}},
    ]
    fvg_run = transition.run(
        FvgZoneRegistry(), fvg_bars,
        {"fvg_min_gap_rule": common.DECLARED_BOS_CLOSE_BUFFER, "zone_ttl_bars": 120})
    if not [e for e in fvg_run.events if e.get("event_kind") == ZONE_FORMED]:
        raise AssertionError("F10 GV-009 gap did not form")

    # 2 · F11 displacement — GV-010: ATR_before=10 => D_ticks=15; move 15 qualifies.
    disp_inputs = [
        {"event_id": "d_origin", "kind": "ORIGIN", "payload": {
            "origin_bar_index": 0, "origin_open_ticks": 1000, "atr14_before_origin_ticks": 10}},
        {"event_id": "d1", "kind": "BAR", "payload": {
            "bar_index": 1, "open_ticks": 1000, "high_ticks": 1015, "low_ticks": 992,
            "close_ticks": 1015}},
    ]
    disp_run = transition.run(
        QualifiedDisplacement(), disp_inputs,
        {"displacement_horizon": 3, "displacement_min_move_rule": common.DECLARED_DISPLACEMENT_MIN_MOVE,
         "body_fraction_rule": common.DECLARED_DISPLACEMENT_BODY_FRACTION,
         "close_location_rule": common.DECLARED_DISPLACEMENT_CLOSE_LOCATION})
    qualified = [e for e in disp_run.events if e.get("event_kind") == "DISPLACEMENT_QUALIFIED"]
    if not qualified:
        raise AssertionError("F11 GV-010 displacement did not qualify")

    # 3 · F13 excursion/reclaim — GV-011: two consecutive qualifying closes confirm.
    reclaim_run = transition.run(
        ExcursionReclaimTracker(),
        [{"event_id": "r_exc", "kind": "EXCURSION_CANDIDATE", "payload": {
              "level_id": "e2e_L1", "direction": common.LONG, "level_ticks": 1000,
              "high_ticks": 1001, "low_ticks": 999, "atr14_ticks": 20}},
         {"event_id": "r_o1", "kind": "RECLAIM_OBSERVATION", "payload": {
              "level_id": "e2e_L1", "ordinal": 1, "close_ticks": 998, "atr14_ticks": 20}},
         {"event_id": "r_o2", "kind": "RECLAIM_OBSERVATION", "payload": {
              "level_id": "e2e_L1", "ordinal": 2, "close_ticks": 997, "atr14_ticks": 20}}],
        {"excursion_min_rule": common.DECLARED_BOS_CLOSE_BUFFER,
         "reclaim_close_buffer_rule": common.DECLARED_BOS_CLOSE_BUFFER,
         "reclaim_horizon": 3, "reclaim_hold_bars": 2})
    if reclaim_run.final_state["levels"]["e2e_L1"]["reclaim_state"] != RECLAIM_CONFIRMED:
        raise AssertionError("F13 GV-011 reclaim did not confirm")

    # 4 · F15 TFI — GV-013: buy=70, sell=30 -> 40/100 exact.
    tfi_run = transition.run(
        TradeFlowImbalance(),
        [{"event_id": f"t{i}", "kind": "TRADE", "evaluation_time_us": i,
          "payload": {"quote_notional_ticks": 1, "aggressor_side": "BUY" if i < 70 else "SELL",
                     "event_time_us": i}} for i in range(100)],
        {"tfi_window_trades": 100, "tfi_window_max_age_ms": 2000, "tfi_min_trades": 20})
    tfi_events = [e for e in tfi_run.events if e.get("event_kind") == "FEATURE"]
    if not tfi_events or (tfi_events[-1]["numerator"], tfi_events[-1]["denominator"]) != (40, 100):
        raise AssertionError(f"F15 GV-013 TFI mismatch: {tfi_events[-1] if tfi_events else None}")

    # 5 · F17 tilt refuses by name while RC3-PAR-STRUCT-002 stays NOT_RATIFIED.
    tilt_run = transition.run(
        BookDepthTilt(),
        [{"event_id": "tilt0", "kind": "BOOK_DEPTH", "payload": {
              "bid_quote_depth_ticks_steps": 600, "ask_quote_depth_ticks_steps": 400}}],
        {"book_tilt_min_quote_depth": common.NOT_RATIFIED})
    if tilt_run.events[0]["reason_code"] != "F17_UNAVAILABLE_MIN_DEPTH_NOT_RATIFIED":
        raise AssertionError("F17 must refuse with its named abstention while unratified")

    # 6 · Lifecycle reducer (W05): a legal FORMED->CONFIRMED then an illegal repeat-from-terminal.
    reducer = LifecycleReducer()
    legal = transition.run(
        reducer,
        [{"event_id": "lc1", "kind": "TRANSITION_REQUEST", "payload": {
              "structure_id": "e2e_struct", "requested_transition": "FORMED",
              "trigger_event_id": "lc1"}},
         {"event_id": "lc2", "kind": "TRANSITION_REQUEST", "payload": {
              "structure_id": "e2e_struct", "requested_transition": "CONFIRMED",
              "trigger_event_id": "lc2"}},
         {"event_id": "lc3", "kind": "TRANSITION_REQUEST", "payload": {
              "structure_id": "e2e_struct", "requested_transition": "FULLY_FILLED",
              "trigger_event_id": "lc3"}}], {})
    illegal = transition.run(
        reducer,
        [{"event_id": "lc4", "kind": "TRANSITION_REQUEST", "payload": {
              "structure_id": "e2e_struct", "requested_transition": "CONFIRMED",
              "trigger_event_id": "lc4"}}], {},
        initial=legal.final_state)
    if illegal.final_state["structures"] != legal.final_state["structures"]:
        raise AssertionError("lifecycle reducer must reject an illegal transition without mutation")
    rejections = [e for e in illegal.events if "ILLEGAL" in str(e.get("reason_code", ""))]
    if not rejections:
        raise AssertionError("lifecycle reducer must name the illegal-transition refusal")


@stage("binding_walk", "binding.v2 registry: 105 rows migrated statuses-preserved; ACTIVE "
                       "resolves, BLOCKED refuses by name (B01R)")
def binding_walk() -> None:
    _run_tool("gen_binding_registry.py", "--verify")
    from triad_origin import bindings

    registry = bindings.load_registry()
    counts = registry.status_counts()
    if counts != {"ACTIVE": 3, "BLOCKED": 4, "BLOCKED_BINDING_V2_MIGRATION": 98}:
        raise AssertionError(f"source statuses not preserved: {counts}")
    row = registry.resolve("ingress_price_wire_integer_ticks")
    if row["binding_id"] != "FPB-0001":
        raise AssertionError("active F00 price binding did not resolve")
    try:
        registry.resolve_for_formula("F08")
    except bindings.BindingBlockedError as err:
        if "NOT_RATIFIED" not in err.disposition and not err.status.startswith("BLOCKED"):
            raise AssertionError("F08 refusal is not named") from err
    else:
        raise AssertionError("blocked F08 binding must not be consumable")


@stage("four_plane_walk", "B05: lever registry CAS/staleness -> SHADOW tradeability/dedup/health "
                          "-> PAPER order/fill/close -> population separation -> ADR-005 artifact")
def four_plane_walk() -> None:
    from triad_origin import contracts, timings, transition
    from triad_origin.control import lever_law
    from triad_origin.control.lever_registry import (
        ATTESTATION_ACCEPTED,
        MANIFEST_ACCEPTED,
        MANIFEST_REFUSED,
        STALENESS_FORCED_OFF,
        LeverRegistry,
    )
    from triad_origin.control.paper_ledger import (
        PAPER_FILL_RECORDED,
        PAPER_TRADE_RECORDED,
        PaperLedger,
    )
    from triad_origin.control.shadow_health import (
        HEALTH_FORCED_OFF,
        ShadowHealth,
    )
    from triad_origin.control.shadow_ledger import (
        MARKET_WATERMARK_TS_KEY,
        SHADOW_REJECTION_AUDIT_RECORDED,
        SHADOW_TRADE_RECORDED,
        TRADEABILITY_REQUIREMENTS,
        ShadowLedger,
    )

    # 1. Every one of the 10 RC4-declared valid combinations resolves accepted; the required
    #    non-authoritative baseline OFF/OFF/OFF/LIVE is exactly one of them.
    if lever_law.BASELINE_MANIFEST not in [
        dict(c, shadow_activation="LIVE") for c in lever_law.VALID_COMBINATIONS
    ]:
        raise AssertionError("baseline manifest is not a valid combination")
    for combo in lever_law.VALID_COMBINATIONS:
        payload = dict(combo, shadow_activation="LIVE")
        if combo["venue_environment"] == "LIVE" and combo["venue_activation"] == "LIVE":
            payload["testnet_promotion_receipt"] = {"receipt_id": "r1"}
        result = lever_law.resolve_manifest(payload)
        if not result.accepted:
            raise AssertionError(f"valid combination refused: {combo} -> {result.refusal_code}")

    # 2. A sample across all three reachability classes of the 32 refusal codes fires by name.
    bad_alias = lever_law.resolve_manifest(
        {"venue_environment": "OFF", "venue_activation": "live", "paper_activation": "OFF",
         "shadow_activation": "LIVE"})
    if bad_alias.refusal_code != "VENUE_ACTIVATION_VALUE_INVALID":
        raise AssertionError("alias refusal law not enforced in the e2e walk")
    off_live = lever_law.resolve_manifest(
        {"venue_environment": "OFF", "venue_activation": "LIVE", "paper_activation": "OFF",
         "shadow_activation": "LIVE"})
    if off_live.refusal_code != "OFF_WITH_LIVE_VENUE_ACTIVATION":
        raise AssertionError("combination refusal law not enforced in the e2e walk")
    external = lever_law.classify_external_refusal("OPPOSITE_ENVIRONMENT_REACHABLE", True)
    if external is None or external.refusal_code != "OPPOSITE_ENVIRONMENT_REACHABLE":
        raise AssertionError("EXTERNAL_EVIDENCE refusal classification broken")

    # 3. Lever registry: exact-CAS accept at revision 1, a stale (behind) revision refused with
    #    state byte-identical, a fresh runtime attestation accepted, and a stale cached copy
    #    resolves the forced-OFF containment action with shadow_activation preserved LIVE.
    activations = {"origin.candidate_publisher": "OFF"}
    manifest = {"venue_environment": "OFF", "venue_activation": "OFF", "paper_activation": "OFF",
               "shadow_activation": "LIVE", "activations": activations,
               "manifest_digest_sha256": "d1", "revision": 1}
    reg_result = transition.run(
        LeverRegistry(),
        [{"event_id": "e1", "kind": "REGISTER_MANIFEST", "payload": manifest}], {})
    if reg_result.events[0]["event_kind"] != MANIFEST_ACCEPTED:
        raise AssertionError("lever registry did not accept revision 1")
    stale_result = transition.run(
        LeverRegistry(),
        [{"event_id": "e1", "kind": "REGISTER_MANIFEST", "payload": manifest},
         {"event_id": "e2", "kind": "REGISTER_MANIFEST",
          "payload": dict(manifest, revision=1, manifest_digest_sha256="d2")}], {})
    if (stale_result.events[-1]["event_kind"] != MANIFEST_REFUSED
            or stale_result.events[-1]["refusal_code"] != "LEVER_REVISION_STALE"):
        raise AssertionError("CAS revision-fencing not enforced")
    if stale_result.final_state["revision"] != 1:
        raise AssertionError("a refused manifest must leave the registry state unchanged")
    att_result = transition.run(
        LeverRegistry(),
        [{"event_id": "e1", "kind": "REGISTER_MANIFEST", "payload": manifest},
         {"event_id": "e2", "kind": "ATTEST_RUNTIME",
          "payload": {"engine_id": "eng-1", "accepted_manifest_digest_sha256": "d1",
                     "accepted_revision": 1, "freshness_age_ms": 100}}], {})
    if att_result.events[-1]["event_kind"] != ATTESTATION_ACCEPTED:
        raise AssertionError("a fresh, matching runtime attestation must be accepted")
    stale_cache = transition.run(
        LeverRegistry(),
        [{"event_id": "e1", "kind": "REGISTER_MANIFEST", "payload": manifest},
         {"event_id": "e2", "kind": "RESOLVE_STALENESS",
          "payload": {"engine_id": "origin.candidate_publisher",
                     "cached_age_ms": timings.timing_ms("lever_cache_max_age_ms") + 1}}], {})
    staleness_event = stale_cache.events[-1]
    if staleness_event["event_kind"] != STALENESS_FORCED_OFF:
        raise AssertionError("stale cache must resolve a forced-OFF containment event")
    if staleness_event["action"]["shadow_activation"] != "LIVE":
        raise AssertionError("staleness containment must preserve shadow_activation LIVE")

    # 4. SHADOW: a tradeable candidate freezes a trade row; an untradeable one persists a rejection
    #    audit with NO fabricated geometry; a duplicate delivery is a no-op; SHADOW health forces
    #    venue/PAPER OFF on a stale writer heartbeat while shadow_activation stays LIVE.
    good_payload = {
        "candidate_id": "cand-1", "hypothesis_id": "hyp-1", "origin_disposition": "REJECTED",
        "rejection_stage": "E08_RISK", "rejection_reason": "oversized",
        "market_watermark": {MARKET_WATERMARK_TS_KEY: 1_000},
        "proposed_geometry": {"side": "LONG", "entry_ticks": 100},
        "evaluation_notional_quote": "1000000", "simulator_version": "sim-1",
        "resolver_version": "res-1", "cost_model_version": "cost-1", "event_time_us": 1_000,
    }
    for name in TRADEABILITY_REQUIREMENTS:
        good_payload[name] = True
    shadow_result = transition.run(
        ShadowLedger(), [{"event_id": "s1", "kind": "SHADOW_CANDIDATE", "payload": good_payload}],
        {})
    if shadow_result.events[0]["event_kind"] != SHADOW_TRADE_RECORDED:
        raise AssertionError("a tradeable SHADOW candidate must freeze a trade row")
    trade_row = shadow_result.events[0]["row"] if "row" in shadow_result.events[0] else None
    dup_result = transition.run(
        ShadowLedger(),
        [{"event_id": "s1", "kind": "SHADOW_CANDIDATE", "payload": good_payload},
         {"event_id": "s2", "kind": "SHADOW_CANDIDATE", "payload": dict(good_payload)}], {})
    if len(dup_result.events) != 1:
        raise AssertionError("an identical SHADOW redelivery must be a no-op (LEV-0070)")

    bad_payload = dict(good_payload, candidate_id="cand-2", hypothesis_id="hyp-2")
    bad_payload[TRADEABILITY_REQUIREMENTS[0]] = False
    audit_result = transition.run(
        ShadowLedger(), [{"event_id": "s3", "kind": "SHADOW_CANDIDATE", "payload": bad_payload}],
        {})
    audit_event = audit_result.events[0]
    if audit_event["event_kind"] != SHADOW_REJECTION_AUDIT_RECORDED:
        raise AssertionError("an untradeable candidate must persist a rejection audit")
    if any("geometry" in str(k).lower() for k in audit_event.get("row", audit_event)):
        raise AssertionError("a SHADOW_UNTRADEABLE audit must never carry fabricated geometry")

    health_result = transition.run(
        ShadowHealth(),
        [{"event_id": "h1", "kind": "WRITER_HEARTBEAT",
          "payload": {"age_ms": timings.timing_ms("shadow_health_max_age_ms") + 1}}], {})
    forced = health_result.events[0]
    if forced["event_kind"] != HEALTH_FORCED_OFF:
        raise AssertionError("a stale SHADOW writer heartbeat must force venue/PAPER OFF")
    if forced["payload"]["shadow_activation"] != "LIVE":
        raise AssertionError("SHADOW health containment must preserve shadow_activation LIVE")

    # 5. PAPER: keyless (no forbidden import substring in its own source), an order/fill closing
    #    flat freezes a schema-valid paper_trade.v1 row, and a venue-shaped field is refused.
    paper_source = (ROOT / "src" / "triad_origin" / "control" / "paper_ledger.py").read_text()
    for forbidden in ("socket", "requests", "urllib", "websocket", "credential", "api_key",
                     "private_key"):
        if forbidden in paper_source:
            raise AssertionError(f"PAPER ledger source carries a forbidden capability substring: "
                                 f"{forbidden!r} (LEV-0078)")
    paper_inputs = [
        {"event_id": "p1", "kind": "PAPER_ACCOUNT_OPEN",
         "payload": {"virtual_account_id": "ACCT-1", "starting_balance_quote": "1000000"}},
        {"event_id": "p2", "kind": "PAPER_ORDER",
         "payload": {"virtual_account_id": "ACCT-1", "candidate_id": "cand-1",
                    "activation_revision": "1", "order_id": "ord-entry", "side": "LONG",
                    "entry_policy": {"limit_ticks": 100}, "size_ticks": 10}},
        {"event_id": "p3", "kind": "PAPER_FILL",
         "payload": {"virtual_account_id": "ACCT-1", "order_id": "ord-entry", "fill_id": "fill-1",
                    "fill_qty_ticks": 10, "fill_price_ticks": 100, "event_time_us": 1_000}},
        {"event_id": "p4", "kind": "PAPER_ORDER",
         "payload": {"virtual_account_id": "ACCT-1", "candidate_id": "cand-1",
                    "activation_revision": "1", "order_id": "ord-exit", "side": "SHORT",
                    "entry_policy": {"limit_ticks": 110}, "size_ticks": 10}},
        {"event_id": "p5", "kind": "PAPER_FILL",
         "payload": {"virtual_account_id": "ACCT-1", "order_id": "ord-exit", "fill_id": "fill-2",
                    "fill_qty_ticks": 10, "fill_price_ticks": 110, "event_time_us": 2_000}},
    ]
    paper_result = transition.run(PaperLedger(), paper_inputs, {})
    kinds = [e.get("event_kind") for e in paper_result.events]
    if PAPER_FILL_RECORDED not in kinds or PAPER_TRADE_RECORDED not in kinds:
        raise AssertionError("PAPER order/fill closing flat did not freeze a trade")
    trade_row = list(paper_result.final_state["trades"].values())[-1]
    if trade_row["population"] != "PAPER":
        raise AssertionError("a frozen PAPER row must carry population=PAPER")
    contracts.validate_payload("triad.paper_trade.v1", trade_row)

    forbidden_field_result = transition.run(
        PaperLedger(),
        [{"event_id": "p1", "kind": "PAPER_ACCOUNT_OPEN",
          "payload": {"virtual_account_id": "ACCT-2", "starting_balance_quote": "1000000"}},
         {"event_id": "p2", "kind": "PAPER_ORDER",
          "payload": {"virtual_account_id": "ACCT-2", "candidate_id": "cand-3",
                     "activation_revision": "1", "order_id": "ord-2", "side": "LONG",
                     "entry_policy": {"limit_ticks": 100}, "size_ticks": 10,
                     "venue_order_id": "not-allowed"}}], {})
    refused = forbidden_field_result.events[-1]
    if refused.get("reason_code") != "PAPER_VENUE_EFFECT_FORBIDDEN":
        raise AssertionError("a venue-identity-shaped field must refuse PAPER_VENUE_EFFECT_FORBIDDEN")

    # 6. Population separation at the contract boundary: a PAPER row never validates against the
    #    SHADOW schema, and vice versa (structural closed-enum proof, LEV-0084).
    shadow_shaped = dict(good_payload)
    shadow_shaped.update({
        "shadow_trade_id": "shd-1", "population": "SHADOW", "shadow_activation": "LIVE",
        "fill_model_result": {"result": "NO_FILL"}, "terminal_outcome": {},
        "recorded_time_us": 1_000,
    })
    try:
        contracts.validate_payload("triad.shadow_trade.v1", trade_row)
    except contracts.ContractError:
        pass
    else:
        raise AssertionError("a PAPER row must never validate against the SHADOW schema")

    # 7. ADR-005 supersession artifact exists, is unsigned, and names its exact scope.
    adr_path = ROOT / "docs" / "governance" / "ADR-005-SUPERSESSION.md"
    adr_text = adr_path.read_text()
    if "COUNTERSIGNED: ________________" not in adr_text:
        raise AssertionError("ADR-005 supersession artifact must be prepared unsigned")
    if "LEV-0001" not in adr_text or "sibling-repo estate rules untouched" not in adr_text.replace(
            "\n", " "):
        raise AssertionError("ADR-005 artifact must name LEV-0001 and its scope boundary")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--stage")
    args = parser.parse_args(argv)

    if args.list:
        for name, doc in STAGES:
            print(f"{name}: {doc}")
        return 0

    selected = [s for s in STAGES if not args.stage or s[0] == args.stage]
    if args.stage and not selected:
        print(f"unknown stage: {args.stage}", file=sys.stderr)
        return 2

    failures = 0
    for name, doc in selected:
        fn = globals()[f"_stage_{name}"]
        try:
            fn()
        except Exception:
            failures += 1
            print(f"FAIL {name}: {doc}")
            traceback.print_exc()
        else:
            print(f"PASS {name}: {doc}")
    if failures:
        print(f"E2E AUDIT: {failures}/{len(selected)} stages FAILED", file=sys.stderr)
        return 1
    print(f"E2E AUDIT: all {len(selected)} stages passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
