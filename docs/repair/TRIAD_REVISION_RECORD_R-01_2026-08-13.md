# TRIAD — REVISION RECORD R-01

**Document ID:** `TRIAD-REVISION-RECORD-R-01-2026-08-13`
**Version:** `1.0.0`
**Prepared:** 2026-08-13
**Disposition:** `CORRECTION_RECORD / EVIDENCE / NOT_A_RATIFICATION / NO_RUNTIME_CHANGE`
**Amends:** `TRIAD_ORIGIN_V7_ERRATA_AND_CLARIFICATIONS_2026-08-13.md` · `TRIAD_ORIGIN_V7_GAP_REGISTER_2026-08-13.md` · `TRIAD_REPAIR_WORK_ORDER_2026-08-13.md`
**Occasioned by:** the implementing developer's cross-check against vendored master law, closed at remote head `e122e49`, tree clean, 12 gates green dual-seed, 3,149 tests.

**Convention.** Withdrawn items keep their bodies with a banner. Nothing is deleted, no identifier is reused, and no history is relabeled. This follows the estate's existing withdrawal record (`GEOM-LAW-01`, `UNI-01`); `ERR-02` is the third entry.

---

## 1 · WITHDRAWAL — `ERR-02` (F13 `RECLAIM_PENDING` extreme accrual)

```
╔════════════════════════════════════════════════════════════════════════╗
║  ERR-02 · WITHDRAWN 2026-08-13                                         ║
║  Reason: REVIEWER ERROR. The finding was wrong; the code is right.     ║
║  Body retained below unaltered, per withdrawal-record convention.      ║
║  DO NOT IMPLEMENT. DO NOT RE-RAISE without reading §1.3 first.         ║
╚════════════════════════════════════════════════════════════════════════╝
```

### 1.1 · What was claimed

That §R-F13's `RECLAIM_PENDING` state lacked an excursion-extreme update step, and that test T9 (*"new lower low during RECLAIM_PENDING via reset path — extreme updates; retained through CONFIRMED"*) was therefore unreachable. The proposed erratum inserted `(0.5) extreme := min(extreme, L_t)` into `RECLAIM_PENDING`, before the tau check.

### 1.2 · Why it was wrong

**Three independent reasons, any one of which is sufficient.**

**(a) The disambiguating phrase was in T9 itself and I read past it.** T9 says *"new lower low during RECLAIM_PENDING **via reset path**."* The reset path is step (3): the bar fails the hold, the machine returns to `EXCURSION`, and **subsequent** bars deepen the extreme as `EXCURSION` bars. T9 is fully satisfiable with no update inside `RECLAIM_PENDING`. I read *"during RECLAIM_PENDING"* as *"while in that state"* when it means *"in the episode that passed through it."*

**(b) The CORRECTED LAW is explicit about scope.** It reads `E = min over **excursion-phase** bar lows`. A bar processed while the machine sits in `RECLAIM_PENDING` is not an excursion-phase bar. The proposed change would have silently widened the definition of "excursion phase" to mean "the whole occurrence."

**(c) Two passing tests already pinned the correct behaviour.** `test_hold_bars_do_not_deepen_the_extreme` and `test_h10…deepens…first` are not obstacles to the fix — **they are the law, transcribed.** A finding that requires flipping a passing test to be true is a finding under suspicion.

### 1.3 · Severity of the near-miss, stated honestly

Had the erratum been implemented as written:

- `extreme` and `excursion_depth_ticks` would have changed value on the reset path.
- Both are **mandatory outputs consumed by F18 stop logic** (§R-F13 says so explicitly).
- Different extreme → different stop → different `stop_bps` → different `cost_R` → different `p_BE`.
- A passing test would have been flipped to accommodate a wrong finding, destroying the evidence that the original behaviour was correct.
- The change would have landed under agent authority, without a signature, altering formula-emitted bytes.

**This is the precise defect class the entire repair programme exists to eliminate**, and it was introduced by the audit rather than found by it.

### 1.4 · The developer's disposition was correct on every count

| Judgement | Assessment |
|---|---|
| Refused to implement | **Correct** |
| Refused to modify the passing tests | **Correct** |
| Classified it as an amendment, not a repair | **Correct** |
| Reserved it for owner signature plus a spec-amendment PR | **Correct** |
| Added an honest note at the code site | **Correct** |
| Recorded it rather than silently dropping it | **Correct** |

