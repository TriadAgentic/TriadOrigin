"""Fail-closed membership tests for the B00R source-hash inventory."""

from __future__ import annotations

import hashlib
import pathlib

from tools import verify_source_hashes as verifier


def _write_minimal_inventory(root: pathlib.Path) -> pathlib.Path:
    pinned = root / "pinned.txt"
    pinned.write_text("pinned\n", encoding="utf-8")
    digest = hashlib.sha256(pinned.read_bytes()).hexdigest()
    inventory = root / "docs" / "control" / "SOURCE_HASHES.sha256"
    inventory.parent.mkdir(parents=True, exist_ok=True)
    inventory.write_text(f"{digest}  pinned.txt\n", encoding="utf-8")
    return inventory


def _run_isolated(
    tmp_path: pathlib.Path,
    monkeypatch,
    *,
    required_membership: list[str],
) -> int:
    inventory = _write_minimal_inventory(tmp_path)
    monkeypatch.setattr(verifier, "ROOT", tmp_path)
    monkeypatch.setattr(verifier, "SOURCE_HASHES", inventory)
    monkeypatch.setattr(verifier, "REQUIRED_MEMBERSHIP", required_membership)
    monkeypatch.setattr(verifier, "_verify_rc3_composition", lambda problems: None)
    return verifier.main()


def test_unpinned_rogue_closure_file_fails(
    tmp_path: pathlib.Path, monkeypatch, capsys
) -> None:
    rogue = tmp_path / "docs" / "control" / "closure" / "nested" / "rogue.json"
    rogue.parent.mkdir(parents=True)
    rogue.write_text("{}\n", encoding="utf-8")

    assert _run_isolated(tmp_path, monkeypatch, required_membership=[]) == 1
    assert (
        "FAIL: controlling artifact not pinned: "
        "docs/control/closure/nested/rogue.json"
    ) in capsys.readouterr().err


def test_omitted_fixed_required_source_fails(
    tmp_path: pathlib.Path, monkeypatch, capsys
) -> None:
    required = tmp_path / ".github" / "workflows" / "ci.yml"
    required.parent.mkdir(parents=True)
    required.write_text("name: CI\n", encoding="utf-8")

    assert _run_isolated(
        tmp_path,
        monkeypatch,
        required_membership=[".github/workflows/ci.yml"],
    ) == 1
    assert (
        "FAIL: controlling artifact not pinned: .github/workflows/ci.yml"
        in capsys.readouterr().err
    )


def test_present_classifier_grant_source_is_required_without_fixed_duplicate(
    tmp_path: pathlib.Path, monkeypatch, capsys
) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("governed\n", encoding="utf-8")

    assert _run_isolated(tmp_path, monkeypatch, required_membership=[]) == 1
    assert (
        "FAIL: controlling artifact not pinned: README.md"
        in capsys.readouterr().err
    )
    assert verifier.SELF_REFERENTIAL_INVENTORY not in verifier._required_membership(tmp_path)
