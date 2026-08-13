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
import re
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


def _run_tool_result(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / script), *args],
        capture_output=True, text=True, cwd=ROOT,
    )


def _run_tool(script: str, *args: str) -> None:
    proc = _run_tool_result(script, *args)
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
    wire_contracts = set(contracts.known_contracts())
    checked = 0
    for schema_dir in sorted(golden_root.iterdir()):
        if not schema_dir.is_dir():
            continue
        # Wire-contract goldens only; the B00R governance schemas (evidence_receipt.v3, trust
        # registry, decision, snapshot, evidence manifest) are NOT wire contracts and are
        # validated by the b00r_governance_evidence stage via triad_origin.governance.
        if schema_dir.name not in wire_contracts:
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
    # Canonical receipt-v3 files are authenticated only by the strict receipt-role gate, which
    # carries the owner pins and the exact-head Git binding. This legacy v2 walk must not
    # consume them: validating a v3 envelope against the v2 schema fails closed by design.
    receipts = sorted(
        path for path in (ROOT / "evidence" / "receipts").glob("B*.json")
        if not path.name.endswith(".receipt.v3.json")
    )
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

    # 2 · F11 displacement — GV-010 on the R-F11 in-place C.3 surface (the raw
    #     QualifiedDisplacement machine is DELETED): ATR_before=10 => D_ticks=15; move 15
    #     qualifies. The four F11 rows are BLOCKED in the genuine registry (honest-dark), so
    #     SELF_TEST fixture surgery mints the caps; PAR-158's declared rule byte-string carries
    #     '*' (the C.1 sentinel), so its cap is minted with a sentinel-free stand-in and the
    #     verified handle's value swapped to the declared rule (acceptance ran in full).
    import dataclasses as _dc

    from triad_origin import e01_interface as e01
    from triad_origin.structures import displacement as disp

    forge = _capability_forge()
    f11_updates: dict = {}
    for row_id, par in (("FPB-0021", "PAR-046"), ("FPB-0065", "PAR-157"),
                        ("FPB-0066", "PAR-158"), ("FPB-0067", "PAR-159")):
        f11_updates[row_id] = {
            "lifecycle_status": "ACTIVE", "cardinality": "EXACTLY_ONE",
            "migration_state": "NOT_APPLICABLE",
            "semantic_slot": f"f11_{par.lower().replace('-', '_')}_E2E",
            "condition": "E2E SELF_TEST stand-in for the F11 ratification ceremony",
            "activation_scope": f"E2E;F11;{par};displacement walk only",
            "precedence": "TEST_FIXTURE",
            "consumer": "ORIGIN(F11)",
            "consuming_wiring_ids": "W03",
            "disposition_reason": "E2E SELF_TEST posture; the repository rows stay BLOCKED.",
        }
    f11_updates["FPB-0066"]["declared_value"] = (
        "E2E-TRANSPORT max(5,ceil(ATR14_before_origin 3/2)) (sentinel-free)")
    f11_bundle = forge["fixture_bundle"](f11_updates)
    f11_caps = {
        par: transition.require_bundle(f11_bundle, par, formula_id="F11", ctx=forge["ctx"])
        for par in (disp.PARAMETER_BODY_FRACTION, disp.PARAMETER_HORIZON,
                    disp.PARAMETER_MIN_MOVE, disp.PARAMETER_CLOSE_LOCATION)
    }
    f11_caps[disp.PARAMETER_MIN_MOVE] = _dc.replace(
        f11_caps[disp.PARAMETER_MIN_MOVE], value=common.DECLARED_DISPLACEMENT_MIN_MOVE)

    def f11_bar(identity, o, h, low, c):
        return e01.require_valid_bar({
            "bar_identity": identity, "metadata_revision": "r1",
            "open_ticks": o, "high_ticks": h, "low_ticks": low, "close_ticks": c,
            "base_volume": 1, "quote_volume": 1, "trade_count": 1,
        })

    disp_state = disp.initial_state()
    origin_result = disp.evaluate(
        f11_caps, f11_bar("d_origin", 1000, 1001, 999, 1000), disp_state,
        role=disp.ROLE_ORIGIN, bar_index=0, atr14_before_origin_ticks=10)
    bar_result = disp.evaluate(
        f11_caps, f11_bar("d1", 1000, 1015, 992, 1015), origin_result.state,
        role="BAR", bar_index=1)
    qualified = [e for e in (*origin_result.events, *bar_result.events)
                 if e.get("event_kind") == "DISPLACEMENT_QUALIFIED"]
    if not qualified:
        raise AssertionError("F11 GV-010 displacement did not qualify on the v2 surface")
    if qualified[0].get("origin_bar_identity") != "d_origin":
        raise AssertionError(f"GV-010 origin identity wrong: {qualified[0]!r}")

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


# ---------------------------------------------------------------- B00R stage
@stage("b00r_governance_evidence",
       "B00R governance/evidence root: source hashes, PR-role, receipt-v3 fail-closed, "
       "closed-scope/digest law, invalidation manifest, owner-gated validators")
