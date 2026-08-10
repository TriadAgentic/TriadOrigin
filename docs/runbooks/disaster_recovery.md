# Disaster-recovery runbook

- **Runbook-ID:** `RB-DISASTER-RECOVERY`
- **Scope:** ORIGIN-OWNED (the checkpoint/replay restore leg) · ESTATE-BOUNDARY (E09 account-truth restore).
- **Activation posture:** `DENIED_SAFE_HOLD` — baseline `venue_environment=OFF / venue_activation=OFF / paper_activation=OFF / shadow_activation=LIVE`. Restore ends with **all candidates in `READY_NO_AUTHORITY`**; DR restores state, never authority.
- **Sources:** RC1 §09.10 (protected artifacts, restore order, DR proof); the checkpoint law (`CLAUDE.md`, `CHECKPOINTS.md`).

Disaster recovery restores sealed state into isolation and brings the system back to a **fail-closed,
no-authority** posture. It never restores an active lease as active, and it invents no timing numbers.

## Owner

- **ORIGIN** owns its restore leg: verify sealed checkpoint hashes into isolation, restore the ORIGIN
  checkpoint + replay suffix, and compare the checksum. Candidates come back in `READY_NO_AUTHORITY`.
- **E09** restores account truth from venue + ledger; **E00/E01** rebuild canonical state; **E07/E08**
  restore projections/reservations. The money-line legs are estate-owned.

## Trigger

Loss or corruption of a protected artifact, or a systemic defect (rollback Case 5) requiring a restore
from sealed state.

## Stop

The **restore order** is fixed (RC1 §09.10) and must not be reordered:

1. Verify sealed segment/checkpoint hashes and restore into an **isolated** environment.
2. Restore contract/config/control-plane state; **do not restore active leases as active**.
3. Restore E09 account truth from venue plus ledger; **reconcile before entry**
   ([`reconciliation.md`](reconciliation.md)).
4. Restore E00/E01 and rebuild canonical state to the current watermark.
5. Restore the ORIGIN checkpoint + replay suffix and compare the checksum.
6. Restore E07/E08 projections/reservations; **unresolved money state remains fail-closed**.
7. **Start all candidates in `READY_NO_AUTHORITY`**; issue fresh higher fencing tokens only after
   full readiness.

## Rollback

DR is itself the recovery path; its own failure modes route back through the case matrix
([`rollback.md`](rollback.md)). Nothing leaves the fail-closed posture until the restore order
completes: no active lease is restored as active, unresolved money state stays fail-closed, and no
authority is issued before full readiness.

## Evidence

The **protected-artifact set** (RC1 §09.10): raw ledgers; contract/config/activation/rollback
manifests; the producer-lease log; money journals; ORIGIN journals/checkpoints; instrument/fee
revisions; the trial registry; receipts; audit/incident records. The sealed-hash verification and the
checkpoint checksum comparison are the restore evidence. Fingerprints, never credentials.

## Escalation

**`BLOCKING_OWNER_DECISION`** — the DR `RPO` and `RTO` values, and the DR-proof cadence, are **TBD and
require owner ratification**; **no invented numbers appear here** (RC1 §09.10). These stay named,
fail-closed data with a named abstention until the operator ratifies them; a DR execution against real
account truth is an estate act with its own go/no-go and independent sign-off. ORIGIN flags loudly and
never issues authority during recovery.
