# PLAN — "unlock all tokens · open fairness · every symbol tradable" (2026-08-13)

**Disposition:** `PLAN / NOT_A_RATIFICATION / NO_RUNTIME_CHANGE`. This document changes no code,
no config, no contract, and no flag. It **prepares** the fairness change (agent-buildable) and the
widening switches (owner-armed), and it hands the account owner the exact GOV-01 arming card.
Posture is and stays **OFF/OFF/OFF/LIVE · DENIED_SAFE_HOLD**.

Owner directive (2026-08-13): *"unlock all tokens, open fairness for every symbol, every symbol
should be tradable"* → resolved to *"confirm on-box, but prepare the fairness and widening plan."*
Root analysis: `INVESTIGATION-BTC-BCH-2026-08-13.md`. Confirm tooling:
`TriadLearning/analysis/symbol_funnel/`.

---

## 0 · The ask, decomposed — nothing is "locked"

All 30 symbols ship **ON** (`active_matrix.v1.json` `config_version 2026.07.28-universe-30`, 90 cells).
There is no per-token lock. The collapse to ~2 is the **intersection of four gates**, and the law
treats each differently:

| Gate | Kind | Ceremony | Owner |
|---|---|---|---|
| Judge fairness / admission | mostly **already armed**; `fair_admission_split` unwired | **none** (narrowing-neutral) | agent-buildable |
| scan_gate `$25k` depth floor vs equity | **WIDENING** + §1 contracts train | **GOV-01** | owner arms |
| venue min-notional × margin-capped notional | **PHYSICS** (venue rejects sub-min) | n/a — more equity | owner |
| LIVE30-PROFITABLE-ONLY wall (bos_choch/order_block **LONG only**) | **WIDENING** (capital direction) | **GOV-01** | owner arms |

**The one sentence that governs this whole plan (ARM-02):** *narrowing needs no ceremony; widening
always does; an agent builds the switch, the owner flips it.* So the fairness change I may land; the
two widenings I build DARK + default-OFF, and you arm them through the §4 card.

---

## 1 · CONFIRM FIRST (do this before arming anything)

The estate already built the read surfaces; `TriadLearning/analysis/symbol_funnel/confirm_30.py`
assembles them into one per-symbol funnel:

```bash
cd TriadLearning
python3 analysis/symbol_funnel/confirm_30.py \
    --ro-dsn "$DATABANK_RO_DSN" \
    --census /Users/liko/.triad/run/gateway_census.json \
    --equity <live_equity> --min-notionals min_notionals.json
```

It answers, per symbol: **where it dies** (`shadow.v_symbol_gate_aggregate`), **whether it is
admitted / judged / supplied / served** (the gateway census maps), and **whether it can even clear
the venue floor** at the current equity (the physics table, §5). Read that report first — it tells
you which of the four gates is actually binding for which symbols, so you arm only what the evidence
demands. (If your bank predates migration `triaddtbnk/1.33`, use the windowed MCP tool
`query_symbol_gate_aggregate` instead.)

---

## 2 · FAIRNESS PLAN — agent-buildable, narrowing-neutral (no ceremony)

**Already armed** (do not re-do): the "5 of 30" fairness fixes landed — `fair_order`'s
least-recently-served rotation (Intelligence CROSS-POLL ROTATION), the both-intake `fair_order`
(FAIR-DRAIN-PARITY), and the admission controller wired to `observe` (byte-identical). So the judge
already rotates across symbols within and across polls.

**The one remaining fairness lever** the investigation named as *built-but-never-called*:
`judging_budget.fair_admission_split` (defined in Intelligence `judging_budget.py`, `grep` shows only
the `def` — never invoked in `run_gateway.py`). Wiring it makes admission **round-robin the token
grants across the active `(symbol, direction)` groups** instead of letting a prefix-first drain hand
the whole per-poll bucket to the head of the order.

- **Why it needs no ceremony:** it *redistributes* a fixed judging budget across symbols; it does
  not enlarge the budget, widen the live set, loosen a gate, or change any verdict. It can only make
  a starved symbol MORE likely to be judged — a fairness (narrowing-neutral) change, exactly the
  class ARM-02 lets an agent land.
