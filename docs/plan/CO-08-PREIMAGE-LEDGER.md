# CO-08 — Corpus Preimage Ledger and Claims Cleanup

**DISPOSITION:** `EVIDENCE_RECORD / NO_RECOVERY_BY_INVENTION / OWNER_PACKAGING_STEPS_PENDING`.
Executed under `TRIAD-ORIGIN-V7-CHANGE-ORDERS-2026-08-12` CO-08 (steps 1–3 in-repo; step 4 is
an external-package/owner act, recorded below as PENDING). Posture unchanged:
`OFF/OFF/OFF/LIVE`, `DENIED_SAFE_HOLD`. Nothing here closes any milestone.

**The two-state law (CO-08 step 2):** each declared item is `RECOVERED{sha256 verified}` or
`UNAVAILABLE{declared_hash, search_log}` — **no third state, no invention**. An unavailable
preimage is never reconstructed from a derived view (a workbook-derived view is not an
equivalent replacement for the original bytes).

## 1. Declared-hash sources

| Source of declared hashes | Location |
|---|---|
| RC1 artifact manifest (16 payload rows) | `docs/spec/TRIAD_ORIGIN_V7_ARTIFACT_MANIFEST_1.0.0_RC1.json` |
| RC3 reproducibility input manifest (RC2 canonical inputs) | `docs/control/rc3_normative_overlay.json` → `reproducibility_input_manifest` |
| Change order text (truncated prefixes `82636c6f…`, `33c01f8a…`) | `TRIAD-ORIGIN-V7-CHANGE-ORDERS-2026-08-12` §CO-08; full digests confirmed against the two manifests above |

## 2. Search log (common to every row below)

