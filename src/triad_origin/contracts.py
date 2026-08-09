"""Contract loading, validation and envelope invariants (Doc 03).

Every authoritative event validates **before publication** and **again at the consuming boundary**.
Unknown safety/economic data never defaults: it rejects (``ContractError``) or is quarantined with
raw evidence. Schema compatibility does not imply producer authority — a valid payload with a stale
epoch is rejected by ``assert_epoch_ge`` at the consumer.

Validation uses ``jsonschema`` when available; a stdlib fallback enforces the load-bearing checks
(required fields, closed enums, ``const`` and forbidden keys) so the money path never hard-depends
on a third-party library.
"""

from __future__ import annotations

import copy
import functools
import json
import pathlib
import re
from typing import Any

from .canonical import CanonicalError, canonical_json, str_to_tick
from .control import lever_law

_PACKAGE_CONTRACTS_DIR = pathlib.Path(__file__).resolve().parent / "_contracts"
_SOURCE_CONTRACTS_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "contracts"
_CONTRACTS_DIR = (
    _PACKAGE_CONTRACTS_DIR
    if (_PACKAGE_CONTRACTS_DIR / "registry" / "index.json").is_file()
    else _SOURCE_CONTRACTS_DIR
)
_SCHEMA_DIR = _CONTRACTS_DIR / "schemas"
_REGISTRY = _CONTRACTS_DIR / "registry" / "index.json"


class ContractError(ValueError):
    """A contract validation or envelope-invariant failure. Always fail closed."""


class StaleEpochError(ContractError):
    """A structurally valid payload carrying a lower producer epoch than already accepted."""


@functools.lru_cache(maxsize=1)
def _registry_cached() -> dict[str, Any]:
    if not _REGISTRY.exists():
        raise ContractError("contract registry index missing; run tools/gen_contracts.py")
    return json.loads(_REGISTRY.read_text(encoding="utf-8"))


def registry() -> dict[str, Any]:
    """Return a detached registry view; callers cannot mutate validation truth."""
    return copy.deepcopy(_registry_cached())


@functools.lru_cache(maxsize=256)
def _load_schema_cached(schema_id: str) -> dict[str, Any]:
    # Called only after the non-cached type/grammar/membership guard below. Keeping this loader
    # private prevents lru_cache from hashing an attacker-supplied unhashable object first.
    path = _SCHEMA_DIR / f"{schema_id}.schema.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot load contract schema {schema_id!r}: {exc}") from exc


def _checked_schema_id(schema_id: object) -> str:
    if (
        not isinstance(schema_id, str)
        or len(schema_id) > 128
        or re.fullmatch(
            r"triad\.[a-z0-9_]+(?:\.[a-z0-9_]+)*\.v[1-9][0-9]*", schema_id
        ) is None
    ):
        raise ContractError(f"invalid contract schema identifier: {schema_id!r}")
    if schema_id not in _known_contracts_cached():
        raise ContractError(f"unknown contract schema: {schema_id}")
    return schema_id


def _schema_for_validation(schema_id: object) -> dict[str, Any]:
    return _load_schema_cached(_checked_schema_id(schema_id))


def load_schema(schema_id: str) -> dict[str, Any]:
    """Return a detached schema view; the private validation cache is never exposed."""
    return copy.deepcopy(_schema_for_validation(schema_id))


@functools.lru_cache(maxsize=1)
def _known_contracts_cached() -> tuple[str, ...]:
    return tuple(contract["contract_id"] for contract in _registry_cached()["contracts"])


def known_contracts() -> list[str]:
    return list(_known_contracts_cached())


# --- validation ----------------------------------------------------------------------------------
def _validate_jsonschema(schema: dict, event: dict) -> None:
    import jsonschema  # lazy; optional dependency

    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)
    errors = sorted(validator.iter_errors(event), key=lambda e: list(e.path))
    if errors:
        e = errors[0]
        loc = "/".join(str(p) for p in e.path) or "<root>"
        raise ContractError(f"schema violation at {loc}: {e.message}")


