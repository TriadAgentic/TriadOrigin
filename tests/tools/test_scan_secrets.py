"""Tests for tools/scan_secrets.py -- differential against the frozen audit runner.

The frozen runner ``audit_package/triad_origin_b01_b10_audit.py`` (v1.2.0, SHA-256
pinned below) is the single source of truth for the scan law.  These tests load it
via ``importlib.util.spec_from_file_location`` (after asserting its ``__main__``
guard) and pin byte-equality of every extracted constant, plus byte-equality of the
tool's CLI output against a literal re-execution of the runner's own scan loop.

Fixture "secrets" are assembled from fragments at runtime so that this test file
itself never contains a matchable literal -- this file will later be a tracked
repository file and must scan clean (asserted below).
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import pathlib
import shutil
import subprocess
import sys
from types import ModuleType

import pytest

# Dynamic imports below must never write bytecode caches into the repository
# (the fresh-clone tree-mutation law: audit_package/ and tools/ must stay clean).
sys.dont_write_bytecode = True

FROZEN_RUNNER_SHA256 = "12c8896479b902165fa2c6d3e7565ea8402b49fcfe2d044f6fd69153926d35a2"
EXPECTED_PATTERN_COUNT = 17
EXPECTED_PATTERN_NAMES = (
    "authorization_bearer",
    "bearer",
    "query_token",
    "github_token",
    "triad_mcp_token",
    "authorization_basic",
    "cookie_header",
    "session_assignment",
    "openai_token",
    "stripe_token",
    "slack_token",
    "gitlab_token",
    "jwt",
    "aws_access_key",
    "uri_userinfo",
    "secret_assignment",
    "private_key",
)

_ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL_PATH = _ROOT / "tools" / "scan_secrets.py"
_RUNNER_CANDIDATES = (
    _ROOT / "audit_package" / "triad_origin_b01_b10_audit.py",
    pathlib.Path("/home/user/TriadOrigin/audit_package/triad_origin_b01_b10_audit.py"),
)

_PY_ENV = {
    "PATH": os.environ.get("PATH", ""),
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "PYTHONDONTWRITEBYTECODE": "1",
}

_MODULE_CACHE: dict[str, ModuleType] = {}


def _runner_path() -> pathlib.Path:
    for candidate in _RUNNER_CANDIDATES:
        if candidate.is_file():
            return candidate
    # Sibling-or-skip: the frozen runner is untracked (audit_package/ gitignored), so it is
    # absent in a fresh clone and present only when deployed beside the repo.
    pytest.skip("frozen audit runner not found at any known location (audit_package/ untracked)")


def _load_module(path: pathlib.Path, name: str) -> ModuleType:
    if name in _MODULE_CACHE:
        return _MODULE_CACHE[name]
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec: the runner's dataclasses resolve string annotations
    # through sys.modules[cls.__module__] at class-creation time.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    _MODULE_CACHE[name] = module
    return module


def _load_runner() -> ModuleType:
    path = _runner_path()
    source = path.read_text(encoding="utf-8")
    # Importing must not execute main -- require the guard before exec_module.
    assert 'if __name__ == "__main__":' in source
    return _load_module(path, "frozen_audit_runner_under_test")


def _load_tool() -> ModuleType:
    return _load_module(TOOL_PATH, "scan_secrets_under_test")


def _j(*parts: str) -> str:
    """Assemble fixture strings at runtime so this source never holds a matchable literal."""
    return "".join(parts)


# Fixture payloads (fragment-assembled; see _j docstring).
AUTH_LINE = _j("Auth", "orization: ", "Bea", "rer ", "t" * 24)
AWS_LINE = _j("AK", "IA", "C" * 16)
GH_LINE = _j("gh", "p_", "A" * 24)
SA_LINE = _j("pass", "word = ", "q" * 16)
PK_BLOCK = _j(
    "-----BEG", "IN PRIV", "ATE KEY-----", "\n",
    "MIIfakefakefake", "\n",
    "-----E", "ND PRIV", "ATE KEY-----",
)


def _run_git(repo: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(_PY_ENV)
    env["HOME"] = str(repo.parent)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    result = subprocess.run(
        ["git", "-C", str(repo), *args], text=True, capture_output=True,
        env=env, check=False)
    return result


def _make_repo(tmp_path: pathlib.Path, files: dict[str, bytes]) -> pathlib.Path:
    repo = tmp_path / "fixture"
    (repo / "tools").mkdir(parents=True)
    shutil.copyfile(TOOL_PATH, repo / "tools" / "scan_secrets.py")
    init = _run_git(repo, "init", "-q")
    assert init.returncode == 0, init.stderr
    for rel, data in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    add = _run_git(repo, "add", "-A")
    assert add.returncode == 0, add.stderr
    return repo


def _run_cli(repo: pathlib.Path, *flags: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(repo / "tools" / "scan_secrets.py"), *flags],
        cwd=str(repo), text=True, capture_output=True, env=_PY_ENV, check=False)


def _dirty_files() -> dict[str, bytes]:
    return {
        "config/example.toml": (GH_LINE + "\n").encode(),
        "deploy/settings.ini": (SA_LINE + "\n").encode(),
        "keys/dev.txt": (PK_BLOCK + "\n").encode(),
        "notes.md": ("benign line\n" + AUTH_LINE + "\n" + AWS_LINE + "\n").encode(),
    }


DIRTY_EXPECTED_LINES = (
    "github_token\tconfig/example.toml",
    "secret_assignment\tdeploy/settings.ini",
    "private_key\tkeys/dev.txt",
    "authorization_bearer\tnotes.md",
    "bearer\tnotes.md",
    "aws_access_key\tnotes.md",
)


class TestFrozenRunnerFixture:
    def test_runner_is_present_sha_pinned_and_main_guarded(self) -> None:
        path = _runner_path()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == FROZEN_RUNNER_SHA256
        assert 'if __name__ == "__main__":' in path.read_text(encoding="utf-8")


class TestPatternLawDifferential:
    def test_pattern_count_is_17_in_both(self) -> None:
        tool, runner = _load_tool(), _load_runner()
        assert len(tool.SECRET_PATTERNS) == EXPECTED_PATTERN_COUNT
        assert len(runner.SECRET_PATTERNS) == EXPECTED_PATTERN_COUNT

    def test_pattern_names_match_runner_in_order(self) -> None:
        tool, runner = _load_tool(), _load_runner()
        tool_names = tuple(name for name, _ in tool.SECRET_PATTERNS)
        runner_names = tuple(name for name, _ in runner.SECRET_PATTERNS)
        assert tool_names == runner_names == EXPECTED_PATTERN_NAMES

    def test_every_regex_is_byte_equal_to_the_runner(self) -> None:
        tool, runner = _load_tool(), _load_runner()
        for (t_name, t_pat), (r_name, r_pat) in zip(
                tool.SECRET_PATTERNS, runner.SECRET_PATTERNS, strict=True):
            assert t_name == r_name
            assert t_pat.pattern == r_pat.pattern
            assert t_pat.pattern.encode("utf-8") == r_pat.pattern.encode("utf-8")
            assert t_pat.flags == r_pat.flags

    def test_text_suffixes_match_runner_exactly(self) -> None:
        tool, runner = _load_tool(), _load_runner()
        assert tool.TEXT_SUFFIXES == runner.TEXT_SUFFIXES

    def test_size_ceiling_matches_runner_filter_line(self) -> None:
        tool = _load_tool()
        assert tool.MAX_TEXT_FILE_BYTES == 8_000_000
        runner_source = _runner_path().read_text(encoding="utf-8")
        assert "st_size > 8_000_000" in runner_source


class TestCliOnFixtureRepos:
    def test_dirty_fixture_exact_hit_lines_and_exit_1(self, tmp_path: pathlib.Path) -> None:
        repo = _make_repo(tmp_path, _dirty_files())
        result = _run_cli(repo, "--tracked", "--fail-on-hit")
        assert result.returncode == 1
        assert result.stdout == "".join(line + "\n" for line in DIRTY_EXPECTED_LINES)
        assert result.stderr == "scan_secrets: scanned 5 tracked text files, 6 hit(s)\n"

    def test_dirty_fixture_without_fail_flag_prints_hits_but_exits_0(
            self, tmp_path: pathlib.Path) -> None:
        repo = _make_repo(tmp_path, _dirty_files())
        result = _run_cli(repo, "--tracked")
        assert result.returncode == 0
        assert result.stdout == "".join(line + "\n" for line in DIRTY_EXPECTED_LINES)

    def test_dirty_fixture_stdout_byte_equals_runner_scan_loop(
            self, tmp_path: pathlib.Path) -> None:
        repo = _make_repo(tmp_path, _dirty_files())
        runner = _load_runner()
        lines: list[str] = []
        for path in runner.tracked_files(repo):
            relative = path.relative_to(repo)
            if path.suffix.lower() not in runner.TEXT_SUFFIXES or not path.is_file() \
                    or path.stat().st_size > 8_000_000:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for name, pattern in runner.SECRET_PATTERNS:
                if pattern.search(text):
                    lines.append(f"{name}\t{relative}")
        result = _run_cli(repo, "--tracked", "--fail-on-hit")
        assert result.stdout.encode("utf-8") == "".join(
            line + "\n" for line in lines).encode("utf-8")
        assert lines, "differential fixture must produce hits"

    def test_clean_fixture_exits_0_with_empty_stdout(self, tmp_path: pathlib.Path) -> None:
        repo = _make_repo(tmp_path, {"README.md": b"clean readme\n"})
        result = _run_cli(repo, "--tracked", "--fail-on-hit")
        assert result.returncode == 0
        assert result.stdout == ""
        assert result.stderr == "scan_secrets: scanned 2 tracked text files, 0 hit(s)\n"

    def test_oversize_and_non_text_skipped_boundary_scanned(
            self, tmp_path: pathlib.Path) -> None:
        marker = (AWS_LINE + "\n").encode()
        files = {
            "big.md": marker + b"x" * (8_000_001 - len(marker)),
            "creds.bin": marker,
            "edge.md": marker + b"x" * (8_000_000 - len(marker)),
        }
        assert len(files["big.md"]) == 8_000_001
        assert len(files["edge.md"]) == 8_000_000
        repo = _make_repo(tmp_path, files)
        result = _run_cli(repo, "--tracked", "--fail-on-hit")
        assert result.returncode == 1
        assert result.stdout == "aws_access_key\tedge.md\n"

    def test_missing_tracked_flag_is_rejected_exit_2(self, tmp_path: pathlib.Path) -> None:
        repo = _make_repo(tmp_path, {"README.md": b"clean readme\n"})
        result = _run_cli(repo, "--fail-on-hit")
        assert result.returncode == 2

    def test_unknown_mode_is_rejected_exit_2(self, tmp_path: pathlib.Path) -> None:
        repo = _make_repo(tmp_path, {"README.md": b"clean readme\n"})
        result = _run_cli(repo, "--tracked", "--untracked")
        assert result.returncode == 2

    def test_outside_a_git_repo_fails_loudly_exit_2(self, tmp_path: pathlib.Path) -> None:
        bare = tmp_path / "norepo"
        (bare / "tools").mkdir(parents=True)
        shutil.copyfile(TOOL_PATH, bare / "tools" / "scan_secrets.py")
        result = _run_cli(bare, "--tracked", "--fail-on-hit")
        assert result.returncode == 2
        assert result.stdout == ""
        assert "error" in result.stderr

    def test_tool_run_mutates_nothing_in_the_tree(self, tmp_path: pathlib.Path) -> None:
        repo = _make_repo(tmp_path, _dirty_files())
        before = _run_git(repo, "status", "--porcelain=v1", "--ignored=matching")
        assert before.returncode == 0
        _run_cli(repo, "--tracked", "--fail-on-hit")
        after = _run_git(repo, "status", "--porcelain=v1", "--ignored=matching")
        assert after.returncode == 0
        assert before.stdout == after.stdout
        assert list(repo.rglob("__pycache__")) == []


class TestSelfReference:
    def test_tool_source_never_hits_its_own_patterns(self) -> None:
        tool = _load_tool()
        assert tool.scan_text(TOOL_PATH.read_text(encoding="utf-8")) == []

    def test_this_test_source_never_hits_the_patterns(self) -> None:
        tool = _load_tool()
        own = pathlib.Path(__file__).resolve().read_text(encoding="utf-8")
        assert tool.scan_text(own) == []

    def test_frozen_runner_source_known_self_hit_is_exactly_one(self) -> None:
        # Experiment record: the frozen runner's vendored source trips exactly one
        # pattern -- not via its pattern definitions (those interpose regex
        # metacharacters and cannot match their own spelling) but via the
        # ``start_new_session=(...)`` keyword argument at its line 3794.
        tool = _load_tool()
        runner_source = _runner_path().read_text(encoding="utf-8")
        assert tool.scan_text(runner_source) == ["session_assignment"]