def b00r_governance_evidence_walk() -> None:
    from triad_origin import governance as gov

    # 1 · source-hash inventory recomputes and the RC3 composition manifest is consistent.
    _run_tool("verify_source_hashes.py")

    # 2 · PR-role classifier: SOURCE is the positive B00R governance allowlist, not every path
    #     outside evidence/.  Only the canonical bare receipt path is RECEIPT; the formerly
    #     advertised DSSE name, downstream contract code, and mixed source/evidence are INVALID.
    assert gov.classify_changed_paths(["src/triad_origin/governance.py"])[0] == "SOURCE"
    assert gov.classify_changed_paths(["src/triad_origin/contracts.py"])[0] == "INVALID"
    assert gov.classify_changed_paths(
        ["evidence/receipts/B00R.g2.receipt.v3.json"])[0] == "RECEIPT"
    assert gov.classify_changed_paths(
        ["evidence/receipts/B00R.receipt.v3.json"])[0] == "INVALID"
    assert gov.classify_changed_paths(["evidence/receipts/B00R.dsse.json"])[0] == "INVALID"
    assert gov.classify_changed_paths(
        ["src/triad_origin/contracts.py",
         "evidence/receipts/B00R.g2.receipt.v3.json"])[0] == "MIXED"
    _run_tool("classify_milestone_pr.py", "src/triad_origin/governance.py")

    # 3 · the five governance schemas validate their valid golden and reject their invalid golden.
    for sid in ("triad.evidence_receipt.v3", "triad.receipt_trust_registry.v1",
                "triad.governance_decision.v1", "triad.governance_snapshot.v1",
                "triad.evidence_manifest.v1"):
        valid = json.loads((ROOT / f"contracts/golden/{sid}/valid.json").read_text())
        invalid = json.loads((ROOT / f"contracts/golden/{sid}/invalid.json").read_text())
        gov.validate_structure(valid, sid)
        try:
            gov.validate_structure(invalid, sid)
            raise AssertionError(f"{sid} invalid golden passed structural validation")
        except gov.GovernanceError:
            pass

    # 4 · receipt-v3 is fail-closed without an externally pinned trust registry (never PASS).
    generation_one = json.loads(
        (ROOT / "contracts/golden/triad.evidence_receipt.v3/valid.json").read_text())
    result, reason = gov.validate_receipt_v3(
        generation_one, milestone="B00R", expected_root_generation=1)
    assert result == "BLOCKED", (result, reason)
    generation_two = json.loads(json.dumps(generation_one))
    generation_two["payload"]["repair_generation"] = 2
    result, reason = gov.validate_receipt_v3(generation_two, milestone="B00R")
    assert result == "BLOCKED", (result, reason)

    # 5 · closed-scope and digest laws recursively reject empty/wildcard/placeholder.
    for bad in ({}, [], "", "  ", "a*b", None):
        try:
            gov.assert_closed_scope(bad)
            raise AssertionError(f"closed-scope admitted {bad!r}")
        except gov.GovernanceError:
            pass
    for bad in ("", gov.ZERO_DIGEST, "A" * 64, "NOT_APPLICABLE"):
        try:
            gov.assert_hex64(bad, "x")
            raise AssertionError(f"assert_hex64 admitted {bad!r}")
        except gov.GovernanceError:
            pass

    # 6 · the historical invalidation manifest resolves every entry digest to the committed,
    #     byte-unchanged receipt (real evidence check).
    inv = json.loads(
        (ROOT / "docs/governance/B00_B07_INVALIDATION_MANIFEST.v1.json").read_text())
    from triad_origin.canonical import sha256_hex
    assert inv["entries"], "invalidation manifest empty"
    for entry in inv["entries"]:
        data = (ROOT / entry["path"]).read_bytes()
        assert sha256_hex(data) == entry["sha256"], entry["path"]
        assert entry["disposition"] in inv["disposition_vocabulary"]
    generation_ledger = json.loads(
        (ROOT / "docs/governance/B00R_GENERATION_LEDGER.v1.json").read_text())
    generation_one = generation_ledger["generation_1"]
    assert generation_one["disposition"] == "MERGED_UNVERIFIED"
    old_receipt = ROOT / generation_one["receipt_path"]
    assert sha256_hex(old_receipt.read_bytes()) == generation_one["receipt_sha256"]

    # 7 · the decision/trust/ruleset templates are fail-closed (unauthenticated), never a PASS.
    dec = json.loads(
        (ROOT / "docs/governance/decisions/DEC-B00-REPAIR-002.template.json").read_text())
    assert gov.decision_is_authenticated(dec) is False
    _run_tool("validate_authority_root.py")        # non-strict: UNAVAILABLE reported, exit 0
    _run_tool("validate_governance_snapshot.py")   # non-strict: UNAVAILABLE reported, exit 0

    # 8 · safety posture is exactly OFF/OFF/OFF/LIVE / DENIED_SAFE_HOLD.
    assert gov.SAFETY_POSTURE == {
        "venue_environment": "OFF", "venue_activation": "OFF",
        "paper_activation": "OFF", "shadow_activation": "LIVE"}
    assert gov.ACTIVATION_RESULT == "DENIED_SAFE_HOLD"


