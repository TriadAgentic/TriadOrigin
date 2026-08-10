# B01C entry gate + offline-preparation design (WP-B01C-01)

**Milestone:** B01C (contract identity, binding capability, domain evidence)
**Repository:** `TriadAgentic/TriadOrigin`
**Predecessor (hard):** validated `B00R_RECEIPT_ANCHOR` — the receipt commit sealing the exact B00R
source merge. **B01C may not become authoritative until that anchor validates.**
**Posture (invariant):** `activation_result=DENIED_SAFE_HOLD`, OFF/OFF/OFF/LIVE.
**Permitted result:** `PASS_REPOSITORY_SAFE_HOLD` only.

> This document is **offline preparation** (analysis + patch design + the state/correction lock). It
> lands no authoritative contract, binding, or receipt change. Per the pack, offline prep may not
> make a downstream branch authoritative, merge, or issue evidence before the predecessor receipt
> anchor exists. The substantive B01C code work (WP-B01C-02..06) is designed here and implemented in
> the engaged session that follows a validated B00R anchor.

---

## 1. B00R dependency contract (consume exactly, never mutate)

B01C consumes the B00R root **byte-for-byte**. It MUST NOT:

- edit `contracts/schemas/triad.evidence_receipt.v3.schema.json` or its golden fixtures in place;
- change receipt-v3 canonicalization, signature algorithm, signer threshold, chronology/tolerance,
  trust registry, or lifecycle law under the same identity;
- replace B00R governance evidence with a B01C self-attestation;
- create a parallel receipt profile or competing correction ledger.

B01C MAY publish a separately identified, content-addressed `B01C_ACCEPTANCE_PROFILE.v1` listing
B01C-specific required evidence, referenced as an **immutable preimage** from the unchanged B00R
receipt-v3 envelope. If the base v3 envelope cannot express a mandatory binding, **STOP** and return
a corrective requirement to B00R — never an in-place mutation (a breaking change is a new receipt
contract identity + signed supersession).

Handoff fields B01C's entry gate must recompute from the B00R closure bundle before any B01C source
branch is authoritative: `b00r_receipt_anchor_id`, receipt merge commit/tree/time, receipt-v3 +
trust-registry digests, ruleset id/digest/effective time + no-bypass proof, and the historical
invalidation-manifest digest (`docs/governance/B00_B07_INVALIDATION_MANIFEST.v1.json`).

---

## 2. Historical B01/B01R disposition (additive, never edited)

The historical B01 and B01R receipts remain **byte-unchanged immutable evidence**. They are already
inventoried in the B00R invalidation manifest with disposition `BUILT_ON_INVALID_ANCESTRY`
(`evidence/receipts/B01.json`, `evidence/receipts/B01R.json`). B01C adds authenticated correction
records under `evidence/corrections/` with disposition `REVOKED` or `SUPERSEDED` — it never edits the
old bytes to appear retroactively valid, and it never reuses the old B01/B01R receipt as ancestry.

Historical governance defects carried forward for correction (each gets a forward correction record,
not a history rewrite):

| ID | Defect | Correction |
|---|---|---|
| `B01C-GOV-01` | PR #9 merged before its later review; threads unresolved | New final head + independent pre-merge approval |
| `B01C-GOV-02` | B01R PR #14 merged before review; receipt PR #15 lacked valid independent closure | Forward-supersede; do not reuse the old receipt as ancestry |
| `B01C-EVD-01` | Historical B receipts: zero bundle hashes, one hash for many evidence IDs, CI labels as reviewers, unkeyed self-hashes, skipped B-series auth | Preserve as negative fixtures; forward-revoke/supersede via the B00R correction ledger |

B01/B01R capabilities are reclassified `UNVALIDATED_LOCKED` until B01C closes.

---

## 3. Defect register → target invariant → implementation plan

Each row is a concrete, agent-testable code change staged for the engaged session. None widens
capability; all fail closed.

### WP-B01C-02 — corrective contract-train release (schema closure)

