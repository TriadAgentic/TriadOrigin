"""B01C-ID-01/ID-02 — the deny-capable promotion verifier battery.

Promotion is verification only: activation is DENIED on every path, PASS or REFUSE. A present but
failed/stale/differently-bound proving receipt is refused (ID-01); two environments may never
reuse an account, credential, or route (ID-02, §4.4). The module reaches no venue or lever.
"""

from __future__ import annotations

import ast
import copy
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import governance, promotion  # noqa: E402
from triad_origin.canonical import canonical_json, sha256_hex  # noqa: E402

GOLDEN = ROOT / "contracts" / "golden"


def _projection() -> dict:
    return {field: sha256_hex(field.encode()) for field in promotion.INVARIANT_FIELDS}


def _trust() -> dict:
    return {
        "prod": {"key_id": "prod", "identity": "producer@triad", "role": "EVIDENCE_PRODUCER",
                 "algorithm": "ed25519", "public_key_hex": "ab" * 32, "revoked": False},
        "counter": {"key_id": "counter", "identity": "reviewer@triad",
                    "role": "INDEPENDENT_COUNTERSIGNER", "algorithm": "ed25519",
                    "public_key_hex": "cd" * 32, "revoked": False},
    }


def _pass_receipt(binding_digest: str) -> dict:
    receipt = json.loads(
        (GOLDEN / "triad.evidence_receipt.v3" / "valid.json").read_text(encoding="utf-8"))
    payload = receipt["payload"]
    payload["evidence_sha256s"] = [binding_digest, "9" * 64]
    payload["signatures"] = [
        {"key_id": "prod", "signature_hex": "1" * 128},
        {"key_id": "counter", "signature_hex": "2" * 128},
    ]
    return receipt


def _ok_verify(pk: str, msg: bytes, sig: str) -> bool:
    return True


def _verify(invariant, receipt, *, environments=None, now_us=4_000_000, verify_fn=_ok_verify):
    return promotion.verify_promotion(
        invariant_projection=invariant, proving_receipt=receipt, milestone="B00R",
        trust=_trust(), environments=environments, now_us=now_us, verify_fn=verify_fn)


class TestVerifiedPath:
    def test_wellformed_projection_bound_by_pass_receipt_verifies(self):
        inv = _projection()
        v = _verify(inv, _pass_receipt(promotion.invariant_projection_digest(inv)))
        assert v.verified is True and v.reason == "OK"
        assert v.activation_result == "DENIED_SAFE_HOLD"

    def test_verified_path_still_denies_activation(self):
        inv = _projection()
        v = _verify(inv, _pass_receipt(promotion.invariant_projection_digest(inv)))
        assert v.activation_result == governance.ACTIVATION_RESULT == "DENIED_SAFE_HOLD"


class TestInvariantMaterialMismatch:
    @pytest.mark.parametrize("field", promotion.INVARIANT_FIELDS)
    def test_one_field_change_unbinds_the_receipt(self, field):
        # The receipt binds the ORIGINAL projection; changing any one invariant digest changes the
        # projection digest, so the PASS receipt no longer binds it — refuse (ID-01).
        inv = _projection()
        receipt = _pass_receipt(promotion.invariant_projection_digest(inv))
        mutated = dict(inv)
        mutated[field] = "f" * 64
        v = _verify(mutated, receipt)
        assert not v.verified
        assert v.reason == "PROVING_RECEIPT_DOES_NOT_BIND_INVARIANT_PROJECTION"
        assert v.activation_result == "DENIED_SAFE_HOLD"

    @pytest.mark.parametrize("mutate,code", [
        (lambda p: p.pop(promotion.INVARIANT_FIELDS[0]), "MISSING_FIELDS"),
        (lambda p: p.__setitem__("rogue", "a" * 64), "EXTRA_FIELDS"),
        (lambda p: p.__setitem__(promotion.INVARIANT_FIELDS[0], "A" * 64), "FIELD_NOT_HEX64"),
        (lambda p: p.__setitem__(promotion.INVARIANT_FIELDS[0], "0"), "FIELD_NOT_HEX64"),
    ])
    def test_malformed_projection_refused(self, mutate, code):
        inv = _projection()
        mutate(inv)
        v = _verify(inv, _pass_receipt("9" * 64))
        assert not v.verified and code in v.reason


