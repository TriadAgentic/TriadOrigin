# Protection runbook

- **Runbook-ID:** `RB-PROTECTION`
- **Scope:** ESTATE-BOUNDARY (E09 owns protection/cancel/reduction). ORIGIN documents the invariant and holds no exit verb.
- **Activation posture:** `DENIED_SAFE_HOLD` — baseline `venue_environment=OFF / venue_activation=OFF / paper_activation=OFF / shadow_activation=LIVE`. The invariant this runbook records is that **exit authority survives** every OFF/rollback/degradation.
- **Sources:** RC1 §09.1 (*exit authority survives entry rollback*), §09.7 cases 3/4 (*do not disable protection/cancel/reduction*); RC4 `OFF_TRANSITION_EXPOSURE_REMAINS`; `00_MASTER_PLAN.md` System Law 4.

The single invariant: **a rollback, degradation, or OFF transition never disables protection.**
Cancels, protection, reconciliation, and verified exposure reduction remain available until flat.
This is E09's authority; ORIGIN records the boundary and the invariant it must never violate.

## Owner

**E09** owns protection, cancel, and reduction (System Law 4) and retains that authority through
every entry rollback (RC1 §09.7 case 3: *E09 retains cancel/reconcile authority*). ORIGIN issues no
protection, cancel, or reduction verb (`CLAUDE.md`); it documents that no ORIGIN action removes them.

## Trigger

- Any rollback with an open/unknown order (case 3) or an open/partial position (case 4).
- A SHADOW/PAPER degradation forcing a scope OFF while exposure remains.
- **`OFF_TRANSITION_EXPOSURE_REMAINS`** — `venue_environment=OFF` was requested while positions,
  orders, reservations, or the protection lifecycle remain.
- An **unprotected live position past deadline** (RC1 §09.8, Severity 1).

## Stop

- **Do not disable protection/cancel/reduction** (RC1 §09.7 cases 3/4) — the load-bearing prohibition.
- `OFF_TRANSITION_EXPOSURE_REMAINS` `minimum_action`: `venue_activation=OFF; paper_activation
  unchanged; shadow_activation=LIVE` — new entry is stopped while **protection and verified reduction
  stay available until flat**.
- An unprotected live position past deadline: freeze entries; invoke the emergency (reduction-only)
  policy; reconcile; roll back.

## Rollback

Exit authority survives entry rollback. Assign one explicit campaign owner (normally E09 under the
originating authorization/policy) until flat; follow the normal maker exit while safe; invoke the
governed emergency exit only if protection/urgency thresholds require, and only as **reduction-only**.
Reconcile the venue position to zero, cancel orphan orders/protection, and release the reservation
exactly once ([`reconciliation.md`](reconciliation.md)). Only after a flat proof may legacy/control
authority be restored.

## Evidence

Protection-coverage verification (position, regular/algo orders, protection coverage, risk
reservation, account stream); exposure-reduction receipts; the flat proof. Evidence is append-only; a
rollback deletes no losing event. Fingerprints, never credentials.

## Escalation

Unprotected live position past deadline, and exposure increase/reversal from an emergency path, are
Severity 1 (RC1 §09.8) → page Security/Risk/Execution, maintain protective reduction, reconcile, raise
an incident ([`incident.md`](incident.md)). E09 owns protection; ORIGIN flags loudly and never
disables an exit.
