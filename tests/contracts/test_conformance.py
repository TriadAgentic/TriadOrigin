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


def test_registry_lists_thirty_contracts():
    assert len(CONTRACT_IDS) == 30


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
