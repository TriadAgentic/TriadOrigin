"""F14 departure/first-touch battery: GV-012, the three departure conjuncts, mirror, invariance."""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import transition  # noqa: E402
from triad_origin.structures import common  # noqa: E402
from triad_origin.structures import reaction  # noqa: E402
from triad_origin.structures.common import StructureLawError  # noqa: E402
from triad_origin.structures.reaction import (  # noqa: E402
    DEPARTED,
    ELIGIBLE,
    EXPIRED,
    FIRST_TOUCH_CONSUMED,
    INVALIDATED,
    DepartureAndFirstTouch,
)

PARAMS = {
    "min_departure_rule": common.DECLARED_MIN_DEPARTURE,
    "min_depart_events": 1,
    "min_depart_time_ms": 60000,
    "contact_price_source": reaction.DECLARED_CONTACT_PRICE_SOURCE,
    "first_touch_ordinal": 1,
}


def zone_registered(zone_id, direction, z_near, z_far, knowledge_time=0, event_id=None):
    return {"event_id": event_id or f"reg_{zone_id}", "kind": "ZONE_REGISTERED",
            "payload": {"zone_id": zone_id, "direction": direction,
                        "z_near_ticks": z_near, "z_far_ticks": z_far,
                        "knowledge_time_us": knowledge_time}}


def departure(zone_id, distance, events=1, elapsed_ms=60000, atr=20, event_id=None):
    return {"event_id": event_id or f"dep_{zone_id}_{distance}_{events}_{elapsed_ms}",
            "kind": "DEPARTURE_CANDIDATE",
            "payload": {"zone_id": zone_id,
                        "directional_distance_from_near_edge_ticks": distance,
                        "depart_event_count": events,
                        "elapsed_depart_time_ms": elapsed_ms,
                        "atr14_ticks": atr}}


def contact(zone_id, low, high, source=None, event_time=1000, event_id=None):
    return {"event_id": event_id or f"contact_{zone_id}_{low}_{high}_{event_time}",
            "kind": "CONTACT_OBSERVATION",
            "payload": {"zone_id": zone_id,
                        "contact_source": (reaction.DECLARED_CONTACT_PRICE_SOURCE
                                            if source is None else source),
                        "observed_low_ticks": low, "observed_high_ticks": high,
                        "event_time_us": event_time}}


def zone_expired(zone_id, event_id=None):
    return {"event_id": event_id or f"exp_{zone_id}", "kind": "ZONE_EXPIRED",
            "payload": {"zone_id": zone_id}}


def zone_invalidated(zone_id, event_id=None):
    return {"event_id": event_id or f"inv_{zone_id}", "kind": "ZONE_INVALIDATED",
            "payload": {"zone_id": zone_id}}


def run(inputs, params=None, initial=None):
    return transition.run(DepartureAndFirstTouch(), inputs, params or PARAMS, initial=initial)


def to_states(zone_id, result):
    return [e["to_state"] for e in result.events
            if e.get("zone_id") == zone_id and "to_state" in e]


class TestGv012:
    def test_second_identical_touch_produces_no_second_candidate(self):
        # zone=[100,105]; departure satisfied; price low/high=[105,110] -> touch ordinal1
        # consumes eligibility; a second, later identical touch is not a second candidate.
        inputs = [
            zone_registered("Z1", common.LONG, z_near=105, z_far=100),
            departure("Z1", distance=5),
            contact("Z1", low=105, high=110, event_time=1000),
            contact("Z1", low=105, high=110, event_time=2000, event_id="second_touch"),
        ]
        result = run(inputs)
        assert to_states("Z1", result) == [DEPARTED, FIRST_TOUCH_CONSUMED]
        confirmed = [e for e in result.events if e["event_kind"] == "REACTION_CONFIRMED"]
        assert len(confirmed) == 1
        event = confirmed[0]
        assert event["zone_id"] == "Z1"
        assert event["direction"] == common.LONG
        assert event["contact_event_id"] == "contact_Z1_105_110_1000"
        assert event["observed_low_ticks"] == 105 and event["observed_high_ticks"] == 110
        assert len(event["source_reaction_id"]) == 64
        int(event["source_reaction_id"], 16)  # lowercase hex, decodes cleanly
        assert result.final_state["zones"]["Z1"]["reaction_state"] == FIRST_TOUCH_CONSUMED


