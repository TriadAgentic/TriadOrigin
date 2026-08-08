"""Milestone receipts bind every claim-bearing digest to a persisted typed preimage."""

from __future__ import annotations

import base64
import csv
import copy
import hashlib
import io
import json
import pathlib
import subprocess
import tarfile
import zipfile

import jsonschema
import pytest

from triad_origin.canonical import canonical_json
from tools.validate_milestone_receipt import (
    R00_FAILED_ATTEMPT,
    R00_INHERITED_THREADS,
    R00_IMPLEMENTATION_HEAD_SHA,
    R00_IMPLEMENTATION_MERGE_SHA,
    R00_IMPLEMENTATION_REVIEW_BODY,
    R00_IMPLEMENTATION_REVIEW_ID,
    R00_IMPLEMENTATION_REVIEW_URL,
    R00_IMPLEMENTATION_REVIEWER,
    R00_KNOWN_PR4_THREADS,
    R00_KNOWN_PR7_THREADS,
    R00_PR_AUTHOR,
    R00_RECEIPT_PR,
    R00_REQUIRED_REVIEWER,
    R00_REVIEWED_ROOTS,
    R00_REVIEW_PRS,
    R00_REQUIRED_CI_STEPS,
    R00_REQUIRED_COMMANDS,
    R00_REVIEW_THREADS_QUERY,
    ReceiptValidationError,
    _exact_dependency_pin_name,
    _expected_codex_review_body,
    _expected_remediation_reply_body,
    _github_get_json_from_token,
    _github_get_review_threads_from_token,
    _git_tree_sha,
    validate_receipt as _validate_receipt_impl,
)

SCHEMA_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / "docs"
    / "plan"
    / "milestone_receipt.schema.json"
)
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE40 = R00_IMPLEMENTATION_MERGE_SHA
HEAD40 = "2" * 40
SCOPE = "repository integrity refreeze"
CONSTRAINT = "/fresh/checkout/constraints/ci.txt"
SOURCE_PATH = "src/triad_origin/__init__.py"
SOURCE_BYTES = b'__version__ = "7.0.0rc1.post1"\n'
TEST_SOURCE_PATH = "tests/test_example.py"
TEST_SOURCE_BYTES = b"def test_one():\n    assert True\n"
PYPROJECT_BYTES = (
    b"[project]\nname='triad-origin'\nversion='7.0.0rc1.post1'\n"
    b"requires-python='>=3.11'\ndependencies=[]\n"
)
SETUP_BYTES = b"from setuptools import setup\nsetup()\n"
CONSTRAINT_BYTES = b"pytest==9.1.1\n"
COLLECTOR_BYTES = (REPO_ROOT / "tools" / "collect_test_ids.py").read_bytes()
CONTRACT_SOURCE_FILES = {
    str(path.relative_to(REPO_ROOT)): path.read_bytes()
    for path in sorted((REPO_ROOT / "contracts").rglob("*"))
    if path.is_file()
}
REGISTRY_BYTES = CONTRACT_SOURCE_FILES["contracts/registry/index.json"]
CONTRACT_MANIFEST_BYTES = CONTRACT_SOURCE_FILES["contracts/MANIFEST.sha256"]
GOLDEN_MANIFEST_BYTES = b"".join(
    line for line in CONTRACT_MANIFEST_BYTES.splitlines(keepends=True)
    if b"  contracts/golden/" in line
)
AUTHORITY_INVENTORY_PATH = "docs/plan/06_RC2_SOURCE_INVENTORY.md"
AUTHORITY_INVENTORY_BYTES = (REPO_ROOT / AUTHORITY_INVENTORY_PATH).read_bytes()
AUTHORITY_SOURCES = [
    {"bytes": 8_000, "name": "index.html", "sha256": "042f6bea59f897add75dd108632cdd22d90382350a290f8f5a0873fa2e636568"},
    {"bytes": 669_712, "name": "TRIAD_ORIGIN_V7_IMPLEMENTATION_CONTROL_WORKBOOK_1.0.0_RC2.xlsx", "sha256": "2b60d1d4a40456948eff8da5a982956d35f144a7e76445839aa937a1282481e4"},
    {"bytes": 3_106_927, "name": "02_TRIAD_ORIGIN_V7_WIRING_FORMULA_AND_PLUMBING_GUIDE_1.0.0_RC2.html", "sha256": "6c12490ba5677177dc6a85818ce6936e3f028c54ccbbb50bc85496d48162573d"},
    {"bytes": 357_745, "name": "03_TRIAD_ORIGIN_V7_UNAMBIGUOUS_DECLARATIONS_VARIABLES_AND_OBJECTIVE_ACCEPTANCE_1.0.0_RC2.html", "sha256": "15a85a4f42de6636cecb86341d2488eb77b13bc452dc682b5dcb3d847d054fb4"},
    {"bytes": 2_243_356, "name": "Illustrative topology PNG", "sha256": "e4bfc5b549eef6cf7c729d469ab8e78212f1d0d30c011e9dee85797096229f0c"},
]
AUTHORITY_MISSING = [
    "01_TRIAD_ORIGIN_V7_COMPLETE_IMPLEMENTATION_CHECKLIST_1.0.0_RC2.html",
    "canonical/ control bundle and manifest/digests",
]


def _fake_github_get_json(path: str) -> object:
    final_review_id = "5999999999"
    final_review_body = _expected_codex_review_body(HEAD40)
    initial_pr7_review_id = R00_REVIEWED_ROOTS[next(iter(R00_KNOWN_PR7_THREADS))][
        "review_id"
    ]
    initial_pr7_review_head = "6" * 40
    initial_pr7_review_body = _expected_codex_review_body(initial_pr7_review_head)
    if path == "/repos/TriadAgentic/TriadOrigin/pulls/7":
        return {
            "base": {"sha": BASE40},
            "head": {"sha": HEAD40},
            "html_url": "https://github.com/TriadAgentic/TriadOrigin/pull/7",
            "merge_commit_sha": MERGE40,
            "merged": True,
            "merged_at": "2026-08-09T02:00:00Z",
            "number": R00_RECEIPT_PR,
            "user": {"login": R00_PR_AUTHOR},
        }
    if path == "/repos/TriadAgentic/TriadOrigin/actions/runs/1":
        return {
            "conclusion": "success",
            "event": "pull_request",
            "head_branch": "agent/r00-receipt-closure",
            "head_sha": HEAD40,
            "html_url": "https://github.com/TriadAgentic/TriadOrigin/actions/runs/1",
            "id": 1,
            "name": "CI",
            "path": ".github/workflows/ci.yml",
            "pull_requests": [{"number": R00_RECEIPT_PR}],
            "status": "completed",
            "updated_at": "2026-08-09T01:30:00Z",
        }
    if path == "/repos/TriadAgentic/TriadOrigin/actions/jobs/2":
        return {
            "conclusion": "success",
            "head_sha": HEAD40,
            "html_url": "https://github.com/TriadAgentic/TriadOrigin/actions/runs/1/job/2",
            "id": 2,
            "name": "test-and-verify",
            "run_id": 1,
            "status": "completed",
            "steps": [
                {"conclusion": conclusion, "name": name}
                for name, conclusion in R00_REQUIRED_CI_STEPS
            ],
        }
    if path == f"/repos/TriadAgentic/TriadOrigin/git/commits/{HEAD40}":
        return {"sha": HEAD40, "tree": {"sha": TREE40}}
    if path == (
        "/repos/TriadAgentic/TriadOrigin/pulls/4/reviews/"
        f"{R00_IMPLEMENTATION_REVIEW_ID}"
    ):
        return {
            "body": R00_IMPLEMENTATION_REVIEW_BODY,
            "commit_id": R00_IMPLEMENTATION_HEAD_SHA,
            "html_url": R00_IMPLEMENTATION_REVIEW_URL,
            "id": int(R00_IMPLEMENTATION_REVIEW_ID),
            "state": "COMMENTED",
            "user": {"login": R00_IMPLEMENTATION_REVIEWER},
        }
    if path == f"/repos/TriadAgentic/TriadOrigin/pulls/7/reviews/{final_review_id}":
        return {
            "body": final_review_body,
            "commit_id": HEAD40,
            "html_url": (
                "https://github.com/TriadAgentic/TriadOrigin/pull/7"
                f"#pullrequestreview-{final_review_id}"
            ),
            "id": int(final_review_id),
            "state": "COMMENTED",
            "submitted_at": "2026-08-09T01:00:00Z",
            "user": {"login": R00_REQUIRED_REVIEWER},
        }
    if path == "/repos/TriadAgentic/TriadOrigin/pulls/7/reviews?per_page=100&page=1":
        return [
            {
                "body": initial_pr7_review_body,
                "commit_id": initial_pr7_review_head,
                "html_url": (
                    "https://github.com/TriadAgentic/TriadOrigin/pull/7"
                    f"#pullrequestreview-{initial_pr7_review_id}"
                ),
                "id": int(initial_pr7_review_id),
                "state": "COMMENTED",
                "submitted_at": "2026-08-09T00:30:00Z",
                "user": {"login": R00_REQUIRED_REVIEWER},
            },
            {
                "body": final_review_body,
                "commit_id": HEAD40,
                "html_url": (
                    "https://github.com/TriadAgentic/TriadOrigin/pull/7"
                    f"#pullrequestreview-{final_review_id}"
                ),
                "id": int(final_review_id),
                "state": "COMMENTED",
                "submitted_at": "2026-08-09T01:00:00Z",
                "user": {"login": R00_REQUIRED_REVIEWER},
            },
        ]
    if path == "/repos/TriadAgentic/TriadOrigin/pulls/7/reviews?per_page=100&page=2":
        return []
    if path == (
        f"/repos/TriadAgentic/TriadOrigin/pulls/7/reviews/{final_review_id}"
        "/comments?per_page=100"
    ):
        return []
    if path in {
        "/repos/TriadAgentic/TriadOrigin/pulls/7/comments?per_page=100&page=1",
        "/repos/TriadAgentic/TriadOrigin/pulls/7/comments?per_page=100&page=2",
    }:
        return []
    raise AssertionError(f"unexpected GitHub REST path: {path}")


