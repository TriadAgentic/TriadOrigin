# TRIAD ORIGIN — REPAIR REPORT (2026-08-13)

Scope: TriadOrigin (E02, structure detection ONLY). READ-ONLY audit; no source file was
edited. Evidence is anchored to `file:line` and named tests. Where a test was run, the exact
command was `env -u PYTHONPATH TZ=UTC /home/user/TriadOrigin/.venv/bin/python -m pytest …`.

---

## 1 · Authoritative document set and supersession chain

Four authoritative repair documents govern this audit, plus two prior disposition inputs:

1. `docs/repair/TRIAD_ORIGIN_V7_GAP_REGISTER_2026-08-13.md` — the 50-gap register.
2. `docs/repair/TRIAD_REPAIR_WORK_ORDER_2026-08-13.md` — the work-order bodies (WO-A … WO-J).
3. `docs/repair/TRIAD_REVISION_RECORD_R-01_2026-08-13.md` — the R-01 revision record.
4. `docs/repair/TRIAD_MASTER_SEQUENCE_2026-08-13.md` — the governing sequence + estate law §0.
   Prior disposition inputs: `docs/repair/GAP-CROSSCHECK-2026-08-13.md`,
   `docs/plan/DECISIONS-REQUIRED.md`.

**Supersession chain (what is now standing, what is retired):**

