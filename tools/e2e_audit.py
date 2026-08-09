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


# ---------------------------------------------------------------- stage 7
@stage("capability_boundary", "DARK posture: no network/credential/order capability imports")
def capability_boundary() -> None:
    _run_tool("verify_no_forbidden_capabilities.py")


# ---------------------------------------------------------------- stage 8
@stage("build_ledger", "Build ledger regenerates byte-identical (partition is current)")
def build_ledger() -> None:
    _run_tool("build_ledger.py", "--verify")


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