def _fake_github_get_review_threads(pr_number: int) -> object:
    export = next(
        json.loads(item["bytes"])
        for item in _materials()
        if item["evidence_id"] == "review-api"
    )
    pull = next(
        item for item in export["pull_requests"] if item["pr_number"] == pr_number
    )
    threads = []
    for row in pull["inline_threads"]:
        root_record = row["root"]
        root = {
            "author": {"login": root_record["author"]},
            "body": R00_REVIEWED_ROOTS[row["id"]]["body"],
            "fullDatabaseId": row["id"],
            "id": root_record["node_id"],
            "path": row["path"],
            "pullRequestReview": {"fullDatabaseId": root_record["review_id"]},
            "replyTo": None,
            "url": root_record["url"],
        }
        comments = [root]
        reply = row.get("remediation_reply")
        if isinstance(reply, dict):
            reply_record = row["reply_inventory"][0]
            comments.append({
                "author": {"login": reply["author"]},
                "body": reply["body"],
                "fullDatabaseId": reply["id"],
                "id": reply_record["node_id"],
                "path": reply_record["path"],
                "pullRequestReview": {"fullDatabaseId": reply_record["review_id"]},
                "replyTo": {"fullDatabaseId": row["id"]},
                "url": reply["url"],
            })
        threads.append({
            "comments": {
                "nodes": comments,
                "pageInfo": {"hasNextPage": False},
                "totalCount": len(comments),
            },
            "id": row["thread_node_id"],
            "isResolved": row["is_resolved"],
        })
    return {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "nodes": threads,
                        "pageInfo": {"hasNextPage": False},
                        "totalCount": len(threads),
                    }
                }
            }
        }
    }


def validate_receipt(
    receipt, schema, *, evidence_root, git_root=None, receipt_path=None
):
    """Unit tests inject live-shaped REST data; the CLI has no offline bypass."""
    return _validate_receipt_impl(
        receipt,
        schema,
        evidence_root=evidence_root,
        github_get_json=_fake_github_get_json,
        github_get_review_threads=_fake_github_get_review_threads,
        git_root=git_root,
        receipt_path=receipt_path,
    )
SOURCE_FILES = {
    **CONTRACT_SOURCE_FILES,
    AUTHORITY_INVENTORY_PATH: AUTHORITY_INVENTORY_BYTES,
    "pyproject.toml": PYPROJECT_BYTES,
    "setup.py": SETUP_BYTES,
    "constraints/ci.txt": CONSTRAINT_BYTES,
    SOURCE_PATH: SOURCE_BYTES,
    TEST_SOURCE_PATH: TEST_SOURCE_BYTES,
    "tools/collect_test_ids.py": COLLECTOR_BYTES,
}


