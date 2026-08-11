# TRIAD / UPONLY — B00-to-BN Closure Marathon Plan

**Classification:** `COORDINATION_ONLY_NON_EVIDENCE`  
**Plan version:** `2026-08-11.2`  
**Status:** `CONFIRMED_EXECUTING`  
**Execution start:** 2026-08-11  
**Current work:** `C0-NORM`, `C0-OPS`, and B00R G2 diagnostic/source preparation  
**Invariant posture:** `OFF/OFF/OFF/LIVE`  
**B00R–B10 permitted result:** `PASS_REPOSITORY_SAFE_HOLD`  
**BN permitted result:** `PASS_TERMINAL_SAFE_HOLD`

This plan is intentionally stricter than “tests green.” It specifies the subject, failure-first
diagnostic, fix scope, test, provider chronology, receipt, runtime proof, independent review, and
next-entry condition for every milestone.

## 1. Execution laws

### 1.1 Diagnostic before fix

Before changing a milestone subject, capture a baseline record containing:

- canonical composite milestone ID and registry digest;
- repository, branch, commit, tree, predecessor, and changed-path classification;
- exact command, tool/runtime versions, environment allowlist, start/end time, and return code;
- expected versus actual result and a typed failure ID;
- severity, owning milestone, proposed fix boundary, and evidence digest;
- explicit statement of what the test does not prove.

No baseline result may be overwritten. A later checkpoint supersedes it.

### 1.2 One subject per claim

Every PASS binds exact source, build, configuration, contracts, bindings, provider objects,
deployment, environment, route, account, lease, and evidence subjects as applicable. A green test
against a different commit, checkout, Python, dependency set, ruleset, runtime, or cohort is not a
PASS for the target subject.

### 1.3 Source and receipt cadence

For each build milestone:

1. validate the predecessor receipt/anchor;
2. branch from the exact receipt merge;
3. freeze acceptance profile and adoption manifest;
4. baseline failures;
5. implement only declared scope;
6. run targeted falsification and cumulative regression;
7. freeze one final source head;
8. obtain exact-head CI, resolved threads, and independent approval;
9. ordinary two-parent merge with verified parents/tree;
10. reproduce the merge hermetically;
11. open a separate append-only evidence-only receipt PR;
12. obtain exact-head CI/review and merge with no intervening main change;
13. protect/publish the anchor or checkpoint and run the terminal gate;
14. create the successor only from the validated receipt merge.

### 1.4 Plan persistence without chronology drift

- Mutable plan/master/checkpoints live only on
  `coordination/b00-bn-closure-marathon-20260811`.
- The branch is append-only by commit: no force-push, amend, or rebase.
- It is never merged into `main` during the closure ceremony.
- Immutable C0 normative controls may enter PR #34 before final source freeze.
- Receipt PRs contain only their declared evidence namespace and one canonical receipt.
- After every material transition, append a checkpoint and verify authoritative refs did not move.

## 2. Severity and waiver law

| Severity | Meaning | Rule |
|---|---|---|
| P0 | Can forge authority, cause or hide side effects, contaminate planes, accept wrong subjects, falsify evidence, violate chronology, or misstate a terminal result | Blocks the milestone and every dependent milestone. No ordinary waiver. A signed scope change may relocate ownership but cannot turn the defect into PASS. |
| P1 | Can violate formula/contract semantics, causality, deterministic replay, reconciliation, compatibility, or safe recovery | Blocks the owning milestone and terminal closure. |
| P2 | Material operability, observability, performance, or maintainability defect without a demonstrated safety/authority failure | Must be closed or explicitly carried with owner, deadline, and bounded impact before terminal audit. |
| P3 | Documentation or cosmetic defect with no semantic effect | May be scheduled, but contradictory operator instructions become P1. |

An issue cannot be downgraded because a test count is high. Any severity change requires a written
reproduction analysis and independent review.

## 3. Canonical milestone and digest law

New milestone identity is:

`<track_id>::<milestone_id>@sha256:<scope_digest>`

`scope_digest` is lowercase SHA-256 over canonical UTF-8 JSON with sorted keys, no insignificant
whitespace, one terminal newline excluded from the hash, no floats, no duplicate keys, and domain:

```json
{
  "domain": "triad.closure.milestone_scope.v1",
  "track_id": "ORIGIN_REPAIR",
  "milestone_id": "B00R_G2",
  "scope_version": "1",
  "scope_text": "exact normative scope",
  "owns": ["sorted semantic units"],
  "excludes": ["sorted semantic units"]
}
```

