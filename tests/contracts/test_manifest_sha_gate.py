"""The human/tool byte manifest is itself regenerated and verified exactly."""

from __future__ import annotations

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
