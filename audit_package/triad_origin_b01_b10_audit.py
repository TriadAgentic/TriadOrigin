#!/usr/bin/env python3
"""Read-only B01-B10 audit, scoring, and evidence-bundle runner for TriadOrigin.

This tool deliberately separates a diagnostic completion score from hard-gate status.  A score
can explain how much independently checkable work exists; it can never turn a failed, blocked, or
unmeasured safety gate into a pass.  A successful repository audit remains
``PASS_REPOSITORY_SAFE_HOLD`` and never authorizes PAPER, TESTNET, LIVE, venue access, or money
authority.

The runner uses only the Python standard library.  In ``local`` mode it clones the requested local
repository into a temporary directory and executes the repository's bounded verification commands
without inheriting credentials.  In ``github`` mode it reads GitHub REST/GraphQL evidence.  In
``full`` mode it requires the local and GitHub subject identities to match exactly.

Exit codes:
    0   completed; every requested hard gate passed (repository safe-hold only)
    1   completed; at least one hard assertion failed
    2   invalid invocation or policy
    3   completed; blocked/unavailable/not-run evidence prevents a decision
    4   runner/internal dependency error prevented a trustworthy audit
    124 a mandatory command timed out

No credentials are accepted on the command line.  GitHub authentication, when required, is read
only and comes from ``GH_TOKEN`` or ``GITHUB_TOKEN``.  Those values are never passed to audited
subprocesses or written to reports.
"""

from __future__ import annotations

import argparse
import ast
import base64
import binascii
import contextlib
import csv
import dataclasses
import datetime as dt
import hashlib
import html
import io
import importlib.metadata
import json
import os
import pathlib
import platform
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence


TOOL_NAME = "triad_origin_b01_b10_audit"
TOOL_VERSION = "1.2.0"
REPORT_SCHEMA = "triad.origin.b01_b10.audit_report.v1"
EVIDENCE_SCHEMA = "triad.origin.audit_evidence_manifest.v1"
CHECK_EVIDENCE_SCHEMA = "triad.origin.audit_check_evidence.v1"
GITHUB_SNAPSHOT_SCHEMA = "triad.origin.github_audit_snapshot.v1"
GITHUB_SNAPSHOT_ENVELOPE_SCHEMA = "triad.origin.github_audit_snapshot_envelope.v1"
GITHUB_SNAPSHOT_PAYLOAD_TYPE = "application/vnd.triad.github-audit-snapshot.v1+json"
RECEIPT_PAYLOAD_TYPE = "application/vnd.triad.evidence-receipt.v3+json"
EXPECTED_REPOSITORY = "triadagentic/triadorigin"

EXIT_PASS = 0
EXIT_HARD_FAIL = 1
EXIT_USAGE = 2
EXIT_INCOMPLETE = 3
EXIT_INTERNAL = 4
EXIT_TIMEOUT = 124

PASS = "PASS"
FAIL = "FAIL"
BLOCKED = "BLOCKED"
NOT_RUN = "NOT_RUN"
UNAVAILABLE = "UNAVAILABLE"
PARTIAL = "PARTIAL"
VALID_OUTCOMES = {PASS, FAIL, BLOCKED, NOT_RUN, UNAVAILABLE, PARTIAL}
INCOMPLETE_OUTCOMES = {BLOCKED, NOT_RUN, UNAVAILABLE, PARTIAL}

ACTIVATION_RESULT = "DENIED_SAFE_HOLD"
SUCCESS_STATUS = "PASS_REPOSITORY_SAFE_HOLD"
REPOSITORY_FUTURE_TOLERANCE_US = 0
MAX_RECEIPT_TTL_US = 2_592_000_000_000
MAX_GITHUB_PAGES = 10

