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
    check_runs_for_head_url,
    codeowners_errors_url,
    collaborator_permission_url,
    compare_receipt_merge_to_main_url,
    fetch_and_match_live_ruleset,
    fetch_and_match_pull_request,
    fetch_and_match_pull_request_review,
    fetch_and_match_rule_suite,
    fetch_and_verify_receipt_head,
    fetch_and_verify_receipt_merge,
    fetch_anchor_tag_object_sha,
    fetch_canary_ref_sha,
    fetch_codeowners_errors,
    fetch_repository_permission,
    pull_request_url,
    pull_request_reviews_url,
    rule_suite_url,
    ruleset_url,
    workflow_runs_for_head_url,
)


NOW_US = 30_000_000
DATE = "Thu, 01 Jan 1970 00:00:30 GMT"
REPOSITORY = "TriadAgentic/TriadOrigin"
REPOSITORY_ID = 1_327_825_324
SOURCE_PR = 28
SOURCE_HEAD = "e" * 40


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
        "conditions": {
            "ref_name": {
                "include": [
                    "refs/heads/main",
                    "refs/heads/b00r-ruleset-canary",
                ],
                "exclude": [],
            }
        },
        "rules": [
            {
                "type": "pull_request",
                "parameters": {
                    "required_approving_review_count": 1,
                    "dismiss_stale_reviews_on_push": True,
                    "require_code_owner_review": True,
                    "require_last_push_approval": True,
                    "required_review_thread_resolution": True,
                    "allowed_merge_methods": ["merge"],
                },
            },
            {
                "type": "required_status_checks",
                "parameters": {
                    "strict_required_status_checks_policy": True,
                    "do_not_enforce_on_create": False,
                    "required_status_checks": [
                        {
                            "context": "test-and-verify",
                            "integration_id": 15368,
                        }
                    ],
                },
            },
            {"type": "non_fast_forward"},
            {"type": "deletion"},
        ],
    }


