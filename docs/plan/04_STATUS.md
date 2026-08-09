# 04 · Audited Status

_Audited: 2026-08-09. Status is evidence-based and DARK._

## Pre-R00 repository snapshot

| Item | State |
|---|---|
| Repository | `TriadAgentic/TriadOrigin` |
| Default branch | `main` |
| Audited main | `69dfd7245fb462992f17e4af06e6746ac2f9d2f0` |
| Open PRs at audit | 0 |
| Merged PRs | #1, #2, #3 |
| GitHub workflow/status evidence | None |
| Unresolved review threads | 14: 9 P1, 5 P2 |
| Old feature branch | Diverged; not an acceptable next-milestone base |

## Reproduced baseline

An authenticated file reconstruction of audited `main` reproduced:

- `165 passed` locally;
- `tools/verify_manifest.py`: 91 artifacts match
  `5189c78ae315850d…`.

This proves reproducibility of the current tests/bytes, not correctness: two tests explicitly encoded
the rejected same-epoch behavior, and the manifest verifier did not validate the manifest artifact
against its declared schema.

## Milestones

| Milestone | Status | Evidence / reason |
|---|---|---|
| RC1 M1 | `MERGED_IMPLEMENTATION / FAILED_AUDIT` | PR #1; 5 unresolved findings; no CI |
| RC1 M2 | `MERGED_IMPLEMENTATION / FAILED_AUDIT` | PR #2; 6 unresolved findings; no CI |
| Prior plan | `SUPERSEDED` | PR #3; 3 unresolved findings; incompatible with RC2 |
| R00 | `PR #4 + PR #7 MERGED_UNVERIFIED / PR #8 CORRECTION` | PR #4 failed on its sdist snapshot; PR #7 failed on edit-witness, retroactive closure-body, and thread-ID semantics; PR #8 owns final receipt closure |
| B00 | `BLOCKED` | Incomplete/conflicting RC2 package and missing authority decisions |
| B01–B09 | `BLOCKED_BY_PREDECESSOR` | No implementation starts early |

## Repository control gap

| Control | State | Compensating control / closure |
|---|---|---|
| Required main CI + review ruleset | `UNVERIFIED` | R00 exact-head guarded merge only; issue [#5](https://github.com/TriadAgentic/TriadOrigin/issues/5) must close in B00 |
| CI action identity | `PINNED` | Immutable action SHAs in `.github/workflows/ci.yml` |
| CI dependency identity | `PINNED_R00_SNAPSHOT` | `constraints/ci.txt`; receipt records the resolved environment |
| Post-merge receipt storage | `FAILED_CLOSED / PR8_CORRECTION_PENDING` | No receipt was published; PR #7 is authenticated rejected history and PR #8 must merge/reproduce before `evidence/receipts/R00.json` can be sealed |

## RC2 control catalogue

- 1,088 tasks are `NOT_STARTED`.
- 1,496 verification rows are `NOT_RUN`.
- All G-1…G9 gates are open.
- The workbook is a catalogue/operator view, not an authoritative evidence engine.
- Its static control `PASS` is invalid; broken references and vocabulary defects are recorded in
  the conflict register.

## Next permissible action

Complete final-receipt PR #8 on exact-head green CI, the raw-GraphQL history preflight, and
independent review; merge it only with the expected-head guard, reproduce fresh corrected `main`,
and seal the R00 receipt against that squash. PR #4's squash
`241b301d1144e3e2a0a15f4bfe9ffef5b51068ed` and PR #7's squash
`0012e89214c7e0321592684b3b866323f891ace9` remain explicit failed-closed predecessors in the
evidence chain; neither is relabelled verified. After closure, B00
still remains in `SAFE_HOLD` until the complete RC2 source bundle and named decisions exist. Do not
resume detector fan-out.
