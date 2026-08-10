"""Falsification tests for mandatory live GitHub ruleset provenance and freshness."""

from __future__ import annotations

import copy
import io
import json
import urllib.error

import pytest

from tools.github_ruleset_live import (
    LiveRulesetMismatch,
    LiveRulesetUnavailable,
    anchor_tag_ref_url,
    canary_ref_url,
    codeowners_errors_url,
    collaborator_permission_url,
    fetch_and_match_rule_suite,
    fetch_and_match_live_ruleset,
    fetch_and_match_pull_request,
    fetch_anchor_tag_object_sha,
    fetch_canary_ref_sha,
    fetch_codeowners_errors,
    fetch_repository_permission,
    pull_request_url,
    rule_suite_url,
    ruleset_url,
)


NOW_US = 30_000_000
DATE = "Thu, 01 Jan 1970 00:00:30 GMT"


def _ruleset() -> dict:
    return {
        "id": 42,
        "name": "main",
        "target": "branch",
        "source_type": "Repository",
        "source": "TriadAgentic/TriadOrigin",
        "enforcement": "active",
        "bypass_actors": [],
        "current_user_can_bypass": "never",
        "node_id": "RRS_provider42",
        "_links": {
            "self": {
                "href": "https://api.github.com/repos/TriadAgentic/TriadOrigin/rulesets/42"
            },
            "html": {"href": "https://github.com/TriadAgentic/TriadOrigin/rules/42"},
        },
        "created_at": "1970-01-01T00:00:05Z",
        "updated_at": "1970-01-01T00:00:10Z",
        "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
        "rules": [{"type": "deletion"}],
    }


class _Response:
    def __init__(
        self,
        document: dict,
        *,
        url: str = ruleset_url(42),
        status: int = 200,
        headers: dict[str, str] | None = None,
    ):
        self.status = status
        self._url = url
        self._body = json.dumps(document).encode()
        self.headers = headers or {
            "Content-Type": "application/json; charset=utf-8",
            "Date": DATE,
            "X-GitHub-Request-Id": "REQ:live:42",
        }

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def getcode(self):
        return self.status

    def geturl(self):
        return self._url

    def read(self, limit: int):
        return self._body[:limit]


def test_live_ruleset_uses_fixed_authenticated_endpoint_and_matches_security_fields():
    committed = _ruleset()
    seen = {}

    def opener(request, *, timeout):
        seen["url"] = request.full_url
        seen["method"] = request.get_method()
        seen["authorization"] = request.get_header("Authorization")
        seen["cache_control"] = request.get_header("Cache-control")
        seen["pragma"] = request.get_header("Pragma")
        seen["version"] = request.get_header("X-github-api-version")
        seen["timeout"] = timeout
        return _Response(copy.deepcopy(committed))

    result = fetch_and_match_live_ruleset(
        json.dumps(committed).encode(), token="test-token", now_us=NOW_US, opener=opener
    )
    assert result.document == committed
    assert result.bypass_visible is True
    assert result.request_id == "REQ:live:42"
    assert seen == {
        "url": ruleset_url(42),
        "method": "GET",
        "authorization": "Bearer test-token",
        "cache_control": "no-cache",
        "pragma": "no-cache",
        "version": "2022-11-28",
        "timeout": 20.0,
    }


def test_live_ruleset_allows_hidden_bypass_only_before_terminal_mode():
    committed = _ruleset()
    live = copy.deepcopy(committed)
    live.pop("bypass_actors")
    result = fetch_and_match_live_ruleset(
        json.dumps(committed).encode(), token="token", now_us=NOW_US,
        opener=lambda *_args, **_kwargs: _Response(live),
    )
    assert result.bypass_visible is False
    with pytest.raises(LiveRulesetMismatch, match="BYPASS_VISIBILITY_REQUIRED"):
        fetch_and_match_live_ruleset(
            json.dumps(committed).encode(), token="token", now_us=NOW_US,
            require_bypass_visibility=True,
            opener=lambda *_args, **_kwargs: _Response(live),
        )


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (lambda live: live.__setitem__("enforcement", "disabled"), "enforcement"),
        (lambda live: live.__setitem__("current_user_can_bypass", "always"), "BYPASS"),
        (lambda live: live.__setitem__("bypass_actors", [{"actor_id": 1}]), "BYPASS"),
        (lambda live: live["conditions"]["ref_name"].__setitem__(
            "exclude", ["refs/heads/*"]), "conditions"),
    ],
)
def test_live_ruleset_rejects_security_drift(mutation, reason):
    committed = _ruleset()
    live = copy.deepcopy(committed)
    mutation(live)
    with pytest.raises(LiveRulesetMismatch, match=reason):
        fetch_and_match_live_ruleset(
            json.dumps(committed).encode(), token="token", now_us=NOW_US,
            opener=lambda *_args, **_kwargs: _Response(live),
        )


