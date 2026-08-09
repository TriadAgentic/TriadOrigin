# 09 · Open Questions & Clarifications Register

_Per the operator's directive, ambiguities are **not** asked in chat. They are collected here —
wiring, specification, governance, everything — and answered by the operator in one batch at the
end of the build. Each question carries a **default** the build proceeds on; an answer that
differs from the default becomes a fix-forward work item. Status: OPEN unless marked._

## A · Governance & repository

**Q-A1 · Repository home.** The operator said "the home for this engine will be in the triad
agent," while the specification (Doc 00 §00.2, RC3) and all existing work name
`TriadAgentic/TriadOrigin` as the clean-room home.
**Default:** build in `TriadAgentic/TriadOrigin` (the org is "TriadAgentic" — reading the spoken
"triad agent" as the org name, not the `TriadAgent` fleet repo).

**Q-A2 · ADR-005 supersession signature.** RC4 requires a *signed* ADR superseding ADR-005
(LEV-0001) ratifying the lever enums. The RC4 document itself is stamped
`OWNER_DIRECTIVE_RATIFIED_IMPLEMENTATION_NOT_APPLIED`.
**Default:** treat RC4 + this build directive as the operator's ratification for DARK
implementation; record the supersession in the decision register; the formally signed ADR remains
an operator artifact to countersign at answer time.

**Q-A3 · R00 receipt seal.** The R00 post-merge receipt ceremony (branch `evidence/r00-receipt`,
GraphQL snapshot validation) was designed but the sealed `evidence/receipts/R00.json` does not
exist in `main`. Its validator requires live GitHub API evidence at seal time.
**Default:** B-series uses a proportionate receipt schema (B01 defines it); the R00-specific
ceremony receipt stays honestly OPEN for the operator to run (or to ratify the B-series receipt
law as its replacement).

