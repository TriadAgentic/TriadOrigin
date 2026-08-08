# TRIAD ORIGIN V7 — Authority and Coverage Index

## Source status

| Source | Repository role | Current authority |
|---|---|---|
| `docs/spec/` documents 00–10 | Vendored RC1 provenance used by the original M1/M2 build | Historical; not authority for new work |
| RC1 contracts and golden vectors under `contracts/` | Immutable compatibility baseline | Re-audit in B01; never rewrite bytes in place |
| Supplied RC2 declarations, wiring, workbook, and package index | Candidate control package | Incomplete/conflicting; `SAFE_HOLD` |
| `docs/plan/` | Audited execution and ownership law | Controls work ordering; cannot override unresolved RC2 semantics |

The exact supplied RC2 hashes and missing package members are recorded in
[`plan/06_RC2_SOURCE_INVENTORY.md`](plan/06_RC2_SOURCE_INVENTORY.md). Conflicts are tracked in
[`plan/05_RC2_CONFLICT_REGISTER.md`](plan/05_RC2_CONFLICT_REGISTER.md).

## Audited implementation state

| Build | Scope | State |
|---|---|---|
| RC1 M1 | Contract/identity foundation | `MERGED_IMPLEMENTATION / FAILED_AUDIT`; repair in R00, re-audit in B01 |
| RC1 M2 | Kernel/transport foundation | `MERGED_IMPLEMENTATION / FAILED_AUDIT`; repair in R00, re-audit in B02 |
| R00 | Review, correctness, CI, packaging, DARK boundary, and plan truth | PR #4 bootstrap; merge receipt determines verification |
| B00 | Complete/resolve RC2 package, compatibility, E02 ownership, and consequential variables | `BLOCKED / SAFE_HOLD` |
| B01–B09 | Contract refreeze through offline verification/operator artifacts | Blocked by predecessor |

The obsolete M3–M6 route is superseded. Do not implement its detector list, runtime legacy bridge,
authority router, risk/exit policies, fill-driven withdrawal, or lease coordinator.

## E02 ownership map

| Family | Classification |
|---|---|
| W02 | `CONSUME` |
| W03–W06 | `OWN` |
| W22 | `CONSUME / VERIFY_ONLY` |
| E02-specific W23–W25 | `OWN` |
| W00–W01, W07–W21 | `REFERENCE_ONLY` or `OUT_OF_REPO` |
| F00 boundary, F02–F19 | E02 scope after B00 resolution |
| F01 | Upstream E01 conformance boundary |
| F20–F23 | Downstream reference only |

Row-level milestone ownership and OPS allocation are in
[`plan/02_TRACEABILITY.md`](plan/02_TRACEABILITY.md). No file, test, or contract presence alone marks a
requirement passed; future status is derived from exact-head CI, review, merge, post-merge
reproduction, and an immutable receipt.
