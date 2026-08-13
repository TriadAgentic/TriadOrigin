# TRIAD ORIGIN V7 — THE GAP REGISTER

**Document ID:** `TRIAD-ORIGIN-V7-GAP-REGISTER-2026-08-13`
**Version:** `1.0.0`
**Prepared:** 2026-08-13
**Disposition:** `GAP_INVENTORY / EVIDENCE / NOT_A_RATIFICATION / NO_RUNTIME_CHANGE`
**Companion:** `TRIAD_ORIGIN_V7_REPAIR_WORK_ORDER_2026-08-13.md` — every gap below with an ID maps to exactly one work order.

**Posture:** unchanged. `venue_environment=OFF · venue_activation=OFF · paper_activation=OFF · shadow_activation=LIVE` · `DENIED_SAFE_HOLD`. Nothing in this register disarms anything. The shadow plane is armed, live, and recording throughout, and every remedy proposed adds a gate rather than removing one.

---

## 0. How to read this register

A **gap** is something that must exist for the system to be correct, and does not exist. It is not an opinion about design.

Each gap carries:

| Field | Meaning |
|---|---|
| **ID** | `GAP-nn`. Stable forever. Never renumbered. |
| **Severity** | `P0` blocks money. `P1` blocks correctness or evidence. `P2` blocks completeness. |
| **Class** | `ECON` economics · `EXEC` execution/venue · `FORM` formula · `GOV` governance · `DATA` data/measurement · `OPS` operational |
| **State** | `ABSENT` nothing exists · `SPECIFIED_NOT_BUILT` spec exists, code does not · `BUILT_NOT_WIRED` code exists, nothing calls it · `BUILT_NOT_ATTESTED` claimed green, not independently verified · `WRONG` exists and is incorrect |
| **Evidence** | The exact source. Named, quotable, checkable. |
| **WO** | The work order that closes it. |

**Three states are deliberately distinguished and must never be collapsed.** A specification is not code. Code is not a wired call site. A wired call site is not an attested runtime. The estate's own law says so: *"Repository presence, a green local test, a merged PR, and runtime deployment are separate claims and require separate evidence."* Most of what follows is `SPECIFIED_NOT_BUILT`, and that is a completely different problem from `ABSENT`.

---

## 1. Summary — what is missing, in one table

| Tier | Count | What it is | Blocks |
|---|---:|---|---|
| **A · The economic hole** | 4 | No layer can refuse an unprofitable trade | Every money decision |
| **B · Venue reality drift** | 6 | The venue changed under the specification | Every protective stop, every flow measurement |
| **C · Formula defects** | 3 | Internal contradictions producing implementation-defined output | B04C, cross-implementer parity |
| **D · Execution mechanics** | 3 | Entry law contradicted by evidence; exit has an unbounded tail | G6, G7 |
| **E · Carried-forward estate debt** | 7 | Open estate P0/P1 that V7 does not know exist | G6, G7, all measurement |
| **F · Measurement plumbing** | 6 | The bank cannot answer questions asked of it | Every scorecard claim |
| **G · Governance closure** | 8 | Signatures, roots, grants, decisions | The merge chain |
| **H · Unbuilt by design** | 5 | Deferred parameters and phases | First light |
| | **42** | | |

**The one-sentence version.** The specification work is close to finished; the economic layer does not exist; the venue moved and nobody re-pinned it; and seven open estate defects did not cross into the new design.

---

## TIER A — The economic hole

*This tier is the reason the profit-engine score is 20/100. All four gaps are one problem seen from four sides.*

### GAP-01 · No fee-net admission predicate exists · `P0` · `ECON` · `ABSENT`

**What is missing.** A mechanism, at any layer, that computes whether a candidate's required win rate exceeds what its cell has demonstrated, and refuses it if so.

**Evidence.**
- RC3 non-negotiable law 07: *"Risk thresholds, leverage, stop floors, and portfolio budgets must never enter structure detection geometry."* E02 is constitutionally forbidden to check.
- RC3 §01 authority matrix, E07 row: *"Eligibility, **economic admission**, opportunity arbitration, arm identity, lifecycle coordination."* E07 is the assigned home.
- RC3 deferred register, **TBD-011**: *"E07 economic admission and opportunity arbitration policy · E07/Governance · Before treatment allocation."* **The policy is a TBD. It does not exist.**
- RC3 deferred register, **TBD-010** additionally defers *"Candidate TTL/departure/target and **cost-model parameters**."*
- F20 (E08) carries cost buffer `c` into `unit_loss = m·|E−S| + c`. It sizes correctly. It never rejects.
- F23 / `outcome.v3` (E10) computes net P&L exactly — after the fill.

**Why P0.** The estate's own `get_bank_priced` reports `breakeven_roundtrip_bps: 3.09` against a venue ladder of `zero 0.0 · pure maker 4.0 · Binance taker 9.0 · taker+spread+slip 12.0`. **Pure maker is already above break-even.** The system will produce a perfectly-lineaged record of losing trades, none of which were refused.

**WO:** `WO-02`

---

### GAP-02 · No cost model exists as a first-class, versioned, signed object · `P0` · `ECON` · `ABSENT`

**What is missing.** A `cost_model.v1` contract that resolves `H_bps` — the round-trip cost in basis points — for a given `(venue, instrument, account VIP tier, BNB-burn flag, entry liquidity role, exit liquidity role, metadata_revision)`, and refuses when any input is unknown.

**Evidence.** `H = 9 bps` appears as an estate constant with no schema, no signature, no per-symbol resolution, no VIP-tier input, and no revision. The Mission Control artifact hardcodes `let FEE = 9.0` in a display layer. Binance's published standard tier is 0.02% maker / 0.05% taker — so `H` should be a *function* of the fill mix, not a scalar.

**Why P0.** Every downstream number depends on it. `cost_R = H/stop_bps`; `MIN_STOP_WIDTH_BPS = H/MAX_COST_R`; `p_required = (1+cost_R)/(1+RR)`. A hardcoded `H` makes all three unversioned. And under RC3 law 20 (*"Any NOT_RATIFIED consequential value resolves to SAFE_HOLD or DENY; implementers have no authority to invent a number"*), a hardcoded fee **is** an invented number.

**WO:** `WO-01`

---

### GAP-03 · The 45 bps minimum stop width has no home in the V7 architecture · `P0` · `ECON` · `ABSENT`

