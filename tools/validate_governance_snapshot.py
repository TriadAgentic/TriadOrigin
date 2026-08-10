#!/usr/bin/env python3
"""Verify a normalized governance snapshot against pinned raw GitHub ruleset evidence."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from triad_origin import governance  # noqa: E402

DEFAULT = ROOT / "docs/governance/rulesets/main.ruleset.provider.json"
TEMPLATE = ROOT / "docs/governance/rulesets/main.ruleset.provider.template.json"
PIN_ENV = "MAIN_RULESET_EVIDENCE_SHA256"


def _git(root: pathlib.Path, *args: str, text: bool = True) -> str | bytes:
    env = dict(os.environ)
    for name in tuple(env):
        if name.startswith("GIT_") and name != "GIT_CONFIG_NOSYSTEM":
            env.pop(name, None)
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          text=text, env=env)
    if proc.returncode:
        err = proc.stderr.strip() if text else proc.stderr.decode("utf-8", "replace").strip()
        raise ValueError(f"GIT_COMMAND_FAILED:{' '.join(args)}:{err}")
    return proc.stdout.strip() if text else proc.stdout


def _validate_git_binding(
    *, path: pathlib.Path, raw_path: pathlib.Path, git_root: pathlib.Path, expected_head: str,
) -> None:
    if re.fullmatch(r"[0-9a-f]{40}", expected_head or "") is None:
        raise ValueError("EXPECTED_HEAD_NOT_CANONICAL_SHA40")
    root = pathlib.Path(str(_git(git_root, "rev-parse", "--show-toplevel"))).resolve(strict=True)
    if root != git_root.resolve(strict=True) or str(_git(root, "rev-parse", "HEAD")) != expected_head:
        raise ValueError("EXPECTED_HEAD_OR_GIT_ROOT_MISMATCH")
    if str(_git(root, "status", "--porcelain=v1", "--untracked-files=all")):
        raise ValueError("GIT_WORKTREE_NOT_CLEAN")
    expected = {
        path: "docs/governance/rulesets/main.ruleset.provider.json",
        raw_path: "docs/governance/rulesets/main.ruleset.provider.raw.json",
    }
    for candidate, rel in expected.items():
        try:
            actual_rel = candidate.resolve(strict=True).relative_to(root).as_posix()
        except (OSError, ValueError):
            raise ValueError(f"GOVERNANCE_PATH_OUTSIDE_GIT_ROOT:{candidate}") from None
        if actual_rel != rel:
            raise ValueError(f"GOVERNANCE_PATH_NONCANONICAL:{actual_rel}")
        if _git(root, "show", f"{expected_head}:{rel}", text=False) != candidate.read_bytes():
            raise ValueError(f"GOVERNANCE_GIT_BLOB_MISMATCH:{rel}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--snapshot", type=pathlib.Path)
    parser.add_argument("--provider-raw", type=pathlib.Path,
                        help="raw bytes returned by GET /repos/.../rulesets/{id}")
    parser.add_argument("--provider-pin",
                        help=f"external SHA-256 pin (or protected {PIN_ENV})")
    parser.add_argument("--now-us", type=int,
                        help="trusted current Unix time in microseconds")
    parser.add_argument("--source-merge-time-us", type=int,
                        help="source merge time; evidence capture must precede it")
    parser.add_argument("--expected-head")
    parser.add_argument("--git-root", type=pathlib.Path, default=ROOT)
    args = parser.parse_args(argv)
    path = args.snapshot or (DEFAULT if DEFAULT.exists() else TEMPLATE)
    if not path.exists():
        print("FAIL: no governance snapshot file", file=sys.stderr)
        return 1
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"FAIL: snapshot not JSON: {exc}", file=sys.stderr)
        return 1
    raw_bytes = None
    if args.provider_raw is not None:
        try:
            raw_path = args.provider_raw.resolve(strict=True)
            raw_bytes = raw_path.read_bytes()
            rel = raw_path.relative_to(ROOT.resolve(strict=True)).as_posix()
        except (OSError, ValueError) as exc:
            print(f"FAIL: provider response must be a committed repository file: {exc}",
                  file=sys.stderr)
            return 1
        declared = doc.get("provider", {}).get("api_response_path") if isinstance(doc, dict) else None
        if declared != rel:
            print("FAIL: provider api_response_path does not name --provider-raw", file=sys.stderr)
            return 1
    cli_pin = args.provider_pin
    env_pin = os.environ.get(PIN_ENV)
    if cli_pin and env_pin and cli_pin != env_pin:
        print("FAIL: conflicting CLI and protected-environment provider pins", file=sys.stderr)
        return 1
    external_pin = env_pin or cli_pin
    result, reason = governance.validate_governance_snapshot(
        doc, provider_raw_bytes=raw_bytes, external_pin=external_pin,
        now_us=args.now_us, source_merge_time_us=args.source_merge_time_us)
    if result == "PASS":
        if args.strict:
            if args.expected_head is None or args.provider_raw is None:
                print("FAIL: --strict requires --expected-head and --provider-raw", file=sys.stderr)
                return 2
            try:
                _validate_git_binding(
                    path=path, raw_path=args.provider_raw, git_root=args.git_root,
                    expected_head=args.expected_head)
            except (OSError, ValueError) as exc:
                print(f"FAIL: {exc}", file=sys.stderr)
                return 1
        print(f"OK: governance snapshot is raw-provider-derived, externally pinned, no-bypass "
              f"main control ({path.name})")
        return 0
    stream = sys.stderr if result == "FAIL" else sys.stdout
    print(f"{result}: {reason} ({path.name})", file=stream)
    return 1 if args.strict else (0 if result == "UNAVAILABLE" else 1)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
