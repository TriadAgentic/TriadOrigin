#!/usr/bin/env python3
"""Deterministic generator for the ORIGIN contract bundle (Doc 03).

Materializes, from the normative field profiles:
  * ``contracts/schemas/<schema_id>.schema.json`` — JSON Schema (draft 2020-12), self-contained,
  * ``contracts/golden/<schema_id>/{valid,invalid}.json`` — golden vectors,
  * ``contracts/registry/index.json`` — the contract registry index.

The generator is the *source*; the committed JSON bytes are the *artifact* pinned by
``contracts/MANIFEST.sha256`` (regenerate that with ``tools/gen_manifest.py``).

Byte-canonical output: ``json.dumps(sort_keys=True, indent=2)`` + trailing newline. Re-running is a
no-op unless a profile changed. No clock, no randomness.
"""

from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "contracts" / "schemas"
GOLDEN_DIR = ROOT / "contracts" / "golden"
REGISTRY_DIR = ROOT / "contracts" / "registry"

DRAFT = "https://json-schema.org/draft/2020-12/schema"

# Envelope fields always required (Doc 03 §03.3).
ENVELOPE_REQUIRED = [
    "schema",
    "schema_version",
    "event_id",
    "event_kind",
    "producer_service",
    "producer_instance_id",
    "emitted_at_us",
    "contract_manifest_sha256",
    "config_bundle_sha256",
    "build_commit",
    "artifact_sha256",
    "payload",
]
ENVELOPE_OPTIONAL = ["producer_epoch", "activation_manifest_id", "traceparent", "correlation_id"]

DECIMAL_UINT = r"^(0|[1-9][0-9]*)$"
SIGNED_INT = r"^-?(0|[1-9][0-9]*)$"
HEX64 = r"^[0-9a-f]{64}$"


# Contract profile: (schema_id, semantic_version, producer, consumers, event_kinds, authority,
#                    required_payload_fields, payload_enums, forbidden_fields)
def _c(schema_id, version, producer, consumers, event_kinds, authority, required, enums=None,
       forbidden=None, payload_overrides=None, invalid_payload_overrides=None,
       superseded_by=None):
    return {
        "id": schema_id,
        "version": version,
        "producer": producer,
        "consumers": consumers,
        "event_kinds": event_kinds,
        "authority": authority,  # True => producer_epoch required (fenced authoritative topic)
        "required": required,
        "enums": enums or {},
        "forbidden": forbidden or [],
        # Semantic-law contracts need goldens that satisfy (valid) / violate (invalid) the
        # cross-field law, not just the JSON Schema — overrides patch the generated payloads.
        "payload_overrides": payload_overrides or {},
        "invalid_payload_overrides": invalid_payload_overrides or {},
        "superseded_by": superseded_by,
    }


DIRECTION = ["LONG", "SHORT"]

