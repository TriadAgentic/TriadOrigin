# scan_secrets self-hit report (self-reference experiment)

Date: 2026-08-09. Subject repo: `/home/user/TriadOrigin` (branch `b00-b07-review`, read-only).
Law source: the frozen runner `audit_package/triad_origin_b01_b10_audit.py` v1.2.0,
SHA-256 `12c8896479b902165fa2c6d3e7565ea8402b49fcfe2d044f6fd69153926d35a2` (verified before use).
Scanner: the staged mirror `tools/scan_secrets.py` (TEXT_SUFFIXES runner L243-246 and the 17
SECRET_PATTERNS runner L248-270 copied verbatim; enumeration/filter/read law mirrors runner
L2333-2337, L2351-2355, L2394-2407; byte-equality pinned by differential tests).

## Method

All tracked files enumerated with `git ls-files -z`; regular files with a TEXT_SUFFIXES
suffix and size <= 8_000_000 bytes read as UTF-8 (`errors="replace"`); each of the 17
patterns searched once per file (at most one hit per pattern-file pair, the runner's law).
421 tracked text files scanned.

NOTE ON THIS REPORT'S OWN TEXT: matched spans are deliberately paraphrased, never quoted
verbatim, so this report itself scans clean if it is ever tracked (verified empirically).

## Full hit list (4 hits, all pattern `session_assignment`)

| # | pattern | file | line | matched construct (paraphrased, not verbatim) |
|---|---------|------|------|-----------------------------------------------|
| 1 | session_assignment | `audit_package/triad_origin_b01_b10_audit.py` | 3794 | the `start_new_session` keyword argument of `subprocess.Popen`, whose value expression `(os.name ...)` supplies 8+ non-delimiter characters after the equals sign |
| 2 | session_assignment | `src/triad_origin/contracts.py` | 184 | a three-letter local variable (schema-id abbreviation) assigned from `schema_id or declared` |
| 3 | session_assignment | `src/triad_origin/structures/structure_state.py` | 310 | the same three-letter local variable assigned from an `ids.structure_id(...)` call |
| 4 | session_assignment | `tests/structures/test_capsules.py` | 89 | the same three-letter identifier used as a dict-comprehension key followed by a colon and a call expression |

Why these match: the `session_assignment` regex has NO word boundary on its trigger
alternatives, so the trailing `session` inside `start_new_session` anchors it (hit 1), and the
bare three-letter alternative anchors mid-identifier wherever that abbreviation is followed by
an equals sign or colon plus 8+ non-delimiter characters (hits 2-4). All four are false
positives — no real credential exists in any of them.

## (a) Does the runner's own vendored copy self-hit?

**YES — exactly once** (`session_assignment`, its line 3794), but **not via its pattern
definitions**. The pattern block (runner L248-270) is structurally self-safe: every pattern
interposes regex metacharacters — `(?:...)` groups, escape classes, character classes —
between the trigger word and the payload class, so the pattern literals can never match their
own spelling (e.g. the private-key pattern requires its BEGIN marker to be immediately
followed by the KEY marker, but the source spelling has an optional `(?:...)` group text
in between). The one self-hit comes from an ordinary `subprocess.Popen` keyword argument
elsewhere in the file. Consequence: in a fresh clone of the current tree,
`python tools/scan_secrets.py --tracked --fail-on-hit` exits 1 with the 4 lines above.

## (b) Would the staged tool's source self-hit?

**NO** (verified empirically, and pinned by test
`TestSelfReference::test_tool_source_never_hits_its_own_patterns`). The tool copies the
runner's pattern lines byte-for-byte and therefore inherits the same structural
non-self-match property; its surrounding code avoids every trigger construct. The staged
test file also scans clean (fixture "secrets" are assembled from fragments at runtime, so
no matchable literal exists in the test source), pinned by
`TestSelfReference::test_this_test_source_never_hits_the_patterns`.

## Repair actions (upstream decisions — NOT taken here)

For the required command `scan_tracked_secrets` to exit 0 in a fresh clone, upstream must
resolve the 4 false positives, e.g. by one of:

1. Rename the three-letter schema/structure-id locals (hits 2-4) to a spelling the pattern
   does not anchor on (e.g. `schema_ref` / `struct_id`), and respell hit 1 so fewer than 8
   non-delimiter characters follow the equals sign (e.g. bind the boolean to a short-named
   variable first). NOTE: the runner file is frozen machine law — editing it changes its
   pinned SHA-256, which is its own ceremony.
2. Untrack `audit_package/` (removes hit 1 only; hits 2-4 remain and must still be fixed).
3. Amend the pattern law itself (add word boundaries) — this would fork the tool from the
   frozen runner's law and would break the runner's own independent scan parity; rejected
   unless the runner is re-frozen at a new version.

Until repaired, `--tracked --fail-on-hit` correctly reports these 4 lines and exits 1; the
tool is behaving exactly as the frozen runner's independent scan would.