| ID | Defect (as-built) | Target invariant | Plan |
|---|---|---|---|
| `B01C-CON-01` | `tools/gen_contracts.py::_field_schema` emits bare `{"type":"object"}` / `{"type":"array"}` for safety-significant fields | No safety-significant field is an open object/array; nested members, item schemas, cardinalities, bounds, enums are declared | Extend `_field_schema` to require a typed member/item spec per field profile; add a generator guard that **rejects** a bare object/array in a safety-significant contract; allocate new majors only for schemas whose recursive-mutation corpus proves current bytes unsafe |
| `B01C-CON-02` | generated payloads default `additionalProperties: true` | Safety-significant payload + nested boundaries are closed (`additionalProperties: false`); extension points only where explicitly typed + owned | Default closed in `build_schema`; an explicit per-contract `open_containers` allowlist for the few legitimately-open maps |
| `B01C-CON-04` | published fixtures/contracts previously changed while retaining identity | one identity ⟹ one byte set forever | New additive majors + a signed supersession map; preserve every historical byte (the existing `verify_manifest` additive law + `SUPERSEDED_RC1_PATHS` pattern) |
| `B01C-CON-05` | digest checks accept shape/length without proving strict lowercase hex + preimage equality | exact `[0-9a-f]{64}` + recompute every digest from independently selected bytes | Route every contract-side digest check through `triad_origin.governance.assert_hex64` (built at B00R) + a preimage recompute |

### WP-B01C-03 — authoritative schema engine (fail-closed validation)

| ID | Defect | Target invariant | Plan |
|---|---|---|---|
| `B01C-CON-03` | `contracts.py::_validate_fallback` ignores arrays/bounds/`$ref`/composition/conditional — a schema-valid-but-illegal payload can pass on the fallback path | Authoritative validation REQUIRES the pinned full Draft 2020-12 validator; absence/load-failure ⟹ `SCHEMA_VALIDATOR_UNAVAILABLE`, never fallback PASS | Split `validate()` into an **authoritative** path (jsonschema required; raise `ContractError("SCHEMA_VALIDATOR_UNAVAILABLE")` if absent) and a clearly-labelled **diagnostic** fallback that always reports non-authoritative status; pin `jsonschema` (already in `constraints/ci.txt`) as a hard authoritative dep; add validator-present + validator-absent test lanes (the absent lane must refuse before payload acceptance) |

> ⚠️ **Blast radius (must be handled in the engaged session):** `tools/test_wheel_install.py` and
> `tests/contracts/test_conformance.py::test_fallback_validator_agrees` /
> `test_fallback_enforces_declared_pattern_and_min_length` currently assert the fallback *validates*.
> Under CON-03 the fallback becomes diagnostic-only; those tests move to asserting the
> `SCHEMA_VALIDATOR_UNAVAILABLE` refusal on the authoritative path. This is why CON-03 is not landed
> unattended.

### WP-B01C-04 — authenticated binding bundle + capability

| ID | Defect | Target invariant | Plan |
|---|---|---|---|
| `B01C-BIND-01` | binding rows use recomputable row hashes as integrity, not authenticated bundle identity | externally pinned signature/trust anchor over the exact bundle root | Verify a bundle-root signature under the B00R-style pinned trust registry before constructing any capability |
| `B01C-BIND-02` | `BindingRegistry` validates status counts but ignores declared `row_count` + exact source-bundle preimage | `row_count == len(unique binding_id) == 105`; source digest + inventory-root equality (parameter reuse allowed, ≠ duplicate binding identity) | Add row-count/inventory-root/source-digest equality checks in `load_registry` |
| `B01C-BIND-03` | `DEFAULT_REGISTRY_PATH` → `docs/control/...` (not an installed-wheel resource) | package the canonical bundle; load via `importlib.resources` | Vendor bundle to `src/triad_origin/_control/`; repo-relative paths become test-only |
| `B01C-BIND-04` | `ACTIVE` can carry unresolved value/source metadata; `resolve_for_formula()` returns a partial active subset | refuse sentinels (`TBD`/`UNKNOWN`/`UNSET`/`N/A`/empty/null/wildcard) in any active semantic field; require the formula's complete registered binding set | Sentinel guard + formula-complete set check (one active row cannot hide blocked required rows) |
| `B01C-BIND-05` | `transition.Params` + `transition.require()` allow raw dicts + presence-only checks | public production paths require an unforgeable, immutable `ResolvedParameterBundle` capability constructed only by the authenticated loader | Introduce a sealed `ResolvedParameterBundle` (private construction marker); replace raw `Params` on every public production entrypoint; static + dynamic bypass scans for raw dict access |
| `B01C-BIND-06` | duplicate scope keys / scope collisions not closed independently of `binding_id` uniqueness | reject duplicate IDs, duplicate semantic scope keys, ambiguous precedence, missing/extra/reordered rows | Independent scope-key uniqueness + precedence checks in the loader |

