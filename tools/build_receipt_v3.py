#!/usr/bin/env python3
"""Build an UNSIGNED ``triad.evidence_receipt.v3`` draft plus its external-signing preimages.

This ceremony draft-builder mirrors the receipt law of the frozen audit runner
(``audit_package/triad_origin_b01_b10_audit.py``, v1.2.0, ``receipt_issues`` and its reference
fixture ``make_valid_receipt``).  It emits:

  (a) the full receipt event JSON — ``{"schema": "triad.evidence_receipt.v3", "payload": {...},
      "dsse": {"payloadType": "application/vnd.triad.evidence-receipt.v3+json",
      "payload": <base64 of the RFC 8785 JCS payload bytes>, "signatures": []}}`` — UNSIGNED;
  (b) a sidecar ``*.signing.json`` carrying the exact DSSE PAE bytes (hex), the payload base64
      and the payload SHA-256, for the operator's EXTERNAL Ed25519 signer; and
  (c) with ``--self-check``, an independent re-validation of the written draft against every
      unsigned-checkable clause of the runner's receipt law (named issue list; empty => exit 0).

THIS TOOL NEVER SIGNS.  It holds no keys, loads no private material, opens no network path.
The DSSE ``signatures`` array is emitted empty; signing is the operator's external act.

JCS NOTE: ``jcs_canonical_bytes`` below is an EMBEDDED minimal copy of the frozen runner's
implementation.  It must stay byte-identical in behavior to the repository's
``tools/jcs_canonical.py`` (when that module lands) and to the frozen runner — the
differential test enforces output byte-equality against the runner.  The copy exists because
of the self-contained-tool law: importing sibling repository modules from a tool executed as
``python tools/build_receipt_v3.py`` would compile ``__pycache__`` inside a fresh clone and
violate the tree-mutation law, so this tool imports ONLY the Python standard library.

TREE-MUTATION LAW: ``--out`` refuses a path inside this tool's repository root unless
``--allow-in-repo``; the evidence ``--repo`` root is only ever READ.

Exit codes: 0 success (and, with --self-check, zero issues); 1 self-check found issues;
2 invalid invocation, refused config, or policy refusal.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import pathlib
import re
import sys
from typing import Any, Iterable

TOOL_NAME = "build_receipt_v3"
TOOL_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Constants copied VERBATIM from the frozen runner (v1.2.0).
# ---------------------------------------------------------------------------
RECEIPT_SCHEMA = "triad.evidence_receipt.v3"
RECEIPT_PAYLOAD_TYPE = "application/vnd.triad.evidence-receipt.v3+json"
EXPECTED_REPOSITORY = "triadagentic/triadorigin"
REPOSITORY_FUTURE_TOLERANCE_US = 0
MAX_RECEIPT_TTL_US = 2_592_000_000_000
PASS = "PASS"

REQUIRED_RECEIPT_DIGEST_ROLES: tuple[tuple[str, str], ...] = (
    ("receipt_profile_decision_sha256", "RECEIPT_PROFILE_DECISION"),
    ("artifact_sha256", "ARTIFACT"),
    ("config_bundle_sha256", "CONFIGURATION"),
    ("contract_bundle_sha256", "CONTRACT_BUNDLE"),
    ("binding_bundle_sha256", "BINDING_BUNDLE"),
    ("test_collection_sha256", "TEST_COLLECTION"),
    ("evidence_manifest_sha256", "EVIDENCE_MANIFEST"),
    ("rollback_proof_sha256", "ROLLBACK_PROOF"),
)
EXTRA_EVIDENCE_ROLES = ("CHECK_EVIDENCE_INDEX", "GITHUB_EVIDENCE", "REVIEW_EVIDENCE", "OTHER")
ALLOWED_EVIDENCE_ROLES = frozenset(
    {role for _, role in REQUIRED_RECEIPT_DIGEST_ROLES} | set(EXTRA_EVIDENCE_ROLES))

GOVERNANCE = {"branch_rules_enforced": True, "bypass_used": False}

# The closed ratified profile-decision content (runner SUPPORTED_RECEIPT_PROFILE_DECISION),
# used to validate the RECEIPT_PROFILE_DECISION evidence preimage's content.
RECEIPT_PROFILE_DECISION: dict[str, Any] = {
    "schema": "triad.receipt_profile_decision.v1",
    "decision_id": "DECISION-RECEIPT-PROFILE-001",
    "status": "RATIFIED",
    "repository": EXPECTED_REPOSITORY,
    "canonicalization": "RFC8785_JCS",
    "payload_type": RECEIPT_PAYLOAD_TYPE,
    "signature_algorithm": "Ed25519",
    "required_signer_roles": ["PRODUCER", "COUNTERSIGNER"],
    "minimum_distinct_signers": 2,
    "max_receipt_ttl_us": MAX_RECEIPT_TTL_US,
    "repository_provider_future_tolerance_us": REPOSITORY_FUTURE_TOLERANCE_US,
}

SIGNING_MATERIAL_SCHEMA = "triad.receipt_signing_material.v1"

_INT64_RE = re.compile(r"(?:0|-[1-9][0-9]*|[1-9][0-9]*)")
_MILESTONE_RE = re.compile(r"B(0[1-9]|10)")
_CI_REVIEWER_RE = re.compile(r"(?i)github-actions|ci-run|workflow")

_CONFIG_KEYS = (
    "milestone", "receipt_id", "source_pr", "receipt_pr", "build_commit", "merge_commit",
    "source_head_sha", "reviewed_at_us", "source_merge_at_us", "observed_at_us",
    "emitted_at_us", "expires_at_us", "builder", "reviewer", "predecessor",
    "correction_of_receipt_ids", "ci_runs", "evidence",
)
_EVIDENCE_ROW_KEYS = ("evidence_id", "digest_role", "path", "producer", "observed_at_us", "media_type")
_CI_RUN_KEYS = ("run_id", "head_sha", "conclusion", "required_jobs_unskipped")
_PREDECESSOR_KEYS = ("id", "sha256")


class ConfigRefused(ValueError):
    """A named, fail-closed builder refusal."""


def _refuse(name: str, detail: str) -> ConfigRefused:
    return ConfigRefused(f"REFUSED {name}: {detail}")


# ---------------------------------------------------------------------------
# Wire-law helpers mirroring the frozen runner (behavioral copies; the
# differential test pins them to the runner's own functions).
# ---------------------------------------------------------------------------

def parse_canonical_int64(value: Any) -> int | None:
    """Parse the receipt wire law: a canonical signed-int64 base-10 string."""
    if not isinstance(value, str) or not _INT64_RE.fullmatch(value):
        return None
    parsed = int(value)
    if parsed < -(2**63) or parsed > 2**63 - 1:
        return None
    return parsed


def is_hex_sha(value: Any, length: int) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(rf"[0-9a-f]{{{length}}}", value))


def is_nonzero_sha256(value: Any) -> bool:
    return is_hex_sha(value, 64) and value != "0" * 64


def normalize_milestone_from_text(value: str) -> str | None:
    match = re.search(r"\bB(0[1-9]|10)(?:C|R)?\b", value.upper())
    return f"B{match.group(1)}" if match else None


class DuplicateJSONKey(ValueError):
    pass


def strict_json_loads(value: str) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise DuplicateJSONKey(f"duplicate JSON object key {key!r}")
            result[key] = item
        return result

    def reject_constant(token: str) -> Any:
        raise json.JSONDecodeError(f"non-finite JSON number {token}", value, 0)

    return json.loads(value, object_pairs_hook=reject_duplicates, parse_constant=reject_constant)


def jcs_canonical_bytes(value: Any) -> bytes:
    """RFC 8785 canonical bytes for the closed receipt domain.

    EMBEDDED minimal copy of the frozen runner's ``jcs_canonical_bytes`` — it must stay
    byte-identical in behavior to ``tools/jcs_canonical.py`` (when that module lands) and to
    the frozen runner; the differential test enforces output byte-equality.  Floating point
    is forbidden; integers must sit within the exact I-JSON range; object keys sort by their
    UTF-16BE code units.
    """
    def render(item: Any) -> str:
        if item is None:
            return "null"
        if item is True:
            return "true"
        if item is False:
            return "false"
        if isinstance(item, int):
            if abs(item) > 2**53 - 1:
                raise ValueError("receipt JCS integer exceeds exact I-JSON range")
            return str(item)
        if isinstance(item, float):
            raise ValueError("receipt JCS domain prohibits floating-point numbers")
        if isinstance(item, str):
            try:
                item.encode("utf-8", errors="strict")
            except UnicodeEncodeError as exc:
                raise ValueError("receipt JCS string contains an invalid surrogate") from exc
            return json.dumps(item, ensure_ascii=False, separators=(",", ":"))
        if isinstance(item, list):
            return "[" + ",".join(render(child) for child in item) + "]"
        if isinstance(item, dict):
            if not all(isinstance(key, str) for key in item):
                raise ValueError("receipt JCS object keys must be strings")

            def utf16_key(key: str) -> bytes:
                try:
                    return key.encode("utf-16be", errors="strict")
                except UnicodeEncodeError as exc:
                    raise ValueError("receipt JCS key contains an invalid surrogate") from exc

            keys = sorted(item, key=utf16_key)
            return "{" + ",".join(render(key) + ":" + render(item[key]) for key in keys) + "}"
        raise ValueError(f"receipt JCS domain rejects {type(item).__name__}")

    return render(value).encode("utf-8")


def dsse_pae(payload_type: str, payload: bytes) -> bytes:
    """DSSE pre-authentication encoding — behavioral copy of the frozen runner's dsse_pae."""
    type_bytes = payload_type.encode("utf-8")
    return (
        b"DSSEv1 " + str(len(type_bytes)).encode() + b" " + type_bytes
        + b" " + str(len(payload)).encode() + b" " + payload
    )


