"""F18 candidate-geometry battery: GV-015, target selection, unreduced RR, mirror, fail-closed."""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin.structures import candidate_geometry, capsules, common  # noqa: E402
from triad_origin.structures.common import StructureLawError  # noqa: E402
from triad_origin.transition import MissingParameterError  # noqa: E402

CAPSULE_ID = "fvg_displacement_first_touch.v1"

PARAMS = {
    capsules.PAR_NATURAL_INVALIDATION_BUFFER_RULE: capsules.DECLARED_NATURAL_INVALIDATION_BUFFER,
    capsules.PAR_TARGET_AVAILABILITY_RULE: capsules.TARGET_AVAILABILITY_RULE,
    capsules.PAR_TARGET_SELECTOR: capsules.TARGET_SELECTOR_PRIORITY,
    candidate_geometry.PARAM_MIN_GEOMETRIC_RR_RULE: candidate_geometry.DECLARED_MIN_GEOMETRIC_RR,
}


def target(target_type, target_ticks, knowledge_time_us=0, root_id="t"):
    return {"target_type": target_type, "target_ticks": target_ticks,
            "knowledge_time_us": knowledge_time_us, "root_id": root_id}


def evaluate(
    direction=common.LONG,
    entry=100,
    source=99,
    atr=20,
    targets=None,
    knowledge_time=1_000,
    capsule_id=CAPSULE_ID,
    params=None,
):
    if targets is None:
        targets = [target("PROTECTED_SWING", 104)]
    return candidate_geometry.evaluate_candidate_geometry(
        direction=direction,
        entry_reference_ticks=entry,
        natural_invalidation_source_ticks=source,
        atr14_ticks=atr,
        capsule_semantic_id=capsule_id,
        available_targets=targets,
        candidate_knowledge_time_us=knowledge_time,
        params=params if params is not None else PARAMS,
    )


class TestGv015:
    def test_exact_pass_admits_with_unreduced_rr(self):
        # entry=100, source=99, atr=20 -> buffer=max(1,ceil(20/20))=1 -> stop=99-1=98 -> risk=2.
        result = evaluate(targets=[target("PROTECTED_SWING", 104)])
        assert result.admitted is True
        assert result.risk_ticks == 2
        assert result.reward_ticks == 4
        assert result.rr_numerator == 4
        assert result.rr_denominator == 2  # unreduced (4, 2), not simplified to (2, 1)
        assert result.entry_reference_ticks == 100
        assert result.natural_invalidation_ticks == 98
        assert result.selected_target_ticks == 104
        assert result.selected_target_type == "PROTECTED_SWING"
        assert result.abstain_reason is None
        assert result.abstain_detail is None

    def test_one_tick_below_floor_abstains(self):
        # Same setup, T=103: reward=3; 3*1=3 is NOT >= 2*2=4.
        result = evaluate(targets=[target("PROTECTED_SWING", 103)])
        assert result.admitted is False
        assert result.risk_ticks == 2
        assert result.reward_ticks == 3
        assert result.rr_numerator is None
        assert result.rr_denominator is None
        assert result.abstain_reason == candidate_geometry.ABSTAIN_GEOMETRY_BELOW_FLOOR