CONTRACTS = [
    _c("triad.market_event.v2", "2.0.0", "triad-e00", ["triad-e01", "raw-ledger", "replay"],
       ["DEPTH_DIFF", "BOOK_TICKER", "AGG_TRADE", "MARK_PRICE", "KLINE", "TICKER", "LIQUIDATION",
        "ORDER_UPDATE", "ACCOUNT_UPDATE", "ALGO_UPDATE", "LISTEN_KEY_EXPIRED"], True,
       ["raw_event_id", "venue", "route_family", "source_stream", "connection_epoch",
        "receive_sequence", "canonical_instrument_id", "venue_instrument_id",
        "source_event_time_us", "local_receipt_wall_us", "local_receipt_mono_ns",
        "normalization_time_us", "instrument_metadata_revision", "raw_payload_hash", "quality",
        "parser_version"],
       {"route_family": ["PUBLIC", "MARKET", "PRIVATE"]}),

    _c("triad.market_state.v2", "2.0.0", "triad-e01", ["origin", "features", "replay"],
       ["BOOK", "BAR", "TRADE", "DERIVATIVE"], True,
       ["state_revision_id", "partition_key", "state_kind", "canonical_instrument_id", "timeframe",
        "source_offset_range", "dependency_event_ids", "finalized_event_time_us",
        "watermark_complete", "knowledge_time_us", "publication_time_us", "instrument_revision",
        "validity", "book_sequence_state", "bar_finalization_state", "provenance_hash",
        "prior_revision_id"],
       {"validity": ["SYNCING", "READY", "DEGRADED", "GAPPED", "STALE"]}),

    _c("triad.feature_snapshot.v2", "2.0.0", "origin-feature-primitives",
       ["capsules", "intelligence", "replay"], ["FEATURE_SNAPSHOT"], True,
       ["feature_set", "feature_version", "partition_key", "as_of_state_revision_id",
        "feature_values", "dependency_ranges", "formula_digest", "parameter_digest",
        "warmup_status", "source_time_us", "knowledge_time_us", "evaluation_time_us",
        "publication_time_us", "output_hash"]),

    _c("triad.structure_atom.v2", "2.0.0", "origin", ["lifecycle", "audit", "learning"],
       ["STRUCTURE_CONFIRMED"], True,
       ["structure_id", "semantic_instance_id", "structure_kind", "structure_subtype",
        "canonical_instrument_id", "venue_model", "timeframe", "direction", "origin_source_ids",
        "confirmation_source_ids", "origin_time_us", "confirmation_time_us", "availability_time_us",
        "knowledge_time_us", "original_geometry", "original_geometry_digest", "reference_level_ids",
        "source_offset_range", "dependency_quality", "formula_version", "parameter_set_id",
        "parameter_digest", "build_commit", "config_bundle_sha256", "instrument_digest", "state",
        "predecessor_structure_ids"],
       {"direction": DIRECTION, "state": ["CONFIRMED"]}),

    _c("triad.structure_transition.v2", "2.0.0", "origin-lifecycle-reducer",
       ["candidate-reducer", "audit"], ["STRUCTURE_TRANSITION"], True,
       ["transition_id", "structure_id", "state_seq", "previous_transition_id", "from_state",
        "to_state", "transition_reason", "geometry_revision", "current_geometry", "event_time_us",
        "receipt_time_us", "knowledge_at_us", "publication_time_us", "source_event_ids",
        "reference_ids", "watermark_complete", "quality_snapshot", "provenance_hash"]),

    _c("triad.reaction_event.v1", "1.0.0", "origin-reaction-engine", ["capsule-host", "evidence"],
       ["REACTION_EVALUATED"], True,
       ["reaction_id", "source_structure_id", "source_transition_id", "location_result",
        "departure_result", "trigger_result", "confirmation_result", "fresh_flow_atom_ids",
        "first_touch_ordinal", "natural_entry_ticks", "natural_invalidation_ticks", "target_ticks",
        "rr_numerator", "rr_denominator", "cancellation_causes", "not_before_us", "expiry_us",
        "dependency_clocks"]),

    _c("triad.edge_candidate.v2", "2.0.0", "origin", ["e07", "comparator", "evidence"],
       ["EDGE_CANDIDATE"], True,
       ["candidate_id", "hypothesis_id", "opportunity_cluster_id", "capsule_id", "capsule_version",
        "parameter_digest", "trial_id", "source_structure_id", "source_reaction_id",
        "canonical_instrument_id", "direction", "horizon", "entry_policy", "entry_reference_ticks",
        "natural_invalidation_ticks", "targets", "rr_numerator", "rr_denominator", "ttl_us",
        "not_before_us", "cancellation_conditions", "cost_model_id", "fill_model_id", "arm",
        "quality", "prerequisites", "provenance_hash"],
       {"direction": DIRECTION, "arm": ["CONTROL", "TREATMENT", "SHADOW"]},
       forbidden=["final_approval", "account_id", "notional", "leverage", "executable_quantity",
                  "venue_order_id", "raw_credentials", "expected_return", "e09_destination"]),

    _c("triad.edge_candidate_transition.v1", "1.0.0", "origin", ["e07", "audit"],
       ["CANDIDATE_TRANSITION"], True,
       ["transition_id", "candidate_id", "state_seq", "previous_transition_id", "from_state",
        "to_state", "reason", "source_transition_id", "event_time_us", "knowledge_at_us"]),

    _c("triad.decision.v2", "2.0.0", "triad-e07", ["e08", "evidence"], ["DECISION"], True,
       ["decision_id", "candidate_id", "opportunity_cluster_id", "arm", "allocation_manifest_id",
        "policy_id", "policy_version", "policy_digest", "disposition", "clause_results",
        "arbitration_set", "arbitration_winner", "economic_assumption_refs", "reason",
        "valid_until_us", "decided_at_us"],
       {"disposition": ["TAKE", "WAIT", "SKIP"]}),

    _c("triad.risk_decision.v2", "2.0.0", "triad-e08", ["e09", "audit"], ["RISK_DECISION"], True,
       ["risk_decision_id", "decision_id", "candidate_id", "account_id", "risk_cell",
        "environment", "disposition", "clause_evaluations", "exposure_snapshot_id", "policy_digest",
        "max_qty_steps", "max_notional_quote", "max_leverage", "loss_budget", "correlation_budget",
        "protection_requirements", "reservation_id", "reservation_expiry_us", "valid_until_us",
        "denial_reason"],
       {"disposition": ["ALLOW", "DENY", "REDUCE_ONLY"], "environment": ["LIVE"]}),

    _c("triad.risk_reservation.v1", "1.0.0", "triad-e08", ["e09", "reconciler"], ["RESERVATION"],
       True,
       ["reservation_id", "risk_decision_id", "account_id", "risk_cell", "canonical_instrument_id",
        "reserved_amount", "reserved_unit", "state", "expiry_us", "owner", "linked_execution_ids"],
       {"state": ["REQUESTED", "HELD", "COMMITTED", "RELEASED", "EXPIRED", "REVOKED"]}),

    _c("triad.execution_authorization.v2", "2.0.0", "triad-e08", ["e09-orchestrator"],
       ["EXECUTION_AUTHORIZATION"], True,
       ["candidate_id", "decision_id", "risk_decision_id", "reservation_id", "account_id",
        "canonical_instrument_id", "direction", "position_effect", "max_qty_steps",
        "max_notional_quote", "entry_geometry", "invalidation_geometry", "target_geometry",
        "allowed_liquidity", "allowed_tif", "allowed_order_roles", "protection_deadline_us",
        "protection_budget", "valid_until_us"],
       {"direction": DIRECTION,
        "position_effect": ["OPEN", "INCREASE", "REDUCE", "CLOSE", "REVERSE"]}),

    _c("triad.emergency_exit_authorization.v1", "1.0.0", "triad-e08", ["e09"],
       ["EMERGENCY_EXIT_AUTHORIZATION"], True,
       ["position_snapshot_id", "max_reducible_qty_steps", "position_side", "position_mode",
        "urgency_tier", "worst_acceptable_price_ticks", "tier2_market_permitted", "trigger",
        "evidence", "standing_policy_id", "standing_policy_signature", "expiry_us", "serial_key",
        "audit_reason"],
       {"position_side": ["LONG", "SHORT", "BOTH"], "position_mode": ["ONE_WAY", "HEDGE"],
        "urgency_tier": ["TIER1", "TIER2"]}),

    # 2.1.0 (B01/RC4): every venue command names its exact environment + the accepted
    # venue-activation revision it executes under.
    _c("triad.execution_cmd.v2", "2.1.0", "e09-orchestrator", ["e09-venue-adapter"],
       ["EXECUTION_CMD"], True,
       ["command_id", "attempt_id", "idempotency_id", "authorization_id", "reservation_id",
        "account_id", "canonical_instrument_id", "venue", "venue_environment",
        "venue_activation_revision", "order_side", "position_side",
        "position_effect", "quantity_steps", "price_ticks", "order_type", "time_in_force",
        "post_only", "reduce_only", "close_position", "working_type", "price_protect", "stp",
        "role", "deadline_us", "urgency", "retry_budget", "adapter_route",
        "expected_prior_order_state"],
       {"order_side": ["BUY", "SELL"], "position_side": ["LONG", "SHORT", "BOTH"],
        "position_effect": ["OPEN", "INCREASE", "REDUCE", "CLOSE", "REVERSE"],
        "venue_environment": ["LIVE", "TESTNET"]}),

    _c("triad.order_event.v2", "2.0.0", "e09-oms-vgp", ["reconciler", "e10", "audit"],
       ["ORDER_EVENT"], True,
       ["oms_order_id", "venue_order_id", "command_id", "idempotency_id", "authorization_id",
        "account_id", "canonical_instrument_id", "order_side", "position_side", "position_effect",
        "order_role", "liquidity_intent", "order_type", "time_in_force", "price_ticks", "qty_steps",
        "cumulative_qty_steps", "remaining_qty_steps", "state", "reason", "venue_response",
        "event_time_us", "transaction_time_us", "receipt_time_us", "order_family",
        "reconciliation_status", "source_payload_hash"],
       {"order_side": ["BUY", "SELL"], "order_family": ["REGULAR", "ALGO"]}),

    # 3.1.0 (B01/RC4): environment widened to LIVE|TESTNET — the four-plane law certifies the
    # two venue environments separately and forbids mixing them in one bundle.
    _c("triad.fill.v3", "3.1.0", "e09-fill-normalizer", ["reconciler", "e10", "learning"],
       ["FILL"], True,
       ["fill_id", "venue_trade_id", "oms_order_id", "venue_order_id", "execution_command_id",
        "authorization_id", "economic_idempotency_id", "venue", "environment", "account_id",
        "canonical_instrument_id", "venue_instrument_id", "instrument_revision", "risk_decision_id",
        "reservation_id", "decision_id", "candidate_id", "hypothesis_id", "opportunity_cluster_id",
        "structure_id", "capsule_id", "capsule_version", "lane", "experiment_arm", "campaign_id",
        "position_id", "order_side", "position_side", "position_mode", "position_effect",
        "order_role", "liquidity_role", "reduce_only", "close_position", "price_ticks", "qty_steps",
        "base_value", "quote_value", "fee_asset", "fee_amount_atomic", "fee_quote_minor",
        "conversion_evidence", "exchange_transaction_time_us", "exchange_event_time_us",
        "local_receipt_wall_us", "local_receipt_mono_ns", "normalized_time_us", "recorded_time_us",
        "connection_session_id", "raw_payload_digest", "reconciliation_status",
        "position_effect_derivation_evidence", "role_derivation_evidence"],
       {"environment": ["LIVE", "TESTNET"], "order_side": ["BUY", "SELL"],
        "position_side": ["LONG", "SHORT", "BOTH"], "position_mode": ["ONE_WAY", "HEDGE"],
        "position_effect": ["OPEN", "INCREASE", "REDUCE", "CLOSE", "REVERSE"],
        "order_role": ["ENTRY", "EXIT", "PROTECTION", "EMERGENCY"],
        "liquidity_role": ["MAKER", "TAKER"],
        "reconciliation_status": ["VENUE_CONFIRMED", "PENDING", "QUARANTINED"]}),

    _c("triad.venue_account_event.v2", "2.0.0", "e09-vgp", ["exposure", "reconciler", "audit"],
       ["VENUE_ACCOUNT_EVENT"], True,
       ["account_id", "venue", "session_id", "venue_event_kind", "venue_ids", "venue_sequences",
        "canonical_mapping", "raw_payload", "normalized_payload", "event_time_us", "receipt_time_us",
        "connection_state", "reconciliation_state"],
       {"venue_event_kind": ["ACCOUNT", "BALANCE", "MARGIN", "POSITION", "ORDER", "ALGO_ORDER",
                             "FILL", "REJECTION", "DISCONNECT", "RATE_LIMIT", "LIQUIDATION",
                             "ADL"]}),

    _c("triad.position_event.v2", "2.0.0", "e09-reconciler", ["e08", "protection", "e10"],
       ["POSITION_EVENT"], True,
       ["position_id", "campaign_id", "account_id", "canonical_instrument_id", "position_mode",
        "position_side", "before_qty_steps", "delta_qty_steps", "after_qty_steps",
        "average_price_ticks", "realized_value", "unrealized_value", "cause_fill_id",
        "cause_order_id", "cause_account_event_id", "protection_group_id", "margin", "leverage",
        "event_time_us", "receipt_time_us", "reconciliation_time_us", "status",
        "conservation_proof"],
       {"position_mode": ["ONE_WAY", "HEDGE"], "position_side": ["LONG", "SHORT", "BOTH"],
        "status": ["OPENING", "OPEN", "REDUCING", "FLAT_PENDING_RECONCILIATION", "FLAT",
                   "UNKNOWN"]}),

    _c("triad.protection_event.v2", "2.0.0", "e09-protection-owner",
       ["e08", "operations", "e10"], ["PROTECTION_EVENT"], True,
       ["protection_group_id", "position_id", "authorization_id", "regular_order_id",
        "algo_order_id", "state", "trigger_price_ticks", "working_type", "price_protect",
        "covered_qty_steps", "deadline_us", "raw_evidence", "reconciliation"],
       {"state": ["REQUESTED", "ACKNOWLEDGED", "ARMED", "TRIGGERING", "TRIGGERED", "FINISHED",
                  "REJECTED", "EXPIRED", "CANCELED", "DEGRADED"]}),

    _c("triad.outcome.v2", "2.0.0", "triad-e10", ["learning", "governance"], ["OUTCOME"], True,
       ["campaign_id", "campaign_state", "fills", "quantity_conservation", "gross_pnl", "fees",
        "rebates", "funding", "liquidation_adl_cost", "emergency_cost", "net_pnl", "mae", "mfe",
        "markouts", "duration_us", "capsule_attribution", "arm_attribution", "regime_attribution",
        "valuation_evidence", "concentration_unit", "reconciliation_state"],
       {"campaign_state": ["OPEN", "CLOSING", "COMPLETED", "UNRESOLVED"]}),

    _c("triad.trial_registration.v1", "1.0.0", "governance-evidence",
       ["replay", "analysis", "promotion"], ["TRIAL_REGISTRATION"], False,
       ["trial_id", "family_id", "hypothesis", "formula", "parameters", "data_revisions",
        "symbols", "sides", "timeframes", "regimes", "entry_model", "exit_model", "cost_model",
        "fill_model", "sample_unit", "split", "purge", "embargo", "primary_metric",
        "multiplicity_family", "power_sample_rule", "promotion_threshold", "demotion_threshold",
        "frozen_at_us", "owner", "signature", "result_access_audit"]),

    _c("triad.divergence_record.v1", "1.0.0", "edge-comparator", ["learning", "promotion"],
       ["DIVERGENCE"], True,
       ["divergence_id", "input_offset", "control_candidate_id", "treatment_candidate_id",
        "divergence_class", "detail", "control_ref", "treatment_ref", "evaluated_at_us"],
       {"divergence_class": ["MISSING", "EXTRA", "RETIMED", "REIDENTIFIED", "GEOMETRY", "LIFECYCLE",
                            "QUALITY", "DOWNSTREAM_ELIGIBILITY"]}),

    _c("triad.producer_lease.v1", "1.0.0", "lease-coordinator", ["all-authority-consumers"],
       ["LEASE"], False,
       ["lease_id", "authoritative_topic", "scope", "producer_service", "producer_instance_id",
        "fencing_token", "issued_at_us", "not_before_us", "expires_at_us", "revoked_at_us",
        "activation_manifest_id", "issuer", "state", "signature"],
       {"state": ["ISSUED", "ACTIVE", "REVOKED", "EXPIRED", "SUPERSEDED"]}),

    _c("triad.engine_attestation.v1", "1.0.0", "every-producer", ["consumers", "operations"],
       ["ATTESTATION"], True,
       ["contract_bundle_version", "contract_manifest_sha256", "config_bundle_sha256",
        "risk_policy_sha", "build_commit", "artifact_sha256", "parameter_set_id",
        "parameter_digest", "instrument_map_digest", "fee_model_id", "universe_digest",
        "activation_manifest_id", "producer_epoch", "environment", "host_identity",
        "startup_receipt_id"]),

    _c("triad.service_heartbeat.v1", "1.0.0", "every-producer", ["health-controller"],
       ["HEARTBEAT"], True,
       ["service_id", "partition_offsets", "watermark", "warmup_status", "quality", "lease_state",
        "side_effect_capability"]),

    _c("triad.contract_bundle.manifest.v1", "1.0.0", "contract-governance", ["every-service"],
       ["CONTRACT_BUNDLE_MANIFEST"], False,
       ["bundle_version", "artifacts", "canonical_manifest_hash"]),

    # RC4 supersession: C-027 activation_manifest.v1 is replaced by engine_control_manifest.v2
    # with exact lever enums; v1 bytes stay frozen for compatibility evidence.
    _c("triad.activation_manifest.v1", "1.0.0", "release-governance", ["every-service"],
       ["ACTIVATION_MANIFEST"], False,
       ["activation_manifest_id", "build_commit", "artifact_sha256", "contract_manifest_sha256",
        "config_bundle_sha256", "services", "topic_bindings", "capsules", "symbols", "sides",
        "timeframes", "experiment_arm", "allocation", "account_id", "risk_cell",
        "permitted_authority", "lease_scope", "limits_ref", "policy_ref", "start_us", "expiry_us",
        "approvals", "rollback_manifest_id", "allow_money_publish"],
       superseded_by="triad.engine_control_manifest.v2"),

    _c("triad.compatibility_manifest.v1", "1.0.0", "contract-governance",
       ["bridges", "consumers"], ["COMPATIBILITY_MANIFEST"], False,
       ["manifest_id", "contract_id", "allowed_readers", "allowed_writers", "transformations",
        "non_material_fields", "sunset_gate"]),

    _c("triad.quarantine_record.v1", "1.0.0", "contract-boundary", ["owner", "operations"],
       ["QUARANTINE"], True,
       ["quarantine_id", "source", "boundary", "raw_reference", "rejection_reason", "contract_id",
        "observed_at_us"]),

    _c("triad.replay_receipt.v1", "1.0.0", "replay-runner", ["governance", "evidence"],
       ["REPLAY_RECEIPT"], False,
       ["receipt_id", "input_segment_hashes", "input_offsets", "fidelity_class", "build_commit",
        "config_bundle_sha256", "contract_manifest_sha256", "parameter_digest", "instrument_digest",
        "checkpoint_identity", "run_seed", "platform", "output_segment_hashes", "state_checksums",
        "test_suite_result", "divergence_links", "signer"]),

    # ---------------------------------------------------------------- B01 additions (G0 / RC4 L2)
    # RC4 lever law: exact enums, no aliases, no coercion. Valid golden uses the TESTNET/LIVE
    # combination (lawful without a promotion receipt); invalid golden is the OFF+LIVE semantic
    # refusal OFF_WITH_LIVE_VENUE_ACTIVATION — schema-valid, semantically rejected.
    _c("triad.engine_control_manifest.v2", "2.0.0", "governance-configuration",
       ["every-service", "lever-resolver"], ["ENGINE_CONTROL_MANIFEST"], False,
       ["control_manifest_id", "engine_id", "revision", "scope", "venue_environment",
        "venue_activation", "paper_activation", "shadow_activation", "activations",
        "registry_digest", "strategy_digest", "adapter_digest", "parameter_digest",
        "venue_binding", "account_binding", "route_binding", "credential_fingerprint_sha256",
        "issued_at_us", "expires_at_us", "testnet_promotion_receipt", "signatures"],
       {"venue_environment": ["LIVE", "TESTNET", "OFF"],
        "venue_activation": ["LIVE", "OFF"],
        "paper_activation": ["LIVE", "OFF"],
        "shadow_activation": ["LIVE"]},
       payload_overrides={"venue_environment": "TESTNET", "venue_activation": "LIVE",
                          "paper_activation": "OFF",
                          "activations": {"origin.candidate_publisher": "OFF"},
                          "scope": {"engine_id": "triad-origin-e02",
                                    "instruments": ["BTCUSDT.binance-usdm"]}},
       invalid_payload_overrides={"venue_environment": "OFF", "venue_activation": "LIVE"}),

    _c("triad.runtime_lever_registry.v1", "1.0.0", "governance-configuration",
       ["every-service", "lever-resolver"], ["RUNTIME_LEVER_REGISTRY"], False,
       ["registry_id", "revision", "levers", "registry_digest"]),

    _c("triad.runtime_lever_attestation.v1", "1.0.0", "every-runtime-instance",
       ["operations", "audit"], ["RUNTIME_LEVER_ATTESTATION"], True,
       ["attestation_id", "engine_id", "accepted_manifest_digest_sha256", "accepted_revision",
        "venue_environment", "venue_activation", "paper_activation", "shadow_activation",
        "process_identity", "route_proof", "account_proof", "lease_epoch", "health",
        "attested_at_us", "freshness_age_ms"],
       {"venue_environment": ["LIVE", "TESTNET", "OFF"],
        "venue_activation": ["LIVE", "OFF"],
        "paper_activation": ["LIVE", "OFF"],
        "shadow_activation": ["LIVE"]},
       payload_overrides={"venue_environment": "OFF", "venue_activation": "OFF",
                          "paper_activation": "OFF"}),

    # RC4 shadow law: every rejected shadow-tradeable candidate produces a durable disposition.
    _c("triad.shadow_trade.v1", "1.0.0", "origin-shadow-recorder",
       ["shadow-resolver", "learning", "audit"], ["SHADOW_TRADE"], True,
       ["shadow_trade_id", "candidate_id", "hypothesis_id", "frozen_at_us", "origin_disposition",
        "rejection_stage", "rejection_reason", "population", "shadow_activation",
        "market_watermark", "proposed_geometry", "evaluation_notional_quote",
        "simulator_version", "resolver_version", "cost_model_version", "event_time_us",
        "recorded_time_us", "fill_model_result", "terminal_outcome"],
       {"origin_disposition": ["REJECTED", "ACCEPTED_NOT_EXECUTED", "PROVEN_NO_VENUE_EFFECT"],
        "population": ["SHADOW"], "shadow_activation": ["LIVE"]},
       forbidden=["venue_order_id", "venue_trade_id", "account_id", "raw_credentials"]),

    # Never fabricates geometry: an untradeable input is recorded WITHOUT entry/stop/target.
    _c("triad.shadow_rejection_audit.v1", "1.0.0", "origin-candidate-guards",
       ["owner", "operations"], ["SHADOW_REJECTION_AUDIT"], True,
       ["audit_id", "attempt_identity", "raw_source_evidence", "validation_failure", "marker",
        "observed_at_us"],
       {"marker": ["SHADOW_UNTRADEABLE"]},
       forbidden=["entry_ticks", "stop_ticks", "target_ticks", "proposed_geometry",
                  "entry_reference_ticks", "natural_invalidation_ticks", "targets"]),

    # PAPER is a virtual demo plane: full virtual lineage, no venue identity, ever.
    _c("triad.paper_trade.v1", "1.0.0", "paper-demo-executor",
       ["learning", "audit"], ["PAPER_TRADE"], True,
       ["paper_trade_id", "candidate_id", "population", "activation_revision",
        "virtual_account_id", "virtual_balance_quote", "virtual_order", "virtual_fill",
        "virtual_position", "virtual_outcome", "market_watermark", "event_time_us",
        "recorded_time_us"],
       {"population": ["PAPER"]},
       forbidden=["venue", "venue_order_id", "venue_trade_id", "account_id", "raw_credentials"]),

    _c("triad.shadow_health.v1", "1.0.0", "origin-shadow-recorder",
       ["operations", "health-controller"], ["SHADOW_HEALTH"], True,
       ["writer_heartbeat_us", "rejection_persist_latency_ms", "backlog_watermark_us",
        "resolver_lag_ms", "dedupe_count", "collision_count", "coverage",
        "contamination_count"]),

    # RC4: E08 authorization v3 names exact environment, activation revision, lease epoch, scope.
    _c("triad.execution_authorization.v3", "3.0.0", "triad-e08", ["e09-orchestrator"],
       ["EXECUTION_AUTHORIZATION"], True,
       ["candidate_id", "decision_id", "risk_decision_id", "reservation_id", "account_id",
        "canonical_instrument_id", "direction", "position_effect", "max_qty_steps",
        "max_notional_quote", "entry_geometry", "invalidation_geometry", "target_geometry",
        "allowed_liquidity", "allowed_tif", "allowed_order_roles", "protection_deadline_us",
        "protection_budget", "valid_until_us", "venue_environment", "venue_activation_revision",
        "lease_epoch", "scope"],
       {"direction": DIRECTION,
        "position_effect": ["OPEN", "INCREASE", "REDUCE", "CLOSE", "REVERSE"],
        "venue_environment": ["LIVE", "TESTNET"]}),

    # RC3 receipt_v2_requirements: strict evidence/task/gate receipts (PASS is conditional).
    _c("triad.evidence_receipt.v2", "2.0.0", "governance-evidence", ["governance", "audit"],
       ["EVIDENCE_RECEIPT"], False,
       ["receipt_id", "scope", "result", "evidence_ids", "evidence_sha256s", "observed_at_us",
        "expires_at_us", "producer_digests", "builder", "reviewer", "signature"],
       {"result": ["PASS", "FAIL", "BLOCKED"]},
       payload_overrides={"result": "PASS",
                          "scope": {"milestone": "B00"},
                          "evidence_ids": ["ev-1"],
                          "evidence_sha256s": ["0" * 64],
                          "observed_at_us": 1786156800123456,
                          "expires_at_us": 1786243200123456,
                          "builder": "builder-a", "reviewer": "reviewer-b",
                          "signature": "sig-1"},
       invalid_payload_overrides={"result": "PASS", "builder": "same-actor",
                                  "reviewer": "same-actor"}),

    _c("triad.task_status_event.v2", "2.0.0", "governance-evidence", ["governance", "audit"],
       ["TASK_STATUS_EVENT"], False,
       ["task_id", "gate", "from_status", "to_status", "predecessor_receipt_ids",
        "acceptance_receipt_ids", "verification_receipt_ids", "scope", "transitioned_at_us",
        "actor", "signature"],
       {"from_status": ["NOT_STARTED", "IN_PROGRESS", "BLOCKED", "PASS", "FAIL"],
        "to_status": ["NOT_STARTED", "IN_PROGRESS", "BLOCKED", "PASS", "FAIL"]},
       payload_overrides={"from_status": "IN_PROGRESS", "to_status": "PASS",
                          "acceptance_receipt_ids": ["acc-1"],
                          "verification_receipt_ids": ["ver-1"],
                          "signature": "sig-1"},
       invalid_payload_overrides={"from_status": "IN_PROGRESS", "to_status": "PASS",
                                  "acceptance_receipt_ids": [],
                                  "verification_receipt_ids": []}),

    _c("triad.gate_receipt.v2", "2.0.0", "governance-evidence", ["governance", "audit"],
       ["GATE_RECEIPT"], False,
       ["gate", "scope", "result", "predecessor_gate_receipt_id", "task_receipt_ids",
        "verification_receipt_ids", "open_blockers", "rollback_proof_ids", "producer_digests",
        "observed_at_us", "expires_at_us", "approver", "signature"],
       {"result": ["READY", "PASS", "FAIL", "BLOCKED"]},
       payload_overrides={"result": "PASS", "task_receipt_ids": ["t-1"],
                          "verification_receipt_ids": ["v-1"],
                          "rollback_proof_ids": ["r-1"], "open_blockers": [],
                          "approver": "approver-a", "signature": "sig-1"},
       invalid_payload_overrides={"result": "PASS", "open_blockers": ["BLK-1"],
                                  "task_receipt_ids": ["t-1"],
                                  "verification_receipt_ids": ["v-1"]}),

    # CTRL-B01-002 / BLK-RC2-016: attestation v2 — payload identity fields MUST equal their
    # envelope twins (the semantic equality law); valid golden satisfies it by construction,
    # invalid golden carries one mismatched digest.
    _c("triad.engine_attestation.v2", "2.0.0", "every-producer", ["consumers", "operations"],
       ["ATTESTATION"], True,
       ["contract_bundle_version", "contract_manifest_sha256", "config_bundle_sha256",
        "risk_policy_sha", "build_commit", "artifact_sha256", "parameter_set_id",
        "parameter_digest", "instrument_map_digest", "fee_model_id", "universe_digest",
        "activation_manifest_id", "producer_epoch", "environment", "host_identity",
        "startup_receipt_id", "identity_equality_version"],
       {"environment": ["LIVE", "TESTNET", "OFF"],
        "identity_equality_version": ["attestation-equality/1"]},
       payload_overrides={"contract_manifest_sha256": "1" * 64,
                          "config_bundle_sha256": "2" * 64,
                          "build_commit": "0000000000000000000000000000000000000000",
                          "artifact_sha256": "3" * 64,
                          "producer_epoch": "42",
                          "environment": "OFF"},
       invalid_payload_overrides={"contract_manifest_sha256": "f" * 64,
                                  "config_bundle_sha256": "2" * 64,
                                  "build_commit": "0000000000000000000000000000000000000000",
                                  "artifact_sha256": "3" * 64,
                                  "producer_epoch": "42"}),
]