class _Response:
    def __init__(
        self,
        document: object,
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
        (lambda live: live["rules"][0]["parameters"].__setitem__(
            "allowed_merge_methods", ["merge", "squash"]), "rules"),
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


def _source_pr() -> dict:
    return {
        "number": SOURCE_PR,
        "state": "closed",
        "merged": True,
        "merged_at": "1970-01-01T00:00:20Z",
        "merge_commit_sha": "d" * 40,
        "base": {
            "ref": "main",
            "repo": {"full_name": REPOSITORY, "id": REPOSITORY_ID},
        },
        "head": {
            "sha": SOURCE_HEAD,
            "repo": {"full_name": REPOSITORY, "id": REPOSITORY_ID},
        },
        "user": {"login": "source-author", "type": "User"},
        "updated_at": "1970-01-01T00:00:21Z",
    }


def _source_pr_review(*, state: str = "APPROVED") -> dict:
    return {
        "source_pr": SOURCE_PR,
        "source_head": SOURCE_HEAD,
        "review": {
            "id": 7001,
            "state": state,
            "commit_id": SOURCE_HEAD,
            "submitted_at": "1970-01-01T00:00:19Z",
            "user": {"login": "independent-reviewer", "type": "User"},
        },
    }


def test_live_source_pr_binds_provider_merge_identity_without_volatile_fields():
    committed = _source_pr()
    live = copy.deepcopy(committed)
    live["updated_at"] = "1970-01-01T00:00:29Z"
    assert fetch_and_match_pull_request(
        json.dumps(committed).encode(), token="token", now_us=NOW_US,
        opener=lambda *_args, **_kwargs: _Response(
            live, url=pull_request_url(SOURCE_PR)),
    ) == live

    changed = copy.deepcopy(live)
    changed["merge_commit_sha"] = "f" * 40
    with pytest.raises(LiveRulesetMismatch, match="merge_commit_sha"):
        fetch_and_match_pull_request(
            json.dumps(committed).encode(), token="token", now_us=NOW_US,
            opener=lambda *_args, **_kwargs: _Response(
                changed, url=pull_request_url(SOURCE_PR)),
        )


@pytest.mark.parametrize(("document", "side"), [("committed", "base"), ("live", "head")])
def test_live_source_pr_binds_immutable_repository_id(document, side):
    committed = _source_pr()
    live = copy.deepcopy(committed)
    target = committed if document == "committed" else live
    target[side]["repo"]["id"] = 99
    with pytest.raises(LiveRulesetMismatch, match="SOURCE_PR_REPOSITORY_MISMATCH"):
        fetch_and_match_pull_request(
            json.dumps(committed).encode(), token="token", now_us=NOW_US,
            opener=lambda *_args, **_kwargs: _Response(
                live, url=pull_request_url(SOURCE_PR)),
        )


def test_live_source_pr_review_uses_fixed_endpoint_and_accepts_exact_head_approval():
    committed = _source_pr_review()
    live_review = copy.deepcopy(committed["review"])
    seen = {}

    def opener(request, *, timeout):
        seen["url"] = request.full_url
        seen["version"] = request.get_header("X-github-api-version")
        seen["cache_control"] = request.get_header("Cache-control")
        seen["timeout"] = timeout
        return _Response([live_review], url=pull_request_reviews_url(SOURCE_PR))

    assert fetch_and_match_pull_request_review(
        json.dumps(committed).encode(), token="token", now_us=NOW_US,
        opener=opener,
    ) == live_review
    assert seen == {
        "url": pull_request_reviews_url(SOURCE_PR),
        "version": "2022-11-28",
        "cache_control": "no-cache",
        "timeout": 20.0,
    }


def test_live_source_pr_review_rejects_approval_on_old_head():
    committed = _source_pr_review()
    old_head_review = copy.deepcopy(committed["review"])
    old_head_review["commit_id"] = "c" * 40
    with pytest.raises(
        LiveRulesetMismatch,
        match="LIVE_SOURCE_PR_REVIEW_FIELD_MISMATCH:commit_id",
    ):
        fetch_and_match_pull_request_review(
            json.dumps(committed).encode(), token="token", now_us=NOW_US,
            opener=lambda *_args, **_kwargs: _Response(
                [old_head_review], url=pull_request_reviews_url(SOURCE_PR)),
        )


def test_live_source_pr_review_rejects_non_approved_state():
    committed = _source_pr_review(state="COMMENTED")
    with pytest.raises(LiveRulesetMismatch, match="LIVE_SOURCE_PR_REVIEW_NOT_APPROVED"):
        fetch_and_match_pull_request_review(
            json.dumps(committed).encode(), token="token", now_us=NOW_US,
            opener=lambda *_args, **_kwargs: _Response(
                [copy.deepcopy(committed["review"])],
                url=pull_request_reviews_url(SOURCE_PR)),
        )


def test_live_source_pr_review_rejects_later_changes_requested_by_same_reviewer():
    committed = _source_pr_review()
    approval = copy.deepcopy(committed["review"])
    withdrawal = copy.deepcopy(approval)
    withdrawal.update(id=7002, state="CHANGES_REQUESTED")
    with pytest.raises(LiveRulesetMismatch, match="APPROVAL_SUPERSEDED"):
        fetch_and_match_pull_request_review(
            json.dumps(committed).encode(), token="token", now_us=NOW_US,
            opener=lambda *_args, **_kwargs: _Response(
                [approval, withdrawal], url=pull_request_reviews_url(SOURCE_PR)),
        )


@pytest.mark.parametrize(
    ("reviews", "expected_count"),
    [
        ([], 0),
        ([
            {**_source_pr_review()["review"], "id": 7002},
        ], 0),
        ([
            _source_pr_review()["review"],
            copy.deepcopy(_source_pr_review()["review"]),
        ], 2),
    ],
)
def test_live_source_pr_review_rejects_missing_or_duplicate_review_id(
    reviews, expected_count,
):
    committed = _source_pr_review()
    with pytest.raises(
        LiveRulesetMismatch,
        match=rf"LIVE_SOURCE_PR_REVIEW_ID_COUNT:7001:{expected_count}",
    ):
        fetch_and_match_pull_request_review(
            json.dumps(committed).encode(), token="token", now_us=NOW_US,
            opener=lambda *_args, **_kwargs: _Response(
                reviews, url=pull_request_reviews_url(SOURCE_PR)),
        )


def test_live_anchor_ref_must_resolve_to_annotated_tag_object():
    document = {
        "ref": "refs/tags/B00R_RECEIPT_ANCHOR_G2",
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


def _receipt_provider_documents() -> dict[str, object]:
    receipt_pr = 35
    merge_sha = "d" * 40
    head_sha = "e" * 40
    return {
        pull_request_url(receipt_pr): {
            "number": receipt_pr,
            "state": "closed",
            "merged": True,
            "merged_at": "1970-01-01T00:00:20Z",
            "merge_commit_sha": merge_sha,
            "base": {
                "ref": "main",
                "repo": {"full_name": REPOSITORY, "id": REPOSITORY_ID},
            },
            "head": {
                "sha": head_sha,
                "repo": {"full_name": REPOSITORY, "id": REPOSITORY_ID},
            },
            "user": {"login": "receipt-author", "type": "User"},
        },
        pull_request_reviews_url(receipt_pr): [{
            "id": 7001,
            "state": "APPROVED",
            "commit_id": head_sha,
            "submitted_at": "1970-01-01T00:00:19Z",
            "user": {"login": "djordi10", "type": "User"},
        }],
        collaborator_permission_url("djordi10"): {
            "permission": "admin",
            "role_name": "admin",
            "user": {"login": "djordi10", "type": "User"},
        },
        workflow_runs_for_head_url(head_sha): {
            "total_count": 1,
            "workflow_runs": [{
                "id": 9001,
                "head_sha": head_sha,
                "event": "pull_request",
                "status": "completed",
                "conclusion": "success",
                "run_attempt": 1,
                "created_at": "1970-01-01T00:00:17Z",
                "run_started_at": "1970-01-01T00:00:17Z",
                "updated_at": "1970-01-01T00:00:18Z",
                "path": ".github/workflows/ci.yml@main",
                "check_suite_id": 8001,
                "pull_requests": [{"number": receipt_pr}],
                "repository": {"full_name": REPOSITORY, "id": REPOSITORY_ID},
                "head_repository": {"full_name": REPOSITORY, "id": REPOSITORY_ID},
            }],
        },
        check_runs_for_head_url(head_sha): {
            "total_count": 1,
            "check_runs": [{
                "id": 8002,
                "name": "test-and-verify",
                "head_sha": head_sha,
                "status": "completed",
                "conclusion": "success",
                "started_at": "1970-01-01T00:00:17Z",
                "completed_at": "1970-01-01T00:00:18Z",
                "app": {"id": 15368},
                "check_suite": {"id": 8001},
            }],
        },
        compare_receipt_merge_to_main_url(merge_sha): {
            "status": "identical",
            "ahead_by": 0,
            "behind_by": 0,
            "base_commit": {"sha": merge_sha},
            "merge_base_commit": {"sha": merge_sha},
        },
    }


def _provider_opener(documents: dict[str, object]):
    def opener(request, *, timeout):
        assert timeout == 20.0
        return _Response(documents[request.full_url], url=request.full_url)
    return opener


def test_live_receipt_merge_binds_pr_review_actions_check_and_main_ancestry():
    documents = _receipt_provider_documents()
    proof = fetch_and_verify_receipt_merge(
        35,
        expected_merge_sha="d" * 40,
        expected_codeowner="djordi10",
        token="token",
        now_us=NOW_US,
        opener=_provider_opener(documents),
    )
    assert proof.pull_request == 35
    assert proof.head_sha == "e" * 40
    assert proof.merge_sha == "d" * 40
    assert proof.merged_at_us == 20_000_000
    assert proof.reviewer == "djordi10"
    assert proof.workflow_run_id == 9001
    assert proof.check_run_id == 8002


def _receipt_premerge_documents() -> dict[str, object]:
    documents = _receipt_provider_documents()
    pr = documents[pull_request_url(35)]
    pr.update({"state": "open", "merged": False, "merged_at": None, "draft": False})
    pr["base"]["sha"] = "c" * 40
    return documents


def _add_older_workflow_rerun(
    documents: dict[str, object], *, failing_layer: str, outcome: str
) -> None:
    workflows = documents[workflow_runs_for_head_url("e" * 40)]
    prior_workflow = workflows["workflow_runs"][0]
    workflow_terminal = failing_layer == "check" or outcome == "failure"
    workflows["workflow_runs"].append({
        **copy.deepcopy(prior_workflow),
        "id": 9000,
        "check_suite_id": 8000,
        "run_attempt": 2,
        "created_at": "1970-01-01T00:00:09Z",
        "run_started_at": "1970-01-01T00:00:19Z",
        "updated_at": "1970-01-01T00:00:19Z",
        "status": "completed" if workflow_terminal else "in_progress",
        "conclusion": (
            "success" if failing_layer == "check"
            else "failure" if outcome == "failure"
            else None
        ),
    })
    workflows["total_count"] = 2

    checks = documents[check_runs_for_head_url("e" * 40)]
    prior_check = checks["check_runs"][0]
    check_terminal = outcome == "failure"
    checks["check_runs"].append({
        **copy.deepcopy(prior_check),
        "id": 8000,
        "check_suite": {"id": 8000},
        "started_at": "1970-01-01T00:00:19Z",
        "status": "completed" if check_terminal else "in_progress",
        "conclusion": "failure" if check_terminal else None,
        "completed_at": "1970-01-01T00:00:19Z" if check_terminal else None,
    })
    checks["total_count"] = 2


def test_live_receipt_premerge_binds_open_pr_base_head_review_and_latest_ci():
    documents = _receipt_premerge_documents()
    proof = fetch_and_verify_receipt_head(
        35,
        expected_head_sha="e" * 40,
        expected_base_sha="c" * 40,
        expected_codeowner="djordi10",
        token="token",
        now_us=NOW_US,
        opener=_provider_opener(documents),
    )
    assert proof.base_sha == "c" * 40
    assert proof.head_sha == "e" * 40
    assert proof.review_id == 7001
    assert proof.workflow_run_id == 9001
    assert proof.check_run_id == 8002


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (lambda docs: docs[pull_request_url(35)]["base"].__setitem__("sha", "b" * 40),
         "PREMERGE_PR_IDENTITY_MISMATCH"),
        (lambda docs: docs[pull_request_url(35)]["head"].__setitem__("sha", "b" * 40),
         "PREMERGE_PR_IDENTITY_MISMATCH"),
        (lambda docs: docs[pull_request_url(35)].__setitem__("draft", True),
         "PREMERGE_PR_IDENTITY_MISMATCH"),
        (lambda docs: docs[pull_request_reviews_url(35)].clear(),
         "PREMERGE_EXACT_HEAD_CODEOWNER_APPROVAL_COUNT:0"),
        (lambda docs: docs[workflow_runs_for_head_url("e" * 40)][
            "workflow_runs"][0].__setitem__("conclusion", "failure"),
         "PREMERGE_LATEST_WORKFLOW_NOT_SUCCESS"),
        (lambda docs: docs[check_runs_for_head_url("e" * 40)][
            "check_runs"][0].__setitem__("conclusion", "failure"),
         "PREMERGE_LATEST_CHECK_NOT_SUCCESS"),
    ],
)
def test_live_receipt_premerge_rejects_false_green_paths(mutation, reason):
    documents = _receipt_premerge_documents()
    mutation(documents)
    with pytest.raises(LiveRulesetMismatch, match=reason):
        fetch_and_verify_receipt_head(
            35,
            expected_head_sha="e" * 40,
            expected_base_sha="c" * 40,
            expected_codeowner="djordi10",
            token="token",
            now_us=NOW_US,
            opener=_provider_opener(documents),
        )


