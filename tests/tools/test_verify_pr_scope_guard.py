"""CO-12 — tests for the governance-only PR scope guard (fail-closed on every ambiguity)."""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import verify_pr_scope_guard as guard  # noqa: E402


GOVERNANCE_PATHS = [
    "docs/control/milestone_registry.v1.json",
    "docs/governance/README.md",
    "tools/verify_milestone_registry.py",
    "tests/tools/test_milestone_registry.py",
]


def test_governance_only_clean_set_passes() -> None:
    assert guard.evaluate("governance-only", GOVERNANCE_PATHS) == []


@pytest.mark.parametrize(
    ("path", "deny"),
    [
        ("src/triad_origin/structures/reaction.py", "FORMULA_MODULE"),
        ("src/triad_origin/features.py", "FORMULA_MODULE"),
        ("src/triad_origin/instrument_math_v2.py", "FORMULA_MODULE"),
        ("src/triad_origin/config/signed_bundle.py", "FORMULA_MODULE"),
        ("contracts/schemas/some.schema.json", "FORMULA_MODULE"),
        ("contracts/read_faces/catalog.v1.json", "B08_FACE"),
        ("src/triad_origin/control/shadow_health.py", "B08_FACE"),
        ("contracts/adoption/B08.manifest.v1.json", "B08_FACE"),
        ("evidence/B08/anything.json", "B08_FACE"),
        ("docs/runbooks/B09_DR.md", "B09_ARTIFACT"),
        ("contracts/adoption/B09.manifest.v1.json", "B09_ARTIFACT"),
        ("evidence/receipts/B09.receipt.v4.json", "B09_ARTIFACT"),
    ],
)
def test_denied_path_fails_governance_only(path: str, deny: str) -> None:
    violations = guard.evaluate("governance-only", GOVERNANCE_PATHS + [path])
    assert len(violations) == 1
    assert violations[0].startswith(f"{deny}: {path}")


def test_every_violation_is_reported_not_only_the_first() -> None:
    violations = guard.evaluate(
        "governance-only",
        ["src/triad_origin/features.py", "docs/runbooks/B09_DR.md"],
    )
    assert len(violations) == 2


def test_non_governance_class_applies_no_deny_set_here() -> None:
    assert guard.evaluate("non-governance", ["src/triad_origin/features.py"]) == []


def test_unknown_class_refuses_fail_closed() -> None:
    with pytest.raises(guard.ScopeGuardError, match="unknown PR class"):
        guard.evaluate("formula-repair", GOVERNANCE_PATHS)


def test_empty_path_set_refuses() -> None:
    with pytest.raises(guard.ScopeGuardError, match="empty changed-path set"):
        guard.evaluate("governance-only", [])


@pytest.mark.parametrize("path", ["/etc/passwd", "../escape.py", "a\\b.py", "a/../b.py", ""])
def test_unsafe_path_refuses(path: str) -> None:
    with pytest.raises(guard.ScopeGuardError, match="unsafe path|empty"):
        guard.evaluate("governance-only", [path] if path else [path])


def test_main_paths_file_exit_codes(tmp_path: pathlib.Path) -> None:
    clean = tmp_path / "clean.txt"
    clean.write_text("\n".join(GOVERNANCE_PATHS) + "\n", encoding="utf-8")
    assert guard.main(["--pr-class", "governance-only", "--paths", str(clean)]) == 0
    dirty = tmp_path / "dirty.txt"
    dirty.write_text("src/triad_origin/structures/capsules.py\n", encoding="utf-8")
    assert guard.main(["--pr-class", "governance-only", "--paths", str(dirty)]) == 1
    assert guard.main(["--pr-class", "bogus", "--paths", str(clean)]) == 2


def test_main_missing_paths_file_is_a_refusal(tmp_path: pathlib.Path) -> None:
    absent = tmp_path / "absent.txt"
    assert guard.main(["--pr-class", "governance-only", "--paths", str(absent)]) == 2


def test_bad_diff_range_is_a_refusal() -> None:
    rc = guard.main(
        ["--pr-class", "governance-only", "--diff-range", "no-such-ref..also-none", "--root", str(ROOT)]
    )
    assert rc == 2
