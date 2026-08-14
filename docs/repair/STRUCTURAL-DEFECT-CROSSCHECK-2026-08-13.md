# Structural-defect repair — cross-check and disposition

**Date** 2026-08-13 · **Subject** `TRIAD_STRUCTURAL_DEFECT_REPAIR_2026-08-13.md` (vendored
byte-identically in this directory, sha256 `c8e9ae68…e67c3`) · **Method** a 13-agent read-only
verification pass against the live code of all five estate repos, run **before** any repair was
written · **Posture** unchanged: `DENIED_SAFE_HOLD`, `OFF/OFF/OFF/LIVE`.

---

## 0 · The one-paragraph answer

The document's **method** is right and its **meta-defect is real**. Its **register is not**.

Its thesis — that the estate keeps building mechanisms which *look* like they are doing work and
are not — is correct, and its own best example is this repo's sibling `triad_param_census.py`:
a scanner that has classified magic numbers since it shipped and then ended in a printed prose
note. Nothing froze the count, so a new magic number on the money-line Rust cost exactly nothing
to add. That is now closed.

But of the ten `UNRECONCILED CONSTANTS` rows, **eight do not survive contact with the code.** Six
were reconciled between two and six weeks before the document was written; two describe machinery
that does not exist. Only the two CI-hygiene rows (`UC-09`, `UC-10`) verify, and they are exactly
what was built.

This matters beyond bookkeeping. The document's headline claim is that a coincidence between a
cost ceiling and the measured edge "is the entire P&L" — and the constant it names as that
ceiling **appears nowhere in the estate**. Acting on the register as written would have meant
changing live money-line values to fix arithmetic the code does not perform.

**LAW-9 held.** Every row below was checked by reading the implementing code and naming the
pinning test before a finding was written. Nothing in the register was repaired on the strength
of the document alone.

---

## 1 · Class A register · row-by-row disposition

