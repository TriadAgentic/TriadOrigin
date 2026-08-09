# 07 · Review Remediation Register

R00 owns all unresolved actionable findings from PRs #1–#3.

| Cluster | PR | Priority | Required correction | R00 evidence |
|---|---:|---:|---|---|
| Current epoch equality | #1/#2 | P1 | Accept subsequent events at current epoch; reject lower | Contract + ingress regression |
| Stdlib validator completeness | #1 | P1 | Enforce used pattern/length/range/array safety keywords or make full validator runtime law | Validator parity vectors |
| Manifest contract validity | #1 | P1 | Manifest artifact validates against declared schema | Generation + CI validation |
| Installed contract resources | #1 | P2 | Wheel contains registry/schemas/golden/manifest resources | Clean wheel-install test |
| Canonical floats | #1 | P2 | Reject every float, finite or not | Canonical/digest regression |
| Checkpoint integrity | #2 | P1 | Seal state and replay-controlling metadata | Per-field tamper tests |
| Cross-source ordering | #2 | P1 | Preserve receipt order across sources; compare source sequence within source only | Adversarial connection test |
| Revocation | #2 | P1 | Reject all writes while revoked until validated replacement lease accepted | Guessed-higher-token test |
| Heartbeat contract | #2 | P2 | Builder and schema agree; output validates | Golden heartbeat validation |
| Quarantine contract | #2 | P2 | Rejection record serializes contract-valid raw reference | Invalid-input output validation |
| Production modes | #3 | P1 | Production is LIVE-only; replay/simulation are offline harnesses | Package posture test |
| Durable lease truth | #3 | P1 | Remove lease issuance/coordinator runtime; keep verify-only fencing | Absence test + plan/traceability correction |
| OPS traceability | #3 | P2 | Map build, service, replay smoke, soak, ACL, rollback/DR work | `02_TRACEABILITY.md` |
| Receipt artifact closure | #7 | P1 | Include the reviewed dependency snapshot in the sdist and bind the corrective merge/review chain honestly | Real sdist + semantic receipt validation |
| Dependency pin grammar | #7 | P2 | Reject wildcard, range, marker, URL, hash, malformed, and normalized-duplicate dependency pins | Exact-pin parser + CI/sealer regressions |

The 14 inherited threads remained open through PR #4's pre-merge gate. After that merge, each
received a thread-specific reply citing squash `241b301d1144e3e2a0a15f4bfe9ffef5b51068ed`
and `evidence/receipts/R00.json`, and all 14 were resolved. PR #4's six current threads were also
resolved and later received the same post-merge closure reference.

This sequencing was deliberate: PR #4 had zero unresolved actionable current threads before merge,
while the inherited PR #1–#3 threads could close only after their replies could name the actual
squash SHA and receipt path. The receipt binds both populations and their actual API resolution
state; it does not rewrite when or against which merge those historical replies closed.

PR #4's first post-merge receipt attempt failed closed on the sdist/dependency-snapshot mismatch.
PR #7 is the only authorized corrective continuation. Adversarial review created actionable root
`3741593887`; later top-level review `4889942759` identified non-concrete dependency-pin acceptance.
Exact-head review `4890177398` then created root `3742096931`, claiming that the timeline
`merged.commit_id` is the squash result. GitHub's official event contract defines it as the PR head
that was merged, while the pull response and raw Git bind the resulting squash separately. The
controlled disposition preserves that root, retains the `head_sha` comparison, and regression-tests
rejection of a coordinated `merge_sha` substitution. Because the finding initially existed only as
a deletable inline comment, the corrective source also pins its exact root/review/trigger bytes and
IDs and rejects coordinated removal from both the live API and persisted export. This reviewed plan
names every finding instead of erasing history. Every observed PR #7 root enters
the controlled set, is fixed/replied/resolved before merge, and receives an authenticated
post-merge closure reply citing the corrective squash and receipt path. The sealer compares two
complete live GraphQL snapshots against every persisted PR #1–#4/#7 root, resolution, and selected
reply; a reviewed immutable root manifest pins every original root's finding text, author, path,
IDs, and URL. Incomplete pagination, edited roots, or any mismatch fails closed.
Both final-acceptance arms also apply a strict temporal cutoff: every root and non-closure reply
must predate the selected review object or, in the clean-comment arm, the final review trigger. The
exact selected closure reply must appear once,
strictly after merge, and remain unedited. Same-time, intermediate, later, edited, missing, or
duplicate activity blocks the receipt even when the thread is eventually resolved.

