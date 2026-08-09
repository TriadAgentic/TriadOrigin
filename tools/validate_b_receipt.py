#!/usr/bin/env python3
"""Validate a B-series milestone receipt (evidence/receipts/B*.json).

The B-series receipt is a ``triad.evidence_receipt.v2`` event whose payload scope names the
milestone; its PASS conditionals (nonempty scope/evidence, valid validity window,
builder != reviewer, signature) are the RC3 receipt-v2 law enforced by the contract's semantic
validator. This validator additionally checks:

  * the file name matches ``payload.scope.milestone``;
  * the signature is the SHA-256 of the canonical payload with the signature field blanked
    (a deterministic self-integrity seal — not an authorization signature; GOV-level
    countersigning remains an operator act, tracked in the open-questions register).

Usage: python tools/validate_b_receipt.py evidence/receipts/B00.json
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import contracts  # noqa: E402
from triad_origin.canonical import canonical_json, sha256_hex  # noqa: E402


def compute_signature(payload: dict) -> str:
    unsigned = dict(payload)
    unsigned["signature"] = ""
    return sha256_hex(canonical_json(unsigned))


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: validate_b_receipt.py <receipt.json>", file=sys.stderr)
        return 2
    path = pathlib.Path(argv[0])
    try:
        event = json.loads(path.read_text(encoding="utf-8"))
        contracts.validate(event, schema_id="triad.evidence_receipt.v2")
    except (OSError, json.JSONDecodeError, contracts.ContractError) as exc:
        print(f"FAIL: receipt is not contract-valid: {exc}", file=sys.stderr)
        return 1
    payload = event["payload"]
    milestone = payload.get("scope", {}).get("milestone")
    if path.stem != milestone:
        print(f"FAIL: receipt file {path.name} names milestone {milestone!r}", file=sys.stderr)
        return 1
    expected = compute_signature(payload)
    if payload.get("signature") != expected:
        print(f"FAIL: receipt self-integrity signature mismatch (expected {expected[:16]}...)",
              file=sys.stderr)
        return 1
    print(f"OK: milestone receipt {milestone} valid ({payload['result']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
