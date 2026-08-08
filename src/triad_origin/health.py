"""Read-only readiness and attestation face (MOD-020, Doc 04 §04.17, Doc 05 §05.8).

This R00 bootstrap face is deliberately narrow: it reports only manifest equality, warm-up,
checkpoint parity and writable owned ledgers. It does **not** yet prove source freshness/coverage,
lease validity or estate activation; those evidence dimensions remain blocked milestones. The
process is compiled with zero side-effect authority.

Nothing here has side effects; it only reads state and builds attestation/heartbeat/readiness facts.
A healthy dark process is ``READY_NO_AUTHORITY`` (Doc 04 §04.17).
"""

from __future__ import annotations

from enum import Enum

from . import ALLOW_MONEY_PUBLISH, SERVICE_ID, contracts
from .canonical import canonical_json, loads_canonical


class Readiness(str, Enum):
    CREATED = "CREATED"
    STARTING = "STARTING"
    WARMING = "WARMING"
    READY_NO_AUTHORITY = "READY_NO_AUTHORITY"
    DRAINING = "DRAINING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


def compute_readiness(
    *,
    manifest_ok: bool,
    warmup_complete: bool,
    checkpoint_parity: bool,
    ledgers_writable: bool,
) -> Readiness:
    """Derive narrow bootstrap readiness; never imply source or authority readiness."""
    values = {
        "manifest_ok": manifest_ok,
        "warmup_complete": warmup_complete,
        "checkpoint_parity": checkpoint_parity,
        "ledgers_writable": ledgers_writable,
    }
    if any(type(value) is not bool for value in values.values()):
        raise ValueError("readiness evidence inputs must be booleans")
    if ALLOW_MONEY_PUBLISH:
        raise RuntimeError("constitutional breach: DARK readiness requires zero money capability")
    if not (manifest_ok and ledgers_writable):
        return Readiness.STARTING
    if not (warmup_complete and checkpoint_parity):
        return Readiness.WARMING
    return Readiness.READY_NO_AUTHORITY


def build_service_heartbeat(
    *,
    partition_offsets: dict,
    watermark: dict,
    warmup_status: str,
    quality: dict,
    lease_state: str,
) -> dict:
    """A ``service_heartbeat.v1`` payload. ``side_effect_capability`` is zero for a dark process."""
    if ALLOW_MONEY_PUBLISH:
        raise RuntimeError("constitutional breach: ORIGIN cannot advertise money authority")
    payload = {
        "service_id": SERVICE_ID,
        "partition_offsets": partition_offsets,
        "watermark": watermark,
        "warmup_status": warmup_status,
        "quality": quality,
        "lease_state": lease_state,
        "side_effect_capability": "NONE",
    }
    contracts.validate_payload("triad.service_heartbeat.v1", payload)
    snapshot = loads_canonical(canonical_json(payload))
    if not isinstance(snapshot, dict):  # pragma: no cover - payload invariant
        raise RuntimeError("heartbeat payload did not canonicalize to an object")
    return snapshot


def build_engine_attestation(
    *,
    contract_manifest_sha256: str,
    config_bundle_sha256: str,
    build_commit: str,
    artifact_sha256: str,
    parameter_set_id: str,
    parameter_digest: str,
    instrument_map_digest: str,
    universe_digest: str,
    activation_manifest_id: str,
    producer_epoch: str,
    environment: str,
    host_identity: str,
    startup_receipt_id: str,
) -> dict:
    """Build only the RC1 payload fragment; it is not an authoritative runtime attestation.

    RC1 does not enforce equality between duplicated envelope/payload identity fields. B01 must
    introduce an additive compatible contract before this fragment can be treated as authoritative.
    """
    digests = {
        "contract_manifest_sha256": contract_manifest_sha256,
        "config_bundle_sha256": config_bundle_sha256,
        "artifact_sha256": artifact_sha256,
        "parameter_digest": parameter_digest,
        "instrument_map_digest": instrument_map_digest,
        "universe_digest": universe_digest,
    }
    if any(value == "0" * 64 for value in digests.values()):
        raise contracts.ContractError("attestation payload refuses all-zero identity digests")
    identities = {
        "build_commit": build_commit,
        "parameter_set_id": parameter_set_id,
        "activation_manifest_id": activation_manifest_id,
        "environment": environment,
        "host_identity": host_identity,
        "startup_receipt_id": startup_receipt_id,
    }
    if any(not isinstance(value, str) or not value for value in identities.values()):
        raise contracts.ContractError("attestation payload identity fields must be non-empty strings")
    payload = {
        "contract_bundle_version": "origin.contracts.1.0.0-RC1",
        "contract_manifest_sha256": contract_manifest_sha256,
        "config_bundle_sha256": config_bundle_sha256,
        "risk_policy_sha": "",  # ORIGIN never holds risk policy; empty by construction
        "build_commit": build_commit,
        "artifact_sha256": artifact_sha256,
        "parameter_set_id": parameter_set_id,
        "parameter_digest": parameter_digest,
        "instrument_map_digest": instrument_map_digest,
        "fee_model_id": "",
        "universe_digest": universe_digest,
        "activation_manifest_id": activation_manifest_id,
        "producer_epoch": producer_epoch,
        "environment": environment,
        "host_identity": host_identity,
        "startup_receipt_id": startup_receipt_id,
    }
    contracts.validate_payload("triad.engine_attestation.v1", payload)
    return payload
