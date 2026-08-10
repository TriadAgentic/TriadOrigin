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
import re
from typing import Callable
import urllib.error
import urllib.request

REPOSITORY = "TriadAgentic/TriadOrigin"
API_VERSION = "2022-11-28"
RULE_SUITE_API_VERSION = "2026-03-10"
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


def collaborator_permission_url(username: str) -> str:
    if (not isinstance(username, str)
            or re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", username)
            is None):
        raise LiveRulesetMismatch("COLLABORATOR_USERNAME_INVALID")
    return (
        f"https://api.github.com/repos/{REPOSITORY}/collaborators/{username}/permission"
    )


def rule_suite_url(rule_suite_id: int) -> str:
    if (not isinstance(rule_suite_id, int) or isinstance(rule_suite_id, bool)
            or rule_suite_id <= 0):
        raise LiveRulesetMismatch("RULE_SUITE_ID_NOT_POSITIVE_INTEGER")
    return (
        f"https://api.github.com/repos/{REPOSITORY}/rulesets/rule-suites/{rule_suite_id}"
    )


def canary_ref_url() -> str:
    return (
        f"https://api.github.com/repos/{REPOSITORY}/git/ref/heads/b00r-ruleset-canary"
    )


def anchor_tag_ref_url() -> str:
    return (
        f"https://api.github.com/repos/{REPOSITORY}/git/ref/tags/B00R_RECEIPT_ANCHOR"
    )


def codeowners_errors_url(expected_head: str) -> str:
    if not isinstance(expected_head, str) or re.fullmatch(r"[0-9a-f]{40}", expected_head) is None:
        raise LiveRulesetMismatch("CODEOWNERS_EXPECTED_HEAD_INVALID")
    return (
        f"https://api.github.com/repos/{REPOSITORY}/codeowners/errors?ref={expected_head}"
    )


def pull_request_url(number: int) -> str:
    if not isinstance(number, int) or isinstance(number, bool) or number <= 0:
        raise LiveRulesetMismatch("PULL_REQUEST_NUMBER_INVALID")
    return f"https://api.github.com/repos/{REPOSITORY}/pulls/{number}"


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


def _require_uncached_response(headers: object) -> None:
    age = _header(headers, "Age").strip()
    if not age:
        return
    if not age.isascii() or not age.isdigit():
        raise LiveRulesetMismatch("LIVE_RULESET_CACHE_AGE_INVALID")
    if int(age) != 0:
        raise LiveRulesetMismatch(f"LIVE_RULESET_CACHE_AGE_NOT_ZERO:{age}")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


_DIRECT_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    _NoRedirect(),
)


def _direct_urlopen(request, *, timeout: float):
    return _DIRECT_OPENER.open(request, timeout=timeout)


def _fetch_fixed_json(
    expected_url: str,
    *,
    token: str | None,
    now_us: int,
    api_version: str,
    user_agent: str,
    label: str,
    timeout_s: float,
    opener: Callable[..., object],
) -> dict:
    if not isinstance(token, str) or not token.strip():
        raise LiveRulesetUnavailable("GITHUB_TOKEN_ABSENT")
    if not isinstance(now_us, int) or isinstance(now_us, bool) or now_us <= 0:
        raise LiveRulesetMismatch(f"{label}_NOW_US_INVALID")
    if not isinstance(timeout_s, (int, float)) or isinstance(timeout_s, bool) or timeout_s <= 0:
        raise LiveRulesetMismatch(f"{label}_TIMEOUT_INVALID")
    request = urllib.request.Request(
        expected_url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "User-Agent": user_agent,
            "X-GitHub-Api-Version": api_version,
        },
        method="GET",
    )
    try:
        response = opener(request, timeout=float(timeout_s))
        with response:
            status = getattr(response, "status", response.getcode())
            final_url = response.geturl()
            headers = response.headers
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403, 429} or 500 <= exc.code <= 599:
            raise LiveRulesetUnavailable(f"{label}_HTTP_STATUS:{exc.code}") from exc
        raise LiveRulesetMismatch(f"{label}_HTTP_STATUS:{exc.code}") from exc
    except (OSError, urllib.error.URLError) as exc:
        raise LiveRulesetUnavailable(f"{label}_FETCH_FAILED:{type(exc).__name__}") from exc
    if status != 200:
        error = f"{label}_HTTP_STATUS:{status}"
        if status in {401, 403, 429} or 500 <= status <= 599:
            raise LiveRulesetUnavailable(error)
        raise LiveRulesetMismatch(error)
    if final_url != expected_url:
        raise LiveRulesetMismatch(f"{label}_UNEXPECTED_FINAL_URL:{final_url!r}")
    if len(raw) > MAX_RESPONSE_BYTES:
        raise LiveRulesetMismatch(f"{label}_RESPONSE_TOO_LARGE")
    content_type = _header(headers, "Content-Type").split(";", 1)[0].strip().lower()
    if content_type not in {"application/json", "application/vnd.github+json"}:
        raise LiveRulesetMismatch(f"{label}_CONTENT_TYPE_INVALID:{content_type!r}")
    if not _header(headers, "X-GitHub-Request-Id").strip():
        raise LiveRulesetMismatch(f"{label}_REQUEST_ID_ABSENT")
    _require_uncached_response(headers)
    _provider_date_us(_header(headers, "Date"), now_us)
    return _loads_unique_object(raw, label)


