# Implementation Report — ONBOX work orders, WO-A reconciliation, judge measurement

**Date:** 2026-08-13 · **Boxes touched:** Mac Studio only · **Posture:** `OFF/OFF/OFF/LIVE`
throughout. Every action below was read-only. Nothing was armed, no order was placed, no money
flag was changed, and no bank row was written.

---

## 1. Document cross-check — which box, which repo

The three documents were checked against the actual machines before any work started.

| Work item | Target box | Repo | State found | Action taken |
|---|---|---|---|---|
| `measure_judge.sh` | **Mac** (Ollama-A `:11434` exists only there) | TriadIntelligence | not present on box | deployed + executed |
| WO-A `run_wo_a.py` | **Mac** (bank + print tape live there) | TriadLearning | **claimed "built", was absent** | built from scratch + executed |
| BTC/BCH funnel 30→2 | **Mac** (gateway census, engine keeper) | TriadEngine / VGP | census present | diagnosed |
| O-3 B00R closure | **GitHub**, not a box | TriadOrigin | **claim stale** — steps 1–3 already done | corrected in prior audit |
| O-1 credential rotation | owner-only | — | outstanding | left owner-gated |
| O-2 forensic salvage | **Mac** (4 refs exist only on box) | TriadOrigin | outstanding | deliberately untouched |

**None of these belong to Dell/Origin.** Dell has no Ollama, no bank, no gateway. Routing any of
this to Origin would have been the wrong box.

`ONBOX-GUIDE-1.md` is a superset of `ONBOX-GUIDE.md` (+39 lines: the WO-A section and the
BTC/BCH funnel section). Everything in the shorter file is carried unchanged.

---

## 2. WO-A — built, run, and a false alarm corrected

### 2.1 The harness did not exist

`ONBOX-GUIDE-1.md` states the WO-A harness is "built and its arithmetic is proven in CI". It was
not on the box: `analysis/wo_a/` did not exist in TriadLearning (`main`, head `bd00107`). It was
built to the stated WO-A specification against the real bank schema
(`databank_shadow_trades`, 3,070,819 rows).

Installed: `~/triad/TriadLearning/analysis/wo_a/run_wo_a.py`
Output: `~/triad/databank/RECONCILIATION-2026-08-13.md`

### 2.2 First run reported A0 STOP — and that was my bug, not the bank's

The first version keyed the A0 consistency gate on `decision_id` alone. It flagged **1,102
conflicting decision_ids** and halted, exactly as the WO-A law requires.

Investigating the first offender showed the flag was wrong. A single `decision_id` carries one
row per **cohort**, and each cohort is a *different execution scenario* replayed against the same
signal:

```
decision_id 018VPAK6MQTYZPZHF663V55DG9
  P-AMP-AT-SIG   LONG  win       <- amplified entry at signal time
  P-LADDER-MKT   LONG  loss      <- laddered market entry
  P-CHASE-1T     LONG  no_fill   <- chase, one tick
  TRIAD-A        LONG  no_fill   <- the production lane
  VR-BASE        LONG  no_fill   <- reference path
  ... 12 cohorts total
```

One decision legitimately resolving win under one execution scenario and loss under another is
the **entire purpose** of a counterfactual bank. Keying A0 on `decision_id` alone therefore
condemns correct data as corrupt.

Verification: `(decision_id, cohort)` pairs with more than one row = **0**. Every pair is unique.

**Fix:** the A0 gate now keys on `(decision_id, cohort)` — a real inconsistency is the *same
scenario* resolving two ways. Cross-cohort disagreement is now reported separately and labelled
as expected behaviour.

### 2.3 Result after the fix

**A0 verdict: PASS** — 0 conflicting scenarios; 1,102 cross-cohort disagreements, all healthy.

| Population | Wins | Losses | Resolved | Win rate |
|---|---|---|---|---|
| Gate ACCEPTED | 20 | 27 | 47 | **42.55%** |
| Gate DECLINED | 99,845 | 216,602 | 316,447 | **31.55%** |
| **TRUE OPPORTUNITY** | 100,674 | 217,132 | 317,806 | **31.68%** |

**Gap (accepted − true opportunity): +10.87 pp**

Win rate by execution scenario (top by resolved count):

| Cohort | Resolved | Win rate |
|---|---|---|
| M-null | 223,037 | 32.30% |
| M3 | 33,636 | 26.21% |
| M5b | 15,980 | 29.59% |
| M5a | 8,151 | 28.16% |
| M2 | 6,941 | 28.27% |
| P-AMP-AT-SIG | 5,395 | **75.38%** |
| M4 | 3,686 | 27.10% |

### 2.4 SYNC-2 signal, stated honestly

