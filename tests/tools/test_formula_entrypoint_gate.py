"""C.3 static gate (`tools/verify_formula_entrypoints.py`) — the fail-closed ratchet works.

Formula Repair spec §C.3: the CI scan fails the build on raw-dict formula surfaces, and the
ratchet allowlist only ever shrinks (a stale pin is itself a failure).
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
TOOL = ROOT / "tools" / "verify_formula_entrypoints.py"
sys.path.insert(0, str(ROOT / "tools"))

import verify_formula_entrypoints as gate  # noqa: E402


def test_gate_passes_on_the_current_tree() -> None:
    proc = subprocess.run(
        [sys.executable, str(TOOL)], capture_output=True, text=True, cwd=str(ROOT))
    assert proc.returncode == 0, proc.stderr
    assert "ratchet pins remaining" in proc.stdout


def test_every_pin_names_a_real_module_with_real_violations() -> None:
    # A pinned-but-clean module is a stale pin (build failure) — so every current pin must have
    # at least one live finding, and every pinned name must exist on disk.
    for name in sorted(gate.LEGACY_UNCONVERTED):
        path = (gate.SRC / name) if name in gate.ROOT_FORMULA_MODULE_NAMES else (gate.STRUCTURES / name)
        assert path.exists(), f"stale pin: {name} does not exist"
        assert gate.scan_module(path), f"stale pin: {name} scans clean — remove it"


def test_raw_alias_and_raw_require_are_detected(tmp_path: pathlib.Path) -> None:
    bad = tmp_path / "bad_formula.py"
    bad.write_text(
        '"""a formula module."""\n'
        "Params = dict\n"
        "def evaluate(params: dict[str, Any]):\n"
        "    return require(params, 'x')\n",
        encoding="utf-8",
    )
    findings = gate.scan_module(bad)
    assert any("Params = dict" in f for f in findings)
    assert any("evaluate signature" in f for f in findings)
    assert any("transition.require" in f for f in findings)


def test_validated_input_construction_outside_e01_is_detected(tmp_path: pathlib.Path) -> None:
    bad = tmp_path / "forger.py"
    bad.write_text('"""x."""\nv = ValidatedBar(1, 2, 3)\n', encoding="utf-8")
    assert any("outside e01_interface" in f for f in gate.scan_module(bad))


def test_class_level_retired_banner_does_not_exempt_a_live_module(tmp_path: pathlib.Path) -> None:
    mixed = tmp_path / "mixed.py"
    mixed.write_text(
        '"""live module hosting one retired machine."""\n'
        "class OldMachine:\n"
        '    """RETIRED_DEFECTIVE{defect_ref=X}."""\n'
        "Params = dict\n",
        encoding="utf-8",
    )
    assert gate.scan_module(mixed), "a class-level banner must not exempt live module surfaces"


def test_module_docstring_banner_exempts_preserved_bytes(tmp_path: pathlib.Path) -> None:
    retired = tmp_path / "retired.py"
    retired.write_text(
        '"""RETIRED_DEFECTIVE{defect_ref=R-FXX} — preserved v1 bytes."""\n'
        "Params = dict\n",
        encoding="utf-8",
    )
    assert gate.scan_module(retired) == []
