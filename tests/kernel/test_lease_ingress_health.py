"""Producer lease/fencing, contract ingress boundary, telemetry and health read-face."""

from __future__ import annotations

import json
import pathlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from threading import Barrier

import pytest

from triad_origin import contracts, health, telemetry
from triad_origin.health import Readiness
from triad_origin.ingress import Accepted, ContractIngress, Quarantined
from triad_origin.lease import ConsumerFence, Lease, LeaseState

GOLDEN = pathlib.Path(__file__).resolve().parent.parent.parent / "contracts" / "golden"


def _valid(schema_id: str) -> dict:
    return json.loads((GOLDEN / schema_id / "valid.json").read_text(encoding="utf-8"))


# --- lease / fencing -----------------------------------------------------------------------------
def _external_lease(token: int, *, scope: str = "scope") -> Lease:
    """Fixture for a lease already issued and activated by external governance."""
    return Lease(
        lease_id=f"external-lease-{token}",
        scope=scope,
        producer_service="origin",
        producer_instance_id=f"i{token}",
        fencing_token=token,
        activation_manifest_id=f"a{token}",
        state=LeaseState.ACTIVE,
    )


def test_origin_exposes_no_lease_issuer():
    from triad_origin import lease

    assert not hasattr(lease, "LeaseCoordinator")
    assert not hasattr(Lease, "with_state")


def test_external_lease_representation_is_immutable():
    lease = _external_lease(1)
    with pytest.raises(FrozenInstanceError):
        lease.state = LeaseState.REVOKED


def test_consumer_fence_rejects_stale_and_equal():
    fence = ConsumerFence()
    l1 = _external_lease(1)
    assert fence.accept(l1) is True
    # A lease with an equal or lower token is rejected even if it "arrives later".
    stale = l1  # same token
    assert fence.accept(stale) is False


def test_write_requires_exact_previously_accepted_external_token():
    fence = ConsumerFence()
    # Positive or higher-looking numbers are not authority until the corresponding externally
    # validated ACTIVE lease has passed through accept().
    assert fence.accepts_write("scope", 1) is False
    assert fence.accepts_write("scope", 10_000) is False

    active = _external_lease(1)
    assert fence.accept(active) is True
    assert fence.accepts_write("scope", active.fencing_token) is True
    assert fence.accepts_write("scope", active.fencing_token + 1) is False
    assert fence.accepts_write("other-scope", active.fencing_token) is False
    assert fence.accepts_write("scope", True) is False
    assert fence.accepts_write([], 1) is False


@pytest.mark.parametrize("token", [True, 0, -1, "1"])
def test_consumer_fence_rejects_malformed_external_tokens(token):
    fence = ConsumerFence()
    malformed = Lease(
        lease_id="external-lease",
        scope="scope",
        producer_service="origin",
        producer_instance_id="i1",
        fencing_token=token,
        activation_manifest_id="a1",
        state=LeaseState.ACTIVE,
    )
    assert fence.accept(malformed) is False
    assert fence.accepts_write("scope", token) is False


def test_higher_external_lease_fences_old_token():
    fence = ConsumerFence()
    old = _external_lease(1)
    fence.accept(old)
    new = _external_lease(2)
    assert new.fencing_token > old.fencing_token
    assert new.state is LeaseState.ACTIVE
    assert fence.accept(new) is True
    assert fence.accepts_write("scope", old.fencing_token) is False
    assert fence.accepts_write("scope", new.fencing_token) is True


def test_consumer_fence_concurrent_accept_never_loses_high_watermark():
    fence = ConsumerFence()
    barrier = Barrier(2)

    def accept(token):
        barrier.wait()
        return fence.accept(_external_lease(token))

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(accept, [1, 2]))
    assert any(outcomes)
    assert fence.accepts_write("scope", 2)
    assert not fence.accepts_write("scope", 1)


def test_lease_scope_uses_canonical_unicode_identity():
    fence = ConsumerFence()
    assert fence.accept(_external_lease(1, scope="é"))
    assert fence.accept(_external_lease(2, scope="e\u0301"))
    assert fence.accepts_write("é", 2)
    assert not fence.accepts_write("e\u0301", 1)


def test_consumer_fence_rejects_noncanonical_scope_without_leaking():
    fence = ConsumerFence()
    assert not fence.accept(_external_lease(1, scope="\ud800"))
    fence.revoke("\ud800")
    assert not fence.accepts_write("\ud800", 1)


