#!/usr/bin/env python3
"""Verify the B00R authority root against external pins (B00R AUTH-* / NEG-003 / NEG-010).

The three root decisions (``DEC-AUTHORITY-BUNDLE-001``, ``DEC-RECEIPT-PROFILE-001``,
``DEC-B00-REPAIR-001``) and the public trust registry are authenticated only when:

  1. each decision file is authenticated (``authenticated: true`` with verifying signatures);
  2. each decision/registry digest equals a pin supplied from OUTSIDE the proposed tree (protected
     repo/environment variable), so a self-updating source + in-tree hash cannot bypass authority.

Absent external pins or unauthenticated decisions are fail-closed ``UNAVAILABLE_AUTHORITY_ROOT`` —
never a silent pass. External pins are read from environment variables
``RECEIPT_TRUST_REGISTRY_SHA256``, ``RECEIPT_PROFILE_DECISION_SHA256``,
``AUTHORITY_BUNDLE_DECISION_SHA256``, ``B00_REPAIR_DECISION_SHA256`` or from ``--pins <json>``.

Usage:
  python tools/validate_authority_root.py --strict [--pins pins.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from triad_origin import governance  # noqa: E402

GOV = ROOT / "docs" / "governance"

# (env var, pin key, candidate authenticated path, template path)
SUBJECTS = {
    "authority_bundle": (
        "AUTHORITY_BUNDLE_DECISION_SHA256",
        GOV / "decisions" / "DEC-AUTHORITY-BUNDLE-001.json",
        GOV / "decisions" / "DEC-AUTHORITY-BUNDLE-001.template.json",
    ),
    "receipt_profile": (
        "RECEIPT_PROFILE_DECISION_SHA256",
        GOV / "decisions" / "DEC-RECEIPT-PROFILE-001.json",
        GOV / "decisions" / "DEC-RECEIPT-PROFILE-001.template.json",
    ),
    "b00_repair": (
        "B00_REPAIR_DECISION_SHA256",
        GOV / "decisions" / "DEC-B00-REPAIR-001.json",
        GOV / "decisions" / "DEC-B00-REPAIR-001.template.json",
    ),
    "trust_registry": (
        "RECEIPT_TRUST_REGISTRY_SHA256",
        GOV / "trust" / "receipt_trust_registry.v1.json",
        GOV / "trust" / "receipt_trust_registry.v1.template.json",
    ),
}


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--pins", help="json object of external pin key -> hex64")
    args = parser.parse_args(argv)

    pins: dict[str, str] = {}
    if args.pins:
        pins.update(json.loads(pathlib.Path(args.pins).read_text(encoding="utf-8")))
    for name, (env, _authed, _tmpl) in SUBJECTS.items():
        if env in os.environ:
            pins[env] = os.environ[env]

    problems: list[str] = []
    unavailable: list[str] = []
    for name, (env, authed_path, tmpl_path) in SUBJECTS.items():
        path = authed_path if authed_path.exists() else tmpl_path
        if not path.exists():
            problems.append(f"{name}: no decision/registry file")
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        # Authentication (owner-gated).
        if name == "trust_registry":
            authenticated = doc.get("authenticated") is True
            try:
                governance.validate_trust_registry(doc)
            except governance.GovernanceError as exc:
                problems.append(f"trust_registry invalid: {exc}")
                authenticated = False
        else:
            authenticated = governance.decision_is_authenticated(doc)
        if not authenticated:
            unavailable.append(f"{name} ({path.name}) not authenticated")
        # External pin binding.
        pin = pins.get(env)
        if pin is None:
            unavailable.append(f"{name}: external pin {env} absent")
        else:
            actual = _sha256(path)
            if pin != actual:
                problems.append(f"{name}: pin {env} != file digest ({actual[:16]})")

    if problems:
        for p in problems:
            print(f"FAIL: {p}", file=sys.stderr)
        return 1
    if unavailable:
        for u in unavailable:
            print(f"UNAVAILABLE_AUTHORITY_ROOT: {u}", file=sys.stdout)
        print("UNAVAILABLE_AUTHORITY_ROOT: owner authentication and external pins are required "
              "before B00R can PASS (fail-closed).", file=sys.stdout)
        return 1 if args.strict else 0
    print("OK: authority root authenticated and externally pinned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
