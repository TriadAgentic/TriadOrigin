"""B00R falsification matrix — governance/receipt/evidence law (repair plan §10).

Each test is a focused mutation that must fail closed. The governance/provider-authenticated rows
(GitHub rulesets, real signatures, provider evidence) are owner acts; the machinery here is proven
to fail closed until those inputs exist — an unauthenticated template, a self-hash receipt, or an
absent trust registry can never PASS.
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

from triad_origin import governance as gov  # noqa: E402
from triad_origin.canonical import sha256_hex  # noqa: E402

PY = sys.executable


def _run(*argv, cwd=ROOT):
    return subprocess.run([PY, *argv], cwd=cwd, capture_output=True, text=True)


def _golden(sid, which):
    return json.loads((ROOT / f"contracts/golden/{sid}/{which}.json").read_text())


# --- NEG-001 · unknown ledger task refuses (no B00 fallback) -------------------------------------
def test_neg001_unknown_row_class_refuses_not_b00():
    from tools import build_ledger as bl
    with pytest.raises(bl.LedgerClassificationError):
        bl.classify_rc3({"id": "X-999", "row_class": "MYSTERY", "node": "Nowhere",
                         "gate": "", "phase": ""})
    with pytest.raises(bl.LedgerClassificationError):
        bl.classify_rc4({"id": "L-999", "gate": "L99", "instruction": "", "domain": ""})


def test_neg001_gap_and_scope_rows_are_explicit_governance():
    from tools import build_ledger as bl
    assert bl.classify_rc3({"id": "GAP-1", "row_class": "GAP_CLOSURE", "node": "x",
                            "gate": "G-1", "phase": "P-1"}) == (
        "B00", "IN_REPO_GOVERNANCE", "R8_GOVERNANCE_CLOSURE")
    assert bl.classify_rc3({"id": "SCP-1", "row_class": "RC1_SCOPE_CLOSURE", "node": "x",
                            "gate": "G-1", "phase": "P-1"})[2] == "R8_GOVERNANCE_CLOSURE"


# --- NEG-004 · same bundle id with changed bytes fails (immutability) -----------------------------
def test_neg004_receipt_v3_immutable_schema_registered():
    # The v3 schema is a NEW additive identity; the historical v2 is preserved untouched.
    assert (ROOT / "contracts/schemas/triad.evidence_receipt.v2.schema.json").exists()
    assert (ROOT / "contracts/schemas/triad.evidence_receipt.v3.schema.json").exists()


# --- NEG-005 · nonhex/uppercase/zero/placeholder digest fails -------------------------------------
@pytest.mark.parametrize("bad", ["", gov.ZERO_DIGEST, "A" * 64, "abc", "g" * 64,
                                 "NOT_APPLICABLE", "0" + "a" * 63 + "Z"])
def test_neg005_bad_digest_rejected(bad):
    with pytest.raises(gov.GovernanceError):
        gov.assert_hex64(bad, "field")


def test_neg005_good_digest_accepted():
    assert gov.assert_hex64("a" * 64, "field") == "a" * 64


# --- NEG-006 · empty/null/whitespace/wildcard/nested-empty/unknown scope fails --------------------
@pytest.mark.parametrize("bad", [{}, [], "", "   ", "a*b", "*", None, 1.5,
                                 {"k": ""}, {"k": []}, {"k": {"j": None}}, [1, []]])
def test_neg006_closed_scope_rejects(bad):
    with pytest.raises(gov.GovernanceError):
        gov.assert_closed_scope(bad)


def test_neg006_closed_scope_accepts_wellformed():
    gov.assert_closed_scope({"milestone": "B00R", "paths": ["a", "b"], "n": 3, "flag": True})


# --- NEG-007 · source row_class/gate/node drift with equal milestone fails ------------------------
def test_neg007_dag_detects_row_class_drift(tmp_path):
    # Copy the repo control tree, corrupt one ledger row's row_class, and prove the DAG validator
    # rejects the authority drift.
    import shutil
    tree = tmp_path / "repo"
    (tree / "docs" / "control").mkdir(parents=True)
    (tree / "tools").mkdir()
    for name in ("rc3_effective_control_bundle.json", "rc4_control_bundle.json",
                 "build_ledger.json"):
        shutil.copy(ROOT / "docs/control" / name, tree / "docs/control" / name)
    shutil.copy(ROOT / "tools/validate_combined_dag.py", tree / "tools/validate_combined_dag.py")
    ledger = json.loads((tree / "docs/control/build_ledger.json").read_text())
    # Find one RC3-sourced row and flip its row_class.
    rc3 = {t["id"] for t in json.loads(
        (tree / "docs/control/rc3_effective_control_bundle.json").read_text())["tasks"]}
    for row in ledger["tasks"]:
        if row["id"] in rc3 and row.get("row_class"):
            row["row_class"] = "TAMPERED_ROW_CLASS"
            break
    (tree / "docs/control/build_ledger.json").write_text(json.dumps(ledger))
    proc = subprocess.run([PY, "tools/validate_combined_dag.py"], cwd=tree,
                          capture_output=True, text=True)
    assert proc.returncode == 1
    assert "row_class" in (proc.stdout + proc.stderr)


# --- NEG-008 · self-hash-only / no external signature fails ---------------------------------------
def test_neg008_no_external_signatures_is_blocked():
    receipt = _golden("triad.evidence_receipt.v3", "valid")
    trust = gov.validate_trust_registry(_golden("triad.receipt_trust_registry.v1", "valid"))
    # A profile-required threshold with an empty signatures array can never PASS.
    result, reason = gov.validate_receipt_v3(
        receipt, milestone="B00R", trust=trust,
        now_us=receipt["payload"]["emitted_at_us"], expected_root_generation=1)
    assert result == "BLOCKED" and reason == "NO_EXTERNAL_SIGNATURES"


def test_neg008_v2_self_hash_receipt_cannot_pass_strict():
    proc = _run("tools/validate_b_receipt.py", "--strict", "--milestone", "B00",
                "evidence/receipts/B00.json")
    # Missing strict closure inputs are a CLI-usage refusal (2); a fully supplied v2 remains a
    # validation refusal (1). Either way the historical self-hash can never return closure success.
    assert proc.returncode != 0


# --- NEG-009 · unknown/revoked/duplicate/wrong-role signer fails ----------------------------------
def test_neg009_signer_threshold_rejections():
    trust = {
        "k1": {"key_id": "k1", "identity": "id1", "role": "EVIDENCE_PRODUCER",
               "algorithm": "ed25519", "public_key_hex": "0" * 64, "revoked": False},
        "k2": {"key_id": "k2", "identity": "id1", "role": "INDEPENDENT_COUNTERSIGNER",
               "algorithm": "ed25519", "public_key_hex": "1" * 64, "revoked": False},
        "k3": {"key_id": "k3", "identity": "id3", "role": "EVIDENCE_PRODUCER",
               "algorithm": "ed25519", "public_key_hex": "2" * 64, "revoked": True},
    }
    body = b"payload"
    # unknown signer
    ok, reason = gov.verify_signatures(
        signed_bytes=body, signatures=[{"key_id": "nope", "signature_hex": "0"}],
        trust=trust, required_roles=("EVIDENCE_PRODUCER",), threshold=1)
    assert not ok and reason.startswith("UNKNOWN_SIGNER")
    # revoked signer
    ok, reason = gov.verify_signatures(
        signed_bytes=body, signatures=[{"key_id": "k3", "signature_hex": "0"}],
        trust=trust, required_roles=("EVIDENCE_PRODUCER",), threshold=1)
    assert not ok and reason.startswith("REVOKED_SIGNER")
    # duplicate identity across two key ids
    ok, reason = gov.verify_signatures(
        signed_bytes=body,
        signatures=[{"key_id": "k1", "signature_hex": "0" * 128},
                    {"key_id": "k2", "signature_hex": "0" * 128}],
        trust=trust, required_roles=(), threshold=2)
    assert not ok and reason.startswith("DUPLICATE_SIGNER_IDENTITY")
    # empty signatures
    ok, reason = gov.verify_signatures(
        signed_bytes=body, signatures=[], trust=trust, required_roles=(), threshold=1)
    assert not ok and reason == "NO_EXTERNAL_SIGNATURES"


# --- NEG-011 · missing/wrong/path-escaped/untracked/symlink evidence preimage fails ---------------
def test_neg011_evidence_manifest_missing_and_mismatch(tmp_path):
    (tmp_path / "evidence").mkdir()
    good = tmp_path / "evidence" / "a.json"
    good.write_text("{}")
    manifest = {
        "schema": "triad.evidence_manifest.v1", "schema_version": "1.0.0",
        "manifest_kind": "EVIDENCE_MANIFEST", "entry_count": 1,
        "entries": [{"path": "evidence/a.json", "role": "A", "media_type": "application/json",
                     "size": 2, "sha256": sha256_hex(b"{}")}]}
    gov.validate_evidence_manifest(manifest, tmp_path)  # baseline valid
    # digest mismatch
    bad = copy.deepcopy(manifest)
    bad["entries"][0]["sha256"] = "b" * 64
    with pytest.raises(gov.GovernanceError):
        gov.validate_evidence_manifest(bad, tmp_path)
    # path escape
    esc = copy.deepcopy(manifest)
    esc["entries"][0]["path"] = "../secret.json"
    with pytest.raises(gov.GovernanceError):
        gov.validate_evidence_manifest(esc, tmp_path)
    # missing file
    miss = copy.deepcopy(manifest)
    miss["entries"][0]["path"] = "evidence/nope.json"
    with pytest.raises(gov.GovernanceError):
        gov.validate_evidence_manifest(miss, tmp_path)


def test_neg011_evidence_manifest_rejects_symlink(tmp_path):
    (tmp_path / "evidence").mkdir()
    target = tmp_path / "evidence" / "real.json"
    target.write_text("{}")
    link = tmp_path / "evidence" / "link.json"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    manifest = {
        "schema": "triad.evidence_manifest.v1", "schema_version": "1.0.0",
        "manifest_kind": "EVIDENCE_MANIFEST", "entry_count": 1,
        "entries": [{"path": "evidence/link.json", "role": "A", "media_type": "application/json",
                     "size": 2, "sha256": sha256_hex(b"{}")}]}
    with pytest.raises(gov.GovernanceError):
        gov.validate_evidence_manifest(manifest, tmp_path)


@pytest.mark.parametrize(
    ("unique_flags", "should_fail"),
    [((True, False), True), ((False, True), True), ((None, False), True),
     ((False, False), False)],
)
def test_evidence_manifest_duplicate_role_group_law(
    tmp_path, unique_flags, should_fail
):
    (tmp_path / "evidence").mkdir()
    entries = []
    for index, flag in enumerate(unique_flags):
        rel = f"evidence/{index}.json"
        data = b"{}"
        (tmp_path / rel).write_bytes(data)
        entry = {
            "path": rel,
            "role": "SINGLETON",
            "media_type": "application/json",
            "size": len(data),
            "sha256": sha256_hex(data),
        }
        if flag is not None:
            entry["role_unique"] = flag
        entries.append(entry)
    manifest = {
        "schema": "triad.evidence_manifest.v1",
        "schema_version": "1.0.0",
        "manifest_kind": "EVIDENCE_MANIFEST",
        "entry_count": len(entries),
        "entries": entries,
    }
    if not should_fail:
        gov.validate_evidence_manifest(manifest, tmp_path)
        return
    with pytest.raises(gov.GovernanceError, match="EVIDENCE_DUPLICATE_ROLE: SINGLETON"):
        gov.validate_evidence_manifest(manifest, tmp_path)


@pytest.mark.parametrize(
    ("rel", "role", "role_unique", "allowed"),
    [
        (
            "evidence/B00R_G2/clean_runner/commands/00-pytest-seed0/stderr.bin",
            "CLEAN_RUNNER_COMMAND_STDERR", False, True,
        ),
        (
            "evidence/B00R_G2/clean_runner/rollback/stdout.bin",
            "CLEAN_RUNNER_ROLLBACK_STDOUT", True, True,
        ),
        (
            "evidence/B00R_G2/clean_runner/commands/00-pytest-seed0/stderr.bin",
            "UNRELATED", False, False,
        ),
        (
            "evidence/B00R_G2/clean_runner/commands/00-pytest-seed0/stderr.bin",
            "CLEAN_RUNNER_COMMAND_STDERR", True, False,
        ),
        (
            "evidence/B00R_G2/clean_runner/not-a-command/stderr.bin",
            "CLEAN_RUNNER_COMMAND_STDERR", False, False,
        ),
    ],
)
def test_evidence_manifest_empty_stream_exception_is_narrow(
    tmp_path, rel, role, role_unique, allowed
):
    from tools.b00r_clean_runner import ALLOWED_EMPTY_PATHS

    path = tmp_path / rel
    path.parent.mkdir(parents=True)
    path.write_bytes(b"")
    entry = {
        "path": rel,
        "role": role,
        "role_unique": role_unique,
        "media_type": "application/octet-stream",
        "size": 0,
        "sha256": sha256_hex(b""),
    }
    manifest = {
        "schema": "triad.evidence_manifest.v1",
        "schema_version": "1.0.0",
        "manifest_kind": "EVIDENCE_MANIFEST",
        "entry_count": 1,
        "entries": [entry],
    }
    if allowed:
        gov.validate_evidence_manifest(
            manifest, tmp_path, allowed_empty_paths=ALLOWED_EMPTY_PATHS)
    else:
        with pytest.raises(gov.GovernanceError, match="EVIDENCE_ZERO_SIZE"):
            gov.validate_evidence_manifest(
                manifest, tmp_path, allowed_empty_paths=ALLOWED_EMPTY_PATHS)


# --- NEG-012 · evidence before source merge / future-dated fails ----------------------------------
def test_neg012_chronology_order_and_future():
    receipt = _golden("triad.evidence_receipt.v3", "valid")
    # observed before merge
    bad = copy.deepcopy(receipt)
    bad["payload"]["observed_at_us"] = bad["payload"]["source_merge_time_us"] - 1
    result, reason = gov.validate_receipt_v3(
        bad, milestone="B00R", expected_root_generation=1)
    assert result == "FAIL" and reason.startswith("CHRONOLOGY_ORDER")
    # future-dated
    fut = copy.deepcopy(receipt)
    result, reason = gov.validate_receipt_v3(
        fut, milestone="B00R", now_us=fut["payload"]["emitted_at_us"] - 1,
        expected_root_generation=1)
    assert result == "FAIL" and reason == "CHRONOLOGY_FUTURE_EVIDENCE"


# --- NEG-017 · source PR touching receipt / receipt PR touching source fails ----------------------
def test_neg017_pr_role_mixed_fails():
    role, _ = gov.classify_changed_paths(
        ["src/x.py", "evidence/receipts/B00R.g2.receipt.v3.json"])
    assert role == "MIXED"
    proc = _run(
        "tools/classify_milestone_pr.py",
        "src/x.py",
        "evidence/receipts/B00R.g2.receipt.v3.json",
    )
    assert proc.returncode == 1


def test_neg017_pure_roles_pass():
    assert gov.classify_changed_paths(["src/triad_origin/governance.py"])[0] == "SOURCE"
    assert gov.classify_changed_paths(
        ["evidence/receipts/B00R.g2.receipt.v3.json"]
    )[0] == "RECEIPT"
    assert gov.classify_changed_paths(
        ["evidence/receipts/B00R.receipt.v3.json"]
    )[0] == "INVALID"


@pytest.mark.parametrize(
    "path",
    [
        "contracts/schemas/triad.execution_cmd.v2.schema.json",
        "docs/spec_rc4/new_formula.html",
        "src/triad_origin/contracts.py",
        "src/triad_origin/structures/structure_state.py",
        "src/triad_origin/control/lever_law.py",
        "src/triad_origin/formulas.py",
        "src/triad_origin/adapters/binance.py",
        "deploy/triad-origin.yaml",
        "ops/restart.sh",
        "venue/binance.json",
    ],
)
def test_neg017_b00r_source_scope_rejects_downstream_owned_paths(path):
    role, reason = gov.classify_changed_paths([path])
    assert role == "INVALID"
    assert "outside frozen governance scope" in reason


def test_neg017_b00r_source_scope_allows_only_c0_and_b00r_test_prefixes():
    assert gov.classify_changed_paths(
        ["docs/control/closure/closure_semantics.v1.json"]
    )[0] == "SOURCE"
    assert gov.classify_changed_paths(
        ["tests/b00r/test_new_scope_guard.py"]
    )[0] == "SOURCE"
    assert gov.classify_changed_paths(["docs/closure/coordination.md"])[0] == "INVALID"
    assert gov.classify_changed_paths(["tests/runtime/test_activation.py"])[0] == "INVALID"
    assert gov.classify_changed_paths(["tests/b00r/../runtime/test_activation.py"])[0] == \
        "INVALID"


# --- NEG-018 · B01C without exact B00R anchor is blocked (successor variant) ----------------------
def test_neg018_successor_requires_predecessor_anchor():
    receipt = _golden("triad.evidence_receipt.v3", "valid")
    succ = copy.deepcopy(receipt)
    succ["payload"]["milestone"] = "B01C"
    succ["payload"]["scope"]["milestone"] = "B01C"
    succ["payload"]["variant"] = "SUCCESSOR"
    # no predecessor block -> FAIL
    result, reason = gov.validate_receipt_v3(succ, milestone="B01C")
    assert result == "FAIL" and "PREDECESSOR" in reason


# --- NEG-021 · forbidden capability guard present -------------------------------------------------
def test_neg021_dark_capability_scan_passes():
    proc = _run("tools/verify_no_forbidden_capabilities.py")
    assert proc.returncode == 0, proc.stderr


# --- NEG-022 · OFF/OFF/OFF/LIVE drift fails -------------------------------------------------------
def test_neg022_safety_posture_drift_fails():
    receipt = _golden("triad.evidence_receipt.v3", "valid")
    bad = copy.deepcopy(receipt)
    bad["payload"]["levers"]["shadow_activation"] = "OFF"  # SHADOW must stay LIVE
    result, reason = gov.validate_receipt_v3(
        bad, milestone="B00R", expected_root_generation=1)
    assert result == "FAIL"


def test_neg022_result_enum_closed():
    receipt = _golden("triad.evidence_receipt.v3", "valid")
    bad = copy.deepcopy(receipt)
    bad["payload"]["result"] = "PASS"  # generic PASS is not a closure result
    result, _ = gov.validate_receipt_v3(
        bad, milestone="B00R", expected_root_generation=1)
    assert result == "FAIL"


# --- authority root + governance snapshot fail-closed on templates -------------------------------
def test_authority_root_unavailable_on_templates_strict():
    proc = _run("tools/validate_authority_root.py", "--strict")
    assert proc.returncode == 1
    assert "UNAVAILABLE_AUTHORITY_ROOT" in (proc.stdout + proc.stderr)


def test_governance_snapshot_unavailable_on_template_strict(capsys):
    from tools import validate_governance_snapshot as snapshot
    assert snapshot.main(["--strict"]) == 1
    captured = capsys.readouterr()
    assert "UNAVAILABLE" in (captured.out + captured.err)


def test_absent_canonical_governance_snapshot_is_unavailable_not_fabricated_fail(capsys):
    from tools import validate_governance_snapshot as snapshot
    assert snapshot.main([
        "--strict", "--snapshot", "docs/governance/rulesets/main.ruleset.provider.json",
    ]) == 1
    captured = capsys.readouterr()
    assert "UNAVAILABLE" in (captured.out + captured.err)


def test_empty_provider_expansion_does_not_become_a_malformed_authority_pin():
    from tools import validate_authority_root as authority
    empty_ci_environment = {meta[0]: "" for meta in authority.SUBJECTS.values()}
    assert authority.load_external_pins(environ=empty_ci_environment) == {}


def test_generation2_pin_file_must_contain_exactly_four_authority_pins(
    tmp_path
):
    from tools import validate_authority_root as authority

    subjects, _paths = authority._authority_profile(2)
    names = [meta[0] for meta in subjects.values()]
    complete = {name: chr(97 + index) * 64 for index, name in enumerate(names)}
    pins = tmp_path / "pins.json"
    pins.write_text(json.dumps(complete), encoding="utf-8")
    assert authority.load_external_pins(
        pins_path=pins, environ={}, repair_generation=2) == complete

    partial = dict(complete)
    missing_name = names[-1]
    partial.pop(missing_name)
    pins.write_text(json.dumps(partial), encoding="utf-8")
    with pytest.raises(
        authority.AuthorityRootError, match="EXTERNAL_PIN_FILE_KEY_SET_MISMATCH"
    ):
        authority.load_external_pins(
            pins_path=pins,
            environ={missing_name: complete[missing_name]},
            repair_generation=2,
        )

    pins.write_text(json.dumps({**complete, "MAIN_RULESET_EVIDENCE_SHA256": "f" * 64}))
    with pytest.raises(authority.AuthorityRootError, match="UNKNOWN_EXTERNAL_PIN_NAMES"):
        authority.load_external_pins(pins_path=pins, environ={}, repair_generation=2)


def test_decision_templates_are_unauthenticated():
    for name in (
        "DEC-AUTHORITY-BUNDLE-001",
        "DEC-RECEIPT-PROFILE-001",
        "DEC-B00-REPAIR-001",
        "DEC-RECEIPT-PROFILE-002",
        "DEC-B00-REPAIR-002",
    ):
        doc = json.loads(
            (ROOT / f"docs/governance/decisions/{name}.template.json").read_text())
        assert gov.decision_is_authenticated(doc) is False


def test_invalidation_manifest_matches_committed_receipts():
    inv = json.loads((ROOT / "docs/governance/B00_B07_INVALIDATION_MANIFEST.v1.json").read_text())
    assert inv["entries"]
    for entry in inv["entries"]:
        data = (ROOT / entry["path"]).read_bytes()
        assert sha256_hex(data) == entry["sha256"]
        assert entry["disposition"] in inv["disposition_vocabulary"]


def test_b00r_gate_owner_commands_are_strict_and_use_one_canonical_receipt():
    from argparse import Namespace
    from tools import b00r_gate

    args = Namespace(
        mode="receipt",
        expected_head="a" * 40,
        now_us=1_000_000,
        pins=None,
        receipt=b00r_gate.CANONICAL_RECEIPT,
        manifest=b00r_gate.CANONICAL_MANIFEST,
        governance_snapshot=b00r_gate.CANONICAL_GOVERNANCE_SNAPSHOT,
        provider_raw=b00r_gate.CANONICAL_PROVIDER_RAW,
        provider_pin=None,
        anchor_ruleset=b00r_gate.CANONICAL_ANCHOR_RULESET,
        anchor_ruleset_pin=None,
        receipt_pr=35,
    )
    gates = b00r_gate._owner_gates(args)
    commands = [gate.argv for gate in gates]
    assert all(gate.owner_gated for gate in gates)
    assert any(
        "--strict" in command
        and any(part.endswith("/validate_authority_root.py") for part in command)
        for command in commands
    )
    for command in commands[:2]:
        assert "--expected-head" in command
        assert "--git-root" in command
        assert "--now-us" in command
    receipt_commands = [
        command for command in commands
        if any(part.endswith("/validate_b_receipt.py") for part in command)
    ]
    assert len(receipt_commands) == 1
    assert receipt_commands[0][-1] == b00r_gate.CANONICAL_RECEIPT
    assert b00r_gate.CANONICAL_RECEIPT == "evidence/receipts/B00R.g2.receipt.v3.json"
    for flag in ("--now-us", "--manifest", "--git-root", "--expected-head",
                 "--governance-snapshot", "--provider-raw", "--receipt-pr"):
        assert flag in receipt_commands[0]
    assert receipt_commands[0][receipt_commands[0].index("--receipt-pr") + 1] == "35"
    assert "--trust" not in receipt_commands[0]
    assert not any("dsse" in part.lower() for command in commands for part in command)


@pytest.mark.parametrize(
    ("mode_flag", "expected_mode", "expected_privileged"),
    [
        ("--nonterminal-provider-proof", "nonterminal", False),
        ("--premerge-provider-proof", "premerge", True),
    ],
)
def test_receipt_provider_proof_modes_are_separate_and_nonterminal(
    monkeypatch, mode_flag, expected_mode, expected_privileged
):
    from tools import validate_b_receipt

    captured = {}

    def fake_strict(_receipt, **kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(validate_b_receipt, "_strict", fake_strict)
    receipt_pr_args = ["--receipt-pr", "35"] if expected_mode == "premerge" else []
    result = validate_b_receipt.main([
        "--strict",
        "--milestone", "B00R",
        "--now-us", "1000000",
        "--manifest", "evidence/B00R_G2/evidence_manifest.json",
        "--expected-head", "a" * 40,
        "--governance-snapshot", "docs/governance/rulesets/main.ruleset.provider.json",
        "--provider-raw", "docs/governance/rulesets/main.ruleset.provider.raw.json",
        "--provider-pin", "b" * 64,
        *receipt_pr_args,
        mode_flag,
        "evidence/receipts/B00R.g2.receipt.v3.json",
    ])
    assert result == 0
    assert captured["provider_proof_mode"] == expected_mode
    assert captured["require_live_rule_suite"] is expected_privileged
    assert captured["require_live_canary_ref"] is expected_privileged
    assert captured["require_bypass_visibility"] is expected_privileged
    assert captured["receipt_pr"] == (35 if expected_mode == "premerge" else None)


def test_receipt_provider_proof_modes_reject_ambiguous_terminal_inputs(capsys):
    from tools import validate_b_receipt

    common = [
        "--strict", "--milestone", "B00R", "--now-us", "1000000",
        "--manifest", "evidence/B00R_G2/evidence_manifest.json",
        "--expected-head", "a" * 40,
        "--governance-snapshot", "docs/governance/rulesets/main.ruleset.provider.json",
        "--provider-raw", "docs/governance/rulesets/main.ruleset.provider.raw.json",
        "--provider-pin", "b" * 64,
        "evidence/receipts/B00R.g2.receipt.v3.json",
    ]
    assert validate_b_receipt.main([
        *common[:-1], "--nonterminal-provider-proof", "--premerge-provider-proof", common[-1]
    ]) == 2
    assert "mutually exclusive" in capsys.readouterr().err
    assert validate_b_receipt.main([
        *common[:-1], "--premerge-provider-proof", common[-1]
    ]) == 2
    assert "premerge B00R strict mode requires" in capsys.readouterr().err
    assert validate_b_receipt.main([
        *common[:-1], "--nonterminal-provider-proof", "--receipt-pr", "35", common[-1]
    ]) == 2
    assert "nonterminal provider mode does not accept" in capsys.readouterr().err
    nonroot = list(common)
    nonroot[2] = "B01C"
    assert validate_b_receipt.main([
        *nonroot[:-1], "--premerge-provider-proof", "--receipt-pr", "35", nonroot[-1]
    ]) == 2
    assert "defined only for B00R" in capsys.readouterr().err
