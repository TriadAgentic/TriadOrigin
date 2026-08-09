# 00 · TRIAD ORIGIN V7 Master Plan — Reconciled RC3 + RC4 Baseline

_Revision: 2026-08-09 · This document supersedes the uploaded B-series plan. It corrects the
formula registry, authority boundaries, four-plane controls, receipt law, and decision timing._

## 1 · Controlling state

The control package is composition-complete, but the system is not activation-ready. These are
different claims and must stay separate:

| Dimension | Controlling state | Meaning |
|---|---|---|
| Document composition | `PASS_COMPOSITION_SAFE_HOLD` | RC3's effective bundle composes; this is not a runtime or gate pass. |
| Offline implementation authority | `AUTHORIZED_OFFLINE_IMPLEMENTATION_ONLY` | Repository code, schemas, fixtures, replay, and zero-venue-capability services may be built. |
| Service readiness | `NOT_ATTESTED` | Current runtime state is unknown until a fresh, scoped attestation exists. |
| Activation result | `DENIED_SAFE_HOLD` | No venue, PAPER, TESTNET, canary, or production gate is authorized by this plan. |

The required non-authoritative baseline manifest is exactly:

```yaml
venue_environment: OFF
venue_activation: OFF
paper_activation: OFF
shadow_activation: LIVE
```

`shadow_activation` is fixed `LIVE`, not switchable. `DARK` and every other RC4-invalid alias are
refusals, not synonyms. The tuple above is a required configuration target; it is not a claim that
an as-built runtime currently enforces it.

## 2 · Objective and completion claim

Build the complete ORIGIN repository implementation and its estate interface contracts for the
deterministic causal path:

`market_state.v2 → features → structures → reactions → isolated capsules → edge_candidate.v2`

The repository outcome includes deterministic state machines, immutable contracts, bindings,
replay/checkpoint logic, four-plane control and evidence components, signed configuration
artifacts, read-only evidence projections, and falsification-first tests.

Repository completion does **not** mean the TRIAD estate is certified. E00/E01 ingress, E07
admission, E08 sizing/risk, E09 execution/money facts, E10 outcomes, credentials, live process
census, TESTNET proof, canary, economic proof, and cutover remain estate-owned and require their
own gate receipts.

Repository home: `TriadAgentic/TriadOrigin`.

## 3 · Binding authority and precedence

1. Authenticated owner decisions and signed supersessions.
2. RC4 for four-plane controls and the selected-policy form of F20.
3. RC3 effective overlay and effective machine bundle.
4. RC2 canonical registries where RC3/RC4 do not override them.
5. RC1 inherited requirements where not superseded.
6. This plan as scheduling metadata only.
7. The topology image as `ILLUSTRATIVE_TARGET_SUPERSEDED` orientation only.

No plan row may change a source task's authority owner, hard dependency, gate, contract, formula,
or refusal behavior. Scheduling metadata may add a repository milestone but cannot legalize a
blocked source row.

## 4 · System laws

1. E02/ORIGIN produces causal features, structures, reactions, and complete trade hypotheses; it
   never admits trades, sizes risk, routes orders, or originates money facts.
2. E07 alone admits/arbitrates candidates. ORIGIN may verify an externally issued authority fact
   and technical-writer lease; it may not own or issue a money-selection lease.
3. E08 alone performs final sizing and risk authorization. F20 consumes one already-selected,
   signed risk-budget policy reference and digest. Environment or rollout metadata may not enter
   the sizing formula. Missing, stale, or invalid policy means `DENY`.
4. E09 alone compiles venue commands and owns order/fill/position facts. Normal execution is
   maker-first/post-only; governed emergency IOC is reduction-only.
5. E10 derives outcomes from strict money lineage; it never fabricates missing P&L.
6. Published schema bytes are immutable. Breaking changes create a new major version.
7. Deterministic transitions receive time/age as inputs; no wall clock, randomness, network, or
   process identity enters semantic output.
8. Missing or unratified safety-relevant data produces named abstention, rejection, quarantine, or
   `SAFE_HOLD`; never a code default.