- **Coupling sites (one PR-set):** Intelligence `run_gateway.py` (call `fair_admission_split` at the
  `_handle_batch` admission point, threading the same `_served` map already used by `fair_order`) +
  a test `test_fair_admission_split_round_robins_grants_across_symbols` + the existing
  `test_fair_order` invariants must stay green (the flag-off / empty-served path byte-identical).
- **Careful boundary:** this is admission *ordering*, not admission *rate*. The rate (the 8.4/min
  bucket) is the `TRIAD_ADMISSION_CONTROLLER=profiled` widening in §3c — a separate, owner-armed act.

**Status:** ready for me to build on request. It is the one part of "open fairness" an agent may
actually land; say the word and it goes in as a normal (no-ceremony) PR with its test.

---

## 3 · WIDENING PLAN — built DARK + default-OFF; you arm (GOV-01)

Each switch below I build **inert** (unset ⇒ byte-identical to today); flipping it live is your
signed act. None is landed by this plan.

### 3a · Per-symbol scan_gate depth-floor override (Engine)
The scan_gate `$25k` quote-depth + `8 bps` spread screen (`symbols.v1.json:5-12`,
`ref_position_notional_quote=25000`) is **majors-calibrated for $10k equity**; at ~$100 it collapses
the field toward the deepest books. The widening is a per-symbol / equity-scaled override so alts
pass the depth screen.
- **Kind:** WIDENING (admits more symbols) **and** a §1 contracts train (`symbols.v1.json` is
  vendored ×4 → byte-identical ×4 + `MANIFEST.sha256` re-pin + estate `VERSION` bump + conformance
  ×4). Detector emission is downstream of scan_gate, so re-derivation scoping applies if the screen
  changes what emits.
- **DARK switch:** an operator `TRIAD_SCANGATE_DEPTH_SCALE` (or a per-symbol override block, default
  = the current $25k) read by `scan_gate.rs`, unset ⇒ today's value ⇒ byte-identical.
- **Enforced:** `scan_gate` tests + `verify_alignment.py §15a/§1`.

> **GAP-51 (R-02 §3) — the symbol-selection confound, before you widen.** The live win rate is
> measured on the NON-RANDOM ~2-symbol subset that clears the funnel, so part of the "13 pp"
> shortfall may be *symbol selection*, not signal quality — and widening the gates is exactly the
> remedy for that source (whereas entry-mechanism work, WO-B, is not). WO-A **A5** (per-symbol
> baseline reconciliation + the 93-round-trip distinguishability bar, `TriadLearning/analysis/wo_a/`)
> quantifies it on-box; run it in the §1 confirm so you widen against evidence, not a confound.

### 3b · All-detector / both-sides money policy (the LIVE30-PROFITABLE-ONLY wall)
Live money is currently exactly `bos_choch LONG ∪ order_block LONG`; **all M1 and all SHORT are
shadow-only** (`is_money_live_candidate` / `_money_live_candidate` / `LiveEligibilityConfig` side
sets / `LaneRegistry::live_eligible`). "Every symbol tradable in every setup" means admitting M1
and/or SHORT to the money lane.
- **Kind:** capital-direction **WIDENING** — the exact class of CG-M1-SHORT (which required GOV-01
  one-approver + your consent line). It moves as a coupled set across Engine `runtime.rs`,
  Intelligence `run_gateway._money_live_candidate`, Executor `LiveEligibilityConfig` + `LaneRegistry`
  + `cellbook_ref`, and the profitable-LIVE30 settlement verifier.
- **DARK switch:** per-arm money-canary flags (the DC-03 precedent: `TRIAD_M1_MONEY_CANARY`,
  `TRIAD_..._SHORT_MONEY_CANARY`), default-OFF, each with its own isolated account + caps in the
  activation policy — so you widen one arm at a time, not the whole wall at once.
- **Enforced:** the profitable-LIVE30 workflows + `verify_settlement_v2.py` + the Executor
  eligibility tests.