Allowed lifecycle states are `NOT_STARTED`, `BASELINED_FAIL`, `IN_PROGRESS`, `BLOCKED`,
`SOURCE_READY`, `SOURCE_MERGED`, `RECEIPT_READY`, and `CLOSED`. `CLOSED` requires the physical
receipt/anchor, not a manual status edit.

## 4. Current diagnostic checkpoint

### 4.1 Exact subjects

- `main`: `ba495ba90e0e4eff50ed75d2443f9cc12ce6ddcd`.
- canary: same `ba495ba…` before-state.
- PR #34: `77a1ff3c7d31ba8b817be750976291c690c87b23`, draft, zero reviews.
- provider CI run: `31484607824`.
- local diagnostic: fresh full clone, CPython 3.11.15, pinned constraints.

### 4.2 Observed failures

| Failure ID | Severity | Actual | Owner |
|---|---:|---|---|
| `C0-NORMATIVE_REGISTRY_ABSENT` | P0 | No canonical composite registry/crosswalk/profile law exists. | C0 |
| `LOCAL_CONSTRAINT_PATH_NOT_RELOCATABLE` | P1 reproducibility | Documented relative `PIP_CONSTRAINT` breaks isolated wheel smoke after cwd change. | B00R |
| `G2_AUTHORITY_PINS_ABSENT` | P0 | Four required protected digests are empty. | B00R ceremony |
| `G2_RULESET_CAPTURE_SYNTHETIC` | P0 | Committed payload is declarative, not provider-originated. | B00R provider |
| `G2_PROVIDER_PIN_STALE` | P0 | Protected pin and PR-head raw bytes disagree. | B00R provider |
| `G2_RULESET_LIVE_NOT_ATTESTED` | P0 | Exact targets, exclusions, bypass, checks, merge mode, force/delete law are unproved. | B00R provider |
| `G2_NEGATIVE_CANARY_ABSENT` | P0 | No dedicated pre-source rejected push/rule-suite record. | B00R provider |
| `G2_INDEPENDENT_REVIEW_ABSENT` | P0 | PR #34 has zero submitted reviews. | B00R reviewer |
| `G2_RECEIPT_AND_ANCHOR_ABSENT` | P0 | No receipt PR or protected G2 anchor. | B00R receipt |
| `RUNTIME_NOT_ATTESTED` | P0 for runtime claims | Current deployed subject is unknown. | B05/B10/BN |

### 4.3 Passing source checks that do not close B00R

- 2,000 tests passed per CI hash seed;
- source/history/contract manifests passed;
- reproducible sdist/wheel and installed-wheel checks passed in CI;
- no forbidden E02 capability imports;
- E2E 24/24;
- build ledger 1,250/1,250 reviewed;
- combined 1,250-task DAG acyclic with one scheduling owner.

## 5. C0 — control and semantic freeze

### 5.1 Split

- `C0-NORM`: immutable machine registry, crosswalk, profiles, decision/disposition law, and tests.
  These bytes enter PR #34 before final freeze.
- `C0-OPS`: mutable master, plan, checkpoint index, and append-only checkpoints. These remain on
  the coordination branch.

### 5.2 C0-NORM deliverables

1. strict milestone-registry schema and generated registry;
2. legacy/current crosswalk with no ambiguous new bare identifiers;
3. exact B00R–BN scope, ownership, exclusion, predecessor, paths, tests, review count, and result;
4. acceptance-profile schema and one profile for every current corrective milestone;
5. D-01..D-09 decision record with `authenticated=false` until real signature/pin exists;
6. audit-conflict disposition ledger, including the D-02 sequencing supersession;
7. milestone × T0–T12 layer matrix;
8. generated status/checklist views bound to the registry digest;
9. local-work forensic inventory with no destructive cleanup;
10. secret scanner over source, Git history additions, logs, URLs, and checkpoint bytes.

### 5.3 C0-NORM attacks

- duplicate composite key, duplicate bare/current ID, wrong digest, noncanonical JSON;
- missing predecessor/profile/adoption/receipt path;
- dependency cycle or unresolved dependency;
- zero-task B10, missing BN aggregate, future expansion silently deleted;
- status changed without generated registry update;
- formula allocated to zero or multiple owner milestones;
- B00R scope widened to formula/capability/runtime implementation;
- unsigned decision represented as authenticated;
- token, bearer header value, query token, private key, or credential material committed.

### 5.4 C0 exit