**No further action is required on ERR-02.** It does not need a D-21 signature, because there is nothing to sign — the finding is withdrawn, not deferred.

### 1.5 · One constructive residual — documentation only, not a formula change

A genuine one-bar boundary exists and is currently decided **implicitly** by state-machine ordering rather than stated: the reset bar's *own* low. At bar `t`, the machine is in `RECLAIM_PENDING`, `C_t` fails the hold, and the machine returns to `EXCURSION` — but bar `t`'s low is never applied to the extreme, because `EXCURSION` processing begins at `t+1`.

**The developer's reading is correct and should stay.** But it is currently a consequence of ordering rather than a stated rule, which is how this finding got raised in the first place and how it will get raised again.

**Proposed — a test that codifies the existing behaviour and changes no bytes:**

```
test_reset_bar_low_is_not_applied_to_extreme

  Setup:  machine in RECLAIM_PENDING at bar t
          C_t fails the hold predicate
          L_t < current extreme          (a genuinely lower low on the reset bar)

  Assert: extreme UNCHANGED at t
          bar t+1, now in EXCURSION, deepens the extreme normally

  Docstring must name ERR-02 and state: the reset bar is not an
  excursion-phase bar; its low is excluded by the CORRECTED LAW's scope.
```

**Classification:** this is a **repair** under `LAW-9`, not an amendment — it changes no emitted bytes and flips no passing test. It may land under agent authority. It is optional; its only purpose is to stop this question being re-litigated.

**If the estate ever wants to *test* the deeper-accrual behaviour**, it is a `level_excursion_reclaim.closed.v3` **research identity** under §1.5 version discipline — never an amendment to v2. Both readings produce different stop widths on the reset path; under the fee law that means different `cost_R`; which makes it a measurable question rather than a doctrinal one. That is the right way to settle it.

---

## 2 · NEW STANDING LAW — `LAW-9`, derived from the ERR-02 near-miss

The near-miss is more valuable than the finding would have been, because it generalises. `LAW-9` is now standing law and is specified in full in `TRIAD_MASTER_SEQUENCE_2026-08-13` §0.3.

**Summary.** When any external finding proposes a change that would flip a passing test:

1. **STOP.** Do not implement. Do not modify the test.
2. Read the **vendored master law** — not the finding's restatement of it.
3. Route: code contradicts master law → **repair**, agent authority. Finding contradicts master law → **amendment**, owner signature plus spec-amendment PR. Master law genuinely ambiguous → **owner-gated**, record both readings, do not pick.
4. **The discriminator when unclear:** does the change alter the emitted bytes of a formula? If yes → **amendment, always, no exceptions**, regardless of how obviously correct the change appears.
5. Record the disposition **at the code site**, naming the finding ID and the reason.

**Why the discriminator is bytes rather than correctness.** An agent that believes a change is obviously correct is exactly the agent most likely to be wrong, because obviousness is what suppresses the check. Byte-level change is objective and mechanically detectable. "Correct" is a judgement the agent is not authorised to make alone.

---

## 3 · DISPOSITION LEDGER — every finding, current state

### 3.1 · Errata (Origin scope, D-21)

| ID | Finding | Disposition | State |
|---|---|---|---|
| **ERR-01** | F10 FVG state predicates overlap; T4 contradicts the state block | Module already implemented the mutually-exclusive reading (following the **ratified T4 row, which is normative**). Property test `TestErr01MutuallyExclusiveStates` added — 10⁵ random `pen`, exactly one predicate true, `_state_for` agrees. Docstring tightened. | **CLOSED in code.** Spec-text amendment still requires D-21 signature. |
| **ERR-02** | F13 `RECLAIM_PENDING` extreme accrual | **Reviewer error.** Code faithfully implements the vendored CORRECTED LAW. | **WITHDRAWN.** §1 above. |
| **ERR-03** | F12 confirms on `GENERIC_BREAK` while F08 refuses | Trial-identity partition. A/B/C options presented; **B recommended, not selected.** Honest note added at the code site. | **OWNER_GATED on D-17.** Correctly unpicked. `SYNC-4` applies: must land before any CAP-01 shadow row. |

### 3.2 · Cross-check findings (CHK-01 … CHK-08) — routed by ownership

