"""Causal clocks, watermark, single-writer coordinator and the E01 quality machine."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from triad_origin import clock_watermark as cw
from triad_origin import partition as P
from triad_origin.partition import PartitionKey, Quality, QualityEvent


def test_clocks_reject_acausal_ordering():
    cw.Clocks(10, 10, 10, 10)  # ok: equal is allowed
    with pytest.raises(cw.ClockError):
        cw.Clocks(event_time_us=10, availability_time_us=9, knowledge_time_us=10,
                  publication_time_us=10)


def test_watermark_is_monotonic():
    wm = cw.Watermark(allowed_lateness_us=5)
    wm.advance(100)
    wm.advance(200)
    assert wm.is_complete_for(200) and not wm.is_complete_for(201)
    with pytest.raises(cw.ClockError):
        wm.advance(150)


def test_watermark_lateness():
    wm = cw.Watermark(allowed_lateness_us=5, completed_through_us=100)
    assert wm.is_late(90)
    assert not wm.is_late(96)


def test_watermark_configuration_and_progress_cannot_be_mutated_around_guard():
    wm = cw.Watermark(allowed_lateness_us=5)
    wm.advance(100)
    with pytest.raises(AttributeError):
        wm.completed_through_us = 0
    with pytest.raises(AttributeError):
        wm.allowed_lateness_us = -1
    with pytest.raises(cw.ClockError):
        wm.advance(50)


def test_no_future_venue_read():
    with pytest.raises(cw.ClockError):
        cw.assert_not_future_venue_read(reader_knowledge_us=100, other_venue_knowledge_us=101)
    cw.assert_not_future_venue_read(reader_knowledge_us=100, other_venue_knowledge_us=100)


def test_cross_venue_causality_uses_other_knowledge_not_event_time():
    late_fact = cw.Clocks(50, 50, 200, 200)
    with pytest.raises(cw.ClockError):
        cw.assert_not_future_venue_read(
            reader_knowledge_us=100,
            other_venue_knowledge_us=late_fact.knowledge_time_us,
        )


@pytest.mark.parametrize("bad", [True, 1.0, -(2**63) - 1, 2**63])
def test_clock_fields_require_signed_int64(bad):
    with pytest.raises(cw.ClockError):
        cw.Clocks(bad, 10, 10, 10)


def test_single_writer_lock():
    coord = P.PartitionCoordinator()
    key = PartitionKey("BINANCE_USDM", "BTCUSDT", "15m")
    coord.claim(key, "writer_a")
    coord.claim(key, "writer_a")  # idempotent for same writer
    assert coord.next_seq(key, "writer_a") == 0
    assert coord.next_seq(key, "writer_a") == 1
    with pytest.raises(P.PartitionError):
        coord.claim(key, "writer_b")
    with pytest.raises(P.PartitionError):
        coord.next_seq(key, "writer_b")


def test_concurrent_partition_claim_grants_only_one_writer():
    coord = P.PartitionCoordinator()
    key = PartitionKey("BINANCE_USDM", "BTCUSDT", "15m")
    barrier = Barrier(2)

    def claim(writer):
        barrier.wait()
        try:
            coord.claim(key, writer)
        except P.PartitionError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(claim, ["writer_a", "writer_b"]))
    assert sorted(outcomes) == [False, True]


def test_partition_key_string_is_injective_by_construction():
    with pytest.raises(P.PartitionError, match="delimiter"):
        PartitionKey("A|B", "C", "D")


def test_partition_key_normalizes_canonical_unicode_before_ownership():
    composed = PartitionKey("é", "BTC", "1m")
    decomposed = PartitionKey("e\u0301", "BTC", "1m")
    assert composed == decomposed
    coordinator = P.PartitionCoordinator()
    coordinator.claim(composed, "one")
    with pytest.raises(P.PartitionError):
        coordinator.claim(decomposed, "two")


def test_partition_and_writer_identity_are_canonical_wire_values():
    with pytest.raises(P.PartitionError, match="canonical-wire"):
        PartitionKey("\ud800", "BTC", "1m")
    key = PartitionKey("venue", "BTC", "1m")
    coordinator = P.PartitionCoordinator()
    coordinator.claim(key, "é")
    coordinator.claim(key, "e\u0301")
    assert coordinator.next_seq(key, "e\u0301") == 0
    with pytest.raises(P.PartitionError, match="canonical-wire"):
        coordinator.claim(key, "\ud800")


def _ordered_event(raw_id, *, source, connection, receive, receipt):
    return {
        "raw_event_id": raw_id,
        "venue": "BINANCE_USDM",
        "route_family": "PUBLIC",
        "source_stream": source,
        "connection_epoch": connection,
        "receive_sequence": receive,
        "local_receipt_mono_ns": receipt,
    }


def test_cross_source_order_preserves_local_receipt():
    events = [
        _ordered_event("later-b", source="book-b", connection=8, receive=1, receipt=20),
        _ordered_event("first-a", source="book-a", connection=7, receive=100, receipt=10),
    ]
    ordered = [e["raw_event_id"] for e in P.deterministic_order(events)]
    assert ordered == ["first-a", "later-b"]


def test_equal_receipt_uses_sequence_only_within_source():
    events = [
        _ordered_event("two", source="book-a", connection=7, receive=2, receipt=10),
        _ordered_event("one", source="book-a", connection=7, receive=1, receipt=10),
    ]
    assert [e["raw_event_id"] for e in P.deterministic_order(events)] == ["one", "two"]


def test_source_sequence_regression_fails_closed():
    events = [
        _ordered_event("two", source="book-a", connection=7, receive=2, receipt=10),
        _ordered_event("one", source="book-a", connection=7, receive=1, receipt=20),
    ]
    with pytest.raises(P.PartitionError):
        P.deterministic_order(events)


def test_exact_duplicate_ordering_input_is_idempotent():
    event = _ordered_event("one", source="book-a", connection=7, receive=1, receipt=10)
    assert P.deterministic_order([event, dict(event)]) == [event]


def test_same_receive_sequence_with_different_bytes_is_not_a_duplicate():
    first = _ordered_event("one", source="book-a", connection=7, receive=1, receipt=10)
    conflict = {**first, "raw_event_id": "other"}
    with pytest.raises(P.PartitionError, match="receive_sequence regression"):
        P.deterministic_order([first, conflict])


@pytest.mark.parametrize(
    "bad",
    [1.0, "01", "+1", " 1", "1 ", True, "١", "9" * 5_000],
)
def test_ordering_rejects_noncanonical_numeric_values(bad):
    event = _ordered_event("one", source="book-a", connection=7, receive=1, receipt=10)
    event["local_receipt_mono_ns"] = bad
    with pytest.raises(P.PartitionError, match="not (?:an integer|canonical)"):
        P.deterministic_order([event])


@pytest.mark.parametrize("field", ["connection_epoch", "receive_sequence"])
def test_source_ordering_counters_reject_negative_values(field):
    event = _ordered_event("one", source="book-a", connection=7, receive=1, receipt=10)
    event[field] = -1
    with pytest.raises(P.PartitionError, match="non-negative"):
        P.deterministic_order([event])


def test_ordering_rejects_negative_monotonic_receipt():
    event = _ordered_event("one", source="book-a", connection=7, receive=1, receipt=-1)
    with pytest.raises(P.PartitionError, match="non-negative"):
        P.deterministic_order([event])


@pytest.mark.parametrize("field", ["raw_event_id", "venue", "route_family", "source_stream"])
def test_ordering_identity_fields_are_not_string_coerced(field):
    event = _ordered_event("one", source="book-a", connection=7, receive=1, receipt=10)
    event[field] = 1
    with pytest.raises(P.PartitionError, match="not a string"):
        P.deterministic_order([event])


def test_quality_machine_paths():
    s = Quality.INIT
    s = P.quality_transition(s, QualityEvent.START)
    assert s is Quality.SYNCING
    s = P.quality_transition(s, QualityEvent.SNAPSHOT_ALIGNED)
    assert s is Quality.READY and P.entry_eligible(s)
    s = P.quality_transition(s, QualityEvent.SEQUENCE_GAP)
    assert s is Quality.GAPPED and not P.entry_eligible(s)
    s = P.quality_transition(s, QualityEvent.RECOVERY_BEGIN)
    assert s is Quality.RESYNCING
    s = P.quality_transition(s, QualityEvent.RESNAPSHOT_COMPLETE)
    assert s is Quality.READY


def test_metadata_invalid_from_any_state():
    assert P.quality_transition(Quality.READY, QualityEvent.METADATA_INVALID) is Quality.DEGRADED


def test_undefined_transition_fails_closed():
    with pytest.raises(P.QualityTransitionError):
        P.quality_transition(Quality.INIT, QualityEvent.SNAPSHOT_ALIGNED)
