"""R00 regression guards for immutable CI inputs."""

from __future__ import annotations

import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_ci_actions_are_sha_pinned_and_solver_uses_committed_constraints():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "actions/checkout@11d5960a326750d5838078e36cf38b85af677262" in workflow
    assert "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065" in workflow
    assert not re.search(r"uses:\s+actions/(?:checkout|setup-python)@v\\d", workflow)
    assert "PIP_CONSTRAINT: constraints/ci.txt" in workflow


def test_ci_constraint_snapshot_is_exact_and_unique():
    lines = [
        line.strip()
        for line in (ROOT / "constraints" / "ci.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert lines
    assert all(re.fullmatch(r"[A-Za-z0-9_.-]+==[^=\\s]+", line) for line in lines)
    names = [line.split("==", 1)[0].lower().replace("_", "-") for line in lines]
    assert len(names) == len(set(names))
    assert {"pytest", "jsonschema", "setuptools", "wheel"} <= set(names)
