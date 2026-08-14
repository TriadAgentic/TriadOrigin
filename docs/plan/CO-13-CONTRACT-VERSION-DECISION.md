# CO-13 — Contract-Version Drift Resolution (the one signed decision, ten pairs)

**DISPOSITION:** `PENDING_SIGNATURE / DECISION_DRAFT`. This is the single
compatibility-and-migration decision `TRIAD-ORIGIN-V7-CHANGE-ORDERS-2026-08-12` CO-13 orders,
prepared for owner signature. **It is unsigned and therefore not in force**; until the
signature slot below is filled by the owner, every pair remains in drift and any consumer that
must choose between the two versions answers `BLOCKED_ON_RATIFY(CO-13)` — never a silent pick.
Posture unchanged: `OFF/OFF/OFF/LIVE`, `DENIED_SAFE_HOLD`.

**Laws of this decision (from the order):**
- **Additive, never rewriting historical bytes.** Both versions' published bytes are retained;
  the non-canonical one becomes a *historical alias*, never deleted, never edited.
- The canonical defaults below are **the versions the RC3 contract catalog §03 binds** —
  the decision adopts the catalog's binding unless the owner strikes a row at signature.
- RC5 (`RC5_EFFECTIVE_CONSOLIDATION`, CO-01) carries the canonical choice: after this decision
  is signed, the RC5 contract union shows exactly one canonical version per family.
- Reader/writer rule: writers emit the canonical version only; readers accept the historical
  alias read-only for replay/history, translating on read where a mapping exists, refusing
  with a named refusal (`HISTORICAL_ALIAS_UNTRANSLATABLE`) where it does not. Fixture tests
  per pair accompany the RC5 landing (CO-13 acceptance), not this draft.

## The ten pairs

| # | Pair (drifted versions) | Canonical choice (RC3 catalog §03 default) | Historical-alias note | Reader-compatibility note |
|---|---|---|---|---|
| 1 | `market_state.v1` / `market_state.v2` | **`market_state.v2`** | `v1` retained as frozen historical bytes; no new writer | `v1` rows readable for replay; field superset in `v2` — `v1` reads translate with absent fields honest-null, never defaulted |
| 2 | `structure_atom.v1` / `structure_atom.v2` | **`structure_atom.v2`** | `v1` frozen historical alias | `v1` atoms admissible in historical replay only; never pooled with `v2` populations (never-blend law on the version axis) |
| 3 | `edge_candidate.v1` / `edge_candidate.v2` | **`edge_candidate.v2`** | `v1` frozen historical alias | **Field note (ordered by CO-13):** `edge_candidate.v2` replaces the ambiguous `arm` field with explicit **`engine_cohort`** and **`intelligence_arm`** fields; a reader meeting legacy `arm` must not guess the split — an unmappable `arm` value is a named refusal, never a silent assignment |
| 4 | `decision.v1` / `decision.v2` | **`decision.v2`** | `v1` frozen historical alias | `v1` decisions readable for lineage joins only; no authority semantics inferred beyond the recorded bytes |
| 5 | `reservation.v1` / `risk_reservation.v1` | **`risk_reservation.v1`** | `reservation.v1` is the historical *name* alias (rename, not a shape change claim) | Readers treat `reservation.v1` records as `risk_reservation.v1`-named history; any shape divergence discovered at translation is a typed conflict, not a coercion |
| 6 | `execution_command.v3` / `execution_cmd.v2` | **`execution_cmd.v2`** | `execution_command.v3` frozen historical alias | The higher numeral does not outrank the catalog binding; readers of `execution_command.v3` history translate by the recorded crosswalk or refuse by name |
| 7 | `order_event.v3` / `order_event.v2` | **`order_event.v2`** | `order_event.v3` frozen historical alias | Same numeral-vs-catalog law as pair 6; `v3` history readable, never emitted |
| 8 | `position.v2` / `position_event.v2` | **`position_event.v2`** | `position.v2` is the historical name alias | Event-shaped canonical form; snapshot-shaped `position.v2` history readable as derived state, never re-emitted |
| 9 | `protection.v2` / `protection_event.v2` | **`protection_event.v2`** | `protection.v2` is the historical name alias | Same event-canonical law as pair 8 |
| 10 | `campaign_outcome.v2` + `attribution.v2` / `outcome.v2` | **`outcome.v2` → `outcome.v3`** per CO-04 | `campaign_outcome.v2` and `attribution.v2` frozen historical aliases; `outcome.v2` itself becomes historical bytes at the CO-04 cutover | The outcome family migrates once: `outcome.v3` (exact reduced rationals + quote unit + fee-conversion preimages, draft at `docs/plan/outcome.v3.draft.schema.json`) is the terminal canonical form; dual-write v2+v3 through the migration window; readers cut over by signed supersession |

## Cross-cutting notes ordered by CO-13

- **`edge_candidate.v2` `arm` split:** see pair 3 — `arm` → `engine_cohort` + `intelligence_arm`
  is part of this decision's scope; the rename lands additively in the `v2` canonical shape.
- **`divergence_record.v1` comparison axis:** `divergence_record.v1` gains the **enforced
  comparison axis** (which two subjects a divergence row compares, as a typed field, never
  implied by context) — a **B07 dependency**: the axis field is registered with this decision
  but its enforcement fixtures land with B07, and until then a comparison-axis-less divergence
  row is readable history, not new-writable.

## Signature

| Field | Value |
|---|---|
| Decision ID | `CO-13-CONTRACT-VERSION-DECISION` |
| Covers | the ten pairs above, as one indivisible decision (partial signature is no signature) |
| Owner signature | **`PENDING-OWNER`** — empty; Claude never signs; an agent never fills this slot |
| Signed at (UTC) | `PENDING-OWNER` |
| Effect on signature | canonical choices bind; RC5 carries them; reader/writer fixtures become required CI per CO-13 acceptance |
| Effect while unsigned | none — every consumer refusal stays `BLOCKED_ON_RATIFY(CO-13)` |
