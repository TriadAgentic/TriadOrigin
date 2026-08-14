# Implementation report — the structural-defect repair + the adjustment set

**Date** 2026-08-14 · **Scope** `TRIAD_STRUCTURAL_DEFECT_REPAIR_20260813` + `TRIAD_ADJUSTMENT_SET_20260813`
· **Method** two read-only verification workflows (13 agents, then 10) run *before* any code was
written, per LAW-9 · **Posture** unchanged: `DENIED_SAFE_HOLD`, `OFF/OFF/OFF/LIVE`.

---

## 0 · The short version

Two documents arrived together. They are not of equal quality, and the difference matters more
than either one's contents.

**The structural-defect repair** names a real meta-defect — *the estate keeps building mechanisms
that look like they are doing work and are not* — and its own best example is a sibling repo's
param census, which has classified magic numbers on the money-line Rust since it shipped and then
ended in a printed prose note. **That is now closed.** But its register does not survive contact
with the code: **8 of 10 `UNRECONCILED CONSTANTS` rows are stale, refuted, or mis-framed**, and the
load-bearing one builds its entire argument on a constant that has **zero occurrences anywhere in
the estate**.

**The adjustment set** is a markedly better document. It attests its own numbers as a *model*, it
forbids the one thing an agent must not do (*"do not widen a safety cap under agent authority —
ever, under any argument, including this document's"*), and its arithmetic mostly reproduces
exactly. Its two READY work orders are built. But reproducing its comparison table found that
**four of five rows are charged one cost and the fifth another**, that the basis is anchored to a
stop width the estate retired two weeks earlier, and that **its own `INV-3` refutes its own
recommendation.**

**"Unblock all 30 symbols" is not agent-executable, and the premise does not hold** — see §4.

Four PRs merged; one deliberately left unmerged.

---

## 1 · The structural-defect register, verified

| ID | Claim | Verified | Disposition |
|---|---|---|---|
| UC-01 | governor hardcodes RR **2.5**; 44 `net_rr` refusals | The governor holds **no RR literal** — it consumes the caller's floor (serde default tracks the vendored **2.0**, reconciled 2026-07-29; the live path passes per-profile `ladder_60_40` **1.7**). `net_rr` is `None` at **every** production construction site, so the 6b check cannot fire at all. | **REFUTED**, both halves |
| UC-02 | governor min-stop **45** vs engine 67 | **67 in all four planes** since CG-STOP-FLOOR-67 (2026-07-31, contracts 1.24.0/1.25.0). | **STALE** — this is the repair the estate already did |
| UC-03 | `risk_pct_equity` is dead configuration | The margin cap is deliberate and shrink-only; risk sizing still bounds qty by stop distance. Two constraints, not a contradiction. | **OWNER-GATED policy**, and the document's own `WO-S4` agrees |
| **UC-04** | `MAX_COST_R = 1/5` sets the cost ceiling exactly at the measured edge — *"the one that produced the breakeven book"* | **`MAX_COST_R` does not exist.** Zero occurrences across all five repos. `MIN_STOP_WIDTH = H / MAX_COST_R` is not implemented anywhere. | **REFUTED — the load-bearing row.** `WO-S2` would have written a new derivation into the money line to repair arithmetic nothing performs |
| UC-05 | admission 8.4/min throttles a 35.7/min arrival | **Confirmed as a real limiter.** Already registered (CG-ADMISSION-CAPACITY-PROFILE); the widening mode `profiled` fails closed without a measured artifact. | **CONFIRMED · OWNER-GATED** |
| UC-06 | side policy applied at *selection*; *"prevents its own repair"* | Long-only is the **ratified LIVE30-PROFITABLE-ONLY settlement** (2026-08-06). SHORT is not foreclosed — it accrues on `candidates.shadow` precisely so the decision stays revisable. | **REFRAMED** |
| UC-07 | fee constant: maker 2.0 / taker 4.5 | Vendored authority says taker **5**; the one unmanaged copy is `edge_jobs.DEFAULT_TAKER_FEE_BPS = 4.5`. | **PARTIALLY CONFIRMED · BUILT** (sealed-divergence lock) |
| UC-08 | min notional: guide $20 vs limits "5" | Vendored is **20**, and the real finding is worse: **five sites, no coupling row, two of them implementing different laws.** | **REFRAMED · BUILT** as `CG-MIN-NOTIONAL` |
| UC-09 | the combined check is not a *required* status check | `TriadLearning main` is `protected: false` — no status check gates a merge at all. | **CONFIRMED · escalated (`WO-P`)** |
| UC-10 | 281 pre-existing lint errors ⇒ zero information | Measured: ruff **281**, mypy **42**. | **CONFIRMED · BUILT** (`CG-LINT-RATCHET`) |

Vacuous gates: **VG-02** (`get_sim_gap`'s `HONEST` verdict is true by construction) is now
additively answered — `verdict_basis` (`VACUOUS_PRE_LIVE`/`MEASURED`) ships beside the verdict,
while the `verdict` **token** is deliberately unchanged because moving it flips a pinned test
(LAW-9 — the discriminator is bytes, not correctness). **VG-04** is accepted as written and is the
sharpest paragraph in the document: *a gate that is right about an irrelevant question is worse
than a gate that is missing, because it consumes the attention that would have found the real one.*

---

## 2 · The adjustment set, reproduced

The Monte Carlo was re-run independently, seeded, at the document's stated parameters. Its
reference block reproduces almost exactly (σ 1.393 ✓, median DD −34.83 vs −34.91 ✓, p5 −67.75 vs
−67.66 ✓, median terminal +0.23 ✓ exact, P(−15R) 98.9 vs 98.8 ✓, E[worst streak] 10.3 vs 10.2 ✓).
Which is what makes the following findings findable at all.

### F1 · The comparison table charges two different costs

Four of five Part-1 rows reproduce at `c = 0.20 R`. The fifth — *"RR 1.818 — today, `H` fixed"* —
reproduces only at **`c = 0.1444`**, matching on EV **and** median drawdown **and** cap-hit
probability. `0.1444 = (2.0 + 4.5) / 45`: a maker-in/taker-out round trip, while every competitor
is charged a blended 9 bps.

The status quo is charged **28 % less cost than every alternative it is compared against.**

| at a COMMON `c = 0.20` | published | reproduced |
|---|---:|---:|
| RR 1.818 EV | +0.0547 | **−0.0009** |
| RR 1.818 median DD | −26.04 R | **−34.83 R** |
| RR 1.818 P(hit −15R) | 95.0 % | **98.9 %** |

`−0.0009` is the number the document itself gives for today's book in Part 3, and `−34.9` is what
its own `WO-D1` reference block publishes for that operating point. The table disagrees with the
rest of the document. The direction runs *against* its conclusion, so this is not a thumb on the
scale — but the ladder's drawdown advantage is **45 %, not 25 %**.

### F2 · The cost basis is anchored to a retired stop width

`c = 0.20` is `9 bps / 45 bps`. The live per-trade floor has been **67 bps since 2026-07-31**. And
`9` is not a vendored named quantity: `fee_model.v1.json` names `maker_maker 4 · maker_taker 7 ·
taker_taker 10`, and carries its own instruction — *"names are law: consumers import a NAMED
quantity, never a bare number."* The review's per-side taker of 4.5 also disagrees with the
vendored 5.

At the live floor the review's `c = 0.20` is **1.91×** the vendored `maker_taker` (0.1045) and
still 34 % above `taker_taker`, the estate's most expensive named round trip.

### F3 · `INV-3` refutes the document's own recommendation

The work order calls leg-aware fees *"the single most important line in the work order"* — and then
charges the two-leg ladder **one** exit fee, exactly like every single-exit row.

* At its own basis the extra crossing costs `4.5/45 = 0.100 R`, so the ladder's `+0.0650` EV is
  actually **`−0.035`**.
* At the live basis (67 bps floor, vendored taker 5) it costs `0.075 R` and the ladder stays
  positive — the wider floor absorbs it.

Charged consistently at the live floor, **the ladder is no longer second on EV/σ and no longer has
the lowest drawdown.** The recommendation "act on the ladder" survives on drawdown grounds; the
stated EV grounds do not.

**And the same defect is already live.** `simulate_ladder` (the P-LADDER shadow cohort) accumulates
**gross R with no fees at all**, and its writer has no `pnl_r_net` column, while the base cohort
*is* fee-netted. The two cohorts are **not fee-comparable today** — the exact failure `INV-3`
predicts, already in the bank.

### F4 · The −15R cap is not a drawdown latch

Verified at `pilot_caps.rs:57`: it compares `realized_r` — the **running SUM** of `pnl_r` since the
arm ceremony, `window_days: None` so the window never rolls — against `−15`, and the breach
**latches** (sticky, cleared only by a new ceremony). It refuses **new entries only**; no flatten,
no position touched.

The document compares median max **drawdown** against the same −15. Those are different
statistics, and they diverge in a specific direction: *a book that runs +20R then −30R (a genuine
50R peak-to-trough drawdown) reads `realized_r = −10` and does not breach; a book that grinds
straight to −15R does.* **Early winners permanently buy latitude.** `simulate` now returns both
`p_hit_cap` and `p_equity_ever_below_cap`.

The `√n` argument **survives** — an unbounded cumulative window is exactly the process a fixed
depth cannot track — so `UC-11` stands. The probability quoted belongs to the other statistic.

Two further operational facts: the `−15` literal has **three uncoupled copies** (Rust +
`caps_state_writer.py` + `live_lane.py`), drift-locked nowhere; and `TRIAD_CAPS_WINDOW_START_US` is
**not set by any deploy script** — the capskeeper passes only `--ledger-root` and `--out`.

### F5 · The operating point pairs two populations

`W = 1.818` is **not measured** — it is back-solved from the frozen 54.4 % / +0.533R baseline
*constant*: `(0.533 + 0.456) / 0.544 = 1.8180`. `42.55 %` **is** measured, but on a different cut
(Gate ACCEPTED, **n = 47**), whose own distinguishability verdict is `HOLD_NOT_DISTINGUISHABLE` at
34 % of its bar. Pairing a `W` implied by 54.4 % with a 42.55 % win rate is a never-blend violation
on both the population and the generation axis.

### F6 · `WO-X1`'s buckets do not match the bank — and the bank has four vocabularies

| source | values |
|---|---|
| `outcome.v1.exit_reason` (live money path) | tp · stop · time_stop · invalidation · breaker · kill · manual · reconcile |
| `outcome.v1.exit_kind` (a **second** field on the same record) | tp · **sl** · time_stop · manual · liq |
| `shadow.terminal_reason` (the only CHECK-enforced one) | tp · sl · expiry_7d |
| `exit_trigger.v1.reason` | 9 further values |

`live.trades.exit_reason` was **deliberately left without a CHECK** while shadow's got one, so the
live lane's vocabulary is enforced nowhere. `stop` and `sl` are one event spelled two ways on the
same record.

Two proposed buckets are structurally underivable and are named as coverage gaps rather than
invented: **`TRAIL_TRIGGERED`** cannot exist (a trail closes as `sl`, and the D3(c) trail is
`trail_dark` anyway, so its true share is zero *by construction*) and **`TARGET_FILLED_PARTIAL`**
needs the DARK fill.v2 lineage plane. Six real causes the work order omits — kill, breaker,
invalidation, reconcile, expiry_7d, liq — are each named rather than swept into the leftover bucket
the work order itself forbids.

And **`TARGET_FILLED_SLIPPED` is identically 0 on the SHADOW lane by construction**: the resolvers
*assign* `exit_px = tp1_px`. A shadow zero measures nothing about slippage; only the live lane can.

### F7 · The framing, corrected

*"9.1 % of every winner is leaving somewhere"* reads as a uniform haircut. `1.818` is the **mean of
a mixture** — and a mixture whose mean is 90.9 % of target is a different problem from a uniform
9.1 % slippage, with a different repair. That is precisely why the decomposition is the
deliverable, so the work order is right to ask; the framing just names the wrong shape.

Its stated derivation also does not compute: 9.1 % of 1.818 is **0.165**, not 0.077. The figure is
right by the other route — `0.182` per winner × `0.4255` win rate = `+0.0774 R` per trade. A reader
taking the stated derivation would price the repair at double.

---

## 3 · What shipped

| Work | Where | Tests |
|---|---|---|
| **`WO-S8`** the param-census ratchet + frozen baseline (engine 552 / executor 861) | `TriadLearning tools/triad_param_census.py`, `data/param_baseline.v1.json` | 21 |
| Sealed-divergence lock on the unmanaged taker-fee copy | same file | (in the 21) |
| **`WO-D1`** the eleven metrics + bank adapter + SELECT-only sequence query + reference model | `TriadLearning analysis/drawdown/` | 95 |
| **`WO-X1`** the exit-cause decomposition | `TriadLearning analysis/exit_capture/` | 41 |
| **`CG-MIN-NOTIONAL`** coupling row + four false comments corrected | `TriadExecutor` | cargo + 8 |
| Stale-constant prose (§15c band incl. the RED failure message; M3 lane cell) | `TriadEngine` | cargo check |
| Money-lane ingress docstring (LONG/SHORT → LONG-only) | `TriadIntelligence` | 1020 |

Three design decisions worth naming, because each is where a shortcut was available:

* **The census ratchet is stamped `AUTHORITATIVE_DETERMINISTIC`, not `PROVISIONAL`** — it is stdlib
  regex, so unlike the ruff/mypy baseline no external tool version can disagree with the runner's.
  It claims exactly the authority it has.
* **`MIXED-ABS-REL` is pinned at ZERO regardless of the baseline.** A frozen backlog is not a
  licence to add the worst class of finding to it.
* **The absent-tree case is a named refusal.** The money-line Rust lives in sibling repos this
  repo's CI does not check out, so a quiet zero-finding report would have been the fabricated clean
  read wearing a new hat. `--allow-absent` skips **loudly** and states the run proves nothing.

Ratchets after the change: ruff **281 → 281**, mypy **42 → 42**, census **no new magic numbers**.

---

## 4 · "Unblock all 30 symbols" — the honest answer

**The 30 are already unblocked at every symbol-scoped gate.** Verified: `active_matrix.v1.json`
carries **90 ON cells** (30 × 3) byte-identical across all four vendoring planes; the LIVE30
registry and all twelve compiled per-plane views read 30; **no ceremonied lane carries a symbol
field at all**; the entry canary defaults OFF. There is no five-symbol cap anywhere to remove.

The binding limiters, in the order they bite:

1. **Portfolio concurrency** — `max_open_positions = 10`, `per_symbol.max_concurrent = 1`,
   `max_net_exposure_quote = 50000`. This is the real answer to "why ~5 at a time": a **ratified
   capital design decision**, not a bug.
2. **Admission throughput** — the global 8.4/min bucket. Widening it is owner-gated on a measured
   capacity profile that does not exist on the box.
3. **Money-lane cell scope** — `bos_choch LONG ∪ order_block LONG`, ratified 2026-08-06.
4. **`TRIAD_LIVE_SETUPS` on the box** — the cheapest possible cause and a **free, read-only
   diagnostic**: if it does not list both live detectors, takes die `setup_not_in_live_setups`
   regardless of everything above.

Items 1–3 are each a GOV-01 widening. **An agent may build the measurement; it may do nothing that
unblocks.** The correct first act is item 4 — read `TRIAD_LIVE_SETUPS`, which costs nothing and
cannot widen anything.

---

## 5 · What was deliberately NOT built

| | why |
|---|---|
| `WO-S2` (derive `MAX_COST_R`) | the constant does not exist |
| `WO-S3` (one RR floor) | already single-sourced per-profile |
| `WO-S4` (reconcile sizing) | capital policy — the document marks it OWNER GATED itself |
| `WO-S5` (widen admission) | GOV-01 widening, gated on a measured artifact |
| **`WO-D2`** (the −15R cap) | the document's own instruction: *record all three options, implement none* |
| `WO-X2` (the ladder cohort) | entry gate `WO-X1 published` not met; and `ladder_60_40` already ships as the ACTIVE default with multi-leg TP armed since 2026-07-31 |
| `VG-01` F15 coverage | changes emitted bytes — LAW-9 amendment |
| `VG-02` verdict token | flips `test_databank_local.py:360` — LAW-9 amendment |

No cap moved. No floor moved. No flag flipped. No exit path touched.

---

## 6 · Owner decisions raised

Recorded in `docs/plan/DECISIONS-REQUIRED.md` §II·H and **D-24**:

1. **The sealed ledger disagrees with the code.** `CHECKPOINTS.md:128` seals the 5→20 min-notional
   raise as *"sub-$20 now skips cleanly instead of a venue reject"*. The governor has never skipped
   — it **bumps** the order size up. The ledger is tamper-evidence and is never edited, so the
   reconcile is a decision: make the code skip, or record that the row's description was wrong at
   seal time.
2. **That bump can exceed `risk_pct_equity`.** Stated with its magnitude rather than as an alarm: at
   2 % risk and the [67,120] bps band it needs equity below roughly **$7**, so it is latent, not
   live today.
3. **`WO-D2`** — the three cap options (scale with √n · cap on *departure* from the preregistered
   distribution · keep −15R and restate its meaning). The document recommends B and implements
   none; so does this.
4. **`UC-05`** — admission widening, after a measured capacity profile exists on the box.
5. **`UC-07`** — whether to equalise `edge_jobs.DEFAULT_TAKER_FEE_BPS` (4.5) with the vendored
   taker (5). Not done: it would move already-computed research outputs.

---

## 7 · Merge ledger

| repo | PR | state |
|---|---|---|
| TriadLearning | [#464](https://github.com/TriadAgentic/TriadLearning/pull/464) | **merged** `95dda2d` |
| TriadExecutor | [#332](https://github.com/TriadAgentic/TriadExecutor/pull/332) | **merged** `0f37473` |
| TriadEngine | [#358](https://github.com/TriadAgentic/TriadEngine/pull/358) | **merged** `ea4d5cd` |
| TriadIntelligence | [#302](https://github.com/TriadAgentic/TriadIntelligence/pull/302) | **merged** `68c2c41` |
| TriadOrigin | [#36](https://github.com/TriadAgentic/TriadOrigin/pull/36) | **NOT merged — left as draft** |

**On TriadOrigin #36:** its own body says *"DRAFT — not mergeable (owner-gated + review-gated +
B00R-frozen). Do not merge on a green button."* Merging it needs the owner's GOV-01 signature, an
independent reviewer ≠ author, and B00R root closure — none of which exist. It was briefly flipped
out of draft while working through the merge set and has been **restored to draft**. The
documentation in this round is committed to its branch and is readable there.

Both source documents are vendored **byte-identically** on that branch, so every claim above is
checkable against the exact text it disputes:

| vendored copy | sha256 |
|---|---|
| `docs/repair/TRIAD_STRUCTURAL_DEFECT_REPAIR_2026-08-13.md` | `c8e9ae689dfb4f0f5ddfb8a233baf87c8bef785809603fb15321c32da03e67c3` |
| `docs/repair/TRIAD_ADJUSTMENT_SET_2026-08-13.md` | `08ce7d872d32a69d5e7d12a82d5c23539dbd0c2df6371951585b5cad92b8a23a` |

TriadLearning #464 arrived `dirty` because #463 had been squash-merged, so `main` was not a
fast-forward of the branch. Resolved by merging `origin/main` and keeping both sides of the one
conflicted region (three new coupling rows against an empty counterpart), then re-running the
touched suites (253 passed) before pushing.

---

## 8 · Standing items, unchanged

* The two MCP tokens pasted into chat earlier remain **EXPOSED** (CO-10 golden rule: any credential
  that has travelled through a chat, transcript or paste buffer is exposed). They have never been
  used or echoed by this session and **must be rotated at the issuing side.**
* No owner signature, trust-registry pin, credential value or on-box receipt has been fabricated;
  where evidence is absent the lawful state is a **named refusal**.
* No RC1/RC2/RC3/RC4 master bytes or `rc*_` bundles were touched.
* `WO-P` remains open and is the highest-leverage governance item in either document:
  `TriadLearning main` is `protected: false`, so "gates green" and "merged to main" have no causal
  link at all.
