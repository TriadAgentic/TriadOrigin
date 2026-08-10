# B00R external-authority and clean-runner handoff

**Milestone:** B00R — forward-only governance, evidence, and receipt root repair  
**Repository:** `TriadAgentic/TriadOrigin`  
**Execution boundary:** GitHub provider controls, separated signing workstations, and an ephemeral clean runner  
**Trading/MCP box required:** **NO**  
**Document status:** operator handoff; live identifiers must be filled from the provider immediately before execution  
**Permitted terminal success:** `PASS_REPOSITORY_SAFE_HOLD`  
**Required runtime posture throughout:** `venue_environment=OFF`, `venue_activation=OFF`, `paper_activation=OFF`, `shadow_activation=LIVE`

> B00R is a repository-authority milestone. Logging into a trading, execution, database, or MCP host
> does not make any missing B00R control more authentic. Do not request box credentials, inspect
> venue secrets, restart services, or alter runtime configuration for this work. Any instruction that
> says B00R must be run on the trading box is a boundary error.

---

## 0. Boundary and acceptance matrix

| Work item | Execution surface | Trading/MCP box | Acceptance evidence |
|---|---|---:|---|
| Repaired engineering-head freeze and diagnostics | GitHub/local clean engineering runner | **Never** | Frozen head/tree plus deterministic diagnostic results |
| Authority decisions, trust bootstrap, and receipt signing | Separated owner/signing workstations | **Never** | Canonical signed public artifacts plus externally protected digest pins |
| Branch/tag rulesets and bypass rejection | Privileged repository-owner session outside PR CI | **Never** | Provider API capture, negative canary, external signature, external digest pin |
| Final exact-head strict CI/review/guarded repair merge | GitHub | **Never** | Provider checks/reviews/threads/merge bound to the post-ceremony final head |
| Hermetic reproduction | New ephemeral clean runner | **Never** | Fresh-clone identity, raw logs/results, artifact hashes, clean-tree proof |
| B00R evidence and bare receipt | Receipt-only Git branch/PR | **Never** | Only `evidence/B00R/**` and `evidence/receipts/B00R.receipt.v3.json` |
| Protected receipt anchor | GitHub protected annotated tag | **Never** | Immutable anchor object binding receipt merge and receipt digest |
| MCP deployment or investigation-family activation | Separate MCP-host guide | **Not B00R** | Explicitly excluded from this document |

The execution order is fixed: **freeze repaired engineering head and run diagnostics → use that exact
verifier for owner ceremony → install active no-bypass branch/tag rulesets and capture privileged
provider proof → incorporate any required public ceremony/proof artifacts and refreeze the final head
→ exact-head strict CI → independent review → guarded repair merge → clean reproduction → bare
receipt-only PR → guarded receipt merge → protected anchor**. PR CI may verify owner material but must
not fabricate or self-attest it.

All `<ANGLE_BRACKET>` values are mandatory operator inputs, not shell syntax. Resolve them from the
frozen head or provider, record them in Section 2, and review the expanded command before execution.

---

## 1. Outcome and non-goals

This handoff closes only the residual controls that cannot be manufactured by the implementation
author:

1. a frozen repaired engineering head with deterministic diagnostics;
2. authenticated authority decisions and an externally pinned trust root built with that verifier;
3. active provider-proven GitHub rulesets with privileged no-bypass proof captured outside CI;
4. exact-head strict CI, independent review, and guarded merge of the final post-ceremony repair head;
5. hermetic reproduction of the repaired merge on a fresh runner;
6. a single canonical bare receipt-only PR and protected immutable receipt anchor; and
7. a complete evidence return bundle.

It does **not**:

- arm Origin, paper trading, venues, or an executor;
- deploy to the TRIAD box;
- read or write live databases, ledgers, queues, or credentials;
- repair B01C or any later milestone;
- rewrite historical R00/B00/B00C/B01–B07 receipts; or
- turn a missing owner decision into an implementation default.

Until every acceptance row in this guide passes, report `BLOCKED_SAFE_HOLD`, not “mostly complete.”

---

## 2. Live execution record — fill before acting

Never copy identifiers from an old guide. Query GitHub again and fill this record.