class TestDepartureConjuncts:
    # ATR=20 -> dep_ticks = max(2, ceil(20/10)) = 2.
    def test_distance_below_floor_alone_fails_departure(self):
        inputs = [
            zone_registered("Z1", common.LONG, z_near=105, z_far=100),
            departure("Z1", distance=1, events=1, elapsed_ms=60000),
        ]
        result = run(inputs)
        assert to_states("Z1", result) == []
        assert result.final_state["zones"]["Z1"]["reaction_state"] == ELIGIBLE

    def test_event_count_below_floor_alone_fails_departure(self):
        inputs = [
            zone_registered("Z1", common.LONG, z_near=105, z_far=100),
            departure("Z1", distance=5, events=0, elapsed_ms=60000),
        ]
        result = run(inputs)
        assert to_states("Z1", result) == []
        assert result.final_state["zones"]["Z1"]["reaction_state"] == ELIGIBLE

    def test_elapsed_time_below_floor_alone_fails_departure(self):
        inputs = [
            zone_registered("Z1", common.LONG, z_near=105, z_far=100),
            departure("Z1", distance=5, events=1, elapsed_ms=59999),
        ]
        result = run(inputs)
        assert to_states("Z1", result) == []
        assert result.final_state["zones"]["Z1"]["reaction_state"] == ELIGIBLE

    def test_all_three_conjuncts_at_exact_inclusive_floor_departs(self):
        inputs = [
            zone_registered("Z1", common.LONG, z_near=105, z_far=100),
            departure("Z1", distance=2, events=1, elapsed_ms=60000),
        ]
        result = run(inputs)
        assert to_states("Z1", result) == [DEPARTED]

    def test_departed_zone_ignores_a_further_departure_candidate(self):
        inputs = [
            zone_registered("Z1", common.LONG, z_near=105, z_far=100),
            departure("Z1", distance=5, event_id="dep_1"),
            departure("Z1", distance=50, events=99, elapsed_ms=999999, event_id="dep_2"),
        ]
        result = run(inputs)
        assert to_states("Z1", result) == [DEPARTED]  # exactly one DEPARTED transition, ever


class TestMissingAtrAbstains:
    def test_null_atr_abstains_and_leaves_zone_eligible(self):
        inputs = [
            zone_registered("Z1", common.LONG, z_near=105, z_far=100),
            departure("Z1", distance=5, atr=None),
        ]
        result = run(inputs)
        assert result.events[0]["reason_code"] == "F14_NO_ATR"
        assert result.final_state["zones"]["Z1"]["reaction_state"] == ELIGIBLE


class TestFailClosed:
    def test_undeclared_min_departure_rule_refused(self):
        bad = dict(PARAMS, min_departure_rule=common.DECLARED_BOS_CLOSE_BUFFER)
        with pytest.raises(StructureLawError, match="undeclared min_departure rule"):
            run([zone_registered("Z1", common.LONG, 105, 100)], params=bad)

    def test_first_touch_ordinal_not_exactly_one_refused(self):
        bad = dict(PARAMS, first_touch_ordinal=2)
        with pytest.raises(StructureLawError, match="ratified at exactly 1"):
            run([zone_registered("Z1", common.LONG, 105, 100)], params=bad)

    def test_min_depart_events_not_exactly_one_refused(self):
        # PAR-166 declared_value "1": any other value is a config defect, not a silent >=1 admit
        # (mirrors the exact-declared-value pin the module applies to PAR-050/168/062).
        bad = dict(PARAMS, min_depart_events=7)
        with pytest.raises(StructureLawError, match="PAR-166"):
            run([zone_registered("Z1", common.LONG, 105, 100)], params=bad)

    def test_min_depart_time_not_exactly_60000_refused(self):
        # PAR-167 declared_value "60000": a 0 (previously admitted under the >=0 range) is refused.
        bad = dict(PARAMS, min_depart_time_ms=0)
        with pytest.raises(StructureLawError, match="PAR-167"):
            run([zone_registered("Z1", common.LONG, 105, 100)], params=bad)

    def test_undeclared_contact_price_source_param_refused(self):
        bad = dict(PARAMS, contact_price_source="mark_price")
        with pytest.raises(StructureLawError, match="undeclared contact_price_source"):
            run([zone_registered("Z1", common.LONG, 105, 100)], params=bad)

    def test_unknown_envelope_kind_refused(self):
        with pytest.raises(StructureLawError, match="unknown F14 envelope kind"):
            run([{"event_id": "e1", "kind": "NOT_A_KIND", "payload": {}}])

    @pytest.mark.parametrize("missing", sorted(PARAMS))
    def test_each_required_parameter_fails_closed_when_missing(self, missing):
        incomplete = {k: v for k, v in PARAMS.items() if k != missing}
        with pytest.raises(transition.MissingParameterError):
            run([zone_registered("Z1", common.LONG, 105, 100)], params=incomplete)


