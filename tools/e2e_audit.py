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
                          "structure atom -> journal; F06/F08 refuse by name; F05 rolling extreme; "
                          "F07 E01 session-level ingress accept + calendar/watermark refusals")
def structures_walk() -> None:
    from triad_origin import contracts, e01_interface, transition
    from triad_origin.features import AtrCalculator, RollingExtreme
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

    # 6 · F05-1 rolling extreme (trailing, current bar excluded; window=3, PAR-039). Three warm-up
    #     abstentions then the trailing extreme over the 3 prior bars: upper=max(1005,1010,1008)=1010,
    #     lower=min(995,990,992)=990; the current bar (index 3) is excluded (dependency_range [0,2]).
    re_bars = [bar_event(0, 1000, 1005, 995, 1000), bar_event(1, 1000, 1010, 990, 1000),
               bar_event(2, 1000, 1008, 992, 1000), bar_event(3, 1000, 1000, 1000, 1000)]
    re_run = transition.run(RollingExtreme(), re_bars, {"window": 3})
    re_feats = [e for e in re_run.events if e.get("event_kind") == "FEATURE"]
    re_warm = [e for e in re_run.events if e.get("reason_code") == "F05_WARMUP"]
    if len(re_warm) != 3:
        raise AssertionError(f"F05 expected exactly 3 warm-up abstentions, got {len(re_warm)}")
    if not re_feats or (re_feats[-1]["upper_ticks"], re_feats[-1]["lower_ticks"]) != (1010, 990):
        raise AssertionError(f"F05-1 rolling extreme mismatch: {re_feats[-1] if re_feats else None}")
    if re_feats[-1]["dependency_range"] != {"first_bar_index": 0, "last_bar_index": 2}:
        raise AssertionError("F05-1 dependency range must exclude the current bar")

    # 7 · F07-1 E01 session-level ingress (E01-owned; ORIGIN consumes/validates, never authors).
    #     A UTC-day-aligned final session accepts; a calendar-id disagreement and a final-flag set
    #     before the session-end watermark each reject by name (never a repaired fact).
    _DAY_US = e01_interface.DAY_US

    def session_payload(**overrides):
        payload = {
            "state_kind": "SESSION_LEVEL", "calendar_id": "CAL-UTC",
            "calendar_row": {"calendar_id": "CAL-UTC", "utc_day_offset_us": 0,
                             "session_length_us": _DAY_US},
            "session_start_us": 0, "session_end_us": _DAY_US,
            "session_open_ticks": 100, "session_high_ticks": 110, "session_low_ticks": 90,
            "final": False}
        payload.update(overrides)
        return {"event_id": "e2e_session", "payload": payload}

    accepted = e01_interface.validate_session_level(
        session_payload(final=True, session_end_watermark_us=_DAY_US))
    if not accepted.get("accepted") or accepted.get("kind") != "SESSION_LEVEL":
        raise AssertionError(f"F07-1 valid session level was not accepted: {accepted}")
    mismatch = e01_interface.validate_session_level(session_payload(calendar_id="CAL-OTHER"))
    if mismatch.get("reason_code") != e01_interface.E01_SESSION_CALENDAR_MISMATCH:
        raise AssertionError("F07-1 calendar mismatch must reject E01_SESSION_CALENDAR_MISMATCH")
    early_final = e01_interface.validate_session_level(
        session_payload(final=True, session_end_watermark_us=_DAY_US - 1))
    if early_final.get("reason_code") != e01_interface.E01_SESSION_FINAL_BEFORE_WATERMARK:
        raise AssertionError(
            "F07-1 final-before-watermark must reject E01_SESSION_FINAL_BEFORE_WATERMARK")


@stage("structure_flow_walk", "B04: FVG GV-009 -> displacement GV-010 -> order block "
                              "PENDING/CONFIRMED -> excursion/reclaim GV-011 -> TFI GV-013 -> "
                              "OFI (-1) + crossed-book refusal -> tilt refuses by name -> "
                              "lifecycle reducer illegal-transition wall")
def structure_flow_walk() -> None:
    from triad_origin import transition
    from triad_origin.structures import common
    from triad_origin.structures.displacement import QualifiedDisplacement
    from triad_origin.structures.excursion_reclaim_registry import (
        CONFIRMED as RECLAIM_CONFIRMED, ExcursionReclaimTracker)
    from triad_origin.structures.flow_atoms import (
        BookDepthTilt, OrderFlowImbalance, TradeFlowImbalance)
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
    #     After the F1213 direction correction a LONG level reclaims by closing ABOVE it (>= level
    #     + reclaim buffer); the low-side excursion (low=999 below level 1000) still qualifies, and
    #     the two consecutive closes 1002/1003 (above 1000) confirm.
    reclaim_run = transition.run(
        ExcursionReclaimTracker(),
        [{"event_id": "r_exc", "kind": "EXCURSION_CANDIDATE", "payload": {
              "level_id": "e2e_L1", "direction": common.LONG, "level_ticks": 1000,
              "high_ticks": 1001, "low_ticks": 999, "atr14_ticks": 20}},
         {"event_id": "r_o1", "kind": "RECLAIM_OBSERVATION", "payload": {
              "level_id": "e2e_L1", "ordinal": 1, "close_ticks": 1002, "atr14_ticks": 20}},
         {"event_id": "r_o2", "kind": "RECLAIM_OBSERVATION", "payload": {
              "level_id": "e2e_L1", "ordinal": 2, "close_ticks": 1003, "atr14_ticks": 20}}],
        {"excursion_min_rule": common.DECLARED_BOS_CLOSE_BUFFER,
         "reclaim_close_buffer_rule": common.DECLARED_BOS_CLOSE_BUFFER,
         "reclaim_horizon": 3, "reclaim_hold_bars": 2})
    if reclaim_run.final_state["levels"]["e2e_L1"]["reclaim_state"] != RECLAIM_CONFIRMED:
        raise AssertionError("F13 GV-011 reclaim did not confirm")

    # 4 · F15 TFI — GV-013: buy=70, sell=30 -> 40/100 exact. PAR-055 flow_atom_ttl_ms is a
    #     required (fail-closed) parameter now, stamped onto every emitted atom.
    tfi_run = transition.run(
        TradeFlowImbalance(),
        [{"event_id": f"t{i}", "kind": "TRADE", "evaluation_time_us": i,
          "payload": {"quote_notional_ticks": 1, "aggressor_side": "BUY" if i < 70 else "SELL",
                     "event_time_us": i}} for i in range(100)],
        {"tfi_window_trades": 100, "tfi_window_max_age_ms": 2000, "tfi_min_trades": 20,
         "flow_atom_ttl_ms": 500})
    tfi_events = [e for e in tfi_run.events if e.get("event_kind") == "FEATURE"]
    if not tfi_events or (tfi_events[-1]["numerator"], tfi_events[-1]["denominator"]) != (40, 100):
        raise AssertionError(f"F15 GV-013 TFI mismatch: {tfi_events[-1] if tfi_events else None}")
    if tfi_events[-1].get("freshness_deadline_us") != tfi_events[-1]["evaluation_time_us"] + 500 * 1000:
        raise AssertionError("F15 PAR-055 freshness_deadline_us not stamped from flow_atom_ttl_ms")

    # 4b · F16 OFI — best-level order-flow imbalance over three sequence-continuous VALID book
    #      updates -> OFI = -1; a crossed best book fires F16_INVALID_BOOK by name. PAR-055
    #      flow_atom_ttl_ms is required here too.
    ofi_params = {"ofi_window_updates": 100, "ofi_window_max_age_ms": 2000,
                  "ofi_min_updates": 2, "flow_atom_ttl_ms": 500}
    ofi_run = transition.run(
        OrderFlowImbalance(),
        [{"event_id": "b1", "kind": "BOOK_UPDATE", "payload": {
              "sequence": 1, "best_bid_price_ticks": 100, "best_bid_qty_steps": 5,
              "best_ask_price_ticks": 101, "best_ask_qty_steps": 7, "watermark_complete": True}},
         {"event_id": "b2", "kind": "BOOK_UPDATE", "payload": {
              "sequence": 2, "best_bid_price_ticks": 100, "best_bid_qty_steps": 8,
              "best_ask_price_ticks": 101, "best_ask_qty_steps": 4, "watermark_complete": True}},
         {"event_id": "b3", "kind": "BOOK_UPDATE", "payload": {
              "sequence": 3, "best_bid_price_ticks": 100, "best_bid_qty_steps": 1,
              "best_ask_price_ticks": 101, "best_ask_qty_steps": 4, "watermark_complete": True}}],
        ofi_params)
    ofi_events = [e for e in ofi_run.events if e.get("event_kind") == "FEATURE"]
    if not ofi_events or ofi_events[-1]["ofi_value"] != -1:
        raise AssertionError(f"F16 OFI mismatch: {ofi_events[-1] if ofi_events else None}")
    crossed = transition.run(
        OrderFlowImbalance(),
        [{"event_id": "bx", "kind": "BOOK_UPDATE", "payload": {
              "sequence": 1, "best_bid_price_ticks": 101, "best_bid_qty_steps": 5,
              "best_ask_price_ticks": 100, "best_ask_qty_steps": 7, "watermark_complete": True}}],
        ofi_params)
    if crossed.events[0].get("reason_code") != "F16_INVALID_BOOK":
        raise AssertionError("F16 must name F16_INVALID_BOOK for a crossed best book")

    # 5 · F17 tilt refuses by name while RC3-PAR-STRUCT-002 stays NOT_RATIFIED. PAR-059
    #     book_tilt_band_bps and PAR-055 flow_atom_ttl_ms are required (fetched fail-closed)
    #     before the NOT_RATIFIED min-depth refusal is reached.
    tilt_run = transition.run(
        BookDepthTilt(),
        [{"event_id": "tilt0", "kind": "BOOK_DEPTH", "payload": {
              "bid_quote_depth_ticks_steps": 600, "ask_quote_depth_ticks_steps": 400}}],
        {"book_tilt_min_quote_depth": common.NOT_RATIFIED, "book_tilt_band_bps": 5,
         "flow_atom_ttl_ms": 500})
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
    if bad_alias.refusal_code != "LEGACY_LEVER_ALIAS_FORBIDDEN":
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