# --- type heuristics -----------------------------------------------------------------------------
_TICK_SUFFIXES = ("_ticks", "_steps", "_atomic", "_minor", "_quote")
_INT_US = ("_us",)
_NS = ("_ns",)
_HEX = ("_sha256", "_hash", "_digest")
_BOOL = {"watermark_complete", "post_only", "reduce_only", "close_position", "price_protect",
         "tier2_market_permitted", "allow_money_publish"}
_ARRAY = {"levers", "signatures", "evidence_ids", "evidence_sha256s",
          "predecessor_receipt_ids", "acceptance_receipt_ids", "verification_receipt_ids",
          "task_receipt_ids", "rollback_proof_ids", "open_blockers",
          "source_offset_range", "dependency_event_ids", "origin_source_ids",
          "confirmation_source_ids", "reference_level_ids", "predecessor_structure_ids",
          "source_event_ids", "reference_ids", "fresh_flow_atom_ids", "targets", "target_ticks",
          "linked_execution_ids", "allowed_liquidity", "allowed_tif", "allowed_order_roles",
          "clause_results", "clause_evaluations", "arbitration_set", "economic_assumption_refs",
          "cancellation_causes", "cancellation_conditions", "prerequisites", "artifacts",
          "services", "capsules", "symbols", "sides", "timeframes", "regimes", "data_revisions",
          "approvals", "allowed_readers", "allowed_writers", "transformations",
          "non_material_fields", "fills", "markouts", "input_segment_hashes", "input_offsets",
          "output_segment_hashes", "divergence_links", "venue_sequences"}
