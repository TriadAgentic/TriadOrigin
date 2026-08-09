"""B01R binding.v2 foundation — acceptance battery.

Reconciled-plan B01 scope closed here: binding.v2 schema + semantic validator, structural
migration of all 105 effective bindings with source states preserved, and the no-blocked-
consumption law. Structural migration never ratifies a value.
"""

from __future__ import annotations

import copy
import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import bindings, contracts  # noqa: E402
from triad_origin.canonical import canonical_json, sha256_hex  # noqa: E402

PY = sys.executable
REGISTRY_PATH = ROOT / "docs" / "control" / "binding_registry.v2.json"
REGISTRY = json.loads(REGISTRY_PATH.read_text())


def _resign(row: dict) -> dict:
    unsigned = {k: v for k, v in row.items() if k != "binding_digest"}
    row["binding_digest"] = sha256_hex(canonical_json(unsigned))
    return row


class TestStructuralMigration:
    def test_all_105_rows_accounted(self):
        assert REGISTRY["row_count"] == 105
        assert len(REGISTRY["rows"]) == 105

    def test_source_states_preserved_verbatim(self):
        assert REGISTRY["status_counts"] == {
            "ACTIVE": 3, "BLOCKED": 4, "BLOCKED_BINDING_V2_MIGRATION": 98}

    def test_registry_generator_is_current(self):
        result = subprocess.run(
            [PY, str(ROOT / "tools" / "gen_binding_registry.py"), "--verify"],
            capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

    def test_every_row_schema_and_semantically_valid(self):
        for row in REGISTRY["rows"]:
            contracts.validate_payload("triad.binding.v2", row)

    def test_source_bundle_digest_binds(self):
        bundle = (ROOT / "docs" / "control" / "rc3_effective_control_bundle.json").read_bytes()
        assert REGISTRY["source_bundle_digest"] == sha256_hex(bundle)

    def test_no_row_invents_a_ratified_value(self):
        # Every non-ACTIVE row keeps a named disposition; none carries a fabricated activation.
        for row in REGISTRY["rows"]:
            if row["status"] != "ACTIVE":
                assert row["disposition_reason"], row["binding_id"]


@pytest.fixture(scope="module")
def registry():
    return bindings.load_registry()


class TestConsumptionLaw:

    def test_active_slot_resolves(self, registry):
        row = registry.resolve("ingress_price_wire_integer_ticks")
        assert row["binding_id"] == "FPB-0001"
        assert row["status"] == "ACTIVE"

    def test_blocked_binding_not_consumable(self, registry):
        blocked = next(r for r in REGISTRY["rows"]
                       if r["status"] == "BLOCKED_BINDING_V2_MIGRATION")
        with pytest.raises(bindings.BindingBlockedError) as err:
            registry.resolve(blocked["semantic_slot"])
        assert err.value.status == "BLOCKED_BINDING_V2_MIGRATION"

    def test_research_blocked_f06_named(self, registry):
        f06 = next(r for r in REGISTRY["rows"] if r["binding_id"] == "RC3-FPB-001")
        with pytest.raises(bindings.BindingBlockedError) as err:
            registry.resolve(f06["semantic_slot"])
        assert "NOT_RATIFIED" in err.value.disposition

    def test_unknown_slot_fails_closed(self, registry):
        with pytest.raises(bindings.BindingUnknownError):
            registry.resolve("no_such_semantic_slot")

    def test_resolve_for_formula_blocked_raises_named(self, registry):
        with pytest.raises(bindings.BindingBlockedError):
            registry.resolve_for_formula("F08")

    def test_resolve_for_formula_active(self, registry):
        rows = registry.resolve_for_formula("F00")
        assert {r["binding_id"] for r in rows} == {"FPB-0001", "FPB-0002"}

    def test_row_read_of_record_any_status(self, registry):
        row = registry.row("RC3-FPB-002")
        assert row["status"] == "BLOCKED"


class TestRegistryIntegrity:
    def _load_mutated(self, tmp_path, mutate):
        registry = copy.deepcopy(REGISTRY)
        mutate(registry)
        path = tmp_path / "registry.json"
        path.write_text(json.dumps(registry))
        return path

    def test_tampered_row_digest_fails(self, tmp_path):
        def mutate(reg):
            reg["rows"][0]["declared_value"] = "tampered"
        path = self._load_mutated(tmp_path, mutate)
        with pytest.raises(bindings.BindingRegistryError, match="DIGEST_MISMATCH"):
            bindings.load_registry(path)

    def test_resigned_activation_forgery_fails_semantically(self, tmp_path):
        # An attacker re-signs a blocked row as ACTIVE: the semantic law still refuses
        # (unresolved cardinality / unmigrated state), so forgery needs more than a hash.
        def mutate(reg):
            row = next(r for r in reg["rows"]
                       if r["status"] == "BLOCKED_BINDING_V2_MIGRATION")
            row["status"] = "ACTIVE"
            row["lifecycle_status"] = "ACTIVE"
            _resign(row)
        path = self._load_mutated(tmp_path, mutate)
        with pytest.raises(bindings.BindingRegistryError,
                           match="BINDING_ACTIVE_WITH_UNRESOLVED_CARDINALITY"):
            bindings.load_registry(path)

    def test_duplicate_active_slot_overlap_fails(self, tmp_path):
        def mutate(reg):
            src = next(r for r in reg["rows"] if r["binding_id"] == "FPB-0001")
            clone = copy.deepcopy(src)
            clone["binding_id"] = "FPB-9999"
            _resign(clone)
            reg["rows"].append(clone)
            reg["row_count"] = len(reg["rows"])
            reg["status_counts"] = dict(reg["status_counts"])
            reg["status_counts"]["ACTIVE"] += 1
        path = self._load_mutated(tmp_path, mutate)
        with pytest.raises(bindings.BindingRegistryError, match="OVERLAP"):
            bindings.load_registry(path)

    def test_status_count_disagreement_fails(self, tmp_path):
        def mutate(reg):
            reg["status_counts"] = dict(reg["status_counts"])
            reg["status_counts"]["ACTIVE"] = 99
        path = self._load_mutated(tmp_path, mutate)
        with pytest.raises(bindings.BindingRegistryError, match="disagree"):
            bindings.load_registry(path)

    def test_duplicate_binding_id_fails(self, tmp_path):
        def mutate(reg):
            reg["rows"].append(copy.deepcopy(reg["rows"][0]))
        path = self._load_mutated(tmp_path, mutate)
        with pytest.raises(bindings.BindingRegistryError, match="duplicate"):
            bindings.load_registry(path)

    def test_unknown_registry_version_fails(self, tmp_path):
        def mutate(reg):
            reg["registry_version"] = "origin.binding-registry.v3"
        path = self._load_mutated(tmp_path, mutate)
        with pytest.raises(bindings.BindingRegistryError, match="version"):
            bindings.load_registry(path)


class TestBindingContractLaw:
    def test_valid_golden_validates(self):
        golden = json.loads(
            (ROOT / "contracts" / "golden" / "triad.binding.v2" / "valid.json").read_text())
        contracts.validate(golden)

    def test_invalid_golden_rejects_semantically(self):
        golden = json.loads(
            (ROOT / "contracts" / "golden" / "triad.binding.v2" / "invalid.json").read_text())
        with pytest.raises(contracts.ContractError,
                           match="BINDING_ACTIVE_WITH_UNRESOLVED_CARDINALITY"):
            contracts.validate(golden)

    @pytest.mark.parametrize("patch,code", [
        ({"activation_scope": "venue/*"}, "BINDING_ACTIVE_WILDCARD_SCOPE"),
        ({"semantic_slot": ""}, "BINDING_ACTIVE_EMPTY_FIELD"),
        ({"superseded_by": "FPB-0002"}, "BINDING_ACTIVE_BUT_SUPERSEDED"),
        ({"lifecycle_status": "BLOCKED"}, "BINDING_ACTIVE_LIFECYCLE_MISMATCH"),
        ({"status": "BLOCKED", "disposition_reason": ""},
         "BINDING_BLOCKED_WITHOUT_DISPOSITION"),
    ])
    def test_semantic_defects_refused(self, patch, code):
        golden = json.loads(
            (ROOT / "contracts" / "golden" / "triad.binding.v2" / "valid.json").read_text())
        golden["payload"].update(patch)
        _resign(golden["payload"])
        with pytest.raises(contracts.ContractError, match=code):
            contracts.validate(golden)

    def test_digest_mismatch_refused(self):
        golden = json.loads(
            (ROOT / "contracts" / "golden" / "triad.binding.v2" / "valid.json").read_text())
        golden["payload"]["binding_digest"] = "f" * 64
        with pytest.raises(contracts.ContractError, match="BINDING_DIGEST_MISMATCH"):
            contracts.validate(golden)
