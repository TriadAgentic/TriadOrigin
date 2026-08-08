# TRIAD ORIGIN V7 — Deterministic Causal Edge Core

**Engineering name:** TRIAD ORIGIN V7 · **Descriptive name:** Deterministic Causal Edge Core
**Repository:** `TriadAgentic/TriadOrigin` · **Service:** `triad-origin-e02` · **Topology node:** `E02-V7`
**Namespace:** `triad.origin.v7` · **Shorthand:** `ORIGIN`

> **No profitability claim.** ORIGIN is an engineering and research specification. Profitability
> remains an empirical hypothesis. **No live activation is authorized by this repository.** Every
> route ships **DARK** (no venue credentials, no order verbs, no money authority).

ORIGIN is a **clean-room replacement for the deterministic E02** feature/structure/candidate
authority inside the existing TRIAD chassis. It is not a new E00–E10 monolith and copies no legacy
detector wholesale. It reuses only independently verified contracts, venue mechanics, exact
arithmetic, safety rails and operational patterns.

This repository implements the governed baseline defined by the **TRIAD ORIGIN V7 1.0.0-RC1**
specification set (see [`docs/spec/`](docs/spec/) and [`docs/SPEC_INDEX.md`](docs/SPEC_INDEX.md)).

## Constitution (the load-bearing laws)

- **Deterministic control bypasses intelligence.** ORIGIN is pure, causal state machines over an
  explicitly ordered input stream. `transition(prior_state, ordered_input, immutable_params,
  dependency_quality) -> (new_state, events)` — **no system clock, no I/O, no randomness, no
  unordered output.**
- **Maker-first / post-only.** Normal entry and exit are post-only maker. Taker is an E09-owned,
  governed, position-reducing **emergency escape only** — never open, add or reverse exposure.
- **One live mode.** Replay/simulation exist only as offline harnesses. No dry-run/testnet/paper
  production mode.
- **Five isolated capsules.** No vote ensemble. Every capsule has its own formula, parameter, trial
  and denominator.
- **RR ≥ 2.0 candidate floor** before costs; stop placement is natural/learned, never a fixed
  legacy distance.
- **No legacy-value inheritance.** Numeric detector thresholds are **symbolic** until a registered
  trial and a signed activation manifest supply them. A code default is a hidden experiment and is
  forbidden — ORIGIN **fails closed** when a required parameter is absent.
- **Deploy is not authority.** A healthy dark process holds no money authority. Authority is a
  scoped producer lease with monotonic fencing, issued by governance — never inherited on restart.

## Layout

```
contracts/         Signed contract schemas, bundle manifest, registry, golden vectors
src/triad_origin/  The deterministic kernel, structures, capsules and read-only faces
config/            Signed canonical config artifacts (schemas + owner + change control)
docs/spec/         The vendored 1.0.0-RC1 specification set (00–10) — the normative source
docs/              SPEC_INDEX, ADRs, runbooks, verification matrix
tools/             Deterministic generators and manifest verifiers
tests/             Falsification-first invariant, golden, compatibility and property tests
```

## Build status

Implemented milestone-by-milestone; see [`docs/SPEC_INDEX.md`](docs/SPEC_INDEX.md) for the
inventory→module map and current coverage. Run the suite:

```bash
python3 -m pip install -e '.[test]'
python3 -m pytest
python3 tools/verify_manifest.py   # contract bundle byte-integrity
```
