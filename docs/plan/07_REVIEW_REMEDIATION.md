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
`3741593887`; this reviewed plan therefore names it instead of erasing history. Every observed PR #7
root must enter the controlled set, be fixed/replied/resolved before merge, and receive an
authenticated post-merge closure reply citing the corrective squash and receipt path. The sealer
compares two complete live GraphQL snapshots against every persisted PR #1–#4/#7 root, resolution,
and selected reply; a reviewed immutable root manifest also pins every original finding's text,
author, path, IDs, and URL. Incomplete pagination, edited roots, or any mismatch fails closed. The
sealer twice fetches the complete PR #7 top-level review inventory and rejects every current
`CHANGES_REQUESTED`, every review after the selected pre-merge acceptance, and every post-merge
review not carried solely by an authenticated canonical closure reply. The final exact-head Codex
acceptance must itself have zero findings. PR #7 must not merge until the service's authentic clean
artifact is observed; a 👍-only result requires a separately reviewed exact-head reaction binding
rather than an invented empty review object. The sealed export preserves historical states and does
not relabel PR #4 as the accepted corrective merge.
