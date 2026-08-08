# CLAUDE.md — TriadOrigin (node E02-V7, service `triad-origin-e02`)

TriadOrigin is the **clean-room deterministic E02 replacement** for the TRIAD estate. It is governed
by the **TRIAD ORIGIN V7 1.0.0-RC1** specification set vendored under `docs/spec/`. That set is the
normative source; this file is the day-to-day map.

## Normative precedence (Doc 00 §00.4)

1. Owner decision record → 2. Master Specification (`docs/spec/01…`) → 3. Contract schemas
(`contracts/schemas/*` + bundle manifest) → 4. State-machine catalog (`docs/spec/04…`) →
5. Wiring (`docs/spec/05…`) → 6. Runbooks (`docs/spec/09…`). Examples, diagrams, generated clients
and comments are **non-authoritative** and may never override a schema or normative requirement.

`MUST/MUST NOT/SHALL` are release-blocking. `SHOULD` needs a recorded exception. `TBD` is **not**
permission to choose locally — the dependent path stays blocked (fail closed).

## The never-list (where every agent looks first)

ORIGIN has **no** network or filesystem path to: the venue gateway command surface, venue keys, arm
tokens, account ledgers, the live writer DSN, or risk-state writes. ORIGIN emits **no** account,
leverage, quantity, risk approval, venue command or invented expected return. It publishes only
structures, candidates, checkpoints, quarantine records, evidence and metrics. A candidate carrying
any forbidden field (final approval, account, notional, leverage, executable quantity, venue order
IDs, raw credentials, invented expected return, direct E09 destination) is a constitutional breach
(Doc 03 §03.6).

## Determinism law (Doc 02)

Every ORIGIN structure is a pure causal state machine:
`transition(prior_state_bytes, ordered_input_envelope, immutable_parameter_bundle,
dependency_quality_snapshot) -> (new_state_bytes, zero_or_more_events)`. **No system clock, no I/O,
no randomness, no unordered output.** All prices enter semantic code as signed integer ticks under a
pinned instrument metadata revision; overflow/conversion error is fail-closed.

Proof obligations that gate every structure module (Doc 02 §02.16): prefix invariance, restart
invariance, duplicate invariance, mirror property, scale metamorphism, lifecycle monotonicity,
identity stability, risk independence, null honesty, falsification.

## Parameter discipline (Doc 02 §02.15) — no hidden experiments

Numeric detector thresholds (δ, b, g_min, D, H, W, e, τ, n, TTL, departure, …) are **symbolic** in
RC1. They enter code **only** through a signed, hashed parameter bundle. A code default for a
semantic threshold is forbidden; a required-but-absent parameter makes the detector **fail closed**.
Every emitted fact carries `formula_version`, `parameter_set_id` and `parameter_digest`.

## Contract discipline (Doc 03)

Published contract bytes are immutable; a breaking change is a new major. Every authoritative event
validates before publication **and again** at the consuming boundary. Unknown safety/economic data
never defaults — it rejects or quarantines with raw evidence. `contracts/MANIFEST.sha256` pins the
exact bytes of every schema; CI (`tools/verify_manifest.py`) fails on unmanifested or same-version
byte changes. Canonical wire is sorted-key UTF-8 JSON, integer tick/step as base-10 strings, no
NaN/Infinity; IDs are length-prefixed hashes per the Doc 03 §03.4 identity hierarchy — raw
concatenation is forbidden.

## Authority discipline (Doc 04)

Deploy is not authority. A dark process is `READY_NO_AUTHORITY`. Money/candidate authority is a
scoped `producer_lease.v1` with a monotonic fencing token; consumers keep the highest token per
scope and reject lower/expired/revoked tokens even when a later-timestamped payload arrives. A
restart never inherits a lease.

## Milestone / PR discipline

Work ships milestone-by-milestone; each milestone is a PR merged to `main`. Every PR keeps
`python3 -m pytest` green and `python3 tools/verify_manifest.py` exit-0. See `docs/SPEC_INDEX.md`
for the inventory→module coverage map.
