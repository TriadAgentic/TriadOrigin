# B10 · Implementation Report — Audit and Repository Seal

_TriadOrigin E02-V7. HEAD `fe8d106` (branch `b00-b07-review`), 2026-08-10._
_Authority: reconciled plan (`docs/plan/00..10`), RC4 (`docs/control/rc4_control_bundle.json`),
RC3 (`docs/control/rc3_effective_control_bundle.json`), `CLAUDE.md`. No claim here is a gate
receipt; the controlling activation result is and remains `DENIED_SAFE_HOLD`._

This report separates the B10 seal work — and the whole B00→B09 build it seals — into
**BUILT** (landed in-repo), **VERIFIED** (the gate + audits), **BLOCKED** (fail-closed inventory,
never green), **ESTATE** (out-of-repo money line + the G-gate checklist), and **OPERATOR**
(the ceremony acts no agent may take).

---

## 1 · BUILT (landed in this repository)

| Block | What landed | Where |
|---|---|---|
| B00–B07 | Typed identity/contracts/receipts (v2), F00 ingress, journal/checkpoint fences, F02–F19 formula + structure + kernel layers, four-plane substrate (B05), reaction/capsule/candidate publisher (B06), config/comparator/authority-router/legacy-bridge/replay control-plane libraries (B07, `BUILD_DARK_LIBRARY`) | `src/triad_origin/**`, `contracts/**` |
| B0R | **52 confirmed code fixes** across F00–F19 + kernel + control-plane + integrator work (fix-forward-while-dark), landed on `b00-b07-review` (source PR #26) | register row E30; per-domain commits |
| B08 | Read faces / evidence: `read_faces/{envelope,views,faces}.py` — `origin.evidence_view.v2` internal projection envelope + the LEV read faces (engine lever registry / shadow health / inventory reconciliation), honest `NOT_MEASURABLE`/`UNAVAILABLE` per axis | register rows E37/E38; `src/triad_origin/read_faces/**` |
| B09 | Conformance matrix (`docs/control/conformance_matrix.v1.json`, RC1 408 ⊂ RC3 1,523 + RC4 125 = 1,648 rows, **COVERED=0 by design**), F20–F23 estate formula catalog (`formula_catalog.v1.json`, IN_REPO_CATALOG slice + GV-017..020), **eleven** operational runbooks (`docs/runbooks/**`) | register rows E39/E40/E41 |
| Tooling | `tools/e2e_audit.py` (27 walk stages), `tools/{conformance_matrix,build_formula_catalog,build_receipt_v3,ed25519_verify,build_trust_registry,scan_secrets,validate_b_receipt,verify_no_forbidden_capabilities,verify_spec_control_counts,jcs_canonical}.py`, verify_manifest / validate_contract_manifest / build_ledger / validate_combined_dag | `tools/**` |
| B10 (this milestone) | This report; the terminal-state doc (`B10_TERMINAL_STATE.md`); the disposition-register seal rows (E42–E45); the unsigned terminal-receipt scaffold; the two P3 audit dispositions (below) | `docs/reports/**`, `docs/plan/09_OPEN_QUESTIONS.md`, `docs/plan/04_STATUS.md` |

### B10 audit adjudication (this milestone's code touch)

Two independent auditors ran (structural + safety/evidence-integrity). Auditor 1: **CLEAN**.
Auditor 2 raised **two P3** findings; both were re-confirmed against RC4 and both are
**deliberately pinned / mooted** — neither is a P0/P1:

- **P3-1 · lever LIVE/LIVE promotion-receipt honest-null under-enforcement** (`src/triad_origin/control/lever_law.py`).
  CONFIRMED: RC4 `semantic_rules[2]` / `refusals[11]` / `LEV-0042` require a *current successful
  same-digest* TESTNET receipt; `_promotion_receipt_ok` enforces only the honest-null subset (a
  PRESENT non-PASS result / a PRESENT disagreeing digest / a past expiry refuse; an ABSENT result
  or ABSENT digest does not). The behaviour is **pinned by `tests/control/test_lever_law.py` and
  the `e2e_audit.py` lever walk** (`{"receipt_id":"r1"}` is accepted by design), and **mooted by
  `activation_result=DENIED_SAFE_HOLD`** — ORIGIN never activates; the affirmative same-digest
  binding is the operator/estate **G-8/G-9 same-digest TESTNET certificate + production-risk
  signing** (out-of-repo). **Fix applied:** the `_promotion_receipt_ok` docstring overclaim was
  narrowed to state exactly the in-repo honest-null subset and to defer the full binding to
  G-8/G-9 (no behaviour change; lever + scan tests re-run green). Registered: **E43**.
- **P3-2 · scan_secrets pattern-coverage blind spots** (`tools/scan_secrets.py`). CONFIRMED: the
  `secret_assignment` regex omits `api_secret`/`secret`/`credential` and bare high-entropy blobs.
  But `SECRET_PATTERNS` is **verbatim from the frozen runner** (SHA `12c8896…`) and **byte-pinned
  by `tests/tools/test_scan_secrets.py`** — editing it would break frozen-runner provenance and the
  differential test. Keylessness is guaranteed **structurally** by the AST capability boundary
  (`verify_no_forbidden_capabilities.py`), the tree has **0 hits over 464 tracked files**, and the
  repo is keyless by construction (Ed25519 keys are operator-owned/off-tree per E32). **Not changed
  in-repo**; any pattern extension must land in the frozen runner first (operator-owned). Registered:
  **E44**.

Both P3s: NO LIVE IMPACT, no P0/P1 opened, no behaviour changed.

---

## 2 · VERIFIED (the gate + the audits)

- The 14-command CLAUDE.md gate ran green across B00→B09 (both `PYTHONHASHSEED=0` and `=1`
  pytest, `collect_test_ids`, `verify_manifest`, `validate_contract_manifest`,
  `verify_reproducible_build`, `test_wheel_install`, `verify_no_forbidden_capabilities`,
  `e2e_audit` (27 stages), `build_ledger --verify`, `validate_combined_dag`). CI: 18 source +
  3 receipt step names green per merged milestone.
- The B10 code touch (the lever docstring narrowing) is behaviour-neutral: `tests/control/test_lever_law.py`
  + `tests/tools/test_scan_secrets.py` re-run **green** post-edit.
- Two independent B10 auditors reported (structural: CLEAN; safety/evidence-integrity: two P3s,
  both adjudicated above).
- **Running the full gate is the NEXT phase, not this one** (`CLAUDE.md` PR law) — this report does
  not itself claim a fresh gate receipt.

---

## 3 · BLOCKED (fail-closed inventory — never green, by design)

Per the reconciled plan and the register law, every unratified decision stays fail-closed data
with a named abstention — nothing is silently defaulted green:

- **Conformance matrix `COVERED=0`** (E39): no `verification_id → pytest-node` evidence link exists
  yet, so the matrix greens nothing; the 297 direct-blocked rows are independently sound.
- **8 `BLOCKING_OWNER_DECISION`** activation values (`09_OPEN_QUESTIONS.md` §B) — `NOT_RATIFIED`,
  fail-closed DENY.
- **3 `BLOCKING_RESEARCH_DECISION`** (§C) — interfaces + named abstention only.
- **123 × `PROPOSED_RC2_MUST_RATIFY`** parameter bundle (§D) — proposed, never applied.
- **F20 production path** (`PAR-070`, `BLOCKING_OWNER_DECISION`) — fail-closed DENY; F20 is built in
  RC4-corrected form (rollout can never reach sizing, E40).
- **DR RPO/RTO + DR-proof cadence** (E41) — `BLOCKING_OWNER_DECISION`, no invented numbers.

---

## 4 · ESTATE (out-of-repo money line + the G-gate checklist)

ORIGIN is `BUILD_DARK_LIBRARY` / verify-only. The money line is out of this repository:

- **F20–F23** estate formulas: F20 (E08 sizing), F21 (E09 maker), F22 (E09 reduction-only IOC),
  F23 (E10 P&L) — implementations `OUT_OF_REPO`; this repo carries only the IN_REPO_CATALOG shape +
  golden vectors (E40).
- **E07/E08/E09/E10** decision/risk/order/outcome and venue/account truth — `REFERENCE_ONLY` /
  `OUT_OF_REPO` (`CLAUDE.md` repository-ownership law).
- **The estate G-gate checklist** (`08_BUILD_CHECKLIST.md` G-1..G9): credentials/attestation, route
  reverification, E01 certification, the eight owner blockers, the same-digest TESTNET certificate,
  production-risk signing — **entirely operator/estate**, stays `DENIED_SAFE_HOLD`.

---

## 5 · OPERATOR (ceremony acts no agent may take)

- **E31 — the exit-3 terminal.** The frozen runner's `--check-evidence` index is a self-referential
  git-hash fixed point, so a full-PASS `exit 0` is **structurally unreachable**; the only lawful
  non-failing terminal is **exit-3 `BLOCKED_INCOMPLETE`** with every reachable hard gate green + the
  WP checks `NOT_RUN` (index-absent). See `B10_TERMINAL_STATE.md`. The operator either **accepts
  exit-3** as the honest reachable maximum or authorizes a runner-amendment ceremony.
- **E32 — the ceremony operator-asks**: Ed25519 key minting (PRODUCER · COUNTERSIGNER · AUDITOR;
  closes issue #5), default-branch rulesets, the signed offline GitHub DSSE snapshot (two distinct
  signers), the ten per-milestone work-order MDs deployed beside the runner. None is an agent act.
- **The B10 seal ceremony**: merge the B10 source PR green; reproduce the gate against merged `main`;
  land the **detached, signed** B10 terminal receipt (this report ships an **unsigned scaffold** —
  see `B10_receipt_config.DRAFT.json` + `docs/reports/B10_receipt_scaffold.md`); tag + local
  checkpoint referencing the terminal receipt.
- **All G-1..G9 estate gates** stay operator/estate. The handoff line: **`DENIED_SAFE_HOLD` unless
  separate estate gates exist.**

---

## 6 · The honest one-line seal

Every reachable in-repo gate is green and the tree is keyless by construction; the seal's terminal
is exit-3 `BLOCKED_INCOMPLETE` (E31), and every money-facing act beyond the repository — activation,
the same-digest TESTNET certificate, production-risk signing, key minting, branch governance —
remains the operator's, fail-closed at `DENIED_SAFE_HOLD`.