def _validate_fallback(schema: dict, event: dict) -> None:
    """Minimal stdlib validator covering the safety-material subset of the schema vocabulary."""

    def check(node_schema: Any, value: Any, path: str) -> None:
        if node_schema is False:
            raise ContractError(f"forbidden field present at {path or '<root>'}")
        if node_schema is True or not isinstance(node_schema, dict):
            return
        if "const" in node_schema and value != node_schema["const"]:
            raise ContractError(f"{path}: expected const {node_schema['const']!r}, got {value!r}")
        if "enum" in node_schema and value not in node_schema["enum"]:
            raise ContractError(f"{path}: value {value!r} not in closed enum")
        t = node_schema.get("type")
        if t and not _type_ok(t, value):
            raise ContractError(f"{path}: expected type {t}, got {type(value).__name__}")
        if "minLength" in node_schema and isinstance(value, str):
            minimum = node_schema["minLength"]
            if len(value) < minimum:
                raise ContractError(
                    f"{path}: string length {len(value)} is below minLength {minimum}")
        if "pattern" in node_schema and isinstance(value, str):
            pattern = node_schema["pattern"]
            try:
                matched = re.search(pattern, value)
            except re.error as exc:
                raise ContractError(f"{path}: invalid schema pattern {pattern!r}") from exc
            if matched is None:
                raise ContractError(f"{path}: value {value!r} does not match pattern {pattern!r}")
        if t == "object" or "properties" in node_schema or "required" in node_schema:
            if not isinstance(value, dict):
                if node_schema.get("additionalProperties") is False:
                    raise ContractError(f"{path}: expected object")
                return
            for req in node_schema.get("required", []):
                if req not in value:
                    raise ContractError(f"{path}: missing required field '{req}'")
            props = node_schema.get("properties", {})
            addl = node_schema.get("additionalProperties", True)
            for k, v in value.items():
                sub = f"{path}.{k}" if path else k
                if k in props:
                    check(props[k], v, sub)
                elif addl is False:
                    raise ContractError(f"{sub}: additional property not permitted")

    check(schema, event, "")


def _type_ok(t: str, value: Any) -> bool:
    if isinstance(value, bool):
        return t == "boolean"
    return {
        "string": isinstance(value, str),
        "integer": isinstance(value, int),
        "number": isinstance(value, (int, float)),
        "boolean": isinstance(value, bool),
        "array": isinstance(value, list),
        "object": isinstance(value, dict),
        "null": value is None,
    }.get(t, True)


def validate(event: dict, *, schema_id: str | None = None) -> None:
    """Validate ``event`` against its declared (or given) contract schema. Fail closed.

    The ``schema`` envelope field is authoritative; a mismatch with ``schema_id`` rejects.
    """
    if not isinstance(event, dict):
        raise ContractError("event must be a JSON object")
    _require_canonical_wire(event, "event")
    declared = event.get("schema")
    sid = schema_id or declared
    if sid is None:
        raise ContractError("event has no 'schema' field")
    if declared is not None and schema_id is not None and declared != schema_id:
        raise ContractError(f"schema mismatch: envelope says {declared!r}, expected {schema_id!r}")
    schema = _schema_for_validation(sid)
    _validate_against_schema(schema, event)
    if sid in {"triad.edge_candidate.v1", "triad.edge_candidate.v2"}:
        assert_no_forbidden_candidate_fields(event)
    semantic = SEMANTIC_VALIDATORS.get(sid)
    if semantic is not None:
        semantic(event)


# --- semantic (cross-field) laws — RC3 semantic_transition_validator posture ----------------------
# JSON Schema cannot express cross-field equality or conditional-combination laws; these run after
# schema validation inside validate(), so a schema-valid but semantically illegal event still
# rejects (fail closed). Each validator raises ContractError with the RC4/RC3 refusal name.


