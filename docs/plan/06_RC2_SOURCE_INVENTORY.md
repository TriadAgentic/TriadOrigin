# 06 · Control-Package Source Inventory

> **CO-08 correction (2026-08-13).** The B00 paragraph below originally read "The package is
> now **COMPLETE**". That claim is withdrawn: the CO-08 preimage scan
> ([`CO-08-PREIMAGE-LEDGER.md`](CO-08-PREIMAGE-LEDGER.md)) finds the 2 RC1 declared payloads
> (`README.md` 2,015 B `82636c6f…`; complete-edition HTML 3,993,202 B `33c01f8a…`) and all
> 18 RC2 declared canonical inputs (manifest, `canonical/control_bundle.json`, 13 registries,
> 3 receipt schemas) **UNAVAILABLE** in this repository, its full git history, and the session
> uploads. The presentation artifacts are present and hash-correct; the canonical original
> bytes are not — the RC3-embedded registries are *derived* extractions, not the declared
> preimages. The corpus is **PARTIAL** until those bytes are re-supplied and hash-verified.

_Updated 2026-08-09 (B00), corrected 2026-08-13 (CO-08). Original B00 wording (withdrawn):
"The package is now COMPLETE: the members recorded missing in the 2026-08-09 audit were
supplied by the operator, and the canonical registries arrive embedded in the RC3 master
document, extracted and vendored under `docs/control/`."_

## Authentication against RC3's own integrity table

RC3 §00 declares SHA-256 hashes for its incorporated sources. Supplied files reproduce them:

| Artifact | Declared by RC3 | Supplied | Match |
|---|---|---|---|
| RC1 complete master spec HTML | `33c01f8ab73fefd0af4a0660ce63127b954b15b94182470f4c088ac7d20b5da8` | same | ✅ |

Additional supplied-file hashes are pinned in
[`docs/control/SOURCE_HASHES.sha256`](../control/SOURCE_HASHES.sha256) (17 vendored artifacts).

## Vendored in this repository

| Location | Contents |
|---|---|
| `docs/spec/` | RC1 modular docs 00–10 + RC1 CSVs + artifact manifest (pre-existing) |
| `docs/spec_rc2/` | RC2 index, complete implementation checklist (**previously missing**), wiring & formula guide, unambiguous declarations, control workbook (**previously missing**) |
| `docs/spec_rc3/` | RC3 Complete Master Specification & Master Document (22.8 MB, embeds the RC2 canonical registries + RC3 overlay + effective bundle) |
| `docs/spec_rc4/` | RC4 Four-Plane Execution & Lever Master Addendum |
| `docs/control/` | Extracted machine-readable law: RC3 overlay schema, normative overlay, **effective control bundle** (1,115 tasks), bundle manifest, validation report, RC3 executable builder, RC4 control bundle (135 tasks), RC4 addendum builder, build ledger + overrides |
| `docs/reports/` | Constitutional sign-off full report, structure-definition cross-engine comparison (2026-08-08) |

## Registered by hash, not vendored (size/duplication)

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| RC1 complete-edition HTML (content = docs 00–10 already vendored; authenticated above) | 3,993,202 | `33c01f8ab73fefd0af4a0660ce63127b954b15b94182470f4c088ac7d20b5da8` |
| RC1 checklist CSV (duplicate of `docs/spec/…RC1.csv`) | 116,135 | `b46fc91c831ee5c00a3c8b06a518c8b805df525e5b54ffd667a6000585b78a5c` |
| RC1 checklist HTML (duplicate of `docs/spec/07_…RC1.html`) | 267,051 | `5a9636a4f0453f81f7cd406cee80549dd4a0cf5481c63e5197a4f9996aa20337` |

## Prior audit rows (2026-08-09 pre-B00) — superseded

The original inventory recorded the RC2 package `INCOMPLETE / SAFE_HOLD` (missing complete
checklist + canonical bundle). That state is closed by this B00 delivery; the historical hashes
remain in git history (`241b301`).