class TestInvalidStopSide:
    def test_long_wrong_side_stop_abstains_never_admits(self):
        # LONG E=100, source=105, atr=20 -> buffer=1 -> stop=105-1=104, ABOVE entry: invalid.
        # abs(100-104)=4 would otherwise read as a valid positive risk; must abstain instead.
        result = evaluate(direction=common.LONG, entry=100, source=105, atr=20,
                          targets=[target("PROTECTED_SWING", 110)])
        assert result.admitted is False
        assert result.abstain_reason == candidate_geometry.ABSTAIN_INVALID_STOP_SIDE
        assert result.risk_ticks is None
        assert result.reward_ticks is None
        assert result.entry_reference_ticks == 100
        assert result.natural_invalidation_ticks == 104

    def test_short_wrong_side_stop_abstains_never_admits(self):
        # SHORT mirror: E=100, source=95, atr=20 -> buffer=1 -> stop=95+1=96, BELOW entry: invalid.
        result = evaluate(direction=common.SHORT, entry=100, source=95, atr=20,
                          targets=[target("PROTECTED_SWING", 90)])
        assert result.admitted is False
        assert result.abstain_reason == candidate_geometry.ABSTAIN_INVALID_STOP_SIDE
        assert result.natural_invalidation_ticks == 96

    def test_stop_exactly_at_entry_still_reaches_zero_risk_not_invalid_side(self):
        # The exact-equality boundary is untouched: LONG stop==entry stays ABSTAIN_ZERO_RISK.
        result = evaluate(direction=common.LONG, entry=100, source=101, atr=20,
                          targets=[target("PROTECTED_SWING", 110)])
        assert result.abstain_reason == candidate_geometry.ABSTAIN_ZERO_RISK

    def test_long_correct_side_stop_still_admits(self):
        # The valid, documented GV-015 case is unaffected by the new side check.
        result = evaluate(targets=[target("PROTECTED_SWING", 104)])
        assert result.admitted is True


class TestZeroRisk:
    def test_entry_and_buffered_stop_coincide_abstains(self):
        # source=101, atr=20 -> buffer=1 -> stop=101-1=100 == entry.
        result = evaluate(source=101, targets=[target("PROTECTED_SWING", 110)])
        assert result.admitted is False
        assert result.abstain_reason == candidate_geometry.ABSTAIN_ZERO_RISK
        assert result.risk_ticks == 0
        assert result.natural_invalidation_ticks == 100
        assert result.reward_ticks is None


class TestNonpositiveReward:
    def test_only_a_nonpositive_reward_target_yields_no_target(self):
        # A target at or behind entry has dir_sign*(T-E) <= 0, so PAR-173's own
        # nearest_positive_reward filter excludes it during selection — the observable law is
        # F18_NO_TARGET, never a fabricated candidate. (F18_NONPOSITIVE_REWARD is the module's
        # internal re-verification of the selector's own guarantee; see the module docstring for
        # why it is unreachable through this public entry point.)
        result = evaluate(targets=[target("PROTECTED_SWING", 100),  # reward == 0, excluded
                                   target("SESSION_LEVEL", 90)])     # reward < 0, excluded
        assert result.admitted is False
        assert result.abstain_reason == candidate_geometry.ABSTAIN_NO_TARGET
        assert result.reward_ticks is None

    def test_nonpositive_reward_target_never_wins_over_a_qualifying_one(self):
        result = evaluate(targets=[target("PROTECTED_SWING", 95, root_id="behind"),
                                   target("SESSION_LEVEL", 108, root_id="ahead")])
        assert result.admitted is True
        assert result.selected_target_ticks == 108
        assert result.selected_target_type == "SESSION_LEVEL"


class TestNoAtr:
    def test_missing_atr_abstains_before_any_geometry_math(self):
        result = evaluate(atr=None, source=999999, targets=[])
        assert result.admitted is False
        assert result.abstain_reason == candidate_geometry.ABSTAIN_NO_ATR
        assert result.entry_reference_ticks == 100
        assert result.natural_invalidation_ticks is None
        assert result.risk_ticks is None


class TestUnknownCapsule:
    def test_unknown_capsule_id_raises_and_is_not_swallowed(self):
        with pytest.raises(capsules.CapsuleUnavailableError):
            evaluate(capsule_id="not_a_capsule.v1")

    def test_capsule_check_precedes_missing_params(self):
        # Even with no params at all, the unknown capsule id is the first thing checked.
        with pytest.raises(capsules.CapsuleUnavailableError):
            evaluate(capsule_id="CAP01_OB_ENTRY", params={})


