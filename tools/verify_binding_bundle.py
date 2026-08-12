#!/usr/bin/env python3
"""B01C-BIND-01/03/06 + Formula-Repair §C.2 — verify the binding bundle + its owner authority.

Three surfaces:

* ``--bundle <path>``: load the bundle through :func:`triad_origin.bindings.load_registry`, proving
  the exact 105-row inventory, every per-row digest, the no-sentinel-in-ACTIVE law, and the
  scope-collision law. A tampered / wrong-count / non-hex-digest bundle exits 1.
* ``--authority <path>`` (spec §C.2): a preimage manifest naming the pinned trust registry, the
  three ``DEC-*-002`` decision objects, the sealed root bundle, and the external pins. The tool
  reads EVERY byte payload, hashes each against its expected sha256, parses the trust registry
  (:func:`triad_origin.governance.validate_trust_registry`), verifies every decision and the root
  bundle signature set (role, revocation, validity window, threshold, scope) with a REAL Ed25519
  ``verify_fn``, and verifies the root bundle's ``canonical_root_digest`` per §C.1
  (:func:`triad_origin.bindings.canonical_rows_digest`). Exit 0 ONLY on full success. ANY other
  state exits nonzero with exactly ONE typed reason token on STDOUT (prose goes to stderr):
  ``UNAVAILABLE_AUTHORITY | DIGEST_MISMATCH | SIGNATURE_INVALID | SIGNER_REVOKED | EXPIRED |
  NOT_YET_VALID | SCOPE_MISMATCH | THRESHOLD_NOT_MET | MALFORMED_PREIMAGE | UNKNOWN_FIELD``.
  ABSENT ``--authority`` means the owner-gated path was not run: NONZERO exit with
  ``UNAVAILABLE_AUTHORITY`` on stdout — argument presence never functions as proof, and absence is
  never a green PASS (the historical exit-0 was the defect this closes).
* ``--selftest``: the synthetic SELF_TEST — an ephemeral tool-layer Ed25519 owner key
  authenticates a real :class:`~triad_origin.bindings.ResolvedParameterBundle`, then six
  authenticity attacks (unsigned · wrong-signer · revoked · expired · valid-signature-over-other-
  bytes · wrong-trust-key) are all REFUSED with named reasons. SELF_TEST is clearly labeled and is
  NEVER a substitute for the real ``--authority`` path.

The Ed25519 sign/verify lives HERE in the tool layer (``src/triad_origin`` takes an injected
``verify_fn``); the DARK boundary forbids a crypto import inside ``src/triad_origin`` only.
Fail-closed: if the full schema validator is absent the bundle loader raises and this tool exits 3.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import bindings, contracts, governance  # noqa: E402
from triad_origin.canonical import sha256_hex  # noqa: E402

_BUNDLE_REQUIRED_ROLES = ("AUTHORITY_OWNER",)
_BUNDLE_THRESHOLD = 1

# The process's bound {repository, environment} the sealed root bundle's scope must equal exactly
# (spec §C.1 step 4 / §C.2 SCOPE_MISMATCH). Repository identity is this repository; the venue
# environment posture is the invariant baseline ``venue_environment=OFF`` (never a testnet).
_PROCESS_SCOPE = {"repository": "TriadOrigin", "environment": "OFF"}

# The CLOSED §C.2 reason vocabulary — exactly one of these lands on stdout on any nonzero exit of
# the authority contract.
AUTHORITY_TOKENS = (
    "UNAVAILABLE_AUTHORITY",
    "DIGEST_MISMATCH",
    "SIGNATURE_INVALID",
    "SIGNER_REVOKED",
    "EXPIRED",
    "NOT_YET_VALID",
    "SCOPE_MISMATCH",
    "THRESHOLD_NOT_MET",
    "MALFORMED_PREIMAGE",
    "UNKNOWN_FIELD",
)

_HEX64_RE = re.compile(r"\A[0-9a-f]{64}\Z")

_MANIFEST_FIELDS = ("trust_registry", "decisions", "root_bundle", "external_pins")


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


# =================================================================================================
# §C.2 — the real --authority path: preimage manifest -> byte payloads -> hashes -> trust registry
# -> decision + root-bundle signature sets -> canonical root digest. Real authentication or a
# nonzero exit with exactly ONE typed reason on stdout.
# =================================================================================================
class AuthorityRefusal(Exception):
    """A typed §C.2 refusal — ``token`` is the SINGLE stdout reason, ``detail`` is stderr prose."""

    def __init__(self, token: str, detail: str):
        assert token in AUTHORITY_TOKENS, token
        self.token = token
        self.detail = detail
        super().__init__(f"{token}: {detail}")


def _refuse(token: str, detail: str):
    raise AuthorityRefusal(token, detail)


def _json_strict(raw: bytes, what: str) -> object:
    """Parse JSON bytes refusing duplicate keys, floats, and non-UTF-8 (canonical law)."""
    try:
        text = raw.decode("utf-8")
    except UnicodeError:
        _refuse("MALFORMED_PREIMAGE", f"{what}: not UTF-8")

    def _no_duplicates(pairs: list) -> dict:
        out: dict = {}
        for key, value in pairs:
            if key in out:
                _refuse("MALFORMED_PREIMAGE", f"{what}: duplicate object key {key!r}")
            out[key] = value
        return out

    def _no_float(token: str):
        _refuse("MALFORMED_PREIMAGE", f"{what}: non-canonical numeric literal {token!r}")

    try:
        return json.loads(text, object_pairs_hook=_no_duplicates,
                          parse_float=_no_float, parse_constant=_no_float)
    except AuthorityRefusal:
        raise
    except (ValueError, RecursionError) as exc:
        _refuse("MALFORMED_PREIMAGE", f"{what}: not JSON ({exc})")


def _require_hex64(value: object, what: str) -> str:
    if not isinstance(value, str) or _HEX64_RE.match(value) is None:
        _refuse("MALFORMED_PREIMAGE", f"{what}: expected_sha256 must be 64 lowercase hex chars")
    return value


def _check_entry_keys(entry: object, what: str, allowed: tuple, required: tuple) -> dict:
    """A manifest entry is a closed object: unknown key -> UNKNOWN_FIELD, missing -> MALFORMED."""
    if not isinstance(entry, dict):
        _refuse("MALFORMED_PREIMAGE", f"{what}: not an object")
    unknown = sorted(set(entry) - set(allowed))
    if unknown:
        _refuse("UNKNOWN_FIELD", f"{what}: unknown field {unknown[0]!r}")
    missing = sorted(set(required) - set(entry))
    if missing:
        _refuse("MALFORMED_PREIMAGE", f"{what}: missing field {missing[0]!r}")
    return entry


def _read_payload(entry: dict, base_dir: pathlib.Path, what: str) -> bytes:
    """Read the entry's byte payload (``path`` relative to the manifest, or hex ``inline_bytes``)."""
    has_path = "path" in entry
    has_inline = "inline_bytes" in entry
    if has_path == has_inline:  # both or neither
        _refuse("MALFORMED_PREIMAGE", f"{what}: exactly one of path|inline_bytes is required")
    if has_inline:
        inline = entry["inline_bytes"]
        if not isinstance(inline, str) or len(inline) % 2 != 0:
            _refuse("MALFORMED_PREIMAGE", f"{what}: inline_bytes must be hex-encoded bytes")
        try:
            return bytes.fromhex(inline)
        except ValueError:
            _refuse("MALFORMED_PREIMAGE", f"{what}: inline_bytes must be hex-encoded bytes")
    path = entry["path"]
    if not isinstance(path, str) or not path:
        _refuse("MALFORMED_PREIMAGE", f"{what}: path must be a nonempty string")
    resolved = (base_dir / path) if not pathlib.PurePath(path).is_absolute() else pathlib.Path(path)
    try:
        return resolved.read_bytes()
    except OSError as exc:
        _refuse("UNAVAILABLE_AUTHORITY", f"{what}: payload unreadable at {resolved} ({exc})")


