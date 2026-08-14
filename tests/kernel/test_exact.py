"""Part A shared substrate (§1.2 int64 guard, §1.3 exact rationals, §1.4 availability +
precedence) — TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12."""

from __future__ import annotations

import pytest

from triad_origin import exact
from triad_origin.exact import (
    TRANSITION_PRECEDENCE,
    ExactError,
    QuarantineOverflow,
    TransitionPrecedence,
    availability_allows,
    dominant_transition,
    guard_int64,
    rational,
    rational_add,
    rational_cmp,
    rational_eq,
    rational_ge,
    rational_gt,
    rational_le,
    rational_lt,
    rational_mul,
    rational_sub,
)

INT64_MAX = 2**63 - 1
INT64_MIN = -(2**63)


# --- §1.2 int64 boundary guard --------------------------------------------------------------


def test_int64_boundary_max_passes_and_one_beyond_quarantines():
    assert guard_int64(INT64_MAX, formula_id="F11", field="move_ticks") == INT64_MAX
    with pytest.raises(QuarantineOverflow) as exc_info:
        guard_int64(2**63, formula_id="F11", field="move_ticks")
    exc = exc_info.value
    assert exc.formula_id == "F11"
    assert exc.field == "move_ticks"


def test_int64_boundary_min_passes_and_one_beyond_quarantines():
    assert guard_int64(INT64_MIN, formula_id="F15", field="window_sum") == INT64_MIN
    with pytest.raises(QuarantineOverflow):
        guard_int64(INT64_MIN - 1, formula_id="F15", field="window_sum")


def test_overflow_record_carries_digest_never_the_raw_value():
    offending = 2**63
    with pytest.raises(QuarantineOverflow) as exc_info:
        guard_int64(offending, formula_id="F16", field="ofi_value")
    exc = exc_info.value
    record = exc.record()
    assert record["event_kind"] == "QUARANTINE"
    assert record["accepted"] is False
    assert record["reason_code"] == "QUARANTINE_OVERFLOW"
    assert record["formula_id"] == "F16"
    assert record["field"] == "ofi_value"
    # value_digest is a 64-hex sha256, and the raw value appears NOWHERE in record or message.
    digest = record["value_digest"]
    assert isinstance(digest, str) and len(digest) == 64
    assert set(digest) <= set("0123456789abcdef")
    assert str(offending) not in str(exc)
    for value in record.values():
        assert str(offending) != value
        if isinstance(value, str):
            assert str(offending) not in value


def test_overflow_digest_is_deterministic_and_value_sensitive():
    def digest_of(value):
        with pytest.raises(QuarantineOverflow) as exc_info:
            guard_int64(value, formula_id="F00", field="price_ticks")
        return exc_info.value.value_digest

    assert digest_of(2**63) == digest_of(2**63)
    assert digest_of(2**63) != digest_of(2**63 + 1)


def test_non_int_and_bool_fail_closed_at_the_same_boundary():
    for junk in ("5", True, False, 5.0, None, [5]):
        with pytest.raises(QuarantineOverflow):
            guard_int64(junk, formula_id="F11", field="move_ticks")


# --- §1.3 exact reduced rationals ------------------------------------------------------------


def test_rational_reduces_with_positive_denominator():
    assert rational(2, 4) == (1, 2)
    assert rational(0, 7) == (0, 1)
    assert rational(6, 3) == (2, 1)
    assert rational(13, 20) == (13, 20)


def test_rational_normalizes_negative_denominator_and_negative_numerator():
    assert rational(-2, 4) == (-1, 2)
    assert rational(2, -4) == (-1, 2)
    assert rational(-2, -4) == (1, 2)


def test_rational_reduced_invariant_gcd_one_den_positive():
    num, den = rational(-84, 126)
    assert den > 0
    import math

    assert math.gcd(abs(num), den) == 1
    assert (num, den) == (-2, 3)


def test_rational_zero_denominator_refused():
    with pytest.raises(ExactError):
        rational(1, 0)


def test_rational_non_int_inputs_refused():
    with pytest.raises(ExactError):
        rational(1.0, 2)  # type: ignore[arg-type]
    with pytest.raises(ExactError):
        rational(1, True)  # type: ignore[arg-type]


def test_rational_arithmetic_is_exact_and_reduced():
    assert rational_add((1, 2), (1, 3)) == (5, 6)
    assert rational_sub((1, 2), (1, 3)) == (1, 6)
    assert rational_mul((2, 3), (3, 4)) == (1, 2)
    assert rational_add((1, 2), (-1, 2)) == (0, 1)
    assert rational_sub((-1, 3), (1, 6)) == (-1, 2)


