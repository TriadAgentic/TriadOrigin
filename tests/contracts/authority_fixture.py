"""Deterministic §C.2 authority-preimage fixtures for ``tools/verify_binding_bundle.py``.

Everything here is derived from FIXED byte seeds (committed below) plus the packaged 105-row
binding registry, so every generated payload is byte-deterministic run to run: the Ed25519 keys
come from ``Ed25519PrivateKey.from_private_bytes(<fixed 32-byte seed>)`` and Ed25519 signing is
itself deterministic (RFC 8032). NOT a test module — imported by
``test_verify_binding_bundle_authority.py``.

ONE fixture trust registry serves every variant; the variants differ only in the root bundle
and/or the manifest, so each refusal drill isolates exactly one law.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import bindings, governance  # noqa: E402
from triad_origin.canonical import sha256_hex  # noqa: E402

# --- fixed key seeds (fixture material only — never real authority) ------------------------------
OWNER_SEED = "11" * 32          # active AUTHORITY_OWNER — signs decisions + the root bundle
REVOKED_OWNER_SEED = "22" * 32  # revoked AUTHORITY_OWNER — the SIGNER_REVOKED drill
EVIDENCE_SEED = "33" * 32       # EVIDENCE_PRODUCER (registry usability requires all three roles)
COUNTER_SEED = "44" * 32        # INDEPENDENT_COUNTERSIGNER
ROGUE_SEED = "55" * 32          # a key NOT in the registry — the wrong-signing-key drill

OWNER_KID = "c2-fixture-owner"
REVOKED_OWNER_KID = "c2-fixture-owner-revoked"
EVIDENCE_KID = "c2-fixture-evidence"
COUNTER_KID = "c2-fixture-countersigner"

REPOSITORY = "TriadOrigin"
ENVIRONMENT = "OFF"

# --- fixed times (UTC epoch microseconds) ---------------------------------------------------------
NOW_US = 1_500_000_000_000_000
KEY_NOT_BEFORE_US = 1
KEY_NOT_AFTER_US = 9_000_000_000_000_000
VALID_FROM_US = 1_000_000_000_000_000
VALID_TO_US = 2_000_000_000_000_000
DEC_EFFECTIVE_US = 1_100_000_000_000_000
EXPIRED_VALID_TO_US = 1_200_000_000_000_000       # < NOW_US -> EXPIRED
FUTURE_VALID_FROM_US = 1_600_000_000_000_000      # > NOW_US -> NOT_YET_VALID

DECISION_IDS = ("DEC-AUTHORITY-BUNDLE-002", "DEC-RECEIPT-PROFILE-002", "DEC-B00-REPAIR-002")
_OWNER_SCOPE = ",".join(DECISION_IDS)

VARIANTS = (
    "happy",
    "reordered_rows",
    "wrong_root",
    "wrong_key",
    "revoked",
    "expired",
    "not_yet_valid",
    "duplicate_signer",
    "scope_mismatch",
    "unknown_field",
    "trust_digest_mismatch",
    "malformed_manifest",
)


def _private_key(seed_hex: str):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed_hex))


def public_key_hex(seed_hex: str) -> str:
    return _private_key(seed_hex).public_key().public_bytes_raw().hex()


def sign_hex(seed_hex: str, message: bytes) -> str:
    return _private_key(seed_hex).sign(message).hex()


def _key_entry(kid: str, identity: str, role: str, seed_hex: str, *, revoked: bool) -> dict:
    return {
        "key_id": kid,
        "identity": identity,
        "role": role,
        "algorithm": "ed25519",
        "public_key_hex": public_key_hex(seed_hex),
        "revoked": revoked,
        "not_before_us": KEY_NOT_BEFORE_US,
        "not_after_us": KEY_NOT_AFTER_US,
        "scope": _OWNER_SCOPE if role == "AUTHORITY_OWNER" else "B00R..B07",
    }


def trust_registry_doc() -> dict:
    """The ONE fixture trust registry (schema-valid, usable, all three roles present)."""
    return {
        "schema": "triad.receipt_trust_registry.v1",
        "schema_version": "1.0.0",
        "registry_kind": "RECEIPT_TRUST_REGISTRY",
        "registry_id": "c2-authority-fixture-registry",
        "authenticated": True,
        "keys": [
            _key_entry(OWNER_KID, "owner@c2-fixture", "AUTHORITY_OWNER",
                       OWNER_SEED, revoked=False),
            _key_entry(REVOKED_OWNER_KID, "revoked-owner@c2-fixture", "AUTHORITY_OWNER",
                       REVOKED_OWNER_SEED, revoked=True),
            _key_entry(EVIDENCE_KID, "evidence@c2-fixture", "EVIDENCE_PRODUCER",
                       EVIDENCE_SEED, revoked=False),
            _key_entry(COUNTER_KID, "countersigner@c2-fixture", "INDEPENDENT_COUNTERSIGNER",
                       COUNTER_SEED, revoked=False),
        ],
    }


def _dump(doc: object) -> bytes:
    return json.dumps(doc, sort_keys=True, indent=1).encode("utf-8")


def decision_doc(decision_id: str) -> dict:
    """One signed 002 decision object (schema-valid, owner-signed, in-scope, effective)."""
    doc = {
        "schema": "triad.governance_decision.v1",
        "schema_version": "1.0.0",
        "decision_kind": "GOVERNANCE_DECISION",
        "decision_id": decision_id,
        "issuer": "owner@c2-fixture",
        "authority_registry": "trust_registry.json",
        "subject_sha256s": {
            "c2_fixture_subject": sha256_hex(
                b"triad-origin-c2-fixture-subject:" + decision_id.encode("utf-8")),
        },
        "scope": {"applies_to": "c2-authority-fixture"},
        "decision": f"C2 fixture decision {decision_id}",
        "effective_at_us": DEC_EFFECTIVE_US,
        "authenticated": True,
    }
    signature = sign_hex(OWNER_SEED, governance.canonical_decision_signing_bytes(doc))
    doc["signatures"] = [{"key_id": OWNER_KID, "signature_hex": signature}]
    return doc


def _signed_sealed_bundle(registry, *, environment: str, valid_from: int, valid_to: int,
                          trust_registry_digest: str, signer_seed: str, signer_kid: str):
    unsigned = bindings.build_sealed_bundle(
        registry, repository=REPOSITORY, environment=environment,
        valid_from=valid_from, valid_to=valid_to,
        trust_registry_digest=trust_registry_digest, signer_set=[signer_kid])
    signing_bytes = bindings.sealed_bundle_signing_bytes(
        canonical_root_digest=unsigned.canonical_root_digest, scope=unsigned.scope,
        valid_from=unsigned.valid_from, valid_to=unsigned.valid_to)
    signature = {"key_id": signer_kid, "signature_hex": sign_hex(signer_seed, signing_bytes)}
    return dataclasses.replace(unsigned, signatures=[signature])


def _root_bundle_doc(registry, trust_digest: str, variant: str) -> dict:
    environment = "LIVE" if variant == "scope_mismatch" else ENVIRONMENT
    valid_from = FUTURE_VALID_FROM_US if variant == "not_yet_valid" else VALID_FROM_US
    valid_to = EXPIRED_VALID_TO_US if variant == "expired" else VALID_TO_US
    if variant == "revoked":
        seed, kid = REVOKED_OWNER_SEED, REVOKED_OWNER_KID
    elif variant == "wrong_key":
        seed, kid = ROGUE_SEED, OWNER_KID  # rogue private key presented under the owner's key_id
    else:
        seed, kid = OWNER_SEED, OWNER_KID
    bundle = _signed_sealed_bundle(
        registry, environment=environment, valid_from=valid_from, valid_to=valid_to,
        trust_registry_digest=trust_digest, signer_seed=seed, signer_kid=kid)
    doc = dataclasses.asdict(bundle)
    if variant == "reordered_rows":
        doc["rows"] = list(reversed(doc["rows"]))  # canonicalization must make order irrelevant
    if variant == "wrong_root":
        doc["canonical_root_digest"] = sha256_hex(b"c2-fixture-wrong-root")
    if variant == "duplicate_signer":
        doc["signatures"] = [doc["signatures"][0], dict(doc["signatures"][0])]
    return doc


def write_fixture(dest_dir: pathlib.Path, variant: str = "happy") -> pathlib.Path:
    """Write one complete authority-preimage fixture directory. Returns the manifest path."""
    assert variant in VARIANTS, variant
    dest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = dest_dir / "authority_manifest.json"

    if variant == "malformed_manifest":
        manifest_path.write_bytes(b"{ this is not JSON")
        return manifest_path

    registry = bindings.load_registry()
    trust_bytes = _dump(trust_registry_doc())
    (dest_dir / "trust_registry.json").write_bytes(trust_bytes)
    trust_digest = sha256_hex(trust_bytes)

    decision_entries = []
    for index, decision_id in enumerate(DECISION_IDS):
        payload = _dump(decision_doc(decision_id))
        name = f"decision_{index}.json"
        (dest_dir / name).write_bytes(payload)
        decision_entries.append({"path": name, "expected_sha256": sha256_hex(payload)})

    root_doc = _root_bundle_doc(registry, trust_digest, variant)
    root_bytes = _dump(root_doc)
    (dest_dir / "root_bundle.json").write_bytes(root_bytes)

    manifest = {
        "trust_registry": {
            "path": "trust_registry.json",
            "expected_sha256": (sha256_hex(b"c2-fixture-wrong-trust-digest")
                                if variant == "trust_digest_mismatch" else trust_digest),
        },
        "decisions": decision_entries,
        "root_bundle": {"path": "root_bundle.json", "expected_sha256": sha256_hex(root_bytes)},
        "external_pins": [
            {"name": "rc3_master_document",
             "expected_sha256": sha256_hex(b"c2-fixture-external-pin")},
        ],
    }
    if variant == "unknown_field":
        manifest["extra_authority_claim"] = "presence-is-not-proof"
    manifest_path.write_bytes(_dump(manifest))
    return manifest_path
