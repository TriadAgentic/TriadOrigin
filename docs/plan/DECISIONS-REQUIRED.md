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
