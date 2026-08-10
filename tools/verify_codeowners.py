#!/usr/bin/env python3
"""Fail closed when critical B00R paths have placeholder or missing CODEOWNERS identity.

This proves only that a concrete owner identity is declared in the reviewed file.  Provider-side
CODEOWNERS enforcement and reviewer independence remain separate owner/ruleset evidence gates.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT = ROOT / ".github" / "CODEOWNERS"
KNOWN_PLACEHOLDERS = frozenset(
    value.lower()
    for value in {
        "@TriadAgentic/triad-origin-governance",
        "@OWNER",
        "@UNSET",
        "@placeholder",
    }
)
CRITICAL_PATTERNS = (
    "/.github/",
    "/contracts/",
    "/docs/governance/",
    "/tools/b00r_gate.py",
    "/tools/build_evidence_manifest.py",
    "/tools/classify_milestone_pr.py",
    "/tools/e2e_audit.py",
    "/tools/validate_authority_root.py",
    "/tools/validate_b00r_anchor.py",
    "/tools/validate_b_receipt.py",
    "/tools/validate_governance_snapshot.py",
    "/tools/verify_historical_evidence.py",
    "/tools/verify_codeowners.py",
    "/tools/verify_source_hashes.py",
    "/src/triad_origin/governance.py",
    "/evidence/",
)
OWNER_RE = re.compile(r"@[A-Za-z0-9](?:[A-Za-z0-9-]*)(?:/[A-Za-z0-9_.-]+)?")


class CodeownersError(ValueError):
    """Critical ownership is absent, malformed, or still a known placeholder."""


def verify(path: pathlib.Path) -> tuple[int, set[str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CodeownersError(f"CODEOWNERS_UNREADABLE: {exc}") from exc

    mapping: dict[str, list[str]] = {}
    all_owners: set[str] = set()
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) < 2:
            raise CodeownersError(f"CODEOWNERS_OWNER_MISSING: line {lineno}")
        pattern, owners = fields[0], fields[1:]
        if any(OWNER_RE.fullmatch(owner) is None for owner in owners):
            raise CodeownersError(f"CODEOWNERS_OWNER_INVALID: line {lineno}: {owners}")
        placeholders = sorted(owner for owner in owners if owner.lower() in KNOWN_PLACEHOLDERS)
        if placeholders:
            raise CodeownersError(
                f"CODEOWNERS_PLACEHOLDER_IDENTITY: line {lineno}: {placeholders}"
            )
        mapping[pattern] = owners
        all_owners.update(owners)

    missing = [pattern for pattern in CRITICAL_PATTERNS if not mapping.get(pattern)]
    if missing:
        raise CodeownersError(f"CODEOWNERS_CRITICAL_PATTERN_MISSING: {missing}")
    if not all_owners:
        raise CodeownersError("CODEOWNERS_NO_CONCRETE_OWNER")
    return len(CRITICAL_PATTERNS), all_owners


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default=str(DEFAULT))
    args = parser.parse_args(argv)
    try:
        count, owners = verify(pathlib.Path(args.file))
    except CodeownersError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {count} critical CODEOWNERS patterns bind concrete owners {sorted(owners)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
