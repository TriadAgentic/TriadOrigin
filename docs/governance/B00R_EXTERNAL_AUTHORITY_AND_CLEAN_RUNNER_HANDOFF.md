# B00R generation-2 external-authority and clean-runner handoff

**Milestone:** B00R generation 2 (`B00R_G2`)

**Audited start:** `76b5e4857f80f22f99385810037c5c66289ebd5f`

**Only permitted terminal result:** `PASS_REPOSITORY_SAFE_HOLD`

**Activation result:** `DENIED_SAFE_HOLD`
**Lever invariant:** `venue_environment=OFF / venue_activation=OFF / paper_activation=OFF / shadow_activation=LIVE`

This is an additive, forward-only correction. It does not rewrite the first B00R attempt, move its
tag, manufacture a historical review, or make post-merge provider evidence predate a merge.

The ceremony is repository-only. Do not log into, restart, configure, or deploy the trading estate,
MCP server, database, venue adapter, or model host. Those systems cannot supply missing GitHub
chronology or independent review.

## 1. Historical generation 1 is immutable false-green evidence

The authoritative historical identities are recorded in
`B00R_GENERATION_LEDGER.v1.json`:

| Object | Immutable identity |
|---|---|
| Source PR | PR #31; head `6033e9e0812d3eb980cfbcb3928006226414c7e4`; merge `5b2a0edc6db99934fe6fbe6bb0fa582bf689a7cc`; merged `2026-08-10T12:37:25Z` |
| Receipt PR | PR #32; head `462152e29d249ab3596f6025e1f4d568efab335c`; merge `76b5e4857f80f22f99385810037c5c66289ebd5f`; merged `2026-08-10T13:05:54Z` |
| Receipt | `evidence/receipts/B00R.receipt.v3.json`; SHA-256 `f1328ceb29a8730be93f4fd47d295ac96ef514a747385ab500256d6fa52a7cca` |
| Anchor | annotated tag `B00R_RECEIPT_ANCHOR`; tag object `0b2f0579a81e03988cca119ae7e4a0fbf888ad09`; target `76b5e4857f80f22f99385810037c5c66289ebd5f` |
| Disposition | `MERGED_UNVERIFIED`; never a predecessor acceptance root |

Generation 1 remains non-closing for five independent reasons:

1. PR #31 has no submitted review.
2. PR #32 has no submitted review.
3. GitHub main ruleset `20641102` was created at `2026-08-10T13:47:11.736Z`, after both merges.
4. The receipt sealed a hand-authored provider stub whose ruleset id is `"DECLARATIVE"`.
5. The receipt declares `source_pr=27` while its `source_merge_sha` is PR #31's merge.

Retro-review cannot change pre-merge chronology. Never edit either generation-1 receipt/evidence
namespace, never repoint `B00R_RECEIPT_ANCHOR`, and never relabel generation 1 as passed.

### PR #33 is post-hoc evidence only

PR #33 is open at head `0fc4edef83aa60ffe06d1d8356d798e492a6d98e` and has no submitted
review. It contains a live capture and rejected administrative canaries for ruleset `20641102`.
That proves a provider control existed after generation 1; it cannot repair either earlier merge.

Its captured rule also is not the generation-2 canonical rule as written: it targets only
`refs/heads/main` and permits `merge`, `squash`, and `rebase`. Generation 2 requires the exact main
plus dedicated-canary target set and `allowed_merge_methods=["merge"]`. Treat PR #33 as a historical
input to the correction, not as the corrective source or receipt PR. Issue #5 is open/reopened and
must remain open until the generation-2 terminal gate passes; issue state cannot override these
facts.

## 2. Generation-2 canonical identities

| Role | Canonical identity |
|---|---|
| Policy | `docs/control/b00r_policy.v2.json` |
| Generation ledger | `docs/governance/B00R_GENERATION_LEDGER.v1.json` |
| Audited start | `76b5e4857f80f22f99385810037c5c66289ebd5f` |
| Generation-2 authority decision | `docs/governance/decisions/DEC-AUTHORITY-BUNDLE-002.json` |
| Generation-2 receipt profile | `docs/governance/decisions/DEC-RECEIPT-PROFILE-002.json` |
| Generation-2 repair decision | `docs/governance/decisions/DEC-B00-REPAIR-002.json` |
| G2 trust registry | `docs/governance/trust/receipt_trust_registry.g2.v1.json` |
| Main ruleset index | `docs/governance/rulesets/main.ruleset.provider.json` |
| Raw main ruleset response | `docs/governance/rulesets/main.ruleset.provider.raw.json` |
| Evidence root | `evidence/B00R_G2/` |
| Receipt | `evidence/receipts/B00R.g2.receipt.v3.json` |
| Tag-ruleset capture | `evidence/B00R_G2/tag_ruleset.provider.json` |
| Physical anchor | `B00R_RECEIPT_ANCHOR_G2` |

