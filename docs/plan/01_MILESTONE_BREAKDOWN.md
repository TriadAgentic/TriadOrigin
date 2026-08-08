# 01 · Milestone Breakdown

Each milestone lists **scope**, **deliverable files**, **acceptance evidence**, **inventory /
checklist IDs**, and **dependencies**. ✅ = merged; 🔜 = planned.

---

## M1 · Contract & Identity foundation ✅ (PR #1)

**Scope.** The strict versioned interface law + deterministic identity, plus repo scaffolding.

**Delivered.**
- `src/triad_origin/canonical.py` — canonical JSON, integer-tick numeric law, length-prefixed hashing.
- `src/triad_origin/ids.py` — `semantic_instance → structure → reaction → hypothesis → candidate`.
- `contracts/schemas/*.schema.json` — all 30 contracts (C-001…C-030), draft 2020-12, self-contained.
- `contracts/registry/index.json`, `contracts/manifest/contract_bundle.manifest.v1.json`,
  `contracts/MANIFEST.sha256`, `contracts/golden/<id>/{valid,invalid}.json`.
- `src/triad_origin/contracts.py` — validate (jsonschema + stdlib fallback), epoch fencing,
  forbidden-candidate-field guard.
- `tools/gen_contracts.py`, `tools/gen_manifest.py`, `tools/verify_manifest.py`.
- Scaffolding: `pyproject.toml`, `CLAUDE.md`, `README.md`, `docs/SPEC_INDEX.md`, vendored spec.

**Acceptance.** 128 tests green; `verify_manifest` OK (91 artifacts). **Inventory:** CON-001…030,
REP-017, SRV-004 scaffold. **Deps:** none.

---

## M2 · Kernel primitives & transport ✅ (PR #2)

**Scope.** The deterministic substrate every structure/capsule builds on.

**Delivered.**
- `transition.py` (pure signature + `require()` fail-closed), `instrument_math.py` (MOD-004),
  `clock_watermark.py` (MOD-003), `partition.py` (MOD-002 + E01 quality machine, Doc 04 §04.3),
  `ledger.py` (hash-chained append-only, DAT-001/005/008), `checkpoint.py` (MOD-017),
  `journal.py` (MOD-016 + MOD-018 replay), `lease.py` (CON-023, Doc 04 §04.16),
  `ingress.py` (MOD-001), `telemetry.py` (MOD-019), `health.py` (MOD-020).

**Acceptance.** 165 tests green; manifest OK. **Inventory:** MOD-001/002/003/004/016/017/018/019/020,
CON-023, DAT-001/005/008, partition-quality machine. **Deps:** M1.

---

## M3 · Structure semantics 🔜 (next)

**Scope.** The pure causal detectors — the heart of ORIGIN (Doc 02 §§02.3–02.11, Doc 04 §§04.4–04.7).
Base already laid: `src/triad_origin/structures/{__init__,common}.py` (lifecycle enums, `Direction`,
`penetration`, `mirror_tick`).

**Deliverables (7 detector modules + tests).**
| Module | Inventory | Core rule (spec) |
|--------|-----------|------------------|
| `feature_primitives.py` | MOD-005 | Causal trailing ATR / rolling extremes; warm-up honest-null (§02.11/§02.4) |
| `structures/typed_level_registry.py` | MOD-006 | DC-swing baseline machine + fractal/rolling/equal/session levels (§02.3–02.4, §04.4) |
| `structures/structure_state.py` | MOD-007 | Directional state + BOS/CHOCH + two-stage protected-swing promotion (§02.5–02.6, §04.4) |
| `structures/fvg_registry.py` | MOD-008 | 3-bar FVG + penetration lifecycle (§02.7, §04.5) |
| `structures/order_block_registry.py` | MOD-009 | `ob.displacement_bos.v1` origin+displacement+linked BOS (§02.8, §04.6) |
| `structures/excursion_reclaim_registry.py` | MOD-010 | Frozen-level excursion → timed reclaim → hold (§02.9, §04.7) |
| `structures/flow_atoms.py` | MOD-011 | TFI/OFI/tilt/liquidation/exhaustion, null honesty, no-future-venue (§02.11) |

**Acceptance.** Each detector: formation predicate + lifecycle-to-terminal + precedence +
LONG/SHORT mirror + fail-closed-on-missing-param + null honesty tests. Full suite green; manifest OK.
**Execution:** ultracode fan-out (1 agent/detector, self-tested), then full-suite re-verify.
**Deps:** M2 (`transition`, `canonical`, `clock_watermark`).

---

## M4 · Reaction, capsules & candidates 🔜

