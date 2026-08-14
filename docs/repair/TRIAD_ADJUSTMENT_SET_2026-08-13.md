# TRIAD — THE ADJUSTMENT SET

**Document ID:** `TRIAD-ADJUSTMENTS-2026-08-13`
**Version:** `1.0.0`
**Prepared:** 2026-08-13
**Directive read as:** *build the actual adjustments — the TP/exit repair to capture the full target, and the drawdown metrics before anything else proceeds.*
**Disposition:** `WORK_ORDER_SET / EXECUTION_GRADE / NOT_A_RATIFICATION / NO_RUNTIME_CHANGE`
**Posture:** unchanged. `OFF/OFF/OFF/LIVE` · `DENIED_SAFE_HOLD`.

---

# PART 0 — YOU WERE RIGHT TO PUT DRAWDOWN FIRST

I had not computed it. Doing so produced the largest single finding since the fee analysis, and it changes a recommendation I gave you two turns ago.

```
Monte Carlo, 500 trades, 20,000 paths, at the measured operating point:

    median max drawdown ................ -19 R to -35 R   (across every config)
    5th-percentile max drawdown ........ -37 R to -68 R
    the estate's cap ...................  -15 R
    P(cap fires within 500 trades) .....  76 % to 99 %
```

**The `−15R` cap is smaller than the median drawdown of a working system.**

`sigma` per trade is ≈ 1.39 R. Max drawdown scales as `√n · sigma`. So:

```
    -15R is breached by NORMAL VARIANCE at  n ≈ 117 trades.
```

**When that cap fires you cannot tell "the system broke" from "it is Tuesday."** It returns the same answer regardless of whether anything is wrong. That is a **vacuous gate** in the exact Class B sense from the structural repair, and it belongs in that register:

> **`UC-11` · the `−15R` cap versus the drawdown distribution of a working system** · `P0` · a fixed number set against a `√n` process. It is guaranteed to be wrong at every `n` but one.

**Nothing here says remove the cap.** It says a cap that fires on normal variance is not protecting you — it is interrupting you, and it is doing so at a rate that makes the interruption uninformative. `WO-D2` fixes it without weakening it.

---

# PART 1 — AND IT CHANGES THE RR ANSWER

I told you the drawdown case for lower RR was legitimate. **The simulation says it is not — what helps drawdown is the ladder, not the lower target.**

| Config | WR | `W` | EV | `sigma` | **EV/σ** | median DD | **return/DD** | P(hit −15R) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **RR 2.5** | 37.79 % | 2.500 | +0.1227 | 1.697 | **+0.0723** | −25.70 R | **+2.393** | 96.2 % |
| RR 1.818 — today, `H` fixed | 42.55 % | 1.818 | +0.0547 | 1.393 | +0.0392 | −26.04 R | +1.076 | 95.0 % |
| RR 1.5 | 49.22 % | 1.500 | +0.0305 | 1.250 | +0.0244 | −25.90 R | +0.579 | 93.5 % |
| RR 1.0 | 59.22 % | 1.000 | −0.0156 | 0.983 | −0.0159 | −28.00 R | −0.286 | 92.6 % |
| **LADDER — half at 1R + runner** | 55.00 % | 1.300 | +0.0650 | 1.144 | **+0.0568** | **−19.20 R** | **+1.693** | **75.9 %** |

**Lower RR does cut per-trade volatility** — `sigma` falls from 1.70 at RR 2.5 to 0.98 at RR 1.0, a 42 % reduction. **But it cuts EV faster.** RR 2.5 wins on both risk-adjusted measures.

**The ladder is the configuration that actually improves drawdown:** the lowest absolute drawdown by 25 %, the lowest cap-hit probability by 17 points, second-best EV/σ, second-best return/drawdown. **It gets you the smoothness you were reaching for without paying the EV.**

**Caveat, and it is load-bearing.** Every row assumes the edge stays constant in percentage points as the target moves. That is `H1` from the RR analysis, and it is precisely what `WO-RR1` measures. If the edge decays with distance, the table inverts. **Do not act on the ordering until the target-response curve exists.** Act on the *ladder*, which wins under both hypotheses.

---

# PART 2 — THE ADJUSTMENTS

Four work orders. Two are pure measurement and run today. Two depend on them.

