#!/usr/bin/env python3
"""Build or verify a closed evidence manifest (B00R RCP-010/011 / NEG-011).

``--build`` reads a spec of ``{"path","role"}`` records and computes each file's size/sha256/media
type deterministically. ``--verify`` re-resolves every declared digest against committed bytes and
rejects missing, extra, duplicate, symlink, path-escape, zero-size, or byte-changed entries.

Usage:
  python tools/build_evidence_manifest.py --build spec.json --root . --out manifest.json
  python tools/build_evidence_manifest.py --verify manifest.json --root .
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from triad_origin import governance  # noqa: E402


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build")
    parser.add_argument("--verify")
    parser.add_argument("--root", default=".")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    root = pathlib.Path(args.root)

    if args.build:
        spec = json.loads(pathlib.Path(args.build).read_text(encoding="utf-8"))
        entries = spec["entries"] if isinstance(spec, dict) else spec
        try:
            manifest = governance.build_evidence_manifest(root, entries)
        except governance.GovernanceError as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1
        text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        if args.out:
            pathlib.Path(args.out).write_text(text, encoding="utf-8")
            print(f"OK: wrote {args.out} ({manifest['entry_count']} entries)")
        else:
            sys.stdout.write(text)
        return 0

    if args.verify:
        manifest = json.loads(pathlib.Path(args.verify).read_text(encoding="utf-8"))
        try:
            governance.validate_evidence_manifest(manifest, root)
        except governance.GovernanceError as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1
        print(f"OK: evidence manifest verified ({manifest.get('entry_count')} entries)")
        return 0

    print("FAIL: pass --build or --verify", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