| ID | Finding | Owner | State |
|---|---|---|---|
| CHK-01 | RR floor 2.5 → 2.0 | **E07 decides.** Origin's part is D-11 (F18 refusing-in-place) | See §4, `CORRECTION-02` |
| CHK-02 | No fee-net admission predicate | **E07** — Origin must not build it | See §4, `CORRECTION-01` |
| CHK-03 | 45 bps stop floor homeless | **E07** — RC3 law 07 bars it from E02 | D-13, owner |
| CHK-04 | Law 14 maker-only contradicted | **E09 exit / L2 entry arms** | D-14, owner |
| CHK-05 | 3 of 5 capsules blocked | **Owner sequencing decision** | D-16, owner |
| CHK-06 | Estate P1 not carried into V7 gate ladder | **Estate / L6** | D-18, owner |
| CHK-07 | RC4 measurement→money disarm coupling | **Owner** | D-15, owner |
| CHK-08 | `MIN_NOTIONAL` possibly hardcoded | **E08 / L1** | D-19, D-20, owner |

### 3.3 · Gap register additions (GAP-43 … GAP-50) — routed

| ID | Finding | Owner | Work order |
|---|---|---|---|
| GAP-43 | ~13 pp of win rate lost between signal and money | L2 | WO-A |
| GAP-44 | Counterfactual scores only the filled subset; `no_fill` = 46.6 % of fillable | L2 | WO-A A1 |
| GAP-45 | Maker-only entry law is the largest identified EV destroyer | L2 → owner | WO-B → D-14 |
| GAP-46 | Generation/admission RR floor mismatch (2.0 vs 2.5) | L3 | WO-C |
| GAP-47 | Two risk denominators; every `R` figure ambiguous | L2 | WO-A A2 |
| GAP-48 | Comparator built, never run | L2 | WO-D |
| GAP-49 | Three stop regimes coexist (67–120 / 45 / 10 bps) | L2 → L3 | WO-A A3 |
| GAP-50 | Capsule semantic mapping refused, not established | L4 → owner | WO-D D2 |

---

## 4 · CORRECTIONS CARRIED FORWARD

Both were recorded in the gap register addendum on 2026-08-13 and are restated here so the revision record is self-contained.

### `CORRECTION-01` · The estate **has** a fee-net gate. Origin V7 is a regression against it.

**The earlier claim** (audit §04, GAP-01): *"There is no layer at which a trade is refused for being unprofitable."*

**Too strong. The accurate version is worse.** The live executor governor runs 14 checks and its refusal histogram shows `net_rr_floor` firing **44** times and `stop_bounds.min_width_bps` firing **76** times — and the latter killed both of the estate's takes. **Those are working fee-net admission gates.**

**The corrected finding:** the *live estate* has an economic admission gate that works. **TRIAD Origin V7 has none** — RC3 law 07 bars it from E02, TBD-011 leaves E07's version unspecified. **Migrating from Engine to Origin as specified would remove the only working economic gate in the estate.**

**Consequence for the work order:** `WO-F` is not "invent a gate." It is **"port the gate that already works into E07, improve it with the cost model, and do not lose it in the migration."** That reframing is now in the work order text.

### `CORRECTION-02` · The estate runs two RR floors simultaneously

| Layer | Floor | Source |
|---|---:|---|
| TriadEngine generation | **2.0** | `GROSS_RR_FLOOR`, compiled `LazyLock<Decimal>` |
| TriadOrigin F18 | **2.0** | RC2 §F18, *"RR floor fixed at 2.0"* |
| Executor governor admission | **2.5** | `per_trade.gross_rr_floor` |

**Generation frames at 2.0; admission demands 2.5. The engine manufactures candidates its own governor is obliged to reject.** The 44 `net_rr_floor` refusals are that collision, printing.

The fix is not "pick 2.0 or 2.5" — both are unjustified constants. **Derive the floor from the cost model** so that a cell demonstrating a higher win rate earns a lower floor, and a weak cell is held to a higher one. `WO-C`.

---

## 5 · OWNERSHIP BOUNDARY REROUTE

The original work order set assigned Origin work that Origin must not do. The developer caught this. **The corrected routing is now `TRIAD_MASTER_SEQUENCE_2026-08-13` §1.2 and is binding.**

**The scheduling consequence, restated because it is the practical outcome of this whole revision:**