class TestProvingReceiptRejections:
    def _inv_and_bound_receipt(self):
        inv = _projection()
        return inv, _pass_receipt(promotion.invariant_projection_digest(inv))

    def test_failed_receipt_refused(self):
        inv, receipt = self._inv_and_bound_receipt()
        receipt["payload"]["result"] = "FAIL"
        v = _verify(inv, receipt)
        assert not v.verified and v.reason.startswith("PROVING_RECEIPT_NOT_PASS:FAIL")

    def test_absent_trust_is_blocked_not_pass(self):
        inv, receipt = self._inv_and_bound_receipt()
        v = promotion.verify_promotion(
            invariant_projection=inv, proving_receipt=receipt, milestone="B00R",
            trust=None, now_us=4_000_000, verify_fn=_ok_verify)
        assert not v.verified and "BLOCKED" in v.reason

    def test_absent_verifier_is_blocked(self):
        inv, receipt = self._inv_and_bound_receipt()
        v = _verify(inv, receipt, verify_fn=None)
        assert not v.verified and "VERIFY_UNAVAILABLE" in v.reason

    def test_stale_future_receipt_refused(self):
        inv, receipt = self._inv_and_bound_receipt()
        # now before emission -> future-evidence chronology failure.
        v = _verify(inv, receipt, now_us=receipt["payload"]["emitted_at_us"] - 1)
        assert not v.verified and "PROVING_RECEIPT_NOT_PASS" in v.reason

    def test_pass_receipt_binding_other_projection_refused(self):
        inv, _ = self._inv_and_bound_receipt()
        other = _pass_receipt("7" * 64)  # binds a different projection digest
        v = _verify(inv, other)
        assert not v.verified
        assert v.reason == "PROVING_RECEIPT_DOES_NOT_BIND_INVARIANT_PROJECTION"


class TestEnvironmentIsolation:
    def _env(self, **over) -> dict:
        base = {"venue_environment": "mainnet", "account_id": "acct-A",
                "credential_reference": "cred-A", "endpoint": "e-A",
                "transport": "t-A", "route": "r-A"}
        base.update(over)
        return base

    def test_distinct_environments_pass_when_isolated(self):
        inv = _projection()
        envs = {"mainnet": self._env(),
                "destination": self._env(venue_environment="mainnet", account_id="acct-B",
                                         credential_reference="cred-B", endpoint="e-B",
                                         transport="t-B", route="r-B")}
        v = _verify(inv, _pass_receipt(promotion.invariant_projection_digest(inv)), environments=envs)
        assert v.verified and v.activation_result == "DENIED_SAFE_HOLD"

    @pytest.mark.parametrize("field", promotion.ISOLATED_ENV_IDENTITY_FIELDS)
    def test_cross_environment_identity_reuse_refused(self, field):
        inv = _projection()
        b = self._env(account_id="acct-B", credential_reference="cred-B", route="r-B",
                      endpoint="e-B", transport="t-B")
        b[field] = self._env()[field]  # reuse one isolated identity across environments
        envs = {"mainnet": self._env(), "destination": b}
        v = _verify(inv, _pass_receipt(promotion.invariant_projection_digest(inv)), environments=envs)
        assert not v.verified
        assert v.reason.startswith(f"CROSS_ENVIRONMENT_IDENTITY_REUSE:{field}")
        assert v.activation_result == "DENIED_SAFE_HOLD"

    def test_wildcard_or_empty_environment_field_refused(self):
        assert not promotion.verify_environment_isolation(
            {"e": self._env(route="venue/*")}).verified
        assert not promotion.verify_environment_isolation(
            {"e": self._env(account_id="")}).verified


class TestDarkBoundary:
    def test_promotion_imports_no_venue_or_lever(self):
        tree = ast.parse((ROOT / "src" / "triad_origin" / "promotion.py").read_text())
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        # only __future__ + stdlib dataclasses + internal governance/canonical (relative -> "").
        assert imported <= {"dataclasses", "__future__", "canonical", ""}, imported
        text = (ROOT / "src" / "triad_origin" / "promotion.py").read_text().lower()
        for banned in ("socket", "http", "venue", "credential_loader", "order", "lever_registry"):
            assert f"import {banned}" not in text
