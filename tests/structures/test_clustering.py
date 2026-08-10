"""F19 opportunity-clustering battery: GV-016, boundary, mirror, transitive join, redelivery,
cross-cluster alias (earliest root wins), fail-closed, invariance."""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import canonical, transition  # noqa: E402
from triad_origin.structures import common  # noqa: E402
from triad_origin.structures.common import StructureLawError  # noqa: E402
from triad_origin.structures.clustering import (  # noqa: E402
    CANDIDATE_REVISED,
    CLUSTER_ALIASED,
    CLUSTER_FORMED,
    CLUSTER_JOINED,
    F19_CANDIDATE_CONTENT_MISMATCH,
    SEMANTIC_VERSION_F19,
    OpportunityClusterRegistry,
    _cluster_params_digest,
    resolve_canonical_cluster_id,
)

PARAMS = {"cluster_window_ms": 30000}


def occurrence(
    candidate_id, *, instrument="BTCUSDT", side=common.LONG,
    source_structure_id="", source_reaction_id="", zone_low=0, zone_high=0,
    availability_us=0, occurrence_version=1, capsule_id="cap-1",
    capsule_params_digest="digest-1", event_id=None,
):
    return {
        "event_id": event_id or f"occ_{candidate_id}_{occurrence_version}",
        "kind": "CANDIDATE_OCCURRENCE",
        "payload": {
            "candidate_id": candidate_id, "instrument": instrument, "side": side,
            "source_structure_id": source_structure_id, "source_reaction_id": source_reaction_id,
            "entry_zone_low_ticks": zone_low, "entry_zone_high_ticks": zone_high,
            "availability_us": availability_us, "occurrence_version": occurrence_version,
            "capsule_id": capsule_id, "capsule_params_digest": capsule_params_digest,
        },
    }


def run(inputs, initial=None):
    return transition.run(OpportunityClusterRegistry(), inputs, PARAMS, initial=initial)


def event_kinds(result):
    return [event.get("event_kind") for event in result.events]


def reason_codes(result):
    return [event.get("reason_code") for event in result.events]


class TestGv016:
    def test_zones_touch_one_tick_availability_delta_exactly_window_same_cluster(self):
        # window=30000ms=30_000_000us; delta is exactly at the bound -> inclusive, same cluster.
        a = occurrence("A", zone_low=0, zone_high=100, availability_us=0)
        b = occurrence("B", zone_low=100, zone_high=200, availability_us=30_000_000)
        result = run([a, b])
        assert event_kinds(result) == [CLUSTER_FORMED, CLUSTER_JOINED]
        clusters = result.final_state["clusters"]
        assert len(clusters) == 1
        (cluster,) = clusters.values()
        assert cluster["root_candidate_id"] == "A"
        assert cluster["member_candidate_ids"] == ["A", "B"]

    def test_zones_touch_one_tick_availability_delta_one_unit_short_of_window_same_cluster(self):
        # window=30000ms=30_000_000us; delta ONE unit short of the bound (29_999_000us) is strictly
        # inside the inclusive window -> same cluster. Completes the golden_boundary_tests
        # "one-unit-short/over" pair (the equality and one-unit-over vectors are above/below).
        a = occurrence("A", zone_low=0, zone_high=100, availability_us=0)
        b = occurrence("B", zone_low=100, zone_high=200, availability_us=29_999_000)
        result = run([a, b])
        assert event_kinds(result) == [CLUSTER_FORMED, CLUSTER_JOINED]
        assert len(result.final_state["clusters"]) == 1

    def test_boundary_one_ms_past_window_with_no_source_overlap_is_separate(self):
        a = occurrence("A", zone_low=0, zone_high=100, availability_us=0)
        b = occurrence("B", zone_low=100, zone_high=200, availability_us=30_001_000)
        result = run([a, b])
        assert event_kinds(result) == [CLUSTER_FORMED, CLUSTER_FORMED]
        assert len(result.final_state["clusters"]) == 2


