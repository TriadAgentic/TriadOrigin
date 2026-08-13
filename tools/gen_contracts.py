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
       superseded_by=None, payload_field_schemas=None, payload_additional=None,
       schema_extra=None, registry_extra=None):
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
        # CO-03: exact per-field payload subschemas (nested objects with required members, typed
        # arrays, bounded integers) that the name-suffix heuristics cannot express. Every field
        # named here MUST also carry a payload_overrides sample (asserted in main()) so the golden
        # valid vector is built from an explicit value, never a heuristic guess.
        "payload_field_schemas": payload_field_schemas or {},
        # CO-03 stop rule: a CONTRACT_RATIFICATION_REQUIRED stub closes its payload
        # (additionalProperties false) so no body can be smuggled under a reserved name before
        # the owner-signed topology decision lands. None keeps the Doc 03 additive default (True).
        "payload_additional": payload_additional,
        # Extra top-level JSON Schema annotations ("x-status", "description"); merged verbatim.
        "schema_extra": schema_extra or {},
        # Extra registry-entry annotations (e.g. x_status: CONTRACT_RATIFICATION_REQUIRED).
        "registry_extra": registry_extra or {},
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
                          # B00C gate-receipt law: exact non-wildcard scope, real digests,
                          # a positive validity window, and an approver independent of the
                          # producing service.
                          "scope": {"gate": "G0", "repository": "TriadAgentic/TriadOrigin"},
                          "producer_digests": {"contract_manifest": "4" * 64},
                          "observed_at_us": 1786156800123456,
                          "expires_at_us": 1786243200123456,
                          "approver": "approver-a", "signature": "sig-1"},
       invalid_payload_overrides={"result": "PASS", "open_blockers": ["BLK-1"],
                                  "task_receipt_ids": ["t-1"],
                                  "verification_receipt_ids": ["v-1"]}),

    # B01R / reconciled plan §6: binding.v2 — one formula-parameter binding row with semantic
    # slot, cardinality, condition, scope, precedence, consuming node/edge, and digest identity.
    # Structural migration NEVER activates a row: the source status is preserved verbatim and a
    # blocked binding is not consumable (enforced by triad_origin.bindings + the semantic law).
    _c("triad.binding.v2", "2.0.0", "contract-governance", ["origin", "governance", "audit"],
       ["BINDING_RECORD"], False,
       ["binding_id", "semantic_slot", "formula_id", "parameter_id", "parameter_name",
        "declared_value", "unit", "unit_contract", "cardinality", "condition",
        "activation_scope", "precedence", "consumer", "consuming_wiring_ids", "gate",
        "status", "lifecycle_status", "migration_state", "failure_behavior", "boundary_rule",
        "operation_id", "source_binding_id", "superseded_by", "disposition_reason",
        "binding_digest"],
       {"cardinality": ["EXACTLY_ONE", "UNRESOLVED_BLOCKING"],
        "status": ["ACTIVE", "BLOCKED", "BLOCKED_BINDING_V2_MIGRATION"],
        "lifecycle_status": ["ACTIVE", "BLOCKED"],
        "migration_state": ["NOT_APPLICABLE", "BLOCKED_NOT_STARTED"]},
       payload_overrides={
           "binding_id": "FPB-0001", "semantic_slot": "ingress_price_wire_integer_ticks",
           "formula_id": "F00", "parameter_id": "PAR-001", "parameter_name": "PRICE_WIRE_TYPE",
           "declared_value": "price_ticks=exact_div(venue_price,tick_size)", "unit": "tick",
           "unit_contract": "exact decimal venue price / exact tick_size -> signed int64 ticks",
           "cardinality": "EXACTLY_ONE",
           "condition": "accepted venue price parse under exact metadata revision",
           "activation_scope": "E01;G1;venue/instrument/metadata-revision exact scope",
           "precedence": "AT_INGRESS_BEFORE_CANONICAL_EVENT_PUBLICATION",
           "consumer": "E01", "consuming_wiring_ids": "W01", "gate": "G1",
           "status": "ACTIVE", "lifecycle_status": "ACTIVE", "migration_state": "NOT_APPLICABLE",
           "failure_behavior": "QUARANTINE_INGRESS_EVENT", "boundary_rule": "nonzero remainder quarantines",
           "operation_id": "RC3-BOP-010", "source_binding_id": "FPB-0001",
           "superseded_by": "", "disposition_reason": "",
           "binding_digest": "__BINDING_DIGEST__"},
       # Invalid golden: claims ACTIVE while cardinality is unresolved — the migration-activation
       # confusion the semantic law exists to refuse.
       invalid_payload_overrides={"status": "ACTIVE", "lifecycle_status": "ACTIVE",
                                  "cardinality": "UNRESOLVED_BLOCKING",
                                  "migration_state": "BLOCKED_NOT_STARTED"}),

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

    # ---------------------------------------------------------------- B07 additions
    # RC3 W09 (rc3_effective_control_bundle task[114..145,636]) + rc3_normative_overlay
    # wiring_only_contracts: the externally issued governance-lease fact that names which
    # engine_cohort is the SELECTED producer for a candidate-publishing scope. ORIGIN is
    # VERIFY-ONLY here (row A7 / CLAUDE.md BUILD_DARK_LIBRARY): authority_fact_verifier reads
    # and cross-checks this fact; it never issues, activates, or supersedes one. Shape mirrors
    # producer_lease.v1 (fencing_token/epoch/issued/expires/revoked/state/signature) plus the
    # W09-named telemetry: active epoch, expiry, renewal, allocation, conflicts (split-brain
    # evidence) and the two-axis selection (engine_cohort — mirrors RC3-WOP-001/002's
    # required_typing).
    _c("triad.candidate_authority.v1", "1.0.0", "governance-lease-issuer",
       ["origin-authority-fact-verifier", "comparator", "audit"], ["CANDIDATE_AUTHORITY"], False,
       ["authority_id", "authoritative_topic", "scope", "selected_engine_cohort",
        "fencing_token", "epoch", "issued_at_us", "not_before_us", "expires_at_us",
        "revoked_at_us", "renewed_at_us", "activation_manifest_id", "issuer", "state",
        "allocation", "conflicts", "signature"],
       {"selected_engine_cohort": ["ORIGIN_CANDIDATE", "LEGACY_COMPARATOR"],
        "state": ["ISSUED", "ACTIVE", "REVOKED", "EXPIRED", "SUPERSEDED"]}),
]