| Field | Live value |
|---|---|
| Repository | `TriadAgentic/TriadOrigin` |
| Default branch | `main` |
| Audited starting commit | `<AUDITED_START_SHA>` |
| B00R repaired implementation PR | `<REPAIR_PR_NUMBER>` |
| B00R repaired implementation PR URL | `<REPAIR_PR_URL>` |
| Frozen engineering head/tree used for ceremony | `<ENGINEERING_FROZEN_HEAD_SHA>` / `<ENGINEERING_FROZEN_TREE_SHA>` |
| Final repaired head SHA | `<REPAIR_FINAL_HEAD_SHA>` |
| Final repaired tree SHA | `<REPAIR_FINAL_TREE_SHA>` |
| Exact-head repair CI run / job | `<REPAIR_CI_RUN_ID>` / `<REPAIR_CI_JOB_ID>` |
| Repaired merge SHA | `<REPAIR_MERGE_SHA>` |
| Repaired merge tree SHA | `<REPAIR_MERGE_TREE_SHA>` |
| Repaired merge time, UTC | `<REPAIR_MERGED_AT_UTC>` |
| Receipt `source_merge_time_us` | `<git show -s --format=%ct REPAIR_MERGE_SHA> * 1000000` |
| Authority-bundle decision pin | `AUTHORITY_BUNDLE_DECISION_SHA256=<DECISION_SHA256>` |
| Receipt-profile decision pin | `RECEIPT_PROFILE_DECISION_SHA256=<DECISION_SHA256>` |
| B00-repair decision pin | `B00_REPAIR_DECISION_SHA256=<DECISION_SHA256>` |
| Receipt trust-registry pin | `RECEIPT_TRUST_REGISTRY_SHA256=<TRUST_REGISTRY_SHA256>` |
| Normalized main-ruleset snapshot | `docs/governance/rulesets/main.ruleset.provider.json` |
| Raw main-ruleset provider response | `docs/governance/rulesets/main.ruleset.provider.raw.json` |
| Protected raw-provider SHA-256 | `MAIN_RULESET_EVIDENCE_SHA256=<RAW_PROVIDER_SHA256>` |
| Trusted engineering/source `NOW_US` | `<POSITIVE_UNIX_TIME_MICROSECONDS + TRUSTED-SOURCE EVIDENCE>` |
| Trusted receipt `NOW_US` | `<POSITIVE_UNIX_TIME_MICROSECONDS + TRUSTED-SOURCE EVIDENCE>` |
| Protected tag-ruleset SHA-256 | `B00R_TAG_RULESET_SHA256=<TAG_RULESET_SHA256>` |
| Receipt PR | `<RECEIPT_PR_NUMBER>` |
| Final receipt head SHA | `<RECEIPT_FINAL_HEAD_SHA>` |
| Receipt CI run / job | `<RECEIPT_CI_RUN_ID>` / `<RECEIPT_CI_JOB_ID>` |
| Receipt merge SHA | `<RECEIPT_MERGE_SHA>` |
| Receipt merge tree SHA | `<RECEIPT_MERGE_TREE_SHA>` |
| Receipt merge time, UTC | `<RECEIPT_MERGED_AT_UTC>` |
| Branch ruleset ID | `<MAIN_RULESET_ID>` |
| Anchor/tag ruleset ID | `<ANCHOR_RULESET_ID>` |
| Anchor identity | `B00R_RECEIPT_ANCHOR` (exact validator-required name) |
| Anchor object/tag SHA | `<ANCHOR_OBJECT_SHA>` |
| Receipt file SHA-256 | `<B00R_RECEIPT_SHA256>` |

Stop if the live PR, branch, or head differs from the approved work order. A moved head invalidates
prior CI, review, thread resolution, reproduction, signatures, and receipt assembly.

### 2.1 Trusted-time law

Every strict authority, governance, source, receipt, and terminal gate receives an explicit positive
Unix timestamp in microseconds through `--now-us`. `NOW_US` must come from the approved trusted time
source available to the owner/controlled runner, and the value plus source evidence must be recorded.
Do not derive it from a PR file, receipt field, provider snapshot, or untrusted job output. Use a fresh
trusted value for each later execution; do not reuse a stale ceremony timestamp merely to stay inside
a key-validity window.

Both source and receipt modes are exact-head operations. Supply `--expected-head` equal to the clean
checkout's literal 40-hex `HEAD`; a moved head requires a fresh trusted time, gate run, review, and
evidence record.

---

## 3. Role and separation matrix

One person may hold more than one operational role only where the ratified receipt profile allows it.
The prohibited collisions below are hard failures.

| Role | Required act | Must be distinct from | Evidence returned |
|---|---|---|---|
| Authority owner | Ratifies the three root decisions and trust profile | Implementer acting alone | Signed decisions; authenticated identity |
| Implementer | Produces the repaired engineering head | Sole reviewer, sole resolver, independent countersigner | GitHub PR authorship |
| Repository administrator | Installs rulesets and protected pins; captures provider state | A self-asserted JSON author in place of GitHub | Provider API responses and canary rejection |
| Independent reviewer | Reviews and approves the exact final head | Source/receipt PR author | Provider-authenticated review bound to SHA |
| Evidence custodian | Reproduces the merge from a fresh clone | Uncontrolled author working tree | Runner identity, logs, results, hashes |
| Evidence producer signer | Signs canonical receipt payload | Independent countersigner | Key ID, role, valid signature |
| Independent countersigner | Independently checks and signs the same payload | Evidence producer and receipt PR author where profile requires | Distinct key ID/identity and signature |
| Anchor custodian | Publishes immutable protected anchor | Unprotected local tag author alone | Provider tag object and tag-ruleset proof |

Minimum separation gates:

- the exact-head approval cannot be authored by the PR author;
- the two receipt signatures must resolve to distinct non-revoked keys and distinct identities;
- the protected pins must originate outside the proposed Git tree;
- provider control evidence must come from the provider API, not a hand-written substitute; and
- the clean-runner result must come from a fresh checkout of the merge commit, not the author's dirty
  workspace.

Record the identities without exposing private email, access tokens, key seeds, or private keys:

| Role | Provider/key identity | Operator initials | UTC time |
|---|---|---|---|
| Authority owner | `<IDENTITY>` | `<INITIALS>` | `<UTC>` |
| Repository administrator | `<GITHUB_LOGIN>` | `<INITIALS>` | `<UTC>` |
| Independent reviewer | `<GITHUB_LOGIN>` | `<INITIALS>` | `<UTC>` |
| Evidence custodian | `<RUNNER_IDENTITY>` | `<INITIALS>` | `<UTC>` |
| Evidence producer | `<KEY_ID>` | `<INITIALS>` | `<UTC>` |
| Independent countersigner | `<KEY_ID>` | `<INITIALS>` | `<UTC>` |

---

