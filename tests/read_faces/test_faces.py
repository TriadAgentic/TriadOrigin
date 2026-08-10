"""B08 read-face battery: the six RC4 §L6 faces (LEV-0110..0115) as honest, read-only projections
of the B05 substrate — each returns the shared evidence envelope; requested/effective/proof are
carried separately (LEV-0120); SHADOW activation (the always-LIVE lever) is shown separately from
SHADOW health (LEV-0118); UNAVAILABLE (source absent) and NOT_MEASURABLE (source present, fact
uncomputable) are distinct named absences, never a fabricated zero; the LEV-0088 coverage compute is
an exact integer pair (no float); every read is bounded/paginated with honest truncation; raw legacy
values are echoed never translated (LEV-0116); and the no-clock / no-write-verb / capability-scan
structural walls hold."""

from __future__ import annotations

import ast
import inspect
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import transition  # noqa: E402
from triad_origin.control import lever_law  # noqa: E402
from triad_origin.control.lever_registry import LeverRegistry  # noqa: E402
from triad_origin.control.shadow_health import ShadowHealth  # noqa: E402
from triad_origin.read_faces import envelope as ev  # noqa: E402
from triad_origin.read_faces import faces  # noqa: E402

# Caller-frozen snapshot instant + source watermark (UTC epoch microseconds); a face never reads a
# clock, so every timestamp is a literal fixture.
AS_OF = 1_700_000_000_000_000
WATERMARK = 1_699_999_999_000_000

ALL_FACES = (
    faces.get_engine_lever_registry,
    faces.get_engine_lever_attestation,
    faces.get_engine_lever_history,
    faces.get_shadow_health,
    faces.get_four_plane_status,
    faces.get_engine_inventory_reconciliation,
)

# The scanner's closed allowed import-root set (verbatim, tools/verify_no_forbidden_capabilities.py).
_ALLOWED_ROOTS = frozenset({
    "__future__", "collections", "copy", "dataclasses", "decimal", "enum", "fcntl", "functools",
    "hashlib", "json", "jsonschema", "math", "os", "pathlib", "re", "threading", "typing",
    "unicodedata",
})


# ---------------------------------------------------------------------------------------------
# Fixture builders — drive the REAL substrate machines so a face projects real machine output
# ---------------------------------------------------------------------------------------------
def _manifest(revision, *, activations, digest="d1", **overrides):
    payload = {
        "venue_environment": "OFF", "venue_activation": "OFF", "paper_activation": "OFF",
        "shadow_activation": "LIVE", "activations": activations,
        "manifest_digest_sha256": digest, "revision": revision,
    }
    payload.update(overrides)
    return {"event_id": f"reg_{revision}_{digest}", "kind": "REGISTER_MANIFEST", "payload": payload}


def _attest(engine_id, digest, revision, freshness_age_ms):
    return {
        "event_id": f"att_{engine_id}_{revision}_{freshness_age_ms}", "kind": "ATTEST_RUNTIME",
        "payload": {"engine_id": engine_id, "accepted_manifest_digest_sha256": digest,
                    "accepted_revision": revision, "freshness_age_ms": freshness_age_ms}}


def _hb(age_ms):
    return {"event_id": f"hb_{age_ms}", "kind": "WRITER_HEARTBEAT", "payload": {"age_ms": age_ms}}


def _contaminate():
    return {"event_id": "contam_1", "kind": "RECORD_CONTAMINATION", "payload": {}}


def _registry_state(activations=None, attestations=(("origin.candidate", "d1", 1, 1000),)):
    acts = activations if activations is not None else {"origin.a": "OFF", "origin.b": "OFF"}
    inputs = [_manifest(1, activations=acts)]
    for engine_id, digest, revision, age in attestations:
        inputs.append(_attest(engine_id, digest, revision, age))
    return transition.run(LeverRegistry(), inputs, {}).final_state


def _shadow_health_state(heartbeat_age=2000, contaminated=False):
    inputs = [_hb(heartbeat_age)]
    if contaminated:
        inputs.append(_contaminate())
    return transition.run(ShadowHealth(), inputs, {}).final_state


