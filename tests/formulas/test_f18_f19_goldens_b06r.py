"""B06R milestone golden home — F19 clustering + the F14→F19 exact-digest adoption + §E.0 F18.

This file is the B06R acceptance profile's REQUIRED ARTIFACT
(``docs/control/closure/closure_semantics.v1.json`` →
``tests/formulas/test_f18_f19_goldens_b06r.py``). It executes, on the repaired surfaces:

* **F19 ``opportunity_cluster.v2`` (GV-016 lineage):** the insertion-invariance / ordering law —
  a two-component candidate set clusters into exactly two components with the
  ``(availability, candidate_id)``-minimum root, and arrival order can never change the output.
* **The F14→F19 exact-digest adoption (spec §R-F14 B06R note):** F14 emits a frozen reaction
  identity now; F19's cluster predicate consumes ``source_reaction_id`` overlap. Two candidates
  that share a ``source_reaction_id`` but whose zones do NOT touch still cluster — proving the
  reaction-id edge (the "adopted there" half) is live.
* **§E.0 F18 (spec §E.0):** F18 candidate-geometry stays a NAMED refusal / abstention posture —
  geometry law stands, R-F19 demands no F18 code change. (Authoritative home:
  ``tests/structures/test_candidate_geometry.py``; the posture is re-asserted here.)

The full F19 battery (T1–T11 + the permutation-invariance property + the revision law) lives in
``tests/structures/test_clustering_v2.py``; this milestone home walks the headline GV-016 + the
cross-formula adoption + the F18 posture.
"""

from __future__ import annotations

import dataclasses
import itertools
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import bindings, transition  # noqa: E402
from triad_origin.canonical import canonical_json, sha256_hex  # noqa: E402
from triad_origin.structures import clustering_v2  # noqa: E402
from triad_origin.structures import common  # noqa: E402
from triad_origin.structures.clustering_v2 import (  # noqa: E402
    CandidateOccurrence,
    ClusterBatch,
    run_clustering_v2,
)

OWNER_KID = "k-owner-b06r-goldens"
REPOSITORY = "TriadOrigin"
ENVIRONMENT = "OFF"
NOW_US = 2_000_000


