"""Canonical encoding, numeric law and hashing invariants (Doc 03 §03.4)."""

from __future__ import annotations

import pytest

from triad_origin import canonical as C


def test_sorted_keys_and_determinism():
    a = C.canonical_json({"b": 1, "a": 2})
    b = C.canonical_json({"a": 2, "b": 1})
    assert a == b == b'{"a":2,"b":1}'


def test_nfc_normalization_makes_equal_keys_collide():
    # "é" as U+00E9 vs "e"+U+0301 normalize to the same NFC form.
    composed = "é"
    decomposed = "é"
    assert C.nfc(composed) == C.nfc(decomposed)
    with pytest.raises(C.CanonicalError):
        C.canonical_json({composed: 1, decomposed: 2})


def test_rejects_nan_and_infinity():
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(C.CanonicalError):
            C.canonical_json({"x": bad})


def test_rejects_finite_floats_on_encode_and_decode():
    with pytest.raises(C.CanonicalError):
        C.canonical_json({"x": 1.0})
    with pytest.raises(C.CanonicalError):
        C.loads_canonical('{"x":1.0}')


def test_canonical_wire_rejects_out_of_int64_and_unbounded_integer_lexemes():
    with pytest.raises(C.CanonicalError):
        C.canonical_json({"x": C.INT64_MAX + 1})
    with pytest.raises(C.CanonicalError):
        C.canonical_json({"x": 10**5_000})
    with pytest.raises(C.CanonicalError):
        C.loads_canonical('{"x":' + ("9" * 5_000) + "}")


def test_loads_rejects_duplicate_keys():
    with pytest.raises(C.CanonicalError):
        C.loads_canonical('{"a":1,"a":2}')


@pytest.mark.parametrize("text", ['{"x":-0}', '{ "x":0}', '{"b":1,"a":2}', '"e\u0301"'])
def test_loads_rejects_noncanonical_json_bytes(text):
    with pytest.raises(C.CanonicalError):
        C.loads_canonical(text)


@pytest.mark.parametrize("value", [0, 1, -1, C.INT64_MAX, C.INT64_MIN])
def test_tick_roundtrip(value):
    assert C.str_to_tick(C.tick_to_str(value)) == value


@pytest.mark.parametrize(
    "bad",
    ["01", "+1", " 1", "1 ", "-0", "", "0x1", "1.0", "١", "１２", "²"],
)
def test_tick_rejects_noncanonical(bad):
    with pytest.raises(C.CanonicalError):
        C.str_to_tick(bad)


def test_tick_out_of_range():
    with pytest.raises(C.CanonicalError):
        C.tick_to_str(C.INT64_MAX + 1)
    with pytest.raises(C.CanonicalError):
        C.str_to_tick(str(C.INT64_MAX + 1))
    with pytest.raises(C.CanonicalError):
        C.str_to_tick("9" * 5_000)
    with pytest.raises(C.CanonicalError):
        C.tick_to_str(10**5_000)


def test_length_prefix_prevents_collision():
    # ("a","bc") and ("ab","c") must not collide under length-prefixed framing.
    assert C.digest_fields("a", "bc") != C.digest_fields("ab", "c")


def test_digest_integer_fields_obey_signed_int64_law():
    with pytest.raises(C.CanonicalError):
        C.digest_fields(C.INT64_MAX + 1)
    with pytest.raises(C.CanonicalError):
        C.digest_fields(10**5_000)


def test_digest_arity_matters():
    assert C.digest_fields("a") != C.digest_fields("a", "")


def test_canonical_digest_stable():
    d1 = C.canonical_digest("origin.identity.v1", {"z": 1, "a": 2})
    d2 = C.canonical_digest("origin.identity.v1", {"a": 2, "z": 1})
    assert d1 == d2 and len(d1) == 64
