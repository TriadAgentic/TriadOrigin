#!/usr/bin/env python3
"""Validate a milestone receipt.

Two modes:

* **Legacy self-integrity** (default, positional path). Historical B-series receipts are
  ``triad.evidence_receipt.v2`` events whose ``signature`` is the SHA-256 of the canonical payload
  with the signature blanked — a deterministic self-integrity seal, **not** an authorization
  signature. This mode confirms the document is internally consistent and its filename matches its
  milestone. It is preserved for inspecting historical evidence; it is **not** a closure
  authentication (B00R-D11 / RCP-001): a v2 self-hash can never return
  ``PASS_REPOSITORY_SAFE_HOLD``.

* **Receipt-v3 strict** (``--strict --milestone <M> [--trust <registry.json>]``). The B00R
  forward-repair authenticated path. It validates a ``triad.evidence_receipt.v3`` document under
  :func:`triad_origin.governance.validate_receipt_v3`: canonical hex digests, closed nonempty
  scope, root/non-root variant, chronology, evidence, and a profile-selected external-signature
  threshold under an externally pinned trust registry. Absent owner input (no trust registry, no
  external signatures, no crypto library) is fail-closed ``BLOCKED`` — never PASS.

Usage:
  python tools/validate_b_receipt.py evidence/receipts/B00.json
  python tools/validate_b_receipt.py --strict --milestone B00R --trust <registry.json> <receipt.json>
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import contracts  # noqa: E402
from triad_origin import governance  # noqa: E402
from triad_origin.canonical import canonical_json, sha256_hex  # noqa: E402


def compute_signature(payload: dict) -> str:
    unsigned = dict(payload)
    unsigned["signature"] = ""
    return sha256_hex(canonical_json(unsigned))


def _ed25519_verify_fn():
    """Return an Ed25519 ``verify_fn(pubkey_hex, msg, sig_hex) -> bool`` or ``None`` if no crypto
    library is installed. Crypto lives only here (the tool layer); ``src/triad_origin`` stays DARK.
    """
    try:
        from nacl.signing import VerifyKey  # type: ignore
        from nacl.exceptions import BadSignatureError  # type: ignore

        def _v(pubkey_hex: str, msg: bytes, sig_hex: str) -> bool:
            try:
                VerifyKey(bytes.fromhex(pubkey_hex)).verify(msg, bytes.fromhex(sig_hex))
                return True
            except (BadSignatureError, ValueError):
                return False
        return _v
    except ModuleNotFoundError:
        pass
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey  # type: ignore

        def _v(pubkey_hex: str, msg: bytes, sig_hex: str) -> bool:
            try:
                Ed25519PublicKey.from_public_bytes(
                    bytes.fromhex(pubkey_hex)).verify(bytes.fromhex(sig_hex), msg)
                return True
            except Exception:
                return False
        return _v
    except ModuleNotFoundError:
        return None


def _legacy(path: pathlib.Path) -> int:
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
    print(f"OK: milestone receipt {milestone} self-integrity valid ({payload['result']}) "
          "— LEGACY v2, not a closure authentication (see B00R receipt-v3 for PASS)")
    return 0


def _strict(path: pathlib.Path, milestone: str, trust_path: pathlib.Path | None) -> int:
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: receipt not readable JSON: {exc}", file=sys.stderr)
        return 1
    trust = None
    if trust_path is not None:
        try:
            registry = json.loads(trust_path.read_text(encoding="utf-8"))
            trust = governance.validate_trust_registry(registry)
        except (OSError, json.JSONDecodeError, governance.GovernanceError) as exc:
            print(f"FAIL: trust registry invalid: {exc}", file=sys.stderr)
            return 1
    result, reason = governance.validate_receipt_v3(
        receipt, milestone=milestone, trust=trust, verify_fn=_ed25519_verify_fn())
    if result == governance.RESULT_PASS:
        print(f"OK: {milestone} receipt-v3 {result}")
        return 0
    stream = sys.stderr if result == "FAIL" else sys.stdout
    print(f"{result}: {milestone} receipt-v3 not a closure PASS: {reason}", file=stream)
    # BLOCKED/UNAVAILABLE (owner input absent) is a fail-closed non-PASS, exit 1; only PASS exits 0.
    return 1


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Validate a milestone receipt.")
    parser.add_argument("receipt", help="path to the receipt JSON")
    parser.add_argument("--strict", action="store_true",
                        help="receipt-v3 authenticated closure validation")
    parser.add_argument("--milestone", help="milestone identity (required with --strict)")
    parser.add_argument("--trust", help="path to the externally pinned trust registry (v3)")
    args = parser.parse_args(argv)
    path = pathlib.Path(args.receipt)
    if args.strict:
        if not args.milestone:
            print("FAIL: --strict requires --milestone", file=sys.stderr)
            return 2
        trust_path = pathlib.Path(args.trust) if args.trust else None
        return _strict(path, args.milestone, trust_path)
    return _legacy(path)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
