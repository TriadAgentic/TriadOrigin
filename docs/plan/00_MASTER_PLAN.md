# 00 · Master Plan

## 1 · Objective

Build **TRIAD ORIGIN V7** — the *Deterministic Causal Edge Core* — as a clean-room replacement for
the deterministic **E02** feature/structure/candidate authority inside the existing TRIAD chassis,
faithfully to the 1.0.0-RC1 specification set (docs 00–10, vendored under `docs/spec/`).

The deliverable is a **governed, testable, DARK** codebase:
- deterministic causal state machines (structures → reactions → candidates),
- strict versioned contracts with byte-pinned identity,
- a durable hash-chained transport and replay/checkpoint determinism,
- signed configuration and activation/lease control-plane artifacts,
- read-only evidence/health faces,
- a falsification-first test suite and migration/rollback runbooks.

**Out of scope by construction (Doc 00):** any live activation, any venue credential/order verb, any
money authority, and any *numeric* detector threshold value (thresholds remain symbolic/TBD until a
registered trial + signed activation manifest supplies them). This is an engineering & research
baseline; **no profitability is claimed**.

## 2 · Constitution (the laws every milestone obeys)

Derived from Doc 00 ADRs and Doc 02/03/04. These are release-blocking.

1. **Deterministic control bypasses intelligence.** ORIGIN is pure causal state machines:
   `transition(prior_state, ordered_input, immutable_params, dependency_quality) → (new_state, events)`.
   No system clock, I/O, randomness or unordered output.
2. **Maker-first / post-only.** Normal entry & exit are post-only maker. Taker is an E09-owned,
   governed, position-reducing **emergency escape only** — never open/add/reverse (ADR-003/004).
3. **One live mode.** Replay/simulation are offline harnesses only. No dry-run/testnet/paper
   production mode (ADR-005). The three modes (shadow/paper/live) are a promotion ladder.
4. **Five isolated capsules.** No vote ensemble; each capsule has its own formula, parameter, trial
   and denominator (ADR-006).
5. **RR ≥ 2.0** geometric candidate floor before costs; stop placement is natural/learned, never a
   fixed legacy distance (ADR-008).
6. **No legacy-value inheritance.** A code default for a semantic threshold is a hidden experiment
   and is forbidden — ORIGIN **fails closed** when a required parameter is absent (Doc 02 §02.15).
7. **Deploy is not authority.** A healthy dark process is `READY_NO_AUTHORITY`. Money/candidate
   authority is a scoped producer lease with monotonic fencing, never inherited on restart (Doc 04).
8. **Immutable contract bytes.** Published schemas never change under the same version; the bundle
   manifest pins exact bytes; CI fails on drift (Doc 03).
9. **Evidence is append-only & honest-null.** Losing events and abstentions are never deleted or
   defaulted to zero.

## 3 · Build approach

- **Language:** Python 3.11, **stdlib-only runtime** (deterministic, self-contained CI). `PyYAML`
  reads signed config artifacts; `pytest`/`jsonschema` are test-only. Rationale: the estate's
  contract/conformance tooling is Python; a pure reference implementation with integer arithmetic and
  ordered processing meets the determinism obligations and is fast to verify. (A later Rust port of
  hot paths is a deferred option, not required by RC1.)
- **Layered like the spec, not a monolith.** `contracts/` (schemas + manifest + golden vectors),
  `src/triad_origin/` (kernel → structures → capsules → faces), `config/` (signed artifacts),
  `tools/` (deterministic generators/verifiers), `tests/` (falsification-first), `docs/`.
- **Ultracode where it pays.** Independent, well-specified modules (the 7 structure detectors; later
  the 5 capsules; the verification-matrix suites) are fanned out with a workflow of parallel agents,
  each self-testing. Tightly-coupled substrate (contracts, kernel, wiring) is authored directly for
  coherence. Every workflow output is re-verified by the full suite before it merges.

## 4 · Milestone map

| # | Milestone | Theme | Primary spec |
|---|-----------|-------|--------------|
| **M1** | Contract & Identity foundation | 30 contracts, canonical encoding, identity, manifest | Doc 03 |
| **M2** | Kernel primitives & transport | transition base, tick math, clocks, partitioning, ledger, journal/replay, lease, ingress, telemetry, health | Doc 02 §02.2, Doc 04, Doc 05 |
| **M3** | Structure semantics | feature primitives + typed levels + structure state (BOS/CHOCH) + FVG + order block + reclaim + flow atoms | Doc 02 §§02.3–02.11, Doc 04 §§04.4–04.7 |
| **M4** | Reaction, capsules & candidates | reaction engine, capsule host, 5 capsules, opportunity clusterer, candidate publisher | Doc 02 §§02.12–02.13, Doc 04 §04.8 |
| **M5** | Config artifacts, wiring & services | signed config, comparator, authority router, legacy bridge, replay-runner, service main | Doc 05, Doc 00 config inventory |
| **M6** | Verification matrix & runbooks | falsification-first test registry, migration/rollback runbooks, read-only evidence faces | Doc 08, Doc 09 |

Sequencing: M1 → M2 → M3 → M4 → M5 → M6. M3 depends on M2; M4 on M3; M5 on M1–M4; M6 spans all.
Detail is in [`01_MILESTONE_BREAKDOWN.md`](01_MILESTONE_BREAKDOWN.md).

## 5 · PR & merge cadence

- One PR per milestone into `main`, merged (squash) immediately once green, per the operator's
  directive to minimize local-only work.
- After each merge, the feature branch `claude/triad-origin-implementation-xz7uct` is re-based on the
  fresh `main` (`git checkout -B … origin/main`) and the next milestone begins.
- Every PR body carries the milestone scope, the verification evidence (test count + manifest check),
  and the coupled spec sections.

## 6 · Verification strategy

Falsification-first (Doc 08). Each milestone lands with tests that could *destroy* an apparent
property, not merely confirm it:
- **Contracts:** golden valid/invalid vectors under both validators; closed-enum, stale-epoch,
  forbidden-field, manifest byte-integrity.
- **Kernel:** hash-chain tamper/torn-frame detection, single-writer, fencing monotonicity,
  checkpoint/replay determinism (prefix/restart/duplicate invariance).
- **Structures/capsules (Doc 02 §02.16 proof obligations):** prefix invariance, restart invariance,
  duplicate invariance, LONG/SHORT mirror, scale metamorphism, lifecycle monotonicity, identity
  stability, risk independence, null honesty, and falsification (placebo timestamps/signs, future
  mutation, ablations).
- **Gate:** `python3 -m pytest` green **and** `python3 tools/verify_manifest.py` exit-0 on every PR.

## 7 · Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Threshold values are TBD | Kept symbolic; tests supply parameters; `require()` fails closed — no hidden defaults ship |
| Structure semantics ambiguity | Faithful to Doc 02/04 tables; every rule cites its section; golden vectors pin behavior |
| Workflow-authored drift | Shared base pre-authored; each agent self-tests; full-suite re-verify before merge |
| Live-venue coupling creep | ORIGIN has no venue/keys/order code paths; contract schema forbids money fields on candidates; ACL posture documented |
| Transport assumption (NATS) | File-ledger is the authoritative binding; JetStream is a deferred, separately certified option |

## 8 · Explicitly deferred (Doc 10 / inventory `DEFER`/`BLOCKED`)

Hyperliquid & non-Binance adapters (VEN-019/020), object-store archive (DAT-018), the optional
JetStream transport binding, live economic certification (M7–M9 of Doc 09, which require real market
data + governance ceremony and are **not** agent-executable here), and every numeric detector
threshold value. These are **named, not silently chosen**.
