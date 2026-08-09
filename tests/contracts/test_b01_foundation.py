"""B01 foundation-correction falsification tests.

Covers: typed identity v2 (CTRL-B01-003 / BLK-RC2-017), engine_attestation.v2 equality law
(CTRL-B01-002 / BLK-RC2-016), the RC4 lever-combination law on engine_control_manifest.v2,
strict receipt-v2 PASS conditionals, the descriptor-v2 media-type law (CTRL-B01-001), and the
frozen-history / additive-supersession law.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import canonical, contracts, ids  # noqa: E402


# --- typed identity v2 ---------------------------------------------------------------------------
class TestTypedIdentityV2:
    def test_v1_cross_type_collision_exists(self):
        # The defect BLK-RC2-017 names: different runtime types, identical v1 digest.
        assert canonical.digest_fields(1) == canonical.digest_fields("1")
        assert canonical.digest_fields(True) == canonical.digest_fields(b"\x01")

    def test_v2_separates_types(self):
        assert canonical.digest_fields_v2(1) != canonical.digest_fields_v2("1")
        assert canonical.digest_fields_v2(True) != canonical.digest_fields_v2(b"\x01")
        assert canonical.digest_fields_v2(True) != canonical.digest_fields_v2(1)

    def test_v2_deterministic_and_domain_separated(self):
        assert canonical.digest_fields_v2("a", 2) == canonical.digest_fields_v2("a", 2)
        assert canonical.digest_fields_v2("a") != canonical.digest_fields("a")

    def test_v1_ids_remain_byte_stable(self):
        # Pinned v1 vectors: any change here is an identity-stability release blocker.
        si = ids.semantic_instance_id("f.v1", "d" * 64, "vm", "1m")
        assert si == "sinst_e7be341c2ffb4c208ff65bfb2142554eb05a3fb5"
        st = ids.structure_id("I", "vm", "fvg", si, "LONG", ["e1"], "9" * 64)
        rx = ids.reaction_id(st, "rf", ["e2"])
        hy = ids.hypothesis_id(rx, "cap.v1", "a" * 64)
        ca = ids.candidate_id(hy, "cf", "occ")
        assert ca == ids.candidate_id(hy, "cf", "occ")
        assert ca.startswith("cand_")

    def test_v2_ids_differ_from_v1_and_are_stable(self):
        v2 = {"identity_schema_version": ids.IDENTITY_SCHEMA_VERSION_V2}
        si1 = ids.semantic_instance_id("f.v1", "d" * 64, "vm", "1m")
        si2 = ids.semantic_instance_id("f.v1", "d" * 64, "vm", "1m", **v2)
        assert si1 != si2
        assert si2 == ids.semantic_instance_id("f.v1", "d" * 64, "vm", "1m", **v2)
        st2 = ids.structure_id("I", "vm", "fvg", si2, "LONG", ["e1"], "9" * 64, **v2)
        rx2 = ids.reaction_id(st2, "rf", ["e2"], **v2)
        hy2 = ids.hypothesis_id(rx2, "cap.v1", "a" * 64, **v2)
        ca2 = ids.candidate_id(hy2, "cf", "occ", **v2)
        cl2 = ids.opportunity_cluster_id([hy2], **v2)
        for value, prefix in [(st2, "str_"), (rx2, "rct_"), (hy2, "hyp_"), (ca2, "cand_"),
                              (cl2, "opp_")]:
            assert value.startswith(prefix)

    def test_unknown_identity_version_rejects(self):
        with pytest.raises(TypeError):
            ids.semantic_instance_id("f.v1", "d" * 64, "vm", "1m",
                                     identity_schema_version="origin.identity.v3")

    def test_registry_declares_both_identity_versions(self):
        index = json.loads((ROOT / "contracts/registry/index.json").read_text())
        assert index["identity_schema_version"] == "origin.identity.v1"
        assert index["identity_schema_versions"] == ["origin.identity.v1", "origin.identity.v2"]


# --- attestation v2 equality law -----------------------------------------------------------------
def _attestation_v2() -> dict:
    return json.loads(
        (ROOT / "contracts/golden/triad.engine_attestation.v2/valid.json").read_text())


class TestAttestationEquality:
    def test_golden_valid_passes(self):
        contracts.validate(_attestation_v2())

    @pytest.mark.parametrize("field", [
        "contract_manifest_sha256", "config_bundle_sha256", "build_commit", "artifact_sha256",
        "producer_epoch"])
    def test_each_identity_mismatch_rejects(self, field):
        event = _attestation_v2()
        if field == "build_commit":
            event["payload"][field] = "1111111111111111111111111111111111111111"
        elif field == "producer_epoch":
            event["payload"][field] = "43"
        else:
            event["payload"][field] = "e" * 64
        with pytest.raises(contracts.ContractError, match="ATTESTATION_IDENTITY_MISMATCH"):
            contracts.validate(event)

    def test_golden_invalid_is_schema_valid_but_semantically_rejected(self):
        event = json.loads(
            (ROOT / "contracts/golden/triad.engine_attestation.v2/invalid.json").read_text())
        with pytest.raises(contracts.ContractError, match="ATTESTATION_IDENTITY_MISMATCH"):
            contracts.validate(event)

    def test_v1_attestation_bytes_unchanged(self):
        # v1 stays immutable; its golden still validates without the equality law.
        event = json.loads(
            (ROOT / "contracts/golden/triad.engine_attestation.v1/valid.json").read_text())
        contracts.validate(event)


# --- RC4 lever-combination law -------------------------------------------------------------------
def _control_manifest() -> dict:
    return json.loads(
        (ROOT / "contracts/golden/triad.engine_control_manifest.v2/valid.json").read_text())


class TestLeverCombinationLaw:
    def test_testnet_live_combination_valid(self):
        contracts.validate(_control_manifest())

    def test_off_environment_with_live_activation_rejects(self):
        event = _control_manifest()
        event["payload"]["venue_environment"] = "OFF"
        event["payload"]["venue_activation"] = "LIVE"
        with pytest.raises(contracts.ContractError, match="OFF_WITH_LIVE_VENUE_ACTIVATION"):
            contracts.validate(event)

    def test_live_live_without_promotion_receipt_rejects(self):
        event = _control_manifest()
        event["payload"]["venue_environment"] = "LIVE"
        event["payload"]["venue_activation"] = "LIVE"
        event["payload"]["testnet_promotion_receipt"] = {}
        with pytest.raises(contracts.ContractError, match="LIVE_PROMOTION_RECEIPT_MISSING"):
            contracts.validate(event)

    def test_live_live_with_promotion_receipt_passes(self):
        event = _control_manifest()
        event["payload"]["venue_environment"] = "LIVE"
        event["payload"]["venue_activation"] = "LIVE"
        event["payload"]["testnet_promotion_receipt"] = {
            "receipt_id": "tp-1", "result": "PASS", "build_commit": "0" * 40}
        contracts.validate(event)

    def test_shadow_off_rejects_at_schema_and_law(self):
        event = _control_manifest()
        event["payload"]["shadow_activation"] = "OFF"
        with pytest.raises(contracts.ContractError):
            contracts.validate(event)

    @pytest.mark.parametrize("alias", ["live", "on", "TRUE", "1", "", "ENABLED", "DARK"])
    def test_legacy_lever_aliases_reject(self, alias):
        event = _control_manifest()
        event["payload"]["venue_activation"] = alias
        with pytest.raises(contracts.ContractError):
            contracts.validate(event)

    def test_component_activation_alias_rejects(self):
        event = _control_manifest()
        event["payload"]["activations"] = {"origin.candidate_publisher": "enabled"}
        with pytest.raises(contracts.ContractError, match="ACTIVATION_VALUE_INVALID"):
            contracts.validate(event)

    def test_wildcard_scope_rejects(self):
        event = _control_manifest()
        event["payload"]["scope"] = {"engine_id": "triad-origin-e02", "instruments": ["*"]}
        with pytest.raises(contracts.ContractError, match="SCOPE_VALUE_INVALID"):
            contracts.validate(event)

    def test_ten_valid_rc4_combinations(self):
        # RC4 VALID_COMBINATIONS: {LIVE,TESTNET,OFF-lawful pairs} x paper {LIVE,OFF}.
        lawful = [("LIVE", "LIVE"), ("LIVE", "OFF"), ("TESTNET", "LIVE"), ("TESTNET", "OFF"),
                  ("OFF", "OFF")]
        for env, act in lawful:
            for paper in ("LIVE", "OFF"):
                event = _control_manifest()
                event["payload"]["venue_environment"] = env
                event["payload"]["venue_activation"] = act
                event["payload"]["paper_activation"] = paper
                if (env, act) == ("LIVE", "LIVE"):
                    event["payload"]["testnet_promotion_receipt"] = {
                        "receipt_id": "tp-1", "result": "PASS"}
                contracts.validate(event)


# --- receipt v2 PASS conditionals ----------------------------------------------------------------
class TestReceiptLaws:
    def _load(self, name: str, which: str = "valid") -> dict:
        return json.loads((ROOT / f"contracts/golden/{name}/{which}.json").read_text())

    def test_evidence_receipt_pass_valid(self):
        contracts.validate(self._load("triad.evidence_receipt.v2"))

    def test_evidence_receipt_builder_is_reviewer_rejects(self):
        with pytest.raises(contracts.ContractError, match="BUILDER_IS_REVIEWER"):
            contracts.validate(self._load("triad.evidence_receipt.v2", "invalid"))

    def test_evidence_receipt_stale_window_rejects(self):
        event = self._load("triad.evidence_receipt.v2")
        event["payload"]["expires_at_us"] = event["payload"]["observed_at_us"]
        with pytest.raises(contracts.ContractError, match="VALIDITY_WINDOW"):
            contracts.validate(event)

    def test_evidence_receipt_empty_evidence_rejects(self):
        event = self._load("triad.evidence_receipt.v2")
        event["payload"]["evidence_ids"] = []
        with pytest.raises(contracts.ContractError, match="EMPTY_EVIDENCE"):
            contracts.validate(event)

    def test_task_pass_without_receipts_rejects(self):
        with pytest.raises(contracts.ContractError, match="PASS_WITHOUT_RECEIPTS"):
            contracts.validate(self._load("triad.task_status_event.v2", "invalid"))

    def test_task_self_loop_rejects(self):
        event = self._load("triad.task_status_event.v2")
        event["payload"]["from_status"] = event["payload"]["to_status"]
        with pytest.raises(contracts.ContractError, match="ILLEGAL_TRANSITION"):
            contracts.validate(event)

    def test_gate_pass_with_open_blocker_rejects(self):
        with pytest.raises(contracts.ContractError, match="OPEN_BLOCKERS"):
            contracts.validate(self._load("triad.gate_receipt.v2", "invalid"))

    def test_gate_pass_without_rollback_proof_rejects(self):
        event = self._load("triad.gate_receipt.v2")
        event["payload"]["rollback_proof_ids"] = []
        with pytest.raises(contracts.ContractError, match="ROLLBACK_PROOF"):
            contracts.validate(event)


# --- descriptor v2 + frozen history --------------------------------------------------------------
class TestDescriptorLaw:
    def test_frozen_descriptors_byte_stable(self):
        legacy = ROOT / "contracts/manifest/contract_bundle.manifest.v1.json"
        r00 = ROOT / "contracts/manifest/contract_bundle.manifest.r00.v1.json"
        assert hashlib.sha256(legacy.read_bytes()).hexdigest() == (
            "a4184b29288e58cd9ac65738c2ecc02b1ee1f21481c3698542b9de0ae1bf8ab6")
        assert hashlib.sha256(r00.read_bytes()).hexdigest() == (
            "600de537734e93eb5f4d2c06184649311b555b02a146c1d0c114f7b6a8379e86")

    def test_descriptor_v2_media_types(self):
        manifest = json.loads(
            (ROOT / "contracts/manifest/contract_bundle.manifest.b01.v2.json").read_text())
        for artifact in manifest["payload"]["artifacts"]:
            if artifact["path"].endswith(".schema.json"):
                assert artifact["media_type"] == "application/schema+json", artifact["path"]
            else:
                assert artifact["media_type"] == "application/json", artifact["path"]

    def test_superseded_paths_declare_new_versions(self):
        fill = json.loads((ROOT / "contracts/schemas/triad.fill.v3.schema.json").read_text())
        assert fill["properties"]["schema_version"]["const"] == "3.1.0"
        assert fill["properties"]["payload"]["properties"]["environment"]["enum"] == [
            "LIVE", "TESTNET"]
        cmd = json.loads(
            (ROOT / "contracts/schemas/triad.execution_cmd.v2.schema.json").read_text())
        assert cmd["properties"]["schema_version"]["const"] == "2.1.0"
        assert "venue_environment" in cmd["properties"]["payload"]["required"]
        assert "venue_activation_revision" in cmd["properties"]["payload"]["required"]

    def test_verify_manifest_gate_passes(self):
        proc = subprocess.run([sys.executable, str(ROOT / "tools/verify_manifest.py")],
                              capture_output=True, text=True, cwd=ROOT)
        assert proc.returncode == 0, proc.stderr

    def test_registry_records_supersession(self):
        index = json.loads((ROOT / "contracts/registry/index.json").read_text())
        by_id = {c["contract_id"]: c for c in index["contracts"]}
        assert by_id["triad.activation_manifest.v1"]["superseded_by"] == (
            "triad.engine_control_manifest.v2")
        assert "triad.engine_control_manifest.v2" in by_id
        assert "triad.execution_authorization.v3" in by_id


# --- epoch-law regression (R00 correction held under B01 contracts) ------------------------------
class TestEpochLawRegression:
    def test_current_epoch_accepted_lower_rejected(self):
        assert contracts.assert_epoch_ge({"producer_epoch": "7"}, 7) == 7
        with pytest.raises(contracts.StaleEpochError):
            contracts.assert_epoch_ge({"producer_epoch": "6"}, 7)

    def test_new_authority_contracts_require_epoch(self):
        for cid in ("triad.runtime_lever_attestation.v1", "triad.shadow_trade.v1",
                    "triad.paper_trade.v1", "triad.shadow_health.v1",
                    "triad.execution_authorization.v3"):
            schema = json.loads(
                (ROOT / f"contracts/schemas/{cid}.schema.json").read_text())
            assert "producer_epoch" in schema["required"], cid


# --- B-series receipt ----------------------------------------------------------------------------
class TestMilestoneReceipt:
    def test_b00_receipt_valid(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "tools/validate_b_receipt.py"),
             str(ROOT / "evidence/receipts/B00.json")],
            capture_output=True, text=True, cwd=ROOT)
        assert proc.returncode == 0, proc.stderr

    def test_receipt_signature_tamper_detected(self, tmp_path):
        event = json.loads((ROOT / "evidence/receipts/B00.json").read_text())
        event["payload"]["evidence_ids"].append("forged-evidence")
        bad = tmp_path / "B00.json"
        bad.write_text(json.dumps(event))
        proc = subprocess.run(
            [sys.executable, str(ROOT / "tools/validate_b_receipt.py"), str(bad)],
            capture_output=True, text=True, cwd=ROOT)
        assert proc.returncode == 1
        assert "self-integrity" in proc.stderr


# --- shadow / paper plane guards -----------------------------------------------------------------
class TestPlaneContracts:
    def test_shadow_rejection_audit_never_carries_geometry(self):
        event = json.loads(
            (ROOT / "contracts/golden/triad.shadow_rejection_audit.v1/valid.json").read_text())
        contracts.validate(event)
        event["payload"]["proposed_geometry"] = {"entry": "100"}
        with pytest.raises(contracts.ContractError):
            contracts.validate(event)

    def test_paper_trade_never_carries_venue_identity(self):
        event = json.loads(
            (ROOT / "contracts/golden/triad.paper_trade.v1/valid.json").read_text())
        contracts.validate(event)
        event["payload"]["venue_order_id"] = "v-1"
        with pytest.raises(contracts.ContractError):
            contracts.validate(event)

    def test_shadow_trade_population_closed(self):
        event = json.loads(
            (ROOT / "contracts/golden/triad.shadow_trade.v1/valid.json").read_text())
        contracts.validate(event)
        event["payload"]["population"] = "LIVE"
        with pytest.raises(contracts.ContractError):
            contracts.validate(event)
