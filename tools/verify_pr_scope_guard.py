#!/usr/bin/env python3
"""CO-12 — PR scope guard (TRIAD-ORIGIN-V7-CHANGE-ORDERS-2026-08-12, CO-12 step 1).

The G2 root PR (PR #34 class) must stay governance-only: formula modules, B08 read faces, and
B09 artifacts must never ride a governance-only PR.  This tool is the guard's CI-callable core;
the CI workflow that invokes it is CI-owned and lands through the CI owner's lane.

Inputs (fail-closed — exactly one path source, class mandatory):

  * ``--pr-class {governance-only,non-governance}`` — the declared PR class. Only
    ``governance-only`` applies the deny sets; ``non-governance`` records the class and applies
    no deny set here (its own guards live with its own lane). Any other value refuses.
  * ``--paths FILE`` — newline-separated changed paths, or
  * ``--diff-range A..B`` — resolved via ``git diff --name-only`` in the repository.

A governance-only change set fails if it touches:

  * FORMULA MODULES — ``src/triad_origin/structures/``, ``src/triad_origin/features.py``,
    ``src/triad_origin/instrument_math.py`` / ``instrument_math_v2.py``,
    ``src/triad_origin/config/`` (the sealed formula-parameter surface), or
    ``contracts/schemas/`` formula/golden trees under ``contracts/``;
  * B08 FACES — ``contracts/read_faces/``, ``src/triad_origin/control/``, the B08 adoption
    manifest/receipt/evidence namespaces;
  * B09 ARTIFACTS — ``docs/runbooks/``, the B09 adoption manifest/receipt/evidence namespaces.

Unsafe paths (absolute, ``..``, backslash, control characters) refuse.  An empty change set
refuses — a guard asked to certify nothing is a misuse, not a pass.  This tool grants no
authority and closes nothing; exit 0 means only that the declared class and the changed-path
set are consistent.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

PR_CLASSES = ("governance-only", "non-governance")

FORMULA_MODULE_PREFIXES = (
    "src/triad_origin/structures/",
    "src/triad_origin/config/",
    "contracts/schemas/",
    "contracts/goldens/",
)
FORMULA_MODULE_EXACT = (
    "src/triad_origin/features.py",
    "src/triad_origin/instrument_math.py",
    "src/triad_origin/instrument_math_v2.py",
)
B08_FACE_PREFIXES = (
    "contracts/read_faces/",
    "src/triad_origin/control/",
    "evidence/B08/",
)
B08_FACE_EXACT = (
    "contracts/adoption/B08.manifest.v1.json",
    "docs/control/adoption/B08.v1.json",
    "evidence/receipts/B08.receipt.v4.json",
)
B09_ARTIFACT_PREFIXES = (
    "docs/runbooks/",
    "evidence/B09/",
)
B09_ARTIFACT_EXACT = (
    "contracts/adoption/B09.manifest.v1.json",
    "docs/control/adoption/B09.v1.json",
    "evidence/receipts/B09.receipt.v4.json",
)

DENY_SETS = (
    ("FORMULA_MODULE", FORMULA_MODULE_PREFIXES, FORMULA_MODULE_EXACT),
    ("B08_FACE", B08_FACE_PREFIXES, B08_FACE_EXACT),
    ("B09_ARTIFACT", B09_ARTIFACT_PREFIXES, B09_ARTIFACT_EXACT),
)


class ScopeGuardError(ValueError):
    """A changed-path set cannot be lawfully evaluated."""


def safe_path(path: str) -> bool:
    if not path or path.startswith("/") or "\\" in path:
        return False
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in path):
        return False
    parts = path.split("/")
    return all(part not in ("", ".", "..") for part in parts)


def classify_path(path: str) -> str | None:
    """Return the deny-class name for a path under the governance-only class, else None."""
    for name, prefixes, exacts in DENY_SETS:
        if path in exacts or any(path.startswith(prefix) for prefix in prefixes):
            return name
    return None


def evaluate(pr_class: str, paths: list[str]) -> list[str]:
    """Return violation strings (empty = clean). Raises ScopeGuardError on unusable input."""
    if pr_class not in PR_CLASSES:
        raise ScopeGuardError(f"unknown PR class {pr_class!r}; refusing (fail-closed)")
    if not paths:
        raise ScopeGuardError("empty changed-path set; a guard over nothing is a misuse")
    violations: list[str] = []
    for path in paths:
        if not safe_path(path):
            raise ScopeGuardError(f"unsafe path {path!r}; refusing (fail-closed)")
    if pr_class != "governance-only":
        return []
    for path in paths:
        deny = classify_path(path)
        if deny is not None:
            violations.append(
                f"{deny}: {path} may not ride a governance-only PR"
                " (CO-12: formula modules, B08 faces and B09 artifacts land through their own lanes)"
            )
    return violations


def paths_from_file(path: pathlib.Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip()]


def paths_from_diff(diff_range: str, root: pathlib.Path) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", diff_range],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ScopeGuardError(f"git diff {diff_range!r} failed: {result.stderr.strip()}")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr-class", required=True, help="Declared PR class (mandatory).")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--paths", help="File of newline-separated changed paths.")
    source.add_argument("--diff-range", help="Git range A..B resolved via git diff --name-only.")
    parser.add_argument("--root", default=str(ROOT), help="Repository root (tests only).")
    args = parser.parse_args(argv)
    root = pathlib.Path(args.root)
    try:
        if args.paths:
            paths = paths_from_file(pathlib.Path(args.paths))
        else:
            paths = paths_from_diff(args.diff_range, root)
        violations = evaluate(args.pr_class, paths)
    except (OSError, ScopeGuardError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    if violations:
        for violation in violations:
            print(f"FAIL: {violation}", file=sys.stderr)
        return 1
    print(
        f"OK: {len(paths)} changed path(s) consistent with PR class {args.pr_class!r}"
        " (scope consistency only; this certifies no gate and closes nothing)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