**Scope.** Turn confirmed structures into immutable trade hypotheses (Doc 02 §§02.12–02.13, §04.8).

**Deliverables.**
- `reaction_engine.py` (MOD-012) — location → freshness → departure → trigger → confirmation →
  geometry; emits `reaction_event.v1`-shaped facts; RR rational computed.
- `capsule_host.py` (MOD-013) — pure isolated hypothesis runtime; one capsule per formula/param/trial.
- `capsules/` — the 5 capsules (Doc 02 §02.13): `dc_swing_bos_first_retest.v1`,
  `protected_swing_choch_first_retest.v1`, `fvg_displacement_first_touch.v1`,
  `ob_displacement_bos_first_touch.v1`, `level_excursion_reclaim_flow_confirmed.v1`.
- `opportunity_clusterer.py` (MOD-014) — correlated hypothesis identity; prevents alias confluence.
- `candidate_publisher.py` (MOD-015) — immutable `edge_candidate.v2` + `edge_candidate_transition.v1`
  (withdrawal). Enforces RR ≥ 2.0 and **no forbidden money fields**.

**Acceptance.** End-to-end: `market_state.v2` sequence → structures → reaction → candidate emission,
with RR-floor rejection, withdrawal on structure invalidation/fill, isolation (no cross-capsule vote),
and candidate contract validity + forbidden-field guard. Full suite green.
**Execution:** capsule_host + reaction_engine authored directly; 5 capsules fanned out (ultracode).
**Deps:** M3.

---

## M5 · Config artifacts, wiring & services 🔜

**Scope.** Signed configuration, the comparator/authority control plane, and the dark service main
(Doc 05, Doc 00 config inventory).

**Deliverables.**
- `config/*.yaml|json` + JSON-Schemas + a `config_loader.py` with owner/change-control/digest:
  `capsules.v1`, `geometry.v2`, `lifecycle.v1`, `regime_eligibility.v2`, `symbols.v2`,
  `staleness_bounds.v2`, `latency_budgets.v2`, `risk_policy.v2`, `exit_policy.v2`,
  `transport_bindings.v1`, `activation_manifest.v1` (DARK), `treatment_manifest.v1`,
  `rollback_manifest.v1`, `secret_allowlist.v1`, `compatibility_manifest.v1` (CFG-013…027).
- `comparator.py` (SRV-006) — side-effect-free legacy/ORIGIN diff → `divergence_record.v1`
  (no E07/E08/E09 write path).
- `authority_router.py` (SRV-007) — single selected candidate writer, lease-gated (exactly one arm).
- `legacy_bridge.py` (SRV-005) — `candidate.v1`/context → control candidate (dark, control-only).
- `replay_runner.py` + CLI (SRV-025) — same-code deterministic runner → `replay_receipt.v1`.
- `service/main.py` (SRV-004, `triad-origin-e02`) — startup/readiness sequence to
  `READY_NO_AUTHORITY`; requests no lease; ACL posture doc.

**Acceptance.** Config artifacts validate against their schemas + digests; `activation_manifest`
asserts `allow_money_publish:false`; comparator has no authority-write import; router admits exactly
one candidate per allocation and rejects split-brain/stale-epoch; service main reaches
`READY_NO_AUTHORITY` with zero side effects. Full suite green.
**Deps:** M1–M4.

---

## M6 · Verification matrix & runbooks 🔜

**Scope.** The falsification-first registry + operator runbooks + read-only evidence faces
(Doc 08, Doc 09).

**Deliverables.**
- `tests/matrix/` — the offline-feasible subset of the Doc 08 224-test registry, tagged by test ID,
  wired to pytest (the proof obligations across structures/capsules/kernel/contracts).
- `docs/runbooks/` — migration & rollback runbooks distilled from Doc 09 (dark/canary/cutover/
  rollback cases, automatic stop triggers, incident flow, DR) as **procedure docs** (no live action).
- `mcp_readface.py` — read-only evidence faces (attestation/lease scope, input offsets, structure
  lineage, candidate funnel, divergence, replay receipts) reporting honest `unavailable`.
- `docs/VERIFICATION.md` mapping each obligation → test.

**Acceptance.** Matrix subset green and traceable to Doc 08 IDs; runbooks complete & cross-linked;
read faces expose no secrets/control verbs. Full suite green.
**Deps:** M1–M5.

---

## Not in these milestones (require real market data / governance ceremony)

Doc 09 stages **M5–M9** (strict dual-publish on live data, safety canary, economic certification,
scoped authority cutover, progressive scale/retirement) are **operator/governance activities on live
infrastructure** and are **not agent-executable** in this repo. They are documented as runbooks in M6
so the path exists, but no live activation is performed.