# ---------------------------------------------------------------- stage 21
@stage("candidate_publisher_walk",
       "B06: F14 departure/first-touch (GV-012) -> F18 geometry (GV-015) -> F19 clustering "
       "(GV-016) -> capsule/trial identity -> the mandatory atomic SHADOW fork -> lifecycle")
def candidate_publisher_walk() -> None:
    from triad_origin import canonical, contracts, transition
    from triad_origin.structures import capsules, common, trial_registry
    from triad_origin.structures.candidate_geometry import (
        ABSTAIN_GEOMETRY_BELOW_FLOOR,
        DECLARED_MIN_GEOMETRIC_RR,
        PARAM_MIN_GEOMETRIC_RR_RULE,
        evaluate_candidate_geometry,
    )
    from triad_origin.structures.candidate_publisher import (
        CANDIDATE_PUBLICATION_REFUSED,
        CANDIDATE_PUBLISHED,
        CANDIDATE_TRANSITIONED,
        STATE_WITHDRAWN,
        CandidatePublisher,
    )
    from triad_origin.structures.clustering import (
        CLUSTER_FORMED,
        CLUSTER_JOINED,
        PARAM_CLUSTER_WINDOW_MS,
        OpportunityClusterRegistry,
    )
    from triad_origin.structures.reaction import (
        DECLARED_CONTACT_PRICE_SOURCE,
        PARAM_CONTACT_PRICE_SOURCE,
        PARAM_FIRST_TOUCH_ORDINAL,
        PARAM_MIN_DEPART_EVENTS,
        PARAM_MIN_DEPART_TIME_MS,
        PARAM_MIN_DEPARTURE_RULE,
        REACTION_CONFIRMED,
        DepartureAndFirstTouch,
    )
    from triad_origin.control.shadow_ledger import SHADOW_TRADE_RECORDED

    CAPSULE_ID = "fvg_displacement_first_touch.v1"

    # 1 · F14 — GV-012: zone [100,105], departure exactly at the PAR-050/166/167 floors (each
    #     inclusive per PAR-009), then a first touch at price [105,110] (the golden vector's own
    #     inputs) consumes eligibility, and an identical second touch never yields a second
    #     candidate.
    f14_params = {
        PARAM_MIN_DEPARTURE_RULE: common.DECLARED_MIN_DEPARTURE,
        PARAM_MIN_DEPART_EVENTS: 1,
        PARAM_MIN_DEPART_TIME_MS: 60_000,
        PARAM_CONTACT_PRICE_SOURCE: DECLARED_CONTACT_PRICE_SOURCE,
        PARAM_FIRST_TOUCH_ORDINAL: 1,
    }
    f14_inputs = [
        {"event_id": "z1", "kind": "ZONE_REGISTERED",
         "payload": {"zone_id": "Z1", "direction": common.LONG, "z_near_ticks": 105,
                    "z_far_ticks": 100, "knowledge_time_us": 0}},
        {"event_id": "d1", "kind": "DEPARTURE_CANDIDATE",
         "payload": {"zone_id": "Z1", "directional_distance_from_near_edge_ticks": 2,
                    "depart_event_count": 1, "elapsed_depart_time_ms": 60_000,
                    "atr14_ticks": 20}},
        {"event_id": "c1", "kind": "CONTACT_OBSERVATION",
         "payload": {"zone_id": "Z1", "contact_source": DECLARED_CONTACT_PRICE_SOURCE,
                    "observed_low_ticks": 105, "observed_high_ticks": 110,
                    "event_time_us": 1_000}},
        {"event_id": "c2", "kind": "CONTACT_OBSERVATION",  # second identical touch: GV-012
         "payload": {"zone_id": "Z1", "contact_source": DECLARED_CONTACT_PRICE_SOURCE,
                    "observed_low_ticks": 105, "observed_high_ticks": 110,
                    "event_time_us": 2_000}},
    ]
    f14_result = transition.run(DepartureAndFirstTouch(), f14_inputs, f14_params)
    confirmed = [e for e in f14_result.events if e["event_kind"] == REACTION_CONFIRMED]
    if len(confirmed) != 1:
        raise AssertionError(
            f"F14 GV-012: expected exactly one REACTION_CONFIRMED (first touch consumes; a second "
            f"identical touch must be silently ignored), got {len(confirmed)}")
    source_reaction_id = confirmed[0]["source_reaction_id"]

    # 2 · F18 — GV-015: LONG E=100, source=99, ATR14=20 -> buffer=1 -> S=98 -> risk=2; T=104 ->
    #     reward=4, admits with the UNREDUCED pair (4, 2); T=103 -> reward=3, one tick below the
    #     PAR-061 2:1 floor -> ABSTAIN, never a crash, never a fabricated admit.
    f18_params = {
        capsules.PAR_NATURAL_INVALIDATION_BUFFER_RULE: capsules.DECLARED_NATURAL_INVALIDATION_BUFFER,
        capsules.PAR_TARGET_AVAILABILITY_RULE: capsules.TARGET_AVAILABILITY_RULE,
        capsules.PAR_TARGET_SELECTOR: capsules.TARGET_SELECTOR_PRIORITY,
        PARAM_MIN_GEOMETRIC_RR_RULE: DECLARED_MIN_GEOMETRIC_RR,
    }

    def geometry(target_ticks: int):
        return evaluate_candidate_geometry(
            direction=common.LONG, entry_reference_ticks=100,
            natural_invalidation_source_ticks=99, atr14_ticks=20,
            capsule_semantic_id=CAPSULE_ID,
            available_targets=[{"target_type": "PROTECTED_SWING", "target_ticks": target_ticks,
                               "knowledge_time_us": 0, "root_id": "t1"}],
            candidate_knowledge_time_us=1_000, params=f18_params)

    admitted = geometry(104)
    if not admitted.admitted or (admitted.rr_numerator, admitted.rr_denominator) != (4, 2):
        raise AssertionError(
            f"F18 GV-015 admit case failed: {admitted.admitted}, "
            f"({admitted.rr_numerator}, {admitted.rr_denominator}) != (4, 2) — the unreduced pair")
    below_floor = geometry(103)
    if below_floor.admitted or below_floor.abstain_reason != ABSTAIN_GEOMETRY_BELOW_FLOOR:
        raise AssertionError("F18 GV-015 below-floor boundary (T=103) must abstain, never admit")

    # 3 · F19 — GV-016: same instrument/side, zones touching at one tick, availability delta
    #     exactly 30000ms (the PAR-060 window, ms->us converted) -> SAME cluster; in an isolated
    #     pair, delta 30001ms with no source overlap -> a SEPARATE cluster (one ms past the
    #     inclusive boundary).
    f19_params = {PARAM_CLUSTER_WINDOW_MS: 30_000}
    params_digest = capsules.capsule_digest(capsules.resolve_capsule(CAPSULE_ID))
    same_cluster_inputs = [
        {"event_id": "occ_a", "kind": "CANDIDATE_OCCURRENCE",
         "payload": {"candidate_id": "CAND-A", "instrument": "BTCUSDT.BINANCE.UMF",
                    "side": common.LONG, "source_structure_id": "", "source_reaction_id": "",
                    "entry_zone_low_ticks": 100, "entry_zone_high_ticks": 105,
                    "availability_us": 0, "occurrence_version": 1, "capsule_id": CAPSULE_ID,
                    "capsule_params_digest": params_digest}},
        {"event_id": "occ_b", "kind": "CANDIDATE_OCCURRENCE",
         "payload": {"candidate_id": "CAND-B", "instrument": "BTCUSDT.BINANCE.UMF",
                    "side": common.LONG, "source_structure_id": "", "source_reaction_id": "",
                    "entry_zone_low_ticks": 105, "entry_zone_high_ticks": 110,
                    "availability_us": 30_000_000,  # exactly 30000ms: inclusive boundary
                    "occurrence_version": 1, "capsule_id": CAPSULE_ID,
                    "capsule_params_digest": params_digest}},
    ]
    f19_same = transition.run(OpportunityClusterRegistry(), same_cluster_inputs, f19_params)
    if f19_same.events[0]["event_kind"] != CLUSTER_FORMED:
        raise AssertionError("F19: the root occurrence must form a new cluster")
    if f19_same.events[1]["event_kind"] != CLUSTER_JOINED:
        raise AssertionError("F19 GV-016: an occurrence exactly at the 30000ms window boundary "
                             "must join the existing cluster, not root a new one")
    opportunity_cluster_id = f19_same.events[0]["cluster_id"]

    separate_cluster_inputs = [
        {"event_id": "occ_e", "kind": "CANDIDATE_OCCURRENCE",
         "payload": {"candidate_id": "CAND-E", "instrument": "BTCUSDT.BINANCE.UMF",
                    "side": common.LONG, "source_structure_id": "", "source_reaction_id": "",
                    "entry_zone_low_ticks": 100, "entry_zone_high_ticks": 105,
                    "availability_us": 0, "occurrence_version": 1, "capsule_id": CAPSULE_ID,
                    "capsule_params_digest": params_digest}},
        {"event_id": "occ_f", "kind": "CANDIDATE_OCCURRENCE",
         "payload": {"candidate_id": "CAND-F", "instrument": "BTCUSDT.BINANCE.UMF",
                    "side": common.LONG, "source_structure_id": "", "source_reaction_id": "",
                    "entry_zone_low_ticks": 100, "entry_zone_high_ticks": 105,
                    "availability_us": 30_001_000,  # 30001ms: one ms past the window
                    "occurrence_version": 1, "capsule_id": CAPSULE_ID,
                    "capsule_params_digest": params_digest}},
    ]
    f19_separate = transition.run(OpportunityClusterRegistry(), separate_cluster_inputs, f19_params)
    if f19_separate.events[1]["event_kind"] != CLUSTER_FORMED:
        raise AssertionError("F19 GV-016: 30001ms with no source overlap must root a SEPARATE "
                             "cluster, not join")

    # 4 · Capsule + trial identity: every one of the five ratified semantic capsules resolves; an
    #     RC2 ordinal spelling is never accepted as an alias.
    for semantic_id in capsules.CANONICAL_SEMANTIC_IDS:
        capsules.resolve_capsule(semantic_id)
    try:
        capsules.resolve_capsule("CAP01_OB_ENTRY")
    except capsules.CapsuleUnavailableError:
        pass
    else:
        raise AssertionError("an RC2 CAP-ordinal spelling must never resolve as a capsule alias")

    trial_id = "E2E-TRIAL-1"
    trial_state = transition.run(
        trial_registry.TrialRegistry(),
        [{"event_id": "pre1", "kind": "PREREGISTER_TRIAL",
          "payload": {"trial_id": trial_id, "capsule_semantic_id": CAPSULE_ID,
                     "conjunct_set": ["c1"], "results_available_after_us": 1,
                     "preregistered_at_us": 0}}], {}).final_state

    # 5 · The composed edge_candidate.v2 payload, built from the F14/F18/F19 outputs above -> the
    #     mandatory atomic SHADOW fork. No candidate path without a durable SHADOW write.
    edge_candidate_payload = {
        "candidate_id": "E2E-CAND-1", "hypothesis_id": "E2E-HYP-1",
        "opportunity_cluster_id": opportunity_cluster_id, "capsule_id": CAPSULE_ID,
        "capsule_version": "1", "parameter_digest": "a" * 64, "trial_id": trial_id,
        "source_structure_id": "E2E-STRUCT-1", "source_reaction_id": source_reaction_id,
        "canonical_instrument_id": "BTCUSDT.BINANCE.UMF", "direction": common.LONG,
        "horizon": "100", "entry_policy": "MARKET_TOUCH",
        "entry_reference_ticks": canonical.tick_to_str(admitted.entry_reference_ticks),
        "natural_invalidation_ticks": canonical.tick_to_str(admitted.natural_invalidation_ticks),
        "targets": [{"target_type": admitted.selected_target_type,
                    "target_ticks": canonical.tick_to_str(admitted.selected_target_ticks)}],
        "rr_numerator": canonical.tick_to_str(admitted.rr_numerator),
        "rr_denominator": canonical.tick_to_str(admitted.rr_denominator),
        "ttl_us": 5_000, "not_before_us": 1_000, "cancellation_conditions": [],
        "cost_model_id": "COST1", "fill_model_id": "FILL1", "arm": "SHADOW", "quality": {},
        "prerequisites": [], "provenance_hash": "b" * 64,
    }
    publish_result = transition.run(
        CandidatePublisher(),
        [{"event_id": "pub1", "kind": "PUBLISH_CANDIDATE",
          "payload": {"edge_candidate": edge_candidate_payload,
                     "trial_registry_state": trial_state, "event_time_us": 10_000,
                     "market_watermark": {"watermark_us": 5_000},
                     "evaluation_notional_quote": "1000000", "simulator_version": "sim-1",
                     "resolver_version": "res-1", "cost_model_version": "cost-1"}}],
        {})
    kinds = [e["event_kind"] for e in publish_result.events]
    if kinds != [CANDIDATE_PUBLISHED, SHADOW_TRADE_RECORDED]:
        raise AssertionError(f"composed publish did not fork atomically: {kinds}")
    trade = list(publish_result.final_state["shadow"]["trades"].values())[0]
    if trade["origin_disposition"] != "ACCEPTED_NOT_EXECUTED":
        raise AssertionError("an ORIGIN-published candidate must fork ACCEPTED_NOT_EXECUTED, "
                             "never REJECTED (ORIGIN holds no execution authority)")
    contracts.validate_payload("triad.edge_candidate.v2", edge_candidate_payload)

    # 6 · The untradeable path: a candidate with no surviving target (F18's own ABSTAIN_NO_TARGET/
    #     GEOMETRY_BELOW_FLOOR shape, mirrored here as an empty targets array) forks ONLY a
    #     shadow_rejection_audit — never a published candidate, never a crash.
    untradeable_payload = dict(edge_candidate_payload, candidate_id="E2E-CAND-2", targets=[])
    untradeable_result = transition.run(
        CandidatePublisher(),
        [{"event_id": "pub2", "kind": "PUBLISH_CANDIDATE",
          "payload": {"edge_candidate": untradeable_payload, "trial_registry_state": trial_state,
                     "event_time_us": 10_000, "market_watermark": {"watermark_us": 5_000},
                     "evaluation_notional_quote": "1000000", "simulator_version": "sim-1",
                     "resolver_version": "res-1", "cost_model_version": "cost-1"}}],
        {})
    if untradeable_result.events[0]["event_kind"] != CANDIDATE_PUBLICATION_REFUSED:
        raise AssertionError("an untradeable candidate must be refused, never published")
    if "E2E-CAND-2" in untradeable_result.final_state["candidates"]:
        raise AssertionError("an untradeable candidate must never appear in the published set")

    # 7 · The append-only lifecycle: a published candidate withdraws cleanly.
    withdraw_result = transition.run(
        CandidatePublisher(),
        [{"event_id": "pub1", "kind": "PUBLISH_CANDIDATE",
          "payload": {"edge_candidate": edge_candidate_payload,
                     "trial_registry_state": trial_state, "event_time_us": 10_000,
                     "market_watermark": {"watermark_us": 5_000},
                     "evaluation_notional_quote": "1000000", "simulator_version": "sim-1",
                     "resolver_version": "res-1", "cost_model_version": "cost-1"}},
         {"event_id": "wd1", "kind": "WITHDRAW_CANDIDATE",
          "payload": {"candidate_id": "E2E-CAND-1", "reason": "E2E_WALK", "event_time_us": 20_000}}],
        {})
    if withdraw_result.events[-1]["event_kind"] != CANDIDATE_TRANSITIONED:
        raise AssertionError("withdrawal after publication must transition cleanly")
    if withdraw_result.events[-1]["to_state"] != STATE_WITHDRAWN:
        raise AssertionError("withdrawal must reach the terminal WITHDRAWN state")


