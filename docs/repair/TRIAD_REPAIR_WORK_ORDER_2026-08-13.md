# TRIAD — REPAIR WORK ORDER

**Document ID:** `TRIAD-REPAIR-WORK-ORDER-2026-08-13`
**Version:** `1.0.0`
**Prepared:** 2026-08-13
**Disposition:** `WORK_ORDER_SET / EXECUTION_GRADE / NOT_A_RATIFICATION / NO_RUNTIME_CHANGE UNTIL SIGNED`
**Companion:** `TRIAD_ORIGIN_V7_GAP_REGISTER_2026-08-13.md` — every work order below closes named `GAP-nn` rows.

---

## 0 · HOW TO USE THIS DOCUMENT

**Who this is written for.** A developer who has never seen this estate. Every term is defined at first use. Every file path is absolute or repo-relative and named. Every algorithm is written out. Every test carries its expected value, computed and verified, not left as "assert correct."

**The seven rules that govern every work order below.**

1. **Implement exactly what is written.** Where prose and pseudocode disagree, pseudocode wins. Where a value is marked `MUST_RATIFY`, build the mechanism and wire the named refusal — **do not hardcode the proposed value as active.**
2. **All arithmetic is exact.** Integer ticks and steps. Ratios as reduced rational pairs `(num: int64, den: int64)` with `den > 0` and `gcd(|num|, den) = 1`. Every ratio comparison by cross-multiplication on integers. **No binary float appears anywhere in a decision path.** A static scan enforces this.
3. **Nothing here disarms anything.** `shadow_activation = LIVE` is fixed with no OFF control. The existing estate money path stays armed. Every mechanism added below is a **gate that refuses one trade and records why**, never a switch that stops the engine. A refusal with full lineage is a data point; a trade taken without a cost check is not.
4. **Every refusal is named, typed, and recorded to SHADOW with full lineage.** No silent drop. No `None`. No bare `unknown`.
5. **Tests are part of the deliverable.** A work order without its listed vectors passing is `NOT_DONE`, not "mostly done." `NOT_RUN` is `NOT_RUN`, never coverage.
6. **One work order, one commit series.** Do not mix work orders in one commit. Each lands with its full test family in the same series.
7. **Never mutate published bytes.** Repaired modules ship under a new semantic version. The defective version is retired with a withdrawal banner, never edited, never deleted.

**Definitions used throughout.**

| Term | Definition |
|---|---|
| `bps` | Basis points. 1 bps = 1/10,000. |
| `R` | One unit of risk = the distance from entry to stop. A "+2R win" gained twice the risked distance. |
| `H_bps` | Total round-trip cost of one trade in bps of notional: entry fee + exit fee + spread crossed + slippage. |
| `stop_bps` | Distance from entry to stop, in bps of entry price. |
| `cost_R` | `H_bps / stop_bps`. Cost expressed in R. **This is the number that decides everything.** |
| `RR` | Reward-to-risk ratio = `|target − entry| / |entry − stop|`. |
| `p_BE` | Break-even win rate = `(1 + cost_R) / (1 + RR)`. |
| `W` | Realized average win, in R. **Not the same as `RR`** — `RR` describes the order, `W` describes the fills. |
| `no_fill` | A candidate whose entry order was never filled. **Not a neutral outcome.** See `WO-A`. |
| Maker | An order that rests in the book and adds liquidity. Binance USDⓈ-M: **2 bps**. |
| Taker | An order that crosses the spread and removes liquidity. Binance USDⓈ-M: **5 bps**. |
| GTX | Binance's post-only time-in-force. Rejected with `-5022` if it would take. |
| Algo order | Binance's conditional-order service. Since 2025-12-09 the **only** path for `STOP_MARKET` etc. |

**Sequencing.** Two tracks run in parallel. Track 1 is safety and runs on the box. Track 2 is economics and runs entirely in shadow with no venue risk.

```
TRACK 1 · SAFETY                    TRACK 2 · ECONOMICS
─────────────────────               ────────────────────────────────
WO-00  PROBE  (do first)            WO-A   diagnose the 13 pp
   │                                   │
   ▼                                   ▼
WO-01  algo-order path              WO-B   entry-mechanism arms
   │                                   │
   ▼                                   ▼
WO-02  PROTECTED STOP               WO-C   one derived RR floor
                                       │
                                       ▼
                                    WO-D   run the comparator
                                       │
                                       ▼
                                    WO-E   cost_model.v1
                                       │
                                       ▼
                                    WO-F   E07 admission gate
```

---

# TRACK 1 · SAFETY

---

# WO-00 · PROBE THE BOX

**Closes:** diagnostic for `GAP-05`, `GAP-07`, `GAP-08`, `GAP-10`
**Severity:** `P0` · **Owner:** box operator · **Duration:** 30 minutes
**Prerequisite:** none. **This runs before everything else in this document.**

## Why this exists

On **2025-12-09** Binance moved all conditional orders (`STOP_MARKET`, `TAKE_PROFIT_MARKET`, `STOP`, `TAKE_PROFIT`, `TRAILING_STOP_MARKET`) to a separate Algo Service. `POST /fapi/v1/order` now **rejects** those types with error `-4120 STOP_ORDER_SWITCH_ALGO`.

**If the executor places protective stops through the old endpoint, every stop placement has been failing silently since December.** A position with no stop is unbounded risk. Nothing else in this document matters until this is known.

## Steps — run each, record the exact output

### Step 1 — Find the protective-order placement call site

```bash
cd <TriadExecutor repo root>
grep -rn "fapi/v1/order\|fapi/v1/batchOrders\|fapi/v1/algoOrder" --include=*.py --include=*.rs .
grep -rn "STOP_MARKET\|TAKE_PROFIT_MARKET\|TRAILING_STOP_MARKET" --include=*.py --include=*.rs .
grep -rn "closePosition\|close_position\|reduceOnly\|reduce_only" --include=*.py --include=*.rs .
```

**Record:** for every hit, the file, line, and which endpoint constant it uses.

**Decision:**
- Any `STOP_MARKET` reaching `POST /fapi/v1/order` → **`GAP-05` is CONFIRMED LIVE. Escalate to P0 immediately. Proceed to WO-01 before anything else.**
- All conditional types reaching `POST /fapi/v1/algoOrder` → `GAP-05` is `SPEC_ONLY`. Still complete `WO-01` for the reconciliation half.

### Step 2 — Search the venue for evidence of the failure

```bash
grep -rn "\-4120\|STOP_ORDER_SWITCH_ALGO" --include=*.log --include=*.jsonl <log dir>
grep -rc "\-4120" <log dir>/*.log 2>/dev/null | grep -v ':0$'
```

**Record:** first occurrence timestamp, total count, distinct symbols. A first occurrence on or shortly after 2025-12-09 confirms the diagnosis to the day.

### Step 3 — Confirm the venue's current truth directly

Using the **read-only** audit credential (never the trading key):

```bash
# 3a. Are there any open algo orders right now?
GET /fapi/v1/openAlgoOrders

# 3b. Are there any open regular orders right now?
GET /fapi/v1/openOrders

# 3c. Are there open positions?
GET /fapi/v3/positionRisk
```

**Decision matrix — this is the critical read:**

| `positionRisk` | `openAlgoOrders` | Meaning | Action |
|---|---|---|---|
| position ≠ 0 | contains a matching stop | Protection armed | OK |
| **position ≠ 0** | **empty** | **UNPROTECTED POSITION** | **Page immediately. Flatten manually. Do not wait for WO-01.** |
| position = 0 | anything | No exposure | OK, continue |

### Step 4 — Confirm WebSocket base URLs

Legacy WebSocket URLs were decommissioned **2026-04-23**. Current paths use `/public`, `/market`, `/private`.

```bash
grep -rn "fstream\|wss://" --include=*.py --include=*.rs --include=*.toml --include=*.env .
```

**Record:** every WebSocket URL in the codebase. Any URL lacking `/public`, `/market` or `/private` is stale.

### Step 5 — Resolve `MIN_NOTIONAL` from the venue, not from a guide

```bash
GET /fapi/v1/exchangeInfo
# For each traded symbol, extract:
#   filters[] where filterType == "MIN_NOTIONAL"  -> notional
#   filters[] where filterType == "LOT_SIZE"      -> stepSize, minQty
#   filters[] where filterType == "PRICE_FILTER"  -> tickSize
```

**Record a table:** `symbol | MIN_NOTIONAL | stepSize | tickSize`.

The supplied ops guide asserts a **$20** minimum. Binance documents **5 USDT** and instructs reading the per-symbol filter. The estate's own limits config carries `min_notional_quote: "5"`. **Whichever the venue actually returns is the only true value.**

### Step 6 — Trace the sizing path by hand, once

At equity `$99.82`, `risk_pct_equity = 1.0`, stop `45 bps`:

```
risk_quote  = 99.82 × 0.01                  = $0.9982
stop_frac   = 45 / 10000                    = 0.0045
notional    = 0.9982 / 0.0045               = $221.82
qty         = 221.82 / mark_price
qty_steps   = floor(qty / stepSize) × stepSize
final_notional = qty_steps × mark_price
```

**$221.82 clears a 5 USDT minimum by 44×.** If the executor reports "below minimum," it is not computing this. Instrument the actual path and log every intermediate value:

