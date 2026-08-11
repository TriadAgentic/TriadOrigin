# TRIAD / UPONLY — B00-to-BN Closure Marathon Plan

**Classification:** `COORDINATION_ONLY_NON_EVIDENCE`  
**Plan version:** `2026-08-11.4`
**Status:** `CONFIRMED_EXECUTING`  
**Execution start:** 2026-08-11  
**Current work:** owner/provider authority blockers, exact-head review, and `C0-OPS`
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

### 1.5 Total task-binding sidecar law

The canonical 1,250-row build ledger is an input, not proof that tasks are assigned or satisfiable.
The C0 task-binding sidecar must enforce:

1. set equality between the 1,250 unique ledger `task_id` values and 1,250 unique sidecar rows;
2. exactly one canonical composite lane for each task, or one explicit blocking/deferred disposition
   that cannot contribute to PASS;
3. exact source-task and independent-review-row digests, plus one current composite lane or one
   explicit blocking/deferred disposition for every legacy task; no legacy task may map to C0 or
   B00R;
4. rejection of missing/orphan/duplicate tasks, bare milestone IDs, unknown criteria/verifications,
   cross-lane dependency bypass, digest drift, and numeric-count substitution;
5. for B10, a nonzero task set and at least one bound acceptance criterion and verification for
   every B10 task. B10 cannot pass merely because the three counts are nonzero.

### 1.6 Append-only status-event and generated-view law

Status truth is an ordered append-only event stream. Every event binds a unique event ID, task and
composite lane, prior/next state, exact source/config/control/evidence subjects, actor principal and
role, applicable reviewer binding, UTC, and transition reason. The validator rejects event forks,
gaps, duplicate sequence numbers, illegal transitions, stale subjects, missing evidence, and any
attempt to waive an open P0/P1.

The human-readable status file is regenerated deterministically from the event stream, registry,
task-binding sidecar, profiles, and their digests. It is never independently editable authority.
PASS/CLOSED requires the complete task/criterion/verification set, required receipts/anchors,
exact-head checks/reviews, and zero unresolved P0/P1. A manual snapshot edit or missing event fails
closed.

### 1.7 Reviewer identity, role, and disjointness law

Every review record binds the reviewer principal, authenticated provider identity, organization and
repository role, CODEOWNERS/path authority when required, exact reviewed head/tree, submitted state,
time, and review digest. A head change, dismissal, or later decisive review invalidates the prior
approval. Independence is evaluated by controlling person/entity and credential/key control, not
by distinct display names. Author, owner-decision signer, evidence producer, and test-result producer
cannot satisfy their own independent-review slot. B10's semantic/source and runtime/side-effect
audits require two disjoint qualified principals and disjoint production roles, with adjudication by
a separately bound authority.

### 1.8 Profile/matrix equality law

For every lane, the validator compares the acceptance profile and T0–T12 matrix bidirectionally.
Every profile test appears in the matrix with the same targeted/cumulative/external/aggregate role;
every non-`NOT_APPLICABLE` matrix obligation appears in the profile. Unknown, missing, extra, or
misclassified test layers fail C0.

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

`<track_id>::<milestone_id>::sha256:<scope_digest>`

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
- PR #34 prior diagnostic head: `77a1ff3c7d31ba8b817be750976291c690c87b23`, draft, zero reviews.
- PR #34 prior intermediate head: `d2711b4c775864e43dd11ef8927a7a03355c638c`; superseded by a
  normal forward commit with no amend, rebase, force-push, or history rewrite.
- PR #34 published source head: open draft `76eb4db7f80580d5f451966d359e56ac3baa9179`;
  tree `7ab809a3c93ac07995168b7da9e935d3717ba5e7`; base `ba495ba…`; 66 SOURCE paths; PR body updated;
  zero submitted reviews, zero review threads, and zero requested reviewers.
