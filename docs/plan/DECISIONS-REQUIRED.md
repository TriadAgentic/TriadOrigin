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

## 0 · Owner instruction of 2026-08-14 — RECORDED, and exactly how far it reaches

> *"#36 approved and B00R close it"* — account owner (leesbak@gmail.com), in session.

**Recorded as a real owner instruction. Acted on to its lawful limit, and no further.** What it
does and does not reach is set out below, because the honest boundary this whole register exists to
hold is that **an approval expressed in a chat is not a cryptographic act** — the estate's own
doctrine states it plainly: *an email is not authentication* (GOV-01 §2.2 — the account-owner
consent line **follows the key**, it does not replace it).

### What was done on this instruction

* **PR #36 was taken out of draft** and review was formally requested from **@djordi10**, the
  CODEOWNER of every governance surface it touches. That is the one mechanical step an owner
  approval unlocks, and it merges nothing.
* This record was written. Nothing else changed: no signature was created, no tag was published, no
  gate was bypassed, no posture moved.

### Why #36 still cannot merge — three structural facts, each verified

| # | Fact | Evidence |
|---|---|---|
| 1 | **PR #36 has no human review of any kind.** The only review event is an automated Codex bot **comment** (`state: COMMENTED`, not `APPROVED`) — and it is against `6e831f71`, which is **stale**: head is now `505e209`. | `pull_request_read --method get_reviews` |
| 2 | **You cannot approve it: you are its author.** #36's author is `likosubakti`. GitHub does not permit self-approval, and the B00R gate names this exact case a stop condition — `BLOCKED_REVIEW_SAFE_HOLD` for an approval that is *"absent, self-authored, stale, or not exact-head"*. `D-7` (reviewer ≠ author) is therefore structurally unmet by any act of yours. | `.github/CODEOWNERS`; `docs/governance/B00R_EXTERNAL_AUTHORITY_AND_CLEAN_RUNNER_HANDOFF.md` §11 |
| 3 | **CODEOWNERS says so in its own words:** *"@djordi10 has live administrator permission on this repository and is not the corrective PR author. Native exact-head review remains mandatory; this file is not evidence that review happened."* | `.github/CODEOWNERS` |

`mergeable_state` reads `clean` and the green button is live. **That is precisely the condition the
PR body warns about** — *"Do not merge on a green button."* It is also worth stating that #36's base
is `agent/b00r-generation-2-forward-repair`, **not `main`**, so merging it would not close B00R even
if every review gate were satisfied.

### B00R: the machine verdict is `BLOCKED`, and the gate says source mode can never close it

`tools/b00r_gate.py --mode source --expected-head 505e209 …` was run at this head. Fifteen checks
PASS — including `tests_seed0: 3150 passed` / `tests_seed1: 3150 passed`, `e2e_audit: all 30 stages
passed`, `reproducible_build`, `wheel_install`, `dark_capability`, `historical_evidence`. Then:

```
[BLOCKED] codeowners_identity:   CODEOWNERS_PROVIDER_IDENTITY_UNAVAILABLE:LIVE_PERMISSION_HTTP_STATUS:401
[BLOCKED] authority_root:        UNAVAILABLE_AUTHORITY_ROOT: authority_bundle:EXTERNAL_PIN_ABSENT:AUTHORITY_BUNDLE_G2_DECISION_SHA256
[BLOCKED] governance_snapshot:   UNAVAILABLE: GOVERNANCE_PROVIDER_RAW_OR_EXTERNAL_PIN_ABSENT (main.ruleset.provider.json)
B00R result: BLOCKED
SOURCE mode is engineering diagnostics only and can never close B00R. Fail-closed BLOCKED.
```

**The gate's own last line is the answer to "close it":** source mode *cannot* close B00R by
construction, no matter how green it runs. Only the post-merge **terminal receipt sequence** can,
and only from a clean checkout of a merged receipt PR.

| act | state | evidence |
|---|---|---|
| Authenticate the three root decisions (`DEC-AUTHORITY-BUNDLE-002` · `DEC-B00-REPAIR-002` · `DEC-RECEIPT-PROFILE-002`) | **DONE in-repo** | commit `de9f6ae` *"authenticate generation-2 authority root"*, authored by **josephvoxone** 2026-08-12; each file carries `authenticated: true` and an Ed25519 `signature_hex` under `key_id: owner-ed25519-2026` |
| Externally pin the g2 trust registry | **ASSERTED, NOT VERIFIABLE HERE** — the commit says *"pins set externally as Actions Variables"*, but the gate reports `EXTERNAL_PIN_ABSENT: AUTHORITY_BUNDLE_G2_DECISION_SHA256`. That is expected off-runner (the pin lives in the CI environment), so this session can confirm the artifact exists but **cannot confirm the pin is live.** It must be re-proved on the runner. | `receipt_trust_registry.g2.v1.json` present + `authenticated: true`, three keys; gate `authority_root` BLOCKED |
| Install the no-bypass `main` ruleset | **ASSERTED, NOT VERIFIABLE HERE** — commit `6191b65` captured a live provider object (*"merge-only, canary ref included, bypass empty"*), but the gate reports the raw-or-pin pair absent in this environment. Same caveat: re-prove on the runner. | gate `governance_snapshot` BLOCKED |
| **Threshold-sign receipt-v3 → publish `B00R_RECEIPT_ANCHOR_G2`** | **NOT DONE — and not startable here** | see below |

