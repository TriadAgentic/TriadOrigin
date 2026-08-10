"""R00 regression guards for immutable CI inputs."""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

from tools.validate_milestone_receipt import _exact_dependency_pin_name


ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_ci_actions_are_sha_pinned_and_solver_uses_committed_constraints():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "actions/checkout@11d5960a326750d5838078e36cf38b85af677262" in workflow
    assert "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065" in workflow
    assert not re.search(r"uses:\s+actions/(?:checkout|setup-python)@v\d", workflow)
    assert "PIP_CONSTRAINT: ${{ github.workspace }}/constraints/ci.txt" in workflow
    assert "TZ: UTC" in workflow
    assert "LC_ALL: C.UTF-8" in workflow
    assert 'PYTHONHASHSEED: "0"' in workflow
    assert 'PYTHONHASHSEED: "1"' in workflow
    assert workflow.count("run: python -m pytest -p no:cacheprovider") == 2
    assert "pull-requests: read" in workflow
    assert "actions: read" in workflow
    assert "contents: read" in workflow
    assert "issues: read" in workflow
    # B00R needs the merge base to classify the PR-role, so the checkout is full history.
    assert "fetch-depth: 0" in workflow
    assert "ref: ${{ github.event.pull_request.head.sha || github.sha }}" in workflow
    assert "ref: ${{ github.head_ref || github.sha }}" not in workflow
    assert "name: Checkout exact head" in workflow
    assert "name: Bind checks to exact event head" in workflow
    assert "name: Set up Python 3.11" in workflow
    assert "GITHUB_TOKEN: ${{ github.token }}" in workflow


def test_ci_has_no_branch_specific_receipt_skip_and_is_role_aware():
    """B00R-D16 / CI-002: the receipt authenticator is invoked by diff-derived role on every PR,
    never gated behind a mutable branch name; the old evidence/r00-receipt skip is gone."""
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    # The branch-specific R00 receipt skip and force-create branch step are removed.
    assert "github.head_ref == 'evidence/r00-receipt'" not in workflow
    assert "git switch --force-create evidence/r00-receipt" not in workflow
    assert "Establish receipt evidence branch" not in workflow
    # Role comes from exact immutable event SHAs on PR and main-push events, not a mutable ref.
    assert "name: Classify exact event diff" in workflow
    assert "tools/classify_milestone_pr.py" in workflow
    assert "github.event.pull_request.base.sha || github.event.before" in workflow
    assert "github.event.pull_request.head.sha || github.sha" in workflow
    assert "0000000000000000000000000000000000000000" in workflow
    assert "event base SHA is absent, all-zero, or non-canonical" in workflow
    assert "event head SHA is absent, all-zero, or non-canonical" in workflow
    assert "--github-output \"$GITHUB_OUTPUT\"" in workflow
    assert "tools/verify_source_hashes.py" in workflow
    assert "tools/verify_historical_evidence.py" in workflow
    assert "tools/verify_codeowners.py" in workflow
    assert "changed_paths.txt" not in workflow
    assert "HEAD~1" not in workflow
    assert "git fetch" not in workflow
    # The stable required context is the job name (surfaced as "CI / test-and-verify").
    assert "test-and-verify:" in workflow


def test_ci_receipt_closure_is_exactly_one_canonical_strict_validation():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert workflow.count("tools/validate_b_receipt.py") == 1
    # The classifier owns the canonical path output; neither generation is hard-coded here.
    assert "B00R.receipt.v3.json" not in workflow
    assert "B00R.g2.receipt.v3.json" not in workflow
    assert "steps.milestone_role.outputs.receipt_path" in workflow
    assert "steps.milestone_role.outputs.manifest_path" in workflow
    assert "steps.event_facts.outputs.head_sha" in workflow
    for flag in ("--now-us", "--manifest", "--git-root", "--expected-head",
                 "--governance-snapshot", "--provider-raw", "--provider-pin"):
        assert flag in workflow
    assert "--closed-root evidence/B00R_G2" in workflow
    assert "--require-tracked" in workflow
    assert "*.receipt.v3.json" not in workflow
    assert ".dsse.json" not in workflow
    assert "for r in" not in workflow
    assert "found=0" not in workflow
    assert "B00R_RECEIPT_ANCHOR_G2" in workflow
    assert "does not claim terminal" in workflow


def test_ci_never_ignores_owner_validators_and_wires_external_pins():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "|| true" not in workflow
    assert "python tools/validate_authority_root.py --strict" in workflow
    assert "python tools/validate_governance_snapshot.py --strict" in workflow
    assert "name: Strict source authority control" in workflow
    assert "name: Nonterminal source provider revalidation" in workflow
    assert "name: Strict B00R authority control" in workflow
    assert "name: Nonterminal B00R provider revalidation" in workflow
    assert "name: Mark deterministic engineering complete" in workflow
    assert workflow.count("steps.engineering_complete.outcome == 'success'") == 5
    assert "Source safe-hold governance report" not in workflow
    owner_offset = workflow.index("name: Concrete critical-path CODEOWNERS identity")
    for completed_first in (
        "name: Historical evidence immutability",
        "name: Reproducible source and wheel artifacts",
        "name: Installed-wheel contract smoke",
        "name: DARK capability boundary",
        "name: End-to-end audit walk",
        "name: Combined RC3+RC4 composition DAG",
    ):
        assert workflow.index(completed_first) < owner_offset
    assert "--snapshot docs/governance/rulesets/main.ruleset.provider.json" in workflow
    assert "--provider-raw docs/governance/rulesets/main.ruleset.provider.raw.json" in workflow
    assert "name: Resolve trusted owner-validation time" not in workflow
    assert "NOW_US: ${{ steps.owner_time.outputs.now_us }}" not in workflow
    assert "NOW_US: ${{ steps.event_facts.outputs.now_us }}" not in workflow
    assert workflow.count('NOW_US="$(date -u +%s)000000"') == 6
    assert workflow.count('--expected-head "$EXPECTED_HEAD"') == 6
    assert workflow.count("--git-root .") == 5
    assert workflow.count("--repair-generation 2") == 2
    for name in (
        "AUTHORITY_BUNDLE_DECISION_SHA256",
        "RECEIPT_PROFILE_G2_DECISION_SHA256",
        "B00R_G2_REPAIR_DECISION_SHA256",
        "RECEIPT_G2_TRUST_REGISTRY_SHA256",
        "MAIN_RULESET_EVIDENCE_SHA256",
    ):
        assert f"{name}: ${{{{ vars.{name} }}}}" in workflow
    assert "RECEIPT_PROFILE_DECISION_SHA256:" not in workflow
    assert "B00_REPAIR_DECISION_SHA256:" not in workflow


def test_ci_constraint_snapshot_is_exact_and_unique():
    lines = [
        line.strip()
        for line in (ROOT / "constraints" / "ci.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert lines
    names = [_exact_dependency_pin_name(line) for line in lines]
    assert all(name is not None for name in names)
    assert len(names) == len(set(names))
    assert {"pytest", "jsonschema", "setuptools", "wheel"} <= set(names)


def test_controlled_test_id_collector_runs_under_repository_pytest_config():
    result = subprocess.run(
        [sys.executable, "tools/collect_test_ids.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    node_ids = result.stdout.splitlines()
    assert node_ids
    assert len(node_ids) == len(set(node_ids))
    assert (
        "tests/test_ci_integrity.py::"
        "test_controlled_test_id_collector_runs_under_repository_pytest_config"
    ) in node_ids