## 4. Freeze the repaired engineering head before owner ceremony

The owner must not sign artifacts produced by a moving branch. Freeze the engineering-only candidate
first, without yet claiming strict closure or merging it.

1. Refresh the repair PR and record `<ENGINEERING_FROZEN_HEAD_SHA>` and
   `<ENGINEERING_FROZEN_TREE_SHA>`.
2. Confirm its base and ancestry match the approved forward-repair chain.
3. Run all engineering diagnostics that do not require owner signatures, external pins, or provider
   controls. Preserve raw results and exact command identities.
4. Confirm the candidate contains the canonical verifier/schema/tooling the owner will use.
5. Stop pushes while ceremony inputs are created from that exact head.

Run the diagnostic source gate on that literal clean head with trusted time:

```bash
python tools/b00r_gate.py --mode source \
  --expected-head <ENGINEERING_FROZEN_HEAD_SHA> \
  --now-us <TRUSTED_ENGINEERING_NOW_US>
```

Source mode is diagnostic and can never close B00R. Before owner inputs exist, deterministic rows may
pass while authority/governance rows fail closed; that is expected. An omitted or mismatched exact
head, or an omitted/untrusted `NOW_US`, is not an acceptable diagnostic run.

At this point, owner/provider rows may correctly report `BLOCKED`; strict CI has not yet run and the PR
must not merge. If engineering bytes change, discard ceremony outputs derived from the old verifier,
record a new frozen head, and repeat.

---

## 5. Owner signing and trust ceremony against the frozen verifier

Run this ceremony from a clean checkout detached at `<ENGINEERING_FROZEN_HEAD_SHA>`. Use the
canonicalization, schemas, and validators in those frozen bytes. Do not let repair-PR CI manufacture
or self-sign owner material.

### 5.1 Generate signer keys outside GitHub and CI

Use the signing implementation ratified by `DEC-RECEIPT-PROFILE-001`. The intended profile is
Ed25519 with threshold 2, but the frozen decision/schema is authoritative; do not silently substitute
algorithm, canonicalization, threshold, or roles.

For each signer:

1. generate the keypair on a controlled signing workstation or hardware-backed signer;
2. keep the private seed/key non-exportable where possible;
3. export only the public key and non-secret key ID;
4. set explicit validity bounds;
5. record the assigned role and distinct human identity; and
6. test signing and verification on a disposable payload.

Private keys/seeds are forbidden from Git, PRs, GitHub variables, CI, workflow artifacts, logs,
screenshots, chat, and the evidence bundle.

### 5.2 Create canonical public ceremony artifacts

Starting from the merged templates, create the authenticated public trust registry and the three
signed root decisions without changing their pinned subject bytes or scope unless the owner issues a
new explicit decision:

- `receipt_trust_registry.v1.json`;
- `DEC-AUTHORITY-BUNDLE-001.json`;
- `DEC-RECEIPT-PROFILE-001.json`; and
- `DEC-B00-REPAIR-001.json`.

Materialize these public artifacts at the exact canonical paths declared by the frozen validator.
They are public authority inputs, never private-key material. If they must be committed to the repair
PR, that commit creates a **new** candidate head: record the new SHA/tree, rerun deterministic
diagnostics, and treat it as `<REPAIR_FINAL_HEAD_SHA>`. Never pretend the earlier engineering head is
still the final head.

The later receipt-only PR may add only `evidence/B00R/**` and the bare receipt path. It must not add or
alter these canonical authority files. Therefore any required non-evidence authority path must be
materialized in the repair PR before final strict CI.

For every trust key, prove key encoding, role, identity, validity window, revocation state, and signer
separation. Sign only canonical bytes emitted by the merged code; never sign a visual rendering.

### 5.3 Install the four exact external authority pins

The repository copies cannot authenticate themselves. The owner signs the three decisions through the
ratified trust registry, then an administrator installs these four SHA-256 values in an
owner-controlled external store/protected provider environment:

| Protected pin | Canonical pinned object |
|---|---|
| `AUTHORITY_BUNDLE_DECISION_SHA256` | `docs/governance/decisions/DEC-AUTHORITY-BUNDLE-001.json` |
| `RECEIPT_PROFILE_DECISION_SHA256` | `docs/governance/decisions/DEC-RECEIPT-PROFILE-001.json` |
| `B00_REPAIR_DECISION_SHA256` | `docs/governance/decisions/DEC-B00-REPAIR-001.json` |
| `RECEIPT_TRUST_REGISTRY_SHA256` | `docs/governance/trust/receipt_trust_registry.v1.json` |

Capture each variable name, scope, actor, UTC update time, provider object ID, and non-secret digest
without dumping unrelated variables. A value derived from the same proposed Git bytes inside PR CI is
not an external pin.

If `--pins` is used, its JSON root must be an object containing exactly those four names and nonzero,
lowercase 64-hex digests. Unknown or missing names fail this procedure. The file must resolve outside
the Git repository. As an alternative, supply all four through protected environment variables and
omit `--pins`; if a name exists in both places, the values must match. Do not put the pins file in the
receipt evidence tree.

Run the strict authority validator from the resulting final repair head, supplying the external pin
through the approved input mechanism:

```bash
python tools/validate_authority_root.py --strict \
  --pins <EXTERNAL_AUTHORITY_PINS_JSON_WITH_ALL_FOUR_PINS> \
  --now-us <TRUSTED_SOURCE_NOW_US> \
  --expected-head <REPAIR_FINAL_HEAD_SHA> \
  --git-root .
```

