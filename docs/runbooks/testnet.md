# TESTNET runbook

- **Runbook-ID:** `RB-TESTNET`
- **Scope:** ESTATE-BOUNDARY. TESTNET carries `venue_path: true`, so it runs the same E09 venue lifecycle as LIVE and is **estate-owned**.
- **ORIGIN-operation:** **REFUSED.** ORIGIN never operates, activates, promotes, or routes TESTNET. This runbook is **not a how-to-enable procedure and not a retirement notice** — it records the promotion-gate law and ORIGIN's refusal to operate it.
- **Activation posture:** `DENIED_SAFE_HOLD` — baseline `venue_environment=OFF / venue_activation=OFF / paper_activation=OFF / shadow_activation=LIVE`. No ORIGIN machine represents a non-OFF activation without the signed ADR-005 supersession (currently UNSIGNED) and its gate receipt.
- **Sources:** RC4 `lever_law` (`venue_environment_enum=[LIVE,TESTNET,OFF]`; `case_sensitive=true`, `aliases=false`, `coercion=false`, `trim_input=false`) and `four_plane_law.testnet` (`population=TESTNET`, `real_money=false`, `venue_path=true`); `live_requires_testnet_promotion_receipt=true`; the TESTNET/LIVE binding refusals; open-question **E1** (`DEFAULT_IN_FORCE`); `docs/governance/ADR-005-SUPERSESSION.md`.

**Framing (read this first).** For *this* estate, RC4 makes TESTNET a **canonical isolated venue
environment**, not a forbidden one. The sibling money-line estate's *"no testnet ever / LIVE-only"*
rule (ADR-005 / the sibling `BOTTOM-LINE VENUE RULE`) is a **different estate's law**, superseded
here by RC4 (open-question **E1**, `DEFAULT_IN_FORCE`; `ADR-005-SUPERSESSION.md`), and its
repositories are left untouched. Because TESTNET carries `venue_path: true`, it is estate-owned and
**ORIGIN never operates it**; this runbook is the boundary and the promotion-gate law only.

## Owner

The TESTNET environment — endpoints, accounts, credentials, order/fill lifecycle — is **ESTATE-OWNED
(E09)**. ORIGIN builds and imports no venue client, credential loader, or order verb (`CLAUDE.md`), so
it cannot and does not operate TESTNET. Its role is to **account for** the promotion-gate law and to
**refuse** any request to operate the environment.

## Trigger

A request to promote a build toward LIVE through TESTNET (an estate act). ORIGIN's response is the
refusal above; the estate's own gate law governs whether the promotion is admissible.

## Stop

The RC4 refusals that bound TESTNET (each `minimum_action` keeps `venue_activation=OFF` /
`shadow_activation=LIVE`):

- **`LIVE_PROMOTION_RECEIPT_MISSING`** — LIVE requires a *current successful TESTNET promotion
  receipt for the same build, contracts, strategy, scope, and venue lifecycle*
  (`live_requires_testnet_promotion_receipt=true`; Track B *"TESTNET · same-digest venue certificate —
  TESTNET must pass before LIVE"*).
- **`DIRECT_ENVIRONMENT_TRANSITION_FORBIDDEN`** — a LIVE↔TESTNET transition must pass through OFF
  activation, reconciliation, flatness, isolation, and OFF environment; it is never a toggle.
- **`MIXED_ENVIRONMENT_BUNDLE_FORBIDDEN`** / **`TESTNET_LIVE_BINDING_FORBIDDEN`** /
  **`LIVE_TESTNET_BINDING_FORBIDDEN`** — one bundle may not mix LIVE and TESTNET members, and neither
  environment's record may contain the other's endpoint/account/credential/order/fill/ledger/route.
- **`OPPOSITE_ENVIRONMENT_REACHABLE`** — an engine instance able to reach both LIVE and TESTNET
  authority surfaces is refused.
- **`LEGACY_LEVER_ALIAS_FORBIDDEN`** — the lever slot is case-sensitive with no aliases, coercion, or
  trimming; the lowercase `"testnet"` and every other legacy word/boolean/integer/blank are refused
  (only the exact enum member is a value). `SCOPE_VALUE_INVALID` refuses a wildcard/inexact scope.

Under `DENIED_SAFE_HOLD` the baseline is `venue_environment=OFF`; no non-OFF value — LIVE or TESTNET —
is representable without the signed ADR and its gate receipt.

## Rollback

A TESTNET↔LIVE (or TESTNET→OFF) change is drained, not switched: through OFF activation,
private-state reconciliation ([`reconciliation.md`](reconciliation.md)), a flatness proof, and
physical isolation — the `DIRECT_ENVIRONMENT_TRANSITION_FORBIDDEN` law. All of that is E09-executed;
ORIGIN records the boundary and holds the levers at the OFF baseline.

## Evidence

The **same-digest TESTNET promotion receipt** (build, contracts, strategy, scope, and venue lifecycle
bound together) is the estate evidence LIVE requires. The signed ADR-005 supersession — the
governance artifact that ratifies the TESTNET enum member — is prepared but UNSIGNED
(`ADR-005-SUPERSESSION.md`), so no non-OFF activation is currently representable. Fingerprints, never
credentials.

## Escalation

Only the **operator** signs a non-OFF activation (the estate ARM/GOV ceremony); ORIGIN agents flag
loudly and hand the boundary, never ordering a promotion. `OPPOSITE_ENVIRONMENT_REACHABLE` and any
LIVE/TESTNET binding cross-contamination page Security/Risk/Execution as Severity 1.
