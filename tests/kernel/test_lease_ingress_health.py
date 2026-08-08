"""Producer lease/fencing, contract ingress boundary, telemetry and health read-face."""

from __future__ import annotations

import json
import pathlib

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


def test_consumer_fence_rejects_stale_and_equal():
    fence = ConsumerFence()
    l1 = _external_lease(1)
    assert fence.accept(l1) is True
    # A lease with an equal or lower token is rejected even if it "arrives later".
    stale = l1  # same token
    assert fence.accept(stale) is False


def test_higher_external_lease_fences_old_token():
    fence = ConsumerFence()
    old = _external_lease(1)
    fence.accept(old)
    new = _external_lease(2)
    assert new.fencing_token > old.fencing_token
    assert new.state is LeaseState.ACTIVE
    assert fence.accept(new) is True
    assert fence.accepts_write("scope", old.fencing_token) is False


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
    assert any(k.startswith("candidates|") for k in snap["funnel"])


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


def test_heartbeat_cannot_claim_money():
    hb = health.build_service_heartbeat(partition_offsets={}, watermark={}, warmup_status="WARM",
                                        quality={}, lease_state="NONE")
    assert hb["side_effect_capability"] == "NONE"
    envelope = _valid("triad.service_heartbeat.v1")
    envelope["payload"] = hb
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
