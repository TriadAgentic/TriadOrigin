# TRIAD — THE STRUCTURAL DEFECT REPAIR

**Document ID:** `TRIAD-STRUCTURAL-REPAIR-2026-08-13`
**Version:** `1.0.0`
**Prepared:** 2026-08-13
**Directive:** *"Ignore the fees. Let's do the structural defect repair."*
**Disposition:** `WORK_ORDER_SET / EXECUTION_GRADE / NOT_A_RATIFICATION / NO_RUNTIME_CHANGE`
**Posture:** unchanged. `OFF/OFF/OFF/LIVE` · `DENIED_SAFE_HOLD`. Every mechanism below narrows or asserts. Nothing is disarmed.

---

# PART 0 — HOW I READ THE DIRECTIVE

**"Ignore the fees" is read as: stop optimising the fee term, fix the architecture that lets it — and eleven other constants — sit unchecked.** It is *not* read as "remove cost from the analysis." That reading would be the one error this estate has already paid for, in its own words: *"a zero-fee backtest is not a backtest. It is a chart of what the price did."*

**The structural repair does not abandon the fee finding. It makes the fee finding permanent by construction.** After this work, `H` stops being a number someone remembers to check and becomes a measured input the system cannot violate. That is how you stop thinking about fees — not by ignoring them, but by making them impossible to get wrong.

If the directive genuinely meant "exclude cost from the model," say so and I will argue the other side properly. Everything below assumes it did not.

---

# PART 1 — THE META-DEFECT, NAMED

Across this entire engagement, every serious finding has been the same defect wearing different clothes.

```
  ╔══════════════════════════════════════════════════════════════════╗
  ║  UNRECONCILED CONSTANTS                                          ║
  ║                                                                  ║
  ║  A value exists in two or more places.                           ║
  ║  Each was set independently, by a different person,              ║
  ║  at a different time, for a different reason.                    ║
  ║  No mechanism forces them to agree.                              ║
  ║  No mechanism even compares them.                                ║
  ║  The tighter one wins silently.                                  ║
  ║  Nobody notices, because the losing constant still LOOKS active. ║
  ╚══════════════════════════════════════════════════════════════════╝
```

**Ten instances found. Every one of them was discovered by arithmetic, not by any alarm the system raised.** That is the actual defect: not any single wrong number, but the absence of a mechanism that would have caught any of them.

A second, related class — **VACUOUS GATES** — accounts for four more findings: checks that return the same answer regardless of input, and therefore carry zero information while appearing to be enforcement.

**Both classes share one signature: a mechanism that looks like it is doing work and is not.**

---

# PART 2 — CLASS A REGISTER · UNRECONCILED CONSTANTS

| ID | Value | Site A | Site B | Site C | Who wins | Observed consequence |
|---|---|---|---|---|---|---|
| **UC-01** | RR floor | Engine `GROSS_RR_FLOOR` **2.0** | Origin F18 **2.0** | governor `gross_rr_floor` **2.5** | 2.5 | **44 `net_rr_floor` refusals.** Generation manufactures what admission must reject. |
| **UC-02** | stop width | Engine band **67–120** | governor `min_stop_width_bps` **45** | bank median **10.0** | 45 | **76 `stop_bounds` refusals; both live takes died here.** The bank scores a geometry no layer would authorise. |
| **UC-03** | position size | `risk_pct_equity` **1.0 %** | `max_margin_pct` **1 % × 15x = 15 %** | venue `MIN_NOTIONAL` | margin cap | **Effective risk 0.0675 %, 14.8× below policy, at every equity level.** `risk_pct_equity` is dead configuration. |
| **UC-04** | cost ceiling | `MAX_COST_R` **1/5** (implied by 45 = 9/0.2) | measured gross edge **0.1991** | — | tie | **Fees permitted to consume 100.5 % of the measured edge.** The ceiling was set exactly at ruin. |
| **UC-05** | throughput | admission **8.4/min** | judge capacity **12.4/min** | arrival **35.7/min** | admission | **76.5 % of all signal discarded** before anyone forms an opinion. The judge idles at 68 % utilisation. |
| **UC-06** | side policy stage | documented: **money-eligibility** filter | observed: **selection** stage | — | selection | **30,357 shadow shorts, zero judged shorts.** The policy forecloses the evidence needed to revise it. |
| **UC-07** | fee constant | `H` **9 bps** blended | maker **2.0** / taker **4.5** per side | execution path **unknown** | assumed 9 | Cost term possibly wrong by 2.5 bps = **0.056 R per trade**. |
| **UC-08** | min notional | ops guide **$20** | venue filter **5 USDT** | limits config **"5"** | unknown | Executor may be enforcing an **invented number** — forbidden by RC3 law 20. |
| **UC-09** | merge gate | combined check **exists** | **not a required** status check | — | not required | `mergeable_state = unstable`. **"12 gates green" and "merged to main" are causally independent.** |
| **UC-10** | lint baseline | **281 pre-existing** errors | **0** expected | — | neither | Check red before and after every change. **Zero information content.** |

