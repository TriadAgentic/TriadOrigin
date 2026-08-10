# 01 · Milestone Breakdown — Reconciled B-Series and Estate Gates

_Revision: 2026-08-09 · Formula IDs and owners follow the RC3 effective registry; RC4 controls
apply last. “Gate correspondence” never means a gate has passed._

## Common entry and exit law

Every repository milestone requires:

- a reviewed, dependency-closed task slice with source authority preserved;
- task → criterion → verification links created in the same PR;
- full unit/falsification suite under both required hash seeds;
- exact collection identity, immutable manifest/schema validation, reproducible build, wheel
  smoke, capability/import boundary scan, build-ledger validation, and the growing end-to-end walk;
- zero unresolved P0/P1 findings in its scope;
- a source PR merged on current exact-head CI; and
- a post-merge, evidence-only receipt over the actual merged hash before the next branch opens.

The milestone result is `IMPLEMENTED_UNVERIFIED / DENIED_SAFE_HOLD` until its estate gate has a
separate valid receipt. A blocked mandatory verification remains blocked; it is never counted as
complete because it was named.

## Track A · TriadOrigin repository

### B00 · Historical control-package import — source merged, receipt open

**Recorded outcome.** RC2/RC3/RC4 sources, initial machine ledger, build tools, and the uploaded
plan set were merged in PR #8 at commit `121729751dcd23addce897e4d81c35283a40562c` with successful
CI run `31293420164`.

**Not closed.** The post-merge B00 receipt is absent, the earlier R00 receipt is absent, branch
protection issue #5 remains open, and the uploaded plan/ledger contain material spec drift.

**Status.** `B00_SOURCE_MERGED`; `B00_RECEIPT_OPEN`; B01 blocked.

---

### B00C · Corrective control closure — required before B01

**Scope.** Repair the planning/control layer before semantic implementation consumes it.

**Deliverables.**

- Replace the five plan files with this reconciled set and add the alignment audit.
- Correct every formula/owner reference to F00–F23; prove no F24 reference remains.
- Review all 1,250 scheduling rows. The existing `HEURISTIC_V1` assignment may suggest a lane but
  cannot be represented as reviewed without a row-level reviewer/disposition record.
- Validate the combined RC3+RC4 DAG for referential closure, cycles, milestone inversions,
  cross-lane blockers, one scheduling owner, and preservation of source owner/gate/dependency.
- Land strict additive `evidence_receipt.v2`, `task_status_event.v2`, and `gate_receipt.v2`
  schemas plus semantic validator and invalid fixtures.
- Configure the `main` ruleset required by issue #5, or attach a signed, time-bounded waiver that
  supplies equivalent exact-head/review/no-bypass evidence.
- Resolve the R00 ceremony by either sealing R00 under its existing law or issuing a signed
  supersession that maps every R00 field and invariant into receipt v2. No silent waiver.
- Seal a post-merge B00 receipt against the actual current `main` hash.
- Add `required_before_milestone`, decision owner, status, evidence, and failure behavior to every
  parameter/question row.

**Acceptance evidence.**

- formula registry equality test passes against RC3;
- combined DAG/ledger validator passes with reviewer identity and digest;
- invalid receipt combinations fail semantic validation;
- branch ruleset or waiver evidence is current;
- R00 disposition and B00 receipt exist, validate, and reference current immutable evidence.

**Exit.** `B00_RECEIPT_PASS`; only then may B01 open.

---

### B01 · Contract, identity, and binding foundation

**Scope.** Close inherited foundation defects and make every downstream semantic dependency
machine-verifiable.

**Deliverables.**

- Typed identity v2 with field-type-tagged framing and migration vectors; v1 IDs remain stable.
- Additive `engine_attestation.v2` with envelope/payload equality and corrected goldens.
- Additive bundle descriptor v2 with corrected media types; inherited bytes unchanged.
- Immutable schema catalog and valid/invalid fixtures for the RC3 contracts used by ORIGIN.
- All ten RC4 contracts, including controlling `execution_authorization.v3` and strict `fill.v3`.
- `binding.v2` schema and semantic validator covering slot, cardinality, condition, scope,
  precedence, consuming node/edge, overlap, and digest identity.