- **ERR-02 / GAP-12 / WO-H are WITHDRAWN** per R-01 (reviewer error). The F13 code is correct.
  Evidence: `TRIAD_REVISION_RECORD_R-01_2026-08-13.md:14-62,115,226` ("developer's reading is
  correct"); GAP-12 withdrawn at `:204`. WO-H identifier retired; body retained with a banner.
- **The prior EXECUTION ORDER is superseded by the Master Sequence.** The Master Sequence §1.2
  ownership map + §1.3 register are now the controlling routing of Origin work
  (`TRIAD_MASTER_SEQUENCE_2026-08-13.md:151-193`).
- **LAW-9 is now standing law** (Master Sequence §0.2/§0.3): a change that alters the EMITTED
  BYTES of a formula, or flips a currently-passing test, is an AMENDMENT (owner signature +
  prior spec-amendment PR), NOT an agent repair — however obviously correct it appears. The
  discriminator is BYTES, not correctness. LAW-5 (§1.5 version discipline) rides with it: a
  repaired formula ships under a NEW semantic version; the old version is retired with a banner,
  bytes preserved, never edited in place.

---

## 2 · Origin-scope disposition table (every finding)

Verdict legend: CLOSED · WITHDRAWN · OWNER_GATED · BUILDABLE · OUT_OF_ORIGIN · ON_BOX ·
CHECK_ONLY · STANDING_LAW.

| Item | Verdict | One-line evidence |
|---|---|---|
| WO-G / ERR-01 / GAP-11 (F10 FVG mutually-exclusive states) | CLOSED | `fvg_registry_v3.py:485` `_state_for`; `test_fvg_registry_v3.py:1317` `TestErr01MutuallyExclusiveStates` (spec-text amendment still needs owner D-21, out of agent scope). |
| WO-H / ERR-02 / GAP-12 (F13 RECLAIM_PENDING extreme accrual) | WITHDRAWN | Reviewer error; F13 v2 faithful — `excursion_reclaim_v2.py:532-536,669,712`; pinned by passing `test_hold_bars_do_not_deepen_the_extreme` (`test_excursion_reclaim_v2.py:589`). |
| §1.5 optional test `test_reset_bar_low_is_not_applied_to_extreme` | NEEDS_ATTENTION (not agent-addable as written) | As specified it asserts "extreme UNCHANGED at t"; the machine DEEPENS on the reset bar (`excursion_reclaim_v2.py:712`) and passing T9 (`test_excursion_reclaim_v2.py:567-579`) already pins `extreme==9960` = the reset bar's own low. See §4. |
| WO-I / ERR-03 / GAP-13 (F12 confirm on GENERIC_BREAK vs F08) | OWNER_GATED (D-17) | Agent MUST NOT pick A/B/C; honest note in `order_block_v2.py`; SYNC-4 irreversible. `TRIAD_REVISION_RECORD_R-01_2026-08-13.md:112-116`. |
| WO-C (Origin half) — F18 emits exact unreduced RR pair regardless of floor | VERIFIED_OK / CHECK_ONLY | `candidate_geometry.py:302-307,292-300`; goldens `test_candidate_geometry.py:57-70,72-80,216-224,227-250`; 32 passed. See §5. |
| WO-J / GAP-06 (RPI coverage on flow atoms F15/F16/F17) | OWNER_GATED_AMENDMENT (+ new version) | Adds mandatory `book_completeness` + new F15 refusal → changed emitted bytes of F15/F16/F17; flips 16 frozen-dataclass constructor sites. See §3. |
| GAP-50 / WO-D task D2 (capsules.py ↔ RC2 ordinal mapping) | OWNER_GATED (D-22) | `capsules.py:106,117-159,186` correctly refuses the ordinal alias; a signed mapping is a semantic-owner act ("do not guess a single row"). |
| GAP-04 / GAP-46 (RR floor 2.0 vs 2.5 / derive-at-admission) | OWNER_GATED (D-11) + OUT_OF_ORIGIN | The floor decision is L3/E07 + owner; deleting F18's ratified PAR-061 floor would be a LAW-9 amendment. |
| WO-D comparator run (ORIGIN_CANDIDATE stream vs RC2) | ON_BOX | Comparator BUILT-IN-ORIGIN; running it is an on-box/L2 action; Origin only supplies the candidate stream (`GAP-CROSSCHECK-2026-08-13.md:164-167`). |
| GAP-01..05, 07..10, 14..49; CHK-01..08; Tier-H GAP-38/39 | OUT_OF_ORIGIN | Economic hole, venue drift, execution mechanics, estate debt, measurement plumbing, governance closure — barred from E02 by RC3 law 07 + repo `CLAUDE.md` (no cost model / admission gate / order verb / risk auth / venue client / fill parser / money publisher / lease issuer). |
| LAW-9 byte-change tripwire | STANDING_LAW | Fires on WO-J only; ERR-02/WO-H (WITHDRAWN), WO-C (check-only STOP guard), WO-I (owner-gated) are LAW-9-clean. |

**Completeness answer:** No genuinely-E02, agent-buildable-without-owner-signature item was
missed. The set {ERR-01/WO-G CLOSED, §1.5 optional test, WO-C F18 check, WO-J per-verdict} is
complete; everything else Origin-scope is CLOSED, WITHDRAWN, OWNER_GATED, CHECK_ONLY, ON_BOX,
OUT_OF_ORIGIN, or a standing-law record.

---

## 3 · WO-J verdict (exact)

**Verdict: OWNER_GATED_AMENDMENT.** `byte_change = true`. `flips_passing_test = true`.
LAW-9 classification: **AMENDMENT (owner signature + prior spec-amendment PR), NOT an agent
repair** — and, being a new emission generation, a **new version under LAW-5**.

Evidence:

- WO-J instruction — add `book_completeness ∈ {COMPLETE, RPI_EXCLUDED}` to every flow atom and
  fetch `GET /fapi/v1/rpiDepth` / `<symbol>@rpiDepth@500ms` (`TRIAD_REPAIR_WORK_ORDER_2026-08-13.md:1288`).
- `book_completeness` / `RPI` / `rpiDepth` / maker-fill appear in NO source file — grep over
  `src/` returns zero matches (docs only). It is a NET-NEW mandatory field.
- F15/F16/F17 FEATURE atom emit dicts have no such key: `flow_atoms_v2.py:519-534` (F15),
  `:708-717,731-741` (F16), `:935-945` (F17). Adding a mandatory key changes emitted bytes of
  all three.
- Input dataclasses are frozen with NO defaults (`flow_atoms_v2.py:256-273,277-289,544-561,
  751-765`); a mandatory no-default field turns 16 constructor call sites into TypeErrors
  (`test_f10_f17_goldens_b04c.py` 12 sites; `test_flow_atoms_v2.py` 4 sites).
- The new F15 refusal `COVERAGE_UNVERIFIABLE_RPI` replaces the current coverage/FEATURE emit on
  the RPI-excluded case (current reason codes `flow_atoms_v2.py:121-126`, emission `:505-512`) →
  new emitted bytes on that case.
- Baseline currently GREEN: `test_f10_f17_goldens_b04c.py test_flow_atoms_v2.py → 74 passed`.
  GV-F16-01 (`test_ofi_is_plus_seven`, `test_f10_f17_goldens_b04c.py:206-214`) stays byte-identical
  because WO-J touches completeness/coverage, not the OFI equation — but that single golden guards
  only F16's number, leaving the envelope field-add and the F15 coverage change unguarded (the same
  blind spot ERR-02 exercised).

