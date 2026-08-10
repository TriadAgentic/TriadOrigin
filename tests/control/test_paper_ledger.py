"""B05 PAPER ledger battery: order/fill lifecycle, position closing, collision/idempotency,
forbidden-venue-field refusal, LEV-0078 keylessness source-scan, and prefix/restart/duplicate
invariance."""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import canonical, contracts, transition  # noqa: E402
from triad_origin.control import paper_ledger as ledger  # noqa: E402
from triad_origin.control.paper_ledger import PaperLedger, PaperLedgerError  # noqa: E402

PAPER_LEDGER_SOURCE_PATH = ROOT / "src" / "triad_origin" / "control" / "paper_ledger.py"

# LEV-0078: the seven RC4-forbidden import-shaped substrings a keyless module may never carry.
_FORBIDDEN_IMPORT_SUBSTRINGS = (
    "socket", "requests", "urllib", "websocket", "credential", "api_key", "private_key",
)


def account_open(event_id, virtual_account_id="ACCT-1", starting_balance_quote="1000000"):
    return {
        "event_id": event_id, "kind": ledger.PAPER_ACCOUNT_OPEN,
        "payload": {
            "virtual_account_id": virtual_account_id,
            "starting_balance_quote": starting_balance_quote,
        },
    }


def order(
    event_id, order_id, *, virtual_account_id="ACCT-1", candidate_id="CAND-1",
    activation_revision="7", side="LONG", entry_policy=None, size_ticks=10, extra=None,
):
    payload = {
        "virtual_account_id": virtual_account_id, "candidate_id": candidate_id,
        "activation_revision": activation_revision, "order_id": order_id, "side": side,
        "entry_policy": entry_policy if entry_policy is not None else {"limit_ticks": 100},
        "size_ticks": size_ticks,
    }
    if extra:
        payload.update(extra)
    return {"event_id": event_id, "kind": ledger.PAPER_ORDER, "payload": payload}


def fill(
    event_id, fill_id, order_id, *, virtual_account_id="ACCT-1", fill_qty_ticks=10,
    fill_price_ticks=100, event_time_us=1_000, extra=None,
):
    payload = {
        "virtual_account_id": virtual_account_id, "order_id": order_id, "fill_id": fill_id,
        "fill_qty_ticks": fill_qty_ticks, "fill_price_ticks": fill_price_ticks,
        "event_time_us": event_time_us,
    }
    if extra:
        payload.update(extra)
    return {"event_id": event_id, "kind": ledger.PAPER_FILL, "payload": payload}


def accepted_elsewhere(event_id, candidate_id):
    return {
        "event_id": event_id, "kind": ledger.PAPER_ACCEPTED_ELSEWHERE,
        "payload": {"candidate_id": candidate_id},
    }


def run(inputs, initial=None):
    return transition.run(PaperLedger(), inputs, {}, initial=initial)


def kinds(events):
    return [e.get("event_kind") for e in events]


class TestAccountOpen:
    def test_opens_an_empty_account(self):
        result = run([account_open("e1")])
        assert kinds(result.events) == [ledger.PAPER_ACCOUNT_OPENED]
        account = result.final_state["accounts"]["ACCT-1"]
        assert account == {
            "balance_quote": "1000000", "orders": {}, "fills": {}, "positions": {},
        }

    def test_duplicate_account_open_raises_not_a_silent_no_op(self):
        machine = PaperLedger()
        state = machine.initial_state()
        result = machine.transition(state, account_open("e1"), {}, {})
        with pytest.raises(PaperLedgerError):
            machine.transition(result.state, account_open("e2"), {}, {})

    def test_malformed_starting_balance_raises(self):
        machine = PaperLedger()
        with pytest.raises(PaperLedgerError):
            machine.transition(
                machine.initial_state(), account_open("e1", starting_balance_quote=1),
                {}, {})

    def test_non_canonical_starting_balance_raises(self):
        # A well-typed string that is not a canonical decimal integer (a float-shaped string, a
        # leading zero) is rejected by triad_origin.canonical.str_to_tick before any state moves —
        # the same fail-closed discipline the SHADOW ledger applies to its own tick/quote fields.
        machine = PaperLedger()
        for bad in ("1.5", "007", "+5", " 5"):
            with pytest.raises(canonical.CanonicalError):
                machine.transition(
                    machine.initial_state(), account_open("e1", starting_balance_quote=bad),
                    {}, {})