```
WO-D1  drawdown metric suite          READY   3 days   measurement
WO-D2  reconcile the -15R cap         GATED on D1      owner signature
WO-X1  exit-capture diagnosis         READY   2 days   measurement
WO-X2  the TP ladder cohort           GATED on X1      shadow only
```

---

## `WO-D1` · THE DRAWDOWN METRIC SUITE · **do this first**

```
OWNER LANE     L2 Learning
WRITABLE       analysis/drawdown/*.py · analysis/drawdown/*.sql
               analysis/drawdown/DRAWDOWN-<date>.md
FORBIDDEN      any write to the bank. Every statement SELECT.
               any change to the cap, the governor, or any limit.
ENTRY GATE     none
EXIT GATE      the eleven metrics below published, per cohort, never blended
DURATION       3 days
```

### The metrics — all eleven, per cohort, `COUNT(DISTINCT decision_id)` denominators

```
EQUITY-CURVE METRICS (require an ORDERED sequence — see the drift trap below)
  1  max_drawdown_R           deepest peak-to-trough in R
  2  max_drawdown_duration    trades from peak to recovery (not to trough)
  3  time_to_recover          trades from trough back to prior peak
  4  ulcer_index              sqrt(mean(drawdown_pct^2)) -- penalises depth AND duration
  5  current_drawdown_R       where the curve sits right now

STREAK METRICS
  6  max_losing_streak        longest consecutive losses
  7  max_winning_streak       longest consecutive wins
  8  streak_distribution      full histogram, not just the max

RISK-ADJUSTED
  9  ev_per_trade_R           already have it
 10  sigma_per_trade_R        sqrt(p(1-p)) x (W+1), computed EMPIRICALLY not from the formula
 11  ev_over_sigma            the per-trade Sharpe-like ratio
```

### Reference values to check your implementation against

Computed from the measured operating point (`WR 42.55 %`, `W 1.818 R`, `c 0.20`), 20,000 paths × 500 trades:

| Metric | Expected |
|---|---:|
| median max drawdown | **−34.91 R** |
| 5th-percentile max drawdown | **−67.66 R** |
| median terminal equity | +0.23 R |
| P(hit −15R) | **98.8 %** |
| `sigma` per trade | **1.393 R** |
| E[worst losing streak in 500] | **10.2** |
| P(6 consecutive losses) | 0.0360 |
| P(8 consecutive losses) | 0.0119 |
| P(10 consecutive losses) | 0.0039 |

**If your empirical numbers differ materially from these, either the trades are not independent — which is likely, and important — or the implementation is wrong. Determine which.**

**DRIFT TRAPS**

> **Trap 1 — "I'll compute drawdown over the whole bank."** No. Drawdown requires an **ordered equity sequence**. The bank holds 12 cohorts per decision, each a different execution scenario. **An equity curve built across cohorts is not an equity curve** — it is twelve interleaved ones. Compute per cohort, ordered by `signal_ts_us`, never blended (`LAW-4`).
>
> **Trap 2 — "Max drawdown is the number."** It is the *least* stable statistic in finance — it is an extremum, so it grows with `n` and never shrinks. **Report the distribution and the duration, and always alongside `n`.** A `−34R` drawdown over 500 trades and over 50 trades are different facts.
>
> **Trap 3 — "I'll use the analytic formula for sigma."** Compute it empirically from realised outcomes. The formula assumes every win is exactly `W` and every loss exactly `1R`. Real fills vary, and the difference is the thing worth knowing.
>
> **Trap 4 — Independence.** Your symbols are 73–85 % cross-correlated and trades overlap in time. **Concurrent positions in correlated symbols are one bet, not several.** Report `max_concurrent_positions` and drawdown both per-trade and per-calendar-day. The per-day figure is the one that matches lived experience.

**DEFINITION OF DONE** — all five:
- [ ] Eleven metrics, per cohort, never blended
- [ ] Every denominator `COUNT(DISTINCT decision_id)`
- [ ] Epoch-integer time arithmetic (`FLOOR(((ts/1e6)::BIGINT % 86400)/3600)`) — never `EXTRACT`
- [ ] Empirical `sigma`, not the formula
- [ ] Both per-trade and per-calendar-day drawdown reported

---

## `WO-D2` · RECONCILE THE `−15R` CAP · **OWNER GATED — do not change the cap**

```
OWNER LANE     owner decides; Executor implements
STATE          OWNER_GATED. An agent MAY NOT alter a safety cap.
ENTRY GATE     WO-D1 published
```

