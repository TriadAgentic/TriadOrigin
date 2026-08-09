#!/usr/bin/env python3
"""Build the standalone ORIGIN V7 four-plane and lever-control addendum."""

from __future__ import annotations

import base64
import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "TRIAD_ORIGIN_V7_FOUR_PLANE_EXECUTION_AND_LEVER_MASTER_ADDENDUM_1.0.0_RC4.html"
TOPOLOGY = ROOT / "project_sources/01-06_TRIAD_MASTER_TOPOLOGY_ILLUSTRATIVE_OVERVIEW_V3-1-.png"
RC3 = ROOT / "TRIAD_ORIGIN_V7_COMPLETE_MASTER_SPECIFICATION_AND_MASTER_DOCUMENT_1.0.0_RC3.html"
VERSION = "1.0.0-RC4-ADDENDUM"
ISSUED_UTC = "2026-08-09T01:00:00Z"
STATUS = "OWNER_DIRECTIVE_RATIFIED_IMPLEMENTATION_NOT_APPLIED"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def chip(value: str, tone: str = "") -> str:
    return f'<span class="chip {esc(tone)}">{esc(value)}</span>'


def callout(title: str, body: str, tone: str = "info") -> str:
    return f'<div class="callout {esc(tone)}"><strong>{esc(title)}</strong><div>{body}</div></div>'


def table(headers: list[str], rows: list[list[object]], table_id: str = "") -> str:
    identity = f' id="{esc(table_id)}"' if table_id else ""
    head = "".join(f"<th>{esc(header)}</th>" for header in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows
    )
    return f'<div class="table-wrap"><table{identity}><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def section(anchor: str, number: str, title: str, content: str) -> str:
    return f'<section class="chapter" id="{esc(anchor)}"><h2><span>{esc(number)}</span>{esc(title)}</h2>{content}</section>'


def filter_toolbar(table_id: str, count: int, facets: list[str]) -> str:
    selects = "".join(
        f'<select data-facet-for="{esc(table_id)}" data-facet="{esc(facet)}"><option value="">All {esc(facet)}</option></select>'
        for facet in facets
    )
    return (
        f'<div class="toolbar no-print"><input type="search" data-query-for="{esc(table_id)}" '
        f'placeholder="Search {esc(table_id)}…">{selects}<button data-reset-for="{esc(table_id)}">Reset</button>'
        f'<span data-count-for="{esc(table_id)}">{count} / {count}</span></div>'
    )


_VENUE_COMBINATIONS = [
    ("LIVE", "LIVE", "Accepted candidates may reach exactly attested real-money endpoints, accounts, credentials, leases, E08, and E09."),
    ("LIVE", "OFF", "No new/increasing real-money exposure; reconciliation, cancel, protection, and verified reduction remain available until flat."),
    ("TESTNET", "LIVE", "Accepted candidates may reach exactly attested exchange testnet endpoints/accounts through the same E09 lifecycle used by LIVE."),
    ("TESTNET", "OFF", "Testnet connectivity and reconciliation may remain; no new/increasing testnet exposure."),
    ("OFF", "OFF", "No venue session, credential, producer lease, money-selection lease, or venue effect."),
]
VALID_COMBINATIONS = [
    {
        "venue_environment": environment,
        "venue_activation": activation,
        "paper_activation": paper_activation,
        "shadow_activation": "LIVE",
        "meaning": meaning + (" PAPER demo execution also records accepted candidates." if paper_activation == "LIVE" else " PAPER demo execution is OFF."),
    }
    for environment, activation, meaning in _VENUE_COMBINATIONS
    for paper_activation in ("LIVE", "OFF")
]

INVALID_ALIASES = [
    "live", "testnet", "off", "ON", "ENABLED", "DISABLED", "TRUE", "FALSE", "true", "false",
    "1", "0", "DARK", "SHADOW", "PAPER", "DRYRUN", "DRY-RUN", "SIMULATED", "SIMULATION",
    "CANARY", "PRODUCTION", "PROD", "DEV", "STAGE", "ARMED", "DISARMED", "OPERATIONAL",
    "execution", "small_live", "PILOT", "log", "enforce", "trigger_veto", "", "null",
]

REFUSALS = [
    ("VENUE_ENVIRONMENT_VALUE_INVALID", "venue_environment is missing or not exactly LIVE, TESTNET, or OFF."),
    ("VENUE_ACTIVATION_VALUE_INVALID", "venue_activation is missing or not exactly LIVE or OFF."),
    ("PAPER_ACTIVATION_VALUE_INVALID", "paper_activation is missing or not exactly LIVE or OFF."),
    ("ACTIVATION_VALUE_INVALID", "A registered component or feature activation is missing or not exactly LIVE or OFF."),
    ("SCOPE_VALUE_INVALID", "A manifest scope is missing, malformed, contains a wildcard, or is not exact."),
    ("OFF_WITH_LIVE_VENUE_ACTIVATION", "venue_environment OFF is paired with venue_activation LIVE."),
    ("OFF_TRANSITION_EXPOSURE_REMAINS", "venue_environment OFF requested while positions, orders, reservations, or protection lifecycle remain."),
    ("LIVE_TESTNET_BINDING_FORBIDDEN", "LIVE record contains any testnet endpoint, account, credential, order, fill, ledger, or route."),
    ("TESTNET_LIVE_BINDING_FORBIDDEN", "TESTNET record contains any live endpoint, account, credential, order, fill, ledger, or route."),
    ("MIXED_ENVIRONMENT_BUNDLE_FORBIDDEN", "One activation/evidence bundle contains both LIVE and TESTNET members."),
    ("DIRECT_ENVIRONMENT_TRANSITION_FORBIDDEN", "LIVE↔TESTNET transition did not pass through OFF activation, reconciliation, flatness, isolation, and OFF environment."),
    ("LIVE_PROMOTION_RECEIPT_MISSING", "LIVE activation lacks a current successful TESTNET promotion receipt for the same build, contracts, strategy, scope, and venue lifecycle."),
    ("LEGACY_LEVER_ALIAS_FORBIDDEN", "A legacy word, boolean, integer, blank, null, or coercion was supplied to a canonical lever slot."),
    ("LEVER_REGISTRY_INCOMPLETE", "A required component or feature is absent, duplicated, unknown, or not digest-bound."),
    ("RUNTIME_LEVER_ATTESTATION_MISMATCH", "Runtime readback differs from the signed manifest or accepted revision."),
    ("LEVER_REVISION_STALE", "A command, lease, route, or runtime readback carries a superseded revision."),
    ("PRODUCER_LEASE_MISSING", "Non-OFF authority lacks one current fenced producer lease for the exact scope."),
    ("PRODUCER_LEASE_CONFLICT", "More than one non-OFF producer claims an overlapping scope."),
    ("VENUE_ENVIRONMENT_UNVERIFIED", "Venue/account environment cannot be verified from authoritative venue evidence."),
    ("VENUE_BINDING_MISMATCH", "Top-level environment or scope differs from the manifest venue/account/route binding."),
    ("OPPOSITE_ENVIRONMENT_REACHABLE", "The engine instance can reach both LIVE and TESTNET authority surfaces."),
    ("PRIVATE_STATE_STALE", "Order, position, or protection truth exceeds the declared freshness bound."),
    ("UNKNOWN_SUBMIT_UNRECONCILED", "A venue submit has unknown effect and cannot be classified as rejected or routed to SHADOW until private-state reconciliation proves zero venue effect."),
    ("SHADOW_CAPTURE_OFF_FORBIDDEN", "An attempt was made to set mandatory shadow capture to OFF."),
    ("SHADOW_REJECTION_NOT_PERSISTED", "A shadow-tradeable REJECTED candidate was not durably persisted to the SHADOW recorder inside the deadline."),
    ("SHADOW_HEALTH_STALE", "The mandatory SHADOW writer heartbeat or processable resolver watermark exceeds its declared freshness bound."),
    ("SHADOW_UNTRADEABLE", "An event or candidate fails the shadow-tradeability contract and is recorded without fabricating geometry or a trade."),
    ("SHADOW_LINEAGE_INCOMPLETE", "Candidate, rejection, shadow trade, resolver, or outcome lineage is missing or ambiguous."),
    ("SHADOW_MONEY_CONTAMINATION", "Shadow evidence contains a venue money fact or a money metric combines shadow and venue populations."),
    ("PAPER_VENUE_EFFECT_FORBIDDEN", "A PAPER record, credential, route, or command can reach a venue effect."),
    ("PAPER_LEDGER_CONTAMINATION", "PAPER demo facts were combined with SHADOW, TESTNET, or LIVE outcome/PnL denominators."),
    ("ACCEPTED_CANDIDATE_UNRECORDED", "A complete accepted candidate reached neither PAPER nor venue and has no SHADOW non-execution record."),
]


def refusal_action(code: str) -> str:
    if code in {"VENUE_ENVIRONMENT_VALUE_INVALID", "VENUE_ACTIVATION_VALUE_INVALID", "OFF_WITH_LIVE_VENUE_ACTIVATION", "OFF_TRANSITION_EXPOSURE_REMAINS", "LIVE_TESTNET_BINDING_FORBIDDEN", "TESTNET_LIVE_BINDING_FORBIDDEN", "MIXED_ENVIRONMENT_BUNDLE_FORBIDDEN", "DIRECT_ENVIRONMENT_TRANSITION_FORBIDDEN", "LIVE_PROMOTION_RECEIPT_MISSING", "VENUE_ENVIRONMENT_UNVERIFIED", "VENUE_BINDING_MISMATCH", "OPPOSITE_ENVIRONMENT_REACHABLE", "PRIVATE_STATE_STALE", "UNKNOWN_SUBMIT_UNRECONCILED"}:
        return "venue_activation=OFF; paper_activation unchanged; shadow_activation=LIVE."
    if code == "PAPER_ACTIVATION_VALUE_INVALID":
        return "paper_activation=OFF; venue_activation unchanged; shadow_activation=LIVE."
    if code in {"SHADOW_CAPTURE_OFF_FORBIDDEN", "SHADOW_UNTRADEABLE"}:
        return "Reject the requested/invalid record; preserve shadow_activation=LIVE; do not change a proven-safe execution activation solely for this record-local refusal."
    if code == "PAPER_LEDGER_CONTAMINATION":
        return "Reject the aggregation; paper_activation=OFF for the affected scope pending repair; shadow_activation=LIVE."
    if code in {"SHADOW_REJECTION_NOT_PERSISTED", "SHADOW_HEALTH_STALE", "SHADOW_LINEAGE_INCOMPLETE", "SHADOW_MONEY_CONTAMINATION", "PAPER_VENUE_EFFECT_FORBIDDEN", "ACCEPTED_CANDIDATE_UNRECORDED"}:
        return "venue_activation=OFF; paper_activation=OFF for the affected scope; shadow_activation=LIVE; quarantine the invalid evidence."
    return "venue_activation=OFF; paper_activation=OFF for the affected scope; shadow_activation=LIVE until current proof converges."

TIMINGS = [
    ("lever_cache_max_age_ms", 2000, "Every money-authority consumer; stale resolves activation to OFF."),
    ("control_poll_interval_ms", 1000, "Fallback poll in addition to event delivery."),
    ("off_entry_block_deadline_ms", 2000, "Maximum from accepted OFF revision to global new-exposure denial."),
    ("producer_lease_renew_interval_ms", 5000, "Lease holder renews with the same revision and fencing epoch."),
    ("producer_lease_ttl_ms", 15000, "Expired lease cannot publish authoritative money candidates or commands."),
    ("runtime_attestation_interval_ms", 5000, "Each engine instance emits digest-bound readback."),
    ("runtime_attestation_max_age_ms", 15000, "Stale readback resolves activation to OFF."),
    ("private_state_max_age_ms", 5000, "Maximum order/position/protection truth age for new exposure."),
    ("environment_attestation_max_age_ms", 60000, "Authoritative account/route/environment proof freshness."),
    ("clock_skew_max_ms", 250, "Maximum absolute skew for control, lease, and evidence clocks."),
    ("shadow_rejection_persist_deadline_ms", 100, "Shadow-tradeable REJECTED candidate must be durably recorded before its disposition is acknowledged."),
    ("shadow_health_heartbeat_interval_ms", 1000, "Mandatory writer/consumer heartbeat."),
    ("shadow_health_max_age_ms", 5000, "Stale mandatory rejection recorder forces venue and PAPER activation OFF until recovered."),
    ("shadow_resolver_backlog_max_age_ms", 60000, "Maximum processable tape/backlog lag; future-horizon rows remain pending by definition."),
    ("environment_drain_review_interval_ms", 1000, "Recheck positions, orders, reservations, protections, leases, sessions during drain."),
    ("environment_drain_timeout_ms", 300000, "At timeout remain in current venue_environment with venue_activation OFF; never force unsafe venue_environment OFF."),
    ("post_change_side_effect_audit_ms", 900000, "Immutable census after every change."),
]