### 3c · Admission RATE (the throughput cap)
Not fairness (§2) but rate: the `profiled` admission controller widens the 8.4/min bucket to a
**measured** capacity. The mechanism is built (`admission_rate.py CapacityController`, wired to
`observe`); arming is `TRIAD_ADMISSION_CONTROLLER=profiled` + a measured on-box profile
(`tools/build_capacity_profile.py`), which **fails closed** on any absent/mismatched artifact. This
is an on-box owner act, not an agent flag.

---

## 4 · The GOV-01 arming card (owner-only — the signed step)

For each §3 widening, arming is the ARM-02 §5 / GOV-01 ceremony — **one approver, your consent line
following the key, evidence-verified, synthetic-DENY-confirmed.** A chat message is intent, not the
key. The ordered card:

1. **Run §1 confirm** — attach the `confirm_30.py` report (the evidence the widening is warranted +
   which gate binds).
2. **Sign the activation manifest** — `TriadAgent/configs/activation/activation_policy.v1.json`
   widener row (`M1_FVG` / the SHORT arm / scan_gate override), with: your GOV-01 approver identity,
   the account-owner **consent line** (`leesbak@gmail.com`), the widener's isolated account + caps,
   and a synthetic-DENY confirmation. (The validator + GitHub-attested runner are
   `TriadAgent/src/triad_agent/activation/` — `plane.py`/`runner.py`; it reports lawful, it does not
   flip the flag.)
3. **Land the §1 contracts train** (scan_gate only) — vendored byte-identical ×4 + MANIFEST re-pin +
   VERSION bump + conformance ×4, in the SAME PR-set as the signed manifest.
4. **On-box flip** — set the DARK flag in `secrets/live.env` (`=1` for the specific arm), restart
   through the operator path. Every money layer (arm token · caps latch · kill switch · governor ·
   judge verdict) still gates every resulting order.
5. **Watch armed** (ARM-02): fix-forward-while-armed; the caps latch / kill switch / Sev-1 automatics
   remain the only things that stop the show. Narrow back any time (no ceremony).

**Do NOT** widen the whole wall in one flip — arm one canary (one detector × one side, isolated
account + caps), confirm it trades and settles clean, then the next. Serial adoption is the law.

---

## 5 · The equity / physics floor — the honest half of "every symbol tradable"

Even with §2 + §3 fully armed, at ~$100 equity the margin-capped notional is **$15**
(`equity × max_margin_pct/100 × leverage = 100 × 0.01 × 15`) — below Binance's real min-notional for
the majors (BTC $100). **No gate change makes a sub-floor symbol tradable; the venue rejects it.**
The `notional_physics.py` table computes, per symbol, whether it clears at your equity and the
`min_equity_to_clear` if not (e.g. a $100 min-notional needs ≈ **$667** equity under the 1%×15 cap).

So "every symbol tradable" is, in order: **(1) more equity** (or a raised `max_margin_pct`, itself a
risk widening) so the notional clears the venue floor, **(2)** the §2 fairness wiring so the judge
reaches every symbol, **(3)** the §3 gate widenings so the eligible set is not majors-only. Arming
the gates without the equity is a flip that changes nothing at the venue — which is exactly why §1
confirm comes first.

---

## 6 · What I build vs what only you can do

| Item | Who | Ceremony |
|---|---|---|
| §1 confirm tooling (`symbol_funnel/`) | **DONE** (agent) — read-only | none |
| §2 fairness `fair_admission_split` wiring + test | **agent, on request** | none (narrowing-neutral) |
| §3a/§3b DARK switches (built inert) + §4 manifest template | **agent, on request** | none to BUILD |
| Arming any §3 widener (the flip) | **you** — GOV-01 signed manifest + on-box flag | **GOV-01 §5** |
| §3c `profiled` admission + measured profile | **you** — on-box | on-box owner act |
| §5 equity increase | **you** | n/a |

**Bottom line:** I've confirmed *how* to prove where each symbol dies and *what* each unlock costs.
The fairness half is mine to land; the tradable-set half is a widening — I build the switches dark
and you arm them, one canary at a time, against the confirm evidence. Nothing in this plan arms,
widens, or edits the money line.
