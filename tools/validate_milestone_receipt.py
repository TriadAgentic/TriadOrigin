#!/usr/bin/env python3
"""Validate a milestone receipt's schema and cross-field evidence bindings."""

from __future__ import annotations

import base64
import csv
from email import policy
from email.parser import BytesParser
import hashlib
import io
import json
import os
import pathlib
import re
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile
from typing import Any

import jsonschema

from triad_origin.canonical import canonical_json

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_SCHEMA = ROOT / "docs" / "plan" / "milestone_receipt.schema.json"
R00_REQUIRED_COMMANDS = [
    "PYTHONHASHSEED=0 python -m pytest",
    "PYTHONHASHSEED=1 python -m pytest",
    "python tools/collect_test_ids.py",
    "python tools/verify_manifest.py",
    "python tools/validate_contract_manifest.py",
    "python tools/verify_reproducible_build.py",
    "python tools/test_wheel_install.py",
    "python tools/verify_no_forbidden_capabilities.py",
]
R00_REQUIRED_ARTIFACT_KINDS = {"source-tree", "sdist", "wheel"}
R00_REQUIRED_MANIFESTS = {
    "contracts", "golden_vectors", "test_collection", "test_collection_log"
}
R00_REQUIRED_DEFERRALS = {
    "branch-ruleset": "B00",
    "formula-evidence": "B03",
    "parameter-evidence": "B03",
    "replay-evidence": "B02",
}
R00_INHERITED_THREADS = {
    "3740889446": 1,
    "3740889448": 1,
    "3740889449": 1,
    "3740889452": 1,
    "3740889453": 1,
    "3740901367": 2,
    "3740901373": 2,
    "3740901374": 2,
    "3740901377": 2,
    "3740901381": 2,
    "3740901383": 2,
    "3740938956": 3,
    "3740938960": 3,
    "3740938963": 3,
}
R00_KNOWN_PR4_THREADS = {
    "3741134194", "3741134196", "3741134197",
    "3741211095", "3741211096", "3741211097",
}
R00_RECEIPT_PR = 7
R00_REVIEW_PRS = {1, 2, 3, 4, R00_RECEIPT_PR}
# Populated before the corrective head may merge if PR #7 receives inline findings.
R00_KNOWN_PR7_THREADS: set[str] = set()
R00_AUTHORITY_INVENTORY_PATH = "docs/plan/06_RC2_SOURCE_INVENTORY.md"
R00_AUTHORITY_SOURCES = [
    {"bytes": 8_000, "name": "index.html", "sha256": "042f6bea59f897add75dd108632cdd22d90382350a290f8f5a0873fa2e636568"},
    {"bytes": 669_712, "name": "TRIAD_ORIGIN_V7_IMPLEMENTATION_CONTROL_WORKBOOK_1.0.0_RC2.xlsx", "sha256": "2b60d1d4a40456948eff8da5a982956d35f144a7e76445839aa937a1282481e4"},
    {"bytes": 3_106_927, "name": "02_TRIAD_ORIGIN_V7_WIRING_FORMULA_AND_PLUMBING_GUIDE_1.0.0_RC2.html", "sha256": "6c12490ba5677177dc6a85818ce6936e3f028c54ccbbb50bc85496d48162573d"},
    {"bytes": 357_745, "name": "03_TRIAD_ORIGIN_V7_UNAMBIGUOUS_DECLARATIONS_VARIABLES_AND_OBJECTIVE_ACCEPTANCE_1.0.0_RC2.html", "sha256": "15a85a4f42de6636cecb86341d2488eb77b13bc452dc682b5dcb3d847d054fb4"},
    {"bytes": 2_243_356, "name": "Illustrative topology PNG", "sha256": "e4bfc5b549eef6cf7c729d469ab8e78212f1d0d30c011e9dee85797096229f0c"},
]
R00_AUTHORITY_MISSING = [
    "01_TRIAD_ORIGIN_V7_COMPLETE_IMPLEMENTATION_CHECKLIST_1.0.0_RC2.html",
    "canonical/ control bundle and manifest/digests",
]


class ReceiptValidationError(ValueError):
    pass


