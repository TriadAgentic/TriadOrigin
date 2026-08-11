# TRIAD B00–BN Closure Marathon Ledger

Ledger state: `EXECUTION_IN_PROGRESS`

Checkpoint: `C0-B00R-CP01`

Recorded: 2026-08-11 Asia/Singapore

Activation: `OFF/OFF/OFF/LIVE`

## Resume instruction

Resume from the first unchecked item under “Next exact actions.” Re-run `git status --short --branch`, compare HEAD and dirty-path inventory with this checkpoint, and stop on mismatch until the delta is classified. Do not skip directly to a downstream milestone.

## Exact working subject

- Repository: `TriadAgentic/TriadOrigin`
- Checkout: `TriadOrigin-c0-b00r`
- Branch: `agent/b00r-generation-2-forward-repair`
- Committed HEAD at baseline: `77a1ff3c7d31ba8b817be750976291c690c87b23`
- Remote tracking branch: `origin/agent/b00r-generation-2-forward-repair`
- Worktree at baseline: dirty, 15 tracked modifications plus untracked C0 schemas/tool/tests
- Provider source PR: #34, draft at the recorded baseline
- Runtime evidence: `NOT_ATTESTED`

## Truth snapshot CP01

The first default-runner command was:

`python -m pytest -q`

Result: `UNAVAILABLE_RUNNER`; the default Python lacked pytest. This is not a source failure.

A diagnostic runner was then used:

- Python: 3.12.13, not receipt-grade Python 3.11
- Dependencies: exact versions listed by `constraints/ci.txt`
- Command: `PYTHONHASHSEED=0 PYTHONPATH=src <diagnostic-python> -m pytest -p no:cacheprovider -q`
- Status: diagnostic only; never usable as exact closure evidence

Observed root failures:

| ID | Root cause | Effect | Owner |
|---|---|---|---|
| CP01-F01 | `b00r_policy.v2.json` changed while `DEC-B00-REPAIR-002.template.json` retained the old policy digest | Two B00R authority/integrity tests failed | B00R G2 |
| CP01-F02 | C0 schemas/tool/tests existed but canonical `closure_semantics.v1.json` was absent | 12 dependent setup errors | C0 |
| CP01-F03 | Canonical `closure_status.v1.json` was absent | Two dependent setup errors | C0 |
| CP01-F04 | Legacy crosswalk test demanded alias rejection but validator did not track duplicate current identities | Attack could not fail for the intended named invariant | C0 |

This is the useful surgical baseline: three missing/rebinding causes created the visible 3 failures and 14 errors. The rest of the diagnostic suite passed.

## Changes after truth snapshot

- Added canonical C0 semantics and status instances with recomputed envelope, scope, and composite-identity digests.
- Bound B00R policy to the exact canonical B00R G2 scope digest.
- Rebound `DEC-B00-REPAIR-002.template.json` to the updated policy digest.
- Added duplicate-current-identity rejection to the legacy crosswalk validator.
- Corrected the crosswalk so historical B00, B00R generation 1, and current repair identities remain distinct and testable.
- Added this closure master and marathon ledger.

No deployment, restart, runtime call, MCP-family enablement, arming, order action, venue mutation, or activation change was made.

## Tests after repair

Targeted command covered:

- all `tests/tools/test_closure_control.py` attacks;
- B00R policy/generation ledger binding;
- additive G2 authority and trust-registry path.

Targeted result: `PASS` under the diagnostic Python 3.12 runner.

The first post-repair dual-seed rerun was deterministic but not green: both seeds failed only the closure-document source-prefix parity check. The path grant is now represented as two exact allowed paths across policy, classifier, and packaged governance constants. The targeted parity, generation-2 policy, and C0 control suites pass after that correction. A fresh complete dual-seed run remains required; this checkpoint does not claim cumulative green.

Deterministic gates currently passing under the diagnostic runner: 51 source pins, 11 immutable historical receipts, 148 manifest artifacts, contract-manifest schema, DARK capability scan, all 24 E2E stages, the 1,250-row build ledger, and the 1,250-task/2,383-edge combined DAG.

Receipt-grade status remains `BLOCKED` until exact Python 3.11, full dual-seed execution, deterministic artifact checks, provider exact-head CI, authenticated authority pins, and independent review complete.

## Acceptance checks still required for C0/B00R source readiness

- [ ] Exact Python 3.11 pinned environment available.
- [ ] Full seed-0 suite passes with no cache provider.
- [ ] Full seed-1 suite passes with identical collected test IDs.
- [ ] Source-hash inventory regenerated and verified.
- [ ] Historical evidence immutability passes.
- [ ] Contract manifest and schema pass.
- [ ] Reproducible sdist/wheel and installed-wheel smoke pass.
- [ ] DARK forbidden-capability scan passes.
- [ ] 24-stage E2E, build ledger, and combined DAG pass.
- [ ] Closure master/ledger paths accepted by the source-scope classifier.
- [ ] One final source head is pushed to PR #34.
- [ ] Exact-head provider CI passes deterministic stages.
- [ ] G2 external authority pins are materialized and authenticated.
- [ ] Main/tag rulesets and rejection canary are captured and verified.
- [ ] Independent reviewer approves exact source head and threads are resolved.
- [ ] Source merge is hermetically reproduced.
- [ ] Separate evidence-only receipt PR passes and receives independent review.
- [ ] Protected G2 anchor exists and terminal gate passes.

## Next exact actions

1. Update the B00R source-path policy for these governed closure documents and rebind the policy digest.
2. Regenerate and verify `SOURCE_HASHES.sha256` using the repository tool.
3. Run the complete seed-0 and seed-1 diagnostic suites and compare collections.
4. Run every deterministic local CI command in workflow order; record command, result, and exact failure.
5. Inspect the final diff for out-of-scope formula/runtime changes and secret patterns.
6. Establish a Python 3.11 receipt-grade runner or leave local evidence explicitly diagnostic.
7. Push only the classified C0/B00R source patch to the existing PR branch; do not create a downstream receipt or merge.
8. Read exact-head provider results and update this ledger before any further repair.

## Stop conditions

Stop and re-baseline on unexpected branch movement, provider head mismatch, unclassified dirty bytes, secret material, formula/runtime files entering the B00R diff, required test skip, unavailable P0/P1 evidence, reviewer non-independence, or any requested activation/runtime side effect outside the authorization boundary.