**What is missing.** An E07 binding enforcing a minimum stop width, and the derivation that produces its value.

**Evidence.**
- Live ratified estate limit: `per_trade.min_stop_width_bps: 45` (`get_limits`).
- It is the filter that demonstrably works. Mission Control: *"Both stopped at check 6 (`stop_bounds.min_width_bps`): 6 bps zone-stop vs the fee floor."* Both of the estate's takes died on it.
- The shadow bank's own `median_stop_bps: 10.0` — **4.5× tighter than the floor** — which is exactly why its gross `+0.3093 R` becomes `−0.59 R`.
- RC3 law 07 forbids the floor from E02. **Nothing in the V7 set re-establishes it anywhere else.**

**Why P0.** Ship as specified and V7 admits precisely the geometry that produced `b0_net_total_r: −643 R`.

**Additional finding.** 45 is *derived*, not inherited: it is the width at which `cost_R = 9/45 = 1/5`. Ratifying the number instead of the derivation means the floor silently decays the moment the fee model changes. Reference table:

| `H_bps` | `MAX_COST_R = 1/5` | `1/4` | `1/10` |
|---:|---:|---:|---:|
| 4 (pure maker) | 20 | 16 | 40 |
| 9 (taker round trip) | **45** | 36 | 90 |
| 12 (taker + spread + slip) | 60 | 48 | 120 |

**WO:** `WO-03`

---

### GAP-04 · The RR floor moved 2.5 → 2.0 with no erratum · `P0` · `ECON` · `WRONG`

**Evidence.**
- RC2 §F18 formula card, parameters row: *"entry convention, invalidation buffer, target selector, **RR floor fixed at 2.0**."* Capsules restate: `F18 ≥ 2R`, `abstain when RR <2`.
- Live ratified estate limit: `per_trade.gross_rr_floor: 2.5`.
- No supersession record, no erratum, no measurement.

**The arithmetic.** `p_BE = (1 + c)/(1 + RR)`, `c = H/stop_bps`. At `H=9`, `stop=45`, `c = 1/5`:

| RR | `p_BE` | vs observed 34.3% shadow WR |
|---:|---:|---|
| 5/2 | **12/35 = 34.29 %** | break-even to marginally positive |
| 2 | **2/5 = 40.00 %** | decisively negative |

**+5.71 percentage points of required win rate on identical geometry and identical fees.** At pure maker (`H=4`) the penalty is still +5.19 pp.

**The fair counter-argument, recorded.** RR floor and win rate are not independent — a lower floor admits candidates a 2.5 floor rejects, and a nearer target may be more reliably reached. **The objection is not that 2.0 is wrong. It is that the change was silent, moves in the direction that demands more of the strategy, and has never been measured.**

**WO:** `WO-04`

---

## TIER B — Venue reality drift

*The venue changed. The specification did not. This tier was found by reading Binance's own change log against the V7 corpus, and it contains the single highest-severity operational finding in this register.*

### GAP-05 · Conditional orders migrated to the Algo Service; the operational layer never re-pinned · `P0` · `EXEC` · `SPECIFIED_NOT_BUILT`

**What changed.** Binance's derivatives change log, entry dated **2025-11-06, effective 2025-12-09**:

> USDⓈ-M Futures will migrate conditional orders to the Algo Service, affecting `STOP_MARKET` / `TAKE_PROFIT_MARKET` / `STOP` / `TAKE_PROFIT` / `TRAILING_STOP_MARKET`.
>
> New REST endpoints: `POST fapi/v1/algoOrder`, `DELETE /fapi/v1/algoOrder`, `DELETE fapi/v1/algoOpenOrders`, `GET /fapi/v1/algoOrder`, `GET /fapi/v1/openAlgoOrders`, `GET /fapi/v1/allAlgoOrders`.
>
> `POST /fapi/v1/order` and `POST /fapi/v1/batchOrders` **will block** those order types. Error `-4120 STOP_ORDER_SWITCH_ALGO`.
>
> New WebSocket user-stream event `ALGO_UPDATE`. New WebSocket API methods `algoOrder.place`, `algoOrder.cancel`.
>
> After migration: **no margin check before the conditional order gets triggered**; `GTE_GTC` orders no longer depend on opposite-side open orders but on positions only; **modification of untriggered conditional orders is not supported**.

Follow-on entries: **2025-12-10** — `CONDITIONAL_ORDER_TRIGGER_REJECT` deprecated effective 2025-12-15; rejection reasons now inside `ALGO_UPDATE`. **2025-12-29** — the `MAX_NUM_ALGO_ORDERS` filter was **removed** from `exchangeInfo`; the conditional-order limit is **200 across all symbols**.

**What the corpus says.** Credit where due: **RC3 knows.** Line 1428 reads *"Conditional STOP/TAKE_PROFIT families use the current Algo Service. E09 consumes and persists `ALGO_UPDATE` as well as regular order events, reconciles open regular and algo orders, and proves that protection remains armed. Acknowledgement alone is not protection truth."* RC3 carries 31 algo-order references, a `protection_event.v2` algo lifecycle (CHK-0336), and two named P0 fixtures (EXE-18 algo rejected after trigger, EXE-22 restart with open algo order).

**What is missing.**
1. **RC4 — the newest normative layer, the one that governs execution control — contains zero algo-order references.** The four-plane and lever law was written as if conditional orders still go through `/fapi/v1/order`.
2. **The Formula Repair Specification §E.2 (F21) and §E.3 (F22) contain zero.** GV-018's ladder and the emergency-IOC lifecycle are specified without the endpoint split.
3. **No document anywhere names** `POST /fapi/v1/algoOrder`, error `-4120`, the 200-order cap, "no margin check before trigger", or "modification of untriggered conditional orders is not supported."
4. **The live estate executor's endpoint usage is `NOT_ATTESTED`.** If it places protective stops through `/fapi/v1/order`, **every protection placement has been failing with `-4120` since 2025-12-09.**

**Why this is the highest-severity operational finding.** Protection placement is the difference between a bounded loss and an unbounded one. A silent `-4120` on every stop is a position with no stop. This must be probed on the box before anything else in this register.

**WO:** `WO-05` (probe, first action of the whole programme) and `WO-06` (implementation)

---

### GAP-06 · RPI orders are excluded from the depth and trade feeds F15/F16/F17 consume · `P1` · `DATA` · `SPECIFIED_NOT_BUILT`