def _shadow_ledger_state(trades=2, audits=1):
    return {
        "trades": {f"t{i}": {"origin_disposition": "REJECTED"} for i in range(trades)},
        "audits": {f"a{i}": {"marker": "SHADOW_UNTRADEABLE"} for i in range(audits)},
    }


def _paper_ledger_state():
    return {
        "accounts": {
            "acct1": {"balance_quote": "0", "orders": {"o1": {}, "o2": {}}, "fills": {"f1": {}},
                      "positions": {}}},
        "trades": {"pt1": {}},
    }


def _identities(**axes):
    return dict(axes)


# =============================================================================================
# Every face returns a self-validating envelope; determinism; detachment
# =============================================================================================
def test_every_face_returns_a_validating_envelope():
    envs = [
        faces.get_engine_lever_registry(registry_state=_registry_state(), as_of_us=AS_OF),
        faces.get_engine_lever_attestation(registry_state=_registry_state(), as_of_us=AS_OF),
        faces.get_engine_lever_history(transitions=[{"event_kind": "MANIFEST_ACCEPTED"}], as_of_us=AS_OF),
        faces.get_shadow_health(health_state=_shadow_health_state(), as_of_us=AS_OF),
        faces.get_four_plane_status(as_of_us=AS_OF, shadow_ledger_state=_shadow_ledger_state()),
        faces.get_engine_inventory_reconciliation(
            as_of_us=AS_OF, identities=_identities(registry={"expected": "x", "observed": "x"})),
    ]
    for env in envs:
        ev.validate(env)  # does not raise
        d = env.to_dict()
        assert d["status"] == ev.STATUS_AVAILABLE
        assert d["source"] and d["as_of_us"] == AS_OF  # every response NAMES its source + freshness
        assert d["evidence_view_version"] == ev.EVIDENCE_VIEW_VERSION


@pytest.mark.parametrize("call", [
    lambda: faces.get_engine_lever_registry(registry_state=_registry_state(), as_of_us=AS_OF),
    lambda: faces.get_shadow_health(
        health_state=_shadow_health_state(), ledger_state=_shadow_ledger_state(),
        as_of_us=AS_OF, rejected_inputs_presented=3),
    lambda: faces.get_four_plane_status(
        as_of_us=AS_OF, shadow_ledger_state=_shadow_ledger_state(),
        paper_ledger_state=_paper_ledger_state(), registry_state=_registry_state()),
])
def test_faces_are_deterministic(call):
    assert call().to_dict() == call().to_dict()


def test_read_of_record_detaches_from_input_and_output():
    state = _registry_state(activations={"origin.a": "OFF", "origin.b": "OFF"})
    env = faces.get_engine_lever_registry(registry_state=state, as_of_us=AS_OF)
    # mutating the INPUT after the call cannot change the projected value (deep-copied at the builder)
    state["levers"]["origin.a"]["value"] = "MUTATED"
    assert all(row["value"] == "OFF" for row in env.value["levers"])
    # mutating a returned view cannot corrupt a later read of the same envelope
    d1 = env.to_dict()
    d1["value"]["levers"].append("poison")
    assert "poison" not in env.to_dict()["value"]["levers"]


# =============================================================================================
# LEV-0110 · get_engine_lever_registry
# =============================================================================================
def test_registry_projects_raw_effective_proof_and_levers():
    state = _registry_state(activations={"origin.a": "OFF", "origin.b": "OFF"})
    env = faces.get_engine_lever_registry(
        registry_state=state, as_of_us=AS_OF, watermark_us=WATERMARK)
    v = env.value
    assert v["raw_source"] == state  # the verbatim raw source
    assert v["effective"]["revision"] == 1
    assert v["effective"]["accepted_manifest_digest_sha256"] == "d1"
    canon = v["effective"]["canonical"]
    # the ONE persisted canonical value is effective; shadow_activation is the structural LIVE
    assert canon["venue_environment"] == {"status": "AVAILABLE", "value": "OFF", "reason": None}
    assert canon["shadow_activation"]["value"] == "LIVE"
    # the two activations the registry does NOT persist are NOT_MEASURABLE — never an inferred value
    assert canon["venue_activation"]["status"] == ev.STATUS_NOT_MEASURABLE
    assert canon["paper_activation"]["status"] == ev.STATUS_NOT_MEASURABLE
    assert {row["lever_key"] for row in v["levers"]} == {"origin.a", "origin.b"}
    assert env.plane == ev.CONTROL_PLANE


