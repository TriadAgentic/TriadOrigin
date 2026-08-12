"""E01 envelope boundary — Part A §1.1 VALID_BAR + Part C §C.3 validators
(TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12, B02C).

Every §1.1 clause is violated individually and must land in a typed quarantine with the right
reason; the trade/book validators get a positive vector plus one negative per required clause.
"""

from __future__ import annotations

import dataclasses

import pytest

from triad_origin import e01_interface as e01

INT64_MAX = 2**63 - 1
INT64_MIN = -(2**63)


def good_bar(**overrides) -> dict:
    bar = {
        "bar_identity": "BINANCE_USDM:BTCUSDT:PERP|1m|42",
        "metadata_revision": "rev1",
        "open_ticks": 1000,
        "high_ticks": 1015,
        "low_ticks": 992,
        "close_ticks": 1010,
        "base_volume": 250,
        "quote_volume": 251_000,
        "trade_count": 17,
    }
    bar.update(overrides)
    return bar


def good_trade(**overrides) -> dict:
    trade = {
        "trade_id": "T-0001",
        "revision": "rev1",
        "event_time_us": 1_700_000_000_000_000,
        "aggressor_side": "BUY",
    }
    trade.update(overrides)
    return trade


def good_book(**overrides) -> dict:
    update = {
        "sequence": 6,
        "event_time_us": 1_000_000,
        "best_bid_price_ticks": 999,
        "best_bid_qty_steps": 5,
        "best_ask_price_ticks": 1001,
        "best_ask_qty_steps": 7,
    }
    update.update(overrides)
    return update


def book_kwargs(**overrides) -> dict:
    kwargs = {"prior_seq": 5, "now_us": 1_000_500, "freshness_bound_us": 1_000}
    kwargs.update(overrides)
    return kwargs


def bar_reason(bar: dict) -> str:
    with pytest.raises(e01.QuarantineInvalidBar) as exc_info:
        e01.require_valid_bar(bar)
    return exc_info.value.reason


# --- §1.1 VALID_BAR: the positive vector -----------------------------------------------------


def test_valid_bar_passes_and_returns_a_frozen_validated_bar():
    validated = e01.require_valid_bar(good_bar())
    assert isinstance(validated, e01.ValidatedBar)
    assert validated.bar_identity == "BINANCE_USDM:BTCUSDT:PERP|1m|42"
    assert validated.metadata_revision == "rev1"
    assert (validated.open_ticks, validated.high_ticks, validated.low_ticks,
            validated.close_ticks) == (1000, 1015, 992, 1010)
    assert (validated.base_volume, validated.quote_volume, validated.trade_count) == (
        250, 251_000, 17)
    with pytest.raises(dataclasses.FrozenInstanceError):
        validated.close_ticks = 0  # type: ignore[misc]


def test_valid_bar_doji_and_zero_counts_are_lawful():
    # O == C == L == H with zero activity is a degenerate but VALID bar.
    validated = e01.require_valid_bar(good_bar(
        open_ticks=1000, high_ticks=1000, low_ticks=1000, close_ticks=1000,
        base_volume=0, quote_volume=0, trade_count=0))
    assert validated.trade_count == 0


# --- §1.1 clause 1: every field individually missing -----------------------------------------


@pytest.mark.parametrize("field", [
    "open_ticks", "high_ticks", "low_ticks", "close_ticks",
    "base_volume", "quote_volume", "trade_count",
])
def test_each_missing_field_quarantines_with_its_name(field):
    bar = good_bar()
    del bar[field]
    assert bar_reason(bar) == f"{field} is missing"
    # An explicit None is absence, never a value.
    assert bar_reason(good_bar(**{field: None})) == f"{field} is missing"


# --- §1.1 clause 2: signed int64 ticks -------------------------------------------------------


def test_price_field_at_int64_max_boundary_passes():
    validated = e01.require_valid_bar(good_bar(
        open_ticks=INT64_MAX - 2, high_ticks=INT64_MAX, low_ticks=INT64_MAX - 3,
        close_ticks=INT64_MAX - 1))
    assert validated.high_ticks == INT64_MAX


def test_price_field_one_beyond_int64_quarantines():
    reason = bar_reason(good_bar(high_ticks=2**63, close_ticks=2**63, open_ticks=2**63,
                                 low_ticks=2**63))
    assert "signed int64" in reason
    reason = bar_reason(good_bar(low_ticks=INT64_MIN - 1))
    assert "signed int64" in reason


def test_non_int_price_field_quarantines():
    assert "exact int" in bar_reason(good_bar(open_ticks="1000"))
    assert "exact int" in bar_reason(good_bar(close_ticks=1000.0))
    assert "exact int" in bar_reason(good_bar(high_ticks=True))


def test_count_field_beyond_int64_quarantines():
    assert "signed int64" in bar_reason(good_bar(quote_volume=2**63))


# --- §1.1 clauses 3/4/5: OHLC geometry --------------------------------------------------------