**What changed.** Change log **2025-11-18**: RPI (Retail Price Improvement) orders were introduced to USDⓈ-M Futures with a new `RPI` time-in-force. Critically:

> **Order Book Exclusion** — RPI orders don't appear in `GET /fapi/v1/depth`, `GET /fapi/v1/ticker/bookTicker`, `ticker.book`, `<symbol>@bookTicker`, `!bookTicker`, `<symbol>@depth<levels>`, `<symbol>@depth`.
>
> New endpoints to fetch the RPI book: `GET /fapi/v1/rpiDepth`, `<symbol>@rpiDepth@500ms`.

And **2025-12-29**: *"Effective on 2025-12-31, field `nq` will be available in `<symbol>@aggTrade`. For this new field, only normal market trades will be aggregated, which means the trades involving RPI orders won't be aggregated."*

**What this breaks.**
- **F16 (`flow.ofi.best.v2`)** computes OFI from best-quote updates. Those updates exclude RPI liquidity. The OFI is therefore measured on a partial book, and the exclusion is not random — it is retail-flow-selective.
- **F17 (`flow.book_tilt.band.v2`)** sums banded depth from the local book. Same exclusion. The tilt is systematically biased by however much RPI liquidity sits inside the band.
- **F15 (`flow.tfi.window.v2`)** has a coverage law: `included_trades / expected_trades >= min_coverage else NULL{COVERAGE}`. If `expected_trades` derives from `aggTrade`, RPI trades are absent from the denominator too — so coverage will read as complete while the population is incomplete. **A silent measurement error, not a loud one.**

**What the corpus says.** RC3 has three RPI references, all in one fixture: **BOK-11** *"RPI-incomplete public depth simulation — Evidence plane is labeled **incomplete/approximate**; no exact maker-fill claim."* That is the correct posture and it is `NOT_RUN`. RC2 and RC4 have zero references. The Formula Repair Specification has zero — F15, F16 and F17 were all repaired without an RPI clause.

**WO:** `WO-07`

---

### GAP-07 · Legacy WebSocket base URLs were decommissioned 2026-04-23 · `P1` · `EXEC` · `SPECIFIED_NOT_BUILT`

**Evidence.** Change log **2026-03-05**: new base URL paths `/public`, `/market` for market streams and `/private` for user data streams. **2026-04-02**: *"Updated important websocket change notice with legacy URL decommissioning date: **2026-04-23**."*

RC3 carries one fixture — **DT11**, *"WebSocket migration conformance — Current Binance public/private base URLs and payload fields pass daily contract probes"* — status `NOT_RUN`. The 2026-08-08 forensic comparison lists *"Binance: 2026 WebSocket base-URL split and migration"* as a source. **So it is known and unverified.** The decommissioning date has passed.

**WO:** `WO-05` (probe)

---

### GAP-08 · `MIN_NOTIONAL` may be hardcoded rather than read from the venue filter · `P1` · `OPS` · `WRONG`

**Evidence.** The supplied ops guide states *"every entry is below Binance's **$20 minimum**"*. Binance's contract specification documents **5 USDT** and says the threshold *"will be adjusted from time to time without prior announcement — check proactively via API or the Contract Specifications page."* The `MIN_NOTIONAL` filter is published per symbol in `GET /fapi/v1/exchangeInfo` (change log 2021-01-26). The estate's own limits config carries `min_notional_quote: "5"`, matching the venue. **The `$20` appears in no primary source.**

**And the arithmetic does not reproduce the reported failure.** At ~$99.82 equity with `risk_pct_equity = 1.0`, risking $1.00 at a 45 bps stop gives `1.00 / 0.0045 = $222` notional; at the bank's 10 bps median stop it gives `$1,000`. Both clear 5 USDT comfortably. **Either the executor enforces a hardcoded constant — which RC3 law 20 forbids — or the sizing path does something described in no supplied document.**

**WO:** `WO-08`

---

### GAP-09 · Post-only rejections leave no venue trace, and no reconciliation rule covers it · `P1` · `EXEC` · `SPECIFIED_NOT_BUILT`

**Evidence.** Change log **2023-03-08**: when a `GTX` post-only order cannot be executed as maker it is *"rejected directly… no `order_trade_update` message in websocket. The order **can't be found in** `GET /fapi/v1/order` **or** `GET /fapi/v1/allOrders`."* Error `-5022`.

The Formula Repair Spec's GV-018 handles the **synchronous** case correctly (`EXEC_GTX_REJECTED`, one reprice unit consumed, re-evaluate from a fresh book). What is missing is the **asynchronous** case: if the client loses the HTTP response — timeout, disconnect, process death — the order is invisible in order history whether it was rejected or never sent. RC4's `UNKNOWN_SUBMIT_UNRECONCILED` names the state but no procedure resolves it for GTX specifically, where absence from `allOrders` is *expected on rejection* and therefore proves nothing.

**WO:** `WO-06`

---

### GAP-10 · Rate-limit and order-count budgets are unmodelled · `P2` · `EXEC` · `ABSENT`

**Evidence.** Constraints found in Binance documentation, none of which appear in any V7 contract: conditional-order limit **200 across all symbols** (2025-12-29); **10 open conditional orders per position**; **10,000 open orders** total; `-1008` throttling with the note *"Reduce-only/close-position orders are exempt"*; `-4116` duplicate `clientOrderId`; `-4117` *"Stop order is in triggering process, please try again later"*; `-4531` position-mode change rejected when CM has open positions/orders; `GET /fapi/v1/historicalTrades` reduced to **1 month** (2026-03-19) and `forceOrders` to **90 days** (2026-04-06).

The `-1008` exemption is materially useful: **reduce-only and close-position orders are exempt from system-level throttling**, which is a strong argument for the protective-stop design in `WO-06`.

**WO:** `WO-06`, `WO-08`

---

## TIER C — Formula defects

### GAP-11 · F10 FVG state predicates overlap · `P1` · `FORM` · `WRONG`

Formula Repair Spec §R-F10 states `FRESH -> TOUCHED (pen>0) -> PARTIAL (0<pen<1/2) -> ...`. **Any `pen` in `(0, 1/2)` satisfies both `TOUCHED` and `PARTIAL`.** Compounding it, test T4 contains unresolved authoring reasoning left inline — *"stays FRESH? — normative: … ratify: edge contact at z1 is TOUCHED with pen=0"* — which contradicts the state block in the same section. **WO:** `WO-09`

