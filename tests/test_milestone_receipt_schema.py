"""Milestone receipts cannot validate while omitting required evidence identity."""

from __future__ import annotations

import copy
import json
import pathlib

import jsonschema
import pytest

SCHEMA_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / "docs"
    / "plan"
    / "milestone_receipt.schema.json"
)
ZERO256 = "0" * 64
ZERO40 = "0" * 40


def _valid_receipt() -> dict:
    return {
        "schema": "origin.milestone_receipt.v1",
        "receipt_id": "r00-example",
        "milestone_id": "R00",
        "scope": "repository integrity refreeze",
        "scope_sha256": ZERO256,
        "authority_basis": {
            "status": "INCOMPLETE_AUDIT_BASIS",
            "digest_sha256": ZERO256,
            "canonical": False,
            "inventory_ref": "docs/plan/06_RC2_SOURCE_INVENTORY.md",
        },
        "base_sha": ZERO40,
        "head_sha": ZERO40,
        "merge_sha": ZERO40,
        "toolchain": {
            "python_version": "3.11",
            "platform": "linux",
            "runner_image": "ubuntu-latest",
            "dependency_spec_sha256": ZERO256,
            "dependency_snapshot_sha256": ZERO256,
        },
        "artifacts": [{"name": "source", "kind": "source-tree", "sha256": ZERO256}],
        "ci": {
            "provider": "github-actions",
            "run_id": "1",
            "head_sha": ZERO40,
            "conclusion": "success",
        },
        "tests": [{
            "command": "python -m pytest",
            "exit_code": 0,
            "result_sha256": ZERO256,
            "test_ids_sha256": ZERO256,
            "passed": 1,
            "skips": 0,
            "xfails": 0,
        }],
        "manifests": {"contracts": ZERO256},
        "deferred_evidence": [],
        "negative_capability": {
            "scanner": "tools/verify_no_forbidden_capabilities.py",
            "result_sha256": ZERO256,
            "forbidden_hits": 0,
        },
        "review": {
            "unresolved_actionable_threads": 0,
            "reviewer": "independent-reviewer",
            "review_sha256": ZERO256,
        },
        "post_merge": {
            "fresh_main_sha": ZERO40,
            "reproduced": True,
            "command_set_sha256": ZERO256,
            "result_sha256": ZERO256,
        },
        "supersession": {"supersedes_receipt_id": None, "reason": "first receipt"},
        "rollback": {"strategy": "revert squash commit", "receipt_id": None},
        "status": "VERIFIED",
    }


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_receipt_schema_and_complete_example_validate():
    schema = _schema()
    jsonschema.validators.validator_for(schema).check_schema(schema)
    jsonschema.validate(_valid_receipt(), schema)


def test_receipt_missing_toolchain_is_rejected():
    receipt = _valid_receipt()
    receipt.pop("toolchain")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(receipt, _schema())


def test_incomplete_authority_basis_cannot_claim_canonical():
    receipt = copy.deepcopy(_valid_receipt())
    receipt["authority_basis"]["canonical"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(receipt, _schema())
