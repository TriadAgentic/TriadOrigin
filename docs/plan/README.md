# TRIAD ORIGIN V7 — Controlled Implementation Plan

This directory is the repository-local execution law for the clean-room
`TriadAgentic/TriadOrigin` service.

## Current truth

- Repository scope is **E02-V7 only**: deterministic features, structures, reactions,
  hypotheses/candidates, replay, quarantine, evidence, and the DARK service boundary.
- Runtime posture is **SAFE_HOLD / DARK**. Nothing here authorizes money, a venue command, an
  E07 decision, an E08 risk authorization, or an E09 execution.
- The merged implementation was built against `1.0.0-RC1`.
- The supplied `1.0.0-RC2` control package is a
  `RATIFICATION_CANDIDATE_NOT_ARMED`, is incomplete, and contains unresolved normative conflicts.
- M1 and M2 therefore mean **merged RC1 implementation**, not accepted RC2 gates.
- M3 is **BLOCKED**. Off-tree drafts are non-evidence.

## Authority hierarchy

1. The operator's E02-only repository scope.
2. Independent safety and venue/account truth.
3. Signed activation and risk manifests for the exact scope.
4. The resolved RC2 declaration/parameter registry.
5. The resolved RC2 formula and wiring registries.
6. Immutable contract schemas and state machines.
7. This implementation plan.
8. Code, tests, comments, diagrams, and examples.

An un-migrated conflict enters `SAFE_HOLD`; code does not choose silently.

## Files

| File | Purpose |
|---|---|
| [`00_MASTER_PLAN.md`](00_MASTER_PLAN.md) | Scope, constitution, authority, sequence, and merge law |
| [`01_MILESTONE_BREAKDOWN.md`](01_MILESTONE_BREAKDOWN.md) | R00 and B00–B09 deliverables and acceptance |
| [`02_TRACEABILITY.md`](02_TRACEABILITY.md) | Ownership and milestone mapping for contracts, W/F/PAR/GV/OPS families |
| [`03_ENGINEERING_CONVENTIONS.md`](03_ENGINEERING_CONVENTIONS.md) | Determinism, contracts, replay, security, tests, and evidence rules |
| [`04_STATUS.md`](04_STATUS.md) | Audited repository and gate state |
| [`05_RC2_CONFLICT_REGISTER.md`](05_RC2_CONFLICT_REGISTER.md) | Release-blocking contradictions and missing decisions |
| [`06_RC2_SOURCE_INVENTORY.md`](06_RC2_SOURCE_INVENTORY.md) | Exact supplied-artifact hashes and missing package members |
| [`07_REVIEW_REMEDIATION.md`](07_REVIEW_REMEDIATION.md) | Mapping of the 14 unresolved PR findings into R00 |
| [`milestone_receipt.schema.json`](milestone_receipt.schema.json) | Machine-readable minimum merge/post-merge evidence |

## Execution law

Every build milestone is exactly one PR from a fresh branch based on current `main`.
Semantic scope/spec changes land in a prior plan/spec PR; they are never hidden inside an
implementation PR. A milestone may merge only when:

1. required CI checks pass on the exact PR head;
2. every actionable thread required by that milestone's pre-merge gate is resolved;
3. the approved head SHA is unchanged;
4. the PR is squash-merged;
5. a fresh reconstruction of merged `main` reproduces the checks; and
6. an immutable milestone receipt is sealed.

No force-push workflow, self-reported test count, or workbook colour is acceptance evidence.

### R00 bootstrap exception

R00 is the one-time bootstrap exception to the prior-plan-PR rule: the obsolete plan and the
foundation defects were discovered in the same audit, and no corrected execution law existed under
which to split them safely. R00 may therefore combine governance refreeze with bounded M1/M2
integrity remediation. The exception expires when R00 merges. B00 onward requires any semantic
spec/scope change to merge in a prior, separate PR.

For R00 specifically, PR #4 threads close before merge; the 14 inherited PR #1–#3 threads close
post-merge after their replies can cite the actual squash SHA and receipt, as controlled by
[`00_MASTER_PLAN.md`](00_MASTER_PLAN.md) and [`07_REVIEW_REMEDIATION.md`](07_REVIEW_REMEDIATION.md).
