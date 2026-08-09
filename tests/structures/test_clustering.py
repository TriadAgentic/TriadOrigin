"""F19 opportunity-clustering battery: GV-016, boundary, mirror, transitive join, redelivery,
ambiguous merge, fail-closed, invariance."""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import transition  # noqa: E402
from triad_origin.structures import common  # noqa: E402
from triad_origin.structures.common import StructureLawError  # noqa: E402
from triad_origin.structures.clustering import (  # noqa: E402
    CANDIDATE_REVISED,
    CLUSTER_FORMED,
    CLUSTER_JOINED,
    F19_AMBIGUOUS_CLUSTER_MERGE,
    F19_CANDIDATE_CONTENT_MISMATCH,
    OpportunityClusterRegistry,
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

    def test_boundary_one_ms_past_window_with_no_source_overlap_is_separate(self):
        a = occurrence("A", zone_low=0, zone_high=100, availability_us=0)
        b = occurrence("B", zone_low=100, zone_high=200, availability_us=30_001_000)
        result = run([a, b])
        assert event_kinds(result) == [CLUSTER_FORMED, CLUSTER_FORMED]
        assert len(result.final_state["clusters"]) == 2


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


class TestAmbiguousMerge:
    def test_ambiguous_simultaneous_merge_is_named_not_silently_resolved(self):
        a = occurrence("A", zone_low=0, zone_high=10, availability_us=0)
        d = occurrence("D", zone_low=100, zone_high=110, availability_us=0)
        x = occurrence("X", zone_low=5, zone_high=105, availability_us=0)
        result = run([a, d, x])
        assert F19_AMBIGUOUS_CLUSTER_MERGE in reason_codes(result)
        assert "X" not in result.final_state["candidates"]
        assert len(result.final_state["clusters"]) == 2  # only A's and D's; X was refused


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