**Faithful next step (NOT "done"):** STOP — do not implement WO-J as an in-place agent edit of
`flow_atoms_v2.py` or the v2 contract. It must be routed as an owner-signed spec-amendment PR, and
when ratified built under LAW-5 as new atom versions (`flow.tfi.window.v3` / `flow.ofi.best.v3` /
`flow.book_tilt.band.v3`, a new `flow_atoms_v3.py` + v3 contract carrying `book_completeness` and
the new F15 refusal), retiring the v2 identities with a `RETIRED_DEFECTIVE{ref=WO-J/GAP-06}` banner,
v2 bytes preserved. Scope fence — these are OUT_OF_ORIGIN and must NOT be built in TriadOrigin: the
`GET /fapi/v1/rpiDepth` / `@rpiDepth@500ms` fetch (venue client, forbidden by `CLAUDE.md`), the
authoring of the `book_completeness` fact (an E01/feed input — Origin consumes/validates only,
`GAP-CROSSCHECK-2026-08-13.md:65`), and "forbid exact maker-fill claims" (E09/E10 — Origin has no
fill parser). An enum drift is also flagged for the same amendment: the work order lists
`{COMPLETE, RPI_EXCLUDED}` (`:1288`) while the Master Sequence STEP 1 lists a third `UNKNOWN`.

---

## 4 · §1.5 optional-test result

**Result: the R-01 §1.5 test as specified is NOT agent-addable.** `byte_change = false` (adding a
test file changes no formula bytes) but `flips_passing_test = true` (the specified assertion
collides with a passing test).

- R-01 §1.5 (`TRIAD_REVISION_RECORD_R-01_2026-08-13.md:66,73-84`, premise `:35`) asserts "bar t's
  low is never applied to the extreme" on the reset bar; the proposed
  `test_reset_bar_low_is_not_applied_to_extreme` asserts "extreme UNCHANGED at t".
- The machine DEEPENS on the reset bar: a RECLAIM_PENDING bar whose close fails the hold returns
  to EXCURSION and applies its own low (`excursion_reclaim_v2.py:712`; docstring
  `:48-54`). Passing T9 (`test_excursion_reclaim_v2.py:567-579`) already pins
  `atom.extreme_ticks == 9960` = the reset bar t2's own low.
- The §1.5 assertion is therefore FALSE against the machine; added verbatim it lands RED, and the
  only way to green it is to delete the reset-bar deepen at `:712`, which flips T9 and changes the
  emitted `extreme_ticks`/`excursion_depth_ticks` bytes — a LAW-9 AMENDMENT.

