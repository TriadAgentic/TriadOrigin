# 08 · Master Build Checklist — Reconciled

_A box is checked only after the owning source PR is merged green and the item is evidenced. A
milestone closes only when its separate post-merge receipt validates. Gate completion requires a
separate gate receipt._

The canonical machine projection is `docs/control/closure/closure_status.v1.json`. This checklist
is descriptive and cannot override a composite milestone identity, blocker, receipt, or result.

> **B00R generation-2 correction (2026-08-11):** checked historical boxes prove only that artifacts
> exist. PR #31 and PR #32 merged without submitted reviews and before the real main ruleset was
> created; generation 1 is therefore `MERGED_UNVERIFIED` and immutable. PR #33 is open, unreviewed,
> and post-hoc. Legitimate closure requires the additive G2 policy, exact provider chronology,
> independent exact-head review, separate G2 receipt, and validated
> `B00R_RECEIPT_ANCHOR_G2`. B01C onward stays frozen. See `04_STATUS.md`,
> `docs/governance/B00R_GENERATION_LEDGER.v1.json`, and
> `docs/governance/B00_B07_INVALIDATION_MANIFEST.v1.json`.

## Global controls

- [ ] Controlling result displayed as `DENIED_SAFE_HOLD` in every status/readiness face
- [ ] Exact required baseline is OFF/OFF/OFF/LIVE; no forbidden alias appears as a valid value
- [ ] Formula registry equality proves F00–F23 and no F24
- [ ] E02/E07/E08/E09/E10 authority import and behavior boundaries pass
- [ ] Combined RC3+RC4 DAG closes referentially and preserves source ownership/dependencies
- [ ] Every task has task → criterion → verification → receipt traceability
- [ ] Every mandatory blocked verification remains visibly blocking
- [ ] One source PR + one post-merge evidence-only receipt PR per milestone
- [ ] No next milestone branch before the prior post-merge receipt passes
- [ ] Every capability extends the end-to-end audit in the same source PR

## B00R generation 1 · immutable disposition

- [x] Preserve source PR #31 identities: head `6033e9e…`, merge `5b2a0ed…`, zero submitted reviews
- [x] Preserve receipt PR #32 identities: head `462152e…`, merge `76b5e48…`, zero submitted reviews
- [x] Preserve `evidence/receipts/B00R.receipt.v3.json`, digest `f1328ceb…`, and
  `B00R_RECEIPT_ANCHOR` without edits or repointing
- [x] Record `MERGED_UNVERIFIED` reason codes in `B00R_GENERATION_LEDGER.v1.json`
- [x] Record that ruleset `20641102` and PR #33 evidence are post-hoc and cannot repair generation 1
- [ ] **Forbidden forever:** retro-review generation 1 into PASS, replace its receipt/evidence bytes,
  or move its anchor

## B00R generation 2 · only open root correction

- [ ] Merge the canonical C0 composite registry, legacy crosswalk, D-01–D-09 dispositions,
  acceptance profiles, T0–T12 matrix, status snapshot, and validator on the final reviewed head
- [ ] Prove the positive B00R SOURCE allowlist rejects contracts, formulas, runtime/control modules,
  adapters, venues, deployment/ops, `docs/spec*/**`, `docs/closure/**`, and mixed evidence
- [ ] Prove the documented repository-relative constraint remains valid across every isolated
  wheel verifier cwd transition
- [x] Additive policy `docs/control/b00r_policy.v2.json` names audited start `76b5e48…`
- [x] Distinct decisions and identities defined: `DEC-AUTHORITY-BUNDLE-002`,
  `DEC-RECEIPT-PROFILE-002`, `DEC-B00-REPAIR-002`, `evidence/B00R_G2/`,
  `B00R.g2.receipt.v3.json`, and
  `B00R_RECEIPT_ANCHOR_G2`
- [x] Generation-1 evidence guarded immutable; G2 receipt role rejects mixed content
- [x] Source PR/review provider records require actual PR number, final head, merge SHA/time, positive
  review id, exact-head `APPROVED`, independent author/reviewer, and pre-merge submission time