class TestClusterIdentityMaterial:
    """F19-1: cluster_id = hash(version, params, instrument, side, root_candidate_id) is composed
    from the F19 formula's OWN identity material -- the RC3 semantic version (``version``) and a
    digest of the effective clustering parameter set (``params``: cluster_window + the frozen
    overlap-predicate/arbitration-rule identities) -- NEVER from the root candidate's capsule
    (``capsule_id`` / ``capsule_params_digest``). Each assertion below fails on the earlier
    capsule-field binding."""

    def test_cluster_id_binds_version_and_params_to_the_formula_not_the_capsule(self):
        a = occurrence(
            "A", instrument="BTCUSDT", side=common.LONG, zone_low=0, zone_high=10,
            availability_us=0, capsule_id="cap-XYZ", capsule_params_digest="digest-XYZ")
        result = run([a])
        (cluster_id,) = result.final_state["clusters"].keys()
        expected = canonical.sha256_hex(canonical.canonical_json({
            "version": SEMANTIC_VERSION_F19,
            "params": _cluster_params_digest(30000),  # PARAMS window, in ms
            "instrument": "BTCUSDT",
            "side": common.LONG,
            "root_candidate_id": "A",
        }))
        assert cluster_id == expected

    def test_cluster_id_is_invariant_to_the_root_candidate_capsule(self):
        # Same root candidate_id/instrument/side/window, DIFFERENT capsule fields -> SAME cluster_id
        # (the capsule is not part of cluster identity). The old binding leaked it and these differed.
        one = run([occurrence("A", capsule_id="cap-1", capsule_params_digest="digest-1")])
        two = run([occurrence("A", capsule_id="cap-2", capsule_params_digest="digest-2")])
        (id_one,) = one.final_state["clusters"].keys()
        (id_two,) = two.final_state["clusters"].keys()
        assert id_one == id_two

    def test_cluster_id_moves_with_a_clustering_parameter_change(self):
        # A PAR-060 (cluster_window) change moves cluster identity -- the identity material's
        # "parameter digest" law. The old binding was window-independent and these matched.
        base = transition.run(
            OpportunityClusterRegistry(), [occurrence("A")], {"cluster_window_ms": 30000})
        widened = transition.run(
            OpportunityClusterRegistry(), [occurrence("A")], {"cluster_window_ms": 40000})
        (id_base,) = base.final_state["clusters"].keys()
        (id_widened,) = widened.final_state["clusters"].keys()
        assert id_base != id_widened


class TestSourceOverlap:
    def test_source_overlap_alone_clusters_regardless_of_zone_or_availability(self):
        a = occurrence("A", zone_low=0, zone_high=10, availability_us=0, source_structure_id="SX")
        b = occurrence(
            "B", zone_low=9_000, zone_high=9_100, availability_us=10**12,
            source_structure_id="SX")
        result = run([a, b])
        assert event_kinds(result) == [CLUSTER_FORMED, CLUSTER_JOINED]
        assert len(result.final_state["clusters"]) == 1


class TestMirrorLaw:
    def test_long_and_short_never_cluster(self):
        # Otherwise identical: same zone, same availability, same source -- only side differs.
        a = occurrence(
            "A", side=common.LONG, zone_low=0, zone_high=100, availability_us=0,
            source_structure_id="SX")
        b = occurrence(
            "B", side=common.SHORT, zone_low=0, zone_high=100, availability_us=0,
            source_structure_id="SX")
        result = run([a, b])
        assert event_kinds(result) == [CLUSTER_FORMED, CLUSTER_FORMED]
        assert len(result.final_state["clusters"]) == 2


class TestTransitiveJoin:
    def test_third_candidate_joins_via_a_non_root_member(self):
        a = occurrence("A", zone_low=0, zone_high=10, availability_us=0)
        b = occurrence(
            "B", zone_low=10, zone_high=20, availability_us=0, source_reaction_id="RY")
        c = occurrence(
            "C", zone_low=500, zone_high=600, availability_us=0, source_reaction_id="RY")
        result = run([a, b, c])
        assert event_kinds(result) == [CLUSTER_FORMED, CLUSTER_JOINED, CLUSTER_JOINED]
        clusters = result.final_state["clusters"]
        assert len(clusters) == 1
        (cluster,) = clusters.values()
        assert cluster["root_candidate_id"] == "A"
        assert cluster["member_candidate_ids"] == ["A", "B", "C"]

    def test_root_never_changes_across_multiple_joins(self):
        a = occurrence("A", zone_low=0, zone_high=10, availability_us=0)
        b = occurrence(
            "B", zone_low=10, zone_high=20, availability_us=0, source_reaction_id="RY")
        c = occurrence(
            "C", zone_low=500, zone_high=600, availability_us=0, source_reaction_id="RY")
        after_a = run([a])
        (root_after_a,) = [c["root_candidate_id"] for c in after_a.final_state["clusters"].values()]
        after_all = run([a, b, c])
        (root_after_all,) = [
            c["root_candidate_id"] for c in after_all.final_state["clusters"].values()]
        assert root_after_a == root_after_all == "A"


