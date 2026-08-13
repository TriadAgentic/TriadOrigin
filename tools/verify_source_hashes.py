#!/usr/bin/env python3
"""Strictly verify ``docs/control/SOURCE_HASHES.sha256`` (B00R-D06 / SRC-001 / SRC-002).

Until B00R this inventory existed but CI never recomputed it. This tool:

  1. strictly parses the file (lowercase nonzero hex, canonical relative paths, no duplicates, no
     path escape) via :func:`triad_origin.governance.parse_source_hashes`;
  2. recomputes every listed file's SHA-256 from bytes and fails on any mismatch or missing file;
  3. verifies the RC3 embedded composition manifest digests (effective bundle / overlay / overlay
     schema) against the actual bytes — a self-updating source + in-tree hash cannot bypass the
     embedded composition identity; and
  4. proves complete expected membership: every controlling authority/decision/policy/schema/
     generated-bundle artifact below must be pinned; and
  5. consumes the classifier's complete positive source grant and requires every present exact
     path and every regular file below its recursive roots to be pinned.  This keeps the changed-
     path law and byte inventory from drifting apart.

Exit 0 iff every check passes. This is an inventory verifier; it certifies no gate.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from triad_origin import governance  # noqa: E402
from tools import classify_milestone_pr as classifier  # noqa: E402

SOURCE_HASHES = ROOT / "docs" / "control" / "SOURCE_HASHES.sha256"

# Controlling artifacts that MUST be pinned (complete expected membership). A new controlling
# artifact that is not pinned here fails the run.
REQUIRED_MEMBERSHIP = [
    ".github/CODEOWNERS",
    ".github/workflows/ci.yml",
    "constraints/ci.txt",
    "docs/control/README.md",
    "docs/control/rc3_effective_control_bundle.json",
    "docs/control/rc3_normative_overlay.json",
    "docs/control/rc3_overlay_schema.json",
    "docs/control/rc3_effective_bundle_manifest.json",
    "docs/control/rc4_control_bundle.json",
    "docs/control/rc5_effective_consolidation.py",
    "docs/control/rc5_bundle.json",
    "docs/control/rc5_manifest.json",
    "docs/control/rc5_conflict_report.json",
    "docs/control/rc5_bundle.schema.json",
    "docs/control/formula_repair_overlay.v1.json",
    "docs/control/linkage_repair_overlay.v1.json",
    "docs/control/b00r_policy.v1.json",
    "docs/control/b00r_policy.v2.json",
    "docs/control/binding_registry.v2.json",
    "docs/control/build_ledger.json",
    "docs/control/build_ledger_overrides.json",
    "docs/control/build_ledger_review.v1.json",
    "docs/control/build_ledger_review.v2.json",
    "docs/control/closure/closure_generation_context.v1.json",
    "docs/control/closure/closure_generation_context.v1.schema.json",
    "docs/control/closure/closure_semantics.v1.schema.json",
    "docs/control/closure/closure_semantics.v1.json",
    "docs/control/closure/closure_status.v1.schema.json",
    "docs/control/closure/closure_status.v1.json",
    "docs/control/closure/closure_status_events.v1.schema.json",
    "docs/control/closure/closure_status_events.v1.json",
    "docs/control/closure/closure_task_bindings.v1.schema.json",
    "docs/control/closure/closure_task_bindings.v1.json",
    "docs/plan/04_STATUS.md",
    "docs/plan/08_BUILD_CHECKLIST.md",
    "docs/governance/B00_B07_INVALIDATION_MANIFEST.v1.json",
    "docs/governance/B00R_GENERATION_LEDGER.v1.json",
    "docs/governance/decisions/DEC-AUTHORITY-BUNDLE-002.template.json",
    "docs/governance/decisions/DEC-B00-REPAIR-002.template.json",
    "docs/governance/decisions/DEC-RECEIPT-PROFILE-002.template.json",
    "docs/governance/trust/receipt_trust_registry.g2.v1.template.json",
    "contracts/schemas/triad.evidence_receipt.v3.schema.json",
    "contracts/schemas/triad.receipt_trust_registry.v1.schema.json",
    "contracts/schemas/triad.governance_decision.v1.schema.json",
    "contracts/schemas/triad.governance_snapshot.v1.schema.json",
    "contracts/schemas/triad.evidence_manifest.v1.schema.json",
    "pyproject.toml",
    "src/triad_origin/canonical.py",
    "src/triad_origin/contracts.py",
    "src/triad_origin/governance.py",
    "tools/__init__.py",
    "tools/b00r_clean_runner.py",
    "tools/b00r_clean_runner_capture.py",
    "tools/b00r_gate.py",
    "tools/b00r_pytest_inventory.py",
    "tools/build_evidence_manifest.py",
    "tools/build_ledger.py",
    "tools/classify_milestone_pr.py",
    "tools/closure_control.py",
    "tools/collect_test_ids.py",
    "tools/e2e_audit.py",
    "tools/github_ruleset_live.py",
    "tools/test_wheel_install.py",
    "tools/validate_authority_root.py",
    "tools/validate_b00r_anchor.py",
    "tools/validate_b00r_tag_ruleset.py",
    "tools/validate_b_receipt.py",
    "tools/validate_combined_dag.py",
    "tools/validate_contract_manifest.py",
    "tools/validate_governance_snapshot.py",
    "tools/verify_b01c_entry.py",
    "tools/verify_codeowners.py",
    "tools/verify_historical_evidence.py",
    "tools/verify_manifest.py",
    "tools/verify_no_forbidden_capabilities.py",
    "tools/verify_reproducible_build.py",
    "tools/verify_source_hashes.py",
    "tests/b00r/test_b00r_ci_gates.py",
    "tests/b00r/test_b00r_clean_runner.py",
    "tests/b00r/test_b00r_clean_runner_capture.py",
    "tests/b00r/test_b00r_generation2.py",
    "tests/b00r/test_b00r_governance.py",
    "tests/b00r/test_b00r_pytest_inventory.py",
    "tests/b00r/test_github_ruleset_live.py",
    "tests/b00r/test_governance_crypto_closure.py",
    "tests/b00r/test_validate_b00r_tag_ruleset.py",
    "tests/test_b00c_control_closure.py",
    "tests/test_ci_integrity.py",
    "tests/tools/test_closure_control.py",
    "tests/tools/test_e2e_audit.py",
    "tests/tools/test_validate_b_receipt_failclosed_b01c.py",
    "tests/tools/test_verify_source_hashes.py",
]

SELF_REFERENTIAL_INVENTORY = "docs/control/SOURCE_HASHES.sha256"


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _governed_regular_file(path: pathlib.Path) -> bool:
    """Exclude interpreter caches; all other files in a recursive grant are governed."""
    return (
        path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
    )


def _required_membership(root: pathlib.Path = ROOT) -> tuple[str, ...]:
    """Return fixed controls plus every present path in the classifier's source grant."""
    required = set(REQUIRED_MEMBERSHIP)
    required.update(
        rel
        for rel in classifier.ALLOWED_SOURCE_EXACT_PATHS
        if rel != SELF_REFERENTIAL_INVENTORY and (root / rel).is_file()
    )
    for prefix in classifier.ALLOWED_SOURCE_PREFIXES:
        granted_root = root / prefix
        if granted_root.is_dir():
            required.update(
                path.relative_to(root).as_posix()
                for path in granted_root.rglob("*")
                if _governed_regular_file(path)
            )
    required.discard(SELF_REFERENTIAL_INVENTORY)
    return tuple(sorted(required))


