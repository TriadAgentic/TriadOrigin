"""CO-03 (TRIAD-ORIGIN-V7-CHANGE-ORDERS-2026-08-12) — the contract-union additions.

Covers the four union majors (evidence_view.v2, raw_venue_event.v2, runtime_lifecycle.v2,
signed_recommendation.v1), transport_bindings.v1, venue_execution_plan.v1 (VenueExecutionPlan.v1
in the order's spelling; repo identifier grammar requires lowercase snake), and the six E03-E06
advisory-chain stubs.

Laws under test, each fail-closed:
* the exact closed enums the order names (B08 status; E00 payload_kind; deployment_class);
* structural quarantine flags (gap/clock/dq) and the lease{topic, epoch, ttl} shape;
* decision_authority is const NONE on every advisory contract — consumers read, never auto-apply;
* transport bindings resolve through ONE registry whose unknown-binding refusal is the NAMED
  const TRANSPORT_BINDING_UNKNOWN, never a silent default;
* venue_execution_plan is field-complete for GV-018's variants (sparse level, zone-outside-book,
  GTX race) and ordinal_budget is a bounded integer 0..4;
* the CO-03 STOP RULE: every E03-E06 stub carries ONLY names + lineage/no-authority fields, is
  marked x-status CONTRACT_RATIFICATION_REQUIRED (OWNER-TOPO-01 is adjudicated, NOT signed), and
  its CLOSED payload refuses any smuggled body field;
* validator absence yields SCHEMA_VALIDATOR_UNAVAILABLE, never a silent pass.

Nothing here activates anything: all twelve contracts are DARK additive majors; posture stays
OFF/OFF/OFF/LIVE, DENIED_SAFE_HOLD.
"""

from __future__ import annotations

import copy
import json
import pathlib

import pytest

from triad_origin import contracts

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
GOLDEN = ROOT / "contracts" / "golden"
SCHEMAS = ROOT / "contracts" / "schemas"

UNION_IDS = [
    "triad.evidence_view.v2",
    "triad.raw_venue_event.v2",
    "triad.runtime_lifecycle.v2",
    "triad.signed_recommendation.v1",
]
REGISTRY_AND_PLAN_IDS = [
    "triad.transport_bindings.v1",
    "triad.venue_execution_plan.v1",
]
STUB_IDS = [
    "triad.forecast_request.v2",
    "triad.forecast_response.v2",
    "triad.logos_prompt_packet.v1",
    "triad.logos_explanation.v1",
    "triad.logos_contradiction_report.v1",
    "triad.e05_intelligence_bundle.v1",
]
CO03_IDS = UNION_IDS + REGISTRY_AND_PLAN_IDS + STUB_IDS

STUB_LINEAGE_FIELDS = [
    "artifact_version", "model_version", "prompt_version", "retrieval_version",
    "uncertainty", "calibration", "freshness", "citations", "decision_authority",
]


def _schema(schema_id: str) -> dict:
    return json.loads((SCHEMAS / f"{schema_id}.schema.json").read_text(encoding="utf-8"))


def _valid(schema_id: str) -> dict:
    return json.loads((GOLDEN / schema_id / "valid.json").read_text(encoding="utf-8"))


# --- registration -------------------------------------------------------------------------------
def test_all_twelve_co03_contracts_are_registered():
    known = set(contracts.known_contracts())
    for cid in CO03_IDS:
        assert cid in known, cid
    assert len(known) == 56


def test_registry_entries_follow_the_existing_convention():
    index = json.loads((ROOT / "contracts/registry/index.json").read_text(encoding="utf-8"))
    by_id = {c["contract_id"]: c for c in index["contracts"]}
    for cid in CO03_IDS:
        entry = by_id[cid]
        assert entry["schema_path"] == f"contracts/schemas/{cid}.schema.json"
        assert entry["schema_version"] == _schema(cid)["properties"]["schema_version"]["const"]


@pytest.mark.parametrize("schema_id", CO03_IDS)
def test_schemas_are_draft_2020_12_on_the_authoritative_path(schema_id):
    schema = _schema(schema_id)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["title"] == schema_id
    assert schema["additionalProperties"] is False  # envelope closed, per repo law


# --- evidence_view.v2: the exact B08 envelope law ------------------------------------------------
def test_evidence_view_status_enum_is_exactly_the_b08_seven():
    schema = _schema("triad.evidence_view.v2")
    status = schema["properties"]["payload"]["properties"]["status"]
    assert status["enum"] == ["OK", "UNAVAILABLE", "NOT_IMPLEMENTED", "TOOL_TIMEOUT",
                              "NOT_MEASURABLE", "STALE", "NOT_ATTESTED"]