`PASS_CONTROL_FREEZE_SAFE_HOLD` requires deterministic artifacts, passing tests, real owner
authentication/pin, and exact-head independent review. Until then C0 remains `IN_PROGRESS` or
`BLOCKED`, even if the code is complete.

## 6. B00R G2 — repository/evidence root

### 6.1 Exact source allowlist

Permitted semantics:

- C0 normative registry/crosswalk/profile controls;
- B00R policy, generation ledger, historical invalidation, authority templates;
- source/history/build/package/DAG/CODEOWNERS verification;
- provider capture/validation, direct-push canary law, source/receipt chronology;
- clean-runner producer/verifier and rollback capture;
- receipt-v3/tag-rule/anchor/B01C-entry guard;
- documentation that states only the safe-hold result.

Forbidden semantics:

- production formulas F00–F23;
- contract or binding activation/implementation;
- production capability elevation;
- E00/E01/E03–E10 service or adapter implementation;
- deployment, runtime configuration, credentials, venue calls, activation;
- `evidence/**` in the source PR.

Inherited defective implementation bytes remain explicitly unadopted and blocked behind the G2
entry gate. B00R binds the repository tree for ancestry; it does not certify every module.

### 6.2 Deterministic test chain

Run in fresh full clone with Python 3.11 and exact pins:

1. pytest with `PYTHONHASHSEED=0`;
2. pytest with `PYTHONHASHSEED=1`;
3. exact collected-test-ID equality;
4. source hashes and historical evidence immutability;
5. contract byte manifest and schema;
6. reproducible sdist/wheel;
7. installed-wheel smoke;
8. forbidden-capability scan;
9. full E2E walk;
10. build-ledger regeneration;
11. combined DAG;
12. C0 registry/status generation and attacks;
13. exact CODEOWNERS/provider identity check.

Every command uses an absolute constraint path. The final receipt reproduction records exact argv,
environment allowlist, interpreter and package digests, streams, return codes, artifacts, and times.

### 6.3 Authority ceremony

1. materialize authenticated G2 trust registry;
2. materialize and owner-sign `DEC-AUTHORITY-BUNDLE-002`;
3. materialize and owner-sign `DEC-RECEIPT-PROFILE-002`;
4. materialize and owner-sign `DEC-B00-REPAIR-002`;
5. externally pin the four exact byte digests;
6. validate role, key, scope, time, revocation, quorum, and subject set;
7. never commit private keys or protected variable values.

### 6.4 Provider controls

Capture a real active repository ruleset whose exact normalized law is:

- target branches exactly `refs/heads/main` and `refs/heads/b00r-ruleset-canary`;
- exclusions `[]`;
- bypass actors `[]` and current user cannot bypass;
- pull request required;
- one independent CODEOWNER approval;
- stale approvals dismissed, last-push approval, threads resolved;
- strict required check `test-and-verify` from GitHub Actions integration `15368`;
- allowed merge methods exactly `["merge"]`;
- force push and deletion blocked.

Externally pin the raw provider bytes. Execute a dedicated direct push against the canary and retain
the rejection plus rule-suite response before source merge. Historical PR #33 proof cannot be reused.

### 6.5 Source and receipt close

After authority/provider objects exist:

1. freeze one PR #34 source head;
2. exact-head CI passes all deterministic and external gates;
3. independent reviewer approves that head and all threads resolve;
4. ordinary two-parent merge with first parent `ba495…` and second parent the reviewed head;
5. reproduce the merge hermetically;
6. install/capture/pin the G2 tag ruleset;
7. create separate append-only G2 receipt PR;
8. exact-head receipt CI and independent approval;
9. merge with no intervening main commit;
10. publish protected annotated `B00R_RECEIPT_ANCHOR_G2`;
11. run terminal gate and close issue #5 only on literal PASS.

Exit: `PASS_REPOSITORY_SAFE_HOLD` plus reproducible
`PASS_B01C_ENTRY_BASE:<g2_receipt_merge>`.

## 7. B01C — authority composition, contracts, bindings, capability

### 7.1 RC5 effective consolidation

Recover missing RC1/RC2/RC3 inputs by exact hash or mark them `UNAVAILABLE` and withdraw completeness
claims. RC5 must deterministically apply these ten RC4 supersessions:

1. LIVE-only/no-testnet becomes exact `LIVE|TESTNET|OFF`, with PAPER/SHADOW separate;
2. testnet-retirement rows are superseded; TESTNET remains physically isolated;
3. global testnet rejection becomes mismatch/mixed-bundle rejection;
4. LIVE-only binding cells become exact LIVE and TESTNET bindings;
5. F20 CANARY/PRODUCTION budget branch becomes one already-selected signed risk policy;
6. `activation_manifest.v1` becomes `engine_control_manifest.v2`;
7. arbitrary receipt modes become strict v2 schemas plus semantic validation;
8. W06/G5 connected/prospective-dark vocabulary becomes exact environment/activation fields;
9. PAR-170 boolean becomes `OFI_NORMALIZED_VARIANT_ACTIVATION=OFF`;
10. MCP family booleans become `LIVE|OFF` activation; legacy values remain raw evidence only.

RC5 includes exact preimages, schema, deterministic applier, conflict report, source manifest,
stable digest, and independent regeneration.

### 7.2 Contract/binding/capability closure

- publish additive contract majors; never mutate published bytes;
- require pinned full Draft 2020-12 plus semantic validation;
- add missing union/transport/field-level schemas and v2→v3 migration;
- authenticate all 105 binding rows and disposition all 98 migration-blocked rows individually;
- reject incomplete formula sets, duplicate scopes, sentinels, unknowns, stale signatures, widening;
- replace forgeable in-process markers with content-addressed authenticated capability verification;
- make the real `--authority` CLI path authenticate or return nonzero `UNAVAILABLE_AUTHORITY`;
- prove installed-wheel independence from repository-relative resources.

Exit: separate source/receipt PASS on exact G2 ancestry.

## 8. B02C–B04C — ingress and formulas

### B02C

- fix exact scale-independent F00 decimal-to-tick/step integrality and overflow;
- certify E01 ownership of F01/F07 and ORIGIN consume-only behavior;
- enforce canonical E01 envelope across every F01–F17 ingress;
- prove finality, watermark, dedupe, revision, metadata, fencing, restart, and replay.

### B03C

- F02 N+1 bars and gap/revision law;
- F03 PAR-036 plus same-bar ambiguity decision;
- F04 exact tie law;
- F05 direct golden;
- F06 tested refusal until span/lifecycle decision;
- F07 producer golden;
- F08 tested refusal until reducer ratification;
- F09 first-terminal lifecycle and no BOS/CHOCH without F08.

### B04C repair order

1. F13 direction/horizon/consecutive state;
2. F10 gap-before-evaluation and lifecycle precedence;
3. F12 tie/one-BOS lineage/TTL/mitigation;
4. F11 full OHLC and exact mirrors;
5. F14 knowledge→departure→contact causality and TTL;
6. F15 event-time quote-notional window/provenance;
7. F16 continuous valid book, RC4 enum, normalization and golden;
8. F17 positive minimum depth and zero refusal.

Every enabled formula gets units, exact arithmetic, mirrors, equality/±1 tick, gaps, duplicates,
out-of-order/late events, causality, restart parity, missing/stale input, overflow, and cross-language
goldens. A blocked formula may close only as an explicit tested refusal.

## 9. B05C — physical four-plane isolation

Static enums are insufficient. Prove separate processes, endpoints, accounts, credential
fingerprints, routes, leases, ledgers, storage, queries, dashboards, and side-effect boundaries for
SHADOW, PAPER, TESTNET, and LIVE. PAPER is keyless; SHADOW holds no venue identity; TESTNET and LIVE
cannot share reachable credentials/accounts/routes. One mixed member rejects the whole bundle.

Required on-box proof includes process/network census, mounts/ACLs, routes/topics/DBs, fencing,
cross-plane contamination attacks, fresh attestations, rollback/restore, and at least 24 hours of
non-authoritative SHADOW soak.

**Authorization checkpoint:** current authority permits read-only census only. Deployment/restart
and proof of newly changed source require later explicit authorization. B05 cannot close before it.

## 10. B06R–B07

### B06R

Adopt the exact corrected F14 digest; enforce F18 directional geometry and exact 2R; make F19 root,
aliases, revisions, TTL, compaction, and ordering deterministic; freeze E/S/T; atomically persist the
SHADOW copy. No decision, sizing, venue, fill, P&L, or outcome authority.

### B07

Separate `engine_cohort` and `intelligence_arm`; authenticate scoped lease/authority facts; prove
bridge detachment/idempotency and same-code replay; keep E03–E06 advisory paths unable to call
E07/E08/E09.

## 11. Cross-estate prerequisites

- WAVE-C-001: additive strict `fill.v3`, dual-publish, reconcile every producer/consumer, signed
  supersession, measured cutover;
