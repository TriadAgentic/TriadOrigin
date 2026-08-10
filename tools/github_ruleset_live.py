#!/usr/bin/env python3
"""Fail-closed live GitHub ruleset origin and freshness verification.

Committed provider bytes and an external digest pin prove immutability, not provenance.  Terminal
B00R gates therefore re-fetch the exact ruleset over GitHub's authenticated HTTPS API and require
semantic equality with the committed provider object immediately before accepting it.
"""

from __future__ import annotations

import json
from typing import Callable
import urllib.error
import urllib.request

REPOSITORY = "TriadAgentic/TriadOrigin"
API_VERSION = "2022-11-28"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
DEFAULT_TIMEOUT_S = 20.0


class LiveRulesetError(ValueError):
    """A live provider object is unavailable, malformed, redirected, or stale."""


def _loads_unique_object(data: bytes, label: str) -> dict:
    def unique_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise LiveRulesetError(f"{label}_DUPLICATE_KEY:{key}")
            value[key] = item
        return value

    try:
        value = json.loads(data, object_pairs_hook=unique_object)
    except LiveRulesetError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise LiveRulesetError(f"{label}_NOT_JSON:{exc}") from exc
    if not isinstance(value, dict):
        raise LiveRulesetError(f"{label}_NOT_OBJECT")
    return value


def _positive_ruleset_id(doc: dict) -> int:
    ruleset_id = doc.get("id")
    if not isinstance(ruleset_id, int) or isinstance(ruleset_id, bool) or ruleset_id <= 0:
        raise LiveRulesetError("COMMITTED_RULESET_ID_NOT_POSITIVE_INTEGER")
    return ruleset_id


def ruleset_url(ruleset_id: int) -> str:
    if not isinstance(ruleset_id, int) or isinstance(ruleset_id, bool) or ruleset_id <= 0:
        raise LiveRulesetError("RULESET_ID_NOT_POSITIVE_INTEGER")
    return f"https://api.github.com/repos/{REPOSITORY}/rulesets/{ruleset_id}"


def fetch_and_match_live_ruleset(
    committed_raw: bytes,
    *,
    token: str | None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> dict:
    """Return the live object only when authenticated GitHub bytes match committed semantics."""

    committed = _loads_unique_object(committed_raw, "COMMITTED_RULESET")
    ruleset_id = _positive_ruleset_id(committed)
    if not isinstance(token, str) or not token.strip():
        raise LiveRulesetError("GITHUB_TOKEN_ABSENT")
    if not isinstance(timeout_s, (int, float)) or isinstance(timeout_s, bool) or timeout_s <= 0:
        raise LiveRulesetError("LIVE_RULESET_TIMEOUT_INVALID")

    expected_url = ruleset_url(ruleset_id)
    request = urllib.request.Request(
        expected_url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "TriadOrigin-B00R-live-ruleset-verifier",
            "X-GitHub-Api-Version": API_VERSION,
        },
        method="GET",
    )
    try:
        response = opener(request, timeout=float(timeout_s))
        with response:
            status = getattr(response, "status", response.getcode())
            final_url = response.geturl()
            live_raw = response.read(MAX_RESPONSE_BYTES + 1)
    except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        raise LiveRulesetError(f"LIVE_RULESET_FETCH_FAILED:{type(exc).__name__}") from exc

    if status != 200:
        raise LiveRulesetError(f"LIVE_RULESET_HTTP_STATUS:{status}")
    if final_url != expected_url:
        raise LiveRulesetError(f"LIVE_RULESET_UNEXPECTED_FINAL_URL:{final_url!r}")
    if len(live_raw) > MAX_RESPONSE_BYTES:
        raise LiveRulesetError("LIVE_RULESET_RESPONSE_TOO_LARGE")

    live = _loads_unique_object(live_raw, "LIVE_RULESET")
    if _positive_ruleset_id(live) != ruleset_id:
        raise LiveRulesetError("LIVE_RULESET_ID_MISMATCH")
    if live != committed:
        raise LiveRulesetError("LIVE_RULESET_DIFFERS_FROM_COMMITTED_CAPTURE")
    return live
