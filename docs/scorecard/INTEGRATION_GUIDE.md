# TRIAD Origin full-pipeline scorecard — integration guide

**Document status:** source-only integration guide

**Profile:** `triad.origin.full_pipeline_scorecard.diagnostic.v1`

**Input:** `triad.origin.full_pipeline_scorecard.input.v1`

**Safety claim:** `DIAGNOSTIC_READ_ONLY_NO_AUTHORITY`
**Current baseline:** `venue_environment=OFF`, `venue_activation=OFF`,
`paper_activation=OFF`, `shadow_activation=LIVE`

## 1. Outcome and non-negotiable boundary

The scorecard is an offline, deterministic evidence projection across E00–E10. It observes the
full pipeline without transferring ownership or authority into TriadOrigin. It cannot discover a
service, connect to MCP, read an environment variable, issue or renew a lease, activate a plane,
admit a candidate, size risk, submit or cancel an order, deploy code, restart a process, merge a
branch, or authorize promotion.

The browser artifact is inert:

- canonical JSON is its only data source;
- HTML is generated only after the report digest verifies;
- no JavaScript, external font, CDN, image, form, browser storage, endpoint, or network call exists;
- no credential, token, private key, host address, or session identifier belongs in the input,
  report, HTML, URL, log, repository, or screenshot;
- every displayed count is derived from report rows, never copied into a second UI ledger.

`FULL` is reserved for evidence completeness. It never means profitable, healthy, deployed,
activated, approved, mergeable, or authorized to trade. Diagnostic v1 accepts assertion objects
but does not authenticate cross-repository evidence envelopes, so it always emits
`SCORECARD_ASSERTION_ONLY_INPUT` and cannot currently produce `FULL`.

## 2. Canonical topology and authority

### 2.1 Stage authority

| Stage | Role | Exclusive authority | Scorecard treatment |
|---|---|---|---|
| E00 | Market and raw facts | Raw event ingress | Observed only |
| E01 | Canonical market state | Finalized canonical state | Observed only; Origin consumes |
| E02 | TriadOrigin | Deterministic features, structures, geometry, immutable candidates | Local repository identity is ratified; runtime still needs proof |
| E03 | Forecast provider | Forecast and uncertainty advisory only | Kairos mapping is asserted, not estate-attested |
| E04 | Typed specialists | Specialist advisory evidence only | Component identity remains unbound until attested |
| E05 | Intelligence coordinator | Fan-out, join, fusion, calibration only | Independent component; no admission, risk, or execution authority |
| E06 | Language and knowledge | Governed language/knowledge advisory only | Logos mapping is asserted, not estate-attested |
| E07 | Decision and policy | Sole admission and policy authority | Only E07 may create a trade-intent decision |
| E08 | Risk and governance | Sole sizing, limits, reservation, allow/deny authority | Only E08 may authorize risk |
| E09 | Execution | Sole venue actor and reconciliation owner | New exposure and safety/reconciliation paths are reported separately |
| E10 | Outcomes and learning | Outcome, attribution, calibration feedback, learning lineage | Fills remain E09 facts; E10 consumes them |

TriadOrigin is the system orchestrator but remains E02 in the authority model. Orchestration does
not grant another stage's authority. The scorecard may report sibling evidence without importing
sibling code or ownership.

### 2.2 Canonical semantic edges

The closed diagnostic topology is:

| From | To | Channel | Meaning |
|---|---|---|---|
| E00 | E01 | `RAW_FACTS` | Raw facts enter canonical state |
| E01 | E02 | `CANONICAL_STATE` | Origin receives canonical finalized state |
| E02 | E05 | `IMMUTABLE_CANDIDATE_INPUT` | Origin evidence/candidates enter the coordinator unchanged |
| E05 | E03 | `ADVISORY_REQUEST` | Coordinator requests forecast advice |
| E03 | E05 | `FORECAST_ADVISORY` | Forecast advice returns to the coordinator |
| E04 | E05 | `SPECIALIST_ADVISORY` | Specialist evidence joins at E05 |
| E05 | E06 | `ADVISORY_REQUEST` | Coordinator requests language/knowledge advice |
| E06 | E05 | `LANGUAGE_KNOWLEDGE_ADVISORY` | Language/knowledge advice returns to E05 |
| E05 | E07 | `FUSED_CALIBRATED_EVIDENCE` | One evidence bundle reaches policy |
| E07 | E08 | `DECISION` | Admission/policy decision reaches risk |
| E08 | E09 | `RISK_AUTHORIZATION` | Risk authorization reaches execution |
| E09 | E10 | `EXECUTION_FACTS` | Execution facts reach outcome/learning |

Forbidden implications:

- no direct Kairos/E03 ↔ Logos/E06 dependency;
- no E02 → E03 or E02 → E06 bypass around E05;
- no E03, E05, or E06 → E08/E09/E10 authority path;
- no advisory output may carry admission, risk, quantity, or execution authority;
- no missing advisory may silently become zero, a negative forecast, or a fallback decision.

