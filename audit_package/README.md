# TRIAD ORIGIN V7 — B01–B10 Cleanup, Rebuild, and Audit Package

| Field | Value |
|---|---|
| Evidence snapshot | 2026-08-09 |
| GitHub refresh cut-off | 2026-08-09T12:33:04Z |
| Repository | `TriadAgentic/TriadOrigin` |
| Current observed `main` | `2cebc1391d65028a2a7de200d2e3fb9f82369872` |
| Latest source PR found | B07 PR #24, merged as `2cebc1391d65028a2a7de200d2e3fb9f82369872` from head `7a51bf62305ad87b61784b334a17212916806dbc` on invalid base `b8dc8ba514eb3d5b7f9e3d9c3b49169b58cd1b07` |
| Latest merged source PR | B06 PR #22, merged as `33ff02a6e039ed00f008e8030438b7ce62b281cc` |
| Latest receipt PR found | B07 PR #25, open at head `84c98d9b61528d96dc9efa2a8560bb42bf193e76` on invalid subject/base `2cebc1391d65028a2a7de200d2e3fb9f82369872` |
| Latest merged receipt PR | B06 PR #23, merged as `b8dc8ba514eb3d5b7f9e3d9c3b49169b58cd1b07` |
| B08–B10 PRs found | None at the refresh |
| Controlling posture | `DENIED_SAFE_HOLD` |
| Exact configuration target | `venue_environment=OFF`, `venue_activation=OFF`, `paper_activation=OFF`, `shadow_activation=LIVE` |

## Verdict

The repository is **not legitimately closed through B06 or B07**. Green CI, merged milestone
labels, and self-described receipts do not cure the evidence defects.

- B01–B05 source exists, but the reviewed-head, merge-order, governance, receipt-authentication,
  chronology, preimage, and predecessor-chain record is not sufficient for a valid closure chain.
- Branch-governance issue #5 remains open.
- The B-series receipt-authentication CI condition was R00-only, so B-series runs could skip the
  step while appearing green.
- B06 source PR #22 was built on the invalid B05 chain. Its only submitted independent review
  identifies historical head `9f695cfc4a9d497f51b717debaa377cc6b211e0e`, not final source head
  `3114c97ca77f1a257cc225198eac9e452a9800d4`.
- B06 receipt PR #23 was reviewed at historical head `a9543365…`, then changed and merged. The
  receipt remains invalid for additional reasons documented in the B06 checklist, including its
  receipt profile, evidence roots, chronology, and inherited invalid ancestry.
- B07 PR #24 was merged on that invalid B06 receipt base as `2cebc1391…`. Green CI cannot cure its
  ancestry; its shown automated review binds historical head `b7eea81aea…`, not final head
  `7a51bf6230…`, and its five inline threads were resolved by the implementation author. Preserve
  and tag the merge as `BUILT_ON_INVALID_ANCESTRY`; issue no receipt and forward-repair it from the
  corrected B06R receipt commit.
- B07 receipt PR #25 is open on the invalid PR #24 merge. Its shown automated review binds earlier
  head `04a0c6b5bb…`, not current head `84c98d9b61…`, and its CI was still in progress at the cut-off.
  Even a later green run cannot authenticate or legitimize an invalid subject ancestry; preserve
  the attempt, issue no current B07 receipt from it, and rebuild the receipt only after forward repair.

Preserve all of that material as historical evidence. Do not rewrite or grandfather it. Build the
correction chain from the exact validated predecessor receipt commit and keep every activation
authority denied.

## Scope and evidence boundary

This package closes only a **repository repair and verification procedure**. It does not certify an
estate deployment, a current runtime state, TESTNET, LIVE, money authority, profitability, or
capital safety.

The supplied 2026-08-07 MCP investigation is useful dated diagnostic evidence: it distinguishes
SHADOW from money populations and reports honest `NOT_MEASURABLE` gaps. It is not a source or gate
receipt. MCP reachability, tool enumeration, or an `ok:true` response cannot replace authenticated
source, GitHub, control-plane, venue, or outcome preimages. Optional runtime evidence accepted by
the runner is reported separately and can never promote a repository result into estate
certification.