LIVE_REGISTRY = [
    {
        "engine": "newnaut",
        "registry": "role=execution; enabled=true; source=yn:paper:decisions; v3.1.1",
        "freshness": "last decision 2026-08-09T00:51:07.164Z",
        "contradiction": "Global execution source, but source is named paper; payload identity is newnaut_v2, absent from registry.",
        "venue_environment": "OFF",
        "venue_activation": "OFF",
        "proof": "NONCONFORMING / NOT ENFORCED",
    },
    {
        "engine": "newnaut_v2",
        "registry": "Absent from registry; present in payloads and relay/fill history",
        "freshness": "upstream fresh; relay last seen 2026-08-08T22:48:42.858Z",
        "contradiction": "Fresh upstream and >2-hour stale relay; historical Binance fills exist.",
        "venue_environment": "OFF",
        "venue_activation": "OFF",
        "proof": "NONCONFORMING / NOT ENFORCED",
    },
    {
        "engine": "newnaut_pinned",
        "registry": "role=execution; enabled=true; Redis source",
        "freshness": "last decision null",
        "contradiction": "Execution role without liveness, route, environment, lease, or side-effect proof.",
        "venue_environment": "OFF",
        "venue_activation": "OFF",
        "proof": "NONCONFORMING / NOT ENFORCED",
    },
    {
        "engine": "newnaut_djordi",
        "registry": "role=shadow; enabled=false; NATS source",
        "freshness": "last decision null",
        "contradiction": "Legacy boolean/role cannot prove effect cessation or canonical environment.",
        "venue_environment": "OFF",
        "venue_activation": "OFF",
        "proof": "NONCONFORMING / NOT ENFORCED",
    },
    {
        "engine": "newnaut_supertrend",
        "registry": "role=shadow; enabled=true; source=yn:supertrend:decisions; ab1",
        "freshness": "last decision null",
        "contradiction": "Enabled shadow role has no current decision evidence; shadow population must use fixed activation LIVE, not a boolean.",
        "venue_environment": "OFF",
        "venue_activation": "OFF",
        "proof": "NONCONFORMING / NOT ENFORCED",
    },
    {
        "engine": "triad",
        "registry": "role=shadow; enabled=true; NATS source; selected by Binance and HL routes",
        "freshness": "last decision null; not in service probes",
        "contradiction": "Both money venues select an engine registered as shadow with no liveness evidence.",
        "venue_environment": "OFF",
        "venue_activation": "OFF",
        "proof": "NONCONFORMING / NOT ENFORCED",
    },
    {
        "engine": "yolonaut",
        "registry": "Absent; service flag signal_backend.mode=yolonaut and yolonaut_enabled=true",
        "freshness": "relay last seen 2026-06-22T20:37:06Z",
        "contradiction": "Selected by stale legacy flags but absent from registry and current route proof.",
        "venue_environment": "OFF",
        "venue_activation": "OFF",
        "proof": "NONCONFORMING / NOT ENFORCED",
    },
    {
        "engine": "tidlenaut",
        "registry": "Absent; relay history only",
        "freshness": "last seen 2026-06-22T22:39:22Z",
        "contradiction": "No canonical registration, route, environment, lease, or live process evidence.",
        "venue_environment": "OFF",
        "venue_activation": "OFF",
        "proof": "NONCONFORMING / NOT ENFORCED",
    },
    {
        "engine": "rust-shadow / uo-signal",
        "registry": "Config and historical fingerprints exist; registry identity absent",
        "freshness": "No authoritative current route timestamp",
        "contradiction": "BREAKOUT_MODE=live and execution booleans true, but no environment or money-route proof.",
        "venue_environment": "OFF",
        "venue_activation": "OFF",
        "proof": "NONCONFORMING / NOT ENFORCED",
    },
    {
        "engine": "TRIAD ORIGIN V7",
        "registry": "Not deployed; RC3 SAFE_HOLD",
        "freshness": "No runtime instance",
        "contradiction": "Specification candidate only.",
        "venue_environment": "OFF",
        "venue_activation": "OFF",
        "proof": "CONFORMING TARGET / NOT DEPLOYED",
    },
]
for _engine_row in LIVE_REGISTRY:
    _engine_row["paper_activation"] = "OFF"
    _engine_row["shadow_activation"] = "LIVE"

CODEBASE_INVENTORY = [
    {
        "engine_id": "quant-trade-0", "display": "QuantTrade 0", "as_built": "Broad monolith with exchange path; pinned branch staging.",
        "blocking_evidence": "Branch name is not environment proof; no authoritative control, account, route, credential, kill dominance, or current attestation is established.",
    },
    {
        "engine_id": "yolonaut-1", "display": "YoloNaut 1", "as_built": "Signal/execution assembly; pinned branch production; current direct NewNaut V2 decision path.",
        "blocking_evidence": "Branch name is not LIVE; direct-versus-external executor authority and venue environment are unproven.",
    },
    {
        "engine_id": "yolobotv2-2", "display": "YoloBot V2", "as_built": "Monolith; TA V2 current; SMC disabled in retained evidence.",
        "blocking_evidence": "Kill switch was watch-only and a carry route could execute before pause/main-risk gates; bypass-negative tests are missing.",
    },
    {
        "engine_id": "uponly-core-3", "display": "UPONLY Core / ScalpCore", "as_built": "Small event engine with a direct broker.",
        "blocking_evidence": "Exit, reconciliation, safety-stop, canonical environment, and broker-lifecycle proof are incomplete.",
    },
    {
        "engine_id": "newnaut-4", "display": "NewNaut", "as_built": "Signal brain/router with an external executor.",
        "blocking_evidence": "Legacy brain-live publication boolean is not venue authority; downstream route, lease, account, and environment do not converge.",
    },
    {
        "engine_id": "pulse-5", "display": "Pulse", "as_built": "Event engine with venue adapters and deployment configuration.",
        "blocking_evidence": "No strategy is certified and live/backtest exits diverge; replay/backtest is neither PAPER nor TESTNET proof.",
    },
    {
        "engine_id": "triad-engine", "display": "TRIAD current", "as_built": "Contract-separated candidate producer; E09 is the target money authority.",
        "blocking_evidence": "Retained head is default-OFF/not deployed/not armed; current control values, precedence, account, route, and lease proof are absent.",
    },
    {
        "engine_id": "triad-origin-v7", "display": "TRIAD ORIGIN V7", "as_built": "Target master specification and this addendum; no deployed runtime.",
        "blocking_evidence": "SAFE_HOLD / implementation not applied. Specification bytes cannot establish physical enforcement.",
    },
]
for _codebase_row in CODEBASE_INVENTORY:
    _codebase_row.update({
        "certified_venue_environment": "OFF", "certified_venue_activation": "OFF",
        "certified_paper_activation": "OFF", "required_shadow_activation": "LIVE",
        "enforcement": "NOT PROVEN",
    })

LIVE_FINDINGS = [
    ("MCP transport", "2025-06-18 streamable HTTP; uo-databank 1.28.0; 85 tools", "Read-only header token worked; operator query token was not used."),
    ("Route registry", "active_execution_source=newnaut; Binance=triad; HL=triad; paper=newnaut", "Conflicting global, per-venue, and source identities."),
    ("NewNaut runtime", "Upstream and Redis fresh", "Paper decisions 00:51Z; reasoning/admit stream 00:11Z."),
    ("Relay ingestion", "newnaut_v2 last seen 22:48Z", "More than two hours behind fresh upstream during the audit."),
    ("Money state", "0 open orders; 0 current positions", "Inactivity is not proof of OFF."),
    ("Latest venue fills", "HL 2026-08-05T19:27:00.630Z; Binance 2026-07-06T15:35:41.684Z", "No current money-plane activity during the audit window."),
    ("Historical Binance NewNaut-v2", "1,926 fills: 1,231 maker; 695 taker", "Historical behavior violates a universal maker-only claim; this is separate from lever normalization."),
    ("Hyperliquid attribution", "87,857 fills; engine null; maker state unknown", "Cannot attribute behavior to an engine or prove maker law."),
    ("Recent opened label", "Reasoning event only", "Payload also carried marketable_limit, post_only=false, LIMIT_GTX, internal shadow, and live_gate=true; not a venue fill."),
    ("TESTNET evidence", "No exposed environment or testnet configuration", "TESTNET reachability and TESTNET OFF are unverified."),
    ("Coverage failures", "stream summary and unified positions timed out", "Execution/risk factors returned empty arrays; two config APIs disagreed on STAGE1_LIVE."),
]

SUPERSESSIONS = [
    ("ADR-005", "Forbids testnet and declares LIVE-only production", "Superseded: venue_environment is LIVE|TESTNET|OFF. PAPER is a distinct demo plane; SHADOW is the mandatory rejected-candidate plane; neither is TESTNET."),
    ("DEP-010 / CHK-0310 / SCP-0310 / V-SCP-0310", "Retire testnet with paper/dry-run", "Retire aliases; retain a physically isolated canonical TESTNET path."),
    ("GAP-006 / V-GAP-006", "Reject testnet globally", "Reject only environment mismatch or mixed bundle; certify LIVE and TESTNET separately."),
    ("SEC-015 / CHK-0216 / SCP-0216 / V-SCP-0216", "LIVE-only canary/account cell", "Require exact environment-account-route-credential binding for LIVE and TESTNET."),
    ("F20", "activation_mode selects CANARY or PRODUCTION budget", "Remove branch; pass one already selected signed risk-budget policy. Rollout metadata cannot reach sizing."),
    ("C-027 activation_manifest.v1", "Mode not closed", "Replace with engine_control_manifest.v2 and exact enums."),
    ("RC2 receipt schemas", "environment/modes accept arbitrary strings", "Replace with strict v2 schemas and semantic combination validation."),
    ("W06 and G5", "connected-dark / prospective-dark terminology", "Use explicit venue_environment/venue_activation, PAPER activation, and fixed SHADOW activation LIVE."),
    ("PAR-170 / FPB-0078", "OFI_NORMALIZED_VARIANT_ENABLED=false", "Rename to OFI_NORMALIZED_VARIANT_ACTIVATION=OFF; preserve its separate ratification state."),
    ("MCP *_family_enabled booleans", "true/false and dark/live tool exposure", "Historical raw evidence only; target family activation accepts LIVE|OFF."),
]

CONTRACTS = [
    ("engine_control_manifest.v2", "Governance/configuration", "engine_id, exact scope, venue_environment, venue_activation, paper_activation, fixed shadow_activation, one complete activations map, registry/build/config/contract/parameter/strategy/adapter digests, venue/account/route/credential-fingerprint binding, producer epoch, issued/expires clocks, conditional TESTNET promotion receipt, signatures"),
    ("runtime_lever_registry.v1", "Configuration", "Every engine/component/feature lever ID, allowed enum, owner, dependencies, fail-safe OFF, legacy source mapping, removal revision"),
    ("runtime_lever_attestation.v1", "Each runtime instance", "Accepted manifest digest/revision, venue_environment, venue/paper activation, fixed shadow activation, process/build identity, route/account proof, lease epoch, health/freshness"),
    ("shadow_trade.v1", "Rejection / non-execution router and shadow recorder", "tradeable hypothesis frozen before disposition; origin_disposition REJECTED|ACCEPTED_NOT_EXECUTED|PROVEN_NO_VENUE_EFFECT; rejection stage/reason when applicable; population=SHADOW; activation=LIVE; causal market watermark; proposed geometry; fixed evaluation notional; simulator/resolver and cost-model versions; timestamps; partial/no-fill and terminal outcome"),
    ("shadow_rejection_audit.v1", "Candidate/data guards", "attempt identity, raw source evidence, named validation failure, SHADOW_UNTRADEABLE marker; never fabricates entry/stop/target"),
    ("paper_trade.v1", "PAPER demo executor", "accepted candidate, population=PAPER, activation revision, virtual account/balance/order/fill/position/outcome lineage, live-market watermark; no venue identity"),
    ("shadow_health.v1", "Shadow writer/resolver", "writer heartbeat, rejection persist latency, backlog watermark, resolver lag, dedupe/collision counts, coverage and contamination"),
    ("execution_authorization.v3", "E08", "Exact venue_environment, venue_activation revision, scope, lease epoch, account/route binding, risk reservation, expiry"),
    ("execution_cmd.v2", "E09", "Exact venue_environment, venue_activation revision, command identity, route/account binding, exposure effect, exit-only exception evidence"),
    ("fill.v3", "E09", "Exact TESTNET or LIVE population/environment, engine/candidate/decision/auth/order lineage, symbol, side, role, fees, liquidity, venue identity and timestamps"),
]


