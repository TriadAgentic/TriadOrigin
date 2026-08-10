"""B01C-EVD-01 — ``tools/validate_b_receipt.py --strict`` is fail-closed offline.

The strict receipt-v3 closure path consumes an externally pinned authority context, a trusted time,
an exact Git head, a closed evidence manifest, and a provider-derived ruleset capture. None of those
owner/provider inputs exist in the repository (they are out-of-repo and B00R is unvalidated), so the
strict path can NEVER print a closure PASS offline — it must fail closed with a non-zero exit and a
named reason. This test standing-proves that, so a future edit that let the strict path pass without
real authority would turn it red.

It exercises the tool as a subprocess (its real entry surface), never a fabricated authority.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
TOOL = ROOT / "tools" / "validate_b_receipt.py"
_PLACEHOLDER_RECEIPT = '{"payload":{"milestone":"B01C"}}'  # canonical bare, no real closure content


def _run(args, cwd=ROOT):
    return subprocess.run([sys.executable, str(TOOL), *args], cwd=str(cwd),
                          capture_output=True, text=True)


@pytest.fixture()
def placeholder_receipt(tmp_path):
    path = tmp_path / "placeholder.receipt.json"
    path.write_text(_PLACEHOLDER_RECEIPT, encoding="utf-8")
    return path


def test_strict_without_required_flags_exits_two(placeholder_receipt):
    proc = _run([str(placeholder_receipt), "--strict", "--milestone", "B01C"])
    assert proc.returncode == 2
    assert "--strict requires" in proc.stderr
    assert "OK:" not in proc.stdout


def test_strict_with_absent_authority_blocks_never_passes(placeholder_receipt):
    proc = _run([
        str(placeholder_receipt), "--strict",
        "--milestone", "B01C",
        "--now-us", "1786250000000000",
        "--manifest", "evidence/B00R/manifest.json",
        "--expected-head", "0" * 40,
        "--governance-snapshot", "docs/governance/rulesets/main.ruleset.provider.json",
        "--provider-raw", "docs/governance/rulesets/main.ruleset.provider.raw.json",
        "--provider-pin", "a" * 64,
    ])
    assert proc.returncode != 0
    combined = proc.stdout + proc.stderr
    # fail-closed at the missing external authority root — never a fabricated closure
    assert "UNAVAILABLE_AUTHORITY_ROOT" in combined or "AUTHORITY_ROOT_INVALID" in combined
    assert "OK:" not in proc.stdout


def test_strict_never_prints_a_closure_pass_for_a_frozen_v2_receipt():
    # A real historical v2 receipt cannot be a canonical bare v3 closure PASS either.
    receipt = ROOT / "evidence" / "receipts" / "B01.json"
    proc = _run([
        str(receipt), "--strict",
        "--milestone", "B01",
        "--now-us", "1786250000000000",
        "--manifest", "evidence/B00R/manifest.json",
        "--expected-head", "0" * 40,
        "--governance-snapshot", "docs/governance/rulesets/main.ruleset.provider.json",
        "--provider-raw", "docs/governance/rulesets/main.ruleset.provider.raw.json",
        "--provider-pin", "a" * 64,
    ])
    assert proc.returncode != 0
    assert "OK:" not in proc.stdout
