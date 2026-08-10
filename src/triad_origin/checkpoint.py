"""Versioned, checksummed deterministic checkpoints (MOD-017, Doc 04 §04.17).

A checkpoint captures canonical machine state, the authenticated consumed-input prefix, input/output
segments and offsets, last domain event, producer epoch, projection checksum, journal continuation
identity, and the exact build/config/contract/parameter/instrument digests. R00 proves suffix
identity against the supplied input tape. B02 must add an independently durable output-ledger head
before warm restore can assert terminal-prefix/no-loss identity (Doc 02 §02.16).
"""

from __future__ import annotations

import pathlib
from dataclasses import asdict, dataclass, field

from .canonical import CanonicalError, canonical_json, loads_canonical, sha256_hex


class CheckpointError(RuntimeError):
    pass


class CheckpointMigrationRequired(CheckpointError):
    """A recognized legacy checkpoint cannot be trusted for warm restore."""


# v3 (CTRL-B02-002): the closed per-scope fence state (accepted lease tokens + revocations +
# producer-epoch high-waters) is part of the sealed restart identity — a restore that cannot
# reproduce its fences must cold-rebuild, never guess.
CHECKPOINT_IDENTITY_VERSION = "origin.checkpoint.v3"
LEGACY_CHECKPOINT_IDENTITY_VERSIONS = ("origin.checkpoint.v1", "origin.checkpoint.v2")
REQUIRED_DIGEST_KEYS = frozenset({"build", "config", "contract", "parameter", "instrument"})


