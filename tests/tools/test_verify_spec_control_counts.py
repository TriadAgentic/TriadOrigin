"""Tests for tools/verify_spec_control_counts.py against the REAL read-only repo.

The repository at /home/user/TriadOrigin is READ-ONLY: every subprocess run here uses a
cwd OUTSIDE the repo, and the repo's ``git status --porcelain --ignored=matching`` is
captured before and compared after each run to prove nothing was created or mutated.

Differential tests load the frozen audit runner module
(audit_package/triad_origin_b01_b10_audit.py) from its file path via
``importlib.util.spec_from_file_location`` — after first asserting it carries an
``if __name__ == "__main__"`` guard, so importing never executes ``main`` — and assert
the tool's stdout is byte-equal to the runner's own expected payload and accepted by the
runner's ``spec_control_count_output_issues``.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
from types import ModuleType

import pytest

# Never write __pycache__ next to imported sources (the runner lives INSIDE the
# read-only repo; caching its bytecode would mutate the tree).
sys.dont_write_bytecode = True

REPO = pathlib.Path(__file__).resolve().parents[2]
RUNNER_PATH = REPO / "audit_package" / "triad_origin_b01_b10_audit.py"
RUNNER_SHA256 = "12c8896479b902165fa2c6d3e7565ea8402b49fcfe2d044f6fd69153926d35a2"
STAGING = REPO
TOOL_PATH = STAGING / "tools" / "verify_spec_control_counts.py"

EXPECTED_PAYLOAD = {
    "schema": "triad.origin.spec_control_counts.v1",
    "rc1_test_count": 408,
    "rc3_effective_verification_count": 1523,
    "rc4_fixture_count": 125,
}


def _load_module(path: pathlib.Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def tool() -> ModuleType:
    return _load_module(TOOL_PATH, "b0r_verify_spec_control_counts")


@pytest.fixture(scope="module")
def runner() -> ModuleType:
    import hashlib

    # Sibling-or-skip: the frozen runner is untracked (audit_package/ gitignored), so it is
    # absent in a fresh clone and present only when deployed beside the repo.
    if not RUNNER_PATH.is_file():
        pytest.skip(
            "frozen audit runner absent (audit_package/ untracked); differential runs only "
            "when the runner is deployed beside the repo")
    source_bytes = RUNNER_PATH.read_bytes()
    assert hashlib.sha256(source_bytes).hexdigest() == RUNNER_SHA256, (
        "frozen runner bytes do not match the pinned SHA-256; refuse to trust it"
    )
    # Guard: importing must not execute main.
    assert 'if __name__ == "__main__":' in source_bytes.decode("utf-8")
    assert sys.dont_write_bytecode is True  # never cache bytecode inside the repo
    return _load_module(RUNNER_PATH, "b0r_frozen_audit_runner")


def _repo_status() -> str:
    proc = subprocess.run(
        ["git", "-C", str(REPO), "status", "--porcelain", "--ignored=matching"],
        text=True,
        capture_output=True,
        check=True,
        timeout=120,
    )
    return proc.stdout


def _run_tool(tree: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run the staged tool from ``tree`` with cwd OUTSIDE the repo; prove the repo
    tree (including ignored/untracked files) is byte-identical before and after."""
    script = (tree / "tools" / "verify_spec_control_counts.py").resolve()
    before = _repo_status()
    with tempfile.TemporaryDirectory(prefix="b0r-cwd-") as cwd:
        proc = subprocess.run(
            [sys.executable, str(script), *args],
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=300,
            check=False,
        )
    after = _repo_status()
    assert after == before, f"tool subprocess mutated the read-only repo: {after!r}"
    return proc


def _stage_tree(tmp: pathlib.Path) -> pathlib.Path:
    (tmp / "tools").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(TOOL_PATH, tmp / "tools" / "verify_spec_control_counts.py")
    return tmp


def _real_docs_tree(tmp: pathlib.Path) -> pathlib.Path:
    """Repo-relative layout whose docs/ is a read-only symlink to the real repo docs."""
    _stage_tree(tmp)
    (tmp / "docs").symlink_to(REPO / "docs", target_is_directory=True)
    return tmp


# ---------------------------------------------------------------------------
# Honest derivation against the real repository (read-only).
# ---------------------------------------------------------------------------