@pytest.mark.parametrize("latest_kind", ["workflow", "check"])
def test_live_receipt_premerge_rejects_newer_pending_actions(latest_kind):
    documents = _receipt_premerge_documents()
    if latest_kind == "workflow":
        workflows = documents[workflow_runs_for_head_url("e" * 40)]
        workflows["workflow_runs"].append({
            **copy.deepcopy(workflows["workflow_runs"][0]),
            "id": 9002,
            "check_suite_id": 8003,
            "status": "in_progress",
            "conclusion": None,
            "created_at": "1970-01-01T00:00:19Z",
            "run_started_at": "1970-01-01T00:00:19Z",
            "updated_at": "1970-01-01T00:00:19Z",
        })
        workflows["total_count"] = 2
        reason = "PREMERGE_LATEST_WORKFLOW_NOT_SUCCESS"
    else:
        checks = documents[check_runs_for_head_url("e" * 40)]
        checks["check_runs"].append({
            **copy.deepcopy(checks["check_runs"][0]),
            "id": 8003,
            "status": "in_progress",
            "conclusion": None,
            "started_at": "1970-01-01T00:00:19Z",
            "completed_at": None,
        })
        checks["total_count"] = 2
        reason = "PREMERGE_LATEST_CHECK_NOT_SUCCESS"
    with pytest.raises(LiveRulesetMismatch, match=reason):
        fetch_and_verify_receipt_head(
            35,
            expected_head_sha="e" * 40,
            expected_base_sha="c" * 40,
            expected_codeowner="djordi10",
            token="token",
            now_us=NOW_US,
            opener=_provider_opener(documents),
        )


