# DECISIONS REQUIRED — TRIAD Origin Formula Repair + Change Orders

**For:** the account owner (leesbak@gmail.com / operator).
**Scope:** everything in the Formula Repair Specification + Change Orders CO-01..CO-14 that an
agent **cannot** lawfully do — because it needs a cryptographic signature, an owner-only
credential act, an on-box step, a governance grant only you can widen, or an independent reviewer.
**Posture is unchanged and stays unchanged by everything below:** `OFF/OFF/OFF/LIVE`,
`DENIED_SAFE_HOLD`. Nothing here arms anything; every mechanism below is built and refuses in
place until you act.

The honest boundary I held throughout: I never fabricated a signature, a trust-registry pin, a
credential value, or an on-box receipt. Where the only lawful next step is yours, the code refuses
loudly and names the refusal — it does not guess.

---

## A · Signatures & ratifications (cryptographic — only you hold the key)

| # | Decision | What I built (refusing in place) | What only you can do | Blocks |
|---|----------|----------------------------------|----------------------|--------|
| **D-1** | Sign the repair PR for every `RATIFY_WITH_THIS_REPAIR` law (§1.2 wire-width `PAR-INT-01` int64; §1.4 availability; R-F03 ambiguous-bar `ABSTAIN_EXTEND_WINS`; R-F04 `BOTH_EMIT` erratum; R-F09 `b>=1`; R-F12 `ONE-BOS-ONE-LINEAGE` + origin tie law; R-F13/R-F19 ordering laws) | Each law is wired + tested; the refusal/quarantine behaviour is active now | GOV-01 single-approver signature on the repair PR | merge of every repair milestone |
| **D-2** | Ratify the `PROPOSED_MUST_RATIFY` **values** (F12 `OB_TTL_BARS`/`OB_MITIGATION_FRACTION`/`OB_BREAK_BUFFER_TICKS`; F09 `LEVEL_TTL_BARS`; F17 min-depth; F11 `PAR-158` transport; F03 `PAR-036` transport; and the rest as landed) | The mechanism + its named refusal (`BLOCKED_ON_RATIFY(<param>)`) + tests; the value is never hardcoded active | Ratify each value (or leave it refusing) | formula ACTIVE status only — mechanisms already land refusing |
| **D-3** | **B00R root closure** — authenticate the three root decisions, pin the trust registry externally, install the no-bypass `main` ruleset, threshold-sign receipt-v3 → `B00R_RECEIPT_ANCHOR_G2` | The `-002` decision templates, the g2 trust-registry template, the ruleset provider template, and the receipt-v3 schema all exist and fail closed. **The two previously-failing B00R tests are FIXED by an agent** — root cause was only a missing local `B00R_RECEIPT_ANCHOR` git tag (fetched; zero file changes; CI fetches tags so it holds) | Fill + Ed25519-sign `DEC-AUTHORITY-BUNDLE-002` / `DEC-B00-REPAIR-002` / `DEC-RECEIPT-PROFILE-002`; externally pin the g2 trust registry; install the ruleset; threshold-sign receipt-v3 | the B01C→B02C… merge chain unfreeze (see ON-BOX guide O-3) |
| **D-4** | **OWNER-TOPO-01** signature (E03/E05/E06 topology) | The adjudicated signable text (verdict SIGN + amendments A1–A3) is registered in `docs/plan/CO-14-OWNER-TOPO-01-REGISTRATION.md`, `PENDING_SIGNATURE`; the six E03–E06 contract stubs carry `CONTRACT_RATIFICATION_REQUIRED` | Sign; **confirm A3 identity == the trust-registry owner entry** (the one item the adjudication left `NOT_ATTESTED`) | CO-14 registration; the E03–E06 contract bodies (CO-03 §7) |
| **D-5** | **CO-13** contract-version decision (10 pairs; defaults = RC3 catalog §03) | The decision document with the ten canonical defaults + reader/writer rule; unsigned ⇒ every consumer answers `BLOCKED_ON_RATIFY(CO-13)` | Sign (or strike a row at signature) | RC5 contract-union finality (CO-01) |
| **D-6** | **CO-11** `ORIGIN-F##` namespace rule ratification | The rule doc + the in-repo linter (`tools/lint_origin_f_namespace.py`, report-only until ratified; `--enforce` ready for CI) | One-line ratification (`ratified_by`) | estate-wide `ORIGIN-F##` enforcement |
| **D-7** | **Independent review** of the repair PR (reviewer ≠ author) | — | Assign an independent reviewer (e.g. @djordi10) per GOV-01 | merge |