class TestCrossClusterAlias:
    """RC3 errata (docs/control/rc3_executable_builder.py formula_errata, "Stable opportunity
    identity"): cross-cluster attachment chooses the earliest root deterministically and records
    the other matched cluster(s) as aliases -- never a merge, never a re-root, never a refusal."""

    def test_bridging_occurrence_joins_earliest_root_and_aliases_the_other(self):
        a = occurrence("A", zone_low=0, zone_high=10, availability_us=0)
        d = occurrence("D", zone_low=100, zone_high=110, availability_us=0)
        x = occurrence("X", zone_low=5, zone_high=105, availability_us=0)
        result = run([a, d, x])

        assert event_kinds(result) == [CLUSTER_FORMED, CLUSTER_FORMED, CLUSTER_ALIASED]
        x_event = result.events[-1]
        assert x_event["root_candidate_id"] == "A"  # earliest by (availability, candidate_id)

        candidates = result.final_state["candidates"]
        clusters = result.final_state["clusters"]
        assert "X" in candidates  # bridging occurrence is admitted, never refused
        winner_cluster_id = candidates["X"]["cluster_id"]
        assert winner_cluster_id == x_event["cluster_id"]
        assert clusters[winner_cluster_id]["member_candidate_ids"] == ["A", "X"]

        # D's own cluster record is FROZEN exactly as it stood -- never re-rooted, never merged.
        d_cluster_id = candidates["D"]["cluster_id"]
        assert d_cluster_id != winner_cluster_id
        assert clusters[d_cluster_id] == {
            "root_candidate_id": "D", "member_candidate_ids": ["D"]}
        assert x_event["aliased_cluster_ids"] == [d_cluster_id]
        assert result.final_state["cluster_aliases"] == {d_cluster_id: winner_cluster_id}
        assert resolve_canonical_cluster_id(result.final_state, d_cluster_id) == winner_cluster_id

    def test_a_later_occurrence_resolves_through_the_alias_transparently(self):
        # E touches ONLY D's (now-aliased) zone; it must land on the WINNER cluster directly, not
        # re-trigger a spurious cross-cluster attachment against an already-unified pair.
        a = occurrence("A", zone_low=0, zone_high=10, availability_us=0)
        d = occurrence("D", zone_low=100, zone_high=110, availability_us=0)
        x = occurrence("X", zone_low=5, zone_high=105, availability_us=0)
        e = occurrence("E", zone_low=100, zone_high=110, availability_us=0)
        result = run([a, d, x, e])

        assert event_kinds(result)[-1] == CLUSTER_JOINED
        winner_cluster_id = result.final_state["candidates"]["A"]["cluster_id"]
        assert result.final_state["candidates"]["E"]["cluster_id"] == winner_cluster_id
        assert len(result.final_state["clusters"]) == 2  # A's (now incl. X, E) + D's frozen one

    def test_earliest_root_ties_break_by_candidate_id(self):
        # Same availability_us on both roots -- the tie breaks by candidate_id ascending ("A"<"D").
        a = occurrence("A", zone_low=0, zone_high=10, availability_us=500)
        d = occurrence("D", zone_low=100, zone_high=110, availability_us=500)
        x = occurrence("X", zone_low=5, zone_high=105, availability_us=500)
        result = run([a, d, x])
        assert result.events[-1]["root_candidate_id"] == "A"

    def test_later_root_availability_still_wins_by_earliest(self):
        # D's root is EARLIER in availability_us than A's, despite A's candidate_id sorting first
        # lexicographically -- availability_us is compared FIRST, candidate_id only breaks a tie.
        a = occurrence("A", zone_low=0, zone_high=10, availability_us=1_000)
        d = occurrence("D", zone_low=100, zone_high=110, availability_us=0)
        x = occurrence("X", zone_low=5, zone_high=105, availability_us=0)
        result = run([a, d, x])
        assert result.events[-1]["root_candidate_id"] == "D"