@stage("b01c_contract_binding_promotion",
       "B01C offline-prep: schema-mutation corpus refuses every closure-required mutation; the "
       "binding bundle authenticates + refuses six attacks; the acceptance profile is honest and "
       "drift-locked; historical B receipts stay fail-closed negative fixtures")
def b01c_contract_binding_promotion() -> None:
    import json
    from triad_origin import governance as gov
    from triad_origin.canonical import canonical_json, sha256_hex

    sys.path.insert(0, str(ROOT / "tools"))
    import gen_acceptance_profile as gap
    import run_contract_mutations as rcm
    import verify_binding_bundle as vbb

    # 1 · CON-03/06 — the authoritative validator refuses every closure-required mutation; the
    #     CON-01/02 open-boundary surface is inventoried, never silently closed.
    report = rcm.run_profile("B01C")  # in-proc run IS the proof (the CLI exit is proven by its test)
    assert report["totals"]["closure_required_wrongly_passed"] == 0, report["wrongly_passed"]
    assert report["totals"]["closure_required_refused"] > 1000
    assert len(report["corpus_digest"]) == 64
    assert report["totals"]["open_boundaries"] == len(report["open_boundary_inventory"])

    # 2 · BIND-01/03/06 — a real capability authenticates and all six authenticity attacks are
    #     refused; the packaged bundle inventories to 105 rows; no owner preimage => UNAVAILABLE.
    st = vbb.selftest()
    assert st["authenticated_ok"] and st["all_attacks_refused"], st["attacks"]
    assert st["row_count"] == 105
    _run_tool("verify_binding_bundle.py", "--selftest")

    # 3 · WP-B01C-06 — the acceptance profile is content-addressed, honest, and drift-locked.
    profile = gap.build_profile()
    unsigned = {k: v for k, v in profile.items() if k != "profile_digest"}
    assert profile["profile_digest"] == sha256_hex(canonical_json(unsigned))
    assert profile["closure_claimed"] is False
    assert profile["milestone_status"] == "OFFLINE_PREP_UNRECEIPTED"
    assert profile["levers"] == gov.SAFETY_POSTURE
    assert profile["activation_result"] == gov.ACTIVATION_RESULT
    _run_tool("gen_acceptance_profile.py", "--check")

    # 4 · EVD-01 — the historical B receipts stay byte-frozen negative fixtures (never a v3 PASS).
    inv = json.loads(
        (ROOT / "docs/governance/B00_B07_INVALIDATION_MANIFEST.v1.json").read_text())
    by_ms = {e["milestone"]: e for e in inv["entries"]}
    for milestone in ("B01", "B01R", "B02"):
        entry = by_ms[milestone]
        raw = (ROOT / entry["path"]).read_bytes()
        assert sha256_hex(raw) == entry["sha256"], milestone
        result, _reason = gov.validate_receipt_v3(json.loads(raw), milestone=milestone)
        assert result == "FAIL", (milestone, result)


@stage("c0_closure_control",
       "C0 closure control: canonical projection is structurally valid but explicitly blocked; "
       "closure-ready mode refuses the same open-blocker subject")
def c0_closure_control() -> None:
    structural = _run_tool_result("closure_control.py", "--check")
    structural_output = f"{structural.stdout}\n{structural.stderr}".lower()
    if structural.returncode != 0:
        raise AssertionError(
            "tools/closure_control.py --check did not validate the canonical control "
            f"(exit {structural.returncode})\n{structural_output}"
        )
    if re.search(r"\b[1-9][0-9]* open blockers?\b", structural_output) is None:
        raise AssertionError("C0 structural check did not report a positive open-blocker count")
    if "no closure claim" not in structural_output:
        raise AssertionError("C0 structural check omitted the explicit no-closure-claim marker")

    closure_ready = _run_tool_result("closure_control.py", "--require-closure-ready")
    ready_output = f"{closure_ready.stdout}\n{closure_ready.stderr}".lower()
    if closure_ready.returncode != 2:
        raise AssertionError(
            "tools/closure_control.py --require-closure-ready must refuse the blocked subject "
            f"with exit 2, got {closure_ready.returncode}\n{ready_output}"
        )
    if re.search(r"\bclosure[ _-]+not[ _-]+ready\b", ready_output) is None:
        raise AssertionError("C0 closure-ready refusal omitted a clear CLOSURE_NOT_READY marker")
    if re.search(r"\b[1-9][0-9]* open blockers?\b", ready_output) is None:
        raise AssertionError("C0 closure-ready refusal omitted the positive open-blocker count")


