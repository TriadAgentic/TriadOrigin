"""B05 — lever/alias/combination/refusal law: drift-lock + resolve_manifest battery."""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin.control import lever_law  # noqa: E402


def _bundle() -> dict:
    return json.loads((ROOT / "docs/control/rc4_control_bundle.json").read_text())


class TestDriftLock:
    def test_invalid_aliases_match_the_vendored_bundle(self):
        assert lever_law.INVALID_ALIASES == frozenset(_bundle()["lever_law"]["invalid_aliases"])
        assert len(lever_law.INVALID_ALIASES) == 35

    def test_valid_combinations_match_the_vendored_bundle_as_a_set(self):
        bundle_combos = [
            {"venue_environment": c["venue_environment"], "venue_activation": c["venue_activation"],
             "paper_activation": c["paper_activation"]}
            for c in _bundle()["lever_law"]["valid_combinations"]
        ]
        assert len(lever_law.VALID_COMBINATIONS) == len(bundle_combos) == 10
        for combo in bundle_combos:
            assert combo in lever_law.VALID_COMBINATIONS

    def test_refusal_codes_match_the_vendored_bundle(self):
        bundle_refusals = {r["code"]: r["meaning"] for r in _bundle()["refusals"]}
        assert set(lever_law.REFUSAL_CODES) == set(bundle_refusals) == set(lever_law.REFUSAL_SCOPE)
        assert len(lever_law.REFUSAL_CODES) == 32
        for code, meaning in bundle_refusals.items():
            assert lever_law.REFUSAL_CODES[code]["meaning"] == meaning

    def test_baseline_manifest_matches_master_plan(self):
        assert lever_law.BASELINE_MANIFEST == {
            "venue_environment": "OFF", "venue_activation": "OFF", "paper_activation": "OFF",
            "shadow_activation": "LIVE",
        }


class TestAliasLaw:
    @pytest.mark.parametrize("alias", sorted(lever_law.INVALID_ALIASES))
    def test_every_invalid_alias_is_refused_as_venue_activation(self, alias):
        payload = {"venue_environment": "OFF", "venue_activation": alias,
                   "paper_activation": "OFF", "shadow_activation": "LIVE"}
        result = lever_law.resolve_manifest(payload)
        assert not result.accepted
        assert result.refusal_code == "VENUE_ACTIVATION_VALUE_INVALID"

    def test_case_sensitive_no_coercion_no_trim(self):
        for bad in (" LIVE", "LIVE ", "Live", "live", 1, True, None):
            payload = {"venue_environment": "LIVE", "venue_activation": bad,
                       "paper_activation": "OFF", "shadow_activation": "LIVE"}
            assert not lever_law.resolve_manifest(payload).accepted


class TestValidCombinations:
    @pytest.mark.parametrize("combo", lever_law.VALID_COMBINATIONS)
    def test_every_valid_combination_is_accepted(self, combo):
        payload = dict(combo, shadow_activation="LIVE")
        if combo["venue_environment"] == "LIVE" and combo["venue_activation"] == "LIVE":
            payload["testnet_promotion_receipt"] = {"receipt_id": "r1"}
        result = lever_law.resolve_manifest(payload)
        assert result.accepted, result.refusal_code

    def test_off_environment_with_live_venue_activation_refused(self):
        payload = {"venue_environment": "OFF", "venue_activation": "LIVE",
                   "paper_activation": "OFF", "shadow_activation": "LIVE"}
        result = lever_law.resolve_manifest(payload)
        assert not result.accepted
        assert result.refusal_code == "OFF_WITH_LIVE_VENUE_ACTIVATION"
        assert result.minimum_action["venue_activation"] == "OFF"
        assert result.minimum_action["shadow_activation"] == "LIVE"