@pytest.mark.parametrize("failing_layer", ["workflow", "check"])
@pytest.mark.parametrize("outcome", ["pending", "failure"])
def test_live_receipt_premerge_rejects_older_run_current_rerun(
    failing_layer, outcome
):
    documents = _receipt_premerge_documents()
    _add_older_workflow_rerun(
        documents, failing_layer=failing_layer, outcome=outcome)
    reason = (
        "PREMERGE_LATEST_WORKFLOW_NOT_SUCCESS"
        if failing_layer == "workflow"
        else "PREMERGE_LATEST_CHECK_NOT_SUCCESS"
    )
    with pytest.raises(LiveRulesetMismatch, match=reason):
        fetch_and_verify_receipt_head(
            35,
            expected_head_sha="e" * 40,
            expected_base_sha="c" * 40,
            expected_codeowner="djordi10",
            token="token",
            now_us=NOW_US,
            opener=_provider_opener(documents),
        )


def test_live_receipt_merge_selects_latest_success_from_retained_provider_history():
    documents = _receipt_provider_documents()
    reviews = documents[pull_request_reviews_url(35)]
    reviews.insert(0, {
        **copy.deepcopy(reviews[0]),
        "id": 7000,
        "submitted_at": "1970-01-01T00:00:10Z",
    })
    workflows = documents[workflow_runs_for_head_url("e" * 40)]
    workflows["workflow_runs"].insert(0, {
        **copy.deepcopy(workflows["workflow_runs"][0]),
        "id": 9000,
        "check_suite_id": 8000,
        "created_at": "1970-01-01T00:00:09Z",
        "run_started_at": "1970-01-01T00:00:09Z",
        "updated_at": "1970-01-01T00:00:10Z",
    })
    workflows["total_count"] = 2
    checks = documents[check_runs_for_head_url("e" * 40)]
    checks["check_runs"].insert(0, {
        **copy.deepcopy(checks["check_runs"][0]),
        "id": 8000,
        "check_suite": {"id": 8000},
        "started_at": "1970-01-01T00:00:09Z",
        "completed_at": "1970-01-01T00:00:10Z",
    })
    checks["total_count"] = 2

    proof = fetch_and_verify_receipt_merge(
        35,
        expected_merge_sha="d" * 40,
        expected_codeowner="djordi10",
        token="token",
        now_us=NOW_US,
        opener=_provider_opener(documents),
    )
    assert proof.review_id == 7001
    assert proof.workflow_run_id == 9001
    assert proof.check_run_id == 8002