def _payload_of(event: dict) -> dict:
    payload = event.get("payload")
    if not isinstance(payload, dict):
        raise ContractError("event payload must be a JSON object")
    return payload


def _semantic_engine_attestation_v2(event: dict) -> None:
    """CTRL-B01-002 / BLK-RC2-016: payload identity fields must equal their envelope twins."""
    payload = _payload_of(event)
    for field in ("contract_manifest_sha256", "config_bundle_sha256", "build_commit",
                  "artifact_sha256", "producer_epoch"):
        env_value = event.get(field)
        pay_value = payload.get(field)
        if env_value != pay_value:
            raise ContractError(
                f"ATTESTATION_IDENTITY_MISMATCH: payload.{field}={pay_value!r} "
                f"!= envelope.{field}={env_value!r}")


def _semantic_engine_control_manifest_v2(event: dict) -> None:
    """RC4 lever-combination law (the four-plane law's manifest-side conjuncts).

    Delegates the full EVENT_LOCAL refusal classification to the single source of that law,
    :func:`triad_origin.control.lever_law.resolve_manifest` (B05) — this boundary never restates
    the RC4 refusal-code vocabulary a second time; it raises the SAME named code the runtime
    lever registry and every other consumer of :mod:`triad_origin.control.lever_law` would.
    """
    payload = _payload_of(event)
    resolution = lever_law.resolve_manifest(payload)
    if not resolution.accepted:
        raise ContractError(f"{resolution.refusal_code}: {resolution.meaning}")


