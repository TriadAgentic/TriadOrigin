# 01 · Milestone Breakdown

Status vocabulary: `PLANNED`, `IN_PROGRESS`, `BLOCKED`, `PR_OPEN`, `MERGED_UNVERIFIED`,
`VERIFIED`, `FAILED_AUDIT`, `SUPERSEDED`.

## R00 · Repository integrity refreeze — IN_PROGRESS

**Purpose.** Restore truthful governance and a defensible RC1 foundation without claiming RC2
acceptance.

**Deliverables.**

- Correct all 14 unresolved PR #1–#3 findings or record an explicit non-actionable disposition.
- Add regressions for epoch equality, fallback validation, manifest validity, wheel installation,
  float rejection, checkpoint integrity, cross-source ordering, revocation, heartbeat, quarantine,
  and LIVE-only production posture.
- Add GitHub CI for tests, byte manifest, manifest-schema validation, wheel-install validation, and
  negative-capability scanning; pin action commits and the resolved test/build dependency snapshot.
- Replace false M1/M2 completion language with merged-implementation/acceptance-blocked status.
- Replace the RC1 M1–M6 plan with R00/B00–B09 and add conflict/source/review registers.

**Acceptance.**

- Full local suite and manifest gate pass on the exact PR head.
- CI is green; no actionable PR thread remains.
- Old PR threads are replied to with the remediation PR/commit and resolved only after the fix exists.
- Fresh merged `main` reproduces all checks.
- R00 receipt validates against `milestone_receipt.schema.json`.
- Until issue #5 proves a durable main ruleset, merge is bound procedurally to the reviewed exact
  head SHA; the ruleset gap remains a B00 blocker and is disclosed in the receipt.
- Post-merge receipt is anchored on `evidence/r00-receipt`; failure leaves R00
  `MERGED_UNVERIFIED` and blocks B00.

**Does not assert.** RC2 conformance, package completeness, detector readiness, or live authority.

## B00 · RC2 authority and E02 scope freeze — BLOCKED

**Deliverables.**

- Complete RC2 source bundle, manifest, and exact byte digest.
- Corrected RC2 workbook/control catalogue with no false green or broken references.
- One canonical contract-version/compatibility map.
- Resolved `BLK-RC2-001…015` plus all missing consequential variables.
- Ownership matrix: `OWN`, `CONSUME`, `VERIFY_ONLY`, `REFERENCE_ONLY`, `OUT_OF_REPO`,
  `DEFERRED`.
- Explicit E02 input/output boundary and negative-capability policy.
- Durable main-branch ruleset requiring exact-head CI and review; close issue #5 with evidence.

**Acceptance.** Package validation, all B00 blockers closed by named authority, no `NOT_RATIFIED`
value in B01/B02 scope, and immutable B00 receipt.

## B01 · Contract and identity refreeze — BLOCKED_BY_B00

**Scope.** Re-audit RC1 M1 against the resolved RC2 bundle.

**Deliverables.**

- Additive contract versions only; published bytes never rewritten.
- Canonical semantic type versus JSON encoding decision.
- Clock field/unit decision and migration vectors.
- Installed-resource contract catalogue.
- Contract bundle validates against its own declared schema.
- Stable identity domains, correction/revision semantics, compatibility vectors.

**Acceptance.** Both supported validators agree on all golden vectors; installed wheel behaves
identically to checkout; manifest/registry/schema identities reconcile; all B01 receipt fields sealed.

## B02 · Kernel, transport, and replay refreeze — BLOCKED_BY_B01

**Scope.** Re-audit RC1 M2 within E02 ownership.

**Deliverables.**

- Pure transition kernel, integer math, ordering, quality, journal, checkpoint, ingress, telemetry,
  health, and append-only ledger.
- Production driver and replay driver invoke the same transition implementation.
- Checkpoint seals replay-controlling metadata.
- ORIGIN verifies external leases; lease issuance/durable coordinator remain out of repository.