The required protected external pins are:

```text
AUTHORITY_BUNDLE_G2_DECISION_SHA256
RECEIPT_PROFILE_G2_DECISION_SHA256
B00R_G2_REPAIR_DECISION_SHA256
RECEIPT_G2_TRUST_REGISTRY_SHA256
MAIN_RULESET_EVIDENCE_SHA256
B00R_G2_TAG_RULESET_SHA256
```

`PINS_JSON` is an out-of-repository file containing **exactly the first four authority pins**.
`validate_authority_root.py` rejects `MAIN_RULESET_EVIDENCE_SHA256` and
`B00R_G2_TAG_RULESET_SHA256` as unknown authority subjects. Supply those two provider-object pins
only through their dedicated CLI flags or protected environment variables.

`GITHUB_TOKEN` is a short-lived runtime credential for fixed-host provider revalidation. It is not
an evidence pin. Never put it in argv, a file, a PR, a transcript, or a log.

## 3. Separation of duties

| Role | Required act | Forbidden substitution |
|---|---|---|
| Implementation author | Produces the corrective source head | Approving their own PR |
| Repository administrator | Installs provider rulesets and performs the harmless canary | Hand-writing a provider response |
| Independent CODEOWNER | Reviews and approves the exact bootstrap, source, and receipt heads, independently of each PR author | Review after merge, review of an earlier head, withdrawn approval, or comment-only review |
| Evidence producer | Reproduces and signs the generation-2 receipt | Acting as the independent countersigner |
| Independent countersigner | Independently checks and signs the same receipt preimage | Sharing the producer identity/key |
| Anchor custodian | Publishes the protected annotated G2 tag | Moving or testing the generation-1 tag |

The generation-2 policy currently requires the sole critical-path CODEOWNER to be `@djordi10`.
The repository must independently prove that this user has live repository access and is not the
source PR author. CODEOWNERS text alone is not review evidence.

### Base-branch CODEOWNERS bootstrap is mandatory

GitHub evaluates CODEOWNERS from a pull request's base. The corrective PR cannot protect its own
merge merely by changing `.github/CODEOWNERS` in its head. Before the final corrective source PR:

1. make the existing base owner/team valid so GitHub can enforce the bootstrap, and obtain
   `@djordi10`'s independent exact-head approval on a CODEOWNERS-only PR that puts these exact bytes
   on `main`;
2. refresh the corrective branch from that bootstrap merge; and
3. keep the bootstrap and correction separate—neither is a receipt or closure claim.

The generation-2 receipt validator requires an ordinary two-parent source merge, requires its
second parent to be the exact reviewed source head, and byte-compares CODEOWNERS at the first
parent with the reviewed file. It also requires the receipt manifest to carry the bootstrap PR and
approved-review provider records, proves the bootstrap changed only `.github/CODEOWNERS`, and
matches the provider merge time to the local Git merge time. A direct commit, same-PR change,
synthetic bootstrap, self-review, stale review, or post-merge review fails.

After the bootstrap merge, reserve `main` exclusively for this ceremony. The source merge's first
parent must equal that bootstrap merge—not merely contain equivalent bytes—and the receipt merge's
first parent must equal the source merge. Any intervening `main` merge breaks the chain; stop and
restart the corrective sequence from a fresh reviewed bootstrap rather than layering a repair PR.

## 4. Owner authority ceremony

Start with the checked-in generation-2 templates. Publish authenticated decisions only at their
canonical non-template paths:

- `DEC-AUTHORITY-BUNDLE-002.json`;
- `DEC-RECEIPT-PROFILE-002.json`; and
- `DEC-B00-REPAIR-002.json`.

