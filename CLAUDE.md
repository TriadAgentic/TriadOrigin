# CLAUDE.md — TRIAD ORIGIN E02-V7 repository law

Read [`docs/plan/README.md`](docs/plan/README.md),
[`docs/plan/04_STATUS.md`](docs/plan/04_STATUS.md), and
[`docs/plan/05_RC2_CONFLICT_REGISTER.md`](docs/plan/05_RC2_CONFLICT_REGISTER.md) before changing
this repository.

## Current authority and stop condition

The code and vendored `docs/spec/` originated from RC1. The supplied RC2 control package is an
incomplete, internally contradictory `RATIFICATION_CANDIDATE_NOT_ARMED`. RC1 provenance does not
authorize new implementation, and RC2 is not yet executable law. Every unresolved conflict is
`SAFE_HOLD`; **do not start detector/M3/B01+ work before B00 is ratified**.

Authority order:

1. Operator's clean-room E02-only scope.
2. Independent safety and venue/account truth.
3. Signed activation/risk manifests for their exact external scope.
4. Resolved RC2 declarations and parameter registry.
5. Resolved RC2 formula and wiring registries.
6. Immutable versioned contracts and state machines.
7. `docs/plan/`.
8. Code, tests, historical RC1 docs, diagrams, examples, and comments.

Code never chooses between conflicting sources. A semantic change updates the authoritative
spec/control artifact in a prior PR.

## Repository ownership

- `CONSUME`: W02 canonical E01 state and an externally issued/validated lease.
- `OWN`: W03–W06 plus E02-specific W23–W25 facts.
- `REFERENCE_ONLY` or `OUT_OF_REPO`: W00–W01, W07–W21, E07 decision, E08 risk/sizing/authorization,
  E09 command/order/fill/protection, E10 outcome/learning, and venue/account truth.
- ORIGIN may verify a lease. It must not issue, activate, coordinate, or supersede one.

Never add a venue client, network control path, credential/private-key loader, order verb, risk or
quantity authorization, money publisher, runtime legacy bridge, authority router, fill parser, or
lease issuer. A healthy current build reaches only `READY_NO_AUTHORITY`.

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
```

Use one fresh branch and one PR per build milestone. Merge only after exact-head CI is green and all
actionable review threads are resolved. Then reproduce the checks from fresh merged `main` and seal
the milestone receipt before opening the next build branch. No self-reported test count, workbook
colour, force-push, or off-tree draft is acceptance evidence.