def make_tasks() -> list[dict[str, str]]:
    groups: list[tuple[str, str, str, list[str]]] = [
        ("L0", "Governance", "Owner / Architecture", [
            "Issue a signed ADR superseding ADR-005 and ratifying the two exact lever enums.",
            "Ratify SHADOW as the always-LIVE rejected-candidate recorder with no user-facing OFF control.",
            "Ratify PAPER as a separate demo-account plane with activation LIVE|OFF and zero venue authority.",
            "Freeze field names venue_environment, venue_activation, paper_activation, and shadow_activation; prohibit generic mode in authority contracts.",
            "Ratify the ten valid venue/PAPER combinations and reject venue_environment OFF with venue_activation LIVE.",
            "Ratify the direct LIVE↔TESTNET transition prohibition and mandatory drain boundary.",
            "Require a successful digest-bound TESTNET promotion receipt before any first or changed-build LIVE activation; PAPER cannot satisfy this prerequisite.",
            "Ratify exact freshness, lease, shadow-persistence, and transition timing constants in this addendum.",
            "Assign one accountable owner and independent approver for every non-OFF environment change.",
            "Authorize any qualified operator to set venue_activation or paper_activation OFF immediately without a second approval.",
            "Register every refusal code and bind it to alert, incident, and receipt semantics.",
            "Record RC4 precedence over conflicting effective RC1/RC2/RC3 rows while preserving their audit bytes.",
        ]),
        ("L1", "As-built census", "SRE / Security / Engine owners", [
            "Capture a fresh 85-tool MCP inventory with deployed server identity and sanitized auth class.",
            "Reconcile registry, payload, relay, config, service, order, position, fill, and repository engine identities.",
            "Inventory every venue_environment, venue_activation, paper_activation, and shadow_activation source in env/config/Redis/SQL/CLI/UI/supervisor/container/code defaults.",
            "Inventory every direct broker, relay, executor, adapter, and bypass route from each engine to each venue.",
            "Inventory LIVE and TESTNET endpoints and prove the opposite environment is unreachable per runtime instance.",
            "Fingerprint every credential without exposing its secret and bind it to one account and one environment.",
            "Inventory producer leases, money-selection leases, writer epochs, consumers, ACLs, and stale-writer rejection.",
            "Census current regular orders, algo/protection orders, positions, reservations, sessions, and private-stream freshness.",
            "Inventory SHADOW rejection, PAPER demo, TESTNET venue, and LIVE venue writers/readers/ledgers end to end.",
            "Map legacy values to raw_legacy_value only; do not assign a canonical non-OFF value by inference.",
            "Prove whether TESTNET exists as a real venue environment and separately inventory PAPER as a keyless demo-account executor.",
            "Explain why NewNaut upstream is fresh while relay ingestion is more than two hours stale.",
            "Resolve newnaut versus newnaut_v2 identity and version ownership.",
            "Resolve TRIAD money-route selection versus TRIAD shadow registration and missing health probe.",
            "Resolve Yolonaut backend selection versus registry absence and June relay staleness.",
            "Resolve STAGE1_LIVE/STAGE1_SHADOW simultaneity and disagreement between exact config APIs.",
            "Bound or index get_stream_summary and get_positions_unified so read-only audits finish inside 30 seconds.",
            "Expose non-empty execution and risk configuration or return a named unavailable state with the missing source.",
        ]),
        ("L2", "Contracts and schemas", "Architecture / Contracts", [
            "Publish engine_control_manifest.v2 with uppercase closed enums, no aliases, no defaults, and no coercion.",
            "Publish runtime_lever_registry.v1 with one unique row for every engine, component, and feature lever.",
            "Publish runtime_lever_attestation.v1 with manifest, runtime, environment, account, route, and lease proof.",
            "Publish shadow_trade.v1 and shadow_rejection_audit.v1 with immutable population=SHADOW and activation=LIVE.",
            "Publish paper_trade.v1 with immutable population=PAPER, activation LIVE|OFF, and physical denial of venue authority.",
            "Publish shadow_health.v1 with exact persistence, heartbeat, backlog, lineage, and contamination metrics.",
            "Publish strict v2 evidence, task, and gate receipt schemas; remove free-form environment and modes arrays.",
            "Add population plus venue_environment/venue_activation to venue contracts and paper_activation to PAPER contracts; preserve plane separation.",
            "Add symmetric LIVE_TESTNET_BINDING_FORBIDDEN and TESTNET_LIVE_BINDING_FORBIDDEN validation.",
            "Require one complete activations map: missing, duplicated, reserved, or unknown registered keys reject the manifest.",
            "Require venue_binding environment, venue, and account to equal the top-level environment and exact scope; reject duplicate facts that disagree.",
            "Require every LIVE promotion-receipt digest, scope, result, and expiry to equal the current signed manifest and evaluation clock.",
            "Define canonical JSON serialization and signature bytes; reject reordered semantic ambiguity and unknown fields.",
            "Remove activation_mode from F20 and bind one signed risk-budget policy input independent of rollout metadata.",
            "Replace OFI_NORMALIZED_VARIANT_ENABLED with OFI_NORMALIZED_VARIANT_ACTIVATION using LIVE|OFF.",
            "Version every breaking migration additively; dual-read/write before retiring any older contract.",
            "Create negative schema fixtures for every forbidden alias, boolean, integer, blank, null, case change, and whitespace variant.",
        ]),
        ("L3", "Control-plane plumbing", "Configuration / SRE", [
            "Build one signed append-only canonical lever register with monotonic revision and compare-and-swap writes.",
            "Distribute manifests over one authenticated, replay-protected control edge with immutable delivery receipts.",
            "Require every runtime to refuse money authority until it accepts and attests the exact current revision.",
            "Cache lever state for at most 2,000 ms and resolve venue_activation/paper_activation OFF on missing, stale, malformed, or conflicting state.",
            "Poll at 1,000 ms as a fallback while preserving event-driven delivery.",
            "Implement 5,000 ms lease renewal and 15,000 ms TTL with monotonically increasing fencing epochs.",
            "Reject every stale epoch at the consumer and E09 command seam, not only at the producer.",
            "Emit runtime attestation every 5,000 ms and reject authority after 15,000 ms without a current attestation.",
            "Block new venue exposure within 2,000 ms of an accepted venue_activation OFF revision.",
            "Persist an immutable 15-minute post-change side-effect census after every lever change.",
            "Preserve venue_activation and paper_activation OFF across supervisor restart; no legacy variable may re-enable a path.",
            "Require exact venue/account/capsule/symbol/side scope in every engine manifest; represent estate-wide OFF in a separate signed denial layer that expands deterministically to exact scopes, never with a wildcard manifest.",
            "Make MCP a read-only projection of raw and canonical evidence; it must not write the lever register.",
        ]),
        ("L4", "Four-plane routing", "ORIGIN / E07 / E10 / Data", [
            "Validate every edge_candidate.v2 for shadow-tradeability, then classify each valid hypothesis exactly once as ACCEPTED or REJECTED with stage and named reason.",
            "Route every shadow-tradeable REJECTED candidate into the SHADOW trade outbox regardless of venue_environment, venue_activation, or paper_activation.",
            "Consume rejection dispositions from E07 policy, E08 risk/capacity, and pre-submit E09 eligibility; each complete rejection routes to SHADOW exactly once.",
            "Set SHADOW population exactly SHADOW and shadow_activation exactly LIVE as immutable contract constants.",
            "Reject any configuration or UI request attempting to set shadow_activation OFF.",
            "Persist each rejected candidate within 100 ms before acknowledging the rejection decision.",
            "Define shadow-tradeability as a schema-valid and semantically valid hypothesis with resolved instrument, side, entry policy, invalidation, target or terminal rule, horizon, finite numbers, monotonic clocks, identity, and causal market watermark.",
            "For any event or candidate that fails shadow-tradeability, persist shadow_rejection_audit.v1 with SHADOW_UNTRADEABLE instead of fabricating geometry.",
            "Derive stable shadow_trade_id from candidate identity, rejection revision, simulator/resolver version, and trial revision.",
            "Dedupe at-least-once delivery and refuse identity collisions with unequal payload hashes.",
            "Keep SHADOW keyless and physically unable to publish an E09 venue command.",
            "Freeze symbol, side, entry policy, invalidation, target, horizon, proposed size, rejection stage, and causal market watermark before the rejection result; reject every post-rejection mutation.",
            "Run SHADOW against the same immutable event tape using versioned latency, fee, funding, slippage, partial-fill, and no-fill rules; when a venue fact is unavailable use a declared conservative bound rather than zero.",
            "Publish SHADOW performance in bps and R-multiple on one fixed evaluation notional; retain proposed size separately and never let rejected oversizing distort alpha comparison.",
            "Resolve SHADOW only from events available after its frozen causal watermark; prohibit future-candle access, retroactive entry improvement, and outcome-dependent parameter selection.",
            "Represent a simulated no-fill as NO_FILL; never delete a rejection or fabricate a fill.",
            "When paper_activation is LIVE, route every ACCEPTED candidate to the PAPER demo executor and its virtual account ledger.",
            "Keep PAPER keyless and physically unable to reach LIVE or TESTNET venue adapters.",
            "When venue_activation is LIVE, route ACCEPTED candidates to exactly one venue_environment: TESTNET or LIVE.",
            "When an ACCEPTED candidate reaches neither PAPER nor venue, create a SHADOW ACCEPTED_NOT_EXECUTED record so the opportunity is still measured.",
            "When an E09 submit result is unknown, reconcile venue effects first; only a proven no-effect disposition may create a SHADOW fallback trade.",
            "Allow an ACCEPTED candidate to have a PAPER copy and one venue copy, using distinct population IDs under one candidate lineage.",
            "Use the same immutable market-event ledger and causal stamps across SHADOW, PAPER, TESTNET, and LIVE.",
            "Keep all four populations in separate contracts/tables and never merge performance denominators.",
            "Emit SHADOW writer heartbeat every 1,000 ms and force venue_activation and paper_activation OFF after 5,000 ms stale.",
            "Keep SHADOW resolver processable backlog under 60,000 ms and publish pending horizons honestly.",
            "Backfill SHADOW/PAPER only from immutable events with exact versions; never rewrite prior facts.",
            "Reconcile 100% of rejected inputs to either a SHADOW tradeable hypothesis or an explicit SHADOW_UNTRADEABLE audit before any non-OFF execution activation.",
            "Alert on any SHADOW or PAPER row carrying a venue fill identity and on any cross-population aggregation.",
        ]),
        ("L5", "Authority enforcement", "E07 / E08 / E09", [
            "At E07, route policy rejection to SHADOW; admit execution only when the selected PAPER/venue controls and evidence are valid.",
            "At E08, route risk/capacity denial of a complete candidate to SHADOW before returning the denial receipt.",
            "At E08, reject venue sizing/reservation unless venue_environment, venue_activation revision, policy, account, and lease match exactly.",
            "At E09, re-evaluate the current manifest immediately before every venue send.",
            "At E09, route a proven pre-submit eligibility rejection to SHADOW; never route an unknown-submit outcome until reconciliation proves no venue effect.",
            "Persist an unknown-submit reconciliation record, keep venue_activation OFF for new exposure, query regular orders, algo orders, fills, positions, and idempotency keys, and use PROVEN_NO_VENUE_EFFECT only after every authoritative surface agrees.",
            "If a venue effect appears after PROVEN_NO_VENUE_EFFECT, quarantine the SHADOW outcome, preserve both immutable facts, correct population metrics, and raise a P0 lineage incident.",
            "Bind each LIVE runtime to LIVE endpoints/accounts/credentials only and prove TESTNET is unreachable.",
            "Bind each TESTNET runtime to TESTNET endpoints/accounts/credentials only and prove LIVE is unreachable.",
            "Refuse a whole mixed-environment bundle; never drop only the offending member.",
            "Require one fenced producer per overlapping engine/capsule/symbol/side/account scope.",
            "Reject stale authorization, command, route, lease, or private-state revisions.",
            "With venue_activation OFF, permit cancel, reconciliation, protection, and verified exposure reduction only.",
            "Keep the approved emergency taker exception exit-only, exposure-reducing, capped, and immutably audited.",
            "Forbid a direct LIVE↔TESTNET switch; venue_activation OFF, flatness, lease/session revocation, isolation, and venue_environment OFF must intervene.",
            "Reject LIVE activation unless the same build, contracts, strategy, exact scope, and E09 adapter lifecycle have a current successful TESTNET promotion receipt.",
            "At a 300,000 ms drain timeout remain in the old venue_environment with venue_activation OFF; do not force credential removal while exposure remains.",
            "Make fill.v3 and every TESTNET/LIVE venue fact carry exact population/environment and complete engine lineage.",
            "Eliminate all direct broker bypasses that do not consume the current manifest and fencing epoch.",
            "Prove OFF through negative side-effect tests, not by absence of current orders or positions.",
        ]),
        ("L6", "Read faces and UI", "MCP / Operations / UI", [
            "Add get_engine_lever_registry returning raw source plus canonical venue_environment, venue_activation, paper_activation, shadow_activation, proof, revision, and freshness.",
            "Add get_engine_lever_attestation returning process readback, hashes, account/route environment, leases, and mismatches.",
            "Add get_engine_lever_history returning immutable transitions and side-effect census references.",
            "Add get_shadow_health returning fixed activation LIVE, rejection coverage, persist latency, backlog, resolver health, and contamination.",
            "Add get_four_plane_status returning separate SHADOW, PAPER, TESTNET, and LIVE counts, freshness, outcomes, and authority evidence.",
            "Add get_engine_inventory_reconciliation joining registry, payload, relay, config, service, fill, and repository identities.",
            "Return raw legacy values only under raw_legacy_value; never silently translate them to LIVE or TESTNET.",
            "Render only LIVE, TESTNET, OFF in the environment selector and only LIVE, OFF in activation selectors.",
            "Render SHADOW as the always-LIVE rejected-trade population, PAPER as demo, and TESTNET/LIVE as the venue promotion chain; expose health separately.",
            "Reject free text, lowercase input, whitespace, booleans, integers, blanks, nulls, and aliases at client and server.",
            "Display requested and effective values plus proof status; never claim effect enforcement from configuration alone.",
            "Rename tool-family enabled booleans to activation keys and preserve old keys read-only during migration.",
            "Make every read bounded, paginated, and snapshot-timestamped; named unavailable is preferable to timeout or empty arrays.",
            "Remove tokens and credential material from reports; rotate the credentials supplied for this audit after use.",
        ]),
        ("L7", "Migration and cutover", "Release / Engine owners", [
            "Freeze legacy lever changes except emergency OFF while the census and adapters are built.",
            "Snapshot every legacy source, precedence rule, default, restart behavior, and side effect before migration.",
            "Deploy read-only adapters that compare legacy observations to canonical projections without granting authority.",
            "Run dual-read comparison until every engine/component/feature agrees for seven continuous days and through one restart drill.",
            "Migrate real testnet paths to TESTNET, demo-account simulation to PAPER, rejected-candidate simulation to SHADOW, and replay/backtest to offline evidence metadata.",
            "Migrate enabled/on/true and disabled/off/false keys to activation LIVE/OFF without runtime coercion.",
            "Replace connected-dark with explicit venue_environment, venue_activation OFF, optional paper_activation, and fixed shadow_activation LIVE.",
            "Update supervisors, container manifests, config store, UI, contracts, runbooks, alerts, and MCP projections atomically per engine.",
            "Exercise LIVE→OFF-drain→TESTNET and TESTNET→OFF-drain→LIVE on isolated accounts with zero cross-environment effects.",
            "Remove legacy readers and writers only after canonical receipts, restart persistence, and negative bypass tests pass.",
            "Rotate all audit credentials and prove no token, query string, header, hash, or secret entered the artifacts.",
            "Issue a final as-built inventory, current lever register, attestation set, side-effect census, and rollback receipt.",
        ]),
    ]
    tasks: list[dict[str, str]] = []
    previous_gate_tail = ""
    counter = 1
    for gate, domain, owner, instructions in groups:
        gate_first = ""
        prior = previous_gate_tail
        for instruction in instructions:
            task_id = f"LEV-{counter:04d}"
            if not gate_first:
                gate_first = task_id
            tasks.append({
                "id": task_id,
                "gate": gate,
                "domain": domain,
                "owner": owner,
                "instruction": instruction,
                "depends_on": prior or "OWNER-DIRECTIVE-2026-08-09",
                "acceptance": "Exact implemented bytes/config and a falsifiable test demonstrate this instruction for every registered engine and scope; no open P0/P1 mismatch remains.",
                "evidence": "Signed immutable receipt with build/config/contract/registry digests, UTC, exact scope, test IDs, reviewer, and rollback reference.",
                "stop_rule": "Keep venue_activation and paper_activation OFF for the affected scope; preserve shadow_activation LIVE and preserve venue exit/reconciliation authority for existing exposure.",
            })
            prior = task_id
            counter += 1
        previous_gate_tail = prior
    return tasks