**Acceptance.** Prefix/cold/warm/checkpoint/restart/duplicate/correction/future-mutation invariance;
same-input live/replay byte equality; no credential/order/risk/money capability; B02 receipt sealed.

## B03 · Parameter substrate, features, and typed levels — BLOCKED_BY_B00_B02

**Scope.** Resolved E02 F02–F07. F01 is an upstream E01 conformance boundary.

**Deliverables.**

- Immutable parameter-set schema, digest, verify-only signature/trust-root handling, and ratification
  state; no private signing key.
- Explicit DARK proposed parameter pack; no code default.
- ATR, directional-change swing, closed fractal, rolling extremes, anchored equal levels, and
  session-level consumption/validation as resolved by B00.
- Named nulls for warm-up, gaps, stale metadata, and missing parameters.

**Acceptance.** Every function binds exact F/PAR/GV/test IDs; equality/one-unit/mirror/scale/replay
vectors pass; no unresolved B03 parameter is silently selected.

## B04 · Structure truth — BLOCKED_BY_B03

**Scope.** Resolved F08–F13.

**Deliverables.** Direction/protected swing, accepted BOS/CHOCH, FVG, displacement, causal order
block, excursion/reclaim, exact lifecycle/precedence/correction behavior.

**Acceptance.** Same-event precedence, terminal-state, correction, identity, mirror, restart,
future-mutation, and null-honesty proofs pass for each structure family.

## B05 · Flow and reaction — BLOCKED_BY_B04

**Scope.** Resolved F14–F17.

**Deliverables.** Departure/first touch, TFI, OFI, and book tilt. Liquidation/exhaustion are excluded
unless separately defined by exact formulas and parameters.

**Acceptance.** Sequence-continuity, watermark, TTL, zero-denominator, stale/null, first-touch
consumption, correction, mirror, and replay tests pass.

## B06 · Geometry, clustering, and candidate publication — BLOCKED_BY_B05

**Scope.** Resolved F18–F19 and W06 treatment publication.

**Deliverables.**

- Directional entry/stop/target geometry with stop-side invariant and RR floor.
- Stable, non-circular opportunity identity.
- Immutable treatment candidate, named abstention, expiry, correction, and E02-owned withdrawal.
- No account, quantity, leverage, authorization, order, fill, or invented expected-return field.

**Acceptance.** Complete geometry at publication, target causally pre-existing, one candidate per
identity, no alias duplication, and contract/forbidden-field tests.

## B07 · Five capsules and trial integrity — BLOCKED_BY_B00_B06

**Scope.** Exactly one ratified capsule family.

**Deliverables.** Five isolated capsules, each with exact structural and flow predicates,
entry/invalidation/target, named abstentions, formula/parameter/trial digests, preregistration, and
ablations. No voting ensemble.

**Acceptance.** Isolation, no hidden conjunct, first-touch consumption, withdrawal, ablation,
preregistration, denominator, replay, and no-post-outcome-selection proofs.

## B08 · DARK E02 service integration — BLOCKED_BY_B07

**Scope.** Consume W02; own W03–W06 and E02-specific W23–W25 facts.

**Deliverables.** Service startup/sync/warm/readiness/drain/recovery, logical append-only bindings,
ACL/negative-capability enforcement, route/funnel telemetry, replay CLI, read-only evidence.

**Acceptance.** `READY_NO_AUTHORITY`, zero venue/order/risk/money capability, no legacy runtime
import, exact replay parity, clean shutdown/recovery, and prospective DARK receipt.

## B09 · Full verification and operator artifacts — BLOCKED_BY_B08

**Deliverables.** Complete mapped offline registry, immutable receipts, paired same-tape comparison
tool, read-only evidence projections, migration/rollback/incident/DR runbooks, and explicit external
test register for every test not executable in this repository.

**Acceptance.** Every in-scope requirement maps to code, test, evidence, and owner; every exclusion
has an ID/reason/later gate; no writable MCP or money path.

## External governance stages

RC2 G6–G9 rehearsal, canary, prospective money sample, cutover, scaling, and retirement are outside
this repository and are never implied by B09.
