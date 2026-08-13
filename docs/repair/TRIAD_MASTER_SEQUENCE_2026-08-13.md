# TRIAD — MASTER SEQUENCE & EXECUTION CONTROL

**Document ID:** `TRIAD-MASTER-SEQUENCE-2026-08-13`
**Version:** `1.0.0`
**Prepared:** 2026-08-13
**Supersedes:** the "EXECUTION ORDER" section of `TRIAD_REPAIR_WORK_ORDER_2026-08-13.md` only. Every other section of that document remains in force.
**Companions:** `TRIAD_REVISION_RECORD_R-01_2026-08-13.md` (corrections and withdrawals) · `TRIAD_ORIGIN_V7_GAP_REGISTER_2026-08-13.md` (the 50 gaps)
**Disposition:** `SEQUENCING_CONTROL / EXECUTION_GRADE / NOT_A_RATIFICATION / NO_RUNTIME_CHANGE`

**Posture:** unchanged throughout. `venue_environment=OFF · venue_activation=OFF · paper_activation=OFF · shadow_activation=LIVE` · `DENIED_SAFE_HOLD`. Nothing in this document arms, disarms, or signs anything.

---

# PART 0 — THE ANTI-DRIFT CONTRACT

## 0.1 · Why this document is shaped the way it is

An agent given a vague instruction does not stop. It fills the gap with something plausible and keeps going. The output looks like work, passes a casual read, and is wrong in a way nobody notices until it costs money.

**Every structural choice below exists to remove a place where that can happen.**

| Drift mode | The countermeasure in this document |
|---|---|
| Scope creep — "while I was in there I also…" | Every work order declares `WRITABLE PATHS`. Anything outside is a stop condition. |
| Inventing a test expectation | Every test vector carries its **computed** expected value. None says "assert correct." |
| Inventing a constant | Every value is either pinned with a source, or `MUST_RATIFY` with a named refusal. There is no third option. |
| Flipping a passing test to make a change fit | `LAW-9` (§0.3). A change that flips a passing test is an **amendment**, not a repair, and stops. |
| Guessing when the spec is ambiguous | Every ambiguity in this document is either resolved with a stated rule, or marked `OWNER_GATED` and stopped. |
| Silently picking one of several options | Options are lettered (A/B/C) with a recommendation and an explicit "do not pick" instruction. |
| Declaring done when partly done | Every work order has a binary `DEFINITION OF DONE` checklist. Partial is `NOT_DONE`. |
| Working the wrong repo | Every work order declares `OWNER LANE` and `REPO`. |
| Building something another lane owns | §1.2 ownership map. Origin must not build E07/E08/E09 mechanisms. |

**If you are an agent executing this document: refusing to proceed is a valid, complete, successful outcome.** A stop condition reached and reported correctly is a finished task. Guessing past it is a failed one, even if the guess is right.

## 0.2 · The nine standing laws

These apply to every work order without exception.

**LAW-1 · Exact arithmetic.** Integer ticks and steps. Ratios as reduced rational pairs `(num: int64, den: int64)` with `den > 0` and `gcd(|num|, den) = 1`. Every ratio comparison by cross-multiplication on integers. **No binary float appears in any decision path.** A static scan enforces this and is a required CI stage.

**LAW-2 · Named refusals only.** Every failure path emits a typed, named refusal with its evidence fields. No `None`. No silent `continue`. No bare `unknown`. No log-and-proceed.

**LAW-3 · Refusal is measurement.** Every refused candidate is written to SHADOW with full lineage. A refusal with lineage is a data point. A trade taken without a check is not. **Assert this by counting:** `refusals_emitted == shadow_rows_written`.

**LAW-4 · Never blend.** Populations are never aggregated across mode, venue, environment, source, cohort, arm, resolver, or formula version. A query that would blend must be refused by the query layer, not by convention.

**LAW-5 · Version discipline.** Repaired modules ship under a new semantic version. The defective version is retired with a `RETIRED_DEFECTIVE{ref}` banner. **Bytes preserved. Never edited in place. Never deleted.**

**LAW-6 · One work order, one commit series.** Do not mix work orders in one commit. Each lands with its full test family in the same series.

**LAW-7 · Nothing is disarmed.** `shadow_activation = LIVE` is fixed with no OFF control. The existing estate money path stays armed. Every mechanism added is a **gate that refuses one trade and records why** — never a switch that stops the engine.

**LAW-8 · Source claims are not attestations.** Repository presence, a green local test, a merged PR, and a running deployment are four separate claims requiring four separate proofs. Never write "verified" for something you did not independently rerun.

**LAW-9 · Spec-code conflict resolution.** See §0.3. This one is new and it is the most important.

## 0.3 · LAW-9 — the spec-code conflict rule

**Origin.** During the 2026-08-13 independent cross-check, erratum `ERR-02` proposed adding an excursion-extreme update to F13's `RECLAIM_PENDING` state. The implementing developer refused, on the grounds that the existing code faithfully implements the vendored `CORRECTED LAW` and is pinned by two passing tests. **The developer was right and the erratum was wrong** — see `TRIAD_REVISION_RECORD_R-01`. That near-miss would have silently changed formula-emitted bytes feeding F18 stop logic.

**The generalised rule, now standing law:**

```
When any external finding — audit, erratum, review, model output — proposes a
change to a formula, and that change would flip a currently-passing test:

  STEP 1 · STOP. Do not implement. Do not modify the test.

  STEP 2 · Determine what the code implements:
     Read the VENDORED MASTER LAW (RC1/RC2/RC3/RC4 bytes), not the finding's
     restatement of it.

     (a) Code implements the master law, finding contradicts it
            -> the finding is an AMENDMENT, not a repair.
     (b) Code contradicts the master law
            -> the finding is a REPAIR. Proceed under agent authority.
     (c) The master law is genuinely ambiguous between two readings
            -> OWNER_GATED. Do not pick. Record both readings.

  STEP 3 · Route:
     REPAIR      -> implement, land with its test family.
     AMENDMENT   -> requires (i) owner signature and (ii) a spec-amendment PR.
                    The code change and its acceptance test land TOGETHER
                    inside that signed set, never before it.
     OWNER_GATED -> record both readings at the code site with a named note.
                    Do not pick. Do not default. Do not "choose the safer one."

  THE DISCRIMINATOR, when steps 1-3 are unclear:
     Does the change alter the EMITTED BYTES of a formula?
     If YES -> AMENDMENT. Always. No exceptions. Regardless of how obviously
               correct the change appears.

  ALWAYS: record the disposition as a note AT THE CODE SITE, naming the
  finding ID and the reason. A future reader must not have to re-derive this.
```

