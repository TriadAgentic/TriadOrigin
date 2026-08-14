# TRIAD — REVISION RECORD R-02

**Document ID:** `TRIAD-REVISION-RECORD-R-02-2026-08-13`
**Version:** `1.0.0`
**Prepared:** 2026-08-13
**Amends:** `TRIAD_REVISION_RECORD_R-01_2026-08-13.md` §1.5 · `TRIAD_REPAIR_WORK_ORDER_2026-08-13.md` §WO-J · `TRIAD_MASTER_SEQUENCE_2026-08-13.md` §1.4 SYNC-2
**Occasioned by:** `REPAIR-REPORT-2026-08-13.md` §4 and §3, and `INVESTIGATION-BTC-BCH-2026-08-13.md`
**Disposition:** `CORRECTION_RECORD / EVIDENCE / NOT_A_RATIFICATION / NO_RUNTIME_CHANGE`

---

## 1 · `ERR-02b` — R-01 §1.5 was wrong. Second error, opposite direction.

```
╔════════════════════════════════════════════════════════════════════════╗
║  R-01 §1.5 · WITHDRAWN 2026-08-13                                      ║
║  Reason: REVIEWER ERROR, SECOND OCCURRENCE ON THE SAME MACHINE.        ║
║  The proposed test asserted the opposite of the truth.                 ║
║  DO NOT IMPLEMENT test_reset_bar_low_is_not_applied_to_extreme.        ║
╚════════════════════════════════════════════════════════════════════════╝
```

### 1.1 · The three readings

| Reading | Claim | Verdict |
|---|---|---|
| **ERR-02** (mine, withdrawn in R-01) | Deepen the extreme on **every** `RECLAIM_PENDING` bar | **WRONG** — hold bars must not deepen |
| **R-01 §1.5** (mine, withdrawn here) | The reset bar does **not** deepen | **WRONG** — it does |
| **The machine** | Hold bar → **no** deepen. Reset bar → **yes**, applies its own low | **CORRECT** |

The reset bar returns to `EXCURSION` within the same event, so by the time the low is applied it **is** an excursion-phase bar. The CORRECTED LAW's scope wording — `E = min over excursion-phase bar lows` — is satisfied exactly. Both of my readings collapsed that distinction, in opposite directions.

