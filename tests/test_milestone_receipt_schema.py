"""Milestone receipts bind every claim-bearing digest to a persisted typed preimage."""

from __future__ import annotations

import base64
import csv
import copy
import hashlib
import io
import json
import pathlib
import tarfile
import zipfile

import jsonschema
import pytest

from triad_origin.canonical import canonical_json
from tools.validate_milestone_receipt import (
    R00_INHERITED_THREADS,
    R00_KNOWN_PR4_THREADS,
    R00_KNOWN_PR7_THREADS,
    R00_RECEIPT_PR,
    R00_REVIEW_PRS,
    R00_REQUIRED_COMMANDS,
    ReceiptValidationError,
    _git_tree_sha,
    validate_receipt,
)

SCHEMA_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / "docs"
    / "plan"
    / "milestone_receipt.schema.json"
)
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE40 = "1" * 40
HEAD40 = "2" * 40
MERGE40 = "3" * 40
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
    final_review_body = (
        f"R00_REVIEW_VERDICT: PASS\nHEAD: {HEAD40}\nP0: 0\nP1: 0\n"
    )
    review = _canonical({
        "final_review": {
            "body_sha256": _sha(final_review_body.encode()),
            "head_sha": HEAD40,
            "review_id": final_review_id,
            "reviewer": "independent-reviewer",
            "url": (
                f"https://github.com/TriadAgentic/TriadOrigin/pull/{R00_RECEIPT_PR}"
                f"#pullrequestreview-{final_review_id}"
            ),
            "verdict": "PASS",
        },
        "head_sha": HEAD40,
        "inherited_thread_count": 14,
        "pr4_thread_count": len(R00_KNOWN_PR4_THREADS),
        "reviewed_prs": sorted(R00_REVIEW_PRS),
        "reviewer": "independent-reviewer",
        "schema": "origin.review-evidence.v1",
        "threads": threads,
        "unresolved_actionable_threads": 0,
        "verdict": "PASS",
    })
    review_ids = {1: "4889010117", 2: "4889021032", 3: "4889056077"}
    review_api = _canonical({
        "head_sha": HEAD40,
        "pagination_complete": True,
        "page_info": {"has_next_page": False},
        "pull_requests": [
            {
                "inline_threads": [
                    {
                        "id": thread["thread_id"],
                        "is_resolved": True,
                        "path": "reviewed/path.py",
                        "remediation_reply": {
                            "author": "triad-maintainer",
                            "body": (
                                f"Corrected by squash commit {MERGE40}; sealed evidence: "
                                "evidence/receipts/R00.json"
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
                        "body": final_review_body,
                        "commit_id": HEAD40,
                        "review_id": final_review_id,
                        "reviewer": "independent-reviewer",
                        "state": "COMMENTED",
                        "url": (
                            f"https://github.com/TriadAgentic/TriadOrigin/pull/{R00_RECEIPT_PR}"
                            f"#pullrequestreview-{final_review_id}"
                        ),
                    }]
                    if pr_number == R00_RECEIPT_PR else []
                ),
            }
            for pr_number in sorted(R00_REVIEW_PRS)
        ],
        "repository": "TriadAgentic/TriadOrigin",
        "schema": "origin.github-review-export.v1",
    })
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
            "reviewer": "independent-reviewer",
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
    record["pull_requests"][0]["inline_threads"][0].pop("remediation_reply")
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


def test_r00_final_review_requires_api_bound_exact_head_pass_body(tmp_path):
    _materialize_evidence(tmp_path)
    receipt = _valid_receipt()
    record = json.loads((tmp_path / "evidence/R00/review-api.json").read_bytes())
    record["pull_requests"][4]["reviews"][0]["body"] = "ordinary comment"
    _rewrite_bound_record(tmp_path, receipt, "review-api", record)
    with pytest.raises(ReceiptValidationError, match="final review"):
        validate_receipt(receipt, _schema(), evidence_root=tmp_path)


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