- [x] Bootstrap the exact `@djordi10` critical-path CODEOWNERS bytes onto `main` in independently
  reviewed PR #35; ordinary merge `ba495ba90e0e4eff50ed75d2443f9cc12ce6ddcd` is the reserved
  source-merge first parent
- [ ] Land the truthful fresh-clone/fresh-venv clean-runner capture producer on the final corrective
  source head; a verifier without a producer is not reproducible evidence
- [ ] Owner-authenticate all three G2 `002` decisions under the G2 registry; externally pin all four
  decision/trust objects
- [ ] Install/capture/pin an active provider rule targeting exactly `main` plus
  `b00r-ruleset-canary`, with empty exclusions, no bypass, integration-bound strict CI, required
  review controls, and `allowed_merge_methods=["merge"]`
- [ ] Execute the canonical dedicated direct-push canary before source merge; close its transcript
  and provider rule-suite response under `evidence/B00R_G2/`
- [ ] Freeze corrective source head; exact-head CI green; sole independent CODEOWNER submits approval
  on that head; every actionable thread resolved
- [ ] Merge corrective source using the enforced ordinary two-parent merge method; prove its first
  parent equals the bootstrap merge, its second parent/tree equals the reviewed head, and capture
  exact PR/head/author/review/provider=Git chronology
- [ ] Hermetically reproduce the exact source merge with identical seed-0/seed-1 test inventories
- [ ] Open a separate append-only receipt PR containing only `evidence/B00R_G2/**` and
  `evidence/receipts/B00R.g2.receipt.v3.json`
- [ ] Before final receipt signing/review, install/capture/pin the no-bypass G2 tag rule
- [ ] Require receipt exact-head CI and independent approval; merge with source as literal first
  parent and reviewed receipt head/tree as second parent/result; permit no intervening main merge
- [ ] Publish the protected annotated `B00R_RECEIPT_ANCHOR_G2`; run the privileged terminal receipt
  gate with the positive receipt PR number at the exact receipt merge
- [ ] Only after terminal `PASS_REPOSITORY_SAFE_HOLD`, branch B01C from that receipt merge

## B00 · Historical source import

- [x] RC2/RC3/RC4 source/control package merged in PR #8
- [x] PR #8 exact-head CI succeeded
- [x] B00 post-merge receipt sealed and semantically valid — `evidence/receipts/B00.json` binds `1217297…` (sealed in-band under the superseded cadence; disposition A3)
- [x] R00 receipt sealed or signed field-for-field v2 supersession recorded — `docs/governance/R00_SUPERSESSION.md` + `evidence/receipts/R00.json` (B00C; operator countersignature requested, register A3)

## B00C · Historical corrective-control artifacts

- [x] Merge reconciled 00/01/04/08/09 documents and alignment audit — PR #12, merge `b641edc…`
- [x] Correct all formula/owner references to F00–F23; remove F24 — registry-equality + no-affirmative-F24 tests
- [x] Row-review all 1,250 schedule assignments; record reviewer/disposition — `build_ledger_review.v1.json`, `--verify`-enforced
- [x] Combined RC3+RC4 referential/cycle/inversion/one-owner/source-authority validator — `tools/validate_combined_dag.py` (CI + e2e stage 16)
- [x] `evidence_receipt.v2`, `task_status_event.v2`, `gate_receipt.v2` + semantic validator — landed B01, gate-receipt PASS law hardened at B00C
- [x] Invalid receipt fixtures: stale/scope/digest/reviewer/blocker/rollback/composition failures — `tests/test_b00c_control_closure.py` refusal battery
- [ ] Issue #5 is open/reopened; post-hoc ruleset `20641102` and rejected administrative canaries are
  useful historical evidence only. Close it only after G2 terminal PASS.
- [ ] Fetch current provider truth, then promote the future control to the stricter G2 profile:
  exact main+canary target, no exclusions,
  no bypass, integration-bound `test-and-verify`, `do_not_enforce_on_create=false`, independent
  CODEOWNER, and merge-only method; recapture and pin it before the G2 source merge
- [x] Seal R00 disposition and exact-current-main B00 receipt — `R00_SUPERSESSION.md` + `evidence/receipts/{R00,B00}.json`
- [x] B00C source PR merged green — PR #12, CI `31296105920`
- [x] B00C post-merge receipt passed; B01R may open — `evidence/receipts/B00C.json` binds `b641edc…` (this receipt PR)