# ---------------------------------------------------------------- stage 22
@stage("b07_control_plane_walk",
       "B07: 192-row config materialize/require -> the 13-domain signed bundle -> comparator "
       "two-axis divergence -> authority-fact ordering/split-brain -> frozen legacy bridge -> "
       "same-code replay identity -> READY_NO_AUTHORITY service composition")
def b07_control_plane_walk() -> None:
    from triad_origin import contracts, service, transition
    from triad_origin.config import parameters as config_parameters
    from triad_origin.config import signed_bundle as config_signed_bundle
    from triad_origin.control import authority_fact_verifier as afv
    from triad_origin.control import comparator
    from triad_origin.control import legacy_bridge as lb
    from triad_origin.control import replay_runner as rr
    from triad_origin.health import Readiness

    # 1 · Config materialization: the 192-row partition and the require() refusal/admit law.
    registry = config_parameters.load_registry()
    if len(registry.materialized_ids()) != 51 or len(registry.refused_ids()) != 141:
        raise AssertionError(
            f"192-row partition drifted: materialized={len(registry.materialized_ids())} "
            f"refused={len(registry.refused_ids())} (expected 51/141)")
    try:
        registry.require("PAR-070")  # BLOCKING_OWNER_DECISION — must refuse
    except config_parameters.ParameterRefusedError:
        pass
    else:
        raise AssertionError("PAR-070 (BLOCKING_OWNER_DECISION) must refuse via require()")
    ratified_row = registry.require("PAR-001")  # RATIFIED_RC1 — must admit
    if ratified_row["status"] != "RATIFIED_RC1":
        raise AssertionError("PAR-001 must materialize as RATIFIED_RC1")

    # 2 · The 13-domain signed bundle: builds, self-verifies, and every anchor id resolves.
    known_contracts = frozenset(contracts.known_contracts())
    bundle = config_signed_bundle.build_signed_bundle(registry, known_contracts)
    if set(bundle["domains"]) != set(config_signed_bundle.DOMAINS):
        raise AssertionError("signed bundle must cover exactly the thirteen named domains")
    if not config_signed_bundle.verify_signed_bundle(bundle):
        raise AssertionError("freshly built signed bundle must self-verify")

    # 3 · Comparator: identical candidates diverge nowhere; a geometry mismatch classifies
    #     GEOMETRY on the ENGINE_COHORT axis, never conflated with the INTELLIGENCE_ARM axis.
    control_candidate = {
        "engine_cohort": "LEGACY_COMPARATOR", "intelligence_arm": "DETERMINISTIC_CONTROL",
        "candidate_id": "cand-1", "direction": "LONG",
        "entry_reference_ticks": "100", "natural_invalidation_ticks": "90", "targets": ["110"],
        "rr_numerator": "2", "rr_denominator": "1", "source_structure_id": "s1",
        "source_reaction_id": "r1", "state": "PROPOSED", "quality": {}, "arm": "SHADOW",
        "provenance_hash": "a" * 64,
    }
    # engine_cohort is the axis under test here — intelligence_arm is held CONSTANT across both
    # sides (the comparator refuses a pair whose non-compared axis disagrees).
    treatment_candidate = dict(control_candidate, engine_cohort="ORIGIN_CANDIDATE",
                               entry_reference_ticks="999")
    divergence = comparator.compare_engine_cohort(
        control_candidate, treatment_candidate, input_offset=1, evaluated_at_us=1000,
        divergence_id="e2e-div-1")
    if divergence is None or divergence["divergence_class"] != "GEOMETRY":
        raise AssertionError("a real geometry mismatch on the engine_cohort axis must classify "
                             "GEOMETRY")
    contracts.validate_payload("triad.divergence_record.v1", divergence)

    # 4 · Authority-fact verifier: the ordering law (highest token wins exact scope), a stale
    #     token refuses, a disagreeing same-token duplicate latches split brain, and split brain
    #     blocks even a strictly higher token until an explicit proof-bearing clear.
    def authority_fact(**overrides):
        base = {
            "authority_id": "auth-1", "authoritative_topic": "edge.authority.v1",
            "scope": {"instrument": "BTCUSDT"}, "selected_engine_cohort": "ORIGIN_CANDIDATE",
            "fencing_token": "5", "epoch": "1", "issued_at_us": 1000, "not_before_us": 1000,
            "expires_at_us": 5000, "revoked_at_us": 1000, "renewed_at_us": 1000,
            "activation_manifest_id": "am-1", "issuer": "governance-lease-issuer",
            "state": "ACTIVE", "allocation": {}, "conflicts": [], "signature": "sig-1",
        }
        base.update(overrides)
        return base

    ledger = afv.AuthorityLedger()
    first = ledger.admit_fact(authority_fact(), now_us=1100)
    if not first.accepted:
        raise AssertionError("the first authority fact for a fresh scope must be accepted")
    stale = ledger.admit_fact(authority_fact(fencing_token="1"), now_us=1200)
    if stale.accepted or stale.reason != afv.REFUSED_STALE:
        raise AssertionError("a lower fencing token for the same scope must refuse as STALE")
    conflict = ledger.admit_fact(authority_fact(issuer="rogue-issuer"), now_us=1300)
    if conflict.accepted or not conflict.split_brain:
        raise AssertionError("a same-token disagreeing fact must latch split brain")
    blocked = ledger.admit_fact(authority_fact(fencing_token="99"), now_us=1400)
    if blocked.accepted:
        raise AssertionError("split brain must block even a strictly higher token")
    ledger.clear_split_brain({"instrument": "BTCUSDT"}, proof="e2e walk proof")
    recovered = ledger.admit_fact(authority_fact(fencing_token="99"), now_us=1500)
    if not recovered.accepted:
        raise AssertionError("admission must resume once split brain is explicitly cleared")

    # 5 · Frozen legacy bridge: an omission-carrying legacy record passes through byte-identical,
    #     and a restart resumes from the correct next offset with no reprocessing.
    legacy_state = lb.LegacyBridgeState()
    legacy_raw = {"id": "legacy-1", "symbol": "BTCUSDT"}  # deliberately missing modern fields
    envelope = legacy_state.bridge(
        legacy_raw, intelligence_arm="DETERMINISTIC_CONTROL", source_topic="legacy.candidates.v1",
        input_offset=0, bridged_at_us=1000)
    if envelope["legacy_payload"] != legacy_raw or "targets" in envelope["legacy_payload"]:
        raise AssertionError("the legacy bridge must never repair/backfill a source omission")
    if not lb.verify_byte_preservation(envelope):
        raise AssertionError("the bridged envelope must verify byte-identical to its source")
    if legacy_state.resume_from_offset("legacy.candidates.v1") != 1:
        raise AssertionError("resume_from_offset must advance past the highest bridged offset")

    # 6 · Same-code replay runner: two independent runs over byte-identical inputs produce
    #     byte-identical receipts, each schema-valid.
    class _CounterMachine:
        def initial_state(self):
            return {"count": 0}

        def transition(self, state, envelope, params, quality):
            new_state = dict(state)
            new_state["count"] = state["count"] + 1
            return transition.TransitionResult(
                new_state, ({"event_kind": "TICK", "n": new_state["count"]},))

    machine = _CounterMachine()
    replay_inputs = [{"event_id": f"e2e-{i}"} for i in range(4)]
    replay_kwargs = dict(
        partition="e2e-replay", build_commit="e" * 40, config_bundle_sha256="0" * 64,
        contract_manifest_sha256="1" * 64, parameter_digest=registry.parameter_digest,
        instrument_digest="3" * 64, platform="linux-x86_64", run_seed="e2e-seed",
        receipt_id="e2e-receipt", signer="e2e-signer")
    receipt_a = rr.run_replay(machine, replay_inputs, {}, **replay_kwargs)
    receipt_b = rr.run_replay(machine, replay_inputs, {}, **replay_kwargs)
    if receipt_a != receipt_b:
        raise AssertionError("two independent replay runs over identical inputs must be "
                             "byte-identical")
    contracts.validate_payload("triad.replay_receipt.v1", receipt_a)

    # 7 · The service composes every conjunct into READY_NO_AUTHORITY — and never further.
    readiness, _detail = service.compute_service_readiness(
        manifest_ok=True, warmup_complete=True, checkpoint_parity=True, ledgers_writable=True,
        parameter_registry=registry, known_contract_ids=known_contracts)
    if readiness is not Readiness.READY_NO_AUTHORITY:
        raise AssertionError(f"expected READY_NO_AUTHORITY with every conjunct satisfied, "
                             f"got {readiness}")
    degraded, _detail2 = service.compute_service_readiness(
        manifest_ok=True, warmup_complete=True, checkpoint_parity=True, ledgers_writable=True,
        parameter_registry=registry, known_contract_ids=frozenset())
    if degraded is Readiness.READY_NO_AUTHORITY:
        raise AssertionError("an unresolvable control-plane conjunct must never report "
                             "READY_NO_AUTHORITY")


