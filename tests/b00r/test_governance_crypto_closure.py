"""Focused closure tests for external authority, provider evidence, and Git/manifest binding."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import json
import pathlib
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import governance as gov  # noqa: E402
from triad_origin.canonical import canonical_json, sha256_hex  # noqa: E402
from tools.validate_authority_root import (  # noqa: E402
    AuthorityContext, AuthorityRootError, CANONICAL_AUTHORITY_PATHS, SUBJECTS,
    load_authority_context, validate_git_bound_authority)
from tools.validate_b_receipt import (  # noqa: E402
    ReceiptBindingError, _validate_codeowners_bootstrap, _validate_provider_negative_canary,
    _validate_source_pr_provider_record, validate_receipt_bindings)
from tools.validate_governance_snapshot import _validate_git_binding  # noqa: E402
from tools.verify_codeowners import CRITICAL_PATTERNS  # noqa: E402


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
    policy.write_bytes(canonical_json({"audited_start_sha": audited, "repair_generation": 1}))
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
        now_us=100, pins_path=pins_path, subject_paths=paths, environ={}, repo_root=repo,
        repair_generation=1)
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
            now_us=100, pins_path=pins_path, subject_paths=paths, environ={}, repo_root=repo,
            repair_generation=1)


def test_generation_2_authority_uses_additive_002_under_one_g2_registry(tmp_path):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    owner = Ed25519PrivateKey.generate()
    producer = Ed25519PrivateKey.generate()
    counter = Ed25519PrivateKey.generate()
    owner_identity = "generation-2-owner@example.test"
    registry = {
        "schema": "triad.receipt_trust_registry.v1",
        "schema_version": "1.0.0",
        "registry_kind": "RECEIPT_TRUST_REGISTRY",
        "registry_id": "test/generation-2/1",
        "authenticated": True,
        "keys": [
            {
                "key_id": "g2-owner", "identity": owner_identity,
                "role": "AUTHORITY_OWNER", "algorithm": "ed25519",
                "public_key_hex": _pub_hex(owner), "not_before_us": 1,
                "not_after_us": 9_000_000_000_000_000_000,
                "scope": (
                    "DEC-AUTHORITY-BUNDLE-002,DEC-RECEIPT-PROFILE-002,"
                    "DEC-B00-REPAIR-002"),
                "revoked": False,
            },
            {
                "key_id": "g2-producer", "identity": "producer@example.test",
                "role": "EVIDENCE_PRODUCER", "algorithm": "ed25519",
                "public_key_hex": _pub_hex(producer), "not_before_us": 1,
                "not_after_us": 9_000_000_000_000_000_000,
                "scope": "B00R..B07", "revoked": False,
            },
            {
                "key_id": "g2-counter", "identity": "counter@example.test",
                "role": "INDEPENDENT_COUNTERSIGNER", "algorithm": "ed25519",
                "public_key_hex": _pub_hex(counter), "not_before_us": 1,
                "not_after_us": 9_000_000_000_000_000_000,
                "scope": "B00R..B07", "revoked": False,
            },
        ],
    }
    registry_path = tmp_path / "receipt_trust_registry.g2.v1.json"
    _write(registry_path, registry)

    templates = {
        "authority_bundle": ROOT / (
            "docs/governance/decisions/DEC-AUTHORITY-BUNDLE-002.template.json"),
        "receipt_profile": ROOT / (
            "docs/governance/decisions/DEC-RECEIPT-PROFILE-002.template.json"),
        "b00_repair": ROOT / (
            "docs/governance/decisions/DEC-B00-REPAIR-002.template.json"),
    }
    decisions: dict[str, pathlib.Path] = {}
    for name, template in templates.items():
        document = json.loads(template.read_text())
        document["authenticated"] = True
        document["effective_at_us"] = 1
        document["issuer"] = owner_identity
        document["signatures"] = []
        signature = owner.sign(gov.canonical_decision_signing_bytes(document)).hex()
        document["signatures"] = [{"key_id": "g2-owner", "signature_hex": signature}]
        path = tmp_path / template.name.replace(".template", "")
        _write(path, document)
        decisions[name] = path

    subject_paths = {**decisions, "trust_registry": registry_path}
    environment = {
        "AUTHORITY_BUNDLE_G2_DECISION_SHA256": sha256_hex(
            decisions["authority_bundle"].read_bytes()),
        "RECEIPT_PROFILE_G2_DECISION_SHA256": sha256_hex(
            decisions["receipt_profile"].read_bytes()),
        "B00R_G2_REPAIR_DECISION_SHA256": sha256_hex(
            decisions["b00_repair"].read_bytes()),
        "RECEIPT_G2_TRUST_REGISTRY_SHA256": sha256_hex(registry_path.read_bytes()),
    }
    context = load_authority_context(
        now_us=2,
        environ=environment,
        subject_paths=subject_paths,
        repo_root=ROOT,
        repair_generation=2,
    )
    assert context.decisions["authority_bundle"]["decision_id"] == \
        "DEC-AUTHORITY-BUNDLE-002"
    assert context.paths["authority_bundle"] == decisions["authority_bundle"]
    assert context.repair_generation == 2

    original_registry = copy.deepcopy(registry)
    restricted_registry = copy.deepcopy(registry)
    restricted_registry["keys"][0]["scope"] = (
        "DEC-AUTHORITY-BUNDLE-001,DEC-RECEIPT-PROFILE-001,DEC-B00-REPAIR-001")
    _write(registry_path, restricted_registry)
    environment["RECEIPT_G2_TRUST_REGISTRY_SHA256"] = sha256_hex(
        registry_path.read_bytes())
    with pytest.raises(AuthorityRootError):
        load_authority_context(
            now_us=2, environ=environment, subject_paths=subject_paths,
            repo_root=ROOT, repair_generation=2)
    _write(registry_path, original_registry)
    environment["RECEIPT_G2_TRUST_REGISTRY_SHA256"] = sha256_hex(
        registry_path.read_bytes())

    def replace_signed_decision(name: str, mutation) -> None:
        document = json.loads(templates[name].read_text())
        document["authenticated"] = True
        document["effective_at_us"] = 1
        document["issuer"] = owner_identity
        mutation(document)
        document["signatures"] = []
        document["signatures"] = [{
            "key_id": "g2-owner",
            "signature_hex": owner.sign(
                gov.canonical_decision_signing_bytes(document)).hex(),
        }]
        _write(decisions[name], document)
        environment[{  # exact protected pin for the selected G2 slot
            "authority_bundle": "AUTHORITY_BUNDLE_G2_DECISION_SHA256",
            "receipt_profile": "RECEIPT_PROFILE_G2_DECISION_SHA256",
            "b00_repair": "B00R_G2_REPAIR_DECISION_SHA256",
        }[name]] = sha256_hex(decisions[name].read_bytes())

    replace_signed_decision(
        "authority_bundle", lambda document: document.update(
            decision_id="DEC-AUTHORITY-BUNDLE-001"))
    with pytest.raises(AuthorityRootError, match="DECISION_ID_MISMATCH"):
        load_authority_context(
            now_us=2, environ=environment, subject_paths=subject_paths,
            repo_root=ROOT, repair_generation=2)

    replace_signed_decision(
        "authority_bundle", lambda document: document.update(supersedes=[]))
    with pytest.raises(AuthorityRootError, match="AUTHORITY_BUNDLE_G2_SUPERSESSION_MISMATCH"):
        load_authority_context(
            now_us=2, environ=environment, subject_paths=subject_paths,
            repo_root=ROOT, repair_generation=2)

    replace_signed_decision(
        "authority_bundle", lambda document: document.update(
            authority_registry="docs/governance/trust/receipt_trust_registry.v1.json"))
    with pytest.raises(AuthorityRootError, match="DECISION_AUTHORITY_REGISTRY_MISMATCH"):
        load_authority_context(
            now_us=2, environ=environment, subject_paths=subject_paths,
            repo_root=ROOT, repair_generation=2)

    replace_signed_decision(
        "authority_bundle", lambda _document: None)
    replace_signed_decision(
        "receipt_profile", lambda document: document.update(supersedes=[]))
    with pytest.raises(AuthorityRootError, match="RECEIPT_PROFILE_G2_SUPERSESSION_MISMATCH"):
        load_authority_context(
            now_us=2, environ=environment, subject_paths=subject_paths,
            repo_root=ROOT, repair_generation=2)


def test_pass_receipt_requires_trusted_now_us():
    receipt = json.loads(
        (ROOT / "contracts/golden/triad.evidence_receipt.v3/valid.json").read_text())
    result, reason = gov.validate_receipt_v3(
        receipt, milestone="B00R", trust={}, expected_root_generation=1)
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
    result, actual = gov.validate_receipt_v3(
        receipt, milestone="B00R", now_us=3_000_000, expected_root_generation=1)
    assert (result, actual) == ("FAIL", reason)


def test_receipt_profile_cannot_collapse_two_party_separation():
    profile = json.loads(
        (ROOT / "docs/governance/decisions/DEC-RECEIPT-PROFILE-001.template.json").read_text())
    profile["scope"]["signer_threshold"] = 1
    profile["scope"]["signer_roles"] = ["AUTHORITY_OWNER"]
    with pytest.raises(gov.GovernanceError, match="BAD_THRESHOLD"):
        gov.receipt_profile_from_decision(profile, repair_generation=1)


def _raw_ruleset() -> dict:
    return {
        "id": 42, "name": "main", "target": "branch", "source_type": "Repository",
        "source": "TriadAgentic/TriadOrigin", "enforcement": "active", "bypass_actors": [],
        "current_user_can_bypass": "never", "node_id": "RRS_provider42",
        "_links": {
            "self": {"href": "https://api.github.com/repos/TriadAgentic/TriadOrigin/rulesets/42"},
            "html": {"href": "https://github.com/TriadAgentic/TriadOrigin/rules/42"},
        },
        "created_at": "1970-01-01T00:00:05Z",
        "updated_at": "1970-01-01T00:00:10Z",
        "conditions": {"ref_name": {"include": [
            "refs/heads/main", "refs/heads/b00r-ruleset-canary"
        ], "exclude": []}},
        "rules": [
            {"type": "pull_request", "parameters": {
                "required_approving_review_count": 1, "dismiss_stale_reviews_on_push": True,
                "require_code_owner_review": True, "require_last_push_approval": True,
                "required_review_thread_resolution": True,
                "allowed_merge_methods": ["merge"]}},
            {"type": "required_status_checks", "parameters": {
                "strict_required_status_checks_policy": True,
                "required_status_checks": [{
                    "context": "CI / test-and-verify", "integration_id": 15368}]}},
            {"type": "deletion"}, {"type": "non_fast_forward"},
        ],
    }


def test_governance_snapshot_semantics_are_derived_from_pinned_provider_shape():
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
        (
            lambda raw: raw.__setitem__("current_user_can_bypass", "always"),
            "CURRENT_USER_BYPASS",
        ),
        (
            lambda raw: raw.__setitem__("current_user_can_bypass", "pull_requests_only"),
            "CURRENT_USER_BYPASS",
        ),
        (
            lambda raw: raw.__setitem__("current_user_can_bypass", "exempt"),
            "CURRENT_USER_BYPASS",
        ),
        (
            lambda raw: raw.__setitem__("current_user_can_bypass", False),
            "CURRENT_USER_BYPASS",
        ),
        (
            lambda raw: raw.__setitem__("current_user_can_bypass", True),
            "CURRENT_USER_BYPASS",
        ),
        (lambda raw: raw.pop("current_user_can_bypass"), "CURRENT_USER_BYPASS"),
        (lambda raw: raw.__setitem__("node_id", "not-a-provider-node"), "NODE_ID"),
        (
            lambda raw: raw["_links"]["self"].__setitem__(
                "href", "https://example.invalid/forged"
            ),
            "PROVIDER_LINKS",
        ),
        (
            lambda raw: raw["conditions"]["ref_name"].__setitem__(
                "exclude", ["refs/heads/*"]
            ),
            "MAIN_TARGET",
        ),
        (
            lambda raw: raw["conditions"]["ref_name"].__setitem__(
                "include", ["refs/heads/main"]
            ),
            "MAIN_TARGET",
        ),
        (
            lambda raw: raw["conditions"]["ref_name"].__setitem__(
                "include", ["~DEFAULT_BRANCH", "refs/heads/b00r-ruleset-canary"]
            ),
            "MAIN_TARGET",
        ),
        (
            lambda raw: raw["conditions"]["ref_name"].__setitem__(
                "include", [{"malformed": True}]
            ),
            "MAIN_TARGET",
        ),
        (
            lambda raw: raw["rules"][1]["parameters"]["required_status_checks"][0].pop(
                "integration_id"
            ),
            "STATUS_CONTROL",
        ),
        (
            lambda raw: raw["rules"][1]["parameters"]["required_status_checks"][0].__setitem__(
                "integration_id", 42
            ),
            "STATUS_CONTROL",
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


def test_provider_negative_canary_is_mandatory_and_bound_to_ruleset(tmp_path):
    raw_path = tmp_path / "raw.json"
    raw_path.write_bytes(canonical_json({
        "id": 42,
        "name": "main",
        "node_id": "RRS_provider42",
        "updated_at": "1970-01-01T00:00:10Z",
        "conditions": {"ref_name": {"include": [
            "refs/heads/main", "refs/heads/b00r-ruleset-canary"
        ], "exclude": []}},
    }))
    transcript_rel = "evidence/B00R_G2/provider_negative_canary.transcript.txt"
    transcript = (
        b"TRIAD_CANARY_REF=refs/heads/b00r-ruleset-canary\n"
        b"TRIAD_CANARY_BEFORE_SHA=" + b"a" * 40 + b"\n"
        b"TRIAD_CANARY_AFTER_SHA=" + b"b" * 40 + b"\n"
        b"TRIAD_CANARY_ACTOR=canary-pusher\n"
        b"TRIAD_CANARY_EXIT_CODE=1\n"
        b"git push --porcelain origin " + b"b" * 40
        + b":refs/heads/b00r-ruleset-canary\n"
        b"remote: error: GH013: Repository rule violations found for "
        b"refs/heads/b00r-ruleset-canary.\n"
        b" ! [remote rejected] canary -> b00r-ruleset-canary "
        b"(push declined due to repository rule violations)\n"
    )
    transcript_path = tmp_path / transcript_rel
    transcript_path.parent.mkdir(parents=True)
    transcript_path.write_bytes(transcript)
    rule_suite_rel = "evidence/B00R_G2/provider_negative_canary.rule_suite.raw.json"
    rule_suite = {
        "id": 99,
        "actor_id": 7,
        "actor_name": "canary-pusher",
        "before_sha": "a" * 40,
        "after_sha": "b" * 40,
        "ref": "refs/heads/b00r-ruleset-canary",
        "repository_id": 1_327_825_324,
        "repository_name": "TriadOrigin",
        "pushed_at": "1970-01-01T00:00:15Z",
        "result": "fail",
        "evaluation_result": None,
        "rule_evaluations": [{
            "rule_source": {"type": "ruleset", "id": 42, "name": "main"},
            "enforcement": "active",
            "result": "fail",
            "rule_type": "pull_request",
            "details": "Changes must be made through a pull request.",
        }],
    }
    rule_suite_path = tmp_path / rule_suite_rel
    rule_suite_path.write_bytes(canonical_json(rule_suite))
    canary = {
        "profile": "TRIAD-B00R-PROVIDER-NEGATIVE-CANARY-V1",
        "canary_kind": "PROVIDER_NEGATIVE_CANARY",
        "provider": "github",
        "repository": "TriadAgentic/TriadOrigin",
        "repository_id": 1_327_825_324,
        "ruleset_id": 42,
        "ref": "refs/heads/b00r-ruleset-canary",
        "operation": "DIRECT_PUSH",
        "result": "REJECTED_BY_RULESET",
        "exit_code": 1,
        "attempted_at_us": 20_000_000,
        "actor_id": 7,
        "actor_name": "canary-pusher",
        "before_sha": "a" * 40,
        "after_sha": "b" * 40,
        "rule_suite_id": 99,
        "rule_suite_path": rule_suite_rel,
        "rule_suite_sha256": sha256_hex(rule_suite_path.read_bytes()),
        "transcript_path": transcript_rel,
        "transcript_sha256": sha256_hex(transcript),
    }
    canary_path = tmp_path / "evidence/B00R_G2/provider_negative_canary.v1.json"
    canary_path.write_bytes(canonical_json(canary))
    entries = [
        {"path": canary_path.relative_to(tmp_path).as_posix(),
         "role": "PROVIDER_NEGATIVE_CANARY", "role_unique": True,
         "sha256": sha256_hex(canary_path.read_bytes())},
        {"path": transcript_rel, "role": "PROVIDER_NEGATIVE_CANARY_TRANSCRIPT",
         "role_unique": True, "sha256": sha256_hex(transcript)},
        {"path": rule_suite_rel, "role": "PROVIDER_NEGATIVE_CANARY_RULE_SUITE",
         "role_unique": True, "sha256": sha256_hex(rule_suite_path.read_bytes())},
    ]
    _validate_provider_negative_canary(
        entries=entries, root=tmp_path, provider_raw_path=raw_path,
        provider_merge_time_us=30_000_000,
    )
    same_second_raw = json.loads(raw_path.read_bytes())
    same_second_raw["updated_at"] = "1970-01-01T00:00:15Z"
    raw_path.write_bytes(canonical_json(same_second_raw))
    with pytest.raises(ReceiptBindingError, match="CHRONOLOGY_INVALID"):
        _validate_provider_negative_canary(
            entries=entries, root=tmp_path, provider_raw_path=raw_path,
            provider_merge_time_us=30_000_000,
        )
    same_second_raw["updated_at"] = "1970-01-01T00:00:10Z"
    raw_path.write_bytes(canonical_json(same_second_raw))
    with pytest.raises(ReceiptBindingError, match="ROLE_COUNT"):
        _validate_provider_negative_canary(
            entries=entries[1:], root=tmp_path, provider_raw_path=raw_path,
            provider_merge_time_us=30_000_000,
        )
    canary["ruleset_id"] = 99
    canary_path.write_bytes(canonical_json(canary))
    with pytest.raises(ReceiptBindingError, match="RULESET_IDENTITY"):
        _validate_provider_negative_canary(
            entries=entries, root=tmp_path, provider_raw_path=raw_path,
            provider_merge_time_us=30_000_000,
        )

    def write_suite(document):
        rule_suite_path.write_bytes(canonical_json(document))
        digest = sha256_hex(rule_suite_path.read_bytes())
        canary["rule_suite_sha256"] = digest
        canary_path.write_bytes(canonical_json(canary))
        entries[2]["sha256"] = digest

    canary["ruleset_id"] = 42
    rule_suite["result"] = "pass"
    rule_suite["evaluation_result"] = "fail"
    write_suite(rule_suite)
    with pytest.raises(ReceiptBindingError, match="RULE_SUITE_IDENTITY"):
        _validate_provider_negative_canary(
            entries=entries, root=tmp_path, provider_raw_path=raw_path,
            provider_merge_time_us=30_000_000,
        )

    rule_suite["result"] = "fail"
    rule_suite["evaluation_result"] = None
    rule_suite["rule_evaluations"][0]["rule_source"]["id"] = 999
    write_suite(rule_suite)
    with pytest.raises(ReceiptBindingError, match="ACTIVE_RULESET_FAILURE_ABSENT"):
        _validate_provider_negative_canary(
            entries=entries, root=tmp_path, provider_raw_path=raw_path,
            provider_merge_time_us=30_000_000,
        )

    rule_suite["rule_evaluations"][0]["rule_source"]["id"] = 42
    write_suite(rule_suite)
    wrong_failure = transcript + b"fatal: Authentication failed for repository\n"
    transcript_path.write_bytes(wrong_failure)
    canary["transcript_sha256"] = sha256_hex(wrong_failure)
    canary_path.write_bytes(canonical_json(canary))
    entries[1]["sha256"] = sha256_hex(wrong_failure)
    with pytest.raises(ReceiptBindingError, match="WRONG_FAILURE_CLASS"):
        _validate_provider_negative_canary(
            entries=entries, root=tmp_path, provider_raw_path=raw_path,
            provider_merge_time_us=30_000_000,
        )


def test_source_pr_provider_record_binds_merge_time_before_receipt_observation(tmp_path):
    rel = "evidence/B00R_G2/source_pr.provider.raw.json"
    path = tmp_path / rel
    path.parent.mkdir(parents=True)
    payload = {
        "source_pr": 28,
        "source_merge_sha": "a" * 40,
        "source_merge_time_us": 20_000_000,
        "final_source_head": "b" * 40,
        "observed_at_us": 30_000_000,
        "emitted_at_us": 31_000_000,
    }
    record = {
        "number": 28,
        "state": "closed",
        "merged": True,
        "merged_at": "1970-01-01T00:00:20Z",
        "merge_commit_sha": "a" * 40,
        "base": {"ref": "main", "repo": {
            "id": 1_327_825_324, "full_name": "TriadAgentic/TriadOrigin"}},
        "head": {"sha": "b" * 40,
                 "repo": {"id": 1_327_825_324,
                          "full_name": "TriadAgentic/TriadOrigin"}},
        "user": {"login": "source-author", "type": "User"},
    }
    path.write_bytes(canonical_json(record))
    entries = [{
        "path": rel, "role": "SOURCE_PR_PROVIDER_RECORD", "role_unique": True,
        "sha256": sha256_hex(path.read_bytes()),
    }]
    assert _validate_source_pr_provider_record(
        entries=entries, root=tmp_path, payload=payload, now_us=40_000_000,
        github_token=None, require_live_provider=False,
    ) == 20_000_000
    record["head"]["repo"]["id"] = 99
    path.write_bytes(canonical_json(record))
    entries[0]["sha256"] = sha256_hex(path.read_bytes())
    with pytest.raises(ReceiptBindingError, match="PROVIDER_IDENTITY_MISMATCH"):
        _validate_source_pr_provider_record(
            entries=entries, root=tmp_path, payload=payload, now_us=40_000_000,
            github_token=None, require_live_provider=False,
        )
    record["head"]["repo"]["id"] = 1_327_825_324
    record["merged_at"] = "1970-01-01T00:00:21Z"
    path.write_bytes(canonical_json(record))
    entries[0]["sha256"] = sha256_hex(path.read_bytes())
    with pytest.raises(ReceiptBindingError, match="PROVIDER_PAYLOAD_TIME_MISMATCH"):
        _validate_source_pr_provider_record(
            entries=entries, root=tmp_path, payload=payload, now_us=40_000_000,
            github_token=None, require_live_provider=False,
        )
    record["merged_at"] = "1970-01-01T00:00:30Z"
    payload["source_merge_time_us"] = 30_000_000
    path.write_bytes(canonical_json(record))
    entries[0]["sha256"] = sha256_hex(path.read_bytes())
    with pytest.raises(ReceiptBindingError, match="RECEIPT_CHRONOLOGY_INVALID"):
        _validate_source_pr_provider_record(
            entries=entries, root=tmp_path, payload=payload, now_us=40_000_000,
            github_token=None, require_live_provider=False,
        )


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


def _git_at(root: pathlib.Path, instant: str, *args: str) -> str:
    env = dict(os.environ)
    env["GIT_AUTHOR_DATE"] = instant
    env["GIT_COMMITTER_DATE"] = instant
    proc = subprocess.run(
        ["git", "-C", str(root), *args], check=True,
        capture_output=True, text=True, env=env)
    return proc.stdout.strip()


def _provider_time(root: pathlib.Path, commit: str) -> str:
    seconds = int(_git(root, "show", "-s", "--format=%ct", commit))
    return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_receipt_binding_rejects_unlisted_tracked_milestone_evidence(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "test")
    codeowners = repo / ".github/CODEOWNERS"
    codeowners.parent.mkdir(parents=True)
    codeowners.write_text("\n".join(
        f"{pattern} @TriadAgentic/origin-governance-reviewers"
        for pattern in CRITICAL_PATTERNS))
    (repo / "base.txt").write_text("base")
    _git(repo, "add", ".")
    _git_at(repo, "1970-01-01T00:00:01Z", "commit", "-m", "audited start")
    audited_start = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-b", "codeowners-bootstrap")
    codeowners.write_text("\n".join(
        f"{pattern} @djordi10" for pattern in CRITICAL_PATTERNS))
    _git(repo, "add", ".github/CODEOWNERS")
    _git_at(repo, "1970-01-01T00:00:05Z", "commit", "-m", "bootstrap codeowner")
    bootstrap_head = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "main")
    _git_at(
        repo, "1970-01-01T00:00:10Z", "merge", "--no-ff", "codeowners-bootstrap",
        "-m", "merge codeowners bootstrap")
    bootstrap_merge = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-b", "generation-2-source")
    (repo / "source.txt").write_text("source")
    governance_dir = repo / "docs/governance/rulesets"
    governance_dir.mkdir(parents=True)
    snapshot_path = governance_dir / "main.ruleset.provider.json"
    provider_raw_path = governance_dir / "main.ruleset.provider.raw.json"
    snapshot_path.write_bytes(b"source snapshot")
    provider_raw_path.write_bytes(canonical_json({
        "id": 42,
        "name": "main",
        "node_id": "RRS_provider42",
        "updated_at": "1970-01-01T00:00:10Z",
        "conditions": {"ref_name": {"include": [
            "refs/heads/main", "refs/heads/b00r-ruleset-canary"
        ], "exclude": []}},
    }))
    _git(repo, "add", ".")
    _git_at(repo, "1970-01-01T00:00:25Z", "commit", "-m", "corrective source head")
    final_source = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "main")
    _git_at(
        repo, "1970-01-01T00:00:30Z", "merge", "--no-ff", "generation-2-source",
        "-m", "merge corrective source")
    source = _git(repo, "rev-parse", "HEAD")
    source_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    source_time = int(_git(repo, "show", "-s", "--format=%ct", "HEAD")) * 1_000_000

    roles = ["WORKFLOW", "CONTRACT_MANIFEST", "TEST_MANIFEST", "CONFIG_BUNDLE",
             "ROLLBACK_PROOF"]
    entries = []
    for i, role in enumerate(roles):
        rel = f"evidence/B00R_G2/{i}-{role.lower()}.json"
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        data = canonical_json({"role": role})
        path.write_bytes(data)
        entries.append({"path": rel, "role": role, "media_type": "application/json",
                        "size": len(data), "sha256": sha256_hex(data)})
    transcript_rel = "evidence/B00R_G2/provider_negative_canary.transcript.txt"
    transcript = (
        b"TRIAD_CANARY_REF=refs/heads/b00r-ruleset-canary\n"
        b"TRIAD_CANARY_BEFORE_SHA=" + b"a" * 40 + b"\n"
        b"TRIAD_CANARY_AFTER_SHA=" + b"b" * 40 + b"\n"
        b"TRIAD_CANARY_ACTOR=canary-pusher\n"
        b"TRIAD_CANARY_EXIT_CODE=1\n"
        b"git push --porcelain origin " + b"b" * 40
        + b":refs/heads/b00r-ruleset-canary\n"
        b"remote: error: GH013: Repository rule violations found for "
        b"refs/heads/b00r-ruleset-canary.\n"
        b" ! [remote rejected] canary -> b00r-ruleset-canary "
        b"(push declined due to repository rule violations)\n"
    )
    transcript_path = repo / transcript_rel
    transcript_path.write_bytes(transcript)
    entries.append({
        "path": transcript_rel,
        "role": "PROVIDER_NEGATIVE_CANARY_TRANSCRIPT",
        "role_unique": True,
        "media_type": "application/octet-stream",
        "size": len(transcript),
        "sha256": sha256_hex(transcript),
    })
    rule_suite_rel = "evidence/B00R_G2/provider_negative_canary.rule_suite.raw.json"
    rule_suite = canonical_json({
        "id": 99,
        "actor_id": 7,
        "actor_name": "canary-pusher",
        "before_sha": "a" * 40,
        "after_sha": "b" * 40,
        "ref": "refs/heads/b00r-ruleset-canary",
        "repository_id": 1_327_825_324,
        "repository_name": "TriadOrigin",
        "pushed_at": "1970-01-01T00:00:15Z",
        "result": "fail",
        "evaluation_result": None,
        "rule_evaluations": [{
            "rule_source": {"type": "ruleset", "id": 42, "name": "main"},
            "enforcement": "active",
            "result": "fail",
            "rule_type": "pull_request",
        }],
    })
    (repo / rule_suite_rel).write_bytes(rule_suite)
    entries.append({
        "path": rule_suite_rel,
        "role": "PROVIDER_NEGATIVE_CANARY_RULE_SUITE",
        "role_unique": True,
        "media_type": "application/json",
        "size": len(rule_suite),
        "sha256": sha256_hex(rule_suite),
    })
    canary_rel = "evidence/B00R_G2/provider_negative_canary.v1.json"
    canary = canonical_json({
        "profile": "TRIAD-B00R-PROVIDER-NEGATIVE-CANARY-V1",
        "canary_kind": "PROVIDER_NEGATIVE_CANARY",
        "provider": "github",
        "repository": "TriadAgentic/TriadOrigin",
        "repository_id": 1_327_825_324,
        "ruleset_id": 42,
        "ref": "refs/heads/b00r-ruleset-canary",
        "operation": "DIRECT_PUSH",
        "result": "REJECTED_BY_RULESET",
        "exit_code": 1,
        "attempted_at_us": 20_000_000,
        "actor_id": 7,
        "actor_name": "canary-pusher",
        "before_sha": "a" * 40,
        "after_sha": "b" * 40,
        "rule_suite_id": 99,
        "rule_suite_path": rule_suite_rel,
        "rule_suite_sha256": sha256_hex(rule_suite),
        "transcript_path": transcript_rel,
        "transcript_sha256": sha256_hex(transcript),
    })
    (repo / canary_rel).write_bytes(canary)
    entries.append({
        "path": canary_rel,
        "role": "PROVIDER_NEGATIVE_CANARY",
        "role_unique": True,
        "media_type": "application/json",
        "size": len(canary),
        "sha256": sha256_hex(canary),
    })
    source_pr_rel = "evidence/B00R_G2/source_pr.provider.raw.json"
    source_pr_record = canonical_json({
        "number": 1,
        "state": "closed",
        "merged": True,
        "merged_at": _provider_time(repo, source),
        "merge_commit_sha": source,
        "base": {
            "ref": "main",
            "repo": {"id": 1_327_825_324,
                     "full_name": "TriadAgentic/TriadOrigin"},
            },
            "head": {"sha": final_source,
                     "repo": {"id": 1_327_825_324,
                              "full_name": "TriadAgentic/TriadOrigin"}},
        "user": {"login": "source-author", "type": "User"},
    })
    (repo / source_pr_rel).write_bytes(source_pr_record)
    entries.append({
        "path": source_pr_rel,
        "role": "SOURCE_PR_PROVIDER_RECORD",
        "role_unique": True,
        "media_type": "application/json",
        "size": len(source_pr_record),
        "sha256": sha256_hex(source_pr_record),
    })
    review_rel = "evidence/B00R_G2/source_pr.approved_review.provider.raw.json"
    review_record = canonical_json({
        "source_pr": 1,
        "source_head": final_source,
        "review": {
            "id": 2,
            "state": "APPROVED",
            "commit_id": final_source,
            "submitted_at": "1970-01-01T00:00:25Z",
            "user": {"login": "djordi10", "type": "User"},
        },
    })
    (repo / review_rel).write_bytes(review_record)
    entries.append({
        "path": review_rel,
        "role": "SOURCE_PR_APPROVED_REVIEW_PROVIDER_RECORD",
        "role_unique": True,
        "media_type": "application/json",
        "size": len(review_record),
        "sha256": sha256_hex(review_record),
    })
    bootstrap_pr_rel = "evidence/B00R_G2/codeowners_bootstrap_pr.provider.raw.json"
    bootstrap_pr_record = canonical_json({
        "number": 10,
        "state": "closed",
        "merged": True,
        "merged_at": _provider_time(repo, bootstrap_merge),
        "merge_commit_sha": bootstrap_merge,
        "base": {
            "ref": "main",
            "repo": {"id": 1_327_825_324,
                     "full_name": "TriadAgentic/TriadOrigin"},
        },
        "head": {
            "sha": bootstrap_head,
            "repo": {"id": 1_327_825_324,
                     "full_name": "TriadAgentic/TriadOrigin"},
        },
        "user": {"login": "bootstrap-author", "type": "User"},
    })
    (repo / bootstrap_pr_rel).write_bytes(bootstrap_pr_record)
    entries.append({
        "path": bootstrap_pr_rel,
        "role": "CODEOWNERS_BOOTSTRAP_PR_PROVIDER_RECORD",
        "role_unique": True,
        "media_type": "application/json",
        "size": len(bootstrap_pr_record),
        "sha256": sha256_hex(bootstrap_pr_record),
    })
    bootstrap_review_rel = (
        "evidence/B00R_G2/codeowners_bootstrap_pr.approved_review.provider.raw.json")
    bootstrap_review_record = canonical_json({
        "source_pr": 10,
        "source_head": bootstrap_head,
        "review": {
            "id": 11,
            "state": "APPROVED",
            "commit_id": bootstrap_head,
            "submitted_at": "1970-01-01T00:00:09Z",
            "user": {"login": "djordi10", "type": "User"},
        },
    })
    (repo / bootstrap_review_rel).write_bytes(bootstrap_review_record)
    entries.append({
        "path": bootstrap_review_rel,
        "role": "CODEOWNERS_BOOTSTRAP_APPROVED_REVIEW_PROVIDER_RECORD",
        "role_unique": True,
        "media_type": "application/json",
        "size": len(bootstrap_review_record),
        "sha256": sha256_hex(bootstrap_review_record),
    })
    entries.sort(key=lambda item: item["path"])
    manifest = {"schema": "triad.evidence_manifest.v1", "schema_version": "1.0.0",
                "manifest_kind": "EVIDENCE_MANIFEST", "entry_count": len(entries),
                "entries": entries}
    manifest_path = repo / "evidence/B00R_G2/evidence_manifest.json"
    manifest_path.write_bytes(canonical_json(manifest))
    by_role = {entry["role"]: entry["sha256"] for entry in entries}
    receipt = json.loads(
        (ROOT / "contracts/golden/triad.evidence_receipt.v3/valid.json").read_text())
    payload = receipt["payload"]
    payload.update({
        "source_pr": 1,
        "repair_generation": 2,
        "observed_at_us": 40_000_000,
        "emitted_at_us": 50_000_000,
        "expires_at_us": 60_000_000,
        "source_merge_sha": source, "source_merge_tree": source_tree,
        "final_source_head": final_source, "source_merge_time_us": source_time,
        "audited_start_sha": audited_start, "repair_decision_sha256": "d" * 64,
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
    receipt_path = repo / "evidence/receipts/B00R.g2.receipt.v3.json"
    receipt_path.parent.mkdir(parents=True)
    receipt_path.write_bytes(canonical_json(receipt))
    _git(repo, "checkout", "-b", "generation-2-receipt")
    _git(repo, "add", "evidence")
    _git_at(repo, "1970-01-01T00:00:40Z", "commit", "-m", "receipt")
    receipt_head = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "main")
    _git_at(
        repo, "1970-01-01T00:00:50Z", "merge", "--no-ff", "generation-2-receipt",
        "-m", "merge receipt")
    head = _git(repo, "rev-parse", "HEAD")
    authority = AuthorityContext(
        trust={}, decisions={"b00_repair": {"effective_at_us": 1, "subject_sha256s": {
            "generation_ledger": "e" * 64, "audited_start_sha": audited_start}}},
        digests={"b00_repair": "d" * 64}, receipt_threshold=2,
        receipt_roles=("EVIDENCE_PRODUCER", "INDEPENDENT_COUNTERSIGNER"),
        receipt_algorithm="ed25519")
    validate_receipt_bindings(
        receipt, receipt_path=receipt_path, manifest_path=manifest_path, git_root=repo,
        expected_head=head, authority=authority,
        governance_evidence_paths=(snapshot_path, provider_raw_path),
        require_live_source_pr=False)

    monkeypatch.setattr(
        "tools.validate_b_receipt.fetch_and_verify_receipt_merge",
        lambda *_args, **_kwargs: SimpleNamespace(
            head_sha=receipt_head, merged_at_us=50_000_000))
    validate_receipt_bindings(
        receipt, receipt_path=receipt_path, manifest_path=manifest_path, git_root=repo,
        expected_head=head, authority=authority,
        governance_evidence_paths=(snapshot_path, provider_raw_path),
        now_us=60_000_000, github_token="token",
        require_live_source_pr=False, receipt_pr=35, require_live_receipt_pr=True)

    monkeypatch.setattr(
        "tools.validate_b_receipt.fetch_and_verify_receipt_merge",
        lambda *_args, **_kwargs: SimpleNamespace(
            head_sha=source, merged_at_us=50_000_000))
    with pytest.raises(ReceiptBindingError, match="RECEIPT_MERGE_NOT_EXACT_TWO_PARENT"):
        validate_receipt_bindings(
            receipt, receipt_path=receipt_path, manifest_path=manifest_path, git_root=repo,
            expected_head=head, authority=authority,
            governance_evidence_paths=(snapshot_path, provider_raw_path),
            now_us=60_000_000, github_token="token",
            require_live_source_pr=False, receipt_pr=35,
            require_live_receipt_pr=True)

    original_bootstrap_pr = bootstrap_pr_record
    original_bootstrap_review = bootstrap_review_record

    def replace_entry(path: str, role: str, data: bytes) -> None:
        (repo / path).write_bytes(data)
        entry = next(item for item in entries if item["role"] == role)
        entry["sha256"] = sha256_hex(data)
        entry["size"] = len(data)

    direct_commit_pr = json.loads(original_bootstrap_pr)
    direct_commit_pr["merge_commit_sha"] = bootstrap_head
    direct_commit_pr["merged_at"] = _provider_time(repo, bootstrap_head)
    direct_commit_pr_bytes = canonical_json(direct_commit_pr)
    replace_entry(
        bootstrap_pr_rel, "CODEOWNERS_BOOTSTRAP_PR_PROVIDER_RECORD",
        direct_commit_pr_bytes)
    with pytest.raises(ReceiptBindingError, match="NOT_EXACT_TWO_PARENT_PR_MERGE"):
        _validate_codeowners_bootstrap(
            entries=entries, root=repo, payload=payload,
            source_base_parent=bootstrap_head,
            source_provider_merge_time_us=source_time,
            now_us=None, github_token=None, require_live_provider=False)
    replace_entry(
        bootstrap_pr_rel, "CODEOWNERS_BOOTSTRAP_PR_PROVIDER_RECORD",
        original_bootstrap_pr)

    _git(repo, "checkout", "-b", "bootstrap-extra-head", audited_start)
    codeowners.write_text("\n".join(
        f"{pattern} @djordi10" for pattern in CRITICAL_PATTERNS))
    (repo / "extra.txt").write_text("scope expansion\n")
    _git(repo, "add", ".")
    _git_at(repo, "1970-01-01T00:00:06Z", "commit", "-m", "unsafe bootstrap head")
    extra_head = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-b", "bootstrap-extra-base", audited_start)
    _git_at(
        repo, "1970-01-01T00:00:12Z", "merge", "--no-ff", "bootstrap-extra-head",
        "-m", "merge unsafe bootstrap")
    extra_merge = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "main")
    extra_pr = json.loads(original_bootstrap_pr)
    extra_pr.update({
        "number": 12,
        "merged_at": _provider_time(repo, extra_merge),
        "merge_commit_sha": extra_merge,
    })
    extra_pr["head"]["sha"] = extra_head
    extra_review = json.loads(original_bootstrap_review)
    extra_review.update({"source_pr": 12, "source_head": extra_head})
    extra_review["review"].update({
        "commit_id": extra_head,
        "submitted_at": "1970-01-01T00:00:11Z",
    })
    replace_entry(
        bootstrap_pr_rel, "CODEOWNERS_BOOTSTRAP_PR_PROVIDER_RECORD",
        canonical_json(extra_pr))
    replace_entry(
        bootstrap_review_rel, "CODEOWNERS_BOOTSTRAP_APPROVED_REVIEW_PROVIDER_RECORD",
        canonical_json(extra_review))
    with pytest.raises(ReceiptBindingError, match="DIFF_NOT_EXACT"):
        _validate_codeowners_bootstrap(
            entries=entries, root=repo, payload=payload,
            source_base_parent=extra_merge,
            source_provider_merge_time_us=source_time,
            now_us=None, github_token=None, require_live_provider=False)
    replace_entry(
        bootstrap_pr_rel, "CODEOWNERS_BOOTSTRAP_PR_PROVIDER_RECORD",
        original_bootstrap_pr)
    replace_entry(
        bootstrap_review_rel, "CODEOWNERS_BOOTSTRAP_APPROVED_REVIEW_PROVIDER_RECORD",
        original_bootstrap_review)

    stale_review = json.loads(original_bootstrap_review)
    stale_review["review"]["commit_id"] = audited_start
    replace_entry(
        bootstrap_review_rel, "CODEOWNERS_BOOTSTRAP_APPROVED_REVIEW_PROVIDER_RECORD",
        canonical_json(stale_review))
    with pytest.raises(ReceiptBindingError, match="REVIEW_IDENTITY_MISMATCH"):
        _validate_codeowners_bootstrap(
            entries=entries, root=repo, payload=payload,
            source_base_parent=bootstrap_merge,
            source_provider_merge_time_us=source_time,
            now_us=None, github_token=None, require_live_provider=False)
    replace_entry(
        bootstrap_review_rel, "CODEOWNERS_BOOTSTRAP_APPROVED_REVIEW_PROVIDER_RECORD",
        original_bootstrap_review)

    self_review_pr = json.loads(original_bootstrap_pr)
    self_review_pr["user"]["login"] = "djordi10"
    replace_entry(
        bootstrap_pr_rel, "CODEOWNERS_BOOTSTRAP_PR_PROVIDER_RECORD",
        canonical_json(self_review_pr))
    with pytest.raises(ReceiptBindingError, match="REVIEW_NOT_INDEPENDENT"):
        _validate_codeowners_bootstrap(
            entries=entries, root=repo, payload=payload,
            source_base_parent=bootstrap_merge,
            source_provider_merge_time_us=source_time,
            now_us=None, github_token=None, require_live_provider=False)
    replace_entry(
        bootstrap_pr_rel, "CODEOWNERS_BOOTSTRAP_PR_PROVIDER_RECORD",
        original_bootstrap_pr)

    post_merge_review = json.loads(original_bootstrap_review)
    post_merge_review["review"]["submitted_at"] = _provider_time(repo, bootstrap_merge)
    replace_entry(
        bootstrap_review_rel, "CODEOWNERS_BOOTSTRAP_APPROVED_REVIEW_PROVIDER_RECORD",
        canonical_json(post_merge_review))
    with pytest.raises(ReceiptBindingError, match="REVIEW_NOT_BEFORE_MERGE"):
        _validate_codeowners_bootstrap(
            entries=entries, root=repo, payload=payload,
            source_base_parent=bootstrap_merge,
            source_provider_merge_time_us=source_time,
            now_us=None, github_token=None, require_live_provider=False)
    replace_entry(
        bootstrap_review_rel, "CODEOWNERS_BOOTSTRAP_APPROVED_REVIEW_PROVIDER_RECORD",
        original_bootstrap_review)

    drifted_time = json.loads(original_bootstrap_pr)
    drifted_time["merged_at"] = "1970-01-01T00:00:11Z"
    replace_entry(
        bootstrap_pr_rel, "CODEOWNERS_BOOTSTRAP_PR_PROVIDER_RECORD",
        canonical_json(drifted_time))
    with pytest.raises(ReceiptBindingError, match="PROVIDER_GIT_TIME_MISMATCH"):
        _validate_codeowners_bootstrap(
            entries=entries, root=repo, payload=payload,
            source_base_parent=bootstrap_merge,
            source_provider_merge_time_us=source_time,
            now_us=None, github_token=None, require_live_provider=False)
    replace_entry(
        bootstrap_pr_rel, "CODEOWNERS_BOOTSTRAP_PR_PROVIDER_RECORD",
        original_bootstrap_pr)

    alternate_manifest = repo / "evidence/B00R_G2/alternate_manifest.json"
    alternate_manifest.write_bytes(manifest_path.read_bytes())
    _git(repo, "add", alternate_manifest.relative_to(repo).as_posix())
    _git(repo, "commit", "-m", "alternate manifest attack")
    with pytest.raises(ReceiptBindingError, match="MANIFEST_PATH_NONCANONICAL"):
        validate_receipt_bindings(
            receipt, receipt_path=receipt_path, manifest_path=alternate_manifest, git_root=repo,
            expected_head=_git(repo, "rev-parse", "HEAD"), authority=authority,
            governance_evidence_paths=(snapshot_path, provider_raw_path),
            require_live_source_pr=False)
    alternate_manifest.unlink()
    _git(repo, "add", "-u")
    _git(repo, "commit", "-m", "remove alternate manifest attack")

    extra = repo / "evidence/B00R_G2/unlisted.json"
    extra.write_text("{}")
    _git(repo, "add", extra.relative_to(repo).as_posix())
    _git(repo, "commit", "-m", "unlisted")
    with pytest.raises(ReceiptBindingError, match="NAMESPACE_NOT_CLOSED"):
        validate_receipt_bindings(
            receipt, receipt_path=receipt_path, manifest_path=manifest_path, git_root=repo,
            expected_head=_git(repo, "rev-parse", "HEAD"), authority=authority,
            governance_evidence_paths=(snapshot_path, provider_raw_path),
            require_live_source_pr=False)
