# 01 · Milestone Breakdown — B-Series

Each milestone lists **scope**, **deliverables**, **acceptance evidence**, **control-bundle
slice** (ledger lane), and **dependencies**. Legacy M1/M2 deliverables (merged PRs #1/#2, audited
and remediated by R00 PR #4/#7) are the substrate; the B-series builds on them.

Every milestone PR must satisfy: full CI gate green (pytest ×2 hash seeds, collection identity,
manifest + manifest schema, reproducible build, wheel smoke, capability boundary) **+
`tools/e2e_audit.py` all stages + `tools/build_ledger.py --verify`**, and must extend the e2e
walk with each new capability (E2E growth law).

---

## B00 · Authority & control baseline

**Scope.** Make the complete RC2/RC3/RC4 control package the repository's machine-readable law;
re-plan the build under the operator's 2026-08-09 directive; install the e2e audit walk and the
build ledger; open the questions register.

**Deliverables.**
- `docs/control/` — RC3 overlay schema + normative overlay + effective control bundle + bundle
  manifest + validation report + RC3 executable builder; RC4 control bundle + addendum builder;
  `SOURCE_HASHES.sha256`; `build_ledger.json` + overrides file.
- `docs/spec_rc2/` (complete RC2 package incl. previously-missing checklist + workbook),
  `docs/spec_rc3/`, `docs/spec_rc4/`, `docs/reports/` (sign-off + cross-engine reports).
- `tools/build_ledger.py`, `tools/e2e_audit.py` (9 stages v0), CI wiring for both.
- Plan rewrite: `00_MASTER_PLAN.md`, this file, `04_STATUS.md`, `06_RC2_SOURCE_INVENTORY.md`
  update, `08_BUILD_CHECKLIST.md`, `09_OPEN_QUESTIONS.md`; `CLAUDE.md` authority update.

**Acceptance.** CI green; e2e 9/9; ledger verifies (1,250 rows partitioned); hashes recorded.
**Slice.** Ledger B00 rows (governance/cross-cutting baseline). **Deps.** none.

---

## B01 · Foundation corrections (G0)

**Scope.** Close the inherited foundation findings that must precede all semantic work, and land
the strict contract/identity v2 layer RC3/RC4 demand.

**Deliverables.**
- **CTRL-B01-003 / BLK-RC2-017:** typed identity v2 — field-type-tagged digest framing as a new
  identity schema version with migration vectors; RC1 IDs remain valid under their version.
- **CTRL-B01-002 / BLK-RC2-016:** `engine_attestation.v2` with envelope/payload equality
  constraints + corrected golden vectors; v1 preserved immutable.
- **CTRL-B01-001:** additive bundle descriptor v2 correcting media-type labels; RC1 bundle bytes
  and hash unchanged.
- **RC4 L2 slice:** `engine_control_manifest.v2` schema, strict receipt schemas v2 (exact enums,
  semantic combination validation), `fill.v3`, `structure_atom.v2`, `edge_candidate.v2` (+
  transition contract), `producer_lease` verify-only contract alignment — schema + golden
  vectors + registry + manifest re-pin.
- Epoch-law regression audit (current-epoch equality accepted; lower rejected) across contracts
  and ingress — verifying the R00 corrections and extending vectors.
- Dependency-pin refresh policy note (B01 owns reviewed refreshes per R00).

**Acceptance.** All new/changed schemas have valid+invalid goldens; manifest re-pinned; identity
migration vectors prove v1 stability; e2e gains a v2-identity stage. **Slice.** B01 ledger rows
(Contracts node, G0 gate-control in-repo parts). **Deps.** B00.

---

## B02 · Kernel hardening (G0/G1 in-repo)

**Scope.** Close the two structural kernel findings and land the deterministic timing law.

**Deliverables.**
- **CTRL-B02-001:** external durable anchor binding for ledger output (chain head + segment +
  offset + file identity + recovery receipt); falsification tests for tail deletion/replacement;
  cold/warm exactly-once parity.
- **CTRL-B02-002:** closed per-scope fence state (accepted-token high-water per scope) sealed
  into checkpoints, restored before consumption; falsification: lower-token acceptance across
  restart.
- **RC4 timings registry:** the 17 declared timing bounds as a versioned data artifact + loader
  (pure; consumers receive values, never read clocks).
- F01 (exact tick/step conversion) golden vectors wired to `instrument_math`.

**Acceptance.** New falsification tests; e2e gains anchor + fence-restore stages. **Slice.** B02
rows (W22/W24 in-repo, G1 in-repo). **Deps.** B01.

---

## B03 · Structure semantics I (G2 — F02–F10)

**Scope.** The first half of the pure causal detector core.

**Deliverables** (each a pure state machine over `transition()` with its RC3 formula):
- `feature_primitives.py` — F02 finalized time-bar aggregation, F03 true range/trailing ATR in
  ticks, F06 trailing rolling extreme; warm-up honest-null.
- `structures/typed_level_registry.py` — F04 directional-change swing, F05 closed fractal pivot,
  F07 anchored equal-level cluster (span bound symbolic → RESEARCH), F08 UTC session level.
- `structures/structure_state.py` — F09 directional structure + protected swing (reducer version
  symbolic → RESEARCH), F10 accepted break / BOS / CHOCH with precedence law.
- `structure_atom.v2` / `structure_transition.v2` emission shapes wired to the journal.

**Acceptance.** Per-detector: formation predicate, lifecycle-to-terminal, precedence, LONG/SHORT
mirror, prefix/restart/duplicate invariance, fail-closed-on-missing-param, null honesty; RC2/RC3
golden vectors for F02–F10; e2e gains a synthetic market-state → structures stage.
**Execution.** Ultracode fan-out (one agent per module family, self-tested), full-suite re-verify.
**Slice.** B03 rows (W03/W04, F02–F10, ORIGIN feature/structure nodes). **Deps.** B02.

---

## B04 · Structure semantics II (G2 — F11–F14, F16–F18)

**Scope.** The second half: gap/block/reclaim structures and flow atoms, plus the lifecycle
reducer.

**Deliverables.**
- `structures/fvg_registry.py` — F11 three-bar fair-value gap + penetration lifecycle.
- `structures/order_block_registry.py` — F12 qualified displacement + F13 causal order block
  (origin + displacement + linked BOS).
- `structures/excursion_reclaim_registry.py` — F14 frozen-level excursion → timed reclaim → hold.
- `structures/flow_atoms.py` — F16 trade-flow imbalance, F17 best-level order-flow imbalance
  (min-depth symbolic → RESEARCH), F18 book depth tilt; no-future-venue law; null honesty.
- Lifecycle reducer (W05): structure lifecycle transitions with illegal-transition rejection.

**Acceptance.** Same proof-obligation battery per module; goldens for F11–F18; e2e stage extends
the walk through gaps/blocks/reclaims/flow. **Execution.** Ultracode fan-out. **Slice.** B04 rows
(W05, F11–F18, lifecycle reducer node). **Deps.** B03.

---

## B05 · Reaction, capsules & candidates (G3 — F15, F19, F20)

**Scope.** Confirmed structures → immutable trade hypotheses → published candidates.

**Deliverables.**
- `reaction_engine.py` — F15 departure + first retest/touch; location → freshness → departure →
  trigger → confirmation → geometry.
- `capsule_host.py` — isolated per-capsule runtime (one formula/parameter/trial identity each).
- `capsules/` — the five capsules (`dc_swing_bos_first_retest.v1`,
  `protected_swing_choch_first_retest.v1`, `fvg_displacement_first_touch.v1`,
  `ob_displacement_bos_first_touch.v1`, `level_excursion_reclaim_flow_confirmed.v1`).
- `opportunity_clusterer.py` — F20 clustering + alias control with the non-circular prospective
  cluster-root law (BLK-RC2-012 disposition per RC3).
- `candidate_publisher.py` — F19 candidate geometry + geometric RR (directional stop-side
  invariant per BLK-RC2-014 disposition), RR ≥ 2.0 floor, immutable `edge_candidate.v2`,
  lifecycle with named abstention + withdrawal (BLK-RC2-013 disposition), forbidden-money-field
  guard.

**Acceptance.** End-to-end synthetic sequence market-state → structures → reaction → candidate,
with RR-floor rejection, withdrawal on invalidation, capsule isolation (no cross-capsule vote),
contract validity; e2e full-funnel stage. **Execution.** Host/engine authored directly; capsules
fanned out. **Slice.** B05 rows (W06, F15/F19/F20, capsule/candidate nodes). **Deps.** B04.

---

## B06 · Lever & four-plane control (RC4 L0–L5)

**Scope.** The RC4 lever/plane law as ORIGIN-side code and data. ORIGIN enforces the law for its
own artifacts and candidate routing; venue-side enforcement is estate-owned and stays named.

**Deliverables.**
- Canonical lever model: `venue_environment {LIVE,TESTNET,OFF}` / `venue_activation {LIVE,OFF}` /
  `paper_activation {LIVE,OFF}` / `shadow_activation` (constant LIVE), case-sensitive, no
  coercion; the 34-alias invalid table as data + parser tests.
- The 32-code refusal registry as data + a pure refusal engine mapping each refusal to its exact
  containment action (from the RC4 bundle) + golden tests per code.
- `engine_control_manifest.v2` validation (exact scopes, no wildcards, digest binding) + lever
  resolver with `lever_cache_max_age_ms` staleness→OFF law (age injected, never wall-clock).
- Runtime lever attestation record shapes + revision fencing (stale revision refusal).
- Shadow-law: ORIGIN dispositions — every rejected shadow-tradeable candidate must produce a
  durable SHADOW disposition record (persist-deadline law as data); tradeability contract;
  no-fabricated-geometry rule; population separation guards (SHADOW/PAPER/TESTNET/LIVE never
  blend in one aggregate).
- ADR-005 supersession record + `10_DECISION_REGISTER` note (L0 slice, in-repo documentation of
  the owner directive; the signed ADR itself is an OPERATOR row).

**Acceptance.** Every refusal code has a triggering test; alias table fully rejected;
lever-combination truth table (10 valid combinations) proven; staleness resolves OFF; e2e gains a
lever/refusal stage. **Slice.** B06 rows (RC4 L0/L2–L5 in-repo). **Deps.** B05 (candidates exist
to route/record).

---

## B07 · Config, wiring & services (G4)

**Scope.** Signed configuration, the comparator/authority control plane, service main.

**Deliverables.**
- `config/` signed artifacts + JSON-Schemas + fail-closed loader with owner/change-control/
  digest: capsules, geometry, lifecycle, regime eligibility, symbols, staleness bounds, latency
  budgets, risk policy (catalog), exit policy (catalog), transport bindings,
  `engine_control_manifest.v2` instance (all levers OFF/DARK), treatment/rollback manifests,
  secret allowlist, compatibility manifest.
- **Parameter registry materialization:** all 192 effective parameter records as a versioned data
  artifact with per-row ratification status; `require()` integration so `PROPOSED_*` /
  `NOT_RATIFIED` rows fail closed at runtime unless a ratified activation bundle supplies them.
- `comparator.py` (side-effect-free divergence → `divergence_record.v1`), `authority_router.py`
  (single-writer, lease-gated, split-brain/stale-epoch rejection), `legacy_bridge.py` (control
  candidate, dark), `replay_runner.py` + CLI (same-code deterministic runner → replay receipt),
  `service/main.py` reaching `READY_NO_AUTHORITY`.

**Acceptance.** Configs validate + digest-pin; comparator has no authority-write import; router
admits exactly one candidate per allocation; service main reaches `READY_NO_AUTHORITY` with zero
side effects; e2e gains config-load + comparator + router + replay-runner stages. **Slice.** B07
rows (W07–W09, parameter declarations, Configuration node). **Deps.** B06.

---

## B08 · Read faces & evidence projections (G5 in-repo, RC4 L6)

**Scope.** Honest read-only evidence, closing CTRL-B08-001's narrowness the right way.

**Deliverables.** Read-only faces for: attestation/activation/lease scope; input offsets/
watermarks/coverage/quality; structure & lifecycle lineage with all clocks; candidate funnel with
named zero reasons; divergence; lever/plane state incl. shadow-health; replay receipts. Honest
`unavailable` for absent dependencies; no secrets; no control verbs; bounded cardinality.

**Acceptance.** Face outputs contract-valid; secret/control-verb absence tests; readiness stays
explicitly `READY_NO_AUTHORITY` with named missing-evidence inputs; e2e stage reads every face.
**Slice.** B08 rows (W23/W25, Observability, MCP & evidence UI, RC4 L6). **Deps.** B07.

---

## B09 · Verification matrix & runbooks

**Scope.** Consolidate verification into the Doc 08 / RC3 registry shape; write runbooks.

**Deliverables.**
- `tests/matrix/` — offline-feasible verification rows tagged with RC3 verification IDs; a
  conformance report tool mapping implemented tests → registry rows (counts by gate).
- Estate-formula catalog (F21–F24): contract shapes + golden vectors only, clearly marked
  CATALOG (no execution semantics in this repo).
- `docs/runbooks/` — migration/rollback/incident/DR runbooks distilled from Doc 09 + RC4 L7
  (procedures only); `docs/VERIFICATION.md` obligations → tests map.

**Acceptance.** Matrix report shows every in-repo verification row either implemented (test ID)
or named-deferred with reason; runbooks cross-linked; e2e unchanged but re-verified. **Slice.**
B09 rows (Tests & evidence, Validation, F21–F24). **Deps.** B08.

---

## B10 · Audit rounds, reports & checkpoint seal

**Scope.** The operator-directed multi-round audit and closure.

**Deliverables.**
- ≥2 independent adversarial audit rounds (ultracode fan-out: spec-conformance auditors per
  milestone slice + falsification hunters + boundary/capability auditors); every finding fixed
  forward or honestly registered.
- `docs/reports/IMPLEMENTATION_REPORT.md` — what was built, evidence, deviations, deferred lanes.
- `docs/reports/CLARIFICATIONS.md` — final consolidated questionnaire (from
  `09_OPEN_QUESTIONS.md`) for the operator to answer.
- Checkpoint seal: `checkpoint/<date>-origin-v7-build` branch + `CHECKPOINTS.md` ledger row;
  milestone receipts for B01–B09 sealed under `evidence/receipts/`.
- Final `04_STATUS.md`.

**Acceptance.** All audits dispositioned; full gate + e2e green on final `main`; checkpoint
branch pushed; reports delivered to the operator. **Deps.** B09.
