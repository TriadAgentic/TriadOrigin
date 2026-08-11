#!/usr/bin/env python3
"""Fail-closed validation for the C0 closure semantics and generated status.

This checker is deliberately read-only.  It validates the canonical C0 data artifacts, their
Draft 2020-12 schemas, the digest/identity laws, the closed milestone graph and the generated
safe-hold status.  It also binds the B00R generation-2 source policy to the canonical B00R scope.

The JSON schemas are human-readable JSON.  The two governed data artifacts are exact canonical
JSON: accepting merely equivalent, pretty-printed JSON would make their byte identity ambiguous.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from triad_origin.canonical import CanonicalError, canonical_json, loads_canonical  # noqa: E402


SEMANTICS_SCHEMA_REL = pathlib.Path("docs/control/closure/closure_semantics.v1.schema.json")
SEMANTICS_REL = pathlib.Path("docs/control/closure/closure_semantics.v1.json")
STATUS_SCHEMA_REL = pathlib.Path("docs/control/closure/closure_status.v1.schema.json")
STATUS_REL = pathlib.Path("docs/control/closure/closure_status.v1.json")
B00R_POLICY_REL = pathlib.Path("docs/control/b00r_policy.v2.json")

SEMANTICS_SCHEMA = "triad.closure.semantics.v1"
SEMANTICS_DOMAIN = "triad.closure.semantics.artifact.v1"
STATUS_SCHEMA = "triad.closure.status.v1"
STATUS_DOMAIN = "triad.closure.status.artifact.v1"
SCOPE_DOMAIN = "triad.closure.milestone_scope.v1"

EXPECTED_MILESTONES: tuple[tuple[str, str], ...] = (
    ("CONTROL_FREEZE", "C0"),
    ("ORIGIN_REPAIR", "B00R_G2"),
    ("ORIGIN_REPAIR", "B01C"),
    ("ORIGIN_REPAIR", "B02C"),
    ("ORIGIN_REPAIR", "B03C"),
    ("ORIGIN_REPAIR", "B04C"),
    ("ORIGIN_REPAIR", "B05C"),
    ("ORIGIN_REPAIR", "B06R"),
    ("ORIGIN_REPAIR", "B07"),
    ("ORIGIN_REPAIR", "B08"),
    ("ORIGIN_REPAIR", "B09"),
    ("ORIGIN_REPAIR", "B10"),
    ("ESTATE_CLOSURE", "BN"),
)

EXPECTED_PROFILE_IDS: Mapping[str, str] = {
    "B02C": "B02C_ACCEPTANCE_PROFILE_V1",
    "B03C": "B03C_ACCEPTANCE_PROFILE_V1",
    "B04C": "B04C_ACCEPTANCE_PROFILE_V1",
    "B05C": "B05C_ACCEPTANCE_PROFILE_V1",
    "B06R": "B06R_ACCEPTANCE_PROFILE_V1",
    "B07": "B07_ACCEPTANCE_PROFILE_V1",
    "B08": "B08_ACCEPTANCE_PROFILE_V1",
    "B09": "B09_ACCEPTANCE_PROFILE_V1",
    "B10": "B10_ACCEPTANCE_PROFILE_V1",
}

EXPECTED_DECISIONS = tuple(f"D-{number:02d}" for number in range(1, 10))
EXPECTED_DECISION_RULES: Mapping[str, str] = {
    "D-01": "New milestones use track_id, milestone_id, and scope_digest; no new receipt may use a bare ambiguous B identifier.",
    "D-02": "B00R G2 owns repository governance, authority, provider chronology, receipt law, and the evidence root only; downstream formula, binding, contract, capability, runtime, and topology defects remain blocking at their owning milestones.",
    "D-03": "RC5_EFFECTIVE_CONSOLIDATION is additive over immutable RC3 and RC4 preimages; RC3 and RC4 bytes are never rewritten.",
    "D-04": "ORIGIN_REPAIR B10 is the terminal audit and seal; historical commodities and equities expansion is deferred to FUTURE_EXPANSION.",
    "D-05": "ESTATE_CLOSURE BN aggregates B10, G-1 through G9, cross-estate receipts, and fresh same-subject runtime evidence without granting activation authority.",
    "D-06": "The owner, author, or evidence producer cannot satisfy independent review; every final source and receipt head requires a separate reviewer and B10 requires two independent audits.",
    "D-07": "Normal execution remains post-only and maker-only; a separately bounded reduction-only emergency path remains unless signed replacement proof shows exposure cannot be stranded.",
    "D-08": "Repository closure preserves OFF/OFF/OFF/LIVE and authorizes no deployment, restart, PAPER, TESTNET, LIVE, venue effect, or arming.",
    "D-09": "Operational credentials never enter Git or evidence and must be rotated before B05 or B10 security attestation or any promotion.",
}
EXPECTED_CONFLICTS = tuple(f"C-{number:02d}" for number in range(1, 15))
EXPECTED_TEST_LAYERS = tuple(f"T{number}" for number in range(13))
SAFE_HOLD = {
    "venue_environment": "OFF",
    "venue_activation": "OFF",
    "paper_activation": "OFF",
    "shadow_activation": "LIVE",
}

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "private-key-material",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    ),
    (
        "github-token",
        re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    ),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{16,}\b")),
    ("openai-style-key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("triad-mcp-token", re.compile(r"\btmc_[A-Za-z0-9_-]{16,}\b")),
    (
        "bearer-credential",
        re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{20,}"),
    ),
    (
        "assigned-credential",
        re.compile(
            r"(?i)\b(?:api[_ -]?key|access[_ -]?token|client[_ -]?secret|password)"
            r"\s*[:=]\s*[\"']?[A-Za-z0-9._~+/=-]{16,}"
        ),
    ),
    (
        "query-credential",
        re.compile(r"(?i)[?&](?:token|api_key|secret)=[A-Za-z0-9._~+/=-]{8,}"),
    ),
)


class ClosureControlError(ValueError):
    """Raised when a C0 control invariant fails."""


def _fail(code: str, detail: str) -> None:
    raise ClosureControlError(f"{code}: {detail}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("DUPLICATE_JSON_KEY", repr(key))
        result[key] = value
    return result


def _reject_float(token: str) -> Any:
    _fail("FLOAT_FORBIDDEN", token)


def load_json_object(path: pathlib.Path) -> dict[str, Any]:
    """Load noncanonical supporting JSON while rejecting ambiguous JSON constructs."""

    try:
        text = path.read_text(encoding="utf-8")
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_float=_reject_float,
            parse_constant=_reject_float,
        )
    except ClosureControlError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        _fail("JSON_LOAD_FAILED", f"{path}: {exc}")
    if not isinstance(value, dict):
        _fail("JSON_ROOT_NOT_OBJECT", str(path))
    return value


def load_canonical_object(path: pathlib.Path) -> dict[str, Any]:
    """Load an exact canonical JSON object, rejecting whitespace and equivalent encodings."""

    try:
        value = loads_canonical(path.read_bytes())
    except (OSError, CanonicalError) as exc:
        _fail("NONCANONICAL_CONTROL_ARTIFACT", f"{path}: {exc}")
    if not isinstance(value, dict):
        _fail("CONTROL_ROOT_NOT_OBJECT", str(path))
    return value


def _sha256_canonical(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def compute_envelope_digest(document: Mapping[str, Any], domain: str) -> str:
    """Compute the declared C0 envelope digest from its normative four-field preimage."""

    try:
        preimage = {
            "domain": domain,
            "schema": document["schema"],
            "version": document["version"],
            "payload": document["payload"],
        }
    except KeyError as exc:
        _fail("ENVELOPE_FIELD_MISSING", str(exc))
    return _sha256_canonical(preimage)


def scope_digest(scope: Mapping[str, Any]) -> str:
    """Return ``sha256(canonical_json(scope))`` under the scope's frozen domain field."""

    if scope.get("domain") != SCOPE_DOMAIN:
        _fail("SCOPE_DOMAIN_MISMATCH", repr(scope.get("domain")))
    return _sha256_canonical(scope)


