"""Part A shared exact-arithmetic substrate (repair spec §1.2 / §1.3 / §1.4).

TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12 Part A primitives shared by every formula repair:

* **§1.2 wire-width and overflow law (PAR-INT-01, ``INT_WIRE_WIDTH`` = signed int64).** Every
  persisted integer field must satisfy ``-(2**63) <= x <= 2**63 - 1``. Transient comparison
  arithmetic (cross-multiplications) MAY use unbounded integers, but any value that is persisted,
  hashed into identity material, or emitted on a contract is re-checked at the boundary via
  :func:`guard_int64`. Overflow behavior is ``QUARANTINE_OVERFLOW{formula_id, field,
  value_digest}`` — never wrap, never saturate, never emit. The quarantine record carries a
  digest of the value (via :func:`triad_origin.canonical.digest_fields`), never the raw value.

* **§1.3 exact-rational storage law.** Stored ratios are reduced fractions ``(num, den)`` as
  plain int pairs with ``den > 0`` and ``gcd(|num|, den) = 1``. Reduction uses exact integer gcd
  (``math.gcd`` — the ``fractions`` module is outside the runtime import allowlist). Comparison
  ``a/b ? c/d`` is evaluated by cross-multiplication as ``a*d ? c*b``, lawful because the
  ``den > 0`` invariant fixes the sign of ``b*d``. No binary float ever touches these paths.

* **§1.4 availability and causality law.** A level, zone, or structure may be *tested* only by
  bars whose ``bucket_start_utc >= structure.availability_time`` (:func:`availability_allows`).
  Multi-transition precedence on a single event follows the global order
  ``INVALIDATED > EXPIRED > terminal > progression`` (:class:`TransitionPrecedence`).

Everything here is a pure function of its integer arguments: no clock, no I/O, no environment,
no float.
"""

from __future__ import annotations

import math
from enum import Enum

from .canonical import INT64_MAX, INT64_MIN, digest_fields

QUARANTINE_OVERFLOW = "QUARANTINE_OVERFLOW"


class ExactError(ValueError):
    """A caller violated the exact-arithmetic contract (malformed pair, zero denominator)."""


class QuarantineOverflow(ValueError):
    """§1.2 overflow quarantine: ``QUARANTINE_OVERFLOW{formula_id, field, value_digest}``.

    Raised by :func:`guard_int64` when a value crossing the persistence/emission boundary is not
    an exact signed int64. Never wrap, never saturate, never emit. The exception (and its
    :meth:`record`) carries only a digest of the offending value, never the raw value.
    """

    def __init__(self, *, formula_id: str, field: str, value_digest: str) -> None:
        super().__init__(f"{QUARANTINE_OVERFLOW}:{formula_id}:{field}:{value_digest}")
        self.formula_id = formula_id
        self.field = field
        self.value_digest = value_digest

    def record(self) -> dict:
        """The quarantine-shaped record the consuming formula journals (no atom is emitted)."""
        return {
            "event_kind": "QUARANTINE",
            "accepted": False,
            "reason_code": QUARANTINE_OVERFLOW,
            "formula_id": self.formula_id,
            "field": self.field,
            "value_digest": self.value_digest,
        }


def _overflow_value_digest(value: object) -> str:
    """A deterministic digest of the offending value — the record never carries the value.

    ``canonical.digest_fields`` itself refuses ints outside the signed int64 domain, so the value
    is framed as its decimal string (ints) / the string itself (str) / the type name (anything
    else — deterministic without relying on ``repr`` of arbitrary objects).
    """
    if isinstance(value, bool):
        return digest_fields("triad_origin.exact.int64", "bool", value)
    if isinstance(value, int):
        return digest_fields("triad_origin.exact.int64", "int", str(value))
    if isinstance(value, str):
        return digest_fields("triad_origin.exact.int64", "str", value)
    return digest_fields("triad_origin.exact.int64", "type", type(value).__name__)


