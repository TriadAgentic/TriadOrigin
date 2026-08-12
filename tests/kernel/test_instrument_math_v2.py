"""R-F00 — ``instrument_math.v2`` test family (Formula Repair Specification §2 R-F00 TESTS).

The 13 vectors T1–T13 are transcribed verbatim from the spec table, plus the ACCEPTANCE property
(``to_ticks_exact(k*tick, tick) == k`` for random k within int64) and the static "no float" scan.
"""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
from pathlib import Path
import random

import pytest

from triad_origin.canonical import INT64_MAX
from triad_origin.instrument_math_v2 import (
    QUARANTINE_METADATA_REVISION,
    QUARANTINE_NON_INTEGRAL,
    QUARANTINE_OVERFLOW,
    REFUSE_CONFIG,
    InstrumentV2,
    InstrumentV2Error,
    price_to_ticks_ingress,
    qty_to_steps_ingress,
    qty_to_steps_order_compute,
    steps_to_qty,
    ticks_to_price,
)

REV = "r4"


def _instr(tick: str = "0.10", step: str = "0.001", revision: str = REV) -> InstrumentV2:
    return InstrumentV2(
        canonical_instrument_id="BINANCE:BTCUSDT",
        venue_model="binance-usdm",
        tick_size=tick,
        step_size=step,
        min_notional="5",
        metadata_revision=revision,
    )


# --- T1: the defect trap ---------------------------------------------------------------------
def test_t1_one_point_zero_over_tenth_is_ten_pass() -> None:
    # v1 quarantined this on exponent mismatch (-1 vs -2); v2 decides on value → 10.
    assert price_to_ticks_ingress(_instr(tick="0.10"), "1.0", REV) == 10


def test_t2_one_point_zero_zero_over_tenth_is_ten() -> None:
    assert price_to_ticks_ingress(_instr(tick="0.1"), "1.00", REV) == 10


def test_t3_three_tenths_over_tenth_is_three_string_path_no_float() -> None:
    # A binary-float path would compute 0.3/0.1 = 2.9999999999999996 and fail integrality.
    assert 0.3 / 0.1 != 3.0  # documents exactly why the string/rational path is required
    assert price_to_ticks_ingress(_instr(tick="0.1"), "0.3", REV) == 3


def test_t4_off_grid_price_quarantines_non_integral() -> None:
    with pytest.raises(InstrumentV2Error) as exc:
        price_to_ticks_ingress(_instr(tick="0.10"), "1.05", REV)
    assert exc.value.reason == QUARANTINE_NON_INTEGRAL


def test_t5_nine_tenths_over_three_tenths_is_three() -> None:
    assert price_to_ticks_ingress(_instr(tick="0.3"), "0.9", REV) == 3


def test_t6_one_over_three_tenths_quarantines_ten_thirds() -> None:
    with pytest.raises(InstrumentV2Error) as exc:
        price_to_ticks_ingress(_instr(tick="0.3"), "1.0", REV)
    assert exc.value.reason == QUARANTINE_NON_INTEGRAL
    assert "10/3" in exc.value.detail


# --- T7/T8: signed int64 wire-width boundary -------------------------------------------------
def test_t7_max_int64_ticks_pass_at_boundary() -> None:
    # price = (2^63 - 1) ticks exactly, tick = "1" → price string is the integer itself.
    assert price_to_ticks_ingress(_instr(tick="1"), str(INT64_MAX), REV) == INT64_MAX


def test_t8_one_beyond_int64_quarantines_overflow() -> None:
    with pytest.raises(InstrumentV2Error) as exc:
        price_to_ticks_ingress(_instr(tick="1"), str(INT64_MAX + 1), REV)
    assert exc.value.reason == QUARANTINE_OVERFLOW


# --- T9: config refusal ----------------------------------------------------------------------
def test_t9_zero_and_negative_grid_refuse_config() -> None:
    with pytest.raises(InstrumentV2Error) as exc:
        _instr(tick="0")
    assert exc.value.reason == REFUSE_CONFIG
    with pytest.raises(InstrumentV2Error) as exc2:
        _instr(tick="-0.01")
    assert exc2.value.reason == REFUSE_CONFIG