I am stating the middle two as *asserted* rather than *done* deliberately. Their commit messages
claim the external half was performed; the only mechanism that can confirm it returns
`EXTERNAL_PIN_ABSENT` from this environment. Recording them as closed on the strength of a commit
message would be precisely the kind of unearned green this generation-2 repair exists to eliminate.

**The fourth act is the whole remaining gate, and none of it can be produced here.** Four
independent artifacts are absent:

1. **`evidence/receipts/B00R.g2.receipt.v3.json` does not exist.** Only the generation-1
   `B00R.receipt.v3.json` is present, and `CLAUDE.md` is explicit that *"the generation-1
   `B00R_RECEIPT_ANCHOR` is historical evidence, never a B01C predecessor."*
2. **It needs a 2-of-2 threshold signature.** `governance.py` pins `threshold == 2` over roles
   exactly `["EVIDENCE_PRODUCER", "INDEPENDENT_COUNTERSIGNER"]` — i.e. Ed25519 signatures from
   `producer-ed25519-2026` **and** `countersigner-ed25519-2026`. Both are `@uponlytrader.com`
   identities in the g2 registry. **Neither key is the account-owner key that issued this
   instruction, and no key is held by this session.**
3. **`evidence/B00R_G2/tag_ruleset.provider.json` does not exist** — the no-bypass tag ruleset
   targeting `refs/tags/B00R_RECEIPT_ANCHOR_G2` has not been installed or captured, and its provider
   `updated_at` must be strictly **before** the signed receipt's `observed_at_us`, so it cannot be
   back-filled after the fact.
4. **The tag `B00R_RECEIPT_ANCHOR_G2` does not exist** — locally or on the remote. Only the
   generation-1 `B00R_RECEIPT_ANCHOR` is published.

Fabricating any one of them would be the exact failure this repository was rebuilt to make
impossible. The lawful state is a **named refusal**, and it is named here.

### The remaining sequence, in order (all owner / clean-runner acts)

0. Re-run `b00r_gate --mode source` **on the CI runner**, where the external pins and a permissioned
   token exist, to convert the three environment-BLOCKED checks into real PASS/FAIL. Off-runner they
   are `UNAVAILABLE`, which is neither.
1. Merge #36 **after** @djordi10's exact-head CODEOWNER approval — the source merge.
2. Install the tag ruleset on `refs/tags/B00R_RECEIPT_ANCHOR_G2` (no exclusions, update **and**
   deletion blocked), capture its raw provider object to `evidence/B00R_G2/tag_ruleset.provider.json`,
   and externally pin those exact bytes as `B00R_G2_TAG_RULESET_SHA256`. **Do this before signing.**
3. Produce `evidence/receipts/B00R.g2.receipt.v3.json` and threshold-sign it 2-of-2
   (`producer-ed25519-2026` + `countersigner-ed25519-2026`).
4. Open and merge the **receipt PR** (evidence-only content; mixed or historical content fails
   `FAIL_RECEIPT_LAYOUT`).
5. Create the annotated tag on the exact receipt merge, message bytes exactly as
   `B00R_EXTERNAL_AUTHORITY_AND_CLEAN_RUNNER_HANDOFF.md` §10 specifies — no `-s`, no repeated `-m`,
   no reordered fields, no missing terminal newline. Publish once, never repoint.
6. Run the terminal gate from a clean checkout of the receipt merge:
   `python tools/b00r_gate.py --mode receipt --base-sha "$SOURCE_MERGE" --expected-head "$RECEIPT_MERGE" --receipt-pr "$RECEIPT_PR" --now-us "$NOW_US" --pins "$PINS_JSON" --provider-pin "$MAIN_RULESET_EVIDENCE_SHA256" --anchor-ruleset-pin "$B00R_G2_TAG_RULESET_SHA256"`

**Only that terminal sequence may return `PASS_REPOSITORY_SAFE_HOLD`** — the only permitted B00R
result. Until it does, B01C stays frozen and posture stays `DENIED_SAFE_HOLD`, `OFF/OFF/OFF/LIVE`.

Full operator detail: `docs/governance/B00R_EXTERNAL_AUTHORITY_AND_CLEAN_RUNNER_HANDOFF.md` §§9–11
and `docs/plan/ONBOX-GUIDE.md` O-3.

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
| **D-21 · ERR-02 (F13)** | ~~The errata proposed redefining the excursion `extreme` to accrue over **every** `t_exc..t_confirm` bar.~~ **WITHDRAWN by R-01 (2026-08-13) as reviewer error.** | **No action — the developer's refusal is validated on every count.** R-01 formally WITHDRAWS ERR-02 / GAP-12 / WO-H: the code was RIGHT (the F13 reset branch rule 3 DOES deepen the reset bar's own low — `extreme==9960` in `test_h10`), the reviewer's premise was wrong, and this repo's refusal to edit a passing formula to match a proposal is exactly the discipline R-01 elevates to **standing LAW-9**. The `excursion_reclaim_v2.py` docstring records the withdrawal; a **byte-neutral clarifying test** (`test_reset_bar_low_is_applied_to_the_extreme_err02_r01_corrected`) pins the correct behaviour without changing a single emitted byte. | Nothing — closed as reviewer error. (No amendment, no signature, no F13 byte change.) | ✅ CLOSED — WITHDRAWN (R-01); code + tests unchanged and correct |

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
| GAP-12 | **D-21 (ERR-02)** | ✅ WITHDRAWN (R-01) — reviewer error; code faithful and correct; no amendment; `WO-H` retired (identifier never reused) |
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