9. PAPER, SHADOW, TESTNET, and LIVE populations remain physically and analytically separate.
10. SHADOW capture and its health law exist before the first deployable candidate route.
11. Deployment is not authority. A valid contract without a current lease/manifest is unusable.
12. Evidence is append-only, digest-bound, current for scope, independently reviewed where
    required, and never represented as fresher or more complete than it is.

## 5 · Canonical formula registry

This table replaces every shifted F-number in the uploaded plan. There is no F24.

| ID | Formula | Authoritative owner | Repository treatment |
|---|---|---|---|
| F00 | Exact tick/step conversion | Contract/kernel | Implement in ORIGIN shared kernel. |
| F01 | Finalized time-bar aggregation | E01 | Consume and validate only; estate implementation. |
| F02 | True range / trailing ATR | ORIGIN | Implement. |
| F03 | Directional-change swing | ORIGIN | Implement only after required bindings/parameters are ratified. |
| F04 | Closed fractal pivot | ORIGIN | Implement; strict tie rejection. |
| F05 | Trailing rolling extreme | ORIGIN | Implement when golden coverage is complete. |
| F06 | Anchored equal-level cluster | ORIGIN | Interface + named abstention until max-span research decision. |
| F07 | UTC session level | E01 | Consume and validate only; estate implementation. |
| F08 | Directional structure / protected swing | ORIGIN | Interface + named abstention until reducer version is ratified. |
| F09 | Accepted break / BOS / CHOCH | ORIGIN | Implement after F08 semantic closure. |
| F10 | Three-bar FVG | ORIGIN | Implement after TTL/invalidation parameters close. |
| F11 | Qualified displacement | ORIGIN | Implement after parameter closure. |
| F12 | Causal order block | ORIGIN | Implement after zone/TTL/golden closure. |
| F13 | Excursion and reclaim | ORIGIN | Implement after parameter closure. |
| F14 | Departure / first retest | ORIGIN | Implement in reaction milestone. |
| F15 | Trade-flow imbalance | ORIGIN | Implement. |
| F16 | Best-level OFI | ORIGIN | Implement when golden coverage is complete. |
| F17 | Book-depth tilt | ORIGIN | Interface + named abstention until minimum-depth research decision. |
| F18 | Candidate geometry / geometric RR | ORIGIN | Implement; directional stop invariant and RR floor. |
| F19 | Opportunity clustering / alias control | ORIGIN | Implement with frozen earliest prospective root; never re-root. |
| F20 | Risk sizing | E08 | Contract, binding, and vectors only here; selected signed policy only. |
| F21 | Maker price compilation | E09 | Contract and vectors only here. |
| F22 | Emergency reducing IOC | E09 | Contract and reduction-only vectors only here. |
| F23 | P&L, costs, R, markout | E10 | Contract and vectors only here. |

## 6 · Contract and binding closure before semantics

Before any formula milestone can claim semantic implementation:

- Materialize strict additive `evidence_receipt.v2`, `task_status_event.v2`, and
  `gate_receipt.v2` schemas plus a semantic validator; a shape-valid receipt is not sufficient.
- Catalog all ten RC4 contracts: `engine_control_manifest.v2`,
  `runtime_lever_registry.v1`, `runtime_lever_attestation.v1`, `shadow_trade.v1`,
  `shadow_rejection_audit.v1`, `paper_trade.v1`, `shadow_health.v1`,
  `execution_authorization.v3`, `execution_cmd.v2`, and `fill.v3`.
- Migrate all 105 formula-parameter binding rows into `binding.v2` with semantic slot,
  cardinality, condition, scope, precedence, consuming node/edge, and overlap validation.
- Keep blocked rows blocked. The effective starting state is 98
  `BLOCKED_BINDING_V2_MIGRATION`, four other `BLOCKED`, and three `ACTIVE`; structural migration
  does not ratify a value.
- Build an explicit semantic capsule registry. Ordinal RC2 parameter names may not be guessed or
  silently mapped to RC1 capsule families.
- Validate one combined RC3+RC4 composition manifest: referential closure, cycle freedom, no
  milestone inversion, one scheduling owner per task, and preservation of source authority.

## 7 · Two-track implementation program

### Track A — TriadOrigin repository

