"""Falsification tests for exact-head, role, evidence, history, and CODEOWNERS gates."""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess

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
    with pytest.raises(b00r_gate.HeadIdentityError, match="NOT_CANONICAL_HEX40"):
        b00r_gate.verify_expected_head("HEAD", tmp_path / "repo")
    with pytest.raises(b00r_gate.HeadIdentityError, match="ALL_ZERO_UNAVAILABLE"):
        b00r_gate.verify_expected_head("0" * 40, tmp_path / "repo")
    with pytest.raises(b00r_gate.HeadIdentityError, match="EXPECTED_HEAD_MISMATCH"):
        b00r_gate.verify_expected_head("f" * 40, tmp_path / "repo")


def test_receipt_mode_requires_expected_head_and_base_sha():
    with pytest.raises(SystemExit) as missing_head:
        b00r_gate.main([
            "--mode", "receipt", "--base-sha", "a" * 40, "--now-us", "1000000",
        ])
    assert missing_head.value.code == 2
    with pytest.raises(SystemExit) as missing_base:
        b00r_gate.main([
            "--mode", "receipt", "--expected-head", "a" * 40, "--now-us", "1000000",
        ])
    assert missing_base.value.code == 2
    with pytest.raises(SystemExit) as zero_base:
        b00r_gate.main([
            "--mode", "receipt", "--expected-head", "a" * 40,
            "--base-sha", "0" * 40, "--now-us", "1000000",
        ])
    assert zero_base.value.code == 2
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
            classifier.Change("A", "evidence/B00R/evidence_manifest.json"),
            classifier.Change("A", "evidence/B00R/test.log"),
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
    (repo / "evidence" / "B00R").mkdir()
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
    (repo / "evidence" / "B00R").mkdir()
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
    closed = root / "evidence" / "B00R"
    closed.mkdir(parents=True)
    spec = closed / "spec.json"
    log = closed / "run.log"
    entries = [
        {"path": "evidence/B00R/spec.json", "role": "SPEC"},
        {"path": "evidence/B00R/run.log", "role": "RUN_LOG"},
    ]
    spec.write_text(json.dumps({"entries": entries}), encoding="utf-8")
    log.write_text("green\n", encoding="utf-8")
    manifest = closed / "evidence_manifest.json"
    assert evidence_manifest.main([
        "--build", str(spec), "--root", str(root), "--out", str(manifest),
        "--closed-root", "evidence/B00R",
    ]) == 0
    return closed, manifest


def test_evidence_manifest_membership_is_closed(tmp_path):
    root = tmp_path / "repo"
    closed, manifest = _write_closed_evidence(root)
    assert evidence_manifest.main([
        "--verify", str(manifest), "--root", str(root),
        "--closed-root", "evidence/B00R",
    ]) == 0
    (closed / "omitted.log").write_text("not declared\n", encoding="utf-8")
    assert evidence_manifest.main([
        "--verify", str(manifest), "--root", str(root),
        "--closed-root", "evidence/B00R",
    ]) == 1


