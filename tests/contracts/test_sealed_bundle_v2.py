"""B02C spec §C.1 — SealedParameterBundle v2: content-addressed, unforgeable by construction.

A Python object is never a security boundary. ``_CONSTRUCTION_TOKEN`` is deleted; construction of
every type is UNRESTRICTED and acceptance is what is guarded: ``transition.require_bundle``
re-verifies the full content law on EVERY call and only then returns a ``VerifiedCapability``.
Every adversarial channel below must FAIL TO REACH acceptance — forging acceptance requires
forging Ed25519 signatures over the pinned trust registry.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import importlib
import json
import pathlib
import pickle
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import bindings, transition  # noqa: E402
from triad_origin.canonical import canonical_json, sha256_hex  # noqa: E402

OWNER_KID = "k-owner-v2"
OWNER_PK = "ab" * 32
REPOSITORY = "TriadOrigin"
ENVIRONMENT = "OFF"
VALID_FROM = 1_000_000
VALID_TO = 9_000_000
NOW_US = 2_000_000


def _trust(role: str = "AUTHORITY_OWNER", revoked: bool = False,
           nb: int | None = None, na: int | None = None) -> dict:
    entry = {"key_id": OWNER_KID, "identity": "owner@triad", "role": role,
             "algorithm": "ed25519", "public_key_hex": OWNER_PK, "revoked": revoked}
    if nb is not None:
        entry["not_before_us"] = nb
    if na is not None:
        entry["not_after_us"] = na
    return {OWNER_KID: entry}


def _trust_bytes(trust: dict) -> bytes:
    return json.dumps(trust, sort_keys=True).encode("utf-8")


def _bytes_bound_verify(pk: str, msg: bytes, sig_hex: str) -> bool:
    """A 128-hex stand-in signature bound to the exact bytes (the existing b01c pattern)."""
    return sig_hex == hashlib.sha512(msg + bytes.fromhex(pk)).hexdigest()


def _standin_sign(msg: bytes, pk: str = OWNER_PK, kid: str = OWNER_KID) -> dict:
    return {"key_id": kid, "signature_hex": hashlib.sha512(msg + bytes.fromhex(pk)).hexdigest()}


def _signing_bytes_for(bundle) -> bytes:
    return bindings.sealed_bundle_signing_bytes(
        canonical_root_digest=bundle.canonical_root_digest,
        scope=bundle.scope, valid_from=bundle.valid_from, valid_to=bundle.valid_to)


@pytest.fixture(scope="module")
def registry():
    return bindings.load_registry()


@pytest.fixture(autouse=True)
def _fresh_process_state():
    bindings._reset_trust_registry_pin_for_tests()
    bindings._reset_acceptance_memo_for_tests()
    yield
    bindings._reset_trust_registry_pin_for_tests()
    bindings._reset_acceptance_memo_for_tests()


def _pin_for(trust: dict) -> tuple[bytes, str]:
    raw = _trust_bytes(trust)
    digest = sha256_hex(raw)
    bindings.pin_trust_registry_digest(digest)
    return raw, digest


def _genuine(registry, trust: dict, *, environment: str = ENVIRONMENT,
             valid_from: int = VALID_FROM, valid_to: int = VALID_TO):
    """Build + sign a genuine sealed bundle over the real registry with the stand-in key."""
    _raw, digest = _pin_for(trust)
    unsigned = bindings.build_sealed_bundle(
        registry, repository=REPOSITORY, environment=environment,
        valid_from=valid_from, valid_to=valid_to,
        trust_registry_digest=digest, signer_set=[OWNER_KID])
    sig = _standin_sign(_signing_bytes_for(unsigned))
    return dataclasses.replace(unsigned, signatures=[sig])


def _ctx(trust: dict, *, now_us: int = NOW_US, environment: str = ENVIRONMENT,
         verify_fn=_bytes_bound_verify, pin: str | None = None):
    return bindings.VerificationContext(
        trust=trust, trust_registry_bytes=_trust_bytes(trust), now_us=now_us,
        process_scope={"repository": REPOSITORY, "environment": environment},
        verify_fn=verify_fn, expected_digest_pin=pin)


def _require(bundle, ctx, parameter_id: str = "PAR-001", formula_id: str = "F00"):
    return transition.require_bundle(bundle, parameter_id, formula_id=formula_id, ctx=ctx)


def _rejected(bundle, ctx, prefix: str, **kw) -> None:
    with pytest.raises(bindings.SealedBundleRejected) as excinfo:
        _require(bundle, ctx, **kw)
    assert excinfo.value.reason.startswith(prefix), excinfo.value.reason


def _resign_row(row: dict) -> dict:
    unsigned = {k: v for k, v in row.items() if k != "binding_digest"}
    row["binding_digest"] = sha256_hex(canonical_json(unsigned))
    return row


def _reroot(bundle, rows: list):
    """A self-consistent variant over a DIFFERENT row set, properly re-signed (stand-in key)."""
    root = bindings.canonical_rows_digest(rows)
    preimages = sorted(sha256_hex(canonical_json(r)) for r in rows)
    unsigned = dataclasses.replace(
        bundle, rows=rows, canonical_root_digest=root, row_preimage_digests=preimages,
        signatures=[])
    sig = _standin_sign(_signing_bytes_for(unsigned))
    return dataclasses.replace(unsigned, signatures=[sig])


def _forged(registry) -> "bindings.SealedParameterBundle":
    """Exact-class construction with fabricated maps: a tampered ACTIVE value, self-consistent
    digests, and a self-invented signature no trust registry knows."""
    rows = registry.rows()
    for row in rows:
        if row["binding_id"] == "FPB-0001":
            row["declared_value"] = "attacker-chosen"
            _resign_row(row)
    root = bindings.canonical_rows_digest(rows)
    forged = bindings.SealedParameterBundle(
        schema_version=bindings.SEALED_SCHEMA_VERSION,
        scope={"repository": REPOSITORY, "environment": ENVIRONMENT},
        rows=rows,
        canonical_root_digest=root,
        trust_registry_digest=sha256_hex(_trust_bytes(_trust())),
        signer_set=[OWNER_KID],
        signatures=[{"key_id": OWNER_KID, "signature_hex": "cd" * 64}],
        valid_from=VALID_FROM,
        valid_to=VALID_TO,
        formula_coverage=bindings.derive_formula_coverage(registry),
        row_preimage_digests=sorted(sha256_hex(canonical_json(r)) for r in rows),
    )
    # Bolt the v1 forgery marker on for good measure: acceptance must ignore it entirely.
    object.__setattr__(forged, "verification_reason", "OK")
    return forged


# -- the happy path: a real Ed25519 fixture keypair -------------------------------------------------

class TestHappyPathRealEd25519:
    def test_real_ed25519_signature_reaches_acceptance(self, registry):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey, Ed25519PublicKey)

        private = Ed25519PrivateKey.generate()
        pub_hex = private.public_key().public_bytes_raw().hex()
        trust = {OWNER_KID: {"key_id": OWNER_KID, "identity": "owner@triad",
                             "role": "AUTHORITY_OWNER", "algorithm": "ed25519",
                             "public_key_hex": pub_hex, "revoked": False}}
        raw, digest = _pin_for(trust)
        unsigned = bindings.build_sealed_bundle(
            registry, repository=REPOSITORY, environment=ENVIRONMENT,
            valid_from=VALID_FROM, valid_to=VALID_TO,
            trust_registry_digest=digest, signer_set=[OWNER_KID])
        signing = _signing_bytes_for(unsigned)
        bundle = dataclasses.replace(unsigned, signatures=[
            {"key_id": OWNER_KID, "signature_hex": private.sign(signing).hex()}])

        def ed25519_verify(public_key_hex: str, message: bytes, signature_hex: str) -> bool:
            try:
                key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
                key.verify(bytes.fromhex(signature_hex), message)
                return True
            except Exception:
                return False

        ctx = bindings.VerificationContext(
            trust=trust, trust_registry_bytes=raw, now_us=NOW_US,
            process_scope={"repository": REPOSITORY, "environment": ENVIRONMENT},
            verify_fn=ed25519_verify)
        cap = _require(bundle, ctx)
        assert type(cap) is bindings.VerifiedCapability
        assert cap.parameter_id == "PAR-001" and cap.formula_id == "F00"
        assert cap.value == "price_ticks=exact_div(venue_price,tick_size)"
        # The two digest faces: partial content identity vs the actually-signed canonical root.
        assert cap.source_bundle_digest == bindings.canonical_rows_digest(registry.rows())
        assert cap.signed_root_digest == sha256_hex(signing)
        assert cap.source_bundle_digest != cap.signed_root_digest
        assert cap.signer_key_ids == (OWNER_KID,)
        assert cap.row["binding_id"] == "FPB-0001"

        # cross_check function: the pin agrees with the "repository" trust bytes.
        bindings.cross_check_trust_registry_pin(raw)


# -- adversarial: every laundering channel fails to reach acceptance -------------------------------

class TestForgeryChannels:
    def test_exact_class_construction_with_fabricated_maps_refused(self, registry):
        _pin_for(_trust())
        forged = _forged(registry)
        _rejected(forged, _ctx(_trust()), "SIGNATURE_INVALID:")

    def test_construction_token_is_deleted_and_module_holds_no_ambient_capability(self):
        names = set(vars(bindings))
        assert "_CONSTRUCTION_TOKEN" not in names
        for value in vars(bindings).values():
            assert not isinstance(
                value,
                (bindings.SealedParameterBundle, bindings.VerifiedCapability,
                 bindings.ResolvedParameterBundle))

    def test_subclass_with_fabricated_content_refused(self, registry):
        _pin_for(_trust())

        class Widened(bindings.SealedParameterBundle):
            pass

        forged = _forged(registry)
        sub = Widened(**{name: object.__getattribute__(forged, name)
                         for name in bindings.SEALED_FIELDS})
        _rejected(sub, _ctx(_trust()), "SIGNATURE_INVALID:")

    def test_copy_deepcopy_pickle_roundtrips_launder_nothing(self, registry):
        forged = _forged(registry)
        _pin_for(_trust())
        ctx = _ctx(_trust())
        for laundered in (copy.copy(forged), copy.deepcopy(forged),
                          pickle.loads(pickle.dumps(forged))):
            _rejected(laundered, ctx, "SIGNATURE_INVALID:")

    def test_copy_of_a_genuine_bundle_is_the_same_signed_content(self, registry):
        # The content law: a faithful copy IS the signed content and verifies identically —
        # copying launders nothing and grants nothing beyond what the signature already grants.
        genuine = _genuine(registry, _trust())
        ctx = _ctx(_trust())
        original = _require(genuine, ctx)
        copied = _require(copy.deepcopy(genuine), ctx)
        assert copied.signed_root_digest == original.signed_root_digest

    def test_module_reload_launders_nothing(self, registry):
        reloaded = importlib.reload(bindings)
        try:
            reloaded._reset_trust_registry_pin_for_tests()
            reloaded._reset_acceptance_memo_for_tests()
            trust = _trust()
            raw = _trust_bytes(trust)
            reloaded.pin_trust_registry_digest(sha256_hex(raw))
            rows = registry.rows()
            for row in rows:
                if row["binding_id"] == "FPB-0001":
                    row["declared_value"] = "attacker-chosen"
                    _resign_row(row)
            forged = reloaded.SealedParameterBundle(
                schema_version=reloaded.SEALED_SCHEMA_VERSION,
                scope={"repository": REPOSITORY, "environment": ENVIRONMENT},
                rows=rows,
                canonical_root_digest=reloaded.canonical_rows_digest(rows),
                trust_registry_digest=sha256_hex(raw),
                signer_set=[OWNER_KID],
                signatures=[{"key_id": OWNER_KID, "signature_hex": "cd" * 64}],
                valid_from=VALID_FROM, valid_to=VALID_TO,
                formula_coverage=reloaded.derive_formula_coverage(registry),
                row_preimage_digests=sorted(
                    sha256_hex(canonical_json(r)) for r in rows),
            )
            ctx = reloaded.VerificationContext(
                trust=trust, trust_registry_bytes=raw, now_us=NOW_US,
                process_scope={"repository": REPOSITORY, "environment": ENVIRONMENT},
                verify_fn=_bytes_bound_verify)
            with pytest.raises(reloaded.SealedBundleRejected) as excinfo:
                transition.require_bundle(forged, "PAR-001", formula_id="F00", ctx=ctx)
            assert excinfo.value.reason.startswith("SIGNATURE_INVALID:")
        finally:
            reloaded._reset_trust_registry_pin_for_tests()
            reloaded._reset_acceptance_memo_for_tests()

    def test_private_field_mutation_fails_the_content_law(self, registry):
        genuine = _genuine(registry, _trust())
        ctx = _ctx(_trust())
        _require(genuine, ctx)  # sane before mutation

        mutated = copy.deepcopy(genuine)
        rows = mutated.rows
        rows[0] = dict(rows[0])
        rows[0]["declared_value"] = "attacker-chosen"
        _resign_row(rows[0])
        # Coordinated private mutation: rows AND their preimages — the recomputed root still
        # disagrees with the carried (signed) digest, so the content law catches it.
        object.__setattr__(mutated, "rows", rows)
        object.__setattr__(mutated, "row_preimage_digests",
                           sorted(sha256_hex(canonical_json(r)) for r in rows))
        _rejected(mutated, ctx, "ROOT_DIGEST_MISMATCH")

        dict_mutated = copy.deepcopy(genuine)
        dict_mutated.__dict__["canonical_root_digest"] = "0" * 64
        _rejected(dict_mutated, ctx, "ROOT_DIGEST_MISMATCH")

    def test_raw_dict_refused_at_the_production_path(self, registry):
        _pin_for(_trust())
        genuine = _genuine(registry, _trust())
        as_dict = {name: object.__getattribute__(genuine, name)
                   for name in bindings.SEALED_FIELDS}
        with pytest.raises(bindings.CapabilityForgeryError):
            _require(as_dict, _ctx(_trust()))


# -- adversarial: scope / validity / signer set ----------------------------------------------------

class TestScopeValidityAndSigners:
    def test_scope_widening_refused_in_both_directions(self, registry):
        # A LIVE-scoped bundle presented to an OFF-bound process…
        live_bundle = _genuine(registry, _trust(), environment="LIVE")
        _rejected(live_bundle, _ctx(_trust(), environment=ENVIRONMENT), "SCOPE_MISMATCH")
        # …and an OFF-scoped bundle presented to a LIVE-bound process.
        bindings._reset_trust_registry_pin_for_tests()
        off_bundle = _genuine(registry, _trust(), environment=ENVIRONMENT)
        _rejected(off_bundle, _ctx(_trust(), environment="LIVE"), "SCOPE_MISMATCH")

    def test_expired_validity_refused(self, registry):
        bundle = _genuine(registry, _trust())
        _rejected(bundle, _ctx(_trust(), now_us=VALID_TO + 1), "EXPIRED")

    def test_not_yet_valid_refused(self, registry):
        bundle = _genuine(registry, _trust())
        _rejected(bundle, _ctx(_trust(), now_us=VALID_FROM - 1), "NOT_YET_VALID")

    def test_revoked_signer_refused(self, registry):
        trust = _trust(revoked=True)
        bundle = _genuine(registry, trust)
        _rejected(bundle, _ctx(trust), "SIGNATURE_INVALID:REVOKED_SIGNER")

    def test_absent_verifier_is_fail_closed(self, registry):
        bundle = _genuine(registry, _trust())
        _rejected(bundle, _ctx(_trust(), verify_fn=None),
                  "SIGNATURE_INVALID:VERIFY_UNAVAILABLE")

    def test_duplicate_signer_counted_once_toward_threshold(self, registry):
        bundle = _genuine(registry, _trust())
        doubled = dataclasses.replace(
            bundle, signatures=[bundle.signatures[0], dict(bundle.signatures[0])])
        _rejected(doubled, _ctx(_trust()), "SIGNATURE_INVALID:DUPLICATE_SIGNER_IDENTITY")

    def test_signature_from_a_key_outside_the_declared_signer_set_refused(self, registry):
        bundle = _genuine(registry, _trust())
        stranger = dataclasses.replace(
            bundle, signatures=[{"key_id": "stranger", "signature_hex": "cd" * 64}])
        _rejected(stranger, _ctx(_trust()), "SIGNER_NOT_IN_SET:")


# -- adversarial: content identity ------------------------------------------------------------------

class TestContentIdentity:
    def test_wrong_root_digest_refused(self, registry):
        bundle = _genuine(registry, _trust())
        wrong = dataclasses.replace(bundle, canonical_root_digest="e3" * 32)
        _rejected(wrong, _ctx(_trust()), "ROOT_DIGEST_MISMATCH")

    def test_reordering_rows_does_not_change_the_digest(self, registry):
        rows = registry.rows()
        assert (bindings.canonical_rows_digest(rows)
                == bindings.canonical_rows_digest(list(reversed(rows))))

    def test_reordered_rows_still_reach_acceptance_with_the_same_signature(self, registry):
        bundle = _genuine(registry, _trust())
        ctx = _ctx(_trust())
        reordered = dataclasses.replace(bundle, rows=list(reversed(bundle.rows)))
        cap = _require(reordered, ctx)
        assert cap.signed_root_digest == _require(bundle, ctx).signed_root_digest

    def test_a_truly_different_row_set_fails(self, registry):
        bundle = _genuine(registry, _trust())
        rows = [dict(r) for r in bundle.rows]
        for row in rows:
            if row["binding_id"] == "FPB-0001":
                row["declared_value"] = "attacker-chosen"
                _resign_row(row)
        # Preimages recomputed to agree with the tampered rows: the recompute-and-compare of the
        # carried root digest (step 1) is what refuses the different set.
        different = dataclasses.replace(
            bundle, rows=rows,
            row_preimage_digests=sorted(sha256_hex(canonical_json(r)) for r in rows))
        _rejected(different, _ctx(_trust()), "ROOT_DIGEST_MISMATCH")
        # And with stale preimages the earlier content-integrity arm refuses instead.
        stale = dataclasses.replace(bundle, rows=rows)
        _rejected(stale, _ctx(_trust()), "ROW_PREIMAGE_MISMATCH")

    def test_row_preimage_digest_mismatch_refused(self, registry):
        bundle = _genuine(registry, _trust())
        preimages = list(bundle.row_preimage_digests)
        preimages[0] = "f" * 64
        tampered = dataclasses.replace(bundle, row_preimage_digests=preimages)
        _rejected(tampered, _ctx(_trust()), "ROW_PREIMAGE_MISMATCH")

    def test_104_row_inventory_refused_even_when_signed(self, registry):
        bundle = _genuine(registry, _trust())
        short = _reroot(bundle, [dict(r) for r in bundle.rows][:-1])
        _rejected(short, _ctx(_trust()), "ROW_COUNT_INVALID:104")

    def test_106_row_inventory_refused_even_when_signed(self, registry):
        bundle = _genuine(registry, _trust())
        rows = [dict(r) for r in bundle.rows]
        extra = dict(rows[0])
        extra["binding_id"] = "FPB-9999"
        extra["semantic_slot"] = rows[0]["semantic_slot"] + "__extra"
        _resign_row(extra)
        long = _reroot(bundle, rows + [extra])
        _rejected(long, _ctx(_trust()), "ROW_COUNT_INVALID:106")


# -- adversarial: wire shape -------------------------------------------------------------------------

class TestWireShape:
    def _as_doc(self, bundle) -> dict:
        return {name: object.__getattribute__(bundle, name)
                for name in bindings.SEALED_FIELDS}

    def test_unknown_field_rejected(self, registry):
        doc = self._as_doc(_genuine(registry, _trust()))
        doc["verification_reason"] = "OK"
        with pytest.raises(bindings.SealedBundleRejected) as excinfo:
            bindings.SealedParameterBundle.from_dict(doc)
        assert excinfo.value.reason == "UNKNOWN_FIELD:verification_reason"

    def test_missing_field_rejected(self, registry):
        doc = self._as_doc(_genuine(registry, _trust()))
        del doc["signatures"]
        with pytest.raises(bindings.SealedBundleRejected) as excinfo:
            bindings.SealedParameterBundle.from_dict(doc)
        assert excinfo.value.reason == "MISSING_FIELD:signatures"

    def test_duplicate_scope_key_rejected(self, registry):
        doc = self._as_doc(_genuine(registry, _trust()))
        text = json.dumps(doc)
        dup = text.replace(
            '"scope": {"repository":', '"scope": {"repository": "shadow", "repository":', 1)
        assert dup != text  # the duplication actually landed in the document
        with pytest.raises(bindings.SealedBundleRejected) as excinfo:
            bindings.SealedParameterBundle.from_json(dup)
        assert excinfo.value.reason == "DUPLICATE_OBJECT_KEY:repository"

    def test_from_json_round_trips_a_genuine_bundle(self, registry):
        genuine = _genuine(registry, _trust())
        doc = self._as_doc(genuine)
        parsed = bindings.SealedParameterBundle.from_json(json.dumps(doc))
        cap = _require(parsed, _ctx(_trust()))
        assert cap.value == "price_ticks=exact_div(venue_price,tick_size)"

    def test_float_in_wire_document_rejected(self, registry):
        doc = self._as_doc(_genuine(registry, _trust()))
        text = json.dumps(doc).replace(f'"valid_from": {VALID_FROM}',
                                       '"valid_from": 1.5', 1)
        with pytest.raises(bindings.SealedBundleRejected) as excinfo:
            bindings.SealedParameterBundle.from_json(text)
        assert excinfo.value.reason.startswith("SEALED_SHAPE_INVALID:float")


# -- coverage / formula law --------------------------------------------------------------------------

class TestFormulaCoverage:
    def test_blocked_formula_is_a_typed_blocked_binding_incomplete(self, registry):
        bundle = _genuine(registry, _trust())
        with pytest.raises(bindings.BlockedBindingIncomplete) as excinfo:
            _require(bundle, _ctx(_trust()), parameter_id="anything", formula_id="F08")
        assert excinfo.value.formula_id == "F08"
        assert str(excinfo.value) == "BLOCKED_BINDING_INCOMPLETE:F08"

    def test_one_active_row_never_hides_blocked_siblings(self, registry):
        # F21 carries one ACTIVE row among blocked rows: incomplete, never consumable.
        bundle = _genuine(registry, _trust())
        with pytest.raises(bindings.BlockedBindingIncomplete) as excinfo:
            _require(bundle, _ctx(_trust()),
                     parameter_id="RC3-PAR-EXEC-001", formula_id="F21")
        assert excinfo.value.formula_id == "F21"

    def test_coverage_map_must_carry_all_24_formula_ids(self, registry):
        bundle = _genuine(registry, _trust())
        coverage = dict(bundle.formula_coverage)
        del coverage["F23"]
        _rejected(dataclasses.replace(bundle, formula_coverage=coverage),
                  _ctx(_trust()), "COVERAGE_INVALID:")

    def test_coverage_saying_active_over_blocked_rows_still_refuses(self, registry):
        # The signature binds root+scope+validity, so a coverage flip leaves the signature
        # intact — but the rows themselves are re-checked in step 5, and a lying map can only
        # ever cause refusal, never admit a blocked formula.
        bundle = _genuine(registry, _trust())
        coverage = dict(bundle.formula_coverage)
        coverage["F08"] = "ACTIVE"  # a lying map cannot out-vote the rows themselves
        lying = dataclasses.replace(bundle, formula_coverage=coverage)
        with pytest.raises(bindings.BlockedBindingIncomplete):
            _require(lying, _ctx(_trust()), parameter_id="anything", formula_id="F08")

    def test_unknown_requesting_formula_refused(self, registry):
        bundle = _genuine(registry, _trust())
        _rejected(bundle, _ctx(_trust()), "UNKNOWN_FORMULA:",
                  parameter_id="PAR-001", formula_id="F99")

    def test_unknown_parameter_fails_closed(self, registry):
        bundle = _genuine(registry, _trust())
        with pytest.raises(bindings.BindingUnknownError):
            _require(bundle, _ctx(_trust()), parameter_id="NO_SUCH_PARAMETER")


# -- the process trust pin + memoization law ----------------------------------------------------------

class TestTrustPinAndMemo:
    def test_unpinned_process_refuses_acceptance(self, registry):
        trust = _trust()
        raw = _trust_bytes(trust)
        unsigned = bindings.build_sealed_bundle(
            registry, repository=REPOSITORY, environment=ENVIRONMENT,
            valid_from=VALID_FROM, valid_to=VALID_TO,
            trust_registry_digest=sha256_hex(raw), signer_set=[OWNER_KID])
        bundle = dataclasses.replace(
            unsigned, signatures=[_standin_sign(_signing_bytes_for(unsigned))])
        _rejected(bundle, _ctx(trust), "TRUST_REGISTRY_UNPINNED")

    def test_pin_mismatch_and_bundle_digest_mismatch_are_distinct_refusals(self, registry):
        trust = _trust()
        bundle = _genuine(registry, trust)
        # Supplied bytes different from the bundle's declared digest.
        other = dict(trust)
        other["k-extra"] = {"key_id": "k-extra", "identity": "x@triad",
                            "role": "AUTHORITY_OWNER", "algorithm": "ed25519",
                            "public_key_hex": "cd" * 32, "revoked": False}
        ctx = bindings.VerificationContext(
            trust=trust, trust_registry_bytes=_trust_bytes(other), now_us=NOW_US,
            process_scope={"repository": REPOSITORY, "environment": ENVIRONMENT},
            verify_fn=_bytes_bound_verify)
        _rejected(bundle, ctx, "TRUST_REGISTRY_DIGEST_MISMATCH")
        # Pin repointed to a different registry: the bundle agrees with the bytes, the pin does not.
        bindings._reset_trust_registry_pin_for_tests()
        bindings.pin_trust_registry_digest(sha256_hex(_trust_bytes(other)))
        _rejected(bundle, _ctx(trust), "TRUST_REGISTRY_PIN_MISMATCH")

    def test_pin_is_set_once(self):
        bindings.pin_trust_registry_digest("a" * 64)
        bindings.pin_trust_registry_digest("a" * 64)  # idempotent same-value re-pin
        with pytest.raises(bindings.TrustRegistryPinError):
            bindings.pin_trust_registry_digest("b" * 64)
        assert bindings.pinned_trust_registry_digest() == "a" * 64

    def test_cross_check_against_repository_bytes(self):
        raw = b"trust-registry-file-bytes"
        bindings.pin_trust_registry_digest(sha256_hex(raw))
        bindings.cross_check_trust_registry_pin(raw)  # agrees — no raise
        with pytest.raises(bindings.TrustRegistryPinError):
            bindings.cross_check_trust_registry_pin(raw + b"tampered")

    def test_memoization_only_by_digest_and_never_launders(self, registry):
        trust = _trust()
        bundle = _genuine(registry, trust)
        calls = {"n": 0}

        def counting_verify(pk, msg, sig_hex):
            calls["n"] += 1
            return _bytes_bound_verify(pk, msg, sig_hex)

        # Without a pin: crypto runs on EVERY call.
        ctx_nopin = _ctx(trust, verify_fn=counting_verify)
        _require(bundle, ctx_nopin)
        _require(bundle, ctx_nopin)
        assert calls["n"] == 2

        # With the process-pinned expected digest: memo by digest, crypto skipped on the rerun.
        pin = _require(bundle, ctx_nopin).signed_root_digest
        ctx_pinned = _ctx(trust, verify_fn=counting_verify, pin=pin)
        _require(bundle, ctx_pinned)   # full verification + memo record
        before = calls["n"]
        cap = _require(bundle, ctx_pinned)  # memo hit — no new crypto call
        assert calls["n"] == before
        assert cap.signed_root_digest == pin

        # The memo can never launder: same signed root, stripped signatures — refused.
        stripped = dataclasses.replace(bundle, signatures=[])
        _rejected(stripped, ctx_pinned, "SIGNATURE_INVALID:NO_EXTERNAL_SIGNATURES")
        # …and tampered rows under the same pin — refused before any signature question.
        rows = [dict(r) for r in bundle.rows]
        for row in rows:
            if row["binding_id"] == "FPB-0001":
                row["declared_value"] = "attacker-chosen"
                _resign_row(row)
        tampered = dataclasses.replace(
            bundle, rows=rows,
            row_preimage_digests=sorted(sha256_hex(canonical_json(r)) for r in rows))
        _rejected(tampered, ctx_pinned, "ROOT_DIGEST_MISMATCH")

    def test_expired_bundle_refuses_even_after_a_memo_hit(self, registry):
        trust = _trust()
        bundle = _genuine(registry, trust)
        pin = _require(bundle, _ctx(trust)).signed_root_digest
        ctx_pinned = _ctx(trust, pin=pin)
        _require(bundle, ctx_pinned)  # memo recorded
        _rejected(bundle, _ctx(trust, now_us=VALID_TO + 1, pin=pin), "EXPIRED")