### The problem, stated precisely

```
cap                                -15 R      FIXED
max drawdown of a working system   sqrt(n) x sigma,  sigma ~ 1.39 R      GROWS

    n = 100   ->  expected DD scale  13.9 R
    n = 250   ->                     22.0 R
    n = 500   ->                     31.1 R
    n = 1000  ->                     44.0 R

    -15R is breached by normal variance at n ~ 117.
```

**A fixed number set against a `√n` process is guaranteed to be wrong at every `n` but one.** Below `n≈117` the cap is loose enough to be irrelevant; above it, the cap fires on variance and tells you nothing.

### Three lawful options — one must be signed

| Option | Mechanism | Character |
|---|---|---|
| **A · Scale the cap with `n`** | `cap(n) = k · √n · sigma`, `k` ratified. At `k = 2`: −28 R at n=100, −62 R at n=500 | **WIDENING at large `n`, narrowing at small `n`.** GOV-01. |
| **B · Cap on *departure*, not depth** *(recommended)* | Fire when the realised drawdown falls below the **1st percentile of the preregistered distribution at the current `n`**. Fires when behaviour departs from the model, not when it matches it | **Narrowing in character** — it is strictly more informative. Still a ceremony because it changes a safety mechanism. |
| **C · Keep −15R, restate its meaning** | It is not a "system broken" signal. It is a "stop and re-examine every 117 trades" signal. **Document it as such and stop treating it as evidence of failure** | **No ceremony.** Documentation only. Legitimate and honest. |

**Why B.** A cap should answer *"is this system behaving as modelled?"* A fixed depth cap answers *"has enough time passed?"* Option B is the only one that fires on information.

**AGENT INSTRUCTION:** record all three as open. **Do not implement any. Do not widen a safety cap under agent authority — ever, under any argument, including this document's.** Under `ARMED-BY-DEFAULT` the automatics remain sovereign over every signature including the owner's; an agent proposing to loosen one is exactly the failure mode the law exists to prevent.

### The interim that requires no signature

```
Add to every cap-fire event, as a recorded field, not a change of behaviour:

    expected_dd_at_n     = k x sqrt(n) x sigma_empirical
    percentile_of_dd     = where this drawdown sits in the preregistered
                           distribution at the current n
    verdict              = WITHIN_MODEL | DEPARTURE

The cap still fires exactly as it does today. But the operator now sees
whether it fired on variance or on breakage. That distinction is currently
unavailable and it costs one computed field.
```

---

## `WO-X1` · EXIT-CAPTURE DIAGNOSIS · **the 90.9 % question**

```
OWNER LANE     L2 Learning (diagnosis) -> E09 (repair)
WRITABLE       analysis/exit_capture/*
FORBIDDEN      any change to an exit path in THIS work order
ENTRY GATE     none
EXIT GATE      the 9.1 % gap decomposed into named causes summing to 100 %
DURATION       2 days
```

### The fact

```
framed target ............ 2.000 R
realised average win ..... 1.818 R
CAPTURE .................. 90.9 %

9.1 % of every winner is leaving somewhere. Name it.
```

### The decomposition — every winner lands in exactly one bucket

```
For each WINNING trade, classify by WHY it closed:

  TARGET_FILLED_FULL      hit the target, filled the whole size at/above it
  TARGET_FILLED_PARTIAL   hit the target, only part filled -> the rest exited elsewhere
  TRAIL_TRIGGERED         a trailing stop closed it before the target
  TIME_EXIT               a TTL/session close fired
  MANUAL_OR_OTHER         anything else -- must be named, never a bucket for leftovers
  SLIPPAGE_ON_TARGET      target filled but BELOW the target price

REQUIRED: the buckets are exhaustive and mutually exclusive.
          Their R-weighted shortfalls must sum to exactly the 9.1 %.
          If they do not sum, a bucket is missing -- FIND IT, do not
          create an "other" category.
```

### And the reading that decides the next work order

```
IF the gap is dominated by TRAIL / TIME_EXIT / PARTIAL:
    -> EXIT MECHANICS are leaking. The target is fine.
    -> Repair the exit. Worth +0.077 R. No geometry change.
    -> This is the READING B branch from the RR analysis.

IF the gap is dominated by TARGET_NEVER_REACHED
    (i.e. these are not "winners that fell short" but trades that closed
     positive without reaching target at all):
    -> the target is TOO FAR. Your instinct is right.
    -> This is READING A. Feeds WO-RR1's target-response curve directly.

IF SLIPPAGE_ON_TARGET dominates:
    -> the target fill is a taker crossing a thin book.
    -> the fix is execution, and it interacts with the maker/taker
       question in WO-B.
```