All three `002` decisions supersede their `001` counterparts only for generation 2. They do not
mutate the generation-1 objects. Each decision must bind its declared subjects, be signed by a valid
`AUTHORITY_OWNER` Ed25519 identity in the distinct externally pinned G2 trust registry, and carry a real
effective time. Typing `authenticated:true` without a valid signature is a failure.

The existing generation-1 registry scopes its owner key only to `-001` decisions and is therefore
incapable of authenticating generation 2. Materialize
`receipt_trust_registry.g2.v1.template.json` as `receipt_trust_registry.g2.v1.json`, with owner scope
covering `DEC-AUTHORITY-BUNDLE-002,DEC-RECEIPT-PROFILE-002,DEC-B00-REPAIR-002`, then externally pin
those exact bytes as `RECEIPT_G2_TRUST_REGISTRY_SHA256`.

Validate the exact source head with generation 2 selected:

```bash
python tools/validate_authority_root.py --strict \
  --repair-generation 2 \
  --pins "$PINS_JSON" \
  --now-us "$NOW_US" \
  --expected-head "$SOURCE_HEAD" \
  --git-root .
```

Any missing owner act is `BLOCKED` or `UNAVAILABLE`, never an inferred pass.

## 5. Install the generation-2 main ruleset before the source merge

Before activating this ruleset, the repository administrator must create the dedicated canary ref
at the fixed harmless pre-attempt commit:

```bash
CANARY_BEFORE_SHA=ba495ba90e0e4eff50ed75d2443f9cc12ce6ddcd
git push origin "$CANARY_BEFORE_SHA:refs/heads/b00r-ruleset-canary"
```

Verify the provider ref resolves to exactly that SHA, then install the ruleset. This ordering is
mandatory: with `do_not_enforce_on_create=false`, pull-request enforcement, and no bypass actors,
trying to create the canary ref after activation is itself blocked and leaves no stable before-state
for the negative update proof.

The live GitHub provider object must satisfy all of these conditions simultaneously:

- positive integer id, provider-shaped source/link/timestamps, `enforcement=active`;
- repository source exactly `TriadAgentic/TriadOrigin`;
- include set exactly `{refs/heads/main, refs/heads/b00r-ruleset-canary}`;
- exclusion list exactly empty;
- `bypass_actors=[]` and `current_user_can_bypass="never"`;
- pull request required with at least one approval;
- stale approvals dismissed, CODEOWNER review required, last-push approval required, and every
  conversation resolved;
- `allowed_merge_methods=["merge"]` — squash and rebase are not permitted for the corrective train;
- exactly one strict required check, provider `CheckRun.name=test-and-verify`, bound to GitHub Actions integration id
  `15368`;
- `do_not_enforce_on_create=false`, so creating the dedicated canary ref cannot evade the required
  check rule;
- deletion and non-fast-forward updates blocked.

Capture the exact raw bytes returned by the fixed provider endpoint into
`docs/governance/rulesets/main.ruleset.provider.raw.json`. Derive the normalized index at
`docs/governance/rulesets/main.ruleset.provider.json`; it is an index, not self-authenticating
evidence. Externally pin the raw bytes as `MAIN_RULESET_EVIDENCE_SHA256`.

The ruleset `updated_at` instant, raw capture, normalized capture, and external pin must all predate
the generation-2 source merge. Any later ruleset update invalidates the capture and requires a new
capture, new pin, fresh exact-head CI, and fresh review.

## 6. Run the dedicated negative canary before the source merge

Use only the already-created `refs/heads/b00r-ruleset-canary`. Construct an empty fast-forward
descendant of its fixed before commit (same tree, one new commit), attempt that direct update, and
require GitHub to reject it under the same active ruleset. Keep the canary branch at its pre-attempt
provider SHA; never probe `main` or either receipt anchor. A branch-creation rejection is not a
substitute because it does not exercise the required update control against a stable ref.

Preserve the exact canonical evidence for the later receipt PR:

```text
evidence/B00R_G2/provider_negative_canary.v1.json
evidence/B00R_G2/provider_negative_canary.transcript.txt
evidence/B00R_G2/provider_negative_canary.rule_suite.raw.json
```

