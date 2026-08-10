# B00R on-box operator guide + offline task list

**Milestone:** B00R (forward-repair governance/receipt/evidence root)
**Repository:** `TriadAgentic/TriadOrigin`
**Audited start:** `main@e1f76b845bc1251c156d37a662f87fc468397fb0`
**Draft engineering PR:** #27 (`claude/triad-origin-implementation-da6ah9`)
**Safety invariant (never changes):** `activation_result=DENIED_SAFE_HOLD`, `venue_environment=OFF /
venue_activation=OFF / paper_activation=OFF / shadow_activation=LIVE`
**Only permitted terminal result:** `PASS_REPOSITORY_SAFE_HOLD`

> This guide separates **agent-built engineering** (done, green, in PR #27) from **owner-only acts**
> that an agent cannot authentically perform and must never fake. Every owner act below is a hard
> gate: until it exists, the matching validator fail-closes to `BLOCKED`/`UNAVAILABLE`, never `PASS`.
> Nothing here arms, activates, or ratifies anything.

---

## 0. Status at a glance

| Layer | State | Proof command |
|---|---|---|
| Deterministic engineering (ledger, DAG, source hashes, contract manifest, receipt-v3 code, tools, tests, e2e stage, CI role gate) | **BUILT + GREEN** | `python tools/b00r_gate.py --mode source` (deterministic rows `PASS`) |
| Owner-gated closure (decisions, trust pins, ruleset, receipt-v3, anchor) | **BLOCKED — owner required** | same command (owner rows `BLOCKED`) |

Run it yourself on the box:

```bash
python tools/b00r_gate.py --mode source
# deterministic gates -> PASS ; authority_root / governance_snapshot / receipt_v3_closure -> BLOCKED
```

The rest of this document is the exact sequence to turn every `BLOCKED` into `PASS`.

---

## 1. Roles (identity separation is itself a gate)

You must staff these as **distinct GitHub / key identities** — any collision is a stop condition:

- **Authority owner** — signs the three `DEC-*` decisions and the trust registry.
- **Implementer** — authored PR #27; may not be the sole reviewer/resolver/custodian/signer.
- **Independent reviewer** — approves the exact final source/receipt heads (not the author).
- **Repository administrator** — installs the ruleset, captures provider evidence, sets protected pins.
- **Evidence custodian** — reproduces from a fresh clone, publishes committed preimages.
- **Receipt signers** — `EVIDENCE_PRODUCER` + `INDEPENDENT_COUNTERSIGNER` (two distinct keys).

---

## 2. Owner act A — authenticate the three root decisions

The decision **templates** carry the real subject digests already and ship `authenticated:false`:

- `docs/governance/decisions/DEC-AUTHORITY-BUNDLE-001.template.json`
- `docs/governance/decisions/DEC-RECEIPT-PROFILE-001.template.json`
- `docs/governance/decisions/DEC-B00-REPAIR-001.template.json`

For each, the owner:

1. Reviews the `subject_sha256s` and `scope` (they pin the exact RC bytes / schema bytes / audited start).
2. Decides the profile (`DEC-RECEIPT-PROFILE-001`): the default proposal is **Ed25519, threshold 2**,
   roles `EVIDENCE_PRODUCER` + `INDEPENDENT_COUNTERSIGNER`, canonicalization
   `triad_origin.canonical.canonical_json`. Amend if you choose a different scheme — then implement
   exactly what you ratify (do not silently substitute).
3. Copies the template to the authenticated name (drop `.template`), sets `"authenticated": true`,
   and appends `signatures` (each `{key_id, signature_hex}`) whose `key_id` resolves in the trust
   registry (Act B) and whose bytes sign the canonical decision payload:

```bash
cp docs/governance/decisions/DEC-B00-REPAIR-001.template.json \
   docs/governance/decisions/DEC-B00-REPAIR-001.json
# edit: authenticated=true ; add verifying signatures ; keep subject_sha256s/scope unchanged
```

`validate_authority_root.py` prefers the authenticated `DEC-*.json` over the template automatically.

---

## 3. Owner act B — publish + externally pin the trust registry

1. Generate the two signer keypairs **off-box** (never commit a private key/seed).
2. Copy `docs/governance/trust/receipt_trust_registry.v1.template.json` to
   `docs/governance/trust/receipt_trust_registry.v1.json`, set `"authenticated": true`, and for each
   key set the real `public_key_hex` (Ed25519, 32 bytes = 64 hex), a valid `not_before_us`/
   `not_after_us` window, `revoked:false`, and a distinct `identity`.
3. **Pin its digest OUTSIDE the tree.** Compute `sha256` of the file and set it as a protected repo/
   environment variable so CI receives it from outside the proposed PR:

```bash
sha256sum docs/governance/trust/receipt_trust_registry.v1.json
# store the hash as protected variable RECEIPT_TRUST_REGISTRY_SHA256
```

Do the same for the three decision files:

```bash
sha256sum docs/governance/decisions/DEC-AUTHORITY-BUNDLE-001.json  # -> AUTHORITY_BUNDLE_DECISION_SHA256
sha256sum docs/governance/decisions/DEC-RECEIPT-PROFILE-001.json   # -> RECEIPT_PROFILE_DECISION_SHA256
sha256sum docs/governance/decisions/DEC-B00-REPAIR-001.json        # -> B00_REPAIR_DECISION_SHA256
```

Verify:

```bash
RECEIPT_TRUST_REGISTRY_SHA256=... AUTHORITY_BUNDLE_DECISION_SHA256=... \
RECEIPT_PROFILE_DECISION_SHA256=... B00_REPAIR_DECISION_SHA256=... \
python tools/validate_authority_root.py --strict
# OK: authority root authenticated and externally pinned
```

The pins are **public hashes**. Private keys, seeds, credentials, and bearer tokens are forbidden
from the repository, logs, and evidence bundle.

---

## 4. Owner act C — install the no-bypass `main` ruleset (issue #5)

Repository admin installs a branch ruleset on `refs/heads/main` proving, via the GitHub rulesets API:

- pull requests required (no direct push);
- exact required status context `CI / test-and-verify`, strict / current-base;
- ≥ 1 independent approval on the current final head (2 for receipts if the profile requires);
- stale approvals dismissed on push / last-push approval required;
- all review conversations resolved;
- force-push and branch deletion blocked;
- **no** administrator/team/app/actor bypass;
- CODEOWNERS review for the critical paths in `.github/CODEOWNERS` (replace the placeholder team with
  a real handle you control, independent of the implementer);
- expected-head merge protection.

Then:

1. Attempt a deliberate noncompliant merge; **keep GitHub's rejection** (do not merge the canary).
2. Capture the provider ruleset detail into `docs/governance/rulesets/main.ruleset.provider.json`
   (from the API, not hand-written), set `"authenticated": true`, fill `ruleset_id` + `effective_at_us`.
3. Verify:

```bash
python tools/validate_governance_snapshot.py --strict
# OK: governance snapshot proves no-bypass main controls
```

Keep **issue #5 open** until the compliant B00R source merge proves the positive control; close it
then, linking the ruleset + merge evidence.

---

## 5. Owner act D — source merge, fresh-clone reproduction, receipt-v3, anchor

1. **Independent review** PR #27's exact final head; resolve every actionable thread with evidence
   (author-only resolution is insufficient). Confirm `CI / test-and-verify` is green on that exact head.
2. **Guarded merge** under the ruleset (expected-head, no bypass). Record the merge commit/tree/time.
3. **Fresh-clone reproduce** the exact merge and rerun the full gate under both hash seeds:

```bash
git clone <repo> fresh && cd fresh && git rev-parse HEAD   # == the merge commit
python -m pip install -e '.[test]'
PYTHONHASHSEED=0 python -m pytest -p no:cacheprovider
PYTHONHASHSEED=1 python -m pytest -p no:cacheprovider
python tools/b00r_gate.py --mode source
```

4. **Build the closed evidence manifest** and verify every preimage before signing:

```bash
python tools/build_evidence_manifest.py --build evidence/B00R/spec.json --root . \
  --out evidence/B00R/evidence_manifest.json
python tools/build_evidence_manifest.py --verify evidence/B00R/evidence_manifest.json --root .
```

5. **Assemble + threshold-sign** `evidence/receipts/B00R.receipt.v3.json` (schema
   `triad.evidence_receipt.v3`, `variant:"ROOT"`, `result:"PASS_REPOSITORY_SAFE_HOLD"`,
   `levers` OFF/OFF/OFF/LIVE, real hex digests, `repair_decision_sha256` +
   `invalidation_manifest_sha256` + `audited_start_sha`, chronology `source_merge < observed <=
   emitted`). The bytes signed are the payload with `signatures` removed —
   `triad_origin.governance.canonical_receipt_signing_bytes`. Sign with the two Ed25519 keys; append
   `{key_id, signature_hex}` per signer. Validate:

```bash
python tools/validate_b_receipt.py --strict --milestone B00R \
  --trust docs/governance/trust/receipt_trust_registry.v1.json \
  evidence/receipts/B00R.receipt.v3.json
# OK: B00R receipt-v3 PASS_REPOSITORY_SAFE_HOLD
```

6. **Receipt-only PR** from the exact source merge; diff limited to `evidence/B00R/**` +
   `evidence/receipts/B00R.dsse.json` (the role gate rejects mixed content). Independent review + the
   receipt-mode CI on the exact head; guarded merge.
7. **Closure anchor** `B00R_RECEIPT_ANCHOR`: bind the immutable receipt bytes to the receipt PR final
   head + provider merge facts (a protected signed annotated tag under a no-update/no-delete tag
   ruleset, or the ratified two-signer equivalent). No self-reference; no third "receipt-for-the-receipt".

When all rows read green:

```bash
python tools/b00r_gate.py --mode receipt --expected-head <receipt-merge-sha>
# B00R result: PASS_REPOSITORY_SAFE_HOLD
```

---

## 6. Historical record (do not touch)

`docs/governance/B00_B07_INVALIDATION_MANIFEST.v1.json` inventories the historical
R00/B00/B00C/B01–B07 receipts with immutable SHA-256 and forward-only dispositions. They stay
byte-unchanged. Do not edit any historical receipt into a retroactive pass; supersede forward only.

---

## 7. Offline-preparation task list (permitted before the B00R anchor validates)

Per the pack, B01C–B07 may be **prepared offline** (analysis, patch design, disposable local testing)
but **no downstream branch may become authoritative, merge, or issue evidence** until the exact
predecessor receipt anchor exists. Sequence is strict: each milestone branches from the validated
**receipt** merge commit of its predecessor, never merely the source merge.

| Order | Milestone | Offline prep that is safe now | Blocked until |
|---:|---|---|---|
| 1 | **B00R** | Done (PR #27). | — |
| 2 | B01C | Draft the contracts/bindings defect fixes against the plan; local tests. | valid `B00R_RECEIPT_ANCHOR` |
| 3 | B02C | Draft kernel / E01-boundary fixes. | valid B01C anchor |
| 4 | B03C | Draft F02–F13 causal-feature/structure fixes. | valid B02C anchor |
| 5 | B04C | Draft lifecycle/flow fixes. | valid B03C anchor |
| 6 | B05C | Draft four-plane substrate; surface the B05 owner decisions (TESTNET, maker/taker, ADR-005) as blockers. | valid B04C anchor + B05 entry decisions |
| 7 | B06R | Review/port plan for capsules/candidates (capsule-semantics decision). | valid B05C anchor |
| 8 | B07 | Review/port plan for the forward rebuild (activation-identity decision). | valid B06R anchor |

Global owner decisions that must be authenticated before their consuming milestone can close:
`DEC-TESTNET-001`, `DEC-MAKER-TAKER-001`, `DEC-ADR005-001` (B05C); `DEC-CAPSULE-SEMANTICS-001`
(B06R); `DEC-ACTIVATION-IDENTITY-001` (B07). Absent → the listed fail-closed default, never a
convenient substitute.

---

## 8. Stop conditions (halt the affected milestone immediately)

- `main` or the planned predecessor anchor changes unexpectedly;
- a required decision/pin is missing, self-sourced, expired, revoked, or differently scoped;
- the ruleset is inactive, wrong-branch, bypassable, or effective only after merge;
- a mandatory CI step is skipped/neutral/cancelled/wrong-head;
- a P0/P1 remains, a thread is unresolved, or approval is stale/not independent;
- a receipt lacks committed preimages, external authentication, exact ancestry, or valid chronology;
- source and evidence are mixed in one PR;
- historical evidence is edited rather than additively dispositioned;
- the DARK scan finds venue/credential/money/order capability;
- any effective control differs from OFF/OFF/OFF/LIVE.

On stop: preserve evidence, mark `BLOCKED`/`FAIL`, keep safe hold, correct **forward** with a new
immutable head, and rerun every invalidated control.