- WAVE-C-005: one canonical instrument/venue/account-mode registry and deterministic compiler;
- WAVE-C-006: typed `VenueExecutionPlan` from E08 authorization through E09 execution;
- E08 owns F20; E09 owns F21/F22; E10 owns F23;
- AG1–AG4/Kairos/Logos/Fusion remain typed advisory/casefile lanes with no decision/risk/execution
  authority.

Each owner repository needs its own source and receipt evidence. Origin cannot certify them by proxy.

## 12. B08–B09

### B08

Freeze bounded read faces and response envelopes before implementation. Every response names source,
plane, cohort, scope, revisions, times, freshness, completeness, and typed `OK|UNAVAILABLE|
NOT_IMPLEMENTED|TOOL_TIMEOUT|NOT_MEASURABLE|STALE|NOT_ATTESTED`. Prove pagination/bounds,
cost/rate limits, cancellation, no side effects, no SHADOW/MONEY aggregation, injection/resource
attacks, query plans, and deployed-catalog parity.

### B09

Build the unique effective verification set by ID/lineage; never double-count inherited rows or
convert `NOT_RUN` to coverage. Bind every result to subject, command, environment, time, artifacts,
and owner. Close F20–F23 owner-service proofs and executable runbooks for migration, rollback,
split-brain, data gaps, unknown submit, partial fill/dust, protection, disconnect, isolation,
emergency reduction, backup restore, and DR.

## 13. B10 and BN

### B10

Create nonzero machine tasks, dependencies, acceptance criteria, verification rows, audit-subject and
report schemas, receipt profile, and checkpoint law. Freeze all subjects and require zero unresolved
P0/P1. Perform two genuinely independent audits:

1. semantic/source: authority, formulas, bindings, schemas, DAG, topology, compatibility, supply
   chain, chronology;
2. runtime/side effects: deployed identity, leases, routes, planes, MCP/read faces, money state,
   reconciliation, rollback/DR, secret/network boundaries.

B10 exit is exactly `PASS_REPOSITORY_SAFE_HOLD`.

### BN

Aggregate the B10 receipt, G-1..G9, all cross-estate receipts, and fresh runtime proof over identical
source/config/contract/binding/route/lease/environment/deployment subjects. Require convergent order,
algo-order, fill, position, protection, outcome, and idempotency ledgers; zero unresolved unknown
submits; successful restore/DR; bounded B08; soak; and both audits.

BN exit is `PASS_TERMINAL_SAFE_HOLD`. LIVE remains unauthorized.

## 14. Milestone × test-layer matrix

| Stage | Required layers |
|---|---|
| C0 | T0 plus registry/schema/DAG/status/secret falsification |
| B00R | T0, T5, T6, T7 |
| B01C | T0–T3, T5, T7 |
| B02C–B04C | T2–T5, T7 |
| B05C | T2, T7–T9, T11 |
| B06R–B07 | T2–T5, T7, relevant T9 |
| Cross-estate | T2–T4, T8–T11 |
| B08 | T2, T5, T7–T9, side-effect denial |
| B09 | T0–T11 cumulative |
| B10 | T0–T12 |
| BN | Fresh T7–T12 aggregate over identical subjects |

T0 corpus; T1 composition; T2 contracts; T3 formulas; T4 replay/state; T5 supply chain; T6
provider; T7 receipt; T8 runtime; T9 plane isolation; T10 execution; T11 chaos/DR; T12 independent
audit.

## 15. Reviewer and authorization gates

- PR #34 source reviewer: `djordi10` or another genuinely separate qualified CODEOWNER.
- Receipt reviewer: separate from author/evidence producer; may be the same independent reviewer if
  governance permits and exact-head duties are independently performed.
- B10: two independent audits; owner-controlled aliases/keys do not create independence.
- Before B05 deployed proof: explicit deployment/restart authorization.
- Before TESTNET/LIVE: explicit bounded promotion authorization.
- Before B05/B10 security attestation: rotate exposed operational credentials.

## 16. Checkpoint rule

Append a checkpoint after every baseline, fix batch, CI run, review transition, merge, receipt,
anchor, runtime observation, closure, or blocker change. Each checkpoint records:

- exact refs and immutable subject digests;
- tests with actual result and evidence digest;
- closed/open defects and severity;
- authority/provider/runtime status;
- next gate and stop condition;
- master and plan SHA-256;
- confirmation that `OFF/OFF/OFF/LIVE` and authoritative refs remained unchanged unless the recorded
  authorized ceremony step required a specific ref transition.

No checkpoint can claim source, receipt, runtime, or terminal PASS by narrative alone.