## B · Governance grants (only a CODEOWNER can widen)

| # | Decision | Why it exists | What only you can do | Blocks |
|---|----------|---------------|----------------------|--------|
| **D-3b** | Widen the frozen B00R **SOURCE grant** in `tools/classify_milestone_pr.py` to admit the formula paths (`structures/*`, `instrument_math*`, `config/*`, `contracts/schemas|golden/*`, `tests/kernel|structures|formulas|control/*`) for the B02C+ milestone **source PRs** | The B00R generation-2 grant deliberately excludes formula paths, so a milestone PR to `main` classifies as out-of-scope. The repair series is cleanly ordered per-milestone on the designated branch for mechanical re-cut; CO-12's scope-guard keeps the G2 root PR governance-only | Widen the grant in an owner-reviewed PR, then pin the newly-granted prefix files in `SOURCE_HASHES` | any formula-repair milestone PR passing CI classification against `main` |

## C · Owner-only credential / on-box acts (see the ON-BOX GUIDE)

| # | Decision | Why | Detail |
|---|----------|-----|--------|
| **O-1** | **CO-10** credential rotation (venue keys, tunnel/bearer tokens, Auth0) — issuing-side revocation + fingerprint receipts | Credentials appeared in supplied ops guides; anything that travelled through a doc/chat/transcript is EXPOSED and must be rotated before B05C security attestation | ON-BOX GUIDE §O-1 |
| **O-2** | **CO-12** forensic salvage of the off-clone refs (`7dbab10` post-g2-integration, `ef88414` B08, `d6795cb` status, the dirty worktrees) | These are absent from the GitHub clone — they live only on the box; the preserve-as-patch-candidates law forbids reconstructing them by invention | ON-BOX GUIDE §O-2 |
| **O-3** | **B00R** external trust-registry pin + `main` ruleset install + threshold-sign on a clean runner | The cryptographic half of D-3 | ON-BOX GUIDE §O-3 |

## D2 · Linkage & status closures (CO-06 / CO-09 — semantic-owner + signed-event)

| # | Decision | What I built (refusing in place) | What only you / a semantic owner can do | Blocks |
|---|----------|----------------------------------|-----------------------------------------|--------|
| **D-8** | **CO-06 RC3-LINK-BLOCK-002** — the 17 `SEM-*` verification rows whose `linked_task_ids` point at the nonexistent `CTL-G2/G3-03`. The finding FORBIDS an inferred blanket replacement | Each of the 17 rows is individually **retired from the effective linkage** and marked `EDGE_UNRESOLVED_PRESERVED` / `effective_status=UNRESOLVED_SEMANTIC_OWNER_REQUIRED` (evidence, never coverage; excluded from the B09 conformance denominator). I did **not** guess the obvious `CTL-G2-03;CTL-G3-03` mapping — it is explicitly disallowed | A **semantic owner** selects the exact existing task ids for each SEM row in a **signed event** | those 17 rows entering the B09 unique conformance denominator |
| **D-9** | **CO-06 RC3-LINK-BLOCK-001 / -003** — the 182 composite `G2/G3` gate rows + the 408 preserved RC1 rows | The overlay **materializes** the typed multi-gate edges (all members validated) and attributes task/gate edges; status `MATERIALIZED_AWAITING_SIGNED_CLOSURE`. The RC3 finding is **never mutated in place** | A **signed `RESOLVED` event** per RC3's closure rule flips the two findings from OPEN_BLOCKER | RC3 linkage findings reading RESOLVED (the materialization itself is complete + gate-green) |
| **D-10** | **CO-09 provider run id** — the status projections embed the real git HEAD they were generated against, but the authenticated provider (CI/Actions) run id is `AUTHORITY_OPEN` (offline) | The head is a **real** 40-hex sha (`--stamp-context`); the run-id slot is the typed `AUTHORITY_OPEN` placeholder, **never fabricated** | Re-stamp on an authenticated CI runner so the provider run id is a real value (or leave it AUTHORITY_OPEN) | a fully provider-attested status header (the head half is already truthful) |