Pinned by `excursion_reclaim_v2.py:712` (rule-3 reset-branch `_deepen`), `test_h10` (`extreme == 9960` = the reset bar's own low), and `test_hold_bars_do_not_deepen_the_extreme` (`test_excursion_reclaim_v2.py:589`).

### 1.2 · The failure mode, named so it stops recurring

**Both errors came from reasoning about the state machine from spec prose rather than from the code.** The prose is ambiguous enough to support two contradictory wrong readings; the code is not ambiguous at all. Twice I produced a confident finding from the ambiguous source and did not check it against the unambiguous one.

**Standing addition to `LAW-9`, step 2:**

```
When reading the "vendored master law" to classify a finding, the reviewer
MUST also read the implementing code and the tests that pin it, BEFORE the
finding is written — not after it is challenged.

Rationale: a spec-prose reading that has never been checked against the
machine is a hypothesis, not a finding. Publishing it as a finding transfers
the reviewer's uncertainty onto the implementer as work.

Corollary: a finding that would flip a passing test must quote that test by
name and file:line, and state why the test is wrong. If the reviewer cannot
name the test, the finding is not ready.

Neither ERR-02 nor R-01 §1.5 named the tests they contradicted. That absence
was the detectable signature of the defect in both cases.
```

### 1.3 · Disposition

- **`test_reset_bar_low_is_not_applied_to_extreme` is withdrawn.** Do not add it.
- The developer's replacement, `test_reset_bar_low_is_applied_to_the_extreme_err02_r01_corrected`, is **correct and sufficient**. It codifies actual behaviour, is byte-neutral, flips nothing, and closes the question permanently.
- **No documentation erratum against R-01 §1.5 is needed beyond this record** — R-01 §1.5 is withdrawn in full, not amended.
- **F13 requires no further work of any kind.** The machine was right the first time and the second time.

---

## 2 · `WO-J` — the classification is confirmed. LAW-9 fired on the document that created it.

**Verdict `OWNER_GATED_AMENDMENT` is correct and is accepted without reservation.**

The evidence is decisive and I did not check it before writing the work order:

- `book_completeness` / `RPI` / `rpiDepth` appear in **zero source files** — it is a net-new mandatory field.
- Input dataclasses are **frozen with no defaults** (`flow_atoms_v2.py:256-273, 277-289, 544-561, 751-765`). A mandatory no-default field turns **16 constructor call sites into `TypeError`**.
- The new F15 refusal `COVERAGE_UNVERIFIABLE_RPI` **replaces** the current coverage emit → new emitted bytes on that case.
- Baseline is green (74 passed). The work order would have broken it.

**`byte_change = true` · `flips_passing_test = true` → AMENDMENT.** Owner signature plus a prior spec-amendment PR, then built under `LAW-5` as `flow.tfi.window.v3` / `flow.ofi.best.v3` / `flow.book_tilt.band.v3` in a new `flow_atoms_v3.py`, retiring v2 with `RETIRED_DEFECTIVE{ref=WO-J/GAP-06}`, v2 bytes preserved.

**This is the law working.** I wrote `LAW-9` in the master sequence, then immediately wrote a work order that violates it. The implementer applied it to my own document and stopped. That is exactly the outcome the law exists to produce, and it is worth more than the work order was.

### 2.1 · Enum drift — my error, and `UNKNOWN` is the correct resolution

The implementer found the drift: `TRIAD_REPAIR_WORK_ORDER_2026-08-13.md:1288` lists `{COMPLETE, RPI_EXCLUDED}`; `TRIAD_MASTER_SEQUENCE_2026-08-13.md` STEP 1 lists `{COMPLETE, RPI_EXCLUDED, UNKNOWN}`.

**`UNKNOWN` is correct. The work order line is the error.** Under `LAW-2`, an atom whose provenance was never established must not be labelled either way — labelling it `RPI_EXCLUDED` asserts a fact about the feed that was not observed, and labelling it `COMPLETE` is worse. `UNKNOWN` is the honest default and the one that fails safe.

**Erratum:** the canonical enum is `{COMPLETE, RPI_EXCLUDED, UNKNOWN}`, three values, `UNKNOWN` as the no-default default. Carry this into the amendment PR.

### 2.2 · The byte-neutral subset that **is** agent-buildable

`WO-J` is fully blocked, but the defect it describes is real and will be forgotten while the amendment waits. There is a subset that changes no bytes and flips no test:

```
WO-J-a · TRIPWIRE ONLY. Agent-buildable. byte_change = false.

Add ONE xfail test to tests/formulas/, no source change:

    @pytest.mark.xfail(
        reason="GAP-06 / WO-J: F15 coverage denominator shares the "
               "numerator's RPI exclusion, so the ratio reads ~1.0 "
               "regardless of true completeness. Blocked on owner "
               "spec-amendment PR (LAW-9 AMENDMENT). See R-02 §2.",
        strict=True,
    )
    def test_f15_coverage_is_unverifiable_when_expected_trades_share_the_rpi_exclusion():
        ...

MUST: strict=True, so the day the amendment lands and the defect is fixed,
      the xfail becomes XPASS and FAILS the build — forcing the marker to be
      removed rather than left rotting.

MUST NOT: touch flow_atoms_v2.py, the v2 contract, any dataclass, or any
          reason-code enum. This is a record, not a repair.
```

**Classification: repair under `LAW-9`.** It changes no formula bytes and flips no passing test. Optional — its only purpose is to make sure the amendment is not silently dropped when this session's context is gone.

---

## 3 · `GAP-51` — the symbol-selection confound · **NEW · P0 · affects SYNC-2**

The BTC/BCH investigation and the 13-pp reconciliation are the same problem viewed from two ends, and reading them together produces a hypothesis neither contains alone.

### 3.1 · The confound

```
The frozen baseline    : 54.4 % WR / +0.533 R on fvg_retest, measured across
                         a broad population.

The live observation   : "barely profitable, borderline losing" — measured on
                         a population where only ~2 of 30 symbols reach a take.

The 28 missing symbols are NOT randomly absent. Per the investigation they are
removed by:
  - the VGP min_notional_after_rounding screen (per-symbol, precision-keyed),
  - the scan_gate $25k depth / 8 bps floor (favours the deepest books),
  - the owner-margin cap crushing notional to ~$15 at ~$100 equity.

=> The live win rate is measured on a NON-RANDOM subset selected by
   liquidity and venue precision, not by signal quality.
```

**The 13 pp therefore has at least four possible sources, not three:**

| Source | Remedy | Work order |
|---|---|---|
| Adverse selection on resting entries | Entry-mechanism arms | WO-B |
| R-denominator mismatch (`STOP` vs `INVALIDATION`) | Tag every R figure | WO-A A2 |
| Stop-regime mismatch (67–120 / 45 / 10 bps) | Reconcile the regimes | WO-A A3 |
| **Symbol selection — the live subset is not the measured population** | **Per-symbol funnel + per-symbol baseline** | **NEW — WO-A A5** |

**These are different defects with different remedies, and fixing the wrong one costs a 21-day window.**

### 3.2 · The sample-size question, quantified

`P(observed WR ≤ 40 % | true WR = 54.4 %)`:

| n (completed live round trips) | Probability | Reading |
|---:|---:|---|
| 30 | **0.0809** | plausibly noise — cannot conclude a gap exists |
| 60 | 0.0176 | unlikely but possible |
| 128 | **0.00066** | the gap is real, not sampling |

To distinguish 54.4 % from 40 % at 80 % power and α = 0.05 requires **93 trades**.

**The estate's own money-plane evidence is 332 fills / 128 decisions / 4 symbols — and `last_reconcile_ts` is null, so completed round-trip P&L has never been computed.** The value of `n` is therefore not currently known to anyone.

**This is not a reason to doubt the operator's report.** It is a reason to put a confidence interval on it before spending 21 days on a remedy. If `n` is near 30, "borderline" and "+0.533 R with bad luck" are not yet distinguishable.

### 3.3 · `WO-A A5` — new task, cheap, mandatory before SYNC-2

```
A5 · PER-SYMBOL BASELINE RECONCILIATION

A5.1  Count completed live round trips, per symbol, since the frozen
      baseline was recorded. Report n per symbol and n total.
      If n_total < 93, state plainly that the live gap is NOT YET
      STATISTICALLY DISTINGUISHABLE from the frozen baseline, and say so
      in A4's verdict rather than absorbing it.

A5.2  Recompute the frozen fvg_retest baseline RESTRICTED to the symbols
      that actually reach live takes (BTC, BCH, or whatever the funnel
      returns). Two figures, side by side:

          baseline_all_symbols   = 54.4 % / +0.533 R   (as recorded)
          baseline_live_subset   = ____ % / ____ R     (recomputed)

      If baseline_live_subset is materially BELOW baseline_all_symbols,
      part of the 13 pp is SYMBOL SELECTION and no amount of entry-mechanism
      work will recover it.

A5.3  Add the fourth line to A4's decomposition:
          adverse selection ....... ___ pp
          denominator mismatch .... ___ pp
          stop-regime mismatch .... ___ pp
          SYMBOL SELECTION ........ ___ pp   <- NEW
          unexplained ............. ___ pp

DRIFT TRAP: do NOT compute baseline_live_subset by filtering the frozen
number — the frozen number is a scalar constant in the engine source, not a
distribution. It must be RECOMPUTED from the underlying rows, restricted by
symbol. If the underlying rows are unavailable, the answer is
BASELINE_NOT_DECOMPOSABLE, an honest refusal, never an estimate.
```

### 3.4 · SYNC-2 is amended

```
BEFORE (R-01 / Master Sequence §1.4):
  SYNC-2 gates WO-B on no_fill_win_share alone.

AFTER:
  SYNC-2 gates WO-B on BOTH:
    (a) no_fill_win_share materially below 50 %, AND
    (b) A5 showing symbol selection does NOT account for the majority
        of the gap.

  If (a) holds but (b) fails — adverse selection is real but symbol
  selection dominates — then the higher-value work is the per-symbol
  funnel, not the entry arms. WO-B still gets built, but it is no longer
  the lead.
```

---

## 4 · What is now true

| Lane | State |
|---|---|
| **L4 ORIGIN** | **Finished.** Every Origin-scope item is `CLOSED`, `WITHDRAWN`, `OWNER_GATED`, `CHECK_ONLY` or `OUT_OF_ORIGIN`. `WO-J` is an amendment, not agent work. Only `WO-J-a` (§2.2, optional tripwire) remains buildable. **Do not manufacture work.** |
| **L2 DIAGNOSIS** | Built and correct. `RECONCILIATION-2026-08-13.md` returns `ON_BOX_PENDING` on every metric — the honest refusal. **Blocked on one on-box run.** |
| **L1 SAFETY** | `WO-00` not yet run. Blocked on operator. |
| **Investigation** | BTC/BCH funnel audit complete, read-only. Definitive answer available in **one on-box query**. |

**Three separate deliverables — the algo-endpoint probe, the 13-pp reconciliation, and the BTC/BCH funnel — are all blocked on the same thing: physical access to the Mac box.** All three are read-only. All three are fast. They should be one session.

---

## 5 · THE ON-BOX SESSION CARD

```
╔════════════════════════════════════════════════════════════════════════╗
║ ON-BOX SESSION · READ ONLY · ~45 MINUTES · ONE SITTING                 ║
║ Credential: read-only audit identity. NOT the trading key.             ║
║ Writes: zero. Orders: zero. Config edits: zero.                        ║
║ Posture unchanged throughout: OFF/OFF/OFF/LIVE.                        ║
╚════════════════════════════════════════════════════════════════════════╝
```

**Run in this order. The order matters — step 1 can abort the session.**

### Step 1 · WO-00 · the safety probe · ~10 min · **may halt everything**

Six steps, verbatim from `TRIAD_REPAIR_WORK_ORDER_2026-08-13` §WO-00.

```
ABORT CONDITION — check this before anything else:
  GET /fapi/v3/positionRisk   -> any position with qty != 0 ?
  GET /fapi/v1/openAlgoOrders -> a matching protective stop for it ?

  Position != 0 AND no matching algo order
     -> UNPROTECTED POSITION RIGHT NOW.
     -> STOP THE SESSION. Page. Flatten manually.
     -> Nothing else in this card matters until that is closed.

Then: grep for STOP_MARKET reaching POST /fapi/v1/order, and grep the logs
for -4120. A first occurrence on or near 2025-12-09 confirms the diagnosis
to the day.
```

**Output:** `PROBE-2026-08-13.md`, verdict `CONFIRMED_LIVE` / `SPEC_ONLY` / `INDETERMINATE`.

### Step 2 · the BTC/BCH funnel · ~5 min · **one query**

```sql
SELECT * FROM shadow.v_symbol_gate_aggregate ORDER BY instrument_id;
```

Then the live-equity settle, which the investigation flags as its own lead:

```bash
cat $RUN/<lane>/exposure_snapshot.json          # actual equity
ps auxww | grep triad_live_exec                 # --max-margin-pct
```

**Why this is step 2 and not step 4.** The result **changes how step 3 is interpreted**. If the funnel shows the 28 symbols dying at the VGP min-notional screen, then `GAP-51` is live and `WO-A A5` becomes mandatory before SYNC-2. Running the reconciliation first and the funnel later means re-reading the reconciliation.

The investigation also notes a real tension worth settling here: at ~$100 equity with `--max-margin-pct 1`, notional caps near **$15** — below BTC's real venue min-notional of **$100**. **If BTC is genuinely trading, equity is higher than assumed**, and several downstream assumptions move with it.

### Step 3 · WO-A · the reconciliation · ~20 min

```bash
<runner> --db /Users/liko/triad/databank/triad.db
```

Produces A0 → A0.4 → A1 → A2 → A3 → A4. **Then add A5** (§3.3) using step 2's symbol list.

```
A0 STOP CONDITION, as amended:
  within-resolver disagreement on fill status  -> STOP (exit 2), escalate to DTBNK
  cross-resolver disagreement                  -> informational; first_touch canonical
```

### Step 4 · the decision, on the same day

| Reading | Next |
|---|---|
| `WO-00` → `CONFIRMED_LIVE` | **L1 becomes P0.** Halt new starts in L2/L3/L4. Build `WO-01`. |
| `no_fill_win_share` well below 50 % **and** A5 shows symbol selection is minor | **Build `WO-B`.** Start the 21-day clock immediately. |
| `no_fill_win_share` below 50 % **but** A5 shows symbol selection dominates | **Per-symbol funnel first.** `WO-B` is still built but is no longer the lead. |
| `no_fill_win_share` ≈ 50 % | **Do not build `WO-B`.** The 13 pp is in A2/A3/A5. |
| `n_total < 93` | **State that the gap is not yet statistically distinguishable.** Do not spend 21 days on a remedy for an effect that may not exist. |

---

## 6 · Attestation boundary

| Claim | Status to this reviewer |
|---|---|
| Remote head `073f728`, tree clean, 12 gates green dual-seed | **Source claim** — not rerun |
| `test_reset_bar_low_is_applied_to_the_extreme_err02_r01_corrected` green | **Source claim** — not rerun |
| `tests/wo_a/` 31 passed | **Source claim** — not rerun |
| `flow_atoms_v2.py` frozen dataclasses, 16 constructor sites, zero `book_completeness` matches | **Source claim** — but internally consistent and sufficient to sustain the AMENDMENT verdict on its own logic |
| F13 reset-bar deepen behaviour | **Verified by this reviewer against the cited tests and line references.** The developer is right; R-01 §1.5 was wrong. |
| `GAP-51` symbol-selection confound | **Derived by this reviewer** from the two supplied documents. **Hypothesis, not measurement** — A5 tests it. |

**Runtime state: `NOT_ATTESTED`.** Repository presence, a green local test, a merged PR, and a running deployment remain four separate claims.

---

*Prepared 2026-08-13 · revision record R-02 · one withdrawal (second on the same machine), one law strengthened, one enum corrected, one new gap, one session card · posture unchanged `OFF/OFF/OFF/LIVE` · no signature, pin, credential or receipt fabricated*
