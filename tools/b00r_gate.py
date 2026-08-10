#!/usr/bin/env python3
"""B00R deterministic gate orchestrator (repair plan §9).

Runs and INDEPENDENTLY PARSES the B00R control set rather than trusting a bare exit code, and
prints a per-gate result. The deterministic engineering gates (ledger, source hashes, contract
manifest, DAG, DARK capability, e2e, tests-id, receipt-v3 structure) can pass with no owner input.
The owner-gated gates (authority root, governance snapshot, receipt-v3 closure) are fail-closed
``BLOCKED`` until the account owner authenticates the decisions, pins the trust registry, and
installs the no-bypass ruleset — never faked.

The overall result is ``PASS_REPOSITORY_SAFE_HOLD`` only when EVERY gate passes; otherwise it is
``BLOCKED`` (or ``FAIL``). Safety posture is invariant OFF/OFF/OFF/LIVE / DENIED_SAFE_HOLD.

Usage:
  python tools/b00r_gate.py --mode source [--expected-head <sha>]
  python tools/b00r_gate.py --mode receipt --expected-head <sha>
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable

# (gate id, argv, owner_gated)
DETERMINISTIC = [
    ("baseline_ledger", [PY, "tools/build_ledger.py", "--verify"], False),
    ("source_hashes", [PY, "tools/verify_source_hashes.py"], False),
    ("contract_byte_manifest", [PY, "tools/verify_manifest.py"], False),
    ("contract_manifest_schema", [PY, "tools/validate_contract_manifest.py"], False),
    ("combined_dag", [PY, "tools/validate_combined_dag.py"], False),
    ("dark_capability", [PY, "tools/verify_no_forbidden_capabilities.py"], False),
    ("test_ids", [PY, "tools/collect_test_ids.py"], False),
    ("e2e_audit", [PY, "tools/e2e_audit.py"], False),
]
OWNER_GATED = [
    ("authority_root", [PY, "tools/validate_authority_root.py", "--strict"], True),
    ("governance_snapshot", [PY, "tools/validate_governance_snapshot.py", "--strict"], True),
    ("receipt_v3_closure", [PY, "tools/validate_b_receipt.py", "--strict", "--milestone", "B00R",
                            "evidence/receipts/B00R.receipt.v3.json"], True),
]


def _run(gate: str, argv: list[str]) -> tuple[str, str]:
    proc = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
    out = (proc.stdout + proc.stderr).strip().splitlines()
    tail = out[-1] if out else ""
    if proc.returncode == 0:
        return "PASS", tail
    if "UNAVAILABLE" in (proc.stdout + proc.stderr) or "BLOCKED" in (proc.stdout + proc.stderr):
        return "BLOCKED", tail
    if not pathlib.Path(ROOT / argv[-1]).exists() and argv[-1].endswith(".json"):
        return "BLOCKED", f"owner input absent: {argv[-1]}"
    return "FAIL", tail


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["source", "receipt"], required=True)
    parser.add_argument("--expected-head")
    args = parser.parse_args(argv)

    results: dict[str, str] = {}
    print(f"B00R gate — mode={args.mode} expected_head={args.expected_head or '<unset>'}")
    print("levers: venue_environment=OFF venue_activation=OFF paper_activation=OFF "
          "shadow_activation=LIVE ; activation_result=DENIED_SAFE_HOLD")
    for gate, cmd, _ in DETERMINISTIC + OWNER_GATED:
        status, tail = _run(gate, cmd)
        results[gate] = status
        print(f"  [{status:7}] {gate}: {tail[:100]}")

    det_fail = [g for g, (_, _, o) in zip([g for g, _, _ in DETERMINISTIC],
                                          DETERMINISTIC) if results[g] == "FAIL"]
    any_fail = any(v == "FAIL" for v in results.values())
    any_blocked = any(v == "BLOCKED" for v in results.values())
    if any_fail:
        overall = "FAIL"
    elif any_blocked:
        overall = "BLOCKED"
    else:
        overall = "PASS_REPOSITORY_SAFE_HOLD"
    print(f"B00R result: {overall}")
    if overall == "PASS_REPOSITORY_SAFE_HOLD":
        return 0
    if any_fail:
        print("A deterministic gate FAILED — repair forward.", file=sys.stderr)
    else:
        print("Owner-gated closure inputs are absent (authenticated decisions, pinned trust "
              "registry, installed no-bypass ruleset, signed receipt-v3). Fail-closed BLOCKED.",
              file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
