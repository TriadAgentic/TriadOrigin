"""CO-06 — verification-linkage repair overlay proofs.

Standing proof that ``tools/gen_linkage_repair.py`` + ``docs/control/linkage_repair_overlay.v1.json``
repair the three RC3 verification-linkage blockers additively, deterministically and honestly:

  * the frozen masters (RC1 CSV/HTML) and the frozen RC3/RC4 machine bundles are byte-identical
    before and after the tool runs — masters are never mutated;
  * the overlay is byte-stable across two independent builds;
  * the effective (post-overlay) linkage has zero dangling references, while the raw RC1 links had
    exactly 17 (``CTL-G2/G3-03``);
  * the B09 unique set recomputes to base 1,648 (by id + lineage) WITHOUT the blind summation
    (2,056) that double-counts the 408 RC1 rows;
  * the 17 ``EDGE_UNRESOLVED_PRESERVED`` rows are excluded from the conformance denominator;
  * every disposition is individually recorded (the counts are exact).
"""

from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
TOOL_PATH = ROOT / "tools" / "gen_linkage_repair.py"
OVERLAY_PATH = ROOT / "docs" / "control" / "linkage_repair_overlay.v1.json"


def _load_tool():
    spec = importlib.util.spec_from_file_location("gen_linkage_repair", TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def tool():
    return _load_tool()


@pytest.fixture(scope="module")
def overlay(tool):
    return tool.build_overlay()


# --- masters are never mutated -------------------------------------------------------------------
def test_running_the_tool_leaves_every_master_byte_identical(tool):
    before = tool.master_digests()
    # exercise both the pure builder and the on-disk writer path
    tool.build_overlay()
    tool._write(tool.build_overlay())
    after = tool.master_digests()
    assert before == after, "a master digest changed — the tool must never mutate a frozen master"


def test_frozen_rc3_rc5_bytes_unchanged_by_a_build(tool):
    # RC3 bundle + normative overlay + overlay schema + rc4 bundle are frozen; hash them directly.
    frozen = [
        ROOT / "docs/control/rc3_effective_control_bundle.json",
        ROOT / "docs/control/rc3_normative_overlay.json",
        ROOT / "docs/control/rc3_overlay_schema.json",
        ROOT / "docs/control/rc4_control_bundle.json",
    ]
    import hashlib

    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in frozen if p.is_file()}
    tool.build_overlay()
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in frozen if p.is_file()}
    assert before == after


# --- byte-stability --------------------------------------------------------------------------------
def test_overlay_is_byte_stable_across_two_builds(tool):
    a = tool._canonical_json(tool.build_overlay())
    b = tool._canonical_json(tool.build_overlay())
    assert a == b


def test_on_disk_overlay_matches_the_recomputed_overlay(tool):
    assert OVERLAY_PATH.is_file(), "overlay artifact missing (run: python tools/gen_linkage_repair.py --write)"
    assert OVERLAY_PATH.read_bytes() == tool._canonical_json(tool.build_overlay())


# --- schema / posture ------------------------------------------------------------------------------
def test_schema_and_invariant_posture(overlay):
    assert overlay["schema"] == "triad.linkage_repair_overlay.v1"
    assert overlay["change_order"] == "CO-06"
    assert overlay["mutates_masters"] is False
    assert overlay["posture"] == {
        "venue_environment": "OFF",
        "venue_activation": "OFF",
        "paper_activation": "OFF",
        "shadow_activation": "LIVE",
        "activation_result": "DENIED_SAFE_HOLD",
    }


# --- composite gate representation (RC3-LINK-BLOCK-001) ------------------------------------------
def test_single_composite_gate_representation_applied_uniformly(overlay, tool):
    rep = overlay["composite_gate_representation"]
    assert rep["chosen"] == "TYPED_MULTI_GATE_EDGE"
    assert rep["field"] == "gates"
    # every row carries a typed gates[] array; composites have >1 member, all validated.
    bundle = json.loads((ROOT / "docs/control/rc3_effective_control_bundle.json").read_text())
    real_gates = {g["gate"] for g in bundle["gates"]}
    composite = 0
    for d in overlay["row_dispositions"]:
        assert d["gates"], "row missing typed gates[] edge"
        assert all(m in real_gates for m in d["gates"]), f"{d['verification_id']} has an unreal gate member"
        if d["composite"]:
            composite += 1
            assert len(d["gates"]) > 1
    assert composite == 182, "exactly 182 composite rows expected"
    assert rep["composite_rows"] == 182


# --- CTL-G2/G3-03 danglers (RC3-LINK-BLOCK-002) -------------------------------------------------
def test_ctl_g2g3_03_danglers_individually_retired_not_replaced(overlay):
    br = overlay["blocker_resolutions"]["RC3-LINK-BLOCK-002"]
    assert br["effective_status"] == "UNRESOLVED_SEMANTIC_OWNER_REQUIRED"
    affected = br["affected_verification_ids"]
    assert len(affected) == 17, "exactly 17 SEM danglers expected"
    # each is individually recorded with a typed retired-link disposition; no inferred replacement.
    seen = 0
    for d in overlay["row_dispositions"]:
        if d["verification_id"] in affected:
            seen += 1
            assert d["task_edge_status"] == "TASK_LINK_RETIRED_UNRESOLVED"
            assert d["row_disposition"] == "EDGE_UNRESOLVED_PRESERVED"
            assert d["conformance_countable"] is False
            assert d["retired_task_links"], "retired link not individually recorded"
            for rec in d["retired_task_links"]:
                assert rec["retired_task_id"] == "CTL-G2/G3-03"
                assert rec["disposition"] == "RETIRED_FROM_EFFECTIVE_LINKAGE_PENDING_SEMANTIC_OWNER"
            # NEVER an inferred replacement task edge
            assert "CTL-G2-03" not in d["task_edge_target_tasks"]
            assert "CTL-G3-03" not in d["task_edge_target_tasks"]
    assert seen == 17


