"""LEV-0032/0040/0043/0048/0050/0051/0053/0055/0058 — runtime lever registry battery."""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import timings, transition  # noqa: E402
from triad_origin.control import lever_law  # noqa: E402
from triad_origin.control.lever_registry import (  # noqa: E402
    ATTESTATION_ACCEPTED,
    ATTESTATION_REFUSED,
    MANIFEST_ACCEPTED,
    MANIFEST_REFUSED,
    STALENESS_FORCED_OFF,
    LeverRegistry,
    LeverRegistryError,
)

BASE_ACTIVATIONS = {"origin.candidate_publisher": "OFF", "origin.edge_comparator": "OFF"}


def manifest_payload(revision, activations=BASE_ACTIVATIONS, digest="d1", **overrides):
    payload = {
        "venue_environment": "OFF", "venue_activation": "OFF", "paper_activation": "OFF",
        "shadow_activation": "LIVE", "activations": activations,
        "manifest_digest_sha256": digest, "revision": revision,
    }
    payload.update(overrides)
    return payload


def register(revision, activations=BASE_ACTIVATIONS, digest="d1", event_id=None, **overrides):
    return {"event_id": event_id or f"reg_{revision}", "kind": "REGISTER_MANIFEST",
            "payload": manifest_payload(revision, activations, digest, **overrides)}


def attest(engine_id, digest, revision, freshness_age_ms, event_id=None):
    return {"event_id": event_id or f"att_{engine_id}_{revision}_{freshness_age_ms}",
            "kind": "ATTEST_RUNTIME",
            "payload": {"engine_id": engine_id, "accepted_manifest_digest_sha256": digest,
                        "accepted_revision": revision, "freshness_age_ms": freshness_age_ms}}


def resolve_staleness(engine_id, cached_age_ms, event_id=None):
    return {"event_id": event_id or f"stale_{engine_id}_{cached_age_ms}",
            "kind": "RESOLVE_STALENESS",
            "payload": {"engine_id": engine_id, "cached_age_ms": cached_age_ms}}


def run(inputs, initial=None):
    return transition.run(LeverRegistry(), inputs, {}, initial=initial)


def only_event(result):
    assert len(result.events) == 1
    return result.events[0]


