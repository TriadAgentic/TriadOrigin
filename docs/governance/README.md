# B00R governance, trust, and evidence root

This directory contains the **B00R forward-repair** governance machinery. It never arms a venue,
deploys the investigation MCP, or requires access to the trading/MCP host. The invariant posture is
`DENIED_SAFE_HOLD`: venue environment `OFF`, venue activation `OFF`, paper activation `OFF`, and
shadow computation `LIVE`.

The schemas, validators, CI role gate, historical-evidence guard, and closure orchestrator are
engineering artifacts. They deliberately fail closed. The following are authentic external acts
that an implementation agent must not fabricate:

| Required object | Canonical repository path | Protected external pin / provider act |
|---|---|---|
| Authority-bundle decision | `decisions/DEC-AUTHORITY-BUNDLE-001.json` | `AUTHORITY_BUNDLE_DECISION_SHA256` |
| Receipt-profile decision | `decisions/DEC-RECEIPT-PROFILE-001.json` | `RECEIPT_PROFILE_DECISION_SHA256` |
| Forward-repair decision | `decisions/DEC-B00-REPAIR-001.json` | `B00_REPAIR_DECISION_SHA256` |
| Public trust registry | `trust/receipt_trust_registry.v1.json` | `RECEIPT_TRUST_REGISTRY_SHA256` |
| Normalized main-ruleset index | `rulesets/main.ruleset.provider.json` | derived from the raw capture |
| Raw GitHub main-ruleset response | `rulesets/main.ruleset.provider.raw.json` | `MAIN_RULESET_EVIDENCE_SHA256` |
| Concrete independent ownership | `.github/CODEOWNERS` | replace the placeholder with a real handle/team |

The authority decisions must be signed by a valid `AUTHORITY_OWNER` Ed25519 identity in the
externally pinned registry. Receipt closure requires two distinct valid identities: one
`EVIDENCE_PRODUCER` and one `INDEPENDENT_COUNTERSIGNER`. The exact signing preimages are produced by
`triad_origin.governance`; setting `authenticated: true` or typing a signature string is not
authentication. The test/governance toolchain pins `cryptography==50.0.0`; the runtime remains
stdlib-only and DARK.

The owner starts from the `.template.json` files but publishes authenticated objects at the
canonical paths above. A caller-supplied trusted `now_us`, all external digest pins, a clean exact
Git head, and a write-authorized raw provider capture are mandatory. GitHub's ruleset API exposes
the full no-bypass facts only to appropriately authorized callers; do not place an admin token in
PR-controlled CI.

## Canonical receipt layout

B00R uses one bare canonical JSON receipt, not DSSE:

- receipt: `evidence/receipts/B00R.receipt.v3.json`
- closed evidence root: `evidence/B00R/`
- manifest: `evidence/B00R/evidence_manifest.json`
- tag-ruleset capture: `evidence/B00R/tag_ruleset.provider.json`

A receipt PR is append-only. It may add exactly the B00R receipt and files below `evidence/B00R/`;
it may not alter source, historical evidence, another milestone, or an existing file. The evidence
manifest names every regular file below the closed evidence root except itself, and every named
preimage must be tracked at the exact receipt head.

`tools/validate_b_receipt.py --strict` binds the bare receipt, evidence manifest, source merge,
source tree and timestamp, final source head, authority bytes, normalized/raw provider evidence,
audited start, and exact receipt head. A source merge alone is never B00R closure.

After the guarded receipt merge, terminal closure additionally requires the annotated
`B00R_RECEIPT_ANCHOR` tag to point at that exact merge and bind the canonical receipt path/digest.
`evidence/B00R/tag_ruleset.provider.json`, externally pinned as `B00R_TAG_RULESET_SHA256`, must prove
an active exact-tag no-update/no-delete/no-bypass ruleset. The validator proves an annotated tag;
it does **not** implement cryptographic tag-signature verification.

## Historical record and sequence

`B00_B07_INVALIDATION_MANIFEST.v1.json` inventories the old R00/B00/B00C/B01–B07 receipt bytes and
their forward-only disposition. The old v2 documents are self-integrity blobs, not authenticated
closure, and remain byte-immutable.

Downstream work remains ordered:

`B00R anchor → B01C receipt → B02C receipt → B03C receipt → B04C receipt → B05C receipt → B06R receipt → B07 receipt`

Every next source branch starts from the validated predecessor **receipt merge/anchor**, never from
the predecessor source merge. See `B00R_EXTERNAL_AUTHORITY_AND_CLEAN_RUNNER_HANDOFF.md` for the
external ceremony and clean-runner sequence. The old `B00R_ONBOX_OPERATOR_GUIDE.md` is a
supersession notice only; actual trading/MCP-host work is documented separately.