### II·G · The revision records + master sequence (R-01 / R-02 / R-03 / LAW-1…LAW-9)

The owner supplied `TRIAD_REVISION_RECORD_R-01_2026-08-13` and `-R-02-` and `-R-03-` (correction
records) and `TRIAD_MASTER_SEQUENCE_2026-08-13` (sequencing control + nine standing laws), all
vendored in `docs/repair/`. Their Origin-scope dispositions:

| Item | Disposition |
|---|---|
| **ERR-01 / GAP-11 / WO-G** | CLOSED-IN-ORIGIN (F10 predicates + property test) — R-01 marks ERR-01 closed. |
| **ERR-02 / GAP-12 / WO-H** | **WITHDRAWN by R-01 as reviewer error.** Code correct; refusal validated; `WO-H` identifier retired, never reused. |
| **ERR-03 / GAP-13 / WO-I** | OWNER-GATED (D-17) — F12 A/B/C confirmation semantics; behaviour unchanged. |
| **LAW-9 (the standing law R-01 elevates; R-02 strengthens step 2)** | **RECORDED as estate law.** Any external finding that would alter a formula's **emitted bytes** — or flip a currently-passing test — is an **amendment** (owner signature + prior spec-amendment PR), **never an agent repair, however obviously correct it appears.** The discriminator is *bytes, not correctness.* **R-02 §1.2 strengthens step 2:** when classifying a finding the reviewer MUST read the implementing code + the tests that pin it BEFORE the finding is written; a finding that would flip a passing test MUST quote that test by name + file:line and say why it is wrong — if it cannot name the test, the finding is not ready. (Neither ERR-02 nor R-01 §1.5 named the test they contradicted — that absence was the detectable signature of the defect in both.) It governs every repair item in `docs/repair/`. |
| **WO-J (RPI book-completeness coverage)** | **OWNER-GATED AMENDMENT — NOT ready agent work (R-02 §2 accepts this verdict without reservation).** WO-J adds a **mandatory** `book_completeness` field to F15/F16/F17 → CHANGES emitted bytes + turns 16 frozen-dataclass constructor sites into `TypeError`, and its new F15 refusal `COVERAGE_UNVERIFIABLE_RPI` replaces the current coverage emit. Under **LAW-9** it lands only in a signed spec-amendment PR-set (then built as `flow_atoms_v3.py`, v2 retired `RETIRED_DEFECTIVE{ref=WO-J/GAP-06}`, v2 bytes preserved). **Enum correction (R-02 §2.1):** the canonical `book_completeness` enum is **`{COMPLETE, RPI_EXCLUDED, UNKNOWN}` — three values, `UNKNOWN` the no-default default** (the work order's two-value line is the error; carry the 3-value enum into the amendment PR). **WO-J-a (optional tripwire, R-02 §2.2):** a strict-xfail record in `tests/formulas/` to keep the amendment from being forgotten — **NOT added here:** a faithful `strict=True` xfail must FAIL for the right reason, which needs the not-yet-existing `book_completeness` field to even express; R-02's placeholder `…` body would trivially PASS ⇒ XPASS ⇒ the strict marker BREAKS the gate. Per LAW-9 step 2 (checked against pytest's strict-xfail semantics, not just the prose) the tripwire is deferred INTO the amendment PR, where the assertion can be real. Code UNCHANGED. |
| **WO-C (F18 remove-generation-floor)** | VERIFIED_OK / check-only — F18 already uses the ratified PAR-061 `2/1` (injected, not hardcoded); 32 tests pass. No change; WO-C's remove-generation-floor is the owner redesign D-11. |
| **R-01 §1.5 optional byte-neutral test** | **CLOSED — R-01 §1.5 fully WITHDRAWN by R-02 §1 (a SECOND reviewer error on the same machine, opposite direction).** R-01 §1.5 claimed the reset bar does NOT deepen; R-02 confirms it DOES (the machine was right both times). The proposed `test_reset_bar_low_is_not_applied_to_extreme` is withdrawn — **do not add it.** The developer's replacement `test_reset_bar_low_is_applied_to_the_extreme_err02_r01_corrected` is "correct and sufficient" (R-02 §1.3) — added, byte-neutral, suite green. F13 requires no further work of any kind. |
| **GAP-51 (NEW · P0 · R-02 §3) — the symbol-selection confound** | **Recorded; OUT-OF-ORIGIN measurement, built in TriadLearning WO-A A5.** The live WR is measured on a NON-RANDOM subset (only the ~2 of 30 symbols that clear the funnel), so the 13 pp has a FOURTH possible source — symbol selection — distinct from adverse selection / denominator / stop-regime. Closed by the A5 per-symbol baseline reconciliation + the sample-size distinguishability statistic (`TriadLearning/analysis/wo_a/` `a5_per_symbol_baseline.sql` + `sample_size.py`, tests green) and the **SYNC-2 amendment**: WO-B is now gated on BOTH (a) `no_fill_win_share` below 50 % AND (b) A5 showing symbol selection does not dominate; and if `n_total` is below the bar the gap is not yet statistically distinguishable. **The BAR is corrected by R-03 §5 (row below): it is a function of the OBSERVED rate, not the fixed 93 this row first carried.** Origin owns no economic layer — this is Learning/measurement, recorded here for the estate view. |
| **R-03 §5 — the fixed 93-trade bar is miscalibrated (SELF-CORRECTION of R-02 §3.2)** | **ACCEPTED and REPAIRED under LAW-9 agent authority (out-of-Origin, TriadLearning).** 93 is the required sample only at an observed 40 %; the bar climbs to 221 at an observed 45 % and 1,009 at 50 %, so a frozen gate RELEASES on ~42 % of the required evidence at 45 % and HOLDS on already-adequate evidence at 30 %. Repaired by passing the OBSERVATION, not by adding a formula: `min_n_for_power` was ALREADY R-03's exact expression, so a second derivation would have created the estate's own re-deriver drift class — `n_required()` is a thin adapter over it and `distinguishability()` returns a tri-state verdict PLUS the bar it judged against, so the artifact prints both numbers. **Zero tests flipped** (LAW-9 clean: `is_distinguishable` already took `p1` as a keyword; the 93 case stays correct; 11 original pins pass verbatim, 26 added). **ERRATUM back to the reviewer:** R-03's own §5 table rows for 30/35/38 % (31/50/71) are `round()` of values its own `ceil()` formula puts at 31.12/50.37/71.21, and its `0.84` power-z is less precise than the module's `0.8416` — the module is HIGHER at every disagreement, and a required-sample bar is never rounded down. The `n_floor` binding is **D-23 (below)**. |
| **R-03 §2 / M-1 — the combined check is not a required status check** | **CONFIRMED BY DIRECT READ, and the finding is stronger than R-03 inferred.** R-03 §8 marked this an inference from `mergeable_state` semantics and asked for the settings to be read; read: `TriadLearning main` is **`protected: false`** — not merely "the check is not required", there is no branch protection at all. **Asymmetry newly visible:** `TriadOrigin main` reads `protected: true` (with `b00r-ruleset-canary` also `true`, which is the internal control proving a ruleset in this org does set the flag) — so the repo under `DENIED_SAFE_HOLD` is protected while the repo carrying the live measurement code is not. R-03's disposition stands: no action against the merge, and **`WO-P` escalates** — until the ruleset is installed, "gates green" and "merged to main" have no causal link. The install is an owner/GitHub-admin act; an agent can neither perform nor fake it. |
| **R-03 §3 / M-2 — a permanently-red check carries zero signal** | **CONFIRMED (281 ruff findings exact) and WORSE than stated: `mypy` fails independently with 42 errors in 5 files**, so a lint-only baseline would have left the combined check exactly as uninformative as it found it. Remedy BUILT out-of-Origin (`TriadLearning tools/lint_ratchet.py` + `data/lint_baseline.v1.json`, CG-LINT-RATCHET): both tools frozen, fails only on NEW findings, refuses fail-closed on tool-version skew, never fabricates a clean read. **Two corrections back to the reviewer:** (1) the "estate's OWN existing CI-ratchet law … already applied to the param census" does NOT exist as described — `census.py`/`test_param_census.py` assert classification and units, not a never-increase count ratchet, so this is a NEW discipline, not a re-application; (2) the baseline is stamped `PROVISIONAL_LOCAL_VERSIONS` and is deliberately **NOT wired into CI**, because it was generated with ruff 0.15.8 / mypy 1.19.1 while `uv.lock` pins **0.15.21 / 2.2.0** for the runner — a baseline claiming agreement with a version nobody ran is a fabricated receipt. Regenerating it on the runner is the operator step. **SHARPENED by a live CI read (PR #463, job 94499973501): the check is worse than "permanently red" — `ci.yml` runs `Ruff (lint)` FIRST and GitHub Actions aborts a job at its first non-zero step, so `Mypy (typecheck)`, `Pytest (unit + golden conformance + round-trip)` and the build-rejecting `PII-lint` HAVE NOT EXECUTED on any branch or PR for as long as the debt has existed.** The check named `lint · typecheck · test · conformance` only ever ran the first quarter of its own name; the conformance/round-trip/PII evidence it appears to provide has been vacuous, not merely uninformative. Corroboration for the frozen baseline: the runner's own locked ruff reports **`Found 281 errors`** — the exact frozen total, so the count is version-agreed even though the per-file distribution is not yet (the `PROVISIONAL` stamp stands). |
| **R-03 §4 / M-3 — the checkpoint seal is owed** | **ACKNOWLEDGED, still OPEN, still owner-gated.** The seal was correctly not performed unbid (R-03 §1 records that call as correct), and performing it now unbid would contradict that record: it means creating a `checkpoint/<date>-<name>` branch at fresh `main` across five repos, which the standing branch instruction reserves to the owner's explicit word. The agent-executable half (the TriadLearning branch + its `CHECKPOINTS.md` row) is ready on request; the annotated-tag mirror is an operator step (the App token cannot push tags). |
| **R-03 §6 — the pin-vs-grant scope check (the D-7 reviewer's question)** | **ANSWERED WITH EVIDENCE; the verdict is the reviewer's.** Computed with the classifier's own predicate over `governance.parse_source_hashes`: **58 of the 137 pinned paths are not admitted by the gen-2 SOURCE grant** (35 of them are `verify_source_hashes.REQUIRED_MEMBERSHIP` entries; 23 are pins outside both). **But the merge introduced ZERO of them:** parentA(8254043)=133 pins, parentB(661923b)=120, merge=137 = exactly the union, merge-only = `[]`, and all 58 out-of-grant pins were ALREADY in parentA. So the pin attests to no scope the pin file did not already attest to before the merge, and **no D-3b widening is forced by the conflict resolution.** Structurally, pinning and granting are disjoint: the grant is a PURE POSITIVE allowlist with no exclusion rules (so R-03's premise that it "deliberately EXCLUDES the formula paths" is a paths-not-listed condition, not an exclusion clause), and `verify_source_hashes` asserts only grant ⊆ pinned — its exit 0 is evidence for the disjoint reading, never for pinned ⊆ grant. |
| **M-4 (NEW · this cross-check) — the gen-2 grant is narrower than the repair programme's own documentation surface** | **RECORDED, owner-gated with D-3b.** `classify_milestone_pr.source_path_allowed` returns **False** for `docs/plan/DECISIONS-REQUIRED.md`, `docs/repair/README.md`, `docs/repair/REPAIR-REPORT-*.md` and every vendored revision record — the grant admits only 4 `docs/plan/` and 2 `docs/repair/` paths — so **every repair-record commit (including the R-01/R-02 vendorings already on the branch) trips `SOURCE_PATH_OUT_OF_SCOPE` at the CI classify step by construction.** This is not a reason to stop recording the programme; it is the observation that the grant and the programme's evidence surface disagree, and the reconciliation belongs in D-3b's widening (which the double gate at `tests/b00r/test_b00r_ci_gates.py` also forces to re-pin `governance.py`). Reported, not worked around. |
| **M-5 (NEW · this cross-check) — a live `CG-REFUSAL-CODES` violation, caught by the very test run M-2 proved CI never performs** | **FOUND and REPAIRED out-of-Origin (TriadLearning), display-only.** Running the full suite locally — the run `ci.yml` has never reached — surfaced one real failure: `TriadVenueGateway src/triad_vgp/reject_taxonomy.py` added `RejectClass.MAINTENANCE = "maintenance"` (commit `8c7d667`, the A-010 typed venue-error subclasses; Binance −1016 "system busy / undergoing maintenance") **without moving its coupled §2b glossary row** — the obligation VGP's own `CLAUDE.md` states verbatim ("A change to `RejectClass` moves with the glossary row in the same PR-set"). **Invisible twice over:** the drift-lock `test_vgp_reject_classes_are_fully_explained` is sibling-or-skip, so it SKIPS wherever `TriadVenueGateway` is not checked out beside `TriadLearning`, and where it DOES run — the estate dev layout — CI never got past ruff. A drift-lock that skips in CI and never executes locally is not a lock; **M-5 is the first concrete cost of M-2, not a coincidence.** Repaired: the plain-words row + `KIND`(`health` — the venue is not answering, not refusing) + `ORIGIN`(`venue`) + `STATUS`, both generated faces regenerated. The words carry the load-bearing fact that `maintenance` is deliberately NOT in VGP's `_VENUE_WIDE` set (auth/margin only) — an outage clears itself and a latched venue-wide halt would outlive it. Display-only (§2b: the glossary can never gate or filter); the registration point stays singular at the VGP source. **No Origin scope; no owner decision required** — recorded because it is evidence for M-2's severity and for `WO-P`. |
| **B-6 (NEW · Codex review of PR #463, 2026-08-13) — the WO-A canonical POPULATION is undeclared, and it sets the numbers SYNC-2 releases WO-B on** | **RECORDED, OWNER-GATED (out-of-Origin, TriadLearning).** An independent reviewer raised, and the cohort axis confirms, that **A1/A2 replay and aggregate EVERY cohort** (personas are cloned per decision with different entry rules, so A4 reconciles duplicated heterogeneous populations) and that **A5 counts resolved shadow outcomes with no gate-accepted/live constraint and no frozen-baseline timestamp boundary**. The size of the question is visible in the two numbers already on the table: the on-box run measured **47** gate-accepted resolved rows while A5's population is **317,806** — and under the R-03 §5 corrected bar those two sit on OPPOSITE sides of distinguishability (47 vs a required 139; 317,806 vs a required 37). Choosing the canonical cohort/class predicate therefore SETS the SYNC-2 verdict, so it is a declared decision with the cohort semantics named, not an agent's mid-PR adjustment. **Two REAL divergences from the canonical resolver are already named + measured in the harness** (the OHLC replay cannot recover intra-bar print order and resolves adverse-first always ⇒ `no_fill_win_share` is a LOWER BOUND biased AGAINST the mechanism WO-B tests; and the fixed 24 h scan vs the resolver's `max(4h, 2*hold_s)` horizon) — closing those is a replay redesign through `tape.first_touch`, which would flip a pinned test and is therefore LAW-9-shaped. |
| **Sequencing / lanes / SYNC points** | Recorded; the Master Sequence Part 1 supersedes only the work order's `EXECUTION ORDER` section (SYNC-2 further amended by R-02 §3.4; its distinguishability bar corrected by R-03 §5). Origin's economic-layer / venue / bank / on-box items stay OUT-OF-ORIGIN. |

#### **D-23 · Ratify the A5 minimum-sample floor (`n_floor`, proposed 30)** — P2 · research (GAP-51 / R-03 §5)

| Field | Content |
|---|---|
| **The finding** | R-03 §5 replaces the fixed 93-round-trip bar with `n_required(0.544, observed_wr)`, which collapses toward ~32 as the observed gap widens — and at small `n` the normal approximation behind it degrades, so a wide-gap observation could clear a bar of a handful of trades. R-03 therefore asks for a floor below which the answer is `INSUFFICIENT_SAMPLE_REGARDLESS`, and proposes **30**. |
| **Origin scope** | **OUT-OF-ORIGIN.** The statistic and its gate live in `TriadLearning/analysis/wo_a/sample_size.py`; Origin owns no economic or measurement layer. Recorded here only because the register carries the GAP-51 lineage (R-02 §3 / R-03 §5) that this binding belongs to. |
| **What only you can do** | Ratify the value. It ships as `N_FLOOR_PROPOSED = 30`, marked `PROPOSED_MUST_RATIFY`, and is a NARROWING guard by construction — it can only ever withhold a `DISTINGUISHABLE` verdict, never manufacture one, so an unratified floor cannot release a window it should have held. |
| **Blocks** | Nothing today (the floor is already conservative and the whole A5 read is on-box-pending). It blocks only the claim that the floor is *ratified* rather than *proposed*. |
| **Status** | OPEN |

---

### II·H · The structural-defect repair (UC-01…UC-10 / VG-01…VG-04 / WO-S1…WO-S8)

The owner supplied `TRIAD_STRUCTURAL_DEFECT_REPAIR_2026-08-13` ("unreconciled constants" +
"vacuous gates" + eight work orders), vendored in `docs/repair/`. A 13-agent read-only pass ran
against the live code of all five repos **before** any repair was written; the full disposition is
`docs/repair/STRUCTURAL-DEFECT-CROSSCHECK-2026-08-13.md`. Headline: **the meta-defect is real and
is now closed; the register is not — eight of ten UC rows are stale, refuted, or mis-framed.**

| Item | Disposition |
|---|---|
| **UC-01 (governor hardcodes RR 2.5 · 44 net_rr refusals)** | **REFUTED, both halves.** The governor holds no RR literal — it consumes the caller's floor (serde default tracks the vendored 2.0, reconciled 2026-07-29; the live path passes the per-profile `ladder_60_40` 1.7). And `net_rr` is `None` at every production construction site, so the 6b check cannot fire at all. |
| **UC-02 (min_stop 45 vs 67)** | **STALE.** 67 in all four planes since CG-STOP-FLOOR-67 (2026-07-31, contracts 1.24.0/1.25.0), CI-checked by `verify_alignment.py §15c`. This is the repair the estate already performed. |
| **UC-04 (`MAX_COST_R = 1/5` sets the ceiling at the edge)** | **REFUTED — and it is the document's load-bearing row.** `MAX_COST_R` has **zero occurrences** anywhere in the estate; the derivation `MIN_STOP_WIDTH = H / MAX_COST_R` is not implemented. `WO-S2` would have written a new derivation into the money line to repair arithmetic nothing performs. |
| **UC-03 (risk_pct_equity dead)** | **OWNER-GATED policy interaction, not an unreconciled constant.** The margin cap is deliberate and shrink-only; risk sizing still bounds qty by stop distance. Whether the combination under-risks is your capital decision (the document's own `WO-S4` agrees). |
| **UC-05 (admission 8.4/min)** | **CONFIRMED as a real limiter · OWNER-GATED.** Already registered as CG-ADMISSION-CAPACITY-PROFILE. Widening it means arming `profiled` against a MEASURED on-box capacity artifact that does not exist; the mode fails closed without one. An agent may build the measurement, never the widening. |
| **UC-06 (side policy at selection)** | **REFRAMED.** Long-only is the ratified LIVE30-PROFITABLE-ONLY settlement (2026-08-06). SHORT is not foreclosed — it accrues on `candidates.shadow` precisely so the decision stays revisable on evidence, which answers the row's "prevents its own repair" concern. |
| **UC-07 (fee constant)** | **PARTIALLY CONFIRMED · BUILT.** Vendored `fee_model.v1.json` taker = **5**; the one unmanaged copy is `edge_jobs.DEFAULT_TAKER_FEE_BPS = 4.5`. Locked as a SEALED DIVERGENCE (both values pinned), **not equalised** — moving the research default moves already-computed research outputs, which is yours to decide. |
| **UC-08 (min notional)** | **REFRAMED · BUILT as CG-MIN-NOTIONAL.** The real finding is five sites, no coupling row, and **two different laws**: the config floor is a sizing BUMP, the venue floor was a refusal that was REMOVED (`ecc942d`) leaving its whole input path computed and read by nothing. Four comments — including two operator CLI help strings and a test **name** — still promised the removed skip; corrected. **Two owner-gated findings raised: D-24 below.** |
| **UC-09 / UC-10 / VG-03 (CI hygiene)** | **CONFIRMED — the only rows that verify.** Already dispositioned in §II·G (M-1 `WO-P` escalation; M-2 `CG-LINT-RATCHET` built, deliberately unwired pending runner regeneration). |
| **VG-01 (F15 coverage ratio)** | **OWNER-GATED AMENDMENT (`WO-J`, unchanged).** Emitting `NULL{COVERAGE_UNVERIFIABLE_RPI}` changes emitted bytes — LAW-9. |
| **VG-02 (`get_sim_gap` vacuous HONEST)** | **BUILT — additively.** `verdict_basis` (`VACUOUS_PRE_LIVE`/`MEASURED`) + `measured` now ship beside the verdict. The `verdict` TOKEN is deliberately unchanged: moving it flips `test_databank_local.py:360`, making it an amendment (LAW-9 — bytes, not correctness). |
| **VG-04 (`matrix_off = 0`)** | **ACCEPTED as written.** The sharpest observation in the document: a check that is correct, passing, and measuring a question that was never the suppressor. |
| **WO-S8 (the CI ratchet) — the meta-defect's own example** | **BUILT (TriadLearning `triad_param_census.py` + `data/param_baseline.v1.json`).** Engine 552 / executor 861 frozen; `MIXED-ABS-REL` pinned at ZERO regardless of the baseline; an absent sibling tree is a NAMED refusal, and `--allow-absent` skips LOUDLY stating the run proves nothing. Stamped `AUTHORITATIVE_DETERMINISTIC` (stdlib regex — no tool-version skew), unlike the lint baseline. |
| **"Unblock all 30 symbols"** | **NOT AGENT-EXECUTABLE — and the premise does not hold.** The 30 are already unblocked at every symbol-scoped gate (matrix 90 ON cells ×4, LIVE30 registry + all 12 views at 30, no lane carries a symbol field, canary default-OFF). The binding limiters are (1) portfolio concurrency `max_open_positions=10` / `per_symbol=1` / `max_net_exposure_quote=50000`, (2) the 8.4/min admission bucket, (3) the ratified money-lane cell scope — **all three GOV-01 widenings.** The free first act is diagnostic: read `TRIAD_LIVE_SETUPS` on the box. |

#### D-24 · The min-notional behaviour reconcile (NEW · money-line · Executor)

| | |
|---|---|
| **The finding** | Two defects surfaced by CG-MIN-NOTIONAL, both raised and deliberately NOT fixed. **(a)** `CHECKPOINTS.md:128` seals the 5→20 raise as "sub-$20 now *skips cleanly* instead of a venue reject" — the governor has never skipped, it **bumps** (rounds a sub-floor order UP via `ceil_to_lot(floor / entry_mid)`). **(b)** That bump raises risk above `risk_pct_equity`, because the size is no longer the risk-derived size. |
| **Origin scope** | **OUT-OF-ORIGIN.** Money-line behaviour in `TriadExecutor governor.rs`; Origin owns no execution layer. Recorded here because (a) touches the estate checkpoint ledger, which is tamper-evidence and is never edited. |
| **What only you can do** | Decide the reconcile for (a): make the code SKIP as the ledger describes, or record that the ledger row's description was wrong at seal time. Either is a decision; neither is an agent repair (LAW-9 — changing bump→skip changes money-line behaviour). For (b), decide whether the bump is acceptable at all, or whether a sub-floor take should refuse. |
| **Magnitude (b)** | Currently latent, stated honestly rather than as an alarm: at 2 % risk and the `[67,120]` bps band, the bump only engages below roughly **$7** equity. It is a real defect at small equity, not a live one today. |
| **Blocks** | Nothing today. It blocks the claim that the ledger and the code agree. |
| **Status** | OPEN |

---

### II·I · The adjustment set (WO-D1 / WO-D2 / WO-X1 / WO-X2 · UC-11)

Vendored byte-identically at `docs/repair/TRIAD_ADJUSTMENT_SET_2026-08-13.md`
(sha256 `08ce7d87…`); reproduced and dispositioned in
`docs/repair/IMPLEMENTATION-REPORT-2026-08-14.md` §2. Headline: **a markedly better document than
the structural-defect repair — it attests its own numbers as a MODEL and forbids the one thing an
agent must not do — and its two READY work orders are built. Four defects were found by reproducing
its own arithmetic, and one of them is already live in the bank.**

| Item | Disposition |
|---|---|
| **WO-D1 (drawdown metric suite)** | **BUILT (TriadLearning `analysis/drawdown/`, 95 tests).** Eleven metrics + the bank adapter + a SELECT-only sequence query + the reference model. Three documented corrections to the work order as written: the ulcer index in **percent** is honest-null (the R-unit series has no percentage basis), a censored recovery is **labelled** rather than reported as a duration, and duplicate `decision_id`s are **refused**, never deduped. |
| **WO-X1 (exit-cause decomposition)** | **BUILT (TriadLearning `analysis/exit_capture/`, 41 tests).** Two proposed buckets are structurally underivable and are named as coverage gaps rather than invented (`TRAIL_TRIGGERED` cannot exist — a trail closes as `sl`, and the D3(c) trail is `trail_dark`; `TARGET_FILLED_PARTIAL` needs the DARK fill.v2 lineage plane). Six real causes the work order omits — kill · breaker · invalidation · reconcile · expiry_7d · liq — are each named rather than swept into the leftover bucket the work order itself forbids. |
| **WO-X2 (the ladder cohort)** | **NOT BUILT.** Its own entry gate (`WO-X1 published`) is not met, and `ladder_60_40` already ships as the ACTIVE exit profile with multi-leg TP armed since 2026-07-31 — so the "add a ladder cohort" framing is behind the estate. |
| **F1 · the comparison table charges two costs** | **RECORDED.** Four of five Part-1 rows reproduce at `c = 0.20 R`; the status quo row reproduces only at `c = 0.1444` (`= (2.0 + 4.5)/45`, a maker-in/taker-out round trip) — **28 % less cost than every alternative it is compared against**. At a common `c`, its EV is `−0.0009` (not `+0.0547`) and its median drawdown `−34.8 R` (not `−26.0 R`). The direction runs AGAINST the document's own conclusion, so this is an error, not a thumb on the scale — but the ladder's drawdown advantage is **45 %, not 25 %**. |
| **F2 · the cost basis is a retired anchor** | **RECORDED.** `c = 0.20` is `9 bps / 45 bps`; the live per-trade floor has been **67 bps since 2026-07-31** (CG-STOP-FLOOR-67). And `9` is not a vendored named quantity — `fee_model.v1.json` names `maker_maker 4 · maker_taker 7 · taker_taker 10` and carries its own instruction, *"names are law: consumers import a NAMED quantity, never a bare number."* At the live floor the review's `c` is **1.91×** the vendored `maker_taker`. |
| **F3 · `INV-3` refutes the document's own recommendation — and the defect is ALREADY LIVE** | **RECORDED · money-line-adjacent, OWNER-GATED.** The work order calls leg-aware fees *"the single most important line in the work order"* and then charges the two-leg ladder one exit fee. Charged consistently, the ladder is no longer second on EV/σ. **More importantly the same defect is already in the bank:** `simulate_ladder` (the `P-LADDER` shadow cohort) accumulates **gross R with no fees at all** and its writer has no `pnl_r_net` column, while the base cohort **is** fee-netted — so the two cohorts are **not fee-comparable today**, and any P-LADDER-vs-base comparison already published overstates the ladder. Fixing it changes recorded research outputs, so it is yours to schedule, not an agent's to repair. |
| **F4 / UC-11 · the −15R cap is not a drawdown latch** | **RECORDED · the `√n` argument SURVIVES.** Verified at `pilot_caps.rs:57`: the latch compares `realized_r` — the running **SUM** since the arm ceremony, `window_days: None` so the window never rolls — against `−15`, latches stickily, and refuses **new entries only** (no flatten). The document compares median max **drawdown** against the same number. They diverge in a specific direction: *a book that runs +20R then −30R does not breach; a book that grinds straight to −15R does.* **Early winners permanently buy latitude.** Two operational facts recorded with it: the `−15` literal has **three uncoupled copies** (Rust · `caps_state_writer.py` · `live_lane.py`), and `TRIAD_CAPS_WINDOW_START_US` is set by **no deploy script**. |
| **WO-D2 (the −15R cap options)** | **REFUSED — as the document itself instructs** (*"record all three options, implement none"*, and *"do not widen a safety cap under agent authority — ever, under any argument, including this document's"*). **This is your decision, D-25 below.** |
| **F5 · the operating point pairs two populations** | **RECORDED.** `W = 1.818` is not measured — it is back-solved from the frozen 54.4 % / +0.533R baseline constant. `42.55 %` **is** measured, on a different cut (Gate ACCEPTED, **n = 47**) whose own verdict is `HOLD_NOT_DISTINGUISHABLE` at 34 % of its bar. Pairing them is a never-blend violation on both the population and the generation axis, so every table built on the pair is a model, not a measurement — which the document states, and which this note preserves. |
| **F6 · four exit vocabularies** | **RECORDED · measurement debt.** `outcome.v1.exit_reason` (8) · `outcome.v1.exit_kind` (5, a **second** field on the same record) · `shadow.terminal_reason` (3, the only CHECK-enforced one) · `exit_trigger.v1.reason` (9). `stop` and `sl` are one event spelled two ways on one record, and **`live.trades.exit_reason` was deliberately left without a CHECK** while shadow's got one — so the live lane's vocabulary is enforced nowhere. `TARGET_FILLED_SLIPPED` is additionally **identically 0 on the shadow lane by construction** (the resolvers *assign* `exit_px = tp1_px`), so only the live lane can measure slippage at all. |

#### D-25 · The −15R cap semantics (NEW · money-line · Executor · OWNER ONLY)

| | |
|---|---|
| **The finding** | The cap is a **cumulative-sum floor**, not a drawdown floor, and it is compared in the review against a **drawdown** distribution. Under the document's own model the probability of a book with genuine positive edge eventually touching a fixed −15R sum over an unbounded window approaches certainty — that is the `√n` argument, and it survives the correction. |
| **The three options (recorded, none implemented)** | **A** — scale the floor with `√n`. **B** — cap on *departure from the preregistered distribution* rather than on a fixed depth (the document's own recommendation). **C** — keep −15R and restate its meaning as "a hard capital stop, not a drawdown tolerance". |
| **Why no agent may act** | Every option is a **widening or a re-scoping of a safety cap** (ARM-02 §5 · GOV-01). The document forbids it explicitly; so does this repo's law. An agent may build the measurement that informs the choice — that is `WO-D1`, and it is built. |
| **Prerequisite before any option is priceable** | The three uncoupled `−15` copies need one coupling row, and `TRIAD_CAPS_WINDOW_START_US` needs a deploy-script owner — otherwise "the window" in options A and B has no single definition to change. |
| **Blocks** | Nothing today. The cap is armed and behaving as written. |
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
  (F10 `_state_for` returns exactly one state per pen); **ERR-02 is WITHDRAWN by R-01 as reviewer
  error** — the F13 code was correct all along, the refusal is validated, `WO-H` is retired, and a
  byte-neutral clarifying test now pins the correct reset-bar-deepens behaviour; ERR-03/D-17 is
  recorded owner-gated with an honest note in `order_block_v2.py` (F12 behaviour unchanged; the
  A/B/C choice is the owner's).