def test_revoked_scope_rejects_guessed_token_until_validated_replacement():
    fence = ConsumerFence()
    old = _external_lease(1)
    assert fence.accept(old)
    fence.revoke("scope")
    assert fence.accepts_write("scope", old.fencing_token + 10_000) is False
    guessed_replacement = _external_lease(old.fencing_token + 10_000)
    assert fence.accept(guessed_replacement) is False
    assert fence.accepts_write("scope", guessed_replacement.fencing_token) is False


# --- contract ingress ----------------------------------------------------------------------------
def test_ingress_accepts_valid_and_fences_epoch():
    gate = ContractIngress(boundary="e07-inbound")
    ev = _valid("triad.edge_candidate.v2")
    ev["producer_epoch"] = "10"
    res = gate.ingest(ev, expected_schema="triad.edge_candidate.v2", fence_scope="cand")
    assert isinstance(res, Accepted) and res.epoch == 10
    # Any number of events from the current epoch are accepted.
    ev2 = _valid("triad.edge_candidate.v2")
    ev2["event_id"] = "evt_second_current_epoch"
    ev2["producer_epoch"] = "10"
    res2 = gate.ingest(ev2, expected_schema="triad.edge_candidate.v2", fence_scope="cand")
    assert isinstance(res2, Accepted) and res2.epoch == 10

    stale = _valid("triad.edge_candidate.v2")
    stale["producer_epoch"] = "9"
    rejected = gate.ingest(stale, expected_schema="triad.edge_candidate.v2", fence_scope="cand")
    assert isinstance(rejected, Quarantined)
    assert "stale producer_epoch" in rejected.record["rejection_reason"]


def test_ingress_quarantines_invalid():
    gate = ContractIngress(boundary="e07-inbound")
    bad = _valid("triad.edge_candidate.v2")
    bad["payload"].pop("rr_numerator")
    res = gate.ingest(bad, expected_schema="triad.edge_candidate.v2")
    assert isinstance(res, Quarantined)
    assert res.record["contract_id"] == "triad.edge_candidate.v2"
    assert res.record["quarantine_id"].startswith("qtn_")
    assert isinstance(res.record["raw_reference"], str)
    envelope = _valid("triad.quarantine_record.v1")
    envelope["payload"] = res.record
    contracts.validate(envelope)


def test_ingress_rejects_noncanonical_nested_values_and_breaks_aliases():
    gate = ContractIngress(boundary="e07-inbound")
    noncanonical = _valid("triad.edge_candidate.v2")
    noncanonical["payload"]["nested_float"] = 1.5
    assert isinstance(gate.ingest(noncanonical), Quarantined)

    event = _valid("triad.edge_candidate.v2")
    result = gate.ingest(event, expected_schema="triad.edge_candidate.v2")
    assert isinstance(result, Accepted)
    original_id = result.event["event_id"]
    event["event_id"] = "mutated_after_validation"
    event["payload"]["account_id"] = "forbidden"
    assert result.event["event_id"] == original_id
    assert "account_id" not in result.event["payload"]
    returned = result.event
    returned["payload"]["account_id"] = "mutated-result"
    assert "account_id" not in result.event["payload"]


def test_ingress_quarantines_pathological_schema_identifier():
    gate = ContractIngress(boundary="b")
    result = gate.ingest({"schema": "x" * 5_000})
    assert isinstance(result, Quarantined)


def test_ingress_quarantines_surrogate_and_cyclic_objects_without_leaking():
    gate = ContractIngress(boundary="b")
    assert isinstance(gate.ingest({"schema": "x", "value": "\ud800"}), Quarantined)
    cyclic = {"schema": "x"}
    cyclic["self"] = cyclic
    assert isinstance(gate.ingest(cyclic), Quarantined)


@pytest.mark.parametrize("field", ["schema", "producer_service"])
def test_ingress_sanitizes_noncanonical_quarantine_metadata(field):
    gate = ContractIngress(boundary="b")
    result = gate.ingest({"schema": "x", field: "\ud800"})
    assert isinstance(result, Quarantined)
    assert result.record["contract_id" if field == "schema" else "source"] == "unknown"