def guard_int64(value: object, *, formula_id: str, field: str) -> int:
    """§1.2 boundary guard: return ``value`` iff it is an exact signed int64, else quarantine.

    An exact ``int`` (bool excluded) with ``INT64_MIN <= value <= INT64_MAX`` passes through
    unchanged. Anything else — a non-int, a bool, or an out-of-range integer — raises
    :class:`QuarantineOverflow` (fail closed at the same boundary; a value that is not even an
    exact int is just as un-emittable as one that overflows).
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise QuarantineOverflow(
            formula_id=formula_id, field=field, value_digest=_overflow_value_digest(value))
    if value < INT64_MIN or value > INT64_MAX:
        raise QuarantineOverflow(
            formula_id=formula_id, field=field, value_digest=_overflow_value_digest(value))
    return value


# ---------------------------------------------------------------------------------------------
# §1.3 exact reduced rationals as plain int pairs (num, den) with den > 0, gcd(|num|, den) = 1
# ---------------------------------------------------------------------------------------------

Rational = tuple  # (num: int, den: int) — plain pair; JSON-canonical as a two-element list.


def _exact_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ExactError(f"{name} must be an exact int, got {type(value).__name__}")
    return value


def rational(num: int, den: int) -> tuple:
    """Construct the §1.3 reduced rational pair: ``den > 0``, ``gcd(|num|, den) = 1``.

    A negative denominator is normalized by moving the sign to the numerator (the value is
    unchanged and the ``den > 0`` invariant holds). A zero denominator is refused. ``0/x``
    reduces to ``(0, 1)``.
    """
    n = _exact_int(num, "num")
    d = _exact_int(den, "den")
    if d == 0:
        raise ExactError("rational denominator must be nonzero")
    if d < 0:
        n, d = -n, -d
    g = math.gcd(abs(n), d)
    # gcd(0, d) == d, so 0/x reduces to (0, 1); g > 0 always here since d > 0.
    return (n // g, d // g)


def _pair(value: object, name: str) -> tuple:
    """Validate a rational pair for arithmetic/comparison: two exact ints, den > 0.

    Comparison lawfulness relies on the ``den > 0`` invariant (§1.3), so it is checked on every
    operand — fail closed, never assumed.
    """
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise ExactError(f"{name} must be a (num, den) pair, got {type(value).__name__}")
    n = _exact_int(value[0], f"{name}.num")
    d = _exact_int(value[1], f"{name}.den")
    if d <= 0:
        raise ExactError(f"{name}.den must be > 0 (the §1.3 invariant), got {d}")
    return (n, d)


def rational_add(a: tuple, b: tuple) -> tuple:
    """Exact ``a + b``, returned reduced."""
    an, ad = _pair(a, "a")
    bn, bd = _pair(b, "b")
    return rational(an * bd + bn * ad, ad * bd)


def rational_sub(a: tuple, b: tuple) -> tuple:
    """Exact ``a - b``, returned reduced."""
    an, ad = _pair(a, "a")
    bn, bd = _pair(b, "b")
    return rational(an * bd - bn * ad, ad * bd)


def rational_mul(a: tuple, b: tuple) -> tuple:
    """Exact ``a * b``, returned reduced."""
    an, ad = _pair(a, "a")
    bn, bd = _pair(b, "b")
    return rational(an * bn, ad * bd)


def rational_cmp(a: tuple, b: tuple) -> int:
    """Cross-multiplication comparison (§1.3): sign of ``a/b - c/d`` via ``a*d ? c*b``.

    Returns -1, 0, or +1. Lawful without division because both denominators are checked > 0.
    Transient products may exceed int64 (§1.2 permits unbounded transient comparison arithmetic).
    """
    an, ad = _pair(a, "a")
    bn, bd = _pair(b, "b")
    left = an * bd
    right = bn * ad
    if left < right:
        return -1
    if left > right:
        return 1
    return 0


def rational_eq(a: tuple, b: tuple) -> bool:
    """``a == b`` by cross-multiplication (unreduced pairs of equal value compare equal)."""
    return rational_cmp(a, b) == 0


def rational_lt(a: tuple, b: tuple) -> bool:
    """``a < b`` by cross-multiplication."""
    return rational_cmp(a, b) < 0


def rational_le(a: tuple, b: tuple) -> bool:
    """``a <= b`` by cross-multiplication."""
    return rational_cmp(a, b) <= 0


def rational_gt(a: tuple, b: tuple) -> bool:
    """``a > b`` by cross-multiplication."""
    return rational_cmp(a, b) > 0


def rational_ge(a: tuple, b: tuple) -> bool:
    """``a >= b`` by cross-multiplication."""
    return rational_cmp(a, b) >= 0


# ---------------------------------------------------------------------------------------------
# §1.4 availability / causality law
# ---------------------------------------------------------------------------------------------


def availability_allows(structure_availability_time_us: int, bar_bucket_start_us: int) -> bool:
    """§1.4: a structure may be *tested* only by bars whose bucket start is not before its
    availability time — ``bar_bucket_start_us >= structure_availability_time_us``.

    The boundary is inclusive: a bar whose bucket starts exactly at the availability instant IS
    allowed (the structure is knowable strictly before the testing bar opens). This single rule
    closes the F09 late-bar false trigger, the F13 pre-existing-level requirement, and the F14
    pre-knowledge contact defect at the data layer.
    """
    availability = _exact_int(structure_availability_time_us, "structure_availability_time_us")
    bucket_start = _exact_int(bar_bucket_start_us, "bar_bucket_start_us")
    return bucket_start >= availability


class TransitionPrecedence(Enum):
    """§1.4 global multi-transition precedence on a single event.

    ``INVALIDATED > EXPIRED > terminal (FILLED/BROKEN/CONFIRMED-terminal) > progression
    (TOUCHED/PARTIAL/…)``. Lower ``rank`` = higher precedence. Formulas instantiate their own
    transition names onto these four classes; ties INSIDE one class are each formula's declared
    rule and no formula may leave a same-event tie undefined after this repair set.
    """

    INVALIDATED = 0
    EXPIRED = 1
    TERMINAL = 2
    PROGRESSION = 3

    @property
    def rank(self) -> int:
        """The precedence rank (0 is the most dominant class)."""
        return self.value


TRANSITION_PRECEDENCE = (
    TransitionPrecedence.INVALIDATED,
    TransitionPrecedence.EXPIRED,
    TransitionPrecedence.TERMINAL,
    TransitionPrecedence.PROGRESSION,
)


def dominant_transition(classes: object) -> TransitionPrecedence:
    """The single class that wins a same-event tie under the §1.4 global order.

    ``classes`` is a non-empty iterable of :class:`TransitionPrecedence` members; anything else
    fails closed. Deterministic: the member with the lowest rank wins regardless of input order.
    """
    members = list(classes)  # type: ignore[call-overload]
    if not members:
        raise ExactError("dominant_transition requires at least one transition class")
    winner: TransitionPrecedence | None = None
    for member in members:
        if not isinstance(member, TransitionPrecedence):
            raise ExactError(
                f"dominant_transition admits only TransitionPrecedence members, "
                f"got {type(member).__name__}")
        if winner is None or member.value < winner.value:
            winner = member
    assert winner is not None  # non-empty proven above
    return winner