### GAP-12 · F13 `RECLAIM_PENDING` never updates the excursion extreme · `P1` · `FORM` · `WRONG`

The `EXCURSION` block carries `(1) extreme := min(extreme, L_t)`. `RECLAIM_PENDING` has no extreme-update step — yet test T9 requires *"extreme updates; retained through CONFIRMED."* Not cosmetic: §R-F13 makes `extreme` and `excursion_depth_ticks` **mandatory outputs consumed by F18 stop logic.** A wrong extreme is a wrong stop, on the money path. **WO:** `WO-10`

### GAP-13 · F12 confirms on `GENERIC_BREAK` while F08 refuses · `P1` · `FORM` · `WRONG`

§R-F12 confirms on *"a same-direction accepted F09 break occurrence"*. §R-F09 emits only `GENERIC_BREAK` — no BOS/CHOCH label — while F08 refuses (`PROTECTED_SWING_REDUCER_VERSION` `NOT_RATIFIED`, kept refusing by Part F item 6). So `ob.displacement_bos.v2` confirms on **any close through a frozen level**, not on breaks of structure. Under RC3 law 18 this is a **different trial family**; rows accrued before F08 ratifies can never be pooled with rows after. **WO:** `WO-11`

---

## TIER D — Execution mechanics

### GAP-14 · Law 14's maker-only entry mandate is contradicted by the estate's own measurements · `P1` · `EXEC` · `WRONG`

RC3 law 14 mandates post-only maker for **every normal entry and exit**, under a heading reading *"No implementer interpretation."* Three internal contradictions: (a) resting-limit entries measure ≈28% WR / negative EV vs market-at-signal ≈51.5% / positive EV, with the no-model control bleeding identically on the resting path; (b) RC4 §06's own audit — *"1,926 fills: 1,231 maker; 695 taker. Historical behavior violates a universal maker-only claim"* — **36% taker**; (c) at 4.0 bps pure maker the book still fails the 3.09 bps break-even, so maker-only does not rescue the edge even in the limit. **WO:** `WO-12`

### GAP-15 · The exit path has an unbounded tail and no ratified escalation · `P0` · `EXEC` · `ABSENT`

Law 14 makes post-only maker the *normal* exit. A post-only stop that does not fill as maker **does not fill**, while the position keeps moving. EXIT-MECH-01 is registered but unratified and unimplemented: taker cost on the stop leg of losers is bounded at ~0.04–0.1 R; maker-stop failure is unbounded. **WO:** `WO-06`

### GAP-16 · No entry-mechanism experiment structure exists · `P1` · `EXEC` · `ABSENT`

There is no cohort structure, no arm registry, and no per-arm `H_bps` that would let the estate answer "which entry mechanism is best" with evidence rather than a constitutional prohibition. **WO:** `WO-12`

---

## TIER E — Carried-forward estate debt

*Seven open estate conditions. A full-text search across all seven uploaded V7 documents returns **zero** references to any of them.*

| ID | Gap | Sev | Evidence | WO |
|---|---|---|---|---|
| **GAP-17** | **The reconciler has never run.** `last_reconcile_ts` permanently null. Mission Control renders venue `RED`: *"the reconciler has never run — local state has never been compared to a venue."* V7 law 10 and RC4's `UNKNOWN_SUBMIT_UNRECONCILED` both make reconciliation a precondition for classification — a reconciler that has never run cannot satisfy either. | `P0` | `get_positions`/venue projection | `WO-13` |
| **GAP-18** | **Thirteen incident orders carry unrecorded round-trip P&L** (5 ETH, 4 BNB, 4 BTC, all buys, 2026-07-11/12 window). Discriminator is the market-sell timestamp: operator runbook flatten = compliant; incident-era close = unrecorded live round trip. | `P0` | P1 incident record | `WO-13` |
| **GAP-19** | **Two-clock contamination writer fix not deployed.** Bank mixes `−07:00` and `+00:00` stamps; fresh rows still stamp `−07:00`. Any weekday or hour cut is unlawful until both reader and writer fixes land. All time extraction must use epoch integer arithmetic: `uh = FLOOR(((ts/1e6)::BIGINT % 86400)/3600)`. | `P1` | D-CLOCK-01 | `WO-14` |
| **GAP-20** | **Three resolvers write one table.** `triad-cf/1` declares one; first-touch, confirm-first-touch and ladder/trail all write. One `decision_id` carries `["loss","win","loss"]` with `pnl_r [−1.0, +1.3551, −1.0]`, **summed** into `net_pnl_r`. | `P1` | `get_resolver_registry` mismatch | `WO-14` |
| **GAP-21** | **2.93× row inflation.** 8,008 rows over 2,731 distinct decisions. Every CI computed on the bank is narrow by √2.93 ≈ 1.71×. `disagreement_rate` is *"the number nobody has."* | `P1` | `get_bank_dedup` | `WO-14` |
| **GAP-22** | **Bank is ~0.39% priced.** ~2.3M accepted rows, ~0.39% resolved. The historical scorecard is missing not for lack of samples but because the backfill resolver has barely run. | `P1` | Bank state | `WO-14` |
| **GAP-23** | **`F4 liq_flush` is writer-missing.** The code path exists per manifest; the bank column is NULL on all rows. Liquidation rows exist in the UpONLY bank; TRIAD's own bank has no writer landing data. | `P2` | Bank column scan | `WO-14` |

---

## TIER F — Measurement plumbing

