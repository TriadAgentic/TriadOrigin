"""CO-05 — ledger review rebinding (make a stale review impossible).

The v1 review binds only the frozen REVIEWED_V2 subject and the v1 ``--verify`` compares only row
ID + milestone, so 94 rows whose ``rule`` field drifted (R8_DEFAULT -> R8_GOVERNANCE_CLOSURE)
escaped re-review. The v2 layer binds the exact SHA-256 of the full CURRENT ledger bytes PLUS a
per-row digest over every safety-significant field; ``--verify`` recomputes and compares both.

These tests prove the mechanism: mutating any single safety-significant row field without a fresh
review changes a digest and fails the build — including the exact ``rule``-only drift class the v1
milestone check misses. They deliberately do NOT assert the re-review dispositions are resolved:
those 94 dispositions are owner/reviewer judgment and stay honestly REVIEW_PENDING, while the digest
binding is mechanically green.
"""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import build_ledger as bl  # noqa: E402


# --------------------------------------------------------------------------------------------------
# Fixtures: a tiny synthetic ledger + a v2 review generated over it (no repo file mutation).
# --------------------------------------------------------------------------------------------------

def _row(rid: str, milestone: str, rule: str, exec_class: str = "IN_REPO_CODE") -> dict:
    """A row carrying exactly the safety-significant field set the real ledger rows carry."""
    return {
        "id": rid,
        "source": "RC3_EFFECTIVE",
        "row_class": "GATE_CONTROL",
        "gate": "G0",
        "phase": "P0",
        "node": "Cross-cutting",
        "milestone": milestone,
        "exec_class": exec_class,
        "rule": rule,
        "status": "NOT_STARTED",
    }


def _fixture_ledger() -> dict:
    return {
        "ledger_version": bl.LEDGER_VERSION,
        "task_count": 3,
        "milestone_counts": {"B00": 1, "B01": 2},
        "tasks": [
            _row("CTL-A-01", "B01", "R1_GATE"),
            _row("CTL-A-02", "B01", "R1_GATE"),
            _row("GAP-001", "B00", "R8_GOVERNANCE_CLOSURE", exec_class="IN_REPO_GOVERNANCE"),
        ],
    }


def _fixture_subject() -> dict:
    """A REVIEWED_V2-shaped predecessor where GAP-001's rule differs (milestone identical)."""
    return {
        "ledger_version": bl.REVIEW_SUBJECT_VERSION,
        "tasks": [
            _row("CTL-A-01", "B01", "R1_GATE"),
            _row("CTL-A-02", "B01", "R1_GATE"),
            _row("GAP-001", "B00", "R8_DEFAULT", exec_class="IN_REPO_GOVERNANCE"),
        ],
    }


def _rendered(ledger: dict) -> bytes:
    return (json.dumps(ledger, indent=1, sort_keys=True) + "\n").encode("utf-8")


def _make_review(ledger: dict, subject: dict | None = None) -> tuple[bytes, dict]:
    subject = subject if subject is not None else _fixture_subject()
    ledger_bytes = _rendered(ledger)
    review = bl.build_review_v2(
        ledger_bytes, ledger, subject,
        reviewer="test-session", reviewed_at="2026-08-12", review_basis="fixture",
    )
    return ledger_bytes, review


# --------------------------------------------------------------------------------------------------
# Positive: a freshly-generated v2 review binds its ledger.
# --------------------------------------------------------------------------------------------------

def test_fresh_v2_review_binds_its_ledger():
    ledger = _fixture_ledger()
    ledger_bytes, review = _make_review(ledger)
    assert bl.verify_review_v2(ledger_bytes, ledger, review) == []


def test_real_repo_v2_review_binds_the_real_ledger():
    """The committed v2 artifact binds the committed ledger — the mechanism is green in-repo."""
    ledger = bl.build()
    ledger_bytes = bl.LEDGER.read_bytes()
    review = json.loads(bl.REVIEW_V2.read_text())
    assert bl.verify_review_v2(ledger_bytes, ledger, review) == []
    # And the review's full-bytes bind is the actual on-disk ledger digest.
    assert review["binds_ledger_sha256"] == hashlib.sha256(ledger_bytes).hexdigest()