@stage("b02c_security_boundary",
       "B02C security boundary: E01 envelope validators quarantine invalid inputs; a forged "
       "sealed bundle refuses at content acceptance; the C.3 entrypoint ratchet holds; absent "
       "--authority is never a green PASS")
def b02c_security_boundary() -> None:
    # C.3 static gate — the fail-closed ratchet over the production formula surface.
    _run_tool("verify_formula_entrypoints.py")

    # C.2 absence law — no --authority preimage is NONZERO with the one stdout token.
    proc = _run_tool_result("verify_binding_bundle.py")
    if proc.returncode == 0 or proc.stdout.strip() != "UNAVAILABLE_AUTHORITY":
        raise AssertionError(
            "verify_binding_bundle without --authority must refuse UNAVAILABLE_AUTHORITY "
            f"(exit {proc.returncode}; stdout {proc.stdout!r})"
        )

    # Part A §1.1 / C.3 envelope walk — valid inputs validate, invalid inputs quarantine.
    from triad_origin import e01_interface as e01

    good_bar = {
        "bar_identity": "e2e-bar-1", "metadata_revision": "r1",
        "open_ticks": 10, "high_ticks": 12, "low_ticks": 9, "close_ticks": 11,
        "base_volume": 5, "quote_volume": 55, "trade_count": 3,
    }
    validated = e01.require_valid_bar(good_bar)
    assert type(validated).__name__ == "ValidatedBar"
    try:
        e01.require_valid_bar({**good_bar, "low_ticks": 13})  # low > min(open, close)
    except e01.QuarantineInvalidBar:
        pass
    else:
        raise AssertionError("an invalid-geometry bar reached ValidatedBar")
    trade = {"trade_id": "t-1", "revision": "r1", "event_time_us": 1_000, "aggressor_side": "BUY"}
    e01.validate_trade(trade)
    try:
        e01.validate_trade({k: v for k, v in trade.items() if k != "aggressor_side"})
    except e01.QuarantineInvalidTrade:
        pass
    else:
        raise AssertionError("a trade without an aggressor flag validated")
    book = {
        "sequence": 7, "event_time_us": 1_000,
        "best_bid_price_ticks": 100, "best_bid_qty_steps": 5,
        "best_ask_price_ticks": 101, "best_ask_qty_steps": 4,
    }
    e01.validate_book_update(book, prior_seq=6, now_us=2_000, freshness_bound_us=10_000)
    try:
        crossed = {**book, "best_bid_price_ticks": 102}
        e01.validate_book_update(crossed, prior_seq=6, now_us=2_000, freshness_bound_us=10_000)
    except e01.QuarantineInvalidBookUpdate:
        pass
    else:
        raise AssertionError("a crossed book validated")

    # C.1 acceptance law — a fabricated sealed shape refuses at require_bundle (content law),
    # long before any formula; type identity buys nothing.
    from triad_origin import bindings, transition

    forged = {
        "schema_version": "sealed-bundle.v2",
        "scope": {"repository": "TriadOrigin", "environment": "OFF"},
        "rows": [{"binding_id": "B-XXX", "parameter_id": "PAR-000", "formula_id": "F00",
                  "semantic_slot": "forged", "declared_value": 1, "status": "ACTIVE"}],
        "canonical_root_digest": "0" * 64,
        "trust_registry_digest": "0" * 64,
        "signer_set": [], "signatures": [],
        "valid_from": 0, "valid_to": 2**62,
        "formula_coverage": {f"F{i:02d}": "ACTIVE" for i in range(24)},
        "row_preimage_digests": [],
    }
    ctx = bindings.VerificationContext(
        trust={}, trust_registry_bytes=b"{}", now_us=1,
        process_scope={"repository": "TriadOrigin", "environment": "OFF"},
        verify_fn=None, expected_digest_pin=None,
    )
    try:
        transition.require_bundle(forged, "PAR-000", formula_id="F00", ctx=ctx)
    except (bindings.SealedBundleRejected, bindings.CapabilityForgeryError):
        pass
    else:
        raise AssertionError("a forged sealed bundle reached acceptance")


_FORGE_CACHE: dict = {}