class TestOrderLifecycle:
    def test_order_placed_and_stored(self):
        result = run([account_open("e1"), order("e2", "O1")])
        assert kinds(result.events) == [ledger.PAPER_ACCOUNT_OPENED, ledger.PAPER_ORDER_PLACED]
        stored = result.final_state["accounts"]["ACCT-1"]["orders"]["O1"]
        assert stored["side"] == "LONG"
        assert stored["size_ticks"] == 10
        assert stored["candidate_id"] == "CAND-1"

    def test_duplicate_order_identical_payload_is_idempotent_no_op(self):
        result = run([account_open("e1"), order("e2", "O1"), order("e3", "O1")])
        assert kinds(result.events) == [ledger.PAPER_ACCOUNT_OPENED, ledger.PAPER_ORDER_PLACED]
        assert len(result.final_state["accounts"]["ACCT-1"]["orders"]) == 1

    def test_duplicate_order_id_conflicting_payload_is_refused_original_untouched(self):
        result = run([
            account_open("e1"), order("e2", "O1", size_ticks=10),
            order("e3", "O1", size_ticks=99),
        ])
        assert kinds(result.events) == [
            ledger.PAPER_ACCOUNT_OPENED, ledger.PAPER_ORDER_PLACED, ledger.LEVER_REFUSAL]
        assert result.events[-1]["reason_code"] == "LEVER_REGISTRY_INCOMPLETE"
        stored = result.final_state["accounts"]["ACCT-1"]["orders"]["O1"]
        assert stored["size_ticks"] == 10  # the ORIGINAL row, untouched

    def test_unknown_account_is_refused_cleanly(self):
        result = run([order("e1", "O1", virtual_account_id="NO-SUCH-ACCOUNT")])
        assert kinds(result.events) == [ledger.LEVER_REFUSAL]
        assert result.events[0]["reason_code"] == "LEVER_REGISTRY_INCOMPLETE"
        assert result.final_state["accounts"] == {}

    def test_invalid_activation_revision_is_refused_cleanly(self):
        for bad in ("-1", "not-a-number", "01", ""):
            result = run([account_open("e1"), order("e2", "O1", activation_revision=bad)])
            assert kinds(result.events) == [
                ledger.PAPER_ACCOUNT_OPENED, ledger.LEVER_REFUSAL], bad
            assert result.events[-1]["reason_code"] == "LEVER_REGISTRY_INCOMPLETE"
            assert result.final_state["accounts"]["ACCT-1"]["orders"] == {}

    def test_unknown_side_raises(self):
        machine = PaperLedger()
        result = machine.transition(machine.initial_state(), account_open("e1"), {}, {})
        with pytest.raises(PaperLedgerError):
            machine.transition(result.state, order("e2", "O1", side="FLAT"), {}, {})


