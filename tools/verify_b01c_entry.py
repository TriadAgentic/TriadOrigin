#!/usr/bin/env python3
"""Fail closed unless the current checkout is the terminally validated B00R G2 base.

This is an entry authorization, not a promotion or activation command.  It derives the source
merge from the canonical generation-2 receipt, runs the complete terminal ``b00r_gate`` against
the exact clean receipt-merge checkout, requires its literal safe-hold PASS, then rechecks that no
repository state changed.  It never creates a branch and never changes a lever.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from triad_origin.canonical import CanonicalError, canonical_json, loads_canonical  # noqa: E402

try:  # importable both as ``python tools/...`` and ``from tools import ...``
    from tools.b00r_gate import (  # type: ignore  # noqa: E402
        CANONICAL_RECEIPT, HeadIdentityError, verify_final_repository_state)
except ModuleNotFoundError:  # pragma: no cover - direct script fallback
    from b00r_gate import (  # type: ignore  # noqa: E402
        CANONICAL_RECEIPT, HeadIdentityError, verify_final_repository_state)


HEX40_RE = re.compile(r"[0-9a-f]{40}")
HEX64_RE = re.compile(r"[0-9a-f]{64}")
PASS_LINE = "B00R result: PASS_REPOSITORY_SAFE_HOLD"
ENTRY_PASS = "PASS_B01C_ENTRY_BASE"


class B01CEntryError(ValueError):
    """The physical B00R G2 closure is not a valid B01C branch base."""


def _resolve_protected_pin(
    cli_pin: str | None, env_pin: str | None, label: str
) -> str | None:
    if cli_pin and env_pin and cli_pin != env_pin:
        raise B01CEntryError(f"CONFLICTING_CLI_AND_PROTECTED_{label}_PINS")
    return env_pin or cli_pin


def _canonical_g2_receipt(root: pathlib.Path) -> tuple[pathlib.Path, str]:
    receipt_path = root / CANONICAL_RECEIPT
    try:
        raw = receipt_path.read_bytes()
        receipt = loads_canonical(raw)
    except (OSError, CanonicalError) as exc:
        raise B01CEntryError(f"B00R_G2_RECEIPT_NOT_CANONICAL:{exc}") from exc
    if not isinstance(receipt, dict) or canonical_json(receipt) != raw:
        raise B01CEntryError("B00R_G2_RECEIPT_NOT_CANONICAL_OBJECT")
    payload = receipt.get("payload")
    if (not isinstance(payload, dict)
            or payload.get("milestone") != "B00R"
            or payload.get("repair_generation") != 2):
        raise B01CEntryError("B00R_G2_RECEIPT_IDENTITY_MISMATCH")
    source_merge = payload.get("source_merge_sha")
    if (not isinstance(source_merge, str)
            or HEX40_RE.fullmatch(source_merge) is None
            or source_merge == "0" * 40):
        raise B01CEntryError("B00R_G2_SOURCE_MERGE_INVALID")
    return receipt_path, source_merge


def _require_detached_head(root: pathlib.Path) -> None:
    env = {
        name: value for name, value in os.environ.items()
        if not name.startswith("GIT_") or name == "GIT_CONFIG_NOSYSTEM"
    }
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    proc = subprocess.run(
        ["git", "-C", str(root), "symbolic-ref", "-q", "HEAD"],
        capture_output=True, text=True, check=False, env=env)
    if proc.returncode == 0:
        raise B01CEntryError(f"B01C_BASE_HEAD_NOT_DETACHED:{proc.stdout.strip()}")
    if proc.returncode != 1:
        raise B01CEntryError(f"B01C_BASE_HEAD_STATE_UNAVAILABLE:{proc.stderr.strip()}")


def _terminal_command(
    *,
    root: pathlib.Path,
    expected_head: str,
    source_merge: str,
    receipt_pr: int,
    now_us: int,
    pins: pathlib.Path | None,
    provider_pin: str,
    anchor_ruleset_pin: str,
) -> tuple[str, ...]:
    command = [
        sys.executable,
        str(root / "tools" / "b00r_gate.py"),
        "--mode", "receipt",
        "--base-sha", source_merge,
        "--expected-head", expected_head,
        "--receipt-pr", str(receipt_pr),
        "--now-us", str(now_us),
        "--provider-pin", provider_pin,
        "--anchor-ruleset-pin", anchor_ruleset_pin,
    ]
    if pins is not None:
        command.extend(("--pins", str(pins)))
    return tuple(command)


def _run_terminal_gate(root: pathlib.Path, command: tuple[str, ...]) -> subprocess.CompletedProcess:
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("GIT_") or name == "GIT_CONFIG_NOSYSTEM"
    }
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    return subprocess.run(
        command, cwd=root, env=env, capture_output=True, text=True, check=False)


def _require_terminal_pass(proc: subprocess.CompletedProcess) -> None:
    combined = f"{proc.stdout or ''}\n{proc.stderr or ''}"
    pass_rows = [line.strip() for line in combined.splitlines() if line.startswith("B00R result:")]
    if proc.returncode != 0:
        tail = next((line.strip() for line in reversed(combined.splitlines()) if line.strip()), "")
        raise B01CEntryError(f"B00R_TERMINAL_GATE_REJECTED:{proc.returncode}:{tail}")
    if pass_rows != [PASS_LINE]:
        raise B01CEntryError(f"B00R_TERMINAL_PASS_MARKER_INVALID:{pass_rows}")


def verify_entry(
    *,
    root: pathlib.Path,
    expected_head: str,
    receipt_pr: int,
    now_us: int,
    pins: pathlib.Path | None,
    provider_pin: str,
    anchor_ruleset_pin: str,
) -> str:
    """Return the exact authorized B01C base without mutating repository state."""
    root = root.resolve(strict=True)
    if (HEX40_RE.fullmatch(expected_head or "") is None
            or expected_head == "0" * 40):
        raise B01CEntryError("EXPECTED_RECEIPT_MERGE_INVALID")
    if (not isinstance(receipt_pr, int) or isinstance(receipt_pr, bool) or receipt_pr <= 0):
        raise B01CEntryError("RECEIPT_PR_INVALID")
    if not isinstance(now_us, int) or isinstance(now_us, bool) or now_us <= 0:
        raise B01CEntryError("NOW_US_INVALID")
    for label, value in (
        ("MAIN_RULESET_PIN", provider_pin),
        ("TAG_RULESET_PIN", anchor_ruleset_pin),
    ):
        if (not isinstance(value, str) or HEX64_RE.fullmatch(value) is None
                or value == "0" * 64):
            raise B01CEntryError(f"{label}_INVALID")
    if pins is not None:
        try:
            pins = pins.resolve(strict=True)
        except OSError as exc:
            raise B01CEntryError(f"AUTHORITY_PINS_UNREADABLE:{exc}") from exc
        try:
            pins.relative_to(root)
        except ValueError:
            pass
        else:
            raise B01CEntryError("AUTHORITY_PINS_MUST_BE_OUTSIDE_REPOSITORY")

    try:
        verify_final_repository_state(expected_head, root)
    except HeadIdentityError as exc:
        raise B01CEntryError(f"B01C_BASE_REPOSITORY_STATE_INVALID:{exc}") from exc
    _require_detached_head(root)
    _receipt_path, source_merge = _canonical_g2_receipt(root)
    command = _terminal_command(
        root=root,
        expected_head=expected_head,
        source_merge=source_merge,
        receipt_pr=receipt_pr,
        now_us=now_us,
        pins=pins,
        provider_pin=provider_pin,
        anchor_ruleset_pin=anchor_ruleset_pin,
    )
    _require_terminal_pass(_run_terminal_gate(root, command))
    try:
        verify_final_repository_state(expected_head, root)
    except HeadIdentityError as exc:
        raise B01CEntryError(f"B01C_BASE_CHANGED_DURING_GATE:{exc}") from exc
    _require_detached_head(root)
    return expected_head


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Authorize the exact terminally validated B00R G2 receipt merge as B01C base")
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--receipt-pr", required=True, type=int)
    parser.add_argument("--now-us", required=True, type=int)
    parser.add_argument("--git-root", type=pathlib.Path, default=ROOT)
    parser.add_argument("--pins", type=pathlib.Path)
    parser.add_argument("--provider-pin")
    parser.add_argument("--anchor-ruleset-pin")
    args = parser.parse_args(argv)
    try:
        requested_root = args.git_root.resolve(strict=True)
        canonical_root = ROOT.resolve(strict=True)
    except OSError as exc:
        print(f"FAIL_B01C_ENTRY:CANONICAL_REPOSITORY_ROOT_UNAVAILABLE:{exc}", file=sys.stderr)
        return 1
    if requested_root != canonical_root:
        print("FAIL_B01C_ENTRY:NONCANONICAL_GIT_ROOT_FORBIDDEN", file=sys.stderr)
        return 1
    try:
        provider_pin = _resolve_protected_pin(
            args.provider_pin,
            os.environ.get("MAIN_RULESET_EVIDENCE_SHA256"),
            "MAIN_RULESET",
        )
        anchor_pin = _resolve_protected_pin(
            args.anchor_ruleset_pin,
            os.environ.get("B00R_G2_TAG_RULESET_SHA256"),
            "TAG_RULESET",
        )
    except B01CEntryError as exc:
        print(f"FAIL_B01C_ENTRY:{exc}", file=sys.stderr)
        return 1
    if provider_pin is None or anchor_pin is None:
        print(
            "BLOCKED: protected main/tag ruleset pins are required",
            file=sys.stderr,
        )
        return 1
    try:
        head = verify_entry(
            root=args.git_root,
            expected_head=args.expected_head,
            receipt_pr=args.receipt_pr,
            now_us=args.now_us,
            pins=args.pins,
            provider_pin=provider_pin,
            anchor_ruleset_pin=anchor_pin,
        )
    except (B01CEntryError, OSError, ValueError) as exc:
        print(f"FAIL_B01C_ENTRY:{exc}", file=sys.stderr)
        return 1
    print(f"{ENTRY_PASS}:{head}")
    print("levers remain OFF/OFF/OFF/LIVE; activation_result=DENIED_SAFE_HOLD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
