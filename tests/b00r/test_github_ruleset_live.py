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
    fetch_and_match_live_ruleset,
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
            committed_raw, token="never-print-this", now_us=NOW_US,
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
