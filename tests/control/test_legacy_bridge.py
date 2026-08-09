"""B07 legacy-bridge battery: byte preservation (never repairs/backfills/reshapes), omission
preservation, restart resume-offset correctness, idempotent redelivery vs disagreeing-content
refusal, the freeze law (only LEGACY_COMPARATOR is ever stamped), fail-closed inputs."""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin.control import legacy_bridge as lb  # noqa: E402


LEGACY_RECORD = {"id": "legacy-1", "symbol": "BTCUSDT", "price": "100.5"}


# ---------------------------------------------------------------------------------------------
# bridge_legacy_record: byte preservation + omission preservation + the freeze law
# ---------------------------------------------------------------------------------------------


def test_bridged_envelope_stamps_legacy_comparator_cohort():
    env = lb.bridge_legacy_record(
        LEGACY_RECORD, intelligence_arm="DETERMINISTIC_CONTROL",
        source_topic="legacy.candidates.v1", input_offset=0, bridged_at_us=1000)
    assert env["engine_cohort"] == lb.LEGACY_ENGINE_COHORT == "LEGACY_COMPARATOR"


def test_legacy_payload_is_carried_verbatim():
    env = lb.bridge_legacy_record(
        LEGACY_RECORD, intelligence_arm="DETERMINISTIC_CONTROL",
        source_topic="legacy.candidates.v1", input_offset=0, bridged_at_us=1000)
    assert env["legacy_payload"] == LEGACY_RECORD


def test_a_field_the_legacy_record_never_carried_stays_absent():
    env = lb.bridge_legacy_record(
        LEGACY_RECORD, intelligence_arm="DETERMINISTIC_CONTROL",
        source_topic="legacy.candidates.v1", input_offset=0, bridged_at_us=1000)
    # A modern edge_candidate.v2-shaped field this legacy record never had (targets, rr, etc.)
    # must never be fabricated onto legacy_payload.
    for modern_field in ("targets", "rr_numerator", "rr_denominator", "capsule_id"):
        assert modern_field not in env["legacy_payload"]


def test_byte_preservation_verifies_on_an_untouched_envelope():
    env = lb.bridge_legacy_record(
        LEGACY_RECORD, intelligence_arm="DETERMINISTIC_CONTROL",
        source_topic="legacy.candidates.v1", input_offset=0, bridged_at_us=1000)
    assert lb.verify_byte_preservation(env)


def test_byte_preservation_detects_tampering():
    env = lb.bridge_legacy_record(
        LEGACY_RECORD, intelligence_arm="DETERMINISTIC_CONTROL",
        source_topic="legacy.candidates.v1", input_offset=0, bridged_at_us=1000)
    tampered = dict(env)
    tampered["legacy_payload"] = dict(tampered["legacy_payload"])
    tampered["legacy_payload"]["price"] = "999.99"
    assert not lb.verify_byte_preservation(tampered)


def test_verify_byte_preservation_is_false_on_malformed_envelopes():
    assert not lb.verify_byte_preservation({})
    assert not lb.verify_byte_preservation({"legacy_payload": "not-a-dict"})
    assert not lb.verify_byte_preservation("not-a-dict")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------------------------
# Fail-closed inputs
# ---------------------------------------------------------------------------------------------


def test_non_dict_raw_record_refuses():
    with pytest.raises(lb.LegacyBridgeError):
        lb.bridge_legacy_record(
            "not-a-dict", intelligence_arm="DETERMINISTIC_CONTROL",  # type: ignore[arg-type]
            source_topic="t", input_offset=0, bridged_at_us=1000)


def test_unknown_intelligence_arm_refuses():
    with pytest.raises(lb.LegacyBridgeError):
        lb.bridge_legacy_record(
            LEGACY_RECORD, intelligence_arm="SOMETHING_ELSE", source_topic="t",
            input_offset=0, bridged_at_us=1000)


def test_empty_source_topic_refuses():
    with pytest.raises(lb.LegacyBridgeError):
        lb.bridge_legacy_record(
            LEGACY_RECORD, intelligence_arm="DETERMINISTIC_CONTROL", source_topic="",
            input_offset=0, bridged_at_us=1000)


def test_negative_input_offset_refuses():
    with pytest.raises(lb.LegacyBridgeError):
        lb.bridge_legacy_record(
            LEGACY_RECORD, intelligence_arm="DETERMINISTIC_CONTROL", source_topic="t",
            input_offset=-1, bridged_at_us=1000)


# ---------------------------------------------------------------------------------------------
# LegacyBridgeState: restart/resume + idempotency vs conflict
# ---------------------------------------------------------------------------------------------