## The two rows that matter most

**`UC-04` is the one that produced the breakeven book.** `MIN_STOP_WIDTH = H / MAX_COST_R = 9 / 0.2 = 45 bps`. Nobody chose 45 — it fell out of a `MAX_COST_R` of one fifth, and one fifth was never checked against the thing it constrains. The measured gross edge is `0.1991 R`; the permitted cost is `0.2000 R`. **The ceiling and the edge are equal to three decimal places, by coincidence, and that coincidence is the entire P&L.**

**`UC-06` is the one that compounds.** A policy applied at selection instead of money-eligibility means shorts are never judged, so no evidence about shorts accumulates, so the policy that excludes shorts can never be revisited on evidence. **It is the only defect in this register that actively prevents its own repair.**

---

# PART 3 — CLASS B REGISTER · VACUOUS GATES

A gate that returns the same answer regardless of input is not a gate.

| ID | Gate | Why it is vacuous | Fix |
|---|---|---|---|
| **VG-01** | F15 coverage ratio | Numerator and denominator **share the RPI exclusion**, so the ratio reads ~1.0 regardless of true completeness | `WO-J` (owner amendment) — emit `NULL{COVERAGE_UNVERIFIABLE_RPI}` rather than a computed lie |
| **VG-02** | `get_sim_gap` verdict `HONEST` | `real_fills = 0`, so nothing can disagree. Mission Control already flags it: *"verdict:HONEST-is-vacuous"* | Refuse to emit a verdict below a minimum `real_fills`; return `INSUFFICIENT_EVIDENCE` |
| **VG-03** | `main` combined check | Red before and after every change (281 baseline). Cannot attribute anything | `WO-S6` — baseline + ratchet |
| **VG-04** | `matrix_off = 0` | Reads as "the matrix is not switching short off," which is **true and irrelevant** — the suppressor is elsewhere. A green light on a control that was never the control | Name the actual stage in the census output |

**`VG-04` deserves a note.** It is the subtlest of the four: a check that is *correct*, *passing*, and *measuring the wrong thing*. It sent the investigation looking at `side_weight` for a suppressor that was never there. **A gate that is right about an irrelevant question is worse than a gate that is missing, because it consumes the attention that would have found the real one.**

---

# PART 4 — THE REPAIR PATTERN

Every instance above is repaired by the same four moves. **Apply them uniformly; do not invent a bespoke fix per instance.**

```
  ┌─ 1 · SINGLE AUTHORITY ─────────────────────────────────────────┐
  │  Exactly ONE site owns each value. Every other site that needs │
  │  it READS it. No site may define a second copy.                │
  └────────────────────────────────────────────────────────────────┘
  ┌─ 2 · DERIVE, DON'T PICK ───────────────────────────────────────┐
  │  If a value can be computed from measured inputs, it is        │
  │  COMPUTED. A hand-picked constant is permitted only when it    │
  │  encodes a genuine owner preference with no measurable         │
  │  correct answer.                                               │
  └────────────────────────────────────────────────────────────────┘
  ┌─ 3 · ASSERT AT EVERY OTHER SITE ───────────────────────────────┐
  │  Sites that consume the value ASSERT agreement with the        │
  │  authority at boot and refuse to start on mismatch. Silent     │
  │  divergence becomes impossible rather than merely discouraged. │
  └────────────────────────────────────────────────────────────────┘
  ┌─ 4 · CI RATCHET ───────────────────────────────────────────────┐
  │  A test enumerates every constant in the estate and FAILS the  │
  │  build if a new hand-picked value appears. The count may never │
  │  increase on merge — the estate's own param-census law,        │
  │  extended from detectors to constants.                         │
  └────────────────────────────────────────────────────────────────┘
```