**Faithful disposition:** file a documentation erratum against R-01 §1.5/§1.2b (the reset bar IS an
excursion-phase bar; its own low IS applied at t). Any fresh clarifying test must codify the ACTUAL
behaviour (the opposite assertion, consistent with T9) and is largely redundant with T9 — so the
higher-value action is the erratum, not a new test. R-01's self-classification of its §1.5 proposal
as a "byte-neutral agent repair" is incorrect for the test as written; escalate to owner.

---

## 5 · WO-C F18 result

**Result: VERIFIED_OK (check-only).** `byte_change = false`, `flips_passing_test = false`.

- F18 emits reward/risk as an exact integer rational pair. On admit it is UNREDUCED
  (`candidate_geometry.py:302-307`: `rr_numerator=reward_ticks`, `rr_denominator=risk_ticks`).
- The ratified PAR-061 floor (`2/1`, injected declared parameter `:88-90,222-226`) gates ONLY the
  `admitted` verdict and the mirror rr fields, not geometry emission. A below-floor candidate
  ABSTAINS (`ABSTAIN_GEOMETRY_BELOW_FLOOR`, `:292-300`) while still emitting `risk_ticks` and
  `reward_ticks`, so a downstream E07 consumer can re-derive RR against any floor.
- Goldens lock it: `test_candidate_geometry.py:57-70` (`rr==4/2`, unreduced), `:72-80`
  (below-floor preserves `risk_ticks==2`, `reward_ticks==3`), `:216-224` (never simplified to 2/1),
  `:227-250` (mirror preserved). Test run: `test_candidate_geometry.py → 32 passed`.

**Faithful disposition:** No change. Do NOT add or remove an RR floor in F18 (Master Sequence §1.2
STOP; that authority is E07/owner D-11), do NOT edit PAR-061. Any reviewer-comfort assertion would
be additive/byte-neutral and is already covered by `test_one_tick_below_floor_abstains`.

---

## 6 · Scope wall and the R-01 reroute

TriadOrigin is **E02 (structure detection) ONLY**. RC3 law 07 and the repo `CLAUDE.md` forbid
Origin from holding a cost model, economic-admission gate, order verb, risk/quantity authorization,
venue client, fill parser, money publisher, or lease issuer — those belong to E07/E08/E09/E10. By
construction roughly **40 of the 50 register gaps are out of Origin** (GAP-01..05, 07..10, 14..49,
all CHK-01..08, Tier-H GAP-38/39).

Per R-01 §5 (`TRIAD_REVISION_RECORD_R-01_2026-08-13.md:180-194`) the bottleneck has moved off
Origin: the Origin queue is WO-J (owner-gated amendment, per §3), WO-I (owner-gated D-17), and WO-C
(check-only, satisfied). **Do not manufacture Origin work** to fill the idle L4 lane — an idle
correct lane is a finished lane (Master Sequence §1.2 / phase-3 "idle — do not fill").

---

## 6b · The cross-repo lead: WO-A (TriadLearning) + the BTC/BCH investigation

R-01 §5 / Master Sequence Track 2 make **WO-A the lead economics work order** — and it is
measurement-only with no entry gate, so it started while the Origin lane sat idle-correct. WO-A owns
no structure detection and therefore is **not** an Origin item; it is homed in **TriadLearning**
(`analysis/wo_a/`, branch `claude/scorecard-origin-validation-mboymp`, pushed):

- A0.1–A0.4 + A1 + A2 + A3 **`SELECT`-only** queries; a pure stdlib arithmetic module
  (`wo_a_arithmetic.py`) whose `true_opportunity_WR` is proven against the work order's own reference
  table (0 %→26.4, 35 %→42.7, 50 %→49.6, 65 %→56.6) by `tests/wo_a/` (31 tests green); an on-box
  runner that reuses `databank_resolver.bars_1m` + first-touch for the A1 market-at-signal
  counterfactual and writes `RECONCILIATION-2026-08-13.md`.