The canonical record must bind the provider rule-suite id, actor, before/attempted-after commit
identities, nonzero exit code, attempted time, ruleset id, transcript digest, and rule-suite digest.
The provider rule suite must show an active `pull_request` rule failure for the same ruleset and
canary ref. The ruleset update, rule-suite push, and canary attempt must all predate the source merge.

If the push succeeds, stop with `BLOCKED_PROVIDER_CONTROL_UNAVAILABLE`. Do not delete the evidence
of the failure and do not substitute a prose transcript.

## 7. Freeze, test, review, and merge the corrective source

The generation-2 source branch starts from audited start
`76b5e4857f80f22f99385810037c5c66289ebd5f`. It may contain the policy, generation ledger,
corrective validators, ruleset source-phase capture, and governance documentation. It must not
contain `evidence/B00R_G2/**` or `evidence/receipts/B00R.g2.receipt.v3.json`.

After every source-phase artifact is committed:

1. freeze the literal 40-hex final source head and tree;
2. require a clean worktree and no Git replace objects;
3. run the full repository gate suite under `PYTHONHASHSEED=0` and `1`;
4. require GitHub `test-and-verify` green on that exact head (the UI may display
   `CI / test-and-verify`);
5. obtain a submitted `APPROVED` review from the independent CODEOWNER on that exact head;
6. resolve every actionable review thread;
7. merge with GitHub's ordinary **merge** method under the active ruleset; and
8. verify the source merge's first parent is the recorded bootstrap merge, its second parent is the
   reviewed source head, its tree equals that head's tree, and provider `main` contains it.

If the source head moves after approval, the approval and CI are stale. Repeat steps 1–6.

Source-mode orchestration is diagnostic and deliberately returns overall `BLOCKED`; it cannot close
B00R:

```bash
python tools/b00r_gate.py --mode source \
  --expected-head "$SOURCE_HEAD" \
  --now-us "$NOW_US" \
  --pins "$PINS_JSON" \
  --provider-pin "$MAIN_RULESET_EVIDENCE_SHA256"
```

The subordinate rows must pass. The expected overall source result remains `BLOCKED` because the
receipt merge and physical G2 anchor do not yet exist.

### Exact review evidence required in the receipt

The later receipt manifest must contain exactly one of each canonical provider record:

```text
evidence/B00R_G2/source_pr.provider.raw.json
evidence/B00R_G2/source_pr.approved_review.provider.raw.json
```

The source PR record must bind the actual generation-2 PR number, `main` base, repository identity,
final source head, merge commit, author, merged state, and provider merge time. The approved-review
record must bind:

- one positive provider review id;
- state exactly `APPROVED`;
- `commit_id` exactly equal to the final source head;
- reviewer different from the PR author;
- reviewer exactly equal to the sole critical-path CODEOWNER;
- `submitted_at` strictly before provider `merged_at`; and
- a fresh live provider match plus live repository permission at terminal validation.

A requested reviewer, issue comment, approval on another PR, retro-review, or approval after merge is
not review evidence.

## 8. Bounded clean-runner reproduction at the exact source merge

Run the committed producer on a clean Linux host with a non-symlink system CPython 3.11 binary.
Give it three absent, canonical, pairwise-disjoint paths under a fresh parent; it refuses an
existing or symlinked clone, virtual environment, or output root:

```bash
SOURCE_MERGE=<EXACT_TWO_PARENT_SOURCE_MERGE_ON_LIVE_ORIGIN_MAIN>
CAPTURE_PARENT="$(mktemp -d)"
BOOTSTRAP_PYTHON="$(realpath "$(command -v python3.11)")"
CONTROLLER_PYTHON="$BOOTSTRAP_PYTHON"
test -f "$BOOTSTRAP_PYTHON" && test ! -L "$BOOTSTRAP_PYTHON"

"$CONTROLLER_PYTHON" -I tools/b00r_clean_runner_capture.py \
  --source-merge "$SOURCE_MERGE" \
  --clone-root "$CAPTURE_PARENT/source" \
  --venv-root "$CAPTURE_PARENT/venv" \
  --output-root "$CAPTURE_PARENT/output" \
  --python "$BOOTSTRAP_PYTHON"
```

