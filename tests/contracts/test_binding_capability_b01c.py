"""B01C-BIND-01/04/05/06 — the authenticated, sealed parameter-capability battery.

The structural registry law (105 rows, per-row digests, no-blocked-consumption) is proven in
``test_binding_v2.py``. This file adds the B01C hardening: an externally pinned owner signature
must authenticate the exact bundle root before a capability exists; the capability is unforgeable
and immutable; ACTIVE rows may carry no unresolved sentinel; and duplicate semantic scope keys are
refused independently of ``binding_id`` uniqueness. Every attack refuses with a stable reason.
"""

from __future__ import annotations

import copy
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


def _bytes_bound_verify(pk: str, msg: bytes, sig_hex: str) -> bool:
    """A stand-in for a real Ed25519 verify: the signature is bound to the exact signed bytes."""
    return sig_hex == hashlib.sha256(msg + bytes.fromhex(pk)).hexdigest()


def _sign_over(registry: bindings.BindingRegistry, **kw) -> dict:
    """Produce a signature over the exact canonical bundle root the loader will recompute."""
    root = bindings.canonical_bundle_root(
        bundle_id=kw["bundle_id"], bundle_version=kw["bundle_version"],
        source_bundle_digest=registry.source_bundle_digest(),
        authority_digest=kw["authority_digest"], engine=kw["engine"], plane=kw["plane"],
        environment=kw["environment"], scope=kw["scope"],
        row_count=registry.status_counts_total(), status_counts=registry.status_counts())
    sig_hex = hashlib.sha256(root + bytes.fromhex(OWNER_PK)).hexdigest()
    return {"key_id": OWNER_KID, "signature_hex": sig_hex}


BUNDLE_KW = dict(
    bundle_id="origin.binding-bundle.v1", bundle_version="1",
    authority_digest="a" * 64, engine="E02", plane="four_plane",
    environment="OFF", scope="repository", trust_registry_digest="b" * 64)


@pytest.fixture(scope="module")
def registry() -> bindings.BindingRegistry:
    return bindings.load_registry()


def _build(registry, *, trust=None, verify_fn=_bytes_bound_verify, signatures=None,
           now_us=None, **overrides):
    kw = {**BUNDLE_KW, **overrides}
    trust = trust if trust is not None else _trust()
    if signatures is None:
        signatures = [_sign_over(registry, **kw)]
    return bindings.build_resolved_bundle(
        registry, trust=trust, signatures=signatures, verify_fn=verify_fn, now_us=now_us, **kw)


# -- BIND-01: bundle authenticity -----------------------------------------------------------------

class TestBundleAuthenticity:
    def test_valid_owner_signature_builds(self, registry):
        cap = _build(registry)
        assert type(cap) is bindings.ResolvedParameterBundle
        assert cap.verification()["verification_reason"] == "OK"
        assert cap.verification()["signer_key_ids"] == [OWNER_KID]

    def test_absent_verifier_is_fail_closed(self, registry):
        with pytest.raises(bindings.BindingBundleUnauthenticated, match="VERIFY_UNAVAILABLE"):
            _build(registry, verify_fn=None)

    def test_unsigned_bundle_refused(self, registry):
        with pytest.raises(bindings.BindingBundleUnauthenticated, match="NO_EXTERNAL_SIGNATURES"):
            _build(registry, signatures=[])

    def test_unknown_signer_refused(self, registry):
        with pytest.raises(bindings.BindingBundleUnauthenticated, match="UNKNOWN_SIGNER"):
            _build(registry, signatures=[{"key_id": "stranger", "signature_hex": "cd" * 32}])

    def test_revoked_key_refused(self, registry):
        with pytest.raises(bindings.BindingBundleUnauthenticated, match="REVOKED_SIGNER"):
            _build(registry, trust=_trust(revoked=True))

    def test_expired_key_refused(self, registry):
        with pytest.raises(bindings.BindingBundleUnauthenticated, match="SIGNER_EXPIRED"):
            _build(registry, trust=_trust(na=1_000), now_us=2_000)

    def test_wrong_role_refused(self, registry):
        with pytest.raises(bindings.BindingBundleUnauthenticated, match="MISSING_ROLE"):
            _build(registry, trust=_trust(role="EVIDENCE_PRODUCER"))

    def test_valid_signature_over_other_bytes_refused(self, registry):
        # A real signature bound to a DIFFERENT bundle root (wrong authority digest) must not
        # verify against the recomputed root: the crypto pass returns BAD_SIGNATURE.
        good = _sign_over(registry, **{**BUNDLE_KW, "authority_digest": "f" * 64})
        with pytest.raises(bindings.BindingBundleUnauthenticated, match="BAD_SIGNATURE"):
            _build(registry, signatures=[good])  # BUNDLE_KW.authority_digest = "a"*64 != signed