**Why the discriminator is bytes and not correctness.** An agent that believes a change is obviously correct is exactly the agent most likely to be wrong, because obviousness is what suppresses the check. Byte-level change is objective and mechanically detectable; "correct" is a judgement the agent is not authorised to make alone.

## 0.4 · The work order header format

Every work order in Part 2 carries this block. **Read all of it before writing any code.**

```
OWNER LANE      which lane owns this. If you are not in it, you are not doing it.
REPO            the exact repository.
WRITABLE PATHS  the ONLY paths this work order may create or modify.
FORBIDDEN       paths that are explicitly out of bounds even if they seem related.
ENTRY GATE      a binary precondition. FALSE -> do not start.
EXIT GATE       a binary postcondition. FALSE -> NOT_DONE.
STOP CONDITIONS named conditions that halt work, each with a required action.
MAY NOT         explicitly forbidden actions.
DRIFT TRAPS     what an agent will be tempted to do here, and why not to.
DURATION        estimate for a competent developer with no prior context.
```

## 0.5 · What to do when you hit a stop condition

```
1. STOP writing code immediately.
2. Write a file: STOP-<WO-ID>-<condition-name>.md
   containing: what you were doing, the exact condition hit, the exact
   evidence (command output, file:line, test name), and what you did NOT do.
3. Do NOT attempt a workaround.
4. Do NOT proceed to the next work order — a stop condition may invalidate
   downstream assumptions.
5. Report and wait.
```

---

# PART 1 — THE MASTER SEQUENCE

## 1.1 · Lane map

Six lanes. Lanes run in parallel; work orders inside a lane run in sequence. Cross-lane dependencies are enforced only at the named `SYNC` points in §1.4.

| Lane | Name | Owner | Repo(s) | Money risk |
|---|---|---|---|---|
| **L1** | SAFETY | E09 / box operator | TriadExecutor, TriadVenueGateway | **Touches the venue** |
| **L2** | DIAGNOSIS | Learning / measurement | TriadLearning, TriadDTBNK | None — read-only |
| **L3** | GATES | E07 / E08 | TriadIntelligence, TriadExecutor | None until armed |
| **L4** | ORIGIN | TriadOrigin | TriadOrigin | None — E02 only |
| **L5** | GOVERNANCE | Owner | all | Ceremony only |
| **L6** | PLUMBING | Learning / Infra | TriadLearning, TriadDTBNK | None |

## 1.2 · Ownership map — the fence that stopped ERR-02's sibling errors

This table exists because the original work order set assigned Origin work that Origin must not do. **Read this before starting anything.**

| Work order | Owner lane | Origin's role | If Origin starts building this |
|---|---|---|---|
| WO-00 probe | **L1** | none | **STOP** — Origin has no venue access, by design |
| WO-01 algo path | **L1** | none | **STOP** — Origin holds no credentials, ever |
| WO-02 PROTECTED STOP | **L1** | none | **STOP** — order verbs are a forbidden capability in Origin |
| WO-A diagnose 13 pp | **L2** | none | **STOP** — Origin does not own the bank |
| WO-B entry arms | **L2** | supplies the candidate stream only | **STOP** if editing fill models |
| WO-D comparator | **L2** | supplies `ORIGIN_CANDIDATE` stream | OK to run Origin over the tape |
| WO-E `cost_model.v1` | **L3** | none | **STOP** — cost must never enter E02 (RC3 law 07) |
| WO-C derived RR floor | **L3** decides | **check only** — confirm F18 emits the exact unreduced RR pair regardless of floor outcome | **STOP** if adding a floor to F18 |
| WO-F E07 admission gate | **L3** | none | **STOP** — admission authority is E07's alone |
| WO-G ERR-01 F10 | **L4** | **CLOSED** | — |
| WO-H ERR-02 F13 | — | **WITHDRAWN** | see §1.3 |
| WO-I ERR-03 F12 | **L4** | owner-gated, correctly unpicked | **STOP** — do not pick A/B/C |
| WO-J RPI coverage | **L4** | **the only substantive Origin work outstanding** | proceed |
| WO-K … WO-Q | **L6 / L5** | none | **STOP** |

**The scheduling consequence, stated plainly.** After the ERR-01 closure and the ERR-02 withdrawal, **Origin's queue contains exactly one substantive item: WO-J.** Everything else on the critical path is L1, L2 and L3. The bottleneck has moved off Origin entirely. Do not manufacture Origin work to fill the gap.

## 1.3 · Work order register — current disposition

| WO | Title | Lane | State | Notes |
|---|---|---|---|---|
| WO-00 | Probe the box | L1 | **READY** | Runs first, absolutely |
| WO-01 | Algo-order path | L1 | GATED on WO-00 | P0 if probe confirms |
| WO-02 | PROTECTED STOP | L1 | GATED on WO-01 | |
| WO-A | Diagnose the 13 pp | L2 | **READY** | Pure SQL, no dependencies |
| WO-B | Entry-mechanism arms | L2 | GATED on WO-A1 + SYNC-2 | |
| WO-C | Derived RR floor | L3 | GATED on WO-E | |
| WO-D | Run the comparator | L2 | **READY** | Needs a frozen tape only |
| WO-E | `cost_model.v1` | L3 | GATED on WO-00 step 5 | |
| WO-F | E07 admission gate | L3 | GATED on WO-E, WO-C | |
| WO-G | ERR-01 F10 predicates | L4 | **CLOSED 2026-08-13** | Property test landed; spec text still needs D-21 |
| ~~WO-H~~ | ~~ERR-02 F13 extreme~~ | — | **WITHDRAWN 2026-08-13** | Reviewer error. Body retained with banner. See `R-01`. |
| WO-I | ERR-03 F12 split identity | L4 | **OWNER_GATED** on D-17 | Must land before any CAP-01 accrual |
| WO-J | RPI coverage clause | L4 | **READY** | Only outstanding Origin work |
| WO-K | Reconciler first run | L6 | GATED on WO-01 | |
| WO-L | Bank repair | L6 | **READY** | Blocks trust in WO-B's report |
| WO-M | `outcome.v3` | L6 | GATED on WO-L | |
| WO-N | Wire the control surface | L6 | READY | |
| WO-O | Prompt pinning | L6 | READY | Root unblock of the learning chain |
| WO-P | B00R root + source grant | L5 | **OWNER ACT** | Unfreezes the merge chain |
| WO-Q | Credentials + dead-man webhook | L5 | **OWNER ACT** | Standing P0 |