def _source_entry(path: str, data: bytes) -> dict[str, str]:
    return {
        "path": path,
        "mode": "100644",
        "type": "blob",
        "blob_sha": hashlib.sha1(
            f"blob {len(data)}\0".encode() + data,
            usedforsecurity=False,
        ).hexdigest(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


SOURCE_ENTRIES = [_source_entry(path, SOURCE_FILES[path]) for path in sorted(SOURCE_FILES)]
TREE40 = _git_tree_sha(SOURCE_ENTRIES)
MERGE_COMMIT_BYTES = (
    f"tree {TREE40}\n"
    f"parent {BASE40}\n"
    "author R00 Fixture <r00-fixture@example.invalid> 0 +0000\n"
    "committer R00 Fixture <r00-fixture@example.invalid> 0 +0000\n"
    "\n"
    "deterministic corrective merge fixture\n"
).encode()
MERGE40 = hashlib.sha1(
    f"commit {len(MERGE_COMMIT_BYTES)}\0".encode() + MERGE_COMMIT_BYTES,
    usedforsecurity=False,
).hexdigest()


def _canonical(value: dict) -> bytes:
    return canonical_json(value)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sdist_bytes() -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        prefix = "triad_origin-7.0.0rc1.post1/"
        members = {
            "PKG-INFO": (
                b"Metadata-Version: 2.1\nName: triad-origin\nVersion: 7.0.0rc1.post1\n"
                b"Requires-Python: >=3.11\n"
            ),
            "pyproject.toml": PYPROJECT_BYTES,
            "setup.cfg": b"[egg_info]\ntag_build = \ntag_date = 0\n\n",
            "setup.py": SETUP_BYTES,
            "constraints/ci.txt": CONSTRAINT_BYTES,
            "src/triad_origin/__init__.py": SOURCE_BYTES,
        }
        members.update(CONTRACT_SOURCE_FILES)
        for name, payload in members.items():
            info = tarfile.TarInfo(prefix + name)
            info.size = len(payload)
            info.mtime = 0
            archive.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def _wheel_bytes() -> bytes:
    dist_info = "triad_origin-7.0.0rc1.post1.dist-info/"
    members = {
        "triad_origin/__init__.py": SOURCE_BYTES,
        dist_info + "WHEEL": (
            b"Wheel-Version: 1.0\n"
            b"Generator: setuptools (79.0.1)\n"
            b"Root-Is-Purelib: true\n"
            b"Tag: py3-none-any\n\n"
        ),
        dist_info + "METADATA": (
            b"Metadata-Version: 2.1\nName: triad-origin\nVersion: 7.0.0rc1.post1\n"
            b"Requires-Python: >=3.11\n"
        ),
        dist_info + "top_level.txt": b"triad_origin\n",
    }
    members.update({
        "triad_origin/_contracts/" + path.removeprefix("contracts/"): data
        for path, data in CONTRACT_SOURCE_FILES.items()
    })
    record_name = dist_info + "RECORD"
    members[record_name] = _wheel_record(members, record_name)
    return _zip_bytes(members)


def _wheel_record(members: dict[str, bytes], record_name: str) -> bytes:
    record_buffer = io.StringIO(newline="")
    writer = csv.writer(record_buffer, lineterminator="\n")
    for name, payload in members.items():
        if name == record_name:
            continue
        digest = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b"=").decode()
        writer.writerow((name, f"sha256={digest}", str(len(payload))))
    writer.writerow((record_name, "", ""))
    return record_buffer.getvalue().encode()


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, payload in members.items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            archive.writestr(info, payload)
    return buffer.getvalue()


def _materials() -> list[dict]:
    dependency_spec = b"pytest==9.1.1\n"
    dependency_spec_sha = _sha(dependency_spec)
    ci_log = b"immutable GitHub Actions job log\n"
    ci_log_sha = _sha(ci_log)
    sdist = _sdist_bytes()
    wheel = _wheel_bytes()
    source_tree = _canonical({
        "files": SOURCE_ENTRIES,
        "merge_sha": MERGE40,
        "repository": "TriadAgentic/TriadOrigin",
        "schema": "origin.source-tree-evidence.v1",
        "tree_sha": TREE40,
    })
    collection_log = b"tests/test_example.py::test_one\n"

    authority = _canonical({
        "canonical": False,
        "inventory_path": AUTHORITY_INVENTORY_PATH,
        "inventory_sha256": _sha(AUTHORITY_INVENTORY_BYTES),
        "missing_members": AUTHORITY_MISSING,
        "schema": "origin.authority-basis-evidence.v1",
        "sources": AUTHORITY_SOURCES,
        "status": "INCOMPLETE_AUDIT_BASIS",
    })
    toolchain = _canonical({
        "dependency_spec_sha256": dependency_spec_sha,
        "packages": ["pytest==9.1.1"],
        "platform": "linux",
        "python_version": "3.11",
        "runner_image": "ubuntu-latest",
        "schema": "origin.toolchain-evidence.v1",
    })
    ci = _canonical({
        "commands": R00_REQUIRED_COMMANDS,
        "conclusion": "success",
        "head_sha": HEAD40,
        "job_id": "2",
        "log_sha256": ci_log_sha,
        "provider": "github-actions",
        "run_id": "1",
        "schema": "origin.ci-evidence.v1",
    })

    materials: list[dict] = [
        _material("authority", "authority-basis", "authority.json", authority,
                  "/authority_basis/digest_sha256"),
        _material("dependency-spec", "dependency-spec", "constraints.txt", dependency_spec,
                  "/toolchain/dependency_spec_sha256"),
        _material("toolchain", "dependency-snapshot", "toolchain.json", toolchain,
                  "/toolchain/dependency_snapshot_sha256"),
        _material("source-tree", "artifact", "source.manifest.json", source_tree,
                  "/artifacts/0/sha256"),
        _material("sdist", "artifact", "triad-origin.tar.gz", sdist,
                  "/artifacts/1/sha256"),
        _material("wheel", "artifact", "triad_origin.whl", wheel,
                  "/artifacts/2/sha256"),
        _material("ci", "ci", "ci.json", ci, "/ci/evidence_sha256"),
        _material("ci-log", "ci-log", "ci.log", ci_log, "/ci/log_sha256"),
    ]

    result_hashes: list[str] = []
    log_hashes: list[str] = []
    for index, command in enumerate(R00_REQUIRED_COMMANDS):
        test_ids = (
            b"tests/test_example.py::test_one\n"
            if command.endswith("python -m pytest")
            else f"R00-GATE-{index:02d}\n".encode()
        )
        test_ids_sha = _sha(test_ids)
        if command == "python tools/verify_reproducible_build.py":
            command_log = (
                f"OK: reproducible sdist={_sha(sdist)} wheel={_sha(wheel)}\n".encode()
            )
        elif command == "python tools/collect_test_ids.py":
            command_log = collection_log
        else:
            command_log = f"$ {command}\nPASS\n".encode()
        command_log_sha = _sha(command_log)
        result = _canonical({
            "command": command,
            "exit_code": 0,
            "head_sha": MERGE40,
            "log_sha256": command_log_sha,
            "passed": 1,
            "schema": "origin.test-result-evidence.v1",
            "skips": 0,
            "test_ids_sha256": test_ids_sha,
            "xfails": 0,
        })
        result_hashes.append(_sha(result))
        log_hashes.append(command_log_sha)
        materials.extend([
            _material(
                f"test-result-{index}", "test-result", f"test-result-{index}.json", result,
                f"/tests/{index}/result_sha256",
            ),
            _material(
                f"test-ids-{index}", "test-ids", f"test-ids-{index}.txt", test_ids,
                f"/tests/{index}/test_ids_sha256",
            ),
            _material(
                f"command-log-{index}", "command-log", f"command-{index}.log", command_log,
                f"/tests/{index}/log_sha256",
            ),
        ])

    negative = _canonical({
        "forbidden_hits": 0,
        "head_sha": MERGE40,
        "result": "PASS",
        "scanner": "tools/verify_no_forbidden_capabilities.py",
        "schema": "origin.negative-capability-evidence.v1",
    })
    failed_attempt = _canonical(R00_FAILED_ATTEMPT)
    thread_prs = {
        **R00_INHERITED_THREADS,
        **{value: 4 for value in R00_KNOWN_PR4_THREADS},
        **{value: R00_RECEIPT_PR for value in R00_KNOWN_PR7_THREADS},
    }
    threads = [
        {
            "actionable": True,
            "disposition": "fixed and resolved by R00",
            "pr_number": pr_number,
            "resolved": True,
            "thread_id": thread_id,
            "url": (
                f"https://github.com/TriadAgentic/TriadOrigin/pull/{pr_number}"
                f"#discussion_r{thread_id}"
            ),
        }
        for thread_id, pr_number in sorted(
            thread_prs.items(), key=lambda item: (item[1], int(item[0]))
        )
    ]
    final_review_id = "5999999999"
    final_review_body = _expected_codex_review_body(HEAD40)
    initial_pr7_review_id = R00_REVIEWED_ROOTS[next(iter(R00_KNOWN_PR7_THREADS))][
        "review_id"
    ]
    initial_pr7_review_head = "6" * 40
    initial_pr7_review_body = _expected_codex_review_body(initial_pr7_review_head)
    review = _canonical({
        "final_review": {
            "body_sha256": _sha(final_review_body.encode()),
            "head_sha": HEAD40,
            "review_id": final_review_id,
            "reviewer": R00_REQUIRED_REVIEWER,
            "url": (
                f"https://github.com/TriadAgentic/TriadOrigin/pull/{R00_RECEIPT_PR}"
                f"#pullrequestreview-{final_review_id}"
            ),
            "verdict": "PASS",
        },
        "head_sha": HEAD40,
        "inherited_thread_count": 14,
        "pr4_thread_count": len(R00_KNOWN_PR4_THREADS),
        "pr_author": R00_PR_AUTHOR,
        "reviewed_prs": sorted(R00_REVIEW_PRS),
        "reviewer": R00_REQUIRED_REVIEWER,
        "schema": "origin.review-evidence.v1",
        "threads": threads,
        "unresolved_actionable_threads": 0,
        "verdict": "PASS",
    })
    review_ids = {1: "4889010117", 2: "4889021032", 3: "4889056077"}
    review_api_record = {
        "head_sha": HEAD40,
        "pagination_complete": True,
        "page_info": {"has_next_page": False},
        "pull_requests": [
            {
                "author": R00_PR_AUTHOR if pr_number == R00_RECEIPT_PR else "likosubakti",
                "inline_threads": [
                    {
                        "id": thread["thread_id"],
                        "is_resolved": True,
                        "path": "reviewed/path.py",
                        "remediation_reply": {
                            "author": "triad-maintainer",
                            "body": _expected_remediation_reply_body(
                                thread["thread_id"],
                                (
                                    MERGE40
                                    if pr_number == R00_RECEIPT_PR
                                    else R00_IMPLEMENTATION_MERGE_SHA
                                ),
                            ),
                            "id": "8" + thread["thread_id"],
                            "url": (
                                f"https://github.com/TriadAgentic/TriadOrigin/pull/{pr_number}"
                                f"#discussion_r8{thread['thread_id']}"
                            ),
                        },
                        "review_id": (
                            review_ids[pr_number]
                            if pr_number in review_ids
                            else (
                                "4889242636"
                                if int(thread["thread_id"]) <= 3741134197
                                else "4889327416"
                            )
                        ),
                        "url": thread["url"],
                    }
                    for thread in threads if thread["pr_number"] == pr_number
                ],
                "pr_number": pr_number,
                "reviews": (
                    [{
                        "body": initial_pr7_review_body,
                        "commit_id": initial_pr7_review_head,
                        "review_id": initial_pr7_review_id,
                        "reviewer": R00_REQUIRED_REVIEWER,
                        "state": "COMMENTED",
                        "submitted_at": "2026-08-09T00:30:00Z",
                        "url": (
                            f"https://github.com/TriadAgentic/TriadOrigin/pull/{R00_RECEIPT_PR}"
                            f"#pullrequestreview-{initial_pr7_review_id}"
                        ),
                    }, {
                        "body": final_review_body,
                        "commit_id": HEAD40,
                        "review_id": final_review_id,
                        "reviewer": R00_REQUIRED_REVIEWER,
                        "state": "COMMENTED",
                        "submitted_at": "2026-08-09T01:00:00Z",
                        "url": (
                            f"https://github.com/TriadAgentic/TriadOrigin/pull/{R00_RECEIPT_PR}"
                            f"#pullrequestreview-{final_review_id}"
                        ),
                    }]
                    if pr_number == R00_RECEIPT_PR else ([{
                        "body": R00_IMPLEMENTATION_REVIEW_BODY,
                        "commit_id": R00_IMPLEMENTATION_HEAD_SHA,
                        "review_id": R00_IMPLEMENTATION_REVIEW_ID,
                        "reviewer": R00_IMPLEMENTATION_REVIEWER,
                        "state": "COMMENTED",
                        "url": R00_IMPLEMENTATION_REVIEW_URL,
                    }] if pr_number == 4 else [])
                ),
            }
            for pr_number in sorted(R00_REVIEW_PRS)
        ],
        "repository": "TriadAgentic/TriadOrigin",
        "schema": "origin.github-review-export.v1",
    }
    for pull in review_api_record["pull_requests"]:
        for row in pull["inline_threads"]:
            reply = row["remediation_reply"]
            reviewed = R00_REVIEWED_ROOTS[row["id"]]
            assert reviewed["pr_number"] == pull["pr_number"]
            row["path"] = reviewed["path"]
            row["review_id"] = reviewed["review_id"]
            row["thread_node_id"] = reviewed["thread_node_id"]
            row["root"] = {
                "author": reviewed["author"],
                "body_sha256": _sha(str(reviewed["body"]).encode()),
                "node_id": reviewed["root_node_id"],
                "review_id": reviewed["review_id"],
                "url": reviewed["url"],
            }
            row["reply_inventory"] = [{
                "author": reply["author"],
                "body_sha256": _sha(reply["body"].encode()),
                "id": reply["id"],
                "node_id": "PRRC_reply_" + reply["id"],
                "path": row["path"],
                "reply_to_id": row["id"],
                "review_id": row["review_id"],
                "url": reply["url"],
            }]
    review_api = _canonical(review_api_record)
    merge = _canonical({
        "base_sha": BASE40,
        "expected_head_guard": True,
        "expected_head_sha": HEAD40,
        "head_sha": HEAD40,
        "merge_sha": MERGE40,
        "tree_sha": TREE40,
        "method": "squash",
        "pr_number": R00_RECEIPT_PR,
        "repository": "TriadAgentic/TriadOrigin",
        "schema": "origin.merge-evidence.v1",
        "url": (
            f"https://github.com/TriadAgentic/TriadOrigin/pull/{R00_RECEIPT_PR}"
        ),
    })
    command_set = _canonical({
        "branch": "main",
        "clone_performed": True,
        "commands": R00_REQUIRED_COMMANDS,
        "environment": {
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PIP_CONSTRAINT": CONSTRAINT,
            "TZ": "UTC",
        },
        "fresh_reconstruction": True,
        "fresh_main_sha": MERGE40,
        "origin_main_sha": MERGE40,
        "schema": "origin.command-set-evidence.v1",
        "setup_log_sha256": "SETUP_LOG_DIGEST_REPLACED_BELOW",
        "setup": [
            {
                "command": (
                    "git clone --no-local "
                    "https://github.com/TriadAgentic/TriadOrigin.git /fresh/checkout"
                ),
                "kind": "fresh-clone",
                "target": "/fresh/checkout",
            },
            {
                "command": "git -C /fresh/checkout rev-parse HEAD",
                "expected_sha": MERGE40,
                "kind": "checkout-identity",
            },
            {
                "command": "git -C /fresh/checkout branch --show-current",
                "expected": "main",
                "kind": "branch-identity",
            },
            {
                "command": "git -C /fresh/checkout rev-parse origin/main",
                "expected_sha": MERGE40,
                "kind": "remote-main-identity",
            },
            {
                "command": "git -C /fresh/checkout status --porcelain=v1",
                "expected": "",
                "kind": "clean-tree",
            },
            {
                "command": "python -m pip install -e '.[test]'",
                "constraint_path": CONSTRAINT,
                "cwd": "/fresh/checkout",
                "kind": "install",
            },
        ],
        "working_tree_clean": True,
    })
    setup_log = (
        "CLONE=TriadAgentic/TriadOrigin\n"
        "TARGET=/fresh/checkout\n"
        f"HEAD={MERGE40}\n"
        "BRANCH=main\n"
        f"ORIGIN_MAIN={MERGE40}\n"
        "CLEAN=true\n"
        "INSTALL=success\n"
    ).encode()
    command_set_record = json.loads(command_set)
    command_set_record["setup_log_sha256"] = _sha(setup_log)
    command_set = _canonical(command_set_record)
    post_merge = _canonical({
        "command_logs": log_hashes,
        "command_results": result_hashes,
        "command_set_sha256": _sha(command_set),
        "fresh_main_sha": MERGE40,
        "reproduced": True,
        "result": "PASS",
        "schema": "origin.post-merge-evidence.v1",
        "setup_log_sha256": _sha(setup_log),
        "toolchain_snapshot_sha256": _sha(toolchain),
    })
    test_collection = _canonical({
        "collected": 1,
        "command": "python tools/collect_test_ids.py",
        "head_sha": MERGE40,
        "log_sha256": _sha(collection_log),
        "node_ids": ["tests/test_example.py::test_one"],
        "pytest_args": ["-o", "addopts=", "--collect-only", "-p", "no:terminal"],
        "schema": "origin.pytest-collection-evidence.v1",
    })
    materials.extend([
        _material("contracts-manifest", "manifest", "contracts.manifest",
                  CONTRACT_MANIFEST_BYTES, "/manifests/contracts"),
        _material("failed-attempt", "manifest", "failed-attempt.json",
                  failed_attempt, "/manifests/failed_attempt"),
        _material("golden-manifest", "manifest", "goldens.manifest",
                  GOLDEN_MANIFEST_BYTES, "/manifests/golden_vectors"),
        _material("test-collection", "manifest", "test-collection.json", test_collection,
                  "/manifests/test_collection"),
        _material("test-collection-log", "manifest", "test-collection.log", collection_log,
                  "/manifests/test_collection_log"),
        _material("negative", "negative-capability", "negative.json", negative,
                  "/negative_capability/result_sha256"),
        _material("review", "review", "review.json", review, "/review/review_sha256"),
        _material("review-api", "review-api", "review-api.json", review_api,
                  "/review/api_export_sha256"),
        _material("merge", "merge", "merge.json", merge,
                  "/merge_control/evidence_sha256"),
        _material("command-set", "command-set", "command-set.json", command_set,
                  "/post_merge/command_set_sha256"),
        _material("setup-log", "setup-log", "setup.log", setup_log,
                  "/post_merge/setup_log_sha256"),
        _material("post-merge", "post-merge-result", "post-merge.json", post_merge,
                  "/post_merge/result_sha256"),
    ])
    return materials


def _material(
    evidence_id: str, kind: str, filename: str, data: bytes, pointer: str
) -> dict:
    return {
        "evidence_id": evidence_id,
        "kind": kind,
        "path": f"evidence/R00/{filename}",
        "bytes": data,
        "binds": [pointer],
    }


def _digest_by_pointer() -> dict[str, str]:
    return {item["binds"][0]: _sha(item["bytes"]) for item in _materials()}


def _valid_receipt() -> dict:
    digests = _digest_by_pointer()
    evidence_files = [
        {
            "evidence_id": item["evidence_id"],
            "kind": item["kind"],
            "path": item["path"],
            "sha256": _sha(item["bytes"]),
            "binds": item["binds"],
        }
        for item in _materials()
    ]
    tests = [
        {
            "command": command,
            "exit_code": 0,
            "result_sha256": digests[f"/tests/{index}/result_sha256"],
            "test_ids_sha256": digests[f"/tests/{index}/test_ids_sha256"],
            "log_sha256": digests[f"/tests/{index}/log_sha256"],
            "passed": 1,
            "skips": 0,
            "xfails": 0,
        }
        for index, command in enumerate(R00_REQUIRED_COMMANDS)
    ]
    return {
        "schema": "origin.milestone_receipt.v1",
        "receipt_id": "r00-example",
        "milestone_id": "R00",
        "scope": SCOPE,
        "scope_sha256": _sha(SCOPE.encode()),
        "authority_basis": {
            "status": "INCOMPLETE_AUDIT_BASIS",
            "digest_sha256": digests["/authority_basis/digest_sha256"],
            "canonical": False,
            "inventory_ref": "evidence/R00/authority.json",
        },
        "base_sha": BASE40,
        "head_sha": HEAD40,
        "merge_sha": MERGE40,
        "toolchain": {
            "python_version": "3.11",
            "platform": "linux",
            "runner_image": "ubuntu-latest",
            "dependency_spec_sha256": digests["/toolchain/dependency_spec_sha256"],
            "dependency_snapshot_sha256": digests["/toolchain/dependency_snapshot_sha256"],
        },
        "evidence_files": evidence_files,
        "artifacts": [
            {"name": "source.manifest", "kind": "source-tree",
             "sha256": digests["/artifacts/0/sha256"]},
            {"name": "triad-origin.tar.gz", "kind": "sdist",
             "sha256": digests["/artifacts/1/sha256"]},
            {"name": "triad_origin.whl", "kind": "wheel",
             "sha256": digests["/artifacts/2/sha256"]},
        ],
        "ci": {
            "provider": "github-actions",
            "run_id": "1",
            "head_sha": HEAD40,
            "conclusion": "success",
            "evidence_sha256": digests["/ci/evidence_sha256"],
            "log_sha256": digests["/ci/log_sha256"],
        },
        "tests": tests,
        "manifests": {
            "contracts": digests["/manifests/contracts"],
            "failed_attempt": digests["/manifests/failed_attempt"],
            "golden_vectors": digests["/manifests/golden_vectors"],
            "test_collection": digests["/manifests/test_collection"],
            "test_collection_log": digests["/manifests/test_collection_log"],
        },
        "deferred_evidence": [
            {
                "evidence_id": "branch-ruleset",
                "reason": "GitHub issue #5 records the unproven durable ruleset",
                "owner": "repository-admin",
                "later_milestone": "B00",
            },
            {
                "evidence_id": "formula-evidence",
                "reason": "R00 changes no detector formula",
                "owner": "origin",
                "later_milestone": "B03",
            },
            {
                "evidence_id": "parameter-evidence",
                "reason": "R00 selects no detector parameter",
                "owner": "origin",
                "later_milestone": "B03",
            },
            {
                "evidence_id": "replay-evidence",
                "reason": (
                    "full replay parity and CTRL-B02-001/CTRL-B02-002 closure belong to kernel "
                    "refreeze"
                ),
                "owner": "origin",
                "later_milestone": "B02",
            },
        ],
        "negative_capability": {
            "scanner": "tools/verify_no_forbidden_capabilities.py",
            "result_sha256": digests["/negative_capability/result_sha256"],
            "forbidden_hits": 0,
        },
        "review": {
            "unresolved_actionable_threads": 0,
            "reviewer": R00_REQUIRED_REVIEWER,
            "review_sha256": digests["/review/review_sha256"],
            "api_export_sha256": digests["/review/api_export_sha256"],
        },
        "merge_control": {
            "repository": "TriadAgentic/TriadOrigin",
            "pr_number": R00_RECEIPT_PR,
            "method": "squash",
            "expected_head_sha": HEAD40,
            "tree_sha": TREE40,
            "url": (
                f"https://github.com/TriadAgentic/TriadOrigin/pull/{R00_RECEIPT_PR}"
            ),
            "evidence_sha256": digests["/merge_control/evidence_sha256"],
        },
        "post_merge": {
            "fresh_main_sha": MERGE40,
            "reproduced": True,
            "command_set_sha256": digests["/post_merge/command_set_sha256"],
            "setup_log_sha256": digests["/post_merge/setup_log_sha256"],
            "result_sha256": digests["/post_merge/result_sha256"],
        },
        "supersession": {"supersedes_receipt_id": None, "reason": "first receipt"},
        "rollback": {"strategy": "revert squash commit", "receipt_id": None},
        "status": "VERIFIED",
    }


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _materialize_evidence(root: pathlib.Path) -> None:
    for relative, data in SOURCE_FILES.items():
        source = root / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(data)
    for item in _materials():
        path = root / item["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(item["bytes"])


def _git(root: pathlib.Path, *arguments: str, input_bytes: bytes | None = None) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout


def _materialize_git_seal(
    root: pathlib.Path,
    receipt: dict,
    *,
    receipt_parent: str = MERGE40,
    extra_evidence: dict[str, bytes] | None = None,
) -> pathlib.Path:
    receipt_path = root / "evidence/receipts/R00.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_bytes(_canonical(receipt))
    _git(root, "init", "-q", "-b", "evidence/r00-receipt")
    _git(root, "add", "--", *sorted(SOURCE_FILES))
    assert _git(root, "write-tree").decode().strip() == TREE40
    assert (
        _git(
            root,
            "hash-object",
            "-t",
            "commit",
            "-w",
            "--stdin",
            input_bytes=MERGE_COMMIT_BYTES,
        ).decode().strip()
        == MERGE40
    )
    for relative, data in (extra_evidence or {}).items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    _git(root, "add", "-A")
    evidence_tree = _git(root, "write-tree").decode().strip()
    commit_bytes = (
        f"tree {evidence_tree}\n"
        f"parent {receipt_parent}\n"
        "author R00 Fixture <r00-fixture@example.invalid> 1 +0000\n"
        "committer R00 Fixture <r00-fixture@example.invalid> 1 +0000\n"
        "\n"
        "deterministic receipt seal fixture\n"
    ).encode()
    receipt_commit = _git(
        root,
        "hash-object",
        "-t",
        "commit",
        "-w",
        "--stdin",
        input_bytes=commit_bytes,
    ).decode().strip()
    _git(root, "update-ref", "refs/heads/evidence/r00-receipt", receipt_commit)
    assert _git(root, "rev-parse", "HEAD").decode().strip() == receipt_commit
    return receipt_path


def _rewrite_bound_record(root: pathlib.Path, receipt: dict, evidence_id: str, record: dict) -> None:
    item = next(value for value in receipt["evidence_files"] if value["evidence_id"] == evidence_id)
    data = _canonical(record)
    (root / item["path"]).write_bytes(data)
    digest = _sha(data)
    item["sha256"] = digest
    _set_pointer(receipt, item["binds"][0], digest)


def _rewrite_bound_bytes(root: pathlib.Path, receipt: dict, evidence_id: str, data: bytes) -> None:
    item = next(value for value in receipt["evidence_files"] if value["evidence_id"] == evidence_id)
    (root / item["path"]).write_bytes(data)
    digest = _sha(data)
    item["sha256"] = digest
    _set_pointer(receipt, item["binds"][0], digest)


def _set_pointer(document: dict, pointer: str, value: str) -> None:
    parts = pointer[1:].split("/")
    node = document
    for token in parts[:-1]:
        node = node[int(token)] if isinstance(node, list) else node[token]
    if isinstance(node, list):
        node[int(parts[-1])] = value
    else:
        node[parts[-1]] = value


def test_receipt_schema_and_complete_example_validate(tmp_path):
    schema = _schema()
    jsonschema.validators.validator_for(schema).check_schema(schema)
    jsonschema.validate(_valid_receipt(), schema)
    _materialize_evidence(tmp_path)
    validate_receipt(_valid_receipt(), schema, evidence_root=tmp_path)


def test_r00_final_seal_authenticates_git_tree_lineage_and_committed_bytes(tmp_path):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    receipt_path = _materialize_git_seal(tmp_path, receipt)
    validate_receipt(
        receipt,
        _schema(),
        evidence_root=tmp_path,
        git_root=tmp_path,
        receipt_path=receipt_path,
    )


@pytest.mark.parametrize("mutation", ["base", "tree", "receipt-parent", "receipt-bytes"])
def test_r00_final_seal_rejects_false_git_lineage(tmp_path, mutation):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    receipt_parent = MERGE40
    if mutation == "base":
        receipt["base_sha"] = "1" * 40
    elif mutation == "tree":
        receipt["merge_control"]["tree_sha"] = "4" * 40
    elif mutation == "receipt-parent":
        receipt_parent = HEAD40
    receipt_path = _materialize_git_seal(
        tmp_path,
        receipt,
        receipt_parent=receipt_parent,
    )
    if mutation == "receipt-bytes":
        receipt_path.write_bytes(b"{}\n")
    with pytest.raises(ReceiptValidationError, match="Git-object lineage"):
        validate_receipt(
            receipt,
            _schema(),
            evidence_root=tmp_path,
            git_root=tmp_path,
            receipt_path=receipt_path,
        )


@pytest.mark.parametrize("mutation", ["branch", "extra-evidence", "dirty"])
def test_r00_final_seal_requires_canonical_clean_exact_evidence_branch(
    tmp_path, mutation
):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    receipt_path = _materialize_git_seal(
        tmp_path,
        receipt,
        extra_evidence=(
            {"evidence/R00/unbound-claim.txt": b"unbound\n"}
            if mutation == "extra-evidence"
            else None
        ),
    )
    if mutation == "branch":
        _git(tmp_path, "branch", "-m", "attacker/not-canonical")
    elif mutation == "dirty":
        (tmp_path / "tools/untracked_shadow.py").write_text("raise SystemExit\n")
    with pytest.raises(ReceiptValidationError, match="Git-object lineage"):
        validate_receipt(
            receipt,
            _schema(),
            evidence_root=tmp_path,
            git_root=tmp_path,
            receipt_path=receipt_path,
        )


def test_r00_sealing_requires_live_github_revalidation(tmp_path):
    _materialize_evidence(tmp_path)
    with pytest.raises(
        ReceiptValidationError, match="requires live GitHub REST revalidation"
    ):
        _validate_receipt_impl(_valid_receipt(), _schema(), evidence_root=tmp_path)


@pytest.mark.parametrize("same_actor_field", ["author", "reviewer"])
def test_r00_live_review_requires_connector_and_author_separation(
    tmp_path, same_actor_field
):
    _materialize_evidence(tmp_path)

    def same_actor_get(path: str):
        record = copy.deepcopy(_fake_github_get_json(path))
        if same_actor_field == "author" and path.endswith("/pulls/7"):
            record["user"]["login"] = R00_REQUIRED_REVIEWER
        if same_actor_field == "reviewer" and path.endswith("/reviews/5999999999"):
            record["user"]["login"] = R00_PR_AUTHOR
        return record

    with pytest.raises(
        ReceiptValidationError,
        match="not an independent exact-head pre-merge review",
    ):
        _validate_receipt_impl(
            _valid_receipt(),
            _schema(),
            evidence_root=tmp_path,
            github_get_json=same_actor_get,
            github_get_review_threads=_fake_github_get_review_threads,
        )


@pytest.mark.parametrize(
    "submitted_at", ["2026-08-09T03:00:00Z", "2026-08-09T01:00:00"]
)
def test_r00_live_review_must_precede_merge(tmp_path, submitted_at):
    _materialize_evidence(tmp_path)

    def late_review_get(path: str):
        record = copy.deepcopy(_fake_github_get_json(path))
        if path.endswith("/reviews/5999999999"):
            record["submitted_at"] = submitted_at
        return record

    with pytest.raises(
        ReceiptValidationError,
        match="not an independent exact-head pre-merge review",
    ):
        _validate_receipt_impl(
            _valid_receipt(),
            _schema(),
            evidence_root=tmp_path,
            github_get_json=late_review_get,
            github_get_review_threads=_fake_github_get_review_threads,
        )


def test_r00_live_final_connector_review_must_have_no_inline_findings(tmp_path):
    _materialize_evidence(tmp_path)

    def finding_get(path: str):
        if path.endswith("/comments?per_page=100"):
            return [{"id": 1, "body": "actionable finding"}]
        return copy.deepcopy(_fake_github_get_json(path))

    with pytest.raises(
        ReceiptValidationError,
        match="not an independent exact-head pre-merge review",
    ):
        _validate_receipt_impl(
            _valid_receipt(),
            _schema(),
            evidence_root=tmp_path,
            github_get_json=finding_get,
            github_get_review_threads=_fake_github_get_review_threads,
        )


def test_r00_codex_review_body_cannot_hide_a_negative_verdict(tmp_path):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    poisoned = _expected_codex_review_body(HEAD40) + "\nP1: CRITICAL BYPASS. DO NOT MERGE.\n"
    review = json.loads((tmp_path / "evidence/R00/review.json").read_bytes())
    review["final_review"]["body_sha256"] = _sha(poisoned.encode())
    _rewrite_bound_record(tmp_path, receipt, "review", review)
    export = json.loads((tmp_path / "evidence/R00/review-api.json").read_bytes())
    corrective = next(
        pull for pull in export["pull_requests"]
        if pull["pr_number"] == R00_RECEIPT_PR
    )
    corrective["reviews"][0]["body"] = poisoned
    _rewrite_bound_record(tmp_path, receipt, "review-api", export)

    def poisoned_get(path: str):
        record = copy.deepcopy(_fake_github_get_json(path))
        if path.endswith("/reviews/5999999999"):
            record["body"] = poisoned
        return record

    with pytest.raises(ReceiptValidationError, match="final review"):
        _validate_receipt_impl(
            receipt,
            _schema(),
            evidence_root=tmp_path,
            github_get_json=poisoned_get,
            github_get_review_threads=_fake_github_get_review_threads,
        )


def test_r00_live_review_rejects_an_uninventoried_pr7_thread(tmp_path):
    _materialize_evidence(tmp_path)

    def late_thread_get(pr_number: int):
        record = copy.deepcopy(_fake_github_get_review_threads(pr_number))
        if pr_number == R00_RECEIPT_PR:
            connection = record["data"]["repository"]["pullRequest"]["reviewThreads"]
            connection["nodes"].append({
                "comments": {
                    "nodes": [{
                        "author": {"login": "review-bot"},
                        "body": "late finding",
                        "fullDatabaseId": "4999999999",
                        "id": "PRRC_late",
                        "path": "late.py",
                        "pullRequestReview": {"fullDatabaseId": "5999999998"},
                        "replyTo": None,
                        "url": (
                            "https://github.com/TriadAgentic/TriadOrigin/pull/7"
                            "#discussion_r4999999999"
                        ),
                    }],
                    "pageInfo": {"hasNextPage": False},
                    "totalCount": 1,
                },
                "id": "PRRT_late",
                "isResolved": False,
            })
            connection["totalCount"] += 1
        return record

    with pytest.raises(
        ReceiptValidationError,
        match="persisted thread roots do not equal",
    ):
        _validate_receipt_impl(
            _valid_receipt(),
            _schema(),
            evidence_root=tmp_path,
            github_get_json=_fake_github_get_json,
            github_get_review_threads=late_thread_get,
        )


@pytest.mark.parametrize("field", ["id", "author", "body", "url"])
def test_r00_live_graphql_rejects_fabricated_historical_remediation_reply(
    tmp_path, field
):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    export = json.loads((tmp_path / "evidence/R00/review-api.json").read_bytes())
    historical = next(
        row
        for pull in export["pull_requests"]
        if pull["pr_number"] == 1
        for row in pull["inline_threads"]
    )
    replacement = {
        "id": "9999999999",
        "author": "invented-author",
        "body": (
            f"invented {R00_IMPLEMENTATION_MERGE_SHA} "
            "evidence/receipts/R00.json"
        ),
        "url": (
            "https://github.com/TriadAgentic/TriadOrigin/pull/1"
            "#discussion_r9999999999"
        ),
    }
    historical["remediation_reply"][field] = replacement[field]
    _rewrite_bound_record(tmp_path, receipt, "review-api", export)
    with pytest.raises(
        ReceiptValidationError,
        match="actionable review thread|resolution/reply is not authenticated",
    ):
        _validate_receipt_impl(
            receipt,
            _schema(),
            evidence_root=tmp_path,
            github_get_json=_fake_github_get_json,
            github_get_review_threads=_fake_github_get_review_threads,
        )


def test_r00_remediation_reply_cannot_embed_a_negative_closure(tmp_path):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    export = json.loads((tmp_path / "evidence/R00/review-api.json").read_bytes())
    corrective = next(
        row
        for pull in export["pull_requests"]
        if pull["pr_number"] == R00_RECEIPT_PR
        for row in pull["inline_threads"]
    )
    negative = (
        "P1 CRITICAL: remediation failed; DO NOT MERGE.\n"
        f"remediation_merge={MERGE40}\n"
        "receipt=evidence/receipts/R00.json\n"
    )
    corrective["remediation_reply"]["body"] = negative
    corrective["reply_inventory"][0]["body_sha256"] = _sha(negative.encode())
    _rewrite_bound_record(tmp_path, receipt, "review-api", export)

    def negative_get(pr_number: int):
        record = copy.deepcopy(_fake_github_get_review_threads(pr_number))
        if pr_number == R00_RECEIPT_PR:
            record["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"][
                0
            ]["comments"]["nodes"][-1]["body"] = negative
        return record

    with pytest.raises(ReceiptValidationError, match="actionable review thread"):
        _validate_receipt_impl(
            receipt,
            _schema(),
            evidence_root=tmp_path,
            github_get_json=_fake_github_get_json,
            github_get_review_threads=negative_get,
        )


def test_r00_live_graphql_requires_resolved_historical_thread(tmp_path):
    _materialize_evidence(tmp_path)

    def unresolved_get(pr_number: int):
        record = copy.deepcopy(_fake_github_get_review_threads(pr_number))
        if pr_number == 1:
            record["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"][0][
                "isResolved"
            ] = False
        return record

    with pytest.raises(ReceiptValidationError, match="disagrees with live GitHub GraphQL"):
        _validate_receipt_impl(
            _valid_receipt(),
            _schema(),
            evidence_root=tmp_path,
            github_get_json=_fake_github_get_json,
            github_get_review_threads=unresolved_get,
        )


def test_r00_selected_remediation_must_be_the_final_live_thread_reply(tmp_path):
    _materialize_evidence(tmp_path)

    def later_negative_reply_get(pr_number: int):
        record = copy.deepcopy(_fake_github_get_review_threads(pr_number))
        if pr_number == R00_RECEIPT_PR:
            thread = record["data"]["repository"]["pullRequest"]["reviewThreads"][
                "nodes"
            ][0]
            root = thread["comments"]["nodes"][0]
            thread["comments"]["nodes"].append({
                "author": {"login": "review-bot"},
                "body": "P1 CRITICAL: remediation is invalid; DO NOT MERGE",
                "fullDatabaseId": "9999999996",
                "id": "PRRC_later_negative",
                "path": root["path"],
                "pullRequestReview": {"fullDatabaseId": root["pullRequestReview"]["fullDatabaseId"]},
                "replyTo": {"fullDatabaseId": root["fullDatabaseId"]},
                "url": (
                    "https://github.com/TriadAgentic/TriadOrigin/pull/7"
                    "#discussion_r9999999996"
                ),
            })
            thread["comments"]["totalCount"] += 1
        return record

    with pytest.raises(
        ReceiptValidationError,
        match="persisted review root|resolution/reply is not authenticated",
    ):
        _validate_receipt_impl(
            _valid_receipt(),
            _schema(),
            evidence_root=tmp_path,
            github_get_json=_fake_github_get_json,
            github_get_review_threads=later_negative_reply_get,
        )


@pytest.mark.parametrize("field", ["body", "author", "node-id"])
def test_r00_live_graphql_rejects_rewritten_root_identity(tmp_path, field):
    _materialize_evidence(tmp_path)

    def rewritten_root_get(pr_number: int):
        record = copy.deepcopy(_fake_github_get_review_threads(pr_number))
        if pr_number == R00_RECEIPT_PR:
            root = record["data"]["repository"]["pullRequest"]["reviewThreads"][
                "nodes"
            ][0]["comments"]["nodes"][0]
            if field == "body":
                root["body"] = "P1 CRITICAL: prior remediation is invalid; DO NOT MERGE"
            elif field == "author":
                root["author"]["login"] = "invented-reviewer"
            else:
                root["id"] = "PRRC_rewritten_root"
        return record

    with pytest.raises(ReceiptValidationError, match="reviewed pre-merge root"):
        _validate_receipt_impl(
            _valid_receipt(),
            _schema(),
            evidence_root=tmp_path,
            github_get_json=_fake_github_get_json,
            github_get_review_threads=rewritten_root_get,
        )


def test_r00_reviewed_root_manifest_rejects_coordinated_negative_rewrite(tmp_path):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    negative = "P1 CRITICAL: prior remediation is invalid; DO NOT MERGE"
    export = json.loads((tmp_path / "evidence/R00/review-api.json").read_bytes())
    corrective = next(
        pull for pull in export["pull_requests"]
        if pull["pr_number"] == R00_RECEIPT_PR
    )
    corrective["inline_threads"][0]["root"]["body_sha256"] = _sha(
        negative.encode()
    )
    _rewrite_bound_record(tmp_path, receipt, "review-api", export)

    def coordinated_rewrite_get(pr_number: int):
        record = copy.deepcopy(_fake_github_get_review_threads(pr_number))
        if pr_number == R00_RECEIPT_PR:
            record["data"]["repository"]["pullRequest"]["reviewThreads"][
                "nodes"
            ][0]["comments"]["nodes"][0]["body"] = negative
        return record

    with pytest.raises(ReceiptValidationError, match="reviewed pre-merge root"):
        _validate_receipt_impl(
            receipt,
            _schema(),
            evidence_root=tmp_path,
            github_get_json=_fake_github_get_json,
            github_get_review_threads=coordinated_rewrite_get,
        )


def test_r00_live_graphql_snapshots_bind_root_content(tmp_path):
    _materialize_evidence(tmp_path)
    calls = 0

    def racing_root_get(pr_number: int):
        nonlocal calls
        record = copy.deepcopy(_fake_github_get_review_threads(pr_number))
        if pr_number == 1:
            calls += 1
            root = record["data"]["repository"]["pullRequest"]["reviewThreads"][
                "nodes"
            ][0]["comments"]["nodes"][0]
            root["body"] = f"review finding revision {calls}"
        return record

    with pytest.raises(ReceiptValidationError, match="changed during sealing"):
        _validate_receipt_impl(
            _valid_receipt(),
            _schema(),
            evidence_root=tmp_path,
            github_get_json=_fake_github_get_json,
            github_get_review_threads=racing_root_get,
        )


def test_r00_live_graphql_rejects_extra_historical_root_as_nonactionable(tmp_path):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    root_id = "4999999998"
    root_url = (
        "https://github.com/TriadAgentic/TriadOrigin/pull/4"
        f"#discussion_r{root_id}"
    )
    export = json.loads((tmp_path / "evidence/R00/review-api.json").read_bytes())
    pr4 = next(pull for pull in export["pull_requests"] if pull["pr_number"] == 4)
    pr4["inline_threads"].append({
        "id": root_id,
        "is_resolved": False,
        "path": "critical.py",
        "remediation_reply": None,
        "reply_inventory": [],
        "review_id": "5999999997",
        "root": {
            "author": "review-bot",
            "body_sha256": _sha(b"P1 CRITICAL: DO NOT MERGE"),
            "node_id": "PRRC_extra_historical",
            "review_id": "5999999997",
            "url": root_url,
        },
        "thread_node_id": "PRRT_extra_historical",
        "url": root_url,
    })
    _rewrite_bound_record(tmp_path, receipt, "review-api", export)
    review = json.loads((tmp_path / "evidence/R00/review.json").read_bytes())
    review["threads"].append({
        "actionable": False,
        "disposition": "self-classified nonactionable",
        "pr_number": 4,
        "resolved": False,
        "thread_id": root_id,
        "url": root_url,
    })
    review["pr4_thread_count"] += 1
    _rewrite_bound_record(tmp_path, receipt, "review", review)

    def extra_root_get(pr_number: int):
        record = copy.deepcopy(_fake_github_get_review_threads(pr_number))
        if pr_number == 4:
            connection = record["data"]["repository"]["pullRequest"]["reviewThreads"]
            connection["nodes"].append({
                "comments": {
                    "nodes": [{
                        "author": {"login": "review-bot"},
                        "body": "P1 CRITICAL: DO NOT MERGE",
                        "fullDatabaseId": root_id,
                        "id": "PRRC_extra_historical",
                        "path": "critical.py",
                        "pullRequestReview": {"fullDatabaseId": "5999999997"},
                        "replyTo": None,
                        "url": root_url,
                    }],
                    "pageInfo": {"hasNextPage": False},
                    "totalCount": 1,
                },
                "id": "PRRT_extra_historical",
                "isResolved": False,
            })
            connection["totalCount"] += 1
        return record

    with pytest.raises(ReceiptValidationError, match="reviewed controlled set"):
        _validate_receipt_impl(
            receipt,
            _schema(),
            evidence_root=tmp_path,
            github_get_json=_fake_github_get_json,
            github_get_review_threads=extra_root_get,
        )


@pytest.mark.parametrize("connection", ["threads", "comments"])
def test_r00_live_graphql_rejects_incomplete_pagination(tmp_path, connection):
    _materialize_evidence(tmp_path)

    def incomplete_get(pr_number: int):
        record = copy.deepcopy(_fake_github_get_review_threads(pr_number))
        if pr_number == 1:
            threads = record["data"]["repository"]["pullRequest"]["reviewThreads"]
            target = threads if connection == "threads" else threads["nodes"][0]["comments"]
            target["pageInfo"]["hasNextPage"] = True
        return record

    with pytest.raises(ReceiptValidationError, match="thread revalidation failed"):
        _validate_receipt_impl(
            _valid_receipt(),
            _schema(),
            evidence_root=tmp_path,
            github_get_json=_fake_github_get_json,
            github_get_review_threads=incomplete_get,
        )


def test_r00_live_ci_rejects_fabricated_run_and_job_ids(tmp_path):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    receipt["ci"]["run_id"] = "9"
    record = json.loads((tmp_path / "evidence/R00/ci.json").read_bytes())
    record["run_id"] = "9"
    record["job_id"] = "8"
    _rewrite_bound_record(tmp_path, receipt, "ci", record)

    def mismatched_ci_get(path: str):
        if path.endswith("/actions/runs/9"):
            return copy.deepcopy(_fake_github_get_json(
                "/repos/TriadAgentic/TriadOrigin/actions/runs/1"
            ))
        if path.endswith("/actions/jobs/8"):
            return copy.deepcopy(_fake_github_get_json(
                "/repos/TriadAgentic/TriadOrigin/actions/jobs/2"
            ))
        return copy.deepcopy(_fake_github_get_json(path))

    with pytest.raises(ReceiptValidationError, match="successful exact-head PR #7 run/job"):
        _validate_receipt_impl(
            receipt,
            _schema(),
            evidence_root=tmp_path,
            github_get_json=mismatched_ci_get,
            github_get_review_threads=_fake_github_get_review_threads,
        )


def test_r00_live_review_binds_reviewed_head_to_merge_tree(tmp_path):
    _materialize_evidence(tmp_path)

    def wrong_head_tree_get(path: str):
        record = copy.deepcopy(_fake_github_get_json(path))
        if path.endswith(f"/git/commits/{HEAD40}"):
            record["tree"]["sha"] = "9" * 40
        return record

    with pytest.raises(
        ReceiptValidationError,
        match="not an independent exact-head pre-merge review",
    ):
        _validate_receipt_impl(
            _valid_receipt(),
            _schema(),
            evidence_root=tmp_path,
            github_get_json=wrong_head_tree_get,
            github_get_review_threads=_fake_github_get_review_threads,
        )


def test_r00_live_ci_requires_every_controlled_step_result(tmp_path):
    _materialize_evidence(tmp_path)

    def missing_gate_get(path: str):
        record = copy.deepcopy(_fake_github_get_json(path))
        if path.endswith("/actions/jobs/2"):
            record["steps"] = record["steps"][:-2] + record["steps"][-1:]
        return record

    with pytest.raises(
        ReceiptValidationError,
        match="successful exact-head PR #7 run/job",
    ):
        _validate_receipt_impl(
            _valid_receipt(),
            _schema(),
            evidence_root=tmp_path,
            github_get_json=missing_gate_get,
            github_get_review_threads=_fake_github_get_review_threads,
        )


def test_github_rest_client_requires_token_and_sends_controlled_headers(monkeypatch):
    with pytest.raises(ReceiptValidationError, match="GITHUB_TOKEN"):
        _github_get_json_from_token("")

    observed = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, limit):
            observed["limit"] = limit
            return b'{"number":7}'

    def fake_urlopen(request, *, timeout):
        observed["url"] = request.full_url
        observed["headers"] = dict(request.header_items())
        observed["timeout"] = timeout
        return Response()

    monkeypatch.setattr(
        "tools.validate_milestone_receipt.urllib.request.urlopen", fake_urlopen
    )
    result = _github_get_json_from_token("test-token")(
        "/repos/TriadAgentic/TriadOrigin/pulls/7"
    )
    assert result == {"number": 7}
    assert observed == {
        "headers": {
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer test-token",
            "User-agent": "triad-origin-r00-sealer",
            "X-github-api-version": "2022-11-28",
        },
        "limit": 1_048_577,
        "timeout": 20,
        "url": "https://api.github.com/repos/TriadAgentic/TriadOrigin/pulls/7",
    }


def test_github_graphql_client_is_fixed_bounded_and_fail_closed(monkeypatch):
    observed = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, limit):
            observed["limit"] = limit
            return b'{"data":{"repository":{"pullRequest":{}}}}'

    def fake_urlopen(request, *, timeout):
        observed["url"] = request.full_url
        observed["method"] = request.get_method()
        observed["headers"] = {
            key.lower(): value for key, value in request.header_items()
        }
        observed["body"] = json.loads(request.data)
        observed["timeout"] = timeout
        return Response()

    monkeypatch.setattr(
        "tools.validate_milestone_receipt.urllib.request.urlopen", fake_urlopen
    )
    result = _github_get_review_threads_from_token("test-token")(1)
    assert result == {"data": {"repository": {"pullRequest": {}}}}
    assert observed["url"] == "https://api.github.com/graphql"
    assert observed["method"] == "POST"
    assert observed["timeout"] == 20
    assert observed["limit"] == 1_048_577
    assert observed["body"] == {
        "query": R00_REVIEW_THREADS_QUERY,
        "variables": {"number": 1, "owner": "TriadAgentic", "repo": "TriadOrigin"},
    }
    assert observed["headers"]["authorization"] == "Bearer test-token"
    assert observed["headers"]["content-type"] == "application/json"
    with pytest.raises(ReceiptValidationError, match="uncontrolled"):
        _github_get_review_threads_from_token("test-token")(6)

    class ErrorResponse(Response):
        def read(self, limit):
            return b'{"data":null,"errors":[{"message":"denied"}]}'

    monkeypatch.setattr(
        "tools.validate_milestone_receipt.urllib.request.urlopen",
        lambda request, *, timeout: ErrorResponse(),
    )
    with pytest.raises(ReceiptValidationError, match="partial or has errors"):
        _github_get_review_threads_from_token("test-token")(1)


