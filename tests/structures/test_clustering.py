"""F19 ``opportunity_cluster.v1`` — RETIRED_DEFECTIVE posture only (repair spec §1.5).

The v1 clustering machine is retired by R-F19 (repaired as ``opportunity_cluster.v2``,
:mod:`triad_origin.structures.clustering_v2`). Its bytes/logic are preserved unchanged by the §1.5
withdrawal law — never edited in place, never deleted — so this file no longer exercises the v1
semantics; it asserts the withdrawal posture: the module carries the ``RETIRED_DEFECTIVE`` banner in
its MODULE docstring, a versioned successor is present, and the frozen v1 surface still imports.
"""

from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin.structures import clustering  # noqa: E402


def _banner_line_present(doc: str) -> bool:
    """The C.3-gate banner law: the token stands alone on its line, only a dash/whitespace tail."""
    for line in (doc or "").splitlines():
        stripped = line.strip().strip("`").lstrip()
        if not stripped.startswith("RETIRED_DEFECTIVE{"):
            continue
        close = stripped.find("}")
        if close < 0:
            continue
        tail = stripped[close + 1:].strip().strip("`").strip()
        if all(ch in "—–-. " for ch in tail):
            return True
    return False


def test_v1_module_carries_the_retired_defective_banner():
    doc = ast.get_docstring(ast.parse(pathlib.Path(clustering.__file__).read_text("utf-8")))
    assert _banner_line_present(doc)
    assert "R-F19" in doc


def test_v2_successor_module_is_present():
    successor = pathlib.Path(clustering.__file__).with_name("clustering_v2.py")
    assert successor.is_file()
    from triad_origin.structures import clustering_v2
    assert clustering_v2.V2_FORMULA_VERSION == "opportunity_cluster.v2"
    assert clustering_v2.RETIRED_PREDECESSOR == "opportunity_cluster.v1"


def test_frozen_v1_bytes_still_import():
    # The withdrawal law preserves the v1 machine bytes; it must still be importable/constructible.
    machine = clustering.OpportunityClusterRegistry()
    assert machine.initial_state() == {"candidates": {}, "clusters": {}, "cluster_aliases": {}}
