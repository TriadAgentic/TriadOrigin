"""Envelope + authority invariants: fencing, forbidden candidate fields, closed enums, schema id."""

from __future__ import annotations

import copy
import json
import pathlib

import pytest

from triad_origin import contracts

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
GOLDEN = ROOT / "contracts" / "golden"


def _valid(schema_id: str) -> dict:
    return json.loads((GOLDEN / schema_id / "valid.json").read_text(encoding="utf-8"))


def test_schema_mismatch_rejects():
    ev = _valid("triad.fill.v3")
    with pytest.raises(contracts.ContractError):
        contracts.validate(ev, schema_id="triad.decision.v2")


def test_closed_enum_rejects_unknown_value():
    ev = _valid("triad.risk_decision.v2")
    ev["payload"]["disposition"] = "MAYBE"
    with pytest.raises(contracts.ContractError):
        contracts.validate(ev)


def test_environment_enum_is_closed_at_live_and_testnet():
    # RC4 four-plane law (B01): fill.v3 3.1.0 admits exactly LIVE and TESTNET — the two venue
    # environments are certified separately and never mixed in one bundle. Every other token
    # (paper/demo/dry-run aliases) rejects.
    ev = _valid("triad.fill.v3")
    ev["payload"]["environment"] = "TESTNET"
    contracts.validate(ev)
    for alias in ("PAPER", "DEMO", "DRYRUN", "testnet", "live", ""):
        ev["payload"]["environment"] = alias
        with pytest.raises(contracts.ContractError):
            contracts.validate(ev)


def test_epoch_fencing_accepts_current_and_rejects_lower():
    ev = _valid("triad.edge_candidate.v2")
    ev["producer_epoch"] = "42"
    assert contracts.assert_epoch_ge(ev, 41) == 42
    assert contracts.assert_epoch_ge(ev, 42) == 42  # current producer emits many events
    ev["producer_epoch"] = "41"
    with pytest.raises(contracts.StaleEpochError):
        contracts.assert_epoch_ge(ev, 42)


def test_authority_event_without_epoch_is_rejected():
    ev = _valid("triad.decision.v2")
    ev.pop("producer_epoch", None)
    with pytest.raises(contracts.StaleEpochError):
        contracts.assert_epoch_ge(ev, 0)


@pytest.mark.parametrize("bad", [True, 1, 1.0, "01", "+1", " 1", "-1"])
def test_epoch_helper_rejects_noncanonical_or_negative_values(bad):
    event = _valid("triad.edge_candidate.v2")
    event["producer_epoch"] = bad
    with pytest.raises(contracts.StaleEpochError):
        contracts.assert_epoch_ge(event, -1)


def test_forbidden_candidate_field_is_a_breach():
    ev = _valid("triad.edge_candidate.v2")
    bad = copy.deepcopy(ev)
    bad["payload"]["account_id"] = "acct_canary_01"
    # schema forbids the key ...
    with pytest.raises(contracts.ContractError):
        contracts.validate(bad)
    # ... and the explicit constitutional guard also catches it.
    with pytest.raises(contracts.ContractError):
        contracts.assert_no_forbidden_candidate_fields(bad)


def test_clean_candidate_passes_forbidden_guard():
    contracts.assert_no_forbidden_candidate_fields(_valid("triad.edge_candidate.v2"))


def test_forbidden_candidate_field_is_rejected_recursively_and_at_validation_boundary():
    bad = _valid("triad.edge_candidate.v2")
    bad["payload"]["quality"]["raw_credentials"] = "secret"
    with pytest.raises(contracts.ContractError, match="raw_credentials"):
        contracts.assert_no_forbidden_candidate_fields(bad)
    with pytest.raises(contracts.ContractError, match="raw_credentials"):
        contracts.validate(bad)
    tuple_nested = _valid("triad.edge_candidate.v2")
    tuple_nested["payload"]["quality"]["nested"] = ({"raw_credentials": "secret"},)
    with pytest.raises(contracts.ContractError, match="raw_credentials"):
        contracts.validate(tuple_nested)