### 2.3 Product mappings are separate evidence

The normative RC2/RC4 corpus defines E-stages but does not ratify the product names Kairos and
Logos. Diagnostic v1 therefore starts with:

| Product/component | Diagnostic stage | Mapping state |
|---|---|---|
| `triad-origin-e02` | E02 | `RATIFIED` for repository role only |
| Kairos | E03 | `OPERATOR_ASSERTED_UNATTESTED` |
| Logos | E06 | `OPERATOR_ASSERTED_UNATTESTED` |
| E00, E01, E04, E05, E07–E10 components | Corresponding stages | `UNBOUND` until evidence binds them |

An E03/E06 mapping can become `RATIFIED` only through a governed cross-repository artifact that
binds component identity, repository subject, contract, build, deployment, producer scope, lease,
and attestation. A hostname, repository name, diagram label, process name, mirror row, or caller
assertion is insufficient.

## 3. Integration architecture

Use a three-boundary design:

1. **Evidence acquisition outside TriadOrigin runtime.** A separately governed read-only runner
   queries approved sources and writes a closed input file. It owns transport/session handling but
   no trading authority.
2. **Pure projection inside this package.** The CLI loads one closed JSON object, validates it,
   derives routes and conservation, emits canonical JSON, and renders deterministic HTML.
3. **Static distribution.** Serve or archive the JSON/HTML pair as immutable evidence. The browser
   performs zero data acquisition.

This division is mandatory because the TriadOrigin runtime capability gate forbids network,
credential, venue-order, and dynamic execution seams under `src/triad_origin`.

### 3.1 Files

| Path | Purpose |
|---|---|
| `src/triad_origin/scorecard/model.py` | Closed enums and immutable evidence objects |
| `src/triad_origin/scorecard/law.py` | Topology, proof precedence, reason registry, metric profile |
| `src/triad_origin/scorecard/codec.py` | Strict JSON-object decoder |
| `src/triad_origin/scorecard/conservation.py` | Event-time route derivation and terminal reconciliation |
| `src/triad_origin/scorecard/builder.py` | Deterministic report projection and publication gate |
| `src/triad_origin/scorecard/render.py` | Offline evidence-console HTML renderer |
| `tools/generate_full_pipeline_scorecard.py` | File-to-JSON/HTML CLI |
| `docs/scorecard/component_role_registry.v1.json` | Descriptive starting mappings; not service discovery |
| `docs/scorecard/examples/status_only_input.v1.json` | Intentionally incomplete, fail-closed integration fixture |

## 4. Closed input contract

The input root must contain exactly these fields:

```text
schema
report_id
as_of_us
components
posture
stages
edges
cohort
evaluations
terminals
metrics
```

Unknown fields, duplicate JSON keys, missing fields, non-object roots, floats, `NaN`, infinity,
invalid enums, noncanonical decimals, and ambiguous null/zero representations are rejected.

### 4.1 Report identity

| Field | Rule |
|---|---|
| `schema` | Exactly `triad.origin.full_pipeline_scorecard.input.v1` |
| `report_id` | Nonempty canonical text; unique within the archive |
| `as_of_us` | Nonnegative signed-64 integer; supplied observation cut in epoch microseconds |

The projector never reads wall time. Freshness and maturity are evaluated against supplied
evidence time and `as_of_us`.

### 4.2 Components

Each component row contains exactly:

```text
component_id
stage
role
mapping_status
mapping_evidence_refs
authority_claims
```

Allowed mapping states:

- `RATIFIED`: governed evidence binds the component to the stage;
- `OPERATOR_ASSERTED_UNATTESTED`: useful mapping hypothesis; caps publication below `FULL`;
- `UNBOUND`: no identity is assigned; publication blocker;
- `CONFLICT`: evidence assigns incompatible identities; publication blocker.

Authority claims use the closed per-stage enum. A component cannot claim authority outside its
stage. One authority class cannot have multiple claimants. Advisory stages E03–E06 cannot claim
E07, E08, or E09 authority.

### 4.3 Stage and edge proof object

Every stage/path observation and every canonical edge carries one proof object with exactly these
fields:

| Group | Fields |
|---|---|
| Identity | `evidence_id`, `source_kind`, `evidence_refs` |
| Source/deployment | `implementation`, `absence_proven`, `deployment_role`, `activation` |
| Time | `freshness`, `freshness_age_ms`, `freshness_bound_ms` |
| Trust | `reconciliation`, `attestation`, `side_effect_census_complete` |
| Four proof dimensions | `source_present`, `formula_correct`, `authority_closed`, `runtime_attested` |
| Lineage | `source_watermark`, `consumer_watermark` |
| Immutable subjects | `build_digest`, `config_digest`, `contract_digest`, `binding_digest` |
| Typed failure | `reason_code` |