## B01 · Contract, identity, and binding foundation

- [x] Typed identity v2 + migration vectors; v1 IDs stable — PR #9, pinned v1 vector `sinst_e7be341c…`
- [x] `engine_attestation.v2` equality law + corrected goldens — PR #9
- [x] Bundle descriptor v2; inherited bundle bytes unchanged — PR #9, RC1/R00 pins held
- [x] Catalog all ten RC4 contracts, including `execution_authorization.v3` and `fill.v3` — PR #9
- [x] Contract schemas have positive and negative golden fixtures — 42 contracts, valid+invalid goldens, wheel smoke
- [x] `binding.v2` schema + semantic slot/cardinality/condition/scope/precedence validator — B01R (`triad.binding.v2` + payload-level semantic law)
- [x] All 105 binding rows migrated and source status preserved — B01R (`binding_registry.v2.json`: 3 ACTIVE / 4 BLOCKED / 98 BLOCKED_BINDING_V2_MIGRATION)
- [x] Blocked bindings cannot be consumed — B01R (`bindings.resolve` refuses by name; forgery drill in `test_binding_v2.py`)
- [x] Compatibility manifest + producer-lease verification; no lease issuance in ORIGIN — `lease.py` verify-only
- [x] Epoch/scope/wildcard/stale/split-brain regression battery — PR #9
- [x] End-to-end identity/binding/contract stage — `identity_v2_walk` + `epoch_fence` + `contracts_manifest` + `binding_walk` (B01R, e2e stage 17)
- [x] Source PR merged green — PR #9, CI `31294503427`
- [x] Post-merge B01 receipt passed — `evidence/receipts/B01.json` binds `a00e2ee…` (in-band cadence; disposition A3)

## B02 · Kernel and E01 interfaces

- [x] F00 exact tick/step conversion + boundary goldens — GV-001 side rounding conformance, PR #10
- [ ] Validate/consume E01 F01 finalized bars; ORIGIN cannot publish them — **GAP → B03 source PR**
- [ ] Validate/consume E01 F07 UTC session levels; ORIGIN cannot publish them — **GAP → B03 source PR**
- [x] External durable journal anchor + tail deletion/replacement falsification — PR #10
- [x] Cold/warm/restart exactly-once parity — PR #10
- [x] Per-scope fencing high-water sealed/restored before consumption — checkpoint v3 fence state, PR #10
- [x] Partition/watermark/checkpoint/replay receipt kernel — R00 kernel + B02 hardening
- [x] RC4 17-bound timing registry imported as data; age injected — `timings.py`, drift-locked to the RC4 bundle
- [ ] End-to-end anchor/fence/E01-ingress stage — anchor/fence/timing walks live; E01-ingress leg lands with B03
- [x] Source PR merged green — PR #10, CI `31295070373`
- [x] Post-merge B02 receipt passed — `evidence/receipts/B02.json` binds `a44bd7a…` (sealed in the B00C source PR per its charter)

## B03 · F02–F09 causal feature/structure layer

- [x] F02 true range/trailing ATR over prior finalized bars — GV-004 exact, PR #16
- [x] F03 directional-change swing + required parameter/binding closure — GV-005 exact, declared-rule-only law
- [x] F04 closed fractal pivot with strict tie rejection — GV-006 exact
- [x] F05 rolling extreme — implemented + repo-pinned boundary tests; linked RC3 golden vector remains owed (register E11)
- [x] F06 equal-level interface; named abstention while max span is unratified — GV-007 exact, F06_UNAVAILABLE_MAX_SPAN_NOT_RATIFIED
- [x] F08 protected-structure interface; no semantic output until reducer ratified — pure refusal interface, zero implementation
- [x] F09 generic accepted break; BOS/CHOCH only with valid F08 state — GV-008 exact, UNCLASSIFIED_STRUCTURE_STATE_UNAVAILABLE
- [x] Append-only structure atom/transition publication — journal round-trip proven
- [x] Prefix/restart/duplicate/mirror/boundary/no-lookahead/null-honesty battery — 86 tests across the three module families
- [x] End-to-end market state → structure stage — e2e stage 18 structures_walk
- [x] Source PR merged green — PR #16, CI `31298074478`
- [x] Post-merge B03 receipt passed — `evidence/receipts/B03.json` binds `1bb00a7b…`