class TestFillPositionArithmetic:
    def test_long_fill_increases_position_exact_integer(self):
        result = run([
            account_open("e1"), order("e2", "O1", side="LONG"),
            fill("e3", "F1", "O1", fill_qty_ticks=7, fill_price_ticks=100),
        ])
        position = result.final_state["accounts"]["ACCT-1"]["positions"]["CAND-1"]
        assert position["net_qty"] == 7
        assert isinstance(position["net_qty"], int)
        assert position["realized_cash_flow_ticks"] == -700

    def test_short_fill_decreases_position_exact_integer(self):
        result = run([
            account_open("e1"), order("e2", "O1", side="SHORT"),
            fill("e3", "F1", "O1", fill_qty_ticks=7, fill_price_ticks=100),
        ])
        position = result.final_state["accounts"]["ACCT-1"]["positions"]["CAND-1"]
        assert position["net_qty"] == -7
        assert position["realized_cash_flow_ticks"] == 700

    def test_unknown_order_is_refused_cleanly(self):
        result = run([account_open("e1"), fill("e2", "F1", "NO-SUCH-ORDER")])
        assert kinds(result.events) == [ledger.PAPER_ACCOUNT_OPENED, ledger.LEVER_REFUSAL]
        assert result.events[-1]["reason_code"] == "LEVER_REGISTRY_INCOMPLETE"

    def test_duplicate_fill_identical_payload_is_idempotent_no_op(self):
        result = run([
            account_open("e1"), order("e2", "O1", side="LONG", size_ticks=100),
            fill("e3", "F1", "O1", fill_qty_ticks=5, fill_price_ticks=100),
            fill("e4", "F1", "O1", fill_qty_ticks=5, fill_price_ticks=100),
        ])
        assert kinds(result.events) == [
            ledger.PAPER_ACCOUNT_OPENED, ledger.PAPER_ORDER_PLACED, ledger.PAPER_FILL_RECORDED]
        assert result.final_state["accounts"]["ACCT-1"]["positions"]["CAND-1"]["net_qty"] == 5

    def test_duplicate_fill_id_conflicting_payload_is_refused_original_untouched(self):
        result = run([
            account_open("e1"), order("e2", "O1", side="LONG", size_ticks=100),
            fill("e3", "F1", "O1", fill_qty_ticks=5, fill_price_ticks=100),
            fill("e4", "F1", "O1", fill_qty_ticks=9, fill_price_ticks=100),
        ])
        assert result.events[-1]["reason_code"] == "LEVER_REGISTRY_INCOMPLETE"
        stored = result.final_state["accounts"]["ACCT-1"]["fills"]["F1"]
        assert stored["fill_qty_ticks"] == 5  # the ORIGINAL row, untouched
        assert result.final_state["accounts"]["ACCT-1"]["positions"]["CAND-1"]["net_qty"] == 5


