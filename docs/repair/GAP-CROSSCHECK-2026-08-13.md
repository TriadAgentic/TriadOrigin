# TRIAD ORIGIN V7 — Gap-register cross-check + disposition

**Cross-checks:** `TRIAD_ORIGIN_V7_GAP_REGISTER_2026-08-13.md` (`GAP-01…GAP-50`) and
`TRIAD_REPAIR_WORK_ORDER_2026-08-13.md` (`WO-00…WO-Q`, `WO-A…WO-F`), both vendored in this
directory.
**Prepared:** 2026-08-13. **Disposition:** honest repo-side status. No signature, trust-registry
pin, credential value, or on-box receipt is fabricated. Posture unchanged: `OFF/OFF/OFF/LIVE`,
`DENIED_SAFE_HOLD`; `shadow_activation = LIVE` fixed. **Nothing here arms or disarms anything.**

## The one thing to read first — the scope wall

TriadOrigin is **E02 (structure detection) only**. RC3 non-negotiable **law 07** ("Risk
thresholds, leverage, stop floors, and portfolio budgets must never enter structure detection
geometry") and this repo's `CLAUDE.md` ("Never add a venue client, network control path,
credential/private-key loader, order verb, risk or quantity authorization, money publisher, fill
parser, or lease issuer") make it **structurally illegal** for Origin to hold the economic layer,
the venue layer, the bank, or the order path.

The gap register's own **CORRECTION-01** says the same thing from the other side: the working
economic gate belongs at **E07**, and *"Migrating from Engine to Origin as specified would remove
the only working economic gate in the estate."* The remedy is to **build the gate at E07**, and
Origin (E02) must never build it. So "close all 50 gaps in Origin" is not achievable — for ~40 of
them it is **forbidden**. Closing them here would breach the boundary the estate depends on, not
honor it.

This cross-check therefore reports four dispositions, and closes exactly the Origin-scope items:

| Disposition | Meaning | Count |
|---|---:|
| **CLOSED-IN-ORIGIN** | Origin-scope, agent-buildable, done + tested | 1 |
| **OWNER-GATED (recorded)** | Origin-scope but needs a GOV-01 signature / owner choice; recorded refusing-in-place, behaviour unchanged | 6 |
| **OUT-OF-ORIGIN** | Belongs to E07/E08/E09/E10/DTBNK/Mission-Control/Intelligence/estate; Origin must not build it | ~34 |
| **ON-BOX / operator** | A probe or run on the box, or a physical secret only the owner holds | ~9 |

**No gap is silently dropped. Every one is placed.**

---

## TIER A — the economic hole (GAP-01 … GAP-04) — OUT-OF-ORIGIN / owner

| Gap | WO | Disposition | Why |
|---|---|---|---|
| **GAP-01** no fee-net admission predicate | WO-02/WO-F | **OUT-OF-ORIGIN (E07)** | RC3 law 07 forbids cost in E02; RC3 authority matrix homes economic admission at E07; TBD-011. Building it in Origin is forbidden. Recorded in `DECISIONS-REQUIRED.md` **D-12**. |
| **GAP-02** no `cost_model.v1` | WO-01/WO-E | **OUT-OF-ORIGIN (E07)** | A cost model is the definition of "cost entering the system"; law 07 bars it from E02. It is an E07 contract + resolver. Recorded adjacent to **D-12/D-13**. |
| **GAP-03** 45 bps min-stop-width has no home | WO-03/WO-F | **OUT-OF-ORIGIN (E07)** | The floor must live at E07 admission (`MIN_STOP_WIDTH_BPS = H/MAX_COST_R`), never at E02. Recorded **D-13**. |
| **GAP-04** RR floor moved 2.5→2.0 | WO-04/WO-C | **OWNER-GATED (recorded) — D-11** | Origin's F18 (`candidate_geometry.py`) applies RR≥2 from **PAR-061 `MIN_GEOMETRIC_RR` (RATIFIED_RC1, `"2/1"`)** — an *injected required declared parameter, not a hardcoded default* (law 20 satisfied). The 2.0-vs-2.5 reconciliation, and WO-C's proposal to *remove the generation floor and derive it at admission*, is a change to a **ratified** formula → owner signature. See **D-11** + the F18 note below. |

**Note on GAP-04 / GAP-46 / WO-C (the F18 half that touches Origin).** WO-C's "GENERATION emits
RR, applies NO floor" would delete F18's ratified PAR-061 geometric floor and move all RR authority
to E07 admission. That is a semantic change to a RATIFIED_RC1 formula; an agent does not remove a
ratified floor to match a proposal. F18 stays faithful (PAR-061 = 2/1, refuses if the parameter is
absent); the redesign is **D-11**, owner-signed, landing as a prior spec artifact.

---

## TIER B — venue reality drift (GAP-05 … GAP-10) — OUT-OF-ORIGIN (E09 / executor) + ON-BOX

Every gap in this tier is about the **Binance venue** and the **executor's venue client**. Origin
has no venue client, no network path, and no order verb — by construction and by law. These are
`TriadExecutor` / `TriadVenueGateway` work, and WO-00 is an on-box probe.

| Gap | WO | Disposition |
|---|---|---|
| **GAP-05** conditional orders migrated to the Algo Service; `-4120` | WO-00 (probe), WO-01 | **ON-BOX probe + OUT-OF-ORIGIN (executor).** The register's own #1 hard rule: probe the box first. Origin cannot place or reconcile a venue order. |
| **GAP-06** RPI orders excluded from depth/trade feeds (F15/F16/F17 coverage) | WO-07/WO-J | **OUT-OF-ORIGIN (feed/E01 + executor).** F15/F16/F17 *detectors* live in Origin, but the RPI book-completeness fact is a **feed-layer** input (E01-owned market data + venue endpoints `rpiDepth`); Origin consumes/validates, never authors the feed. A `book_completeness` flag on the atom would be an additive input from the feed — recorded as a feed/producer follow-on, not an Origin formula edit. |
| **GAP-07** legacy WS URLs decommissioned 2026-04-23 | WO-00 | **ON-BOX + OUT-OF-ORIGIN (executor/feed).** |
| **GAP-08** `MIN_NOTIONAL` maybe hardcoded | WO-00, WO-08 | **ON-BOX + OUT-OF-ORIGIN (executor).** |
| **GAP-09** post-only rejection leaves no venue trace | WO-01 | **OUT-OF-ORIGIN (executor).** |
| **GAP-10** rate-limit / order-count budgets unmodelled | WO-01, WO-08 | **OUT-OF-ORIGIN (executor).** |

---

## TIER C — formula defects (GAP-11 … GAP-13) — the Origin-scope tier

| Gap | WO | Disposition |
|---|---|---|
| **GAP-11** F10 FVG state predicates overlap | WO-G | **✅ CLOSED-IN-ORIGIN.** `fvg_registry_v3._state_for` already implements the mutually-exclusive T4-ratified reading (`TOUCHED: pen==0`, `PARTIAL: 0<pen<1/2`, `MIDPOINT_FILLED: 1/2≤pen<1`, `FILLED: pen==1`); the required property test `test_fvg_registry_v3.TestErr01MutuallyExclusiveStates` (10⁵ random pens → exactly one predicate true) + a precise docstring landed. Recorded **D-21 (ERR-01)**. |
| **GAP-12** F13 `RECLAIM_PENDING` never updates the extreme | WO-H | **OWNER-GATED (recorded) — D-21 (ERR-02).** The current `excursion_reclaim_v2.py` faithfully implements the vendored CORRECTED LAW (`extreme = min over excursion-phase bar lows`), pinned by `test_hold_bars_do_not_deepen_the_extreme` + `test_h10_…deepens…first`. WO-H's "deepen in every non-terminal state" **contradicts that law**, flips a passing test, and changes `extreme`/`excursion_depth_ticks` bytes consumed by F18 stop logic → a formula-byte semantic change reserved for the owner's signature (a prior spec-amendment PR). Honest note in the module. |
| **GAP-13** F12 confirms on `GENERIC_BREAK` while F08 refuses | WO-I | **OWNER-GATED (recorded) — D-17 (ERR-03).** The BOS-vs-`GENERIC_BREAK` trial-identity resolution is the owner's A/B/C choice (B = split identity recommended). Behaviour unchanged; honest note in `order_block_v2.py`. **Hard ordering rule preserved:** WO-I must land before any CAP-01 shadow row is written (the register's rule #2) — which is exactly why it is surfaced as owner-gated *now*, not deferred silently. |

---

## TIER D — execution mechanics (GAP-14 … GAP-16) — OUT-OF-ORIGIN (E08/E09/engine)

| Gap | WO | Disposition |
|---|---|---|
| **GAP-14** Law 14 maker-only entry contradicted by evidence | WO-12/WO-B | **OUT-OF-ORIGIN (engine entry arms) + owner (amend a non-negotiable law).** Recorded **D-14 (entry half)**. |
| **GAP-15** exit path has an unbounded tail | WO-02 | **OUT-OF-ORIGIN (E09 protected stop) + owner.** The PROTECTED-STOP rail is a venue order path — forbidden in Origin. Recorded **D-14 (exit half)**. |
| **GAP-16** no entry-mechanism experiment structure | WO-12/WO-B | **OUT-OF-ORIGIN (engine `config/entry_arms.v1.json` + shadow resolution).** |

---

## TIER E — carried-forward estate debt (GAP-17 … GAP-23) — OUT-OF-ORIGIN (estate/DTBNK) + on-box

| Gap | WO | Disposition |
|---|---|---|
| **GAP-17** reconciler has never run | WO-13/WO-K | **ON-BOX + OUT-OF-ORIGIN (estate reconciler).** Recorded **D-18**. |
| **GAP-18** 13 incident orders' round-trip P&L unrecorded | WO-13/WO-K | **ON-BOX + estate.** Recorded **D-18**. |
| **GAP-19** two-clock contamination writer fix | WO-14/WO-L | **OUT-OF-ORIGIN (DTBNK bank writer).** |
| **GAP-20** three resolvers write one table | WO-14/WO-L | **OUT-OF-ORIGIN (DTBNK / resolver registry).** |
| **GAP-21** 2.93× row inflation / dedup | WO-14/WO-L | **OUT-OF-ORIGIN (DTBNK).** |
| **GAP-22** bank ~0.39% priced | WO-14/WO-L | **OUT-OF-ORIGIN (DTBNK backfill resolver).** |
| **GAP-23** `F4 liq_flush` writer-missing | WO-14/WO-L | **OUT-OF-ORIGIN (engine/DTBNK writer).** |

---

## TIER F — measurement plumbing (GAP-24 … GAP-29) — OUT-OF-ORIGIN (bank / MC / Intelligence)

| Gap | WO | Disposition |
|---|---|---|
| **GAP-24** synthesised geometry (every bank RR = 2.50) | WO-14 | **OUT-OF-ORIGIN (bank replay).** Origin's F18 fixes geometry at spec level going forward; replaying the historical bank is a DTBNK/estate act. |
| **GAP-25** zero-fee bank / `outcome.v3` unpublished | WO-15/WO-M | **OUT-OF-ORIGIN (E10).** The `outcome.v3` **DRAFT** schema is an Origin doc artifact (`docs/plan/outcome.v3.draft.schema.json`, CO-04); publishing, dual-write, and reader cutover are the E10 owner service's signed acts (already recorded, `DECISIONS-REQUIRED.md` Part D). |
| **GAP-26** six personas at n=0 | WO-14 | **OUT-OF-ORIGIN (bank scheduler).** |
| **GAP-27** `propose_action` executes nothing | WO-16/WO-N | **OUT-OF-ORIGIN (Mission Control).** |
| **GAP-28** `live_eligible.rs` wired nowhere | WO-16/WO-N | **OUT-OF-ORIGIN (TriadExecutor).** |
| **GAP-29** learning corpus cannot be built (`prompt_pinned:false`) | WO-17/WO-O | **OUT-OF-ORIGIN (Intelligence/Learning).** |

---

## TIER G — governance closure (GAP-30 … GAP-37) — OWNER / on-box (already recorded)

| Gap | WO | Disposition |
|---|---|---|
| **GAP-30** B00R root closure | WO-18/WO-P | **OWNER on-box — D-3 / O-3.** Templates fail closed; the four owner acts are unfabricated. |
| **GAP-31** milestone SOURCE grant excludes formula paths | WO-18/WO-P | **OWNER (CODEOWNER) — D-3b.** |
| **GAP-32** 8 owner blocking decisions + 3 research sentinels | WO-19 | **OWNER — D-2** (`PROPOSED_MUST_RATIFY` values; F06/F08/F17 refuse in place). |
| **GAP-33** 98 binding rows migration-blocked | WO-19 | **OWNER — D-2 / CO-07 worksheets** (`BLOCKED_BINDING_V2_MIGRATION`; a formula activates only when its *entire* set is ACTIVE). |
| **GAP-34** 28 TBDs open | WO-19 | **OWNER — D-2 / TBD register.** |
| **GAP-35** CO-14 topology decision "never received" | — | **CORRECTED: the file WAS received (2026-08-13).** `TOPOLOGY-DECISION-E03-E05-E06.md` is now registered + cross-checked in `docs/plan/CO-14-OWNER-TOPO-01-REGISTRATION.md`, `PENDING_SIGNATURE` — **D-4**. The gap register's "reserved slot" line predates the intake. |
| **GAP-36** three physical blanks (Auth0 / pager chat id / dead-man webhook) | WO-20/WO-Q | **OWNER physical values — O-1 adjacent.** The **dead-man second-channel webhook (standing P0)** is added to the owner register. |
| **GAP-37** credential rotation not performed | WO-20/WO-Q | **OWNER on-box — O-1** (exposure independently confirmed; no value read/copied). |

---

## TIER H — unbuilt by design (GAP-38 … GAP-42) — deferred / OUT-OF-ORIGIN

| Gap | Disposition |
|---|---|
| **GAP-38** every edge parameter unset | **OWNER — D-2 / TBD-004…009.** The register calls this "the single best anti-overfitting decision" — the mechanisms exist refusing-in-place; ratifying values is the owner's, deliberately deferred. |
| **GAP-39** 3 of 5 capsules cannot fire | **OWNER sequencing — D-16.** Origin's capsule *code* is correct + refusing (F06/F08/F17 gates stand); which to unblock first is the owner's ordering choice. |
| **GAP-40** 1,250 ledger rows NOT_STARTED (B08/B09/B10) | **DOWNSTREAM (estate milestones).** Not an Origin formula gap. |
| **GAP-41** WAVE-C-001 canonical identity migration | **OUT-OF-ORIGIN (cross-estate `fill.v3`).** |
| **GAP-42** two-bot problem (pre- vs post-governor tap) | **OUT-OF-ORIGIN (Relay/Learning).** |

---

## ADDENDUM A — engine teardown (GAP-43 … GAP-50) — OUT-OF-ORIGIN measurement + owner + one Origin-built lib

| Gap | WO | Disposition |
|---|---|---|
| **GAP-43** ~13 pp lost between signal and fill | WO-A | **OUT-OF-ORIGIN measurement (bank/engine).** Pure SQL on the estate shadow bank; Origin does not own the bank. |
| **GAP-44** counterfactual scores only the filled subset (`no_fill_win_share`) | WO-A | **OUT-OF-ORIGIN (bank).** |
| **GAP-45** maker-only entry is the largest EV destroyer | WO-B | **OUT-OF-ORIGIN (engine/execution) + owner (Law 14).** Recorded **D-14**. |
| **GAP-46** generation/admission RR-floor mismatch | WO-C | **OWNER-GATED — D-11** (same as GAP-04; the enforcement layer is E07 admission, the generation half is F18 above). |
| **GAP-47** R reported against two denominators | WO-A | **OUT-OF-ORIGIN (bank schema `risk_denominator`).** |
| **GAP-48** the comparator is built and never run | WO-D | **BUILT-IN-ORIGIN; running is ON-BOX.** `src/triad_origin/control/comparator.py` + `replay_runner.py` exist (the W07–W09 dark libraries) and are unit-tested. "Run it" needs a frozen 30-day E01 tape + running TriadEngine and TriadOrigin over it — an on-box/operator act with no venue risk. Nothing to build; the run is the operator's. |
| **GAP-49** three stop regimes coexist | WO-A | **OUT-OF-ORIGIN (cross-plane measurement).** |
| **GAP-50** `capsules.py` ↔ RC2 capsule mapping refused, not established | WO-D (D2) | **OWNER-GATED (recorded).** `capsules.py` correctly **refuses** the ordinal mapping (`rc2_ordinal_disclaimer`, bound by name+evidence, never guessed). A signed `CAP-01…CAP-05` mapping is a semantic-owner act — an agent does not guess a single row. Recorded as a new owner row (**D-22**). |

---

## What this repo did, precisely

1. **Closed the one Origin-scope, agent-buildable formula gap** that was open: GAP-11 / ERR-01 (F10
   mutually-exclusive predicates + property test) — landed and dual-seed green.
2. **Recorded, refusing-in-place, the Origin-scope owner-gated items:** GAP-12 (ERR-02, F13),
   GAP-13 (ERR-03/D-17, F12), GAP-04/GAP-46 (D-11, F18 RR floor), GAP-50 (D-22, capsule mapping) —
   each with an honest code-site note; **no formula bytes changed to match a non-ratified proposal.**
3. **Vendored both repair documents verbatim** here (evidence, `NOT_A_RATIFICATION`).
4. **Placed every one of the 50 gaps** in exactly one disposition and named the estate node that
   owns each out-of-Origin item, so nothing is lost and nothing is falsely claimed closed.

**What this repo did NOT do, and must not:** build the E07 economic-admission gate, the
`cost_model.v1` resolver, the min-stop-width binding, the algo-order venue path, the PROTECTED
STOP, the entry-mechanism arms, the bank repairs, or the reconciler — all forbidden in E02 by law
07 and this repo's `CLAUDE.md`. Those are real, mostly-P0 work; they are simply **someone else's to
build**, and the honest register above says whose.

**No outstanding *Origin-scope, agent-buildable, non-owner-gated* item remains.** The remaining
Origin items are owner signatures/choices (D-11, D-17, D-21, D-22, D-2, D-16); everything else is
out-of-Origin or on-box. The 12-gate suite is green dual-seed at the head that carries this
cross-check.