The producer itself performs the canonical public HTTPS `--no-local --no-tags` clone, proves the
detached source is the current two-parent `origin/main`, loads its local verifier by compiling
retained `.py` bytes without consulting bytecode caches, and refuses to proceed unless its own
producer, verifier, and pytest-inventory bytes exactly equal their Git blobs at that merge. It
creates the new isolated venv with system/user package injection and pip
configuration disabled, installs the exact constraints plus a non-editable wheel built from the
source Git archive, and
preserves raw stdout, stderr, exit status, timestamps, runner/Git facts, installed import-surface
file hashes, and test ids. It re-fetches `origin/main` before and after the real mainline rollback
proof; any nonzero command or identity movement fails the capture. Controller and required-command
Git calls suppress
ambient global/system configuration, replacement objects, hooks, commit-graph acceleration, and
multi-pack-index acceleration; each source boundary also performs a strict full object check.

This is bounded clone/venv/output and declared-environment isolation, not complete host or
toolchain attestation. The external trusted-computing base still includes the clean Linux host,
kernel and filesystem, the base CPython 3.11 standard library/shared libraries, Git/TLS, and the
package index/artifact supply path. The locally invoked launcher/controller up to the point where
those executing profile bytes are bound to the canonical clone is also in that external TCB.
Hostile or background processes, and within-command mutate/use/restore behavior, are outside this
bounded controller: it does not claim an immutable mount or process-containment boundary.
`constraints/ci.txt` pins its listed dependency versions, while bootstrapped `pip` remains observed
rather than pinned; neither supplies platform wheel hashes or index provenance. The capture
therefore records and signs the exact import-surface files it observed, closes that surface against
unowned files, and revalidates those bytes as byte-identical before and after each required command.
It does not claim that independently rebuilding those dependency artifacts from the version pins
alone must reproduce their hashes.

At minimum reproduce:

```bash
PYTHONHASHSEED=0 python -m pytest
PYTHONHASHSEED=1 python -m pytest
python tools/collect_test_ids.py
python tools/verify_manifest.py
python tools/validate_contract_manifest.py
python tools/verify_reproducible_build.py
python tools/test_wheel_install.py
python tools/verify_no_forbidden_capabilities.py
python tools/e2e_audit.py
python tools/build_ledger.py --verify
python tools/validate_combined_dag.py
```

Both seed runs must collect identical test ids. A local dirty checkout, inherited virtual
environment, developer cache, or self-reported summary is not a clean-runner reproduction.

A successful producer returns literal `PASS_CAPTURE_ONLY` and leaves exactly:

```text
$CAPTURE_PARENT/output/evidence/B00R_G2/clean_runner/   # canonical 50 files
$CAPTURE_PARENT/output/clean_runner.spec-fragment.v1.json
```

Copy only the `clean_runner/` subtree to the receipt worktree. Merge the fragment's 50 `entries`
into the later `evidence/B00R_G2/spec.json`; never copy the fragment into the closed evidence root.
`PASS_CAPTURE_ONLY` is not a receipt, signature authorization, or B00R closure. After all receipt
evidence and payload bindings are materialized on the exact receipt head, run
`tools/b00r_clean_runner.py verify` against that committed head. It independently validates the
canonical 50-file bundle and derives every claim from the raw records. Do not construct or repair
the bundle by hand.

## 9. Build the separate append-only receipt PR

The receipt PR may add only:

```text
evidence/B00R_G2/**
evidence/receipts/B00R.g2.receipt.v3.json
```

It must add at least:

```text
evidence/B00R_G2/evidence_manifest.json
evidence/receipts/B00R.g2.receipt.v3.json
```

It may not modify any source, policy, decision, ruleset source-phase capture, historical receipt,
generation-1 evidence, or tag. Mixed content is a hard failure.

Materialize the clean-runner results, provider source PR/review records, canary bundle, authority
preimages, rollback proof, configuration proof, and tag-ruleset capture below `evidence/B00R_G2/`.
The provider review bundle must include all four canonical PR records:

```text
evidence/B00R_G2/codeowners_bootstrap_pr.provider.raw.json
evidence/B00R_G2/codeowners_bootstrap_pr.approved_review.provider.raw.json
evidence/B00R_G2/source_pr.provider.raw.json
evidence/B00R_G2/source_pr.approved_review.provider.raw.json
```

The receipt build spec must declare `"role_unique": true` on exactly one entry for each of these
twenty-five singleton roles; the manifest builder preserves the explicit boolean and the receipt
validator rejects an absent, duplicated, or misspelled declaration:

