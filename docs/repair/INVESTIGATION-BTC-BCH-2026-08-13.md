# INVESTIGATION — "the estate is only trading BTC and BCH" (2026-08-13)

**Scope:** READ-ONLY code + config analysis across the TRIAD estate repos (`/home/user/Triad*`).
This container holds the git repos but **not** the on-box runtime (no venue, bank, gateway census,
or live ledger — those live on the Mac at `/Users/liko/...`). Every finding below is a statement
about **where** a per-symbol collapse *can* live in code and **what on-box read would prove it** —
never a claim that any symbol is or is not trading. No runtime number is asserted.

**Posture unchanged: OFF/OFF/OFF/LIVE.** Nothing here arms, narrows, or edits anything.

---

## 1 · The question and the confirmed fact

The operator reports that of the shipped LIVE-30 universe, only ~2 symbols (BTC, BCH) reach live
money takes — the estate's "N of 30" funnel-collapse symptom in extreme form.

**Confirmed by config (not a config narrowing):**

- `TriadEngine/config/universes/live30.v1.json` and
  `TriadIntelligence/contracts/config/active_matrix.v1.json` (`config_version 2026.07.28-universe-30`)
  ship **30 symbols × 3 detectors = 90 cells ON**. All three detectors are enabled.
- The feed universe is **structurally forced to the full 30 or a fail-closed FATAL boot** — there is
  no shorter fallback list and no env path that can narrow the feed to two symbols
  (`run_stack.sh:105-116`, `compile_live_universe.py resolve_committed_symbols()` set-equality gate,
  `run_stack.sh:222-228` armed `matrix_reconcile --exact`).

So the collapse is **not** a universe/config narrowing. It lives **downstream** of the feed: in
candidate emission, the LIVE30-PROFITABLE-ONLY money-policy wall, judging admission, executor
eligibility/sizing, or the venue-precision/min-notional screen.

**Load-bearing caveat carried through this whole report:** *no single code or config path was found
that deterministically selects exactly `{BTC, BCH}`.* Every real per-symbol funnel below is either
(a) a general N-of-30 narrower that favours the *deepest books* (BTC/ETH/SOL/BNB — not BCH), or
(b) a screen keyed on each symbol's **real** venue precision, which ships
`metadata_state=PENDING_VENUE_SNAPSHOT` (tick/step/min-notional = `None`) and is therefore
**unknowable in-container**. The BTC+BCH pattern is most consistent with the *intersection* of two
or three general narrowers landing, in the current market window and at the current precision, on
the two symbols that happen to satisfy all of them. The definitive answer is the on-box per-symbol
funnel — which the estate already built the tools to read.

---

## 2 · Ranked candidate collapse points

Ranked by (per-symbol collapse power × does it plausibly single out BTC+BCH). PRIMARY suspects first.

| # | Stage | Can collapse per-symbol | Singles out BTC+BCH | Likelihood | Fastest on-box check |
|---|-------|:---:|:---:|---|---|
| **1** | **eligibility / sizing / venue min-notional** (Stage 5 + Stage 2 venue precision) | **YES** | LOW (per-symbol, precision-dependent) | **PRIMARY — CONTRIBUTING (general N-of-30 at the VGP)** | `shadow.v_symbol_gate_aggregate` per-symbol death stage; grep `venuegateway-<lane>` log for `minNotional` / `min_notional_after_rounding` / `reject_class=sizing` per symbol |
| **2** | **detection scan_gate depth floor** (Stage 4) | **YES** | LOW (favours *deepest* books → BTC/ETH/SOL/BNB, not BCH) | **PRIMARY — CONTRIBUTING (strongest general N-of-30 at $100 equity)** | engine keeper `interval funnel` + `interval drops_by_symbol` (`scan=` per symbol); `symbols.v1.json:5-12` $25k depth / 8bps screen |
| 3 | **money-live policy + long-only structure supply** (LIVE30-PROFITABLE-ONLY) | YES (market-state) | LOW (trend-dependent, not identity-dependent) | CONTRIBUTING | `per_symbol_candidates` census map + `get_packet`/`get_render` MCP for per-symbol `last_bos`/`last_choch` dir=='up' |
| 4 | **selection / serial-judge admission** (Stage 3) | NO (global token bucket) | LOW | CONTRIBUTING (throughput throttle, not a selector) | `gateway_census.json` `per_symbol_selection` (admits>0 for all 30?); door digest `admit/defer` line; `TOKEN_BUCKET_EXHAUSTED` per symbol |
| 5 | **venue-precision snapshot as a placement allowlist** (Stage 2, the PENDING_VENUE_SNAPSHOT hypothesis) | no | NO | **UNLIKELY** (no plane gates on config precision) | grep VGP log for `no venue filters for` — expect ZERO for the 30 (VGP fetches live exchangeInfo) |
| 6 | **feed / universe narrowing** (Stage 1) | no | NO | **RULED OUT** (fail-closed to full 30 or FATAL boot) | `ps aux \| grep market-data-run` argv; tape distinct-symbol count; `grep 'S5\|matrix_reconcile\|FATAL'` boot log |