# --------------------------------------------------------------------------------------------------
# The core CO-05 acceptance: mutating ANY single row field without a new review fails.
# --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "field,new_value",
    [
        ("source", "RC4_ADDENDUM"),
        ("row_class", "FORMULA_ATOMIC"),
        ("gate", "G1"),
        ("phase", "P1"),
        ("node", "ORIGIN"),
        ("milestone", "B02"),
        ("exec_class", "ESTATE_NODE"),
        ("rule", "R6_NODE"),
        ("status", "DONE"),
    ],
)
def test_mutating_any_single_row_field_without_new_review_fails(field, new_value):
    ledger = _fixture_ledger()
    ledger_bytes, review = _make_review(ledger)
    # sanity: unmutated binds
    assert bl.verify_review_v2(ledger_bytes, ledger, review) == []
    # mutate exactly one field of exactly one row; DO NOT regenerate the review
    mutated = copy.deepcopy(ledger)
    assert mutated["tasks"][0][field] != new_value  # a real change
    mutated["tasks"][0][field] = new_value
    problems = bl.verify_review_v2(_rendered(mutated), mutated, review)
    assert problems, f"mutating {field!r} escaped the v2 binding"
    joined = " ".join(problems)
    assert "digest mismatch" in joined


def test_rule_only_drift_with_unchanged_milestone_is_caught():
    """The exact class the v1 ID+milestone verifier misses: rule changes, milestone stays."""
    ledger = _fixture_ledger()
    ledger_bytes, review = _make_review(ledger)
    mutated = copy.deepcopy(ledger)
    # GAP-001 keeps milestone B00 but its rule changes — invisible to an ID+milestone check.
    row = mutated["tasks"][2]
    assert row["id"] == "GAP-001" and row["milestone"] == "B00"
    row["rule"] = "R8_DEFAULT"
    assert row["milestone"] == "B00"  # milestone unchanged
    problems = bl.verify_review_v2(_rendered(mutated), mutated, review)
    assert any("digest mismatch" in p for p in problems)


# --------------------------------------------------------------------------------------------------
# The two binding layers are independent.
# --------------------------------------------------------------------------------------------------

def test_full_bytes_layer_catches_a_byte_change_that_leaves_rows_intact():
    ledger = _fixture_ledger()
    ledger_bytes, review = _make_review(ledger)
    # Re-serialize the SAME rows with different byte formatting: per-row digests still match,
    # but the full-bytes digest must not.
    other_bytes = json.dumps(ledger, indent=2, sort_keys=True).encode("utf-8")
    assert other_bytes != ledger_bytes
    problems = bl.verify_review_v2(other_bytes, ledger, review)
    assert any("full-ledger digest mismatch" in p for p in problems)


def test_added_or_removed_field_fails_closed():
    ledger = _fixture_ledger()
    ledger_bytes, review = _make_review(ledger)
    # add an undeclared field
    added = copy.deepcopy(ledger)
    added["tasks"][0]["surprise"] = "x"
    assert any("field set" in p for p in bl.verify_review_v2(_rendered(added), added, review))
    # remove a declared field
    removed = copy.deepcopy(ledger)
    del removed["tasks"][0]["status"]
    assert any("field set" in p for p in bl.verify_review_v2(_rendered(removed), removed, review))


def test_extra_or_missing_row_digest_fails():
    ledger = _fixture_ledger()
    ledger_bytes, review = _make_review(ledger)
    # a review missing one row's digest
    short = copy.deepcopy(review)
    short["row_digests"].pop("CTL-A-01")
    assert any("omits row digests" in p for p in bl.verify_review_v2(ledger_bytes, ledger, short))
    # a review carrying a digest for a task not in the ledger
    over = copy.deepcopy(review)
    over["row_digests"]["CTL-Z-99"] = "0" * 64
    assert any("unknown tasks" in p for p in bl.verify_review_v2(ledger_bytes, ledger, over))


