#!/usr/bin/env python3
"""Emit the CLOSED ratified DECISION-RECEIPT-PROFILE-001 ceremony object.

This draft-builder writes the exact receipt-profile decision object the frozen audit runner
(``audit_package/triad_origin_b01_b10_audit.py``, ``SUPPORTED_RECEIPT_PROFILE_DECISION``)
ratifies.  The content is CLOSED: every key and value below is copied verbatim from the frozen
runner and the differential test asserts exact-dict equality against the runner's constant.

BYTE LAW: the external ceremony PIN is the SHA-256 over the FILE BYTES, not over any
re-canonicalized form.  The bytes are therefore ceremony-fixed as exactly
``json.dumps(value, sort_keys=True, indent=2) + "\\n"`` encoded UTF-8.  Changing the
serialization (key order, indent, trailing newline, encoding) is a pin-breaking act.

TREE-MUTATION LAW: by default this tool refuses to write inside its own repository root
(the parent of the ``tools/`` directory containing this script); pass ``--allow-in-repo``
only for a deliberate, ceremony-recorded in-repo write.  The tool is fully self-contained:
it imports ONLY the Python standard library and never imports sibling repository modules,
so invoking it as ``python tools/build_profile_decision.py`` mutates nothing in the tree.

No network code, no credentials, no signing.  Exit codes: 0 success, 2 invalid invocation
or policy refusal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from typing import Any

TOOL_NAME = "build_profile_decision"
TOOL_VERSION = "1.0.0"

# Constants below are copied VERBATIM from the frozen runner
# audit_package/triad_origin_b01_b10_audit.py (v1.2.0):
#   EXPECTED_REPOSITORY, RECEIPT_PAYLOAD_TYPE, MAX_RECEIPT_TTL_US,
#   REPOSITORY_FUTURE_TOLERANCE_US, SUPPORTED_RECEIPT_PROFILE_DECISION.
EXPECTED_REPOSITORY = "triadagentic/triadorigin"
RECEIPT_PAYLOAD_TYPE = "application/vnd.triad.evidence-receipt.v3+json"
REPOSITORY_FUTURE_TOLERANCE_US = 0
MAX_RECEIPT_TTL_US = 2_592_000_000_000

RECEIPT_PROFILE_DECISION: dict[str, Any] = {
    "schema": "triad.receipt_profile_decision.v1",
    "decision_id": "DECISION-RECEIPT-PROFILE-001",
    "status": "RATIFIED",
    "repository": EXPECTED_REPOSITORY,
    "canonicalization": "RFC8785_JCS",
    "payload_type": RECEIPT_PAYLOAD_TYPE,
    "signature_algorithm": "Ed25519",
    "required_signer_roles": ["PRODUCER", "COUNTERSIGNER"],
    "minimum_distinct_signers": 2,
    "max_receipt_ttl_us": MAX_RECEIPT_TTL_US,
    "repository_provider_future_tolerance_us": REPOSITORY_FUTURE_TOLERANCE_US,
}


def deterministic_json_bytes(value: Any) -> bytes:
    """The ceremony-fixed file-byte serialization (see BYTE LAW in the module docstring)."""
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")


def repo_root_of_tool() -> pathlib.Path:
    """The repository root this tool lives in: the parent of its ``tools/`` directory."""
    return pathlib.Path(__file__).resolve().parent.parent


def refuse_out_inside_repo(out_path: pathlib.Path, allow_in_repo: bool) -> str | None:
    """Return a named refusal when ``out_path`` resolves inside the repository root."""
    if allow_in_repo:
        return None
    resolved = out_path.resolve()
    root = repo_root_of_tool()
    if resolved == root or root in resolved.parents:
        return (
            f"REFUSED OUT_PATH_INSIDE_REPOSITORY: {resolved} is inside repository root {root}; "
            "the tree-mutation law forbids writing into the repository "
            "(pass --allow-in-repo only for a deliberate ceremony-recorded in-repo write)"
        )
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Emit the closed ratified DECISION-RECEIPT-PROFILE-001 object.",
    )
    parser.add_argument("--out", required=True, help="output file path (outside the repository)")
    parser.add_argument(
        "--allow-in-repo", action="store_true",
        help="permit writing inside the repository root (tree-mutation law override)")
    args = parser.parse_args(argv)

    out_path = pathlib.Path(args.out)
    refusal = refuse_out_inside_repo(out_path, args.allow_in_repo)
    if refusal is not None:
        print(refusal, file=sys.stderr)
        return 2

    payload_bytes = deterministic_json_bytes(RECEIPT_PROFILE_DECISION)
    try:
        out_path.resolve().parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(payload_bytes)
    except OSError as exc:
        print(f"REFUSED OUT_PATH_UNWRITABLE: {exc}", file=sys.stderr)
        return 2
    print(hashlib.sha256(payload_bytes).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