def test_registry_requested_effective_and_proof_are_separate():
    state = _registry_state()
    requested = {"venue_environment": "TESTNET", "venue_activation": "LIVE",
                 "paper_activation": "OFF", "shadow_activation": "LIVE"}
    env = faces.get_engine_lever_registry(
        registry_state=state, as_of_us=AS_OF, requested_manifest=requested)
    v = env.value
    # requested is echoed VERBATIM and is a DISTINCT object from effective and proof (LEV-0120)
    assert v["requested"] == requested
    assert v["requested"] is not v["effective"]
    assert v["proof"]["accepted_manifest_digest_sha256"] == "d1"
    # configuration alone never claims enforcement — proof.effect_enforced is NOT_MEASURABLE
    assert v["proof"]["effect_enforced"]["status"] == ev.STATUS_NOT_MEASURABLE
    # without a supplied requested manifest, requested is None (it is not persisted anywhere)
    assert faces.get_engine_lever_registry(registry_state=state, as_of_us=AS_OF).value["requested"] is None


def test_registry_raw_legacy_value_is_echoed_never_translated():
    # LEV-0116 / LEV-V-0121: a raw legacy value is returned as-is; canonical stays untranslated.
    state = _registry_state()
    env = faces.get_engine_lever_registry(
        registry_state=state, as_of_us=AS_OF, raw_legacy_values={"BREAKOUT_MODE": "live"})
    assert env.value["raw_legacy_value"] == {"BREAKOUT_MODE": "live"}
    # the raw "live" is NEVER promoted into the canonical venue_environment
    assert env.value["effective"]["canonical"]["venue_environment"]["value"] == "OFF"


def test_registry_venue_environment_not_measurable_before_any_manifest():
    # LEV-V-0122: no accepted environment ⇒ do NOT infer OFF/LIVE/TESTNET — NOT_MEASURABLE.
    fresh = LeverRegistry().initial_state()
    env = faces.get_engine_lever_registry(registry_state=fresh, as_of_us=AS_OF)
    facet = env.value["effective"]["canonical"]["venue_environment"]
    assert facet["status"] == ev.STATUS_NOT_MEASURABLE and facet["value"] is None


def test_registry_unavailable_when_state_absent_never_a_fabricated_zero():
    env = faces.get_engine_lever_registry(registry_state=None, as_of_us=AS_OF)
    assert env.status == ev.STATUS_UNAVAILABLE
    assert env.value is None and env.reason  # no empty green, a named absence


def test_registry_levers_bounded_and_paginated():
    state = _registry_state(activations={"origin.a": "OFF", "origin.b": "OFF", "origin.c": "OFF"})
    first = faces.get_engine_lever_registry(registry_state=state, as_of_us=AS_OF, limit=2)
    assert first.returned == 2 and first.truncated is True and first.cursor is not None
    assert first.completeness == ev.COMPLETENESS_TRUNCATED
    second = faces.get_engine_lever_registry(
        registry_state=state, as_of_us=AS_OF, limit=2, after=first.cursor)
    assert second.truncated is False and second.cursor is None
    assert second.completeness == ev.COMPLETENESS_COMPLETE
    keys = {r["lever_key"] for r in first.value["levers"]} | {r["lever_key"] for r in second.value["levers"]}
    assert keys == {"origin.a", "origin.b", "origin.c"}  # the union recovers the whole table