_OBJECT = {"activations", "venue_binding", "account_binding", "route_binding",
           "testnet_promotion_receipt", "process_identity", "route_proof", "account_proof",
           "health", "market_watermark", "proposed_geometry", "fill_model_result",
           "terminal_outcome", "attempt_identity", "raw_source_evidence", "virtual_order",
           "virtual_fill", "virtual_position", "virtual_outcome", "producer_digests",
           "coverage",
           "partition_key", "original_geometry", "current_geometry", "entry_geometry",
           "invalidation_geometry", "target_geometry", "quality", "quality_snapshot",
           "dependency_quality", "dependency_ranges", "dependency_clocks", "feature_values",
           "location_result", "departure_result", "trigger_result", "confirmation_result",
           "conversion_evidence", "position_effect_derivation_evidence", "role_derivation_evidence",
           "conservation_proof", "quantity_conservation", "valuation_evidence",
           "capsule_attribution", "arm_attribution", "regime_attribution", "raw_payload",
           "normalized_payload", "canonical_mapping", "venue_ids", "raw_evidence", "reconciliation",
           "scope", "topic_bindings", "allocation", "protection_requirements", "state_checksums",
           "test_suite_result", "trigger", "evidence", "book_sequence_state",
           "bar_finalization_state", "partition_offsets", "watermark"}
