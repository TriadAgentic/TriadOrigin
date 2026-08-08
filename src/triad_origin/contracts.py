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

import functools
import json
import pathlib
import re
from typing import Any

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
def registry() -> dict[str, Any]:
    if not _REGISTRY.exists():
        raise ContractError("contract registry index missing; run tools/gen_contracts.py")
    return json.loads(_REGISTRY.read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=256)
def load_schema(schema_id: str) -> dict[str, Any]:
    path = _SCHEMA_DIR / f"{schema_id}.schema.json"
    if not path.exists():
        raise ContractError(f"unknown contract schema: {schema_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def known_contracts() -> list[str]:
    return [c["contract_id"] for c in registry()["contracts"]]


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
    declared = event.get("schema")
    sid = schema_id or declared
    if sid is None:
        raise ContractError("event has no 'schema' field")
    if declared is not None and schema_id is not None and declared != schema_id:
        raise ContractError(f"schema mismatch: envelope says {declared!r}, expected {schema_id!r}")
    schema = load_schema(sid)
    _validate_against_schema(schema, event)


def validate_payload(schema_id: str, payload: dict) -> None:
    """Validate a payload builder against the pinned payload schema for ``schema_id``.

    Builders that do not own envelope metadata still validate the bytes they do own before handing
    them to an envelope producer.  This prevents a read-face or quarantine path from constructing a
    payload that its declared contract can never carry.
    """
    schema = load_schema(schema_id)
    payload_schema = schema.get("properties", {}).get("payload")
    if not isinstance(payload_schema, dict):
        raise ContractError(f"contract {schema_id!r} has no object payload schema")
    if not isinstance(payload, dict):
        raise ContractError("payload must be a JSON object")
    _validate_against_schema(payload_schema, payload)


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
    raw = event.get("producer_epoch")
    if raw is None:
        raise StaleEpochError("authority-path event carries no producer_epoch")
    try:
        epoch = int(raw)
    except (TypeError, ValueError) as exc:
        raise StaleEpochError(f"producer_epoch not a decimal integer: {raw!r}") from exc
    if epoch < highest_accepted:
        raise StaleEpochError(
            f"stale producer_epoch {epoch} < highest accepted {highest_accepted}")
    return max(epoch, highest_accepted)


def assert_no_forbidden_candidate_fields(event: dict) -> None:
    """Constitutional guard: an edge candidate may carry no money-authority field (Doc 03 §03.6)."""
    forbidden = ("final_approval", "account_id", "notional", "leverage", "executable_quantity",
                 "venue_order_id", "raw_credentials", "expected_return", "e09_destination")
    payload = event.get("payload", {})
    present = [f for f in forbidden if f in payload]
    if present:
        raise ContractError(f"edge candidate carries forbidden money field(s): {present}")
