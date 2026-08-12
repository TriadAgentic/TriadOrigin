#!/usr/bin/env python3
"""Capture-profile verifier for the B00R generation-2 clean-runner bundle.

The receipt manifest is a content-addressed inventory, not proof that its files mean what their
roles claim.  This module supplies the missing semantic layer.  It binds a closed clean-runner
namespace to the exact source merge, requires the complete command set with raw streams and return
codes, and derives every PASS claim from committed evidence rather than summary booleans.

``validate_bundle`` is intentionally independent of receipt signatures and provider access.  The
strict receipt validator must call it *after* generic manifest validation; receipt-PR CI can call
the CLI earlier so absent owner pins cannot hide malformed deterministic evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import tomllib
from typing import Any


class CleanRunnerError(ValueError):
    """The clean-runner evidence is malformed, contradictory, or not Git-bound."""


REPOSITORY = "TriadAgentic/TriadOrigin"
PROFILE = "TRIAD-B00R-G2-CLEAN-RUNNER-V1"
EVIDENCE_ROOT = "evidence/B00R_G2/clean_runner"

RUN_PATH = f"{EVIDENCE_ROOT}/run.v1.json"
SOURCE_IDENTITY_PATH = f"{EVIDENCE_ROOT}/source/source_identity.v1.json"
SOURCE_TREE_PATH = f"{EVIDENCE_ROOT}/source/ls-tree.bin"
SOURCE_WORKFLOW_PATH = f"{EVIDENCE_ROOT}/source/ci.yml"
CONTRACT_MANIFEST_PATH = f"{EVIDENCE_ROOT}/source/contracts.MANIFEST.sha256"
RUNNER_FACTS_PATH = f"{EVIDENCE_ROOT}/runner/runner_facts.v1.json"
PACKAGE_SNAPSHOT_PATH = f"{EVIDENCE_ROOT}/runner/installed_packages.v1.json"
TEST_MANIFEST_PATH = f"{EVIDENCE_ROOT}/tests/test_manifest.v1.json"
TEST_IDS_PATHS = {
    "0": f"{EVIDENCE_ROOT}/tests/test_ids.seed0.txt",
    "1": f"{EVIDENCE_ROOT}/tests/test_ids.seed1.txt",
}
PYTEST_RESULT_PATHS = {
    "0": f"{EVIDENCE_ROOT}/tests/pytest.seed0.v1.json",
    "1": f"{EVIDENCE_ROOT}/tests/pytest.seed1.v1.json",
}
CONFIG_BUNDLE_PATH = f"{EVIDENCE_ROOT}/config/config_bundle.v1.json"
ROLLBACK_PROOF_PATH = f"{EVIDENCE_ROOT}/rollback/rollback_proof.v1.json"
ROLLBACK_STDOUT_PATH = f"{EVIDENCE_ROOT}/rollback/stdout.bin"
ROLLBACK_STDERR_PATH = f"{EVIDENCE_ROOT}/rollback/stderr.bin"
ROLLBACK_RC_PATH = f"{EVIDENCE_ROOT}/rollback/rc.txt"

ROLE_PATHS = {
    "WORKFLOW": SOURCE_WORKFLOW_PATH,
    "CONTRACT_MANIFEST": CONTRACT_MANIFEST_PATH,
    "TEST_MANIFEST": TEST_MANIFEST_PATH,
    "CONFIG_BUNDLE": CONFIG_BUNDLE_PATH,
    "ROLLBACK_PROOF": ROLLBACK_PROOF_PATH,
}

FIXED_FILE_ROLES = {
    RUN_PATH: "CLEAN_RUNNER_RUN",
    SOURCE_IDENTITY_PATH: "CLEAN_RUNNER_SOURCE_IDENTITY",
    SOURCE_TREE_PATH: "CLEAN_RUNNER_SOURCE_TREE",
    SOURCE_WORKFLOW_PATH: "WORKFLOW",
    CONTRACT_MANIFEST_PATH: "CONTRACT_MANIFEST",
    RUNNER_FACTS_PATH: "CLEAN_RUNNER_FACTS",
    PACKAGE_SNAPSHOT_PATH: "CLEAN_RUNNER_PACKAGE_SNAPSHOT",
    TEST_MANIFEST_PATH: "TEST_MANIFEST",
    TEST_IDS_PATHS["0"]: "CLEAN_RUNNER_TEST_IDS_SEED0",
    TEST_IDS_PATHS["1"]: "CLEAN_RUNNER_TEST_IDS_SEED1",
    PYTEST_RESULT_PATHS["0"]: "CLEAN_RUNNER_PYTEST_RESULT_SEED0",
    PYTEST_RESULT_PATHS["1"]: "CLEAN_RUNNER_PYTEST_RESULT_SEED1",
    CONFIG_BUNDLE_PATH: "CONFIG_BUNDLE",
    ROLLBACK_PROOF_PATH: "ROLLBACK_PROOF",
    ROLLBACK_STDOUT_PATH: "CLEAN_RUNNER_ROLLBACK_STDOUT",
    ROLLBACK_STDERR_PATH: "CLEAN_RUNNER_ROLLBACK_STDERR",
    ROLLBACK_RC_PATH: "CLEAN_RUNNER_ROLLBACK_RC",
}

SAFE_HOLD_LEVERS = {
    "venue_environment": "OFF",
    "venue_activation": "OFF",
    "paper_activation": "OFF",
    "shadow_activation": "LIVE",
}

BASE_ENV = {
    "GIT_CONFIG_COUNT": "3",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_KEY_0": "core.hooksPath",
    "GIT_CONFIG_KEY_1": "core.commitGraph",
    "GIT_CONFIG_KEY_2": "core.multiPackIndex",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "GIT_CONFIG_VALUE_0": "/dev/null",
    "GIT_CONFIG_VALUE_1": "false",
    "GIT_CONFIG_VALUE_2": "false",
    "GIT_NO_REPLACE_OBJECTS": "1",
    "GIT_TERMINAL_PROMPT": "0",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "PIP_CONFIG_FILE": "/dev/null",
    "PIP_DISABLE_PIP_VERSION_CHECK": "1",
    "PIP_NO_COMPILE": "1",
    "PIP_NO_CACHE_DIR": "1",
    "PIP_NO_INPUT": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    "PYTHONSAFEPATH": "1",
    "PYTHONNOUSERSITE": "1",
    "TZ": "UTC",
}

PYTEST_ARGV = [
    "$PYTHON", "-P", "tools/b00r_pytest_inventory.py",
]

REQUIRED_COMMANDS: list[tuple[str, list[str], str]] = [
    ("pytest-seed0", PYTEST_ARGV, "0"),
    ("pytest-seed1", PYTEST_ARGV, "1"),
    ("collect-test-ids", ["$PYTHON", "-P", "tools/collect_test_ids.py"], "0"),
    ("verify-manifest", ["$PYTHON", "-P", "tools/verify_manifest.py"], "0"),
    ("validate-contract-manifest", ["$PYTHON", "-P", "tools/validate_contract_manifest.py"], "0"),
    ("verify-reproducible-build", ["$PYTHON", "-P", "tools/verify_reproducible_build.py"], "0"),
    ("test-wheel-install", ["$PYTHON", "-P", "tools/test_wheel_install.py"], "0"),
    ("verify-no-forbidden-capabilities",
     ["$PYTHON", "-P", "tools/verify_no_forbidden_capabilities.py"], "0"),
    ("e2e-audit", ["$PYTHON", "-P", "tools/e2e_audit.py"], "0"),
    ("build-ledger", ["$PYTHON", "-P", "tools/build_ledger.py", "--verify"], "0"),
    ("validate-combined-dag", ["$PYTHON", "-P", "tools/validate_combined_dag.py"], "0"),
]

ALLOWED_EMPTY_PATHS = frozenset(
    {
        f"{EVIDENCE_ROOT}/commands/{ordinal:02d}-{command_id}/stderr.bin"
        for ordinal, (command_id, _argv, _seed) in enumerate(REQUIRED_COMMANDS)
    }
    | {ROLLBACK_STDOUT_PATH, ROLLBACK_STDERR_PATH}
)


def _expected_clean_runner_paths() -> set[str]:
    paths = set(FIXED_FILE_ROLES)
    for ordinal, (command_id, _argv, _seed) in enumerate(REQUIRED_COMMANDS):
        base = f"{EVIDENCE_ROOT}/commands/{ordinal:02d}-{command_id}"
        paths.update({f"{base}/stdout.bin", f"{base}/stderr.bin", f"{base}/rc.txt"})
    return paths

CONFIG_SOURCE_PATHS = [
    ".github/workflows/ci.yml",
    "constraints/ci.txt",
    "contracts/MANIFEST.sha256",
    "docs/control/b00r_policy.v2.json",
    "docs/control/rc3_effective_bundle_manifest.json",
    "docs/control/rc4_control_bundle.json",
]

_HEX40 = re.compile(r"[0-9a-f]{40}")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_RUN_ID = re.compile(r"[0-9a-f]{32,64}")
_PACKAGE_NAME = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?")
_VERSION = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.!+_-]*[A-Za-z0-9])?")
_REPRO_LINE = re.compile(
    rb"OK: reproducible sdist=([0-9a-f]{64}) wheel=([0-9a-f]{64})\n"
)
_PYTEST_SUMMARY = re.compile(rb"(?:^|\n)([1-9][0-9]*) passed in [^\r\n]+\n\Z")
_E2E_SUMMARY = re.compile(rb"E2E AUDIT: all ([1-9][0-9]*) stages passed\n")
_EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    re.compile(rb"(?:^|[^A-Za-z0-9])tmc_[A-Za-z0-9]{16,}"),
    re.compile(rb"(?:^|[^A-Za-z0-9])gh(?:p|o|u|s|r)_[A-Za-z0-9]{20,}"),
    re.compile(rb"(?:^|[^A-Z0-9])AKIA[A-Z0-9]{16}(?:[^A-Z0-9]|$)"),
    re.compile(rb"[?&](?:access_)?token=[^\s&]+", re.IGNORECASE),
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def reject_secret_material(data: bytes, label: str) -> None:
    if any(pattern.search(data) for pattern in SECRET_PATTERNS):
        raise CleanRunnerError(f"CLEAN_RUNNER_SECRET_MATERIAL_DETECTED:{label}")


def _valid_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and _HEX64.fullmatch(value) is not None
        and value != "0" * 64
    )


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _safe_relpath(value: object) -> bool:
    if not isinstance(value, str) or not value or value.startswith("/") or "\\" in value:
        return False
    parts = value.split("/")
    return all(part not in ("", ".", "..") for part in parts)


def safe_source_tree_entries(raw: bytes) -> dict[bytes, tuple[bytes, bytes]]:
    """Parse the canonical source tree and reject alternate executable/import surfaces."""
    entries: dict[bytes, tuple[bytes, bytes]] = {}
    rows = [row for row in raw.split(b"\0") if row]
    if not rows:
        raise CleanRunnerError("CLEAN_RUNNER_SOURCE_TREE_EMPTY")
    for row in rows:
        try:
            metadata, rel = row.split(b"\t", 1)
            mode, kind, object_id = metadata.split()
            object_id_text = object_id.decode("ascii")
        except (UnicodeDecodeError, ValueError) as exc:
            raise CleanRunnerError("CLEAN_RUNNER_SOURCE_TREE_ROW_MALFORMED") from exc
        if (
            not rel
            or rel in entries
            or kind != b"blob"
            or mode not in {b"100644", b"100755"}
            or _HEX40.fullmatch(object_id_text) is None
        ):
            raise CleanRunnerError("CLEAN_RUNNER_SOURCE_TREE_ENTRY_UNSAFE_OR_DUPLICATE")
        parts = rel.split(b"/")
        if any(not part or part in {b".", b".."} for part in parts):
            raise CleanRunnerError("CLEAN_RUNNER_SOURCE_TREE_PATH_UNSAFE")
        if b"__pycache__" in parts or rel.endswith((b".pyc", b".pyo")):
            raise CleanRunnerError("CLEAN_RUNNER_SOURCE_TREE_BYTECODE_CACHE_FORBIDDEN")
        if rel.endswith((b".so", b".pyd", b".dll", b".dylib")):
            raise CleanRunnerError("CLEAN_RUNNER_SOURCE_TREE_NATIVE_EXTENSION_FORBIDDEN")
        if rel.startswith(b"tools/b00r_pytest_inventory/"):
            raise CleanRunnerError(
                "CLEAN_RUNNER_SOURCE_TREE_INVENTORY_PACKAGE_SHADOW_FORBIDDEN"
            )
        entries[rel] = (mode, object_id)
    return entries


def _normalise_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _expect_keys(value: object, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CleanRunnerError(f"{label}_NOT_OBJECT")
    delta = set(value) ^ expected
    if delta:
        raise CleanRunnerError(f"{label}_FIELDS:{sorted(delta)}")
    return value


def _loads_unique(data: bytes, label: str, *, canonical: bool = True) -> dict[str, Any]:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise CleanRunnerError(f"{label}_DUPLICATE_KEY:{key}")
            result[key] = value
        return result

    try:
        value = json.loads(data, object_pairs_hook=unique)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CleanRunnerError(f"{label}_NOT_JSON:{exc}") from exc
    if not isinstance(value, dict):
        raise CleanRunnerError(f"{label}_NOT_OBJECT")
    if canonical and data != _canonical_json(value):
        raise CleanRunnerError(f"{label}_NOT_CANONICAL_JSON")
    return value


def _git(root: pathlib.Path, *args: str, text: bool = True) -> str | bytes:
    env = {
        name: value
        for name, value in BASE_ENV.items()
        if name.startswith("GIT_") or name in {"LANG", "LC_ALL", "TZ"}
    }
    proc = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=False,
        text=text, env=env,
    )
    if proc.returncode:
        stderr = proc.stderr if text else proc.stderr.decode("utf-8", "replace")
        raise CleanRunnerError(f"GIT_COMMAND_FAILED:{' '.join(args)}:{stderr.strip()}")
    return proc.stdout.strip() if text else proc.stdout


def _git_blob(root: pathlib.Path, commit: str, path: str) -> bytes:
    return _git(root, "show", f"{commit}:{path}", text=False)  # type: ignore[return-value]


class _Files:
    def __init__(
        self, root: pathlib.Path, entries: list[dict[str, Any]], expected_head: str
    ) -> None:
        self.root = root
        self.expected_head = expected_head
        self.by_path: dict[str, dict[str, Any]] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                raise CleanRunnerError("EVIDENCE_ENTRY_NOT_OBJECT")
            path = entry.get("path")
            if not _safe_relpath(path):
                raise CleanRunnerError(f"EVIDENCE_PATH_UNSAFE:{path!r}")
            if path in self.by_path:
                raise CleanRunnerError(f"EVIDENCE_PATH_DUPLICATE:{path}")
            self.by_path[path] = entry

    def read(
        self,
        path: str,
        *,
        role: str | None = None,
        role_unique: bool | None = None,
    ) -> bytes:
        entry = self.by_path.get(path)
        if entry is None:
            raise CleanRunnerError(f"EVIDENCE_ENTRY_MISSING:{path}")
        if role is not None and entry.get("role") != role:
            raise CleanRunnerError(
                f"EVIDENCE_ROLE_MISMATCH:{path}:{entry.get('role')!r}!={role!r}"
            )
        if role_unique is not None and entry.get("role_unique") is not role_unique:
            raise CleanRunnerError(f"EVIDENCE_ROLE_UNIQUENESS_MISMATCH:{path}")
        disk_path = self.root / path
        if disk_path.is_symlink() or not disk_path.is_file():
            raise CleanRunnerError(f"EVIDENCE_NOT_REGULAR_FILE:{path}")
        data = disk_path.read_bytes()
        if entry.get("size") != len(data):
            raise CleanRunnerError(f"EVIDENCE_SIZE_MISMATCH:{path}")
        digest = entry.get("sha256")
        if not _valid_sha256(digest):
            raise CleanRunnerError(f"EVIDENCE_DIGEST_INVALID:{path}")
        if digest != _sha256(data):
            raise CleanRunnerError(f"EVIDENCE_DIGEST_MISMATCH:{path}")
        if _git_blob(self.root, self.expected_head, path) != data:
            raise CleanRunnerError(f"EVIDENCE_GIT_BLOB_MISMATCH:{path}")
        return data

    def require_digest(self, path: str, digest: object, label: str) -> bytes:
        data = self.read(path)
        if digest != _sha256(data):
            raise CleanRunnerError(f"{label}_DIGEST_MISMATCH")
        return data

    def require_clean_runner_closed(self) -> None:
        prefix = f"{EVIDENCE_ROOT}/"
        declared = {path for path in self.by_path if path.startswith(prefix)}
        actual: set[str] = set()
        for candidate in (self.root / EVIDENCE_ROOT).rglob("*"):
            rel = candidate.relative_to(self.root).as_posix()
            if candidate.is_symlink():
                raise CleanRunnerError(f"CLEAN_RUNNER_SYMLINK_FORBIDDEN:{rel}")
            if candidate.is_dir():
                continue
            if not candidate.is_file():
                raise CleanRunnerError(f"CLEAN_RUNNER_NOT_REGULAR_FILE:{rel}")
            actual.add(rel)
        if declared != actual:
            raise CleanRunnerError(
                f"CLEAN_RUNNER_NAMESPACE_NOT_CLOSED:missing={sorted(actual-declared)}:"
                f"extra={sorted(declared-actual)}"
            )
        expected = _expected_clean_runner_paths()
        if actual != expected:
            raise CleanRunnerError(
                f"CLEAN_RUNNER_PROFILE_PATHS_MISMATCH:missing={sorted(expected-actual)}:"
                f"extra={sorted(actual-expected)}"
            )


def _require_reserved_roles(files: _Files, entries: list[dict[str, Any]], payload: dict) -> None:
    payload_fields = {
        "WORKFLOW": "workflow_sha256",
        "CONTRACT_MANIFEST": "contract_manifest_sha256",
        "TEST_MANIFEST": "test_manifest_sha256",
        "CONFIG_BUNDLE": "config_bundle_sha256",
        "ROLLBACK_PROOF": "rollback_proof_sha256",
    }
    for role, path in ROLE_PATHS.items():
        matches = [entry for entry in entries if entry.get("role") == role]
        if len(matches) != 1 or matches[0].get("path") != path:
            raise CleanRunnerError(f"RESERVED_ROLE_PATH_OR_COUNT:{role}:{len(matches)}")
        data = files.read(path, role=role, role_unique=True)
        if payload.get(payload_fields[role]) != _sha256(data):
            raise CleanRunnerError(f"RESERVED_ROLE_RECEIPT_DIGEST_MISMATCH:{role}")


def _validate_source(
    files: _Files, payload: dict[str, Any], source_merge: str, source_tree: str
) -> tuple[dict[str, Any], list[str]]:
    source_raw = files.read(
        SOURCE_IDENTITY_PATH, role="CLEAN_RUNNER_SOURCE_IDENTITY", role_unique=True
    )
    source = _expect_keys(
        _loads_unique(source_raw, "CLEAN_RUNNER_SOURCE_IDENTITY"),
        {
            "schema", "repository", "source_merge_sha", "source_merge_tree",
            "source_merge_time_us", "parents", "ls_tree_path", "ls_tree_sha256",
            "workflow_path", "workflow_sha256", "contract_manifest_path",
            "contract_manifest_sha256",
        },
        "CLEAN_RUNNER_SOURCE_IDENTITY",
    )
    if (
        source.get("schema") != "triad.b00r.clean_runner_source_identity.v1"
        or source.get("repository") != REPOSITORY
        or source.get("source_merge_sha") != source_merge
        or source.get("source_merge_tree") != source_tree
        or source.get("source_merge_time_us") != payload.get("source_merge_time_us")
    ):
        raise CleanRunnerError("CLEAN_RUNNER_SOURCE_IDENTITY_MISMATCH")

    row = str(_git(files.root, "rev-list", "--parents", "-n", "1", source_merge)).split()
    if len(row) != 3 or row[0] != source_merge:
        raise CleanRunnerError("CLEAN_RUNNER_SOURCE_NOT_TWO_PARENT_MERGE")
    parents = row[1:]
    if source_merge == files.expected_head:
        raise CleanRunnerError("CLEAN_RUNNER_SOURCE_IS_RECEIPT_HEAD")
    _git(files.root, "merge-base", "--is-ancestor", source_merge, files.expected_head)
    if source.get("parents") != parents:
        raise CleanRunnerError("CLEAN_RUNNER_SOURCE_PARENTS_MISMATCH")
    actual_tree = str(_git(files.root, "rev-parse", f"{source_merge}^{{tree}}"))
    if actual_tree != source_tree:
        raise CleanRunnerError("CLEAN_RUNNER_SOURCE_TREE_MISMATCH")
    commit_time_us = int(str(
        _git(files.root, "show", "-s", "--format=%ct", source_merge)
    )) * 1_000_000
    if commit_time_us != payload.get("source_merge_time_us"):
        raise CleanRunnerError("CLEAN_RUNNER_SOURCE_TIME_MISMATCH")

    if source.get("ls_tree_path") != SOURCE_TREE_PATH:
        raise CleanRunnerError("CLEAN_RUNNER_LS_TREE_PATH_NONCANONICAL")
    tree_bytes = files.read(
        SOURCE_TREE_PATH, role="CLEAN_RUNNER_SOURCE_TREE", role_unique=True
    )
    expected_tree_bytes = _git(
        files.root, "ls-tree", "-r", "-z", "--full-tree", source_merge, text=False
    )
    if tree_bytes != expected_tree_bytes or source.get("ls_tree_sha256") != _sha256(tree_bytes):
        raise CleanRunnerError("CLEAN_RUNNER_LS_TREE_MISMATCH")
    safe_source_tree_entries(tree_bytes)

    workflow = files.read(SOURCE_WORKFLOW_PATH, role="WORKFLOW", role_unique=True)
    if (
        source.get("workflow_path") != SOURCE_WORKFLOW_PATH
        or source.get("workflow_sha256") != _sha256(workflow)
        or workflow != _git_blob(files.root, source_merge, ".github/workflows/ci.yml")
    ):
        raise CleanRunnerError("CLEAN_RUNNER_SOURCE_WORKFLOW_MISMATCH")
    contract = files.read(CONTRACT_MANIFEST_PATH, role="CONTRACT_MANIFEST", role_unique=True)
    if (
        source.get("contract_manifest_path") != CONTRACT_MANIFEST_PATH
        or source.get("contract_manifest_sha256") != _sha256(contract)
        or contract != _git_blob(files.root, source_merge, "contracts/MANIFEST.sha256")
    ):
        raise CleanRunnerError("CLEAN_RUNNER_CONTRACT_MANIFEST_MISMATCH")
    return source, parents


def _validate_runner_facts(
    files: _Files,
    payload: dict[str, Any],
    run_id: str,
    source_merge: str,
    source_tree: str,
) -> dict[str, Any]:
    raw = files.read(RUNNER_FACTS_PATH, role="CLEAN_RUNNER_FACTS", role_unique=True)
    facts = _expect_keys(
        _loads_unique(raw, "CLEAN_RUNNER_FACTS"),
        {
            "schema", "run_id", "repository", "origin_url", "origin_main_sha",
            "checkout_mode", "head_sha", "tree_sha", "clone_no_local", "clone_no_tags",
            "clone_target_preexisted", "git_status_porcelain_z_sha256",
            "git_replace_list_sha256", "alternates_present", "is_shallow_repository",
            "submodule_count", "checkout_root", "evidence_output_root", "constraints_path",
            "constraints_sha256", "python_implementation", "python_version",
            "python_executable", "python_executable_sha256", "venv",
        },
        "CLEAN_RUNNER_FACTS",
    )
    expected = {
        "schema": "triad.b00r.clean_runner_facts.v1",
        "run_id": run_id,
        "repository": REPOSITORY,
        "origin_url": "https://github.com/TriadAgentic/TriadOrigin.git",
        "origin_main_sha": source_merge,
        "checkout_mode": "detached",
        "head_sha": source_merge,
        "tree_sha": source_tree,
        "clone_no_local": True,
        "clone_no_tags": True,
        "clone_target_preexisted": False,
        "git_status_porcelain_z_sha256": _EMPTY_SHA256,
        "git_replace_list_sha256": _EMPTY_SHA256,
        "alternates_present": False,
        "is_shallow_repository": False,
        "submodule_count": 0,
        "constraints_path": "constraints/ci.txt",
        "constraints_sha256": _sha256(_git_blob(files.root, source_merge, "constraints/ci.txt")),
        "python_implementation": "CPython",
    }
    if any(facts.get(key) != value for key, value in expected.items()):
        raise CleanRunnerError("CLEAN_RUNNER_FACTS_IDENTITY_MISMATCH")
    if (not isinstance(facts.get("python_version"), str)
            or re.fullmatch(r"3\.11\.[0-9]+", facts["python_version"]) is None):
        raise CleanRunnerError("CLEAN_RUNNER_PYTHON_VERSION_MISMATCH")
    if not _valid_sha256(facts.get("python_executable_sha256")):
        raise CleanRunnerError("CLEAN_RUNNER_PYTHON_DIGEST_INVALID")
    venv = _expect_keys(
        facts.get("venv"), {"prefix", "base_prefix", "system_site_packages"},
        "CLEAN_RUNNER_VENV",
    )
    if (
        not isinstance(venv.get("prefix"), str)
        or not isinstance(venv.get("base_prefix"), str)
        or not venv["prefix"]
        or not venv["base_prefix"]
        or venv["prefix"] == venv["base_prefix"]
        or venv.get("system_site_packages") is not False
    ):
        raise CleanRunnerError("CLEAN_RUNNER_VENV_NOT_FRESH")
    checkout_root = facts.get("checkout_root")
    evidence_root = facts.get("evidence_output_root")
    executable = facts.get("python_executable")
    path_values = (checkout_root, evidence_root, venv.get("prefix"), venv.get("base_prefix"))
    canonical_absolute = all(
        isinstance(value, str)
        and value.startswith("/")
        and ".." not in pathlib.PurePosixPath(value).parts
        and str(pathlib.PurePosixPath(value)) == value
        for value in path_values
    )
    isolated = False
    if canonical_absolute:
        scoped_paths = [
            pathlib.PurePosixPath(checkout_root),
            pathlib.PurePosixPath(evidence_root),
            pathlib.PurePosixPath(venv["prefix"]),
        ]
        isolated = all(
            left != right and left not in right.parents and right not in left.parents
            for index, left in enumerate(scoped_paths)
            for right in scoped_paths[index + 1:]
        )
    if (
        not isinstance(checkout_root, str) or not checkout_root.startswith("/")
        or not isinstance(evidence_root, str) or not evidence_root.startswith("/")
        or not isinstance(executable, str) or not executable.startswith("/")
        or not canonical_absolute
        or not isolated
        or pathlib.PurePosixPath(executable)
        != pathlib.PurePosixPath(venv["prefix"]) / "bin" / "python"
    ):
        raise CleanRunnerError("CLEAN_RUNNER_PATH_ISOLATION_MISMATCH")
    return facts


def _parse_constraints(data: bytes) -> dict[str, str]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CleanRunnerError("CLEAN_RUNNER_CONSTRAINTS_NOT_UTF8") from exc
    result: dict[str, str] = {}
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.count("==") != 1:
            raise CleanRunnerError(f"CLEAN_RUNNER_CONSTRAINT_NOT_EXACT:{lineno}")
        name, version = line.split("==", 1)
        if _PACKAGE_NAME.fullmatch(name) is None or _VERSION.fullmatch(version) is None:
            raise CleanRunnerError(f"CLEAN_RUNNER_CONSTRAINT_INVALID:{lineno}")
        normal = _normalise_name(name)
        if normal in result:
            raise CleanRunnerError(f"CLEAN_RUNNER_CONSTRAINT_DUPLICATE:{normal}")
        result[normal] = version
    if not result:
        raise CleanRunnerError("CLEAN_RUNNER_CONSTRAINTS_EMPTY")
    return result


def _source_runtime_files(root: pathlib.Path, source_merge: str) -> dict[str, tuple[int, str]]:
    output = _git(
        root, "ls-tree", "-r", "-z", "--long", source_merge, "--", "src/triad_origin",
        text=False,
    )
    result: dict[str, tuple[int, str]] = {}
    for row in output.split(b"\0"):
        if not row:
            continue
        try:
            metadata, raw_path = row.split(b"\t", 1)
            _mode, kind, _object_id, size_raw = metadata.decode("ascii").split()
            path = raw_path.decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise CleanRunnerError("CLEAN_RUNNER_SOURCE_RUNTIME_TREE_MALFORMED") from exc
        if kind != "blob" or not size_raw.isdigit():
            raise CleanRunnerError("CLEAN_RUNNER_SOURCE_RUNTIME_TREE_MALFORMED")
        installed = "triad_origin/" + path.removeprefix("src/triad_origin/")
        blob = _git_blob(root, source_merge, path)
        result[installed] = (int(size_raw), _sha256(blob))
    if not result:
        raise CleanRunnerError("CLEAN_RUNNER_SOURCE_RUNTIME_EMPTY")
    return result


def _validate_packages(
    files: _Files,
    run_id: str,
    source_merge: str,
    facts: dict[str, Any],
) -> dict[str, Any]:
    raw = files.read(
        PACKAGE_SNAPSHOT_PATH, role="CLEAN_RUNNER_PACKAGE_SNAPSHOT", role_unique=True
    )
    snapshot = _expect_keys(
        _loads_unique(raw, "CLEAN_RUNNER_PACKAGE_SNAPSHOT"),
        {
            "schema", "run_id", "source_merge_sha", "constraints_path",
            "constraints_sha256", "distributions",
        },
        "CLEAN_RUNNER_PACKAGE_SNAPSHOT",
    )
    constraint_bytes = _git_blob(files.root, source_merge, "constraints/ci.txt")
    if (
        snapshot.get("schema") != "triad.b00r.installed_packages.v1"
        or snapshot.get("run_id") != run_id
        or snapshot.get("source_merge_sha") != source_merge
        or snapshot.get("constraints_path") != "constraints/ci.txt"
        or snapshot.get("constraints_sha256") != _sha256(constraint_bytes)
        or snapshot.get("constraints_sha256") != facts.get("constraints_sha256")
    ):
        raise CleanRunnerError("CLEAN_RUNNER_PACKAGE_SNAPSHOT_IDENTITY_MISMATCH")
    constraints = _parse_constraints(constraint_bytes)
    distributions = snapshot.get("distributions")
    if not isinstance(distributions, list) or not distributions:
        raise CleanRunnerError("CLEAN_RUNNER_PACKAGE_SNAPSHOT_EMPTY")
    names = [item.get("name") if isinstance(item, dict) else None for item in distributions]
    if (
        not all(isinstance(name, str) for name in names)
        or names != sorted(names)
        or len(names) != len(set(names))
    ):
        raise CleanRunnerError("CLEAN_RUNNER_PACKAGES_NOT_CANONICAL_UNIQUE")
    by_name: dict[str, dict[str, Any]] = {}
    all_files: dict[str, tuple[int, str]] = {}
    for item in distributions:
        dist = _expect_keys(item, {"name", "version", "files"}, "CLEAN_RUNNER_PACKAGE")
        name = dist.get("name")
        version = dist.get("version")
        if (
            not isinstance(name, str)
            or name != _normalise_name(name)
            or _PACKAGE_NAME.fullmatch(name) is None
            or not isinstance(version, str)
            or _VERSION.fullmatch(version) is None
        ):
            raise CleanRunnerError("CLEAN_RUNNER_PACKAGE_IDENTITY_INVALID")
        file_rows = dist.get("files")
        if not isinstance(file_rows, list) or not file_rows:
            raise CleanRunnerError(f"CLEAN_RUNNER_PACKAGE_FILES_EMPTY:{name}")
        paths = [row.get("path") if isinstance(row, dict) else None for row in file_rows]
        if (
            not all(isinstance(path, str) for path in paths)
            or paths != sorted(paths)
            or len(paths) != len(set(paths))
        ):
            raise CleanRunnerError(f"CLEAN_RUNNER_PACKAGE_FILES_NOT_CANONICAL:{name}")
        for row in file_rows:
            file_row = _expect_keys(
                row, {"path", "size", "sha256"}, "CLEAN_RUNNER_PACKAGE_FILE"
            )
            path = file_row.get("path")
            digest = file_row.get("sha256")
            size = file_row.get("size")
            if (
                not _safe_relpath(path)
                or not isinstance(size, int)
                or isinstance(size, bool)
                or size < 0
                or not _valid_sha256(digest)
            ):
                raise CleanRunnerError(f"CLEAN_RUNNER_PACKAGE_FILE_INVALID:{name}:{path}")
            if path in all_files:
                raise CleanRunnerError(f"CLEAN_RUNNER_PACKAGE_FILE_DUPLICATE:{path}")
            all_files[path] = (size, digest)
        by_name[name] = dist

    for name, version in constraints.items():
        if name not in by_name or by_name[name].get("version") != version:
            raise CleanRunnerError(f"CLEAN_RUNNER_CONSTRAINT_PACKAGE_MISMATCH:{name}")
    allowed_names = set(constraints) | {"pip", "triad-origin"}
    if set(by_name) != allowed_names:
        raise CleanRunnerError(
            "CLEAN_RUNNER_PACKAGE_SET_MISMATCH:"
            f"missing={sorted(allowed_names-set(by_name))}:"
            f"extra={sorted(set(by_name)-allowed_names)}"
        )
    try:
        pyproject = tomllib.loads(_git_blob(files.root, source_merge, "pyproject.toml").decode())
        project_version = pyproject["project"]["version"]
    except (UnicodeError, tomllib.TOMLDecodeError, KeyError, TypeError) as exc:
        raise CleanRunnerError("CLEAN_RUNNER_PROJECT_VERSION_UNAVAILABLE") from exc
    if by_name.get("triad-origin", {}).get("version") != project_version:
        raise CleanRunnerError("CLEAN_RUNNER_PROJECT_PACKAGE_VERSION_MISMATCH")
    triad_files = {
        row["path"]: (row["size"], row["sha256"])
        for row in by_name["triad-origin"]["files"]
    }
    source_runtime = _source_runtime_files(files.root, source_merge)
    for path, expected in source_runtime.items():
        if triad_files.get(path) != expected:
            raise CleanRunnerError(f"CLEAN_RUNNER_INSTALLED_SOURCE_MISMATCH:{path}")
    unexpected_runtime = sorted(
        path for path in triad_files if path.startswith("triad_origin/")
        and path not in source_runtime
    )
    if unexpected_runtime:
        raise CleanRunnerError(f"CLEAN_RUNNER_INSTALLED_SOURCE_EXTRA:{unexpected_runtime}")
    return snapshot


def _read_stream(
    files: _Files,
    record: dict[str, Any],
    prefix: str,
    expected_path: str,
    role: str,
) -> bytes:
    path = record.get(f"{prefix}_path")
    if path != expected_path:
        raise CleanRunnerError(f"CLEAN_RUNNER_{prefix.upper()}_PATH_NONCANONICAL:{path}")
    data = files.read(path, role=role, role_unique=False)
    if (
        record.get(f"{prefix}_size") != len(data)
        or record.get(f"{prefix}_sha256") != _sha256(data)
    ):
        raise CleanRunnerError(f"CLEAN_RUNNER_{prefix.upper()}_BINDING_MISMATCH:{path}")
    return data


def _validate_commands(
    files: _Files,
    run: dict[str, Any],
    source_merge: str,
    observed_at_us: int,
    facts: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, bytes]]:
    commands = run.get("commands")
    if not isinstance(commands, list) or len(commands) != len(REQUIRED_COMMANDS):
        raise CleanRunnerError("CLEAN_RUNNER_COMMAND_SET_LENGTH_MISMATCH")
    by_id: dict[str, dict[str, Any]] = {}
    stdout_by_id: dict[str, bytes] = {}
    previous_finish = run["started_at_us"]
    fields = {
        "ordinal", "id", "argv", "env", "cwd", "started_at_us", "finished_at_us",
        "stdout_path", "stdout_sha256", "stdout_size", "stderr_path", "stderr_sha256",
        "stderr_size", "rc_path", "rc_sha256", "rc_size", "exit_code",
    }
    for ordinal, (record, required) in enumerate(zip(commands, REQUIRED_COMMANDS, strict=True)):
        item = _expect_keys(record, fields, "CLEAN_RUNNER_COMMAND")
        command_id, argv, seed = required
        expected_argv = [facts["python_executable"] if part == "$PYTHON" else part for part in argv]
        expected_env = dict(
            BASE_ENV,
            PIP_CONSTRAINT=f"{facts['checkout_root']}/constraints/ci.txt",
            PYTHONHASHSEED=seed,
        )
        if command_id.startswith("pytest-seed"):
            expected_env.update({
                "TRIAD_B00R_RUN_ID": run["run_id"],
                "TRIAD_B00R_SOURCE_MERGE": source_merge,
                "TRIAD_B00R_TEST_IDS_PATH":
                    f"{facts['evidence_output_root']}/{TEST_IDS_PATHS[seed]}",
                "TRIAD_B00R_TEST_IDS_REL": TEST_IDS_PATHS[seed],
                "TRIAD_B00R_TEST_RESULT_PATH":
                    f"{facts['evidence_output_root']}/{PYTEST_RESULT_PATHS[seed]}",
                "TRIAD_B00R_TEST_RESULT_REL": PYTEST_RESULT_PATHS[seed],
            })
        if (
            item.get("ordinal") != ordinal
            or item.get("id") != command_id
            or item.get("argv") != expected_argv
            or item.get("env") != expected_env
            or item.get("cwd") != facts["checkout_root"]
            or item.get("exit_code") != 0
        ):
            raise CleanRunnerError(f"CLEAN_RUNNER_COMMAND_PROFILE_MISMATCH:{ordinal}")
        started = item.get("started_at_us")
        finished = item.get("finished_at_us")
        if (
            not isinstance(started, int) or isinstance(started, bool)
            or not isinstance(finished, int) or isinstance(finished, bool)
            or started < previous_finish or finished < started or finished > observed_at_us
        ):
            raise CleanRunnerError(f"CLEAN_RUNNER_COMMAND_CHRONOLOGY:{command_id}")
        previous_finish = finished
        base = f"{EVIDENCE_ROOT}/commands/{ordinal:02d}-{command_id}"
        stdout = _read_stream(
            files, item, "stdout", f"{base}/stdout.bin", "CLEAN_RUNNER_COMMAND_STDOUT"
        )
        _read_stream(
            files, item, "stderr", f"{base}/stderr.bin", "CLEAN_RUNNER_COMMAND_STDERR"
        )
        rc = _read_stream(
            files, item, "rc", f"{base}/rc.txt", "CLEAN_RUNNER_COMMAND_RC"
        )
        if rc != b"0\n":
            raise CleanRunnerError(f"CLEAN_RUNNER_COMMAND_RC_NOT_ZERO:{command_id}")
        by_id[command_id] = item
        stdout_by_id[command_id] = stdout
    if previous_finish > run["finished_at_us"]:
        raise CleanRunnerError("CLEAN_RUNNER_FINISH_BEFORE_LAST_COMMAND")
    return by_id, stdout_by_id


def _parse_test_ids(data: bytes, label: str) -> list[str]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CleanRunnerError(f"{label}_NOT_UTF8") from exc
    ids = text.splitlines()
    if (
        not data.endswith(b"\n")
        or not ids
        or len(ids) != len(set(ids))
        or any(not item.startswith("tests/") or "::" not in item for item in ids)
        or any(any(ord(char) < 32 or ord(char) == 127 for char in item) for item in ids)
    ):
        raise CleanRunnerError(f"{label}_MALFORMED")
    return ids


def _validate_tests(
    files: _Files,
    run_id: str,
    source_merge: str,
    command_stdout: dict[str, bytes],
) -> dict[str, Any]:
    raw = files.read(TEST_MANIFEST_PATH, role="TEST_MANIFEST", role_unique=True)
    manifest = _expect_keys(
        _loads_unique(raw, "CLEAN_RUNNER_TEST_MANIFEST"),
        {
            "schema", "run_id", "source_merge_sha", "collector_stdout_path",
            "collector_stdout_sha256", "seed_runs", "test_count", "identical",
        },
        "CLEAN_RUNNER_TEST_MANIFEST",
    )
    collector = command_stdout["collect-test-ids"]
    if (
        manifest.get("schema") != "triad.b00r.clean_runner_tests.v1"
        or manifest.get("run_id") != run_id
        or manifest.get("source_merge_sha") != source_merge
        or manifest.get("collector_stdout_path")
        != f"{EVIDENCE_ROOT}/commands/02-collect-test-ids/stdout.bin"
        or manifest.get("collector_stdout_sha256") != _sha256(collector)
        or manifest.get("identical") is not True
    ):
        raise CleanRunnerError("CLEAN_RUNNER_TEST_MANIFEST_IDENTITY_MISMATCH")
    collector_ids = _parse_test_ids(collector, "CLEAN_RUNNER_COLLECTOR_TEST_IDS")
    seed_runs = manifest.get("seed_runs")
    if not isinstance(seed_runs, list) or len(seed_runs) != 2:
        raise CleanRunnerError("CLEAN_RUNNER_SEED_RUNS_MALFORMED")
    all_ids = []
    for index, seed in enumerate(("0", "1")):
        row = _expect_keys(
            seed_runs[index],
            {"seed", "result_path", "result_sha256", "test_ids_path", "test_ids_sha256"},
            "CLEAN_RUNNER_SEED_RUN",
        )
        if (
            row.get("seed") != seed
            or row.get("result_path") != PYTEST_RESULT_PATHS[seed]
            or row.get("test_ids_path") != TEST_IDS_PATHS[seed]
        ):
            raise CleanRunnerError(f"CLEAN_RUNNER_SEED_RUN_PATH_MISMATCH:{seed}")
        ids_raw = files.read(
            TEST_IDS_PATHS[seed],
            role=f"CLEAN_RUNNER_TEST_IDS_SEED{seed}", role_unique=True,
        )
        result_raw = files.read(
            PYTEST_RESULT_PATHS[seed],
            role=f"CLEAN_RUNNER_PYTEST_RESULT_SEED{seed}", role_unique=True,
        )
        if (
            row.get("test_ids_sha256") != _sha256(ids_raw)
            or row.get("result_sha256") != _sha256(result_raw)
        ):
            raise CleanRunnerError(f"CLEAN_RUNNER_SEED_RUN_DIGEST_MISMATCH:{seed}")
        ids = _parse_test_ids(ids_raw, f"CLEAN_RUNNER_TEST_IDS_SEED{seed}")
        result = _expect_keys(
            _loads_unique(result_raw, f"CLEAN_RUNNER_PYTEST_RESULT_SEED{seed}"),
            {
                "schema", "run_id", "source_merge_sha", "seed", "exit_code", "collected",
                "passed", "skipped", "xfailed", "failed", "errors", "test_ids_path",
                "test_ids_sha256",
            },
            f"CLEAN_RUNNER_PYTEST_RESULT_SEED{seed}",
        )
        if (
            result.get("schema") != "triad.b00r.pytest_inventory.v1"
            or result.get("run_id") != run_id
            or result.get("source_merge_sha") != source_merge
            or result.get("seed") != int(seed)
            or result.get("exit_code") != 0
            or result.get("collected") != len(ids)
            or result.get("passed") != len(ids)
            or any(result.get(field) != 0 for field in ("skipped", "xfailed", "failed", "errors"))
            or result.get("test_ids_path") != TEST_IDS_PATHS[seed]
            or result.get("test_ids_sha256") != _sha256(ids_raw)
        ):
            raise CleanRunnerError(f"CLEAN_RUNNER_PYTEST_RESULT_MISMATCH:{seed}")
        all_ids.append(ids)
    if all_ids[0] != all_ids[1] or all_ids[0] != collector_ids:
        raise CleanRunnerError("CLEAN_RUNNER_TEST_INVENTORIES_DIFFER")
    if manifest.get("test_count") != len(collector_ids):
        raise CleanRunnerError("CLEAN_RUNNER_TEST_COUNT_MISMATCH")
    for seed in ("0", "1"):
        stdout = command_stdout[f"pytest-seed{seed}"]
        summary = _PYTEST_SUMMARY.search(stdout)
        if summary is None or int(summary.group(1)) != len(collector_ids):
            raise CleanRunnerError(f"CLEAN_RUNNER_PYTEST_STDOUT_MISMATCH:{seed}")
    return manifest


def _validate_output_semantics(stdout: dict[str, bytes]) -> tuple[str, str]:
    required_markers = {
        "verify-manifest": b"OK: ",
        "validate-contract-manifest":
            b"OK: committed contract manifest validates against triad.contract_bundle.manifest.v1\n",
        "test-wheel-install": b"OK: sdist-built wheel byte-matches runtime",
        "verify-no-forbidden-capabilities":
            b"OK: E02 runtime has no network, credential, or venue-order capability\n",
        "build-ledger": b"OK: build ledger current (",
        "validate-combined-dag": b"OK: combined DAG valid ",
    }
    for command_id, marker in required_markers.items():
        if marker not in stdout[command_id] or b"FAIL:" in stdout[command_id]:
            raise CleanRunnerError(f"CLEAN_RUNNER_SUCCESS_MARKER_ABSENT:{command_id}")
    repro = stdout["verify-reproducible-build"]
    match = _REPRO_LINE.fullmatch(repro)
    if (
        match is None
        or match.group(1) == match.group(2)
        or not _valid_sha256(match.group(1).decode())
        or not _valid_sha256(match.group(2).decode())
    ):
        raise CleanRunnerError("CLEAN_RUNNER_REPRODUCIBLE_BUILD_OUTPUT_INVALID")
    e2e = stdout["e2e-audit"]
    summary = _E2E_SUMMARY.search(e2e)
    if (
        summary is None
        or int(summary.group(1)) < 24
        or e2e.count(b"PASS ") != int(summary.group(1))
    ):
        raise CleanRunnerError("CLEAN_RUNNER_E2E_OUTPUT_INVALID")
    return match.group(1).decode(), match.group(2).decode()


def _validate_config(
    files: _Files,
    payload: dict[str, Any],
    run_id: str,
    source_merge: str,
    sdist_sha: str,
    wheel_sha: str,
) -> dict[str, Any]:
    raw = files.read(CONFIG_BUNDLE_PATH, role="CONFIG_BUNDLE", role_unique=True)
    config = _expect_keys(
        _loads_unique(raw, "CLEAN_RUNNER_CONFIG_BUNDLE"),
        {
            "schema", "run_id", "source_merge_sha", "activation_result", "levers",
            "source_files", "reproducible_sdist_sha256", "reproducible_wheel_sha256",
        },
        "CLEAN_RUNNER_CONFIG_BUNDLE",
    )
    expected_rows = [
        {"path": path, "sha256": _sha256(_git_blob(files.root, source_merge, path))}
        for path in CONFIG_SOURCE_PATHS
    ]
    if (
        config.get("schema") != "triad.b00r.clean_runner_config_bundle.v1"
        or config.get("run_id") != run_id
        or config.get("source_merge_sha") != source_merge
        or config.get("activation_result") != "DENIED_SAFE_HOLD"
        or config.get("levers") != SAFE_HOLD_LEVERS
        or config.get("levers") != payload.get("levers")
        or payload.get("activation_result") != "DENIED_SAFE_HOLD"
        or config.get("source_files") != expected_rows
        or config.get("reproducible_sdist_sha256") != sdist_sha
        or config.get("reproducible_wheel_sha256") != wheel_sha
    ):
        raise CleanRunnerError("CLEAN_RUNNER_CONFIG_BUNDLE_MISMATCH")
    return config


def _validate_rollback(
    files: _Files,
    run_id: str,
    source_merge: str,
    source_tree: str,
    parents: list[str],
) -> dict[str, Any]:
    raw = files.read(ROLLBACK_PROOF_PATH, role="ROLLBACK_PROOF", role_unique=True)
    proof = _expect_keys(
        _loads_unique(raw, "CLEAN_RUNNER_ROLLBACK_PROOF"),
        {
            "schema", "run_id", "source_merge_sha", "source_merge_tree",
            "mainline_parent_sha", "mainline_parent_tree", "command", "stdout_path",
            "stdout_sha256", "stdout_size", "stderr_path", "stderr_sha256", "stderr_size",
            "rc_path", "rc_sha256", "rc_size", "exit_code", "result_tree_sha", "result",
        },
        "CLEAN_RUNNER_ROLLBACK_PROOF",
    )
    stdout = files.read(
        ROLLBACK_STDOUT_PATH, role="CLEAN_RUNNER_ROLLBACK_STDOUT", role_unique=True
    )
    stderr = files.read(
        ROLLBACK_STDERR_PATH, role="CLEAN_RUNNER_ROLLBACK_STDERR", role_unique=True
    )
    rc = files.read(ROLLBACK_RC_PATH, role="CLEAN_RUNNER_ROLLBACK_RC", role_unique=True)
    parent_tree = str(_git(files.root, "rev-parse", f"{parents[0]}^{{tree}}"))
    expected = {
        "schema": "triad.b00r.clean_runner_rollback_proof.v1",
        "run_id": run_id,
        "source_merge_sha": source_merge,
        "source_merge_tree": source_tree,
        "mainline_parent_sha": parents[0],
        "mainline_parent_tree": parent_tree,
        "command": ["git", "revert", "--no-commit", "-m", "1", source_merge],
        "stdout_path": ROLLBACK_STDOUT_PATH,
        "stdout_sha256": _sha256(stdout),
        "stdout_size": len(stdout),
        "stderr_path": ROLLBACK_STDERR_PATH,
        "stderr_sha256": _sha256(stderr),
        "stderr_size": len(stderr),
        "rc_path": ROLLBACK_RC_PATH,
        "rc_sha256": _sha256(rc),
        "rc_size": len(rc),
        "exit_code": 0,
        "result_tree_sha": parent_tree,
        "result": "PASS",
    }
    if proof != expected or rc != b"0\n":
        raise CleanRunnerError("CLEAN_RUNNER_ROLLBACK_PROOF_MISMATCH")
    return proof


def validate_bundle(
    root: pathlib.Path | str,
    entries: list[dict[str, Any]],
    payload: dict[str, Any],
    expected_head: str,
    now_us: int | None = None,
) -> None:
    """Validate one committed B00R G2 clean-runner bundle or raise ``CleanRunnerError``."""
    root = pathlib.Path(root).resolve(strict=True)
    if _HEX40.fullmatch(expected_head or "") is None or expected_head == "0" * 40:
        raise CleanRunnerError("CLEAN_RUNNER_EXPECTED_HEAD_INVALID")
    if str(_git(root, "rev-parse", "HEAD")) != expected_head:
        raise CleanRunnerError("CLEAN_RUNNER_EXPECTED_HEAD_MISMATCH")
    if str(_git(root, "status", "--porcelain=v1", "--untracked-files=all")):
        raise CleanRunnerError("CLEAN_RUNNER_WORKTREE_NOT_CLEAN")
    if not isinstance(entries, list) or not isinstance(payload, dict):
        raise CleanRunnerError("CLEAN_RUNNER_INPUT_SHAPE_INVALID")

    source_merge = payload.get("source_merge_sha")
    source_tree = payload.get("source_merge_tree")
    if (
        not isinstance(source_merge, str) or _HEX40.fullmatch(source_merge) is None
        or not isinstance(source_tree, str) or _HEX40.fullmatch(source_tree) is None
    ):
        raise CleanRunnerError("CLEAN_RUNNER_SOURCE_IDENTITY_INVALID")

    files = _Files(root, entries, expected_head)
    files.require_clean_runner_closed()
    for path in sorted(_expected_clean_runner_paths()):
        reject_secret_material(files.read(path), path)
    _require_reserved_roles(files, entries, payload)
    source, parents = _validate_source(files, payload, source_merge, source_tree)

    run_raw = files.read(RUN_PATH, role="CLEAN_RUNNER_RUN", role_unique=True)
    run = _expect_keys(
        _loads_unique(run_raw, "CLEAN_RUNNER_RUN"),
        {
            "schema", "profile", "repository", "run_id", "source_merge_sha",
            "source_merge_tree", "source_merge_time_us", "started_at_us", "finished_at_us",
            "runner_facts_path", "runner_facts_sha256", "package_snapshot_path",
            "package_snapshot_sha256", "source_identity_path", "source_identity_sha256",
            "test_manifest_path", "test_manifest_sha256", "config_bundle_path",
            "config_bundle_sha256", "rollback_proof_path", "rollback_proof_sha256",
            "commands", "result",
        },
        "CLEAN_RUNNER_RUN",
    )
    run_id = run.get("run_id")
    source_time = payload.get("source_merge_time_us")
    observed = payload.get("observed_at_us")
    emitted = payload.get("emitted_at_us")
    started = run.get("started_at_us")
    finished = run.get("finished_at_us")
    if (
        run.get("schema") != "triad.b00r.clean_runner_run.v1"
        or run.get("profile") != PROFILE
        or run.get("repository") != REPOSITORY
        or not isinstance(run_id, str) or _RUN_ID.fullmatch(run_id) is None
        or set(run_id) == {"0"}
        or run.get("source_merge_sha") != source_merge
        or run.get("source_merge_tree") != source_tree
        or run.get("source_merge_time_us") != source_time
        or not all(isinstance(value, int) and not isinstance(value, bool)
                   for value in (source_time, observed, emitted, started, finished))
        or not source_time < started <= finished <= observed <= emitted
        or run.get("result") != "PASS"
        or (
            now_us is not None
            and (
                not isinstance(now_us, int)
                or isinstance(now_us, bool)
                or emitted > now_us
            )
        )
    ):
        raise CleanRunnerError("CLEAN_RUNNER_RUN_IDENTITY_OR_CHRONOLOGY_MISMATCH")

    pointer_specs = (
        ("runner_facts", RUNNER_FACTS_PATH),
        ("package_snapshot", PACKAGE_SNAPSHOT_PATH),
        ("source_identity", SOURCE_IDENTITY_PATH),
        ("test_manifest", TEST_MANIFEST_PATH),
        ("config_bundle", CONFIG_BUNDLE_PATH),
        ("rollback_proof", ROLLBACK_PROOF_PATH),
    )
    for prefix, path in pointer_specs:
        if run.get(f"{prefix}_path") != path:
            raise CleanRunnerError(f"CLEAN_RUNNER_POINTER_PATH_MISMATCH:{prefix}")
        files.require_digest(path, run.get(f"{prefix}_sha256"), f"CLEAN_RUNNER_{prefix.upper()}")

    facts = _validate_runner_facts(files, payload, run_id, source_merge, source_tree)
    _validate_packages(files, run_id, source_merge, facts)
    _commands, command_stdout = _validate_commands(
        files, run, source_merge, observed, facts
    )
    _validate_tests(files, run_id, source_merge, command_stdout)
    sdist_sha, wheel_sha = _validate_output_semantics(command_stdout)
    _validate_config(files, payload, run_id, source_merge, sdist_sha, wheel_sha)
    _validate_rollback(files, run_id, source_merge, source_tree, parents)

    # Re-check the source identity pointer after all subordinate checks; this also prevents an
    # unused parsed source document from becoming presentation-only metadata.
    if source.get("source_merge_sha") != run.get("source_merge_sha"):
        raise CleanRunnerError("CLEAN_RUNNER_SOURCE_RUN_BINDING_MISMATCH")


def _load_json_file(path: pathlib.Path, label: str) -> dict[str, Any]:
    return _loads_unique(path.read_bytes(), label, canonical=False)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Verify B00R G2 clean-runner evidence.")
    sub = parser.add_subparsers(dest="mode", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--root", default=".")
    verify.add_argument("--manifest", default="evidence/B00R_G2/evidence_manifest.json")
    verify.add_argument("--receipt", default="evidence/receipts/B00R.g2.receipt.v3.json")
    verify.add_argument("--expected-head", required=True)
    verify.add_argument("--now-us", type=int)
    args = parser.parse_args(argv)
    root = pathlib.Path(args.root).resolve()
    try:
        manifest = _load_json_file(root / args.manifest, "CLEAN_RUNNER_EVIDENCE_MANIFEST")
        receipt = _load_json_file(root / args.receipt, "CLEAN_RUNNER_RECEIPT")
        entries = manifest.get("entries")
        payload = receipt.get("payload")
        validate_bundle(root, entries, payload, args.expected_head, now_us=args.now_us)
    except (OSError, CleanRunnerError) as exc:
        print(f"FAIL: CLEAN_RUNNER_BUNDLE_INVALID:{exc}", file=sys.stderr)
        return 1
    print(f"OK: B00R G2 clean-runner bundle bound to {payload['source_merge_sha']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
