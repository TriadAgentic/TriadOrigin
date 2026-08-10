# CLAUDE.md — TRIAD ORIGIN E02-V7 repository law

Read [`docs/plan/README.md`](docs/plan/README.md),
[`docs/plan/04_STATUS.md`](docs/plan/04_STATUS.md), and
[`docs/plan/05_RC2_CONFLICT_REGISTER.md`](docs/plan/05_RC2_CONFLICT_REGISTER.md) before changing
this repository.

## Current authority and stop condition

**Updated 2026-08-09 (B00C).** The complete control package is vendored (RC2/RC3/RC4 under
`docs/spec_*/` with machine law in `docs/control/`), and the operator supplied a **reconciled
plan baseline** (`docs/plan/00…10`, incl. `10_MASTER_SPEC_ALIGNMENT_AUDIT.md`) correcting the
uploaded plan's P0 defects. Controlling states: `AUTHORIZED_OFFLINE_IMPLEMENTATION_ONLY` for
repository work; activation result **`DENIED_SAFE_HOLD`** always. The required non-authoritative
baseline manifest is exactly `venue_environment=OFF / venue_activation=OFF / paper_activation=OFF
/ shadow_activation=LIVE` (`shadow_activation` fixed LIVE, not switchable; `DARK` and every
RC4-invalid alias are refusals, not states). Key reconciled laws: **F01 finalized bars and F07
UTC session levels are E01-owned — ORIGIN consumes/validates, never authors**; the four-plane
substrate (B05) precedes any candidate publisher (B06); F20 consumes one already-selected signed
policy (no environment/rollout input); no guessed ordinal↔semantic capsule mapping; every
`BLOCKING_OWNER_DECISION` / `BLOCKING_RESEARCH_DECISION` / `PROPOSED_*` parameter stays
fail-closed data with named abstention. Decisions live in `docs/plan/09_OPEN_QUESTIONS.md` — a
**disposition register** with per-row due-before milestones, never resolved silently in code.

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
python tools/validate_combined_dag.py
python tools/validate_b_receipt.py --all --strict
python tools/verify_spec_control_counts.py --strict
python tools/scan_secrets.py --tracked --fail-on-hit
```

These fourteen commands are the authoritative gate — the frozen audit runner's
`REQUIRED_LOCAL_COMMANDS` and the `.github/workflows/ci.yml` source-PR steps enumerate the same
fourteen. The prose above is the currency mirror; on any drift the frozen runner + CI are the
source of truth (register row E46).

**The E2E growth law:** every milestone that lands a capability extends `tools/e2e_audit.py`
with a walk stage for it in the same PR; a capability with no walk stage is an incomplete
milestone.

Use one fresh branch and one **source PR** per build milestone; merge only after exact-head CI is
green and all actionable review threads are resolved. After the source PR merges, reproduce the
checks against the exact merged `main` hash and land a **separate evidence-only receipt PR**; the
next milestone branch may not open until that receipt is merged and validated (the one-behind
scheme is rejected — reconciled plan §9.3). A code-merge receipt and a gate receipt are distinct;
no Track A milestone is a G-gate pass. No self-reported test count, workbook colour, force-push,
or off-tree draft is acceptance evidence.
