"""External durable anchor for the hash-chained ledger (CTRL-B02-001).

A self-contained hash-chained ledger detects torn/interior corruption, but cannot detect deletion
or replacement of a complete, internally-consistent tail — the file simply looks shorter (or
different) and still verifies. The anchor closes that class: an append-only anchor journal,
stored at an *operator-chosen external durable location* (a different filesystem/volume in
production; any distinct path in tests), pins the ledger's

  * file identity (magic digest + genesis record chain),
  * record count and byte length,
  * chain head at anchor time,

and each anchor entry chains over its predecessor, so the anchor journal itself is
tamper-evident. ``verify_anchored`` then refuses a ledger whose history disagrees with any
anchored point — a deleted tail, a replaced tail (even a validly re-chained one), or a wholesale
file swap all fail loudly.

Recovery receipts are plain dicts the caller journals/checkpoints — this module performs no
authority action and reads no clock.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib

from . import ledger as ledger_mod
from .canonical import canonical_json, sha256_hex

ANCHOR_VERSION = "origin.ledger-anchor.v1"
_GENESIS_PREV = "genesis"


class AnchorError(RuntimeError):
    pass


def _ledger_scan(ledger_path: pathlib.Path):
    """Walk the ledger, returning (records, byte_length, file_identity)."""
    records = list(ledger_mod.read_records(ledger_path))
    byte_length = ledger_path.stat().st_size
    magic_digest = sha256_hex(ledger_mod.MAGIC)
    genesis_chain = records[0].chain.hex() if records else ""
    file_identity = sha256_hex(
        canonical_json({"magic": magic_digest, "genesis_chain": genesis_chain}))
    return records, byte_length, file_identity


def _entry_digest(entry: dict) -> str:
    unsigned = {k: v for k, v in entry.items() if k != "entry_digest"}
    return sha256_hex(canonical_json(unsigned))


def read_anchor_entries(anchor_path: str | os.PathLike) -> list[dict]:
    """Read and chain-verify the anchor journal. Empty file / missing file -> empty list."""
    path = pathlib.Path(anchor_path)
    if not path.exists():
        return []
    entries: list[dict] = []
    prev = _GENESIS_PREV
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AnchorError(f"anchor journal line {line_no} is not JSON") from exc
        if entry.get("previous_entry_digest") != prev:
            raise AnchorError(f"anchor journal chain broken at line {line_no}")
        if entry.get("entry_digest") != _entry_digest(entry):
            raise AnchorError(f"anchor journal entry digest mismatch at line {line_no}")
        if entry.get("anchor_version") != ANCHOR_VERSION:
            raise AnchorError(f"unknown anchor version at line {line_no}")
        entries.append(entry)
        prev = entry["entry_digest"]
    return entries


def anchor_ledger(ledger_path: str | os.PathLike, anchor_path: str | os.PathLike) -> dict:
    """Append the ledger's current verified state to the external anchor journal."""
    lpath = pathlib.Path(ledger_path)
    apath = pathlib.Path(anchor_path)
    if lpath.resolve(strict=False) == apath.resolve(strict=False):
        raise AnchorError("anchor journal must live at a distinct durable location")
    records, byte_length, file_identity = _ledger_scan(lpath)
    existing = read_anchor_entries(apath)
    if existing:
        last = existing[-1]
        if last["file_identity"] != file_identity:
            raise AnchorError("refusing to anchor: ledger file identity changed under the anchor")
        if len(records) < last["record_count"] or byte_length < last["byte_length"]:
            raise AnchorError("refusing to anchor: ledger shrank below the anchored state")
    entry = {
        "anchor_version": ANCHOR_VERSION,
        "anchor_seq": len(existing),
        "file_identity": file_identity,
        "record_count": len(records),
        "byte_length": byte_length,
        "chain_head": records[-1].chain.hex() if records else "",
        "last_seq": records[-1].seq if records else -1,
        "previous_entry_digest": existing[-1]["entry_digest"] if existing else _GENESIS_PREV,
    }
    entry["entry_digest"] = _entry_digest(entry)
    apath.parent.mkdir(parents=True, exist_ok=True)
    with open(apath, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return entry


def verify_anchored(ledger_path: str | os.PathLike, anchor_path: str | os.PathLike) -> dict:
    """Verify the ledger against every anchored point. Returns a recovery receipt dict.

    Detects (each a named failure):
      * ANCHOR_TAIL_DELETED  — the ledger holds fewer records/bytes than an anchored point;
      * ANCHOR_TAIL_REPLACED — the chain at an anchored seq disagrees with the anchored head
        (a re-chained substitute tail cannot reproduce the anchored chain value);
      * ANCHOR_FILE_REPLACED — the ledger's file identity (magic + genesis chain) changed.
    """
    entries = read_anchor_entries(anchor_path)
    if not entries:
        raise AnchorError("no anchor entries: the ledger has no external binding to verify")
    records, byte_length, file_identity = _ledger_scan(pathlib.Path(ledger_path))
    chain_by_seq = {rec.seq: rec.chain.hex() for rec in records}
    for entry in entries:
        if entry["file_identity"] != file_identity:
            raise AnchorError("ANCHOR_FILE_REPLACED: ledger file identity mismatch")
        if len(records) < entry["record_count"] or byte_length < entry["byte_length"]:
            raise AnchorError(
                f"ANCHOR_TAIL_DELETED: ledger shrank below anchor_seq {entry['anchor_seq']}")
        if entry["record_count"] > 0:
            observed = chain_by_seq.get(entry["last_seq"])
            if observed != entry["chain_head"]:
                raise AnchorError(
                    f"ANCHOR_TAIL_REPLACED: chain at seq {entry['last_seq']} does not reproduce "
                    f"anchor_seq {entry['anchor_seq']}")
    head = entries[-1]
    return {
        "anchor_version": ANCHOR_VERSION,
        "verified_against_anchor_seq": head["anchor_seq"],
        "anchored_record_count": head["record_count"],
        "ledger_record_count": len(records),
        "ledger_byte_length": byte_length,
        "file_identity": file_identity,
        "chain_head": records[-1].chain.hex() if records else "",
        "result": "PASS",
    }
