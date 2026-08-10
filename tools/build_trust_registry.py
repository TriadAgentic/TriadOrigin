#!/usr/bin/env python3
"""Build a ``triad.receipt_trust_registry.v1`` DRAFT from an operator-supplied spec.

The output mirrors the registry law the frozen audit runner
(``audit_package/triad_origin_b01_b10_audit.py``, v1.2.0) enforces when it consumes a pinned
trust registry inside ``receipt_issues``/``verify_offline_github_envelope`` and in its own
fixture registries: a root object ``{"schema": "triad.receipt_trust_registry.v1", "keys": [...]}``
whose rows carry ``key_id`` (unique) · ``identity`` · ``role`` in {PRODUCER, COUNTERSIGNER,
AUDITOR} · ``algorithm`` forced ``"Ed25519"`` · ``status`` forced ``"ACTIVE"`` ·
``public_key_base64`` (strict base64 of exactly 32 bytes — an Ed25519 PUBLIC key) ·
``valid_from_us``/``valid_until_us`` (the runner's canonical signed-int64 base-10 string
grammar) · ``approved_milestones`` (``"ALL"`` / ``["ALL"]`` / a list of B01..B10 ids) ·
optional ``revoked_at_us``.

PUBLIC KEYS ONLY: this tool refuses — as a hard error — any spec field whose NAME suggests
private material (seed / private / secret / passphrase / mnemonic), anywhere in the spec.
It never loads, derives, or signs with a private key.

BYTE LAW: the external ceremony PIN is the SHA-256 over the FILE BYTES; the bytes are
ceremony-fixed as exactly ``json.dumps(value, sort_keys=True, indent=2) + "\\n"`` UTF-8.

TREE-MUTATION LAW: same ``--out`` posture as build_profile_decision.py — writing inside the
repository root is refused unless ``--allow-in-repo``.  Fully self-contained: stdlib-only,
never imports sibling repository modules.

Exit codes: 0 success, 2 invalid invocation, refused spec, or policy refusal.
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
from typing import Any

TOOL_NAME = "build_trust_registry"
TOOL_VERSION = "1.0.0"

TRUST_REGISTRY_SCHEMA = "triad.receipt_trust_registry.v1"
ALLOWED_ROLES = ("PRODUCER", "COUNTERSIGNER", "AUDITOR")
FORCED_ALGORITHM = "Ed25519"
FORCED_STATUS = "ACTIVE"
ED25519_PUBLIC_KEY_BYTES = 32

# Mirror of the frozen runner's canonical int64-string grammar (parse_canonical_int64).
_INT64_RE = re.compile(r"(?:0|-[1-9][0-9]*|[1-9][0-9]*)")
# Mirror of the frozen runner's milestone grammar (normalize_milestone_from_text), closed to
# the bare B-ids a registry approves.
_MILESTONE_RE = re.compile(r"B(0[1-9]|10)")

_PRIVATE_MATERIAL_TOKENS = ("seed", "private", "secret", "passphrase", "mnemonic")

_REQUIRED_ROW_KEYS = (
    "key_id", "identity", "role", "public_key_base64",
    "valid_from_us", "valid_until_us", "approved_milestones",
)
# algorithm/status may be present in the spec but only with the forced values.
_OPTIONAL_ROW_KEYS = ("algorithm", "status", "revoked_at_us")


class SpecRefused(ValueError):
    """A named, fail-closed spec refusal."""


def parse_canonical_int64(value: Any) -> int | None:
    """Mirror the frozen runner's receipt wire law: canonical signed-int64 base-10 string."""
    if not isinstance(value, str) or not _INT64_RE.fullmatch(value):
        return None
    parsed = int(value)
    if parsed < -(2**63) or parsed > 2**63 - 1:
        return None
    return parsed


def _refuse(name: str, detail: str) -> SpecRefused:
    return SpecRefused(f"REFUSED {name}: {detail}")