## The derivation tree

**Twelve hand-picked constants collapse to three genuine free parameters.**

```
ROOTS — measured or genuinely chosen, nothing else
  H_bps            <- venue fee schedule x actual execution path      MEASURED
  p_cell, W_cell   <- per-cell outcome statistics                     MEASURED
  venue filters    <- exchangeInfo (MIN_NOTIONAL, LOT_SIZE, tick)     READ, never written
  p50_judge_ms     <- the decisions ledger                            MEASURED
  ─────────────────────────────────────────────────────────────────
  EV_TARGET_R      <- owner risk/return appetite                      OWNER
  risk_pct_equity  <- owner risk appetite                             OWNER
  MARGIN           <- statistical safety margin on p_cell             OWNER

DERIVED — every one of these is a hand-picked constant TODAY
  gross_edge          = p·W − (1−p)
  MAX_COST_R          = gross_edge − EV_TARGET_R
  MIN_STOP_WIDTH_BPS  = H_bps / MAX_COST_R
  cost_R              = H_bps / stop_bps
  RR_min              = (1 + cost_R) / (p_cell − MARGIN) − 1
  max_margin_pct·lev  = risk_pct_equity / min_stop_frac      (outer bound, never binding)
  judge_capacity      = 60000 / p50_judge_ms × concurrent_slots
  admission_rate      = judge_capacity                       (equal, by construction)
  min_notional        = venue filter                         (read, never written)
```

### What the tree produces at today's measured inputs

`gross_edge = +0.1991 R`

| `EV_TARGET_R` | `MAX_COST_R` | `MIN_STOP` @ H=6.5 | `MIN_STOP` @ H=9 |
|---:|---:|---:|---:|
| +0.05 R | 0.1491 | 43.6 bps | 60.4 bps |
| **+0.10 R** | **0.0991** | **65.6 bps** | **90.9 bps** |
| +0.15 R | 0.0491 | 132.5 bps | 183.5 bps |
| +0.20 R | — | **impossible — cost cannot go below zero** | — |

**The last row is the tree telling you something no constant ever could:** at the currently measured gross edge, `+0.20 R` net is unreachable by *any* cost setting. It requires `p` or `W` to move. **A derived system tells you when you have run out of road. A hand-picked one lets you keep turning the dial.**

### Sizing

```
for the RISK policy to bind rather than the margin cap:
    max_margin_pct × leverage  ≥  risk_pct_equity / min_stop_frac
                               ≥  0.01 / 0.0045  =  222.2 %

today:  1 % × 15x = 15 %   ->  short by 14.8×
```

| Combination | Product | Satisfies |
|---|---:|---|
| 1 % × 15x — **today** | 15 % | **no — margin cap binds** |
| 15 % × 15x | 225 % | yes |
| 25 % × 10x | 250 % | yes |
| 10 % × 25x | 250 % | yes |
| 3 % × 75x | 225 % | yes |

**Note what this table is not.** It is not a recommendation to lever up. It is a statement that **the current pair is incoherent** — one of the two constants is not doing what its name says. Choosing which one is authoritative is `D-23`, an owner decision, and either answer is defensible. **What is not defensible is leaving both in place while only one has effect.**

---

# PART 5 — WORK ORDERS

Standard header applies. `WRITABLE PATHS` is an allowlist; anything outside is a stop condition.

---

## `WO-S1` · THE CONSTANT REGISTRY · **the foundation. Build this first.**

```
OWNER LANE     estate-wide (Intelligence owns the file; all repos read it)
WRITABLE       contracts/schemas/constant_registry.v1.json
               src/*/constants/registry_reader.*
               tests/constants/*
FORBIDDEN      changing any constant's VALUE in this work order.
               This WO makes values visible and asserted. It changes none.
ENTRY GATE     none
EXIT GATE      every constant in Part 2 appears in the registry with exactly
               one AUTHORITY site and N asserting sites
DURATION       4 days
```

### The contract

