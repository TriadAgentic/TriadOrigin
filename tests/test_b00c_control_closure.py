"""B00C corrective control closure — acceptance battery.

Proves the reconciled-plan corrections hold against the vendored machine law:

  * formula-registry equality: the RC3 effective bundle declares exactly F00..F23 and no F24
    reference survives anywhere in the plan/tool layer;
  * F01/F07 are E01-owned: the build ledger schedules their implementation rows in the estate
    lane, never in a repository milestone;
  * the RC4 bundle declares exactly 35 invalid lever aliases (the uploaded-plan claim of 34 was
    a P0 defect) and 32 refusal codes and 17 timing bounds;
  * the combined RC3+RC4 DAG validator passes, and each of its hard-fail checks actually fails
    on a poisoned input;
  * the historical build-ledger review is bound to its exact frozen REVIEWED_V2 subject, never
    silently promoted to the current candidate, and --verify fails without either artifact;
  * the hardened gate-receipt PASS semantics refuse stale windows, wildcard/empty scope,
    placeholder digests, non-independent approvers, open blockers, and missing rollback proof.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import contracts  # noqa: E402

CONTROL = ROOT / "docs" / "control"
RC3 = json.loads((CONTROL / "rc3_effective_control_bundle.json").read_text())
RC4 = json.loads((CONTROL / "rc4_control_bundle.json").read_text())
LEDGER = json.loads((CONTROL / "build_ledger.json").read_text())
PY = sys.executable


class TestFormulaRegistryEquality:
    def test_rc3_declares_exactly_f00_to_f23(self):
        ids = sorted(f["id"] for f in RC3["formulas"])
        assert ids == [f"F{i:02d}" for i in range(24)]

    def test_no_f24_reference_in_plan_or_tools(self):
        # An affirmative F24 reference is a defect; the prohibition prose itself
        # ("there is no F24", "remove F24", "F24 invented") is the law being enforced.
        pattern = re.compile(r"\bF24\b")
        negation = re.compile(r"no F24|remove F24|F24 invented|IDs/F24|no F24 reference|"
                              r"Assert no F24|F24 exists", re.IGNORECASE)
        hits = []
        for base in (ROOT / "docs" / "plan", ROOT / "tools", ROOT / "src"):
            for path in sorted(base.rglob("*")):
                if path.suffix in (".md", ".py", ".json") and path.is_file():
                    for line_no, line in enumerate(
                            path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                        if pattern.search(line) and not negation.search(line):
                            hits.append(f"{path.relative_to(ROOT)}:{line_no}")
        assert hits == [], f"affirmative F24 references survive: {hits}"

    def test_f01_and_f07_formula_rows_are_estate_lane(self):
        lanes = {
            row["id"]: row["milestone"] for row in LEDGER["tasks"]
            if row["row_class"] == "FORMULA_ATOMIC"
        }
        rc3_tasks = {t["id"]: t for t in RC3["tasks"]}
        seen = {"F01": 0, "F07": 0}
        for task_id, lane in lanes.items():
            refs = str(rc3_tasks[task_id].get("formula_refs") or "")
            for fid in ("F01", "F07"):
                if re.search(rf"\b{fid}\b", refs):
                    seen[fid] += 1
                    assert lane == "ESTATE", (
                        f"{task_id} ({fid}, E01-owned) scheduled in {lane}")
        assert seen["F01"] > 0 and seen["F07"] > 0


class TestRc4BundleCounts:
    def test_exactly_35_invalid_aliases(self):
        assert len(RC4["lever_law"]["invalid_aliases"]) == 35

    def test_exactly_32_refusal_codes(self):
        assert len(RC4["refusals"]) == 32

    def test_exactly_17_timing_bounds(self):
        assert len(RC4["timings"]) == 17

    def test_exactly_135_tasks_and_125_verifications(self):
        assert len(RC4["tasks"]) == 135
        assert len(RC4["verifications"]) == 125


class TestCombinedDagValidator:
    def test_validator_passes_on_vendored_bundles(self):
        result = subprocess.run(
            [PY, str(ROOT / "tools" / "validate_combined_dag.py")],
            capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert "no cycles" in result.stdout
        assert "source authority preserved" in result.stdout

    def _run_with_ledger(self, tmp_path, mutate):
        """Copy the control dir, poison the ledger, run the validator against the copy."""
        control = tmp_path / "docs" / "control"
        control.mkdir(parents=True)
        for name in ("rc3_effective_control_bundle.json", "rc4_control_bundle.json",
                     "build_ledger.json"):
            control.joinpath(name).write_text((CONTROL / name).read_text())
        ledger = json.loads((control / "build_ledger.json").read_text())
        mutate(ledger)
        control.joinpath("build_ledger.json").write_text(json.dumps(ledger))
        tool = tmp_path / "tools" / "validate_combined_dag.py"
        tool.parent.mkdir()
        tool.write_text((ROOT / "tools" / "validate_combined_dag.py").read_text())
        return subprocess.run([PY, str(tool)], capture_output=True, text=True)

    def test_duplicate_scheduling_owner_fails(self, tmp_path):
        result = self._run_with_ledger(
            tmp_path, lambda ledger: ledger["tasks"].append(dict(ledger["tasks"][0])))
        assert result.returncode == 1
        assert "more than once" in result.stderr

    def test_missing_scheduling_owner_fails(self, tmp_path):
        result = self._run_with_ledger(tmp_path, lambda ledger: ledger["tasks"].pop())
        assert result.returncode == 1
        assert "lack a scheduling owner" in result.stderr

    def test_rewritten_source_gate_fails(self, tmp_path):
        def mutate(ledger):
            ledger["tasks"][0]["gate"] = "G9-REWRITTEN"
        result = self._run_with_ledger(tmp_path, mutate)
        assert result.returncode == 1
        assert "rewrote gate" in result.stderr

    def test_unreviewed_inversion_fails(self, tmp_path):
        def mutate(ledger):
            # Manufacture a brand-new inversion class: push one B01 task with hard
            # successors in B00's slice out to B09.
            for row in ledger["tasks"]:
                if row["id"] == "CTL-G0-01":
                    row["milestone"] = "B09"
        result = self._run_with_ledger(tmp_path, mutate)
        assert result.returncode == 1
        assert "unreviewed milestone inversion" in result.stderr


class TestLedgerReviewRecord:
    def test_review_covers_exact_frozen_v2_subject(self):
        review = json.loads((CONTROL / "build_ledger_review.v1.json").read_text())
        subject_path = CONTROL / "closure/predecessors/build_ledger.REVIEWED_V2.json"
        subject = json.loads(subject_path.read_text())
        assert hashlib.sha256(subject_path.read_bytes()).hexdigest() == (
            "78f6ce7254390997d54ce6732a46e138f24a56502677ba469dff22bf92f2b51e"
        )
        assert subject["ledger_version"] == review["ledger_version"] == "REVIEWED_V2"
        assert LEDGER["ledger_version"] == "CANDIDATE_V3"
        assert review["reviewer"]
        reviewed = {row["id"] for row in review["rows"]}
        assert reviewed == {row["id"] for row in subject["tasks"]}
        assert review["row_count"] == len(subject["tasks"])
        subject_rows = {row["id"]: row for row in subject["tasks"]}
        candidate_rows = {row["id"]: row for row in LEDGER["tasks"]}
        assert sum(candidate_rows[k] != subject_rows[k] for k in candidate_rows) == 94

    def test_review_dispositions_closed_vocabulary(self):
        review = json.loads((CONTROL / "build_ledger_review.v1.json").read_text())
        allowed = {"REVIEWED_ACCEPT", "REVIEWED_MOVED", "REVIEWED_NEW"}
        assert {row["disposition"] for row in review["rows"]} <= allowed

    def test_verify_fails_without_review_record(self, tmp_path, monkeypatch):
        # Run --verify from a tree copy whose review record is deleted.
        import shutil
        tree = tmp_path / "tree"
        (tree / "docs").mkdir(parents=True)
        shutil.copytree(CONTROL, tree / "docs" / "control")
        (tree / "docs" / "control" / "build_ledger_review.v1.json").unlink()
        tool_dir = tree / "tools"
        tool_dir.mkdir()
        (tool_dir / "build_ledger.py").write_text(
            (ROOT / "tools" / "build_ledger.py").read_text())
        result = subprocess.run(
            [PY, str(tool_dir / "build_ledger.py"), "--verify"],
            capture_output=True, text=True)
        assert result.returncode == 1
        assert "review record missing" in result.stderr

    def test_verify_fails_without_frozen_review_subject(self, tmp_path):
        import shutil
        tree = tmp_path / "tree"
        (tree / "docs").mkdir(parents=True)
        shutil.copytree(CONTROL, tree / "docs" / "control")
        (tree / "docs/control/closure/predecessors/build_ledger.REVIEWED_V2.json").unlink()
        tool_dir = tree / "tools"
        tool_dir.mkdir()
        (tool_dir / "build_ledger.py").write_text(
            (ROOT / "tools" / "build_ledger.py").read_text())
        result = subprocess.run(
            [PY, str(tool_dir / "build_ledger.py"), "--verify"],
            capture_output=True, text=True)
        assert result.returncode == 1
        assert "frozen REVIEWED_V2 review subject missing" in result.stderr


def _gate_receipt_event(**payload_patch):
    event = json.loads(
        (ROOT / "contracts" / "golden" / "triad.gate_receipt.v2" / "valid.json").read_text())
    event["payload"].update(payload_patch)
    return event


class TestHardenedGateReceiptLaw:
    def test_valid_golden_passes(self):
        contracts.validate(_gate_receipt_event())

    @pytest.mark.parametrize("patch,code", [
        ({"open_blockers": ["BLK-1"]}, "GATE_PASS_WITH_OPEN_BLOCKERS"),
        ({"rollback_proof_ids": []}, "GATE_PASS_WITHOUT_ROLLBACK_PROOF"),
        ({"task_receipt_ids": []}, "GATE_PASS_WITHOUT_RECEIPTS"),
        ({"scope": {}}, "GATE_PASS_EMPTY_SCOPE"),
        ({"scope": {"gate": "G*"}}, "SCOPE_VALUE_INVALID"),
        ({"expires_at_us": 1786156800123456, "observed_at_us": 1786156800123456},
         "GATE_PASS_INVALID_VALIDITY_WINDOW"),
        ({"producer_digests": {}}, "GATE_PASS_MISSING_OR_PLACEHOLDER_DIGESTS"),
        ({"producer_digests": {"contract_manifest": "0" * 64}},
         "GATE_PASS_MISSING_OR_PLACEHOLDER_DIGESTS"),
        ({"producer_digests": {"contract_manifest": "abc"}},
         "GATE_PASS_MISSING_OR_PLACEHOLDER_DIGESTS"),
        ({"approver": "governance-evidence"}, "GATE_PASS_APPROVER_NOT_INDEPENDENT"),
    ])
    def test_pass_defect_refused(self, patch, code):
        with pytest.raises(contracts.ContractError, match=code):
            contracts.validate(_gate_receipt_event(**patch))

    def test_non_pass_result_not_gated(self):
        # A FAIL/BLOCKED gate receipt records honestly without the PASS conjuncts.
        contracts.validate(_gate_receipt_event(result="BLOCKED", open_blockers=["BLK-1"],
                                               producer_digests={}))


class TestReceiptFilesOnDisk:
    @pytest.mark.parametrize("name", ["B00", "B01", "B02", "R00"])
    def test_receipt_validates(self, name):
        result = subprocess.run(
            [PY, str(ROOT / "tools" / "validate_b_receipt.py"),
             str(ROOT / "evidence" / "receipts" / f"{name}.json")],
            capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

    def test_r00_supersession_names_absent_evidence(self):
        receipt = json.loads((ROOT / "evidence" / "receipts" / "R00.json").read_text())
        ids = receipt["payload"]["evidence_ids"]
        assert "r00-ceremony-status:NOT_EXECUTED" in ids
        assert any(i.startswith("absent-evidence-named:") for i in ids)
        doc = (ROOT / "docs" / "governance" / "R00_SUPERSESSION.md").read_text()
        assert "COUNTERSIGNED" in doc