Required result: decision signatures, scopes, subject digests, key validity, role separation, all four
external pins, and exact-head Git binding pass. Preserve raw output and exit status.

---

## 6. Active GitHub rulesets, privileged bypass proof, strict CI, and guarded repair merge

### 6.1 Install the `main` and anchor rulesets

Before final strict CI/review/merge, the repository administrator installs an active ruleset
targeting `refs/heads/main` and the dedicated
`refs/heads/b00r-ruleset-canary`, with an empty exclusion list and no wildcard target, with:

- pull request required and direct push denied;
- exact required context `CI / test-and-verify`, bound to the positive provider
  `integration_id` for GitHub Actions so a same-named status from another actor cannot satisfy it;
- required checks bound to current base;
- independent exact-head approval;
- two approvals for receipt PRs if the ratified profile requires it;
- stale approvals dismissed on push and last-push approval where supported;
- all review conversations resolved;
- CODEOWNERS approval on critical paths, after replacing the checked-in
  `@TriadAgentic/origin-governance-reviewers` placeholder with a proven real independent
  user/team that has repository access;
- force-push and branch deletion denied;
- no administrator, team, app, integration, or repository-role bypass; and
- expected-head merge protection.

Install a separate active ruleset targeting exactly `refs/tags/B00R_RECEIPT_ANCHOR` that denies update
and deletion with no bypass. The main ruleset must be active before the repaired PR merge; the tag
ruleset must be active early enough to capture and externally pin its canonical evidence before the
receipt PR's final exact-head validation, and must remain active through anchor publication.

The main ruleset must include the existing dedicated harmless
`refs/heads/b00r-ruleset-canary` branch for the required negative direct-push test. It must not
include any other extra ref or any exclusion. The tag ruleset must target exactly
`refs/tags/B00R_RECEIPT_ANCHOR`; do not widen it with a tag canary, and never mutation-test the real
anchor.

### 6.2 Capture bypass proof outside PR CI

Ruleset existence and bypass behavior require privileges that an untrusted PR workflow must never
possess. A privileged owner, in a separate authenticated session **outside PR CI**, must:

1. query and save complete provider API objects for both rulesets;
   - save the exact unmodified `GET /repos/.../rulesets/{id}` response for `main` as
     `docs/governance/rulesets/main.ruleset.provider.raw.json`;
   - derive the canonical normalized index as
     `docs/governance/rulesets/main.ruleset.provider.json`; its
     `provider.api_response_path` must name the raw path and its `api_response_sha256` must equal the
     raw bytes' SHA-256;
   - require canonical raw `created_at` and `updated_at` timestamps; normalized `effective_at_us`
     must equal the raw `updated_at` instant converted to Unix microseconds, while `captured_at_us`
     must be no later than trusted `NOW_US`;
2. prove target, enforcement state, required context, review controls, and empty bypass list;
3. attempt a noncompliant direct push against the existing
   `refs/heads/b00r-ruleset-canary` and preserve the provider rejection, proving the same rule
   ID/node/conditions applied; materialize the closed canonical record at
   `evidence/B00R/provider_negative_canary.v1.json` with role
   `PROVIDER_NEGATIVE_CANARY`, and its byte-bound transcript with role
   `PROVIDER_NEGATIVE_CANARY_TRANSCRIPT`;
4. capture the tag-ruleset provider object proving exact anchor scope, active enforcement,
   `current_user_can_bypass:"never"`, an empty bypass list, and update/deletion restrictions; later
   materialize it as `evidence/B00R/tag_ruleset.provider.json` in the receipt-only PR and externally
   pin those exact bytes as `B00R_TAG_RULESET_SHA256`; do not probe the real anchor;
5. leave `main` and the real anchor untouched; if the branch canary mutation unexpectedly succeeds,
   mark the ruleset failed and preserve that harmless canary state as evidence; and
6. record authenticated actor, provider request/object IDs, and UTC timestamps.

PR CI may verify the returned proof but may not create, impersonate, or self-attest it.

### 6.3 Externally pin the canonical raw ruleset evidence

The privileged owner authenticates the provider capture and negative canary record outside GitHub
Actions. The validator-enforced main-ruleset pin is the SHA-256 of the exact raw response bytes,
installed as the protected external variable:

`MAIN_RULESET_EVIDENCE_SHA256=<SHA256_OF_main.ruleset.provider.raw.json>`

Do not invent a second protected digest or treat a PR-produced aggregate digest as provider
authority. The external raw-provider pin, provider-authenticated objects, canary rejection, and final
return-bundle checksum are the separate facts to preserve.

The normalized and raw main-ruleset files are mandatory canonical committed source-phase artifacts.
Their commit changes the head: refreeze the new SHA/tree and invalidate prior final-head CI/review.
The raw provider response must remain byte-exact; exclude authorization headers/cookies rather than
redacting the JSON body. Run the strict governance validator against the canonical pair, trusted time,
exact head, and protected external pin:

```bash
test -n "${GITHUB_TOKEN:?short-lived GitHub read token missing}"
test -n "${MAIN_RULESET_EVIDENCE_SHA256:?protected provider pin missing}"
python tools/validate_governance_snapshot.py --strict \
  --snapshot docs/governance/rulesets/main.ruleset.provider.json \
  --provider-raw docs/governance/rulesets/main.ruleset.provider.raw.json \
  --now-us <TRUSTED_SOURCE_NOW_US> \
  --expected-head <REPAIR_FINAL_HEAD_SHA> \
  --git-root .
```

