"""Identity hierarchy determinism and stability (Doc 03 §03.4, Doc 02 §02.16 identity stability)."""

from __future__ import annotations

import pytest

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


def test_opportunity_cluster_deduplicates_after_unicode_normalization():
    composed = "hyp_é"
    decomposed = "hyp_e\u0301"
    assert ids.opportunity_cluster_id([composed, decomposed]) == (
        ids.opportunity_cluster_id([composed])
    )


def test_direction_changes_identity():
    si = ids.semantic_instance_id("f.v1", "pd", "V", "15m")
    long_ = ids.structure_id("INSTR", "V", "SWING", si, "LONG", ["s1"], "geo")
    short_ = ids.structure_id("INSTR", "V", "SWING", si, "SHORT", ["s1"], "geo")
    assert long_ != short_


@pytest.mark.parametrize("bad", [1, True, b"f", ""])
def test_public_identity_fields_reject_type_aliases(bad):
    with pytest.raises(TypeError):
        ids.semantic_instance_id(bad, "pd", "V", "15m")
    with pytest.raises(TypeError):
        ids.opportunity_cluster_id([bad])


def test_identity_iterables_reject_scalar_string_aliases():
    semantic = ids.semantic_instance_id("f", "pd", "V", "1m")
    with pytest.raises(TypeError):
        ids.structure_id("I", "V", "K", semantic, "LONG", "ab", "geo")
    with pytest.raises(TypeError):
        ids.opportunity_cluster_id("ab")


def test_order_semantic_identity_rejects_unordered_sources():
    semantic = ids.semantic_instance_id("f", "pd", "V", "1m")
    with pytest.raises(TypeError, match="ordered sequence"):
        ids.structure_id("I", "V", "K", semantic, "LONG", {"a", "b"}, "geo")


def test_identity_fields_reject_non_wire_unicode():
    with pytest.raises(TypeError, match="canonical-wire"):
        ids.opportunity_cluster_id(["hyp_\ud800"])
