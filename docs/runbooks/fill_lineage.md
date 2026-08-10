# Fill-lineage runbook

- **Runbook-ID:** `RB-FILL-LINEAGE`
- **Scope:** ESTATE-BOUNDARY (E09 owns order/fill/position facts; E10 derives outcomes). ORIGIN is **consume/verify-only** and produces no fill or lineage logic.
- **Activation posture:** `DENIED_SAFE_HOLD` — baseline `venue_environment=OFF / venue_activation=OFF / paper_activation=OFF / shadow_activation=LIVE`. No dual-publish scope is selected under this baseline; this runbook records the boundary and the F23 catalog pairing.
- **Sources:** RC1 §09.5-M5 (strict money-lineage dual-publish); `00_MASTER_PLAN.md` System Laws 4/5 (E09 owns fills/positions; E10 never fabricates missing P&L); `CLAUDE.md` (ORIGIN adds no venue client or fill parser); the F23 catalog (`docs/control/formula_catalog.v1.json`).

Fill-lineage is the strict, gap-free binding of every fill to its account/position/protection/outcome
facts. It is **money-line territory** owned by E09/E10. ORIGIN emits **contract shapes and golden
vectors only** (the F23 catalog) and consumes/verifies at the boundary; it parses no fill and joins no
lineage.

## Owner

- **E09** compiles venue commands and owns order/fill/position facts (System Law 4).
- **E10** derives outcomes from strict money lineage and **never fabricates missing P&L** (System
  Law 5).
- **ORIGIN** owns only the **F23 catalog** — the outcome/P&L/cost/R/markout contract and golden
  vectors — and marks the owning implementation **ESTATE**. ORIGIN builds/imports no fill parser
  (`CLAUDE.md`).

## Trigger

The M5 stage: strict money-lineage **dual-publish** for a selected, already-safe scope — `fill.v1/v2/
v3` plus `v2` account/position/protection/outcome (RC1 §09.5-M5). Under `DENIED_SAFE_HOLD` no scope is
selected, so the trigger is documentary here.

## Stop

- The exit gate is **100% strict-join coverage** for the selected scope; **unresolved rows are
  quarantined** (RC1 §09.5-M5).
- **`UNKNOWN_SUBMIT_UNRECONCILED`** — a venue submit with unknown effect cannot be classified as
  rejected or routed to SHADOW until private-state reconciliation proves zero venue effect
  (`minimum_action`: `venue_activation=OFF; shadow_activation=LIVE`).
- **`SHADOW_MONEY_CONTAMINATION`** — a money metric may never combine shadow and venue populations;
  fills are venue-population facts.

## Rollback

Unresolved money state stays **fail-closed** — E10 never fabricates the missing P&L; the row stays
quarantined until authoritative reconciliation ([`reconciliation.md`](reconciliation.md)) resolves it.
ORIGIN documents this boundary and takes no money-line action; a rollback of authority follows
[`rollback.md`](rollback.md) (E09-executed).

## Evidence

`fill.v1/v2/v3` and the `v2` account/position/protection/outcome records; the strict-join coverage
receipt (100% for the selected scope); the quarantine ledger for unresolved rows. On the ORIGIN side,
the **F23 catalog** contract + golden vectors, referenced against the already-committed
`contracts/schemas/` set (owning implementation marked ESTATE). Fingerprints, never credentials.

## Escalation

Position/fill/order unresolved beyond bound is Severity 1 (RC1 §09.8) → freeze the affected
account/symbol, retain exits, roll back if canary. The lineage owners are E09/E10; ORIGIN files a
boundary note and never a money-line change.
