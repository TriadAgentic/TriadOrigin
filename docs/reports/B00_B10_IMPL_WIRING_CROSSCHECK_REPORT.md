# TRIAD ORIGIN — B00→B10 implementation + wiring crosscheck

**Authority for this crosscheck:** the uploaded frozen audit package — runner
`triad_origin_b01_b10_audit.py` **v1.2.0, SHA `12c8896479b902165fa2c6d3e7565ea8402b49fcfe2d044f6fd69153926d35a2`**
(byte-identical to the on-disk `audit_package/`), `README.md`, `PACKAGE_VALIDATION.md` — plus the
reconciled plan (`docs/plan/00..10`), RC3/RC4 bundles, `CLAUDE.md` ownership law, and the disposition
register.
**Method:** read-only 9-agent crosscheck — 6 milestone groups + a dedicated end-to-end **wiring**
trace + a dedicated **closure-validity/ancestry** auditor + a consolidating critic. Every capability
verified independently of any tick/report claim.
**Head:** `bd8d688` on `b00-b07-review` (PR #26). **Two axes kept strictly separate:** *is the code
built and wired* vs *is any milestone validly closed per the receipt cadence.*

---

## 1 · Headline — two axes

**Axis 1 — Implementation + Wiring: BUILT and CONNECTED, faithful to spec.** All 27 e2e stages pass,
all 14 authoritative gate commands exit 0, the combined DAG validates (1250 tasks, 2383 hard edges,
no cycles, one owner), 300+ scope tests pass. Every load-bearing safety invariant HELD. **One in-repo
actionable defect** — two e2e-walk orphans — found and **fixed this session** (§4).

**Axis 2 — Closure Validity: NO milestone is validly closed.** The package's `BUILT_ON_INVALID_ANCESTRY`
verdict holds byte-for-byte on the real tree. Green CI ≠ valid closure. The entire salvage is
operator-owned under the E47 governance hold. This is **not** an implementation defect — it is the
receipt-chain ceremony, which no agent may perform (§5).

> The two never conflate: **the code is built and connected; the closure is not; and the closure is
> not an agent's to grant.** Controlling result remains `DENIED_SAFE_HOLD`.

---

## 2 · Axis 1 — implementation + wiring, per milestone

| Group | Milestones / WP families | Implementation | Wiring |
|---|---|---|---|
| 1 | B00 · B00C (plan/bundles/ledger/DAG) | 11 COVERED · 1 PARTIAL (receipts) | 7 WIRED · 1 UNWIRED (receipt cadence — axis 2) |
| 2 | B01 · B01R · B02 (WP-B01C/B02C) | 10 COVERED | 5 WIRED (+ receipt-cadence UNWIRED = axis 2) |
| 3 | B03 · B04 (WP-B03C/B04C) | 15 COVERED | 5 WIRED · **2 e2e-walk orphans (F04, F12)** |
| 4 | B05 · B06 (WP-B05C/B06R) | 10 COVERED | 4 WIRED |
| 5 | B07 · B08 (WP-B07/B08) | 10 COVERED | 6 WIRED |
| 6 | B09 · B10 (WP-B09 + terminal) | 12 COVERED | 6 WIRED |
| 7 | end-to-end wiring spine | 15 COVERED | 7 WIRED · (receipt-chain = axis 2) |
| 8 | closure-validity / ancestry | — | see §5 |

**The wiring spine is genuinely connected**, traced open at path:line and each exercised by a real
e2e stage:
- **E01 ingress** (F01/F07 consume-validate) → **F02–F09 features** → **F10–F17 structures** →
  **lifecycle reducer** (stages 17–18).
- **four-plane substrate** (levers/health) → **candidate publisher** → the **mandatory atomic SHADOW
  fork** — `candidate_publisher.py:376-427` runs `ShadowLedger().transition(...)` **unconditionally
  before** the tradeability branch; both the published and the untradeable branch carry the shadow
  result; **no third path**. No candidate can exist without its shadow trace.
- **signed config → edge comparator → authority-fact verifier (+split-brain latch) → frozen legacy
  bridge → replay runner → READY_NO_AUTHORITY service** — replay delegates to the one live
  `DeterministicMachine` (two-run byte-identity proven); the verifier issues no lease.
- **6 read faces → ReadFaceEnvelope → 9 W25 views.**
- **27-stage e2e_audit walk** (0 SKIP) + the **14-command gate** (every tool ↔ `ci.yml` step names ↔
  the frozen runner's `REQUIRED_LOCAL_COMMANDS`) + the **build-ledger DAG**.

**The live money-line producer→consumer runtime is OUT_OF_REPO** by `BUILD_DARK_LIBRARY` / ownership
law (E07–E10, register A7) — lawful non-wiring, not an orphan.

---

## 3 · Invariant falsification pass (critic re-opened each; all HELD)

| Invariant | Evidence | Held |
|---|---|---|
| `DENIED_SAFE_HOLD` | `04_STATUS.md`; ORIGIN ceiling `READY_NO_AUTHORITY` (`service.py:96-112`); activation is E07+ (OUT_OF_REPO) | ✓ |
| `OFF/OFF/OFF/LIVE`, shadow immutable | `lever_law.BASELINE_MANIFEST` byte-exact; shadow enum no setter; `SHADOW_CAPTURE_OFF_FORBIDDEN` | ✓ |
| keyless `src/` | `verify_no_forbidden_capabilities.py` exit 0 + independent 0/464-file grep (no requests/socket/urllib/ccxt/api_key) | ✓ |
| F24 ban | `f24_absent=True count=24`; registry exactly F00..F23 | ✓ |
| 1648 join greening nothing | RC1 408 ⊂ RC3 1523 + RC4 125; `COVERED=0`; BLOCKED-beats-COVERED asserted (refuses a fabricated green) | ✓ |
| F13 half-open `[0,3)` | `excursion_reclaim_registry.py:170` `if ordinal >= horizon: RECLAIM_EXPIRED` | ✓ |
| lever 35/10/32 | runtime lens drift-locked to the vendored RC4 bundle | ✓ |
| atomic SHADOW fork | `candidate_publisher.py:376-427` unconditional pre-branch `ShadowLedger`; no third path | ✓ |
| replay = live transition | `replay_runner.run_replay` → `journal.replay` over the one `DeterministicMachine` | ✓ |
| lease verify-only | `authority_fact_verifier` issues nothing; `clear_split_brain` needs non-empty proof | ✓ |

**Clarification (faithful, not a leak):** NO TESTNET binds via the fixed OFF baseline +
`TESTNET_LIVE_BINDING_FORBIDDEN` / `DENIED_SAFE_HOLD`, **not** by refusing the `TESTNET` string —
`TESTNET` is a legal RC4 lever value in 4 of 10 valid combinations. This is RC4-faithful.

---

## 4 · The one in-repo defect — fixed this session

**Finding (group 3 + critic, the only actionable in-repo item):** two structure formulas were
**e2e_audit-walk orphans** — fully built and pytest-gate-covered, but exercised by **no** e2e walk
stage, violating the CLAUDE.md **E2E growth law** ("a capability with no walk stage is an incomplete
milestone"):

- **F04 `FractalPivot`** (`typed_level_registry.py:246`, GV-006, 10 tests) — absent from every e2e
  stage (grep `FractalPivot`/`GV-006` = 0).
- **F12 `OrderBlockRegistry`** (`order_block_registry.py`, 38 tests) — absent from the walk body, and
  `structure_flow_walk`'s stage-doc advertised "order block PENDING/CONFIRMED" that the body never
  drove (the grep hits were the doc string + F11 GV-010 comments).

**Fix (`tools/e2e_audit.py`):**
- Added an **F04 leg to `structures_walk`** — GV-006: highs `[8,9,12,11,10]`, left=2/right=2 → a single
  `pivot_high` `level_ticks=12` at the centre bar (seq 2), and the incomplete right window (`bars[:4]`)
  publishes nothing early.
- Added an **F12 leg to `structure_flow_walk`** (between displacement GV-010 and excursion/reclaim
  GV-011, where the doc already advertises it) — PAR-047 lookback 8 / PAR-160 H_bos 5: a LONG
  origin-search batch opens one `PENDING` block; a same-direction `LINKED_BOS` at exactly the 5th
  finalized bar after availability (bar 105) confirms it to `CONFIRMED`; a BOS at the 6th bar (106) is
  one bar past the horizon and never confirms. This makes the advertised stage-doc true.

**Verification:** all **27 e2e stages pass**, **14/14 gate commands exit 0**; no new coupling, no
invariant touched. Registered **E48**.

---

## 5 · Axis 2 — closure validity (operator-owned, unchanged)

**No milestone is validly closed** — every group converges on `NOT-VALIDLY-CLOSED` /
`BUILT_ON_INVALID_ANCESTRY`, confirming the package on the real tree:

- **Invalid ancestry holds:** the B07 receipt `build_commit = 2cebc139` = the package's observed
  `main` (B07 PR #24), and `git merge-base --is-ancestor 2cebc139 HEAD` = **true** — the branch
  inherits pre-B00R ancestry. Per E47 it "cannot become a valid B01C–B10 source merely by rebasing
  or showing green CI."
- **No authenticated receipt cadence exists anywhere:** all **11 on-disk receipts** (B00, B00C, R00,
  B01, B01R, B02..B07) are `triad.evidence_receipt.v2` shape, `result=PASS`, carrying **zero** cadence
  fields — no `subject_source_merge_sha`, no later authenticated `receipt_commit_sha`, no predecessor
  link. `validate_b_receipt --all --strict` attests **schema + chain-so-far**, and the CI "Receipt
  authentication" step runs that same validator — **no Ed25519/DSSE crypto**. This is the package's
  "green CI ≠ valid closure" exactly.
- **B08/B09/B10 are built on-branch but entirely unreceipted** (no receipt file of any kind; B10 is an
  unsigned `__OPERATOR_FILLS__` scaffold; no signed terminal tag; exit-0 structurally unreachable, so
  the honest terminal is exit-3 `BLOCKED_INCOMPLETE`).

Every closure residual maps to a register E-row / the ownership law / the operator salvage — **no
closure residual is an in-repo agent gap.**

### Ranked residuals

| # | Residual | Tag | Anchor |
|---|---|---|---|
| 1 | No authenticated receipt-chain cadence (no receipt carries subject/later-receipt/parent) | operator/estate | E47/E45 |
| 2 | Invalid ancestry: `2cebc139` is an ancestor of HEAD | operator/estate | E47/E29 |
| 3 | B08/B09/B10 built as branch commits with no receipt | operator | E45 cadence |
| 4 | R00 supersession `NOT_EXECUTED` (countersignature requested) | operator | R00 / E47 |
| 5 | Exit-0 fixed point unreachable → accept exit-3 or amend the runner | operator | E31 |
| 6 | Ed25519 signing + external trust registry + `DECISION-RECEIPT-PROFILE-001` pins (keys off-tree) | operator/estate | E32/E45 |
| 7 | Branch ruleset / issue #5 unconfigured | operator/estate | A4 |
| 8 | Ten per-milestone work-order MDs absent (runner self-test 62/63) | operator | E29 |
| 9 | **F04 + F12 e2e-walk orphans + false stage-doc** | **actionable-in-repo** | **FIXED — E48 (§4)** |
| 10 | B05 receipt future-dated (E24) + B06 evidence digest unbound (E28) | operator disposition | B10 |

---

## 6 · Overall verdict

**Implementation + wiring.** The code is genuinely built and connected, faithful to the reconciled
spec: 27/27 e2e stages, 14/14 gate commands, the combined DAG (1250 tasks, no cycles, one owner), and
300+ tests all green; every load-bearing safety claim held at real path:line evidence; the E01/F01/F07
consume-only ownership boundary and every blocking-parameter refusal (F06/F08/F17) are lawful
abstentions, not gaps. The sole in-repo actionable residual — the F04/F12 e2e-walk orphans — is now
closed (E48). Everything else non-wired (the live money-line runtime) is OUT_OF_REPO by ownership law.

**Closure validity.** Green CI is not valid closure, and no milestone is validly closed. The package's
`BUILT_ON_INVALID_ANCESTRY` verdict holds on the real tree; no authenticated receipt-chain cadence
exists; B08/B09/B10 carry the implementation but no receipt; R00 is unsealed; exit-0 is unreachable;
no signed terminal tag exists. The entire salvage is operator-owned under the E47 hold — a validated
B00R anchor first, then one milestone at a time cut from each predecessor's authenticated receipt
(reconciled plan §9.3). The controlling result is and remains `DENIED_SAFE_HOLD`.

---

*Read-only crosscheck, 9 agents, 0 errors. Machine evidence: `tools/e2e_audit.py` (27 stages),
`docs/control/{conformance_matrix,formula_catalog}.v1.json`, the 14-command gate outputs, the frozen
runner policy, `docs/plan/09_OPEN_QUESTIONS.md` (E-rows).*
