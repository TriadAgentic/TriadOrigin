"""LEV-0084: "Keep all four populations in separate contracts/tables and never merge performance
denominators." This proves the PAPER/SHADOW split at two independent levels:

* the PAPER machine's OWN state never nests a row of any other population (a runtime proof, driven
  through a full PAPER_FILL flow that closes a position and freezes a trade), and
* the two contracts themselves are structurally incompatible at the schema boundary — a PAPER
  payload can never validate against ``triad.shadow_trade.v1`` and a SHADOW payload can never
  validate against ``triad.paper_trade.v1`` (the closed ``population`` enum on each schema is the
  wall; the PAPER row is hand-built the same way :mod:`triad_origin.control.shadow_ledger` would
  build a SHADOW row, without importing that sibling module, matching this module's own
  import-isolation).
"""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import contracts, transition  # noqa: E402
from triad_origin.control import paper_ledger as ledger  # noqa: E402
from triad_origin.control.paper_ledger import PaperLedger  # noqa: E402


def _run_full_paper_cycle():
    """A complete PAPER_ACCOUNT_OPEN -> PAPER_ORDER -> PAPER_FILL x2 close cycle."""
    inputs = [
        {"event_id": "e1", "kind": ledger.PAPER_ACCOUNT_OPEN,
         "payload": {"virtual_account_id": "ACCT-1", "starting_balance_quote": "1000000"}},
        {"event_id": "e2", "kind": ledger.PAPER_ORDER,
         "payload": {
             "virtual_account_id": "ACCT-1", "candidate_id": "CAND-1", "activation_revision": "3",
             "order_id": "O-ENTRY", "side": "LONG", "entry_policy": {"limit_ticks": 100},
             "size_ticks": 10,
         }},
        {"event_id": "e3", "kind": ledger.PAPER_FILL,
         "payload": {
             "virtual_account_id": "ACCT-1", "order_id": "O-ENTRY", "fill_id": "F1",
             "fill_qty_ticks": 10, "fill_price_ticks": 100, "event_time_us": 1_000,
         }},
        {"event_id": "e4", "kind": ledger.PAPER_ORDER,
         "payload": {
             "virtual_account_id": "ACCT-1", "candidate_id": "CAND-1", "activation_revision": "3",
             "order_id": "O-EXIT", "side": "SHORT", "entry_policy": {"limit_ticks": 110},
             "size_ticks": 10,
         }},
        {"event_id": "e5", "kind": ledger.PAPER_FILL,
         "payload": {
             "virtual_account_id": "ACCT-1", "order_id": "O-EXIT", "fill_id": "F2",
             "fill_qty_ticks": 10, "fill_price_ticks": 110, "event_time_us": 2_000,
         }},
    ]
    return transition.run(PaperLedger(), inputs, {})


def _paper_trade_fixture() -> dict:
    """A hand-built triad.paper_trade.v1-shaped payload (the machine's own shape, by hand)."""
    return {
        "paper_trade_id": "paper-trade-fixture-1",
        "candidate_id": "CAND-1",
        "population": "PAPER",
        "activation_revision": "3",
        "virtual_account_id": "ACCT-1",
        "virtual_balance_quote": "1000000",
        "virtual_order": {"order_id": "O-EXIT", "side": "SHORT", "size_ticks": 10},
        "virtual_fill": {"fill_id": "F2", "fill_qty_ticks": 10, "fill_price_ticks": 110},
        "virtual_position": {"net_qty": 0},
        "virtual_outcome": {"closed": True, "realized_cash_flow_ticks": 100},
        "market_watermark": {"watermark_us": 2_000},
        "event_time_us": 2_000,
        "recorded_time_us": 2_000,
    }


def _shadow_trade_fixture() -> dict:
    """A hand-built triad.shadow_trade.v1-shaped payload — no import of shadow_ledger (it is
    another module's file; matching this module's own import-isolation, this fixture is built
    directly against the vendored schema's required fields instead)."""
    return {
        "shadow_trade_id": "shadow-trade-fixture-1",
        "candidate_id": "CAND-1",
        "hypothesis_id": "HYP-1",
        "frozen_at_us": 2_000,
        "origin_disposition": "REJECTED",
        "rejection_stage": "E08_RISK",
        "rejection_reason": "oversized",
        "population": "SHADOW",
        "shadow_activation": "LIVE",
        "market_watermark": {"watermark_us": 2_000},
        "proposed_geometry": {"side": "LONG", "entry_ticks": 100},
        "evaluation_notional_quote": "1000000",
        "simulator_version": "sim-1",
        "resolver_version": "res-1",
        "cost_model_version": "cost-1",
        "event_time_us": 2_000,
        "recorded_time_us": 2_000,
        "fill_model_result": {"status": "PENDING"},
        "terminal_outcome": {"status": "PENDING"},
    }


class TestPaperStateNeverNestsAnotherPopulation:
    def test_every_frozen_trade_row_is_population_paper(self):
        result = _run_full_paper_cycle()
        trades = result.final_state["trades"]
        assert len(trades) == 1  # the position actually closed and froze exactly one row
        for row in trades.values():
            assert row["population"] == "PAPER"
            assert row["population"] != "SHADOW"

    def test_no_account_or_order_row_carries_a_non_paper_population_field(self):
        result = _run_full_paper_cycle()
        for account in result.final_state["accounts"].values():
            for order in account["orders"].values():
                assert "population" not in order or order["population"] == "PAPER"
            for stored_fill in account["fills"].values():
                assert "population" not in stored_fill or stored_fill["population"] == "PAPER"


class TestSchemaBoundaryEnforcesClosedPopulationEnums:
    def test_the_paper_fixture_validates_against_its_own_schema(self):
        contracts.validate_payload("triad.paper_trade.v1", _paper_trade_fixture())

    def test_the_shadow_fixture_validates_against_its_own_schema(self):
        contracts.validate_payload("triad.shadow_trade.v1", _shadow_trade_fixture())

    def test_the_paper_fixture_never_validates_as_a_shadow_trade(self):
        with pytest.raises(contracts.ContractError):
            contracts.validate_payload("triad.shadow_trade.v1", _paper_trade_fixture())

    def test_the_shadow_fixture_never_validates_as_a_paper_trade(self):
        with pytest.raises(contracts.ContractError):
            contracts.validate_payload("triad.paper_trade.v1", _shadow_trade_fixture())

    def test_a_paper_row_with_the_shadow_population_string_still_fails_both_ways(self):
        # Even a caller trying to rename its way across the wall is caught: swapping only the
        # population field does not manufacture a valid row on either side, because every other
        # required field still belongs to the wrong contract.
        mismatched = dict(_paper_trade_fixture())
        mismatched["population"] = "SHADOW"
        with pytest.raises(contracts.ContractError):
            contracts.validate_payload("triad.paper_trade.v1", mismatched)
        with pytest.raises(contracts.ContractError):
            contracts.validate_payload("triad.shadow_trade.v1", mismatched)

    def test_the_two_fixtures_disagree_on_population(self):
        assert _paper_trade_fixture()["population"] != _shadow_trade_fixture()["population"]
