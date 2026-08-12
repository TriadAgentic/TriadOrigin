#!/usr/bin/env python3
"""Validate the G2 tag-ruleset capture on a receipt-PR head before merge or tagging.

This gate deliberately proves only facts that can exist on the reviewed receipt PR head: the
canonical provider capture is committed at the exact clean head, externally SHA-256 pinned,
provider-shaped, active, immutable, and effective before a trusted current time.  In strict-live
mode it also re-fetches the ruleset from its fixed GitHub API endpoint.  It never claims terminal
B00R closure; ``validate_b00r_anchor.py`` separately requires the reviewed receipt merge and the
live annotated anchor tag.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:  # importable both as `python tools/...` and as `from tools import ...`
    from tools.github_ruleset_live import (  # type: ignore
        LiveRulesetError, LiveRulesetUnavailable, fetch_and_match_live_ruleset)
    from tools.validate_b00r_anchor import (  # type: ignore
        AnchorError, DEFAULT_RULESET, HEX40_RE, HEX64_RE, PIN_ENV, ROOT,
        _canonical_file, _git, _loads_unique_object, _resolve_ruleset_pin,
        _receipt_observation_window, _ruleset_time_us, _validate_ruleset)
except ModuleNotFoundError:  # pragma: no cover - direct script fallback
    from github_ruleset_live import (  # type: ignore
        LiveRulesetError, LiveRulesetUnavailable, fetch_and_match_live_ruleset)
    from validate_b00r_anchor import (  # type: ignore
        AnchorError, DEFAULT_RULESET, HEX40_RE, HEX64_RE, PIN_ENV, ROOT,
        _canonical_file, _git, _loads_unique_object, _resolve_ruleset_pin,
        _receipt_observation_window, _ruleset_time_us, _validate_ruleset)


def verify(
    *,
    root: pathlib.Path,
    expected_head: str,
    ruleset_path: pathlib.Path,
    ruleset_pin: str | None,
    now_us: int,
    github_token: str | None = None,
    strict_live: bool = False,
    require_bypass_visibility: bool = False,
    receipt_path: pathlib.Path | None = None,
) -> str:
    """Return the bound SHA-256 after pre-anchor validation succeeds."""
    root = root.resolve()
    if (HEX40_RE.fullmatch(expected_head or "") is None
            or expected_head == "0" * 40):
        raise AnchorError(
            f"FAIL: EXPECTED_HEAD_NOT_CANONICAL_HEX40: {expected_head!r}"
        )
    if not isinstance(now_us, int) or isinstance(now_us, bool) or now_us <= 0:
        raise AnchorError("FAIL: NOW_US_INVALID")
    if require_bypass_visibility and not strict_live:
        raise AnchorError("FAIL: BYPASS_VISIBILITY_REQUIRES_STRICT_LIVE")
    if require_bypass_visibility and receipt_path is None:
        raise AnchorError("FAIL: PRIVILEGED_PREMERGE_RECEIPT_ABSENT")
    actual_head = _git(root, "rev-parse", "HEAD").decode().strip()
    if actual_head != expected_head:
        raise AnchorError(f"FAIL: EXPECTED_HEAD_MISMATCH: {actual_head}!={expected_head}")
    if _git(root, "status", "--porcelain=v1", "--untracked-files=all").strip():
        raise AnchorError("FAIL: GIT_WORKTREE_NOT_CLEAN")

    ruleset_path = _canonical_file(root, ruleset_path, DEFAULT_RULESET, "TAG_RULESET")
    _git(root, "ls-files", "--error-unmatch", "--", DEFAULT_RULESET)
    committed_blob = _git(root, "rev-parse", f"{expected_head}:{DEFAULT_RULESET}").decode().strip()
    if _git(root, "cat-file", "-t", committed_blob).decode().strip() != "blob":
        raise AnchorError("FAIL: TAG_RULESET_COMMITTED_OBJECT_NOT_BLOB")
    worktree_blob = _git(
        root, "hash-object", "--no-filters", "--", DEFAULT_RULESET
    ).decode().strip()
    if worktree_blob != committed_blob:
        raise AnchorError("FAIL: TAG_RULESET_WORKTREE_BLOB_DIFFERS_FROM_EXPECTED_HEAD")
    ruleset_bytes = ruleset_path.read_bytes()
    if _git(root, "show", f"{expected_head}:{DEFAULT_RULESET}") != ruleset_bytes:
        raise AnchorError("FAIL: TAG_RULESET_WORKTREE_DIFFERS_FROM_EXPECTED_HEAD")

    if ruleset_pin is None or ruleset_pin == "":
        raise AnchorError(f"BLOCKED: EXTERNAL_TAG_RULESET_PIN_ABSENT: {PIN_ENV}")
    if HEX64_RE.fullmatch(ruleset_pin) is None or ruleset_pin == "0" * 64:
        raise AnchorError(f"FAIL: EXTERNAL_TAG_RULESET_PIN_INVALID: {ruleset_pin!r}")
    digest = hashlib.sha256(ruleset_bytes).hexdigest()
    if digest != ruleset_pin:
        raise AnchorError("FAIL: TAG_RULESET_EXTERNAL_PIN_MISMATCH")

    ruleset = _loads_unique_object(ruleset_bytes)
    _validate_ruleset(ruleset)
    created_at_us = _ruleset_time_us(ruleset.get("created_at"), "created_at")
    updated_at_us = _ruleset_time_us(ruleset.get("updated_at"), "updated_at")
    if not created_at_us <= updated_at_us < now_us:
        raise AnchorError("FAIL: TAG_RULESET_NOT_EFFECTIVE_BEFORE_TRUSTED_NOW")

    if receipt_path is not None:
        receipt_path = _canonical_file(
            root, receipt_path,
            "evidence/receipts/B00R.g2.receipt.v3.json", "RECEIPT")
        receipt_rel = "evidence/receipts/B00R.g2.receipt.v3.json"
        _git(root, "ls-files", "--error-unmatch", "--", receipt_rel)
        receipt_bytes = receipt_path.read_bytes()
        if _git(root, "show", f"{expected_head}:{receipt_rel}") != receipt_bytes:
            raise AnchorError("FAIL: RECEIPT_WORKTREE_DIFFERS_FROM_EXPECTED_HEAD")
        observed_at_us, emitted_at_us = _receipt_observation_window(
            _loads_unique_object(receipt_bytes))
        if not updated_at_us < observed_at_us <= emitted_at_us <= now_us:
            raise AnchorError(
                "FAIL: TAG_RULESET_NOT_EFFECTIVE_BEFORE_RECEIPT_OBSERVATION")

    if strict_live:
        fetch_and_match_live_ruleset(
            ruleset_bytes,
            token=github_token,
            now_us=now_us,
            require_bypass_visibility=require_bypass_visibility,
        )
    return digest


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--now-us", required=True, type=int)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--ruleset", default=DEFAULT_RULESET)
    parser.add_argument("--ruleset-pin")
    parser.add_argument("--receipt")
    parser.add_argument("--strict-live", action="store_true")
    parser.add_argument(
        "--require-bypass-visibility", action="store_true",
        help="privileged premerge mode: provider must expose an empty bypass_actors field")
    args = parser.parse_args(argv)
    root = pathlib.Path(args.root).resolve()
    ruleset = pathlib.Path(args.ruleset)
    if not ruleset.is_absolute():
        ruleset = root / ruleset
    receipt = pathlib.Path(args.receipt) if args.receipt else None
    if receipt is not None and not receipt.is_absolute():
        receipt = root / receipt
    try:
        pin = _resolve_ruleset_pin(args.ruleset_pin, os.environ.get(PIN_ENV))
        digest = verify(
            root=root,
            expected_head=args.expected_head,
            ruleset_path=ruleset,
            ruleset_pin=pin,
            now_us=args.now_us,
            github_token=os.environ.get("GITHUB_TOKEN"),
            strict_live=args.strict_live,
            require_bypass_visibility=args.require_bypass_visibility,
            receipt_path=receipt,
        )
    except LiveRulesetUnavailable as exc:
        print(f"BLOCKED: LIVE_TAG_PROVIDER_UNAVAILABLE:{exc}")
        return 1
    except LiveRulesetError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (AnchorError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    mode = "strict-live" if args.strict_live else "static"
    print(
        f"OK: pre-anchor G2 tag ruleset {digest} is bound to {args.expected_head} ({mode})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