## D · Part E — the owner-service corrections (NEVER implemented in Origin)

Part E (F20–F23 + GV-018) corrects **E08/E09/E10** owner services and is recorded in
`docs/plan/PART-E-OWNER-SERVICE-CORRECTIONS.md` as spec-level corrections. Origin **must not**
implement any of them (order verbs / risk / venue reach are forbidden capabilities here). The
`outcome.v3` schema (CO-04, E10) ships as a **DRAFT** spec artifact
(`docs/plan/outcome.v3.draft.schema.json`); publishing it, dual-writing v2+v3, and the reader
cutover are the E10 owner service's signed acts.

---

## PART II · v2.0 — the eleven decisions from the independent cross-check (D-11 … D-21)

**Source:** the owner supplied `DECISIONSREQUIREDv2.0` + `TRIAD_ORIGIN_V7_ERRATA_AND_CLARIFICATIONS_2026-08-13`
and `INDEPENDENT_AUDIT_AND_SCORECARD` ("the answer for the decisions you required", 2026-08-13).
These rows are recorded here at v2.0 parity. **Forwarding the register is not signing it** — every
row below whose "what only you can do" is a signature is still `OPEN`; no signature, trust-registry
pin, credential value, or on-box receipt is fabricated. Posture unchanged: `OFF/OFF/OFF/LIVE`,
`DENIED_SAFE_HOLD`; `shadow_activation = LIVE` is fixed with no OFF control. **Nothing here disarms
anything** — every remedy adds a gate, splits an identity, names a refusal, or converts a silent
default into a measured experiment.

**Scope discipline (why Origin builds almost none of these):** Origin owns **E02 only**. The three
P0 economic gates (D-12, D-13) live at **E07**; the exit half of D-14 and D-19/D-20 sizing live at
**E08/E09**; D-18 reconciliation is an **estate** act; D-15 is an **RC4** amendment. Origin must not
implement order verbs, risk, sizing, venue reach, or a fee-net admission gate — those are forbidden
capabilities here. The only rows that touch Origin code are **D-11** (F18 RR floor — recorded, an
owner choice), **D-17** (F12 confirmation semantics — recorded, an owner A/B/C choice), and **D-21**
(the F10/F13 formula errata).

### II·A · The economic gate — three P0s (all cross-estate / owner; Origin does NOT build them)

