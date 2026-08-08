"""R00 regression guards for immutable CI inputs."""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys


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
    assert "fetch-depth: 2" in workflow
    assert "ref: ${{ github.head_ref || github.sha }}" in workflow
    assert "name: Checkout exact head" in workflow
    assert "name: Set up Python 3.11" in workflow
    assert "hashFiles('evidence/receipts/R00.json')" in workflow
    assert "github.head_ref == 'evidence/r00-receipt'" in workflow
    assert "github.event_name == 'pull_request'" in workflow
    assert "GITHUB_TOKEN: ${{ github.token }}" in workflow
    assert (
        "run: python tools/validate_milestone_receipt.py "
        "evidence/receipts/R00.json"
    ) in workflow


def test_ci_constraint_snapshot_is_exact_and_unique():
    lines = [
        line.strip()
        for line in (ROOT / "constraints" / "ci.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert lines
    assert all(re.fullmatch(r"[A-Za-z0-9_.-]+==[^=\s]+", line) for line in lines)
    names = [line.split("==", 1)[0].lower().replace("_", "-") for line in lines]
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
