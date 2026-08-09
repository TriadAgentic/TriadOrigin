"""Canonical encoding, numeric law and hashing (Doc 03 §03.4).

Canonical wire v1 is UTF-8 JSON with:
  * lexicographically sorted object keys,
  * NFC-normalized strings,
  * no duplicate keys,
  * no ``NaN``/``Infinity``,
  * no insignificant numeric alternatives (ints only; semantic price/qty are base-10 strings).

Hashing never uses raw concatenation. It uses **length-prefixed** canonical byte fields, so
``("a", "bc")`` and ``("ab", "c")`` can never collide.

This module is pure: no clock, no I/O, no randomness.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any

# 64-bit signed integer bounds — tick/step values live here and overflow is fail-closed (Doc 02).
INT64_MIN = -(2**63)
INT64_MAX = 2**63 - 1


class CanonicalError(ValueError):
    """Raised when a value violates the canonical encoding or numeric law."""


# --- string normalization ------------------------------------------------------------------------
def nfc(s: str) -> str:
    """NFC-normalize a string (idempotent)."""
    return unicodedata.normalize("NFC", s)


def _normalize(obj: Any) -> Any:
    """Recursively NFC-normalize strings and reject every floating-point value.

    Canonical wire v1 has one numeric representation: JSON integers.  Semantic decimal values are
    represented as canonical base-10 strings at the boundary.  Accepting even a finite float would
    give equivalent values such as ``1`` and ``1.0`` different bytes and therefore different IDs.
    """
    if isinstance(obj, str):
        return nfc(obj)
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        raise CanonicalError("floating-point values are not permitted on the canonical wire")
    if isinstance(obj, int):
        if obj < INT64_MIN or obj > INT64_MAX:
            raise CanonicalError("integer value out of signed 64-bit range")
        return obj
    if obj is None:
        return None
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if not isinstance(k, str):
                raise CanonicalError(f"object keys must be strings, got {type(k).__name__}")
            nk = nfc(k)
            if nk in out:
                raise CanonicalError(f"duplicate key after NFC normalization: {nk!r}")
            out[nk] = _normalize(v)
        return out
    if isinstance(obj, (list, tuple)):
        return [_normalize(v) for v in obj]
    raise CanonicalError(f"non-encodable type on canonical wire: {type(obj).__name__}")


def canonical_json(obj: Any) -> bytes:
    """Return the canonical UTF-8 JSON bytes for ``obj``.

    Keys are sorted, strings NFC-normalized, and NaN/Infinity rejected.
    """
    try:
        normalized = _normalize(obj)
        text = json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        return text.encode("utf-8")
    except CanonicalError:
        raise
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise CanonicalError("value cannot be encoded on the canonical wire") from exc


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: dict[str, Any] = {}
    for k, v in pairs:
        if k in seen:
            raise CanonicalError(f"duplicate key in decoded JSON: {k!r}")
        seen[k] = v
    return seen


def loads_canonical(data: bytes | str) -> Any:
    """Decode canonical JSON, rejecting duplicate keys and every floating-point number."""
    try:
        if isinstance(data, bytes):
            source = data
            data = data.decode("utf-8")
        elif isinstance(data, str):
            source = data.encode("utf-8")
        else:
            raise CanonicalError("canonical JSON input must be bytes or text")
        if not isinstance(data, str):
            raise CanonicalError("canonical JSON input must be bytes or text")
        value = json.loads(
            data,
            object_pairs_hook=_reject_duplicate_keys,
            parse_float=_reject_float,
            parse_int=_parse_int,
            parse_constant=_reject_const,
        )
        if canonical_json(value) != source:
            raise CanonicalError("JSON bytes are not in exact canonical form")
        return value
    except CanonicalError:
        raise
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise CanonicalError("invalid canonical JSON") from exc


def _parse_int(token: str) -> int:
    """Parse only a signed-int64 JSON integer without invoking an unbounded ``int`` conversion."""
    neg = token.startswith("-")
    body = token[1:] if neg else token
    if not body or len(body) > 19:
        raise CanonicalError("JSON integer is outside the signed 64-bit domain")
    if token == "-0":
        raise CanonicalError("negative zero is not a canonical JSON integer")
    value = int(token)
    if value < INT64_MIN or value > INT64_MAX:
        raise CanonicalError("JSON integer is outside the signed 64-bit domain")
    return value


def _reject_float(token: str) -> Any:
    raise CanonicalError(f"floating-point JSON number is not permitted: {token}")


def _reject_const(token: str) -> Any:  # pragma: no cover - defensive
    raise CanonicalError(f"non-finite JSON constant is not permitted: {token}")


# --- numeric law: signed-integer tick/step as base-10 strings ------------------------------------
def tick_to_str(value: int) -> str:
    """Encode a signed 64-bit integer tick/step value as a canonical base-10 string."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise CanonicalError("tick/step value must be a Python int")
    if value < INT64_MIN or value > INT64_MAX:
        raise CanonicalError("tick/step value out of signed 64-bit range")
    return str(value)