_DECIMAL_UINT_FIELDS = {"producer_epoch", "fencing_token", "state_seq", "geometry_revision",
                        "connection_epoch", "receive_sequence", "instrument_metadata_revision",
                        "instrument_revision", "first_touch_ordinal", "rr_numerator",
                        "rr_denominator", "retry_budget", "horizon",
                        "revision", "accepted_revision", "activation_revision",
                        "venue_activation_revision", "lease_epoch",
                        "rejection_persist_latency_ms", "resolver_lag_ms", "freshness_age_ms",
                        "dedupe_count", "collision_count", "contamination_count"}


def _field_schema(name: str, enums: dict) -> dict:
    if name in enums:
        return {"type": "string", "enum": list(enums[name])}
    if name in _BOOL:
        return {"type": "boolean"}
    if name in _ARRAY:
        return {"type": "array"}
    if name in _OBJECT:
        return {"type": "object"}
    if name in _DECIMAL_UINT_FIELDS:
        return {"type": "string", "pattern": DECIMAL_UINT}
    if name.endswith(_TICK_SUFFIXES) or name in (
        "reserved_amount", "max_notional_quote", "base_value", "gross_pnl", "net_pnl", "fees",
        "rebates", "funding", "mae", "mfe", "realized_value", "unrealized_value",
        "worst_acceptable_price_ticks"):
        return {"type": "string", "pattern": SIGNED_INT}
    if name.endswith(_NS):
        return {"type": "string", "pattern": SIGNED_INT}
    if name.endswith(_INT_US):
        return {"type": "integer"}
    if name.endswith(_HEX):
        return {"type": "string", "pattern": HEX64}
    return {"type": "string"}


