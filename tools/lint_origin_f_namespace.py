#!/usr/bin/env python3
"""CO-11 — the ``ORIGIN-F##`` namespace linter (TRIAD-ORIGIN-V7-CHANGE-ORDERS-2026-08-12).

Scans ``docs/plan/*.md`` in THIS repository only and flags:

  * ``BARE_F_SINGLE_DIGIT`` — a bare ``F#`` (the letter F followed by exactly one digit, no
    leading zero form) outside fenced code blocks and inline code spans. Bare ``F#`` is
    reserved for estate filter fields; an Origin formula reference must read ``ORIGIN-F##``.
  * ``MALFORMED_ORIGIN_REF`` — ``ORIGIN-F`` followed by exactly one digit (Origin references
    always carry two digits, ``ORIGIN-F00`` … ``ORIGIN-F23``).

Default mode is REPORT-ONLY (exit 0 with findings printed): the CO-11 rule ships
``PENDING-OWNER`` and pre-existing estate-filter-field rows are preserved, not silently
rewritten.  ``--enforce`` makes any finding fatal and is reserved for CI after the owner signs
``docs/plan/CO-11-ORIGIN-F-NAMESPACE-RULE.md``.

This linter reads documentation bytes only.  It certifies no gate and changes no posture.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

SCAN_GLOB = "docs/plan/*.md"

# Bare F + exactly one digit: not preceded by an identifier char or '-', not followed by an
# identifier char or another digit.  "ORIGIN-F2" is excluded here (caught as MALFORMED below).
BARE_F_RE = re.compile(r"(?<![A-Za-z0-9_\-!])F([0-9])(?![0-9A-Za-z_])")
MALFORMED_ORIGIN_RE = re.compile(r"ORIGIN-F([0-9])(?![0-9A-Za-z_])")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE_RE = re.compile(r"`[^`]*`")


class Finding:
    __slots__ = ("path", "line", "column", "kind", "token", "context")

    def __init__(self, path: str, line: int, column: int, kind: str, token: str, context: str):
        self.path = path
        self.line = line
        self.column = column
        self.kind = kind
        self.token = token
        self.context = context

    def render(self) -> str:
        return f"{self.path}:{self.line}:{self.column}: {self.kind}: {self.token!r} in: {self.context.strip()}"


def lint_text(text: str, path: str) -> list[Finding]:
    findings: list[Finding] = []
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), start=1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        # Inline code spans are data, not references; blank them preserving offsets.
        scrubbed = INLINE_CODE_RE.sub(lambda m: " " * len(m.group(0)), line)
        for match in MALFORMED_ORIGIN_RE.finditer(scrubbed):
            findings.append(
                Finding(path, lineno, match.start() + 1, "MALFORMED_ORIGIN_REF", match.group(0), line)
            )
        for match in BARE_F_RE.finditer(scrubbed):
            # Skip the tail of a malformed ORIGIN-F# (already reported above).
            prefix = scrubbed[: match.start()]
            if prefix.endswith("ORIGIN-"):
                continue
            findings.append(
                Finding(path, lineno, match.start() + 1, "BARE_F_SINGLE_DIGIT", match.group(0), line)
            )
    return findings


def lint_tree(root: pathlib.Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in sorted(root.glob(SCAN_GLOB)):
        rel = str(path.relative_to(root))
        findings.extend(lint_text(path.read_text(encoding="utf-8"), rel))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--enforce",
        action="store_true",
        help="Exit nonzero on any finding (CI mode; only after CO-11 owner ratification).",
    )
    parser.add_argument("--root", default=str(ROOT), help="Repository root (tests only).")
    args = parser.parse_args(argv)
    root = pathlib.Path(args.root)
    findings = lint_tree(root)
    for finding in findings:
        print(finding.render())
    if findings:
        mode = "ENFORCE" if args.enforce else "REPORT-ONLY"
        print(
            f"{mode}: {len(findings)} ORIGIN-F namespace finding(s) in {SCAN_GLOB}"
            " (rule: docs/plan/CO-11-ORIGIN-F-NAMESPACE-RULE.md, ratification PENDING-OWNER)"
        )
        return 1 if args.enforce else 0
    print("OK: no bare F# or malformed ORIGIN-F reference outside code in docs/plan/*.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
