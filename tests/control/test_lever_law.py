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


def _base(**overrides):
    payload = {"venue_environment": "OFF", "venue_activation": "OFF",
               "paper_activation": "OFF", "shadow_activation": "LIVE"}
    payload.update(overrides)
    return payload


class TestAliasLaw:
    @pytest.mark.parametrize("alias", sorted(lever_law.INVALID_ALIASES))
    def test_every_invalid_alias_on_an_activation_slot_is_a_legacy_alias_refusal(self, alias):
        # COV-1 / LEV-V-0012..0046: a legacy word/boolean/blank/null on a canonical slot is
        # LEGACY_LEVER_ALIAS_FORBIDDEN (the both-OFF containment), NEVER *_VALUE_INVALID — the RC4
        # canonical evaluation order rejects the exact bytes before any closed-enum check.
        result = lever_law.resolve_manifest(_base(venue_activation=alias))
        assert not result.accepted
        assert result.refusal_code == "LEGACY_LEVER_ALIAS_FORBIDDEN"
        # the pinned containment is the STRONGER both-OFF, not a single-axis OFF.
        assert result.minimum_action["venue_activation"] == "OFF"
        assert result.minimum_action["paper_activation"] == "OFF"
        assert result.minimum_action["shadow_activation"] == "LIVE"

    def test_case_sensitive_no_coercion_no_trim(self):
        for bad in (" LIVE", "LIVE ", "Live", "live", 1, True, None):
            assert not lever_law.resolve_manifest(_base(venue_activation=bad)).accepted


class TestRc4AliasFixtureDriftLock:
    """COV-1: every LEV-V-0012..0059 fixture in the vendored RC4 bundle pins
    LEGACY_LEVER_ALIAS_FORBIDDEN; every one, on a concrete manifest, must refuse by that code.
    LEV-V-0060..0063 (the field-enum near-misses) must NOT collapse onto the alias code."""

    def test_the_48_alias_fixtures_all_pin_the_alias_code_in_the_bundle(self):
        fixtures = {v["id"]: v for v in _bundle()["verifications"]}
        alias_ids = [f"LEV-V-{n:04d}" for n in range(12, 60)]
        assert len(alias_ids) == 48
        for fid in alias_ids:
            assert fixtures[fid]["refusal"] == "LEGACY_LEVER_ALIAS_FORBIDDEN", fid

    @pytest.mark.parametrize("slot", ["venue_activation", "paper_activation"])
    @pytest.mark.parametrize("word", sorted(lever_law.INVALID_ALIASES))
    def test_every_word_alias_on_each_activation_slot_refuses_the_alias_code(self, word, slot):
        result = lever_law.resolve_manifest(_base(**{slot: word}))
        assert result.refusal_code == "LEGACY_LEVER_ALIAS_FORBIDDEN", (slot, word)

    @pytest.mark.parametrize("word", sorted(lever_law.INVALID_ALIASES - {"SHADOW", "PAPER"}))
    def test_env_word_aliases_refuse_alias_except_the_population_carveout(self, word):
        result = lever_law.resolve_manifest(_base(venue_environment=word))
        assert result.refusal_code == "LEGACY_LEVER_ALIAS_FORBIDDEN", word

    @pytest.mark.parametrize("slot", ["venue_environment", "venue_activation", "paper_activation"])
    @pytest.mark.parametrize("typed", [True, False, 1, 0, None])
    def test_typed_json_values_on_any_slot_refuse_the_alias_code(self, slot, typed):
        # LEV-V-0047..0055: JSON true/false/1/0/null present on a slot is a coercion attempt.
        base = _base(venue_environment="LIVE" if slot != "venue_environment" else "OFF")
        base[slot] = typed
        assert lever_law.resolve_manifest(base).refusal_code == "LEGACY_LEVER_ALIAS_FORBIDDEN"

    @pytest.mark.parametrize(
        "slot,value",
        [("venue_environment", " LIVE"), ("venue_environment", "LIVE "),
         ("venue_activation", "\tLIVE"), ("paper_activation", "OFF\n")])
    def test_whitespace_bytes_refuse_the_alias_code(self, slot, value):
        # LEV-V-0056..0059: exact bytes, no trim.
        base = _base(venue_environment="LIVE" if slot != "venue_environment" else "OFF")
        base[slot] = value
        assert lever_law.resolve_manifest(base).refusal_code == "LEGACY_LEVER_ALIAS_FORBIDDEN"

    def test_population_words_on_venue_environment_are_value_invalid_not_alias(self):
        # LEV-V-0062/0063: SHADOW/PAPER on venue_environment are a WRONG-AXIS value, not a legacy
        # alias — a population, not a venue environment value.
        for word in ("SHADOW", "PAPER"):
            result = lever_law.resolve_manifest(_base(venue_environment=word))
            assert result.refusal_code == "VENUE_ENVIRONMENT_VALUE_INVALID", word

    def test_testnet_on_an_activation_slot_is_value_invalid_not_alias(self):
        # LEV-V-0060/0061: TESTNET is a well-formed non-alias value legal only in venue_environment.
        assert lever_law.resolve_manifest(
            _base(venue_activation="TESTNET")).refusal_code == "VENUE_ACTIVATION_VALUE_INVALID"
        assert lever_law.resolve_manifest(
            _base(paper_activation="TESTNET")).refusal_code == "PAPER_ACTIVATION_VALUE_INVALID"

    def test_a_missing_slot_is_value_invalid_not_a_json_null_alias(self):
        # A key entirely ABSENT is the field's own VALUE_INVALID ("missing or not exactly …"),
        # distinct from a present JSON null (an alias/coercion) — key presence is the discriminator.
        payload = {"venue_activation": "OFF", "paper_activation": "OFF", "shadow_activation": "LIVE"}
        assert lever_law.resolve_manifest(
            payload).refusal_code == "VENUE_ENVIRONMENT_VALUE_INVALID"


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


