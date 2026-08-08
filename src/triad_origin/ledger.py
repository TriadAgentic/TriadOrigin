"""Append-only, length-framed, hash-chained file ledger (transport phase-0 binding, Doc 05 §05.5).

One authoritative writer lock per logical topic/partition. Each record is ``uint32_be(len) ||
payload || sha256_chain(32)`` where ``chain_i = sha256(chain_{i-1} || len_bytes || payload_i)`` and
``chain_0 = sha256(MAGIC)``. Corrupt/torn frames stop the partition and preserve bytes — never a
silent skip. A restart scans to the end and recovers the chain, so replay has no duplicates and no
loss.

The money/evidence durability class fsyncs on append. This is the practical durable path; a NATS
JetStream binding is a later, separately certified option (Doc 05 §05.5) and ORIGIN activation never
waits on an unprovisioned bus.
"""

from __future__ import annotations

import fcntl
import hashlib
import os
import pathlib
from dataclasses import dataclass

MAGIC = b"TRIAD-ORIGIN-LEDGER-1\n"
_LEN = 4
_CHAIN = 32
_MAX_RECORD = 64 * 1024 * 1024  # a single record may not exceed 64 MiB (fail-closed)


class LedgerError(RuntimeError):
    pass


class LedgerCorruption(LedgerError):
    """A torn or tampered frame. The partition stops; bytes are preserved for quarantine."""


class LedgerLocked(LedgerError):
    """Another writer already holds the single-writer lock for this ledger."""


def _chain(prev: bytes, length_bytes: bytes, payload: bytes) -> bytes:
    h = hashlib.sha256()
    h.update(prev)
    h.update(length_bytes)
    h.update(payload)
    return h.digest()


@dataclass
class Record:
    offset: int
    seq: int
    payload: bytes
    chain: bytes


class LedgerWriter:
    """Single-writer append handle. Use as a context manager to hold/release the lock."""

    def __init__(self, path: str | os.PathLike, *, fsync: bool = True):
        self.path = pathlib.Path(path)
        self.fsync = fsync
        self._fh = None
        self._lock_fh = None
        self._prev = hashlib.sha256(MAGIC).digest()
        self._seq = -1

    def __enter__(self) -> "LedgerWriter":
        self.open()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self._lock_fh = open(lock_path, "w")
        try:
            fcntl.flock(self._lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self._lock_fh.close()
            self._lock_fh = None
            raise LedgerLocked(f"ledger already has a writer: {self.path}") from exc
        # Initialize magic on a fresh file, then recover the chain from any existing records.
        if not self.path.exists() or self.path.stat().st_size == 0:
            with open(self.path, "wb") as f:
                f.write(MAGIC)
                if self.fsync:
                    f.flush()
                    os.fsync(f.fileno())
        else:
            self._recover()
        self._fh = open(self.path, "ab")

    def _recover(self) -> None:
        """Scan existing records, verifying the chain, to recover ``_prev`` and ``_seq``."""
        for rec in read_records(self.path):
            self._prev = rec.chain
            self._seq = rec.seq

    def append(self, payload: bytes) -> Record:
        if self._fh is None:
            raise LedgerError("ledger writer is not open")
        if not isinstance(payload, (bytes, bytearray)):
            raise LedgerError("ledger payload must be bytes")
        if len(payload) == 0 or len(payload) > _MAX_RECORD:
            raise LedgerError(f"ledger record length out of bounds: {len(payload)}")
        length_bytes = len(payload).to_bytes(_LEN, "big")
        chain = _chain(self._prev, length_bytes, bytes(payload))
        offset = self._fh.tell()
        self._fh.write(length_bytes)
        self._fh.write(payload)
        self._fh.write(chain)
        self._fh.flush()
        if self.fsync:
            os.fsync(self._fh.fileno())
        self._prev = chain
        self._seq += 1
        return Record(offset=offset, seq=self._seq, payload=bytes(payload), chain=chain)

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None
        if self._lock_fh is not None:
            fcntl.flock(self._lock_fh, fcntl.LOCK_UN)
            self._lock_fh.close()
            self._lock_fh = None


def read_records(path: str | os.PathLike):
    """Iterate verified records. Raises ``LedgerCorruption`` on a torn or tampered frame."""
    path = pathlib.Path(path)
    if not path.exists():
        return
    data = path.read_bytes()
    if data[: len(MAGIC)] != MAGIC:
        raise LedgerCorruption(f"bad ledger magic: {path}")
    pos = len(MAGIC)
    prev = hashlib.sha256(MAGIC).digest()
    seq = -1
    n = len(data)
    while pos < n:
        if pos + _LEN > n:
            raise LedgerCorruption(f"torn length header at offset {pos}")
        length = int.from_bytes(data[pos : pos + _LEN], "big")
        if length == 0 or length > _MAX_RECORD:
            raise LedgerCorruption(f"invalid record length {length} at offset {pos}")
        start = pos + _LEN
        end = start + length
        if end + _CHAIN > n:
            raise LedgerCorruption(f"torn record body/chain at offset {pos}")
        payload = data[start:end]
        stored_chain = data[end : end + _CHAIN]
        expected = _chain(prev, data[pos : pos + _LEN], payload)
        if stored_chain != expected:
            raise LedgerCorruption(f"hash-chain mismatch at offset {pos} (tamper or corruption)")
        seq += 1
        yield Record(offset=pos, seq=seq, payload=payload, chain=stored_chain)
        prev = stored_chain
        pos = end + _CHAIN


def verify(path: str | os.PathLike) -> int:
    """Verify the whole chain; return the record count. Raises on corruption."""
    count = 0
    for _ in read_records(path):
        count += 1
    return count
