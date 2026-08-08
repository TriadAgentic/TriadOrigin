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
        if self.tick <= 0 or self.step <= 0:
            raise InstrumentError("tick_size and step_size must be positive")


def _dec(s: str) -> Decimal:
    try:
        d = Decimal(s)
    except (InvalidOperation, TypeError) as exc:
        raise InstrumentError(f"not a decimal: {s!r}") from exc
    if not d.is_finite():
        raise InstrumentError(f"non-finite decimal: {s!r}")
    return d


def _guard_int64(value: int, what: str) -> int:
    if value < INT64_MIN or value > INT64_MAX:
        raise InstrumentError(f"{what} out of signed 64-bit range: {value}")
    return value


def _quantize(raw: Decimal, unit: Decimal, mode: Rounding) -> int:
    ratio = raw / unit
    if mode is Rounding.EXACT:
        if ratio != ratio.to_integral_value():
            raise InstrumentError(f"{raw} is not an exact multiple of {unit}")
        return int(ratio)
    if mode is Rounding.DOWN:
        import math
        return math.floor(ratio)
    if mode is Rounding.UP:
        import math
        return math.ceil(ratio)
    if mode is Rounding.HALF_EVEN:
        from decimal import ROUND_HALF_EVEN
        return int(ratio.quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
    raise InstrumentError(f"unknown rounding mode: {mode}")  # pragma: no cover


def price_to_ticks(instrument: Instrument, price: str, mode: Rounding = Rounding.EXACT) -> int:
    """Convert a venue decimal price to integer ticks. ``EXACT`` is the default and fails closed."""
    return _guard_int64(_quantize(_dec(price), instrument.tick, mode), "price ticks")


def ticks_to_price(instrument: Instrument, ticks: int) -> str:
    """Convert integer ticks back to a canonical decimal price string."""
    if isinstance(ticks, bool) or not isinstance(ticks, int):
        raise InstrumentError("ticks must be an int")
    _guard_int64(ticks, "price ticks")
    return format(instrument.tick * ticks, "f")


def qty_to_steps(instrument: Instrument, qty: str, mode: Rounding = Rounding.EXACT) -> int:
    return _guard_int64(_quantize(_dec(qty), instrument.step, mode), "qty steps")


def steps_to_qty(instrument: Instrument, steps: int) -> str:
    if isinstance(steps, bool) or not isinstance(steps, int):
        raise InstrumentError("steps must be an int")
    _guard_int64(steps, "qty steps")
    return format(instrument.step * steps, "f")


# --- pure integer helpers (semantic path: ints only) ---------------------------------------------
def add_ticks(a: int, b: int) -> int:
    return _guard_int64(a + b, "tick sum")


def bps_of_ticks(price_ticks: int, bps: int) -> int:
    """Ceil( |price_ticks| * bps / 10_000 ) as integer ticks (Doc 02 §02.4 δ term).

    Integer-exact ceiling division; no floats on the semantic path.
    """
    num = abs(price_ticks) * bps
    ticks = -(-num // 10_000)  # ceil division
    return _guard_int64(ticks, "bps ticks")


def notional_quote(instrument: Instrument, price_ticks: int, qty_steps: int) -> str:
    """Quote notional as a canonical decimal string (boundary/reporting value, not semantic int)."""
    price = instrument.tick * price_ticks
    qty = instrument.step * qty_steps
    return format(price * qty, "f")