| ID | Gap | Sev | State | WO |
|---|---|---|---|---|
| **GAP-24** | **Synthesised geometry.** Every RR in the bank is exactly 2.50 because `TP = entry ± 2.5 × (SL − entry)`. The `+988 R` is *"the P&L of a trade plan no component of this system ever proposed."* V7's F18 fixes this at spec level; nothing has replayed the bank under real geometry. | `P1` | `SPECIFIED_NOT_BUILT` | `WO-14` |
| **GAP-25** | **Zero-fee bank.** The bank prices nothing. `outcome.v3` (CO-04) is a DRAFT schema artifact; publication, dual-write v2+v3, and reader cutover are all unbuilt. | `P1` | `SPECIFIED_NOT_BUILT` | `WO-15` |
| **GAP-26** | **Six personas at n=0.** `P-SKIP-B0`, `P-REJ-GOV`, `P-NOFLOOR`, `P-LOWCONV-40`, `P-MIRROR`, `P-MISSED-TOUCH`. 8,008 addressable rows already exist; `blocked_on: "the personas have never been scheduled."` Two of them — *"was the model right to skip?"* and *"what did each refusal cost?"* — could run today. | `P1` | `BUILT_NOT_WIRED` | `WO-14` |
| **GAP-27** | **`propose_action` executes nothing.** Mission Control's action path appends JSONL and does nothing else (`proposals.py:3-6`). The control surface is decorative. | `P1` | `WRONG` | `WO-16` |
| **GAP-28** | **`live_eligible.rs` is wired nowhere.** The predicate exists in TriadExecutor, is safe to ship disarmed, and no call site references it. Needs R2 wiring, boot R11, and a 14k-row T13 replay. | `P1` | `BUILT_NOT_WIRED` | `WO-16` |
| **GAP-29** | **The learning corpus cannot be built.** `prompt_pinned: false` ⇒ decisions carry no resolvable render profile ⇒ corpus construction is blocked ⇒ the corpus manifest has never been built ⇒ the slot-B race has never been held. Prompt pinning is the root cause and the first unblock. | `P1` | `ABSENT` | `WO-17` |

---

## TIER G — Governance closure

| ID | Gap | Sev | Detail | WO |
|---|---|---|---|---|
| **GAP-30** | **B00R root closure.** Four owner acts: authenticate the three `-002` decisions, externally pin the g2 trust registry, install the no-bypass `main` ruleset, threshold-sign receipt-v3 → `B00R_RECEIPT_ANCHOR_G2`. Until then B01C stays frozen and the whole milestone chain is blocked. | `P0` | Templates exist and fail closed | `WO-18` |
| **GAP-31** | **The milestone SOURCE grant excludes formula paths.** `tools/classify_milestone_pr.py` will classify every formula-repair milestone PR as out-of-scope against `main`. | `P0` | Owner-reviewed PR + `SOURCE_HASHES` pin | `WO-18` |
| **GAP-32** | **Eight owner blocking decisions + three research sentinels.** `PAR-070`, `PAR-072`, `PAR-076`, `PAR-077`, `PAR-118`, `PAR-119`, `PAR-120`, `PAR-121`; plus `EQUAL_LEVEL_MAX_SPAN` (F06), `BOOK_TILT_MIN_QUOTE_DEPTH` (F17), `PROTECTED_SWING_REDUCER_VERSION` (F08). Each `NOT_RATIFIED` with an explicit `SAFE_HOLD` consequence. | `P0` | Blocks G7 and G9 | `WO-19` |
| **GAP-33** | **98 binding rows are migration-blocked.** Zero rows may remain in `BLOCKED_BINDING_V2_MIGRATION`. A formula activates only when its **entire** set is ACTIVE — F21's 1-of-10 must never present as active. | `P1` | CO-07 worksheets exist | `WO-19` |
| **GAP-34** | **28 TBDs open**, of which TBD-004…TBD-011, TBD-020, TBD-021 and TBD-022 gate every edge parameter, the economic admission policy, the optional-stopping boundary, the power calculation, and the final net-EV/DSR/PBO thresholds. | `P0` | Deliberate; see Tier H | `WO-19` |
| **GAP-35** | **CO-14 topology decision file never received.** `TOPOLOGY-DECISION-E03-E05-E06.md` is a reserved slot. The E03–E06 contract bodies cannot land without it. | `P2` | Reserved | — |
| **GAP-36** | **Three physical blanks unfilled.** Auth0 tenant domain (blank ①), pager Telegram chat ID (blank ②), **dead-man second-channel webhook URL (blank ③ — standing P0)**. The dead-man webhook originated from an estate-went-dark-with-no-page event. | `P0` | Physical values only the owner holds | `WO-20` |
| **GAP-37** | **Credential rotation not performed.** Confirmed: credential-shaped material exists in four supplied ops guides — `TRIAD-Operator-MCP-Reference.md` (6 lines), `TRIAD-Redeploy-Guide-for-Liko.md` (2), `TRIAD-Market-Data-MCP-Guide.md` (1), `TRIAD-Ops-Control-Guide.md` (1). **No value was read or copied — only counted.** Under the CO-10 golden rule these classes are EXPOSED. | `P0` | Blocks B05C | `WO-20` |

---

## TIER H — Unbuilt by design

*These are not defects. They are deliberate, and three of them are among the best decisions in the corpus. They are listed because they are the reason first light is far away, and because "deliberate" and "done" are different.*

| ID | Item | Why deliberate | Consequence |
|---|---|---|---|
| **GAP-38** | **Every edge parameter is unset.** TBD-004 (DC δ families), TBD-005 (break buffer), TBD-006 (FVG `g_min`, displacement, touch source, TTL), TBD-007 (OB `W/D/H`, zone, quality, mitigation), TBD-008 (excursion `e, r, τ, n`), TBD-009 (flow horizons/thresholds/TTL) — each due *"before capsule result access."* | **This is the single best anti-overfitting decision in the estate's history.** It directly answers the forensic comparison's warning that tuning against the same 225,133 overlapping shadow rows is the wrong first move. | The engine currently has **no specified edge**. The honesty and the emptiness are the same choice. |
| **GAP-39** | **Three of five capsules cannot fire.** CAP-03 blocked on F06; CAP-04 blocked on F08 (F09 emits `GENERIC_BREAK` with no CHOCH label, ever); CAP-02 blocked on F17 or needs a ruling that tilt is advisory; CAP-05 depends on E01-owned F07. Only CAP-01 runs cleanly — and `order_block` is the estate's most trustworthy **negative** finding (−0.13 to −0.22 R), while `fvg_retest` (CAP-02) is its only positive one (+0.08 to +0.12 R). | Dependency-true with respect to formulas. | **Evidence-blind with respect to edges.** The repair set makes the negative-prior capsule runnable and leaves the positive-prior capsule gated. |
| **GAP-40** | **1,250 ledger rows `NOT_STARTED`.** B08 read faces, B09 conformance/runbooks, B10 audits/seal all unimplemented. G-1 through G9 all open. | Correct dependency ordering. | Time to first evidence is measured in months, not weeks. |
| **GAP-41** | **WAVE-C-001 canonical identity migration unclosed.** Additive `fill.v3`, dual-publish, reconciliation, signed supersession, consumer cutover. A VERSION bump and manifest re-pin alone are insufficient. | Highest cross-estate dependency; correctly sequenced first. | Blocks B-003/B-006 measurement and all downstream outcome work. |
| **GAP-42** | **The two-bot problem.** The designed TG-01 broadcaster (TriadRelay, correct post-governor tap) is not the live bot; the group's feed still comes from `tools/triad_telegram_signals.py` (TriadLearning, **pre-governor** tap). D-2 closes only when the live feed switches. | Known and registered. | The signals people see are not the signals the governor approved. |

