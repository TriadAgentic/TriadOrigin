# B10 · Terminal-receipt scaffold — UNSIGNED, operator-completed

_TriadOrigin E02-V7. HEAD `fe8d106`. Builder: `tools/build_receipt_v3.py` (emits an UNSIGNED
`triad.evidence_receipt.v3` draft + DSSE PAE signing preimages; signing is external — E32/E45)._

## Why this is a scaffold, not a full draft

A self-check-passing B10 terminal receipt **cannot be produced by an agent**. `build_receipt_v3.py`
is fail-closed and requires four classes of input that are external / operator-gated and **do not
exist on disk** at this HEAD:

1. **A predecessor receipt chain.** For any non-B01 milestone the config requires
   `predecessor: {id, sha256}` bound to the *prior* milestone's sealed receipt. `evidence/receipts/`
   holds only `B00…B07` — **the B08 and B09 evidence-only receipts are operator-gated post-merge PRs
   that have not landed** (register E42 / A3 cadence). So the B10 predecessor SHA is not yet
   computable.
2. **The external trust-registry SHA-256 pin** (`--trust-registry-sha256`) — a
   `triad.receipt_trust_registry.v1` the operator produces (`tools/build_trust_registry.py`) and
   holds off-tree (E32/E45.6).
3. **The ratified DECISION-RECEIPT-PROFILE-001 profile-decision file** (`RECEIPT_PROFILE_DECISION`
   evidence role) whose bytes must equal the runner's `SUPPORTED_RECEIPT_PROFILE_DECISION` and whose
   SHA-256 is pinned via `--profile-decision-sha256` — an operator artifact (E45.6). An agent must
   not fabricate a ratified decision receipt.
4. **A merged B10 head.** `build_commit`/`merge_commit`/`source_head_sha` + a green `ci_runs` bound
   to that head require the **B10 source PR to be merged** (not done — this is the seal ceremony,
   E45.7), plus committed gate-reproduction / test-collection / rollback-proof preimages against
   merged `main`.

The builder proves its own strictness: run against the scaffold config it refuses in canonical order
(`REFUSED UNKNOWN_CONFIG_KEY` on the human marker key; then `REFUSED BAD_PR_NUMBER` on a placeholder
`source_pr`; and so on down the chain) — every `__OPERATOR_FILLS__` value must be a real
operator/estate input. This is the intended fail-closed behaviour, not a defect.

## What the operator completes (the exact command)

1. Merge the B10 source PR green; reproduce the 14-command gate against the merged `main` hash.
2. Fill a clean config (copy `B10_receipt_config.DRAFT.json`, **remove the `__UNSIGNED_DRAFT__`
   marker key**, and replace every `__OPERATOR_FILLS__` with the real value): the merged head
   (`build_commit == merge_commit`), `source_head_sha`, the green `ci_runs` row, the `B09`
   predecessor `{id, sha256}`, the canonical int64 timestamps, and the eight evidence-role preimages
   (incl. the ratified profile-decision file and committed gate/test/rollback artifacts).
3. Run the builder **outside the repository** (tree-mutation law), with the two external SHA pins:

   ```bash
   python tools/build_receipt_v3.py \
     --config <clean-b10-config>.json \
     --repo /path/to/TriadOrigin \
     --trust-registry-sha256 <64-hex of the external triad.receipt_trust_registry.v1> \
     --profile-decision-sha256 <64-hex of the ratified DECISION-RECEIPT-PROFILE-001 file> \
     --out /path/OUTSIDE/repo/B10_terminal_receipt.UNSIGNED.json \
     --self-check
   ```

   This emits the UNSIGNED `triad.evidence_receipt.v3` draft (`receipt_kind: TERMINAL_REPOSITORY`,
   `scope: {repository: triadagentic/triadorigin, milestone: B10, execution_plane: OFF, environment:
   REPOSITORY, authority: REPOSITORY_ONLY}`, `governance: {branch_rules_enforced: true, bypass_used:
   false}` — all fixed by the builder for B10) + its DSSE PAE signing preimages.

4. **Sign in ceremony** (E32/E45.2): mint the Ed25519 PRODUCER · COUNTERSIGNER keys (≥2 distinct
   signers per `RECEIPT_PROFILE_DECISION`), sign the PAE preimages, and land the detached signed
   terminal receipt as the B10 evidence-only receipt PR. Then tag + local checkpoint referencing it
   (E45.7). **Keep no private key material in the repository.**

## Files in this repository (agent-delivered)

- `docs/reports/B10_receipt_config.DRAFT.json` — the human-readable config scaffold (UNSIGNED,
  `__OPERATOR_FILLS__` placeholders).
- This scaffold doc.

No signed receipt, private key, trust registry, or profile-decision file is shipped in-repo — all
are operator/estate ceremony artifacts (register E45). The controlling result stays
`DENIED_SAFE_HOLD`.
