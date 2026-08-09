# 09 · Decision Disposition Register

_Reconciled at B00C (2026-08-09). This is a **disposition register**, not a questionnaire
deferred to B10: every row names the milestone/gate it must close before, its decision owner,
its current status, its evidence, and its failure behavior while open. Per the operator's
standing directive, rows are **not** asked in chat; they are batched here for the operator. An
explicit decision to keep a value `NOT_RATIFIED` is a closed planning answer and an open
activation blocker — it never authorizes a substitute._

Legend — **Status:** `OPEN` (undecided), `DEFAULT_IN_FORCE` (build proceeds on the recorded
default; operator may veto), `CLOSED` (operator decided / evidence sealed), `BLOCKED_EXTERNAL`
(needs an act outside this session). **Failure behavior** = what the build/runtime does while
the row is open (always fail-closed, never a silent substitute).

## A · Governance & repository

| Row | Question / decision | Required before | Owner | Status | Disposition & evidence | Failure behavior while open |
|---|---|---|---|---|---|---|
| A1 | Repository home ("triad agent" spoken vs `TriadAgentic/TriadOrigin` written) | B00C receipt | Operator | DEFAULT_IN_FORCE | Build proceeds in `TriadAgentic/TriadOrigin` (org read as "TriadAgentic"); all merged work lives there | Relocation would be a fresh operator directive + migration plan |
| A2 | ADR-005 supersession signature (RC4 lever law ratification) | B05 four-plane merge (artifact); any non-OFF activation (signature) | Operator | DEFAULT_IN_FORCE | RC4 + the 2026-08-09 build directive treated as ratification **for DARK implementation only**; B05 prepares the ADR supersession artifact for signature | No non-OFF activation is representable; baseline stays `OFF/OFF/OFF/LIVE` |
| A3 | R00 receipt + B-series receipt law | B00C receipt | Operator countersign; build session seals | DEFAULT_IN_FORCE | `docs/governance/R00_SUPERSESSION.md` maps every R00 field/invariant into `evidence_receipt.v2`; `evidence/receipts/R00.json` seals the disposition; B00/B01 receipts retained (content valid, one-behind cadence superseded); from B00C forward: one source PR + one post-merge evidence-only receipt PR per milestone | Receipts remain self-integrity-sealed, uncountersigned; no gate receipt is claimed |
| A4 | Branch ruleset (issue #5) or signed time-bounded waiver | Was due before B01 (breached historically — recorded); due before next merge wave | Operator (repo admin) | BLOCKED_EXTERNAL | This session has no repository-settings surface. Guarded-merge evidence recorded: every `main` merge via PR on green exact-head CI (runs `31293420164`, `31294503427`, `31295070373`, …). Required ruleset: exact-head CI + review + resolved conversations + no force/direct push + no admin bypass | Marathon continues under the operator's rank-1 directive with this blocker flagged in every status face; never reported as configured |
| A5 | Checkpoint ceremony scope | B10 | Operator | DEFAULT_IN_FORCE | TriadOrigin-local checkpoint only (`checkpoint/<date>-origin-v7-build` + `CHECKPOINTS.md` here); estate-wide checkpoint is G9's | No sibling-repo checkpoint branches are created |
| A6 | Estate/operator lanes (361 ESTATE + 57 OPERATOR ledger rows built elsewhere) | G-1 onward (Track B) | Operator | DEFAULT_IN_FORCE | Partition matches "wire with the other surfaces later"; this repo carries contract shapes + ingress expectations only | Track B gates stay `NOT_PASSED`; completion claims stay repository-scoped |
| A7 | Control-plane homing (comparator / authority-fact verifier / legacy bridge / replay runner) | B01 merge (was); disposition re-affirmed for B07 | Operator | DEFAULT_IN_FORCE | Built here as pure, dark, import-isolated libraries. Per the alignment audit: **no admission/arbitration** — `authority_fact_verifier` verifies externally issued `candidate_authority.v1` + technical-writer lease only; never admits candidates, issues leases, or selects money authority | Any admission-shaped API is a build defect; process deployment stays an estate decision |

## B · Activation values (BLOCKING_OWNER_DECISION — stay `NOT_RATIFIED`, fail closed)

All eight ship as `NOT_RATIFIED` registry rows; `require()` refuses them; runtime fails closed.

| Row | Parameter | Required before | Owner | Status | Failure behavior while open |
|---|---|---|---|---|---|
| B1 | PAR-070 `PRODUCTION_RISK_BUDGET` (bps-of-NAV **and** absolute quote cap) | G9 | Operator | OPEN | No production sizing representable; F20 catalog `DENY` |
| B2 | PAR-072 `PRODUCTION_GROSS_EXPOSURE_CAP` | G9 | Operator | OPEN | Same |
| B3 | PAR-076 `MAX_DAILY_NET_LOSS` (stop, UTC reset, realized/unrealized, rel+abs caps) | G7 | Operator | OPEN | No canary window may open |
| B4 | PAR-077 `MAX_PEAK_TO_TROUGH_DRAWDOWN` (+ HWM reset governance) | G7 | Operator | OPEN | Same |
| B5 | PAR-118 `CANARY_CAPSULE` (exactly one semantic version + parameter digest) | G7 | Operator | OPEN | Same |
| B6 | PAR-119 `CANARY_INSTRUMENT` (one venue-qualified instrument) | G7 | Operator | OPEN | Same |
| B7 | PAR-120 `CANARY_SIDE` (one side enum) | G7 | Operator | OPEN | Same |
| B8 | PAR-121 `CANARY_ACCOUNT` (isolated account/risk cell + position mode + permissions) | G7 | Operator | OPEN | Same |

## C · Research decisions (BLOCKING_RESEARCH_DECISION — interfaces + named abstention only)

| Row | Parameter | Required before | Owner | Status | Failure behavior while open |
|---|---|---|---|---|---|
| C1 | RC3-PAR-STRUCT-001 `EQUAL_LEVEL_MAX_SPAN` | B03 **result emission** (interface/refusal may land) | Research + Operator ratify | OPEN | F06 emits the named abstention `F06_UNAVAILABLE_MAX_SPAN_NOT_RATIFIED`; equal-level structures and dependent capsules `SAFE_HOLD` |
| C2 | RC3-PAR-STRUCT-002 `BOOK_TILT_MIN_QUOTE_DEPTH` | B04 result emission | Research + Operator | OPEN | F17 tilt emits its named abstention; dependent capsules `SAFE_HOLD` |
| C3 | RC3-PAR-STRUCT-003 `PROTECTED_SWING_REDUCER_VERSION` | B03 result emission (F08); B06 CHOCH-capsule availability | Research + Operator | OPEN | F08 has **no semantic implementation** (RC3: none authorized); state stays `UNINITIALIZED`; F09 emits accepted breaks with BOS/CHOCH labels withheld (`UNCLASSIFIED_STRUCTURE_STATE_UNAVAILABLE`) |

## D · Proposed parameter bundle (123 × `PROPOSED_RC2_MUST_RATIFY`)

| Row | Decision | Required before | Owner | Status | Disposition | Failure behavior while open |
|---|---|---|---|---|---|---|
| D | Ratify the RC2 proposal bundle wholesale for SHADOW operation, selectively, or keep symbolic until trial registration | B06 candidate emission (consumed subset); G2 (full) | Operator | OPEN — DEFAULT_IN_FORCE for build | Carried verbatim as a status-labelled, digest-pinned **proposal bundle**; tests exercise formulas with explicitly-labelled test vectors; `require()` refuses `PROPOSED_*` in any non-test context | No semantic result emission on a proposed value; machines fail closed or emit named abstention |

## E · Specification conflicts (dispositioned per RC3/RC4 precedence — confirm or veto)

| Row | Conflict | Required before | Status | Disposition |
|---|---|---|---|---|
| E1 | ADR-005 "no testnet ever" vs RC4 four-plane law | B05 | DEFAULT_IN_FORCE | RC4 wins (later owner directive): TESTNET is a canonical isolated venue environment; sibling-repo estate rules untouched |
| E2 | RC1 `*_ns` fields vs UTC-microsecond law | B01 (closed in code) | DEFAULT_IN_FORCE | UTC Unix **microseconds**; ns remainder carried separately |
| E3 | int64 ticks vs base-10 string wire encoding | B01 (closed in code) | DEFAULT_IN_FORCE | Semantic int64 ticks; JSON wire base-10 string |
| E4 | F02 ATR window inclusion (BLK-RC2-007) | B03 semantic merge | DEFAULT_IN_FORCE | RC3 formula text + GV-004 pin the window: the 14 TRs strictly before the evaluation origin (the most recent finalized bar is TR_{x−1}) |
| E5 | F04 fractal tie-break (BLK-RC2-009) | B03 semantic merge | DEFAULT_IN_FORCE | Strict extreme; ties reject (GV-006) |
| E6 | Capsule family naming (BLK-RC2-011) | B06 candidate emission | OPEN — corrected | **No guessed ordinal↔semantic map** (audit P0): B06 builds the explicit semantic-ID registry (`dc_swing_bos_first_retest.v1`, …); RC2 `CAP01…CAP05` ordinal parameters are non-executable until explicitly remapped by decision |
| E7 | Candidate lifecycle abstention/withdrawal (BLK-RC2-013) | B06 | DEFAULT_IN_FORCE | RC3 lifecycle graph; withdrawal is a first-class transition |
| E8 | F18 stop-side `abs()` defect (BLK-RC2-014) | B06 | DEFAULT_IN_FORCE | Directional stop-side invariant; one-tick vectors |
| E9 | W06 cluster-ID circularity (BLK-RC2-012) | B06 | DEFAULT_IN_FORCE | Frozen earliest prospective root ordered by `(availability, candidate_id)`; never re-root |

| E10 | F09 break-predicate scope: the implementation evaluates BOTH directional predicates against every confirmed frozen level (up_break iff C≥L+b, down_break iff C≤L−b — the literal formula text; first-breach dedup by `(level_id, direction)`), not a kind-scoped single predicate. Both readings satisfy GV-008 and the mirror vectors | B03 semantic merge (implemented; confirm or veto) | Operator/Research | DEFAULT_IN_FORCE | Documented in `structures/structure_state.py`; a kind-scoped veto is a one-line predicate change + re-vector |
| E11 | F05 rolling extreme has NO linked RC3 golden vector (`BLOCKED_MISSING_LINKED_GOLDEN_VECTOR`); its exact values are pinned by repository tests only | G2 | Research + Operator | OPEN | Repo tests pin warm-up boundary + current-bar exclusion; the linked RC3 vector remains owed |
| E12 | F06 span-law boundary is INCLUSIVE (span ≤ max_span joins, per PAR-009); an intended strict bound would be a formula-row spec change | B03 (implemented per PAR-009) | Operator | DEFAULT_IN_FORCE | `typed_level_registry.py` + boundary tests |

| E13 | F16 OFI has no linked RC3 golden vector and no timestamp field on the declared book-update input, so PAR-057's max-age window cannot be applied structurally; the parameter is fetched/validated fail-closed but age-filtering is deferred to a future producer-side envelope revision | G2 | Research + Operator | OPEN | `flow_atoms.py` pins its own hand-worked vector; the sequence/watermark/min-updates laws are enforced now |
| E14 | F12 causal order block: RC3's PAR-047/PAR-161 boundary-rule texts state slightly different tie-break wording (latest-event-then-source-id vs latest-qualifier-then-notional-then-source-id); implemented the fuller PAR-161 rule (notional, then source_id) per this build's task law | B04 (implemented; confirm or veto) | Operator/Research | DEFAULT_IN_FORCE | `order_block_registry.py`; a veto is a tie-break re-derivation, not a new module |
| E15 | F12 has no TTL: RC3's formula row names a generic "TTL" input but no specific PAR governs it (unlike F10's PAR-051); implemented with none (only PENDING→EXPIRED-by-horizon and CONFIRMED→BROKEN are terminal paths) | B04 (implemented; confirm or veto) | Operator/Research | DEFAULT_IN_FORCE | A ratified F12-specific TTL parameter would be a follow-up binding + code change |