# ---------------------------------------------------------------- CO-03 additions (2026-08-12)
# TRIAD-ORIGIN-V7-CHANGE-ORDERS-2026-08-12 CO-03: the four contract-union majors, the transport
# registry, the E08->E09 venue execution plan, and the six E03-E06 advisory-chain stubs. All
# additive majors, all DARK (no producer emits any of them; registration activates nothing;
# posture stays OFF/OFF/OFF/LIVE, DENIED_SAFE_HOLD). The stubs are OWNER-GATED: OWNER-TOPO-01 is
# adjudicated (TRIAD-OWNER-TOPO-01-ADJUDICATION-2026-08-12) but NOT signed, so each stub carries
# ONLY its name + the required lineage/no-authority fields, is marked
# "x-status": "CONTRACT_RATIFICATION_REQUIRED", and CLOSES its payload — a body field is refused
# structurally until the signed CO-14 decision lands (the CO-03 stop rule).

_CO03_DARK_NOTE = (
    "Registered by CO-03 (TRIAD-ORIGIN-V7-CHANGE-ORDERS-2026-08-12) as an additive major. "
    "Registration activates no producer and grants no authority; posture unchanged "
    "OFF/OFF/OFF/LIVE, DENIED_SAFE_HOLD.")

_CO03_STUB_NOTE = (
    "RESERVED ADVISORY-CHAIN STUB (CO-03 step 7). PENDING_SIGNATURE: OWNER-TOPO-01 is "
    "adjudicated (2026-08-12) but NOT signed; per the CO-03 stop rule this schema carries ONLY "
    "the contract name plus the required lineage/no-authority fields "
    "(artifact/model/prompt/retrieval versions, uncertainty, calibration, freshness, citations, "
    "decision_authority const NONE). The payload is CLOSED (additionalProperties false): any "
    "body field is refused until the signed CO-14 topology decision lands. Consumers refuse "
    "with the named refusal CONTRACT_RATIFICATION_REQUIRED. E04 is excluded from the seam "
    "(OWNER-TOPO-01 Amendment A2): no E04 stub exists and none is authorized here. "
    + _CO03_DARK_NOTE)