**DRIFT TRAPS**

> **Trap 1 — "I'll just fix the trail."** Not in this work order. This is a diagnosis. The buckets must sum to 100 % first, or you will fix the second-largest cause and declare victory.
>
> **Trap 2 — an "other" bucket.** Forbidden. Every winner has a named exit cause. If one cannot be determined, the value is `UNRESOLVED_EXIT_CAUSE` — an honest refusal that is counted and reported, never a silent catch-all.
>
> **Trap 3 — "the shortfall is small, so it does not matter."** 9.1 % of `W` is worth `+0.077 R` per trade. Today's book is `−0.0009 R`. **This single gap is 85× the size of the entire current net result.**

---

## `WO-X2` · THE TP LADDER COHORT · **shadow only, no ceremony**

```
OWNER LANE     L2 Learning
WRITABLE       config/exit_arms.v1.json · src/learning/exit_arms/*
               migrations/*_create_exit_arm_rows.sql · tests/exit_arms/*
FORBIDDEN      shadow_bank (any DDL/DML) · any live exit path
ENTRY GATE     WO-X1 published
EXIT GATE      >=4 exit arms accruing to their own table, zero blended aggregates
DURATION       3 days build + accrual
```

### Why a ladder rather than a lower target

**It wins under both hypotheses.** If the edge decays with distance (short reach), the near leg captures it. If the edge is flat or rising, the runner captures that. **You do not have to know which world you are in to benefit** — and the simulation says it is the configuration that actually reduces drawdown.

```
LADDER (half at 1R + runner):  median DD -19.20R   vs  -25.70 to -28.00R
                                P(hit -15R) 75.9%  vs  92.6% to 96.2%
                                EV/sigma +0.0568   -- second only to RR 2.5
```

### The arms — minimum four, all running simultaneously on the same tape

```json
{
  "schema": "triad/exit_arms/1",
  "ratified_by": "PENDING",
  "arms": [
    { "arm_id": "EXIT_SINGLE_2R",     "legs": [{"at_R": 2.0, "frac": 1}],
      "status": "ACTIVE_CONTROL" },
    { "arm_id": "EXIT_SINGLE_2R5",    "legs": [{"at_R": 2.5, "frac": 1}],
      "status": "PROPOSED_MUST_RATIFY" },
    { "arm_id": "EXIT_LADDER_1R_2R",  "legs": [{"at_R": 1.0, "frac": "1/2"},
                                               {"at_R": 2.0, "frac": "1/2"}],
      "status": "PROPOSED_MUST_RATIFY" },
    { "arm_id": "EXIT_LADDER_1R5_2R5","legs": [{"at_R": 1.5, "frac": "1/2"},
                                               {"at_R": 2.5, "frac": "1/2"}],
      "status": "PROPOSED_MUST_RATIFY" },
    { "arm_id": "EXIT_LADDER_1R_2R_3R","legs":[{"at_R": 1.0, "frac": "1/3"},
                                               {"at_R": 2.0, "frac": "1/3"},
                                               {"at_R": 3.0, "frac": "1/3"}],
      "status": "PROPOSED_MUST_RATIFY" }
  ]
}
```

### The four invariants, asserted by test

```
INV-1  Every arm sees the SAME entry, the SAME stop, the SAME decision_id.
       Only the exit legs differ. If the stop differs you are comparing
       different trades and the result is void.

INV-2  frac values are exact rationals summing to exactly 1.
       {"num":1,"den":2} -- never 0.5. LAW-1.

INV-3  H_bps is PER LEG. A ladder pays the exit fee on every leg.
       A 3-leg ladder crosses the spread three times, not once.
       An arm that charges one exit fee for three legs is lying in its
       own favour and will win the comparison by construction.

INV-4  Arms write to exit_arm_rows, NEVER to shadow_bank.
       The only view that exists GROUPs BY arm_id -- an ungrouped
       aggregate is structurally impossible.
```