# =============================================================================================
# LEV-0111 · get_engine_lever_attestation
# =============================================================================================
def test_attestation_lists_rows_and_detects_revision_mismatch():
    # attest at rev 1, then bump to rev 2 (digest d2): the stored attestation now mismatches current.
    state = transition.run(LeverRegistry(), [
        _manifest(1, activations={"origin.a": "OFF"}),
        _attest("engine.one", "d1", 1, 1000),
        _manifest(2, activations={"origin.a": "OFF"}, digest="d2"),
    ], {}).final_state
    env = faces.get_engine_lever_attestation(registry_state=state, as_of_us=AS_OF)
    row = env.value["attestations"][0]
    assert row["engine_id"] == "engine.one"
    assert row["revision_matches_current"] is False
    assert row["mismatch"] == "RUNTIME_LEVER_ATTESTATION_MISMATCH"
    # the rich proof lives only on the wire — honest NOT_MEASURABLE, never a fabricated readback
    for facet in ("process_readback", "route_environment", "account_environment", "lease"):
        assert row[facet]["status"] == ev.STATUS_NOT_MEASURABLE


def test_attestation_current_row_has_no_mismatch():
    state = transition.run(LeverRegistry(), [
        _manifest(1, activations={"origin.a": "OFF"}),
        _attest("engine.cur", "d1", 1, 500),
    ], {}).final_state
    row = faces.get_engine_lever_attestation(registry_state=state, as_of_us=AS_OF).value["attestations"][0]
    assert row["revision_matches_current"] is True and row["mismatch"] is None and row["stale"] is False


def test_attestation_stale_age_is_flagged_a_mismatch():
    # a constructed state whose stored age exceeds the 15,000 ms bound (the machine refuses storing
    # one this stale, so the face's defensive staleness projection is proven on a built state).
    state = {"revision": 1, "levers": {}, "accepted_manifest_digest_sha256": "d1",
             "attestations": {"engine.aged": {"accepted_revision": 1, "attested_age_ms": 99_000}},
             "venue_environment": "OFF"}
    row = faces.get_engine_lever_attestation(registry_state=state, as_of_us=AS_OF).value["attestations"][0]
    assert row["stale"] is True and row["mismatch"] == "RUNTIME_LEVER_ATTESTATION_MISMATCH"


def test_attestation_single_engine_found_and_not_found():
    state = _registry_state(attestations=(("engine.known", "d1", 1, 100),))
    found = faces.get_engine_lever_attestation(
        registry_state=state, as_of_us=AS_OF, engine_id="engine.known")
    assert found.value["attested"] is True
    missing = faces.get_engine_lever_attestation(
        registry_state=state, as_of_us=AS_OF, engine_id="engine.absent")
    # present registry, no attestation on record — a measurable fact, NEVER an inferred OFF
    assert missing.status == ev.STATUS_AVAILABLE
    assert missing.value["attested"] is False and missing.value["reason"]


def test_attestation_unavailable_when_state_absent():
    env = faces.get_engine_lever_attestation(registry_state=None, as_of_us=AS_OF)
    assert env.status == ev.STATUS_UNAVAILABLE and env.value is None


def test_attestation_bounded_and_paginated():
    state = _registry_state(attestations=(
        ("e1", "d1", 1, 1), ("e2", "d1", 1, 1), ("e3", "d1", 1, 1)))
    first = faces.get_engine_lever_attestation(registry_state=state, as_of_us=AS_OF, limit=2)
    assert first.returned == 2 and first.cursor is not None
    second = faces.get_engine_lever_attestation(
        registry_state=state, as_of_us=AS_OF, limit=2, after=first.cursor)
    assert second.cursor is None
    ids = {r["engine_id"] for r in first.value["attestations"]} | {
        r["engine_id"] for r in second.value["attestations"]}
    assert ids == {"e1", "e2", "e3"}


# =============================================================================================
# LEV-0112 · get_engine_lever_history
# =============================================================================================
def test_history_projects_ordered_transitions_and_census_refs():
    transitions = [{"event_kind": "MANIFEST_ACCEPTED", "revision": 1},
                   {"event_kind": "MANIFEST_ACCEPTED", "revision": 2}]
    env = faces.get_engine_lever_history(transitions=transitions, as_of_us=AS_OF)
    rows = env.value["transitions"]
    assert [r["sequence_index"] for r in rows] == [0, 1]  # order preserved (immutable stream)
    assert rows[0]["transition"]["revision"] == 1
    # census is an external durable artifact (LEV-0057) — NOT_MEASURABLE when not supplied
    assert rows[0]["side_effect_census_ref"]["status"] == ev.STATUS_NOT_MEASURABLE
    assert env.value["total_supplied"] == 2