def test_open_below_low_quarantines():
    assert bar_reason(good_bar(open_ticks=991)) == \
        "low_ticks must satisfy low <= min(open, close)"


def test_close_below_low_quarantines():
    assert bar_reason(good_bar(close_ticks=991)) == \
        "low_ticks must satisfy low <= min(open, close)"


def test_open_above_high_quarantines():
    assert bar_reason(good_bar(open_ticks=1016)) == \
        "high_ticks must satisfy max(open, close) <= high"


def test_close_above_high_quarantines():
    assert bar_reason(good_bar(close_ticks=1016)) == \
        "high_ticks must satisfy max(open, close) <= high"


def test_low_above_high_never_passes():
    # low <= high is implied by clauses 3+4 and asserted anyway; a low>high bar must land in a
    # quarantine (whichever clause catches it first) — it can never construct a ValidatedBar.
    with pytest.raises(e01.QuarantineInvalidBar):
        e01.require_valid_bar(good_bar(low_ticks=1020, high_ticks=1005))


def test_boundary_geometry_is_inclusive():
    # open == low and close == high is VALID (<= is inclusive on both clauses).
    validated = e01.require_valid_bar(good_bar(open_ticks=992, close_ticks=1015))
    assert validated.open_ticks == 992 and validated.close_ticks == 1015


# --- §1.1 clause 6: non-negative volumes/count -------------------------------------------------


@pytest.mark.parametrize("field", ["base_volume", "quote_volume", "trade_count"])
def test_negative_volume_or_count_quarantines(field):
    assert bar_reason(good_bar(**{field: -1})) == f"{field} must be >= 0"


# --- identity / revision / record shape --------------------------------------------------------


def test_bar_without_identity_quarantines_with_none_identity():
    bar = good_bar()
    del bar["bar_identity"]
    with pytest.raises(e01.QuarantineInvalidBar) as exc_info:
        e01.require_valid_bar(bar)
    assert exc_info.value.bar_identity is None


def test_bar_without_metadata_revision_quarantines():
    bar = good_bar()
    del bar["metadata_revision"]
    assert bar_reason(bar) == "metadata_revision must be a non-empty str"


def test_non_object_bar_quarantines():
    with pytest.raises(e01.QuarantineInvalidBar):
        e01.require_valid_bar([1, 2, 3])


def test_quarantine_record_carries_identity_and_reason():
    with pytest.raises(e01.QuarantineInvalidBar) as exc_info:
        e01.require_valid_bar(good_bar(close_ticks=2000))
    record = exc_info.value.record()
    assert record == {
        "event_kind": "QUARANTINE",
        "accepted": False,
        "reason_code": "QUARANTINE_INVALID_BAR",
        "bar_identity": "BINANCE_USDM:BTCUSDT:PERP|1m|42",
        "reason": "high_ticks must satisfy max(open, close) <= high",
    }


# --- §C.3 validate_trade ------------------------------------------------------------------------


def test_validate_trade_positive_vector():
    validated = e01.validate_trade(good_trade())
    assert isinstance(validated, e01.ValidatedTrade)
    assert validated.trade_id == "T-0001"
    assert validated.revision == "rev1"
    assert validated.event_time_us == 1_700_000_000_000_000
    assert validated.aggressor_side == "BUY"
    assert e01.validate_trade(good_trade(aggressor_side="SELL")).aggressor_side == "SELL"
    with pytest.raises(dataclasses.FrozenInstanceError):
        validated.aggressor_side = "SELL"  # type: ignore[misc]


@pytest.mark.parametrize("field", ["trade_id", "revision", "event_time_us", "aggressor_side"])
def test_validate_trade_each_required_field_missing_rejects(field):
    trade = good_trade()
    del trade[field]
    with pytest.raises(e01.QuarantineInvalidTrade):
        e01.validate_trade(trade)


def test_validate_trade_unknown_or_non_string_aggressor_rejects():
    for junk in ("buy", "MAKER", True, 1):
        with pytest.raises(e01.QuarantineInvalidTrade):
            e01.validate_trade(good_trade(aggressor_side=junk))


def test_validate_trade_malformed_time_rejects():
    with pytest.raises(e01.QuarantineInvalidTrade):
        e01.validate_trade(good_trade(event_time_us=-1))
    with pytest.raises(e01.QuarantineInvalidTrade):
        e01.validate_trade(good_trade(event_time_us=2**63))
    with pytest.raises(e01.QuarantineInvalidTrade):
        e01.validate_trade(good_trade(event_time_us="1000"))


def test_validate_trade_record_carries_trade_id_and_reason():
    with pytest.raises(e01.QuarantineInvalidTrade) as exc_info:
        e01.validate_trade(good_trade(revision=""))
    record = exc_info.value.record()
    assert record["reason_code"] == "QUARANTINE_INVALID_TRADE"
    assert record["trade_id"] == "T-0001"
    assert record["event_kind"] == "QUARANTINE"


# --- §C.3 validate_book_update --------------------------------------------------------------------