| Milestone | Repository outcome | Gate correspondence only |
|---|---|---|
| B00 | Historical control-package import and planning source merged. | None |
| B00C | Corrective control closure: revised plan, reviewed ledger, branch protection/waiver, strict receipt law, and post-merge B00/R00 disposition. | Precondition to B01 |
| B01 | Contract, identity, receipt, RC4 catalog, and `binding.v2` foundation. | G0 subset |
| B02 | Deterministic kernel, F00, journal anchor, fencing/checkpoint, timing registry; E01 interface validators. | G0/G1 subset |
| B03 | F02–F09 feature/structure layer, with blocked emitters remaining explicit abstentions. | G2 subset |
| B04 | F10–F13 and F15–F17 structures/flow plus append-only lifecycle. | G2 subset |
| B05 | Four-plane substrate: exact controls, refusals, SHADOW/PAPER ledgers, health, resolver, and physical isolation. | RC4 L0–L6 subset |
| B06 | F14/F18/F19, semantic capsule registry, isolated capsule host, candidate publisher, trial registration, and mandatory SHADOW fork. | G3 subset |
| B07 | Signed configuration, comparator, verify-only authority projection, legacy bridge, replay, and zero-venue-capability service. | G4 subset |
| B08 | Exact read faces and evidence projections; no control verbs. | G5 evidence-surface subset |
| B09 | Complete conformance matrix, estate F20–F23 catalog/vectors, migration and incident runbooks. | G6 interface subset |
| B10 | Independent audits, terminal receipt, implementation report, and local checkpoint. | Repository closure only |

No Track A milestone is a G-gate pass. Until the estate predecessor gates close, its result is
`IMPLEMENTED_UNVERIFIED / DENIED_SAFE_HOLD`.

### Track B — estate integration and certification

| Stage | Required estate outcome |
|---|---|
| G-1 | Credential rotation, account/environment identity, deployed/source parity, process/writer census, scope freeze, and current evidence. |
| G0 | Strict contracts, manifests, leases, quarantine, receipt validation, and compatibility closure across owning repos. |
| G1 | Current Binance ingress certification, E00/E01 sequencing, finalized bars, UTC sessions, reconnect, and replay. |
| G2 | Semantic parameters/bindings, deterministic structures, identical-offset proof, and data-quality readiness. |
| G3 | Capsule registry, preregistered trial families, leave-one-conjunct ablations, candidate completeness, and no-money proof. |
| G4 | Paired replay, full divergence taxonomy, fault campaigns, frozen chronological OOS, PBO/DSR/multiplicity, and maker-fill calibration. |
| G5 | Prospective OFF/OFF/OFF/LIVE operation with physical venue denial, current SHADOW health, frozen build/trial, and honest read faces. |
| G6 | E07/E08/E09/E10 decision, selected-policy sizing, reservation, execution, strict fill.v3, reconciliation, protection, and outcome rehearsal. |
| TESTNET | Same-digest TESTNET certificate before any LIVE venue environment. |
| G7 | One signed, isolated canary only after every owner blocker is ratified. |
| G8 | Economic proof on strict, disjoint populations and complete lineage. |
| G9 | Production risk values, progressive scope, estate-wide checkpoint, cutover, and rollback proof. |

Track B begins in parallel where it does not consume unfinished Track A semantics. External tasks
are not an end-of-build backlog: each is due before its consuming gate.

## 8 · Four-plane implementation minimum

The four-plane milestone is incomplete unless all of the following exist and are tested:

- Exact enums, all 35 invalid aliases imported from the signed bundle, all 10 valid combinations,
  and all 32 refusal codes with exact containment actions.
- `shadow_activation=LIVE` fixed; no setter, environment fallback, or alternate alias.
- SHADOW dispositions `REJECTED`, `ACCEPTED_NOT_EXECUTED`, and
  `PROVEN_NO_VENUE_EFFECT`; the last is legal only after authoritative reconciliation.
- Malformed/non-tradeable inputs append to `shadow_rejection_audit.v1` as
  `SHADOW_UNTRADEABLE`; they never become fabricated trades.
- Frozen pre-disposition geometry/watermark, versioned latency/fee/funding/slippage/partial/no-fill
  model, fixed evaluation notional, bps/R outputs, causal resolution, and honest `NO_FILL`.
