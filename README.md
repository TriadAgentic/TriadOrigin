# TRIAD ORIGIN V7 — Deterministic Causal Edge Core

**Repository:** `TriadAgentic/TriadOrigin` · **Service:** `triad-origin-e02` · **Node:** `E02-V7`  
**Namespace:** `triad.origin.v7` · **Posture:** `DARK / SAFE_HOLD`

TRIAD ORIGIN is the clean-room deterministic **E02-only** service in the TRIAD estate. It consumes
canonical E01 state and, after the governing specification is ratified, may produce deterministic
feature, structure, reaction, hypothesis, candidate, quarantine, replay, and evidence facts.
It is not an E00–E10 monolith.

> **No live activation or profitability claim.** This repository has no venue credential, order,
> E07 policy, E08 risk/size/authorization, E09 execution, E10 accounting, lease-issuance, or money
> publication capability. A healthy current process can reach only `READY_NO_AUTHORITY`.

## Governing status

- The merged foundation originated against `1.0.0-RC1` and failed the later repository audit.
- The supplied `1.0.0-RC2` package is a `RATIFICATION_CANDIDATE_NOT_ARMED`; it is incomplete and
  internally contradictory.
- Vendored [`docs/spec/`](docs/spec/) is therefore **historical RC1 provenance**, not sufficient
  authority for new detector work.
- RC2 conflicts enter `SAFE_HOLD`. M3 and every detector milestone remain blocked until B00 closes
  the package, compatibility, ownership, formula, parameter, and lifecycle decisions.

The controlled execution law is [`docs/plan/README.md`](docs/plan/README.md). Audited status is in
[`docs/plan/04_STATUS.md`](docs/plan/04_STATUS.md), and release blockers are in
[`docs/plan/05_RC2_CONFLICT_REGISTER.md`](docs/plan/05_RC2_CONFLICT_REGISTER.md).

## E02 boundary

ORIGIN consumes W02, owns W03–W06 and its E02-specific W23–W25 facts, and treats downstream
decision/risk/execution/outcome contracts as conformance references only. It may verify an externally
issued lease; it never issues, activates, coordinates, or supersedes one. Runtime legacy bridges,
authority routers, risk/exit policy ownership, venue adapters, order compilers, and fill parsers are
out of repository.

## Repository layout

```text
contracts/         RC1 byte-pinned contracts and conformance vectors pending B01 refreeze
src/triad_origin/  DARK deterministic foundation and read-only/verify-only faces
docs/spec/         Historical vendored RC1 source set
docs/plan/         Audited R00/B00–B09 execution plan and blocker registers
tools/             Verification, packaging, and negative-capability gates
tests/             Falsification and regression suites
```

## Required local gate

```bash
PIP_CONSTRAINT=constraints/ci.txt python -m pip install -e '.[test]'
PYTHONHASHSEED=0 python -m pytest
PYTHONHASHSEED=1 python -m pytest
python tools/collect_test_ids.py
python tools/verify_manifest.py
python tools/validate_contract_manifest.py
python tools/verify_reproducible_build.py
python tools/test_wheel_install.py
python tools/verify_no_forbidden_capabilities.py
```

Test count is descriptive, not acceptance evidence. A milestone also requires exact-head CI,
resolved actionable findings, authenticated clean acceptance for that same immutable head, guarded
squash merge, fresh-main reproduction, and an immutable receipt. For corrective R00, a persistent
connector PR-root `+1` is corroboration only; final-head acceptance requires its own fresh clean
Codex artifact, an exact reviewed historical review/comment baseline, unedited top-level comments,
and a complete timeline proving no later head/base mutation or review dismissal. Both acceptance
routes also reject thread activity at or after acceptance except the one canonical unedited
post-merge closure reply.

R00 final-receipt authority is assigned to PR #8. Merged PR #7 is retained and live-authenticated
as a rejected predecessor (squash `0012e89214c7e0321592684b3b866323f891ace9`), including its exact
lineage, ten reviews, three post-merge closure carriers, and GraphQL thread state. Additive v4 review
evidence uses GraphQL `editor`/`lastEditedAt` as edit witnesses, preserves PR #1–#4 historical
closure prose by exact reply ID/body hash, and binds PR #7 V1 closures to `PRRT_…` thread IDs.
Same-repository PR #8 CI double-fetches this raw GraphQL history before merge.

R00 source artifacts use package version `7.0.0rc1.post1`; this distinguishes the repaired RC1
foundation from pre-R00 `7.0.0rc1` bytes and does not claim RC2 specification acceptance. The R00
ledger implementation is Linux/POSIX-only (`fcntl` inode locking); cross-platform transport is not
claimed.