def make_verifications() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    counter = 1

    def add(area: str, fixture: str, expected: str, refusal: str = "") -> None:
        nonlocal counter
        rows.append({"id": f"LEV-V-{counter:04d}", "area": area, "fixture": fixture, "expected": expected, "refusal": refusal})
        counter += 1

    for combo in VALID_COMBINATIONS:
        add("Truth table", f'venue_environment={combo["venue_environment"]}; venue_activation={combo["venue_activation"]}; paper_activation={combo["paper_activation"]}', "Accept only with required plane-specific proofs; shadow_activation remains LIVE.")
    add("Truth table", "venue_environment=OFF; venue_activation=LIVE", "Reject; effective venue pair OFF/OFF; shadow remains LIVE.", "OFF_WITH_LIVE_VENUE_ACTIVATION")
    for alias in INVALID_ALIASES:
        shown = "<empty>" if alias == "" else alias
        add("Alias rejection", f"canonical slot receives {shown!r}", "Reject without trimming, case conversion, aliasing, boolean/integer coercion, or default.", "LEGACY_LEVER_ALIAS_FORBIDDEN")
    for field, typed_value in [
        ("venue_environment", "JSON true"), ("venue_environment", "JSON 1"), ("venue_environment", "JSON null"),
        ("venue_activation", "JSON false"), ("venue_activation", "JSON 0"), ("venue_activation", "JSON null"),
        ("paper_activation", "JSON true"), ("paper_activation", "JSON 1"), ("paper_activation", "JSON null"),
    ]:
        add("Typed rejection", f"{field} receives {typed_value}", "Reject the document before semantic evaluation; do not stringify or coerce.", "LEGACY_LEVER_ALIAS_FORBIDDEN")
    for field, spaced_value in [
        ("venue_environment", "' LIVE'"), ("venue_environment", "'LIVE '"),
        ("venue_activation", "'\\tLIVE'"), ("paper_activation", "'OFF\\n'"),
    ]:
        add("Whitespace rejection", f"{field} receives {spaced_value}", "Reject exact bytes; do not trim.", "LEGACY_LEVER_ALIAS_FORBIDDEN")
    add("Field enum", "venue_activation receives 'TESTNET'", "Reject; TESTNET is legal only in venue_environment.", "VENUE_ACTIVATION_VALUE_INVALID")
    add("Field enum", "paper_activation receives 'TESTNET'", "Reject; PAPER activation accepts only LIVE or OFF.", "PAPER_ACTIVATION_VALUE_INVALID")
    add("Field enum", "venue_environment receives 'SHADOW'", "Reject; SHADOW is a population, not a venue environment value.", "VENUE_ENVIRONMENT_VALUE_INVALID")
    add("Field enum", "venue_environment receives 'PAPER'", "Reject; PAPER is a population, not a venue environment value.", "VENUE_ENVIRONMENT_VALUE_INVALID")
    add("Activation map", "activations contains reserved key venue_activation", "Reject the manifest; canonical top-level controls cannot be shadowed.", "LEVER_REGISTRY_INCOMPLETE")
    add("Activation map", "activations contains an unregistered feature key", "Reject the manifest; unknown activation keys are forbidden.", "LEVER_REGISTRY_INCOMPLETE")
    add("Activation map", "activations omits one required registry key", "Reject the manifest; every registered activation appears exactly once.", "LEVER_REGISTRY_INCOMPLETE")
    add("Activation map", "raw JSON repeats the same activation property name", "Reject during duplicate-key parsing before signature verification.", "LEVER_REGISTRY_INCOMPLETE")
    add("Activation map", "one activation value is TESTNET", "Reject; every component/feature activation accepts only LIVE or OFF.", "ACTIVATION_VALUE_INVALID")
    add("Scope", "LIVE manifest uses symbol='*'", "Reject; every engine manifest scope is exact.", "SCOPE_VALUE_INVALID")
    add("Scope", "OFF manifest uses account_ref='*'", "Reject; wildcard engine manifests are forbidden even for OFF.", "SCOPE_VALUE_INVALID")
    add("Scope", "Estate-wide OFF denial expands to the complete current exact-scope registry", "Accept the denial layer only when expansion is deterministic, signed, revision-bound, and contains no wildcard engine manifest.")
    add("Transition", "LIVE→TESTNET direct", "Reject; remain LIVE/OFF after activation is removed until flat and isolated.", "DIRECT_ENVIRONMENT_TRANSITION_FORBIDDEN")
    add("Transition", "TESTNET→LIVE direct", "Reject; remain TESTNET/OFF after activation is removed until flat and isolated.", "DIRECT_ENVIRONMENT_TRANSITION_FORBIDDEN")
    add("Promotion", "LIVE activation has PAPER results but no successful same-digest TESTNET receipt", "Reject LIVE; PAPER cannot substitute for TESTNET.", "LIVE_PROMOTION_RECEIPT_MISSING")
    add("Promotion", "LIVE activation follows TESTNET on an older build or different scope", "Reject LIVE until the current build, contracts, strategy, scope, and adapter lifecycle pass TESTNET.", "LIVE_PROMOTION_RECEIPT_MISSING")
    add("Transition", "LIVE/LIVE→LIVE/OFF with open position", "Block new exposure; preserve exits, protection, cancel, and reconciliation.")
    add("Transition", "LIVE/OFF→OFF/OFF while one protection/order/position remains", "Reject OFF environment and continue drain.", "OFF_TRANSITION_EXPOSURE_REMAINS")
    add("Isolation", "LIVE manifest contains one TESTNET credential", "Reject the whole bundle.", "LIVE_TESTNET_BINDING_FORBIDDEN")
    add("Isolation", "TESTNET manifest contains one LIVE endpoint", "Reject the whole bundle.", "TESTNET_LIVE_BINDING_FORBIDDEN")
    add("Isolation", "One evidence/authority bundle contains both LIVE and TESTNET orders, fills, accounts, or routes", "Reject the whole bundle; do not retain a supposedly safe subset.", "MIXED_ENVIRONMENT_BUNDLE_FORBIDDEN")
    add("Isolation", "One instance can route to both environment families", "Reject non-OFF activation.", "OPPOSITE_ENVIRONMENT_REACHABLE")
    add("Binding", "venue_environment=LIVE while venue_binding.environment=TESTNET", "Reject the manifest before authority.", "VENUE_BINDING_MISMATCH")
    add("Binding", "scope.account_ref differs from venue_binding.account_ref", "Reject the manifest before authority.", "VENUE_BINDING_MISMATCH")
    add("Binding", "scope.venue_id differs from venue_binding.venue_id", "Reject the manifest before authority.", "VENUE_BINDING_MISMATCH")
    add("Promotion", "TESTNET receipt build digest differs from the current manifest", "Reject LIVE activation.", "LIVE_PROMOTION_RECEIPT_MISSING")
    add("Promotion", "TESTNET receipt scope, config, contracts, parameters, strategy, or adapter digest differs from the current manifest", "Reject LIVE activation.", "LIVE_PROMOTION_RECEIPT_MISSING")
    add("Promotion", "TESTNET receipt is expired at evaluation time", "Reject LIVE activation.", "LIVE_PROMOTION_RECEIPT_MISSING")
    add("Lease", "Two engines hold overlapping producer scope", "Reject both affected non-OFF claims until one fenced owner remains.", "PRODUCER_LEASE_CONFLICT")
    add("Lease", "Non-OFF execution scope has no current fenced producer lease", "Reject PAPER/venue authority for the affected scope.", "PRODUCER_LEASE_MISSING")
    add("Lease", "Command carries expired fencing epoch", "E09 rejects before venue send.", "LEVER_REVISION_STALE")
    add("Freshness", "Private order/position state is 5,001 ms old", "Reject new exposure; reconciliation continues.", "PRIVATE_STATE_STALE")
    add("Freshness", "Runtime attestation is 15,001 ms old", "Resolve venue_activation and paper_activation OFF.", "RUNTIME_LEVER_ATTESTATION_MISMATCH")
    add("Shadow", "Attempt shadow activation OFF", "Reject configuration; shadow desired activation remains LIVE.", "SHADOW_CAPTURE_OFF_FORBIDDEN")
    add("Shadow", "Shadow-tradeable REJECTED candidate has no durable SHADOW trade at 101 ms", "Reject disposition acknowledgement and force PAPER/venue activation OFF for the scope.", "SHADOW_REJECTION_NOT_PERSISTED")
    add("Shadow", "Pre-candidate event lacks valid side/entry/invalidation", "Persist SHADOW_UNTRADEABLE audit; do not simulate or fabricate a trade.", "SHADOW_UNTRADEABLE")
    add("Shadow", "Structurally complete candidate contains NaN price, unresolved instrument, or non-monotonic causal timestamps", "Persist SHADOW_UNTRADEABLE audit; do not send it to the simulator.", "SHADOW_UNTRADEABLE")
    add("Shadow", "venue_environment OFF with shadow-tradeable REJECTED candidate", "Persist and resolve SHADOW trade; no venue command exists.")
    add("Shadow", "venue_environment TESTNET with shadow-tradeable REJECTED candidate", "Persist SHADOW only; rejection does not reach TESTNET.")
    add("Shadow", "venue_environment LIVE with shadow-tradeable REJECTED candidate", "Persist SHADOW only; rejection does not reach LIVE.")
    add("Shadow", "Shadow row contains venue fill ID", "Quarantine row and fail contamination gate.", "SHADOW_MONEY_CONTAMINATION")
    add("Shadow", "Writer heartbeat age 5,001 ms", "venue_activation and paper_activation resolve OFF; SHADOW recovery remains requested LIVE.", "SHADOW_HEALTH_STALE")
    add("Shadow", "Processable resolver watermark is 60,001 ms behind the immutable event tape", "venue_activation and paper_activation resolve OFF; pending future horizons are excluded from this freshness calculation.", "SHADOW_HEALTH_STALE")
    add("Shadow", "Duplicate delivery with same ID and same hash", "Idempotent no-op; one row remains.")
    add("Shadow", "Duplicate ID with unequal hash", "Quarantine both and raise collision incident.", "SHADOW_LINEAGE_INCOMPLETE")
    add("Shadow", "Rejected candidate geometry changes after the frozen rejection watermark", "Reject the mutation; retain the original shadow hypothesis and raise a lineage incident.", "SHADOW_LINEAGE_INCOMPLETE")
    add("Shadow", "Resolver reads a candle or book update timestamped after the evaluated decision point before simulating entry", "Reject the outcome as future-data contamination.", "SHADOW_LINEAGE_INCOMPLETE")
    add("Shadow", "Replay the same candidate, event tape, simulator version, and cost model twice", "Produce byte-identical fill/no-fill and terminal outcome facts.")
    add("Shadow", "Fee, funding, latency, or slippage fact is unavailable", "Use the signed conservative bound and mark the fact estimated; never default the cost to zero.")
    add("Shadow", "Risk rejection was caused by oversized proposed quantity", "Keep proposed quantity as evidence; compute comparable bps and R-multiple on the fixed evaluation notional.")
    add("Paper", "paper_activation=LIVE with accepted candidate", "Create PAPER demo order/fill/position/outcome using virtual balance and live market data; no venue effect.")
    add("Paper", "PAPER command reaches any venue adapter", "Reject and raise P0 isolation incident.", "PAPER_VENUE_EFFECT_FORBIDDEN")
    add("Paper", "PAPER PnL aggregated with LIVE PnL", "Reject the query/publication.", "PAPER_LEDGER_CONTAMINATION")
    add("Routing", "Accepted candidate; paper_activation=OFF; venue_activation=OFF", "Persist SHADOW ACCEPTED_NOT_EXECUTED record.", "ACCEPTED_CANDIDATE_UNRECORDED")
    add("Routing", "Venue submit result is unknown and private order/fill/position truth has not converged", "Do not create a SHADOW fallback; keep new venue exposure OFF and reconcile.", "UNKNOWN_SUBMIT_UNRECONCILED")
    add("Routing", "Unknown submit is absent from regular orders, algo orders, fills, positions, and the venue idempotency index after authoritative convergence", "Create one SHADOW trade with origin_disposition PROVEN_NO_VENUE_EFFECT and attach the reconciliation receipt.")
    add("Routing", "Venue fill appears after a PROVEN_NO_VENUE_EFFECT SHADOW outcome", "Quarantine the SHADOW outcome from performance, preserve both facts, repair metrics, and raise P0.", "SHADOW_MONEY_CONTAMINATION")
    add("Routing", "Accepted candidate; PAPER LIVE; TESTNET LIVE", "Create one PAPER copy and one TESTNET copy under distinct population IDs; no LIVE copy.")
    add("Routing", "Accepted candidate; PAPER LIVE; LIVE LIVE", "Create one PAPER copy and one LIVE copy under distinct population IDs; no TESTNET copy.")
    add("Restart", "Supervisor retains legacy enabled=true but canonical activation=OFF", "Activation remains OFF after restart; legacy source cannot promote.")
    add("F20", "Change rollout metadata with identical signed budget and inputs", "Quantity bytes remain identical; rollout metadata is absent from formula dependencies.")
    add("MCP", "Raw BREAKOUT_MODE=live", "Return as raw_legacy_value only; canonical venue_environment/venue_activation remains OFF without proof.")
    add("MCP", "No testnet/environment key", "Return unavailable proof; do not infer TESTNET OFF or LIVE.", "VENUE_ENVIRONMENT_UNVERIFIED")
    add("MCP", "No orders and no positions", "Do not infer OFF; report side-effect census only.")
    add("MCP", "Fresh paper stream and stale relay", "Return both timestamps and mismatch; no single green liveness claim.")
    add("Security", "Generated artifact scanned for JWT/bearer/query token", "Zero credential patterns or supplied token fragments.")
    return rows