def test_evidence_view_requires_every_envelope_law_field():
    required = set(_schema("triad.evidence_view.v2")["properties"]["payload"]["required"])
    assert required == {"source", "plane", "cohort", "scope", "producer_rev", "build_digest",
                        "config_digest", "contract_digest", "binding_digest", "event_time",
                        "observation_time", "freshness_ms", "completeness", "status", "payload"}


def test_evidence_view_presence_word_never_reads_as_status():
    event = _valid("triad.evidence_view.v2")
    contracts.validate(event)
    for banned in ("PRESENT", "PASSED", "ok", "present"):
        bad = copy.deepcopy(event)
        bad["payload"]["status"] = banned
        with pytest.raises(contracts.ContractError):
            contracts.validate(bad)


def test_evidence_view_not_attested_and_unavailable_are_first_class():
    event = _valid("triad.evidence_view.v2")
    for honest in ("NOT_ATTESTED", "UNAVAILABLE", "STALE"):
        stamped = copy.deepcopy(event)
        stamped["payload"]["status"] = honest
        contracts.validate(stamped)


# --- raw_venue_event.v2: E00 fact ----------------------------------------------------------------
def test_raw_venue_event_payload_kind_enum_is_exact():
    schema = _schema("triad.raw_venue_event.v2")
    kinds = schema["properties"]["payload"]["properties"]["payload_kind"]
    assert kinds["enum"] == ["trade", "book_delta", "book_snapshot", "account", "order",
                              "funding", "mark"]


def test_raw_venue_event_quarantine_flags_are_structural():
    schema = _schema("triad.raw_venue_event.v2")
    flags = schema["properties"]["payload"]["properties"]["quarantine_flags"]
    assert flags["required"] == ["gap", "clock", "dq"]
    assert flags["additionalProperties"] is False
    event = _valid("triad.raw_venue_event.v2")
    contracts.validate(event)
    for missing in ("gap", "clock", "dq"):
        bad = copy.deepcopy(event)
        del bad["payload"]["quarantine_flags"][missing]
        with pytest.raises(contracts.ContractError):
            contracts.validate(bad)


def test_raw_venue_event_is_authority_fenced_replayable_fact():
    # Immutable/replayable E00 fact rides the fenced-authority law: producer_epoch is required.
    schema = _schema("triad.raw_venue_event.v2")
    assert "producer_epoch" in schema["required"]


# --- runtime_lifecycle.v2: process truth ---------------------------------------------------------
def test_runtime_lifecycle_deployment_class_enum_is_exact():
    schema = _schema("triad.runtime_lifecycle.v2")
    dc = schema["properties"]["payload"]["properties"]["deployment_class"]
    assert dc["enum"] == ["ACTIVE_WRITER", "REPLICA", "MIRROR", "DARK", "RETIRED"]


def test_runtime_lifecycle_lease_shape_is_topic_epoch_ttl():
    schema = _schema("triad.runtime_lifecycle.v2")
    lease = schema["properties"]["payload"]["properties"]["lease"]
    assert lease["required"] == ["topic", "epoch", "ttl"]
    assert lease["additionalProperties"] is False
    event = _valid("triad.runtime_lifecycle.v2")
    contracts.validate(event)
    bad = copy.deepcopy(event)
    del bad["payload"]["lease"]["epoch"]
    with pytest.raises(contracts.ContractError):
        contracts.validate(bad)


def test_runtime_lifecycle_golden_declares_dark_not_active_writer():
    # The honest current posture: no CO-03 registration creates an active writer.
    assert _valid("triad.runtime_lifecycle.v2")["payload"]["deployment_class"] == "DARK"


def test_runtime_lifecycle_requires_all_four_identity_digests():
    required = set(_schema("triad.runtime_lifecycle.v2")["properties"]["payload"]["required"])
    assert {"build_digest", "config_digest", "contract_digest", "binding_digest",
            "attestation_time", "plane_bindings", "component_id"} <= required