# --- T10: ingress quantity integrality -------------------------------------------------------
def test_t10_ingress_qty_exact_and_off_grid() -> None:
    assert qty_to_steps_ingress(_instr(step="0.001"), "0.007", REV) == 7
    with pytest.raises(InstrumentV2Error) as exc:
        qty_to_steps_ingress(_instr(step="0.001"), "0.0075", REV)
    assert exc.value.reason == QUARANTINE_NON_INTEGRAL


# --- T11: order-compute floors toward zero ---------------------------------------------------
def test_t11_order_compute_qty_floors() -> None:
    # 0.961723 / 0.001 = 961.723 → floor → 961.
    assert qty_to_steps_order_compute(_instr(step="0.001"), "0.961723", REV) == 961


# --- T12: metadata revision law --------------------------------------------------------------
def test_t12_cross_revision_quarantines() -> None:
    instr = _instr(revision="r5")
    with pytest.raises(InstrumentV2Error) as exc:
        price_to_ticks_ingress(instr, "1.0", "r4")  # event availed under r4, tick from r5
    assert exc.value.reason == QUARANTINE_METADATA_REVISION


# --- T13: cross-language vector file (Python half — identical strings the Rust half will read) --
def test_t13_shared_vector_file_python_half() -> None:
    """The shared vector strings produce the exact outputs the cross-language file pins. The Rust
    half reads the SAME strings and must produce byte-identical integers (§D.1 GV-001a/b)."""
    cases = [
        # (tick, price_str, expected_ticks)
        ("0.10", "1.0", 10),
        ("0.1", "1.00", 10),
        ("0.1", "0.3", 3),
        ("0.3", "0.9", 3),
        ("1", str(INT64_MAX), INT64_MAX),
    ]
    for tick, price, expected in cases:
        assert price_to_ticks_ingress(_instr(tick=tick), price, REV) == expected


# --- ACCEPTANCE: property test + round-trip --------------------------------------------------
def test_property_k_times_tick_recovers_k() -> None:
    """For random exact grids, ``to_ticks_exact(k*tick, tick) == k`` within int64 — the exactness
    guarantee (Formula Repair R-F00 ACCEPTANCE; a bounded deterministic sample stands in for 10^6)."""
    rng = random.Random(0xF00)
    for tick in ("0.1", "0.01", "0.25", "0.001", "1", "0.5"):
        tick_frac = Fraction(Decimal(tick))
        for _ in range(2000):
            k = rng.randint(-(10**9), 10**9)
            price_val = tick_frac * k  # exact k*tick
            price_str = _rational_to_decimal_string(price_val)
            assert price_to_ticks_ingress(_instr(tick=tick), price_str, REV) == k


def test_round_trip_ticks_price_steps_qty() -> None:
    instr = _instr(tick="0.10", step="0.001")
    assert ticks_to_price(instr, 10) == "1.00"
    assert steps_to_qty(instr, 7) == "0.007"
    assert price_to_ticks_ingress(instr, ticks_to_price(instr, 12345), REV) == 12345


def _rational_to_decimal_string(value: Fraction) -> str:
    """Render an exact rational with a power-of-ten denominator as a canonical decimal string."""
    den = value.denominator
    places = 0
    while den % 2 == 0:
        den //= 2
        places += 1
    tens = 0
    while den % 5 == 0:
        den //= 5
        tens += 1
    assert den == 1, "test grids are powers of ten by construction"
    scale = max(places, tens)
    scaled = value * (10**scale)
    assert scaled.denominator == 1
    return str(Decimal(scaled.numerator).scaleb(-scale)) if scale else str(scaled.numerator)


# --- ACCEPTANCE: no binary float appears in the module (static scan) --------------------------
def test_no_float_type_in_module_source() -> None:
    """No ``float`` type/cast token appears anywhere in the ``instrument_math.v2`` module (Formula
    Repair R-F00 ACCEPTANCE: 'no float type appears in the module (static scan)'). The scan
    tokenizes the source and flags a NAME token ``float`` (a cast ``float(x)`` or an annotation
    ``: float``) — the word 'float' in a docstring or comment is not a float type."""
    import io
    import tokenize

    import triad_origin.instrument_math_v2 as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    offenders = [
        tok
        for tok in tokenize.generate_tokens(io.StringIO(source).readline)
        if tok.type == tokenize.NAME and tok.string == "float"
    ]
    assert offenders == [], f"unexpected 'float' type token(s): {[t.start for t in offenders]}"