def test_evidence_manifest_rejects_count_and_media_type_drift(tmp_path):
    root = tmp_path / "repo"
    _closed, manifest = _write_closed_evidence(root)
    doc = json.loads(manifest.read_text())
    doc["entry_count"] += 1
    manifest.write_text(json.dumps(doc), encoding="utf-8")
    assert evidence_manifest.main([
        "--verify", str(manifest), "--root", str(root),
        "--closed-root", "evidence/B00R",
    ]) == 1

    _closed, manifest = _write_closed_evidence(tmp_path / "second")
    doc = json.loads(manifest.read_text())
    doc["entries"][0]["media_type"] = "text/plain"
    manifest.write_text(json.dumps(doc), encoding="utf-8")
    assert evidence_manifest.main([
        "--verify", str(manifest), "--root", str(tmp_path / "second"),
        "--closed-root", "evidence/B00R",
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
        "--closed-root", "evidence/B00R",
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


def _anchored_receipt_repo(root: pathlib.Path) -> tuple[str, pathlib.Path, pathlib.Path, str]:
    root.mkdir(parents=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "anchor-test@example.invalid")
    _git(root, "config", "user.name", "Anchor Test")
    receipt = root / validate_b00r_anchor.RECEIPT_PATH
    receipt.parent.mkdir(parents=True)
    receipt.write_text('{"receipt":"b00r"}\n', encoding="utf-8")
    ruleset = root / validate_b00r_anchor.DEFAULT_RULESET
    ruleset.parent.mkdir(parents=True)
    ruleset.write_text(json.dumps({
        "id": 1001,
        "target": "tag",
        "source_type": "Repository",
        "source": "TriadAgentic/TriadOrigin",
        "current_user_can_bypass": False,
        "enforcement": "active",
        "conditions": {
            "ref_name": {
                "include": ["refs/tags/B00R_RECEIPT_ANCHOR"],
                "exclude": [],
            }
        },
        "bypass_actors": [],
        "rules": [{"type": "update"}, {"type": "deletion"}],
    }, sort_keys=True), encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "receipt merge")
    head = _git(root, "rev-parse", "HEAD")
    receipt_sha = hashlib.sha256(receipt.read_bytes()).hexdigest()
    message = (
        "TRIAD-B00R-RECEIPT-ANCHOR-V1\n"
        f"receipt_path={validate_b00r_anchor.RECEIPT_PATH}\n"
        f"receipt_sha256={receipt_sha}\n"
    )
    _git(root, "tag", "-a", validate_b00r_anchor.TAG_NAME, "-m", message, head)
    pin = hashlib.sha256(ruleset.read_bytes()).hexdigest()
    return head, receipt, ruleset, pin


def test_receipt_anchor_binds_merge_receipt_and_pinned_immutable_ruleset(tmp_path):
    repo = tmp_path / "repo"
    head, receipt, ruleset, pin = _anchored_receipt_repo(repo)
    receipt_sha = validate_b00r_anchor.verify(
        root=repo,
        expected_head=head,
        receipt_path=receipt,
        ruleset_path=ruleset,
        ruleset_pin=pin,
    )
    assert receipt_sha == hashlib.sha256(receipt.read_bytes()).hexdigest()


def test_receipt_anchor_rejects_absent_pin_and_bypassable_ruleset(tmp_path):
    repo = tmp_path / "repo"
    head, receipt, ruleset, pin = _anchored_receipt_repo(repo)
    with pytest.raises(validate_b00r_anchor.AnchorError, match="EXTERNAL_TAG_RULESET_PIN_ABSENT"):
        validate_b00r_anchor.verify(
            root=repo,
            expected_head=head,
            receipt_path=receipt,
            ruleset_path=ruleset,
            ruleset_pin=None,
        )

    # Rebuild the exact commit/tag with a provider capture that contains a bypass actor.  A newly
    # computed external pin cannot make unsafe rules pass semantic validation.
    _git(repo, "tag", "-d", validate_b00r_anchor.TAG_NAME)
    doc = json.loads(ruleset.read_text())
    doc["bypass_actors"] = [{"actor_id": 1, "actor_type": "OrganizationAdmin"}]
    ruleset.write_text(json.dumps(doc, sort_keys=True), encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "unsafe ruleset")
    head = _git(repo, "rev-parse", "HEAD")
    message = (
        "TRIAD-B00R-RECEIPT-ANCHOR-V1\n"
        f"receipt_path={validate_b00r_anchor.RECEIPT_PATH}\n"
        f"receipt_sha256={hashlib.sha256(receipt.read_bytes()).hexdigest()}\n"
    )
    _git(repo, "tag", "-a", validate_b00r_anchor.TAG_NAME, "-m", message, head)
    unsafe_pin = hashlib.sha256(ruleset.read_bytes()).hexdigest()
    with pytest.raises(validate_b00r_anchor.AnchorError, match="BYPASS_ACTORS_PRESENT"):
        validate_b00r_anchor.verify(
            root=repo,
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
    unsafe["current_user_can_bypass"] = True
    with pytest.raises(validate_b00r_anchor.AnchorError, match="CURRENT_USER_BYPASS_NOT_FALSE"):
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
    )
    gates = b00r_gate._owner_gates(args)
    anchor = [gate for gate in gates if gate.gate_id == "receipt_anchor"]
    assert len(anchor) == 1
    assert anchor[0].owner_gated is True
    assert "tools/validate_b00r_anchor.py" in anchor[0].argv
    assert "--expected-head" in anchor[0].argv

    receipt = [gate for gate in gates if gate.gate_id == "receipt_v3_closure"]
    assert len(receipt) == 1
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