def assert_no_private_material(value: Any, path: str = "$") -> None:
    """Hard-refuse any field NAME suggesting private key material, anywhere in the spec."""
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            for token in _PRIVATE_MATERIAL_TOKENS:
                if token in lowered:
                    raise _refuse(
                        "PRIVATE_MATERIAL_FIELD",
                        f"spec field {path}.{key_text} names private material ({token!r}); "
                        "this registry carries PUBLIC keys only",
                    )
            assert_no_private_material(item, f"{path}.{key_text}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            assert_no_private_material(item, f"{path}[{index}]")


def validate_approved_milestones(value: Any, path: str) -> Any:
    if value == "ALL":
        return value
    if not isinstance(value, list) or not value:
        raise _refuse(
            "BAD_APPROVED_MILESTONES",
            f"{path}.approved_milestones must be \"ALL\", [\"ALL\"], or a nonempty list of B-ids")
    if "ALL" in value:
        if value != ["ALL"]:
            raise _refuse(
                "BAD_APPROVED_MILESTONES",
                f"{path}.approved_milestones mixes \"ALL\" with explicit B-ids; the runner would "
                "narrow such a list to the explicit ids only — state one or the other")
        return value
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, str) or not _MILESTONE_RE.fullmatch(item):
            raise _refuse(
                "BAD_APPROVED_MILESTONES",
                f"{path}.approved_milestones[{index}] = {item!r} is not a B01..B10 milestone id")
        if item in seen:
            raise _refuse(
                "BAD_APPROVED_MILESTONES",
                f"{path}.approved_milestones duplicates {item!r}")
        seen.add(item)
    return value


