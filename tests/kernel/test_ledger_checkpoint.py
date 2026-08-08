"""Hash-chained ledger integrity, single-writer lock, restart recovery, and checkpoints."""

from __future__ import annotations

import json

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
    assert loaded.identity_schema_version == cp.CHECKPOINT_IDENTITY_VERSION


def test_legacy_v1_checkpoint_requires_explicit_cold_rebuild(tmp_path):
    path = tmp_path / "legacy.checkpoint"
    state = {"x": 1}
    # M2's v1 checksum authenticated state only. Its offset/digests cannot be trusted for resume.
    raw = {
        "partition": "p",
        "state": state,
        "input_offset": 7,
        "state_checksum": cp.sha256_hex(cp.canonical_json(state)),
        "digests": {"build": "legacy"},
        "identity_schema_version": cp.LEGACY_CHECKPOINT_IDENTITY_VERSION,
    }
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(cp.CheckpointMigrationRequired, match="cold rebuild"):
        cp.load(path)


def test_unknown_checkpoint_version_fails_closed(tmp_path):
    path = tmp_path / "future.checkpoint"
    cp.save(path, cp.Checkpoint(partition="p", state={"x": 1}, input_offset=7))
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["identity_schema_version"] = "origin.checkpoint.v999"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(cp.CheckpointError, match="unsupported checkpoint identity version"):
        cp.load(path)


def test_writer_refuses_legacy_or_unknown_checkpoint_version(tmp_path):
    checkpoint = cp.Checkpoint(
        partition="p",
        state={"x": 1},
        input_offset=7,
        identity_schema_version=cp.LEGACY_CHECKPOINT_IDENTITY_VERSION,
    )
    with pytest.raises(cp.CheckpointError, match="refusing to write unsupported"):
        cp.save(tmp_path / "legacy.checkpoint", checkpoint)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda checkpoint: setattr(checkpoint, "partition", ""),
        lambda checkpoint: setattr(checkpoint, "state", []),
        lambda checkpoint: setattr(checkpoint, "input_offset", "7"),
        lambda checkpoint: setattr(checkpoint, "input_offset", True),
        lambda checkpoint: setattr(checkpoint, "digests", {"build": ""}),
    ],
)
def test_writer_rejects_invalid_checkpoint_field_types(tmp_path, mutate):
    checkpoint = cp.Checkpoint(
        partition="p",
        state={"x": 1},
        input_offset=7,
        digests={"build": "known"},
    )
    mutate(checkpoint)
    with pytest.raises(cp.CheckpointError):
        cp.save(tmp_path / "invalid.checkpoint", checkpoint)


def test_loader_rejects_unknown_fields_and_noncanonical_checksum(tmp_path):
    path = tmp_path / "part.checkpoint"
    cp.save(path, cp.Checkpoint(partition="p", state={"x": 1}, input_offset=7))
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["unexpected"] = "field"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(cp.CheckpointError, match="unknown field"):
        cp.load(path)

    raw.pop("unexpected")
    raw["state_checksum"] = "A" * 64
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(cp.CheckpointError, match="lowercase SHA-256"):
        cp.load(path)


def test_checkpoint_tamper_fails_closed(tmp_path):
    path = tmp_path / "part.checkpoint"
    cp.save(path, cp.Checkpoint(partition="p", state={"x": 1}, input_offset=0))
    text = path.read_text().replace('"x":1', '"x":2')
    path.write_text(text)
    with pytest.raises(cp.CheckpointError):
        cp.load(path)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda raw: raw.__setitem__("partition", "other"),
        lambda raw: raw.__setitem__("input_offset", 999),
        lambda raw: raw.__setitem__("digests", {"build": "changed"}),
        lambda raw: raw.__setitem__("identity_schema_version", "origin.checkpoint.v999"),
    ],
)
def test_checkpoint_replay_metadata_tamper_fails_closed(tmp_path, mutate):
    path = tmp_path / "part.checkpoint"
    cp.save(
        path,
        cp.Checkpoint(
            partition="p",
            state={"x": 1},
            input_offset=7,
            digests={"build": "original"},
        ),
    )
    raw = json.loads(path.read_text(encoding="utf-8"))
    mutate(raw)
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(cp.CheckpointError):
        cp.load(path)


def test_checkpoint_missing_integrity_metadata_fails_closed(tmp_path):
    path = tmp_path / "part.checkpoint"
    cp.save(path, cp.Checkpoint(partition="p", state={"x": 1}, input_offset=7))
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw.pop("input_offset")
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(cp.CheckpointError):
        cp.load(path)
