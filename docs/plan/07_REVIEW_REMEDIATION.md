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

Old threads remain open until the corrective PR contains the fix and exact evidence. After merge,
each receives a reference to the correcting commit/receipt and is resolved.

This post-merge closure is deliberate: PR #4 must have zero unresolved actionable threads before
merge, while the inherited PR #1–#3 threads remain open until their reply can name the actual squash
SHA and `evidence/receipts/R00.json`. The receipt binds both populations and their API resolution
state; it does not pretend the inherited threads closed before that evidence existed.

PR #4's first post-merge receipt attempt failed closed on the sdist/dependency-snapshot mismatch.
PR #7 is the only authorized corrective continuation. Its own actionable threads must close before
merge, and the sealed review export covers PRs #1–#4 and #7 without altering the historical states.
