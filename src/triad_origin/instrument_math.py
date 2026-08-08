"""Integer tick/step algebra and fail-closed boundary conversion (MOD-004, Doc 02 §02.2).

All prices enter *semantic* code as signed 64-bit integer ticks under a pinned instrument metadata
revision. The only place decimals are permitted is this boundary module, which converts a venue
decimal price/quantity into integer ticks/steps and back. Overflow and conversion error are
**fail-closed**; there is no silent rounding on the semantic path.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
import re

from .canonical import INT64_MAX, INT64_MIN, digest_fields


class InstrumentError(ValueError):
    """Invalid instrument metadata or an out-of-domain conversion. Fail closed."""


class Rounding(str, Enum):
    """Explicit rounding mode. There is no default — the caller always names it."""

    DOWN = "DOWN"      # toward -inf on the number line (conservative for a BUY maker price)
    UP = "UP"          # toward +inf (conservative for a SELL maker price)
    HALF_EVEN = "HALF_EVEN"
    EXACT = "EXACT"    # reject if not an exact multiple


@dataclass(frozen=True)
class Instrument:
    """Pinned instrument metadata revision. Semantic code references this by ``revision``/``digest``."""

    canonical_instrument_id: str
    venue_model: str
    tick_size: str   # decimal string, e.g. "0.10"
    step_size: str   # decimal string, e.g. "0.001"
    min_notional: str  # decimal string quote notional
    revision: str

    @property
    def tick(self) -> Decimal:
        return _dec(self.tick_size)

    @property
    def step(self) -> Decimal:
        return _dec(self.step_size)

    @property
    def digest(self) -> str:
        return digest_fields(
            "instrument", self.canonical_instrument_id, self.venue_model, self.tick_size,
            self.step_size, self.min_notional, self.revision)

    def __post_init__(self) -> None:
        for name, value in (
            ("canonical_instrument_id", self.canonical_instrument_id),
            ("venue_model", self.venue_model),
            ("revision", self.revision),
        ):
            if not isinstance(value, str) or not value:
                raise InstrumentError(f"{name} must be a non-empty string")
        if self.tick <= 0 or self.step <= 0:
            raise InstrumentError("tick_size and step_size must be positive")
        if _dec(self.min_notional) < 0:
            raise InstrumentError("min_notional must be non-negative")


def _dec(s: str) -> Decimal:
    if not isinstance(s, str) or len(s) > 128:
        raise InstrumentError(f"not a bounded canonical decimal string: {s!r}")
    if re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", s) is None:
        raise InstrumentError(f"not a canonical decimal string: {s!r}")
    try:
        d = Decimal(s)
    except (InvalidOperation, TypeError) as exc:
        raise InstrumentError(f"not a decimal: {s!r}") from exc
    if not d.is_finite():
        raise InstrumentError(f"non-finite decimal: {s!r}")
    if d == 0 and s.startswith("-"):
        raise InstrumentError("negative zero is not canonical")
    return d


def _scaled_dec(text: str, unit: Decimal, what: str) -> Decimal:
    value = _dec(text)
    places = max(0, -unit.as_tuple().exponent)
    expected = format(value, f".{places}f")
    if text != expected:
        raise InstrumentError(
            f"{what} must use exactly {places} fractional decimal place(s): {text!r}"
        )
    return value


def _guard_int64(value: int, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InstrumentError(f"{what} must be an int")
    if value < INT64_MIN or value > INT64_MAX:
        raise InstrumentError(f"{what} out of signed 64-bit range")
    return value


def _quantize(raw: Decimal, unit: Decimal, mode: Rounding) -> int:
    raw_num, raw_den = raw.as_integer_ratio()
    unit_num, unit_den = unit.as_integer_ratio()
    numerator = raw_num * unit_den
    denominator = raw_den * unit_num
    quotient, remainder = divmod(numerator, denominator)
    if mode is Rounding.EXACT:
        if remainder:
            raise InstrumentError(f"{raw} is not an exact multiple of {unit}")
        return quotient
    if mode is Rounding.DOWN:
        return quotient
    if mode is Rounding.UP:
        return quotient if remainder == 0 else quotient + 1
    if mode is Rounding.HALF_EVEN:
        doubled = remainder * 2
        if doubled < denominator:
            return quotient
        if doubled > denominator:
            return quotient + 1
        return quotient if quotient % 2 == 0 else quotient + 1
    raise InstrumentError(f"unknown rounding mode: {mode}")  # pragma: no cover


def price_to_ticks(instrument: Instrument, price: str, mode: Rounding = Rounding.EXACT) -> int:
    """Convert a venue decimal price to integer ticks. ``EXACT`` is the default and fails closed."""
    return _guard_int64(
        _quantize(_scaled_dec(price, instrument.tick, "price"), instrument.tick, mode),
        "price ticks",
    )


def ticks_to_price(instrument: Instrument, ticks: int) -> str:
    """Convert integer ticks back to a canonical decimal price string."""
    if isinstance(ticks, bool) or not isinstance(ticks, int):
        raise InstrumentError("ticks must be an int")
    _guard_int64(ticks, "price ticks")
    coefficient, exponent = _decimal_coefficient(instrument.tick)
    return _format_coefficient(coefficient * ticks, exponent)


def qty_to_steps(instrument: Instrument, qty: str, mode: Rounding = Rounding.EXACT) -> int:
    return _guard_int64(
        _quantize(_scaled_dec(qty, instrument.step, "quantity"), instrument.step, mode),
        "qty steps",
    )


def steps_to_qty(instrument: Instrument, steps: int) -> str:
    if isinstance(steps, bool) or not isinstance(steps, int):
        raise InstrumentError("steps must be an int")
    _guard_int64(steps, "qty steps")
    coefficient, exponent = _decimal_coefficient(instrument.step)
    return _format_coefficient(coefficient * steps, exponent)


# --- pure integer helpers (semantic path: ints only) ---------------------------------------------
def add_ticks(a: int, b: int) -> int:
    _guard_int64(a, "left tick operand")
    _guard_int64(b, "right tick operand")
    return _guard_int64(a + b, "tick sum")


def bps_of_ticks(price_ticks: int, bps: int) -> int:
    """Ceil( |price_ticks| * bps / 10_000 ) as integer ticks (Doc 02 §02.4 δ term).

    Integer-exact ceiling division; no floats on the semantic path.
    """
    _guard_int64(price_ticks, "price ticks")
    if isinstance(bps, bool) or not isinstance(bps, int) or bps < 0:
        raise InstrumentError("bps must be a non-negative int")
    num = abs(price_ticks) * bps
    _guard_int64(num, "bps numerator")
    ticks = -(-num // 10_000)  # ceil division
    return _guard_int64(ticks, "bps ticks")


def notional_quote(instrument: Instrument, price_ticks: int, qty_steps: int) -> str:
    """Quote notional as a canonical decimal string (boundary/reporting value, not semantic int)."""
    _guard_int64(price_ticks, "price ticks")
    _guard_int64(qty_steps, "qty steps")
    tick_coefficient, tick_exponent = _decimal_coefficient(instrument.tick)
    step_coefficient, step_exponent = _decimal_coefficient(instrument.step)
    coefficient = tick_coefficient * step_coefficient * price_ticks * qty_steps
    return _format_coefficient(coefficient, tick_exponent + step_exponent)


def _decimal_coefficient(value: Decimal) -> tuple[int, int]:
    parts = value.as_tuple()
    coefficient = int("".join(str(digit) for digit in parts.digits) or "0")
    return (-coefficient if parts.sign else coefficient), parts.exponent


def _format_coefficient(coefficient: int, exponent: int) -> str:
    """Format ``coefficient * 10**exponent`` exactly, independent of Decimal context."""
    sign = "-" if coefficient < 0 else ""
    digits = str(abs(coefficient))
    if exponent >= 0:
        return sign + digits + ("0" * exponent)
    scale = -exponent
    digits = digits.rjust(scale + 1, "0")
    return sign + digits[:-scale] + "." + digits[-scale:]
