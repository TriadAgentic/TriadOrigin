# 00 · Master Plan — TRIAD ORIGIN V7 B-Series Build

_Supersedes the M1–M6 plan (PR #3) and the R00 SAFE_HOLD next-action. Operator directive
2026-08-09 (this session): build the complete ORIGIN V7 engine end-to-end, DARK, milestone by
milestone, against the now-complete RC2+RC3+RC4 control package._

## 1 · Authority for this build

The prior hold ("do not start detector/M3/B01+ work before B00 is ratified") was grounded in two
facts: the RC2 source bundle was incomplete, and no owner decision authorized implementation. Both
are now resolved:

1. **The complete control package exists.** The operator supplied the RC3 Complete Master
   Specification & Master Document (1.0.0-RC3, 2026-08-09), which embeds the full RC2 canonical
   registries (1,088 tasks / 2,201 dependencies / 1,496 verifications / 183 parameters / 24
   formulas / 26 wiring rows / 22 golden vectors) plus the RC3 normative overlay, effective
   control bundle (1,115 tasks), manifest, and validation report — all extracted and vendored
   under [`docs/control/`](../control/) with SHA-256 inventory. The RC2 package members previously
   recorded missing in `06_RC2_SOURCE_INVENTORY.md` are now supplied under `docs/spec_rc2/`.
2. **An operator directive authorizes the build.** Per Doc 00 §00.4 / RC3 §00 precedence, an
   authenticated owner decision is authority rank 1. The operator (account owner) directed on
   2026-08-09: build everything end-to-end in this repository, milestone PRs merged on green,
   end-to-end audit script maintained, checkpoint seal at completion, questions batched into a
   clarification document answered at the end. This directive authorizes **specification-faithful
   DARK implementation only** — it does not arm anything, ratify activation values, or create
   money authority. Everything stays `RATIFICATION_CANDIDATE_NOT_ARMED` / `READY_NO_AUTHORITY`.

Additionally, the RC4 Four-Plane Execution & Lever Master Addendum (1.0.0-RC4,
`OWNER_DIRECTIVE_RATIFIED_IMPLEMENTATION_NOT_APPLIED`) supersedes ADR-005: the canonical lever
model is `venue_environment ∈ {LIVE, TESTNET, OFF}` × `venue_activation ∈ {LIVE, OFF}` ×
`paper_activation ∈ {LIVE, OFF}` × `shadow_activation = LIVE` (mandatory). ORIGIN implements the
lever/plane law as code; every venue-facing consequence remains estate-owned.

## 2 · Objective

Build **TRIAD ORIGIN V7 — Deterministic Causal Edge Core** faithfully to the effective control
bundle (RC3) and the lever addendum (RC4): deterministic causal state machines (features →
levels → structures → reactions → capsules → candidates), strict versioned contracts with
byte-pinned identity, hash-chained transport with replay/checkpoint determinism, the four-plane
lever/refusal law, signed configuration artifacts, read-only evidence faces, and a
falsification-first verification matrix — as a governed, testable, **DARK** codebase in
`TriadAgentic/TriadOrigin`.

**Out of scope by construction:** live activation, venue credentials/order verbs, money
authority, ratified numeric activation values (they stay `NOT_RATIFIED` → fail closed), and every
estate-side task (other repos, on-box acts, governance ceremonies) — those are *named and
tracked*, never silently absorbed or silently dropped.

## 3 · Constitution (unchanged, binding)

1. Deterministic control bypasses intelligence — pure transitions, no clock/I-O/randomness.
2. Maker-first/post-only; taker is an E09-owned emergency escape (referenced, never coded here).
3. Four planes per RC4: venue (LIVE|TESTNET|OFF) · PAPER · SHADOW (always LIVE); populations
   never blend; legacy lever aliases are refusals.
4. Five isolated capsules; no vote ensemble.
5. RR ≥ 2.0 geometric candidate floor before costs.
6. No legacy-value inheritance: `require()` fails closed on absent parameters; proposals are
   carried as data, never as code defaults.
7. Deploy is not authority: `READY_NO_AUTHORITY`; leases are verified, never issued here.
8. Immutable contract bytes; same version ⟹ byte-identical; manifest gates CI.
9. Evidence is append-only and honest-null.
10. **The E2E growth law:** every milestone that lands a capability extends
    `tools/e2e_audit.py` with a walk stage for it in the same PR.

## 4 · The build ledger — how 1,250 control rows become work

`tools/build_ledger.py` deterministically partitions every effective task (1,115 RC3 + 135 RC4)
into build milestones `B00–B10` or the named non-repo lanes `ESTATE` / `OPERATOR` / `RESEARCH` /
`ACTIVATION`, writing [`docs/control/build_ledger.json`](../control/build_ledger.json). The
partition is `HEURISTIC_V1` plus a reviewed override table; each milestone PR reviews its slice
and corrects misclassifications via overrides. Current partition:

| Lane | Rows | Meaning |
|---|---:|---|
| B00–B09 | 828 | executable in this repository (code, contracts, config, tests, docs) |
| ESTATE | 361 | owned by other Triad repos / live estate (named, not built here) |
| OPERATOR | 57 | owner/governance ceremony or on-box act (G-1, G7–G9, cutover) |
| RESEARCH | 4 | blocked on named research decisions (fail-closed symbolic) |
| ACTIVATION | 0* | activation-value rows carried inside B07 config as `NOT_RATIFIED` |

The ledger never marks completion; milestone receipts do. `--verify` runs in CI so the partition
can never silently drift from the vendored bundles.

## 5 · Milestone map

| # | Milestone | Theme | Gate anchor |
|---|-----------|-------|-------------|
| **B00** | Authority & control baseline | vendored bundles, plan, ledger, e2e audit v0, questions doc | — |
| **B01** | Foundation corrections | typed identity v2, attestation equality, manifest descriptor, strict receipt schemas, v2/v3 contract catalog (incl. `fill.v3`, `structure_atom.v2`, `edge_candidate.v2`) | G0 |
| **B02** | Kernel hardening | ledger external anchor + tail-deletion falsification, per-scope fence restore, RC4 timing registry | G0/G1 |
| **B03** | Structure semantics I | feature primitives, typed levels, structure state (F02–F10) | G2 |
| **B04** | Structure semantics II | FVG, displacement, order block, excursion/reclaim, flow atoms (F11–F14, F16–F18), lifecycle reducer | G2 |
| **B05** | Reaction, capsules & candidates | reaction engine (F15), geometry+RR (F19), clustering (F20), capsule host, 5 capsules, candidate publisher | G3 |
| **B06** | Lever & four-plane control | `engine_control_manifest.v2`, lever parser/resolver/attestation, 32 refusal codes, shadow-law recorder, plane-population guards | RC4 L0–L5 |
| **B07** | Config, wiring & services | signed config artifacts + parameter registry, comparator, authority router, legacy bridge, replay runner, service main | G4 |
| **B08** | Read faces & evidence | read-only evidence projections, readiness truth, funnel/zero-reason telemetry | G5, RC4 L6 |
| **B09** | Verification matrix & runbooks | Doc 08 matrix consolidation, estate-formula catalog vectors (F21–F24), runbooks | — |
| **B10** | Audit rounds & seal | multi-round adversarial audits, implementation report, clarification report, checkpoint seal | — |

Sequencing: strictly B00 → B01 → … → B10. Detail: [`01_MILESTONE_BREAKDOWN.md`](01_MILESTONE_BREAKDOWN.md).
Checklist: [`08_BUILD_CHECKLIST.md`](08_BUILD_CHECKLIST.md). Questions:
[`09_OPEN_QUESTIONS.md`](09_OPEN_QUESTIONS.md).

## 6 · PR, merge & receipt cadence

- **One PR per milestone** into `main`; squash-merged the moment CI is green. CI = the R00 gate
  (falsification suite under `PYTHONHASHSEED` 0 and 1, exact collection identity, contract
  manifest + schema, reproducible build, wheel smoke, DARK capability boundary) **plus** the two
  B00 additions: `tools/e2e_audit.py` and `tools/build_ledger.py --verify`.
- After each merge the working branch `claude/triod-origin-planning-8257zm` is reset onto fresh
  `origin/main`.
- **Milestone receipts:** each milestone PR seals a JSON receipt for the *previous* milestone
  (evidence reproduced from merged `main`) under `evidence/receipts/`, using a proportionate
  B-series receipt schema (documented in B01). The unfinished R00 GraphQL-ceremony receipt is
  tracked in `09_OPEN_QUESTIONS.md`, not silently dropped.
- **Checkpoints:** per the operator's instruction, checkpoints seal **big** milestones only: one
  `checkpoint/<date>-origin-v7-build` branch + `CHECKPOINTS.md` row at the end of the build
  (B10), plus optional intermediate seals after B05 (core semantics complete) if the operator
  requests one.

## 7 · Verification strategy

Falsification-first, three layers, all growing every milestone:

1. **Unit falsification suite** (`python -m pytest`) — per-module proof obligations: prefix /
   restart / duplicate invariance, LONG/SHORT mirror, scale metamorphism, lifecycle monotonicity,
   identity stability, risk independence, null honesty, fail-closed-on-missing-parameter, and
   golden-vector pins (the 22 RC2/RC3 vectors land with their owning modules).
2. **End-to-end audit walk** (`tools/e2e_audit.py`) — the operator-directed synthetic walk
   through every shipped capability, extended in the same PR as each capability.
3. **Control-bundle conformance** — `build_ledger --verify` + per-milestone review of the claimed
   RC3/RC4 task slice against acceptance criteria; consolidated into `tests/matrix/` (B09) with
   RC3 verification IDs.

## 8 · Risks & mitigations

| Risk | Mitigation |
|---|---|
| 1,250-row scope explosion | machine ledger partitions once, reviewed per milestone; estate/operator rows are named lanes, never build debt |
| RC1↔RC2↔RC3↔RC4 conflicts | RC3 precedence order + conflict register dispositions recorded per milestone; RC4 supersessions applied last |
| Unratified numeric thresholds | carried as data (`NOT_RATIFIED`/proposal status); runtime `require()` fails closed; no code default ever |
| Workflow-authored drift | shared substrate authored directly; fan-out agents self-test; full gate + e2e re-verified before every merge |
| Money-path creep | capability-boundary verifier in CI; candidate contracts forbid money fields; lever law is data+validators, no venue reach |
| Prior-agent ceremony debt (R00 receipt, issue #5 ruleset) | tracked honestly in `09_OPEN_QUESTIONS.md`; never silently relabelled |

## 9 · Explicitly deferred / non-executable here (named)

Estate engines census (RC4 L1), estate wiring W00–W02/W10–W21, live Binance ingress
certification, G-1 credential rotation & estate freeze, G5+ prospective dark operation on live
data, G7 canary, G8 economic certification, G9 cutover, JetStream binding, Hyperliquid adapters,
object-store archive, and all eight `BLOCKING_OWNER_DECISION` activation values plus three
`BLOCKING_RESEARCH_DECISION` structure values — every one carried in the ledger and the questions
document with its blocking decision named.
