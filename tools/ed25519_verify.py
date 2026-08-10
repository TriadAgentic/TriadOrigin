#!/usr/bin/env python3
"""VERIFY-ONLY strict Ed25519 (RFC 8032) + DSSE PAE ceremony aid for TriadOrigin.

This tool mirrors, byte-for-byte in behavior, the verification half of the frozen audit runner
``audit_package/triad_origin_b01_b10_audit.py`` (v1.2.0):

* ``ed25519_verify`` — the runner's strict RFC 8032 verifier: 32-byte public key, 64-byte
  signature, strict canonical point decoding (a non-canonical ``y >= q`` or an ``x == 0`` point
  carrying sign bit 1 is rejected), ``s < L`` scalar bound, full-subgroup membership
  (``L * P == identity``) and small-order rejection (``8 * P == identity`` refuses) for both the
  public key and the signature's ``R`` point.
* ``pae`` — the DSSEv1 pre-authentication encoding the runner's ``dsse_pae`` builds:
  ``b"DSSEv1 " + len(type) + b" " + type + b" " + len(payload) + b" " + payload``.
* ``strict_base64`` — strict (validate=True) base64 decoding with an optional exact length.

The CLI verifies a DSSE envelope against a ``triad.receipt_trust_registry.v1`` registry:
keyid lookup, algorithm Ed25519 (case-insensitive), status ACTIVE (case-insensitive),
strict-base64 32-byte public key, and Ed25519 verification of each signature over the PAE.
It prints one JSON object on stdout::

    {"distinct_identities": N, "failed_keyids": [...], "failed_rows": [...], "verified_keyids": [...]}

and exits 0 iff at least one signature verified.  ``distinct_identities`` counts the distinct
non-empty registry ``identity`` strings among the verified signatures.

Verdicts are per signature ROW.  A keyid appears in ``verified_keyids`` iff ANY of its rows
verifies; ``failed_rows`` lists the 0-based indices of every non-verifying signature row; and
``failed_keyids`` lists only keyids with NO verifying row — a keyid never appears in both lists.

Mirroring the frozen runner's refusal law: a registry whose ``keys`` rows carry a duplicate
``key_id`` is REFUSED outright (hard error naming the duplicate id — the runner rejects such a
registry rather than building a last-wins map), and JSON inputs are parsed strictly per the
runner's ``strict_json_loads`` (duplicate object keys and the non-finite constants
``NaN``/``Infinity``/``-Infinity`` are rejected).  This CLI is a ceremony
AID only — the frozen runner performs its own independent verification and remains the gate
(the runner additionally enforces validity windows, revocation, milestone approvals, payload
canonicalization, and role/identity law that this aid deliberately does not decide).

STRICTLY VERIFY-ONLY: this module contains no signing code, loads no credential or private key,
opens no network connection, and writes no file.  It imports only the Python standard library
and never imports a sibling repository module, so invoking it inside a fresh clone mutates
nothing in the working tree (including ``__pycache__``).
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import sys
from typing import Any

TRUST_REGISTRY_SCHEMA = "triad.receipt_trust_registry.v1"

# Minimal, verification-focused RFC 8032 Ed25519 arithmetic, mirrored verbatim from the frozen
# audit runner (SHA-256 12c8896479b902165f...).  Verification only: there is deliberately no
# point-encoding helper and no signing helper here.
_ED_Q = 2**255 - 19
_ED_L = 2**252 + 27742317777372353535851937790883648493
_ED_D = (-121665 * pow(121666, _ED_Q - 2, _ED_Q)) % _ED_Q
_ED_I = pow(2, (_ED_Q - 1) // 4, _ED_Q)
_ED_ID = (0, 1, 1, 0)


def _ed_xrecover(y: int) -> int:
    xx = (y * y - 1) * pow(_ED_D * y * y + 1, _ED_Q - 2, _ED_Q) % _ED_Q
    x = pow(xx, (_ED_Q + 3) // 8, _ED_Q)
    if (x * x - xx) % _ED_Q:
        x = x * _ED_I % _ED_Q
    if x & 1:
        x = _ED_Q - x
    return x


_ED_BY = 4 * pow(5, _ED_Q - 2, _ED_Q) % _ED_Q
_ED_BX = _ed_xrecover(_ED_BY)
_ED_B = (_ED_BX, _ED_BY, 1, _ED_BX * _ED_BY % _ED_Q)


def _ed_add(p: tuple[int, int, int, int], q: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x1, y1, z1, t1 = p
    x2, y2, z2, t2 = q
    a = (y1 - x1) * (y2 - x2) % _ED_Q
    b = (y1 + x1) * (y2 + x2) % _ED_Q
    c = 2 * _ED_D * t1 * t2 % _ED_Q
    d = 2 * z1 * z2 % _ED_Q
    e, f, g, h = (b - a) % _ED_Q, (d - c) % _ED_Q, (d + c) % _ED_Q, (b + a) % _ED_Q
    return e * f % _ED_Q, g * h % _ED_Q, f * g % _ED_Q, e * h % _ED_Q


def _ed_double(p: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x, y, z, _ = p
    a, b, c = x * x % _ED_Q, y * y % _ED_Q, 2 * z * z % _ED_Q
    d = -a % _ED_Q
    e = ((x + y) * (x + y) - a - b) % _ED_Q
    g, f, h = (d + b) % _ED_Q, (d + b - c) % _ED_Q, (d - b) % _ED_Q
    return e * f % _ED_Q, g * h % _ED_Q, f * g % _ED_Q, e * h % _ED_Q


def _ed_scalar_mult(p: tuple[int, int, int, int], scalar: int) -> tuple[int, int, int, int]:
    result = _ED_ID
    addend = p
    while scalar:
        if scalar & 1:
            result = _ed_add(result, addend)
        addend = _ed_double(addend)
        scalar >>= 1
    return result


def _ed_equal(p: tuple[int, int, int, int], q: tuple[int, int, int, int]) -> bool:
    return (p[0] * q[2] - q[0] * p[2]) % _ED_Q == 0 and (p[1] * q[2] - q[1] * p[2]) % _ED_Q == 0


def _ed_decode(encoded: bytes) -> tuple[int, int, int, int] | None:
    if len(encoded) != 32:
        return None
    raw = int.from_bytes(encoded, "little")
    sign, y = raw >> 255, raw & ((1 << 255) - 1)
    if y >= _ED_Q:
        return None
    x = _ed_xrecover(y)
    # RFC 8032 canonical encoding: x=0 has sign bit 0 only.  Accepting sign=1 here creates a
    # second encoding of the identity/small-order points and breaks strict verification.
    if x == 0 and sign == 1:
        return None
    if (x & 1) != sign:
        x = _ED_Q - x
    if (-x * x + y * y - 1 - _ED_D * x * x * y * y) % _ED_Q:
        return None
    return x, y, 1, x * y % _ED_Q


def ed25519_verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    if len(public_key) != 32 or len(signature) != 64:
        return False
    public_point = _ed_decode(public_key)
    r_point = _ed_decode(signature[:32])
    scalar = int.from_bytes(signature[32:], "little")
    if public_point is None or r_point is None or scalar >= _ED_L:
        return False
    # Strict subgroup and non-small-order checks reject torsion-based malleability.
    if not _ed_equal(_ed_scalar_mult(public_point, _ED_L), _ED_ID):
        return False
    if not _ed_equal(_ed_scalar_mult(r_point, _ED_L), _ED_ID):
        return False
    if _ed_equal(_ed_scalar_mult(public_point, 8), _ED_ID):
        return False
    if _ed_equal(_ed_scalar_mult(r_point, 8), _ED_ID):
        return False
    challenge = int.from_bytes(
        hashlib.sha512(signature[:32] + public_key + message).digest(), "little") % _ED_L
    return _ed_equal(_ed_scalar_mult(_ED_B, scalar), _ed_add(r_point, _ed_scalar_mult(public_point, challenge)))


def pae(payload_type: str, payload: bytes) -> bytes:
    type_bytes = payload_type.encode("utf-8")
    return b"DSSEv1 " + str(len(type_bytes)).encode() + b" " + type_bytes + b" " + str(len(payload)).encode() + b" " + payload


def strict_base64(value: Any, expected_length: int | None = None) -> bytes | None:
    if not isinstance(value, str):
        return None
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return None
    if expected_length is not None and len(decoded) != expected_length:
        return None
    return decoded


class DuplicateJSONKey(ValueError):
    pass


def _strict_json_loads(value: str) -> Any:
    """Exact mirror of the frozen runner's ``strict_json_loads``.

    Duplicate object keys raise ``DuplicateJSONKey`` and the non-finite JSON constants
    (``NaN`` / ``Infinity`` / ``-Infinity``) raise ``json.JSONDecodeError`` via
    ``parse_constant`` — the runner accepts neither, so this aid must not either.
    """
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise DuplicateJSONKey(f"duplicate JSON object key {key!r}")
            result[key] = item
        return result

    def reject_constant(token: str) -> Any:
        raise json.JSONDecodeError(f"non-finite JSON number {token}", value, 0)

    return json.loads(value, object_pairs_hook=reject_duplicates, parse_constant=reject_constant)


def _load_json(path: str) -> Any:
    with open(path, "rb") as handle:
        raw = handle.read()
    return _strict_json_loads(raw.decode("utf-8"))


def _resolve_envelope(document: Any) -> dict[str, Any] | None:
    """Accept either a bare DSSE envelope or an event wrapping one under ``dsse``/``envelope``."""
    if not isinstance(document, dict):
        return None
    if "payloadType" in document or "signatures" in document:
        return document
    for wrapper_key in ("dsse", "envelope"):
        inner = document.get(wrapper_key)
        if isinstance(inner, dict):
            return inner
    return document


def _registry_keys(registry: Any) -> dict[str, dict[str, Any]]:
    """Fail-closed keyid lookup: an invalid registry trusts nothing.

    Mirrors the runner's registry law over ``registry["keys"]``: dict rows keyed by
    ``str(row["key_id"])``, and a DUPLICATE key_id among the dict rows REFUSES the whole
    registry (``ValueError`` naming the duplicate id) — the runner rejects such a registry
    outright ("trust registry contains duplicate key IDs"); it never builds a last-wins map.
    """
    if not isinstance(registry, dict) or registry.get("schema") != TRUST_REGISTRY_SCHEMA:
        return {}
    rows = registry.get("keys")
    if not isinstance(rows, list):
        return {}
    keys: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key_id = str(row.get("key_id"))
        if key_id in keys:
            raise ValueError(f"trust registry contains duplicate key ID {key_id!r}")
        keys[key_id] = row
    return keys


def verify_envelope_against_registry(
    document: Any, registry: Any, payload_type_override: str | None = None,
) -> dict[str, Any]:
    """Per-signature-ROW verdicts for a DSSE envelope against a trust registry.

    Returns ``{"verified_keyids": [...], "failed_keyids": [...], "failed_rows": [...],
    "distinct_identities": N}``.  A signature row verifies iff: its keyid resolves in the
    registry, the key's ``algorithm`` upper-cases to ``ED25519``, its ``status`` upper-cases to
    ``ACTIVE``, its ``public_key_base64`` strictly decodes to 32 bytes, the row's ``sig``
    strictly decodes to 64 bytes, and ``ed25519_verify`` accepts the signature over
    ``pae(payloadType, decoded_payload)``.

    THE ROW RULE (deterministic, keyid-disjoint): a keyid enters ``verified_keyids`` iff ANY of
    its rows verifies (first-acceptance order); ``failed_rows`` carries the 0-based index of
    every non-verifying row; ``failed_keyids`` carries only keyids with NO verifying row
    (first-failure order) — a keyid never appears in both keyid lists.  ``distinct_identities``
    is the number of distinct non-empty ``identity`` strings among verified keys.

    Raises ``ValueError`` if the registry carries a duplicate ``key_id`` (the runner's refusal).
    """
    envelope = _resolve_envelope(document)
    keys = _registry_keys(registry)
    verified: list[str] = []
    failed_candidates: list[str] = []
    failed_rows: list[int] = []
    identities: set[str] = set()

    if envelope is None:
        return {"verified_keyids": [], "failed_keyids": [], "failed_rows": [],
                "distinct_identities": 0}

    payload_type = envelope.get("payloadType")
    decoded_payload = strict_base64(envelope.get("payload"))
    pae_bytes: bytes | None = None
    if (
        isinstance(payload_type, str)
        and decoded_payload is not None
        and (payload_type_override is None or payload_type == payload_type_override)
    ):
        pae_bytes = pae(payload_type, decoded_payload)

    signatures = envelope.get("signatures")
    if not isinstance(signatures, list):
        signatures = []
    for index, row in enumerate(signatures):
        key_id = str(row.get("keyid") or "") if isinstance(row, dict) else ""
        accepted = False
        if isinstance(row, dict) and pae_bytes is not None:
            key = keys.get(key_id)
            if (
                key is not None
                and str(key.get("algorithm", "")).upper() == "ED25519"
                and str(key.get("status", "")).upper() == "ACTIVE"
            ):
                public_key = strict_base64(key.get("public_key_base64"), 32)
                signature = strict_base64(row.get("sig"), 64)
                if (
                    public_key is not None
                    and signature is not None
                    and ed25519_verify(public_key, pae_bytes, signature)
                ):
                    accepted = True
                    identity = str(key.get("identity", "")).strip()
                    if identity:
                        identities.add(identity)
        if accepted:
            if key_id not in verified:
                verified.append(key_id)
        else:
            failed_rows.append(index)
            failed_candidates.append(key_id)

    verified_set = set(verified)
    failed = [key_id for key_id in dict.fromkeys(failed_candidates) if key_id not in verified_set]
    return {
        "verified_keyids": verified,
        "failed_keyids": failed,
        "failed_rows": failed_rows,
        "distinct_identities": len(identities),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ed25519_verify",
        description=(
            "Verify a DSSE envelope against a triad.receipt_trust_registry.v1 registry "
            "(ceremony aid; the frozen audit runner performs its own verification). "
            "Verdicts are per signature ROW: a keyid enters verified_keyids if ANY of its rows "
            "verifies, failed_rows lists the indices of every non-verifying row, and "
            "failed_keyids lists only keyids with NO verifying row — a keyid never appears in "
            "both lists. A registry with a duplicate key_id is refused outright (exit 2, "
            "nothing on stdout), and JSON is parsed strictly (duplicate object keys and "
            "NaN/Infinity/-Infinity are rejected), mirroring the frozen runner."
        ),
    )
    parser.add_argument("--envelope", required=True, help="path to the DSSE envelope JSON")
    parser.add_argument("--registry", required=True, help="path to the trust registry JSON")
    parser.add_argument(
        "--payload-type", default=None,
        help="if given, the envelope payloadType must equal this value exactly")
    return parser


def main(argv: list[str] | None = None) -> int:
    sys.dont_write_bytecode = True
    args = build_parser().parse_args(argv)
    try:
        document = _load_json(args.envelope)
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        print(f"ed25519_verify: cannot read envelope: {exc}", file=sys.stderr)
        return 2
    try:
        registry = _load_json(args.registry)
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        print(f"ed25519_verify: cannot read registry: {exc}", file=sys.stderr)
        return 2
    if not isinstance(registry, dict) or registry.get("schema") != TRUST_REGISTRY_SCHEMA:
        print(
            f"ed25519_verify: registry schema is not {TRUST_REGISTRY_SCHEMA}; trusting no key",
            file=sys.stderr)
    try:
        report = verify_envelope_against_registry(document, registry, args.payload_type)
    except ValueError as exc:
        # The runner's refusal semantics: a duplicate key_id refuses the registry outright —
        # hard error naming the duplicate id, nothing on stdout.
        print(f"ed25519_verify: {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    return 0 if report["verified_keyids"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