class TestRedeliveryIdempotent:
    def test_identical_redelivery_under_a_different_event_id_is_a_noop(self):
        a = occurrence("A", zone_low=0, zone_high=10, availability_us=0, event_id="e1")
        a_again = occurrence("A", zone_low=0, zone_high=10, availability_us=0, event_id="e2")
        first = run([a])
        result = run([a, a_again])
        assert result.final_state == first.final_state
        assert len(result.events) == 1


class TestContentMismatchRefused:
    def test_same_version_content_mismatch_is_refused(self):
        a = occurrence(
            "A", zone_low=0, zone_high=10, availability_us=0, occurrence_version=1,
            event_id="e1")
        conflict = occurrence(
            "A", zone_low=0, zone_high=10, availability_us=999, occurrence_version=1,
            event_id="e2")
        result = run([a, conflict])
        assert reason_codes(result) == [None, F19_CANDIDATE_CONTENT_MISMATCH]
        row = result.final_state["candidates"]["A"]
        assert row["availability_us"] == 0  # left exactly as it was


class TestRevisionUpdatesRow:
    def test_higher_occurrence_version_updates_that_row(self):
        a = occurrence(
            "A", zone_low=0, zone_high=10, availability_us=0, occurrence_version=1,
            event_id="e1")
        revision = occurrence(
            "A", zone_low=0, zone_high=10, availability_us=777, occurrence_version=2,
            event_id="e2")
        first = run([a])
        result = run([a, revision])
        assert event_kinds(result) == [CLUSTER_FORMED, CANDIDATE_REVISED]
        revised_event = result.events[-1]
        assert revised_event["from_occurrence_version"] == 1
        assert revised_event["to_occurrence_version"] == 2
        row = result.final_state["candidates"]["A"]
        assert row["availability_us"] == 777
        assert row["occurrence_version"] == 2
        # never re-root: cluster_id is unchanged from what the original occurrence assigned.
        (original_cluster_id,) = first.final_state["clusters"].keys()
        assert row["cluster_id"] == original_cluster_id
        assert list(result.final_state["clusters"].keys()) == [original_cluster_id]


class TestFailClosed:
    def test_missing_param_fails_closed(self):
        with pytest.raises(transition.MissingParameterError):
            transition.run(OpportunityClusterRegistry(), [occurrence("A")], {})

    def test_entry_zone_low_exceeding_high_refused(self):
        bad = occurrence("A", zone_low=100, zone_high=0)
        with pytest.raises(StructureLawError, match="entry_zone_low_ticks exceeds"):
            run([bad])

    def test_revision_may_not_change_instrument_or_side(self):
        a = occurrence(
            "A", side=common.LONG, zone_low=0, zone_high=10, availability_us=0,
            occurrence_version=1, event_id="e1")
        flipped = occurrence(
            "A", side=common.SHORT, zone_low=0, zone_high=10, availability_us=0,
            occurrence_version=2, event_id="e2")
        with pytest.raises(StructureLawError, match="may not change instrument or side"):
            run([a, flipped])


class TestInvariance:
    def test_prefix_and_restart_and_duplicate(self):
        a = occurrence("A", zone_low=0, zone_high=10, availability_us=0)
        b = occurrence(
            "B", zone_low=10, zone_high=20, availability_us=0, source_reaction_id="RY")
        c = occurrence(
            "C", zone_low=500, zone_high=600, availability_us=0, source_reaction_id="RY")
        full = [a, b, c]
        whole = run(full)
        prefix = run(full[:2])
        assert event_kinds(prefix) == [CLUSTER_FORMED, CLUSTER_JOINED]
        resumed = run(full[2:], initial=prefix.final_state)
        assert resumed.final_state == whole.final_state
        dup = run(full + [full[-1]])
        assert dup.final_state == whole.final_state
