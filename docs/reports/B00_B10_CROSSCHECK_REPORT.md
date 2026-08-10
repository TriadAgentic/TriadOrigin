# TRIAD ORIGIN — B00→B10 crosscheck against master spec + checklist

**Scope:** every built milestone (B00, B00C, B01, B01R, B02, B03, B04, B05, B06, B07, B08, B09, B10)
crosschecked against `docs/plan/08_BUILD_CHECKLIST.md`, the reconciled master-plan set
(`docs/plan/00..10`), RC3 (`docs/control/rc3_effective_control_bundle.json`), RC4
(`docs/control/rc4_control_bundle.json`), the `CLAUDE.md` ownership law, and the frozen audit runner
(`audit_package/triad_origin_b01_b10_audit.py`, SHA `12c8896…`).
**Method:** read-only 8-agent crosscheck (7 milestone/invariant auditors + 1 completeness critic),
each verifying every checklist box **independently of whether the box is ticked** — a ticked box
whose artifact is absent/partial is a finding, not a pass.
**Working head:** `73b2549` on branch `b00-b07-review` (PR #26). **CI:** `test-and-verify` = success.

---

## 1 · Headline verdict

**The B00→B10 build is faithful to the master spec + reconciled checklist.** Across all six milestone
groups: **zero false ticks, zero in-repo build gaps.** Every load-bearing invariant verifies
mechanically at `73b2549`. Every DEFERRED / OUT_OF_REPO item resolves to a real register row
(`docs/plan/09_OPEN_QUESTIONS.md`) or a `CLAUDE.md` ownership law — **zero disguised gaps.** The
completeness critic falsified nothing.

The crosscheck surfaced **one true in-repo gap** — documentation-currency only — now **closed** in
this session (see §5). Everything else is fail-closed operator/estate ceremony under
`DENIED_SAFE_HOLD`, exactly as the ownership law requires.

---

## 2 · Per-milestone result

| Group | Milestones | Boxes/reqs | Result | False ticks | True gaps |
|---|---|---|---|---|---|
| 1 | B00 · B00C | 19 COVERED · 1 DEFERRED | Faithful | 0 | 0 |
| 2 | B01 · B01R · B02 | 28 COVERED · 2 OUT_OF_REPO · 1 DEFERRED | Faithful | 0 | 0 |
| 3 | B03 · B04 | 26 COVERED · 2 OUT_OF_REPO | Faithful | 0 | 0 |
| 4 | B05 · B06 | 38 COVERED | Faithful | 0 | 0 |
| 5 | B07 · B08 | 33 COVERED · 2 DEFERRED | Faithful | 0 | 0 |
| 6 | B09 · B10 | 22 COVERED · 6 DEFERRED | Faithful | 0 | 0 |
| 7 | invariants/counts/gate | 24 COVERED · 1 PARTIAL · 1 OUT_OF_REPO | Faithful | 0 | **1 (doc-currency)** |

### B00 / B00C — authority & corrective control closure
Combined-DAG validator and build-ledger `--verify` both pass (1250 tasks, 2383 hard edges, no cycles,
one owner each, source-authority preserved; 1250 reviewed rows, reviewer recorded + `--verify`-enforced).
B00/B00C/R00 receipts pass the semantic validator and bind their claimed commits
(`1217297…`/`b641edc…`/`241b301…`). The `test_b00c_control_closure` battery (32/32) exercises the
gate-PASS refusals, DAG refusal drills, F00–F23/no-F24, F01/F07 estate-lane, 35 aliases, 32 refusal
codes, 17 timings. **All four reconciled-plan P0 corrections are genuinely in code/config, not just
prose:** F24 removed (`f24_absent=True`, F00–F23 exactly); F01/F07 E01-owned (`e01_interface.py`
consume/validate-only + ledger schedules those rows in the ESTATE lane); four-plane-before-publisher
(B06 depends on the B05 receipt); F20 single-selected-policy
(`f20_missing_policy_denies`/`f20_activation_mode_removed`/`f20_rollout_absent_from_sizing`). The one
unchecked box (main ruleset / issue #5) is lawfully deferred to register **A4** (BLOCKED_EXTERNAL).

### B01 / B01R / B02 — contract/identity foundation + binding migration + kernel
105-row binding migration preserves source status verbatim (0 mismatches, source-bundle digest binds);
blocked bindings are structurally unconsumable; identity v2 byte-stable; epoch-equality/lower-rejects
law correct; contract immutability-by-version + producer-epoch fencing hold; B02 kernel (anchor
tail-falsification, checkpoint-v3 fence seal/restore, cold/warm parity, 17-bound RC4 timings
drift-lock) fully built + tested. Both hash-seed runs pass identically (472 tests); 27/27 e2e stages
green. The one unchecked box (B02 E01-ingress e2e stage) is realized in B03 `structures_walk`.

### B03 / B04 — F02–F09 features/structures + F10–F17 flow/lifecycle
Every formula module is a **pure deterministic transition** with golden-vector or repo-pinned tests;
the full `structures/` suite (359 tests) is green. **F13 half-open reclaim horizon `[0,3)`** confirmed
in code (`excursion_reclaim_registry.py:170` — `if ordinal >= horizon: RECLAIM_EXPIRED`, the B0R P0
fix). F01/F07 are genuinely consume-only validators (quarantine-shaped rejection, no publish/author
path — E01 ownership honored). The four honest-null subsets (F05 golden, F16 golden+age, F12 TTL, F10
invalidation-rule) are each registered as lawful deferrals (E11/E13/E15/E36-F10-1); the F10 box openly
states the invalidation binding is NOT delivered.

### B05 / B06 — four-plane substrate + reaction/capsules/candidates
Lever law drift-locks **exactly** to RC4: **35 aliases / 10 valid combinations / 32 refusal codes**.
Baseline `OFF/OFF/OFF/LIVE` with `shadow_activation` immutable LIVE holds. The B0R P0 refusals
(`DIRECT_ENVIRONMENT_TRANSITION_FORBIDDEN`, `LEGACY_LEVER_ALIAS_FORBIDDEN`,
`SHADOW_MONEY_CONTAMINATION`, `MIXED_ENVIRONMENT_BUNDLE_FORBIDDEN`) are all present + tested. PAPER is
keyless (source-scan proof); the semantic capsule registry binds 5 stable IDs by name/formula_refs
(every CAP01–05 ordinal refused — no guessed ordinal↔semantic mapping); the candidate publisher's
**mandatory atomic SHADOW fork** is a single nested `ShadowLedger` call in `_publish` — no candidate
can exist without its shadow trace. 475 scope tests pass.

### B07 / B08 — config/comparator/verifier/bridge/replay/service + read faces
B07 merged (`2cebc13` / PR #24) + receipted (gate reproduced on the merged SHA). Comparator is
side-effect-free (two independent axes, constant non-compared axis); authority ledger is verify-only
single-writer with a split-brain latch and **issues no lease**; legacy bridge emits control candidates
only; replay runner shares the live `DeterministicMachine` path; service ceiling is
`READY_NO_AUTHORITY`. B08's 6 read faces (LEV-0110..0115) + 9 W25 views + shared `ReadFaceEnvelope`
(honest `UNAVAILABLE`/`NOT_MEASURABLE`, two-timestamp W25 law) are built + verified; e2e stage 24
`read_faces_walk` green. B08's two process boxes (source PR merge / post-merge receipt) are honestly
unchecked — consistent with the unmerged branch, not false ticks.

### B09 / B10 — conformance/catalog/runbooks + audit/seal
The **1648-row conformance matrix** (`408⊂1523 + 125`) regenerates byte-identical and **greens
nothing** (`COVERED=0`, BLOCKED precedence structurally beats COVERED, `no_blocked_row_covered=True`);
no F24. The F20–F23 catalog is documentation-only (`IN_REPO_CATALOG`, GV-017..020, no executable money
logic, F20 RC4-corrected). 11 runbooks carry six sections + `OFF/OFF/OFF/LIVE` + `DENIED_SAFE_HOLD`;
**TESTNET is a refusal doc.** B10: two independent audits (Auditor 1 CLEAN; Auditor 2 two confirmed
P3s, both registered E43/E44 with a behaviour-neutral docstring narrowing); implementation report
separates built/verified/blocked/estate/operator; the exit-3 fixed-point analysis is grounded in the
actual frozen runner; the unsigned receipt scaffold is fully blank/honest; register rows E42–E45
present; agent-boxes ticked with operator-boxes left open.

### Cross-cutting invariants / counts / gate (all milestones)
Verified mechanically at `73b2549`: baseline `OFF/OFF/OFF/LIVE` (shadow non-switchable),
`activation_result=DENIED_SAFE_HOLD`, keyless `src/` (independent grep clean + capability check exit
0), F24 banned (registry exactly F00..F23), counts (`408⊂1523`, 125 RC4, 44 contracts, 9 effective
counts) reconcile via `verify_spec_control_counts --strict` + conformance invariants incl.
`no_blocked_row_covered=True`. Determinism enforced (two-seed collection md5-identical). The 14-command
frozen-runner gate is fully present and CI-wired with a 27-stage e2e growth walk.

---

## 3 · Invariant falsification pass (critic re-opened each; all held)

| Invariant | Evidence at `73b2549` | Held |
|---|---|---|
| `DENIED_SAFE_HOLD` | `rc3_effective_validation_report.json` `activation_result=DENIED_SAFE_HOLD`, `status=PASS_COMPOSITION_SAFE_HOLD` | ✓ |
| `OFF/OFF/OFF/LIVE` | `lever_law.py:101` `BASELINE_MANIFEST` byte-exact; `SHADOW_ACTIVATION_ENUM=('LIVE',)` (no setter) | ✓ |
| keyless `src/` | `verify_no_forbidden_capabilities.py` exit 0 ("no network, credential, or venue-order capability") | ✓ |
| F24 ban | `formula_catalog.v1.json f24_absent=True count=24`; `conformance_matrix no_f24=True`; `grep F24 src/` → none | ✓ |
| counts | `matrix_rows=1648 = 408⊂1523 + 125`; `{BLOCKED:297, COVERED:0, DEFERRED:848, OUT_OF_REPO:503}`; `no_blocked_row_covered=True` | ✓ |
| F13 half-open `[0,3)` | `excursion_reclaim_registry.py:170` `if ordinal >= horizon: RECLAIM_EXPIRED` | ✓ |
| lever drift-lock | `INVALID_ALIASES=35`, `VALID_COMBINATIONS=10`, `REFUSAL_CODES=32` = RC4 (refusals=32, timings=17) | ✓ |

**Benign provenance note (not a gap):** register E42 + `B10_IMPLEMENTATION_REPORT.md` state the B10
auditors ran at `fe8d106`, but the sealed head is `73b2549`. The `fe8d106..73b2549` diff is exactly
one commit — the B10 seal commit — touching only B10 docs + a **docstring-only** `lever_law.py` delta
(the E43 P3-1 narrowing, behaviour-neutral). The audited-head→sealed-head gap **is** the seal commit,
not a moving-head defect.

---

## 4 · Consolidated residuals — one ranked list (most-material first)

| # | Residual | Tag | Anchor |
|---|---|---|---|
| 1 | CLAUDE.md gate prose listed 11 of 14 frozen-runner commands | **actionable-in-repo** | **CLOSED this session** — E46 (§5) |
| 2 | B08/B09/B10 source-PR merge + post-merge receipts unshipped (chain ends at B07) | operator/estate | E42, E45.7 (A4-gated) |
| 3 | Full-PASS exit-0 structurally unreachable (self-referential check-evidence fixed point); exit-3 is the honest terminal | operator/estate | **E31** |
| 4 | Branch ruleset (issue #5) never configured; guarded-merge evidence only | operator/estate | **A4** |
| 5 | Pre-B07 receipt digests descriptive-only / B05 future-dated ts (sealed append-only) | operator/estate | **E24, E28** (mooted by DENIED_SAFE_HOLD) |
| 6 | Ten per-milestone work-order MDs absent from upload (runner self-test 62/63) | operator/estate | **E29, E32(5), E45.5** |
| 7 | 8 activation params NOT_RATIFIED (B1‑B8), 3 research (C1‑C3), 123-row PROPOSED bundle (D) — fail-closed | operator/estate | B/C/D rows, G7/G9 |
| 8 | P3-1 lever promotion-receipt honest-null subset; P3-2 scan_secrets pattern blind spots | operator/estate | **E43** (mooted) / **E44** (structural keylessness proven) |
| 9 | RC3 golden vectors F05/F16, F12 no-TTL, F10 invalidation-rule binding NOT delivered | operator/estate (research) | **E11, E13, E15, E36/F10-1** |
| 10 | DR RPO/RTO + DR-proof cadence `BLOCKING_OWNER_DECISION`; `09_B09` runbook MD absent | operator/estate | **E41** |
| 11 | ADR-005 unsigned; PAR-178 `CAP05` orphaned; legacy-bridge exact path; E01/divergence estate wiring | operator/estate | **A2/E20, E21, F2, F1‑F5** |
| 12 | Estate gate checklist G-1..G9 (all `[ ]`); LEV-0088 coverage as B08 read face | operator/estate | **E45, A6** / E36-CTL-9, E38(b) |

**Residual #1 is the only in-repo item; residuals #2–#12 are all fail-closed, register-anchored,
and reachable only through the operator's signed ceremony under `DENIED_SAFE_HOLD`.**

---

## 5 · The one in-repo gap — closed this session

**Finding (critic, group 7):** `CLAUDE.md` `## Required gate and PR law` enumerated only 11 of the 14
authoritative frozen-runner `REQUIRED_LOCAL_COMMANDS` — it omitted `validate_b_receipt.py --all
--strict`, `verify_spec_control_counts.py --strict`, `scan_secrets.py --tracked --fail-on-hit`. All
three already run in CI **and** in the frozen runner, so **no functional gate was ever missing** — the
defect was documentation-currency only.

**Fix:** the CLAUDE.md gate block now enumerates all **fourteen** commands + a currency-mirror note
that defers to the frozen runner + CI as the source of truth on any drift. Registered as **E46**.
Non-blocking; touches no invariant, no contract, no code path, and does not alter the
`DENIED_SAFE_HOLD` posture.

---

## 6 · What remains (all operator/estate ceremony, `DENIED_SAFE_HOLD`)

No agent may perform these; each is fail-closed and register-anchored (E45 is the full list):
1. **Accept the exit-3 terminal** (E31) or authorize a runner-amendment ceremony.
2. **Ed25519 key minting** (PRODUCER · COUNTERSIGNER · AUDITOR) + sign the B10 terminal receipt;
   close issue #5.
3. **Default-branch rulesets** (PR-required · ≥1 approving · conversation-resolution · stale-head
   rejection · required-checks strict) — A4.
4. The **signed offline GitHub DSSE snapshot** (two distinct signers).
5. The **ten per-milestone work-order MDs** deployed beside the runner (E29).
6. The **external trust registry** + ratified **DECISION-RECEIPT-PROFILE-001** (the two SHA pins).
7. The **B08→B10 seal**: merge each source PR green → reproduce the gate against merged `main` → land
   each detached signed terminal receipt → tag + local checkpoint.
8. **All G-1..G9 estate gates** — activation stays `DENIED_SAFE_HOLD` until every one exists.

---

## 7 · Build ledger (this marathon)

| Milestone | Commit | Gate | CI |
|---|---|---|---|
| B0R (B00–B07 review/reimplementation) | `f9c42ad` | 14/14 exit 0 | green |
| B08 (read faces + evidence projections) | `64d1170` | 14/14 exit 0 | green |
| B09 (conformance / catalog / runbooks) | `fe8d106` | 14/14 exit 0 | green |
| B10 (audits + terminal seal) | `73b2549` | 14/14 exit 0 | green |
| E46 (crosscheck gate-prose reconcile) | *this commit* | 14/14 exit 0 | pending |

All independently gate-verified (not self-reported) before push, on `b00-b07-review` / PR #26.

*Report generated by the B00→B10 crosscheck workflow (8 agents, 0 errors). Authoritative machine
evidence: `docs/control/{conformance_matrix,formula_catalog}.v1.json`, `tools/*` gate outputs,
`docs/plan/09_OPEN_QUESTIONS.md` (E-rows), the frozen runner policy.*