def test_validate_book_update_positive_vector_with_continuity():
    validated = e01.validate_book_update(good_book(), **book_kwargs())
    assert isinstance(validated, e01.ValidatedBookUpdate)
    assert validated.sequence == 6
    assert validated.best_bid_price_ticks == 999
    assert validated.best_ask_price_ticks == 1001
    with pytest.raises(dataclasses.FrozenInstanceError):
        validated.sequence = 7  # type: ignore[misc]


def test_validate_book_update_first_update_has_no_continuity_to_check():
    validated = e01.validate_book_update(good_book(sequence=41), **book_kwargs(prior_seq=None))
    assert validated.sequence == 41


@pytest.mark.parametrize("field", [
    "sequence", "event_time_us", "best_bid_price_ticks", "best_bid_qty_steps",
    "best_ask_price_ticks", "best_ask_qty_steps",
])
def test_validate_book_update_each_required_field_missing_rejects(field):
    update = good_book()
    del update[field]
    with pytest.raises(e01.QuarantineInvalidBookUpdate):
        e01.validate_book_update(update, **book_kwargs())


def test_sequence_gap_rejects_with_expected_and_got():
    with pytest.raises(e01.QuarantineInvalidBookUpdate) as exc_info:
        e01.validate_book_update(good_book(sequence=8), **book_kwargs(prior_seq=5))
    assert "expected 6, got 8" in exc_info.value.reason


def test_duplicate_and_backward_sequence_reject():
    with pytest.raises(e01.QuarantineInvalidBookUpdate):
        e01.validate_book_update(good_book(sequence=5), **book_kwargs(prior_seq=5))
    with pytest.raises(e01.QuarantineInvalidBookUpdate):
        e01.validate_book_update(good_book(sequence=4), **book_kwargs(prior_seq=5))


def test_crossed_book_rejects():
    with pytest.raises(e01.QuarantineInvalidBookUpdate) as exc_info:
        e01.validate_book_update(
            good_book(best_bid_price_ticks=1002), **book_kwargs())
    assert "crossed or locked" in exc_info.value.reason


def test_locked_book_rejects():
    with pytest.raises(e01.QuarantineInvalidBookUpdate):
        e01.validate_book_update(
            good_book(best_bid_price_ticks=1001), **book_kwargs())


@pytest.mark.parametrize("field", ["best_bid_qty_steps", "best_ask_qty_steps"])
@pytest.mark.parametrize("qty", [0, -1])
def test_non_positive_quantity_rejects(field, qty):
    with pytest.raises(e01.QuarantineInvalidBookUpdate) as exc_info:
        e01.validate_book_update(good_book(**{field: qty}), **book_kwargs())
    assert "strictly positive" in exc_info.value.reason


def test_stale_update_rejects_and_the_bound_is_inclusive():
    # age == bound passes (inclusive); one microsecond beyond is stale.
    at_bound = e01.validate_book_update(
        good_book(), **book_kwargs(now_us=1_001_000, freshness_bound_us=1_000))
    assert at_bound.event_time_us == 1_000_000
    with pytest.raises(e01.QuarantineInvalidBookUpdate) as exc_info:
        e01.validate_book_update(
            good_book(), **book_kwargs(now_us=1_001_001, freshness_bound_us=1_000))
    assert "stale" in exc_info.value.reason


def test_future_event_time_rejects_fail_closed():
    with pytest.raises(e01.QuarantineInvalidBookUpdate) as exc_info:
        e01.validate_book_update(
            good_book(event_time_us=1_000_501), **book_kwargs(now_us=1_000_500))
    assert "future" in exc_info.value.reason


def test_book_record_carries_sequence_and_reason():
    with pytest.raises(e01.QuarantineInvalidBookUpdate) as exc_info:
        e01.validate_book_update(good_book(best_bid_qty_steps=0), **book_kwargs())
    record = exc_info.value.record()
    assert record["reason_code"] == "QUARANTINE_INVALID_BOOK_UPDATE"
    assert record["sequence"] == 6
    assert record["event_kind"] == "QUARANTINE"


# --- additive law: the pre-existing validators are untouched ------------------------------------


def test_existing_validate_finalized_bar_face_is_untouched():
    event = {
        "payload": {
            "state_kind": "BAR",
            "bar_finalization_state": "FINALIZED",
            "watermark_complete": True,
            "validity": "READY",
            "bar_index": 0,
            "bar_open_time_us": 0,
            "bar_close_time_us": 60_000_000,
            "open_ticks": 1000,
            "high_ticks": 1015,
            "low_ticks": 992,
            "close_ticks": 1010,
        }
    }
    accepted = e01.validate_finalized_bar(event)
    assert accepted["accepted"] is True and accepted["kind"] == "BAR"


def test_validated_types_are_defined_only_in_e01_interface():
    # The later CI static gate enforces construction-locality by scan; pin the module home now.
    for cls in (e01.ValidatedBar, e01.ValidatedTrade, e01.ValidatedBookUpdate):
        assert cls.__module__ == "triad_origin.e01_interface"
        assert dataclasses.is_dataclass(cls)
