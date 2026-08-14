#!/usr/bin/env python3
"""C.3 static gate — formula entrypoints consume the capability + E01 envelope only.

TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12 §C.3: raw dict parameters and raw
``transition.require()`` on production formula paths are DELETED. This gate fails the build on
any of, inside a production formula module:

* ``Params = dict`` (the raw-parameter alias),
* ``dict[str, Any]`` / ``Dict[str, Any]`` in an ``evaluate``/public entrypoint signature,
* a call of ``transition.require(`` / bare ``require(params`` outside the capability module,
* construction of a ``ValidatedInput`` type (``ValidatedBar``/``ValidatedTrade``/
  ``ValidatedBookUpdate``) outside ``e01_interface``.

FAIL-CLOSED RATCHET. Conversion lands formula-by-formula across B03C/B04C/B06R (a v1 module is
converted in the same commit series that repairs it — §1.6 order). Until then the not-yet-
converted legacy modules are pinned in ``LEGACY_UNCONVERTED`` below. The ratchet is two-sided:

* a module with violations that is NOT pinned fails the build (no new raw-dict surface, ever);
* a pinned module that has become clean fails the build as a STALE pin (the pin must be removed
  in the converting commit — the set only shrinks, and the empty set is the exit criterion).

RETIRED modules (a ``RETIRED_DEFECTIVE`` withdrawal banner per §1.5) keep their original bytes
by law and are exempt from conversion — but each must have a non-retired successor module
present, so retirement can never silently remove a formula's production surface.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "triad_origin"
STRUCTURES = SRC / "structures"

# The production formula surface (F00-F19 homes). Non-formula machines (lifecycle_reducer,
# trial_registry, candidate_publisher, capsules, common, structure_state plumbing) are outside
# C.3's "formula modules" scope and keep the shared transition machinery.
FORMULA_MODULE_NAMES = (
    "displacement.py",            # F11 (R-F11 in-place conversion — must scan clean)
    "excursion_reclaim_registry.py",  # F13 (v1, retired R-F13)
    "excursion_reclaim_v2.py",    # F13 machine (R-F13, converted — must scan clean)
    "excursion_reclaim_registry_v2.py",  # F13 v2 registry face (converted)
    "reaction.py",                # F14 (v1, retired R-F14)
    "reaction_v2.py",             # F14 machine (R-F14, converted — must scan clean)
    "flow_atoms.py",              # F15/F16/F17 (v1, retired R-F15/16/17)
    "flow_atoms_v2.py",           # F15/F16/F17 machine (converted — must scan clean)
    "fvg_registry.py",            # F10 (v2, retired R-F10)
    "fvg_registry_v3.py",         # F10 machine (R-F10, converted — must scan clean)
    "order_block_registry.py",    # F12 (v1, retired R-F12)
    "order_block_v2.py",          # F12 machine (R-F12, converted — must scan clean)
    "order_block_registry_v2.py", # F12 v2 registry face (converted)
    "typed_level_registry.py",    # F03/F04/F06 levels (v1)
    "structure_state.py",         # F09 (v1 host; F08 raw sites stay until F08's own train)
    "break_v2.py",                # F09 machine (R-F09, converted — must scan clean)
    "swing_dc_v2.py",             # F03 machine (R-F03, converted — must scan clean)
    "clustering.py",              # F19 (v1, retired R-F19)
    "clustering_v2.py",           # F19 machine (R-F19, converted — must scan clean)
    "candidate_geometry.py",      # F18 geometry home
)

# Formula homes at the package root (outside structures/).
ROOT_FORMULA_MODULE_NAMES = (
    "features.py",                # F02/F05 rolling windows
)

# Fail-closed ratchet: modules awaiting their §1.6 repair commit. REMOVE each entry in the same
# commit series that converts the module; an entry whose module scans clean is a build failure.
LEGACY_UNCONVERTED: set[str] = {
    "typed_level_registry.py",
    "structure_state.py",  # shared host: live F08 raw sites remain (§1.6 F06/F08 untouched)
    "candidate_geometry.py",
    "features.py",
}

RETIRED_BANNER = "RETIRED_DEFECTIVE"
VALIDATED_INPUT_TYPES = ("ValidatedBar", "ValidatedTrade", "ValidatedBookUpdate")

_RAW_ALIAS = re.compile(r"^\s*Params\s*=\s*dict", re.MULTILINE)
_RAW_SIG = re.compile(r"def\s+\w*evaluate\w*\s*\([^)]*[Dd]ict\[str,\s*Any\]", re.DOTALL)
_RAW_REQUIRE = re.compile(r"(?:transition\.)?require\(\s*params")


def _constructs_validated_input(text: str) -> bool:
    """AST-precise: a CALL of a ValidatedInput type (never a type-identity check or prose)."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False  # the other regex findings still fire; unparseable never hides a ctor
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else (
            func.attr if isinstance(func, ast.Attribute) else None)
        if name in VALIDATED_INPUT_TYPES:
            return True
    return False


