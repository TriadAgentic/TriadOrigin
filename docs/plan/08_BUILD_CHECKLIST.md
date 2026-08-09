# 08 · Master Build Checklist

_The human-readable face of the machine ledger
([`docs/control/build_ledger.json`](../control/build_ledger.json), 1,250 rows). The ledger is
truth; this checklist is the working summary. Boxes tick only when the owning PR is merged
green._

## B00 · Authority & control baseline
- [x] Extract + vendor RC3 overlay/effective bundle/manifest/validation + builders
- [x] Vendor complete RC2 package (checklist, wiring, declarations, workbook, index)
- [x] Vendor RC4 addendum + control bundle; vendor sign-off + cross-engine reports
- [x] SHA-256 source inventory (`docs/control/SOURCE_HASHES.sha256`)
- [x] `tools/build_ledger.py` + generated ledger + overrides file + CI verify
- [x] `tools/e2e_audit.py` v0 (9 stages green) + CI wiring
- [x] Plan rewrite (00/01/04/06) + this checklist + `09_OPEN_QUESTIONS.md`
- [x] `CLAUDE.md` authority update (operator directive 2026-08-09)
- [x] PR merged green (#8, squash `1217297`); branch reset on fresh main

## B01 · Foundation corrections (G0)
- [x] Typed identity v2 (field-type tags) + migration vectors; v1 IDs stable
- [x] `engine_attestation.v2` equality law + corrected goldens
- [x] Bundle descriptor v2 (media types) — RC1/R00 descriptor bytes frozen; additive supersession law in `verify_manifest`
- [x] Strict receipt schemas v2 (`evidence_receipt.v2` · `task_status_event.v2` · `gate_receipt.v2` + semantic PASS conditionals)
- [x] RC4 L2 contracts: `engine_control_manifest.v2` (lever-combination law) · `runtime_lever_registry.v1` · `runtime_lever_attestation.v1` · `shadow_trade.v1` · `shadow_rejection_audit.v1` · `paper_trade.v1` · `shadow_health.v1` · `execution_authorization.v3`; `fill.v3`→3.1.0 (+TESTNET) · `execution_cmd.v2`→2.1.0 (+environment/activation-revision); registry + manifest re-pin (127 artifacts, 42 contracts)
- [x] Epoch-law regression audit (current accepted / lower rejected; new authority contracts epoch-fenced)
- [x] B-series milestone receipt law (`tools/validate_b_receipt.py`) + B00 receipt sealed
- [x] R00 ceremony tests repointed to the frozen R00-era fixture (`tests/fixtures/r00_state`)
- [ ] e2e: identity-v2 + lever-law + receipt stages · PR merged green

## B02 · Kernel hardening
- [ ] Ledger external durable anchor + tail-deletion/replacement falsification
- [ ] Cold/warm exactly-once parity evidence
- [ ] Per-scope fence state sealed in checkpoint, restored before consumption
- [ ] RC4 timing registry (17 bounds) as data + loader
- [ ] F00 golden vectors on `instrument_math`
- [ ] e2e: anchor + fence-restore stages · B01 receipt · PR merged green

## B03 · Structure semantics I (F01–F09)
- [ ] `feature_primitives.py` (F01 bars, F02 ATR, F05 rolling extremes)
- [ ] `structures/typed_level_registry.py` (F03 DC swing, F04 fractal, F06 equal-level*, F07 session)
- [ ] `structures/structure_state.py` (F08 structure/protected swing*, F09 break/BOS/CHOCH)
- [ ] Proof-obligation battery ×3 modules + RC goldens F01–F09
- [ ] `structure_atom.v2` emission wired to journal
- [ ] e2e: market-state → structures stage · B02 receipt · PR merged green
  \* research-blocked parameters symbolic, named abstention

## B04 · Structure semantics II (F10–F13, F15–F17)
- [ ] `structures/fvg_registry.py` (F10)
- [ ] `structures/order_block_registry.py` (F11+F12)
- [ ] `structures/excursion_reclaim_registry.py` (F13)
- [ ] `structures/flow_atoms.py` (F15, F16*, F17)
- [ ] Lifecycle reducer (W05) + illegal-transition rejection
- [ ] Proof-obligation battery ×4 modules + goldens F10–F17
- [ ] e2e: gaps/blocks/reclaims/flow stage · B03 receipt · PR merged green

## B05 · Reaction, capsules & candidates (F14, F18, F19)
- [ ] `reaction_engine.py` (F14) · `capsule_host.py` · 5 capsules
- [ ] `opportunity_clusterer.py` (F19, non-circular cluster root)
- [ ] `candidate_publisher.py` (F18, RR≥2.0, stop-side invariant, withdrawal, forbidden-field guard)
- [ ] Isolation proof (no cross-capsule vote) + full-funnel synthetic test
- [ ] e2e: full-funnel stage · B04 receipt · PR merged green

## B06 · Lever & four-plane control (RC4)
- [ ] Lever enums + alias rejection (34) + 10-combination truth table
- [ ] 32-code refusal registry + containment engine + per-code tests
- [ ] `engine_control_manifest.v2` validation + lever resolver (staleness→OFF)
- [ ] Attestation records + revision fencing
- [ ] SHADOW disposition recorder + tradeability contract + population guards
- [ ] ADR-005 supersession decision-register entry
- [ ] e2e: lever/refusal stage · B05 receipt · PR merged green

## B07 · Config, wiring & services
- [ ] Signed config artifacts + schemas + fail-closed loader (15 artifact families)
- [ ] Parameter registry materialization (192 rows, status-labelled, digest-pinned)
- [ ] `comparator.py` · `authority_router.py` · `legacy_bridge.py` · `replay_runner.py`
- [ ] `service/main.py` → `READY_NO_AUTHORITY`
- [ ] e2e: config + comparator + router + replay stages · B06 receipt · PR merged green

## B08 · Read faces & evidence
- [ ] Evidence faces (attestation/offsets/lineage/funnel/divergence/lever/shadow-health/receipts)
- [ ] Honest `unavailable`; no secrets; no control verbs; bounded cardinality
- [ ] Readiness truth inputs named (closes CTRL-B08-001 narrowness)
- [ ] e2e: read-face stage · B07 receipt · PR merged green

## B09 · Verification matrix & runbooks
- [ ] `tests/matrix/` tagged with RC3 verification IDs + conformance report tool
- [ ] F20–F23 estate-formula catalog vectors (CATALOG marked)
- [ ] `docs/runbooks/` + `docs/VERIFICATION.md`
- [ ] B08 receipt · PR merged green

## B10 · Audit rounds, reports & seal
- [ ] Adversarial audit round 1 (spec conformance per milestone slice)
- [ ] Adversarial audit round 2 (falsification hunt + capability boundary)
- [ ] All findings fixed forward or registered
- [ ] `IMPLEMENTATION_REPORT.md` + `CLARIFICATIONS.md` delivered
- [ ] Receipts B01–B09 sealed · checkpoint branch + `CHECKPOINTS.md` row
- [ ] Final status + operator handoff