def build_registry(spec: Any) -> dict[str, Any]:
    """Validate the operator spec and build the draft registry object (fail-closed)."""
    assert_no_private_material(spec)
    if not isinstance(spec, list):
        raise _refuse("BAD_SPEC_ROOT", "spec root must be a JSON array of key rows")
    if not spec:
        raise _refuse("EMPTY_SPEC", "a trust registry draft with zero keys is refused")
    rows: list[dict[str, Any]] = []
    seen_key_ids: set[str] = set()
    for index, entry in enumerate(spec):
        path = f"$[{index}]"
        if not isinstance(entry, dict):
            raise _refuse("BAD_ROW", f"{path} is not an object")
        allowed = set(_REQUIRED_ROW_KEYS) | set(_OPTIONAL_ROW_KEYS)
        unknown = sorted(set(map(str, entry)) - allowed)
        if unknown:
            raise _refuse("UNKNOWN_ROW_KEY", f"{path} carries unknown keys {unknown}")
        missing = sorted(key for key in _REQUIRED_ROW_KEYS if key not in entry)
        if missing:
            raise _refuse("MISSING_ROW_KEY", f"{path} lacks required keys {missing}")

        key_id = entry["key_id"]
        if not isinstance(key_id, str) or not key_id.strip():
            raise _refuse("BAD_KEY_ID", f"{path}.key_id must be a nonempty string")
        if key_id in seen_key_ids:
            raise _refuse("DUPLICATE_KEY_ID", f"{path}.key_id {key_id!r} is duplicated")
        seen_key_ids.add(key_id)

        identity = entry["identity"]
        if not isinstance(identity, str) or not identity.strip():
            raise _refuse("BAD_IDENTITY", f"{path}.identity must be a nonempty string")

        role = entry["role"]
        if role not in ALLOWED_ROLES:
            raise _refuse(
                "BAD_ROLE",
                f"{path}.role {role!r} is not one of {list(ALLOWED_ROLES)}")

        if "algorithm" in entry and entry["algorithm"] != FORCED_ALGORITHM:
            raise _refuse(
                "BAD_ALGORITHM",
                f"{path}.algorithm {entry['algorithm']!r} refused; algorithm is forced to "
                f"{FORCED_ALGORITHM!r}")
        if "status" in entry and entry["status"] != FORCED_STATUS:
            raise _refuse(
                "BAD_STATUS",
                f"{path}.status {entry['status']!r} refused; a draft registry key is forced to "
                f"{FORCED_STATUS!r}")

        raw_key = entry["public_key_base64"]
        if not isinstance(raw_key, str):
            raise _refuse("BAD_PUBLIC_KEY", f"{path}.public_key_base64 must be a string")
        try:
            decoded = base64.b64decode(raw_key, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise _refuse(
                "BAD_PUBLIC_KEY", f"{path}.public_key_base64 is not strict base64: {exc}")
        if len(decoded) != ED25519_PUBLIC_KEY_BYTES:
            raise _refuse(
                "BAD_PUBLIC_KEY",
                f"{path}.public_key_base64 decodes to {len(decoded)} bytes; an Ed25519 PUBLIC "
                f"key is exactly {ED25519_PUBLIC_KEY_BYTES} bytes")

        valid_from = parse_canonical_int64(entry["valid_from_us"])
        if valid_from is None:
            raise _refuse(
                "BAD_INT64",
                f"{path}.valid_from_us is not a canonical signed-int64 base-10 string")
        valid_until = parse_canonical_int64(entry["valid_until_us"])
        if valid_until is None:
            raise _refuse(
                "BAD_INT64",
                f"{path}.valid_until_us is not a canonical signed-int64 base-10 string")
        if valid_from >= valid_until:
            raise _refuse(
                "EMPTY_VALIDITY_WINDOW",
                f"{path} has valid_from_us >= valid_until_us; the key could never sign")

        row: dict[str, Any] = {
            "key_id": key_id,
            "identity": identity,
            "role": role,
            "algorithm": FORCED_ALGORITHM,
            "status": FORCED_STATUS,
            "public_key_base64": raw_key,
            "valid_from_us": entry["valid_from_us"],
            "valid_until_us": entry["valid_until_us"],
            "approved_milestones": validate_approved_milestones(
                entry["approved_milestones"], path),
        }
        if "revoked_at_us" in entry:
            if parse_canonical_int64(entry["revoked_at_us"]) is None:
                raise _refuse(
                    "BAD_INT64",
                    f"{path}.revoked_at_us is not a canonical signed-int64 base-10 string")
            row["revoked_at_us"] = entry["revoked_at_us"]
        rows.append(row)
    return {"schema": TRUST_REGISTRY_SCHEMA, "keys": rows}


def deterministic_json_bytes(value: Any) -> bytes:
    """The ceremony-fixed file-byte serialization (PIN is over file bytes — see BYTE LAW)."""
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Build a triad.receipt_trust_registry.v1 draft from an operator spec.")
    parser.add_argument("--spec", required=True, help="operator spec JSON (array of key rows)")
    parser.add_argument("--out", required=True, help="output file path (outside the repository)")
    parser.add_argument(
        "--allow-in-repo", action="store_true",
        help="permit writing inside the repository root (tree-mutation law override)")
    args = parser.parse_args(argv)

    out_path = pathlib.Path(args.out)
    refusal = refuse_out_inside_repo(out_path, args.allow_in_repo)
    if refusal is not None:
        print(refusal, file=sys.stderr)
        return 2
    try:
        spec_text = pathlib.Path(args.spec).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"REFUSED SPEC_UNREADABLE: {exc}", file=sys.stderr)
        return 2
    try:
        spec = json.loads(spec_text)
    except json.JSONDecodeError as exc:
        print(f"REFUSED SPEC_INVALID_JSON: {exc}", file=sys.stderr)
        return 2
    try:
        registry = build_registry(spec)
    except SpecRefused as exc:
        print(str(exc), file=sys.stderr)
        return 2
    payload_bytes = deterministic_json_bytes(registry)
    try:
        out_path.resolve().parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(payload_bytes)
    except OSError as exc:
        print(f"REFUSED OUT_PATH_UNWRITABLE: {exc}", file=sys.stderr)
        return 2
    print(hashlib.sha256(payload_bytes).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
