"""Hash-chained ledger integrity, single-writer lock, restart recovery, and checkpoints."""

from __future__ import annotations

import pytest

from triad_origin import checkpoint as cp
from triad_origin import ledger as L


def test_append_and_verify_chain(tmp_path):
    path = tmp_path / "topic.ledger"
    with L.LedgerWriter(path) as w:
        w.append(b"one")
        w.append(b"two")
        w.append(b"three")
    recs = list(L.read_records(path))
    assert [r.payload for r in recs] == [b"one", b"two", b"three"]
    assert [r.seq for r in recs] == [0, 1, 2]
    assert L.verify(path) == 3


def test_tamper_is_detected(tmp_path):
    path = tmp_path / "topic.ledger"
    with L.LedgerWriter(path) as w:
        w.append(b"alpha")
        w.append(b"bravo")
    data = bytearray(path.read_bytes())
    # Flip a byte inside the first payload; the chain must no longer verify.
    idx = data.index(b"alpha")
    data[idx] ^= 0x40
    path.write_bytes(bytes(data))
    with pytest.raises(L.LedgerCorruption):
        L.verify(path)


def test_truncation_is_detected(tmp_path):
    path = tmp_path / "topic.ledger"
    with L.LedgerWriter(path) as w:
        w.append(b"payload-payload")
    data = path.read_bytes()[:-4]  # chop the tail (torn frame)
    path.write_bytes(data)
    with pytest.raises(L.LedgerCorruption):
        L.verify(path)


def test_single_writer_lock(tmp_path):
    path = tmp_path / "topic.ledger"
    w1 = L.LedgerWriter(path)
    w1.open()
    try:
        with pytest.raises(L.LedgerLocked):
            L.LedgerWriter(path).open()
    finally:
        w1.close()


def test_restart_recovers_chain_no_dup_no_loss(tmp_path):
    path = tmp_path / "topic.ledger"
    with L.LedgerWriter(path) as w:
        w.append(b"one")
        w.append(b"two")
    # A fresh writer recovers prev-chain + seq and continues the same chain.
    with L.LedgerWriter(path) as w:
        rec = w.append(b"three")
        assert rec.seq == 2
    recs = list(L.read_records(path))
    assert [r.payload for r in recs] == [b"one", b"two", b"three"]
    assert L.verify(path) == 3


def test_checkpoint_roundtrip_and_checksum(tmp_path):
    path = tmp_path / "part.checkpoint"
    checkpoint = cp.Checkpoint(partition="BINANCE_USDM|BTCUSDT|15m",
                              state={"leg": "UP", "extreme": 621234}, input_offset=41)
    checksum = cp.save(path, checkpoint)
    loaded = cp.load(path)
    assert loaded.state == checkpoint.state
    assert loaded.input_offset == 41
    assert loaded.state_checksum == checksum


def test_checkpoint_tamper_fails_closed(tmp_path):
    path = tmp_path / "part.checkpoint"
    cp.save(path, cp.Checkpoint(partition="p", state={"x": 1}, input_offset=0))
    text = path.read_text().replace('"x":1', '"x":2')
    path.write_text(text)
    with pytest.raises(cp.CheckpointError):
        cp.load(path)