class TestRegisterManifest:
    def test_first_manifest_accepted_at_revision_one(self):
        result = run([register(1)])
        assert result.final_state["revision"] == 1
        assert result.final_state["accepted_manifest_digest_sha256"] == "d1"
        assert result.final_state["levers"] == {
            "origin.candidate_publisher": {"value": "OFF", "digest": "d1", "revision": 1},
            "origin.edge_comparator": {"value": "OFF", "digest": "d1", "revision": 1},
        }
        event = only_event(result)
        assert event["event_kind"] == MANIFEST_ACCEPTED
        assert event["revision"] == 1

    def test_refused_manifest_bad_alias_leaves_state_unchanged(self):
        bad = register(1, venue_activation="on")
        result = run([bad])
        assert result.final_state == LeverRegistry().initial_state()
        event = only_event(result)
        assert event["event_kind"] == MANIFEST_REFUSED
        assert event["refusal_code"] == "VENUE_ACTIVATION_VALUE_INVALID"
        assert event["minimum_action"]["shadow_activation"] == "LIVE"

    def test_skipped_revision_is_refused_stale_and_state_unchanged(self):
        # Accept revision 1, then attempt revision 3 (skipping 2) — CAS must refuse, not fast-forward.
        first = run([register(1)])
        result = run([register(3, digest="d3")], initial=first.final_state)
        assert result.final_state == first.final_state
        event = only_event(result)
        assert event["event_kind"] == MANIFEST_REFUSED
        assert event["refusal_code"] == "LEVER_REVISION_STALE"

    def test_repeated_revision_is_refused_stale(self):
        # A DISTINCT envelope (different event_id) re-asserting the already-current revision must
        # still be refused by the CAS — exact-once, not "any revision <= current is idempotent".
        first = run([register(1)])
        result = run(
            [register(1, digest="d1-again", event_id="reg_1_replay")],
            initial=first.final_state,
        )
        assert result.final_state == first.final_state
        assert only_event(result)["refusal_code"] == "LEVER_REVISION_STALE"

    def test_incomplete_activations_map_missing_key_refused(self):
        first = run([register(1)])
        narrower = {"origin.candidate_publisher": "LIVE"}  # drops origin.edge_comparator
        result = run([register(2, activations=narrower, digest="d2")], initial=first.final_state)
        assert result.final_state == first.final_state
        assert only_event(result)["refusal_code"] == "LEVER_REGISTRY_INCOMPLETE"

    def test_incomplete_activations_map_unknown_key_refused(self):
        first = run([register(1)])
        wider = dict(BASE_ACTIVATIONS, **{"origin.replay_runner": "OFF"})
        result = run([register(2, activations=wider, digest="d2")], initial=first.final_state)
        assert result.final_state == first.final_state
        assert only_event(result)["refusal_code"] == "LEVER_REGISTRY_INCOMPLETE"

    def test_matching_key_set_with_new_values_accepted(self):
        first = run([register(1)])
        flipped = {"origin.candidate_publisher": "LIVE", "origin.edge_comparator": "OFF"}
        result = run([register(2, activations=flipped, digest="d2")], initial=first.final_state)
        assert result.final_state["revision"] == 2
        assert result.final_state["levers"]["origin.candidate_publisher"] == {
            "value": "LIVE", "digest": "d2", "revision": 2,
        }
        assert only_event(result)["event_kind"] == MANIFEST_ACCEPTED

    def test_missing_manifest_digest_refused_incomplete(self):
        result = run([register(1, digest=None)])
        assert result.final_state == LeverRegistry().initial_state()
        assert only_event(result)["refusal_code"] == "LEVER_REGISTRY_INCOMPLETE"

    def test_malformed_revision_raises_cleanly(self):
        payload = manifest_payload(1)
        del payload["revision"]
        envelope = {"event_id": "reg_bad", "kind": "REGISTER_MANIFEST", "payload": payload}
        with pytest.raises(LeverRegistryError):
            LeverRegistry().transition(LeverRegistry().initial_state(), envelope, {}, {})

    def test_boolean_revision_raises_cleanly(self):
        payload = manifest_payload(True)
        envelope = {"event_id": "reg_bool", "kind": "REGISTER_MANIFEST", "payload": payload}
        with pytest.raises(LeverRegistryError):
            LeverRegistry().transition(LeverRegistry().initial_state(), envelope, {}, {})


class TestAttestRuntime:
    def _registered(self):
        return run([register(1)]).final_state

    def test_matching_digest_revision_fresh_age_accepted(self):
        state = self._registered()
        result = run([attest("engineA", digest="d1", revision=1, freshness_age_ms=100)],
                      initial=state)
        assert result.final_state["attestations"]["engineA"] == {
            "accepted_revision": 1, "attested_age_ms": 100,
        }
        event = only_event(result)
        assert event["event_kind"] == ATTESTATION_ACCEPTED
        assert event["engine_id"] == "engineA"

    def test_wrong_digest_refused(self):
        state = self._registered()
        result = run([attest("engineA", digest="wrong", revision=1, freshness_age_ms=100)],
                      initial=state)
        assert result.final_state == state
        event = only_event(result)
        assert event["event_kind"] == ATTESTATION_REFUSED
        assert event["refusal_code"] == "RUNTIME_LEVER_ATTESTATION_MISMATCH"

    def test_wrong_revision_refused_same_code(self):
        state = self._registered()
        result = run([attest("engineA", digest="d1", revision=99, freshness_age_ms=100)],
                      initial=state)
        assert result.final_state == state
        assert only_event(result)["refusal_code"] == "RUNTIME_LEVER_ATTESTATION_MISMATCH"

    def test_correct_digest_but_stale_age_refused_same_code_as_mismatch(self):
        state = self._registered()
        fresh = run([attest("engineA", digest="d1", revision=1, freshness_age_ms=15000)],
                     initial=state)
        assert fresh.final_state["attestations"]["engineA"]["attested_age_ms"] == 15000

        stale_state = self._registered()
        stale = run([attest("engineA", digest="d1", revision=1, freshness_age_ms=15001)],
                     initial=stale_state)
        assert stale.final_state == stale_state  # refused: attestations untouched
        assert only_event(stale)["refusal_code"] == "RUNTIME_LEVER_ATTESTATION_MISMATCH"

    def test_malformed_freshness_age_raises_cleanly(self):
        state = self._registered()
        envelope = attest("engineA", digest="d1", revision=1, freshness_age_ms="soon")
        with pytest.raises(timings.TimingError):
            LeverRegistry().transition(state, envelope, {}, {})

    def test_malformed_accepted_revision_raises_cleanly(self):
        state = self._registered()
        envelope = attest("engineA", digest="d1", revision="1", freshness_age_ms=100)
        with pytest.raises(LeverRegistryError):
            LeverRegistry().transition(state, envelope, {}, {})

    def test_malformed_engine_id_raises_cleanly(self):
        state = self._registered()
        envelope = attest("", digest="d1", revision=1, freshness_age_ms=100)
        with pytest.raises(LeverRegistryError):
            LeverRegistry().transition(state, envelope, {}, {})


