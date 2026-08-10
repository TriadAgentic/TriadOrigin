"""R00 regression guards for immutable CI inputs."""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

from tools.validate_milestone_receipt import _exact_dependency_pin_name


ROOT = pathlib.Path(__file__).resolve().parent.parent


# The frozen audit runner (audit_package/triad_origin_b01_b10_audit.py) requires these exact 18
# source-PR CI step names and the 3 receipt-PR step names, each present and concluding "success"
# on the exact PR head. This guard pins them in the committed workflow so a rename cannot drift the
# ci.yml away from the runner's REQUIRED_CI_STEPS / REQUIRED_RECEIPT_CI_STEPS without turning red.
_REQUIRED_SOURCE_CI_STEPS = (
    "Checkout exact head",
    "Bind checks to exact event head",
    "Set up Python 3.11",
    "Install test toolchain",
    "Falsification suite",
    "Hash-order invariance",
    "Exact pytest collection identity",
    "Contract byte manifest",
    "Contract manifest schema",
    "Reproducible source and wheel artifacts",
    "Installed-wheel contract smoke",
    "OFF capability boundary",
    "End-to-end audit walk",
    "Build ledger currency",
    "Combined RC3+RC4 composition DAG",
    "Strict B-series receipt chain",
    "Spec/control count reconciliation",
    "Tracked secret scan",
)
_REQUIRED_RECEIPT_CI_STEPS = (
    "Checkout exact head",
    "Bind checks to exact event head",
    "Receipt authentication",
)


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
    assert "fetch-depth: 2" in workflow
    assert "ref: ${{ github.event.pull_request.head.sha || github.sha }}" in workflow
    assert "ref: ${{ github.head_ref || github.sha }}" not in workflow

    # Every runner-required step name is present exactly once (a required 'skipped' fails the audit;
    # a duplicate would multiply the required conclusions).
    step_names = re.findall(r"^\s*- name:\s*(.+?)\s*$", workflow, re.MULTILINE)
    for name in _REQUIRED_SOURCE_CI_STEPS:
        assert step_names.count(name) == 1, name
    for name in _REQUIRED_RECEIPT_CI_STEPS:
        assert step_names.count(name) == 1, name

    # The renamed capability boundary and receipt-authentication steps and their commands.
    assert "name: OFF capability boundary" in workflow
    assert "name: DARK capability boundary" not in workflow
    assert "run: python tools/verify_no_forbidden_capabilities.py" in workflow
    assert "run: python tools/verify_spec_control_counts.py --strict" in workflow
    assert "run: python tools/scan_secrets.py --tracked --fail-on-hit" in workflow
    # The strict B-series receipt chain step and the receipt-authentication step run the same
    # legacy-tolerant validator, unconditionally, so both PR classes stay green on a valid tree.
    assert workflow.count("run: python tools/validate_b_receipt.py --all --strict") == 2

    # The R00-only receipt-branch machinery is retired: no required-named step carries an `if:`
    # that could yield a 'skipped' conclusion, and there is no milestone-specific receipt gate.
    assert "name: Establish receipt evidence branch" not in workflow
    assert "git switch --force-create evidence/r00-receipt" not in workflow
    assert "hashFiles('evidence/receipts/R00.json')" not in workflow
    assert "validate_milestone_receipt.py" not in workflow
    assert "\n        if:" not in workflow and "\n      if:" not in workflow


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