def test_history_census_ref_available_when_supplied_and_missing_named():
    env = faces.get_engine_lever_history(
        transitions=[{"e": 1}, {"e": 2}], as_of_us=AS_OF, side_effect_census=["census-a", None])
    rows = env.value["transitions"]
    assert rows[0]["side_effect_census_ref"] == {"status": "AVAILABLE", "ref": "census-a", "reason": None}
    assert rows[1]["side_effect_census_ref"]["status"] == ev.STATUS_NOT_MEASURABLE  # named missing


def test_history_empty_is_measured_not_off_and_none_is_unavailable():
    empty = faces.get_engine_lever_history(transitions=[], as_of_us=AS_OF)
    # a measured-empty history is AVAILABLE (never inferred OFF, LEV-V-0123), not UNAVAILABLE
    assert empty.status == ev.STATUS_AVAILABLE and empty.value["transitions"] == []
    absent = faces.get_engine_lever_history(transitions=None, as_of_us=AS_OF)
    assert absent.status == ev.STATUS_UNAVAILABLE and absent.value is None


def test_history_bounded_preserves_order_across_pages():
    transitions = [{"n": i} for i in range(5)]
    first = faces.get_engine_lever_history(transitions=transitions, as_of_us=AS_OF, limit=2)
    second = faces.get_engine_lever_history(
        transitions=transitions, as_of_us=AS_OF, limit=2, after=first.cursor)
    third = faces.get_engine_lever_history(
        transitions=transitions, as_of_us=AS_OF, limit=2, after=second.cursor)
    order = ([r["transition"]["n"] for r in first.value["transitions"]]
             + [r["transition"]["n"] for r in second.value["transitions"]]
             + [r["transition"]["n"] for r in third.value["transitions"]])
    assert order == [0, 1, 2, 3, 4] and third.cursor is None


def test_history_census_length_mismatch_is_refused():
    with pytest.raises(ev.ReadFaceEnvelopeError):
        faces.get_engine_lever_history(
            transitions=[{"a": 1}, {"a": 2}], as_of_us=AS_OF, side_effect_census=["only-one"])


# =============================================================================================
# LEV-0113 · get_shadow_health  (+ LEV-0088 coverage)
# =============================================================================================
def test_shadow_activation_is_shown_separately_from_shadow_health():
    env = faces.get_shadow_health(health_state=_shadow_health_state(), as_of_us=AS_OF)
    v = env.value
    # LEV-0118: the always-LIVE lever and the health gauges are DISTINCT blocks
    assert v["shadow_activation"]["value"] == "LIVE" and v["shadow_activation"]["user_switchable"] is False
    assert "writer_heartbeat_age_ms" in v["health"]  # health carries the gauges
    assert "writer_heartbeat_age_ms" not in v["shadow_activation"]  # activation is not a health signal
    assert "value" not in v["health"]  # health carries no lever value
    assert env.plane == ev.PLANE_SHADOW


def test_shadow_health_gauges_and_staleness_are_honest():
    fresh = faces.get_shadow_health(health_state=_shadow_health_state(heartbeat_age=2000), as_of_us=AS_OF)
    assert fresh.value["health"]["heartbeat_stale"] is False
    stale = faces.get_shadow_health(health_state=_shadow_health_state(heartbeat_age=6000), as_of_us=AS_OF)
    assert stale.value["health"]["heartbeat_stale"] is True
    # a never-observed heartbeat is None (honest), never a fabricated False
    never = faces.get_shadow_health(health_state=ShadowHealth().initial_state(), as_of_us=AS_OF)
    assert never.value["health"]["heartbeat_stale"] is None
    contam = faces.get_shadow_health(
        health_state=_shadow_health_state(contaminated=True), as_of_us=AS_OF)
    assert contam.value["health"]["contaminated"] is True