def _sample_for(fs: dict):
    t = fs.get("type")
    if "enum" in fs:
        return fs["enum"][0]
    if t == "boolean":
        return True
    if t == "array":
        return []
    if t == "object":
        return {}
    if t == "integer":
        return 1786156800123456
    if t == "string":
        p = fs.get("pattern")
        if p == HEX64:
            return "0" * 64
        if p == DECIMAL_UINT:
            return "1"
        if p == SIGNED_INT:
            return "0"
        return "x"
    return "x"


def build_schema(c: dict) -> dict:
    props: dict[str, dict] = {
        "schema": {"const": c["id"]},
        "schema_version": {"const": c["version"]},
        "event_id": {"type": "string", "minLength": 1},
        "event_kind": {"type": "string", "enum": list(c["event_kinds"])},
        "producer_service": {"type": "string", "minLength": 1},
        "producer_instance_id": {"type": "string", "minLength": 1},
        "producer_epoch": {"type": "string", "pattern": DECIMAL_UINT},
        "emitted_at_us": {"type": "integer"},
        "contract_manifest_sha256": {"type": "string", "pattern": HEX64},
        "config_bundle_sha256": {"type": "string", "pattern": HEX64},
        "build_commit": {"type": "string", "minLength": 1},
        "artifact_sha256": {"type": "string", "pattern": HEX64},
        "activation_manifest_id": {"type": "string"},
        "traceparent": {"type": "string"},
        "correlation_id": {"type": "string"},
    }
    payload_props: dict[str, dict] = {}
    for f in c["required"]:
        payload_props[f] = _field_schema(f, c["enums"])
    for f in c["forbidden"]:
        payload_props[f] = False  # presence of a forbidden key fails validation
    payload = {
        "type": "object",
        "required": list(c["required"]),
        "properties": payload_props,
        "additionalProperties": True,  # additive minor fields preserved (Doc 03 compatibility)
    }
    props["payload"] = payload
    required = list(ENVELOPE_REQUIRED)
    if c["authority"]:
        required.append("producer_epoch")
    return {
        "$schema": DRAFT,
        "$id": f"https://triad.origin.v7/contracts/{c['id']}.schema.json",
        "title": c["id"],
        "type": "object",
        "required": sorted(required),
        "properties": props,
        "additionalProperties": False,
    }


