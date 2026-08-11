# TRIAD ORIGIN V7 — Controlled Implementation Plan (B-Series)

This directory is the repository-local execution law for the clean-room
`TriadAgentic/TriadOrigin` service. Updated 2026-08-09 under the operator's build directive; the
complete RC2+RC3+RC4 control package is vendored (`docs/control/`, `docs/spec_rc2..rc4/`).

## C0 authority routing

Canonical machine milestone semantics and status live under [`../control/closure/`](../control/closure/).
This plan directory supplies planning, provenance, generated projections, and decision inputs; it
does not override the closure registry. In particular, `04_STATUS.md`,
`05_RC2_CONFLICT_REGISTER.md`, `08_BUILD_CHECKLIST.md`, and `09_OPEN_QUESTIONS.md` are
historical, generated, or input views. Routing them this way does not claim that C0 is closed or
signed.

B00R closes only the governance/evidence root. It does not close formula migration or capability
implementation; those remain downstream blockers. The operational posture is invariant
`OFF/OFF/OFF/LIVE`.

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
| [`04_STATUS.md`](04_STATUS.md) | Historical/generated status view; non-authoritative |
| [`05_RC2_CONFLICT_REGISTER.md`](05_RC2_CONFLICT_REGISTER.md) | Historical conflict/blocker input; non-authoritative |
| [`06_RC2_SOURCE_INVENTORY.md`](06_RC2_SOURCE_INVENTORY.md) | Control-package source inventory (now COMPLETE) |
| [`07_REVIEW_REMEDIATION.md`](07_REVIEW_REMEDIATION.md) | Historical review-finding remediation (R00) |
| [`08_BUILD_CHECKLIST.md`](08_BUILD_CHECKLIST.md) | Human-readable generated checklist; non-authoritative |
| [`09_OPEN_QUESTIONS.md`](09_OPEN_QUESTIONS.md) | Decision/question input view; non-authoritative until compiled into the closure registry |
| `milestone_receipt.schema.json` | Receipt schema (R00 lineage; B-series profile defined in B01) |

## Authority hierarchy

See `CLAUDE.md` (rank 1: operator's authenticated scoped decisions, incl. the 2026-08-09 build
directive; then safety truth, signed manifests, RC4, RC3 + corrections, effective bundle, RC1,
contracts, this plan, code). An un-migrated conflict enters `SAFE_HOLD`; code never chooses
silently. Questions may be recorded in `09_OPEN_QUESTIONS.md`, but only their compiled canonical
representation under `docs/control/closure/` can govern machine status.