- Structural migration of all 105 effective bindings. Preserve the source states: blocked rows do
  not become active merely because they are encoded in v2.
- Compatibility manifest and producer-lease verification rules. ORIGIN issues neither technical
  writer nor money-selection authority.
- Epoch-law regression tests: current exact epoch accepted; stale/lower/wildcard/mismatched scope
  rejected.

**Acceptance evidence.** Every schema has positive and negative fixtures; the bundle is
byte-pinned; all 105 bindings are accounted for; the semantic validator detects overlap,
cardinality, precedence, and scope defects; no blocked binding is consumable.

**Gate correspondence.** G0 subset only. **Dependency.** B00C receipt.

---

### B02 · Deterministic kernel and E01 interfaces

**Scope.** Harden the journal/checkpoint/fencing substrate and implement only the formula work
owned by the repository.

**Deliverables.**

- F00 exact tick/step conversion with integer/rational boundary vectors.
- `market_state.v2` and E01-produced F01 finalized-bar/F07 UTC-session validators and adapters;
  ORIGIN does not author either fact.
- External durable journal anchor binding with chain head, segment, offset, file identity, and
  recovery receipt; tail-deletion/replacement falsification.
- Per-scope accepted-token high-water sealed into checkpoints and restored before consumption.
- Deterministic partition/watermark coordinator, semantic checkpoint, replay receipt, and honest
  readiness inputs.
- All 17 RC4 timing bounds imported as versioned data; age/time injected into pure consumers.

**Acceptance evidence.** Cold/warm/restart exactly-once parity; deletion/replacement detected;
stale token rejected across restart; F00 boundaries pass; malformed or provisional E01 facts
quarantine; host timezone cannot redefine a session.

**Gate correspondence.** G0/G1 subset. **Dependency.** B01 receipt.

---

### B03 · Causal features and directional structure — F02–F09

**Scope.** Build the first causal structure layer while refusing output that depends on unresolved
research or parameter bindings.

**Deliverables.**

- F02 true range/trailing ATR using finalized bars strictly before the evaluation origin.
- F03 directional-change swing.
- F04 closed fractal pivot with strict tie rejection.
- F05 trailing rolling extreme.
- F06 anchored equal-level cluster interface and named abstention until
  `EQUAL_LEVEL_MAX_SPAN` is measured and ratified.
- F08 directional structure/protected-swing interface and named abstention until an exact reducer
  version and goldens are ratified.
- F09 generic accepted-break primitive; BOS/CHOCH labels emit only when F08 state is valid.
- Append-only `structure_atom.v2` and `structure_transition.v2` publication.
- Consume, never author, E01 F07 session levels.

**Acceptance evidence.** Formation/confirmation separation; no lookahead; prefix/restart/duplicate
invariance; LONG/SHORT mirror; exact boundary vectors; blocked parameter causes the specified
named abstention; no substitute/default; lifecycle and ID stability.

**Hard blockers.** Every consumed `binding.v2` row, PAR-036/F03 if still unresolved, F05 goldens,
F06 research value, F08 reducer/goldens, and E01 source evidence. Interfaces/refusals may land;
semantic result access may not.

**Gate correspondence.** G2 subset. **Dependency.** B02 receipt.

---

### B04 · Gaps, blocks, reclaim, and flow — F10–F13, F15–F17

**Scope.** Complete the remaining structure and microstructure primitives plus the lifecycle
reducer.

**Deliverables.**

- F10 three-bar FVG and penetration lifecycle.
- F11 qualified displacement.
- F12 causal order block linked to same-direction accepted BOS.
- F13 frozen-level excursion and timed reclaim.
- F15 trade-flow imbalance.
- F16 best-level order-flow imbalance.
- F17 depth tilt interface and named abstention until
  `BOOK_TILT_MIN_QUOTE_DEPTH` is measured and ratified.
- Append-only lifecycle reducer with invalid-transition rejection, withdrawal, expiry, and frozen
  original geometry.

**Acceptance evidence.** Same-bar/future-touch rejection; first-qualifying-event law; TTL
boundaries (F10 invalidation-rule binding NOT delivered — register E36/F10-1); missing/gapped
market data refusal; exact mirror; restart parity;
no-future-venue-state law; all formula-specific goldens.