Executed 2026-08-13, worktree of `TriadAgentic/TriadOrigin` at branch base
`ba495ba90e0e4eff50ed75d2443f9cc12ce6ddcd` (`main`, PR #35 merge).

- **Method A — working tree:** SHA-256 over the full bytes of every file in the checkout
  (`.git/` excluded): **506 files hashed**, compared against every declared digest.
- **Method B — full git history:** `git rev-list --objects --all` (91 commits, every local
  ref including all `wip/*`, `worktree-*`, and `claude/*` branches) piped through
  `git cat-file --batch`; SHA-256 computed over every blob body: **935 blobs hashed**.
  (`git log --all --find-object` is not applicable as ordered: the declared digests are
  SHA-256 *content* hashes, not git object IDs; full-blob enumeration + rehash is the
  equivalent-or-stronger search.)
- **Method C — session uploads:** SHA-256 over all **23 files** in this session's upload set.

Result: **zero matches** for any of the 20 declared digests in any of the three corpora.

## 3. The preimage ledger — 20 items, all `UNAVAILABLE`

Every row: `UNAVAILABLE{declared_hash, search_log: §2 (methods A+B+C, 0 matches)}`.

### 3.1 RC1 (2 items — the two payloads the RC1 manifest declares that the vendored corpus lacks)

| # | Item | Declared bytes | Declared SHA-256 | State |
|---|---|---:|---|---|
| 1 | RC1 `README.md` | 2,015 | `82636c6f447f2e430f14d2b66ab09ec760989fe5751936360816fba4ca7d2387` | UNAVAILABLE |
| 2 | RC1 `TRIAD_ORIGIN_V7_COMPLETE_MASTER_SPECIFICATION_1.0.0_RC1.html` | 3,993,202 | `33c01f8ab73fefd0af4a0660ce63127b954b15b94182470f4c088ac7d20b5da8` | UNAVAILABLE |

Note on #2: `docs/plan/06_RC2_SOURCE_INVENTORY.md` records this hash as *authenticated at
B00 intake* ("supplied … same ✅") and then "registered by hash, not vendored". The bytes are
not in the repository, in any git ref, or in this session's uploads today; a past
authentication claim is not a present preimage. State stands `UNAVAILABLE` until the exact
bytes are re-supplied and re-verified.

### 3.2 RC2 — the 18 declared canonical inputs (all under `TRIAD_ORIGIN_V7_IMPLEMENTATION_CONTROL_PACKAGE_1.0.0_RC2/`)

| # | Item | Declared bytes | Declared SHA-256 | State |
|---|---|---:|---|---|
| 3 | `manifest.json` | 6,477 | `45cb4328846fb7220ae02f667f0c45baf7b8b7caa12e7a0e891ae11cd4abb77e` | UNAVAILABLE |
| 4 | `canonical/control_bundle.json` | 5,933,107 | `54346b65a0c8ac5a592a822918d438aefc48e6336c18cd8817de9f38a50dd7d0` | UNAVAILABLE |
| 5 | `canonical/task_registry.csv` | 1,236,213 | `3c76e98620d77b8d1d97cbed72abbbfc227a8c1aabbd0ca8c6ce316c3b374be9` | UNAVAILABLE |
| 6 | `canonical/dependency_edges.csv` | 199,555 | `96e723b766874c6cdad1fe845d4098576d8a740fde0bea075757ab1f2976a316` | UNAVAILABLE |
| 7 | `canonical/acceptance_criteria.csv` | 693,776 | `b93e291af720db336f28880235ea449eb4fd34691ffb9fce55321d7f4c337616` | UNAVAILABLE |
| 8 | `canonical/verification_registry.csv` | 1,168,049 | `991c8095ffcdd00aeff8a43f3ae697f628e7d7d2e2a7dc60828156f2cdc23240` | UNAVAILABLE |
| 9 | `canonical/gate_registry.csv` | 6,524 | `1871a13de1a0c3f98adb98a358b2c230956a41775da599e5bde5c6722be6f1ad` | UNAVAILABLE |
| 10 | `canonical/declared_parameter_registry.csv` | 77,210 | `a6b87bc42fb93f60f68a7382904c8ba839a2b587c20d047a3ec6fae8d0d0a9d5` | UNAVAILABLE |
| 11 | `canonical/formula_registry.csv` | 21,557 | `c7d5eec5c9306013c34d1df8b927133dc0dfad2a55bb517237676b09a8546869` | UNAVAILABLE |
| 12 | `canonical/formula_parameter_bindings.csv` | 17,592 | `6a9b93c42862d09e82257ef9c1eacd4f4493cecca6577768848dadd05a1e5db1` | UNAVAILABLE |
| 13 | `canonical/golden_test_vectors.csv` | 3,849 | `64288db4aeecdf2de023cd61b73b3e0e4a34d1ee0e7c7ce97cc1f09ed1b974bf` | UNAVAILABLE |
| 14 | `canonical/wiring_registry.csv` | 16,328 | `37b4bad25a9a03644b2656d7da5ecaf9064042b01b0c84cddef7f0f5ab8a99f2` | UNAVAILABLE |
| 15 | `canonical/rc1_crosswalk.csv` | 153,862 | `11a690410e9b9bfaedd92681a69f292ce368da64a0716dd30cf3b034338cad6a` | UNAVAILABLE |
| 16 | `canonical/traceability.csv` | 226,792 | `5e13191b66dc8934d6d2b803a793d2103d741dba2dbf44df4ebfc912aa7b8357` | UNAVAILABLE |
| 17 | `canonical/source_registry.csv` | 2,927 | `e851a4c4e016d0c9593f7a09d4b3923b8f8b664f169b6458749df700941536cc` | UNAVAILABLE |
| 18 | `schemas/evidence_receipt.schema.json` | 6,112 | `ff28622a4d794e75b5f9a54d39f1f0dea4e74a8f553925dd5901d2c9d2bf1e85` | UNAVAILABLE |
| 19 | `schemas/gate_receipt.schema.json` | 4,198 | `7eaf0977caf231be4318a352a89ea42064c9b03b630846368a69eadfe0e8f5ff` | UNAVAILABLE |
| 20 | `schemas/task_status_event.schema.json` | 4,657 | `d624317f83ea01a1381dde81053398fcddb47cf5d699604286cec0d8ff0b46d8` | UNAVAILABLE |

Rows 3–20 declared bytes/hashes are quoted verbatim from the RC3
`reproducibility_input_manifest`. The RC3 master HTML embeds *derived* registries (extracted
into `docs/control/`), and the RC2 workbook carries a *view* of them — neither is the original
canonical bytes, and neither is claimed as a recovery.

## 4. Overclaim-string audit (CO-08 step 3) and edits made

Because **every item above is UNAVAILABLE**, CO-08 step 3 is in force: strip/correct
"full", "complete", "independently reproducible", "post-RC4 effective" on claim surfaces, and
correct the source-law README's effective-law line to point at V3 + RC5-pending.

Grep scope: repository claim surfaces (`README.md`, `docs/SPEC_INDEX.md`, `docs/control/README.md`,
`docs/governance/README.md`, `docs/plan/*.md`; the `docs/spec*` trees carry no README —
`docs/spec_rc2/index.html` is hash-pinned in `docs/control/SOURCE_HASHES.sha256` and is
therefore frozen historical bytes, not an editable claim surface).

| Surface · line | String found | Adjudication | Action |
|---|---|---|---|
| `docs/plan/06_RC2_SOURCE_INVENTORY.md` — "The package is now **COMPLETE**" | "COMPLETE" | **Overclaim** — contradicted by this ledger (18 RC2 canonical inputs + 2 RC1 payloads UNAVAILABLE); the B00 intake had the presentation artifacts, not the canonical bytes | **EDITED** — corrected with a dated CO-08 correction block; original wording quoted, not erased |
| `docs/control/README.md` — "`rc3_effective_control_bundle.json` … **The effective law.**" | effective-law claim | **Overclaim as stated** — RC3 is pre-RC4-supersession; the ten RC4 supersessions are not compiled in; the post-RC4 effective bundle is RC5 (CO-01, pending) | **EDITED** — line corrected to name RC3-effective-pre-RC4 + RC5-pending |
| `docs/control/README.md` — "The ledger is `REVIEWED_V2`" (B00C section) | stale version claim | **Stale** — `build_ledger.json` now carries `REVIEWED_V3` while `build_ledger_review.v1.json` still binds `REVIEWED_V2` (the CO-05 drift); the README asserted V2 as current | **EDITED** — corrected to point at V3 + the open CO-05 rebinding + RC5-pending (the "ledger V2 / RC3 is the effective law" correction ordered by CO-08 step 3) |
| `README.md` line 18 — "it is incomplete and internally contradictory" | "incomplete" | Not an overclaim — an honest deficiency statement | none |
| `README.md` line 67 — "a complete timeline proving no later head/base mutation" | "complete" | Not an overclaim — a *requirement* on future evidence, not a possession claim | none |
| `docs/SPEC_INDEX.md` — "B00 · Complete/resolve RC2 package…" | "Complete" (verb) | Not an overclaim — milestone scope description, row status reads `BLOCKED / SAFE_HOLD` | none |
| `docs/control/README.md` — "fails without full coverage/agreement" | "full" | Not an overclaim — a verifier requirement statement | none |
| `docs/governance/README.md` — "the full no-bypass facts" | "full" | Not an overclaim — access-scoping instruction | none |
| editable claim surfaces | "independently reproducible" | **Zero occurrences** on any editable claim surface (README/plan docs) | none — enforced by `tests/plan/test_no_overclaim.py` |
| editable claim surfaces | "post-RC4 effective" | **Occurs only in corrective / naming context** — `docs/control/README.md` NAMES `RC5_EFFECTIVE_CONSOLIDATION` as the post-RC4 effective bundle (a true naming, not a package possession-claim) and NEGATES the claim for the RC3 bundle ("neither … is the post-RC4 effective law"); the RC5 compiler docstring names itself. **Not an overclaim.** (The earlier "zero occurrences" row was inaccurate: the CO-08 step-3 correction itself introduced the RC5-naming reference.) | none — the machine guard `tests/plan/test_no_overclaim.py` permits ONLY the RC5-naming / negating context and fails any package possession-claim |

## 5. CO-08 step 4 — PENDING (external package, owner/packaging act)

Step 4 (repackage with every permitted preimage and build tool; the **51**
`SOURCE_HASHES.sha256` entries resolving from the *package* root; the four broken nested links
fixed; a truthful validation report) addresses the external distribution package, not this
repository: the in-repo `docs/control/SOURCE_HASHES.sha256` pins **29** repository artifacts
and is a frozen integrity anchor this change set may not and does not modify (CO-01 stop-rule
discipline: RC3/RC4 bytes and their pins are never mutated here). Step 4 is recorded
**PENDING — owner/packaging lane**, blocked on the UNAVAILABLE rows above being re-supplied
or the package claims being cut down to the verified subset.

## 6. Acceptance state against CO-08

- Complete verified corpus: **NO** — this is the explicit `UNAVAILABLE` ledger instead
  (the lawful alternative the order names).
- Overclaim strings on editable claim surfaces: corrected as tabled in §4; frozen hash-pinned
  historical bytes are exempt by construction and named as such.
- Package-relative link validation (step 4): **PENDING** with the packaging step.