**Numbering stability law.** `WO-H` is withdrawn, not reused. Its identifier is retired permanently. No future work order takes the letter H. This prevents a reader six months from now from finding two different WO-H references.

## 1.4 · Sync points — the only cross-lane gates

Everything else runs in parallel. These five are hard.

### SYNC-1 · after WO-00 · **BRANCH**

```
IF probe step 1 finds STOP_MARKET reaching POST /fapi/v1/order
   OR probe step 2 finds any -4120 in the logs:
     -> GAP-05 CONFIRMED_LIVE
     -> L1 becomes P0. Halt L2/L3/L4 new starts until WO-01 lands.
     -> Reason: every protective stop may have been failing since 2025-12-09.
        A position with no stop outranks a 13 pp measurement question.

ELIF probe step 3 finds a non-zero position with no matching algo order:
     -> UNPROTECTED POSITION RIGHT NOW.
     -> Page. Flatten manually. Do not wait for WO-01.

ELSE:
     -> GAP-05 = SPEC_ONLY. L1 proceeds at normal priority.
     -> All lanes continue in parallel.
```

### SYNC-2 · after WO-A task A1 · **GO / NO-GO on WO-B**

```
Compute no_fill_win_share (the share of no_fill rows that would have won
under market-at-signal entry).

IF no_fill_win_share is materially BELOW 50%:
     -> Adverse selection is CONFIRMED as a major contributor.
     -> WO-B is the highest-value work in the estate. Build it.

IF no_fill_win_share is at or near 50%:
     -> Fills are approximately random. Adverse selection is NOT the culprit.
     -> DO NOT BUILD WO-B YET. The 13 pp is somewhere else.
     -> Return to WO-A tasks A2/A3 and find it.
     -> This is a real possible outcome. Do not assume the hypothesis is true.

IF no_fill_win_share is materially ABOVE 50%:
     -> The resting entry is FAVOURABLY selected — the opposite of expected.
     -> STOP. This contradicts every other measurement in the estate.
        Something is wrong with the query. Do not report it as a finding
        until the query is independently reproduced.
```

### SYNC-3 · WO-E before WO-C and WO-F

`cost_model.v1` must land before either consumer. **Neither WO-C nor WO-F may hardcode `H = 9` as a temporary measure to unblock development.** Under RC3 law 20 an invented number is the exact defect class being repaired. If `cost_model.v1` is unsigned, both consumers emit `BLOCKED_ON_RATIFY(cost_model)` and that is the correct, complete behaviour.

### SYNC-4 · WO-I before the first CAP-01 shadow row · **IRREVERSIBLE**

```
Once CAP-01 rows accrue under an ambiguous confirmation identity
(CONFIRMED_BY_BOS vs CONFIRMED_BY_BREAK, unresolved while F08 refuses),
they can NEVER be pooled with post-F08 rows. Under RC3 law 18 they are a
different trial family.

There is no later repair. The evidence is permanently split.

=> No CAP-01 shadow emission is permitted until D-17 is signed and WO-I lands.
=> If CAP-01 is already emitting, STOP the emission now and record how many
   rows accrued under the ambiguous identity. They become their own cohort.
```

### SYNC-5 · WO-L before trusting WO-B's report · **with a documented bypass**

```
The existing bank carries 2.93x row inflation (8,008 rows / 2,731 distinct
decisions) and three resolvers writing to one table with contradictory
outcomes summed into net_pnl_r.

An arm comparison written INTO that bank inherits the corruption.

TWO OPTIONS:
  (a) Land WO-L first, then run WO-B.        Slow. Correct.
  (b) WO-B writes to its OWN clean table.     Fast. Also correct.

ADOPT (b). The arms need their own table anyway under LAW-4 (never blend).
Specification is in WO-B §B2.1. This is not a shortcut — it is the correct
design, and it removes WO-L from WO-B's critical path.
```

## 1.5 · The critical path

The shortest chain from today to a defensible answer on the 13 percentage points:

```
WO-00  probe                 0.5 day   L1
   ├─ SYNC-1 branch
WO-A   diagnose              3   days  L2   ← parallel with WO-00
   ├─ SYNC-2 go/no-go
WO-B   arms build            4   days  L2
WO-B   arms accrue          21   days  L2   ← calendar, not effort
WO-B   paired report         2   days  L2
   ═══════════════════════════════════
   CRITICAL PATH ≈ 30 days, of which 21 are calendar wait
```

**The 21-day accrual window is the binding constraint and it cannot be compressed.** It is declared in advance and frozen — shortening it after seeing partial results is optional stopping, which invalidates the whole comparison (RC3 TBD-020 exists precisely to prevent this).

**Therefore: start WO-B's shadow accrual as early as SYNC-2 permits.** Everything else — WO-C, WO-E, WO-F, WO-J, WO-L — fits inside the 21-day window without extending the path.

## 1.6 · Full sequence, by phase

| Phase | Days | L1 SAFETY | L2 DIAGNOSIS | L3 GATES | L4 ORIGIN | L5 GOV | L6 PLUMBING |
|---|---|---|---|---|---|---|---|
| **0** | 0–1 | **WO-00 probe** | WO-A start (A0, A1) | — | WO-J start | WO-P begin | WO-L start |
| **SYNC-1** | 1 | ← branch decides whether L1 becomes P0 | | | | | |
| **1** | 1–7 | WO-01 *(if confirmed)* | WO-A A2, A3, A4 | WO-E build | WO-J | WO-P | WO-L, WO-O |
| **SYNC-2** | ~4 | | ← go/no-go on WO-B | | | | |
| **2** | 7–14 | WO-02 | WO-B build · WO-D run | WO-C build | WO-J done | WO-Q | WO-N |
| **3** | 14–35 | WO-K | **WO-B accrual (21d)** | WO-F build | *(idle — do not fill)* | — | WO-M |
| **SYNC-4** | before any CAP-01 | | | | ← WO-I gate | D-17 signature | |
| **4** | 35–37 | — | **WO-B paired report** | WO-F wired, refusing | — | — | — |
| **DECISION** | 37 | ← §3 decision points | | | | | |