```json
{
  "schema": "triad/constant_registry/1",
  "ratified_by": "PENDING",
  "constants": [
    {
      "id": "MIN_STOP_WIDTH_BPS",
      "kind": "DERIVED",
      "derivation": "H_BPS / MAX_COST_R",
      "authority": "E07",
      "consumers": ["engine.scan_gate", "executor.governor", "origin.F18"],
      "current_value": {"num": 45, "den": 1},
      "status": "PROPOSED_MUST_RATIFY"
    },
    {
      "id": "RISK_PCT_EQUITY",
      "kind": "OWNER_CHOICE",
      "derivation": null,
      "authority": "activation_policy",
      "consumers": ["executor.sizing"],
      "current_value": {"num": 1, "den": 100},
      "status": "RATIFIED"
    }
  ]
}
```

**`kind` is one of exactly three values, and this is the whole point of the work order:**

| `kind` | Meaning | Permitted? |
|---|---|---|
| `MEASURED` | read from a venue, a ledger, or a bank | always |
| `DERIVED` | computed from other registry entries via a stated formula | always |
| `OWNER_CHOICE` | a genuine preference with no measurable correct answer | **only with a written justification field** |

**Any constant that is none of these three is a defect.** Today the estate has twelve of them.

### The boot assertion

```python
def assert_constant_agreement() -> None:
    """Called at process boot in EVERY repo. Refuses to start on mismatch."""
    reg = load_registry()
    for c in reg.constants:
        if c.authority_site == THIS_SITE:
            continue
        local = read_local_value(c.id)          # None if this site doesn't hold one
        if local is None:
            continue                            # correct — it reads, it doesn't define
        if local != c.current_value:
            raise ConstantDivergence(
                code="CONSTANT_DIVERGENCE",
                constant=c.id, authority=c.current_value,
                local=local, site=THIS_SITE,
            )
```

**`ConstantDivergence` is a refusal to start, not a warning.** Under `LAW-7` this does not disarm anything — a process that cannot agree on its own constants was never safely armed.

### Tests

| # | Scenario | Expected |
|---|---|---|
| T1 | Two sites, same value | boot clean |
| T2 | Two sites, different values | `CONSTANT_DIVERGENCE`, process refuses to start |
| T3 | Consuming site holds no local copy | clean — reading is correct |
| T4 | Registry entry `kind` outside the three | schema validation **fails** |
| T5 | `OWNER_CHOICE` without a justification field | schema validation **fails** |
| T6 | `DERIVED` whose formula references an absent id | schema validation **fails** |
| T7 | The registry loaded against today's real values | **`UC-01` … `UC-08` all fire.** This test is the proof the registry works. |

**T7 is the acceptance criterion for the whole work order.** If the registry does not immediately surface all eight known divergences, it is not built correctly.

**DRIFT TRAPS**

> **Trap 1 — "I'll fix the divergences while I'm here."** No. This work order makes them *visible*. Fixing each one is `WO-S2` … `WO-S5`, and several require owner signature. A registry that reports zero divergences on day one has been built to hide them.
>
> **Trap 2 — "I'll pick the value that looks right."** No. The registry records what each site currently holds. Choosing the authority value is a separate, owner-gated act.
>
> **Trap 3 — "Floats are fine for a config file."** `LAW-1`. Exact rational pairs. `45` is `{"num": 45, "den": 1}`.

---

## `WO-S2` · DERIVE `MAX_COST_R` AND `MIN_STOP_WIDTH_BPS` · closes `UC-02`, `UC-04`

```
OWNER LANE     E07
WRITABLE       src/*/admission/cost_floor.*  ·  tests/admission/*
FORBIDDEN      engine scan_gate band, origin F18 — they must READ, not define
ENTRY GATE     WO-S1 landed; H_BPS registered as MEASURED
EXIT GATE      MIN_STOP_WIDTH_BPS is DERIVED; no site holds a literal 45
DURATION       2 days
```