class TestTargetAvailability:
    def test_future_knowledge_time_target_is_excluded_even_if_nearest(self):
        near_but_future = target("PROTECTED_SWING", 101, knowledge_time_us=2_000, root_id="near")
        far_but_available = target("SESSION_LEVEL", 110, knowledge_time_us=500, root_id="far")
        result = evaluate(knowledge_time=1_000, targets=[near_but_future, far_but_available])
        assert result.admitted is True
        assert result.selected_target_ticks == 110
        assert result.selected_target_type == "SESSION_LEVEL"

    def test_knowledge_time_equal_to_candidate_time_is_available(self):
        # PAR-064 boundary_rule: "Equality passes."
        result = evaluate(knowledge_time=1_000,
                           targets=[target("PROTECTED_SWING", 104, knowledge_time_us=1_000)])
        assert result.admitted is True

    def test_unknown_target_type_raises(self):
        with pytest.raises(StructureLawError):
            evaluate(targets=[target("MOVING_AVERAGE", 104)])


class TestPriorityTieBreak:
    def test_protected_swing_wins_over_session_level_at_equal_distance(self):
        result = evaluate(targets=[target("SESSION_LEVEL", 104, root_id="a"),
                                   target("PROTECTED_SWING", 104, root_id="b")])
        assert result.selected_target_type == "PROTECTED_SWING"

    def test_session_level_wins_over_equal_level_at_equal_distance(self):
        result = evaluate(targets=[target("EQUAL_LEVEL", 104, root_id="a"),
                                   target("SESSION_LEVEL", 104, root_id="b")])
        assert result.selected_target_type == "SESSION_LEVEL"

    def test_protected_swing_wins_over_all_three_at_equal_distance(self):
        result = evaluate(targets=[target("EQUAL_LEVEL", 104, root_id="a"),
                                   target("SESSION_LEVEL", 104, root_id="b"),
                                   target("PROTECTED_SWING", 104, root_id="c")])
        assert result.selected_target_type == "PROTECTED_SWING"


class TestRootIdTieBreak:
    def test_same_type_and_distance_breaks_on_root_id_ascending(self):
        result = evaluate(targets=[target("PROTECTED_SWING", 104, root_id="zzz"),
                                   target("PROTECTED_SWING", 104, root_id="aaa")])
        # Only root_id distinguishes the two candidates; the lexicographically-smaller wins.
        assert result.admitted is True
        assert result.selected_target_ticks == 104


class TestSelectedTargetLevelIdentity:
    """RC3 F18 identity_material: capsule occurrence + E/S/T level IDs + formula/params."""

    def test_winning_target_root_id_survives_to_the_result(self):
        # The T level ID (root_id) must be recoverable from the F18 result so the identity layer
        # can bind it; the old (type, ticks) result discarded it.
        result = evaluate(targets=[target("PROTECTED_SWING", 104, root_id="T-LEVEL-9")])
        assert result.admitted is True
        assert result.selected_target_root_id == "T-LEVEL-9"

    def test_root_id_tiebreak_winner_is_the_one_reported(self):
        # Two identical type+distance targets; the ascending-root_id winner is "aaa", and since the
        # tie-break is ON root_id, only the returned root_id disambiguates the selected level.
        result = evaluate(targets=[target("PROTECTED_SWING", 104, root_id="zzz"),
                                   target("PROTECTED_SWING", 104, root_id="aaa")])
        assert result.admitted is True
        assert result.selected_target_root_id == "aaa"

    def test_optional_entry_and_stop_level_ids_echo_when_supplied(self):
        result = candidate_geometry.evaluate_candidate_geometry(
            direction=common.LONG, entry_reference_ticks=100,
            natural_invalidation_source_ticks=99, atr14_ticks=20,
            capsule_semantic_id=CAPSULE_ID,
            available_targets=[target("PROTECTED_SWING", 104)],
            candidate_knowledge_time_us=1_000, params=PARAMS,
            entry_reference_level_id="E-LVL", natural_invalidation_level_id="S-LVL")
        assert result.entry_reference_level_id == "E-LVL"
        assert result.natural_invalidation_level_id == "S-LVL"

    def test_level_ids_are_honest_null_when_not_supplied(self):
        result = evaluate(targets=[target("PROTECTED_SWING", 104)])
        assert result.entry_reference_level_id is None
        assert result.natural_invalidation_level_id is None

    def test_supplied_level_id_must_be_nonempty(self):
        with pytest.raises(StructureLawError):
            candidate_geometry.evaluate_candidate_geometry(
                direction=common.LONG, entry_reference_ticks=100,
                natural_invalidation_source_ticks=99, atr14_ticks=20,
                capsule_semantic_id=CAPSULE_ID,
                available_targets=[target("PROTECTED_SWING", 104)],
                candidate_knowledge_time_us=1_000, params=PARAMS,
                entry_reference_level_id="")

    def test_abstention_carries_selected_target_root_id_when_a_target_was_selected(self):
        # Below-floor abstention still carries the winner's level identity (honest diagnostic).
        result = evaluate(targets=[target("PROTECTED_SWING", 103, root_id="T-3")])
        assert result.abstain_reason == candidate_geometry.ABSTAIN_GEOMETRY_BELOW_FLOOR
        assert result.selected_target_root_id == "T-3"