def test_receipt_missing_toolchain_is_rejected():
    receipt = _valid_receipt()
    receipt.pop("toolchain")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(receipt, _schema())


def test_incomplete_authority_basis_cannot_claim_canonical():
    receipt = _valid_receipt()
    receipt["authority_basis"]["canonical"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(receipt, _schema())


def test_deferred_evidence_requires_exactly_one_internal_or_external_disposition():
    external = _valid_receipt()
    external["deferred_evidence"].append({
        "evidence_id": "money-canary",
        "reason": "ORIGIN is DARK and has no money authority",
        "external_owner": "estate-governance",
        "external_gate": "RC2-G8",
    })
    jsonschema.validate(external, _schema())
    ambiguous = copy.deepcopy(external)
    ambiguous["deferred_evidence"][-1].update({"owner": "origin", "later_milestone": "B09"})
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(ambiguous, _schema())


def test_semantic_validator_rejects_cross_field_sha_mismatches(tmp_path):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    receipt["ci"]["head_sha"] = "4" * 40
    with pytest.raises(ReceiptValidationError, match="ci.head_sha"):
        validate_receipt(receipt, _schema(), evidence_root=tmp_path)
    receipt = _valid_receipt()
    receipt["merge_control"]["expected_head_sha"] = "4" * 40
    with pytest.raises(ReceiptValidationError, match="expected_head_sha"):
        validate_receipt(receipt, _schema(), evidence_root=tmp_path)


def test_r00_receipt_must_bind_the_controlled_corrective_pr(tmp_path):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    receipt["merge_control"]["pr_number"] = 4
    receipt["merge_control"]["url"] = (
        "https://github.com/TriadAgentic/TriadOrigin/pull/4"
    )
    with pytest.raises(ReceiptValidationError, match="corrective PR #7"):
        validate_receipt(receipt, _schema(), evidence_root=tmp_path)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda receipt: receipt["artifacts"][0].__setitem__("sha256", "0" * 64),
        lambda receipt: receipt.__setitem__("receipt_id", "DRAFT-R00-MUST_REPLACE"),
        lambda receipt: receipt["tests"].append(copy.deepcopy(receipt["tests"][0])),
    ],
)
def test_semantic_validator_rejects_sentinels_and_duplicate_evidence(mutate, tmp_path):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    mutate(receipt)
    with pytest.raises(ReceiptValidationError):
        validate_receipt(receipt, _schema(), evidence_root=tmp_path)


