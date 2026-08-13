# TRIAD — REVISION RECORD R-03

**Document ID:** `TRIAD-REVISION-RECORD-R-03-2026-08-13`
**Version:** `1.0.0`
**Prepared:** 2026-08-13
**Occasioned by:** TriadLearning PR #462 merged to `main` (`135a2702`); TriadOrigin PR #36 unblocked (`9f52fdf`) and correctly not merged
**Amends:** `TRIAD_REVISION_RECORD_R-02_2026-08-13.md` §3.2 (the sample-size bar)
**Disposition:** `CORRECTION_RECORD / FINDING_REGISTER / NOT_A_RATIFICATION / NO_RUNTIME_CHANGE`
**Posture:** unchanged. `OFF/OFF/OFF/LIVE` · `DENIED_SAFE_HOLD`.

---

## 1 · Correct calls, recorded

Three judgements in the 2026-08-13 report were right and are recorded so they are not re-litigated.

| Call | Assessment |
|---|---|
| **Refused to merge #36** — DRAFT, its own body says *"do not merge on a green button,"* gated on B00R gen-2 root closure, GOV-01 signature, independent review (reviewer ≠ author), and CO-06 semantic closures | **Correct.** *"I will not fabricate the B00R receipt or your signature"* is the lawful refusal. A resolved conflict is not an authorisation. |
| **Fixed 23 ruff findings in own code rather than relaxing the linter** | **Correct**, and worth naming. Relaxing a linter to accommodate new code is the same move as flipping a passing test to accommodate a finding — the LAW-9 failure mode in a different costume. |
| **Refused to create the checkpoint-seal branch unbid** | **Correct.** Standing branch instruction plus a token that cannot push tags. Handing the obligation back is the right disposition. |
| **Resolved `SOURCE_HASHES.sha256` by regenerating, not hand-merging** | **Correct method.** A generated pin file is regenerated from the merged worktree; every hash recomputed read-only; no hand-picked value. `verify_source_hashes.py` OK, 137 hashes, exit 0. |

---

## 2 · `FINDING M-1` — the combined check is not a required status check · **P0 · governance**

### The evidence is in the report's own wording

> *"that's why `mergeable_state` was **unstable**, not branch-protection-blocked."*

GitHub's `mergeable_state` semantics are unambiguous:

```
blocked   = merging is prevented — a REQUIRED status check is failing,
            or a required review is missing
unstable  = mergeable, with a NON-REQUIRED check failing
```

**`unstable` is proof that `lint · typecheck · test · conformance` is not a required status check on `main`.** Had it been required, the state would have read `blocked` and the merge would not have been mechanically possible.

### Why this matters more than the merge itself

The merge was **lawful under the rules currently installed**. The finding is that **the rules are not installed.**

This is exactly the fourth item in the B00R gen-2 root closure — `D-3` / `WO-P`:

> *authenticate the three root decisions, externally pin the trust registry, **install the no-bypass `main` ruleset**, threshold-sign receipt-v3*

**`M-1` is not a new gap. It is `GAP-30` printing.** The absence of the ruleset was previously an abstract governance item on a list; it is now an observed property of the repository, demonstrated by a merge that a ruleset would have blocked.

### Disposition

No action against the merge — it was additive, measurement-only, lint-clean, DARK, with no money-line reach. **The action is to escalate `WO-P` from "governance closure, do it when convenient" to "the thing that makes every other CI claim in this estate meaningful."** Until the ruleset is installed, *"12 gates green"* and *"merged to main"* are independent facts with no causal link between them.

---

## 3 · `FINDING M-2` — a permanently-red check carries zero signal · **P1 · measurement**

> *"main already carries **281 pre-existing ruff errors** that are not mine (33 in `tools/triad_confluence_placebo.py` alone). So CI reads red regardless of my code."*

**A check that is red before your change and red after it cannot tell anyone whether your change was safe.** The signal is not degraded; it is absent. Its information content is exactly zero, and it has been zero for however long those 281 errors have existed.

### This is a defect class the estate has already named twice