```
LOG: equity=<> risk_pct=<> risk_quote=<> stop_bps=<> notional_target=<>
     mark=<> qty_raw=<> stepSize=<> qty_steps=<> final_notional=<>
     venue_min_notional=<> passes=<bool>
```

**Record the actual values.** They will not match the hand trace, and the difference is the defect.

## Acceptance

A file `PROBE-2026-08-13.md` containing all six step outputs verbatim, with the `GAP-05` verdict stated as one of `CONFIRMED_LIVE` / `SPEC_ONLY` / `INDETERMINATE`, and the unprotected-position check answered explicitly.

## Rollback

None. Read-only throughout. No order placed, cancelled, or modified.

---

# WO-01 · MIGRATE THE CONDITIONAL-ORDER PATH TO THE ALGO SERVICE

**Closes:** `GAP-05`, `GAP-09`, `GAP-10`
**Severity:** `P0` · **Prerequisite:** `WO-00`

## The venue facts, pinned

Source: Binance derivatives change log, entries 2025-11-06, 2025-12-10, 2025-12-29.

```
ENDPOINTS (conditional orders only — regular LIMIT/MARKET stay on /fapi/v1/order)
  POST   /fapi/v1/algoOrder          place
  DELETE /fapi/v1/algoOrder          cancel one
  DELETE /fapi/v1/algoOpenOrders     cancel all open
  GET    /fapi/v1/algoOrder          query one
  GET    /fapi/v1/openAlgoOrders     query open
  GET    /fapi/v1/allAlgoOrders      query history

  WebSocket API:  algoOrder.place  ·  algoOrder.cancel
  User stream event:  ALGO_UPDATE

AFFECTED TYPES
  STOP_MARKET · TAKE_PROFIT_MARKET · STOP · TAKE_PROFIT · TRAILING_STOP_MARKET

BLOCKED PATH
  POST /fapi/v1/order        -> -4120 STOP_ORDER_SWITCH_ALGO for the above types
  POST /fapi/v1/batchOrders  -> same

BEHAVIOURAL CHANGES YOU MUST HANDLE
  1. NO margin check before the conditional order triggers.
     => A stop can be accepted and then fail at trigger for insufficient margin.
     => Protection is NOT proven by acknowledgement. It is proven by reconciliation.
  2. Modification of untriggered conditional orders is NOT supported.
     => There is no amend. Every change is cancel-then-place.
     => Between cancel-ack and place-ack the position is UNPROTECTED. This window
        must be bounded, measured, and alarmed. Place-before-cancel where the venue
        permits it; where it does not, the window is a declared risk with a deadline.
  3. GTE_GTC orders depend on positions only, not on opposite-side open orders.
  4. CONDITIONAL_ORDER_TRIGGER_REJECT was deprecated 2025-12-15.
     => Rejection reasons now arrive inside ALGO_UPDATE. A listener that only
        handles ORDER_TRADE_UPDATE will never learn that its stop was rejected.

LIMITS
  Conditional orders: 200 across ALL symbols  (the MAX_NUM_ALGO_ORDERS filter was
    REMOVED from exchangeInfo on 2025-12-29 — do not read it, it is gone)
  Conditional orders per position: 10
  All open orders: 10,000
  closePosition=true: at most 1 active per type per direction — cancel before replacing

ERROR CODES TO HANDLE EXPLICITLY
  -4120  STOP_ORDER_SWITCH_ALGO      wrong endpoint (this defect)
  -4116  ClientOrderId is duplicated
  -4117  Stop order is in triggering process, try again later
  -1008  Throttled by system-level protection
         NOTE: "Reduce-only/close-position orders are exempt" — this is why the
         protective stop in WO-02 uses closePosition
  -5022  GTX post-only rejected; order NOT recorded in order history
  -2011  Unknown order (cancel of something that does not exist)
```

## Build

### 1.1 Split the venue client

**File:** `<executor>/venue/binance_usdm/client.py` (or `.rs` equivalent)

```python
# Two physically separate submit paths. A conditional type must be UNABLE to
# reach the regular path by construction, not by convention.

CONDITIONAL_TYPES = frozenset({
    "STOP_MARKET", "TAKE_PROFIT_MARKET", "STOP",
    "TAKE_PROFIT", "TRAILING_STOP_MARKET",
})

def submit_regular(payload: RegularOrderPayload) -> VenueAck:
    if payload.order_type in CONDITIONAL_TYPES:
        raise VenueRoutingError(
            code="ROUTING_CONDITIONAL_ON_REGULAR_PATH",
            detail=f"{payload.order_type} must route to submit_algo",
        )
    return _post("/fapi/v1/order", payload)

def submit_algo(payload: AlgoOrderPayload) -> VenueAck:
    if payload.order_type not in CONDITIONAL_TYPES:
        raise VenueRoutingError(
            code="ROUTING_REGULAR_ON_CONDITIONAL_PATH",
            detail=f"{payload.order_type} must route to submit_regular",
        )
    return _post("/fapi/v1/algoOrder", payload)
```

**Static gate — add to CI, must fail the build:**

```
FAIL if any string literal from CONDITIONAL_TYPES appears in the same function
     body as the literal "/fapi/v1/order" or "/fapi/v1/batchOrders".
FAIL if "MAX_NUM_ALGO_ORDERS" appears anywhere (the filter no longer exists).
```

### 1.2 Consume `ALGO_UPDATE`

**File:** `<executor>/venue/binance_usdm/user_stream.py`

The user stream handler currently dispatches `ORDER_TRADE_UPDATE`, `ACCOUNT_UPDATE`, etc. Add `ALGO_UPDATE` as a **first-class event with its own persistence**, not an alias.

```python
def on_user_event(evt: dict) -> None:
    kind = evt.get("e")
    if kind == "ORDER_TRADE_UPDATE":
        _handle_regular_order(evt)
    elif kind == "ALGO_UPDATE":
        _handle_algo_order(evt)          # NEW — do not fold into the branch above
    elif kind == "ACCOUNT_UPDATE":
        _handle_account(evt)
    else:
        _record_unhandled(kind, evt)     # never silently drop
```

`_handle_algo_order` must persist to `protection_event.v2` with the full algo lifecycle: `NEW → TRIGGERING → TRIGGERED → FINISHED`, plus `REJECTED`, `EXPIRED`, `CANCELED`. RC3 CHK-0336 already specifies this contract. **Rejection reasons arrive here and nowhere else.**

### 1.3 Reconciliation must query both order books

**File:** `<executor>/reconcile/venue_reconciler.py`

```python
def reconcile(account: AccountRef) -> ReconcileResult:
    positions   = venue.get("/fapi/v3/positionRisk")
    regular     = venue.get("/fapi/v1/openOrders")
    algo        = venue.get("/fapi/v1/openAlgoOrders")     # NEW — previously absent
    fills       = venue.get("/fapi/v1/userTrades", since=cursor)

    for pos in positions:
        if pos.qty == 0:
            continue
        protective = [a for a in algo
                      if a.symbol == pos.symbol
                      and a.order_type in ("STOP_MARKET", "STOP")
                      and _reduces(a, pos)]
        if not protective:
            emit_refusal("POSITION_UNPROTECTED",
                         symbol=pos.symbol, qty=pos.qty,
                         severity="P0", page=True)
            # ARMED-BY-DEFAULT: do NOT disarm the estate. Arm protection for
            # THIS position immediately (WO-02), page, and continue.
            protective_stop.arm(pos)
    ...
```

**A reconciler that queries only `/fapi/v1/openOrders` will report every position as unprotected, or — worse — will not look and report nothing.** This is the reconciliation half of `GAP-05`.

### 1.4 Resolve the GTX unknown-submit case

`GAP-09`: a rejected GTX order is **absent from `GET /fapi/v1/order` and `GET /fapi/v1/allOrders`.** Absence therefore proves nothing on its own.

```
UNKNOWN SUBMIT RESOLUTION FOR GTX  (normative)

Given: a GTX submit whose HTTP response was lost (timeout, disconnect, crash).

  1. Query GET /fapi/v1/openOrders filtered by symbol.
       found by clientOrderId  -> state = RESTING. Done.
  2. Query GET /fapi/v1/userTrades since (submit_time - 5s).
       any fill carrying clientOrderId -> state = FILLED. Done.
  3. Query GET /fapi/v1/allOrders since (submit_time - 5s).
       found -> state = terminal, read status. Done.
  4. NOT FOUND in any of the three:
       state = REJECTED_OR_NEVER_SENT.
       These two are indistinguishable by construction and MUST NOT be guessed.
       Both are economically identical: no venue effect, no position change.
       Emit GTX_UNRESOLVED_NO_VENUE_EFFECT{clientOrderId, submit_time,
                                            search_log=[1,2,3]}
       Treat as no-effect. Re-evaluate from a FRESH validated book.
       Consume one reprice-budget unit (a lost attempt is still an attempt).
  5. NEVER retry with the same clientOrderId after step 4 without a fresh
     idempotency identity — -4116 will reject a duplicate, and a duplicate that
     somehow lands is a double position.
```

## Tests — every one must exist and pass