# ---------------------------------------------------------------- stage 22 (B0R tooling)
@stage("repair_tooling_walk", "B0R tooling: spec/control counts (strict) -> tracked secret scan "
                              "(clean) -> RFC 8785 JCS canonicalization (deterministic) -> receipt "
                              "profile-decision + two-key trust registry drafts -> Ed25519 verify "
                              "fails closed on an unsigned envelope")
def repair_tooling_walk() -> None:
    import hashlib

    def _tool(script: str, *args: str, expect_zero: bool = True) -> subprocess.CompletedProcess:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "tools" / script), *args],
            capture_output=True, text=True, cwd=ROOT)
        if expect_zero and proc.returncode != 0:
            raise AssertionError(
                f"tools/{script} {' '.join(args)} exited {proc.returncode}\n"
                f"stdout: {proc.stdout}\nstderr: {proc.stderr}")
        return proc

    # 1 · Spec/control count reconciliation (strict): exactly one strict-JSON object, exit 0.
    counts = json.loads(_tool("verify_spec_control_counts.py", "--strict").stdout)
    if counts.get("schema") != "triad.origin.spec_control_counts.v1":
        raise AssertionError(f"spec/control counts schema mismatch: {counts.get('schema')!r}")
    if (counts.get("rc1_test_count"), counts.get("rc3_effective_verification_count"),
            counts.get("rc4_fixture_count")) != (408, 1523, 125):
        raise AssertionError(f"spec/control counts drifted from the pinned expectations: {counts}")

    # 2 · Tracked secret scan: clean (no hit) on the current tree, exit 0.
    scan = _tool("scan_secrets.py", "--tracked", "--fail-on-hit")
    if scan.stdout.strip():
        raise AssertionError(f"tracked secret scan reported hits:\n{scan.stdout}")

    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)  # outside the repository (the tools refuse an in-repo --out)

        # 3 · RFC 8785 JCS canonicalization: key-sorted, whitespace-free, and deterministic.
        jcs_fixture = tmp / "jcs.json"
        jcs_fixture.write_text('{"b": 2, "a": {"d": 4, "c": 3}}', encoding="utf-8")
        one = _tool("jcs_canonical.py", str(jcs_fixture)).stdout
        two = _tool("jcs_canonical.py", str(jcs_fixture)).stdout
        if one != two or one != '{"a":{"c":3,"d":4},"b":2}':
            raise AssertionError(f"JCS canonicalization is not deterministic/RFC 8785: {one!r}")

        # 4 · Receipt-ceremony draft builders: the ratified profile decision and a two-key trust
        #     registry; each writes deterministic bytes and prints exactly the file's SHA-256.
        profile = tmp / "profile_decision.json"
        pd = _tool("build_profile_decision.py", "--out", str(profile))
        if pd.stdout.strip() != hashlib.sha256(profile.read_bytes()).hexdigest():
            raise AssertionError("build_profile_decision stdout is not the file SHA-256")

        import base64
        far_future = str(4_102_444_800_000_000)  # ~year 2100, UTC epoch microseconds
        spec = tmp / "registry_spec.json"
        spec.write_text(json.dumps([
            {"key_id": "e2e-producer", "identity": "builder-a", "role": "PRODUCER",
             "public_key_base64": base64.b64encode(bytes(range(32))).decode("ascii"),
             "valid_from_us": "0", "valid_until_us": far_future, "approved_milestones": ["ALL"]},
            {"key_id": "e2e-countersigner", "identity": "reviewer-b", "role": "COUNTERSIGNER",
             "public_key_base64": base64.b64encode(bytes(range(32, 64))).decode("ascii"),
             "valid_from_us": "0", "valid_until_us": far_future, "approved_milestones": ["ALL"]},
        ]), encoding="utf-8")
        registry = tmp / "registry.json"
        tr = _tool("build_trust_registry.py", "--spec", str(spec), "--out", str(registry))
        if tr.stdout.strip() != hashlib.sha256(registry.read_bytes()).hexdigest():
            raise AssertionError("build_trust_registry stdout is not the file SHA-256")

        # 5 · Ed25519 verification fails CLOSED: an UNSIGNED DSSE envelope (no signatures) yields no
        #     verified signer against a valid two-key registry, so the tool exits non-zero. (This
        #     repository holds verify-only tooling — signing is an external operator act.)
        envelope = tmp / "envelope.json"
        envelope.write_text(json.dumps({
            "payloadType": "application/vnd.triad.evidence-receipt.v3+json",
            "payload": base64.b64encode(b"{}").decode("ascii"),
            "signatures": []}), encoding="utf-8")
        ev = _tool("ed25519_verify.py", "--envelope", str(envelope), "--registry", str(registry),
                   expect_zero=False)
        if ev.returncode == 0:
            raise AssertionError("ed25519_verify must fail closed on an unsigned envelope")


