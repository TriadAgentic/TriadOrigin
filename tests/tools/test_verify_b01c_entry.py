"""Falsification tests for the physical B00R-to-B01C entry gate."""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from triad_origin.canonical import canonical_json
from tools import verify_b01c_entry


HEAD = "d" * 40
SOURCE = "c" * 40
PIN = "a" * 64


def _write_receipt(root: pathlib.Path, **payload_updates) -> None:
    path = root / verify_b01c_entry.CANONICAL_RECEIPT
    path.parent.mkdir(parents=True)
    payload = {
        "milestone": "B00R",
        "repair_generation": 2,
        "source_merge_sha": SOURCE,
    }
    payload.update(payload_updates)
    path.write_bytes(canonical_json({"payload": payload}))


def test_entry_runs_terminal_gate_on_exact_clean_receipt_merge(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    _write_receipt(root)
    checks = []
    monkeypatch.setattr(
        verify_b01c_entry,
        "verify_final_repository_state",
        lambda expected, actual_root: checks.append((expected, actual_root)) or expected,
    )
    monkeypatch.setattr(verify_b01c_entry, "_require_detached_head", lambda _root: None)
    captured = {}

    def fake_run(actual_root, command):
        captured["root"] = actual_root
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0, verify_b01c_entry.PASS_LINE + "\n", "")

    monkeypatch.setattr(verify_b01c_entry, "_run_terminal_gate", fake_run)
    pins = tmp_path / "pins.json"
    pins.write_text("{}\n", encoding="utf-8")
    assert verify_b01c_entry.verify_entry(
        root=root,
        expected_head=HEAD,
        receipt_pr=35,
        now_us=30_000_000,
        pins=pins,
        provider_pin=PIN,
        anchor_ruleset_pin="b" * 64,
    ) == HEAD
    assert checks == [(HEAD, root), (HEAD, root)]
    command = captured["command"]
    assert command[command.index("--mode") + 1] == "receipt"
    assert command[command.index("--base-sha") + 1] == SOURCE
    assert command[command.index("--expected-head") + 1] == HEAD
    assert command[command.index("--receipt-pr") + 1] == "35"
    assert command[command.index("--pins") + 1] == str(pins)


@pytest.mark.parametrize(
    "proc",
    [
        subprocess.CompletedProcess([], 1, "B00R result: FAIL\n", "gate failed\n"),
        subprocess.CompletedProcess([], 0, "", ""),
        subprocess.CompletedProcess([], 0, verify_b01c_entry.PASS_LINE + "\n" * 2
                                    + verify_b01c_entry.PASS_LINE + "\n", ""),
        subprocess.CompletedProcess([], 0, "B00R result: BLOCKED\n", ""),
    ],
)
def test_entry_rejects_nonterminal_or_ambiguous_gate_result(proc):
    with pytest.raises(verify_b01c_entry.B01CEntryError):
        verify_b01c_entry._require_terminal_pass(proc)


@pytest.mark.parametrize(
    ("payload_update", "reason"),
    [
        ({"milestone": "B01C"}, "IDENTITY_MISMATCH"),
        ({"repair_generation": 1}, "IDENTITY_MISMATCH"),
        ({"source_merge_sha": "0" * 40}, "SOURCE_MERGE_INVALID"),
        ({"source_merge_sha": "not-a-sha"}, "SOURCE_MERGE_INVALID"),
    ],
)
def test_entry_rejects_wrong_receipt_identity(tmp_path, payload_update, reason):
    root = tmp_path / "repo"
    root.mkdir()
    _write_receipt(root, **payload_update)
    with pytest.raises(verify_b01c_entry.B01CEntryError, match=reason):
        verify_b01c_entry._canonical_g2_receipt(root)


def test_entry_rejects_noncanonical_receipt_bytes(tmp_path):
    root = tmp_path / "repo"
    _write_receipt(root)
    path = root / verify_b01c_entry.CANONICAL_RECEIPT
    path.write_bytes(b'{"payload": {"milestone": "B00R"}}\n')
    with pytest.raises(verify_b01c_entry.B01CEntryError, match="NOT_CANONICAL"):
        verify_b01c_entry._canonical_g2_receipt(root)


