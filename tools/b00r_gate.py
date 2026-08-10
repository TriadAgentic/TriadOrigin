#!/usr/bin/env python3
"""B00R gate orchestrator with exact-head, reproducibility, and receipt-role enforcement.

Both modes require the exact checked-out head SHA, and ``receipt`` additionally requires the
immutable event base SHA.  The head check runs before every subordinate gate and is forwarded into
every strict owner validator.  Owner inputs remain fail-closed and are never manufactured here.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable
HEX40_RE = re.compile(r"[0-9a-f]{40}")
CANONICAL_RECEIPT = "evidence/receipts/B00R.receipt.v3.json"
CANONICAL_MANIFEST = "evidence/B00R/evidence_manifest.json"
CANONICAL_EVIDENCE_ROOT = "evidence/B00R"
CANONICAL_GOVERNANCE_SNAPSHOT = "docs/governance/rulesets/main.ruleset.provider.json"
CANONICAL_PROVIDER_RAW = "docs/governance/rulesets/main.ruleset.provider.raw.json"
CANONICAL_ANCHOR_RULESET = "evidence/B00R/tag_ruleset.provider.json"


@dataclass(frozen=True)
class Gate:
    gate_id: str
    argv: tuple[str, ...]
    owner_gated: bool = False
    env: dict[str, str] = field(default_factory=dict)


COMMON_GATES = (
    Gate("baseline_ledger", (PY, "tools/build_ledger.py", "--verify")),
    Gate("source_hashes", (PY, "tools/verify_source_hashes.py")),
    Gate("contract_byte_manifest", (PY, "tools/verify_manifest.py")),
    Gate("contract_manifest_schema", (PY, "tools/validate_contract_manifest.py")),
    Gate("combined_dag", (PY, "tools/validate_combined_dag.py")),
    Gate("historical_evidence", (PY, "tools/verify_historical_evidence.py")),
    Gate(
        "tests_seed0",
        (PY, "-m", "pytest", "-p", "no:cacheprovider"),
        env={"PYTHONHASHSEED": "0"},
    ),
    Gate(
        "tests_seed1",
        (PY, "-m", "pytest", "-p", "no:cacheprovider"),
        env={"PYTHONHASHSEED": "1"},
    ),
    Gate("test_ids", (PY, "tools/collect_test_ids.py")),
    Gate("reproducible_build", (PY, "tools/verify_reproducible_build.py")),
    Gate("wheel_install", (PY, "tools/test_wheel_install.py")),
    Gate("dark_capability", (PY, "tools/verify_no_forbidden_capabilities.py")),
    Gate("e2e_audit", (PY, "tools/e2e_audit.py")),
)
CODEOWNERS_GATES = (
    Gate("codeowners_identity", (PY, "tools/verify_codeowners.py"), owner_gated=True),
)


class HeadIdentityError(ValueError):
    """The checked-out commit is not the exact event head requested by the caller."""


def _git_head(root: pathlib.Path = ROOT) -> str:
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("GIT_") or name == "GIT_CONFIG_NOSYSTEM"
    }
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    proc = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if proc.returncode:
        raise HeadIdentityError(f"GIT_HEAD_UNAVAILABLE: {proc.stderr.strip()}")
    return proc.stdout.strip()


def verify_expected_head(expected: str, root: pathlib.Path = ROOT) -> str:
    """Return the current head only when it exactly equals canonical ``expected``."""
    if HEX40_RE.fullmatch(expected or "") is None:
        raise HeadIdentityError(f"EXPECTED_HEAD_NOT_CANONICAL_HEX40: {expected!r}")
    if expected == "0" * 40:
        raise HeadIdentityError("EXPECTED_HEAD_ALL_ZERO_UNAVAILABLE")
    actual = _git_head(root)
    if actual != expected:
        raise HeadIdentityError(f"EXPECTED_HEAD_MISMATCH: actual={actual} expected={expected}")
    return actual


def _run(gate: Gate) -> tuple[str, str]:
    env = dict(os.environ)
    env.update(gate.env)
    # This marker prevents a regression test from recursively launching a complete gate while the
    # gate's own dual-seed pytest runs are in progress.
    env["TRIAD_B00R_GATE_RUNNING"] = "1"
    proc = subprocess.run(
        list(gate.argv), cwd=ROOT, env=env, capture_output=True, text=True, check=False
    )
    combined = proc.stdout + proc.stderr
    lines = combined.strip().splitlines()
    tail = lines[-1] if lines else ""
    if proc.returncode == 0:
        return "PASS", tail
    if gate.owner_gated and (
        "UNAVAILABLE" in combined
        or "BLOCKED" in combined
        or "No such file" in combined
        or "not readable" in combined
        or "owner input absent" in combined
    ):
        return "BLOCKED", tail
    return "FAIL", tail


def _receipt_gates(args: argparse.Namespace) -> tuple[Gate, ...]:
    return (
        Gate(
            "receipt_pr_role",
            (
                PY,
                "tools/classify_milestone_pr.py",
                "--base-sha",
                args.base_sha,
                "--head-sha",
                args.expected_head,
                "--repo",
                str(ROOT),
            ),
        ),
        Gate(
            "closed_evidence_manifest",
            (
                PY,
                "tools/build_evidence_manifest.py",
                "--verify",
                args.manifest,
                "--root",
                ".",
                "--closed-root",
                CANONICAL_EVIDENCE_ROOT,
                "--require-tracked",
            ),
        ),
    )


def _optional_pair(flag: str, value: str | None) -> tuple[str, ...]:
    return (flag, value) if value else ()


def _owner_gates(args: argparse.Namespace) -> tuple[Gate, ...]:
    """Build strict owner gates without ever running receipt closure in SOURCE mode."""
    authority_command = (
        PY,
        "tools/validate_authority_root.py",
        "--strict",
        "--now-us",
        str(args.now_us),
        "--expected-head",
        args.expected_head,
        "--git-root",
        str(ROOT),
        *_optional_pair("--pins", args.pins),
    )
    governance_command = (
        PY,
        "tools/validate_governance_snapshot.py",
        "--strict",
        "--snapshot",
        args.governance_snapshot,
        "--provider-raw",
        args.provider_raw,
        "--now-us",
        str(args.now_us),
        "--expected-head",
        args.expected_head,
        "--git-root",
        str(ROOT),
        *_optional_pair("--provider-pin", args.provider_pin),
    )
    gates: tuple[Gate, ...] = (
        Gate("authority_root", authority_command, owner_gated=True),
        Gate("governance_snapshot", governance_command, owner_gated=True),
    )
    if args.mode == "source":
        return gates

    receipt_command = (
        PY,
        "tools/validate_b_receipt.py",
        "--strict",
        "--milestone",
        "B00R",
        "--now-us",
        str(args.now_us),
        "--manifest",
        args.manifest,
        "--git-root",
        str(ROOT),
        "--expected-head",
        args.expected_head,
        "--governance-snapshot",
        args.governance_snapshot,
        "--provider-raw",
        args.provider_raw,
        *_optional_pair("--pins", args.pins),
        *_optional_pair("--provider-pin", args.provider_pin),
        args.receipt,
    )
    anchor_command = (
        PY,
        "tools/validate_b00r_anchor.py",
        "--expected-head",
        args.expected_head,
        "--receipt",
        args.receipt,
        "--ruleset",
        args.anchor_ruleset,
        *_optional_pair("--ruleset-pin", args.anchor_ruleset_pin),
    )
    gates += (
        Gate("receipt_v3_closure", receipt_command, owner_gated=True),
        Gate("receipt_anchor", anchor_command, owner_gated=True),
    )
    return gates


def overall_result(mode: str, results: dict[str, str]) -> str:
    """Compute terminal state; SOURCE diagnostics can never close B00R."""
    if any(value == "FAIL" for value in results.values()):
        return "FAIL"
    if mode == "source":
        return "BLOCKED"
    if any(value == "BLOCKED" for value in results.values()):
        return "BLOCKED"
    return "PASS_REPOSITORY_SAFE_HOLD"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["source", "receipt"], required=True)
    parser.add_argument("--expected-head")
    parser.add_argument("--base-sha")
    parser.add_argument("--now-us", type=int, required=True,
                        help="trusted current Unix time in microseconds")
    parser.add_argument("--pins",
                        help="optional out-of-repository JSON containing authority pins")
    parser.add_argument("--receipt", default=CANONICAL_RECEIPT)
    parser.add_argument("--manifest", default=CANONICAL_MANIFEST)
    parser.add_argument("--governance-snapshot", default=CANONICAL_GOVERNANCE_SNAPSHOT)
    parser.add_argument("--provider-raw", default=CANONICAL_PROVIDER_RAW)
    parser.add_argument("--provider-pin",
                        help="external main-ruleset SHA-256; protected env is also accepted")
    parser.add_argument("--anchor-ruleset", default=CANONICAL_ANCHOR_RULESET)
    parser.add_argument("--anchor-ruleset-pin",
                        help="external tag-ruleset SHA-256; protected env is also accepted")
    args = parser.parse_args(argv)

    if not args.expected_head:
        parser.error("both source and receipt modes require --expected-head")
    if args.mode == "receipt" and not args.base_sha:
        parser.error("receipt mode requires --base-sha")
    if args.mode == "source" and args.base_sha:
        parser.error("source mode does not accept --base-sha")
    if args.mode == "receipt" and (
        HEX40_RE.fullmatch(args.base_sha or "") is None or args.base_sha == "0" * 40
    ):
        parser.error("receipt --base-sha must be a nonzero canonical 40-hex commit identity")
    if args.now_us <= 0:
        parser.error("--now-us must be a positive Unix timestamp in microseconds")
    if args.receipt != CANONICAL_RECEIPT:
        parser.error(f"receipt path must be exactly {CANONICAL_RECEIPT}")
    if args.manifest != CANONICAL_MANIFEST:
        parser.error(f"manifest path must be exactly {CANONICAL_MANIFEST}")
    if args.governance_snapshot != CANONICAL_GOVERNANCE_SNAPSHOT:
        parser.error(
            f"governance snapshot path must be exactly {CANONICAL_GOVERNANCE_SNAPSHOT}"
        )
    if args.provider_raw != CANONICAL_PROVIDER_RAW:
        parser.error(f"provider raw path must be exactly {CANONICAL_PROVIDER_RAW}")
    if args.anchor_ruleset != CANONICAL_ANCHOR_RULESET:
        parser.error(f"anchor ruleset path must be exactly {CANONICAL_ANCHOR_RULESET}")

    print(f"B00R gate — mode={args.mode} expected_head={args.expected_head}")
    print("levers: venue_environment=OFF venue_activation=OFF paper_activation=OFF "
          "shadow_activation=LIVE ; activation_result=DENIED_SAFE_HOLD")

    # Exact identity is a precondition, not merely another row that later gates can obscure.
    if args.expected_head:
        try:
            actual = verify_expected_head(args.expected_head)
        except HeadIdentityError as exc:
            print(f"  [FAIL   ] exact_head: {exc}", file=sys.stderr)
            print("B00R result: FAIL")
            return 1
        print(f"  [PASS   ] exact_head: {actual}")

    gates: tuple[Gate, ...] = COMMON_GATES
    if args.mode == "receipt":
        gates += _receipt_gates(args)
    gates += CODEOWNERS_GATES
    gates += _owner_gates(args)

    results: dict[str, str] = {}
    for gate in gates:
        status, tail = _run(gate)
        results[gate.gate_id] = status
        print(f"  [{status:7}] {gate.gate_id}: {tail[:160]}")

    overall = overall_result(args.mode, results)
    print(f"B00R result: {overall}")
    if overall == "PASS_REPOSITORY_SAFE_HOLD":
        return 0
    if overall == "FAIL":
        print("A mandatory engineering or closure gate FAILED — repair forward.", file=sys.stderr)
    else:
        if args.mode == "source":
            print("SOURCE mode is engineering diagnostics only and can never close B00R. "
                  "Fail-closed BLOCKED.", file=sys.stderr)
        else:
            print("Owner-gated closure input is absent or unavailable. Fail-closed BLOCKED.",
                  file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
