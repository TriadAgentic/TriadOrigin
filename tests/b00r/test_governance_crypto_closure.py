"""Focused closure tests for external authority, provider evidence, and Git/manifest binding."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import governance as gov  # noqa: E402
from triad_origin.canonical import canonical_json, sha256_hex  # noqa: E402
from tools.validate_authority_root import (  # noqa: E402
    AuthorityContext, AuthorityRootError, CANONICAL_AUTHORITY_PATHS, SUBJECTS,
    load_authority_context, validate_git_bound_authority)
from tools.validate_b_receipt import ReceiptBindingError, validate_receipt_bindings  # noqa: E402
from tools.validate_governance_snapshot import _validate_git_binding  # noqa: E402


def _pub_hex(private_key) -> str:
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    return private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()


def _write(path: pathlib.Path, value: dict) -> None:
    path.write_bytes(canonical_json(value))


def _signed_authority(tmp_path: pathlib.Path):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    owner = Ed25519PrivateKey.generate()
    producer = Ed25519PrivateKey.generate()
    counter = Ed25519PrivateKey.generate()
    registry = {
        "schema": "triad.receipt_trust_registry.v1", "schema_version": "1.0.0",
        "registry_kind": "RECEIPT_TRUST_REGISTRY", "registry_id": "test/1",
        "authenticated": True,
        "keys": [
            {"key_id": "owner", "identity": "owner@example.test", "role": "AUTHORITY_OWNER",
             "algorithm": "ed25519", "public_key_hex": _pub_hex(owner), "not_before_us": 1,
             "not_after_us": 1000,
             "scope": "DEC-AUTHORITY-BUNDLE-001,DEC-RECEIPT-PROFILE-001,DEC-B00-REPAIR-001",
             "revoked": False},
            {"key_id": "producer", "identity": "producer@example.test",
             "role": "EVIDENCE_PRODUCER", "algorithm": "ed25519",
             "public_key_hex": _pub_hex(producer), "not_before_us": 1,
             "not_after_us": 1000, "scope": "B00R..B07", "revoked": False},
            {"key_id": "counter", "identity": "counter@example.test",
             "role": "INDEPENDENT_COUNTERSIGNER", "algorithm": "ed25519",
             "public_key_hex": _pub_hex(counter), "not_before_us": 1,
             "not_after_us": 1000, "scope": "B00R..B07", "revoked": False},
        ],
    }
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "test")
    authority_relpaths = {
        "RC2_complete_checklist":
            "docs/spec_rc2/01_TRIAD_ORIGIN_V7_COMPLETE_IMPLEMENTATION_CHECKLIST_1.0.0_RC2.html",
        "RC2_master_workbook":
            "docs/spec_rc2/TRIAD_ORIGIN_V7_IMPLEMENTATION_CONTROL_WORKBOOK_1.0.0_RC2.xlsx",
        "RC2_wiring_guide":
            "docs/spec_rc2/02_TRIAD_ORIGIN_V7_WIRING_FORMULA_AND_PLUMBING_GUIDE_1.0.0_RC2.html",
        "RC3_master_document":
            "docs/spec_rc3/TRIAD_ORIGIN_V7_COMPLETE_MASTER_SPECIFICATION_AND_MASTER_DOCUMENT_1.0.0_RC3.html",
        "RC4_master_addendum":
            "docs/spec_rc4/TRIAD_ORIGIN_V7_FOUR_PLANE_EXECUTION_AND_LEVER_MASTER_ADDENDUM_1.0.0_RC4.html",
        "rc3_effective_control_bundle": "docs/control/rc3_effective_control_bundle.json",
        "rc4_control_bundle": "docs/control/rc4_control_bundle.json",
    }
    authority_subjects = {}
    for name, rel in authority_relpaths.items():
        candidate = repo / rel
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_bytes(f"test subject {name}".encode())
        authority_subjects[name] = sha256_hex(candidate.read_bytes())
    profile_relpaths = {
        "evidence_manifest_schema": "contracts/schemas/triad.evidence_manifest.v1.schema.json",
        "evidence_receipt_v3_schema": "contracts/schemas/triad.evidence_receipt.v3.schema.json",
        "trust_registry_schema": "contracts/schemas/triad.receipt_trust_registry.v1.schema.json",
    }
    profile_subjects = {}
    for name, rel in profile_relpaths.items():
        candidate = repo / rel
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_bytes((ROOT / rel).read_bytes())
        profile_subjects[name] = sha256_hex(candidate.read_bytes())
    invalidation = repo / "docs/governance/B00_B07_INVALIDATION_MANIFEST.v1.json"
    invalidation.parent.mkdir(parents=True, exist_ok=True)
    invalidation.write_bytes(b"{}")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "audited start")
    audited = _git(repo, "rev-parse", "HEAD")
    policy = repo / "docs/control/b00r_policy.v1.json"
    policy.write_bytes(canonical_json({"audited_start_sha": audited}))
    _git(repo, "add", policy.relative_to(repo).as_posix())
    _git(repo, "commit", "-m", "policy")

    external = tmp_path / "external"
    external.mkdir()
    paths: dict[str, pathlib.Path] = {}
    trust_path = repo / CANONICAL_AUTHORITY_PATHS["trust_registry"]
    trust_path.parent.mkdir(parents=True, exist_ok=True)
    _write(trust_path, registry)
    paths["trust_registry"] = trust_path
    for name in ("authority_bundle", "receipt_profile", "b00_repair"):
        template = SUBJECTS[name][3]
        decision = json.loads(template.read_text(encoding="utf-8"))
        if name == "authority_bundle":
            decision["subject_sha256s"] = authority_subjects
        elif name == "receipt_profile":
            decision["subject_sha256s"] = profile_subjects
        else:
            decision["subject_sha256s"] = {
                "audited_start_sha": audited,
                "invalidation_manifest": sha256_hex(invalidation.read_bytes()),
            }
            decision["scope"]["audited_start"] = f"main@{audited}"
        decision.update({"authenticated": True, "issuer": "owner@example.test",
                         "effective_at_us": 2, "signatures": []})
        signature = owner.sign(gov.canonical_decision_signing_bytes(decision)).hex()
        decision["signatures"] = [{"key_id": "owner", "signature_hex": signature}]
        path = repo / CANONICAL_AUTHORITY_PATHS[name]
        path.parent.mkdir(parents=True, exist_ok=True)
        _write(path, decision)
        paths[name] = path
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "authenticated authority")
    pins = {SUBJECTS[name][0]: hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in paths.items()}
    pins_path = external / "pins.json"
    _write(pins_path, pins)
    return repo, paths, pins_path, pins


def test_authority_root_verifies_real_dec_signatures_and_external_pins(tmp_path):
    repo, paths, pins_path, pins = _signed_authority(tmp_path)
    context = load_authority_context(
        now_us=100, pins_path=pins_path, subject_paths=paths, environ={}, repo_root=repo)
    assert context.receipt_threshold == 2
    assert context.receipt_roles == ("EVIDENCE_PRODUCER", "INDEPENDENT_COUNTERSIGNER")
    validate_git_bound_authority(
        context, git_root=repo, expected_head=_git(repo, "rev-parse", "HEAD"))

    tampered = json.loads(paths["b00_repair"].read_text())
    tampered["signatures"][0]["signature_hex"] = "0" * 128
    _write(paths["b00_repair"], tampered)
    with pytest.raises(AuthorityRootError, match="WORKTREE_NOT_CLEAN"):
        validate_git_bound_authority(
            context, git_root=repo, expected_head=_git(repo, "rev-parse", "HEAD"))
    pins[SUBJECTS["b00_repair"][0]] = sha256_hex(paths["b00_repair"].read_bytes())
    _write(pins_path, pins)
    with pytest.raises(AuthorityRootError, match="DECISION_SIGNATURE_INVALID"):
        load_authority_context(
            now_us=100, pins_path=pins_path, subject_paths=paths, environ={}, repo_root=repo)


def test_pass_receipt_requires_trusted_now_us():
    receipt = json.loads(
        (ROOT / "contracts/golden/triad.evidence_receipt.v3/valid.json").read_text())
    result, reason = gov.validate_receipt_v3(receipt, milestone="B00R", trust={})
    assert (result, reason) == ("BLOCKED", "NOW_US_REQUIRED")


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (lambda p: p.update(repository="elsewhere/repo"), "REPOSITORY_IDENTITY_MISMATCH"),
        (lambda p: p.update(source_pr=0), "SOURCE_PR_INVALID"),
        (lambda p: p.update(repair_generation=2), "ROOT_REPAIR_GENERATION_MISMATCH"),
        (lambda p: p["scope"].update(milestone="B01C"), "SCOPE_IDENTITY_MISMATCH"),
    ],
)
def test_receipt_identity_fields_are_semantically_bound(mutation, reason):
    receipt = json.loads(
        (ROOT / "contracts/golden/triad.evidence_receipt.v3/valid.json").read_text())
    mutation(receipt["payload"])
    result, actual = gov.validate_receipt_v3(receipt, milestone="B00R", now_us=3_000_000)
    assert (result, actual) == ("FAIL", reason)


def test_receipt_profile_cannot_collapse_two_party_separation():
    profile = json.loads(
        (ROOT / "docs/governance/decisions/DEC-RECEIPT-PROFILE-001.template.json").read_text())
    profile["scope"]["signer_threshold"] = 1
    profile["scope"]["signer_roles"] = ["AUTHORITY_OWNER"]
    with pytest.raises(gov.GovernanceError, match="BAD_THRESHOLD"):
        gov.receipt_profile_from_decision(profile)


def _raw_ruleset() -> dict:
    return {
        "id": 42, "name": "main", "target": "branch", "source_type": "Repository",
        "source": "TriadAgentic/TriadOrigin", "enforcement": "active", "bypass_actors": [],
        "node_id": "RRS_provider42",
        "_links": {
            "self": {"href": "https://api.github.com/repos/TriadAgentic/TriadOrigin/rulesets/42"},
            "html": {"href": "https://github.com/TriadAgentic/TriadOrigin/rules/42"},
        },
        "created_at": "1970-01-01T00:00:05Z",
        "updated_at": "1970-01-01T00:00:10Z",
        "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
        "rules": [
            {"type": "pull_request", "parameters": {
                "required_approving_review_count": 1, "dismiss_stale_reviews_on_push": True,
                "require_code_owner_review": True, "require_last_push_approval": True,
                "required_review_thread_resolution": True}},
            {"type": "required_status_checks", "parameters": {
                "strict_required_status_checks_policy": True,
                "required_status_checks": [{"context": "CI / test-and-verify"}]}},
            {"type": "deletion"}, {"type": "non_fast_forward"},
        ],
    }


def test_governance_snapshot_is_derived_from_pinned_raw_provider_response():
    raw_bytes = canonical_json(_raw_ruleset())
    pin = sha256_hex(raw_bytes)
    doc = {
        "schema": "triad.governance_snapshot.v1", "schema_version": "1.0.0",
        "snapshot_kind": "GOVERNANCE_SNAPSHOT", "authenticated": True,
        "effective_at_us": 10_000_000,
        "provider": {"name": "github", "repository": "TriadAgentic/TriadOrigin",
                     "captured_at_us": 20_000_000, "api_response_path": "evidence/raw.json",
                     "api_response_sha256": pin},
        "ruleset": {"ruleset_id": "42", "target": "refs/heads/main",
                    "pull_request_required": True,
                    "required_status_check": "CI / test-and-verify",
                    "strict_required_status": True, "required_approvals": 1,
                    "dismiss_stale_reviews": True, "require_conversation_resolution": True,
                    "block_force_push": True, "block_deletions": True, "bypass_actors": []},
    }
    assert gov.validate_governance_snapshot(
        doc, provider_raw_bytes=raw_bytes, external_pin=pin, now_us=30_000_000) == ("PASS", "OK")
    # Source-PR bootstrap is valid before a merge exists; receipt mode can add the time binding.
    assert gov.validate_governance_snapshot(
        doc, provider_raw_bytes=raw_bytes, external_pin=pin, now_us=30_000_000,
        source_merge_time_us=25_000_000) == ("PASS", "OK")
    altered = _raw_ruleset()
    altered.pop("bypass_actors")
    altered_bytes = canonical_json(altered)
    altered_pin = sha256_hex(altered_bytes)
    changed = copy.deepcopy(doc)
    changed["provider"]["api_response_sha256"] = altered_pin
    result, reason = gov.validate_governance_snapshot(
        changed, provider_raw_bytes=altered_bytes, external_pin=altered_pin, now_us=30_000_000)
    assert result == "FAIL" and "BYPASS" in reason


def _snapshot_for_raw(raw: dict) -> tuple[dict, bytes, str]:
    raw_bytes = canonical_json(raw)
    pin = sha256_hex(raw_bytes)
    doc = {
        "schema": "triad.governance_snapshot.v1", "schema_version": "1.0.0",
        "snapshot_kind": "GOVERNANCE_SNAPSHOT", "authenticated": True,
        "effective_at_us": 10_000_000,
        "provider": {"name": "github", "repository": "TriadAgentic/TriadOrigin",
                     "captured_at_us": 20_000_000, "api_response_path": "evidence/raw.json",
                     "api_response_sha256": pin},
        "ruleset": {"ruleset_id": str(raw.get("id")), "target": "refs/heads/main",
                    "pull_request_required": True,
                    "required_status_check": "CI / test-and-verify",
                    "strict_required_status": True, "required_approvals": 1,
                    "dismiss_stale_reviews": True, "require_conversation_resolution": True,
                    "block_force_push": True, "block_deletions": True, "bypass_actors": []},
    }
    return doc, raw_bytes, pin


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (lambda raw: raw.__setitem__("id", "DECLARATIVE"), "RULESET_ID"),
        (lambda raw: raw.__setitem__("name", "PLACEHOLDER"), "RULESET_NAME"),
        (lambda raw: raw.__setitem__("note", "actual enforcement pending"), "SYNTHETIC"),
        (lambda raw: raw.pop("source_type"), "SOURCE_TYPE"),
        (lambda raw: raw.pop("node_id"), "NODE_ID"),
        (lambda raw: raw.pop("_links"), "PROVIDER_LINKS"),
        (
            lambda raw: raw["_links"]["self"].__setitem__(
                "href", "https://example.invalid/forged"
            ),
            "PROVIDER_LINKS",
        ),
    ],
)
def test_governance_snapshot_rejects_non_provider_ruleset_shapes(mutation, reason):
    raw = _raw_ruleset()
    mutation(raw)
    doc, raw_bytes, pin = _snapshot_for_raw(raw)
    result, actual = gov.validate_governance_snapshot(
        doc, provider_raw_bytes=raw_bytes, external_pin=pin, now_us=30_000_000
    )
    assert result == "FAIL"
    assert reason in actual


def test_checked_in_declarative_ruleset_stub_cannot_pass_even_when_pinned():
    doc = json.loads(
        (ROOT / "docs/governance/rulesets/main.ruleset.provider.json").read_text()
    )
    raw_bytes = (
        ROOT / "docs/governance/rulesets/main.ruleset.provider.raw.json"
    ).read_bytes()
    pin = sha256_hex(raw_bytes)
    doc["authenticated"] = True
    result, reason = gov.validate_governance_snapshot(
        doc, provider_raw_bytes=raw_bytes, external_pin=pin,
        now_us=doc["provider"]["captured_at_us"] + 1,
    )
    assert result == "FAIL"
    assert "SYNTHETIC" in reason or "RULESET_ID" in reason


def test_normalized_snapshot_commentary_cannot_authenticate_provider_bytes():
    raw = _raw_ruleset()
    doc, raw_bytes, pin = _snapshot_for_raw(raw)
    doc["provider"]["note"] = "hand-authored declaration"
    result, reason = gov.validate_governance_snapshot(
        doc, provider_raw_bytes=raw_bytes, external_pin=pin, now_us=30_000_000
    )
    assert (result, reason) == ("FAIL", "GOVERNANCE_PROVIDER_SYNTHETIC_METADATA")


def test_source_governance_evidence_is_exact_head_bound(tmp_path):
    repo = tmp_path / "repo"
    snapshot = repo / "docs/governance/rulesets/main.ruleset.provider.json"
    raw = repo / "docs/governance/rulesets/main.ruleset.provider.raw.json"
    raw.parent.mkdir(parents=True)
    snapshot.write_bytes(b"snapshot")
    raw.write_bytes(b"raw")
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "test")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "governance")
    head = _git(repo, "rev-parse", "HEAD")
    _validate_git_binding(path=snapshot, raw_path=raw, git_root=repo, expected_head=head)
    raw.write_bytes(b"runtime replacement")
    with pytest.raises(ValueError, match="WORKTREE_NOT_CLEAN"):
        _validate_git_binding(path=snapshot, raw_path=raw, git_root=repo, expected_head=head)


def test_manifest_symlink_scan_is_bounded_to_resolved_root(tmp_path):
    real_root = tmp_path / "real"
    (real_root / "evidence").mkdir(parents=True)
    (real_root / "evidence/a.json").write_text("{}")
    root_link = tmp_path / "root-link"
    root_link.symlink_to(real_root, target_is_directory=True)
    manifest = {
        "schema": "triad.evidence_manifest.v1", "schema_version": "1.0.0",
        "manifest_kind": "EVIDENCE_MANIFEST", "entry_count": 1,
        "entries": [{"path": "evidence/a.json", "role": "A",
                     "media_type": "application/json", "size": 2,
                     "sha256": sha256_hex(b"{}")}]}
    gov.validate_evidence_manifest(manifest, root_link)

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "b.json").write_text("{}")
    (real_root / "escape").symlink_to(outside, target_is_directory=True)
    escaped = copy.deepcopy(manifest)
    escaped["entries"][0]["path"] = "escape/b.json"
    with pytest.raises(gov.GovernanceError, match="SYMLINK|ESCAPE"):
        gov.validate_evidence_manifest(escaped, real_root)


def _git(root: pathlib.Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(root), *args], check=True,
                          capture_output=True, text=True)
    return proc.stdout.strip()


def test_receipt_binding_rejects_unlisted_tracked_milestone_evidence(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "test")
    (repo / "source.txt").write_text("source")
    governance_dir = repo / "docs/governance/rulesets"
    governance_dir.mkdir(parents=True)
    snapshot_path = governance_dir / "main.ruleset.provider.json"
    provider_raw_path = governance_dir / "main.ruleset.provider.raw.json"
    snapshot_path.write_bytes(b"source snapshot")
    provider_raw_path.write_bytes(b"source raw")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "source")
    source = _git(repo, "rev-parse", "HEAD")
    source_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    source_time = int(_git(repo, "show", "-s", "--format=%ct", "HEAD")) * 1_000_000

    roles = ["WORKFLOW", "CONTRACT_MANIFEST", "TEST_MANIFEST", "CONFIG_BUNDLE",
             "ROLLBACK_PROOF"]
    entries = []
    for i, role in enumerate(roles):
        rel = f"evidence/B00R/{i}-{role.lower()}.json"
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        data = canonical_json({"role": role})
        path.write_bytes(data)
        entries.append({"path": rel, "role": role, "media_type": "application/json",
                        "size": len(data), "sha256": sha256_hex(data)})
    entries.sort(key=lambda item: item["path"])
    manifest = {"schema": "triad.evidence_manifest.v1", "schema_version": "1.0.0",
                "manifest_kind": "EVIDENCE_MANIFEST", "entry_count": len(entries),
                "entries": entries}
    manifest_path = repo / "evidence/B00R/evidence_manifest.json"
    manifest_path.write_bytes(canonical_json(manifest))
    by_role = {entry["role"]: entry["sha256"] for entry in entries}
    receipt = json.loads(
        (ROOT / "contracts/golden/triad.evidence_receipt.v3/valid.json").read_text())
    payload = receipt["payload"]
    payload.update({
        "source_merge_sha": source, "source_merge_tree": source_tree,
        "final_source_head": source, "source_merge_time_us": source_time,
        "audited_start_sha": source, "repair_decision_sha256": "d" * 64,
        "invalidation_manifest_sha256": "e" * 64,
        "evidence_manifest_sha256": sha256_hex(manifest_path.read_bytes()),
        "evidence_ids": [entry["path"] for entry in entries],
        "evidence_sha256s": [entry["sha256"] for entry in entries],
        "workflow_sha256": by_role["WORKFLOW"],
        "contract_manifest_sha256": by_role["CONTRACT_MANIFEST"],
        "test_manifest_sha256": by_role["TEST_MANIFEST"],
        "config_bundle_sha256": by_role["CONFIG_BUNDLE"],
        "rollback_proof_sha256": by_role["ROLLBACK_PROOF"],
    })
    receipt_path = repo / "evidence/receipts/B00R.receipt.v3.json"
    receipt_path.parent.mkdir(parents=True)
    receipt_path.write_bytes(canonical_json(receipt))
    _git(repo, "add", "evidence")
    _git(repo, "commit", "-m", "receipt")
    head = _git(repo, "rev-parse", "HEAD")
    authority = AuthorityContext(
        trust={}, decisions={"b00_repair": {"effective_at_us": 1, "subject_sha256s": {
            "invalidation_manifest": "e" * 64, "audited_start_sha": source}}},
        digests={"b00_repair": "d" * 64}, receipt_threshold=2,
        receipt_roles=("EVIDENCE_PRODUCER", "INDEPENDENT_COUNTERSIGNER"),
        receipt_algorithm="ed25519")
    validate_receipt_bindings(
        receipt, receipt_path=receipt_path, manifest_path=manifest_path, git_root=repo,
        expected_head=head, authority=authority,
        governance_evidence_paths=(snapshot_path, provider_raw_path))

    extra = repo / "evidence/B00R/unlisted.json"
    extra.write_text("{}")
    _git(repo, "add", extra.relative_to(repo).as_posix())
    _git(repo, "commit", "-m", "unlisted")
    with pytest.raises(ReceiptBindingError, match="NAMESPACE_NOT_CLOSED"):
        validate_receipt_bindings(
            receipt, receipt_path=receipt_path, manifest_path=manifest_path, git_root=repo,
            expected_head=_git(repo, "rev-parse", "HEAD"), authority=authority,
            governance_evidence_paths=(snapshot_path, provider_raw_path))