Digest values are lowercase, nonzero SHA-256 strings. Diagnostic v1 validates their shape and
propagates them, but a future authenticated input profile must recompute and authenticate them from
authoritative bytes. Caller-supplied digest text alone never proves maturity.

`source_kind` is one of `AUTHORITATIVE_SOURCE`, `MIRROR`, or `EXPORT`. A mirror/export supports
diagnosis but cannot prove active writer, current control state, or `OFF`.

`deployment_role` is one of `ACTIVE_WRITER`, `REPLICA`, `MIRROR`, `DARK`, `RETIRED`, or
`UNKNOWN`. These are not health states.

### 4.4 Proof-state precedence

The renderer exposes the builder's fail-closed resolution:

1. stale evidence → `STALE`;
2. unknown freshness → `UNRECONCILED`;
3. mirror/export as current proof → `UNRECONCILED`;
4. missing/invalid attestation or reconciliation → `UNRECONCILED`;
5. explicit, authoritative, fresh absence proof plus complete side-effect census →
   `NOT_IMPLEMENTED`;
6. authoritative, fresh, attested dark/retired proof → `DARK`;
7. authoritative, fresh, attested OFF proof plus complete side-effect census → `OFF`;
8. all required dimensions, watermarks, digests, authority, and runtime evidence complete →
   `PROVEN`.

Silence, no rows, no orders, no process, or zero activity never proves `OFF`, `DARK`, or
`NOT_IMPLEMENTED`.

### 4.5 Four-plane posture

The posture object contains:

```text
desired
observed
freshness
reconciliation
attestation
side_effect_census_complete
evidence_refs
```

Both desired and observed, when present, use:

```text
venue_environment = LIVE | TESTNET | OFF
venue_activation  = LIVE | OFF
paper_activation  = LIVE | OFF
shadow_activation = LIVE
```

`shadow_activation` is fixed `LIVE`. `DARK`, `ENABLED`, `DISABLED`, `ON`, `TRUE`, and other aliases
are invalid lever values. When `venue_environment=OFF`, venue activation must also be `OFF`.

Diagnostic v1's accepted repository baseline is exactly OFF/OFF/OFF/LIVE in the named field order
above. The compact string may appear in prose, but the GUI always renders all four named values so
their meanings cannot be swapped.

### 4.6 Authoritative E02 cohort

The cohort object contains:

```text
cohort_id
window_start_us
window_end_us
source_watermark
source_cut_digest
complete
candidate_ids
zero_proof
evidence_refs
```

Rules:

- the window cannot end after `as_of_us`;
- every candidate ID must be unique and every evaluation candidate must belong to the cut;
- a nonempty cohort cannot carry a zero proof;
- an empty complete cohort is valid only with a nonzero query digest, source-cut digest,
  `source_completeness=COMPLETE`, and watermark;
- an empty proved cohort remains a status limitation; it cannot establish a functioning pipeline;
- an incomplete or missing cohort blocks publication.

### 4.7 Evaluations

Each evaluation contains:

```text
evaluation_id
candidate_id
decision_state
route_revision
observed_at_us
maturity_deadline_us
event_posture
```

`decision_state` is `ACCEPTED`, `REJECTED`, or `UNTRADEABLE`. Every evaluation ID is unique.
Multiple evaluations for one candidate require distinct evaluation IDs and explicit route
revisions. The event is routed from its captured event-time posture, never today's browser or
process posture.

### 4.8 Terminals

Each terminal contains:

```text
terminal_id
population_instance_id
kind
payload_digest
reason_code
evidence_refs
```

Closed terminal kinds:

```text
ABSTAINED
REJECTED
SHADOW_UNTRADEABLE
EXPIRED
WITHDRAWN_PRE_SEND
RISK_DENIED
ACCEPTED_NOT_EXECUTED
EXECUTION_REJECTED
CANCELED_NO_FILL
PROVEN_NO_VENUE_EFFECT
OUTCOME_COMPLETE
UNKNOWN_SUBMIT_UNRECONCILED
```

Refusal and unresolved terminals require a registered typed reason. Literal `unknown` is never a
valid reason. Exact replay of one identical terminal fact is idempotent. A second terminal ID,
kind, digest, reason, or evidence set for the same route is a conflict.

### 4.9 Metrics

Each metric contains:

```text
metric_id
metric_class
population
value_type
value
unit
availability
reason_code
zero_proof
evidence_refs
```

Rules:

- count metrics are exact nonnegative signed-64 integers with unit `COUNT`;
- decimal metrics are canonical non-exponent strings; binary floats are forbidden;
- economic metrics always name one explicit population;
- a missing value is `null` with a typed reason and non-observed availability;
- an observed numeric zero requires a complete zero proof;
- a nonzero value cannot carry a zero proof;
- SHADOW, PAPER, TESTNET, and LIVE rows never share one metric identity or denominator.

## 5. Conservation algorithm

