#!/usr/bin/env python3
"""Fail if the E02 runtime acquires network, credential, or venue-order capability.

Contract names and declarative schemas may describe downstream commands. This gate inspects
executable Python under ``src/triad_origin`` and therefore tests capability, not vocabulary.
"""

from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "src" / "triad_origin"

ALLOWED_MODULE_ROOTS = {
    "__future__",
    "collections",
    "dataclasses",
    "decimal",
    "enum",
    "fcntl",
    "functools",
    "hashlib",
    "json",
    "jsonschema",  # optional local schema validation only
    "math",
    "os",
    "pathlib",
    "re",
    "typing",
    "unicodedata",
}
FORBIDDEN_CALLS = {
    "__import__",
    "amend_order",
    "cancel_order",
    "create_order",
    "execv",
    "execve",
    "getenv",
    "import_module",
    "popen",
    "place_order",
    "send_order",
    "sign_request",
    "spawnl",
    "spawnv",
    "submit_order",
    "system",
    "urlopen",
}
FORBIDDEN_IDENTIFIERS = {
    "api_key",
    "api_secret",
    "arm_token",
    "private_key",
    "secret_key",
    "venue_credentials",
}


def scan_file(path: pathlib.Path) -> list[str]:
    findings: list[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        return [f"{path}: cannot parse runtime source: {exc}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root not in ALLOWED_MODULE_ROOTS:
                    findings.append(f"{path}:{node.lineno}: unapproved runtime import {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.level == 0:
                root = node.module.split(".", 1)[0]
                if root not in ALLOWED_MODULE_ROOTS:
                    findings.append(
                        f"{path}:{node.lineno}: unapproved runtime import {node.module}"
                    )
        elif isinstance(node, ast.Call):
            name = None
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            if name in FORBIDDEN_CALLS:
                findings.append(f"{path}:{node.lineno}: forbidden capability call {name}")
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_IDENTIFIERS:
            findings.append(f"{path}:{node.lineno}: forbidden credential identifier {node.id}")
        elif isinstance(node, ast.Attribute):
            if node.attr == "environ" or node.attr in FORBIDDEN_IDENTIFIERS:
                findings.append(f"{path}:{node.lineno}: forbidden credential access {node.attr}")
    return findings


def scan_runtime() -> list[str]:
    findings: list[str] = []
    for path in sorted(RUNTIME.rglob("*.py")):
        findings.extend(scan_file(path))
    return findings


def main() -> int:
    findings = scan_runtime()
    if findings:
        for finding in findings:
            print(f"FAIL: {finding}", file=sys.stderr)
        return 1
    print("OK: E02 runtime has no network, credential, or venue-order capability")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
