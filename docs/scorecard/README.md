# TRIAD full-pipeline scorecard

## Status and safety boundary

This package is a deterministic, read-only diagnostic projection over the target E00--E10
pipeline. Its fixed claim is `DIAGNOSTIC_READ_ONLY_NO_AUTHORITY` and its authority effect is
`NONE`. It does not discover services, query live systems, mutate state, issue leases, select a
money path, activate a plane, admit a candidate, size risk, send an order, merge code, or deploy
anything.

The complete acquisition, schema, topology, conservation, GUI, validation, deployment, rollback,
and merge procedure is in [`INTEGRATION_GUIDE.md`](INTEGRATION_GUIDE.md). The intentionally
incomplete [`status_only_input.v1.json`](examples/status_only_input.v1.json) fixture is the safe
first integration test; it demonstrates honest missing evidence and must not be used as runtime
proof.

The repository's current safe baseline is:

| Dimension | Baseline |
|---|---|
| `venue_environment` | `OFF` |
| `venue_activation` | `OFF` |
| `paper_activation` | `OFF` |
| `shadow_activation` | `LIVE` |

This is written compactly as `OFF/OFF/OFF/LIVE`. A report may describe that baseline only from
caller-supplied evidence. Silence or lack of activity never proves `OFF`, and the scorecard cannot
change the baseline it observes. At E09, the new-exposure path is expected `OFF`; the
cancel/protection/reconciliation/reduction safety path remains expected active.

## Diagnostic architecture

The canonical scorecard topology uses semantic channel names rather than product names:

| From | To | Channel | Meaning |
|---|---|---|---|
| E00 | E01 | `RAW_FACTS` | Raw market facts enter canonical state. |
| E01 | E02 | `CANONICAL_STATE` | Canonical state is supplied to ORIGIN. |
| E02 | E05 | `IMMUTABLE_CANDIDATE_INPUT` | ORIGIN evidence and candidates enter the coordinator unchanged. |
| E05 | E03 | `ADVISORY_REQUEST` | The coordinator requests forecast advice. |
| E03 | E05 | `FORECAST_ADVISORY` | Forecast advice returns to the coordinator. |
| E04 | E05 | `SPECIALIST_ADVISORY` | Specialist evidence joins at the coordinator. |
| E05 | E06 | `ADVISORY_REQUEST` | The coordinator requests language/knowledge advice. |
| E06 | E05 | `LANGUAGE_KNOWLEDGE_ADVISORY` | Language/knowledge advice returns to the coordinator. |
| E05 | E07 | `FUSED_CALIBRATED_EVIDENCE` | One joined evidence product proceeds to policy. |
| E07 | E08 | `DECISION` | Policy emits an admitted or refused decision. |
| E08 | E09 | `RISK_AUTHORIZATION` | Risk alone supplies execution authorization. |
| E09 | E10 | `EXECUTION_FACTS` | Venue facts proceed to outcomes and learning. |

E05 is the only modeled fan-out/join point. It receives immutable E02 input, fans advisory work
out to E03 and E06, joins those results with E04 specialist evidence, calibrates the joined
evidence, and sends that evidence to E07. It does not give Kairos, Logos, E04, or itself E07 policy,
E08 risk, or E09 execution authority. A missing, refused, timed-out, stale, or unreconciled
advisory remains an explicit evidence state; it is never coerced to a negative result or a numeric
zero.

## Component-role registry

[`component_role_registry.v1.json`](component_role_registry.v1.json) records the diagnostic mapping
confidence separately from topology and runtime proof:

| Component | Stage | Mapping | Interpretation |
|---|---|---|---|
| `triad-origin-e02` | E02 | `RATIFIED` | The local repository declares its E02-only identity and boundary. |
| Kairos | E03 | `OPERATOR_ASSERTED_UNATTESTED` | Forecast-provider mapping is an operator assertion, not a ratified estate fact. |
| Logos | E06 | `OPERATOR_ASSERTED_UNATTESTED` | Language/knowledge-provider mapping is an operator assertion, not a ratified estate fact. |
| Unnamed sibling services | E00, E01, E04, E05, E07--E10 | `UNBOUND` | No component identity is assigned by this repository. |