def test_wrong_ledger_version_or_missing_reviewer_fails():
    ledger = _fixture_ledger()
    ledger_bytes, review = _make_review(ledger)
    bad_ver = copy.deepcopy(review)
    bad_ver["ledger_version"] = "SOMETHING_ELSE"
    assert bl.verify_review_v2(ledger_bytes, ledger, bad_ver)
    no_reviewer = copy.deepcopy(review)
    no_reviewer["reviewer"] = ""
    assert any("reviewer" in p for p in bl.verify_review_v2(ledger_bytes, ledger, no_reviewer))


# --------------------------------------------------------------------------------------------------
# The drift change-log documents the 94-row drift with exact fields; dispositions stay pending.
# --------------------------------------------------------------------------------------------------

def test_drift_change_log_lists_exact_fields_and_stays_review_pending():
    ledger = _fixture_ledger()
    _, review = _make_review(ledger)
    drift = review["drift_from_reviewed_v2"]
    assert drift["dispositions_state"] == "REVIEW_PENDING"
    assert review["row_rereview_disposition"] == "REVIEW_PENDING"
    log = {e["id"]: e for e in drift["change_log"]}
    # only GAP-001 drifted in the fixture (rule R8_DEFAULT -> R8_GOVERNANCE_CLOSURE)
    assert set(log) == {"GAP-001"}
    entry = log["GAP-001"]
    assert entry["disposition"] == "REVIEW_PENDING"
    fields = {c["field"]: (c["reviewed_v2_value"], c["current_v3_value"]) for c in entry["changed_fields"]}
    assert fields == {"rule": ("R8_DEFAULT", "R8_GOVERNANCE_CLOSURE")}


def test_real_v2_drift_log_covers_the_94_rows_all_pending():
    review = json.loads(bl.REVIEW_V2.read_text())
    drift = review["drift_from_reviewed_v2"]
    assert drift["changed_row_count"] == 94
    assert drift["dispositions_state"] == "REVIEW_PENDING"
    assert all(e["disposition"] == "REVIEW_PENDING" for e in drift["change_log"])


def test_emit_is_deterministic():
    ledger = _fixture_ledger()
    subject = _fixture_subject()
    b = _rendered(ledger)
    one = bl.build_review_v2(b, ledger, subject, reviewer="s", reviewed_at="d", review_basis="x")
    two = bl.build_review_v2(b, ledger, subject, reviewer="s", reviewed_at="d", review_basis="x")
    assert json.dumps(one, sort_keys=True) == json.dumps(two, sort_keys=True)


# --------------------------------------------------------------------------------------------------
# End-to-end: --verify still prints BOTH the v1 lines and adds the v2 line; a stale v2 fails the
# actual build path (v1 evaluated first and passing, then v2 catching the drift).
# --------------------------------------------------------------------------------------------------

def test_cli_verify_exit_zero_and_prints_both_layers():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "build_ledger.py"), "--verify"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    # v1 output preserved:
    assert "structurally current" in proc.stdout
    assert "historical REVIEWED_V2 subject authenticated" in proc.stdout
    # v2 output added:
    assert "build_ledger_review.v2 binding authenticated" in proc.stdout


def test_cli_verify_fails_when_v2_review_is_stale(tmp_path, monkeypatch):
    """A pinned v2 review that no longer matches the ledger fails the real --verify path."""
    ledger = bl.build()
    real_bytes = bl.LEDGER.read_bytes()
    review = json.loads(bl.REVIEW_V2.read_text())
    # corrupt exactly one per-row digest, as a silent unreviewed row edit would
    stale = copy.deepcopy(review)
    victim = sorted(stale["row_digests"])[0]
    stale["row_digests"][victim] = "0" * 64
    stale_path = tmp_path / "build_ledger_review.v2.json"
    stale_path.write_text(json.dumps(stale, indent=1, sort_keys=True) + "\n")
    monkeypatch.setattr(bl, "REVIEW_V2", stale_path)
    rc = bl.main(["--verify"])
    assert rc == 1
    # the ledger itself is untouched by this test
    assert bl.LEDGER.read_bytes() == real_bytes
