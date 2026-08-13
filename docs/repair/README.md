# docs/repair — vendored independent repair evidence (NOT ratifications)

This directory holds independent cross-check / repair documents supplied by the account owner,
vendored **verbatim** so they are version-controlled and cross-checkable, plus this repo's honest
disposition of them.

**These documents are EVIDENCE, not authority.** Every one carries its own
`NOT_A_RATIFICATION / NO_RUNTIME_CHANGE` disposition. Vendoring them here changes no formula, no
contract, no owner, and no safety invariant. Posture is unchanged and stays unchanged:
`venue_environment=OFF / venue_activation=OFF / paper_activation=OFF / shadow_activation=LIVE`,
`DENIED_SAFE_HOLD`. A document's *proposal* becomes law only when the account owner signs it under
GOV-01, and a *spec* change lands as a prior additive artifact — never by an agent editing a
formula to match a proposal (repo authority order: "Code never chooses between conflicting
sources").

| File | What it is |
|---|---|
| `TRIAD_ORIGIN_V7_GAP_REGISTER_2026-08-13.md` | Independent 50-gap inventory (`GAP-01…GAP-50`) across the whole estate. `GAP_INVENTORY / EVIDENCE / NOT_A_RATIFICATION`. In force incl. Addendum A, **except `GAP-12` is WITHDRAWN** (see R-01). |
| `TRIAD_REPAIR_WORK_ORDER_2026-08-13.md` | The companion execution-grade work orders (`WO-00…WO-Q`, `WO-A…WO-F`). In force **except its `EXECUTION ORDER` section (superseded by the Master Sequence Part 1) and `WO-H` (WITHDRAWN, identifier retired)**. |
| `TRIAD_REVISION_RECORD_R-01_2026-08-13.md` | **Correction record.** Formally **WITHDRAWS ERR-02 / GAP-12 / WO-H as reviewer error** (the code was right; the developer's refusal is validated on every count), marks ERR-01 CLOSED and ERR-03 OWNER_GATED, introduces standing **LAW-9**, and reroutes ownership. `CORRECTION_RECORD / EVIDENCE / NOT_A_RATIFICATION`. |
| `TRIAD_REVISION_RECORD_R-02_2026-08-13.md` | **Second correction record.** Fully **WITHDRAWS R-01 §1.5** (a second reviewer error, opposite direction — the reset bar DOES deepen; the developer's replacement test is correct); **accepts WO-J = OWNER_GATED_AMENDMENT** + corrects its enum to `{COMPLETE, RPI_EXCLUDED, UNKNOWN}`; **strengthens LAW-9 step 2** (read the code + name the test before writing a finding); and opens **GAP-51** (the symbol-selection confound → WO-A A5 + the SYNC-2 amendment). `CORRECTION_RECORD / EVIDENCE / NOT_A_RATIFICATION / NO_RUNTIME_CHANGE`. |
| `TRIAD_REVISION_RECORD_R-03_2026-08-13.md` | **Third correction record.** Records four correct calls (the #36 non-merge, the lint-fix-not-linter-relax, the unbid checkpoint refusal, the regenerate-not-hand-merge pin resolution); opens three findings — **M-1** (P0: `mergeable_state=unstable` means the combined check is not a REQUIRED status check on `main`, i.e. `GAP-30`/`WO-P` printing), **M-2** (P1: a permanently-red check carries zero signal → baseline + never-increase ratchet, do not mass-fix), **M-3** (P1: the checkpoint seal is now owed); **CORRECTS its own R-02 §3.2** — the fixed 93-round-trip bar is miscalibrated in both directions and must be computed against the OBSERVED win rate (`n_required`), with a `MUST_RATIFY` `n_floor`; and hands the D-7 reviewer one scope check on the #36 pin union. `CORRECTION_RECORD / FINDING_REGISTER / NOT_A_RATIFICATION / NO_RUNTIME_CHANGE`. |
| `TRIAD_MASTER_SEQUENCE_2026-08-13.md` | **Sequencing control + the nine standing laws (LAW-1…LAW-9).** Supersedes only the work order's `EXECUTION ORDER` section. Confirms Origin's lawful queue = **WO-J** (RPI coverage) + **WO-I** (owner-gated) + **WO-C** (F18 check-only) + R-01 §1.5's byte-neutral optional test. `SEQUENCING_CONTROL / NOT_A_RATIFICATION`. |
| `GAP-CROSSCHECK-2026-08-13.md` | This repo's honest per-gap disposition (superseded on ERR-02/GAP-12/WO-H by R-01; see the repair report). |
| `REPAIR-REPORT-2026-08-13.md` | **The full four-document cross-check + repair report** (the deliverable): every finding across the four documents, verified against the code, with its Origin-scope disposition, LAW-9, and the ownership reroute. Incl. §6b — the cross-repo WO-A lead (TriadLearning) + the BTC/BCH investigation. |
| `INVESTIGATION-BTC-BCH-2026-08-13.md` | **The "why only BTC and BCH trade" investigation** (read-only, six-lane funnel audit). No code path selects exactly {BTC, BCH}; feed-narrowing and the config-precision allowlist are ruled out; the primary suspect is the VGP min-notional × margin-cap ∩ scan-gate depth floor at ~$100 equity. Fastest on-box read named. `INVESTIGATION / EVIDENCE / NO_RUNTIME_CHANGE`. |
| `UNLOCK-ALL-SYMBOLS-PLAN-2026-08-13.md` | **The "unlock all tokens / every symbol tradable" plan** (owner directive). Confirms nothing is locked; decomposes the 30→~2 collapse into fairness (agent-buildable, narrowing-neutral), two money-line widenings (scan_gate floor + the LIVE30-PROFITABLE-ONLY wall — GOV-01), and the equity/physics floor; carries the GOV-01 arming card. Confirm tooling: `TriadLearning/analysis/symbol_funnel/`. `PLAN / NOT_A_RATIFICATION / NO_RUNTIME_CHANGE`. |
| `B01C_ENTRY_GATE.md` · `B01C_ACCEPTANCE_PROFILE.v1.json` | (pre-existing) the B01C entry-gate records. |

**LAW-9 (the most important addition).** When any external finding proposes a change that would
alter the **emitted bytes of a formula** — or flip a currently-passing test — it is an **amendment**,
not a repair: it requires the owner's signature plus a prior spec-amendment artifact, and an agent
does **not** implement it under its own authority, *however obviously correct it appears*. The
discriminator is bytes, not correctness. R-01 records that this repo already applied exactly this
discipline (refusing ERR-02), and elevates it to standing law. It governs every item in this
directory.

**The scope wall that governs this whole directory.** TriadOrigin is **E02 (structure detection)
only**. RC3 non-negotiable law 07 and this repo's `CLAUDE.md` forbid Origin from holding a cost
model, an economic-admission gate, an order verb, risk/quantity authorization, a venue client, a
fill parser, a money publisher, or a lease issuer. The **majority** of the gap register's 50 gaps —
the entire economic layer (E07), all venue-reality drift (E09/executor), the bank/measurement debt
(DTBNK/estate), and the governance/on-box acts — are therefore **out of Origin's scope by
construction**, and closing them here would breach the repository boundary, not honor it. The
cross-check states, gap by gap, exactly where each one lives and why.
