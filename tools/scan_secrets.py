#!/usr/bin/env python3
"""Tracked-file secret scan for TriadOrigin.

This tool is the repository-local mirror of the independent static secret scan
performed by the frozen audit runner ``audit_package/triad_origin_b01_b10_audit.py``
(v1.2.0, SHA-256 ``12c8896479b902165fa2c6d3e7565ea8402b49fcfe2d044f6fd69153926d35a2``).
``TEXT_SUFFIXES`` and ``SECRET_PATTERNS`` below are copied verbatim from that runner
(source lines 243-270); the enumeration/filter/read law mirrors its
``tracked_files`` (lines 2351-2355), ``run_git`` (lines 2333-2337) and the scan loop
(lines 2394-2407).  Differential tests in ``tests/tools/test_scan_secrets.py`` pin
byte-equality against the runner source.

Law:
  * Enumerate tracked files with ``git ls-files -z`` from the repository root
    (the parent of ``tools/``, resolved from ``__file__`` -- never from the CWD).
  * Scan only regular files whose lowercased suffix is in ``TEXT_SUFFIXES`` and
    whose size is <= 8_000_000 bytes; read as UTF-8 with ``errors="replace"``.
  * Record at most one hit per (pattern, file) pair, in ``git ls-files`` file
    order and ``SECRET_PATTERNS`` order within a file.
  * ``--fail-on-hit``: any hit prints one ``name<TAB>relative/path`` line per hit
    to stdout and exits 1; a clean scan prints nothing to stdout and exits 0.
    A one-line summary always goes to stderr only.
  * Read-only: this tool writes nothing, imports only the standard library, and
    never imports sibling repository modules (no ``__pycache__`` in a fresh clone).

Self-reference note: the pattern literals below cannot match their own spelling
because regex metacharacters (``\\s*[:=]``, ``(?:...)`` groups, character classes)
sit between each trigger word and its payload class -- the same structural
property that keeps the frozen runner's own vendored source clean.  This is
verified empirically by the test suite.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import subprocess
import sys
from collections.abc import Sequence

# Runner source line 2402 (the tracked-text-file size ceiling).
MAX_TEXT_FILE_BYTES = 8_000_000

# --- Verbatim from audit_package/triad_origin_b01_b10_audit.py L243-246 ---
TEXT_SUFFIXES = {
    ".py", ".json", ".jsonl", ".ndjson", ".md", ".txt", ".toml", ".yaml", ".yml",
    ".ini", ".cfg", ".csv", ".schema", ".html", ".xml", ".sh",
}

# --- Verbatim from audit_package/triad_origin_b01_b10_audit.py L248-270 ---
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("authorization_bearer", re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[A-Za-z0-9._~+/=-]{16,}")),
    ("bearer", re.compile(r"(?i)(\bbearer\s+)[A-Za-z0-9._~+/=-]{20,}")),
    ("query_token", re.compile(r"(?i)([?&](?:token|access_token|auth)=)[^\s&#\"']{12,}")),
    ("github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{20,}\b")),
    ("triad_mcp_token", re.compile(r"\btmc_[A-Za-z0-9_-]{16,}\b")),
    ("authorization_basic", re.compile(r"(?i)(authorization\s*[:=]\s*basic\s+)[A-Za-z0-9+/=]{8,}")),
    ("cookie_header", re.compile(r"(?im)^((?:set-)?cookie\s*:\s*)[^\r\n]+")),
    ("session_assignment", re.compile(
        r"(?i)((?:session(?:id|_id|_key|_token)?|sid)\s*[:=]\s*[\"']?)[^\s,;\"']{8,}")),
    ("openai_token", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("stripe_token", re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{16,}\b")),
    ("gitlab_token", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("uri_userinfo", re.compile(r"(?i)(https?://)[^\s/@:]+:[^\s/@]+@")),
    ("secret_assignment", re.compile(
        r"(?i)((?:api[_-]?key|client[_-]?secret|password|passwd|access[_-]?token)\s*[:=]\s*[\"']?)[^\s,;\"']{12,}")),
    ("private_key", re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]{0,100000}?"
        r"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
)
# --- End verbatim runner blocks ---


class ScanError(RuntimeError):
    """Raised when tracked files cannot be enumerated trustworthily."""


def repo_root() -> pathlib.Path:
    """The repository root: the parent of the ``tools/`` directory holding this file."""
    return pathlib.Path(__file__).resolve().parent.parent


def run_git(repo: pathlib.Path, *args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    """Read-only git query with the scrubbed environment the frozen runner uses."""
    return subprocess.run(
        ["git", "-C", str(repo), *args], text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=timeout, check=False,
        env={"PATH": os.environ.get("PATH", ""), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC"})


def tracked_files(repo: pathlib.Path) -> list[str]:
    """Repo-relative tracked paths from ``git ls-files -z``; raises ScanError on git failure."""
    result = run_git(repo, "ls-files", "-z")
    if result.returncode != 0:
        raise ScanError(f"git ls-files failed (exit {result.returncode}): {result.stderr.strip()}")
    return [item for item in result.stdout.split("\0") if item]


def scan_text(text: str) -> list[str]:
    """Pattern names (in SECRET_PATTERNS order) that hit the given text, one per pattern."""
    return [name for name, pattern in SECRET_PATTERNS if pattern.search(text)]


def scan_repo(repo: pathlib.Path) -> tuple[int, list[tuple[str, str]]]:
    """Scan every eligible tracked text file of ``repo``.

    Returns ``(text_files_scanned, hits)`` where each hit is
    ``(pattern_name, repo_relative_posix_path)`` -- at most one hit per
    (pattern, file) pair, exactly mirroring the frozen runner's scan loop.
    Raises ScanError if enumeration fails or yields no tracked files
    (a fresh clone always has tracked files; silence must not be a pass).
    """
    items = tracked_files(repo)
    if not items:
        raise ScanError("cannot enumerate any tracked files for secret scan")
    scanned = 0
    hits: list[tuple[str, str]] = []
    for item in items:
        path = repo / item
        if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file() \
                or path.stat().st_size > MAX_TEXT_FILE_BYTES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        scanned += 1
        for name in scan_text(text):
            hits.append((name, item))
    return scanned, hits


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scan_secrets.py",
        description="Read-only tracked-file secret scan (mirror of the frozen audit runner law).")
    parser.add_argument(
        "--tracked", action="store_true", required=True,
        help="enumerate via git ls-files (the only supported mode)")
    parser.add_argument(
        "--fail-on-hit", action="store_true",
        help="exit 1 when any credential-like pattern hits a tracked text file")
    args = parser.parse_args(argv)

    repo = repo_root()
    try:
        scanned, hits = scan_repo(repo)
    except (ScanError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"scan_secrets: error: {exc}", file=sys.stderr)
        return 2

    for name, relative in hits:
        print(f"{name}\t{relative}")
    print(
        f"scan_secrets: scanned {scanned} tracked text files, {len(hits)} hit(s)",
        file=sys.stderr)
    if hits and args.fail_on_hit:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
