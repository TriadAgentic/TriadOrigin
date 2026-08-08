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


class CheckpointMigrationRequired(CheckpointError):
    """A recognized legacy checkpoint cannot be trusted for warm restore."""


CHECKPOINT_IDENTITY_VERSION = "origin.checkpoint.v2"
LEGACY_CHECKPOINT_IDENTITY_VERSION = "origin.checkpoint.v1"


@dataclass
class Checkpoint:
    partition: str
    state: dict
    input_offset: int
    state_checksum: str = ""
    digests: dict = field(default_factory=dict)
    identity_schema_version: str = CHECKPOINT_IDENTITY_VERSION

    def integrity_material(self) -> dict:
        """Every field that controls restore identity or replay position."""
        return {
            "partition": self.partition,
            "state": self.state,
            "input_offset": self.input_offset,
            "digests": self.digests,
            "identity_schema_version": self.identity_schema_version,
        }

    def compute_checksum(self) -> str:
        return sha256_hex(canonical_json(self.integrity_material()))

    def sealed(self) -> "Checkpoint":
        """Return a copy sealed over state and all replay-controlling metadata."""
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
    _validate_fields(cp, loading=False)
    sealed = cp.sealed()
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    body = canonical_json(asdict(sealed))
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_bytes(body)
    tmp.replace(p)
    return sealed.state_checksum


def load(path: str | pathlib.Path) -> Checkpoint:
    """Load and verify a checkpoint. Missing metadata or checksum mismatch is fail-closed."""
    p = pathlib.Path(path)
    if not p.exists():
        raise CheckpointError(f"checkpoint missing: {p}")
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CheckpointError(f"checkpoint is not valid UTF-8 JSON: {p}") from exc
    if not isinstance(raw, dict):
        raise CheckpointError("checkpoint root must be an object")
    required = {
        "partition",
        "state",
        "input_offset",
        "state_checksum",
        "digests",
        "identity_schema_version",
    }
    missing = sorted(required - raw.keys())
    if missing:
        raise CheckpointError(f"checkpoint missing integrity field(s): {missing}")
    extra = sorted(raw.keys() - required)
    if extra:
        raise CheckpointError(f"checkpoint carries unknown field(s): {extra}")
    cp = Checkpoint(
        partition=raw["partition"],
        state=raw["state"],
        input_offset=raw["input_offset"],
        state_checksum=raw["state_checksum"],
        digests=raw["digests"],
        identity_schema_version=raw["identity_schema_version"],
    )
    _validate_fields(cp, loading=True)
    if cp.identity_schema_version == LEGACY_CHECKPOINT_IDENTITY_VERSION:
        raise CheckpointMigrationRequired(
            "origin.checkpoint.v1 authenticated state only; cold rebuild and write "
            "origin.checkpoint.v2 before warm restore"
        )
    if cp.identity_schema_version != CHECKPOINT_IDENTITY_VERSION:
        raise CheckpointError(
            f"unsupported checkpoint identity version: {cp.identity_schema_version!r}"
        )
    if cp.state_checksum != cp.compute_checksum():
        raise CheckpointError(f"checkpoint checksum mismatch for partition {cp.partition}")
    return cp


def _validate_fields(cp: Checkpoint, *, loading: bool) -> None:
    if not isinstance(cp.partition, str) or not cp.partition:
        raise CheckpointError("checkpoint partition must be a non-empty string")
    if not isinstance(cp.state, dict):
        raise CheckpointError("checkpoint state must be an object")
    if isinstance(cp.input_offset, bool) or not isinstance(cp.input_offset, int):
        raise CheckpointError("checkpoint input_offset must be an integer")
    if not isinstance(cp.digests, dict) or any(
        not isinstance(k, str) or not k or not isinstance(v, str) or not v
        for k, v in cp.digests.items()
    ):
        raise CheckpointError("checkpoint digests must map non-empty strings to non-empty strings")
    if not isinstance(cp.identity_schema_version, str):
        raise CheckpointError("checkpoint identity_schema_version must be a string")
    if loading:
        if (
            not isinstance(cp.state_checksum, str)
            or len(cp.state_checksum) != 64
            or any(ch not in "0123456789abcdef" for ch in cp.state_checksum)
        ):
            raise CheckpointError("checkpoint state_checksum must be lowercase SHA-256 hex")
    elif cp.identity_schema_version != CHECKPOINT_IDENTITY_VERSION:
        raise CheckpointError(
            f"refusing to write unsupported checkpoint version: {cp.identity_schema_version!r}"
        )
