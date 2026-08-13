# PART E — Owner-Service Specification Corrections (E08 / E09 / E10)

**DISPOSITION:** `OWNER E08/E09/E10 — NEVER IMPLEMENTED IN ORIGIN`. This file is the
Origin-vendored **correction record the owner services consume**. It implements nothing,
activates nothing, and closes nothing. Posture: `venue_environment=OFF / venue_activation=OFF /
paper_activation=OFF / shadow_activation=LIVE`; activation result `DENIED_SAFE_HOLD`.

**Provenance:** transcribed verbatim-in-substance from
`TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12` §5 "Part E — Owner-service specification
corrections (E08 / E09 / E10 — never implemented in Origin)" (source lines 821–837), under
change order `TRIAD-ORIGIN-V7-CHANGE-ORDERS-2026-08-12`. E08 (risk/sizing/authorization),
E09 (command/order/fill/protection) and E10 (outcome/learning) are `REFERENCE_ONLY` /
`OUT_OF_REPO` for TriadOrigin (repository law, `CLAUDE.md` ownership table); TriadOrigin
carries this record so the corrections travel with the spec corpus, never so that Origin
implements them.

**Consumption law.** The owner service for each section is the sole implementer. Nothing in
this record grants TriadOrigin (or any agent) authority to build E08/E09/E10 behavior; a
change to any section below is a change to the Formula Repair specification and moves with
it, never independently here.

---

## E.0 — F18 note (Origin, B06R — spec confirmation, no defect)

Geometry law stands: LONG requires `S < E < T`; SHORT requires `T < E < S`; exact rational
`reward × 1 >= risk × 2`; a wrong-side stop is rejected **before** any `abs()`; raw E/S/T are
frozen at publication.

The buffered-stop derivation and the priority target selector remain lawful **only** under
explicit bindings — `STOP_BUFFER_SOURCE` and `TARGET_SELECTOR_POLICY` — and both bindings stay
`PROPOSED_MUST_RATIFY`. **Absent ratification the formula abstains rather than improvising**:
the abstention is the named, fail-closed behavior; no default buffer source and no default
target selector may ever be invented in code. (This is the one Part E row with an Origin-side
subject — B06R — and it is a *confirmation*, not a defect: no Origin change is ordered by it.)

## E.1 — F20 `risk_sizing.linear_usdm.v1` (E08) — single-policy slot

- **Delete the `activation_mode = CANARY|PRODUCTION` budget branch** (RC4 supersession).
- Signature: `size(policy: SignedRiskPolicy, E, S, m, step, snapshot: ExposureSnapshot)` where
  the policy is **one already-selected, signature-verified object**
  `{B, c, limit clauses, min_notional, max_qty}`.
- Law: `unit_loss = m·|E−S| + c`, require `> 0`; `qty_raw = B / unit_loss`;
  `qty = floor(qty_raw / step) · step`; then the minimum across
  position/portfolio/exposure/leverage/concentration capacities with the **binding clause
  recorded**.
- Defense in depth: re-assert direction consistency (LONG `S < E`, SHORT `S > E`) and DENY on
  violation — `abs()` never launders a wrong-side stop.
- Unknown fee/stop/limits/exposure/account-mode → **DENY new exposure**.
- **Rollout/environment metadata is not an input**; a test asserts the function is closed over
  rollout fields.
- **Golden:** `B=1, m=1, |E−S|=1, c=0.0398 → unit_loss 1.0398 → qty_raw 0.961723… → 0.961`.

## E.2 — F21 `execution.maker_gtx.v1` (E09) — completed by GV-018 + `VenueExecutionPlan`

The compact law is correct and venue-verified. Completion requirements:

- The `VenueExecutionPlan` contract (Change Orders document, CO-03) carrying: observed ladder
  snapshot + book revision, ordinal budget `0..4`, reprice count, TTL, filters/price bands,
  account mode.