def test_cross_multiplication_comparisons_including_negative_numerators():
    assert rational_lt((-1, 2), (1, 3))
    assert rational_gt((-1, 3), (-1, 2))
    assert rational_le((-1, 2), (-1, 2))
    assert rational_ge((3, 4), (2, 3))
    assert rational_cmp((-5, 7), (-5, 7)) == 0
    assert rational_cmp((-5, 7), (-4, 7)) == -1
    assert rational_cmp((-4, 7), (-5, 7)) == 1


def test_comparison_admits_unreduced_pairs_by_value():
    assert rational_eq((2, 4), (1, 2))
    assert rational_eq((-2, 4), (-1, 2))
    assert not rational_eq((2, 4), (3, 4))


def test_comparison_refuses_nonpositive_denominator_fail_closed():
    with pytest.raises(ExactError):
        rational_cmp((1, -2), (1, 2))
    with pytest.raises(ExactError):
        rational_cmp((1, 2), (1, 0))
    with pytest.raises(ExactError):
        rational_lt((1, 2), (1, 2, 3))  # type: ignore[arg-type]


def test_cross_multiplication_holds_where_float_division_misrounds():
    # a = (10^18 + 1)/10^18 and b = 10^18/(10^18 - 1): float sees both as 1.0 + ~1e-18 == 1.0,
    # exact cross-multiplication proves a < b because (10^18+1)(10^18-1) = 10^36 - 1 < 10^36.
    a = (10**18 + 1, 10**18)
    b = (10**18, 10**18 - 1)
    assert rational_lt(a, b)
    assert rational_gt(b, a)
    assert not rational_eq(a, b)


def test_transient_cross_multiplication_may_exceed_int64():
    # §1.2: transient comparison arithmetic MAY use unbounded integers.
    big = (INT64_MAX, INT64_MAX - 1)
    bigger = (INT64_MAX, INT64_MAX - 2)
    assert rational_lt(big, bigger)


# --- §1.4 availability law -------------------------------------------------------------------


def test_availability_boundary_equal_is_allowed_inclusive():
    # bucket_start == availability_time is ALLOWED — the '>=' law.
    assert availability_allows(1_000_000, 1_000_000) is True


def test_availability_after_is_allowed_and_before_is_refused():
    assert availability_allows(1_000_000, 1_000_001) is True
    assert availability_allows(1_000_000, 999_999) is False


def test_availability_requires_exact_ints():
    with pytest.raises(ExactError):
        availability_allows(1.0, 1)  # type: ignore[arg-type]
    with pytest.raises(ExactError):
        availability_allows(1, True)  # type: ignore[arg-type]


# --- §1.4 global transition precedence -------------------------------------------------------


def test_precedence_order_is_invalidated_expired_terminal_progression():
    assert TRANSITION_PRECEDENCE == (
        TransitionPrecedence.INVALIDATED,
        TransitionPrecedence.EXPIRED,
        TransitionPrecedence.TERMINAL,
        TransitionPrecedence.PROGRESSION,
    )
    ranks = [member.rank for member in TRANSITION_PRECEDENCE]
    assert ranks == sorted(ranks) == [0, 1, 2, 3]


def test_dominant_transition_picks_the_global_winner_regardless_of_input_order():
    assert dominant_transition(
        [TransitionPrecedence.PROGRESSION, TransitionPrecedence.INVALIDATED,
         TransitionPrecedence.TERMINAL]
    ) is TransitionPrecedence.INVALIDATED
    assert dominant_transition(
        [TransitionPrecedence.PROGRESSION, TransitionPrecedence.TERMINAL,
         TransitionPrecedence.EXPIRED]
    ) is TransitionPrecedence.EXPIRED
    assert dominant_transition(
        [TransitionPrecedence.PROGRESSION, TransitionPrecedence.TERMINAL]
    ) is TransitionPrecedence.TERMINAL
    assert dominant_transition(
        [TransitionPrecedence.PROGRESSION]
    ) is TransitionPrecedence.PROGRESSION


def test_dominant_transition_fails_closed_on_empty_or_foreign_members():
    with pytest.raises(ExactError):
        dominant_transition([])
    with pytest.raises(ExactError):
        dominant_transition(["INVALIDATED"])  # a bare string is not a member


def test_module_uses_no_float_and_no_division_on_semantic_paths():
    # House discipline (the displacement AST-test sibling): no float literals and no TRUE
    # division anywhere in the module — comparisons are cross-multiplied; the only division
    # is exact floor division by the gcd inside rational reduction (remainder provably 0).
    import ast
    import pathlib

    source = pathlib.Path(exact.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        assert not isinstance(node, ast.Div), "true division found in exact.py"
        if isinstance(node, ast.Constant):
            assert not isinstance(node.value, float), "float literal found in exact.py"
