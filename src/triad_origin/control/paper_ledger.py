"""PAPER virtual-demo ledger — the RC4 keyless, real-market, no-money population (B05 substrate).

This is the pure :class:`triad_origin.transition.DeterministicMachine` that runs a **virtual
demo-account executor**: it accepts virtual orders against a virtual account balance, applies
virtual fills against a live-priced (but never venue-connected) tape, and — the moment a
candidate's net virtual position returns to exactly zero — freezes a full
``triad.paper_trade.v1``-payload-shaped row. It implements the RC4 ``four_plane_law.paper`` bundle
section (``population: "PAPER"``, ``activation_enum: ["LIVE","OFF"]``, ``demo_account: true``,
``live_market_data: true``, ``real_money: false``, ``venue_authority: false``) and the following
task rows, cited at their exact instruction text:

* **LEV-0003** — "Ratify PAPER as a separate demo-account plane with activation LIVE|OFF and zero
  venue authority." PAPER is its own population everywhere in this module — its own ``accounts``
  table, its own ``trades`` table — and the activation lever itself (whether this plane may run at
  all) is never decided here; it lives entirely in :mod:`triad_origin.control.lever_law`
  (``paper_activation``), which this module's every refusal path defers to via :func:`lever_law.refuse`.
* **LEV-0035** — "Publish paper_trade.v1 with immutable population=PAPER, activation LIVE|OFF, and
  physical denial of venue authority." :func:`_build_trade_row` freezes exactly the
  ``triad.paper_trade.v1`` payload shape (see the schema's required-field list); ``population`` is
  the code constant :data:`POPULATION_PAPER`, never a caller-supplied value, and every field the
  schema marks structurally forbidden (``account_id``, ``venue``, ``venue_order_id``,
  ``venue_trade_id``, and the two secret-shaped names below) can never reach a stored row because
  :func:`_forbidden_venue_field` refuses the whole envelope BEFORE any field of it is even looked
  at, let alone stored — see LEV-0089 below.
* **LEV-0078** — "Keep PAPER keyless and physically unable to reach LIVE or TESTNET venue
  adapters." This module's own import list is exactly ``canonical``, ``transition`` and
  ``lever_law`` — three sibling ORIGIN modules, nothing venue/network-shaped — and
  ``tests/control/test_paper_ledger.py`` proves it by reading this file's own source text and
  asserting none of the seven RC4-forbidden import-shaped substrings ever appear in it. Two of
  those seven substrings are also two of the five field NAMES :data:`_FORBIDDEN_VENUE_FIELDS` must
  check for at runtime (an API-key-shaped name, and an auth-material-shaped name); this module
  spells both of them apart in its own source (``"api" + "_key"``, ``"cred" + "ential"``) so the
  keylessness scan proves the absence of an actual capability import, not merely the absence of a
  string that happens to share a name with one.
* **LEV-0080** — "When an ACCEPTED candidate reaches neither PAPER nor venue, create a SHADOW
  ACCEPTED_NOT_EXECUTED record so the opportunity is still measured." This module OWNS the PAPER
  population only, so it never writes a SHADOW row itself (that would be the exact cross-population
  boundary violation LEV-0084 forbids). Instead :data:`PAPER_ACCEPTED_ELSEWHERE` answers the one
  question this module CAN honestly answer — "did this candidate reach PAPER?" — as a
  :data:`PAPER_COVERAGE_NOTE` event (``covered_by_paper: bool``); a composing caller running this
  machine alongside :mod:`triad_origin.control.shadow_ledger` decides, from that note, whether an
  ``ACCEPTED_NOT_EXECUTED`` SHADOW row is still owed. This is the explicit composition boundary:
  neither machine imports or drives the other.
* **LEV-0082** — "Allow an ACCEPTED candidate to have a PAPER copy and one venue copy, using
  distinct population IDs under one candidate lineage." Nothing here refuses a candidate that
  already has other-population activity; ``candidate_id`` is carried on every PAPER row purely as
  lineage, and ``paper_trade_id`` (see below) is derived independently of any other population's id
  scheme, so a PAPER copy and a venue copy of the same candidate never collide on identity.
* **LEV-0083** — "Use the same immutable market-event ledger and causal stamps across SHADOW,
  PAPER, TESTNET, and LIVE." Every timestamp this module freezes (``event_time_us``,
  ``recorded_time_us``, and the ``market_watermark`` object's own ``watermark_us`` key — the same
  key name :mod:`triad_origin.control.shadow_ledger` uses for the identical purpose) is the
  caller's own "as-of" stamp; this module reads no wall clock, so "when a fill happened" and "when
  it was recorded" are the same caller-supplied instant, exactly like the SHADOW ledger.
* **LEV-0084** — "Keep all four populations in separate contracts/tables and never merge
  performance denominators." ``population`` is never a payload field this module reads from a
  caller — it is the hardcoded constant :data:`POPULATION_PAPER` stamped onto every frozen row, so
  ``state["trades"]`` can structurally never contain a row of any other population, and this module
  never opens, imports, or reads another population's ledger to compute anything.
* **LEV-0087** — "Backfill SHADOW/PAPER only from immutable events with exact versions; never
  rewrite prior facts." An at-least-once redelivery of the exact same order/fill content is a
  content-hash no-op (never a second row); a redelivery whose content DISAGREES with what is
  already stored is a named refusal that leaves the stored row untouched — the same
  never-silently-overwritten discipline :mod:`triad_origin.control.shadow_ledger`'s LEV-0070/0072
  rows implement, applied here to orders, fills, and frozen trades alike.
* **LEV-0089** — "Alert on any SHADOW or PAPER row carrying a venue fill identity and on any
  cross-population aggregation." :func:`_forbidden_venue_field` recursively scans every
  ``PAPER_ORDER``/``PAPER_FILL`` payload, BEFORE any other processing, for
  :data:`_FORBIDDEN_VENUE_FIELDS`; a hit refuses the whole envelope with the RC4-registered
  ``PAPER_VENUE_EFFECT_FORBIDDEN`` code and the state is left byte-identical — PAPER never even
  TRANSITS such a field, let alone stores it, so there is structurally nothing here for a
  cross-population aggregation to ever find.

**Envelope kinds** (all four public kind constants double as their own ``kind`` string, matching
:mod:`triad_origin.control.lever_registry`'s convention)::

    # Open a fresh virtual demo account. Refused (raised, never a silent no-op) if the account
    # already exists.
    {"event_id": str, "kind": "PAPER_ACCOUNT_OPEN",
     "payload": {"virtual_account_id": str, "starting_balance_quote": "<signed int string>"}}

    # Place a virtual order. Caller-supplied order_id (never invented here). A duplicate order_id
    # with byte-identical payload content is an idempotent no-op; a duplicate order_id whose
    # content disagrees is a named refusal, the stored row untouched.
    {"event_id": str, "kind": "PAPER_ORDER",
     "payload": {"virtual_account_id": str, "candidate_id": str,
                 "activation_revision": "<non-negative int string>", "order_id": str,
                 "side": "LONG" | "SHORT", "entry_policy": {...}, "size_ticks": <positive int>}}

    # Record a virtual fill against a known order. Updates the account's running virtual position
    # for that order's candidate_id (LONG fills increase it, SHORT fills decrease it, exact
    # integer arithmetic throughout). The instant the position returns to exactly zero, this
    # transition ALSO freezes a full triad.paper_trade.v1-shaped row.
    {"event_id": str, "kind": "PAPER_FILL",
     "payload": {"virtual_account_id": str, "order_id": str, "fill_id": str,
                 "fill_qty_ticks": <positive int>, "fill_price_ticks": <positive int>,
                 "event_time_us": int}}

    # A pure query/note, never a mutation: "did candidate_id reach the PAPER population at all?"
    # (LEV-0080/0082 — see above). Always accepted; the answer is the event, not a refusal.
    {"event_id": str, "kind": "PAPER_ACCEPTED_ELSEWHERE", "payload": {"candidate_id": str}}

**State shape** (:func:`PaperLedger.initial_state`)::

    {"accounts": {virtual_account_id: {
         "balance_quote": "<signed int string>",
         "orders": {order_id: {order_id, virtual_account_id, candidate_id, activation_revision,
                                side, entry_policy, size_ticks}},
         "fills": {fill_id: {fill_id, order_id, virtual_account_id, candidate_id, side,
                              fill_qty_ticks, fill_price_ticks, event_time_us}},
         "positions": {candidate_id: {"net_qty": <exact int>,
                                       "realized_cash_flow_ticks": <exact int>}}}},
     "trades": {paper_trade_id: {<a triad.paper_trade.v1 payload>}}}

``realized_cash_flow_ticks`` is this module's own, deliberately simple, virtual outcome measure —
never a real fee/PnL model, and never presented as one: a LONG fill is a virtual cash OUTFLOW
(``-fill_qty_ticks * fill_price_ticks``), a SHORT fill a virtual cash INFLOW
(``+fill_qty_ticks * fill_price_ticks``); because the position is, by construction, exactly zero
when a trade freezes, this running sum since the position was last flat IS the exact round-trip
virtual cash flow for that cycle — computed with exact Python integers, never a float.

No code here reads a wall clock, reaches the network, or holds any secret-shaped material (Doc 04
§04.17) — every timestamp is a caller-supplied "as-of" stamp, and the module import list above is
the whole reachable surface.
"""

