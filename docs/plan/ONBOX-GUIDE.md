# ON-BOX GUIDE — TRIAD Origin Formula Repair + Change Orders

**For:** the account owner / box operator (leesbak@gmail.com).
**What this is:** the steps an agent cannot do — because they touch credentials, external key
material, the box filesystem, or the GitHub org settings — collected in one place, each with its
"why" and its refusal cross-reference. **Nothing here is executed by any agent, in any repository,
or in any session transcript.** Posture is and stays `OFF/OFF/OFF/LIVE`, `DENIED_SAFE_HOLD`.

Companion: `docs/plan/DECISIONS-REQUIRED.md` (the signature/ratification/grant decisions). This
guide is the *action* half; that register is the *decision* half.

> **Golden rule (CO-10):** any credential that has travelled through a document, chat, transcript,
> screenshot, or paste buffer is **EXPOSED** and must be rotated — regardless of whether misuse is
> observed. No secret value ever appears in this guide, the repo, or a session.

---

## O-3 · B00R root closure (do this FIRST — it unfreezes the milestone chain)

The B00R generation-2 corrective source is fully built and its tests pass; closure is
**owner-gated** and fail-closes to `BLOCKED`/`UNAVAILABLE` until you complete four acts on a clean
runner. Canonical procedure: `docs/governance/B00R_ONBOX_OPERATOR_GUIDE.md`. The delta this work
adds:

1. **Authenticate the three root decisions.** Fill and Ed25519-sign, from the templates:
   - `docs/governance/decisions/DEC-AUTHORITY-BUNDLE-002.template.json` → `…-002.json`
   - `docs/governance/decisions/DEC-B00-REPAIR-002.template.json` → `…-002.json`
   - `docs/governance/decisions/DEC-RECEIPT-PROFILE-002.template.json` → `…-002.json`
   Validate: `python tools/validate_governance_snapshot.py` (fails closed on any unsigned/malformed decision).
2. **Externally pin the trust registry.** Produce the real g2 registry from
   `docs/governance/trust/receipt_trust_registry.g2.v1.template.json` → `…g2.v1.json`, and pin its
   digest **outside the repo** (the external anchor — a self-referential in-tree pin cannot
   bootstrap trust). Cross-check: `python tools/validate_authority_root.py`.
3. **Install the no-bypass `main` ruleset** from
   `docs/governance/rulesets/main.ruleset.provider.template.json` via the GitHub org settings
   (required PR + review + status checks, no force-push, no bypass). Verify the live ruleset:
   `python tools/validate_b00r_tag_ruleset.py` and `python tools/github_ruleset_live.py`.
4. **Threshold-sign receipt-v3** on a clean runner → the exact `B00R_RECEIPT_ANCHOR_G2`. Then
   `python tools/b00r_gate.py` must read `PASS_REPOSITORY_SAFE_HOLD`, and `tools/validate_b00r_anchor.py`
   must confirm the anchor. **Only after this does B01C unfreeze** (the only permitted B00R result
   is `PASS_REPOSITORY_SAFE_HOLD`; B01C stays frozen until the exact `B00R_RECEIPT_ANCHOR_G2`
   validates — the generation-1 `B00R_RECEIPT_ANCHOR` is historical evidence, never a B01C
   predecessor).

*Agent status:* the two previously-failing B00R tests are already GREEN (root cause was a missing
local `B00R_RECEIPT_ANCHOR` tag; fetched; zero file changes; CI fetches tags). The G2 closure
artifacts above remain templates awaiting your keys — an agent cannot mint them.

## D-3b · Widen the milestone SOURCE grant (GitHub / CODEOWNERS)

Before any formula-repair **milestone PR** to `main` can pass CI classification, widen the frozen
B00R source grant in `tools/classify_milestone_pr.py` (`ALLOWED_SOURCE_EXACT_PATHS` /
`ALLOWED_SOURCE_PREFIXES`) to admit the formula paths, in an owner-reviewed PR:
`src/triad_origin/structures/`, `src/triad_origin/instrument_math*.py`,
`src/triad_origin/features.py`, `contracts/schemas/`, `contracts/golden/`,
`tests/kernel/`, `tests/structures/`, `tests/formulas/`, `tests/control/`,
`docs/control/formula_repair_overlay.v1.json`. Then pin the newly-granted prefix files in
`docs/control/SOURCE_HASHES.sha256` (`verify_source_hashes.py` will demand it). CO-12's scope-guard
(`tools/verify_pr_scope_guard.py`) keeps the B00R **root** PR governance-only regardless.

## O-1 · CO-10 credential rotation (issuing-side, before B05C)

Full procedure: `docs/plan/CO-10-CREDENTIAL-ROTATION-ONBOX.md`. Every step is OWNER/BOX-ONLY. In
order: for each exposed credential class (venue API keys, tunnel/bearer tokens, Auth0 client
secrets), **rotate/revoke on the issuing side**, install the new secret on the box **read-only**,
and record a **fingerprint** receipt (a truncated non-reversible digest — never the value). No
security attestation (B05C) may issue while any exposed credential is still live.

## O-2 · CO-12 forensic salvage of the off-clone refs

Full record + search log: `docs/plan/CO-12-SALVAGE-INVENTORY.md`. These refs are **absent from the
GitHub clone** — they live only on the box, and the preserve-as-patch-candidates law forbids
reconstructing them by invention:

- `7dbab10` — the `offline/post-g2-integration` branch
- `ef88414` — the B08 work
- `d6795cb` — the status commit (**never a merge base**)
- the dirty integration worktree and the B09 worktree

On the box, run a **forensic inventory by hash** (`git rev-list --objects --all`, `git fsck --lost-found`,
`git reflog`), export any recovered commits as `git format-patch` bundles, and preserve them as
patch candidates. **Do not** `git reset`, `git stash`, or blind-merge; **never** use `d6795cb` as a
merge base. Recovery is yours; the agent recorded only the honest `UNAVAILABLE{declared_ref,
search_log}` disposition.

## Deploy / activation (reference — all gated, none defaulted on)

Arming any live behaviour is out of scope for this repair set and stays behind its own ceremony.
For the record: `venue_environment=OFF / venue_activation=OFF / paper_activation=OFF /
shadow_activation=LIVE` is invariant; a `PROPOSED_MUST_RATIFY` value or a signed decision (D-1..D-6)
changes only *measurement/formula* status, never the money line. There is no on-box "turn it on"
step in this work — by design.

---

## Order of operations (shortest path to a green, mergeable milestone chain)

1. **O-3** B00R root closure → `PASS_REPOSITORY_SAFE_HOLD` (unfreezes B01C).
2. **D-3b** widen the source grant + pin the new files.
3. **D-1** sign the repair PR (`RATIFY_WITH_THIS_REPAIR` laws) + **D-7** assign an independent reviewer.
4. **D-2** ratify the `PROPOSED_MUST_RATIFY` values you want ACTIVE (the rest stay refusing — safe).
5. **D-4 / D-5 / D-6** sign OWNER-TOPO-01, CO-13, CO-11 as you're ready (each unblocks its own consumers).
6. **O-1** credential rotation before any B05C security attestation.
7. **O-2** forensic salvage at your convenience (evidence preservation, not a blocker for the repair chain).
