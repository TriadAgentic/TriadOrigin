"""B06 semantic capsule registry: explicit binding, no RC2-ordinal aliasing, isolation."""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin.structures import capsules  # noqa: E402


class TestCanonicalIds:
    def test_exactly_five_capsules(self):
        assert len(capsules.CANONICAL_SEMANTIC_IDS) == 5

    def test_the_five_stable_ids(self):
        assert set(capsules.CANONICAL_SEMANTIC_IDS) == {
            "dc_swing_bos_first_retest.v1",
            "protected_swing_choch_first_retest.v1",
            "fvg_displacement_first_touch.v1",
            "ob_displacement_bos_first_touch.v1",
            "level_excursion_reclaim_flow_confirmed.v1",
        }

    @pytest.mark.parametrize("semantic_id", capsules.CANONICAL_SEMANTIC_IDS)
    def test_every_canonical_id_resolves(self, semantic_id):
        definition = capsules.resolve_capsule(semantic_id)
        assert definition.semantic_id == semantic_id
        assert definition.structural_formulas


class TestNoOrdinalAliasing:
    @pytest.mark.parametrize("ordinal", ["CAP01_OB_ENTRY", "CAP02_FVG_ENTRY",
                                         "CAP03_EQUAL_SWEEP_ENTRY", "CAP04_CHOCH_ENTRY",
                                         "CAP05_SESSION_ENTRY", "CAP01", "cap01_ob_entry.v1"])
    def test_rc2_ordinal_spellings_never_resolve(self, ordinal):
        with pytest.raises(capsules.CapsuleUnavailableError):
            capsules.resolve_capsule(ordinal)

    def test_unknown_id_refused(self):
        with pytest.raises(capsules.CapsuleUnavailableError):
            capsules.resolve_capsule("not_a_capsule.v1")


class TestExplicitBinding:
    def test_ob_capsule_bound_to_par_174(self):
        d = capsules.resolve_capsule("ob_displacement_bos_first_touch.v1")
        assert d.entry_anchor_par_id == "PAR-174"
        assert d.entry_anchor_rule == "zone_midpoint"

    def test_fvg_capsule_bound_to_par_175(self):
        d = capsules.resolve_capsule("fvg_displacement_first_touch.v1")
        assert d.entry_anchor_par_id == "PAR-175"
        assert "F10" in d.structural_formulas

    def test_equal_sweep_capsule_bound_to_par_176(self):
        d = capsules.resolve_capsule("level_excursion_reclaim_flow_confirmed.v1")
        assert d.entry_anchor_par_id == "PAR-176"
        assert "F06" in d.structural_formulas and "F13" in d.structural_formulas

    def test_choch_capsule_bound_to_par_177(self):
        d = capsules.resolve_capsule("protected_swing_choch_first_retest.v1")
        assert d.entry_anchor_par_id == "PAR-177"
        assert "F08" in d.structural_formulas and "F09" in d.structural_formulas

    def test_dc_swing_capsule_has_no_capsule_specific_override(self):
        d = capsules.resolve_capsule("dc_swing_bos_first_retest.v1")
        assert d.entry_anchor_rule is None
        assert d.entry_anchor_par_id is None
        assert d.source_par_id is None


class TestOrphanedLegacyRow:
    def test_par_178_is_registered_but_unbound(self):
        assert "PAR-178" in capsules.ORPHANED_LEGACY_PARAMETERS
        row = capsules.ORPHANED_LEGACY_PARAMETERS["PAR-178"]
        assert row["legacy_name"] == "CAP05_SESSION_ENTRY"
        for definition in capsules.CANONICAL_SEMANTIC_IDS:
            d = capsules.resolve_capsule(definition)
            assert d.source_par_id != "PAR-178"


class TestIsolation:
    def test_capsule_digest_is_stable_and_distinct_per_capsule(self):
        digests = {struct_ident: capsules.capsule_digest(capsules.resolve_capsule(struct_ident))
                   for struct_ident in capsules.CANONICAL_SEMANTIC_IDS}
        assert len(set(digests.values())) == 5  # every capsule has a distinct identity
        # Determinism: recomputing yields the exact same digest.
        again = capsules.capsule_digest(capsules.resolve_capsule("fvg_displacement_first_touch.v1"))
        assert again == digests["fvg_displacement_first_touch.v1"]

    def test_natural_invalidation_buffer_reuses_the_f09_declared_rule(self):
        from triad_origin.structures import common
        assert capsules.DECLARED_NATURAL_INVALIDATION_BUFFER == common.DECLARED_BOS_CLOSE_BUFFER