class _Forge:
    def __init__(self) -> None:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey, Ed25519PublicKey)

        self._private = Ed25519PrivateKey.generate()
        pub_hex = self._private.public_key().public_bytes_raw().hex()
        self.trust = {OWNER_KID: {
            "key_id": OWNER_KID, "identity": "b06r-goldens@triad-origin",
            "role": "AUTHORITY_OWNER", "algorithm": "ed25519",
            "public_key_hex": pub_hex, "revoked": False}}
        self.trust_bytes = json.dumps(self.trust, sort_keys=True).encode("utf-8")
        self.trust_digest = sha256_hex(self.trust_bytes)

        def _verify(public_key_hex: str, message: bytes, signature_hex: str) -> bool:
            try:
                key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
                key.verify(bytes.fromhex(signature_hex), message)
                return True
            except Exception:
                return False

        self.ctx = bindings.VerificationContext(
            trust=self.trust, trust_registry_bytes=self.trust_bytes, now_us=NOW_US,
            process_scope={"repository": REPOSITORY, "environment": ENVIRONMENT},
            verify_fn=_verify)
        self.registry = bindings.load_registry()
        self._base_rows = self.registry.rows()
        self._base_coverage = bindings.derive_formula_coverage(self.registry)

    @staticmethod
    def _resign(row: dict) -> dict:
        unsigned = {k: v for k, v in row.items() if k != "binding_digest"}
        row["binding_digest"] = sha256_hex(canonical_json(unsigned))
        return row

    def _sign(self, unsigned):
        signing = bindings.sealed_bundle_signing_bytes(
            canonical_root_digest=unsigned.canonical_root_digest, scope=unsigned.scope,
            valid_from=unsigned.valid_from, valid_to=unsigned.valid_to)
        return dataclasses.replace(unsigned, signatures=[
            {"key_id": OWNER_KID, "signature_hex": self._private.sign(signing).hex()}])

    def f19_bundle(self, window_value="30000", max_value="32"):
        rows = [dict(r) for r in self._base_rows]
        for row in rows:
            if row["binding_id"] == "FPB-0036":
                row["status"] = "ACTIVE"
                row["parameter_id"] = clustering_v2.PARAM_CLUSTER_WINDOW
                row["declared_value"] = window_value
                row["semantic_slot"] = "B06R:F19.cluster_window"
                self._resign(row)
            elif row["binding_id"] == "FPB-0092":
                row["status"] = "ACTIVE"
                row["formula_id"] = clustering_v2.FORMULA_F19
                row["parameter_id"] = clustering_v2.PARAM_CLUSTER_MAX
                row["parameter_name"] = clustering_v2.PARAM_CLUSTER_MAX
                row["semantic_slot"] = "B06R:F19.cluster_max_members"
                row["declared_value"] = max_value
                self._resign(row)
        coverage = dict(self._base_coverage)
        coverage["F19"] = "ACTIVE"
        root = bindings.canonical_rows_digest(rows)
        unsigned = bindings.SealedParameterBundle(
            schema_version=bindings.SEALED_SCHEMA_VERSION,
            scope={"repository": REPOSITORY, "environment": ENVIRONMENT},
            rows=rows, canonical_root_digest=root, trust_registry_digest=self.trust_digest,
            signer_set=[OWNER_KID], signatures=[], valid_from=1_000_000, valid_to=9_000_000,
            formula_coverage=coverage,
            row_preimage_digests=sorted(sha256_hex(canonical_json(r)) for r in rows))
        return self._sign(unsigned)


@pytest.fixture(scope="module")
def forge():
    bindings._reset_trust_registry_pin_for_tests()
    bindings._reset_acceptance_memo_for_tests()
    f = _Forge()
    bindings.pin_trust_registry_digest(f.trust_digest)
    yield f
    bindings._reset_trust_registry_pin_for_tests()
    bindings._reset_acceptance_memo_for_tests()


@pytest.fixture(scope="module")
def caps(forge):
    b = forge.f19_bundle()
    return {
        clustering_v2.PARAM_CLUSTER_WINDOW: transition.require_bundle(
            b, clustering_v2.PARAM_CLUSTER_WINDOW, formula_id="F19", ctx=forge.ctx),
        clustering_v2.PARAM_CLUSTER_MAX: transition.require_bundle(
            b, clustering_v2.PARAM_CLUSTER_MAX, formula_id="F19", ctx=forge.ctx),
    }


def _occ(cid, *, zone_low, zone_high, avail, srid="", side=common.LONG):
    return CandidateOccurrence(
        candidate_id=cid, instrument="BTCUSDT", side=side,
        source_structure_id="", source_reaction_id=srid,
        entry_zone_low_ticks=zone_low, entry_zone_high_ticks=zone_high,
        availability_us=avail, occurrence_version=1, capsule_id="cap-1",
        capsule_params_digest="digest-1", source_event_id=f"occ:{cid}")


def _batch(*cands):
    return ClusterBatch(candidates=tuple(cands), source_event_id="b1")


def _live_components(state):
    return {cid: c for cid, c in state["components"].items() if not c["expired"]}


