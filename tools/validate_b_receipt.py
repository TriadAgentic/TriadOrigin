#!/usr/bin/env python3
"""Validate B-series milestone receipt(s) — legacy-tolerant across the v2/v3 schema transition.

Two modes:

  * SINGLE FILE  ``validate_b_receipt.py <receipt.json>`` — validate one receipt, dispatched by
    its ``schema``: a ``triad.evidence_receipt.v2`` receipt is validated against the v2 shape (the
    contract's semantic validator + file-name/scope agreement + the deterministic self-integrity
    signature); a ``triad.evidence_receipt.v3`` receipt is validated against the full
    unsigned-checkable clause set of the frozen audit runner's receipt law plus file-byte
    predecessor chaining and cross-receipt chronology.

  * CHAIN WALK  ``validate_b_receipt.py --all [--strict]`` — walk the frozen runner's milestone
    receipt discovery (``MILESTONE_RECEIPT_NAMES`` over ``evidence/receipts|terminal/<name>.json``
    and ``evidence/<name>.json``) for B01..B10, validate every EXISTING receipt (an absent future
    milestone is fine), and — with ``--strict`` — additionally require every v3 receipt to chain
    by byte to its discovered predecessor and to satisfy the chain-so-far chronology. Exit 0 iff
    every existing receipt satisfies its schema's law (and, under ``--strict``, the chain-so-far).

The v2 receipts on disk today (B01..B07, plus the pre-chain B00/B00C/R00) predate the v3 receipt
law; they are validated against the v2 law and never retroactively rewritten (docs/plan
09_OPEN_QUESTIONS E24/E28/E34). The v3 clause set / predecessor chaining is enforced only when a
v3 receipt is actually present — the repair chain produces those.

Signature/DSSE AUTHENTICATION (two independently-verified Ed25519 signers over the RFC 8785
canonical payload, the external trust-registry and receipt-profile-decision pins) is NOT performed
here — that is the frozen runner's independent audit, and GOV-level countersigning is an operator
act (docs/plan 09_OPEN_QUESTIONS E31/E32). This validator is a repository-side self-integrity gate.

Usage:
  python tools/validate_b_receipt.py evidence/receipts/B07.json
  python tools/validate_b_receipt.py --all --strict
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import re
import sys
import time
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import contracts  # noqa: E402
from triad_origin.canonical import canonical_json, sha256_hex  # noqa: E402

V2_SCHEMA = "triad.evidence_receipt.v2"
V3_SCHEMA = "triad.evidence_receipt.v3"

# --- Mirror of the frozen runner's discovery/chain constants (audit_package runner L134-158). ---
MILESTONE_RECEIPT_NAMES: dict[str, tuple[str, ...]] = {
    "B01": ("B01C", "B01R", "B01"),
    "B02": ("B02C", "B02"),
    "B03": ("B03C", "B03"),
    "B04": ("B04C", "B04"),
    "B05": ("B05C", "B05"),
    "B06": ("B06R", "B06"),
    "B07": ("B07",),
    "B08": ("B08",),
    "B09": ("B09",),
    "B10": ("B10",),
}
PREDECESSOR: dict[str, str | None] = {
    "B01": None, "B02": "B01", "B03": "B02", "B04": "B03", "B05": "B04",
    "B06": "B05", "B07": "B06", "B08": "B07", "B09": "B08", "B10": "B09",
}
_DISCOVERY_SUBDIRS = ("evidence/receipts", "evidence/terminal", "evidence")


def compute_signature(payload: dict) -> str:
    """The deterministic v2 self-integrity seal: SHA-256 of the canonical payload, signature blanked."""
    unsigned = dict(payload)
    unsigned["signature"] = ""
    return sha256_hex(canonical_json(unsigned))


def find_receipt(root: pathlib.Path, milestone: str) -> pathlib.Path | None:
    """The frozen runner's discovery: first present of MILESTONE_RECEIPT_NAMES across the dirs."""
    for name in MILESTONE_RECEIPT_NAMES[milestone]:
        for subdir in _DISCOVERY_SUBDIRS:
            path = root / subdir / f"{name}.json"
            if path.is_file():
                return path
    return None