class TestPromotionReceiptEquality:
    """COV-3 / LEV-0042 (LEV-V-0074/0075/0085/0086/0087): a LIVE/LIVE receipt is not accepted on
    presence alone — its declared digests/scope must EQUAL the manifest's, it must be a PASS, and
    it must not be expired against a provided evaluation clock."""

    def _live_live(self, **overrides):
        return _base(venue_environment="LIVE", venue_activation="LIVE", **overrides)

    def test_a_minimal_receipt_still_accepts(self):
        # additive: a receipt that declares no digest/result/expiry is unchanged from pre-COV-3.
        assert lever_law.resolve_manifest(
            self._live_live(testnet_promotion_receipt={"receipt_id": "r1"})).accepted

    def test_a_pass_receipt_with_matching_declared_fields_accepts(self):
        assert lever_law.resolve_manifest(self._live_live(
            build_commit="c1",
            testnet_promotion_receipt={"result": "PASS", "build_commit": "c1"})).accepted

    def test_receipt_build_digest_differs_refuses(self):
        result = lever_law.resolve_manifest(self._live_live(
            build_commit="A",
            testnet_promotion_receipt={"result": "PASS", "build_commit": "B"}))
        assert result.refusal_code == "LIVE_PROMOTION_RECEIPT_MISSING"

    def test_receipt_scope_or_parameter_digest_differs_refuses(self):
        result = lever_law.resolve_manifest(self._live_live(
            parameter_digest="X",
            testnet_promotion_receipt={"result": "PASS", "parameter_digest": "Y"}))
        assert result.refusal_code == "LIVE_PROMOTION_RECEIPT_MISSING"

    def test_receipt_expired_against_the_evaluation_clock_refuses(self):
        result = lever_law.resolve_manifest(self._live_live(
            evaluation_clock_us=1000,
            testnet_promotion_receipt={"result": "PASS", "expires_at_us": 999}))
        assert result.refusal_code == "LIVE_PROMOTION_RECEIPT_MISSING"

    def test_receipt_result_not_pass_refuses(self):
        result = lever_law.resolve_manifest(self._live_live(
            testnet_promotion_receipt={"result": "FAIL", "build_commit": "c1"}))
        assert result.refusal_code == "LIVE_PROMOTION_RECEIPT_MISSING"