---

# PART 2 — PHASE DETAIL

*Only work orders whose sequencing or scope changed since `TRIAD_REPAIR_WORK_ORDER_2026-08-13` are re-specified in full here. For the rest, that document's technical content stands unchanged — this document changes only their order and ownership.*

---

## PHASE 0 · WO-00 — PROBE THE BOX

```
╔════════════════════════════════════════════════════════════════════════╗
║ WO-00 · PROBE THE BOX                                                  ║
╠════════════════════════════════════════════════════════════════════════╣
║ OWNER LANE     L1 SAFETY                                               ║
║ REPO           TriadExecutor, TriadVenueGateway (READ ONLY)            ║
║ WRITABLE PATHS  PROBE-2026-08-13.md   ← ONE file. Nothing else.        ║
║ FORBIDDEN      every source file, every config, every venue endpoint   ║
║                that is not a GET                                       ║
║ ENTRY GATE     read-only audit credential available (NOT trading key)  ║
║ EXIT GATE      PROBE-2026-08-13.md exists with all six steps answered  ║
║ DURATION       30 minutes                                              ║
╚════════════════════════════════════════════════════════════════════════╝
```

**STOP CONDITIONS**

| Condition | Action |
|---|---|
| Only the trading key is available | **STOP.** Do not probe with a key that can write. Request a read-only audit identity (CO-10 step 3). |
| A non-zero position has no matching algo order | **STOP everything. Page immediately.** Flatten manually. Do not proceed to any other step or work order. |
| Any GET returns 401/403 | **STOP.** Record it. Do not retry with a different credential. |

**MAY NOT**
- May not place, cancel, or modify any order.
- May not edit any source file, even to add a log line.
- May not "fix" anything discovered. **This is a probe. Finding the defect is the deliverable.**
- May not run the probe against LIVE and TESTNET in the same session (mixed-environment evidence is forbidden — RC4 `MIXED_ENVIRONMENT_BUNDLE_FORBIDDEN`).

**DRIFT TRAPS**

> **Trap 1 — "I found the bug, I'll just fix it."** No. A probe that mutates the system destroys the evidence of what the system was. Record and stop. WO-01 fixes it, under its own scope fence, with tests.
>
> **Trap 2 — "The grep found nothing, so it's fine."** No. A negative grep proves the *string* is absent, not that the *behaviour* is absent. The endpoint may be constructed dynamically. Step 3 (query the venue directly) is the authoritative check and is not optional.
>
> **Trap 3 — "I'll summarise the output."** No. Record command output **verbatim**. A summary is an interpretation, and the interpretation is the thing being checked.

**The six steps are specified verbatim in `TRIAD_REPAIR_WORK_ORDER_2026-08-13` §WO-00. Execute them exactly. Do not reorder. Do not skip step 6 because steps 1–5 looked clean.**

**DEFINITION OF DONE** — all five true:
- [ ] `PROBE-2026-08-13.md` exists
- [ ] All six steps present with verbatim output
- [ ] `GAP-05` verdict stated as exactly one of `CONFIRMED_LIVE` / `SPEC_ONLY` / `INDETERMINATE`
- [ ] The unprotected-position question answered explicitly, yes or no
- [ ] Zero writes performed — confirmed by `git status` showing only the probe file

---

## PHASE 0 · WO-A — DIAGNOSE THE 13 PERCENTAGE POINTS

```
╔════════════════════════════════════════════════════════════════════════╗
║ WO-A · DIAGNOSE THE 13 pp                                              ║
╠════════════════════════════════════════════════════════════════════════╣
║ OWNER LANE     L2 DIAGNOSIS                                            ║
║ REPO           TriadLearning                                           ║
║ WRITABLE PATHS  analysis/wo_a/*.sql                                    ║
║                 analysis/wo_a/*.py                                     ║
║                 analysis/wo_a/RECONCILIATION-2026-08-13.md             ║
║ FORBIDDEN      the bank itself — every query is SELECT.                ║
║                No UPDATE, no INSERT, no DELETE, no schema change.      ║
║ ENTRY GATE     read access to /Users/liko/triad/databank/triad.db      ║
║ EXIT GATE      RECONCILIATION-2026-08-13.md with all six numbers       ║
║                and the residual "unexplained" stated                   ║
║ DURATION       3 days                                                  ║
╚════════════════════════════════════════════════════════════════════════╝
```

**MAY NOT**
- May not write to the bank. Every statement is `SELECT`.
- May not use `COUNT(*)` as a denominator anywhere. **`COUNT(DISTINCT decision_id)` only.**
- May not use `EXTRACT(hour FROM to_timestamp(ts/1e6))` — DuckDB renders that in the box session timezone (`−07:00`), not UTC. **Use epoch integer arithmetic:** `uh = FLOOR(((ts/1e6)::BIGINT % 86400) / 3600)`.
- May not aggregate across resolvers. See A0.
- May not proceed to A1 before A0 is complete.

### A0 — Resolver disambiguation. **This is new and it is mandatory.**

**Why this step exists.** The original WO-A specification told you to query `no_fill` rows. **That query is unsafe as written**, because the bank has three resolvers — `first-touch`, `confirm first-touch`, `ladder/trail 25bps-floor` — writing to one table, and a single `decision_id` can carry up to three rows with different outcomes. `no_fill` status is resolver-dependent: `confirm first-touch` uses a different entry trigger, so a decision can be `no_fill` under one resolver and `win` under another.

**Querying `WHERE shadow_outcome = 'no_fill'` without disambiguating counts the same decision multiple times and mixes fill models.** Do A0 first.