An owner-side invocation may supply `--provider-pin <EXTERNAL_RAW_PROVIDER_SHA256>` instead of the
protected environment. If both exist, they must match. Computing either value inside PR CI from the
same proposed raw file is not an external pin.

If the provider cannot express or prove the required no-bypass controls, return
`BLOCKED_PROVIDER_CONTROL_UNAVAILABLE`; do not replace them with prose or a CI-authored JSON file.

### 6.4 Refreeze, run exact-head strict CI, independently review, and guarded-merge

After every required public ceremony/provider artifact is materialized:

1. record `<REPAIR_FINAL_HEAD_SHA>` and `<REPAIR_FINAL_TREE_SHA>`;
2. prove every ceremony/proof artifact was generated by the separated owner and matches its external
   signature/pin;
3. run strict CI on that exact head, including authority, governance, deterministic engineering,
   packaging, capability, and role gates;
4. reject skipped, neutral, cancelled, stale-head, or workflow-only mandatory results;
5. have an independent reviewer inspect the exact final diff and submit a provider-authenticated
   approval bound to `<REPAIR_FINAL_HEAD_SHA>`;
6. resolve every actionable thread with evidence and re-query all thread/review state;
7. use expected-head guarded merge under the already active no-bypass main ruleset;
8. if the head moves, invalidate CI/review and repeat this subsection; and
9. record provider-returned `<REPAIR_MERGE_SHA>`, tree, actor, UTC time, strategy, PR number, and
   ruleset evaluation, then prove `main` contains it.

The exact-head source orchestrator invocation is:

```bash
test -n "${MAIN_RULESET_EVIDENCE_SHA256:?protected provider pin missing}"
python tools/b00r_gate.py --mode source \
  --expected-head <REPAIR_FINAL_HEAD_SHA> \
  --now-us <TRUSTED_SOURCE_NOW_US> \
  --pins <EXTERNAL_AUTHORITY_PINS_JSON_WITH_ALL_FOUR_PINS> \
  --governance-snapshot docs/governance/rulesets/main.ruleset.provider.json \
  --provider-raw docs/governance/rulesets/main.ruleset.provider.raw.json
```

`source` mode deliberately terminates `BLOCKED` and cannot close B00R, even when every subordinate
row passes. CI must assert that exact diagnostic contract rather than discard the nonzero exit or
misreport it as closure. `receipt` mode is the only terminal closure mode.

This guarded repair merge is the positive control paired with the privileged negative canary. It is
still not B00R closure; clean reproduction, bare receipt, guarded receipt merge, and anchor remain.

---

## 7. Hermetic clean-runner reproduction

Use a new ephemeral runner/VM with no author checkout, editable install, warmed caches, inherited
Python path, or private workspace artifacts. The runner needs GitHub read access only long enough to
clone the private repository.

Record before testing:

```bash
set -eu
umask 077
python --version
python -m pip --version
git --version
uname -a
```

Clone and detach at the provider-returned repaired merge, not the PR branch:

```bash
git clone --no-tags <REPOSITORY_CLONE_URL> triad-origin-clean
cd triad-origin-clean
git checkout --detach <REPAIR_MERGE_SHA>
test "$(git rev-parse HEAD)" = "<REPAIR_MERGE_SHA>"
test -z "$(git status --porcelain)"
git rev-parse HEAD
git rev-parse 'HEAD^{tree}'
```

Use the repository's committed pinned dependency snapshot and the exact install/build commands from
the final workflow. Do not replace them with a floating `pip install` because it happens to pass.
At minimum, capture the lock/constraint digest, Python implementation/version, platform, build-backend
version, and every produced distribution digest.

Run the complete controlled gate set from the merged tree, including both deterministic hash seeds:

```bash
<PINNED_INSTALL_COMMAND_FROM_FINAL_WORKFLOW>
PYTHONHASHSEED=0 python -m pytest -p no:cacheprovider
PYTHONHASHSEED=1 python -m pytest -p no:cacheprovider
test -n "${MAIN_RULESET_EVIDENCE_SHA256:?protected provider pin missing}"
python tools/b00r_gate.py --mode source \
  --expected-head <REPAIR_MERGE_SHA> \
  --now-us <TRUSTED_REPRODUCTION_NOW_US> \
  --pins <EXTERNAL_AUTHORITY_PINS_JSON_WITH_ALL_FOUR_PINS> \
  --governance-snapshot docs/governance/rulesets/main.ruleset.provider.json \
  --provider-raw docs/governance/rulesets/main.ruleset.provider.raw.json
<MANIFEST_AND_CONTRACT_GATE_COMMANDS_FROM_FINAL_WORKFLOW>
<REPRODUCIBLE_SDIST_WHEEL_GATE_FROM_FINAL_WORKFLOW>
<INSTALLED_DISTRIBUTION_ISOLATION_GATE_FROM_FINAL_WORKFLOW>
<DARK_NEGATIVE_CAPABILITY_GATE_FROM_FINAL_WORKFLOW>
```

Acceptance requires:

- clean checkout before and after the run, except declared evidence output outside the source tree;
- identical collected test IDs across the two seeds;
- zero failures, errors, skips, xfails, neutralized mandatory jobs, or collection drift unless the
  ratified spec explicitly permits and counts them;
- byte-reproducible artifacts where claimed;
- installed-distribution bytes traceable to reviewed source bytes;
- all contract/manifest families present and valid;
- DARK scan clean; and
- `activation_result=DENIED_SAFE_HOLD` with OFF/OFF/OFF/LIVE levers.