def test_shadow_coverage_landed_as_exact_integer_pair_no_float():
    # LEV-0088: 2 tradeable + 1 untradeable = 3 reconciled; presented 3 ⇒ fully reconciled.
    env = faces.get_shadow_health(
        health_state=_shadow_health_state(), ledger_state=_shadow_ledger_state(trades=2, audits=1),
        as_of_us=AS_OF, rejected_inputs_presented=3)
    cov = env.value["coverage"]
    assert cov["status"] == ev.STATUS_AVAILABLE
    assert cov["reconciled_tradeable_hypotheses"] == 2 and cov["reconciled_untradeable_audits"] == 1
    assert cov["reconciled_total"] == 3 and cov["fully_reconciled"] is True
    assert isinstance(cov["reconciled_total"], int) and isinstance(cov["fully_reconciled"], bool)
    assert not any(isinstance(x, float) for x in cov.values())  # determinism: no float ratio
    short = faces.get_shadow_health(
        health_state=_shadow_health_state(), ledger_state=_shadow_ledger_state(trades=2, audits=1),
        as_of_us=AS_OF, rejected_inputs_presented=4)
    assert short.value["coverage"]["fully_reconciled"] is False


def test_shadow_coverage_unavailable_vs_not_measurable_are_distinct():
    # no ledger ⇒ coverage UNAVAILABLE (source absent); no presented total ⇒ NOT_MEASURABLE (present,
    # uncomputable). The two honest-null statuses are never the same fact — and the envelope stays
    # AVAILABLE (health IS present) in both cases.
    no_ledger = faces.get_shadow_health(
        health_state=_shadow_health_state(), ledger_state=None, as_of_us=AS_OF,
        rejected_inputs_presented=3)
    no_total = faces.get_shadow_health(
        health_state=_shadow_health_state(), ledger_state=_shadow_ledger_state(),
        as_of_us=AS_OF, rejected_inputs_presented=None)
    assert no_ledger.status == ev.STATUS_AVAILABLE and no_total.status == ev.STATUS_AVAILABLE
    assert no_ledger.value["coverage"]["status"] == ev.STATUS_UNAVAILABLE
    assert no_total.value["coverage"]["status"] == ev.STATUS_NOT_MEASURABLE
    assert no_ledger.value["coverage"]["status"] != no_total.value["coverage"]["status"]
    # NOT_MEASURABLE coverage still shows the reconciled counts but no fabricated verdict
    assert no_total.value["coverage"]["reconciled_total"] == 3
    assert no_total.value["coverage"]["fully_reconciled"] is None


def test_shadow_persist_latency_is_not_measurable():
    v = faces.get_shadow_health(health_state=_shadow_health_state(), as_of_us=AS_OF).value
    assert v["rejection_persist"]["status"] == ev.STATUS_NOT_MEASURABLE
    assert v["rejection_persist"]["deadline_ms"] == 100  # the 100 ms bound, from the timing table


def test_shadow_health_unavailable_when_state_absent():
    env = faces.get_shadow_health(health_state=None, as_of_us=AS_OF)
    assert env.status == ev.STATUS_UNAVAILABLE and env.value is None  # no fabricated zero counts


# =============================================================================================
# LEV-0114 · get_four_plane_status
# =============================================================================================
def test_four_planes_are_separate_shadow_live_testnet_live_unavailable():
    env = faces.get_four_plane_status(
        as_of_us=AS_OF, shadow_ledger_state=_shadow_ledger_state(),
        paper_ledger_state=_paper_ledger_state(), registry_state=_registry_state())
    planes = env.value["planes"]
    assert set(planes) == {"SHADOW", "PAPER", "TESTNET", "LIVE"}
    assert planes["SHADOW"]["activation"] == "LIVE"
    # TESTNET / LIVE hold no venue truth in-repo ⇒ UNAVAILABLE, never inferred OFF (LEV-V-0122)
    assert planes["TESTNET"]["status"] == ev.STATUS_UNAVAILABLE and planes["TESTNET"]["reason"]
    assert planes["LIVE"]["status"] == ev.STATUS_UNAVAILABLE
    assert planes["PAPER"]["real_money"] is False
    assert env.plane is None  # the face spans all four populations