def _expect_digest(raw: bytes, expected_hex: str, what: str) -> None:
    if not bindings.ct_hex_equal(sha256_hex(raw), expected_hex):
        _refuse("DIGEST_MISMATCH", f"{what}: sha256 does not match expected_sha256")


def _signature_token(reason: str) -> str:
    """Map a governance.verify_signatures refusal reason onto the closed §C.2 vocabulary."""
    if reason.startswith("REVOKED_SIGNER"):
        return "SIGNER_REVOKED"
    if reason.startswith("SIGNER_EXPIRED"):
        return "EXPIRED"
    if reason.startswith("SIGNER_NOT_YET_VALID"):
        return "NOT_YET_VALID"
    if reason.startswith("SIGNER_SCOPE_DENIED"):
        return "SCOPE_MISMATCH"
    if reason.startswith(("BELOW_THRESHOLD", "NO_EXTERNAL_SIGNATURES",
                          "DUPLICATE_SIGNER_IDENTITY", "MISSING_ROLE",
                          "BAD_SIGNATURE_THRESHOLD", "DUPLICATE_REQUIRED_ROLE")):
        return "THRESHOLD_NOT_MET"
    # UNKNOWN_SIGNER / BAD_SIGNATURE* / BAD_SIGNATURE_ENCODING / BAD_SIGNATURE_RECORD /
    # VERIFY_UNAVAILABLE / BAD_NOW_US and anything unnamed: the signature set did not verify.
    return "SIGNATURE_INVALID"