```sql
-- A0.1 · Classify every row by its producing resolver.
--        The resolver is not a column; it must be derived from resolve_note.
--        This mapping is EXACT. Do not invent additional classes.
CREATE OR REPLACE VIEW wo_a_rows AS
SELECT *,
  CASE
    WHEN resolve_note LIKE 'confirm%'                       THEN 'confirm_first_touch'
    WHEN resolve_note LIKE '%ladder%' OR resolve_note LIKE '%trail%'
                                                            THEN 'ladder_trail_25bps'
    WHEN resolve_note LIKE '%zone%'                         THEN 'first_touch_zone'
    ELSE 'first_touch'
  END AS resolver_id
FROM shadow_bank;

-- A0.2 · Per-resolver census. Report. Do not merge.
SELECT resolver_id,
       COUNT(DISTINCT decision_id)                       AS decisions,
       COUNT(*)                                          AS rows,
       COUNT(*)::DOUBLE / COUNT(DISTINCT decision_id)    AS rows_per_decision
FROM wo_a_rows GROUP BY 1 ORDER BY 1;

-- A0.3 · FILL-STATUS DISAGREEMENT. This is the number that gates A1.
--        How often do resolvers disagree about whether the entry filled?
WITH fillstat AS (
  SELECT decision_id, resolver_id,
         CASE WHEN shadow_outcome = 'no_fill' THEN 0 ELSE 1 END AS filled
  FROM wo_a_rows
  WHERE shadow_outcome IN ('no_fill','win','loss')
)
SELECT COUNT(*) FILTER (WHERE mn <> mx) AS decisions_disagreeing_on_fill,
       COUNT(*)                          AS decisions_with_2plus_resolvers,
       COUNT(*) FILTER (WHERE mn <> mx)::DOUBLE / NULLIF(COUNT(*),0)
                                         AS fill_disagreement_rate
FROM (SELECT decision_id, MIN(filled) mn, MAX(filled) mx, COUNT(*) c
      FROM fillstat GROUP BY 1 HAVING COUNT(*) >= 2);
```

**A0 STOP CONDITION.**

```
IF fill_disagreement_rate > 0.05:
    STOP. Do not proceed to A1.
    The resolvers disagree about the basic fact of whether an order filled.
    Until one resolver owns fill status, no_fill_win_share is not computable
    and any number produced would be an average of contradictory books.
    Escalate to WO-L (bank repair) and report.

IF fill_disagreement_rate <= 0.05:
    Proceed to A1, using resolver_id = 'first_touch' as the canonical fill
    model — it is the declared triad-cf/1 resolver. Report A1 for the other
    resolvers SEPARATELY, never merged (LAW-4).
```

### A1 — `no_fill_win_share`

Specification unchanged from `TRIAD_REPAIR_WORK_ORDER_2026-08-13` §WO-A task A1, with two mandatory additions:

1. **Restrict to `resolver_id = 'first_touch'`** per A0's stop rule. Report other resolvers separately.
2. **Re-derive the stop and target from the new entry** so that `stop_bps` is identical to the original. The entry price for this counterfactual is the **mark price at signal time**, not `cf_entry_price` (which is the resting limit that never filled). If you do not re-derive, you are measuring a different trade and the comparison is void.

**Verified sensitivity table — check your result against it:**

| `no_fill_win_share` | true opportunity WR | reported on filled subset |
|---:|---:|---:|
| 0 % | 26.4 % | 49.33 % |
| 20 % | 35.7 % | 49.33 % |
| **35 %** | **42.7 %** | 49.33 % |
| 50 % | 49.6 % | 49.33 % |
| 65 % | 56.6 % | 49.33 % |

**DRIFT TRAPS**

> **Trap 1 — "no_fill is missing data, I'll exclude it."** That is precisely the bias being measured. `no_fill` is 2,617 rows — **46.6 % of everything fillable**. Excluding it is what produced the 49.33 % figure in the first place.
>
> **Trap 2 — "I'll reuse `cf_entry_price` since it's already there."** No. That is the resting limit price that never filled. Using it measures nothing.
>
> **Trap 3 — "The result came out above 50 %, that's interesting, let me report it."** No — SYNC-2 says stop. A result above 50 % contradicts every other measurement in the estate and means the query is wrong. Reproduce it independently before it becomes a finding.
>
> **Trap 4 — "I'll just merge the resolvers to get more samples."** LAW-4. Three books are three books.

**DEFINITION OF DONE** — all six true:
- [ ] A0 complete, `fill_disagreement_rate` reported
- [ ] A1 computed for `first_touch`, others reported separately
- [ ] A2 (R-denominator audit) complete — `risk_denominator ∈ {STOP, INVALIDATION}` backfilled or honestly `UNRESOLVED_RISK_DENOMINATOR`
- [ ] A3 (stop-regime reconciliation) complete — the frozen baseline's regime named
- [ ] A4 published — six numbers plus the decomposition
- [ ] **"Unexplained" residual stated as a number, not absorbed.** If it exceeds 3 pp, the diagnosis is incomplete and WO-B waits.

---

## PHASE 2 · WO-B — ENTRY-MECHANISM ARMS

```
╔════════════════════════════════════════════════════════════════════════╗
║ WO-B · ENTRY-MECHANISM ARMS                                            ║
╠════════════════════════════════════════════════════════════════════════╣
║ OWNER LANE     L2 DIAGNOSIS                                            ║
║ REPO           TriadLearning (arm registry, resolver, table)           ║
║ WRITABLE PATHS  config/entry_arms.v1.json                              ║
║                 src/learning/entry_arms/*.py                           ║
║                 migrations/*_create_entry_arm_rows.sql                 ║
║                 tests/entry_arms/*.py                                  ║
║ FORBIDDEN      shadow_bank table (any DDL or DML)                      ║
║                any executor order-placement path                       ║
║                any Origin module                                       ║
║ ENTRY GATE     SYNC-2 returned GO                                      ║
║ EXIT GATE      3 arms accruing to entry_arm_rows; 0 blended aggregates ║
║ DURATION       4 days build + 21 days calendar accrual                 ║
╚════════════════════════════════════════════════════════════════════════╝
```

### B2.1 — The arms get their own table. **This is new (SYNC-5) and is not optional.**