@pytest.mark.parametrize("latest_kind", ["workflow", "check"])
def test_live_receipt_merge_rejects_latest_relevant_actions_failure(latest_kind):
    documents = _receipt_provider_documents()
    if latest_kind == "workflow":
        workflows = documents[workflow_runs_for_head_url("e" * 40)]
        workflows["workflow_runs"].append({
            **copy.deepcopy(workflows["workflow_runs"][0]),
            "id": 9002,
            "check_suite_id": 8003,
            "conclusion": "failure",
            "updated_at": "1970-01-01T00:00:19Z",
        })
        workflows["total_count"] = 2
        reason = "LATEST_WORKFLOW_NOT_SUCCESS"
    else:
        checks = documents[check_runs_for_head_url("e" * 40)]
        checks["check_runs"].append({
            **copy.deepcopy(checks["check_runs"][0]),
            "id": 8003,
            "conclusion": "failure",
            "completed_at": "1970-01-01T00:00:19Z",
        })
        checks["total_count"] = 2
        reason = "LATEST_CHECK_NOT_SUCCESS"
    with pytest.raises(LiveRulesetMismatch, match=reason):
        fetch_and_verify_receipt_merge(
            35,
            expected_merge_sha="d" * 40,
            expected_codeowner="djordi10",
            token="token",
            now_us=NOW_US,
            opener=_provider_opener(documents),
        )