_STUB_LINEAGE_REQUIRED = [
    "artifact_version", "model_version", "prompt_version", "retrieval_version",
    "uncertainty", "calibration", "freshness", "citations", "decision_authority",
]

_STUB_LINEAGE_SCHEMAS = {
    # An empty version string is not a lineage claim: every version field is non-empty.
    "artifact_version": {"type": "string", "minLength": 1},
    "model_version": {"type": "string", "minLength": 1},
    "prompt_version": {"type": "string", "minLength": 1},
    "retrieval_version": {"type": "string", "minLength": 1},
    "uncertainty": {"type": "object"},
    "calibration": {"type": "object"},
    "freshness": {"type": "object"},
    "citations": {"type": "array", "items": {"type": "string", "minLength": 1}},
}

_STUB_LINEAGE_SAMPLES = {
    "artifact_version": "x",
    "model_version": "x",
    "prompt_version": "x",
    "retrieval_version": "x",
    "uncertainty": {},
    "calibration": {},
    "freshness": {},
    "citations": [],
}


def _stub(schema_id, version, producer, consumers, event_kind):
    """A CO-03 step-7 reserved advisory-chain stub: names + lineage fields, nothing else."""
    return _c(
        schema_id, version, producer, consumers, [event_kind], False,
        list(_STUB_LINEAGE_REQUIRED),
        {"decision_authority": ["NONE"]},
        payload_field_schemas=dict(_STUB_LINEAGE_SCHEMAS),
        payload_overrides=dict(_STUB_LINEAGE_SAMPLES),
        # The stop-rule negative: a smuggled body field under a ratification-required stub is
        # refused by the closed payload (additionalProperties false) — by BOTH the full
        # validator and the stdlib diagnostic.
        invalid_payload_overrides={"body": {"smuggled": "x"}},
        payload_additional=False,
        schema_extra={"x-status": "CONTRACT_RATIFICATION_REQUIRED",
                      "description": _CO03_STUB_NOTE},
        registry_extra={"x_status": "CONTRACT_RATIFICATION_REQUIRED",
                        "x_change_order": "CO-03"},
    )