@pytest.mark.parametrize("observed", [True, 1.5, "1", None, "\ud800", -1, 2**63])
def test_ingress_quarantines_invalid_observation_clock(observed):
    gate = ContractIngress(boundary="b")
    result = gate.ingest({"schema": "x"}, observed_at_us=observed)
    assert isinstance(result, Quarantined)
    assert result.record["observed_at_us"] == 0


def test_ingress_rejects_noncanonical_boundary_and_scope():
    with pytest.raises(ValueError, match="boundary"):
        ContractIngress(boundary="\ud800")
    gate = ContractIngress(boundary="b")
    event = _valid("triad.edge_candidate.v2")
    assert isinstance(gate.ingest(event, fence_scope="\ud800"), Quarantined)


def test_ingress_concurrent_epoch_updates_preserve_high_watermark():
    gate = ContractIngress(boundary="b")
    barrier = Barrier(2)

    def submit(epoch):
        event = _valid("triad.edge_candidate.v2")
        event["event_id"] = f"epoch-{epoch}"
        event["producer_epoch"] = str(epoch)
        barrier.wait()
        return gate.ingest(event, fence_scope="scope")

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(submit, [1, 2]))
    stale = _valid("triad.edge_candidate.v2")
    stale["producer_epoch"] = "1"
    assert isinstance(gate.ingest(stale, fence_scope="scope"), Quarantined)


# --- telemetry -----------------------------------------------------------------------------------
def test_telemetry_named_zero_reasons_only():
    t = telemetry.EvidenceTelemetry()
    t.bump("candidates", ("cap.v1", "BTC", "LONG"))
    t.zero("RR_BELOW_FLOOR", ("cap.v1", "BTC", "LONG"))
    with pytest.raises(telemetry.TelemetryError):
        t.zero("because_reasons", ("x",))
    with pytest.raises(telemetry.TelemetryError):
        t.bump("not_a_stage", ("x",))
    snap = t.snapshot()
    assert '["candidates","cap.v1","BTC","LONG"]' in snap["funnel"]


@pytest.mark.parametrize("bad", [-1, 0, True, 1.5, "1"])
def test_telemetry_rejects_nonpositive_or_noninteger_counts(bad):
    with pytest.raises(telemetry.TelemetryError):
        telemetry.EvidenceTelemetry().bump("candidates", ("cap.v1",), bad)


def test_telemetry_key_encoding_is_injective():
    t = telemetry.EvidenceTelemetry()
    t.bump("candidates", ("a|b", "c"))
    t.bump("candidates", ("a", "b|c"), 2)
    values = sorted(t.snapshot()["funnel"].values())
    assert values == [1, 2]


def test_telemetry_normalizes_unicode_before_series_identity():
    t = telemetry.EvidenceTelemetry()
    t.bump("candidates", ("é",))
    t.bump("candidates", ("e\u0301",), 2)
    assert list(t.snapshot()["funnel"].values()) == [3]


def test_telemetry_enforces_bounded_series_cardinality():
    t = telemetry.EvidenceTelemetry(max_series=1)
    t.bump("candidates", ("one",))
    with pytest.raises(telemetry.TelemetryError, match="cardinality"):
        t.bump("candidates", ("two",))


def test_telemetry_rejects_counter_overflow_and_serializes_cardinality():
    t = telemetry.EvidenceTelemetry(max_series=1)
    t.bump("candidates", ("one",), 2**63 - 1)
    with pytest.raises(telemetry.TelemetryError, match="overflow"):
        t.bump("candidates", ("one",))

    concurrent = telemetry.EvidenceTelemetry(max_series=1)
    barrier = Barrier(2)

    def add(label):
        barrier.wait()
        try:
            concurrent.bump("candidates", (label,))
        except telemetry.TelemetryError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(add, ["one", "two"]))
    assert sorted(outcomes) == [False, True]


# --- health ---------------------------------------------------------------------------------------
def test_readiness_is_dark_without_lease():
    r = health.compute_readiness(manifest_ok=True, warmup_complete=True, checkpoint_parity=True,
                                 ledgers_writable=True)
    assert r is Readiness.READY_NO_AUTHORITY
    r2 = health.compute_readiness(manifest_ok=True, warmup_complete=True, checkpoint_parity=True,
                                  ledgers_writable=True)
    assert r2 is Readiness.READY_NO_AUTHORITY
    r3 = health.compute_readiness(manifest_ok=False, warmup_complete=True, checkpoint_parity=True,
                                  ledgers_writable=True)
    assert r3 is Readiness.STARTING