| # | Scenario | Expected |
|---|---|---|
| T1 | `submit_regular(STOP_MARKET)` | raises `ROUTING_CONDITIONAL_ON_REGULAR_PATH`, no HTTP call made |
| T2 | `submit_algo(LIMIT)` | raises `ROUTING_REGULAR_ON_CONDITIONAL_PATH`, no HTTP call made |
| T3 | Static scan on a fixture placing `STOP_MARKET` at `/fapi/v1/order` | CI **fails** |
| T4 | Static scan finds `MAX_NUM_ALGO_ORDERS` | CI **fails** |
| T5 | `ALGO_UPDATE` with `algoStatus=REJECTED` | `protection_event.v2` row written with reason; `POSITION_UNPROTECTED` raised if position ≠ 0 |
| T6 | Reconcile: position ≠ 0, `openAlgoOrders` empty | `POSITION_UNPROTECTED` P0 + page + protection armed. **Estate is NOT disarmed.** |
| T7 | Reconcile: position ≠ 0, matching algo stop present | clean, no refusal |
| T8 | GTX submit, response lost, not in openOrders/userTrades/allOrders | `GTX_UNRESOLVED_NO_VENUE_EFFECT`, reprice budget −1, **no retry on same clientOrderId** |
| T9 | GTX submit, response lost, IS in openOrders | `RESTING`, no refusal, no duplicate submit |
| T10 | 200 conditional orders open, place the 201st | `REFUSED_ALGO_BUDGET_EXHAUSTED` before any HTTP call |
| T11 | `closePosition=true` placed while one already active same type/direction | cancel-then-place sequence, never two |
| T12 | `-4117` (stop in triggering process) returned | bounded retry with backoff; **never** treated as failure-to-protect |

## Acceptance

All twelve pass. The static gate is a required CI stage. A replay of the last 30 days of user-stream events reconstructs a `protection_event.v2` timeline with zero `UNHANDLED` event kinds.

## Rollback

Revert the client split. The old path is preserved as `client_v1.py` with a `RETIRED_DEFECTIVE{GAP-05}` banner. **Bytes preserved, never deleted.**

---

# WO-02 · THE PROTECTED STOP

**Closes:** `GAP-15`
**Severity:** `P0` · **Prerequisite:** `WO-01`
**Ratifies:** `EXIT-MECH-01`

## The problem, stated exactly

RC3 law 14 makes post-only maker the *normal* exit. **A post-only stop that cannot fill as maker does not fill.** The position keeps moving. The loss is unbounded.

The registered ruling `EXIT-MECH-01` already says this: a limit priced to cross is a taker regardless of label; post-only is the only maker guarantee; instant-fill maker is impossible; taker cost on the stop leg of losers is **bounded** at ~0.04–0.1 R blended; **maker-stop failure is unbounded.**

**Bounded cost versus unbounded tail is not a close call.**

## The design — two orders, not one escalation loop

There are two possible readings of "stop-limit attempts maker then escalates." Only one is safe.

| Reading | Mechanism | Verdict |
|---|---|---|
| **(a)** A stop-limit that, once triggered, rests as a limit for `T` seconds, then the engine cancel-replaces to market | Requires the engine to be alive, connected, and fast at the exact moment of maximum stress. **If the engine is down, there is no escalation.** | **REJECTED** — reintroduces the unbounded tail through a latency-dependent path |
| **(b)** An unconditional venue-side `STOP_MARKET` rail placed first, plus an optional maker limit resting inside the band ahead of it | The rail lives at the venue. It fires whether or not the engine is alive. The maker attempt is pure upside — if it fills, the rail is cancelled; if it doesn't, the rail fires. | **ADOPTED** |

**Reading (b) is also cheaper to operate:** `-1008` throttling explicitly exempts reduce-only and close-position orders, so the rail is the one order class that cannot be throttled away under load — precisely when you need it.

## The mechanism

```
PROTECTED_STOP(position P, invalidation price S, params)

PHASE 1 — THE RAIL  (unconditional, placed FIRST, before any maker attempt)
  order_type   = STOP_MARKET
  side         = opposite of P.side
  stopPrice    = S
  closePosition= true                    # exempt from -1008 throttling
  workingType  = MARK_PRICE              # MUST_RATIFY, see TBD-018
  priceProtect = true                    # MUST_RATIFY, see TBD-018
  positionSide = BOTH (one-way) | P.positionSide (hedge)
  endpoint     = POST /fapi/v1/algoOrder      # NEVER /fapi/v1/order
  DO NOT send quantity with closePosition=true.
  DO NOT combine closePosition=true with reduceOnly — the venue rejects it.

  DEADLINE: PROTECTION_ARM_DEADLINE_MS from the entry fill acknowledgement.
            MUST_RATIFY. Proposed 2000 ms.
            Miss the deadline -> EMERGENCY_FLATTEN via F22 IOC. Do not wait.
  PROOF:    the rail is armed when it appears in GET /fapi/v1/openAlgoOrders
            with a matching clientAlgoId. Acknowledgement alone is NOT proof —
            since 2025-12-09 there is no margin check before trigger, so an
            accepted order is not a guaranteed exit.

PHASE 2 — THE MAKER ATTEMPT  (optional, pure upside, never blocking)
  Only after the rail is PROVEN armed.
  order_type   = LIMIT
  timeInForce  = GTX                      # post-only, guaranteed maker
  price        = S ± X_bps on the favourable side
                 (long position -> SELL at S + X_bps; short -> BUY at S − X_bps)
                 X_bps MUST_RATIFY. Proposed 5 bps.
  reduceOnly   = true
  quantity     = |P.qty|
  endpoint     = POST /fapi/v1/order      # LIMIT is NOT conditional

  This order sits INSIDE the rail — closer to current price — so it has the
  chance to fill first on an orderly move. On a violent move price gaps past it
  and the rail fires. Either way the position closes.

  -5022 on placement -> the maker price is already crossable. Do not retry, do
  not reprice into a taker. The rail is armed; that is sufficient. Record
  MAKER_EXIT_UNAVAILABLE{reason=GTX_REJECTED} and continue.

PHASE 3 — MUTUAL CANCELLATION
  maker LIMIT fills   -> cancel the rail (DELETE /fapi/v1/algoOrder).
                         Verify position == 0 before declaring the campaign flat.
  rail TRIGGERS       -> cancel the maker LIMIT (DELETE /fapi/v1/order).
                         Cancel FIRST, then verify. A -2011 (unknown order) on
                         cancel is SUCCESS — it means it was already gone.
  BOTH appear to act  -> reconcile against GET /fapi/v3/positionRisk.
                         Position is the truth. Orders are claims.

INVARIANT, asserted after every transition:
  sum(reduce-only quantity across all live protective orders) <= |P.qty|
  A violation means a reversal is possible. HALT and page.

MODIFICATION:
  The venue does NOT support modifying an untriggered conditional order.
  Every stop change is cancel-then-place.
  The window between cancel-ack and place-ack is UNPROTECTED.
  Bound it: UNPROTECTED_WINDOW_MAX_MS, MUST_RATIFY, proposed 1000 ms.
  Exceeded -> page. Do not disarm; arm a replacement rail immediately.
```

## Order-budget accounting

Two orders per open position. Venue limits: 10 conditional per position, 200 conditional across all symbols, 10,000 orders total.

```
max_concurrent_positions <= floor(200 / 1)     # one rail each
Assert before every entry:
    open_algo_count + 1 <= 200   else REFUSED_ALGO_BUDGET_EXHAUSTED
```

The estate's current `per_symbol.max_concurrent_positions = 1` across a 30-symbol universe gives a worst case of 30 rails — well inside 200. **Record the assertion anyway.** Budgets that are never checked are budgets that are exceeded exactly once.

## Bindings — all `MUST_RATIFY`, all refuse until signed

| Row | Proposed | Refusal when unratified |
|---|---|---|
| `PROTECTION_ARM_DEADLINE_MS` | 2000 | `BLOCKED_ON_RATIFY(PROTECTION_ARM_DEADLINE_MS)` |
| `MAKER_EXIT_BAND_BPS` (`X_bps`) | 5 | Phase 2 skipped entirely; rail-only. **Safe default.** |
| `UNPROTECTED_WINDOW_MAX_MS` | 1000 | `BLOCKED_ON_RATIFY(...)` |
| `PROTECTION_WORKING_TYPE` | `MARK_PRICE` | `BLOCKED_ON_RATIFY(...)` — TBD-018 |
| `PROTECTION_PRICE_PROTECT` | `true` | `BLOCKED_ON_RATIFY(...)` — TBD-018 |

**Note the asymmetry, and keep it.** If `MAKER_EXIT_BAND_BPS` is unratified, Phase 2 is skipped and the system runs rail-only — which is *safer*, merely more expensive. If `PROTECTION_ARM_DEADLINE_MS` is unratified, the system cannot prove protection in time and must refuse new entries. **Unratified must always fail toward safety, never toward silence.**

## Tests