```text
CODEOWNERS_BOOTSTRAP_PR_PROVIDER_RECORD
CODEOWNERS_BOOTSTRAP_APPROVED_REVIEW_PROVIDER_RECORD
SOURCE_PR_PROVIDER_RECORD
SOURCE_PR_APPROVED_REVIEW_PROVIDER_RECORD
PROVIDER_NEGATIVE_CANARY
PROVIDER_NEGATIVE_CANARY_TRANSCRIPT
PROVIDER_NEGATIVE_CANARY_RULE_SUITE
WORKFLOW
CONTRACT_MANIFEST
TEST_MANIFEST
CONFIG_BUNDLE
ROLLBACK_PROOF
TAG_RULESET_PROVIDER
CLEAN_RUNNER_RUN
CLEAN_RUNNER_SOURCE_IDENTITY
CLEAN_RUNNER_SOURCE_TREE
CLEAN_RUNNER_FACTS
CLEAN_RUNNER_PACKAGE_SNAPSHOT
CLEAN_RUNNER_TEST_IDS_SEED0
CLEAN_RUNNER_TEST_IDS_SEED1
CLEAN_RUNNER_PYTEST_RESULT_SEED0
CLEAN_RUNNER_PYTEST_RESULT_SEED1
CLEAN_RUNNER_ROLLBACK_STDOUT
CLEAN_RUNNER_ROLLBACK_STDERR
CLEAN_RUNNER_ROLLBACK_RC
```

The clean-runner and tag-ruleset singleton paths are exact:

| Role | Canonical path |
|---|---|
| `WORKFLOW` | `evidence/B00R_G2/clean_runner/source/ci.yml` |
| `CONTRACT_MANIFEST` | `evidence/B00R_G2/clean_runner/source/contracts.MANIFEST.sha256` |
| `TEST_MANIFEST` | `evidence/B00R_G2/clean_runner/tests/test_manifest.v1.json` |
| `CONFIG_BUNDLE` | `evidence/B00R_G2/clean_runner/config/config_bundle.v1.json` |
| `ROLLBACK_PROOF` | `evidence/B00R_G2/clean_runner/rollback/rollback_proof.v1.json` |
| `TAG_RULESET_PROVIDER` | `evidence/B00R_G2/tag_ruleset.provider.json` |
| `CLEAN_RUNNER_RUN` | `evidence/B00R_G2/clean_runner/run.v1.json` |
| `CLEAN_RUNNER_SOURCE_IDENTITY` | `evidence/B00R_G2/clean_runner/source/source_identity.v1.json` |
| `CLEAN_RUNNER_SOURCE_TREE` | `evidence/B00R_G2/clean_runner/source/ls-tree.bin` |
| `CLEAN_RUNNER_FACTS` | `evidence/B00R_G2/clean_runner/runner/runner_facts.v1.json` |
| `CLEAN_RUNNER_PACKAGE_SNAPSHOT` | `evidence/B00R_G2/clean_runner/runner/installed_packages.v1.json` |
| `CLEAN_RUNNER_TEST_IDS_SEED0` | `evidence/B00R_G2/clean_runner/tests/test_ids.seed0.txt` |
| `CLEAN_RUNNER_TEST_IDS_SEED1` | `evidence/B00R_G2/clean_runner/tests/test_ids.seed1.txt` |
| `CLEAN_RUNNER_PYTEST_RESULT_SEED0` | `evidence/B00R_G2/clean_runner/tests/pytest.seed0.v1.json` |
| `CLEAN_RUNNER_PYTEST_RESULT_SEED1` | `evidence/B00R_G2/clean_runner/tests/pytest.seed1.v1.json` |
| `CLEAN_RUNNER_ROLLBACK_STDOUT` | `evidence/B00R_G2/clean_runner/rollback/stdout.bin` |
| `CLEAN_RUNNER_ROLLBACK_STDERR` | `evidence/B00R_G2/clean_runner/rollback/stderr.bin` |
| `CLEAN_RUNNER_ROLLBACK_RC` | `evidence/B00R_G2/clean_runner/rollback/rc.txt` |

Repeated command stdout, stderr, and status roles must explicitly declare
`"role_unique": false`. Only the verifier's thirteen exact raw-stream paths may be zero bytes;
an empty near-match, different role, or different uniqueness declaration fails closed.