def test_semantic_validator_rejects_missing_tampered_or_unbound_preimages(tmp_path):
    receipt = _valid_receipt()
    with pytest.raises(ReceiptValidationError, match="missing"):
        validate_receipt(receipt, _schema(), evidence_root=tmp_path)
    _materialize_evidence(tmp_path)
    (tmp_path / "evidence/R00/review.json").write_text("tampered", encoding="utf-8")
    with pytest.raises(ReceiptValidationError, match="digest mismatch"):
        validate_receipt(receipt, _schema(), evidence_root=tmp_path)
    _materialize_evidence(tmp_path)
    receipt["evidence_files"] = [
        item for item in receipt["evidence_files"] if item["evidence_id"] != "review"
    ]
    with pytest.raises(ReceiptValidationError, match="lack persisted preimages"):
        validate_receipt(receipt, _schema(), evidence_root=tmp_path)


def test_semantic_validator_recomputes_scope_digest(tmp_path):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    receipt["scope"] += " changed"
    with pytest.raises(ReceiptValidationError, match="scope_sha256"):
        validate_receipt(receipt, _schema(), evidence_root=tmp_path)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda receipt: receipt["tests"][0].__setitem__("passed", 2),
        lambda receipt: receipt["tests"][0].__setitem__("command", "different"),
        lambda receipt: receipt["toolchain"].__setitem__("runner_image", "different"),
        lambda receipt: receipt["review"].__setitem__("reviewer", "different"),
    ],
)
def test_typed_evidence_must_agree_with_claims(mutate, tmp_path):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    mutate(receipt)
    with pytest.raises(ReceiptValidationError, match="typed evidence claim mismatch"):
        validate_receipt(receipt, _schema(), evidence_root=tmp_path)


