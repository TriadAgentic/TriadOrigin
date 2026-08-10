#!/usr/bin/env python3
"""Fail-closed live GitHub ruleset origin and freshness verification.

A committed capture plus an external digest proves byte immutability, not provider provenance.
Terminal B00R gates therefore re-fetch the fixed repository/ruleset endpoint over authenticated TLS
and compare every security-relevant provider field in memory.  No URL, response file, or token is
accepted from an argument.
"""

from __future__ import annotations

from dataclasses import dataclass
from email.utils import parsedate_to_datetime
import json
from typing import Callable
import urllib.error
import urllib.request

REPOSITORY = "TriadAgentic/TriadOrigin"
API_VERSION = "2022-11-28"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
DEFAULT_TIMEOUT_S = 20.0
MAX_DATE_AGE_US = 5 * 60 * 1_000_000
MAX_DATE_FUTURE_US = 60 * 1_000_000
SECURITY_FIELDS = (
    "id", "name", "target", "source_type", "source", "enforcement", "conditions", "rules",
    "node_id", "_links", "created_at", "updated_at",
)


class LiveRulesetError(ValueError):
    """Base live-provider error."""


class LiveRulesetUnavailable(LiveRulesetError):
    """The fixed GitHub endpoint could not be authenticated or reached."""


class LiveRulesetMismatch(LiveRulesetError):
    """The live response is malformed, stale, redirected, or differs from the capture."""


@dataclass(frozen=True)
class LiveRuleset:
    document: dict
    bypass_visible: bool
    request_id: str
    provider_date_us: int


def _loads_unique_object(data: bytes, label: str) -> dict:
    def unique_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise LiveRulesetMismatch(f"{label}_DUPLICATE_KEY:{key}")
            value[key] = item
        return value

    try:
        value = json.loads(data, object_pairs_hook=unique_object)
    except LiveRulesetMismatch:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise LiveRulesetMismatch(f"{label}_NOT_JSON:{exc}") from exc
    if not isinstance(value, dict):
        raise LiveRulesetMismatch(f"{label}_NOT_OBJECT")
    return value


def _positive_ruleset_id(doc: dict, label: str) -> int:
    ruleset_id = doc.get("id")
    if not isinstance(ruleset_id, int) or isinstance(ruleset_id, bool) or ruleset_id <= 0:
        raise LiveRulesetMismatch(f"{label}_ID_NOT_POSITIVE_INTEGER")
    return ruleset_id


def ruleset_url(ruleset_id: int) -> str:
    if not isinstance(ruleset_id, int) or isinstance(ruleset_id, bool) or ruleset_id <= 0:
        raise LiveRulesetMismatch("RULESET_ID_NOT_POSITIVE_INTEGER")
    return (
        f"https://api.github.com/repos/{REPOSITORY}/rulesets/{ruleset_id}"
        "?includes_parents=false"
    )


def _header(headers: object, name: str) -> str:
    getter = getattr(headers, "get", None)
    if not callable(getter):
        return ""
    value = getter(name, "")
    return value if isinstance(value, str) else ""


def _provider_date_us(value: str, now_us: int) -> int:
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            raise ValueError("timezone absent")
        observed_us = int(parsed.timestamp() * 1_000_000)
    except (OverflowError, TypeError, ValueError) as exc:
        raise LiveRulesetMismatch("LIVE_RULESET_DATE_HEADER_INVALID") from exc
    if observed_us > now_us + MAX_DATE_FUTURE_US:
        raise LiveRulesetMismatch("LIVE_RULESET_DATE_IN_FUTURE")
    if observed_us < now_us - MAX_DATE_AGE_US:
        raise LiveRulesetMismatch("LIVE_RULESET_DATE_STALE")
    return observed_us