Key structural facts behind the ranking:

- **The config's PENDING_VENUE_SNAPSHOT precision is never a placement gate** at any plane. VGP owns
  precision from *live* exchangeInfo (`TriadVenueGateway/src/triad_vgp/runtime.py:116-188`), the
  governor uses a **global** tick/lot (`triad_live_exec.rs:4651-4654`, defaults `0.0001`/`0.001`),
  and the engine falls back loudly when `tick_size` is `None` (`symbol_policy.rs:37-88`,
  `triad_engine.rs:917`/`2440`). So row 5 is refuted in code.
- **The governor no longer rejects on per-symbol min-notional** — it was moved to the VGP seam
  (`governor.rs:180-184` field declared but unread in the check body; comment at `governor.rs:523-533`;
  test `venue_min_notional_is_a_vgp_gate_not_a_governor_reject`). The per-symbol min-notional screen
  therefore runs **on-box at the VGP after real-precision rounding** — invisible here.
- **The min-notional-per-symbol default `BTC-USDT-PERP=100,ETH-USDT-PERP=20`** (`triad_live_exec.rs:1338`)
  makes **BTC harder**, not easier, and is neutral for BCH — the *opposite* of the reported symptom.
  If BTC is genuinely trading, the ~$100 estate-equity assumption is suspect (the owner-margin cap at
  `--max-margin-pct 1` would crush notional to ~$15 — below BTC's real $100 venue min-notional). This
  tension is itself a lead: **confirm live equity on-box.**
- **scan_gate ($25k depth / 8bps spread)** is majors-calibrated for $10k equity
  (`scan_gate.rs:14-40`); at ~$100 equity it collapses toward the deepest books — a strong general
  N-of-30 driver, but it favours BTC/ETH/SOL/BNB and would *exclude* BCH, so it cannot alone produce
  the pair.

---

## 3 · The single most likely cause

**No code path selects exactly `{BTC, BCH}`.** The honest ranking is that the extreme collapse is the
*intersection* of general per-symbol narrowers, of which the **strongest and most invisible-in-container
is the venue-precision / min-notional screen at the VGP (row 1), gated on each symbol's real Binance
exchangeInfo precision that ships `PENDING_VENUE_SNAPSHOT`** and combined with a tiny margin-capped
notional at low estate equity.

Reasoning — *what could BTC and BCH share that the other 28 lack, that this stage keys on:*

- Every real per-symbol screen downstream of the feed keys on **notional-after-rounding vs the
  symbol's real venue min-notional/lot** — a quantity that depends on each symbol's actual
  `step_size`/`minNotional`, which is `None` in config and only resolved on-box. The survivor set of
  a "capped-notional ≥ venue-min-notional-after-lot-rounding" test is precisely a small, per-symbol,
  precision-dependent set — the exact shape of the reported symptom.
- Combined with scan_gate (row 2) upstream and the LIVE30-PROFITABLE-ONLY long-only structure supply
  (row 3), the intersection can plausibly land on two symbols in a given window. *Which* two is a
  market-window × real-precision fact, not a code constant.

Because the specific pair is precision- and market-dependent, **the code cannot name it — the on-box
funnel can, in one query.**

**The ONE on-box command that confirms it fastest** (converts every hypothesis above into per-symbol
evidence at once):

```sql
-- On the Mac, against DTBNK: the per-symbol GATE aggregate over the GATED shadow rows
SELECT * FROM shadow.v_symbol_gate_aggregate ORDER BY instrument_id;
--   (or the windowed MCP read: runtime-family query_symbol_gate_aggregate,
--    start_utc/end_utc on opened_at, split by detector_version)
```

This returns, per symbol, **where in the funnel each of the 30 dies** — the direct answer to
"why only BTC+BCH." (Note the estate's own honesty caveat: this view is a *slice* of the funnel over
GATED shadow rows; pair it with the gateway census panels in §4 for the feed→judge→venue stages it
cannot see.)

---

## 4 · Run these on-box, in this order (read-only)

Uses only instrumentation the estate already built. Goal: the definitive per-symbol funnel in minutes.

1. **Live equity + governor args (settles the $100 tension).**
   `cat $RUN/<lane>/exposure_snapshot.json` (equity) and `ps auxww | grep triad_live_exec`
   (`--max-margin-pct`; confirm **no** `--tick/--lot/--min-notional-per-symbol` override ⇒ global
   precision). At $100 × margin_pct 1 × lev 15 the notional cap is ~$15 — below BTC's real venue
   min-notional; if BTC trades, equity is higher than assumed.

2. **The per-symbol GATE aggregate (the one command from §3).**
   `SELECT * FROM shadow.v_symbol_gate_aggregate ORDER BY instrument_id;` — or MCP
   `query_symbol_gate_aggregate` windowed on `opened_at`, split by `detector_version`. Shows the
   first-death gate_reason per symbol for the gated population.

3. **The gateway census panels (feed→judge stages the SQL view can't see).**
   Read `$TRIAD/run/gateway_census.json` (`TRIAD_GATEWAY_CENSUS_PATH`) via the runtime-family MCP
   reads:
   - `per_symbol_candidates` — does each of the 30 even *supply* a money-eligible (bos_choch/order_block LONG) candidate? (Stage 1/3 supply.)
   - `per_symbol_selection` — `admits>0` and comparable `best_rank` for all 30, or only BTC+BCH admitted? (Stage 3 admission.)
   - `get_per_symbol_model` — `started>0` / `completed>0` per symbol (judge starvation / HANDED_NO_VERDICT).
   - `per_symbol_terminal` — served vs deferred-forever per symbol.

4. **The engine drop attribution (Stage 4 detection/scan_gate).**
   On the engine keeper stderr: `grep 'interval funnel'` and `grep 'interval drops_by_symbol'`
   (`triad_engine.rs:2195`/`2202`). A symbol with high `scan=` is liquidity-gated (counted); a symbol
   **absent from both** is silently cold/no-data (SymbolDrops has no warmup reason).

5. **Symbol-funnel forensics + heartbeats (data-availability vs gate).**
   With `TRIAD_FUNNEL_FORENSICS=1` read the death certificates / `symbol_funnel` stages; with
   `TRIAD_ATOM_HEARTBEAT=1` grep the `triad.shadow.detector_route_heartbeat.v1` topic for
   `zero_reason=DATA_MISSING` per symbol — distinguishes "no feed data" from "gated."

6. **VGP per-symbol rejects (Stage 5/row 1 confirmation).**
   Grep the `venuegateway-<lane>` log / VGP reject ledger for `minNotional` /
   `min_notional_after_rounding` / `reject_class=sizing`, tallied by symbol; grep for
   `no venue filters for` (expect zero — proves VGP resolved live precision for all 30, refuting row 5).
   Cross-check `tools/fetch_tick_sizes.py` output: were `step_size`/`minNotional` resolved for all 30?

7. **Feed sanity (rule out row 6 definitively).**
   `ps aux | grep market-data-run` (`--symbols` count = 30?); distinct-symbol count over a recent
   tape window; `grep 'S5\|matrix_reconcile\|FATAL'` in the boot log; `grep -n 'TRIAD_SYMBOLS'
   /Users/liko/triad/secrets/live.env` (absent, or exactly the 30).

**Read the results as a funnel:** the earliest stage at which the 28 non-trading symbols disappear is
the collapse point. If they die at feed → row 6 (should be impossible). At candidate supply → Stage
1/3. At admission → Stage 3. At scan_gate → row 2. At the VGP min-notional → row 1.

---

## 5 · Honesty boundary

This report is **code and configuration analysis only**, performed against the git repos in this
container. It has:

- **claimed no runtime number** and asserted **no symbol is or is not trading** — those are on-box
  facts (venue, bank, gateway census, live ledger on the Mac) this container cannot read;
- identified **where** a per-symbol collapse can live in code and **what on-box read confirms each**;
- been explicit that **no code path deterministically yields exactly `{BTC, BCH}`** — the pattern is
  best explained by an intersection of general narrowers over each symbol's real (PENDING) venue
  precision and the current market window, which only the on-box per-symbol funnel can resolve.

The definitive answer is the on-box funnel read in §4 (step 2 first). **Posture unchanged:
OFF/OFF/OFF/LIVE.** No file was edited; nothing was armed or narrowed.