# -- BIND-05: capability forgery ------------------------------------------------------------------

class TestCapabilityForgery:
    def test_direct_construction_refused(self, registry):
        with pytest.raises(bindings.CapabilityForgeryError):
            bindings.ResolvedParameterBundle(object(), bundle_id="x")

    def test_raw_dict_refused_at_production_path(self):
        with pytest.raises(bindings.CapabilityForgeryError):
            transition.require_bundle({"declared_value": 1}, "p")

    def test_subclass_refused_at_production_path(self, registry):
        cap = _build(registry)

        class Widened(bindings.ResolvedParameterBundle):
            pass

        # An exact-type gate rejects even a subclass instance built via the private token.
        forged = Widened(
            bindings._CONSTRUCTION_TOKEN, **{
                "bundle_id": cap._bundle_id, "bundle_version": cap._bundle_version,
                "bundle_root_digest": cap._bundle_root_digest,
                "trust_registry_digest": cap._trust_registry_digest,
                "authority_digest": cap._authority_digest, "engine": cap._engine,
                "plane": cap._plane, "environment": cap._environment, "scope": cap._scope,
                "signer_key_ids": cap._signer_key_ids,
                "verification_reason": cap._verification_reason,
                "row_count": cap._row_count, "status_counts": cap._status_counts,
                "by_param": cap._by_param, "by_slot": cap._by_slot,
                "formula_rows": cap._formula_rows})
        with pytest.raises(bindings.CapabilityForgeryError):
            transition.require_bundle(forged, "p")

    def test_capability_is_immutable(self, registry):
        cap = _build(registry)
        with pytest.raises(bindings.CapabilityForgeryError):
            cap._engine = "LIVE"
        with pytest.raises(bindings.CapabilityForgeryError):
            del cap._engine

    def test_narrow_cannot_widen(self, registry):
        cap = _build(registry)
        with pytest.raises(bindings.CapabilityForgeryError, match="cannot widen"):
            cap.narrow({"NO_SUCH_PARAMETER"})

    def test_narrow_yields_strict_subset(self, registry):
        cap = _build(registry)
        keep = {registry.active_rows()[0]["parameter_id"]}
        narrowed = cap.narrow(keep)
        assert type(narrowed) is bindings.ResolvedParameterBundle
        got = {narrowed.resolve(s)["parameter_id"] for s in
               (r["semantic_slot"] for r in registry.active_rows()
                if r["parameter_id"] in keep)}
        assert got == keep


# -- BIND-05: consumption faces -------------------------------------------------------------------

class TestConsumptionThroughCapability:
    def test_require_bundle_resolves_active_parameter(self, registry):
        cap = _build(registry)
        active = registry.active_rows()[0]
        assert transition.require_bundle(cap, active["parameter_id"]) == active["declared_value"]

    def test_require_bundle_unknown_parameter_fails_closed(self, registry):
        cap = _build(registry)
        with pytest.raises(bindings.BindingUnknownError):
            transition.require_bundle(cap, "NO_SUCH_PARAMETER")

    def test_for_formula_incomplete_set_absent(self, registry):
        cap = _build(registry)
        # F08 has only blocked rows in the real registry — never exposed as a complete set.
        with pytest.raises(bindings.BindingUnknownError):
            cap.for_formula("F08")


# -- BIND-04 / BIND-06: inventory hardening (loader-level) -----------------------------------------

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