def _walk_strings(value: Any, path: str = "<root>"):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk_strings(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_strings(child, f"{path}[{index}]")
    elif isinstance(value, str):
        yield path, value


def validate_receipt(
    receipt: dict[str, Any], schema: dict[str, Any], *, evidence_root: pathlib.Path
) -> None:
    """Reject structurally valid receipts whose linked evidence identities disagree."""
    jsonschema.validators.validator_for(schema).check_schema(schema)
    jsonschema.validate(receipt, schema)
    problems: list[str] = []
    if receipt["ci"]["head_sha"] != receipt["head_sha"]:
        problems.append("ci.head_sha does not equal head_sha")
    if receipt["post_merge"]["fresh_main_sha"] != receipt["merge_sha"]:
        problems.append("post_merge.fresh_main_sha does not equal merge_sha")
    if receipt["merge_control"]["expected_head_sha"] != receipt["head_sha"]:
        problems.append("merge_control.expected_head_sha does not equal reviewed head_sha")
    expected_merge_url = (
        f"https://github.com/{receipt['merge_control']['repository']}/pull/"
        f"{receipt['merge_control']['pr_number']}"
    )
    if receipt["merge_control"]["url"] != expected_merge_url:
        problems.append("merge_control.url does not match repository and PR number")
    if len({receipt["base_sha"], receipt["head_sha"], receipt["merge_sha"]}) != 3:
        problems.append("base, head, and squash-merge SHAs must be distinct")
    if not receipt["ci"]["run_id"].isdigit():
        problems.append("ci.run_id must be a decimal GitHub Actions run ID")
    commands = [test["command"] for test in receipt["tests"]]
    if receipt["milestone_id"] == "R00":
        if (
            receipt["merge_control"]["repository"] != "TriadAgentic/TriadOrigin"
            or receipt["merge_control"]["pr_number"] != R00_RECEIPT_PR
        ):
            problems.append(
                "R00 merge control does not identify the controlled corrective PR #7"
            )
        if commands != R00_REQUIRED_COMMANDS:
            problems.append("R00 tests do not equal the controlled required command set")
        artifact_kind_list = [artifact["kind"] for artifact in receipt["artifacts"]]
        artifact_kinds = set(artifact_kind_list)
        if not R00_REQUIRED_ARTIFACT_KINDS.issubset(artifact_kinds):
            problems.append("R00 artifacts omit source-tree, sdist, or wheel preimages")
        if len(artifact_kind_list) != len(artifact_kinds):
            problems.append("R00 artifact kinds must be unique; no claim may hide behind a duplicate")
        if not R00_REQUIRED_MANIFESTS.issubset(receipt["manifests"]):
            problems.append("R00 manifests omit contract, golden-vector, or test-collection identity")
        deferrals = {
            item["evidence_id"]: item for item in receipt["deferred_evidence"]
        }
        for evidence_id, milestone in R00_REQUIRED_DEFERRALS.items():
            item = deferrals.get(evidence_id)
            if item is None or item.get("later_milestone") != milestone or not item.get("owner"):
                problems.append(
                    f"R00 required deferral {evidence_id!r} is absent or not assigned to {milestone}"
                )
        ruleset = deferrals.get("branch-ruleset", {})
        if "#5" not in ruleset.get("reason", ""):
            problems.append("R00 branch-ruleset deferral does not disclose issue #5")
        replay_reason = deferrals.get("replay-evidence", {}).get("reason", "")
        if not all(control in replay_reason for control in ("CTRL-B02-001", "CTRL-B02-002")):
            problems.append("R00 replay deferral omits known B02 ledger/fence blockers")
    expected_scope = hashlib.sha256(receipt["scope"].encode("utf-8")).hexdigest()
    if receipt["scope_sha256"] != expected_scope:
        problems.append("scope_sha256 does not hash the exact UTF-8 scope string")
    draft_markers = ("MUST_REPLACE", "PLACEHOLDER", "DRAFT-")
    for path, value in _walk_strings(receipt):
        if len(value) in (40, 64) and set(value) == {"0"}:
            problems.append(f"{path} is an all-zero placeholder")
        if any(marker in value.upper() for marker in draft_markers):
            problems.append(f"{path} contains an unsealed draft marker")
    for collection, key in (
        (receipt["evidence_files"], "evidence_id"),
        (receipt["artifacts"], "name"),
        (receipt["tests"], "command"),
        (receipt["deferred_evidence"], "evidence_id"),
    ):
        values = [item[key] for item in collection]
        if len(values) != len(set(values)):
            problems.append(f"duplicate {key} in receipt")
    _validate_evidence_files(receipt, evidence_root, problems)
    if problems:
        raise ReceiptValidationError("; ".join(problems))


def _validate_evidence_files(
    receipt: dict[str, Any], evidence_root: pathlib.Path, problems: list[str]
) -> None:
    root = evidence_root.resolve()
    bound: dict[str, dict[str, Any]] = {}
    paths: set[str] = set()
    for item in receipt["evidence_files"]:
        relative = pathlib.PurePosixPath(item["path"])
        if relative.is_absolute() or ".." in relative.parts:
            problems.append(f"unsafe evidence path: {item['path']}")
            continue
        if item["path"] in paths:
            problems.append(f"duplicate evidence path: {item['path']}")
        paths.add(item["path"])
        target = (root / pathlib.Path(*relative.parts)).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            problems.append(f"evidence path escapes repository root: {item['path']}")
            continue
        if not target.is_file():
            problems.append(f"evidence file is missing: {item['path']}")
            continue
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != item["sha256"]:
            problems.append(f"evidence file digest mismatch: {item['path']}")
        for pointer in item["binds"]:
            if pointer in bound:
                problems.append(f"evidence field is bound more than once: {pointer}")
            bound[pointer] = item
            try:
                value = _resolve_pointer(receipt, pointer)
            except (KeyError, IndexError, TypeError, ValueError):
                problems.append(f"evidence binding does not resolve: {pointer}")
                continue
            if value != item["sha256"]:
                problems.append(f"evidence binding digest mismatch: {pointer}")
            expected_kind = _expected_evidence_kind(pointer)
            if expected_kind != item["kind"]:
                problems.append(
                    f"evidence kind {item['kind']!r} cannot bind {pointer}; "
                    f"expected {expected_kind!r}"
                )
            _validate_typed_evidence(receipt, item, pointer, target, problems)

    required = set(_required_digest_pointers(receipt))
    missing = sorted(required - bound.keys())
    extra = sorted(bound.keys() - required)
    if missing:
        problems.append(f"digest fields lack persisted preimages: {missing}")
    if extra:
        problems.append(f"evidence bindings target non-evidence fields: {extra}")
    if receipt["milestone_id"] == "R00":
        _validate_r00_evidence_set(receipt, bound, root, problems)
    authority_pointer = "/authority_basis/digest_sha256"
    authority = bound.get(authority_pointer)
    if authority is not None and authority["path"] != receipt["authority_basis"]["inventory_ref"]:
        problems.append("authority inventory_ref does not name its bound evidence file")


def _required_digest_pointers(receipt: dict[str, Any]):
    yield "/authority_basis/digest_sha256"
    yield "/toolchain/dependency_spec_sha256"
    yield "/toolchain/dependency_snapshot_sha256"
    for index, _ in enumerate(receipt["artifacts"]):
        yield f"/artifacts/{index}/sha256"
    yield "/ci/evidence_sha256"
    yield "/ci/log_sha256"
    for index, _ in enumerate(receipt["tests"]):
        yield f"/tests/{index}/result_sha256"
        yield f"/tests/{index}/test_ids_sha256"
        yield f"/tests/{index}/log_sha256"
    for name in receipt["manifests"]:
        yield "/manifests/" + name.replace("~", "~0").replace("/", "~1")
    yield "/negative_capability/result_sha256"
    yield "/review/review_sha256"
    yield "/review/api_export_sha256"
    yield "/merge_control/evidence_sha256"
    yield "/post_merge/command_set_sha256"
    yield "/post_merge/setup_log_sha256"
    yield "/post_merge/result_sha256"


def _expected_evidence_kind(pointer: str) -> str:
    if pointer == "/authority_basis/digest_sha256":
        return "authority-basis"
    if pointer == "/toolchain/dependency_spec_sha256":
        return "dependency-spec"
    if pointer == "/toolchain/dependency_snapshot_sha256":
        return "dependency-snapshot"
    if pointer.startswith("/artifacts/"):
        return "artifact"
    if pointer == "/ci/evidence_sha256":
        return "ci"
    if pointer == "/ci/log_sha256":
        return "ci-log"
    if pointer.startswith("/tests/") and pointer.endswith("/result_sha256"):
        return "test-result"
    if pointer.startswith("/tests/") and pointer.endswith("/test_ids_sha256"):
        return "test-ids"
    if pointer.startswith("/tests/") and pointer.endswith("/log_sha256"):
        return "command-log"
    if pointer.startswith("/manifests/"):
        return "manifest"
    if pointer == "/negative_capability/result_sha256":
        return "negative-capability"
    if pointer == "/review/review_sha256":
        return "review"
    if pointer == "/review/api_export_sha256":
        return "review-api"
    if pointer == "/merge_control/evidence_sha256":
        return "merge"
    if pointer == "/post_merge/command_set_sha256":
        return "command-set"
    if pointer == "/post_merge/setup_log_sha256":
        return "setup-log"
    if pointer == "/post_merge/result_sha256":
        return "post-merge-result"
    return "<invalid>"


def _validate_typed_evidence(
    receipt: dict[str, Any],
    item: dict[str, Any],
    pointer: str,
    target: pathlib.Path,
    problems: list[str],
) -> None:
    typed = {
        "authority-basis",
        "dependency-snapshot",
        "ci",
        "test-result",
        "negative-capability",
        "review",
        "merge",
        "command-set",
        "post-merge-result",
    }
    source_artifact = False
    if item["kind"] == "artifact" and pointer.startswith("/artifacts/"):
        index = int(pointer.split("/")[2])
        source_artifact = receipt["artifacts"][index]["kind"] == "source-tree"
    if (item["kind"] not in typed and not source_artifact) or not target.is_file():
        return
    try:
        raw = target.read_bytes()
        record = json.loads(raw)
        if not isinstance(record, dict):
            raise ValueError("record root is not an object")
        if canonical_json(record) != raw:
            raise ValueError("record bytes are not exact canonical JSON")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        problems.append(f"typed evidence is not canonical JSON: {item['path']}: {exc}")
        return

    if source_artifact:
        _compare_record(
            record,
            {
                "schema": "origin.source-tree-evidence.v1",
                "repository": receipt["merge_control"]["repository"],
                "merge_sha": receipt["merge_sha"],
                "tree_sha": receipt["merge_control"]["tree_sha"],
            },
            item["path"],
            problems,
        )
        files = record.get("files")
        if not isinstance(files, list) or not files:
            problems.append(f"source-tree evidence has no file inventory: {item['path']}")
        if set(record) != {"schema", "repository", "merge_sha", "tree_sha", "files"}:
            problems.append(f"source-tree evidence has contradictory unknown fields: {item['path']}")
    elif item["kind"] == "authority-basis":
        _compare_record(
            record,
            {
                "schema": "origin.authority-basis-evidence.v1",
                "status": receipt["authority_basis"]["status"],
                "canonical": receipt["authority_basis"]["canonical"],
            },
            item["path"],
            problems,
        )
        if not isinstance(record.get("sources"), list) or not record["sources"]:
            problems.append(f"authority evidence has no source inventory: {item['path']}")
    elif item["kind"] == "dependency-snapshot":
        _compare_record(
            record,
            {
                "schema": "origin.toolchain-evidence.v1",
                "python_version": receipt["toolchain"]["python_version"],
                "platform": receipt["toolchain"]["platform"],
                "runner_image": receipt["toolchain"]["runner_image"],
                "dependency_spec_sha256": receipt["toolchain"]["dependency_spec_sha256"],
            },
            item["path"],
            problems,
        )
        if not isinstance(record.get("packages"), list):
            problems.append(f"toolchain evidence packages is not a list: {item['path']}")
    elif item["kind"] == "ci":
        _compare_record(
            record,
            {
                "schema": "origin.ci-evidence.v1",
                "provider": receipt["ci"]["provider"],
                "run_id": receipt["ci"]["run_id"],
                "head_sha": receipt["ci"]["head_sha"],
                "conclusion": receipt["ci"]["conclusion"],
                "log_sha256": receipt["ci"]["log_sha256"],
            },
            item["path"],
            problems,
        )
        if not isinstance(record.get("job_id"), str) or not record["job_id"].isdigit():
            problems.append(f"CI evidence lacks a decimal job_id: {item['path']}")
        if receipt["milestone_id"] == "R00" and record.get("commands") != R00_REQUIRED_COMMANDS:
            problems.append(f"CI evidence omits the controlled R00 command set: {item['path']}")
    elif item["kind"] == "test-result":
        index = int(pointer.split("/")[2])
        test = receipt["tests"][index]
        _compare_record(
            record,
            {
                "schema": "origin.test-result-evidence.v1",
                "head_sha": receipt["merge_sha"],
                "command": test["command"],
                "exit_code": test["exit_code"],
                "passed": test["passed"],
                "skips": test["skips"],
                "xfails": test["xfails"],
                "test_ids_sha256": test["test_ids_sha256"],
                "log_sha256": test["log_sha256"],
            },
            item["path"],
            problems,
        )
    elif item["kind"] == "negative-capability":
        _compare_record(
            record,
            {
                "schema": "origin.negative-capability-evidence.v1",
                "head_sha": receipt["merge_sha"],
                "scanner": receipt["negative_capability"]["scanner"],
                "forbidden_hits": receipt["negative_capability"]["forbidden_hits"],
                "result": "PASS",
            },
            item["path"],
            problems,
        )
    elif item["kind"] == "review":
        _compare_record(
            record,
            {
                "schema": "origin.review-evidence.v1",
                "head_sha": receipt["head_sha"],
                "reviewer": receipt["review"]["reviewer"],
                "unresolved_actionable_threads": receipt["review"][
                    "unresolved_actionable_threads"
                ],
                "verdict": "PASS",
            },
            item["path"],
            problems,
        )
        if set(record) != {
            "schema", "head_sha", "reviewer", "unresolved_actionable_threads", "verdict",
            "reviewed_prs", "inherited_thread_count", "pr4_thread_count", "threads",
            "final_review",
        }:
            problems.append(f"review evidence has contradictory unknown fields: {item['path']}")
        threads = record.get("threads")
        if not isinstance(threads, list):
            problems.append(f"review evidence contains unresolved actionable threads: {item['path']}")
        else:
            if receipt["milestone_id"] == "R00":
                if record.get("reviewed_prs") != sorted(R00_REVIEW_PRS):
                    problems.append(
                        f"R00 review evidence omits PR #1-#4 or corrective PR #7: "
                        f"{item['path']}"
                    )
                inherited = [
                    thread for thread in threads
                    if isinstance(thread, dict) and thread.get("pr_number") in {1, 2, 3}
                ]
                current = [
                    thread for thread in threads
                    if isinstance(thread, dict) and thread.get("pr_number") == 4
                ]
                if (
                    record.get("inherited_thread_count") != 14
                    or len(inherited) != 14
                    or any(
                        thread.get("actionable") is not True
                        or thread.get("resolved") is not True
                        for thread in inherited
                    )
                ):
                    problems.append(
                        f"R00 review evidence omits the 14 inherited threads: {item['path']}"
                    )
                if record.get("pr4_thread_count") != len(current) or not current:
                    problems.append(f"R00 review evidence omits PR #4 thread inventory: {item['path']}")
                final_review = record.get("final_review")
                if (
                    not isinstance(final_review, dict)
                    or not isinstance(final_review.get("review_id"), str)
                    or not final_review.get("review_id")
                    or final_review.get("head_sha") != receipt["head_sha"]
                    or final_review.get("verdict") != "PASS"
                    or not isinstance(final_review.get("reviewer"), str)
                    or not final_review.get("reviewer")
                    or not isinstance(final_review.get("url"), str)
                    or not final_review["url"].startswith(
                        f"https://github.com/TriadAgentic/TriadOrigin/pull/"
                        f"{R00_RECEIPT_PR}#"
                    )
                ):
                    problems.append(f"R00 final-head review evidence is incomplete: {item['path']}")
            required_thread_fields = {
                "thread_id", "pr_number", "url", "actionable", "resolved", "disposition"
            }
            thread_ids: set[str] = set()
            thread_urls: set[str] = set()
            computed_unresolved = 0
            for thread in threads:
                if not isinstance(thread, dict) or not required_thread_fields.issubset(thread):
                    problems.append(f"review evidence has incomplete thread inventory: {item['path']}")
                    break
                thread_id = thread.get("thread_id")
                url = thread.get("url")
                disposition = thread.get("disposition")
                pr_number = thread.get("pr_number")
                actionable = thread.get("actionable")
                resolved = thread.get("resolved")
                if (
                    not isinstance(thread_id, str) or not thread_id
                    or not isinstance(url, str)
                    or not isinstance(disposition, str) or not disposition
                    or isinstance(pr_number, bool) or pr_number not in R00_REVIEW_PRS
                    or not isinstance(actionable, bool)
                    or not isinstance(resolved, bool)
                ):
                    problems.append(f"review evidence has invalid thread identity: {item['path']}")
                    break
                expected_prefix = (
                    f"https://github.com/TriadAgentic/TriadOrigin/pull/{pr_number}#"
                )
                if not url.startswith(expected_prefix):
                    problems.append(f"review thread URL contradicts repository/PR: {item['path']}")
                    break
                if thread_id in thread_ids or url in thread_urls:
                    problems.append(f"review evidence repeats a thread identity: {item['path']}")
                    break
                thread_ids.add(thread_id)
                thread_urls.add(url)
                if actionable and not resolved:
                    computed_unresolved += 1
            if computed_unresolved != record.get("unresolved_actionable_threads"):
                problems.append(f"review unresolved count does not match inventory: {item['path']}")
            if computed_unresolved:
                problems.append(f"review evidence contains unresolved actionable threads: {item['path']}")
    elif item["kind"] == "merge":
        _compare_record(
            record,
            {
                "schema": "origin.merge-evidence.v1",
                "repository": receipt["merge_control"]["repository"],
                "pr_number": receipt["merge_control"]["pr_number"],
                "method": receipt["merge_control"]["method"],
                "base_sha": receipt["base_sha"],
                "head_sha": receipt["head_sha"],
                "expected_head_sha": receipt["merge_control"]["expected_head_sha"],
                "merge_sha": receipt["merge_sha"],
                "tree_sha": receipt["merge_control"]["tree_sha"],
                "expected_head_guard": True,
                "url": receipt["merge_control"]["url"],
            },
            item["path"],
            problems,
        )
    elif item["kind"] == "command-set":
        _compare_record(
            record,
            {
                "schema": "origin.command-set-evidence.v1",
                "fresh_main_sha": receipt["merge_sha"],
                "fresh_reconstruction": True,
                "commands": [test["command"] for test in receipt["tests"]],
                "clone_performed": True,
                "branch": "main",
                "origin_main_sha": receipt["merge_sha"],
                "working_tree_clean": True,
                "setup_log_sha256": receipt["post_merge"]["setup_log_sha256"],
            },
            item["path"],
            problems,
        )
        if set(record) != {
            "schema", "fresh_main_sha", "fresh_reconstruction", "clone_performed", "branch",
            "origin_main_sha", "working_tree_clean", "commands", "environment", "setup",
            "setup_log_sha256",
        }:
            problems.append(f"command-set evidence has contradictory unknown fields: {item['path']}")
        if not isinstance(record.get("environment"), dict):
            problems.append(f"command-set evidence environment is not an object: {item['path']}")
        target_root = "/fresh/checkout"
        repository_url = (
            f"https://github.com/{receipt['merge_control']['repository']}.git"
        )
        constraint = f"{target_root}/constraints/ci.txt"
        expected_setup = [
            {
                "command": f"git clone --no-local {repository_url} {target_root}",
                "kind": "fresh-clone",
                "target": target_root,
            },
            {
                "command": f"git -C {target_root} rev-parse HEAD",
                "expected_sha": receipt["merge_sha"],
                "kind": "checkout-identity",
            },
            {
                "command": f"git -C {target_root} branch --show-current",
                "expected": "main",
                "kind": "branch-identity",
            },
            {
                "command": f"git -C {target_root} rev-parse origin/main",
                "expected_sha": receipt["merge_sha"],
                "kind": "remote-main-identity",
            },
            {
                "command": f"git -C {target_root} status --porcelain=v1",
                "expected": "",
                "kind": "clean-tree",
            },
            {
                "command": "python -m pip install -e '.[test]'",
                "constraint_path": constraint,
                "cwd": target_root,
                "kind": "install",
            },
        ]
        if record.get("setup") != expected_setup:
            problems.append(f"command-set fresh reconstruction setup mismatch: {item['path']}")
        if record.get("environment", {}).get("PIP_CONSTRAINT") != constraint:
            problems.append(f"command-set environment does not enforce PIP_CONSTRAINT: {item['path']}")
    elif item["kind"] == "post-merge-result":
        _compare_record(
            record,
            {
                "schema": "origin.post-merge-evidence.v1",
                "fresh_main_sha": receipt["post_merge"]["fresh_main_sha"],
                "reproduced": receipt["post_merge"]["reproduced"],
                "command_set_sha256": receipt["post_merge"]["command_set_sha256"],
                "toolchain_snapshot_sha256": receipt["toolchain"][
                    "dependency_snapshot_sha256"
                ],
                "setup_log_sha256": receipt["post_merge"]["setup_log_sha256"],
                "command_results": [test["result_sha256"] for test in receipt["tests"]],
                "command_logs": [test["log_sha256"] for test in receipt["tests"]],
                "result": "PASS",
            },
            item["path"],
            problems,
        )


def _validate_r00_evidence_set(
    receipt: dict[str, Any],
    bound: dict[str, dict[str, Any]],
    root: pathlib.Path,
    problems: list[str],
) -> None:
    """Validate R00 evidence content, not only the hashes of opaque files."""

    def target(pointer: str) -> pathlib.Path | None:
        item = bound.get(pointer)
        if item is None:
            return None
        return root / pathlib.Path(*pathlib.PurePosixPath(item["path"]).parts)

    # A dependency snapshot must identify a non-empty exact-pin set and cover the committed
    # constraint specification. An empty JSON list is not a toolchain identity.
    spec_path = target("/toolchain/dependency_spec_sha256")
    snapshot_path = target("/toolchain/dependency_snapshot_sha256")
    if spec_path is not None and snapshot_path is not None:
        try:
            spec_lines = {
                line.strip() for line in spec_path.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            }
            snapshot = json.loads(snapshot_path.read_bytes())
            packages = snapshot.get("packages") if isinstance(snapshot, dict) else None
            if (
                not isinstance(packages, list)
                or not packages
                or any(not isinstance(package, str) or "==" not in package for package in packages)
                or not spec_lines.issubset(set(packages))
            ):
                problems.append("R00 toolchain snapshot is empty, unpinned, or omits constraints")
        except (OSError, UnicodeError, json.JSONDecodeError):
            problems.append("R00 toolchain/constraint evidence cannot be read")

    artifact_by_kind = {
        artifact["kind"]: (index, artifact)
        for index, artifact in enumerate(receipt["artifacts"])
    }
    artifact_hashes: dict[str, str] = {}
    source_files: dict[str, bytes] = {}
    source_entry = artifact_by_kind.get("source-tree")
    if source_entry is not None:
        source_index, _ = source_entry
        source_path = target(f"/artifacts/{source_index}/sha256")
        if source_path is not None:
            source_files = _validate_source_tree_evidence(
                source_path,
                root,
                receipt["merge_sha"],
                receipt["merge_control"]["tree_sha"],
                problems,
            )
    _validate_r00_authority_and_manifests(receipt, target, source_files, problems)
    for kind in ("sdist", "wheel"):
        entry = artifact_by_kind.get(kind)
        if entry is None:
            continue
        index, artifact = entry
        artifact_hashes[kind] = artifact["sha256"]
        path = target(f"/artifacts/{index}/sha256")
        if path is None:
            continue
        try:
            data = path.read_bytes()
            if kind == "sdist":
                with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as archive:
                    members: dict[str, bytes] = {}
                    directories: set[str] = set()
                    for member in archive.getmembers():
                        relative = pathlib.PurePosixPath(member.name)
                        if relative.is_absolute() or ".." in relative.parts:
                            raise ValueError("unsafe sdist member")
                        if member.isdir():
                            directory = member.name.rstrip("/")
                            if not directory or directory in directories:
                                raise ValueError("duplicate sdist directory")
                            directories.add(directory)
                            continue
                        if not member.isfile() or member.name in members:
                            raise ValueError("non-regular or duplicate sdist member")
                        stream = archive.extractfile(member)
                        if stream is None:
                            raise ValueError("unreadable sdist member")
                        members[member.name] = stream.read()
                    if not _archive_directories_safe(directories, set(members)):
                        raise ValueError("sdist has a file/directory path conflict")
                    names = set(members)
                    pkg_info_name = next(
                        (name for name in names if name.endswith("/PKG-INFO")), None
                    )
                    pkg_info = members.get(pkg_info_name, b"")
                prefix = "triad_origin-7.0.0rc1.post1/"
                required = {
                    prefix + "PKG-INFO",
                    prefix + "pyproject.toml",
                    prefix + "setup.cfg",
                    prefix + "setup.py",
                    prefix + "src/triad_origin/__init__.py",
                    prefix + "contracts/registry/index.json",
                }
                if not required.issubset(names) or not _distribution_metadata_ok(
                    pkg_info, source_files
                ):
                    raise ValueError("sdist identity/content is incomplete")
                expected = {
                    prefix + source_path: source_data
                    for source_path, source_data in source_files.items()
                    if source_path.startswith(("src/triad_origin/", "contracts/"))
                    or source_path in {
                        "MANIFEST.in", "README.md", "constraints/ci.txt",
                        "pyproject.toml", "setup.py",
                    }
                }
                actual_critical = {
                    name: payload for name, payload in members.items()
                    if name.startswith((prefix + "src/triad_origin/", prefix + "contracts/"))
                    or name in {prefix + path for path in (
                        "MANIFEST.in", "README.md", "constraints/ci.txt",
                        "pyproject.toml", "setup.py",
                    )}
                }
                if not expected or actual_critical != expected:
                    raise ValueError("sdist bytes do not match the reviewed source tree")
                generated = {
                    "PKG-INFO",
                    "setup.cfg",
                    "src/triad_origin.egg-info/PKG-INFO",
                    "src/triad_origin.egg-info/SOURCES.txt",
                    "src/triad_origin.egg-info/dependency_links.txt",
                    "src/triad_origin.egg-info/requires.txt",
                    "src/triad_origin.egg-info/top_level.txt",
                }
                for name, payload in members.items():
                    if not name.startswith(prefix):
                        raise ValueError("sdist has a member outside its distribution root")
                    relative_name = name.removeprefix(prefix)
                    if relative_name in source_files:
                        if payload != source_files[relative_name]:
                            raise ValueError("sdist source member differs from reviewed bytes")
                    elif relative_name not in generated:
                        raise ValueError("sdist has an unreviewed extra member")
                if members[prefix + "setup.cfg"] != (
                    b"[egg_info]\ntag_build = \ntag_date = 0\n\n"
                ):
                    raise ValueError("sdist generated setup.cfg is not the controlled form")
            else:
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    members = {}
                    directories = set()
                    for info in archive.infolist():
                        relative = pathlib.PurePosixPath(info.filename)
                        if (
                            relative.is_absolute()
                            or ".." in relative.parts
                            or info.is_dir()
                            or info.filename in members
                        ):
                            if info.is_dir() and not (
                                relative.is_absolute() or ".." in relative.parts
                            ):
                                directory = info.filename.rstrip("/")
                                if not directory or directory in directories:
                                    raise ValueError("duplicate wheel directory")
                                directories.add(directory)
                                continue
                            raise ValueError("unsafe or duplicate wheel member")
                        members[info.filename] = archive.read(info)
                    if not _archive_directories_safe(directories, set(members)):
                        raise ValueError("wheel has a file/directory path conflict")
                    names = set(members)
                    metadata_name = next(
                        (name for name in names if name.endswith(".dist-info/METADATA")), None
                    )
                    metadata = members.get(metadata_name, b"")
                dist_info = "triad_origin-7.0.0rc1.post1.dist-info/"
                required = {
                    "triad_origin/__init__.py",
                    "triad_origin/_contracts/registry/index.json",
                    dist_info + "WHEEL",
                    dist_info + "METADATA",
                    dist_info + "RECORD",
                }
                if not required.issubset(names) or not _distribution_metadata_ok(
                    metadata, source_files
                ):
                    raise ValueError("wheel identity/content is incomplete")
                expected = {}
                for source_path, source_data in source_files.items():
                    if source_path.startswith("src/triad_origin/"):
                        expected["triad_origin/" + source_path.removeprefix(
                            "src/triad_origin/"
                        )] = source_data
                    elif source_path.startswith("contracts/"):
                        expected["triad_origin/_contracts/" + source_path.removeprefix(
                            "contracts/"
                        )] = source_data
                actual_package = {
                    name: payload for name, payload in members.items()
                    if name.startswith("triad_origin/")
                }
                if not expected or actual_package != expected:
                    raise ValueError("wheel bytes do not match the reviewed source tree")
                allowed_dist_info = {
                    dist_info + "METADATA",
                    dist_info + "WHEEL",
                    dist_info + "top_level.txt",
                    dist_info + "RECORD",
                }
                if set(members) != set(expected) | allowed_dist_info:
                    raise ValueError("wheel has an unreviewed package or executable member")
                if members[dist_info + "top_level.txt"] != b"triad_origin\n":
                    raise ValueError("wheel top-level package declaration is not controlled")
                if members[dist_info + "WHEEL"] != (
                    b"Wheel-Version: 1.0\n"
                    b"Generator: setuptools (79.0.1)\n"
                    b"Root-Is-Purelib: true\n"
                    b"Tag: py3-none-any\n\n"
                ):
                    raise ValueError("wheel compatibility metadata is not the controlled form")
                if not _wheel_record_ok(members, dist_info + "RECORD"):
                    raise ValueError("wheel RECORD does not authenticate every member")
        except (OSError, tarfile.TarError, zipfile.BadZipFile, ValueError):
            problems.append(f"R00 {kind} evidence is not a valid distribution archive")

    repro_index = R00_REQUIRED_COMMANDS.index("python tools/verify_reproducible_build.py")
    repro_log = target(f"/tests/{repro_index}/log_sha256")
    if repro_log is not None and {"sdist", "wheel"}.issubset(artifact_hashes):
        try:
            line = repro_log.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            line = ""
        expected = (
            f"OK: reproducible sdist={artifact_hashes['sdist']} "
            f"wheel={artifact_hashes['wheel']}\n"
        )
        if line != expected:
            problems.append("R00 reproducible-build log does not bind sdist/wheel artifacts")

    # Every command has a canonical, unique ID corpus reconciled to its result counts. R00 permits
    # no silent skips or xfails; a future milestone may add explicit owned dispositions instead.
    pytest_id_sets: list[list[str]] = []
    for index, test in enumerate(receipt["tests"]):
        if test["skips"] != 0 or test["xfails"] != 0:
            problems.append(f"R00 test command {index} has undispositioned skips/xfails")
        ids_path = target(f"/tests/{index}/test_ids_sha256")
        if ids_path is None:
            continue
        try:
            raw = ids_path.read_bytes()
            text = raw.decode("utf-8")
            ids = text.splitlines()
        except (OSError, UnicodeError):
            ids = []
            raw = b""
        if (
            not ids
            or not raw.endswith(b"\n")
            or any(not node_id or any(ord(ch) < 32 for ch in node_id) for node_id in ids)
            or len(ids) != len(set(ids))
            or len(ids) != test["passed"] + test["skips"] + test["xfails"]
        ):
            problems.append(f"R00 test-ID corpus is malformed or count-mismatched: command {index}")
            continue
        if test["command"].endswith("python -m pytest"):
            if test["passed"] <= 0 or any(
                not node_id.startswith("tests/") or "::" not in node_id for node_id in ids
            ):
                problems.append(f"R00 pytest ID corpus is not a canonical node-ID list: command {index}")
            pytest_id_sets.append(ids)
        elif ids != [f"R00-GATE-{index:02d}"]:
            problems.append(f"R00 non-pytest gate ID is not controlled: command {index}")

    collection_path = target("/manifests/test_collection")
    collection_log_path = target("/manifests/test_collection_log")
    if collection_path is not None and collection_log_path is not None:
        try:
            raw = collection_path.read_bytes()
            collection = json.loads(raw)
            node_ids = collection["node_ids"]
            canonical = canonical_json(collection) == raw
            collection_log = collection_log_path.read_bytes()
            collected_from_log = collection_log.decode("utf-8").splitlines()
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            collection = {}
            node_ids = []
            collection_log = b""
            collected_from_log = []
            canonical = False
        if (
            not canonical
            or collection.get("schema") != "origin.pytest-collection-evidence.v1"
            or collection.get("head_sha") != receipt["merge_sha"]
            or collection.get("command") != "python tools/collect_test_ids.py"
            or collection.get("pytest_args") != [
                "-o", "addopts=", "--collect-only", "-p", "no:terminal"
            ]
            or collection.get("log_sha256") != receipt["manifests"]["test_collection_log"]
            or not isinstance(node_ids, list)
            or not node_ids
            or collection.get("collected") != len(node_ids)
            or len(node_ids) != len(set(node_ids))
            or any(
                not isinstance(node_id, str)
                or not node_id.startswith("tests/")
                or "::" not in node_id
                or not (root / node_id.split("::", 1)[0]).is_file()
                for node_id in node_ids
            )
        ):
            problems.append("R00 pytest collection export is malformed or not merge-SHA bound")
        elif (
            node_ids != collected_from_log
            or not collection_log.endswith(b"\n")
            or len(pytest_id_sets) != 2
            or any(ids != node_ids for ids in pytest_id_sets)
        ):
            problems.append("R00 seed test-ID sets differ from the persisted pytest collection")
        collector_index = R00_REQUIRED_COMMANDS.index("python tools/collect_test_ids.py")
        collector_log = target(f"/tests/{collector_index}/log_sha256")
        if collector_log is None or collector_log.read_bytes() != collection_log:
            problems.append("R00 test collection is not bound to the collector command log")
        try:
            with tempfile.TemporaryDirectory(prefix="triad-r00-collection-") as temporary:
                reviewed_root = pathlib.Path(temporary)
                for source_path, source_data in source_files.items():
                    destination = reviewed_root / pathlib.Path(
                        *pathlib.PurePosixPath(source_path).parts
                    )
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(source_data)
                collector_tool = reviewed_root / "tools" / "collect_test_ids.py"
                if not collector_tool.is_file():
                    raise OSError("controlled collector absent")
                environment = os.environ.copy()
                environment.update({
                    "LANG": "C.UTF-8",
                    "LC_ALL": "C.UTF-8",
                    "PYTHONHASHSEED": "0",
                    "PYTHONPATH": str(reviewed_root / "src"),
                    "TZ": "UTC",
                })
                recollected = subprocess.run(
                    [sys.executable, str(collector_tool)],
                    cwd=reviewed_root,
                    env=environment,
                    check=False,
                    capture_output=True,
                    timeout=120,
                )
        except (OSError, subprocess.TimeoutExpired):
            recollected = None
        if (
            recollected is None
            or recollected.returncode != 0
            or recollected.stdout != collection_log
        ):
            problems.append(
                "R00 persisted pytest collection does not equal a fresh reviewed-source collection"
            )

    review_path = target("/review/review_sha256")
    review_api_path = target("/review/api_export_sha256")
    if review_path is not None and review_api_path is not None:
        _validate_r00_review_export(
            review_path,
            review_api_path,
            receipt["head_sha"],
            receipt["merge_sha"],
            problems,
        )

    setup_path = target("/post_merge/setup_log_sha256")
    if setup_path is not None:
        expected_setup_log = (
            f"CLONE={receipt['merge_control']['repository']}\n"
            "TARGET=/fresh/checkout\n"
            f"HEAD={receipt['merge_sha']}\n"
            "BRANCH=main\n"
            f"ORIGIN_MAIN={receipt['merge_sha']}\n"
            "CLEAN=true\n"
            "INSTALL=success\n"
        ).encode()
        try:
            actual_setup_log = setup_path.read_bytes()
        except OSError:
            actual_setup_log = b""
        if actual_setup_log != expected_setup_log:
            problems.append("R00 fresh-main setup log does not prove clone/main/clean/install identity")


def _validate_r00_authority_and_manifests(
    receipt: dict[str, Any],
    target,
    source_files: dict[str, bytes],
    problems: list[str],
) -> None:
    authority_path = target("/authority_basis/digest_sha256")
    inventory_bytes = source_files.get(R00_AUTHORITY_INVENTORY_PATH)
    if authority_path is not None:
        try:
            raw = authority_path.read_bytes()
            authority = json.loads(raw)
        except (OSError, UnicodeError, json.JSONDecodeError):
            authority = None
        if (
            not isinstance(authority, dict)
            or canonical_json(authority) != raw
            or set(authority) != {
                "canonical", "inventory_path", "inventory_sha256", "missing_members",
                "schema", "sources", "status",
            }
            or authority.get("schema") != "origin.authority-basis-evidence.v1"
            or authority.get("status") != "INCOMPLETE_AUDIT_BASIS"
            or authority.get("canonical") is not False
            or authority.get("inventory_path") != R00_AUTHORITY_INVENTORY_PATH
            or inventory_bytes is None
            or authority.get("inventory_sha256") != hashlib.sha256(inventory_bytes).hexdigest()
            or authority.get("sources") != R00_AUTHORITY_SOURCES
            or authority.get("missing_members") != R00_AUTHORITY_MISSING
        ):
            problems.append("R00 authority basis does not bind the closed supplied-source inventory")

    contract_path = target("/manifests/contracts")
    golden_path = target("/manifests/golden_vectors")
    source_manifest = source_files.get("contracts/MANIFEST.sha256")
    if contract_path is None or golden_path is None or source_manifest is None:
        problems.append("R00 contract/golden manifest evidence is absent from reviewed source")
        return
    try:
        contract_bytes = contract_path.read_bytes()
        golden_bytes = golden_path.read_bytes()
    except OSError:
        problems.append("R00 contract/golden manifest evidence cannot be read")
        return
    path_rows: list[tuple[str, str, bytes]] = []
    identity_rows: list[tuple[str, str]] = []
    for raw_line in source_manifest.splitlines(keepends=True):
        if not raw_line.endswith(b"\n"):
            problems.append("R00 reviewed contract manifest lacks canonical line termination")
            return
        try:
            line = raw_line[:-1].decode("ascii")
        except UnicodeError:
            problems.append("R00 reviewed contract manifest is not ASCII")
            return
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            problems.append("R00 reviewed contract manifest has a malformed row")
            return
        digest, name = match.groups()
        if name.startswith("contracts/"):
            path_rows.append((name, digest, raw_line))
        else:
            identity_rows.append((name, digest))
    expected_paths = sorted(
        path for path in source_files
        if path.startswith(("contracts/golden/", "contracts/registry/", "contracts/schemas/"))
    )
    row_paths = [path for path, _, _ in path_rows]
    rows_valid = (
        len(path_rows) == 91
        and row_paths == expected_paths
        and len(row_paths) == len(set(row_paths))
        and identity_rows == [
            ("origin.contracts.1.0.0-RC1", "5189c78ae315850d0f2ab230dd4cb00ba6af693af2fec6e69f52e0c9c0dd3fe1")
        ]
        and all(
            hashlib.sha256(source_files[path]).hexdigest() == digest
            for path, digest, _ in path_rows
        )
    )
    expected_golden = b"".join(
        raw_line for path, _, raw_line in path_rows if path.startswith("contracts/golden/")
    )
    if contract_bytes != source_manifest or not rows_valid:
        problems.append("R00 contract manifest does not authenticate the 91 reviewed artifacts")
    if golden_bytes != expected_golden or len(expected_golden.splitlines()) != 60:
        problems.append("R00 golden manifest does not equal the reviewed 60-vector inventory")


def _distribution_metadata_ok(data: bytes, source_files: dict[str, bytes]) -> bool:
    try:
        metadata = BytesParser(policy=policy.default).parsebytes(data)
        project = tomllib.loads(source_files["pyproject.toml"].decode("utf-8"))["project"]
        dependencies = project.get("dependencies", [])
        optional = project.get("optional-dependencies", {})
        expected_requirements = list(dependencies)
        for extra, requirements in optional.items():
            expected_requirements.extend(
                f'{requirement}; extra == "{extra}"' for requirement in requirements
            )
    except (KeyError, TypeError, UnicodeError, tomllib.TOMLDecodeError):
        return False
    actual_requirements = metadata.get_all("Requires-Dist", [])
    actual_extras = metadata.get_all("Provides-Extra", [])
    return (
        len(metadata.get_all("Name", [])) == 1
        and len(metadata.get_all("Version", [])) == 1
        and len(metadata.get_all("Requires-Python", [])) == 1
        and metadata.get("Name") == project.get("name") == "triad-origin"
        and metadata.get("Version") == project.get("version") == "7.0.0rc1.post1"
        and metadata.get("Requires-Python") == project.get("requires-python") == ">=3.11"
        and len(actual_requirements) == len(set(actual_requirements))
        and set(actual_requirements) == set(expected_requirements)
        and len(actual_extras) == len(set(actual_extras))
        and set(actual_extras) == set(optional)
    )


def _wheel_record_ok(members: dict[str, bytes], record_name: str) -> bool:
    try:
        rows = list(csv.reader(io.StringIO(members[record_name].decode("utf-8"))))
    except (KeyError, UnicodeError, csv.Error):
        return False
    if any(len(row) != 3 for row in rows):
        return False
    entries = {row[0]: (row[1], row[2]) for row in rows}
    if len(entries) != len(rows) or set(entries) != set(members):
        return False
    for name, payload in members.items():
        digest, size = entries[name]
        if name == record_name:
            if digest or size:
                return False
            continue
        encoded = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b"=").decode()
        if digest != f"sha256={encoded}" or size != str(len(payload)):
            return False
    return True


