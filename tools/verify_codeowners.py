#!/usr/bin/env python3
"""Fail closed unless critical CODEOWNERS resolve to a live writable GitHub identity."""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import sys

try:  # importable both as `python tools/...` and as `from tools import ...`
    from tools.github_ruleset_live import (  # type: ignore
        LiveRulesetError, fetch_codeowners_errors, fetch_repository_permission)
except ModuleNotFoundError:  # pragma: no cover - direct script fallback
    from github_ruleset_live import (  # type: ignore
        LiveRulesetError, fetch_codeowners_errors, fetch_repository_permission)

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT = ROOT / ".github" / "CODEOWNERS"
MAX_CODEOWNERS_BYTES = 3 * 1024 * 1024
KNOWN_PLACEHOLDERS = frozenset(
    value.lower()
    for value in {
        "@TriadAgentic/triad-origin-governance",
        "@TriadAgentic/origin-governance-reviewers",
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
    "/tools/github_ruleset_live.py",
    "/tools/validate_authority_root.py",
    "/tools/validate_b00r_anchor.py",
    "/tools/validate_b_receipt.py",
    "/tools/validate_governance_snapshot.py",
    "/tools/verify_historical_evidence.py",
    "/tools/verify_codeowners.py",
    "/tools/verify_source_hashes.py",
    "/src/triad_origin/",
    "/evidence/",
)
OWNER_RE = re.compile(r"@[A-Za-z0-9](?:[A-Za-z0-9-]*)(?:/[A-Za-z0-9_.-]+)?")


class CodeownersError(ValueError):
    """Critical ownership is absent, malformed, or still a known placeholder."""


def verify(path: pathlib.Path) -> tuple[int, set[str]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CodeownersError(f"CODEOWNERS_UNREADABLE: {exc}") from exc
    if len(raw) >= MAX_CODEOWNERS_BYTES:
        raise CodeownersError(f"CODEOWNERS_TOO_LARGE:{len(raw)}")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CodeownersError("CODEOWNERS_NOT_UTF8") from exc

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


def verify_provider(
    owners: set[str],
    *,
    token: str | None,
    now_us: int,
    expected_head: str,
    pr_author: str | None = None,
    opener=None,
) -> tuple[str, str]:
    """Resolve exactly one individual owner and prove write-or-higher repository access live."""
    if len(owners) != 1:
        raise CodeownersError(f"CODEOWNERS_EXACTLY_ONE_OWNER_REQUIRED:{sorted(owners)}")
    owner = next(iter(owners))
    if "/" in owner:
        raise CodeownersError(
            "CODEOWNERS_TEAM_IDENTITY_UNSUPPORTED_WITHOUT_MEMBERS_PERMISSION")
    username = owner.removeprefix("@")
    if isinstance(pr_author, str) and pr_author.strip():
        author = pr_author.strip().removeprefix("@")
        if username.lower() == author.lower():
            raise CodeownersError("CODEOWNERS_OWNER_EQUALS_PR_AUTHOR")
    kwargs = {"token": token, "now_us": now_us}
    if opener is not None:
        kwargs["opener"] = opener
    try:
        document = fetch_repository_permission(username, **kwargs)
        fetch_codeowners_errors(expected_head, **kwargs)
    except LiveRulesetError as exc:
        raise CodeownersError(f"CODEOWNERS_PROVIDER_IDENTITY_UNPROVEN:{exc}") from exc
    return username, document["permission"]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default=str(DEFAULT))
    parser.add_argument("--now-us", required=True, type=int)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument(
        "--pr-author",
        help="optional PR-author inequality check; provider review rules prove actual independence",
    )
    args = parser.parse_args(argv)
    try:
        count, owners = verify(pathlib.Path(args.file))
        username, permission = verify_provider(
            owners,
            token=os.environ.get("GITHUB_TOKEN"),
            now_us=args.now_us,
            expected_head=args.expected_head,
            pr_author=args.pr_author,
        )
    except CodeownersError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 1
    print(
        f"OK: {count} critical CODEOWNERS patterns bind live @{username} "
        f"with {permission} repository permission"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
