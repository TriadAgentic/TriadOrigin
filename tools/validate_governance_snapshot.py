#!/usr/bin/env python3
"""Verify a provider governance snapshot proving no-bypass ``main`` controls (B00R GOV-* / NEG-016).

An authenticated provider snapshot must prove: pull requests required, exact required status
context ``CI / test-and-verify`` with strict enforcement, at least one independent approval, stale
reviews dismissed, conversations resolved, force-push and branch deletion blocked, no bypass actor,
and an effective time. An unauthenticated template (``authenticated: false``) is fail-closed
``UNAVAILABLE`` — provider evidence must be captured from the GitHub API, never hand-written.

Usage:
  python tools/validate_governance_snapshot.py --strict [--snapshot PATH]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from triad_origin import governance  # noqa: E402

DEFAULT = ROOT / "docs" / "governance" / "rulesets" / "main.ruleset.provider.json"
TEMPLATE = ROOT / "docs" / "governance" / "rulesets" / "main.ruleset.provider.template.json"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--snapshot")
    args = parser.parse_args(argv)
    path = pathlib.Path(args.snapshot) if args.snapshot else (
        DEFAULT if DEFAULT.exists() else TEMPLATE)
    if not path.exists():
        print("FAIL: no governance snapshot file", file=sys.stderr)
        return 1
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"FAIL: snapshot not JSON: {exc}", file=sys.stderr)
        return 1
    result, reason = governance.validate_governance_snapshot(doc)
    if result == "PASS":
        print(f"OK: governance snapshot proves no-bypass main controls ({path.name})")
        return 0
    stream = sys.stderr if result == "FAIL" else sys.stdout
    print(f"{result}: {reason} ({path.name})", file=stream)
    return 1 if args.strict else (0 if result == "UNAVAILABLE" else 1)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