def _archive_directories_safe(directories: set[str], files: set[str]) -> bool:
    parents: set[str] = set()
    for name in files:
        parts = pathlib.PurePosixPath(name).parts
        parents.update("/".join(parts[:index]) for index in range(1, len(parts)))
    return not directories.intersection(files) and directories.issubset(parents)


def _validate_r00_review_export(
    review_path: pathlib.Path,
    export_path: pathlib.Path,
    head_sha: str,
    merge_sha: str,
    problems: list[str],
) -> None:
    try:
        review_raw = review_path.read_bytes()
        export_raw = export_path.read_bytes()
        review = json.loads(review_raw)
        export = json.loads(export_raw)
        if canonical_json(review) != review_raw or canonical_json(export) != export_raw:
            raise ValueError("noncanonical review evidence")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError):
        problems.append("R00 review/API evidence is not exact canonical JSON")
        return
    if (
        export.get("schema") != "origin.github-review-export.v1"
        or export.get("repository") != "TriadAgentic/TriadOrigin"
        or export.get("pagination_complete") is not True
        or export.get("page_info") != {"has_next_page": False}
        or export.get("head_sha") != head_sha
        or not isinstance(export.get("pull_requests"), list)
    ):
        problems.append("R00 GitHub review export lacks complete repository/head provenance")
        return
    exported: dict[str, tuple[int, str, bool]] = {}
    exported_rows: dict[str, dict[str, Any]] = {}
    reviews: dict[str, dict[str, Any]] = {}
    covered_prs: set[int] = set()
    for pull in export["pull_requests"]:
        if not isinstance(pull, dict) or pull.get("pr_number") not in R00_REVIEW_PRS:
            problems.append("R00 GitHub review export has an invalid pull request row")
            return
        pr_number = pull["pr_number"]
        covered_prs.add(pr_number)
        comments = pull.get("inline_threads")
        if not isinstance(comments, list):
            problems.append("R00 GitHub review export omits inline thread rows")
            return
        for comment in comments:
            if not isinstance(comment, dict):
                problems.append("R00 GitHub review export has a malformed inline thread")
                return
            comment_id = comment.get("id")
            url = comment.get("url")
            expected_url = (
                f"https://github.com/TriadAgentic/TriadOrigin/pull/{pr_number}"
                f"#discussion_r{comment_id}"
            )
            if (
                not isinstance(comment_id, str)
                or not comment_id.isdigit()
                or url != expected_url
                or not isinstance(comment.get("path"), str)
                or not comment["path"]
                or not isinstance(comment.get("review_id"), str)
                or not comment["review_id"].isdigit()
                or not isinstance(comment.get("is_resolved"), bool)
                or comment_id in exported
            ):
                problems.append("R00 GitHub review export has invalid/duplicate thread identity")
                return
            exported[comment_id] = (pr_number, url, comment["is_resolved"])
            exported_rows[comment_id] = comment
        for api_review in pull.get("reviews", []):
            if not isinstance(api_review, dict):
                problems.append("R00 GitHub review export has a malformed review")
                return
            review_id = api_review.get("review_id")
            if not isinstance(review_id, str) or not review_id.isdigit() or review_id in reviews:
                problems.append("R00 GitHub review export has invalid/duplicate review identity")
                return
            reviews[review_id] = api_review
    if covered_prs != R00_REVIEW_PRS:
        problems.append("R00 GitHub review export does not cover PR #1-#4 and PR #7")
    for comment_id, pr_number in R00_INHERITED_THREADS.items():
        if exported.get(comment_id, (None,))[0] != pr_number:
            problems.append("R00 GitHub review export omits a known inherited thread")
            break
    if not R00_KNOWN_PR4_THREADS.issubset(exported):
        problems.append("R00 GitHub review export omits a known PR #4 thread")
    if not R00_KNOWN_PR7_THREADS.issubset(exported):
        problems.append("R00 GitHub review export omits a known PR #7 thread")
    review_threads = review.get("threads")
    if not isinstance(review_threads, list):
        problems.append("R00 review inventory is not a list")
        return
    inventory = {
        str(thread.get("thread_id")): (
            thread.get("pr_number"), thread.get("url"), thread.get("resolved")
        )
        for thread in review_threads if isinstance(thread, dict)
    }
    if inventory != exported:
        problems.append("R00 review inventory does not exactly match the GitHub API export")
    inventory_rows = {
        str(thread.get("thread_id")): thread
        for thread in review_threads if isinstance(thread, dict)
    }
    known_actionable = (
        set(R00_INHERITED_THREADS) | R00_KNOWN_PR4_THREADS | R00_KNOWN_PR7_THREADS
    )
    for thread_id in known_actionable:
        api_thread = exported_rows.get(thread_id, {})
        inventory_thread = inventory_rows.get(thread_id, {})
        reply = api_thread.get("remediation_reply")
        pr_number = exported.get(thread_id, (None,))[0]
        expected_reply_url = (
            f"https://github.com/TriadAgentic/TriadOrigin/pull/{pr_number}"
            f"#discussion_r{reply.get('id') if isinstance(reply, dict) else ''}"
        )
        if (
            api_thread.get("is_resolved") is not True
            or inventory_thread.get("actionable") is not True
            or inventory_thread.get("resolved") is not True
            or not isinstance(inventory_thread.get("disposition"), str)
            or not inventory_thread.get("disposition")
            or not isinstance(reply, dict)
            or set(reply) != {"author", "body", "id", "url"}
            or not isinstance(reply.get("id"), str)
            or not reply["id"].isdigit()
            or not isinstance(reply.get("author"), str)
            or not reply["author"]
            or reply.get("url") != expected_reply_url
            or not isinstance(reply.get("body"), str)
            or merge_sha not in reply["body"]
            or "evidence/receipts/R00.json" not in reply["body"]
        ):
            problems.append(
                "R00 actionable review thread lacks an API-bound resolution reply and fix/receipt reference"
            )
            break
    final = review.get("final_review")
    if not isinstance(final, dict):
        problems.append("R00 final review is missing")
        return
    api_final = reviews.get(str(final.get("review_id")))
    expected_review_body = (
        f"R00_REVIEW_VERDICT: PASS\nHEAD: {head_sha}\nP0: 0\nP1: 0\n"
    )
    if (
        api_final is None
        or api_final.get("commit_id") != head_sha
        or api_final.get("url") != final.get("url")
        or api_final.get("reviewer") != final.get("reviewer")
        or api_final.get("state") not in {"APPROVED", "COMMENTED"}
        or api_final.get("body") != expected_review_body
        or final.get("body_sha256") != hashlib.sha256(
            expected_review_body.encode("utf-8")
        ).hexdigest()
    ):
        problems.append("R00 final review does not match the exact-head GitHub API export")