## B04 · F10–F13 and F15–F17 structure/flow layer

- [x] F10 FVG + TTL/invalidation/same-bar/future-touch boundaries — GV-009 exact, monotonic shrink
- [x] F11 displacement + parameter/golden closure — GV-010 exact, exact-rational never float
- [x] F12 causal OB + linked BOS — PENDING/CONFIRMED/EXPIRED/BROKEN lifecycle; no TTL per formula row (register E15)
- [x] F13 excursion/reclaim + parameter closure — GV-011 exact, horizon boundary inclusive
- [x] F15 trade-flow imbalance — GV-013 exact rational (40/100), buy/sell-swap mirror
- [x] F16 best-level OFI — hand-worked vector (no linked RC3 golden, register E13); sequence-gap + watermark law
- [x] F17 depth-tilt interface; named abstention while minimum depth is unratified — GV-014 exact under TEST ratification, F17_UNAVAILABLE_MIN_DEPTH_NOT_RATIFIED
- [x] Append-only lifecycle reducer + illegal transition/withdrawal/expiry tests — closed 7-state graph, zero-mutation-on-illegal proven
- [x] End-to-end gaps/blocks/reclaim/flow stage — e2e stage 19 structure_flow_walk
- [x] Source PR merged green — PR #18, CI `31300989327`
- [x] Post-merge B04 receipt passed — `evidence/receipts/B04.json` binds `831cc22c…`

## B05 · Four-plane substrate

- [x] Exact lever types; `shadow_activation=LIVE` has no setter — `control/lever_law.py` `ACTIVATION_ENUM`/`VENUE_ENVIRONMENT_ENUM`, `SHADOW_CAPTURE_OFF_FORBIDDEN`
- [x] All 35 signed-bundle invalid aliases + typed/whitespace negative cases — `control/lever_law.py INVALID_ALIASES`, drift-locked + parametrized battery (`test_lever_law.py`)
- [x] All 10 valid combinations and all 32 exact refusal/containment rows — `control/lever_law.py VALID_COMBINATIONS`/`REFUSAL_CODES`, drift-locked to `rc4_control_bundle.json`
- [x] Exact OFF/OFF/OFF/LIVE baseline manifest — `control/lever_law.py BASELINE_MANIFEST`
- [x] Manifest scope/digest/revision/staleness resolver; stale means venue/PAPER OFF — `control/lever_registry.py` (CAS revision fencing, digest binding, `RESOLVE_STALENESS`)
- [x] Durable SHADOW outbox, ledger, rejection audit, resolver, heartbeat, backlog, coverage — `control/shadow_ledger.py` + `control/shadow_health.py`
- [x] All SHADOW dispositions and `SHADOW_UNTRADEABLE` malformed path — `shadow_ledger.py` REJECTED/ACCEPTED_NOT_EXECUTED/PROVEN_NO_VENUE_EFFECT + the 12-conjunct tradeability gate
- [x] Frozen geometry/watermark + versioned evaluation model + fixed notional + bps/R + `NO_FILL` — `shadow_ledger.py` freeze-at-`SHADOW_CANDIDATE` + `SHADOW_FILL_MODEL`'s one designed exception
- [x] Persistence deadline and writer/resolver stale tests force venue/PAPER OFF — `shadow_health.py` (100/1000/5000/60000 ms bounds via `timings.py`)
- [x] Keyless PAPER executor and separate virtual order/fill/position/outcome ledger — `control/paper_ledger.py`
- [x] Static/runtime proof of no PAPER venue adapter or credential path — `paper_ledger.py`'s own import list + source-scan test (LEV-0078)
- [x] Physical and analytical separation: SHADOW/PAPER/TESTNET/LIVE — `population` is a hardcoded per-module constant, never a caller field; `test_population_separation.py` proves cross-schema validation fails both ways
- [x] ADR-005 supersession artifact prepared; no non-OFF activation without owner signature — `docs/governance/ADR-005-SUPERSESSION.md` (unsigned)
- [x] End-to-end four-plane/refusal/health stage — e2e stage 20 `four_plane_walk`
- [x] Source PR merged green — PR #20, CI `31303846548`
- [x] Post-merge B05 receipt passed — `evidence/receipts/B05.json` binds `bab29bcb…`