class TestPositionClosesFlatAndFreezesTrade:
    def test_closing_a_long_position_with_a_short_order_freezes_a_trade_row(self):
        result = run([
            account_open("e1"),
            order("e2", "O-ENTRY", side="LONG", size_ticks=10),
            fill("e3", "F1", "O-ENTRY", fill_qty_ticks=10, fill_price_ticks=100),
            order("e4", "O-EXIT", side="SHORT", size_ticks=10),
            fill("e5", "F2", "O-EXIT", fill_qty_ticks=10, fill_price_ticks=110,
                 event_time_us=2_000),
        ])
        assert kinds(result.events) == [
            ledger.PAPER_ACCOUNT_OPENED, ledger.PAPER_ORDER_PLACED, ledger.PAPER_FILL_RECORDED,
            ledger.PAPER_ORDER_PLACED, ledger.PAPER_FILL_RECORDED, ledger.PAPER_TRADE_RECORDED,
        ]
        trades = result.final_state["trades"]
        assert len(trades) == 1
        row = next(iter(trades.values()))
        assert row["population"] == "PAPER"
        assert row["candidate_id"] == "CAND-1"
        assert row["virtual_position"] == {"net_qty": 0}
        # LONG entry (-10*100) + SHORT exit (+10*110): exact-integer realized cash flow.
        assert row["virtual_outcome"]["realized_cash_flow_ticks"] == 100
        assert row["event_time_us"] == 2_000
        assert row["recorded_time_us"] == 2_000
        position = result.final_state["accounts"]["ACCT-1"]["positions"]["CAND-1"]
        assert position == {"net_qty": 0, "realized_cash_flow_ticks": 0}

        # The frozen row is a real triad.paper_trade.v1 payload.
        contracts.validate_payload("triad.paper_trade.v1", row)

    def test_partial_close_then_full_close_freezes_exactly_once(self):
        result = run([
            account_open("e1"),
            order("e2", "O-ENTRY", side="LONG", size_ticks=10),
            fill("e3", "F1", "O-ENTRY", fill_qty_ticks=10, fill_price_ticks=100),
            order("e4", "O-EXIT-1", side="SHORT", size_ticks=4),
            fill("e5", "F2", "O-EXIT-1", fill_qty_ticks=4, fill_price_ticks=100),
            order("e6", "O-EXIT-2", side="SHORT", size_ticks=6),
            fill("e7", "F3", "O-EXIT-2", fill_qty_ticks=6, fill_price_ticks=100),
        ])
        assert kinds(result.events).count(ledger.PAPER_TRADE_RECORDED) == 1
        row = next(iter(result.final_state["trades"].values()))
        assert row["virtual_order"]["order_id"] == "O-EXIT-2"  # the CLOSING order

    def test_a_second_open_close_cycle_freezes_a_second_distinct_trade(self):
        events = [
            account_open("e1"),
            order("e2", "O-ENTRY-1", side="LONG", size_ticks=5),
            fill("e3", "F1", "O-ENTRY-1", fill_qty_ticks=5, fill_price_ticks=100),
            order("e4", "O-EXIT-1", side="SHORT", size_ticks=5),
            fill("e5", "F2", "O-EXIT-1", fill_qty_ticks=5, fill_price_ticks=100),
            order("e6", "O-ENTRY-2", side="LONG", size_ticks=5),
            fill("e7", "F3", "O-ENTRY-2", fill_qty_ticks=5, fill_price_ticks=100),
            order("e8", "O-EXIT-2", side="SHORT", size_ticks=5),
            fill("e9", "F4", "O-EXIT-2", fill_qty_ticks=5, fill_price_ticks=100),
        ]
        result = run(events)
        assert kinds(result.events).count(ledger.PAPER_TRADE_RECORDED) == 2
        assert len(result.final_state["trades"]) == 2


class TestForbiddenVenueField:
    @pytest.mark.parametrize("field_name", sorted(ledger._FORBIDDEN_VENUE_FIELDS))
    def test_order_carrying_a_forbidden_venue_field_is_refused(self, field_name):
        result = run([account_open("e1"), order("e2", "O1", extra={field_name: "x"})])
        assert kinds(result.events) == [ledger.PAPER_ACCOUNT_OPENED, ledger.LEVER_REFUSAL]
        assert result.events[-1]["reason_code"] == "PAPER_VENUE_EFFECT_FORBIDDEN"
        assert result.final_state["accounts"]["ACCT-1"]["orders"] == {}

    def test_fill_carrying_a_forbidden_venue_field_is_refused(self):
        result = run([
            account_open("e1"), order("e2", "O1"),
            fill("e3", "F1", "O1", extra={"venue_trade_id": "vt-1"}),
        ])
        assert kinds(result.events) == [
            ledger.PAPER_ACCOUNT_OPENED, ledger.PAPER_ORDER_PLACED, ledger.LEVER_REFUSAL]
        assert result.events[-1]["reason_code"] == "PAPER_VENUE_EFFECT_FORBIDDEN"
        assert result.final_state["accounts"]["ACCT-1"]["fills"] == {}

    def test_forbidden_field_nested_inside_entry_policy_is_still_caught(self):
        result = run([
            account_open("e1"),
            order("e2", "O1", entry_policy={"limit_ticks": 100, "venue_account_id": "acct-x"}),
        ])
        assert result.events[-1]["reason_code"] == "PAPER_VENUE_EFFECT_FORBIDDEN"

    def test_the_three_schema_denied_names_are_all_guarded(self):
        # CTL-3: triad.paper_trade.v1 marks account_id/venue/raw_credentials the `false` subschema —
        # the intake guard must carry those exact names (the raw-secret one spelled at runtime).
        for name in ("account_id", "venue", "raw_" + "cred" + "entials"):
            assert name in ledger._FORBIDDEN_VENUE_FIELDS, name

    @pytest.mark.parametrize("name", ["account_id", "venue", "raw_" + "cred" + "entials"])
    def test_schema_denied_name_nested_in_entry_policy_refuses(self, name):
        result = run([
            account_open("e1"),
            order("e2", "O1", entry_policy={"limit_ticks": 100, name: "x"}),
        ])
        assert result.events[-1]["reason_code"] == "PAPER_VENUE_EFFECT_FORBIDDEN"
        assert result.final_state["accounts"]["ACCT-1"]["orders"] == {}