CONTRACTS += [
    # CO-03 step 1 — the B08 read-face envelope law, promoted to a schema. The seven-value
    # status enum is exact and closed; presence never reads as OK.
    _c("triad.evidence_view.v2", "2.0.0", "b08-read-face",
       ["operations", "governance", "audit"], ["EVIDENCE_VIEW"], False,
       ["source", "plane", "cohort", "scope", "producer_rev", "build_digest", "config_digest",
        "contract_digest", "binding_digest", "event_time", "observation_time", "freshness_ms",
        "completeness", "status", "payload"],
       {"status": ["OK", "UNAVAILABLE", "NOT_IMPLEMENTED", "TOOL_TIMEOUT", "NOT_MEASURABLE",
                   "STALE", "NOT_ATTESTED"]},
       payload_field_schemas={
           "source": {"type": "string", "minLength": 1},
           "plane": {"type": "string", "minLength": 1},
           "cohort": {"type": "string", "minLength": 1},
           "producer_rev": {"type": "string", "minLength": 1},
           "event_time": {"type": "integer"},
           "observation_time": {"type": "integer"},
           "freshness_ms": {"type": "string", "pattern": DECIMAL_UINT},
           "completeness": {"type": "string", "minLength": 1},
           "payload": {"type": "object"},
       },
       payload_overrides={
           "source": "b08-read-face", "plane": "governance", "cohort": "x-cohort",
           "producer_rev": "x-rev", "event_time": 1786156800123456,
           "observation_time": 1786156800123456, "freshness_ms": "0",
           "completeness": "COMPLETE", "payload": {},
       },
       # The envelope-law negative: a status outside the closed seven-value enum (e.g. the
       # presence-reads-as-closure word) is refused.
       invalid_payload_overrides={"status": "PRESENT"},
       schema_extra={"description": (
           "CO-03 step 1: the exact B08 read-face envelope law as a contract. status is the "
           "CLOSED seven-value truth vocabulary {OK, UNAVAILABLE, NOT_IMPLEMENTED, TOOL_TIMEOUT, "
           "NOT_MEASURABLE, STALE, NOT_ATTESTED}; an unavailable read is UNAVAILABLE, an "
           "unattested claim is NOT_ATTESTED — never a fabricated OK. " + _CO03_DARK_NOTE)}),

    # CO-03 step 2 — the E00 immutable, replayable venue fact with structural quarantine flags.
    _c("triad.raw_venue_event.v2", "2.0.0", "triad-e00", ["triad-e01", "raw-ledger", "replay"],
       ["RAW_VENUE_EVENT"], True,
       ["venue", "instrument_id", "route_id", "session_id", "source_sequence", "event_time",
        "receive_time", "payload_kind", "payload_bytes_digest", "metadata_revision",
        "quarantine_flags"],
       {"payload_kind": ["trade", "book_delta", "book_snapshot", "account", "order", "funding",
                         "mark"]},
       payload_field_schemas={
           "venue": {"type": "string", "minLength": 1},
           "instrument_id": {"type": "string", "minLength": 1},
           "route_id": {"type": "string", "minLength": 1},
           "session_id": {"type": "string", "minLength": 1},
           "source_sequence": {"type": "string", "pattern": DECIMAL_UINT},
           "event_time": {"type": "integer"},
           "receive_time": {"type": "integer"},
           "metadata_revision": {"type": "string", "pattern": DECIMAL_UINT},
           "quarantine_flags": {
               "type": "object",
               "required": ["gap", "clock", "dq"],
               "properties": {"gap": {"type": "boolean"}, "clock": {"type": "boolean"},
                              "dq": {"type": "boolean"}},
               "additionalProperties": False},
       },
       payload_overrides={
           "venue": "binance-usdm", "instrument_id": "x-instrument", "route_id": "x-route",
           "session_id": "x-session", "source_sequence": "1",
           "event_time": 1786156800123456, "receive_time": 1786156800123456,
           "metadata_revision": "1",
           "quarantine_flags": {"gap": False, "clock": False, "dq": False},
       },
       # Recursive negative: quarantine_flags missing its dq member (nested required violation).
       invalid_payload_overrides={"quarantine_flags": {"gap": False, "clock": False}},
       schema_extra={"description": (
           "CO-03 step 2: the E00 fact — immutable and replayable; quarantine flags for "
           "gap/clock/DQ are structural (all three booleans required, closed object). "
           + _CO03_DARK_NOTE)}),

    # CO-03 step 3 — process truth. deployment_class DARK is the gate-#12 deployment-class
    # vocabulary (legitimate post-RC4), NOT the retired RC4 connected-dark LEVER vocabulary and
    # NOT an activation-manifest plane value.
    _c("triad.runtime_lifecycle.v2", "2.0.0", "every-runtime-instance",
       ["operations", "audit", "deployment-registry"], ["RUNTIME_LIFECYCLE"], True,
       ["component_id", "deployment_class", "build_digest", "config_digest", "contract_digest",
        "binding_digest", "lease", "attestation_time", "plane_bindings"],
       {"deployment_class": ["ACTIVE_WRITER", "REPLICA", "MIRROR", "DARK", "RETIRED"]},
       payload_field_schemas={
           "component_id": {"type": "string", "minLength": 1},
           "lease": {
               "type": "object",
               "required": ["topic", "epoch", "ttl"],
               "properties": {"topic": {"type": "string", "minLength": 1},
                              "epoch": {"type": "string", "pattern": DECIMAL_UINT},
                              "ttl": {"type": "string", "pattern": DECIMAL_UINT}},
               "additionalProperties": False},
           "attestation_time": {"type": "integer"},
           "plane_bindings": {"type": "object"},
       },
       payload_overrides={
           "component_id": "x-component",
           "deployment_class": "DARK",
           "lease": {"topic": "x-topic", "epoch": "1", "ttl": "1"},
           "attestation_time": 1786156800123456,
           "plane_bindings": {},
       },
       # Recursive negative: lease missing its epoch member (nested required violation).
       invalid_payload_overrides={"lease": {"topic": "x-topic", "ttl": "1"}},
       schema_extra={"description": (
           "CO-03 step 3: runtime process truth — deployment class, build/config/contract/"
           "binding digests, lease{topic, epoch, ttl}, attestation time, plane bindings. "
           "deployment_class DARK is the deployment-class vocabulary (closure gate #12), not "
           "the retired RC4 connected-dark lever vocabulary. " + _CO03_DARK_NOTE)}),

    # CO-03 step 4 — Learning's advisory output, hard-split from outcome.*: decision_authority
    # is const NONE; consumers may read, never auto-apply.
    _c("triad.signed_recommendation.v1", "1.0.0", "triad-e10-learning",
       ["governance", "owner", "audit"], ["SIGNED_RECOMMENDATION"], False,
       ["recommendation_id", "subject_scope", "evidence_refs", "proposal", "decision_authority",
        "signer", "signature", "valid_to"],
       {"decision_authority": ["NONE"]},
       payload_field_schemas={
           "recommendation_id": {"type": "string", "minLength": 1},
           "subject_scope": {"type": "object"},
           "evidence_refs": {"type": "array", "items": {"type": "string", "minLength": 1}},
           "proposal": {"type": "object"},
           "signer": {"type": "string", "minLength": 1},
           "signature": {"type": "string", "minLength": 1},
           "valid_to": {"type": "integer"},
       },
       payload_overrides={
           "recommendation_id": "rec-x", "subject_scope": {}, "evidence_refs": ["ev-1"],
           "proposal": {}, "signer": "x-signer", "signature": "sig-1",
           "valid_to": 1786243200123456,
       },
       # The constitutional negative: any decision_authority other than NONE is refused.
       invalid_payload_overrides={"decision_authority": "FULL"},
       schema_extra={"description": (
           "CO-03 step 4: Learning's advisory output, hard-split from outcome.*. "
           "decision_authority is const NONE — consumers may read, never auto-apply. "
           + _CO03_DARK_NOTE)}),

    # CO-03 step 5 — the single owner of exact transports per logical topic. An unknown binding
    # resolves to the NAMED refusal TRANSPORT_BINDING_UNKNOWN, never a silent default.
    _c("triad.transport_bindings.v1", "1.0.0", "contract-governance", ["every-service"],
       ["TRANSPORT_BINDINGS"], False,
       ["bindings_id", "revision", "bindings", "unknown_binding_refusal", "bindings_digest"],
       {"unknown_binding_refusal": ["TRANSPORT_BINDING_UNKNOWN"]},
       payload_field_schemas={
           "bindings_id": {"type": "string", "minLength": 1},
           "bindings": {
               "type": "array",
               "minItems": 1,
               "items": {
                   "type": "object",
                   "required": ["logical_topic", "transport_kind", "exact_binding", "owner"],
                   "properties": {
                       "logical_topic": {"type": "string", "minLength": 1},
                       "transport_kind": {"type": "string",
                                          "enum": ["TOPIC", "FILENAME", "DATABASE_PATH",
                                                   "OBJECT_PATH"]},
                       "exact_binding": {"type": "string", "minLength": 1},
                       "owner": {"type": "string", "minLength": 1},
                       "consumers": {"type": "array",
                                     "items": {"type": "string", "minLength": 1}}},
                   "additionalProperties": False}},
       },
       payload_overrides={
           "bindings_id": "x-bindings",
           "bindings": [{"logical_topic": "x.logical", "transport_kind": "TOPIC",
                         "exact_binding": "x.exact", "owner": "x-owner",
                         "consumers": ["x-consumer"]}],
       },
       # The named-refusal negative: a silent-default token in place of the named refusal.
       invalid_payload_overrides={"unknown_binding_refusal": "SILENT_DEFAULT"},
       schema_extra={"description": (
           "CO-03 step 5: the SINGLE owner of exact topics, filenames, database paths and "
           "object paths per logical topic in the wiring matrix. Producers/consumers resolve "
           "transport only through this registry; an unknown binding yields the named refusal "
           "TRANSPORT_BINDING_UNKNOWN (const), never a silent default. Golden vectors carry "
           "placeholder rows only — no live wiring truth is declared here. " + _CO03_DARK_NOTE)}),

    # CO-03 step 6 — VenueExecutionPlan.v1 (repo grammar: triad.venue_execution_plan.v1), the
    # E08->E09 plan required by F21/C-006, field-complete for GV-018's variants.
    _c("triad.venue_execution_plan.v1", "1.0.0", "triad-e08", ["e09-orchestrator", "audit"],
       ["VENUE_EXECUTION_PLAN"], True,
       ["authorization_ref", "economic_purpose", "side", "instrument_id", "account_mode",
        "zone", "observed_book", "ordinal_budget", "reprice_budget", "ttl_ms",
        "price_filters", "price_bands", "idempotency_key_law", "refusal_codes"],
       {"side": ["BUY", "SELL"]},
       payload_field_schemas={
           "authorization_ref": {"type": "string", "minLength": 1},
           "economic_purpose": {"type": "string", "minLength": 1},
           "instrument_id": {"type": "string", "minLength": 1},
           "account_mode": {"type": "string", "minLength": 1},
           "zone": {
               "type": "object",
               "required": ["z0", "z1"],
               "properties": {"z0": {"type": "string", "pattern": SIGNED_INT},
                              "z1": {"type": "string", "pattern": SIGNED_INT}},
               "additionalProperties": False},
           "observed_book": {
               "type": "object",
               "required": ["revision", "levels"],
               "properties": {
                   "revision": {"type": "string", "pattern": DECIMAL_UINT},
                   "levels": {
                       "type": "array",
                       "items": {
                           "type": "object",
                           "required": ["price_ticks", "qty_steps"],
                           "properties": {
                               "price_ticks": {"type": "string", "pattern": SIGNED_INT},
                               "qty_steps": {"type": "string", "pattern": SIGNED_INT}},
                           "additionalProperties": False}}},
               "additionalProperties": False},
           "ordinal_budget": {"type": "integer", "minimum": 0, "maximum": 4},
           "reprice_budget": {"type": "string", "pattern": DECIMAL_UINT},
           "ttl_ms": {"type": "string", "pattern": DECIMAL_UINT},
           "price_filters": {"type": "object"},
           "price_bands": {"type": "object"},
           "idempotency_key_law": {"type": "string", "minLength": 1},
           "refusal_codes": {"type": "array", "items": {"type": "string", "minLength": 1}},
       },
       payload_overrides={
           "authorization_ref": "x-authorization", "economic_purpose": "x-purpose",
           "instrument_id": "x-instrument", "account_mode": "x-mode",
           "zone": {"z0": "100", "z1": "90"},
           "observed_book": {"revision": "1",
                             "levels": [{"price_ticks": "101", "qty_steps": "5"}]},
           "ordinal_budget": 0, "reprice_budget": "1", "ttl_ms": "1000",
           "price_filters": {}, "price_bands": {}, "idempotency_key_law": "x-law",
           "refusal_codes": [],
       },
       # Recursive negative: zone missing z1 (nested required violation).
       invalid_payload_overrides={"zone": {"z0": "100"}},
       forbidden=["raw_credentials", "venue_order_id", "venue_trade_id"],
       schema_extra={"description": (
           "CO-03 step 6: VenueExecutionPlan.v1 — the E08->E09 plan (F21/C-006). Field-complete "
           "for GV-018's variants: sparse level (observed_book.levels is an explicit, possibly "
           "empty or non-contiguous list of price/qty pairs), zone-outside-book (zone[z0,z1] is "
           "not range-bound to observed_book levels), GTX race (a post-only cross race resolves "
           "to a named token in refusal_codes, never a silent conversion). ordinal_budget is a "
           "bounded integer 0..4. price_filters and price_bands carry the venue price-filter "
           "and band constraints ('price_filters/bands' in the order text). " + _CO03_DARK_NOTE)}),

    # CO-03 step 7 — the six E03-E06 advisory-chain reserved stubs (names + lineage fields
    # only; bodies land only with the signed CO-14 / OWNER-TOPO-01 decision). E04 is excluded
    # (Amendment A2): no E04 stub.
    _stub("triad.forecast_request.v2", "2.0.0", "triad-e05", ["triad-e03"],
          "FORECAST_REQUEST"),
    _stub("triad.forecast_response.v2", "2.0.0", "triad-e03", ["triad-e05"],
          "FORECAST_RESPONSE"),
    _stub("triad.logos_prompt_packet.v1", "1.0.0", "triad-e05", ["triad-e06"],
          "LOGOS_PROMPT_PACKET"),
    _stub("triad.logos_explanation.v1", "1.0.0", "triad-e06", ["triad-e05"],
          "LOGOS_EXPLANATION"),
    _stub("triad.logos_contradiction_report.v1", "1.0.0", "triad-e06", ["triad-e05"],
          "LOGOS_CONTRADICTION_REPORT"),
    _stub("triad.e05_intelligence_bundle.v1", "1.0.0", "triad-e05", ["triad-e07"],
          "E05_INTELLIGENCE_BUNDLE"),
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
          "output_segment_hashes", "divergence_links", "venue_sequences", "conflicts"}
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
                        "venue_activation_revision", "lease_epoch", "epoch",
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
        payload_props[f] = c["payload_field_schemas"].get(f) or _field_schema(f, c["enums"])
    for f in c["forbidden"]:
        payload_props[f] = False  # presence of a forbidden key fails validation
    payload_additional = c.get("payload_additional")
    payload = {
        "type": "object",
        "required": list(c["required"]),
        "properties": payload_props,
        # Additive minor fields preserved by default (Doc 03 compatibility); a ratification-
        # required stub instead closes its payload (CO-03 stop rule — no smuggled bodies).
        "additionalProperties": True if payload_additional is None else payload_additional,
    }
    props["payload"] = payload
    required = list(ENVELOPE_REQUIRED)
    if c["authority"]:
        required.append("producer_epoch")
    schema = {
        "$schema": DRAFT,
        "$id": f"https://triad.origin.v7/contracts/{c['id']}.schema.json",
        "title": c["id"],
        "type": "object",
        "required": sorted(required),
        "properties": props,
        "additionalProperties": False,
    }
    schema.update(c.get("schema_extra") or {})
    return schema


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
    if payload.get("binding_digest") == "__BINDING_DIGEST__":
        payload["binding_digest"] = _binding_digest(payload)
    env["payload"] = payload
    return env


