# CO-07 — Per-Formula Completeness Matrix

Generated deterministically by `tools/gen_binding_adjudication_worksheets.py` from `docs/control/binding_registry.v2.json`. A formula's group activates only when its ENTIRE set of binding rows is proposed `ACTIVE`. Proposals only — no adjudication, no signature.

| formula | rows | proposed ACTIVE | proposed BLOCKED | proposed SUPERSEDED | proposed REFUSED | group activation |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| F00 | 2 | 2 | 0 | 0 | 0 | ACTIVE |
| F01 | 1 | 0 | 1 | 0 | 0 | NOT_ACTIVE (0/1) |
| F02 | 1 | 0 | 1 | 0 | 0 | NOT_ACTIVE (0/1) |
| F03 | 1 | 0 | 1 | 0 | 0 | NOT_ACTIVE (0/1) |
| F04 | 2 | 0 | 2 | 0 | 0 | NOT_ACTIVE (0/2) |
| F05 | 1 | 0 | 1 | 0 | 0 | NOT_ACTIVE (0/1) |
| F06 | 4 | 0 | 4 | 0 | 0 | NOT_ACTIVE (0/4) |
| F07 | 2 | 0 | 2 | 0 | 0 | NOT_ACTIVE (0/2) |
| F08 | 3 | 0 | 3 | 0 | 0 | NOT_ACTIVE (0/3) |
| F09 | 2 | 0 | 2 | 0 | 0 | NOT_ACTIVE (0/2) |
| F10 | 3 | 0 | 3 | 0 | 0 | NOT_ACTIVE (0/3) |
| F11 | 4 | 0 | 4 | 0 | 0 | NOT_ACTIVE (0/4) |
| F12 | 5 | 0 | 5 | 0 | 0 | NOT_ACTIVE (0/5) |
| F13 | 6 | 0 | 6 | 0 | 0 | NOT_ACTIVE (0/6) |
| F14 | 8 | 0 | 8 | 0 | 0 | NOT_ACTIVE (0/8) |
| F15 | 5 | 0 | 5 | 0 | 0 | NOT_ACTIVE (0/5) |
| F16 | 5 | 0 | 4 | 1 | 0 | NOT_ACTIVE (0/5) |
| F17 | 4 | 0 | 4 | 0 | 0 | NOT_ACTIVE (0/4) |
| F18 | 9 | 0 | 9 | 0 | 0 | NOT_ACTIVE (0/9) |
| F19 | 1 | 0 | 1 | 0 | 0 | NOT_ACTIVE (0/1) |
| F20 | 8 | 0 | 8 | 0 | 0 | NOT_ACTIVE (0/8) |
| F21 | 10 | 1 | 9 | 0 | 0 | NOT_ACTIVE (1/10) |
| F22 | 9 | 0 | 9 | 0 | 0 | NOT_ACTIVE (0/9) |
| F23 | 9 | 0 | 9 | 0 | 0 | NOT_ACTIVE (0/9) |

**Formula-complete ACTIVE groups:** `F00`.

Every other formula has at least one non-ACTIVE row and therefore MUST NOT present as active. Note F21 in particular: a single ACTIVE row (`RC3-FPB-004`, MAKER_MAX_BOOK_LEVELS) of 10 — the 1-of-10 that must never read as an active formula.