**`INV-3` is the one most likely to be got wrong, and it is the one that decides the answer.** A three-leg ladder pays roughly three exit fees. At `H_exit = 4.5 bps` and a 45 bps stop, each extra leg costs `4.5/45 = 0.10 R`. **A 3-leg ladder is carrying `0.20 R` of extra cost that a single exit does not.** If the comparison does not charge it, the ladder wins on an accounting error.

Let that number sit for a moment: **the ladder's headline advantage in the simulation was `+0.065 R` of EV. Two extra legs cost `0.20 R`.** Under a naive fee model the ladder looks best; under a correct one it may lose outright. **This is the single most important line in the work order.**

### The report

```
Per arm, after a declared window frozen before it opens:
    n, WR, W, gross_EV_R, cost_R (LEG-AWARE), net_EV_R, CI_lower
    max_drawdown_R, ulcer_index, sigma, EV/sigma      <- from WO-D1
    P(hit the cap)

PAIRED comparison -- arms share decision_id. McNemar, exact, integer
arithmetic. An unpaired test on paired data hides real effects.

Adopt the PLATEAU, never the spike.
```

---

# PART 3 — SEQUENCE

```
NOW, in parallel, both pure measurement, no ceremony
   WO-D1   drawdown metric suite        3 days
   WO-X1   exit-capture diagnosis       2 days

THEN, decided by what they return
   WO-X1 says EXIT MECHANICS leak  ->  E09 repair, worth +0.077 R
   WO-X1 says TARGET TOO FAR       ->  feeds WO-RR1 target-response curve
   WO-D1 published                 ->  WO-D2 cap reconciliation, owner signature

THEN
   WO-X2   the TP ladder cohort, shadow, leg-aware fees
   WO-RR1  the target-response curve

OWNER TRACK, no agent dependency
   WO-D2 option A / B / C signature
   exit arm ratifications
```

## Two ordering rules

1. **`WO-D1` before any cap discussion.** You cannot reconcile a cap against a distribution you have not measured. The Monte Carlo figures in Part 0 are a *model*; `WO-D1` gives you the *empirical* ones, and the difference between them is itself information — specifically about whether your trades are independent.

2. **`WO-X1` before `WO-X2`.** If the 9.1 % is a leaking trail, a ladder does not fix it — it adds legs to a mechanism that is already exiting early, and pays extra fees for the privilege. **Diagnose, then adjust.**

---

# PART 4 — WHAT THIS SET DOES NOT DO

| | |
|---|---|
| **It does not change the cap** | `WO-D2` records three options and picks none. An agent widening a safety cap is the failure mode the ARMED-BY-DEFAULT law exists to prevent. The interim adds a *field*, not a behaviour. |
| **It does not lower RR** | The drawdown simulation says lower RR does not buy the smoothness you were reaching for. The ladder does. And the RR question stays open until the target-response curve exists. |
| **It does not touch a live exit** | `WO-X1` is a diagnosis. `WO-X2` is shadow. The repair is E09's and comes after the decomposition sums to 100 %. |
| **It does not disarm anything** | Every mechanism added is a metric, a named refusal, or a shadow cohort. |

---

## Attestation

| Claim | Status |
|---|---|
| All drawdown, streak, Kelly and `EV/σ` figures | **Monte Carlo by this reviewer** — 20,000 paths × 500 trades, seeded, reproducible. **A model, not a measurement.** `WO-D1` replaces them with empirical values. |
| The model assumes **independent** trades | **Almost certainly false.** Your symbols are 73–85 % cross-correlated and positions overlap. **Real drawdowns will be deeper than these figures, not shallower.** The `−15R` finding therefore understates the problem. |
| `sigma ≈ 1.39 R`, `−15R` breached at `n ≈ 117` | Derived from `WR 42.55 %`, `W 1.818 R` — both resting on `n = 47`, CI `[28.4 %, 56.7 %]`. **Provisional.** The `√n` scaling argument holds regardless of the exact `sigma`. |
| The RR/ladder ordering in Part 1 | Assumes a **constant-pp edge across distance** (`H1`). `WO-RR1` tests it. **The ladder recommendation holds under both hypotheses; the RR ordering does not.** |
| 90.9 % capture | **Source claim** — `W = 1.818` against a framed 2.0 |

**Runtime state: `NOT_ATTESTED`.**

---

*Prepared 2026-08-13 · the adjustment set · four work orders, one new structural defect (`UC-11`), one reversed recommendation · posture unchanged `OFF/OFF/OFF/LIVE`*
