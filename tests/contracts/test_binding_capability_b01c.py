"""B01C binding capability battery — REWRITTEN to the B02C spec §C.1 v2 law.

The structural registry law (105 rows, per-row digests, no-blocked-consumption) is proven in
``test_binding_v2.py`` and stays below (loader hardening). The v1 construction-token pins are
GONE: ``_CONSTRUCTION_TOKEN`` is deleted, construction of every type is unrestricted, and
ACCEPTANCE is what is guarded — ``transition.require_bundle`` re-verifies the sealed bundle's
content (root digest · pinned trust registry · Ed25519 signature set · validity window · scope ·
formula coverage) on EVERY call and only then returns a ``VerifiedCapability``. The exhaustive
adversarial battery lives in ``test_sealed_bundle_v2.py``; this file keeps the B01C-shaped
authenticity/forgery/consumption drills on the v2 acceptance path.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import bindings, transition  # noqa: E402
from triad_origin.canonical import canonical_json, sha256_hex  # noqa: E402

REGISTRY_PATH = ROOT / "docs" / "control" / "binding_registry.v2.json"
REGISTRY = json.loads(REGISTRY_PATH.read_text())

OWNER_KID = "k-owner-b01c"
OWNER_PK = "ab" * 32
REPOSITORY = "TriadOrigin"
ENVIRONMENT = "OFF"
VALID_FROM = 1_000
VALID_TO = 5_000_000
NOW_US = 2_000


def _resign(row: dict) -> dict:
    unsigned = {k: v for k, v in row.items() if k != "binding_digest"}
    row["binding_digest"] = sha256_hex(canonical_json(unsigned))
    return row


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
    """A 128-hex stand-in signature bound to the exact bytes (Ed25519 encoding shape)."""
    return sig_hex == hashlib.sha512(msg + bytes.fromhex(pk)).hexdigest()


def _sign_over(bundle) -> dict:
    """Produce a signature over the exact canonical signing bytes acceptance will recompute."""
    signing = bindings.sealed_bundle_signing_bytes(
        canonical_root_digest=bundle.canonical_root_digest, scope=bundle.scope,
        valid_from=bundle.valid_from, valid_to=bundle.valid_to)
    sig_hex = hashlib.sha512(signing + bytes.fromhex(OWNER_PK)).hexdigest()
    return {"key_id": OWNER_KID, "signature_hex": sig_hex}


@pytest.fixture(scope="module")
def registry() -> bindings.BindingRegistry:
    return bindings.load_registry()


@pytest.fixture(autouse=True)
def _fresh_process_state():
    bindings._reset_trust_registry_pin_for_tests()
    bindings._reset_acceptance_memo_for_tests()
    yield
    bindings._reset_trust_registry_pin_for_tests()
    bindings._reset_acceptance_memo_for_tests()


def _bundle(registry, trust: dict, *, signatures=None) -> bindings.SealedParameterBundle:
    raw = _trust_bytes(trust)
    bindings.pin_trust_registry_digest(sha256_hex(raw))
    unsigned = bindings.build_sealed_bundle(
        registry, repository=REPOSITORY, environment=ENVIRONMENT,
        valid_from=VALID_FROM, valid_to=VALID_TO,
        trust_registry_digest=sha256_hex(raw), signer_set=[OWNER_KID])
    if signatures is None:
        signatures = [_sign_over(unsigned)]
    return dataclasses.replace(unsigned, signatures=signatures)


def _ctx(trust: dict, *, now_us: int = NOW_US, verify_fn=_bytes_bound_verify):
    return bindings.VerificationContext(
        trust=trust, trust_registry_bytes=_trust_bytes(trust), now_us=now_us,
        process_scope={"repository": REPOSITORY, "environment": ENVIRONMENT},
        verify_fn=verify_fn)


def _require(bundle, ctx, parameter_id: str = "PAR-001", formula_id: str = "F00"):
    return transition.require_bundle(bundle, parameter_id, formula_id=formula_id, ctx=ctx)


# -- BIND-01 (v2): bundle authenticity — enforced at ACCEPTANCE, on every call ---------------------

class TestBundleAuthenticity:
    def test_valid_owner_signature_reaches_acceptance(self, registry):
        trust = _trust()
        cap = _require(_bundle(registry, trust), _ctx(trust))
        assert type(cap) is bindings.VerifiedCapability
        assert cap.signer_key_ids == (OWNER_KID,)
        # The renamed digest faces: partial content identity vs the actually-signed root.
        assert cap.source_bundle_digest == bindings.canonical_rows_digest(registry.rows())
        assert cap.source_bundle_digest != cap.signed_root_digest

    def test_absent_verifier_is_fail_closed(self, registry):
        trust = _trust()
        bundle = _bundle(registry, trust)
        with pytest.raises(bindings.SealedBundleRejected, match="VERIFY_UNAVAILABLE"):
            _require(bundle, _ctx(trust, verify_fn=None))

    def test_unsigned_bundle_refused(self, registry):
        trust = _trust()
        bundle = _bundle(registry, trust, signatures=[])
        with pytest.raises(bindings.SealedBundleRejected, match="NO_EXTERNAL_SIGNATURES"):
            _require(bundle, _ctx(trust))

    def test_unknown_signer_refused(self, registry):
        trust = _trust()
        bundle = _bundle(registry, trust)
        # Declared in the signer set but absent from the trust registry: UNKNOWN_SIGNER.
        bundle = dataclasses.replace(
            bundle, signer_set=[OWNER_KID, "stranger"],
            signatures=[{"key_id": "stranger", "signature_hex": "cd" * 64}])
        with pytest.raises(bindings.SealedBundleRejected, match="UNKNOWN_SIGNER"):
            _require(bundle, _ctx(trust))

    def test_signer_outside_the_declared_set_refused(self, registry):
        trust = _trust()
        bundle = _bundle(registry, trust)
        outside = dataclasses.replace(
            bundle, signatures=[{"key_id": "stranger", "signature_hex": "cd" * 64}])
        with pytest.raises(bindings.SealedBundleRejected, match="SIGNER_NOT_IN_SET"):
            _require(outside, _ctx(trust))

    def test_revoked_key_refused(self, registry):
        trust = _trust(revoked=True)
        bundle = _bundle(registry, trust)
        with pytest.raises(bindings.SealedBundleRejected, match="REVOKED_SIGNER"):
            _require(bundle, _ctx(trust))

    def test_expired_key_refused(self, registry):
        trust = _trust(na=1_000)
        bundle = _bundle(registry, trust)
        with pytest.raises(bindings.SealedBundleRejected, match="SIGNER_EXPIRED"):
            _require(bundle, _ctx(trust, now_us=2_000))

    def test_wrong_role_refused(self, registry):
        trust = _trust(role="EVIDENCE_PRODUCER")
        bundle = _bundle(registry, trust)
        with pytest.raises(bindings.SealedBundleRejected, match="MISSING_ROLE"):
            _require(bundle, _ctx(trust))

    def test_valid_signature_over_other_bytes_refused(self, registry):
        # A real signature bound to a DIFFERENT signed root (other validity window) must not
        # verify against the recomputed signing bytes: the crypto pass returns BAD_SIGNATURE.
        trust = _trust()
        bundle = _bundle(registry, trust)
        other = dataclasses.replace(bundle, valid_to=VALID_TO + 1)
        stolen = dataclasses.replace(bundle, signatures=[_sign_over(other)])
        with pytest.raises(bindings.SealedBundleRejected, match="BAD_SIGNATURE"):
            _require(stolen, _ctx(trust))


# -- BIND-05 (v2): forgery — construction is unrestricted, acceptance refuses content --------------

class TestCapabilityForgery:
    def test_construction_token_is_deleted(self):
        assert "_CONSTRUCTION_TOKEN" not in vars(bindings)

    def test_raw_dict_refused_at_production_path(self, registry):
        trust = _trust()
        bindings.pin_trust_registry_digest(sha256_hex(_trust_bytes(trust)))
        with pytest.raises(bindings.CapabilityForgeryError):
            _require({"declared_value": 1}, _ctx(trust))

    def test_fabricated_exact_class_construction_refused_at_acceptance(self, registry):
        trust = _trust()
        genuine = _bundle(registry, trust)
        rows = [dict(r) for r in genuine.rows]
        for row in rows:
            if row["binding_id"] == "FPB-0001":
                row["declared_value"] = "attacker-chosen"
                _resign(row)
        forged = dataclasses.replace(
            genuine, rows=rows,
            canonical_root_digest=bindings.canonical_rows_digest(rows),
            row_preimage_digests=sorted(sha256_hex(canonical_json(r)) for r in rows))
        # Self-consistent digests over fabricated content: only the signature law stops it.
        with pytest.raises(bindings.SealedBundleRejected, match="SIGNATURE_INVALID"):
            _require(forged, _ctx(trust))

    def test_subclass_with_fabricated_content_refused(self, registry):
        trust = _trust()
        genuine = _bundle(registry, trust)

        class Widened(bindings.SealedParameterBundle):
            pass

        rows = [dict(r) for r in genuine.rows]
        for row in rows:
            if row["binding_id"] == "FPB-0001":
                row["declared_value"] = "attacker-chosen"
                _resign(row)
        forged = Widened(
            schema_version=genuine.schema_version, scope=genuine.scope, rows=rows,
            canonical_root_digest=bindings.canonical_rows_digest(rows),
            trust_registry_digest=genuine.trust_registry_digest,
            signer_set=genuine.signer_set, signatures=genuine.signatures,
            valid_from=genuine.valid_from, valid_to=genuine.valid_to,
            formula_coverage=genuine.formula_coverage,
            row_preimage_digests=sorted(sha256_hex(canonical_json(r)) for r in rows))
        with pytest.raises(bindings.SealedBundleRejected, match="SIGNATURE_INVALID"):
            _require(forged, _ctx(trust))

    def test_mutated_capability_content_fails_on_the_next_call(self, registry):
        trust = _trust()
        bundle = _bundle(registry, trust)
        ctx = _ctx(trust)
        _require(bundle, ctx)  # accepted before mutation
        mutated = copy.deepcopy(bundle)
        object.__setattr__(mutated, "canonical_root_digest", "0" * 64)
        with pytest.raises(bindings.SealedBundleRejected, match="ROOT_DIGEST_MISMATCH"):
            _require(mutated, ctx)


# -- BIND-05 (v2): consumption through the acceptance path -----------------------------------------

class TestConsumptionThroughCapability:
    def test_require_bundle_resolves_active_parameter(self, registry):
        trust = _trust()
        active = next(r for r in registry.active_rows() if r["formula_id"] == "F00")
        cap = _require(_bundle(registry, trust), _ctx(trust),
                       parameter_id=active["parameter_id"], formula_id="F00")
        assert cap.value == active["declared_value"]
        assert cap.row["binding_id"] == active["binding_id"]

    def test_require_bundle_unknown_parameter_fails_closed(self, registry):
        trust = _trust()
        bundle = _bundle(registry, trust)
        with pytest.raises(bindings.BindingUnknownError):
            _require(bundle, _ctx(trust), parameter_id="NO_SUCH_PARAMETER")

    def test_blocked_formula_is_typed_blocked_binding_incomplete(self, registry):
        # F08 has only blocked rows in the real registry — never a consumable set.
        trust = _trust()
        bundle = _bundle(registry, trust)
        with pytest.raises(bindings.BlockedBindingIncomplete) as excinfo:
            _require(bundle, _ctx(trust), parameter_id="anything", formula_id="F08")
        assert excinfo.value.formula_id == "F08"


# -- BIND-04 / BIND-06: inventory hardening (loader-level, unchanged law) --------------------------

class TestLoaderHardening:
    def _load_mutated(self, tmp_path, mutate):
        registry = copy.deepcopy(REGISTRY)
        mutate(registry)
        path = tmp_path / "registry.json"
        path.write_text(json.dumps(registry))
        return bindings.load_registry(path)

    def test_row_count_lie_refused(self, tmp_path):
        with pytest.raises(bindings.BindingRegistryError, match="row_count"):
            self._load_mutated(tmp_path, lambda r: r.__setitem__("row_count", 104))

    def test_short_inventory_refused(self, tmp_path):
        def mutate(r):
            r["rows"] = r["rows"][:-1]
            r["row_count"] = len(r["rows"])
            last = REGISTRY["rows"][-1]["status"]
            r["status_counts"] = dict(r["status_counts"])
            r["status_counts"][last] -= 1
        with pytest.raises(bindings.BindingRegistryError, match="exactly 105"):
            self._load_mutated(tmp_path, mutate)

    def test_bad_source_bundle_digest_refused(self, tmp_path):
        with pytest.raises(bindings.BindingRegistryError, match="BUNDLE_DIGEST_INVALID"):
            self._load_mutated(tmp_path, lambda r: r.__setitem__("source_bundle_digest", "NOTHEX"))

    def test_active_sentinel_field_refused(self, tmp_path):
        def mutate(r):
            row = next(x for x in r["rows"] if x["status"] == "ACTIVE")
            row["condition"] = "TBD"
            _resign(row)
        with pytest.raises(bindings.BindingRegistryError,
                           match="ACTIVE_BINDING_UNRESOLVED_FIELD"):
            self._load_mutated(tmp_path, mutate)

    def test_active_scope_collision_refused(self, tmp_path):
        # Two ACTIVE rows sharing (parameter_id, activation_scope) but DISTINCT semantic slots
        # and binding ids: the slot-overlap and id-uniqueness checks both pass, so the scope
        # collision must be closed independently (BIND-06).
        def mutate(r):
            src = next(x for x in r["rows"] if x["binding_id"] == "FPB-0001")
            victim = next(x for x in r["rows"]
                          if x["status"] == "BLOCKED_BINDING_V2_MIGRATION")
            clone = copy.deepcopy(src)
            clone["binding_id"] = "FPB-8888"
            clone["semantic_slot"] = src["semantic_slot"] + "__alt"
            idx = r["rows"].index(victim)
            r["rows"][idx] = _resign(clone)  # keep exactly 105 rows (BIND-02)
            r["status_counts"] = dict(r["status_counts"])
            r["status_counts"]["ACTIVE"] += 1
            r["status_counts"]["BLOCKED_BINDING_V2_MIGRATION"] -= 1
        with pytest.raises(bindings.BindingRegistryError, match="SCOPE_COLLISION"):
            self._load_mutated(tmp_path, mutate)
