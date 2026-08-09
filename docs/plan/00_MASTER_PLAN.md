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
post-R00 status; post-merge truth is carried by PR #4, corrective PR #7, and the R00 receipt.

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
existed. PR #4's receipt attempt failed closed, so the exception remains open only for corrective
PR #7 and the single receipt commit. It expires when the corrective R00 receipt is sealed; B00
onward follows the prior-plan-PR rule without exception.

Mandatory evidence:

- authority-basis digest and status (`RATIFIED_BUNDLE` or explicitly noncanonical audit basis), plus
  exact scope digest;
- base, PR-head, and merge SHAs;
- build/toolchain, dependency-specification, and resolved dependency-snapshot identity;
- test IDs, commands, exit codes, skips/xfails, and result digest;
- contract-manifest, golden-vector, and replay output digests where applicable, with every
  non-applicable item named, owned, reasoned, and assigned to a later milestone;
- negative-capability scan;
- CI run identity; independent review/thread state; and complete authenticated PR review,
  top-level issue-comment, PR-root reaction, and issue-timeline inventories;
- post-merge fresh-main reproduction;
- supersession linkage to any earlier receipt.

Repository ruleset enforcement is **not yet evidenced** by the available repository API. Issue
[#5](https://github.com/TriadAgentic/TriadOrigin/issues/5) is therefore a B00 control blocker. R00
may use only the documented bootstrap merge procedure: re-read the immutable corrective PR #7
head, require its exact-head `CI / test-and-verify` run and authenticated clean Codex acceptance,
require zero unresolved actionable PR #7 threads, prove that the accepted head remained unchanged
through the complete issue timeline, and submit the squash merge with that same head SHA as the
expected value. A direct/admin merge outside that procedure invalidates the receipt; it does not
prove a durable ruleset. PR #4 used the same guarded procedure for the first, failed-closed attempt;
its exact head, review, merge, and artifact failure remain historical evidence rather than the final
acceptance target.

For PR #4's completed pre-merge guard, “zero actionable threads” meant PR #4's six current review
threads. The 14 inherited PR #1–#3 threads were then given post-merge remediation replies citing
PR #4's actual squash SHA and receipt path and were resolved. The final receipt preserves those
historical API states and replies; it does not require them to cite PR #7's later corrective merge.
PR #7 acquired actionable root `3741593887` during adversarial review and later top-level review
`4889942759` identified non-concrete dependency-pin acceptance, so the evidence law is explicitly
extended here rather than erasing either finding. Exact-head review `4890177398` then opened root
`3742096931`, asserting that a timeline `merged.commit_id` is the resulting squash SHA. GitHub's
[official event contract](https://docs.github.com/en/rest/using-the-rest-api/issue-event-types#merged)
states that this field is the PR `HEAD` commit that was merged; the squash identity is separately
bound by the pull response and raw Git lineage. The reviewed disposition therefore preserves the
finding, retains the documented `head_sha` comparison, and adds a regression that rejects a
self-consistent substitution of `merge_sha`. Because this adverse result initially existed only as
a deletable inline comment, it also triggers the reviewed capture-law extension: the next source
head pins its exact root/review/trigger text and identities, and a coordinated live-plus-export
deletion must still fail against that immutable set. Every PR #1–#4 and PR #7 root, live resolution
state, and selected remediation reply must match two identical complete GitHub GraphQL snapshots.
The reviewed control set pins each root's immutable author, full finding text, path,
PR/review/comment/thread IDs, and URL; a post-merge export cannot redefine the finding it claims to
close. Each observed PR #7 root must be named in that set, fixed and resolved before merge, then
receive a live-authenticated post-merge reply citing the corrective squash and receipt path.
For either final-acceptance arm, every root and non-closure reply must be created and last updated
strictly before the selected acceptance artifact. The one selected canonical closure reply must be
created strictly after merge, remain unedited, and occur exactly once; tied, intermediate, later,
edited, missing, or duplicate thread activity invalidates acceptance.

The versioned `origin.review-evidence.v2` and `origin.github-review-export.v2` preimages fetch twice,
with complete pagination, PR #7's top-level review, issue-comment, PR-root-reaction, and
issue-timeline inventories and require both live snapshots to equal the persisted export. Any
current `CHANGES_REQUESTED`, review at or after the selected final-head trigger, unbound post-merge
review, changed inventory, or pagination gap fails closed. The clean-review-object arm remains valid
only for an exact-head review object with no findings and is subject to the same historical
comment/review, reaction, pull-boundary, and timeline law. The observed clean-comment arm requires an
unchanged maintainer trigger naming the full PR head and successful CI run/job, followed by a
complete byte-for-byte match to one of the finite Codex clean-response bodies ratified from live
artifacts, naming that head's reviewed prefix. The reviewed allowlist currently contains only the
observed “What shall we delve into next?” and “Bravo.” bodies with their exact common tail; unknown
wording, suffixes, or prefix-only matches fail closed. The persistent
PR-level `+1` from `chatgpt-codex-connector[bot]` is authenticated by raw login and immutable actor
ID and is supporting corroboration only: it need not be recreated for every trigger and can never
independently establish which head was reviewed.

Because submitted GitHub reviews have no review-body update timestamp, the reviewed source pins the
exact five-review and seven-comment PR #7 history that existed before this law: IDs, raw and numeric
actors, commit/state, complete bodies, submission/creation times, and URLs. The live export must
start with that exact review/comment baseline; it cannot redefine history after merge. Every
top-level comment, including the fresh selected pair, must remain unedited (`created_at ==
updated_at`). Any extra pre-merge review, changed historical review, or `review_dismissed` event
after the final trigger fails closed.

The complete issue timeline and boundary PR snapshots must show the same head and base from the
selected trigger through the guarded squash merge; any intervening commit, force-push, head-ref
deletion/restoration, base-ref deletion, `automatic_base_change_succeeded`, or other head/base ref mutation fails
closed. Post-merge head-ref deletion before sealing also fails closed. A clean result is
head-scoped: any later commit invalidates it
and requires new exact-head CI, a fresh full-head trigger, and a fresh clean acceptance artifact. An
earlier protocol observation therefore cannot accept the later commit that ratifies this law.
Missing, invented, unresolved, changed, stale-head, or pagination-incomplete evidence fails closed.
GitHub's issue timeline does not expose deleted issue- or review-comment history, so R00 does not
claim that it does. The accepted issue comment must be the exact clean artifact; Codex adverse
results are required to remain represented by the durable review/thread inventory. If Codex is ever
observed emitting an adverse result whose only durable form is a deletable top-level or inline
comment, the merge blocks pending a reviewed evidence-law extension rather than treating absence as
PASS. Root `3742096931` is the first such inline observation; the source-pinned controlled-root
extension above is its required disposition, and head `8380348c…` remains non-mergeable.
After merge and the canonical inline closure replies, receipt construction waits for two identical
complete snapshots and seals them without any later PR #7 top-level comment or head-branch deletion;
GitHub timeline eventual consistency is never papered over with a guessed export.

The final merge SHA and fresh-main result do not exist before merge, so an R00 receipt cannot
truthfully live in PR #4 or PR #7. After PR #7's corrective squash merge, it is generated and
schema-validated at
`evidence/receipts/R00.json`; its canonical test-ID/results, commands, toolchain, review,
post-merge, manifest, dependency, source, sdist, and wheel preimages are persisted beneath
`evidence/R00/` (or referenced repository paths) and bound through `evidence_files`. It is validated
first by the JSON Schema and semantic cross-field checks, then anchored by one commit on
`evidence/r00-receipt` whose sole parent is PR #7's corrective merge SHA. From that committed state,
`tools/validate_milestone_receipt.py` reruns the semantic checks, reads the raw Git objects to prove
the merge tree/parent and committed evidence bytes, and re-fetches PR #7 through the authenticated
GitHub API to prove author/reviewer separation, exact clean-acceptance identity, complete stable
inventories, and the no-head-mutation timeline. The committed
`evidence/r00-receipt:evidence/receipts/R00.json` object is the immutable anchor; it is not posted as
a new PR #7 comment because that would invalidate the authenticated inventory. R00 remains
`MERGED_UNVERIFIED` and B00 may not start unless that post-merge mechanism succeeds.

The first execution of that mechanism failed closed after PR #4: its reviewed sealer required the
exact dependency snapshot in the sdist, while the merged package omitted it. No receipt was
published. Corrective PR #7 is therefore a bounded continuation of R00, not B00 and not a silent
rewrite of PR #4 evidence. It must add the missing artifact byte, preserve every stronger sealer
check, bind reviews and complete acceptance inventories for PRs #1–#4 plus #7, and pass the same
fresh-final-head, guarded-squash, fresh-main, and receipt controls. The final R00 receipt binds PR
#7's corrective squash and records PR #4's
failed-closed merge, exact rejected sdist digest, CI run, and no-receipt outcome as a typed
predecessor. Any broader implementation in PR #7 invalidates R00.

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