def _validate_source_tree_evidence(
    manifest_path: pathlib.Path,
    root: pathlib.Path,
    expected_merge_sha: str,
    expected_tree_sha: str,
    problems: list[str],
) -> dict[str, bytes]:
    try:
        raw = manifest_path.read_bytes()
        record = json.loads(raw)
        files = record["files"]
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError):
        problems.append("R00 source-tree manifest is unreadable")
        return {}
    if (
        canonical_json(record) != raw
        or record.get("schema") != "origin.source-tree-evidence.v1"
        or record.get("repository") != "TriadAgentic/TriadOrigin"
        or record.get("merge_sha") != expected_merge_sha
        or record.get("tree_sha") != expected_tree_sha
    ):
        problems.append("R00 source-tree manifest lacks canonical merge/repository provenance")
        return {}
    if not isinstance(files, list) or not files:
        problems.append("R00 source-tree manifest has no file inventory")
        return {}
    entries: list[dict[str, str]] = []
    file_data: dict[str, bytes] = {}
    seen: set[str] = set()
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {
            "path", "mode", "type", "blob_sha", "sha256"
        }:
            problems.append("R00 source-tree manifest has a malformed file entry")
            return {}
        path = entry["path"]
        relative = pathlib.PurePosixPath(path) if isinstance(path, str) else None
        if (
            relative is None
            or relative.is_absolute()
            or ".." in relative.parts
            or not relative.parts
            or path in seen
            or entry["type"] != "blob"
            or entry["mode"] not in {"100644", "100755", "120000"}
            or re.fullmatch(r"[0-9a-f]{40}", entry["blob_sha"]) is None
            or re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]) is None
        ):
            problems.append("R00 source-tree manifest has unsafe or duplicate file identity")
            return {}
        seen.add(path)
        target = root / pathlib.Path(*relative.parts)
        try:
            if entry["mode"] == "120000":
                if not target.is_symlink():
                    raise OSError("expected symlink")
                data = target.readlink().as_posix().encode()
            else:
                if not target.is_file() or target.is_symlink():
                    raise OSError("expected regular file")
                data = target.read_bytes()
                actual_mode = "100755" if target.stat().st_mode & 0o111 else "100644"
                if actual_mode != entry["mode"]:
                    raise OSError("mode mismatch")
        except OSError:
            problems.append(f"R00 source-tree file is missing or has wrong mode: {path}")
            return {}
        blob_sha = hashlib.sha1(
            f"blob {len(data)}\0".encode() + data, usedforsecurity=False
        ).hexdigest()
        if blob_sha != entry["blob_sha"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
            problems.append(f"R00 source-tree file digest mismatch: {path}")
            return {}
        entries.append(entry)
        file_data[path] = data
    if [entry["path"] for entry in entries] != sorted(seen):
        problems.append("R00 source-tree manifest paths are not in canonical sorted order")
        return {}
    if _git_tree_sha(entries) != expected_tree_sha:
        problems.append("R00 source-tree inventory does not reconstruct the merge tree SHA")
        return {}
    return file_data


def _git_tree_sha(entries: list[dict[str, str]]) -> str:
    root: dict[str, Any] = {}
    for entry in entries:
        parts = entry["path"].split("/")
        node = root
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = entry

    def digest(node: dict[str, Any]) -> str:
        material: list[tuple[str, str, str]] = []
        for name, value in node.items():
            if isinstance(value, dict) and "blob_sha" not in value:
                material.append((name + "/", "40000", digest(value)))
            else:
                material.append((name, value["mode"], value["blob_sha"]))
        content = b"".join(
            mode.encode() + b" " + name.rstrip("/").encode() + b"\0" + bytes.fromhex(sha)
            for name, mode, sha in sorted(material, key=lambda item: item[0].encode())
        )
        return hashlib.sha1(
            f"tree {len(content)}\0".encode() + content, usedforsecurity=False
        ).hexdigest()

    return digest(root)


def _compare_record(
    record: dict[str, Any],
    expected: dict[str, Any],
    path: str,
    problems: list[str],
) -> None:
    for name, value in expected.items():
        if record.get(name) != value:
            problems.append(f"typed evidence claim mismatch: {path}:{name}")


def _resolve_pointer(document: Any, pointer: str) -> Any:
    if not pointer.startswith("/"):
        raise ValueError("not a JSON pointer")
    value = document
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            value = value[int(token)]
        elif isinstance(value, dict):
            value = value[token]
        else:
            raise TypeError("pointer descends through a scalar")
    return value


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) not in (1, 2):
        print("usage: validate_milestone_receipt.py RECEIPT [SCHEMA]", file=sys.stderr)
        return 2
    receipt_path = pathlib.Path(args[0])
    schema_path = pathlib.Path(args[1]) if len(args) == 2 else DEFAULT_SCHEMA
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validate_receipt(receipt, schema, evidence_root=ROOT)
    except (OSError, json.JSONDecodeError, jsonschema.ValidationError, ReceiptValidationError) as exc:
        print(f"FAIL: milestone receipt invalid: {exc}", file=sys.stderr)
        return 1
    print(f"OK: milestone receipt {receipt['receipt_id']} is structurally and semantically bound")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