| # | Finding (one line) | Origin scope | What only you can do | Status |
|---|---|---|---|---|
| **D-11** | RC2 §F18 fixes `RR floor = 2.0`; the estate's live ratified `gross_rr_floor = 2.5`. Unremarked; costs ≈5.7 pp of required win rate at `H=9 bps`, `stop=45 bps` (`p_BE=(1+c)/(1+RR)`). Flips the shadow board's 34.3 % from break-even to negative. | **F18 is Origin (candidate_geometry).** But this is an owner *choice*, not a bug: the value is contested between two ratified sources, so an agent does not pick. Recorded refusing-in-place — F18 must not hardcode a contested floor active (§0 rule 1 / law 20). | Sign one: **(i)** restore `RR_FLOOR = 5/2` exact rational, or **(ii)** preregister `RR_FLOOR ∈ {2.0, 2.5}` as a two-arm cohort-tagged measurement frozen before any capsule read. Meanwhile F18 emits `BLOCKED_ON_RATIFY(RR_FLOOR)` and publishes exact-rational RR to SHADOW with no floor applied (both arms recoverable). | OPEN |
| **D-12** | **No layer in V7 refuses a candidate for being fee-unviable.** E02 is forbidden cost (law 07, correct); E07's economic admission is `TBD-011` (does not exist); F20 sizes an unviable trade; F23 measures the loss after. Estate's own `breakeven_roundtrip_bps = 3.09` is below even pure-maker 4.0 bps. **Highest severity in the register.** | **E07 — OUT OF ORIGIN.** Origin cannot and must not build a fee-net gate (law 07). Recorded as the estate's owner/E07 act. | Ratify the E07 `ADMIT` predicate (stop_bps ≥ floor; RR_exact ≥ RR_FLOOR; `p_required=(1+cost_R)/(1+RR)`, `cost_R=H_bps/stop_bps`, per-side never blended; cell win-rate CI lower bound > p_required, else SHADOW-only `BLOCKED_ON_EVIDENCE(cell)`). Failure emits `REFUSED_FEE_UNVIABLE{…}` + full SHADOW lineage. | OPEN — blocks G7, any promotion, any expectancy claim |
| **D-13** | The 45 bps `min_stop_width_bps` — the estate's single most effective filter — has **no home** in V7. Law 07 forbids it from E02; nothing re-establishes it at E07/E08. V7 as specified admits the 10 bps-median geometry that produced −643 R. | **E07 — OUT OF ORIGIN.** Recorded as the owner/E07 act. | Register `MIN_STOP_WIDTH_BPS` as an E07 admission binding, `PROPOSED_MUST_RATIFY`, proposed 45, refusal `REFUSED_STOP_TOO_TIGHT{…}` + SHADOW recording. **Derived, not inherited:** `MIN_STOP_WIDTH_BPS = H_bps / MAX_COST_R` (`MAX_COST_R` signed, proposed 1/5) so it moves with the fee model. | OPEN — blocks G7 |

### II·B · Execution mechanics (cross-estate / RC4)

| # | Finding (one line) | Origin scope | What only you can do | Status |
|---|---|---|---|---|
| **D-14** | Law 14 (post-only maker for every normal entry AND exit) is contradicted by three internal sources: resting entries ≈28 % WR vs market-at-signal ≈51.5 %; RC4 §06 audit shows 36 % historical taker fills; maker-stop failure is an unbounded tail vs bounded taker-stop cost. | **E08/E09 — OUT OF ORIGIN** (execution mechanics, venue). Recorded. | Two signatures: **(i) entry** — demote to a preregistered cohort-tagged measurement `{post_only_resting, confirmed_entry, market_at_signal}`; **(ii) exit** — ratify EXIT-MECH-01's PROTECTED-STOP hybrid (maker for `T` s in an `X` bps band, then deterministic market; `T`,`X` `PROPOSED_MUST_RATIFY`). | OPEN — exit half is a standing unbounded-tail exposure; sign before `venue_activation` is ever LIVE |
| **D-15** | RC4 §01 law 10 lets four SHADOW refusals force `venue_activation=OFF` — a measurement-plane heartbeat revoking money-plane authority, conflicting with ARMED-BY-DEFAULT (disarm is never the default remedy) and creating a 5 s DoS surface. | **RC4 amendment — OUT OF ORIGIN.** Recorded. | Sign the split by what each refusal actually threatens (contamination → quarantine+page, no activation change; lineage → block new cohort opening; stale → page+fix-forward, escalate only after a signed `T_grace`; not-persisted → quarantine+page). Extend RC4's own `SHADOW_UNTRADEABLE` pattern. | OPEN — inert while posture is OFF; sign before it is not |