TASKS = make_tasks()
VERIFICATIONS = make_verifications()


def task_table() -> str:
    rows = []
    for task in TASKS:
        search = esc(" ".join(task.values()).lower())
        rows.append(
            f'<tr data-search="{search}" data-gate="{esc(task["gate"])}" data-domain="{esc(task["domain"])}">'
            f'<td><code>{esc(task["id"])}</code><br>{chip(task["gate"], "blue")}</td>'
            f'<td>{esc(task["domain"])}<br><span class="muted">{esc(task["owner"])}</span></td>'
            f'<td><strong>{esc(task["instruction"])}</strong><details><summary>Dependencies, evidence, and stop rule</summary>'
            f'<dl><dt>Depends on</dt><dd>{esc(task["depends_on"])}</dd><dt>Acceptance</dt><dd>{esc(task["acceptance"])}</dd>'
            f'<dt>Evidence</dt><dd>{esc(task["evidence"])}</dd><dt>Stop rule</dt><dd>{esc(task["stop_rule"])}</dd></dl></details></td></tr>'
        )
    return filter_toolbar("tasks", len(TASKS), ["gate", "domain"]) + (
        '<div class="table-wrap registry"><table id="tasks"><thead><tr><th>ID / gate</th><th>Domain / owner</th><th>Atomic instruction</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )


def verification_table() -> str:
    rows = []
    for row in VERIFICATIONS:
        search = esc(" ".join(row.values()).lower())
        rows.append(
            f'<tr data-search="{search}" data-area="{esc(row["area"])}"><td><code>{esc(row["id"])}</code></td>'
            f'<td>{esc(row["area"])}</td><td>{esc(row["fixture"])}</td><td>{esc(row["expected"])}</td>'
            f'<td><code>{esc(row["refusal"] or "—")}</code></td></tr>'
        )
    return filter_toolbar("verifications", len(VERIFICATIONS), ["area"]) + (
        '<div class="table-wrap registry"><table id="verifications"><thead><tr><th>ID</th><th>Area</th><th>Fixture</th><th>Expected</th><th>Refusal</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )


def build() -> None:
    topology_data = base64.b64encode(TOPOLOGY.read_bytes()).decode("ascii")
    rc3_digest = sha256(RC3)
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://triad.internal/contracts/engine-control-manifest.v2.schema.json",
        "type": "object",
        "required": [
            "schema", "engine_id", "scope", "venue_environment", "venue_activation", "paper_activation", "shadow_activation", "paper", "shadow",
            "activations", "venue_binding", "revision", "producer_epoch", "digests",
            "issued_at_utc", "expires_at_utc", "signatures",
        ],
        "properties": {
            "schema": {"const": "engine_control_manifest.v2"},
            "engine_id": {"type": "string", "minLength": 1},
            "scope": {
                "type": "object",
                "required": ["venue_id", "account_ref", "capsule_id", "symbol", "side"],
                "additionalProperties": False,
                "properties": {
                    "venue_id": {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$"},
                    "account_ref": {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$"},
                    "capsule_id": {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$"},
                    "symbol": {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$"},
                    "side": {"enum": ["LONG", "SHORT"]},
                },
            },
            "venue_environment": {"enum": ["LIVE", "TESTNET", "OFF"]},
            "venue_activation": {"enum": ["LIVE", "OFF"]},
            "paper_activation": {"enum": ["LIVE", "OFF"]},
            "shadow_activation": {"const": "LIVE"},
            "paper": {
                "type": "object",
                "required": ["population", "demo_account_ref", "ledger_ref", "live_market_data", "venue_authority"],
                "additionalProperties": False,
                "properties": {
                    "population": {"const": "PAPER"},
                    "demo_account_ref": {"type": "string", "minLength": 1},
                    "ledger_ref": {"type": "string", "minLength": 1},
                    "live_market_data": {"const": True},
                    "venue_authority": {"const": False},
                },
            },
            "shadow": {
                "type": "object",
                "required": ["population", "recorder_id", "ledger_ref", "user_switchable", "venue_authority"],
                "additionalProperties": False,
                "properties": {
                    "population": {"const": "SHADOW"},
                    "recorder_id": {"type": "string", "minLength": 1},
                    "ledger_ref": {"type": "string", "minLength": 1},
                    "user_switchable": {"const": False},
                    "venue_authority": {"const": False},
                },
            },
            "activations": {
                "type": "object", "minProperties": 1,
                "propertyNames": {
                    "allOf": [
                        {"pattern": "^[a-z][a-z0-9_.-]{2,127}$"},
                        {"not": {"enum": ["venue_environment", "venue_activation", "paper_activation", "shadow_activation"]}},
                    ]
                },
                "additionalProperties": {"enum": ["LIVE", "OFF"]},
            },
            "venue_binding": {
                "type": "object",
                "required": ["environment", "venue_id", "account_ref", "route_bound", "credential_usable", "opposite_environment_reachable"],
                "additionalProperties": False,
                "properties": {
                    "environment": {"enum": ["LIVE", "TESTNET", "OFF"]},
                    "venue_id": {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$"},
                    "account_ref": {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$"},
                    "route_bound": {"type": "boolean"},
                    "credential_usable": {"type": "boolean"},
                    "opposite_environment_reachable": {"const": False},
                    "route_digest": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                    "endpoint_family_digest": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                    "credential_fingerprint": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                },
                "allOf": [
                    {
                        "if": {"properties": {"environment": {"const": "OFF"}}, "required": ["environment"]},
                        "then": {
                            "properties": {"route_bound": {"const": False}, "credential_usable": {"const": False}},
                            "not": {"anyOf": [{"required": ["route_digest"]}, {"required": ["endpoint_family_digest"]}, {"required": ["credential_fingerprint"]}]},
                        },
                    },
                    {
                        "if": {"properties": {"environment": {"enum": ["LIVE", "TESTNET"]}}, "required": ["environment"]},
                        "then": {
                            "required": ["route_digest", "endpoint_family_digest", "credential_fingerprint"],
                            "properties": {"route_bound": {"const": True}, "credential_usable": {"const": True}},
                        },
                    },
                ],
            },
            "revision": {"type": "integer", "minimum": 1},
            "digests": {
                "type": "object", "required": ["lever_registry", "build", "config", "contracts", "parameters", "strategy", "adapter"],
                "additionalProperties": False,
                "properties": {
                    "lever_registry": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                    "build": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                    "config": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                    "contracts": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                    "parameters": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                    "strategy": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                    "adapter": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                },
            },
            "producer_epoch": {"type": "integer", "minimum": 0},
            "issued_at_utc": {"type": "string", "format": "date-time"},
            "expires_at_utc": {"type": "string", "format": "date-time"},
            "testnet_promotion_receipt": {
                "type": "object",
                "required": ["receipt_id", "result", "scope_digest", "build_digest", "config_digest", "contracts_digest", "parameters_digest", "strategy_digest", "adapter_digest", "passed_at_utc", "expires_at_utc"],
                "additionalProperties": False,
                "properties": {
                    "receipt_id": {"type": "string", "minLength": 1},
                    "result": {"const": "PASS"},
                    "scope_digest": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                    "build_digest": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                    "config_digest": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                    "contracts_digest": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                    "parameters_digest": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                    "strategy_digest": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                    "adapter_digest": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                    "passed_at_utc": {"type": "string", "format": "date-time"},
                    "expires_at_utc": {"type": "string", "format": "date-time"},
                },
            },
            "signatures": {
                "type": "array", "minItems": 1,
                "items": {
                    "type": "object", "required": ["signer_id", "key_id", "algorithm", "signature"],
                    "additionalProperties": False,
                    "properties": {
                        "signer_id": {"type": "string", "minLength": 1},
                        "key_id": {"type": "string", "minLength": 1},
                        "algorithm": {"type": "string", "minLength": 1},
                        "signature": {"type": "string", "minLength": 16},
                    },
                },
            },
        },
        "additionalProperties": False,
        "allOf": [
            {
                "if": {"properties": {"venue_environment": {"const": "OFF"}}, "required": ["venue_environment"]},
                "then": {"properties": {"venue_activation": {"const": "OFF"}}},
            },
            {
                "if": {
                    "properties": {"venue_environment": {"const": "LIVE"}, "venue_activation": {"const": "LIVE"}},
                    "required": ["venue_environment", "venue_activation"],
                },
                "then": {"required": ["testnet_promotion_receipt"]},
            },
            {
                "if": {"properties": {"venue_environment": {"const": "LIVE"}}, "required": ["venue_environment"]},
                "then": {"properties": {"venue_binding": {"properties": {"environment": {"const": "LIVE"}}}}},
            },
            {
                "if": {"properties": {"venue_environment": {"const": "TESTNET"}}, "required": ["venue_environment"]},
                "then": {"properties": {"venue_binding": {"properties": {"environment": {"const": "TESTNET"}}}}},
            },
            {
                "if": {"properties": {"venue_environment": {"const": "OFF"}}, "required": ["venue_environment"]},
                "then": {"properties": {"venue_binding": {"properties": {"environment": {"const": "OFF"}}}}},
            }
        ],
        "semantic_rules": [
            "venue_environment OFF requires venue_activation OFF.",
            "Venue environment change LIVE↔TESTNET requires prior OFF transition receipt.",
            "LIVE activation requires a current successful same-digest TESTNET promotion receipt; PAPER never substitutes.",
            "venue_binding.environment equals venue_environment; venue_binding venue_id/account_ref equal the same fields in scope.",
            "A LIVE promotion receipt scope/build/config/contracts/parameters/strategy/adapter digest equals the current manifest material and is unexpired.",
            "PAPER is a keyless demo-account plane and cannot reach a venue effect.",
            "SHADOW records every shadow-tradeable REJECTED candidate; its activation is LIVE in every manifest.",
            "The activations map contains every registered component/feature lever exactly once, no unknown key, and no reserved control name.",
            "Every engine manifest scope is exact and wildcard-free; estate-wide OFF is a separate signed denial layer expanded to exact registered scopes.",
        ],
    }
    bundle = {
        "document": {"version": VERSION, "issued_utc": ISSUED_UTC, "status": STATUS, "supersedes_rc3_sha256": rc3_digest},
        "lever_law": {
            "venue_environment_enum": ["LIVE", "TESTNET", "OFF"],
            "activation_enum": ["LIVE", "OFF"],
            "case_sensitive": True,
            "trim_input": False,
            "aliases": False,
            "coercion": False,
            "valid_combinations": VALID_COMBINATIONS,
            "invalid_aliases": INVALID_ALIASES,
        },
        "four_plane_law": {
            "populations": ["SHADOW", "PAPER", "TESTNET", "LIVE"],
            "promotion": ["TESTNET", "LIVE"],
            "paper_substitutes_for_testnet": False,
            "live_requires_testnet_promotion_receipt": True,
            "shadow": {"population": "SHADOW", "activation": "LIVE", "user_switchable": False, "venue_authority": False},
            "paper": {
                "population": "PAPER", "activation_enum": ["LIVE", "OFF"], "demo_account": True,
                "live_market_data": True, "real_money": False, "venue_authority": False,
            },
            "testnet": {"population": "TESTNET", "venue_path": True, "real_money": False},
            "live": {"population": "LIVE", "venue_path": True, "real_money": True},
        },
        "shadow_law": {
            "population": "SHADOW", "activation": "LIVE", "user_switchable": False,
            "origin_dispositions": ["REJECTED", "ACCEPTED_NOT_EXECUTED", "PROVEN_NO_VENUE_EFFECT"],
            "routes": "Every shadow-tradeable REJECTED candidate; an otherwise accepted candidate with no execution copy uses ACCEPTED_NOT_EXECUTED; a reconciled unknown submit with proven zero venue effect may use PROVEN_NO_VENUE_EFFECT.",
            "tradeability_requirements": [
                "schema_valid", "semantically_valid", "resolved_instrument", "side", "entry_policy",
                "invalidation", "target_or_terminal_rule", "horizon", "finite_numbers", "monotonic_clocks",
                "stable_identity", "causal_market_watermark",
            ],
            "untradeable_input": "Any event/candidate failing schema, semantics, identity, finite-number, time, instrument, or geometry validation uses shadow_rejection_audit.v1 with SHADOW_UNTRADEABLE; no fabricated trade.",
            "continues_for_venue_environments": ["LIVE", "TESTNET", "OFF"],
            "money_authority": False,
            "execution_dependency": "venue_activation and paper_activation resolve OFF when mandatory SHADOW persistence/health is unavailable.",
        },
        "timings": {name: value for name, value, _ in TIMINGS},
        "refusals": [{"code": code, "meaning": meaning, "minimum_action": refusal_action(code)} for code, meaning in REFUSALS],
        "contracts": [{"name": name, "producer": producer, "required": required} for name, producer, required in CONTRACTS],
        "live_mcp_snapshot": {
            "window_utc": "2026-08-09T00:42:05Z/2026-08-09T00:55:53Z",
            "server": "uo-databank 1.28.0", "protocol": "2025-06-18", "tool_count": 85,
            "read_only": True, "operator_token_used": False, "registry": LIVE_REGISTRY,
        },
        "codebase_inventory": CODEBASE_INVENTORY,
        "supersessions": [{"record": a, "old": b, "replacement": c} for a, b, c in SUPERSESSIONS],
        "tasks": TASKS,
        "verifications": VERIFICATIONS,
        "schema": schema,
    }
    bundle_json = canonical_json(bundle).replace("</", "<\\/")
    bundle_digest = hashlib.sha256(canonical_json(bundle).encode()).hexdigest()

    valid_rows = [
        [
            chip(row["venue_environment"], "green" if row["venue_environment"] != "OFF" else "red"),
            chip(row["venue_activation"], "green" if row["venue_activation"] == "LIVE" else "red"),
            chip(row["paper_activation"], "green" if row["paper_activation"] == "LIVE" else "red"),
            chip(row["shadow_activation"], "cyan"), esc(row["meaning"]),
        ]
        for row in VALID_COMBINATIONS
    ]
    refusal_rows = [[f"<code>{esc(code)}</code>", esc(meaning), esc(refusal_action(code))] for code, meaning in REFUSALS]
    timing_rows = [[f"<code>{esc(name)}</code>", f"<code>{value}</code>", esc(note)] for name, value, note in TIMINGS]
    registry_rows = [[
        f'<strong>{esc(row["engine"])}</strong>', esc(row["registry"]), esc(row["freshness"]), esc(row["contradiction"]),
        chip(row["venue_environment"], "red"), chip(row["venue_activation"], "red"), chip("OFF", "red"), chip("LIVE", "cyan"), esc(row["proof"]),
    ] for row in LIVE_REGISTRY]
    codebase_rows = [[
        f'<strong>{esc(row["engine_id"])}</strong><br><span class="muted">{esc(row["display"])}</span>',
        esc(row["as_built"]), esc(row["blocking_evidence"]),
        chip(row["certified_venue_environment"], "red"), chip(row["certified_venue_activation"], "red"),
        chip(row["certified_paper_activation"], "red"), chip(row["required_shadow_activation"], "cyan"), esc(row["enforcement"]),
    ] for row in CODEBASE_INVENTORY]
    finding_rows = [[esc(a), esc(b), esc(c)] for a, b, c in LIVE_FINDINGS]
    supersession_rows = [[f"<code>{esc(a)}</code>", esc(b), esc(c)] for a, b, c in SUPERSESSIONS]
    contract_rows = [[f"<code>{esc(a)}</code>", esc(b), esc(c)] for a, b, c in CONTRACTS]

    css = r"""
:root{--bg:#040a0f;--panel:#0a1720;--panel2:#0e2230;--ink:#e7f3f8;--muted:#94abb7;--line:#244957;--cyan:#50dcf4;--green:#65e3a6;--amber:#ffc75b;--red:#ff6f7b;--violet:#c09cff}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:66px}body{margin:0;background:linear-gradient(180deg,#020609,#07131b 38rem,#050e14);color:var(--ink);font:14.5px/1.58 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;overflow-x:hidden}a{color:var(--cyan);text-decoration:none}code,.mono{font-family:"SFMono-Regular",Consolas,monospace;color:#c9f5ff;overflow-wrap:anywhere}code{background:#06131b;border:1px solid #214453;padding:.08rem .3rem;border-radius:5px}.top{position:sticky;top:0;z-index:20;border-bottom:1px solid #173541;background:rgba(2,8,12,.95);backdrop-filter:blur(12px)}.top>div{max-width:1800px;margin:auto;display:flex;gap:16px;align-items:center;padding:10px 18px;min-width:0}.brand{min-width:310px}.brand b{letter-spacing:.08em}.brand small{display:block;color:var(--muted)}nav{display:flex;gap:7px;overflow:auto;min-width:0}nav a{white-space:nowrap;border:1px solid #294d5c;border-radius:999px;padding:5px 8px;color:#c7dce5;font-size:11px}.hero{padding:62px 0 38px;border-bottom:1px solid #193b48;background:radial-gradient(circle at 85% 8%,rgba(80,220,244,.18),transparent 34%),radial-gradient(circle at 8% 30%,rgba(101,227,166,.10),transparent 32%)}.wrap{width:min(1740px,calc(100% - 38px));margin:auto;min-width:0}.eyebrow{color:var(--cyan);font-weight:900;text-transform:uppercase;letter-spacing:.14em;font-size:12px}.hero h1{font-size:clamp(2.3rem,5.3vw,5.3rem);line-height:.95;letter-spacing:-.05em;margin:.18em 0}.hero h1 em{font-style:normal;color:var(--cyan)}.lead{max-width:1120px;color:#bed3dd;font-size:clamp(1rem,1.55vw,1.25rem)}.chips{display:flex;gap:8px;flex-wrap:wrap;min-width:0}.chip{display:inline-flex;border:1px solid #365665;border-radius:999px;padding:3px 8px;font-size:11px;font-weight:850;max-width:100%;white-space:normal;overflow-wrap:anywhere}.chip.green{color:var(--green);border-color:#2d7555}.chip.red{color:var(--red);border-color:#793943}.chip.cyan,.chip.blue{color:var(--cyan);border-color:#287082}.chip.amber{color:var(--amber);border-color:#775f2b}.layout{max-width:1800px;margin:auto;display:grid;grid-template-columns:260px minmax(0,1fr);gap:22px;padding:25px 18px 80px}.layout main{min-width:0}.side{position:sticky;top:70px;align-self:start;max-height:calc(100vh - 90px);overflow:auto;border:1px solid var(--line);border-radius:14px;background:#07141d;padding:12px}.side strong{color:var(--cyan);display:block;margin:4px 6px 8px}.side a{display:block;color:#b9d0da;padding:5px 7px;border-radius:6px;font-size:12px}.side a:hover{background:#102530}.chapter{margin:0 0 42px;min-width:0}.chapter li{overflow-wrap:anywhere}.chapter h2{font-size:clamp(1.5rem,2.5vw,2.5rem);line-height:1.13;border-bottom:1px solid #245063;padding-bottom:10px}.chapter h2 span{font:.65em "SFMono-Regular",Consolas,monospace;color:var(--cyan);margin-right:11px}.chapter h3{color:#ddf7ff;margin-top:28px}.callout{display:grid;grid-template-columns:minmax(150px,220px) minmax(0,1fr);gap:14px;border:1px solid #2a5261;border-left:5px solid var(--cyan);background:#0a1b25;border-radius:10px;padding:14px 16px;margin:15px 0;min-width:0}.callout.danger{border-left-color:var(--red)}.callout.good{border-left-color:var(--green)}.callout.warn{border-left-color:var(--amber)}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:12px;background:#07141d;margin:12px 0 22px;max-width:100%}.registry{max-height:76vh}table{border-collapse:collapse;width:100%;min-width:940px}th{position:sticky;top:0;background:#102938;color:#d8f7ff;text-align:left;text-transform:uppercase;letter-spacing:.055em;font-size:10.5px;z-index:3}th,td{padding:9px 10px;border-bottom:1px solid #193a47;vertical-align:top}tbody tr:hover{background:#0d202a}.grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:12px;min-width:0}.card{grid-column:span 4;border:1px solid var(--line);border-radius:13px;background:linear-gradient(180deg,#0d1e29,#091720);padding:16px;min-width:0;overflow-wrap:anywhere}.card.wide{grid-column:span 6}.card.full{grid-column:1/-1}.kpi{font-size:2rem;font-weight:950;color:var(--cyan);line-height:1;overflow-wrap:anywhere}.muted{color:var(--muted)}.law{display:grid;grid-template-columns:35px minmax(0,1fr);gap:10px;border:1px solid #214552;background:#091923;border-radius:9px;padding:10px}.laws{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.law b{display:grid;place-items:center;height:28px;border-radius:7px;background:#123247;color:var(--cyan)}.topology{display:block;width:min(1100px,100%);height:auto;margin:16px auto;border:1px solid #2a5b6d;border-radius:13px;background:#02070b}.toolbar{display:flex;gap:7px;flex-wrap:wrap;align-items:center;margin:10px 0}.toolbar input,.toolbar select,.toolbar button,#downloadBundle{background:#071720;color:var(--ink);border:1px solid #2c5362;border-radius:8px;padding:8px 10px}.toolbar input{min-width:260px;flex:1}.toolbar button,#downloadBundle{cursor:pointer;color:var(--cyan)}details{border:1px solid #214453;border-radius:8px;background:#081720;padding:7px;margin-top:6px}summary{cursor:pointer;color:#c9eef9;font-weight:750}dl{display:grid;grid-template-columns:150px 1fr;gap:7px 10px}dt{color:var(--cyan);font-size:10px;text-transform:uppercase;font-weight:850}dd{margin:0}.codebox{white-space:pre-wrap;overflow:auto;max-height:620px;background:#05121a;border:1px solid #244a59;border-radius:12px;padding:14px;color:#d6f4fb}.flow{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:9px}.node{border:1px solid #28586b;background:#0a1d27;border-radius:10px;padding:11px}.node b{display:block;color:var(--cyan)}.footer{border-top:1px solid #193844;padding:30px 20px 45px;color:var(--muted);background:#03090d;overflow-wrap:anywhere}.back{position:fixed;right:17px;bottom:17px;width:42px;height:42px;display:grid;place-items:center;border:1px solid var(--cyan);border-radius:50%;background:#0a2733;color:var(--cyan)}
@media(max-width:1000px){.layout{display:block}.side{position:static;max-height:none;margin-bottom:20px}.card,.card.wide{grid-column:1/-1}.flow{grid-template-columns:1fr 1fr}.laws{grid-template-columns:1fr}.callout{grid-template-columns:1fr}.topology{width:100%}}
@media(max-width:560px){.wrap{width:min(100% - 22px,1740px)}.hero{padding-top:38px}.layout{padding:18px 11px 60px}.flow{grid-template-columns:1fr}.brand{min-width:240px}table{min-width:760px}}
@media print{body{background:#fff;color:#111;font-size:8pt}.top,.side,.toolbar,.back{display:none!important}.layout{display:block;padding:0}.wrap{width:100%}.chapter{content-visibility:visible;contain:none}.hero{background:none;padding:6mm 0}.hero h1{font-size:28pt}.card,.callout,.table-wrap,.law,.node,details,.codebox{background:#fff;color:#111;box-shadow:none;border-color:#888}table{min-width:0;font-size:6.2pt}th{position:static;background:#ddd;color:#111}.muted{color:#444}.topology{max-height:240mm;object-fit:contain}.chip,code{color:#111;background:#fff;border-color:#777}.registry{max-height:none;overflow:visible}}
"""
    laws = [
        "The venue_environment lever accepts only LIVE, TESTNET, or OFF.",
        "venue_activation and paper_activation accept only LIVE or OFF.",
        "Values are uppercase, case-sensitive, whitespace-sensitive, and never coerced or aliased.",
        "The four outcome populations are SHADOW, PAPER, TESTNET, and LIVE; their denominators never mix.",
        "SHADOW records every shadow-tradeable REJECTED candidate; shadow_activation is fixed LIVE and has no OFF control.",
        "Any event or candidate failing shadow-tradeability is recorded as SHADOW_UNTRADEABLE; a trade is never fabricated from malformed geometry.",
        "PAPER is a demo-account plane on live market data with virtual money and zero venue authority.",
        "TESTNET and LIVE use the same E09/adapter lifecycle but physically separate environments, accounts, credentials, and ledgers.",
        "LIVE activation requires a current successful same-digest TESTNET promotion receipt; PAPER never substitutes.",
        "A stale mandatory SHADOW path forces venue_activation and paper_activation OFF while recovery continues.",
        "LIVE and TESTNET accounts, endpoints, credentials, ledgers, leases, orders, fills, and outcomes never mix.",
        "LIVE↔TESTNET transitions pass through venue_activation OFF, reconciliation, flatness, isolation, and venue_environment OFF.",
        "venue_activation OFF blocks new/increasing venue exposure but preserves protection, cancel, reconciliation, and verified reduction.",
        "No process, branch, stream name, enabled boolean, inactivity, or prior fill proves a canonical lever value.",
        "SHADOW freezes every trade hypothesis before rejection and resolves it without hindsight on the same immutable event tape.",
        "The MCP reports evidence only and never becomes the write/control seam.",
    ]
    laws_html = '<div class="laws">' + "".join(f'<div class="law"><b>{i:02d}</b><span>{esc(law)}</span></div>' for i, law in enumerate(laws, 1)) + '</div>'
    schema_pretty = esc(json.dumps(schema, indent=2, ensure_ascii=False))
    toc = [
        ("control", "00 · Control & precedence"), ("decision", "01 · Exact owner decision"),
        ("shadow", "02 · Always-on SHADOW"), ("contracts", "03 · Contracts & schemas"),
        ("derivation", "04 · Truth table & algorithms"), ("wiring", "05 · Wiring & authority"),
        ("live-audit", "06 · Live MCP audit"), ("engines", "07 · Engine certification"),
        ("supersessions", "08 · Master-spec supersessions"), ("migration", "09 · Migration plumbing"),
        ("checklist", f"10 · Checklist ({len(TASKS)})"), ("verification", f"11 · Verification ({len(VERIFICATIONS)})"),
        ("sources", "12 · Sources & security"), ("machine", "13 · Machine authority"),
    ]
    toc_html = "".join(f'<a href="#{a}">{esc(b)}</a>' for a, b in toc)
    quick = "".join(f'<a href="#{a}">{esc(b.split("·",1)[-1].strip())}</a>' for a, b in toc[:7])

    body: list[str] = []
    body.append(section("control", "00", "Document control, authority, and precedence", f"""
    {callout("Controlling disposition", f"The vocabulary and always-on SHADOW decisions are owner-ratified. The live estate is not normalized or certified. This addendum authorizes implementation work but applies no runtime change because the supplied MCP is read-only.", "danger")}
    <div class="grid"><article class="card"><div class="kpi">{esc(VERSION)}</div><h3>Release</h3><p>{esc(STATUS)}</p></article><article class="card"><div class="kpi">4 planes</div><h3>Control law</h3><p>SHADOW, PAPER, TESTNET, LIVE; exact venue and activation levers.</p></article><article class="card"><div class="kpi">{len(TASKS)} / {len(VERIFICATIONS)}</div><h3>Controls</h3><p>Atomic tasks / falsification fixtures.</p></article></div>
    {table(["Authority","Value"],[
        ["Owner directive", "SHADOW always LIVE; PAPER demo activation LIVE|OFF; venue_environment LIVE|TESTNET|OFF; venue_activation LIVE|OFF"],
        ["Precedence", "This addendum supersedes conflicting effective RC1/RC2/RC3 lever semantics; historical bytes remain audit evidence."],
        ["RC3 baseline", f'<code>{rc3_digest}</code>'],
        ["Machine bundle digest", f'<code>{bundle_digest}</code>'],
        ["Activation authority", "None. Read-only inspection only; no setting, order, route, account, or service was changed."],
    ])}
    """))
    body.append(section("decision", "01", "Exact lever law — no aliases and no third vocabulary", f"""
    {laws_html}
    <h3>Valid combinations</h3>{table(["Venue environment","Venue activation","PAPER activation","SHADOW activation","Exact effect"], valid_rows)}
    {callout("Fail-closed projection is not proof of physical OFF", "Every currently uncertified engine is projected as venue_environment OFF / venue_activation OFF. That does not prove the legacy runtime is physically unable to trade. SHADOW remains LIVE by owner law; PAPER remains OFF until its keyless isolation is proven.", "warn")}
    <h3>Exact timing constants</h3>{table(["Variable","Value","Boundary"], timing_rows)}
    <h3>Named refusals</h3>{table(["Code","Meaning","Minimum fail-closed action"], refusal_rows)}
    """))
    body.append(section("shadow", "02", "Four-plane law — SHADOW, PAPER, TESTNET, LIVE", f"""
    {callout("Owner directive", "SHADOW capture is permanently LIVE. It is not an optional experiment switch and is independent of venue_activation and paper_activation.", "good")}
    {table(["Population","Receives","Execution model","Capital","Promotion meaning"],[
        [chip("SHADOW","cyan"), "Every shadow-tradeable REJECTED candidate; accepted but unexecuted or proven-no-effect hypothesis", "Internal keyless simulator/resolver", "None", "Measures rejection quality; never promotes by itself"],
        [chip("PAPER","cyan"), "Accepted candidates when paper_activation=LIVE", "Virtual demo account on live market data", "Virtual only", "Product/logic rehearsal; not venue certification"],
        [chip("TESTNET","cyan"), "Accepted candidates when venue_environment=TESTNET and venue_activation=LIVE", "Real E09/adapter/order lifecycle on exchange test environment", "No real money", "Mandatory execution certification before LIVE"],
        [chip("LIVE","green"), "Accepted candidates when venue_environment=LIVE and venue_activation=LIVE", "Real E09/adapter/order lifecycle on real accounts", "Real money", "LIVE real-capital population"],
    ])}
    <div class="flow"><div class="node"><b>edge_candidate.v2</b>Complete causal hypothesis</div><div class="node"><b>E07/E08 routing</b>ACCEPTED or REJECTED</div><div class="node"><b>REJECTED → SHADOW</b>Always-LIVE simulator/recorder</div><div class="node"><b>ACCEPTED</b>PAPER and/or TESTNET/LIVE</div><div class="node"><b>E10 comparison</b>Four separate populations</div></div>
    {callout("Promotion law", "TESTNET is the required venue-execution predecessor to LIVE. PAPER is a separate demo plane and cannot substitute for TESTNET. SHADOW is continuously measuring rejected opportunities and is not a promotion rung.", "warn")}
    <h3>Non-negotiable behavior</h3><ul>
      <li>Every shadow-tradeable candidate rejected by E07 decision/policy, E08 risk/capacity, or pre-submit E09 eligibility produces one immutable SHADOW trade intent.</li>
      <li>Any event or candidate that fails shadow-tradeability is still recorded, but as SHADOW_UNTRADEABLE rather than a fabricated trade.</li>
      <li>Venue OFF does not stop SHADOW. TESTNET, LIVE, and PAPER never consume or relabel SHADOW.</li>
      <li>The shadow outbox is keyless and has no E09 subject, credential, venue adapter, or money-selection lease.</li>
      <li>A no-fill, rejection, timeout, or unresolved horizon is recorded honestly; no row is dropped to improve results.</li>
      <li>Each SHADOW hypothesis is frozen before the rejection result and resolved without future data against the same immutable tape and a versioned conservative cost/fill model.</li>
      <li>Comparable performance uses bps, R-multiple, and one fixed evaluation notional; a rejected proposed size is retained as evidence but cannot distort the alpha denominator.</li>
      <li>SHADOW_UNTRADEABLE records count toward rejection coverage but never enter shadow trade win-rate or EV denominators.</li>
      <li>SHADOW, PAPER, TESTNET, and LIVE remain physically and analytically separate. Candidate lineage enables comparison, never denominator mixing.</li>
      <li>Mandatory SHADOW persistence/health failure forces PAPER and venue execution OFF. Existing venue protection and reduction remain available.</li>
      <li>An unknown venue submit is never presumed rejected. Reconcile first; create a SHADOW fallback only after proving no venue effect.</li>
    </ul>
    {callout("Critical distinction", "SHADOW activation can be LIVE while health is DOWN. Activation is the fixed desired control; health is observed reality. The UI must show both and must never rewrite DOWN as OFF or LIVE as healthy.", "warn")}
    """))
    body.append(section("contracts", "03", "Normative contracts, fields, and exact schemas", f"""
    {table(["Contract","Producer","Required material"], contract_rows)}
    <h3>engine_control_manifest.v2 schema</h3><pre class="codebox">{schema_pretty}</pre>
    {callout("Semantic validation is mandatory", "JSON Schema closes the values; a separate semantic validator enforces valid combinations, PAPER keylessness, complete registry coverage, transition receipts, environment isolation, SHADOW constants, leases, and freshness. Schema-valid does not automatically mean authority-valid.", "danger")}
    """))
    body.append(section("derivation", "04", "Effective-value derivation and transition algorithms", f"""
    <h3>Canonical evaluation order</h3><ol>
      <li>Parse exact bytes. Do not trim, case-fold, alias, coerce, or default.</li>
      <li>Validate venue_environment, venue_activation, and paper_activation independently against their closed enums.</li>
      <li>Validate the venue pair. venue_environment OFF with venue_activation LIVE is invalid. shadow_activation must be LIVE.</li>
      <li>Resolve estate, engine, and exact-scope records. Any applicable OFF activation dominates. Conflicting non-OFF venue environments reject.</li>
      <li>Verify manifest signature, registry completeness, revision, build/config/contract/parameter digests, runtime readback, clock, route, account, credential fingerprint, private state, leases, and opposite-environment unreachability.</li>
      <li>Require venue_binding to equal venue_environment and the exact venue/account scope. For LIVE/LIVE, require a current PASS receipt from TESTNET with identical scope and build/config/contracts/parameters/strategy/adapter digests.</li>
      <li>For a REJECTED complete candidate, verify its SHADOW trade was durably persisted. For an ACCEPTED candidate, verify at least one PAPER/venue execution copy or a SHADOW ACCEPTED_NOT_EXECUTED record.</li>
      <li>E07, E08, and E09 each re-check their relevant proof. E09 checks immediately before the venue effect.</li>
      <li>Any missing, stale, conflicting, or invalid proof resolves venue_activation and affected paper_activation OFF and emits one named refusal. SHADOW stays LIVE.</li>
    </ol>
    <h3>Environment transition</h3><ol>
      <li>Set venue_activation OFF and revoke new-entry admission to the venue path.</li><li>Keep cancel, protection, reconciliation, and verified reduction available.</li>
      <li>Reconcile positions, regular orders, algo/protection orders, reservations, leases, sessions, and private state every 1,000 ms.</li>
      <li>When flat and drained, revoke the old lease, credential ACL, route, and session; then set venue_environment OFF.</li>
      <li>Attest the opposite environment is unreachable. Bind the new endpoint/account/credential/ledger/route set.</li>
      <li>Set the new venue_environment with venue_activation OFF and re-attest. For LIVE, validate the same-digest TESTNET receipt; then separately approve venue_activation LIVE.</li>
      <li>If not drained after 300,000 ms, remain in the old venue_environment with venue_activation OFF and raise an incident. Never force an unsafe venue_environment OFF.</li>
    </ol>
    """))
    body.append(section("wiring", "05", "Topology wiring, authority, and failure plumbing", f"""
    <img class="topology" src="data:image/png;base64,{topology_data}" alt="TRIAD target-state topology">
    {callout("The image is illustrative", "The written authority below controls. The topology does not prove deployed edges and currently contains dev/stage/prod wording that this addendum supersedes for trading environment levers.", "warn")}
    {table(["Boundary","Required guard","Failure behavior"],[
        ["Configuration → every node", "W26 engine_control_manifest.v2; authenticated delivery, CAS revision, exact digests", "Refuse PAPER/venue authority; SHADOW recovery process remains LIVE."],
        ["Every node → evidence", "W27 runtime_lever_attestation.v1 every 5,000 ms", "After 15,000 ms stale, venue/PAPER activation OFF."],
        ["E07 rejection → SHADOW", "shadow_trade.v1 outbox for every shadow-tradeable REJECTED candidate", "After 100 ms unpersisted, refuse execution activations for scope."],
        ["Invalid input/candidate → SHADOW audit", "shadow_rejection_audit.v1", "Record SHADOW_UNTRADEABLE; never fabricate geometry."],
        ["E07 acceptance → PAPER", "paper_trade.v1 when paper_activation LIVE", "Virtual demo ledger only; any venue reach is P0."],
        ["E07 acceptance → E08", "venue_environment/venue_activation revision", "Reject venue candidate; if no PAPER copy, record ACCEPTED_NOT_EXECUTED in SHADOW."],
        ["E07 → E08", "Eligibility, exact scope, current lever proof", "No reservation or size."],
        ["E08 → E09", "execution_authorization.v3, environment, revision, lease epoch, expiry", "No venue command."],
        ["E09 → venue", "Immediate readback, route/account isolation, private state, stale-epoch rejection", "No new effect; reconcile and alert."],
        ["E09 → E10", "fill.v3/order/position/protection facts with environment and full lineage", "Quarantine incomplete money truth."],
        ["Four planes → E10", "Separate SHADOW/PAPER/TESTNET/LIVE contracts, tables, population IDs", "Never average populations; compare through candidate lineage only."],
    ])}
    """))
    body.append(section("live-audit", "06", "Fresh live MCP behavior audit — 2026-08-09", f"""
    {callout("Decisive finding", "The current estate has no single authoritative answer for environment or activation. Registry, route, stream, config, relay, service, and fill evidence disagree. No exposed key certifies TESTNET or proves it unreachable.", "danger")}
    {table(["Evidence","Observed","Meaning"], finding_rows)}
    <h3>Forbidden values inside canonical lever fields</h3><p><code>{esc(' · '.join(INVALID_ALIASES))}</code></p><p class="muted">SHADOW and PAPER are legal population labels. They are rejected only when someone incorrectly places them into venue_environment or an activation field.</p>
    {callout("Read coverage limits", "get_stream_summary and get_positions_unified timed out. execution and risk config returned empty arrays. Two exact configuration APIs disagreed about STAGE1_LIVE. These are evidence defects, not zero values.", "warn")}
    """))
    body.append(section("engines", "07", "Engine-by-engine canonical certification projection", f"""
    {callout("How to read OFF / OFF", "This is the only honest fail-closed certification result under the new law. It does not claim the legacy estate is physically OFF; the final column explicitly records that enforcement is not yet proven.", "warn")}
    <h3>Pinned as-built codebase inventory</h3>
    {table(["Engine","As-built role","Why non-OFF is blocked","Venue env","Venue activation","PAPER activation","Required SHADOW activation","Enforcement"], codebase_rows)}
    <h3>Fresh runtime identities observed through MCP</h3>
    {table(["Engine","Raw registry/config","Freshness","Contradiction","Certified venue env","Certified venue activation","Certified PAPER activation","Required SHADOW activation","Certification"], registry_rows)}
    <h3>Current side-effect census</h3><p>At the audit window: zero open orders and zero current positions. Latest Hyperliquid fill was 2026-08-05; latest Binance fill was 2026-07-06. This does not prove OFF, because inactivity is not a control readback or a negative side-effect test.</p>
    """))
    body.append(section("supersessions", "08", "Exact master-spec conflicts and controlling replacements", f"""
    {table(["Record / family","Conflicting existing rule","RC4 controlling replacement"], supersession_rows)}
    {callout("Historical text remains", "RC1/RC2/RC3 source rows and the dated MCP books remain intact as audit evidence. An effective-control evaluator must apply these supersessions before implementation or gate evaluation.", "warn")}
    """))
    body.append(section("migration", "09", "Migration, coexistence, cutover, and rollback", f"""
    <h3>Required sequence</h3><ol>
      <li>Freeze legacy lever changes except emergency activation OFF.</li><li>Complete the as-built census and identify every hidden default, precedence path, supervisor capture, direct broker, and bypass.</li>
      <li>Publish the new contracts and registry. Deploy read-only projections first; they grant no authority.</li><li>Dual-read legacy and canonical controls for seven continuous days and through restart, process replacement, stale cache, network partition, and lease-expiry drills.</li>
      <li>Run the canonical guards in report-only comparison, then enforce routing at E07, risk at E08, and venue effect at E09. E09 is the final non-bypassable venue boundary.</li><li>Migrate one engine and one exact scope at a time while SHADOW remains LIVE for all shadow-tradeable REJECTED candidates.</li>
      <li>Prove PAPER is keyless and cannot reach a venue. Prove TESTNET and LIVE isolation with separate endpoints, accounts, credentials, ledgers, leases, sessions, and side-effect censuses.</li><li>Delete or de-permission every legacy writer only after canonical readback, negative bypass tests, and rollback rehearsal pass.</li>
    </ol>
    <h3>Rollback</h3><p>Rollback sets venue_activation and paper_activation OFF first. It never turns SHADOW off. Existing venue positions retain protection, cancel, reconciliation, and verified reduction until flat; only then may venue_environment become OFF. A rollback cannot restore a legacy boolean or alias as authority.</p>
    """))
    body.append(section("checklist", "10", f"Complete atomic implementation checklist — {len(TASKS)} tasks", f"""
    {callout("Execution rule", "A task is not complete because code exists. It requires exact-scope evidence, falsifiable tests, current digests, an accountable owner, independent review where required, and a stop/rollback receipt.", "danger")}
    {task_table()}
    """))
    body.append(section("verification", "11", f"Verification and falsification matrix — {len(VERIFICATIONS)} fixtures", f"""
    {verification_table()}
    """))
    body.append(section("sources", "12", "Evidence sources, limitations, and credential handling", f"""
    {table(["Source","Use","Limit"],[
        ["Read-only settings MCP, 2026-08-09", "Fresh engine registry/config/runtime/relay/order/position/fill observations", "Contradictory inventories; timeouts; no canonical environment field; no write/enforcement proof."],
        ["INVESTIGATION-MCP-FOR-LIKO.md", "Historical SHADOW/MONEY separation and false-LIVE scorecard incident", "Dated 2026-08-07; fill.v1 limitations."],
        ["MCP-COMPLETE-BOOK.md", "Historical MCP family/tool vocabulary and authority boundaries", "Different triad-mcp surface; dated 2026-08-07."],
        ["TRIAD ORIGIN V7 RC3", "Architecture, contracts, checklist, formulas, wiring, and machine overlay baseline", f'Superseded for lever semantics by this addendum; SHA-256 {rc3_digest}.'],
        ["Topology V3", "Visual orientation", "Illustrative target state, not deployed proof."],
    ])}
    {callout("Credential action", "No credential is embedded in this artifact. The two bearer credentials supplied in chat should be rotated after this audit because they were disclosed as plaintext and do not expire until 2026-11-06.", "danger")}
    """))
    body.append(section("machine", "13", "Embedded machine-readable authority and integrity", f"""
    <div class="grid"><article class="card wide"><div class="kpi">SHA-256</div><p><code>{bundle_digest}</code></p><p>Canonical embedded control bundle.</p></article><article class="card wide"><div class="kpi">SECRET-FREE</div><p>No bearer, JWT, query token, credential hash, or authorization header is included.</p></article></div>
    <p><button id="downloadBundle">Download embedded control bundle</button></p>
    <p class="muted">The bundle contains the four-plane law, fixed SHADOW law, PAPER controls, venue levers, timings, refusals, contracts, pinned codebase inventory, sanitized live snapshot, supersessions, {len(TASKS)} tasks, {len(VERIFICATIONS)} verifications, and the manifest schema.</p>
    """))

    js = r"""
const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
function populateFacets(){ $$('[data-facet-for]').forEach(sel=>{const table=$('#'+sel.dataset.facetFor),key=sel.dataset.facet;const vals=[...new Set($$('tbody tr',table).map(r=>r.dataset[key]).filter(Boolean))].sort();vals.forEach(v=>{const o=document.createElement('option');o.value=v;o.textContent=v;sel.appendChild(o)})}) }
function apply(id){const t=$('#'+id);if(!t)return;const q=($(`[data-query-for="${id}"]`)?.value||'').trim().toLowerCase();const facets=$$(`[data-facet-for="${id}"]`);let n=0,total=0;$$('tbody tr',t).forEach(r=>{total++;let ok=!q||(r.dataset.search||r.textContent.toLowerCase()).includes(q);facets.forEach(f=>{if(f.value&&(r.dataset[f.dataset.facet]||'')!==f.value)ok=false});r.hidden=!ok;if(ok)n++});const c=$(`[data-count-for="${id}"]`);if(c)c.textContent=`${n} / ${total}`}
populateFacets();$$('[data-query-for]').forEach(e=>e.addEventListener('input',()=>apply(e.dataset.queryFor)));$$('[data-facet-for]').forEach(e=>e.addEventListener('change',()=>apply(e.dataset.facetFor)));$$('[data-reset-for]').forEach(b=>b.addEventListener('click',()=>{const id=b.dataset.resetFor;const q=$(`[data-query-for="${id}"]`);if(q)q.value='';$$(`[data-facet-for="${id}"]`).forEach(x=>x.value='');apply(id)}));
$('#downloadBundle')?.addEventListener('click',()=>{const raw=$('#rc4-control-bundle').textContent,a=document.createElement('a');a.href=URL.createObjectURL(new Blob([raw],{type:'application/json'}));a.download='TRIAD_ORIGIN_V7_RC4_FOUR_PLANE_CONTROL_BUNDLE.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)});
"""
    document = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="TRIAD ORIGIN V7 SHADOW PAPER TESTNET LIVE four-plane and exact lever master addendum"><title>TRIAD ORIGIN V7 — Four-Plane Execution & Lever Master Addendum — {VERSION}</title><style>{css}</style></head>
<body id="top"><header class="top"><div><div class="brand"><b>TRIAD ORIGIN V7</b><small>Four-Plane Execution + Exact Levers · {VERSION}</small></div><nav>{quick}</nav></div></header>
<section class="hero"><div class="wrap"><div class="eyebrow">Normative master addendum · Exact controls · Fresh live audit</div><h1>SHADOW · PAPER<br><em>TESTNET → LIVE</em></h1><p class="lead">SHADOW records every shadow-tradeable REJECTED candidate and can never be turned off. Invalid hypotheses remain auditable without fabricated trades. PAPER is the demo-account plane. TESTNET and LIVE share the real venue execution lifecycle but remain physically isolated.</p><div class="chips">{chip(VERSION,"cyan")}{chip(STATUS,"amber")}{chip("shadow_activation = LIVE","green")}{chip("paper_activation = LIVE | OFF","cyan")}{chip("venue_environment = LIVE | TESTNET | OFF","cyan")}{chip("promotion = TESTNET → LIVE","cyan")}{chip("RUNTIME NOT CHANGED","red")}</div></div></section>
<div class="layout"><aside class="side"><strong>Contents</strong>{toc_html}</aside><main>{''.join(body)}</main></div><footer class="footer"><div class="wrap"><b>TRIAD ORIGIN V7 — Four-Plane Execution & Lever Master Addendum</b><p>{VERSION} · issued {ISSUED_UTC} · bundle {bundle_digest}</p></div></footer><a class="back" href="#top">↑</a>
<script id="rc4-control-bundle" type="application/json">{bundle_json}</script><script>{js}</script></body></html>"""
    OUTPUT.write_text(document, encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT), "bytes": OUTPUT.stat().st_size, "sha256": sha256(OUTPUT),
        "bundle_sha256": bundle_digest, "tasks": len(TASKS), "verifications": len(VERIFICATIONS),
        "issued_utc": ISSUED_UTC, "built_at_utc": datetime.now(timezone.utc).isoformat(),
    }, indent=2))


if __name__ == "__main__":
    build()