def test_entry_requires_pins_outside_repository(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    _write_receipt(root)
    inside = root / "pins.json"
    inside.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        verify_b01c_entry, "verify_final_repository_state", lambda *_args: HEAD)
    with pytest.raises(
        verify_b01c_entry.B01CEntryError, match="PINS_MUST_BE_OUTSIDE_REPOSITORY"
    ):
        verify_b01c_entry.verify_entry(
            root=root,
            expected_head=HEAD,
            receipt_pr=35,
            now_us=30_000_000,
            pins=inside,
            provider_pin=PIN,
            anchor_ruleset_pin="b" * 64,
        )


def test_entry_requires_detached_head(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "test"], check=True)
    subprocess.run([
        "git", "-C", str(root), "config", "user.email", "test@example.invalid"
    ], check=True)
    (root / "file.txt").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "base"], check=True)
    with pytest.raises(verify_b01c_entry.B01CEntryError, match="HEAD_NOT_DETACHED"):
        verify_b01c_entry._require_detached_head(root)
    subprocess.run(["git", "-C", str(root), "checkout", "--detach", "-q"], check=True)
    verify_b01c_entry._require_detached_head(root)


def test_entry_rechecks_detached_head_after_terminal_gate(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    _write_receipt(root)
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "test"], check=True)
    subprocess.run([
        "git", "-C", str(root), "config", "user.email", "test@example.invalid"
    ], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "receipt"], check=True)
    subprocess.run(["git", "-C", str(root), "checkout", "--detach", "-q"], check=True)
    monkeypatch.setattr(
        verify_b01c_entry, "verify_final_repository_state", lambda *_args: HEAD)

    def fake_run(actual_root, command):
        subprocess.run(["git", "-C", str(actual_root), "branch", "attack"], check=True)
        subprocess.run([
            "git", "-C", str(actual_root), "symbolic-ref", "HEAD", "refs/heads/attack"
        ], check=True)
        return subprocess.CompletedProcess(command, 0, verify_b01c_entry.PASS_LINE + "\n", "")

    monkeypatch.setattr(verify_b01c_entry, "_run_terminal_gate", fake_run)
    with pytest.raises(verify_b01c_entry.B01CEntryError, match="HEAD_NOT_DETACHED"):
        verify_b01c_entry.verify_entry(
            root=root,
            expected_head=HEAD,
            receipt_pr=35,
            now_us=30_000_000,
            pins=None,
            provider_pin=PIN,
            anchor_ruleset_pin="b" * 64,
        )


def test_entry_cli_rejects_attacker_controlled_git_root(tmp_path, monkeypatch, capsys):
    attacker = tmp_path / "attacker"
    attacker.mkdir()
    monkeypatch.setenv("MAIN_RULESET_EVIDENCE_SHA256", "a" * 64)
    monkeypatch.setenv("B00R_G2_TAG_RULESET_SHA256", "b" * 64)
    assert verify_b01c_entry.main([
        "--expected-head", HEAD,
        "--receipt-pr", "35",
        "--now-us", "30000000",
        "--git-root", str(attacker),
    ]) == 1
    assert "NONCANONICAL_GIT_ROOT_FORBIDDEN" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("flag", "env_name", "other_flag", "other_env", "reason"),
    [
        (
            "--provider-pin", "MAIN_RULESET_EVIDENCE_SHA256",
            "--anchor-ruleset-pin", "B00R_G2_TAG_RULESET_SHA256", "MAIN_RULESET",
        ),
        (
            "--anchor-ruleset-pin", "B00R_G2_TAG_RULESET_SHA256",
            "--provider-pin", "MAIN_RULESET_EVIDENCE_SHA256", "TAG_RULESET",
        ),
    ],
)
def test_entry_cli_cannot_override_protected_ruleset_pins(
    monkeypatch, capsys, flag, env_name, other_flag, other_env, reason
):
    monkeypatch.setenv(env_name, "b" * 64)
    monkeypatch.setenv(other_env, "d" * 64)
    result = verify_b01c_entry.main([
        "--expected-head", HEAD,
        "--receipt-pr", "35",
        "--now-us", "30000000",
        flag, "c" * 64,
        other_flag, "d" * 64,
    ])
    assert result == 1
    assert f"CONFLICTING_CLI_AND_PROTECTED_{reason}_PINS" in capsys.readouterr().err
