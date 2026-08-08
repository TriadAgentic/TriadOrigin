"""The committed bundle descriptor must itself satisfy its declared contract."""

from __future__ import annotations

import json
import hashlib
import pathlib

from triad_origin import contracts

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


LEGACY_DESCRIPTOR_SHA256 = "a4184b29288e58cd9ac65738c2ecc02b1ee1f21481c3698542b9de0ae1bf8ab6"


def test_immutable_rc1_descriptor_bytes_are_preserved():
    path = ROOT / "contracts" / "manifest" / "contract_bundle.manifest.v1.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == LEGACY_DESCRIPTOR_SHA256
    descriptor = json.loads(path.read_text(encoding="utf-8"))
    assert descriptor["bundle_version"] == "origin.contracts.1.0.0-RC1"
    assert "payload" not in descriptor  # published RC1 provenance; repaired only additively


def test_additive_r00_contract_manifest_validates():
    path = ROOT / "contracts" / "manifest" / "contract_bundle.manifest.r00.v1.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    contracts.validate(manifest, schema_id="triad.contract_bundle.manifest.v1")
    assert manifest["payload"]["bundle_version"] == "origin.contracts.1.0.0-RC1"
    assert manifest["payload"]["descriptor_version"] == (
        "origin.contract-bundle-descriptor.r00.v1"
    )