PR #7 first established the clean-comment protocol shape on head
`73771e53105a915756ae14fac93dc616190c4d1a`: exact full-head/CI trigger comment `5228555326` was
followed by exact connector clean-response comment `5228567753`, while PR-root reaction
`444909869` recorded `+1` from `chatgpt-codex-connector[bot]` (`199175422`). That observation
ratifies the artifact shape only. Because the commit that implements and documents this law creates
a different head, the `73771e…` clean result cannot authorize the final merge head.

Later clean results used “Bravo.” on head `52656010…` and “Breezy!” on head `2c9fbf09…`, while
retaining the same fixed clean declaration, reviewed-head marker, common tail, connector identity,
and fresh post-trigger `+1`. Those exact historical bodies remain source-pinned. Their stochastic
display phrase is explicitly opaque and non-authoritative in v3; each complete actual body is still
preserved and hashed exactly, but no lexical interpretation of the display phrase affects PASS.
The `2c9fbf09…` observation is trigger `5229144298`, clean comment `5229158255`, and fresh reaction
`444992088` at `2026-08-09T01:21:29Z`; it is historical evidence, not authorization for the next
source head.

Review `4890352011` on head `17a0645f…` then opened root `3742370663`: using the short
`github.head_ref` as the checkout ref fails for fork PRs because checkout still targets the base
repository. The correction checks out the immutable event head SHA and creates the named local
`evidence/r00-receipt` branch only for a same-repository receipt PR; the receipt-auth step has the
same origin guard. Trigger `5229377643`, review `4890352011`, root `3742370663`, and their exact
identities/bodies are historical source-pinned evidence, not a clean result. Its non-claiming
acknowledgment created blank carrier review `4890384420`, which is likewise source-pinned; the root
remains unresolved until the corrected head passes CI.

For the final head, the versioned v3 evidence fetches twice and persists the complete PR #7
top-level review, issue-comment, PR-root-reaction, and issue-timeline inventories. It rejects every
current `CHANGES_REQUESTED`, every review at or after the selected final-head trigger, every
unbound post-merge review, every inventory race or omission, and every commit, force-push,
head-ref deletion/restoration, `automatic_base_change_succeeded`, or other head/base ref mutation
between trigger and guarded merge. The reviewed law also pins the exact seven-review/ten-comment
pre-final history, including raw and numeric actors, complete bodies, commit/state, IDs, times, and
URLs. Every top-level comment must remain unedited; any changed historical review or post-trigger
review dismissal fails closed. The selected trigger must be
unchanged and name the full final head plus its successful CI run/job. A fresh unchanged Codex
clean-response comment must follow with the exact fixed declaration, a 1–80 byte one-line ASCII
opaque display reason with no renderer/control syntax, the exact reviewed-head marker, and the exact
common tail. The complete body remains
byte-bound; an extra sentence, suffix, Unicode/control byte, or malformed envelope fails closed. A
unique connector PR-root `+1` must be
created strictly after this trigger and no later than the clean response. The sealed
export preserves historical states and does not relabel PR #4 or the `73771e…` observation as the
accepted corrective merge.

GitHub's issue timeline does not expose deleted issue- or review-comment history; this law does not
pretend otherwise. The selected top-level result must be the exact clean artifact, while Codex
adverse results must remain visible through the durable review/thread inventory. If the service is
ever observed emitting an adverse result whose only durable form is a deletable top-level or inline
comment, PR #7 remains blocked until a reviewed capture law covers that new protocol shape.
Roots `3742096931` and `3742370663` are covered by that extension; source-pinning their complete
identities and requiring exact live-set equality closes these observed shapes only. It does not
create a generic deletion history.

After merge, post the canonical inline closure replies first, then wait for two identical complete
API snapshots containing the merge and replies. Build and seal the receipt without any later PR #7
top-level comment or head-branch deletion: either mutation would invalidate future live
revalidation. The committed `evidence/r00-receipt:evidence/receipts/R00.json` object itself is the
durable anchor.