| ID | Document claim | Verified state | Disposition |
|---|---|---|---|
| **UC-01** | governor hardcodes `gross_rr_floor` **2.5**; 44 `net_rr_floor` refusals | The governor **holds no RR literal.** It consumes the caller's `EvalContext.gross_rr_floor`; the serde default tracks the vendored `limit_config` (**2.0**, reconciled from 2.5 by CG-RISK-LIMITS on **2026-07-29**); the live path passes the per-profile `ladder_60_40` **1.7** via `exit_profiles.rs::gross_rr_floor_for`. Separately, `net_rr` is `None` at **every** production construction site (`triad_live_exec.rs:4674,7724`, `triad_shadow_exec.rs:1035`), so the 6b `NetRrCheck` cannot fire at all. | **REFUTED.** Both halves. The 44 refusals are structurally impossible on today's code; they belong to a window that closed. |
| **UC-02** | governor `min_stop_width_bps` **45** vs engine band 67–120 | **67 in all four planes** — `limit_config.per_trade` = 67, `exit_profiles.constraints` = 67, `symbols.v1.json edge.min_stop_bps` = {67,67}, and the `[67,120]` band agrees across Executor / Learning / Intelligence (CI-checked by Engine `verify_alignment.py §15c`). CG-STOP-FLOOR-67 landed **2026-07-31** at contracts 1.24.0/1.25.0. | **STALE.** The incoherence the row describes is the one the estate already repaired, including the detector generation re-launch it forced. |
| **UC-03** | `risk_pct_equity` is dead configuration; effective risk 14.8× below policy | The margin cap is **shrink-only and deliberate** (`governor.rs`: bound notional so posted margin ≤ `max_margin_pct × equity`, then derive leverage). Risk sizing is not dead — it bounds qty by stop distance, and the cap binds *on top*. The two are different constraints, not a contradiction. | **OWNER-GATED, not a defect.** Whether the *combination* under-risks is a capital-policy question for the owner, and `WO-S4` already marks it OWNER GATED. Reclassified from "unreconciled constant" to "policy interaction". |
| **UC-04** | `MAX_COST_R = 1/5` sets the cost ceiling exactly at the measured edge | **`MAX_COST_R` does not exist.** Zero occurrences across TriadEngine, TriadExecutor, TriadIntelligence and TriadLearning. `MIN_STOP_WIDTH` is not derived from `H / MAX_COST_R` anywhere; it is a vendored value with a contract home. | **REFUTED — the load-bearing row.** The document calls this "the one that produced the breakeven book". The derivation it describes is not implemented. `WO-S2` would have written a new derivation into the money line to fix arithmetic nothing performs. |
| **UC-05** | admission 8.4/min throttles a 35.7/min arrival; 76.5 % of signal discarded | **CONFIRMED as a limiter.** `JUDGE_CAPACITY_PER_MIN=7 × ADMIT_HEADROOM=1.2 = 8.4/min` is the live global bucket. Already registered as CG-ADMISSION-CAPACITY-PROFILE; the controller ships `legacy`, the deploy defaults `observe` (byte-identical in trading behaviour), and the widening mode `profiled` **fails closed** without a measured capacity artifact. | **CONFIRMED · OWNER-GATED.** The repair is not a constant edit: it is building the measured profile on the box and then arming `profiled`. An agent may build the measurement; it may not widen admission. |
| **UC-06** | side policy is applied at *selection*, not money-eligibility; "prevents its own repair" | Long-only is the **ratified LIVE30-PROFITABLE-ONLY settlement (2026-08-06)**: the money lane is exactly `bos_choch LONG ∪ order_block LONG`, at the gateway ingress (`_money_live_candidate`) *and* at the executor (`LiveEligibilityConfig` sides). SHORT is **not foreclosed** — it continues to accrue on `candidates.shadow` precisely so the decision can be revisited on evidence. | **REFRAMED.** A ratified design decision, not an unreconciled constant. The "cannot be revised on evidence" concern is answered by the shadow arm the settlement kept for that purpose. |
| **UC-07** | fee constant: maker 2.0 / taker 4.5, execution path unknown | **PARTIALLY CONFIRMED — and now locked.** The vendored authority `fee_model.v1.json` says taker **5**; every governed consumer reads it. The single unmanaged copy is `edge_jobs.DEFAULT_TAKER_FEE_BPS = 4.5` — an overridable research-CLI default, 0.5 bps/side adrift. | **BUILT (sealed-divergence lock).** Not equalised: moving the research default would move already-computed research outputs, which is the owner's call. Both values are now pinned in `TestTheUnmanagedTakerFeeCopy`, so either one moving REDs the suite and forces a deliberate reconcile. |
| **UC-08** | min notional: guide $20 vs venue 5 vs limits "5" — "may be enforcing an invented number" | The vendored value is **20**, and the real finding is different and worse: **five sites, no coupling row, and two of them implement different laws.** The config floor is a **sizing BUMP** (`ceil_to_lot(floor / entry_mid)`); the venue floor **was** a pre-send refusal and was REMOVED (`ecc942d`, 2026-07-26) — its whole input path (`--min-notional`, `--min-notional-per-symbol`, `effective_min_notional`, `EvalContext.venue_min_notional`) is computed, plumbed, and **read by nothing**. Four comments, including two operator-facing CLI help strings and a *test name*, still promised the removed skip. | **REFRAMED · BUILT.** Registered as **CG-MIN-NOTIONAL** in TriadExecutor with all five sites; every false comment corrected. Two owner-gated findings raised, not fixed — see §3. |
| **UC-09** | the combined check exists but is not a *required* status check | **CONFIRMED.** `TriadLearning` `main` is `protected: false` — no status check gates a merge at all. | **CONFIRMED · escalated (`WO-P`).** Installing a no-bypass ruleset is a repository-admin act. |
| **UC-10** | 281 pre-existing lint errors ⇒ red before and after ⇒ zero information | **CONFIRMED**, measured 2026-08-13: ruff **281**, mypy **42**. | **BUILT (`CG-LINT-RATCHET`), deliberately not wired.** The shipped baseline is stamped `PROVISIONAL_LOCAL_VERSIONS`: it was produced by ruff 0.15.8 / mypy 1.19.1 while `uv.lock` pins 0.15.21 / 2.2.0 for the runner. A baseline claiming agreement with a version nobody ran would be a fabricated receipt — exactly the failure class this document names. Regeneration on the runner is the operator's step. |

**Two rows verify. Eight do not.** The document's own §Attestation invites this check; this is it.

---

## 2 · Class B register · vacuous gates

| ID | Verified state | Disposition |
|---|---|---|
| **VG-01** F15 coverage ratio | Confirmed here previously; the numerator and denominator do share the RPI exclusion. | **OWNER-GATED (`WO-J`).** Emitting `NULL{COVERAGE_UNVERIFIABLE_RPI}` instead of a computed ~1.0 changes a formula's emitted bytes — LAW-9 makes it an amendment, not a repair. Already recorded in `DECISIONS-REQUIRED`. |
| **VG-02** `get_sim_gap` verdict `HONEST` | Confirmed: with `real_fills = 0` nothing can disagree, so the verdict is true by construction. | **BUILT — additively.** `verdict_basis` (`VACUOUS_PRE_LIVE` / `MEASURED`) and `measured` now ship alongside the verdict, so a caller can tell a vacuous green from an earned one. The `verdict` token itself is **deliberately unchanged**: moving it flips `tests/learning/test_databank_local.py:360`, which makes it an amendment (LAW-9 — the discriminator is bytes, not correctness). |
| **VG-03** `main` combined check | Same finding as UC-10. | See UC-10. |
| **VG-04** `matrix_off = 0` | The observation stands — a correct, passing check measuring a question that was never the suppressor. | **ACCEPTED as written.** It is the sharpest paragraph in the document: *a gate that is right about an irrelevant question is worse than a gate that is missing, because it consumes the attention that would have found the real one.* |

---

## 3 · What was actually built (and what was refused)

**Built — agent authority, all verified locally:**