| # | Scenario | Expected |
|---|---|---|
| T1 | Entry fills | rail placed via `/fapi/v1/algoOrder` **before** any maker attempt; ordering asserted |
| T2 | Rail ack received, but not in `openAlgoOrders` within deadline | `PROTECTION_UNPROVEN` → emergency flatten |
| T3 | `MAKER_EXIT_BAND_BPS` unratified | Phase 2 skipped; rail-only; **no error** |
| T4 | Maker limit `-5022` | `MAKER_EXIT_UNAVAILABLE`; rail intact; no reprice; no taker |
| T5 | Maker fills | rail cancelled; position verified 0 |
| T6 | Rail triggers | maker cancelled; `-2011` on that cancel treated as **success** |
| T7 | Both appear filled | reconcile against `positionRisk`; position wins; discrepancy recorded |
| T8 | Stop moved | cancel-then-place; unprotected window measured and under bound |
| T9 | Unprotected window exceeds bound | page; replacement rail armed; **estate stays armed** |
| T10 | Sum of reduce-only qty > position | HALT + page |
| T11 | 200 algo orders open | `REFUSED_ALGO_BUDGET_EXHAUSTED` before entry, not after |
| T12 | Engine killed between entry fill and rail placement, then restarted | restart reconcile finds unprotected position, arms rail, pages |
| T13 | Full short mirror of T1–T12 | exact sign inversion |

## Acceptance

All thirteen pass on testnet with real venue round-trips, not mocks. A 24-hour testnet soak with induced disconnects shows **zero** intervals in which a non-zero position had no armed rail, measured at 1-second resolution.

---

# TRACK 2 · ECONOMICS

---

# WO-A · DIAGNOSE THE 13 PERCENTAGE POINTS

**Closes:** `GAP-43`, `GAP-44`, `GAP-47`, `GAP-49`
**Severity:** `P0` · **Prerequisite:** none. **Pure measurement. No venue access. No arming. Can start today.**

## Why this is now the lead work order

```
frozen baseline WR .......... 54.4 %      (recorded in the engine's own source)
break-even WR ............... 38.2 – 40.3 %  (its own 67–120 bps band, H = 9 bps)
operator's live report ...... "barely profitable, borderline losing"
implied realized WR ......... 38 – 42 %

THE MARGIN OF THE BUSINESS .. ~14 – 16 pp
WHAT SURVIVES ............... 0 – 4 pp
```

**Roughly 13 percentage points of win rate are earned by the signal and lost somewhere before the money lands.** Finding them is worth more than any new detector, and it costs nothing but query time.

## Task A1 — Compute `no_fill_win_share`. This is the number nobody has.

**The hypothesis to test.** The counterfactual resolver scores only filled candidates. `no_fill` is **2,617 of 8,008 rows — 46.6 % of everything that could have been filled.** For a resting limit entry, fill and outcome are causally coupled in one direction: you get filled when price comes to you *and keeps going against you*; you do **not** get filled when price turns at your level and runs to target *without you*. **The winners are systematically over-represented among the ones that got away.**

**The measurement.** For every `no_fill` row, replay the same tape and ask: had the entry been taken at the **signal price** — market-at-signal, not the resting limit price — would it have reached TP before SL?

```sql
-- Pseudo-SQL. Adapt to the bank schema. The shape is what matters.
--
-- INPUT:  every row where shadow_outcome = 'no_fill'
-- OUTPUT: for each, a counterfactual outcome under market-at-signal entry
--
-- CRITICAL: entry price for this counterfactual is the MARK PRICE AT SIGNAL
--           TIME, not cf_entry_price (which is the resting limit price that
--           never filled). The stop and target must be RE-DERIVED from the new
--           entry so that stop_bps is preserved, otherwise you are measuring a
--           different trade.

WITH nofills AS (
  SELECT decision_id, instrument_id, side, opened_at,
         cf_entry_price, cf_sl_price, cf_tp1_price
  FROM shadow_bank
  WHERE shadow_outcome = 'no_fill'
),
resited AS (
  SELECT n.*,
         m.mark_price                                    AS entry_at_signal,
         ABS(n.cf_entry_price - n.cf_sl_price)           AS stop_dist,
         ABS(n.cf_tp1_price  - n.cf_entry_price)         AS tgt_dist
  FROM nofills n
  JOIN marks m
    ON m.instrument_id = n.instrument_id
   AND m.ts = n.opened_at          -- exact signal-time mark, not a nearby bar
)
SELECT decision_id,
       entry_at_signal,
       CASE WHEN side='LONG' THEN entry_at_signal - stop_dist
            ELSE entry_at_signal + stop_dist END          AS sl_resited,
       CASE WHEN side='LONG' THEN entry_at_signal + tgt_dist
            ELSE entry_at_signal - tgt_dist END           AS tp_resited
FROM resited;
-- Then run the SAME first-touch resolver over these re-sited levels.
```

**Then report exactly this, and nothing more:**

```
no_fill_win_share = wins_under_market_entry / (wins + losses) among no_fill rows

true_opportunity_WR = (1482 + no_fill_win_share × 2617)
                    / (1482 + 1522 + 2617)

adverse_selection_gap = 49.33 % − true_opportunity_WR
```

**Reference sensitivity, precomputed so you can sanity-check your result:**

| `no_fill_win_share` | true opportunity WR | Reported on filled subset |
|---:|---:|---:|
| 0 % | 26.4 % | 49.33 % |
| 20 % | 35.7 % | 49.33 % |
| **35 %** | **42.7 %** | 49.33 % |
| 50 % | 49.6 % | 49.33 % |
| 65 % | 56.6 % | 49.33 % |

**A result near 50 % means fills are random and adverse selection is not the culprit — look elsewhere.** A result meaningfully below 50 % confirms it, and `WO-B` becomes the highest-value work in the estate. **Compute the number before deciding.**

## Task A2 — Audit the R denominator. Every R figure in the estate is currently ambiguous.

The engine's geometry has **two** risk distances:

```
mid        = (zone_low + zone_high) / 2
b          = max(zone_width, abs_band, mid × floor_bps / 1e4)
stop       = mid − b            <- risk = b
invalidation = mid − b − b/2    <- risk = 1.5b
target t1  = mid + GROSS_RR_FLOOR × b
```

The teardown states *"RR is ~1.67 vs the stated invalidation, ≥2.0 vs the stop."* **So `1R` means one thing in one sentence and 1.5× that in the next.**

Every figure in circulation — `+0.533R` frozen, `1.818R` realized, `−0.59R` bank-net, `−643R` total, `−0.13R` order_block, `+0.12R` fvg_retest — carries no denominator tag. Under the never-blend law **these are not comparable numbers.**

**Deliverable:** add a mandatory field to every R-carrying row.

```
risk_denominator ∈ { STOP | INVALIDATION }     NOT NULL, no default

Backfill rule: read it from the resolver that produced the row. Where the
producing resolver cannot be determined, the value is
UNRESOLVED_RISK_DENOMINATOR — an honest null, never a guess, and excluded
from every aggregate until resolved.
```

Then republish every headline number twice, once per denominator, and **retire every untagged figure with a withdrawal banner.**

## Task A3 — Reconcile three stop regimes

| Regime | Value | Where | Break-even WR at `W=1.818`, `H=9` |
|---|---|---|---:|
| Engine band floor | 67–120 bps | `zone_geometry()` `band_of` | 38.2 – 40.3 % |
| Governor admission floor | 45 bps | `per_trade.min_stop_width_bps` | **42.6 %** |
| Shadow bank median | **10.0 bps** | `get_bank_priced` | **67.4 %** |

**At 10 bps the break-even win rate is 67.4 %. No SMC setup clears that. The bank is scoring a geometry that no layer of the system would authorize.**

**Deliverable:** a table of every distinct `stop_bps` regime present in the bank, with row counts and per-regime break-even, plus a written determination of which regime the `+0.533R` frozen baseline was measured under. **If the answer is "10 bps," the frozen baseline is void and must be withdrawn.**

## Task A4 — Publish the reconciliation

One page. Six numbers. No prose padding.

```
1. no_fill_win_share                          = ____ %
2. true_opportunity_WR                        = ____ %
3. adverse_selection_gap                      = ____ pp
4. realized live WR, last 90 days, tagged     = ____ %
5. R denominator of the frozen baseline       = STOP | INVALIDATION
6. stop_bps regime of the frozen baseline     = ____ bps

VERDICT: the ~13 pp gap decomposes as
   adverse selection ....... ____ pp
   denominator mismatch .... ____ pp
   stop-regime mismatch .... ____ pp
   resolver disagreement ... ____ pp
   unexplained ............. ____ pp
```

**"Unexplained" must be stated, not absorbed.** If it exceeds 3 pp the diagnosis is incomplete and `WO-B` waits.

## Acceptance