def build_valid(c: dict, schema: dict) -> dict:
    env: dict = {
        "schema": c["id"],
        "schema_version": c["version"],
        "event_id": f"evt_{c['id'].replace('.', '_')}",
        "event_kind": c["event_kinds"][0],
        "producer_service": c["producer"],
        "producer_instance_id": "inst_golden_01",
        "emitted_at_us": 1786156800123456,
        "contract_manifest_sha256": "1" * 64,
        "config_bundle_sha256": "2" * 64,
        "build_commit": "0000000000000000000000000000000000000000",
        "artifact_sha256": "3" * 64,
    }
    if c["authority"]:
        env["producer_epoch"] = "42"
    payload = {}
    for f in c["required"]:
        payload[f] = _sample_for(_field_schema(f, c["enums"]))
    payload.update(c.get("payload_overrides", {}))
    env["payload"] = payload
    return env


def build_invalid(c: dict) -> dict:
    """A golden invalid vector.

    Default: drop the first required payload field. Contracts with a semantic (cross-field) law
    instead supply ``invalid_payload_overrides`` — a schema-valid payload that violates the
    semantic law, so the invalid golden proves the semantic validator, not just JSON Schema.
    """
    v = build_valid(c, {})
    if c.get("invalid_payload_overrides"):
        v["payload"].update(c["invalid_payload_overrides"])
        return v
    dropped = c["required"][0]
    v["payload"].pop(dropped, None)
    v["_invalid_reason"] = f"missing required payload field: {dropped}"
    # _invalid_reason is at top level where additionalProperties is False, so it also fails —
    # but the primary defect under test is the missing required field. Remove it to keep the
    # vector clean and let the missing-field be the sole cause.
    v.pop("_invalid_reason", None)
    return v


def _write_json(path: pathlib.Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")


def main() -> None:
    index = {
        "identity_schema_version": "origin.identity.v1",
        "identity_schema_versions": ["origin.identity.v1", "origin.identity.v2"],
        "contracts": [],
    }
    for c in CONTRACTS:
        schema = build_schema(c)
        _write_json(SCHEMA_DIR / f"{c['id']}.schema.json", schema)
        _write_json(GOLDEN_DIR / c["id"] / "valid.json", build_valid(c, schema))
        _write_json(GOLDEN_DIR / c["id"] / "invalid.json", build_invalid(c))
        entry = {
            "contract_id": c["id"],
            "schema_version": c["version"],
            "producer": c["producer"],
            "consumers": c["consumers"],
            "authority_fenced": c["authority"],
            "schema_path": f"contracts/schemas/{c['id']}.schema.json",
        }
        if c.get("superseded_by"):
            entry["superseded_by"] = c["superseded_by"]
        index["contracts"].append(entry)
    _write_json(REGISTRY_DIR / "index.json", index)
    print(f"generated {len(CONTRACTS)} contracts + golden vectors + registry index")


if __name__ == "__main__":
    main()
