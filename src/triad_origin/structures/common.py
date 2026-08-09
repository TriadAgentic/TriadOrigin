"""Shared structure-semantics law (B03/B04 substrate).

This module is the ONE in-repo home of:

* the closed direction vocabulary and its mirror (RC3 mirror rule: C -> -C, up <-> down,
  high <-> low, bullish <-> bearish);
* exact integer helpers (``ceil_div`` — every RC3 rational parameter expression rounds up);
* the declared RC3/RC2 rational parameter expressions (PAR-036 / PAR-041 / PAR-043 / PAR-156 /
  PAR-046 / PAR-159 / PAR-158), each admitted ONLY by its exact declared-value string — a caller
  supplying any other rule is a hidden experiment and fails closed, and a caller supplying
  nothing fails closed via ``transition.require``;
* the ``NOT_RATIFIED`` sentinel + named-abstention event builder (W03/W04 failure law: a missing
  required dependency yields a NAMED abstention, never a silent null and never a fabricated
  value);
* the geometry digest helper used by structure identity (structure_atom.v2
  ``original_geometry_digest``).

Nothing here reads a clock, performs I/O, or defaults a semantic threshold.
"""

from __future__ import annotations

from .. import canonical

# ---------------------------------------------------------------------------------------------
# Directions (closed vocabulary; structure_atom.v2 enum)
# ---------------------------------------------------------------------------------------------

LONG = "LONG"
SHORT = "SHORT"
DIRECTIONS = (LONG, SHORT)


class StructureLawError(ValueError):
    """A structure-semantics law was violated (fail closed, named)."""


def opposite(direction: str) -> str:
    """The directional mirror (up <-> down)."""
    if direction == LONG:
        return SHORT
    if direction == SHORT:
        return LONG
    raise StructureLawError(f"unknown direction: {direction!r}")


def require_direction(direction: object) -> str:
    if direction not in DIRECTIONS:
        raise StructureLawError(f"direction must be one of {DIRECTIONS}: {direction!r}")
    return direction  # type: ignore[return-value]


# ---------------------------------------------------------------------------------------------
# Exact integer helpers
# ---------------------------------------------------------------------------------------------