The E02 mapping evidence is [`README.md`](../../README.md#e02-boundary) and
[`docs/SPEC_INDEX.md`](../SPEC_INDEX.md#e02-ownership-map). It ratifies only the mapping of the
local `triad-origin-e02` component to the E02 diagnostic role. It does not ratify formulas,
activation, deployment, current health, cross-repository ownership, or any downstream authority.

`OPERATOR_ASSERTED_UNATTESTED` prevents a `FULL` report and must not be promoted to `RATIFIED`
without a separately governed cross-repository artifact. `UNBOUND` is a publication blocker. The
registry is descriptive evidence metadata, not a service-discovery file, deployment manifest,
ownership registry, or wiring instruction. Its empty `authority_claims` arrays are intentional.

## Closed input

The CLI accepts exactly one JSON object with schema
`triad.origin.full_pipeline_scorecard.input.v1` and these top-level members:

| Member | Required evidence |
|---|---|
| `schema`, `report_id`, `as_of_us` | Input identity and caller-supplied observation time. |
| `components` | Component/stage role, mapping status, mapping evidence, and claimed authority. |
| `posture` | Desired and observed four-plane posture plus freshness, reconciliation, attestation, side-effect census, and references. |
| `stages` | One proof object for every required stage/path cell. |
| `edges` | One proof object for every canonical semantic edge. |
| `cohort` | Closed E02 candidate cut, source watermark/digest, completeness, IDs, and evidence references. |
| `evaluations` | Candidate decision, route revision, observation time, maturity deadline, and event-time posture. |
| `terminals` | Typed terminal dispositions keyed to derived population instances. |
| `metrics` | Facts from the closed diagnostic metric profile. |

Objects use closed field sets. The loader rejects duplicate JSON keys, non-finite numbers,
non-object roots, unknown fields, missing fields, invalid enum values, and ambiguous numeric
representations. All clocks, watermarks, freshness ages and bounds, build/config/contract/binding
digests, population facts, and dispositions are supplied by the caller; the scorecard performs no
environment or wall-clock discovery.

An empty cohort is valid only with a complete zero proof containing a nonzero query digest,
nonzero source-cut digest, `source_completeness=COMPLETE`, and a watermark. An observed numeric zero
metric likewise requires its own zero proof. Missing measurement is represented by `null` with a
typed reason and a non-observed availability; it is never silently converted to zero.

## Output and integrity

The builder emits schema `triad.origin.full_pipeline_scorecard.diagnostic.v1`. The report contains
the desired and observed posture, posture proof, component mappings, stage cells, edge cells,
candidate cohort, derived population routes, reconciled terminals, mandatory metrics, candidate
traces, publication findings, and a `content_digest` over the canonical unsigned report.

JSON is canonical and deterministic. HTML is a self-contained escaped rendering of the same report.
The HTML renderer verifies `content_digest` before rendering and rejects a report modified after
digest creation. The HTML view is a convenience; candidate traces, route identities, terminal
evidence references, and zero proofs remain in the JSON companion artifact.

The adjusted HTML uses the useful visual grammar of the legacy dense matrix and target-topology
poster while correcting their semantics. It renders one canonical E00--E10 stage card, groups the
two E09 paths, shows asserted Kairos/E03 and Logos/E06 mappings separately from E05, keeps all four
populations separate, and derives every headline count from report rows. It has no JavaScript,
external font/CDN, endpoint, browser storage, form, or network connection. It never reproduces the
legacy board's generic `LIVE` or premature `PROMOTE` claims.

## CLI

From the repository root:

```bash
PYTHONPATH=src python tools/generate_full_pipeline_scorecard.py evidence.json
PYTHONPATH=src python tools/generate_full_pipeline_scorecard.py evidence.json \
  --json-output scorecard.json --html-output scorecard.html

# Safe first render: intentionally WITHHELD/STATUS_ONLY evidence
PYTHONPATH=src python tools/generate_full_pipeline_scorecard.py \
  docs/scorecard/examples/status_only_input.v1.json --diagnostic-only \
  --json-output /tmp/triad-scorecard.json \
  --html-output /tmp/triad-scorecard.html
```

Without `--json-output`, canonical JSON is written to standard output. A successfully built
non-`FULL` report is still emitted for diagnosis before the process fails closed.

| Exit | Meaning |
|---:|---|
| `0` | A `FULL` report was emitted, or `--diagnostic-only` explicitly allowed a successfully emitted non-`FULL` diagnostic. |
| `1` | Input, model, digest, or rendering validation failed. |
| `2` | A `WITHHELD` or `STATUS_ONLY` report was emitted and default fail-closed publication behavior refused success. |

`--diagnostic-only` changes only the process exit code after successful emission. It does not
change the report's publication outcome, remove findings, grant authority, or make evidence
publishable.

## Proof-state semantics

Resolution is fail-closed and precedence-sensitive:

| State | Meaning |
|---|---|
| `NOT_IMPLEMENTED` | Absence is explicitly proven with evidence and a complete side-effect census. Missing evidence alone is not absence. |
| `DARK` | Fresh authoritative evidence proves a deployed dark or retired role. No activity alone is not `DARK`. |
| `OFF` | Fresh authoritative, reconciled, digest-bound evidence and a complete side-effect census prove activation off. |
| `STALE` | The supplied evidence age exceeds its bound. Staleness takes precedence over a claimed dark/off condition. |
| `UNRECONCILED` | Authority, mapping, freshness, watermark, digest, attestation, reconciliation, or another proof dimension is incomplete. |
| `PROVEN` | Every required proof dimension is complete and consistent for the reported state. |

Mirrors and exports may support diagnosis but cannot prove current writer or control state. A
component may claim only the authority class allowed for its stage, and the scorecard never
transfers that claim into an operational capability.

## Publication semantics

| Outcome | Condition | Default CLI result |
|---|---|---:|
| `WITHHELD` | At least one blocker exists, such as an unbound/conflicting mapping, missing edge/stage evidence, posture mismatch, incomplete cohort, unexplained terminal, input-cut mismatch, or authority leak. | `2` |
| `STATUS_ONLY` | No blocker exists, but one or more limitations remain, such as an unattested mapping, missing metric, empty cohort, or no matured population. | `2` |
| `FULL` | There are no blockers and no status flags and an authenticated evidence-envelope verifier has established source role, scope, digest, epoch, and signature. Reserved in diagnostic v1. | `0` |

`FULL` means evidence completeness for this diagnostic profile. It does not mean profitable,
healthy, activated, deployed, approved, mergeable, or authorized to trade. Diagnostic v1 accepts
caller-supplied assertions but does not yet authenticate cross-repository evidence envelopes, so
it always emits `SCORECARD_ASSERTION_ONLY_INPUT` and cannot produce `FULL`. This is an intentional
honesty cap, not a missing status label.

For terminal conservation, every matured population route must resolve to one compatible terminal
disposition. Exact replay duplicates are idempotent; conflicting duplicates, orphan terminals,
unexplained matured routes, cross-population contamination, and unresolved unknown-submit states
fail closed.

Every accepted evaluation derives an independent mandatory `SHADOW` route. `PAPER` is additive,
and one event-time `TESTNET` or `LIVE` route is additive when its event-time posture authorizes it;
none replaces SHADOW. `UNKNOWN_SUBMIT_UNRECONCILED` and `PROVEN_NO_VENUE_EFFECT` are E09 lifecycle
terminals on the venue route, never E07 decision states. Even a venue-side `RISK_DENIED` terminal
therefore cannot erase the separate SHADOW population record.

## Mandatory diagnostic metrics

Every count metric below has the exact shape `metric_class=COUNT`, `value_type=INTEGER`, and
`unit=COUNT`. E00--E07 counts use `population=null`; E08--E10 counts require one row for each of
`SHADOW`, `PAPER`, `TESTNET`, and `LIVE` so no money-plane population can be silently aggregated.
Omission of any required identity produces `SCORECARD_MANDATORY_METRIC_MISSING`.

| Stage | Metric IDs |
|---|---|
| E00 | `e00.raw_events.count` |
| E01 | `e01.canonical_updates.count` |
| E02 | `e02.candidates.count` |
| E03 | `e03.forecast.requests.count`, `e03.forecast.outputs.count`, `e03.forecast.refusals.count` |
| E04 | `e04.specialist.outputs.count` |
| E05 | `e05.coordinator.inputs.count`, `e05.coordinator.fused.count` |
| E06 | `e06.language_knowledge.requests.count`, `e06.language_knowledge.outputs.count`, `e06.language_knowledge.refusals.count` |
| E07 | `e07.decisions.accepted.count`, `e07.decisions.rejected.count` |
| E08 | `e08.risk.allowed.count`, `e08.risk.denied.count` |
| E09 | `e09.execution.commands.count`, `e09.execution.fills.count`, `e09.execution.unknown_submit.count` |
| E10 | `e10.outcomes.complete.count`, `e10.outcomes.unresolved.count` |

The profile also requires stage latency/freshness metrics in canonical decimal milliseconds:
`e00.data_freshness.p95_ms`, `e03.forecast.latency.p95_ms`,
`e05.coordinator.latency.p95_ms`, `e06.language_knowledge.latency.p95_ms`,
`e07.decision.latency.p95_ms`, `e08.risk.latency.p95_ms`, and
`e09.execution.ack_latency.p95_ms`. E08/E09 latency rows are population-separated.

Optional economic metrics remain population-separated and include E09 fill rate/slippage plus E10
net P&L, net R multiple, win rate, profit factor, and maximum drawdown. A missing value stays
`null` with a typed reason; an exact observed zero requires completeness proof.

## Governance blocker: do not open a PR

This scorecard work is stacked on the blocked B00R generation-2 forward-repair head. The frozen
B00R source classifier in [`tools/classify_milestone_pr.py`](../../tools/classify_milestone_pr.py)
does not grant `src/triad_origin/scorecard/**`, `tests/scorecard/**`, `docs/scorecard/**`, or
`tools/generate_full_pipeline_scorecard.py`. A PR containing these paths would therefore fail with
`SOURCE_PATH_OUT_OF_SCOPE`. Adding source hashes alone does not expand that grant.

Do not open a scorecard PR under B00R G2. B00R G2 must first merge, receive its governed receipt,
and be anchored as described in [`docs/governance/README.md`](../governance/README.md). A later
authorized milestone must explicitly grant every scorecard source, test, documentation, and tool
path and pin every required regular file in `docs/control/SOURCE_HASHES.sha256` in the same governed
change.

Until that happens, this branch is diagnostic preparation only. It creates no component ownership,
cross-repository ratification, runtime activation, deployment authority, merge authority, or
exception to the safe-hold posture.
