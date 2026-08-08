# TRIAD ORIGIN V7 — Spec Index & Coverage Map

The normative source is vendored under [`docs/spec/`](spec/) (documents 00–10, 1.0.0-RC1) plus the
machine-readable inventory / checklist / verification-matrix CSVs. This file maps the specification's
bill of materials to the milestones that implement it, so coverage is auditable.

## Normative documents

| Doc | Title | Role here |
|----|-------|-----------|
| 00 | Document Control & Index | Naming, ADRs, evidence labels, precedence |
| 01 | Master Specification | Constitution, authority boundaries, SLOs, phase gates |
| 02 | Structure Semantics | Exact causal definitions (levels, BOS/CHOCH, FVG, OB, reclaim, flow, capsules) |
| 03 | Contract & Identity Catalog | 30 contracts, envelope, canonical encoding, identity hierarchy |
| 04 | State-Machine Catalog | Owner-specific append-only lifecycle machines + guards |
| 05 | End-to-End Wiring | Topics, producer/consumer edges, transport, startup/failure |
| 06 | Implementation Inventory | Bill of materials (repos, services, modules, contracts, topics, config, data) |
| 07 | Implementation Checklist | Work breakdown, owners, acceptance evidence, gates |
| 08 | Verification Matrix | Falsification-first test registry |
| 09 | Migration & Rollback | Freeze → dark → canary → cutover → rollback → retirement |
| 10 | Decision & Deferred Register | Binding decisions, TBDs, deferred scope |

## Milestone → inventory coverage

| Milestone | Inventory IDs | Status |
|-----------|---------------|--------|
| **M1 · Contract & Identity foundation** | CON-001…CON-030 (schemas + bundle manifest + registry + golden vectors), MOD identity/canonical primitives, SRV-004/REP-017 scaffolding | **DONE** (PR #1) |
| **M2 · Kernel primitives & transport** | MOD-001 contract_ingress, MOD-002 partition_coordinator, MOD-003 clock_watermark, MOD-004 instrument_math, MOD-016 state_journal, MOD-017 checkpoint_restore, MOD-018 replay_adapter, MOD-019 evidence_telemetry, MOD-020 health_readface, CON-023 producer_lease, DAT-001/005/008 ledgers, partition-quality machine (Doc 04 §04.3) | **DONE** (PR #2) |
| M3 · Structure semantics | MOD-005 feature_primitives, MOD-006 typed_level_registry, MOD-007 structure_state, MOD-008 fvg_registry, MOD-009 order_block_registry, MOD-010 excursion_reclaim_registry, MOD-011 flow_atoms (Doc 02 §§02.3–02.11, Doc 04 §§04.4–04.7) | planned |
| M4 · Reaction, capsules & candidates | MOD-012 reaction_engine, MOD-013 capsule_host, MOD-014 opportunity_clusterer, MOD-015 candidate_publisher, the 5 capsules (Doc 02 §02.13, Doc 04 §04.8) | planned |
| M5 · Config artifacts, wiring & services | CFG-013…027 signed config, SRV-005 legacy-input-bridge, SRV-006 edge-comparator, SRV-007 edge-authority-router, SRV-025 replay-runner, `triad-origin-e02` main (Doc 05) | planned |
| M6 · Verification matrix & runbooks | Doc 08 test registry (offline-feasible subset), Doc 09 runbooks, read-only evidence faces | planned |

## Determinism & governance invariants enforced repo-wide

- Pure transition signature; no clock / I/O / randomness / unordered output (Doc 02).
- Integer-tick numeric law; canonical sorted-key JSON; length-prefixed identity hashes (Doc 03 §03.4).
- Contract bytes pinned by `contracts/MANIFEST.sha256`; CI fails on unmanifested/same-version drift.
- Symbolic thresholds only — a required-but-absent parameter fails closed (Doc 02 §02.15).
- DARK posture: no venue credentials, order verbs, or money authority. Authority is a fenced
  producer lease, never inherited on restart (Doc 04 §04.16/§04.17).

## Explicitly deferred (Doc 10 / inventory `DEFER`/`BLOCKED`)

Hyperliquid & non-Binance adapters (VEN-019/020), object-store archive (DAT-018), JetStream
transport binding (optional, file-ledger first), and every numeric threshold value (remains TBD
until a registered trial + signed activation manifest). These are named, not silently chosen.
