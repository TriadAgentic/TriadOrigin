# IMPLEMENTATION REPORT — R-03 + the on-box report (2026-08-13)

**For:** the account owner (leesbak@gmail.com).
**Covers:** the `TRIAD_REVISION_RECORD_R-03_2026-08-13` cross-check and repairs, the cross-check of
`ONBOX-IMPLEMENTATION-REPORT-2026-08-13`, and the independent Codex review of TriadLearning PR #463.
**Disposition:** `MEASUREMENT / NO_RUNTIME_CHANGE / NOT_A_RATIFICATION`.

Everything below is **measurement-plane and DARK**. No contract byte, no `MANIFEST.sha256`, no
estate `VERSION`, no arming flag, no money-path reach, no venue/key/credential touched. TriadOrigin
posture is invariant throughout: **`OFF/OFF/OFF/LIVE` · `DENIED_SAFE_HOLD`**.

**Landed:** TriadLearning `main` **`577c906`** (PR #463, squash) · TriadOrigin branch
`claude/scorecard-origin-validation-mboymp` **`01897a2`** (PR #36 still draft, still correctly
unmerged).

---

## 0 · One page

| | |
|---|---|
| **Shipped** | The A5 distinguishability bar is now computed from the observed rate, not fixed at 93 · a lint/type ratchet that restores signal to a permanently-red CI check · the owed §2b `maintenance` glossary row · the WO-A A0 stop rule keyed on the real scenario identity · two Codex findings closed and two verified |
| **Biggest correction to the box report** | "Where do shorts die" is **not an open question** — it is the ratified LIVE30-PROFITABLE-ONLY settlement, verified in code at two planes. Its recommendation #1 would hunt a bug that does not exist |
| **Biggest new finding** | The CI check named `lint · typecheck · test · conformance` has been running **the first quarter of its own name**. Mypy, pytest and the PII-lint have not executed on any branch for as long as the 281-finding debt has existed |
| **Biggest open decision** | **B-6** — WO-A's canonical population is undeclared, and it *sets* the SYNC-2 verdict that releases WO-B. 47 accepted rows vs A5's 317,806, on opposite sides of the corrected bar |
| **Regressions** | Zero. Full suite on merged `main`: 101 failed / 2,333 passed, against 102 / 2,278 before — one pre-existing failure fixed, +55 passing |

---

## 1 · R-03 §5 — the A5 bar is computed, not constant

### The finding (R-03's own self-correction of its R-02 §3.2)

`n = 93` is the sample size required to distinguish the frozen **54.4 %** baseline **from 40 %**. It
is the right bar only if the live rate happens to be 40 %. It is not a general bar:

| observed live WR | `n_required` vs the 54.4 % baseline |
|---:|---:|
| 30 % | 32 |
| 40 % | 93 |
| **45 %** | **221** |
| 50 % | 1,009 |

So a frozen 93 **releases a SYNC-2 verdict on ~42 % of the required evidence at 45 %**, and holds on
already-adequate evidence at 30 % — it fails in both directions, and it fails hardest exactly where
the live and frozen rates are close, which is the case that matters.

### The repair

Passed the **observation**, rather than adding a formula:

- `n_required(p_frozen, p_observed)` — returns `inf` for a degenerate observation (0, 1, or equal to
  the baseline) instead of raising or fabricating a finite bar.
- `distinguishability(n_total, observed_wr)` — one of three named states
  `INSUFFICIENT_SAMPLE_REGARDLESS` / `HOLD_NOT_DISTINGUISHABLE` / `DISTINGUISHABLE`, **plus the bar
  it was judged against**.
- `run_wo_a.py` prints both `n_total` and `n_required`; the SYNC-2 HOLD branch cites the
  observation-derived bar; the A5 SQL comment and the README were rewritten off the constant.

**No second re-deriver was created.** `min_n_for_power` was *already* R-03's exact expression, so
`n_required` delegates to it. A parallel derivation would have manufactured this estate's own
recurring drift class — §9b's "membership, not equality"; the third and fifth `gross_rr_floor`
copies; the two-registries-that-don't-intersect F1 lesson.

**Zero tests flipped** (LAW-9 clean). `min_n_for_power`, `is_distinguishable` and
`N_FOR_54_4_VS_40 = 93` are untouched, so all eleven original `test_sample_size.py` tests pass
verbatim. 22 tests added, including the falsifying one:

> at `n = 100` and 45 % observed, the old gate says releasable (`is_distinguishable(100) → True`)
> and the new gate says **HOLD** against a bar of 221.

### Erratum returned to the reviewer

R-03's own §5 table computes its 30/35/38 % rows with `round()` while its stated formula says
`ceil()` (31.12 → 31, 50.37 → 50, 71.21 → 71), and its `0.84` power-z is less precise than the
module's `0.8416`. The module is **higher at every disagreement** and the conservative numbers
shipped — a required-sample bar is never rounded down. Recorded in the module docstring rather than
silently reconciled.

---

## 2 · R-03 §2 / M-1 — confirmed by direct read, and stronger than inferred

R-03 §8 marked this an inference from `mergeable_state` semantics and asked for the branch-protection
settings to be read directly. Read:

| repo | `main` |
|---|---|
| **TriadLearning** | **`protected: false`** |
| TriadOrigin | `protected: true` (with `b00r-ruleset-canary` also `true` — the internal control proving a ruleset in this org does set the flag) |

Not merely "the combined check is not required" — **there is no branch protection at all.** And the
estate is **asymmetric**: the repo under `DENIED_SAFE_HOLD` is protected; the repo carrying the live
measurement code is not.

R-03's disposition stands (no action against the merge itself). **`WO-P` escalates:** until the
ruleset is installed, "gates green" and "merged to main" have no causal link. The install is an
owner/GitHub-admin act; an agent can neither perform nor fake it.

---

## 3 · R-03 §3 / M-2 — confirmed, remedied, and worse than reported

### 3.1 Confirmed, with two corrections upstream

The 281 ruff findings are exact. Two corrections:

1. **`mypy` fails independently** with 42 errors in 5 files. R-03 prescribed a *lint-only* baseline,
   which would have left the combined check **exactly as uninformative as it found it** — two
   independently red steps, one frozen.
2. **The cited precedent does not exist.** R-03 refers to "the estate's OWN existing CI-ratchet law
   … already applied to the param census". Verified: `census.py` / `test_param_census.py` assert
   classification and units, **not** a never-increase count ratchet. This is a **new** discipline,
   not a re-application of an old one, and is documented as such.

### 3.2 The sharpening — the check runs a quarter of its own name

Watching PR #463's own CI closed the last of it. `ci.yml` orders its steps
**ruff → mypy → pytest → PII-lint**, and a GitHub Actions job aborts at its first non-zero step.
Job `94499973501` ends with:

```
Found 281 errors.
##[error]Process completed with exit code 1.
```

— no mypy output, no pytest output, no PII-lint output.

**For as long as the 281 findings have existed, `Mypy`, `Pytest` (unit + golden conformance +
round-trip) and the build-rejecting `PII-lint` have not executed at all.** The check named
`lint · typecheck · test · conformance` has been running the first quarter of its own name. This is a
stronger claim than R-03's: the conformance, golden round-trip and PII evidence the check *appears*
to supply is not weak — it is **absent**.

Combined with M-1, the honest statement is that TriadLearning has had **neither an enforced merge
gate nor an executed test gate**.

### 3.3 The remedy

`tools/lint_ratchet.py` freezes the debt, fails only on **new** findings, and can never let the
frozen count grow. Three laws, each a test:

| law | why |
|---|---|
| **Both tools or neither** | a ruff-only baseline leaves the combined check as uninformative as before |
| **Fail closed on version skew** | a baseline is only meaningful against the version that produced it; a differing running version is a named `VERSION_SKEW` refusal, never a comparison across versions |
| **Never fabricate a clean read** | a missing tool, empty output, unparseable output, or a mypy run whose `Found N errors` exceeds what could be attributed is a **refusal**, not zero findings |

**This is not a linter relaxation.** The 21 ruff findings in my own new files were fixed in the code
(wrapped lines, renamed a shadowing `l`), not silenced with a per-file-ignore. Baselining
pre-existing debt behind a never-increase ratchet is the opposite move from relaxing a rule so new
code can pass — the distinction R-03 §1 recorded as load-bearing.

### 3.4 Deliberately NOT wired into CI

The baseline is stamped `PROVISIONAL_LOCAL_VERSIONS`: generated with **ruff 0.15.8 / mypy 1.19.1**,
while `uv.lock` pins **ruff 0.15.21 / mypy 2.2.0** for the runner. A baseline claiming agreement with
a version nobody ran is a fabricated receipt.

Corroboration worth having: the runner's own locked ruff prints exactly **`Found 281 errors`** —
the count is version-agreed. The per-file / per-code **distribution** the ratchet actually compares
is not yet verified across versions, which is precisely why the stamp stands.

**Operator step:** `python tools/lint_ratchet.py --write-baseline --status AUTHORITATIVE_RUNNER`
on the runner, then swap the `ci.yml` lint step. And restoring the signal is not enforcing it — that
is `WO-P` (§2).

---

## 4 · R-03 §4 / M-3 — the checkpoint seal stays owed

Acknowledged, **not performed**. Sealing means creating a `checkpoint/<date>-<name>` branch at fresh
`main` across five repositories. R-03 §1 records my earlier refusal to do it unbid as *correct*;
doing it now unbid would contradict that record. The agent-executable half (the branch + its
`CHECKPOINTS.md` row) is ready on request; the annotated-tag mirror is an operator step (the App
token cannot push tags).

---

## 5 · R-03 §6 — the reviewer's scope check, answered with evidence

Computed with the classifier's own predicate over `governance.parse_source_hashes`:

- **58 of the 137** pinned paths are not admitted by the gen-2 SOURCE grant (35 are
  `verify_source_hashes.REQUIRED_MEMBERSHIP` entries; 23 are pins outside both).
- **The merge introduced ZERO of them.** parentA(`8254043`) = 133 pins, parentB(`661923b`) = 120,
  merge = 137 = **exactly the union**, merge-only set = `[]`, and all 58 out-of-grant pins were
  already in parentA.

So the pin file attests to no scope it did not already attest to before the merge, and **no D-3b
widening is forced by the conflict resolution.** Structurally, pinning and granting are disjoint
here: the grant is a pure positive allowlist with no exclusion rules (so R-03's premise that it
"deliberately EXCLUDES the formula paths" is a paths-not-listed condition, not an exclusion clause),
and `verify_source_hashes` asserts only *grant ⊆ pinned* — its exit 0 is evidence for the disjoint
reading, never for *pinned ⊆ grant*. **The verdict remains the D-7 reviewer's.**

---

## 6 · M-4 (new) — the grant is narrower than the programme's own evidence surface

`classify_milestone_pr.source_path_allowed` returns **False** for `docs/plan/DECISIONS-REQUIRED.md`,
`docs/repair/README.md`, `docs/repair/REPAIR-REPORT-*.md`, every vendored revision record — and for
this file. The grant admits only 4 `docs/plan/` and 2 `docs/repair/` paths, so **every repair-record
commit trips `SOURCE_PATH_OUT_OF_SCOPE` at the CI classify step by construction.**

Not a reason to stop recording the programme; it is the observation that the grant and the
programme's evidence surface disagree. Recorded for **D-3b**'s widening, not worked around.

---

## 7 · M-5 (new) — a live coupling violation, caught by the run CI never performs

Because §3.2 established pytest has never executed in CI, the suite was run by hand. It immediately
surfaced a real `CG-REFUSAL-CODES` violation:

`TriadVenueGateway` added `RejectClass.MAINTENANCE = "maintenance"` (commit `8c7d667`, the A-010
typed venue-error subclasses; Binance −1016 "system busy / undergoing maintenance") **without moving
its coupled §2b glossary row** — the obligation VGP's own `CLAUDE.md` states verbatim: *"A change to
`RejectClass` moves with the glossary row in the same PR-set."*

**Invisible twice over.** The drift-lock `test_vgp_reject_classes_are_fully_explained` is
sibling-or-skip, so it **skips** wherever `TriadVenueGateway` is not checked out beside
`TriadLearning`; and where it *does* run — the estate dev layout — CI never got past ruff.
**A drift-lock that skips in CI and never executes locally is not a lock.** M-5 is the first concrete
cost of M-2, not a coincidence.

**Repaired** (display-only): the plain-words row + `KIND` (`health` — the venue is not answering, not
refusing) + `ORIGIN` (`venue`) + `STATUS`, with both generated faces regenerated via
`tools/refusal_glossary.py --write-doc`. The words carry the one operationally load-bearing fact:
`maintenance` is deliberately **not** in VGP's `_VENUE_WIDE` set (only `auth`/`margin` are), because
an outage clears on its own and a latched venue-wide halt would outlive it — an operator reading the
glossary should not reach for the halt. §2b: the glossary can never gate or filter; the registration
point stays singular at the VGP source.

---

## 8 · The on-box report cross-check (B-1 … B-5)

`ONBOX-IMPLEMENTATION-REPORT-2026-08-13.md` is vendored byte-identically in `docs/repair/`. It is the
first report in this programme produced from **real data on the real box**, and it is largely right.

### B-1 · The A0 diagnosis is CORRECT — and the same defect was in the repo copy

The box keyed A0 on `decision_id` alone, flagged **1,102 conflicts**, and — instead of shipping the
STOP — investigated and found the flag wrong. A `decision_id` carries **one row per COHORT**, and a
cohort is a different **execution scenario** replayed against the same signal (TRIAD-A is the
production lane; P-AMP-AT-SIG, P-LADDER-MKT, P-CHASE-1T, VR-BASE … are counterfactual personas). One
decision resolving `win` under an amplified entry and `loss` under a laddered one is the **entire
point** of a counterfactual bank. The bank agrees structurally:
`cohort text NOT NULL DEFAULT 'TRIAD-A'` under a UNIQUE index on `(decision_id, cohort, opened_at)`.

**The repo harness had the same defect, by a different route.** `a0_3_fill_disagreement.sql` carried
the right *doctrine* (cross-X expected, within-X a stop) but keyed it on a `resolve_note`-derived
`resolver_id` and **never read `cohort`** — even though the sibling census `a0_2_census.sql` already
groups by it. Two rows for different cohorts that happen to resolve the same way (both first-touch)
collapsed into one bucket and read as *"the same model answered twice"*: a **false stop** that halts
A1/A4 on correct data. The doctrine was right; the **key was a proxy for the identity instead of the
identity**.

**Repaired:**

```
STOP = (decision_id, cohort, resolver_id) with > 1 distinct outcome
INFO = cross-COHORT   disagreement   (different execution scenarios)
INFO = cross-RESOLVER disagreement   (different entry models)
```

**Narrow is not vacuous.** Having just written a ratchet about gates that always return the same
answer, the obvious risk in narrowing a gate is that it can no longer fire — a test proves it does.

**Proven by execution, not by reading.** Zero tests exercised that `.sql` before (only a static
SELECT-only scan), so neither the old bug nor the new fix was observable in CI. Five tests now drive
the real query against an in-memory bank: the on-box false alarm replayed · the same
decision+cohort+resolver answering twice · cross-resolver within one cohort still informational · a
`no_fill` beside a terminal outcome is not a disagreement · and a drift-lock that the query reads the
real `cohort` column.

### B-2 · The two harnesses are a FORK, and the box copy is about to collide

§2.1 is factually right that `analysis/wo_a/` was absent at head `bd00107` — that commit is the
**parent** of the #462 merge (`135a270`), so the guide described the branch while the box held the
pre-merge tree. But the response was to build a **second implementation**, and the two now differ in
both directions:

| | box copy | repo copy |
|---|---|---|
| A0 cohort fix | yes | yes (as of `577c906`) |
| R-03 §5 observation bar | no | yes |
| A5 per-symbol reconciliation | no | yes |
| Named A1 resolver divergences | no | yes |

`analysis/wo_a/` is now tracked on `main`, so the next `git pull` on the box meets a
modified/untracked collision. **Move the box copy aside and pull the repo copy — do not hand-merge.**
Two implementations of one measurement is the estate's own re-deriver drift class, on the harness
axis.

### B-3 · The two halves of §2.3's table have completely different evidential status

Applying the R-03 §5 corrected bar to the box's own numbers:

| population | n | observed WR | `n_required` | verdict |
|---|---:|---:|---:|---|
| Gate ACCEPTED | 47 | 42.55 % | **139** | `HOLD_NOT_DISTINGUISHABLE` — 34 % of the bar |
| Gate DECLINED | 316,447 | 31.55 % | 36 | `DISTINGUISHABLE` |
| **TRUE OPPORTUNITY** | 317,806 | 31.68 % | 37 | `DISTINGUISHABLE` — 8,600× the bar |

The true-opportunity finding is **solid**: the opportunity pool genuinely wins far less than the
frozen 54.4 % baseline. The accepted number is **not evidence yet** and needs roughly 3× more data.
§2.4's caveat ("47 rows is far too small") is right and now has a number.

**And the sign is the other way.** Accepted 42.55 % is **above** the pool's 31.68 %, so at the gate
the judge is selecting **favourably**, not adversely — the opposite of what §2.4's framing suggests,
though at n = 47 that direction is not established either.
`P(observe ≤ 42.55 % | true 54.4 %, n = 47) = 0.038` — an unlikely single observation, not a finding.

### B-4 · §4's "single highest-value open question" is ANSWERED — it is a ratified design decision

The report finds zero shorts in the gateway census, concludes the suppressor is "upstream of the
gateway", and makes hunting it **recommendation #1**. It is not a bug.

The **LIVE30-PROFITABLE-ONLY settlement (2026-08-06)** makes the money lane exactly
`bos_choch LONG ∪ order_block LONG`; **all M1 and all SHORT are shadow-only by ratified design.**
Verified in code at both planes:

- Engine `runtime.rs::is_money_live_candidate` — requires `direction == "long"` before a candidate
  reaches `CANDIDATES_TOPIC`.
- Intelligence `run_gateway._LIVE_JUDGED_DIRECTIONS = ("long",)`.

The report's own evidence supports this: `matrix_off = 0` and the shadow lane carrying 30,357 shorts
over the same window is the settlement **working**, not a leak. **Recommendation #1 would send
someone hunting a bug that does not exist.**

The `side_weight` 0.5 → 1.0 parity note is a real but separate lever (emission **scoring**, not lane
admission). What *is* worth reading from that census: **27 symbols, not 30**.

Recommendation **#2** — `defer_ttl_dropped` 26,725 against `decisions_published` 8,229, roughly three
candidates expiring per decision published — is the report's strongest operational finding and stands
entirely on its own evidence.

### B-5 · Two consistency notes

- §3 states "**2,029** recorded decisions" and then a verdict mix summing to **4,000**
  (`skip` 3,725 + `take` 272 + `wait` 3) — two different windows or a transcription slip; the latency
  percentiles need to name which population they came from.
- The p99 landing exactly on 12,000 ms is **correctly** read as a timeout cap being hit, not a
  natural tail.

### What the report gets right, said plainly

It refused to fabricate a judge benchmark when the timeout could not be beaten, and measured **real
production latency** instead. It caught its **own** A0 bug rather than shipping the STOP. It left
O-1/O-2 untouched. And it independently reached the CO-10 conclusion that the two MCP tokens are
**EXPOSED and need rotation**. Those are the right instincts.

---

## 9 · The independent Codex review of PR #463

Five findings against files this branch touches. Each was checked **against the code**, not accepted
or dismissed.

### P2 (mypy abnormal exit) — CLOSED, and it was a real hole in the module's own stated law

`collect_mypy` refused an unparseable run **only** when mypy printed a `Found N errors` summary that
disagreed with the parse. A config error, plugin crash or usage failure exits **non-zero and prints
text with no summary at all**: the regex found nothing, `parsed == 0`, no refusal fired, and `{}` was
returned. `compare` then reads that as the **entire baseline burned down** and prints a **passing**
ratchet — from a run that measured nothing. That is precisely the fabricated clean read the module's
third law forbids, so the law was true of the docstring and not of the code.

Now a non-zero exit with no findings summary is `MYPY_ABNORMAL_EXIT`, quoting the first lines it saw.
Three tests, including the one that matters: a genuine `Success: no issues found` at rc=0 is still
accepted, so the fix cannot turn a clean tree into a refusal.

### P1-1 / P1-2 — VERIFIED CORRECT, and the docstring was making a FALSE CLAIM

`_first_touch_win` said it mirrored `databank_resolver.resolve_pending` **"exactly"**. It does not.
Read at `databank_resolver.py:552-566`:

- The resolver calls `tape.first_touch` for TP and SL **separately** and compares **print
  timestamps** (`tp_hit[0] < sl_hit[0]`), so stop-first pessimism applies **only to an exact tie**.
- It expires an open trade at `filled_us + max(4h, 2 × hold_s)` (`_EXIT_TIMEOUT_FLOOR_US`), not at a
  fixed window.

This replay reduces a minute to OHLC extremes, so within a bar it **cannot recover print order** and
resolves adverse-first **always**; and it scans a fixed 24 h with no `hold_s` read.

**Direction matters:** a minute where TP printed at :10 and SL at :50 is a **WIN** to the resolver and
a **LOSS** here — so `no_fill_win_share` computed from bars is a **LOWER BOUND, biased AGAINST the
entry mechanism WO-B exists to test.**

Closing it properly means replaying the print tape through `tape.first_touch`, which is a **redesign**
of this replay, not a tweak, and would flip the pinned
`test_same_bar_touches_both_resolves_stop_first` — LAW-9-shaped. So the honest half shipped instead:
the docstring states **both** divergences plainly, and `_a1_no_fill_win_share` now **counts** the
ambiguous bars (`same_bar_ambiguous`) and stamps the horizon it actually used (`exit_horizon`), so the
bias **travels with the number** rather than being absorbed into it. Additive — no verdict changes, no
tests flipped.

### P1-3 / P1-4 — RECORDED as **B-6**, not silently changed

See §10.

---

## 10 · B-6 (new, open) — the WO-A canonical population is an undeclared owner decision

Codex is very likely right, and the cohort axis confirms it:

- **A1/A2 replay and aggregate EVERY cohort.** Personas are cloned per decision and use different
  entry rules, so A4 reconciles duplicated, heterogeneous resolver populations rather than the
  declared canonical first-touch resting-entry population.
- **A5 counts resolved shadow outcomes with no gate-accepted/live constraint and no frozen-baseline
  timestamp boundary**, so both `n_total` and `observed_wr` can be inflated or blended by non-live,
  duplicated history.

The size of the question is already visible in two numbers on the table: **the on-box run measured 47
gate-accepted resolved rows while A5's population is 317,806** — and under the R-03 §5 corrected bar
those sit on **opposite sides of distinguishability** (47 against a required 139; 317,806 against a
required 37).

**Choosing the canonical cohort/class predicate therefore SETS the SYNC-2 verdict that releases
WO-B.** That makes it a declared decision with the cohort semantics named — not an agent's mid-PR
adjustment. Recorded in `docs/plan/DECISIONS-REQUIRED.md` as **B-6**.

---

## 11 · Verification

### Full suite — run locally, because CI cannot reach pytest

Both runs performed in a checkout with the estate siblings visible, so the sibling-or-skip tests
actually execute:

| tree | failed | passed | skipped | collection errors |
|---|---:|---:|---:|---:|
| `main` before (`135a270`) | 102 | 2,278 | 21 | 47 |
| `main` after (`577c906`) | **101** | **2,333** | 21 | 47 |

- **Regressions: none.** The branch-only failure set is **empty**.
- **Fixed: 1** — `test_refusal_glossary.py::test_vgp_reject_classes_are_fully_explained`.
- The 47 collection errors are this container missing `jsonschema` (46) and `duckdb` (1) — an
  environment gap, identical on both sides, **not** a code fault.
- The 101 remaining failures are pre-existing on `main` and untouched by this work.

### Targeted suites

| suite | result |
|---|---|
| `tests/wo_a/` | **74 passed** (33 sample-size incl. 22 new · 5 new A0.3 fixture tests · 4 R-03 source drift-locks) |
| `tests/tools/test_lint_ratchet.py` | **23 passed** (incl. an end-to-end planted-`F401` proof and the three abnormal-exit cases) |
| `tests/test_refusal_glossary.py` | **10 passed** (1 was failing on `main`) |
| `tools/lint_ratchet.py` on merged `main` | ruff **281 → 281**, mypy **42 → 42** — zero new static-analysis findings |

### TriadOrigin gates

`tests/plan/test_no_overclaim.py` + `tests/test_b00c_control_closure.py` — **36 passed**.
ORIGIN-F linter — 10 findings, **all pre-existing** in `00_MASTER_PLAN.md` / `09_OPEN_QUESTIONS.md`,
none from this work. Earlier in the round the full 12-gate suite ran green (pytest seed 0 + seed 1 ·
`collect_test_ids` · `verify_manifest` · `validate_contract_manifest` · `verify_source_hashes`
137 pins / 114 required · `verify_reproducible_build` · `test_wheel_install` ·
`verify_no_forbidden_capabilities` · `validate_combined_dag` · `build_ledger --verify` ·
`e2e_audit` 30/30).

---

## 12 · Commit ledger

### TriadLearning — merged to `main` as `577c906`

| commit | what |
|---|---|
| `8493abc` | R-03 §5 observation-parameterized A5 bar + the lint/type ratchet (M-2) |
| `4c26ad5` | ancestry merge of `origin/main` (squash-merge add/add resolution; resolved tree == branch head, proven byte-identical) |
| `23787b8` | §2b — the owed `maintenance` glossary row + both regenerated faces (M-5) |
| `a004e6c` | WO-A A0 stop rule keyed on `(decision_id, cohort, resolver_id)` + 5 fixture tests (B-1) |
| `da775b7` | Codex P2 mypy abnormal-exit closed; the A1 replay's two real divergences named + measured |

### TriadOrigin — branch `claude/scorecard-origin-validation-mboymp`, head `01897a2`

| commit | what |
|---|---|
| `52fa58d` | R-03 vendored + M-1/M-2/M-3 recorded + M-4 opened + D-23 |
| `a5299c7` | M-2 sharpened — the CI check never reached mypy, pytest or PII-lint |
| `02979c4` | M-5 recorded — the live `CG-REFUSAL-CODES` violation |
| `77c922d` | on-box report vendored byte-identically + cross-check §9 (B-1 … B-5) + README row |
| `01897a2` | B-6 recorded — the WO-A canonical population |

---

## 13 · Still owner-gated

| item | why it is yours |
|---|---|
| **B-6** — declare the WO-A canonical population | It *sets* the SYNC-2 verdict; two numbers currently sit on opposite sides of the bar |
| **WO-P** — install the no-bypass `main` ruleset | `TriadLearning main` is `protected: false`; with §3.2 that means neither an enforced merge gate nor an executed test gate |
| **M-3** — the estate checkpoint seal | Five repositories; R-03 §1 recorded the refusal to do it unbid as correct |
| Regenerate the lint baseline **on the runner** | `--write-baseline --status AUTHORITATIVE_RUNNER`, then swap the `ci.yml` lint step |
| **Rotate both MCP tokens** | Still exposed at the issuing side. The on-box report reached the same conclusion independently. Neither token has been used, echoed, or stored by me |
| **D-23** — ratify the A5 minimum-sample floor (`n_floor`, proposed 30) | A `PROPOSED_MUST_RATIFY` value; the module refuses to treat it as ratified |
| **D-3b** — widen the gen-2 SOURCE grant | M-4: every repair-record commit is out-of-scope by construction |
| **PR #36** | Still draft, still correctly unmerged — B00R root closure (D-3), the GOV-01 signature (D-1), independent review (D-7), the CO-06 semantic closures (D-8/D-9) |

The A1 replay redesign (print-tape `first_touch` + the `max(4h, 2 × hold_s)` horizon) is **named and
measured**, not silently carried: it would flip a pinned test, so it is LAW-9-shaped and rides B-6.

---

*Prepared 2026-08-13. Nothing in this report arms, widens, or signs anything. No owner signature,
trust-registry pin, credential value, or on-box receipt was fabricated at any point; where the only
lawful next step is the owner's, it is named above and refused in place. Posture unchanged:*
**`OFF/OFF/OFF/LIVE` · `DENIED_SAFE_HOLD`.**
