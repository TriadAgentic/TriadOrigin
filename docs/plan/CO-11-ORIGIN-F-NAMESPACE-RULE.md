# CO-11 · `ORIGIN-F##` namespace disambiguation rule

**Change order:** CO-11 of `TRIAD-ORIGIN-V7-CHANGE-ORDERS-2026-08-12` (v1.0.0)
**Plane:** documentation namespace law only — no runtime, contract, formula, or posture change.
**Posture (invariant):** `DENIED_SAFE_HOLD`; levers `OFF/OFF/OFF/LIVE`.
**Disposition:** `RULE_TEXT_PREPARED / PENDING_OWNER_RATIFICATION` — this document binds nothing
until the signature slot below is filled by the owner. Until then the linter runs report-only.

---

## The rule (verbatim, for one-line owner ratification)

> Every cross-estate document, dashboard label, and work order referencing a TRIAD ORIGIN
> formula uses the `ORIGIN-F##` prefix (two digits, leading zero: `ORIGIN-F00` … `ORIGIN-F23`).
> Bare `F#` (single digit, no leading zero) remains **reserved for estate filter fields**
> (`F2` = OI, `F3` = funding, `F4` = liq_flush, `F5` = volume, and their siblings). Linters on
> the docs repositories enforce the rule.

### Why

The estate filter-field namespace (`F2`/`F3`/`F4`/`F5` …) and the Origin formula namespace
(`F00`–`F23`) collide the moment either appears bare in shared prose, dashboards, queries, or
work orders. A collided reference is a mis-routed order waiting to happen. The `ORIGIN-F##`
prefix makes every Origin formula reference self-identifying; the bare single-digit form stays
unambiguously an estate filter field.

### Scope and mechanics in THIS repository

- The linter is `tools/lint_origin_f_namespace.py` and scans `docs/plan/*.md` in this
  repository only (per the CO-11 build order; other repositories carry their own linters).
- A **bare `F#`** — the letter `F` followed by exactly one digit, not preceded by an
  identifier character or `ORIGIN-`, not followed by a further digit or letter — is flagged
  outside fenced code blocks and inline code spans.
- A **malformed Origin reference** — `ORIGIN-F` followed by exactly one digit — is also
  flagged: Origin references always carry two digits.
- `ORIGIN-F##` (two digits) is compliant. `F00`–`F23` two-digit forms inside this repository's
  own internal plan prose are the Origin-internal spelling and are not flagged by this linter;
  the `ORIGIN-` prefix is mandatory in **cross-estate** contexts.
- Fenced code blocks (```` ``` ````) and inline code spans (`` ` ``) are exempt: quoted
  spreadsheet cells, regexes, and historical evidence strings are data, not references.
- **Default mode is report-only** (exit 0, findings printed). `--enforce` fails the run on any
  finding and is reserved for CI **after** the owner signs this rule and the existing
  estate-filter-field rows in `docs/plan/` are either annotated or re-keyed. Flipping CI to
  `--enforce` is part of the ratification act, never an agent default.

### Known pre-existing bare `F#` rows (report-only findings, preserved, not silently rewritten)

At preparation time the linter reports existing bare single-digit `F#` tokens in
`docs/plan/00_MASTER_PLAN.md` (estate filter-field census lines), and
`docs/plan/09_OPEN_QUESTIONS.md` (historic question-row IDs `F1`–`F4`). These are estate
filter-field or row-ID uses — the *reserved* meaning — and are left byte-unchanged here;
re-keying the question-row IDs is a plan-owner act recorded in its own PR, not a silent edit
under CO-11.

---

## Signature slot

| Field | Value |
|---|---|
| Rule ratification | **PENDING** |
| ratified_by | `PENDING-OWNER` |
| signature | `PENDING_SIGNATURE` |
| effective (enforce mode in CI) | not before ratification |

An agent may prepare this rule; only the owner may ratify it. Until ratification the linter's
`--enforce` mode must not be wired into a required CI stage.
