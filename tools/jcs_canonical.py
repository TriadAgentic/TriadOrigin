#!/usr/bin/env python3
"""RFC 8785 (JCS) canonicalizer for the closed receipt domain.

Self-contained, stdlib-only mirror of the frozen audit runner's
``strict_json_loads`` (L404-414) and ``jcs_canonical_bytes`` (L417-457) from
``audit_package/triad_origin_b01_b10_audit.py`` (TOOL_VERSION 1.2.0, SHA-256
``12c8896479b902165fa2c6d3e7565ea8402b49fcfe2d044f6fd69153926d35a2``).  The
runner is the single source of truth; byte-equality with it is asserted by the
differential test suite.

Rules (verbatim from the runner):

* Object keys are sorted by their UTF-16 (big-endian) code-unit sequence.
* Binary floating point is forbidden and raises ``ValueError``.
* Integers must satisfy ``abs(i) <= 2**53 - 1`` (exact I-JSON range).
* Strings must be valid Unicode scalar sequences (no lone surrogates) and are
  serialized with ``json.dumps(..., ensure_ascii=False)`` escaping.
* Only ``None``/``bool``/``int``/``str``/``list``/``dict`` are accepted.

CLI: ``python tools/jcs_canonical.py <file.json>`` writes the canonical bytes
to stdout (binary-safe via ``sys.stdout.buffer``).  JSON is loaded strictly:
duplicate object keys and non-finite numbers (``NaN``/``Infinity``) are
rejected.  Any error goes to stderr and exits 1.  This tool writes nothing and
imports nothing outside the Python standard library.
"""

from __future__ import annotations

import json
import sys
from typing import Any

__all__ = [
    "DuplicateJSONKey",
    "strict_json_loads",
    "jcs_canonical_bytes",
    "main",
]


class DuplicateJSONKey(ValueError):
    pass


def strict_json_loads(value: str) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise DuplicateJSONKey(f"duplicate JSON object key {key!r}")
            result[key] = item
        return result

    def reject_constant(token: str) -> Any:
        raise json.JSONDecodeError(f"non-finite JSON number {token}", value, 0)

    return json.loads(value, object_pairs_hook=reject_duplicates, parse_constant=reject_constant)


def jcs_canonical_bytes(value: Any) -> bytes:
    """RFC 8785 canonical bytes for the closed receipt domain.

    Safety-significant receipts are forbidden from using binary floating point.  Integers must be
    exactly representable by I-JSON/IEEE-754; strings must be valid Unicode scalar sequences.
    Within that closed domain this implements JCS key ordering (UTF-16 code units), escaping, and
    whitespace-free serialization without relying on a third-party package.
    """

    def render(item: Any) -> str:
        if item is None:
            return "null"
        if item is True:
            return "true"
        if item is False:
            return "false"
        if isinstance(item, int):
            if abs(item) > 2**53 - 1:
                raise ValueError("receipt JCS integer exceeds exact I-JSON range")
            return str(item)
        if isinstance(item, float):
            raise ValueError("receipt JCS domain prohibits floating-point numbers")
        if isinstance(item, str):
            try:
                item.encode("utf-8", errors="strict")
            except UnicodeEncodeError as exc:
                raise ValueError("receipt JCS string contains an invalid surrogate") from exc
            return json.dumps(item, ensure_ascii=False, separators=(",", ":"))
        if isinstance(item, list):
            return "[" + ",".join(render(child) for child in item) + "]"
        if isinstance(item, dict):
            if not all(isinstance(key, str) for key in item):
                raise ValueError("receipt JCS object keys must be strings")

            def utf16_key(key: str) -> bytes:
                try:
                    return key.encode("utf-16be", errors="strict")
                except UnicodeEncodeError as exc:
                    raise ValueError("receipt JCS key contains an invalid surrogate") from exc

            keys = sorted(item, key=utf16_key)
            return "{" + ",".join(render(key) + ":" + render(item[key]) for key in keys) + "}"
        raise ValueError(f"receipt JCS domain rejects {type(item).__name__}")

    return render(value).encode("utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python tools/jcs_canonical.py <file.json>", file=sys.stderr)
        return 1
    path = argv[0]
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
        text = raw.decode("utf-8", errors="strict")
        value = strict_json_loads(text)
        canonical = jcs_canonical_bytes(value)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"jcs_canonical: error: {exc}", file=sys.stderr)
        return 1
    sys.stdout.buffer.write(canonical)
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
