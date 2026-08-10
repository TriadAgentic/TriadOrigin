# B10 · Terminal State — the lawful exit-3 seal (E31)

_TriadOrigin E02-V7. HEAD `fe8d106`. Frozen audit runner:
`audit_package/triad_origin_b01_b10_audit.py` v1.2.0, SHA-256
`12c8896479b902165fa2c6d3e7565ea8402b49fcfe2d044f6fd69153926d35a2` (untracked, provenance-pinned in
`docs/plan/AUDIT_RUNNER_PROVENANCE.md`; register rows E31/E33)._

## The claim

**The runner's full-PASS `exit 0` (`PASS_REPOSITORY_SAFE_HOLD`) is STRUCTURALLY UNREACHABLE by any
repository change.** The honest, reachable terminal of the B10 seal is **exit `3`
`BLOCKED_INCOMPLETE`** — every reachable hard gate green, and the per-milestone work-package (WP)
checks `NOT_RUN` because the check-evidence index is absent (and cannot lawfully be made present).

## Why — the self-referential git-hash fixed point (exact runner mechanics)

The runner scores per-milestone work packages `WP-B01C-01 … WP-B09-09` (`MILESTONE_WORK_PACKAGES`,
runner L161-169). Each WP is assessed only through a **check-evidence index**
(`validate_check_evidence_index`, runner L2454) whose validity requires, simultaneously:

1. `data["subject_sha"] == subject_sha` — the index's declared subject equals the **audited exact
   head** (L2476-2477).
2. The index names an **authentication receipt** preimage whose `payload["build_commit"] ==
   subject_sha` (L2507-2508 — "does not bind audited exact head").
3. The index must be **receipt-bound**: the auth receipt's own `evidence[]` rows must carry a row
   whose `path == <the index's repo-relative path>` **and** whose `sha256 == sha256_file(<the
   index>)` (L2515+, the `bound = any(...)` clause).

Conditions (1)+(2)+(3) require a commit whose head hash equals a value **recorded inside files that
commit contains** (the index's `subject_sha`, the auth receipt's `build_commit`, and the index's own
content hash bound into the receipt). Writing the index/receipt mutates the tree and therefore the
head, so the recorded `subject_sha`/`build_commit` can never equal the head that already contains
them — **a commit cannot contain its own hash.** The index is a fixed point of the git object graph;
no repository change closes it.

## What the reachable terminal actually is

With the check-evidence index **absent** (the only lawful state), `validate_check_evidence_index`
returns early — `[f"check evidence index unavailable at {path}"]` (L2462) — so every WP check is
`NOT_RUN` (`NOT_RUN ∈ INCOMPLETE_OUTCOMES`, L84/88). That drives:

- per-milestone `hard_gate_result = BLOCKED`, `status = "BLOCKED_INCOMPLETE"` (runner L3196-3201);
- overall `hard_gate_result = BLOCKED`, `status = "BLOCKED_INCOMPLETE"` (L3213-3218);
- `determine_exit` → `EXIT_INCOMPLETE = 3` (L77, the `if score["hard_gate_result"] == BLOCKED`
  branch);
- `activation_result = "DENIED_SAFE_HOLD"` (L90), `estate_certification_eligible = False`.

The runner's own acceptance test pins this: `assert score["status"] == "BLOCKED_INCOMPLETE"`
(runner L4222). `SUCCESS_STATUS = "PASS_REPOSITORY_SAFE_HOLD"` (L91) requires **zero** incomplete WP
checks — unreachable while the index is a fixed point. **Fail-closed:** no WP is ever claimed PASS
while the index is absent; a fabricated index that mismatched `subject_sha`/`build_commit`/binding
would be an *issue* (harder-failing), never a pass — so the index-absent NOT_RUN path is both the
maximum reachable AND the only honest one.

## Every REACHABLE hard gate is green (recorded in E30, verified across B00→B09)

- The ten CLAUDE.md gate commands (both `PYTHONHASHSEED` values of pytest, `collect_test_ids`,
  `verify_manifest`, `validate_contract_manifest`, `verify_reproducible_build`, `test_wheel_install`,
  `verify_no_forbidden_capabilities`, `e2e_audit` (27 stages), `build_ledger --verify`,
  `validate_combined_dag`).
- CI 18 source + 3 receipt step names; the strict receipt chain (`validate_b_receipt --all --strict`,
  exit 0 on the all-v2 tree); the spec/control count reconciliation; the tracked secret scan
  (`scan_secrets --tracked --fail-on-hit` → 0 hits over 464 files).

## The handoff line

> **`DENIED_SAFE_HOLD` unless separate estate gates exist.**

The seal's honest terminal is exit-3 `BLOCKED_INCOMPLETE` with every reachable hard gate green and
the WP checks `NOT_RUN` (index-absent fixed point). No in-repo change closes it (E31). The operator
either **accepts exit-3** as the reachable maximum, or authorizes a runner-amendment ceremony (a new
runner version + SHA re-pin in `AUDIT_RUNNER_PROVENANCE.md`) that breaks the fixed point. Activation,
the same-digest TESTNET certificate, production-risk signing, key minting (issue #5), and branch
governance are the operator/estate G-1..G9 gates — none is an agent act, and all remain
`DENIED_SAFE_HOLD`.
