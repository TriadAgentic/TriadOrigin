# 03 · Engineering Conventions

## Deterministic semantic path

Every semantic component exposes a pure transition:

`transition(prior_state, ordered_input_envelope, immutable_parameter_bundle,
dependency_quality_snapshot) -> (new_state, events)`.

Forbidden on that path:

- wall clock, process identity, environment reads, file/network I/O, randomness;
- float values or float-dependent comparison;
- iteration-order-dependent output;
- future or non-watermark-safe facts;
- mutable global configuration or silent fallback.

CI runs with fixed UTC/locale and varied `PYTHONHASHSEED` where order invariance matters.

## Representation and clocks

The current RC1 code uses base-10 strings for tick/step wire values, while RC2 declarations say
signed int64. RC2 also conflicts between `*_ns` field names and UTC Unix microseconds.
Until B00 resolves semantic type, JSON encoding, field names, and migration compatibility:

- existing published bytes remain immutable;
- no new contract version is inferred;
- internal semantic math remains checked signed integers;
- boundary conversion is exact and fail-closed;
- any ambiguous/new scope is `SAFE_HOLD`.

## Parameters

- No semantic numeric default in code.
- Every parameter has canonical ID, type, unit, inclusive/exclusive boundary, rounding, scope,
  formula version, failure behavior, immutable digest, status, and evidence receipt.
- Missing/null/`NOT_RATIFIED` is a named not-ready/abstention state.
- A proposed RC2 value is not ratified merely because a test fixture uses it.
- A semantic change creates a new parameter set and preregistered trial; old evidence becomes stale.

## Contracts and identities

- Validate before publication and again at consumption.
- Supported validators must agree; the stdlib path enforces every safety-material keyword used.
- Unknown contract major, stale/lower epoch, forbidden field, noncanonical number, or missing lineage
  rejects/quarantines.
- Current producer epoch equality is valid for subsequent events; lower epochs reject.
- Stable root identity and append-only revision identity are distinct.
- Published schemas are installed package resources and remain byte-pinned.
- The contract bundle artifact must validate against its own declared schema.

## Config and signatures

ORIGIN may verify signed public configuration. It may not contain a private signing key.
B00 must define signature algorithm, canonical signed bytes, trust-root distribution, signer roles,
revocation, expiry, and failure behavior before `signed config` is an acceptance claim.

## Ordering, checkpoint, and replay

- Cross-source events preserve recorded local receipt order; source sequences are compared only
  within the same source/connection epoch.
- The R00 checkpoint authenticates canonical state, partition, input segment/offset and consumed
  prefix digest, last domain event ID, highest producer epoch, projection checksum, output
  segment/offset, the closed build/config/contract/parameter/instrument digest set, state sequence,
  last transition identity, and identity version. It binds the supplied input prefix and build
  context before skipping. B02 must additionally bind an independently durable output-ledger head
  and complete per-scope consumer-fence state before restart/exactly-once acceptance.
- Replay, production consumption, checkpoint resume, and cold rebuild invoke the exact same
  transition functions.
- Duplicate identity is idempotent. Corrections append and never move knowledge time backward.

## Capability boundaries

Runtime source and built artifacts must fail a negative scan for:

- venue credential/token loading or secret persistence;
- network clients or direct venue/MCP control connections;
- order place/cancel/replace/flatten/close verbs;
- E07/E08/E09 producer bindings;
- lease issuance/coordinator capability;
- risk, quantity authorization, or money-publish effects.

Declarative conformance schemas are allowed only when clearly separated from executable capability.

## Testing and CI

Each module ships:

- equality and one-unit-neighbor boundaries;
- invalid/null/stale/gap/overflow cases;
- duplicate, correction, future-mutation, prefix, cold/warm/restart/checkpoint tests;
- LONG/SHORT mirror and scale tests where meaningful;
- contract-valid output and forbidden-field tests;
- property/falsification tests tied to stable requirement IDs.

Every PR runs at minimum:

```bash
PYTHONHASHSEED=0 python -m pytest
PYTHONHASHSEED=1 python -m pytest
python tools/collect_test_ids.py
python tools/verify_manifest.py
python tools/validate_contract_manifest.py
python tools/verify_reproducible_build.py
python tools/test_wheel_install.py
python tools/verify_no_forbidden_capabilities.py
```

No skip/xfail is accepted silently; each has an owner and receipt disposition.

## PR and merge

- One fresh branch and one PR per milestone.
- Spec/scope change precedes implementation in a separate PR.
- R00 alone is the recorded bootstrap exception because it introduces this corrected law while
  repairing the audit defects that made the prior law unsafe; after PR #4's receipt failed closed,
  the exception expires only when the corrective R00 receipt is sealed.
- No normal force-push or reused long-lived milestone branch.
- Merge only after exact-head CI, zero unresolved actionable threads, and an authenticated clean
  acceptance for that same immutable head.
- A clean acceptance is head-scoped. Any later commit invalidates it and requires new exact-head CI,
  a fresh full-head trigger, and a fresh clean artifact.
- In the clean-comment arm, the response must have the exact fixed clean declaration, a bounded
  one-line ASCII display reason with no renderer/control syntax, the exact reviewed-head marker, and
  the exact common tail. The full body is still persisted, compared, and hashed byte-for-byte; the
  reason is an opaque non-authoritative field whose lexical meaning is never a verdict input. A
  unique connector PR-root `+1` must occur strictly after the exact-head trigger and no later than
  the clean response.
- Complete review, top-level issue-comment, PR-root-reaction, and issue-timeline inventories are
  fetched twice, persisted exactly, and fail closed on pagination gaps, races, or disagreement.
- The reviewed source pins PR #7's exact pre-final review/comment baseline, including immutable
  numeric actors and complete bodies. Every top-level comment must remain unedited; a changed
  historical review or any post-trigger `review_dismissed` event fails closed.
- No commit, force-push, head-ref deletion/restoration, base-ref deletion, or head/base ref mutation may occur between
  the accepted trigger and guarded merge. `automatic_base_change_succeeded` is a base mutation, and
  head-ref deletion before receipt sealing is forbidden even after merge.
- In either clean-acceptance arm, every thread root and ordinary reply must predate the selected
  review object or, for the clean-comment arm, the final review trigger.
  Exactly one selected canonical closure reply may follow, strictly after merge and without edits;
  tied, intermediate, later, missing, edited, or duplicate thread activity fails closed.
- Post-merge verification uses a fresh reconstruction of `main`.
- Old review threads are resolved only after their corrective commit exists and is referenced.

## Milestone receipt

A milestone is `VERIFIED` only when its receipt validates against
`milestone_receipt.schema.json` plus `tools/validate_milestone_receipt.py` and includes exact
authority-basis/scope, toolchain/dependency,
artifact, test-ID/result, CI, review, merge, post-merge, supersession, rollback, and
negative-capability evidence. Every receipt digest except the directly recomputed scope digest binds
to a persisted repository-relative preimage in `evidence_files`; the semantic validator rehashes
those files and rejects missing, tampered, duplicate, escaping, unbound, or opaque evidence.
Inapplicable formula/parameter/corpus/replay evidence is an explicit owned deferral, never omission.
A workbook/manual status cannot substitute for a receipt.

For corrective R00, the typed review evidence is versioned as `origin.review-evidence.v3` with a
matching `origin.github-review-export.v3` and uses a discriminated final-acceptance record. The
review-object arm requires an exact-head clean review object with no findings and the same complete
historical comment/review, reaction, pull-boundary, and timeline checks. The clean-comment arm
requires an unchanged maintainer trigger containing the full final head and successful CI run/job,
then an unchanged connector clean-response comment with the fixed declaration, structurally
isolated reason phrase, exact reviewed prefix, and exact common tail. The raw
connector login and immutable numeric actor ID must agree across the clean comment and the persisted
PR-root `+1`. That reaction must be created after this trigger and at or before the clean response;
an older persistent reaction cannot excuse a missing, stale, or wrong-head clean comment.