### 5.1 Route derivation

For `REJECTED`, derive one SHADOW route allowing only `REJECTED`.

For `UNTRADEABLE`, derive one SHADOW route allowing only `SHADOW_UNTRADEABLE`.

For `ACCEPTED`:

1. always derive an independent SHADOW route;
2. add a PAPER route when event-time `paper_activation=LIVE`;
3. add exactly one venue route when event-time `venue_activation=LIVE`:
   - TESTNET when `venue_environment=TESTNET`;
   - LIVE when `venue_environment=LIVE`;
4. never derive a venue route when the environment is `OFF`;
5. never derive TESTNET and LIVE for the same evaluation.

The population-instance ID is a canonical hash of candidate ID, evaluation ID, population, and
route revision. Candidate count, evaluation count, route count, placement count, fill count, and
outcome count are different cardinalities and must not be presented as a sequential percentage
funnel unless their one-to-many relationships are explicit.

### 5.2 Reconciliation

Every matured population route requires exactly one compatible terminal. The report withholds on:

- matured route without terminal;
- incompatible terminal kind;
- competing terminal facts;
- terminal referencing no route;
- same terminal identity claimed across routes;
- `UNKNOWN_SUBMIT_UNRECONCILED`;
- implicit/undeclared evaluation multiplicity.

Unmatured routes may remain `PENDING_WITHIN_GRACE`, which is a status limitation. Unknown venue
submit can resolve only after authoritative order, algorithm-order, fill, position, and idempotency
reconciliation proves venue effect or proves none. It never silently falls back to SHADOW.

## 6. Metric profile

### 6.1 Mandatory counts

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
| E08 | `e08.risk.allowed.count`, `e08.risk.denied.count` × each population |
| E09 | `e09.execution.commands.count`, `e09.execution.fills.count`, `e09.execution.unknown_submit.count` × each population |
| E10 | `e10.outcomes.complete.count`, `e10.outcomes.unresolved.count` × each population |

### 6.2 Mandatory health/latency

All use canonical decimal milliseconds:

- `e00.data_freshness.p95_ms`
- `e03.forecast.latency.p95_ms`
- `e05.coordinator.latency.p95_ms`
- `e06.language_knowledge.latency.p95_ms`
- `e07.decision.latency.p95_ms`
- `e08.risk.latency.p95_ms` × population
- `e09.execution.ack_latency.p95_ms` × population

### 6.3 Optional economic metrics

All remain population-separated:

- `e09.execution.fill_rate`
- `e09.execution.slippage.mean_bps`
- `e10.outcomes.net_pnl.quote`
- `e10.outcomes.net_r_multiple`
- `e10.outcomes.win_rate`
- `e10.outcomes.profit_factor`
- `e10.outcomes.max_drawdown.quote`

Do not publish win rate, EV, MFE, MAE, capture, or P&L from a contract that lacks instrument,
side/role, campaign/decision/order identity, quantity, price, fees/cost lineage, event time,
environment, and population. Legacy `fill.v1` is insufficient; the migration is additive
`fill.v3` dual-publish, reconciliation, and consumer cutover. Published v1 bytes are immutable.

### 6.4 Official LIVE performance cut

When a future official LIVE performance view is authorized, its row filter is exactly:

```text
decision_status = ACCEPTED
route_mode       = LIVE
live_authority   = LIVE_ALLOWED
```

Rejected SHADOW rows are excluded from LIVE metrics, rankings, and performance gates. Accepted but
unfilled rows stay in the execution funnel. This filter does not alter canonical all-population
headline conservation totals.

## 7. Contract and identity evidence

For every cross-stage event, preserve the RC2 envelope concepts:

- contract name/version and schema digest;
- event, root, revision, and parent identities;
- producer, producer instance, build digest, and config digest;
- partition key, sequence, and source sequence range;
- event-time start/end, knowledge time, and publish time;
- correction target, lifecycle state, and quality flags;
- authority class, account scope, venue scope, and payload.

Semantic root identity remains stable; corrections append revisions. Idempotency is consumer plus
event ID. Event time, knowledge time, ingest time, and publish time are separate facts.

Relevant estate contracts include:

```text
market_event.v2
market_state.v2
feature_snapshot.v2
structure_atom.v2
structure_transition.v2
edge_candidate.v2
divergence_record.v1
candidate_authority.v1
decision.v2
risk_decision.v2
risk_reservation.v1
execution_authorization.v3
execution_cmd.v2
order_event.v2
fill.v3
venue_account_event.v2
position_event.v2
protection_event.v2
outcome.v2
producer_lease.v1
quarantine_record.v1
```

The RC2 written wiring registry does not yet ratify product-specific Kairos/Logos contracts. Labels
such as `forecast.v1`, `calibrated_forecast.v1`, `forecast_request.v2`, or
`logos_prompt_packet.v1` may be design proposals or diagnostic wire objects; do not render them as
normative deployed contracts without a separately governed binding artifact.

