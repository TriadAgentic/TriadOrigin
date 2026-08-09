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
post-R00 status; post-merge truth is carried by PR #4, rejected corrective PR #7, final-receipt
PR #8, and the R00 receipt.

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
existed. PR #4's receipt attempt and PR #7's replacement attempt both failed closed, so the
exception remains open only for final-receipt PR #8 and the single receipt commit. It expires when
the corrective R00 receipt is sealed; B00
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
may use only the documented bootstrap merge procedure: re-read the immutable final-receipt PR #8
head, require its exact-head `CI / test-and-verify` run and authenticated clean Codex acceptance,
require zero unresolved actionable PR #8 threads, prove that the accepted head remained unchanged
through the complete issue timeline, and submit the squash merge with that same head SHA as the
expected value. A direct/admin merge outside that procedure invalidates the receipt; it does not
prove a durable ruleset. PR #4 used the same guarded procedure for the first, failed-closed attempt;
PR #7 then merged squash `0012e89214c7e0321592684b3b866323f891ace9` but failed the corrected
receipt law. Both exact heads, reviews, merges, and failure codes remain authenticated historical
evidence rather than the final acceptance target.

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
close. PR #7 is now an authenticated rejected predecessor: its three observed roots remain in the
historical set, and their exact post-merge closure replies are retained rather than deleted or
rewritten. Those replies bind the GraphQL `PullRequestReviewThread.id` (`PRRT_…`), not the numeric
root-comment database ID. PR #8 is the only PR that may own the final R00 receipt.
For either final-acceptance arm, every root and non-closure reply must be created and last updated
strictly before the selected review object or, in the clean-comment arm, before the final review
trigger. Historical roots, ordinary replies, and selected historical closures must also remain
strictly before that cutoff. For a selected PR #8 closure, creation must be strictly after merge and
`updatedAt` must not precede `createdAt`. Edit status is determined only by GraphQL `editor` and
`lastEditedAt`; both must be present and null for an accepted unedited row.

Exact-head review `4890352011` then opened root `3742370663` against the CI checkout: a fork PR's
`github.head_ref` is only a short source-branch name, while `actions/checkout` otherwise reads the
base repository. The correction checks out `github.event.pull_request.head.sha` and creates the
local `evidence/r00-receipt` branch only for a same-repository receipt PR. Both the branch setup and
receipt-auth step require `head.repo.full_name == github.repository`, so a fork cannot mint the
canonical evidence-branch identity. This review, root, and its exact-head trigger are source-pinned
before the next acceptance window. The single pre-fix acknowledgment is deliberately non-claiming;
its blank carrier review `4890384420` is also source-pinned, and the thread remains unresolved until
the corrected head passes CI.

The additive `origin.review-evidence.v4` and `origin.github-review-export.v4` preimages separate
historical PR #7 from current receipt PR #8. PR #7's squash identity (base, head, merge, tree, and
merge time), exact ten-review history, three closure carriers, and GraphQL thread inventory are
source-pinned and live-authenticated. PR #8 starts with an empty controlled-root and pre-acceptance
review/comment baseline; its own complete review, issue-comment, PR-root-reaction, pull, and
issue-timeline inventories are fetched twice and must equal the persisted export. Any
current `CHANGES_REQUESTED`, review at or after the selected final-head trigger, unbound post-merge
review, changed inventory, or pagination gap fails closed. The export asserts no unauthenticated
PR #1–#3 review rows and exactly the one controlled, live-bound PR #4 implementation review. The
same-repository PR #8 CI preflight reuses this raw GraphQL normalizer before merge and fails on
missing edit-witness keys, non-null edit witnesses, controlled-root drift, or changed historical
selected closures. The
clean-review-object arm remains valid only for an exact-head review object with no findings and is
subject to the same historical
comment/review, reaction, pull-boundary, and timeline law. The clean-comment arm requires an
unchanged maintainer trigger naming the full PR head and successful CI run/job, then an unchanged
connector response with the exact fixed declaration `Codex Review: Didn't find any major issues.`,
a structurally isolated one-line ASCII reason phrase, the exact reviewed-head marker, and the exact
common tail. The reason phrase is display-only protocol metadata: it is limited to 1–80 bytes by a
closed ASCII structural grammar; renderer syntax, Unicode, an extra sentence, or a suffix is
forbidden. Its lexical meaning is deliberately opaque and never supplies or contradicts the
machine verdict. The complete actual body remains byte-for-byte persisted, live-compared, and
SHA-256-bound. A unique
connector PR-level `+1` must be fresh for this review window—strictly after the full-head trigger
and no later than the clean response. Authority therefore comes from the fixed declaration, fresh
authenticated reaction, exact CI/head/timeline bindings, and complete zero-finding inventories,
not from the cosmetic reason phrase by itself.

