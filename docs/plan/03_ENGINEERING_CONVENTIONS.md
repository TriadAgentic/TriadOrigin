# 03 · Engineering Conventions

Binding conventions for every milestone. These make the constitution (00 §2) mechanical.

## Determinism (Doc 02 §02.2, §02.16)

- Every structure/capsule is a pure state machine with the signature
  `transition(prior_state, ordered_input_envelope, immutable_params, dependency_quality) →
  (new_state, events)` via `triad_origin.transition.TransitionResult`.
- **Forbidden on the semantic path:** `time`/`datetime.now`, `random`, environment reads, file/network
  I/O, iteration-order-dependent output, floats in semantic comparisons.
- Prices/quantities are signed **integer ticks/steps** (`int`). The only decimal boundary is
  `instrument_math` conversion, which is fail-closed on overflow/non-multiple.
- Proof obligations are tested per module: prefix invariance, restart invariance, duplicate
  invariance, LONG/SHORT mirror, scale metamorphism, lifecycle monotonicity, identity stability, risk
  independence, null honesty, falsification.

## Parameters (Doc 02 §02.15) — no hidden experiments

- Numeric thresholds are **symbolic**. Read every one via `transition.require(params, "name")`, which
  raises `MissingParameterError` when absent or null. **Never** write a numeric default for a semantic
  threshold.
- Tests supply an explicit parameter bundle. A missing-parameter test proves fail-closed behavior.
- Every emitted semantic fact carries `formula_version`, `parameter_set_id`, `parameter_digest`.

## Contracts & identity (Doc 03)

- Canonical wire = sorted-key UTF-8 JSON, NFC strings, no NaN/Infinity, integer tick/step as base-10
  strings (`canonical.py`).
- IDs are **length-prefixed** field hashes (`canonical.digest_fields`); never raw concatenation. Use
  the `ids.py` hierarchy; mutable geometry retains `structure_id` and increments `state_seq`.
- Validate at production **and** at the consuming boundary; unknown enum/major/stale epoch **rejects**
  (fail closed) or **quarantines** with raw evidence — never defaults.
- New/changed schema bytes update `contracts/MANIFEST.sha256` via `tools/gen_manifest.py`;
  `tools/verify_manifest.py` gates CI. Same version ⟹ byte-identical.

## Transport & journals (Doc 04, Doc 05)

- Durable path is the hash-chained append-only `ledger.py` (one writer lock/partition; torn/tampered
  frames stop the partition and preserve bytes). Consumers checkpoint input offset + projection
  checksum.
- State machines are append-only with compare-and-append; projections rebuild from the journal and
  match the authoritative checksum.
- Authority is a scoped `producer_lease` with a monotonic fencing token; consumers keep the highest
  token per scope. A restart never inherits a lease.

## Modules & layout

```
src/triad_origin/
  canonical.py ids.py contracts.py transition.py            # foundation
  instrument_math.py clock_watermark.py partition.py         # kernel
  ledger.py checkpoint.py journal.py lease.py ingress.py     # transport/control
  telemetry.py health.py                                     # faces
  feature_primitives.py                                      # M3
  structures/                                                # M3 detectors
  capsules/                                                  # M4 capsules
  reaction_engine.py capsule_host.py opportunity_clusterer.py candidate_publisher.py  # M4
  comparator.py authority_router.py legacy_bridge.py replay_runner.py service/        # M5
```

## Testing

- `pytest`; tests mirror the source tree under `tests/`. Each new module ships focused tests in the
  same PR. Falsification-first: prefer a test that could disprove the property.
- A milestone is **not done** until `python3 -m pytest` is green **and** `python3
  tools/verify_manifest.py` is exit-0.

## PR & merge

- One PR per milestone into `main`; squash-merge when green; re-base the feature branch on fresh
  `main` before the next milestone.
- PR body: milestone scope, deliverables, verification evidence (test count + manifest), coupled spec
  sections. Force-with-lease is used only to advance the branch past already-merged history.

## Naming & posture

- Service `triad-origin-e02`, node `E02-V7`, namespace `triad.origin.v7`, shorthand `ORIGIN`.
- `POSTURE = "DARK"`, `ALLOW_MONEY_PUBLISH = False`. No module imports anything that signs, holds a
  venue key, or writes an order. Candidates carry no money field.