RC4 control-plane evidence additionally includes:

```text
engine_control_manifest.v2
runtime_lever_registry.v1
runtime_lever_attestation.v1
shadow_trade.v1
shadow_rejection_audit.v1
paper_trade.v1
shadow_health.v1
execution_authorization.v3
fill.v3
```

Schema validity is necessary but insufficient. Semantic checks must cover scope, registry
completeness, isolation, lease fencing, freshness, signatures, route/account/environment binding,
and mutually legal lever combinations.

## 8. Freshness and boundary constants

Freshness is derived from evidence/event time, never browser render time.

| Check | Bound |
|---|---:|
| Lever cache age | 2,000 ms |
| Control poll interval | 1,000 ms |
| OFF entry-block deadline | 2,000 ms |
| Lease renewal | 5,000 ms |
| Lease TTL | 15,000 ms |
| Runtime attestation interval | 5,000 ms |
| Runtime attestation max age | 15,000 ms |
| Private state max age | 5,000 ms |
| Environment attestation max age | 60,000 ms |
| Clock skew | 250 ms |
| SHADOW rejection persistence | 100 ms |
| SHADOW heartbeat interval | 1,000 ms |
| SHADOW health max age | 5,000 ms |
| Resolver processable backlog | 60,000 ms |
| Drain review interval | 1,000 ms |
| Drain timeout | 300,000 ms |
| Post-change side-effect audit | 900,000 ms |

Test one millisecond below, exactly at, and one millisecond above every boundary. Do not assume the
same bound for a source whose governed contract specifies a stricter value.

## 9. Read-only MCP acquisition

MCP is an evidence facade, not semantic authority, deployment truth, certification, or venue
authority. The 2026-08-07 MCP book is a historical observation and contains internally stale tool
counts. Rediscover the current surface for every acquisition run.

The acquisition runner—not the browser and not `src/triad_origin`—must:

1. initialize using the server's advertised current MCP protocol and both JSON/SSE response types;
2. capture the returned session identifier without writing it into artifacts;
3. call `tools/list` for the exact deployment being observed;
4. invoke only discovered, approved, read-only tools;
5. parse all SSE `data:` frames and preserve the complete response envelope;
6. retain source, plane, cohort, timestamp, revision, availability, timeout, and error identity;
7. page and bound heavy reads; do not infer completeness from the first page;
8. classify the response as authoritative source, mirror, or export;
9. redact transport/session material before writing the scorecard input;
10. close the session without any configuration mutation.

Never call `propose_action` or `record_checkup`. Never enable a dark MCP family as part of report
generation. Never bake a token into an endpoint query, HTML, JavaScript, repository, report, or
log. Authentication mechanisms have differed between historical sources; discover the current
server contract rather than assuming pairing or bearer behavior.

Historical ceilings were 120 cheap and 30 heavy calls per minute with a 30-second timeout. Treat
these as dated observations, not current configuration. Rediscover and record current bounds.

### 9.1 Required acquisition evidence per component

- exact component and deployment identity;
- repository revision, build/image, config, contract, binding, and parameter digests;
- deployment role and active-writer claim;
- producer scope, epoch, and fenced lease verification;
- source watermark and event-time cut;
- attestation timestamp and freshness calculation;
- source-versus-mirror classification and mirror lag;
- contract/schema version and semantic-validation result;
- authority claimant and duplicate/conflict check;
- availability or exact named failure;
- population/plane, cohort, and denominator definition.

A process listing, file existence, branch name, hostname, or successful health endpoint is not
active-writer proof.

## 10. SSH fallback

SSH is a restricted fallback for fresh evidence, not the primary integration. The existing
host-specific SSH guide contains active operational access material and must remain outside this
repository and generated artifacts.

Rules:

- use only separately approved, exact read-only commands;
- never copy an address, password, key, token, secret path, tunnel instruction, or recovery value
  into this guide, input, output, log, or screenshot;
- do not start/stop a VM or container, exec arbitrary container commands, inspect secret files,
  edit an environment/supervisor, restart a service, or change a feature/family gate;
- record command identity, operator, host role, observation time, exit status, output digest, and
  redaction receipt outside the report;
- treat reachability/process presence as availability evidence only, not writer or authority proof;
- rotate exposed legacy credentials through the restricted operational process.

## 11. Generate the scorecard

From the repository root:

```bash
PYTHONPATH=src python tools/generate_full_pipeline_scorecard.py \
  docs/scorecard/examples/status_only_input.v1.json \
  --diagnostic-only \
  --json-output /tmp/triad-scorecard.json \
  --html-output /tmp/triad-scorecard.html
```

For a publication attempt, omit `--diagnostic-only`:

```bash
PYTHONPATH=src python tools/generate_full_pipeline_scorecard.py \
  evidence.json \
  --json-output scorecard.json \
  --html-output scorecard.html
```

Exit codes:

| Exit | Meaning |
|---:|---|
| 0 | `FULL`, or a successfully emitted non-FULL diagnostic explicitly allowed by `--diagnostic-only` |
| 1 | Input/model/digest/render validation failed; no valid report |
| 2 | A `WITHHELD` or `STATUS_ONLY` report was emitted and default publication failed closed |

Always archive input digest, JSON digest, HTML digest, exact source commit, command, exit code, and
runner identity together. Never treat `--diagnostic-only` as a publication or authority override;
it changes only the process exit after successful emission.

## 12. GUI behavior and visual truth

The adjusted GUI reuses the useful legacy scorecard language—dense tables, compact chips,
callouts, sticky headers—and the master topology's dark layer palette. It deliberately changes the
semantics:

- no generic `LIVE` title;
- no `PROMOTE` badge or action wording;
- no target architecture presented as deployed fact;
- no missing value rendered as zero, green, PASS, OFF, or DARK;
- no SHADOW/MONEY or PAPER/TESTNET/LIVE aggregation;
- no E03→E06 route;
- E03 Kairos and E06 Logos mappings remain visibly asserted until attested;
- E05 remains its own coordinator;
- E09 new exposure and reconciliation paths remain distinct;
- green is reserved for `PROVEN` evidence or satisfied aggregate stage proof;
- target/legacy analysis remains subordinate to as-built evidence.

The legacy 418-cell file is historical static backfill, not a current full-pipeline scorecard. Its
header/footer and subsection counts conflict, `PROMOTE` rows still have a pending gate, and its
accepted-only display is not candidate conservation. Do not copy those counts into the new UI.
Import a historical matrix only through a separately identified cohort/window/population with fee
lineage, numerator, denominator, confidence interval, coverage, and complete E02→E10 identity.

### 12.1 Responsive/accessibility contract

- one E00–E10 stage card each; E09 paths are grouped within one stage card;
- no more than four cards per desktop row, then two and one at narrower widths;
- tables scroll horizontally instead of crushing columns;
- skip link, navigation and main/section landmarks;
- table captions, `thead`/`tbody`, and scoped column headers;
- 48-pixel navigation and disclosure targets;
- visible keyboard focus and reduced-motion support;
- status is text plus symbol, never color alone;
- print output exposes disclosure content and removes sticky navigation.

## 13. Security controls

Required controls:

- strict closed-object decoder and duplicate-key refusal;
- HTML escaping for every caller-supplied string;
- digest verification before HTML rendering;
- CSP denying script, connect, object, media, frame, base, and form actions;
- no external URLs or fonts in generated HTML;
- no dynamic import/eval/exec/getattr construction;
- static capability gate over all runtime Python;
- artifact secret scan for JWT/bearer/query-token/authorization/credential patterns;
- canonical JSON and deterministic byte output across hash seeds;
- no browser fetch, storage, service worker, or session behavior.

Model-generated Logos text is untrusted data. It must remain escaped evidence content and may not
be interpreted as HTML, code, a tool call, a policy, or a control instruction.

## 14. Validation matrix

### 14.1 Input/model tests

- positive fixture plus recursive negative fixtures;
- duplicate/unknown/missing field rejection;
- invalid enum and noncanonical alias rejection;
- float, exponent, nonfinite, overflow, and negative-count rejection;
- observed zero without zero proof rejection;
- null with no typed availability/reason rejection;
- cross-language canonical identity/hash vectors;
- caller-provided hashes cannot establish `FULL`;
- empty/incomplete/missing cohort cannot establish `PROVEN` pipeline maturity.

### 14.2 Topology/authority tests

- E00–E10 appear once in the pipeline view;
- E03 is forecast/Kairos asserted, E05 coordinator, E06 language/knowledge/Logos asserted;
- no Kronos alias in this profile and no direct E03→E06 edge;
- E06 contract boundary remains visible;
- duplicate E07 or any authority claimant fails closed;
- advisory-to-risk/execution bypass fails closed;
- unbound/conflicting mappings block publication.

### 14.3 Conservation/population tests

- every candidate is evaluated;
- accepted evaluation always has independent SHADOW;
- PAPER may coexist with one TESTNET or LIVE route;
- TESTNET and LIVE cannot coexist for one evaluation;
- event-time posture, not report-time posture, controls route derivation;
- missing/unknown/stale posture cannot pass;
- one terminal per matured route;
- exact replay is idempotent; competing duplicate/orphan is a failure;
- unknown-submit and late-fill contamination remain unresolved;
- SHADOW, PAPER, TESTNET, and LIVE never cross-count;
- fill cardinality supports zero-to-many fills per placement with identities.

### 14.4 Metric/UI tests