def _capability_forge():
    """SELF_TEST capability forge shared by the milestone formula stages.

    Mints REAL Ed25519 keys and drives the REAL C.1 acceptance path (build/sign →
    ``require_bundle``). The keypair and every ACTIVE-flipped registry row are SELF_TEST fixture
    material — walk scaffolding, never authority evidence. One forge per process: the trust pin
    is set-once, so every formula stage shares the same pinned trust registry.
    """
    if _FORGE_CACHE:
        return _FORGE_CACHE["forge"]
    import dataclasses
    import json as _json

    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey, Ed25519PublicKey)

    from triad_origin import bindings
    from triad_origin.canonical import canonical_json, sha256_hex

    kid = "k-e2e-selftest"
    private = Ed25519PrivateKey.generate()
    pub_hex = private.public_key().public_bytes_raw().hex()
    trust = {kid: {"key_id": kid, "identity": "e2e-selftest@triad-origin",
                   "role": "AUTHORITY_OWNER", "algorithm": "ed25519",
                   "public_key_hex": pub_hex, "revoked": False}}
    trust_bytes = _json.dumps(trust, sort_keys=True).encode("utf-8")
    trust_digest = sha256_hex(trust_bytes)
    bindings.pin_trust_registry_digest(trust_digest)

    def _verify(public_key_hex: str, message: bytes, signature_hex: str) -> bool:
        try:
            key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
            key.verify(bytes.fromhex(signature_hex), message)
            return True
        except Exception:
            return False

    ctx = bindings.VerificationContext(
        trust=trust, trust_registry_bytes=trust_bytes, now_us=2_000_000,
        process_scope={"repository": "TriadOrigin", "environment": "OFF"},
        verify_fn=_verify)

    def _sign(unsigned):
        signing = bindings.sealed_bundle_signing_bytes(
            canonical_root_digest=unsigned.canonical_root_digest, scope=unsigned.scope,
            valid_from=unsigned.valid_from, valid_to=unsigned.valid_to)
        return dataclasses.replace(unsigned, signatures=[
            {"key_id": kid, "signature_hex": private.sign(signing).hex()}])

    def genuine_bundle():
        registry = bindings.load_registry()
        unsigned = bindings.build_sealed_bundle(
            registry, repository="TriadOrigin", environment="OFF",
            valid_from=1_000_000, valid_to=9_000_000,
            trust_registry_digest=trust_digest, signer_set=[kid])
        return _sign(unsigned)

    def fixture_bundle(edit_rows):
        """A signed bundle over the registry with SELF_TEST row surgery applied.

        ``edit_rows`` maps binding_id -> field-update dict; edited rows are re-digested and the
        touched formulas flipped ACTIVE in coverage. Fixture surgery, never a ratification.
        """
        registry = bindings.load_registry()
        rows = [dict(r) for r in registry.rows()]
        coverage = dict(bindings.derive_formula_coverage(registry))
        for row in rows:
            update = edit_rows.get(row["binding_id"])
            if update is None:
                continue
            row.update(update)
            row["status"] = "ACTIVE"
            coverage[row["formula_id"]] = "ACTIVE"
            unsigned_row = {k: v for k, v in row.items() if k != "binding_digest"}
            row["binding_digest"] = sha256_hex(canonical_json(unsigned_row))
        root = bindings.canonical_rows_digest(rows)
        unsigned = bindings.SealedParameterBundle(
            schema_version=bindings.SEALED_SCHEMA_VERSION,
            scope={"repository": "TriadOrigin", "environment": "OFF"},
            rows=rows,
            canonical_root_digest=root,
            trust_registry_digest=trust_digest,
            signer_set=[kid],
            signatures=[],
            valid_from=1_000_000,
            valid_to=9_000_000,
            formula_coverage=coverage,
            row_preimage_digests=sorted(sha256_hex(canonical_json(r)) for r in rows),
        )
        return _sign(unsigned)

    forge = {"ctx": ctx, "genuine_bundle": genuine_bundle, "fixture_bundle": fixture_bundle}
    _FORGE_CACHE["forge"] = forge
    return forge


@stage("b03c_structure_goldens",
       "B03C: F03 v2 ambiguous-bar law + F04 STRICT_UNIQUE erratum + F09 v2 first-terminal "
       "break + GV-F05-01 — capability-sealed walks; the genuine registry stays honest-dark")
