#!/usr/bin/env python3
"""Closed changed-path role classifier for a milestone PR (B00R CI-003 / NEG-017).

Classifies a set of changed paths as ``SOURCE`` or ``RECEIPT`` under a closed allowlist. A source
PR may touch anything EXCEPT the ``evidence/`` namespace; a receipt PR may touch ONLY that
namespace. A PR mixing source and evidence content FAILS regardless of test results — role is
derived from the actual diff, never from branch/title text.

Usage:
  python tools/classify_milestone_pr.py <path> [<path> ...]
  python tools/classify_milestone_pr.py --paths-file changed.txt
"""

from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from triad_origin import governance  # noqa: E402


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--paths-file")
    args = parser.parse_args(argv)
    paths = list(args.paths)
    if args.paths_file:
        text = pathlib.Path(args.paths_file).read_text(encoding="utf-8")
        paths.extend(p.strip() for p in text.splitlines() if p.strip())
    role, reason = governance.classify_changed_paths(paths)
    if role == "MIXED":
        print(f"FAIL: PR_ROLE_MIXED: {reason}", file=sys.stderr)
        return 1
    print(f"OK: PR_ROLE={role} ({reason})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