**Hard blockers.** F10 TTL/invalidation, F11/PAR-158, F12 zone/TTL/goldens, F13 parameter set,
F16 goldens, F17 measured depth, and every corresponding binding. Blocked emitters stay silent.

**Gate correspondence.** G2 subset. **Dependency.** B03 receipt.

---

### B05 · Four-plane substrate before candidate publication

**Scope.** Implement RC4's control, capture, PAPER, and health substrate before any deployable
candidate publisher exists.

**Deliverables.**

- Exact lever enums; fixed `shadow_activation=LIVE`; all 35 invalid aliases imported from the
  signed bundle; all 10 valid combinations; all 32 refusal codes and exact containment actions.
- Strict `engine_control_manifest.v2` validation, revision fencing, digest/scope binding, and
  staleness-to-OFF resolution.
- Required baseline manifest: `OFF/OFF/OFF/LIVE` in the field order defined in the master plan.
- Durable SHADOW outbox/ledger, `shadow_rejection_audit.v1`, causal resolver, heartbeat, backlog,
  coverage, persistence deadline, and recovery.
- SHADOW model identity: frozen pre-disposition geometry/watermark, fixed evaluation notional,
  versioned latency/fill/fee/funding/slippage assumptions, bps/R output, and honest `NO_FILL`.
- Keyless PAPER executor with separate virtual order/fill/position/outcome ledger; static and
  runtime proof that it has no venue adapter or credential path.
- Physical identity/storage/query/aggregate separation for SHADOW, PAPER, TESTNET, and LIVE.
- Health law: missed SHADOW persistence deadline or stale writer/resolver forces effective venue
  and PAPER activation `OFF`; SHADOW recovery continues.
- ADR-005 supersession artifact prepared for owner signature. No non-OFF activation is possible
  without the signed ADR and gate receipt.

**Acceptance evidence.** Every alias and refusal fixture; typed null/boolean/integer and whitespace
negative cases; staleness/revision/scope failures; writer/resolver crash; missed persistence;
backlog/coverage failure; no venue side effect; PAPER keylessness; population-separation queries.

**Gate correspondence.** RC4 L0–L6 repository subset. **Dependency.** B04 receipt.

---

### B06 · Reaction, semantic capsules, and candidate publication — F14, F18, F19

**Scope.** Turn confirmed causal structures into complete immutable hypotheses with mandatory
SHADOW capture and no money authority.

**Deliverables.**

- F14 location → freshness → departure → first retest/touch reaction engine.
- F18 candidate geometry and exact geometric RR with directional stop invariant and RR ≥ 2.0.
- F19 clustering with a frozen earliest prospective root ordered by
  `(availability, candidate_id)`; no re-rooting.
- Explicit semantic capsule registry using stable semantic IDs:
  - `dc_swing_bos_first_retest.v1`
  - `protected_swing_choch_first_retest.v1`
  - `fvg_displacement_first_touch.v1`
  - `ob_displacement_bos_first_touch.v1`
  - `level_excursion_reclaim_flow_confirmed.v1`
- No guessed ordinal mapping from RC2 `CAP01_*…CAP05_*` parameters. Replace them with explicit
  semantic-ID-bound parameter rows or keep the capsule unavailable.
- Isolated capsule host: no voting/ensemble, one formula/parameter/trial identity per instance.
- `edge_candidate.v2` publication and append-only withdrawal/expiry/data-invalid transitions;
  forbidden-money-field guard.
- Atomic SHADOW fork for `REJECTED`, `ACCEPTED_NOT_EXECUTED`, and—only after authoritative
  reconciliation—`PROVEN_NO_VENUE_EFFECT`. Malformed inputs go to
  `shadow_rejection_audit.v1/SHADOW_UNTRADEABLE`.
- Preregistered trial family and leave-one-conjunct ablations before result access.

**Acceptance evidence.** Full synthetic causal walk; no candidate path without durable SHADOW
write; persistence failure containment; RR boundary and one-tick stop tests; capsule isolation;
withdrawal; cluster-root stability; trial/result-access refusal; zero money/venue capability.

**Gate correspondence.** G3 subset. **Dependency.** B05 receipt and semantic parameter closure.

---

### B07 · Signed configuration, comparison, and replay services

**Scope.** Materialize configuration and zero-venue-capability services without crossing E07.