def test_evidence_kind_cannot_be_reused_across_claim_classes(tmp_path):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    receipt["evidence_files"][0]["kind"] = "artifact"
    with pytest.raises(ReceiptValidationError, match="evidence kind"):
        validate_receipt(receipt, _schema(), evidence_root=tmp_path)


def test_r00_corrective_base_must_be_the_pr4_implementation_merge(tmp_path):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    receipt["base_sha"] = "1" * 40
    merge = json.loads((tmp_path / "evidence/R00/merge.json").read_bytes())
    merge["base_sha"] = receipt["base_sha"]
    _rewrite_bound_record(tmp_path, receipt, "merge", merge)
    with pytest.raises(ReceiptValidationError, match="corrective base"):
        validate_receipt(receipt, _schema(), evidence_root=tmp_path)


def test_r00_failed_pr4_attempt_is_a_typed_exact_predecessor(tmp_path):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    record = json.loads((tmp_path / "evidence/R00/failed-attempt.json").read_bytes())
    record["sdist_sha256"] = "f" * 64
    _rewrite_bound_record(tmp_path, receipt, "failed-attempt", record)
    with pytest.raises(ReceiptValidationError, match="failed PR #4 receipt attempt"):
        validate_receipt(receipt, _schema(), evidence_root=tmp_path)