- **Honest on-box boundary:** the bank/tape are on the Mac, so off-box every on-box number is a NAMED
  `ON_BOX_PENDING` refusal — never fabricated. **WO-B is NOT built** (it amends RC3 law 14 and is
  gated on the SYNC-2 `no_fill_win_share` go/no-go the runner produces). The amended A0 stop rule is
  wired: within-resolver disagreement STOPs (exit 2) + escalates the minimum subset to DTBNK;
  cross-resolver disagreement is informational (first_touch canonical).

The separate operator ask — *"why is the estate only trading BTC and BCH?"* — is answered by
`docs/repair/INVESTIGATION-BTC-BCH-2026-08-13.md` (read-only, six-lane funnel audit). **No code path
selects exactly {BTC, BCH}**; feed/universe narrowing is RULED OUT (fail-closed to the full 30) and
the config-precision `PENDING_VENUE_SNAPSHOT` allowlist hypothesis is RULED OUT (VGP owns precision
from live `exchangeInfo`). The extreme collapse is best explained by the intersection, at ~$100
equity, of the VGP `min_notional_after_rounding` × the owner-margin-capped notional and the
scan_gate `$25k` depth floor. Fastest on-box confirmation:
`SELECT * FROM shadow.v_symbol_gate_aggregate ORDER BY instrument_id;`. Both are measurement/audit —
they arm, narrow, and edit nothing; posture stays OFF/OFF/OFF/LIVE.

---

## 6c · Revision Record R-02 cross-check (2026-08-13)

R-02 is a fifth document that cross-checks §3/§4 of this report + the BTC/BCH investigation. Verified
against the code, it **validates this repo's work on every count** and adds four items:

| R-02 item | Verified disposition |
|---|---|
| **§1 · R-01 §1.5 WITHDRAWN** (2nd reviewer error, opposite direction) | ✅ The reset bar DOES deepen (`excursion_reclaim_v2.py` rule-3 `_deepen`; `test_h10` `extreme==9960`). The withdrawn `test_reset_bar_low_is_not_applied_to_extreme` was **never added**; the replacement `_applied_` test is present + green. Verified by grep + the passing suite. |
| **§1.2 · LAW-9 step 2 strengthened** | ✅ RECORDED (DECISIONS-REQUIRED §II·G): read the code + name the pinning test file:line before writing a finding. |
| **§2 · WO-J = OWNER_GATED_AMENDMENT** | ✅ Accepted. `book_completeness`/`RPI` verified **zero matches in `src/`** (net-new); `flow_atoms_v2.py` has 5 frozen dataclasses (the 16-constructor-site claim). Enum corrected to `{COMPLETE, RPI_EXCLUDED, UNKNOWN}`. **WO-J-a deferred into the amendment PR** (a strict-xfail needs the not-yet-existing field to fail honestly; the placeholder body would XPASS-break the gate — a LAW-9-step-2 catch). |
| **§3 · GAP-51 symbol-selection confound** (NEW, P0) | ✅ Built in TriadLearning WO-A **A5** (`a5_per_symbol_baseline.sql` + `sample_size.py`). The binomial table is reproduced exactly (n=30→0.0809, n=60→0.0176, n=128→0.00066; 93 round trips two-sided). SYNC-2 amended (both-condition gate + the `n<93` not-distinguishable rule). |

No F13 byte changed; no owner signature/receipt fabricated; posture `OFF/OFF/OFF/LIVE`.

---

## 7 · Attestation boundary (LAW-8)

Four claims are kept separate and none is conflated:

1. **Repo presence** — the source and tests named above exist in `/home/user/TriadOrigin` at the
   cited lines (verified by Read/Grep).
2. **Green local test** — the pytest runs quoted (`test_candidate_geometry.py → 32 passed`;
   `test_f10_f17_goldens_b04c.py test_flow_atoms_v2.py → 74 passed`;
   `test_excursion_reclaim_v2.py` reset/hold cases + the new byte-neutral clarifying test
   `test_reset_bar_low_is_applied_to_the_extreme_err02_r01_corrected` → all green) were run locally
   under `env -u PYTHONPATH TZ=UTC .venv/bin/python -m pytest`. A green local test is not a merged PR.
   (Cross-repo: TriadLearning `tests/wo_a/` → 31 passed under `pytest`.)
