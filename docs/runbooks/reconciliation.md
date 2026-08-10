# Reconciliation runbook

- **Runbook-ID:** `RB-RECONCILIATION`
- **Scope:** ESTATE-BOUNDARY (E09 owns venue/private-stream reconciliation). ORIGIN is consume/verify-only and joins nothing.
- **Activation posture:** `DENIED_SAFE_HOLD` — baseline `venue_environment=OFF / venue_activation=OFF / paper_activation=OFF / shadow_activation=LIVE`. Reconciliation is the gate that must pass **before** any authority is restored; it never itself arms a lever.
- **Sources:** RC1 §09.6-B (drain legacy scope), §09.7 cases 3/4, §09.9 (*establish truth*), §09.10 (restore order); RC4 `PRIVATE_STATE_STALE` / `UNKNOWN_SUBMIT_UNRECONCILED` (`private_state_max_age_ms=5000`); `00_MASTER_PLAN.md` System Law 4.

Reconciliation proves the venue/private-stream truth — orders, fills, positions, protection,
reservations — against raw facts, so that no authority is restored on top of an ambiguous position.
It is E09's money-line procedure; ORIGIN documents the boundary and its verify-only role.

## Owner

**E09** reconciles route health, producer tokens, orders, fills, positions, algo protection, and
reservations from venue and raw facts. ORIGIN issues no venue query and performs no reconciliation
join (`CLAUDE.md`); it consumes the authoritative result and verifies its own facts (e.g. the
authority-fact ledger, [`split_brain.md`](split_brain.md)).

## Trigger

- Any time authority is about to be restored after a rollback, incident, or DR restore.
- **`PRIVATE_STATE_STALE`** — order, position, or protection truth exceeds the declared freshness
  bound (`private_state_max_age_ms=5000`).
- **`UNKNOWN_SUBMIT_UNRECONCILED`** — a venue submit has unknown effect and cannot be classified until
  reconciliation proves zero venue effect.

## Stop

Reconciliation must complete **before entry** (RC1 §09.6-B, §09.10): reconcile route health, producer
tokens, orders, fills, positions, algo protection, and reservations from venue + raw facts. The RC4
containment holds the levers OFF while state is stale:

- `PRIVATE_STATE_STALE` → `venue_activation=OFF; shadow_activation=LIVE`.
- `UNKNOWN_SUBMIT_UNRECONCILED` → `venue_activation=OFF; shadow_activation=LIVE` until private-state
  reconciliation proves zero venue effect (only then may the record use the SHADOW disposition
  `PROVEN_NO_VENUE_EFFECT`).

## Rollback

The reconciliation sequence within a rollback (RC1 §09.7): release the E08 reservation **only after**
the order's absence/terminal state is authoritative (case 3); reconcile the venue position to zero,
cancel orphan orders/protection, and release the reservation **exactly once** (case 4). Only after a
flat/terminal proof may control authority be restored — never on an ambiguous position (the forbidden
dual-ownership shortcut).

## Evidence

The reconciliation receipt; account truth rebuilt from venue **plus** ledger; the private-stream query
results by client/economic ID. In DR, reconciliation precedes any entry (RC1 §09.10 restore order).
Fingerprints, never credentials.

## Escalation

Position/fill/order unresolved beyond bound and stale-producer/two-writers are Severity 1 (RC1 §09.8)
→ page Security/Risk/Execution. E09 owns the reconciliation; ORIGIN files a boundary note and never a
money-line action.