@pytest.mark.parametrize("latest_kind", ["workflow", "check"])
def test_live_receipt_merge_rejects_newer_pending_actions(latest_kind):
    documents = _receipt_provider_documents()
    if latest_kind == "workflow":
        workflows = documents[workflow_runs_for_head_url("e" * 40)]
        workflows["workflow_runs"].append({
            **copy.deepcopy(workflows["workflow_runs"][0]),
            "id": 9002,
            "check_suite_id": 8003,
            "status": "in_progress",
            "conclusion": None,
            "created_at": "1970-01-01T00:00:19Z",
            "run_started_at": "1970-01-01T00:00:19Z",
            "updated_at": "1970-01-01T00:00:19Z",
        })
        workflows["total_count"] = 2
        reason = "LATEST_WORKFLOW_NOT_SUCCESS"
    else:
        checks = documents[check_runs_for_head_url("e" * 40)]
        checks["check_runs"].append({
            **copy.deepcopy(checks["check_runs"][0]),
            "id": 8003,
            "status": "in_progress",
            "conclusion": None,
            "started_at": "1970-01-01T00:00:19Z",
            "completed_at": None,
        })
        checks["total_count"] = 2
        reason = "LATEST_CHECK_NOT_SUCCESS"
    with pytest.raises(LiveRulesetMismatch, match=reason):
        fetch_and_verify_receipt_merge(
            35,
            expected_merge_sha="d" * 40,
            expected_codeowner="djordi10",
            token="token",
            now_us=NOW_US,
            opener=_provider_opener(documents),
        )


