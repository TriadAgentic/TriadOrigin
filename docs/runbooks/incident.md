# Incident runbook

- **Runbook-ID:** `RB-INCIDENT`
- **Scope:** ESTATE command flow; ORIGIN participates as an evidence producer. Money-line containment (revoke authority, preserve exits) is E08/E09.
- **Activation posture:** `DENIED_SAFE_HOLD` — baseline `venue_environment=OFF / venue_activation=OFF / paper_activation=OFF / shadow_activation=LIVE`. Incident response contains and reduces; it never re-arms a lever.
- **Sources:** RC1 §09.9 (incident command flow); RC1 §09.8 (the Sev-1/2 stop rows that raise an incident).

An incident is the disciplined path from an automatic guard's immutable trigger back to a known,
protected state. The flow is fixed and ordered; ORIGIN's contribution is honest, append-only
evidence, never a money-line action.

## Owner

Incident command is estate (RACI, RC1 §09.12): a named incident owner drives the flow; Security /
Risk / Execution / Architecture hold the sign-off gates. ORIGIN produces evidence — checkpoints,
divergence, replay receipts, the authority-fact ledger — and issues no order, cancel, or activation.

## Trigger

An automatic guard emits an **immutable incident trigger** carrying account, scope, and evidence — or
any Severity 1/2 stop condition fires (RC1 §09.8): unauthorized/shadow order; exposure
increase/reversal from an emergency path; unprotected live position past deadline; position/fill/order
unresolved beyond bound; stale producer / two writers; feed-invalid entry; ledger append/fsync
failure; manifest/build/config mismatch; replay/state checksum divergence; budget exhaustion.

## Stop

The nine-step command flow (RC1 §09.9), executed in order:

1. **Detect** — the guard emits the immutable trigger with account/scope/evidence.
2. **Contain** — revoke entry authority and allocation; **preserve exits, protection, and raw
   evidence** (see [`protection.md`](protection.md)).
3. **Establish truth** — reconcile route health, producer tokens, orders, fills, positions, algo
   protection, and reservations from venue/raw facts ([`reconciliation.md`](reconciliation.md)).
4. **Reduce risk** — repair protection or follow the approved emergency reduction policy
   (reduction-only).
5. **Stabilize** — reach a known flat/protected state; seal ledgers and checkpoints.
6. **Recover** — select the last-known-good manifest, validate compatibility, and issue new fenced
   authority **only after go/no-go**.
7. **Analyze** — reconstruct the exact causal timeline from source/receipt/knowledge/dispatch/venue
   clocks; identify the guard/test gap.
8. **Correct** — a new requirement/test/build/trial where the change is semantic; **no in-place
   evidence-window change**.
9. **Review** — independent risk/security/architecture sign-off before any repromotion.

## Rollback

Recovery routes through [`rollback.md`](rollback.md) using the case that matches live state, and only
after a flat/protected proof. A correction that changes semantics registers a new trial and receipt;
an evidence window is never edited in place.

## Evidence

The immutable incident trigger; sealed ledgers/checkpoints at stabilization; the reconstructed causal
timeline. **Manual action is recorded with operator identity, reason, evidence, exact payload/result,
and two-person approval where required. Operators never paste credentials into incident records** —
fingerprints only (RC1 §09.9). Append-only: no losing event or incident fact is deleted.

## Escalation

Severity 1 rows page Security/Risk/Execution immediately; independent risk/security/architecture
sign-off gates repromotion (RC1 §09.9/§09.12). Two-person approval is required where policy demands
it. ORIGIN agents flag loudly and may report that an automatic fired; they never order a disarm.