3. **Merged PR** — none is claimed by this report; WO-J's amendment PR does not exist.
4. **Running deployment** — none is claimed. WO-D comparator running and any CAP-01 emission are
   ON_BOX actions outside this repo.

Estate posture is invariant **OFF/OFF/OFF/LIVE** (venue OFF / venue-activation OFF / paper OFF /
shadow LIVE). No owner signature, no trust-registry pin, no credential, and no receipt was
fabricated or presumed. This report is an audit record; it arms nothing and merges nothing.

---

## 8 · R-03 cross-check (2026-08-13) — three findings, one self-correction, one reviewer answer

`TRIAD_REVISION_RECORD_R-03_2026-08-13` is vendored in `docs/repair/`; the full per-item
disposition is `docs/plan/DECISIONS-REQUIRED.md` §II·G. What the cross-check itself established,
because two of R-03's own claims were marked inference in its §8 attestation:

**§2 / M-1 — confirmed, and stronger than inferred.** R-03 deduced from `mergeable_state=unstable`
that the combined check is not required, and asked for the branch-protection settings to be read
directly. Read: `TriadLearning main` is **`protected: false`** — there is no branch protection at
all, not merely a non-required check. And the estate is ASYMMETRIC: `TriadOrigin main` reads
`protected: true` (with `b00r-ruleset-canary` also `true` — the internal control showing a ruleset
in this org does set the flag). The repo under `DENIED_SAFE_HOLD` is protected; the repo carrying
the live measurement code is not. `WO-P` escalates accordingly.

**§3 / M-2 — confirmed and worse.** The 281 ruff findings are exact, and `mypy` fails
independently with 42 errors in 5 files — two independently red steps, so the prescribed lint-only
baseline would have left the check exactly as uninformative. The remedy was built covering both
(`TriadLearning tools/lint_ratchet.py`), and two claims in R-03 §3 are corrected: the cited
"estate's OWN existing CI-ratchet law … already applied to the param census" does not exist as
described, and the baseline cannot honestly be wired into CI from this container because it was
generated with tool versions `uv.lock` does not pin for the runner.

**§3 / M-2, sharpened by a live CI read.** Watching PR #463's own run closed the last of it. `ci.yml`
orders the steps ruff → mypy → pytest → PII-lint, and a GitHub Actions job stops at its first
non-zero step — so for as long as the 281 findings have existed, **`Mypy`, `Pytest` and the
build-rejecting `PII-lint` have not executed at all.** The check named
`lint · typecheck · test · conformance` has been running the first quarter of its own name. That is
a stronger claim than R-03's: the conformance, golden round-trip and PII evidence the check appears
to supply is not weak, it is absent. (Corroboration for the frozen baseline: the runner's own locked
ruff prints `Found 281 errors` — the exact frozen total. The count is version-agreed; the per-file
distribution is not, so the `PROVISIONAL_LOCAL_VERSIONS` stamp stands.)