## B06 · F14/F18/F19 reaction, capsules, candidates

- [x] F14 departure/first-retest reaction engine — `structures/reaction.py` `DepartureAndFirstTouch`, `ELIGIBLE→DEPARTED→FIRST_TOUCH_CONSUMED|EXPIRED|INVALIDATED`, GV-012
- [x] F18 directional geometry/RR; one-tick stop and RR ≥ 2.0 boundaries — `structures/candidate_geometry.py` `evaluate_candidate_geometry`, exact cross-multiplication `reward*1>=risk*2`, GV-015 (T=104 admits, T=103 abstains one tick below)
- [x] F19 frozen earliest prospective cluster root; no re-root — `structures/clustering.py` `OpportunityClusterRegistry`, connected-components join; a genuine two-cluster match resolves per the RC3 errata (earliest root wins deterministically, the other cluster is RECORDED as an alias — `CLUSTER_ALIASED`, never a merge, never a refusal), GV-016
- [x] Semantic capsule registry with five stable IDs — `structures/capsules.py` `CANONICAL_SEMANTIC_IDS` (5), each bound by NAME and/or `formula_refs` evidence, never by ordinal position
- [x] RC2 ordinal capsule parameters removed from executable binding unless explicitly remapped — `capsules.resolve_capsule` refuses every `CAP01..CAP05` ordinal spelling (`CapsuleUnavailableError`); PAR-178 registered honestly as `ORPHANED_LEGACY_PARAMETERS`, bound to no capsule
- [x] Isolated capsule host; no voting/ensemble — `resolve_capsule` returns exactly one `CapsuleDefinition` or raises; no blending code path exists
- [x] Complete immutable `edge_candidate.v2`; no money fields — `structures/candidate_publisher.py` composes the full payload, validated via `contracts.validate_payload` (schema + `assert_no_forbidden_candidate_fields`); a candidate's stored geometry never mutates (disagreeing redelivery raises)
- [x] Append-only expiry/withdrawal/data-invalid transitions — `CandidatePublisher._transition_candidate`, `PUBLISHED→WITHDRAWN|EXPIRED|DATA_INVALID`, each terminal; an already-terminal candidate refuses by name
- [x] Atomic mandatory SHADOW fork for every candidate disposition — `CandidatePublisher._publish` nests `ShadowLedger().transition(...)` inside its own transition call: every `PUBLISH_CANDIDATE` produces a candidate+shadow_trade pair or a shadow_rejection_audit alone, never neither, never a follow-up call
- [x] Malformed candidate goes only to rejection audit; no fabricated trade — an `edge_candidate_valid=False` (schema-invalid, or a forbidden money field) or any of the 12 re-derived tradeability flags false routes to `CANDIDATE_PUBLICATION_REFUSED` + `SHADOW_REJECTION_AUDIT_RECORDED`, never a published candidate
- [x] Trial family preregistered before result access — `structures/trial_registry.py` `TrialRegistry`, append-only/immutable-once-set; `resolve_trial` (candidate_publisher's own read) raises `TrialUnavailableError` for an unregistered `trial_id`
- [x] Leave-one-conjunct ablations registered — `trial_registry._derive_ablations`, N conjuncts → N deterministic ablation ids, auto-derived, never hand-picked
- [x] End-to-end structures → reaction → candidate → SHADOW stage — e2e stage 21 `candidate_publisher_walk` (F14 GV-012 → F18 GV-015 → F19 GV-016 → capsule/trial identity → the atomic fork → untradeable path → lifecycle withdrawal)
- [x] Source PR merged green — PR #22 (5 Codex review findings addressed in the same PR, all threads resolved), CI `31308196194`, merged `33ff02a6`
- [x] Post-merge B06 receipt passed — `evidence/receipts/B06.json` binds `33ff02a6…`

## B07 · Configuration, comparison, bridge, replay

- [x] Signed/digest-pinned configuration families + fail-closed loader — `config/parameters.py`
  (192-row `ParameterRegistry`, `parameter_digest`, `require()`) + `config/signed_bundle.py`
  (the 13-domain self-signing bundle, `build_signed_bundle`/`verify_signed_bundle`)
- [x] Exact OFF/OFF/OFF/LIVE control manifest instance — already built in B05
  (`control/lever_law.BASELINE_MANIFEST`); reused, not re-built
- [x] All 192 parameter rows materialized with source status — `ParameterRegistry.status_counts()`
  (16 statuses, 141 refused + 51 materialized, verified programmatically; disposition row E25(b))
- [x] `require()` rejects proposed/unratified/stale/missing/scope-mismatched values —
  `ParameterRegistry.require()` (`ParameterRefusedError`/`ParameterDigestMismatchError`/
  `ParameterUnknownError`/`ParameterScopeMismatchError`); `tests/config/test_parameters.py` (37 tests)
- [x] Comparator keeps `engine_cohort` and `intelligence_arm` independent —
  `control/comparator.py` (`compare_engine_cohort`/`compare_intelligence_arm`, each refusing a
  candidate mislabeled for its own axis, AND (PR #24 review, row E27 finding 3) refusing when the
  non-compared axis disagrees between control/treatment — never a possibly-confounded
  divergence); `tests/control/test_comparator.py` (26 tests, incl. the vendored-enum drift-lock)
- [x] Authority component verifies external facts/technical-writer lease only —
  `control/authority_fact_verifier.py` (`AuthorityLedger`, verify-only over
  `candidate_authority.v1` + `producer_lease.v1`; row A7; PR #24 review, row E27 findings 1/4/5:
  an optional injected `signature_verifier`, a currency check in `admit_fact` before any stateful
  ordering logic, and exact-scope-match conjuncts in `readiness()`); `tests/control/test_authority_fact_verifier.py`
  (58 tests, incl. the ordering/stale/duplicate/split-brain law + the no-write-verb structural check)
- [x] No ORIGIN candidate admission/arbitration or money-selection lease path — `AuthorityLedger`
  exposes `admit_fact`/`current_for_scope`/`clear_split_brain` only (a fencing-token bookkeeping
  law, never a candidate/order verb); `assert_strictly_higher_token` proves a rollback token
  lawful but issues nothing
- [x] Frozen legacy bridge preserves bytes and omissions; exact source/path bound —
  `control/legacy_bridge.py` (`bridge_legacy_record`/`LegacyBridgeState`,
  `verify_byte_preservation`; row F2's exact path stays an OPEN operator decision, the mechanism
  is generic over any caller-supplied source; PR #24 review, row E27 finding 2: `legacy_payload`
  is a canonical-round-trip-detached copy, and every `LegacyBridgeState` read path returns a deep
  copy, so neither the caller's own `raw_record` nor a previously-returned envelope can corrupt
  cached state); `tests/control/test_legacy_bridge.py` (23 tests)
- [x] Same-code replay runner + digest-complete replay receipt — `control/replay_runner.py`
  (wraps `journal.replay`, the SAME live/replay code path; emits a schema-valid
  `triad.replay_receipt.v1` payload); `tests/control/test_replay_runner.py` (21 tests, incl. two
  independent runs byte-identical + checkpoint-resume state identity vs a cold full-tape run)
- [x] Service reaches `READY_NO_AUTHORITY` with zero venue/order/credential capability —
  `service.py` (`compute_service_readiness` composes the R00 bootstrap conjuncts with the new B07
  control-plane conjunct; never exceeds `READY_NO_AUTHORITY` — the enum has no state beyond it);
  `tests/test_service.py` (13 tests) + `tools/verify_no_forbidden_capabilities.py` green
- [x] End-to-end config/comparison/authority-fact/bridge/replay stage — `tools/e2e_audit.py`
  stage 22 `b07_control_plane_walk`
- [x] Source PR merged green — PR #24 squash-merged as `2cebc1391d65028a2a7de200d2e3fb9f82369872`
  (CI green on both the initial push and the five-finding review-fix push, all five review
  threads resolved with reply)
- [x] Post-merge B07 receipt passed — `evidence/receipts/B07.json`, full gate reproduced against
  the exact merged SHA (both pytest seeds, 1491 tests; `collect_test_ids`/`verify_manifest`/
  `validate_contract_manifest`/`verify_reproducible_build`/`test_wheel_install`/
  `verify_no_forbidden_capabilities`/`e2e_audit` 22/22 stages/`build_ledger --verify`/
  `validate_combined_dag`, all green)

## B08 · Read faces and evidence

- [ ] `get_engine_lever_registry`
- [ ] `get_engine_lever_attestation`
- [ ] `get_engine_lever_history`
- [ ] `get_shadow_health`
- [ ] `get_four_plane_status`
- [ ] `get_engine_inventory_reconciliation`
- [ ] Requested/effective/proof shown separately
- [ ] SHADOW activation shown separately from SHADOW health
- [ ] Offsets/watermarks/quality/lineage/funnel/divergence/replay/receipt/readiness views
- [ ] Honest `UNAVAILABLE`/`NOT_MEASURABLE`; source/freshness/completeness always named
- [ ] No secrets/control verbs; bounded queries/cardinality
- [ ] End-to-end read-face stage
- [ ] Source PR merged green
- [ ] Post-merge B08 receipt passed

## B09 · Conformance, estate formula catalog, runbooks

- [ ] Account for 408 inherited RC1 tests
- [ ] Account for all 1,523 RC3 effective verifications
- [ ] Account for all 125 RC4 fixtures
- [ ] No blocked mandatory row counted green
- [ ] F20 E08 selected-policy sizing contract/vectors; no environment or rollout branch
- [ ] F21 E09 maker compilation contract/vectors
- [ ] F22 E09 reduction-only emergency IOC contract/vectors
- [ ] F23 E10 P&L/cost/R/markout contract/vectors
- [ ] Assert no F24 exists
- [ ] Migration/rollback/split-brain/SHADOW/PAPER/TESTNET/fill/reconciliation/DR runbooks
- [ ] Source PR merged green
- [ ] Post-merge B09 receipt passed

## B10 · Audit and repository seal

- [ ] Independent audit 1: source authority, formulas, contracts, bindings, DAG, traceability
- [ ] Independent audit 2: falsification, capability, four-plane, evidence-integrity attacks
- [ ] All P0/P1 findings fixed; lower findings fixed or blocking-deviation registered
- [ ] Implementation report separates built/verified/blocked/estate/operator work
- [ ] Final status and disposition register updated
- [ ] B10 source PR merged green
- [ ] Detached post-merge B10 terminal receipt passed
- [ ] TriadOrigin-local checkpoint references terminal receipt
- [ ] Handoff states `DENIED_SAFE_HOLD` unless separate estate gates exist

## Estate gate checklist

### G-1 / G0 / G1

- [ ] Credentials rotated/revoked; account/environment/permissions/position mode attested
- [ ] Process/writer/source/deployed/config/contract census current
- [ ] Strict contracts/manifests/leases/quarantine/receipts deployed in owning repos
- [ ] Current Binance routes/limits reverified and evidence-pinned
- [ ] U/u/pu book bootstrap, gap reset, reconnect, raw-before-normalize proven
- [ ] E01 finalized bars/session levels and replay certified

### G2 / G3 / G4 / G5

- [ ] Every consumed semantic parameter/binding/golden blocker closed
- [ ] Capsule registry and dependency-closed trial bundle signed
- [ ] Trial families + leave-one-conjunct ablations preregistered
- [ ] Frozen legacy path and exact paired offsets bound
- [ ] Full divergence/fault/OOS/PBO/DSR/multiplicity/maker-fill evidence
- [ ] Prospective OFF/OFF/OFF/LIVE window with physical venue denial and healthy SHADOW

### G6 / TESTNET / G7 / G8 / G9

- [ ] E07 admission, E08 selected-policy risk, E09 execution, E10 outcomes rehearsed
- [ ] Strict fill.v3 lineage, reconciliation, protection, and P&L conservation proven
- [ ] Same-digest TESTNET certificate passed before LIVE
- [ ] Eight owner blockers signed; one capsule/instrument/side/account canary only
- [ ] Economic proof uses disjoint populations and strict lineage
- [ ] Production risk values signed only after G8
- [ ] Progressive scope, stop/rollback, and estate-wide checkpoint passed