def strict_base64(value: Any, expected_length: int | None = None) -> bytes | None:
    if not isinstance(value, str):
        return None
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return None
    if expected_length is not None and len(decoded) != expected_length:
        return None
    return decoded


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def walk_named_values(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    if isinstance(value, dict):
        for key, item in value.items():
            current = path + (str(key),)
            yield current, item
            yield from walk_named_values(item, current)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk_named_values(item, path + (str(index),))


def deterministic_json_bytes(value: Any) -> bytes:
    """Ceremony-fixed file bytes: json.dumps(sort_keys=True, indent=2) + trailing newline."""
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")


# ---------------------------------------------------------------------------
# Config validation + payload construction (fail-closed, named refusals).
# ---------------------------------------------------------------------------

def _require_int64_field(config: dict[str, Any], key: str) -> int:
    parsed = parse_canonical_int64(config.get(key))
    if parsed is None:
        raise _refuse(
            "BAD_INT64", f"config {key} is not a canonical signed-int64 base-10 string")
    return parsed


def _resolve_evidence_path(repo_root: pathlib.Path, reference: str, index: int) -> pathlib.Path:
    if re.match(r"https?://", reference):
        raise _refuse(
            "BAD_EVIDENCE_PATH",
            f"evidence[{index}] remote URI {reference!r} refused; a bundled local repo-relative "
            "preimage is required")
    if pathlib.Path(reference).is_absolute():
        raise _refuse(
            "BAD_EVIDENCE_PATH",
            f"evidence[{index}] path {reference!r} must be repo-relative, not absolute")
    root = repo_root.resolve()
    raw_candidate = root / pathlib.Path(reference)
    candidate = raw_candidate.resolve()
    if candidate != root and root not in candidate.parents:
        raise _refuse(
            "EVIDENCE_PATH_ESCAPES_REPO", f"evidence[{index}] path {reference!r} escapes {root}")
    if raw_candidate.is_symlink():
        raise _refuse(
            "EVIDENCE_PATH_SYMLINK", f"evidence[{index}] preimage is a symbolic link: {reference}")
    if not candidate.is_file():
        raise _refuse(
            "EVIDENCE_PREIMAGE_MISSING", f"evidence[{index}] preimage is missing: {reference}")
    return candidate


def _validate_profile_decision_preimage(path: pathlib.Path, digest: str, pin: str) -> None:
    if digest != pin:
        raise _refuse(
            "PROFILE_DECISION_PIN_MISMATCH",
            f"RECEIPT_PROFILE_DECISION preimage sha256 {digest} does not equal the external "
            f"--profile-decision-sha256 pin {pin}")
    try:
        decision = strict_json_loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, DuplicateJSONKey) as exc:
        raise _refuse(
            "PROFILE_DECISION_CONTENT_INVALID",
            f"RECEIPT_PROFILE_DECISION preimage is unreadable or invalid JSON: {exc}")
    if decision != RECEIPT_PROFILE_DECISION:
        raise _refuse(
            "PROFILE_DECISION_CONTENT_INVALID",
            "RECEIPT_PROFILE_DECISION preimage content is not the closed ratified "
            "DECISION-RECEIPT-PROFILE-001 object")


