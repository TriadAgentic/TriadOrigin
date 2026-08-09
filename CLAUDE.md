# CLAUDE.md — TRIAD ORIGIN E02-V7 repository law

Read [`docs/plan/README.md`](docs/plan/README.md),
[`docs/plan/04_STATUS.md`](docs/plan/04_STATUS.md), and
[`docs/plan/05_RC2_CONFLICT_REGISTER.md`](docs/plan/05_RC2_CONFLICT_REGISTER.md) before changing
this repository.

## Current authority and stop condition

**Updated 2026-08-09 (B00).** The complete control package now exists and is vendored: the RC3
Complete Master Specification (embedding the full RC2 canonical registries and the RC3 effective
control bundle) and the RC4 Four-Plane/Lever Master Addendum live under `docs/spec_rc3/`,
`docs/spec_rc4/`, `docs/spec_rc2/` with extracted machine-readable law in `docs/control/`. The
operator directed on 2026-08-09 (authority rank 1): build the complete ORIGIN V7 engine
end-to-end in this repository, DARK, milestone PRs merged on green, per the B-series plan in
`docs/plan/`. The prior B00 SAFE_HOLD is closed by that directive **for DARK implementation
only** — nothing here arms, activates, or ratifies an activation value; every
`BLOCKING_OWNER_DECISION` / `BLOCKING_RESEARCH_DECISION` / `PROPOSED_*` parameter stays
fail-closed data. Open ambiguities are batched in `docs/plan/09_OPEN_QUESTIONS.md` for the
operator, never resolved silently in code.

Authority order:

1. Operator's authenticated, scoped decisions (incl. the 2026-08-09 build directive).
2. Independent safety and venue/account truth.
3. Signed activation/risk manifests for their exact external scope.
4. RC4 addendum law (four-plane/lever/shadow; supersedes ADR-005 within its scope).
5. RC3 master document + its correction/refusal ledger.
6. RC3 effective control bundle registries (`docs/control/rc3_effective_control_bundle.json`).
7. Incorporated RC1 specification where not superseded.
8. Immutable versioned contracts and state machines.
9. `docs/plan/`.
10. Code, tests, historical docs, diagrams, examples, and comments.

Code never chooses between conflicting sources. A semantic change updates the authoritative
spec/control artifact in a prior PR.

## Repository ownership

- `CONSUME`: W02 canonical E01 state and an externally issued/validated lease.
- `OWN`: W03–W06 plus E02-specific W23–W25 facts.
- `BUILD_DARK_LIBRARY` (operator directive 2026-08-09; homing decision tracked as Q-A7): the
  W07–W09 control-plane pieces — edge comparator (side-effect-free), authority router
  (single-writer selection, lease **verify-only**), frozen legacy bridge (control candidates
  only) and the replay runner — are built here as pure, dark, import-isolated modules with no
  network/process wiring; where their processes deploy is an estate decision.
- `REFERENCE_ONLY` or `OUT_OF_REPO`: W00–W01, W10–W21, E07 decision, E08
  risk/sizing/authorization, E09 command/order/fill/protection, E10 outcome/learning, and
  venue/account truth.
- ORIGIN may verify a lease. It must not issue, activate, coordinate, or supersede one.

Never add a venue client, network control path, credential/private-key loader, order verb, risk or
quantity authorization, money publisher, fill parser, or lease issuer. A healthy current build
reaches only `READY_NO_AUTHORITY`.

## Determinism and contracts

Semantic transitions are pure functions of prior state, ordered input, immutable parameters, and
dependency quality. No wall clock, environment read, file/network I/O, randomness, future data,
floating semantic comparison, unordered output, or silent fallback is permitted on that path.

Published contract bytes never change under the same version. Current producer-epoch equality is
valid; lower epochs reject. Checkpoints authenticate every replay-controlling field. Cross-source
order follows recorded local receipt; source sequences are compared only within a source/connection.
Replay and live consumption must call the same transition implementation.

## Required gate and PR law

Every change runs:

```bash
PYTHONHASHSEED=0 python -m pytest
PYTHONHASHSEED=1 python -m pytest
python tools/collect_test_ids.py
python tools/verify_manifest.py
python tools/validate_contract_manifest.py
python tools/verify_reproducible_build.py
python tools/test_wheel_install.py
python tools/verify_no_forbidden_capabilities.py
python tools/e2e_audit.py
python tools/build_ledger.py --verify
```

**The E2E growth law:** every milestone that lands a capability extends `tools/e2e_audit.py`
with a walk stage for it in the same PR; a capability with no walk stage is an incomplete
milestone.

Use one fresh branch and one PR per build milestone. Merge only after exact-head CI is green and all
actionable review threads are resolved. Then reproduce the checks from fresh merged `main` and seal
the milestone receipt before opening the next build branch. No self-reported test count, workbook
colour, force-push, or off-tree draft is acceptance evidence.
