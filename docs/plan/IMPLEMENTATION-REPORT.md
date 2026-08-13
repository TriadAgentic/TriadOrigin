# TRIAD-ORIGIN-V7 Formula Repair + Change Orders — Implementation Report (DRAFT)

Branch: `claude/scorecard-origin-validation-mboymp` · PR #36 (draft, owner-gated) ·
Posture held invariant throughout: **OFF/OFF/OFF/LIVE · DENIED_SAFE_HOLD**.

Honest boundary held: no owner Ed25519 signature, external trust-registry pin, credential value,
or on-box receipt was ever fabricated. Where the only lawful next step is the owner's, the code
refuses loudly and names the refusal (typed `BLOCKED_ON_RATIFY` / `AUTHORITY_OPEN` /
`EDGE_UNRESOLVED_PRESERVED` / `PENDING_SIGNATURE`) — never a guess.

## Formula Repair milestones (all landed, dual-seed gate-green)
- **B02C** — R-F00 `instrument_math.v2` (value-integrality) + Part C security (C.1 SealedBundle v2
  real Ed25519, C.2 `--authority`, C.3 `evaluate(caps,env,state)` entrypoint law + fail-closed
  static gate `verify_formula_entrypoints.py`). v1 retired in place with `RETIRED_DEFECTIVE` banner.
- **B03C** — R-F03 (swing/DC v2, ambiguous-bar ABSTAIN_EXTEND_WINS), R-F04 (BOTH_EMIT erratum),
  R-F09 (break v2, b>=1), GV-F05.
- **B04C** — R-F13→F10→F12→F11→F14→F15→F16→F17 on repaired v2 surfaces (excursion_reclaim_v2,
  fvg_registry_v3, order_block_v2, displacement in-place, reaction_v2, flow_atoms_v2). GV-013 unit
  pair (+2/5 vs +1/13 unit-bug trap) + GV-F16-01 (OFI +7, normalized identity never emits lever-OFF).
- **B06R** — R-F19 clustering_v2 (ordering-law permutation invariance) + F14→F19 exact-digest
  source_reaction_id adoption + §E.0 F18 fail-closed geometry posture.

Each milestone: a closure-named golden home under `tests/formulas/`, an `e2e_audit.py` walk stage
(29 stages total), and the §1.5 version discipline (new `_vN` module; v1 retired, bytes preserved).

## Part D + Part E
- Part D registry record: `docs/control/formula_repair_overlay.v1.json` (8 golden ops + 13-formula
  version map), a separate non-arming artifact (never mutates RC3/RC4 bytes, CO-01 stop rule).
- Part E docs: the owner-gated record set (fail-closed / PENDING_SIGNATURE).

## Change Orders (agent-executable set — landed)
- **CO-01** RC5 effective-consolidation compiler (10/10 supersessions, typed ops, byte-stable;
  never mutates RC3/RC4). Artifacts: `rc5_effective_consolidation.py` + `rc5_bundle.json` +
  `rc5_manifest.json` + `rc5_conflict_report.json` + `rc5_bundle.schema.json`.
- **CO-02** milestone registry + crosswalk. **CO-03** four union majors + transport_bindings +
  venue_execution_plan + E03–E06 ratification-required stubs.
- **CO-05** ledger review-v2 rebinding (full-bytes + 1250 per-row digests; a stale review is
  impossible). `build_ledger.py --verify` prints v1 + v2 lines.
- **CO-07** binding-adjudication worksheet generator + emitted worksheets/completeness matrix
  (every disposition a PROPOSAL, every owner signature slot EMPTY).
- **CO-08** preimage ledger. **CO-10/12/13/14** owner-gated / on-box records (fail-closed).
- **CO-11** `ORIGIN-F##` namespace rule + report-only linter.
- **CO-06** verification-linkage repair overlay (`linkage_repair_overlay.v1.json` +
  `gen_linkage_repair.py`): 408 RC1 dispositions (182 composite gates materialized, 391
  task-resolved, 17 EDGE_UNRESOLVED_PRESERVED); zero effective dangling refs; B09 base **1,648**
  reproduced without the blind-summation 2,056; read-only over frozen masters; e2e stage
  `co06_linkage_repair`. The 17 SEM rows (RC3-LINK-BLOCK-002) are honestly NOT guessed — they
  await a semantic owner's signed selection (D-8).
- **CO-09** status/checklist truth generation: typed presence states + a real embedded provider-head
  block (run-id AUTHORITY_OPEN offline, never fabricated) + a hand-edit fails CI + no "passed"
  attaches to a presence-only fact. Regenerated against the branch head (reachable).

## Owner-gated / on-box (delivered as documents, never faked)
- `docs/plan/DECISIONS-REQUIRED.md` — D-1..D-7, D-3b (signatures, ratifications, B00R root closure,
  OWNER-TOPO-01, CO-13, CO-11, independent review, SOURCE-grant widening).
