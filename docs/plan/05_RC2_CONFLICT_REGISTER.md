# 05 · RC2 Conflict and Blocker Register

All rows are release-blocking. Resolution requires a changed authoritative artifact, compatibility
evidence, named owner/reviewer, and a receipt. Implementation does not pick a side.

| ID | Conflict / missing decision | Required closure |
|---|---|---|
| BLK-RC2-001 | Repository/code/plan target RC1; supplied controls target RC2 | Complete bundle + compatibility/migration manifest |
| BLK-RC2-002 | RC2 says no task/gate passed; old status marks M1/M2 complete | Evidence-derived status; merged implementation separated from gate acceptance |
| BLK-RC2-003 | `structure_atom` and `edge_candidate` v1 vs v2 | Canonical version map; additive schema/migration vectors |
| BLK-RC2-004 | Decision/execution/order/position/protection/outcome contract names/versions conflict | Estate-wide canonical version and compatibility map |
| BLK-RC2-005 | Envelope `*_ns` names conflict with UTC Unix microsecond declaration | Exact field/type/unit and migration decision |
| BLK-RC2-006 | Base-10 string encoding conflicts with signed-int64 declaration | Separate semantic type from JSON/wire encoding; compatibility tests |
| BLK-RC2-007 | F02 excludes evaluation bar; PAR-035 wording includes current finalized bar | Exact indexed ATR window and distinguishing golden vector |
| BLK-RC2-008 | F03 composite reversal formula conflicts with PAR-036 ATR-only expression | One exact formula and complete parameter IDs |
| BLK-RC2-009 | F04 permits tie-break; PAR/GV reject ties | One exact tie rule and vectors |
| BLK-RC2-010 | RC1 says numeric thresholds symbolic/TBD; RC2 says no runtime TBD and proposes values | Explicit DARK proposal bundle vs ratified activation bundle semantics |
| BLK-RC2-011 | RC1 plan capsule family differs from RC2 CAP-01…05 family | One semantic-versioned capsule registry and ordinal mapping |
| BLK-RC2-012 | W06 partitions by cluster ID before F19 can derive it; member growth destabilizes identity | Non-circular prospective cluster-root design |
| BLK-RC2-013 | Candidate lifecycle permits post-publication abstention and omits withdrawal | Exact lifecycle graph; abstention sibling and withdrawal rules |
| BLK-RC2-014 | F18 uses `abs(E-S)` and can accept a stop on the wrong side | Directional stop-side invariant and one-tick vectors |
| BLK-RC2-015 | Linked complete checklist and `canonical/` bundle are absent | Supply and hash every package member; fail closed on missing link |

## Additional consequential variables

The following require exact declarations or `NOT_RATIFIED`:

- equal-level maximum span;
- F08 swing-pair construction and protected-swing promotion;
- F09 simultaneous continuation/protected-level break precedence;
- F10 contact price and exact bearish penetration;
- F13 reclaim/hold/invalidation/expiry precedence;
- candidate versus zone TTL and E02-owned withdrawal triggers;
- F19 parenthesization, time basis, and stable cluster-root identity;
- signature/trust-root/revocation/canonical-signed-byte law;
- immutable evidence receipt and stale/supersession law;
- exact capsule flow/session/regime thresholds and entry inconsistencies;
- liquidation/exhaustion formulas if they remain in scope.

## Workbook/control defects

| ID | Defect |
|---|---|
| WB-RC2-001 | `Dashboard!F5` is a static false `PASS` |
| WB-RC2-002 | 17 verification rows reference nonexistent `CTL-G2/G3-03` |
| WB-RC2-003 | Eight P3 tasks violate P0/P1/P2 validation |
| WB-RC2-004 | `W00-W25` is unresolved shorthand |
| WB-RC2-005 | Formula free-text parameters do not machine-join 24/24 formulas |
| WB-RC2-006 | PAR-004 says RATIFIED_RC1 but cites RC2 declaration |
| WB-RC2-007 | Capsule ordinal-to-semantic-version map is missing |
| WB-RC2-008 | No PR/commit/CI/receipt baseline; status/evidence cells are blank |
| WB-RC2-009 | Fixed-range dashboard formulas can omit appended task rows |
| WB-RC2-010 | Editable/immutable cells are not protected or adequately validated |

## Repository-control blocker

| ID | Defect | Required closure |
|---|---|---|
| CTRL-R00-001 | Available evidence does not prove a main-branch ruleset requiring exact-head CI and review | Close GitHub issue #5 with repository-setting evidence in B00; until then only the R00 expected-head bootstrap merge is permitted |
