# TRIAD ORIGIN E02-V7 — operational runbooks

This directory is the B09 runbook deliverable
(`docs/plan/01_MILESTONE_BREAKDOWN.md` §B09; `docs/plan/08_BUILD_CHECKLIST.md` §B09).

**The six-field content law.** Every runbook here contains exactly six required sections —
**Owner · Trigger · Stop · Rollback · Evidence · Escalation** — the acceptance criterion the
milestone names verbatim (`01_MILESTONE_BREAKDOWN.md`: *"runbooks contain owner, trigger, stop,
rollback, evidence, and escalation"*). `tests/docs/test_runbooks.py` asserts every file carries
all six and its baseline-posture header.

**These are documentation, not capability.** ORIGIN builds and imports **no** venue client,
network control path, credential/private-key loader, order verb, risk/quantity authorization,
money publisher, fill parser, or lease issuer (`CLAUDE.md` repository-ownership law). A runbook may
*describe* an estate procedure at the boundary, but nothing in this repository *executes* one. The
`verify_no_forbidden_capabilities` gate proves the code carries no such reach.

**Every runbook is written for one baseline.** The controlling activation result is
`DENIED_SAFE_HOLD`. The required non-authoritative manifest is exactly
`venue_environment=OFF / venue_activation=OFF / paper_activation=OFF / shadow_activation=LIVE`
(`shadow_activation` fixed `LIVE`, not switchable — no setter, environment fallback, or alias;
`00_MASTER_PLAN.md`, `docs/control/rc4_control_bundle.json` `shadow_law`). **No procedure in this
directory authorizes an activation.** Each documents the triggers and containment that hold
new/increasing exposure OFF while keeping exits, reconciliation, and SHADOW alive.

**Two content laws bind the prose** (runbooks are not on the deterministic semantic path, so the
wall-clock/randomness ban does not bind their narrative, but these do):

- **No secrets.** Record fingerprints, never credentials — *"operators never paste credentials into
  incident records"* (RC1 §09.9). No runbook contains a key, token, or venue how-to.
- **No invented numbers.** Owner-ratified values that the specification leaves open (DR `RPO`/`RTO`,
  the DR-proof cadence, exact activation scope) stay named `BLOCKING_OWNER_DECISION` — *"no invented
  numbers appear here"* (RC1 §09.10).

## The eleven runbooks and their scope

| Runbook | File | Scope | Primary source |
| --- | --- | --- | --- |
| Migration | [`migration.md`](migration.md) | ORIGIN-OWNED (M1/M2) · ESTATE-BOUNDARY (M3–M9) | RC1 §09.1–§09.2 |
| Rollback | [`rollback.md`](rollback.md) | REPOSITORY-MECHANISM + ESTATE-BOUNDARY | RC1 §09.7–§09.8; `CLAUDE.md` checkpoint law |
| Split-brain | [`split_brain.md`](split_brain.md) | ORIGIN-OWNED (verify-only latch) | RC3 W09; `authority_fact_verifier.py`; RC4 `PRODUCER_LEASE_CONFLICT` |
| SHADOW degradation | [`shadow_degradation.md`](shadow_degradation.md) | ORIGIN-OWNED | RC4 `shadow_law` + SHADOW refusals |
| PAPER isolation | [`paper_isolation.md`](paper_isolation.md) | ORIGIN-OWNED | RC4 `four_plane_law.paper` + PAPER refusals |
| TESTNET | [`testnet.md`](testnet.md) | ESTATE-BOUNDARY (venue-path) | RC4 `lever_law` / `four_plane_law.testnet`; open-question E1 |
| Incident | [`incident.md`](incident.md) | ESTATE command flow; ORIGIN evidence | RC1 §09.9 |
| Fill-lineage | [`fill_lineage.md`](fill_lineage.md) | ESTATE-BOUNDARY (E09/E10) | RC1 §09.5-M5; System Laws 4/5 |
| Reconciliation | [`reconciliation.md`](reconciliation.md) | ESTATE-BOUNDARY (E09) | RC1 §09.6-B, §09.10 |
| Protection | [`protection.md`](protection.md) | ESTATE-BOUNDARY (E09) | RC1 §09.1, §09.7 cases 3/4 |
| Disaster recovery | [`disaster_recovery.md`](disaster_recovery.md) | ORIGIN checkpoint/replay leg + ESTATE-BOUNDARY | RC1 §09.10 |

The compressed checklist line (`08_BUILD_CHECKLIST.md`:
*"Migration/rollback/split-brain/SHADOW/PAPER/TESTNET/fill/reconciliation/DR"*) names nine; the
milestone deliverable (`01_MILESTONE_BREAKDOWN.md`) names eleven, adding **incident** and
**protection**. The milestone deliverable governs, so all eleven are built here.

## Reconciling RC1 §09 to the RC4 lever law

RC1 doc 09 (*Not armed*) pre-dates the exact RC4 four-plane / SHADOW-containment model
(`10_MASTER_SPEC_ALIGNMENT_AUDIT.md`). Where RC1 procedure prose and RC4 containment differ, these
runbooks **follow the RC4 `OFF/OFF/OFF/LIVE` lever law and the 32 refusal `minimum_action`
containments** rather than transcribing RC1 verbatim. RC1 supplies the stage/rollback/incident/DR
*procedure shape*; RC4 supplies the *lever posture and containment* every step is written under.

## The TESTNET framing note (why this is not a "no testnet ever" retirement)

For **this** estate, RC4 makes `TESTNET` a **canonical isolated venue environment**
(`lever_law.venue_environment_enum = [LIVE, TESTNET, OFF]`;
`four_plane_law.testnet = {population: TESTNET, real_money: false, venue_path: true}`). The sibling
money-line estate's *"no testnet ever / LIVE-only"* rule (ADR-005 / the sibling `BOTTOM-LINE VENUE
RULE`) is a **different estate's law**, superseded here by RC4 (open-question **E1**,
`DEFAULT_IN_FORCE`; `docs/governance/ADR-005-SUPERSESSION.md`); sibling repositories are left
untouched. TESTNET carries `venue_path: true`, so it is **estate-owned** and **ORIGIN never
operates it** — [`testnet.md`](testnet.md) is a promotion-gate / boundary runbook that records
ORIGIN's refusal to operate TESTNET, **not** a how-to-enable procedure and **not** a retirement
notice. It is currently `OFF` under `DENIED_SAFE_HOLD`.
