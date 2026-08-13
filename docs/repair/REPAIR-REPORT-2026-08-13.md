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

*Prepared as a READ-ONLY audit. Every disposition above resolves to CLOSED / WITHDRAWN /
OWNER_GATED / CHECK_ONLY / ON_BOX / OUT_OF_ORIGIN / STANDING_LAW; the only genuinely-open Origin
disposition, WO-J, is an owner-gated amendment, not an agent repair.*