def fetch_and_match_live_ruleset(
    committed_raw: bytes,
    *,
    token: str | None,
    now_us: int,
    require_bypass_visibility: bool = False,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> LiveRuleset:
    """Fetch the fixed endpoint and require a fresh, security-equivalent provider object."""

    committed = _loads_unique_object(committed_raw, "COMMITTED_RULESET")
    ruleset_id = _positive_ruleset_id(committed, "COMMITTED_RULESET")
    if not isinstance(token, str) or not token.strip():
        raise LiveRulesetUnavailable("GITHUB_TOKEN_ABSENT")
    if not isinstance(now_us, int) or isinstance(now_us, bool) or now_us <= 0:
        raise LiveRulesetMismatch("LIVE_RULESET_NOW_US_INVALID")
    if not isinstance(timeout_s, (int, float)) or isinstance(timeout_s, bool) or timeout_s <= 0:
        raise LiveRulesetMismatch("LIVE_RULESET_TIMEOUT_INVALID")

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
            headers = response.headers
            live_raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403, 429} or 500 <= exc.code <= 599:
            raise LiveRulesetUnavailable(f"LIVE_RULESET_HTTP_STATUS:{exc.code}") from exc
        raise LiveRulesetMismatch(f"LIVE_RULESET_HTTP_STATUS:{exc.code}") from exc
    except (OSError, urllib.error.URLError) as exc:
        raise LiveRulesetUnavailable(
            f"LIVE_RULESET_FETCH_FAILED:{type(exc).__name__}") from exc

    if status != 200:
        error = f"LIVE_RULESET_HTTP_STATUS:{status}"
        if status in {401, 403, 429} or 500 <= status <= 599:
            raise LiveRulesetUnavailable(error)
        raise LiveRulesetMismatch(error)
    if final_url != expected_url:
        raise LiveRulesetMismatch(f"LIVE_RULESET_UNEXPECTED_FINAL_URL:{final_url!r}")
    if len(live_raw) > MAX_RESPONSE_BYTES:
        raise LiveRulesetMismatch("LIVE_RULESET_RESPONSE_TOO_LARGE")
    content_type = _header(headers, "Content-Type").split(";", 1)[0].strip().lower()
    if content_type not in {"application/json", "application/vnd.github+json"}:
        raise LiveRulesetMismatch(f"LIVE_RULESET_CONTENT_TYPE_INVALID:{content_type!r}")
    request_id = _header(headers, "X-GitHub-Request-Id").strip()
    if not request_id:
        raise LiveRulesetMismatch("LIVE_RULESET_REQUEST_ID_ABSENT")
    provider_date_us = _provider_date_us(_header(headers, "Date"), now_us)

    live = _loads_unique_object(live_raw, "LIVE_RULESET")
    if _positive_ruleset_id(live, "LIVE_RULESET") != ruleset_id:
        raise LiveRulesetMismatch("LIVE_RULESET_ID_MISMATCH")
    for field in SECURITY_FIELDS:
        if live.get(field) != committed.get(field):
            raise LiveRulesetMismatch(f"LIVE_RULESET_SECURITY_FIELD_MISMATCH:{field}")
    if committed.get("current_user_can_bypass") != "never" \
            or live.get("current_user_can_bypass") != "never":
        raise LiveRulesetMismatch("LIVE_RULESET_CURRENT_USER_BYPASS_NOT_NEVER")
    if committed.get("bypass_actors") != []:
        raise LiveRulesetMismatch("COMMITTED_RULESET_BYPASS_NOT_EMPTY")
    bypass_visible = "bypass_actors" in live
    if bypass_visible and live.get("bypass_actors") != []:
        raise LiveRulesetMismatch("LIVE_RULESET_BYPASS_NOT_EMPTY")
    if require_bypass_visibility and not bypass_visible:
        raise LiveRulesetMismatch("LIVE_RULESET_BYPASS_VISIBILITY_REQUIRED")
    return LiveRuleset(
        document=live,
        bypass_visible=bypass_visible,
        request_id=request_id,
        provider_date_us=provider_date_us,
    )