1. **The param-census ratchet** (`WO-S8`, TriadLearning) — the meta-defect's own example, closed.
   `baseline` / `check`, frozen at engine **552** / executor **861** findings, with one law the
   lint ratchet cannot have: **`MIXED-ABS-REL` is pinned at ZERO regardless of the baseline**,
   because a frozen backlog is not a licence to add the worst class of finding to it. Stamped
   `AUTHORITATIVE_DETERMINISTIC` — stdlib regex, so unlike ruff/mypy no external tool version can
   disagree with the runner's. It claims exactly the authority it has, no more.
   The absent-tree case is the one that mattered: the money-line Rust lives in **sibling repos this
   repo's CI does not check out**, so a quiet zero-finding report would have been the fabricated
   clean read wearing a new hat. Default is a named refusal; `--allow-absent` skips **loudly** and
   states that the run proves nothing.
2. **`CG-MIN-NOTIONAL`** (TriadExecutor) — the five-site registry, plus every false comment
   corrected across `governor.rs`, `config.rs`, two operator CLI help strings, and the
   `governor_vectors.rs` docstring whose *function name* still asserts the removed behaviour.
3. **The sealed taker-fee divergence lock** (UC-07 above).
4. **Prose corrections** in Engine (`verify_alignment.py` §15c — including the RED failure message
   an operator only ever reads mid-incident) and Intelligence (`_money_live_candidate`, whose
   docstring said LONG/SHORT while the predicate below it read `("long",)`).

**Refused — owner authority:** `WO-S2` (writes a derivation for a constant that does not exist),
`WO-S3` (the floor is already single-sourced per-profile), `WO-S4` (capital policy, and the
document agrees), `WO-S5` (admission widening — GOV-01), the `verdict`-token change in VG-02, the
F15 formula in VG-01, and both min-notional behaviour findings below.

**Raised, not fixed — the two new real defects, both money-line:**

- **The sealed ledger disagrees with the code.** `CHECKPOINTS.md:128` seals the 5→20 raise as
  "sub-$20 now *skips cleanly* instead of a venue reject". The governor has never skipped — it
  **bumps** (rounds the order up to the floor). The ledger is tamper-evidence and is never edited,
  so the reconcile is a decision: make the code skip, or record that the row's description was
  wrong at seal time.
- **The bump can exceed `risk_pct_equity`.** Rounding up to the floor raises risk above the sized
  amount. Stated with its magnitude rather than as an alarm: at 2 % risk and the [67,120] bps band
  it requires equity below roughly **$7**, so it is latent, not live.

---

## 4 · "Unblock all 30 symbols" — the honest answer

**The 30 are already unblocked at every symbol-scoped gate.** Verified: `active_matrix.v1.json`
carries **90 ON cells** (30 × 3) byte-identical across all four vendoring planes; the LIVE30
registry and all twelve compiled per-plane views read 30; **no ceremonied lane carries a symbol
field at all**; and the entry canary defaults OFF. There is no five-symbol cap anywhere to remove.

The binding limiters, in the order they bite:

1. **Portfolio concurrency** — `max_open_positions = 10`, `per_symbol.max_concurrent = 1`,
   `max_net_exposure_quote = 50000`. This is the real answer to "why ~5 at a time": a ratified
   capital design decision, not a bug.
2. **Admission throughput** — the global 8.4/min bucket (UC-05). Widening it is owner-gated on a
   measured capacity profile that does not exist on the box.
3. **Money-lane cell scope** — `bos_choch LONG ∪ order_block LONG`, ratified 2026-08-06.
4. **`TRIAD_LIVE_SETUPS` on the box** — the cheapest possible cause and a **free, read-only
   diagnostic**: if it does not list both live detectors, takes die `setup_not_in_live_setups`
   regardless of everything above.

Every one of items 1–3 is a GOV-01 widening. **An agent may build the measurement; it may do
nothing that unblocks.** The correct first act is item 4 — read `TRIAD_LIVE_SETUPS`, which costs
nothing and cannot widen anything.

---

## 5 · Standing constraints reaffirmed

- The two MCP tokens pasted into chat earlier remain **EXPOSED** (CO-10). They have never been
  used or echoed by this session and must be rotated at the issuing side.
- No owner signature, trust-registry pin, credential, or on-box receipt has been fabricated;
  where evidence is absent the lawful state is a **named refusal**.
- No RC1/RC2/RC3/RC4 master bytes or `rc*_` bundles were touched.
- ORIGIN posture is invariant: `DENIED_SAFE_HOLD`, `OFF/OFF/OFF/LIVE`.

## 6 · Cross-references

- Vendored source: `TRIAD_STRUCTURAL_DEFECT_REPAIR_2026-08-13.md` (this directory).
- Owner decisions raised by this pass: `docs/plan/DECISIONS-REQUIRED.md` §II·H.
- Prior passes: `TRIAD_REVISION_RECORD_R-01/R-02/R-03_2026-08-13.md`,
  `GAP-CROSSCHECK-2026-08-13.md`, `REPAIR-REPORT-2026-08-13.md`,
  `IMPLEMENTATION-REPORT-2026-08-13.md`.