- `docs/plan/ONBOX-GUIDE.md` — O-1 (CO-10 credential rotation), O-2 (CO-12 salvage), O-3 (B00R
  closure ceremony).

## Independent cross-check closure (ERRATA + DECISIONSREQUIREDv2.0, 2026-08-13)
Owner-forwarded independent audit ("the answer for the decisions you required"). Cross-checked
clause-by-clause; posture unchanged `OFF/OFF/OFF/LIVE`, `DENIED_SAFE_HOLD`; no signature/pin/
credential/receipt fabricated.
- **ERR-01 (F10) — CLOSED in code + test.** The module already implements the RATIFIED T4
  mutually-exclusive state reading; added the required property test
  (`test_fvg_registry_v3.TestErr01MutuallyExclusiveStates` — 10⁵ random pens → exactly one state
  predicate true, `_state_for` agrees) + a precise docstring. Not a new law (spec-text adoption is
  D-21's signature).
- **ERR-02 (F13) — WITHDRAWN by R-01 (2026-08-13) as reviewer error; code correct all along.** The
  later Revision Record R-01 formally withdraws ERR-02 / GAP-12 / WO-H: the F13 module DOES update
  the excursion extreme (rule 3 reset-branch applies the reset bar's own low — `extreme==9960` in
  `test_h10`; `extreme = min over excursion-phase bar lows`), the reviewer's premise was wrong, and
  this repo's refusal to edit a passing formula is validated. `WO-H` is retired. The
  `excursion_reclaim_v2.py` docstring records the withdrawal and a **byte-neutral clarifying test**
  (`test_reset_bar_low_is_applied_to_the_extreme_err02_r01_corrected`) pins the correct behaviour —
  no emitted byte changed. R-01 elevates this refusal discipline to standing **LAW-9**.
- **ERR-03 / D-17 (F12) — RECORDED OWNER-GATED; behaviour UNCHANGED.** The BOS-vs-`GENERIC_BREAK`
  trial-identity resolution is the owner's A/B/C choice (B recommended). Honest note in
  `order_block_v2.py`.
- **D-11..D-20 — RECORDED** in `docs/plan/DECISIONS-REQUIRED.md` Part II (v2.0). Origin-scope
  discipline held: the P0 economic gates (D-12 E07 admission, D-13 E07 stop-width floor) and
  D-14-exit / D-18 reconciliation / D-19 / D-20 sizing are **cross-estate (E07/E08/E09) / estate
  acts Origin must NOT build**; D-11 (F18 RR floor), D-16 (capsule order), D-17, D-21 touch Origin
  and are recorded as owner choices / errata, refusing-in-place.
- **B03C golden home strengthened.** +7 additive walks of the R-F03/R-F04/R-F09 headline repairs at
  the B03C golden home (`tests/formulas/test_f02_f09_goldens_b03c.py`, 8→15), each through the same
  acceptance path as its structure battery; dual-seed green.

## Gap register + repair work order cross-check (2026-08-13)
Owner-supplied `TRIAD_ORIGIN_V7_GAP_REGISTER` (`GAP-01…GAP-50`) + `TRIAD_REPAIR_WORK_ORDER`
(`WO-00…WO-Q`), **vendored verbatim** in `docs/repair/` with the full gap-by-gap disposition at
`docs/repair/GAP-CROSSCHECK-2026-08-13.md`. The scope wall governs: TriadOrigin is **E02 only**, so
RC3 law 07 + this repo's `CLAUDE.md` make ~34 of the 50 gaps (the E07 economic layer, E09 venue
drift, the DTBNK/estate bank + measurement debt, cross-repo governance) **out of Origin by
construction** — the register's own CORRECTION-01 says the economic gate must be built at E07, never
E02. Disposition: **1 CLOSED-IN-ORIGIN** (GAP-11/ERR-01, done), **6 OWNER-GATED recorded**
(GAP-12/ERR-02, GAP-13/D-17, GAP-04+46/D-11, GAP-50/D-22, GAP-39/D-16, plus the D-2 binding/TBD
set), **~34 OUT-OF-ORIGIN** (named to their estate node), **~9 ON-BOX/operator**. No Origin formula
byte was changed to match a non-ratified proposal; every gap is placed, none silently dropped; no
signature/pin/credential/receipt fabricated.

## Four-document set closure (R-01 + Master Sequence, 2026-08-13)
The owner added `TRIAD_REVISION_RECORD_R-01_2026-08-13` (correction record) and
`TRIAD_MASTER_SEQUENCE_2026-08-13` (sequencing + nine standing laws), completing a **four-document**
repair package (with the gap register + work order). All four are vendored verbatim in `docs/repair/`
(`NOT_A_RATIFICATION`); posture unchanged `OFF/OFF/OFF/LIVE`. Origin-scope closures:

- **ERR-02 / GAP-12 / WO-H — WITHDRAWN** as reviewer error (see above); `WO-H` retired.
- **LAW-9 recorded as standing estate law:** an external finding that would change a formula's
  emitted bytes or flip a passing test is an *amendment* (owner signature + prior spec PR), never an
  agent repair, *however obviously correct*. The discriminator is bytes, not correctness. It governs
  every item in `docs/repair/`.
- **R-01 §1.5 optional test — DONE, LAW-9-safe.** §1.5's proposed test as written would flip the
  passing T9 (the same recursive error as ERR-02); the LAW-9-safe response is the OPPOSITE
  byte-neutral clarifying test that confirms the reset bar deepens
  (`test_reset_bar_low_is_applied_to_the_extreme_err02_r01_corrected`, added, suite green).
- **WO-J (RPI book-completeness) — OWNER-GATED AMENDMENT, NOT ready agent work.** Cross-check shows
  WO-J adds a mandatory `book_completeness` field to F15/F16/F17 → changes emitted bytes + flips ~16
  frozen-dataclass constructor sites; under LAW-9 it lands only in a signed spec-amendment PR-set.
  Recorded owner-gated (D-register II·G); code UNCHANGED.
- **WO-C (F18) — VERIFIED_OK / check-only.** F18 already uses the ratified PAR-061 `2/1` (injected,
  not hardcoded); 32 tests pass. No change (the remove-generation-floor is the owner redesign D-11).

### Cross-repo lead: WO-A diagnostic harness (TriadLearning) + the BTC/BCH investigation
The Master Sequence's lead economics work order is **WO-A** (diagnose the ~13 pp), which is
measurement-only and has no entry gate. It is homed in **TriadLearning** (not Origin — Origin owns no
economic layer): `TriadLearning/analysis/wo_a/` — A0.1–A0.4 + A1 + A2 + A3 SELECT-only queries, a
pure stdlib arithmetic module proven against the work order's own reference table
(0 %→26.4, 35 %→42.7, 50 %→49.6, 65 %→56.6), an on-box runner that reuses the estate's first-touch
resolver for the A1 no-fill counterfactual, and a reconciliation that degrades to a NAMED
`ON_BOX_PENDING` off-box (the bank is on the Mac; no number is fabricated). **WO-B is NOT built**
(it amends RC3 law 14 and is gated on the SYNC-2 no_fill_win_share go/no-go).

The BTC/BCH funnel-collapse investigation (`docs/repair/INVESTIGATION-BTC-BCH-2026-08-13.md`,
read-only, 6-lane funnel audit) finds **no code path selects exactly {BTC, BCH}**; the extreme
collapse is best explained by the *intersection* of general per-symbol narrowers at ~$100 equity —
the VGP `min_notional_after_rounding` × the owner-margin-capped notional, and the scan_gate `$25k`
depth floor — with the config-precision `PENDING_VENUE_SNAPSHOT` hypothesis **ruled out** (VGP owns
precision from live `exchangeInfo`, not the config). The single fastest confirming read is on-box:
`SELECT * FROM shadow.v_symbol_gate_aggregate ORDER BY instrument_id;`.

## Final gate
12 required checks: pytest seed 0 + seed 1, collect_test_ids, verify_manifest,
validate_contract_manifest, verify_reproducible_build, test_wheel_install,
verify_no_forbidden_capabilities, e2e_audit, verify_source_hashes, build_ledger --verify,
validate_combined_dag.

**FINAL (fully integrated, clean env, dual-seed — re-run after the 2026-08-13 cross-check closure +
the B03C golden-home strengthening): ALL 12 GREEN.** pytest 3,149 tests, seed 0 + seed 1 both exit 0;
e2e = 30/30 stages; verify_source_hashes = 133 pins / 110 required; build_ledger --verify = v1 + v2
authenticated; all 10 non-pytest gates OK. Branch `claude/scorecard-origin-validation-mboymp` pushed;
PR #36 stays DRAFT — owner-gated (B00R root closure, GOV-01 signature, independent review, CO-06
semantic owner, and the v2.0 register D-11..D-21). No merge performed (none was requested).

## What only you / a semantic owner can do (never faked)
See `docs/plan/DECISIONS-REQUIRED.md` (D-1..D-10, D-3b) and `docs/plan/ONBOX-GUIDE.md` (O-1/O-2/O-3):
GOV-01 signatures, `PROPOSED_MUST_RATIFY` values, B00R three-root-decision authentication + external
trust-registry pin + `main` ruleset + receipt-v3 threshold-sign, OWNER-TOPO-01, CO-13/CO-11 signatures,
CO-10 credential rotation, CO-12 on-box salvage, the CO-06 17-SEM-row selection, the CO-09 provider run id.