**Q-A4 · GitHub branch ruleset (issue #5).** A `main` ruleset requiring exact-head CI + review
cannot be configured from this session (repository-settings write is an operator permission).
**Default:** merges continue under the working practice (merge only on green CI); issue #5 stays
open for the operator to configure the ruleset and attach settings evidence.

**Q-A5 · Checkpoint ceremony scope.** The estate checkpoint law (five-repo ceremony) does not
name TriadOrigin.
**Default:** seal TriadOrigin-local checkpoints only (`checkpoint/<date>-origin-v7-build` +
`CHECKPOINTS.md` in this repo); no sibling-repo checkpoint branches are created for this build.

**Q-A7 · Control-plane homing (comparator / authority router / legacy bridge / replay runner).**
The R00-era repository law listed "runtime legacy bridge" and "authority router" in the never-add
list (reading them as out-of-repo services), while the specification (Doc 06 SRV-005/006/007/025,
RC3 wiring W07–W09 with 8 atomic tasks each) requires them built, and your directive says build
everything.
**Default:** they are built **here** as pure, dark, import-isolated library modules (comparator
side-effect-free; router lease-verify-only; bridge control-candidates-only; no network/process
wiring); where their *processes* are deployed remains an estate decision. Veto if you want them
in a different repo.

**Q-A6 · Estate/operator lanes.** 361 ESTATE + 57 OPERATOR ledger rows (other repos, on-box
acts, G-1 credential rotation, G5+ live stages) are named and tracked but not built here.
**Confirm:** this partition matches your intent ("if you need to wire with the other surfaces,
then you wire with the other surfaces later"). Estate wiring stubs in this repo are limited to
contract shapes + ingress expectations.

## B · Activation values (BLOCKING_OWNER_DECISION — stay NOT_RATIFIED / fail closed)

These eight ship as `NOT_RATIFIED` registry rows; runtime fails closed without them. Provide
values (or defer) at answer time:

| Q | Parameter | What you must declare |
|---|---|---|
| Q-B1 | PAR-070 `PRODUCTION_RISK_BUDGET` | bps-of-NAV **and** absolute quote cap |
| Q-B2 | PAR-072 `PRODUCTION_GROSS_EXPOSURE_CAP` | finite positive integer bps cap |
| Q-B3 | PAR-076 `MAX_DAILY_NET_LOSS` | daily stop, UTC reset, realized/unrealized treatment, relative + absolute caps |
| Q-B4 | PAR-077 `MAX_PEAK_TO_TROUGH_DRAWDOWN` | finite drawdown stop + high-water-mark reset governance |
| Q-B5 | PAR-118 `CANARY_CAPSULE` | exactly one capsule semantic version + parameter digest |
| Q-B6 | PAR-119 `CANARY_INSTRUMENT` | exactly one venue-qualified instrument |
| Q-B7 | PAR-120 `CANARY_SIDE` | exactly one side enum |
| Q-B8 | PAR-121 `CANARY_ACCOUNT` | one isolated account/risk cell + position mode + permissions |

## C · Research decisions (BLOCKING_RESEARCH_DECISION — built symbolic, fail closed)

| Q | Parameter | Effect while unanswered |
|---|---|---|
| Q-C1 | RC3-PAR-STRUCT-001 `EQUAL_LEVEL_MAX_SPAN` | F07 equal-level clusters cannot emit (named abstention) |
| Q-C2 | RC3-PAR-STRUCT-002 `BOOK_TILT_MIN_QUOTE_DEPTH` | F17 tilt cannot emit (named abstention) |
| Q-C3 | RC3-PAR-STRUCT-003 `PROTECTED_SWING_REDUCER_VERSION` | protected-swing promotion runs only under an explicitly versioned reducer supplied by parameter bundle; tests exercise the RC3-documented candidate semantics |

## D · Proposed parameter bundle (123 × PROPOSED_RC2_MUST_RATIFY)

The RC2 declarations propose 123 numeric values (plus 8 DECLARED_RC2, 4 CURRENT_VENDOR_REQUIRED,
8 TARGET_FROM_TOPOLOGY, …).
**Default (per BLK-RC2-010 disposition):** they are carried verbatim as a **DARK proposal
bundle** in the parameter registry (status-labelled, digest-pinned). Tests exercise formulas with
explicit test bundles; nothing runs on a proposed value in any non-test context. **Question:** do
you want to ratify the proposal bundle wholesale for DARK/shadow operation at answer time, ratify
selectively, or keep everything symbolic until trial registration?

## E · Specification conflicts already dispositioned (confirm or veto)

| Q | Conflict | Disposition taken (per RC3/RC4 precedence) |
|---|---|---|
| Q-E1 | ADR-005 "no testnet ever" vs RC4 four-plane law | RC4 wins (later owner directive): TESTNET is a canonical isolated venue environment; estate-wide NO-TESTNET rules in sibling repos are untouched by this repo |
| Q-E2 | RC1 `*_ns` envelope fields vs UTC-microsecond law | RC3 parameter row wins: UTC Unix **microseconds**; ns-precision carries remainder separately |
| Q-E3 | int64 ticks vs base-10 string wire encoding | Both: semantic type is signed int64 ticks; JSON wire encoding is base-10 string (BLK-RC2-006 disposition) |
| Q-E4 | F02 ATR window bar inclusion (BLK-RC2-007) | RC3 formula text + golden vector is authoritative; vector pins the choice |
| Q-E5 | F04 tie-break (BLK-RC2-009) | RC3 formula + vectors reject ties per PAR/GV row |
| Q-E6 | Capsule family naming (BLK-RC2-011) | RC3 CAP-01…05 registry with ordinal↔semantic-version map recorded in the capsule registry artifact |
| Q-E7 | Candidate lifecycle abstention/withdrawal (BLK-RC2-013) | RC3 lifecycle graph implemented; withdrawal is a first-class transition record |
| Q-E8 | F18 stop-side `abs()` defect (BLK-RC2-014) | directional stop-side invariant implemented; one-tick vectors added |
| Q-E9 | W06 cluster-ID circularity (BLK-RC2-012) | non-circular prospective cluster-root design per RC3 overlay |

## F · Estate wiring handoffs (for the "wire with other surfaces later" phase)

- **Q-F1:** Which repo/process will host the E01 `market_state.v2` bridge from `context.packets`
  (W01/W02) when ORIGIN is deployed dark — TriadEngine, or a new bridge service?
- **Q-F2:** The legacy bridge consumes `candidate.v1` from the current E02. Confirm the source
  topic/ledger path to freeze for the control arm.
- **Q-F3:** Divergence + candidate-authority topics (`edge.divergence.v1`, `edge.authority.v1`):
  file-ledger paths/ownership on the box, for `transport_bindings.v1`.
- **Q-F4:** The SHADOW recorder (RC4): does the estate's existing shadow bank (TriadDTBNK)
  consume ORIGIN's shadow dispositions, or does ORIGIN keep a local shadow ledger until an estate
  consumer lands? Default: local durable ledger + contract-shaped rows.
- **Q-F5:** RC4 L1 as-built census covers seven external engines (QuantTrade 0, YoloNaut 1,
  YoloBot V2, UPONLY Core, NewNaut, …) — entirely outside this repo. Confirm these are a separate
  program.

## G · Session-scope confirmations

- **Q-G1:** RC1-complete-edition HTML (4.0 MB) was hash-registered but not vendored (the 11
  modular RC1 docs are already in `docs/spec/`; RC3 embeds RC1). Confirm hash-registration
  suffices.
- **Q-G2:** Milestone receipts are sealed one-behind (milestone N's receipt lands in milestone
  N+1's PR, reproduced from merged `main`). Confirm.
