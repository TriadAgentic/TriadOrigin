# Migration runbook

- **Runbook-ID:** `RB-MIGRATION`
- **Scope:** ORIGIN-OWNED (stages M1 deterministic offline replay, M2 connected dark) · ESTATE-BOUNDARY (M3–M9)
- **Activation posture:** `DENIED_SAFE_HOLD` — baseline `venue_environment=OFF / venue_activation=OFF / paper_activation=OFF / shadow_activation=LIVE` (`shadow_activation` fixed `LIVE`, not switchable). No stage in this runbook advances any lever; a non-OFF activation is not representable without the signed ADR and its gate receipt.
- **Sources:** RC1 §09.1 (migration principles), §09.2 (stage plan M−1..M9 + exit gates), §09.11 (progressive scale), §09.12 (RACI); RC4 `lever_law`; `10_MASTER_SPEC_ALIGNMENT_AUDIT.md` (RC1↔RC4 reconciliation).

Migration is a **staged, one-dimension-at-a-time** promotion, not a switch. The five governing
principles (RC1 §09.1): *deploy is not authority* (validate new code before any producer lease);
*authority is scoped* (capsule, symbol, side, account, risk cell, arm, validity are explicit — no
wildcard first activation); *one writer* (a new producer cannot acquire scope until the prior token
is revoked/fenced and outstanding ownership is safe); *exit authority survives entry rollback*; and
*no big bang / no simultaneous expansion*. ORIGIN's own lawful stages are the offline and dark ones;
the money-line stages are estate-owned and referenced here as a boundary.

## Owner

- **M1 — Deterministic offline replay** and **M2 — Connected dark** are **ORIGIN-OWNED**. M1 runs
  same-code ORIGIN on sealed exact tapes (the B07 replay runner); M2 reads live E01 state and emits
  structures/candidates/heartbeats/divergence only, with money ACLs denied. A healthy build reaches
  only `READY_NO_AUTHORITY`.
- **M−1 (freeze and secure)** and **M0 (contract/authority foundation)** are shared: ORIGIN owns its
  own contract/manifest publication; account/writer/credential custody is estate.
- **M3 authority router · M4 execution rehearsal · M5 dual-publish · M6 canary · M7 economic
  certification · M8 cutover · M9 scale/retirement** are **ESTATE-OWNED** (E07/E08/E09/E10). ORIGIN
  documents the boundary and never issues an order, reservation, lease, or venue command for them.

## Trigger

A migration step begins only when the **prior stage's exit gate has passed** and an operator
requests the advance. Representative exit gates (RC1 §09.2): M1 requires *zero unexplained replay
divergence + signed replay receipts*; M2 requires *zero contamination + coverage/freshness/resource
SLOs pass*; M3 requires *exactly one candidate per allocation + split-brain and stale epochs reject*.
No stage advances the levers off the `OFF/OFF/OFF/LIVE` baseline — TESTNET/LIVE promotion is a
separate estate gate ([`testnet.md`](testnet.md)), not a migration stage.

## Stop

A migration halts on any automatic stop condition (RC1 §09.8), enforced under the RC4 containment:

- **Manifest/build/config mismatch** → reject readiness/authority; roll back to the attested bundle
  (Severity 1). RC4 `RUNTIME_LEVER_ATTESTATION_MISMATCH` / `LEVER_REGISTRY_INCOMPLETE` →
  `venue_activation=OFF; paper_activation=OFF for the affected scope; shadow_activation=LIVE`.
- **Replay/state checksum divergence** → remove ORIGIN authority; preserve inputs/checkpoints; roll
  back (Severity 1).
- **Stale producer accepted / two writers** → the split-brain path ([`split_brain.md`](split_brain.md)).
- A migration never proceeds while a scope is under a scope-forcing refusal; the affected scope stays
  OFF until *current proof converges* (SHADOW stays LIVE throughout).

## Rollback

Rollback contains risk first (RC1 §09.1): entry authority is stopped and positions/orders/protection
are made known **before** diagnosis. A failed stage never advances; the repository-mechanism reversion
is the checkpoint law in [`rollback.md`](rollback.md) — branch **from** a checkpoint, fix forward,
merge via PR; `main` is never rewritten. **Exit authority survives entry rollback**: cancels,
protection, reconciliation, and verified exposure reduction remain available (see
[`protection.md`](protection.md)). The money-line five-case rollback is estate-owned and referenced,
not executed here.

## Evidence

Evidence is **append-only**; a rollback deletes no losing event, failed trial, or incident fact
(RC1 §09.1). Each stage produces its own immutable receipt: signed replay receipts (M1);
coverage/freshness/resource SLO receipts (M2); the per-stage gate receipt for every estate stage.
Every authority owner is named at M−1. Fingerprints, never credentials.

## Escalation

Roles and approvals follow the RC1 §09.12 RACI: independent risk/security/architecture sign-off
gates repromotion, and any non-OFF activation is the **operator's** ratified act (the signed
ADR-005 supersession — currently UNSIGNED — plus the gate receipt). Sev-1 stop rows page
Security/Risk/Execution. ORIGIN agents flag loudly and hand the boundary; they never order an
activation or a disarm.