def test_resume_from_offset_starts_at_zero_for_a_fresh_topic():
    state = lb.LegacyBridgeState()
    assert state.resume_from_offset("legacy.candidates.v1") == 0


def test_resume_from_offset_advances_past_the_highest_bridged_offset():
    state = lb.LegacyBridgeState()
    state.bridge(LEGACY_RECORD, intelligence_arm="DETERMINISTIC_CONTROL",
                 source_topic="t", input_offset=0, bridged_at_us=1000)
    assert state.resume_from_offset("t") == 1
    state.bridge(LEGACY_RECORD, intelligence_arm="DETERMINISTIC_CONTROL",
                 source_topic="t", input_offset=1, bridged_at_us=1000)
    assert state.resume_from_offset("t") == 2


def test_resume_from_offset_is_per_topic_independent():
    state = lb.LegacyBridgeState()
    state.bridge(LEGACY_RECORD, intelligence_arm="DETERMINISTIC_CONTROL",
                 source_topic="topic-a", input_offset=0, bridged_at_us=1000)
    assert state.resume_from_offset("topic-a") == 1
    assert state.resume_from_offset("topic-b") == 0


def test_a_restart_simulated_by_a_fresh_state_resumes_from_the_recorded_offset():
    # Simulates: bridge two records, "restart" (fresh state object), and confirm the caller
    # would correctly resume at offset 2 rather than reprocessing 0/1.
    state = lb.LegacyBridgeState()
    state.bridge(LEGACY_RECORD, intelligence_arm="DETERMINISTIC_CONTROL",
                 source_topic="t", input_offset=0, bridged_at_us=1000)
    state.bridge({"id": "legacy-2"}, intelligence_arm="DETERMINISTIC_CONTROL",
                 source_topic="t", input_offset=1, bridged_at_us=1001)
    next_offset = state.resume_from_offset("t")
    assert next_offset == 2
    # A caller resuming from a durable log would re-supply only offset >= next_offset; bridging
    # offset 2 must succeed cleanly with no reference to the "old" state instance.
    fresh_state = lb.LegacyBridgeState()
    env = fresh_state.bridge({"id": "legacy-3"}, intelligence_arm="DETERMINISTIC_CONTROL",
                              source_topic="t", input_offset=next_offset, bridged_at_us=1002)
    assert env["input_offset"] == 2


def test_identical_redelivery_at_the_same_offset_is_idempotent():
    state = lb.LegacyBridgeState()
    env1 = state.bridge(LEGACY_RECORD, intelligence_arm="DETERMINISTIC_CONTROL",
                         source_topic="t", input_offset=0, bridged_at_us=1000)
    env2 = state.bridge(LEGACY_RECORD, intelligence_arm="DETERMINISTIC_CONTROL",
                         source_topic="t", input_offset=0, bridged_at_us=1000)
    assert env1 == env2
    assert state.resume_from_offset("t") == 1  # unchanged, not double-advanced


def test_disagreeing_content_at_an_already_bridged_offset_refuses():
    state = lb.LegacyBridgeState()
    state.bridge(LEGACY_RECORD, intelligence_arm="DETERMINISTIC_CONTROL",
                 source_topic="t", input_offset=0, bridged_at_us=1000)
    with pytest.raises(lb.LegacyBridgeError):
        state.bridge({"id": "a-different-record"}, intelligence_arm="DETERMINISTIC_CONTROL",
                     source_topic="t", input_offset=0, bridged_at_us=1000)


def test_bridged_at_reads_the_verbatim_stored_envelope():
    state = lb.LegacyBridgeState()
    state.bridge(LEGACY_RECORD, intelligence_arm="DETERMINISTIC_CONTROL",
                 source_topic="t", input_offset=0, bridged_at_us=1000)
    stored = state.bridged_at("t", 0)
    assert stored["legacy_payload"] == LEGACY_RECORD


def test_bridged_at_returns_none_for_an_unknown_offset_or_topic():
    state = lb.LegacyBridgeState()
    assert state.bridged_at("never-seen", 0) is None
    state.bridge(LEGACY_RECORD, intelligence_arm="DETERMINISTIC_CONTROL",
                 source_topic="t", input_offset=0, bridged_at_us=1000)
    assert state.bridged_at("t", 99) is None


def test_bridged_at_returns_a_detached_copy():
    state = lb.LegacyBridgeState()
    state.bridge(LEGACY_RECORD, intelligence_arm="DETERMINISTIC_CONTROL",
                 source_topic="t", input_offset=0, bridged_at_us=1000)
    stored = state.bridged_at("t", 0)
    stored["input_offset"] = 999
    assert state.bridged_at("t", 0)["input_offset"] == 0
