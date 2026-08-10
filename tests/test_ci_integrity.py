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
    assert workflow.count("run: python -m pytest") == 2
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
    # The role-aware gate and the always-run source-hash inventory are present.
    assert "Role-aware milestone gate" in workflow
    assert "tools/classify_milestone_pr.py" in workflow
    assert "tools/verify_source_hashes.py" in workflow
    # The stable required context is the job name (surfaced as "CI / test-and-verify").
    assert "test-and-verify:" in workflow


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
