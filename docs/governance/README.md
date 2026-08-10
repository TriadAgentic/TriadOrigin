# B00R governance, trust, and evidence root

This directory now carries two immutable generations of the logical B00R milestone:

- **generation 1** is preserved as `MERGED_UNVERIFIED` historical evidence; and
- **generation 2** is the only correction permitted to create a valid predecessor root.

The authoritative split is `B00R_GENERATION_LEDGER.v1.json`; executable generation-2 policy is
`../control/b00r_policy.v2.json`. Neither object authorizes runtime activation. The invariant state
is `DENIED_SAFE_HOLD`, with venue environment OFF, venue activation OFF, paper activation OFF, and
shadow activation LIVE.

## Generation 1: preserve, never repair in place

Generation 1 consists of source PR #31, receipt PR #32, receipt
`evidence/receipts/B00R.receipt.v3.json`, and annotated tag `B00R_RECEIPT_ANCHOR`. The PRs have no
submitted reviews; the real main ruleset was created after both merges; the receipt sealed a
`"DECLARATIVE"` provider stub and names the wrong source PR. These identities remain byte- and
tag-immutable.

PR #33 contains useful provider and canary evidence created after generation 1. It cannot make a
later control or review predate the earlier merges and is not a generation-2 source/receipt
substitute.

## Generation-2 owner inputs

Engineering artifacts fail closed until the owner/provider acts below are authentic:

| Required object | Canonical repository path | Protected external pin / proof |
|---|---|---|
| Authority-bundle decision | `decisions/DEC-AUTHORITY-BUNDLE-001.json` | `AUTHORITY_BUNDLE_DECISION_SHA256` |
| G2 receipt-profile decision | `decisions/DEC-RECEIPT-PROFILE-002.json` | `RECEIPT_PROFILE_G2_DECISION_SHA256` |
| G2 forward-repair decision | `decisions/DEC-B00-REPAIR-002.json` | `B00R_G2_REPAIR_DECISION_SHA256` |
| G2 public trust registry | `trust/receipt_trust_registry.g2.v1.json` | `RECEIPT_G2_TRUST_REGISTRY_SHA256` |
| Normalized main-ruleset index | `rulesets/main.ruleset.provider.json` | Derived from the raw provider response |
| Raw main-ruleset response | `rulesets/main.ruleset.provider.raw.json` | `MAIN_RULESET_EVIDENCE_SHA256` |
| Independent critical-path owner | `.github/CODEOWNERS` | `@djordi10`, live permission, and exact-head submitted approval |
| G2 tag-ruleset response | `../../evidence/B00R_G2/tag_ruleset.provider.json` | `B00R_G2_TAG_RULESET_SHA256` |

The `002` decisions and G2 trust-registry template are deliberately unauthenticated. The owner must
publish and externally pin a distinct G2 registry whose owner key explicitly scopes all three
required decisions; the generation-1 registry is preserved and cannot authorize `-002`. A flag,
same-PR digest, or arbitrary signature string is not authentication.

The main ruleset must be active before the corrective source merge, target exactly
`refs/heads/main` plus `refs/heads/b00r-ruleset-canary` with no exclusions, expose no bypass, require
the integration-bound strict CI context and independent review controls, and permit only the
ordinary `merge` method. Provider capture, external pin, rejected canary, exact-head CI, and
independent review must all satisfy the chronology enforced by the validators.

GitHub reads CODEOWNERS from the PR base, not from the proposed head. Therefore `@djordi10` must
first be made the exact critical-path owner on `main` through a separate, independently reviewed
bootstrap (or the existing base team must be made real and then perform that bootstrap). The
corrective source must be refreshed from that main commit. The receipt validator requires an
ordinary two-parent merge and byte-compares the first parent's CODEOWNERS to the reviewed source;
the corrective PR cannot self-bootstrap this control.

## Generation-2 canonical receipt layout

B00R generation 2 uses one bare canonical JSON receipt:

- receipt: `evidence/receipts/B00R.g2.receipt.v3.json`;
- closed evidence root: `evidence/B00R_G2/`;
- manifest: `evidence/B00R_G2/evidence_manifest.json`;
- source PR provider record: `evidence/B00R_G2/source_pr.provider.raw.json`;
- approved-review provider record:
  `evidence/B00R_G2/source_pr.approved_review.provider.raw.json`;
- negative canary: `evidence/B00R_G2/provider_negative_canary.v1.json` plus its transcript and
  provider rule-suite response; and
- tag-ruleset capture: `evidence/B00R_G2/tag_ruleset.provider.json`.

The receipt PR is separate and append-only. It may add only `evidence/B00R_G2/**` and
`evidence/receipts/B00R.g2.receipt.v3.json`; it may not alter source, policy, decisions, ruleset
source-phase captures, historical evidence, or generation-1 identities.

`tools/validate_b_receipt.py --strict` binds the actual G2 source PR number, final reviewed head,
merge SHA/tree/time, independent approval, provider ruleset/canary chronology, authority bytes,
closed manifest, audited start, and exact receipt head. CI's nonterminal provider mode is not
closure.

## Physical closure anchor

After the guarded receipt merge, publish one protected annotated tag:

```text
B00R_RECEIPT_ANCHOR_G2
```

Its message profile is `TRIAD-B00R-RECEIPT-ANCHOR-G2-V1` and binds the G2 receipt path and SHA-256.
The tag must point to the exact receipt merge. Its active exact-ref update/deletion/no-bypass
ruleset is committed below `evidence/B00R_G2/`, externally pinned, and freshly revalidated.

The generation-1 anchor is never moved and does not satisfy this requirement. The terminal gate may
return only `PASS_REPOSITORY_SAFE_HOLD`; it does not authorize a venue or deployed runtime.

## Downstream sequence

The only valid future chain begins:

`B00R_RECEIPT_ANCHOR_G2 → B01C receipt → B02C receipt → B03C receipt → B04C receipt → B05C receipt → B06R receipt → B07 receipt`

Every next authoritative source branch starts from the validated predecessor receipt merge/anchor,
never from a source merge, generation 1, PR #33, or an offline preparation branch. B01C remains
frozen until `B00R_RECEIPT_ANCHOR_G2` validates.

See `B00R_EXTERNAL_AUTHORITY_AND_CLEAN_RUNNER_HANDOFF.md` for the complete owner, provider,
clean-runner, receipt, and anchor procedure. Trading/MCP-host work is explicitly out of scope.