class TestResolveStaleness:
    def test_stale_cache_emits_forced_off_with_shadow_always_live(self):
        state = run([register(1, activations={"origin.candidate_publisher": "LIVE",
                                               "origin.edge_comparator": "OFF"})]).final_state
        result = run([resolve_staleness("origin.candidate_publisher", cached_age_ms=2001)],
                      initial=state)
        assert result.final_state == state  # advisory only: registry truth never mutated
        event = only_event(result)
        assert event["event_kind"] == STALENESS_FORCED_OFF
        action = event["action"]
        assert action["venue_activation"] == "OFF"
        assert action["paper_activation"] == "OFF"
        assert action["shadow_activation"] == "LIVE"
        assert action["value"] == "LIVE"  # the engine's own last-known lever value, preserved
        assert action["digest"] == "d1"
        assert action["revision"] == 1

    def test_fresh_cache_is_a_pure_noop(self):
        state = run([register(1)]).final_state
        result = run([resolve_staleness("origin.candidate_publisher", cached_age_ms=2000)],
                      initial=state)
        assert result.final_state == state
        assert result.events == []

    def test_engine_with_no_row_defaults_to_the_rc4_baseline(self):
        state = run([register(1)]).final_state
        result = run([resolve_staleness("never_registered", cached_age_ms=5000)], initial=state)
        action = only_event(result)["action"]
        assert action == dict(lever_law.BASELINE_MANIFEST)

    def test_negative_cached_age_is_stale_by_definition(self):
        state = run([register(1)]).final_state
        result = run([resolve_staleness("origin.candidate_publisher", cached_age_ms=-1)],
                      initial=state)
        assert only_event(result)["event_kind"] == STALENESS_FORCED_OFF

    def test_malformed_cached_age_raises_cleanly(self):
        state = run([register(1)]).final_state
        envelope = resolve_staleness("origin.candidate_publisher", cached_age_ms=None)
        with pytest.raises(timings.TimingError):
            LeverRegistry().transition(state, envelope, {}, {})

    def test_malformed_engine_id_raises_cleanly(self):
        state = run([register(1)]).final_state
        envelope = resolve_staleness(123, cached_age_ms=5000)
        with pytest.raises(LeverRegistryError):
            LeverRegistry().transition(state, envelope, {}, {})


class TestUnknownEnvelopeKind:
    def test_unknown_kind_raises_cleanly(self):
        envelope = {"event_id": "x", "kind": "SOMETHING_ELSE", "payload": {}}
        with pytest.raises(LeverRegistryError):
            LeverRegistry().transition(LeverRegistry().initial_state(), envelope, {}, {})


class TestInvariance:
    def test_prefix_and_restart_and_duplicate(self):
        full = [
            register(1),
            attest("engineA", digest="d1", revision=1, freshness_age_ms=100),
            register(2, activations={"origin.candidate_publisher": "LIVE",
                                     "origin.edge_comparator": "OFF"}, digest="d2"),
        ]
        whole = run(full)
        prefix = run(full[:2])
        assert prefix.final_state["revision"] == 1
        assert prefix.final_state["attestations"]["engineA"]["accepted_revision"] == 1

        resumed = run(full[2:], initial=prefix.final_state)
        assert resumed.final_state == whole.final_state

        dup = run(full + [full[-1]])
        assert dup.final_state == whole.final_state
        assert dup.duplicate_count == 1
