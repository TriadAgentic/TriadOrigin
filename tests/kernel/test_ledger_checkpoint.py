"""Hash-chained ledger integrity, single-writer lock, restart recovery, and checkpoints."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from triad_origin import checkpoint as cp
from triad_origin import ledger as L


DIGESTS = {
    name: cp.sha256_hex(name.encode("utf-8"))
    for name in sorted(cp.REQUIRED_DIGEST_KEYS)
}


def _checkpoint(
    *,
    partition="p",
    state=None,
    input_offset=7,
    digests=None,
    identity_schema_version=cp.CHECKPOINT_IDENTITY_VERSION,
):
    if state is None:
        state = {"x": 1}
    return cp.Checkpoint(
        partition=partition,
        state=state,
        input_segment="input-000001",
        input_offset=input_offset,
        input_prefix_digest=cp.sha256_hex(b"fixture-input-prefix"),
        last_domain_event_id=f"event-{input_offset}",
        highest_producer_epoch=1,
        projection_checksum=cp.sha256_hex(cp.canonical_json(state)),
        output_segment="output-000001",
        output_offset=input_offset,
        state_seq=input_offset,
        last_transition_id=f"stx_fixture_{input_offset}",
        digests=dict(DIGESTS if digests is None else digests),
        identity_schema_version=identity_schema_version,
    )


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


def test_single_writer_lock_covers_symlink_alias(tmp_path):
    path = tmp_path / "topic.ledger"
    alias = tmp_path / "alias.ledger"
    alias.symlink_to(path)
    writer = L.LedgerWriter(path)
    writer.open()
    try:
        with pytest.raises(L.LedgerLocked):
            L.LedgerWriter(alias).open()
    finally:
        writer.close()


def test_concurrent_appends_on_one_handle_are_serialized(tmp_path):
    path = tmp_path / "topic.ledger"
    with L.LedgerWriter(path) as writer:
        with ThreadPoolExecutor(max_workers=8) as pool:
            records = list(pool.map(lambda i: writer.append(f"r{i}".encode()), range(40)))
    assert sorted(record.seq for record in records) == list(range(40))
    assert L.verify(path) == 40


def test_durable_ledger_refuses_fsync_disable(tmp_path):
    with pytest.raises(L.LedgerError, match="cannot be disabled"):
        L.LedgerWriter(tmp_path / "topic.ledger", fsync=False)


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
    checkpoint = _checkpoint(
        partition="BINANCE_USDM|BTCUSDT|15m",
        state={"leg": "UP", "extreme": 621234},
        input_offset=41,
    )
    checksum = cp.save(path, checkpoint)
    loaded = cp.load(path)
    assert loaded.state == checkpoint.state
    assert loaded.input_offset == 41
    assert loaded.state_checksum == checksum
    assert loaded.identity_schema_version == cp.CHECKPOINT_IDENTITY_VERSION


def test_in_memory_seal_and_persisted_restore_have_identical_canonical_types(tmp_path):
    checkpoint = _checkpoint(partition="e\u0301", state={"shape": (1, 2)})
    sealed = checkpoint.sealed()
    path = tmp_path / "canonical.checkpoint"
    cp.save(path, checkpoint)
    loaded = cp.load(path)
    assert sealed.partition == loaded.partition == "é"
    assert sealed.state == loaded.state == {"shape": [1, 2]}
    assert sealed.state_checksum == loaded.state_checksum


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
        "identity_schema_version": cp.LEGACY_CHECKPOINT_IDENTITY_VERSIONS[0],
    }
    path.write_bytes(cp.canonical_json(raw))
    with pytest.raises(cp.CheckpointMigrationRequired, match="cold rebuild"):
        cp.load(path)


def test_unknown_checkpoint_version_fails_closed(tmp_path):
    path = tmp_path / "future.checkpoint"
    cp.save(path, _checkpoint())
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["identity_schema_version"] = "origin.checkpoint.v999"
    path.write_bytes(cp.canonical_json(raw))
    with pytest.raises(cp.CheckpointError, match="unsupported checkpoint identity version"):
        cp.load(path)


def test_writer_refuses_legacy_or_unknown_checkpoint_version(tmp_path):
    checkpoint = _checkpoint(
        identity_schema_version=cp.LEGACY_CHECKPOINT_IDENTITY_VERSIONS[0],
    )
    with pytest.raises(cp.CheckpointError, match="refusing to write unsupported"):
        cp.save(tmp_path / "legacy.checkpoint", checkpoint)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda checkpoint: setattr(checkpoint, "partition", ""),
        lambda checkpoint: setattr(checkpoint, "state", []),
        lambda checkpoint: setattr(checkpoint, "input_segment", ""),
        lambda checkpoint: setattr(checkpoint, "input_offset", "7"),
        lambda checkpoint: setattr(checkpoint, "input_offset", True),
        lambda checkpoint: setattr(checkpoint, "input_prefix_digest", "not-a-sha"),
        lambda checkpoint: setattr(checkpoint, "last_domain_event_id", ""),
        lambda checkpoint: setattr(checkpoint, "highest_producer_epoch", True),
        lambda checkpoint: setattr(checkpoint, "highest_producer_epoch", -1),
        lambda checkpoint: setattr(checkpoint, "output_segment", ""),
        lambda checkpoint: setattr(checkpoint, "output_offset", True),
        lambda checkpoint: setattr(checkpoint, "state_seq", True),
        lambda checkpoint: setattr(checkpoint, "last_transition_id", ""),
        lambda checkpoint: setattr(checkpoint, "digests", {"build": ""}),
    ],
)
def test_writer_rejects_invalid_checkpoint_field_types(tmp_path, mutate):
    checkpoint = _checkpoint()
    mutate(checkpoint)
    with pytest.raises(cp.CheckpointError):
        cp.save(tmp_path / "invalid.checkpoint", checkpoint)


@pytest.mark.parametrize(
    "digests",
    [
        {},
        {key: value for key, value in DIGESTS.items() if key != "parameter"},
        {**DIGESTS, "unexpected": "0" * 64},
        {**DIGESTS, "build": "not-a-sha"},
        {**DIGESTS, "build": "A" * 64},
    ],
)
def test_checkpoint_requires_closed_sha256_digest_set(tmp_path, digests):
    with pytest.raises(cp.CheckpointError, match="digest"):
        cp.save(tmp_path / "bad-digests.checkpoint", _checkpoint(digests=digests))


def test_checkpoint_projection_checksum_must_match_state(tmp_path):
    checkpoint = _checkpoint()
    checkpoint.projection_checksum = "0" * 64
    with pytest.raises(cp.CheckpointError, match="does not match state"):
        cp.save(tmp_path / "bad-projection.checkpoint", checkpoint)


def test_loader_rejects_unknown_fields_and_noncanonical_checksum(tmp_path):
    path = tmp_path / "part.checkpoint"
    cp.save(path, _checkpoint())
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["unexpected"] = "field"
    path.write_bytes(cp.canonical_json(raw))
    with pytest.raises(cp.CheckpointError, match="unknown field"):
        cp.load(path)

    raw.pop("unexpected")
    raw["state_checksum"] = "A" * 64
    path.write_bytes(cp.canonical_json(raw))
    with pytest.raises(cp.CheckpointError, match="lowercase SHA-256"):
        cp.load(path)


def test_loader_rejects_noncanonical_or_duplicate_json_bytes(tmp_path):
    path = tmp_path / "part.checkpoint"
    cp.save(path, _checkpoint())
    raw = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    with pytest.raises(cp.CheckpointError, match="exact canonical"):
        cp.load(path)

    cp.save(path, _checkpoint())
    encoded = path.read_text(encoding="utf-8")
    duplicate = encoded.replace(
        '"partition":"p"', '"partition":"p","partition":"p"', 1
    )
    path.write_text(duplicate, encoding="utf-8")
    with pytest.raises(cp.CheckpointError, match="exact canonical"):
        cp.load(path)

def test_checkpoint_tamper_fails_closed(tmp_path):
    path = tmp_path / "part.checkpoint"
    cp.save(path, _checkpoint(input_offset=0))
    text = path.read_text().replace('"x":1', '"x":2')
    path.write_text(text)
    with pytest.raises(cp.CheckpointError):
        cp.load(path)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda raw: raw.__setitem__("partition", "other"),
        lambda raw: raw.__setitem__("input_segment", "other-input"),
        lambda raw: raw.__setitem__("input_offset", 999),
        lambda raw: raw.__setitem__("last_domain_event_id", "other-event"),
        lambda raw: raw.__setitem__("highest_producer_epoch", 999),
        lambda raw: raw.__setitem__("projection_checksum", "0" * 64),
        lambda raw: raw.__setitem__("output_segment", "other-output"),
        lambda raw: raw.__setitem__("output_offset", 999),
        lambda raw: raw.__setitem__("state_seq", 999),
        lambda raw: raw.__setitem__("last_transition_id", "stx_other"),
        lambda raw: raw.__setitem__("digests", {**DIGESTS, "build": "0" * 64}),
        lambda raw: raw.__setitem__("identity_schema_version", "origin.checkpoint.v999"),
    ],
)
def test_checkpoint_replay_metadata_tamper_fails_closed(tmp_path, mutate):
    path = tmp_path / "part.checkpoint"
    cp.save(
        path,
        _checkpoint(),
    )
    raw = json.loads(path.read_text(encoding="utf-8"))
    mutate(raw)
    path.write_bytes(cp.canonical_json(raw))
    with pytest.raises(cp.CheckpointError):
        cp.load(path)


def test_checkpoint_missing_integrity_metadata_fails_closed(tmp_path):
    path = tmp_path / "part.checkpoint"
    cp.save(path, _checkpoint())
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw.pop("input_segment")
    path.write_bytes(cp.canonical_json(raw))
    with pytest.raises(cp.CheckpointError):
        cp.load(path)