Build a closed manifest that names every regular file below that root except itself:

```bash
python tools/build_evidence_manifest.py \
  --build evidence/B00R_G2/spec.json \
  --root . \
  --closed-root evidence/B00R_G2 \
  --out evidence/B00R_G2/evidence_manifest.json
```

The bare canonical receipt must use:

- milestone `B00R`, variant/root identity `B00R.g2`, and `repair_generation=2`;
- receipt path `evidence/receipts/B00R.g2.receipt.v3.json`;
- the actual generation-2 source PR number, final source head, source merge SHA/tree/time;
- audited start `76b5e4857f80f22f99385810037c5c66289ebd5f`;
- generation ledger and policy-v2 bindings;
- the generation-2 authority and provider pins;
- result `PASS_REPOSITORY_SAFE_HOLD` and activation `DENIED_SAFE_HOLD`; and
- two valid Ed25519 signatures from distinct `EVIDENCE_PRODUCER` and
  `INDEPENDENT_COUNTERSIGNER` identities over the same canonical preimage.

Before freezing or signing the final receipt head, install, capture, and externally pin the G2 tag
ruleset. The receipt PR must then obtain current exact-head CI, required native review, and resolved
threads, and merge by the sole permitted merge method under the live ruleset. Its merge first
parent must equal the source merge; its second parent and tree must equal the reviewed receipt head.
No intervening `main` merge is permitted. The receipt cannot bind its own future merge SHA; the
physical anchor supplies that final post-merge binding.

Nonterminal receipt-PR CI may use `--nonterminal-provider-proof`. Its zero exit authenticates
receipt content/head only: it skips privileged bypass/rule-suite/ref reads and every post-merge
receipt-PR proof, so it is explicitly not closure and is insufficient by itself to authorize merge.

Immediately before merging the receipt PR, run both privileged premerge proofs with an
administrator token. First prove the protected tag ruleset, visible empty bypass set, exact receipt
bytes, and chronology:

```bash
python tools/validate_b00r_tag_ruleset.py \
  --expected-head "$RECEIPT_HEAD" \
  --now-us "$NOW_US" \
  --ruleset evidence/B00R_G2/tag_ruleset.provider.json \
  --ruleset-pin "$B00R_G2_TAG_RULESET_SHA256" \
  --receipt evidence/receipts/B00R.g2.receipt.v3.json \
  --strict-live \
  --require-bypass-visibility
```

Then prove the open receipt PR's exact source base and receipt head, latest independent
CODEOWNER approval, latest successful workflow/check, live main ruleset with visible empty bypass,
and unchanged canary:

```bash
python tools/validate_b_receipt.py \
  --strict --milestone B00R --now-us "$NOW_US" \
  --manifest evidence/B00R_G2/evidence_manifest.json \
  --git-root . --expected-head "$RECEIPT_HEAD" \
  --governance-snapshot docs/governance/rulesets/main.ruleset.provider.json \
  --provider-raw docs/governance/rulesets/main.ruleset.provider.raw.json \
  --provider-pin "$MAIN_RULESET_EVIDENCE_SHA256" \
  --pins "$PINS_JSON" \
  --receipt-pr "$RECEIPT_PR" \
  --premerge-provider-proof \
  evidence/receipts/B00R.g2.receipt.v3.json
```

The `OK_PREMERGE:` result omits only facts that cannot yet exist: the receipt merge object,
merged-at time, live-main ancestry, and physical anchor. Any subsequent head, review, check,
ruleset, bypass, or canary change invalidates it and requires a fresh proof before merge.

Terminal validation after merge must omit that flag and must expose the live empty bypass
set, rule suite, unchanged canary ref, exact source PR/review, and the receipt PR number. The
terminal gate fetches that receipt PR, independently proves exact-head CODEOWNER approval and
successful provider check `test-and-verify` before merge, and proves its two-parent merge is on live
`main`.
The receipt does not self-reference its future merge SHA; terminal provider/Git proof supplies that
binding after merge.
The terminal token must be able to read the ruleset bypass field, rule suite, canary and anchor refs,
receipt reviews, workflow runs, and check runs; an ordinary restricted Actions token may be
insufficient and must fail closed rather than downgrade proof.

## 10. Publish and validate the new physical anchor

