"""Golden conformance: every contract's valid vector validates and invalid vector rejects.

Runs under jsonschema (the strict path) and additionally exercises the stdlib fallback validator so
the money path never hard-depends on a third-party library (Doc 03 §03.12).
"""

from __future__ import annotations

import json
import pathlib

import pytest

from triad_origin import contracts

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
GOLDEN = ROOT / "contracts" / "golden"

CONTRACT_IDS = contracts.known_contracts()


def _load(schema_id: str, kind: str) -> dict:
    return json.loads((GOLDEN / schema_id / f"{kind}.json").read_text(encoding="utf-8"))


def test_registry_lists_all_contracts():
    # 30 RC1 contracts + 12 B01 additions (RC4 lever/plane + receipt v2 + attestation v2 + auth v3)
    assert len(CONTRACT_IDS) == 42


@pytest.mark.parametrize("schema_id", CONTRACT_IDS)
def test_valid_golden_validates(schema_id):
    event = _load(schema_id, "valid")
    contracts.validate(event)  # jsonschema when present


@pytest.mark.parametrize("schema_id", CONTRACT_IDS)
def test_invalid_golden_rejects(schema_id):
    event = _load(schema_id, "invalid")
    with pytest.raises(contracts.ContractError):
        contracts.validate(event)


@pytest.mark.parametrize("schema_id", CONTRACT_IDS)
def test_fallback_validator_agrees(schema_id, monkeypatch):
    # Force the ModuleNotFoundError path so the stdlib fallback is exercised.
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "jsonschema":
            raise ModuleNotFoundError("jsonschema disabled for test")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    contracts.validate(_load(schema_id, "valid"))
    with pytest.raises(contracts.ContractError):
        contracts.validate(_load(schema_id, "invalid"))


def test_unknown_schema_fails_closed():
    with pytest.raises(contracts.ContractError):
        contracts.validate({"schema": "triad.does_not_exist.v9", "payload": {}})


@pytest.mark.parametrize("bad_schema", [[], {}, 1, None])
def test_unhashable_or_nonstring_schema_id_fails_closed(bad_schema):
    with pytest.raises(contracts.ContractError):
        contracts.load_schema(bad_schema)
    with pytest.raises(contracts.ContractError):
        contracts.validate({"schema": bad_schema})


def test_public_contract_views_cannot_mutate_cached_validation_truth():
    schema_id = "triad.edge_candidate.v2"
    invalid = _load(schema_id, "invalid")
    schema = contracts.load_schema(schema_id)
    schema.clear()
    registry = contracts.registry()
    registry["contracts"].clear()
    assert len(contracts.known_contracts()) == 42
    with pytest.raises(contracts.ContractError):
        contracts.validate(invalid, schema_id=schema_id)
    assert contracts.load_schema(schema_id)


@pytest.mark.parametrize("bad", [1.5, object()])
def test_public_validation_rejects_noncanonical_nested_values(bad):
    event = _load("triad.edge_candidate.v2", "valid")
    # quality is an open RC1 object, so this exercises canonical-wire enforcement beyond schema.
    event["payload"]["quality"]["unsafe"] = bad
    with pytest.raises(contracts.ContractError, match="canonical-wire"):
        contracts.validate(event)
    with pytest.raises(contracts.ContractError, match="canonical-wire"):
        contracts.validate_payload("triad.edge_candidate.v2", event["payload"])


@pytest.mark.parametrize(
    ("schema_id", "mutate"),
    [
        (
            "triad.edge_candidate.v2",
            lambda event: event["payload"].__setitem__("entry_reference_ticks", "01"),
        ),
        (
            "triad.edge_candidate.v2",
            lambda event: event.__setitem__("producer_service", ""),
        ),
    ],
)
def test_fallback_enforces_declared_pattern_and_min_length(schema_id, mutate):
    event = _load(schema_id, "valid")
    mutate(event)
    with pytest.raises(contracts.ContractError):
        contracts._validate_fallback(contracts.load_schema(schema_id), event)
