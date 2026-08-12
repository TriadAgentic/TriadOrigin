#!/usr/bin/env python3
"""B01C-BIND-01/03/06 — verify the packaged binding bundle + its authenticated capability.

Two surfaces:

* ``--bundle <path>``: load the bundle through :func:`triad_origin.bindings.load_registry`, proving
  the exact 105-row inventory, every per-row digest, the no-sentinel-in-ACTIVE law, and the
  scope-collision law. A tampered / wrong-count / non-hex-digest bundle exits 1. Without a real,
  externally pinned ``--authority`` preimage the tool CANNOT authenticate the bundle root (the owner
  trust anchor is out-of-repo and B00R is unvalidated), so it prints ``UNAVAILABLE_AUTHORITY`` and
  exits 0 — fail-closed, never a fabricated authenticated PASS. A ``--authority`` preimage that IS
  supplied but that offline-prep cannot actually authenticate exits **2** (fail-closed): a supplied
  preimage must never be mistaken for an authenticated PASS just because it was present.
* ``--selftest``: build a synthetic tool-layer Ed25519 owner key, authenticate a real
  :class:`~triad_origin.bindings.ResolvedParameterBundle`, then run six authenticity attacks
  (unsigned · wrong-signer · revoked · expired · valid-signature-over-other-bytes · wrong-trust-key)
  and assert every one is REFUSED with a named reason. This is the only real offline green.

The Ed25519 sign/verify lives HERE in the tool layer (``bindings.build_resolved_bundle`` takes an
injected ``verify_fn``); the DARK boundary forbids a crypto import inside ``src/triad_origin`` only.
Fail-closed: if the full schema validator is absent the bundle loader raises and this tool exits 3.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import bindings, contracts, governance  # noqa: E402

_BUNDLE_REQUIRED_ROLES = ("AUTHORITY_OWNER",)
_BUNDLE_THRESHOLD = 1


# --- tool-layer Ed25519 (permitted outside src/) -------------------------------------------------
def ed25519_verify(public_key_hex: str, message: bytes, signature_hex: str) -> bool:
    """Verify one Ed25519 signature — the injected tool-layer backend (validate_authority_root shape)."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
        key.verify(bytes.fromhex(signature_hex), message)
        return True
    except Exception:
        return False


