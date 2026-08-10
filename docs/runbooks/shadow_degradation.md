# SHADOW degradation runbook

- **Runbook-ID:** `RB-SHADOW-DEGRADATION`
- **Scope:** ORIGIN-OWNED (the SHADOW substrate is the B05 four-plane minimum; the health law is ORIGIN's).
- **Activation posture:** `DENIED_SAFE_HOLD` — baseline `venue_environment=OFF / venue_activation=OFF / paper_activation=OFF / shadow_activation=LIVE`. `shadow_activation` is fixed `LIVE`, not switchable — there is **no** setter, environment fallback, or alias; degradation never turns SHADOW off, it forces *execution* off while SHADOW recovers.
- **Sources:** RC4 `shadow_law` (activation `LIVE`, `user_switchable=false`, dispositions, `execution_dependency`); the six SHADOW refusals with their `minimum_action`; `timings` (`shadow_rejection_persist_deadline_ms=100`, `shadow_health_heartbeat_interval_ms=1000`, `shadow_health_max_age_ms=5000`, `shadow_resolver_backlog_max_age_ms=60000`); `00_MASTER_PLAN.md` §8 (SHADOW-before-candidate; health forces OFF).

SHADOW is the always-on measurement plane. Its **execution dependency** is the containment law:
*"venue_activation and paper_activation resolve OFF when mandatory SHADOW persistence/health is
unavailable"* — SHADOW itself stays LIVE, invalid evidence is quarantined, and recovery continues.

## Owner

ORIGIN owns the SHADOW recorder/resolver substrate and the health law. `shadow_activation` cannot be
set OFF by any caller: an attempt is the record-local refusal `SHADOW_CAPTURE_OFF_FORBIDDEN`. SHADOW
capture continues across every venue environment (`shadow_law.continues_for_venue_environments =
[LIVE, TESTNET, OFF]`) and carries no money authority (`money_authority=false`).

## Trigger

Scope-forcing degradations:

- **`SHADOW_HEALTH_STALE`** — the mandatory writer heartbeat or the processable resolver watermark
  exceeds its freshness bound (`heartbeat_interval 1000 ms` / `max_age 5000 ms`; resolver backlog
  `> 60000 ms`).
- **`SHADOW_REJECTION_NOT_PERSISTED`** — a shadow-tradeable REJECTED candidate was not durably
  persisted to the SHADOW recorder inside the `100 ms` deadline.
- **`SHADOW_LINEAGE_INCOMPLETE`** — candidate/rejection/shadow-trade/resolver/outcome lineage is
  missing or ambiguous.
- **`SHADOW_MONEY_CONTAMINATION`** — shadow evidence contains a venue money fact, or a money metric
  combines shadow and venue populations.

Record-local refusals (never a scope change): **`SHADOW_CAPTURE_OFF_FORBIDDEN`** (an attempt to set
capture OFF) and **`SHADOW_UNTRADEABLE`** (an event/candidate fails the tradeability contract — it is
recorded via `shadow_rejection_audit.v1` with no fabricated geometry or trade).

## Stop

The RC4 `minimum_action` per class:

- Scope-forcing (`SHADOW_HEALTH_STALE` / `SHADOW_REJECTION_NOT_PERSISTED` /
  `SHADOW_LINEAGE_INCOMPLETE` / `SHADOW_MONEY_CONTAMINATION`) →
  `venue_activation=OFF; paper_activation=OFF for the affected scope; shadow_activation=LIVE;
  quarantine the invalid evidence`.
- Record-local (`SHADOW_CAPTURE_OFF_FORBIDDEN` / `SHADOW_UNTRADEABLE`) → *reject the requested/invalid
  record; preserve `shadow_activation=LIVE`; do not change a proven-safe execution activation solely
  for this record-local refusal.*

Under `DENIED_SAFE_HOLD` the execution levers are already OFF, so degradation's practical effect is
to **keep** them OFF for the affected scope and quarantine the offending evidence — never to fabricate
a disposition.

## Rollback

There is no "turn SHADOW back on" — it never went off. Recovery: restore the writer heartbeat and the
resolver watermark within their bounds, re-establish complete lineage, and let *current proof
converge* before any scope may later leave OFF (an estate execution gate, not this runbook). The three
lawful ORIGIN dispositions are **`REJECTED`**, **`ACCEPTED_NOT_EXECUTED`**, and
**`PROVEN_NO_VENUE_EFFECT`** — the last only after authoritative private-state reconciliation proves
zero venue effect ([`reconciliation.md`](reconciliation.md)).

## Evidence

`shadow_rejection_audit.v1` for every untradeable input; the writer heartbeat and resolver watermark
readings; the quarantine ledger for invalid evidence. Tradeability requires the full contract
(schema-valid, semantically valid, resolved instrument, side, entry policy, invalidation,
target/terminal rule, horizon, finite numbers, monotonic clocks, stable identity, causal market
watermark). No fabricated trade or geometry, ever. Append-only.

## Escalation

A persistent health/persist/lineage degradation is an incident ([`incident.md`](incident.md)); RC1
§09.8 ledger-append/fsync and feed-invalid rows are Severity 1 where they underlie the SHADOW
failure. A `SHADOW_MONEY_CONTAMINATION` finding pages Risk/Execution immediately. ORIGIN flags loudly
and never disarms SHADOW.