class TestNamedRefusals:
    def test_shadow_capture_off_forbidden(self):
        payload = {"venue_environment": "OFF", "venue_activation": "OFF",
                   "paper_activation": "OFF", "shadow_activation": "OFF"}
        result = lever_law.resolve_manifest(payload)
        assert result.refusal_code == "SHADOW_CAPTURE_OFF_FORBIDDEN"

    def test_scope_wildcard_refused(self):
        payload = {"venue_environment": "OFF", "venue_activation": "OFF",
                   "paper_activation": "OFF", "shadow_activation": "LIVE",
                   "scope": {"instruments": ["*"]}}
        result = lever_law.resolve_manifest(payload)
        assert result.refusal_code == "SCOPE_VALUE_INVALID"

    def test_live_promotion_receipt_missing(self):
        payload = {"venue_environment": "LIVE", "venue_activation": "LIVE",
                   "paper_activation": "OFF", "shadow_activation": "LIVE"}
        result = lever_law.resolve_manifest(payload)
        assert result.refusal_code == "LIVE_PROMOTION_RECEIPT_MISSING"

    def test_activation_value_invalid_in_activations_map(self):
        payload = {"venue_environment": "OFF", "venue_activation": "OFF",
                   "paper_activation": "OFF", "shadow_activation": "LIVE",
                   "activations": {"origin.candidate_publisher": "on"}}
        result = lever_law.resolve_manifest(payload)
        assert result.refusal_code == "ACTIVATION_VALUE_INVALID"

    def test_live_testnet_binding_forbidden(self):
        payload = {"venue_environment": "LIVE", "venue_activation": "OFF",
                   "paper_activation": "OFF", "shadow_activation": "LIVE",
                   "venue_binding": {"testnet_account": "abc"}}
        result = lever_law.resolve_manifest(payload)
        assert result.refusal_code == "LIVE_TESTNET_BINDING_FORBIDDEN"

    def test_venue_binding_mismatch(self):
        payload = {"venue_environment": "LIVE", "venue_activation": "OFF",
                   "paper_activation": "OFF", "shadow_activation": "LIVE",
                   "venue_binding": {"environment": "TESTNET"}}
        result = lever_law.resolve_manifest(payload)
        assert result.refusal_code == "VENUE_BINDING_MISMATCH"


class TestExternalEvidence:
    def test_registered_but_never_raised_by_resolve_manifest(self):
        for code, scope in lever_law.REFUSAL_SCOPE.items():
            if scope != "EXTERNAL_EVIDENCE":
                continue
            # None of the EXTERNAL_EVIDENCE codes are reachable from a plain accepted manifest.
            assert code in lever_law.REFUSAL_CODES

    def test_classify_external_refusal_requires_explicit_bool(self):
        with pytest.raises(lever_law.LeverLawError):
            lever_law.classify_external_refusal("PRIVATE_STATE_STALE", "yes")

    def test_classify_external_refusal_refuses_on_true_and_accepts_on_false(self):
        fired = lever_law.classify_external_refusal("PRIVATE_STATE_STALE", True)
        assert fired is not None and fired.refusal_code == "PRIVATE_STATE_STALE"
        clear = lever_law.classify_external_refusal("PRIVATE_STATE_STALE", False)
        assert clear is None

    def test_classify_external_refusal_rejects_non_external_code(self):
        with pytest.raises(lever_law.LeverLawError):
            lever_law.classify_external_refusal("SHADOW_CAPTURE_OFF_FORBIDDEN", True)


class TestContainment:
    def test_containment_never_widens_and_preserves_shadow_live(self):
        current = {"venue_environment": "LIVE", "venue_activation": "LIVE",
                   "paper_activation": "LIVE", "shadow_activation": "LIVE"}
        result = lever_law.containment_action("OFF_WITH_LIVE_VENUE_ACTIVATION", current)
        assert result["venue_activation"] == "OFF"
        assert result["shadow_activation"] == "LIVE"
        # paper_activation is left at the caller's current value for this code (None in the action)
        assert result["paper_activation"] == "LIVE"

    def test_containment_unknown_code_raises(self):
        with pytest.raises(lever_law.LeverLawError):
            lever_law.containment_action("NOT_A_CODE", lever_law.BASELINE_MANIFEST)

    def test_refuse_unknown_code_raises(self):
        with pytest.raises(lever_law.LeverLawError):
            lever_law.refuse("NOT_A_CODE")

    def test_refuse_builds_named_resolution(self):
        result = lever_law.refuse("LEVER_REVISION_STALE")
        assert not result.accepted
        assert result.refusal_code == "LEVER_REVISION_STALE"
        assert result.minimum_action["venue_activation"] == "OFF"
        assert result.minimum_action["paper_activation"] == "OFF"