def test_r00_requires_full_gate_artifact_manifest_and_deferral_set(tmp_path):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    receipt["tests"] = receipt["tests"][:-1]
    with pytest.raises(ReceiptValidationError, match="controlled required command set"):
        validate_receipt(receipt, _schema(), evidence_root=tmp_path)
    receipt = _valid_receipt()
    receipt["artifacts"] = receipt["artifacts"][:1]
    with pytest.raises(ReceiptValidationError, match="sdist"):
        validate_receipt(receipt, _schema(), evidence_root=tmp_path)
    receipt = _valid_receipt()
    receipt["deferred_evidence"] = []
    with pytest.raises(ReceiptValidationError, match="required deferral"):
        validate_receipt(receipt, _schema(), evidence_root=tmp_path)


def test_r00_review_inventory_cannot_be_an_empty_assertion(tmp_path):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    record = json.loads((tmp_path / "evidence/R00/review.json").read_bytes())
    record["threads"] = []
    _rewrite_bound_record(tmp_path, receipt, "review", record)
    with pytest.raises(ReceiptValidationError, match="14 inherited threads"):
        validate_receipt(receipt, _schema(), evidence_root=tmp_path)


def test_r00_known_review_thread_requires_api_resolution_reply(tmp_path):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    record = json.loads((tmp_path / "evidence/R00/review-api.json").read_bytes())
    record["pull_requests"][0]["inline_threads"][0]["remediation_reply"] = None
    _rewrite_bound_record(tmp_path, receipt, "review-api", record)
    with pytest.raises(ReceiptValidationError, match="resolution reply"):
        validate_receipt(receipt, _schema(), evidence_root=tmp_path)


def test_r00_review_export_must_cover_the_corrective_pr(tmp_path):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    record = json.loads((tmp_path / "evidence/R00/review-api.json").read_bytes())
    record["pull_requests"] = [
        pull for pull in record["pull_requests"]
        if pull["pr_number"] != R00_RECEIPT_PR
    ]
    _rewrite_bound_record(tmp_path, receipt, "review-api", record)
    with pytest.raises(ReceiptValidationError, match="PR #7"):
        validate_receipt(receipt, _schema(), evidence_root=tmp_path)


def test_r00_review_export_must_retain_the_pr4_implementation_review(tmp_path):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    record = json.loads((tmp_path / "evidence/R00/review-api.json").read_bytes())
    next(pull for pull in record["pull_requests"] if pull["pr_number"] == 4)[
        "reviews"
    ] = []
    _rewrite_bound_record(tmp_path, receipt, "review-api", record)
    with pytest.raises(ReceiptValidationError, match="PR #4 implementation review"):
        validate_receipt(receipt, _schema(), evidence_root=tmp_path)


def test_r00_actionable_pr7_thread_requires_a_final_merge_reply(tmp_path):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    export = json.loads((tmp_path / "evidence/R00/review-api.json").read_bytes())
    corrective = next(
        pull for pull in export["pull_requests"]
        if pull["pr_number"] == R00_RECEIPT_PR
    )
    corrective["inline_threads"][0]["remediation_reply"] = None
    _rewrite_bound_record(tmp_path, receipt, "review-api", export)
    with pytest.raises(ReceiptValidationError, match="resolution reply"):
        validate_receipt(receipt, _schema(), evidence_root=tmp_path)


def test_r00_final_review_requires_api_bound_exact_head_pass_body(tmp_path):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    record = json.loads((tmp_path / "evidence/R00/review-api.json").read_bytes())
    final_id = json.loads((tmp_path / "evidence/R00/review.json").read_bytes())[
        "final_review"
    ]["review_id"]
    next(
        review
        for review in record["pull_requests"][4]["reviews"]
        if review["review_id"] == final_id
    )["body"] = "ordinary comment"
    _rewrite_bound_record(tmp_path, receipt, "review-api", record)
    with pytest.raises(ReceiptValidationError, match="final review"):
        validate_receipt(receipt, _schema(), evidence_root=tmp_path)


@pytest.mark.parametrize(
    ("state", "submitted_at"),
    [
        ("CHANGES_REQUESTED", "2026-08-09T01:30:00Z"),
        ("COMMENTED", "2026-08-09T01:30:00Z"),
        ("DISMISSED", "2026-08-09T01:30:00Z"),
        ("COMMENTED", "2026-08-09T01:00:00Z"),
    ],
)
def test_r00_complete_review_inventory_rejects_later_premerge_review(
    tmp_path, state, submitted_at
):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    review_id = "6999999999"
    body = "P1 CRITICAL: DO NOT MERGE"
    normalized = {
        "body": body,
        "commit_id": HEAD40,
        "review_id": review_id,
        "reviewer": "independent-reviewer",
        "state": state,
        "submitted_at": submitted_at,
        "url": (
            "https://github.com/TriadAgentic/TriadOrigin/pull/7"
            f"#pullrequestreview-{review_id}"
        ),
    }
    export = json.loads((tmp_path / "evidence/R00/review-api.json").read_bytes())
    corrective = next(
        pull for pull in export["pull_requests"]
        if pull["pr_number"] == R00_RECEIPT_PR
    )
    corrective["reviews"].append(normalized)
    _rewrite_bound_record(tmp_path, receipt, "review-api", export)

    def later_review_get(path: str):
        value = copy.deepcopy(_fake_github_get_json(path))
        if path == "/repos/TriadAgentic/TriadOrigin/pulls/7/reviews?per_page=100&page=1":
            value.append({
                "body": body,
                "commit_id": HEAD40,
                "html_url": normalized["url"],
                "id": int(review_id),
                "state": state,
                "submitted_at": normalized["submitted_at"],
                "user": {"login": normalized["reviewer"]},
            })
        return value

    with pytest.raises(ReceiptValidationError, match="independent exact-head pre-merge"):
        _validate_receipt_impl(
            receipt,
            _schema(),
            evidence_root=tmp_path,
            github_get_json=later_review_get,
            github_get_review_threads=_fake_github_get_review_threads,
        )


