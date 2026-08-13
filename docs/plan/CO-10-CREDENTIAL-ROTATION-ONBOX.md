# CO-10 — Credential Rotation, On-Box Operator Guide (plan D-09)

**DISPOSITION:** `OWNER-ONLY / PENDING_OWNER_EXECUTION`. Every step in this guide is
**OWNER/BOX-ONLY**: it is executed by the account owner / box operator on the issuing side and
on the box — **never by an agent, never in a repository, never in a session transcript**.
This document is the procedure record only; no step below is claimed executed. Posture
unchanged: `OFF/OFF/OFF/LIVE`, `DENIED_SAFE_HOLD`.

**Order:** `TRIAD-ORIGIN-V7-CHANGE-ORDERS-2026-08-12` CO-10. **Deadline law:** complete before
B05C; no security attestation may issue while any exposed credential is live.

**Why:** operational credentials appeared in supplied operational guides. A credential that
has travelled through a document, chat, transcript, screenshot, or paste buffer is **EXPOSED**
and must be treated as compromised — rotation is mandatory regardless of whether misuse is
observed.

---

## Law 0 — The fingerprint law (inventory-by-fingerprint, never copy values)

- A credential is referenced **only** by fingerprint: `fp = SHA-256(exact credential bytes)`,
  rendered as the first 16 hex characters, computed **on-box** (e.g.
  `printf '%s' "$SECRET" | sha256sum` — from a `read -s` prompt, never from shell history).
- **Never copy a credential value** into an inventory, receipt, ticket, chat, commit, or any
  evidence artifact. The value exists only at the issuing side and in the box's secret store.
- A truncated or reformatted value is still a value. Zero secret bytes in any artifact —
  the estate secret-pattern scan must stay green over every evidence file this order produces.
- If a fingerprint cannot be computed without exposing the value to a shared surface, record
  the credential by issuer + identifier (key ID, token ID) instead — never by value.

## Step 1 — Inventory (OWNER/BOX-ONLY)

Enumerate every credential string present in the supplied operational guides. For each,
record: `{fingerprint (or issuer key-ID), issuer, surface it appeared on, scope/permissions,
status: EXPOSED}`. The inventory artifact carries fingerprints only.

## Step 2 — Rotate/revoke at the ISSUING side (OWNER/BOX-ONLY)

Rotation happens where the credential was minted — revoking a local copy is not rotation.
The issuing-side rotation list:

| Class | Issuing side | Action |
|---|---|---|
| **Venue API keys** (Binance, Hyperliquid; any venue key present in a guide) | Venue account console | Revoke the exposed key; mint the replacement with the narrowest permission set the consuming service actually needs; IP-allowlist where the venue supports it. TriadOrigin holds no venue credential by law — a venue key never enters this repository in any form. |
| **Tunnel tokens** (box ingress/egress tunnels) | Tunnel provider console | Revoke the exposed tunnel token; re-issue; confirm the old tunnel identity no longer connects. |
| **Ops-relay bearer tokens** (the diagnostic/ops relay endpoints) | Relay token issuer | Revoke the exposed bearer tokens. Note: a bearer token is **not** a private boundary (closure-gate 14) — rotation here does not defer the separate hardening/retirement of Internet-reachable bearer endpoints. |
| **Auth0 material** | Auth0 tenant | Per the estate record (TriadAgent AG-§21, superseded 2026-08-03) Auth0 is **NOT in use** — tenant `NOT-APPLICABLE`, client layer dormant. Any Auth0 secret appearing in a guide is rotated/revoked at the tenant anyway (dormant ≠ dead), and its deadness verified. |
| **Anything else found in Step 1** (webhooks, DSNs, bot tokens, SSH material) | Its issuer | Same law: revoke at the issuer, re-issue least-privilege, verify the old one dead. |

## Step 3 — Least-privilege read-only audit identity (OWNER/BOX-ONLY)

Mint **one dedicated audit identity** for runtime census work (the read-side evidence
collection this program needs):

- Scope: **read-only**, enumerated resources only; no write, no order, no config-mutation, no
  key-management permission of any kind.
- Its credential follows Law 0 (fingerprint-only referencing) and is stored only in the box's
  secret store.
- Census/audit tooling authenticates with this identity **exclusively** — never with an
  operational or money-path credential.

## Step 4 — Rotation receipts by fingerprint (OWNER/BOX-ONLY)

For each inventoried credential, record one receipt row:
`{old_fingerprint, issuer, revoked_at (issuer-side timestamp), verified_dead_how,
new_credential: fingerprint-only or NOT_REPLACED, operator}`.

- `verified_dead_how` is a **negative test at the issuer or endpoint** (an authentication
  attempt with the revoked credential fails), not an assumption.
- Receipts carry fingerprints only — a receipt containing a secret value is itself a new
  exposure and restarts this order for that credential.

## Acceptance (verified by the OWNER before B05C)

1. Every Step-1 fingerprint verified **dead** (negative test recorded).
2. The audit identity exists, scoped read-only, and is the only identity census tooling uses.
3. **Zero secret values** in any evidence artifact — the secret-pattern scan stays green.
4. The receipt set covers the full Step-1 inventory (no unrotated EXPOSED row remains).

**Named refusal:** while any Step-1 row lacks a dead-verification receipt, any security
attestation that depends on credential hygiene answers
`BLOCKED_ON_CREDENTIAL_ROTATION(CO-10)` — never a silent pass.
