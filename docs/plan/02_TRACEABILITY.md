# 02 · Traceability and Ownership

This plan classifies requirements before assigning implementation. Status is derived from receipts,
not from the existence of a file.

## Ownership vocabulary

| Class | Meaning |
|---|---|
| `OWN` | ORIGIN runtime is authoritative producer |
| `CONSUME` | ORIGIN validates and consumes an external authoritative fact |
| `VERIFY_ONLY` | Offline/conformance code may verify; runtime does not own |
| `REFERENCE_ONLY` | Needed for end-to-end reasoning, never implemented here |
| `OUT_OF_REPO` | A named external service/repository owns implementation |
| `DEFERRED` | Explicitly deferred with an owner and later gate |

## Wiring ownership

| W IDs | Class | Origin responsibility | Build |
|---|---|---|---|
| W00–W01 | REFERENCE_ONLY | Raw venue/E00 normalization boundary | B09 conformance only |
| W02 | CONSUME | Validate canonical E01 state, order, quality, watermark, identity | B01–B03/B08 |
| W03–W06 | OWN | Features, structures, lifecycle, treatment candidates | B03–B08 |
| W07–W09 | OUT_OF_REPO | Legacy control, comparator authority, router/governance | B09 frozen-fixture comparison only |
| W10–W13 | REFERENCE_ONLY | E07 decision and E08 risk/reservation/authorization | Contract conformance only |
| W14–W19 | OUT_OF_REPO | E09 command/order/fill/account/position/protection | Never runtime-imported |
| W20–W21 | OUT_OF_REPO | E10 outcomes/learning recommendation | Evidence reference only |
| W22 | CONSUME | Verify externally issued producer lease/fence | B01/B02/B08 |
| W23–W24 | OWN | E02 lifecycle/attestation and quarantine facts | B01/B02/B08 |
| W25 | OWN | Read-only E02 evidence projection | B08/B09 |

## Formula ownership

| F IDs | Class | Build |
|---|---|---|
| F00 | OWN boundary utility, subject to B00 representation decision | B01 |
| F01 | CONSUME/VERIFY_ONLY; E01 owns bar construction | B03/B09 |
| F02–F06 | OWN | B03 |
| F07 | CONSUME/VERIFY_ONLY unless B00 explicitly assigns derived final session facts | B03 |
| F08–F13 | OWN | B04 |
| F14–F17 | OWN | B05 |
| F18–F19 | OWN | B06 |
| F20 | REFERENCE_ONLY, E08 | Out of repo |
| F21–F22 | REFERENCE_ONLY, E09 | Out of repo |
| F23 | REFERENCE_ONLY, E10 | Out of repo |

## Contract families

Contracts owned by ORIGIN are limited to its envelope/identity/config verification, feature,
structure, reaction/hypothesis/candidate, transition/withdrawal, checkpoint/replay, quarantine,
heartbeat/attestation, and read-only evidence facts. Decision, risk, reservation, authorization,
command, order, fill, position, protection, outcome, and learning contracts may be vendored as
immutable conformance references; their producer implementations are out of repository.

The canonical version map is `BLOCKED_BY_B00` because the supplied RC2 wiring uses conflicting
v1/v2/v3 names. No published schema byte may be edited in place.

## Parameter and golden-vector mapping

Every in-scope F implementation must list exact `PAR-*` IDs and `GV-*` vectors in its module
metadata and tests. Parameters with `PROPOSED_RC2_MUST_RATIFY` may appear only in a clearly named
DARK proposal bundle. `NOT_RATIFIED`, missing units, ambiguous formulas, or unbound prose aliases
make the formula instance `NOT_READY`.

The supplied workbook's formula bindings and capsule ordinals are not accepted traceability until
B00 repairs the defects listed in the conflict register.

## OPS allocation

| OPS work | Class | Build/owner |
|---|---|---|
| Immutable build artifact and SBOM/provenance | OWN | B01/B09 |
| Dedicated `triad-origin-e02` service definition | OWN | B08 |
| Deployment remains DARK/no authority | OWN | B08 |
| Post-deploy replay smoke | OWN | B08/B09 |
| 26-hour ingress soak | CONSUME/OPERATOR | B09 external-evidence register |
| Secrets/ACL negative proof | OWN | R00/B08 |
| Rollback and DR rehearsal procedure | OWN docs; operator executes | B09 |
| Venue/account/environment certification | OUT_OF_REPO | G-1/G1 estate owner |
| Lease coordinator and durable fencing ledger | OUT_OF_REPO | Platform/Governance |

## Repository milestone truth

| Prior claim | Audited state | Remediation |
|---|---|---|
| RC1 M1 complete | MERGED_IMPLEMENTATION / FAILED_AUDIT | R00 then B01 |
| RC1 M2 complete | MERGED_IMPLEMENTATION / FAILED_AUDIT | R00 then B02 |
| M3 base/drafts laid | NON_AUDITABLE_OFF_TREE | Discard or re-review after B00–B03 |
| M4–M6 planned | SUPERSEDED | B06–B09 |

Every future trace row must carry requirement ID, ownership class, path/symbol, test ID, PR, head
SHA, merge SHA, CI run, receipt ID, status, and superseded-by linkage.