def composite_id(scope: Mapping[str, Any]) -> str:
    digest = scope_digest(scope)
    try:
        track = scope["track_id"]
        milestone = scope["milestone_id"]
    except KeyError as exc:
        _fail("SCOPE_ID_FIELD_MISSING", str(exc))
    if not isinstance(track, str) or not isinstance(milestone, str):
        _fail("SCOPE_ID_FIELD_INVALID", "track_id and milestone_id must be strings")
    return f"{track}::{milestone}::sha256:{digest}"


def _require_digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None or value == "0" * 64:
        _fail("INVALID_SHA256", label)
    return value


def _require_sorted_unique_strings(values: Any, label: str, *, allow_empty: bool = False) -> None:
    if not isinstance(values, list) or (not allow_empty and not values):
        _fail("SET_FIELD_INVALID", f"{label} must be a{' nonempty' if not allow_empty else ''} list")
    if any(not isinstance(value, str) or not value for value in values):
        _fail("SET_FIELD_INVALID", f"{label} contains a non-string or empty member")
    if values != sorted(set(values)):
        _fail("SET_FIELD_NOT_CANONICAL", f"{label} must be sorted and unique")


def validate_schema(schema: Mapping[str, Any], instance: Any, label: str) -> None:
    """Self-check and apply an exact Draft 2020-12 schema, failing closed if unavailable."""

    try:
        from jsonschema import Draft202012Validator
        from jsonschema.exceptions import SchemaError
    except ImportError as exc:  # pragma: no cover - exercised in a dependency-starved runner
        _fail("SCHEMA_VALIDATOR_UNAVAILABLE", str(exc))
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        _fail("WRONG_JSON_SCHEMA_DIALECT", label)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        _fail("SCHEMA_SELF_VALIDATION_FAILED", f"{label}: {exc.message}")
    errors = sorted(Draft202012Validator(schema).iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        error = errors[0]
        location = "/".join(str(part) for part in error.absolute_path) or "<root>"
        _fail("SCHEMA_INSTANCE_INVALID", f"{label}:{location}: {error.message}")


def validate_envelope(document: Mapping[str, Any], expected_schema: str, domain: str) -> str:
    if document.get("schema") != expected_schema or document.get("version") != "1":
        _fail("ENVELOPE_IDENTITY_MISMATCH", expected_schema)
    digest = document.get("digest")
    if not isinstance(digest, dict):
        _fail("DIGEST_ENVELOPE_MISSING", expected_schema)
    declared = _require_digest(digest.get("value"), f"{expected_schema}.digest.value")
    if digest.get("domain") != domain:
        _fail("DIGEST_DOMAIN_MISMATCH", expected_schema)
    actual = compute_envelope_digest(document, domain)
    if declared != actual:
        _fail("ARTIFACT_DIGEST_MISMATCH", f"{expected_schema}: {declared} != {actual}")
    return actual


def _milestone_maps(
    semantics: Mapping[str, Any],
) -> tuple[list[Mapping[str, Any]], dict[tuple[str, str], Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    milestones = semantics["payload"]["milestones"]
    if not isinstance(milestones, list):
        _fail("MILESTONE_REGISTRY_INVALID", "not an array")
    by_key: dict[tuple[str, str], Mapping[str, Any]] = {}
    by_identity: dict[str, Mapping[str, Any]] = {}
    for row in milestones:
        if not isinstance(row, dict) or not isinstance(row.get("scope"), dict):
            _fail("MILESTONE_ROW_INVALID", repr(row))
        scope = row["scope"]
        key = (scope.get("track_id"), scope.get("milestone_id"))
        identity = row.get("identity")
        if key in by_key or identity in by_identity:
            _fail("DUPLICATE_MILESTONE", repr(key))
        by_key[key] = row
        by_identity[identity] = row
    return milestones, by_key, by_identity


def _validate_dependency_dag(rows: Sequence[Mapping[str, Any]], identities: set[str]) -> None:
    graph: dict[str, tuple[str, ...]] = {}
    for row in rows:
        identity = row["identity"]
        dependencies = tuple(row["dependency_identities"])
        for dependency in dependencies:
            if dependency not in identities or dependency == identity:
                _fail("INVALID_MILESTONE_DEPENDENCY", f"{identity} -> {dependency}")
        graph[identity] = dependencies

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(identity: str) -> None:
        if identity in visiting:
            _fail("MILESTONE_DEPENDENCY_CYCLE", identity)
        if identity in visited:
            return
        visiting.add(identity)
        for dependency in graph[identity]:
            visit(dependency)
        visiting.remove(identity)
        visited.add(identity)

    for identity in graph:
        visit(identity)


def validate_milestones(semantics: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    rows, by_key, by_identity = _milestone_maps(semantics)
    actual_order = tuple(
        (row["scope"]["track_id"], row["scope"]["milestone_id"]) for row in rows
    )
    if actual_order != EXPECTED_MILESTONES or set(by_key) != set(EXPECTED_MILESTONES):
        _fail("MILESTONE_SET_OR_ORDER_MISMATCH", repr(actual_order))

    previous_identity: str | None = None
    for row, expected_key in zip(rows, EXPECTED_MILESTONES, strict=True):
        scope = row["scope"]
        if (scope["track_id"], scope["milestone_id"]) != expected_key:
            _fail("MILESTONE_SCOPE_ID_MISMATCH", repr(expected_key))
        calculated_scope_digest = scope_digest(scope)
        declared_scope_digest = row["scope_digest"]
        if declared_scope_digest.get("value") != calculated_scope_digest:
            _fail("SCOPE_DIGEST_MISMATCH", repr(expected_key))
        identity = composite_id(scope)
        if row["identity"] != identity:
            _fail("COMPOSITE_IDENTITY_MISMATCH", repr(expected_key))
        if row["predecessor_identity"] != previous_identity:
            _fail("PREDECESSOR_CHAIN_MISMATCH", identity)
        _require_sorted_unique_strings(scope["owns"], f"{identity}.scope.owns")
        _require_sorted_unique_strings(scope["excludes"], f"{identity}.scope.excludes")
        _require_sorted_unique_strings(row["exclusions"], f"{identity}.exclusions")
        _require_sorted_unique_strings(
            row["dependency_identities"], f"{identity}.dependency_identities", allow_empty=True
        )
        if previous_identity is not None and previous_identity not in row["dependency_identities"]:
            _fail("PREDECESSOR_NOT_A_DEPENDENCY", identity)
        previous_identity = identity

    _validate_dependency_dag(rows, set(by_identity))
    return by_key


def validate_decisions(semantics: Mapping[str, Any]) -> None:
    decisions = semantics["payload"]["decisions"]
    ids = tuple(row.get("decision_id") for row in decisions)
    if ids != EXPECTED_DECISIONS or len(set(ids)) != len(ids):
        _fail("DECISION_SET_OR_ORDER_MISMATCH", repr(ids))
    for row in decisions:
        if row.get("status") != "CONFIRMED" or row.get("cryptographic_authentication") != "NOT_CLAIMED":
            _fail("DECISION_AUTHORITY_OVERCLAIM", str(row.get("decision_id")))
        if row.get("controlling_rule") != EXPECTED_DECISION_RULES[row["decision_id"]]:
            _fail("DECISION_RULE_MISMATCH", row["decision_id"])


def validate_conflicts(
    semantics: Mapping[str, Any],
    milestones: Mapping[tuple[str, str], Mapping[str, Any]],
) -> None:
    payload = semantics["payload"]
    conflicts = payload["conflict_dispositions"]
    ids = tuple(row.get("conflict_id") for row in conflicts)
    if ids != EXPECTED_CONFLICTS or len(set(ids)) != len(ids):
        _fail("CONFLICT_SET_OR_ORDER_MISMATCH", repr(ids))
    known_identities = {row["identity"] for row in milestones.values()}
    for row in conflicts:
        _require_sorted_unique_strings(
            row["controlling_basis"], f"{row['conflict_id']}.controlling_basis"
        )
        if row["severity"] in {"P0", "P1"}:
            if row["blocking"] is not True or row["waiver_status"] != "NOT_WAIVED":
                _fail("P0_P1_CONFLICT_WAIVER", row["conflict_id"])
        elif row["waiver_status"] not in {"NOT_WAIVED", "NOT_APPLICABLE"}:
            _fail("CONFLICT_WAIVER_STATUS_INVALID", row["conflict_id"])
        if row["owner_identity"] not in known_identities:
            _fail("CONFLICT_OWNER_UNKNOWN", row["conflict_id"])

    blocked_rule = payload["state_machine"]["blocked_rule"]
    normalized = blocked_rule.upper().replace("-", "_")
    if "P0" not in normalized or "P1" not in normalized or "WAIVER" not in normalized:
        _fail("P0_P1_NON_WAIVER_LAW_MISSING", blocked_rule)


def validate_profiles(
    semantics: Mapping[str, Any], milestones: Mapping[tuple[str, str], Mapping[str, Any]]
) -> None:
    profiles = semantics["payload"]["acceptance_profiles"]
    by_id = {row.get("profile_id"): row for row in profiles}
    if set(by_id) != set(EXPECTED_PROFILE_IDS.values()) or len(by_id) != len(profiles):
        _fail("ACCEPTANCE_PROFILE_SET_MISMATCH", repr(tuple(by_id)))

    known_identities = {row["identity"] for row in milestones.values()}
    for milestone_id, profile_id in EXPECTED_PROFILE_IDS.items():
        milestone = milestones[("ORIGIN_REPAIR", milestone_id)]
        profile = by_id[profile_id]
        if profile["milestone_identity"] != milestone["identity"]:
            _fail("PROFILE_MILESTONE_MISMATCH", profile_id)
        if milestone["profile_ref"] != profile_id:
            _fail("MILESTONE_PROFILE_REF_MISMATCH", milestone_id)
        if profile["required_independent_reviews"] != milestone["required_independent_reviews"]:
            _fail("PROFILE_REVIEW_QUORUM_MISMATCH", profile_id)
        if profile["owned_scope"] != milestone["scope"]["owns"]:
            _fail("PROFILE_OWNED_SCOPE_MISMATCH", profile_id)
        if profile["excluded_scope"] != milestone["exclusions"]:
            _fail("PROFILE_EXCLUDED_SCOPE_MISMATCH", profile_id)
        predecessor = milestone["predecessor_identity"]
        if predecessor not in profile["prerequisite_identities"]:
            _fail("PROFILE_PREDECESSOR_MISSING", profile_id)
        if any(identity not in known_identities for identity in profile["prerequisite_identities"]):
            _fail("PROFILE_PREREQUISITE_UNKNOWN", profile_id)
        for field in (
            "owned_scope",
            "excluded_scope",
            "prerequisite_identities",
            "required_artifacts",
            "targeted_tests",
            "cumulative_tests",
            "external_evidence",
            "work_packages",
            "acceptance_criteria",
            "attack_vectors",
        ):
            _require_sorted_unique_strings(profile[field], f"{profile_id}.{field}")
        adoption_manifest = profile["adoption_manifest"]
        path = pathlib.PurePosixPath(adoption_manifest)
        if (
            not isinstance(adoption_manifest, str)
            or not adoption_manifest
            or path.is_absolute()
            or ".." in path.parts
            or path.as_posix() != adoption_manifest
        ):
            _fail("PROFILE_ADOPTION_MANIFEST_PATH_INVALID", profile_id)
        if adoption_manifest != milestone["path_law"]["adoption_manifest"]:
            _fail("PROFILE_ADOPTION_MANIFEST_MISMATCH", profile_id)


def validate_test_matrix(
    semantics: Mapping[str, Any], milestones: Mapping[tuple[str, str], Mapping[str, Any]]
) -> None:
    payload = semantics["payload"]
    layers = payload["test_layers"]
    layer_ids = tuple(row.get("layer_id") for row in layers)
    if layer_ids != EXPECTED_TEST_LAYERS or len(set(layer_ids)) != len(layer_ids):
        _fail("TEST_LAYER_SET_OR_ORDER_MISMATCH", repr(layer_ids))

    expected_identities = tuple(milestones[key]["identity"] for key in EXPECTED_MILESTONES)
    matrix = payload["test_layer_matrix"]
    matrix_identities = tuple(row.get("milestone_identity") for row in matrix)
    if matrix_identities != expected_identities or len(set(matrix_identities)) != len(matrix_identities):
        _fail("TEST_MATRIX_MILESTONE_SET_OR_ORDER_MISMATCH", repr(matrix_identities))

    rows_by_identity = {row["milestone_identity"]: row for row in matrix}
    for identity, row in rows_by_identity.items():
        if set(row["layers"]) != set(EXPECTED_TEST_LAYERS):
            _fail("TEST_MATRIX_LAYER_SET_MISMATCH", identity)
        modes = tuple(row["layers"].values())
        if all(mode == "NOT_APPLICABLE" for mode in modes):
            _fail("TEST_MATRIX_EMPTY_ROW", identity)

    for milestone_id in EXPECTED_PROFILE_IDS:
        identity = milestones[("ORIGIN_REPAIR", milestone_id)]["identity"]
        modes = set(rows_by_identity[identity]["layers"].values())
        for required in ("TARGETED", "CUMULATIVE", "EXTERNAL"):
            if required not in modes:
                _fail("TEST_MATRIX_PROFILE_MODE_MISSING", f"{milestone_id}:{required}")


def validate_legacy_crosswalk(
    semantics: Mapping[str, Any], milestones: Mapping[tuple[str, str], Mapping[str, Any]]
) -> None:
    crosswalk = semantics["payload"]["legacy_crosswalk"]
    if not isinstance(crosswalk, list) or not crosswalk:
        _fail("LEGACY_CROSSWALK_EMPTY", "legacy_crosswalk")
    identities = {row["identity"] for row in milestones.values()}
    seen_legacy: set[str] = set()
    expected_legacy_refs = {
        "R00",
        "B00",
        "B00C",
        "B00R_GENERATION_1",
        "B01",
        "B01R",
        "B02",
        "B03",
        "B04",
        "B05",
        "B06",
        "B07",
        "B10_EXPANSION",
        "BN",
    }
    for row in crosswalk:
        if not isinstance(row, dict):
            _fail("LEGACY_CROSSWALK_ROW_INVALID", repr(row))
        legacy_id = row.get("legacy_ref")
        current_identity = row.get("current_identity")
        if not isinstance(legacy_id, str) or not legacy_id or legacy_id in seen_legacy:
            _fail("LEGACY_CROSSWALK_DUPLICATE", repr(legacy_id))
        target_kind = row.get("target_kind")
        if target_kind == "COMPOSITE_IDENTITY":
            if (
                current_identity not in identities
                or row.get("future_track") is not None
            ):
                _fail("LEGACY_CROSSWALK_TARGET_INVALID", repr(current_identity))
        elif target_kind == "FUTURE_TRACK":
            if current_identity is not None or row.get("future_track") != "FUTURE_EXPANSION":
                _fail("LEGACY_CROSSWALK_TARGET_INVALID", legacy_id)
        elif target_kind == "HISTORICAL_ONLY":
            if current_identity is not None or row.get("future_track") is not None:
                _fail("LEGACY_CROSSWALK_TARGET_INVALID", legacy_id)
        else:
            _fail("LEGACY_CROSSWALK_TARGET_INVALID", legacy_id)
        seen_legacy.add(legacy_id)
    if seen_legacy != expected_legacy_refs:
        _fail("LEGACY_CROSSWALK_SET_MISMATCH", repr(sorted(seen_legacy)))


def validate_semantics(semantics: Mapping[str, Any], schema: Mapping[str, Any]) -> str:
    validate_schema(schema, semantics, "closure semantics")
    digest = validate_envelope(semantics, SEMANTICS_SCHEMA, SEMANTICS_DOMAIN)
    payload = semantics["payload"]
    if payload["activation_posture"] != SAFE_HOLD:
        _fail("ACTIVATION_POSTURE_MISMATCH", repr(payload["activation_posture"]))
    authority = payload["authority"]
    if authority["cryptographic_authentication"] != "NOT_CLAIMED":
        _fail("CRYPTOGRAPHIC_AUTHENTICATION_OVERCLAIM", "semantics")
    if authority["activation_authorized"] or not authority["repository_work_authorized"]:
        _fail("AUTHORIZATION_BOUNDARY_MISMATCH", repr(authority))
    milestones = validate_milestones(semantics)
    validate_decisions(semantics)
    validate_conflicts(semantics, milestones)
    validate_profiles(semantics, milestones)
    validate_test_matrix(semantics, milestones)
    validate_legacy_crosswalk(semantics, milestones)
    validate_no_secrets(semantics, "closure semantics")
    return digest


def validate_status(
    status: Mapping[str, Any],
    schema: Mapping[str, Any],
    semantics: Mapping[str, Any],
    semantics_digest: str,
) -> str:
    validate_schema(schema, status, "closure status")
    digest = validate_envelope(status, STATUS_SCHEMA, STATUS_DOMAIN)
    payload = status["payload"]
    if payload["semantics_reference"]["digest_sha256"] != semantics_digest:
        _fail("STATUS_SEMANTICS_DIGEST_MISMATCH", "semantics_reference")
    if payload["activation_posture"] != SAFE_HOLD:
        _fail("STATUS_ACTIVATION_POSTURE_MISMATCH", repr(payload["activation_posture"]))
    if payload["cryptographic_authentication"] != "NOT_CLAIMED":
        _fail("CRYPTOGRAPHIC_AUTHENTICATION_OVERCLAIM", "status")

    rows, _, _ = _milestone_maps(semantics)
    expected_identities = tuple(row["identity"] for row in rows)
    status_rows = payload["milestones"]
    status_identities = tuple(row.get("identity") for row in status_rows)
    if status_identities != expected_identities or len(set(status_identities)) != len(status_identities):
        _fail("STATUS_MILESTONE_SET_OR_ORDER_MISMATCH", repr(status_identities))
    if tuple(payload["current_work"]) != expected_identities[:2]:
        _fail("STATUS_CURRENT_WORK_MISMATCH", repr(payload["current_work"]))

    for index, row in enumerate(status_rows):
        expected_work_state = "SOURCE_IN_PROGRESS" if index < 2 else "NOT_STARTED"
        expected_runtime_state = "NOT_APPLICABLE" if index == 0 else "NOT_ATTESTED"
        if row["work_state"] != expected_work_state:
            _fail("STATUS_WORK_STATE_MISMATCH", row["identity"])
        if row["gate_state"] != "BLOCKED" or row["receipt_state"] != "BLOCKED":
            _fail("STATUS_GATE_NOT_BLOCKED", row["identity"])
        if row["runtime_state"] != expected_runtime_state:
            _fail("STATUS_RUNTIME_STATE_MISMATCH", row["identity"])
        _require_sorted_unique_strings(row["blocking_reasons"], f"{row['identity']}.blocking_reasons")

    if payload["closed_claims"]:
        _fail("CLOSED_CLAIM_WHILE_BLOCKED", repr(payload["closed_claims"]))
    blockers = payload["open_blockers"]
    blocker_ids = [row["blocker_id"] for row in blockers]
    if len(blocker_ids) != len(set(blocker_ids)):
        _fail("DUPLICATE_OPEN_BLOCKER", repr(blocker_ids))
    known_identities = set(expected_identities)
    for blocker in blockers:
        if blocker["owner_identity"] not in known_identities:
            _fail("BLOCKER_OWNER_UNKNOWN", blocker["blocker_id"])
        if blocker["severity"] not in {"P0", "P1"} or blocker["status"] != "OPEN":
            _fail("BLOCKER_NOT_FAIL_CLOSED", blocker["blocker_id"])
    validate_no_secrets(status, "closure status")
    return digest


def validate_b00r_policy(
    policy: Mapping[str, Any], semantics: Mapping[str, Any]
) -> None:
    _, milestones, _ = _milestone_maps(semantics)
    b00r = milestones[("ORIGIN_REPAIR", "B00R_G2")]
    binding = policy.get("pr_role_law", {}).get("source_pr", {}).get("composite_scope_binding")
    if not isinstance(binding, dict):
        _fail("B00R_SCOPE_BINDING_MISSING", "pr_role_law.source_pr.composite_scope_binding")
    expected = {
        "track_id": "ORIGIN_REPAIR",
        "milestone_id": "B00R_G2",
        "scope_digest": b00r["scope_digest"]["value"],
        "scope_digest_source": SEMANTICS_REL.as_posix(),
        "status": "BOUND_CANONICAL",
        "failure_behavior": "SOURCE_MERGE_FORBIDDEN_ON_SCOPE_BINDING_MISMATCH",
    }
    if binding != expected:
        _fail("B00R_SCOPE_BINDING_MISMATCH", f"expected {expected!r}, got {binding!r}")
    if policy.get("levers") != SAFE_HOLD:
        _fail("B00R_POLICY_ACTIVATION_POSTURE_MISMATCH", repr(policy.get("levers")))
    if policy.get("required_result") != b00r["permitted_result"]:
        _fail("B00R_POLICY_RESULT_MISMATCH", repr(policy.get("required_result")))
    validate_no_secrets(policy, "B00R policy")


def validate_no_secrets(value: Any, label: str) -> None:
    """Reject recognizable credential material; identifiers and pin *names* remain allowed."""

    text = canonical_json(value).decode("utf-8")
    for name, pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            _fail("SECRET_PATTERN_DETECTED", f"{label}:{name}")


def check_all(root: pathlib.Path = ROOT) -> dict[str, str | int]:
    """Validate every C0 control input without mutating the worktree."""

    semantics_schema = load_json_object(root / SEMANTICS_SCHEMA_REL)
    status_schema = load_json_object(root / STATUS_SCHEMA_REL)
    semantics = load_canonical_object(root / SEMANTICS_REL)
    status = load_canonical_object(root / STATUS_REL)
    policy = load_json_object(root / B00R_POLICY_REL)

    semantics_digest = validate_semantics(semantics, semantics_schema)
    status_digest = validate_status(status, status_schema, semantics, semantics_digest)
    validate_b00r_policy(policy, semantics)
    return {
        "semantics_digest": semantics_digest,
        "status_digest": status_digest,
        "milestones": len(EXPECTED_MILESTONES),
        "decisions": len(EXPECTED_DECISIONS),
        "conflicts": len(EXPECTED_CONFLICTS),
        "profiles": len(EXPECTED_PROFILE_IDS),
        "test_layers": len(EXPECTED_TEST_LAYERS),
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="read-only validation (the default; retained for explicit CI invocation)",
    )
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=ROOT,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        result = check_all(args.root.resolve())
    except ClosureControlError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        "OK: C0 closure control canonical; "
        f"{result['milestones']} milestones; {result['decisions']} decisions; "
        f"{result['conflicts']} conflict dispositions; {result['profiles']} profiles; "
        f"{result['test_layers']} test layers; OFF/OFF/OFF/LIVE; no closure claim"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
