# 04 · Status — Evidence-Based Reconciled View

_As of 2026-08-11 · Repository facts are separated from runtime facts. No activation is authorized._

## Controlling state

| Item | State | Meaning |
|---|---|---|
| B00R generation 1 | `MERGED_UNVERIFIED_IMMUTABLE` | Mechanically authentic bytes and tag, but not a valid governance root |
| B00R generation 2 | `CORRECTIVE_SOURCE_REQUIRED` | Additive correction prepared from audited start `76b5e4857f80f22f99385810037c5c66289ebd5f`; no source merge, receipt merge, or G2 anchor exists yet |
| B00R terminal result | `BLOCKED` | Only generation 2 may eventually return `PASS_REPOSITORY_SAFE_HOLD` |
| B01C onward | `FROZEN` | May begin only from the receipt merge named by a validated `B00R_RECEIPT_ANCHOR_G2` |
| Activation | `DENIED_SAFE_HOLD` | No venue, paper, or money authority |
| Lever baseline | `OFF / OFF / OFF / LIVE` | Venue environment OFF; venue activation OFF; paper activation OFF; shadow activation LIVE |
| Current deployed runtime | `UNKNOWN_UNTIL_FRESH_ATTESTATION` | Repository status and dated MCP evidence do not certify a running estate |

## Generation-1 historical facts

`docs/governance/B00R_GENERATION_LEDGER.v1.json` is the additive disposition record. These
identities are preserved and must not be edited, repointed, or retro-reviewed into a pass.

| Object | Provider/Git identity | Review state | Disposition |
|---|---|---|---|
| Source PR #31 | head `6033e9e0812d3eb980cfbcb3928006226414c7e4`; merge `5b2a0edc6db99934fe6fbe6bb0fa582bf689a7cc`; merged `2026-08-10T12:37:25Z` | Zero submitted reviews | `MERGED_UNVERIFIED` |
| Receipt PR #32 | head `462152e29d249ab3596f6025e1f4d568efab335c`; merge `76b5e4857f80f22f99385810037c5c66289ebd5f`; merged `2026-08-10T13:05:54Z` | Zero submitted reviews | `MERGED_UNVERIFIED` |
| Generation-1 receipt | `evidence/receipts/B00R.receipt.v3.json`; SHA-256 `f1328ceb29a8730be93f4fd47d295ac96ef514a747385ab500256d6fa52a7cca` | Declares `source_pr=27` while binding PR #31's merge | Historical evidence only |
| Generation-1 anchor | `B00R_RECEIPT_ANCHOR`; tag object `0b2f0579a81e03988cca119ae7e4a0fbf888ad09`; target `76b5e4857f80f22f99385810037c5c66289ebd5f` | Protected after the fact | Never a B01C predecessor |

Generation 1 false-greened because the validator authenticated the bytes of a hand-written
`id:"DECLARATIVE"` provider stub instead of proving those bytes came from GitHub, and because it did
not bind the true source PR identity or require independent pre-merge review.

## Live ruleset and PR #33: useful, but post-hoc

GitHub issue #5 is currently closed. Its closure records later provider evidence; it does not repair
generation 1 and does not close generation 2.

| Fact | Current judgment |
|---|---|
| Main ruleset `20641102` | Real provider object, created `2026-08-10T13:47:11.736Z`, after PRs #31 and #32 merged |
| Rejected administrative canaries | Real post-hoc evidence that future protected-ref operations were refused; no historical effect |
| PR #33 | Open at observed head `0fc4edef83aa60ffe06d1d8356d798e492a6d98e`; zero submitted reviews; evidence-only, not a generation-2 source or receipt PR |
| Generation-2 profile gap | PR #33's capture targets only `main` and permits merge/squash/rebase. G2 requires exact `{main, b00r-ruleset-canary}` scope, empty exclusions, and merge-only operation |
| Old anchor ruleset `20636422` | Protects `B00R_RECEIPT_ANCHOR`; it does not protect the new `B00R_RECEIPT_ANCHOR_G2` identity |

The existing main ruleset may be updated or replaced for future generation-2 merges, but the final
provider capture, external pin, dedicated rejected canary, exact-head CI, and review must all predate
the corrective source merge.

## Generation-2 correction inventory

The correction is additive and uses distinct identities:

| Object | Canonical identity | Current state |
|---|---|---|
| Policy | `docs/control/b00r_policy.v2.json` | Prepared on corrective source branch |
| Generation ledger | `docs/governance/B00R_GENERATION_LEDGER.v1.json` | Prepared; preserves generation 1 |
| Receipt-profile decision | `docs/governance/decisions/DEC-RECEIPT-PROFILE-002.json` | Owner-authenticated object absent; template remains fail-closed |
| Repair decision | `docs/governance/decisions/DEC-B00-REPAIR-002.json` | Owner-authenticated object absent; template remains fail-closed |
| Independent CODEOWNER | `@djordi10` on critical paths | Source policy prepared; live permission and exact-head review still must be proven |
| Evidence root | `evidence/B00R_G2/` | Must be added only in the separate receipt PR |
| Receipt | `evidence/receipts/B00R.g2.receipt.v3.json` | Absent until after the corrective source merge and clean reproduction |
| Physical anchor | `B00R_RECEIPT_ANCHOR_G2` | Absent until after the receipt merge |

Required external pins are
`AUTHORITY_BUNDLE_DECISION_SHA256`, `RECEIPT_PROFILE_G2_DECISION_SHA256`,
`B00R_G2_REPAIR_DECISION_SHA256`, `RECEIPT_G2_TRUST_REGISTRY_SHA256`,
`MAIN_RULESET_EVIDENCE_SHA256`, and `B00R_G2_TAG_RULESET_SHA256`.

## Required closure sequence

1. Preserve every generation-1 byte and tag.
2. Bootstrap the exact `@djordi10` CODEOWNERS bytes onto `main` in a separate reviewed change, then
   refresh the corrective branch so its future merge first parent already contains those bytes.
3. Authenticate the generation-2 owner decisions and externally pin the trust inputs.
4. Install the exact merge-only main-plus-canary ruleset and capture/pin its provider bytes.
5. Run the dedicated canary and obtain the provider rule-suite rejection before source merge.
6. Freeze the final corrective source head; require exact-head CI, independent CODEOWNER approval,
   and resolved threads.
7. Merge the source PR through the enforced ordinary merge path.
8. Reproduce the exact source merge on a clean runner.
9. Create a separate append-only receipt PR containing only `evidence/B00R_G2/**` and
   `evidence/receipts/B00R.g2.receipt.v3.json`.
10. Merge the receipt under the same controls, publish the protected annotated
   `B00R_RECEIPT_ANCHOR_G2`, and run the terminal receipt gate from the exact receipt merge.

Until step 10 passes, the source-mode result remains deliberately non-closing and B01C remains
frozen.

## Historical build artifacts

R00/B00/B00C/B01–B07 source artifacts and receipts remain in the repository for audit and possible
promotion after the new root. Their historical bytes are not deleted or rewritten. Their prior
closure claims remain `INVALIDATED` or `BUILT_ON_INVALID_ANCESTRY` under
`docs/governance/B00_B07_INVALIDATION_MANIFEST.v1.json`.

Offline B01C preparation may continue only as non-authoritative work. It may not create a B01C
source PR, receipt, branch-from-root claim, or promotion before the G2 anchor validates.

## Authority and contract boundaries

TriadOrigin remains the deterministic E02 repository. It consumes E01 facts and must not acquire
E03–E10 forecast/LLM, admission, risk, execution, outcome, P&L, or learning authority. Repository
governance repair does not authorize any runtime wiring.

Published contract bytes remain immutable under the same identity. In particular, the dated MCP
guide's suggestion to add `symbol` and `side/role` to `fill.v1` is rejected. The compatible path is
the already catalogued strict `fill.v3` train with dual-publish, reconciliation, signed
supersession, and consumer cutover outside B00R.

## Dated MCP evidence is not a current gate receipt

The supplied MCP books describe a 2026-08-07 snapshot and a read-mostly operational surface. They
cannot prove GitHub review chronology, branch controls, current runtime state, or B00R closure. No
MCP family activation, keeper edit, server restart, proposal write, or trading-box action belongs in
this correction.

## Immediate next action

Finish only the generation-2 corrective source: owner-authenticate the `002` decisions, install and
capture the merge-only main-plus-canary ruleset, execute the canonical rejected canary, freeze the
head, obtain exact-head CI and independent approval, and merge under that live rule. Then build a
new G2 receipt from that merge. Do not reuse generation-1 evidence and do not open B01C.