# --- required edges for 408 rows (RC3-LINK-BLOCK-003) -------------------------------------------
def test_every_row_required_by_a_real_gate_edge(overlay):
    bundle = json.loads((ROOT / "docs/control/rc3_effective_control_bundle.json").read_text())
    real_tasks = {t["id"] for t in bundle["tasks"]}
    assert len(overlay["row_dispositions"]) == 408
    for d in overlay["row_dispositions"]:
        assert d["gate_edge_status"] == "RESOLVED"
        assert d["gate_edge_target_tasks"], "row lacks a gate edge"
        for anchor in d["gate_edge_target_tasks"]:
            assert anchor in real_tasks, f"gate anchor {anchor} is not a real task"


def test_task_edges_resolved_where_unique_else_unresolved(overlay):
    resolved = [d for d in overlay["row_dispositions"] if d["task_edge_status"] == "RESOLVED"]
    unresolved = [d for d in overlay["row_dispositions"] if d["task_edge_status"] == "TASK_LINK_RETIRED_UNRESOLVED"]
    assert len(resolved) == 391
    assert len(unresolved) == 17
    bundle = json.loads((ROOT / "docs/control/rc3_effective_control_bundle.json").read_text())
    real_tasks = {t["id"] for t in bundle["tasks"]}
    for d in resolved:
        assert d["task_edge_target_tasks"]
        assert all(t in real_tasks for t in d["task_edge_target_tasks"])


def test_acceptance_edges_uniformly_unresolved_preserved(overlay):
    for d in overlay["row_dispositions"]:
        assert d["acceptance_edge_status"] == "EDGE_UNRESOLVED_PRESERVED"
        assert d["acceptance_edge_target_criteria"] == []


# --- dangling references --------------------------------------------------------------------------
def test_zero_effective_dangling_references(tool, overlay):
    assert overlay["effective_dangling_references"] == []
    assert tool.effective_dangling_references(overlay) == []


def test_pre_overlay_dangling_was_the_seventeen_ctl_danglers(overlay):
    pre = overlay["pre_overlay_dangling_references"]
    assert pre == {"CTL-G2/G3-03": 17}, "the raw RC1 links had exactly 17 dangling CTL-G2/G3-03 refs"


# --- B09 unique-set recomputation -----------------------------------------------------------------
def test_b09_base_1648_without_blind_summation(tool, overlay):
    b09 = tool.recompute_b09(overlay)
    assert b09["unique_verification_ids"] == 1523
    assert b09["rc4_fixtures"] == 125
    assert b09["rc1_lineage_rows"] == 408
    assert b09["base_unique_population"] == 1648
    # the blind summation double-counts the 408 lineage rows
    assert b09["blind_summation_rejected"] == 2056
    assert b09["base_unique_population"] != b09["blind_summation_rejected"]
    # overlay's stored numbers agree with the fresh recomputation
    stored = overlay["b09_unique_set"]
    for k, v in b09.items():
        assert stored[k] == v


def test_edge_unresolved_rows_excluded_from_conformance_denominator(tool, overlay):
    b09 = tool.recompute_b09(overlay)
    assert b09["edge_unresolved_preserved_count"] == 17
    # denominator excludes the preserved-but-uncountable rows
    assert b09["conformance_denominator"] == 1648 - 17 == 1631
    countable = [d for d in overlay["row_dispositions"] if d["conformance_countable"]]
    uncountable = [d for d in overlay["row_dispositions"] if not d["conformance_countable"]]
    assert len(countable) == 391
    assert len(uncountable) == 17


# --- every disposition individually recorded ------------------------------------------------------
def test_every_disposition_individually_recorded(overlay):
    c = overlay["counts"]
    assert c["rc1_dispositions"] == 408
    assert len(overlay["row_dispositions"]) == 408
    # no duplicate rows
    ids = [d["verification_id"] for d in overlay["row_dispositions"]]
    assert len(set(ids)) == 408
    assert c["composite_rows"] == 182
    assert c["task_edge_resolved_rows"] == 391
    assert c["edge_unresolved_preserved_rows"] == 17
    assert c["retired_link_dispositions"] == 17
    # the three blocker resolutions are all present and honest about their status
    br = overlay["blocker_resolutions"]
    assert set(br) == {"RC3-LINK-BLOCK-001", "RC3-LINK-BLOCK-002", "RC3-LINK-BLOCK-003"}
    assert br["RC3-LINK-BLOCK-001"]["effective_status"] == "MATERIALIZED_AWAITING_SIGNED_CLOSURE"
    assert br["RC3-LINK-BLOCK-003"]["effective_status"] == "MATERIALIZED_AWAITING_SIGNED_CLOSURE"


def test_no_open_blocker_flipped_to_resolved(overlay):
    # honest boundary: the overlay never claims a signed RESOLVED terminal state.
    blob = json.dumps(overlay)
    assert "RESOLVED_BY_SIGNED_EVENT" not in blob
    for br in overlay["blocker_resolutions"].values():
        assert br["effective_status"] != "RESOLVED"


# --- rc5 dependency honestly recorded when absent -------------------------------------------------
def test_rc5_dependency_recorded_honestly(overlay):
    rc5 = overlay["reads"]["rc5_bundle"]
    if rc5.get("sha256") is None:
        assert rc5["status"] == "ABSENT_DEPENDENCY_NOT_LANDED"
    else:
        assert len(rc5["sha256"]) == 64