**Deliverables.**

- Signed, schema-validated configuration for capsules, geometry, lifecycle, regime eligibility,
  symbols, staleness, timing, selected-policy references, transport bindings, compatibility,
  treatment/rollback, secrets allowlist, and exact four-plane manifest.
- All 192 parameter rows materialized with source status and digest. `require()` refuses
  `PROPOSED_*`, `NOT_RATIFIED`, stale, missing, or scope-mismatched values.
- `comparator.py`, side-effect-free, with independent axes:
  `engine_cohort={LEGACY_COMPARATOR,ORIGIN_CANDIDATE}` and
  `intelligence_arm={DETERMINISTIC_CONTROL,INTELLIGENCE_TREATMENT}`.
- Replace the misleading `authority_router.py` admission behavior with
  `authority_fact_verifier.py`: verify externally issued `candidate_authority.v1` and a technical
  writer lease; never admit/arbitrate candidates, issue leases, or select money authority.
- Frozen legacy bridge that preserves source omissions and exact bytes; no semantic repair.
- Same-code deterministic replay runner with exact tape/config/build/checkpoint/output receipt.
- Service main that reaches `READY_NO_AUTHORITY` only when its declared inputs are current and has
  no venue/order/credential imports.

**Acceptance evidence.** Config/digest/scope failure tests; two-axis type safety; exact-offset
comparison; stale/split-brain fact rejection; bridge restart/omission tests; replay identity;
capability scan; zero side effect.

**Gate correspondence.** G4 repository subset. **Dependency.** B06 receipt.

---

### B08 · Exact read faces and evidence projections

**Scope.** Build honest, read-only evidence surfaces; this is not G5 prospective proof.

**Deliverables.**

- `get_engine_lever_registry`
- `get_engine_lever_attestation`
- `get_engine_lever_history`
- `get_shadow_health`
- `get_four_plane_status`
- `get_engine_inventory_reconciliation`
- Read-only projections for contract/config/build identity, input offsets/watermarks/quality,
  structure/lifecycle lineage, candidate funnel and named zeros, trial/result-access state,
  divergence, replay, receipts, and readiness.
- Requested/effective/proof fields shown separately; SHADOW activation shown separately from
  SHADOW health.
- Named `UNAVAILABLE`/`NOT_MEASURABLE` with source, freshness, and completeness; never empty green
  or substituted zero.

**Acceptance evidence.** Read-only/capability scan; no secret/control verbs; bounded queries and
cardinality; stale/unavailable dependencies; plane/population filters; every response identifies
source and freshness.

**Gate correspondence.** G5 evidence-surface subset. **Dependency.** B07 receipt.

---

### B09 · Conformance matrix, estate formula catalog, and runbooks

**Scope.** Consolidate—not retroactively create—traceability, and publish estate interface
artifacts without implementing foreign authority.

**Deliverables.**

- Conformance view accounting for 408 inherited RC1 tests, 1,523 RC3 effective verifications, and
  125 RC4 fixtures, each linked to task/criterion/gate and current result.
- F20 E08 sizing contract and vectors using one already-selected signed policy reference/digest;
  no environment/rollout input and no RC3 `activation_mode` branch.
- F21 E09 maker compilation vectors; F22 E09 reduction-only emergency IOC vectors; F23 E10
  outcome/P&L/cost/R/markout vectors. Mark all owning implementations `ESTATE`.
- Migration, rollback, split-brain, SHADOW degradation, PAPER isolation, TESTNET, incident,
  fill-lineage, reconciliation, protection, and disaster-recovery runbooks.

**Acceptance evidence.** No F24; no mandatory blocked test reported green; registry equality;
F20 rejects missing/invalid selected policy and ignores environment metadata; runbooks contain
owner, trigger, stop, rollback, evidence, and escalation.

**Gate correspondence.** G6 interface subset. **Dependency.** B08 receipt.

---

### B10 · Independent audits, terminal receipt, and local checkpoint

**Scope.** Close the repository program honestly without implying estate certification.

**Deliverables.**

- At least two independent audit rounds: authority/spec/DAG conformance; then falsification,
  four-plane, capability, and evidence-integrity attack.