def module_is_retired(text: str) -> bool:
    """A module is retired ONLY when its MODULE docstring carries the withdrawal banner.

    A class-level ``RETIRED_DEFECTIVE`` banner inside a module that still hosts live law (the
    typed_level_registry / structure_state pattern — one machine retired, siblings live) does NOT
    exempt the module: its live surfaces still convert. A PROSE MENTION of the token inside a
    successor module's docstring ("repairs the retired v1, banner ``RETIRED_DEFECTIVE{...}``")
    is NOT a banner either: the banner line carries the token with nothing before it but
    whitespace/backticks and nothing after the closing brace but whitespace/backticks/dash-or-dot
    punctuation (the instrument_math.py warning-block and excursion_reclaim_registry.py
    first-line forms).
    """
    try:
        doc = ast.get_docstring(ast.parse(text))
    except SyntaxError:
        return False  # unparseable is never exempt — fail toward scanning
    if not doc:
        return False
    for line in doc.splitlines():
        stripped = line.strip().strip("`").lstrip()
        if not stripped.startswith(RETIRED_BANNER + "{"):
            continue
        close = stripped.find("}")
        if close < 0:
            continue
        tail = stripped[close + 1:].strip().strip("`").strip()
        if all(ch in "—–-. " for ch in tail):
            return True
    return False


def scan_module(path: pathlib.Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    if module_is_retired(text):
        return []  # retired bytes are preserved by §1.5 law; successor presence checked below
    findings: list[str] = []
    if _RAW_ALIAS.search(text):
        findings.append("raw Params = dict alias")
    if _RAW_SIG.search(text):
        findings.append("dict[str, Any] in an evaluate signature")
    if _RAW_REQUIRE.search(text):
        findings.append("raw transition.require(params, ...) on a production path")
    if path.name != "e01_interface.py" and _constructs_validated_input(text):
        # Constructing a ValidatedInput outside the E01 boundary forges an envelope.
        findings.append("ValidatedInput constructed outside e01_interface")
    return findings


def main() -> int:
    failures: list[str] = []
    seen_retired: list[str] = []
    targets = [(name, STRUCTURES / name) for name in FORMULA_MODULE_NAMES]
    targets += [(name, SRC / name) for name in ROOT_FORMULA_MODULE_NAMES]
    for name, path in targets:
        if not path.exists():
            failures.append(f"{name}: formula module missing")
            continue
        text = path.read_text(encoding="utf-8")
        if module_is_retired(text):
            seen_retired.append(name)
        findings = scan_module(path)
        pinned = name in LEGACY_UNCONVERTED
        if findings and not pinned:
            for f in findings:
                failures.append(f"{name}: {f} (module is not pinned LEGACY_UNCONVERTED)")
        if pinned and not findings:
            failures.append(
                f"{name}: pinned LEGACY_UNCONVERTED but scans clean — remove the stale pin "
                f"in the converting commit (the ratchet only shrinks)")
    # Retirement never removes a production surface: every retired v1 needs a live successor.
    for name in seen_retired:
        stem = name[: -len(".py")]
        successors = sorted(STRUCTURES.glob(f"{stem}_v*.py")) + sorted(SRC.glob(f"{stem}_v*.py"))
        if not successors:
            failures.append(f"{name}: RETIRED_DEFECTIVE without a versioned successor module")
    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    unconverted = sorted(LEGACY_UNCONVERTED)
    total = len(FORMULA_MODULE_NAMES) + len(ROOT_FORMULA_MODULE_NAMES)
    print(
        "OK: formula entrypoint gate — "
        f"{total} modules scanned; ratchet pins remaining: "
        f"{len(unconverted)} ({', '.join(unconverted) if unconverted else 'none'})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
