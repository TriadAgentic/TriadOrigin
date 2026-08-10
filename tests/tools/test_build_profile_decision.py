"""Tests for tools/build_profile_decision.py against the frozen runner's ratified profile."""

from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

TOOL_NAME = "build_profile_decision.py"


def _emit(run_tool, out_path: pathlib.Path) -> str:
    proc = run_tool(TOOL_NAME, "--out", str(out_path))
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


class TestBytesLaw:
    def test_bytes_hash_stable_across_runs(self, run_tool, tmp_path: pathlib.Path) -> None:
        first = tmp_path / "one.json"
        second = tmp_path / "two.json"
        sha_one = _emit(run_tool, first)
        sha_two = _emit(run_tool, second)
        assert first.read_bytes() == second.read_bytes()
        assert sha_one == sha_two == hashlib.sha256(first.read_bytes()).hexdigest()

    def test_stdout_is_exactly_the_file_sha256(self, run_tool, tmp_path: pathlib.Path) -> None:
        out = tmp_path / "decision.json"
        printed = _emit(run_tool, out)
        assert printed == hashlib.sha256(out.read_bytes()).hexdigest()
        assert len(printed) == 64 and set(printed) <= set("0123456789abcdef")

    def test_serialization_is_the_documented_ceremony_bytes(
            self, run_tool, tmp_path: pathlib.Path, frozen_runner) -> None:
        out = tmp_path / "decision.json"
        _emit(run_tool, out)
        expected = (json.dumps(
            frozen_runner.SUPPORTED_RECEIPT_PROFILE_DECISION, sort_keys=True, indent=2,
        ) + "\n").encode("utf-8")
        assert out.read_bytes() == expected


class TestDifferentialAgainstFrozenRunner:
    def test_content_equals_runner_supported_profile_exactly(
            self, run_tool, tmp_path: pathlib.Path, frozen_runner) -> None:
        out = tmp_path / "decision.json"
        _emit(run_tool, out)
        emitted = json.loads(out.read_text(encoding="utf-8"))
        expected = frozen_runner.SUPPORTED_RECEIPT_PROFILE_DECISION
        assert emitted == expected
        assert set(emitted) == set(expected)
        for key, value in expected.items():
            assert emitted[key] == value, f"profile decision key {key} diverged"

    def test_runner_profile_validator_accepts_the_emitted_file(
            self, run_tool, tmp_path: pathlib.Path, frozen_runner) -> None:
        out = tmp_path / "decision.json"
        printed_sha = _emit(run_tool, out)
        issues = frozen_runner.receipt_profile_decision_issues(out, printed_sha)
        assert issues == []

    def test_runner_profile_validator_rejects_a_wrong_pin(
            self, run_tool, tmp_path: pathlib.Path, frozen_runner) -> None:
        out = tmp_path / "decision.json"
        _emit(run_tool, out)
        issues = frozen_runner.receipt_profile_decision_issues(out, "1" * 64)
        assert any("do not match the external pin" in issue for issue in issues)

    def test_tool_constant_mirrors_runner_constant(self, tool_profile, frozen_runner) -> None:
        assert tool_profile.RECEIPT_PROFILE_DECISION == \
            frozen_runner.SUPPORTED_RECEIPT_PROFILE_DECISION
        assert tool_profile.MAX_RECEIPT_TTL_US == frozen_runner.MAX_RECEIPT_TTL_US
        assert tool_profile.REPOSITORY_FUTURE_TOLERANCE_US == \
            frozen_runner.REPOSITORY_FUTURE_TOLERANCE_US
        assert tool_profile.RECEIPT_PAYLOAD_TYPE == frozen_runner.RECEIPT_PAYLOAD_TYPE
        assert tool_profile.EXPECTED_REPOSITORY == frozen_runner.EXPECTED_REPOSITORY


class TestTreeMutationLaw:
    def test_refuses_out_inside_its_repo_root_by_default(self, run_tool, repo_root) -> None:
        target = repo_root / "tmp_should_never_exist.json"
        proc = run_tool(TOOL_NAME, "--out", str(target))
        assert proc.returncode == 2
        assert "OUT_PATH_INSIDE_REPOSITORY" in proc.stderr
        assert not target.exists()

    def test_allow_in_repo_overrides_for_a_deliberate_ceremony_write(
            self, tmp_path: pathlib.Path, tools_dir) -> None:
        fake_repo = tmp_path / "fakerepo"
        (fake_repo / "tools").mkdir(parents=True)
        staged_tool = fake_repo / "tools" / TOOL_NAME
        shutil.copy2(tools_dir / TOOL_NAME, staged_tool)
        inside = fake_repo / "decision.json"
        refused = subprocess.run(
            [sys.executable, str(staged_tool), "--out", str(inside)],
            text=True, capture_output=True, timeout=60, check=False)
        assert refused.returncode == 2
        assert "OUT_PATH_INSIDE_REPOSITORY" in refused.stderr
        assert not inside.exists()
        allowed = subprocess.run(
            [sys.executable, str(staged_tool), "--out", str(inside), "--allow-in-repo"],
            text=True, capture_output=True, timeout=60, check=False)
        assert allowed.returncode == 0, allowed.stderr
        assert inside.is_file()
