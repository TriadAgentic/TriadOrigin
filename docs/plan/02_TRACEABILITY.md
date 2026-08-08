# 02 · Traceability

Maps the specification bill of materials (Doc 06 inventory / Doc 07 checklist / Doc 08 verification)
to the milestone and module that implements it. Status: ✅ merged · 🔜 planned · ⏸ deferred (named).

## Repositories & processes (Doc 06 REP/SRV)

| ID | Item | Target | Milestone |
|----|------|--------|-----------|
| REP-017 | TriadOrigin repo | clean-room repo | M1 ✅ |
| SRV-004 | `triad-origin-e02` | standalone no-credential service | scaffold M1 ✅ · main M5 🔜 |
| SRV-005 | legacy-input-bridge | control-only dark bridge | M5 🔜 |
| SRV-006 | edge-comparator | side-effect-free diff | M5 🔜 |
| SRV-007 | edge-authority-router | single candidate writer | M5 🔜 |
| SRV-024 | lease-coordinator | monotonic fencing | M2 ✅ (`lease.py`) |
| SRV-025 | replay-runner | same-code deterministic runner | M5 🔜 |
| REP-001…016, SRV-001…003/008…023 | estate repos/processes | audit/repair/retain/defer **in their own repos** | out of TriadOrigin scope (referenced only) |

## ORIGIN modules (Doc 06 MOD)

| ID | Module | Milestone |
|----|--------|-----------|
| MOD-001 contract_ingress | `ingress.py` | M2 ✅ |
| MOD-002 partition_coordinator | `partition.py` | M2 ✅ |
| MOD-003 clock_watermark | `clock_watermark.py` | M2 ✅ |
| MOD-004 instrument_math | `instrument_math.py` | M2 ✅ |
| MOD-005 feature_primitives | `feature_primitives.py` | M3 🔜 |
| MOD-006 typed_level_registry | `structures/typed_level_registry.py` | M3 🔜 |
| MOD-007 structure_state | `structures/structure_state.py` | M3 🔜 |
| MOD-008 fvg_registry | `structures/fvg_registry.py` | M3 🔜 |
| MOD-009 order_block_registry | `structures/order_block_registry.py` | M3 🔜 |
| MOD-010 excursion_reclaim_registry | `structures/excursion_reclaim_registry.py` | M3 🔜 |
| MOD-011 flow_atoms | `structures/flow_atoms.py` | M3 🔜 |
| MOD-012 reaction_engine | `reaction_engine.py` | M4 🔜 |
| MOD-013 capsule_host | `capsule_host.py` | M4 🔜 |
| MOD-014 opportunity_clusterer | `opportunity_clusterer.py` | M4 🔜 |
| MOD-015 candidate_publisher | `candidate_publisher.py` | M4 🔜 |
| MOD-016 state_journal | `journal.py` | M2 ✅ |
| MOD-017 checkpoint_restore | `checkpoint.py` | M2 ✅ |
| MOD-018 replay_adapter | `journal.py::replay` | M2 ✅ |
| MOD-019 evidence_telemetry | `telemetry.py` | M2 ✅ |
| MOD-020 health_readface | `health.py` | M2 ✅ |

## Contracts (Doc 06 CON) — all M1 ✅

C-001…C-030 → `contracts/schemas/*.schema.json` + registry + golden vectors + bundle manifest.
Producer/consumer implementations that *exercise* each contract land with their owning milestone
(structures M3, candidates M4, comparator/lease/router M5, receipts/faces M6).

## Topics (Doc 06 TOP)

Logical topics bind to the **file-ledger** first (`ledger.py`, M2 ✅). The per-topic
writer/reader/retention wiring + `transport_bindings.v1` lands in **M5** 🔜. JetStream binding is
⏸ deferred (optional, separately certified).

## Configuration (Doc 06 CFG)

CFG-013…027 signed artifacts → **M5** 🔜. Current-estate configs (CFG-001…012) are audited in their
home repos, not re-homed here (referenced only). `live.env` global inheritance is ⏸ RETIRE (estate).

## Storage & data (Doc 06 DAT)

| ID | Milestone |
|----|-----------|
| DAT-001 raw ledger, DAT-005 checkpoint store, DAT-008 lease ledger | M2 ✅ |
| DAT-004 structure journal, DAT-006 candidate ledgers, DAT-007 divergence, DAT-010 quarantine | M3/M4/M5 🔜 |
| DAT-014 golden corpus, DAT-015 replay receipts, DAT-016 trial registry | M5/M6 🔜 |
| DAT-012 shadow.cf_trades | ⏸ BLOCKED (owner unknown — estate) |
| DAT-018 object-store archive | ⏸ DEFER |

## Venue & ingress (Doc 06 VEN)

VEN-001…018 Binance route/book/algo/emergency semantics are **specified** and gated at ORIGIN's
boundary, but ORIGIN holds **no venue code path** — these live in the VGP/E09 estate. ORIGIN encodes
the *contract* expectations (route family enum, environment=LIVE-only, no testnet) in M1 schemas and
the *ingress* discipline in M2. VEN-019/020 (Hyperliquid/other) ⏸ DEFER.

## Security (Doc 06 SEC)

SEC-004/005/006 ORIGIN OS/network/filesystem ACL posture → documented in M5 service main + M6
runbooks; SEC-002/003/013/014 are estate incident/venue items (⏸ referenced). ORIGIN's structural
guarantee: no import that signs, holds a key, or writes an order.

## Observability (Doc 06 OBS)

OBS metrics are modeled by `telemetry.py` (M2 ✅) + the read faces (M6 🔜) with bounded cardinality
and named zero reasons. Prometheus wiring is a deployment concern (documented, not required for CI).

## Verification matrix (Doc 08)

The offline-feasible subset (determinism, contract, structure/capsule proof obligations) is
implemented as tests across M1–M4 and consolidated into `tests/matrix/` with Doc 08 IDs in **M6**.
Tests requiring live venue data or a running bus are ⏸ named as operator/on-box gates (Doc 09 M5–M9).