### II·C · Sequencing & semantics

| # | Finding (one line) | Origin scope | What only you can do | Status |
|---|---|---|---|---|
| **D-16** | Capsule dependency trace: CAP-03 (F06), CAP-04 (F08/CHOCH) hard-blocked; CAP-02 (F17 book tilt) blocked-or-advisory; CAP-05 (F07, E01) unknown; the repair set cleanly unblocks **only CAP-01**, whose base detector (`order_block`) is the estate's most trustworthy *negative* prior, while the positive-prior `fvg_retest` (CAP-02) stays gated. | **Owner sequencing decision + F17/F06/F08 ratifications** (F17/F06/F08 mechanisms exist refusing-in-place, D-2). Recorded — not an agent pick. | Sign a capsule order (proposed: F17 → CAP-02 first; then F08; then F06; CAP-01 second under D-17's split identity). | OPEN — governs what the next months of shadow data are *about* |
| **D-17** | While F08 refuses, §R-F09 emits only `GENERIC_BREAK`, so F12 `ob.displacement_bos.v2` confirms on any close-through, not on breaks of structure — an ambiguous trial identity (RC3 law 18) that must never pool pre-/post-F08 rows. | **F12 is Origin.** Recorded as an owner A/B/C choice; **behaviour left unchanged** (an agent does not pick). Honest note added to `order_block_v2.py`. | Sign one: **A** gate (`BLOCKED_ON_RATIFY(F08)`); **B** split identity `ob.displacement_break.v2` / `CONFIRMED_BY_BREAK` (recommended — never-blend + armed); **C** stamp `confirmation_class ∈ {BOS, GENERIC_BREAK}` + read-time refusal. | OPEN — must precede any CAP-01 shadow accrual |

### II·D · Carried-forward & operational (estate / executor — OUT OF ORIGIN)

| # | Finding (one line) | Origin scope | What only you can do | Status |
|---|---|---|---|---|
| **D-18** | `last_reconcile_ts` is permanently null — the reconciler has **never run**; 13 incident-window orders have unrecorded round-trip P&L; **zero** references across all seven V7 docs. V7 law 10 / RC4 `UNKNOWN_SUBMIT_UNRECONCILED` make reconciliation a precondition it has never met. | **Estate act — OUT OF ORIGIN.** Recorded (Origin owns no venue/reconciler). | Register P1 as a named predecessor on the gate ladder (blocks G6/G7); require one successful reconciliation run + receipt before any promotion receipt; record the 13 orders' P&L discriminated by market-sell timestamp. | OPEN — blocks G6/G7 |
| **D-19** | Ops guide asserts a `$20` MIN_NOTIONAL; Binance documents 5 USDT read per-symbol from `exchangeInfo`; estate limits carry `"5"`. The `$20` appears in no primary source → possibly a hardcoded constant (law 20 defect). | **E08/E09 executor — OUT OF ORIGIN.** Recorded. | Ratify: every venue constant read from live `exchangeInfo` with `metadata_revision` (§R-F00 metadata law); record per-symbol MIN_NOTIONAL in the activation manifest; audit/remove any hardcoded path. | OPEN — blocks TBD-013, G7 |
| **D-20** | At ≈$99.82 equity, 1 % risk / 45 bps stop = $222 notional (clears 5 USDT); the reported "below minimum" failure does not reproduce in either direction → the executor sizing path does something no supplied doc describes. | **E08 sizing — OUT OF ORIGIN.** Recorded. | Require a written sizing-path trace (`risk_pct_equity` → `unit_loss=m·|E−S|+c` → submitted qty, each value + source) reconciled to live filters before signing TBD-012/013. | OPEN — blocks G7 |

### II·E · The formula errata (Origin — D-21)

