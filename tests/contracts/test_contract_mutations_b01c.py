"""B01C-CON-03/06 — the recursive schema-mutation corpus is green and deterministic.

Proves the authoritative validator refuses every closure-required mutation across all registered
contracts (CON-03 enforcement), that the run is deterministic (content-addressed), that the
validator-absent lane fails closed, and that the CON-01/02 open-boundary surface is a documented
non-empty inventory (never silently closed).
"""

from __future__ import annotations

import builtins
import importlib
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import run_contract_mutations as rcm  # noqa: E402
from triad_origin import contracts  # noqa: E402


@pytest.fixture(scope="module")
def report():
    return rcm.run_profile("B01C")


def test_every_closure_required_mutation_is_refused(report):
    assert report["totals"]["closure_required_wrongly_passed"] == 0, report["wrongly_passed"]
    assert report["wrongly_passed"] == []
    # the corpus is substantial — it really exercised the validator, not a trivial empty run
    assert report["totals"]["closure_required_refused"] > 1000
    assert report["contract_count"] == len(contracts.known_contracts())


def test_run_is_deterministic_and_content_addressed(report):
    again = rcm.run_profile("B01C")
    assert again["corpus_digest"] == report["corpus_digest"]
    assert len(report["corpus_digest"]) == 64


def test_open_boundary_inventory_is_documented_not_empty(report):
    inv = report["open_boundary_inventory"]
    assert report["totals"]["open_boundaries"] == len(inv) > 0
    for entry in inv:
        assert set(entry) == {"schema_id", "pointer"}
        assert entry["schema_id"] in contracts.known_contracts()


def test_require_all_refused_cli_exits_zero():
    assert rcm.main(["--profile", "B01C", "--require-all-refused"]) == 0


def test_unknown_profile_refused():
    with pytest.raises(SystemExit):
        rcm.run_profile("NOPE")


def test_validator_absent_lane_fails_closed(monkeypatch):
    # Force the full validator absent: run_profile must surface SchemaValidatorUnavailable and the
    # CLI must exit 3 — never a silent pass.
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "jsonschema":
            raise ModuleNotFoundError("jsonschema disabled for test")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert rcm.main(["--profile", "B01C", "--require-all-refused"]) == 3