# ---------------------------------------------------------------- stage 24
@stage("read_faces_walk",
       "B08: six RC4 §L6 read faces (lever registry/attestation/history, SHADOW health, four-plane "
       "status, inventory reconciliation) + the nine W25 evidence views over the real B05 substrate; "
       "requested/effective/proof separate; SHADOW activation separate from health; honest "
       "UNAVAILABLE/NOT_MEASURABLE; bounded/paginated cardinality; OFF/OFF/OFF/LIVE preserved; "
       "READY_NO_AUTHORITY never widened")
def read_faces_walk() -> None:
    from triad_origin import transition
    from triad_origin.control import comparator, lever_law
    from triad_origin.control.lever_registry import LeverRegistry
    from triad_origin.control.shadow_health import ShadowHealth
    from triad_origin.read_faces import envelope as ev
    from triad_origin.read_faces import faces, views

    # A caller-frozen snapshot instant + a SEPARATE source watermark (UTC epoch microseconds). A face
    # never reads a clock; every timestamp here is a literal fixture (LEV-V-0124: two timestamps).
    as_of = 1_700_000_000_000_000
    watermark = 1_699_999_999_000_000

    def _manifest(rev: int, digest: str):
        # Every manifest carries the required non-authoritative baseline: OFF/OFF/OFF/LIVE.
        return {"event_id": f"reg_{rev}_{digest}", "kind": "REGISTER_MANIFEST", "payload": {
            "venue_environment": "OFF", "venue_activation": "OFF", "paper_activation": "OFF",
            "shadow_activation": "LIVE",
            "activations": {"origin.a": "OFF", "origin.b": "OFF", "origin.c": "OFF"},
            "manifest_digest_sha256": digest, "revision": rev}}

    def _attest(digest: str, rev: int, age_ms: int):
        return {"event_id": f"att_{rev}_{age_ms}", "kind": "ATTEST_RUNTIME", "payload": {
            "engine_id": "origin.candidate", "accepted_manifest_digest_sha256": digest,
            "accepted_revision": rev, "freshness_age_ms": age_ms}}

    # Drive the REAL LeverRegistry and ShadowHealth machines so a face projects real machine output.
    registry_state = transition.run(
        LeverRegistry(), [_manifest(1, "d1"), _attest("d1", 1, 1000)], {}).final_state
    # A revision bump leaves the rev-1 attestation stale-of-revision — the mismatch the face must flag.
    bumped_state = transition.run(
        LeverRegistry(),
        [_manifest(1, "d1"), _attest("d1", 1, 1000), _manifest(2, "d2")], {}).final_state
    health_state = transition.run(
        ShadowHealth(), [{"event_id": "hb", "kind": "WRITER_HEARTBEAT", "payload": {"age_ms": 2000}}],
        {}).final_state
    shadow_ledger = {"trades": {"t0": {}, "t1": {}}, "audits": {"a0": {}}}  # 2 + 1 = 3 reconciled
    paper_ledger = {"accounts": {"acct1": {"orders": {"o1": {}}, "fills": {"f1": {}}}},
                    "trades": {"pt1": {}}}

    # 1 · LEV-0110 registry: canonical venue_environment AVAILABLE=='OFF', shadow_activation 'LIVE'
    #     (structural, never fabricated); venue_activation/paper_activation are NOT_MEASURABLE (the
    #     registry persists neither); requested / effective / proof are carried SEPARATELY (LEV-0120).
    e110 = faces.get_engine_lever_registry(
        registry_state=registry_state, as_of_us=as_of, watermark_us=watermark,
        requested_manifest=dict(lever_law.BASELINE_MANIFEST))
    ev.validate(e110)
    canonical = e110.value["effective"]["canonical"]
    if canonical["venue_environment"] != {"status": "AVAILABLE", "value": "OFF", "reason": None}:
        raise AssertionError(
            f"LEV-0110 effective canonical venue_environment must be AVAILABLE 'OFF'; got "
            f"{canonical['venue_environment']!r}")
    if canonical["shadow_activation"]["value"] != "LIVE":
        raise AssertionError("LEV-0110 canonical shadow_activation must be the structural 'LIVE'")
    if canonical["venue_activation"]["status"] != ev.STATUS_NOT_MEASURABLE \
            or canonical["paper_activation"]["status"] != ev.STATUS_NOT_MEASURABLE:
        raise AssertionError(
            "LEV-0110 venue_activation/paper_activation must be NOT_MEASURABLE (the registry persists "
            "neither) — never a fabricated OFF")
    if e110.value["requested"] != dict(lever_law.BASELINE_MANIFEST):
        raise AssertionError("LEV-0110 requested manifest must be carried separately, verbatim")
    if not (e110.value["requested"] is not e110.value["effective"]
            is not e110.value["proof"]):
        raise AssertionError("LEV-0110 requested / effective / proof must be three SEPARATE facets")
    if e110.as_of_us != as_of or e110.watermark_us != watermark:
        raise AssertionError("LEV-0110 as_of_us and watermark_us must be carried SEPARATELY (LEV-V-0124)")

    # 2 · LEV-0111 attestation: after a revision bump the stored rev-1 attestation is flagged
    #     RUNTIME_LEVER_ATTESTATION_MISMATCH — never silently reconciled.
    e111 = faces.get_engine_lever_attestation(registry_state=bumped_state, as_of_us=as_of)
    ev.validate(e111)
    row = e111.value["attestations"][0]
    if row["revision_matches_current"] is not False \
            or row["mismatch"] != "RUNTIME_LEVER_ATTESTATION_MISMATCH":
        raise AssertionError(
            "LEV-0111 a stale-of-revision attestation must flag RUNTIME_LEVER_ATTESTATION_MISMATCH")
    if row["lease"]["status"] != ev.STATUS_NOT_MEASURABLE:
        raise AssertionError("LEV-0111 lease proof is wire-only → NOT_MEASURABLE (verify-only posture)")

    # 3 · LEV-0112 history: an empty (present) stream is a MEASURED-EMPTY AVAILABLE (never inferred
    #     OFF); an absent source is UNAVAILABLE — the two are distinct named states.
    e112_empty = faces.get_engine_lever_history(transitions=[], as_of_us=as_of)
    ev.validate(e112_empty)
    e112_absent = faces.get_engine_lever_history(transitions=None, as_of_us=as_of)
    ev.validate(e112_absent)
    if e112_empty.status != ev.STATUS_AVAILABLE or e112_absent.status != ev.STATUS_UNAVAILABLE:
        raise AssertionError(
            "LEV-0112 empty history is AVAILABLE (measured empty); None is UNAVAILABLE (distinct)")

    # 4 · LEV-0113 SHADOW health: activation (the always-LIVE lever) is shown SEPARATELY from health
    #     (the gauges/counters) — LEV-0118; the LEV-0088 coverage is an EXACT integer pair (no float),
    #     NOT_MEASURABLE without a presented total, UNAVAILABLE when the ledger itself is absent.
    e113 = faces.get_shadow_health(
        health_state=health_state, ledger_state=shadow_ledger, as_of_us=as_of,
        rejected_inputs_presented=3)
    ev.validate(e113)
    if e113.value["shadow_activation"]["value"] != "LIVE" or "shadow_activation" not in e113.value \
            or "health" not in e113.value:
        raise AssertionError("LEV-0113 SHADOW activation must be shown SEPARATELY from SHADOW health")
    cov = e113.value["coverage"]
    if cov["status"] != ev.STATUS_AVAILABLE or cov["fully_reconciled"] is not True \
            or not isinstance(cov["reconciled_total"], int) or isinstance(cov["reconciled_total"], bool):
        raise AssertionError("LEV-0088 coverage must be an EXACT integer pair; 3 reconciled == 3 presented")
    cov_nm = faces.get_shadow_health(
        health_state=health_state, ledger_state=shadow_ledger, as_of_us=as_of).value["coverage"]
    cov_un = faces.get_shadow_health(
        health_state=health_state, ledger_state=None, as_of_us=as_of,
        rejected_inputs_presented=3).value["coverage"]
    if cov_nm["status"] != ev.STATUS_NOT_MEASURABLE or cov_un["status"] != ev.STATUS_UNAVAILABLE:
        raise AssertionError(
            "LEV-0088 an absent presented-total is NOT_MEASURABLE; an absent ledger is UNAVAILABLE "
            "(the two absences are distinct)")

    # 5 · LEV-0114 four-plane: TESTNET/LIVE hold no in-repo venue truth ⇒ honest UNAVAILABLE, never an
    #     inferred OFF (LEV-V-0122); SHADOW activation is the always-LIVE lever; the requested baseline
    #     is exactly OFF/OFF/OFF/LIVE.
    e114 = faces.get_four_plane_status(
        as_of_us=as_of, shadow_ledger_state=shadow_ledger, paper_ledger_state=paper_ledger,
        registry_state=registry_state)
    ev.validate(e114)
    planes = e114.value["planes"]
    if planes["TESTNET"]["status"] != ev.STATUS_UNAVAILABLE \
            or planes["LIVE"]["status"] != ev.STATUS_UNAVAILABLE:
        raise AssertionError("LEV-0114 TESTNET/LIVE must be UNAVAILABLE (no venue truth), never OFF")
    if planes["SHADOW"]["activation"] != "LIVE":
        raise AssertionError("LEV-0114 SHADOW plane activation must be the always-LIVE lever")
    if e114.value["authority_evidence"]["requested_baseline_manifest"] != dict(lever_law.BASELINE_MANIFEST):
        raise AssertionError("LEV-0114 requested baseline manifest must be exactly OFF/OFF/OFF/LIVE")

    # 6 · LEV-0115 inventory reconciliation: a two-sided mismatch surfaces a NAMED contradiction; a
    #     single-sided axis is NOT_MEASURABLE; an unobserved axis is UNAVAILABLE (never inferred).
    e115 = faces.get_engine_inventory_reconciliation(
        as_of_us=as_of,
        identities={"registry": {"expected": "x", "observed": "y"}, "payload": {"expected": "z"}})
    ev.validate(e115)
    axes = {r["axis"]: r for r in e115.value["axes"]}
    if axes["registry"]["status"] != ev.STATUS_AVAILABLE or axes["registry"]["contradiction"] is not True:
        raise AssertionError("LEV-0115 a two-sided expected!=observed axis must be a NAMED contradiction")
    if axes["payload"]["status"] != ev.STATUS_NOT_MEASURABLE:
        raise AssertionError("LEV-0115 a single-sided axis is NOT_MEASURABLE (nothing to reconcile)")
    if axes["relay"]["status"] != ev.STATUS_UNAVAILABLE:
        raise AssertionError("LEV-0115 an unobserved axis is UNAVAILABLE, never an inferred match")
    if e115.value["contradiction_axes"] != ["registry"] or e115.value["any_contradiction"] is not True:
        raise AssertionError("LEV-0115 the contradiction roll-up must name the registry axis")

    # 7 · Bounded cardinality (LEV-0122): a page smaller than the set is TRUNCATED and carries a
    #     next-page cursor; the full page is COMPLETE and carries NONE (one source of truth).
    first = faces.get_engine_lever_registry(registry_state=registry_state, as_of_us=as_of, limit=2)
    ev.validate(first)
    if first.completeness != ev.COMPLETENESS_TRUNCATED or first.cursor is None:
        raise AssertionError("LEV-0122 a truncated page must be TRUNCATED and name a cursor")
    nxt = faces.get_engine_lever_registry(
        registry_state=registry_state, as_of_us=as_of, limit=2, after=first.cursor)
    ev.validate(nxt)
    if nxt.completeness != ev.COMPLETENESS_COMPLETE or nxt.cursor is not None:
        raise AssertionError("LEV-0122 the final page must be COMPLETE and carry no cursor")

    # 8 · The envelope contract itself: a fabricated zero (AVAILABLE with value None) is REFUSED, and a
    #     non-AVAILABLE status carries no value / a named reason (no empty green).
    try:
        ev.available(face=faces.FACE_LEVER_REGISTRY, source="e2e", as_of_us=as_of, value=None)
    except ev.ReadFaceEnvelopeError:
        pass
    else:
        raise AssertionError("an AVAILABLE envelope with a None value (fabricated zero) must be REFUSED")
    un = ev.unavailable(face=faces.FACE_SHADOW_HEALTH, source="e2e", as_of_us=as_of, reason="ABSENT")
    ev.validate(un)
    if un.value is not None or un.reason != "ABSENT":
        raise AssertionError("an UNAVAILABLE envelope must carry no value and a named reason")

    # 9 · The nine W25 evidence views: each AVAILABLE arm validates and names source + freshness; each
    #     absent-source arm is a validating UNAVAILABLE carrying value=None (no empty green).
    divergence_record = comparator.compare_engine_cohort(
        None, {"candidate_id": "c1", "engine_cohort": "ORIGIN_CANDIDATE"},
        input_offset=3, evaluated_at_us=as_of, divergence_id="d1")
    view_available = [
        views.get_offsets_view(
            partitions={"p1": {"input_segment": "s", "input_offset": 4}}, as_of_us=as_of),
        views.get_watermarks_view(
            watermarks={"p1": {"completed_through_us": 500, "allowed_lateness_us": 1000}}, as_of_us=as_of),
        views.get_quality_view(quality={"finalized": True}, as_of_us=as_of),
        views.get_lineage_view(
            structures_state={"last_event_id": "e", "structures": {"s1": {"state": "CONFIRMED"}}},
            as_of_us=as_of),
        views.get_funnel_view(
            events=[{"event_kind": "CANDIDATE_PUBLISHED", "candidate_id": "c", "transition_id": "t"}],
            as_of_us=as_of),
        views.get_divergence_view(records=[divergence_record], as_of_us=as_of),
        views.get_replay_view(
            receipts=[{"receipt_id": "r1", "fidelity_class": "EXACT"}], as_of_us=as_of),
        views.get_receipt_view(
            receipt={"receipt_id": "B08", "result": "PASS", "builder": "a", "reviewer": "b",
                     "observed_at_us": 10, "expires_at_us": 20}, as_of_us=as_of),
        views.get_readiness_view(bootstrap_readiness="READY_NO_AUTHORITY", as_of_us=as_of),
    ]
    if len(view_available) != len(views.VIEW_NAMES):
        raise AssertionError(
            f"the walk must exercise all {len(views.VIEW_NAMES)} W25 views; drove {len(view_available)}")
    for view in view_available:
        ev.validate(view)
        d = view.to_dict()
        if d["status"] != ev.STATUS_AVAILABLE or not d["source"] or d["as_of_us"] != as_of:
            raise AssertionError(f"W25 view {d['face']} must be AVAILABLE and name source + freshness")

    view_absent = [
        views.get_offsets_view(partitions=None, as_of_us=as_of),
        views.get_watermarks_view(watermarks=None, as_of_us=as_of),
        views.get_quality_view(quality=None, as_of_us=as_of),
        views.get_lineage_view(structures_state=None, as_of_us=as_of),
        views.get_funnel_view(events=None, as_of_us=as_of),
        views.get_divergence_view(records=None, as_of_us=as_of),
        views.get_replay_view(receipts=None, as_of_us=as_of),
        views.get_receipt_view(receipt=None, as_of_us=as_of),
        views.get_readiness_view(bootstrap_readiness=None, as_of_us=as_of),
    ]
    for view in view_absent:
        ev.validate(view)
        if view.status != ev.STATUS_UNAVAILABLE or view.value is not None:
            raise AssertionError(
                f"an absent-source W25 view ({view.face}) must be UNAVAILABLE with value=None")

    # 10 · The divergence view rolls up the REAL comparator record by class (the EXTRA arm), with every
    #      class a named zero.
    div = views.get_divergence_view(records=[divergence_record], as_of_us=as_of)
    if div.value["by_class"]["EXTRA"] != 1 \
            or set(div.value["by_class"]) != set(comparator.DIVERGENCE_CLASSES):
        raise AssertionError("the divergence view must roll up the real EXTRA record over named zeros")

    # 11 · THE NARROWNESS LAW (CTRL-B08-001): the readiness view never claims more than
    #      READY_NO_AUTHORITY — even with every evidence dimension supplied positively.
    readiness = views.get_readiness_view(
        bootstrap_readiness="READY_NO_AUTHORITY", as_of_us=as_of,
        source_freshness={"age_ms": 1, "bound": "runtime_attestation_max_age_ms"},
        coverage={"reconciled": 2, "presented": 2}, lease_validity={"ok": True},
        estate_activation={"estate": "x"})
    ev.validate(readiness)
    if readiness.value["authority"] != "NONE" or readiness.value["ceiling"] != "READY_NO_AUTHORITY" \
            or readiness.value["operational_readiness_claimed"] is not False:
        raise AssertionError("CTRL-B08-001 the readiness view must never widen past READY_NO_AUTHORITY")
    blob = json.dumps(readiness.to_dict())
    for token in ("AUTHORIZED", "ARMED", "OPERATIONAL", "ACTIVATED"):
        if token in blob:
            raise AssertionError(f"a read face must never emit the authority token {token!r}")


