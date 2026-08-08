"""The human/tool byte manifest is itself regenerated and verified exactly."""

from __future__ import annotations

import json

from tools import verify_manifest


def test_manifest_sha_tamper_fails_gate(tmp_path, monkeypatch):
    damaged = tmp_path / "MANIFEST.sha256"
    damaged.write_text("0" * 64 + "  contracts/registry/index.json\n", encoding="utf-8")
    monkeypatch.setattr(verify_manifest, "MANIFEST_SHA", damaged)
    assert verify_manifest.main() == 1


def test_missing_manifest_sha_fails_gate(tmp_path, monkeypatch):
    missing = tmp_path / "missing-MANIFEST.sha256"
    monkeypatch.setattr(verify_manifest, "MANIFEST_SHA", missing)
    assert verify_manifest.main() == 1


def test_legacy_descriptor_pins_current_rc1_artifact_bytes(tmp_path, monkeypatch):
    original = json.loads(verify_manifest.LEGACY_MANIFEST_JSON.read_text(encoding="utf-8"))
    original["artifacts"][0]["sha256"] = "0" * 64
    descriptor = tmp_path / "legacy.json"
    descriptor.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(verify_manifest, "LEGACY_MANIFEST_JSON", descriptor)
    # Keep the descriptor-file pin aligned so this specifically exercises artifact-byte binding.
    monkeypatch.setattr(
        verify_manifest,
        "LEGACY_MANIFEST_SHA256",
        verify_manifest._sha256_bytes(descriptor.read_bytes()),
    )
    assert verify_manifest.main() == 1
