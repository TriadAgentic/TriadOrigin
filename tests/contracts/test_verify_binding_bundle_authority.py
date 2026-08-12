"""Formula-Repair spec §C.2 — ``verify_binding_bundle --authority``: real authentication or nonzero.

Every drill runs through the ACTUAL argv path (``subprocess.run`` on the tool file, never a
unit-internal call) and asserts BOTH the exit code AND the single typed reason token on STDOUT.
The closed vocabulary: ``UNAVAILABLE_AUTHORITY | DIGEST_MISMATCH | SIGNATURE_INVALID |
SIGNER_REVOKED | EXPIRED | NOT_YET_VALID | SCOPE_MISMATCH | THRESHOLD_NOT_MET |
MALFORMED_PREIMAGE | UNKNOWN_FIELD``. Exit 0 happens ONLY on full success — argument presence
never functions as proof, and absence of ``--authority`` is never a green PASS.

Fixtures are byte-deterministic (fixed Ed25519 seeds; RFC 8032 signing is deterministic) —
see ``tests/contracts/authority_fixture.py``.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import authority_fixture as fx  # noqa: E402  (sibling fixture module)

TOOL = ROOT / "tools" / "verify_binding_bundle.py"

_TOKENS = (
    "UNAVAILABLE_AUTHORITY", "DIGEST_MISMATCH", "SIGNATURE_INVALID", "SIGNER_REVOKED",
    "EXPIRED", "NOT_YET_VALID", "SCOPE_MISMATCH", "THRESHOLD_NOT_MET",
    "MALFORMED_PREIMAGE", "UNKNOWN_FIELD",
)


@pytest.fixture(scope="module")
def fixtures(tmp_path_factory) -> dict:
    """Build every fixture variant once; each maps variant -> manifest path."""
    base = tmp_path_factory.mktemp("c2_authority")
    return {variant: fx.write_fixture(base / variant, variant) for variant in fx.VARIANTS}


def run_tool(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL), *argv], capture_output=True, text=True, cwd=str(ROOT))


def run_authority(manifest: pathlib.Path, now_us: int = fx.NOW_US) -> subprocess.CompletedProcess:
    return run_tool("--authority", str(manifest), "--now-us", str(now_us))


def assert_refused(cp: subprocess.CompletedProcess, token: str) -> None:
    """Nonzero exit + EXACTLY ONE typed reason token on stdout (prose only on stderr)."""
    assert token in _TOKENS, token
    assert cp.returncode != 0, (cp.returncode, cp.stdout, cp.stderr)
    lines = [line for line in cp.stdout.splitlines() if line.strip()]
    assert lines == [token], (cp.stdout, cp.stderr)


# --- the §C.2 CLI fixture matrix ------------------------------------------------------------------
def test_happy_path_authenticates_and_exits_zero(fixtures):
    cp = run_authority(fixtures["happy"])
    assert cp.returncode == 0, (cp.stdout, cp.stderr)
    assert cp.stdout.startswith("AUTHORITY_VERIFIED "), cp.stdout
    assert "signed_root_digest=" in cp.stdout and "decisions=3" in cp.stdout


def test_missing_manifest_path_is_unavailable_authority(tmp_path):
    cp = run_authority(tmp_path / "no_such_manifest.json")
    assert_refused(cp, "UNAVAILABLE_AUTHORITY")


def test_malformed_manifest_json_is_malformed_preimage(fixtures):
    cp = run_authority(fixtures["malformed_manifest"])
    assert_refused(cp, "MALFORMED_PREIMAGE")


def test_wrong_root_digest_is_digest_mismatch(fixtures):
    cp = run_authority(fixtures["wrong_root"])
    assert_refused(cp, "DIGEST_MISMATCH")


def test_tampered_trust_registry_payload_is_digest_mismatch(fixtures):
    cp = run_authority(fixtures["trust_digest_mismatch"])
    assert_refused(cp, "DIGEST_MISMATCH")


def test_wrong_signing_key_is_signature_invalid(fixtures):
    cp = run_authority(fixtures["wrong_key"])
    assert_refused(cp, "SIGNATURE_INVALID")


def test_revoked_signer_is_signer_revoked(fixtures):
    cp = run_authority(fixtures["revoked"])
    assert_refused(cp, "SIGNER_REVOKED")


def test_expired_window_is_expired(fixtures):
    cp = run_authority(fixtures["expired"])
    assert_refused(cp, "EXPIRED")


def test_not_yet_valid_window_is_not_yet_valid(fixtures):
    cp = run_authority(fixtures["not_yet_valid"])
    assert_refused(cp, "NOT_YET_VALID")


def test_reordered_rows_still_verify_the_canonicalization_proof(fixtures):
    # Reordering the SAME row set must not change the canonical root digest — the signature over
    # the canonical root still verifies and the run is a full PASS.
    cp = run_authority(fixtures["reordered_rows"])
    assert cp.returncode == 0, (cp.stdout, cp.stderr)
    assert cp.stdout.startswith("AUTHORITY_VERIFIED "), cp.stdout


def test_reordered_rows_carry_the_same_signed_root_digest(fixtures):
    a = run_authority(fixtures["happy"]).stdout.split()[1]
    b = run_authority(fixtures["reordered_rows"]).stdout.split()[1]
    assert a.startswith("signed_root_digest=") and a == b


def test_duplicate_signer_never_double_counts_toward_threshold(fixtures):
    cp = run_authority(fixtures["duplicate_signer"])
    assert_refused(cp, "THRESHOLD_NOT_MET")


def test_unknown_manifest_field_is_unknown_field(fixtures):
    cp = run_authority(fixtures["unknown_field"])
    assert_refused(cp, "UNKNOWN_FIELD")


def test_mismatched_scope_is_scope_mismatch(fixtures):
    cp = run_authority(fixtures["scope_mismatch"])
    assert_refused(cp, "SCOPE_MISMATCH")


# --- the absence law (the historical exit-0 defect) ------------------------------------------------
def test_absent_authority_argument_is_nonzero_unavailable_authority():
    cp = run_tool()
    assert_refused(cp, "UNAVAILABLE_AUTHORITY")
    # the inventory duty still ran — its facts live on stderr, never on the token stream
    assert "rows=105" in cp.stderr


def test_empty_object_manifest_is_malformed_preimage(tmp_path):
    # Presence of a preimage file is not authentication: an {} manifest carries no authority.
    manifest = tmp_path / "authority_manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    cp = run_authority(manifest)
    assert_refused(cp, "MALFORMED_PREIMAGE")


def test_selftest_is_labeled_and_never_substitutes_for_the_real_path():
    cp = run_tool("--selftest")
    assert cp.returncode == 0, (cp.stdout, cp.stderr)
    assert "SELF_TEST" in cp.stdout
    assert "never a substitute for the real --authority path" in cp.stdout
    # SELF_TEST success never emits an authority verdict token
    assert "AUTHORITY_VERIFIED" not in cp.stdout