class TestF19InsertionInvariance:
    def _two_component_set(self):
        # component 1 (root A): A~B via zone touch; B~C via shared source_reaction_id RY.
        # component 2 (root D): D~E via zone touch; E~F via shared source_reaction_id RZ.
        return [
            _occ("A", zone_low=0, zone_high=10, avail=0),
            _occ("B", zone_low=10, zone_high=20, avail=100, srid="RY"),
            _occ("C", zone_low=500, zone_high=600, avail=200, srid="RY"),
            _occ("D", zone_low=1000, zone_high=1010, avail=0),
            _occ("E", zone_low=1010, zone_high=1020, avail=50, srid="RZ"),
            _occ("F", zone_low=1500, zone_high=1600, avail=60, srid="RZ"),
        ]

    def test_arrival_order_never_changes_the_output(self, caps):
        candidates = self._two_component_set()
        baseline = None
        for perm in itertools.permutations(candidates):
            result = run_clustering_v2(caps, [_batch(*perm)])
            fingerprint = canonical_json(result.final_state)
            if baseline is None:
                baseline = fingerprint
            assert fingerprint == baseline  # ORDERING LAW: order is irrelevant

    def test_exactly_two_components_with_min_availability_roots(self, caps):
        state = run_clustering_v2(caps, [_batch(*self._two_component_set())]).final_state
        comps = _live_components(state)
        assert len(comps) == 2
        roots = sorted(c["root_candidate_id"] for c in comps.values())
        assert roots == ["A", "D"]  # the (availability, id)-minimum member of each component


class TestF14ToF19ExactDigestAdoption:
    def test_shared_source_reaction_id_clusters_even_without_zone_overlap(self, caps):
        # The F14→F19 adoption: F14's reaction identity is the source_reaction_id F19's predicate
        # consumes. Two candidates with DISJOINT zones but the SAME source_reaction_id cluster.
        state = run_clustering_v2(caps, [_batch(
            _occ("P", zone_low=0, zone_high=5, avail=0, srid="RX"),
            _occ("Q", zone_low=9000, zone_high=9005, avail=10, srid="RX"),
        )]).final_state
        comps = _live_components(state)
        assert len(comps) == 1, f"shared source_reaction_id must cluster, got {comps!r}"
        (comp,) = comps.values()
        assert sorted(comp["member_candidate_ids"]) == ["P", "Q"]

    def test_disjoint_zones_and_no_shared_source_do_not_cluster(self, caps):
        # The negative: no zone touch AND no shared source_reaction_id -> two components.
        state = run_clustering_v2(caps, [_batch(
            _occ("P", zone_low=0, zone_high=5, avail=0, srid="RX"),
            _occ("Q", zone_low=9000, zone_high=9005, avail=10, srid="RZ"),
        )]).final_state
        assert len(_live_components(state)) == 2


class TestE0F18RefusalPosture:
    def test_f18_stays_a_named_refusal_when_its_binding_is_unratified(self):
        # §E.0: geometry law stands; F18 abstains rather than improvising. F18 is the legacy
        # raw-params surface (outside this repair set's C.3 scope) — an absent required declared
        # rule is a named refusal, never a guessed geometry (fail-closed).
        from triad_origin.structures import candidate_geometry
        from triad_origin.transition import MissingParameterError
        with pytest.raises((MissingParameterError, common.StructureLawError)):
            candidate_geometry.evaluate_candidate_geometry(
                direction=common.LONG, entry_reference_ticks=100,
                natural_invalidation_source_ticks=90, atr14_ticks=10,
                capsule_semantic_id="dc_swing_bos_first_retest.v1",
                available_targets=[{"target_type": "PROTECTED_SWING", "target_ticks": 120,
                                    "target_knowledge_time_us": 0, "target_root_id": "t"}],
                candidate_knowledge_time_us=0, params={})  # empty params -> fail closed


class TestHonestDark:
    def test_unedited_registry_mints_no_f19_capability(self, forge):
        genuine = forge._sign(bindings.build_sealed_bundle(
            forge.registry, repository=REPOSITORY, environment=ENVIRONMENT,
            valid_from=1_000_000, valid_to=9_000_000,
            trust_registry_digest=forge.trust_digest, signer_set=[OWNER_KID]))
        with pytest.raises(bindings.BlockedBindingIncomplete):
            transition.require_bundle(
                genuine, clustering_v2.PARAM_CLUSTER_WINDOW, formula_id="F19", ctx=forge.ctx)
