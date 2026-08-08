"""Identity hierarchy determinism and stability (Doc 03 §03.4, Doc 02 §02.16 identity stability)."""

from __future__ import annotations

from triad_origin import ids


def test_semantic_instance_deterministic():
    a = ids.semantic_instance_id("dc_swing.v1", "pd_deadbeef", "BINANCE_USDM", "15m")
    b = ids.semantic_instance_id("dc_swing.v1", "pd_deadbeef", "BINANCE_USDM", "15m")
    assert a == b and a.startswith("sinst_")


def test_structure_id_depends_on_source_order():
    si = ids.semantic_instance_id("f.v1", "pd", "V", "15m")
    a = ids.structure_id("INSTR", "V", "SWING", si, "LONG", ["s1", "s2"], "geo")
    b = ids.structure_id("INSTR", "V", "SWING", si, "LONG", ["s2", "s1"], "geo")
    assert a != b and a.startswith("str_")


def test_full_chain_deterministic():
    si = ids.semantic_instance_id("f.v1", "pd", "V", "15m")
    st = ids.structure_id("INSTR", "V", "SWING", si, "LONG", ["s1"], "geo")
    rc = ids.reaction_id(st, "first_retest.v1", ["t1"])
    hy = ids.hypothesis_id(rc, "cap.v1", "pd")
    cd = ids.candidate_id(hy, "cand.v1", "occ1")
    assert cd.startswith("cand_")
    # recompute identical chain -> identical candidate id
    st2 = ids.structure_id("INSTR", "V", "SWING", si, "LONG", ["s1"], "geo")
    rc2 = ids.reaction_id(st2, "first_retest.v1", ["t1"])
    hy2 = ids.hypothesis_id(rc2, "cap.v1", "pd")
    cd2 = ids.candidate_id(hy2, "cand.v1", "occ1")
    assert cd == cd2


def test_opportunity_cluster_is_order_insensitive():
    a = ids.opportunity_cluster_id(["hyp_a", "hyp_b"])
    b = ids.opportunity_cluster_id(["hyp_b", "hyp_a", "hyp_a"])
    assert a == b and a.startswith("opp_")


def test_direction_changes_identity():
    si = ids.semantic_instance_id("f.v1", "pd", "V", "15m")
    long_ = ids.structure_id("INSTR", "V", "SWING", si, "LONG", ["s1"], "geo")
    short_ = ids.structure_id("INSTR", "V", "SWING", si, "SHORT", ["s1"], "geo")
    assert long_ != short_
