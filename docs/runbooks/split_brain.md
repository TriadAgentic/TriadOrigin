# Split-brain runbook

- **Runbook-ID:** `RB-SPLIT-BRAIN`
- **Scope:** ORIGIN-OWNED (verify-only authority-fact latch). Enforcement of "stop new entries" is E07/E08/E09 (they consume the fact).
- **Activation posture:** `DENIED_SAFE_HOLD` — baseline `venue_environment=OFF / venue_activation=OFF / paper_activation=OFF / shadow_activation=LIVE`. The latch never issues a candidate or order verb; it is fencing-token bookkeeping only.
- **Sources:** RC3 W09 mandatory edge behavior (*"Stale/duplicate/wildcard token rejects; split brain stops new entries"*); `src/triad_origin/control/authority_fact_verifier.py` (`AuthorityLedger`); RC4 `PRODUCER_LEASE_CONFLICT`; RC1 §09.8 (*"Stale producer accepted / two writers"*, Severity 1); open-question **E26** (the four W09 reading judgments).

Split-brain is the one condition a fencing scheme cannot arbitrate: **two issuers presenting
different content under one equal token**, with no higher-token tiebreak. ORIGIN's role is a
**verify-only latch** — it records the fact and refuses further facts for the scope; it stops no
order itself, because it holds no order verb.

## Owner

ORIGIN owns the verify-only ledger `AuthorityLedger` in
`src/triad_origin/control/authority_fact_verifier.py`, whose entire write surface is
`admit_fact` / `current_for_scope` / `is_split_brain` / `clear_split_brain` / `readiness` — no
candidate, order, cancel, or lease-issue verb exists on it (`CLAUDE.md`: ORIGIN adds no lease
issuer). **Enforcement of "split brain stops new entries" is E07/E08/E09**, which consume the fact.
`readiness()` reports the one fact ORIGIN does not own — `producer_attestation` — as the named
string `NOT_OWNED_HERE`, never silently assumed true.

## Trigger

- **The split-brain trigger is a *disagreeing* same-token duplicate** (open-question E26(c)): two
  facts carrying the same `fencing_token` but different content. `admit_fact` latches at exactly that
  event (`REFUSED_SPLIT_BRAIN_ACTIVE`).
- A **byte-identical redelivery is a no-op**, not a trigger (E26(b)) — it is a retransmission of the
  same fact, not a competing claim.
- **Wildcard** is read as wildcard *scope*, not token (E26(a)): `fencing_token` is schema-constrained
  to `^(0|[1-9][0-9]*)$`, so a token cannot carry `*`; an empty scope or a literal `*` scope refuses
  as `WILDCARD_SCOPE`.
- The estate-level shape is RC4 `PRODUCER_LEASE_CONFLICT` (*more than one non-OFF producer claims an
  overlapping scope*; `producer_lease_ttl_ms=15000`, renew `5000`) and RC1 §09.8's *"Stale producer
  accepted / two writers"*.

## Stop

On the latch, `admit_fact` refuses **all** further facts for that scope until it is cleared; the
ledger's `current_for_scope` still reports the last accepted fact for reconciliation. The estate
containment is the RC4 `PRODUCER_LEASE_CONFLICT` `minimum_action`:
`venue_activation=OFF; paper_activation=OFF for the affected scope; shadow_activation=LIVE until
current proof converges`. RC1 §09.8 adds: *revoke all affected leases; stop consumers' entry
acceptance; reconcile*. An **inactive** high-token fact never wrongly out-stales a later active,
lower-token fact — currency is checked (`REFUSED_NOT_CURRENTLY_VALID`) before any ledger ordering.

## Rollback

The scope is held OFF (SHADOW stays LIVE), all affected leases are revoked, and the conflict is
reconciled against venue/raw facts ([`reconciliation.md`](reconciliation.md)) before any authority is
restored. Restoring authority follows the [`rollback.md`](rollback.md) case matching the live state
(typically Case 3/4 if an order or position exists). A new writer acquires the scope only after the
prior token is revoked/fenced (the *one-writer* principle).

## Evidence

`clear_split_brain(scope, *, proof=...)` requires an explicit `proof` string — bookkeeping that
records *why* the latch is released, never itself a candidate/order verb. `admit_fact` returns an
`AdmissionResult` carrying the refusal reason (`REFUSED_STALE` / `REFUSED_DUPLICATE_TOKEN_CONFLICT` /
`REFUSED_SPLIT_BRAIN_ACTIVE` / `REFUSED_NOT_CURRENTLY_VALID`). The producer-lease log and the
reconciliation receipt are the estate-side evidence. Append-only.

## Escalation

Severity 1 (RC1 §09.8, *two writers*): page Security/Risk/Execution; revoke all affected leases and
stop consumers' entry acceptance immediately. The `clear_split_brain` release is gated on the
reconciliation proof and, per the RACI, independent sign-off before any producer re-acquires the
scope.
