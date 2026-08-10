# docs/governance — B00R governance, trust, and evidence root (fail-closed)

This directory holds the **B00R forward-repair** governance artifacts. Everything here is
**data**; nothing here arms, activates, or ratifies anything. The safety posture is invariant:
`activation_result=DENIED_SAFE_HOLD`, `venue_environment=OFF / venue_activation=OFF /
paper_activation=OFF / shadow_activation=LIVE`.

## What is agent-built vs owner-required

The engineering machinery — schemas, validators (`triad_origin.governance`, `tools/*`), the
invalidation manifest, the policy, and the tests — is complete and **fails closed**. The following
are **owner acts** that an agent cannot authentically perform and must never fake; until they are
supplied by the account owner, every dependent hard gate reports `BLOCKED`/`UNAVAILABLE`, never
`PASS`:

| Artifact | Owner action required | Default while absent |
|---|---|---|
| `decisions/DEC-AUTHORITY-BUNDLE-001.template.json` | Authenticate (sign) the authority bundle decision | `UNAVAILABLE_AUTHORITY_ROOT` |
| `decisions/DEC-RECEIPT-PROFILE-001.template.json` | Ratify (sign) the receipt-v3 profile proposal | `NO_RECEIPT_MAY_RETURN_PASS` |
| `decisions/DEC-B00-REPAIR-001.template.json` | Authorize (sign) the forward repair root | `B01C_BLOCKED_NO_ROOT` |
| `trust/receipt_trust_registry.v1.template.json` | Publish real public signer keys; pin its digest **outside the tree** | `NO_TRUST_REGISTRY_PINNED` |
| `rulesets/main.ruleset.provider.template.json` | Install the no-bypass `main` ruleset; capture provider-authenticated evidence | `GOVERNANCE_UNAVAILABLE` |
| external pins | Supply `receipt_trust_registry_sha256`, `receipt_profile_decision_sha256`, `authority_bundle_decision_sha256`, `b00_repair_decision_sha256` as protected repo/environment variables | `EXTERNAL_PINS_ABSENT` |

Each template carries `authenticated: false` and empty `signatures`; the validators
(`decision_is_authenticated`, `validate_receipt_v3`, `validate_governance_snapshot`) reject them as
non-authoritative. To ratify a decision the owner replaces the template with an authenticated file
(`.dsse.json` if `DEC-RECEIPT-PROFILE-001` selects DSSE), sets `authenticated: true`, and appends
verifying signatures whose key IDs resolve in the pinned public trust registry.

The decision templates carry **real subject digests** (computed from the vendored RC bytes and the
new schemas) so the owner signs the exact bytes; they are drafts to sign, not fabricated
ratifications.

## The historical record

`B00_B07_INVALIDATION_MANIFEST.v1.json` inventories the historical R00/B00/B00C/B01–B07 receipt
blobs with their immutable SHA-256 and a forward-only disposition (`INVALIDATED`,
`BUILT_ON_INVALID_ANCESTRY`, …). Those receipts are self-integrity-consistent v2 documents but are
**not** authenticated closures. They are preserved byte-unchanged; forward repair proceeds from
B00R.
