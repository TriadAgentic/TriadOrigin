"""R-F19 ``opportunity_cluster.v2`` battery — insertion-invariant clustering + revision law.

Every spec test-vector row T1-T11 exists here, plus the ORDERING-LAW permutation-invariance
property test (the defect trap), the TTL/COMPACTION mechanism, the CLUSTER_MAX_MEMBERS
REFUSED_CAPACITY + PROPOSED_MUST_RATIFY refusal, the §1.2 wire-width boundaries, the C.3
typed-boundary adversarial drills, and the restart/prefix parity law.

Capabilities are minted through the REAL sealed-bundle v2 acceptance path
(:func:`triad_origin.transition.require_bundle`) with a fixture Ed25519 keypair — the
``tests/contracts/test_sealed_bundle_v2.py`` / ``test_break_v2.py`` pattern. The real registry's
F19 row (FPB-0036) is BLOCKED (unmigrated), so the fixture bundle carries F19 rows edited ACTIVE —
and one test proves the UNEDITED registry refuses to mint any F19 capability at all (the honest
dark posture).
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import itertools
import json
import pathlib
import random
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import bindings, exact, transition  # noqa: E402
from triad_origin.canonical import canonical_json, sha256_hex  # noqa: E402
from triad_origin.structures import clustering_v2, common  # noqa: E402
from triad_origin.structures.clustering_v2 import (  # noqa: E402
    CandidateOccurrence,
    ClusterBatch,
    EnvelopeRejected,
    MemberTerminal,
    RefuseConfig,
    Watermark,
    evaluate,
    initial_state,
    resolve_canonical_component_id,
    run_clustering_v2,
)

OWNER_KID = "k-owner-f19"
REPOSITORY = "TriadOrigin"
ENVIRONMENT = "OFF"
VALID_FROM = 1_000_000
VALID_TO = 9_000_000
NOW_US = 2_000_000

WINDOW_MS = "30000"
WINDOW_US = 30_000_000


# --- capability forge (real Ed25519 through the real acceptance path) -----------------------------


class _Forge:
    def __init__(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey, Ed25519PublicKey)

        self._private = Ed25519PrivateKey.generate()
        pub_hex = self._private.public_key().public_bytes_raw().hex()
        self.trust = {OWNER_KID: {
            "key_id": OWNER_KID, "identity": "owner@triad", "role": "AUTHORITY_OWNER",
            "algorithm": "ed25519", "public_key_hex": pub_hex, "revoked": False}}
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
    def _resign_row(row: dict) -> dict:
        unsigned = {k: v for k, v in row.items() if k != "binding_digest"}
        row["binding_digest"] = sha256_hex(canonical_json(unsigned))
        return row

    def _sign(self, unsigned):
        signing = bindings.sealed_bundle_signing_bytes(
            canonical_root_digest=unsigned.canonical_root_digest, scope=unsigned.scope,
            valid_from=unsigned.valid_from, valid_to=unsigned.valid_to)
        return dataclasses.replace(unsigned, signatures=[
            {"key_id": OWNER_KID, "signature_hex": self._private.sign(signing).hex()}])

    def fixture_bundle(self, window_value, max_value):
        """A signed fixture bundle whose two F19 rows are edited ACTIVE (fixture surgery)."""
        rows = [dict(r) for r in self._base_rows]
        for row in rows:
            if row["binding_id"] == "FPB-0036":  # the real F19 PAR-060 row
                row["status"] = "ACTIVE"
                row["parameter_id"] = clustering_v2.PARAM_CLUSTER_WINDOW
                row["declared_value"] = window_value
                row["semantic_slot"] = "FIXTURE:F19.cluster_window"
                self._resign_row(row)
            elif row["binding_id"] == "FPB-0092":  # repurposed as the F19 CLUSTER_MAX row
                row["status"] = "ACTIVE"
                row["formula_id"] = clustering_v2.FORMULA_F19
                row["parameter_id"] = clustering_v2.PARAM_CLUSTER_MAX
                row["parameter_name"] = clustering_v2.PARAM_CLUSTER_MAX
                row["semantic_slot"] = "FIXTURE:F19.cluster_max_members"
                row["declared_value"] = max_value
                self._resign_row(row)
        coverage = dict(self._base_coverage)
        coverage["F19"] = "ACTIVE"
        root = bindings.canonical_rows_digest(rows)
        unsigned = bindings.SealedParameterBundle(
            schema_version=bindings.SEALED_SCHEMA_VERSION,
            scope={"repository": REPOSITORY, "environment": ENVIRONMENT},
            rows=rows,
            canonical_root_digest=root,
            trust_registry_digest=self.trust_digest,
            signer_set=[OWNER_KID],
            signatures=[],
            valid_from=VALID_FROM,
            valid_to=VALID_TO,
            formula_coverage=coverage,
            row_preimage_digests=sorted(sha256_hex(canonical_json(r)) for r in rows),
        )
        return self._sign(unsigned)

    def genuine_bundle(self):
        """The UNEDITED registry, signed — F19 stays BLOCKED (the honest dark posture)."""
        unsigned = bindings.build_sealed_bundle(
            self.registry, repository=REPOSITORY, environment=ENVIRONMENT,
            valid_from=VALID_FROM, valid_to=VALID_TO,
            trust_registry_digest=self.trust_digest, signer_set=[OWNER_KID])
        return self._sign(unsigned)

    def mint(self, window_value=WINDOW_MS, max_value="32", *, include_max=True):
        bundle = self.fixture_bundle(window_value, max_value)
        caps = {clustering_v2.PARAM_CLUSTER_WINDOW: transition.require_bundle(
            bundle, clustering_v2.PARAM_CLUSTER_WINDOW, formula_id="F19", ctx=self.ctx)}
        if include_max:
            caps[clustering_v2.PARAM_CLUSTER_MAX] = transition.require_bundle(
                bundle, clustering_v2.PARAM_CLUSTER_MAX, formula_id="F19", ctx=self.ctx)
        return caps

    def mint_f00(self):
        return transition.require_bundle(
            self.genuine_bundle(), "PAR-001", formula_id="F00", ctx=self.ctx)


@pytest.fixture(scope="module")
def forge():
    bindings._reset_trust_registry_pin_for_tests()
    bindings._reset_acceptance_memo_for_tests()
    forge = _Forge()
    bindings.pin_trust_registry_digest(forge.trust_digest)
    yield forge
    bindings._reset_trust_registry_pin_for_tests()
    bindings._reset_acceptance_memo_for_tests()


@pytest.fixture(scope="module")
def caps(forge):
    return forge.mint(WINDOW_MS, "32")


@pytest.fixture(scope="module")
def caps_max2(forge):
    return forge.mint(WINDOW_MS, "2")


@pytest.fixture(scope="module")
def caps_no_max(forge):
    return forge.mint(WINDOW_MS, "32", include_max=False)


@pytest.fixture(scope="module")
def caps_max_unratified(forge):
    return forge.mint(WINDOW_MS, common.NOT_RATIFIED)


# --- envelope helpers ------------------------------------------------------------------------


def occ(candidate_id, *, instrument="BTCUSDT", side=common.LONG, ssid="", srid="",
        zone_low=0, zone_high=0, avail=0, version=1, capsule="cap-1", digest="digest-1",
        eid=None):
    return CandidateOccurrence(
        candidate_id=candidate_id, instrument=instrument, side=side,
        source_structure_id=ssid, source_reaction_id=srid,
        entry_zone_low_ticks=zone_low, entry_zone_high_ticks=zone_high,
        availability_us=avail, occurrence_version=version, capsule_id=capsule,
        capsule_params_digest=digest,
        source_event_id=eid or f"occ:{candidate_id}:{version}")


def batch(*candidates, eid="b1"):
    return ClusterBatch(candidates=tuple(candidates), source_event_id=eid)


def run(caps_map, inputs, initial=None):
    return run_clustering_v2(caps_map, inputs, initial=initial)


def kinds(events, kind):
    return [e for e in events if e.get("event_kind") == kind]


def event_kinds(events):
    return [e.get("event_kind") for e in events]


def reason_codes(events):
    return [e.get("reason_code") for e in events]


def live_components(state):
    return {cid: c for cid, c in state["components"].items() if not c["expired"]}


# =================================================================================================
# The C.3 boundary — typed rejections BEFORE any state transition
# =================================================================================================


class TestBoundary:
    def test_hand_built_dict_int_str_in_place_of_a_capability_are_rejected(self, caps):
        state = initial_state()
        snapshot = copy.deepcopy(state)
        for forged in ({"value": WINDOW_MS}, 5, WINDOW_MS):
            with pytest.raises(bindings.CapabilityForgeryError):
                evaluate({clustering_v2.PARAM_CLUSTER_WINDOW: forged}, batch(occ("A")), state)
        assert state == snapshot  # rejected BEFORE any state transition

    def test_hand_built_dict_env_is_rejected_before_any_transition(self, caps):
        state = initial_state()
        snapshot = copy.deepcopy(state)
        with pytest.raises(EnvelopeRejected):
            evaluate(caps, {"kind": "CANDIDATE_OCCURRENCE", "payload": {}}, state)
        with pytest.raises(EnvelopeRejected):
            evaluate(caps, 1001, state)
        assert state == snapshot

    def test_subclassed_envelope_and_capability_are_rejected_exact_type_law(self, caps):
        class WidenedBatch(ClusterBatch):
            pass

        with pytest.raises(EnvelopeRejected):
            evaluate(caps, WidenedBatch(candidates=(occ("A"),), source_event_id="b"),
                     initial_state())

        class WidenedCap(bindings.VerifiedCapability):
            pass

        real = caps[clustering_v2.PARAM_CLUSTER_WINDOW]
        forged = WidenedCap(
            parameter_id=real.parameter_id, formula_id=real.formula_id, value=real.value,
            source_bundle_digest=real.source_bundle_digest,
            signed_root_digest=real.signed_root_digest, repository=real.repository,
            environment=real.environment, valid_from=real.valid_from, valid_to=real.valid_to,
            signer_key_ids=real.signer_key_ids, _row_canonical=b"{}")
        with pytest.raises(bindings.CapabilityForgeryError):
            evaluate({clustering_v2.PARAM_CLUSTER_WINDOW: forged}, batch(occ("A")), initial_state())

    def test_batch_wrapping_a_raw_dict_candidate_is_rejected(self, caps):
        duck = ClusterBatch(candidates=({"candidate_id": "A"},), source_event_id="b")
        with pytest.raises(EnvelopeRejected):
            evaluate(caps, duck, initial_state())

    def test_wrong_formula_capability_is_refused(self, forge, caps):
        f00 = forge.mint_f00()
        assert f00.formula_id == "F00"
        with pytest.raises(bindings.CapabilityForgeryError):
            evaluate({clustering_v2.PARAM_CLUSTER_WINDOW: f00}, batch(occ("A")), initial_state())

    def test_capability_under_the_wrong_key_is_refused(self, caps):
        max_cap = caps[clustering_v2.PARAM_CLUSTER_MAX]
        with pytest.raises(bindings.CapabilityForgeryError):
            evaluate({clustering_v2.PARAM_CLUSTER_WINDOW: max_cap}, batch(occ("A")),
                     initial_state())

    def test_missing_required_window_capability_fails_closed(self, caps):
        with pytest.raises(transition.MissingParameterError):
            evaluate({}, batch(occ("A")), initial_state())

    def test_unknown_capability_key_is_refused(self, caps):
        widened = dict(caps)
        widened["PAR-999"] = caps[clustering_v2.PARAM_CLUSTER_WINDOW]
        with pytest.raises(RefuseConfig):
            evaluate(widened, batch(occ("A")), initial_state())

    def test_state_must_be_the_exact_v2_state_object(self, caps):
        with pytest.raises(EnvelopeRejected):
            evaluate(caps, batch(occ("A")), 42)
        with pytest.raises(EnvelopeRejected):
            evaluate(caps, batch(occ("A")), {"candidates": {}})
        with pytest.raises(EnvelopeRejected):
            # a v1-shaped state object never blends into v2
            evaluate(caps, batch(occ("A")),
                     {"candidates": {}, "clusters": {}, "cluster_aliases": {}})

    def test_within_batch_duplicate_candidate_id_is_refused(self, caps):
        with pytest.raises(common.StructureLawError):
            evaluate(caps, batch(occ("A"), occ("A", zone_low=5, zone_high=6)), initial_state())

    def test_real_registry_refuses_to_mint_any_f19_capability(self, forge):
        # The honest dark posture: F19's registry row (FPB-0036) is BLOCKED (unmigrated), so the
        # production mint path cannot produce an F19 capability at all.
        with pytest.raises(bindings.BlockedBindingIncomplete) as excinfo:
            transition.require_bundle(
                forge.genuine_bundle(), clustering_v2.PARAM_CLUSTER_WINDOW,
                formula_id="F19", ctx=forge.ctx)
        assert excinfo.value.formula_id == "F19"


# =================================================================================================
# Spec vectors T1-T11
# =================================================================================================


class TestSpecVectors:
    def _two_component_set(self):
        # component 1 (root A): A~B via zone touch @10; B~C via source RY.
        # component 2 (root D): D~E via zone touch @1010; E~F via source RZ.
        return [
            occ("A", zone_low=0, zone_high=10, avail=0),
            occ("B", zone_low=10, zone_high=20, avail=100, srid="RY"),
            occ("C", zone_low=500, zone_high=600, avail=200, srid="RY"),
            occ("D", zone_low=1000, zone_high=1010, avail=0),
            occ("E", zone_low=1010, zone_high=1020, avail=50, srid="RZ"),
            occ("F", zone_low=1500, zone_high=1600, avail=60, srid="RZ"),
        ]

    def test_t1_insertion_invariance_all_permutations_identical(self, caps):
        candidates = self._two_component_set()
        baseline = None
        for perm in itertools.permutations(candidates):
            result = run(caps, [batch(*perm)])
            fingerprint = (
                canonical_json(result.final_state),
                tuple(canonical_json(e) for e in result.events))
            if baseline is None:
                baseline = fingerprint
            assert fingerprint == baseline  # arrival order can never influence any output
        # And the components/roots/aliases are the expected two.
        state = run(caps, [batch(*candidates)]).final_state
        comps = live_components(state)
        assert len(comps) == 2
        roots = sorted(c["root_candidate_id"] for c in comps.values())
        assert roots == ["A", "D"]
        members = sorted([c["member_candidate_ids"] for c in comps.values()])
        assert members == [["A", "B", "C"], ["D", "E", "F"]]
        assert state["aliases"] == {}

    def test_t2_transitive_join_one_component_root_is_min(self, caps):
        a = occ("A", zone_low=0, zone_high=10, avail=0)
        b = occ("B", zone_low=10, zone_high=20, avail=0, srid="RY")
        c = occ("C", zone_low=500, zone_high=600, avail=0, srid="RY")  # joins via B
        result = run(caps, [batch(a, b, c)])
        assert event_kinds(result.events) == [
            clustering_v2.CLUSTER_FORMED, clustering_v2.CLUSTER_JOINED,
            clustering_v2.CLUSTER_JOINED]
        (comp,) = live_components(result.final_state).values()
        assert comp["root_candidate_id"] == "A"
        assert comp["member_candidate_ids"] == ["A", "B", "C"]

    def test_t3_zones_touch_at_one_tick_cluster_inclusive(self, caps):
        a = occ("A", zone_low=0, zone_high=100, avail=0)
        b = occ("B", zone_low=100, zone_high=200, avail=0)  # touch at exactly one tick
        result = run(caps, [batch(a, b)])
        assert event_kinds(result.events) == [
            clustering_v2.CLUSTER_FORMED, clustering_v2.CLUSTER_JOINED]
        assert len(live_components(result.final_state)) == 1

    def test_t4_availability_delta_exactly_window_clusters_plus_one_does_not(self, caps):
        a = occ("A", zone_low=0, zone_high=100, avail=0)
        b_at = occ("B", zone_low=100, zone_high=200, avail=WINDOW_US)       # exactly window
        b_past = occ("B", zone_low=100, zone_high=200, avail=WINDOW_US + 1)  # one past
        at = run(caps, [batch(a, b_at)])
        assert event_kinds(at.events) == [
            clustering_v2.CLUSTER_FORMED, clustering_v2.CLUSTER_JOINED]
        past = run(caps, [batch(a, b_past)])
        assert event_kinds(past.events) == [
            clustering_v2.CLUSTER_FORMED, clustering_v2.CLUSTER_FORMED]
        assert len(live_components(past.final_state)) == 2

    def test_t5_bridging_late_member_merges_two_components(self, caps):
        a = occ("A", zone_low=0, zone_high=10, avail=0)
        d = occ("D", zone_low=100, zone_high=110, avail=0)
        head = run(caps, [batch(a, eid="b1"), batch(d, eid="b2")])
        assert len(live_components(head.final_state)) == 2
        x = occ("X", zone_low=5, zone_high=105, avail=0)  # bridges A and D
        result = run(caps, [batch(x, eid="b3")], initial=head.final_state)
        (merged,) = kinds(result.events, clustering_v2.CLUSTER_MERGED)
        winner = merged["component_id"]
        assert merged["root_candidate_id"] == "A"  # earliest by (availability, candidate_id)
        comps = live_components(result.final_state)
        assert len(comps) == 1  # MERGE, not freeze-and-alias — one live component
        assert comps[winner]["member_candidate_ids"] == ["A", "D", "X"]
        (loser_id,) = merged["aliased_component_ids"]
        assert result.final_state["aliases"] == {loser_id: winner}
        assert resolve_canonical_component_id(result.final_state, loser_id) == winner

    def test_t5b_merge_tie_breaks_by_availability_then_candidate_id(self, caps):
        # D's root availability is EARLIER than A's; availability wins over the id sort.
        a = occ("A", zone_low=0, zone_high=10, avail=1000)
        d = occ("D", zone_low=100, zone_high=110, avail=0)
        x = occ("X", zone_low=5, zone_high=105, avail=0)
        result = run(caps, [batch(a, eid="b1"), batch(d, eid="b2"), batch(x, eid="b3")])
        (merged,) = kinds(result.events, clustering_v2.CLUSTER_MERGED)
        assert merged["root_candidate_id"] == "D"
        # And an equal-availability tie breaks by candidate_id ascending.
        a2 = occ("A", zone_low=0, zone_high=10, avail=500)
        d2 = occ("D", zone_low=100, zone_high=110, avail=500)
        x2 = occ("X", zone_low=5, zone_high=105, avail=500)
        tie = run(caps, [batch(a2, eid="c1"), batch(d2, eid="c2"), batch(x2, eid="c3")])
        (tie_merged,) = kinds(tie.events, clustering_v2.CLUSTER_MERGED)
        assert tie_merged["root_candidate_id"] == "A"

    def test_t6_revision_breaks_overlap_member_retired_component_survives(self, caps):
        a = occ("A", zone_low=0, zone_high=10, avail=0)
        b = occ("B", zone_low=10, zone_high=20, avail=0)  # touches A @10 -> one component
        head = run(caps, [batch(a, b)])
        (comp,) = live_components(head.final_state).values()
        assert comp["member_candidate_ids"] == ["A", "B"]
        # revise B so it no longer overlaps A and shares no source.
        b_rev = occ("B", zone_low=900, zone_high=910, avail=0, version=2)
        result = run(caps, [batch(b_rev, eid="rev")], initial=head.final_state)
        (revision,) = kinds(result.events, clustering_v2.CLUSTER_REVISION)
        assert revision["outcome"] == clustering_v2.REVISION_OUTCOME_RETIRED
        assert revision["cluster_defining_change"] is True
        (retired,) = kinds(result.events, clustering_v2.MEMBER_RETIRED)
        assert retired["candidate_id"] == "B"
        assert retired["component_survives"] is True
        assert retired["remaining_member_count"] == 1
        comps = live_components(result.final_state)
        # A's component survives with just A; B re-forms its own prospective component.
        by_root = {c["root_candidate_id"]: c["member_candidate_ids"] for c in comps.values()}
        assert by_root["A"] == ["A"]
        assert by_root["B"] == ["B"]

    def test_t7_retired_member_reclusters_prospectively_only(self, caps):
        a = occ("A", zone_low=0, zone_high=10, avail=0)
        b = occ("B", zone_low=10, zone_high=20, avail=0)     # in A's component
        c = occ("C", zone_low=900, zone_high=910, avail=0)   # separate component
        head = run(caps, [batch(a, b, c)])
        assert len(live_components(head.final_state)) == 2
        # revise B so it leaves A and now overlaps C -> retires from A, re-clusters into C.
        b_rev = occ("B", zone_low=905, zone_high=915, avail=0, version=2)
        result = run(caps, [batch(b_rev, eid="rev")], initial=head.final_state)
        assert kinds(result.events, clustering_v2.MEMBER_RETIRED)
        (joined,) = kinds(result.events, clustering_v2.CLUSTER_JOINED)
        assert joined["candidate_id"] == "B"
        comps = live_components(result.final_state)
        by_root = {c["root_candidate_id"]: c["member_candidate_ids"] for c in comps.values()}
        assert by_root["A"] == ["A"]
        assert by_root["C"] == ["B", "C"]  # B re-clustered prospectively into C's component

    def test_t8_member_count_at_bound_is_refused_capacity(self, caps_max2):
        a = occ("A", zone_low=0, zone_high=10, avail=0)
        b = occ("B", zone_low=10, zone_high=20, avail=0)     # component now at max (2)
        c = occ("C", zone_low=15, zone_high=25, avail=0)     # would be the 3rd
        result = run(caps_max2, [batch(a, b, c)])
        (refused,) = kinds(result.events, clustering_v2.REFUSED_CAPACITY)
        assert refused["candidate_id"] == "C"
        assert refused["resulting_member_count"] == 3
        assert refused["cluster_max_members"] == 2
        assert "C" not in result.final_state["candidates"]  # never admitted, never evicted
        (comp,) = live_components(result.final_state).values()
        assert comp["member_candidate_ids"] == ["A", "B"]

    def test_t8b_merge_over_the_bound_is_refused_capacity(self, caps_max2):
        a = occ("A", zone_low=0, zone_high=10, avail=0)
        d = occ("D", zone_low=100, zone_high=110, avail=0)
        head = run(caps_max2, [batch(a, eid="b1"), batch(d, eid="b2")])
        x = occ("X", zone_low=5, zone_high=105, avail=0)  # would merge -> union 3 > 2
        result = run(caps_max2, [batch(x, eid="b3")], initial=head.final_state)
        (refused,) = kinds(result.events, clustering_v2.REFUSED_CAPACITY)
        assert refused["resulting_member_count"] == 3
        assert kinds(result.events, clustering_v2.CLUSTER_MERGED) == []
        assert len(live_components(result.final_state)) == 2  # unchanged

    def test_t9_long_and_short_never_cluster(self, caps):
        a = occ("A", side=common.LONG, zone_low=0, zone_high=100, avail=0, ssid="SX")
        b = occ("B", side=common.SHORT, zone_low=0, zone_high=100, avail=0, ssid="SX")
        result = run(caps, [batch(a, b)])
        assert event_kinds(result.events) == [
            clustering_v2.CLUSTER_FORMED, clustering_v2.CLUSTER_FORMED]
        assert len(live_components(result.final_state)) == 2

    def test_t10_restart_parity_mid_stream(self, caps):
        inputs = _composite_tape()
        full = run(caps, inputs)
        for cut in range(1, len(inputs)):
            head = run(caps, inputs[:cut])
            tail = run(caps, inputs[cut:], initial=head.final_state)
            assert list(head.events) + list(tail.events) == list(full.events)
            assert tail.final_state == full.final_state

    def test_t11_duplicate_candidate_id_is_idempotent(self, caps):
        a = occ("A", zone_low=0, zone_high=10, avail=0, eid="e1")
        a_again = occ("A", zone_low=0, zone_high=10, avail=0, eid="e2")  # identical payload
        first = run(caps, [batch(a)])
        result = run(caps, [batch(a, eid="b1"), batch(a_again, eid="b2")])
        assert result.final_state == first.final_state
        assert event_kinds(result.events) == [clustering_v2.CLUSTER_FORMED]


def _composite_tape():
    a = occ("A", zone_low=0, zone_high=10, avail=0)
    b = occ("B", zone_low=10, zone_high=20, avail=100)          # joins A
    d = occ("D", zone_low=1000, zone_high=1010, avail=0)        # separate
    x = occ("X", zone_low=5, zone_high=1005, avail=0)           # bridges A/B and D -> merge
    b_rev = occ("B", zone_low=10, zone_high=20, avail=50, version=2)  # non-defining? avail change
    return [
        batch(a, eid="b1"),
        batch(b, eid="b2"),
        batch(d, eid="b3"),
        batch(x, eid="b4"),
        MemberTerminal(candidate_id="A", terminal_time_us=200, source_event_id="t1"),
        batch(b_rev, eid="b5"),
        Watermark(watermark_us=10_000, source_event_id="w1"),
    ]


# =================================================================================================
# The ORDERING LAW — permutation-invariance property test (the defect trap / ACCEPTANCE)
# =================================================================================================


class TestOrderingLaw:
    def test_random_candidate_sets_are_byte_identical_across_shuffles(self, caps):
        rng = random.Random(20260812)
        for _trial in range(300):
            n = rng.randint(2, 7)
            candidates = []
            for i in range(n):
                base = rng.randint(0, 3) * 1000
                low = base + rng.randint(0, 30)
                candidates.append(occ(
                    f"C{i}",
                    zone_low=low, zone_high=low + rng.randint(0, 40),
                    avail=rng.randint(0, WINDOW_US + 5_000_000),
                    ssid=rng.choice(["", "", "SX", "SY"]),
                    srid=rng.choice(["", "", "RY", "RZ"])))
            reference = None
            for _shuffle in range(6):
                shuffled = list(candidates)
                rng.shuffle(shuffled)
                result = run(caps, [batch(*shuffled)])
                fingerprint = (
                    canonical_json(result.final_state),
                    tuple(canonical_json(e) for e in result.events))
                if reference is None:
                    reference = fingerprint
                assert fingerprint == reference


# =================================================================================================
# Revision law — held / non-defining / content-mismatch / singleton / instrument-side / root
# =================================================================================================


class TestRevisionLaw:
    def test_defining_revision_that_still_overlaps_a_peer_holds(self, caps):
        a = occ("A", zone_low=0, zone_high=100, avail=0)
        b = occ("B", zone_low=50, zone_high=150, avail=0)  # overlaps A
        head = run(caps, [batch(a, b)])
        (comp,) = live_components(head.final_state).values()
        # revise B's zone but keep it overlapping A -> defining change, but edges hold.
        b_rev = occ("B", zone_low=40, zone_high=90, avail=0, version=2)
        result = run(caps, [batch(b_rev, eid="rev")], initial=head.final_state)
        (revision,) = kinds(result.events, clustering_v2.CLUSTER_REVISION)
        assert revision["cluster_defining_change"] is True
        assert revision["outcome"] == clustering_v2.REVISION_OUTCOME_HELD
        assert kinds(result.events, clustering_v2.MEMBER_RETIRED) == []
        (comp2,) = live_components(result.final_state).values()
        assert comp2["member_candidate_ids"] == ["A", "B"]
        assert result.final_state["candidates"]["B"]["entry_zone_low_ticks"] == 40

    def test_non_defining_revision_records_and_holds(self, caps):
        a = occ("A", zone_low=0, zone_high=10, avail=0, capsule="cap-1", version=1)
        head = run(caps, [batch(a)])
        a_rev = occ("A", zone_low=0, zone_high=10, avail=0, capsule="cap-2", version=2)
        result = run(caps, [batch(a_rev, eid="rev")], initial=head.final_state)
        (revision,) = kinds(result.events, clustering_v2.CLUSTER_REVISION)
        assert revision["cluster_defining_change"] is False
        assert revision["outcome"] == clustering_v2.REVISION_OUTCOME_HELD
        assert result.final_state["candidates"]["A"]["capsule_id"] == "cap-2"

    def test_singleton_defining_revision_holds_no_edges_to_fail(self, caps):
        a = occ("A", zone_low=0, zone_high=10, avail=0, version=1)
        head = run(caps, [batch(a)])
        a_rev = occ("A", zone_low=900, zone_high=910, avail=777, version=2)  # defining change
        result = run(caps, [batch(a_rev, eid="rev")], initial=head.final_state)
        (revision,) = kinds(result.events, clustering_v2.CLUSTER_REVISION)
        assert revision["outcome"] == clustering_v2.REVISION_OUTCOME_HELD
        assert kinds(result.events, clustering_v2.MEMBER_RETIRED) == []
        (comp,) = live_components(result.final_state).values()
        assert comp["member_candidate_ids"] == ["A"]
        assert result.final_state["candidates"]["A"]["availability_us"] == 777

    def test_same_or_lower_version_content_mismatch_is_refused(self, caps):
        a = occ("A", zone_low=0, zone_high=10, avail=0, version=1, eid="e1")
        conflict = occ("A", zone_low=0, zone_high=10, avail=999, version=1, eid="e2")
        result = run(caps, [batch(a, eid="b1"), batch(conflict, eid="b2")])
        assert clustering_v2.ABSTAIN_CONTENT_MISMATCH in reason_codes(result.events)
        assert result.final_state["candidates"]["A"]["availability_us"] == 0  # left untouched

    def test_revision_may_not_change_instrument_or_side(self, caps):
        a = occ("A", side=common.LONG, zone_low=0, zone_high=10, avail=0, version=1)
        flipped = occ("A", side=common.SHORT, zone_low=0, zone_high=10, avail=0, version=2)
        with pytest.raises(common.StructureLawError, match="may not change instrument or side"):
            run(caps, [batch(a, eid="b1"), batch(flipped, eid="b2")])

    def test_root_revision_that_breaks_every_edge_is_unsupported(self, caps):
        # Chain A-B-C where A (root, min avail) connects ONLY via B; C joins via B (source).
        a = occ("A", zone_low=0, zone_high=10, avail=0)
        b = occ("B", zone_low=10, zone_high=20, avail=100, srid="RY")
        c = occ("C", zone_low=500, zone_high=600, avail=200, srid="RY")  # joins via B, not A
        head = run(caps, [batch(a, b, c)])
        (comp,) = live_components(head.final_state).values()
        assert comp["root_candidate_id"] == "A"
        # revise A so it no longer overlaps B (and no shared source): A is the root, B/C remain.
        a_rev = occ("A", zone_low=5000, zone_high=5010, avail=0, version=2)
        with pytest.raises(common.StructureLawError, match="F19_ROOT_REVISION_UNSUPPORTED"):
            run(caps, [batch(a_rev, eid="rev")], initial=head.final_state)


# =================================================================================================
# CLUSTER_MAX_MEMBERS — PROPOSED_MUST_RATIFY: mechanism wired, refusal stands
# =================================================================================================


class TestClusterMaxRefusal:
    def test_absent_max_capability_is_a_named_abstention_and_safe_hold(self, caps_no_max):
        state = initial_state()
        result = run(caps_no_max, [batch(occ("A"))])
        assert clustering_v2.ABSTAIN_CLUSTER_MAX_NOT_RATIFIED in reason_codes(result.events)
        assert result.final_state == state  # SAFE_HOLD: zero state mutation

    def test_not_ratified_sentinel_max_is_the_same_refusal(self, caps_max_unratified):
        result = run(caps_max_unratified, [batch(occ("A"), occ("B", zone_low=5, zone_high=6))])
        assert clustering_v2.ABSTAIN_CLUSTER_MAX_NOT_RATIFIED in reason_codes(result.events)
        assert result.final_state["candidates"] == {}

    def test_terminal_and_watermark_channels_stay_live_under_the_refusal(self, caps, caps_no_max):
        # Build a component with the ratified caps, then drive terminal/watermark under the refusal.
        head = run(caps, [batch(occ("A", avail=0))])
        terminal = run(caps_no_max, [
            MemberTerminal(candidate_id="A", terminal_time_us=1, source_event_id="t")],
            initial=head.final_state)
        assert kinds(terminal.events, clustering_v2.MEMBER_TERMINAL)
        assert terminal.final_state["candidates"]["A"]["terminal"] is True

    def test_malformed_max_values_are_refuse_config(self, forge):
        for bad in ("0", "-5", "garbage"):
            caps_bad = forge.mint(WINDOW_MS, bad)
            with pytest.raises(RefuseConfig):
                evaluate(caps_bad, batch(occ("A")), initial_state())

    def test_proposed_max_value_is_never_hardcoded_as_active(self):
        # §0 rule 1: the proposed CLUSTER_MAX_MEMBERS value (32) is never an executable constant.
        source = pathlib.Path(clustering_v2.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, int) \
                    and not isinstance(node.value, bool):
                assert node.value != 32, "the proposed CLUSTER_MAX_MEMBERS value is hardcoded"


# =================================================================================================
# TTL / COMPACTION — Watermark + MemberTerminal
# =================================================================================================


class TestTtlCompaction:
    def _terminal_component(self, caps):
        # A singleton component whose only member is terminal at availability 0.
        head = run(caps, [batch(occ("A", avail=0))])
        head = run(caps, [
            MemberTerminal(candidate_id="A", terminal_time_us=1, source_event_id="t")],
            initial=head.final_state)
        return head.final_state

    def test_component_expires_only_strictly_past_the_window(self, caps):
        state = self._terminal_component(caps)
        # exactly +window: NOT expired (a candidate at +window could still cluster).
        at = run(caps, [Watermark(watermark_us=WINDOW_US, source_event_id="w")], initial=state)
        assert kinds(at.events, clustering_v2.CLUSTER_EXPIRED) == []
        assert len(live_components(at.final_state)) == 1
        # +window+1: EXPIRED + compacted out of the clustering scan.
        past = run(caps, [Watermark(watermark_us=WINDOW_US + 1, source_event_id="w")],
                   initial=state)
        (expired,) = kinds(past.events, clustering_v2.CLUSTER_EXPIRED)
        assert expired["member_count"] == 1
        assert len(live_components(past.final_state)) == 0

    def test_component_with_a_non_terminal_member_never_expires(self, caps):
        head = run(caps, [batch(occ("A", zone_low=0, zone_high=10, avail=0),
                                occ("B", zone_low=5, zone_high=15, avail=0))])
        head = run(caps, [
            MemberTerminal(candidate_id="A", terminal_time_us=1, source_event_id="t")],
            initial=head.final_state)  # only A terminal, B still live
        result = run(caps, [Watermark(watermark_us=10 ** 12, source_event_id="w")],
                     initial=head.final_state)
        assert kinds(result.events, clustering_v2.CLUSTER_EXPIRED) == []

    def test_expired_component_members_no_longer_cluster(self, caps):
        state = self._terminal_component(caps)
        state = run(caps, [Watermark(watermark_us=WINDOW_US + 1, source_event_id="w")],
                    initial=state).final_state
        # A new candidate that WOULD have overlapped A must not join the expired component.
        result = run(caps, [batch(occ("Z", avail=0))], initial=state)
        assert event_kinds(result.events) == [clustering_v2.CLUSTER_FORMED]
        assert len(live_components(result.final_state)) == 1

    def test_watermark_regression_is_refused(self, caps):
        head = run(caps, [Watermark(watermark_us=100, source_event_id="w1")])
        with pytest.raises(common.StructureLawError, match="watermark regression"):
            run(caps, [Watermark(watermark_us=99, source_event_id="w2")],
                initial=head.final_state)

    def test_terminal_for_unknown_candidate_is_refused(self, caps):
        with pytest.raises(common.StructureLawError, match="unknown candidate"):
            run(caps, [MemberTerminal(candidate_id="ghost", terminal_time_us=1,
                                      source_event_id="t")])

    def test_terminal_is_idempotent(self, caps):
        head = run(caps, [batch(occ("A"))])
        once = run(caps, [MemberTerminal(candidate_id="A", terminal_time_us=1,
                                         source_event_id="t1")], initial=head.final_state)
        twice = run(caps, [MemberTerminal(candidate_id="A", terminal_time_us=1,
                                          source_event_id="t2")], initial=once.final_state)
        assert twice.events == ()
        assert twice.final_state == once.final_state


# =================================================================================================
# §1.2 wire width — int64 boundaries (2^63 - 1 passes; one beyond quarantines)
# =================================================================================================


class TestWireWidth:
    def test_availability_int64_edges(self, caps):
        top = 2 ** 63 - 1
        ok = run(caps, [batch(occ("A", avail=top))])
        assert ok.final_state["candidates"]["A"]["availability_us"] == top
        with pytest.raises(exact.QuarantineOverflow) as excinfo:
            evaluate(caps, batch(occ("A", avail=2 ** 63)), initial_state())
        assert excinfo.value.formula_id == "F19"
        assert excinfo.value.field == "availability_us"

    def test_zone_tick_int64_edges(self, caps):
        with pytest.raises(exact.QuarantineOverflow):
            evaluate(caps, batch(occ("A", zone_low=-(2 ** 63) - 1, zone_high=0)), initial_state())
        with pytest.raises(exact.QuarantineOverflow):
            evaluate(caps, batch(occ("A", zone_low=0, zone_high=2 ** 63)), initial_state())

    def test_watermark_int64_edge(self, caps):
        with pytest.raises(exact.QuarantineOverflow):
            evaluate(caps, Watermark(watermark_us=2 ** 63, source_event_id="w"), initial_state())


# =================================================================================================
# Determinism: restart/prefix parity, driver-style dedup
# =================================================================================================


class TestDeterminism:
    def test_evaluate_never_mutates_the_callers_state(self, caps):
        state = run(caps, [batch(occ("A"))]).final_state
        snapshot = copy.deepcopy(state)
        evaluate(caps, batch(occ("B", zone_low=100, zone_high=110, avail=0)), state)
        assert state == snapshot

    def test_exact_duplicate_envelope_is_deduped_by_the_fold(self, caps):
        b = batch(occ("A"))
        result = run(caps, [b, b])
        assert result.duplicate_count == 1
        assert event_kinds(result.events) == [clustering_v2.CLUSTER_FORMED]

    def test_deterministic_replay(self, caps):
        inputs = _composite_tape()
        first = run(caps, inputs)
        second = run(caps, inputs)
        assert [canonical_json(e) for e in first.events] == [
            canonical_json(e) for e in second.events]
        assert canonical_json(first.final_state) == canonical_json(second.final_state)


# =================================================================================================
# Source-overlap clustering + alias resolution helpers
# =================================================================================================


class TestSourceOverlapAndAlias:
    def test_source_overlap_alone_clusters_regardless_of_zone_or_availability(self, caps):
        a = occ("A", zone_low=0, zone_high=10, avail=0, ssid="SX")
        b = occ("B", zone_low=9_000, zone_high=9_100, avail=10 ** 12, ssid="SX")
        result = run(caps, [batch(a, b)])
        assert event_kinds(result.events) == [
            clustering_v2.CLUSTER_FORMED, clustering_v2.CLUSTER_JOINED]
        assert len(live_components(result.final_state)) == 1

    def test_a_later_occurrence_resolves_through_a_merge_alias_to_the_winner(self, caps):
        a = occ("A", zone_low=0, zone_high=10, avail=0)
        d = occ("D", zone_low=100, zone_high=110, avail=0)
        x = occ("X", zone_low=5, zone_high=105, avail=0)  # merges A + D
        e = occ("E", zone_low=100, zone_high=110, avail=0)  # overlaps former-D zone
        result = run(caps, [batch(a, eid="b1"), batch(d, eid="b2"),
                            batch(x, eid="b3"), batch(e, eid="b4")])
        (comp,) = live_components(result.final_state).values()
        assert sorted(comp["member_candidate_ids"]) == ["A", "D", "E", "X"]
        assert event_kinds(result.events)[-1] == clustering_v2.CLUSTER_JOINED