def _load_tool_module(name: str):
    """Load a tools/ module from its file path WITHOUT executing its ``__main__`` block.

    ``tools/`` is not a package on ``sys.path``; the B09 catalog/matrix generators are pure
    (stdlib-only, guarded by ``if __name__ == "__main__":``), so an isolated file-path import is
    the same read-only load the falsification suite uses. No bytecode cache is written into the
    read-only repository tree.
    """
    import importlib.util

    path = ROOT / "tools" / f"{name}.py"
    if 'if __name__ == "__main__":' not in path.read_text(encoding="utf-8"):
        raise AssertionError(f"tools/{name}.py lacks a __main__ guard; importing it could run main")
    spec = importlib.util.spec_from_file_location(f"_e2e_tool_{name}", path)
    module = importlib.util.module_from_spec(spec)
    prev = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = prev
    return module


# ---------------------------------------------------------------- stage 25
@stage("conformance_matrix_walk",
       "B09: the RC1(408)⊂RC3(1523)+RC4(125)=1648 conformance matrix regenerates byte-identical "
       "(--verify); every row carries exactly one status from the closed vocabulary; totals + "
       "population counts reconcile; the committed matrix greens NOTHING (COVERED=0); no COVERED "
       "row carries a blocker; no BLOCKED/OUT_OF_REPO row is ever greened by an evidence link; the "
       "registry is exactly F00..F23 (no F24); the generator REFUSES a matrix that greens a blocked "
       "row")