- Keyless PAPER executor with separate virtual orders, fills, positions, and outcomes; no venue
  adapter or credential import path.
- SHADOW persistence deadline, heartbeat, stale/backlog/coverage checks, and recovery. Writer or
  resolver staleness and missed persistence force venue and PAPER activation `OFF`.
- Physical storage, identity, query, and aggregate separation across SHADOW, PAPER, TESTNET, and
  LIVE.

## 9 · PR, receipt, and checkpoint law

1. Branch protection issue #5 is blocking B01. Configure a ruleset requiring exact-head CI,
   review, resolved conversations, and no force/direct push or admin bypass; otherwise record a
   signed, time-bounded waiver with equivalent guarded-merge evidence.
2. Each milestone has one source PR. Green CI permits merge but does not certify a gate.
3. After the source PR merges, reproduce evidence against the exact merged `main` hash and land a
   separate evidence-only receipt PR. The next milestone branch may not open until that receipt is
   merged and validated. The uploaded “one-behind” scheme is rejected.
4. A code-merge receipt and a gate receipt are distinct. Gate receipts require exact scope,
   build/config/contract/data digests, observation and expiry times, current dependencies,
   independent reviewer, no P0/P1/open blocker, and tested stop/rollback.
5. B10 requires a detached post-merge terminal receipt over the actual B10 merge hash, followed by
   the TriadOrigin-local checkpoint. G9 later requires an estate-wide checkpoint across every
   touched repository/process.
6. A mandatory verification may be `BLOCKED`, but never “named-deferred” and counted green.

## 10 · Verification law

Every capability lands with its task → acceptance criterion → verification → receipt edges.
Conformance views must account for all 408 inherited RC1 tests, all 1,523 RC3 effective
verifications, and all 125 RC4 fixtures. Counts alone are not evidence.

The core falsification battery includes:

- prefix, restart, duplicate, partition, watermark, and checkpoint invariance;
- LONG/SHORT mirror and exact integer/rational boundary tests;
- no-lookahead, no-future-mutation, placebo and parameter-neighborhood tests;
- lifecycle monotonicity, frozen identity, withdrawal, and illegal-transition rejection;
- lease/epoch split-brain, staleness, failover, full disk, and evidence-writer failure;
- four-plane no-side-effect, population-separation, alias, malformed input, and health failure;
- identical-offset paired replay, full divergence classification, and result-access controls;
- capability/import scans proving ORIGIN cannot reach venue/order/credential or E07/E08 authority.

`tools/e2e_audit.py` grows in the same PR as each capability. It is a diagnostic walk, not a gate
receipt by itself.

## 11 · Decision schedule

`09_OPEN_QUESTIONS.md` is now a disposition register, not a questionnaire deferred to B10.
Decisions are due as follows:

| Due before | Required dispositions |
|---|---|
| B00C receipt | A1–A5, G2, branch protection/waiver, R00/B00 receipt law |
| B01 merge | A7, E2/E3, strict schemas, capsule-ID policy, combined composition validation |
| B02 semantic merge | E4/E5 and E01 ownership of F01/F07 |
| B03 result emission | C1/C3 plus every consumed parameter/binding |
| B04 result emission | C2 plus formula-specific parameter/golden blockers |
| B06 candidate emission | D, E6–E9, semantic capsule registry, trial registration |
| G4 | F2/F3 transport census and frozen legacy source |
| G5 | F1/F4/F5 estate homing and current SHADOW health |
| G7 | B3–B8 signed owner values and isolated account identity |
| G9 | B1/B2 signed production values |

An explicit decision to keep a value `NOT_RATIFIED` is a closed planning answer and an open
activation blocker. It does not authorize a substitute.

## 12 · Immediate next action

Do not start B01. First execute B00C and close, in order:

1. merge this reconciled plan set and corrected formula/authority map;
2. replace the heuristic-only ledger claim with row-reviewed overrides and combined RC3+RC4
   validation;
3. configure branch protection or obtain a signed equivalent waiver;
4. define/validate strict receipt v2 and seal the missing post-merge B00/R00 disposition against
   current `main`;
5. confirm `B00_RECEIPT_PASS`, then open B01.