def _verify_rc3_composition(problems: list[str]) -> None:
    manifest_path = ROOT / "docs/control/rc3_effective_bundle_manifest.json"
    if not manifest_path.exists():
        problems.append("rc3 composition manifest missing")
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checks = {
        "effective_bundle_sha256": "docs/control/rc3_effective_control_bundle.json",
        "overlay_sha256": "docs/control/rc3_normative_overlay.json",
        "overlay_schema_sha256": "docs/control/rc3_overlay_schema.json",
    }
    for field, rel in checks.items():
        declared = manifest.get(field)
        actual = _sha256(ROOT / rel)
        if declared != actual:
            problems.append(f"rc3 composition {field} mismatch: declared {str(declared)[:16]} "
                            f"!= actual {actual[:16]} ({rel})")


def main() -> int:
    if not SOURCE_HASHES.exists():
        print("FAIL: docs/control/SOURCE_HASHES.sha256 missing", file=sys.stderr)
        return 1
    try:
        pins = governance.parse_source_hashes(SOURCE_HASHES.read_text(encoding="utf-8"))
    except governance.GovernanceError as exc:
        print(f"FAIL: SOURCE_HASHES parse: {exc}", file=sys.stderr)
        return 1

    problems: list[str] = []
    for rel, digest in sorted(pins.items()):
        path = ROOT / rel
        if not path.is_file():
            problems.append(f"pinned file missing: {rel}")
            continue
        actual = _sha256(path)
        if actual != digest:
            problems.append(f"byte change vs pin: {rel} ({actual[:16]} != {digest[:16]})")

    required_membership = _required_membership(ROOT)
    for rel in required_membership:
        if rel not in pins:
            problems.append(f"controlling artifact not pinned: {rel}")

    _verify_rc3_composition(problems)

    if problems:
        for p in problems:
            print(f"FAIL: {p}", file=sys.stderr)
        return 1
    print(f"OK: {len(pins)} source hashes verified; RC3 composition manifest consistent; "
          f"{len(required_membership)} required artifacts pinned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
