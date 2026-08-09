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