```sql
-- Arms NEVER write into shadow_bank. Reasons, both binding:
--   1. shadow_bank carries 2.93x inflation and three resolvers. An arm
--      comparison written into it inherits that corruption.
--   2. LAW-4: arms are separate populations and must be physically separable.

CREATE TABLE entry_arm_rows (
  arm_id            TEXT    NOT NULL,   -- ENTRY_POST_ONLY_RESTING | ...
  cohort_tag        TEXT    NOT NULL,   -- entry:post_only_resting | ...
  decision_id       TEXT    NOT NULL,   -- JOINS THE THREE ARMS TOGETHER
  instrument_id     TEXT    NOT NULL,
  side              TEXT    NOT NULL,   -- LONG | SHORT
  entry_ticks       BIGINT  NOT NULL,
  stop_ticks        BIGINT  NOT NULL,
  target_ticks      BIGINT  NOT NULL,
  stop_bps_num      BIGINT  NOT NULL,   -- exact rational, never a float
  stop_bps_den      BIGINT  NOT NULL,
  rr_num            BIGINT  NOT NULL,
  rr_den            BIGINT  NOT NULL,
  h_bps_num         BIGINT  NOT NULL,   -- PER ARM. Never shared.
  h_bps_den         BIGINT  NOT NULL,
  risk_denominator  TEXT    NOT NULL,   -- STOP | INVALIDATION   (WO-A task A2)
  fill_model        TEXT    NOT NULL,
  outcome           TEXT    NOT NULL,   -- win | loss | no_fill | expired
                                        --  | gap | ARM_INAPPLICABLE
  pnl_r_num         BIGINT,             -- NULL when unresolved. Never 0.
  pnl_r_den         BIGINT,
  signal_ts_us      BIGINT  NOT NULL,   -- epoch microseconds UTC
  tape_digest       TEXT    NOT NULL,   -- pins the tape this was resolved on
  PRIMARY KEY (arm_id, decision_id)     -- exactly one row per arm per decision
);

CREATE INDEX ix_ear_decision ON entry_arm_rows(decision_id);
CREATE INDEX ix_ear_arm      ON entry_arm_rows(arm_id);
```

**The never-blend guard is a database constraint, not a convention:**

```sql
-- Any aggregate must GROUP BY arm_id. A view that cannot be queried
-- without it is stronger than a rule nobody reads.
CREATE VIEW entry_arm_summary AS
SELECT arm_id,
       COUNT(DISTINCT decision_id)                                  AS n,
       COUNT(*) FILTER (WHERE outcome='win')                        AS wins,
       COUNT(*) FILTER (WHERE outcome='loss')                       AS losses,
       COUNT(*) FILTER (WHERE outcome='no_fill')                    AS no_fills
FROM entry_arm_rows
GROUP BY arm_id;   -- mandatory. There is no ungrouped view. By design.
```

### B2.2 — The three invariants, asserted by test

```
INV-1 · stop_bps is IDENTICAL across all three arms for one decision_id.
        If it differs, you are comparing different trades and the result
        is void. Assert on every write.

INV-2 · h_bps is DIFFERENT across arms and is per-arm mandatory.
        A shared H makes the comparison meaningless — the arms costing
        different amounts IS the thing being measured.

INV-3 · ENTRY_MARKET_AT_SIGNAL has NO no_fill outcome, by construction.
        Assert the enum for that arm excludes it. This is not a modelling
        convenience — it is precisely the difference being measured, and it
        is how the 2,617 excluded rows re-enter the denominator.
```

### B2.3 — The window is frozen before it opens

```
ENTRY_ARM_WINDOW_DAYS = 21          MUST_RATIFY
ENTRY_ARM_WINDOW_START = <utc>      recorded BEFORE the first row is written
ENTRY_ARM_WINDOW_END   = start + 21 days

The end date is written to the registry at start time and is IMMUTABLE.

FORBIDDEN: reading arm results before the window closes.
FORBIDDEN: extending the window because results look promising.
FORBIDDEN: shortening the window because results look conclusive.

Both are optional stopping. RC3 TBD-020 exists to prevent exactly this.
Implement it as a hard block: the report generator refuses to run before
ENTRY_ARM_WINDOW_END with the named refusal WINDOW_NOT_CLOSED{end, now}.
```

### B2.4 — The comparison is PAIRED

```
The three arms share decision_id. They are NOT independent samples.

CORRECT   : McNemar's test on the paired win/loss outcomes.
WRONG     : two-sample proportion test / chi-square on independent groups.

Using an unpaired test on paired data OVERSTATES the variance and will
HIDE a real effect. Given the measured 23.5 pp gap this would produce a
false negative on the single most valuable finding in the estate.

McNemar, exact form, integer arithmetic (LAW-1):
    b = decisions where arm_X won and arm_Y lost
    c = decisions where arm_X lost and arm_Y won
    exact two-sided p = 2 * SUM(k=min(b,c)..0) C(b+c,k) / 2^(b+c), capped at 1
Report b, c, and p for every arm pair.
```

**DRIFT TRAPS**

> **Trap 1 — "I'll write arms into `shadow_bank`, it's already there."** No. §B2.1. The existing bank is corrupted and arms must be physically separable.
>
> **Trap 2 — "One `H` for all arms is simpler."** That destroys the experiment. INV-2.
>
> **Trap 3 — "The market arm shows no `no_fill`, that looks like a bug."** It is not a bug. It is the finding. INV-3.
>
> **Trap 4 — "Results look clear at day 9, let's call it."** Optional stopping. §B2.3. The report generator must refuse.
>
> **Trap 5 — "I'll use scipy's `proportions_ztest`."** Unpaired test on paired data. §B2.4. And it introduces a float into a decision path (LAW-1).
>
> **Trap 6 — "I'll promote the winning arm."** Not yours to do. Promotion to money-eligible is a ceremony. The work order ends at the report.

**DEFINITION OF DONE** — all seven true:
- [ ] `entry_arm_rows` table exists with all constraints
- [ ] Three arms in the registry; two `PROPOSED_MUST_RATIFY`, one `ACTIVE_CONTROL`
- [ ] INV-1, INV-2, INV-3 asserted by passing tests
- [ ] Window start recorded; end immutable; report generator refuses before it
- [ ] Ungrouped aggregate is impossible — no view exists that permits it
- [ ] 21 days accrued
- [ ] Report published with per-arm figures **and** paired McNemar statistics

---

## PHASE 1–2 · WO-J — RPI COVERAGE CLAUSE *(the only outstanding Origin work)*

