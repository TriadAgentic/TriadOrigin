"""B02 kernel-hardening falsification tests.

CTRL-B02-001: external durable anchor — tail deletion/replacement and whole-file replacement of an
internally-consistent ledger must be detected; cold/warm restore parity holds.
CTRL-B02-002: the closed per-scope fence state (lease tokens + revocations + producer epochs) is
sealed into checkpoint v3, restored before consumption, and a lower token/epoch is still rejected
across a restart.
RC4 timing law: the 17 bounds are drift-locked to the vendored RC4 bundle; staleness is a pure
predicate.
F00: exact integer tick conversion golden vectors (GV-001).
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import anchor, checkpoint, ingress, instrument_math, ledger  # noqa: E402
from triad_origin import lease, timings  # noqa: E402
from triad_origin.canonical import canonical_json, sha256_hex  # noqa: E402


def _write_ledger(path, payloads):
    with ledger.LedgerWriter(path) as writer:
        for payload in payloads:
            writer.append(payload)


# --- CTRL-B02-001: the external anchor -----------------------------------------------------------
class TestLedgerAnchor:
    def test_anchor_and_verify_pass(self, tmp_path):
        lpath = tmp_path / "walk.ledger"
        apath = tmp_path / "external" / "walk.anchor"
        _write_ledger(lpath, [b"a", b"b", b"c"])
        entry = anchor.anchor_ledger(lpath, apath)
        assert entry["record_count"] == 3
        receipt = anchor.verify_anchored(lpath, apath)
        assert receipt["result"] == "PASS"
        assert receipt["ledger_record_count"] == 3

    def test_growth_after_anchor_still_verifies(self, tmp_path):
        lpath = tmp_path / "walk.ledger"
        apath = tmp_path / "ext" / "walk.anchor"
        _write_ledger(lpath, [b"a", b"b"])
        anchor.anchor_ledger(lpath, apath)
        with ledger.LedgerWriter(lpath) as writer:
            writer.append(b"c")
        receipt = anchor.verify_anchored(lpath, apath)
        assert receipt["ledger_record_count"] == 3

    def test_tail_deletion_detected(self, tmp_path):
        lpath = tmp_path / "walk.ledger"
        apath = tmp_path / "ext" / "walk.anchor"
        _write_ledger(lpath, [b"a", b"b", b"c"])
        anchor.anchor_ledger(lpath, apath)
        # Rebuild the ledger from its own first two records — internally consistent, shorter.
        records = list(ledger.read_records(lpath))
        rebuilt = tmp_path / "rebuilt.ledger"
        _write_ledger(rebuilt, [r.payload for r in records[:2]])
        rebuilt.replace(lpath)
        assert ledger.verify(lpath) == 2  # self-verification is blind to the deletion
        with pytest.raises(anchor.AnchorError, match="ANCHOR_TAIL_DELETED"):
            anchor.verify_anchored(lpath, apath)

    def test_tail_replacement_detected(self, tmp_path):
        lpath = tmp_path / "walk.ledger"
        apath = tmp_path / "ext" / "walk.anchor"
        _write_ledger(lpath, [b"a", b"b", b"c"])
        anchor.anchor_ledger(lpath, apath)
        records = list(ledger.read_records(lpath))
        rebuilt = tmp_path / "rebuilt.ledger"
        # Same prefix, substituted final record, validly re-chained; same record count.
        _write_ledger(rebuilt, [records[0].payload, records[1].payload, b"FORGED"])
        rebuilt.replace(lpath)
        assert ledger.verify(lpath) == 3  # self-verification passes: the chain is consistent
        with pytest.raises(anchor.AnchorError, match="ANCHOR_TAIL_REPLACED"):
            anchor.verify_anchored(lpath, apath)

    def test_whole_file_replacement_detected(self, tmp_path):
        lpath = tmp_path / "walk.ledger"
        apath = tmp_path / "ext" / "walk.anchor"
        _write_ledger(lpath, [b"a"])
        anchor.anchor_ledger(lpath, apath)
        lpath.unlink()
        _write_ledger(lpath, [b"x", b"y"])
        with pytest.raises(anchor.AnchorError, match="ANCHOR_FILE_REPLACED"):
            anchor.verify_anchored(lpath, apath)

    def test_anchor_journal_tamper_detected(self, tmp_path):
        lpath = tmp_path / "walk.ledger"
        apath = tmp_path / "ext" / "walk.anchor"
        _write_ledger(lpath, [b"a", b"b"])
        anchor.anchor_ledger(lpath, apath)
        text = apath.read_text()
        apath.write_text(text.replace('"record_count": 2', '"record_count": 1'))
        with pytest.raises(anchor.AnchorError, match="digest mismatch"):
            anchor.verify_anchored(lpath, apath)

    def test_same_path_anchor_refused(self, tmp_path):
        lpath = tmp_path / "walk.ledger"
        _write_ledger(lpath, [b"a"])
        with pytest.raises(anchor.AnchorError, match="distinct durable location"):
            anchor.anchor_ledger(lpath, lpath)

    def test_no_anchor_entries_fails_closed(self, tmp_path):
        lpath = tmp_path / "walk.ledger"
        _write_ledger(lpath, [b"a"])
        with pytest.raises(anchor.AnchorError, match="no anchor entries"):
            anchor.verify_anchored(lpath, tmp_path / "missing.anchor")


# --- CTRL-B02-002: fence state across restart ----------------------------------------------------
def _active_lease(scope: str, token: int) -> lease.Lease:
    return lease.Lease(
        lease_id=f"l-{token}", scope=scope, producer_service="svc",
        producer_instance_id="inst", fencing_token=token,
        activation_manifest_id="am-1", state=lease.LeaseState.ACTIVE)


class TestFenceRestore:
    def test_lower_token_rejected_across_restart(self, tmp_path):
        fence = lease.ConsumerFence()
        assert fence.accept(_active_lease("topic/a", 7))
        state = fence.export_state()

        restarted = lease.ConsumerFence()
        restarted.restore_state(state)
        # The falsification CTRL-B02-002 names: a guessed lower token after restart.
        assert not restarted.accept(_active_lease("topic/a", 6))
        assert not restarted.accept(_active_lease("topic/a", 7))  # equal is not higher
        assert not restarted.accepts_write("topic/a", 6)
        assert restarted.accepts_write("topic/a", 7)
        assert restarted.accept(_active_lease("topic/a", 8))

    def test_revocation_survives_restart(self):
        fence = lease.ConsumerFence()
        assert fence.accept(_active_lease("topic/a", 3))
        fence.revoke("topic/a")
        restarted = lease.ConsumerFence()
        restarted.restore_state(fence.export_state())
        assert not restarted.accept(_active_lease("topic/a", 99))
        assert not restarted.accepts_write("topic/a", 3)

    def test_restore_requires_fresh_fence(self):
        fence = lease.ConsumerFence()
        assert fence.accept(_active_lease("topic/a", 1))
        with pytest.raises(ValueError, match="fresh fence"):
            fence.restore_state({"highest": {}, "revoked": []})

    @pytest.mark.parametrize("bad", [
        {"highest": {}},                                   # missing key
        {"highest": {}, "revoked": [], "extra": 1},        # unknown key
        {"highest": {"s": 0}, "revoked": []},              # zero token
        {"highest": {"s": True}, "revoked": []},           # bool token
        {"highest": {"": 1}, "revoked": []},               # empty scope
        {"highest": {}, "revoked": [""]},                  # empty revoked scope
    ])
    def test_malformed_fence_state_rejected(self, bad):
        with pytest.raises(ValueError):
            lease.ConsumerFence().restore_state(bad)

    def test_epoch_high_water_restored(self):
        gate = ingress.ContractIngress(boundary="e02-input")
        valid = json.loads(
            (ROOT / "contracts/golden/triad.edge_candidate.v2/valid.json").read_text())
        assert isinstance(gate.ingest(valid, fence_scope="s"), ingress.Accepted)
        epochs = gate.export_epochs()
        assert epochs == {"s": 42}

        restarted = ingress.ContractIngress(boundary="e02-input")
        restarted.restore_epochs(epochs)
        stale = json.loads(json.dumps(valid))
        stale["producer_epoch"] = "41"
        outcome = restarted.ingest(stale, fence_scope="s")
        assert isinstance(outcome, ingress.Quarantined)

    def test_epoch_restore_requires_fresh_ingress(self):
        gate = ingress.ContractIngress(boundary="e02-input")
        valid = json.loads(
            (ROOT / "contracts/golden/triad.edge_candidate.v2/valid.json").read_text())
        gate.ingest(valid, fence_scope="s")
        with pytest.raises(ValueError, match="fresh ingress"):
            gate.restore_epochs({"s": 42})


class TestCheckpointV3FenceState:
    def _checkpoint(self, fence_state=None):
        state = {"k": 1}
        kwargs = {}
        if fence_state is not None:
            kwargs["fence_state"] = fence_state
        return checkpoint.Checkpoint(
            partition="walk", state=state, input_segment="seg-0", input_offset=5,
            input_prefix_digest="a" * 64, last_domain_event_id="evt-5",
            highest_producer_epoch=3,
            projection_checksum=sha256_hex(canonical_json(state)),
            output_segment="out-0", output_offset=2, state_seq=-1,
            last_transition_id="genesis",
            digests={k: "c" * 64 for k in
                     ("build", "config", "contract", "parameter", "instrument")},
            **kwargs)

    def test_fence_state_round_trips(self, tmp_path):
        fence = lease.ConsumerFence()
        assert fence.accept(_active_lease("topic/a", 9))
        cp = self._checkpoint({"lease": fence.export_state(), "epoch": {"s": 4}})
        path = tmp_path / "cp.json"
        checkpoint.save(path, cp)
        loaded = checkpoint.load(path)
        assert loaded.fence_state["lease"]["highest"] == {"topic/a": 9}
        restored = lease.ConsumerFence()
        restored.restore_state(loaded.fence_state["lease"])
        assert not restored.accept(_active_lease("topic/a", 8))

    def test_fence_tamper_detected_at_load(self, tmp_path):
        cp = self._checkpoint({"lease": {"highest": {"t": 5}, "revoked": []}, "epoch": {}})
        path = tmp_path / "cp.json"
        checkpoint.save(path, cp)
        blob = json.loads(path.read_text())
        blob["fence_state"]["lease"]["highest"]["t"] = 4  # lower the sealed high-water
        path.write_text(json.dumps(blob, sort_keys=True, separators=(",", ":")))
        with pytest.raises(checkpoint.CheckpointError):
            checkpoint.load(path)

    def test_v2_checkpoint_requires_migration(self, tmp_path):
        cp = self._checkpoint()
        sealed = cp.sealed()
        blob = sealed.integrity_material()
        blob.pop("fence_state")
        blob["identity_schema_version"] = "origin.checkpoint.v2"
        blob["state_checksum"] = sha256_hex(canonical_json(blob))
        path = tmp_path / "cp.json"
        path.write_text(json.dumps(blob, sort_keys=True, separators=(",", ":")))
        with pytest.raises(checkpoint.CheckpointMigrationRequired):
            checkpoint.load(path)

    @pytest.mark.parametrize("bad", [
        {"lease": {"highest": {}}, "epoch": {}},               # missing revoked
        {"lease": {"highest": {}, "revoked": []}, "epoch": {}, "x": 1},  # unknown key
        {"lease": {"highest": {"s": 0}, "revoked": []}, "epoch": {}},    # zero token
        {"lease": {"highest": {}, "revoked": []}, "epoch": {"s": -1}},   # negative epoch
    ])
    def test_malformed_fence_state_refuses_seal(self, bad):
        with pytest.raises(checkpoint.CheckpointError):
            self._checkpoint(bad).sealed()


# --- cold/warm exactly-once parity ---------------------------------------------------------------
class TestColdWarmParity:
    def test_warm_restore_equals_cold_rebuild_and_never_reaccepts(self, tmp_path):
        from triad_origin import journal

        lpath = tmp_path / "input.ledger"
        apath = tmp_path / "ext" / "input.anchor"
        events = [{"n": i} for i in range(6)]
        _write_ledger(lpath, [canonical_json(e) for e in events])
        anchor.anchor_ledger(lpath, apath)

        def consume(records, base: journal.StateJournal, start_seq: int):
            state = base.project()
            for i, rec in enumerate(records):
                n = json.loads(rec.payload)["n"]
                new_state = dict(state)
                new_state[f"k{n}"] = n
                base.append(start_seq + i - 1 if False else base.seq, state, new_state,
                            f"env-{n}", ({"event": n},))
                state = new_state
            return base

        # Cold: consume everything from seq -1.
        cold = consume(list(ledger.read_records(lpath)), journal.StateJournal(partition="w"), 0)

        # Warm: consume a prefix, checkpoint (with anchor receipt digest), restart, resume.
        warm_a = consume(list(ledger.read_records(lpath))[:3],
                         journal.StateJournal(partition="w"), 0)
        receipt = anchor.verify_anchored(lpath, apath)
        cp = checkpoint.Checkpoint(
            partition="w", state=warm_a.project(), input_segment=str(lpath), input_offset=3,
            input_prefix_digest=sha256_hex(b"prefix"), last_domain_event_id="env-2",
            highest_producer_epoch=0,
            projection_checksum=sha256_hex(canonical_json(warm_a.project())),
            output_segment="out", output_offset=warm_a.seq, state_seq=warm_a.seq,
            last_transition_id=warm_a.records()[-1].transition_id,
            digests={"build": "c" * 64, "config": "c" * 64, "contract": "c" * 64,
                     "parameter": "c" * 64,
                     "instrument": sha256_hex(canonical_json(receipt))},
        )
        cpath = tmp_path / "cp.json"
        checkpoint.save(cpath, cp)

        loaded = checkpoint.load(cpath)
        anchor.verify_anchored(lpath, apath)  # restart re-verifies the anchor before consumption
        warm_b = journal.StateJournal(
            partition="w", _base_seq=loaded.state_seq,
            _base_transition_id=loaded.last_transition_id, _base_state=loaded.state)
        consume(list(ledger.read_records(lpath))[loaded.input_offset:], warm_b, 0)

        assert warm_b.project() == cold.project()
        assert warm_b.seq == cold.seq
        # Exactly-once: the resumed journal holds only the post-checkpoint transitions.
        assert len(warm_b.records()) == len(events) - loaded.input_offset


# --- RC4 timing law ------------------------------------------------------------------------------
class TestTimings:
    def test_drift_locked_to_rc4_bundle(self):
        bundle = json.loads((ROOT / "docs/control/rc4_control_bundle.json").read_text())
        assert dict(timings.TIMINGS_MS) == bundle["timings"]

    def test_unknown_bound_fails_closed(self):
        with pytest.raises(timings.TimingError):
            timings.timing_ms("made_up_bound_ms")

    def test_staleness_boundaries(self):
        bound = timings.timing_ms("lever_cache_max_age_ms")
        assert not timings.is_stale(bound, "lever_cache_max_age_ms")
        assert timings.is_stale(bound + 1, "lever_cache_max_age_ms")
        assert timings.is_stale(-1, "lever_cache_max_age_ms")  # clock inversion is never fresh
        with pytest.raises(timings.TimingError):
            timings.is_stale(True, "lever_cache_max_age_ms")


# --- F00 exact tick conversion (GV-001) ----------------------------------------------------------
class TestF00GoldenVectors:
    def test_gv001_buy_floor_sell_ceil(self):
        instrument = instrument_math.Instrument(
            canonical_instrument_id="BTCUSDT.binance-usdm", venue_model="binance-usdm.v1",
            tick_size="0.1", step_size="0.001", min_notional="5", revision="1")
        # GV-001: tick=0.1; raw=100.24 -> BUY(floor)=1002 (100.2); SELL(ceil)=1003 (100.3).
        assert instrument_math.price_to_ticks(
            instrument, "100.24", instrument_math.Rounding.DOWN) == 1002
        assert instrument_math.price_to_ticks(
            instrument, "100.24", instrument_math.Rounding.UP) == 1003
        # Boundary: raw=100.2 is exact; both sides stay 100.2.
        for mode in (instrument_math.Rounding.DOWN, instrument_math.Rounding.UP,
                     instrument_math.Rounding.EXACT):
            assert instrument_math.price_to_ticks(instrument, "100.2", mode) == 1002
        assert instrument_math.ticks_to_price(instrument, 1002) == "100.2"

    def test_off_grid_venue_fact_quarantines_exact(self):
        instrument = instrument_math.Instrument(
            canonical_instrument_id="BTCUSDT.binance-usdm", venue_model="binance-usdm.v1",
            tick_size="0.1", step_size="0.001", min_notional="5", revision="1")
        with pytest.raises(instrument_math.InstrumentError):
            instrument_math.price_to_ticks(instrument, "100.24", instrument_math.Rounding.EXACT)