## F · Estate wiring handoffs (Track B)

| Row | Question | Required before | Owner | Status |
|---|---|---|---|---|
| F1 | Host repo/process for the E01 `market_state.v2` bridge (W01/W02) | G5 estate homing | Operator | OPEN |
| F2 | Legacy `candidate.v1` source topic/ledger path to freeze for the control arm | G4 | Operator | OPEN |
| F3 | Divergence/authority topic file-ledger paths for `transport_bindings.v1` | G4 | Operator | OPEN |
| F4 | SHADOW disposition consumer: estate shadow bank vs local durable ledger | G5 | Operator | OPEN — default: local durable ledger, contract-shaped rows |
| F5 | RC4 L1 as-built census of the seven external engines | G5 | Operator | OPEN — confirmed a separate program by default |

## G · Session-scope confirmations

| Row | Question | Required before | Status | Disposition |
|---|---|---|---|---|
| G1 | RC1-complete-edition HTML hash-registered, not vendored | B01 (was) | DEFAULT_IN_FORCE | Hash registration suffices; RC3 embeds RC1 |
| G2 | Receipt cadence | B00C receipt | CLOSED (audit) | The one-behind scheme is **rejected**. One source PR + one post-merge evidence-only receipt PR per milestone; next branch only after the receipt merges and validates. Historical B00/B01 receipts: content retained, cadence disposition recorded (A3) |