def build_receipt_event(
    config: dict[str, Any],
    repo_root: pathlib.Path,
    trust_registry_sha256: str,
    profile_decision_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate the config, hash the evidence preimages, and build (event, signing_material)."""
    if not isinstance(config, dict):
        raise _refuse("BAD_CONFIG_ROOT", "config root must be a JSON object")
    unknown = sorted(set(map(str, config)) - set(_CONFIG_KEYS))
    if unknown:
        raise _refuse("UNKNOWN_CONFIG_KEY", f"config carries unknown keys {unknown}")
    missing = sorted(key for key in _CONFIG_KEYS if key not in config)
    if missing:
        raise _refuse("MISSING_CONFIG_KEY", f"config lacks required keys {missing}")
    if not is_nonzero_sha256(trust_registry_sha256):
        raise _refuse(
            "BAD_PIN", "--trust-registry-sha256 must be a non-zero lowercase 64-hex SHA-256")
    if not is_nonzero_sha256(profile_decision_sha256):
        raise _refuse(
            "BAD_PIN", "--profile-decision-sha256 must be a non-zero lowercase 64-hex SHA-256")

    milestone = config["milestone"]
    if not isinstance(milestone, str) or not _MILESTONE_RE.fullmatch(milestone):
        raise _refuse("BAD_MILESTONE", f"milestone {milestone!r} is not B01..B10")

    receipt_id = config["receipt_id"]
    if not isinstance(receipt_id, str) or not receipt_id.strip():
        raise _refuse("BAD_RECEIPT_ID", "receipt_id must be a nonempty string")

    source_pr = config["source_pr"]
    receipt_pr = config["receipt_pr"]
    for name, value in (("source_pr", source_pr), ("receipt_pr", receipt_pr)):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise _refuse("BAD_PR_NUMBER", f"{name} must be a positive integer")
    if source_pr == receipt_pr:
        raise _refuse(
            "SAME_SOURCE_AND_RECEIPT_PR",
            "source_pr and receipt_pr must be different pull requests")

    build_commit = config["build_commit"]
    merge_commit = config["merge_commit"]
    source_head_sha = config["source_head_sha"]
    for name, value in (
        ("build_commit", build_commit), ("merge_commit", merge_commit),
        ("source_head_sha", source_head_sha),
    ):
        if not is_hex_sha(value, 40) or value == "0" * 40:
            raise _refuse("BAD_COMMIT", f"{name} must be a real exact lowercase 40-hex commit")
    if build_commit != merge_commit:
        raise _refuse(
            "BUILD_MERGE_COMMIT_MISMATCH", "build_commit and merge_commit must be identical")

    reviewed_at_us = _require_int64_field(config, "reviewed_at_us")
    source_merge_at_us = _require_int64_field(config, "source_merge_at_us")
    observed_at_us = _require_int64_field(config, "observed_at_us")
    emitted_at_us = _require_int64_field(config, "emitted_at_us")
    expires_at_us = _require_int64_field(config, "expires_at_us")

    # Chronology law — refuse violations BY NAME (mirrors receipt_issues).
    if reviewed_at_us > source_merge_at_us:
        raise _refuse(
            "REVIEWED_AFTER_SOURCE_MERGE",
            f"reviewed_at_us {reviewed_at_us} > source_merge_at_us {source_merge_at_us}")
    if observed_at_us < source_merge_at_us:
        raise _refuse(
            "OBSERVED_BEFORE_SOURCE_MERGE",
            f"observed_at_us {observed_at_us} < source_merge_at_us {source_merge_at_us}")
    if emitted_at_us < observed_at_us:
        raise _refuse(
            "EMITTED_BEFORE_OBSERVED",
            f"emitted_at_us {emitted_at_us} < observed_at_us {observed_at_us}")
    ttl = expires_at_us - emitted_at_us
    if ttl <= 0:
        raise _refuse(
            "TTL_NOT_POSITIVE", f"expires_at_us - emitted_at_us = {ttl} must be positive")
    if ttl > MAX_RECEIPT_TTL_US:
        raise _refuse(
            "TTL_EXCEEDS_MAX",
            f"expires_at_us - emitted_at_us = {ttl} exceeds {MAX_RECEIPT_TTL_US} (30 days)")

    builder = config["builder"]
    reviewer = config["reviewer"]
    if (not isinstance(builder, str) or not builder.strip()
            or not isinstance(reviewer, str) or not reviewer.strip()):
        raise _refuse("BAD_BUILDER_REVIEWER", "builder and reviewer must be nonempty strings")
    if builder.strip() == reviewer.strip():
        raise _refuse("BAD_BUILDER_REVIEWER", "builder and reviewer must be independent")
    if _CI_REVIEWER_RE.search(reviewer):
        raise _refuse(
            "REVIEWER_IS_CI",
            f"reviewer {reviewer!r} names a CI run; this is not independent review")

    predecessor = config["predecessor"]
    if milestone == "B01":
        if predecessor is not None:
            raise _refuse(
                "PREDECESSOR_FORBIDDEN_FOR_B01",
                "B01 is the chain root; predecessor must be null")
    else:
        if not isinstance(predecessor, dict):
            raise _refuse(
                "PREDECESSOR_REQUIRED", f"milestone {milestone} requires predecessor {{id, sha256}}")
        if set(predecessor) != set(_PREDECESSOR_KEYS):
            raise _refuse(
                "BAD_PREDECESSOR", f"predecessor keys must be exactly {list(_PREDECESSOR_KEYS)}")
        if not isinstance(predecessor["id"], str) or not predecessor["id"].strip():
            raise _refuse("BAD_PREDECESSOR", "predecessor.id must be a nonempty string")
        if not is_nonzero_sha256(predecessor["sha256"]):
            raise _refuse(
                "BAD_PREDECESSOR",
                "predecessor.sha256 must be a non-zero lowercase 64-hex SHA-256")

    corrections = config["correction_of_receipt_ids"]
    if not isinstance(corrections, list) or any(
            not isinstance(item, str) or not item for item in corrections):
        raise _refuse(
            "BAD_CORRECTIONS", "correction_of_receipt_ids must be an array of nonempty IDs")

    ci_runs = config["ci_runs"]
    if not isinstance(ci_runs, list) or not ci_runs:
        raise _refuse("BAD_CI_RUNS", "ci_runs must be a nonempty array of run objects")
    has_valid_ci = False
    for index, run in enumerate(ci_runs):
        if not isinstance(run, dict):
            raise _refuse("BAD_CI_RUNS", f"ci_runs[{index}] is not an object")
        if set(run) != set(_CI_RUN_KEYS):
            raise _refuse(
                "BAD_CI_RUNS", f"ci_runs[{index}] keys must be exactly {list(_CI_RUN_KEYS)}")
        run_id = run["run_id"]
        if isinstance(run_id, bool) or not isinstance(run_id, int) or run_id <= 0:
            raise _refuse("BAD_CI_RUNS", f"ci_runs[{index}].run_id must be a positive integer")
        if not is_hex_sha(run["head_sha"], 40):
            raise _refuse("BAD_CI_RUNS", f"ci_runs[{index}].head_sha must be lowercase 40-hex")
        if not isinstance(run["conclusion"], str) or not run["conclusion"]:
            raise _refuse("BAD_CI_RUNS", f"ci_runs[{index}].conclusion must be a nonempty string")
        if not isinstance(run["required_jobs_unskipped"], bool):
            raise _refuse(
                "BAD_CI_RUNS", f"ci_runs[{index}].required_jobs_unskipped must be a boolean")
        if (run["head_sha"] == source_head_sha and run["conclusion"] == "SUCCESS"
                and run["required_jobs_unskipped"] is True):
            has_valid_ci = True
    if not has_valid_ci:
        raise _refuse(
            "NO_VALID_CI_RUN",
            "ci_runs must contain at least one SUCCESS run with required_jobs_unskipped=true "
            "bound to source_head_sha")

    evidence_config = config["evidence"]
    if not isinstance(evidence_config, list) or not evidence_config:
        raise _refuse("BAD_EVIDENCE_ROW", "evidence must be a nonempty array of typed rows")
    evidence_rows: list[dict[str, Any]] = []
    role_hashes: dict[str, str] = {}
    seen_evidence_ids: set[str] = set()
    for index, row in enumerate(evidence_config):
        if not isinstance(row, dict):
            raise _refuse("BAD_EVIDENCE_ROW", f"evidence[{index}] is not an object")
        unknown_keys = sorted(set(map(str, row)) - set(_EVIDENCE_ROW_KEYS))
        if unknown_keys:
            raise _refuse(
                "UNKNOWN_EVIDENCE_KEY",
                f"evidence[{index}] carries unknown keys {unknown_keys}; sha256 digests are "
                "computed by this builder from the preimages, never supplied")
        missing_keys = sorted(key for key in _EVIDENCE_ROW_KEYS if key not in row)
        if missing_keys:
            raise _refuse(
                "MISSING_EVIDENCE_KEY", f"evidence[{index}] lacks required keys {missing_keys}")
        evidence_id = row["evidence_id"]
        if not isinstance(evidence_id, str) or not evidence_id.strip():
            raise _refuse(
                "BAD_EVIDENCE_ROW", f"evidence[{index}] lacks a stable nonempty evidence_id")
        if evidence_id in seen_evidence_ids:
            raise _refuse(
                "DUPLICATE_EVIDENCE_ID", f"evidence[{index}] duplicates evidence_id {evidence_id!r}")
        seen_evidence_ids.add(evidence_id)
        digest_role = row["digest_role"]
        if digest_role not in ALLOWED_EVIDENCE_ROLES:
            raise _refuse(
                "BAD_EVIDENCE_ROLE", f"evidence[{index}] digest_role {digest_role!r} is invalid")
        producer = row["producer"]
        if not isinstance(producer, str) or not producer.strip():
            raise _refuse("BAD_PRODUCER", f"evidence[{index}] lacks producer identity")
        row_observed = parse_canonical_int64(row["observed_at_us"])
        if row_observed is None:
            raise _refuse(
                "BAD_INT64", f"evidence[{index}].observed_at_us is not a canonical int64 string")
        if not source_merge_at_us <= row_observed <= observed_at_us:
            raise _refuse(
                "EVIDENCE_OBSERVED_OUT_OF_WINDOW",
                f"evidence[{index}].observed_at_us {row_observed} is outside "
                f"[source_merge_at_us {source_merge_at_us}, observed_at_us {observed_at_us}]")
        media_type = row["media_type"]
        if not isinstance(media_type, str) or "/" not in media_type:
            raise _refuse("BAD_MEDIA_TYPE", f"evidence[{index}] lacks a type/subtype media_type")
        reference = row["path"]
        if not isinstance(reference, str) or not reference:
            raise _refuse("BAD_EVIDENCE_PATH", f"evidence[{index}] lacks a repo-relative path")
        preimage = _resolve_evidence_path(repo_root, reference, index)
        digest = sha256_file(preimage)
        if digest_role in {role for _, role in REQUIRED_RECEIPT_DIGEST_ROLES}:
            if digest_role in role_hashes:
                raise _refuse(
                    "DUPLICATE_EVIDENCE_ROLE",
                    f"required digest_role {digest_role} appears more than once")
            role_hashes[digest_role] = digest
            if digest_role == "RECEIPT_PROFILE_DECISION":
                _validate_profile_decision_preimage(preimage, digest, profile_decision_sha256)
        evidence_rows.append({
            "evidence_id": evidence_id,
            "path": reference,
            "sha256": digest,
            "digest_role": digest_role,
            "producer": producer,
            "observed_at_us": row["observed_at_us"],
            "media_type": media_type,
        })
    for _field, role in REQUIRED_RECEIPT_DIGEST_ROLES:
        if role not in role_hashes:
            raise _refuse(
                "MISSING_REQUIRED_DIGEST_ROLE",
                f"no evidence row carries required digest_role {role}")

    payload: dict[str, Any] = {
        "receipt_id": receipt_id,
        "milestone_id": milestone,
        "receipt_kind": "TERMINAL_REPOSITORY" if milestone == "B10" else "MILESTONE_SOURCE",
        "scope": {
            "repository": EXPECTED_REPOSITORY,
            "milestone": milestone,
            "execution_plane": "OFF",
            "environment": "REPOSITORY",
            "authority": "REPOSITORY_ONLY",
        },
        "result": PASS,
        "status": "CURRENT",
        "open_blockers": [],
        "builder": builder,
        "reviewer": reviewer,
        "source_pr": source_pr,
        "receipt_pr": receipt_pr,
        "build_commit": build_commit,
        "merge_commit": merge_commit,
        "source_head_sha": source_head_sha,
        "review_head_sha": source_head_sha,
        "reviewed_at_us": config["reviewed_at_us"],
        "unresolved_p0_p1": 0,
        "ci_runs": ci_runs,
        "governance": dict(GOVERNANCE),
        "correction_of_receipt_ids": corrections,
        **{field: role_hashes[role] for field, role in REQUIRED_RECEIPT_DIGEST_ROLES},
        "source_merge_at_us": config["source_merge_at_us"],
        "observed_at_us": config["observed_at_us"],
        "emitted_at_us": config["emitted_at_us"],
        "expires_at_us": config["expires_at_us"],
        "trust_registry_sha256": trust_registry_sha256,
        "evidence": evidence_rows,
        "evidence_ids": [row["evidence_id"] for row in evidence_rows],
        "evidence_sha256s": [row["sha256"] for row in evidence_rows],
    }
    if milestone != "B01":
        assert isinstance(predecessor, dict)
        payload["predecessor_receipt_id"] = predecessor["id"]
        payload["predecessor_receipt_sha256"] = predecessor["sha256"]

    payload_bytes = jcs_canonical_bytes(payload)
    pae = dsse_pae(RECEIPT_PAYLOAD_TYPE, payload_bytes)
    event = {
        "schema": RECEIPT_SCHEMA,
        "payload": payload,
        "dsse": {
            "payloadType": RECEIPT_PAYLOAD_TYPE,
            "payload": base64.b64encode(payload_bytes).decode("ascii"),
            "signatures": [],
        },
    }
    signing_material = {
        "schema": SIGNING_MATERIAL_SCHEMA,
        "receipt_id": receipt_id,
        "milestone_id": milestone,
        "payload_type": RECEIPT_PAYLOAD_TYPE,
        "payload_b64": event["dsse"]["payload"],
        "payload_sha256": sha256_bytes(payload_bytes),
        "pae_hex": pae.hex(),
        "pae_sha256": sha256_bytes(pae),
        "instructions": (
            "Sign the PAE bytes (hex-decode pae_hex) with each approved Ed25519 signer, "
            "EXTERNALLY to this repository toolchain; append {\"keyid\": <registry key_id>, "
            "\"sig\": <base64 signature>} rows to dsse.signatures in the receipt event. "
            "This builder never signs and never handles private key material."
        ),
    }
    return event, signing_material


# ---------------------------------------------------------------------------
# --self-check: independent re-validation of the written draft against every
# unsigned-checkable clause of the frozen runner's receipt law.
# ---------------------------------------------------------------------------

def draft_issues(
    path: pathlib.Path,
    milestone: str,
    *,
    repository_root: pathlib.Path,
    trust_registry_sha256: str,
    receipt_profile_decision_sha256: str,
    now_us: int | None = None,
) -> list[str]:
    """Every unsigned-checkable clause of the runner's ``receipt_issues``, re-derived from bytes.

    Signature-verification clauses (two verified DSSE signers, roles, builder/reviewer signer
    binding) are deliberately OUT of scope: the draft is unsigned by design.  When ``now_us``
    is provided the verifier-time clauses (zero future tolerance, not expired) are checked too.
    """
    issues: list[str] = []
    try:
        event = strict_json_loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, DuplicateJSONKey) as exc:
        return [f"receipt is unreadable or invalid JSON: {exc}"]
    if not isinstance(event, dict):
        return ["receipt root must be an object"]
    if event.get("schema") != RECEIPT_SCHEMA:
        issues.append(f"receipt schema is not {RECEIPT_SCHEMA}")
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else event
    scope = payload.get("scope") if isinstance(payload.get("scope"), dict) else {}
    claimed_raw = payload.get("milestone_id") or scope.get("milestone")
    claimed = normalize_milestone_from_text(str(claimed_raw or path.stem))
    if claimed != milestone:
        issues.append(f"receipt scope milestone {claimed_raw!r} does not match {milestone}")
    if payload.get("result") != PASS:
        issues.append("receipt result must be exactly PASS")
    if payload.get("status") != "CURRENT":
        issues.append("receipt status must be exactly CURRENT")
    expected_kind = "TERMINAL_REPOSITORY" if milestone == "B10" else "MILESTONE_SOURCE"
    if payload.get("receipt_kind") != expected_kind:
        issues.append(f"receipt_kind must be exactly {expected_kind}")
    open_blockers = payload.get("open_blockers")
    if not isinstance(open_blockers, list):
        issues.append("receipt open_blockers must be an array")
    elif open_blockers:
        issues.append("PASS receipt has non-empty open_blockers")

    receipt_id = payload.get("receipt_id")
    if not isinstance(receipt_id, str) or not receipt_id.strip():
        issues.append("receipt_id is missing")
    source_pr = payload.get("source_pr")
    if isinstance(source_pr, bool) or not isinstance(source_pr, int) or source_pr <= 0:
        issues.append("source_pr must be a positive integer")
    receipt_pr = payload.get("receipt_pr")
    if isinstance(receipt_pr, bool) or not isinstance(receipt_pr, int) or receipt_pr <= 0:
        issues.append("receipt_pr must be a positive integer")
    if isinstance(source_pr, int) and isinstance(receipt_pr, int) and source_pr == receipt_pr:
        issues.append("source_pr and receipt_pr must be different pull requests")
    if milestone != "B01":
        if not isinstance(payload.get("predecessor_receipt_id"), str) or not payload.get(
                "predecessor_receipt_id"):
            issues.append("predecessor_receipt_id is missing")
        if not is_nonzero_sha256(payload.get("predecessor_receipt_sha256")):
            issues.append("predecessor_receipt_sha256 is missing or invalid")

    build_commit = payload.get("build_commit")
    merge_commit = payload.get("merge_commit")
    if not is_hex_sha(build_commit, 40) or build_commit == "0" * 40:
        issues.append("receipt lacks a real exact 40-hex build/merge commit")
    if not is_hex_sha(merge_commit, 40) or merge_commit == "0" * 40:
        issues.append("receipt lacks a real exact 40-hex merge_commit")
    elif build_commit != merge_commit:
        issues.append("build_commit and merge_commit differ")
    source_head_sha = payload.get("source_head_sha")
    if not is_hex_sha(source_head_sha, 40) or source_head_sha == "0" * 40:
        issues.append("receipt source_head_sha is not a real exact 40-hex PR head")
    if payload.get("review_head_sha") != source_head_sha:
        issues.append("receipt independent review is not bound to source_head_sha")
    reviewed_at_us = parse_canonical_int64(payload.get("reviewed_at_us"))
    if reviewed_at_us is None:
        issues.append("receipt reviewed_at_us is not a canonical int64 string")
    if payload.get("unresolved_p0_p1") != 0:
        issues.append("receipt unresolved_p0_p1 must be integer zero")
    ci_runs = payload.get("ci_runs")
    valid_ci = False
    if not isinstance(ci_runs, list) or not ci_runs:
        issues.append("receipt ci_runs must contain exact-head CI evidence")
    else:
        for run in ci_runs:
            if (
                isinstance(run, dict)
                and isinstance(run.get("run_id"), int) and not isinstance(run.get("run_id"), bool)
                and run.get("run_id") > 0 and run.get("head_sha") == source_head_sha
                and run.get("conclusion") == "SUCCESS"
                and run.get("required_jobs_unskipped") is True
            ):
                valid_ci = True
        if not valid_ci:
            issues.append("receipt has no successful unskipped CI run bound to source_head_sha")
    governance = payload.get("governance")
    if not isinstance(governance, dict) or set(governance) != {"branch_rules_enforced", "bypass_used"}:
        issues.append("receipt governance must be the closed branch-rules/bypass object")
    elif governance != GOVERNANCE:
        issues.append("receipt governance does not prove enforced rules and no bypass")
    corrections = payload.get("correction_of_receipt_ids")
    if not isinstance(corrections, list) or any(
            not isinstance(item, str) or not item for item in corrections):
        issues.append("receipt correction_of_receipt_ids must be an array of nonempty IDs")

    expected_scope = {
        "repository": EXPECTED_REPOSITORY,
        "milestone": milestone,
        "execution_plane": "OFF",
        "environment": "REPOSITORY",
        "authority": "REPOSITORY_ONLY",
    }
    if set(scope) != set(expected_scope):
        issues.append("receipt scope keys are not the exact closed repository-milestone set")
    for key, expected in expected_scope.items():
        actual = scope.get(key)
        comparable = actual.lower() if key == "repository" and isinstance(actual, str) else actual
        if comparable != expected:
            issues.append(f"receipt scope {key}={actual!r}; expected {expected!r}")

    for field, role in REQUIRED_RECEIPT_DIGEST_ROLES:
        if not is_nonzero_sha256(payload.get(field)):
            issues.append(f"required {role} digest {field} is not a non-zero lowercase SHA-256")
    if payload.get("receipt_profile_decision_sha256") != receipt_profile_decision_sha256:
        issues.append(
            "receipt_profile_decision_sha256 does not match the external "
            "DECISION-RECEIPT-PROFILE-001 pin")
    if payload.get("trust_registry_sha256") != trust_registry_sha256:
        issues.append("signed receipt trust_registry_sha256 does not match external pin")

    digest_fields: list[tuple[str, str]] = []
    for field_path, value in walk_named_values(event):
        key = field_path[-1].lower() if field_path else ""
        if "sha256" in key or key.endswith("_digest") or key in {"digest", "signature_preimage_digest"}:
            if isinstance(value, str):
                digest_fields.append((".".join(field_path), value))
    if not digest_fields:
        issues.append("receipt has no independently recomputable digest fields")
    for field_name, value in digest_fields:
        if not is_nonzero_sha256(value):
            issues.append(f"receipt digest {field_name} is not a non-zero lowercase SHA-256")

    evidence_rows = payload.get("evidence")
    if not isinstance(evidence_rows, list) or not evidence_rows:
        issues.append("receipt has no typed evidence entries")
        evidence_rows = []
    evidence_ids: list[str] = []
    evidence_hashes: list[str] = []
    role_hashes: dict[str, str] = {}
    evidence_observed: list[tuple[int, int]] = []
    root = repository_root.resolve()
    for index, row in enumerate(evidence_rows):
        if not isinstance(row, dict):
            issues.append(f"evidence[{index}] is not an object")
            continue
        evidence_id = row.get("evidence_id")
        digest = row.get("sha256")
        digest_role = row.get("digest_role")
        evidence_ids.append(str(evidence_id) if evidence_id is not None else "")
        evidence_hashes.append(str(digest) if digest is not None else "")
        if not isinstance(evidence_id, str) or not evidence_id.strip():
            issues.append(f"evidence[{index}] lacks a stable evidence_id")
        if not is_nonzero_sha256(digest):
            issues.append(f"evidence[{index}] digest is not a real non-zero SHA-256")
        if digest_role not in ALLOWED_EVIDENCE_ROLES:
            issues.append(f"evidence[{index}] has invalid digest_role {digest_role!r}")
        elif digest_role in role_hashes:
            issues.append(f"evidence digest_role {digest_role} is duplicated")
        elif isinstance(digest, str):
            role_hashes[str(digest_role)] = digest
        if not isinstance(row.get("producer"), str) or not row.get("producer", "").strip():
            issues.append(f"evidence[{index}] lacks producer identity")
        observed_item = parse_canonical_int64(row.get("observed_at_us"))
        if observed_item is None:
            issues.append(f"evidence[{index}] lacks canonical observed_at_us")
        else:
            evidence_observed.append((index, observed_item))
        if not isinstance(row.get("media_type"), str) or "/" not in row.get("media_type", ""):
            issues.append(f"evidence[{index}] lacks media_type")
        reference = row.get("path") or row.get("uri")
        if not isinstance(reference, str) or not reference:
            issues.append(f"evidence[{index}] lacks immutable path/URI")
            continue
        if re.match(r"https?://", reference):
            issues.append(
                f"evidence[{index}] remote URI is not fetched by this verifier; "
                "a bundled local preimage is required")
            continue
        raw_candidate = root / pathlib.Path(reference)
        candidate = raw_candidate.resolve()
        if candidate != root and root not in candidate.parents:
            issues.append(f"evidence[{index}] path escapes repository")
        elif raw_candidate.is_symlink():
            issues.append(f"evidence[{index}] preimage is a symbolic link: {reference}")
        elif not candidate.is_file():
            issues.append(f"evidence[{index}] preimage is missing: {reference}")
        elif is_nonzero_sha256(digest):
            if sha256_file(candidate) != digest:
                issues.append(f"evidence[{index}] preimage digest mismatch: {reference}")
            elif digest_role == "RECEIPT_PROFILE_DECISION":
                try:
                    decision = strict_json_loads(candidate.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError, json.JSONDecodeError, DuplicateJSONKey) as exc:
                    issues.append(f"receipt-profile decision is unreadable or invalid JSON: {exc}")
                else:
                    if decision != RECEIPT_PROFILE_DECISION:
                        issues.append(
                            "receipt-profile decision content does not match the closed "
                            "ratified profile")
                if str(digest) != receipt_profile_decision_sha256:
                    issues.append("receipt-profile decision bytes do not match the external pin")
    if len(set(evidence_ids)) != len(evidence_ids):
        issues.append("evidence IDs are duplicated")
    for field, role in REQUIRED_RECEIPT_DIGEST_ROLES:
        if role_hashes.get(role) != payload.get(field):
            issues.append(
                f"required digest {field} is not recomputed from exactly one typed {role} preimage")
    declared_ids = payload.get("evidence_ids")
    declared_hashes = payload.get("evidence_sha256s")
    if declared_ids is not None or declared_hashes is not None:
        if not isinstance(declared_ids, list) or not isinstance(declared_hashes, list):
            issues.append("parallel evidence_ids/evidence_sha256s must both be arrays when present")
        elif len(declared_ids) != len(declared_hashes):
            issues.append("evidence_ids and evidence_sha256s cardinality differ")
        elif declared_ids != evidence_ids or declared_hashes != evidence_hashes:
            issues.append("parallel evidence IDs/hashes disagree with typed evidence entries")

    time_fields = {
        "source_merge_at_us": parse_canonical_int64(payload.get("source_merge_at_us")),
        "observed_at_us": parse_canonical_int64(payload.get("observed_at_us")),
        "emitted_at_us": parse_canonical_int64(payload.get("emitted_at_us")),
        "expires_at_us": parse_canonical_int64(payload.get("expires_at_us")),
    }
    for key, value in time_fields.items():
        if value is None:
            issues.append(f"receipt {key} is not a canonical signed-int64 base-10 string")
    if all(value is not None for value in time_fields.values()):
        source_merge_us = int(time_fields["source_merge_at_us"] or 0)
        observed_us = int(time_fields["observed_at_us"] or 0)
        emitted_us = int(time_fields["emitted_at_us"] or 0)
        expires_us = int(time_fields["expires_at_us"] or 0)
        if reviewed_at_us is not None and reviewed_at_us > source_merge_us:
            issues.append("receipt review completed after the source merge")
        if not source_merge_us <= observed_us <= emitted_us:
            issues.append("receipt chronology is not source_merge <= observed <= emitted")
        for index, item_observed_us in evidence_observed:
            if not source_merge_us <= item_observed_us <= observed_us:
                issues.append(
                    f"evidence[{index}] chronology is not "
                    "source_merge <= evidence_observed <= receipt_observed")
        ttl = expires_us - emitted_us
        if ttl <= 0 or ttl > MAX_RECEIPT_TTL_US:
            issues.append("receipt validity must be positive and at most 30 days")
        if now_us is not None:
            if emitted_us > now_us + REPOSITORY_FUTURE_TOLERANCE_US:
                issues.append(
                    "receipt claims evidence from the future; repository/provider evidence "
                    "has zero future tolerance")
            if expires_us <= now_us:
                issues.append("receipt is expired at verifier time")

    builder = str(payload.get("builder", "")).strip()
    reviewer = str(payload.get("reviewer", "")).strip()
    if not builder or not reviewer or builder == reviewer:
        issues.append("receipt builder and reviewer are missing or not independent")
    if _CI_REVIEWER_RE.search(reviewer):
        issues.append("a CI run is recorded as reviewer; this is not independent review")
    if "signature" in payload:
        issues.append("draft payload must not carry an embedded signature field")

    envelope = event.get("dsse") or event.get("envelope")
    if not isinstance(envelope, dict):
        issues.append("receipt has no DSSE envelope")
    else:
        if envelope.get("payloadType") != RECEIPT_PAYLOAD_TYPE:
            issues.append("DSSE payloadType is not the closed receipt-v3 media type")
        encoded_payload = strict_base64(envelope.get("payload"))
        if encoded_payload is None:
            issues.append("DSSE payload is not strict base64")
        else:
            try:
                canonical_payload = jcs_canonical_bytes(payload)
            except ValueError as exc:
                canonical_payload = None
                issues.append(f"receipt payload is outside the closed RFC 8785 domain: {exc}")
            if canonical_payload is not None and encoded_payload != canonical_payload:
                issues.append("DSSE payload bytes do not equal RFC 8785 canonical receipt payload")
        if not isinstance(envelope.get("signatures"), list):
            issues.append("DSSE signatures must be an array (empty while unsigned)")
    return list(dict.fromkeys(issues))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def repo_root_of_tool() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent


def refuse_out_inside_repo(out_path: pathlib.Path, allow_in_repo: bool) -> str | None:
    if allow_in_repo:
        return None
    resolved = out_path.resolve()
    root = repo_root_of_tool()
    if resolved == root or root in resolved.parents:
        return (
            f"REFUSED OUT_PATH_INSIDE_REPOSITORY: {resolved} is inside repository root {root}; "
            "the tree-mutation law forbids writing into the repository "
            "(pass --allow-in-repo only for a deliberate ceremony-recorded in-repo write)"
        )
    return None


def sidecar_path_for(out_path: pathlib.Path) -> pathlib.Path:
    """``receipt.json`` -> ``receipt.signing.json`` (suffix replaced; no-suffix names append)."""
    return out_path.with_suffix(".signing.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Build an UNSIGNED triad.evidence_receipt.v3 draft + signing preimages.")
    parser.add_argument("--config", required=True, help="receipt config JSON path")
    parser.add_argument("--repo", required=True, help="repository root for evidence preimages (read-only)")
    parser.add_argument("--trust-registry-sha256", required=True,
                        help="external trust-registry file-bytes SHA-256 pin")
    parser.add_argument("--profile-decision-sha256", required=True,
                        help="external DECISION-RECEIPT-PROFILE-001 file-bytes SHA-256 pin")
    parser.add_argument("--out", required=True, help="output receipt path (outside the repository)")
    parser.add_argument("--allow-in-repo", action="store_true",
                        help="permit writing inside the repository root (tree-mutation law override)")
    parser.add_argument("--self-check", action="store_true",
                        help="re-validate the written draft against every unsigned-checkable clause")
    parser.add_argument("--now-us", default=None,
                        help="optional canonical int64 verifier time for the future/expiry clauses")
    args = parser.parse_args(argv)

    out_path = pathlib.Path(args.out)
    refusal = refuse_out_inside_repo(out_path, args.allow_in_repo)
    if refusal is not None:
        print(refusal, file=sys.stderr)
        return 2
    sidecar = sidecar_path_for(out_path)
    refusal = refuse_out_inside_repo(sidecar, args.allow_in_repo)
    if refusal is not None:
        print(refusal, file=sys.stderr)
        return 2
    now_us: int | None = None
    if args.now_us is not None:
        now_us = parse_canonical_int64(args.now_us)
        if now_us is None:
            print("REFUSED BAD_INT64: --now-us is not a canonical signed-int64 base-10 string",
                  file=sys.stderr)
            return 2

    repo_root = pathlib.Path(args.repo)
    if not repo_root.is_dir():
        print(f"REFUSED BAD_REPO_ROOT: {repo_root} is not a directory", file=sys.stderr)
        return 2
    try:
        config_text = pathlib.Path(args.config).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"REFUSED CONFIG_UNREADABLE: {exc}", file=sys.stderr)
        return 2
    try:
        config = strict_json_loads(config_text)
    except (json.JSONDecodeError, DuplicateJSONKey) as exc:
        print(f"REFUSED CONFIG_INVALID_JSON: {exc}", file=sys.stderr)
        return 2
    try:
        event, signing_material = build_receipt_event(
            config, repo_root, args.trust_registry_sha256, args.profile_decision_sha256)
    except ConfigRefused as exc:
        print(str(exc), file=sys.stderr)
        return 2

    event_bytes = deterministic_json_bytes(event)
    signing_bytes = deterministic_json_bytes(signing_material)
    try:
        out_path.resolve().parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(event_bytes)
        sidecar.write_bytes(signing_bytes)
    except OSError as exc:
        print(f"REFUSED OUT_PATH_UNWRITABLE: {exc}", file=sys.stderr)
        return 2
    print(f"receipt_sha256 {sha256_bytes(event_bytes)}")
    print(f"signing_material_sha256 {sha256_bytes(signing_bytes)}")

    if args.self_check:
        milestone = str(config.get("milestone", ""))
        issues = draft_issues(
            out_path, milestone,
            repository_root=repo_root,
            trust_registry_sha256=args.trust_registry_sha256,
            receipt_profile_decision_sha256=args.profile_decision_sha256,
            now_us=now_us,
        )
        for issue in issues:
            print(f"self-check ISSUE: {issue}")
        print(f"self-check issues: {len(issues)}")
        if issues:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