- null timestamp/hold/P&L remains null;
- observed zero displays a receipt-backed zero, not missing data;
- summary counts are derived from canonical rows;
- any heading/footer/row count mismatch fails generation tests;
- filters in any future interactive wrapper cannot mutate canonical totals;
- unmatched Kairos/Logos comparison cannot be green or promotion-eligible;
- XSS payloads render as text;
- generated browser artifact contains no script, endpoint, token, or external request;
- 320, 375, 768, and 1440-pixel visual snapshots remain legible;
- keyboard, screen-reader, color-blind, contrast, reduced-motion, and print checks pass.

### 14.5 Repository gates

Run the repository law exactly:

```bash
PYTHONHASHSEED=0 python -m pytest
PYTHONHASHSEED=1 python -m pytest
python tools/collect_test_ids.py
python tools/verify_manifest.py
python tools/validate_contract_manifest.py
python tools/verify_reproducible_build.py
python tools/test_wheel_install.py
python tools/verify_no_forbidden_capabilities.py
python tools/e2e_audit.py
python tools/build_ledger.py --verify
python tools/validate_combined_dag.py
```

Also validate the example input, deterministic JSON/HTML bytes, CSP/no-network structure, and a
clean installed-wheel import. Local green is engineering evidence, not merge or closure evidence.

## 15. Deployment sequence

### 15.1 Source integration

1. Close the authorized predecessor milestone and its receipt/anchor; do not side-door it through
   this branch.
2. Establish a governed milestone/path grant for every scorecard source, test, tool, example, and
   guide path.
3. Preserve this branch history; merge validated current `main` into it normally rather than
   force-pushing or rewriting.
4. Reconcile source hashes, classifier scope, package inventory, and the E2E audit under that
   milestone.
5. Generate JSON/HTML from closed fixtures and compare with the historical UI only as a report.
6. Open one source PR whose diff contains only the governed scorecard milestone.
7. Require exact-final-head CI, code-owner/last-push approval, zero unresolved threads, and an
   ordinary protected merge.
8. Reproduce against the exact merged `main` hash and land the separate evidence-only receipt PR.

### 15.2 Read-projection deployment

1. Deploy only the static read projection or separately governed acquisition runner.
2. Record deployed commit/image/config/input/output digests and immutable artifact location.
3. Confirm zero credential, control, lease-issuer, network-to-venue, or order capability in the
   projector.
4. Dual-read legacy and canonical sources for at least seven continuous days and through restart,
   stale-cache, partition, pagination, timeout, and lease-expiry drills.
5. Compare source cuts, watermarks, population totals, terminal conservation, and mirror lag.
6. Keep publication `WITHHELD`/`STATUS_ONLY` until every required proof is authenticated.

No source merge implies deployment. No deployment implies restart. No read-projection deployment
implies activation. Any future enforcement/promotion is a separate governed action.

## 16. Rollback

Projection-only rollback:

1. stop serving the affected static projection or disable only its separately governed read
   family;
2. restore the last attested immutable JSON/HTML pair;
3. preserve failed artifacts and append correction/supersession evidence;
4. verify trading/data planes were untouched;
5. rerun conservation and source-cut comparison before restoring publication.

Never rewrite or delete a published report to hide a defect. If a wider runtime rollback is ever
separately authorized, venue and PAPER activation go OFF first, SHADOW remains LIVE, and
protection/cancel/reconciliation/reduction for existing exposure remains available.

## 17. Named failures and troubleshooting

| Symptom | Required state/code | Action |
|---|---|---|
| No stage row | `SCORECARD_EVIDENCE_MISSING` | Repair acquisition; do not invent `OFF` |
| Mirror claims current writer | `SCORECARD_MIRROR_NOT_AUTHORITATIVE` | Obtain authoritative source/lease proof |
| Evidence past bound | `SCORECARD_EVIDENCE_STALE` | Refresh exact source cut |
| Posture missing or mismatched | `SCORECARD_POSTURE_UNPROVEN` / `SCORECARD_POSTURE_MISMATCH` | Obtain fresh attestation/census; do not infer |
| Kairos/Logos name only | `SCORECARD_MAPPING_UNATTESTED` | Bind governed cross-repository mapping |
| Missing component identity | `SCORECARD_MAPPING_UNBOUND` | Bind exact component or remain withheld |
| Candidate absent from evaluation | `SCORECARD_CANDIDATE_UNEVALUATED` | Repair E02→E07 conservation |
| Evaluation outside cohort | `SCORECARD_EVALUATION_ORPHAN` | Repair source cut/join |
| Mature route has no terminal | `SCORECARD_TERMINAL_UNEXPLAINED` | Reconcile terminal lineage |
| Terminal conflicts/orphans | `SCORECARD_TERMINAL_CONFLICT` | Resolve identity/duplicate defect |
| Submit state uncertain | `UNKNOWN_SUBMIT_UNRECONCILED` | Reconcile orders/fills/positions; no retry/fallback |
| Metric contract lacks lineage | `NOT_MEASURABLE` / `FEE_LINEAGE_MISSING` | Migrate additively to sufficient contract |
| Bounded acquisition exceeds budget | `TOOL_TIMEOUT` | Record timeout; page/batch within approved limits |
| Browser shows zero for missing | `SCORECARD_NULL_COERCION_FORBIDDEN` | Fix renderer/input; missing remains null |

