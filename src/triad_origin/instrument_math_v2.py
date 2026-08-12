"""``instrument_math.v2`` — exact tick/step conversion (Formula Repair R-F00, Doc 02 §02.2).

Repairs the ``instrument_math.v1`` defect (see :mod:`triad_origin.instrument_math`, retired):
``v1`` compared decimal *display exponents* at the EXACT boundary, so a mathematically exact
conversion like price ``"1.0"`` with tick ``"0.10"`` quarantined even though ``1.0 / 0.10 = 10``
exactly. ``v2`` decides integrality on the *value* (Option B): the reduced exact rational
``price / tick`` is an integer iff its denominator is 1.

The repair also separates the two modes v1 conflated (Formula Repair R-F00 CORRECTED LAW):

* **INGRESS** — venue-reported facts (prices AND quantities). NEVER rounds; a non-integral venue
  fact ``QUARANTINE_NON_INTEGRAL`` and emits no atom.
* **ORDER-COMPUTE** — internally computed quantities only. Floors toward zero (PAR-008). Price
  snapping is NOT this module's job — side-specific ``FLOOR_TO_TICK``/``CEIL_TO_TICK`` live in
  F21/F22 under PAR-006/PAR-007.

Universal laws applied here (Formula Repair §1):

* §1.2 wire width — every emitted integer is re-checked signed int64; a violation is
  ``QUARANTINE_OVERFLOW``, never a wrap and never a saturation.
* §1.4 metadata — a conversion is valid only under the ``metadata_revision`` current at the event's
  availability time; a tick/step from a different revision is ``QUARANTINE_METADATA_REVISION``.
  Arithmetic across revisions is forbidden without an explicit signed rescale event.

All arithmetic is exact: a :class:`decimal.Decimal` parse of the venue string into an exact
integer ratio (``Decimal.as_integer_ratio()``), then integer cross-multiplication and ``math.gcd``
reduction — the same technique ``v1`` uses, with no ``fractions`` import and no binary ``float``
anywhere (the property/static-scan tests assert it — Formula Repair R-F00 ACCEPTANCE).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from math import gcd
import re

from .canonical import INT64_MAX, INT64_MIN, digest_fields

V2_FORMULA_ID = "instrument_math.v2"

# --- named refusal / quarantine reason codes (Formula Repair R-F00 CORRECTED LAW) ----------------
REFUSE_CONFIG = "REFUSE_CONFIG"                              # ZERO_OR_NEGATIVE_GRID etc.
QUARANTINE_NON_INTEGRAL = "QUARANTINE_NON_INTEGRAL"         # venue fact off the exact grid
QUARANTINE_OVERFLOW = "QUARANTINE_OVERFLOW"                 # result outside signed int64
QUARANTINE_METADATA_REVISION = "QUARANTINE_METADATA_REVISION"  # cross-revision conversion
REFUSE_NOT_CANONICAL = "REFUSE_NOT_CANONICAL"              # not a canonical decimal string
REFUSE_NEGATIVE_QUANTITY = "REFUSE_NEGATIVE_QUANTITY"     # a quantity is never negative

# Inline pattern string (not ``re.compile`` — the runtime forbidden-capability scanner bans the
# ``compile`` builtin; v1 uses the same inline ``re.fullmatch`` discipline).
_CANONICAL_DECIMAL = r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?"


class InstrumentV2Error(ValueError):
    """A fail-closed refusal or quarantine at the ``instrument_math.v2`` boundary.

    Carries the machine-readable ``reason`` code (one of the module constants) and a human
    ``detail`` — the caller records ``{reason, detail}`` and emits no atom, exactly as a GAP does.
    """

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class InstrumentV2:
    """Pinned instrument metadata revision for ``instrument_math.v2``.

    ``metadata_revision`` is the revision the tick/step belong to; a conversion that presents an
    event availed under a *different* revision is refused (§1.4). The grid strings are validated
    positive at construction (``REFUSE_CONFIG`` on a zero/negative grid).
    """

    canonical_instrument_id: str
    venue_model: str
    tick_size: str      # exact venue decimal string, e.g. "0.10"
    step_size: str      # exact venue decimal string, e.g. "0.001"
    min_notional: str   # exact venue decimal string, quote notional
    metadata_revision: str

    def __post_init__(self) -> None:
        for name, value in (
            ("canonical_instrument_id", self.canonical_instrument_id),
            ("venue_model", self.venue_model),
            ("metadata_revision", self.metadata_revision),
        ):
            if not isinstance(value, str) or not value:
                raise InstrumentV2Error(REFUSE_CONFIG, f"{name} must be a non-empty string")
        # §1.4 / CORRECTED LAW: REQUIRE tick > 0 and step > 0, else REFUSE_CONFIG.
        if _ratio(self.tick_size, "tick_size")[0] <= 0:
            raise InstrumentV2Error(REFUSE_CONFIG, f"ZERO_OR_NEGATIVE_GRID tick_size={self.tick_size!r}")
        if _ratio(self.step_size, "step_size")[0] <= 0:
            raise InstrumentV2Error(REFUSE_CONFIG, f"ZERO_OR_NEGATIVE_GRID step_size={self.step_size!r}")
        if _ratio(self.min_notional, "min_notional")[0] < 0:
            raise InstrumentV2Error(REFUSE_CONFIG, "min_notional must be non-negative")

    @property
    def digest(self) -> str:
        return digest_fields(
            "instrument.v2", self.canonical_instrument_id, self.venue_model, self.tick_size,
            self.step_size, self.min_notional, self.metadata_revision)


def _ratio(text: str, what: str) -> tuple[int, int]:
    """Parse a canonical decimal string to an EXACT integer ratio ``(num, den)``, ``den > 0``,
    reduced (``gcd(|num|, den) == 1``) — value, not text.

    ``Decimal(str)`` preserves the exact value and ``Decimal.as_integer_ratio()`` is exact, so no
    binary float ever enters the conversion. A non-canonical string is refused
    (``REFUSE_NOT_CANONICAL``).
    """
    if not isinstance(text, str) or not text or len(text) > 128:
        raise InstrumentV2Error(REFUSE_NOT_CANONICAL, f"{what} not a bounded string: {text!r}")
    if re.fullmatch(_CANONICAL_DECIMAL, text) is None:
        raise InstrumentV2Error(REFUSE_NOT_CANONICAL, f"{what} not canonical decimal: {text!r}")
    try:
        d = Decimal(text)
    except (InvalidOperation, ValueError) as exc:  # pragma: no cover - regex already gates this
        raise InstrumentV2Error(REFUSE_NOT_CANONICAL, f"{what} not a decimal: {text!r}") from exc
    if text.startswith("-") and d == 0:
        raise InstrumentV2Error(REFUSE_NOT_CANONICAL, f"{what} negative zero is not canonical")
    num, den = d.as_integer_ratio()  # exact; den > 0, already reduced
    return num, den


def _divide(a: tuple[int, int], b: tuple[int, int]) -> tuple[int, int]:
    """Exact rational division ``a / b`` → reduced ``(num, den)`` with ``den > 0``. Pure integer
    arithmetic (cross-multiplication); ``b`` is a positive grid so its numerator is non-zero."""
    an, ad = a
    bn, bd = b
    num = an * bd
    den = ad * bn
    if den < 0:  # keep den > 0 (b is a positive grid, so this branch is unreachable in practice)
        num, den = -num, -den
    g = gcd(abs(num), den)
    return (num // g, den // g) if g else (num, den)


def _guard_int64(value: int, reason_field: str) -> int:
    """§1.2 wire-width: a persisted/emitted integer must fit signed int64, else QUARANTINE_OVERFLOW."""
    if value < INT64_MIN or value > INT64_MAX:
        raise InstrumentV2Error(QUARANTINE_OVERFLOW, f"{reason_field} out of signed int64: {value}")
    return value


def _require_revision(instrument: InstrumentV2, event_metadata_revision: str) -> None:
    """§1.4: the tick/step revision must match the event's availability-time revision."""
    if event_metadata_revision != instrument.metadata_revision:
        raise InstrumentV2Error(
            QUARANTINE_METADATA_REVISION,
            f"event revision {event_metadata_revision!r} != instrument revision "
            f"{instrument.metadata_revision!r}",
        )


