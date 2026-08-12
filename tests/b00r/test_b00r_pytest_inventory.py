"""Adversarial coverage for B00R pytest-inventory output isolation."""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import pytest

from tools import b00r_pytest_inventory as inventory


RUN_ID = "a" * 32
SOURCE = "b" * 40


def test_inventory_script_runs_directly_with_safe_path(tmp_path):
    project = tmp_path / "project"
    tests = project / "tests"
    output = tmp_path / "output"
    tests.mkdir(parents=True)
    output.mkdir()
    (tests / "test_example.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8"
    )
    ids_rel = "evidence/B00R_G2/clean_runner/tests/test_ids.seed0.txt"
    result_rel = "evidence/B00R_G2/clean_runner/tests/pytest.seed0.v1.json"
    (output / pathlib.PurePosixPath(ids_rel).parent).mkdir(parents=True)
    env = {
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "PYTHONSAFEPATH": "1",
        "TRIAD_B00R_RUN_ID": RUN_ID,
        "TRIAD_B00R_SOURCE_MERGE": SOURCE,
        "TRIAD_B00R_TEST_IDS_PATH": str(output / ids_rel),
        "TRIAD_B00R_TEST_RESULT_PATH": str(output / result_rel),
        "TRIAD_B00R_TEST_IDS_REL": ids_rel,
        "TRIAD_B00R_TEST_RESULT_REL": result_rel,
    }
    result = subprocess.run(
        [sys.executable, "-P", str(pathlib.Path(inventory.__file__))],
        cwd=project,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (output / ids_rel).read_text(encoding="utf-8") == (
        "tests/test_example.py::test_ok\n"
    )
    payload = json.loads((output / result_rel).read_bytes())
    assert payload["passed"] == payload["collected"] == 1


def _configure_env(monkeypatch, output: pathlib.Path, seed: str = "0") -> None:
    ids_rel = f"evidence/B00R_G2/clean_runner/tests/test_ids.seed{seed}.txt"
    result_rel = f"evidence/B00R_G2/clean_runner/tests/pytest.seed{seed}.v1.json"
    values = {
        "TRIAD_B00R_RUN_ID": RUN_ID,
        "TRIAD_B00R_SOURCE_MERGE": SOURCE,
        "PYTHONHASHSEED": seed,
        "TRIAD_B00R_TEST_IDS_PATH": str(output / ids_rel),
        "TRIAD_B00R_TEST_RESULT_PATH": str(output / result_rel),
        "TRIAD_B00R_TEST_IDS_REL": ids_rel,
        "TRIAD_B00R_TEST_RESULT_REL": result_rel,
    }
    (output / pathlib.PurePosixPath(ids_rel).parent).mkdir(parents=True, exist_ok=True)
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_inventory_freezes_identity_and_paths_before_tests_can_mutate_env(
    tmp_path, monkeypatch
):
    output = tmp_path / "output"
    output.mkdir()
    _configure_env(monkeypatch, output)
    inventory.pytest_configure(None)
    original_ids = inventory._context["ids_path"]
    original_result = inventory._context["result_path"]

    monkeypatch.setenv("TRIAD_B00R_RUN_ID", "c" * 32)
    monkeypatch.setenv("TRIAD_B00R_SOURCE_MERGE", "d" * 40)
    monkeypatch.setenv("PYTHONHASHSEED", "1")
    monkeypatch.setenv("TRIAD_B00R_TEST_IDS_PATH", str(tmp_path / "escaped-ids"))
    monkeypatch.setenv("TRIAD_B00R_TEST_RESULT_PATH", str(tmp_path / "escaped-result"))
    inventory._node_ids = ["tests/test_example.py::test_ok"]
    inventory._outcomes = {
        "passed": 1, "skipped": 0, "xfailed": 0, "failed": 0, "errors": 0,
    }
    inventory.pytest_sessionfinish(None, 0)
    assert inventory._context["directory_fd"] == -1

    assert original_ids.read_text(encoding="utf-8") == "tests/test_example.py::test_ok\n"
    result = json.loads(original_result.read_bytes())
    assert result["run_id"] == RUN_ID
    assert result["source_merge_sha"] == SOURCE
    assert result["seed"] == 0
    assert not (tmp_path / "escaped-ids").exists()


def test_inventory_requires_both_outputs_under_same_derived_root(tmp_path, monkeypatch):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    _configure_env(monkeypatch, first)
    result_rel = os.environ["TRIAD_B00R_TEST_RESULT_REL"]
    monkeypatch.setenv("TRIAD_B00R_TEST_RESULT_PATH", str(second / result_rel))
    with pytest.raises(pytest.UsageError, match="do not share one output root"):
        inventory.pytest_configure(None)


def test_inventory_rejects_broken_final_symlink(tmp_path, monkeypatch):
    output = tmp_path / "output"
    output.mkdir()
    _configure_env(monkeypatch, output)
    ids = pathlib.Path(os.environ["TRIAD_B00R_TEST_IDS_PATH"])
    ids.parent.mkdir(parents=True, exist_ok=True)
    ids.symlink_to(tmp_path / "missing-target")
    assert os.path.lexists(ids)
    with pytest.raises(pytest.UsageError, match="contains symlink"):
        inventory.pytest_configure(None)


def test_inventory_temp_creation_refuses_preplanted_symlink(tmp_path, monkeypatch):
    target = tmp_path / "result.json"
    victim = tmp_path / "victim"
    victim.write_bytes(b"do-not-touch")
    monkeypatch.setattr(inventory.secrets, "token_hex", lambda _size: "fixed")
    temporary = tmp_path / ".result.json.tmp-fixed"
    temporary.symlink_to(victim)
    with pytest.raises(pytest.UsageError, match="atomic write failed"):
        inventory._atomic_write(target, b"captured")
    assert victim.read_bytes() == b"do-not-touch"
    assert not target.exists()


def test_inventory_frozen_dirfd_detects_parent_swap_without_writing_escape(
    tmp_path, monkeypatch
):
    output = tmp_path / "output"
    output.mkdir()
    _configure_env(monkeypatch, output)
    inventory.pytest_configure(None)
    tests_dir = inventory._context["directory_path"]
    assert isinstance(tests_dir, pathlib.Path)
    moved = tests_dir.with_name("tests-original")
    tests_dir.rename(moved)
    attacker = tmp_path / "attacker"
    attacker.mkdir()
    tests_dir.symlink_to(attacker, target_is_directory=True)
    inventory._node_ids = ["tests/test_example.py::test_ok"]
    inventory._outcomes = {
        "passed": 1, "skipped": 0, "xfailed": 0, "failed": 0, "errors": 0,
    }
    with pytest.raises(pytest.UsageError, match="directory identity changed"):
        inventory.pytest_sessionfinish(None, 0)
    assert list(attacker.iterdir()) == []