def test_health_has_no_money_or_authoritative_readiness_state():
    assert all("MONEY" not in state.value for state in Readiness)
    assert all("AUTHORITATIVE" not in state.value for state in Readiness)


@pytest.mark.parametrize("bad", ["false", 1, 0, None])
def test_readiness_rejects_truthy_or_falsy_non_booleans(bad):
    with pytest.raises(ValueError, match="booleans"):
        health.compute_readiness(
            manifest_ok=bad,
            warmup_complete=True,
            checkpoint_parity=True,
            ledgers_writable=True,
        )


def test_heartbeat_cannot_claim_money():
    hb = health.build_service_heartbeat(partition_offsets={}, watermark={}, warmup_status="WARM",
                                        quality={}, lease_state="NONE")
    assert hb["side_effect_capability"] == "NONE"


def test_heartbeat_breaks_aliases_from_caller_owned_nested_inputs():
    offsets = {"p": "1"}
    watermark = {"event_time_us": 1}
    quality = {"state": "READY"}
    heartbeat = health.build_service_heartbeat(
        partition_offsets=offsets,
        watermark=watermark,
        warmup_status="WARM",
        quality=quality,
        lease_state="NONE",
    )
    offsets["p"] = "999"
    watermark["event_time_us"] = 999
    quality["state"] = "GAPPED"
    assert heartbeat["partition_offsets"] == {"p": "1"}
    assert heartbeat["watermark"] == {"event_time_us": 1}
    assert heartbeat["quality"] == {"state": "READY"}
    envelope = _valid("triad.service_heartbeat.v1")
    envelope["payload"] = heartbeat
    contracts.validate(envelope)


def test_active_lease_label_does_not_grant_dark_baseline_capability():
    hb = health.build_service_heartbeat(
        partition_offsets={},
        watermark={},
        warmup_status="READY",
        quality={},
        lease_state="ACTIVE",
    )
    assert hb["side_effect_capability"] == "NONE"


def test_engine_attestation_builder_emits_contract_valid_payload():
    digest = "1" * 64
    payload = health.build_engine_attestation(
        contract_manifest_sha256=digest,
        config_bundle_sha256=digest,
        build_commit="f" * 40,
        artifact_sha256=digest,
        parameter_set_id="dark-parameters",
        parameter_digest=digest,
        instrument_map_digest=digest,
        universe_digest=digest,
        activation_manifest_id="not-armed",
        producer_epoch="0",
        environment="offline",
        host_identity="test-host",
        startup_receipt_id="startup-test",
    )
    contracts.validate_payload("triad.engine_attestation.v1", payload)
    assert payload["universe_digest"] == digest
    assert payload["risk_policy_sha"] == ""
    assert payload["fee_model_id"] == ""


def test_engine_attestation_builder_rejects_missing_universe_identity():
    digest = "1" * 64
    with pytest.raises(contracts.ContractError):
        health.build_engine_attestation(
            contract_manifest_sha256=digest,
            config_bundle_sha256=digest,
            build_commit="f" * 40,
            artifact_sha256=digest,
            parameter_set_id="dark-parameters",
            parameter_digest=digest,
            instrument_map_digest=digest,
            universe_digest="",
            activation_manifest_id="not-armed",
            producer_epoch="0",
            environment="offline",
            host_identity="test-host",
            startup_receipt_id="startup-test",
        )


@pytest.mark.parametrize(
    "override",
    [
        {"contract_manifest_sha256": "0" * 64},
        {"parameter_set_id": ""},
        {"activation_manifest_id": ""},
        {"environment": ""},
        {"host_identity": ""},
        {"startup_receipt_id": ""},
    ],
)
def test_engine_attestation_builder_rejects_placeholder_identity(override):
    digest = "1" * 64
    args = {
        "contract_manifest_sha256": digest,
        "config_bundle_sha256": digest,
        "build_commit": "f" * 40,
        "artifact_sha256": digest,
        "parameter_set_id": "dark-parameters",
        "parameter_digest": digest,
        "instrument_map_digest": digest,
        "universe_digest": digest,
        "activation_manifest_id": "not-armed",
        "producer_epoch": "0",
        "environment": "offline",
        "host_identity": "test-host",
        "startup_receipt_id": "startup-test",
    }
    args.update(override)
    with pytest.raises(contracts.ContractError):
        health.build_engine_attestation(**args)