The topology image is illustrative target-state orientation only. Written owner decisions and the
RC4/RC3/RC2 authority stack control.

## Required milestone cadence

Each nonterminal milestone has two identities:

- `subject_source_merge_sha`: the independently reviewed source merge;
- `receipt_commit_sha`: the later evidence-only commit containing its authenticated receipt.

The next milestone branches from the predecessor's validated `receipt_commit_sha`, not merely its
source merge. A source PR and receipt PR are distinct. B10 is the terminal exception: its receipt
commit is a direct child of the B10 source merge on a detached immutable evidence ref, is bound by a
verified signed tag, and is never merged back into `main`.

The repair order is B01C → B02C → B03C → B04C → B05C → B06R → B07 → B08 → B09 → B10. If a later
branch or merge was created on invalid ancestry, preserve it as `BUILT_ON_INVALID_ANCESTRY`, port
only reviewed changes onto the corrected predecessor, and rerun every inherited gate.

## Package contents

1. `01_B01_CONTRACT_IDENTITY_BINDING_CLEANUP_WORK_ORDER.md`
2. `02_B02_KERNEL_E01_INTERFACE_CLEANUP_WORK_ORDER.md`
3. `03_B03_FEATURE_STRUCTURE_CLEANUP_WORK_ORDER.md`
4. `04_B04_STRUCTURE_FLOW_LIFECYCLE_CLEANUP_WORK_ORDER.md`
5. `05_B05_FOUR_PLANE_SUBSTRATE_CLEANUP_WORK_ORDER.md`
6. `06_B06_REACTION_CAPSULE_CANDIDATE_BUILD_CHECKLIST.md`
7. `07_B07_CONFIGURATION_COMPARISON_AUTHORITY_REPLAY_BUILD_CHECKLIST.md`
8. `08_B08_READ_FACES_AND_EVIDENCE_PROJECTIONS_BUILD_CHECKLIST.md`
9. `09_B09_CONFORMANCE_FORMULA_CATALOG_RUNBOOKS_BUILD_CHECKLIST.md`
10. `10_B10_INDEPENDENT_AUDIT_TERMINAL_RECEIPT_CHECKPOINT_CHECKLIST.md`
11. `triad_origin_b01_b10_audit.py`
12. `PACKAGE_VALIDATION.md`
13. `SHA256SUMS`

Each milestone file is standalone. It includes its entry gate, authority and non-goals, required
flow, implementation packages, falsification matrix, execution order, receipt law, rollback/stop
conditions, definition of done, handoff, and sign-off record.

## Audit runner

`triad_origin_b01_b10_audit.py` is a standard-library independent checker. It separates hard-gate
status, completion score, and evidence coverage. A high score cannot override a failed, blocked,
unavailable, or unauthenticated mandatory control. The only successful result is
`PASS_REPOSITORY_SAFE_HOLD`; it grants no activation authority.

First run the embedded false-green and leakage suite:

```bash
python3 triad_origin_b01_b10_audit.py --self-test
```

For a local audit, externally select the exact subject head, trust-registry digest, and ratified
`DECISION-RECEIPT-PROFILE-001` digest. The explicit execution flag acknowledges that mandatory
verification commands are repository code:

```bash
python3 triad_origin_b01_b10_audit.py \
  --mode local \
  --repo /path/to/TriadOrigin \
  --expected-head <40-lowercase-hex-subject-sha> \
  --trust-registry /secure/read-only/receipt-trust-registry.json \
  --trust-registry-sha256 <64-lowercase-hex-registry-sha256> \
  --receipt-profile-decision-sha256 <64-lowercase-hex-DECISION-RECEIPT-PROFILE-001-sha256> \
  --check-evidence evidence/audit/check-evidence.json \
  --allow-repo-code-execution \
  --output /absolute/new/audit-output
```

For live GitHub plus local verification, use a read-only `GH_TOKEN` or `GITHUB_TOKEN`; do not put a
token in an argument or URL. Pin the trusted workflow bytes and receipt-profile decision, bind the
subject to one exact PR, and explicitly select the active source and receipt PR where more than one
candidate exists:

```bash
GH_TOKEN="<read-only-token>" python3 triad_origin_b01_b10_audit.py \
  --mode full \
  --repo /path/to/TriadOrigin \
  --repo-full-name TriadAgentic/TriadOrigin \
  --pr <exact-subject-source-pr-number> \
  --expected-head <40-lowercase-hex-subject-sha> \
  --workflow-sha256 <64-lowercase-hex-trusted-ci-yml-sha256> \
  --source-pr B06=22 \
  --receipt-pr B06=23 \
  --trust-registry /secure/read-only/receipt-trust-registry.json \
  --trust-registry-sha256 <64-lowercase-hex-registry-sha256> \
  --receipt-profile-decision-sha256 <64-lowercase-hex-DECISION-RECEIPT-PROFILE-001-sha256> \
  --check-evidence evidence/audit/check-evidence.json \
  --allow-repo-code-execution \
  --output /absolute/new/audit-output
```

An offline GitHub snapshot can be imported with `--github-snapshot`, but an unsigned or unpinned
snapshot is diagnostic-only and must remain `UNAVAILABLE`. A PASS-capable snapshot requires the
runner's closed schema plus two independent valid signatures under the externally pinned trust
registry.

For B10, also supply the detached receipt bytes, its content-addressed evidence root, the exact
direct-child receipt commit, its in-commit path, and a verified signed tag:

```bash
  --terminal-receipt /evidence/B10.json \
  --terminal-evidence-root /evidence/preimages \
  --terminal-receipt-commit <40-lowercase-hex-receipt-commit> \
  --terminal-receipt-git-path evidence/terminal/B10.json \
  --terminal-tag triad-origin-b10-terminal-<id>
```

### Host-execution boundary

The runner never intentionally modifies the supplied checkout: it audits an independent clone,
checks exact heads, uses a fresh clone per mandatory command, strips credentials, caps captured
output, and kills a timed-out process group. That is **source-checkout read-only**, not a host
sandbox. Repository commands can otherwise access whatever the invoking OS account can access.
Run untrusted repository code inside an external container/VM with the source mounted read-only,
network disabled, a writable disposable output volume, and CPU/memory/process/file-size limits.
`--allow-repo-code-execution` is an explicit trust acknowledgment, not a sandbox substitute.

## Reports and exit codes

The runner emits Markdown, HTML, JSON, CSV, JUnit, command logs, an evidence manifest,
content-addressed input preimages, checksums, and a deterministic ZIP. Its ZIP is designed to remain
independently inspectable after temporary clones are gone.

| Exit | Meaning |
|---:|---|
| 0 | All requested repository hard gates passed; safe-hold only |
| 1 | At least one hard assertion failed |
| 2 | Invalid invocation or policy |
| 3 | Blocked/unavailable/not-run evidence prevents a decision |
| 4 | Runner/internal evidence error prevented a trustworthy audit |
| 124 | A mandatory command timed out |

Return the generated ZIP without editing it. Start with `SUMMARY.md`, `DETAILED_REPORT.md`,
`report.json`, `scorecard.csv`, `findings.csv`, `junit.xml`, `github_evidence.json` when present,
`evidence_manifest.json`, `inputs/input_preimages.json`, and `SHA256SUMS`.

## Authority order

1. Authenticated owner decisions and signed supersessions within their lawful scope.
2. RC4 Four-Plane Execution and Lever Master Addendum.
3. RC3 effective master overlay and executable correction bundle where RC4 is silent.
4. RC2 canonical registries where RC3/RC4 are silent.
5. Reconciled scheduling/decision material where the specifications are silent.
6. Repository and GitHub evidence for as-built status.
7. Illustrative topology only for orientation.

No source may silently widen another component's authority. E02 produces deterministic structures,
hypotheses, and candidates; E07 owns admission/policy decision; E08 alone selects risk policy and
final size; E09 owns venue and money facts; E10 owns outcomes.
