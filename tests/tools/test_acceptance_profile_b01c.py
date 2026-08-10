"""WP-B01C-06 — the B01C acceptance profile is content-addressed, honest, and drift-locked.

Proves the profile:

* is content-addressed — ``profile_digest == sha256(canonical_json(all-but-digest))``;
* matches the committed file byte-for-byte (the generator is the single source; ``--check`` red on
  drift);
* is honest offline — ``closure_claimed`` is False, ``milestone_status`` is
  ``OFFLINE_PREP_UNRECEIPTED``, and every owner/provider input is ``null``/``UNAVAILABLE``; and
* can never drift from the estate safety posture — ``levers`` equals ``governance.SAFETY_POSTURE`` and
  ``activation_result`` equals ``governance.ACTIVATION_RESULT`` (``DENIED_SAFE_HOLD``).
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import gen_acceptance_profile as gap  # noqa: E402
from triad_origin import governance  # noqa: E402
from triad_origin.canonical import canonical_json, sha256_hex  # noqa: E402


def test_profile_is_content_addressed():
    profile = gap.build_profile()
    unsigned = {k: v for k, v in profile.items() if k != "profile_digest"}
    assert profile["profile_digest"] == sha256_hex(canonical_json(unsigned))
    assert len(profile["profile_digest"]) == 64


def test_committed_file_matches_the_generator_byte_for_byte():
    on_disk = gap.PROFILE_PATH.read_text(encoding="utf-8")
    assert on_disk == gap._serialize(gap.build_profile())
    assert gap.main(["--check"]) == 0


def test_honest_offline_posture():
    profile = json.loads(gap.PROFILE_PATH.read_text(encoding="utf-8"))
    assert profile["closure_claimed"] is False
    assert profile["milestone_status"] == "OFFLINE_PREP_UNRECEIPTED"
    assert profile["predecessor_hard"] == "B00R_RECEIPT_ANCHOR"
    owner = profile["owner_gated_inputs"]
    for key, value in owner.items():
        assert value in (None, "UNAVAILABLE"), (key, value)


def test_levers_and_activation_track_governance_single_source():
    profile = json.loads(gap.PROFILE_PATH.read_text(encoding="utf-8"))
    assert profile["levers"] == governance.SAFETY_POSTURE
    assert profile["activation_result"] == governance.ACTIVATION_RESULT == "DENIED_SAFE_HOLD"
    assert profile["permitted_result"] == governance.RESULT_PASS
    # OFF/OFF/OFF/LIVE, restated explicitly so a lever flip cannot pass silently
    assert profile["levers"]["shadow_activation"] == "LIVE"
    assert profile["levers"]["venue_environment"] == "OFF"
    assert profile["levers"]["venue_activation"] == "OFF"
    assert profile["levers"]["paper_activation"] == "OFF"


def test_required_evidence_never_claims_owner_gated_rows_are_built():
    profile = json.loads(gap.PROFILE_PATH.read_text(encoding="utf-8"))
    rows = profile["required_evidence"]
    assert rows, "acceptance profile lists no required evidence"
    allowed = {"OFFLINE_PREP_BUILT", "OWNER_GATED_NEW_MAJOR", "PENDING_B00R_ANCHOR"}
    for row in rows:
        assert set(row) >= {"id", "role", "artifact", "status"}
        assert row["status"] in allowed, row
    # at least one deferred row is honestly NOT built (no false all-green)
    assert any(r["status"] != "OFFLINE_PREP_BUILT" for r in rows)


def test_check_detects_drift(tmp_path, monkeypatch):
    # Point the generator at a tampered copy: --check must go red.
    tampered = tmp_path / "B01C_ACCEPTANCE_PROFILE.v1.json"
    good = gap._serialize(gap.build_profile())
    tampered.write_text(good.replace("OFFLINE_PREP_UNRECEIPTED", "CLOSED"), encoding="utf-8")
    monkeypatch.setattr(gap, "PROFILE_PATH", tampered)
    assert gap.main(["--check"]) == 1