def _decision_token(message: str) -> str:
    """Map a governance decision refusal (GovernanceError text) onto the §C.2 vocabulary."""
    if message.startswith("DECISION_SIGNATURE_INVALID:"):
        return _signature_token(message.split(":", 1)[1])
    if message.startswith("DECISION_EXPIRED"):
        return "EXPIRED"
    if message.startswith("DECISION_NOT_YET_EFFECTIVE"):
        return "NOT_YET_VALID"
    # Structural refusals (unauthenticated template, bad scope/subjects/schema, ...): the supplied
    # decision preimage is not a well-formed authenticated decision.
    return "MALFORMED_PREIMAGE"


def _parse_manifest(manifest_path: pathlib.Path) -> dict:
    try:
        raw = manifest_path.read_bytes()
    except OSError as exc:
        _refuse("UNAVAILABLE_AUTHORITY",
                f"authority preimage manifest unreadable at {manifest_path} ({exc})")
    doc = _json_strict(raw, "authority manifest")
    if not isinstance(doc, dict):
        _refuse("MALFORMED_PREIMAGE", "authority manifest: not an object")
    unknown = sorted(set(doc) - set(_MANIFEST_FIELDS))
    if unknown:
        _refuse("UNKNOWN_FIELD", f"authority manifest: unknown field {unknown[0]!r}")
    missing = sorted(set(_MANIFEST_FIELDS) - set(doc))
    if missing:
        _refuse("MALFORMED_PREIMAGE", f"authority manifest: missing field {missing[0]!r}")
    return doc


def _verified_trust(manifest: dict, base_dir: pathlib.Path) -> tuple[dict, bytes]:
    """Read + hash-compare + parse the pinned trust registry. Returns (trust_by_id, raw_bytes)."""
    entry = _check_entry_keys(manifest["trust_registry"], "trust_registry",
                              allowed=("path", "inline_bytes", "expected_sha256"),
                              required=("expected_sha256",))
    expected = _require_hex64(entry["expected_sha256"], "trust_registry")
    raw = _read_payload(entry, base_dir, "trust_registry")
    _expect_digest(raw, expected, "trust_registry")
    doc = _json_strict(raw, "trust_registry")
    if not isinstance(doc, dict):
        _refuse("MALFORMED_PREIMAGE", "trust_registry: not an object")
    try:
        trust = governance.validate_trust_registry(doc)
        governance.assert_usable_trust_registry(trust)
    except governance.GovernanceError as exc:
        _refuse("MALFORMED_PREIMAGE", f"trust_registry: {exc}")
    return trust, raw


