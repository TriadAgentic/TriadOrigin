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

## Final gate (to re-run after CO-06/09 integrate)
12 required checks: pytest seed 0 + seed 1, collect_test_ids, verify_manifest,
validate_contract_manifest, verify_reproducible_build, test_wheel_install,
verify_no_forbidden_capabilities, e2e_audit, verify_source_hashes, build_ledger --verify,
validate_combined_dag.

**FINAL (fully integrated, clean env, dual-seed): ALL 12 GREEN.** e2e = 30/30 stages;
verify_source_hashes = 132 pins / 110 required; build_ledger --verify = v1 + v2 authenticated.
Branch `claude/scorecard-origin-validation-mboymp` pushed (65 commits ahead). PR #36 body rewritten;
stays DRAFT — owner-gated (B00R root closure, GOV-01 signature, independent review, CO-06 semantic
owner). No merge performed (none was requested).

## What only you / a semantic owner can do (never faked)
See `docs/plan/DECISIONS-REQUIRED.md` (D-1..D-10, D-3b) and `docs/plan/ONBOX-GUIDE.md` (O-1/O-2/O-3):
GOV-01 signatures, `PROPOSED_MUST_RATIFY` values, B00R three-root-decision authentication + external
trust-registry pin + `main` ruleset + receipt-v3 threshold-sign, OWNER-TOPO-01, CO-13/CO-11 signatures,
CO-10 credential rotation, CO-12 on-box salvage, the CO-06 17-SEM-row selection, the CO-09 provider run id.
