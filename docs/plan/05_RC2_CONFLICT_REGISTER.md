# 05 · RC2 Conflict and Blocker Register

_B-series dispositions (2026-08-09): the rows below record closure state. A closed row names the
milestone whose merged PR carries the evidence; everything else remains open._

| Row | Disposition |
|---|---|
| BLK-RC2-015 | **CLOSED B00** — complete bundle vendored + hashed (`docs/control/`, `06_RC2_SOURCE_INVENTORY.md`) |
| BLK-RC2-016 / CTRL-B01-002 | **CLOSED B01** — `engine_attestation.v2` equality law + corrected goldens; v1 frozen |
| BLK-RC2-017 / CTRL-B01-003 | **CLOSED B01** — typed identity v2 (`origin.identity.v2`), v1 IDs byte-stable |
| CTRL-B01-001 | **CLOSED B01** — additive descriptor v2 with corrected media types; RC1/R00 descriptors byte-frozen |
| BLK-RC2-005/006 | **DISPOSITIONED B01** — UTC-µs law + int64-ticks-as-base10-string wire law (Q-E2/Q-E3) |
| BLK-RC2-010 | **DISPOSITIONED B00** — proposals carried as DARK data; fail-closed runtime (Q-D) |
| CTRL-B02-001 | **CLOSED B02** — external anchor journal (`anchor.py`) + tail-deletion/replacement falsification + cold/warm parity |
| CTRL-B02-002 | **CLOSED B02** — closed fence state sealed in checkpoint v3, restored before consumption, lower-token acceptance falsified across restart |
| BLK-RC2-007/008/009/011/012/013/014 | open — owned by B03–B05 with RC3 formula/vector law |
| CTRL-B08-001 | open — owned by B08; the read-only evidence PROJECTION is BUILT + falsified (six RC4 §L6 faces `read_faces/faces.py` + nine W25 views `read_faces/views.py`, incl. `get_readiness_view` carrying the four still-open evidence dimensions honest-null; `READY_NO_AUTHORITY` kept explicitly narrow — the faces ADD evidence, claim NO readiness); row stays open pending the on-box source-freshness/coverage/lease-validity/estate-activation evidence INPUTS those dimensions surface |
| CTRL-R00-001 | open — operator ruleset act (Q-A4) |

All `BLK-RC2-*` rows block the B00 authority freeze until a named authority ratifies the semantic
decision, version/migration disposition, owner/reviewer, and evidence obligation. That decision does
not mark downstream implementation complete: corresponding `CTRL-B01+` rows remain blocking at the
assigned build milestone. Implementation never picks a side.

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
| BLK-RC2-016 | RC1 `engine_attestation.v1` duplicates build/config/contract/artifact/epoch identities in envelope and payload without equality constraints; its valid golden contradicts itself | B00 ratifies canonical cross-field equality and migration/version law; CTRL-B01-002 implements additive contracts/vectors; R00 payload builder remains non-authoritative |
| BLK-RC2-017 | RC1 generic length-framed digest encoding has no field type tags, so selected values of different runtime types can encode identically | B00 ratifies typed identity and compatibility law while preserving valid RC1 IDs; CTRL-B01-003 implements the additive identity version/vectors |

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
| CTRL-B01-001 | RC1 manifest labels every JSON artifact as `application/schema+json`, including goldens and registry | Preserve immutable RC1 bundle bytes/hash in R00; correct only through an additive B01 descriptor/bundle version plus compatibility evidence |
| CTRL-B01-002 | RC1 engine-attestation envelope/payload identity equality is unenforced and its valid golden contradicts itself | After B00 decides the law, add a distinct compatible contract/version, corrected vectors, and equality validation in B01 |
| CTRL-B01-003 | Generic RC1 digest framing lacks field type tags even though R00 public identity constructors now enforce declared string types | After B00 decides the law, add typed identity-domain/version vectors and migration evidence in B01 without rewriting valid RC1 IDs |
| CTRL-B02-001 | A self-contained hash-chained ledger detects torn/interior corruption but cannot detect deletion or replacement of a complete tail; checkpoint output segment/offset has no independently durable expected-head binding | Bind output segment, offset, chain head, file identity, and recovery receipt to an external durable anchor; falsify tail deletion/replacement and cold/warm exactly-once parity before B02 acceptance |
| CTRL-B02-002 | R00 consumer fencing and ingress epoch high-water marks are process-local; checkpoint/restart does not yet restore the complete per-scope accepted-token state | Define the closed per-scope fence state, authenticate it in checkpoint/recovery evidence, restore it before consumption, and falsify lower-token acceptance across restart in B02 |
| CTRL-B08-001 | R00 bootstrap readiness has no source freshness, coverage, lease-validity, or estate-activation evidence inputs | Keep `READY_NO_AUTHORITY` explicitly narrow; add and falsify the complete read-only evidence projection in B08 before operational readiness is claimed. **B08 (built):** the projection exists — `get_readiness_view` (`read_faces/views.py`) surfaces the four evidence dimensions as honest-null-by-default facets (`source_freshness` bound-checked; `coverage` an exact integer pair; `lease_validity` echoed verify-only + `producer_attestation=NOT_OWNED_HERE`; `estate_activation` UNAVAILABLE by default — ORIGIN holds no estate/venue truth) while the narrowness invariant holds even with all four supplied positively (`authority="NONE"`, `ceiling="READY_NO_AUTHORITY"`, no AUTHORIZED/ARMED/OPERATIONAL/ACTIVATED token; falsified by `tests/read_faces/test_views.py` + `tools/e2e_audit.py::read_faces_walk`). The row stays open pending the on-box evidence INPUTS themselves (a read face adds evidence, never authority). |