**§5 — accepted, repaired, and returned with an erratum.** The miscalibration is real and was
repaired under LAW-9 agent authority by passing the observation rather than adding a formula
(`min_n_for_power` was already R-03's exact expression — a second derivation would have created
the estate's own re-deriver drift class). Zero tests flipped. The erratum: R-03's §5 table rows for
30/35/38 % are `round()` of values its own `ceil()` formula puts higher, and its `0.84` power-z is
less precise than the module's `0.8416`; the shipped bars are the conservative ones, and a
required-sample bar is never rounded down.

**§6 — answered with evidence for the D-7 reviewer, verdict left to the reviewer.** 58 of the 137
pinned paths are not admitted by the gen-2 SOURCE grant, but the merge introduced **zero** of them
(parents 133 + 120, merge 137 = exactly the union, merge-only empty, all 58 already in parentA), so
no D-3b widening is forced by the conflict resolution. Pinning and granting are structurally
disjoint here: the grant is a pure positive allowlist with no exclusion rules, and
`verify_source_hashes` asserts only grant ⊆ pinned.

**M-4 (new, from this cross-check).** The gen-2 grant admits 4 `docs/plan/` and 2 `docs/repair/`
paths, so the classifier returns False for the decision register, the repair README, this report and
every vendored revision record — **every repair-record commit trips `SOURCE_PATH_OUT_OF_SCOPE` by
construction.** Recorded for D-3b's widening rather than worked around.

**M-5 (new, and the first concrete cost of M-2).** Because CI has never reached pytest, the full
TriadLearning suite was run locally against both the branch and `origin/main`, each with the estate
siblings visible so the sibling-or-skip tests actually execute. It immediately surfaced a live
`CG-REFUSAL-CODES` violation: `TriadVenueGateway` added `RejectClass.MAINTENANCE` (commit `8c7d667`,
Binance −1016) **without moving its coupled §2b glossary row**, the obligation VGP's own `CLAUDE.md`
states verbatim. It had been invisible twice over — the drift-lock is sibling-or-skip, so it SKIPS
wherever the sibling is absent, and where it does run CI never got past ruff. A drift-lock that
skips in CI and never executes locally is not a lock. Repaired in TriadLearning (row + `KIND` +
`ORIGIN` + `STATUS` + both regenerated faces), display-only, registration point untouched. The
like-for-like comparison: `origin/main` 102 failed / 2,278 passed; the branch 101 failed / 2,325
passed; **zero regressions, one pre-existing failure fixed.**

**§4 / M-3 — the checkpoint seal stays owed and owner-gated.** Performing it unbid would contradict
the very call R-03 §1 recorded as correct.

Nothing in this section arms, merges, widens, or signs anything. Posture unchanged
**OFF/OFF/OFF/LIVE** · `DENIED_SAFE_HOLD`.

---

## 9 · On-box implementation report cross-check (2026-08-13)

`ONBOX-IMPLEMENTATION-REPORT-2026-08-13.md` is vendored byte-identically in `docs/repair/`. It is
the first report in this programme produced from REAL data on the real box, and it is largely
right — the A0 diagnosis in particular is a genuinely good catch. Five findings.

**B-1 · The A0 diagnosis is CORRECT and the same defect existed in the repo copy — now repaired.**
The box keyed A0 on `decision_id` alone, flagged 1,102 conflicts, investigated, and found the flag
wrong: a decision carries one row per COHORT and a cohort is a different execution scenario. That
reasoning is exactly right and the bank agrees structurally (`cohort text NOT NULL DEFAULT
'TRIAD-A'` under a UNIQUE index on `(decision_id, cohort, opened_at)`). The repo copy had the right
DOCTRINE (cross-X expected, within-X a stop) but keyed it on a `resolve_note`-derived proxy and
never read `cohort` — so two cohorts that both resolve first-touch collapsed into one bucket and
read as one model answering twice: the SAME false stop, arriving by a different route, and
UNTESTED (zero tests exercised that `.sql`). Repaired: the stop is now
`(decision_id, cohort, resolver_id)`, both cross-classes are informational, and five tests drive
the real query against an in-memory bank — including the on-box false alarm replayed, and a proof
the narrowed gate still fires.

**B-2 · The two harnesses are a FORK, and the box copy is about to collide.** §2.1 is factually
right that `analysis/wo_a/` was absent at head `bd00107` — that commit is the PARENT of the #462
merge (`135a270`), so the guide described the branch while the box held the pre-merge tree. But the
response was to build a SECOND implementation, and the two now differ in both directions: the box
has the cohort fix (now also here), the repo has the R-03 §5 observation-parameterized bar and the
A5 per-symbol reconciliation the box run does not. `analysis/wo_a/` is now tracked on `main`, so
the next `git pull` on the box meets a modified/untracked collision. **The box copy should be moved
aside and the repo copy pulled — not merged by hand.** Two implementations of one measurement is
the estate's own re-deriver drift class, on the harness axis.

**B-3 · The two halves of §2.3's table have COMPLETELY different evidential status, and §2.4 reads
them as one.** Applying the R-03 §5 corrected bar (`n_required(0.544, observed)`) to the box's own
numbers:

| population | n | observed WR | n_required | verdict |
|---|---:|---:|---:|---|
| Gate ACCEPTED | 47 | 42.55 % | **139** | `HOLD_NOT_DISTINGUISHABLE` (34 % of the bar) |
| TRUE OPPORTUNITY | 317,806 | 31.68 % | 37 | `DISTINGUISHABLE` |

So the true-opportunity finding is rock solid — the opportunity pool genuinely wins far less than
the frozen 54.4 % baseline, on 8,600× the required sample. The accepted number is not evidence yet
and needs roughly 3× more data. §2.4's caveat ("47 rows is far too small") is right and now has a
number. **And the sign is the other way:** accepted 42.55 % is ABOVE the pool's 31.68 %, so at the
gate the judge is selecting FAVOURABLY, not adversely — the opposite of what §2.4's framing
suggests, though at n=47 that direction is not established either. `P(observe ≤ 42.55 % | true
54.4 %, n=47) = 0.038` — an unlikely single observation, not a finding.

**B-4 · §4's "single highest-value open question" is ANSWERED, and the answer is a ratified design
decision.** The report finds zero shorts in the census, concludes the suppressor is "upstream of
the gateway", and recommends hunting it as priority #1. It is not a bug. The **LIVE30-PROFITABLE-ONLY
settlement (2026-08-06)** makes the money lane exactly `bos_choch LONG ∪ order_block LONG`; all M1
and all SHORT are shadow-only by ratified design. Verified in code at both planes: Engine
`runtime.rs::is_money_live_candidate` requires `direction == "long"` before a candidate reaches
`CANDIDATES_TOPIC`, and Intelligence `run_gateway._LIVE_JUDGED_DIRECTIONS = ("long",)`. The report's
own evidence supports this — `matrix_off = 0` and the shadow lane carrying 30,357 shorts is the
settlement working, not a leak. **Recommendation #1 would send someone hunting a bug that does not
exist.** The `side_weight` 0.5→1.0 parity note is a real but separate lever (emission SCORING, not
lane admission). What IS worth reading: 27 symbols, not 30.

**B-5 · Two arithmetic/consistency notes.** §3 states "2,029 recorded decisions" and then a verdict
mix summing to 4,000 (`skip` 3,725 + `take` 272 + `wait` 3) — two different windows or a
transcription slip; the latency percentiles need to say which population they came from. The p99
landing exactly on 12,000 ms is correctly read as a timeout cap. Separately, `defer_ttl_dropped`
26,725 vs `decisions_published` 8,229 is the report's strongest operational finding and its
recommendation #2 stands on its own evidence.

**What the report gets right and should be said plainly:** it refused to fabricate a judge benchmark
when the timeout could not be beaten and measured real production latency instead; it caught its own
A0 bug rather than shipping the STOP; it left O-1/O-2 untouched; and it independently reached the
CO-10 conclusion that the two MCP tokens are EXPOSED and need rotation. Those are the right instincts.

Nothing in this section arms, merges, widens, or signs anything. Posture unchanged
**OFF/OFF/OFF/LIVE** · `DENIED_SAFE_HOLD`.

---

*Prepared as a READ-ONLY audit. Every disposition above resolves to CLOSED / WITHDRAWN /
OWNER_GATED / CHECK_ONLY / ON_BOX / OUT_OF_ORIGIN / STANDING_LAW; the only genuinely-open Origin
disposition, WO-J, is an owner-gated amendment, not an agent repair.*