def b03c_structure_goldens() -> None:
    from triad_origin import bindings, features, transition
    from triad_origin import e01_interface as e01
    from triad_origin.structures import break_v2
    from triad_origin.structures import swing_dc_v2 as sdc
    from triad_origin.structures import typed_level_registry as tlr

    forge = _capability_forge()
    ctx = forge["ctx"]

    # 0) HONEST-DARK LAW: on the GENUINE registry, F03's PAR-036 row (FPB-0011) is not ratified —
    #    the capability can never mint, so the v2 formula stays dark by construction.
    try:
        transition.require_bundle(
            forge["genuine_bundle"](), sdc.PARAMETER_DC_REVERSAL, formula_id="F03", ctx=ctx)
    except bindings.SealedBundleRejected:
        pass
    else:
        raise AssertionError("PAR-036 minted from the genuine (unratified) registry")

    # 1) R-F03 walk under a SELF_TEST-ratified transport value: the ambiguous bar abstains
    #    (ABSTAIN_EXTEND_WINS) and the NEXT bar confirms at the NEW extreme's threshold.
    #    SENTINEL COLLISION (documented in the F03/F09 batteries): the declared PAR-036 rule
    #    byte-string contains '*', which C.1 acceptance treats as an unresolved sentinel — so a
    #    sentinel-free stand-in is minted through the REAL acceptance path and the verified
    #    handle's value is then swapped to the declared rule (construction is unrestricted by
    #    the C.1 law; ACCEPTANCE is what is guarded, and it ran in full).
    import dataclasses as _dc

    from triad_origin.structures import common as _common

    transport = "TEST-RATIFIED-TRANSPORT max(5,ceil(ATR14_ticks 1/4)) (sentinel-free)"
    f03_bundle = forge["fixture_bundle"]({
        "FPB-0011": {"lifecycle_status": "ACTIVE", "cardinality": "EXACTLY_ONE",
                     "migration_state": "NOT_APPLICABLE", "declared_value": transport,
                     "semantic_slot": "dc_reversal_delta_ticks_E2E",
                     "condition": "E2E SELF_TEST stand-in for the PAR-036 ceremony"},
    })
    minted = transition.require_bundle(
        f03_bundle, sdc.PARAMETER_DC_REVERSAL, formula_id="F03", ctx=ctx)
    f03_caps = {sdc.PARAMETER_DC_REVERSAL: _dc.replace(
        minted, value=_common.DECLARED_DC_REVERSAL)}

    def swing_bar(identity, high, low):
        return e01.require_valid_bar({
            "bar_identity": identity, "metadata_revision": "r1",
            "open_ticks": low, "high_ticks": high, "low_ticks": low, "close_ticks": high,
            "base_volume": 1, "quote_volume": 1, "trade_count": 1,
        })

    st = sdc.initial_state()
    events: list = []
    for identity, high, low in (
        ("b0", 1000, 998), ("b1", 1004, 998),   # seed + up leg
        ("b2", 1010, 998),                        # ambiguous: extends AND crosses old threshold
        ("b3", 1006, 1005),                       # 1010 - 1005 == 5 == delta: NEW threshold
    ):
        result = sdc.evaluate(f03_caps, swing_bar(identity, high, low), st, atr14_ticks=20)
        events.extend(result.events)
        st = result.state
    ambiguous = [e for e in events
                 if e.get("reason_code") == sdc.AMBIGUOUS_BAR_ABSTENTION]
    assert len(ambiguous) == 1 and ambiguous[0]["refs"]["bar_identity"] == "b2", \
        "the ambiguous bar must abstain exactly once (ABSTAIN_EXTEND_WINS)"
    swings = [e for e in events if e.get("event_kind") == tlr.TYPED_LEVEL]
    assert swings and swings[-1]["level_ticks"] == 1010, \
        f"the extension must win — expected the 1010 swing, got {swings!r}"
    assert all(e["confirmed_by_bar_identity"] != "b2" for e in swings), \
        "nothing may be confirmed BY the ambiguous bar itself"

    # 2) R-F04 erratum: STRICT_UNIQUE is the tie law — a strict pivot publishes on the second
    #    right bar; a right tie rejects the candidate entirely.
    def f04_bar(index, high):
        return {"event_id": f"b{index}", "kind": "BAR",
                "payload": {"high_ticks": high, "low_ticks": high - 7, "bar_seq": index}}

    f04_params = {tlr.PARAM_FRACTAL_LEFT: 2, tlr.PARAM_FRACTAL_RIGHT: 2}
    strict = transition.run(
        tlr.FractalPivot(), [f04_bar(i, h) for i, h in enumerate((8, 9, 12, 11, 10))],
        f04_params)
    published = [e for e in strict.events if e.get("event_kind") == tlr.TYPED_LEVEL]
    assert [e["level_ticks"] for e in published] == [12], "GV-006 strict pivot must publish"
    tie = transition.run(
        tlr.FractalPivot(), [f04_bar(i, h) for i, h in enumerate((8, 9, 12, 11, 12))],
        f04_params)
    assert not [e for e in tie.events if e.get("event_kind") == tlr.TYPED_LEVEL], \
        "a right tie must reject under STRICT_UNIQUE"

    # 3) R-F09 walk: an armed level, one qualifying close -> BREAK_OCCURRENCE (GENERIC_BREAK,
    #    first-terminal); a second qualifying close -> DUPLICATE_BREAK_IGNORED, never a second
    #    occurrence. Acceptance demands EVERY live F09 row ACTIVE, so the second F09 row
    #    (FPB-0092) is fixture-repurposed as the LEVEL_TTL_BARS row (the v2 battery's surgery) —
    #    without a ratified TTL capability the machine lawfully abstains on every observation.
    f09_bundle = forge["fixture_bundle"]({
        "FPB-0018": {"declared_value": 2, "semantic_slot": "E2E:F09.break_buffer_ticks"},
        "FPB-0092": {"parameter_id": break_v2.PARAM_LEVEL_TTL,
                     "parameter_name": break_v2.PARAM_LEVEL_TTL,
                     "semantic_slot": "E2E:F09.level_ttl_bars", "declared_value": 500},
    })
    f09_caps = {
        break_v2.PARAM_BREAK_BUFFER: transition.require_bundle(
            f09_bundle, break_v2.PARAM_BREAK_BUFFER, formula_id="F09", ctx=ctx),
        break_v2.PARAM_LEVEL_TTL: transition.require_bundle(
            f09_bundle, break_v2.PARAM_LEVEL_TTL, formula_id="F09", ctx=ctx),
    }

    def f09_bar(eid, close, ordinal):
        bucket = 1_000_000 + ordinal * 60_000_000
        return break_v2.BarObservation(
            bar=e01.require_valid_bar({
                "bar_identity": f"bar:{eid}", "metadata_revision": "rev-1",
                "open_ticks": close - 1, "high_ticks": close + 1, "low_ticks": close - 2,
                "close_ticks": close, "base_volume": 1, "quote_volume": 1, "trade_count": 1,
            }),
            bucket_start_us=bucket,
            availability_time_us=bucket + 60_000_000 + 2_000_000,
            source_sequence=100 + ordinal,
            bar_ordinal=ordinal,
            atr14_ticks=20,
            source_event_id=eid,
        )

    registration = break_v2.LevelRegistration(
        level_id="L1", level_ticks=1000, direction="LONG",
        availability_time_us=1_000_000, formation_bar_ordinal=0,
        defining_swing_id="SW1", swing_revision=0, source_event_id="lvl-1")
    walk = break_v2.run_break_v2(
        f09_caps, [registration, f09_bar("j1", 1003, 1), f09_bar("j2", 1004, 2)])
    occurrences = [e for e in walk.events
                   if e.get("event_kind") == break_v2.BREAK_OCCURRENCE]
    duplicates = [e for e in walk.events
                  if e.get("event_kind") == break_v2.DUPLICATE_BREAK_IGNORED]
    assert len(occurrences) == 1, f"exactly one first-terminal break, got {len(occurrences)}"
    assert occurrences[0]["classification"] == break_v2.CLASSIFICATION_GENERIC
    assert len(duplicates) == 1, "the second qualifying close must be DUPLICATE_BREAK_IGNORED"

    # 4) GV-F05-01 (Part D §D.5): N=3, highs [10,12,11] -> upper 12; lows [9,9,10] -> lower 9;
    #    the current bar's high 15 excluded by construction.
    def f05_bar(index, o, h, low, c):
        return {"event_id": f"gv_f05_{index}", "payload": {
            "state_kind": "BAR", "bar_finalization_state": "FINALIZED",
            "watermark_complete": True, "validity": "READY", "bar_index": index,
            "bar_open_time_us": index * 60_000_000,
            "bar_close_time_us": (index + 1) * 60_000_000,
            "open_ticks": o, "high_ticks": h, "low_ticks": low, "close_ticks": c,
        }}

    gv = transition.run(features.RollingExtreme(), [
        f05_bar(0, 10, 10, 9, 9), f05_bar(1, 10, 12, 9, 11),
        f05_bar(2, 10, 11, 10, 10), f05_bar(3, 12, 15, 12, 14),
    ], {"window": 3})
    feature = gv.events[3]
    assert feature["event_kind"] == "FEATURE" and feature["upper_ticks"] == 12 \
        and feature["lower_ticks"] == 9, f"GV-F05-01 numbers wrong: {feature!r}"
    assert feature["dependency_range"] == {"first_bar_index": 0, "last_bar_index": 2}