| # | Finding | What the agent did (this PR) | What only you can do | Status |
|---|---|---|---|---|
| **D-21 · ERR-01 (F10)** | Spec §R-F10 state block overlapped `TOUCHED (pen>0)` / `PARTIAL (0<pen<1/2)`; inline T4 reasoning contradicted the `pen>0` gloss. | **Closed in code + test.** The module already implements the RATIFIED T4 mutually-exclusive reading (`TOUCHED: pen==0`, `PARTIAL: 0<pen<1/2`, `MIDPOINT_FILLED: 1/2≤pen<1`, `FILLED: pen==1`); added the required property test (`TestErr01MutuallyExclusiveStates` — 10⁵ random pens, exactly one predicate true) + a precise docstring. This locks already-ratified behaviour; it is not a new law. | Sign the erratum onto the repair PR (formal spec-text amendment) alongside D-1's `RATIFY_WITH_THIS_REPAIR` set. | OPEN (signature) — code/test done |
| **D-21 · ERR-02 (F13)** | The errata proposes redefining the excursion `extreme` to accrue over **every** `t_exc..t_confirm` bar (a `(0.5)` deepen step in `RECLAIM_PENDING`). | **Recorded owner-gated; code UNCHANGED.** The current module faithfully implements the vendored CORRECTED LAW ("`extreme = min over excursion-phase bar lows`") — pinned by `test_hold_bars_do_not_deepen_the_extreme` + `test_h10_…deepens…first`. The erratum CONTRADICTS that law, flips a passing test, and changes `extreme`/`excursion_depth_ticks` bytes consumed by F18 stop logic — a formula-byte semantic change an agent may not pick (authority order: "a semantic change updates the authoritative spec/control artifact in a prior PR"). Honest note added to `excursion_reclaim_v2.py`. | Sign the erratum (redefine `extreme` per the proposal) in a prior spec-amendment PR + on the repair PR; then the F13 code change + acceptance test land in the same signed PR-set. | OPEN — blocks nothing today; adopt before pooling F13-fed stops |

**ERR-03** is D-17 above (F12). **Order of operations (owner):** the register's v2.0 recommends the
three P0s (D-12/D-13/D-11) first, then D-6, then D-21+D-17, then B00R root closure (D-3/O-3), then
the merge chain (D-3b/D-1/D-7), then D-16, D-2, D-18, D-14, D-15, D-19/D-20, then D-4/D-5/D-8/D-9/D-10,
then O-1/O-2.

### II·F · The gap register + repair work order (GAP-01…GAP-50 / WO-00…WO-Q)