class TestContactSourceLaw:
    def test_wrong_contact_source_string_refused_even_on_unknown_zone(self):
        with pytest.raises(StructureLawError, match="contact_source must be the declared"):
            run([contact("ghost", low=1, high=2, source="intrabar_reconstruction")])


class TestContactTiming:
    def test_contact_before_departure_is_ignored(self):
        inputs = [
            zone_registered("Z1", common.LONG, z_near=105, z_far=100),
            contact("Z1", low=105, high=110),
        ]
        result = run(inputs)
        assert to_states("Z1", result) == []
        assert result.final_state["zones"]["Z1"]["reaction_state"] == ELIGIBLE

    def test_contact_after_expiry_is_ignored(self):
        inputs = [
            zone_registered("Z1", common.LONG, z_near=105, z_far=100),
            departure("Z1", distance=5),
            zone_expired("Z1"),
            contact("Z1", low=105, high=110),
        ]
        result = run(inputs)
        assert to_states("Z1", result) == [DEPARTED, EXPIRED]
        assert result.final_state["zones"]["Z1"]["reaction_state"] == EXPIRED

    def test_contact_after_invalidation_is_ignored(self):
        inputs = [
            zone_registered("Z1", common.LONG, z_near=105, z_far=100),
            departure("Z1", distance=5),
            zone_invalidated("Z1"),
            contact("Z1", low=105, high=110),
        ]
        result = run(inputs)
        assert to_states("Z1", result) == [DEPARTED, INVALIDATED]
        assert result.final_state["zones"]["Z1"]["reaction_state"] == INVALIDATED

    def test_unregistered_zone_ignores_every_non_registration_kind(self):
        result = run([
            departure("ghost", distance=99),
            contact("ghost", low=1, high=2),
            zone_expired("ghost"),
            zone_invalidated("ghost"),
        ])
        assert result.final_state == {"zones": {}}
        assert list(result.events) == []

    def test_reregistration_of_a_known_zone_id_is_ignored(self):
        inputs = [
            zone_registered("Z1", common.LONG, z_near=105, z_far=100),
            zone_registered("Z1", common.SHORT, z_near=-1, z_far=-2, event_id="reg_again"),
        ]
        result = run(inputs)
        row = result.final_state["zones"]["Z1"]
        assert row["direction"] == common.LONG and row["z_near_ticks"] == 105


class TestBoundaryIntersection:
    def test_touch_exactly_at_near_edge_counts(self):
        inputs = [
            zone_registered("Z1", common.LONG, z_near=105, z_far=100),
            departure("Z1", distance=5),
            contact("Z1", low=105, high=110),
        ]
        result = run(inputs)
        assert to_states("Z1", result) == [DEPARTED, FIRST_TOUCH_CONSUMED]

    def test_touch_exactly_at_far_edge_counts(self):
        inputs = [
            zone_registered("Z1", common.LONG, z_near=105, z_far=100),
            departure("Z1", distance=5),
            contact("Z1", low=95, high=100),
        ]
        result = run(inputs)
        assert to_states("Z1", result) == [DEPARTED, FIRST_TOUCH_CONSUMED]

    def test_touch_strictly_outside_the_zone_does_not_count(self):
        inputs = [
            zone_registered("Z1", common.LONG, z_near=105, z_far=100),
            departure("Z1", distance=5),
            contact("Z1", low=106, high=110),
        ]
        result = run(inputs)
        assert to_states("Z1", result) == [DEPARTED]
        assert result.final_state["zones"]["Z1"]["reaction_state"] == DEPARTED