# --- signed_recommendation.v1: advisory, never auto-applied --------------------------------------
def test_signed_recommendation_decision_authority_is_const_none():
    schema = _schema("triad.signed_recommendation.v1")
    da = schema["properties"]["payload"]["properties"]["decision_authority"]
    assert da["enum"] == ["NONE"]
    event = _valid("triad.signed_recommendation.v1")
    contracts.validate(event)
    for grabbed in ("FULL", "EXECUTE", "AUTO_APPLY", ""):
        bad = copy.deepcopy(event)
        bad["payload"]["decision_authority"] = grabbed
        with pytest.raises(contracts.ContractError):
            contracts.validate(bad)


def test_signed_recommendation_is_hard_split_from_outcome():
    # Its own contract id and event kind — never an outcome.* alias.
    schema = _schema("triad.signed_recommendation.v1")
    assert schema["properties"]["event_kind"]["enum"] == ["SIGNED_RECOMMENDATION"]
    assert "outcome" not in schema["properties"]["schema"]["const"]


# --- transport_bindings.v1: one owner, named refusal ---------------------------------------------
def test_transport_bindings_unknown_binding_refusal_is_the_named_const():
    schema = _schema("triad.transport_bindings.v1")
    refusal = schema["properties"]["payload"]["properties"]["unknown_binding_refusal"]
    assert refusal["enum"] == ["TRANSPORT_BINDING_UNKNOWN"]
    event = _valid("triad.transport_bindings.v1")
    contracts.validate(event)
    bad = copy.deepcopy(event)
    bad["payload"]["unknown_binding_refusal"] = "SILENT_DEFAULT"
    with pytest.raises(contracts.ContractError):
        contracts.validate(bad)


def test_transport_bindings_rows_are_closed_and_typed():
    schema = _schema("triad.transport_bindings.v1")
    items = schema["properties"]["payload"]["properties"]["bindings"]["items"]
    assert items["required"] == ["logical_topic", "transport_kind", "exact_binding", "owner"]
    assert items["additionalProperties"] is False
    assert items["properties"]["transport_kind"]["enum"] == [
        "TOPIC", "FILENAME", "DATABASE_PATH", "OBJECT_PATH"]
    # A row missing its exact binding is refused by the full validator.
    event = _valid("triad.transport_bindings.v1")
    bad = copy.deepcopy(event)
    del bad["payload"]["bindings"][0]["exact_binding"]
    with pytest.raises(contracts.ContractError):
        contracts.validate(bad)


# --- venue_execution_plan.v1: CO-03 step 6 / GV-018 variants -------------------------------------
def test_venue_execution_plan_carries_the_exact_step6_field_list():
    required = set(_schema("triad.venue_execution_plan.v1")["properties"]["payload"]["required"])
    assert required == {"authorization_ref", "economic_purpose", "side", "instrument_id",
                        "account_mode", "zone", "observed_book", "ordinal_budget",
                        "reprice_budget", "ttl_ms", "price_filters", "price_bands",
                        "idempotency_key_law", "refusal_codes"}


def test_venue_execution_plan_ordinal_budget_is_bounded_0_to_4():
    schema = _schema("triad.venue_execution_plan.v1")
    ob = schema["properties"]["payload"]["properties"]["ordinal_budget"]
    assert ob == {"type": "integer", "minimum": 0, "maximum": 4}
    event = _valid("triad.venue_execution_plan.v1")
    for lawful in (0, 4):
        ok = copy.deepcopy(event)
        ok["payload"]["ordinal_budget"] = lawful
        contracts.validate(ok)
    for out_of_band in (-1, 5):
        bad = copy.deepcopy(event)
        bad["payload"]["ordinal_budget"] = out_of_band
        with pytest.raises(contracts.ContractError):
            contracts.validate(bad)


def test_venue_execution_plan_gv018_sparse_level_variant_is_representable():
    # Sparse level: a non-contiguous — even empty — explicit level list validates.
    event = _valid("triad.venue_execution_plan.v1")
    sparse = copy.deepcopy(event)
    sparse["payload"]["observed_book"]["levels"] = [
        {"price_ticks": "101", "qty_steps": "5"},
        {"price_ticks": "97", "qty_steps": "2"},  # gap between 101 and 97 is lawful
    ]
    contracts.validate(sparse)
    empty = copy.deepcopy(event)
    empty["payload"]["observed_book"]["levels"] = []
    contracts.validate(empty)


def test_venue_execution_plan_gv018_zone_outside_book_variant_is_representable():
    # zone[z0,z1] is not range-bound to the observed book — the plan carries both facts.
    event = _valid("triad.venue_execution_plan.v1")
    outside = copy.deepcopy(event)
    outside["payload"]["zone"] = {"z0": "-500", "z1": "-600"}
    contracts.validate(outside)


