"""Append-only, length-framed, hash-chained file ledger (transport phase-0 binding, Doc 05 §05.5).

One authoritative writer lock per logical topic/partition. Each record is ``uint32_be(len) ||
payload || sha256_chain(32)`` where ``chain_i = sha256(chain_{i-1} || len_bytes || payload_i)`` and
``chain_0 = sha256(MAGIC)``. Corrupt/torn/interior-mutated frames stop the partition and preserve
bytes — never a silent skip. A restart can continue an intact chain. A complete-tail deletion is
not detectable from this file alone until B02 binds an independently durable expected head; no
exactly-once or no-loss claim is made before that control exists.

The money/evidence durability class fsyncs on append. This is the practical durable path; a NATS
JetStream binding is a later, separately certified option (Doc 05 §05.5) and ORIGIN activation never
waits on an unprovisioned bus.
"""

from __future__ import annotations

import fcntl
import hashlib
import os
import pathlib
import threading
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


@dataclass(frozen=True)
class Record:
    offset: int
    seq: int
    payload: bytes
    chain: bytes


class LedgerWriter:
    """Single-writer append handle. Use as a context manager to hold/release the lock."""

    def __init__(self, path: str | os.PathLike, *, fsync: bool = True):
        if fsync is not True:
            raise LedgerError("durable ledger fsync cannot be disabled")
        self.path = pathlib.Path(path).resolve(strict=False)
        self._fh = None
        self._prev = hashlib.sha256(MAGIC).digest()
        self._seq = -1
        self._thread_lock = threading.RLock()

    def __enter__(self) -> "LedgerWriter":
        self.open()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def open(self) -> None:
        with self._thread_lock:
            if self._fh is not None:
                raise LedgerError("ledger writer is already open")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            existed = self.path.exists()
            fh = open(self.path, "a+b")
            try:
                # Lock the ledger inode itself: hard links and symlink aliases cannot acquire an
                # independent path-derived sidecar lock for the same authoritative bytes.
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                fh.close()
                raise LedgerLocked(f"ledger already has a writer: {self.path}") from exc
            self._fh = fh
            self._prev = hashlib.sha256(MAGIC).digest()
            self._seq = -1
            try:
                fh.seek(0, os.SEEK_END)
                if fh.tell() == 0:
                    fh.write(MAGIC)
                    fh.flush()
                    os.fsync(fh.fileno())
                    if not existed:
                        _fsync_directory(self.path.parent)
                else:
                    self._recover()
                fh.seek(0, os.SEEK_END)
            except Exception:
                fcntl.flock(fh, fcntl.LOCK_UN)
                fh.close()
                self._fh = None
                raise

    def _recover(self) -> None:
        """Scan existing records, verifying the chain, to recover ``_prev`` and ``_seq``."""
        for rec in read_records(self.path):
            self._prev = rec.chain
            self._seq = rec.seq

    def append(self, payload: bytes) -> Record:
        with self._thread_lock:
            if self._fh is None:
                raise LedgerError("ledger writer is not open")
            if not isinstance(payload, (bytes, bytearray)):
                raise LedgerError("ledger payload must be bytes")
            payload_bytes = bytes(payload)
            if len(payload_bytes) == 0 or len(payload_bytes) > _MAX_RECORD:
                raise LedgerError(f"ledger record length out of bounds: {len(payload_bytes)}")
            length_bytes = len(payload_bytes).to_bytes(_LEN, "big")
            chain = _chain(self._prev, length_bytes, payload_bytes)
            offset = self._fh.tell()
            self._fh.write(length_bytes)
            self._fh.write(payload_bytes)
            self._fh.write(chain)
            self._fh.flush()
            os.fsync(self._fh.fileno())
            self._prev = chain
            self._seq += 1
            return Record(
                offset=offset, seq=self._seq, payload=payload_bytes, chain=chain
            )

    def close(self) -> None:
        with self._thread_lock:
            if self._fh is not None:
                fcntl.flock(self._fh, fcntl.LOCK_UN)
                self._fh.close()
                self._fh = None


def read_records(path: str | os.PathLike):
    """Iterate verified records. Raises ``LedgerCorruption`` on a torn or tampered frame."""
    path = pathlib.Path(path)
    if not path.exists():
        return
    with open(path, "rb") as fh:
        if fh.read(len(MAGIC)) != MAGIC:
            raise LedgerCorruption(f"bad ledger magic: {path}")
        pos = len(MAGIC)
        prev = hashlib.sha256(MAGIC).digest()
        seq = -1
        while True:
            length_bytes = fh.read(_LEN)
            if length_bytes == b"":
                break
            if len(length_bytes) != _LEN:
                raise LedgerCorruption(f"torn length header at offset {pos}")
            length = int.from_bytes(length_bytes, "big")
            if length == 0 or length > _MAX_RECORD:
                raise LedgerCorruption(f"invalid record length {length} at offset {pos}")
            payload = fh.read(length)
            stored_chain = fh.read(_CHAIN)
            if len(payload) != length or len(stored_chain) != _CHAIN:
                raise LedgerCorruption(f"torn record body/chain at offset {pos}")
            expected = _chain(prev, length_bytes, payload)
            if stored_chain != expected:
                raise LedgerCorruption(
                    f"hash-chain mismatch at offset {pos} (tamper or corruption)"
                )
            seq += 1
            yield Record(offset=pos, seq=seq, payload=payload, chain=stored_chain)
            prev = stored_chain
            pos = fh.tell()


def _fsync_directory(path: pathlib.Path) -> None:
    flags = os.O_RDONLY | os.O_DIRECTORY
    fd = os.open(path, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def verify(path: str | os.PathLike) -> int:
    """Verify the whole chain; return the record count. Raises on corruption."""
    count = 0
    for _ in read_records(path):
        count += 1
    return count
