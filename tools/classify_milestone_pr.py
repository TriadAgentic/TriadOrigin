#!/usr/bin/env python3
"""Fail-closed B00R changed-path role classifier.

CI classification is derived from two immutable Git commit SHAs, never a branch name or a
best-effort fallback.  A SOURCE change may touch only the positive B00R G2 governance/C0 path
grant and may never touch ``evidence/**``.  A B00R RECEIPT change must be append-only and contain
exactly the canonical bare receipt
``evidence/receipts/B00R.g2.receipt.v3.json``, and may otherwise add files only below
``evidence/B00R_G2/**``.  Generation-1/historical receipts, deletions, renames, mixed
source/evidence changes, and
the formerly advertised-but-unimplemented ``*.dsse.json`` envelope all fail closed.

Legacy positional/``--paths-file`` input remains for local falsification tests.  CI must use
``--base-sha`` and ``--head-sha`` so status and ancestry are authenticated by Git.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

HEX40_RE = re.compile(r"[0-9a-f]{40}")
EXPECTED_MILESTONE = "B00R"
EXPECTED_RECEIPT = "evidence/receipts/B00R.g2.receipt.v3.json"
EXPECTED_MANIFEST = "evidence/B00R_G2/evidence_manifest.json"
RECEIPT_EVIDENCE_PREFIX = "evidence/B00R_G2/"
HISTORICAL_RECEIPTS = frozenset(
    f"evidence/receipts/{name}.json"
    for name in ("R00", "B00", "B00C", "B01", "B01R", "B02", "B03", "B04", "B05", "B06", "B07")
)
HISTORICAL_RECEIPTS = HISTORICAL_RECEIPTS | {
    "evidence/receipts/B00R.receipt.v3.json",
}
ALLOWED_RECEIPT_STATUSES = frozenset({"A"})

# B00R G2 is a governance/evidence-root repair, not a generic source milestone.  Keep this a
# positive list: a newly introduced production, contract, formula, binding, runtime, deployment,
# adapter, or venue path is out of scope until a later milestone explicitly owns it.  The C0
# namespace and B00R test namespace are the only prefix grants; executable and package paths are
# always named exactly.
ALLOWED_SOURCE_EXACT_PATHS = frozenset({
    ".github/workflows/ci.yml",
    "CLAUDE.md",
    "README.md",
    "docs/control/SOURCE_HASHES.sha256",
    "docs/control/b00r_policy.v2.json",
    "docs/governance/B00R_EXTERNAL_AUTHORITY_AND_CLEAN_RUNNER_HANDOFF.md",
    "docs/governance/B00R_GENERATION_LEDGER.v1.json",
    "docs/governance/README.md",
    "docs/governance/decisions/DEC-AUTHORITY-BUNDLE-002.json",
    "docs/governance/decisions/DEC-AUTHORITY-BUNDLE-002.template.json",
    "docs/governance/decisions/DEC-B00-REPAIR-002.json",
    "docs/governance/decisions/DEC-B00-REPAIR-002.template.json",
    "docs/governance/decisions/DEC-RECEIPT-PROFILE-002.json",
    "docs/governance/decisions/DEC-RECEIPT-PROFILE-002.template.json",
    "docs/governance/rulesets/main.ruleset.provider.json",
    "docs/governance/rulesets/main.ruleset.provider.raw.json",
    "docs/governance/rulesets/main.ruleset.provider.template.json",
    "docs/governance/trust/receipt_trust_registry.g2.v1.json",
    "docs/governance/trust/receipt_trust_registry.g2.v1.template.json",
    "docs/plan/04_STATUS.md",
    "docs/plan/08_BUILD_CHECKLIST.md",
    "docs/plan/09_OPEN_QUESTIONS.md",
    "docs/plan/README.md",
    "docs/plan/closure/TRIAD_B00_BN_CLOSURE_MASTER_2026-08-11.md",
    "docs/plan/closure/TRIAD_B00_BN_CLOSURE_MARATHON_LEDGER_2026-08-11.md",
    "docs/repair/B01C_ACCEPTANCE_PROFILE.v1.json",
    "docs/repair/B01C_ENTRY_GATE.md",
    "src/triad_origin/governance.py",
    "tests/contracts/test_promotion_b01c.py",
    "tests/test_ci_integrity.py",
    "tests/test_wheel_distribution.py",
    "tests/tools/test_acceptance_profile_b01c.py",
    "tests/tools/test_closure_control.py",
    "tests/tools/test_validate_b_receipt_failclosed_b01c.py",
    "tests/tools/test_verify_b01c_entry.py",
    "tools/b00r_clean_runner.py",
    "tools/b00r_clean_runner_capture.py",
    "tools/b00r_gate.py",
    "tools/b00r_pytest_inventory.py",
    "tools/build_evidence_manifest.py",
    "tools/classify_milestone_pr.py",
    "tools/closure_control.py",
    "tools/collect_test_ids.py",
    "tools/e2e_audit.py",
    "tools/gen_acceptance_profile.py",
    "tools/github_ruleset_live.py",
    "tools/test_wheel_install.py",
    "tools/validate_authority_root.py",
    "tools/validate_b00r_anchor.py",
    "tools/validate_b00r_tag_ruleset.py",
    "tools/validate_b_receipt.py",
    "tools/validate_governance_snapshot.py",
    "tools/verify_b01c_entry.py",
    "tools/verify_codeowners.py",
    "tools/verify_source_hashes.py",
})
ALLOWED_SOURCE_PREFIXES = (
    "docs/control/closure/",
    "tests/b00r/",
)


class ClassificationError(ValueError):
    """A changed-path set cannot be assigned a safe milestone role."""


@dataclass(frozen=True)
class Change:
    status: str
    path: str


@dataclass(frozen=True)
class Classification:
    role: str
    reason: str
    milestone: str = ""
    receipt_path: str = ""
    manifest_path: str = ""


def _safe_path(path: str) -> bool:
    if not isinstance(path, str) or not path or path.startswith("/") or "\\" in path:
        return False
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in path):
        return False
    parts = path.split("/")
    return all(part not in ("", ".", "..") for part in parts)


def source_path_allowed(path: str) -> bool:
    """Return whether one path belongs to the frozen B00R G2 SOURCE domain."""
    return (
        path in ALLOWED_SOURCE_EXACT_PATHS
        or any(path.startswith(prefix) for prefix in ALLOWED_SOURCE_PREFIXES)
    )


def classify_changes(changes: list[Change]) -> Classification:
    """Classify an authenticated Git change set under the closed B00R role law."""
    if not changes:
        raise ClassificationError("PR_ROLE_EMPTY: no changed paths")

    seen: set[str] = set()
    for change in changes:
        if not _safe_path(change.path):
            raise ClassificationError(f"PR_PATH_UNSAFE: {change.path!r}")
        if change.path in seen:
            raise ClassificationError(f"PR_PATH_DUPLICATE: {change.path}")
        seen.add(change.path)

    evidence = [change for change in changes if change.path.startswith("evidence/")]
    source = [change for change in changes if not change.path.startswith("evidence/")]
    if evidence and source:
        raise ClassificationError(
            f"PR_ROLE_MIXED: source+receipt in one change: "
            f"{[c.path for c in source[:2]]} & {[c.path for c in evidence[:2]]}"
        )
    if source:
        outside = sorted(
            f"{change.status}:{change.path}"
            for change in source
            if not source_path_allowed(change.path)
        )
        if outside:
            raise ClassificationError(f"SOURCE_PATH_OUT_OF_SCOPE: {outside}")
        return Classification("SOURCE", f"{len(source)} source paths")

    # Evidence-only changes are not automatically receipts.  They must satisfy the complete,
    # append-only B00R receipt shape below.
    historical = sorted(change.path for change in evidence if change.path in HISTORICAL_RECEIPTS)
    if historical:
        raise ClassificationError(f"HISTORICAL_EVIDENCE_IMMUTABLE: {historical}")
    dsse = sorted(change.path for change in evidence if change.path.endswith(".dsse.json"))
    if dsse:
        raise ClassificationError(
            f"UNSUPPORTED_DSSE_ENVELOPE: use {EXPECTED_RECEIPT}; found {dsse}"
        )
    bad_status = sorted(
        f"{change.status}:{change.path}"
        for change in evidence
        if change.status not in ALLOWED_RECEIPT_STATUSES
    )
    if bad_status:
        raise ClassificationError(f"RECEIPT_NOT_APPEND_ONLY: {bad_status}")

    receipt_changes = [change for change in evidence if change.path == EXPECTED_RECEIPT]
    other_receipt_paths = sorted(
        change.path
        for change in evidence
        if change.path.startswith("evidence/receipts/") and change.path != EXPECTED_RECEIPT
    )
    if other_receipt_paths:
        raise ClassificationError(f"UNEXPECTED_RECEIPT_PATH: {other_receipt_paths}")
    if len(receipt_changes) != 1:
        raise ClassificationError(
            f"EXACTLY_ONE_B00R_RECEIPT_REQUIRED: found {len(receipt_changes)}"
        )
    outside = sorted(
        change.path
        for change in evidence
        if change.path != EXPECTED_RECEIPT
        and not change.path.startswith(RECEIPT_EVIDENCE_PREFIX)
    )
    if outside:
        raise ClassificationError(f"CROSS_MILESTONE_EVIDENCE: {outside}")

    return Classification(
        "RECEIPT",
        f"exactly one {EXPECTED_MILESTONE} receipt plus {len(evidence) - 1} evidence paths",
        milestone=EXPECTED_MILESTONE,
        receipt_path=EXPECTED_RECEIPT,
        manifest_path=EXPECTED_MANIFEST,
    )


def _git(repo: pathlib.Path, *args: str) -> bytes:
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("GIT_") or name == "GIT_CONFIG_NOSYSTEM"
    }
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, check=False, env=env
    )
    if proc.returncode:
        detail = proc.stderr.decode("utf-8", errors="replace").strip()
        raise ClassificationError(f"GIT_COMMAND_FAILED: git {' '.join(args)}: {detail}")
    return proc.stdout


def _require_commit(repo: pathlib.Path, value: str, label: str) -> str:
    if HEX40_RE.fullmatch(value or "") is None:
        raise ClassificationError(f"{label}_NOT_CANONICAL_HEX40: {value!r}")
    if value == "0" * 40:
        raise ClassificationError(f"{label}_ALL_ZERO_UNAVAILABLE")
    resolved = _git(repo, "rev-parse", "--verify", f"{value}^{{commit}}").decode().strip()
    if resolved != value:
        raise ClassificationError(f"{label}_MOVED: expected {value}, resolved {resolved}")
    return resolved


def changes_from_git(repo: pathlib.Path, base_sha: str, head_sha: str) -> list[Change]:
    """Read a NUL-delimited, no-rename diff from the exact base/head commit identities."""
    base = _require_commit(repo, base_sha, "BASE_SHA")
    head = _require_commit(repo, head_sha, "HEAD_SHA")
    checkout = _git(repo, "rev-parse", "HEAD").decode().strip()
    if checkout != head:
        raise ClassificationError(f"CHECKOUT_HEAD_MISMATCH: {checkout}!={head}")
    merge_base = _git(repo, "merge-base", base, head).decode().strip()
    if HEX40_RE.fullmatch(merge_base) is None:
        raise ClassificationError(f"MERGE_BASE_INVALID: {merge_base!r}")
    raw = _git(repo, "diff", "--name-status", "--no-renames", "-z", merge_base, head, "--")
    fields = raw.split(b"\0")
    if fields and fields[-1] == b"":
        fields.pop()
    if len(fields) % 2:
        raise ClassificationError("GIT_DIFF_MALFORMED: odd NUL-delimited field count")
    changes: list[Change] = []
    for i in range(0, len(fields), 2):
        try:
            status = fields[i].decode("ascii")
            path = fields[i + 1].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ClassificationError(f"GIT_DIFF_NON_UTF8: {exc}") from exc
        if not re.fullmatch(r"[A-Z]", status):
            raise ClassificationError(f"GIT_DIFF_STATUS_UNSUPPORTED: {status!r}")
        changes.append(Change(status, path))
    return changes


def _write_github_output(path: pathlib.Path, result: Classification) -> None:
    values = {
        "role": result.role,
        "milestone": result.milestone,
        "receipt_path": result.receipt_path,
        "manifest_path": result.manifest_path,
    }
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        for key, value in values.items():
            if "\n" in value or "\r" in value:
                raise ClassificationError(f"GITHUB_OUTPUT_UNSAFE: {key}")
            fh.write(f"{key}={value}\n")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--paths-file")
    parser.add_argument("--base-sha")
    parser.add_argument("--head-sha")
    parser.add_argument("--repo", default=str(ROOT))
    parser.add_argument("--github-output")
    args = parser.parse_args(argv)

    git_mode = args.base_sha is not None or args.head_sha is not None
    if git_mode and (not args.base_sha or not args.head_sha):
        parser.error("--base-sha and --head-sha are required together")
    if git_mode and (args.paths or args.paths_file):
        parser.error("Git SHA mode cannot be mixed with positional/--paths-file input")

    try:
        if git_mode:
            changes = changes_from_git(pathlib.Path(args.repo), args.base_sha, args.head_sha)
        else:
            paths = list(args.paths)
            if args.paths_file:
                text = pathlib.Path(args.paths_file).read_text(encoding="utf-8")
                paths.extend(line.strip() for line in text.splitlines() if line.strip())
            changes = [Change("M", path) for path in paths]
        result = classify_changes(changes)
        if args.github_output:
            _write_github_output(pathlib.Path(args.github_output), result)
    except (ClassificationError, OSError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print(f"OK: PR_ROLE={result.role} ({result.reason})")
    if result.receipt_path:
        print(f"OK: MILESTONE={result.milestone} RECEIPT_PATH={result.receipt_path} "
              f"MANIFEST_PATH={result.manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