The owner supplied `TRIAD_ORIGIN_V7_GAP_REGISTER_2026-08-13` + `TRIAD_REPAIR_WORK_ORDER_2026-08-13`
(vendored verbatim in `docs/repair/`). The **full gap-by-gap disposition** is
`docs/repair/GAP-CROSSCHECK-2026-08-13.md`. The scope wall holds: TriadOrigin is E02 only, so the
economic layer (E07), venue drift (E09/executor), the bank/measurement debt (DTBNK/estate), and the
governance/on-box acts are **out of Origin by construction** (RC3 law 07 + this repo's `CLAUDE.md`;
the register's own CORRECTION-01 says the economic gate must be built at E07, never E02). The mapping
onto this register:

| Gap(s) | This register | Disposition |
|---|---|---|
| GAP-11 | **D-21 (ERR-01)** | ✅ CLOSED-IN-ORIGIN (F10 predicates + property test) |
| GAP-12 | **D-21 (ERR-02)** | OWNER-GATED — code faithful to the vendored CORRECTED LAW; the redefinition is a signed spec change |
| GAP-13 | **D-17 (ERR-03)** | OWNER-GATED — A/B/C, behaviour unchanged |
| GAP-04, GAP-46 | **D-11** | OWNER-GATED — F18 uses the ratified PAR-061 `2/1`; WO-C's remove-generation-floor is an owner redesign |
| GAP-01, GAP-02, GAP-03 | **D-12, D-13** | OUT-OF-ORIGIN (E07 admission / cost model / stop-width) |
| GAP-05…GAP-10 | (executor / on-box) | OUT-OF-ORIGIN (E09/venue) + WO-00 on-box probe |
| GAP-14, GAP-15, GAP-45 | **D-14** | OUT-OF-ORIGIN (engine/E09) + owner (Law 14) |
| GAP-17, GAP-18 | **D-18** | ON-BOX reconciler + estate |
| GAP-19…GAP-29, GAP-43/44/47/49 | (DTBNK/MC/Intelligence/bank) | OUT-OF-ORIGIN measurement |
| GAP-30, GAP-31 | **D-3, D-3b** | OWNER / CODEOWNER on-box |
| GAP-32, GAP-33, GAP-34, GAP-38 | **D-2** | OWNER `PROPOSED_MUST_RATIFY` / TBDs |
| GAP-35 | **D-4** | CORRECTED — topology file received + registered (`PENDING_SIGNATURE`) |
| GAP-36, GAP-37 | **O-1 (+ dead-man webhook)** | OWNER physical secrets / rotation |
| GAP-39 | **D-16** | OWNER capsule-ordering |
| GAP-48 | (Origin lib built) | BUILT-IN-ORIGIN (`control/comparator.py`); running it is on-box (WO-D) |
| GAP-50 | **D-22 (below)** | OWNER-GATED capsule mapping |

#### **D-22 · Sign the `capsules.py` ↔ RC2 CAP-01…CAP-05 mapping** — P2 · semantic (GAP-50 / WO-D task D2)

| Field | Content |
|---|---|
| **The finding** | `capsules.py` carries 5 semantic entry-convention IDs bound by name + evidence; the RC1/RC2 **ordinal** mapping (`PAR-174…PAR-178`) is **explicitly refused, not guessed** (`rc2_ordinal_disclaimer`). Until a signed mapping exists, the comparator (GAP-48) can only align Origin candidates to engine detectors by geometry, not by semantic identity. |
| **Origin scope** | Origin owns `capsules.py` and does the right thing (refuses to guess). Recorded refusing-in-place — an agent does **not** guess a single mapping row. | 
| **What only you can do** | Sign the `CAP-01…CAP-05` mapping table (name + evidence per row); where evidence is insufficient a row reads `UNRESOLVED_SEMANTIC_OWNER_REQUIRED` — evidence, never coverage. | 
| **Blocks** | Semantic-identity alignment in the comparator run (WO-D). | 
| **Status** | OPEN |

---

## Where the mechanisms live (so you can verify each refusal yourself)

- **Every `PROPOSED_MUST_RATIFY` value** refuses via `BLOCKED_ON_RATIFY(<param>)` in its formula
  module; the unedited binding registry mints no capability (proven by a per-formula
  "honest-dark" test).
- **B00R** fail-closes to `BLOCKED`/`UNAVAILABLE` until the four root acts complete
  (`tools/b00r_gate.py`, `tests/b00r/`).
- **CO-13 / CO-14 / OWNER-TOPO-01** consumers answer `BLOCKED_ON_RATIFY(<id>)` /
  `PENDING_SIGNATURE` until signed.
- **The Part D golden registry** is recorded in `docs/control/formula_repair_overlay.v1.json`
  (a separate, non-arming artifact — the RC3 bundle bytes are never edited, CO-01).
- **The formula errata (D-21):** ERR-01 is closed in code + `TestErr01MutuallyExclusiveStates`
  (F10 `_state_for` returns exactly one state per pen); ERR-02 is recorded owner-gated with an
  honest note in `excursion_reclaim_v2.py` (the code faithfully implements the vendored CORRECTED
  LAW; the proposed redefinition is a signed-owner spec change); ERR-03/D-17 is recorded
  owner-gated with an honest note in `order_block_v2.py` (F12 behaviour unchanged; the A/B/C
  choice is the owner's).
