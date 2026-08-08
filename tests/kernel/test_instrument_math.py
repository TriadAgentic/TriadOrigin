"""Integer tick/step algebra + fail-closed boundary conversion (MOD-004)."""

from __future__ import annotations

import pytest

from triad_origin import instrument_math as im
from triad_origin.instrument_math import Instrument, Rounding

BTC = Instrument("BINANCE_USDM:BTCUSDT:PERP", "BINANCE_USDM", "0.10", "0.001", "5", "rev1")


def test_price_roundtrip_exact():
    ticks = im.price_to_ticks(BTC, "62123.40")
    assert ticks == 621234
    assert im.ticks_to_price(BTC, ticks) == "62123.40"


def test_exact_rejects_non_multiple():
    with pytest.raises(im.InstrumentError):
        im.price_to_ticks(BTC, "62123.45")  # not a multiple of 0.10


def test_rounding_modes_are_explicit():
    assert im.price_to_ticks(BTC, "62123.45", Rounding.DOWN) == 621234
    assert im.price_to_ticks(BTC, "62123.45", Rounding.UP) == 621235


def test_qty_roundtrip():
    steps = im.qty_to_steps(BTC, "0.012")
    assert steps == 12
    assert im.steps_to_qty(BTC, steps) == "0.012"


def test_overflow_is_fail_closed():
    with pytest.raises(im.InstrumentError):
        im.add_ticks(im.INT64_MAX, 1)


def test_bps_ceiling_is_integer_exact():
    # ceil(621234 * 7 / 10000) = ceil(434.86) = 435
    assert im.bps_of_ticks(621234, 7) == 435


def test_bad_instrument_metadata_fails_closed():
    with pytest.raises(im.InstrumentError):
        Instrument("X", "V", "0", "0.1", "5", "r")


def test_digest_is_stable():
    assert BTC.digest == Instrument(
        "BINANCE_USDM:BTCUSDT:PERP", "BINANCE_USDM", "0.10", "0.001", "5", "rev1").digest
