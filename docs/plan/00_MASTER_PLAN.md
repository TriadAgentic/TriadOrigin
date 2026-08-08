# 00 · Master Plan

## 1 · Objective

Build TRIAD ORIGIN V7 as the clean-room deterministic **E02-V7** service inside the existing TRIAD
chassis. ORIGIN consumes canonical, watermark-safe E01 state and emits deterministic E02 facts.
It is not a new E00–E10 monolith.

The repository owns:

- causal feature snapshots and structure/lifecycle facts;
- reaction, hypothesis, abstention, withdrawal, and treatment-candidate facts;
- deterministic state, checkpoints, exact same-code replay, quarantine, telemetry, and evidence;
- a DARK service that reaches `READY_NO_AUTHORITY`.

The repository does **not** own:

- venue connectivity, private account state, order or fill creation;
- E07 policy selection;
- E08 allow/deny, sizing, reservations, or execution authorization;
- E09 command compilation, venue execution, protection, reconciliation, or emergency IOC;
- E10 outcomes, accounting, learning promotion, or profitability claims;
- lease issuance, risk/exit policy authority, a legacy runtime, or an authority router.

## 2 · Pre-R00 audited baseline

The 2026-08-09 pre-R00 `main` contained RC1 M1/M2 implementation. Local reconstruction reproduced
`165 passed` and the 91-artifact byte manifest, but GitHub has no CI status or workflow evidence.
Fourteen actionable review threads remain open, including P1 correctness failures. RC2 acceptance
was therefore unproven and M3 was blocked. This paragraph is an immutable audit snapshot, not the
post-R00 status; post-merge truth is carried by PR #4 and the R00 receipt.

## 3 · Constitution

1. **Causality first.** A semantic transition is a pure function of prior state, ordered input,
   immutable parameters, and dependency quality. No system clock, I/O, randomness, future data,
   unordered output, or float-dependent semantic comparison.
2. **One authority per fact.** E01 owns canonical input state; ORIGIN owns E02 facts; E07 selects;
   E08 authorizes and sizes; E09 executes and owns money truth; E10 derives outcomes.
3. **DARK is structural.** ORIGIN has no credential loader, signing secret, venue client, order verb,
   risk write, or money-publish capability. A boolean alone is not enforcement.
4. **Deploy is not authority.** ORIGIN may verify an externally issued candidate-producer lease.
   It may not issue or coordinate leases.
5. **No hidden experiment.** Every consequential parameter has an ID, type, unit, boundary,
   failure behavior, immutable digest, trial lineage, and ratification state. Proposed RC2 values
   may be explicit DARK fixtures; they are never runtime defaults or activation authority.
6. **Immutable contracts.** Published bytes never change under the same version. A version conflict
   requires a compatibility/migration manifest; otherwise `SAFE_HOLD`.
7. **Append-only honest evidence.** Corrections append revisions. Missing data yields a named
   null/abstention/unresolved state, never zero or an inherited value.
8. **Same code means same transition.** Live consumption and replay call the same production
   transition functions over the same ordered envelopes and immutable bundle.
9. **Review is a gate.** Test success cannot override an unresolved correctness finding.
10. **No live authorization by repository work.** B00–B09 deliver DARK code and operator artifacts.
    RC2 G6–G9 money rehearsals/canary/economic certification/cutover remain external governance work.

## 4 · Specification/control authority

The supplied RC2 package outranks the old RC1 plan only after its package completeness and internal
compatibility are proven. It currently cannot be declared canonical because:

- its linked complete checklist and `canonical/` bundle were not supplied;
- its workbook has broken control references and no evidence-backed task state;
- its prose conflicts on contracts, clocks, numeric representation, formulas, lifecycle, clustering,
  and capsule identity.

All such items are named in [`05_RC2_CONFLICT_REGISTER.md`](05_RC2_CONFLICT_REGISTER.md).
Resolution changes the spec/control artifacts first; implementation follows in a later PR.

## 5 · Corrected build sequence

| ID | Theme | RC2 relationship |
|---|---|---|
| R00 | Repository integrity refreeze | Repairs known M1/M2/review/CI truth without claiming RC2 |
| B00 | RC2 authority and E02 scope freeze | Resolves package, compatibility, ownership, and blockers |
| B01 | Contract and identity refreeze | RC2 G0 E02 slice |
| B02 | Kernel, transport, and replay refreeze | RC2 G0/G1 substrate within E02 |
| B03 | Parameter substrate, features, and typed levels | RC2 G2 F02–F07, after ratification |
| B04 | Structure truth | RC2 G2 F08–F13 |
| B05 | Flow and reaction | RC2 G2 F14–F17 |
| B06 | Geometry, clustering, and candidate publication | RC2 G3 F18–F19 |
| B07 | Five capsules and trial integrity | RC2 G3 |
| B08 | DARK E02 service integration | W02 consume; W03–W06 own; W23–W25 E02 facts |
| B09 | Full verification and operator artifacts | Offline/paired replay/read-only evidence only |

Build IDs deliberately differ from RC2 gates `G-1…G9`.

## 6 · PR and merge gate

Each milestone uses a fresh `agent/<milestone>-<description>` branch from verified `main`.
The PR body identifies exact scope, coupled requirement IDs, root cause, checks, rollback, and
residual blockers.

R00 alone is a documented bootstrap exception: it combines replacement of the already-invalid plan
with bounded foundation remediation because the audit discovered both before a corrected process
existed. This exception ends at the R00 merge; B00 onward follows the prior-plan-PR rule without
exception.

Mandatory evidence:

- authority-basis digest and status (`RATIFIED_BUNDLE` or explicitly noncanonical audit basis), plus
  exact scope digest;
- base, PR-head, and merge SHAs;
- build/toolchain, dependency-specification, and resolved dependency-snapshot identity;
- test IDs, commands, exit codes, skips/xfails, and result digest;
- contract-manifest, golden-vector, and replay output digests where applicable, with every
  non-applicable item named, owned, reasoned, and assigned to a later milestone;
- negative-capability scan;
- CI run identity and independent review state;
- post-merge fresh-main reproduction;
- supersession linkage to any earlier receipt.

## 7 · Verification strategy

Acceptance is falsification-first:

- prefix, future-mutation, duplicate, cold/warm/checkpoint/restart, and correction invariance;
- LONG/SHORT mirror and scale metamorphism;
- integer boundary, one-unit neighbor, null/stale/gap, and overflow tests;
- lifecycle monotonicity and identity stability;
- contract compatibility and installed-wheel conformance;
- same-code live-driver/replay-driver byte equality;
- forbidden credential/network/order/risk/money capability scans.

Test count is descriptive only. A test that encodes the wrong behavior does not prove conformance.

## 8 · External dependencies and stop conditions

B00 cannot pass until the complete RC2 bundle and compatibility decisions exist. B03 cannot start
until every formula it uses has resolved semantics and ratified-or-explicit-DARK parameters.
No B-stage may absorb out-of-repository estate work merely to make a checklist appear complete.