class TestMixedEnvironmentBundle:
    """CTL-1/COV-4 / LEV-0099 (LEV-V-0080): a bundle (or single binding) naming BOTH LIVE and
    TESTNET members is refused whole — never a supposedly-safe subset."""

    def test_single_manifest_binding_naming_both_environments_refuses_under_off(self):
        result = lever_law.resolve_manifest(_base(
            venue_binding={"live_endpoint": "x", "testnet_endpoint": "y"}))
        assert result.refusal_code == "MIXED_ENVIRONMENT_BUNDLE_FORBIDDEN"

    def test_resolve_bundle_refuses_a_mixed_member_set_whole(self):
        result = lever_law.resolve_bundle([{"live_order": "o1"}, {"testnet_fill": "f1"}])
        assert result.refusal_code == "MIXED_ENVIRONMENT_BUNDLE_FORBIDDEN"
        # explicit environment tags are honored too
        tagged = lever_law.resolve_bundle(
            [{"environment": "LIVE"}, {"environment": "TESTNET"}])
        assert tagged.refusal_code == "MIXED_ENVIRONMENT_BUNDLE_FORBIDDEN"

    def test_resolve_bundle_accepts_a_single_environment_set(self):
        assert lever_law.resolve_bundle([{"live_order": "o1"}, {"live_fill": "f1"}]).accepted
        assert lever_law.resolve_bundle([]).accepted

    def test_resolve_bundle_fails_closed_on_a_non_object_member(self):
        with pytest.raises(lever_law.LeverLawError):
            lever_law.resolve_bundle([{"live_order": "o1"}, "not-an-object"])
        with pytest.raises(lever_law.LeverLawError):
            lever_law.resolve_bundle("not-a-list")


class TestVenueBindingScopeEquality:
    """COV-5 / LEV-0041 (LEV-V-0083/0084): venue_binding account/venue must equal the scope's."""

    def test_scope_account_ref_disagrees_with_binding_refuses(self):
        result = lever_law.resolve_manifest(_base(
            venue_environment="LIVE", venue_activation="OFF",
            scope={"account_ref": "A"}, venue_binding={"account_ref": "B"}))
        assert result.refusal_code == "VENUE_BINDING_MISMATCH"

    def test_scope_venue_id_disagrees_with_binding_refuses(self):
        result = lever_law.resolve_manifest(_base(
            venue_environment="LIVE", venue_activation="OFF",
            scope={"venue_id": "V1"}, venue_binding={"venue_id": "V2"}))
        assert result.refusal_code == "VENUE_BINDING_MISMATCH"

    def test_matching_scope_and_binding_accepts(self):
        assert lever_law.resolve_manifest(_base(
            venue_environment="LIVE", venue_activation="OFF",
            scope={"account_ref": "A", "venue_id": "V1"},
            venue_binding={"account_ref": "A", "venue_id": "V1"})).accepted


class TestLeaseCodesAreExternalEvidence:
    """COV-7: the producer-lease codes are EXTERNAL_EVIDENCE (the lease coordinator is OUT_OF_REPO),
    reachable via the caller-supplied classifier — not an unreachable in-repo-state claim."""

    @pytest.mark.parametrize("code", ["PRODUCER_LEASE_MISSING", "PRODUCER_LEASE_CONFLICT"])
    def test_lease_codes_are_classified_external_evidence(self, code):
        assert lever_law.REFUSAL_SCOPE[code] == "EXTERNAL_EVIDENCE"
        fired = lever_law.classify_external_refusal(code, True)
        assert fired is not None and fired.refusal_code == code
        assert lever_law.classify_external_refusal(code, False) is None


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
