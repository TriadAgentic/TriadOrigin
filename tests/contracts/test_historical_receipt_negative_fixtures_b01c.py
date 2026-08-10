"""B01C-EVD-01 — the invalidated historical receipts are byte-frozen negative fixtures.

The old B01/B01R/B02 receipts were never legitimately closed (the chain is invalid at its root). The
forward-repair law preserves them byte-unchanged and additively dispositions them in
``docs/governance/B00_B07_INVALIDATION_MANIFEST.v1.json``; they are NEVER edited into a retroactive
pass. This test is the standing proof of that discipline:

* **byte-immutability** — each historical receipt's on-disk sha256 + size equals the value pinned in
  the invalidation manifest (a silent edit would break this);
* **not a v3 PASS** — the authenticated ``validate_receipt_v3`` returns FAIL for every one (they are
  v2-shaped, self-reported, and unauthenticated), so none can masquerade as a valid root; and
* **the named EVD-01 defects are still visibly present** in the frozen bytes — zero-digest fields, a
  64-hex self-hash where a 128-hex Ed25519 signature belongs, a CI-label "reviewer" (not an
  independent countersigner), and a self-reported ``result: PASS`` — documenting *why* each was
  invalidated, without touching them.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import governance  # noqa: E402

MANIFEST_PATH = ROOT / "docs" / "governance" / "B00_B07_INVALIDATION_MANIFEST.v1.json"
RECEIPTS_DIR = ROOT / "evidence" / "receipts"
_ZERO_DIGEST = "0" * 64
# EVD-01 subjects: the B01-chain receipts the forward-repair invalidated and froze.
SUBJECTS = ("B01", "B01R", "B02")


@pytest.fixture(scope="module")
def manifest():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def entries_by_milestone(manifest):
    return {e["milestone"]: e for e in manifest["entries"]}


@pytest.mark.parametrize("milestone", SUBJECTS)
def test_receipt_bytes_are_frozen_to_the_pinned_manifest_digest(milestone, entries_by_milestone):
    entry = entries_by_milestone[milestone]
    raw = (ROOT / entry["path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == entry["sha256"], (
        f"{milestone} receipt bytes drifted from the pinned invalidation-manifest digest")
    assert len(raw) == entry["size"]
    # the disposition is an additive invalidation, never a retroactive pass
    assert entry["disposition"] in set(manifest_dispositions())


def manifest_dispositions():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["disposition_vocabulary"]


@pytest.mark.parametrize("milestone", SUBJECTS)
def test_receipt_is_not_a_valid_v3_pass(milestone):
    receipt = json.loads((RECEIPTS_DIR / f"{milestone}.json").read_text(encoding="utf-8"))
    result, reason = governance.validate_receipt_v3(receipt, milestone=milestone)
    assert result != "PASS_REPOSITORY_SAFE_HOLD", (milestone, reason)
    assert result == "FAIL", (milestone, result, reason)
    assert result in governance.RECEIPT_RESULTS


@pytest.mark.parametrize("milestone", SUBJECTS)
def test_named_evd01_defects_are_still_present_in_the_frozen_bytes(milestone):
    receipt = json.loads((RECEIPTS_DIR / f"{milestone}.json").read_text(encoding="utf-8"))
    payload = receipt["payload"]
    # the frozen receipt is v2-shaped and self-reports PASS (never an authenticated v3 result)
    assert receipt["schema"] == "triad.evidence_receipt.v2"
    assert payload["result"] == "PASS"
    # ZERO_DIGEST fields — placeholder all-zero hashes standing in for real artifact identities
    assert receipt["artifact_sha256"] == _ZERO_DIGEST
    assert receipt["config_bundle_sha256"] == _ZERO_DIGEST
    # a 64-hex self-hash where a 128-hex Ed25519 signature belongs (BIND/receipt signature law)
    signature = payload["signature"]
    assert len(signature) == 64 and set(signature) <= set("0123456789abcdef")
    # a CI-run label, not an independent human/role countersigner
    assert payload["reviewer"].startswith("github-actions")


def test_all_three_subjects_are_dispositioned_in_the_manifest(entries_by_milestone):
    for milestone in SUBJECTS:
        assert milestone in entries_by_milestone, f"{milestone} missing from invalidation manifest"
