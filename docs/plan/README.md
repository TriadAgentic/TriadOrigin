# TRIAD ORIGIN V7 — Implementation Plan

This directory is the **agreed build plan** for implementing the TRIAD ORIGIN V7 1.0.0-RC1
specification set (vendored under [`../spec/`](../spec/)) in the `TriadAgentic/TriadOrigin`
clean-room repository. Read it before implementing; it is reviewed and ratified before code.

| File | Purpose |
|------|---------|
| [`00_MASTER_PLAN.md`](00_MASTER_PLAN.md) | Objectives, constitution, build approach, milestone map, PR cadence, verification strategy, risks, deferred scope |
| [`01_MILESTONE_BREAKDOWN.md`](01_MILESTONE_BREAKDOWN.md) | Per-milestone scope, deliverable files, acceptance evidence, inventory/checklist IDs, dependencies |
| [`02_TRACEABILITY.md`](02_TRACEABILITY.md) | Every inventory item (REP/SRV/MOD/CON/TOP/CFG/DAT/VEN/SEC/OBS/OPS) → milestone/module; verification-matrix mapping |
| [`03_ENGINEERING_CONVENTIONS.md`](03_ENGINEERING_CONVENTIONS.md) | Determinism, contract, parameter, identity, transport, testing and PR/merge conventions |
| [`04_STATUS.md`](04_STATUS.md) | Live milestone status |

## How the plan is executed

- Work ships **milestone by milestone**; each milestone is a **PR merged to `main`** with a green
  `pytest` suite and `tools/verify_manifest.py` exit-0.
- The scope of each milestone is fixed by [`01_MILESTONE_BREAKDOWN.md`](01_MILESTONE_BREAKDOWN.md).
  A change to scope updates the plan file in the same PR.
- Nothing in this plan authorizes a live activation. Every artifact ships **DARK**.
