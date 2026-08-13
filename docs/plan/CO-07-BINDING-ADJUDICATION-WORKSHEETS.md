# CO-07 — Binding Adjudication Worksheets

**Disposition:** `PLAN_LEVEL / PROPOSALS_ONLY / NOT_A_RATIFICATION / NO_RUNTIME_CHANGE`. Posture unchanged `OFF/OFF/OFF/LIVE`, `DENIED_SAFE_HOLD`.

Generated deterministically by `tools/gen_binding_adjudication_worksheets.py` from `docs/control/binding_registry.v2.json` (`registry_version=origin.binding-registry.v2`, `source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`). Do not hand-edit — regenerate from the registry.

## The law (read first)

* Every **proposed disposition** below is a **PROPOSAL ONLY**. An agent NEVER adjudicates a binding row.
* Every **owner signature slot** is **EMPTY (`PENDING_OWNER`)**. An agent NEVER signs.
* Rows are grouped in **FORMULA-COMPLETE groups**: a formula activates only when its ENTIRE set is `ACTIVE`. A partially-active formula (e.g. F21's 1-of-10) MUST NOT present as active.
* Adjudication targets are the closed set `ACTIVE | BLOCKED | SUPERSEDED | REFUSED` (CO-07 objective). `BLOCKED_ON_RATIFY(...)` / `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` are BLOCKED sub-reasons.

## Row-count reconciliation (honest note)

The registry carries **105 rows** (declared `row_count=105`). Status counts: `ACTIVE=3`, `BLOCKED=4`, `BLOCKED_BINDING_V2_MIGRATION=98`.
The CO-07 title names "the 98 migration-blocked rows"; that is exactly the `BLOCKED_BINDING_V2_MIGRATION=98` subset. The 4 `BLOCKED` (unratified) + 3 `ACTIVE` rows complete the **105-row bundle** the owner authenticates per Formula Repair §C.1 (CO-07 Step 5). PAR-025 (RC3-FPB-005, F01) is a `BLOCKED` (unratified) row not named in the research list; per registry status it is proposed `BLOCKED_ON_RATIFY(PAR-025)`.

## Proposed-disposition tally (proposals, not adjudications)

* `ACTIVE` — 3
* `BLOCKED_ON_MIGRATION` — 96
* `BLOCKED_ON_RATIFY` — 5
* `SUPERSEDED` — 1

Canonical-target rollup: `ACTIVE=3`, `BLOCKED=101`, `SUPERSEDED=1`, `REFUSED=0`. No current row warrants a proposed `REFUSED`.

---

## Formula F00 — group activation: FORMULA-COMPLETE · ACTIVE

*FORMULA-COMPLETE: 2/2 rows proposed ACTIVE.*

### FPB-0001 — F00 · PAR-001 (PRICE_WIRE_TYPE)

* **binding_id:** `FPB-0001`
* **formula_id:** `F00`
* **parameter:** PAR-001 (PRICE_WIRE_TYPE)
* **declared value:** `price_ticks=exact_div(venue_price,tick_size)`
* **unit:** `tick`
* **gate:** `G1`
* **boundary rule:** Any nonzero remainder, overflow or stale/unknown metadata quarantines the complete source event.
* **failure behavior:** QUARANTINE_INGRESS_EVENT; no canonical event, candidate or order.
* **evidence refs:**
    * `source_binding_id=FPB-0001`
    * `rc2_source_digest=ce548b9c89f2f8e4f8caf1f6cf5788901f1966b9f3d5c187f37369efc836452a`
    * `binding_digest=b6c891ee2aec4761ad4567869412d7ec6f2005dbe65f8a4d27992b8ddb70a13f`
    * `operation_id=RC3-BOP-010`
    * `activation_scope=E01;G1;venue/instrument/metadata-revision exact scope`
    * `consuming_wiring_ids=W01`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `ACTIVE` → canonical target `ACTIVE`
    * named refusal / basis: PROPOSED ACTIVE: RC3 makes the already fail-closed price conversion explicit in binding.v2 at the consuming G1 gate.
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0002 — F00 · PAR-002 (QUANTITY_WIRE_TYPE)

* **binding_id:** `FPB-0002`
* **formula_id:** `F00`
* **parameter:** PAR-002 (QUANTITY_WIRE_TYPE)
* **declared value:** `signed int64 exact integer steps`
* **unit:** `step`
* **gate:** `G1`
* **boundary rule:** qty_steps=exact_div(venue_qty,step_size); any nonzero remainder quarantines the complete source event; no floor or tolerance.
* **failure behavior:** QUARANTINE_INGRESS_EVENT on remainder, overflow or stale/unknown metadata.
* **evidence refs:**
    * `source_binding_id=FPB-0002`
    * `rc2_source_digest=70135b5a3a5c352bc009fadbdb2e05ecf4d2db2437ba774502eb3bda24f45c29`
    * `binding_digest=a9bfbc79e5c6d1c13b7f8a253249bd92c87a82ef1c560986ed6e75184c818954`
    * `operation_id=RC3-BOP-007`
    * `activation_scope=E01;G1;venue/instrument/metadata-revision exact scope`
    * `consuming_wiring_ids=W01`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `ACTIVE` → canonical target `ACTIVE`
    * named refusal / basis: PROPOSED ACTIVE: RC3 removes downstream order-floor semantics from ingress parsing while retaining the wire type.
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

---

## Formula F01 — group activation: NOT ACTIVE

*NOT FORMULA-COMPLETE: 0/1 rows proposed ACTIVE — the formula MUST NOT present as active until its entire set is ACTIVE.*

### RC3-FPB-005 — F01 · PAR-025 (ALLOWED_EVENT_LATENESS)

* **binding_id:** `RC3-FPB-005`
* **formula_id:** `F01`
* **parameter:** PAR-025 (ALLOWED_EVENT_LATENESS)
* **declared value:** `2000`
* **unit:** `ms`
* **gate:** `G1`
* **boundary rule:** AFTER_WATERMARK_ADVANCE_BEFORE_FINALIZED_PUBLICATION
* **failure behavior:** Unknown/stale watermark or unratified lateness => no FINALIZED bar; dependent structure SAFE_HOLD.
* **evidence refs:**
    * `source_binding_id=`
    * `rc2_source_digest=`
    * `binding_digest=0220907e9057b7e8f8434ec6d5fe3d3259194f3755ecc4b05e1350cfc481a563`
    * `operation_id=`
    * `activation_scope=E01;G1;venue/instrument/timeframe/partition/formula-version exact scope`
    * `consuming_wiring_ids=W02`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_RATIFY(PAR-025)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_RATIFY(PAR-025): PAR-025 remains unratified; no FINALIZED bar can be authorized until signed.
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

---

## Formula F02 — group activation: NOT ACTIVE

*NOT FORMULA-COMPLETE: 0/1 rows proposed ACTIVE — the formula MUST NOT present as active until its entire set is ACTIVE.*

### FPB-0010 — F02 · PAR-035 (ATR_PERIOD)

* **binding_id:** `FPB-0010`
* **formula_id:** `F02`
* **parameter:** PAR-035 (ATR_PERIOD)
* **declared value:** `14`
* **unit:** `finalized bars`
* **gate:** `G2`
* **boundary rule:** Requires all 14 TRs; no partial warm-up.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: ATR null and dependent structures abstain.
* **evidence refs:**
    * `source_binding_id=FPB-0010`
    * `rc2_source_digest=5072d8f502e684c42eef978801e2be16afe29e019d64945ae3ab78444c54ac85`
    * `binding_digest=d747538d7d32206936d1669eafab065eec549a58745873b54cc72cf2c5aafe7b`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

---

## Formula F03 — group activation: NOT ACTIVE

*NOT FORMULA-COMPLETE: 0/1 rows proposed ACTIVE — the formula MUST NOT present as active until its entire set is ACTIVE.*

### FPB-0011 — F03 · PAR-036 (DC_REVERSAL)

* **binding_id:** `FPB-0011`
* **formula_id:** `F03`
* **parameter:** PAR-036 (DC_REVERSAL)
* **declared value:** `max(5,ceil(ATR14_ticks*1/4))`
* **unit:** `ticks`
* **gate:** `G2`
* **boundary rule:** Reversal confirms on >= delta; equality passes.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: No swing until ATR available.
* **evidence refs:**
    * `source_binding_id=FPB-0011`
    * `rc2_source_digest=e700282e36ab0406597e18591329b09d867dca7ce2a327657a667e44924c178a`
    * `binding_digest=c7e2f82bb0b82fd7e32a42e7e06675ce8ce320905cc620eb881f791595e79abd`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_RATIFY(PAR-036)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_RATIFY(PAR-036): DC_REVERSAL awaits an owner research decision (F03 reversal); the RC2 row is also unmigrated by RC3-TASK-G2-BINDING-V2.
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

---

## Formula F04 — group activation: NOT ACTIVE

*NOT FORMULA-COMPLETE: 0/2 rows proposed ACTIVE — the formula MUST NOT present as active until its entire set is ACTIVE.*

### FPB-0012 — F04 · PAR-037 (FRACTAL_LEFT_BARS)

* **binding_id:** `FPB-0012`
* **formula_id:** `F04`
* **parameter:** PAR-037 (FRACTAL_LEFT_BARS)
* **declared value:** `2`
* **unit:** `finalized bars`
* **gate:** `G2`
* **boundary rule:** Strict > for high and < for low.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Tie rejects pivot.
* **evidence refs:**
    * `source_binding_id=FPB-0012`
    * `rc2_source_digest=7b1901d711bcf72842be42d6a761c7e67c795a2b1854bc3d8e67df3baa5ad383`
    * `binding_digest=794f8faa440a103e14a48e36614e12753fe0a77d1f565cab94f725dc00356961`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0013 — F04 · PAR-038 (FRACTAL_RIGHT_BARS)

* **binding_id:** `FPB-0013`
* **formula_id:** `F04`
* **parameter:** PAR-038 (FRACTAL_RIGHT_BARS)
* **declared value:** `2`
* **unit:** `finalized bars`
* **gate:** `G2`
* **boundary rule:** Publish at close of the second right bar.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Before confirmation no pivot exists.
* **evidence refs:**
    * `source_binding_id=FPB-0013`
    * `rc2_source_digest=23739a3850599b2973d59ea402f90a9eaecb093742a492677521f4c7a41499ae`
    * `binding_digest=b8f77f4d811cc08a9577dba36eef744d152ffd740b22d86cd0d0d5fab98a89e9`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

---

## Formula F05 — group activation: NOT ACTIVE

*NOT FORMULA-COMPLETE: 0/1 rows proposed ACTIVE — the formula MUST NOT present as active until its entire set is ACTIVE.*

### FPB-0014 — F05 · PAR-039 (ROLLING_EXTREME_WINDOW)

* **binding_id:** `FPB-0014`
* **formula_id:** `F05`
* **parameter:** PAR-039 (ROLLING_EXTREME_WINDOW)
* **declared value:** `20`
* **unit:** `prior finalized bars`
* **gate:** `G2`
* **boundary rule:** Exactly 20 complete predecessors required.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Null during warm-up.
* **evidence refs:**
    * `source_binding_id=FPB-0014`
    * `rc2_source_digest=2a259af1e9e2f5616b8336fc81490bf6d80964bc84b572a3d411b3afff93a386`
    * `binding_digest=b294acff3bdc81150e91c5b1e40fb892fe96f2ac33061df9fc2bae231cd26a12`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

---

## Formula F06 — group activation: NOT ACTIVE

*NOT FORMULA-COMPLETE: 0/4 rows proposed ACTIVE — the formula MUST NOT present as active until its entire set is ACTIVE.*

### FPB-0015 — F06 · PAR-040 (EQUAL_LEVEL_MIN_TOUCHES)

* **binding_id:** `FPB-0015`
* **formula_id:** `F06`
* **parameter:** PAR-040 (EQUAL_LEVEL_MIN_TOUCHES)
* **declared value:** `2`
* **unit:** `confirmed pivots`
* **gate:** `G2`
* **boundary rule:** Two passes; one does not.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: No atom.
* **evidence refs:**
    * `source_binding_id=FPB-0015`
    * `rc2_source_digest=fe635de71736cdac26fb5b9233edc26c4a9c00e102653c5075dee8bf4a5dc8af`
    * `binding_digest=6ddb6804e83df149387d369fa36c8e1578c0ce8a5e3092ce1afbe3df7dd9640d`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0016 — F06 · PAR-041 (EQUAL_LEVEL_TOLERANCE)

* **binding_id:** `FPB-0016`
* **formula_id:** `F06`
* **parameter:** PAR-041 (EQUAL_LEVEL_TOLERANCE)
* **declared value:** `max(2,ceil(ATR14_ticks*1/10))`
* **unit:** `ticks`
* **gate:** `G2`
* **boundary rule:** Equality passes; anchor never recenters.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Start a different candidate cluster.
* **evidence refs:**
    * `source_binding_id=FPB-0016`
    * `rc2_source_digest=55bc584a8731e8e108a21a911d4c99d155310bcc9787b9eed5ec164688579123`
    * `binding_digest=88626ab8e456a3662a8039d9422aa252ee24258ace65090aaab0b3e34f40816c`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0087 — F06 · PAR-176 (CAP03_EQUAL_SWEEP_ENTRY)

* **binding_id:** `FPB-0087`
* **formula_id:** `F06`
* **parameter:** PAR-176 (CAP03_EQUAL_SWEEP_ENTRY)
* **declared value:** `frozen_equal_level_anchor`
* **unit:** `ticks`
* **gate:** `G3`
* **boundary rule:** No recentering to later pivots.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Candidate abstains when anchor/lineage unavailable.
* **evidence refs:**
    * `source_binding_id=FPB-0087`
    * `rc2_source_digest=a282bdc72eb1300d08b1bbe7ec57c5e05f06c365958db89bb9868d086a918f09`
    * `binding_digest=74913850cc1eff2900ac53600c4b6a5429d3768780d58ff051a468751c5c6cd7`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### RC3-FPB-001 — F06 · RC3-PAR-STRUCT-001 (EQUAL_LEVEL_MAX_SPAN)

* **binding_id:** `RC3-FPB-001`
* **formula_id:** `F06`
* **parameter:** RC3-PAR-STRUCT-001 (EQUAL_LEVEL_MAX_SPAN)
* **declared value:** `NOT_RATIFIED`
* **unit:** `integer ticks`
* **gate:** `G2`
* **boundary rule:** AFTER_TOLERANCE_CHECK_BEFORE_MEMBER_APPEND
* **failure behavior:** F06 unavailable and dependent capsules SAFE_HOLD.
* **evidence refs:**
    * `source_binding_id=`
    * `rc2_source_digest=`
    * `binding_digest=7ece50b8dd4734e31e94e4e30164ccf173cf095946a5793e36c68d55cc128870`
    * `operation_id=`
    * `activation_scope=ORIGIN;G2;instrument/timeframe/formula-version exact scope`
    * `consuming_wiring_ids=W04\|W05`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_RATIFY(RC3-PAR-STRUCT-001)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_RATIFY(RC3-PAR-STRUCT-001): Parameter is NOT_RATIFIED.
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

---

## Formula F07 — group activation: NOT ACTIVE

*NOT FORMULA-COMPLETE: 0/2 rows proposed ACTIVE — the formula MUST NOT present as active until its entire set is ACTIVE.*

### FPB-0017 — F07 · PAR-042 (SESSION_WINDOWS_UTC)

* **binding_id:** `FPB-0017`
* **formula_id:** `F07`
* **parameter:** PAR-042 (SESSION_WINDOWS_UTC)
* **declared value:** `[00:00,08:00);[08:00,16:00);[16:00,24:00)`
* **unit:** `UTC`
* **gate:** `G2`
* **boundary rule:** Start inclusive, end exclusive.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Calendar missing/mismatched blocks session-level capsule.
* **evidence refs:**
    * `source_binding_id=FPB-0017`
    * `rc2_source_digest=94b19bb2ff083889cf99b908774f378dde3c24d233f9a8d678cddfc952f18f83`
    * `binding_digest=da07b58035780ffe4c798f1fbc84689d42bf7598551d81e4d4227d851cbc7d99`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0095 — F07 · PAR-178 (CAP05_SESSION_ENTRY)

* **binding_id:** `FPB-0095`
* **formula_id:** `F07`
* **parameter:** PAR-178 (CAP05_SESSION_ENTRY)
* **declared value:** `completed_session_anchor`
* **unit:** `ticks`
* **gate:** `G3`
* **boundary rule:** Current/incomplete session anchor forbidden.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Candidate abstains SESSION_INCOMPLETE.
* **evidence refs:**
    * `source_binding_id=FPB-0095`
    * `rc2_source_digest=aa717947307effc8b8efe0a8f546e5f9d4cdb28c3e4a5f6d08914710b5fac06e`
    * `binding_digest=b1b82efd52881b056b523ed63c06f18b17603c2dbc8a24f8c66b60d48c27ee7c`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

---

## Formula F08 — group activation: NOT ACTIVE

*NOT FORMULA-COMPLETE: 0/3 rows proposed ACTIVE — the formula MUST NOT present as active until its entire set is ACTIVE.*

### FPB-0064 — F08 · PAR-156 (PROTECTED_SWING_TOLERANCE)

* **binding_id:** `FPB-0064`
* **formula_id:** `F08`
* **parameter:** PAR-156 (PROTECTED_SWING_TOLERANCE)
* **declared value:** `max(1,ceil(ATR14_ticks*1/20))`
* **unit:** `ticks`
* **gate:** `G2`
* **boundary rule:** A new high/low exactly tolerance away qualifies; one tick less does not.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: State stays RANGE/unchanged.
* **evidence refs:**
    * `source_binding_id=FPB-0064`
    * `rc2_source_digest=4cf22fb437b3c64958997d1284688faee449682aac1e261e32a0430c1ceea223`
    * `binding_digest=7f96092ad2cdad140b81c3cc6cc6020d97789e658ea62015385693fab4f3fa64`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0091 — F08 · PAR-177 (CAP04_CHOCH_ENTRY)

* **binding_id:** `FPB-0091`
* **formula_id:** `F08`
* **parameter:** PAR-177 (CAP04_CHOCH_ENTRY)
* **declared value:** `accepted_break_level`
* **unit:** `ticks`
* **gate:** `G3`
* **boundary rule:** Wick extreme is not substituted.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Candidate abstains if no F09 CHOCH occurrence.
* **evidence refs:**
    * `source_binding_id=FPB-0091`
    * `rc2_source_digest=faa6980240e196d0060df7384de1e1ce3d65ae6c42782690b1ba53367bf2e4f6`
    * `binding_digest=b7975519c932488f847a569c429f6d7530fbd88ac8a489dc7d57d5f0e16bdf73`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### RC3-FPB-002 — F08 · RC3-PAR-STRUCT-003 (PROTECTED_SWING_REDUCER_VERSION)

* **binding_id:** `RC3-FPB-002`
* **formula_id:** `F08`
* **parameter:** RC3-PAR-STRUCT-003 (PROTECTED_SWING_REDUCER_VERSION)
* **declared value:** `NOT_RATIFIED`
* **unit:** `semantic reducer version`
* **gate:** `G2`
* **boundary rule:** BEFORE_ANY_PROTECTED_SWING_STATE_MUTATION
* **failure behavior:** F08 unavailable; state remains UNINITIALIZED/no candidate.
* **evidence refs:**
    * `source_binding_id=`
    * `rc2_source_digest=`
    * `binding_digest=8746bf9bc6c904d071c7aa4f55ce146341bec61ed5f5fa7dae8790cefa81e34d`
    * `operation_id=`
    * `activation_scope=ORIGIN;G2;formula-version exact scope`
    * `consuming_wiring_ids=W04\|W05`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_RATIFY(RC3-PAR-STRUCT-003)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_RATIFY(RC3-PAR-STRUCT-003): Reducer version is NOT_RATIFIED.
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

---

## Formula F09 — group activation: NOT ACTIVE

*NOT FORMULA-COMPLETE: 0/2 rows proposed ACTIVE — the formula MUST NOT present as active until its entire set is ACTIVE.*

### FPB-0018 — F09 · PAR-043 (BOS_CLOSE_BUFFER)

* **binding_id:** `FPB-0018`
* **formula_id:** `F09`
* **parameter:** PAR-043 (BOS_CLOSE_BUFFER)
* **declared value:** `max(1,ceil(ATR14_ticks*1/20))`
* **unit:** `ticks`
* **gate:** `G2`
* **boundary rule:** Equality passes.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: No break transition.
* **evidence refs:**
    * `source_binding_id=FPB-0018`
    * `rc2_source_digest=91949a2444f50cfb717ab349abb070ec76138c798bc266c311e31e854307cbed`
    * `binding_digest=df05ea0c1ac0e92459b87893374df98102c480496f72c08dc94117f693a46006`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0092 — F09 · PAR-177 (CAP04_CHOCH_ENTRY)

* **binding_id:** `FPB-0092`
* **formula_id:** `F09`
* **parameter:** PAR-177 (CAP04_CHOCH_ENTRY)
* **declared value:** `accepted_break_level`
* **unit:** `ticks`
* **gate:** `G3`
* **boundary rule:** Wick extreme is not substituted.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Candidate abstains if no F09 CHOCH occurrence.
* **evidence refs:**
    * `source_binding_id=FPB-0092`
    * `rc2_source_digest=fd6ca9d654d16a93b186b715861448883d0de40a5399c42ddd12acc9b62728c6`
    * `binding_digest=b40551eba4db71b7eb2877e60d08125d0cb779c49a7ecea4b5ccbe0e397a7982`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

---

## Formula F10 — group activation: NOT ACTIVE

*NOT FORMULA-COMPLETE: 0/3 rows proposed ACTIVE — the formula MUST NOT present as active until its entire set is ACTIVE.*

### FPB-0019 — F10 · PAR-044 (FVG_MIN_GAP)

* **binding_id:** `FPB-0019`
* **formula_id:** `F10`
* **parameter:** PAR-044 (FVG_MIN_GAP)
* **declared value:** `max(1,ceil(ATR14_ticks*1/20))`
* **unit:** `ticks`
* **gate:** `G2`
* **boundary rule:** Equality passes; one tick below fails.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: No FVG atom.
* **evidence refs:**
    * `source_binding_id=FPB-0019`
    * `rc2_source_digest=afc36f50f936440e71fce64178bbcbd6562449f0f1025b2250a57bb44e99038d`
    * `binding_digest=0152b364a8bbea6e29cf1e5e0927d7640cffecc97f4647c8c3481187496f9053`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0039 — F10 · PAR-063 (FVG_FORMATION_BARS)

* **binding_id:** `FPB-0039`
* **formula_id:** `F10`
* **parameter:** PAR-063 (FVG_FORMATION_BARS)
* **declared value:** `3`
* **unit:** `finalized bars`
* **gate:** `G2`
* **boundary rule:** Formation bar touch cannot precede availability.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: No early atom.
* **evidence refs:**
    * `source_binding_id=FPB-0039`
    * `rc2_source_digest=bc5000c800db6917f6b23d08a557a77a4d833bd2c7557c57e9a2d317ce182853`
    * `binding_digest=55532749defef0cfd6ed9792c3fa960186178f1aadd50ea933c6896256c7718d`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0084 — F10 · PAR-175 (CAP02_FVG_ENTRY)

* **binding_id:** `FPB-0084`
* **formula_id:** `F10`
* **parameter:** PAR-175 (CAP02_FVG_ENTRY)
* **declared value:** `zone_midpoint`
* **unit:** `ticks`
* **gate:** `G3`
* **boundary rule:** Exact midpoint unchanged.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Candidate abstains if zone invalid/filled before eligibility.
* **evidence refs:**
    * `source_binding_id=FPB-0084`
    * `rc2_source_digest=134462ca00bccc20474367ea70c1bad5bda46e37c49b0c3e282d1dcf656457c0`
    * `binding_digest=41c23096b7c7b776a2b2d5da8761e5f0c4451d90e47c1bc93b8894947b562e6f`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

---

## Formula F11 — group activation: NOT ACTIVE

*NOT FORMULA-COMPLETE: 0/4 rows proposed ACTIVE — the formula MUST NOT present as active until its entire set is ACTIVE.*

### FPB-0021 — F11 · PAR-046 (DISPLACEMENT_BODY_FRACTION)

* **binding_id:** `FPB-0021`
* **formula_id:** `F11`
* **parameter:** PAR-046 (DISPLACEMENT_BODY_FRACTION)
* **declared value:** `13/20`
* **unit:** `bar range`
* **gate:** `G2`
* **boundary rule:** Equality passes; zero range fails.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Displacement false.
* **evidence refs:**
    * `source_binding_id=FPB-0021`
    * `rc2_source_digest=81fe1ad2e5ae66e240f4fcb486e8e09e08b2d7de6d5ebebb2a9d2f47b3520450`
    * `binding_digest=d5cb11dbb0ce280678f6320a3e21d51e2b110c5dfdd1a268e1ce473699b7272c`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0065 — F11 · PAR-157 (DISPLACEMENT_HORIZON)

* **binding_id:** `FPB-0065`
* **formula_id:** `F11`
* **parameter:** PAR-157 (DISPLACEMENT_HORIZON)
* **declared value:** `3`
* **unit:** `finalized bars after origin`
* **gate:** `G2`
* **boundary rule:** Third later bar included; fourth excluded.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Origin expires without displacement.
* **evidence refs:**
    * `source_binding_id=FPB-0065`
    * `rc2_source_digest=7ebee3b96a9df61edba0ec9b48a318a1eb3b2d7c4e53dfb557dbeda91623a434`
    * `binding_digest=fb8d1017e2d278dd79d33c5ee609e03953505c8b9c837a77a8e0ac7899a052c0`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0066 — F11 · PAR-158 (DISPLACEMENT_MIN_MOVE)

* **binding_id:** `FPB-0066`
* **formula_id:** `F11`
* **parameter:** PAR-158 (DISPLACEMENT_MIN_MOVE)
* **declared value:** `max(5,ceil(ATR14_before_origin*3/2))`
* **unit:** `ticks`
* **gate:** `G2`
* **boundary rule:** Equality passes.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Displacement false.
* **evidence refs:**
    * `source_binding_id=FPB-0066`
    * `rc2_source_digest=b260cd29ccdb55bfd741f0eabdd1e4e9b7ff1a93d6f4a3d10c89cd7b8271ef96`
    * `binding_digest=565a473fb12aa12cddf4f2e6fadd41844cc04dd244c98195d5777209efa99f1f`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0067 — F11 · PAR-159 (DISPLACEMENT_CLOSE_LOCATION)

* **binding_id:** `FPB-0067`
* **formula_id:** `F11`
* **parameter:** PAR-159 (DISPLACEMENT_CLOSE_LOCATION)
* **declared value:** `4/5`
* **unit:** `bar range`
* **gate:** `G2`
* **boundary rule:** Equality passes; zero range fails.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Displacement false.
* **evidence refs:**
    * `source_binding_id=FPB-0067`
    * `rc2_source_digest=5aca61df1a4071a0312b382f80ae38a2009d646b6d68d42ad290400d95285442`
    * `binding_digest=e401136c125cd14343af5c69d0bf348f1efea78ef783d52e29727a0655024ebc`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

---

## Formula F12 — group activation: NOT ACTIVE

*NOT FORMULA-COMPLETE: 0/5 rows proposed ACTIVE — the formula MUST NOT present as active until its entire set is ACTIVE.*

### FPB-0022 — F12 · PAR-047 (ORDER_BLOCK_LOOKBACK)

* **binding_id:** `FPB-0022`
* **formula_id:** `F12`
* **parameter:** PAR-047 (ORDER_BLOCK_LOOKBACK)
* **declared value:** `8`
* **unit:** `finalized bars`
* **gate:** `G2`
* **boundary rule:** Distance one wins; tie by latest event then source ID.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: No order block.
* **evidence refs:**
    * `source_binding_id=FPB-0022`
    * `rc2_source_digest=029e11d79f0536b1975f9e9fa5c97c51239c92ea8862de89bca4216f194a3b5c`
    * `binding_digest=d9668ffbf2aa3a18a8d2248604f7c223d569b8518c5db03b64d8888a485be83b`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0068 — F12 · PAR-160 (ORDER_BLOCK_BOS_HORIZON)

* **binding_id:** `FPB-0068`
* **formula_id:** `F12`
* **parameter:** PAR-160 (ORDER_BLOCK_BOS_HORIZON)
* **declared value:** `5`
* **unit:** `finalized bars after displacement`
* **gate:** `G2`
* **boundary rule:** Fifth included; sixth fails.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: No confirmed order block.
* **evidence refs:**
    * `source_binding_id=FPB-0068`
    * `rc2_source_digest=eb80266b44d5b55b87019c96e8d90e0a3848d9e96797b67d42d106c266f9a484`
    * `binding_digest=f32aa7f3d06f3918c252224fc7f92734e9741cd690943fef0f9463414be47c6c`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0069 — F12 · PAR-161 (ORDER_BLOCK_OPPOSING_PREDICATE)

* **binding_id:** `FPB-0069`
* **formula_id:** `F12`
* **parameter:** PAR-161 (ORDER_BLOCK_OPPOSING_PREDICATE)
* **declared value:** `bull:close<open; bear:close>open`
* **unit:** `predicate`
* **gate:** `G2`
* **boundary rule:** Strict inequality.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Skip bar; no origin if none in lookback.
* **evidence refs:**
    * `source_binding_id=FPB-0069`
    * `rc2_source_digest=367012ebf2eec25b64c03cbd44f62e5c441a49fb6aca2794d8cd5db69fe861f6`
    * `binding_digest=fac16a8a9c2181fce253fa6dcfd70fc6c030cbe76bb40e71cbaa38d325613b78`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0070 — F12 · PAR-162 (ORDER_BLOCK_MITIGATION)

* **binding_id:** `FPB-0070`
* **formula_id:** `F12`
* **parameter:** PAR-162 (ORDER_BLOCK_MITIGATION)
* **declared value:** `penetration>=1/2`
* **unit:** `zone width`
* **gate:** `G2`
* **boundary rule:** Exactly midpoint mitigates.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Before midpoint remains TOUCHED/PARTIAL.
* **evidence refs:**
    * `source_binding_id=FPB-0070`
    * `rc2_source_digest=65d64bed8c7972c0539c311142abba323ecf6665639b3793c43f8f1e4a3169c2`
    * `binding_digest=8445d8f7a005aa1ad2ed9f43036910205fdbc190724f307c2f09c0a9ddcf0303`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0071 — F12 · PAR-163 (ORDER_BLOCK_BREAK)

* **binding_id:** `FPB-0071`
* **formula_id:** `F12`
* **parameter:** PAR-163 (ORDER_BLOCK_BREAK)
* **declared value:** `finalized close beyond far edge by BOS_CLOSE_BUFFER`
* **unit:** `predicate`
* **gate:** `G2`
* **boundary rule:** Equality at buffered boundary breaks.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: BROKEN terminal; no candidate.
* **evidence refs:**
    * `source_binding_id=FPB-0071`
    * `rc2_source_digest=830c4bef0f6f110d78347a15c766204a1d171b2c85e86fa5b9d74a920c5994a7`
    * `binding_digest=1930365fb9d6ede80a4152d4edc8a30a07d5009330b13386585a7f67715378c8`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

---

## Formula F13 — group activation: NOT ACTIVE

*NOT FORMULA-COMPLETE: 0/6 rows proposed ACTIVE — the formula MUST NOT present as active until its entire set is ACTIVE.*

### FPB-0023 — F13 · PAR-048 (EXCURSION_MIN)

* **binding_id:** `FPB-0023`
* **formula_id:** `F13`
* **parameter:** PAR-048 (EXCURSION_MIN)
* **declared value:** `max(1,ceil(ATR14_ticks*1/20))`
* **unit:** `ticks`
* **gate:** `G2`
* **boundary rule:** Equality passes.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: State remains ACTIVE.
* **evidence refs:**
    * `source_binding_id=FPB-0023`
    * `rc2_source_digest=bcfdded2061e307d2bc7e61be60cdc1d08168361a97584a2d75fc1d9f51c0e16`
    * `binding_digest=94b568bcc10af9898bf989a6a77d1f45822425b4a7a7c40676bcc52950e4030a`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0024 — F13 · PAR-049 (RECLAIM_HORIZON)

* **binding_id:** `FPB-0024`
* **formula_id:** `F13`
* **parameter:** PAR-049 (RECLAIM_HORIZON)
* **declared value:** `3`
* **unit:** `finalized bars`
* **gate:** `G2`
* **boundary rule:** Third later bar ordinal 3 fails.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Expire reclaim attempt.
* **evidence refs:**
    * `source_binding_id=FPB-0024`
    * `rc2_source_digest=6e2c1a6cc6a13b9bcb217265539779602a4b6f5db48e674dd731b66c22c52c9a`
    * `binding_digest=930045fdc063fb039b2e2b0eac574798d02ce4223086606d9cd03c50eda81688`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0072 — F13 · PAR-164 (RECLAIM_CLOSE_BUFFER)

* **binding_id:** `FPB-0072`
* **formula_id:** `F13`
* **parameter:** PAR-164 (RECLAIM_CLOSE_BUFFER)
* **declared value:** `max(1,ceil(ATR14_ticks*1/20))`
* **unit:** `ticks`
* **gate:** `G2`
* **boundary rule:** Equality passes.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Remain EXCURSION/expire by horizon.
* **evidence refs:**
    * `source_binding_id=FPB-0072`
    * `rc2_source_digest=bf8e85f899613a6181988244a5765f932fff5d5509df4f79a48b9184a55fc013`
    * `binding_digest=985a1255a91403165f982e74aa6f6f0dc8f7e838b5d03c200e4d5e33950da694`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0073 — F13 · PAR-165 (RECLAIM_HOLD_BARS)

* **binding_id:** `FPB-0073`
* **formula_id:** `F13`
* **parameter:** PAR-165 (RECLAIM_HOLD_BARS)
* **declared value:** `2`
* **unit:** `consecutive finalized bars`
* **gate:** `G2`
* **boundary rule:** Second consecutive close confirms.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Remain pending or expire.
* **evidence refs:**
    * `source_binding_id=FPB-0073`
    * `rc2_source_digest=add75505ef0653c0c96e22a25af583e2815cbb2ad648ee20b1a1ef4e1ee928c1`
    * `binding_digest=72c12e82f49e527a400a7b348a46a061c0fafbac7445b894b90621684f8839cb`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0088 — F13 · PAR-176 (CAP03_EQUAL_SWEEP_ENTRY)

* **binding_id:** `FPB-0088`
* **formula_id:** `F13`
* **parameter:** PAR-176 (CAP03_EQUAL_SWEEP_ENTRY)
* **declared value:** `frozen_equal_level_anchor`
* **unit:** `ticks`
* **gate:** `G3`
* **boundary rule:** No recentering to later pivots.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Candidate abstains when anchor/lineage unavailable.
* **evidence refs:**
    * `source_binding_id=FPB-0088`
    * `rc2_source_digest=806bda731d0742b6793d0a118f705fd65e71daceeac886f771aab813d1e471b5`
    * `binding_digest=028ee14bdd20e479669ae2bdcf5b948b68e9e22e127d95e866d682a161f7c032`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0096 — F13 · PAR-178 (CAP05_SESSION_ENTRY)

* **binding_id:** `FPB-0096`
* **formula_id:** `F13`
* **parameter:** PAR-178 (CAP05_SESSION_ENTRY)
* **declared value:** `completed_session_anchor`
* **unit:** `ticks`
* **gate:** `G3`
* **boundary rule:** Current/incomplete session anchor forbidden.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Candidate abstains SESSION_INCOMPLETE.
* **evidence refs:**
    * `source_binding_id=FPB-0096`
    * `rc2_source_digest=b95e0e5e13558b06291e5278c6c7991f82ae680bea4d42b73164005cece3c7eb`
    * `binding_digest=97b88eef30c5ada8ef6a0897004e8f46f3753bf9b9a67148fcb3ffeacde1bc03`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

---

## Formula F14 — group activation: NOT ACTIVE

*NOT FORMULA-COMPLETE: 0/8 rows proposed ACTIVE — the formula MUST NOT present as active until its entire set is ACTIVE.*

### FPB-0025 — F14 · PAR-050 (MIN_DEPARTURE)

* **binding_id:** `FPB-0025`
* **formula_id:** `F14`
* **parameter:** PAR-050 (MIN_DEPARTURE)
* **declared value:** `max(2,ceil(ATR14_ticks*1/10))`
* **unit:** `ticks`
* **gate:** `G2`
* **boundary rule:** Equality passes.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Touch is formation noise, not first retest.
* **evidence refs:**
    * `source_binding_id=FPB-0025`
    * `rc2_source_digest=6489bff40d51a8794fca0825ec93f5b26bf163cf2ad77f51c7d17c902e848088`
    * `binding_digest=01b12b2f0192a67b61a748811d5990d6286fd461b64806b253955b18d45e23e7`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0038 — F14 · PAR-062 (FIRST_TOUCH_ORDINAL)

* **binding_id:** `FPB-0038`
* **formula_id:** `F14`
* **parameter:** PAR-062 (FIRST_TOUCH_ORDINAL)
* **declared value:** `1`
* **unit:** `touch`
* **gate:** `G3`
* **boundary rule:** Boundary price intersection counts as touch.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Later touches are CONSUMED/no publication.
* **evidence refs:**
    * `source_binding_id=FPB-0038`
    * `rc2_source_digest=84c8c86d13bbf05186af76adafe884517f7ed05b406637ef25c035b016cb71c4`
    * `binding_digest=297d532225db8d522a987a30405d0095fde6ba2adf89ffc501880cbe3f4404ed`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0074 — F14 · PAR-166 (MIN_DEPART_EVENTS)

* **binding_id:** `FPB-0074`
* **formula_id:** `F14`
* **parameter:** PAR-166 (MIN_DEPART_EVENTS)
* **declared value:** `1`
* **unit:** `finalized base bar`
* **gate:** `G2`
* **boundary rule:** Formation bar excluded.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Same-bar contact not a retest.
* **evidence refs:**
    * `source_binding_id=FPB-0074`
    * `rc2_source_digest=84f4d3e1289ecb1d61f4363f07aaf4c16ee791a9afb3e9e4bee8a68b192d64bb`
    * `binding_digest=f34533475397a7d3cc3431af826acf9af54c359f54fc1b830709562276874132`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0075 — F14 · PAR-167 (MIN_DEPART_TIME)

* **binding_id:** `FPB-0075`
* **formula_id:** `F14`
* **parameter:** PAR-167 (MIN_DEPART_TIME)
* **declared value:** `60000`
* **unit:** `ms`
* **gate:** `G2`
* **boundary rule:** Exactly 60000 ms passes after event-count rule also passes.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Contact ignored as formation noise.
* **evidence refs:**
    * `source_binding_id=FPB-0075`
    * `rc2_source_digest=805f8a7755d1b3da6c9352ae6bc66e13b1a0a5a0e50be4e8134c821eb7484743`
    * `binding_digest=82f6e2dd77089835d9cdb78d90ef7b99985f8e9acf444ec7252d44dda5926d25`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0076 — F14 · PAR-168 (CONTACT_PRICE_SOURCE)

* **binding_id:** `FPB-0076`
* **formula_id:** `F14`
* **parameter:** PAR-168 (CONTACT_PRICE_SOURCE)
* **declared value:** `finalized_bar_closed_range_[low,high]`
* **unit:** `ticks`
* **gate:** `G2`
* **boundary rule:** Edge equality counts; forming bar and intrabar reconstruction excluded.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: No touch until valid finalized bar.
* **evidence refs:**
    * `source_binding_id=FPB-0076`
    * `rc2_source_digest=a427c6593aeb0be2409988c05ec671def6c0592cf0e12fa5ab084fee213e235e`
    * `binding_digest=cb9eaf9d80bbc23675714c64cbbf85bd9558011f999653dd8187d969181e9959`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0089 — F14 · PAR-176 (CAP03_EQUAL_SWEEP_ENTRY)

* **binding_id:** `FPB-0089`
* **formula_id:** `F14`
* **parameter:** PAR-176 (CAP03_EQUAL_SWEEP_ENTRY)
* **declared value:** `frozen_equal_level_anchor`
* **unit:** `ticks`
* **gate:** `G3`
* **boundary rule:** No recentering to later pivots.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Candidate abstains when anchor/lineage unavailable.
* **evidence refs:**
    * `source_binding_id=FPB-0089`
    * `rc2_source_digest=00159b31231c614cccc532e56dd630bd01bda4bed9897cc95c302bb294360c9e`
    * `binding_digest=99408cff24d3870a533035400b8def5b36a3bc014650af9e239ef700ccd15e08`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0093 — F14 · PAR-177 (CAP04_CHOCH_ENTRY)

* **binding_id:** `FPB-0093`
* **formula_id:** `F14`
* **parameter:** PAR-177 (CAP04_CHOCH_ENTRY)
* **declared value:** `accepted_break_level`
* **unit:** `ticks`
* **gate:** `G3`
* **boundary rule:** Wick extreme is not substituted.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Candidate abstains if no F09 CHOCH occurrence.
* **evidence refs:**
    * `source_binding_id=FPB-0093`
    * `rc2_source_digest=3a92aeeabe9cb4ee0ae0c061ea46772d6b3c83eb960fbbc7ad987353b0b31ec1`
    * `binding_digest=df798f9b932ca49bc250fe94b50bad8906b13658f25da76ede2db4e7f1aa9599`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0097 — F14 · PAR-178 (CAP05_SESSION_ENTRY)

* **binding_id:** `FPB-0097`
* **formula_id:** `F14`
* **parameter:** PAR-178 (CAP05_SESSION_ENTRY)
* **declared value:** `completed_session_anchor`
* **unit:** `ticks`
* **gate:** `G3`
* **boundary rule:** Current/incomplete session anchor forbidden.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Candidate abstains SESSION_INCOMPLETE.
* **evidence refs:**
    * `source_binding_id=FPB-0097`
    * `rc2_source_digest=89412bef546a4e34d3b6ff91cb6e7f4f7b89fc453ac7fe6555245eb2682d3b05`
    * `binding_digest=b28ecffdf00277aa5b6bb0281263776d8f4755f1865842924a53bebd4af19aaf`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

---

## Formula F15 — group activation: NOT ACTIVE

*NOT FORMULA-COMPLETE: 0/5 rows proposed ACTIVE — the formula MUST NOT present as active until its entire set is ACTIVE.*

### FPB-0026 — F15 · PAR-052 (TFI_WINDOW_TRADES)

* **binding_id:** `FPB-0026`
* **formula_id:** `F15`
* **parameter:** PAR-052 (TFI_WINDOW_TRADES)
* **declared value:** `100`
* **unit:** `trades`
* **gate:** `G2`
* **boundary rule:** Current trade included; oldest excess excluded.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Null with INSUFFICIENT_FLOW.
* **evidence refs:**
    * `source_binding_id=FPB-0026`
    * `rc2_source_digest=4d5bfc340c2fb2aa55c7fb5950d9a8e53526bb90b794d6031336c6c4950d3391`
    * `binding_digest=19370e5043a1f0e6a56d3d790864b82058d51871344f223c193c5f24dfdbc9c0`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0027 — F15 · PAR-053 (TFI_WINDOW_MAX_AGE)

* **binding_id:** `FPB-0027`
* **formula_id:** `F15`
* **parameter:** PAR-053 (TFI_WINDOW_MAX_AGE)
* **declared value:** `2000`
* **unit:** `ms`
* **gate:** `G2`
* **boundary rule:** Both endpoints inclusive.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Older trades excluded.
* **evidence refs:**
    * `source_binding_id=FPB-0027`
    * `rc2_source_digest=ab5cee3d898a69672216951b783d5c919e77c51969353672757f5bde8ca8c21d`
    * `binding_digest=8434c2120404b9136740de3740a305f8c9d17c7de34fa5be2336aabc13e73bed`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0028 — F15 · PAR-054 (TFI_MIN_TRADES)

* **binding_id:** `FPB-0028`
* **formula_id:** `F15`
* **parameter:** PAR-054 (TFI_MIN_TRADES)
* **declared value:** `20`
* **unit:** `trades`
* **gate:** `G2`
* **boundary rule:** 20 passes; 19 null.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Null; required-flow capsule abstains.
* **evidence refs:**
    * `source_binding_id=FPB-0028`
    * `rc2_source_digest=5c704c3647e97cd28f8ff5346b32c779ebe5fcfeddf8614b876400d60f6d4c8e`
    * `binding_digest=0cc6af6b4cc3ea1de81437d13d011ebe030ade022f5e6257bbfacf98a2752891`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0029 — F15 · PAR-055 (FLOW_ATOM_TTL)

* **binding_id:** `FPB-0029`
* **formula_id:** `F15`
* **parameter:** PAR-055 (FLOW_ATOM_TTL)
* **declared value:** `500`
* **unit:** `ms`
* **gate:** `G2`
* **boundary rule:** 500 ms passes; 501 ms stale.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Named abstention FLOW_STALE.
* **evidence refs:**
    * `source_binding_id=FPB-0029`
    * `rc2_source_digest=989dae78061070e5a24865df013a75c164abe63a91a7ab939a54a766fd0967ee`
    * `binding_digest=cb18d7877fb032eb2b4eefa1cc6cd4a6a38365c14f1df71a78bb30c77405fc45`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0077 — F15 · PAR-169 (TRADE_AGGRESSOR_SOURCE)

* **binding_id:** `FPB-0077`
* **formula_id:** `F15`
* **parameter:** PAR-169 (TRADE_AGGRESSOR_SOURCE)
* **declared value:** `venue buyer_is_maker flag`
* **unit:** `enum`
* **gate:** `G2`
* **boundary rule:** No tick-rule fallback.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: TFI null if minimum valid count not met.
* **evidence refs:**
    * `source_binding_id=FPB-0077`
    * `rc2_source_digest=d84ac0fcea5f0f80f298f7fa5e8732927af7f27db0ef0d739c5b769401c83e84`
    * `binding_digest=50d11b3b3971d9b6aa07e8edd0d9aa215326628b97bfa75b48eccd4a460f2f64`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

---

## Formula F16 — group activation: NOT ACTIVE

*NOT FORMULA-COMPLETE: 0/5 rows proposed ACTIVE — the formula MUST NOT present as active until its entire set is ACTIVE.*

### FPB-0030 — F16 · PAR-055 (FLOW_ATOM_TTL)

* **binding_id:** `FPB-0030`
* **formula_id:** `F16`
* **parameter:** PAR-055 (FLOW_ATOM_TTL)
* **declared value:** `500`
* **unit:** `ms`
* **gate:** `G2`
* **boundary rule:** 500 ms passes; 501 ms stale.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Named abstention FLOW_STALE.
* **evidence refs:**
    * `source_binding_id=FPB-0030`
    * `rc2_source_digest=dfb2c363e8c2005d2283f7bf0eaf3f73662c9fecd61a85930907352d4782e034`
    * `binding_digest=40a78f529d866ddd79b71035a95ac812a2321e4f0abefadd8c59cfed36cdfb03`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0032 — F16 · PAR-056 (OFI_WINDOW_UPDATES)

* **binding_id:** `FPB-0032`
* **formula_id:** `F16`
* **parameter:** PAR-056 (OFI_WINDOW_UPDATES)
* **declared value:** `100`
* **unit:** `book updates`
* **gate:** `G2`
* **boundary rule:** Current update included.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Null when sequence invalid/insufficient.
* **evidence refs:**
    * `source_binding_id=FPB-0032`
    * `rc2_source_digest=58afd1aeb68cd08883dedef46676b04b8277e69206a3d63577d9405de5ce5789`
    * `binding_digest=81260fa9a15e4eff78f23b4d4e0c3703cfaff3fb7fffe78204fafdc6374c055f`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0033 — F16 · PAR-057 (OFI_WINDOW_MAX_AGE)

* **binding_id:** `FPB-0033`
* **formula_id:** `F16`
* **parameter:** PAR-057 (OFI_WINDOW_MAX_AGE)
* **declared value:** `1000`
* **unit:** `ms`
* **gate:** `G2`
* **boundary rule:** Both endpoints inclusive.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Older updates excluded.
* **evidence refs:**
    * `source_binding_id=FPB-0033`
    * `rc2_source_digest=c74101275e14a4be8e5e8b53d864a10a02cef05ceb38c37a04b53433e42e991c`
    * `binding_digest=e3371447eabd2e55cf020df002c885fc3f315a76055252b8017630b23f3e0db0`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0034 — F16 · PAR-058 (OFI_MIN_UPDATES)

* **binding_id:** `FPB-0034`
* **formula_id:** `F16`
* **parameter:** PAR-058 (OFI_MIN_UPDATES)
* **declared value:** `20`
* **unit:** `updates`
* **gate:** `G2`
* **boundary rule:** 20 passes; 19 null.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Null; required-flow capsule abstains.
* **evidence refs:**
    * `source_binding_id=FPB-0034`
    * `rc2_source_digest=deb28d503ff6aa360e327a2aaa42d67b7cd5eba1f8b819f4d44c64a428b2f44f`
    * `binding_digest=1083703674af6eea4bf2054cf988d73900448b85d01a63c5972514a7a02a9b64`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0078 — F16 · PAR-170 (OFI_NORMALIZED_VARIANT_ENABLED)

* **binding_id:** `FPB-0078`
* **formula_id:** `F16`
* **parameter:** PAR-170 (OFI_NORMALIZED_VARIANT_ENABLED)
* **declared value:** `false`
* **unit:** `boolean`
* **gate:** `G2`
* **boundary rule:** Enabling requires a new formula/parameter/trial version.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Consumer treats normalized field unavailable.
* **evidence refs:**
    * `source_binding_id=FPB-0078`
    * `rc2_source_digest=280daf460537f16a4bc24c4236eba085896002b2eae7a8ea9c3a9e0645edea50`
    * `binding_digest=5a3184300329ad80293478169b500b5801d22e884324a6f09c02e7ac4a336d3c`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `SUPERSEDED` → canonical target `SUPERSEDED`
    * named refusal / basis: PROPOSED SUPERSEDED: OFI_NORMALIZED_VARIANT_ENABLED superseded by RC4: PAR-170/FPB-0078 -> OFI_NORMALIZED_VARIANT_ACTIVATION=OFF (RC4 control bundle; compiled into RC5_EFFECTIVE_CONSOLIDATION per CO-01).
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

---

## Formula F17 — group activation: NOT ACTIVE

*NOT FORMULA-COMPLETE: 0/4 rows proposed ACTIVE — the formula MUST NOT present as active until its entire set is ACTIVE.*

### FPB-0031 — F17 · PAR-055 (FLOW_ATOM_TTL)

* **binding_id:** `FPB-0031`
* **formula_id:** `F17`
* **parameter:** PAR-055 (FLOW_ATOM_TTL)
* **declared value:** `500`
* **unit:** `ms`
* **gate:** `G2`
* **boundary rule:** 500 ms passes; 501 ms stale.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Named abstention FLOW_STALE.
* **evidence refs:**
    * `source_binding_id=FPB-0031`
    * `rc2_source_digest=6fb93a594afa447bfd06a2f66ae30db9ae9cb24ee8624ce5ad838304f1995b41`
    * `binding_digest=9394c619c7f89a9d5c54c18c563b9488596142be19d03336b475480c47ba9b47`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0035 — F17 · PAR-059 (BOOK_TILT_BAND)

* **binding_id:** `FPB-0035`
* **formula_id:** `F17`
* **parameter:** PAR-059 (BOOK_TILT_BAND)
* **declared value:** `5`
* **unit:** `bps from best`
* **gate:** `G2`
* **boundary rule:** Boundary level included.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Null if denominator zero/book invalid.
* **evidence refs:**
    * `source_binding_id=FPB-0035`
    * `rc2_source_digest=303c210f22bb977e0b88672ae1189e8900d3f23e1093ca79a840381f0e1184ae`
    * `binding_digest=c3302dfa5472313e54b6a5002c3d30d57a5e17224effb6ee6aba8a918900d9f7`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0079 — F17 · PAR-171 (BOOK_TILT_DEPTH_UNIT)

* **binding_id:** `FPB-0079`
* **formula_id:** `F17`
* **parameter:** PAR-171 (BOOK_TILT_DEPTH_UNIT)
* **declared value:** `quote_notional_ticks_steps`
* **unit:** `exact product`
* **gate:** `G2`
* **boundary rule:** Zero total denominator returns null.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Required-flow capsule abstains.
* **evidence refs:**
    * `source_binding_id=FPB-0079`
    * `rc2_source_digest=c00037d4977e5dab7d2883e7f3f9bef73705f01a584444de2c6f5f242940def1`
    * `binding_digest=4b229038b868f2a89c488dad12745db06bc82b4a3c7967b0baeeebbcf63ab35c`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### RC3-FPB-003 — F17 · RC3-PAR-STRUCT-002 (BOOK_TILT_MIN_QUOTE_DEPTH)

* **binding_id:** `RC3-FPB-003`
* **formula_id:** `F17`
* **parameter:** RC3-PAR-STRUCT-002 (BOOK_TILT_MIN_QUOTE_DEPTH)
* **declared value:** `NOT_RATIFIED`
* **unit:** `quote notional across declared bands`
* **gate:** `G2`
* **boundary rule:** BEFORE_DENOMINATOR_DIVISION
* **failure behavior:** F17 returns null; dependent capsule SAFE_HOLD.
* **evidence refs:**
    * `source_binding_id=`
    * `rc2_source_digest=`
    * `binding_digest=186e65c78de2f110a3cf3a4215e6ab2ba667f32aaf2062c5c0d230ea55786caf`
    * `operation_id=`
    * `activation_scope=ORIGIN;G2;instrument/band/formula-version exact scope`
    * `consuming_wiring_ids=W03\|W04`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_RATIFY(RC3-PAR-STRUCT-002)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_RATIFY(RC3-PAR-STRUCT-002): Minimum quote depth is NOT_RATIFIED.
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

---

## Formula F18 — group activation: NOT ACTIVE

*NOT FORMULA-COMPLETE: 0/9 rows proposed ACTIVE — the formula MUST NOT present as active until its entire set is ACTIVE.*

### FPB-0037 — F18 · PAR-061 (MIN_GEOMETRIC_RR)

* **binding_id:** `FPB-0037`
* **formula_id:** `F18`
* **parameter:** PAR-061 (MIN_GEOMETRIC_RR)
* **declared value:** `2/1`
* **unit:** `R`
* **gate:** `G3`
* **boundary rule:** Exactly 2R passes; below by one tick fails.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Candidate abstains GEOMETRY.
* **evidence refs:**
    * `source_binding_id=FPB-0037`
    * `rc2_source_digest=5f38dfa1ee658b53cff6e4bdf13eb56a77c5d129d99c6c958fcb5e0ed3c2d37f`
    * `binding_digest=ce0ab39172a5919b9d7f619d75b8664775363af097263b09eb89e71571a762f4`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0040 — F18 · PAR-064 (TARGET_AVAILABILITY_RULE)

* **binding_id:** `FPB-0040`
* **formula_id:** `F18`
* **parameter:** PAR-064 (TARGET_AVAILABILITY_RULE)
* **declared value:** `target.knowledge_time<=candidate.knowledge_time`
* **unit:** `predicate`
* **gate:** `G3`
* **boundary rule:** Equality passes.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Candidate abstains TARGET_UNAVAILABLE.
* **evidence refs:**
    * `source_binding_id=FPB-0040`
    * `rc2_source_digest=26a0f40b2013f47545d3846fd28f11079be10fd4821d42aa67215b373557ba8e`
    * `binding_digest=d83759edcd8f93d35f96e9e51b7b1941f8a43c450b8ca3aebc74c074528f5f55`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0080 — F18 · PAR-172 (NATURAL_INVALIDATION_BUFFER)

* **binding_id:** `FPB-0080`
* **formula_id:** `F18`
* **parameter:** PAR-172 (NATURAL_INVALIDATION_BUFFER)
* **declared value:** `max(1,ceil(ATR14_ticks*1/20))`
* **unit:** `ticks`
* **gate:** `G3`
* **boundary rule:** Equality at stop triggers invalidation policy; never tighten historically.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Candidate abstains if invalidation edge unavailable.
* **evidence refs:**
    * `source_binding_id=FPB-0080`
    * `rc2_source_digest=e076707cc8d3c79c36325a602415548db6a614558f8d5e925e7e3b5e6768b8be`
    * `binding_digest=97a73fedea8222d3ebb3f76c155969ce698f0393b294f17fb7e4f8cea17271dc`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0081 — F18 · PAR-173 (TARGET_SELECTOR)

* **binding_id:** `FPB-0081`
* **formula_id:** `F18`
* **parameter:** PAR-173 (TARGET_SELECTOR)
* **declared value:** `nearest_positive_reward(preexisting PROTECTED_SWING\|SESSION_LEVEL\|EQUAL_LEVEL)`
* **unit:** `ordered set`
* **gate:** `G3`
* **boundary rule:** Target at entry has zero reward and is excluded.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Candidate abstains TARGET_UNAVAILABLE.
* **evidence refs:**
    * `source_binding_id=FPB-0081`
    * `rc2_source_digest=492427a08407f9c0f5374f19c4a88c32aad16d6259b8ddc8324e938e1c5365e0`
    * `binding_digest=08dcd7db6a1e36c5ba9d62287fa7191090122b1f9c900c4034e1c455716ff419`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0082 — F18 · PAR-174 (CAP01_OB_ENTRY)

* **binding_id:** `FPB-0082`
* **formula_id:** `F18`
* **parameter:** PAR-174 (CAP01_OB_ENTRY)
* **declared value:** `zone_midpoint`
* **unit:** `ticks`
* **gate:** `G3`
* **boundary rule:** Exact midpoint unchanged.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Candidate abstains if midpoint violates zone/grid.
* **evidence refs:**
    * `source_binding_id=FPB-0082`
    * `rc2_source_digest=fd5e17da5dd0f6092fbc61b6402c0f344c399cd857b4f322fb5194a7aeb7c772`
    * `binding_digest=a60e166efd16123269b7d70ed00bb60dbb8233c8b421012d0f181fbca8750546`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0085 — F18 · PAR-175 (CAP02_FVG_ENTRY)

* **binding_id:** `FPB-0085`
* **formula_id:** `F18`
* **parameter:** PAR-175 (CAP02_FVG_ENTRY)
* **declared value:** `zone_midpoint`
* **unit:** `ticks`
* **gate:** `G3`
* **boundary rule:** Exact midpoint unchanged.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Candidate abstains if zone invalid/filled before eligibility.
* **evidence refs:**
    * `source_binding_id=FPB-0085`
    * `rc2_source_digest=cdc9d3f08580ac9d23ad20b7b455788bea4aab451afe3d2c40aff452a17cbc00`
    * `binding_digest=0ba32f60f8d5cb4237218ff372a663fb9c9ae8c1d867bc9ae558a7361fcb2204`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0090 — F18 · PAR-176 (CAP03_EQUAL_SWEEP_ENTRY)

* **binding_id:** `FPB-0090`
* **formula_id:** `F18`
* **parameter:** PAR-176 (CAP03_EQUAL_SWEEP_ENTRY)
* **declared value:** `frozen_equal_level_anchor`
* **unit:** `ticks`
* **gate:** `G3`
* **boundary rule:** No recentering to later pivots.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Candidate abstains when anchor/lineage unavailable.
* **evidence refs:**
    * `source_binding_id=FPB-0090`
    * `rc2_source_digest=096bd2f98b19dd55514c5c9b515db8a8a26d7ca1b743e200c0150320c5916449`
    * `binding_digest=ee2af43da7334ac5727c5d7c3b458ab5d9a3de66505e7bd387cc262a8c73e34e`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0094 — F18 · PAR-177 (CAP04_CHOCH_ENTRY)

* **binding_id:** `FPB-0094`
* **formula_id:** `F18`
* **parameter:** PAR-177 (CAP04_CHOCH_ENTRY)
* **declared value:** `accepted_break_level`
* **unit:** `ticks`
* **gate:** `G3`
* **boundary rule:** Wick extreme is not substituted.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Candidate abstains if no F09 CHOCH occurrence.
* **evidence refs:**
    * `source_binding_id=FPB-0094`
    * `rc2_source_digest=19648f2f01b4847d434c00460a7e954b52f5f5c238cd9f7cf9b72d0c2d6e1418`
    * `binding_digest=82edff4eb88c4e550c13768202bfc0e32abf2d046970daf3a248d734d652ef78`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0098 — F18 · PAR-178 (CAP05_SESSION_ENTRY)

* **binding_id:** `FPB-0098`
* **formula_id:** `F18`
* **parameter:** PAR-178 (CAP05_SESSION_ENTRY)
* **declared value:** `completed_session_anchor`
* **unit:** `ticks`
* **gate:** `G3`
* **boundary rule:** Current/incomplete session anchor forbidden.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Candidate abstains SESSION_INCOMPLETE.
* **evidence refs:**
    * `source_binding_id=FPB-0098`
    * `rc2_source_digest=ffa42b4120c41c245f4fe1066a2162a81c4dbf3221b0fa1fb9ae9c4d080f69e0`
    * `binding_digest=78500bdff3afddac3179da3f86dfe671f1dab3c83881f3cb2b894482d214829d`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

---

## Formula F19 — group activation: NOT ACTIVE

*NOT FORMULA-COMPLETE: 0/1 rows proposed ACTIVE — the formula MUST NOT present as active until its entire set is ACTIVE.*

### FPB-0036 — F19 · PAR-060 (OPPORTUNITY_CLUSTER_WINDOW)

* **binding_id:** `FPB-0036`
* **formula_id:** `F19`
* **parameter:** PAR-060 (OPPORTUNITY_CLUSTER_WINDOW)
* **declared value:** `30000`
* **unit:** `ms`
* **gate:** `G3`
* **boundary rule:** Equality passes; long and short never cluster.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Separate clusters when predicate false.
* **evidence refs:**
    * `source_binding_id=FPB-0036`
    * `rc2_source_digest=0049937a64243859e9169f04ebb34a8472e9fbb35584e5632d4a8ca63c858f5b`
    * `binding_digest=ed89c82f8e5378d4077e88312bac4e3a4933ff905d08cd29ee942b4c9871da42`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

---

## Formula F20 — group activation: NOT ACTIVE

*NOT FORMULA-COMPLETE: 0/8 rows proposed ACTIVE — the formula MUST NOT present as active until its entire set is ACTIVE.*

### FPB-0007 — F20 · PAR-008 (ORDER_QUANTITY_ROUNDING)

* **binding_id:** `FPB-0007`
* **formula_id:** `F20`
* **parameter:** PAR-008 (ORDER_QUANTITY_ROUNDING)
* **declared value:** `FLOOR_TOWARD_ZERO`
* **unit:** `step`
* **gate:** `G6`
* **boundary rule:** Below one step becomes zero and denies/no-ops.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: DENY increase; emergency escalates if residual remains.
* **evidence refs:**
    * `source_binding_id=FPB-0007`
    * `rc2_source_digest=f3feb98f1bee6e528dd428550fb8528e6472ff6f23aa2f4e836da90e2d0881b6`
    * `binding_digest=83d5f519d8f2b9a2eb427d1ac74fb8f9ad7176b8cba7c340021664c5b473bc3c`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0041 — F20 · PAR-066 (EXPOSURE_SNAPSHOT_MAX_AGE)

* **binding_id:** `FPB-0041`
* **formula_id:** `F20`
* **parameter:** PAR-066 (EXPOSURE_SNAPSHOT_MAX_AGE)
* **declared value:** `1000`
* **unit:** `ms`
* **gate:** `G6`
* **boundary rule:** 1000 ms passes.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: DENY new exposure.
* **evidence refs:**
    * `source_binding_id=FPB-0041`
    * `rc2_source_digest=72fd201177bbe749a4096baaf72de1c207a696aa6f85d0bc1c182dbd0bc01cef`
    * `binding_digest=9c8b30a76eaf26fc6f0b741a482a2c418c87935dc804e9f707d016511f843cf1`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0042 — F20 · PAR-069 (CANARY_RISK_BUDGET)

* **binding_id:** `FPB-0042`
* **formula_id:** `F20`
* **parameter:** PAR-069 (CANARY_RISK_BUDGET)
* **declared value:** `min(NAV*1/10000,10 USDT)`
* **unit:** `USDT`
* **gate:** `G7`
* **boundary rule:** Round final quantity down; if venue minimum exceeds budget, deny.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: No order; never increase budget implicitly.
* **evidence refs:**
    * `source_binding_id=FPB-0042`
    * `rc2_source_digest=71212efe90115004599b90f98ed2582803bef1c32d8d776c53e5b709324a0e5e`
    * `binding_digest=3f13735203dbcde883a242851ace2edec415e94cf6a41fa841f5280ecd39dfc9`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0043 — F20 · PAR-070 (PRODUCTION_RISK_BUDGET)

* **binding_id:** `FPB-0043`
* **formula_id:** `F20`
* **parameter:** PAR-070 (PRODUCTION_RISK_BUDGET)
* **declared value:** `NOT_RATIFIED`
* **unit:** `bps NAV and quote cap`
* **gate:** `G9`
* **boundary rule:** No value means false/denied, not zero-risk approval.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: SAFE_HOLD; G9 cannot pass.
* **evidence refs:**
    * `source_binding_id=FPB-0043`
    * `rc2_source_digest=72d2022cd2d0e324916e6d57143ad775c8d933eb63b8983628c9eb22ecf552dc`
    * `binding_digest=8e2585aa85a95af13fa573f756a5a3d3a4fa0fd778bbb401d5fc1bf36bee07c0`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0044 — F20 · PAR-072 (PRODUCTION_GROSS_EXPOSURE_CAP)

* **binding_id:** `FPB-0044`
* **formula_id:** `F20`
* **parameter:** PAR-072 (PRODUCTION_GROSS_EXPOSURE_CAP)
* **declared value:** `NOT_RATIFIED`
* **unit:** `bps NAV`
* **gate:** `G9`
* **boundary rule:** Absent/invalid never inherits canary value.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: SAFE_HOLD; G9 cannot pass.
* **evidence refs:**
    * `source_binding_id=FPB-0044`
    * `rc2_source_digest=a086220e796bdf3662034983b2e4afd7cca85d993ea3d6816c80338b78d68443`
    * `binding_digest=f8c052821677df8de8a8fdc0cf1b3d070201fe95d108fc2feaeea06800ec106c`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0047 — F20 · PAR-078 (FEE_RATE_SOURCE)

* **binding_id:** `FPB-0047`
* **formula_id:** `F20`
* **parameter:** PAR-078 (FEE_RATE_SOURCE)
* **declared value:** `venue account fee tier snapshot`
* **unit:** `quote per notional`
* **gate:** `G6`
* **boundary rule:** Snapshot must be <=24 h and digest-bound.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: E08 denies if fee unknown; E10 outcome unresolved.
* **evidence refs:**
    * `source_binding_id=FPB-0047`
    * `rc2_source_digest=c5b0a45694bb5acda06d7d59475a21165ec28340622f88144968bf8af7a7bd36`
    * `binding_digest=2341ad7b892aade02208e7b0bd6688da2fedd0a8f5696f16b14c276ed3d0669f`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0049 — F20 · PAR-079 (ADVERSE_COST_BUFFER_PER_SIDE)

* **binding_id:** `FPB-0049`
* **formula_id:** `F20`
* **parameter:** PAR-079 (ADVERSE_COST_BUFFER_PER_SIDE)
* **declared value:** `2`
* **unit:** `bps notional`
* **gate:** `G6`
* **boundary rule:** Two sides total 4 bps; no netting with rebates.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: DENY if cost cannot be represented.
* **evidence refs:**
    * `source_binding_id=FPB-0049`
    * `rc2_source_digest=d192810d79c10a0f59296d67550bd0e7b8ffabbae8f9f5b25b1db5c1a4b5acc6`
    * `binding_digest=b686c94d16c8826d6f687636412325c9dae7fa502a412a6456864098c70d057b`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0050 — F20 · PAR-080 (MIN_NOTIONAL_AND_MAX_QTY)

* **binding_id:** `FPB-0050`
* **formula_id:** `F20`
* **parameter:** PAR-080 (MIN_NOTIONAL_AND_MAX_QTY)
* **declared value:** `current instrument/account filter snapshot`
* **unit:** `venue units`
* **gate:** `G6`
* **boundary rule:** If rounded quantity violates minimum, deny rather than round up.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: E08 DENY.
* **evidence refs:**
    * `source_binding_id=FPB-0050`
    * `rc2_source_digest=d967b00e6ca37d32cc82b0d439785797e787589b5b4d7f8425e1a4c70e195c34`
    * `binding_digest=a089e079db97bafdb09cf6922a66221309a24aed92fe2b7d56da9e4dda308453`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

---

## Formula F21 — group activation: NOT ACTIVE

*NOT FORMULA-COMPLETE: 1/10 rows proposed ACTIVE — the formula MUST NOT present as active until its entire set is ACTIVE.*

### FPB-0003 — F21 · PAR-006 (BUY_PRICE_ROUNDING)

* **binding_id:** `FPB-0003`
* **formula_id:** `F21`
* **parameter:** PAR-006 (BUY_PRICE_ROUNDING)
* **declared value:** `FLOOR_TO_TICK`
* **unit:** `tick`
* **gate:** `G6`
* **boundary rule:** Exact grid value stays unchanged.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: REFUSE command when rounding policy absent.
* **evidence refs:**
    * `source_binding_id=FPB-0003`
    * `rc2_source_digest=71beb251a8de8791a1bef61770a45cdb80cc80332b76b5657d2c3b1d84a98c95`
    * `binding_digest=7c0a10dab5fa130779abf5dd668637b03752c00ad191705b5df0808209e39710`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0005 — F21 · PAR-007 (SELL_PRICE_ROUNDING)

* **binding_id:** `FPB-0005`
* **formula_id:** `F21`
* **parameter:** PAR-007 (SELL_PRICE_ROUNDING)
* **declared value:** `CEIL_TO_TICK`
* **unit:** `tick`
* **gate:** `G6`
* **boundary rule:** Exact grid value stays unchanged.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: REFUSE command when rounding policy absent.
* **evidence refs:**
    * `source_binding_id=FPB-0005`
    * `rc2_source_digest=2ac67b1e13cd8610402ccaaa94aeec1074de4bdee4059134993fbcecd4e44158`
    * `binding_digest=ade1347859959cb3e93fd8303919d79b9238048d4290a7bc6c348edf375baddc`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0051 — F21 · PAR-081 (NORMAL_PATH_TAKER_ALLOWED)

* **binding_id:** `FPB-0051`
* **formula_id:** `F21`
* **parameter:** PAR-081 (NORMAL_PATH_TAKER_ALLOWED)
* **declared value:** `false`
* **unit:** `boolean`
* **gate:** `G6`
* **boundary rule:** No exception by timeout.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Cancel/expire and record no-fill.
* **evidence refs:**
    * `source_binding_id=FPB-0051`
    * `rc2_source_digest=67fc53a34fb49753061f5962aac52af634d75eb56bb6e9fcadeb08192bbc5aec`
    * `binding_digest=05627eaaf50072b1372851b19c5f6d730c5209ba7273ba6a4365e75449bdeea2`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0052 — F21 · PAR-082 (MAKER_MAX_REPRICES)

* **binding_id:** `FPB-0052`
* **formula_id:** `F21`
* **parameter:** PAR-082 (MAKER_MAX_REPRICES)
* **declared value:** `3`
* **unit:** `replacements`
* **gate:** `G6`
* **boundary rule:** Initial submit is ordinal 0; reprices 1,2,3; fourth forbidden.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Cancel and expire purpose.
* **evidence refs:**
    * `source_binding_id=FPB-0052`
    * `rc2_source_digest=2fd8b92d7a12a6a9c8f695c45285eb0d609bd6e0d9a486ab2599d2afb5fe94ff`
    * `binding_digest=d87a2b9d1e62e51c926a879715171bf287feefa26007497eebc855084d5e7596`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0053 — F21 · PAR-083 (MAKER_MIN_REPRICE_INTERVAL)

* **binding_id:** `FPB-0053`
* **formula_id:** `F21`
* **parameter:** PAR-083 (MAKER_MIN_REPRICE_INTERVAL)
* **declared value:** `5000`
* **unit:** `ms`
* **gate:** `G6`
* **boundary rule:** 5000 ms passes.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Wait; never burst replace.
* **evidence refs:**
    * `source_binding_id=FPB-0053`
    * `rc2_source_digest=bb195ea5846097db96c6aa1147b819c7e6b2b8fcdee3ae233feaaa1513b3204a`
    * `binding_digest=8b3bbf8adf90dd4962b0a58d8b418acbc4d7f1e6a3e4e91538b585d5d060d2c9`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0054 — F21 · PAR-084 (MAKER_ORDER_TTL)

* **binding_id:** `FPB-0054`
* **formula_id:** `F21`
* **parameter:** PAR-084 (MAKER_ORDER_TTL)
* **declared value:** `30000`
* **unit:** `ms`
* **gate:** `G6`
* **boundary rule:** At exact expiry, cancel/expire before fill assumption.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Cancel and reconcile; no taker fallback.
* **evidence refs:**
    * `source_binding_id=FPB-0054`
    * `rc2_source_digest=3f7e433476b53cb4650cbd8fba73dfe49907501696bd7cb039a8ed2432794edf`
    * `binding_digest=d56b9ae5884c75ac1360f366e9d4482e999b40d2aada4c0a184d77f357ab7e38`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0083 — F21 · PAR-174 (CAP01_OB_ENTRY)

* **binding_id:** `FPB-0083`
* **formula_id:** `F21`
* **parameter:** PAR-174 (CAP01_OB_ENTRY)
* **declared value:** `zone_midpoint`
* **unit:** `ticks`
* **gate:** `G3`
* **boundary rule:** Exact midpoint unchanged.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Candidate abstains if midpoint violates zone/grid.
* **evidence refs:**
    * `source_binding_id=FPB-0083`
    * `rc2_source_digest=51b41fa97dfac517e216c89b8ca73e4009dbb82de6dfeaef055b57a3bead713e`
    * `binding_digest=7445087aca8c9a2208d72f0611ceda536f8febe1c42ba8fe876edd85b106130f`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0086 — F21 · PAR-175 (CAP02_FVG_ENTRY)

* **binding_id:** `FPB-0086`
* **formula_id:** `F21`
* **parameter:** PAR-175 (CAP02_FVG_ENTRY)
* **declared value:** `zone_midpoint`
* **unit:** `ticks`
* **gate:** `G3`
* **boundary rule:** Exact midpoint unchanged.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Candidate abstains if zone invalid/filled before eligibility.
* **evidence refs:**
    * `source_binding_id=FPB-0086`
    * `rc2_source_digest=56e37be729febc288c63d05de2815a3939cc61396b6969a621b236147385c8a2`
    * `binding_digest=ffa4985bbc922e6f340270f0b735937c3fe76e7ab2b7bde24d42999f7e6a9e4c`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0100 — F21 · PAR-180 (MAKER_REPRICE_TRIGGER)

* **binding_id:** `FPB-0100`
* **formula_id:** `F21`
* **parameter:** PAR-180 (MAKER_REPRICE_TRIGGER)
* **declared value:** `best_moves>=1_tick AND prior_price_not_best`
* **unit:** `predicate`
* **gate:** `G6`
* **boundary rule:** One tick passes.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Keep order unchanged.
* **evidence refs:**
    * `source_binding_id=FPB-0100`
    * `rc2_source_digest=99a608cdf91184eae806f45fcd3e9199306316311bad341e58bb846d355f7e42`
    * `binding_digest=6a85a9d5802636c6b75fc638b5a26e2f990d17600d4b087d885710ae826bed22`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### RC3-FPB-004 — F21 · RC3-PAR-EXEC-001 (MAKER_MAX_BOOK_LEVELS)

* **binding_id:** `RC3-FPB-004`
* **formula_id:** `F21`
* **parameter:** RC3-PAR-EXEC-001 (MAKER_MAX_BOOK_LEVELS)
* **declared value:** `5`
* **unit:** `observed same-side nonempty book levels`
* **gate:** `G6`
* **boundary rule:** AFTER_FROZEN_ZONE_BEFORE_GTX_SUBMIT
* **failure behavior:** Empty feasible set refuses; no taker fallback.
* **evidence refs:**
    * `source_binding_id=`
    * `rc2_source_digest=`
    * `binding_digest=ad9920f42b4e995ee6859b54c5951e94729f9554cb6421091d9decf712e66044`
    * `operation_id=`
    * `activation_scope=E09;G6;venue/account/instrument/authorization exact scope`
    * `consuming_wiring_ids=W14\|W15`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `ACTIVE` → canonical target `ACTIVE`
    * named refusal / basis: PROPOSED ACTIVE: Ratified RC3 Maker Law.
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

---

## Formula F22 — group activation: NOT ACTIVE

*NOT FORMULA-COMPLETE: 0/9 rows proposed ACTIVE — the formula MUST NOT present as active until its entire set is ACTIVE.*

### FPB-0004 — F22 · PAR-006 (BUY_PRICE_ROUNDING)

* **binding_id:** `FPB-0004`
* **formula_id:** `F22`
* **parameter:** PAR-006 (BUY_PRICE_ROUNDING)
* **declared value:** `FLOOR_TO_TICK`
* **unit:** `tick`
* **gate:** `G6`
* **boundary rule:** Exact grid value stays unchanged.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: REFUSE command when rounding policy absent.
* **evidence refs:**
    * `source_binding_id=FPB-0004`
    * `rc2_source_digest=a97e6ebe32cb743c836dcb55106359db91758f2b654b79adcc8975ae823c6411`
    * `binding_digest=76dbea76956dc3ec34198c36273c72eebbaef08204a8c02f86e9003a13a86afe`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0006 — F22 · PAR-007 (SELL_PRICE_ROUNDING)

* **binding_id:** `FPB-0006`
* **formula_id:** `F22`
* **parameter:** PAR-007 (SELL_PRICE_ROUNDING)
* **declared value:** `CEIL_TO_TICK`
* **unit:** `tick`
* **gate:** `G6`
* **boundary rule:** Exact grid value stays unchanged.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: REFUSE command when rounding policy absent.
* **evidence refs:**
    * `source_binding_id=FPB-0006`
    * `rc2_source_digest=17ff3862f5374e37a7cea4295c3e7057f0beb51a39183320fe547a8ce08228ae`
    * `binding_digest=c63d11dccc6342bc1d5201b9d2d3e8771820edffaad13aa8796568db20c18b2c`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0008 — F22 · PAR-008 (ORDER_QUANTITY_ROUNDING)

* **binding_id:** `FPB-0008`
* **formula_id:** `F22`
* **parameter:** PAR-008 (ORDER_QUANTITY_ROUNDING)
* **declared value:** `FLOOR_TOWARD_ZERO`
* **unit:** `step`
* **gate:** `G6`
* **boundary rule:** Below one step becomes zero and denies/no-ops.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: DENY increase; emergency escalates if residual remains.
* **evidence refs:**
    * `source_binding_id=FPB-0008`
    * `rc2_source_digest=024b8032f6ce6928c65d92017114731093f979483872d58f4f9256f2f65154ea`
    * `binding_digest=0e28504489098368e85fe1a716c9fa39f964b5c202209e2a9d3a0dacfe02dec9`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0055 — F22 · PAR-090 (EMERGENCY_IOC_MAX_SLIPPAGE)

* **binding_id:** `FPB-0055`
* **formula_id:** `F22`
* **parameter:** PAR-090 (EMERGENCY_IOC_MAX_SLIPPAGE)
* **declared value:** `10`
* **unit:** `bps`
* **gate:** `G6`
* **boundary rule:** Exact bound included; fill worse than bound impossible for limit IOC.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Residual remains; retry within budget or escalate.
* **evidence refs:**
    * `source_binding_id=FPB-0055`
    * `rc2_source_digest=af08b644c1e6441e9d99e9221c47101a96d014ea724272e89156dea8919b6a0f`
    * `binding_digest=6926fc56bfdda524bed55ce1d189bbe6c450daa7acaff2f5d4d06811c99c675b`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0056 — F22 · PAR-091 (EMERGENCY_IOC_MAX_ATTEMPTS)

* **binding_id:** `FPB-0056`
* **formula_id:** `F22`
* **parameter:** PAR-091 (EMERGENCY_IOC_MAX_ATTEMPTS)
* **declared value:** `3`
* **unit:** `attempts`
* **gate:** `G6`
* **boundary rule:** Ordinals 1-3 allowed; 4 forbidden.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Stop automation and page owner with residual.
* **evidence refs:**
    * `source_binding_id=FPB-0056`
    * `rc2_source_digest=f899333cc9b669b86c453958b59d8f3e27770d5a8731f396f15a1a03e64e4163`
    * `binding_digest=109a2e69560fd98f247ca26301dc026c5263eeeef50e428b1683104add321657`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0057 — F22 · PAR-092 (EMERGENCY_IOC_RETRY_INTERVAL)

* **binding_id:** `FPB-0057`
* **formula_id:** `F22`
* **parameter:** PAR-092 (EMERGENCY_IOC_RETRY_INTERVAL)
* **declared value:** `1000`
* **unit:** `ms`
* **gate:** `G6`
* **boundary rule:** 1000 ms passes.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Wait; do not reuse stale residual.
* **evidence refs:**
    * `source_binding_id=FPB-0057`
    * `rc2_source_digest=38da439cd01da18f08784a7c3270c6416294b311f4f4c5e71c18bc792773e497`
    * `binding_digest=af133e77f68ece2e0b39a2086322fb8604e0f79f64ba9f02975a6da8dfa48414`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0058 — F22 · PAR-093 (EMERGENCY_POSITION_MONOTONICITY)

* **binding_id:** `FPB-0058`
* **formula_id:** `F22`
* **parameter:** PAR-093 (EMERGENCY_POSITION_MONOTONICITY)
* **declared value:** `abs(after)<abs(before) AND no sign flip`
* **unit:** `predicate`
* **gate:** `G6`
* **boundary rule:** Zero residual is terminal; equal magnitude fails.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Reject command; incident.
* **evidence refs:**
    * `source_binding_id=FPB-0058`
    * `rc2_source_digest=67c5f309dcab08f23bd7db87334b62453212ec7912a119711ec427d7ddb8f1b7`
    * `binding_digest=e328789a71b2d037ca9e666f14127043c74030b8a07c4244b219a9a5d60c4f89`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0101 — F22 · PAR-181 (EMERGENCY_TRIGGER_SET)

* **binding_id:** `FPB-0101`
* **formula_id:** `F22`
* **parameter:** PAR-181 (EMERGENCY_TRIGGER_SET)
* **declared value:** `[PROTECTION_DEADLINE,STOP_DEADLINE,SIGNED_FLATTEN,SHUTDOWN_WITH_EXPOSURE,PROTECTION_UNKNOWN_AFTER_RECONCILE]`
* **unit:** `closed enum`
* **gate:** `G6`
* **boundary rule:** Unknown enum rejects.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: No automated IOC; page owner/SAFE_HOLD.
* **evidence refs:**
    * `source_binding_id=FPB-0101`
    * `rc2_source_digest=796a5d7773734025d0c52ee5f8ca9ea21f5141007ad42b55076eac7ef1d5a31d`
    * `binding_digest=121f757007c738e264f575818beb47223861742e0631f10b9ef176053d0a35cd`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0102 — F22 · PAR-182 (EMERGENCY_MAKER_GRACE_BY_TRIGGER)

* **binding_id:** `FPB-0102`
* **formula_id:** `F22`
* **parameter:** PAR-182 (EMERGENCY_MAKER_GRACE_BY_TRIGGER)
* **declared value:** `{PROTECTION_DEADLINE:0,STOP_DEADLINE:0,SIGNED_FLATTEN:5000,SHUTDOWN_WITH_EXPOSURE:5000,PROTECTION_UNKNOWN_AFTER_RECONCILE:0}`
* **unit:** `ms`
* **gate:** `G6`
* **boundary rule:** At expiry IOC may compile; stale residual forces new reconcile.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: No hidden universal timeout.
* **evidence refs:**
    * `source_binding_id=FPB-0102`
    * `rc2_source_digest=bd67f71347e5fe4f6f65704ef5797217328450a7d2f28c2590ab70fc6d055505`
    * `binding_digest=f2c4cd3c46436d47a02f168b98dbbc920abdd328e753e6e0a26c91391af71d07`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

---

## Formula F23 — group activation: NOT ACTIVE

*NOT FORMULA-COMPLETE: 0/9 rows proposed ACTIVE — the formula MUST NOT present as active until its entire set is ACTIVE.*

### FPB-0045 — F23 · PAR-076 (MAX_DAILY_NET_LOSS)

* **binding_id:** `FPB-0045`
* **formula_id:** `F23`
* **parameter:** PAR-076 (MAX_DAILY_NET_LOSS)
* **declared value:** `NOT_RATIFIED`
* **unit:** `bps NAV and quote cap`
* **gate:** `G7`
* **boundary rule:** Absent value prevents ARMED canary.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: SAFE_HOLD; G7 cannot pass.
* **evidence refs:**
    * `source_binding_id=FPB-0045`
    * `rc2_source_digest=3db8c83bcb6bdb4d55e4ca7d1c9a92bcd7fd8e59944913728c6775124ab59201`
    * `binding_digest=1fef5b9a239d432cc92d58f72b4561358df02b79479923ae9f22fcd0e232a82f`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0046 — F23 · PAR-077 (MAX_PEAK_TO_TROUGH_DRAWDOWN)

* **binding_id:** `FPB-0046`
* **formula_id:** `F23`
* **parameter:** PAR-077 (MAX_PEAK_TO_TROUGH_DRAWDOWN)
* **declared value:** `NOT_RATIFIED`
* **unit:** `bps NAV`
* **gate:** `G7`
* **boundary rule:** Absent value prevents ARMED canary.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: SAFE_HOLD; G7 cannot pass.
* **evidence refs:**
    * `source_binding_id=FPB-0046`
    * `rc2_source_digest=2c939437cc26b7dfe4aae10c3793ca763b8d45218bcdc1d3012f98d62c7a0de6`
    * `binding_digest=96bcff3d81a540b6cda39bfd22f2e2fdc8d05de58c7190845009ab506a283546`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0048 — F23 · PAR-078 (FEE_RATE_SOURCE)

* **binding_id:** `FPB-0048`
* **formula_id:** `F23`
* **parameter:** PAR-078 (FEE_RATE_SOURCE)
* **declared value:** `venue account fee tier snapshot`
* **unit:** `quote per notional`
* **gate:** `G6`
* **boundary rule:** Snapshot must be <=24 h and digest-bound.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: E08 denies if fee unknown; E10 outcome unresolved.
* **evidence refs:**
    * `source_binding_id=FPB-0048`
    * `rc2_source_digest=901c1699113354cdd5e18b085b641b863e634a2acbc5c4aba7379a75bcc04039`
    * `binding_digest=7e87ee09259c64d545d422e443c6c5dfe99ee3860dde1ec2fd9422c492d78930`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0059 — F23 · PAR-096 (NORMAL_AVERAGE_SLIPPAGE_MAX)

* **binding_id:** `FPB-0059`
* **formula_id:** `F23`
* **parameter:** PAR-096 (NORMAL_AVERAGE_SLIPPAGE_MAX)
* **declared value:** `2`
* **unit:** `bps`
* **gate:** `G8`
* **boundary rule:** Strictly less; missing decision reference excludes and lowers completeness.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Economic gate fails.
* **evidence refs:**
    * `source_binding_id=FPB-0059`
    * `rc2_source_digest=db0348b05185c3c9c69df87557d4de475bd4c0d6474b03ef93ad77cc8e8075f2`
    * `binding_digest=0e3fe78a357d661b4271bdc003dcbc3a6555614f79544d8219ad058066fff66f`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0060 — F23 · PAR-097 (MARKOUT_HORIZONS)

* **binding_id:** `FPB-0060`
* **formula_id:** `F23`
* **parameter:** PAR-097 (MARKOUT_HORIZONS)
* **declared value:** `[1,5,30,60]`
* **unit:** `s`
* **gate:** `G6`
* **boundary rule:** Exact horizon included; otherwise null, never interpolated.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Markout null with reason.
* **evidence refs:**
    * `source_binding_id=FPB-0060`
    * `rc2_source_digest=28334ef39a422ecf0624ebe676e61c685e22ebc56b1b8f5315c47f710190ba29`
    * `binding_digest=691f0c4e10cf73601a354a7619f0ce7d58038041d09b1ae10bf1d0efb8076cb3`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0061 — F23 · PAR-098 (FLAT_CONFIRMATIONS_REQUIRED)

* **binding_id:** `FPB-0061`
* **formula_id:** `F23`
* **parameter:** PAR-098 (FLAT_CONFIRMATIONS_REQUIRED)
* **declared value:** `2`
* **unit:** `reconciliations`
* **gate:** `G6`
* **boundary rule:** Two passes; one remains FLAT_PENDING.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Campaign not complete.
* **evidence refs:**
    * `source_binding_id=FPB-0061`
    * `rc2_source_digest=42413ef40af63bfdaf1c679620261c29eb6e6fb731a2bbd9f31e03a393a45ed0`
    * `binding_digest=a1af9a4d7e91c567b5647c1dc9374badd426378b1177ffc74607af8faeb484d9`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0062 — F23 · PAR-099 (MONEY_CONSERVATION_TOLERANCE)

* **binding_id:** `FPB-0062`
* **formula_id:** `F23`
* **parameter:** PAR-099 (MONEY_CONSERVATION_TOLERANCE)
* **declared value:** `0`
* **unit:** `atomic quote/quantity units`
* **gate:** `G6`
* **boundary rule:** Any nonzero unexplained residual fails.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Outcome UNRESOLVED; incident if live.
* **evidence refs:**
    * `source_binding_id=FPB-0062`
    * `rc2_source_digest=21bd95eb1c6f6a27effdc250caa2e2eb95e4ed69405b651fb6757b527e3a7204`
    * `binding_digest=fb14114916b37a95b8c8eccbc8e3eb7090dee28afed4fb1fcc371550a121363b`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0063 — F23 · PAR-123 (CANARY_CUMULATIVE_STOP)

* **binding_id:** `FPB-0063`
* **formula_id:** `F23`
* **parameter:** PAR-123 (CANARY_CUMULATIVE_STOP)
* **declared value:** `2`
* **unit:** `R net loss`
* **gate:** `G7`
* **boundary rule:** Equality -2R triggers.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: SAFE_HOLD and incident; owner review.
* **evidence refs:**
    * `source_binding_id=FPB-0063`
    * `rc2_source_digest=b6c089a80cca2015e4e5809ccafa374e554c1ad9a0346ccfc6b1482ea5ae111d`
    * `binding_digest=0c82bef30a34325bcd0714264094272734fe57d4a5ce4884a5ba5ba616802e48`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

### FPB-0103 — F23 · PAR-183 (FEE_CONVERSION_MAX_AGE)

* **binding_id:** `FPB-0103`
* **formula_id:** `F23`
* **parameter:** PAR-183 (FEE_CONVERSION_MAX_AGE)
* **declared value:** `1000`
* **unit:** `ms`
* **gate:** `G6`
* **boundary rule:** 1000 ms included; no interpolation.
* **failure behavior:** SAFE_HOLD; this binding cannot activate. Preserved RC2 behavior: Fee/net PnL remains null/UNRESOLVED.
* **evidence refs:**
    * `source_binding_id=FPB-0103`
    * `rc2_source_digest=cb1f2e0c438532b36158d58816dc9a71c44ae26a04c6086a37ce4ae76e9ca242`
    * `binding_digest=a1e2b3dc83e058de7e4ad909cfce17b7773ed304e6af499a9a0c76c5fc0b72b3`
    * `operation_id=`
    * `activation_scope=NONE_UNTIL_OWNER_MIGRATES_THIS_SOURCE_ROW`
    * `consuming_wiring_ids=UNRESOLVED_BLOCKING`
    * `registry_source_bundle_digest=b42afe0e57b285eb44eb5969a8069afd3e5c0ab3870735e3600f6becc54bb114`
* **proposed disposition (PROPOSAL ONLY):** `BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2)` → canonical target `BLOCKED`
    * named refusal / basis: BLOCKED_ON_MIGRATION(RC3-TASK-G2-BINDING-V2): Preserved RC2 row has not yet been semantically migrated by RC3-TASK-G2-BINDING-V2; no slot, scope, consumer edge or cardinality is inferred. (NEVER_ACTIVE_UNTIL_RC3_TASK_G2_BINDING_V2_PASSES)
* **owner signature slot:** `PENDING_OWNER` (empty — owner adjudicates + signs; agent never does)

---

## Owner gate (not an agent act)

CO-07 Step 5 — authenticating the exact 105-row bundle per Formula Repair §C.1 (wrong count / duplicate scope / partial set refuses) and driving zero rows left in `BLOCKED_BINDING_V2_MIGRATION` — is the OWNER's adjudication act after signing each worksheet. This document supplies the mechanical worksheets only; it authenticates nothing and signs nothing.

