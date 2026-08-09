# ADR-005 Supersession — the RC4 four-plane/lever law, prepared for owner signature

_B05 disposition (register row A2). Status: **UNSIGNED — prepared for owner signature only.**
This document is a governance artifact, not a gate pass, and arms nothing by its own existence.
Per RC4 task `LEV-0001` ("Issue a signed ADR superseding ADR-005 and ratifying the two exact
lever enums") and the B05 milestone deliverable ("ADR-005 supersession artifact prepared for
owner signature. No non-OFF activation is possible without the signed ADR and gate receipt."),
this document is that artifact. The controlling activation result remains `DENIED_SAFE_HOLD`;
the required non-authoritative baseline manifest stays `venue_environment=OFF /
venue_activation=OFF / paper_activation=OFF / shadow_activation=LIVE` until an operator signs
below **and** the four-plane substrate's own gate receipt (this milestone's `evidence/receipts/
B05.json`) passes.

## Why a supersession

ADR-005 is a prior architecture decision record — not vendored in this repository's tree —
whose content the RC4 Four-Plane/Lever Master Addendum (`docs/spec_rc4/
TRIAD_ORIGIN_V7_FOUR_PLANE_EXECUTION_AND_LEVER_MASTER_ADDENDUM_1.0.0_RC4.html`,
`docs/control/rc4_control_bundle.json`'s `supersessions` array) records verbatim as:

> **ADR-005 (superseded text):** "Forbids testnet and declares LIVE-only production."

The 2026-08-09 owner build directive (`OWNER-DIRECTIVE-2026-08-09`, `LEV-0001`'s `depends_on`)
adopted the RC4 addendum, which requires a canonical, physically isolated `TESTNET` venue
environment as one of the four populations. That directly contradicts ADR-005's literal text, so
RC4 supersedes it explicitly, in-record, rather than silently overriding it:

> **RC4 replacement (ratified here, pending signature):** "Superseded: `venue_environment` is
> `LIVE|TESTNET|OFF`. PAPER is a distinct demo plane; SHADOW is the mandatory rejected-candidate
> plane; neither is TESTNET."

This repository's own `CLAUDE.md` authority order already names this precisely: "RC4 addendum
law (four-plane/lever; supersedes ADR-005 **within its scope**)" ranks above the RC3 master
document. **Scope is the operative word** — this supersession is TriadOrigin-local. Register row
E1 records the boundary explicitly: *"RC4 wins (later owner directive): TESTNET is a canonical
isolated venue environment; sibling-repo estate rules untouched."* Nothing here amends,
contradicts, or is binding on any sibling repository's own "no testnet, ever" doctrine (e.g.
TriadExecutor's BOTTOM-LINE VENUE RULE) — those repositories are not consulted, altered, or
overridden by this document; the supersession is scoped strictly to what this repository's own
`engine_control_manifest.v2` lever law governs.

## The two exact lever enums ratified (LEV-0001)

RC4 replaces the free-form "mode"/"environment" strings ADR-005-era config accepted with exactly
two closed enums, case-sensitive, no aliases, no coercion (`lever_law.py`
`ACTIVATION_ENUM`/`VENUE_ENVIRONMENT_ENUM`, drift-locked to `docs/control/rc4_control_bundle.json`
`lever_law.activation_enum`/`lever_law.venue_environment_enum`):

| Enum | Values | Governs |
|---|---|---|
| `activation_enum` | `LIVE`, `OFF` | `venue_activation`, `paper_activation`, `shadow_activation` (fixed at `LIVE`), and every per-component/feature entry in the `activations` map |
| `venue_environment_enum` | `LIVE`, `TESTNET`, `OFF` | `venue_environment` — the one field this ADR supersession admits `TESTNET` into |

Any other value — the 35-member `INVALID_ALIASES` set (`"live"`, `"1"`, `"DARK"`, `"PRODUCTION"`,
`""`, `"null"`, …) — is refused by name (`VENUE_ENVIRONMENT_VALUE_INVALID` /
`VENUE_ACTIVATION_VALUE_INVALID` / `PAPER_ACTIVATION_VALUE_INVALID` /
`LEGACY_LEVER_ALIAS_FORBIDDEN`), never coerced, trimmed, or silently normalized.

## Companion supersessions carried in the same signed record

RC4's `LEV-0001` acceptance criterion ("exact implemented bytes/config and a falsifiable test
demonstrate this instruction for every registered engine and scope; no open P0/P1 mismatch
remains") reaches nine further ADR/decision-register entries the four-plane law also retires or
narrows, recorded verbatim from `docs/control/rc4_control_bundle.json` `supersessions[]`:

| Superseded record | Old text | RC4 replacement |
|---|---|---|
| `DEP-010` / `CHK-0310` / `SCP-0310` / `V-SCP-0310` | Retire testnet with paper/dry-run | Retire aliases; retain a physically isolated canonical TESTNET path |
| `GAP-006` / `V-GAP-006` | Reject testnet globally | Reject only environment mismatch or mixed bundle; certify LIVE and TESTNET separately |
| `SEC-015` / `CHK-0216` / `SCP-0216` / `V-SCP-0216` | LIVE-only canary/account cell | Require exact environment-account-route-credential binding for LIVE and TESTNET |
| `F20` | `activation_mode` selects CANARY or PRODUCTION budget | Remove branch; pass one already-selected signed risk-budget policy — rollout metadata cannot reach sizing |
| `C-027 activation_manifest.v1` | Mode not closed | Replace with `engine_control_manifest.v2` and exact enums |
| RC2 receipt schemas | `environment`/`modes` accept arbitrary strings | Replace with strict v2 schemas and semantic combination validation |
| `W06` and `G5` | connected-dark / prospective-dark terminology | Use explicit `venue_environment`/`venue_activation`, PAPER activation, and fixed SHADOW activation `LIVE` |
| `PAR-170` / `FPB-0078` | `OFI_NORMALIZED_VARIANT_ENABLED=false` | Rename to `OFI_NORMALIZED_VARIANT_ACTIVATION=OFF`; preserve its separate ratification state |
| MCP `*_family_enabled` booleans | true/false and dark/live tool exposure | Historical raw evidence only; target family activation accepts `LIVE`\|`OFF` |

Every row above is a **narrowing or a naming correction**, never an authority grant: no row in
this table, on its own or in combination, makes any non-`OFF` venue/PAPER activation possible —
that still requires this ADR's signature, a passing `engine_control_manifest.v2` (this
milestone's semantic law, `src/triad_origin/control/lever_law.py::resolve_manifest`), a current
runtime attestation, and the B05 gate receipt, all four together.

## What remains untouched

- **`shadow_activation` stays permanently `LIVE`** and user-unswitchable (RC4's own ratification,
  `LEV-0002`) — this ADR does not, and cannot, touch that.
- **No sibling repository's venue doctrine is amended.** This is a TriadOrigin-local governance
  record.
- **No non-OFF activation exists today.** Signing this ADR ratifies the *lever vocabulary and
  supersession record*; it does not itself flip `venue_activation` or `paper_activation` to
  `LIVE` for any scope — that is a separate, later, per-scope `engine_control_manifest.v2`
  ceremony gated on this signature plus the B05 gate receipt plus a current runtime attestation.

## Signature

Prepared by the B05 build session; enforced in code by
`src/triad_origin/control/lever_law.py` (drift-locked to `docs/control/rc4_control_bundle.json`
by `tests/control/test_lever_law.py`). Sealed alongside `evidence/receipts/B05.json`.

Operator countersignature line (to be added by the operator at ratification time — until signed,
this ADR remains a prepared draft and the baseline manifest stays `OFF/OFF/OFF/LIVE`):

```
COUNTERSIGNED: ________________  date: ____________
```
