# 04 · Status

_Updated: 2026-08-09 (B00). Status is evidence-based and DARK._

## Authority state

| Item | State |
|---|---|
| Controlling package | RC3 effective control bundle (PASS_COMPOSITION_SAFE_HOLD) + RC4 addendum, vendored under `docs/control/` |
| Build authorization | Operator directive 2026-08-09 (see `00_MASTER_PLAN.md` §1) — DARK implementation only |
| Activation | `RATIFICATION_CANDIDATE_NOT_ARMED`; every lever OFF; `READY_NO_AUTHORITY` |
| RC2 source inventory | **COMPLETE** — previously-missing members supplied + hashed (`06_RC2_SOURCE_INVENTORY.md`) |
| Open questions | `09_OPEN_QUESTIONS.md` — answered by the operator at end of build |

## Milestones

| Milestone | Status | PR | Evidence |
|---|---|---|---|
| RC1 M1 (contracts) | merged + R00-remediated | #1, #4, #7 | substrate for B-series |
| RC1 M2 (kernel) | merged + R00-remediated | #2, #4, #7 | substrate for B-series |
| R00 refreeze | merged | #4, #7 | receipt seal tracked in Q-A3 |
| **B00** authority & control baseline | **in flight** | this PR | e2e 9/9 · ledger 1,250 rows · gate green |
| B01–B10 | planned | — | see `01_MILESTONE_BREAKDOWN.md` |

## Gate state (local reproduction, pre-B00-merge)

- `python -m pytest` → **206 passed** (seeds 0 and 1)
- `tools/verify_manifest.py` → OK (91 artifacts)
- `tools/validate_contract_manifest.py` → OK
- `tools/verify_no_forbidden_capabilities.py` → OK
- `tools/e2e_audit.py` → 9/9 stages PASS
- `tools/build_ledger.py --verify` → OK (1,250 tasks)

## Non-repo lanes (named, not built here)

ESTATE 361 rows · OPERATOR 57 rows · RESEARCH 4 rows (fail-closed symbolic) — see the ledger and
`09_OPEN_QUESTIONS.md` §B/§C/§F.