def _reject_wildcard_scope(node: Any, path: str) -> None:
    if isinstance(node, str):
        if node == "" or "*" in node:
            raise ContractError(
                f"SCOPE_VALUE_INVALID: {path} is empty, malformed, or contains a wildcard")
    elif isinstance(node, dict):
        for key, value in node.items():
            _reject_wildcard_scope(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            _reject_wildcard_scope(value, f"{path}[{i}]")


def _semantic_evidence_receipt_v2(event: dict) -> None:
    """RC3 receipt law: PASS requires nonempty scope/evidence, valid clocks, builder != reviewer."""
    payload = _payload_of(event)
    if payload.get("result") != "PASS":
        return
    if not payload.get("scope"):
        raise ContractError("RECEIPT_PASS_EMPTY_SCOPE")
    if not payload.get("evidence_ids") or not payload.get("evidence_sha256s"):
        raise ContractError("RECEIPT_PASS_EMPTY_EVIDENCE")
    observed = payload.get("observed_at_us")
    expires = payload.get("expires_at_us")
    if not isinstance(observed, int) or not isinstance(expires, int) or expires <= observed:
        raise ContractError("RECEIPT_PASS_INVALID_VALIDITY_WINDOW")
    if not payload.get("signature"):
        raise ContractError("RECEIPT_PASS_MISSING_SIGNATURE")
    if payload.get("builder") == payload.get("reviewer"):
        raise ContractError("RECEIPT_PASS_BUILDER_IS_REVIEWER")


def _semantic_task_status_event_v2(event: dict) -> None:
    """RC3 receipt law: a PASS transition needs acceptance + verification receipts; no self-loop."""
    payload = _payload_of(event)
    if payload.get("from_status") == payload.get("to_status"):
        raise ContractError("TASK_STATUS_ILLEGAL_TRANSITION: from == to")
    if payload.get("to_status") == "PASS":
        if not payload.get("acceptance_receipt_ids") or not payload.get(
                "verification_receipt_ids"):
            raise ContractError("TASK_STATUS_PASS_WITHOUT_RECEIPTS")
        if not payload.get("signature"):
            raise ContractError("TASK_STATUS_PASS_MISSING_SIGNATURE")


def _semantic_gate_receipt_v2(event: dict) -> None:
    """RC3/B00C gate-receipt law: PASS requires exact scope, digests, a valid validity window,
    zero blockers, task+verification+rollback evidence, and an independent approver."""
    payload = _payload_of(event)
    if payload.get("result") != "PASS":
        return
    if payload.get("open_blockers"):
        raise ContractError("GATE_PASS_WITH_OPEN_BLOCKERS")
    if not payload.get("task_receipt_ids") or not payload.get("verification_receipt_ids"):
        raise ContractError("GATE_PASS_WITHOUT_RECEIPTS")
    if not payload.get("rollback_proof_ids"):
        raise ContractError("GATE_PASS_WITHOUT_ROLLBACK_PROOF")
    if not payload.get("approver") or not payload.get("signature"):
        raise ContractError("GATE_PASS_MISSING_APPROVAL")
    scope = payload.get("scope")
    if not scope:
        raise ContractError("GATE_PASS_EMPTY_SCOPE")
    _reject_wildcard_scope(scope, "scope")
    observed = payload.get("observed_at_us")
    expires = payload.get("expires_at_us")
    if not isinstance(observed, int) or not isinstance(expires, int) or expires <= observed:
        raise ContractError("GATE_PASS_INVALID_VALIDITY_WINDOW")
    digests = payload.get("producer_digests")
    if not isinstance(digests, dict) or not digests or any(
            not isinstance(v, str) or len(v) != 64 or v == "0" * 64
            for v in digests.values()):
        raise ContractError("GATE_PASS_MISSING_OR_PLACEHOLDER_DIGESTS")
    if payload.get("approver") == event.get("producer_service"):
        raise ContractError("GATE_PASS_APPROVER_NOT_INDEPENDENT")


def _semantic_binding_v2(event: dict) -> None:
    """binding.v2 law (B01R): structural migration never activates a row.

    ACTIVE demands a fully-resolved semantic binding (EXACTLY_ONE cardinality, migrated state,
    non-empty slot/condition/scope/precedence/unit contract, no wildcard scope, not superseded);
    any non-ACTIVE status demands a named disposition. The digest identity binds the row bytes.
    """
    payload = _payload_of(event)
    digest = payload.get("binding_digest")
    unsigned = {k: v for k, v in payload.items() if k != "binding_digest"}
    from .canonical import canonical_json, sha256_hex
    if digest != sha256_hex(canonical_json(unsigned)):
        raise ContractError("BINDING_DIGEST_MISMATCH")
    status = payload.get("status")
    if status == "ACTIVE":
        if payload.get("lifecycle_status") != "ACTIVE":
            raise ContractError("BINDING_ACTIVE_LIFECYCLE_MISMATCH")
        if payload.get("cardinality") != "EXACTLY_ONE":
            raise ContractError("BINDING_ACTIVE_WITH_UNRESOLVED_CARDINALITY")
        if payload.get("migration_state") == "BLOCKED_NOT_STARTED":
            raise ContractError("BINDING_ACTIVE_WITH_UNMIGRATED_STATE")
        for field in ("semantic_slot", "condition", "activation_scope", "precedence",
                      "unit_contract", "consumer", "consuming_wiring_ids"):
            if not payload.get(field):
                raise ContractError(f"BINDING_ACTIVE_EMPTY_FIELD: {field}")
        if "*" in payload.get("activation_scope", ""):
            raise ContractError("BINDING_ACTIVE_WILDCARD_SCOPE")
        if payload.get("superseded_by"):
            raise ContractError("BINDING_ACTIVE_BUT_SUPERSEDED")
    else:
        if not payload.get("disposition_reason"):
            raise ContractError("BINDING_BLOCKED_WITHOUT_DISPOSITION")


# Semantic validators that read ONLY payload fields (no envelope cross-reference) also run in
# validate_payload, so a payload-level consumer (registry loader, read face) cannot admit a
# schema-valid but semantically illegal payload.
PAYLOAD_SEMANTIC_VALIDATORS = {
    "triad.binding.v2": _semantic_binding_v2,
}

SEMANTIC_VALIDATORS = {
    "triad.binding.v2": _semantic_binding_v2,
    "triad.engine_attestation.v2": _semantic_engine_attestation_v2,
    "triad.engine_control_manifest.v2": _semantic_engine_control_manifest_v2,
    "triad.evidence_receipt.v2": _semantic_evidence_receipt_v2,
    "triad.task_status_event.v2": _semantic_task_status_event_v2,
    "triad.gate_receipt.v2": _semantic_gate_receipt_v2,
}


def validate_payload(schema_id: str, payload: dict) -> None:
    """Validate a payload builder against the pinned payload schema for ``schema_id``.

    Builders that do not own envelope metadata still validate the bytes they do own before handing
    them to an envelope producer.  This prevents a read-face or quarantine path from constructing a
    payload that its declared contract can never carry.
    """
    schema = _schema_for_validation(schema_id)
    payload_schema = schema.get("properties", {}).get("payload")
    if not isinstance(payload_schema, dict):
        raise ContractError(f"contract {schema_id!r} has no object payload schema")
    if not isinstance(payload, dict):
        raise ContractError("payload must be a JSON object")
    _require_canonical_wire(payload, "payload")
    _validate_against_schema(payload_schema, payload)
    if schema_id in {"triad.edge_candidate.v1", "triad.edge_candidate.v2"}:
        assert_no_forbidden_candidate_fields({"payload": payload})
    payload_semantic = PAYLOAD_SEMANTIC_VALIDATORS.get(schema_id)
    if payload_semantic is not None:
        payload_semantic({"payload": payload})


def _require_canonical_wire(value: dict, label: str) -> None:
    try:
        canonical_json(value)
    except (CanonicalError, UnicodeError, RecursionError) as exc:
        raise ContractError(f"{label} is not canonical-wire encodable: {exc}") from exc


def _validate_against_schema(schema: dict, value: Any) -> None:
    try:
        _validate_jsonschema(schema, value)
    except ModuleNotFoundError:
        _validate_fallback(schema, value)


def is_valid(event: dict, *, schema_id: str | None = None) -> bool:
    try:
        validate(event, schema_id=schema_id)
        return True
    except ContractError:
        return False


# --- envelope / authority invariants -------------------------------------------------------------
def assert_epoch_ge(event: dict, highest_accepted: int) -> int:
    """Fencing check at a consuming authority boundary (Doc 03 §03.9, Doc 04 §04.16).

    Returns the current highest accepted epoch. The active epoch may emit any number of events;
    only a lower epoch is stale. A newly promoted producer still needs a strictly higher epoch.
    """
    if (
        isinstance(highest_accepted, bool)
        or not isinstance(highest_accepted, int)
        or highest_accepted < -1
    ):
        raise StaleEpochError("highest accepted epoch must be an integer >= -1")
    raw = event.get("producer_epoch")
    if raw is None:
        raise StaleEpochError("authority-path event carries no producer_epoch")
    try:
        epoch = str_to_tick(raw)
    except CanonicalError as exc:
        raise StaleEpochError(f"producer_epoch not a canonical decimal integer: {raw!r}") from exc
    if epoch < 0:
        raise StaleEpochError("producer_epoch must be non-negative")
    if epoch < highest_accepted:
        raise StaleEpochError(
            f"stale producer_epoch {epoch} < highest accepted {highest_accepted}")
    return max(epoch, highest_accepted)


def assert_no_forbidden_candidate_fields(event: dict) -> None:
    """Constitutional guard: an edge candidate may carry no money-authority field (Doc 03 §03.6)."""
    forbidden = {"final_approval", "account_id", "notional", "leverage", "executable_quantity",
                 "venue_order_id", "raw_credentials", "expected_return", "e09_destination"}
    payload = event.get("payload", {})
    stack: list[Any] = [payload]
    present: set[str] = set()
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            present.update(forbidden.intersection(value))
            stack.extend(value.values())
        elif isinstance(value, (list, tuple)):
            stack.extend(value)
    if present:
        raise ContractError(
            f"edge candidate carries forbidden money field(s): {sorted(present)}"
        )
