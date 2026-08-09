# R00 Receipt Supersession — field-for-field mapping into `evidence_receipt.v2`

_B00C disposition (register row A3). Status: sealed with the build session's deterministic
self-integrity signature; **operator countersignature requested** — this supersession is a
governance record, not a gate pass. Nothing here arms anything; the controlling activation
result remains `DENIED_SAFE_HOLD`._

## Why a supersession

The R00 post-merge receipt ceremony (`docs/plan/milestone_receipt.schema.json` +
`tools/validate_milestone_receipt.py`) requires live GitHub GraphQL/REST evidence exports
(review-thread snapshots, CI log hashes, API export digests) captured at seal time on the
`evidence/r00-receipt` branch. That ceremony was designed under RC1 and was never executed; the
session environment has no authenticated GraphQL export surface, and re-running it now would
fabricate "at seal time" evidence for a merge that happened earlier. The reconciled master plan
(§9.4 receipt law) requires the R00 ceremony be **resolved** — sealed under its existing law or
superseded by a signed mapping of every field and invariant into receipt v2. This document is
that mapping. The RC1-era validator and schema stay in-tree, byte-unchanged, as the historical
law of record.

## Field-for-field mapping

Every required field of the R00 receipt schema maps to an `evidence_receipt.v2` field or a
named evidence item in `evidence/receipts/R00.json`:

| R00 receipt field | v2 home | Disposition |
|---|---|---|
| `schema`, `receipt_id`, `milestone_id` | `schema`/`schema_version`, `payload.receipt_id`, `payload.scope.milestone` | Direct. |
| `scope`, `scope_sha256` | `payload.scope` (repository + milestone + merged SHA) | Scope is the frozen R00-era tree; its digest is the evidence item `r00-state-fixture-digest`. |
| `authority_basis` (status/digest/canonical/inventory_ref) | `payload.evidence_ids` + `payload.producer_digests` | The R00 authority inventory (`06_RC2_SOURCE_INVENTORY.md`) is frozen byte-exact in `tests/fixtures/r00_state/` and digest-bound below. |
| `base_sha`, `head_sha`, `merge_sha` | `build_commit` + evidence item | Pinned: implementation merge `241b301d1144e3e2a0a15f4bfe9ffef5b51068ed`, base `69dfd7245fb462992f17e4af06e6746ac2f9d2f0`, head `b66a95ca84b8660e26c6ff12b3af73cb32aebc04`, tree `049c9186b34ded7ad664499249d733af57931fd1` (the values the validator pins). |
| `toolchain` | evidence item `toolchain-ci-python311` | CI runner facts live in the recorded workflow runs. |
| `evidence_files`, `artifacts`, `manifests` | evidence item `r00-state-fixture-95-files` | The R00-era contract tree + manifests (91 artifacts, RC1 manifest pin `a4184b29…`) are frozen from git `0012e89` into `tests/fixtures/r00_state/` and regression-tested by `tests/test_milestone_receipt_schema.py`. |
| `ci` (run/conclusion/log digests) | evidence item `ci-runs-recorded` | The gate command set runs in CI on every PR; historical run IDs are recorded in PR history (#1–#7). The R00-specific log-hash export was never captured — recorded here as **absent evidence**, not reconstructed. |
| `tests` | evidence item `pytest-seed0-seed1` | The dual-seed falsification suite + exact collection identity run on every merge; `tools/collect_test_ids.py` is unchanged. |
| `deferred_evidence` (branch-ruleset→B00, formula/parameter-evidence→B03, replay-evidence→B02) | register rows A4, C1–C3; status addendum | Deferrals carried forward: branch ruleset remains OPEN (A4); replay evidence landed at B02 (PR #10); formula/parameter evidence lands B03+ under the reconciled plan. |
| `negative_capability` | evidence item `capability-gate` | `tools/verify_no_forbidden_capabilities.py` runs in CI on every merge, byte-unchanged in intent, extended honestly since. |
| `review` (threads/reviewer/api export) | evidence item `review-threads-inherited` | The 14 inherited + 6 PR-4 thread IDs and reviewer identities are pinned in the validator source (byte-unchanged). The live GraphQL export was never captured — **absent evidence**, named. |
| `merge_control` | evidence item `merge-control-pr7` | PR #7 (`R00_RECEIPT_PR`) merged under the working guarded-merge practice; the ruleset gap is register row A4. |
| `post_merge` (fresh-main reproduction) | the B-series receipt law | Post-merge reproduction against the exact merged SHA is now the standing B-series law (master plan §9.3); executed for B00/B01/B02 and forward. |
| `supersession` | this document | `supersedes_receipt_id: null` (no prior sealed R00 receipt exists); reason: ceremony infeasible without fabricating at-seal evidence. |
| `rollback` | repository history | Rollback strategy: git revert of the R00 merge; no rollback receipt was needed. |
| `status` | `payload.result` | `PASS` **for the supersession disposition itself** — the underlying R00 ceremony is recorded `NOT_EXECUTED`; absent evidence stays absent. |

## Invariants carried forward

The R00 validator's behavioral invariants are not waived; each has a standing home:

1. **Required command set** — the eight R00 commands are a subset of the current standing gate
   (`CLAUDE.md`), which adds `e2e_audit.py` and `build_ledger.py --verify`.
2. **Exact-head CI binding** — the CI workflow still binds checks to the exact event head.
3. **Reviewer independence** — receipt v2's semantic validator refuses `builder == reviewer`.
4. **No self-reported acceptance** — receipts bind CI run IDs and merged SHAs, never workbook
   colour or self-reported counts.
5. **Frozen R00 state** — `tests/fixtures/r00_state/` (95 files, extracted from git `0012e89`)
   keeps the R00-era artifacts regression-testable without letting later bundles mutate the
   historical claim.

## Signature

Sealed by `evidence/receipts/R00.json` (self-integrity signature over the canonical payload).
Operator countersignature line (to be added by the operator at answer time):

```
COUNTERSIGNED: ________________  date: ____________
```