# --- INGRESS mode (venue-reported facts — NEVER rounds) ------------------------------------------
def price_to_ticks_ingress(
    instrument: InstrumentV2, price_str: str, event_metadata_revision: str
) -> int:
    """Venue price string → integer ticks. Integrality is on the VALUE (Option B): the reduced
    exact rational ``price / tick`` is an integer iff its denominator is 1. Off-grid ⇒
    ``QUARANTINE_NON_INTEGRAL``; ingress never rounds (not floor, not ceil, not side-snap)."""
    _require_revision(instrument, event_metadata_revision)
    q_num, q_den = _divide(_ratio(price_str, "price"), _ratio(instrument.tick_size, "tick_size"))
    if q_den != 1:
        raise InstrumentV2Error(
            QUARANTINE_NON_INTEGRAL,
            f"price {price_str!r} not an integral multiple of tick {instrument.tick_size!r} "
            f"(q={q_num}/{q_den})",
        )
    return _guard_int64(q_num, "price_ticks")


def qty_to_steps_ingress(
    instrument: InstrumentV2, qty_str: str, event_metadata_revision: str
) -> int:
    """Venue quantity string → integer steps, INGRESS. A non-integral venue quantity
    ``QUARANTINE_NON_INTEGRAL`` (never rounds)."""
    _require_revision(instrument, event_metadata_revision)
    q_num, q_den = _divide(_ratio(qty_str, "quantity"), _ratio(instrument.step_size, "step_size"))
    if q_den != 1:
        raise InstrumentV2Error(
            QUARANTINE_NON_INTEGRAL,
            f"quantity {qty_str!r} not an integral multiple of step {instrument.step_size!r} "
            f"(q={q_num}/{q_den})",
        )
    return _guard_int64(q_num, "qty_steps")