### WP-B01C-05 — identity / attestation / promotion verifier

| ID | Defect | Target invariant | Plan |
|---|---|---|---|
| `B01C-ID-01` | TESTNET promotion satisfied by a present/nonempty but failed/stale/wrong-scope/differently-bound receipt | validate status, result, signature, scope, time, ancestry, material projection, environment isolation | Deny-capable promotion verifier only (no lever set, no venue contact); reuse the B00R receipt-v3 verifier semantics |
| `B01C-ID-02` | identity/attestation equality covers only a subset of build/config/contract/binding/adapter/strategy/account/route material | closed environment-invariant + environment-specific projections with full equality; TESTNET/destination isolation (no account/credential/route reuse) | Publish closed projection contracts under new identities; full-equality checks |

### WP-B01C-06 — domain acceptance profile + evidence, and the plan single-source

| ID | Defect | Target invariant | Plan |
|---|---|---|---|
| `B01C-PLAN-01` | `04_STATUS.md` vs `08_BUILD_CHECKLIST.md` disagree on B01 | both views generated from one B00R milestone-state register | Single register → generate both faces (extends the B00R §B00R status reconciliation) |
| — | domain evidence | `docs/repair/B01C_ACCEPTANCE_PROFILE.v1.json` (signed, content-addressed) enumerates exact test IDs, contract-train release, 105-row inventory, installed-artifact proof, identity-mismatch corpus, capability scans, correction records, safe-hold proof; digest cited by the B01C receipt (does not redefine receipt-v3 law) | Build with `build_evidence_manifest.py` (B00R tool) |

---

## 4. New B01C acceptance CLIs to implement (WP-B01C-04/06)

- `tools/verify_binding_bundle.py --bundle <packaged-bundle> --authority <pinned-authority-preimage>`
- `tools/run_contract_mutations.py --profile B01C --require-all-refused`
- `tools/validate_b_receipt.py --receipt evidence/receipts/B01C.json --require-provider-evidence`
  (consumer of the **unchanged** B00R receipt-v3 profile — no in-place edit)

## 5. Falsification families (staged, from the pack §7)

schema closure · validator availability (`SCHEMA_VALIDATOR_UNAVAILABLE`) · immutability · wire
canonicality · bundle authenticity · inventory (104/106, dup ID, dup scope key, reordered) · active
sentinels · formula completeness · capability forgery (plain dict / copied dataclass / subclass /
reloaded marker / widened scope) · installed artifact (offline wheel load of schemas + bundle) ·
promotion (one-at-a-time mismatch; failed/stale receipt; TESTNET/LIVE reuse) · DARK boundary ·
receipt domain (missing acceptance-profile preimage, stale review, zero digest, skipped auth, wrong
predecessor → the unchanged B00R verifier rejects the B01C receipt).

## 6. STOP conditions (keep DENIED_SAFE_HOLD)

B00R evidence invalid/absent/stale/not-the-base · any edit changes receipt-v3 or a published
identity without a new signed supersession · authoritative validation can PASS without the full
validator · a raw dict / incomplete-unverified bundle reaches a public production path · bundle
authenticity or the exact 105-row inventory cannot be proven · a TESTNET/LIVE check treats presence
as success · installed artifacts depend on repo-relative resources · any venue/credential/order/
admission/sizing/execution/fill/P&L/outcome capability appears · required CI skipped / review
late-stale-self / a P0/P1 remains / bypass · any evidence digest lacks a one-to-one immutable
preimage.

## 7. Status

- **Offline-prep produced:** this entry-gate + the WP-B01C-02..06 design/defect register.
- **Blocked (owner-gated):** B01C cannot become authoritative until `B00R_RECEIPT_ANCHOR` validates.
- **Next engaged session:** implement WP-B01C-02 (schema closure) → WP-B01C-03 (fail-closed
  validator, with the test-lane migration) → WP-B01C-04 (sealed `ResolvedParameterBundle`) →
  WP-B01C-05 (projection verifier) → WP-B01C-06 (acceptance profile), each with its falsification
  slice, then the source-PR/receipt cadence off the validated B00R anchor.