```
╔════════════════════════════════════════════════════════════════════════╗
║ WO-J · RPI COVERAGE CLAUSE                                             ║
╠════════════════════════════════════════════════════════════════════════╣
║ OWNER LANE     L4 ORIGIN                                               ║
║ REPO           TriadOrigin                                             ║
║ WRITABLE PATHS  src/triad_origin/structures/flow_*.py                  ║
║                 src/triad_origin/e01_interface.py  (validator only)    ║
║                 contracts/schemas/flow_atom.*.json                     ║
║                 tests/formulas/test_f15*.py test_f16*.py test_f17*.py  ║
║ FORBIDDEN      any venue client · any credential path · any E07/E08/E09║
║                module · the CKS event equation itself (verified exact) ║
║ ENTRY GATE     none — READY now                                        ║
║ EXIT GATE      every flow atom carries book_completeness; no exact     ║
║                maker-fill claim survives from an RPI_EXCLUDED atom     ║
║ DURATION       3 days                                                  ║
╚════════════════════════════════════════════════════════════════════════╝
```

### The venue fact, pinned

Binance change log **2025-11-18** and **2025-12-29**:

```
RPI (Retail Price Improvement) orders were introduced to USDⓈ-M Futures.

ORDER BOOK EXCLUSION — RPI orders do NOT appear in:
    GET /fapi/v1/depth
    GET /fapi/v1/ticker/bookTicker
    ticker.book · <symbol>@bookTicker · !bookTicker
    <symbol>@depth<levels> · <symbol>@depth

RPI book available separately:
    GET /fapi/v1/rpiDepth
    <symbol>@rpiDepth@500ms

TRADE EXCLUSION — effective 2025-12-31, field `nq` in <symbol>@aggTrade
aggregates only NORMAL market trades. Trades involving RPI orders are NOT
aggregated.
```

### What this breaks, formula by formula

| Formula | Consumes | Breakage |
|---|---|---|
| **F16** `flow.ofi.best.v2` | best-quote updates | Computed on a book missing RPI liquidity. The exclusion is **not random** — it is retail-flow-selective, so the bias is directional. |
| **F17** `flow.book_tilt.band.v2` | banded local-book depth | Same exclusion. Tilt is biased by whatever RPI liquidity sits inside the band. |
| **F15** `flow.tfi.window.v2` | trades + `expected_trades` | **The dangerous one.** F15's coverage law is `included/expected >= min_coverage else NULL{COVERAGE}`. If `expected_trades` derives from `aggTrade`, RPI trades are absent from **both** numerator and denominator — so **coverage reads COMPLETE while the population is incomplete.** A silent measurement error, not a loud one. |

### The change — label first, fetch second

```
STEP 1 · Add a mandatory field to the flow atom contract.

    book_completeness ∈ { COMPLETE | RPI_EXCLUDED | UNKNOWN }
        NOT NULL. No default. No inference.

    COMPLETE      the atom was computed from a book/trade stream proven to
                  include RPI (i.e. rpiDepth was fetched and merged, or the
                  venue confirms no RPI on this instrument)
    RPI_EXCLUDED  computed from the standard depth/aggTrade feeds
    UNKNOWN       provenance not established -> the atom is EVIDENCE ONLY

STEP 2 · Downstream law.
    An atom with book_completeness != COMPLETE MUST NOT support:
      - an exact maker-fill claim
      - a queue-position estimate
      - any statement about the depth available at a price
    It MAY support a directional signal, labelled approximate.

    This is RC3 BOK-11's already-correct posture:
      "Evidence plane is labeled incomplete/approximate; no exact maker-fill
       claim." Implement it. Do not restate it.

STEP 3 · F15 coverage repair. THIS IS THE ONE THAT MATTERS.
    expected_trades MUST NOT be derived from aggTrade alone.
    Either:
      (a) derive expected_trades from the raw trade stream (which includes
          RPI trades) and count RPI trades as included; or
      (b) if only aggTrade is available, set
             book_completeness = RPI_EXCLUDED
          AND emit coverage as NULL{COVERAGE_UNVERIFIABLE_RPI}
          rather than a computed ratio.
    NEVER report a coverage ratio computed from a denominator that shares
    the numerator's exclusion. That ratio is always ~1.0 and always a lie.

STEP 4 · Only where COMPLETE is genuinely required, fetch the RPI book.
    Do NOT fetch rpiDepth everywhere. It doubles the feed cost and most
    consumers do not need it. Fetch it only where a downstream consumer
    declares a COMPLETE requirement.
```

**DRIFT TRAPS**

> **Trap 1 — "I'll just merge `rpiDepth` into the book everywhere and call it fixed."** No. Step 4. Most consumers do not need it; you would double the feed cost for no gain, and you would still not have fixed F15's coverage denominator, which is the actual defect.
>
> **Trap 2 — "Coverage reads 0.99, so coverage is fine."** That is the bug. If numerator and denominator share an exclusion, the ratio is meaningless. Step 3.
>
> **Trap 3 — "The CKS equation must be wrong too."** It is not. The F16 event equation was independently verified against Cont, Kukanov & Stoikov (JFE 12(1), 2014) term for term, and `GV-F16-01` recomputes exactly (`OFI = +7`, normalized `21/20`). **The equation is correct; its input is incomplete.** Do not touch the equation.
>
> **Trap 4 — "I'll default `book_completeness` to `COMPLETE` to avoid breaking tests."** LAW-2. `UNKNOWN` is the honest default and it is the one that fails safe.

**TESTS**

| # | Scenario | Expected |
|---|---|---|
| T1 | Atom built from `<symbol>@depth` only | `book_completeness = RPI_EXCLUDED` |
| T2 | Atom built from depth + `rpiDepth`, sequence-consistent | `COMPLETE` |
| T3 | Provenance not recorded | `UNKNOWN`; atom is evidence-only |
| T4 | Consumer requests an exact maker-fill claim from an `RPI_EXCLUDED` atom | **refused** — `REFUSED_INCOMPLETE_BOOK` |
| T5 | F15 with `expected_trades` from `aggTrade`, `book_completeness = RPI_EXCLUDED` | coverage `NULL{COVERAGE_UNVERIFIABLE_RPI}` — **not** a computed ratio |
| T6 | F15 with raw trade stream including RPI | coverage computed normally; `COMPLETE` |
| T7 | `book_completeness` field absent from an atom | contract validation **fails** |
| T8 | `GV-F16-01` | still `OFI = +7`, normalized `21/20` — **the equation is unchanged** |