```
Origin's outstanding queue after ERR-01 closure and ERR-02 withdrawal:

    WO-J   RPI coverage clause          READY, 3 days   <- the only substantive item
    WO-I   ERR-03 F12 split identity    OWNER_GATED on D-17
    WO-C   (check only) confirm F18 emits the exact unreduced RR pair
           regardless of floor outcome, so E07 can re-derive

    That is the complete list.

Everything on the critical path is now L1 (E09/box), L2 (Learning) and
L3 (E07/E08). The bottleneck has moved off Origin entirely.

DO NOT MANUFACTURE ORIGIN WORK TO FILL THE GAP. An idle correct lane is
a finished lane.
```

---

## 6 · SUPERSESSION MAP

| Document | Status after R-01 |
|---|---|
| `TRIAD_ORIGIN_V7_ERRATA_AND_CLARIFICATIONS_2026-08-13.md` | In force **except** §2 `ERR-02`, which is **WITHDRAWN**. `ERR-01` marked **CLOSED**. `ERR-03` marked **OWNER_GATED**. |
| `TRIAD_ORIGIN_V7_GAP_REGISTER_2026-08-13.md` | In force, including Addendum A. `GAP-12` (the ERR-02 gap) is **WITHDRAWN** with this record as its reference. |
| `TRIAD_REPAIR_WORK_ORDER_2026-08-13.md` | In force **except** its `EXECUTION ORDER` section, superseded by `TRIAD_MASTER_SEQUENCE_2026-08-13` Part 1. `WO-H` is **WITHDRAWN**; its identifier is retired permanently and may not be reused. |
| `DECISIONS-REQUIRED-v2.0.md` | In force. **D-21's ERR-02 clause is void** — nothing to sign there. D-21's ERR-01 clause remains open (spec-text amendment). |
| `TRIAD_ORIGIN_V7_INDEPENDENT_AUDIT_AND_SCORECARD_2026-08-13.html` | In force with two amendments: §04's *"no layer"* claim is corrected by `CORRECTION-01`; §07's ERR-02 entry is **WITHDRAWN**. The composite score is unaffected — ERR-02 was one of three contributors to a −1.0 on D4, and the other two stand. |
| `TRIAD_MASTER_SEQUENCE_2026-08-13.md` | **New. In force.** Sequencing control and `LAW-9`. |
| `TRIAD_REVISION_RECORD_R-01_2026-08-13.md` | **This document. In force.** |

---

## 7 · ATTESTATION BOUNDARY

Recorded per `LAW-8`, without implying doubt.

| Claim | Status to this reviewer |
|---|---|
| Remote head `e122e49`, tree clean | **Source claim** — not independently verified |
| 12 gates green, dual-seed, 3,149 tests | **Source claim** — not independently rerun |
| `TestErr01MutuallyExclusiveStates` passes | **Source claim** — not independently rerun |
| B03C golden-home integration, +7 additive walks | **Source claim** — not independently rerun |
| PR #36 remains DRAFT, no merge | **Source claim** |
| Posture `OFF/OFF/OFF/LIVE`, nothing armed or signed | **Source claim** |
| RC1–RC4 and rc3/rc4/rc5 bundle bytes untouched | **Source claim** |
| ERR-02's reasoning against the vendored law | **Independently verified by this reviewer.** The developer's reading is correct. |

Repository presence, a green local test, a merged PR, and a running deployment remain four separate claims requiring four separate proofs. **Runtime state this session: `NOT_ATTESTED`.**

---

## 8 · THE NEXT ACTION IS UNCHANGED

`WO-00` — a 30-minute read-only probe of the box — runs before everything else in every lane.

Binance moved conditional orders to a separate Algo Service effective **2025-12-09**. `POST /fapi/v1/order` now rejects `STOP_MARKET` with `-4120 STOP_ORDER_SWITCH_ALGO`. RC3 knows; RC4 and the Formula Repair Specification have zero references, and no document in the corpus names the endpoints, the error code, the 200-order cap, or the constraint that *"modification of untriggered conditional orders is not supported."*

**If the executor still places protective stops through the old endpoint, every stop placement has been failing silently since December, and that outranks every other item in either register — including the 13 percentage points.**

---

*Prepared 2026-08-13 · revision record R-01 · one withdrawal, one new standing law, two corrections, one ownership reroute · posture unchanged `OFF/OFF/OFF/LIVE` · no signature, pin, credential or receipt fabricated · runtime state `NOT_ATTESTED`*