def test_four_plane_shadow_activation_separate_from_counts():
    # activation is the structural LIVE lever even when the ledger source is absent (data ≠ activation)
    env = faces.get_four_plane_status(as_of_us=AS_OF, shadow_ledger_state=None)
    assert env.value["planes"]["SHADOW"]["activation"] == "LIVE"
    assert env.value["planes"]["SHADOW"]["counts"]["status"] == ev.STATUS_UNAVAILABLE


def test_four_plane_requested_effective_proof_authority_evidence_separate():
    env = faces.get_four_plane_status(as_of_us=AS_OF, registry_state=_registry_state())
    auth = env.value["authority_evidence"]
    assert auth["requested_baseline_manifest"] == lever_law.BASELINE_MANIFEST  # the OFF/OFF/OFF/LIVE baseline
    assert auth["effective"]["venue_environment"]["value"] == "OFF"
    assert auth["proof"]["accepted_manifest_digest_sha256"] == "d1"
    assert auth["live_requires_testnet_promotion_receipt"] is True


def test_four_plane_counts_from_ledgers():
    env = faces.get_four_plane_status(
        as_of_us=AS_OF, shadow_ledger_state=_shadow_ledger_state(trades=2, audits=1),
        paper_ledger_state=_paper_ledger_state())
    assert env.value["planes"]["SHADOW"]["counts"] == {"status": "AVAILABLE", "trades": 2, "audits": 1}
    paper = env.value["planes"]["PAPER"]["counts"]
    assert paper["accounts"] == 1 and paper["orders"] == 2 and paper["fills"] == 1 and paper["trades"] == 1


def test_four_plane_effective_env_not_measurable_before_manifest():
    env = faces.get_four_plane_status(as_of_us=AS_OF, registry_state=None)
    facet = env.value["authority_evidence"]["effective"]["venue_environment"]
    assert facet["status"] == ev.STATUS_NOT_MEASURABLE and facet["value"] is None


# =============================================================================================
# LEV-0115 · get_engine_inventory_reconciliation
# =============================================================================================
def test_inventory_joins_seven_axes_in_fixed_order():
    ids = {axis: {"expected": "x", "observed": "x"} for axis in faces.INVENTORY_AXES}
    env = faces.get_engine_inventory_reconciliation(as_of_us=AS_OF, identities=ids)
    assert env.value["axis_order"] == list(faces.INVENTORY_AXES)
    assert [r["axis"] for r in env.value["axes"]] == list(faces.INVENTORY_AXES)
    assert all(r["status"] == ev.STATUS_AVAILABLE and r["contradiction"] is False for r in env.value["axes"])
    assert env.value["any_contradiction"] is False


def test_inventory_contradiction_surfaces_both_facts_never_single_green():
    # LEV-V-0124: a mismatch surfaces both the expected and observed identity + freshness, and is a
    # NAMED contradiction — never one green liveness claim.
    ids = {"registry": {"expected": "a", "observed": "a", "freshness_us": 10},
           "relay": {"expected": "b", "observed": "c", "freshness_us": 5}}
    env = faces.get_engine_inventory_reconciliation(as_of_us=AS_OF, identities=ids)
    rows = {r["axis"]: r for r in env.value["axes"]}
    assert rows["relay"]["contradiction"] is True
    assert rows["relay"]["expected"] == "b" and rows["relay"]["observed"] == "c"
    assert rows["relay"]["freshness_us"] == 5
    assert env.value["any_contradiction"] is True and env.value["contradiction_axes"] == ["relay"]


def test_inventory_absent_axis_unavailable_single_sided_not_measurable():
    ids = {"registry": {"expected": "x", "observed": "x"}, "payload": {"expected": "only"}}
    # config/relay/service/fill/repository are absent ⇒ UNAVAILABLE; payload is single-sided ⇒
    # NOT_MEASURABLE; the two honest-null statuses are distinct.
    env = faces.get_engine_inventory_reconciliation(as_of_us=AS_OF, identities=ids)
    rows = {r["axis"]: r for r in env.value["axes"]}
    assert rows["config"]["status"] == ev.STATUS_UNAVAILABLE
    assert rows["payload"]["status"] == ev.STATUS_NOT_MEASURABLE
    assert rows["config"]["status"] != rows["payload"]["status"]