# --- ORDER-COMPUTE mode (internally computed quantities only — floors toward zero, PAR-008) ------
def qty_to_steps_order_compute(
    instrument: InstrumentV2, qty_str: str, event_metadata_revision: str
) -> int:
    """Internally computed quantity → integer steps, ORDER-COMPUTE. Floors toward zero (PAR-008).
    A quantity is never negative (``REFUSE_NEGATIVE_QUANTITY``), so floor == truncation here."""
    _require_revision(instrument, event_metadata_revision)
    q_num, q_den = _divide(_ratio(qty_str, "quantity"), _ratio(instrument.step_size, "step_size"))
    if q_num < 0:  # den > 0, so the sign of the ratio is the sign of the numerator
        raise InstrumentV2Error(REFUSE_NEGATIVE_QUANTITY, f"quantity {qty_str!r} is negative")
    # floor of a non-negative exact rational: numerator // denominator (denominator > 0, reduced).
    steps = q_num // q_den
    return _guard_int64(steps, "qty_steps")


# --- exact back-conversion (reporting / boundary; no float) --------------------------------------
def ticks_to_price(instrument: InstrumentV2, ticks: int) -> str:
    """Integer ticks → canonical decimal price string (exact, Decimal-free format)."""
    _guard_int64(ticks, "price_ticks")
    coefficient, exponent = _decimal_coefficient(instrument.tick_size)
    return _format_coefficient(coefficient * ticks, exponent)


def steps_to_qty(instrument: InstrumentV2, steps: int) -> str:
    """Integer steps → canonical decimal quantity string (exact, Decimal-free format)."""
    _guard_int64(steps, "qty_steps")
    coefficient, exponent = _decimal_coefficient(instrument.step_size)
    return _format_coefficient(coefficient * steps, exponent)


def conversion_identity(instrument: InstrumentV2, original_decimal_bytes: str) -> str:
    """Algorithm step 5: attach ``{instrument_id, metadata_revision, original_decimal_bytes}`` to
    the identity material (unchanged from v1's identity discipline)."""
    return digest_fields(
        "instrument_math.v2.conversion",
        instrument.canonical_instrument_id,
        instrument.metadata_revision,
        original_decimal_bytes,
    )


def _decimal_coefficient(text: str) -> tuple[int, int]:
    parts = Decimal(text).as_tuple()
    coefficient = int("".join(str(digit) for digit in parts.digits) or "0")
    exponent = int(parts.exponent)
    return (-coefficient if parts.sign else coefficient), exponent


def _format_coefficient(coefficient: int, exponent: int) -> str:
    """Format ``coefficient * 10**exponent`` exactly, independent of Decimal context."""
    sign = "-" if coefficient < 0 else ""
    digits = str(abs(coefficient))
    if exponent >= 0:
        return sign + digits + ("0" * exponent)
    scale = -exponent
    digits = digits.rjust(scale + 1, "0")
    return sign + digits[:-scale] + "." + digits[-scale:]