def _ephemeral_owner_key():
    """Return (public_key_hex, sign(message)->signature_hex) for a fresh synthetic owner key."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    private = Ed25519PrivateKey.generate()
    pub_hex = private.public_key().public_bytes_raw().hex()

    def sign(message: bytes) -> str:
        return private.sign(message).hex()

    return pub_hex, sign


# --- bundle inventory verification ---------------------------------------------------------------
def verify_bundle(bundle_path: pathlib.Path) -> dict:
    """Load + inventory-verify a binding bundle. Raises BindingRegistryError on any tamper."""
    registry = bindings.load_registry(bundle_path)
    return {
        "row_count": registry.status_counts_total(),
        "status_counts": registry.status_counts(),
        "source_bundle_digest": registry.source_bundle_digest(),
    }


def _bundle_kw(registry: bindings.BindingRegistry) -> dict:
    return dict(
        bundle_id="origin.binding-bundle.v1", bundle_version="1",
        authority_digest="a" * 64, engine="E02", plane="four_plane",
        environment="OFF", scope="repository", trust_registry_digest="b" * 64)


def _root_bytes(registry, kw) -> bytes:
    return bindings.canonical_bundle_root(
        bundle_id=kw["bundle_id"], bundle_version=kw["bundle_version"],
        source_bundle_digest=registry.source_bundle_digest(),
        authority_digest=kw["authority_digest"], engine=kw["engine"], plane=kw["plane"],
        environment=kw["environment"], scope=kw["scope"],
        row_count=registry.status_counts_total(), status_counts=registry.status_counts())


def selftest() -> dict:
    """Authenticate a real capability, then prove six authenticity attacks are all refused."""
    registry = bindings.load_registry()
    kw = _bundle_kw(registry)
    owner_pk, sign = _ephemeral_owner_key()
    kid = "owner-selftest"
    trust = {kid: {"key_id": kid, "identity": "owner@selftest", "role": "AUTHORITY_OWNER",
                   "algorithm": "ed25519", "public_key_hex": owner_pk, "revoked": False,
                   "not_before_us": 1, "not_after_us": 5_000_000}}
    good_sig = sign(_root_bytes(registry, kw))
    now_us = 2_000_000

    def build(*, signatures, trust_reg=trust, now=now_us):
        return bindings.build_resolved_bundle(
            registry, trust=trust_reg, signatures=signatures, verify_fn=ed25519_verify,
            now_us=now, **kw)

    # Happy path: a real owner signature authenticates the capability.
    cap = build(signatures=[{"key_id": kid, "signature_hex": good_sig}])
    assert type(cap) is bindings.ResolvedParameterBundle
    assert cap.verification()["verification_reason"] == "OK"

    attacks = {}

    def refused(name, fn) -> None:
        try:
            fn()
            attacks[name] = "WRONGLY_BUILT"
        except bindings.BindingBundleUnauthenticated as exc:
            attacks[name] = exc.reason

    refused("unsigned", lambda: build(signatures=[]))
    refused("wrong_signer",
            lambda: build(signatures=[{"key_id": "stranger", "signature_hex": good_sig}]))
    revoked = {kid: {**trust[kid], "revoked": True}}
    refused("revoked", lambda: build(signatures=[{"key_id": kid, "signature_hex": good_sig}],
                                     trust_reg=revoked))
    refused("expired", lambda: build(signatures=[{"key_id": kid, "signature_hex": good_sig}],
                                     now=6_000_000))
    other_sig = sign(_root_bytes(registry, {**kw, "authority_digest": "f" * 64}))
    refused("valid_sig_over_other_bytes",
            lambda: build(signatures=[{"key_id": kid, "signature_hex": other_sig}]))
    wrong_pk, _ = _ephemeral_owner_key()
    wrong_trust = {kid: {**trust[kid], "public_key_hex": wrong_pk}}
    refused("wrong_trust_key",
            lambda: build(signatures=[{"key_id": kid, "signature_hex": good_sig}],
                          trust_reg=wrong_trust))

    all_refused = all(v not in ("WRONGLY_BUILT",) for v in attacks.values())
    return {"authenticated_ok": True, "attacks": attacks, "all_attacks_refused": all_refused,
            "row_count": registry.status_counts_total()}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=pathlib.Path, help="path to a binding_registry.v2.json")
    parser.add_argument("--authority", type=pathlib.Path,
                        help="externally pinned authority preimage (owner-gated; absent => UNAVAILABLE)")
    parser.add_argument("--selftest", action="store_true",
                        help="run the six-attack authenticity self-test with an ephemeral owner key")
    args = parser.parse_args(argv)

    try:
        if args.selftest:
            result = selftest()
            for name, reason in sorted(result["attacks"].items()):
                print(f"  attack {name:28s} -> {reason}")
            if not result["all_attacks_refused"]:
                print("FAIL: an authenticity attack WRONGLY BUILT a capability", file=sys.stderr)
                return 1
            print(f"OK: capability authenticated; all 6 attacks refused "
                  f"(bundle rows={result['row_count']})")
            return 0

        bundle_path = args.bundle if args.bundle is not None else bindings.DEFAULT_REGISTRY_PATH
        facts = verify_bundle(bundle_path)
        print(f"bundle rows={facts['row_count']} status_counts={facts['status_counts']} "
              f"source_bundle_digest={facts['source_bundle_digest'][:16]}")
        if args.authority is None:
            # No externally pinned authority preimage -> cannot authenticate the bundle root offline.
            print("UNAVAILABLE_AUTHORITY: bundle inventory verified; owner-pinned authority preimage "
                  "absent, so bundle-root authentication is not attempted (fail-closed).")
            return 0
        # A supplied authority preimage MUST be cryptographically authenticated before this tool
        # may report success. Offline-prep cannot reach the out-of-repo owner trust anchor, so it
        # CANNOT authenticate the supplied preimage and therefore fails closed (exit 2) rather than
        # returning a green exit that would read as an authenticated PASS. Presence of a preimage is
        # not authentication — this is the exact false-green the gate exists to refuse (audit #10).
        print("UNAVAILABLE_AUTHORITY: an --authority preimage was supplied, but the owner trust "
              "anchor is out-of-repo and authentication was NOT performed; failing closed (exit 2, "
              "not a PASS). Run --selftest for the real offline authenticity proof.", file=sys.stderr)
        return 2
    except contracts.SchemaValidatorUnavailable as exc:
        print(f"SCHEMA_VALIDATOR_UNAVAILABLE: {exc}", file=sys.stderr)
        return 3
    except bindings.BindingRegistryError as exc:
        print(f"FAIL: bundle inventory invalid: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
