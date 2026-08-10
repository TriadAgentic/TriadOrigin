# Rollback runbook

- **Runbook-ID:** `RB-ROLLBACK`
- **Scope:** REPOSITORY-MECHANISM (git checkpoint reversion, ORIGIN-owned) · ESTATE-BOUNDARY (money-line rollback cases 2–5)
- **Activation posture:** `DENIED_SAFE_HOLD` — baseline `venue_environment=OFF / venue_activation=OFF / paper_activation=OFF / shadow_activation=LIVE`. A rollback never re-arms a lever; it only contains and reverts.
- **Sources:** RC1 §09.7 (five rollback cases + forbidden shortcut), §09.8 (automatic stop & rollback triggers); `CLAUDE.md` checkpoint/rollback law + `CHECKPOINTS.md` ledger.

Rollback has two faces. The **repository mechanism** reverts merged build work; the **money-line
cases** contain live risk. ORIGIN owns the first and Case 1 of the second; the remaining money-line
cases are estate-owned and documented here as the boundary.

## Owner

- The **repository-mechanism** rollback is **ORIGIN-OWNED** and is the `CLAUDE.md` checkpoint law:
  rollback branches **from** a sealed checkpoint (`git checkout -b rollback/<name>
  checkpoint/<...>`), fixes forward, and merges via PR — **`main` is never rewritten**, and no
  checkpoint is ever moved, deleted, or reused. Every merge to `main` is sealed with an estate
  checkpoint recorded in `CHECKPOINTS.md`.
- **Case 1 — dark ORIGIN, no authority** is **ORIGIN-OWNED**.
- **Cases 2–5** (authority issued / open order / open position / post-cutover defect) are
  **ESTATE-OWNED** (E08 reservation release, E09 cancel/reconcile/protection). ORIGIN documents the
  boundary; it issues no order, cancel, or reservation verb.

## Trigger

A rollback is initiated by any automatic stop condition (RC1 §09.8 — twelve Sev-1/2 rows) or by a
defect requiring reversion of merged work. The applicable **case** is chosen by the live state:

1. **Dark ORIGIN, no authority** — no authority/money journal event exists.
2. **Authority issued, no open order or position.**
3. **Open/unknown order, no confirmed position.**
4. **Open or partial position.**
5. **Post-cutover systemic defect.**

## Stop

The load-bearing law is the **forbidden shortcut**: *never reactivate legacy/control while ORIGIN
orders, positions, protection, or reservations are ambiguous* (dual ownership). Each case stops at
its own truth boundary:

- **Case 1** — stop ORIGIN input/process; seal checkpoint/output/divergence evidence; confirm no
  authority/money journal event exists; the legacy/control path is unchanged; diagnose offline.
- **Case 2** — set allocation to zero and revoke the ORIGIN candidate lease; prove consumers reject
  the token; reconcile zero orders/positions/reservations for scope.
- **Case 3** — disable new ORIGIN entries and revoke candidate authority (E09 retains cancel/
  reconcile authority); query the private stream and the venue by client/economic ID (never blindly
  resubmit or assume absent); release the E08 reservation only after the order's absence/terminal
  state is authoritative.
- **Case 4** — disable new entries and fence ORIGIN candidate authority; **do not disable
  protection/cancel/reduction** (see [`protection.md`](protection.md)); reconcile the venue position
  to zero, cancel orphan orders/protection, release the reservation exactly once.
- **Case 5** — treat as an incident ([`incident.md`](incident.md)).

Under RC4, a rollback that requests `venue_environment=OFF` while exposure remains is
`OFF_TRANSITION_EXPOSURE_REMAINS` → `venue_activation=OFF; shadow_activation=LIVE` while
protection/reduction stay available until flat.

## Rollback

The reversion action itself: for the repository, branch **from** the last-good checkpoint and fix
forward (never rewrite `main`); for the money line, reach a **flat proof** for the scope before any
legacy/control token is restored, and only then issue a strictly higher legacy/control token under
the last-known-good manifest. A rollback contains risk first and diagnoses second.

## Evidence

Every rollback records a rollback event and **preserves ORIGIN evidence** (append-only — no losing
event, failed trial, or incident fact is deleted). The checkpoint ledger (`CHECKPOINTS.md`) is the
tamper-evidence for the repository mechanism; the money-line cases require an authoritative flat/
terminal-state proof before restore. Fingerprints, never credentials.

## Escalation

Sev-1 stop rows (unauthorized/shadow order; exposure increase/reversal; unprotected position past
deadline; position/fill/order unresolved; stale producer/two writers; feed-invalid entry; ledger
append/fsync failure; manifest/build/config mismatch; replay/state checksum divergence) page
Security/Risk/Execution. Independent risk/security/architecture sign-off gates any repromotion.
