# 06 · Supplied RC2 Source Inventory

These hashes identify the files supplied for the 2026-08-09 audit. They are evidence inputs, not a
claim that the package is complete or ratified.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `index.html` | 8,000 | `042f6bea59f897add75dd108632cdd22d90382350a290f8f5a0873fa2e636568` |
| `TRIAD_ORIGIN_V7_IMPLEMENTATION_CONTROL_WORKBOOK_1.0.0_RC2.xlsx` | 669,712 | `2b60d1d4a40456948eff8da5a982956d35f144a7e76445839aa937a1282481e4` |
| `02_TRIAD_ORIGIN_V7_WIRING_FORMULA_AND_PLUMBING_GUIDE_1.0.0_RC2.html` | 3,106,927 | `6c12490ba5677177dc6a85818ce6936e3f028c54ccbbb50bc85496d48162573d` |
| `03_TRIAD_ORIGIN_V7_UNAMBIGUOUS_DECLARATIONS_VARIABLES_AND_OBJECTIVE_ACCEPTANCE_1.0.0_RC2.html` | 357,745 | `15a85a4f42de6636cecb86341d2488eb77b13bc452dc682b5dcb3d847d054fb4` |
| Illustrative topology PNG | 2,243,356 | `e4bfc5b549eef6cf7c729d469ab8e78212f1d0d30c011e9dee85797096229f0c` |

## Missing linked members

`index.html` links the following members, but they were not supplied:

- `01_TRIAD_ORIGIN_V7_COMPLETE_IMPLEMENTATION_CHECKLIST_1.0.0_RC2.html`;
- the `canonical/` control bundle and its manifest/digests.

Package status is therefore `INCOMPLETE / SAFE_HOLD`. The workbook can be audited as a catalogue,
but its 1,088-task graph cannot substitute for the missing canonical source bundle.