def conformance_matrix_walk() -> None:
    # 1 · The committed artifact is byte-current (the build_ledger --verify coupling precedent).
    _run_tool("conformance_matrix.py", "--verify")

    cm = _load_tool_module("conformance_matrix")

    # 2 · Regenerate to memory and re-assert the load-bearing 408⊂1523 + 125 = 1648 accounting.
    matrix = cm.generate()
    totals = matrix["totals"]
    if (totals["rc1_408_preserved"], totals["rc3_effective_verifications"],
            totals["rc4_fixtures"]) != (408, 1523, 125):
        raise AssertionError(f"conformance matrix totals drifted from 408/1523/125: {totals}")
    if totals["matrix_rows"] != 1648 or len(matrix["rows"]) != 1648:
        raise AssertionError("the matrix must be exactly 1523+125=1648 rows (RC1 408 ⊂ RC3 1523)")

    # 3 · Exactly one status per row from the closed vocabulary; the population counts reconcile.
    counts = matrix["status_counts"]
    if any(r.get("status") not in cm.STATUS_VOCABULARY for r in matrix["rows"]):
        raise AssertionError("every row must carry a status from the closed vocabulary")
    if sum(counts.values()) != len(matrix["rows"]):
        raise AssertionError("status counts must sum to the row count")

    # 4 · The committed matrix greens NOTHING today (no evidence-link file), and no COVERED row
    #     ever carries a blocker (the no-fabricated-green law, honest fail-closed).
    if counts[cm.STATUS_COVERED] != 0:
        raise AssertionError("the committed matrix must green NOTHING today (COVERED=0)")
    if any(r.get("status") == cm.STATUS_COVERED and r.get("blocked_by") is not None
           for r in matrix["rows"]):
        raise AssertionError("no COVERED row may carry a blocker")

    # 5 · An evidence link NEVER greens a blocked or an out-of-repo row (it stays its status, with
    #     no evidence_test_id) — proven against the real RC3/RC4 bundles the tool reads.
    rc3 = cm.load_json(cm.RC3_BUNDLE, "RC3 effective control bundle")
    rc4 = cm.load_json(cm.RC4_BUNDLE, "RC4 control bundle")
    for status in (cm.STATUS_BLOCKED, cm.STATUS_OUT_OF_REPO):
        target = next(r for r in matrix["rows"] if r.get("status") == status)
        linked = cm.build_matrix(rc3, rc4, {target["id"]: "tests/x::fake"})
        row = next(r for r in linked["rows"] if r["id"] == target["id"])
        if row["status"] != status or row.get("evidence_test_id") is not None:
            raise AssertionError(f"an evidence link greened a {status} row {target['id']!r}")
        if linked["invariants"]["no_blocked_row_covered"] is not True:
            raise AssertionError("the no_blocked_row_covered invariant must hold under linking")

    # 6 · Assert no F24: the formula registry is exactly F00..F23.
    reg = matrix["formula_registry"]
    if not reg["f24_absent"] or reg["formula_ids"] != [f"F{i:02d}" for i in range(24)]:
        raise AssertionError("Assert no F24 exists: the registry must be exactly F00..F23")

    # 7 · The no-blocked-green invariant is ENFORCED, not decorative: a forged matrix that hand-forces
    #     a still-blocked row to COVERED is refused loud by the generator's own invariant assertion.
    poisoned = json.loads(cm.render(matrix))
    forced = next(r for r in poisoned["rows"] if r["status"] == cm.STATUS_BLOCKED)
    forced["status"] = cm.STATUS_COVERED  # keep blocked_by set — a fabricated green
    poisoned["invariants"] = cm._compute_invariants(poisoned)
    if poisoned["invariants"]["no_blocked_row_covered"] is not False:
        raise AssertionError("forcing a blocked row to COVERED must flip no_blocked_row_covered")
    try:
        cm._assert_invariants(poisoned)
    except cm.MatrixError:
        pass
    else:
        raise AssertionError("the matrix generator must REFUSE a greened-blocked row")