@pytest.mark.parametrize("failing_layer", ["workflow", "check"])
@pytest.mark.parametrize("outcome", ["pending", "failure"])
def test_live_receipt_merge_rejects_older_run_current_rerun(failing_layer, outcome):
    documents = _receipt_provider_documents()
    _add_older_workflow_rerun(
        documents, failing_layer=failing_layer, outcome=outcome)
    reason = (
        "LATEST_WORKFLOW_NOT_SUCCESS"
        if failing_layer == "workflow"
        else "LATEST_CHECK_NOT_SUCCESS"
    )
    with pytest.raises(LiveRulesetMismatch, match=reason):
        fetch_and_verify_receipt_merge(
            35,
            expected_merge_sha="d" * 40,
            expected_codeowner="djordi10",
            token="token",
            now_us=NOW_US,
            opener=_provider_opener(documents),
        )


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (lambda docs: docs[pull_request_url(35)]["base"].__setitem__("ref", "attack"),
         "RECEIPT_PR_IDENTITY"),
        (lambda docs: docs[pull_request_reviews_url(35)][0].__setitem__(
            "commit_id", "c" * 40), "APPROVAL_COUNT:0"),
        (lambda docs: docs[pull_request_url(35)]["user"].__setitem__(
            "login", "djordi10"), "REVIEW_NOT_INDEPENDENT"),
        (lambda docs: docs[pull_request_reviews_url(35)][0].__setitem__(
            "submitted_at", "1970-01-01T00:00:20Z"), "REVIEW_NOT_BEFORE_MERGE"),
        (lambda docs: docs[pull_request_reviews_url(35)].append({
            **copy.deepcopy(docs[pull_request_reviews_url(35)][0]),
            "id": 7002,
            "state": "CHANGES_REQUESTED",
        }), "APPROVAL_SUPERSEDED"),
        (lambda docs: docs[workflow_runs_for_head_url("e" * 40)][
            "workflow_runs"][0].__setitem__("path", ".github/workflows/ci.yml"),
         "RELEVANT_WORKFLOW_COUNT:0"),
        (lambda docs: docs[workflow_runs_for_head_url("e" * 40)].__setitem__(
            "total_count", 2), "WORKFLOW_RUNS_MALFORMED"),
        (lambda docs: docs[workflow_runs_for_head_url("e" * 40)][
            "workflow_runs"][0].__setitem__("conclusion", "failure"),
         "LATEST_WORKFLOW_NOT_SUCCESS"),
        (lambda docs: docs[workflow_runs_for_head_url("e" * 40)][
            "workflow_runs"][0].__setitem__(
                "updated_at", "1970-01-01T00:00:20Z"),
         "LATEST_WORKFLOW_NOT_BEFORE_MERGE"),
        (lambda docs: docs[check_runs_for_head_url("e" * 40)][
            "check_runs"][0]["app"].__setitem__("id", 1),
         "RELEVANT_CHECK_COUNT:0"),
        (lambda docs: docs[check_runs_for_head_url("e" * 40)][
            "check_runs"][0].__setitem__("name", "CI / test-and-verify"),
         "RELEVANT_CHECK_COUNT:0"),
        (lambda docs: docs[check_runs_for_head_url("e" * 40)][
            "check_runs"][0].__setitem__(
                "completed_at", "1970-01-01T00:00:20Z"),
         "LATEST_CHECK_NOT_BEFORE_MERGE"),
        (lambda docs: docs[check_runs_for_head_url("e" * 40)].__setitem__(
            "total_count", 2), "CHECK_RUNS_MALFORMED"),
        (lambda docs: docs[compare_receipt_merge_to_main_url("d" * 40)].__setitem__(
            "status", "diverged"), "MERGE_NOT_ON_MAIN"),
    ],
)
def test_live_receipt_merge_rejects_false_green_provider_paths(mutation, reason):
    documents = _receipt_provider_documents()
    mutation(documents)
    with pytest.raises(LiveRulesetMismatch, match=reason):
        fetch_and_verify_receipt_merge(
            35,
            expected_merge_sha="d" * 40,
            expected_codeowner="djordi10",
            token="token",
            now_us=NOW_US,
            opener=_provider_opener(documents),
        )