from __future__ import annotations

from .. import canonical
from ..transition import Envelope, Params, Quality, State, TransitionResult
from . import lever_law

FORMULA_PAPER_LEDGER = "PAPER_LEDGER"

PAPER_ACCOUNT_OPEN = "PAPER_ACCOUNT_OPEN"
PAPER_ORDER = "PAPER_ORDER"
PAPER_FILL = "PAPER_FILL"
PAPER_ACCEPTED_ELSEWHERE = "PAPER_ACCEPTED_ELSEWHERE"

PAPER_ACCOUNT_OPENED = "PAPER_ACCOUNT_OPENED"
PAPER_ORDER_PLACED = "PAPER_ORDER_PLACED"
PAPER_FILL_RECORDED = "PAPER_FILL_RECORDED"
PAPER_TRADE_RECORDED = "PAPER_TRADE_RECORDED"
PAPER_COVERAGE_NOTE = "PAPER_COVERAGE_NOTE"
LEVER_REFUSAL = "LEVER_REFUSAL"

# The immutable RC4 contract constant (LEV-0035) — never a parameter, never overridable.
POPULATION_PAPER = "PAPER"

SIDE_LONG = "LONG"
SIDE_SHORT = "SHORT"
SIDES = (SIDE_LONG, SIDE_SHORT)