Before the receipt merge, install an active no-bypass tag ruleset targeting exactly
`refs/tags/B00R_RECEIPT_ANCHOR_G2`, with no exclusions and both update and deletion blocked. Capture
its raw provider object at `evidence/B00R_G2/tag_ruleset.provider.json` and externally pin those
exact bytes as `B00R_G2_TAG_RULESET_SHA256`. Its provider `updated_at` must be strictly before the
signed receipt's `observed_at_us` (and therefore before `emitted_at_us` and the later receipt merge).

After the receipt merge, create one annotated tag object targeting the exact receipt merge. Its
message is exactly:

```text
TRIAD-B00R-RECEIPT-ANCHOR-G2-V1
receipt_path=evidence/receipts/B00R.g2.receipt.v3.json
receipt_sha256=<SHA256_OF_EXACT_RECEIPT_BYTES>
```

Create those exact bytes in a file and pass the file once:

```bash
TAG_MESSAGE_FILE="$(mktemp)"
printf '%s\n%s\n%s\n' \
  'TRIAD-B00R-RECEIPT-ANCHOR-G2-V1' \
  'receipt_path=evidence/receipts/B00R.g2.receipt.v3.json' \
  "receipt_sha256=$RECEIPT_SHA256" > "$TAG_MESSAGE_FILE"
git tag -a B00R_RECEIPT_ANCHOR_G2 "$RECEIPT_MERGE" -F "$TAG_MESSAGE_FILE"
```

Publish `B00R_RECEIPT_ANCHOR_G2` once. Never repoint it, never use a lightweight tag, and never test
update/deletion against the real anchor. Do not use `-s`, repeated `-m`, reordered fields, a missing
terminal newline, or extra blank lines; each changes the protected tag-object profile.

Run the post-merge terminal gate from a clean checkout of the receipt merge:

```bash
python tools/b00r_gate.py --mode receipt \
  --base-sha "$SOURCE_MERGE" \
  --expected-head "$RECEIPT_MERGE" \
  --receipt-pr "$RECEIPT_PR" \
  --now-us "$NOW_US" \
  --pins "$PINS_JSON" \
  --provider-pin "$MAIN_RULESET_EVIDENCE_SHA256" \
  --anchor-ruleset-pin "$B00R_G2_TAG_RULESET_SHA256"
```

Only this terminal sequence may return `PASS_REPOSITORY_SAFE_HOLD`.

## 11. Stop conditions

| Condition | Result |
|---|---|
| Generation-1 byte/tag mutation or retro-review claimed as closure | `FAIL_GENERATION_1_MUTATION` |
| Ruleset/canary/review created after generation-2 source merge | `FAIL_CHRONOLOGY` |
| Main ruleset permits squash/rebase or omits the dedicated canary target | `FAIL_RULESET_PROFILE` |
| Source approval absent, self-authored, stale, or not exact-head | `BLOCKED_REVIEW_SAFE_HOLD` |
| Source PR number/head/merge/provider time mismatch | `FAIL_SOURCE_PR_BINDING` |
| CODEOWNERS bootstrap is direct, mixed-content, stale/self-reviewed, or time-mismatched | `FAIL_BOOTSTRAP_BINDING` |
| Receipt PR contains mixed or historical content | `FAIL_RECEIPT_LAYOUT` |
| Receipt merge lacks exact-head CI/review, ordinary merge shape, main ancestry, or matching provider/Git time | `FAIL_RECEIPT_PR_BINDING` |
| Tag ruleset was installed or updated at/after receipt `observed_at_us` | `FAIL_TAG_RULESET_CHRONOLOGY` |
| G2 anchor absent, lightweight, mutable, or points elsewhere | `BLOCKED_ANCHOR_SAFE_HOLD` |
| Any owner pin, live provider proof, or trusted time unavailable | `BLOCKED_EXTERNAL_AUTHORITY` |
| All generation-2 authority, repository, review, evidence, receipt, and anchor checks pass | `PASS_REPOSITORY_SAFE_HOLD` |

`B01C` remains frozen in every non-PASS row. When the terminal result passes, B01C may branch only
from the exact generation-2 receipt merge commit named by the validated
`B00R_RECEIPT_ANCHOR_G2`; it may not branch from generation 1, the corrective source merge, PR #33,
or an offline-preparation branch.