def _binding_digest(payload: dict) -> str:
    """The binding.v2 digest identity: sha256 over the canonical payload minus the digest field.

    Must byte-agree with triad_origin.bindings/contracts (the same canonical_json law).
    """
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from triad_origin.canonical import canonical_json, sha256_hex
    unsigned = {k: v for k, v in payload.items() if k != "binding_digest"}
    return sha256_hex(canonical_json(unsigned))


def build_invalid(c: dict) -> dict:
    """A golden invalid vector.

    Default: drop the first required payload field. Contracts with a semantic (cross-field) law
    instead supply ``invalid_payload_overrides`` — a schema-valid payload that violates the
    semantic law, so the invalid golden proves the semantic validator, not just JSON Schema.
    """
    v = build_valid(c, {})
    if c.get("invalid_payload_overrides"):
        v["payload"].update(c["invalid_payload_overrides"])
        if "binding_digest" in v["payload"]:
            # Keep the digest identity true so the ONLY defect is the semantic-law violation.
            v["payload"]["binding_digest"] = _binding_digest(v["payload"])
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
        # CO-03 discipline: a field with an exact custom subschema never takes a heuristic
        # sample — the golden must state its value explicitly or generation fails loudly.
        missing = sorted(set(c["payload_field_schemas"]) - set(c["payload_overrides"]))
        if missing:
            raise SystemExit(
                f"{c['id']}: payload_field_schemas fields lack payload_overrides samples: "
                f"{missing}")
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
        entry.update(c.get("registry_extra") or {})
        index["contracts"].append(entry)
    _write_json(REGISTRY_DIR / "index.json", index)
    print(f"generated {len(CONTRACTS)} contracts + golden vectors + registry index")


if __name__ == "__main__":
    main()
