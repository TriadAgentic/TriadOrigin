"""Integer tick/step algebra + fail-closed boundary conversion (MOD-004)."""

from __future__ import annotations

from decimal import localcontext

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


def test_qty_one_unit_boundaries_are_exact():
    # F00 golden_boundary_tests: equality + one-unit-short/over on the quantity axis.
    assert im.qty_to_steps(BTC, "0.011") == 11
    assert im.qty_to_steps(BTC, "0.013") == 13


def test_qty_default_quarantines_off_grid_quantity():
    # F00 venue-fact ingress (units_rounding: no floor/ceil/tolerance): an off-grid quantity
    # quarantines under the EXACT default — it is never silently floored to a valid step.
    with pytest.raises(im.InstrumentError, match="fractional decimal place"):
        im.qty_to_steps(BTC, "0.9809")  # 4 places against the 0.001 (3-place) step


def test_qty_exact_rejects_non_multiple():
    # correctly-formatted (3 places) but not an exact multiple of the 0.005 step -> quarantine.
    instrument = Instrument("I", "V", "0.10", "0.005", "0", "r")
    with pytest.raises(im.InstrumentError, match="not an exact multiple"):
        im.qty_to_steps(instrument, "0.012")


@pytest.mark.parametrize("mode", [Rounding.DOWN, Rounding.UP, Rounding.HALF_EVEN])
def test_qty_to_steps_is_exact_only(mode):
    # errata F00: quantity floor-to-step belongs only to F20/F22; F00 ingress may not floor a
    # venue fact. Any non-EXACT mode is refused by name, never silently floored.
    with pytest.raises(im.InstrumentError, match="EXACT-only"):
        im.qty_to_steps(BTC, "0.9809", mode)


def test_boundary_formatting_is_independent_of_global_decimal_context():
    expected = ("62123.40", "123.456")
    for precision in (2, 5, 28):
        with localcontext() as context:
            context.prec = precision
            assert (
                im.ticks_to_price(BTC, 621234),
                im.steps_to_qty(BTC, 123456),
            ) == expected


def test_overflow_is_fail_closed():
    with pytest.raises(im.InstrumentError):
        im.add_ticks(im.INT64_MAX, 1)


def test_bps_ceiling_is_integer_exact():
    # ceil(621234 * 7 / 10000) = ceil(434.86) = 435
    assert im.bps_of_ticks(621234, 7) == 435


@pytest.mark.parametrize("bad", [True, 1.5, "1"])
def test_integer_helpers_reject_non_integer_operands(bad):
    with pytest.raises(im.InstrumentError):
        im.add_ticks(bad, 1)
    with pytest.raises(im.InstrumentError):
        im.bps_of_ticks(bad, 1)


@pytest.mark.parametrize("bad", [-1, True, 1.5, "7"])
def test_bps_rejects_negative_or_non_integer_values(bad):
    with pytest.raises(im.InstrumentError):
        im.bps_of_ticks(100, bad)


@pytest.mark.parametrize(
    "bad", [
        True, 1.0, " 1.00", "+1.00", "01.00", "1e0", "1.0", "1.000", "-0.00",
        "9" * 5_000,
    ]
)
def test_decimal_boundary_requires_canonical_string(bad):
    with pytest.raises(im.InstrumentError):
        im.price_to_ticks(BTC, bad)


def test_bps_rejects_signed_int64_intermediate_overflow():
    with pytest.raises(im.InstrumentError, match="bps numerator"):
        im.bps_of_ticks(im.INT64_MAX, 2)


def test_half_even_rounding_is_integer_exact_for_negative_and_positive_ties():
    unit = Instrument("I", "V", "1.00", "1.00", "0", "r")
    assert im.price_to_ticks(unit, "2.50", Rounding.HALF_EVEN) == 2
    assert im.price_to_ticks(unit, "3.50", Rounding.HALF_EVEN) == 4
    assert im.price_to_ticks(unit, "-2.50", Rounding.HALF_EVEN) == -2
    assert im.price_to_ticks(unit, "-3.50", Rounding.HALF_EVEN) == -4


@pytest.mark.parametrize(
    "tick, step, expected",
    [("0.25", "0.5", "0.125"), ("0.125", "0.2", "0.0250"), ("0.50", "0.05", "0.0250")],
)
def test_notional_format_uses_original_decimal_coefficients(tick, step, expected):
    instrument = Instrument("I", "V", tick, step, "0", "r")
    assert im.notional_quote(instrument, 1, 1) == expected


def test_bad_instrument_metadata_fails_closed():
    with pytest.raises(im.InstrumentError):
        Instrument("X", "V", "0", "0.1", "5", "r")


def test_digest_is_stable():
    assert BTC.digest == Instrument(
        "BINANCE_USDM:BTCUSDT:PERP", "BINANCE_USDM", "0.10", "0.001", "5", "rev1").digest