def test_inventory_unavailable_source_vs_present_but_empty():
    absent = faces.get_engine_inventory_reconciliation(as_of_us=AS_OF, identities=None)
    assert absent.status == ev.STATUS_UNAVAILABLE and absent.value is None  # no join source at all
    empty = faces.get_engine_inventory_reconciliation(as_of_us=AS_OF, identities={})
    # present but empty ⇒ AVAILABLE with all seven axes honestly UNAVAILABLE (never a fabricated join)
    assert empty.status == ev.STATUS_AVAILABLE
    assert all(r["status"] == ev.STATUS_UNAVAILABLE for r in empty.value["axes"])


def test_inventory_bounded_and_paginated():
    ids = {axis: {"expected": "x", "observed": "x"} for axis in faces.INVENTORY_AXES}
    first = faces.get_engine_inventory_reconciliation(as_of_us=AS_OF, identities=ids, limit=3)
    assert first.returned == 3 and first.cursor is not None
    second = faces.get_engine_inventory_reconciliation(
        as_of_us=AS_OF, identities=ids, limit=3, after=first.cursor)
    third = faces.get_engine_inventory_reconciliation(
        as_of_us=AS_OF, identities=ids, limit=3, after=second.cursor)
    seen = [r["axis"] for r in first.value["axes"]] + [r["axis"] for r in second.value["axes"]] + [
        r["axis"] for r in third.value["axes"]]
    assert seen == list(faces.INVENTORY_AXES) and third.cursor is None


# =============================================================================================
# Cross-face structural walls: read-only / capability scan / no-clock / bounded-cursor guards
# =============================================================================================
def test_capability_scanner_passes_over_the_read_face_package():
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "verify_no_forbidden_capabilities.py")],
        cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, (result.stdout, result.stderr)


def test_faces_module_imports_only_allowed_roots_or_relative():
    source = (ROOT / "src" / "triad_origin" / "read_faces" / "faces.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    saw_relative = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] in _ALLOWED_ROOTS, alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:  # a relative triad_origin import — allowed
                saw_relative = True
                continue
            assert (node.module or "").split(".")[0] in _ALLOWED_ROOTS, node.module
    assert saw_relative  # the substrate dependencies are internal/relative


def test_no_write_verb_or_credential_in_the_public_surface():
    # write-verb prefixes + the scanner's exact forbidden identifiers. (Reason CONSTANTS legitimately
    # name the venue-truth axis they REFUSE to observe, so a bare "venue" substring is NOT banned;
    # the capability scanner is the authoritative wall and it is exercised above.)
    banned_prefixes = ("issue_", "admit_", "select_authority", "arm_", "activate_", "place_",
                       "submit_", "send_", "create_", "cancel_", "amend_")
    forbidden_ids = ("api_key", "api_secret", "arm_token", "private_key", "secret_key",
                     "venue_credentials")
    for name in dir(faces):
        if name.startswith("_"):
            continue
        assert not name.startswith(banned_prefixes), name
        assert name not in forbidden_ids, name


@pytest.mark.parametrize("face", ALL_FACES)
def test_every_face_takes_as_of_us_with_no_default(face):
    # the no-clock law, structural: freshness is a required caller input, never a read clock.
    param = inspect.signature(face).parameters["as_of_us"]
    assert param.default is inspect.Parameter.empty
    assert param.kind is inspect.Parameter.KEYWORD_ONLY


def test_a_bad_cursor_fails_closed_named():
    with pytest.raises(ev.ReadFaceEnvelopeError):
        faces.get_engine_lever_registry(registry_state=_registry_state(), as_of_us=AS_OF, after="not-a-cursor")
    with pytest.raises(ev.ReadFaceEnvelopeError):
        faces.get_engine_lever_registry(registry_state=_registry_state(), as_of_us=AS_OF, limit=-1)