def test_derived_values_match_the_pins_against_the_real_repo(tool: ModuleType) -> None:
    assert tool.derive_rc1_test_count(REPO) == 408
    assert tool.derive_rc3_effective_verification_count(REPO) == 1523
    assert tool.derive_rc4_fixture_count(REPO) == 125
    assert tool.derive_counts(REPO) == EXPECTED_PAYLOAD
    # The named pins the --strict comparison uses.
    assert tool.EXPECTED_RC1_TEST_COUNT == 408
    assert tool.EXPECTED_RC3_EFFECTIVE_VERIFICATION_COUNT == 1523
    assert tool.EXPECTED_RC4_FIXTURE_COUNT == 125


def test_strict_subprocess_emits_exactly_one_json_object_and_exit_zero(
    tmp_path: pathlib.Path,
) -> None:
    tree = _real_docs_tree(tmp_path)
    proc = _run_tool(tree, "--strict")
    assert proc.returncode == 0, proc.stderr
    assert proc.stderr == ""
    # The whole stdout parses as ONE JSON document (surrounding whitespace only).
    assert json.loads(proc.stdout) == EXPECTED_PAYLOAD
    # Byte-exact: one line, one trailing newline, nothing else.
    assert proc.stdout == json.dumps(EXPECTED_PAYLOAD) + "\n"


# ---------------------------------------------------------------------------
# Differential tests against the frozen runner module.
# ---------------------------------------------------------------------------


def test_runner_accepts_the_tool_stdout_and_rejects_a_wrong_value(
    tmp_path: pathlib.Path, runner: ModuleType
) -> None:
    tree = _real_docs_tree(tmp_path)
    proc = _run_tool(tree, "--strict")
    assert proc.returncode == 0, proc.stderr
    assert runner.spec_control_count_output_issues(proc.stdout) == []
    wrong = json.loads(proc.stdout)
    wrong["rc4_fixture_count"] -= 1
    assert runner.spec_control_count_output_issues(json.dumps(wrong))


def test_tool_stdout_is_byte_equal_to_the_runner_constant_payload(
    tmp_path: pathlib.Path, runner: ModuleType
) -> None:
    # Mirrors the runner's own self-test payload construction (runner ~L5218-5223).
    runner_payload = json.dumps(
        {
            "schema": "triad.origin.spec_control_counts.v1",
            "rc1_test_count": runner.EXPECTED_RC1_TEST_COUNT,
            "rc3_effective_verification_count": runner.EXPECTED_EFFECTIVE_COUNTS[
                "effective_verification_count"
            ],
            "rc4_fixture_count": runner.EXPECTED_RC4_FIXTURE_COUNT,
        }
    )
    tree = _real_docs_tree(tmp_path)
    proc = _run_tool(tree, "--strict")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == runner_payload


def test_strict_json_loads_matches_the_runner_law(
    tool: ModuleType, runner: ModuleType
) -> None:
    duplicate = '{"a": 1, "a": 2}'
    with pytest.raises(tool.DuplicateJSONKey):
        tool.strict_json_loads(duplicate)
    with pytest.raises(runner.DuplicateJSONKey):
        runner.strict_json_loads(duplicate)
    clean = '{"verifications": [1, 2, 3], "n": 3}'
    assert tool.strict_json_loads(clean) == runner.strict_json_loads(clean)
    non_finite = '{"x": NaN}'
    with pytest.raises(json.JSONDecodeError):
        tool.strict_json_loads(non_finite)
    with pytest.raises(json.JSONDecodeError):
        runner.strict_json_loads(non_finite)


# ---------------------------------------------------------------------------
# Failure paths (temp fixtures only; the real repo is never touched).
# ---------------------------------------------------------------------------


def test_duplicate_json_key_in_a_temp_bundle_is_refused(
    tmp_path: pathlib.Path, tool: ModuleType
) -> None:
    tree = _stage_tree(tmp_path)
    control = tree / "docs" / "control"
    control.mkdir(parents=True)
    (control / "rc3_effective_control_bundle.json").write_text(
        '{"verifications": [], "verifications": []}', encoding="utf-8"
    )
    with pytest.raises(tool.CountDerivationError) as excinfo:
        tool.derive_rc3_effective_verification_count(tree)
    assert "duplicate JSON object key" in str(excinfo.value)


def test_missing_files_exit_nonzero_with_empty_stdout(tmp_path: pathlib.Path) -> None:
    tree = _stage_tree(tmp_path)  # no docs/ at all
    proc = _run_tool(tree, "--strict")
    assert proc.returncode == 1
    assert proc.stdout == ""
    error = json.loads(proc.stderr)
    assert error["schema"] == "triad.origin.spec_control_counts.error.v1"
    assert "missing" in error["error"]
    assert proc.stderr.count("\n") == 1  # single-line JSON error object