@dataclass
class Checkpoint:
    partition: str
    state: dict
    input_segment: str
    input_offset: int
    input_prefix_digest: str
    last_domain_event_id: str
    highest_producer_epoch: int
    projection_checksum: str
    output_segment: str
    output_offset: int
    state_seq: int
    last_transition_id: str
    digests: dict[str, str]
    fence_state: dict = field(default_factory=lambda: {
        "lease": {"highest": {}, "revoked": []}, "epoch": {}})
    state_checksum: str = ""
    identity_schema_version: str = CHECKPOINT_IDENTITY_VERSION

    def integrity_material(self) -> dict:
        """Every field that controls restore identity or replay position."""
        return {
            "partition": self.partition,
            "state": self.state,
            "input_segment": self.input_segment,
            "input_offset": self.input_offset,
            "input_prefix_digest": self.input_prefix_digest,
            "last_domain_event_id": self.last_domain_event_id,
            "highest_producer_epoch": self.highest_producer_epoch,
            "projection_checksum": self.projection_checksum,
            "output_segment": self.output_segment,
            "output_offset": self.output_offset,
            "state_seq": self.state_seq,
            "last_transition_id": self.last_transition_id,
            "digests": self.digests,
            "fence_state": self.fence_state,
            "identity_schema_version": self.identity_schema_version,
        }

    def compute_checksum(self) -> str:
        return sha256_hex(canonical_json(self.integrity_material()))

    def sealed(self) -> "Checkpoint":
        """Return a copy sealed over state and all replay-controlling metadata."""
        _validate_fields(self, loading=False)
        try:
            material = loads_canonical(canonical_json(self.integrity_material()))
        except (CanonicalError, UnicodeError, RecursionError) as exc:
            raise CheckpointError("checkpoint material is not canonical-wire encodable") from exc
        if not isinstance(material, dict):  # pragma: no cover - construction invariant
            raise CheckpointError("checkpoint integrity material must canonicalize to an object")
        return Checkpoint(
            partition=material["partition"],
            state=material["state"],
            input_segment=material["input_segment"],
            input_offset=material["input_offset"],
            input_prefix_digest=material["input_prefix_digest"],
            last_domain_event_id=material["last_domain_event_id"],
            highest_producer_epoch=material["highest_producer_epoch"],
            projection_checksum=material["projection_checksum"],
            output_segment=material["output_segment"],
            output_offset=material["output_offset"],
            state_seq=material["state_seq"],
            last_transition_id=material["last_transition_id"],
            digests=material["digests"],
            fence_state=material["fence_state"],
            state_checksum=sha256_hex(canonical_json(material)),
            identity_schema_version=material["identity_schema_version"],
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
    """Load and verify a checkpoint. Missing metadata or checksum mismatch is fail-closed."""
    p = pathlib.Path(path)
    if not p.exists():
        raise CheckpointError(f"checkpoint missing: {p}")
    try:
        raw = loads_canonical(p.read_bytes())
    except (OSError, CanonicalError, UnicodeError, RecursionError) as exc:
        raise CheckpointError(f"checkpoint is not exact canonical UTF-8 JSON: {p}") from exc
    if not isinstance(raw, dict):
        raise CheckpointError("checkpoint root must be an object")
    if raw.get("identity_schema_version") in LEGACY_CHECKPOINT_IDENTITY_VERSIONS:
        raise CheckpointMigrationRequired(
            f"{raw.get('identity_schema_version')} did not authenticate the complete restart "
            "identity (v1: replay metadata; v2: per-scope fence state); cold rebuild and write "
            "origin.checkpoint.v3 before warm restore"
        )
    required = {
        "partition",
        "state",
        "input_segment",
        "input_offset",
        "input_prefix_digest",
        "last_domain_event_id",
        "highest_producer_epoch",
        "projection_checksum",
        "output_segment",
        "output_offset",
        "state_seq",
        "last_transition_id",
        "state_checksum",
        "digests",
        "fence_state",
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
        input_segment=raw["input_segment"],
        input_offset=raw["input_offset"],
        input_prefix_digest=raw["input_prefix_digest"],
        last_domain_event_id=raw["last_domain_event_id"],
        highest_producer_epoch=raw["highest_producer_epoch"],
        projection_checksum=raw["projection_checksum"],
        output_segment=raw["output_segment"],
        output_offset=raw["output_offset"],
        state_seq=raw["state_seq"],
        last_transition_id=raw["last_transition_id"],
        digests=raw["digests"],
        fence_state=raw["fence_state"],
        state_checksum=raw["state_checksum"],
        identity_schema_version=raw["identity_schema_version"],
    )
    validate_for_restore(cp)
    return cp


def validate_for_restore(cp: Checkpoint) -> None:
    """Fail closed unless ``cp`` is a complete, sealed v3 restart identity."""
    _validate_fields(cp, loading=True)
    if cp.identity_schema_version != CHECKPOINT_IDENTITY_VERSION:
        raise CheckpointError(
            f"unsupported checkpoint identity version: {cp.identity_schema_version!r}"
        )
    if cp.state_checksum != cp.compute_checksum():
        raise CheckpointError(f"checkpoint checksum mismatch for partition {cp.partition}")


def _validate_fields(cp: Checkpoint, *, loading: bool) -> None:
    if not isinstance(cp.partition, str) or not cp.partition:
        raise CheckpointError("checkpoint partition must be a non-empty string")
    if not isinstance(cp.state, dict):
        raise CheckpointError("checkpoint state must be an object")
    if not isinstance(cp.input_segment, str) or not cp.input_segment:
        raise CheckpointError("checkpoint input_segment must be a non-empty string")
    if (
        isinstance(cp.input_offset, bool)
        or not isinstance(cp.input_offset, int)
        or cp.input_offset < -1
    ):
        raise CheckpointError("checkpoint input_offset must be an integer >= -1")
    if not _is_sha256(cp.input_prefix_digest):
        raise CheckpointError("checkpoint input_prefix_digest must be lowercase SHA-256 hex")
    if not isinstance(cp.last_domain_event_id, str) or not cp.last_domain_event_id:
        raise CheckpointError("checkpoint last_domain_event_id must be a non-empty string")
    if (
        isinstance(cp.highest_producer_epoch, bool)
        or not isinstance(cp.highest_producer_epoch, int)
        or cp.highest_producer_epoch < 0
    ):
        raise CheckpointError("checkpoint highest_producer_epoch must be an integer >= 0")
    if not _is_sha256(cp.projection_checksum):
        raise CheckpointError("checkpoint projection_checksum must be lowercase SHA-256 hex")
    expected_projection = sha256_hex(canonical_json(cp.state))
    if cp.projection_checksum != expected_projection:
        raise CheckpointError("checkpoint projection_checksum does not match state")
    if not isinstance(cp.output_segment, str) or not cp.output_segment:
        raise CheckpointError("checkpoint output_segment must be a non-empty string")
    if (
        isinstance(cp.output_offset, bool)
        or not isinstance(cp.output_offset, int)
        or cp.output_offset < -1
    ):
        raise CheckpointError("checkpoint output_offset must be an integer >= -1")
    if isinstance(cp.state_seq, bool) or not isinstance(cp.state_seq, int) or cp.state_seq < -1:
        raise CheckpointError("checkpoint state_seq must be an integer >= -1")
    if not isinstance(cp.last_transition_id, str) or not cp.last_transition_id:
        raise CheckpointError("checkpoint last_transition_id must be a non-empty string")
    if cp.state_seq == -1 and cp.last_transition_id != "genesis":
        raise CheckpointError("checkpoint genesis state requires last_transition_id='genesis'")
    if cp.state_seq >= 0 and not cp.last_transition_id.startswith("stx_"):
        raise CheckpointError("checkpoint last_transition_id must identify a state transition")
    fence = cp.fence_state
    if (not isinstance(fence, dict) or set(fence) != {"lease", "epoch"}
            or not isinstance(fence.get("lease"), dict)
            or set(fence["lease"]) != {"highest", "revoked"}
            or not isinstance(fence["lease"]["highest"], dict)
            or not isinstance(fence["lease"]["revoked"], list)
            or not isinstance(fence.get("epoch"), dict)):
        raise CheckpointError(
            "checkpoint fence_state must be exactly {lease:{highest,revoked}, epoch}")
    for scope, token in fence["lease"]["highest"].items():
        if not isinstance(scope, str) or not scope or isinstance(token, bool)                 or not isinstance(token, int) or token <= 0:
            raise CheckpointError(f"checkpoint fence lease token invalid for scope {scope!r}")
    for scope in fence["lease"]["revoked"]:
        if not isinstance(scope, str) or not scope:
            raise CheckpointError("checkpoint fence revoked scope must be non-empty text")
    for scope, epoch in fence["epoch"].items():
        if not isinstance(scope, str) or not scope or isinstance(epoch, bool)                 or not isinstance(epoch, int) or epoch < 0:
            raise CheckpointError(f"checkpoint fence epoch invalid for scope {scope!r}")
    if not isinstance(cp.digests, dict) or set(cp.digests) != REQUIRED_DIGEST_KEYS:
        raise CheckpointError(
            "checkpoint digests require exactly build/config/contract/parameter/instrument"
        )
    if any(not _is_sha256(value) for value in cp.digests.values()):
        raise CheckpointError("checkpoint digest values must be lowercase SHA-256 hex")
    if not isinstance(cp.identity_schema_version, str):
        raise CheckpointError("checkpoint identity_schema_version must be a string")
    if loading:
        if not _is_sha256(cp.state_checksum):
            raise CheckpointError("checkpoint state_checksum must be lowercase SHA-256 hex")
    elif cp.identity_schema_version != CHECKPOINT_IDENTITY_VERSION:
        raise CheckpointError(
            f"refusing to write unsupported checkpoint version: {cp.identity_schema_version!r}"
        )


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(ch in "0123456789abcdef" for ch in value)
    )
