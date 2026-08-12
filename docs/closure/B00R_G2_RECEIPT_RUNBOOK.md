# B00R gen‑2 receipt PR — pre‑staged skeleton + runbook

**Repo:** `TriadAgentic/TriadOrigin` · Safety stays `OFF/OFF/OFF/LIVE` (`activation_result: DENIED_SAFE_HOLD`).
This is the **evidence‑only receipt PR** that follows the PR #34 source merge. It is produced **after** the
source merge (validator chronology), reproduced hermetically, threshold‑signed by the owner, then anchored.
Nothing here may fabricate receipt content or a green — the CI + `b00r_gate` verify it live.

Reserved `main` sequence: **bootstrap merge (#35 ✅) → PR #34 source merge → THIS receipt merge → anchor.**

---

## 0) Preconditions (all must already be true)

- [ ] PR #34 source‑merged to `main` by ordinary merge commit (record `SOURCE_MERGE_SHA`, `SOURCE_MERGE_TREE`, `SOURCE_PR=34`).
- [ ] The 4 authority Variables set + Gate‑1/Gate‑2 green on #34 (see `PR34-SIGN-AND-VARIABLES.md`).
- [ ] The **G2 anchor tag rule** is installed on the provider, captured to `evidence/B00R_G2/tag_ruleset.provider.json` (+ `provider/tag_ruleset.provider.raw.json`), and externally pinned as Variable **`B00R_G2_TAG_RULESET_SHA256`**.

## 1) PR identity (classifier `tools/classify_milestone_pr.py` → role RECEIPT)

- **Branch:** `agent/b00r-g2-receipt` (off merged `main`)
- **Base:** `main` · **Title:** `B00R G2 receipt: evidence + canonical g2 receipt-v3 (clean-runner threshold-signed)`
- **APPEND‑ONLY, status `A` only.** Do **not** modify/delete/rename any file. Never touch gen‑1/historical receipts (`evidence/receipts/B00R.receipt.v3.json`, `B0*.json`, `R00.json`, …).
- **Exactly one receipt** at `evidence/receipts/B00R.g2.receipt.v3.json`. Every other new file lives under `evidence/B00R_G2/`. (The classifier also permits the `DEC-RECEIPT-PROFILE-002` decision path.)

### File inventory to add (mirror of gen‑1 `evidence/B00R/`)

```
evidence/receipts/B00R.g2.receipt.v3.json        # the single receipt (v3 envelope, threshold-signed)
evidence/B00R_G2/evidence_manifest.json          # manifest_kind, schema, entry_count, entries[]
evidence/B00R_G2/spec.json
evidence/B00R_G2/main.ruleset.provider.json
evidence/B00R_G2/main.ruleset.provider.raw.json
evidence/B00R_G2/tag_ruleset.provider.json
evidence/B00R_G2/provider/tag_ruleset.provider.raw.json
evidence/B00R_G2/provider/canary_rejection.json  # fresh rejected dedicated-canary record
evidence/B00R_G2/receipt_trust_registry.g2.v1.json
evidence/B00R_G2/DEC-AUTHORITY-BUNDLE-002.json
evidence/B00R_G2/DEC-RECEIPT-PROFILE-002.json
evidence/B00R_G2/DEC-B00-REPAIR-002.json
evidence/B00R_G2/logs/gates.log
evidence/B00R_G2/logs/pytest_seed0.log
evidence/B00R_G2/logs/pytest_seed1.log
evidence/B00R_G2/results/clean_runner_summary.json
evidence/B00R_G2/results/test_ids_seed0.txt
evidence/B00R_G2/results/test_ids_seed1.txt
```

## 2) Produce the evidence (hermetic clean‑runner, against merged main)

```bash
# a) hermetic reproduction over the source-merge commit — writes logs/results/receipt+manifest
python tools/b00r_clean_runner_capture.py \
  --source-merge  <SOURCE_MERGE_SHA> \
  --clone-root    /tmp/b00r_g2/clone \
  --venv-root     /tmp/b00r_g2/venv \
  --output-root   evidence/B00R_G2 \
  --python        python3

# b) (re)build the manifest over the closed evidence set
python tools/build_evidence_manifest.py --build \
  --root . --closed-root evidence/B00R_G2 --require-tracked \
  --out evidence/B00R_G2/evidence_manifest.json
```

## 3) Receipt‑v3 payload — required values (owner‑set, then threshold‑sign)

```
receipt_kind, schema=triad.evidence_receipt.v3, schema_version
payload.milestone = "B00R"           payload.repair_generation = 2
payload.repository = "TriadAgentic/TriadOrigin"
payload.result / payload.activation_result = "DENIED_SAFE_HOLD"
payload.levers = {venue_environment: OFF, venue_activation: OFF, paper_activation: OFF, shadow_activation: LIVE}
payload.source_pr = 34
payload.final_source_head / source_merge_sha / source_merge_tree / source_merge_time_us  ← from the merge
payload.repair_decision_sha256          = sha256(DEC-B00-REPAIR-002.json)   # matches B00R_G2_REPAIR_DECISION_SHA256
payload.evidence_manifest_sha256        = sha256(evidence/B00R_G2/evidence_manifest.json)
payload.contract_manifest_sha256 / config_bundle_sha256 / test_manifest_sha256 / workflow_sha256 / invalidation_manifest_sha256 / rollback_proof_sha256
payload.evidence_ids[] / evidence_sha256s[]
payload.emitted_at_us / observed_at_us / expires_at_us
payload.signatures = []  → OWNER threshold-signs (receipt-v3); a bare authenticated flag has no authority
```

## 4) Validate locally before opening the PR

```bash
NOW_US="$(date -u +%s)000000"
# manifest + receipt self-consistency
python tools/b00r_clean_runner.py verify \
  --root . --expected-head <RECEIPT_HEAD_SHA> --now-us "$NOW_US"
# tag-ruleset pin
python tools/validate_b00r_tag_ruleset.py \
  --expected-head <RECEIPT_HEAD_SHA> --now-us "$NOW_US" \
  --ruleset evidence/B00R_G2/tag_ruleset.provider.json \
  --ruleset-pin "$B00R_G2_TAG_RULESET_SHA256" \
  --receipt evidence/receipts/B00R.g2.receipt.v3.json --strict-live
# nonterminal receipt authentication (what CI runs on the receipt PR head)
python tools/validate_b_receipt.py --strict --milestone B00R --now-us "$NOW_US" \
  --manifest evidence/B00R_G2/evidence_manifest.json --git-root . \
  --expected-head <RECEIPT_HEAD_SHA> \
  --governance-snapshot docs/governance/rulesets/main.ruleset.provider.json \
  --provider-raw docs/governance/rulesets/main.ruleset.provider.raw.json \
  --provider-pin "$MAIN_RULESET_EVIDENCE_SHA256" --nonterminal-provider-proof \
  evidence/receipts/B00R.g2.receipt.v3.json
```

## 5) Open, review, merge, anchor

1. Push `agent/b00r-g2-receipt`; open the receipt PR (base `main`). CI classifies role **RECEIPT** and runs the tag‑ruleset + nonterminal receipt authentication above.
2. **Independent `APPROVED` review by `@djordi10`** on the exact receipt head; resolve threads.
3. **Ordinary merge commit** (no squash/rebase). Record `RECEIPT_MERGE_SHA`.
4. **Terminal gate (post‑merge, privileged live proof):**
   ```bash
   python tools/b00r_gate.py --mode receipt \
     --expected-head <RECEIPT_MERGE_SHA> --base-sha <SOURCE_MERGE_SHA> \
     --receipt-pr <RECEIPT_PR_NUMBER> \
     --provider-pin "$MAIN_RULESET_EVIDENCE_SHA256" \
     --anchor-ruleset-pin "$B00R_G2_TAG_RULESET_SHA256" \
     --now-us "$(date -u +%s)000000"
   ```
5. Create the protected annotated tag **`B00R_RECEIPT_ANCHOR_G2`** at `RECEIPT_MERGE_SHA`; validate:
   ```bash
   python tools/validate_b00r_anchor.py --expected-head <RECEIPT_MERGE_SHA> \
     --now-us "$(date -u +%s)000000" --receipt-pr <RECEIPT_PR_NUMBER> \
     --ruleset-pin "$B00R_G2_TAG_RULESET_SHA256"
   ```
   B01C stays frozen until this exact `B00R_RECEIPT_ANCHOR_G2` validates.

## Owner‑only (an agent must not do these)

Threshold‑signing the receipt, authoring `DEC-RECEIPT-PROFILE-002`, capturing/attesting the provider tag‑ruleset + fresh canary, the `@djordi10` approval, the merge, and creating the protected tag. An agent may run the clean‑runner/manifest/validators, assemble the branch, and pre‑fill the non‑signature payload fields from real hashes.