**DEFINITION OF DONE** — all five true:
- [ ] `book_completeness` mandatory in the flow atom contract, no default
- [ ] F15 coverage returns `NULL{COVERAGE_UNVERIFIABLE_RPI}` when the denominator shares the numerator's exclusion
- [ ] Exact maker-fill claims refused from non-`COMPLETE` atoms
- [ ] `rpiDepth` fetched **only** where a consumer declares a `COMPLETE` requirement
- [ ] `GV-F16-01` unchanged and passing — proof the equation was not touched

---

## PHASE 3 · WO-I — ERR-03 / D-17 · **OWNER GATED — DO NOT PICK**

```
╔════════════════════════════════════════════════════════════════════════╗
║ WO-I · F12 CONFIRMATION IDENTITY                                       ║
╠════════════════════════════════════════════════════════════════════════╣
║ OWNER LANE     L4 ORIGIN — but BLOCKED on owner signature D-17         ║
║ STATE          OWNER_GATED. An agent MAY NOT select option A, B or C.  ║
║ ENTRY GATE     D-17 signed, naming exactly one option                  ║
║ IRREVERSIBLE   SYNC-4 — must land before ANY CAP-01 shadow row         ║
╚════════════════════════════════════════════════════════════════════════╝
```

**The situation.** §R-F12 confirms an order block on *"a same-direction accepted F09 break occurrence."* §R-F09 emits only `GENERIC_BREAK` — no BOS/CHOCH label — while F08 refuses. So `ob.displacement_bos.v2` confirms on **any close through a frozen level**, not on breaks of structure.

**Why an agent may not pick.** Under RC3 law 18 this determines the **trial family**. Rows accrued under one identity can never be pooled with rows under another. **There is no later repair.** This is a permanent, irreversible partition of the evidence, and it belongs to the owner.

| Option | Mechanism | Recommendation |
|---|---|---|
| **A · Gate** | F12 refuses while F08 refuses: `BLOCKED_ON_RATIFY(F08)` | Cleanest semantics, costs the most time |
| **B · Split identity** | `ob.displacement_break.v2` / `CONFIRMED_BY_BREAK`, own registry row, own trial family, own cohort tag | **RECOMMENDED** — only option satisfying both never-blend and armed-by-default |
| **C · Accept and record** | Keep the name, stamp `confirmation_class ∈ {BOS, GENERIC_BREAK}`, refuse cross-class aggregation at read time | Cheapest; relies on read-time discipline rather than write-time structure |

**AGENT INSTRUCTION:** record that all three remain open. Add the honest note at the code site. **Do not implement any of them. Do not implement "the safest one." Do not implement B because this document recommends it.** A recommendation to the owner is not authority for an agent.

**Interim requirement, which IS in scope:** verify whether CAP-01 is currently emitting shadow rows. If it is, **stop the emission** and record how many rows accrued under the ambiguous identity. They become their own permanently-separate cohort. Report the count. Do not delete them.

---

# PART 3 — DECISION POINTS

Three points where a human decides and the programme branches. Each is binary, with a stated threshold.

## DP-1 · after WO-00 — is the estate placing stops correctly?

| Evidence | Decision |
|---|---|
| `STOP_MARKET` on `/fapi/v1/order`, or any `-4120` in logs | `GAP-05 CONFIRMED_LIVE` → **L1 becomes P0. Halt new starts in L2/L3/L4 until WO-01 lands.** |
| Non-zero position, no matching algo order | **Page. Flatten. Immediate.** |
| Neither | `SPEC_ONLY` → all lanes proceed in parallel at normal priority |

## DP-2 · after WO-A A1 — is adverse selection the culprit?

| `no_fill_win_share` | Decision |
|---|---|
| materially **below** 50 % | Confirmed. **Build WO-B.** It is the highest-value work in the estate. |
| at or near 50 % | Not the culprit. **Do not build WO-B yet.** Return to A2/A3 and find the 13 pp elsewhere. |
| materially **above** 50 % | Contradicts every other estate measurement. **STOP.** Reproduce the query independently before reporting. |

## DP-3 · after WO-B's 21-day window — change the entry mechanism?

**The threshold, precomputed and verified:**

```
Switching entry maker -> taker costs 6 bps.
In win-rate terms, at W = 1.818R:
    at  67 bps stop  ->  3.18 pp
    at 120 bps stop  ->  1.77 pp

DECISION RULE:
  IF the CI lower bound of (market_at_signal_WR − post_only_resting_WR),
     from the PAIRED McNemar comparison,
     EXCEEDS 3.18 pp (or 1.77 pp at the wider stop):
       -> the fee swap pays for itself with evidence
       -> amend RC3 law 14's ENTRY half via signed spec-amendment PR
       -> promote ENTRY_MARKET_AT_SIGNAL to money-eligible by ceremony

  ELSE:
       -> keep post-only resting entry
       -> the 13 pp is elsewhere; return to WO-A

REFERENCE (the estate's prior measurement, for orientation only —
           this decision is made on WO-B's data, not on these):
    resting ~28 % · confirmed ~46 % · market-at-signal ~51.5 %
    gap 23.5 pp  ->  7x to 13x the break-even threshold
```

**Note carefully:** the decision is made on WO-B's own paired data. The prior 23.5 pp figure sets expectations, it does not substitute for the measurement. If WO-B returns 4 pp, that still clears the threshold at 67 bps and the change is justified — just less dramatically. If it returns 2 pp, it does not clear at 67 bps but does at 120 bps, and the answer becomes stop-width-dependent.

---

# PART 4 — WHAT STAYS TRUE THROUGHOUT

| Plane | State for the entire programme |
|---|---|
| **SHADOW** | **LIVE. Fixed. No OFF control.** Grows on every refusal added by every work order. |
| **Existing estate money path** | **Armed.** Nothing in this sequence disarms it. Caps, kill, predicate and reconciler remain sovereign. |
| **TRIAD Origin V7 venue path** | `OFF` — never deployed. There is nothing to disarm. |
| **PAPER** | `OFF` until keyless isolation is proven. |

**Every mechanism added by this sequence is a gate that refuses one trade and records exactly why, with the counterfactual preserved in SHADOW.** None stops the engine. None reduces the evidence rate. They increase it.

---

*Prepared 2026-08-13 · master sequence v1.0.0 · anti-drift execution control · supersedes only the EXECUTION ORDER section of the repair work order · posture unchanged `OFF/OFF/OFF/LIVE` · no signature, pin, credential or receipt fabricated*