`true_opportunity_WR = 31.68%`, which is materially below 50%. Under the WO-A decision rule this
means **adverse selection is a live hypothesis** rather than being ruled out.

Two caveats that must travel with that number:

1. **The accepted sample is 47 resolved rows.** That is far too small to characterise the judge.
   The +10.87 pp gap is directionally interesting and statistically weak.
2. **WO-B was not built.** It amends RC3 law 14 and is an owner amendment. The go/no-go remains
   yours; this report only supplies the measurement.

`P-AMP-AT-SIG` at 75.38% over 5,395 resolved rows is the most interesting line in the table and
is worth its own investigation — it suggests entry timing, not signal quality, may dominate.

---

## 3. Judge measurement — real production latency

`measure_judge.sh` was deployed to `~/triad/TriadIntelligence/tools/`. Its live benchmark
**timed out**, first at the built-in 120 s and again after I raised it to 600 s, because Ollama
is concurrently serving production (model resident, 10 GB VRAM) and benchmark requests queue
behind live judging.

Rather than report a fabricated or contended number, I measured the thing that actually matters:
**real production latency** from 2,029 recorded decisions in the `decisions` ledger.

| Metric | Value |
|---|---|
| p50 | **4,842 ms** |
| p95 | **8,833 ms** |
| p99 | **12,000 ms** |
| max | 12,006 ms |
| mean | 5,094 ms |

Verdict mix over the same window: `skip` 3,725 · `take` 272 · `wait` 3.

Reading: the judge needs roughly 5 seconds at the median. Against a 12 s E05 deadline it fits;
against a sub-2-second target it does not. The p99 landing exactly on 12,000 ms is the signature
of a timeout cap being hit, not a natural tail.

---

## 4. The 30→2 funnel — a larger cause than the documents assumed

The suggested query (`shadow.v_symbol_gate_aggregate`) was not available, so I used the
cross-check the same document recommends: `~/.triad/run/gateway_census.json`.

```
per_symbol_selection sides: {'long': 27}   <- 27 symbols, ALL long
per_symbol_model     sides: {'long': 27}   <- identical, zero short
```

**Zero short entries anywhere in the gateway census.** This matches the finding from the paper
book: the money lane holds 6,667 candidates, 100% long, while the shadow lane produced 30,357
shorts over the same window.

Gateway dispositions:

| Disposition | Count |
|---|---|
| `defer_ttl_dropped` | 26,725 |
| `decisions_published` | 8,229 |
| `matrix_pass` | 8,226 |
| `ack_duplicate` | 355 |
| `serve_timeout` | 182 |
| `matrix_off` | 0 |

Two observations worth acting on:

1. **`defer_ttl_dropped` = 26,725 against 8,229 published** — roughly 3 candidates expire in the
   defer buffer for every 1 that reaches a decision. This is the dominant loss in the funnel and
   is a latency problem, consistent with the 5 s median judge time above.
2. **`matrix_off` = 0** means the active matrix is not switching short off explicitly. The
   short-side suppressor is therefore upstream of the gateway, not at it.

On the suppressor: `edge_policy.rs` carries an operator directive dated 2026-07-30 raising
`side_weight("short")` from 0.5 to 1.0 for parity, describing the old 0.5 as "an accidental
short-side suppressor". The source is at parity, and `side_weight` appears only inside the
compiled binary on the box (vendored config). So the surviving suppression is **not** this lever
in source form. Where shorts die between detector emission and gateway admission is still open,
and it is the single highest-value open question in the estate: **more than half of all generated
signal never reaches the judge at all.**

---

## 5. Not done, and why

| Item | Reason |
|---|---|
| **O-1 credential rotation** | Owner-only, touches issuing side. Now also covers the two MCP tokens I created — they appear in `ACCESS-GUIDE.md`, so under CO-10's golden rule they are EXPOSED and need rotation. |
| **O-2 forensic salvage** | The guide forbids `git reset` / `stash` / blind-merge and forbids `d6795cb` as a merge base. Left completely untouched. |
| **WO-B** | Gated on your go/no-go; amends RC3 law 14. |
| **D-3b source-grant widening** | Requires an owner-reviewed PR. |

---

## 6. Recommended order of work, based on evidence

1. **Find where shorts are suppressed.** Over half of generated signal never reaches the judge.
   No amount of judge tuning matters while one side of the market is invisible.
2. **Attack `defer_ttl_dropped` (26,725).** Three candidates expire per decision published. The
   5 s median judge latency is the prime suspect.
3. **Grow the accepted sample.** 47 resolved rows cannot answer the adverse-selection question,
   no matter how carefully the arithmetic is done.
4. **Then, and only then,** decide WO-B.

Items 1 and 2 are execution-plumbing problems and need no new theory. They are also, on current
evidence, worth more than any model change.