class TestUnreducedRrPair:
    def test_reward_6_risk_3_is_never_simplified_to_2_1(self):
        # entry=200, source=198, atr=20 -> buffer=1 -> stop=198-1=197 -> risk=3.
        result = evaluate(entry=200, source=198, targets=[target("PROTECTED_SWING", 206)])
        assert result.admitted is True
        assert result.risk_ticks == 3
        assert result.reward_ticks == 6
        assert (result.rr_numerator, result.rr_denominator) == (6, 3)
        assert (result.rr_numerator, result.rr_denominator) != (2, 1)


class TestMirror:
    def test_long_short_full_reflection(self):
        long_result = evaluate(
            direction=common.LONG, entry=100, source=99,
            targets=[target("PROTECTED_SWING", 104)])
        short_result = evaluate(
            direction=common.SHORT, entry=-100, source=-99,
            targets=[target("PROTECTED_SWING", -104)])
        assert long_result.admitted == short_result.admitted is True
        assert long_result.risk_ticks == short_result.risk_ticks == 2
        assert long_result.reward_ticks == short_result.reward_ticks == 4
        assert (long_result.rr_numerator, long_result.rr_denominator) == \
            (short_result.rr_numerator, short_result.rr_denominator) == (4, 2)

    def test_long_short_full_reflection_at_the_geometry_floor_boundary(self):
        long_result = evaluate(targets=[target("PROTECTED_SWING", 103)])
        short_result = evaluate(
            direction=common.SHORT, entry=-100, source=-99,
            targets=[target("PROTECTED_SWING", -103)])
        assert long_result.admitted == short_result.admitted is False
        assert long_result.abstain_reason == short_result.abstain_reason == \
            candidate_geometry.ABSTAIN_GEOMETRY_BELOW_FLOOR
        assert long_result.risk_ticks == short_result.risk_ticks == 2
        assert long_result.reward_ticks == short_result.reward_ticks == 3


class TestFailClosed:
    def test_missing_param_fails_closed(self):
        with pytest.raises(MissingParameterError):
            evaluate(params={})

    def test_undeclared_buffer_rule_string_refused(self):
        bad = dict(PARAMS)
        bad[capsules.PAR_NATURAL_INVALIDATION_BUFFER_RULE] = "max(1,ceil(ATR14_ticks*1/10))"
        with pytest.raises(StructureLawError, match="PAR-172"):
            evaluate(params=bad)

    def test_undeclared_target_availability_rule_refused(self):
        bad = dict(PARAMS)
        bad[capsules.PAR_TARGET_AVAILABILITY_RULE] = "target.knowledge_time<candidate.knowledge_time"
        with pytest.raises(StructureLawError, match="PAR-064"):
            evaluate(params=bad)

    def test_undeclared_target_selector_priority_refused(self):
        bad = dict(PARAMS)
        bad[capsules.PAR_TARGET_SELECTOR] = ("SESSION_LEVEL", "PROTECTED_SWING", "EQUAL_LEVEL")
        with pytest.raises(StructureLawError, match="PAR-173"):
            evaluate(params=bad)

    def test_undeclared_min_geometric_rr_rule_refused(self):
        bad = dict(PARAMS)
        bad[candidate_geometry.PARAM_MIN_GEOMETRIC_RR_RULE] = "3/2"
        with pytest.raises(StructureLawError, match="PAR-061"):
            evaluate(params=bad)
