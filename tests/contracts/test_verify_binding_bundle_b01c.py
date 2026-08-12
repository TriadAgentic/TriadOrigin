"""B01C-BIND-01/03/06 — the binding-bundle verifier tool is green, fail-closed, and adversarial.

Proves that ``tools/verify_binding_bundle.py``:

* authenticates a real capability with an ephemeral owner key and REFUSES all six authenticity
  attacks (unsigned · wrong-signer · revoked · expired · valid-sig-over-other-bytes · wrong-trust-key),
  each with a NAMED refusal reason — never a wrongly-built capability;
* inventory-verifies the packaged 105-row bundle but, with no externally pinned authority preimage,
  prints ``UNAVAILABLE_AUTHORITY`` and exits 0 (fail-closed, never a fabricated authenticated PASS);
* exits 1 on a byte-tampered / wrong-count bundle; and
* exits 3 when the full schema validator is absent (never a silent pass).
"""

from __future__ import annotations

import builtins
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import verify_binding_bundle as vbb  # noqa: E402
from triad_origin import bindings  # noqa: E402

_EXPECTED_ATTACKS = {
    "unsigned", "wrong_signer", "revoked", "expired",
    "valid_sig_over_other_bytes", "wrong_trust_key",
}


def test_selftest_authenticates_then_refuses_all_six_attacks():
    result = vbb.selftest()
    assert result["authenticated_ok"] is True
    assert result["all_attacks_refused"] is True
    assert set(result["attacks"]) == _EXPECTED_ATTACKS
    # every attack is a NAMED refusal, never a wrongly-built capability
    for name, reason in result["attacks"].items():
        assert reason != "WRONGLY_BUILT", name
        assert reason and isinstance(reason, str)
    assert result["row_count"] == bindings.REQUIRED_ROW_COUNT


def test_selftest_reasons_are_deterministic_across_ephemeral_keys():
    # The ephemeral key differs each run, but the refusal REASONS are a property of the attack,
    # not of the random signature bytes.
    a = vbb.selftest()["attacks"]
    b = vbb.selftest()["attacks"]
    assert a == b


def test_selftest_cli_exits_zero():
    assert vbb.main(["--selftest"]) == 0


def test_bundle_only_reports_unavailable_authority_and_exits_zero(capsys):
    rc = vbb.main([])  # default bundle, no --authority
    out = capsys.readouterr().out
    assert rc == 0
    assert "UNAVAILABLE_AUTHORITY" in out
    assert f"rows={bindings.REQUIRED_ROW_COUNT}" in out


def test_wrong_count_bundle_exits_one(tmp_path):
    bundle = json.loads(bindings.DEFAULT_REGISTRY_PATH.read_text(encoding="utf-8"))
    bundle["rows"] = bundle["rows"][:-1]            # drop one row -> 104
    bundle["row_count"] = len(bundle["rows"])       # keep row_count self-consistent
    tampered = tmp_path / "binding_registry.v2.json"
    tampered.write_text(json.dumps(bundle), encoding="utf-8")
    assert vbb.main(["--bundle", str(tampered)]) == 1


def test_byte_tampered_row_exits_one(tmp_path):
    bundle = json.loads(bindings.DEFAULT_REGISTRY_PATH.read_text(encoding="utf-8"))
    # mutate a row body without recomputing its binding_digest -> BINDING_DIGEST_MISMATCH
    bundle["rows"][0]["semantic_slot"] = bundle["rows"][0]["semantic_slot"] + "_TAMPERED"
    tampered = tmp_path / "binding_registry.v2.json"
    tampered.write_text(json.dumps(bundle), encoding="utf-8")
    assert vbb.main(["--bundle", str(tampered)]) == 1


def test_validator_absent_lane_exits_three(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "jsonschema":
            raise ModuleNotFoundError("jsonschema disabled for test")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert vbb.main([]) == 3


def test_unknown_bundle_path_exits_one(tmp_path):
    assert vbb.main(["--bundle", str(tmp_path / "does_not_exist.json")]) == 1


def test_supplied_but_unauthenticated_authority_fails_closed(tmp_path, capsys):
    # Audit #10: a supplied --authority preimage that offline-prep cannot authenticate must NOT
    # exit 0 (which would read as an authenticated PASS). Presence is not authentication; the tool
    # fails closed with a non-zero exit until a real owner authentication path runs.
    preimage = tmp_path / "authority_preimage.json"
    preimage.write_text("{}", encoding="utf-8")
    rc = vbb.main(["--authority", str(preimage)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "UNAVAILABLE_AUTHORITY" in err
