"""Falsification tests for exact-head, role, evidence, history, and CODEOWNERS gates."""

from __future__ import annotations

import hashlib
import json
import pathlib
import os
import subprocess
from types import SimpleNamespace

import pytest

from tools import b00r_gate
from tools import build_evidence_manifest as evidence_manifest
from tools import classify_milestone_pr as classifier
from tools import verify_codeowners
from tools import verify_historical_evidence
from tools import validate_b00r_anchor


def _git(root: pathlib.Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def _git_at(root: pathlib.Path, instant: str, *args: str) -> str:
    env = dict(os.environ)
    env["GIT_AUTHOR_DATE"] = instant
    env["GIT_COMMITTER_DATE"] = instant
    proc = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True,
        check=False, env=env)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def _init_repo(root: pathlib.Path) -> str:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "b00r-test@example.invalid")
    _git(root, "config", "user.name", "B00R Test")
    (root / "src").mkdir()
    (root / "src" / "baseline.txt").write_text("baseline\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "baseline")
    return _git(root, "rev-parse", "HEAD")


def test_exact_head_accepts_only_the_checked_out_canonical_sha(tmp_path):
    head = _init_repo(tmp_path / "repo")
    assert b00r_gate.verify_expected_head(head, tmp_path / "repo") == head
    assert b00r_gate.verify_final_repository_state(head, tmp_path / "repo") == head
    (tmp_path / "repo" / "untracked.txt").write_text("dirty\n")
    with pytest.raises(b00r_gate.HeadIdentityError, match="WORKTREE_NOT_CLEAN"):
        b00r_gate.verify_final_repository_state(head, tmp_path / "repo")
    with pytest.raises(b00r_gate.HeadIdentityError, match="NOT_CANONICAL_HEX40"):
        b00r_gate.verify_expected_head("HEAD", tmp_path / "repo")
    with pytest.raises(b00r_gate.HeadIdentityError, match="ALL_ZERO_UNAVAILABLE"):
        b00r_gate.verify_expected_head("0" * 40, tmp_path / "repo")
    with pytest.raises(b00r_gate.HeadIdentityError, match="EXPECTED_HEAD_MISMATCH"):
        b00r_gate.verify_expected_head("f" * 40, tmp_path / "repo")


def test_terminal_receipt_base_is_derived_from_two_parent_merge(tmp_path):
    repo = tmp_path / "repo"
    base = _init_repo(repo)
    main_branch = _git(repo, "branch", "--show-current")
    _git(repo, "checkout", "-qb", "receipt")
    (repo / "receipt.txt").write_text("receipt\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "receipt head")
    receipt_head = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", main_branch)
    _git(repo, "merge", "--no-ff", "-qm", "receipt merge", "receipt")
    merge = _git(repo, "rev-parse", "HEAD")
    assert b00r_gate.verify_receipt_merge_base(merge, base, repo) == (base, receipt_head)
    with pytest.raises(b00r_gate.HeadIdentityError, match="RECEIPT_BASE_MISMATCH"):
        b00r_gate.verify_receipt_merge_base(merge, receipt_head, repo)
    with pytest.raises(
        b00r_gate.HeadIdentityError, match="RECEIPT_HEAD_NOT_EXACT_TWO_PARENT_MERGE"
    ):
        b00r_gate.verify_receipt_merge_base(receipt_head, base, repo)


def test_receipt_mode_requires_expected_head_and_base_sha():
    with pytest.raises(SystemExit) as missing_head:
        b00r_gate.main([
            "--mode", "receipt", "--base-sha", "a" * 40, "--receipt-pr", "35",
            "--now-us", "1000000",
        ])
    assert missing_head.value.code == 2
    with pytest.raises(SystemExit) as missing_base:
        b00r_gate.main([
            "--mode", "receipt", "--expected-head", "a" * 40, "--receipt-pr", "35",
            "--now-us", "1000000",
        ])
    assert missing_base.value.code == 2
    with pytest.raises(SystemExit) as zero_base:
        b00r_gate.main([
            "--mode", "receipt", "--expected-head", "a" * 40,
            "--base-sha", "0" * 40, "--receipt-pr", "35", "--now-us", "1000000",
        ])
    assert zero_base.value.code == 2
    with pytest.raises(SystemExit) as missing_receipt_pr:
        b00r_gate.main([
            "--mode", "receipt", "--expected-head", "a" * 40,
            "--base-sha", "b" * 40, "--now-us", "1000000",
        ])
    assert missing_receipt_pr.value.code == 2
    with pytest.raises(SystemExit) as source_missing_head:
        b00r_gate.main(["--mode", "source", "--now-us", "1000000"])
    assert source_missing_head.value.code == 2
    with pytest.raises(SystemExit) as source_with_base:
        b00r_gate.main([
            "--mode", "source", "--expected-head", "a" * 40,
            "--base-sha", "b" * 40, "--now-us", "1000000",
        ])
    assert source_with_base.value.code == 2


def test_source_mode_can_never_return_terminal_pass():
    assert b00r_gate.overall_result("source", {"all_engineering": "PASS"}) == "BLOCKED"
    assert b00r_gate.overall_result("source", {"broken": "FAIL"}) == "FAIL"
    assert b00r_gate.overall_result("receipt", {"all_closure": "PASS"}) == (
        "PASS_REPOSITORY_SAFE_HOLD"
    )


def test_classifier_accepts_one_canonical_append_only_receipt():
    result = classifier.classify_changes(
        [
            classifier.Change("A", classifier.EXPECTED_RECEIPT),
            classifier.Change("A", classifier.EXPECTED_MANIFEST),
            classifier.Change("A", "evidence/B00R_G2/test.log"),
        ]
    )
    assert result.role == "RECEIPT"
    assert result.receipt_path == classifier.EXPECTED_RECEIPT
    assert result.manifest_path == classifier.EXPECTED_MANIFEST


@pytest.mark.parametrize(
    "changes,code",
    [
        ([], "PR_ROLE_EMPTY"),
        ([classifier.Change("A", "evidence/receipts/B00R.dsse.json")],
         "UNSUPPORTED_DSSE_ENVELOPE"),
        ([classifier.Change("M", "evidence/receipts/B00.json")],
         "HISTORICAL_EVIDENCE_IMMUTABLE"),
        ([classifier.Change("A", "evidence/receipts/B00R.receipt.v3.json")],
         "HISTORICAL_EVIDENCE_IMMUTABLE"),
        ([classifier.Change("D", classifier.EXPECTED_RECEIPT)], "RECEIPT_NOT_APPEND_ONLY"),
        ([classifier.Change("A", classifier.EXPECTED_RECEIPT),
          classifier.Change("A", "evidence/receipts/B01C.receipt.v3.json")],
         "UNEXPECTED_RECEIPT_PATH"),
        ([classifier.Change("A", classifier.EXPECTED_RECEIPT),
          classifier.Change("A", "evidence/B01C/run.log")], "CROSS_MILESTONE_EVIDENCE"),
        ([classifier.Change("M", "src/x.py"),
          classifier.Change("A", classifier.EXPECTED_RECEIPT)], "PR_ROLE_MIXED"),
    ],
)
def test_classifier_rejects_ambiguous_or_mutating_receipt_changes(changes, code):
    with pytest.raises(classifier.ClassificationError, match=code):
        classifier.classify_changes(changes)


def test_git_classifier_binds_exact_event_shas_and_writes_outputs(tmp_path):
    repo = tmp_path / "repo"
    base = _init_repo(repo)
    (repo / "evidence" / "receipts").mkdir(parents=True)
    (repo / classifier.EXPECTED_RECEIPT).write_text("{}\n", encoding="utf-8")
    (repo / "evidence" / "B00R_G2").mkdir()
    (repo / classifier.EXPECTED_MANIFEST).write_text("{}\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "receipt")
    head = _git(repo, "rev-parse", "HEAD")
    changes = classifier.changes_from_git(repo, base, head)
    assert classifier.classify_changes(changes).role == "RECEIPT"

    output = tmp_path / "github-output"
    assert classifier.main([
        "--repo", str(repo), "--base-sha", base, "--head-sha", head,
        "--github-output", str(output),
    ]) == 0
    values = dict(line.split("=", 1) for line in output.read_text().splitlines())
    assert values == {
        "role": "RECEIPT",
        "milestone": "B00R",
        "receipt_path": classifier.EXPECTED_RECEIPT,
        "manifest_path": classifier.EXPECTED_MANIFEST,
    }

    _git(repo, "checkout", "-q", base)
    with pytest.raises(classifier.ClassificationError, match="CHECKOUT_HEAD_MISMATCH"):
        classifier.changes_from_git(repo, base, head)


def test_git_classifier_handles_main_push_merge_commit_from_before_to_after(tmp_path):
    repo = tmp_path / "repo"
    before = _init_repo(repo)
    main_branch = _git(repo, "branch", "--show-current")
    _git(repo, "checkout", "-qb", "receipt-work")
    (repo / "evidence" / "receipts").mkdir(parents=True)
    (repo / classifier.EXPECTED_RECEIPT).write_text("{}\n", encoding="utf-8")
    (repo / "evidence" / "B00R_G2").mkdir()
    (repo / classifier.EXPECTED_MANIFEST).write_text("{}\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "receipt evidence")
    _git(repo, "checkout", "-q", main_branch)
    _git(repo, "merge", "--no-ff", "-qm", "merge receipt", "receipt-work")
    after = _git(repo, "rev-parse", "HEAD")
    changes = classifier.changes_from_git(repo, before, after)
    assert classifier.classify_changes(changes).role == "RECEIPT"


def test_git_classifier_rejects_all_zero_push_before_sha(tmp_path):
    repo = tmp_path / "repo"
    head = _init_repo(repo)
    with pytest.raises(classifier.ClassificationError, match="BASE_SHA_ALL_ZERO_UNAVAILABLE"):
        classifier.changes_from_git(repo, "0" * 40, head)


def _write_closed_evidence(root: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    closed = root / "evidence" / "B00R_G2"
    closed.mkdir(parents=True)
    spec = closed / "spec.json"
    log = closed / "run.log"
    entries = [
        {"path": "evidence/B00R_G2/spec.json", "role": "SPEC"},
        {"path": "evidence/B00R_G2/run.log", "role": "RUN_LOG"},
    ]
    spec.write_text(json.dumps({"entries": entries}), encoding="utf-8")
    log.write_text("green\n", encoding="utf-8")
    manifest = closed / "evidence_manifest.json"
    assert evidence_manifest.main([
        "--build", str(spec), "--root", str(root), "--out", str(manifest),
        "--closed-root", "evidence/B00R_G2",
    ]) == 0
    return closed, manifest


def test_evidence_manifest_membership_is_closed(tmp_path):
    root = tmp_path / "repo"
    closed, manifest = _write_closed_evidence(root)
    assert evidence_manifest.main([
        "--verify", str(manifest), "--root", str(root),
        "--closed-root", "evidence/B00R_G2",
    ]) == 0
    (closed / "omitted.log").write_text("not declared\n", encoding="utf-8")
    assert evidence_manifest.main([
        "--verify", str(manifest), "--root", str(root),
        "--closed-root", "evidence/B00R_G2",
    ]) == 1


def test_evidence_manifest_builder_preserves_explicit_role_uniqueness(tmp_path):
    root = tmp_path / "repo"
    closed = root / "evidence" / "B00R_G2"
    closed.mkdir(parents=True)
    spec = closed / "spec.json"
    record = closed / "source_pr.provider.raw.json"
    repeatable = closed / "repeatable.log"
    entries = [
        {"path": "evidence/B00R_G2/spec.json", "role": "SPEC"},
        {
            "path": "evidence/B00R_G2/repeatable.log",
            "role": "REPEATABLE_LOG",
            "role_unique": False,
        },
        {
            "path": "evidence/B00R_G2/source_pr.provider.raw.json",
            "role": "SOURCE_PR_PROVIDER_RECORD",
            "role_unique": True,
        },
    ]
    spec.write_text(json.dumps({"entries": entries}), encoding="utf-8")
    record.write_text("{}\n", encoding="utf-8")
    repeatable.write_text("repeatable\n", encoding="utf-8")
    manifest = closed / "evidence_manifest.json"

    assert evidence_manifest.main([
        "--build", str(spec), "--root", str(root), "--out", str(manifest),
        "--closed-root", "evidence/B00R_G2",
    ]) == 0
    built = json.loads(manifest.read_text(encoding="utf-8"))
    by_role = {entry["role"]: entry for entry in built["entries"]}
    assert "role_unique" not in by_role["SPEC"]
    assert by_role["REPEATABLE_LOG"]["role_unique"] is False
    assert by_role["SOURCE_PR_PROVIDER_RECORD"]["role_unique"] is True
    assert evidence_manifest.main([
        "--verify", str(manifest), "--root", str(root),
        "--closed-root", "evidence/B00R_G2",
    ]) == 0

    for invalid in ("false", 1, None):
        entries[1]["role_unique"] = invalid
        spec.write_text(json.dumps({"entries": entries}), encoding="utf-8")
        assert evidence_manifest.main([
            "--build", str(spec), "--root", str(root), "--out", str(manifest),
            "--closed-root", "evidence/B00R_G2",
        ]) == 1

    entries[1]["role_unique"] = False
    entries[1]["role_uniqe"] = True
    spec.write_text(json.dumps({"entries": entries}), encoding="utf-8")
    assert evidence_manifest.main([
        "--build", str(spec), "--root", str(root), "--out", str(manifest),
        "--closed-root", "evidence/B00R_G2",
    ]) == 1


def test_receipt_ci_and_terminal_orchestrator_require_semantic_clean_runner_bundle():
    ci = (b00r_gate.ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "Semantic B00R clean-runner bundle" in ci
    assert "python tools/b00r_clean_runner.py verify" in ci
    assert "--expected-head \"$EXPECTED_HEAD\"" in ci

    from argparse import Namespace

    args = Namespace(
        base_sha="b" * 40,
        expected_head="a" * 40,
        manifest=b00r_gate.CANONICAL_MANIFEST,
        receipt=b00r_gate.CANONICAL_RECEIPT,
        now_us=1_000_000,
    )
    gates = b00r_gate._receipt_gates(args)
    semantic = [gate for gate in gates if gate.gate_id == "clean_runner_bundle"]
    assert len(semantic) == 1
    command = semantic[0].argv
    assert "tools/b00r_clean_runner.py" in command
    assert command[command.index("--expected-head") + 1] == "a" * 40
    assert command[command.index("--receipt") + 1] == b00r_gate.CANONICAL_RECEIPT


def test_evidence_manifest_rejects_count_and_media_type_drift(tmp_path):
    root = tmp_path / "repo"
    _closed, manifest = _write_closed_evidence(root)
    doc = json.loads(manifest.read_text())
    doc["entry_count"] += 1
    manifest.write_text(json.dumps(doc), encoding="utf-8")
    assert evidence_manifest.main([
        "--verify", str(manifest), "--root", str(root),
        "--closed-root", "evidence/B00R_G2",
    ]) == 1

    _closed, manifest = _write_closed_evidence(tmp_path / "second")
    doc = json.loads(manifest.read_text())
    doc["entries"][0]["media_type"] = "text/plain"
    manifest.write_text(json.dumps(doc), encoding="utf-8")
    assert evidence_manifest.main([
        "--verify", str(manifest), "--root", str(tmp_path / "second"),
        "--closed-root", "evidence/B00R_G2",
    ]) == 1


def test_evidence_manifest_rejects_an_undeclared_symlink(tmp_path):
    root = tmp_path / "repo"
    closed, manifest = _write_closed_evidence(root)
    try:
        (closed / "alias.log").symlink_to(closed / "run.log")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    assert evidence_manifest.main([
        "--verify", str(manifest), "--root", str(root),
        "--closed-root", "evidence/B00R_G2",
    ]) == 1


def _historical_repo(root: pathlib.Path) -> tuple[str, pathlib.Path]:
    root.mkdir(parents=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "history-test@example.invalid")
    _git(root, "config", "user.name", "History Test")
    entries = []
    vocabulary = ["INVALIDATED", "BUILT_ON_INVALID_ANCESTRY"]
    for index, rel in enumerate(sorted(verify_historical_evidence.EXPECTED_PATHS)):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        data = f"historical-{index}\n".encode()
        path.write_bytes(data)
        entries.append({
            "path": rel,
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
            "disposition": "INVALIDATED",
        })
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "audited start")
    start = _git(root, "rev-parse", "HEAD")
    manifest = root / "docs" / "governance" / "B00_B07_INVALIDATION_MANIFEST.v1.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({
        "audited_start_sha": start,
        "disposition_vocabulary": vocabulary,
        "entry_count": len(entries),
        "entries": entries,
    }), encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "additive invalidation manifest")
    return start, manifest


def test_historical_evidence_is_bound_to_audited_git_blobs(tmp_path):
    repo = tmp_path / "repo"
    start, manifest = _historical_repo(repo)
    assert verify_historical_evidence.verify(repo, manifest, start) == 11
    victim = repo / sorted(verify_historical_evidence.EXPECTED_PATHS)[0]
    victim.write_text("rewritten\n", encoding="utf-8")
    with pytest.raises(
        verify_historical_evidence.HistoricalEvidenceError,
        match="HISTORICAL_BYTES_CHANGED",
    ):
        verify_historical_evidence.verify(repo, manifest, start)


def test_historical_manifest_cannot_drop_a_receipt(tmp_path):
    repo = tmp_path / "repo"
    start, manifest = _historical_repo(repo)
    doc = json.loads(manifest.read_text())
    doc["entries"].pop()
    doc["entry_count"] -= 1
    manifest.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(
        verify_historical_evidence.HistoricalEvidenceError,
        match="INVALIDATION_MEMBERSHIP_NOT_CLOSED",
    ):
        verify_historical_evidence.verify(repo, manifest, start)


def _valid_codeowners(owner: str) -> str:
    return "\n".join(
        f"{pattern} {owner}" for pattern in verify_codeowners.CRITICAL_PATTERNS
    ) + "\n"


def test_codeowners_placeholder_or_missing_critical_identity_is_blocked(tmp_path):
    path = tmp_path / "CODEOWNERS"
    path.write_text(_valid_codeowners("@TriadAgentic/triad-origin-governance"))
    with pytest.raises(verify_codeowners.CodeownersError, match="PLACEHOLDER_IDENTITY"):
        verify_codeowners.verify(path)
    path.write_text(_valid_codeowners("@triadagentic/TRIAD-ORIGIN-GOVERNANCE"))
    with pytest.raises(verify_codeowners.CodeownersError, match="PLACEHOLDER_IDENTITY"):
        verify_codeowners.verify(path)
    path.write_text(_valid_codeowners("@TriadAgentic/origin-governance-reviewers"))
    with pytest.raises(verify_codeowners.CodeownersError, match="PLACEHOLDER_IDENTITY"):
        verify_codeowners.verify(path)

    lines = _valid_codeowners("@TriadAgentic/real-governance-team").splitlines()
    path.write_text("\n".join(lines[:-1]) + "\n")
    with pytest.raises(verify_codeowners.CodeownersError, match="CRITICAL_PATTERN_MISSING"):
        verify_codeowners.verify(path)


def test_codeowners_concrete_critical_identity_passes(tmp_path):
    path = tmp_path / "CODEOWNERS"
    path.write_text(_valid_codeowners("@TriadAgentic/real-governance-team"))
    count, owners = verify_codeowners.verify(path)
    assert count == len(verify_codeowners.CRITICAL_PATTERNS)
    assert owners == {"@TriadAgentic/real-governance-team"}


def test_codeowners_covers_package_and_rejects_github_size_limit(tmp_path):
    assert "/src/triad_origin/" in verify_codeowners.CRITICAL_PATTERNS
    assert "/src/triad_origin/governance.py" not in verify_codeowners.CRITICAL_PATTERNS
    path = tmp_path / "CODEOWNERS"
    path.write_bytes(b"x" * verify_codeowners.MAX_CODEOWNERS_BYTES)
    with pytest.raises(verify_codeowners.CodeownersError, match="TOO_LARGE"):
        verify_codeowners.verify(path)


def test_codeowners_provider_identity_is_writable_individual_and_independent(monkeypatch):
    def permission(username, **_kwargs):
        return {"permission": "write", "user": {"login": username}}

    monkeypatch.setattr(verify_codeowners, "fetch_repository_permission", permission)
    monkeypatch.setattr(
        verify_codeowners, "fetch_codeowners_errors", lambda *_args, **_kwargs: {"errors": []})
    assert verify_codeowners.verify_provider(
        {"@independent-reviewer"}, token="token", now_us=1,
        expected_head="a" * 40,
        pr_author="source-author",
    ) == ("independent-reviewer", "write")
    with pytest.raises(verify_codeowners.CodeownersError, match="TEAM_IDENTITY_UNSUPPORTED"):
        verify_codeowners.verify_provider(
            {"@TriadAgentic/real-governance-team"}, token="token", now_us=1,
            expected_head="a" * 40)
    with pytest.raises(verify_codeowners.CodeownersError, match="EQUALS_PR_AUTHOR"):
        verify_codeowners.verify_provider(
            {"@source-author"}, token="token", now_us=1,
            expected_head="a" * 40,
            pr_author="source-author")


def _anchored_receipt_repo(
    root: pathlib.Path,
    *,
    bypass_actors: list[dict] | None = None,
    ruleset_created_at: str = "1970-01-01T00:00:01Z",
    ruleset_updated_at: str = "1970-01-01T00:00:02Z",
    receipt_merge_instant: str | None = None,
) -> tuple[str, pathlib.Path, pathlib.Path, str]:
    root.mkdir(parents=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "anchor-test@example.invalid")
    _git(root, "config", "user.name", "Anchor Test")
    (root / "source.txt").write_text("source\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "source merge")
    source_merge = _git(root, "rev-parse", "HEAD")
    main_branch = _git(root, "branch", "--show-current")
    _git(root, "checkout", "-qb", "receipt-work")
    receipt = root / validate_b00r_anchor.RECEIPT_PATH
    receipt.parent.mkdir(parents=True)
    ruleset_updated_us = validate_b00r_anchor._ruleset_time_us(
        ruleset_updated_at, "updated_at")
    receipt.write_text(json.dumps({
        "payload": {
            "source_merge_sha": source_merge,
            "observed_at_us": ruleset_updated_us + 1,
            "emitted_at_us": ruleset_updated_us + 2,
        },
        "receipt": "b00r",
    }, sort_keys=True), encoding="utf-8")
    ruleset = root / validate_b00r_anchor.DEFAULT_RULESET
    ruleset.parent.mkdir(parents=True)
    ruleset.write_text(json.dumps({
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
                "href": "https://api.github.com/repos/TriadAgentic/TriadOrigin/rulesets/1001"
            },
            "html": {
                "href": "https://github.com/TriadAgentic/TriadOrigin/rules/1001"
            },
        },
        "created_at": ruleset_created_at,
        "updated_at": ruleset_updated_at,
        "conditions": {
            "ref_name": {
                "include": [f"refs/tags/{validate_b00r_anchor.TAG_NAME}"],
                "exclude": [],
            }
        },
        "bypass_actors": [] if bypass_actors is None else bypass_actors,
        "rules": [{"type": "update"}, {"type": "deletion"}],
    }, sort_keys=True), encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "receipt head")
    _git(root, "checkout", "-q", main_branch)
    merge_command = ("merge", "--no-ff", "-qm", "receipt merge", "receipt-work")
    if receipt_merge_instant is None:
        _git(root, *merge_command)
    else:
        _git_at(root, receipt_merge_instant, *merge_command)
    head = _git(root, "rev-parse", "HEAD")
    receipt_sha = hashlib.sha256(receipt.read_bytes()).hexdigest()
    message = (
        "TRIAD-B00R-RECEIPT-ANCHOR-G2-V1\n"
        f"receipt_path={validate_b00r_anchor.RECEIPT_PATH}\n"
        f"receipt_sha256={receipt_sha}\n"
    )
    _git(root, "tag", "-a", validate_b00r_anchor.TAG_NAME, "-m", message, head)
    pin = hashlib.sha256(ruleset.read_bytes()).hexdigest()
    return head, receipt, ruleset, pin


def test_receipt_anchor_binds_merge_receipt_and_pinned_immutable_ruleset(tmp_path):
    repo = tmp_path / "repo"
    head, receipt, ruleset, pin = _anchored_receipt_repo(repo)
    receipt_sha = validate_b00r_anchor._verify_static(
        root=repo,
        expected_head=head,
        receipt_path=receipt,
        ruleset_path=ruleset,
        ruleset_pin=pin,
    )
    assert receipt_sha == hashlib.sha256(receipt.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    "message",
    [
        (
            "TRIAD-B00R-RECEIPT-ANCHOR-G2-V1\n"
            f"receipt_sha256={'a' * 64}\n"
            f"receipt_path={validate_b00r_anchor.RECEIPT_PATH}\n"
        ),
        (
            "TRIAD-B00R-RECEIPT-ANCHOR-G2-V1\n"
            f"receipt_path={validate_b00r_anchor.RECEIPT_PATH}\n"
            f"receipt_sha256={'a' * 64}"
        ),
        (
            "TRIAD-B00R-RECEIPT-ANCHOR-G2-V1\n"
            f"receipt_path={validate_b00r_anchor.RECEIPT_PATH}\n"
            f"receipt_sha256={'a' * 64}\n\n"
        ),
        (
            "TRIAD-B00R-RECEIPT-ANCHOR-G2-V1\n"
            f"receipt_path={validate_b00r_anchor.RECEIPT_PATH}\n"
            f"receipt_sha256={'a' * 64}\n"
            "-----BEGIN PGP SIGNATURE-----\n"
        ),
    ],
)
def test_anchor_message_requires_exact_order_and_one_terminal_newline(message):
    with pytest.raises(
        validate_b00r_anchor.AnchorError,
        match="ANCHOR_MESSAGE_NOT_EXACT_CANONICAL_THREE_LINES",
    ):
        validate_b00r_anchor._parse_anchor_message(message)


def test_anchor_tag_object_rejects_extra_header_even_with_exact_message():
    raw = (
        f"object {'a' * 40}\n"
        "type commit\n"
        f"tag {validate_b00r_anchor.TAG_NAME}\n"
        "tagger Anchor Custodian <anchor@example.invalid> 1 +0000\n"
        "encoding UTF-8\n\n"
        "TRIAD-B00R-RECEIPT-ANCHOR-G2-V1\n"
        f"receipt_path={validate_b00r_anchor.RECEIPT_PATH}\n"
        f"receipt_sha256={'b' * 64}\n"
    ).encode("utf-8")
    with pytest.raises(
        validate_b00r_anchor.AnchorError,
        match="ANCHOR_TAG_HEADER_SET_NOT_EXACT",
    ):
        validate_b00r_anchor._parse_tag(raw)


def test_receipt_anchor_rejects_tagged_single_parent_evidence_commit(tmp_path):
    repo = tmp_path / "repo"
    _head, receipt, ruleset, pin = _anchored_receipt_repo(repo)
    _git(repo, "tag", "-d", validate_b00r_anchor.TAG_NAME)
    (repo / "evidence" / "B00R_G2" / "attack.txt").write_text("unreviewed\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "unreviewed evidence commit")
    attack_head = _git(repo, "rev-parse", "HEAD")
    message = (
        "TRIAD-B00R-RECEIPT-ANCHOR-G2-V1\n"
        f"receipt_path={validate_b00r_anchor.RECEIPT_PATH}\n"
        f"receipt_sha256={hashlib.sha256(receipt.read_bytes()).hexdigest()}\n"
    )
    _git(repo, "tag", "-a", validate_b00r_anchor.TAG_NAME, "-m", message, attack_head)
    with pytest.raises(
        validate_b00r_anchor.AnchorError,
        match="RECEIPT_MERGE_NOT_EXACT_TWO_PARENT_SOURCE_MERGE",
    ):
        validate_b00r_anchor._verify_static(
            root=repo, expected_head=attack_head, receipt_path=receipt,
            ruleset_path=ruleset, ruleset_pin=pin)


def test_receipt_anchor_terminal_verify_uses_bound_bytes_and_requires_live_token(
    tmp_path, monkeypatch
):
    repo = tmp_path / "repo"
    head, _receipt, _ruleset, pin = _anchored_receipt_repo(repo)
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(outside)
    with pytest.raises(validate_b00r_anchor.LiveRulesetUnavailable, match="TOKEN_ABSENT"):
        validate_b00r_anchor.verify(
            root=repo,
            expected_head=head,
            receipt_path=pathlib.Path(validate_b00r_anchor.RECEIPT_PATH),
            ruleset_path=pathlib.Path(validate_b00r_anchor.DEFAULT_RULESET),
            ruleset_pin=pin,
            now_us=1,
            github_token=None,
            receipt_pr=35,
        )


def test_receipt_anchor_terminal_verify_binds_live_annotated_tag_object(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    head, receipt, ruleset, pin = _anchored_receipt_repo(repo)
    tag_object_sha = _git(repo, "rev-parse", f"refs/tags/{validate_b00r_anchor.TAG_NAME}")
    monkeypatch.setattr(
        validate_b00r_anchor, "fetch_and_match_live_ruleset", lambda *_args, **_kwargs: object())
    receipt_head = _git(repo, "rev-parse", f"{head}^2")
    merge_time_us = int(_git(repo, "show", "-s", "--format=%ct", head)) * 1_000_000
    monkeypatch.setattr(
        validate_b00r_anchor, "fetch_and_verify_receipt_merge",
        lambda *_args, **_kwargs: SimpleNamespace(
            head_sha=receipt_head, merged_at_us=merge_time_us))
    monkeypatch.setattr(
        validate_b00r_anchor, "fetch_anchor_tag_object_sha",
        lambda **_kwargs: tag_object_sha)
    assert validate_b00r_anchor.verify(
        root=repo, expected_head=head, receipt_path=receipt, ruleset_path=ruleset,
        ruleset_pin=pin, now_us=1, github_token="token", receipt_pr=35,
    ) == hashlib.sha256(receipt.read_bytes()).hexdigest()
    monkeypatch.setattr(
        validate_b00r_anchor, "fetch_anchor_tag_object_sha",
        lambda **_kwargs: "0" * 40)
    with pytest.raises(validate_b00r_anchor.AnchorError, match="TAG_OBJECT_MISMATCH"):
        validate_b00r_anchor.verify(
            root=repo, expected_head=head, receipt_path=receipt, ruleset_path=ruleset,
            ruleset_pin=pin, now_us=1, github_token="token", receipt_pr=35,
        )


def test_receipt_anchor_rejects_tag_ruleset_installed_after_receipt_merge(
    tmp_path, monkeypatch
):
    repo = tmp_path / "repo"
    head, receipt, ruleset, pin = _anchored_receipt_repo(
        repo, ruleset_updated_at="2999-01-01T00:00:00Z")
    receipt_head = _git(repo, "rev-parse", f"{head}^2")
    merge_time_us = int(_git(repo, "show", "-s", "--format=%ct", head)) * 1_000_000
    monkeypatch.setattr(
        validate_b00r_anchor, "fetch_and_verify_receipt_merge",
        lambda *_args, **_kwargs: SimpleNamespace(
            head_sha=receipt_head, merged_at_us=merge_time_us))
    with pytest.raises(
        validate_b00r_anchor.AnchorError,
        match="TAG_RULESET_NOT_EFFECTIVE_BEFORE_RECEIPT_MERGE",
    ):
        validate_b00r_anchor.verify(
            root=repo, expected_head=head, receipt_path=receipt, ruleset_path=ruleset,
            ruleset_pin=pin, now_us=1, github_token="token", receipt_pr=35)


def test_receipt_anchor_rejects_tag_ruleset_created_after_its_update(
    tmp_path, monkeypatch
):
    repo = tmp_path / "repo"
    head, receipt, ruleset, pin = _anchored_receipt_repo(
        repo,
        ruleset_created_at="1970-01-01T00:00:03Z",
        ruleset_updated_at="1970-01-01T00:00:02Z",
    )
    receipt_head = _git(repo, "rev-parse", f"{head}^2")
    merge_time_us = int(_git(repo, "show", "-s", "--format=%ct", head)) * 1_000_000
    monkeypatch.setattr(
        validate_b00r_anchor, "fetch_and_verify_receipt_merge",
        lambda *_args, **_kwargs: SimpleNamespace(
            head_sha=receipt_head, merged_at_us=merge_time_us))
    with pytest.raises(
        validate_b00r_anchor.AnchorError,
        match="TAG_RULESET_NOT_EFFECTIVE_BEFORE_RECEIPT_OBSERVATION",
    ):
        validate_b00r_anchor.verify(
            root=repo, expected_head=head, receipt_path=receipt, ruleset_path=ruleset,
            ruleset_pin=pin, now_us=1, github_token="token", receipt_pr=35)


@pytest.mark.parametrize("fractional_before", [False, True])
def test_receipt_anchor_tag_ruleset_strict_merge_time_boundary(
    tmp_path, monkeypatch, fractional_before
):
    repo = tmp_path / "repo"
    updated_at = (
        "2030-01-01T23:59:59.999999Z"
        if fractional_before else "2030-01-02T00:00:00Z"
    )
    head, receipt, ruleset, pin = _anchored_receipt_repo(
        repo,
        ruleset_updated_at=updated_at,
        receipt_merge_instant="2030-01-02T00:00:00Z",
    )
    receipt_head = _git(repo, "rev-parse", f"{head}^2")
    merge_time_s = int(_git(repo, "show", "-s", "--format=%ct", head))
    merge_time_us = merge_time_s * 1_000_000
    tag_object_sha = _git(repo, "rev-parse", f"refs/tags/{validate_b00r_anchor.TAG_NAME}")
    monkeypatch.setattr(
        validate_b00r_anchor, "fetch_and_verify_receipt_merge",
        lambda *_args, **_kwargs: SimpleNamespace(
            head_sha=receipt_head, merged_at_us=merge_time_us))
    monkeypatch.setattr(
        validate_b00r_anchor, "fetch_and_match_live_ruleset",
        lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        validate_b00r_anchor, "fetch_anchor_tag_object_sha",
        lambda **_kwargs: tag_object_sha)
    if fractional_before:
        assert validate_b00r_anchor.verify(
            root=repo, expected_head=head, receipt_path=receipt, ruleset_path=ruleset,
            ruleset_pin=pin, now_us=1, github_token="token", receipt_pr=35,
        ) == hashlib.sha256(receipt.read_bytes()).hexdigest()
    else:
        with pytest.raises(
            validate_b00r_anchor.AnchorError,
            match="TAG_RULESET_NOT_EFFECTIVE_BEFORE_RECEIPT_MERGE",
        ):
            validate_b00r_anchor.verify(
                root=repo, expected_head=head, receipt_path=receipt, ruleset_path=ruleset,
                ruleset_pin=pin, now_us=1, github_token="token", receipt_pr=35)


def test_receipt_anchor_rejects_provider_and_git_merge_time_drift(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    head, receipt, ruleset, pin = _anchored_receipt_repo(repo)
    receipt_head = _git(repo, "rev-parse", f"{head}^2")
    merge_time_us = int(_git(repo, "show", "-s", "--format=%ct", head)) * 1_000_000
    monkeypatch.setattr(
        validate_b00r_anchor, "fetch_and_verify_receipt_merge",
        lambda *_args, **_kwargs: SimpleNamespace(
            head_sha=receipt_head, merged_at_us=merge_time_us + 1_000_000))
    with pytest.raises(
        validate_b00r_anchor.AnchorError,
        match="RECEIPT_PR_PROVIDER_GIT_TIME_MISMATCH",
    ):
        validate_b00r_anchor.verify(
            root=repo, expected_head=head, receipt_path=receipt, ruleset_path=ruleset,
            ruleset_pin=pin, now_us=1, github_token="token", receipt_pr=35)


def test_receipt_anchor_rejects_absent_pin_and_bypassable_ruleset(tmp_path):
    repo = tmp_path / "repo"
    head, receipt, ruleset, pin = _anchored_receipt_repo(repo)
    with pytest.raises(validate_b00r_anchor.AnchorError, match="EXTERNAL_TAG_RULESET_PIN_ABSENT"):
        validate_b00r_anchor._verify_static(
            root=repo,
            expected_head=head,
            receipt_path=receipt,
            ruleset_path=ruleset,
            ruleset_pin=None,
        )

    unsafe_repo = tmp_path / "unsafe-repo"
    head, receipt, ruleset, unsafe_pin = _anchored_receipt_repo(
        unsafe_repo,
        bypass_actors=[{"actor_id": 1, "actor_type": "OrganizationAdmin"}],
    )
    with pytest.raises(validate_b00r_anchor.AnchorError, match="BYPASS_ACTORS_PRESENT"):
        validate_b00r_anchor._verify_static(
            root=unsafe_repo,
            expected_head=head,
            receipt_path=receipt,
            ruleset_path=ruleset,
            ruleset_pin=unsafe_pin,
        )


def test_receipt_anchor_rejects_wrong_provider_source_or_current_user_bypass(tmp_path):
    repo = tmp_path / "repo"
    _head, _receipt, ruleset, _pin = _anchored_receipt_repo(repo)
    safe = json.loads(ruleset.read_text())

    unsafe = dict(safe)
    unsafe["current_user_can_bypass"] = "always"
    with pytest.raises(validate_b00r_anchor.AnchorError, match="CURRENT_USER_BYPASS_NOT_NEVER"):
        validate_b00r_anchor._validate_ruleset(unsafe)

    wrong_source = dict(safe)
    wrong_source["source"] = "attacker/fork"
    with pytest.raises(validate_b00r_anchor.AnchorError, match="SOURCE_MISMATCH"):
        validate_b00r_anchor._validate_ruleset(wrong_source)


def test_receipt_mode_terminal_gate_contains_anchor_validation():
    from argparse import Namespace

    args = Namespace(
        mode="receipt",
        expected_head="a" * 40,
        now_us=1_000_000,
        pins=None,
        receipt=b00r_gate.CANONICAL_RECEIPT,
        manifest=b00r_gate.CANONICAL_MANIFEST,
        governance_snapshot=b00r_gate.CANONICAL_GOVERNANCE_SNAPSHOT,
        provider_raw=b00r_gate.CANONICAL_PROVIDER_RAW,
        provider_pin=None,
        anchor_ruleset=b00r_gate.CANONICAL_ANCHOR_RULESET,
        anchor_ruleset_pin=None,
        receipt_pr=35,
    )
    gates = b00r_gate._owner_gates(args)
    anchor = [gate for gate in gates if gate.gate_id == "receipt_anchor"]
    assert len(anchor) == 1
    assert anchor[0].owner_gated is True
    assert "tools/validate_b00r_anchor.py" in anchor[0].argv
    assert "--expected-head" in anchor[0].argv
    assert anchor[0].argv[anchor[0].argv.index("--receipt-pr") + 1] == "35"

    receipt = [gate for gate in gates if gate.gate_id == "receipt_v3_closure"]
    assert len(receipt) == 1
    assert receipt[0].argv[receipt[0].argv.index("--receipt-pr") + 1] == "35"
    assert gates[-1].gate_id == "receipt_v3_closure"
    for required in (
        "--now-us", "--manifest", "--git-root", "--expected-head",
        "--governance-snapshot", "--provider-raw",
    ):
        assert required in receipt[0].argv


def test_source_owner_gates_are_strict_but_never_run_receipt_closure():
    from argparse import Namespace

    args = Namespace(
        mode="source",
        expected_head="a" * 40,
        now_us=1_000_000,
        pins=None,
        governance_snapshot=b00r_gate.CANONICAL_GOVERNANCE_SNAPSHOT,
        provider_raw=b00r_gate.CANONICAL_PROVIDER_RAW,
        provider_pin=None,
    )
    gates = b00r_gate._owner_gates(args)
    assert [gate.gate_id for gate in gates] == ["authority_root", "governance_snapshot"]
    assert all(gate.owner_gated and "--strict" in gate.argv for gate in gates)
    assert all("--now-us" in gate.argv for gate in gates)
    assert all("--expected-head" in gate.argv and "--git-root" in gate.argv for gate in gates)
    assert not any("validate_b_receipt.py" in gate.argv for gate in gates)


def test_owner_provider_time_advances_by_monotonic_elapsed_time():
    assert b00r_gate._advanced_trusted_now_us(
        1_000_000, 5_000_000_000, 70_000_000_000) == 66_000_000
    gate = b00r_gate.Gate(
        "owner", ("python", "validator.py", "--now-us", "1"), owner_gated=True)
    advanced = b00r_gate._with_trusted_now_us(gate, 66_000_000)
    assert advanced.argv[-1] == "66000000"
    assert advanced.owner_gated is True


def test_each_owner_gate_gets_a_fresh_monotonic_advanced_time(monkeypatch):
    expected_head = "a" * 40
    monkeypatch.setattr(
        b00r_gate, "verify_expected_head", lambda expected: expected_head)
    monkeypatch.setattr(
        b00r_gate, "COMMON_GATES", (b00r_gate.Gate("deterministic", ("noop",)),))
    monkeypatch.setattr(
        b00r_gate,
        "_codeowners_gates",
        lambda _args: (
            b00r_gate.Gate(
                "owner_one", ("python", "one.py", "--now-us", "1"), owner_gated=True),
            b00r_gate.Gate(
                "owner_two", ("python", "two.py", "--now-us", "1"), owner_gated=True),
        ),
    )
    monkeypatch.setattr(b00r_gate, "_owner_gates", lambda _args: ())
    instants = iter((1_000_000_000, 71_000_000_000, 141_000_000_000))
    monkeypatch.setattr(b00r_gate.time, "monotonic_ns", lambda: next(instants))
    observed: list[tuple[str, str | None]] = []

    def fake_run(gate):
        now = gate.argv[gate.argv.index("--now-us") + 1] if "--now-us" in gate.argv else None
        observed.append((gate.gate_id, now))
        return "PASS", "ok"

    monkeypatch.setattr(b00r_gate, "_run", fake_run)
    assert b00r_gate.main([
        "--mode", "source", "--expected-head", expected_head,
        "--now-us", "1000000",
    ]) == 1
    assert observed == [
        ("deterministic", None),
        ("owner_one", "71000000"),
        ("owner_two", "141000000"),
    ]


def test_deterministic_failure_never_constructs_or_runs_owner_gates(monkeypatch):
    expected_head = "a" * 40
    monkeypatch.setattr(
        b00r_gate, "verify_expected_head", lambda expected: expected_head)
    monkeypatch.setattr(
        b00r_gate, "COMMON_GATES", (b00r_gate.Gate("known_bad", ("noop",)),))
    invoked: list[str] = []

    def fake_run(gate):
        invoked.append(gate.gate_id)
        return "FAIL", "deterministic failure"

    def owner_path_must_not_be_reached(_args):
        raise AssertionError("provider-authenticated owner gate was constructed")

    monkeypatch.setattr(b00r_gate, "_run", fake_run)
    monkeypatch.setattr(b00r_gate, "_codeowners_gates", owner_path_must_not_be_reached)
    monkeypatch.setattr(b00r_gate, "_owner_gates", owner_path_must_not_be_reached)

    assert b00r_gate.main([
        "--mode", "source", "--expected-head", expected_head,
        "--now-us", "1000000",
    ]) == 1
    assert invoked == ["known_bad"]