```
MAX_COST_R          = gross_edge − EV_TARGET_R
MIN_STOP_WIDTH_BPS  = H_BPS / MAX_COST_R

gross_edge = p_cell·W_cell − (1 − p_cell), computed per cell from the bank,
             refusing with INSUFFICIENT_CELL_EVIDENCE below MIN_CELL_N.

EV_TARGET_R : OWNER_CHOICE, MUST_RATIFY, proposed +0.10 R
              justification field REQUIRED — this is a genuine preference.

GUARD, mandatory:
    if MAX_COST_R <= 0:
        REFUSE{EV_TARGET_UNREACHABLE, gross_edge, EV_TARGET_R}
    # fires whenever the target exceeds the measured gross edge.
    # At today's +0.1991 R gross, any target >= +0.20 R refuses.
    # This is the system telling you that no stop width will save it.
```

**Golden vectors — computed, verify against these exactly:**

| `gross_edge` | `EV_TARGET_R` | `MAX_COST_R` | `H` | `MIN_STOP_WIDTH_BPS` |
|---:|---:|---:|---:|---:|
| 0.1991 | 0.05 | 0.1491 | 6.5 | 43.6 |
| 0.1991 | 0.05 | 0.1491 | 9.0 | 60.4 |
| 0.1991 | 0.10 | 0.0991 | 6.5 | 65.6 |
| 0.1991 | 0.10 | 0.0991 | 9.0 | 90.9 |
| 0.1991 | 0.20 | **≤ 0** | — | **`REFUSE{EV_TARGET_UNREACHABLE}`** |

---

## `WO-S3` · ONE RR FLOOR · closes `UC-01`

```
OWNER LANE     E07 decides; Engine and Origin become read-only consumers
WRITABLE       src/*/admission/rr_floor.*  ·  tests/admission/*
FORBIDDEN      adding any floor to a GENERATION module
ENTRY GATE     WO-S1, WO-S2 landed
EXIT GATE      static scan finds ZERO RR-floor literals in generation modules
DURATION       2 days
```

```
GENERATION (Engine, Origin F18):
    emit the exact unreduced RR pair. Apply NO floor. Generation must not
    know about cost (RC3 law 07). Emit everything; let admission decide.

ADMISSION (E07):
    RR_min = (1 + cost_R) / (p_cell − MARGIN) − 1
    the ONLY site that applies a floor.
    REFUSED_RR_BELOW_DERIVED_FLOOR{rr, rr_min, cost_R, p_cell}

CI:  static scan FAILS the build if GROSS_RR_FLOOR is read in any
     generation module.
```

**Effect:** the 44 `net_rr_floor` refusals become either admissions the cell has earned, or refusals with a reason a human can act on — instead of a collision between two arbitrary constants.

---

## `WO-S4` · RECONCILE SIZING · closes `UC-03` · **OWNER GATED**

```
OWNER LANE     owner decides (D-23); E08 implements
STATE          OWNER_GATED. An agent MAY NOT pick.
```

**Three lawful options. One must be signed.**

| Option | Change | Kind | Effect |
|---|---|---|---|
| **A** | Set `max_margin_pct × leverage ≥ 222 %` so the risk policy binds | **RISK WIDENING** — 14.8× per-trade exposure increase. **GOV-01 ceremony. Not a config tidy-up.** | `risk_pct_equity` becomes real |
| **B** | Restate `risk_pct_equity` to its true effective value (0.0675 %) | DOCUMENTATION. No ceremony. | Nobody reads 1.0 and believes it |
| **C** | Derive: `max_margin_pct × lev = risk_pct_equity / min_stop_frac` | agent-buildable **if** it reproduces today's effective number; **WIDENING** if it changes it | Cannot drift again |

**AGENT INSTRUCTION:** record all three as open. Do not implement. Do not pick "the safe one." A recommendation is not authority.

---

## `WO-S5` · RECONCILE THROUGHPUT · closes `UC-05`

```
OWNER LANE     Intelligence + operator
WRITABLE       config/admission_rate.*  ·  tools/build_capacity_profile.py
ENTRY GATE     p50 judge latency measured (done: 4,842 ms)
EXIT GATE      admission_rate == judge_capacity, both derived, neither picked
DURATION       1 day + on-box profile
```

```
judge_capacity = 60000 / p50_judge_ms × concurrent_slots
admission_rate = judge_capacity            (equal BY CONSTRUCTION)

today:   1 slot @ 4,842 ms -> 12.4/min.  admission is 8.4.  32 % of capacity wasted.
arrival: 35.7/min -> requires 2.9 slots.

  slots   capacity     covers arrival?
    1      12.4/min          no
    2      24.8/min          no
    3      37.2/min          YES
    4      49.6/min          headroom
```

