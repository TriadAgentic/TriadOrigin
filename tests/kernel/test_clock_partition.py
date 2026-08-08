"""Causal clocks, watermark, single-writer coordinator and the E01 quality machine."""

from __future__ import annotations

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


def test_no_future_venue_read():
    with pytest.raises(cw.ClockError):
        cw.assert_not_future_venue_read(reader_knowledge_us=100, other_venue_event_us=101)
    cw.assert_not_future_venue_read(reader_knowledge_us=100, other_venue_event_us=100)


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