Preserve RC4 refusal codes verbatim when they are the originating failure, including:

```text
VENUE_ENVIRONMENT_VALUE_INVALID
VENUE_ACTIVATION_VALUE_INVALID
PAPER_ACTIVATION_VALUE_INVALID
ACTIVATION_VALUE_INVALID
SCOPE_VALUE_INVALID
OFF_WITH_LIVE_VENUE_ACTIVATION
OFF_TRANSITION_EXPOSURE_REMAINS
LIVE_TESTNET_BINDING_FORBIDDEN
TESTNET_LIVE_BINDING_FORBIDDEN
MIXED_ENVIRONMENT_BUNDLE_FORBIDDEN
DIRECT_ENVIRONMENT_TRANSITION_FORBIDDEN
LIVE_PROMOTION_RECEIPT_MISSING
LEGACY_LEVER_ALIAS_FORBIDDEN
LEVER_REGISTRY_INCOMPLETE
RUNTIME_LEVER_ATTESTATION_MISMATCH
LEVER_REVISION_STALE
PRODUCER_LEASE_MISSING
PRODUCER_LEASE_CONFLICT
VENUE_ENVIRONMENT_UNVERIFIED
VENUE_BINDING_MISMATCH
OPPOSITE_ENVIRONMENT_REACHABLE
PRIVATE_STATE_STALE
UNKNOWN_SUBMIT_UNRECONCILED
SHADOW_CAPTURE_OFF_FORBIDDEN
SHADOW_REJECTION_NOT_PERSISTED
SHADOW_HEALTH_STALE
SHADOW_UNTRADEABLE
SHADOW_LINEAGE_INCOMPLETE
SHADOW_MONEY_CONTAMINATION
PAPER_VENUE_EFFECT_FORBIDDEN
PAPER_LEDGER_CONTAMINATION
ACCEPTED_CANDIDATE_UNRECORDED
```

Do not collapse `unavailable`, `not_implemented`, `tool_timeout`, `not_measurable`, `stale`, and
`not_attested`; they represent different failures and remediation owners.

## 18. Current merge gate — 2026-08-12

This branch is a direct descendant of the still-unmerged B00R G2 repair head. It therefore cannot
be merged to `main` safely: doing so would import that predecessor through a different PR. It also
cannot be merged into the G2 branch without changing G2's frozen scope and exact-head evidence.

In addition, the current B00R source classifier does not grant the scorecard paths. A scorecard PR
opened under that milestone would fail `SOURCE_PATH_OUT_OF_SCOPE`. Do not broaden a frozen
predecessor classifier inside this branch to self-authorize the change.

The safe merge order is:

1. PR #34 exact-head external authority/provider gates, required CI, independent code-owner review,
   and protected ordinary merge;
2. separate G2 receipt PR, protected G2 anchor, and terminal B00R gate;
3. governed B01C and downstream predecessor receipts through the owning read-face milestone;
4. explicit scorecard path/acceptance grant;
5. normal merge of validated `main` into this same branch, without history rewrite;
6. exact-head scorecard CI, final-push code-owner approval, zero threads, protected merge;
7. exact-merged-main reproduction and separate evidence receipt.

“Merge on green” means all required ancestry, scope, CI, review, and receipt gates are green—not
only the local Python suite.

## 19. Operator handoff checklist

- [ ] Input schema exact and duplicate-key safe.
- [ ] E00–E10 component identities and mapping states explicit.
- [ ] Kairos/E03, E05 coordinator, and Logos/E06 remain separate.
- [ ] No E03↔E06 or advisory-to-money bypass.
- [ ] Desired and observed named four-plane posture supplied separately.
- [ ] Authoritative E02 cohort complete with cut digest and watermark.
- [ ] Every evaluation uses event-time posture and explicit route revision.
- [ ] Every accepted evaluation has independent SHADOW.
- [ ] PAPER/TESTNET/LIVE routes remain distinct.
- [ ] Every matured route has one compatible terminal.
- [ ] Unknown submit count is zero or publication is withheld.
- [ ] Every zero has a zero proof; every missing value stays null.
- [ ] Money metrics have complete contract/fee/population lineage.
- [ ] Source/mirror role and lag are explicit.
- [ ] All digests, leases, attestations, and evidence references bind exact subjects.
- [ ] Generated HTML has zero external requests and no secrets/endpoints.
- [ ] Dual hash-seed, full E2E, capability, reproducibility, package, and example gates pass.
- [ ] Exact-head provider CI and independent final-push review pass.
- [ ] Predecessor/receipt/anchor order is valid.
- [ ] Runtime posture remains OFF/OFF/OFF/LIVE unless a later separate authority changes it.