def test_venue_execution_plan_gv018_gtx_race_variant_is_representable():
    # GTX race: the race outcome travels as a named token in refusal_codes (sample token; the
    # authoritative token vocabulary is owned by the F21/GV-018 goldens, not invented here).
    event = _valid("triad.venue_execution_plan.v1")
    race = copy.deepcopy(event)
    race["payload"]["refusal_codes"] = ["GTX_RACE_SAMPLE_TOKEN"]
    contracts.validate(race)


def test_venue_execution_plan_zone_is_closed_and_complete():
    event = _valid("triad.venue_execution_plan.v1")
    bad = copy.deepcopy(event)
    del bad["payload"]["zone"]["z1"]
    with pytest.raises(contracts.ContractError):
        contracts.validate(bad)


def test_venue_execution_plan_forbids_credentials_and_venue_ids():
    # A plan precedes any venue identity and never carries credentials.
    event = _valid("triad.venue_execution_plan.v1")
    for forbidden in ("raw_credentials", "venue_order_id", "venue_trade_id"):
        bad = copy.deepcopy(event)
        bad["payload"][forbidden] = "x"
        with pytest.raises(contracts.ContractError):
            contracts.validate(bad)


# --- E03-E06 stubs: the CO-03 stop rule ----------------------------------------------------------
@pytest.mark.parametrize("schema_id", STUB_IDS)
def test_stub_is_marked_contract_ratification_required(schema_id):
    schema = _schema(schema_id)
    assert schema["x-status"] == "CONTRACT_RATIFICATION_REQUIRED"
    # The registry row carries the same flag so no reader mistakes registration for ratification.
    index = json.loads((ROOT / "contracts/registry/index.json").read_text(encoding="utf-8"))
    by_id = {c["contract_id"]: c for c in index["contracts"]}
    assert by_id[schema_id]["x_status"] == "CONTRACT_RATIFICATION_REQUIRED"


@pytest.mark.parametrize("schema_id", STUB_IDS)
def test_stub_carries_only_lineage_and_no_authority_fields(schema_id):
    payload = _schema(schema_id)["properties"]["payload"]
    assert payload["required"] == STUB_LINEAGE_FIELDS
    assert set(payload["properties"]) == set(STUB_LINEAGE_FIELDS)
    assert payload["additionalProperties"] is False  # closed: bodies cannot land early


@pytest.mark.parametrize("schema_id", STUB_IDS)
def test_stub_decision_authority_is_none_and_never_widens(schema_id):
    event = _valid(schema_id)
    assert event["payload"]["decision_authority"] == "NONE"
    contracts.validate(event)
    bad = copy.deepcopy(event)
    bad["payload"]["decision_authority"] = "FULL"
    with pytest.raises(contracts.ContractError):
        contracts.validate(bad)


@pytest.mark.parametrize("schema_id", STUB_IDS)
def test_stub_refuses_a_smuggled_body(schema_id):
    # The stop rule structurally: no contract body beyond lineage/no-authority fields until the
    # signed CO-14 decision. A body field is refused by the closed payload.
    event = _valid(schema_id)
    bad = copy.deepcopy(event)
    bad["payload"]["body"] = {"forecast": "smuggled"}
    with pytest.raises(contracts.ContractError):
        contracts.validate(bad)
    # And the stdlib diagnostic refuses it too — the invalid golden IS this defect.
    with pytest.raises(contracts.ContractError):
        contracts.diagnostic_validate(schema_id, json.loads(
            (GOLDEN / schema_id / "invalid.json").read_text(encoding="utf-8")))


def test_no_e04_stub_exists():
    # OWNER-TOPO-01 Amendment A2: E04 stays excluded from the seam; no E04 contract is registered.
    for cid in contracts.known_contracts():
        assert "e04" not in cid, cid


# --- validator absence: named refusal, never silent ----------------------------------------------
@pytest.mark.parametrize("schema_id", ["triad.evidence_view.v2", "triad.transport_bindings.v1",
                                        "triad.forecast_request.v2"])
def test_validator_absence_yields_schema_validator_unavailable(schema_id, monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "jsonschema":
            raise ModuleNotFoundError("jsonschema disabled for test")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(contracts.SchemaValidatorUnavailable, match="SCHEMA_VALIDATOR_UNAVAILABLE"):
        contracts.validate(_valid(schema_id))