def fetch_and_match_live_ruleset(
    committed_raw: bytes,
    *,
    token: str | None,
    now_us: int,
    require_bypass_visibility: bool = False,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    opener: Callable[..., object] = _direct_urlopen,
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
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
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
    _require_uncached_response(headers)
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


def fetch_repository_permission(
    username: str,
    *,
    token: str | None,
    now_us: int,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    opener: Callable[..., object] = _direct_urlopen,
) -> dict:
    """Prove one individual CODEOWNER exists and has write-or-higher repository access."""
    expected_url = collaborator_permission_url(username)
    if not isinstance(token, str) or not token.strip():
        raise LiveRulesetUnavailable("GITHUB_TOKEN_ABSENT")
    if not isinstance(now_us, int) or isinstance(now_us, bool) or now_us <= 0:
        raise LiveRulesetMismatch("LIVE_PERMISSION_NOW_US_INVALID")
    if not isinstance(timeout_s, (int, float)) or isinstance(timeout_s, bool) or timeout_s <= 0:
        raise LiveRulesetMismatch("LIVE_PERMISSION_TIMEOUT_INVALID")
    request = urllib.request.Request(
        expected_url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "User-Agent": "TriadOrigin-B00R-live-codeowner-verifier",
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
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403, 429} or 500 <= exc.code <= 599:
            raise LiveRulesetUnavailable(f"LIVE_PERMISSION_HTTP_STATUS:{exc.code}") from exc
        raise LiveRulesetMismatch(f"LIVE_PERMISSION_HTTP_STATUS:{exc.code}") from exc
    except (OSError, urllib.error.URLError) as exc:
        raise LiveRulesetUnavailable(
            f"LIVE_PERMISSION_FETCH_FAILED:{type(exc).__name__}") from exc
    if status != 200:
        error = f"LIVE_PERMISSION_HTTP_STATUS:{status}"
        if status in {401, 403, 429} or 500 <= status <= 599:
            raise LiveRulesetUnavailable(error)
        raise LiveRulesetMismatch(error)
    if final_url != expected_url:
        raise LiveRulesetMismatch(f"LIVE_PERMISSION_UNEXPECTED_FINAL_URL:{final_url!r}")
    if len(raw) > MAX_RESPONSE_BYTES:
        raise LiveRulesetMismatch("LIVE_PERMISSION_RESPONSE_TOO_LARGE")
    content_type = _header(headers, "Content-Type").split(";", 1)[0].strip().lower()
    if content_type not in {"application/json", "application/vnd.github+json"}:
        raise LiveRulesetMismatch(f"LIVE_PERMISSION_CONTENT_TYPE_INVALID:{content_type!r}")
    if not _header(headers, "X-GitHub-Request-Id").strip():
        raise LiveRulesetMismatch("LIVE_PERMISSION_REQUEST_ID_ABSENT")
    _require_uncached_response(headers)
    _provider_date_us(_header(headers, "Date"), now_us)
    document = _loads_unique_object(raw, "LIVE_PERMISSION")
    user = document.get("user")
    login = user.get("login") if isinstance(user, dict) else None
    if (not isinstance(login, str) or login.lower() != username.lower()
            or user.get("type") != "User"):
        raise LiveRulesetMismatch("LIVE_PERMISSION_USER_MISMATCH")
    if document.get("permission") not in {"admin", "write"}:
        raise LiveRulesetMismatch(
            f"LIVE_PERMISSION_NOT_WRITE:{document.get('permission')!r}")
    return document


def fetch_codeowners_errors(
    expected_head: str,
    *,
    token: str | None,
    now_us: int,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    opener: Callable[..., object] = _direct_urlopen,
) -> dict:
    """Require GitHub's parser to accept the exact-head CODEOWNERS file without errors."""
    document = _fetch_fixed_json(
        codeowners_errors_url(expected_head), token=token, now_us=now_us,
        api_version=API_VERSION,
        user_agent="TriadOrigin-B00R-live-codeowners-parser-verifier",
        label="LIVE_CODEOWNERS_ERRORS", timeout_s=timeout_s, opener=opener)
    if set(document) != {"errors"} or document.get("errors") != []:
        raise LiveRulesetMismatch("LIVE_CODEOWNERS_PROVIDER_PARSE_ERRORS")
    return document


def fetch_and_match_pull_request(
    committed_raw: bytes,
    *,
    token: str | None,
    now_us: int,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    opener: Callable[..., object] = _direct_urlopen,
) -> dict:
    """Authenticate immutable source-merge facts against the live GitHub pull request."""
    committed = _loads_unique_object(committed_raw, "COMMITTED_SOURCE_PR")
    number = committed.get("number")
    if not isinstance(number, int) or isinstance(number, bool) or number <= 0:
        raise LiveRulesetMismatch("COMMITTED_SOURCE_PR_NUMBER_INVALID")
    live = _fetch_fixed_json(
        pull_request_url(number), token=token, now_us=now_us, api_version=API_VERSION,
        user_agent="TriadOrigin-B00R-live-source-pr-verifier",
        label="LIVE_SOURCE_PR", timeout_s=timeout_s, opener=opener)
    for field in ("number", "state", "merged", "merged_at", "merge_commit_sha"):
        if live.get(field) != committed.get(field):
            raise LiveRulesetMismatch(f"LIVE_SOURCE_PR_FIELD_MISMATCH:{field}")
    for side, fields in (("base", ("ref",)), ("head", ("sha",))):
        committed_side = committed.get(side)
        live_side = live.get(side)
        if not isinstance(committed_side, dict) or not isinstance(live_side, dict):
            raise LiveRulesetMismatch(f"LIVE_SOURCE_PR_SIDE_MALFORMED:{side}")
        for field in fields:
            if live_side.get(field) != committed_side.get(field):
                raise LiveRulesetMismatch(
                    f"LIVE_SOURCE_PR_FIELD_MISMATCH:{side}.{field}")
    for label, side in (("COMMITTED", committed.get("base")), ("LIVE", live.get("base"))):
        repo = side.get("repo") if isinstance(side, dict) else None
        if not isinstance(repo, dict) or repo.get("full_name") != REPOSITORY:
            raise LiveRulesetMismatch(f"{label}_SOURCE_PR_REPOSITORY_MISMATCH")
    return live


def fetch_and_match_rule_suite(
    committed_raw: bytes,
    *,
    token: str | None,
    now_us: int,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    opener: Callable[..., object] = _direct_urlopen,
) -> dict:
    """Authenticate the exact historical provider rule-suite detail used by the canary."""
    committed = _loads_unique_object(committed_raw, "COMMITTED_RULE_SUITE")
    rule_suite_id = committed.get("id")
    if (not isinstance(rule_suite_id, int) or isinstance(rule_suite_id, bool)
            or rule_suite_id <= 0):
        raise LiveRulesetMismatch("COMMITTED_RULE_SUITE_ID_NOT_POSITIVE_INTEGER")
    live = _fetch_fixed_json(
        rule_suite_url(rule_suite_id), token=token, now_us=now_us,
        api_version=RULE_SUITE_API_VERSION,
        user_agent="TriadOrigin-B00R-live-rule-suite-verifier",
        label="LIVE_RULE_SUITE", timeout_s=timeout_s, opener=opener)
    if live != committed:
        raise LiveRulesetMismatch("LIVE_RULE_SUITE_MISMATCH")
    return live


def fetch_canary_ref_sha(
    *,
    token: str | None,
    now_us: int,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    opener: Callable[..., object] = _direct_urlopen,
) -> str:
    """Return the current provider SHA for the fixed harmless canary ref."""
    document = _fetch_fixed_json(
        canary_ref_url(), token=token, now_us=now_us, api_version=API_VERSION,
        user_agent="TriadOrigin-B00R-live-canary-ref-verifier",
        label="LIVE_CANARY_REF", timeout_s=timeout_s, opener=opener)
    target = document.get("object")
    sha = target.get("sha") if isinstance(target, dict) else None
    if (document.get("ref") != "refs/heads/b00r-ruleset-canary"
            or not isinstance(target, dict) or target.get("type") != "commit"
            or not isinstance(sha, str) or re.fullmatch(r"[0-9a-f]{40}", sha) is None):
        raise LiveRulesetMismatch("LIVE_CANARY_REF_MALFORMED")
    return sha


def fetch_anchor_tag_object_sha(
    *,
    token: str | None,
    now_us: int,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    opener: Callable[..., object] = _direct_urlopen,
) -> str:
    """Return the provider's annotated-tag object SHA for the fixed receipt anchor ref."""
    document = _fetch_fixed_json(
        anchor_tag_ref_url(), token=token, now_us=now_us, api_version=API_VERSION,
        user_agent="TriadOrigin-B00R-live-anchor-tag-verifier",
        label="LIVE_ANCHOR_TAG_REF", timeout_s=timeout_s, opener=opener)
    target = document.get("object")
    sha = target.get("sha") if isinstance(target, dict) else None
    if (document.get("ref") != "refs/tags/B00R_RECEIPT_ANCHOR"
            or not isinstance(target, dict) or target.get("type") != "tag"
            or not isinstance(sha, str) or re.fullmatch(r"[0-9a-f]{40}", sha) is None):
        raise LiveRulesetMismatch("LIVE_ANCHOR_TAG_REF_MALFORMED")
    return sha