- prior provider CI run: `31484607824`.
- current intermediate CI run: `31495102659` (#153), completed `FAILURE` on `d2711b4…`.
- exact-head CI run: `31501456871` (#154), job `93812221250`, `COMPLETED / FAILURE` on
  `76eb4db…`; deterministic engineering passed and authority/provider controls failed closed.
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

The C0 semantic review found six false-green gaps. Corrective bytes for all six are published at
`76eb4db…`, and both independent semantic audit plus exact-head deterministic engineering passed.
They remain gate-open until a qualified GitHub reviewer approves that same head and owner/provider
authentication is present:

| Review finding | Severity | Exact correction state |
|---|---:|---|
| `C0_LEGACY_CROSSWALK_INCOMPLETE` | P0 | Corrective total crosswalk is published; exact-head provider gates remain. |
| `C0_TASK_BINDING_AND_B10_REGISTRY_ABSENT` | P0 | Total 1,250-row binding and B10 nonzero task/criterion/verification law are published; exact-head provider gates remain. |
| `C0_XC01_PREREQUISITE_LANE_ABSENT` | P0 | Canonical XC01 lane is published; future owner-repository receipts remain blockers. |
| `C0_STATUS_PROJECTION_FALSE_GREEN` | P0 | Append-only event projection is published and reports 103 blockers with zero closures; exact-head provider gates remain. |
| `C0_PROFILE_MATRIX_CROSSCHECK_ABSENT` | P1 | Bidirectional profile/T0–T12 equality is published and semantically reviewed. |
| `C0_REVIEWER_IDENTITY_INDEPENDENCE_UNBOUND` | P1 | Binding validator is published; no qualified GitHub exact-head approval exists. |

The `LOCAL_CONSTRAINT_PATH_NOT_RELOCATABLE` P1 is separate: it was diagnosed failure-first and the
published fix normalizes the inherited relative constraint before cwd-changing wheel subprocesses,
with a regression that supplies the relative value. Local matching-tree tests pass; CI #154
confirmed the exact-head engineering path, while authority/provider gates failed closed.

Run #153 is engineering-green/provider-blocked, not C0-valid. Steps 1–20 and 23–24 passed: 2,030
tests at `PYTHONHASHSEED=0`, 2,030 at seed 1, test collection, source/history/contract verification,
reproducible package and installed
wheel, forbidden-capability/DARK gates, E2E 24/24, 1,250 ledger/DAG, and CODEOWNERS. Step 25 failed
`UNAVAILABLE_AUTHORITY_ROOT: authority_bundle:EXTERNAL_PIN_ABSENT:AUTHORITY_BUNDLE_G2_DECISION_SHA256`
with all protected pins still absent. Step 26 failed `UNAVAILABLE: SNAPSHOT_UNAUTHENTICATED
(owner/provider evidence absent) (main.ruleset.provider.json)`. This run does not close any of the
six semantic review gaps and cannot be reused after the source head changes.

### 4.3 Passing prior/local checks that do not validate `d2711b4…` or close B00R

- 2,000 tests passed per CI hash seed;
- source/history/contract manifests passed;
- reproducible sdist/wheel and installed-wheel checks passed in CI;
- no forbidden E02 capability imports;
- E2E 24/24;
- build ledger 1,250/1,250 reviewed;
- combined 1,250-task DAG acyclic with one scheduling owner.

Focused classifier/governance parity, 17 semantic-control tests, deterministic E2E 24/24, and the
1,250/1,250 ledger/DAG checks also passed on the earlier unpublished corrective worktree. Those
facts remain diagnostic only. The prior `d2711b4…` head contained intermediate false-green C0 bytes
plus two unwanted mutable files,
`docs/plan/closure/TRIAD_B00_BN_CLOSURE_MARATHON_LEDGER_2026-08-11.md` and
`docs/plan/closure/TRIAD_B00_BN_CLOSURE_MASTER_2026-08-11.md`; both are outside the B00R source law
and absent from the published forward-reconciled diff.

### 4.4 Published source engineering-green / provider-blocked result

Forward reconciliation produced head `76eb4db7f80580d5f451966d359e56ac3baa9179`, tree
`7ab809a3c93ac07995168b7da9e935d3717ba5e7`, with 66 positively classified SOURCE paths and neither
unwanted mutable closure-plan file. PR #34's body was updated. Local validation on the matching
final tree passed:

- 2,043 tests at `PYTHONHASHSEED=0` and 2,043 at seed 1;
- identical collected-test IDs with SHA-256
  `cad0c3ce11db29fabbdb9b698f30a0d3bdd9e84a84fa20495bf6a077825d7f67`;
- 67 source pins / 50 required artifacts, 11 historical objects, and 148 contract artifacts;
- reproducible sdist
  `1af431060cc3a034ddd4168da0120f75c811ba9a86b4438f40d028284fa6feb8` and wheel
  `5f42caced44929c2a9b56fbe079ff9983acab7978f3d779dd3b9838950b2316d`;
- installed-wheel, DARK/forbidden-capability, E2E 24/24, and 1,250/1,250 ledger plus acyclic
  2,383-edge DAG checks;
- independent semantic audit PASS over the published C0/B00R control semantics.

That semantic audit is not a submitted GitHub approval. Exact-head run `31501456871` (#154), job
`93812221250`, completed `FAILURE`. Steps 1–20 all succeeded; deterministic engineering step 23 and
live CODEOWNERS step 24 also succeeded. CODEOWNERS verified 17 critical patterns and `@djordi10`
admin. Exact-head pytest passed 2,043 tests at seed 0 in 202.08 seconds and 2,043 at seed 1 in
197.70 seconds. The decoded UTF-8 job log is 347,194 characters / 347,206 bytes with SHA-256
`1ad0488e1ba7b20861762e5e08ef93c628623b269125ad9a34bc57afd261238a`.

Step 25 failed with
`UNAVAILABLE_AUTHORITY_ROOT: authority_bundle:EXTERNAL_PIN_ABSENT:AUTHORITY_BUNDLE_G2_DECISION_SHA256`.
Step 26 failed with `UNAVAILABLE: SNAPSHOT_UNAUTHENTICATED (owner/provider evidence absent) (main.ruleset.provider.json)`. Receipt-only steps 21–22 skipped, as did downstream steps 27–30. The
terminal interpretation is `ENGINEERING_GREEN / C0_AND_B00R_BLOCKED`. The status projection retains
103 open blockers and zero closure claims. Provider ruleset truth is `NOT_ATTESTED`; protected
authority pins and exact-head GitHub review are absent.

## 5. C0 — control and semantic freeze

### 5.1 Split

- `C0-NORM`: immutable machine registry, crosswalk, profiles, decision/disposition law, and tests.
  These bytes enter PR #34 before final freeze.
- `C0-OPS`: mutable master, plan, checkpoint index, and append-only checkpoints. These remain on
  the coordination branch.

### 5.2 C0-NORM deliverables

1. strict milestone-registry schema and generated registry;
2. total legacy/current/future crosswalk with no ambiguous new bare identifiers and exact historical
   receipt/hash disposition where applicable;
3. exact C0–BN scope, ownership, exclusion, predecessor, paths, tests, review count, and result,
   including `ESTATE_CROSS_REPO::XC01` between B07 and B08;
4. acceptance-profile schema and one profile for every current corrective/cross-repository lane;
5. total 1,250-row task-binding sidecar and nonzero per-task B10 criterion/verification registry;
6. append-only task/milestone status-event schema, transition validator, and generated view;
7. reviewer-principal/role/exact-head/disjoint-control schema and validator;
8. D-01..D-09 decision record with authentication `NOT_CLAIMED` until real signature/pin exists;
9. audit-conflict disposition ledger, including the D-02 sequencing supersession;
10. milestone × T0–T12 matrix with bidirectional acceptance-profile equality;
11. local-work forensic inventory with no destructive cleanup;
12. secret scanner over source, Git history additions, logs, URLs, and checkpoint bytes.

### 5.3 C0-NORM attacks

- duplicate composite key, duplicate bare/current ID, wrong digest, noncanonical JSON;
- missing predecessor/profile/adoption/receipt path;
- dependency cycle or unresolved dependency;
- missing/orphan/duplicate task sidecar row; task-to-lane or digest mismatch; zero-task B10; a B10
  task without criterion or verification; numeric-count-only satisfaction;
- missing XC01 lane or direct B07→B08 bypass; missing BN aggregate; future expansion silently deleted;
- status snapshot changed without a valid append-only event; event fork/gap/illegal transition;
- PASS/CLOSED projected with missing receipt/anchor/review/evidence or any open P0/P1;
- profile/matrix missing, extra, or role-mismatched test layer;
- reviewer alias, self-review, producer collision, stale/wrong-head review, or B10 audit principals
  controlled by the same person/entity;
- formula allocated to zero or multiple owner milestones;
- B00R scope widened to formula/capability/runtime implementation;
- unsigned decision represented as authenticated;
- token, bearer header value, query token, private key, or credential material committed.

### 5.4 C0 exit

`PASS_CONTROL_FREEZE_SAFE_HOLD` requires all six semantic gaps closed in the published bytes,
deterministic artifacts, passing exact-head tests, real owner authentication/pin, and independent
exact-head GitHub review. Corrective source and semantic audit are present, but C0 remains
`SOURCE_ENGINEERING_GREEN_PROVIDER_BLOCKED`; no control-freeze closure is claimed.

## 6. B00R G2 — repository/evidence root

### 6.1 Exact source allowlist

Permitted semantics are enforced by a positive, deny-by-default path law:

- C0 normative registry/crosswalk/profile controls;
- B00R policy, generation ledger, historical invalidation, authority templates;
- source/history/build/package/DAG/CODEOWNERS verification;
- provider capture/validation, direct-push canary law, source/receipt chronology;
- clean-runner producer/verifier and rollback capture;
- receipt-v3/tag-rule/anchor/B01C-entry guard;
- documentation that states only the safe-hold result.

The only allowed prefixes are `docs/control/closure/` and `tests/b00r/`; all other permitted files
must be individually enumerated in `docs/control/b00r_policy.v2.json`. Deleting an allowed path does
not authorize a replacement elsewhere. The policy's exact scope digest must equal the canonical
B00R G2 registry scope digest or SOURCE classification and merge both fail.

The published head's final forward diff contains 66 SOURCE paths under this law.

Forbidden semantics:

- production formulas F00–F23;
- contract or binding activation/implementation;
- production capability elevation;
- E00/E01/E03–E10 service or adapter implementation;
- deployment, runtime configuration, credentials, venue calls, activation;
- `evidence/**` in the source PR.
- mutable closure ledgers under `docs/plan/closure/**`.

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

## 11. `ESTATE_CROSS_REPO::XC01` — explicit cross-repository prerequisite lane

XC01 is a canonical C0 registry row, acceptance profile, task/status lane, and receipt aggregate. Its
composite identity is `ESTATE_CROSS_REPO::XC01::sha256:<scope_digest>`. Its predecessor is B07; B08's
sole direct predecessor is XC01. A B07→B08 edge that bypasses XC01 fails the registry DAG.

XC01 owns only cross-repository identity and receipt convergence:

- WAVE-C-001: additive strict `fill.v3`, dual-publish, reconcile every producer/consumer, signed
  supersession, measured cutover;
- WAVE-C-005: one canonical instrument/venue/account-mode registry and deterministic compiler;
- WAVE-C-006: typed `VenueExecutionPlan` from E08 authorization through E09 execution;
- exact owner receipts proving E08/F20, E09/F21/F22, and E10/F23;
- AG1–AG4/Kairos/Logos/Fusion typed advisory/casefile boundaries with no decision, risk, execution,
  venue, or money authority.

Every input binds owner repository, exact source/receipt commit and tree, contract/binding/config
digests, reviewer principal/role, anchor, and compatibility result. All owner repositories need
their own source and receipt evidence; Origin cannot certify them by proxy. Missing, stale,
self-reviewed, subject-mismatched, or incompatible inputs keep XC01 and every successor blocked.
XC01 has no deployment, activation, order, cancellation, or venue-state authority.

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
| `ESTATE_CROSS_REPO::XC01` | T2–T4, T6–T12 as applicable to each owner receipt and aggregate |
| B08 | T2, T5, T7–T9, side-effect denial |
| B09 | T0–T11 cumulative |
| B10 | T0–T12 |
| BN | Fresh T7–T12 aggregate over identical subjects |

T0 corpus; T1 composition; T2 contracts; T3 formulas; T4 replay/state; T5 supply chain; T6
provider; T7 receipt; T8 runtime; T9 plane isolation; T10 execution; T11 chaos/DR; T12 independent
audit.

## 15. Reviewer and authorization gates

- PR #34 source reviewer: an authenticated, qualified CODEOWNER whose principal, role, exact-head
  approval, and disjoint control satisfy Section 1.7. A username string alone is insufficient.
- Receipt reviewer: separate from author, owner-decision signer, evidence producer, and result
  producer; every provider review record is exact-head and invalidated by a later head.
- B10: two independently controlled audit principals with disjoint production roles; aliases,
  accounts, keys, or bots controlled by one person/entity do not create independence.
- Before B05 deployed proof: explicit deployment/restart authorization.
- Before TESTNET/LIVE: explicit bounded promotion authorization.
- Before B05/B10 security attestation: rotate exposed operational credentials.

## 16. Checkpoint rule

Append a checkpoint after every baseline, fix batch, CI run, review transition, merge, receipt,
anchor, runtime observation, closure, or blocker change. Each checkpoint records:

- exact refs and immutable subject digests;
- prior/current source heads and any concurrent-ref mutation or reconciliation requirement;
- tests with actual result and evidence digest;
- closed/open defects and severity;
- authority/provider/runtime status;
- next gate and stop condition;
- master and plan SHA-256;
- confirmation that `OFF/OFF/OFF/LIVE` and authoritative refs remained unchanged unless the recorded
  authorized ceremony step required a specific ref transition.

No checkpoint can claim source, receipt, runtime, or terminal PASS by narrative alone.