- Strict noncrossing check against a **fresh validated book at compile time**.
- GTX rejection → named refusal consuming **one reprice unit**.
- Idempotency key per `(economic purpose, reprice ordinal)`.
- Cancel-ack-replace lifecycle.
- Sparse-level and zone-outside-book refusals per golden **GV-018** (`REFUSED{NO_OBSERVED_LEVEL}`,
  `REFUSED{NO_OBSERVED_LEVEL_IN_ZONE}`, `REFUSED{LEVEL_BUDGET_EXHAUSTED}`; GTX race →
  `EXEC_GTX_REJECTED`, re-evaluate from a fresh validated book, never taker).
- **CO-07 note:** nine remaining migration-blocked F21 binding rows are adjudicated
  individually under CO-07 — **the single ACTIVE row does not authorize the formula**
  (a formula activates only when its *entire* binding set is ACTIVE; F21's 1-of-10 must never
  present as active).

## E.3 — F22 `execution.emergency_ioc.v1` (E09) — purpose-named rounding + lifecycle

- **Rename** the retained maker-side rounding parameters to purpose-specific
  **`LONG_SELL_OUTWARD_FLOOR`** and **`SHORT_BUY_OUTWARD_CEIL`** (values unchanged:
  long SELL `worst = floor_to_tick(best_bid × (1 − s/10⁴))`;
  short BUY `worst = ceil_to_tick(best_ask × (1 + s/10⁴))`).
- **Goldens:** reference `10000` at `10 bps` → `9990` (long-sell floor) / `10010`
  (short-buy ceil).
- Mandatory preconditions per attempt: fresh reconciled position
  (age ≤ `private_state_max_age_ms`), fresh validated book, current emergency authorization.
- `qty ≤ |reconciled residual|`; post-state assertion `|position_after| < |position_before|`
  and **no sign flip**.
- One-way vs hedge payloads are **separately certified compilers**.
- Monotone partial-fill retries within the tier budget; dust and cooldown laws.
- Unknown submit → **reconcile before any retry** (never blind-repeat); disconnect →
  **escalate, never fabricate**.

## E.4 — F23 `outcome.linear_usdm.v1` (E10) — schema conflict resolution → `outcome.v3`

`outcome.v2`'s integer-string, unitless money fields cannot encode the golden
(`0.2`, `−0.1`, net `5.1`). Publish **`outcome.v3`** (additive major, CO-04): every money field
is an **exact reduced rational `{num: int64-string, den: int64-string}`** with declared quote
unit and **fee-conversion mark preimages**. Laws bound with it:

- Quantity conservation `Σ entry_qty_steps == Σ exit_qty_steps` required for `COMPLETE`.
- `R_net = net / initial_risk_quote`, **NULL** when initial risk unknown or `≤ 0`.
- `fill_cost_bps = order_side_sign × (fill − decision_ref)/decision_ref × 10⁴`.
- `markout_bps(h) = order_side_sign × (mid_{t+h} − fill)/fill × 10⁴`, **NULL** when the causal
  mid mark at horizon `h` is unavailable.
- Signed funding.
- The emergency cohort is **permanently separate**.
- `SHADOW/PAPER/TESTNET/LIVE` identity is **mandatory and never mixed**.
- **Golden:** `gross 6 − fees 1 + rebates 0.2 + funding (−0.1) = 5.1` encodes as
  `{num:"51", den:"10"}`.

The Origin-side DRAFT encoding of this section is `docs/plan/outcome.v3.draft.schema.json`
(CO-04). Publication of `outcome.v3` is the **E10 owner service's act**: dual-write v2+v3
through the migration window, readers cut over by **signed supersession**, v2 retained as
historical bytes. The draft in this repository is input material only and confers no
publication authority.

---

*End of record. Nothing above is implemented in TriadOrigin; every section is owner-service
law consumed by E08/E09/E10. Any conflict between this transcription and
`TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12` §5 resolves in favor of the source specification.*
