"""Versioned, checksummed deterministic checkpoints (MOD-017, Doc 04 §04.17).

A checkpoint captures a machine's state bytes, the input offset it is current through, and the exact
build/config/contract/parameter/instrument digests. Restore is byte-identity invariant: cold, warm
and checkpoint-resumed runs yield identical suffix events and IDs (Doc 02 §02.16 restart invariance).
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import asdict, dataclass, field

from .canonical import canonical_json, sha256_hex


class CheckpointError(RuntimeError):
    pass


@dataclass
class Checkpoint:
    partition: str
    state: dict
    input_offset: int
    state_checksum: str = ""
    digests: dict = field(default_factory=dict)
    identity_schema_version: str = "origin.checkpoint.v1"

    def compute_checksum(self) -> str:
        return sha256_hex(canonical_json(self.state))

    def sealed(self) -> "Checkpoint":
        """Return a copy with the state checksum filled from the canonical state bytes."""
        return Checkpoint(
            partition=self.partition,
            state=self.state,
            input_offset=self.input_offset,
            state_checksum=self.compute_checksum(),
            digests=dict(self.digests),
            identity_schema_version=self.identity_schema_version,
        )


def save(path: str | pathlib.Path, cp: Checkpoint) -> str:
    """Seal and write a checkpoint atomically. Returns the state checksum."""
    sealed = cp.sealed()
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    body = canonical_json(asdict(sealed))
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_bytes(body)
    tmp.replace(p)
    return sealed.state_checksum


def load(path: str | pathlib.Path) -> Checkpoint:
    """Load and verify a checkpoint. A checksum mismatch is fail-closed."""
    p = pathlib.Path(path)
    if not p.exists():
        raise CheckpointError(f"checkpoint missing: {p}")
    raw = json.loads(p.read_text(encoding="utf-8"))
    cp = Checkpoint(
        partition=raw["partition"],
        state=raw["state"],
        input_offset=raw["input_offset"],
        state_checksum=raw.get("state_checksum", ""),
        digests=raw.get("digests", {}),
        identity_schema_version=raw.get("identity_schema_version", "origin.checkpoint.v1"),
    )
    if cp.state_checksum != cp.compute_checksum():
        raise CheckpointError(f"checkpoint checksum mismatch for partition {cp.partition}")
    return cp