| Instance | The broken signal |
|---|---|
| **F15 coverage ratio** (`GAP-06`) | Numerator and denominator share the RPI exclusion, so the ratio reads ~1.0 regardless of true completeness |
| **`get_sim_gap` verdict `HONEST`** | Flagged in Mission Control as *"verdict:HONEST-is-vacuous"* — real_fills 0, so nothing can disagree |
| **`main`'s combined check** *(new)* | Red before and after every change, so nothing can be attributed |

**Three instances of one pattern: a gate that always returns the same answer is not a gate.** The estate is good at catching this in its measurement plane and has not applied the same standard to its own CI.

### Remedy — do not mass-fix 281 errors

That would be a large, risky, unrelated change. The cheap fix restores the signal without touching the debt:

```
1. Baseline the existing 281 into a frozen allowlist
   (ruff's per-file-ignores, or a checked-in baseline file).

2. The check then fails ONLY on NEW findings.
   Signal restored immediately. Debt untouched.

3. RATCHET: the baseline count may never increase on merge.
   This is the estate's OWN existing CI-ratchet law, already applied to
   the param census — "param census count may never increase on merge;
   new detectors ship census-clean." Apply the same rule to lint.

4. Burn the 281 down separately, on its own schedule, at whatever pace.
   Not on the critical path. Not this week.
```

**Note on `tools/triad_confluence_placebo.py` (33 errors).** A placebo is a control instrument. A control instrument carrying a third of the repo's lint debt is worth one look — not because lint errors imply logic errors, but because a null/control tool is exactly the code nobody reads, and a broken control silently invalidates every comparison drawn against it.

---

## 4 · `FINDING M-3` — the checkpoint-seal obligation is now outstanding · **P1 · governance debt**

Merging #462 to `main` triggered the estate checkpoint-seal ceremony: a `checkpoint/2026-08-13-…` branch at fresh `main` across all five core repos, a `CHECKPOINTS.md` row in each, and the annotated tag.

**It was correctly not performed, and it is now owed.** `main` sits at a state that requires a seal and does not have one.

```
Disposition: OPEN OBLIGATION, owner-gated.
  - The TriadLearning side can be sealed by the agent on your word.
  - The tag mirror is an operator step (App tokens cannot push tags).
  - Until sealed, the five repos' main branches are not jointly pinned to a
    named checkpoint, so "fresh main" is not a reproducible reference.

This is not urgent. It IS a debt, and debts of this shape compound: the
longer main advances unsealed, the larger the first seal's diff and the
weaker the guarantee it provides.
```

---

## 5 · CORRECTION to R-02 §3.2 — the fixed 93-trade bar is miscalibrated

### What I published

R-02 §3.2 stated *"93 trades to distinguish 54.4 % from 40 % at 80 % power."* That number is correct **for an observed win rate of exactly 40 %.** It was then mechanized in `sample_size.py` as a fixed `n_total < 93 ⇒ HOLD` gate.

**A fixed 93 is wrong in both directions.**

| Observed WR | `n` required | vs the fixed 93 |
|---:|---:|---|
| 30 % | **31** | 93 holds on evidence that is already adequate |
| 35 % | 50 | holds unnecessarily |
| 38 % | 71 | holds unnecessarily |
| **40 %** | **93** | correct only here |
| 42 % | 126 | **releases on inadequate evidence** |
| 45 % | 220 | **releases badly** |
| 48 % | 476 | **releases very badly** |
| 50 % | 1,007 | **releases on ~9 % of the needed sample** |

The dangerous half is the bottom. **If the live win rate comes back at 45 %, a fixed-93 gate declares the evidence adequate at 42 % of the required sample and green-lights a 21-day window on an effect that has not been demonstrated.** That is precisely the failure the gate exists to prevent, inverted.

### The fix — compute against the observation, not a constant

```python
def n_required(p_frozen: float, p_observed: float,
               alpha_z: float = 1.96, power_z: float = 0.84) -> int:
    """One-sample two-sided test, 80% power at alpha=.05.
    p_frozen  : the recorded baseline (0.544)
    p_observed: the ACTUAL live win rate from the reconciliation
    """
    if p_observed == p_frozen:
        return math.inf          # cannot distinguish identical values
    num = (alpha_z * math.sqrt(p_frozen * (1 - p_frozen))
           + power_z * math.sqrt(p_observed * (1 - p_observed))) ** 2
    return math.ceil(num / (p_frozen - p_observed) ** 2)

# The gate becomes:
#   HOLD  if n_total < n_required(0.544, observed_wr)
#   PASS  otherwise
# and the report must PRINT both n_total and n_required so the margin
# is visible rather than implied.
```