---

## 2. What is *not* missing — the honest other half

An inventory that lists only holes misrepresents the work. These are verified present and correct, and each one is better than anything in the six-engine forensic corpus.

| Verified | Evidence |
|---|---|
| **Causal integrity** | Availability law §1.4; five separate time fields (law 02); forming bars excluded (law 04); centered pivots available only after the right window closes (law 05); append-only revisions; restart-parity tests on every stateful formula. |
| **Every golden vector** | GV-F16-01 (OFI +7, normalized 21/20), GV-013 (2/5 vs 1/13 unit pair), F20 (0.961), F22 (9990/10010), F23 ({51,10}), GV-018 (0..4 ladder budget), GV-F05-01 — **all seven recomputed by hand; all reproduce exactly.** |
| **F16 literature provenance** | The event equation matches Cont, Kukanov & Stoikov (JFE 12(1), 2014) term for term. The claim *"exact CKS — literature-verified"* is true. |
| **Plane separation** | RC4 is exemplary. `shadow_activation` fixed LIVE with no OFF control; `SHADOW_CAPTURE_OFF_FORBIDDEN`; 38 named refusals; never-blend enforced structurally rather than by convention. |
| **The security fix** | Part C.1's content-addressed `SealedBundle` v2 is the correct fix for a real P0 — *"a Python object is never a security boundary"* — with an adversarial suite covering subclassing, pickle, module reload and scope widening. |
| **The F13 direction trap** | Test T10 — feed the LONG stream to the SHORT machine, expect nothing — wired into CI as a named regression so the reversed-direction bug cannot recur silently. |
| **Refusal discipline** | Typed refusals throughout; `BLOCKED_ON_RATIFY(<param>)`; presence ≠ closure; CI greps that fail the build on overclaim strings; four distinct unresolved states with no bare `unknown` permitted. |

---

## 3. Dependency graph — what must happen before what

```
WO-05  PROBE the box (algo endpoints, WS URLs, MIN_NOTIONAL, sizing path)
  │      ── nothing else is trustworthy until this returns
  │
  ├─► WO-06  PROTECTED STOP + algo-order path          [GAP-05,09,10,15]
  │
  └─► WO-08  venue-filter resolution                    [GAP-08,10]

WO-01  cost_model.v1                                    [GAP-02]
  │
  ├─► WO-02  E07 admission gate                         [GAP-01]
  ├─► WO-03  MIN_STOP_WIDTH derivation                  [GAP-03]
  └─► WO-04  RR floor reconciliation                    [GAP-04]

WO-09  F10 predicate fix     ─┐
WO-10  F13 extreme accrual   ─┼─► B04C can land         [GAP-11,12]
WO-11  F12 split identity    ─┘   must precede any CAP-01 accrual [GAP-13]

WO-07  RPI coverage clause                              [GAP-06]
WO-12  entry-mechanism arms                             [GAP-14,16]
WO-13  reconciler first run + P1 closure                [GAP-17,18]
WO-14  bank repair (clock, resolver, dedup, pricing)    [GAP-19..24,26]
WO-15  outcome.v3 publication + dual-write              [GAP-25]
WO-16  wire the control surface                         [GAP-27,28]
WO-17  prompt pinning → corpus                          [GAP-29]
WO-18  B00R root + source grant                         [GAP-30,31]
WO-19  binding adjudication + TBD closure               [GAP-32,33,34]
WO-20  credentials + dead-man webhook                   [GAP-36,37]
```

**Two hard ordering rules.**
1. **`WO-05` runs first, before any other work.** If protective stops have been failing with `-4120` since December, that fact changes the priority of everything else in this register.
2. **`WO-11` must land before any CAP-01 shadow row is written.** Once rows accrue under an ambiguous trial identity they can never be pooled with post-F08 rows, and the evidence is permanently split.

---

*Prepared 2026-08-13 · independent gap inventory · 42 gaps · posture unchanged `OFF/OFF/OFF/LIVE` · `shadow_activation = LIVE` fixed · no runtime change · runtime state `NOT_ATTESTED` this session · evidence, not authority*

---
---

# ADDENDUM A — Engine teardown intake · 2026-08-13

**Source:** `engine-vs-origin.html` (signal-generation teardown, source-read 2026-08-13) plus the operator's live report: *"engine is not so profitable, barely profitability borderline losing."*

**Why this addendum exists.** The teardown supplies the engine's frozen performance baseline. The operator supplies live ground truth. **They do not agree, and the size of the disagreement is exactly the size of the business.** Reconciling them produces the sharpest diagnosis in this register and reorders the entire work programme.

---

## A.1 · The reconciliation — where the money goes

**The frozen claim.** The teardown records the engine's baseline as *"`fvg_retest` frozen at 54.4% win rate / +0.533R on real tape — a number, not a proof."* The methodology section is explicit that this figure is *"the frozen `fvg_retest` baseline recorded in its own source"* — a constant in the codebase, not a live measurement.

**Step 1 — back out the realized reward.** `EV = WR·W − (1−WR)·1` where `W` is average win in R:

```
0.533 = 0.544·W − 0.456
W = (0.533 + 0.456) / 0.544 = 1.8180 R
```

**The engine's realized average win is 1.818R, not 2.0R.** The `GROSS_RR_FLOOR = 2.0` is a floor on *framing*, not a description of *outcomes* — targets are missed, time-exits happen, and partials close early. Any statement of the form "we run 2R" is a statement about the order, not the fill.

**Step 2 — break-even at the engine's own stop band.** `p_BE = (1 + H/stop_bps)/(W + 1)` at `W = 1.818`:

| Stop | `H = 9 bps` | `H = 4 bps` (maker) | `H = 10 bps` (taker) |
|---:|---:|---:|---:|
| 67 bps | **40.25 %** | 37.60 % | 40.78 % |
| 120 bps | **38.15 %** | — | — |
| 45 bps | 42.58 % | — | — |
| 10 bps *(the bank's median)* | **67.42 %** | — | — |

**Step 3 — locate "borderline."** Net EV by realized win rate, at `H = 9 bps`:

| Realized WR | net @ 67 bps | net @ 120 bps | Verdict |
|---:|---:|---:|---|
| 54.4 % *(frozen)* | +0.399 R | +0.458 R | strongly positive |
| 45 % | +0.134 R | +0.193 R | positive |
| **42 %** | **+0.049 R** | +0.109 R | **borderline** |
| **40 %** | **−0.007 R** | +0.052 R | **borderline** |
| 38 % | −0.064 R | −0.004 R | losing |
| 35 % | −0.148 R | −0.089 R | losing |

**The operator's report — "barely profitable, borderline losing" — corresponds to a realized win rate of 38–42 %.**

### GAP-43 · Roughly 13 percentage points of win rate do not survive contact with live execution · `P0` · `ECON`

```
frozen baseline WR ...... 54.4 %
break-even WR ........... 38.2 – 40.3 %   (its own stop band, H = 9 bps)
implied realized WR ..... 38 – 42 %       (from the operator's report)

MARGIN OF THE BUSINESS .. 14.1 – 16.2 pp
SURVIVING ............... 0 – 3.8 pp
LOST IN TRANSLATION ..... ~12.4 – 16.4 pp
```

**This is the whole problem, stated as one number.** Every other economic gap in this register is a contributor to it.

**WO:** `WO-A` (diagnosis), `WO-B` (the fix)

---

## A.2 · The mechanism — `no_fill` is not a neutral outcome

### GAP-44 · The counterfactual scores only the filled subset, and the filled subset is adversely selected · `P0` · `DATA` · `WRONG`

**The bank's own outcome mix** (`get_shadow_bank`, 8,008 rows):

| Outcome | n | Share of all rows |
|---|---:|---:|
| `win` | 1,482 | 18.5 % |
| `loss` | 1,522 | 19.0 % |
| **`no_fill`** | **2,617** | **32.7 %** |
| `gap` | 2,195 | 27.4 % |
| `expired` | 192 | 2.4 % |

- WR among resolved (`win`/(`win`+`loss`)) = **49.33 %**
- **`no_fill` is 46.6 % of everything that could have been filled** (`win` + `loss` + `no_fill`).

**Nearly half of all fillable opportunities never filled — and they are excluded from the win-rate denominator entirely.**

**Why this is not survivorship noise but a directional bias.** For a *resting limit entry*, fill and outcome are causally coupled in one direction: you get filled when price comes to you and keeps going, and you do not get filled when price turns at your level and runs to target without you. **The trades that would have won are systematically over-represented in `no_fill`.** This is textbook adverse selection and it is the estate's own already-documented "short disease" — resting entries ≈ 28 % WR, confirmed ≈ 46 %, market-at-signal ≈ 51.5 %, with the no-model geometry control bleeding identically on the resting path.

**Sensitivity — how much of the gap this alone explains:**

| If this share of `no_fill` would have won | True opportunity WR | Reported WR on filled subset |
|---:|---:|---:|
| 0 % | 26.4 % | 49.33 % |
| 20 % | 35.7 % | 49.33 % |
| **35 %** | **42.7 %** | 49.33 % |
| 50 % | 49.6 % | 49.33 % |
| 65 % | 56.6 % | 49.33 % |

At a 35 % win share among `no_fill` rows the true opportunity WR is 42.7 % — **exactly the borderline band.** The counterfactual reports 49.33 % because it never scores the ones that got away.

**`disagreement_rate` is not the only number nobody has. `no_fill_win_share` is the other one, and it is more important.**

**WO:** `WO-A`

---

## A.3 · The intervention — this is the highest-ROI change available

### GAP-45 · The maker-only entry law is the largest single identified destroyer of EV · `P0` · `EXEC` · `WRONG`

Binance USDⓈ-M standard tier is 2 bps maker / 5 bps taker per side. Round trips: maker/maker **4 bps**, maker-in/taker-out **7 bps**, taker/taker **10 bps**.

**How much win rate must taker entry buy to pay for itself?** The extra 6 bps, divided by `(W + 1) = 2.818`:

| Stop | Extra cost | In win-rate terms |
|---:|---:|---:|
| 67 bps | 0.0896 R | **3.18 pp** |
| 120 bps | 0.0500 R | **1.77 pp** |

**The measured gap between resting entry (28 %) and market-at-signal (51.5 %) is 23.5 pp.**

```
COST of switching to taker entry ....... 3.2 pp  (67 bps)  /  1.8 pp  (120 bps)
BENEFIT measured by the estate ......... 23.5 pp
MARGIN OF SAFETY ....................... 7×  to  13×
```

**Net EV by entry mechanism**, at `W = 1.818R`:

| Mechanism | WR | `H` | net @ 67 bps | net @ 120 bps |
|---|---:|---:|---:|---:|
| resting maker, live-observed | 40 % | 4 | +0.068 R | +0.094 R |
| resting maker, optimistic | 42 % | 4 | +0.124 R | +0.150 R |
| confirmed entry *(measured)* | 46 % | 7 | +0.192 R | +0.238 R |
| **market-at-signal, pessimistic** | 45 % | 10 | **+0.119 R** | **+0.185 R** |
| **market-at-signal, conservative** | 48 % | 10 | **+0.203 R** | **+0.269 R** |
| **market-at-signal *(measured)*** | 51.5 % | 10 | **+0.302 R** | **+0.368 R** |

**Even the pessimistic case — assuming market-at-signal delivers only 45 % rather than the measured 51.5 % — beats the current resting path by 1.8× to 2.0×.** The break-even win rate rises only from 37.60 % to 40.78 % when you switch from pure maker to pure taker.

**This is the single change with the best evidence-to-effort ratio in the entire estate.** It requires no new detector, no new formula, no ratification of an edge parameter. It is a change to how an already-measured signal is entered.

**WO:** `WO-B`

---

## A.4 · Two corrections to this reviewer's own prior findings

*Recorded because the estate's convention is that a mid-work correction is a first-class finding, and because both corrections make the register more accurate rather than less alarming.*

### CORRECTION-01 · The estate **does** have a fee-net gate. Origin V7 is a regression against it.

**My earlier claim** (audit §04, GAP-01): *"There is no layer at which a trade is refused for being unprofitable."*

**That was too strong, and the correct version is worse.** The live executor governor runs 14 checks, and the recorded refusal histogram shows:

| Check | Refusals |
|---|---:|
| `stop_bounds` (`min_width_bps` = 45) | 76 |
| `ttl_bounds` | 49 |
| **`net_rr_floor`** | **44** |
| `stop_distance` | 44 |
| `zone_not_subset` | 21 |
| `schema_parse` | 15 |

**`net_rr_floor` is a fee-net admission gate, it exists, and it fires.** So does the 45 bps stop-width floor — it killed both of the estate's takes.

**The accurate finding:** the *live estate* has an economic admission gate that works. **TRIAD Origin V7 has none** — RC3 law 07 bars it from E02, and TBD-011 leaves E07's version unspecified. **V7 is therefore a regression against the running system on precisely the dimension that decides profitability.** Migrating from Engine to Origin as specified would *remove* the only working economic gate in the estate.

This does not soften GAP-01, GAP-02 or GAP-03. It sharpens them: the work is not "invent a gate" but "port and improve the gate that already exists, and do not lose it in the migration."

### CORRECTION-02 · The estate runs two different RR floors simultaneously

**My earlier claim** (audit §05, GAP-04): *"F18's RR floor of 2.0 is below the estate's ratified 2.5."* True, but incomplete.

**The full picture, from three sources:**

| Layer | RR floor | Source |
|---|---:|---|
| TriadEngine generation | **2.0** | `GROSS_RR_FLOOR`, compiled `LazyLock<Decimal>` from `limit_config` |
| TriadOrigin F18 | **2.0** | RC2 §F18 card, *"RR floor fixed at 2.0"* |
| Executor governor admission | **2.5** | `get_limits` → `per_trade.gross_rr_floor` |

**Generation frames at 2.0. Admission demands 2.5. The engine therefore manufactures candidates its own governor is contractually obliged to reject** — and the `net_rr_floor` refusal count of 44 is that mismatch, printing.

### GAP-46 · Generation/admission RR floor mismatch · `P0` · `ECON` · `WRONG`

Fixing this is not "pick 2.0 or 2.5." Both floors are currently unjustified constants. The correct fix is **derive the floor from the cost model** — `RR_FLOOR` such that `p_BE` sits a declared margin below the cell's demonstrated win rate — and enforce **one** value at **one** layer, with the other layer asserting rather than duplicating. See `WO-C`.

### GAP-47 · The engine reports R against two different denominators · `P1` · `DATA` · `WRONG`

The teardown records: stop at `mid − b`, invalidation at `mid − b − b/2` (1.5×`b`), target at `mid + 2.0×b`. It then states *"RR is ~1.67 vs the stated invalidation, ≥2.0 vs the stop."*

**Two risk denominators exist in one geometry, and every `R` figure in the estate is ambiguous until it declares which one it used.** `1.818R` realized, `+0.533R` frozen, `−0.59R` bank-net, `−643R` total: none of these carry a denominator tag. Under the never-blend law these are not comparable numbers. **WO:** `WO-A`

---

## A.5 · Further gaps from the teardown

### GAP-48 · The comparator is built and has never been run · `P1` · `DATA` · `BUILT_NOT_WIRED`

`control/comparator.py` compares two labelled candidate streams at a matching input offset and classifies every divergence into a closed, fixed-precedence taxonomy: `MISSING → EXTRA → RETIMED → REIDENTIFIED → GEOMETRY → LIFECYCLE → QUALITY → DOWNSTREAM_ELIGIBILITY`, with two never-conflated axes — `engine_cohort ∈ {LEGACY_COMPARATOR, ORIGIN_CANDIDATE}` and `intelligence_arm ∈ {DETERMINISTIC_CONTROL, INTELLIGENCE_TREATMENT}`.

**This is the instrument that settles the entire Engine-vs-Origin question, it is written, and it has never been pointed at a tape.** The teardown says so itself: *"the only way to know that number is to run them side by side, which is exactly what the comparator does."*

It requires no arming, no ratification, no venue access — both streams are shadow. **It is the cheapest high-value action in this register.** **WO:** `WO-D`

### GAP-49 · Three stop regimes coexist in one estate · `P1` · `ECON` · `WRONG`

| Regime | Value | Where |
|---|---|---|
| Engine band floor | **67–120 bps**, single-sourced into `band_of`; *"changing it is a full detector re-launch (new generation)"* | `zone_geometry()` |
| Governor admission floor | **45 bps** | `per_trade.min_stop_width_bps` |
| Shadow bank median | **10.0 bps** | `get_bank_priced` |

At 10 bps the break-even win rate is **67.42 %** — no SMC setup clears that. The bank is scoring a geometry no layer would authorize. **WO:** `WO-A`

### GAP-50 · Origin's `capsules.py` carries 5 entry-convention IDs; RC2 defines 5 capsules; the mapping is refused, not established · `P2` · `FORM` · `ABSENT`

The teardown notes *"5 stable semantic entry-convention IDs (`capsules.py`), each bound by name+evidence — the old ordinal mapping is explicitly refused, not guessed."* Refusing to guess is correct. But until a signed mapping exists, no Origin capsule output can be joined to a RC2 capsule definition, and the comparator cannot align Origin candidates to engine detectors by semantic identity. **WO:** `WO-D`

---

## A.6 · What this addendum changes about priority

**Before this intake**, the register's first action was `WO-05` (probe the box for the Algo Service migration). That remains a genuine P0 — a silent `-4120` on every protective stop is unbounded risk.

**After this intake, there are two P0 tracks running in parallel, and the economic one now leads:**

```
TRACK 1 · SAFETY  (unchanged, still first on the box)
  WO-05 probe  ─►  WO-06 protected stop + algo path

TRACK 2 · ECONOMICS  (new lead, pure measurement, no venue risk)
  WO-A  diagnose the 13 pp        ─┐
        · no_fill_win_share        │
        · R-denominator audit      ├─►  WO-B  entry-mechanism arms
        · stop-regime reconciliation┘         (the 7×–13× trade)
  WO-D  run the comparator          ─────►  settles Engine vs Origin empirically
  WO-C  derive one RR floor from the cost model
```

**The reordering rationale.** Before this intake the economic work was "build a gate the system lacks." After it, the economic work is "recover 13 percentage points of win rate that the system already earns and then loses at the entry." The second is a far larger, far better-evidenced prize, and it can be measured entirely in shadow without arming anything.

