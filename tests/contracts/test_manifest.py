"""The committed bundle descriptor must itself satisfy its declared contract."""

from __future__ import annotations

import json
import pathlib

from triad_origin import contracts

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def test_committed_contract_manifest_validates():
    path = ROOT / "contracts" / "manifest" / "contract_bundle.manifest.v1.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    contracts.validate(manifest, schema_id="triad.contract_bundle.manifest.v1")
