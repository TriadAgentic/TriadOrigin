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
    normalized = _normalize(obj)
    text = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return text.encode("utf-8")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: dict[str, Any] = {}
    for k, v in pairs:
        if k in seen:
            raise CanonicalError(f"duplicate key in decoded JSON: {k!r}")
        seen[k] = v
    return seen


def loads_canonical(data: bytes | str) -> Any:
    """Decode canonical JSON, rejecting duplicate keys and every floating-point number."""
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    return json.loads(
        data,
        object_pairs_hook=_reject_duplicate_keys,
        parse_float=_reject_float,
        parse_constant=_reject_const,
    )


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
        raise CanonicalError(f"tick/step value out of signed 64-bit range: {value}")
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


def sha256_hex(data: bytes) -> str:
    """Lowercase hex SHA-256 of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def canonical_digest(identity_schema_version: str, payload: Any) -> str:
    """Digest of an identity-schema version plus canonical payload bytes (Doc 03 §03.4)."""
    return digest_fields("identity_schema", identity_schema_version, canonical_json(payload))