**Do not tune latency in this work order.** The judge has 48 % headroom above what it is being fed. Optimising a non-binding constraint returns nothing. Raise admission to capacity, add slots, *then* look at p50.

**Count killed judgments separately.** `p99 = 12,000 ms` exactly is a timeout cap firing, not a natural tail — 1 % of judgments are being killed, and a killed judgment is a different event from a slow one. Folding them together understates both the latency distribution and the loss rate.

---

## `WO-S6` · RESTORE THE VACUOUS GATES · closes `UC-09`, `UC-10`, `VG-02`, `VG-03`

```
OWNER LANE     estate-wide CI
WRITABLE       .github/workflows/*  ·  ruff baseline file  ·  tools/gate_ratchet.py
FORBIDDEN      mass-fixing the 281 lint errors in this work order
DURATION       1 day
```

```
1 · BASELINE the 281 existing ruff findings into a frozen allowlist.
    The check then fails ONLY on NEW findings. Signal restored today;
    debt untouched.

2 · RATCHET: the baseline count may never increase on merge.
    This is the estate's OWN param-census law, extended from detectors
    to lint. Same mechanism, same enforcement.

3 · get_sim_gap: refuse to emit a verdict below MIN_REAL_FILLS.
    Return INSUFFICIENT_EVIDENCE{real_fills, required}.
    A verdict computed on zero fills is not conservative — it is false.

4 · Burn the 281 down separately, on its own schedule. NOT on the
    critical path. NOT this week.
```

**`UC-09` — the required-check gap — is not in scope here.** Installing the no-bypass `main` ruleset is one of the four B00R owner acts (`WO-P` / `D-3`). Flagged, routed, not built. Until it lands, *"12 gates green"* and *"merged to main"* remain independent facts.

---

## `WO-S7` · NAME THE SIDE-POLICY STAGE · closes `UC-06` · **highest-value read in the register**

```
OWNER LANE     Engine + Intelligence + Executor
WRITABLE       diagnostic output only in phase 1 — NO behaviour change
ENTRY GATE     none
EXIT GATE      the stage at which the side filter applies is NAMED in the census
DURATION       2 hours to answer; the fix depends on the answer
```

**Phase 1 — read the four named sites and answer one question.**

```
  is_money_live_candidate
  _money_live_candidate
  LiveEligibilityConfig side sets
  LaneRegistry::live_eligible

QUESTION: is the side filter applied at SELECTION, or at MONEY ELIGIBILITY?

Evidence for SELECTION:  gateway census per_symbol_selection sides = {'long': 27}
Evidence for the DOC:    unlock plan §3b says shorts are "shadow-only",
                         i.e. generated, JUDGED, measured, but not funded.

IF SELECTION:
  - shorts are never judged  ->  30,357 shadow shorts, ZERO judged shorts
  - EVERY judge statistic in this estate is LONG-ONLY and must be relabelled,
    including the +10.87 pp lift
  - the policy forecloses the evidence needed to revise it

  MINIMUM REPAIR: move the filter to MONEY ELIGIBILITY, where it is documented
  to be. Shorts are then judged and measured, and remain unfunded.
  KIND: this is NARROWING-NEUTRAL for money — no short gains funding.
        It widens only the EVIDENCE plane. No GOV-01 ceremony required.
```

**That last line is the point.** Moving the filter from selection to money-eligibility funds nothing new. It only lets the estate *learn about* the side it has decided not to trade. **A policy you cannot gather evidence against is not a decision, it is a permanent condition** — and un-making it costs nothing but a code move.

**Phase 2 — relabel.** Until Phase 1 answers, stamp every judge statistic in the estate `SCOPE: LONG_ONLY`. Including the +10.87 pp lift. Including everything in the WO-A report.

---

# PART 6 — THE MECHANISM THAT PREVENTS RECURRENCE

Everything above repairs ten instances. **This prevents the eleventh.**