**Classification under LAW-9: repair, agent authority.** It changes no formula bytes and flips no passing test — the existing `sample_size.py` tests should be extended, not replaced, since the 93 case remains correct at `p_observed = 0.40`.

**Keep a floor.** `n_required` collapses toward ~31 as the observed gap widens, and at very small `n` the normal approximation behind the formula degrades. Add `n_floor = 30` as a `MUST_RATIFY` binding, proposed 30, below which the answer is `INSUFFICIENT_SAMPLE_REGARDLESS`.

---

## 6 · One check to run against #36's conflict resolution

The resolution took **the union of both sides' pinned paths** — the B00R gen-2 governance artifacts (`DEC-*-002.json`, `receipt_trust_registry.g2.v1.json`) plus the formula-repair / rc5 / linkage set. Every hash recomputed real, both sides preserved, 137 pins verified.

**The method is right. One scope question remains open, and it belongs to the reviewer, not the agent.**

```
D-3b records that the B00R generation-2 SOURCE grant DELIBERATELY
EXCLUDES the formula paths, which is why a formula-repair milestone PR
classifies as out-of-scope against main.

The union pin set now attests to files on BOTH sides of that exclusion.

Pinning a path is not the same as granting it — the grant lives in
tools/classify_milestone_pr.py, not in SOURCE_HASHES.sha256 — so this is
NOT a defect on its face.

But the two must be checked for agreement before signature:
   Does the pinned union contain any path the gen-2 grant excludes?
   If yes -> D-3b's widening must land in the SAME PR-set as the pin,
             or the pin attests to a scope the grant does not admit.

This is a one-command check (set difference of pinned paths against the
grant's allowlist) and it is the kind of thing the independent reviewer
under D-7 should be handed explicitly rather than left to notice.
```

---

## 7 · What has and has not moved

| | State |
|---|---|
| **Moved** | WO-A tooling is on `main` in TriadLearning — reachable from a normal pull on the box rather than a feature branch. That is the practical value of #462 and it makes the on-box session easier, not harder. |
| **Moved** | #36 is no longer `dirty`. When the four owner acts land, it merges without a second conflict fight. |
| **Not moved** | **Every substantive question still requires the Mac.** WO-00 probe, `confirm_30.py`, `run_wo_a.py` + A5 — all three, unchanged, still blocked on physical box access. |
| **Not moved** | WO-D remains `BLOCKED_ON_ORIGIN_EMISSION` — Origin tier holds 0 rows. |
| **New debt** | The checkpoint seal (§4). |
| **Newly visible** | `main` has no enforced merge gate (§2), and its lint check has been carrying zero information (§3). |

---

## 8 · Attestation

| Claim | Status |
|---|---|
| #462 merged at `135a2702`; ruff clean on the two new tools; 54 + 11 tests green | **Source claim** — not rerun |
| #36 at `9f52fdf`; 137 hashes verified; e2e_audit 30/30; 57 pin/overclaim/governance tests passed | **Source claim** — not rerun |
| `mergeable_state = unstable` ⇒ the combined check is not required | **Inference by this reviewer** from GitHub's documented state semantics. High confidence; confirm by reading the branch protection settings directly. |
| The `n_required` miscalibration | **Computed by this reviewer.** The table in §5 is reproducible from the formula given. |
| Tokens not used, echoed, or stored by either party | **Verified** for this reviewer; **source claim** for the implementing agent. **Rotation is still required and still outstanding.** |

**Runtime state: `NOT_ATTESTED`.**

---

*Prepared 2026-08-13 · revision record R-03 · three correct calls recorded, three findings, one self-correction, one reviewer check · posture unchanged `OFF/OFF/OFF/LIVE` · no token handled · no signature, pin, or receipt fabricated*