def test_live_ruleset_rejects_missing_token_redirect_and_stale_date_without_leaking_token():
    committed_raw = json.dumps(_ruleset()).encode()
    with pytest.raises(LiveRulesetUnavailable, match="TOKEN_ABSENT"):
        fetch_and_match_live_ruleset(committed_raw, token=None, now_us=NOW_US)

    with pytest.raises(LiveRulesetMismatch, match="UNEXPECTED_FINAL_URL"):
        fetch_and_match_live_ruleset(
            committed_raw, token="never-print-this", now_us=NOW_US,
            opener=lambda *_args, **_kwargs: _Response(
                _ruleset(), url="https://example.invalid/ruleset"),
        )

    stale_headers = {
        "Content-Type": "application/json",
        "Date": "Thu, 01 Jan 1970 00:00:01 GMT",
        "X-GitHub-Request-Id": "REQ:stale",
    }
    with pytest.raises(LiveRulesetMismatch, match="DATE_STALE") as caught:
        fetch_and_match_live_ruleset(
            committed_raw, token="never-print-this",
            now_us=NOW_US + 6 * 60 * 1_000_000,
            opener=lambda *_args, **_kwargs: _Response(
                _ruleset(), headers=stale_headers),
        )
    assert "never-print-this" not in str(caught.value)


def test_live_ruleset_classifies_provider_outage_unavailable():
    error = urllib.error.HTTPError(
        ruleset_url(42), 403, "forbidden", {}, io.BytesIO(b"{}")
    )

    def opener(*_args, **_kwargs):
        raise error

    with pytest.raises(LiveRulesetUnavailable, match="HTTP_STATUS:403"):
        fetch_and_match_live_ruleset(
            json.dumps(_ruleset()).encode(), token="token", now_us=NOW_US, opener=opener
        )


@pytest.mark.parametrize("age", ["30", "-1", "stale"])
def test_live_ruleset_rejects_cached_or_malformed_age(age):
    headers = {
        "Content-Type": "application/json",
        "Date": DATE,
        "Age": age,
        "X-GitHub-Request-Id": "REQ:cached",
    }
    with pytest.raises(LiveRulesetMismatch, match="CACHE_AGE"):
        fetch_and_match_live_ruleset(
            json.dumps(_ruleset()).encode(), token="token", now_us=NOW_US,
            opener=lambda *_args, **_kwargs: _Response(_ruleset(), headers=headers),
        )


def test_live_codeowner_permission_uses_fixed_endpoint_and_requires_write():
    seen = {}
    permission = {
        "permission": "write",
        "role_name": "write",
        "user": {"login": "independent-reviewer", "type": "User"},
    }

    def opener(request, *, timeout):
        seen["url"] = request.full_url
        seen["method"] = request.get_method()
        seen["authorization"] = request.get_header("Authorization")
        seen["cache_control"] = request.get_header("Cache-control")
        seen["timeout"] = timeout
        return _Response(
            permission,
            url=collaborator_permission_url("independent-reviewer"),
        )

    assert fetch_repository_permission(
        "independent-reviewer", token="test-token", now_us=NOW_US, opener=opener
    ) == permission
    assert seen == {
        "url": collaborator_permission_url("independent-reviewer"),
        "method": "GET",
        "authorization": "Bearer test-token",
        "cache_control": "no-cache",
        "timeout": 20.0,
    }


@pytest.mark.parametrize(
    ("document", "reason"),
    [
        ({"permission": "read", "user": {"login": "reviewer", "type": "User"}},
         "NOT_WRITE"),
        ({"permission": "write", "user": {"login": "attacker", "type": "User"}},
         "USER_MISMATCH"),
        ({"permission": "write", "user": {"login": "reviewer", "type": "Bot"}},
         "USER_MISMATCH"),
    ],
)
def test_live_codeowner_permission_rejects_unwritable_or_wrong_identity(document, reason):
    with pytest.raises(LiveRulesetMismatch, match=reason):
        fetch_repository_permission(
            "reviewer", token="token", now_us=NOW_US,
            opener=lambda *_args, **_kwargs: _Response(
                document, url=collaborator_permission_url("reviewer")),
        )


def test_live_codeowners_parser_is_bound_to_exact_head_and_must_report_no_errors():
    head = "c" * 40
    seen = {}

    def opener(request, *, timeout):
        seen["url"] = request.full_url
        return _Response({"errors": []}, url=codeowners_errors_url(head))

    assert fetch_codeowners_errors(
        head, token="token", now_us=NOW_US, opener=opener) == {"errors": []}
    assert seen["url"] == codeowners_errors_url(head)

    with pytest.raises(LiveRulesetMismatch, match="PROVIDER_PARSE_ERRORS"):
        fetch_codeowners_errors(
            head, token="token", now_us=NOW_US,
            opener=lambda *_args, **_kwargs: _Response(
                {"errors": [{"line": 1, "kind": "Invalid owner"}]},
                url=codeowners_errors_url(head)),
        )


