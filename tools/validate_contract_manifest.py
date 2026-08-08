#!/usr/bin/env python3
"""Validate the committed contract-bundle descriptor against its pinned contract schema."""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import contracts  # noqa: E402

MANIFEST = ROOT / "contracts" / "manifest" / "contract_bundle.manifest.v1.json"


def main() -> int:
    try:
        event = json.loads(MANIFEST.read_text(encoding="utf-8"))
        contracts.validate(event, schema_id="triad.contract_bundle.manifest.v1")
    except (OSError, json.JSONDecodeError, contracts.ContractError) as exc:
        print(f"FAIL: contract manifest is not contract-valid: {exc}", file=sys.stderr)
        return 1
    print("OK: committed contract manifest validates against triad.contract_bundle.manifest.v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
