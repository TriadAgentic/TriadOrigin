"""Producer lease/fencing, contract ingress boundary, telemetry and health read-face."""

from __future__ import annotations

import json
import pathlib

import pytest

from triad_origin import health, telemetry
from triad_origin.health import Readiness
from triad_origin.ingress import Accepted, ContractIngress, Quarantined
from triad_origin.lease import ConsumerFence, LeaseCoordinator, LeaseState

GOLDEN = pathlib.Path(__file__).resolve().parent.parent.parent / "contracts" / "golden"


def _valid(schema_id: str) -> dict:
    return json.loads((GOLDEN / schema_id / "valid.json").read_text(encoding="utf-8"))


# --- lease / fencing -----------------------------------------------------------------------------
def test_tokens_are_strictly_monotonic():
    lc = LeaseCoordinator()
    a = lc.issue("edge.candidates.v2.treatment", "origin", "inst1", "act1")
    b = lc.issue("edge.candidates.v2.treatment", "origin", "inst2", "act2")
    assert b.fencing_token > a.fencing_token


def test_consumer_fence_rejects_stale_and_equal():
    lc = LeaseCoordinator()
    fence = ConsumerFence()
    l1 = lc.activate(lc.issue("scope", "origin", "i1", "a1"))
    assert fence.accept(l1) is True
    # A lease with an equal or lower token is rejected even if it "arrives later".
    stale = l1  # same token
    assert fence.accept(stale) is False


def test_supersede_issues_higher_token_and_fences_old():
    lc = LeaseCoordinator()
    fence = ConsumerFence()
    old = lc.activate(lc.issue("scope", "origin", "i1", "a1"))
    fence.accept(old)
    new = lc.supersede("scope", "origin", "i2", "a2")
    assert new.fencing_token > old.fencing_token
    assert new.state is LeaseState.ACTIVE
    assert fence.accept(new) is True
    assert fence.accepts_write("scope", old.fencing_token) is False


# --- contract ingress ----------------------------------------------------------------------------
def test_ingress_accepts_valid_and_fences_epoch():
    gate = ContractIngress(boundary="e07-inbound")
    ev = _valid("triad.edge_candidate.v2")
    ev["producer_epoch"] = "10"
    res = gate.ingest(ev, expected_schema="triad.edge_candidate.v2", fence_scope="cand")
    assert isinstance(res, Accepted) and res.epoch == 10
    # A second event with a non-greater epoch is quarantined, not accepted.
    ev2 = _valid("triad.edge_candidate.v2")
    ev2["producer_epoch"] = "10"
    res2 = gate.ingest(ev2, expected_schema="triad.edge_candidate.v2", fence_scope="cand")
    assert isinstance(res2, Quarantined)
    assert "stale producer_epoch" in res2.record["rejection_reason"]


def test_ingress_quarantines_invalid():
    gate = ContractIngress(boundary="e07-inbound")
    bad = _valid("triad.edge_candidate.v2")
    bad["payload"].pop("rr_numerator")
    res = gate.ingest(bad, expected_schema="triad.edge_candidate.v2")
    assert isinstance(res, Quarantined)
    assert res.record["contract_id"] == "triad.edge_candidate.v2"
    assert res.record["quarantine_id"].startswith("qtn_")


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
                                 ledgers_writable=True, lease_active=False)
    assert r is Readiness.READY_NO_AUTHORITY
    r2 = health.compute_readiness(manifest_ok=True, warmup_complete=True, checkpoint_parity=True,
                                  ledgers_writable=True, lease_active=True)
    assert r2 is Readiness.READY_AUTHORITATIVE
    r3 = health.compute_readiness(manifest_ok=False, warmup_complete=True, checkpoint_parity=True,
                                  ledgers_writable=True, lease_active=True)
    assert r3 is Readiness.STARTING


def test_heartbeat_cannot_claim_money():
    hb = health.build_service_heartbeat(partition_offsets={}, watermark={}, warmup_status="WARM",
                                        quality="READY", lease_state="NONE")
    assert hb["side_effect_capability"]["money"] is False