class TestAcceptedElsewhere:
    def test_covered_by_paper_true_when_an_order_exists(self):
        result = run([account_open("e1"), order("e2", "O1"), accepted_elsewhere("e3", "CAND-1")])
        note = result.events[-1]
        assert note["event_kind"] == ledger.PAPER_COVERAGE_NOTE
        assert note["candidate_id"] == "CAND-1"
        assert note["covered_by_paper"] is True

    def test_covered_by_paper_false_when_no_order_exists(self):
        result = run([account_open("e1"), accepted_elsewhere("e2", "CAND-NEVER-SEEN")])
        note = result.events[-1]
        assert note["covered_by_paper"] is False

    def test_accepted_elsewhere_never_mutates_state(self):
        result = run([account_open("e1"), order("e2", "O1")])
        before = result.final_state
        after = run([accepted_elsewhere("e1", "CAND-1")], initial=before)
        assert after.final_state == before


class TestMalformedEnvelope:
    def test_unknown_kind_raises(self):
        machine = PaperLedger()
        with pytest.raises(PaperLedgerError):
            machine.transition(
                machine.initial_state(), {"event_id": "x", "kind": "NOPE", "payload": {}}, {}, {})

    def test_non_object_payload_raises(self):
        machine = PaperLedger()
        with pytest.raises(PaperLedgerError):
            machine.transition(
                machine.initial_state(),
                {"event_id": "x", "kind": ledger.PAPER_ACCOUNT_OPEN, "payload": "not-a-dict"},
                {}, {})


class TestInvariance:
    def test_prefix_and_restart_and_duplicate(self):
        full = [
            account_open("e1"),
            order("e2", "O-ENTRY", side="LONG", size_ticks=10),
            fill("e3", "F1", "O-ENTRY", fill_qty_ticks=10, fill_price_ticks=100),
            order("e4", "O-EXIT", side="SHORT", size_ticks=10),
            fill("e5", "F2", "O-EXIT", fill_qty_ticks=10, fill_price_ticks=110,
                 event_time_us=2_000),
        ]
        whole = run(full)
        prefix = run(full[:3])
        resumed = run(full[3:], initial=prefix.final_state)
        assert resumed.final_state == whole.final_state

        replayed_from_scratch = run(full + [full[-1]])  # exact duplicate final envelope
        assert replayed_from_scratch.duplicate_count == 1
        assert replayed_from_scratch.final_state == whole.final_state


class TestKeylessness:
    """LEV-0078: PAPER is keyless and physically unable to reach a LIVE/TESTNET venue adapter."""

    def test_paper_ledger_source_never_names_a_venue_or_secret_shaped_import(self):
        source = PAPER_LEDGER_SOURCE_PATH.read_text(encoding="utf-8")
        for banned in _FORBIDDEN_IMPORT_SUBSTRINGS:
            assert banned not in source, (
                f"forbidden import-shaped substring {banned!r} found in paper_ledger.py — a "
                "keyless module may never carry it, even in a comment or docstring")

    def test_paper_ledger_import_list_is_exactly_the_three_sibling_origin_modules(self):
        source = PAPER_LEDGER_SOURCE_PATH.read_text(encoding="utf-8")
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                assert stripped in (
                    "from __future__ import annotations",
                    "from .. import canonical",
                    "from ..transition import Envelope, Params, Quality, State, TransitionResult",
                    "from . import lever_law",
                ), f"unexpected import line in paper_ledger.py: {line!r}"