- Every finding fixed forward or recorded as a blocking deviation with owner and consuming gate.
- Implementation report separating built, verified, blocked, estate-owned, and operator-owned.
- Updated status and decision registers.
- Source PR merge, then detached post-merge B10 receipt over the exact merge hash.
- TriadOrigin-local checkpoint only after the terminal receipt; G9 later owns the estate-wide
  checkpoint.

**Acceptance evidence.** No unresolved P0/P1 in repository scope; all code receipts current; full
suite reproducible on merged main; checkpoint references the terminal receipt. Activation remains
`DENIED_SAFE_HOLD` unless separate estate gate receipts exist.

## Track B · Estate integration and certification milestones

Track B uses one PR per affected owning repository per gate, followed by one cross-repository gate
receipt. It may proceed in parallel only when it does not consume a blocked Track A output.

### G-1 · Security and as-built truth

- Rotate/revoke exposed or stale credentials; record fingerprints, never secrets.
- Attest account, venue environment, position mode, permissions, routes, writers, processes,
  deployed/source/config/contract digests, clocks, storage, and network reachability.
- Freeze scope and declare all unavailable evidence. NATS/Prometheus absence is blocking where a
  gate requires them.

### G0 · Estate contract and authority foundation

- Deploy strict schemas/validators, manifests, leases, quarantine, compatibility, and receipts at
  every authoritative boundary.
- Prove only the named producer can publish each fact; schema compatibility grants no authority.

### G1 · Binance ingress and canonical state

- Re-verify current official routes and limits at gate time.
- Implement deterministic sharding/reconnect, raw-before-normalize, U/u/pu local-book bootstrap,
  gap reset, finalized bars, UTC session levels, instrument metadata, and replay.
- Produce current freshness, clock, and data-quality receipts.

### G2 · Semantic readiness

- Close every consumed formula parameter/binding/golden blocker.
- Prove identical input ranges, watermarks, causality, restart, scale/mirror, and named abstention.

### G3 · Trial-integrity candidate proof

- Freeze semantic capsule registry and dependency-closed parameter bundle.
- Preregister hypotheses/families and leave-one-conjunct ablations before result access.
- Prove complete immutable hypotheses, lifecycle, clustering, isolation, and zero money authority.

### G4 · Paired replay and divergence

- Freeze legacy and ORIGIN builds/configs and exact input offsets.
- Classify missing/extra/retimed/reidentified/geometry/lifecycle/unexplained divergence.
- Run restart/gap/fault campaigns, chronological OOS, PBO/DSR/multiplicity controls, and maker-fill
  calibration.

### G5 · Prospective OFF/OFF/OFF/LIVE operation

- Run a frozen prospective window with physical venue denial, current SHADOW writer/resolver
  health, complete capture, PAPER disabled, and honest read faces.
- Any side effect, stale health, missing capture, or unmeasurable dependency fails the gate.

### G6 · Risk, execution, money, and outcome rehearsal

- E07 admission/arbitration, E08 selected-policy sizing/reservation, E09 maker execution and
  strict fill.v3/reconciliation/protection, and E10 outcomes.
- Prove quantity/P&L conservation, account mode, ambiguous-submit containment, late fills,
  reductions, and complete lineage.

### TESTNET · Same-digest venue certificate

- Promote the same signed build/config/contracts/parameters from OFF/PAPER rehearsal into isolated
  TESTNET; no semantic rebuild.
- Prove venue routing, private lifecycle, filters, fills, reconciliation, protection, stop, and
  rollback. TESTNET must pass before LIVE.

### G7 · One isolated canary

- Exactly one semantic capsule, instrument, side, and isolated account/risk cell.
- Owner-signed canary risk/stop values, current strict lineage, physical isolation, and automatic
  stop/rollback. No scope expansion during the evidence window.

### G8 · Economic proof

- Use strict fill.v3/outcome lineage and disjoint SHADOW/PAPER/TESTNET/LIVE populations.
- No money win rate or EV may be computed from the dated fill.v1 snapshot; unresolved lineage is
  `NOT_MEASURABLE`.

### G9 · Production decision and cutover

- Owner-sign production risk budget and gross exposure cap only after G8.
- Move one progressive scope step at a time; prove monitoring, stop, rollback, and current
  receipts.
- Seal the estate-wide checkpoint across every affected repository and process.