def _verify_decisions(manifest: dict, base_dir: pathlib.Path, trust: dict, now_us: int) -> int:
    decisions = manifest["decisions"]
    if not isinstance(decisions, list) or not decisions:
        _refuse("MALFORMED_PREIMAGE", "decisions: must be a nonempty array")
    for index, item in enumerate(decisions):
        what = f"decisions[{index}]"
        entry = _check_entry_keys(item, what, allowed=("path", "expected_sha256"),
                                  required=("path", "expected_sha256"))
        expected = _require_hex64(entry["expected_sha256"], what)
        raw = _read_payload(entry, base_dir, what)
        _expect_digest(raw, expected, what)
        doc = _json_strict(raw, what)
        if not isinstance(doc, dict):
            _refuse("MALFORMED_PREIMAGE", f"{what}: not an object")
        try:
            governance.validate_authenticated_decision(
                doc, trust=trust, now_us=now_us, verify_fn=ed25519_verify)
        except governance.GovernanceError as exc:
            _refuse(_decision_token(str(exc)), f"{what}: {exc}")
    return len(decisions)


def _verify_root_bundle(manifest: dict, base_dir: pathlib.Path, trust: dict,
                        trust_bytes: bytes, now_us: int) -> str:
    """Verify the sealed root bundle: bytes -> shape -> canonical root -> signatures -> window/scope.

    Returns the ``signed_root_digest`` (sha256 of the actually-signed canonical root bytes).
    """
    entry = _check_entry_keys(manifest["root_bundle"], "root_bundle",
                              allowed=("path", "expected_sha256"),
                              required=("path", "expected_sha256"))
    expected = _require_hex64(entry["expected_sha256"], "root_bundle")
    raw = _read_payload(entry, base_dir, "root_bundle")
    _expect_digest(raw, expected, "root_bundle")
    try:
        bundle = bindings.SealedParameterBundle.from_json(raw)
    except bindings.SealedBundleRejected as exc:
        token = "UNKNOWN_FIELD" if exc.reason.startswith("UNKNOWN_FIELD") else "MALFORMED_PREIMAGE"
        _refuse(token, f"root_bundle: {exc.reason}")

    if bundle.schema_version != bindings.SEALED_SCHEMA_VERSION:
        _refuse("MALFORMED_PREIMAGE", f"root_bundle: unsupported schema_version "
                                      f"{bundle.schema_version!r}")
    scope = bundle.scope
    if (not isinstance(scope, dict) or sorted(scope) != sorted(bindings.SCOPE_FIELDS)
            or any(not isinstance(scope[k], str) or not scope[k] for k in bindings.SCOPE_FIELDS)):
        _refuse("MALFORMED_PREIMAGE", "root_bundle: scope must be {repository, environment}")
    for name in ("valid_from", "valid_to"):
        value = getattr(bundle, name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            _refuse("MALFORMED_PREIMAGE", f"root_bundle: {name} must be a nonnegative integer")
    if bundle.valid_from > bundle.valid_to:
        _refuse("MALFORMED_PREIMAGE", "root_bundle: valid_from > valid_to")
    if not isinstance(bundle.canonical_root_digest, str) \
            or _HEX64_RE.match(bundle.canonical_root_digest) is None:
        _refuse("MALFORMED_PREIMAGE", "root_bundle: canonical_root_digest must be hex64")
    signer_set = bundle.signer_set
    if (not isinstance(signer_set, list)
            or any(not isinstance(k, str) or not k for k in signer_set)
            or len(set(signer_set)) != len(signer_set)):
        _refuse("MALFORMED_PREIMAGE", "root_bundle: signer_set must be unique nonempty strings")
    if not isinstance(bundle.signatures, list):
        _refuse("MALFORMED_PREIMAGE", "root_bundle: signatures must be an array")

    # The bundle's pinned trust digest must be THE registry the manifest supplied (§C.1 step 2).
    if not bindings.ct_hex_equal(bundle.trust_registry_digest, sha256_hex(trust_bytes)):
        _refuse("DIGEST_MISMATCH",
                "root_bundle: trust_registry_digest does not match the supplied trust registry")

    # §C.1 step 1 — recompute the canonical root over rows[]; order is canonicalized away.
    try:
        recomputed_root = bindings.canonical_rows_digest(bundle.rows)
    except bindings.SealedBundleRejected as exc:
        _refuse("MALFORMED_PREIMAGE", f"root_bundle: {exc.reason}")
    if not bindings.ct_hex_equal(recomputed_root, bundle.canonical_root_digest):
        _refuse("DIGEST_MISMATCH",
                "root_bundle: canonical_root_digest does not match the recomputed rows digest")

    # §C.1 step 3 — the REAL Ed25519 signature set over canonical root || scope || validity.
    signing_bytes = bindings.sealed_bundle_signing_bytes(
        canonical_root_digest=recomputed_root, scope=scope,
        valid_from=bundle.valid_from, valid_to=bundle.valid_to)
    for sig in bundle.signatures:
        if not isinstance(sig, dict):
            _refuse("MALFORMED_PREIMAGE", "root_bundle: signature record must be an object")
        if sig.get("key_id") not in signer_set:
            _refuse("SIGNATURE_INVALID",
                    f"root_bundle: signer {sig.get('key_id')!r} not in the declared signer_set")
    ok, reason = governance.verify_signatures(
        signed_bytes=signing_bytes, signatures=bundle.signatures, trust=trust,
        required_roles=_BUNDLE_REQUIRED_ROLES, threshold=_BUNDLE_THRESHOLD,
        now_us=now_us, verify_fn=ed25519_verify)
    if not ok:
        _refuse(_signature_token(reason), f"root_bundle: signature set refused ({reason})")

    # §C.1 step 4 — validity window against the trusted now; exact process-scope binding.
    if now_us < bundle.valid_from:
        _refuse("NOT_YET_VALID", f"root_bundle: valid_from={bundle.valid_from} > now_us={now_us}")
    if now_us > bundle.valid_to:
        _refuse("EXPIRED", f"root_bundle: valid_to={bundle.valid_to} < now_us={now_us}")
    if (scope["repository"] != _PROCESS_SCOPE["repository"]
            or scope["environment"] != _PROCESS_SCOPE["environment"]):
        _refuse("SCOPE_MISMATCH",
                f"root_bundle: scope {scope!r} != process scope {_PROCESS_SCOPE!r}")

    return sha256_hex(signing_bytes)


def _check_external_pins(manifest: dict) -> int:
    """Structurally validate the recorded external pins (name + expected_sha256, unique names).

    An external pin names an OUT-OF-REPO artifact by digest; the manifest supplies no byte payload
    for it, so there is nothing to hash here — the pin is recorded expectation, checked closed.
    """
    pins = manifest["external_pins"]
    if not isinstance(pins, list):
        _refuse("MALFORMED_PREIMAGE", "external_pins: must be an array")
    seen: set = set()
    for index, item in enumerate(pins):
        what = f"external_pins[{index}]"
        entry = _check_entry_keys(item, what, allowed=("name", "expected_sha256"),
                                  required=("name", "expected_sha256"))
        name = entry["name"]
        if not isinstance(name, str) or not name.strip():
            _refuse("MALFORMED_PREIMAGE", f"{what}: name must be a nonempty string")
        if name in seen:
            _refuse("MALFORMED_PREIMAGE", f"{what}: duplicate pin name {name!r}")
        seen.add(name)
        _require_hex64(entry["expected_sha256"], what)
    return len(pins)


def verify_authority(manifest_path: pathlib.Path, now_us: int) -> dict:
    """The full §C.2 authority verification. Raises :class:`AuthorityRefusal`; returns facts."""
    if not isinstance(now_us, int) or isinstance(now_us, bool) or now_us <= 0:
        _refuse("UNAVAILABLE_AUTHORITY", f"no trusted clock: now_us={now_us!r}")
    try:
        manifest = _parse_manifest(manifest_path)
        base_dir = manifest_path.resolve().parent
        trust, trust_bytes = _verified_trust(manifest, base_dir)
        decision_count = _verify_decisions(manifest, base_dir, trust, now_us)
        signed_root_digest = _verify_root_bundle(manifest, base_dir, trust, trust_bytes, now_us)
        pin_count = _check_external_pins(manifest)
    except contracts.SchemaValidatorUnavailable as exc:
        # No schema validator => the authority material CANNOT be authenticated. Fail closed.
        _refuse("UNAVAILABLE_AUTHORITY", f"schema validator unavailable: {exc}")
    return {
        "signed_root_digest": signed_root_digest,
        "decisions": decision_count,
        "external_pins": pin_count,
    }


# --- SELF_TEST (synthetic; clearly labeled; never a substitute for the real --authority path) -----
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
    """SELF_TEST: authenticate a real capability, then prove six authenticity attacks are refused."""
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
                        help="the §C.2 authority preimage manifest; absent => UNAVAILABLE_AUTHORITY"
                             " (nonzero exit — absence is never a green PASS)")
    parser.add_argument("--now-us", type=int, default=None,
                        help="trusted now (UTC epoch microseconds); default: the tool-layer clock")
    parser.add_argument("--selftest", action="store_true",
                        help="run the labeled SELF_TEST (six-attack synthetic authenticity drill; "
                             "never a substitute for the real --authority path)")
    args = parser.parse_args(argv)

    try:
        if args.selftest:
            result = selftest()
            for name, reason in sorted(result["attacks"].items()):
                print(f"  SELF_TEST attack {name:28s} -> {reason}")
            if not result["all_attacks_refused"]:
                print("SELF_TEST FAIL: an authenticity attack WRONGLY BUILT a capability",
                      file=sys.stderr)
                return 1
            print(f"SELF_TEST OK: capability authenticated; all 6 attacks refused "
                  f"(bundle rows={result['row_count']}). SELF_TEST is synthetic and never a "
                  f"substitute for the real --authority path.")
            return 0

        if args.authority is not None:
            # The REAL owner-gated path (§C.2): full authentication or a nonzero exit carrying
            # exactly ONE typed reason token on stdout.
            now_us = args.now_us if args.now_us is not None else time.time_ns() // 1_000
            try:
                facts = verify_authority(args.authority, now_us)
            except AuthorityRefusal as exc:
                print(exc.token)
                print(f"authority refused: {exc.token}: {exc.detail}", file=sys.stderr)
                return 2
            print(f"AUTHORITY_VERIFIED signed_root_digest={facts['signed_root_digest']} "
                  f"decisions={facts['decisions']} external_pins={facts['external_pins']}")
            return 0

        # No --authority: the inventory duty still runs (its facts on stderr), but the owner-gated
        # path was NOT run, so the run is NONZERO with the single typed reason on stdout —
        # absence of the argument is never a green PASS (the historical exit-0 was the defect).
        bundle_path = args.bundle if args.bundle is not None else bindings.DEFAULT_REGISTRY_PATH
        facts = verify_bundle(bundle_path)
        print(f"bundle rows={facts['row_count']} status_counts={facts['status_counts']} "
              f"source_bundle_digest={facts['source_bundle_digest'][:16]}", file=sys.stderr)
        print("UNAVAILABLE_AUTHORITY")
        print("bundle inventory verified, but no --authority preimage was supplied, so the "
              "owner-gated authentication path was NOT run; failing closed (exit 2, never a "
              "PASS). Supply --authority <manifest> for the real path.", file=sys.stderr)
        return 2
    except contracts.SchemaValidatorUnavailable as exc:
        print(f"SCHEMA_VALIDATOR_UNAVAILABLE: {exc}", file=sys.stderr)
        return 3
    except bindings.BindingRegistryError as exc:
        print(f"FAIL: bundle inventory invalid: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