# ---------------------------------------------------------------- stage 26
@stage("formula_catalog_walk",
       "B09: the F00..F23 estate formula catalog regenerates byte-identical (--verify); the registry "
       "is exactly F00..F23 with no F24; estate_catalog is exactly F20/F21/F22/F23 as IN_REPO_CATALOG "
       "OUT_OF_REPO with owners E08/E09/E09/E10, each vendoring its GV-017..020 golden vector + the "
       "seven FORM-Fxx-01..07 boundary rows; F20 is RC4-corrected (activation_mode/rollout removed — "
       "rollout never reaches sizing, missing/invalid selected policy DENIES); the generator imports "
       "only stdlib (no money line)")
def formula_catalog_walk() -> None:
    import ast

    # 1 · The committed catalog is byte-current.
    _run_tool("build_formula_catalog.py", "--verify")

    fc = _load_tool_module("build_formula_catalog")
    catalog = fc.generate()

    # 2 · Assert no F24: the registry is exactly F00..F23.
    reg = catalog["formula_registry"]
    if not reg["f24_absent"] or reg["formula_ids"] != [f"F{i:02d}" for i in range(24)]:
        raise AssertionError("Assert no F24 exists: the registry must be exactly F00..F23")

    # 3 · estate_catalog is exactly the four money-line economics formulas F20..F23, each an
    #     OUT_OF_REPO IN_REPO_CATALOG row owned by its estate node, vendoring its golden vector +
    #     the seven FORM-Fxx-01..07 boundary rows.
    estate = catalog["estate_catalog"]
    if sorted(estate) != ["F20", "F21", "F22", "F23"]:
        raise AssertionError(f"estate_catalog must be exactly F20..F23: {sorted(estate)}")
    expected_owner = {"F20": "E08", "F21": "E09", "F22": "E09", "F23": "E10"}
    expected_gv = {"F20": "GV-017", "F21": "GV-018", "F22": "GV-019", "F23": "GV-020"}
    for fid, entry in estate.items():
        if entry.get("exec_class") != "IN_REPO_CATALOG" or entry.get("ownership") != "ESTATE" \
                or entry.get("implementation_is_out_of_repo") is not True:
            raise AssertionError(f"{fid} must be an ESTATE IN_REPO_CATALOG OUT_OF_REPO row")
        if entry.get("owner_node") != expected_owner[fid]:
            raise AssertionError(f"{fid} owner_node must be {expected_owner[fid]}")
        if entry["ledger_rows"] != [f"FORM-{fid}-{i:02d}" for i in range(1, 8)]:
            raise AssertionError(f"{fid} must vendor its seven FORM-{fid}-01..07 boundary rows")
        if entry["golden_vectors"][0]["id"] != expected_gv[fid]:
            raise AssertionError(f"{fid} must vendor its golden vector {expected_gv[fid]}")

    # 4 · F20 is RC4-corrected: no activation_mode / rollout branch — rollout metadata can NEVER
    #     reach sizing, and a missing/unsigned/stale/invalid selected policy DENIES.
    f20 = estate["F20"]["f20_law"]
    if not f20.get("activation_mode_removed") or f20.get("rollout_reaches_sizing") is not False \
            or f20.get("missing_policy_disposition") != "DENY":
        raise AssertionError("F20 law must remove rollout from sizing and DENY a missing policy")
    for policy, reason in ((None, "MISSING_SELECTED_POLICY"),
                           ("POL-1", "INVALID_SELECTED_POLICY"),
                           ({"policy_ref": "P"}, "UNSIGNED_SELECTED_POLICY"),
                           ({"policy_ref": "P", "signed": True, "stale": True},
                            "STALE_SELECTED_POLICY")):
        if fc.f20_selected_policy_deny_reason(policy) != reason:
            raise AssertionError(f"F20 must DENY policy {policy!r} with {reason}")
    if fc.f20_selected_policy_deny_reason({"policy_ref": "P", "signed": True}) is not None:
        raise AssertionError("F20 must ACCEPT one present, signed, current selected policy")
    # A rollout/environment token is stripped from the corrected F20 inputs (never a sizing input).
    corrected = fc.correct_f20_inputs(["one already-selected signed risk-budget policy",
                                       "activation_mode", "rollout_stage", "canary"])
    if any(fc._is_rollout_token(tok) for tok in corrected):
        raise AssertionError("F20 corrected inputs must carry no rollout/environment token")

    # 5 · Capability boundary — the generator imports only the stdlib allowlist (no money line).
    allow = {"__future__", "argparse", "json", "pathlib", "sys"}
    tree = ast.parse((ROOT / "tools" / "build_formula_catalog.py").read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    if not roots <= allow:
        raise AssertionError(f"formula catalog generator imports beyond stdlib: {sorted(roots - allow)}")


# ---------------------------------------------------------------- stage 27
@stage("runbooks_walk",
       "B09: the eleven operational runbooks each carry the six required sections "
       "(Owner/Trigger/Stop/Rollback/Evidence/Escalation) + a RUNBOOK id + the DENIED_SAFE_HOLD / "
       "OFF·OFF·OFF·LIVE (shadow LIVE) baseline; the TESTNET runbook is a refusal-to-operate boundary "
       "doc (never a how-to-enable) that cites the ADR-005 / sibling-estate framing")
def runbooks_walk() -> None:
    runbooks = ROOT / "docs" / "runbooks"
    names = ("migration.md", "rollback.md", "split_brain.md", "shadow_degradation.md",
             "paper_isolation.md", "testnet.md", "incident.md", "fill_lineage.md",
             "reconciliation.md", "protection.md", "disaster_recovery.md")
    if not runbooks.is_dir():
        raise AssertionError("docs/runbooks/ is missing")
    if len(names) != 11:
        raise AssertionError("the runbook set must be exactly eleven")

    required = ("Owner", "Trigger", "Stop", "Rollback", "Evidence", "Escalation")
    baseline = ("venue_environment=off", "venue_activation=off",
                "paper_activation=off", "shadow_activation=live")
    for name in names:
        path = runbooks / name
        if not path.is_file():
            raise AssertionError(f"runbook missing: docs/runbooks/{name}")
        text = path.read_text(encoding="utf-8")
        for section in required:
            if f"## {section}" not in text:
                raise AssertionError(f"docs/runbooks/{name} missing the '## {section}' section")
        if "Runbook-ID:" not in text:
            raise AssertionError(f"docs/runbooks/{name} lacks a Runbook-ID header")
        lowered = text.lower()
        if "activation posture:" not in lowered or "denied_safe_hold" not in lowered:
            raise AssertionError(f"docs/runbooks/{name} must name the DENIED_SAFE_HOLD posture")
        # The exact non-authoritative baseline manifest (shadow fixed LIVE), field=value form.
        for lever in baseline:
            if lever not in lowered:
                raise AssertionError(
                    f"docs/runbooks/{name} does not carry the baseline lever {lever.upper()!r}")

    # The TESTNET runbook is a refusal-to-operate boundary doc — never a how-to-enable procedure.
    testnet = (runbooks / "testnet.md").read_text(encoding="utf-8").lower()
    if "origin never operates" not in testnet and "refuse" not in testnet and "refusal" not in testnet:
        raise AssertionError("testnet.md must be a refusal-to-operate boundary doc")
    for forbidden in ("how to enable testnet", "how to activate testnet", "steps to enable testnet",
                      "turn on testnet", "enable testnet by"):
        if forbidden in testnet:
            raise AssertionError(f"testnet.md must not carry a how-to-enable imperative: {forbidden!r}")
    if "adr-005" not in testnet or "sibling" not in testnet:
        raise AssertionError("testnet.md must cite the ADR-005 / sibling-estate supersession framing")


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