class TestMirror:
    def test_long_short_full_reflection(self):
        long_inputs = [
            zone_registered("Z1", common.LONG, z_near=105, z_far=100),
            departure("Z1", distance=5),
            contact("Z1", low=105, high=110),
        ]
        short_inputs = [
            zone_registered("Z1", common.SHORT, z_near=-105, z_far=-100),
            departure("Z1", distance=5),
            contact("Z1", low=-110, high=-105),
        ]
        long_result = run(long_inputs)
        short_result = run(short_inputs)
        assert to_states("Z1", long_result) == to_states("Z1", short_result) == \
            [DEPARTED, FIRST_TOUCH_CONSUMED]
        assert (long_result.final_state["zones"]["Z1"]["reaction_state"]
                == short_result.final_state["zones"]["Z1"]["reaction_state"]
                == FIRST_TOUCH_CONSUMED)


class TestSourceReactionIdentityMaterial:
    """RC3 F14 identity_material: structure ID + departure event + first contact event + params."""

    @staticmethod
    def _first_touch_id(inputs):
        result = run(inputs)
        confirmed = [e for e in result.events if e["event_kind"] == "REACTION_CONFIRMED"]
        assert len(confirmed) == 1
        return confirmed[0]["source_reaction_id"]

    def test_departure_event_is_bound_into_source_reaction_id(self):
        # Same zone geometry and an IDENTICAL first-contact event; only the DEPARTURE event id
        # differs. The old {zone_id, event_time_us, low, high} hash omitted the departure event, so
        # the two ids collided; binding the departure event makes them distinct.
        def inputs(dep_event_id):
            return [
                zone_registered("Z1", common.LONG, z_near=105, z_far=100),
                departure("Z1", distance=5, event_id=dep_event_id),
                contact("Z1", low=105, high=110, event_time=1000, event_id="c1"),
            ]
        id_a = self._first_touch_id(inputs("dep_A"))
        id_b = self._first_touch_id(inputs("dep_B"))
        assert id_a != id_b
        assert id_a == self._first_touch_id(inputs("dep_A"))  # deterministic reproduction

    def test_first_contact_event_is_bound_into_source_reaction_id(self):
        # Same zone, same departure, same contact price/range/time; only the CONTACT event id
        # differs -> distinct identity (the "first contact event" member).
        def inputs(contact_event_id):
            return [
                zone_registered("Z1", common.LONG, z_near=105, z_far=100),
                departure("Z1", distance=5, event_id="dep"),
                contact("Z1", low=105, high=110, event_time=1000, event_id=contact_event_id),
            ]
        assert self._first_touch_id(inputs("c_A")) != self._first_touch_id(inputs("c_B"))

    def test_source_reaction_id_stays_lowercase_hex_64(self):
        inputs = [
            zone_registered("Z1", common.LONG, z_near=105, z_far=100),
            departure("Z1", distance=5),
            contact("Z1", low=105, high=110),
        ]
        reaction_ident = self._first_touch_id(inputs)
        assert len(reaction_ident) == 64
        int(reaction_ident, 16)  # decodes cleanly as hex


class TestInvariance:
    def test_prefix_and_restart_and_duplicate(self):
        full = [
            zone_registered("Z1", common.LONG, z_near=105, z_far=100),
            departure("Z1", distance=5),
            contact("Z1", low=105, high=110),
        ]
        whole = run(full)
        prefix = run(full[:2])
        assert to_states("Z1", prefix) == [DEPARTED]
        resumed = run(full[2:], initial=prefix.final_state)
        assert resumed.final_state == whole.final_state
        dup = run(full + [full[-1]])
        assert dup.final_state == whole.final_state