Because submitted GitHub reviews have no review-body update timestamp, reviewed source pins PR #7's
exact ten review objects: IDs, raw and numeric actors, commit/state, complete bodies, submission
times, and URLs. PR #8 acceptance uses a new baseline instead of retroactively treating PR #7's
objects as current acceptance. Top-level PR #8 comments, including a fresh selected pair, must
remain unedited (`created_at == updated_at`). Any changed historical PR #7 review, extra PR #8
pre-merge review, or `review_dismissed` event after the final trigger fails closed.

The ten-comment baseline preserves all three observed clean display phrases—“What shall we delve
into next?”, “Bravo.”, and “Breezy!”—and their exact full bodies. Their variation is why v4 isolates
the bounded reason phrase instead of interpreting or matching its words. Each observation is
historical only; the final source head still requires its own successful CI, trigger, fresh
reaction, and clean response.

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
PASS. Root `3742096931` is the first such inline observation and root `3742370663` is preserved by
the same controlled-root law; the source-pinned extension above is their required disposition, and
their reviewed heads remain non-mergeable.
After the guarded PR #8 merge and any source-controlled canonical PR #8 inline closure replies,
receipt construction waits for two identical complete snapshots and seals them without any later
PR #8 top-level comment or head-branch deletion;
GitHub timeline eventual consistency is never papered over with a guessed export.

The final merge SHA and fresh-main result do not exist before merge, so an R00 receipt cannot
truthfully live in PR #4, PR #7, or PR #8. After PR #8's guarded squash merge, it is generated and
schema-validated at
`evidence/receipts/R00.json`; its canonical test-ID/results, commands, toolchain, review,
post-merge, manifest, dependency, source, sdist, and wheel preimages are persisted beneath
`evidence/R00/` (or referenced repository paths) and bound through `evidence_files`. It is validated
first by the JSON Schema and semantic cross-field checks, then anchored by one commit on
`evidence/r00-receipt` whose sole parent is PR #8's corrective merge SHA. From that committed state,
`tools/validate_milestone_receipt.py` reruns the semantic checks, reads the raw Git objects to prove
the merge tree/parent and committed evidence bytes, re-fetches PR #8 through the authenticated
GitHub API to prove author/reviewer separation, exact clean-acceptance identity, and complete stable
inventories, and the no-head-mutation timeline. The committed
`evidence/r00-receipt:evidence/receipts/R00.json` object is the immutable anchor; it is not posted as
a new PR #8 comment because that would invalidate the authenticated inventory. R00 remains
`MERGED_UNVERIFIED` and B00 may not start unless that post-merge mechanism succeeds.

The ordered failed-attempt chain records two rejected predecessors. PR #4 omitted the exact
dependency snapshot from its merged sdist. PR #7 repaired that byte but failed on GraphQL edit
witnesses, retroactive closure-body requirements, and numeric-root versus thread-ID semantics; no
receipt was published for either merge. PR #8 is therefore a bounded continuation of R00, not B00
and not a silent rewrite of PR #4 or PR #7 evidence. It preserves the exact historical closures,
authenticates PR #7's squash/reviews/threads, binds current PR #8 acceptance inventories, and passes
the same fresh-final-head, guarded-squash, fresh-main, and receipt controls. The final R00 receipt
binds PR #8's corrective squash and records both failed merges, their failure codes, CI runs, and
no-receipt outcomes as a typed v2 predecessor chain. Any broader implementation in PR #8
invalidates R00.

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
