# CO-12 · PR #34 scope guard and local-salvage inventory

**Change order:** CO-12 of `TRIAD-ORIGIN-V7-CHANGE-ORDERS-2026-08-12` (v1.0.0)
**Plane:** governance/tooling only — no runtime, contract, formula, or posture change.
**Posture (invariant):** `DENIED_SAFE_HOLD`; levers `OFF/OFF/OFF/LIVE`.
**Law restated:** nothing inventoried here counts as source, provider, or receipt closure
anywhere. A forensic ref is evidence, never ancestry.

---

## 1. Scope guard (step 1)

The guard core is `tools/verify_pr_scope_guard.py` (+ `tests/tools/test_verify_pr_scope_guard.py`).
It fails a `governance-only` change set that touches formula modules
(`src/triad_origin/structures/`, `src/triad_origin/features.py`, `instrument_math*.py`,
`src/triad_origin/config/`, `contracts/schemas|goldens`), B08 faces
(`contracts/read_faces/`, `src/triad_origin/control/`, the B08 adoption/receipt/evidence
namespaces), or B09 artifacts (`docs/runbooks/`, the B09 adoption/receipt/evidence namespaces).
It reads a `--paths` file or a `--diff-range`, requires the PR class by flag, and refuses
(exit 2) on an unknown class, an empty change set, or an unsafe path.

**CI wiring is CI-owned.** The `.github/CODEOWNERS`-adjacent path law and the workflow stage
that invokes this tool land through the CI owner's lane (`.github/` is CODEOWNER-gated); this
order deliberately does not edit `.github/`. Until that stage lands, the guard is runnable
locally and by reviewers; the PR-blocking effect is `PENDING_CI_OWNER_WIRING`.

## 2. Forensic inventory of the named local refs (step 2)

**Search executed 2026-08-12** in this GitHub clone
(`origin = https://github.com/TriadAgentic/TriadOrigin`, fetch+push), worktree base
`bb500d56a7a81ce027893aacdf5ded48acd11910`.

### Search log (verbatim results)

| Command | Result |
|---|---|
| `git rev-parse --verify 7dbab10^{commit}` | `fatal: Needed a single revision` (exit 128) |
| `git rev-parse --verify ef88414^{commit}` | `fatal: Needed a single revision` (exit 128) |
| `git rev-parse --verify d6795cb^{commit}` | `fatal: Needed a single revision` (exit 128) |
| `git tag --list` | `B00R_RECEIPT_ANCHOR` (only) |
| `git remote -v` | `origin https://github.com/TriadAgentic/TriadOrigin` (fetch/push) |

`git branch -a` (full listing at search time):

```
+ claude/scorecard-origin-validation-mboymp
  main
  wip/c1_sealed_bundle
* wip/co_governance
  wip/f03_f04_swing
+ wip/f09_break
  wip/f10_fvg
+ wip/f13_excursion
  wip/parta_envelope
  worktree-wf_52baa395-984-1
  worktree-wf_52baa395-984-2
  worktree-wf_8b7a9a41-9b1-1
  worktree-wf_8b7a9a41-9b1-2
  worktree-wf_caa04fd5-9a9-1
+ worktree-wf_caa04fd5-9a9-2
  worktree-wf_dd0a5ff4-7c0-1
  worktree-wf_dd0a5ff4-7c0-2
  worktree-wf_ed880a8b-867-1
  worktree-wf_ed880a8b-867-2
  remotes/origin/claude/scorecard-origin-validation-mboymp
  remotes/origin/main
```

No ref named `offline/post-g2-integration` exists in this clone; no object prefixed `7dbab10`,
`ef88414`, or `d6795cb` resolves.

### Dispositions (no third state — RECOVERED{sha256 verified} or UNAVAILABLE{...})

| Ref | Claimed content | Disposition |
|---|---|---|
| `offline/post-g2-integration@7dbab10` | claimed capability-repair integration branch | `UNAVAILABLE_ON_CLONE{declared_ref: 7dbab10, search_log: §2 above}` |
| B08 branch `ef88414` | six read faces (B08 candidate patch) | `UNAVAILABLE_ON_CLONE{declared_ref: ef88414, search_log: §2 above}` |
| Diverged status branch `d6795cb` | status divergence — **forensic-only, never a merge base** | `UNAVAILABLE_ON_CLONE{declared_ref: d6795cb, search_log: §2 above}` |
| Dirty integration worktree | local uncommitted work incl. a `SOURCE_HASHES.sha256` conflict | `UNAVAILABLE_ON_CLONE{not_a_git_object; lives only on the local box}` |
| B09 worktree | conformance projection with the defective counting model | `UNAVAILABLE_ON_CLONE{not_a_git_object; lives only on the local box}` |

These objects exist (if at all) only on the local box. Nothing here recovers them by
invention; recovery is the owner's on-box act below.

## 3. On-box preservation steps (owner-run; nothing here is executable by this session)

Run on the box that holds the local work. **Never** `git reset`, `git stash` (drop-prone),
or blind-merge; every step is read-only inventory first, then explicit copies.

1. **Inventory by hash before touching anything.** For each ref above that resolves on-box:
   `git rev-parse <ref>`, `git cat-file -t <sha>`, `git log --format=fuller -1 <sha>`,
   `git show --stat <sha>`. Record output verbatim into an evidence file.
2. **Export patch candidates, do not merge.** `git format-patch --stdout <base>..<ref> >
   <ref>.patch` (or `git diff <base> <ref>` for a worktree), then `sha256sum` every patch and
   `git patch-id --stable` each; record hashes. Copy the dirty integration worktree wholesale
   (`tar` + `sha256sum`) BEFORE any cleanup.
3. **`7dbab10` (claimed capability repair):** audit commit-by-commit against Formula Repair
   §C.1. Adoption is by clean re-implementation, or cherry-pick only after every invariant and
   attack test passes on a clean B01C branch. Never fast-forward or merge the branch itself.
4. **`ef88414` (B08 six read faces):** hold as a candidate patch for B08 only; replay on the
   valid predecessor against the frozen B08 acceptance profile. It enters no earlier milestone.
5. **`d6795cb` (diverged status):** forensic inventory only. It is **never a merge base** and
   never a source of status truth; status regenerates from the closure route.
6. **`SOURCE_HASHES.sha256` conflict:** resolve only on the clean branch by regeneration from
   actual bytes — never by hand-picking hunks in the dirty worktree.
7. **B09 worktree:** the conformance projection's counting model must be corrected per CO-06
   (no blind summation of the 408 preserved RC1 rows) before any of its content is reused.
8. Store all inventories/patches under an evidence directory outside the repository work tree,
   content-addressed; reference them by hash in any later PR. None of this creates a receipt.

## 4. Acceptance state for this order

| CO-12 acceptance item | State |
|---|---|
| Path-guard live | Tool + tests landed; CI stage `PENDING_CI_OWNER_WIRING` (`.github/` is CODEOWNER-gated) |
| Salvage inventory published | This document (§2–§3) |
| Nothing local counts as closure | Restated in §0 and structurally true — no ref resolves in this clone |
