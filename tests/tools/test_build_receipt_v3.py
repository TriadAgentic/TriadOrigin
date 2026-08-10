"""Core differential proof for tools/build_receipt_v3.py against the frozen runner.

The deliverable's core proof: a complete fixture receipt built by the tool, self-checked to
zero issues, is then judged by the FROZEN runner's ``receipt_issues`` with matching pins — and
the ONLY complaints are the missing-signature/DSSE ones; every non-DSSE clause is clean.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import importlib.util
import inspect
import json
import pathlib
import time
import types
from typing import Any

import pytest

TOOL1 = "build_profile_decision.py"
TOOL2 = "build_trust_registry.py"
TOOL3 = "build_receipt_v3.py"

# The exact, ordered complaint list the frozen runner emits for a valid-but-unsigned draft
# (signatures == []).  Every entry is a missing-signature/DSSE clause; nothing else may appear.
EXPECTED_UNSIGNED_ISSUES = [
    "DSSE requires producer and independent countersigner signatures",
    "receipt lacks two distinct independently verified signer identities",
    "receipt lacks verified producer and countersigner roles",
    "receipt builder is not an independently verified signer identity",
    "receipt reviewer is not an independently verified signer identity",
]


class Fixture(types.SimpleNamespace):
    pass


def build_fixture(
    tmp_path: pathlib.Path,
    run_tool,
    registry_spec_factory,
    milestone: str = "B05",
) -> Fixture:
    """A complete draft-receipt fixture: preimages, registry + pins, config — all in tmp."""
    now_us = int(time.time() * 1_000_000)
    repo = tmp_path / "evrepo"
    repo.mkdir()

    profile_path = repo / "profile_decision.json"
    proc = run_tool(TOOL1, "--out", str(profile_path))
    assert proc.returncode == 0, proc.stderr
    profile_sha = proc.stdout.strip()

    roles = (
        ("receipt_profile_decision_sha256", "RECEIPT_PROFILE_DECISION"),
        ("artifact_sha256", "ARTIFACT"),
        ("config_bundle_sha256", "CONFIGURATION"),
        ("contract_bundle_sha256", "CONTRACT_BUNDLE"),
        ("binding_bundle_sha256", "BINDING_BUNDLE"),
        ("test_collection_sha256", "TEST_COLLECTION"),
        ("evidence_manifest_sha256", "EVIDENCE_MANIFEST"),
        ("rollback_proof_sha256", "ROLLBACK_PROOF"),
    )
    role_paths: dict[str, str] = {"RECEIPT_PROFILE_DECISION": "profile_decision.json"}
    for _field, role in roles[1:]:
        name = f"fixture_{role.lower()}.txt"
        (repo / name).write_text(f"immutable {role} fixture evidence\n", encoding="utf-8")
        role_paths[role] = name

    registry_path = tmp_path / "registry.json"
    spec_path = tmp_path / "registry_spec.json"
    spec_path.write_text(json.dumps(registry_spec_factory(now_us)), encoding="utf-8")
    proc = run_tool(TOOL2, "--spec", str(spec_path), "--out", str(registry_path))
    assert proc.returncode == 0, proc.stderr
    registry_sha = proc.stdout.strip()

    source_head_sha = "9" * 40
    evidence = [
        {
            "evidence_id": f"ev-{role.lower()}",
            "digest_role": role,
            "path": role_paths[role],
            "producer": "fixture-producer",
            "observed_at_us": str(now_us - 2_500_000),
            "media_type": "application/json" if role == "RECEIPT_PROFILE_DECISION" else "text/plain",
        }
        for _field, role in roles
    ]
    config: dict[str, Any] = {
        "milestone": milestone,
        "receipt_id": f"receipt-{milestone.lower()}-fixture",
        "source_pr": 1,
        "receipt_pr": 2,
        "build_commit": "a" * 40,
        "merge_commit": "a" * 40,
        "source_head_sha": source_head_sha,
        "reviewed_at_us": str(now_us - 4_000_000),
        "source_merge_at_us": str(now_us - 3_000_000),
        "observed_at_us": str(now_us - 2_000_000),
        "emitted_at_us": str(now_us - 1_000_000),
        "expires_at_us": str(now_us + 86_400_000_000),
        "builder": "builder-a",
        "reviewer": "reviewer-b",
        "predecessor": (
            None if milestone == "B01"
            else {"id": "receipt-predecessor-fixture", "sha256": "7" * 64}
        ),
        "correction_of_receipt_ids": [],
        "ci_runs": [{
            "run_id": 1,
            "head_sha": source_head_sha,
            "conclusion": "SUCCESS",
            "required_jobs_unskipped": True,
        }],
        "evidence": evidence,
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    out_path = tmp_path / "receipt.json"
    return Fixture(
        now_us=now_us, repo=repo, milestone=milestone,
        profile_sha=profile_sha, registry_path=registry_path, registry_sha=registry_sha,
        config=config, config_path=config_path,
        out_path=out_path, sidecar_path=out_path.with_suffix(".signing.json"),
    )


def rewrite_config(fx: Fixture) -> None:
    fx.config_path.write_text(json.dumps(fx.config), encoding="utf-8")


def run_build(fx: Fixture, run_tool, *extra: str):
    return run_tool(
        TOOL3,
        "--config", str(fx.config_path),
        "--repo", str(fx.repo),
        "--trust-registry-sha256", fx.registry_sha,
        "--profile-decision-sha256", fx.profile_sha,
        "--out", str(fx.out_path),
        *extra,
    )


class TestBuildAndSelfCheck:
    @pytest.mark.parametrize("milestone", ["B01", "B05", "B10"])
    def test_build_then_self_check_zero_issues(
            self, run_tool, registry_spec_factory, tmp_path, milestone) -> None:
        fx = build_fixture(tmp_path, run_tool, registry_spec_factory, milestone)
        proc = run_build(fx, run_tool, "--self-check", "--now-us", str(fx.now_us))
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "self-check issues: 0" in proc.stdout
        assert "self-check ISSUE" not in proc.stdout
        assert fx.out_path.is_file() and fx.sidecar_path.is_file()
        event = json.loads(fx.out_path.read_text(encoding="utf-8"))
        expected_kind = "TERMINAL_REPOSITORY" if milestone == "B10" else "MILESTONE_SOURCE"
        assert event["payload"]["receipt_kind"] == expected_kind
        assert event["dsse"]["signatures"] == []
        if milestone == "B01":
            assert "predecessor_receipt_id" not in event["payload"]
        else:
            assert event["payload"]["predecessor_receipt_id"] == "receipt-predecessor-fixture"

    def test_receipt_bytes_deterministic_for_a_frozen_config(
            self, run_tool, registry_spec_factory, tmp_path) -> None:
        fx = build_fixture(tmp_path, run_tool, registry_spec_factory)
        assert run_build(fx, run_tool).returncode == 0
        first = fx.out_path.read_bytes()
        assert run_build(fx, run_tool).returncode == 0
        assert fx.out_path.read_bytes() == first


class TestRunnerDifferentialCore:
    @pytest.mark.parametrize("milestone", ["B01", "B05", "B10"])
    def test_only_complaints_are_the_missing_signature_dsse_ones(
            self, run_tool, registry_spec_factory, tmp_path, frozen_runner, milestone) -> None:
        signature = inspect.signature(frozen_runner.receipt_issues)
        assert list(signature.parameters) == [
            "path", "milestone", "now", "repository_root", "trust_registry_path",
            "trust_registry_sha256", "receipt_profile_decision_sha256",
        ], "frozen runner receipt_issues signature changed; differential is void"

        fx = build_fixture(tmp_path, run_tool, registry_spec_factory, milestone)
        proc = run_build(fx, run_tool, "--self-check", "--now-us", str(fx.now_us))
        assert proc.returncode == 0, proc.stdout + proc.stderr

        now = dt.datetime.now(dt.timezone.utc)
        issues, event = frozen_runner.receipt_issues(
            fx.out_path, milestone, now,
            repository_root=fx.repo,
            trust_registry_path=fx.registry_path,
            trust_registry_sha256=fx.registry_sha,
            receipt_profile_decision_sha256=fx.profile_sha,
        )
        assert issues == EXPECTED_UNSIGNED_ISSUES, (
            "non-DSSE receipt-law complaints surfaced (every clause other than the "
            f"missing signatures must be clean): {issues}")
        for issue in issues:
            assert ("DSSE" in issue) or ("signer" in issue) or ("signature" in issue)
        assert isinstance(event, dict)
        assert event["payload"]["receipt_id"] == fx.config["receipt_id"]

    def test_tool_constants_mirror_runner_constants(
            self, tool_receipt, frozen_runner) -> None:
        assert tool_receipt.REQUIRED_RECEIPT_DIGEST_ROLES == \
            frozen_runner.REQUIRED_RECEIPT_DIGEST_ROLES
        assert tool_receipt.RECEIPT_PAYLOAD_TYPE == frozen_runner.RECEIPT_PAYLOAD_TYPE
        assert tool_receipt.MAX_RECEIPT_TTL_US == frozen_runner.MAX_RECEIPT_TTL_US
        assert tool_receipt.REPOSITORY_FUTURE_TOLERANCE_US == \
            frozen_runner.REPOSITORY_FUTURE_TOLERANCE_US
        assert tool_receipt.EXPECTED_REPOSITORY == frozen_runner.EXPECTED_REPOSITORY
        assert tool_receipt.RECEIPT_PROFILE_DECISION == \
            frozen_runner.SUPPORTED_RECEIPT_PROFILE_DECISION

    def test_runner_flags_a_tampered_draft(
            self, run_tool, registry_spec_factory, tmp_path, frozen_runner) -> None:
        """Falsification guard: the differential is not vacuously green."""
        fx = build_fixture(tmp_path, run_tool, registry_spec_factory)
        assert run_build(fx, run_tool).returncode == 0
        event = json.loads(fx.out_path.read_text(encoding="utf-8"))
        event["payload"]["unresolved_p0_p1"] = 1
        fx.out_path.write_text(json.dumps(event, sort_keys=True), encoding="utf-8")
        issues, _ = frozen_runner.receipt_issues(
            fx.out_path, "B05", dt.datetime.now(dt.timezone.utc),
            repository_root=fx.repo,
            trust_registry_path=fx.registry_path,
            trust_registry_sha256=fx.registry_sha,
            receipt_profile_decision_sha256=fx.profile_sha,
        )
        assert "receipt unresolved_p0_p1 must be integer zero" in issues


class TestPaeSidecarByteLaw:
    def test_sidecar_carries_the_exact_signing_preimages(
            self, run_tool, registry_spec_factory, tmp_path, frozen_runner) -> None:
        fx = build_fixture(tmp_path, run_tool, registry_spec_factory)
        assert run_build(fx, run_tool).returncode == 0
        event = json.loads(fx.out_path.read_text(encoding="utf-8"))
        sidecar = json.loads(fx.sidecar_path.read_text(encoding="utf-8"))
        payload = event["payload"]
        payload_bytes = frozen_runner.jcs_canonical_bytes(payload)

        decoded = base64.b64decode(sidecar["payload_b64"], validate=True)
        assert decoded == payload_bytes, "sidecar payload b64 does not decode to JCS payload bytes"
        assert sidecar["payload_b64"] == event["dsse"]["payload"]
        assert sidecar["payload_sha256"] == hashlib.sha256(payload_bytes).hexdigest()
        assert sidecar["payload_type"] == event["dsse"]["payloadType"]

        pae = frozen_runner.dsse_pae(event["dsse"]["payloadType"], payload_bytes)
        assert bytes.fromhex(sidecar["pae_hex"]) == pae
        assert sidecar["pae_sha256"] == hashlib.sha256(pae).hexdigest()
        assert event["dsse"]["signatures"] == []


class TestJcsDifferential:
    CASES: tuple[Any, ...] = (
        None, True, False, 0, 1, -1, 2**53 - 1, -(2**53 - 1),
        "", "a", "é", "€", "\U0001d11e", "line\nbreak", "quote\"back\\slash",
        [], {}, [1, "2", None, {"k": [True]}],
        {"b": 1, "a": [{}, [], "x"], "é": "acute", "A": "upper", "z": "low",
         "Ａ": "fullwidth-A", "\U0001d11e": "clef"},
        {"nested": {"deep": {"": "empty-key", "0": 0}}},
    )

    def test_embedded_jcs_is_byte_identical_to_the_runner(
            self, tool_receipt, frozen_runner) -> None:
        for case in self.CASES:
            assert tool_receipt.jcs_canonical_bytes(case) == \
                frozen_runner.jcs_canonical_bytes(case), f"JCS bytes diverged on {case!r}"

    def test_embedded_jcs_rejection_parity(self, tool_receipt, frozen_runner) -> None:
        for bad in (1.5, 2**53, -(2**53), {1: "x"}, {"f": 0.0}, ("tuple",)):
            with pytest.raises(ValueError):
                tool_receipt.jcs_canonical_bytes(bad)
            with pytest.raises(ValueError):
                frozen_runner.jcs_canonical_bytes(bad)

    def test_embedded_jcs_matches_repo_jcs_module_if_present(
            self, tool_receipt, repo_root) -> None:
        candidates = (
            repo_root / "tools" / "jcs_canonical.py",
            pathlib.Path("/home/user/TriadOrigin/tools/jcs_canonical.py"),
        )
        module_path = next((c for c in candidates if c.is_file()), None)
        if module_path is None:
            pytest.skip("tools/jcs_canonical.py has not landed yet (sibling-or-skip)")
        import sys
        spec = importlib.util.spec_from_file_location("repo_jcs_canonical", module_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules["repo_jcs_canonical"] = module
        try:
            spec.loader.exec_module(module)
        finally:
            sys.modules.pop("repo_jcs_canonical", None)
        for case in self.CASES:
            assert tool_receipt.jcs_canonical_bytes(case) == \
                module.jcs_canonical_bytes(case), f"JCS bytes diverged on {case!r}"


class TestChronologyRefusedByName:
    def _expect_refusal(self, fx: Fixture, run_tool, token: str) -> None:
        rewrite_config(fx)
        proc = run_build(fx, run_tool)
        assert proc.returncode == 2, f"expected refusal {token}; stdout={proc.stdout}"
        assert token in proc.stderr, proc.stderr
        assert not fx.out_path.exists()

    def test_reviewed_after_source_merge(self, run_tool, registry_spec_factory, tmp_path) -> None:
        fx = build_fixture(tmp_path, run_tool, registry_spec_factory)
        fx.config["reviewed_at_us"] = str(fx.now_us - 2_900_000)
        self._expect_refusal(fx, run_tool, "REVIEWED_AFTER_SOURCE_MERGE")

    def test_observed_before_source_merge(self, run_tool, registry_spec_factory, tmp_path) -> None:
        fx = build_fixture(tmp_path, run_tool, registry_spec_factory)
        fx.config["observed_at_us"] = str(fx.now_us - 3_500_000)
        self._expect_refusal(fx, run_tool, "OBSERVED_BEFORE_SOURCE_MERGE")

    def test_emitted_before_observed(self, run_tool, registry_spec_factory, tmp_path) -> None:
        fx = build_fixture(tmp_path, run_tool, registry_spec_factory)
        fx.config["emitted_at_us"] = str(fx.now_us - 2_100_000)
        self._expect_refusal(fx, run_tool, "EMITTED_BEFORE_OBSERVED")

    def test_ttl_not_positive(self, run_tool, registry_spec_factory, tmp_path) -> None:
        fx = build_fixture(tmp_path, run_tool, registry_spec_factory)
        fx.config["expires_at_us"] = fx.config["emitted_at_us"]
        self._expect_refusal(fx, run_tool, "TTL_NOT_POSITIVE")

    def test_ttl_exceeds_max(self, run_tool, registry_spec_factory, tmp_path,
                             tool_receipt) -> None:
        fx = build_fixture(tmp_path, run_tool, registry_spec_factory)
        emitted = int(fx.config["emitted_at_us"])
        fx.config["expires_at_us"] = str(emitted + tool_receipt.MAX_RECEIPT_TTL_US + 1)
        self._expect_refusal(fx, run_tool, "TTL_EXCEEDS_MAX")

    def test_ttl_at_exact_max_is_accepted(self, run_tool, registry_spec_factory, tmp_path,
                                          tool_receipt) -> None:
        fx = build_fixture(tmp_path, run_tool, registry_spec_factory)
        emitted = int(fx.config["emitted_at_us"])
        fx.config["expires_at_us"] = str(emitted + tool_receipt.MAX_RECEIPT_TTL_US)
        rewrite_config(fx)
        proc = run_build(fx, run_tool)
        assert proc.returncode == 0, proc.stderr

    def test_evidence_observed_out_of_window(
            self, run_tool, registry_spec_factory, tmp_path) -> None:
        fx = build_fixture(tmp_path, run_tool, registry_spec_factory)
        fx.config["evidence"][2]["observed_at_us"] = str(fx.now_us - 3_000_001)
        self._expect_refusal(fx, run_tool, "EVIDENCE_OBSERVED_OUT_OF_WINDOW")

    def test_bad_int64_time_field(self, run_tool, registry_spec_factory, tmp_path) -> None:
        fx = build_fixture(tmp_path, run_tool, registry_spec_factory)
        fx.config["emitted_at_us"] = "+123"
        self._expect_refusal(fx, run_tool, "BAD_INT64")


class TestStructuralRefusals:
    def _expect_refusal(self, fx: Fixture, run_tool, token: str) -> None:
        rewrite_config(fx)
        proc = run_build(fx, run_tool)
        assert proc.returncode == 2, f"expected refusal {token}; stdout={proc.stdout}"
        assert token in proc.stderr, proc.stderr

    def test_b01_with_predecessor_refused(self, run_tool, registry_spec_factory, tmp_path) -> None:
        fx = build_fixture(tmp_path, run_tool, registry_spec_factory, "B01")
        fx.config["predecessor"] = {"id": "x", "sha256": "7" * 64}
        self._expect_refusal(fx, run_tool, "PREDECESSOR_FORBIDDEN_FOR_B01")

    def test_non_b01_without_predecessor_refused(
            self, run_tool, registry_spec_factory, tmp_path) -> None:
        fx = build_fixture(tmp_path, run_tool, registry_spec_factory, "B05")
        fx.config["predecessor"] = None
        self._expect_refusal(fx, run_tool, "PREDECESSOR_REQUIRED")

    def test_supplied_evidence_sha256_refused(
            self, run_tool, registry_spec_factory, tmp_path) -> None:
        fx = build_fixture(tmp_path, run_tool, registry_spec_factory)
        fx.config["evidence"][1]["sha256"] = "5" * 64
        self._expect_refusal(fx, run_tool, "UNKNOWN_EVIDENCE_KEY")

    def test_missing_required_digest_role_refused(
            self, run_tool, registry_spec_factory, tmp_path) -> None:
        fx = build_fixture(tmp_path, run_tool, registry_spec_factory)
        fx.config["evidence"] = [
            row for row in fx.config["evidence"] if row["digest_role"] != "ARTIFACT"]
        self._expect_refusal(fx, run_tool, "MISSING_REQUIRED_DIGEST_ROLE")

    def test_duplicate_required_digest_role_refused(
            self, run_tool, registry_spec_factory, tmp_path) -> None:
        fx = build_fixture(tmp_path, run_tool, registry_spec_factory)
        duplicate = dict(fx.config["evidence"][1])
        duplicate["evidence_id"] = "ev-artifact-duplicate"
        fx.config["evidence"].append(duplicate)
        self._expect_refusal(fx, run_tool, "DUPLICATE_EVIDENCE_ROLE")

    def test_same_source_and_receipt_pr_refused(
            self, run_tool, registry_spec_factory, tmp_path) -> None:
        fx = build_fixture(tmp_path, run_tool, registry_spec_factory)
        fx.config["receipt_pr"] = fx.config["source_pr"]
        self._expect_refusal(fx, run_tool, "SAME_SOURCE_AND_RECEIPT_PR")

    def test_build_merge_commit_mismatch_refused(
            self, run_tool, registry_spec_factory, tmp_path) -> None:
        fx = build_fixture(tmp_path, run_tool, registry_spec_factory)
        fx.config["merge_commit"] = "b" * 40
        self._expect_refusal(fx, run_tool, "BUILD_MERGE_COMMIT_MISMATCH")

    def test_ci_reviewer_refused(self, run_tool, registry_spec_factory, tmp_path) -> None:
        fx = build_fixture(tmp_path, run_tool, registry_spec_factory)
        fx.config["reviewer"] = "github-actions[bot]"
        self._expect_refusal(fx, run_tool, "REVIEWER_IS_CI")

    def test_profile_decision_pin_mismatch_refused(
            self, run_tool, registry_spec_factory, tmp_path) -> None:
        fx = build_fixture(tmp_path, run_tool, registry_spec_factory)
        fx.profile_sha = "1" * 64
        rewrite_config(fx)
        proc = run_build(fx, run_tool)
        assert proc.returncode == 2
        assert "PROFILE_DECISION_PIN_MISMATCH" in proc.stderr

    def test_evidence_path_escape_refused(self, run_tool, registry_spec_factory, tmp_path) -> None:
        fx = build_fixture(tmp_path, run_tool, registry_spec_factory)
        outside = tmp_path / "outside.txt"
        outside.write_text("outside\n", encoding="utf-8")
        fx.config["evidence"][1]["path"] = "../outside.txt"
        self._expect_refusal(fx, run_tool, "EVIDENCE_PATH_ESCAPES_REPO")

    def test_out_inside_repo_refused(self, run_tool, registry_spec_factory, tmp_path,
                                     repo_root) -> None:
        fx = build_fixture(tmp_path, run_tool, registry_spec_factory)
        fx.out_path = repo_root / "tmp_receipt_should_never_exist.json"
        proc = run_build(fx, run_tool)
        assert proc.returncode == 2
        assert "OUT_PATH_INSIDE_REPOSITORY" in proc.stderr
        assert not fx.out_path.exists()


class TestSelfCheckIndependence:
    def test_self_check_catches_post_build_tampering(
            self, run_tool, registry_spec_factory, tmp_path, tool_receipt) -> None:
        fx = build_fixture(tmp_path, run_tool, registry_spec_factory)
        assert run_build(fx, run_tool).returncode == 0
        event = json.loads(fx.out_path.read_text(encoding="utf-8"))
        event["payload"]["result"] = "FAIL"
        tampered = tmp_path / "tampered.json"
        tampered.write_text(json.dumps(event, sort_keys=True), encoding="utf-8")
        issues = tool_receipt.draft_issues(
            tampered, "B05",
            repository_root=fx.repo,
            trust_registry_sha256=fx.registry_sha,
            receipt_profile_decision_sha256=fx.profile_sha,
        )
        assert "receipt result must be exactly PASS" in issues
        assert "DSSE payload bytes do not equal RFC 8785 canonical receipt payload" in issues

    def test_self_check_clean_draft_has_zero_issues_via_module(
            self, run_tool, registry_spec_factory, tmp_path, tool_receipt) -> None:
        fx = build_fixture(tmp_path, run_tool, registry_spec_factory)
        assert run_build(fx, run_tool).returncode == 0
        issues = tool_receipt.draft_issues(
            fx.out_path, "B05",
            repository_root=fx.repo,
            trust_registry_sha256=fx.registry_sha,
            receipt_profile_decision_sha256=fx.profile_sha,
            now_us=fx.now_us,
        )
        assert issues == []