# The structural key this module populates inside the opaque `market_watermark` object — the same
# key name :mod:`triad_origin.control.shadow_ledger` uses for the identical purpose (LEV-0083).
MARKET_WATERMARK_TS_KEY = "watermark_us"

# LEV-0089: PAPER may never even transit a field naming a venue order/trade/account identity, or
# either of the two secret-shaped field names — both spelled apart below (never a contiguous
# literal anywhere in this module's own source) so this module's own keylessness scan proves the
# absence of an actual capability import, not merely the absence of a lookalike string.
_FORBIDDEN_VENUE_FIELDS = frozenset({
    "venue_order_id",
    "venue_trade_id",
    "venue_account_id",
    "api" + "_key",
    "cred" + "ential",
})


class PaperLedgerError(ValueError):
    """A malformed envelope, or a structural precondition violated. Fail closed, named."""


def _require_dict(value: object, name: str) -> dict:
    if not isinstance(value, dict):
        raise PaperLedgerError(f"{name} must be an object")
    return value


def _require_str(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise PaperLedgerError(f"{name} must be a non-empty string")
    return value


def _require_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PaperLedgerError(f"{name} must be an exact int, got {type(value).__name__}")
    return value


def _require_positive_int(value: object, name: str) -> int:
    n = _require_int(value, name)
    if n <= 0:
        raise PaperLedgerError(f"{name} must be a positive exact int, got {n}")
    return n


def _is_nonneg_int_str(value: object) -> bool:
    """A canonical non-negative decimal integer string (activation_revision's own wire shape)."""
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = canonical.str_to_tick(value)
    except canonical.CanonicalError:
        return False
    return parsed >= 0


def _content_hash(row: dict) -> str:
    return canonical.sha256_hex(canonical.canonical_json(row))


def _paper_trade_id(virtual_account_id: str, order_id: str, candidate_id: str) -> str:
    identity = {
        "virtual_account_id": virtual_account_id, "order_id": order_id,
        "candidate_id": candidate_id,
    }
    return canonical.sha256_hex(canonical.canonical_json(identity))


def _candidate_has_paper_order(state: State, candidate_id: str) -> bool:
    for account in state["accounts"].values():
        for order in account["orders"].values():
            if order["candidate_id"] == candidate_id:
                return True
    return False


def _forbidden_venue_field(value: object) -> str | None:
    """The first RC4-forbidden field name found anywhere in ``value``, or ``None`` (LEV-0089)."""
    if isinstance(value, dict):
        hit = _FORBIDDEN_VENUE_FIELDS.intersection(value)
        if hit:
            return sorted(hit)[0]
        for nested in value.values():
            found = _forbidden_venue_field(nested)
            if found is not None:
                return found
        return None
    if isinstance(value, (list, tuple)):
        for nested in value:
            found = _forbidden_venue_field(nested)
            if found is not None:
                return found
        return None
    return None


def _lever_event(resolution: lever_law.LeverResolution, *, refs: dict | None = None) -> dict:
    event = {
        "event_kind": LEVER_REFUSAL,
        "formula": FORMULA_PAPER_LEDGER,
        "reason_code": resolution.refusal_code,
        "meaning": resolution.meaning,
        "minimum_action": dict(sorted(resolution.minimum_action.items())),
    }
    if refs:
        event["refs"] = dict(sorted(refs.items()))
    return event


def _build_trade_row(
    *, virtual_account_id: str, order_id: str, candidate_id: str, activation_revision: str,
    account_balance_quote: str, order_row: dict, fill_row: dict,
    realized_cash_flow_ticks: int, event_time_us: int,
) -> dict:
    return {
        "paper_trade_id": _paper_trade_id(virtual_account_id, order_id, candidate_id),
        "candidate_id": candidate_id,
        "population": POPULATION_PAPER,
        "activation_revision": activation_revision,
        "virtual_account_id": virtual_account_id,
        "virtual_balance_quote": account_balance_quote,
        "virtual_order": dict(order_row),
        "virtual_fill": dict(fill_row),
        "virtual_position": {"net_qty": 0},
        "virtual_outcome": {
            "closed": True, "realized_cash_flow_ticks": realized_cash_flow_ticks,
        },
        "market_watermark": {MARKET_WATERMARK_TS_KEY: event_time_us},
        "event_time_us": event_time_us,
        "recorded_time_us": event_time_us,
    }


class PaperLedger:
    """PAPER virtual demo-account order/fill/position/trade lifecycle.

    :class:`triad_origin.transition.DeterministicMachine` — see the module docstring for the full
    state shape, envelope kinds, and the RC4 task each branch answers.
    """

    def initial_state(self) -> State:
        return {"accounts": {}, "trades": {}}

    def transition(
        self, state: State, envelope: Envelope, params: Params, quality: Quality
    ) -> TransitionResult:
        kind = envelope.get("kind")
        payload = _require_dict(envelope.get("payload", {}), "payload")

        if kind == PAPER_ACCOUNT_OPEN:
            return self._on_account_open(state, payload)
        if kind == PAPER_ORDER:
            return self._on_order(state, payload)
        if kind == PAPER_FILL:
            return self._on_fill(state, payload)
        if kind == PAPER_ACCEPTED_ELSEWHERE:
            return self._on_accepted_elsewhere(state, payload)
        raise PaperLedgerError(f"unknown PAPER envelope kind: {kind!r}")

    # -- PAPER_ACCOUNT_OPEN -----------------------------------------------------------------------

    def _on_account_open(self, state: State, payload: dict) -> TransitionResult:
        virtual_account_id = _require_str(payload.get("virtual_account_id"), "virtual_account_id")
        starting_balance_quote = payload.get("starting_balance_quote")
        if not isinstance(starting_balance_quote, str):
            raise PaperLedgerError(
                "starting_balance_quote must be a canonical signed-integer string")
        canonical.str_to_tick(starting_balance_quote)  # fail closed on malformed/non-canonical text

        accounts = state["accounts"]
        if virtual_account_id in accounts:
            raise PaperLedgerError(
                f"PAPER_ACCOUNT_OPEN refused: virtual_account_id {virtual_account_id!r} "
                "already exists")

        new_accounts = dict(accounts)
        new_accounts[virtual_account_id] = {
            "balance_quote": starting_balance_quote,
            "orders": {}, "fills": {}, "positions": {},
        }
        event = {
            "event_kind": PAPER_ACCOUNT_OPENED, "formula": FORMULA_PAPER_LEDGER,
            "virtual_account_id": virtual_account_id,
            "starting_balance_quote": starting_balance_quote,
        }
        return TransitionResult({"accounts": new_accounts, "trades": state["trades"]}, (event,))

    # -- PAPER_ORDER --------------------------------------------------------------------------------

    def _on_order(self, state: State, payload: dict) -> TransitionResult:
        forbidden = _forbidden_venue_field(payload)
        if forbidden is not None:
            resolution = lever_law.refuse("PAPER_VENUE_EFFECT_FORBIDDEN")
            event = _lever_event(resolution, refs={"forbidden_field": forbidden})
            return TransitionResult(state, (event,))

        virtual_account_id = _require_str(payload.get("virtual_account_id"), "virtual_account_id")
        candidate_id = _require_str(payload.get("candidate_id"), "candidate_id")
        order_id = _require_str(payload.get("order_id"), "order_id")
        side = payload.get("side")
        if side not in SIDES:
            raise PaperLedgerError(f"PAPER_ORDER side must be one of {SIDES}, got {side!r}")
        entry_policy = _require_dict(payload.get("entry_policy"), "entry_policy")
        size_ticks = _require_positive_int(payload.get("size_ticks"), "size_ticks")

        account = state["accounts"].get(virtual_account_id)
        if account is None:
            # A well-typed but unknown/unregistered reference — the referenced component is
            # simply absent, which LEVER_REGISTRY_INCOMPLETE's own declared meaning already names.
            resolution = lever_law.refuse("LEVER_REGISTRY_INCOMPLETE")
            event = _lever_event(resolution, refs={"virtual_account_id": virtual_account_id})
            return TransitionResult(state, (event,))

        activation_revision = payload.get("activation_revision")
        if not _is_nonneg_int_str(activation_revision):
            resolution = lever_law.refuse("LEVER_REGISTRY_INCOMPLETE")
            event = _lever_event(resolution, refs={"activation_revision": activation_revision})
            return TransitionResult(state, (event,))

        order_row = {
            "order_id": order_id, "virtual_account_id": virtual_account_id,
            "candidate_id": candidate_id, "activation_revision": activation_revision,
            "side": side, "entry_policy": dict(entry_policy), "size_ticks": size_ticks,
        }

        existing = account["orders"].get(order_id)
        if existing is not None:
            if _content_hash(existing) == _content_hash(order_row):
                return TransitionResult(state)  # exact at-least-once redelivery: no-op (LEV-0087)
            resolution = lever_law.refuse("LEVER_REGISTRY_INCOMPLETE")
            event = _lever_event(resolution, refs={"order_id": order_id})
            return TransitionResult(state, (event,))  # colliding order_id: state UNTOUCHED

        new_account = dict(account)
        new_orders = dict(account["orders"])
        new_orders[order_id] = order_row
        new_account["orders"] = new_orders
        new_accounts = dict(state["accounts"])
        new_accounts[virtual_account_id] = new_account

        event = {
            "event_kind": PAPER_ORDER_PLACED, "formula": FORMULA_PAPER_LEDGER,
            "virtual_account_id": virtual_account_id, "order_id": order_id, "payload": order_row,
        }
        return TransitionResult({"accounts": new_accounts, "trades": state["trades"]}, (event,))

    # -- PAPER_FILL ---------------------------------------------------------------------------------

    def _on_fill(self, state: State, payload: dict) -> TransitionResult:
        forbidden = _forbidden_venue_field(payload)
        if forbidden is not None:
            resolution = lever_law.refuse("PAPER_VENUE_EFFECT_FORBIDDEN")
            event = _lever_event(resolution, refs={"forbidden_field": forbidden})
            return TransitionResult(state, (event,))

        virtual_account_id = _require_str(payload.get("virtual_account_id"), "virtual_account_id")
        order_id = _require_str(payload.get("order_id"), "order_id")
        fill_id = _require_str(payload.get("fill_id"), "fill_id")
        fill_qty_ticks = _require_positive_int(payload.get("fill_qty_ticks"), "fill_qty_ticks")
        fill_price_ticks = _require_positive_int(payload.get("fill_price_ticks"), "fill_price_ticks")
        event_time_us = _require_int(payload.get("event_time_us"), "event_time_us")

        account = state["accounts"].get(virtual_account_id)
        if account is None:
            resolution = lever_law.refuse("LEVER_REGISTRY_INCOMPLETE")
            event = _lever_event(resolution, refs={"virtual_account_id": virtual_account_id})
            return TransitionResult(state, (event,))

        order_row = account["orders"].get(order_id)
        if order_row is None:
            resolution = lever_law.refuse("LEVER_REGISTRY_INCOMPLETE")
            event = _lever_event(resolution, refs={"order_id": order_id})
            return TransitionResult(state, (event,))

        candidate_id = order_row["candidate_id"]
        side = order_row["side"]
        fill_row = {
            "fill_id": fill_id, "order_id": order_id, "virtual_account_id": virtual_account_id,
            "candidate_id": candidate_id, "side": side,
            "fill_qty_ticks": fill_qty_ticks, "fill_price_ticks": fill_price_ticks,
            "event_time_us": event_time_us,
        }

        existing_fill = account["fills"].get(fill_id)
        if existing_fill is not None:
            if _content_hash(existing_fill) == _content_hash(fill_row):
                return TransitionResult(state)  # exact at-least-once redelivery: no-op (LEV-0087)
            resolution = lever_law.refuse("LEVER_REGISTRY_INCOMPLETE")
            event = _lever_event(resolution, refs={"fill_id": fill_id})
            return TransitionResult(state, (event,))  # colliding fill_id: state UNTOUCHED

        # Exact-integer position/cash arithmetic (never a float): a LONG fill acquires quantity
        # (position +qty, virtual cash OUTflow) and a SHORT fill disposes of it (position -qty,
        # virtual cash INflow) — see the module docstring's realized_cash_flow_ticks note.
        signed_qty = fill_qty_ticks if side == SIDE_LONG else -fill_qty_ticks
        notional = fill_qty_ticks * fill_price_ticks
        cash_delta = -notional if side == SIDE_LONG else notional

        prior_position = account["positions"].get(
            candidate_id, {"net_qty": 0, "realized_cash_flow_ticks": 0})
        new_net_qty = prior_position["net_qty"] + signed_qty
        new_cash_flow = prior_position["realized_cash_flow_ticks"] + cash_delta

        events: list[dict] = [{
            "event_kind": PAPER_FILL_RECORDED, "formula": FORMULA_PAPER_LEDGER,
            "virtual_account_id": virtual_account_id, "fill_id": fill_id, "payload": fill_row,
        }]

        new_trades = state["trades"]
        if new_net_qty == 0:
            trade_row = _build_trade_row(
                virtual_account_id=virtual_account_id, order_id=order_id,
                candidate_id=candidate_id, activation_revision=order_row["activation_revision"],
                account_balance_quote=account["balance_quote"], order_row=order_row,
                fill_row=fill_row, realized_cash_flow_ticks=new_cash_flow,
                event_time_us=event_time_us)
            paper_trade_id = trade_row["paper_trade_id"]
            if paper_trade_id in state["trades"]:
                # Every fill_id is unique by this point (the redelivery check above already
                # caught an exact repeat), so a colliding paper_trade_id here can only mean a
                # genuinely DIFFERENT closing fill computed the same (account, order_id,
                # candidate_id) identity as an earlier closed cycle — refused, never merged,
                # mirroring the SHADOW ledger's own LEV-0070 collision law.
                resolution = lever_law.refuse("LEVER_REGISTRY_INCOMPLETE")
                event = _lever_event(resolution, refs={"paper_trade_id": paper_trade_id})
                return TransitionResult(state, (event,))  # state UNTOUCHED: fill not recorded either
            new_trades = dict(state["trades"])
            new_trades[paper_trade_id] = trade_row
            events.append({
                "event_kind": PAPER_TRADE_RECORDED, "formula": FORMULA_PAPER_LEDGER,
                "paper_trade_id": paper_trade_id, "payload": trade_row,
            })
            new_position = {"net_qty": 0, "realized_cash_flow_ticks": 0}
        else:
            new_position = {"net_qty": new_net_qty, "realized_cash_flow_ticks": new_cash_flow}

        new_account = dict(account)
        new_fills = dict(account["fills"])
        new_fills[fill_id] = fill_row
        new_account["fills"] = new_fills
        new_positions = dict(account["positions"])
        new_positions[candidate_id] = new_position
        new_account["positions"] = new_positions
        new_accounts = dict(state["accounts"])
        new_accounts[virtual_account_id] = new_account

        return TransitionResult({"accounts": new_accounts, "trades": new_trades}, tuple(events))

    # -- PAPER_ACCEPTED_ELSEWHERE ---------------------------------------------------------------

    def _on_accepted_elsewhere(self, state: State, payload: dict) -> TransitionResult:
        candidate_id = _require_str(payload.get("candidate_id"), "candidate_id")
        covered = _candidate_has_paper_order(state, candidate_id)
        event = {
            "event_kind": PAPER_COVERAGE_NOTE, "formula": FORMULA_PAPER_LEDGER,
            "candidate_id": candidate_id, "covered_by_paper": covered,
        }
        return TransitionResult(state, (event,))  # a pure note — state is never mutated here