def str_to_tick(text: str) -> int:
    """Decode a canonical base-10 tick/step string to a Python int, fail-closed.

    Rejects leading zeros (except ``"0"``), ``"+"`` signs, whitespace and out-of-range values.
    """
    if not isinstance(text, str):
        raise CanonicalError("tick/step wire value must be a string")
    s = text
    neg = s.startswith("-")
    body = s[1:] if neg else s
    if body == "" or any(ch < "0" or ch > "9" for ch in body):
        raise CanonicalError(f"not a canonical integer string: {text!r}")
    if len(body) > 1 and body[0] == "0":
        raise CanonicalError(f"leading zero not permitted: {text!r}")
    if neg and body == "0":
        raise CanonicalError("negative zero not permitted")
    # Signed int64 has at most 19 decimal digits. Bound before int() so Python's configurable
    # large-integer parsing limit can never leak a raw ValueError at this boundary.
    if len(body) > 19:
        raise CanonicalError(f"tick/step value out of signed 64-bit range: {text!r}")
    value = int(s)
    if value < INT64_MIN or value > INT64_MAX:
        raise CanonicalError(f"tick/step value out of signed 64-bit range: {text!r}")
    return value


# --- hashing: length-prefixed field digests (raw concatenation forbidden) -------------------------
def _as_bytes(field: Any) -> bytes:
    if isinstance(field, bytes):
        return field
    if isinstance(field, str):
        return nfc(field).encode("utf-8")
    if isinstance(field, bool):
        return b"\x01" if field else b"\x00"
    if isinstance(field, int):
        if field < INT64_MIN or field > INT64_MAX:
            raise CanonicalError("digest integer field is outside the signed 64-bit domain")
        return str(field).encode("ascii")
    # Structured field -> canonical JSON bytes.
    return canonical_json(field)


def digest_fields(*fields: Any) -> str:
    """Hash an ordered tuple of fields using length-prefixed framing.

    Each field is encoded to bytes then framed as ``uint64_be(len) || bytes``. Returns lowercase
    hex SHA-256. This is the primitive behind every ORIGIN identity (Doc 03 §03.4).
    """
    h = hashlib.sha256()
    h.update(len(fields).to_bytes(8, "big"))  # arity guard
    for f in fields:
        b = _as_bytes(f)
        h.update(len(b).to_bytes(8, "big"))
        h.update(b)
    return h.hexdigest()


# --- typed identity framing v2 (CTRL-B01-003 / BLK-RC2-017) ---------------------------------------
# The v1 framing encodes only value bytes, so fields of different runtime types can collide
# (int 1 and str "1" both frame as b"1"). v2 prepends a one-byte type tag to every field frame so
# a value's runtime type is part of its identity. v1 stays valid under its own version; nothing
# rewrites an existing v1 ID.
_IDENTITY_V2_DOMAIN = b"origin.identity.v2"


def _type_tag(field: Any) -> bytes:
    if isinstance(field, bytes):
        return b"y"
    if isinstance(field, str):
        return b"s"
    if isinstance(field, bool):  # bool before int: bool subclasses int
        return b"b"
    if isinstance(field, int):
        return b"i"
    return b"j"  # structured field, canonical-JSON encoded


def digest_fields_v2(*fields: Any) -> str:
    """Typed, length-prefixed field digest (identity schema origin.identity.v2).

    Frame layout: ``domain || uint64_be(arity) || (tag || uint64_be(len) || bytes)*``.
    The tag makes runtime type part of identity, closing the v1 cross-type collision class.
    """
    h = hashlib.sha256()
    h.update(_IDENTITY_V2_DOMAIN)
    h.update(len(fields).to_bytes(8, "big"))
    for f in fields:
        b = _as_bytes(f)
        h.update(_type_tag(f))
        h.update(len(b).to_bytes(8, "big"))
        h.update(b)
    return h.hexdigest()


def sha256_hex(data: bytes) -> str:
    """Lowercase hex SHA-256 of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def canonical_digest(identity_schema_version: str, payload: Any) -> str:
    """Digest of an identity-schema version plus canonical payload bytes (Doc 03 §03.4)."""
    return digest_fields("identity_schema", identity_schema_version, canonical_json(payload))