@stage("b04c_flow_goldens",
       "B04C: F15 flow.tfi.window.v2 GV-013 unit pair (+2/5 vs +1/13 — the unit-bug trap) + "
       "F16 flow.ofi.best.v2 GV-F16-01 (OFI +7) with the normalized identity default-OFF (it "
       "never emits) — capability-sealed on the repaired v2 surfaces")
def b04c_flow_goldens() -> None:
    from triad_origin import transition
    from triad_origin.structures import flow_atoms_v2 as fv2
    from triad_origin.structures.flow_atoms_v2 import (
        BookUpdateObservation, TradeObservation, WindowClose, run_f15, run_f16)
    from triad_origin.e01_interface import validate_trade

    forge = _capability_forge()
    ctx = forge["ctx"]

    # F15/F16 acceptance requires EVERY live row of the requesting formula ACTIVE, so the full
    # row set is flipped (empty edit == flip-ACTIVE only); the three/four value rows carry their
    # SELF_TEST declared values. The genuine registry leaves these rows BLOCKED (honest-dark).
    f15_edits = {"FPB-0026": {"declared_value": 100}, "FPB-0027": {"declared_value": 2000},
                 "FPB-0028": {"declared_value": 1}, "FPB-0029": {}, "FPB-0077": {}}
    f15_bundle = forge["fixture_bundle"](f15_edits)
    f15_caps = {
        fv2.PARAM_TFI_WINDOW_TRADES: transition.require_bundle(
            f15_bundle, "PAR-052", formula_id="F15", ctx=ctx),
        fv2.PARAM_TFI_WINDOW_MAX_AGE: transition.require_bundle(
            f15_bundle, "PAR-053", formula_id="F15", ctx=ctx),
        fv2.PARAM_TFI_MIN_TRADES: transition.require_bundle(
            f15_bundle, "PAR-054", formula_id="F15", ctx=ctx),
    }

    def tobs(tid, side, event_time, price, qty):
        return TradeObservation(
            trade=validate_trade({"trade_id": tid, "revision": "rev-1",
                                  "event_time_us": event_time, "aggressor_side": side}),
            venue="BINANCE", instrument="BTCUSDT", price_ticks=price, qty_steps=qty,
            metadata_revision="m1", source_event_id=tid)

    def wclose():
        return WindowClose(w_start=0, w_end=1000, expected_trades=2, watermark_us=1000,
                           source_event_id="wc")

    def tfi_of(run):
        feats = [e for e in run.events
                 if e.get("formula_version") == fv2.F15_FORMULA_VERSION
                 and e.get("event_kind") == "FEATURE"]
        assert len(feats) == 1, f"expected one F15 feature, got {feats!r}"
        return feats[0]

    # GV-013 (a) equal-price: buy atoms 70, sell atoms 30 -> TFI +2/5 reduced.
    a = tfi_of(run_f15(f15_caps, [
        tobs("b", "BUY", 100, 1, 70), tobs("s", "SELL", 200, 1, 30), wclose()]))
    assert a["tfi"] == [2, 5] and a["buy_atoms"] == 70 and a["sell_atoms"] == 30, \
        f"GV-013(a) wrong: {a!r}"
    # GV-013 (b) unequal-price: 70 steps @ 100 ticks = 7000 vs 30 steps @ 200 ticks = 6000
    #   -> TFI +1/13 (a base-quantity computation would claim +2/5 — the unit-bug trap).
    b = tfi_of(run_f15(f15_caps, [
        tobs("b", "BUY", 100, 100, 70), tobs("s", "SELL", 200, 200, 30), wclose()]))
    assert b["tfi"] == [1, 13] and b["buy_atoms"] == 7000 and b["sell_atoms"] == 6000, \
        f"GV-013(b) unit-bug trap wrong: {b!r}"

    # F16 GV-F16-01: OFI = +7; the normalized identity is a SEPARATE identity behind a
    # default-OFF lever — with the lever OFF it must NEVER emit.
    f16_edits = {"FPB-0030": {}, "FPB-0032": {"declared_value": 100},
                 "FPB-0033": {"declared_value": 1000}, "FPB-0034": {"declared_value": 3},
                 "FPB-0078": {"parameter_id": fv2.PARAM_OFI_NORM_ACTIVATION,
                              "parameter_name": fv2.PARAM_OFI_NORM_ACTIVATION,
                              "semantic_slot": "E2E:F16.ofi_normalized_variant_activation",
                              "declared_value": fv2.NORM_ACTIVATION_OFF}}
    f16_bundle = forge["fixture_bundle"](f16_edits)
    f16_caps = {
        fv2.PARAM_OFI_WINDOW_UPDATES: transition.require_bundle(
            f16_bundle, "PAR-056", formula_id="F16", ctx=ctx),
        fv2.PARAM_OFI_WINDOW_MAX_AGE: transition.require_bundle(
            f16_bundle, "PAR-057", formula_id="F16", ctx=ctx),
        fv2.PARAM_OFI_MIN_UPDATES: transition.require_bundle(
            f16_bundle, "PAR-058", formula_id="F16", ctx=ctx),
    }

    def bupd(seq, pb, qb, pa, qa):
        return BookUpdateObservation(
            sequence=seq, event_time_us=seq * 10, eval_time_us=seq * 10,
            best_bid_price_ticks=pb, best_bid_qty_steps=qb, best_ask_price_ticks=pa,
            best_ask_qty_steps=qa, watermark_complete=True, source_event_id=f"u{seq}")

    ofi_run = run_f16(f16_caps, [
        bupd(0, 100, 5, 101, 7), bupd(1, 100, 8, 101, 7),   # e1 = +3
        bupd(2, 99, 4, 101, 6), bupd(3, 99, 9, 102, 6)])    # e2 = -7, e3 = +11
    ofi_feats = [e for e in ofi_run.events
                 if e.get("formula_version") == fv2.F16_FORMULA_VERSION
                 and e.get("event_kind") == "FEATURE"]
    assert len(ofi_feats) == 1 and ofi_feats[0]["ofi_value"] == 7 \
        and ofi_feats[0]["window_size"] == 3, f"GV-F16-01 OFI wrong: {ofi_feats!r}"
    # The OFF-lever law: the normalized identity never emits.
    norm_feats = [e for e in ofi_run.events
                  if e.get("formula_version") == fv2.F16_NORM_FORMULA_VERSION]
    assert not norm_feats, \
        f"the normalized identity emitted with the lever OFF: {norm_feats!r}"


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