def test_absent_kpi_exits_nonzero_with_empty_stdout(tmp_path: pathlib.Path) -> None:
    tree = _stage_tree(tmp_path)
    spec_dir = tree / "docs" / "spec"
    spec_dir.mkdir(parents=True)
    (spec_dir / "08_TRIAD_ORIGIN_V7_VERIFICATION_MATRIX_1.0.0_RC1.html").write_text(
        "<html><body><h1>no KPI block here</h1></body></html>", encoding="utf-8"
    )
    (tree / "docs" / "control").symlink_to(
        REPO / "docs" / "control", target_is_directory=True
    )
    proc = _run_tool(tree, "--strict")
    assert proc.returncode == 1
    assert proc.stdout == ""
    error = json.loads(proc.stderr)
    assert "absent" in error["error"]


def test_ambiguous_kpi_exits_nonzero_with_empty_stdout(tmp_path: pathlib.Path) -> None:
    tree = _stage_tree(tmp_path)
    spec_dir = tree / "docs" / "spec"
    spec_dir.mkdir(parents=True)
    block = '<div class="kpi">408</div><h3>Total target tests</h3>'
    (spec_dir / "08_TRIAD_ORIGIN_V7_VERIFICATION_MATRIX_1.0.0_RC1.html").write_text(
        f"<html><body>{block}{block}</body></html>", encoding="utf-8"
    )
    (tree / "docs" / "control").symlink_to(
        REPO / "docs" / "control", target_is_directory=True
    )
    proc = _run_tool(tree, "--strict")
    assert proc.returncode == 1
    assert proc.stdout == ""
    error = json.loads(proc.stderr)
    assert "ambiguous" in error["error"]


def test_strict_mismatch_fails_loud_while_nonstrict_derives_honestly(
    tmp_path: pathlib.Path,
) -> None:
    tree = _stage_tree(tmp_path)
    spec_dir = tree / "docs" / "spec"
    spec_dir.mkdir(parents=True)
    (spec_dir / "08_TRIAD_ORIGIN_V7_VERIFICATION_MATRIX_1.0.0_RC1.html").symlink_to(
        REPO / "docs" / "spec" / "08_TRIAD_ORIGIN_V7_VERIFICATION_MATRIX_1.0.0_RC1.html"
    )
    control = tree / "docs" / "control"
    control.mkdir(parents=True)
    (control / "rc3_effective_control_bundle.json").symlink_to(
        REPO / "docs" / "control" / "rc3_effective_control_bundle.json"
    )
    (control / "rc4_control_bundle.json").write_text(
        json.dumps({"verifications": [1, 2, 3]}), encoding="utf-8"
    )
    strict = _run_tool(tree, "--strict")
    assert strict.returncode == 1
    assert strict.stdout == ""
    error = json.loads(strict.stderr)
    assert "rc4_fixture_count" in error["error"]
    # Non-strict: derived values are printed as measured — proof the tool derives
    # rather than hardcode-and-print.
    loose = _run_tool(tree)
    assert loose.returncode == 0
    value = json.loads(loose.stdout)
    assert value["rc4_fixture_count"] == 3
    assert value["rc1_test_count"] == 408
    assert value["rc3_effective_verification_count"] == 1523


def test_kpi_regex_tolerates_attribute_and_whitespace_variance(
    tmp_path: pathlib.Path, tool: ModuleType
) -> None:
    tree = _stage_tree(tmp_path)
    spec_dir = tree / "docs" / "spec"
    spec_dir.mkdir(parents=True)
    variant = (
        "<div id='x' class='stat kpi wide' data-k=\"1\">\n  408 \n</div>\n"
        "<h3 class=\"lbl\"> Total  target\ttests </h3>"
    )
    (spec_dir / "08_TRIAD_ORIGIN_V7_VERIFICATION_MATRIX_1.0.0_RC1.html").write_text(
        f"<html><body>{variant}</body></html>", encoding="utf-8"
    )
    assert tool.derive_rc1_test_count(tree) == 408


def test_repo_root_resolution_is_script_relative_not_cwd(tool: ModuleType) -> None:
    assert tool.repo_root_from_script() == TOOL_PATH.resolve().parent.parent
