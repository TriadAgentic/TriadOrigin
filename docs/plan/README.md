# TRIAD ORIGIN V7 — Controlled Implementation Plan (B-Series)

This directory is the repository-local execution law for the clean-room
`TriadAgentic/TriadOrigin` service. Updated 2026-08-09 under the operator's build directive; the
complete RC2+RC3+RC4 control package is vendored (`docs/control/`, `docs/spec_rc2..rc4/`).

## Current truth

- Repository scope is **E02-V7**: deterministic features, structures, reactions,
  hypotheses/candidates, replay, quarantine, evidence, the lever/four-plane law, the DARK
  control-plane libraries (comparator/router/bridge/replay-runner), and the DARK service
  boundary.
- Runtime posture is **DARK / `READY_NO_AUTHORITY`**. Nothing here authorizes money, a venue
  command, an E07 decision, an E08 risk authorization, or an E09 execution.
- The build proceeds milestone-by-milestone (B00–B10), one PR each, merged only on a green gate.
- Every unratified value stays fail-closed data; open ambiguities live in
  [`09_OPEN_QUESTIONS.md`](09_OPEN_QUESTIONS.md) for the operator's batch answer.

| File | Purpose |
|---|---|
| [`00_MASTER_PLAN.md`](00_MASTER_PLAN.md) | Authority, objective, constitution, ledger partition, milestone map, cadence, verification, risks |
| [`01_MILESTONE_BREAKDOWN.md`](01_MILESTONE_BREAKDOWN.md) | Per-milestone scope, deliverables, acceptance, slices, dependencies |
| [`02_TRACEABILITY.md`](02_TRACEABILITY.md) | Inventory → milestone/module map (historical + B-series) |
| [`03_ENGINEERING_CONVENTIONS.md`](03_ENGINEERING_CONVENTIONS.md) | Determinism, contract, parameter, identity, transport, testing, PR law |
| [`04_STATUS.md`](04_STATUS.md) | Live evidence-based status |
| [`05_RC2_CONFLICT_REGISTER.md`](05_RC2_CONFLICT_REGISTER.md) | Conflict/blocker register + dispositions |
| [`06_RC2_SOURCE_INVENTORY.md`](06_RC2_SOURCE_INVENTORY.md) | Control-package source inventory (now COMPLETE) |
| [`07_REVIEW_REMEDIATION.md`](07_REVIEW_REMEDIATION.md) | Historical review-finding remediation (R00) |
| [`08_BUILD_CHECKLIST.md`](08_BUILD_CHECKLIST.md) | Human-readable master checklist over the machine ledger |
| [`09_OPEN_QUESTIONS.md`](09_OPEN_QUESTIONS.md) | Batched operator questions/clarifications |
| `milestone_receipt.schema.json` | Receipt schema (R00 lineage; B-series profile defined in B01) |

## Authority hierarchy

See `CLAUDE.md` (rank 1: operator's authenticated scoped decisions, incl. the 2026-08-09 build
directive; then safety truth, signed manifests, RC4, RC3 + corrections, effective bundle, RC1,
contracts, this plan, code). An un-migrated conflict enters `SAFE_HOLD`; code never chooses
silently — it lands in `09_OPEN_QUESTIONS.md`.