def _rule_suite() -> dict:
    return {
        "id": 99,
        "actor_id": 7,
        "actor_name": "canary-pusher",
        "before_sha": "a" * 40,
        "after_sha": "b" * 40,
        "ref": "refs/heads/b00r-ruleset-canary",
        "repository_id": 1_327_825_324,
        "repository_name": "TriadOrigin",
        "pushed_at": "1970-01-01T00:00:15Z",
        "result": "fail",
        "evaluation_result": None,
        "rule_evaluations": [{
            "rule_source": {"type": "ruleset", "id": 42, "name": "main"},
            "enforcement": "active",
            "result": "fail",
            "rule_type": "pull_request",
        }],
    }


def test_live_rule_suite_uses_fixed_admin_endpoint_and_requires_exact_provider_bytes():
    committed = _rule_suite()
    seen = {}

    def opener(request, *, timeout):
        seen["url"] = request.full_url
        seen["version"] = request.get_header("X-github-api-version")
        seen["cache_control"] = request.get_header("Cache-control")
        seen["timeout"] = timeout
        return _Response(copy.deepcopy(committed), url=rule_suite_url(99))

    assert fetch_and_match_rule_suite(
        json.dumps(committed).encode(), token="admin-read-token", now_us=NOW_US,
        opener=opener,
    ) == committed
    assert seen == {
        "url": rule_suite_url(99),
        "version": "2026-03-10",
        "cache_control": "no-cache",
        "timeout": 20.0,
    }

    changed = copy.deepcopy(committed)
    changed["result"] = "pass"
    with pytest.raises(LiveRulesetMismatch, match="RULE_SUITE_MISMATCH"):
        fetch_and_match_rule_suite(
            json.dumps(committed).encode(), token="admin-read-token", now_us=NOW_US,
            opener=lambda *_args, **_kwargs: _Response(
                changed, url=rule_suite_url(99)),
        )


def test_live_canary_ref_is_fixed_and_must_resolve_to_a_commit_sha():
    ref = {
        "ref": "refs/heads/b00r-ruleset-canary",
        "node_id": "REF_canary",
        "url": canary_ref_url(),
        "object": {"type": "commit", "sha": "a" * 40, "url": "https://api.github.com/x"},
    }
    seen = {}

    def opener(request, *, timeout):
        seen["url"] = request.full_url
        seen["version"] = request.get_header("X-github-api-version")
        return _Response(ref, url=canary_ref_url())

    assert fetch_canary_ref_sha(
        token="token", now_us=NOW_US, opener=opener) == "a" * 40
    assert seen == {"url": canary_ref_url(), "version": "2022-11-28"}

    malformed = copy.deepcopy(ref)
    malformed["object"]["type"] = "tag"
    with pytest.raises(LiveRulesetMismatch, match="CANARY_REF_MALFORMED"):
        fetch_canary_ref_sha(
            token="token", now_us=NOW_US,
            opener=lambda *_args, **_kwargs: _Response(
                malformed, url=canary_ref_url()),
        )


def test_live_source_pr_binds_provider_merge_identity_without_volatile_fields():
    committed = {
        "number": 28,
        "state": "closed",
        "merged": True,
        "merged_at": "1970-01-01T00:00:20Z",
        "merge_commit_sha": "d" * 40,
        "base": {
            "ref": "main",
            "repo": {"full_name": "TriadAgentic/TriadOrigin"},
        },
        "head": {"sha": "e" * 40},
        "updated_at": "1970-01-01T00:00:21Z",
    }
    live = copy.deepcopy(committed)
    live["updated_at"] = "1970-01-01T00:00:29Z"
    assert fetch_and_match_pull_request(
        json.dumps(committed).encode(), token="token", now_us=NOW_US,
        opener=lambda *_args, **_kwargs: _Response(live, url=pull_request_url(28)),
    ) == live

    changed = copy.deepcopy(live)
    changed["merge_commit_sha"] = "f" * 40
    with pytest.raises(LiveRulesetMismatch, match="merge_commit_sha"):
        fetch_and_match_pull_request(
            json.dumps(committed).encode(), token="token", now_us=NOW_US,
            opener=lambda *_args, **_kwargs: _Response(
                changed, url=pull_request_url(28)),
        )


def test_live_anchor_ref_must_resolve_to_annotated_tag_object():
    document = {
        "ref": "refs/tags/B00R_RECEIPT_ANCHOR",
        "object": {"type": "tag", "sha": "f" * 40},
    }
    assert fetch_anchor_tag_object_sha(
        token="token", now_us=NOW_US,
        opener=lambda *_args, **_kwargs: _Response(
            document, url=anchor_tag_ref_url()),
    ) == "f" * 40
    document["object"]["type"] = "commit"
    with pytest.raises(LiveRulesetMismatch, match="ANCHOR_TAG_REF_MALFORMED"):
        fetch_anchor_tag_object_sha(
            token="token", now_us=NOW_US,
            opener=lambda *_args, **_kwargs: _Response(
                document, url=anchor_tag_ref_url()),
        )