As in final source CI, the source orchestrator must report all expected subordinate rows accurately
and terminal `BLOCKED`; the controlled reproduction harness asserts that diagnostic contract rather
than treating source mode as closure.

The evidence custodian exports raw logs and machine-readable results. A pasted “tests passed” line is
not reproduction evidence.

---

## 8. Closed evidence manifest

After clean reproduction succeeds, create a new receipt worktree/branch directly from
`<REPAIR_MERGE_SHA>`. Materialize only the ceremony/provider preimages and clean-runner outputs under
`evidence/B00R/**`, then build the manifest using the merged project tools:

```bash
python tools/build_evidence_manifest.py \
  --build evidence/B00R/spec.json \
  --root . \
  --closed-root evidence/B00R \
  --out evidence/B00R/evidence_manifest.json

python tools/build_evidence_manifest.py \
  --verify evidence/B00R/evidence_manifest.json \
  --root . \
  --closed-root evidence/B00R \
  --require-tracked
```

Every receipt claim must have a committed preimage or an explicitly typed provider-external preimage.
The manifest must reject missing, duplicate, mutable, path-escaping, hash-mismatched, or undeclared
members. Include raw command logs/results, provider evidence, review inventories, repaired-merge
ancestry, toolchain snapshot, and distribution hashes. Future receipt-PR/merge facts are not inputs
to this pre-merge manifest; the anchor binds them later. Do not include credentials or private keys.

The strict receipt binding requires exactly one manifest entry for each role below, and the entry's
SHA-256 must equal the corresponding receipt payload field:

| Required manifest role | Receipt payload field |
|---|---|
| `WORKFLOW` | `workflow_sha256` |
| `CONTRACT_MANIFEST` | `contract_manifest_sha256` |
| `TEST_MANIFEST` | `test_manifest_sha256` |
| `CONFIG_BUNDLE` | `config_bundle_sha256` |
| `ROLLBACK_PROOF` | `rollback_proof_sha256` |

The manifest must additionally contain exactly one canonical
`PROVIDER_NEGATIVE_CANARY` entry at
`evidence/B00R/provider_negative_canary.v1.json` and exactly one
`PROVIDER_NEGATIVE_CANARY_TRANSCRIPT` entry whose path and digest the canary record binds. These
roles are covered by the closed manifest, receipt evidence arrays, and threshold signatures; they
do not add self-referential receipt fields.

Every path named by `evidence_ids` must be under `evidence/B00R/`. The manifest file itself is
excluded from `evidence_ids` to avoid self-reference; every other tracked file under that namespace
must appear exactly once. A missing, duplicate, extra, or out-of-namespace member fails closure.

---

## 9. Assemble and threshold-sign the canonical receipt

The one canonical receipt path is:

`evidence/receipts/B00R.receipt.v3.json`

The receipt must use the schema and canonical signing function shipped in the exact repaired merge.
Its closed payload binds:

- milestone `B00R`, variant `ROOT`, and result `PASS_REPOSITORY_SAFE_HOLD`;
- `repair_generation=1`, the audited start, repair-decision digest, and invalidation-manifest digest;
- source PR, reviewed final source head, repair merge commit/tree/time, and repository/scope identity;
- the closed evidence-manifest digest plus the five required role digests in Section 8;
- `evidence_ids` and `evidence_sha256s` for clean-runner, provider-canary, strict CI, independent
  review, authority, and other declared preimages under `evidence/B00R/`;
- OFF/OFF/OFF/LIVE levers and `DENIED_SAFE_HOLD` activation result; and
- valid internal chronology: engineering-head freeze precedes owner ceremony/provider proof; any
  resulting artifact commit precedes final strict CI/review; guarded repair merge precedes clean
  observation and receipt emission/signing.

The strict validator separately authenticates the three decisions and trust registry with the four
external authority pins and verifies the canonical normalized/raw main-ruleset files against
`MAIN_RULESET_EVIDENCE_SHA256`. Do not add undeclared authority or aggregate-digest fields to the
closed receipt schema.

Set `payload.source_merge_time_us` from the Git commit itself, exactly:

```bash
SOURCE_MERGE_TIME_US="$(( $(git show -s --format=%ct <REPAIR_MERGE_SHA>) * 1000000 ))"
```

Do not use GitHub `mergedAt`, a fractional timestamp, local wall-clock time, or a copied guide value.
Set `payload.final_source_head` to the reviewed final repair head. It must be the same commit as, or an
ancestor of, `<REPAIR_MERGE_SHA>`, and its tree must equal the repair merge tree. The receipt checkout
must contain enough Git history for the validator to resolve and prove both `<AUDITED_START_SHA>` and
`<REPAIR_MERGE_SHA>`; a shallow checkout that omits either object is unacceptable.

The bare receipt and evidence manifest must not list or hash the receipt itself. It also cannot contain
its own future PR-head or merge SHA without creating a hash cycle. Receipt PR final-head, review, CI,
merge, and provider chronology are proved after the receipt bytes exist and are bound by the protected
closure anchor in Section 11.

Generate signing bytes using the repository function, with `signatures` omitted exactly as the schema
requires. Each signer independently verifies the receipt preimages and then signs the **same** byte
sequence. Append `{key_id, signature_hex}` without reserializing any other field.

After the evidence and receipt are committed on the receipt branch, validate the literal clean final
receipt head before review/merge. The external authority pins JSON must contain all four required
authority digests; it is not a substitute trust registry. The protected runner injects the raw
provider pin:

```bash
test -n "${GITHUB_TOKEN:?short-lived GitHub read token missing}"
test -n "${MAIN_RULESET_EVIDENCE_SHA256:?protected provider pin missing}"
python tools/validate_b_receipt.py --strict --milestone B00R \
  --pins <EXTERNAL_AUTHORITY_PINS_JSON_WITH_ALL_FOUR_PINS> \
  --now-us <TRUSTED_RECEIPT_NOW_US> \
  --manifest evidence/B00R/evidence_manifest.json \
  --git-root . \
  --expected-head <RECEIPT_FINAL_HEAD_SHA> \
  --governance-snapshot docs/governance/rulesets/main.ruleset.provider.json \
  --provider-raw docs/governance/rulesets/main.ruleset.provider.raw.json \
  evidence/receipts/B00R.receipt.v3.json
```

An owner-side run may add `--provider-pin <EXTERNAL_RAW_PROVIDER_SHA256>` instead of relying on the
protected environment; if both are set they must match. There is deliberately no `--trust` option:
strict validation reconstructs trust from the externally pinned, Git-bound authority root.

This is a **bare JSON receipt**. No DSSE file, wrapper, alternate envelope, alias, or second truth
object is permitted. If the final merged role gate requires any different receipt path or envelope,
stop with `BLOCKED_RECEIPT_LAYOUT_CONFLICT` and repair the source law in a new reviewed PR.

---

## 10. Canonical receipt-only PR layout

Create the receipt branch directly from `<REPAIR_MERGE_SHA>`. The allowed diff is closed:

```text
evidence/
├── B00R/
│   ├── spec.json
│   ├── evidence_manifest.json
│   ├── tag_ruleset.provider.json
│   ├── logs/
│   ├── results/
│   └── provider/
└── receipts/
    └── B00R.receipt.v3.json
```

No source, tests, workflows, schemas, contracts, decisions, trust files, validator code, historical
receipts, or unrelated documentation may change in this PR. Generated build products are allowed
only when explicitly required and declared by the evidence manifest.

Run the receipt-role/diff gate first. Then require:

- receipt-mode CI on `<RECEIPT_FINAL_HEAD_SHA>`;
- strict receipt and manifest verification;
- exact-head independent approval;
- every review thread resolved;
- no stale approvals after the last push; and
- expected-head guarded merge under the effective main ruleset.

Record provider facts in Section 2. A receipt signed before its final content exists, or a receipt PR
based on anything other than the exact repaired merge, fails.

---

## 11. Protected closure anchor

After the receipt merge, publish the exact annotated tag `B00R_RECEIPT_ANCHOR` under the already
active exact-ref no-update/no-delete tag ruleset. It must be an annotated Git tag object, not a
lightweight tag, and it must point directly to `<RECEIPT_MERGE_SHA>`.

The annotated message profile is closed—no extra fields:

```text
TRIAD-B00R-RECEIPT-ANCHOR-V1
receipt_path=evidence/receipts/B00R.receipt.v3.json
receipt_sha256=<B00R_RECEIPT_SHA256>
```

Create it with the ordinary annotated-tag operation (`git tag -a`), not a command that claims a
cryptographic tag signature. The implemented validator verifies the annotated object type, exact tag
name, target receipt-merge commit, tagger presence, closed message profile, canonical receipt path and
digest, plus the externally pinned protected tag-ruleset evidence. It does **not** verify a GPG, SSH,
or other cryptographic signature on the tag. Do not describe the anchor as “signed” or claim a
verified tag signature.

The canonical tag-ruleset evidence, `evidence/B00R/tag_ruleset.provider.json`, must already be
committed in the receipt merge and externally pinned by `B00R_TAG_RULESET_SHA256`; the anchor cannot
retroactively add it. After publication, query the provider and save the tag reference, annotated tag
object, target commit, and tag-ruleset evaluation only in the external return bundle. Do not modify
the merged receipt/evidence bytes and do not probe update/deletion against the real anchor.

Final validation from a clean checkout of the receipt merge:

```bash
test -n "${MAIN_RULESET_EVIDENCE_SHA256:?protected provider pin missing}"
test -n "${B00R_TAG_RULESET_SHA256:?protected tag-ruleset pin missing}"
python tools/b00r_gate.py --mode receipt \
  --expected-head <RECEIPT_MERGE_SHA> \
  --base-sha <REPAIR_MERGE_SHA> \
  --now-us <TRUSTED_TERMINAL_NOW_US> \
  --pins <EXTERNAL_AUTHORITY_PINS_JSON_WITH_ALL_FOUR_PINS> \
  --receipt evidence/receipts/B00R.receipt.v3.json \
  --manifest evidence/B00R/evidence_manifest.json \
  --governance-snapshot docs/governance/rulesets/main.ruleset.provider.json \
  --provider-raw docs/governance/rulesets/main.ruleset.provider.raw.json \
  --anchor-ruleset evidence/B00R/tag_ruleset.provider.json
```

Only an all-green strict result permits `PASS_REPOSITORY_SAFE_HOLD`.

---

## 12. Evidence return bundle

Return one immutable, checksummed bundle with this minimum inventory:

```text
B00R_EXTERNAL_CLOSURE_<UTC>/
├── 00_EXECUTION_RECORD.md
├── 01_ROLE_SEPARATION.json
├── 02_AUTHORITY_VALIDATION.log
├── 03_PROTECTED_PIN_METADATA.json
├── 04_TRUSTED_TIME_EVIDENCE.json
├── provider/
│   ├── main.ruleset.provider.raw.json
│   ├── main.ruleset.provider.json
│   ├── tag_ruleset.provider.json
│   ├── canary_rejection.json
│   ├── repair_pr.json
│   ├── repair_checks.json
│   ├── repair_reviews_and_threads.json
│   ├── repair_merge.json
│   ├── receipt_pr.json
│   ├── receipt_checks.json
│   ├── receipt_reviews_and_threads.json
│   ├── receipt_merge.json
│   └── anchor_objects.json
├── clean_runner/
│   ├── runner_identity.json
│   ├── toolchain.txt
│   ├── checkout_identity.txt
│   ├── seed_0.log
│   ├── seed_1.log
│   ├── collected_ids.txt
│   ├── repair_gate.log
│   ├── artifact_gates.log
│   └── artifact_sha256s.txt
├── committed_preimages/
│   ├── evidence_manifest.json
│   └── B00R.receipt.v3.json
├── 98_REDACTION_REPORT.md
└── SHA256SUMS
```

Evidence requirements:

- preserve the exact raw bytes of
  `docs/governance/rulesets/main.ruleset.provider.raw.json`, the derived normalized
  `docs/governance/rulesets/main.ruleset.provider.json`, and
  `evidence/B00R/tag_ruleset.provider.json`; record the four authority pins,
  `MAIN_RULESET_EVIDENCE_SHA256`, `B00R_TAG_RULESET_SHA256`, their scopes, actors, update times, and
  provider object IDs in `03_PROTECTED_PIN_METADATA.json`;
- record each trusted `NOW_US`, its approved source, collection actor, and evidence identifier in
  `04_TRUSTED_TIME_EVIDENCE.json`;
- preserve raw provider IDs, SHAs, UTC timestamps, conclusions, and exit codes;
- redact bearer tokens, cookies, private keys, seeds, credential URLs, and unrelated secret values;
- make redactions explicit in `98_REDACTION_REPORT.md` without destroying the claim being proved;
- generate `SHA256SUMS` after the bundle is final; and
- verify every checksum from a second clean location before return.

---

## 13. Safe-hold outcome table

| Observed state | Required result | Next action |
|---|---|---|
| All authority, provider, review, reproduction, receipt, and anchor gates pass | `PASS_REPOSITORY_SAFE_HOLD` | Permit B01C to branch only from the validated B00R receipt merge/anchor |
| Deterministic repair gates pass but any owner/provider artifact is absent | `BLOCKED_SAFE_HOLD` | Obtain the missing external act; do not alter runtime |
| Head, ancestry, tree, receipt, signature, or digest mismatch | `FAIL_SAFE_HOLD` | Preserve evidence; correct forward on a new immutable head |
| Ruleset is inactive, bypassable, wrong-target, or installed after merge | `FAIL_GOVERNANCE_SAFE_HOLD` | Repair controls and repeat the controlled merge |
| Review is stale, self-authored, or not bound to exact head | `BLOCKED_REVIEW_SAFE_HOLD` | Re-review the current head independently |
| Clean runner cannot reproduce exact merged bytes/results | `FAIL_REPRODUCTION_SAFE_HOLD` | Diagnose repair/build drift; issue a new repair PR |
| Receipt PR contains source or unrelated files | `FAIL_ROLE_SEPARATION_SAFE_HOLD` | Close/rebuild receipt branch from repaired merge with closed layout |
| Anchor is mutable, missing, or points elsewhere | `BLOCKED_ANCHOR_SAFE_HOLD` | Install protection and publish a correct forward anchor |
| Any effective activation differs from OFF/OFF/OFF/LIVE | `FAIL_POSTURE_VIOLATION` | Stop immediately; restore safe hold and investigate separately |

No failure in this table authorizes access to the trading box. The repair surface remains GitHub,
signing workstations, and the clean runner.

---

## 14. Final operator sign-off

- [ ] Live execution record is complete and provider-derived.
- [ ] Role separation is proven with authenticated identities.
- [ ] Private signing material never entered GitHub, CI, chat, or evidence.
- [ ] Trust registry and three decisions validate against protected external pins.
- [ ] `main` and anchor rulesets are active, correct-target, and no-bypass.
- [ ] Engineering head was frozen before ceremony; any ceremony/proof commit produced a new recorded final head.
- [ ] Owner ceremony and active no-bypass rulesets preceded final strict CI/review/guarded repair merge.
- [ ] Privileged negative canaries were captured outside CI; guarded repair and receipt merges are positive ruleset proofs.
- [ ] Repair CI, independent review, and all resolved threads bind the exact final repair head.
- [ ] Fresh clean runner reproduced the repaired merge under both hash seeds and all artifact gates.
- [ ] Closed evidence manifest verifies every declared preimage.
- [ ] Exactly one canonical threshold-signed B00R receipt validates.
- [ ] Receipt-only PR contains no source/unrelated changes and was guarded-merged.
- [ ] Protected closure anchor binds the receipt merge and receipt digest.
- [ ] Final strict receipt-mode gate returns `PASS_REPOSITORY_SAFE_HOLD`.
- [ ] Evidence bundle is redacted, checksummed, independently verified, and returned.
- [ ] No trading/MCP box credentials or runtime actions were requested or used.

**Operator:** `<NAME / IDENTITY>`  
**Independent reviewer:** `<NAME / IDENTITY>`  
**Completed at (UTC):** `<UTC>`  
**Final result:** `<PASS_REPOSITORY_SAFE_HOLD | BLOCKED_* | FAIL_*>`