def require_int(value: object, name: str) -> int:
    """An exact signed integer (bool excluded) — the only numeric type on the semantic path."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise StructureLawError(f"{name} must be an exact int, got {type(value).__name__}")
    return value


def ceil_div(numerator: int, denominator: int) -> int:
    """Exact ceiling division for non-negative numerators (RC3 rational expressions round up)."""
    n = require_int(numerator, "numerator")
    d = require_int(denominator, "denominator")
    if n < 0 or d <= 0:
        raise StructureLawError("ceil_div domain: numerator >= 0, denominator > 0")
    return -(-n // d)


# ---------------------------------------------------------------------------------------------
# Declared rational parameter expressions
#
# The bundle declares each of these as an exact string (``declared_value``). The machine takes
# the declared string as a required parameter and this module admits ONLY the known declared
# byte-string per parameter — the single implementation below is the RC3 formula text made
# executable. Supplying a different rule string is refused (no silently substituted semantics),
# and the ratification status of the PARAMETER is a registry/activation fact, not a code fact:
# nothing here arms anything.
# ---------------------------------------------------------------------------------------------

DECLARED_DC_REVERSAL = "max(5,ceil(ATR14_ticks*1/4))"          # PAR-036 (F03)
DECLARED_EQUAL_LEVEL_TOLERANCE = "max(2,ceil(ATR14_ticks*1/10))"  # PAR-041 (F06)
DECLARED_BOS_CLOSE_BUFFER = "max(1,ceil(ATR14_ticks*1/20))"    # PAR-043 (F09)
DECLARED_PROTECTED_SWING_TOLERANCE = "max(1,ceil(ATR14_ticks*1/20))"  # PAR-156 (F08)

_RATIONAL_RULES = {
    DECLARED_DC_REVERSAL: (5, 4),
    DECLARED_EQUAL_LEVEL_TOLERANCE: (2, 10),
    DECLARED_BOS_CLOSE_BUFFER: (1, 20),
    # PAR-156 shares the byte-string of PAR-043 — same floor/divisor by declaration.
}


def evaluate_declared_rational(declared_rule: str, atr14_ticks: int) -> int:
    """Evaluate a declared ``max(floor, ceil(ATR14_ticks/divisor))`` rule exactly.

    Only the exact declared byte-strings above are admitted; anything else fails closed. The ATR
    input must be a positive exact tick integer (a null/absent ATR is the caller's warm-up
    abstention, never a zero here).
    """
    if declared_rule not in _RATIONAL_RULES:
        raise StructureLawError(
            f"undeclared rational parameter rule: {declared_rule!r} — only the exact declared "
            "value strings are executable")
    atr = require_int(atr14_ticks, "atr14_ticks")
    if atr <= 0:
        raise StructureLawError("ATR14_ticks must be a positive integer (warm-up abstains upstream)")
    floor_ticks, divisor = _RATIONAL_RULES[declared_rule]
    return max(floor_ticks, ceil_div(atr, divisor))


# ---------------------------------------------------------------------------------------------
# Declared fixed-fraction parameter expressions (PAR-046, PAR-159 — F11)
#
# These are NOT of the ``max(floor, ceil(ATR/divisor))`` shape ``evaluate_declared_rational``
# implements: they are a plain declared fraction (a bar-range ratio) compared against a
# caller-computed numerator/denominator, with no ATR scaling at all. The same admit-only-the-
# exact-declared-byte-string discipline applies, so the (numerator, denominator) pair below is
# looked up from the declared string, never hardcoded a second time at the call site.
# ---------------------------------------------------------------------------------------------

DECLARED_DISPLACEMENT_BODY_FRACTION = "13/20"    # PAR-046 (F11)
DECLARED_DISPLACEMENT_CLOSE_LOCATION = "4/5"     # PAR-159 (F11)

_FRACTION_RULES = {
    DECLARED_DISPLACEMENT_BODY_FRACTION: (13, 20),
    DECLARED_DISPLACEMENT_CLOSE_LOCATION: (4, 5),
}


def declared_fraction(declared_rule: str) -> tuple[int, int]:
    """The exact ``(numerator, denominator)`` pair for a declared fixed-fraction rule.

    Only the exact declared byte-strings above are admitted; anything else fails closed. The
    caller cross-multiplies against this pair — never a floating division — so an equality
    boundary (PAR-009 inclusive) is decided exactly regardless of magnitude.
    """
    if declared_rule not in _FRACTION_RULES:
        raise StructureLawError(
            f"undeclared fraction parameter rule: {declared_rule!r} — only the exact declared "
            "value strings are executable")
    return _FRACTION_RULES[declared_rule]


# ---------------------------------------------------------------------------------------------
# PAR-158 DISPLACEMENT_MIN_MOVE (F11) — a dedicated function, not the shared ATR-rational table
#
# The declared expression is ``max(5, ceil(ATR14_before_origin*3/2))`` — a ``*3`` multiplier
# ahead of the ``/2`` divide that ``evaluate_declared_rational``'s ``max(floor, ceil(atr /
# divisor))`` shape cannot express (that helper has no multiplier term). Rather than force-fit
# it, this is a separate pure function; the string-gate discipline still applies — the machine
# takes the declared string as a required parameter and refuses any other value — it is simply
# enforced at the call site (the machine), not inside this function.
# ---------------------------------------------------------------------------------------------

DECLARED_DISPLACEMENT_MIN_MOVE = "max(5,ceil(ATR14_before_origin*3/2))"  # PAR-158 (F11)


def evaluate_displacement_min_move(atr14_before_origin_ticks: int) -> int:
    """``max(5, ceil(3 * ATR14_before_origin_ticks / 2))`` — the PAR-158 displacement floor.

    The ATR input must be a positive exact tick integer (a null/absent ATR is the caller's
    warm-up abstention, never a zero here — the same domain law as
    ``evaluate_declared_rational``).
    """
    atr = require_int(atr14_before_origin_ticks, "atr14_before_origin_ticks")
    if atr <= 0:
        raise StructureLawError(
            "ATR14_before_origin_ticks must be a positive integer (warm-up abstains upstream)")
    return max(5, ceil_div(3 * atr, 2))


# ---------------------------------------------------------------------------------------------
# NOT_RATIFIED sentinel + named abstention
# ---------------------------------------------------------------------------------------------

NOT_RATIFIED = "NOT_RATIFIED"


def is_ratified_int(value: object) -> bool:
    """True iff a blocking-decision parameter has been supplied as an exact non-negative int."""
    return not isinstance(value, bool) and isinstance(value, int) and value >= 0


def abstention(reason_code: str, *, formula: str, detail: str, refs: dict | None = None) -> dict:
    """A NAMED abstention event (W03/W04 failure law).

    A required dependency/parameter that is missing, unratified, or in warm-up produces one of
    these — an explicit, journalable fact — never a silent null and never a fabricated output.
    """
    if not reason_code or not reason_code.isupper():
        raise StructureLawError("abstention reason_code must be a non-empty UPPER_SNAKE token")
    event = {
        "event_kind": "NAMED_ABSTENTION",
        "reason_code": reason_code,
        "formula": formula,
        "detail": detail,
    }
    if refs:
        event["refs"] = dict(sorted(refs.items()))
    return event


# ---------------------------------------------------------------------------------------------
# Geometry digest (structure_atom.v2 original_geometry_digest)
# ---------------------------------------------------------------------------------------------


def geometry_digest(geometry: dict) -> str:
    """SHA-256 of the canonical-JSON geometry object (immutable original geometry identity)."""
    if not isinstance(geometry, dict) or not geometry:
        raise StructureLawError("geometry must be a non-empty dict")
    return canonical.sha256_hex(canonical.canonical_json(geometry))