def _receipt_schema(path: pathlib.Path) -> tuple[str | None, dict | None, str | None]:
    """Return (schema, event, load_error). Never raises."""
    try:
        event = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, None, f"receipt is unreadable or invalid JSON: {exc}"
    if not isinstance(event, dict):
        return None, None, "receipt root must be a JSON object"
    return event.get("schema"), event, None


def validate_v2(path: pathlib.Path) -> list[str]:
    """The v2 receipt law: contract-valid, file name agrees with scope milestone, self-integrity."""
    schema, event, err = _receipt_schema(path)
    if err is not None:
        return [err]
    assert event is not None
    try:
        contracts.validate(event, schema_id=V2_SCHEMA)
    except contracts.ContractError as exc:
        return [f"receipt is not contract-valid ({V2_SCHEMA}): {exc}"]
    issues: list[str] = []
    payload = event.get("payload", {})
    milestone = payload.get("scope", {}).get("milestone")
    if path.stem != milestone:
        issues.append(f"receipt file {path.name} does not name its scope milestone {milestone!r}")
    expected = compute_signature(payload)
    if payload.get("signature") != expected:
        issues.append(f"receipt self-integrity signature mismatch (expected {expected[:16]}...)")
    return issues


_DRAFT_ISSUES = None


def _draft_issues():
    """Lazily load ``draft_issues`` from tools/build_receipt_v3.py (the full v3 unsigned clause set)."""
    global _DRAFT_ISSUES
    if _DRAFT_ISSUES is None:
        module_path = ROOT / "tools" / "build_receipt_v3.py"
        spec = importlib.util.spec_from_file_location("_b0r_build_receipt_v3", module_path)
        if spec is None or spec.loader is None:  # pragma: no cover - defensive
            raise RuntimeError(f"cannot load {module_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _DRAFT_ISSUES = module.draft_issues
    return _DRAFT_ISSUES


def validate_v3(
    path: pathlib.Path, milestone: str, *, strict: bool, predecessor_path: pathlib.Path | None,
) -> list[str]:
    """The v3 receipt law: full unsigned-checkable clause set + file-byte predecessor chaining."""
    schema, event, err = _receipt_schema(path)
    if err is not None:
        return [err]
    assert event is not None
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else event
    now_us = int(time.time() * 1_000_000)
    # The unsigned-checkable clause set, re-derived from bytes. The external trust-registry and
    # receipt-profile-decision pins are taken from the receipt's own declared values, so the
    # pin-match clauses check internal consistency (independent authentication is the runner's job).
    issues = list(_draft_issues()(
        path, milestone,
        repository_root=ROOT,
        trust_registry_sha256=str(payload.get("trust_registry_sha256") or ""),
        receipt_profile_decision_sha256=str(payload.get("receipt_profile_decision_sha256") or ""),
        now_us=now_us,
    ))
    if strict and PREDECESSOR.get(milestone) is not None:
        if predecessor_path is None:
            issues.append(
                f"v3 chain: predecessor receipt for {PREDECESSOR[milestone]} is not on disk")
        else:
            pre_bytes = predecessor_path.read_bytes()
            pre_digest = hashlib.sha256(pre_bytes).hexdigest()
            if payload.get("predecessor_receipt_sha256") != pre_digest:
                issues.append(
                    "v3 chain: predecessor_receipt_sha256 does not equal the byte SHA-256 of the "
                    f"discovered predecessor receipt {predecessor_path.name}")
            try:
                pre_event = json.loads(pre_bytes.decode("utf-8"))
                pre_payload = pre_event.get("payload") if isinstance(
                    pre_event.get("payload"), dict) else pre_event
                pre_emitted = _int_or_none(pre_payload.get("emitted_at_us"))
                this_merge = _int_or_none(payload.get("source_merge_at_us"))
                if pre_emitted is not None and this_merge is not None and not pre_emitted <= this_merge:
                    issues.append(
                        "v3 chain: predecessor was emitted after this receipt's source merge")
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                issues.append(f"v3 chain: predecessor receipt is unreadable for chronology: {exc}")
    return issues


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _milestone_for(path: pathlib.Path, event: dict) -> str:
    """Normalize a receipt's claimed milestone (mirrors the runner's normalize_milestone_from_text)."""
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else event
    scope = payload.get("scope") if isinstance(payload.get("scope"), dict) else {}
    raw = str(payload.get("milestone_id") or scope.get("milestone") or path.stem)
    match = re.search(r"\bB(0[1-9]|10)(?:C|R)?\b", raw.upper())
    return f"B{match.group(1)}" if match else raw


def validate_one(path: pathlib.Path, *, strict: bool, milestone: str | None = None) -> list[str]:
    """Validate a single receipt file by its declared schema."""
    schema, event, err = _receipt_schema(path)
    if err is not None:
        return [err]
    assert event is not None
    if schema == V2_SCHEMA:
        return validate_v2(path)
    if schema == V3_SCHEMA:
        key = milestone or _milestone_for(path, event)
        predecessor = PREDECESSOR.get(key)
        predecessor_path = find_receipt(ROOT, predecessor) if predecessor else None
        return validate_v3(path, key, strict=strict, predecessor_path=predecessor_path)
    return [f"unsupported receipt schema {schema!r} (expected {V2_SCHEMA} or {V3_SCHEMA})"]


def validate_all(*, strict: bool) -> int:
    """Walk B01..B10 and validate every discovered receipt; exit 0 iff all pass."""
    any_failed = False
    seen = 0
    for milestone in MILESTONE_RECEIPT_NAMES:
        path = find_receipt(ROOT, milestone)
        if path is None:
            continue  # an absent future-milestone receipt is not a failure
        seen += 1
        issues = validate_one(path, strict=strict, milestone=milestone)
        rel = path.relative_to(ROOT).as_posix()
        if issues:
            any_failed = True
            for issue in issues:
                print(f"FAIL {milestone} {rel}: {issue}", file=sys.stderr)
        else:
            schema, _event, _err = _receipt_schema(path)
            print(f"OK {milestone} {rel} ({schema})")
    if seen == 0:
        print("FAIL: no B01..B10 milestone receipts were discovered", file=sys.stderr)
        return 1
    if any_failed:
        return 1
    print(f"OK: {seen} B-series milestone receipt(s) valid ({'strict' if strict else 'lenient'})")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="validate_b_receipt.py",
        description="Validate B-series milestone receipt(s), legacy-tolerant across v2/v3.")
    parser.add_argument("receipt", nargs="?", help="a single receipt JSON to validate")
    parser.add_argument("--all", action="store_true",
                        help="walk B01..B10 receipt discovery and validate every existing receipt")
    parser.add_argument("--strict", action="store_true",
                        help="additionally enforce the v3 file-byte predecessor chain-so-far")
    args = parser.parse_args(argv)

    if args.all:
        if args.receipt is not None:
            print("usage: --all takes no positional receipt path", file=sys.stderr)
            return 2
        return validate_all(strict=args.strict)

    if args.receipt is None:
        print("usage: validate_b_receipt.py <receipt.json> | --all [--strict]", file=sys.stderr)
        return 2
    path = pathlib.Path(args.receipt)
    issues = validate_one(path, strict=args.strict)
    if issues:
        for issue in issues:
            print(f"FAIL: {issue}", file=sys.stderr)
        return 1
    schema, event, _err = _receipt_schema(path)
    payload = event.get("payload", {}) if isinstance(event, dict) else {}
    milestone = payload.get("scope", {}).get("milestone") or payload.get("milestone_id") or path.stem
    print(f"OK: milestone receipt {milestone} valid ({payload.get('result')}) [{schema}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