def test_r00_complete_review_inventory_rejects_unpersisted_live_review(tmp_path):
    _materialize_evidence(tmp_path)

    def unpersisted_review_get(path: str):
        value = copy.deepcopy(_fake_github_get_json(path))
        if path == "/repos/TriadAgentic/TriadOrigin/pulls/7/reviews?per_page=100&page=1":
            value.append({
                "body": "P1 CRITICAL: DO NOT MERGE",
                "commit_id": HEAD40,
                "html_url": (
                    "https://github.com/TriadAgentic/TriadOrigin/pull/7"
                    "#pullrequestreview-6999999998"
                ),
                "id": 6999999998,
                "state": "CHANGES_REQUESTED",
                "submitted_at": "2026-08-09T01:30:00Z",
                "user": {"login": "independent-reviewer"},
            })
        return value

    with pytest.raises(ReceiptValidationError, match="independent exact-head pre-merge"):
        _validate_receipt_impl(
            _valid_receipt(),
            _schema(),
            evidence_root=tmp_path,
            github_get_json=unpersisted_review_get,
            github_get_review_threads=_fake_github_get_review_threads,
        )


def test_r00_complete_review_inventory_rejects_earlier_changes_requested(tmp_path):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    review_id = "6999999997"
    normalized = {
        "body": "P1 CRITICAL: DO NOT MERGE",
        "commit_id": HEAD40,
        "review_id": review_id,
        "reviewer": "independent-reviewer",
        "state": "CHANGES_REQUESTED",
        "submitted_at": "2026-08-09T00:45:00Z",
        "url": (
            "https://github.com/TriadAgentic/TriadOrigin/pull/7"
            f"#pullrequestreview-{review_id}"
        ),
    }
    export = json.loads((tmp_path / "evidence/R00/review-api.json").read_bytes())
    corrective = next(
        pull for pull in export["pull_requests"]
        if pull["pr_number"] == R00_RECEIPT_PR
    )
    corrective["reviews"].insert(-1, normalized)
    _rewrite_bound_record(tmp_path, receipt, "review-api", export)

    def changes_requested_get(path: str):
        value = copy.deepcopy(_fake_github_get_json(path))
        if path == "/repos/TriadAgentic/TriadOrigin/pulls/7/reviews?per_page=100&page=1":
            value.insert(-1, {
                "body": normalized["body"],
                "commit_id": HEAD40,
                "html_url": normalized["url"],
                "id": int(review_id),
                "state": normalized["state"],
                "submitted_at": normalized["submitted_at"],
                "user": {"login": normalized["reviewer"]},
            })
        return value

    with pytest.raises(ReceiptValidationError, match="independent exact-head pre-merge"):
        _validate_receipt_impl(
            receipt,
            _schema(),
            evidence_root=tmp_path,
            github_get_json=changes_requested_get,
            github_get_review_threads=_fake_github_get_review_threads,
        )


def test_r00_complete_review_inventory_rejects_snapshot_race(tmp_path):
    _materialize_evidence(tmp_path)
    page_one_calls = 0

    def racing_reviews_get(path: str):
        nonlocal page_one_calls
        value = copy.deepcopy(_fake_github_get_json(path))
        if path == "/repos/TriadAgentic/TriadOrigin/pulls/7/reviews?per_page=100&page=1":
            page_one_calls += 1
            if page_one_calls == 2:
                value.append({
                    "body": "late review",
                    "commit_id": HEAD40,
                    "html_url": (
                        "https://github.com/TriadAgentic/TriadOrigin/pull/7"
                        "#pullrequestreview-6999999996"
                    ),
                    "id": 6999999996,
                    "state": "COMMENTED",
                    "submitted_at": "2026-08-09T01:15:00Z",
                    "user": {"login": "independent-reviewer"},
                })
        return value

    with pytest.raises(ReceiptValidationError, match="independent exact-head pre-merge"):
        _validate_receipt_impl(
            _valid_receipt(),
            _schema(),
            evidence_root=tmp_path,
            github_get_json=racing_reviews_get,
            github_get_review_threads=_fake_github_get_review_threads,
        )


def test_r00_sdist_must_carry_the_reviewed_dependency_snapshot(tmp_path):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    original = (tmp_path / "evidence/R00/triad-origin.tar.gz").read_bytes()
    rebuilt = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(original), mode="r:*") as source:
        with tarfile.open(fileobj=rebuilt, mode="w") as target:
            for member in source.getmembers():
                if member.name.endswith("/constraints/ci.txt"):
                    continue
                stream = source.extractfile(member) if member.isfile() else None
                target.addfile(member, stream)
    _rewrite_bound_bytes(tmp_path, receipt, "sdist", rebuilt.getvalue())
    with pytest.raises(ReceiptValidationError, match="sdist evidence"):
        validate_receipt(receipt, _schema(), evidence_root=tmp_path)


def test_r00_dependency_spec_must_equal_reviewed_constraints(tmp_path):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    forged_spec = b"pytest==9.1.1\nwheel==0.43\n"
    _rewrite_bound_bytes(tmp_path, receipt, "dependency-spec", forged_spec)
    toolchain = json.loads((tmp_path / "evidence/R00/toolchain.json").read_bytes())
    toolchain["dependency_spec_sha256"] = _sha(forged_spec)
    toolchain["packages"] = ["pytest==9.1.1", "wheel==0.43"]
    _rewrite_bound_record(tmp_path, receipt, "toolchain", toolchain)
    with pytest.raises(ReceiptValidationError, match="reviewed constraints/ci.txt"):
        validate_receipt(receipt, _schema(), evidence_root=tmp_path)


@pytest.mark.parametrize(
    "forged_pin",
    [
        "example==1.*",
        "example==1.0.*",
        "example==",
        "example==not-a-version",
        "example==1..0",
        "example>=1.0",
        "example~=1.0",
        "example===1.0",
        "example==1.0,==2.0",
        "example[extra]==1.0",
        "example @ https://e.invalid/example.whl",
        " example==1.0",
        "example == 1.0",
        "example==1.0 ",
        "example==1.0 --hash=sha256:abc",
        "example==1.0 # pinned",
        "example==1.0;python_version>'3.11'",
    ],
)
def test_r00_dependency_snapshot_requires_concrete_exact_pins(tmp_path, forged_pin):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    toolchain = json.loads((tmp_path / "evidence/R00/toolchain.json").read_bytes())
    toolchain["packages"].append(forged_pin)
    _rewrite_bound_record(tmp_path, receipt, "toolchain", toolchain)
    with pytest.raises(ReceiptValidationError, match="empty, unpinned, or omits constraints"):
        validate_receipt(receipt, _schema(), evidence_root=tmp_path)


def test_r00_dependency_snapshot_rejects_duplicate_normalized_project_names(tmp_path):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    toolchain = json.loads((tmp_path / "evidence/R00/toolchain.json").read_bytes())
    toolchain["packages"].extend(["Example_Name==1.0", "example-name==1.0"])
    _rewrite_bound_record(tmp_path, receipt, "toolchain", toolchain)
    with pytest.raises(ReceiptValidationError, match="empty, unpinned, or omits constraints"):
        validate_receipt(receipt, _schema(), evidence_root=tmp_path)


def test_r00_dependency_pin_parser_accepts_concrete_pep440_subset():
    assert (
        _exact_dependency_pin_name(
            "Example_Name==1!2.0rc3.post4.dev5+linux.x86_64"
        )
        == "example-name"
    )


def test_r00_dependency_snapshot_cannot_be_omitted_from_source_and_sdist(tmp_path):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    source = json.loads((tmp_path / "evidence/R00/source.manifest.json").read_bytes())
    source["files"] = [
        entry for entry in source["files"]
        if entry["path"] != "constraints/ci.txt"
    ]
    reduced_tree = _git_tree_sha(source["files"])
    source["tree_sha"] = reduced_tree
    _rewrite_bound_record(tmp_path, receipt, "source-tree", source)
    receipt["merge_control"]["tree_sha"] = reduced_tree
    merge = json.loads((tmp_path / "evidence/R00/merge.json").read_bytes())
    merge["tree_sha"] = reduced_tree
    _rewrite_bound_record(tmp_path, receipt, "merge", merge)

    original = (tmp_path / "evidence/R00/triad-origin.tar.gz").read_bytes()
    rebuilt = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(original), mode="r:*") as source_archive:
        with tarfile.open(fileobj=rebuilt, mode="w") as target_archive:
            for member in source_archive.getmembers():
                if member.name.endswith("/constraints/ci.txt"):
                    continue
                stream = source_archive.extractfile(member) if member.isfile() else None
                target_archive.addfile(member, stream)
    _rewrite_bound_bytes(tmp_path, receipt, "sdist", rebuilt.getvalue())

    receipt_path = _materialize_git_seal(tmp_path, receipt)
    with pytest.raises(ReceiptValidationError) as caught:
        validate_receipt(
            receipt,
            _schema(),
            evidence_root=tmp_path,
            git_root=tmp_path,
            receipt_path=receipt_path,
        )
    message = str(caught.value)
    assert "R00 sdist evidence is not a valid distribution archive" in message
    assert "merge commit tree does not equal merge_control.tree_sha" in message


@pytest.mark.parametrize("mutation", ["extra-pth", "runtime-dependency"])
def test_r00_wheel_is_closed_and_metadata_matches_reviewed_project(tmp_path, mutation):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    wheel_path = tmp_path / "evidence/R00/triad_origin.whl"
    with zipfile.ZipFile(io.BytesIO(wheel_path.read_bytes())) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    record_name = next(name for name in members if name.endswith(".dist-info/RECORD"))
    if mutation == "extra-pth":
        members["triad_origin_bootstrap.pth"] = b"import sys; raise SystemExit(99)\n"
    else:
        metadata_name = next(name for name in members if name.endswith(".dist-info/METADATA"))
        members[metadata_name] += b"Requires-Dist: attacker-package\n"
    members[record_name] = _wheel_record(members, record_name)
    _rewrite_bound_bytes(tmp_path, receipt, "wheel", _zip_bytes(members))
    with pytest.raises(ReceiptValidationError, match="wheel evidence"):
        validate_receipt(receipt, _schema(), evidence_root=tmp_path)


def test_command_set_must_enforce_absolute_constraint_and_fresh_identity(tmp_path):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    record = json.loads((tmp_path / "evidence/R00/command-set.json").read_bytes())
    record["environment"].pop("PIP_CONSTRAINT")
    _rewrite_bound_record(tmp_path, receipt, "command-set", record)
    # Post-merge typed evidence also binds the command-set digest; update it so this probe reaches
    # the actual environment invariant rather than failing only on a stale cross-record hash.
    post = json.loads((tmp_path / "evidence/R00/post-merge.json").read_bytes())
    post["command_set_sha256"] = receipt["post_merge"]["command_set_sha256"]
    _rewrite_bound_record(tmp_path, receipt, "post-merge", post)
    with pytest.raises(ReceiptValidationError, match="PIP_CONSTRAINT"):
        validate_receipt(receipt, _schema(), evidence_root=tmp_path)
