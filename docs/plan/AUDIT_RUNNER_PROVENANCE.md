# AUDIT RUNNER PROVENANCE — the frozen independent audit runner is deployed BESIDE the repo

The independent B01–B10 audit runner is **not a repository artifact**. It is the frozen,
externally-authored law that judges this repository; committing it inside the tree it audits would
(a) let a repository PR silently alter its own judge, and (b) trip the tracked-file secret scan on
the runner's own `subprocess.Popen(..., start_new_session=...)` construct (the `session_assignment`
pattern has no word boundary on its trigger alternatives, so the trailing `session` inside
`start_new_session` anchors a false positive — see `docs/reports/scan_secrets_self_hit_report.md`,
hit #1). Untracking the runner is what clears that self-hit.

## Frozen pin (the only bytes the repository trusts)

| Field | Value |
|---|---|
| File | `audit_package/triad_origin_b01_b10_audit.py` |
| Tool version | `1.2.0` (`TOOL_VERSION`, runner source line 64) |
| SHA-256 | `12c8896479b902165fa2c6d3e7565ea8402b49fcfe2d044f6fd69153926d35a2` |
| Tracking status | **UNTRACKED** — `audit_package/` is git-ignored (see `.gitignore`) |

Every repository-local mirror of a runner law pins this exact SHA-256 before it trusts the runner
bytes, and refuses to run a differential against any other bytes:

- `tools/scan_secrets.py` — the tracked-file secret scan (`TEXT_SUFFIXES`, `SECRET_PATTERNS` copied
  verbatim from runner L243-270).
- `tools/verify_spec_control_counts.py` — the RC1/RC3/RC4 count reconciliation
  (`EXPECTED_*` pinned from runner L110-122).
- `tools/jcs_canonical.py`, `tools/ed25519_verify.py`, `tools/build_profile_decision.py`,
  `tools/build_trust_registry.py`, `tools/build_receipt_v3.py` — the receipt-ceremony draft tooling
  (verify-only; no signing key material ever lives in this repo — GOV-level signing is an operator
  act, tracked in `docs/plan/09_OPEN_QUESTIONS.md` E31/E32).
- `tests/tools/*.py` — the differential proofs. Every one is **sibling-or-skip**: it resolves the
  runner relative to the repo root and skips cleanly (`pytest.skip(..., allow_module_level=True)`
  for module-level differentials, a skipping fixture/helper otherwise) when
  `audit_package/triad_origin_b01_b10_audit.py` is absent — so a fresh clone / CI checkout skips the
  differentials, and they run only when the operator deploys the runner beside the repo.

## The deploy-beside law (operator-side)

When the operator runs the frozen audit, the runner is placed beside the repository checkout and
executed against it. The runner's own **policy-document-sync** check
(`validate_policy_document_sync`, runner L880-902) reads its `WORK_ORDER_FILENAMES` from
`pathlib.Path(__file__).resolve().parent` — i.e. **from the runner's own directory** — and requires
the **ten** milestone work-order / checklist markdown files to sit next to the runner, each
containing every one of its `WORK_PACKAGES[milestone]` source IDs (for B10, the eight B10 markers).
The ten owed files are:

| Milestone | File (must sit beside the runner) |
|---|---|
| B01 | `01_B01_CONTRACT_IDENTITY_BINDING_CLEANUP_WORK_ORDER.md` |
| B02 | `02_B02_KERNEL_E01_INTERFACE_CLEANUP_WORK_ORDER.md` |
| B03 | `03_B03_FEATURE_STRUCTURE_CLEANUP_WORK_ORDER.md` |
| B04 | `04_B04_STRUCTURE_FLOW_LIFECYCLE_CLEANUP_WORK_ORDER.md` |
| B05 | `05_B05_FOUR_PLANE_SUBSTRATE_CLEANUP_WORK_ORDER.md` |
| B06 | `06_B06_REACTION_CAPSULE_CANDIDATE_BUILD_CHECKLIST.md` |
| B07 | `07_B07_CONFIGURATION_COMPARISON_AUTHORITY_REPLAY_BUILD_CHECKLIST.md` |
| B08 | `08_B08_READ_FACES_AND_EVIDENCE_PROJECTIONS_BUILD_CHECKLIST.md` |
| B09 | `09_B09_CONFORMANCE_FORMULA_CATALOG_RUNBOOKS_BUILD_CHECKLIST.md` |
| B10 | `10_B10_INDEPENDENT_AUDIT_TERMINAL_RECEIPT_CHECKPOINT_CHECKLIST.md` |

These are governance work-order documents that live with the runner, not with the code; providing
them beside the deployed runner is an operator act (owed, tracked in `docs/plan/09_OPEN_QUESTIONS.md`
E32). This repository does not commit them for the same reason it does not commit the runner: the
repository must not carry the artifacts that judge it.

## What this does NOT change

Untracking the runner changes no repository behavior on the machine-law gate: the ten CLAUDE.md gate
commands, the CI source/receipt step names, and the tools above are all present and byte-stable. The
runner remains the single source of truth for every mirrored law; the repository only ever holds
verify-only mirrors pinned to the SHA-256 above.
