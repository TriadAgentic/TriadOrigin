#!/usr/bin/env python3
"""Fail-closed live GitHub ruleset origin and freshness verification.

A committed capture plus an external digest proves byte immutability, not provider provenance.
Terminal B00R gates therefore re-fetch the fixed repository/ruleset endpoint over authenticated TLS
and compare every security-relevant provider field in memory.  No URL, response file, or token is
accepted from an argument.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
import json
import re
from typing import Callable
import urllib.error
import urllib.request

REPOSITORY = "TriadAgentic/TriadOrigin"
REPOSITORY_ID = 1_327_825_324
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


@dataclass(frozen=True)
class LiveReceiptMerge:
    """Provider-authenticated receipt-PR closure facts.

    These facts cannot be committed inside the receipt PR without a self-reference.  Terminal
    closure therefore derives them from fixed GitHub endpoints and cross-binds them to the local
    merge object, exact-head review, Actions check run, and current ``main`` ancestry.
    """

    pull_request: int
    head_sha: str
    merge_sha: str
    merged_at_us: int
    reviewer: str
    review_id: int
    workflow_run_id: int
    check_run_id: int


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


def _loads_unique_array(data: bytes, label: str) -> list[dict]:
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
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise LiveRulesetMismatch(f"{label}_NOT_OBJECT_ARRAY")
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
        f"https://api.github.com/repos/{REPOSITORY}/git/ref/tags/B00R_RECEIPT_ANCHOR_G2"
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


def pull_request_reviews_url(number: int) -> str:
    if not isinstance(number, int) or isinstance(number, bool) or number <= 0:
        raise LiveRulesetMismatch("PULL_REQUEST_NUMBER_INVALID")
    return f"https://api.github.com/repos/{REPOSITORY}/pulls/{number}/reviews?per_page=100"


def workflow_runs_for_head_url(head_sha: str) -> str:
    if not isinstance(head_sha, str) or re.fullmatch(r"[0-9a-f]{40}", head_sha) is None:
        raise LiveRulesetMismatch("WORKFLOW_HEAD_SHA_INVALID")
    return (
        f"https://api.github.com/repos/{REPOSITORY}/actions/runs"
        f"?head_sha={head_sha}&event=pull_request&status=completed&per_page=100"
    )


def check_runs_for_head_url(head_sha: str) -> str:
    if not isinstance(head_sha, str) or re.fullmatch(r"[0-9a-f]{40}", head_sha) is None:
        raise LiveRulesetMismatch("CHECK_RUN_HEAD_SHA_INVALID")
    return f"https://api.github.com/repos/{REPOSITORY}/commits/{head_sha}/check-runs?per_page=100"


def compare_receipt_merge_to_main_url(merge_sha: str) -> str:
    if not isinstance(merge_sha, str) or re.fullmatch(r"[0-9a-f]{40}", merge_sha) is None:
        raise LiveRulesetMismatch("RECEIPT_MERGE_SHA_INVALID")
    return f"https://api.github.com/repos/{REPOSITORY}/compare/{merge_sha}...main"


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


def _provider_utc_us(value: object, label: str) -> int:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise LiveRulesetMismatch(f"{label}_INVALID")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
        if parsed.tzinfo is None:
            raise ValueError("timezone absent")
        return int(parsed.timestamp() * 1_000_000)
    except (OverflowError, TypeError, ValueError) as exc:
        raise LiveRulesetMismatch(f"{label}_INVALID") from exc


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


def _fetch_fixed_json_array(
    expected_url: str,
    *,
    token: str | None,
    now_us: int,
    api_version: str,
    user_agent: str,
    label: str,
    timeout_s: float,
    opener: Callable[..., object],
) -> list[dict]:
    """Fetch one fixed GitHub array endpoint and reject redirects, caching, and pagination."""
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
    if "rel=\"next\"" in _header(headers, "Link"):
        raise LiveRulesetMismatch(f"{label}_PAGINATION_UNRESOLVED")
    _require_uncached_response(headers)
    _provider_date_us(_header(headers, "Date"), now_us)
    return _loads_unique_array(raw, label)


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
    for label, document in (("COMMITTED", committed), ("LIVE", live)):
        for side_name in ("base", "head"):
            side = document.get(side_name)
            repo = side.get("repo") if isinstance(side, dict) else None
            if (not isinstance(repo, dict)
                    or repo.get("full_name") != REPOSITORY
                    or repo.get("id") != REPOSITORY_ID):
                raise LiveRulesetMismatch(
                    f"{label}_SOURCE_PR_REPOSITORY_MISMATCH:{side_name}")
        user = document.get("user")
        if (not isinstance(user, dict) or user.get("type") != "User"
                or not isinstance(user.get("login"), str)):
            raise LiveRulesetMismatch(f"{label}_SOURCE_PR_AUTHOR_MALFORMED")
    if live["user"]["login"].lower() != committed["user"]["login"].lower():
        raise LiveRulesetMismatch("LIVE_SOURCE_PR_AUTHOR_MISMATCH")
    return live


def _require_latest_decisive_review(
    reviews: list[dict],
    approved: dict,
    *,
    label: str,
) -> None:
    """Reject an approval superseded by a later decision from the same reviewer.

    GitHub retains review history. Merely locating an earlier ``APPROVED`` row can therefore
    false-green after that reviewer submits ``CHANGES_REQUESTED``. The committed/live approval
    must be the reviewer's latest decisive (non-comment-only) review.
    """
    approved_user = approved.get("user")
    approved_login = (
        approved_user.get("login") if isinstance(approved_user, dict) else None
    )
    approved_id = approved.get("id")
    if (not isinstance(approved_login, str) or not approved_login
            or not isinstance(approved_id, int) or isinstance(approved_id, bool)
            or approved_id <= 0):
        raise LiveRulesetMismatch(f"{label}_APPROVAL_MALFORMED")
    decisive_states = {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}
    same_reviewer: list[tuple[int, int, dict]] = []
    for candidate in reviews:
        if candidate.get("state") not in decisive_states:
            continue
        user = candidate.get("user")
        login = user.get("login") if isinstance(user, dict) else None
        review_id = candidate.get("id")
        if (not isinstance(login, str) or not login
                or not isinstance(review_id, int) or isinstance(review_id, bool)
                or review_id <= 0):
            raise LiveRulesetMismatch(f"{label}_DECISIVE_REVIEW_MALFORMED")
        if login.lower() != approved_login.lower():
            continue
        submitted_at_us = _provider_utc_us(
            candidate.get("submitted_at"), f"{label}_DECISIVE_REVIEW_SUBMITTED_AT")
        same_reviewer.append((submitted_at_us, review_id, candidate))
    if not same_reviewer:
        raise LiveRulesetMismatch(f"{label}_DECISIVE_REVIEW_ABSENT")
    latest = max(same_reviewer, key=lambda row: (row[0], row[1]))[2]
    if latest.get("id") != approved_id or latest.get("state") != "APPROVED":
        raise LiveRulesetMismatch(f"{label}_APPROVAL_SUPERSEDED")


def fetch_and_match_pull_request_review(
    committed_raw: bytes,
    *,
    token: str | None,
    now_us: int,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    opener: Callable[..., object] = _direct_urlopen,
) -> dict:
    """Require one committed exact-head APPROVED review to remain APPROVED at GitHub."""
    committed = _loads_unique_object(committed_raw, "COMMITTED_SOURCE_PR_REVIEW")
    number = committed.get("source_pr")
    review = committed.get("review")
    if (not isinstance(number, int) or isinstance(number, bool) or number <= 0
            or not isinstance(review, dict)):
        raise LiveRulesetMismatch("COMMITTED_SOURCE_PR_REVIEW_MALFORMED")
    review_id = review.get("id")
    if not isinstance(review_id, int) or isinstance(review_id, bool) or review_id <= 0:
        raise LiveRulesetMismatch("COMMITTED_SOURCE_PR_REVIEW_ID_INVALID")
    reviews = _fetch_fixed_json_array(
        pull_request_reviews_url(number), token=token, now_us=now_us,
        api_version=API_VERSION,
        user_agent="TriadOrigin-B00R-G2-live-source-pr-review-verifier",
        label="LIVE_SOURCE_PR_REVIEWS", timeout_s=timeout_s, opener=opener)
    matches = [item for item in reviews if item.get("id") == review_id]
    if len(matches) != 1:
        raise LiveRulesetMismatch(
            f"LIVE_SOURCE_PR_REVIEW_ID_COUNT:{review_id}:{len(matches)}")
    live = matches[0]
    for field in ("id", "state", "commit_id", "submitted_at"):
        if live.get(field) != review.get(field):
            raise LiveRulesetMismatch(f"LIVE_SOURCE_PR_REVIEW_FIELD_MISMATCH:{field}")
    for label, candidate in (("COMMITTED", review), ("LIVE", live)):
        user = candidate.get("user")
        if (not isinstance(user, dict) or user.get("type") != "User"
                or not isinstance(user.get("login"), str)):
            raise LiveRulesetMismatch(f"{label}_SOURCE_PR_REVIEW_USER_MALFORMED")
    if live["user"]["login"].lower() != review["user"]["login"].lower():
        raise LiveRulesetMismatch("LIVE_SOURCE_PR_REVIEW_USER_MISMATCH")
    if live.get("state") != "APPROVED":
        raise LiveRulesetMismatch("LIVE_SOURCE_PR_REVIEW_NOT_APPROVED")
    _require_latest_decisive_review(
        reviews, live, label="LIVE_SOURCE_PR_REVIEW")
    return live


def fetch_and_verify_receipt_merge(
    number: int,
    *,
    expected_merge_sha: str,
    expected_codeowner: str,
    token: str | None,
    now_us: int,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    opener: Callable[..., object] = _direct_urlopen,
) -> LiveReceiptMerge:
    """Prove that ``expected_merge_sha`` is a reviewed, CI-green receipt PR on ``main``.

    The receipt PR cannot commit its own post-merge provider response.  This terminal-only proof
    therefore uses fixed endpoints, refuses redirects/cached responses, and binds the exact merge
    to its PR head, one independent CODEOWNER approval, the required GitHub Actions job, and live
    ``main`` ancestry.  Local callers additionally verify the two-parent Git object.
    """
    if not isinstance(number, int) or isinstance(number, bool) or number <= 0:
        raise LiveRulesetMismatch("RECEIPT_PR_NUMBER_INVALID")
    if (not isinstance(expected_merge_sha, str)
            or re.fullmatch(r"[0-9a-f]{40}", expected_merge_sha) is None):
        raise LiveRulesetMismatch("RECEIPT_MERGE_SHA_INVALID")
    if (not isinstance(expected_codeowner, str)
            or re.fullmatch(
                r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?",
                expected_codeowner,
            ) is None):
        raise LiveRulesetMismatch("RECEIPT_CODEOWNER_INVALID")

    pr = _fetch_fixed_json(
        pull_request_url(number), token=token, now_us=now_us, api_version=API_VERSION,
        user_agent="TriadOrigin-B00R-G2-live-receipt-pr-verifier",
        label="LIVE_RECEIPT_PR", timeout_s=timeout_s, opener=opener)
    base = pr.get("base")
    head = pr.get("head")
    base_repo = base.get("repo") if isinstance(base, dict) else None
    head_repo = head.get("repo") if isinstance(head, dict) else None
    author = pr.get("user")
    head_sha = head.get("sha") if isinstance(head, dict) else None
    author_login = author.get("login") if isinstance(author, dict) else None
    if (pr.get("number") != number
            or pr.get("state") != "closed" or pr.get("merged") is not True
            or pr.get("merge_commit_sha") != expected_merge_sha
            or not isinstance(base, dict) or base.get("ref") != "main"
            or not isinstance(base_repo, dict)
            or base_repo.get("full_name") != REPOSITORY
            or base_repo.get("id") != REPOSITORY_ID
            or not isinstance(head, dict)
            or not isinstance(head_sha, str)
            or re.fullmatch(r"[0-9a-f]{40}", head_sha) is None
            or not isinstance(head_repo, dict)
            or head_repo.get("full_name") != REPOSITORY
            or head_repo.get("id") != REPOSITORY_ID
            or not isinstance(author, dict) or author.get("type") != "User"
            or not isinstance(author_login, str) or not author_login):
        raise LiveRulesetMismatch("LIVE_RECEIPT_PR_IDENTITY_MISMATCH")
    merged_at_us = _provider_utc_us(pr.get("merged_at"), "LIVE_RECEIPT_PR_MERGED_AT")
    if merged_at_us > now_us:
        raise LiveRulesetMismatch("LIVE_RECEIPT_PR_MERGED_AT_IN_FUTURE")

    reviews = _fetch_fixed_json_array(
        pull_request_reviews_url(number), token=token, now_us=now_us,
        api_version=API_VERSION,
        user_agent="TriadOrigin-B00R-G2-live-receipt-review-verifier",
        label="LIVE_RECEIPT_PR_REVIEWS", timeout_s=timeout_s, opener=opener)
    matching_reviews: list[dict] = []
    for review in reviews:
        user = review.get("user")
        login = user.get("login") if isinstance(user, dict) else None
        if (review.get("state") == "APPROVED"
                and review.get("commit_id") == head_sha
                and isinstance(review.get("id"), int)
                and not isinstance(review.get("id"), bool)
                and review.get("id") > 0
                and isinstance(user, dict) and user.get("type") == "User"
                and isinstance(login, str)
                and login.lower() == expected_codeowner.lower()):
            matching_reviews.append(review)
    if len(matching_reviews) != 1:
        raise LiveRulesetMismatch(
            f"LIVE_RECEIPT_PR_EXACT_HEAD_CODEOWNER_APPROVAL_COUNT:{len(matching_reviews)}")
    review = matching_reviews[0]
    _require_latest_decisive_review(
        reviews, review, label="LIVE_RECEIPT_PR_REVIEW")
    reviewer = review["user"]["login"]
    if reviewer.lower() == author_login.lower():
        raise LiveRulesetMismatch("LIVE_RECEIPT_PR_REVIEW_NOT_INDEPENDENT")
    submitted_at_us = _provider_utc_us(
        review.get("submitted_at"), "LIVE_RECEIPT_PR_REVIEW_SUBMITTED_AT")
    if submitted_at_us >= merged_at_us:
        raise LiveRulesetMismatch("LIVE_RECEIPT_PR_REVIEW_NOT_BEFORE_MERGE")
    fetch_repository_permission(
        reviewer, token=token, now_us=now_us, timeout_s=timeout_s, opener=opener)

    workflow_document = _fetch_fixed_json(
        workflow_runs_for_head_url(head_sha), token=token, now_us=now_us,
        api_version=API_VERSION,
        user_agent="TriadOrigin-B00R-G2-live-receipt-workflow-verifier",
        label="LIVE_RECEIPT_WORKFLOW_RUNS", timeout_s=timeout_s, opener=opener)
    workflow_runs = workflow_document.get("workflow_runs")
    workflow_total = workflow_document.get("total_count")
    if (not isinstance(workflow_total, int) or isinstance(workflow_total, bool)
            or workflow_total < 0
            or not isinstance(workflow_runs, list)
            or workflow_total != len(workflow_runs)
            or any(not isinstance(item, dict) for item in workflow_runs)):
        raise LiveRulesetMismatch("LIVE_RECEIPT_WORKFLOW_RUNS_MALFORMED")
    matching_workflows = []
    for run in workflow_runs:
        pull_requests = run.get("pull_requests")
        repository = run.get("repository")
        head_repository = run.get("head_repository")
        workflow_path = run.get("path")
        valid_workflow_path = (
            isinstance(workflow_path, str)
            and re.fullmatch(r"\.github/workflows/ci\.yml@[A-Za-z0-9._/-]+", workflow_path)
            is not None
            and ".." not in workflow_path.split("@", 1)[1]
        )
        try:
            workflow_completed_at_us = _provider_utc_us(
                run.get("updated_at"), "LIVE_RECEIPT_WORKFLOW_COMPLETED_AT")
        except LiveRulesetMismatch:
            continue
        if (run.get("head_sha") == head_sha
                and run.get("event") == "pull_request"
                and run.get("status") == "completed"
                and run.get("conclusion") == "success"
                and valid_workflow_path
                and isinstance(run.get("id"), int)
                and not isinstance(run.get("id"), bool) and run.get("id") > 0
                and isinstance(run.get("check_suite_id"), int)
                and not isinstance(run.get("check_suite_id"), bool)
                and isinstance(repository, dict)
                and repository.get("full_name") == REPOSITORY
                and repository.get("id") == REPOSITORY_ID
                and isinstance(head_repository, dict)
                and head_repository.get("full_name") == REPOSITORY
                and head_repository.get("id") == REPOSITORY_ID
                and isinstance(pull_requests, list)
                and any(isinstance(item, dict) and item.get("number") == number
                        for item in pull_requests)
                and workflow_completed_at_us < merged_at_us):
            matching_workflows.append(run)
    if len(matching_workflows) != 1:
        raise LiveRulesetMismatch(
            f"LIVE_RECEIPT_PR_SUCCESS_WORKFLOW_COUNT:{len(matching_workflows)}")
    workflow = matching_workflows[0]

    checks_document = _fetch_fixed_json(
        check_runs_for_head_url(head_sha), token=token, now_us=now_us,
        api_version=API_VERSION,
        user_agent="TriadOrigin-B00R-G2-live-receipt-check-verifier",
        label="LIVE_RECEIPT_CHECK_RUNS", timeout_s=timeout_s, opener=opener)
    check_runs = checks_document.get("check_runs")
    checks_total = checks_document.get("total_count")
    if (not isinstance(checks_total, int) or isinstance(checks_total, bool)
            or checks_total < 0
            or not isinstance(check_runs, list)
            or checks_total != len(check_runs)
            or any(not isinstance(item, dict) for item in check_runs)):
        raise LiveRulesetMismatch("LIVE_RECEIPT_CHECK_RUNS_MALFORMED")
    matching_checks = []
    for check in check_runs:
        app = check.get("app")
        check_suite = check.get("check_suite")
        try:
            check_completed_at_us = _provider_utc_us(
                check.get("completed_at"), "LIVE_RECEIPT_CHECK_COMPLETED_AT")
        except LiveRulesetMismatch:
            continue
        if (check.get("name") == "test-and-verify"
                and check.get("head_sha") == head_sha
                and check.get("status") == "completed"
                and check.get("conclusion") == "success"
                and isinstance(check.get("id"), int)
                and not isinstance(check.get("id"), bool) and check.get("id") > 0
                and isinstance(app, dict) and app.get("id") == 15368
                and isinstance(check_suite, dict)
                and check_suite.get("id") == workflow.get("check_suite_id")
                and check_completed_at_us < merged_at_us):
            matching_checks.append(check)
    if len(matching_checks) != 1:
        raise LiveRulesetMismatch(
            f"LIVE_RECEIPT_PR_REQUIRED_CHECK_COUNT:{len(matching_checks)}")
    check = matching_checks[0]

    comparison = _fetch_fixed_json(
        compare_receipt_merge_to_main_url(expected_merge_sha), token=token, now_us=now_us,
        api_version=API_VERSION,
        user_agent="TriadOrigin-B00R-G2-live-receipt-main-ancestry-verifier",
        label="LIVE_RECEIPT_MAIN_ANCESTRY", timeout_s=timeout_s, opener=opener)
    base_commit = comparison.get("base_commit")
    merge_base = comparison.get("merge_base_commit")
    if (comparison.get("status") not in {"ahead", "identical"}
            or comparison.get("behind_by") != 0
            or not isinstance(base_commit, dict)
            or base_commit.get("sha") != expected_merge_sha
            or not isinstance(merge_base, dict)
            or merge_base.get("sha") != expected_merge_sha):
        raise LiveRulesetMismatch("LIVE_RECEIPT_MERGE_NOT_ON_MAIN")

    return LiveReceiptMerge(
        pull_request=number,
        head_sha=head_sha,
        merge_sha=expected_merge_sha,
        merged_at_us=merged_at_us,
        reviewer=reviewer,
        review_id=review["id"],
        workflow_run_id=workflow["id"],
        check_run_id=check["id"],
    )


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
    if (document.get("ref") != "refs/tags/B00R_RECEIPT_ANCHOR_G2"
            or not isinstance(target, dict) or target.get("type") != "tag"
            or not isinstance(sha, str) or re.fullmatch(r"[0-9a-f]{40}", sha) is None):
        raise LiveRulesetMismatch("LIVE_ANCHOR_TAG_REF_MALFORMED")
    return sha
