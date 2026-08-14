# docs/control — The Machine-Readable Build Law

This directory holds the authoritative, machine-readable control artifacts the B-series build is
driven by. Everything here is **data**: nothing in this directory arms, activates, or ratifies
anything.

| File | What it is |
|---|---|
| `rc3_overlay_schema.json` | JSON-Schema for the RC3 normative overlay |
| `rc3_normative_overlay.json` | RC3 corrections/overrides: parameter + formula overrides, DAG/binding/golden-vector operations, named rejections, external prerequisites, receipt v2 requirements |
| `rc3_effective_control_bundle.json` | **The RC3-effective law, pre-RC4 supersession.** RC2 canonical registries with the RC3 overlay applied: 1,115 tasks, 2,249 dependencies, 1,115 criteria, 1,523 verifications, 192 parameter records, 24 formulas, 27 wiring rows, 11 gates, 22 golden vectors, crosswalk + traceability. The ten RC4 supersessions are **not** compiled into this bundle; the post-RC4 effective bundle is `RC5_EFFECTIVE_CONSOLIDATION` (CO-01, **compiled/landed** — `docs/control/rc5_bundle.json`, byte-stable, RC3/RC4 bytes untouched). RC5 **consumption is `GATED_BEHIND_B01C`** (its own provenance), so until B01C opens, machine consumers still read *this* RC3 bundle and must treat the superseded records it still carries (F20 `activation_mode` budgets, boolean PAR-170, W06/G5 connected-dark vocabulary) as superseded, never effective (CO-08 step 3 correction, 2026-08-13; RC5-landed update, 2026-08-13) |
| `rc3_effective_bundle_manifest.json` | Composition manifest (base/overlay/effective SHA-256) |
| `rc3_effective_validation_report.json` | The bundle's own validation report (`PASS` composition, `DENIED_SAFE_HOLD` activation — activation stays denied by design) |
| `rc3_executable_builder.py` | The RC3 document's embedded builder (provenance; not executed by CI) |
| `rc4_control_bundle.json` | RC4 lever addendum law: four-plane law, lever law, shadow law, 32 refusals, 17 timings, 135 LEV tasks, 125 verifications, supersessions, engine census |
| `rc4_addendum_builder.py` | RC4 document builder (provenance) |
| `SOURCE_HASHES.sha256` | SHA-256 pins for every vendored control/spec/report artifact |
| `build_ledger.json` | Generated `CANDIDATE_V3` partition of all 1,250 tasks into build milestones / named lanes — regenerate with `python tools/build_ledger.py`; CI runs `--verify` |
| `build_ledger_overrides.json` | Reviewed reclassifications (take precedence over the heuristic rules) |
| `closure/predecessors/build_ledger.REVIEWED_V2.json` | Exact frozen byte subject of the historical B00C row review; current-row drift is computed against this file |

Extraction provenance: the RC3 artifacts were extracted from the `<script type="application/json">`
blocks embedded in `docs/spec_rc3/…RC3.html` (ids `rc3-overlay-schema`, `rc3-normative-overlay`,
`rc3-effective-control-bundle`, `rc3-effective-bundle-manifest`, `rc3-effective-validation-report`,
`rc3-executable-builder` base64); the RC4 bundle from `rc4-control-bundle` in
`docs/spec_rc4/…RC4.html`. Re-extraction reproduces these bytes.

## B00C · row review + combined DAG (2026-08-09)

> **CO-08 step 3 note (2026-08-13):** the paragraph below is the historical B00C record.
> `build_ledger.json` now carries `CANDIDATE_V3` while `build_ledger_review.v1.json` binds the
> frozen `REVIEWED_V2` subject — the open review-rebinding drift tracked as **CO-05** (the
> review must rebind the exact V3 ledger bytes plus per-row digests). Current-state reads point
> at **V3 + the pending CO-05 rebinding**; neither this section nor the RC3 bundle is the
> post-RC4 effective law.

The historical ledger is `REVIEWED_V2`: the reconciled plan's corrections are applied to the rule
table (F01/F07 → E01 estate lane; four-plane substrate → B05; capsules/candidates → B06), and every
one of its 1,250 rows carries a reviewer/disposition record in `build_ledger_review.v1.json`.
That review is byte-bound to `closure/predecessors/build_ledger.REVIEWED_V2.json`; it does not
review the current `CANDIDATE_V3` ledger or its target allocations. `--verify` fails if the frozen
subject/review relationship is incomplete and reports current drift as review-required.
`tools/validate_combined_dag.py` validates
the combined RC3+RC4 composition: referential closure, cycle freedom, one scheduling owner per
task, source-authority preservation, reviewed inversion classes, and cross-lane blocker
visibility. Neither artifact marks any task complete.
