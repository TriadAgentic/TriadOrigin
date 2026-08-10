# PAPER isolation runbook

- **Runbook-ID:** `RB-PAPER-ISOLATION`
- **Scope:** ORIGIN-OWNED (the keyless PAPER executor is part of the B05 four-plane minimum).
- **Activation posture:** `DENIED_SAFE_HOLD` — baseline `venue_environment=OFF / venue_activation=OFF / paper_activation=OFF / shadow_activation=LIVE`. PAPER is a **measurement lane, never real money**; a contamination forces `paper_activation=OFF` for the affected scope.
- **Sources:** RC4 `four_plane_law.paper` (`population=PAPER`, `real_money=false`, `venue_authority=false`, `demo_account=true`, `live_market_data=true`, `activation_enum=[LIVE,OFF]`); `paper_substitutes_for_testnet=false`; the two PAPER refusals with their `minimum_action`; `00_MASTER_PLAN.md` §8 (physical population separation).

PAPER records accepted candidates against a **demo account with live market data and no real
money** — a keyless, venue-authority-free execution copy. Its whole safety case is **isolation**:
a PAPER record can never reach a venue effect, and PAPER facts never mix into money denominators.
PAPER does **not** substitute for TESTNET (`paper_substitutes_for_testnet=false`).

## Owner

ORIGIN owns the keyless PAPER executor and its separate virtual order/fill/position/outcome ledger.
The isolation is proven two ways: **static** — an import scan shows no venue adapter and no
credential import path on the PAPER code; **runtime** — a proof that no PAPER command reaches a venue
effect. Physical identity/storage/query/aggregate separation holds across SHADOW / PAPER / TESTNET /
LIVE populations. ORIGIN holds no credentials for PAPER (`venue_authority=false`).

## Trigger

- **`PAPER_VENUE_EFFECT_FORBIDDEN`** — a PAPER record, credential, route, or command *can* reach a
  venue effect (an isolation breach).
- **`PAPER_LEDGER_CONTAMINATION`** — PAPER demo facts were combined with SHADOW, TESTNET, or LIVE
  outcome/PnL denominators (a population-mixing breach).

## Stop

The RC4 `minimum_action` per class:

- `PAPER_VENUE_EFFECT_FORBIDDEN` → `venue_activation=OFF; paper_activation=OFF for the affected scope;
  shadow_activation=LIVE; quarantine the invalid evidence`.
- `PAPER_LEDGER_CONTAMINATION` → *reject the aggregation; `paper_activation=OFF` for the affected
  scope pending repair; `shadow_activation=LIVE`.*

The isolation walls fail **closed**: a proven or provable venue-reach stops PAPER for the scope
rather than trusting that the reach was benign.

## Rollback

Repair the isolation before PAPER returns to `LIVE` (an operator/estate activation, never authorized
by this runbook): restore the venue/credential import ban (static + runtime proof), and re-establish
physical population separation so no denominator crosses SHADOW/PAPER/TESTNET/LIVE. Baseline
`paper_activation=OFF` is the safe resting state; SHADOW stays LIVE throughout.

## Evidence

The static import-scan proof (no venue adapter / no credential path); the runtime no-venue-effect
proof; the separate PAPER ledger identity; the population-separation proof that PAPER facts carry no
SHADOW/TESTNET/LIVE denominator. Fingerprints, never credentials — PAPER holds none.

## Escalation

A proven venue-reach from a PAPER record is an incident ([`incident.md`](incident.md)) and pages
Risk/Execution. A ledger-contamination finding blocks any aggregate that would report a PAPER-mixed
metric until repaired. ORIGIN flags loudly; it never re-activates PAPER on its own.