```
tools/constant_census.py            (mirrors the existing param census)

  1 · Walk every repo. Extract every numeric literal that reaches a
      decision path — thresholds, floors, caps, rates, widths.
  2 · Join against constant_registry.v1.json.
  3 · Classify each:
        REGISTERED_DERIVED       ok
        REGISTERED_MEASURED      ok
        REGISTERED_OWNER_CHOICE  ok — justification field required
        UNREGISTERED             <- DEFECT
  4 · HARDCODED count may never increase on merge.
      New code ships census-clean.

  CI stage: REQUIRED (once the main ruleset lands under WO-P).
```

**This is not a new invention.** The estate already runs `triad_param_census.py` with a `CONFIGURED / HARDCODED / MIXED-ABS-REL` classification and a ratchet law. `WO-S8` extends the same mechanism from detector parameters to estate constants. **The tool, the pattern, and the law already exist — they were simply never pointed at this class of value.**

---

# PART 7 — SEQUENCE

```
WEEK 1
  WO-S7 phase 1   name the side-policy stage        2 hours   <- do this first
                  (cheapest, highest-value, may relabel every statistic
                   in the estate)
  WO-S1           the constant registry             4 days
                  acceptance = UC-01..UC-08 all fire on day one

WEEK 2
  WO-S2           derive MAX_COST_R + MIN_STOP      2 days
  WO-S3           one RR floor                      2 days
  WO-S5           reconcile throughput              1 day + on-box
  WO-S6           restore the vacuous gates         1 day

WEEK 3
  WO-S8           constant census + CI ratchet      2 days
  WO-S7 phase 2   move the side filter (if selection-staged)

OWNER TRACK, parallel, no agent dependency
  D-23            sizing reconciliation (WO-S4)     signature
  EV_TARGET_R     ratify (WO-S2 root)               signature
  WO-P            B00R root + main ruleset          on-box + signature
                  <- until this lands, UC-09 stands and CI cannot enforce
```

## Two ordering rules

1. **`WO-S1` before `WO-S2` … `WO-S5`.** Every downstream repair reads the registry. Repairing a constant before it is registered creates an eleventh unregistered constant.
2. **`WO-S7` phase 1 before anything is claimed about the judge.** If the side filter is selection-staged, every judge statistic is long-only and the `+10.87 pp` finding needs a scope banner before it is quoted anywhere else.

---

# PART 8 — WHAT THIS BUYS

| | Before | After |
|---|---|---|
| Hand-picked constants | **12** | **3** (`EV_TARGET_R`, `risk_pct_equity`, `MARGIN`) |
| Sites that can define a value | many | exactly one per value |
| Silent divergence | possible and observed 10× | **impossible** — boot refusal |
| New hand-picked constant | ships freely | **CI failure** |
| Fee ceiling | picked at 1/5, equals the edge | derived from the measured edge |
| Stop floor | literal 45 in three places | derived, tracks `H` |
| Throughput | 8.4 vs 12.4 vs 35.7 | equal by construction |
| "Have we run out of road?" | unanswerable | **`REFUSE{EV_TARGET_UNREACHABLE}`** |

**And the fee question stops being a question.** Not because it was ignored — because `H` became a measured root and `MIN_STOP_WIDTH` became a function of it. **After this work you cannot set a stop that lets fees eat the edge, because the floor is computed from the edge.** That is the actual answer to *"ignore the fees."*

---

## Attestation

| Claim | Status |
|---|---|
| All ten `UC-*` divergences | **Derived by this reviewer** from supplied documents and reports. Each cites its sites; **none has been confirmed by reading the code** except where the implementer previously confirmed it. |
| `UC-06` stage question | **Open.** The census evidence and the documentation disagree; `WO-S7` phase 1 settles it. |
| Every derivation, golden vector, and threshold table | **Computed by this reviewer**; reproducible from the formulas given |
| `gross_edge = +0.1991 R` | Rests on `n = 47` with a 95 % CI of `[28.4 %, 56.7 %]`. **Every derived value inherits that uncertainty.** The derivation tree is correct regardless; the *numbers it currently produces* are provisional until `n` grows. |

**Runtime state: `NOT_ATTESTED`.**

---

*Prepared 2026-08-13 · the structural defect repair · one meta-defect, ten instances, four vacuous gates, eight work orders · twelve constants collapse to three · posture unchanged `OFF/OFF/OFF/LIVE`*