All six numbers computed from the bank with `COUNT(DISTINCT decision_id)` denominators, epoch-integer time arithmetic (`uh = FLOOR(((ts/1e6)::BIGINT % 86400)/3600)` — never `EXTRACT(hour FROM to_timestamp(...))`, which renders in the box's `−07:00` session timezone), and every query reproducible from a committed SQL file.

---

# WO-B · ENTRY-MECHANISM ARMS

**Closes:** `GAP-14`, `GAP-16`, `GAP-45`
**Severity:** `P0` · **Prerequisite:** `WO-A` (task A1 specifically)
**Amends:** RC3 non-negotiable law 14, entry half only

## The trade, in one block

```
Binance USDⓈ-M standard tier:  maker 2 bps/side · taker 5 bps/side
Round trips:  maker/maker 4 · maker-in/taker-out 7 · taker/taker 10

COST of switching entry from maker to taker, expressed in win rate:
    extra 6 bps ÷ (W + 1)  where W = 1.818 R
    at 67 bps stop  ->  3.18 pp
    at 120 bps stop ->  1.77 pp

BENEFIT measured by this estate:
    resting entry ......... ~28 % WR
    confirmed entry ....... ~46 % WR
    market-at-signal ...... ~51.5 % WR
    gap ................... 23.5 pp

MARGIN OF SAFETY:  7×  (67 bps)  to  13×  (120 bps)
```

**Net EV by mechanism, at `W = 1.818R`:**

| Mechanism | WR | `H` | net @ 67 bps | net @ 120 bps |
|---|---:|---:|---:|---:|
| resting maker, live-observed | 40 % | 4 | +0.068 R | +0.094 R |
| confirmed entry | 46 % | 7 | +0.192 R | +0.238 R |
| **market-at-signal, pessimistic** | 45 % | 10 | **+0.119 R** | **+0.185 R** |
| **market-at-signal, measured** | 51.5 % | 10 | **+0.302 R** | **+0.368 R** |

**Even assuming market-at-signal delivers only 45 % — well below the 51.5 % the estate measured — it beats the current resting path by 1.8×.** Break-even rises only from 37.60 % to 40.78 % across the whole fee swap.

## Why this is a measurement, not a switch

Law 14 is a constitutional prohibition under a heading reading *"No implementer interpretation."* **Do not violate it. Amend it, then measure it.** The amendment converts one arm into three and requires that all three be measured before one is chosen.

## Build

### B1 — The arm registry

**File:** `<engine>/config/entry_arms.v1.json`

```json
{
  "schema": "triad/entry_arms/1",
  "ratified_by": "PENDING",
  "arms": [
    { "arm_id": "ENTRY_POST_ONLY_RESTING",
      "cohort_tag": "entry:post_only_resting",
      "order_type": "LIMIT", "time_in_force": "GTX",
      "price_rule": "ZONE_EDGE",
      "H_bps_entry_leg": 2,
      "status": "ACTIVE_CONTROL" },

    { "arm_id": "ENTRY_CONFIRMED",
      "cohort_tag": "entry:confirmed",
      "order_type": "LIMIT", "time_in_force": "GTX",
      "price_rule": "ZONE_EDGE_AFTER_CONFIRMATION_CLOSE",
      "H_bps_entry_leg": 2,
      "status": "PROPOSED_MUST_RATIFY" },

    { "arm_id": "ENTRY_MARKET_AT_SIGNAL",
      "cohort_tag": "entry:market_at_signal",
      "order_type": "MARKET",
      "price_rule": "MARK_AT_SIGNAL",
      "H_bps_entry_leg": 5,
      "status": "PROPOSED_MUST_RATIFY" }
  ]
}
```

**Laws that make this an experiment rather than a change:**

1. **`H_bps_entry_leg` is per-arm and mandatory.** An arm without its own fee model cannot be scored. A shared `H` would make the comparison meaningless — the whole point is that the arms cost different amounts.
2. **`cohort_tag` rides every row the arm produces, forever.** Under never-blend, arms are never aggregated. Ever.
3. **`ENTRY_POST_ONLY_RESTING` is `ACTIVE_CONTROL`, not `PROPOSED`.** It is the current behaviour and the control arm. It does not change and does not need ratification.
4. **Shadow first.** All three arms run in SHADOW simultaneously from day one — shadow costs nothing and violates no law. Only one arm may be money-eligible at a time, and promoting a different arm to money-eligible is a ceremony.

### B2 — Shadow-resolve all three arms on every candidate

This is the key mechanism and it needs stating precisely: **every candidate produces three shadow rows, one per arm, on the same tape, at the same instant.**

```python
def emit_shadow_arms(candidate: EdgeCandidate, tape: Tape) -> list[ShadowRow]:
    rows = []
    for arm in ENTRY_ARMS:
        entry_px = resolve_entry_price(arm, candidate, tape)
        if entry_px is None:
            rows.append(ShadowRow(arm=arm.arm_id,
                                  outcome="ARM_INAPPLICABLE",
                                  reason=...))
            continue

        # CRITICAL: re-derive stop and target from THIS arm's entry so that
        # stop_bps is IDENTICAL across arms. Otherwise you are comparing
        # different trades and the result is meaningless.
        stop_px = derive_stop(entry_px, candidate.stop_bps, candidate.side)
        tgt_px  = derive_target(entry_px, stop_px, candidate.rr)

        outcome = first_touch_resolve(tape, entry_px, stop_px, tgt_px,
                                      fill_model=arm.fill_model)
        rows.append(ShadowRow(
            arm=arm.arm_id, cohort_tag=arm.cohort_tag,
            entry=entry_px, stop=stop_px, target=tgt_px,
            stop_bps=candidate.stop_bps,          # identical across arms
            H_bps=arm.H_bps_entry_leg + EXIT_LEG_H_BPS,
            risk_denominator="STOP",              # WO-A task A2
            outcome=outcome,
            decision_id=candidate.decision_id))   # joins the arms together
    return rows
```

**`fill_model` per arm — this is where the honesty lives:**

| Arm | Fill model |
|---|---|
| `ENTRY_POST_ONLY_RESTING` | Fills **only** if price trades **through** the limit — touching it is not enough for a resting order behind a queue. Otherwise `no_fill`. **This is the model that generates the 2,617 no_fills.** |
| `ENTRY_CONFIRMED` | Same, but the order is only placed after the confirmation close. |
| `ENTRY_MARKET_AT_SIGNAL` | **Always fills**, at the signal-time mark plus a slippage assumption. `no_fill` is impossible by construction. |

**The single most important line in this work order:** `ENTRY_MARKET_AT_SIGNAL` **has no `no_fill` outcome.** That is not a modelling convenience — it is precisely the difference being measured, and it is why the 2,617 excluded rows come back into the denominator.

### B3 — The comparison, done once, correctly

After a declared window — `ENTRY_ARM_WINDOW_DAYS`, `MUST_RATIFY`, proposed 21 days, frozen before the window opens:

```
Per arm, report:
    n                    COUNT(DISTINCT decision_id)   -- never COUNT(*)
    WR                   wins / (wins + losses)
    W                    mean win in R
    gross_EV_R           WR·W − (1−WR)
    cost_R               H_bps / stop_bps, per row, then median
    net_EV_R             gross_EV_R − cost_R
    CI_lower             one-sided exact binomial lower bound at α = 0.05

Verdict law (unchanged estate law, restated so it is not re-litigated):
    An arm wins iff its CI lower bound exceeds BOTH
      (a) its OWN fee-net break-even  p_BE = (1 + cost_R)/(1 + RR), and
      (b) the certified null for that structure,
    walk-forward, per side, with the window declared in advance.

Paired comparison: arms share decision_id, so compare PAIRWISE, not as
independent samples. The correct test is McNemar on the paired win/loss
outcomes, not two-sample proportions. Using an unpaired test on paired data
overstates the variance and will hide a real effect.
```

## Tests

| # | Scenario | Expected |
|---|---|---|
| T1 | One candidate, three arms | exactly 3 shadow rows, same `decision_id`, **identical `stop_bps`** |
| T2 | Resting arm, price touches limit but does not trade through | `no_fill` |
| T3 | Market arm, same candidate | fills; `no_fill` **impossible** — assert the outcome enum has no such value for this arm |
| T4 | Aggregate query attempts to `SUM` across `cohort_tag` | **refused** — `NEVER_BLEND_VIOLATION` |
| T5 | Arm without `H_bps_entry_leg` | config load **fails** |
| T6 | Arm `PROPOSED_MUST_RATIFY` requested for money-eligibility | `BLOCKED_ON_RATIFY(<arm_id>)`; shadow accrual continues |
| T7 | Window closes; report generated | all four figures per arm; CI floors present; McNemar paired statistic present |
| T8 | Replay the same tape twice | byte-identical shadow rows |

## Acceptance

Three arms accruing in shadow. Zero blended aggregates possible. The 21-day report published with paired statistics. **No arm promoted to money-eligible without a signed ceremony.**

## Rollback

Delete the two proposed arms from the registry. `ENTRY_POST_ONLY_RESTING` is unchanged throughout — **the control arm is the current production behaviour, so there is nothing to roll back on the money path.**

---

# WO-C · ONE RR FLOOR, DERIVED FROM COST

**Closes:** `GAP-04`, `GAP-46` · **Severity:** `P0` · **Prerequisite:** `WO-E`

## The defect

Three layers, two values, no derivation:

| Layer | Floor | Source |
|---|---:|---|
| TriadEngine generation | **2.0** | `GROSS_RR_FLOOR`, compiled `LazyLock<Decimal>` |
| TriadOrigin F18 | **2.0** | RC2 §F18, *"RR floor fixed at 2.0"* |
| Executor governor admission | **2.5** | `per_trade.gross_rr_floor` |

**Generation frames at 2.0; admission demands 2.5. The engine manufactures candidates its own governor must reject** — and the `net_rr_floor` refusal count of **44** is that mismatch, printing.

## The fix — derive, do not pick

```
Neither 2.0 nor 2.5 is justified by anything. Both are constants.
Derive the floor from the cost model and the cell's demonstrated performance:

    Given  cost_R    = H_bps / stop_bps
    and    p_cell    = the cell's demonstrated win-rate CI LOWER bound
    and    MARGIN    = a declared safety margin in win-rate points

    Require:  p_cell  >=  p_BE + MARGIN
    where     p_BE    =  (1 + cost_R) / (1 + RR)

    Solve for the minimum admissible RR:

        RR_min  =  (1 + cost_R) / (p_cell − MARGIN)  −  1

All arithmetic exact rational. MARGIN is MUST_RATIFY, proposed 3/100.
```

**Worked example — verified:**

```
H = 9 bps, stop = 67 bps  ->  cost_R = 9/67
p_cell = 0.45 (CI lower bound), MARGIN = 0.03  ->  p_cell − MARGIN = 0.42

RR_min = (1 + 9/67) / 0.42 − 1 = (76/67)/(21/50) − 1
       = 3800/1407 − 1 = 2393/1407 ≈ 1.701

So a cell demonstrating a 45 % CI floor may lawfully trade at RR 1.70.
A cell demonstrating 35 % requires RR = (76/67)/0.32 − 1 ≈ 2.545.

THE FLOOR IS A FUNCTION OF DEMONSTRATED PERFORMANCE, NOT A CONSTANT.
A good cell earns a lower floor. A weak cell is held to a higher one.
```

## Enforcement — one layer decides, the other asserts

```
GENERATION (Engine / Origin F18):
    Frame geometry. Emit the exact rational RR as (num, den), UNREDUCED
    per F18's existing law — (4,2) not (2,1), because the magnitudes carry
    information. Apply NO floor. Generation must not know about cost
    (RC3 law 07). Emit everything and let admission decide.

ADMISSION (E07 / executor governor):
    THE ONLY layer that applies RR_min. Computes it per candidate from
    cost_model.v1 (WO-E) and the cell statistics.
    Refusal: REFUSED_RR_BELOW_DERIVED_FLOOR{rr, rr_min, cost_R, p_cell}

ASSERTION (both layers, CI):
    A test asserts that generation contains no RR floor constant at all.
    Static scan: FAIL the build if GROSS_RR_FLOOR is read in any
    generation module.
```

**Effect:** the 44 `net_rr_floor` refusals become either admissions (where the cell earns it) or refusals with a *reason a human can act on* — instead of a collision between two arbitrary constants.

## Tests

| # | Scenario | Expected |
|---|---|---|
| T1 | `cost_R = 9/67`, `p_cell = 0.45`, `MARGIN = 0.03` | `RR_min = 2393/1407` exactly, as a reduced rational |
| T2 | `p_cell − MARGIN <= 0` | `REFUSED_CELL_UNDEMONSTRATED` — no division by zero, ever |
| T3 | `p_cell = 0.35` | `RR_min ≈ 2.545`; a candidate at RR 2.5 is **refused** |
| T4 | Candidate RR exactly `RR_min` | admitted (inclusive boundary) |
| T5 | Candidate RR one integer cross-multiplication unit below | refused |
| T6 | Static scan finds `GROSS_RR_FLOOR` in a generation module | CI **fails** |
| T7 | `MARGIN` unratified | `BLOCKED_ON_RATIFY(RR_MARGIN)`; candidate goes to SHADOW only |
| T8 | Any float appears in the RR path | static scan **fails** |

---

# WO-D · RUN THE COMPARATOR

**Closes:** `GAP-48`, `GAP-50` · **Severity:** `P1` · **Prerequisite:** none

## Why this is nearly free

`control/comparator.py` already exists. It compares two labelled candidate streams at a matching input offset and classifies every divergence into a closed, fixed-precedence taxonomy:

```
divergence_record.v1 precedence — exactly one class wins per record:
  MISSING → EXTRA → RETIMED → REIDENTIFIED → GEOMETRY → LIFECYCLE
          → QUALITY → DOWNSTREAM_ELIGIBILITY

Two axes, never conflated:
  engine_cohort    ∈ {LEGACY_COMPARATOR, ORIGIN_CANDIDATE}
  intelligence_arm ∈ {DETERMINISTIC_CONTROL, INTELLIGENCE_TREATMENT}
```

**This is the instrument that settles the Engine-vs-Origin question, and it has never been pointed at a tape.** It needs no arming, no ratification, no venue access. Both streams are shadow.

## Steps

1. **Freeze one tape.** 30 days of E01-finalized bars across the traded universe. Record its digest. **Never re-cut it mid-comparison** — a changed tape invalidates every prior record.
2. **Run TriadEngine** over the tape → candidate stream tagged `LEGACY_COMPARATOR`.
3. **Run TriadOrigin** over the same tape → candidate stream tagged `ORIGIN_CANDIDATE`.
   Origin will refuse a great deal — F06, F08 and F17 all stand. **That is data, not failure.** Every refusal is a `MISSING` record with a named reason.
4. **Run the comparator.** Emit `divergence_record.v1` rows.
5. **Join to outcomes.** Resolve every record on the same tape and report:

```
For each divergence class:
    n
    Engine-only candidates  -> their realized outcome distribution
    Origin-only candidates  -> their realized outcome distribution
    Both, geometry differs  -> outcome under each geometry

The three questions that matter, answered directly:

  Q1. Do the EXTRA records (signals Engine emitted, Origin refused)
      have a WORSE outcome distribution than the agreed set?
      YES -> Origin's refusals are removing losers. Precision is real.
      NO  -> Origin is refusing at random. Its discipline costs coverage
             and buys nothing.

  Q2. Do the GEOMETRY divergences change realized R?
      Quantify in R, per structure, with the risk_denominator tagged
      (WO-A task A2).

  Q3. Which capsules can Origin actually produce?
      Expect: CAP-01 only, and under an ambiguous confirmation identity
      until F08 ratifies. Confirms or refutes GAP-39 empirically.
```

## Task D2 — establish the capsule mapping

`capsules.py` carries 5 semantic entry-convention IDs, bound by name and evidence, with the old ordinal mapping **explicitly refused rather than guessed**. That refusal is correct. But until a signed mapping to RC2's `CAP-01`…`CAP-05` exists, the comparator cannot align Origin candidates to engine detectors by semantic identity, and every comparison is by geometry alone.

**Deliverable:** a mapping table with evidence per row, unsigned, presented for ratification. **Do not guess a single row.** Where the evidence is insufficient, the row reads `UNRESOLVED_SEMANTIC_OWNER_REQUIRED` — evidence, never coverage.

## Acceptance

A `DIVERGENCE-REPORT-<tape_digest>.md` answering Q1, Q2 and Q3 with counts and outcome distributions. **This report is what converts "Origin is more precise" from an argument into a number.**

---

# WO-E · `cost_model.v1`

**Closes:** `GAP-02` · **Severity:** `P0` · **Prerequisite:** `WO-00` step 5

## Why `H = 9` cannot stay a constant

`H = 9 bps` currently appears as an estate constant with no schema, no signature, no per-symbol resolution, no VIP-tier input, and no revision. The Mission Control artifact literally hardcodes `let FEE = 9.0` in a display layer. **Under RC3 law 20 — *"Any NOT_RATIFIED consequential value resolves to SAFE_HOLD or DENY; implementers have no authority to invent a number"* — a hardcoded fee is an invented number.**

And every downstream quantity depends on it: `cost_R = H/stop_bps`, `MIN_STOP_WIDTH_BPS = H/MAX_COST_R`, `RR_min = f(cost_R, p_cell)`, `p_BE = (1+cost_R)/(1+RR)`.

## The contract

**File:** `contracts/schemas/cost_model.v1.json`

```json
{
  "schema": "triad/cost_model/1",
  "ratified_by": "PENDING",
  "metadata_revision": "<uint64>",
  "valid_from": "<utc>", "valid_to": "<utc>",
  "venue": "BINANCE_USDM",
  "account_scope": { "account_id": "<...>", "vip_tier": 0, "bnb_burn": false },
  "fee_bps_per_side": {
    "MAKER": { "num": 2,  "den": 1 },
    "TAKER": { "num": 5,  "den": 1 }
  },
  "spread_bps_by_symbol":   { "BTCUSDT": {"num": 1, "den": 2}, "...": "..." },
  "slippage_bps_by_symbol": { "BTCUSDT": {"num": 1, "den": 2}, "...": "..." },
  "signature": "<ed25519>"
}
```

**Every value is an exact reduced rational.** No floats, anywhere, ever.

## Resolution

```
resolve_H(venue, instrument, account, entry_role, exit_role, revision)
  -> Fraction | Refusal

  H_bps =   fee_bps_per_side[entry_role]
          + fee_bps_per_side[exit_role]
          + spread_bps_by_symbol[instrument]
          + slippage_bps_by_symbol[instrument]

  REFUSE cases — each named, none defaulted:
    model unsigned                  -> BLOCKED_ON_RATIFY(cost_model)
    instrument absent from a map    -> REFUSED_COST_UNKNOWN{instrument}
    revision mismatch vs the event  -> QUARANTINE_METADATA_REVISION
    now outside [valid_from,valid_to] -> REFUSED_COST_STALE
    entry_role or exit_role unknown -> REFUSED_COST_ROLE_UNKNOWN

  NEVER return a default. NEVER return zero. NEVER interpolate.
```

## The conservative-pairing rule — a real design decision, stated and justified

Under the PROTECTED STOP (`WO-02`), the exit **may** fill as maker or **may** escalate to market. Which one happens is unknowable at admission time.

```
For ADMISSION (WO-F), always charge the PESSIMISTIC pairing:
    entry_role = the arm's declared entry role
    exit_role  = TAKER, whenever the exit path can escalate to market

RATIONALE: admission is a fail-closed decision. If the true cost turns out
lower because the maker exit filled, the trade was better than admitted —
which is a safe direction to be wrong in. If admission assumed maker and the
rail fired, the trade was worse than admitted — which is the direction that
kills the account. Charge the worst case at the gate; measure the actual
liquidity role at settlement (F23 / outcome.v3 already carries it).
```

## Reference table — precomputed and verified

| entry / exit | `H_bps` | `cost_R` @ 45 | @ 67 | @ 120 |
|---|---:|---:|---:|---:|
| maker / maker | 4 | 0.0889 | 0.0597 | 0.0333 |
| maker / taker | 7 | 0.1556 | 0.1045 | 0.0583 |
| taker / taker | 10 | 0.2222 | 0.1493 | 0.0833 |

*(fees only; add per-symbol spread and slippage)*

## Tests

| # | Scenario | Expected |
|---|---|---|
| T1 | Unsigned model | `BLOCKED_ON_RATIFY(cost_model)` — no `H` returned |
| T2 | Unknown instrument | `REFUSED_COST_UNKNOWN` — **never** a universe default |
| T3 | maker/maker, spread 0, slip 0 | `H = 4` exactly, as `Fraction(4,1)` |
| T4 | taker/taker, spread 1/2, slip 1/2 | `H = 11` exactly |
| T5 | Revision mismatch | `QUARANTINE_METADATA_REVISION` |
| T6 | `valid_to` in the past | `REFUSED_COST_STALE` |
| T7 | Escalating exit path requested | `exit_role` forced to `TAKER`; asserted in test |
| T8 | Any float in the module | static scan **fails** |

---

# WO-F · THE E07 ADMISSION GATE

**Closes:** `GAP-01`, `GAP-03` · **Severity:** `P0` · **Prerequisite:** `WO-E`, `WO-C`
**Ratifies:** TBD-011

## Read this before building

**`CORRECTION-01` from the gap register applies here and changes the framing.** The live executor governor **already has** a working economic gate — `net_rr_floor` (44 refusals) and `stop_bounds.min_width_bps` (76 refusals, and it killed both of the estate's takes). **TRIAD Origin V7 has none.**

So this work order is **not** "invent a gate." It is **"port the gate that already works into E07, improve it with the cost model, and do not lose it in the migration."** Migrating to Origin as specified would remove the only working economic gate in the estate.

## The predicate

```
ADMIT(candidate, cost_model, cell_stats) -> ADMIT | REFUSE{code, evidence}

All arithmetic exact rational. All comparisons by cross-multiplication.

STEP 0 — derive stop_bps exactly
    stop_ticks = |E_ticks − S_ticks|
    REQUIRE E_ticks > 0            else REFUSE_CONFIG{NONPOSITIVE_ENTRY}
    REQUIRE stop_ticks > 0         else REFUSE_CONFIG{ZERO_RISK}
    stop_bps = Fraction(stop_ticks × 10000, E_ticks)    # ticks cancel, exact

STEP 1 — GATE: minimum stop width          [closes GAP-03]
    MIN_STOP_WIDTH_BPS = H_bps / MAX_COST_R          # DERIVED, not a constant
      MAX_COST_R : MUST_RATIFY, proposed 1/5
    Compare by cross-multiplication:  stop_bps >= MIN_STOP_WIDTH_BPS
    FAIL -> REFUSE{REFUSED_STOP_TOO_TIGHT, stop_bps, floor, H_bps, MAX_COST_R}

STEP 2 — GATE: derived RR floor            [WO-C]
    RR = Fraction(|T_ticks − E_ticks|, stop_ticks)
    RR_min = (1 + cost_R) / (p_cell − MARGIN) − 1
    FAIL -> REFUSE{REFUSED_RR_BELOW_DERIVED_FLOOR, rr, rr_min, cost_R, p_cell}

STEP 3 — compute the required win rate     [closes GAP-01]
    cost_R     = H_bps / stop_bps
    p_required = (1 + cost_R) / (1 + RR)

    IF p_required >= 1:
        The trade cannot win even at a 100 % win rate.
        REFUSE{REFUSED_FEE_UNVIABLE_IMPOSSIBLE, p_required}
        (This fires whenever cost_R >= RR. At stop=3bps, H=9, RR=2:
         cost_R = 3, p_required = 4/3 > 1. Guaranteed loss. Refuse instantly.)

STEP 4 — GATE: evidence
    IF cell_stats is NULL or cell_stats.n < MIN_CELL_N:
        REFUSE{BLOCKED_ON_EVIDENCE, cell_id, n}
        -> the candidate STILL GOES TO SHADOW with full lineage.
           It is not money-eligible. It is not discarded.
           This is how a new cell earns its way in.

    ELSE: one-sided exact binomial test, integer arithmetic only:
        H0: true win rate <= p_required
        p_value = SUM over k=wins..n of  C(n,k)·u^k·(v−u)^(n−k) / v^n
                  where p_required = u/v
        ADMIT iff p_value <= ALPHA          (MUST_RATIFY, proposed 1/20)
        FAIL -> REFUSE{REFUSED_CELL_UNDEMONSTRATED, wins, n, p_required, p_value}

ON EVERY REFUSAL:
    write the candidate to SHADOW with the full refusal record.
    NEVER drop. NEVER return None. NEVER log-and-continue.
    The refusal IS the measurement.
```

**Why the exact binomial and not a Wilson or normal interval.** Wilson requires a square root; the normal approximation requires a float. **Both violate the exact-arithmetic law.** The one-sided binomial sum is exact integer arithmetic over rationals — it needs big integers, but §1.2 explicitly permits unbounded integers in transient comparison arithmetic. Persist the *decision* plus a decimal-string rendering of the p-value at declared precision 30; do not attempt to store the raw numerator in an `int64`.

## Golden vectors — computed and verified. Implement against these exactly.

### `GV-ADM-01` — the canonical ADMIT

```
E_ticks = 100000 · S_ticks = 99550 · T_ticks = 101125 · H_bps = 9 · tick = 1

stop_ticks = 450 ·  tgt_ticks = 1125
stop_bps   = 450 × 10000 / 100000 = 45          exactly Fraction(45,1)
RR         = 1125 / 450 = 5/2                   exactly Fraction(5,2)
cost_R     = 9 / 45 = 1/5                       exactly Fraction(1,5)
p_required = (1 + 1/5) / (1 + 5/2) = (6/5)/(7/2)
           = 12/35                              = 34.2857 %

Evidence step, ALPHA = 1/20:
   wins=160 n=400 (40.00%)  p_value = 0.009826  -> ADMIT
   wins=153 n=400 (38.25%)  p_value = 0.053749  -> REFUSE  (just above alpha)
   wins=152 n=400 (38.00%)  p_value = 0.066054  -> REFUSE
   wins=150 n=400 (37.50%)  p_value = 0.097118  -> REFUSE
   wins=140 n=400 (35.00%)  p_value = 0.399970  -> REFUSE
```

**Note `wins=153` deliberately: `p_value = 0.0537` sits just above `α = 0.05`. This vector exists to catch an off-by-one in the summation bound (`k = wins` inclusive, not `wins+1`).**

### `GV-ADM-02` — stop too tight

```
E_ticks = 100000 · S_ticks = 99900 -> stop_ticks = 100
stop_bps = 100 × 10000 / 100000 = 10
MIN_STOP_WIDTH_BPS = 9 / (1/5) = 45
10 >= 45 FALSE -> REFUSE{REFUSED_STOP_TOO_TIGHT, stop_bps=10, floor=45}

(Had it passed: cost_R = 9/10 = 0.9 — nine tenths of the risk spent on fees.
 This is the geometry the shadow bank's 10 bps median is made of.)
```

### `GV-ADM-03` — the RR floor regression, made permanently detectable

```
Identical geometry, H = 9, stop = 45:
    RR = 5/2  ->  p_required = 12/35 = 34.2857 %
    RR = 2    ->  p_required =  2/5  = 40.0000 %
    delta = 5.7143 pp

Both vectors MUST be in the registry. Their existence makes the 2.5 -> 2.0
regression permanently detectable by test rather than by argument.
```

### `GV-ADM-04` — impossible trade

```
H = 9, stop = 3 bps, RR = 2
cost_R = 9/3 = 3
p_required = (1+3)/(1+2) = 4/3 > 1
-> REFUSE{REFUSED_FEE_UNVIABLE_IMPOSSIBLE, p_required=4/3}
   Refused at STEP 3, before any evidence lookup.
```

### `MIN_STOP_WIDTH_BPS` derivation table — verified

| `H_bps` | `MAX_COST_R = 1/10` | `1/5` | `1/4` |
|---:|---:|---:|---:|
| 4 | 40 | **20** | 16 |
| 9 | 90 | **45** ← the estate's current value | 36 |
| 12 | 120 | **60** | 48 |

**The estate's ratified 45 bps is exactly `H/MAX_COST_R` at `H=9`, `MAX_COST_R=1/5`. It was never arbitrary. Ratify the derivation and the value follows the fee model instead of decaying silently.**

## Tests

| # | Scenario | Expected |
|---|---|---|
| T1 | `GV-ADM-01` @ wins=160 | `ADMIT`; every intermediate matches the golden exactly as a `Fraction` |
| T2 | `GV-ADM-01` @ wins=153 | `REFUSE{REFUSED_CELL_UNDEMONSTRATED}`; `p_value = 0.053749` |
| T3 | `GV-ADM-02` | `REFUSE{REFUSED_STOP_TOO_TIGHT}` |
| T4 | `GV-ADM-03` both arms | `p_required` = `12/35` and `2/5` exactly |
| T5 | `GV-ADM-04` | `REFUSE{..._IMPOSSIBLE}` at step 3, **before** any cell lookup |
| T6 | `cell_stats = NULL` | `BLOCKED_ON_EVIDENCE`; **shadow row written**; assert it exists |
| T7 | `stop_bps` exactly equals floor | `ADMIT` (inclusive boundary) |
| T8 | `stop_bps` one integer unit below floor | `REFUSE` |
| T9 | `p_value` exactly equals `ALPHA` | `ADMIT` (inclusive) |
| T10 | Any float in the module | static scan **fails** |
| T11 | Every refusal path | a SHADOW row exists with full lineage. **Zero silent drops.** Assert by counting: `refusals_emitted == shadow_rows_written` |
| T12 | `MAX_COST_R` unratified | `BLOCKED_ON_RATIFY(MAX_COST_R)`; shadow accrual continues |
| T13 | 10⁵ random candidates | every one lands in exactly one terminal state; the union of states is exhaustive |

## Acceptance

All thirteen pass. `refusals_emitted == shadow_rows_written` holds over a 10⁵-candidate replay. The static no-float scan is a required CI stage. **The gate is wired into E07 and refuses in place until `MAX_COST_R`, `MARGIN`, `ALPHA` and `MIN_CELL_N` are ratified — at which point it becomes active without a code change.**

---

# REMAINING WORK ORDERS — SPECIFIED, LOWER PRIORITY

*These close real gaps and are fully scoped, but none is on the critical path to recovering the 13 pp. Build them after Track 2 reports.*

| WO | Closes | One-line spec |
|---|---|---|
| **WO-G** | `GAP-11` | **F10 predicates.** Replace the overlapping state block with mutually exclusive predicates: `TOUCHED : pen == 0` (edge contact), `PARTIAL : 0 < pen < 1/2`, `MIDPOINT_FILLED : 1/2 <= pen < 1`, `FILLED : pen == 1`. Verified against zone `[100,108]`: `p=108 → pen=0 → TOUCHED`; `p=107 → 1/8 → PARTIAL`; `p=104 → 1/2 → MIDPOINT_FILLED`; `p=100 → 1 → FILLED`. Add a property test asserting exactly one predicate true over 10⁵ random `pen`. |
| **WO-H** | `GAP-12` | **F13 extreme accrual.** Insert `(0.5) extreme := min(extreme, L_t)` — `max(extreme, H_t)` for SHORT — into `RECLAIM_PENDING`, before the tau check. The extreme accrues in **every** non-terminal state because it is a stop reference consumed by F18, not a phase-local variable. Test T9 becomes reachable. |
| **WO-I** | `GAP-13` | **F12 split identity.** While F08 refuses, emit under `ob.displacement_break.v2` with state `CONFIRMED_BY_BREAK`, its own registry row, trial family and cohort tag. **Must land before any CAP-01 shadow row is written** — rows accrued under an ambiguous identity can never be pooled with post-F08 rows. |
| **WO-J** | `GAP-06` | **RPI coverage clause.** RPI orders are excluded from `depth`, `bookTicker` and the depth streams, and RPI trades are excluded from `aggTrade` aggregation. F16 OFI and F17 tilt are therefore computed on a partial book; F15's coverage ratio reads complete while the population is not. Add `book_completeness ∈ {COMPLETE, RPI_EXCLUDED}` to every flow atom; fetch `GET /fapi/v1/rpiDepth` / `<symbol>@rpiDepth@500ms` where the measurement requires completeness; otherwise label the atom `RPI_EXCLUDED` and forbid exact maker-fill claims from it. RC3's `BOK-11` already states the correct posture — implement it. |
| **WO-K** | `GAP-17`, `GAP-18` | **Run the reconciler, once.** `last_reconcile_ts` is permanently null. Register P1 as a named predecessor blocking G6/G7. Record the thirteen incident orders' round-trip P&L, discriminated by market-sell timestamp: operator runbook flatten = compliant; incident-era close = unrecorded live round trip. |
| **WO-L** | `GAP-19`–`GAP-24`, `GAP-26` | **Bank repair.** Deploy the writer clock fix (`.2`); every time extraction by epoch integer arithmetic. Split the three resolvers into three tables or stop two. Dedup by identity — `COUNT(DISTINCT decision_id)` as the only lawful denominator. Run the batch resolver with checkpointing to price the bank beyond 0.39 %. Schedule `P-SKIP-B0` and `P-REJ-GOV` — 8,008 addressable rows exist and nothing is asking them anything. |
| **WO-M** | `GAP-25` | **`outcome.v3`.** Publish, dual-write v2+v3 through the window, cut readers over by signed supersession, retain v2 bytes. Golden: `6 − 1 + 0.2 + (−0.1) = 5.1` encodes as `{num:"51", den:"10"}`. |
| **WO-N** | `GAP-27`, `GAP-28` | **Wire the control surface.** `propose_action` appends JSONL and executes nothing (`proposals.py:3-6`). `live_eligible.rs` exists and is called from nowhere — needs R2 wiring, boot R11, and a 14k-row T13 replay. |
| **WO-O** | `GAP-29` | **Pin the prompt.** `prompt_pinned: false` ⇒ no resolvable render profile ⇒ corpus blocked ⇒ manifest never built ⇒ slot-B race never held. Prompt pinning is the root cause and the first unblock of the entire learning chain. |
| **WO-P** | `GAP-30`, `GAP-31` | **B00R root + source grant.** Four owner acts on a clean runner; then widen the milestone SOURCE grant to admit formula paths and pin the new files in `SOURCE_HASHES`. Unfreezes the whole merge chain. |
| **WO-Q** | `GAP-36`, `GAP-37` | **Credentials and the dead-man webhook.** Rotate every exposed class at the issuing side, record fingerprints only. Fill the three physical blanks — Auth0 tenant domain, pager chat ID, and the **dead-man second-channel webhook (standing P0, originated from an estate-went-dark-with-no-page event)**. |

---

# EXECUTION ORDER

```
DAY 0        WO-00   probe the box                     30 min · box operator
             WO-A    start the no_fill_win_share query  parallel · pure SQL

IF WO-00 RETURNS CONFIRMED_LIVE:
  DAY 0-3    WO-01   algo-order path                    P0 · stop everything else
  DAY 3-7    WO-02   PROTECTED STOP

WEEK 1       WO-A    publish the six-number reconciliation
             WO-D    freeze the tape, run the comparator

WEEK 2       WO-E    cost_model.v1
             WO-B    build the three entry arms, start shadow accrual

WEEK 3       WO-C    derived RR floor
             WO-F    E07 admission gate

WEEK 5       WO-B    21-day arm window closes -> paired report
             ---- THE DECISION POINT ----
             If market-at-signal beats resting by more than 3.2 pp
             (the fee-swap break-even), amend Law 14's entry half
             and promote the arm by ceremony.

THEN         WO-G, WO-H, WO-I   formula errata (WO-I before any CAP-01 accrual)
             WO-J .. WO-Q       in dependency order
```

## Two hard ordering rules

1. **`WO-00` runs before everything.** If protective stops have been failing with `-4120` since December, that changes the priority of every other line in this document.
2. **`WO-I` lands before the first CAP-01 shadow row.** Once rows accrue under an ambiguous trial identity, they can never be pooled with post-F08 rows. The evidence is permanently split, and no later work recovers it.

## What stays armed throughout

| Plane | State |
|---|---|
| SHADOW | **LIVE. Fixed. No OFF control.** Grows on every refusal added by this document. |
| Existing estate money path | **Armed.** Nothing here disarms it. Caps, kill, predicate and reconciler remain sovereign. |
| TRIAD Origin V7 venue path | `OFF` — never deployed. Nothing to disarm. |
| PAPER | `OFF` until keyless isolation is proven. |

Every mechanism in this document is a **gate that refuses one trade and records exactly why**, with the counterfactual preserved in SHADOW. None stops the engine or reduces the evidence rate. **They increase it.**

---

*Prepared 2026-08-13 · execution-grade · every golden vector computed and verified · posture unchanged `OFF/OFF/OFF/LIVE` · `shadow_activation = LIVE` fixed · no signature, pin, credential or receipt fabricated · runtime state `NOT_ATTESTED` this session*