SUPPORTED_RECEIPT_PROFILE_DECISION: dict[str, Any] = {
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

EXPECTED_EFFECTIVE_COUNTS = {
    "effective_formula_count": 24,
    "effective_parameter_record_count": 192,
    "effective_binding_count": 105,
    "effective_wiring_count": 27,
    "effective_task_count": 1115,
    "effective_acceptance_count": 1115,
    "effective_verification_count": 1523,
    "effective_dependency_count": 2249,
    "effective_traceability_count": 4019,
}
EXPECTED_RC1_TEST_COUNT = 408
EXPECTED_RC4_FIXTURE_COUNT = 125
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

MILESTONE_RECEIPT_NAMES = {
    "B01": ("B01C", "B01R", "B01"),
    "B02": ("B02C", "B02"),
    "B03": ("B03C", "B03"),
    "B04": ("B04C", "B04"),
    "B05": ("B05C", "B05"),
    "B06": ("B06R", "B06"),
    "B07": ("B07",),
    "B08": ("B08",),
    "B09": ("B09",),
    "B10": ("B10",),
}

PREDECESSOR = {
    "B01": None,
    "B02": "B01",
    "B03": "B02",
    "B04": "B03",
    "B05": "B04",
    "B06": "B05",
    "B07": "B06",
    "B08": "B07",
    "B09": "B08",
    "B10": "B09",
}

WORK_PACKAGES: dict[str, tuple[str, ...]] = {
    "B01": tuple(f"WP-B01C-{i:02d}" for i in range(1, 7)),
    "B02": tuple(f"WP-B02C-{i:02d}" for i in range(1, 7)),
    "B03": tuple(f"WP-B03C-{i:02d}" for i in range(1, 11)),
    "B04": tuple(f"WP-B04C-{i:02d}" for i in range(1, 11)),
    "B05": tuple(f"WP-B05C-{i:02d}" for i in range(1, 12)),
    "B06": tuple(f"WP-B06R-{i:02d}" for i in range(1, 10)),
    "B07": tuple(f"WP-B07-{i:02d}" for i in range(1, 9)),
    "B08": tuple(f"WP-B08-{i:02d}" for i in range(1, 8)),
    "B09": tuple(f"WP-B09-{i:02d}" for i in range(1, 10)),
    "B10": (
        "AUDIT-ROUND-1",
        "AUDIT-ROUND-2",
        "FINDING-DISPOSITION",
        "IMPLEMENTATION-REPORT",
        "STATUS-REGISTER",
        "SOURCE-MERGE",
        "TERMINAL-RECEIPT",
        "LOCAL-CHECKPOINT",
    ),
}

WORK_ORDER_FILENAMES = {
    "B01": "01_B01_CONTRACT_IDENTITY_BINDING_CLEANUP_WORK_ORDER.md",
    "B02": "02_B02_KERNEL_E01_INTERFACE_CLEANUP_WORK_ORDER.md",
    "B03": "03_B03_FEATURE_STRUCTURE_CLEANUP_WORK_ORDER.md",
    "B04": "04_B04_STRUCTURE_FLOW_LIFECYCLE_CLEANUP_WORK_ORDER.md",
    "B05": "05_B05_FOUR_PLANE_SUBSTRATE_CLEANUP_WORK_ORDER.md",
    "B06": "06_B06_REACTION_CAPSULE_CANDIDATE_BUILD_CHECKLIST.md",
    "B07": "07_B07_CONFIGURATION_COMPARISON_AUTHORITY_REPLAY_BUILD_CHECKLIST.md",
    "B08": "08_B08_READ_FACES_AND_EVIDENCE_PROJECTIONS_BUILD_CHECKLIST.md",
    "B09": "09_B09_CONFORMANCE_FORMULA_CATALOG_RUNBOOKS_BUILD_CHECKLIST.md",
    "B10": "10_B10_INDEPENDENT_AUDIT_TERMINAL_RECEIPT_CHECKPOINT_CHECKLIST.md",
}

REQUIRED_LOCAL_COMMANDS: tuple[tuple[str, tuple[str, ...], int], ...] = (
    ("pytest_seed_0", ("{python}", "-m", "pytest", "-p", "no:cacheprovider"), 900),
    ("pytest_seed_1", ("{python}", "-m", "pytest", "-p", "no:cacheprovider"), 900),
    ("collect_test_ids", ("{python}", "tools/collect_test_ids.py"), 180),
    ("verify_manifest", ("{python}", "tools/verify_manifest.py"), 180),
    ("validate_contract_manifest", ("{python}", "tools/validate_contract_manifest.py"), 180),
    ("verify_reproducible_build", ("{python}", "tools/verify_reproducible_build.py"), 600),
    ("test_wheel_install", ("{python}", "tools/test_wheel_install.py"), 600),
    ("verify_no_forbidden_capabilities", ("{python}", "tools/verify_no_forbidden_capabilities.py"), 180),
    ("e2e_audit", ("{python}", "tools/e2e_audit.py"), 600),
    ("build_ledger", ("{python}", "tools/build_ledger.py", "--verify"), 180),
    ("validate_combined_dag", ("{python}", "tools/validate_combined_dag.py"), 180),
    ("strict_b_receipt_chain", ("{python}", "tools/validate_b_receipt.py", "--all", "--strict"), 300),
    ("verify_spec_control_counts", ("{python}", "tools/verify_spec_control_counts.py", "--strict"), 300),
    ("scan_tracked_secrets", ("{python}", "tools/scan_secrets.py", "--tracked", "--fail-on-hit"), 300),
)

REQUIRED_CI_STEPS = (
    "Checkout exact head",
    "Bind checks to exact event head",
    "Set up Python 3.11",
    "Install test toolchain",
    "Falsification suite",
    "Hash-order invariance",
    "Exact pytest collection identity",
    "Contract byte manifest",
    "Contract manifest schema",
    "Reproducible source and wheel artifacts",
    "Installed-wheel contract smoke",
    "OFF capability boundary",
    "End-to-end audit walk",
    "Build ledger currency",
    "Combined RC3+RC4 composition DAG",
    "Strict B-series receipt chain",
    "Spec/control count reconciliation",
    "Tracked secret scan",
)

REQUIRED_RECEIPT_CI_STEPS = (
    "Checkout exact head",
    "Bind checks to exact event head",
    "Receipt authentication",
)

FORBIDDEN_IMPORT_ROOTS = {
    "binance", "ccxt", "hyperliquid", "web3", "paramiko", "boto3", "alpaca_trade_api"
}

TEXT_SUFFIXES = {
    ".py", ".json", ".jsonl", ".ndjson", ".md", ".txt", ".toml", ".yaml", ".yml",
    ".ini", ".cfg", ".csv", ".schema", ".html", ".xml", ".sh",
}

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("authorization_bearer", re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[A-Za-z0-9._~+/=-]{16,}")),
    ("bearer", re.compile(r"(?i)(\bbearer\s+)[A-Za-z0-9._~+/=-]{20,}")),
    ("query_token", re.compile(r"(?i)([?&](?:token|access_token|auth)=)[^\s&#\"']{12,}")),
    ("github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{20,}\b")),
    ("triad_mcp_token", re.compile(r"\btmc_[A-Za-z0-9_-]{16,}\b")),
    ("authorization_basic", re.compile(r"(?i)(authorization\s*[:=]\s*basic\s+)[A-Za-z0-9+/=]{8,}")),
    ("cookie_header", re.compile(r"(?im)^((?:set-)?cookie\s*:\s*)[^\r\n]+")),
    ("session_assignment", re.compile(
        r"(?i)((?:session(?:id|_id|_key|_token)?|sid)\s*[:=]\s*[\"']?)[^\s,;\"']{8,}")),
    ("openai_token", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("stripe_token", re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{16,}\b")),
    ("gitlab_token", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("uri_userinfo", re.compile(r"(?i)(https?://)[^\s/@:]+:[^\s/@]+@")),
    ("secret_assignment", re.compile(
        r"(?i)((?:api[_-]?key|client[_-]?secret|password|passwd|access[_-]?token)\s*[:=]\s*[\"']?)[^\s,;\"']{12,}")),
    ("private_key", re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]{0,100000}?"
        r"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
)


@dataclasses.dataclass(frozen=True)
class PolicyCheck:
    check_id: str
    milestone: str
    title: str
    hard_gate: bool
    weight: int
    source_id: str
    kind: str


@dataclasses.dataclass
class CheckResult:
    check_id: str
    milestone: str
    title: str
    hard_gate: bool
    weight: int
    source_id: str
    kind: str
    outcome: str = NOT_RUN
    points: float = 0.0
    expected: str = ""
    actual: str = ""
    evidence_ids: list[str] = dataclasses.field(default_factory=list)
    remediation: str = ""

    def set_outcome(
        self,
        outcome: str,
        *,
        actual: str,
        expected: str = "",
        evidence_ids: Iterable[str] = (),
        remediation: str = "",
    ) -> None:
        if outcome not in VALID_OUTCOMES:
            raise ValueError(f"invalid outcome {outcome!r}")
        self.outcome = outcome
        self.expected = expected
        self.actual = actual
        self.evidence_ids = list(dict.fromkeys(str(x) for x in evidence_ids))
        self.remediation = remediation
        if outcome == PASS:
            self.points = float(self.weight)
        elif outcome == PARTIAL and not self.hard_gate:
            self.points = self.weight / 2.0
        else:
            self.points = 0.0


@dataclasses.dataclass
class Finding:
    finding_id: str
    severity: str
    milestone: str
    check_id: str
    title: str
    detail: str
    evidence_ids: list[str]
    remediation: str


@dataclasses.dataclass
class CommandRecord:
    command_id: str
    argv: list[str]
    cwd: str
    started_at: str
    completed_at: str
    duration_ms: int
    exit_code: int | None
    timed_out: bool
    stdout_path: str
    stderr_path: str
    stdout_sha256: str
    stderr_sha256: str
    stdout_raw_sha256: str
    stderr_raw_sha256: str
    truncated: bool
    redaction_hits: list[str] = dataclasses.field(default_factory=list)


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_z(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_iso(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(dt.timezone.utc)


def from_epoch_us(value: Any) -> dt.datetime | None:
    parsed = parse_canonical_int64(value)
    if parsed is None:
        return None
    try:
        return dt.datetime.fromtimestamp(parsed / 1_000_000, tz=dt.timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def parse_canonical_int64(value: Any) -> int | None:
    """Parse the receipt wire law: a canonical signed-int64 base-10 string."""
    if not isinstance(value, str) or not re.fullmatch(r"(?:0|-[1-9][0-9]*|[1-9][0-9]*)", value):
        return None
    parsed = int(value)
    if parsed < -(2**63) or parsed > 2**63 - 1:
        return None
    return parsed


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


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

    Safety-significant receipts are forbidden from using binary floating point.  Integers must be
    exactly representable by I-JSON/IEEE-754; strings must be valid Unicode scalar sequences.
    Within that closed domain this implements JCS key ordering (UTF-16 code units), escaping, and
    whitespace-free serialization without relying on a third-party package.
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


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def toolchain_versions() -> dict[str, Any]:
    packages: dict[str, str | None] = {}
    for name in ("pytest", "build", "wheel", "setuptools"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    try:
        git = subprocess.run(
            ["git", "--version"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=10, check=False,
            env={"PATH": os.environ.get("PATH", ""), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"})
        git_version = git.stdout.strip() if git.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        git_version = None
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": sys.platform,
        "machine": platform.machine(),
        "git": git_version,
        "packages": packages,
    }


def is_hex_sha(value: Any, length: int) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(rf"[0-9a-f]{{{length}}}", value))


def is_nonzero_sha256(value: Any) -> bool:
    return is_hex_sha(value, 64) and value != "0" * 64


# Minimal, verification-focused RFC 8032 Ed25519 implementation.  It keeps this runner
# standard-library-only and, critically, verifies cryptographic preimages instead of trusting a
# receipt's ``verified: true`` assertion.  The signing helper below is used only by self-tests.
_ED_Q = 2**255 - 19
_ED_L = 2**252 + 27742317777372353535851937790883648493
_ED_D = (-121665 * pow(121666, _ED_Q - 2, _ED_Q)) % _ED_Q
_ED_I = pow(2, (_ED_Q - 1) // 4, _ED_Q)
_ED_ID = (0, 1, 1, 0)


def _ed_xrecover(y: int) -> int:
    xx = (y * y - 1) * pow(_ED_D * y * y + 1, _ED_Q - 2, _ED_Q) % _ED_Q
    x = pow(xx, (_ED_Q + 3) // 8, _ED_Q)
    if (x * x - xx) % _ED_Q:
        x = x * _ED_I % _ED_Q
    if x & 1:
        x = _ED_Q - x
    return x


_ED_BY = 4 * pow(5, _ED_Q - 2, _ED_Q) % _ED_Q
_ED_BX = _ed_xrecover(_ED_BY)
_ED_B = (_ED_BX, _ED_BY, 1, _ED_BX * _ED_BY % _ED_Q)


def _ed_add(p: tuple[int, int, int, int], q: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x1, y1, z1, t1 = p
    x2, y2, z2, t2 = q
    a = (y1 - x1) * (y2 - x2) % _ED_Q
    b = (y1 + x1) * (y2 + x2) % _ED_Q
    c = 2 * _ED_D * t1 * t2 % _ED_Q
    d = 2 * z1 * z2 % _ED_Q
    e, f, g, h = (b - a) % _ED_Q, (d - c) % _ED_Q, (d + c) % _ED_Q, (b + a) % _ED_Q
    return e * f % _ED_Q, g * h % _ED_Q, f * g % _ED_Q, e * h % _ED_Q


def _ed_double(p: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x, y, z, _ = p
    a, b, c = x * x % _ED_Q, y * y % _ED_Q, 2 * z * z % _ED_Q
    d = -a % _ED_Q
    e = ((x + y) * (x + y) - a - b) % _ED_Q
    g, f, h = (d + b) % _ED_Q, (d + b - c) % _ED_Q, (d - b) % _ED_Q
    return e * f % _ED_Q, g * h % _ED_Q, f * g % _ED_Q, e * h % _ED_Q


def _ed_scalar_mult(p: tuple[int, int, int, int], scalar: int) -> tuple[int, int, int, int]:
    result = _ED_ID
    addend = p
    while scalar:
        if scalar & 1:
            result = _ed_add(result, addend)
        addend = _ed_double(addend)
        scalar >>= 1
    return result


def _ed_equal(p: tuple[int, int, int, int], q: tuple[int, int, int, int]) -> bool:
    return (p[0] * q[2] - q[0] * p[2]) % _ED_Q == 0 and (p[1] * q[2] - q[1] * p[2]) % _ED_Q == 0


def _ed_encode(p: tuple[int, int, int, int]) -> bytes:
    inverse = pow(p[2], _ED_Q - 2, _ED_Q)
    x, y = p[0] * inverse % _ED_Q, p[1] * inverse % _ED_Q
    encoded = y | ((x & 1) << 255)
    return encoded.to_bytes(32, "little")


def _ed_decode(encoded: bytes) -> tuple[int, int, int, int] | None:
    if len(encoded) != 32:
        return None
    raw = int.from_bytes(encoded, "little")
    sign, y = raw >> 255, raw & ((1 << 255) - 1)
    if y >= _ED_Q:
        return None
    x = _ed_xrecover(y)
    # RFC 8032 canonical encoding: x=0 has sign bit 0 only.  Accepting sign=1 here creates a
    # second encoding of the identity/small-order points and breaks strict verification.
    if x == 0 and sign == 1:
        return None
    if (x & 1) != sign:
        x = _ED_Q - x
    if (-x * x + y * y - 1 - _ED_D * x * x * y * y) % _ED_Q:
        return None
    return x, y, 1, x * y % _ED_Q


def ed25519_verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    if len(public_key) != 32 or len(signature) != 64:
        return False
    public_point = _ed_decode(public_key)
    r_point = _ed_decode(signature[:32])
    scalar = int.from_bytes(signature[32:], "little")
    if public_point is None or r_point is None or scalar >= _ED_L:
        return False
    # Strict subgroup and non-small-order checks reject torsion-based malleability.
    if not _ed_equal(_ed_scalar_mult(public_point, _ED_L), _ED_ID):
        return False
    if not _ed_equal(_ed_scalar_mult(r_point, _ED_L), _ED_ID):
        return False
    if _ed_equal(_ed_scalar_mult(public_point, 8), _ED_ID):
        return False
    if _ed_equal(_ed_scalar_mult(r_point, 8), _ED_ID):
        return False
    challenge = int.from_bytes(
        hashlib.sha512(signature[:32] + public_key + message).digest(), "little") % _ED_L
    return _ed_equal(_ed_scalar_mult(_ED_B, scalar), _ed_add(r_point, _ed_scalar_mult(public_point, challenge)))


def _ed25519_sign_for_self_test(seed: bytes, message: bytes) -> tuple[bytes, bytes]:
    if len(seed) != 32:
        raise ValueError("fixture seed must be 32 bytes")
    expanded = hashlib.sha512(seed).digest()
    scalar_bytes = bytearray(expanded[:32])
    scalar_bytes[0] &= 248
    scalar_bytes[31] &= 63
    scalar_bytes[31] |= 64
    scalar = int.from_bytes(scalar_bytes, "little")
    public_key = _ed_encode(_ed_scalar_mult(_ED_B, scalar))
    nonce = int.from_bytes(hashlib.sha512(expanded[32:] + message).digest(), "little") % _ED_L
    encoded_r = _ed_encode(_ed_scalar_mult(_ED_B, nonce))
    challenge = int.from_bytes(hashlib.sha512(encoded_r + public_key + message).digest(), "little") % _ED_L
    signature = encoded_r + ((nonce + challenge * scalar) % _ED_L).to_bytes(32, "little")
    return public_key, signature


def dsse_pae(payload_type: str, payload: bytes) -> bytes:
    type_bytes = payload_type.encode("utf-8")
    return b"DSSEv1 " + str(len(type_bytes)).encode() + b" " + type_bytes + b" " + str(len(payload)).encode() + b" " + payload


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


def verify_offline_github_envelope(
    event: Mapping[str, Any], *, trust_registry_path: pathlib.Path | None,
    trust_registry_sha256: str | None, selected: Sequence[str], now: dt.datetime,
) -> tuple[list[str], dict[str, Any] | None]:
    """Verify a normalized offline snapshot with two pinned DSSE/Ed25519 auditor signatures."""
    issues: list[str] = []
    if event.get("schema") != GITHUB_SNAPSHOT_ENVELOPE_SCHEMA:
        return [f"offline snapshot envelope schema must be {GITHUB_SNAPSHOT_ENVELOPE_SCHEMA}"], None
    payload = event.get("payload")
    envelope = event.get("dsse")
    if not isinstance(payload, dict) or payload.get("schema") != GITHUB_SNAPSHOT_SCHEMA:
        return [f"offline snapshot payload schema must be {GITHUB_SNAPSHOT_SCHEMA}"], None
    if not isinstance(envelope, dict):
        return ["offline snapshot has no DSSE envelope"], payload
    emitted_us = parse_canonical_int64(payload.get("emitted_at_us"))
    expires_us = parse_canonical_int64(payload.get("expires_at_us"))
    now_us = int(now.timestamp() * 1_000_000)
    if emitted_us is None or expires_us is None:
        issues.append("offline snapshot emitted/expires clocks are not canonical int64 strings")
    else:
        if emitted_us > now_us + REPOSITORY_FUTURE_TOLERANCE_US:
            issues.append(
                "offline snapshot emission is in the future; repository/provider evidence "
                "has zero future tolerance")
        if expires_us <= now_us or expires_us - emitted_us > MAX_RECEIPT_TTL_US:
            issues.append("offline snapshot is expired or has a validity window over 30 days")

    if trust_registry_path is None or not is_nonzero_sha256(trust_registry_sha256):
        issues.append("offline snapshot has no independently pinned trust registry")
        registry = None
    else:
        try:
            registry_bytes = trust_registry_path.read_bytes()
            registry = strict_json_loads(registry_bytes.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            issues.append(f"offline snapshot trust registry is unreadable: {exc}")
            registry = None
        else:
            if sha256_bytes(registry_bytes) != trust_registry_sha256:
                issues.append("offline snapshot trust registry does not match external pin")
            if payload.get("trust_registry_sha256") != trust_registry_sha256:
                issues.append("offline snapshot signed trust-registry pin differs from external pin")
            if not isinstance(registry, dict) or registry.get("schema") != "triad.receipt_trust_registry.v1":
                issues.append("offline snapshot trust registry schema is invalid")

    payload_type = envelope.get("payloadType")
    encoded_payload = strict_base64(envelope.get("payload"))
    if payload_type != GITHUB_SNAPSHOT_PAYLOAD_TYPE:
        issues.append("offline snapshot DSSE payloadType is invalid")
    try:
        canonical_payload = jcs_canonical_bytes(payload)
    except ValueError as exc:
        canonical_payload = None
        issues.append(f"offline snapshot payload is outside RFC 8785 domain: {exc}")
    if encoded_payload is None:
        issues.append("offline snapshot DSSE payload is not strict base64")
    elif canonical_payload is not None and encoded_payload != canonical_payload:
        issues.append("offline snapshot DSSE payload differs from canonical payload")

    registry_keys = registry.get("keys") if isinstance(registry, dict) else None
    registry_keys = registry_keys if isinstance(registry_keys, list) else []
    key_ids = [str(row.get("key_id")) for row in registry_keys if isinstance(row, dict)]
    if len(key_ids) != len(set(key_ids)):
        issues.append("offline snapshot trust registry contains duplicate key IDs")
    keys = {str(row.get("key_id")): row for row in registry_keys if isinstance(row, dict)}
    signatures = envelope.get("signatures")
    if not isinstance(signatures, list) or len(signatures) < 2:
        issues.append("offline snapshot requires two auditor signatures")
        signatures = []
    verified: list[tuple[str, str, str]] = []
    if encoded_payload is not None and payload_type == GITHUB_SNAPSHOT_PAYLOAD_TYPE:
        pae = dsse_pae(payload_type, encoded_payload)
        for index, signature_row in enumerate(signatures):
            if not isinstance(signature_row, dict):
                issues.append(f"offline snapshot signature[{index}] is not an object")
                continue
            key_id = str(signature_row.get("keyid") or "")
            key = keys.get(key_id)
            if key is None:
                issues.append(f"offline snapshot signer {key_id!r} is not pinned/approved")
                continue
            if str(key.get("algorithm", "")).upper() != "ED25519" or str(key.get("status", "")).upper() != "ACTIVE":
                issues.append(f"offline snapshot signer {key_id!r} is not active Ed25519")
                continue
            approvals = key.get("approved_milestones")
            if approvals not in ("ALL", ["ALL"]) and (
                not isinstance(approvals, list) or any(item not in approvals for item in selected)
            ):
                issues.append(f"offline snapshot signer {key_id!r} is not approved for selected milestones")
                continue
            valid_from = parse_canonical_int64(key.get("valid_from_us"))
            valid_until = parse_canonical_int64(key.get("valid_until_us"))
            revoked_at = parse_canonical_int64(key.get("revoked_at_us")) if key.get("revoked_at_us") is not None else None
            if key.get("revoked_at_us") is not None and revoked_at is None:
                issues.append(f"offline snapshot signer {key_id!r} has malformed revocation time")
                continue
            if emitted_us is None or valid_from is None or valid_until is None or not valid_from <= emitted_us < valid_until:
                issues.append(f"offline snapshot signer {key_id!r} is outside validity")
                continue
            if revoked_at is not None and revoked_at <= emitted_us:
                issues.append(f"offline snapshot signer {key_id!r} was revoked")
                continue
            public_key = strict_base64(key.get("public_key_base64"), 32)
            signature = strict_base64(signature_row.get("sig"), 64)
            if public_key is None or signature is None or not ed25519_verify(public_key, pae, signature):
                issues.append(f"offline snapshot signature[{index}] failed Ed25519 verification")
                continue
            identity = str(key.get("identity", "")).strip()
            role = str(key.get("role", "")).upper()
            if not identity or role not in {"AUDITOR", "COUNTERSIGNER"}:
                issues.append(f"offline snapshot signer {key_id!r} lacks auditor/countersigner role")
                continue
            verified.append((key_id, identity, role))
    if len({item[0] for item in verified}) < 2 or len({item[1] for item in verified}) < 2:
        issues.append("offline snapshot lacks two distinct verified signer identities")
    if not {"AUDITOR", "COUNTERSIGNER"}.issubset({item[2] for item in verified}):
        issues.append("offline snapshot lacks verified auditor and countersigner roles")
    producer = payload.get("producer")
    reviewers = payload.get("reviewed_by")
    identity_roles = {(item[1], item[2]) for item in verified}
    if (producer, "AUDITOR") not in identity_roles:
        issues.append("offline snapshot producer is not the verified AUDITOR")
    if not isinstance(reviewers, list) or not any((reviewer, "COUNTERSIGNER") in identity_roles for reviewer in reviewers):
        issues.append("offline snapshot reviewed_by lacks the verified COUNTERSIGNER")
    return list(dict.fromkeys(issues)), payload


def redact_text(value: str) -> tuple[str, list[str]]:
    redacted = value
    hits: list[str] = []
    for name, pattern in SECRET_PATTERNS:
        if pattern.search(redacted):
            hits.append(name)
            if name in {
                "authorization_bearer", "authorization_basic", "bearer", "query_token",
                "cookie_header", "session_assignment", "uri_userinfo", "secret_assignment",
            }:
                redacted = pattern.sub(lambda m: m.group(1) + "<REDACTED>", redacted)
            else:
                redacted = pattern.sub("<REDACTED>", redacted)
    return redacted, hits


def sensitive_mapping_key(value: Any) -> bool:
    """Return true for credential-bearing JSON/object field names.

    Text-pattern redaction catches serialized ``password=...`` and ``password: ...`` forms, but
    structured inputs are sanitized before serialization.  Treat common credential names and
    credential suffixes as secrets so no unredacted value is ever written merely because the key
    and value arrived as separate Python objects.
    """
    key = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")
    exact = {
        "authorization", "proxy_authorization", "authorization_header",
        "token", "access_token", "refresh_token", "id_token", "csrf_token",
        "gh_token", "github_token", "gitlab_token", "openai_token",
        "api_key", "apikey", "client_secret", "secret", "secret_key",
        "password", "passwd", "passphrase", "private_key",
        "session", "session_id", "session_key", "session_token", "sid",
        "cookie", "set_cookie",
    }
    return key in exact or key.endswith((
        "_access_token", "_refresh_token", "_id_token", "_session_token",
        "_api_key", "_client_secret", "_password", "_passphrase", "_private_key",
    ))


def redact_value(value: Any) -> tuple[Any, list[str]]:
    hits: list[str] = []
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        result = []
        for item in value:
            cleaned, found = redact_value(item)
            result.append(cleaned)
            hits.extend(found)
        return result, hits
    if isinstance(value, dict):
        result_dict: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if sensitive_mapping_key(key):
                result_dict[str(key)] = "<REDACTED>"
                hits.append(f"sensitive_key:{lowered}")
            else:
                cleaned, found = redact_value(item)
                result_dict[str(key)] = cleaned
                hits.extend(found)
        return result_dict, hits
    return value, hits


def build_policy() -> tuple[PolicyCheck, ...]:
    checks: list[PolicyCheck] = []
    for milestone in sorted(WORK_PACKAGES):
        packages = WORK_PACKAGES[milestone]
        checks.append(PolicyCheck(
            f"{milestone}.ENTRY", milestone, "Validated predecessor and exact subject entry gate",
            True, 15, f"{milestone}-ENTRY", "entry"))
        base, remainder = divmod(50, len(packages))
        for index, package in enumerate(packages):
            weight = base + (1 if index < remainder else 0)
            checks.append(PolicyCheck(
                f"{milestone}.{package}", milestone, package, True, weight, package, "work_package"))
        checks.append(PolicyCheck(
            f"{milestone}.LOCAL_GATE", milestone, "Independent local exact-head verification",
            True, 15, f"{milestone}-LOCAL", "local"))
        checks.append(PolicyCheck(
            f"{milestone}.GITHUB_GATE", milestone, "Exact-head GitHub review, CI, and governance",
            True, 10, f"{milestone}-GITHUB", "github"))
        checks.append(PolicyCheck(
            f"{milestone}.RECEIPT", milestone, "Authenticated post-merge milestone receipt",
            True, 10, f"{milestone}-RECEIPT", "receipt"))
    validate_policy_rows(checks)
    return tuple(checks)


def validate_policy_rows(checks: Sequence[PolicyCheck]) -> None:
    ids = [row.check_id for row in checks]
    if len(ids) != len(set(ids)):
        raise ValueError("embedded audit policy contains duplicate check IDs")
    totals = defaultdict(int)
    for row in checks:
        totals[row.milestone] += row.weight
    if any(total != 100 for total in totals.values()):
        raise ValueError(f"embedded audit policy milestone weights are not 100: {dict(totals)}")


POLICY = build_policy()
POLICY_SHA256 = sha256_bytes(canonical_json_bytes([dataclasses.asdict(row) for row in POLICY]))


def validate_policy_document_sync(directory: pathlib.Path) -> list[str]:
    issues: list[str] = []
    b10_markers = {
        "AUDIT-ROUND-1": "Audit round 1",
        "AUDIT-ROUND-2": "Audit round 2",
        "FINDING-DISPOSITION": "Finding disposition law",
        "IMPLEMENTATION-REPORT": "Implementation report requirements",
        "STATUS-REGISTER": "Status and decision-register closure",
        "SOURCE-MERGE": "B10 source PR gate",
        "TERMINAL-RECEIPT": "Detached terminal receipt ceremony",
        "LOCAL-CHECKPOINT": "TriadOrigin-local checkpoint ceremony",
    }
    for milestone, filename in WORK_ORDER_FILENAMES.items():
        path = directory / filename
        if not path.is_file():
            issues.append(f"missing work-order file {filename}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for source_id in WORK_PACKAGES[milestone]:
            marker = b10_markers.get(source_id, source_id) if milestone == "B10" else source_id
            if marker not in text:
                issues.append(f"{filename} does not contain policy source ID {source_id}")
    return issues


class GitHubError(RuntimeError):
    pass


class GitHubClient:
    def __init__(self, token: str | None, api_url: str = "https://api.github.com") -> None:
        self._token = token
        self._api_url = api_url.rstrip("/")

    def _request(self, request: urllib.request.Request) -> Any:
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        request.add_header("User-Agent", f"{TOOL_NAME}/{TOOL_VERSION}")
        if self._token:
            request.add_header("Authorization", f"Bearer {self._token}")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read(2048).decode("utf-8", errors="replace")
            raise GitHubError(f"GitHub HTTP {exc.code}: {body}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise GitHubError(f"GitHub request failed: {exc}") from exc
        try:
            return strict_json_loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, DuplicateJSONKey, RecursionError) as exc:
            raise GitHubError("GitHub returned non-JSON data") from exc

    def get(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        url = self._api_url + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        return self._request(urllib.request.Request(url, method="GET"))

    def graphql(self, query: str, variables: Mapping[str, Any]) -> Any:
        payload = canonical_json_bytes({"query": query, "variables": variables})
        request = urllib.request.Request(
            self._api_url + "/graphql", data=payload, method="POST",
            headers={"Content-Type": "application/json"})
        result = self._request(request)
        if result.get("errors"):
            raise GitHubError(f"GitHub GraphQL errors: {result['errors']}")
        return result.get("data", {})


def github_get_all(
    client: GitHubClient, path: str, *, params: Mapping[str, Any] | None = None,
    array_key: str | None = None,
) -> list[Any]:
    rows: list[Any] = []
    for page in range(1, MAX_GITHUB_PAGES + 1):
        query = {**(params or {}), "per_page": 100, "page": page}
        response = client.get(path, query)
        page_rows = response.get(array_key, []) if array_key and isinstance(response, dict) else response
        if not isinstance(page_rows, list):
            raise GitHubError(f"GitHub pagination response for {path} is not an array")
        rows.extend(page_rows)
        if len(page_rows) < 100:
            return rows
    raise GitHubError(f"GitHub evidence for {path} exceeds {MAX_GITHUB_PAGES * 100} rows")


def collect_review_threads(client: GitHubClient, owner: str, name: str, pr_number: int) -> list[dict[str, Any]]:
    thread_query = """
    query($owner:String!,$name:String!,$number:Int!){
      repository(owner:$owner,name:$name){
        pullRequest(number:$number){
          reviewThreads(first:100){
            pageInfo{hasNextPage}
            nodes{isResolved isOutdated path line
              comments(first:50){pageInfo{hasNextPage} nodes{body createdAt updatedAt author{login}}}}
          }
        }
      }
    }
    """
    graph = client.graphql(thread_query, {"owner": owner, "name": name, "number": pr_number})
    threads = graph["repository"]["pullRequest"]["reviewThreads"]
    if threads.get("pageInfo", {}).get("hasNextPage"):
        raise GitHubError(f"PR #{pr_number} review threads exceed 100; refuse incomplete evidence")
    rows = threads.get("nodes", [])
    for row in rows:
        comments = row.get("comments", {}) if isinstance(row, dict) else {}
        if isinstance(comments, dict) and comments.get("pageInfo", {}).get("hasNextPage"):
            raise GitHubError(f"PR #{pr_number} review thread comments exceed 50; refuse incomplete evidence")
    return rows


def collect_pull_bundle(
    client: GitHubClient, repo_full_name: str, owner: str, name: str,
    pr_number: int, preloaded_pr: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    pr = dict(preloaded_pr) if preloaded_pr else client.get(f"/repos/{repo_full_name}/pulls/{pr_number}")
    reviews = github_get_all(client, f"/repos/{repo_full_name}/pulls/{pr_number}/reviews")
    commits = github_get_all(client, f"/repos/{repo_full_name}/pulls/{pr_number}/commits")
    head_sha = pr.get("head", {}).get("sha", "")
    workflow_fact = client.get(
        f"/repos/{repo_full_name}/contents/.github/workflows/ci.yml", params={"ref": head_sha})
    workflow_content = workflow_fact.get("content") if isinstance(workflow_fact, dict) else None
    try:
        workflow_bytes = base64.b64decode("".join(workflow_content.split()), validate=True) \
            if isinstance(workflow_content, str) and workflow_fact.get("encoding") == "base64" else None
    except (binascii.Error, ValueError):
        workflow_bytes = None
    if workflow_bytes is None:
        raise GitHubError(f"PR #{pr_number} exact-head CI workflow bytes are unavailable")
    runs = github_get_all(
        client, f"/repos/{repo_full_name}/actions/runs",
        params={"head_sha": head_sha}, array_key="workflow_runs")
    normalized_runs: list[dict[str, Any]] = []
    for run in runs:
        jobs_url = str(run.get("jobs_url", ""))
        jobs_path = urllib.parse.urlparse(jobs_url).path
        if not jobs_path:
            raise GitHubError(f"workflow run {run.get('id')} has no jobs URL")
        jobs = github_get_all(client, jobs_path, array_key="jobs")
        normalized_runs.append({**run, "jobs": jobs})
    return {
        "pr": pr,
        "reviews": reviews,
        "review_threads": collect_review_threads(client, owner, name, pr_number),
        "workflow_runs": normalized_runs,
        "workflow_path": ".github/workflows/ci.yml",
        "workflow_sha256": sha256_bytes(workflow_bytes),
        "commits": commits,
    }


def pull_is_receipt(pr: Mapping[str, Any]) -> bool:
    text = " ".join([
        str(pr.get("title", "")),
        str((pr.get("head") or {}).get("ref", "")) if isinstance(pr.get("head"), dict) else "",
    ])
    return bool(re.search(
        r"(?i)(?<![A-Za-z0-9])(receipt|terminal[-_ ]evidence|evidence[-_ ]receipt)(?![A-Za-z0-9])",
        text,
    ))


def github_snapshot_structure_issues(data: Any, selected: Sequence[str]) -> list[str]:
    issues: list[str] = []
    if not isinstance(data, dict):
        return ["GitHub snapshot root is not an object"]
    stack: list[tuple[Any, int]] = [(data, 0)]
    nodes = 0
    while stack:
        value, depth = stack.pop()
        nodes += 1
        if depth > 32:
            return ["GitHub snapshot exceeds maximum nesting depth 32"]
        if nodes > 1_000_000:
            return ["GitHub snapshot exceeds maximum structural node count"]
        if isinstance(value, dict):
            stack.extend((child, depth + 1) for child in value.values())
        elif isinstance(value, list):
            stack.extend((child, depth + 1) for child in value)
    if data.get("schema") != GITHUB_SNAPSHOT_SCHEMA:
        issues.append(f"GitHub snapshot schema must be {GITHUB_SNAPSHOT_SCHEMA}")
    if not isinstance(data.get("repository"), str) or "/" not in data.get("repository", ""):
        issues.append("GitHub snapshot repository is malformed")
    milestones = data.get("milestones")
    if not isinstance(milestones, dict):
        return issues + ["GitHub snapshot milestones is not an object"]
    for milestone in selected:
        fact = milestones.get(milestone)
        if not isinstance(fact, dict):
            issues.append(f"GitHub snapshot {milestone} fact is unavailable")
            continue
        for key in ("source_candidate_numbers", "receipt_candidate_numbers"):
            numbers = fact.get(key)
            if not isinstance(numbers, list) or any(
                isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in numbers
            ):
                issues.append(f"GitHub snapshot {milestone}.{key} must be a positive-integer array")
        for key in ("source", "receipt"):
            if fact.get(key) is not None and not isinstance(fact.get(key), dict):
                issues.append(f"GitHub snapshot {milestone}.{key} must be object or null")
    governance = data.get("governance")
    if not isinstance(governance, dict):
        issues.append("GitHub snapshot governance is not an object")
    return issues


def classify_source_merge_proof(
    *, compare_status: Any, head_sha: Any, merge_sha: Any, base_sha: Any = None,
    head_commit: Mapping[str, Any] | None = None,
    merge_commit: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify reviewed-head incorporation without conflating squash with ancestry."""
    if not is_hex_sha(head_sha, 40) or not is_hex_sha(merge_sha, 40):
        return {"kind": UNAVAILABLE, "verified": False, "reason": "commit identities unavailable"}
    normalized_status = str(compare_status or "").lower()
    if normalized_status == "ahead" or (
        normalized_status == "identical" and head_sha == merge_sha
    ):
        return {
            "kind": "ANCESTOR", "verified": True,
            "head_sha": head_sha, "merge_sha": merge_sha,
        }
    head_tree = (head_commit or {}).get("tree")
    merge_tree = (merge_commit or {}).get("tree")
    head_tree_sha = head_tree.get("sha") if isinstance(head_tree, dict) else None
    merge_tree_sha = merge_tree.get("sha") if isinstance(merge_tree, dict) else None
    parents = (merge_commit or {}).get("parents")
    parent_shas = [
        row.get("sha") for row in parents
        if isinstance(row, dict) and is_hex_sha(row.get("sha"), 40)
    ] if isinstance(parents, list) else []
    if is_hex_sha(head_tree_sha, 40) and is_hex_sha(merge_tree_sha, 40):
        if (
            head_tree_sha == merge_tree_sha
            and isinstance(parents, list) and len(parents) == 1 and len(parent_shas) == 1
            and is_hex_sha(base_sha, 40) and parent_shas[0] == base_sha
        ):
            return {
                "kind": "EXACT_TREE_SQUASH", "verified": True,
                "head_sha": head_sha, "merge_sha": merge_sha,
                "head_tree_sha": head_tree_sha, "merge_tree_sha": merge_tree_sha,
                "merge_parent_sha": parent_shas[0], "base_sha": base_sha,
            }
        if head_tree_sha != merge_tree_sha:
            return {
                "kind": "UNRELATED", "verified": False,
                "head_sha": head_sha, "merge_sha": merge_sha,
                "head_tree_sha": head_tree_sha, "merge_tree_sha": merge_tree_sha,
                "compare_status": normalized_status,
            }
        return {
            "kind": UNAVAILABLE, "verified": False,
            "reason": "equal trees do not meet the closed same-base one-parent squash rule",
            "head_sha": head_sha, "merge_sha": merge_sha,
        }
    return {
        "kind": UNAVAILABLE, "verified": False,
        "reason": "Git commit/tree identities unavailable for non-ancestor merge",
        "head_sha": head_sha, "merge_sha": merge_sha,
    }


def normalize_default_branch_controls(
    ruleset_details: Sequence[Any], default_branch: str | None,
) -> dict[str, Any] | None:
    """Extract a narrow closed proof from detailed active rulesets; summaries never suffice."""
    if not default_branch:
        return None
    target_ref = f"refs/heads/{default_branch}"
    applicable: list[Mapping[str, Any]] = []
    for row in ruleset_details:
        if not isinstance(row, dict) or str(row.get("enforcement", "")).lower() != "active":
            continue
        ruleset_id = row.get("id")
        if not isinstance(ruleset_id, int) or isinstance(ruleset_id, bool) or ruleset_id <= 0:
            continue
        if str(row.get("target", "")).lower() != "branch":
            continue
        conditions = row.get("conditions")
        ref_name = conditions.get("ref_name") if isinstance(conditions, dict) else None
        includes = ref_name.get("include") if isinstance(ref_name, dict) else None
        excludes = ref_name.get("exclude") if isinstance(ref_name, dict) else None
        if (
            not isinstance(includes, list) or not all(isinstance(item, str) for item in includes)
            or not isinstance(excludes, list) or not all(isinstance(item, str) for item in excludes)
        ):
            continue
        included = "~DEFAULT_BRANCH" in includes or target_ref in includes
        excluded = "~DEFAULT_BRANCH" in excludes or target_ref in excludes
        if included and not excluded:
            applicable.append(row)
    ruleset_ids: list[int] = []
    approving_reviews = 0
    pull_request_required = False
    resolved_conversations_required = False
    stale_head_rejection_required = False
    required_checks: set[str] = set()
    strict_status_checks = False
    for row in applicable:
        ruleset_id = row.get("id")
        if isinstance(ruleset_id, int) and not isinstance(ruleset_id, bool) and ruleset_id > 0:
            ruleset_ids.append(ruleset_id)
        for rule in row.get("rules", []) if isinstance(row.get("rules"), list) else []:
            if not isinstance(rule, dict):
                continue
            rule_type = str(rule.get("type", ""))
            parameters = rule.get("parameters") if isinstance(rule.get("parameters"), dict) else {}
            if rule_type == "pull_request":
                count = parameters.get("required_approving_review_count")
                if isinstance(count, int) and not isinstance(count, bool) and count >= 1:
                    pull_request_required = True
                    approving_reviews = max(approving_reviews, count)
                resolved_conversations_required = resolved_conversations_required or (
                    parameters.get("required_review_thread_resolution") is True)
                stale_head_rejection_required = stale_head_rejection_required or (
                    parameters.get("dismiss_stale_reviews_on_push") is True
                    or parameters.get("require_last_push_approval") is True)
            elif rule_type == "required_status_checks":
                checks = parameters.get("required_status_checks")
                if isinstance(checks, list):
                    required_checks.update(
                        str(item.get("context")) for item in checks
                        if isinstance(item, dict) and isinstance(item.get("context"), str)
                        and item.get("context")
                    )
                strict_status_checks = strict_status_checks or (
                    parameters.get("strict_required_status_checks_policy") is True)
    if not (
        ruleset_ids and pull_request_required and approving_reviews >= 1
        and resolved_conversations_required and stale_head_rejection_required
        and required_checks and strict_status_checks
    ):
        return None
    return {
        "schema": "triad.github.default_branch_controls.v1",
        "target_ref": target_ref,
        "ruleset_ids": sorted(set(ruleset_ids)),
        "pull_request_required": True,
        "required_approving_review_count": approving_reviews,
        "resolved_conversations_required": True,
        "stale_head_rejection_required": True,
        "required_status_checks": sorted(required_checks),
        "required_status_checks_strict": True,
    }


def collect_github_snapshot(
    client: GitHubClient, repo_full_name: str, pr_number: int | None,
    selected: Sequence[str], source_prs: Mapping[str, int] | None = None,
    receipt_prs: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    if "/" not in repo_full_name:
        raise GitHubError("repository must be owner/name")
    owner, name = repo_full_name.split("/", 1)
    repository_info = client.get(f"/repos/{repo_full_name}")
    default_branch = repository_info.get("default_branch") if isinstance(repository_info, dict) else None
    default_branch_head_sha: str | None = None
    if isinstance(default_branch, str) and default_branch:
        encoded_ref = urllib.parse.quote(f"heads/{default_branch}", safe="/")
        ref_fact = client.get(f"/repos/{repo_full_name}/git/ref/{encoded_ref}")
        object_fact = ref_fact.get("object") if isinstance(ref_fact, dict) else None
        candidate_sha = object_fact.get("sha") if isinstance(object_fact, dict) else None
        if is_hex_sha(candidate_sha, 40):
            default_branch_head_sha = candidate_sha
    pulls = github_get_all(
        client, f"/repos/{repo_full_name}/pulls",
        params={"state": "all", "sort": "updated", "direction": "desc"})
    explicit = next((row for row in pulls if row.get("number") == pr_number), None) if pr_number else None
    if pr_number and explicit is None:
        explicit = client.get(f"/repos/{repo_full_name}/pulls/{pr_number}")
    try:
        rulesets = github_get_all(client, f"/repos/{repo_full_name}/rulesets")
    except GitHubError as exc:
        rulesets = {"unavailable": str(exc)}
    ruleset_details: list[dict[str, Any]] = []
    if isinstance(rulesets, list):
        for row in rulesets:
            ruleset_id = row.get("id") if isinstance(row, dict) else None
            if (
                not isinstance(ruleset_id, int) or isinstance(ruleset_id, bool) or ruleset_id <= 0
                or str(row.get("enforcement", "")).lower() != "active"
            ):
                continue
            try:
                detail = client.get(f"/repos/{repo_full_name}/rulesets/{ruleset_id}")
            except GitHubError as exc:
                detail = {"id": ruleset_id, "unavailable": str(exc)}
            if isinstance(detail, dict):
                ruleset_details.append(detail)
    try:
        issue5 = client.get(f"/repos/{repo_full_name}/issues/5")
    except GitHubError as exc:
        issue5 = {"unavailable": str(exc)}
    milestone_facts: dict[str, Any] = {}
    for milestone in selected:
        candidates = [
            row for row in pulls
            if normalize_milestone_from_text(" ".join([
                str(row.get("title", "")),
                str((row.get("head") or {}).get("ref", "")) if isinstance(row.get("head"), dict) else "",
            ])) == milestone
        ]
        source_candidates = [row for row in candidates if not pull_is_receipt(row)]
        receipt_candidates = [row for row in candidates if pull_is_receipt(row)]
        all_source_numbers = [row.get("number") for row in source_candidates]
        all_receipt_numbers = [row.get("number") for row in receipt_candidates]
        if source_prs and milestone in source_prs:
            selected_number = source_prs[milestone]
            chosen = next((row for row in pulls if row.get("number") == selected_number), None)
            if chosen is None:
                chosen = client.get(f"/repos/{repo_full_name}/pulls/{selected_number}")
            if pull_is_receipt(chosen) or normalize_milestone_from_text(str(chosen.get("title", ""))) != milestone:
                raise GitHubError(f"explicit source selection {milestone}=#{selected_number} is not that milestone source PR")
            source_candidates = [chosen]
        if receipt_prs and milestone in receipt_prs:
            selected_number = receipt_prs[milestone]
            chosen = next((row for row in pulls if row.get("number") == selected_number), None)
            if chosen is None:
                chosen = client.get(f"/repos/{repo_full_name}/pulls/{selected_number}")
            if not pull_is_receipt(chosen) or normalize_milestone_from_text(str(chosen.get("title", ""))) != milestone:
                raise GitHubError(f"explicit receipt selection {milestone}=#{selected_number} is not that milestone receipt PR")
            receipt_candidates = [chosen]
        if explicit and normalize_milestone_from_text(str(explicit.get("title", ""))) == milestone:
            if pull_is_receipt(explicit):
                receipt_candidates = [explicit]
            else:
                source_candidates = [explicit]
        source = source_candidates[0] if source_candidates else None
        receipt = receipt_candidates[0] if receipt_candidates else None
        source_bundle = collect_pull_bundle(client, repo_full_name, owner, name, int(source["number"]), source) if source else None
        receipt_bundle = collect_pull_bundle(client, repo_full_name, owner, name, int(receipt["number"]), receipt) if receipt else None
        if source_bundle:
            source_pr = source_bundle["pr"]
            head_sha = source_pr.get("head", {}).get("sha")
            merge_sha = source_pr.get("merge_commit_sha")
            if is_hex_sha(head_sha, 40) and is_hex_sha(merge_sha, 40):
                try:
                    compare = client.get(f"/repos/{repo_full_name}/compare/{head_sha}...{merge_sha}")
                    compare_status = compare.get("status") if isinstance(compare, dict) else None
                    head_commit = None
                    merge_commit = None
                    if str(compare_status or "").lower() not in {"ahead", "identical"}:
                        head_commit = client.get(f"/repos/{repo_full_name}/git/commits/{head_sha}")
                        merge_commit = client.get(f"/repos/{repo_full_name}/git/commits/{merge_sha}")
                    proof = classify_source_merge_proof(
                        compare_status=compare_status, head_sha=head_sha, merge_sha=merge_sha,
                        base_sha=(source_pr.get("base") or {}).get("sha")
                        if isinstance(source_pr.get("base"), dict) else None,
                        head_commit=head_commit if isinstance(head_commit, dict) else None,
                        merge_commit=merge_commit if isinstance(merge_commit, dict) else None,
                    )
                except GitHubError as exc:
                    proof = {"kind": UNAVAILABLE, "verified": False, "reason": str(exc)}
                source_bundle["merge_proof"] = proof
                source_bundle["merge_contains_head"] = proof.get("kind") == "ANCESTOR"
        if source_bundle and receipt_bundle:
            source_merge = source_bundle["pr"].get("merge_commit_sha")
            receipt_head = receipt_bundle["pr"].get("head", {}).get("sha")
            if is_hex_sha(source_merge, 40) and is_hex_sha(receipt_head, 40):
                compare = client.get(f"/repos/{repo_full_name}/compare/{source_merge}...{receipt_head}")
                receipt_bundle["contains_source_merge"] = compare.get("status") in {"ahead", "identical"}
        milestone_facts[milestone] = {
            "source": source_bundle,
            "receipt": receipt_bundle,
            "source_candidate_numbers": [row.get("number") for row in source_candidates],
            "receipt_candidate_numbers": [row.get("number") for row in receipt_candidates],
            "all_source_candidate_numbers": all_source_numbers,
            "all_receipt_candidate_numbers": all_receipt_numbers,
            "selection_explicit": bool(
                (source_prs and milestone in source_prs) or (receipt_prs and milestone in receipt_prs)),
        }
    default_branch_controls = normalize_default_branch_controls(
        ruleset_details, default_branch if isinstance(default_branch, str) else None)
    return {
        "schema": GITHUB_SNAPSHOT_SCHEMA,
        "captured_at": iso_z(utc_now()),
        "repository": repo_full_name,
        "default_branch": default_branch,
        "default_branch_head_sha": default_branch_head_sha,
        "subject_pr": explicit,
        "milestones": milestone_facts,
        "rulesets": rulesets,
        "ruleset_details": ruleset_details,
        "issue_5": issue5,
        "governance": {
            "active_ruleset_summaries_present": any(
                isinstance(row, dict) and str(row.get("enforcement", "")).lower() == "active"
                for row in rulesets) if isinstance(rulesets, list) else False,
            "branch_protection_enforced": default_branch_controls is not None,
            "default_branch_controls": default_branch_controls,
            # REST PR/ruleset evidence cannot prove an administrator did not bypass.  A normalized
            # offline snapshot may fill this from immutable audit-log evidence; live collection
            # remains explicitly incomplete instead of guessing false.
            "bypass_used": None,
            "signed_waiver_verified": False,
        },
        "recent_pulls": pulls,
    }


def classify_review_severity(body: str) -> str | None:
    match = re.search(r"\bP([0-3])\b", body, flags=re.IGNORECASE)
    return f"P{match.group(1)}" if match else None


def github_commit_time(commit: Mapping[str, Any]) -> dt.datetime | None:
    body = commit.get("commit") if isinstance(commit.get("commit"), dict) else commit
    for actor in ("committer", "author"):
        row = body.get(actor) if isinstance(body, dict) else None
        when = parse_iso(row.get("date")) if isinstance(row, dict) else None
        if when:
            return when
    return None


def github_exact_ci_issues(
    bundle: Mapping[str, Any], head_sha: str, required_steps: Sequence[str], label: str,
    merged_at: dt.datetime | None,
) -> tuple[list[str], list[str]]:
    runs = bundle.get("workflow_runs")
    if not isinstance(runs, list):
        return [], [f"{label} workflow-run evidence is unavailable"]
    matching = [run for run in runs if run.get("head_sha") == head_sha]
    if not matching:
        return [], [f"{label} has no exact-head CI evidence"]
    missing_step_sets: list[list[str]] = []
    missing_completion = False
    completed_after_merge = False
    untrusted_workflow = False
    saw_green = False
    for run in matching:
        if run.get("path") != ".github/workflows/ci.yml" or run.get("event") != "pull_request":
            untrusted_workflow = True
            continue
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            continue
        saw_green = True
        step_map: dict[str, list[str]] = defaultdict(list)
        for job in run.get("jobs", []) if isinstance(run.get("jobs"), list) else []:
            for step in job.get("steps", []) if isinstance(job.get("steps"), list) else []:
                step_map[str(step.get("name"))].append(str(step.get("conclusion")))
        missing = [
            name for name in required_steps
            if not step_map.get(name) or any(conclusion != "success" for conclusion in step_map[name])
        ]
        if missing:
            missing_step_sets.append(missing)
            continue
        completed_at = parse_iso(run.get("updated_at") or run.get("completed_at") or run.get("completedAt"))
        if completed_at is None:
            missing_completion = True
            continue
        if merged_at is not None and completed_at >= merged_at:
            completed_after_merge = True
            continue
        return [], []
    failures: list[str] = []
    incomplete: list[str] = []
    if not saw_green:
        failures.append(f"{label} has no completed successful exact-head CI run")
    if missing_step_sets:
        best = min(missing_step_sets, key=len)
        failures.append(f"{label} exact-head CI skipped/failed required steps: {', '.join(best)}")
    if completed_after_merge:
        failures.append(f"{label} has no complete required exact-head CI run before merge")
    if untrusted_workflow:
        failures.append(f"{label} CI evidence came from an untrusted workflow path/event")
    if missing_completion:
        incomplete.append(f"{label} CI completion chronology is unavailable")
    return failures, incomplete


def github_pull_bundle_issues(
    bundle: Mapping[str, Any] | None,
    *,
    label: str,
    required_steps: Sequence[str],
) -> tuple[list[str], list[str], dict[str, Any]]:
    failures: list[str] = []
    incomplete: list[str] = []
    facts: dict[str, Any] = {}
    if not isinstance(bundle, dict):
        return failures, [f"{label} PR evidence is unavailable"], facts
    pr = bundle.get("pr")
    if not isinstance(pr, dict):
        return failures, [f"{label} subject PR is unavailable"], facts
    number = pr.get("number")
    head = pr.get("head", {}) if isinstance(pr.get("head"), dict) else {}
    base = pr.get("base", {}) if isinstance(pr.get("base"), dict) else {}
    head_sha, base_sha = head.get("sha"), base.get("sha")
    facts.update({
        "number": number,
        "head_sha": head_sha,
        "base_sha": base_sha,
        "merge_sha": pr.get("merge_commit_sha"),
        "created_at": parse_iso(pr.get("created_at") or pr.get("createdAt")),
        "merged_at": parse_iso(pr.get("merged_at") or pr.get("mergedAt")),
    })
    if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
        incomplete.append(f"{label} PR number is unavailable")
    if not is_hex_sha(head_sha, 40) or not is_hex_sha(base_sha, 40):
        incomplete.append(f"{label} exact base/head SHA evidence is unavailable")
    elif head_sha == base_sha:
        failures.append(f"{label} base and head SHA are identical")
    if not is_hex_sha(facts["merge_sha"], 40):
        incomplete.append(f"{label} merge commit SHA is unavailable")
    if facts["created_at"] is None or facts["merged_at"] is None:
        incomplete.append(f"{label} created/merged chronology is unavailable")
    elif facts["created_at"] >= facts["merged_at"]:
        failures.append(f"{label} created_at is not before merged_at")

    commits = bundle.get("commits")
    commit_times = [github_commit_time(row) for row in commits] if isinstance(commits, list) else []
    commit_times = [row for row in commit_times if row is not None]
    if not commit_times:
        incomplete.append(f"{label} commit chronology is unavailable")
        last_commit = None
    else:
        last_commit = max(commit_times)
        facts["last_commit_at"] = last_commit
        if facts["merged_at"] and last_commit > facts["merged_at"]:
            failures.append(f"{label} last commit is after PR merge")

    author = (pr.get("user") or {}).get("login") if isinstance(pr.get("user"), dict) else pr.get("author")
    reviews = bundle.get("reviews")
    approved_times: list[dt.datetime] = []
    approved_reviewers: list[str] = []
    if not author:
        incomplete.append(f"{label} author identity is unavailable")
    if not isinstance(reviews, list):
        incomplete.append(f"{label} review evidence is unavailable")
        reviews = []
    effective_reviews: dict[str, tuple[dt.datetime, Mapping[str, Any]]] = {}
    for review in reviews:
        submitted = parse_iso(review.get("submitted_at") or review.get("submittedAt"))
        reviewer = review.get("user") or review.get("author")
        reviewer_login = reviewer.get("login") if isinstance(reviewer, dict) else str(reviewer or "")
        if submitted and facts["merged_at"] and submitted >= facts["merged_at"]:
            failures.append(f"{label} review was submitted at/after merge")
        if submitted and reviewer_login:
            current = effective_reviews.get(reviewer_login)
            if current is None or submitted >= current[0]:
                effective_reviews[reviewer_login] = (submitted, review)
    for reviewer_login, (submitted, review) in effective_reviews.items():
        if reviewer_login != author and str(review.get("state", "")).upper() == "APPROVED":
            review_commit = review.get("commit_id") or review.get("commitId")
            if review_commit is None:
                incomplete.append(f"{label} approval commit identity is unavailable")
            elif review_commit != head_sha:
                failures.append(f"{label} approval is not bound to the final PR head")
            else:
                approved_times.append(submitted)
                approved_reviewers.append(reviewer_login)
    if not approved_times:
        incomplete.append(f"{label} has no independent APPROVED review")
    else:
        final_review = max(approved_times)
        facts["approved_at"] = final_review
        facts["approved_reviewers"] = sorted(set(approved_reviewers))
        if last_commit and final_review < last_commit:
            failures.append(f"{label} approval predates the last code commit")
        if facts["merged_at"] and final_review >= facts["merged_at"]:
            failures.append(f"{label} independent approval did not precede merge")

    threads = bundle.get("review_threads")
    if not isinstance(threads, list):
        incomplete.append(f"{label} review-thread evidence is unavailable")
        threads = []
    for index, thread in enumerate(threads):
        comments = thread.get("comments", []) if isinstance(thread, dict) else []
        if isinstance(comments, dict):
            comments = comments.get("nodes", [])
        severity = [classify_review_severity(str(row.get("body", ""))) for row in comments]
        if any(item in {"P0", "P1"} for item in severity) and not thread.get("isResolved"):
            failures.append(f"{label} unresolved actionable P0/P1 review thread #{index + 1}")

    ci_failures, ci_incomplete = github_exact_ci_issues(
        bundle, str(head_sha), required_steps, label, facts["merged_at"])
    failures.extend(ci_failures)
    incomplete.extend(ci_incomplete)
    return list(dict.fromkeys(failures)), list(dict.fromkeys(incomplete)), facts


def github_source_merge_proof_issues(
    bundle: Mapping[str, Any], label: str,
) -> tuple[list[str], list[str]]:
    pr = bundle.get("pr") if isinstance(bundle.get("pr"), dict) else {}
    head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
    base = pr.get("base") if isinstance(pr.get("base"), dict) else {}
    expected_head = head.get("sha")
    expected_base = base.get("sha")
    expected_merge = pr.get("merge_commit_sha")
    proof = bundle.get("merge_proof")
    if isinstance(proof, dict):
        kind = proof.get("kind")
        if kind == "ANCESTOR":
            if (
                proof.get("verified") is True
                and proof.get("head_sha") == expected_head
                and proof.get("merge_sha") == expected_merge
            ):
                return [], []
            return [f"{label} ancestry proof is internally inconsistent"], []
        if kind == "EXACT_TREE_SQUASH":
            head_tree = proof.get("head_tree_sha")
            merge_tree = proof.get("merge_tree_sha")
            if (
                proof.get("verified") is True
                and proof.get("head_sha") == expected_head
                and proof.get("merge_sha") == expected_merge
                and is_hex_sha(head_tree, 40) and head_tree == merge_tree
                and is_hex_sha(expected_base, 40)
                and proof.get("base_sha") == expected_base
                and proof.get("merge_parent_sha") == expected_base
            ):
                return [], []
            return [f"{label} exact-tree squash proof is internally inconsistent"], []
        if kind == "UNRELATED":
            return [
                f"{label} merge is neither reviewed-head ancestry nor exact-tree squash equivalence"
            ], []
        if kind == UNAVAILABLE:
            return [], [f"{label} merge proof is unavailable: {proof.get('reason', 'unspecified')}"]
        return [], [f"{label} merge proof kind is unavailable or unsupported"]
    legacy = bundle.get("merge_contains_head")
    if legacy is True:
        return [], [
            f"{label} legacy merge_contains_head=true cannot replace a structured merge proof"
        ]
    if legacy is False:
        return [], [
            f"{label} ancestry is false, but exact-tree squash proof is unavailable"
        ]
    return [], [f"{label} reviewed-head merge proof is unavailable"]


def exact_governance_waiver_verified(
    governance: Mapping[str, Any], snapshot: Mapping[str, Any], now: dt.datetime,
) -> bool:
    if governance.get("signed_waiver_verified") is not True:
        return False
    evidence = governance.get("waiver_evidence")
    if not isinstance(evidence, dict):
        return False
    identities = evidence.get("signer_identities")
    reviewers = snapshot.get("reviewed_by")
    producer = snapshot.get("producer")
    commit_range = evidence.get("commit_range")
    checks = evidence.get("required_status_checks")
    valid_from = parse_canonical_int64(evidence.get("valid_from_us"))
    expires = parse_canonical_int64(evidence.get("expires_at_us"))
    now_us = int(now.timestamp() * 1_000_000)
    declared_digest = evidence.get("procedure_sha256")
    unsigned = dict(evidence)
    unsigned.pop("procedure_sha256", None)
    try:
        actual_digest = sha256_bytes(jcs_canonical_bytes(unsigned))
    except ValueError:
        actual_digest = None
    milestones = snapshot.get("milestones")
    b01 = milestones.get("B01") if isinstance(milestones, dict) else None
    source = b01.get("source") if isinstance(b01, dict) else None
    source_pr = source.get("pr") if isinstance(source, dict) else None
    source_base = source_pr.get("base") if isinstance(source_pr, dict) else None
    source_head = source_pr.get("head") if isinstance(source_pr, dict) else None
    expected_start = source_base.get("sha") if isinstance(source_base, dict) else None
    expected_ends = {
        source_head.get("sha") if isinstance(source_head, dict) else None,
        source_pr.get("merge_commit_sha") if isinstance(source_pr, dict) else None,
    }
    return bool(
        evidence.get("schema") == "triad.github.exact_equivalent_control_procedure.v1"
        and str(evidence.get("repository", "")).lower() == EXPECTED_REPOSITORY
        and evidence.get("issue_number") == 5
        and evidence.get("branch") == snapshot.get("default_branch")
        and isinstance(commit_range, dict)
        and set(commit_range) == {"start_sha", "end_sha"}
        and is_hex_sha(expected_start, 40) and commit_range.get("start_sha") == expected_start
        and is_hex_sha(commit_range.get("end_sha"), 40)
        and commit_range.get("end_sha") in expected_ends
        and isinstance(evidence.get("approver"), str) and evidence.get("approver", "").strip()
        and isinstance(evidence.get("abort_path"), str) and evidence.get("abort_path", "").strip()
        and isinstance(checks, list) and checks
        and all(isinstance(item, str) and item.strip() for item in checks)
        and len(checks) == len(set(checks))
        and evidence.get("final_head_review_required") is True
        and evidence.get("resolved_conversations_required") is True
        and evidence.get("stale_head_rejection_required") is True
        and evidence.get("bypass_allowed") is False
        and is_nonzero_sha256(evidence.get("negative_early_merge_test_sha256"))
        and is_nonzero_sha256(evidence.get("negative_bypass_test_sha256"))
        and valid_from is not None and expires is not None
        and valid_from <= now_us < expires
        and 0 < expires - valid_from <= MAX_RECEIPT_TTL_US
        and is_nonzero_sha256(declared_digest) and declared_digest == actual_digest
        and isinstance(identities, list)
        and isinstance(reviewers, list)
        and producer in identities
        and any(reviewer in identities for reviewer in reviewers)
        and evidence.get("approver") in reviewers
        and len({item for item in identities if isinstance(item, str) and item.strip()}) >= 2
    )


def github_governance_issues(
    snapshot: Mapping[str, Any], *, now: dt.datetime | None = None,
) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    incomplete: list[str] = []
    governance = snapshot.get("governance")
    if not isinstance(governance, dict):
        return [], ["normalized detailed governance evidence is unavailable"]
    waiver = exact_governance_waiver_verified(governance, snapshot, now or utc_now())
    if governance.get("signed_waiver_verified") is True and not waiver:
        failures.append("governance waiver claim lacks exact independently signed waiver evidence")

    issue = snapshot.get("issue_5")
    if not waiver:
        if not isinstance(issue, dict) or "unavailable" in issue:
            incomplete.append("governance control-gap issue #5 state is unavailable")
        else:
            state = str(issue.get("state", "")).lower()
            if issue.get("number") != 5:
                failures.append("governance evidence does not refer to control-gap issue #5")
            if state == "open":
                failures.append("governance control-gap issue #5 remains open without an exact signed waiver")
            elif state != "closed":
                incomplete.append("governance control-gap issue #5 has no closed/open state proof")

    bypass = governance.get("bypass_used")
    if bypass is True:
        failures.append(
            "a governance bypass was used; an exact-equivalent procedure does not authorize bypass")
    elif bypass is not False:
        incomplete.append("governance bypass-use evidence is unavailable")

    if not waiver:
        controls = governance.get("default_branch_controls")
        if not isinstance(controls, dict):
            incomplete.append(
                "detailed default-branch ruleset/required-status-check proof is unavailable; "
                "active ruleset summaries are insufficient")
        else:
            default_branch = snapshot.get("default_branch")
            expected_ref = f"refs/heads/{default_branch}" if isinstance(default_branch, str) else None
            ruleset_ids = controls.get("ruleset_ids")
            approving = controls.get("required_approving_review_count")
            checks = controls.get("required_status_checks")
            valid = bool(
                controls.get("schema") == "triad.github.default_branch_controls.v1"
                and expected_ref is not None and controls.get("target_ref") == expected_ref
                and isinstance(ruleset_ids, list) and ruleset_ids
                and all(
                    isinstance(item, int) and not isinstance(item, bool) and item > 0
                    for item in ruleset_ids)
                and len(ruleset_ids) == len(set(ruleset_ids))
                and controls.get("pull_request_required") is True
                and isinstance(approving, int) and not isinstance(approving, bool) and approving >= 1
                and controls.get("resolved_conversations_required") is True
                and controls.get("stale_head_rejection_required") is True
                and isinstance(checks, list) and checks
                and all(isinstance(item, str) and item.strip() for item in checks)
                and len(checks) == len(set(checks))
                and controls.get("required_status_checks_strict") is True
            )
            if not valid:
                failures.append("detailed default-branch governance controls are malformed or insufficient")
    return list(dict.fromkeys(failures)), list(dict.fromkeys(incomplete))


def github_milestone_gate_issues(
    snapshot: Mapping[str, Any], milestone: str, *, expected_subject_sha: str | None = None,
    local_receipt_payload: Mapping[str, Any] | None = None,
    now: dt.datetime | None = None,
) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    incomplete: list[str] = []
    milestone_map = snapshot.get("milestones")
    if not isinstance(milestone_map, dict):
        return failures, ["normalized source+detached-receipt milestone facts are unavailable"]
    fact = milestone_map.get(milestone)
    if not isinstance(fact, dict):
        return failures, [f"normalized {milestone} GitHub facts are unavailable"]
    source_numbers = fact.get("source_candidate_numbers")
    receipt_numbers = fact.get("receipt_candidate_numbers")
    if not isinstance(source_numbers, list):
        incomplete.append(f"{milestone} source candidate list is unavailable or malformed")
        source_numbers = []
    if not isinstance(receipt_numbers, list):
        incomplete.append(f"{milestone} receipt candidate list is unavailable or malformed")
        receipt_numbers = []
    if len(source_numbers) > 1:
        incomplete.append(f"{milestone} has ambiguous source PR candidates: {source_numbers}")
    if len(receipt_numbers) > 1:
        incomplete.append(f"{milestone} has ambiguous receipt PR candidates: {receipt_numbers}")
    source_fail, source_incomplete, source = github_pull_bundle_issues(
        fact.get("source"), label=f"{milestone} source", required_steps=REQUIRED_CI_STEPS)
    receipt_fail, receipt_incomplete, receipt = github_pull_bundle_issues(
        fact.get("receipt"), label=f"{milestone} receipt", required_steps=REQUIRED_RECEIPT_CI_STEPS)
    failures.extend(source_fail + receipt_fail)
    incomplete.extend(source_incomplete + receipt_incomplete)
    source_bundle = fact.get("source")
    if isinstance(source_bundle, dict):
        merge_failures, merge_incomplete = github_source_merge_proof_issues(
            source_bundle, f"{milestone} source")
        failures.extend(merge_failures)
        incomplete.extend(merge_incomplete)
    if milestone == "B10" and isinstance(fact.get("receipt"), dict):
        receipt_pr = fact["receipt"].get("pr")
        base = receipt_pr.get("base") if isinstance(receipt_pr, dict) else None
        base_ref = base.get("ref") if isinstance(base, dict) else None
        default_branch = snapshot.get("default_branch")
        if not isinstance(base_ref, str) or not base_ref:
            incomplete.append("B10 terminal receipt evidence-ref PR base is unavailable")
        elif base_ref == default_branch:
            failures.append("B10 terminal receipt PR targets the default branch instead of an evidence ref")
    if source and receipt:
        if source.get("number") == receipt.get("number"):
            failures.append(f"{milestone} source and receipt use the same PR")
        if source.get("merged_at") and receipt.get("created_at") and receipt["created_at"] <= source["merged_at"]:
            failures.append(f"{milestone} receipt PR was not created after source merge")
        if source.get("merged_at") and receipt.get("last_commit_at") and receipt["last_commit_at"] <= source["merged_at"]:
            failures.append(f"{milestone} receipt commit was not authored after source merge")
        receipt_contains = fact.get("receipt", {}).get("contains_source_merge")
        if receipt_contains is False:
            failures.append(f"{milestone} detached receipt head does not prove source-merge ancestry")
        elif receipt_contains is not True:
            incomplete.append(f"{milestone} detached receipt source-merge ancestry proof is unavailable")
        if local_receipt_payload:
            if local_receipt_payload.get("build_commit") != source.get("merge_sha"):
                failures.append(f"{milestone} receipt build_commit does not equal source merge commit")
            if local_receipt_payload.get("merge_commit") != source.get("merge_sha"):
                failures.append(f"{milestone} receipt merge_commit does not equal source merge commit")
            if local_receipt_payload.get("source_pr") != source.get("number"):
                failures.append(f"{milestone} receipt source_pr does not equal normalized source PR")
            if local_receipt_payload.get("receipt_pr") != receipt.get("number"):
                failures.append(f"{milestone} receipt receipt_pr does not equal normalized detached receipt PR")
            countersigner = local_receipt_payload.get("reviewer")
            if countersigner not in receipt.get("approved_reviewers", []):
                failures.append(f"{milestone} receipt countersigner is not an approved detached-receipt reviewer")
            if local_receipt_payload.get("source_head_sha") != source.get("head_sha"):
                failures.append(f"{milestone} receipt source_head_sha does not equal normalized source head")
            if local_receipt_payload.get("review_head_sha") != source.get("head_sha"):
                failures.append(f"{milestone} receipt review_head_sha does not equal normalized source head")
            signed_review_us = parse_canonical_int64(local_receipt_payload.get("reviewed_at_us"))
            source_reviewed = source.get("approved_at")
            if signed_review_us is None or source_reviewed is None:
                incomplete.append(f"{milestone} signed/GitHub source-review chronology cannot be compared")
            elif abs(signed_review_us - int(source_reviewed.timestamp() * 1_000_000)) > 1_000_000:
                failures.append(f"{milestone} signed reviewed_at_us disagrees with GitHub source review")
            signed_runs = local_receipt_payload.get("ci_runs")
            signed_run_ids = {
                row.get("run_id") for row in signed_runs if isinstance(row, dict)
            } if isinstance(signed_runs, list) else set()
            source_bundle = fact.get("source") if isinstance(fact, dict) else None
            source_runs = source_bundle.get("workflow_runs", []) if isinstance(source_bundle, dict) else []
            actual_run_ids = {
                run.get("id") for run in source_runs
                if isinstance(run, dict)
                and run.get("head_sha") == source.get("head_sha")
                and run.get("status") == "completed" and run.get("conclusion") == "success"
            }
            if not signed_run_ids or not signed_run_ids.issubset(actual_run_ids):
                failures.append(f"{milestone} signed receipt CI run IDs do not match normalized exact-head runs")
            signed_merge_us = parse_canonical_int64(local_receipt_payload.get("source_merge_at_us"))
            source_merged = source.get("merged_at")
            if signed_merge_us is None or source_merged is None:
                incomplete.append(f"{milestone} signed/GitHub source-merge chronology cannot be compared")
            elif abs(signed_merge_us - int(source_merged.timestamp() * 1_000_000)) > 1_000_000:
                failures.append(f"{milestone} signed source_merge_at_us disagrees with GitHub source merge")
    if expected_subject_sha and source:
        allowed = {source.get("head_sha"), source.get("merge_sha"), receipt.get("head_sha"), receipt.get("merge_sha")}
        if expected_subject_sha not in allowed:
            incomplete.append(f"expected subject SHA {expected_subject_sha} is not a normalized source/receipt identity")

    governance_failures, governance_incomplete = github_governance_issues(snapshot, now=now)
    failures.extend(governance_failures)
    incomplete.extend(governance_incomplete)
    return list(dict.fromkeys(failures)), list(dict.fromkeys(incomplete))


def github_predecessor_chronology_issues(
    snapshot: Mapping[str, Any], milestone: str,
) -> tuple[list[str], list[str]]:
    predecessor = PREDECESSOR[milestone]
    if predecessor is None:
        return [], []
    milestone_map = snapshot.get("milestones")
    if not isinstance(milestone_map, dict):
        return [], [f"{milestone} predecessor {predecessor} normalized facts are unavailable"]
    current = milestone_map.get(milestone)
    prior = milestone_map.get(predecessor)
    source_bundle = current.get("source") if isinstance(current, dict) else None
    predecessor_receipt = prior.get("receipt") if isinstance(prior, dict) else None
    source_pr = source_bundle.get("pr") if isinstance(source_bundle, dict) else None
    predecessor_pr = predecessor_receipt.get("pr") if isinstance(predecessor_receipt, dict) else None
    predecessor_merged = parse_iso(predecessor_pr.get("merged_at")) if isinstance(predecessor_pr, dict) else None
    source_created = parse_iso(source_pr.get("created_at")) if isinstance(source_pr, dict) else None
    if predecessor_merged is None:
        return [], [f"{milestone} predecessor {predecessor} detached-receipt merge evidence is unavailable"]
    if source_created is None:
        return [], [f"{milestone} source PR creation time is unavailable"]
    if source_created <= predecessor_merged:
        return [f"{milestone} source PR began before predecessor {predecessor} receipt merged"], []
    return [], []


def normalize_milestone_from_text(value: str) -> str | None:
    match = re.search(r"\bB(0[1-9]|10)(?:C|R)?\b", value.upper())
    return f"B{match.group(1)}" if match else None


def find_json_receipt(repo: pathlib.Path, milestone: str) -> pathlib.Path | None:
    candidates: list[pathlib.Path] = []
    for name in MILESTONE_RECEIPT_NAMES[milestone]:
        candidates.extend([
            repo / "evidence" / "receipts" / f"{name}.json",
            repo / "evidence" / "terminal" / f"{name}.json",
            repo / "evidence" / f"{name}.json",
        ])
    return next((path for path in candidates if path.is_file()), None)


def walk_named_values(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    if isinstance(value, dict):
        for key, item in value.items():
            current = path + (str(key),)
            yield current, item
            yield from walk_named_values(item, current)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk_named_values(item, path + (str(index),))


def receipt_profile_decision_issues(
    path: pathlib.Path, external_sha256: str | None,
) -> list[str]:
    issues: list[str] = []
    if not is_nonzero_sha256(external_sha256):
        return ["receipt-profile decision cannot be interpreted without its external SHA-256 pin"]
    try:
        if path.stat().st_size > 1_000_000:
            return ["receipt-profile decision exceeds 1 MB bounded-input limit"]
        raw = path.read_bytes()
        decision = strict_json_loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, DuplicateJSONKey, RecursionError) as exc:
        return [f"receipt-profile decision is unreadable or invalid JSON: {exc}"]
    if sha256_bytes(raw) != external_sha256:
        issues.append("receipt-profile decision bytes do not match the external pin")
    if not isinstance(decision, dict):
        return issues + ["receipt-profile decision root must be an object"]
    if set(decision) != set(SUPPORTED_RECEIPT_PROFILE_DECISION):
        issues.append("receipt-profile decision keys do not match the closed supported profile")
    for key, expected in SUPPORTED_RECEIPT_PROFILE_DECISION.items():
        if decision.get(key) != expected:
            issues.append(
                f"receipt-profile decision {key}={decision.get(key)!r}; "
                f"runner supports only ratified value {expected!r}")
    return list(dict.fromkeys(issues))


def receipt_issues(
    path: pathlib.Path,
    milestone: str,
    now: dt.datetime,
    *,
    repository_root: pathlib.Path | None = None,
    trust_registry_path: pathlib.Path | None = None,
    trust_registry_sha256: str | None = None,
    receipt_profile_decision_sha256: str | None = None,
) -> tuple[list[str], dict[str, Any] | None]:
    """Independently validate one v3 receipt.

    The receipt never gets to authenticate or define its own profile.  PASS requires an externally
    pinned trust registry, an externally pinned ratified receipt-profile decision preimage, and two
    independently verified DSSE/Ed25519 signatures over the exact canonical payload bytes.
    Embedded ``verified`` booleans are deliberately ignored.
    """
    issues: list[str] = []
    if path.is_symlink():
        return ["receipt path is a symbolic link"], None
    try:
        if path.stat().st_size > 16_000_000:
            return ["receipt exceeds 16 MB bounded-input limit"], None
    except OSError as exc:
        return [f"receipt cannot be stated: {exc}"], None
    try:
        event = strict_json_loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, DuplicateJSONKey, RecursionError) as exc:
        return [f"receipt is unreadable or invalid JSON: {exc}"], None
    if not isinstance(event, dict):
        return ["receipt root must be an object"], None
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else event
    if event.get("schema") != "triad.evidence_receipt.v3":
        issues.append("receipt schema is not triad.evidence_receipt.v3")
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
        if not isinstance(payload.get("predecessor_receipt_id"), str) or not payload.get("predecessor_receipt_id"):
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
    review_head_sha = payload.get("review_head_sha")
    if not is_hex_sha(source_head_sha, 40) or source_head_sha == "0" * 40:
        issues.append("receipt source_head_sha is not a real exact 40-hex PR head")
    if review_head_sha != source_head_sha:
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
        for index, run in enumerate(ci_runs):
            if not isinstance(run, dict):
                issues.append(f"receipt ci_runs[{index}] is not an object")
                continue
            if (
                isinstance(run.get("run_id"), int) and not isinstance(run.get("run_id"), bool)
                and run.get("run_id") > 0 and run.get("head_sha") == source_head_sha
                and run.get("conclusion") == "SUCCESS" and run.get("required_jobs_unskipped") is True
            ):
                valid_ci = True
        if not valid_ci:
            issues.append("receipt has no successful unskipped CI run bound to source_head_sha")
    governance = payload.get("governance")
    if not isinstance(governance, dict) or set(governance) != {"branch_rules_enforced", "bypass_used"}:
        issues.append("receipt governance must be the closed branch-rules/bypass object")
    elif governance != {"branch_rules_enforced": True, "bypass_used": False}:
        issues.append("receipt governance does not prove enforced rules and no bypass")
    corrections = payload.get("correction_of_receipt_ids")
    if not isinstance(corrections, list) or any(not isinstance(item, str) or not item for item in corrections):
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
        value = payload.get(field)
        if not is_nonzero_sha256(value):
            issues.append(f"required {role} digest {field} is not a non-zero lowercase SHA-256")
    if not is_nonzero_sha256(receipt_profile_decision_sha256):
        issues.append("external receipt-profile decision SHA-256 pin is unavailable")
    elif payload.get("receipt_profile_decision_sha256") != receipt_profile_decision_sha256:
        issues.append(
            "receipt_profile_decision_sha256 does not match the external DECISION-RECEIPT-PROFILE-001 pin")

    digest_fields = []
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
    allowed_roles = {role for _, role in REQUIRED_RECEIPT_DIGEST_ROLES} | {
        "CHECK_EVIDENCE_INDEX", "GITHUB_EVIDENCE", "REVIEW_EVIDENCE", "OTHER",
    }
    root = repository_root.resolve() if repository_root else None
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
        if digest_role not in allowed_roles:
            issues.append(f"evidence[{index}] has invalid digest_role {digest_role!r}")
        elif digest_role in role_hashes:
            issues.append(f"evidence digest_role {digest_role} is duplicated")
        elif isinstance(digest, str):
            role_hashes[digest_role] = digest
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
                f"evidence[{index}] remote URI is not fetched by this verifier; a bundled local preimage is required")
            continue
        if root is None:
            issues.append(f"evidence[{index}] local preimage cannot be verified without repository root")
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
                issues.extend(receipt_profile_decision_issues(
                    candidate, receipt_profile_decision_sha256))
    if len(evidence_ids) != len(evidence_hashes):
        issues.append("evidence ID and SHA-256 cardinality differ")
    if len(set(evidence_ids)) != len(evidence_ids):
        issues.append("evidence IDs are duplicated")
    for field, role in REQUIRED_RECEIPT_DIGEST_ROLES:
        if role_hashes.get(role) != payload.get(field):
            issues.append(f"required digest {field} is not recomputed from exactly one typed {role} preimage")
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
        source_merge_us = int(time_fields["source_merge_at_us"])
        observed_us = int(time_fields["observed_at_us"])
        emitted_us = int(time_fields["emitted_at_us"])
        expires_us = int(time_fields["expires_at_us"])
        now_us = int(now.timestamp() * 1_000_000)
        if reviewed_at_us is not None and reviewed_at_us > source_merge_us:
            issues.append("receipt review completed after the source merge")
        if not source_merge_us <= observed_us <= emitted_us:
            issues.append("receipt chronology is not source_merge <= observed <= emitted")
        for index, item_observed_us in evidence_observed:
            if not source_merge_us <= item_observed_us <= observed_us:
                issues.append(
                    f"evidence[{index}] chronology is not source_merge <= evidence_observed <= receipt_observed")
        if emitted_us > now_us + REPOSITORY_FUTURE_TOLERANCE_US:
            issues.append(
                "receipt claims evidence from the future; repository/provider evidence "
                "has zero future tolerance")
        ttl = expires_us - emitted_us
        if ttl <= 0 or ttl > MAX_RECEIPT_TTL_US:
            issues.append("receipt validity must be positive and at most 30 days")
        if expires_us <= now_us:
            issues.append("receipt is expired at verifier time")

    builder = str(payload.get("builder", "")).strip()
    reviewer = str(payload.get("reviewer", "")).strip()
    if not builder or not reviewer or builder == reviewer:
        issues.append("receipt builder and reviewer are missing or not independent")
    if re.search(r"(?i)github-actions|ci-run|workflow", reviewer):
        issues.append("a CI run is recorded as reviewer; this is not independent review")

    signature = payload.get("signature")
    if isinstance(signature, str) and is_hex_sha(signature, 64):
        unsigned = dict(payload)
        unsigned["signature"] = ""
        if sha256_bytes(canonical_json_bytes(unsigned)) == signature:
            issues.append("receipt signature is only a deterministic self-hash, not authentication")
    if trust_registry_path is None or not is_nonzero_sha256(trust_registry_sha256):
        issues.append("independent pinned trust registry/path is unavailable")
        registry: dict[str, Any] | None = None
    else:
        try:
            registry_bytes = trust_registry_path.read_bytes()
            registry = strict_json_loads(registry_bytes.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, DuplicateJSONKey, RecursionError) as exc:
            issues.append(f"independent trust registry is unreadable: {exc}")
            registry = None
        else:
            if sha256_bytes(registry_bytes) != trust_registry_sha256:
                issues.append("independent trust registry digest does not match external pin")
            if payload.get("trust_registry_sha256") != trust_registry_sha256:
                issues.append("signed receipt trust_registry_sha256 does not match external pin")
            if not isinstance(registry, dict) or registry.get("schema") != "triad.receipt_trust_registry.v1":
                issues.append("independent trust registry schema is not triad.receipt_trust_registry.v1")

    envelope = event.get("dsse") or event.get("envelope")
    if not isinstance(envelope, dict):
        issues.append("receipt has no DSSE envelope")
    else:
        payload_type = envelope.get("payloadType")
        encoded_payload = strict_base64(envelope.get("payload"))
        if payload_type != RECEIPT_PAYLOAD_TYPE:
            issues.append("DSSE payloadType is not the closed receipt-v3 media type")
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
        signatures = envelope.get("signatures")
        verified_signers: list[tuple[str, str, str]] = []
        registry_keys = registry.get("keys") if isinstance(registry, dict) else None
        registry_key_ids = [str(row.get("key_id")) for row in registry_keys if isinstance(row, dict)] \
            if isinstance(registry_keys, list) else []
        if len(registry_key_ids) != len(set(registry_key_ids)):
            issues.append("independent trust registry contains duplicate key IDs")
        key_rows = {
            str(row.get("key_id")): row for row in registry_keys if isinstance(row, dict)
        } if isinstance(registry_keys, list) else {}
        if not isinstance(signatures, list) or len(signatures) < 2:
            issues.append("DSSE requires producer and independent countersigner signatures")
            signatures = []
        if encoded_payload is not None and isinstance(payload_type, str):
            pae = dsse_pae(payload_type, encoded_payload)
            emitted_us = parse_canonical_int64(payload.get("emitted_at_us"))
            for index, row in enumerate(signatures):
                if not isinstance(row, dict):
                    issues.append(f"DSSE signature[{index}] is not an object")
                    continue
                key_id = str(row.get("keyid") or "")
                key = key_rows.get(key_id)
                if key is None:
                    issues.append(f"DSSE signer key {key_id!r} is not approved by pinned registry")
                    continue
                if str(key.get("algorithm", "")).upper() != "ED25519":
                    issues.append(f"DSSE signer key {key_id!r} is not Ed25519")
                    continue
                if str(key.get("status", "")).upper() != "ACTIVE":
                    issues.append(f"DSSE signer key {key_id!r} is not ACTIVE")
                    continue
                approved = key.get("approved_milestones", [])
                if approved not in ("ALL", ["ALL"]) and (not isinstance(approved, list) or milestone not in approved):
                    issues.append(f"DSSE signer key {key_id!r} is not approved for {milestone}")
                    continue
                valid_from = parse_canonical_int64(key.get("valid_from_us"))
                valid_until = parse_canonical_int64(key.get("valid_until_us"))
                revoked_at = parse_canonical_int64(key.get("revoked_at_us")) if key.get("revoked_at_us") is not None else None
                if key.get("revoked_at_us") is not None and revoked_at is None:
                    issues.append(f"DSSE signer key {key_id!r} has malformed revoked_at_us")
                    continue
                if emitted_us is None or valid_from is None or valid_until is None or not valid_from <= emitted_us < valid_until:
                    issues.append(f"DSSE signer key {key_id!r} is outside its validity window")
                    continue
                if revoked_at is not None and revoked_at <= emitted_us:
                    issues.append(f"DSSE signer key {key_id!r} was revoked at emission")
                    continue
                public_key = strict_base64(key.get("public_key_base64"), 32)
                signature_bytes = strict_base64(row.get("sig"), 64)
                if public_key is None or signature_bytes is None or not ed25519_verify(public_key, pae, signature_bytes):
                    issues.append(f"DSSE signature[{index}] failed independent Ed25519 verification")
                    continue
                identity = str(key.get("identity", "")).strip()
                role = str(key.get("role", "")).upper()
                if not identity or role not in {"PRODUCER", "COUNTERSIGNER"}:
                    issues.append(f"DSSE signer key {key_id!r} lacks approved identity/role")
                    continue
                verified_signers.append((key_id, identity, role))
        if len({item[0] for item in verified_signers}) < 2 or len({item[1] for item in verified_signers}) < 2:
            issues.append("receipt lacks two distinct independently verified signer identities")
        roles = {item[2] for item in verified_signers}
        if not {"PRODUCER", "COUNTERSIGNER"}.issubset(roles):
            issues.append("receipt lacks verified producer and countersigner roles")
        signer_identities = {item[1] for item in verified_signers}
        if builder and builder not in signer_identities:
            issues.append("receipt builder is not an independently verified signer identity")
        elif builder and (builder, "PRODUCER") not in {(item[1], item[2]) for item in verified_signers}:
            issues.append("receipt builder is not the verified PRODUCER signer")
        if reviewer and reviewer not in signer_identities:
            issues.append("receipt reviewer is not an independently verified signer identity")
        elif reviewer and (reviewer, "COUNTERSIGNER") not in {(item[1], item[2]) for item in verified_signers}:
            issues.append("receipt reviewer is not the verified COUNTERSIGNER signer")
    return list(dict.fromkeys(issues)), event


def run_git(repo: pathlib.Path, *args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args], text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=timeout, check=False,
        env={"PATH": os.environ.get("PATH", ""), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC"})


def normalize_git_repository(remote: str) -> str | None:
    """Normalize common SSH/HTTPS Git remotes to lowercase owner/name."""
    value = remote.strip().rstrip("/")
    if value.endswith(".git"):
        value = value[:-4]
    match = re.search(r"(?:github\.com|git\.chatgpt-team\.site)(?::|/)([^/\s:]+)/([^/\s]+)$", value, re.I)
    if not match:
        return None
    return f"{match.group(1)}/{match.group(2)}".lower()


def tracked_files(repo: pathlib.Path) -> list[pathlib.Path]:
    result = run_git(repo, "ls-files", "-z")
    if result.returncode != 0:
        return []
    return [repo / item for item in result.stdout.split("\0") if item]


def independent_static_issues(repo: pathlib.Path) -> tuple[list[str], list[tuple[str, pathlib.Path]]]:
    issues: list[str] = []
    secret_hits: list[tuple[str, pathlib.Path]] = []

    manifest = repo / "docs" / "control" / "rc3_effective_bundle_manifest.json"
    if not manifest.is_file():
        issues.append("missing docs/control/rc3_effective_bundle_manifest.json")
    else:
        try:
            data = strict_json_loads(manifest.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("manifest root is not an object")
            counts = data.get("effective_counts", {})
            for key, expected in EXPECTED_EFFECTIVE_COUNTS.items():
                if counts.get(key) != expected:
                    issues.append(f"effective count {key}={counts.get(key)!r}; expected {expected}")
            if data.get("activation_result") != ACTIVATION_RESULT:
                issues.append("RC3 effective manifest does not remain DENIED_SAFE_HOLD")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, DuplicateJSONKey, ValueError) as exc:
            issues.append(f"RC3 effective manifest invalid: {exc}")

    rc4_bundle = repo / "docs" / "control" / "rc4_control_bundle.json"
    if not rc4_bundle.is_file():
        issues.append("missing docs/control/rc4_control_bundle.json")
    else:
        try:
            rc4 = strict_json_loads(rc4_bundle.read_text(encoding="utf-8"))
            if not isinstance(rc4, dict):
                raise ValueError("bundle root is not an object")
            verifications = rc4.get("verifications")
            if not isinstance(verifications, list) or len(verifications) != EXPECTED_RC4_FIXTURE_COUNT:
                actual = len(verifications) if isinstance(verifications, list) else None
                issues.append(f"RC4 verification/fixture count {actual!r}; expected {EXPECTED_RC4_FIXTURE_COUNT}")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, DuplicateJSONKey, ValueError) as exc:
            issues.append(f"RC4 control bundle invalid: {exc}")

    tracked = tracked_files(repo)
    if not tracked:
        issues.append("cannot enumerate any tracked files for independent static audit")
    for path in tracked:
        try:
            relative = path.relative_to(repo)
        except ValueError:
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file() or path.stat().st_size > 8_000_000:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for name, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                secret_hits.append((name, relative))
        if re.search(r'(?m)^\s*F24\s*,|"formula_id"\s*:\s*"F24"|"id"\s*:\s*"F24"', text):
            issues.append(f"affirmative F24 registry row found in {relative}")

    src = repo / "src" / "triad_origin"
    if src.is_dir():
        for path in src.rglob("*.py"):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (SyntaxError, UnicodeError) as exc:
                issues.append(f"cannot independently parse {path.relative_to(repo)}: {exc}")
                continue
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    if name.split(".")[0] in FORBIDDEN_IMPORT_ROOTS:
                        issues.append(f"forbidden venue/network capability import {name} in {path.relative_to(repo)}")
    if secret_hits:
        for name, path in secret_hits[:20]:
            issues.append(f"credential-like pattern {name} in tracked file {path}")
        if len(secret_hits) > 20:
            issues.append(f"and {len(secret_hits) - 20} additional credential-like tracked-file hits")
    return list(dict.fromkeys(issues)), secret_hits


def spec_control_count_output_issues(stdout: str) -> list[str]:
    try:
        value = strict_json_loads(stdout)
    except (json.JSONDecodeError, DuplicateJSONKey) as exc:
        return [f"spec/control count command did not emit one JSON object: {exc}"]
    if not isinstance(value, dict) or value.get("schema") != "triad.origin.spec_control_counts.v1":
        return ["spec/control count output schema must be triad.origin.spec_control_counts.v1"]
    expected = {
        "rc1_test_count": EXPECTED_RC1_TEST_COUNT,
        "rc3_effective_verification_count": EXPECTED_EFFECTIVE_COUNTS["effective_verification_count"],
        "rc4_fixture_count": EXPECTED_RC4_FIXTURE_COUNT,
    }
    return [
        f"spec/control count {key}={value.get(key)!r}; expected {wanted}"
        for key, wanted in expected.items() if value.get(key) != wanted
    ]


def validate_check_evidence_index(
    repo: pathlib.Path, path: pathlib.Path, subject_sha: str, known_ids: set[str],
    *, now: dt.datetime, trust_registry_path: pathlib.Path | None,
    trust_registry_sha256: str | None,
    receipt_profile_decision_sha256: str | None = None,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    issues: list[str] = []
    results: dict[str, dict[str, Any]] = {}
    if not path.is_file():
        return results, [f"check evidence index unavailable at {path}"]
    if path.is_symlink():
        return results, ["check evidence index path is a symbolic link"]
    if path.stat().st_size > 32_000_000:
        return results, ["check evidence index exceeds 32 MB bounded-input limit"]
    try:
        data = strict_json_loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, DuplicateJSONKey, RecursionError) as exc:
        return results, [f"check evidence index invalid: {exc}"]
    if not isinstance(data, dict):
        return results, ["check evidence index root must be an object"]
    if data.get("schema") != CHECK_EVIDENCE_SCHEMA:
        issues.append(f"check evidence index schema must be {CHECK_EVIDENCE_SCHEMA}")
    if data.get("subject_sha") != subject_sha:
        issues.append("check evidence index subject_sha does not match audited exact head")
    producer = str(data.get("producer", ""))
    reviewers = data.get("reviewed_by")
    if not producer or not isinstance(reviewers, list) or not reviewers or producer in reviewers:
        issues.append("check evidence index lacks independent producer/reviewer identities")
    root = repo.resolve()
    auth_relative = data.get("authentication_receipt_path")
    auth_milestone = normalize_milestone_from_text(str(data.get("authentication_receipt_milestone", "")))
    if not isinstance(auth_relative, str) or not auth_relative or auth_milestone is None:
        issues.append("check evidence index lacks an authenticated receipt preimage reference")
    else:
        raw_auth_path = repo / pathlib.Path(auth_relative)
        auth_path = raw_auth_path.resolve()
        if raw_auth_path.is_symlink():
            issues.append("check evidence authentication receipt path is a symbolic link")
        elif auth_path != root and root not in auth_path.parents:
            issues.append("check evidence authentication receipt path escapes repository")
        elif not auth_path.is_file():
            issues.append("check evidence authentication receipt preimage is missing")
        else:
            auth_issues, auth_event = receipt_issues(
                auth_path, auth_milestone, now, repository_root=repo,
                trust_registry_path=trust_registry_path,
                trust_registry_sha256=trust_registry_sha256,
                receipt_profile_decision_sha256=receipt_profile_decision_sha256,
            )
            if auth_issues:
                issues.append("check evidence authentication receipt failed: " + "; ".join(auth_issues))
            else:
                auth_payload = (auth_event or {}).get("payload", {})
                if not isinstance(auth_payload, dict) or auth_payload.get("build_commit") != subject_sha:
                    issues.append("check evidence authentication receipt does not bind audited exact head")
                try:
                    relative_index = str(path.resolve().relative_to(root))
                except ValueError:
                    issues.append("check evidence index is outside repository and cannot be receipt-bound")
                else:
                    auth_rows = (auth_event or {}).get("payload", {}).get("evidence", [])
                    if not isinstance(auth_rows, list):
                        auth_rows = []
                    bound = any(
                        isinstance(row, dict)
                        and row.get("path") == relative_index
                        and row.get("sha256") == sha256_file(path)
                        for row in auth_rows
                    )
                    if not bound:
                        issues.append("authenticated receipt does not bind the exact check evidence index bytes")
    header_issue_count = len(issues)
    rows = data.get("checks")
    if not isinstance(rows, list):
        return results, issues + ["check evidence index checks must be an array"]
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            issues.append("check evidence index contains a non-object row")
            continue
        check_id = str(row.get("check_id", ""))
        if check_id in seen:
            issues.append(f"duplicate check evidence ID {check_id}")
            continue
        seen.add(check_id)
        if check_id not in known_ids:
            issues.append(f"unknown check evidence ID {check_id}")
            continue
        outcome = str(row.get("outcome", ""))
        if outcome not in VALID_OUTCOMES:
            issues.append(f"check {check_id} has invalid outcome {outcome!r}")
            continue
        evidence = row.get("evidence")
        verified_evidence: list[str] = []
        if outcome in {PASS, PARTIAL} and (not isinstance(evidence, list) or not evidence):
            issues.append(f"check {check_id} claims {outcome} without evidence preimages")
            continue
        row_bad = False
        for item in evidence if isinstance(evidence, list) else []:
            if not isinstance(item, dict):
                row_bad = True
                issues.append(f"check {check_id} has a non-object evidence item")
                continue
            rel = pathlib.Path(str(item.get("path", "")))
            raw_candidate = repo / rel
            candidate = raw_candidate.resolve()
            if root not in candidate.parents and candidate != root:
                row_bad = True
                issues.append(f"check {check_id} evidence path escapes repository: {rel}")
                continue
            if raw_candidate.is_symlink():
                row_bad = True
                issues.append(f"check {check_id} evidence path is a symbolic link: {rel}")
                continue
            if not candidate.is_file():
                row_bad = True
                issues.append(f"check {check_id} evidence file missing: {rel}")
                continue
            expected = item.get("sha256")
            actual = sha256_file(candidate)
            if not is_nonzero_sha256(expected) or expected != actual:
                row_bad = True
                issues.append(f"check {check_id} evidence digest mismatch: {rel}")
                continue
            verified_evidence.append(str(rel))
        if not row_bad:
            results[check_id] = {**row, "verified_evidence": verified_evidence}
    # Header/authentication failures invalidate every row; a per-row PASS must never survive a
    # wrong head, self-declared auth boolean, or unbound index.
    if header_issue_count:
        results = {}
    return results, issues


class AuditRunner:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.started = utc_now()
        self.run_id = f"{self.started.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
        self.selected = parse_milestones(args.milestones)
        self.results = {
            row.check_id: CheckResult(**dataclasses.asdict(row))
            for row in POLICY if row.milestone in self.selected
        }
        self.findings: list[Finding] = []
        self.commands: list[CommandRecord] = []
        self.command_outputs: dict[str, tuple[str, str]] = {}
        self.subject_repo: pathlib.Path | None = None
        self.subject_sha: str | None = None
        self.source_repo: pathlib.Path | None = None
        self.source_dirty: bool | None = None
        self.github_snapshot: dict[str, Any] | None = None
        self.github_envelope: dict[str, Any] | None = None
        self.github_auth_failures: list[str] = []
        self.github_auth_incomplete: list[str] = []
        self.runtime_evidence: Any = None
        self.trust_registry_path: pathlib.Path | None = None
        self.trust_registry_sha256: str | None = (
            args.trust_registry_sha256 or os.environ.get("TRIAD_RECEIPT_TRUST_REGISTRY_SHA256")
        )
        self.receipt_profile_decision_sha256: str | None = (
            getattr(args, "receipt_profile_decision_sha256", None)
            or os.environ.get("TRIAD_RECEIPT_PROFILE_DECISION_SHA256")
        )
        self.tool_error: str | None = None
        self.any_timeout = False
        self.redaction_hits: list[str] = []
        self.tempdir: tempfile.TemporaryDirectory[str] | None = None
        self.output_dir: pathlib.Path | None = None

    def add_finding(
        self, severity: str, milestone: str, check_id: str, title: str, detail: str,
        *, evidence_ids: Iterable[str] = (), remediation: str = ""
    ) -> None:
        stable = sha256_bytes(canonical_json_bytes({
            "severity": severity, "milestone": milestone, "check_id": check_id,
            "title": title, "detail": detail,
        }))[:12]
        self.findings.append(Finding(
            finding_id=f"F-{stable}", severity=severity, milestone=milestone,
            check_id=check_id, title=title, detail=detail,
            evidence_ids=list(evidence_ids), remediation=remediation))

    def fail_entry(self, milestone: str, detail: str, expected: str) -> None:
        check = self.results[f"{milestone}.ENTRY"]
        actual = f"{check.actual}; {detail}" if check.outcome == FAIL and check.actual else detail
        check.set_outcome(FAIL, actual=actual, expected=expected)

    def set_all_local(self, outcome: str, actual: str, evidence: Iterable[str] = ()) -> None:
        for milestone in self.selected:
            self.results[f"{milestone}.LOCAL_GATE"].set_outcome(
                outcome, actual=actual,
                expected="all independent static checks and mandatory local commands pass",
                evidence_ids=evidence,
                remediation="repair the named local failures and rerun from a clean exact head")

    def prepare_local(self) -> None:
        if not self.args.repo:
            raise ValueError("--repo is required in local/full mode")
        source = pathlib.Path(self.args.repo).expanduser().resolve()
        probe = run_git(source, "rev-parse", "--show-toplevel")
        if probe.returncode != 0:
            raise ValueError(f"--repo is not a Git repository: {probe.stderr.strip()}")
        source = pathlib.Path(probe.stdout.strip()).resolve()
        self.source_repo = source
        if self.args.mode == "full" and self.args.repo_full_name:
            remote = run_git(source, "config", "--get", "remote.origin.url")
            actual_repo = normalize_git_repository(remote.stdout.strip()) if remote.returncode == 0 else None
            if actual_repo != self.args.repo_full_name.lower():
                for milestone in self.selected:
                    self.fail_entry(
                        milestone,
                        f"local origin identity {actual_repo!r} != {self.args.repo_full_name.lower()!r}",
                        "local origin repository must match --repo-full-name exactly")
        status = run_git(source, "status", "--porcelain=v1", "--untracked-files=all")
        dirty = bool(status.stdout.strip())
        self.source_dirty = dirty
        head = run_git(source, "rev-parse", "HEAD")
        if head.returncode != 0 or not is_hex_sha(head.stdout.strip(), 40):
            raise RuntimeError("cannot resolve exact local HEAD")
        self.subject_sha = head.stdout.strip()
        if self.args.expected_head and self.subject_sha != self.args.expected_head:
            for milestone in self.selected:
                self.fail_entry(
                    milestone, f"local HEAD {self.subject_sha} != expected {self.args.expected_head}",
                    "exact expected head")
        if dirty:
            for milestone in self.selected:
                self.fail_entry(
                    milestone, "source checkout is dirty; uncommitted state is not auditable",
                    "clean exact-head checkout")
        self.tempdir = tempfile.TemporaryDirectory(prefix="triad-origin-audit-")
        clone = pathlib.Path(self.tempdir.name) / "subject"
        clone_result = subprocess.run(
            ["git", "clone", "--quiet", "--no-local", "--no-hardlinks", str(source), str(clone)],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120, check=False,
            env={"PATH": os.environ.get("PATH", ""), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC"})
        if clone_result.returncode != 0:
            raise RuntimeError(f"isolated local clone failed: {clone_result.stderr.strip()}")
        checkout = run_git(clone, "checkout", "--detach", self.subject_sha)
        if checkout.returncode != 0:
            raise RuntimeError(f"cannot checkout exact subject: {checkout.stderr.strip()}")
        self.subject_repo = clone
        if self.args.trust_registry:
            candidate = pathlib.Path(self.args.trust_registry).expanduser()
            self.trust_registry_path = candidate.resolve() if candidate.is_absolute() else (clone / candidate).resolve()
        else:
            self.trust_registry_path = clone / "evidence" / "trust" / "receipt_signers.v1.json"
        if not dirty:
            self.evaluate_entry_receipts()

    def evaluate_entry_receipts(self) -> None:
        assert self.subject_repo is not None
        for milestone in self.selected:
            check = self.results[f"{milestone}.ENTRY"]
            if check.outcome == FAIL:
                continue
            predecessor = PREDECESSOR[milestone]
            if predecessor is None:
                baseline_paths = [
                    self.subject_repo / "docs" / "control" / "rc3_effective_bundle_manifest.json",
                    self.subject_repo / "docs" / "control" / "rc4_control_bundle.json",
                ]
                missing = [str(path.relative_to(self.subject_repo)) for path in baseline_paths if not path.is_file()]
                if missing:
                    check.set_outcome(BLOCKED, actual="missing foundation: " + ", ".join(missing))
                else:
                    check.set_outcome(
                        PASS, actual="foundation control bundles present",
                        evidence_ids=[str(path.relative_to(self.subject_repo)) for path in baseline_paths])
                continue
            receipt = find_json_receipt(self.subject_repo, predecessor)
            if receipt is None:
                check.set_outcome(
                    BLOCKED, actual=f"no predecessor {predecessor} receipt found",
                    expected=f"authenticated {predecessor} receipt in exact ancestry")
                continue
            issues, event = receipt_issues(
                receipt, predecessor, self.started,
                repository_root=self.subject_repo,
                trust_registry_path=self.trust_registry_path,
                trust_registry_sha256=self.trust_registry_sha256,
                receipt_profile_decision_sha256=self.receipt_profile_decision_sha256,
            )
            receipt_predecessor = PREDECESSOR.get(predecessor)
            if receipt_predecessor is not None:
                predecessor_path = find_json_receipt(self.subject_repo, receipt_predecessor)
                if predecessor_path is None:
                    issues.append(
                        f"{predecessor} predecessor {receipt_predecessor} receipt preimage is unavailable")
                else:
                    try:
                        predecessor_event = strict_json_loads(predecessor_path.read_text(encoding="utf-8"))
                        predecessor_payload = predecessor_event.get("payload")
                    except (OSError, UnicodeDecodeError, json.JSONDecodeError, DuplicateJSONKey, RecursionError):
                        predecessor_payload = None
                    payload = event.get("payload") if isinstance(event, dict) else None
                    if not isinstance(payload, dict) or not isinstance(predecessor_payload, dict):
                        issues.append(f"{predecessor} predecessor receipt link cannot be decoded")
                    else:
                        if payload.get("predecessor_receipt_id") != predecessor_payload.get("receipt_id"):
                            issues.append(
                                f"{predecessor} predecessor_receipt_id does not match {receipt_predecessor}")
                        if payload.get("predecessor_receipt_sha256") != sha256_file(predecessor_path):
                            issues.append(
                                f"{predecessor} predecessor_receipt_sha256 does not match {receipt_predecessor} bytes")
            if issues:
                check.set_outcome(
                    FAIL, actual="; ".join(issues),
                    expected=f"valid authenticated {predecessor} receipt",
                    evidence_ids=[str(receipt.relative_to(self.subject_repo))])
            else:
                build_commit = (event or {}).get("payload", {}).get("build_commit")
                ancestry = run_git(self.subject_repo, "merge-base", "--is-ancestor", str(build_commit), str(self.subject_sha))
                if ancestry.returncode != 0:
                    check.set_outcome(FAIL, actual=f"{predecessor} receipt subject is not an ancestor")
                else:
                    check.set_outcome(
                        PASS, actual=f"authenticated {predecessor} receipt validated in ancestry",
                        evidence_ids=[str(receipt.relative_to(self.subject_repo))])

    def load_check_evidence(self) -> list[str]:
        assert self.subject_repo is not None and self.subject_sha is not None
        path = pathlib.Path(self.args.check_evidence) if self.args.check_evidence else pathlib.Path("evidence/audit/check_results.v1.json")
        if not path.is_absolute():
            path = self.subject_repo / path
        known_ids = {row.check_id for row in POLICY}
        rows, issues = validate_check_evidence_index(
            self.subject_repo, path, self.subject_sha, known_ids,
            now=self.started, trust_registry_path=self.trust_registry_path,
            trust_registry_sha256=self.trust_registry_sha256,
            receipt_profile_decision_sha256=self.receipt_profile_decision_sha256)
        for check_id, row in rows.items():
            if check_id not in self.results:
                continue
            if self.results[check_id].kind != "work_package":
                continue
            self.results[check_id].set_outcome(
                str(row["outcome"]), actual=str(row.get("actual", "verified committed evidence preimages")),
                expected=str(row.get("expected", "work-package acceptance evidence")),
                evidence_ids=row.get("verified_evidence", []),
                remediation=str(row.get("remediation", "")))
        return issues

    def run_local_commands(self) -> list[str]:
        assert self.subject_repo is not None and self.subject_sha is not None and self.tempdir is not None
        if not getattr(self.args, "allow_repo_code_execution", False):
            raise ValueError(
                "repository verification code execution was not explicitly authorized; "
                "pass --allow-repo-code-execution")
        issues: list[str] = []
        python = sys.executable
        for command_id, template, default_timeout in REQUIRED_LOCAL_COMMANDS:
            argv = [part.format(python=python) for part in template]
            command_repo = pathlib.Path(self.tempdir.name) / f"command-{command_id}"
            clone = subprocess.run(
                [
                    "git", "clone", "--quiet", "--no-checkout", "--no-local", "--no-hardlinks",
                    str(self.subject_repo), str(command_repo),
                ],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120, check=False,
                env={
                    "PATH": os.environ.get("PATH", ""), "LANG": "C.UTF-8",
                    "LC_ALL": "C.UTF-8", "TZ": "UTC",
                },
            )
            if clone.returncode != 0:
                issues.append(f"mandatory command {command_id} isolated clone failed: {clone.stderr.strip()}")
                continue
            checkout = run_git(command_repo, "checkout", "--detach", self.subject_sha, timeout=120)
            if checkout.returncode != 0:
                issues.append(
                    f"mandatory command {command_id} exact-head checkout failed: {checkout.stderr.strip()}")
                continue
            pre_head = run_git(command_repo, "rev-parse", "HEAD")
            pre_status = run_git(
                command_repo, "status", "--porcelain=v1", "--untracked-files=all", "--ignored=matching")
            if (
                pre_head.returncode != 0 or pre_head.stdout.strip() != self.subject_sha
                or pre_status.returncode != 0 or pre_status.stdout.strip()
            ):
                issues.append(f"mandatory command {command_id} isolated precondition is not clean exact head")
                continue
            if len(argv) > 1 and argv[1] not in {"-m", "-c"}:
                script_path = command_repo / argv[1]
                if not script_path.is_file():
                    issues.append(f"mandatory command {command_id} unavailable: {argv[1]}")
                    continue
            timeout = min(default_timeout, self.args.timeout) if self.args.timeout else default_timeout
            extra_env = {"PYTHONHASHSEED": "1" if command_id == "pytest_seed_1" else "0"}
            record, stdout, stderr = execute_bounded_command(
                command_id, argv, command_repo, timeout, self.args.max_log_bytes, extra_env)
            self.commands.append(record)
            self.command_outputs[command_id] = (stdout, stderr)
            if record.timed_out:
                self.any_timeout = True
                issues.append(f"mandatory command {command_id} timed out after {timeout}s")
            elif record.exit_code != 0:
                issues.append(f"mandatory command {command_id} exited {record.exit_code}")
            elif command_id == "verify_spec_control_counts":
                issues.extend(spec_control_count_output_issues(stdout))
            post_head = run_git(command_repo, "rev-parse", "HEAD")
            tracked_status = run_git(
                command_repo, "status", "--porcelain=v1", "--untracked-files=all", "--ignored=matching")
            if post_head.returncode != 0 or post_head.stdout.strip() != self.subject_sha:
                issues.append(f"mandatory command {command_id} changed exact HEAD")
            elif tracked_status.returncode != 0:
                issues.append(f"mandatory command {command_id} post-run tree state is unavailable")
            elif tracked_status.stdout.strip():
                issues.append(
                    f"mandatory command {command_id} mutated its isolated exact-head clone: "
                    f"{tracked_status.stdout.strip()[:500]}")
        return issues

    def evaluate_local(self) -> None:
        assert self.subject_repo is not None
        work_order_issues = validate_policy_document_sync(pathlib.Path(__file__).resolve().parent)
        static_issues, _secret_hits = independent_static_issues(self.subject_repo)
        evidence_issues = self.load_check_evidence()
        command_issues = self.run_local_commands()
        evidence_failures = [
            issue for issue in evidence_issues
            if not issue.startswith("check evidence index unavailable at ")
        ]
        hard_issues = work_order_issues + static_issues + evidence_failures + command_issues
        if hard_issues:
            self.set_all_local(FAIL, "; ".join(hard_issues), ["local-static", "local-commands"])
            for issue in hard_issues:
                self.add_finding(
                    "P1", "GLOBAL", "GLOBAL.LOCAL", "Independent local gate failure", issue,
                    evidence_ids=["local-static"], remediation="repair and rerun exact-head local audit")
        else:
            self.set_all_local(PASS, "independent static checks and every mandatory local command passed",
                               ["local-static", "local-commands"])
        for issue in evidence_issues:
            unavailable = issue.startswith("check evidence index unavailable at ")
            self.add_finding(
                "P2" if unavailable else "P1", "GLOBAL", "GLOBAL.EVIDENCE_INDEX",
                "Check evidence index unavailable" if unavailable else "Check evidence index failed closed",
                issue, remediation="publish authenticated exact-head work-package preimages and rerun")

    def load_github(self) -> None:
        if self.args.github_snapshot:
            raw_path = pathlib.Path(self.args.github_snapshot).expanduser()
            if raw_path.is_symlink():
                raise ValueError("offline GitHub snapshot may not be a symbolic link")
            path = raw_path.resolve()
            if path.stat().st_size > 64_000_000:
                raise ValueError("offline GitHub snapshot must be a regular file no larger than 64 MB")
            data = strict_json_loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("offline GitHub snapshot root must be an object")
            if self.trust_registry_path is None and self.args.trust_registry:
                registry_candidate = pathlib.Path(self.args.trust_registry).expanduser()
                self.trust_registry_path = registry_candidate.resolve()
            if data.get("schema") == GITHUB_SNAPSHOT_ENVELOPE_SCHEMA:
                self.github_envelope = data
                auth_issues, payload = verify_offline_github_envelope(
                    data, trust_registry_path=self.trust_registry_path,
                    trust_registry_sha256=self.trust_registry_sha256,
                    selected=self.selected, now=self.started)
                if auth_issues:
                    if any("no independently pinned trust registry" in issue for issue in auth_issues):
                        self.github_auth_incomplete.extend(auth_issues)
                    else:
                        self.github_auth_failures.extend(auth_issues)
                if payload is None:
                    raise ValueError("offline GitHub envelope has no usable normalized payload")
                data = payload
            elif data.get("schema") == GITHUB_SNAPSHOT_SCHEMA:
                self.github_auth_incomplete.append(
                    "offline GitHub snapshot is unsigned; a pinned two-signature DSSE envelope is required")
            else:
                raise ValueError(
                    f"offline GitHub snapshot schema must be {GITHUB_SNAPSHOT_SCHEMA} or "
                    f"{GITHUB_SNAPSHOT_ENVELOPE_SCHEMA}")
            if self.args.repo_full_name and str(data.get("repository", "")).lower() != self.args.repo_full_name.lower():
                raise ValueError("offline GitHub snapshot repository does not match --repo-full-name")
            structure_issues = github_snapshot_structure_issues(data, self.selected)
            if structure_issues:
                raise ValueError("offline GitHub snapshot structure failed: " + "; ".join(structure_issues))
            if self.args.pr is not None:
                subject_pr = data.get("subject_pr")
                subject_number = subject_pr.get("number") if isinstance(subject_pr, dict) else None
                if subject_number != self.args.pr:
                    raise ValueError(
                        f"offline GitHub snapshot subject PR {subject_number!r} does not match --pr {self.args.pr}")
            self.github_snapshot = data
            return
        if not self.args.repo_full_name:
            raise ValueError("github/full mode requires --repo-full-name, or --github-snapshot")
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        client = GitHubClient(token)
        self.github_snapshot = collect_github_snapshot(
            client, self.args.repo_full_name, self.args.pr, self.selected,
            parse_pr_selections(self.args.source_pr), parse_pr_selections(self.args.receipt_pr))
        structure_issues = github_snapshot_structure_issues(self.github_snapshot, self.selected)
        if structure_issues:
            raise GitHubError("live GitHub normalization failed: " + "; ".join(structure_issues))

    def evaluate_github(self) -> None:
        assert self.github_snapshot is not None
        milestone_map = self.github_snapshot.get("milestones")
        identity_failures: list[str] = []
        if self.args.mode == "full":
            local_sha = self.subject_sha
            if self.args.pr is not None:
                subject_pr = self.github_snapshot.get("subject_pr")
                head = subject_pr.get("head") if isinstance(subject_pr, dict) else None
                github_subject_sha = head.get("sha") if isinstance(head, dict) else None
                identity_label = f"explicit PR #{self.args.pr} head"
            else:
                github_subject_sha = self.github_snapshot.get("default_branch_head_sha")
                identity_label = "default-branch head"
            if not is_hex_sha(github_subject_sha, 40):
                identity_failures.append(f"authenticated GitHub {identity_label} identity is unavailable")
            elif github_subject_sha != local_sha or github_subject_sha != self.args.expected_head:
                identity_failures.append(
                    f"local/expected exact head {local_sha!r}/{self.args.expected_head!r} "
                    f"does not equal GitHub {identity_label} {github_subject_sha!r}")
        for item in self.selected:
            local_payload: Mapping[str, Any] | None = None
            if self.subject_repo:
                if item == "B10" and self.args.terminal_receipt:
                    receipt_path = pathlib.Path(self.args.terminal_receipt).expanduser().resolve()
                else:
                    receipt_path = find_json_receipt(self.subject_repo, item)
                if receipt_path:
                    try:
                        receipt_event = strict_json_loads(receipt_path.read_text(encoding="utf-8"))
                        payload_candidate = receipt_event.get("payload")
                        local_payload = payload_candidate if isinstance(payload_candidate, dict) else None
                    except (OSError, UnicodeDecodeError, json.JSONDecodeError, DuplicateJSONKey, RecursionError):
                        local_payload = None
            expected_for_item: str | None = None
            if self.subject_repo is None and self.args.expected_head:
                subject_pr = self.github_snapshot.get("subject_pr")
                subject_number = subject_pr.get("number") if isinstance(subject_pr, dict) else None
                fact_for_subject = milestone_map.get(item) if isinstance(milestone_map, dict) else None
                numbers: set[Any] = set()
                if isinstance(fact_for_subject, dict):
                    for kind in ("source", "receipt"):
                        bundle = fact_for_subject.get(kind)
                        pr_row = bundle.get("pr") if isinstance(bundle, dict) else None
                        if isinstance(pr_row, dict):
                            numbers.add(pr_row.get("number"))
                if len(self.selected) == 1 or (subject_number is not None and subject_number in numbers):
                    expected_for_item = self.args.expected_head
            failures, incomplete = github_milestone_gate_issues(
                self.github_snapshot,
                item,
                expected_subject_sha=expected_for_item,
                local_receipt_payload=local_payload,
                now=self.started,
            )
            failures = identity_failures + list(self.github_auth_failures) + failures
            incomplete = list(self.github_auth_incomplete) + incomplete
            fact = milestone_map.get(item) if isinstance(milestone_map, dict) else None
            if isinstance(fact, dict):
                for kind in ("source", "receipt"):
                    bundle = fact.get(kind)
                    if isinstance(bundle, dict) and bundle.get("workflow_sha256") != self.args.workflow_sha256:
                        failures.append(
                            f"{item} {kind} CI workflow bytes do not match the external SHA-256 pin")
            predecessor_failures, predecessor_incomplete = github_predecessor_chronology_issues(
                self.github_snapshot, item)
            failures.extend(predecessor_failures)
            incomplete.extend(predecessor_incomplete)
            if self.subject_repo and isinstance(fact, dict) and isinstance(fact.get("source"), dict):
                source_pr = fact["source"].get("pr", {})
                source_merge = source_pr.get("merge_commit_sha") if isinstance(source_pr, dict) else None
                if is_hex_sha(source_merge, 40):
                    ancestry = run_git(self.subject_repo, "merge-base", "--is-ancestor", source_merge, str(self.subject_sha))
                    if ancestry.returncode != 0:
                        failures.append(f"{item} source merge is not in local exact-head ancestry")
                else:
                    incomplete.append(f"{item} source merge SHA unavailable for local ancestry proof")
            check = self.results[f"{item}.GITHUB_GATE"]
            if failures:
                check.set_outcome(
                    FAIL, actual="; ".join(list(dict.fromkeys(failures + incomplete))),
                    expected="source+receipt PR chronology, final-code review, exact-head CI, ancestry, and governance",
                    evidence_ids=["github-snapshot"])
            elif incomplete:
                check.set_outcome(
                    UNAVAILABLE, actual="; ".join(list(dict.fromkeys(incomplete))),
                    expected="complete normalized source+detached-receipt and governance evidence",
                    evidence_ids=["github-snapshot"])
            else:
                check.set_outcome(PASS, actual="GitHub source+receipt chronology/ancestry/review/CI/governance passed",
                                  evidence_ids=["github-snapshot"])
            for issue in failures:
                self.add_finding(
                    "P1", item, f"{item}.GITHUB_GATE", "GitHub gate failure", issue,
                    evidence_ids=["github-snapshot"],
                    remediation="repair source/receipt chronology, exact-head review/CI, ancestry, or governance")
            for issue in incomplete:
                self.add_finding(
                    "P2", item, f"{item}.GITHUB_GATE", "GitHub evidence unavailable", issue,
                    evidence_ids=["github-snapshot"],
                    remediation="provide normalized immutable GitHub/audit-log evidence")

    def evaluate_receipts(self) -> None:
        if self.subject_repo is None:
            for milestone in self.selected:
                self.results[f"{milestone}.RECEIPT"].set_outcome(
                    NOT_RUN, actual="receipt bytes unavailable in GitHub-only mode",
                    expected="local or normalized receipt preimages")
            return
        for milestone in self.selected:
            terminal_root: pathlib.Path | None = None
            if milestone == "B10" and self.args.terminal_receipt:
                path = pathlib.Path(self.args.terminal_receipt).expanduser().resolve()
                terminal_root = pathlib.Path(
                    self.args.terminal_evidence_root or path.parent).expanduser().resolve()
            else:
                path = find_json_receipt(self.subject_repo, milestone)
            check = self.results[f"{milestone}.RECEIPT"]
            if path is None or not path.is_file():
                check.set_outcome(BLOCKED, actual=f"no {milestone} receipt found")
                continue
            issues, event = receipt_issues(
                path, milestone, self.started,
                repository_root=terminal_root or self.subject_repo,
                trust_registry_path=self.trust_registry_path,
                trust_registry_sha256=self.trust_registry_sha256,
                receipt_profile_decision_sha256=self.receipt_profile_decision_sha256,
            )
            predecessor = PREDECESSOR.get(milestone)
            if predecessor is not None:
                predecessor_path = find_json_receipt(self.subject_repo, predecessor)
                payload = event.get("payload") if isinstance(event, dict) else None
                if predecessor_path is None:
                    issues.append(f"{milestone} predecessor {predecessor} receipt preimage is unavailable")
                else:
                    try:
                        predecessor_event = strict_json_loads(predecessor_path.read_text(encoding="utf-8"))
                        predecessor_payload = predecessor_event.get("payload")
                    except (OSError, UnicodeDecodeError, json.JSONDecodeError, DuplicateJSONKey, RecursionError):
                        predecessor_payload = None
                    if not isinstance(payload, dict) or not isinstance(predecessor_payload, dict):
                        issues.append(f"{milestone} predecessor receipt link cannot be decoded")
                    else:
                        if payload.get("predecessor_receipt_id") != predecessor_payload.get("receipt_id"):
                            issues.append(f"{milestone} predecessor_receipt_id does not match {predecessor}")
                        if payload.get("predecessor_receipt_sha256") != sha256_file(predecessor_path):
                            issues.append(f"{milestone} predecessor_receipt_sha256 does not match {predecessor} bytes")
            try:
                evidence_id = str(path.relative_to(self.subject_repo))
            except ValueError:
                evidence_id = f"external://{path.name}"
            if milestone == "B10" and self.args.terminal_receipt:
                commit = self.args.terminal_receipt_commit
                git_path = self.args.terminal_receipt_git_path
                tag = self.args.terminal_tag
                if not is_hex_sha(commit, 40) or not isinstance(git_path, str) or not git_path or not tag:
                    issues.append("B10 detached receipt requires commit, git path, and signed tag inputs")
                else:
                    parent = run_git(self.subject_repo, "rev-parse", f"{commit}^")
                    if parent.returncode != 0 or parent.stdout.strip() != self.subject_sha:
                        issues.append("B10 terminal receipt commit is not the direct child of audited source merge")
                    blob = run_git(self.subject_repo, "show", f"{commit}:{git_path}")
                    if blob.returncode != 0 or blob.stdout.encode("utf-8") != path.read_bytes():
                        issues.append("B10 terminal receipt bytes do not equal the named Git commit blob")
                    tag_target = run_git(self.subject_repo, "rev-list", "-n", "1", tag)
                    if tag_target.returncode != 0 or tag_target.stdout.strip() != commit:
                        issues.append("B10 terminal signed tag does not target the receipt commit")
                    tag_verify = run_git(self.subject_repo, "verify-tag", tag)
                    if tag_verify.returncode != 0:
                        issues.append("B10 terminal tag signature did not verify in the configured trust context")
            if issues:
                check.set_outcome(
                    FAIL, actual="; ".join(issues),
                    expected="post-merge current-time receipt with real preimages and independent authentication",
                    evidence_ids=[evidence_id])
                for issue in issues:
                    self.add_finding(
                        "P1", milestone, check.check_id, "Receipt trust failure", issue,
                        evidence_ids=[evidence_id], remediation="replace with a truthful authenticated receipt")
            else:
                build_commit = event.get("payload", {}).get("build_commit")
                ancestry = run_git(self.subject_repo, "merge-base", "--is-ancestor", str(build_commit), str(self.subject_sha))
                if ancestry.returncode != 0:
                    check.set_outcome(FAIL, actual="receipt subject is not in exact-head ancestry", evidence_ids=[evidence_id])
                else:
                    check.set_outcome(PASS, actual="receipt bytes, chronology fields, preimages, and auth evidence passed",
                                      evidence_ids=[evidence_id])

    def load_runtime_evidence(self) -> None:
        if not self.args.runtime_evidence:
            return
        raw_path = pathlib.Path(self.args.runtime_evidence).expanduser()
        if raw_path.is_symlink():
            raise ValueError("runtime evidence may not be a symbolic link")
        path = raw_path.resolve()
        if path.stat().st_size > 64_000_000:
            raise ValueError("runtime evidence must be a regular file no larger than 64 MB")
        value = strict_json_loads(path.read_text(encoding="utf-8"))
        cleaned, hits = redact_value(value)
        self.redaction_hits.extend(hits)
        self.runtime_evidence = {
            "source_path": str(path), "sha256": sha256_file(path), "sanitized": cleaned,
            "scope_note": "external runtime evidence; never promotes a Track-A repository check",
        }

    def propagate_dependency_blocks(self) -> None:
        """Block descendant entry gates without erasing diagnostic implementation evidence."""
        selected = set(self.selected)
        for milestone in self.selected:
            predecessor = PREDECESSOR[milestone]
            if predecessor not in selected:
                continue
            predecessor_rows = [row for row in self.results.values() if row.milestone == predecessor]
            blockers = [row.check_id for row in predecessor_rows if row.hard_gate and row.outcome != PASS]
            if not blockers:
                continue
            entry = self.results[f"{milestone}.ENTRY"]
            if entry.outcome != FAIL:
                entry.set_outcome(
                    BLOCKED,
                    actual=f"dependency-blocked by {predecessor}: {', '.join(blockers)}",
                    expected=f"every hard {predecessor} gate passes before {milestone} acceptance",
                    evidence_ids=entry.evidence_ids,
                    remediation=f"close {predecessor} hard gates and rerun before accepting {milestone}",
                )

    def score(self) -> dict[str, Any]:
        milestones: list[dict[str, Any]] = []
        any_fail = False
        any_incomplete = False
        profile_authority_missing = not is_nonzero_sha256(self.receipt_profile_decision_sha256)
        for milestone in self.selected:
            rows = [row for row in self.results.values() if row.milestone == milestone]
            total = sum(row.weight for row in rows)
            points = sum(row.points for row in rows)
            assessed = sum(row.weight for row in rows if row.outcome not in {NOT_RUN, UNAVAILABLE, BLOCKED})
            hard_fail = any(row.hard_gate and row.outcome == FAIL for row in rows)
            hard_incomplete = (
                any(row.hard_gate and row.outcome in INCOMPLETE_OUTCOMES for row in rows)
                or profile_authority_missing
            )
            any_fail = any_fail or hard_fail
            any_incomplete = any_incomplete or hard_incomplete
            if hard_fail:
                status = "HARD_GATE_FAIL"
            elif hard_incomplete:
                status = "BLOCKED_INCOMPLETE"
            else:
                status = "PASS_REPOSITORY_SAFE_HOLD"
            milestones.append({
                "milestone": milestone,
                "status": status,
                "hard_gate_result": FAIL if hard_fail else (BLOCKED if hard_incomplete else PASS),
                "completion_score": round(100 * points / total, 2) if total else 0.0,
                "evidence_coverage": round(100 * assessed / total, 2) if total else 0.0,
                "earned_points": round(points, 2),
                "total_points": total,
            })
        program_score = round(sum(row["completion_score"] for row in milestones) / len(milestones), 2)
        coverage = round(sum(row["evidence_coverage"] for row in milestones) / len(milestones), 2)
        if any_fail:
            overall = "HARD_GATE_FAIL"
            hard = FAIL
        elif any_incomplete:
            overall = "BLOCKED_INCOMPLETE"
            hard = BLOCKED
        else:
            overall = SUCCESS_STATUS
            hard = PASS
        if self.tool_error:
            overall = "RUNNER_ERROR"
            hard = BLOCKED
        return {
            "status": overall,
            "hard_gate_result": hard,
            "repository_safe_hold_eligible": hard == PASS,
            "receipt_profile_decision_pin_valid": not profile_authority_missing,
            "estate_certification_eligible": False,
            "activation_result": ACTIVATION_RESULT,
            "program_completion_score": program_score,
            "evidence_coverage": coverage,
            "milestones": milestones,
        }

    def determine_exit(self, score: Mapping[str, Any]) -> int:
        if self.tool_error:
            return EXIT_INTERNAL
        if self.any_timeout:
            return EXIT_TIMEOUT
        if score["hard_gate_result"] == FAIL:
            return EXIT_HARD_FAIL
        if score["hard_gate_result"] == BLOCKED:
            return EXIT_INCOMPLETE
        return EXIT_PASS

    def execute(self) -> int:
        try:
            if self.args.mode in {"local", "full"}:
                self.prepare_local()
                self.evaluate_local()
            if self.args.mode in {"github", "full"}:
                self.load_github()
                self.evaluate_github()
            self.evaluate_receipts()
            self.load_runtime_evidence()
        except (ValueError, OSError, json.JSONDecodeError, TypeError, KeyError, AttributeError, RecursionError) as exc:
            self.tool_error = f"invalid input/evidence: {exc}"
        except (RuntimeError, GitHubError, subprocess.SubprocessError) as exc:
            self.tool_error = str(exc)
        except Exception as exc:  # fail closed with exit 4; never leak a traceback as a false PASS
            self.tool_error = f"unexpected runner error ({type(exc).__name__}): {exc}"
        self.propagate_dependency_blocks()
        score = self.score()
        exit_code = self.determine_exit(score)
        try:
            self.write_reports(score, exit_code)
        except Exception as exc:  # last-resort: report generation itself must not false-pass
            self.tool_error = f"report generation failed: {exc}"
            safe_error, _ = redact_text(self.tool_error)
            print(safe_error, file=sys.stderr)
            return EXIT_INTERNAL
        return exit_code

    def choose_output_dir(self) -> pathlib.Path:
        if self.args.output:
            base = pathlib.Path(self.args.output).expanduser().resolve()
        elif self.source_repo:
            base = self.source_repo.parent / "triad_origin_audit_runs" / self.run_id
        else:
            base = pathlib.Path.cwd() / "triad_origin_audit_runs" / self.run_id
        if self.source_repo and (base == self.source_repo or self.source_repo in base.parents):
            raise ValueError("audit output must be outside the audited repository")
        if base.exists() and any(base.iterdir() if base.is_dir() else [base]):
            raise FileExistsError(f"refuse to overwrite non-empty output path {base}")
        base.mkdir(parents=True, exist_ok=True)
        self.output_dir = base
        return base

    def write_input_preimages(self, output: pathlib.Path) -> None:
        """Bundle the exact local bytes used for receipt/work-package decisions.

        Reports must not point only into the temporary clone that cleanup deletes.  Inputs are
        copied by content digest, with a narrow source/check map.  A credential-like preimage makes
        report generation fail rather than leaking it into the handoff archive.
        """
        candidates: dict[pathlib.Path, dict[str, Any]] = {}

        def add_candidate(path: pathlib.Path | None, kind: str, check_ids: Iterable[str]) -> None:
            if path is None or not path.is_file() or path.is_symlink():
                return
            resolved = path.resolve()
            row = candidates.setdefault(resolved, {"source_kind": kind, "check_ids": set()})
            row["check_ids"].update(check_ids)

        add_candidate(self.trust_registry_path, "PINNED_TRUST_REGISTRY", sorted(self.results))
        if getattr(self.args, "terminal_receipt", None):
            terminal_path = pathlib.Path(self.args.terminal_receipt).expanduser().resolve()
            terminal_root = pathlib.Path(
                getattr(self.args, "terminal_evidence_root", None) or terminal_path.parent).expanduser().resolve()
            add_candidate(terminal_path, "TERMINAL_RECEIPT", ["B10.RECEIPT"])
            if terminal_path.is_file():
                with contextlib.suppress(OSError, json.JSONDecodeError, DuplicateJSONKey):
                    event = strict_json_loads(terminal_path.read_text(encoding="utf-8"))
                    payload = event.get("payload") if isinstance(event, dict) else None
                    for evidence in payload.get("evidence", []) if isinstance(payload, dict) else []:
                        if isinstance(evidence, dict) and isinstance(evidence.get("path"), str):
                            add_candidate(
                                terminal_root / evidence["path"], "TERMINAL_RECEIPT_PREIMAGE", ["B10.RECEIPT"])
        if self.subject_repo is not None:
            index_path = pathlib.Path(self.args.check_evidence) if self.args.check_evidence else pathlib.Path(
                "evidence/audit/check_results.v1.json")
            if not index_path.is_absolute():
                index_path = self.subject_repo / index_path
            add_candidate(index_path, "CHECK_EVIDENCE_INDEX", sorted(self.results))
            if index_path.is_file():
                with contextlib.suppress(OSError, json.JSONDecodeError, DuplicateJSONKey):
                    index = strict_json_loads(index_path.read_text(encoding="utf-8"))
                    for check in index.get("checks", []) if isinstance(index, dict) else []:
                        if not isinstance(check, dict):
                            continue
                        check_id = str(check.get("check_id", ""))
                        for evidence in check.get("evidence", []) if isinstance(check.get("evidence"), list) else []:
                            if isinstance(evidence, dict) and isinstance(evidence.get("path"), str):
                                add_candidate(
                                    self.subject_repo / evidence["path"], "WORK_PACKAGE_PREIMAGE", [check_id])
            receipt_milestones = set(self.selected)
            receipt_milestones.update(
                predecessor for item in self.selected
                if (predecessor := PREDECESSOR.get(item)) is not None)
            for milestone in sorted(receipt_milestones):
                receipt_path = find_json_receipt(self.subject_repo, milestone)
                add_candidate(receipt_path, "MILESTONE_RECEIPT", [f"{milestone}.RECEIPT"])
                if receipt_path is None:
                    continue
                with contextlib.suppress(OSError, json.JSONDecodeError, DuplicateJSONKey):
                    event = strict_json_loads(receipt_path.read_text(encoding="utf-8"))
                    payload = event.get("payload") if isinstance(event, dict) else None
                    for evidence in payload.get("evidence", []) if isinstance(payload, dict) else []:
                        if isinstance(evidence, dict) and isinstance(evidence.get("path"), str):
                            add_candidate(
                                self.subject_repo / evidence["path"], "RECEIPT_PREIMAGE",
                                [f"{milestone}.RECEIPT"])

        target_root = output / "inputs" / "sha256"
        target_root.mkdir(parents=True, exist_ok=True)
        mapping: list[dict[str, Any]] = []
        for source, metadata in sorted(candidates.items(), key=lambda item: str(item[0])):
            raw = source.read_bytes()
            decoded = raw.decode("utf-8", errors="replace")
            secret_names = [name for name, pattern in SECRET_PATTERNS if pattern.search(decoded)]
            if secret_names:
                raise RuntimeError(
                    f"refuse to bundle credential-like input preimage {source.name}: {sorted(set(secret_names))}")
            digest = sha256_bytes(raw)
            target = target_root / digest
            if not target.exists():
                target.write_bytes(raw)
            if self.subject_repo is not None:
                try:
                    source_label = str(source.relative_to(self.subject_repo.resolve()))
                except ValueError:
                    source_label = f"external://{source.name}"
            else:
                source_label = f"external://{source.name}"
            mapping.append({
                "source": source_label,
                "bundled_path": str(target.relative_to(output)),
                "sha256": digest,
                "bytes": len(raw),
                "source_kind": metadata["source_kind"],
                "check_ids": sorted(metadata["check_ids"]),
            })
        write_json(output / "input_preimages.json", {
            "schema": "triad.origin.audit_input_preimages.v1",
            "subject_sha": self.subject_sha or self.args.expected_head,
            "entries": mapping,
        })

    def write_reports(self, score: Mapping[str, Any], exit_code: int) -> None:
        output = self.choose_output_dir()
        self.write_input_preimages(output)
        logs = output / "logs"
        logs.mkdir()
        command_rows: list[dict[str, Any]] = []
        for record in self.commands:
            self.redaction_hits.extend(record.redaction_hits)
            stdout, stderr = self.command_outputs.get(record.command_id, ("", ""))
            stdout_path = logs / f"{record.command_id}.stdout.txt"
            stderr_path = logs / f"{record.command_id}.stderr.txt"
            stdout_path.write_text(stdout, encoding="utf-8")
            stderr_path.write_text(stderr, encoding="utf-8")
            record.stdout_path = str(stdout_path.relative_to(output))
            record.stderr_path = str(stderr_path.relative_to(output))
            record.stdout_sha256 = sha256_file(stdout_path)
            record.stderr_sha256 = sha256_file(stderr_path)
            command_rows.append(dataclasses.asdict(record))

        completed = utc_now()
        cleaned_github = None
        if self.github_snapshot is not None:
            github_report_value: Any = {
                "normalized": self.github_snapshot,
                "offline_envelope": self.github_envelope,
                "authentication_failures": self.github_auth_failures,
                "authentication_incomplete": self.github_auth_incomplete,
            }
            cleaned_github, hits = redact_value(github_report_value)
            self.redaction_hits.extend(hits)
        cleaned_runtime = None
        if self.runtime_evidence is not None:
            cleaned_runtime, hits = redact_value(self.runtime_evidence)
            self.redaction_hits.extend(hits)
        report = {
            "schema": REPORT_SCHEMA,
            "tool": {"name": TOOL_NAME, "version": TOOL_VERSION, "self_sha256": sha256_file(pathlib.Path(__file__))},
            "toolchain": toolchain_versions(),
            "policy": {"version": "1", "sha256": POLICY_SHA256, "check_count": len(POLICY)},
            "external_pins": {
                "receipt_trust_registry_sha256": self.trust_registry_sha256,
                "receipt_profile_decision_sha256": self.receipt_profile_decision_sha256,
                "github_workflow_sha256": getattr(self.args, "workflow_sha256", None),
                "source_pr_selections": parse_pr_selections(getattr(self.args, "source_pr", [])),
                "receipt_pr_selections": parse_pr_selections(getattr(self.args, "receipt_pr", [])),
            },
            "run": {
                "run_id": self.run_id, "mode": self.args.mode,
                "started_at": iso_z(self.started), "completed_at": iso_z(completed),
                "exit_code": exit_code, "tool_error": self.tool_error,
                "repo_code_execution_authorized": bool(
                    getattr(self.args, "allow_repo_code_execution", False)),
            },
            "subject": {
                "local_source": str(self.source_repo) if self.source_repo else None,
                "repository_full_name": self.args.repo_full_name,
                "pr_number": self.args.pr,
                "head_sha": self.subject_sha or self.args.expected_head,
                "source_checkout_dirty": self.source_dirty,
            },
            "overall": score,
            "checks": [dataclasses.asdict(self.results[key]) for key in sorted(self.results)],
            "findings": [dataclasses.asdict(row) for row in self.findings],
            "commands": command_rows,
            "runtime_evidence": cleaned_runtime,
            "github_evidence_sha256": sha256_bytes(canonical_json_bytes({
                "normalized": self.github_snapshot, "offline_envelope": self.github_envelope,
            })) if self.github_snapshot else None,
            "redaction_hits": sorted(set(self.redaction_hits)),
            "claim_boundary": (
                "Repository audit only. This report cannot authorize PAPER, TESTNET, LIVE, venue access, "
                "money authority, estate certification, or profitability."
            ),
        }
        cleaned_report, report_hits = redact_value(report)
        self.redaction_hits.extend(report_hits)
        cleaned_report["redaction_hits"] = sorted(set(self.redaction_hits))
        write_json(output / "report.json", cleaned_report)
        if cleaned_github is not None:
            write_json(output / "github_evidence.json", cleaned_github)
        if cleaned_runtime is not None:
            write_json(output / "runtime_evidence_sanitized.json", cleaned_runtime)

        self.write_summary(output / "SUMMARY.md", score, exit_code)
        self.write_detailed(output / "DETAILED_REPORT.md", score)
        self.write_html(output / "DETAILED_REPORT.html", score, exit_code)
        self.write_scorecard(output / "scorecard.csv")
        self.write_findings(output / "findings.csv")
        self.write_command_log(output / "command_log.ndjson", command_rows)
        self.write_junit(output / "junit.xml")
        cleaned_report["redaction_hits"] = sorted(set(self.redaction_hits))
        write_json(output / "report.json", cleaned_report)

        leakage = report_secret_issues(output)
        if leakage:
            raise RuntimeError("post-redaction credential leakage check failed: " + "; ".join(leakage))

        pre_manifest = sorted(path for path in output.rglob("*") if path.is_file())
        manifest_rows = []
        for path in pre_manifest:
            relative = str(path.relative_to(output))
            if relative.startswith("logs/"):
                source_kind = "COMMAND_OUTPUT"
                check_ids = [f"{item}.LOCAL_GATE" for item in self.selected]
                source_uri = f"command://{path.stem.rsplit('.', 2)[0]}"
            elif relative == "command_log.ndjson":
                source_kind = "COMMAND_METADATA"
                check_ids = [f"{item}.LOCAL_GATE" for item in self.selected]
                source_uri = f"audit://{self.run_id}/commands"
            elif relative == "github_evidence.json":
                source_kind = "GITHUB_NORMALIZED_EVIDENCE"
                check_ids = [f"{item}.GITHUB_GATE" for item in self.selected]
                source_uri = f"github://{self.args.repo_full_name or self.github_snapshot.get('repository', 'unknown')}"
            elif relative == "runtime_evidence_sanitized.json":
                source_kind = "EXTERNAL_RUNTIME_EVIDENCE"
                check_ids = []
                source_uri = "runtime-evidence://sanitized-import"
            elif relative == "findings.csv":
                source_kind = "DERIVED_FINDING_REPORT"
                check_ids = sorted({row.check_id for row in self.findings})
                source_uri = f"audit://{self.run_id}/findings"
            else:
                source_kind = "DERIVED_REPORT"
                check_ids = sorted(self.results)
                source_uri = f"audit://{self.run_id}/{relative}"
            manifest_rows.append({
                "artifact_id": sha256_bytes(relative.encode())[:16],
                "path": relative,
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
                "media_type": media_type(path),
                "source_kind": source_kind,
                "source_uri": source_uri,
                "check_ids": check_ids,
                "captured_at": iso_z(completed),
                "subject_sha": self.subject_sha or self.args.expected_head,
                "redaction": "APPLIED" if self.redaction_hits else "SCANNED_NO_HITS",
            })
        evidence_manifest = {
            "schema": EVIDENCE_SCHEMA,
            "run_id": self.run_id,
            "subject_sha": self.subject_sha or self.args.expected_head,
            "unsigned": True,
            "authentication_note": "SHA-256 integrity is not authorization; sign this bundle externally.",
            "coverage": {
                "included": "every report/evidence/log byte created before this manifest",
                "excluded_self_referential": ["evidence_manifest.json", "SHA256SUMS", f"{self.run_id}.zip"],
            },
            "verification": {"performed": True, "result": PASS},
            "artifacts": manifest_rows,
        }
        write_json(output / "evidence_manifest.json", evidence_manifest)
        manifest_verify_issues = verify_evidence_manifest(output, output / "evidence_manifest.json")
        if manifest_verify_issues:
            raise RuntimeError("generated evidence manifest failed verification: " + "; ".join(manifest_verify_issues))
        checksum_paths = sorted(path for path in output.rglob("*") if path.is_file())
        (output / "SHA256SUMS").write_text(
            "".join(f"{sha256_file(path)}  {path.relative_to(output)}\n" for path in checksum_paths),
            encoding="utf-8")
        zip_path = output / f"{self.run_id}.zip"
        deterministic_zip(output, zip_path)
        print(f"Audit status: {score['status']}")
        print(f"Hard gate: {score['hard_gate_result']}")
        print(f"Completion score: {score['program_completion_score']:.2f}/100")
        print(f"Evidence coverage: {score['evidence_coverage']:.2f}%")
        print(f"Reports: {output}")

    def write_summary(self, path: pathlib.Path, score: Mapping[str, Any], exit_code: int) -> None:
        lines = [
            "# TRIAD ORIGIN B01–B10 Audit Summary", "",
            f"- Status: `{score['status']}`",
            f"- Hard gate: `{score['hard_gate_result']}`",
            f"- Run ID: `{self.run_id}`",
            f"- Subject SHA: `{self.subject_sha or self.args.expected_head or 'UNAVAILABLE'}`",
            f"- Source checkout dirty: `{self.source_dirty if self.source_dirty is not None else 'NOT_APPLICABLE'}`",
            f"- Activation result: `{ACTIVATION_RESULT}`",
            f"- Completion score: `{score['program_completion_score']:.2f}/100`",
            f"- Evidence coverage: `{score['evidence_coverage']:.2f}%`",
            f"- Exit code: `{exit_code}`", "",
            "> A numeric score never overrides a failed, blocked, unavailable, or unmeasured hard gate. "
            "This is repository evidence only and cannot authorize PAPER, TESTNET, LIVE, venue access, "
            "money authority, or profitability.", "", "## Milestones", "",
            "| Milestone | Hard gate | Status | Score | Coverage |", "|---|---|---|---:|---:|",
        ]
        for row in score["milestones"]:
            lines.append(
                f"| {row['milestone']} | {row['hard_gate_result']} | {row['status']} | "
                f"{row['completion_score']:.2f} | {row['evidence_coverage']:.2f}% |")
        blockers = [row for row in self.results.values() if row.hard_gate and row.outcome != PASS]
        profile_pin_missing = not is_nonzero_sha256(self.receipt_profile_decision_sha256)
        lines.extend(["", "## Hard blockers", ""])
        if blockers:
            for row in sorted(blockers, key=lambda item: item.check_id):
                lines.append(f"- `{row.check_id}` — **{row.outcome}**: {row.actual or 'no evidence'}")
        if profile_pin_missing:
            lines.append(
                "- `GLOBAL.RECEIPT_PROFILE_DECISION_PIN` — **BLOCKED**: external ratified "
                "DECISION-RECEIPT-PROFILE-001 SHA-256 pin is unavailable")
        if not blockers and not profile_pin_missing:
            lines.append("- None within the requested repository scope.")
        if self.tool_error:
            lines.extend(["", "## Runner error", "", f"`{self.tool_error}`"])
        cleaned, hits = redact_text("\n".join(lines) + "\n")
        self.redaction_hits.extend(hits)
        path.write_text(cleaned, encoding="utf-8")

    def write_detailed(self, path: pathlib.Path, score: Mapping[str, Any]) -> None:
        profile_state = (
            "VALID" if is_nonzero_sha256(self.receipt_profile_decision_sha256) else "BLOCKED_MISSING"
        )
        lines = [
            "# Detailed B01–B10 Audit Report", "", f"Policy SHA-256: `{POLICY_SHA256}`",
            f"Receipt-profile decision pin: `{profile_state}`", "",
        ]
        for milestone in self.selected:
            lines.extend([f"## {milestone}", ""])
            for row in sorted((r for r in self.results.values() if r.milestone == milestone), key=lambda r: r.check_id):
                lines.extend([
                    f"### `{row.check_id}` — {row.outcome}", "",
                    f"- Hard gate: `{str(row.hard_gate).lower()}`",
                    f"- Weight/points: `{row.weight}/{row.points:g}`",
                    f"- Expected: {row.expected or 'declared work-order acceptance'}",
                    f"- Actual: {row.actual or 'not evaluated'}",
                    f"- Evidence: {', '.join(row.evidence_ids) if row.evidence_ids else 'none'}",
                    f"- Remediation: {row.remediation or 'provide independently verifiable exact-head evidence'}", "",
                ])
        lines.extend(["## Findings", ""])
        if not self.findings:
            lines.append("No findings beyond check outcomes.")
        for finding in self.findings:
            lines.extend([
                f"### `{finding.finding_id}` — {finding.severity} — {finding.title}", "",
                finding.detail, "", f"Remediation: {finding.remediation or 'not supplied'}", "",
            ])
        cleaned, hits = redact_text("\n".join(lines) + "\n")
        self.redaction_hits.extend(hits)
        path.write_text(cleaned, encoding="utf-8")

    def write_html(self, path: pathlib.Path, score: Mapping[str, Any], exit_code: int) -> None:
        rows = []
        for row in sorted(self.results.values(), key=lambda item: item.check_id):
            rows.append(
                "<tr>"
                f"<td><code>{html.escape(row.check_id)}</code></td>"
                f"<td>{html.escape(row.milestone)}</td>"
                f"<td>{html.escape(row.outcome)}</td>"
                f"<td>{row.weight}</td><td>{row.points:g}</td>"
                f"<td>{html.escape(row.actual or 'not evaluated')}</td>"
                f"<td>{html.escape(row.remediation or 'provide independently verified evidence')}</td>"
                "</tr>"
            )
        body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TRIAD ORIGIN B01-B10 audit</title>
<style>body{{font:14px/1.45 system-ui,sans-serif;margin:2rem;color:#17202a}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ccd1d1;padding:.45rem;vertical-align:top;text-align:left}}th{{background:#eef2f3;position:sticky;top:0}}code{{white-space:nowrap}}.boundary{{border-left:4px solid #b03a2e;padding:.7rem;background:#fdf2f2}}</style>
</head><body><h1>TRIAD ORIGIN B01-B10 Audit</h1>
<p class="boundary">Hard gate: <strong>{html.escape(str(score['hard_gate_result']))}</strong>. Status: <strong>{html.escape(str(score['status']))}</strong>. Receipt-profile decision pin valid: <strong>{html.escape(str(score['receipt_profile_decision_pin_valid']))}</strong>. A numeric score never overrides a failed or incomplete hard gate; repository evidence cannot authorize PAPER, TESTNET, LIVE, venue access, or money authority.</p>
<ul><li>Completion score: {score['program_completion_score']:.2f}/100</li><li>Evidence coverage: {score['evidence_coverage']:.2f}%</li><li>Exit code: {exit_code}</li><li>Activation result: {ACTIVATION_RESULT}</li></ul>
<table><thead><tr><th>Check</th><th>Milestone</th><th>Outcome</th><th>Weight</th><th>Points</th><th>Actual</th><th>Remediation</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
</body></html>"""
        cleaned, hits = redact_text(body)
        self.redaction_hits.extend(hits)
        path.write_text(cleaned, encoding="utf-8")

    def write_scorecard(self, path: pathlib.Path) -> None:
        fields = [
            "check_id", "milestone", "source_id", "kind", "title", "severity", "hard_gate",
            "weight", "outcome", "points", "expected", "actual", "evidence_ids", "remediation",
        ]
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=fields)
        writer.writeheader()
        for row in sorted(self.results.values(), key=lambda item: item.check_id):
            writer.writerow({
                "check_id": row.check_id, "milestone": row.milestone,
                "source_id": row.source_id, "kind": row.kind, "title": row.title,
                "severity": "HARD_GATE" if row.hard_gate else "ADVISORY",
                "hard_gate": str(row.hard_gate).lower(), "weight": row.weight,
                "outcome": row.outcome, "points": f"{row.points:g}",
                "expected": row.expected, "actual": row.actual,
                "evidence_ids": ";".join(row.evidence_ids), "remediation": row.remediation,
            })
        cleaned, hits = redact_text(buffer.getvalue())
        self.redaction_hits.extend(hits)
        path.write_text(cleaned, encoding="utf-8")

    def write_findings(self, path: pathlib.Path) -> None:
        fields = ["finding_id", "severity", "milestone", "check_id", "title", "detail", "evidence_ids", "remediation"]
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=fields)
        writer.writeheader()
        for row in self.findings:
            data = dataclasses.asdict(row)
            data["evidence_ids"] = ";".join(row.evidence_ids)
            writer.writerow(data)
        cleaned, hits = redact_text(buffer.getvalue())
        self.redaction_hits.extend(hits)
        path.write_text(cleaned, encoding="utf-8")

    def write_command_log(self, path: pathlib.Path, rows: Sequence[Mapping[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                cleaned, hits = redact_value(dict(row))
                self.redaction_hits.extend(hits)
                handle.write(json.dumps(cleaned, sort_keys=True, ensure_ascii=False) + "\n")

    def write_junit(self, path: pathlib.Path) -> None:
        profile_pin_failure = not is_nonzero_sha256(self.receipt_profile_decision_sha256)
        hard_failures = sum(
            1 for row in self.results.values()
            if row.outcome == FAIL or (row.hard_gate and row.outcome in INCOMPLETE_OUTCOMES)
        ) + (1 if profile_pin_failure else 0)
        nonhard_skips = sum(
            1 for row in self.results.values()
            if not row.hard_gate and row.outcome in INCOMPLETE_OUTCOMES)
        suite = ET.Element("testsuite", {
            "name": "triad-origin-b01-b10-audit",
            "tests": str(
                len(self.results) + (1 if self.tool_error else 0) + (1 if profile_pin_failure else 0)),
            "failures": str(hard_failures),
            "errors": str(1 if self.tool_error else 0),
            "skipped": str(nonhard_skips),
        })
        for row in sorted(self.results.values(), key=lambda item: item.check_id):
            case = ET.SubElement(suite, "testcase", {"classname": row.milestone, "name": row.check_id})
            if row.outcome == FAIL:
                node = ET.SubElement(case, "failure", {"message": row.actual or "hard gate failed"})
                node.text = row.remediation
            elif row.hard_gate and row.outcome in INCOMPLETE_OUTCOMES:
                node = ET.SubElement(
                    case, "failure", {"message": row.actual or f"incomplete hard gate: {row.outcome}"})
                node.text = row.remediation or "supply independently verified evidence"
            elif row.outcome in INCOMPLETE_OUTCOMES:
                ET.SubElement(case, "skipped", {"message": row.actual or row.outcome})
        if profile_pin_failure:
            case = ET.SubElement(
                suite, "testcase", {"classname": "GLOBAL", "name": "RECEIPT_PROFILE_DECISION_PIN"})
            ET.SubElement(case, "failure", {
                "message": "external ratified DECISION-RECEIPT-PROFILE-001 SHA-256 pin is unavailable",
            })
        if self.tool_error:
            case = ET.SubElement(suite, "testcase", {"classname": "RUNNER", "name": "RUNNER.INTERNAL"})
            ET.SubElement(case, "error", {"message": self.tool_error})
        raw = ET.tostring(suite, encoding="utf-8", xml_declaration=True).decode("utf-8")
        cleaned, hits = redact_text(raw)
        self.redaction_hits.extend(hits)
        path.write_text(cleaned, encoding="utf-8")

    def cleanup(self) -> None:
        if self.tempdir is not None:
            self.tempdir.cleanup()


def execute_bounded_command(
    command_id: str,
    argv: Sequence[str],
    cwd: pathlib.Path,
    timeout: int | float,
    max_log_bytes: int,
    extra_env: Mapping[str, str] | None = None,
) -> tuple[CommandRecord, str, str]:
    started = utc_now()
    env = {
        "PATH": os.environ.get("PATH", ""),
        "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC",
        "PYTHONDONTWRITEBYTECODE": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PYTHONHASHSEED": "0",
    }
    if extra_env:
        env.update({str(key): str(value) for key, value in extra_env.items()})
    timed_out = False
    exit_code: int | None = None

    def terminate_process_group(process: subprocess.Popen[Any], grace_seconds: float = 0.15) -> None:
        """Best-effort cleanup of the private POSIX session, including surviving descendants."""
        if os.name != "posix":
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            return

        def group_exists() -> bool:
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                return False
            except PermissionError:
                return True
            return True

        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(process.pid, signal.SIGTERM)
        deadline = time.monotonic() + grace_seconds
        while group_exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        if group_exists():
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(process.pid, signal.SIGKILL)

    with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
        process = subprocess.Popen(
            list(argv), cwd=str(cwd), env=env, stdin=subprocess.DEVNULL,
            stdout=stdout_file, stderr=stderr_file, close_fds=True,
            start_new_session=(os.name == "posix"))
        try:
            process.communicate(timeout=timeout)
            exit_code = process.returncode
            # A finished parent can still leave descendants behind.  Tear down the private
            # session before returning evidence to the caller.
            terminate_process_group(process)
        except subprocess.TimeoutExpired:
            timed_out = True
            terminate_process_group(process)
            process.communicate()
        stdout_size, stderr_size = stdout_file.tell(), stderr_file.tell()

        def digest_and_prefix(handle: Any) -> tuple[str, bytes]:
            digest = hashlib.sha256()
            prefix = bytearray()
            handle.seek(0)
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                if len(prefix) < max_log_bytes:
                    prefix.extend(chunk[:max_log_bytes - len(prefix)])
            return digest.hexdigest(), bytes(prefix)

        stdout_raw_sha256, stdout_raw = digest_and_prefix(stdout_file)
        stderr_raw_sha256, stderr_raw = digest_and_prefix(stderr_file)
    completed = utc_now()
    truncated = stdout_size > max_log_bytes or stderr_size > max_log_bytes
    stdout_slice = stdout_raw.decode("utf-8", errors="replace")
    stderr_slice = stderr_raw.decode("utf-8", errors="replace")
    stdout, stdout_hits = redact_text(stdout_slice)
    stderr, stderr_hits = redact_text(stderr_slice)
    record = CommandRecord(
        command_id=command_id, argv=list(argv), cwd=str(cwd),
        started_at=iso_z(started), completed_at=iso_z(completed),
        duration_ms=max(0, int((completed - started).total_seconds() * 1000)),
        exit_code=exit_code, timed_out=timed_out, stdout_path="", stderr_path="",
        stdout_sha256="", stderr_sha256="",
        stdout_raw_sha256=stdout_raw_sha256, stderr_raw_sha256=stderr_raw_sha256,
        truncated=truncated, redaction_hits=sorted(set(stdout_hits + stderr_hits)),
    )
    return record, stdout, stderr


def parse_milestones(value: str) -> tuple[str, ...]:
    if value.strip().upper() in {"ALL", "B01-B10"}:
        return tuple(f"B{i:02d}" for i in range(1, 11))
    result: list[str] = []
    for raw in value.split(","):
        item = raw.strip().upper()
        if not re.fullmatch(r"B(?:0[1-9]|10)", item):
            raise ValueError(f"invalid milestone {raw!r}; use B01..B10")
        if item not in result:
            result.append(item)
    if not result:
        raise ValueError("at least one milestone is required")
    return tuple(sorted(result))


def parse_pr_selections(values: Sequence[str] | None) -> dict[str, int]:
    result: dict[str, int] = {}
    for raw in values or ():
        match = re.fullmatch(r"(B(?:0[1-9]|10))=([1-9][0-9]*)", raw.strip().upper())
        if not match:
            raise ValueError(f"invalid PR selection {raw!r}; expected B01=123")
        milestone, number_text = match.groups()
        if milestone in result:
            raise ValueError(f"duplicate PR selection for {milestone}")
        result[milestone] = int(number_text)
    return result


def write_json(path: pathlib.Path, value: Any) -> None:
    cleaned, _ = redact_value(value)
    path.write_text(json.dumps(cleaned, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def media_type(path: pathlib.Path) -> str:
    return {
        ".json": "application/json", ".ndjson": "application/x-ndjson",
        ".csv": "text/csv", ".md": "text/markdown", ".html": "text/html", ".xml": "application/xml",
        ".txt": "text/plain",
    }.get(path.suffix.lower(), "application/octet-stream")


def verify_evidence_manifest(root: pathlib.Path, manifest_path: pathlib.Path) -> list[str]:
    issues: list[str] = []
    try:
        manifest = strict_json_loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, DuplicateJSONKey, RecursionError) as exc:
        return [f"manifest unreadable: {exc}"]
    if not isinstance(manifest, dict):
        return ["manifest root is not an object"]
    rows = manifest.get("artifacts")
    if not isinstance(rows, list):
        return ["manifest artifacts is not an array"]
    root = root.resolve()
    seen: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            issues.append(f"artifact[{index}] is not an object")
            continue
        relative = str(row.get("path", ""))
        if relative in seen:
            issues.append(f"duplicate manifest path {relative}")
            continue
        seen.add(relative)
        raw_candidate = root / pathlib.Path(relative)
        candidate = raw_candidate.resolve()
        if candidate != root and root not in candidate.parents:
            issues.append(f"manifest path escapes root: {relative}")
        elif raw_candidate.is_symlink():
            issues.append(f"manifest artifact is a symbolic link: {relative}")
        elif not candidate.is_file():
            issues.append(f"manifest artifact missing: {relative}")
        elif sha256_file(candidate) != row.get("sha256"):
            issues.append(f"manifest artifact digest mismatch: {relative}")
        elif candidate.stat().st_size != row.get("bytes"):
            issues.append(f"manifest artifact size mismatch: {relative}")
        if not isinstance(row.get("source_uri"), str) or not row.get("source_uri"):
            issues.append(f"manifest artifact has no source_uri: {relative}")
        if not isinstance(row.get("source_kind"), str) or not row.get("source_kind"):
            issues.append(f"manifest artifact has no source_kind: {relative}")
        if not isinstance(row.get("check_ids"), list):
            issues.append(f"manifest artifact has no check_ids array: {relative}")
    return list(dict.fromkeys(issues))


def report_secret_issues(root: pathlib.Path) -> list[str]:
    issues: list[str] = []
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        # Scan every bundle member before archive creation, including extensionless
        # content-addressed preimages.  Binary decoding with replacement cannot invent one of the
        # long credential signatures below, but it can still expose embedded ASCII secrets.
        text_value = path.read_bytes().decode("utf-8", errors="replace")
        for name, pattern in SECRET_PATTERNS:
            if pattern.search(text_value):
                issues.append(f"{name} remains in {path.relative_to(root)}")
    return issues


def deterministic_zip(root: pathlib.Path, target: pathlib.Path) -> None:
    files = sorted(path for path in root.rglob("*") if path.is_file() and path != target)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            info = zipfile.ZipInfo(str(path.relative_to(root)), date_time=(2026, 8, 9, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def make_valid_receipt(
    path: pathlib.Path, milestone: str, now: dt.datetime,
) -> tuple[pathlib.Path, str, str]:
    root = path.parent
    evidence_files: dict[str, pathlib.Path] = {}
    for _field, role in REQUIRED_RECEIPT_DIGEST_ROLES:
        suffix = ".json" if role == "RECEIPT_PROFILE_DECISION" else ".txt"
        evidence_path = root / f"fixture_{role.lower()}{suffix}"
        content = (
            json.dumps(SUPPORTED_RECEIPT_PROFILE_DECISION, sort_keys=True, separators=(",", ":")) + "\n"
            if role == "RECEIPT_PROFILE_DECISION"
            else f"immutable {role} fixture evidence\n"
        )
        evidence_path.write_text(content, encoding="utf-8")
        evidence_files[role] = evidence_path
    producer_seed = bytes(range(32))
    counter_seed = bytes(range(32, 64))
    producer_public, _ = _ed25519_sign_for_self_test(producer_seed, b"")
    counter_public, _ = _ed25519_sign_for_self_test(counter_seed, b"")
    now_us = int(now.timestamp() * 1_000_000)
    registry = {
        "schema": "triad.receipt_trust_registry.v1",
        "keys": [
            {
                "key_id": "fixture-producer", "identity": "builder-a", "role": "PRODUCER",
                "algorithm": "Ed25519", "status": "ACTIVE",
                "public_key_base64": base64.b64encode(producer_public).decode("ascii"),
                "valid_from_us": str(now_us - 86_400_000_000),
                "valid_until_us": str(now_us + 365 * 86_400_000_000),
                "approved_milestones": ["ALL"],
            },
            {
                "key_id": "fixture-countersigner", "identity": "reviewer-b", "role": "COUNTERSIGNER",
                "algorithm": "Ed25519", "status": "ACTIVE",
                "public_key_base64": base64.b64encode(counter_public).decode("ascii"),
                "valid_from_us": str(now_us - 86_400_000_000),
                "valid_until_us": str(now_us + 365 * 86_400_000_000),
                "approved_milestones": ["ALL"],
            },
        ],
    }
    registry_path = root / "receipt_signers.v1.json"
    registry_path.write_text(
        json.dumps(registry, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    registry_digest = sha256_file(registry_path)
    source_head_sha = "9" * 40
    role_digests = {role: sha256_file(evidence_files[role]) for _, role in REQUIRED_RECEIPT_DIGEST_ROLES}
    evidence_rows = [
        {
            "evidence_id": f"ev-{role.lower()}", "path": evidence_files[role].name,
            "sha256": role_digests[role], "digest_role": role,
            "producer": "fixture-producer",
            "observed_at_us": str(now_us - 2_500_000),
            "media_type": "application/json" if role == "RECEIPT_PROFILE_DECISION" else "text/plain",
        }
        for _, role in REQUIRED_RECEIPT_DIGEST_ROLES
    ]
    payload: dict[str, Any] = {
        "receipt_id": f"receipt-{milestone.lower()}-fixture", "milestone_id": milestone,
        "receipt_kind": "TERMINAL_REPOSITORY" if milestone == "B10" else "MILESTONE_SOURCE",
        "scope": {
            "repository": "triadagentic/triadorigin", "milestone": milestone,
            "execution_plane": "OFF", "environment": "REPOSITORY", "authority": "REPOSITORY_ONLY",
        },
        "result": PASS, "status": "CURRENT", "open_blockers": [],
        "builder": "builder-a", "reviewer": "reviewer-b",
        "source_pr": 1, "receipt_pr": 2,
        "build_commit": "a" * 40, "merge_commit": "a" * 40,
        "source_head_sha": source_head_sha, "review_head_sha": source_head_sha,
        "reviewed_at_us": str(now_us - 4_000_000), "unresolved_p0_p1": 0,
        "ci_runs": [{
            "run_id": 1, "head_sha": source_head_sha, "conclusion": "SUCCESS",
            "required_jobs_unskipped": True,
        }],
        "governance": {"branch_rules_enforced": True, "bypass_used": False},
        "correction_of_receipt_ids": [],
        **{field: role_digests[role] for field, role in REQUIRED_RECEIPT_DIGEST_ROLES},
        "source_merge_at_us": str(now_us - 3_000_000),
        "observed_at_us": str(now_us - 2_000_000),
        "emitted_at_us": str(now_us - 1_000_000),
        "expires_at_us": str(now_us + 86_400_000_000),
        "trust_registry_sha256": registry_digest,
        "evidence": evidence_rows,
    }
    if milestone != "B01":
        payload["predecessor_receipt_id"] = "receipt-predecessor-fixture"
        # The isolated receipt-law fixture has no predecessor file to bind, but the v3 law still
        # requires a syntactically valid, non-zero content digest.  Receipt-chain self-tests create
        # real predecessor files and independently verify their exact bytes.
        payload["predecessor_receipt_sha256"] = "7" * 64
    payload_bytes = jcs_canonical_bytes(payload)
    payload_type = "application/vnd.triad.evidence-receipt.v3+json"
    pae = dsse_pae(payload_type, payload_bytes)
    _, producer_signature = _ed25519_sign_for_self_test(producer_seed, pae)
    _, counter_signature = _ed25519_sign_for_self_test(counter_seed, pae)
    event = {
        "schema": "triad.evidence_receipt.v3", "payload": payload,
        "dsse": {
            "payloadType": payload_type,
            "payload": base64.b64encode(payload_bytes).decode("ascii"),
            "signatures": [
                {"keyid": "fixture-producer", "sig": base64.b64encode(producer_signature).decode("ascii")},
                {"keyid": "fixture-countersigner", "sig": base64.b64encode(counter_signature).decode("ascii")},
            ],
        },
    }
    path.write_text(json.dumps(event, sort_keys=True), encoding="utf-8")
    return registry_path, registry_digest, role_digests["RECEIPT_PROFILE_DECISION"]


def run_self_tests() -> int:
    tests: list[tuple[str, Any]] = []

    def register(name: str):
        def decorator(func: Any) -> Any:
            tests.append((name, func))
            return func
        return decorator

    def resign_fixture_receipt(path: pathlib.Path) -> None:
        event = strict_json_loads(path.read_text(encoding="utf-8"))
        assert isinstance(event, dict) and isinstance(event.get("payload"), dict)
        envelope = event.get("dsse")
        assert isinstance(envelope, dict)
        payload_type = str(envelope.get("payloadType"))
        payload_bytes = jcs_canonical_bytes(event["payload"])
        pae = dsse_pae(payload_type, payload_bytes)
        _, producer_signature = _ed25519_sign_for_self_test(bytes(range(32)), pae)
        _, counter_signature = _ed25519_sign_for_self_test(bytes(range(32, 64)), pae)
        envelope["payload"] = base64.b64encode(payload_bytes).decode("ascii")
        envelope["signatures"] = [
            {
                "keyid": "fixture-producer",
                "sig": base64.b64encode(producer_signature).decode("ascii"),
            },
            {
                "keyid": "fixture-countersigner",
                "sig": base64.b64encode(counter_signature).decode("ascii"),
            },
        ]
        path.write_text(json.dumps(event, sort_keys=True), encoding="utf-8")

    def receipt_mutation_issues(mutator: Any, milestone: str = "B05") -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            path = root / f"{milestone}C.json"
            now = utc_now()
            registry, pin, profile_pin = make_valid_receipt(path, milestone, now)
            event = strict_json_loads(path.read_text(encoding="utf-8"))
            assert isinstance(event, dict)
            mutator(event, root)
            path.write_text(json.dumps(event, sort_keys=True), encoding="utf-8")
            issues, _ = receipt_issues(
                path, milestone, now, repository_root=root,
                trust_registry_path=registry, trust_registry_sha256=pin,
                receipt_profile_decision_sha256=profile_pin,
            )
            return issues

    def fixture_runner_args(output: pathlib.Path | None = None) -> argparse.Namespace:
        argv = [
            "--mode", "github", "--milestones", "B01",
            "--workflow-sha256", "f" * 64, "--expected-head", "a" * 40,
            "--receipt-profile-decision-sha256", "e" * 64,
        ]
        if output is not None:
            argv.extend(["--output", str(output)])
        return build_parser().parse_args(argv)

    @register("policy IDs unique and per-milestone weights exact")
    def _policy() -> None:
        assert len({row.check_id for row in POLICY}) == len(POLICY)
        totals = defaultdict(int)
        for row in POLICY:
            totals[row.milestone] += row.weight
        assert set(totals.values()) == {100}

    @register("redaction removes bearer, Basic, cookie, MCP, JWT, GitHub, and query tokens")
    def _redaction() -> None:
        # Assemble credential-shaped *fake* values at runtime so source scanners do not mistake
        # this negative fixture for a committed credential.
        fake_bearer = "abc" + "defghijklmnopqrstuvwxyz"
        fake_query = "abc" + "defghijklmnop"
        fake_github = "gh" + "p_" + "abcdefghijklmnopqrstuvwxyz123456"
        fake_mcp = "tm" + "c_" + "abcdefghijklmnopqrstuvwxyz123456"
        fake_basic = "dXNl" + "cjpzdXBlcnNlY3JldA=="
        fake_jwt = ".".join(("eyJ" + "abcdefghijk", "abcdefghijklmnop", "abcdefghijklmnop"))
        source = (
            "Authorization: " + "Bearer " + fake_bearer + " token?token=" + fake_query + " "
            + fake_github + " " + fake_mcp + " " + fake_jwt
            + "\nAuthorization: Basic " + fake_basic
            + "\nCookie: sessionid=" + "cookie-secret-value"
            + "\npassword=" + "correct-horse-battery "
            + "https://user:" + "supersecretvalue@example.invalid/path")
        cleaned, hits = redact_text(source)
        assert "abcdefghijklmnopqrstuvwxyz" not in cleaned and "correct-horse" not in cleaned
        assert "supersecretvalue" not in cleaned and "dXNlcj" not in cleaned
        assert "cookie-secret-value" not in cleaned
        assert hits
        structured, structured_hits = redact_value({
            "password": "not-written-to-any-report",
            "nested": {"refresh-token": "also-never-written", "signature": "public-proof"},
        })
        assert structured["password"] == "<REDACTED>"
        assert structured["nested"]["refresh-token"] == "<REDACTED>"
        assert structured["nested"]["signature"] == "public-proof"
        assert len(structured_hits) == 2

    @register("valid receipt fixture passes")
    def _valid_receipt() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "B05C.json"
            now = utc_now()
            registry, pin, profile_pin = make_valid_receipt(path, "B05", now)
            issues, _ = receipt_issues(
                path, "B05", now, repository_root=path.parent,
                trust_registry_path=registry, trust_registry_sha256=pin,
                receipt_profile_decision_sha256=profile_pin)
            assert not issues, issues

    @register("receipt profile decision requires external pin and exact bundled preimage")
    def _receipt_profile_decision_pin() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            path = root / "B05C.json"
            now = utc_now()
            registry, pin, profile_pin = make_valid_receipt(path, "B05", now)
            missing, _ = receipt_issues(
                path, "B05", now, repository_root=root,
                trust_registry_path=registry, trust_registry_sha256=pin,
                receipt_profile_decision_sha256=None)
            assert any("external receipt-profile decision" in issue for issue in missing), missing
            mismatch, _ = receipt_issues(
                path, "B05", now, repository_root=root,
                trust_registry_path=registry, trust_registry_sha256=pin,
                receipt_profile_decision_sha256="b" * 64)
            assert any("DECISION-RECEIPT-PROFILE-001 pin" in issue for issue in mismatch), mismatch
            decision_preimage = root / "fixture_receipt_profile_decision.json"
            decision = strict_json_loads(decision_preimage.read_text(encoding="utf-8"))
            decision["max_receipt_ttl_us"] = 123
            decision_preimage.write_text(
                json.dumps(decision, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8")
            unsupported_pin = sha256_file(decision_preimage)
            event = strict_json_loads(path.read_text(encoding="utf-8"))
            event["payload"]["receipt_profile_decision_sha256"] = unsupported_pin
            decision_row = next(
                row for row in event["payload"]["evidence"]
                if row.get("digest_role") == "RECEIPT_PROFILE_DECISION")
            decision_row["sha256"] = unsupported_pin
            path.write_text(json.dumps(event, sort_keys=True), encoding="utf-8")
            resign_fixture_receipt(path)
            unsupported, _ = receipt_issues(
                path, "B05", now, repository_root=root,
                trust_registry_path=registry, trust_registry_sha256=pin,
                receipt_profile_decision_sha256=unsupported_pin)
            assert any("max_receipt_ttl_us" in issue for issue in unsupported), unsupported

            decision_preimage.write_text("unratified replacement\n", encoding="utf-8")
            tampered, _ = receipt_issues(
                path, "B05", now, repository_root=root,
                trust_registry_path=registry, trust_registry_sha256=pin,
                receipt_profile_decision_sha256=unsupported_pin)
            assert any(
                "preimage digest mismatch" in issue and "receipt_profile_decision" in issue
                for issue in tampered
            ), tampered

    @register("missing receipt profile authority blocks otherwise all-PASS score")
    def _receipt_profile_score_gate() -> None:
        runner = AuditRunner(fixture_runner_args())
        for row in runner.results.values():
            row.set_outcome(PASS, actual="fixture")
        runner.receipt_profile_decision_sha256 = None
        score = runner.score()
        assert score["status"] == "BLOCKED_INCOMPLETE", score
        assert score["hard_gate_result"] == BLOCKED, score
        assert score["receipt_profile_decision_pin_valid"] is False, score

    @register("receipt status vocabulary is exactly CURRENT")
    def _receipt_status() -> None:
        issues = receipt_mutation_issues(
            lambda event, _root: event["payload"].__setitem__("status", "BANANA"))
        assert any("status must be exactly CURRENT" in issue for issue in issues), issues

    @register("receipt scope is closed to the repository safe-hold plane")
    def _receipt_scope() -> None:
        def mutate(event: dict[str, Any], _root: pathlib.Path) -> None:
            event["payload"]["scope"] = {
                "repository": "attacker/unrelated",
                "milestone": "B05",
                "execution_plane": "LIVE",
                "environment": "REAL_MONEY",
                "authority": "VENUE_TRADING",
            }

        issues = receipt_mutation_issues(mutate)
        for field in ("repository", "execution_plane", "environment", "authority"):
            assert any(f"scope {field}=" in issue for issue in issues), (field, issues)

    @register("receipt remote evidence URI cannot masquerade as a local preimage")
    def _receipt_remote_uri() -> None:
        def mutate(event: dict[str, Any], _root: pathlib.Path) -> None:
            row = event["payload"]["evidence"][0]
            row.pop("path")
            row["uri"] = "https://evil.invalid/" + "a" * 40 + "/proof"

        issues = receipt_mutation_issues(mutate)
        assert any("remote URI" in issue and "bundled local preimage" in issue for issue in issues), issues

    @register("receipt required digest must recompute from its typed preimage")
    def _receipt_recomputed_digest() -> None:
        field, _role = REQUIRED_RECEIPT_DIGEST_ROLES[0]
        issues = receipt_mutation_issues(
            lambda event, _root: event["payload"].__setitem__(field, "b" * 64))
        assert any(
            f"required digest {field} is not recomputed" in issue for issue in issues
        ), issues

    @register("receipt evidence chronology is bounded by merge and observation")
    def _receipt_evidence_chronology() -> None:
        def mutate(event: dict[str, Any], _root: pathlib.Path) -> None:
            observed = int(event["payload"]["observed_at_us"])
            event["payload"]["evidence"][0]["observed_at_us"] = str(observed + 1)

        issues = receipt_mutation_issues(mutate)
        assert any("evidence[0] chronology" in issue for issue in issues), issues

    @register("receipt source and receipt pull requests cannot collide")
    def _receipt_pr_collision() -> None:
        issues = receipt_mutation_issues(
            lambda event, _root: event["payload"].__setitem__(
                "receipt_pr", event["payload"]["source_pr"]))
        assert any("must be different pull requests" in issue for issue in issues), issues

    @register("receipt DSSE payload type and bytes are both exact")
    def _receipt_dsse_payload() -> None:
        type_issues = receipt_mutation_issues(
            lambda event, _root: event["dsse"].__setitem__("payloadType", "application/json"))
        assert any("closed receipt-v3 media type" in issue for issue in type_issues), type_issues
        byte_issues = receipt_mutation_issues(
            lambda event, _root: event["dsse"].__setitem__(
                "payload", base64.b64encode(b"{}").decode("ascii")))
        assert any("do not equal RFC 8785 canonical" in issue for issue in byte_issues), byte_issues

    @register("RFC 8032 Ed25519 verification vector passes and tamper fails")
    def _rfc8032() -> None:
        public_key = bytes.fromhex(
            "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
        signature = bytes.fromhex(
            "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
            "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")
        assert ed25519_verify(public_key, b"", signature)
        assert not ed25519_verify(public_key, b"tampered", signature)

    @register("Ed25519 rejects small-order and noncanonical identity encodings")
    def _ed25519_strict_points() -> None:
        message = b"strict Ed25519 negative fixture"
        seed = bytes(range(32))
        expanded = hashlib.sha512(seed).digest()
        scalar_bytes = bytearray(expanded[:32])
        scalar_bytes[0] &= 248
        scalar_bytes[31] &= 63
        scalar_bytes[31] |= 64
        secret_scalar = int.from_bytes(scalar_bytes, "little")
        public_key = _ed_encode(_ed_scalar_mult(_ED_B, secret_scalar))
        identity = (1).to_bytes(32, "little")
        noncanonical_identity = (1 | (1 << 255)).to_bytes(32, "little")

        challenge = int.from_bytes(
            hashlib.sha512(identity + public_key + message).digest(), "little") % _ED_L
        forged_scalar = (challenge * secret_scalar) % _ED_L
        forged = identity + forged_scalar.to_bytes(32, "little")
        assert not ed25519_verify(public_key, message, forged)
        assert not ed25519_verify(
            public_key, message,
            noncanonical_identity + forged_scalar.to_bytes(32, "little"),
        )
        assert not ed25519_verify(identity, message, identity + b"\0" * 32)

    @register("embedded verified booleans cannot authenticate a receipt")
    def _embedded_verified() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "B05C.json"
            now = utc_now()
            registry, pin, profile_pin = make_valid_receipt(path, "B05", now)
            data = json.loads(path.read_text())
            data.pop("dsse")
            data["payload"]["authentication"] = {"verified": True}
            path.write_text(json.dumps(data))
            issues, _ = receipt_issues(
                path, "B05", now, repository_root=path.parent,
                trust_registry_path=registry, trust_registry_sha256=pin,
                receipt_profile_decision_sha256=profile_pin)
            assert any("DSSE" in issue for issue in issues)

    @register("embedded verified boolean cannot authenticate work-package index")
    def _embedded_index_verified() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            path = root / "check_results.v1.json"
            path.write_text(json.dumps({
                "schema": CHECK_EVIDENCE_SCHEMA, "subject_sha": "a" * 40,
                "producer": "producer", "reviewed_by": ["reviewer"],
                "authentication": {"verified": True},
                "checks": [{"check_id": "B01.WP-B01C-01", "outcome": FAIL, "evidence": []}],
            }), encoding="utf-8")
            rows, issues = validate_check_evidence_index(
                root, path, "a" * 40, {"B01.WP-B01C-01"}, now=utc_now(),
                trust_registry_path=None, trust_registry_sha256=None)
            assert not rows and any("authenticated receipt" in issue for issue in issues)

    @register("authenticated check evidence index passes then fails closed on header tamper")
    def _authenticated_index_binding() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            now = utc_now()
            subject_sha = "a" * 40
            check_id = "B01.WP-B01C-01"
            proof = root / "proof.txt"
            proof.write_text("independent work-package proof\n", encoding="utf-8")
            index_path = root / "check_results.v1.json"
            index = {
                "schema": CHECK_EVIDENCE_SCHEMA,
                "subject_sha": subject_sha,
                "producer": "evidence-producer",
                "reviewed_by": ["evidence-reviewer"],
                "authentication_receipt_path": "B01C.json",
                "authentication_receipt_milestone": "B01",
                "checks": [{
                    "check_id": check_id,
                    "outcome": PASS,
                    "actual": "fixture accepted",
                    "expected": "fixture proof",
                    "evidence": [{"path": proof.name, "sha256": sha256_file(proof)}],
                }],
            }
            index_path.write_text(json.dumps(index, sort_keys=True), encoding="utf-8")
            receipt_path = root / "B01C.json"
            registry, pin, profile_pin = make_valid_receipt(receipt_path, "B01", now)
            receipt = strict_json_loads(receipt_path.read_text(encoding="utf-8"))
            receipt["payload"]["build_commit"] = subject_sha
            receipt["payload"]["merge_commit"] = subject_sha
            receipt["payload"]["evidence"].append({
                "evidence_id": "ev-check-index",
                "path": index_path.name,
                "sha256": sha256_file(index_path),
                "digest_role": "CHECK_EVIDENCE_INDEX",
                "producer": "fixture-producer",
                "observed_at_us": receipt["payload"]["observed_at_us"],
                "media_type": "application/json",
            })
            receipt_path.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
            resign_fixture_receipt(receipt_path)

            rows, issues = validate_check_evidence_index(
                root, index_path, subject_sha, {check_id}, now=now,
                trust_registry_path=registry, trust_registry_sha256=pin,
                receipt_profile_decision_sha256=profile_pin)
            assert not issues and rows.get(check_id, {}).get("outcome") == PASS, (rows, issues)

            index["subject_sha"] = "b" * 40
            index["reviewed_by"] = [index["producer"]]
            index["authentication"] = {"verified": True}
            index_path.write_text(json.dumps(index, sort_keys=True), encoding="utf-8")
            rows, issues = validate_check_evidence_index(
                root, index_path, subject_sha, {check_id}, now=now,
                trust_registry_path=registry, trust_registry_sha256=pin,
                receipt_profile_decision_sha256=profile_pin)
            assert not rows, (rows, issues)
            assert any("subject_sha does not match" in issue for issue in issues), issues
            assert any("independent producer/reviewer" in issue for issue in issues), issues
            assert any("authentication receipt failed" in issue for issue in issues), issues

    @register("malformed check evidence index root fails closed without exception")
    def _malformed_index_root() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            index_path = root / "check_results.v1.json"
            index_path.write_text("[]", encoding="utf-8")
            rows, issues = validate_check_evidence_index(
                root, index_path, "a" * 40, set(), now=utc_now(),
                trust_registry_path=None, trust_registry_sha256=None)
            assert not rows and issues == ["check evidence index root must be an object"]

    @register("repository receipt has zero future-time tolerance")
    def _future_receipt() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "B05C.json"
            now = utc_now()
            registry, pin, profile_pin = make_valid_receipt(path, "B05", now)
            data = json.loads(path.read_text())
            data["payload"]["emitted_at_us"] = str(int(now.timestamp() * 1_000_000) + 1)
            path.write_text(json.dumps(data))
            issues, _ = receipt_issues(
                path, "B05", now, repository_root=path.parent,
                trust_registry_path=registry, trust_registry_sha256=pin,
                receipt_profile_decision_sha256=profile_pin)
            assert any("future" in issue and "zero future tolerance" in issue for issue in issues), issues

    @register("receipt TTL over 30 days fails")
    def _receipt_ttl() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "B05C.json"
            now = utc_now()
            registry, pin, profile_pin = make_valid_receipt(path, "B05", now)
            data = json.loads(path.read_text())
            emitted = int(data["payload"]["emitted_at_us"])
            data["payload"]["expires_at_us"] = str(emitted + MAX_RECEIPT_TTL_US + 1)
            path.write_text(json.dumps(data))
            issues, _ = receipt_issues(
                path, "B05", now, repository_root=path.parent,
                trust_registry_path=registry, trust_registry_sha256=pin,
                receipt_profile_decision_sha256=profile_pin)
            assert any("30 days" in issue for issue in issues)

    @register("receipt result vocabulary is exactly PASS")
    def _receipt_result() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "B05C.json"
            now = utc_now()
            registry, pin, profile_pin = make_valid_receipt(path, "B05", now)
            data = json.loads(path.read_text())
            data["payload"]["result"] = "SAFE_HOLD"
            path.write_text(json.dumps(data))
            issues, _ = receipt_issues(
                path, "B05", now, repository_root=path.parent,
                trust_registry_path=registry, trust_registry_sha256=pin,
                receipt_profile_decision_sha256=profile_pin)
            assert any("exactly PASS" in issue for issue in issues)

    @register("all-zero digest fails")
    def _zero_digest() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "B05C.json"
            now = utc_now()
            registry, pin, profile_pin = make_valid_receipt(path, "B05", now)
            data = json.loads(path.read_text())
            data["payload"]["artifact_sha256"] = "0" * 64
            path.write_text(json.dumps(data))
            issues, _ = receipt_issues(
                path, "B05", now, repository_root=path.parent,
                trust_registry_path=registry, trust_registry_sha256=pin,
                receipt_profile_decision_sha256=profile_pin)
            assert any("non-zero" in issue for issue in issues)

    @register("evidence cardinality mismatch fails")
    def _cardinality() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "B05C.json"
            now = utc_now()
            registry, pin, profile_pin = make_valid_receipt(path, "B05", now)
            data = json.loads(path.read_text())
            data["payload"]["evidence_ids"] = ["ev-1", "ev-2"]
            data["payload"]["evidence_sha256s"] = [data["payload"]["evidence"][0]["sha256"]]
            path.write_text(json.dumps(data))
            issues, _ = receipt_issues(
                path, "B05", now, repository_root=path.parent,
                trust_registry_path=registry, trust_registry_sha256=pin,
                receipt_profile_decision_sha256=profile_pin)
            assert any("cardinality" in issue for issue in issues)

    @register("self-hash is rejected as authentication")
    def _self_hash() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "B05C.json"
            now = utc_now()
            registry, pin, profile_pin = make_valid_receipt(path, "B05", now)
            data = json.loads(path.read_text())
            data.pop("dsse")
            data["payload"]["signature"] = ""
            data["payload"]["signature"] = sha256_bytes(canonical_json_bytes(data["payload"]))
            path.write_text(json.dumps(data))
            issues, _ = receipt_issues(
                path, "B05", now, repository_root=path.parent,
                trust_registry_path=registry, trust_registry_sha256=pin,
                receipt_profile_decision_sha256=profile_pin)
            assert any("self-hash" in issue for issue in issues)
            assert any("DSSE" in issue for issue in issues)

    @register("tampered pinned trust registry fails")
    def _tampered_trust() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "B05C.json"
            now = utc_now()
            registry, pin, profile_pin = make_valid_receipt(path, "B05", now)
            registry.write_text(registry.read_text() + " ", encoding="utf-8")
            issues, _ = receipt_issues(
                path, "B05", now, repository_root=path.parent,
                trust_registry_path=registry, trust_registry_sha256=pin,
                receipt_profile_decision_sha256=profile_pin)
            assert any("external pin" in issue for issue in issues)

    def github_pull_fixture(
        *, number: int, head_sha: str, base_sha: str, merge_sha: str,
        created: dt.datetime, committed: dt.datetime, reviewed: dt.datetime,
        merged: dt.datetime, receipt: bool,
    ) -> dict[str, Any]:
        required = REQUIRED_RECEIPT_CI_STEPS if receipt else REQUIRED_CI_STEPS
        steps = [{"name": name, "conclusion": "success"} for name in required]
        return {
            "pr": {
                "number": number, "title": f"B01 {'receipt' if receipt else 'source'}",
                "head": {"sha": head_sha}, "base": {"sha": base_sha},
                "merge_commit_sha": merge_sha, "user": {"login": "author"},
                "created_at": iso_z(created), "merged_at": iso_z(merged),
            },
            "commits": [{"sha": head_sha, "commit": {"committer": {"date": iso_z(committed)}}}],
            "reviews": [{
                "state": "APPROVED", "submitted_at": iso_z(reviewed),
                "commit_id": head_sha, "user": {"login": "reviewer"},
            }],
            "review_threads": [],
            "workflow_runs": [{
                "head_sha": head_sha, "status": "completed", "conclusion": "success",
                "path": ".github/workflows/ci.yml", "event": "pull_request",
                "updated_at": iso_z(reviewed + dt.timedelta(seconds=30)),
                "jobs": [{"steps": steps}],
            }],
        }

    def github_fixture() -> dict[str, Any]:
        now = utc_now()
        source = github_pull_fixture(
            number=1, head_sha="1" * 40, base_sha="2" * 40, merge_sha="3" * 40,
            created=now - dt.timedelta(minutes=40), committed=now - dt.timedelta(minutes=30),
            reviewed=now - dt.timedelta(minutes=20), merged=now - dt.timedelta(minutes=15),
            receipt=False,
        )
        source["merge_proof"] = {
            "kind": "ANCESTOR", "verified": True,
            "head_sha": "1" * 40, "merge_sha": "3" * 40,
        }
        source["merge_contains_head"] = True
        receipt = github_pull_fixture(
            number=2, head_sha="4" * 40, base_sha="3" * 40, merge_sha="5" * 40,
            created=now - dt.timedelta(minutes=14), committed=now - dt.timedelta(minutes=10),
            reviewed=now - dt.timedelta(minutes=5), merged=now - dt.timedelta(minutes=1),
            receipt=True,
        )
        receipt["contains_source_merge"] = True
        return {
            "schema": GITHUB_SNAPSHOT_SCHEMA, "repository": "TriadAgentic/TriadOrigin",
            "default_branch": "main",
            "issue_5": {"number": 5, "state": "closed"},
            "milestones": {
                "B01": {
                    "source": source, "receipt": receipt,
                    "source_candidate_numbers": [1], "receipt_candidate_numbers": [2],
                },
            },
            "governance": {
                "active_ruleset_summaries_present": True,
                "branch_protection_enforced": True,
                "default_branch_controls": {
                    "schema": "triad.github.default_branch_controls.v1",
                    "target_ref": "refs/heads/main", "ruleset_ids": [101],
                    "pull_request_required": True, "required_approving_review_count": 1,
                    "resolved_conversations_required": True,
                    "stale_head_rejection_required": True,
                    "required_status_checks": ["ci / required"],
                    "required_status_checks_strict": True,
                },
                "bypass_used": False,
                "signed_waiver_verified": False,
            },
        }

    def signed_github_fixture(root: pathlib.Path) -> tuple[dict[str, Any], pathlib.Path, str]:
        now = utc_now()
        now_us = int(now.timestamp() * 1_000_000)
        auditor_seed, counter_seed = b"A" * 32, b"B" * 32
        auditor_public, _ = _ed25519_sign_for_self_test(auditor_seed, b"")
        counter_public, _ = _ed25519_sign_for_self_test(counter_seed, b"")
        registry = {
            "schema": "triad.receipt_trust_registry.v1",
            "keys": [
                {
                    "key_id": "audit-key", "identity": "auditor-a", "role": "AUDITOR",
                    "algorithm": "Ed25519", "status": "ACTIVE",
                    "public_key_base64": base64.b64encode(auditor_public).decode("ascii"),
                    "valid_from_us": str(now_us - 1_000_000),
                    "valid_until_us": str(now_us + 86_400_000_000),
                    "approved_milestones": ["ALL"],
                },
                {
                    "key_id": "counter-key", "identity": "auditor-b", "role": "COUNTERSIGNER",
                    "algorithm": "Ed25519", "status": "ACTIVE",
                    "public_key_base64": base64.b64encode(counter_public).decode("ascii"),
                    "valid_from_us": str(now_us - 1_000_000),
                    "valid_until_us": str(now_us + 86_400_000_000),
                    "approved_milestones": ["ALL"],
                },
            ],
        }
        registry_path = root / "github_trust.json"
        registry_path.write_text(json.dumps(registry, sort_keys=True), encoding="utf-8")
        pin = sha256_file(registry_path)
        payload = json.loads(json.dumps(github_fixture()))
        payload.update({
            "emitted_at_us": str(now_us - 100_000),
            "expires_at_us": str(now_us + 3_600_000_000),
            "trust_registry_sha256": pin,
            "producer": "auditor-a", "reviewed_by": ["auditor-b"],
        })
        payload_bytes = jcs_canonical_bytes(payload)
        pae = dsse_pae(GITHUB_SNAPSHOT_PAYLOAD_TYPE, payload_bytes)
        _, auditor_sig = _ed25519_sign_for_self_test(auditor_seed, pae)
        _, counter_sig = _ed25519_sign_for_self_test(counter_seed, pae)
        envelope = {
            "schema": GITHUB_SNAPSHOT_ENVELOPE_SCHEMA, "payload": payload,
            "dsse": {
                "payloadType": GITHUB_SNAPSHOT_PAYLOAD_TYPE,
                "payload": base64.b64encode(payload_bytes).decode("ascii"),
                "signatures": [
                    {"keyid": "audit-key", "sig": base64.b64encode(auditor_sig).decode("ascii")},
                    {"keyid": "counter-key", "sig": base64.b64encode(counter_sig).decode("ascii")},
                ],
            },
        }
        return envelope, registry_path, pin

    @register("signed offline GitHub snapshot verifies and tamper fails")
    def _signed_github() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            envelope, registry, pin = signed_github_fixture(pathlib.Path(tmp))
            issues, payload = verify_offline_github_envelope(
                envelope, trust_registry_path=registry, trust_registry_sha256=pin,
                selected=("B01",), now=utc_now())
            assert not issues and payload is not None, issues
            envelope["payload"]["repository"] = "attacker/other"
            issues, _ = verify_offline_github_envelope(
                envelope, trust_registry_path=registry, trust_registry_sha256=pin,
                selected=("B01",), now=utc_now())
            assert any("differs from canonical" in issue for issue in issues)

    @register("offline GitHub evidence has zero future-time tolerance")
    def _offline_github_future() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            envelope, registry, pin = signed_github_fixture(pathlib.Path(tmp))
            verifier_now = utc_now()
            envelope["payload"]["emitted_at_us"] = str(
                int(verifier_now.timestamp() * 1_000_000) + 1)
            issues, _ = verify_offline_github_envelope(
                envelope, trust_registry_path=registry, trust_registry_sha256=pin,
                selected=("B01",), now=verifier_now)
            assert any(
                "future" in issue and "zero future tolerance" in issue for issue in issues
            ), issues

    @register("malformed offline GitHub snapshot structure fails closed without exception")
    def _malformed_github_snapshot() -> None:
        data = github_fixture()
        data["milestones"]["B01"]["source_candidate_numbers"] = None
        data["milestones"]["B01"]["receipt"] = ["not", "an", "object"]
        data["governance"] = None
        issues = github_snapshot_structure_issues(data, ("B01",))
        assert any("positive-integer array" in issue for issue in issues), issues
        assert any("object or null" in issue for issue in issues), issues
        assert any("governance is not an object" in issue for issue in issues), issues
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            snapshot = root / "malformed-snapshot.json"
            snapshot.write_text(json.dumps(data), encoding="utf-8")
            output = root / "reports"
            args = build_parser().parse_args([
                "--mode", "github", "--github-snapshot", str(snapshot),
                "--workflow-sha256", "f" * 64,
                "--receipt-profile-decision-sha256", "e" * 64,
                "--milestones", "B01", "--output", str(output),
            ])
            runner = AuditRunner(args)
            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = runner.execute()
            runner.cleanup()
            assert exit_code == EXIT_INTERNAL
            report = strict_json_loads((output / "report.json").read_text(encoding="utf-8"))
            assert report["overall"]["status"] == "RUNNER_ERROR", report["overall"]
            suite = ET.parse(output / "junit.xml").getroot()
            assert suite.attrib["errors"] == "1"

    @register("clean GitHub fixture passes")
    def _github_clean() -> None:
        failures, incomplete = github_milestone_gate_issues(
            github_fixture(), "B01", expected_subject_sha="3" * 40)
        assert not failures and not incomplete, (failures, incomplete)

    @register("merge proof distinguishes ancestor, exact-tree squash, unrelated, and unavailable")
    def _merge_proof_classes() -> None:
        head_sha, merge_sha = "1" * 40, "3" * 40
        ancestor = classify_source_merge_proof(
            compare_status="ahead", head_sha=head_sha, merge_sha=merge_sha)
        assert ancestor["kind"] == "ANCESTOR" and ancestor["verified"] is True
        squash = classify_source_merge_proof(
            compare_status="diverged", head_sha=head_sha, merge_sha=merge_sha,
            base_sha="2" * 40,
            head_commit={"tree": {"sha": "a" * 40}},
            merge_commit={"tree": {"sha": "a" * 40}, "parents": [{"sha": "2" * 40}]},
        )
        assert squash["kind"] == "EXACT_TREE_SQUASH" and squash["verified"] is True
        wrong_base = classify_source_merge_proof(
            compare_status="diverged", head_sha=head_sha, merge_sha=merge_sha,
            base_sha="2" * 40,
            head_commit={"tree": {"sha": "a" * 40}},
            merge_commit={"tree": {"sha": "a" * 40}, "parents": [{"sha": "4" * 40}]},
        )
        assert wrong_base["kind"] == UNAVAILABLE and wrong_base["verified"] is False
        data = github_fixture()
        data["milestones"]["B01"]["source"]["merge_proof"] = squash
        failures, incomplete = github_milestone_gate_issues(data, "B01")
        assert not failures and not incomplete, (failures, incomplete)

        unrelated = classify_source_merge_proof(
            compare_status="diverged", head_sha=head_sha, merge_sha=merge_sha,
            base_sha="2" * 40,
            head_commit={"tree": {"sha": "a" * 40}},
            merge_commit={"tree": {"sha": "b" * 40}, "parents": [{"sha": "2" * 40}]},
        )
        assert unrelated["kind"] == "UNRELATED" and unrelated["verified"] is False
        data["milestones"]["B01"]["source"]["merge_proof"] = unrelated
        failures, _ = github_milestone_gate_issues(data, "B01")
        assert any("neither reviewed-head ancestry nor exact-tree squash" in issue for issue in failures)

        source = data["milestones"]["B01"]["source"]
        source.pop("merge_proof")
        source["merge_contains_head"] = False
        failures, incomplete = github_milestone_gate_issues(data, "B01")
        assert not any("reviewed-head ancestry" in issue for issue in failures), failures
        assert any("exact-tree squash proof is unavailable" in issue for issue in incomplete), incomplete

    @register("legacy merge_contains_head true cannot replace structured merge proof")
    def _legacy_merge_boolean_fails_closed() -> None:
        data = github_fixture()
        source = data["milestones"]["B01"]["source"]
        source.pop("merge_proof")
        source["merge_contains_head"] = True
        failures, incomplete = github_milestone_gate_issues(data, "B01")
        assert not failures, failures
        assert any(
            "legacy merge_contains_head=true cannot replace a structured merge proof" in issue
            for issue in incomplete
        ), incomplete

    @register("issue #5 and detailed governance controls fail closed")
    def _governance_issue_and_controls() -> None:
        assert normalize_default_branch_controls(
            [{
                "id": 101, "enforcement": "active", "target": "branch",
                "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
                "rules": [
                    {"type": "pull_request", "parameters": {
                        "required_approving_review_count": 1,
                        "required_review_thread_resolution": True,
                        "dismiss_stale_reviews_on_push": True,
                    }},
                    {"type": "required_status_checks", "parameters": {
                        "required_status_checks": [{"context": "ci / required"}],
                        "strict_required_status_checks_policy": True,
                    }},
                ],
            }],
            "main",
        ) is not None
        assert normalize_default_branch_controls(
            [{"id": 101, "enforcement": "active", "target": "branch"}], "main") is None
        data = github_fixture()
        data["issue_5"]["state"] = "open"
        failures, _ = github_milestone_gate_issues(data, "B01")
        assert any("issue #5 remains open" in issue for issue in failures), failures

        data = github_fixture()
        data["governance"]["default_branch_controls"] = None
        data["governance"]["branch_protection_enforced"] = True
        failures, incomplete = github_milestone_gate_issues(data, "B01")
        assert not failures, failures
        assert any("active ruleset summaries are insufficient" in issue for issue in incomplete), incomplete

        data = github_fixture()
        data["issue_5"] = {"unavailable": "provider denied"}
        failures, incomplete = github_milestone_gate_issues(data, "B01")
        assert not failures, failures
        assert any("issue #5 state is unavailable" in issue for issue in incomplete), incomplete

        now = utc_now()
        now_us = int(now.timestamp() * 1_000_000)
        data = github_fixture()
        data["issue_5"]["state"] = "open"
        data["producer"] = "auditor-a"
        data["reviewed_by"] = ["auditor-b"]
        procedure = {
            "schema": "triad.github.exact_equivalent_control_procedure.v1",
            "repository": EXPECTED_REPOSITORY, "issue_number": 5, "branch": "main",
            "commit_range": {"start_sha": "2" * 40, "end_sha": "1" * 40},
            "approver": "auditor-b", "abort_path": "stop and invalidate the merge",
            "required_status_checks": ["ci / required"],
            "final_head_review_required": True,
            "resolved_conversations_required": True,
            "stale_head_rejection_required": True,
            "bypass_allowed": False,
            "negative_early_merge_test_sha256": "c" * 64,
            "negative_bypass_test_sha256": "d" * 64,
            "valid_from_us": str(now_us - 1_000_000),
            "expires_at_us": str(now_us + 3_600_000_000),
            "signer_identities": ["auditor-a", "auditor-b"],
        }
        procedure["procedure_sha256"] = sha256_bytes(jcs_canonical_bytes(procedure))
        data["governance"].update({
            "signed_waiver_verified": True,
            "waiver_evidence": procedure,
            "default_branch_controls": None,
        })
        failures, incomplete = github_milestone_gate_issues(data, "B01", now=now)
        assert not failures and not incomplete, (failures, incomplete)

    @register("exact-equivalent governance procedure cannot waive an actual bypass")
    def _exact_procedure_cannot_waive_bypass() -> None:
        now = utc_now()
        now_us = int(now.timestamp() * 1_000_000)
        data = github_fixture()
        data["issue_5"]["state"] = "open"
        data["producer"] = "auditor-a"
        data["reviewed_by"] = ["auditor-b"]
        procedure = {
            "schema": "triad.github.exact_equivalent_control_procedure.v1",
            "repository": EXPECTED_REPOSITORY, "issue_number": 5, "branch": "main",
            "commit_range": {"start_sha": "2" * 40, "end_sha": "1" * 40},
            "approver": "auditor-b", "abort_path": "stop and invalidate the merge",
            "required_status_checks": ["ci / required"],
            "final_head_review_required": True,
            "resolved_conversations_required": True,
            "stale_head_rejection_required": True,
            "bypass_allowed": False,
            "negative_early_merge_test_sha256": "c" * 64,
            "negative_bypass_test_sha256": "d" * 64,
            "valid_from_us": str(now_us - 1_000_000),
            "expires_at_us": str(now_us + 3_600_000_000),
            "signer_identities": ["auditor-a", "auditor-b"],
        }
        procedure["procedure_sha256"] = sha256_bytes(jcs_canonical_bytes(procedure))
        data["governance"].update({
            "signed_waiver_verified": True,
            "waiver_evidence": procedure,
            "default_branch_controls": None,
            "bypass_used": True,
        })
        failures, incomplete = github_milestone_gate_issues(data, "B01", now=now)
        assert any("does not authorize bypass" in issue for issue in failures), failures
        assert not incomplete, incomplete

    @register("skipped CI authentication/required step fails")
    def _github_skipped() -> None:
        data = github_fixture()
        data["milestones"]["B01"]["receipt"]["workflow_runs"][0]["jobs"][0]["steps"][2]["conclusion"] = "skipped"
        failures, _ = github_milestone_gate_issues(data, "B01")
        assert any("skipped/failed" in issue for issue in failures)

    @register("CI completing after merge fails chronology")
    def _github_ci_after_merge() -> None:
        data = github_fixture()
        source = data["milestones"]["B01"]["source"]
        merged = parse_iso(source["pr"]["merged_at"])
        source["workflow_runs"][0]["updated_at"] = iso_z(merged + dt.timedelta(seconds=1))
        failures, _ = github_milestone_gate_issues(data, "B01")
        assert any("before merge" in issue for issue in failures)

    @register("review after merge fails")
    def _review_after() -> None:
        data = github_fixture()
        source = data["milestones"]["B01"]["source"]
        merged = parse_iso(source["pr"]["merged_at"])
        source["reviews"][0]["submitted_at"] = iso_z(merged + dt.timedelta(seconds=1))
        failures, _ = github_milestone_gate_issues(data, "B01")
        assert any("at/after" in issue for issue in failures)

    @register("unresolved P1 fails")
    def _unresolved() -> None:
        data = github_fixture()
        data["milestones"]["B01"]["source"]["review_threads"] = [
            {"isResolved": False, "comments": {"nodes": [{"body": "P1 durable failure"}]}}]
        failures, _ = github_milestone_gate_issues(data, "B01")
        assert any("unresolved" in issue for issue in failures)

    @register("same-PR source and receipt fails")
    def _same_pr() -> None:
        data = github_fixture()
        data["milestones"]["B01"]["receipt"]["pr"]["number"] = 1
        failures, _ = github_milestone_gate_issues(data, "B01")
        assert any("same PR" in issue for issue in failures)

    @register("invalid base/head chronology fails")
    def _invalid_base_head() -> None:
        data = github_fixture()
        source_pr = data["milestones"]["B01"]["source"]["pr"]
        source_pr["base"]["sha"] = source_pr["head"]["sha"]
        failures, _ = github_milestone_gate_issues(data, "B01")
        assert any("base and head" in issue for issue in failures)

    @register("missing predecessor receipt is explicitly unavailable")
    def _missing_predecessor() -> None:
        data = github_fixture()
        data["milestones"]["B02"] = data["milestones"].pop("B01")
        failures, incomplete = github_predecessor_chronology_issues(data, "B02")
        assert not failures and any("predecessor B01" in issue for issue in incomplete)

    @register("next source before predecessor receipt fails")
    def _next_before_predecessor() -> None:
        data = github_fixture()
        data["milestones"]["B02"] = json.loads(json.dumps(data["milestones"]["B01"]))
        predecessor_merge = parse_iso(data["milestones"]["B01"]["receipt"]["pr"]["merged_at"])
        data["milestones"]["B02"]["source"]["pr"]["created_at"] = iso_z(
            predecessor_merge - dt.timedelta(seconds=1))
        failures, _ = github_predecessor_chronology_issues(data, "B02")
        assert any("before predecessor" in issue for issue in failures)

    @register("approval before last code commit fails")
    def _review_before_last_commit() -> None:
        data = github_fixture()
        source = data["milestones"]["B01"]["source"]
        last_commit = github_commit_time(source["commits"][0])
        source["reviews"][0]["submitted_at"] = iso_z(last_commit - dt.timedelta(seconds=1))
        failures, _ = github_milestone_gate_issues(data, "B01")
        assert any("predates the last code commit" in issue for issue in failures)

    @register("receipt PR before source merge fails")
    def _receipt_before_source_merge() -> None:
        data = github_fixture()
        source_merge = parse_iso(data["milestones"]["B01"]["source"]["pr"]["merged_at"])
        data["milestones"]["B01"]["receipt"]["pr"]["created_at"] = iso_z(
            source_merge - dt.timedelta(seconds=1))
        failures, _ = github_milestone_gate_issues(data, "B01")
        assert any("not created after" in issue for issue in failures)

    @register("receipt-to-source GitHub identity mismatch fails")
    def _receipt_identity_mismatch() -> None:
        data = github_fixture()
        payload = {
            "build_commit": "9" * 40, "merge_commit": "9" * 40,
            "source_pr": 99, "receipt_pr": 98,
            "source_merge_at_us": "0",
        }
        failures, _ = github_milestone_gate_issues(
            data, "B01", local_receipt_payload=payload)
        assert any("does not equal" in issue or "disagrees" in issue for issue in failures)

    @register("dirty checkout fixture is detected")
    def _dirty_checkout() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp)
            init = subprocess.run(["git", "init", "--quiet", str(repo)], check=False)
            assert init.returncode == 0
            tracked = repo / "tracked.txt"
            tracked.write_text("clean\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
            subprocess.run([
                "git", "-C", str(repo), "-c", "user.name=fixture", "-c",
                "user.email=fixture@example.invalid", "commit", "--quiet", "-m", "fixture",
            ], check=True)
            tracked.write_text("dirty\n", encoding="utf-8")
            status = run_git(repo, "status", "--porcelain=v1", "--untracked-files=all")
            assert status.returncode == 0 and status.stdout.strip()

    @register("mandatory commands execute in independent exact-head clones")
    def _independent_command_clone() -> None:
        global REQUIRED_LOCAL_COMMANDS
        original_commands = REQUIRED_LOCAL_COMMANDS
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            repo = root / "repo"
            subprocess.run(["git", "init", "--quiet", str(repo)], check=True)
            (repo / "tracked.txt").write_text("fixture\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
            subprocess.run([
                "git", "-C", str(repo), "-c", "user.name=fixture", "-c",
                "user.email=fixture@example.invalid", "commit", "--quiet", "-m", "fixture",
            ], check=True)
            subject_sha = run_git(repo, "rev-parse", "HEAD").stdout.strip()
            probe = (
                "import subprocess,sys; "
                "common=subprocess.check_output(['git','rev-parse','--git-common-dir'],text=True).strip(); "
                "sys.exit(0 if common=='.git' else 9)"
            )
            REQUIRED_LOCAL_COMMANDS = (
                ("independent_clone_probe", ("{python}", "-c", probe), 10),
            )
            args = build_parser().parse_args([
                "--mode", "local", "--repo", str(repo),
                "--expected-head", subject_sha, "--allow-repo-code-execution",
                "--receipt-profile-decision-sha256", "e" * 64,
            ])
            runner = AuditRunner(args)
            runner.subject_repo = repo
            runner.subject_sha = subject_sha
            runner.tempdir = tempfile.TemporaryDirectory(prefix="triad-clone-fixture-")
            try:
                issues = runner.run_local_commands()
                assert not issues, issues
                assert len(runner.commands) == 1 and runner.commands[0].exit_code == 0
            finally:
                runner.cleanup()
                REQUIRED_LOCAL_COMMANDS = original_commands

    @register("local remote repository identity normalizes exactly")
    def _remote_identity() -> None:
        assert normalize_git_repository("git@github.com:TriadAgentic/TriadOrigin.git") == "triadagentic/triadorigin"
        assert normalize_git_repository("https://github.com/TriadAgentic/Other.git") != "triadagentic/triadorigin"

    @register("local mode requires external head pin and explicit repository-code execution consent")
    def _local_execution_consent() -> None:
        base = ["--mode", "local", "--repo", "/fixture/repo"]
        missing_head = build_parser().parse_args(base + ["--allow-repo-code-execution"])
        try:
            validate_args(missing_head)
        except ValueError as exc:
            assert "--expected-head" in str(exc)
        else:
            raise AssertionError("local mode accepted a self-selected HEAD")

        missing_consent = build_parser().parse_args(base + ["--expected-head", "a" * 40])
        try:
            validate_args(missing_consent)
        except ValueError as exc:
            assert "--allow-repo-code-execution" in str(exc)
        else:
            raise AssertionError("local mode accepted repository code execution without consent")

        complete = build_parser().parse_args(
            base + [
                "--expected-head", "a" * 40,
                "--allow-repo-code-execution",
                "--receipt-profile-decision-sha256", "e" * 64,
            ])
        validate_args(complete)

        malformed_profile = build_parser().parse_args(
            base + [
                "--expected-head", "a" * 40,
                "--allow-repo-code-execution",
                "--receipt-profile-decision-sha256", "0" * 64,
            ])
        try:
            validate_args(malformed_profile)
        except ValueError as exc:
            assert "receipt-profile-decision" in str(exc)
        else:
            raise AssertionError("all-zero receipt-profile decision pin was accepted")

    @register("explicit source/receipt PR selectors reject ambiguity")
    def _pr_selectors() -> None:
        assert parse_pr_selections(["B05=20"]) == {"B05": 20}
        for values in (["B05=20", "B05=21"], ["B01=0"], ["B11=1"], ["B01=-1"]):
            try:
                parse_pr_selections(values)
            except ValueError:
                pass
            else:
                raise AssertionError(f"invalid/ambiguous selector was accepted: {values}")

    @register("receipt PR classifier recognizes underscore branch names")
    def _receipt_classifier() -> None:
        assert pull_is_receipt({"title": "B05 evidence", "head": {"ref": "b05_receipt"}})
        assert pull_is_receipt({"title": "B10 terminal evidence", "head": {"ref": "audit"}})
        assert not pull_is_receipt({"title": "B05 source implementation", "head": {"ref": "b05_source"}})

    @register("duplicate embedded check ID is rejected")
    def _duplicate_check() -> None:
        rows = list(POLICY)
        try:
            validate_policy_rows(rows + [rows[0]])
        except ValueError as exc:
            assert "duplicate" in str(exc)
        else:
            raise AssertionError("duplicate policy check ID was accepted")

    @register("tampered evidence manifest preimage fails")
    def _tampered_manifest() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            artifact = root / "report.txt"
            artifact.write_text("original\n", encoding="utf-8")
            manifest = root / "evidence_manifest.json"
            write_json(manifest, {
                "schema": EVIDENCE_SCHEMA,
                "artifacts": [{
                    "path": "report.txt", "sha256": sha256_file(artifact),
                    "bytes": artifact.stat().st_size, "source_uri": "audit://fixture/report.txt",
                    "source_kind": "DERIVED_REPORT", "check_ids": ["B01.ENTRY"],
                }],
            })
            assert not verify_evidence_manifest(root, manifest)
            artifact.write_text("tampered\n", encoding="utf-8")
            assert any("digest mismatch" in issue for issue in verify_evidence_manifest(root, manifest))

    @register("full report bundle emits HTML, manifest, ZIP, and no token")
    def _report_bundle() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = pathlib.Path(tmp) / "reports"
            runner = AuditRunner(fixture_runner_args(output))
            for row in runner.results.values():
                row.set_outcome(PASS, actual="fixture")
            runner.add_finding(
                "P2", "B01", "B01.ENTRY", "redaction fixture",
                "gh" + "p_" + "abcdefghijklmnopqrstuvwxyz123456", remediation="fixture")
            score = runner.score()
            with contextlib.redirect_stdout(io.StringIO()):
                runner.write_reports(score, EXIT_PASS)
            assert (output / "DETAILED_REPORT.html").is_file()
            assert not verify_evidence_manifest(output, output / "evidence_manifest.json")
            assert not report_secret_issues(output)
            archives = list(output.glob("*.zip"))
            assert len(archives) == 1
            with zipfile.ZipFile(archives[0]) as archive:
                assert "report.json" in archive.namelist()

    @register("runner tool error overrides all-PASS scoring and exit")
    def _tool_error_dominates() -> None:
        runner = AuditRunner(fixture_runner_args())
        for row in runner.results.values():
            row.set_outcome(PASS, actual="fixture")
        runner.tool_error = "fixture internal failure"
        score = runner.score()
        assert score["status"] == "RUNNER_ERROR", score
        assert score["hard_gate_result"] == BLOCKED, score
        assert score["repository_safe_hold_eligible"] is False, score
        assert runner.determine_exit(score) == EXIT_INTERNAL

    @register("JUnit renders incomplete hard gates as failures and tool errors as errors")
    def _junit_fail_closed() -> None:
        runner = AuditRunner(fixture_runner_args())
        hard_count = 0
        for row in runner.results.values():
            if row.hard_gate:
                hard_count += 1
                row.set_outcome(BLOCKED, actual="fixture evidence unavailable")
            else:
                row.set_outcome(PASS, actual="fixture")
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            first = root / "junit-incomplete.xml"
            runner.write_junit(first)
            suite = ET.parse(first).getroot()
            assert int(suite.attrib["failures"]) == hard_count
            assert len(suite.findall("./testcase/failure")) == hard_count
            runner.tool_error = "fixture runner error"
            second = root / "junit-tool-error.xml"
            runner.write_junit(second)
            suite = ET.parse(second).getroot()
            assert suite.attrib["errors"] == "1"
            assert suite.find("./testcase[@name='RUNNER.INTERNAL']/error") is not None
            runner.tool_error = None
            runner.receipt_profile_decision_sha256 = None
            third = root / "junit-profile-pin.xml"
            runner.write_junit(third)
            suite = ET.parse(third).getroot()
            assert int(suite.attrib["failures"]) == hard_count + 1
            assert suite.find(
                "./testcase[@name='RECEIPT_PROFILE_DECISION_PIN']/failure") is not None

    @register("PARTIAL, BLOCKED, and UNAVAILABLE hard checks earn zero")
    def _incomplete_zero() -> None:
        template = next(row for row in POLICY if row.check_id == "B01.ENTRY")
        for outcome in (PARTIAL, BLOCKED, UNAVAILABLE):
            row = CheckResult(**dataclasses.asdict(template))
            row.set_outcome(outcome, actual="fixture")
            assert row.points == 0 and outcome in INCOMPLETE_OUTCOMES

    @register("work-order policy source IDs remain synchronized")
    def _document_sync() -> None:
        assert not validate_policy_document_sync(pathlib.Path(__file__).resolve().parent)

    @register("spec/control count command output is exact")
    def _spec_counts() -> None:
        value = json.dumps({
            "schema": "triad.origin.spec_control_counts.v1",
            "rc1_test_count": EXPECTED_RC1_TEST_COUNT,
            "rc3_effective_verification_count": EXPECTED_EFFECTIVE_COUNTS["effective_verification_count"],
            "rc4_fixture_count": EXPECTED_RC4_FIXTURE_COUNT,
        })
        assert not spec_control_count_output_issues(value)
        wrong = json.loads(value)
        wrong["rc4_fixture_count"] -= 1
        assert spec_control_count_output_issues(json.dumps(wrong))

    @register("mandatory command timeout is observable")
    def _timeout() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record, _, _ = execute_bounded_command(
                "timeout-fixture", [sys.executable, "-c", "import time; time.sleep(1)"],
                pathlib.Path(tmp), 0.05, 10000)
            assert record.timed_out and record.exit_code is None

    @register("timed-out command kills its surviving grandchild process group")
    def _grandchild_kill() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            started = root / "grandchild-started"
            survived = root / "grandchild-survived"
            child_code = (
                "import pathlib,signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); "
                f"pathlib.Path({str(started)!r}).write_text('started'); "
                "time.sleep(1.5); "
                f"pathlib.Path({str(survived)!r}).write_text('survived')"
            )
            parent_code = (
                "import pathlib,subprocess,sys,time; "
                f"subprocess.Popen([sys.executable,'-c',{child_code!r}]); "
                f"marker=pathlib.Path({str(started)!r}); "
                "deadline=time.time()+1; "
                "\nwhile not marker.exists() and time.time()<deadline: time.sleep(.01)\n"
                "time.sleep(5)"
            )
            record, _, _ = execute_bounded_command(
                "grandchild-timeout-fixture", [sys.executable, "-c", parent_code],
                root, 0.8, 10000)
            assert record.timed_out
            if os.name == "posix":
                assert started.is_file(), "fixture grandchild did not start"
                time.sleep(1.0)
                assert not survived.exists(), "timed-out grandchild survived process-group cleanup"

    @register("completed command kills a TERM-ignoring background grandchild")
    def _completed_grandchild_kill() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            started = root / "background-started"
            survived = root / "background-survived"
            child_code = (
                "import pathlib,signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); "
                f"pathlib.Path({str(started)!r}).write_text('started'); "
                "time.sleep(0.8); "
                f"pathlib.Path({str(survived)!r}).write_text('survived')"
            )
            parent_code = (
                "import pathlib,subprocess,sys,time; "
                f"subprocess.Popen([sys.executable,'-c',{child_code!r}]); "
                f"marker=pathlib.Path({str(started)!r}); "
                "deadline=time.time()+1; "
                "\nwhile not marker.exists() and time.time()<deadline: time.sleep(.01)\n"
            )
            record, _, _ = execute_bounded_command(
                "background-grandchild-fixture", [sys.executable, "-c", parent_code],
                root, 3, 10000)
            assert record.exit_code == 0 and not record.timed_out
            if os.name == "posix":
                assert started.is_file(), "fixture background grandchild did not start"
                time.sleep(0.9)
                assert not survived.exists(), "background grandchild survived completed command cleanup"

    @register("command output is bounded while raw digest covers full bytes")
    def _bounded_output() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw = b"x" * 5000 + b"\n"
            record, stdout, _ = execute_bounded_command(
                "output-fixture", [sys.executable, "-c", "print('x' * 5000)"],
                pathlib.Path(tmp), 5, 1024)
            assert record.exit_code == 0 and record.truncated and len(stdout.encode()) == 1024
            assert record.stdout_raw_sha256 == sha256_bytes(raw)

    @register("hard-gate failure dominates a high score")
    def _dominance() -> None:
        rows = [CheckResult(**dataclasses.asdict(row)) for row in POLICY if row.milestone == "B01"]
        for row in rows:
            row.set_outcome(PASS, actual="fixture")
        rows[0].set_outcome(FAIL, actual="fixture hard fail")
        completion = sum(row.points for row in rows)
        assert completion >= 80
        assert any(row.hard_gate and row.outcome == FAIL for row in rows)

    passed = 0
    failures: list[str] = []
    for name, func in tests:
        try:
            func()
            passed += 1
            print(f"PASS: {name}")
        except Exception as exc:
            failures.append(f"{name}: {exc}")
            print(f"FAIL: {name}: {exc}", file=sys.stderr)
    print(f"Self-test: {passed}/{len(tests)} passed")
    if failures:
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only B01-B10 audit/scoring runner; a high score never overrides a hard gate.")
    parser.add_argument("--mode", choices=("local", "github", "full"), default="local")
    parser.add_argument("--repo", help="local Git checkout to audit (required for local/full)")
    parser.add_argument(
        "--allow-repo-code-execution", action="store_true",
        help=(
            "explicitly authorize local/full mode to execute the audited repository's bounded "
            "verification commands"),
    )
    parser.add_argument("--repo-full-name", help="GitHub owner/name (required for live github/full)")
    parser.add_argument(
        "--pr", type=int,
        help="exact subject pull request number for GitHub evidence (required in full mode)")
    parser.add_argument(
        "--source-pr", action="append", default=[], metavar="B01=N",
        help="explicit active source PR selection; repeat for correction chains")
    parser.add_argument(
        "--receipt-pr", action="append", default=[], metavar="B01=N",
        help="explicit active detached-receipt PR selection; repeat for correction chains")
    parser.add_argument(
        "--github-snapshot",
        help="offline normalized GitHub JSON; unsigned input remains UNAVAILABLE, PASS requires pinned two-signature DSSE",
    )
    parser.add_argument("--runtime-evidence", help="optional sanitized/imported runtime evidence JSON; never promotes Track A")
    parser.add_argument("--terminal-receipt", help="detached B10 receipt JSON outside audited main")
    parser.add_argument("--terminal-evidence-root", help="root containing B10 receipt evidence preimages")
    parser.add_argument("--terminal-receipt-commit", help="direct-child Git commit containing detached B10 receipt")
    parser.add_argument(
        "--terminal-receipt-git-path", default="evidence/terminal/B10.json",
        help="receipt path inside --terminal-receipt-commit")
    parser.add_argument("--terminal-tag", help="verified signed tag naming --terminal-receipt-commit")
    parser.add_argument("--check-evidence", help="relative/absolute authenticated work-package evidence index")
    parser.add_argument("--trust-registry", help="externally approved receipt signer registry (relative to repo or absolute)")
    parser.add_argument(
        "--trust-registry-sha256",
        help="external lowercase SHA-256 pin for --trust-registry (or TRIAD_RECEIPT_TRUST_REGISTRY_SHA256)",
    )
    parser.add_argument(
        "--receipt-profile-decision-sha256",
        help=(
            "external lowercase SHA-256 pin for ratified DECISION-RECEIPT-PROFILE-001 "
            "(or TRIAD_RECEIPT_PROFILE_DECISION_SHA256); receipts cannot PASS without it"),
    )
    parser.add_argument(
        "--workflow-sha256",
        help="external SHA-256 pin for the trusted .github/workflows/ci.yml bytes")
    parser.add_argument(
        "--expected-head",
        help="external exact 40-hex subject SHA pin (required for local/full; optional in github)",
    )
    parser.add_argument("--milestones", default="B01-B10", help="B01-B10, ALL, or comma-separated B01..B10")
    parser.add_argument("--output", help="new/empty report directory outside audited repo")
    parser.add_argument("--timeout", type=int, default=900, help="maximum seconds per mandatory command (default 900)")
    parser.add_argument("--max-log-bytes", type=int, default=2_000_000, help="maximum stored bytes per stdout/stderr")
    parser.add_argument("--self-test", action="store_true", help="run built-in false-green/leakage fixtures and exit")
    parser.add_argument("--version", action="version", version=f"%(prog)s {TOOL_VERSION}")
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if args.expected_head and not is_hex_sha(args.expected_head, 40):
        raise ValueError("--expected-head must be exactly 40 lowercase hex characters")
    if args.terminal_receipt_commit and not is_hex_sha(args.terminal_receipt_commit, 40):
        raise ValueError("--terminal-receipt-commit must be exactly 40 lowercase hex characters")
    if args.timeout <= 0:
        raise ValueError("--timeout must be positive")
    if args.max_log_bytes < 1024:
        raise ValueError("--max-log-bytes must be at least 1024")
    if args.pr is not None and args.pr <= 0:
        raise ValueError("--pr must be a positive integer")
    if args.repo_full_name and not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repo_full_name):
        raise ValueError("--repo-full-name must be exactly owner/name")
    selected = set(parse_milestones(args.milestones))
    for label, values in (("--source-pr", args.source_pr), ("--receipt-pr", args.receipt_pr)):
        mapping = parse_pr_selections(values)
        extra = set(mapping) - selected
        if extra:
            raise ValueError(f"{label} selects milestones outside --milestones: {sorted(extra)}")
    registry_pin = args.trust_registry_sha256 or os.environ.get("TRIAD_RECEIPT_TRUST_REGISTRY_SHA256")
    if registry_pin and not is_nonzero_sha256(registry_pin):
        raise ValueError("--trust-registry-sha256 must be a non-zero lowercase SHA-256")
    profile_pin = (
        args.receipt_profile_decision_sha256
        or os.environ.get("TRIAD_RECEIPT_PROFILE_DECISION_SHA256")
    )
    if profile_pin and not is_nonzero_sha256(profile_pin):
        raise ValueError(
            "--receipt-profile-decision-sha256 must be a non-zero lowercase SHA-256")
    if args.workflow_sha256 and not is_nonzero_sha256(args.workflow_sha256):
        raise ValueError("--workflow-sha256 must be a non-zero lowercase SHA-256")
    if args.mode in {"github", "full"} and not args.workflow_sha256:
        raise ValueError("--workflow-sha256 is required in github/full mode")
    if args.mode in {"local", "full"} and not args.repo:
        raise ValueError("--repo is required for local/full mode")
    if args.mode in {"local", "full"} and not args.expected_head:
        raise ValueError("--expected-head is required in local/full mode as an external subject pin")
    if args.mode in {"local", "full"} and not args.allow_repo_code_execution:
        raise ValueError(
            "--allow-repo-code-execution is required in local/full mode because mandatory "
            "verification commands execute audited repository code")
    if args.mode == "full" and not args.repo_full_name:
        raise ValueError("--repo-full-name is required in full mode to bind local and GitHub identity")
    if args.mode == "full" and args.pr is None:
        raise ValueError("--pr is required in full mode to bind the local head to one exact GitHub PR")
    if args.mode in {"github", "full"} and not args.github_snapshot and not args.repo_full_name:
        raise ValueError("github/full mode requires --repo-full-name, or --github-snapshot")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.self_test:
        return run_self_tests()
    try:
        validate_args(args)
    except ValueError as exc:
        parser.error(str(exc))
        return EXIT_USAGE
    runner = AuditRunner(args)
    try:
        return runner.execute()
    finally:
        runner.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
