"""Adversarial tests for the pre-anchor G2 tag-ruleset gate."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import subprocess

import pytest

from tools.github_ruleset_live import (
    LiveRulesetMismatch, LiveRulesetUnavailable, ruleset_url)
from tools import validate_b00r_anchor
from tools import validate_b00r_tag_ruleset


ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
NOW_US = 30_000_000
DATE = "Thu, 01 Jan 1970 00:00:30 GMT"


def _git(root: pathlib.Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def _ruleset() -> dict:
    return {
        "id": 1001,
        "name": "b00r-g2-receipt-anchor",
        "target": "tag",
        "source_type": "Repository",
        "source": "TriadAgentic/TriadOrigin",
        "current_user_can_bypass": "never",
        "enforcement": "active",
        "node_id": "RRS_anchor1001",
        "_links": {
            "self": {
                "href": (
                    "https://api.github.com/repos/TriadAgentic/TriadOrigin/rulesets/1001"
                )
            },
            "html": {
                "href": "https://github.com/TriadAgentic/TriadOrigin/rules/1001"
            },
        },
        "created_at": "1970-01-01T00:00:05Z",
        "updated_at": "1970-01-01T00:00:10Z",
        "conditions": {
            "ref_name": {
                "include": ["refs/tags/B00R_RECEIPT_ANCHOR_G2"],
                "exclude": [],
            }
        },
        "bypass_actors": [],
        "rules": [{"type": "update"}, {"type": "deletion"}],
    }


def _repo(root: pathlib.Path, document: dict | None = None) -> tuple[str, pathlib.Path, str]:
    root.mkdir(parents=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "pre-anchor-test@example.invalid")
    _git(root, "config", "user.name", "Pre Anchor Test")
    path = root / validate_b00r_anchor.DEFAULT_RULESET
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(_ruleset() if document is None else document, sort_keys=True),
        encoding="utf-8",
    )
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "receipt PR head")
    head = _git(root, "rev-parse", "HEAD")
    return head, path, hashlib.sha256(path.read_bytes()).hexdigest()


class _Response:
    def __init__(self, document: dict):
        self.status = 200
        self._body = json.dumps(document).encode()
        self.headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Date": DATE,
            "X-GitHub-Request-Id": "REQ:tag:1001",
        }

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def getcode(self):
        return self.status

    def geturl(self):
        return ruleset_url(1001)

    def read(self, limit: int):
        return self._body[:limit]


def _verify(
    root: pathlib.Path,
    head: str,
    path: pathlib.Path,
    pin: str | None,
    **kwargs,
) -> str:
    return validate_b00r_tag_ruleset.verify(
        root=root,
        expected_head=head,
        ruleset_path=path,
        ruleset_pin=pin,
        now_us=NOW_US,
        **kwargs,
    )


def test_pre_anchor_gate_passes_without_receipt_merge_or_anchor_tag(tmp_path):
    root = tmp_path / "repo"
    head, path, pin = _repo(root)

    assert _git(root, "rev-list", "--count", "HEAD") == "1"
    assert _git(root, "rev-list", "--parents", "-n", "1", "HEAD").split() == [head]
    assert _git(root, "tag", "--list", validate_b00r_anchor.TAG_NAME) == ""
    assert _verify(root, head, path, pin) == pin


def test_pre_anchor_gate_requires_external_pin_exact_head_and_clean_tree(tmp_path):
    root = tmp_path / "repo"
    head, path, pin = _repo(root)

    with pytest.raises(validate_b00r_anchor.AnchorError, match="PIN_ABSENT"):
        _verify(root, head, path, None)
    with pytest.raises(validate_b00r_anchor.AnchorError, match="PIN_INVALID"):
        _verify(root, head, path, "0" * 64)
    with pytest.raises(validate_b00r_anchor.AnchorError, match="PIN_MISMATCH"):
        _verify(root, head, path, "f" * 64)
    with pytest.raises(validate_b00r_anchor.AnchorError, match="EXPECTED_HEAD_MISMATCH"):
        _verify(root, "f" * 40, path, pin)

    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(validate_b00r_anchor.AnchorError, match="WORKTREE_NOT_CLEAN"):
        _verify(root, head, path, pin)


def test_pre_anchor_cli_accepts_only_external_pin_on_relative_root(
    tmp_path, monkeypatch, capsys
):
    root = tmp_path / "repo"
    head, _path, pin = _repo(root)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(validate_b00r_anchor.PIN_ENV, pin)

    assert validate_b00r_tag_ruleset.main([
        "--root", "repo", "--expected-head", head, "--now-us", str(NOW_US),
    ]) == 0
    assert "OK: pre-anchor G2 tag ruleset" in capsys.readouterr().out


def test_tag_validator_clis_reject_pin_conflicting_with_protected_environment(
    monkeypatch, capsys
):
    monkeypatch.setenv(validate_b00r_anchor.PIN_ENV, "b" * 64)
    common = [
        "--expected-head", "a" * 40,
        "--now-us", str(NOW_US),
        "--ruleset-pin", "c" * 64,
    ]
    assert validate_b00r_tag_ruleset.main(common) == 1
    assert "CONFLICTING_CLI_AND_PROTECTED_TAG_RULESET_PINS" in capsys.readouterr().err
    assert validate_b00r_anchor.main([*common, "--receipt-pr", "35"]) == 1
    assert "CONFLICTING_CLI_AND_PROTECTED_TAG_RULESET_PINS" in capsys.readouterr().err


def test_pre_anchor_gate_requires_canonical_path_and_committed_blob_match(
    tmp_path, monkeypatch
):
    root = tmp_path / "repo"
    head, path, pin = _repo(root)
    with pytest.raises(validate_b00r_anchor.AnchorError, match="PATH_NOT_CANONICAL"):
        _verify(root, head, root / "tag_ruleset.provider.json", pin)

    real_git = validate_b00r_tag_ruleset._git

    def mismatched_blob(repo, *args, **kwargs):
        if args[:2] == ("hash-object", "--no-filters"):
            return b"f" * 40 + b"\n"
        return real_git(repo, *args, **kwargs)

    monkeypatch.setattr(validate_b00r_tag_ruleset, "_git", mismatched_blob)
    with pytest.raises(validate_b00r_anchor.AnchorError, match="WORKTREE_BLOB_DIFFERS"):
        _verify(root, head, path, pin)


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (lambda doc: doc.__setitem__("target", "branch"), "WRONG_TARGET"),
        (lambda doc: doc.__setitem__("enforcement", "evaluate"), "NOT_ACTIVE"),
        (lambda doc: doc.__setitem__("captured_from", "handwritten"),
         "PROVIDER_FIELDS_MISMATCH"),
        (lambda doc: doc.__setitem__("source", "attacker/fork"), "SOURCE_MISMATCH"),
        (lambda doc: doc.__setitem__("node_id", None), "NODE_ID_INVALID"),
        (lambda doc: doc.pop("_links"), "PROVIDER_FIELDS_MISMATCH"),
        (lambda doc: doc["_links"]["self"].__setitem__("note", "handwritten"),
         "PROVIDER_LINKS_MISMATCH"),
        (lambda doc: doc.__setitem__("current_user_can_bypass", "always"),
         "CURRENT_USER_BYPASS_NOT_NEVER"),
        (lambda doc: doc.__setitem__("bypass_actors", [{"actor_id": 1}]),
         "BYPASS_ACTORS_PRESENT"),
        (lambda doc: doc["conditions"]["ref_name"].__setitem__("exclude", ["~ALL"]),
         "SCOPE_NOT_EXACT"),
        (lambda doc: doc["conditions"]["ref_name"].pop("exclude"), "SCOPE_NOT_EXACT"),
        (lambda doc: doc["conditions"].__setitem__("repository_name", {}),
         "SCOPE_NOT_EXACT"),
        (lambda doc: doc["rules"].pop(), "RULE_SET_NOT_EXACT"),
        (lambda doc: doc["rules"][0].__setitem__("note", "handwritten"),
         "RULES_NOT_ARRAY"),
        (lambda doc: doc["rules"].append({"type": "update"}),
         "RULE_SET_NOT_EXACT"),
        (lambda doc: doc["rules"].append({"type": "creation"}),
         "RULE_SET_NOT_EXACT"),
        (lambda doc: doc.__setitem__("rules", [{"type": "deletion"}, "update"]),
         "RULES_NOT_ARRAY"),
    ],
)
def test_pre_anchor_gate_rejects_non_provider_or_unsafe_ruleset(
    tmp_path, mutation, reason
):
    document = _ruleset()
    mutation(document)
    root = tmp_path / reason
    head, path, pin = _repo(root, document)
    with pytest.raises(validate_b00r_anchor.AnchorError, match=reason):
        _verify(root, head, path, pin)


@pytest.mark.parametrize(
    ("created_at", "updated_at"),
    [
        ("1970-01-01T00:00:11Z", "1970-01-01T00:00:10Z"),
        ("1970-01-01T00:00:05Z", "1970-01-01T00:00:30Z"),
        ("1970-01-01T00:00:05Z", "1970-01-01T00:00:31Z"),
    ],
)
def test_pre_anchor_gate_requires_created_before_update_before_trusted_now(
    tmp_path, created_at, updated_at
):
    document = _ruleset()
    document["created_at"] = created_at
    document["updated_at"] = updated_at
    root = tmp_path / updated_at.replace(":", "-")
    head, path, pin = _repo(root, document)
    with pytest.raises(
        validate_b00r_anchor.AnchorError,
        match="TAG_RULESET_NOT_EFFECTIVE_BEFORE_TRUSTED_NOW",
    ):
        _verify(root, head, path, pin)


def test_strict_live_uses_fixed_endpoint_and_allows_hidden_bypass_pre_anchor(
    tmp_path, monkeypatch
):
    root = tmp_path / "repo"
    head, path, pin = _repo(root)
    live = _ruleset()
    live.pop("bypass_actors")
    seen = {}

    def strict_match(raw, **kwargs):
        seen["require_bypass_visibility"] = kwargs["require_bypass_visibility"]

        def opener(request, *, timeout):
            seen["url"] = request.full_url
            seen["authorization"] = request.get_header("Authorization")
            seen["timeout"] = timeout
            return _Response(live)

        from tools.github_ruleset_live import fetch_and_match_live_ruleset

        return fetch_and_match_live_ruleset(raw, opener=opener, **kwargs)

    monkeypatch.setattr(
        validate_b00r_tag_ruleset, "fetch_and_match_live_ruleset", strict_match)
    assert _verify(
        root, head, path, pin, strict_live=True, github_token="test-token"
    ) == pin
    assert seen == {
        "require_bypass_visibility": False,
        "url": ruleset_url(1001),
        "authorization": "Bearer test-token",
        "timeout": 20.0,
    }


def test_strict_live_rejects_visible_bypass_and_requires_token(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    head, path, pin = _repo(root)

    with pytest.raises(LiveRulesetUnavailable, match="TOKEN_ABSENT"):
        _verify(root, head, path, pin, strict_live=True, github_token=None)

    live = copy.deepcopy(_ruleset())
    live["bypass_actors"] = [{"actor_id": 1, "actor_type": "OrganizationAdmin"}]

    def strict_match(raw, **kwargs):
        from tools.github_ruleset_live import fetch_and_match_live_ruleset

        return fetch_and_match_live_ruleset(
            raw, opener=lambda *_args, **_kwargs: _Response(live), **kwargs
        )

    monkeypatch.setattr(
        validate_b00r_tag_ruleset, "fetch_and_match_live_ruleset", strict_match)
    with pytest.raises(LiveRulesetMismatch, match="LIVE_RULESET_BYPASS_NOT_EMPTY"):
        _verify(
            root, head, path, pin, strict_live=True, github_token="test-token"
        )


def test_privileged_premerge_requires_visible_empty_tag_bypass_state(
    tmp_path, monkeypatch
):
    root = tmp_path / "repo"
    _head, path, pin = _repo(root)
    receipt = root / "evidence/receipts/B00R.g2.receipt.v3.json"
    receipt.parent.mkdir(parents=True)
    receipt.write_bytes(json.dumps({
        "payload": {"observed_at_us": 20_000_000, "emitted_at_us": 21_000_000},
    }, sort_keys=True, separators=(",", ":")).encode())
    _git(root, "add", str(receipt.relative_to(root)))
    _git(root, "commit", "-qm", "receipt head")
    head = _git(root, "rev-parse", "HEAD")
    seen = {}

    def match(_raw, **kwargs):
        seen.update(kwargs)
        return object()

    monkeypatch.setattr(validate_b00r_tag_ruleset, "fetch_and_match_live_ruleset", match)
    assert _verify(
        root, head, path, pin,
        strict_live=True,
        require_bypass_visibility=True,
        github_token="test-token",
        receipt_path=receipt,
    ) == pin
    assert seen["require_bypass_visibility"] is True
    with pytest.raises(
        validate_b00r_anchor.AnchorError,
        match="BYPASS_VISIBILITY_REQUIRES_STRICT_LIVE",
    ):
        _verify(root, head, path, pin, require_bypass_visibility=True, receipt_path=receipt)

    receipt.write_bytes(json.dumps({
        "payload": {"observed_at_us": 10_000_000, "emitted_at_us": 21_000_000},
    }, sort_keys=True, separators=(",", ":")).encode())
    _git(root, "add", str(receipt.relative_to(root)))
    _git(root, "commit", "-qm", "stale tag capture chronology")
    stale_head = _git(root, "rev-parse", "HEAD")
    with pytest.raises(
        validate_b00r_anchor.AnchorError,
        match="TAG_RULESET_NOT_EFFECTIVE_BEFORE_RECEIPT_OBSERVATION",
    ):
        _verify(
            root, stale_head, path, pin,
            strict_live=True,
            require_bypass_visibility=True,
            github_token="test-token",
            receipt_path=receipt,
        )


def test_terminal_anchor_remains_stricter_than_pre_anchor():
    source = pathlib.Path(validate_b00r_anchor.__file__).read_text(encoding="utf-8")
    assert "TAG_RULESET_NOT_EFFECTIVE_BEFORE_RECEIPT_MERGE" in source
    assert "require_bypass_visibility=True" in source
    assert "fetch_anchor_tag_object_sha" in source


def test_receipt_head_ci_runs_pinned_live_pre_anchor_validation():
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "Pre-anchor G2 tag ruleset validation" in ci
    assert "B00R_G2_TAG_RULESET_SHA256: ${{ vars.B00R_G2_TAG_RULESET_SHA256 }}" in ci
    assert "python tools/validate_b00r_tag_ruleset.py" in ci
    assert "--ruleset evidence/B00R_G2/tag_ruleset.provider.json" in ci
    assert "--ruleset-pin \"$B00R_G2_TAG_RULESET_SHA256\"" in ci
    assert "RECEIPT_PATH: ${{ steps.milestone_role.outputs.receipt_path }}" in ci
    assert "--receipt \"$RECEIPT_PATH\"" in ci
    assert "--strict-live" in ci
