"""B06 trial registry: preregistration immutability, auto-derived ablations, result-access gate."""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import transition  # noqa: E402
from triad_origin.structures.trial_registry import (  # noqa: E402
    RESULT_ACCESS_GRANTED,
    TRIAL_PREREGISTERED,
    TrialRegistry,
    TrialRegistryError,
    TrialUnavailableError,
    resolve_trial,
)


def preregister(trial_id, conjuncts, results_after=2_000, prereg_at=1_000, event_id=None,
                capsule="fvg_displacement_first_touch.v1"):
    return {"event_id": event_id or f"pre_{trial_id}", "kind": "PREREGISTER_TRIAL",
            "payload": {"trial_id": trial_id, "capsule_semantic_id": capsule,
                       "conjunct_set": conjuncts, "results_available_after_us": results_after,
                       "preregistered_at_us": prereg_at}}


def request_access(trial_id, requested_at, event_id=None):
    return {"event_id": event_id or f"acc_{trial_id}_{requested_at}",
            "kind": "REQUEST_RESULT_ACCESS",
            "payload": {"trial_id": trial_id, "requested_at_us": requested_at}}


def run(inputs, initial=None):
    return transition.run(TrialRegistry(), inputs, {}, initial=initial)


class TestPreregistration:
    def test_new_trial_registers_and_derives_ablations(self):
        result = run([preregister("T1", ["c1", "c2", "c3"])])
        assert result.events[0]["event_kind"] == TRIAL_PREREGISTERED
        assert len(result.events[0]["ablation_ids"]) == 3
        assert len(set(result.events[0]["ablation_ids"])) == 3  # distinct per omitted conjunct

    def test_ablation_ids_are_deterministic_across_runs(self):
        r1 = run([preregister("T1", ["c1", "c2"])])
        r2 = run([preregister("T1", ["c1", "c2"], event_id="different_event_id")])
        assert r1.events[0]["ablation_ids"] == r2.events[0]["ablation_ids"]

    def test_identical_redelivery_is_idempotent_noop(self):
        result = run([preregister("T1", ["c1", "c2"]), preregister("T1", ["c1", "c2"])])
        assert len(result.events) == 1

    def test_disagreeing_redelivery_refused(self):
        result = run([preregister("T1", ["c1", "c2"]),
                      preregister("T1", ["c1", "c2", "c3"], event_id="second")])
        assert result.events[-1]["reason_code"] == "TRIAL_ALREADY_REGISTERED_DISAGREEMENT"
        assert len(resolve_trial(result.final_state, "T1").conjunct_set) == 2

    def test_results_available_before_preregistration_refused(self):
        with pytest.raises(TrialRegistryError):
            transition.run(
                TrialRegistry(),
                [preregister("T1", ["c1"], results_after=500, prereg_at=1_000)], {})

    def test_duplicate_conjunct_name_refused(self):
        with pytest.raises(TrialRegistryError):
            transition.run(TrialRegistry(), [preregister("T1", ["c1", "c1"])], {})

    def test_empty_conjunct_set_refused(self):
        with pytest.raises(TrialRegistryError):
            transition.run(TrialRegistry(), [preregister("T1", [])], {})


class TestResultAccess:
    def test_access_granted_at_or_after_the_declared_instant(self):
        inputs = [preregister("T1", ["c1"], results_after=2_000),
                  request_access("T1", 2_000)]
        result = run(inputs)
        assert result.events[-1]["event_kind"] == RESULT_ACCESS_GRANTED

    def test_access_refused_before_the_declared_instant(self):
        inputs = [preregister("T1", ["c1"], results_after=2_000),
                  request_access("T1", 1_999)]
        result = run(inputs)
        assert result.events[-1]["reason_code"] == "RESULT_ACCESS_TOO_EARLY"

    def test_access_refused_for_unregistered_trial(self):
        result = run([request_access("ghost", 999_999)])
        assert result.events[-1]["reason_code"] == "TRIAL_NOT_PREREGISTERED"


class TestResolveTrial:
    def test_resolve_unregistered_trial_raises(self):
        with pytest.raises(TrialUnavailableError):
            resolve_trial({"trials": {}}, "ghost")

    def test_resolve_registered_trial(self):
        result = run([preregister("T1", ["c1", "c2"])])
        d = resolve_trial(result.final_state, "T1")
        assert d.trial_id == "T1"
        assert d.conjunct_set == ("c1", "c2")
        assert len(d.ablation_ids) == 2


class TestFailClosed:
    def test_missing_field_raises(self):
        with pytest.raises(TrialRegistryError):
            transition.run(TrialRegistry(), [{"event_id": "e1", "kind": "PREREGISTER_TRIAL",
                                              "payload": {"trial_id": "T1"}}], {})

    def test_unknown_kind_raises(self):
        with pytest.raises(TrialRegistryError):
            transition.run(TrialRegistry(),
                           [{"event_id": "e1", "kind": "BOGUS", "payload": {}}], {})


class TestInvariance:
    def test_prefix_and_restart_and_duplicate(self):
        full = [preregister("T1", ["c1", "c2"]), request_access("T1", 2_000)]
        whole = run(full)
        prefix = run(full[:1])
        resumed = run(full[1:], initial=prefix.final_state)
        assert resumed.final_state == whole.final_state
        dup = run(full + [full[-1]])
        assert dup.final_state == whole.final_state
