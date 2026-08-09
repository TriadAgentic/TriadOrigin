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
import urllib.error
import urllib.request
import zipfile
from datetime import datetime
from typing import Any, Callable

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
R00_REQUIRED_CI_STEPS = [
    ("Checkout exact head", "success"),
    ("Bind checks to exact event head", "success"),
    ("Set up Python 3.11", "success"),
    ("Install test toolchain", "success"),
    ("Falsification suite", "success"),
    ("Hash-order invariance", "success"),
    ("Exact pytest collection identity", "success"),
    ("Contract byte manifest", "success"),
    ("Contract manifest schema", "success"),
    ("Reproducible source and wheel artifacts", "success"),
    ("Installed-wheel contract smoke", "success"),
    ("DARK capability boundary", "success"),
    ("Authenticate sealed milestone receipt", "skipped"),
]
R00_REQUIRED_ARTIFACT_KINDS = {"source-tree", "sdist", "wheel"}
R00_REQUIRED_MANIFESTS = {
    "contracts", "failed_attempt", "golden_vectors", "test_collection",
    "test_collection_log",
}
R00_REQUIRED_DEFERRALS = {
    "branch-ruleset": "B00",
    "formula-evidence": "B03",
    "parameter-evidence": "B03",
    "replay-evidence": "B02",
}
_DEPENDENCY_NAME_RE = re.compile(
    r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?"
)
_CONCRETE_VERSION_RE = re.compile(
    r"(?:[0-9]+!)?[0-9]+(?:\.[0-9]+)*"
    r"(?:(?:a|b|rc)[0-9]+)?"
    r"(?:\.post[0-9]+)?"
    r"(?:\.dev[0-9]+)?"
    r"(?:\+[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*)?",
    re.IGNORECASE,
)
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
R00_PR_AUTHOR = "likosubakti"
R00_PR_AUTHOR_ID = "41339678"
R00_REQUIRED_REVIEWER = "chatgpt-codex-connector"
R00_REQUIRED_REVIEWER_ID = "199175422"
R00_IMPLEMENTATION_MERGE_SHA = "241b301d1144e3e2a0a15f4bfe9ffef5b51068ed"
R00_IMPLEMENTATION_BASE_SHA = "69dfd7245fb462992f17e4af06e6746ac2f9d2f0"
R00_IMPLEMENTATION_HEAD_SHA = "b66a95ca84b8660e26c6ff12b3af73cb32aebc04"
R00_IMPLEMENTATION_TREE_SHA = "049c9186b34ded7ad664499249d733af57931fd1"
R00_IMPLEMENTATION_REVIEW_ID = "4889614037"
R00_IMPLEMENTATION_REVIEWER = "likosubakti"
R00_IMPLEMENTATION_REVIEW_URL = (
    "https://github.com/TriadAgentic/TriadOrigin/pull/4"
    f"#pullrequestreview-{R00_IMPLEMENTATION_REVIEW_ID}"
)
R00_IMPLEMENTATION_REVIEW_BODY = (
    f"R00_REVIEW_VERDICT: PASS\nHEAD: {R00_IMPLEMENTATION_HEAD_SHA}\nP0: 0\nP1: 0\n"
)
R00_FAILED_ATTEMPT = {
    "base_sha": R00_IMPLEMENTATION_BASE_SHA,
    "ci_job_id": "93149756437",
    "ci_run_id": "31276105452",
    "corrective_pr": 7,
    "failure_code": "SDIST_MISSING_CONSTRAINT_SNAPSHOT",
    "head_sha": R00_IMPLEMENTATION_HEAD_SHA,
    "merge_sha": R00_IMPLEMENTATION_MERGE_SHA,
    "pr_number": 4,
    "receipt_published": False,
    "schema": "origin.failed-attempt-evidence.v1",
    "sdist_sha256": "4b4a0d0fcd731587ed16aa815bd7208bbfd8a48d6aeb97694a5efd120666eb3b",
    "status": "REJECTED_NO_RECEIPT",
    "tree_sha": R00_IMPLEMENTATION_TREE_SHA,
}
# Exact corrective-review roots observed before the final head. Every row must be live-resolved.
R00_KNOWN_PR7_THREADS: set[str] = {"3741593887"}

# Immutable pre-merge review-root manifest. The full finding text is source-reviewed here
# so a post-merge export cannot legitimize an edited or substituted finding.
R00_REVIEWED_ROOTS: dict[str, dict[str, str | int]] = {
    "3740889446": {
        "author": "chatgpt-codex-connector",
        "body": "**<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub>  Accept additional events from the current fencing epoch**\n\nWhen a producer emits more than one event under the same active lease, the consumer stores the first event's epoch as `highest_accepted`, after which this `<=` check rejects every subsequent legitimate event from that producer. Doc 03 §03.9 specifies rejecting lower tokens while accepting the current token; only a newly promoted producer needs a strictly higher token.\n\nUseful? React with 👍 / 👎.",
        "path": "src/triad_origin/contracts.py",
        "pr_number": 1,
        "review_id": "4889010117",
        "root_node_id": "PRRC_kwDOTyUBrM7e-XFm",
        "thread_node_id": "PRRT_kwDOTyUBrM6Xeuh7",
        "url": "https://github.com/TriadAgentic/TriadOrigin/pull/1#discussion_r3740889446",
    },
    "3740889448": {
        "author": "chatgpt-codex-connector",
        "body": "**<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub>  Enforce schema patterns in the stdlib validation path**\n\nIn a normal runtime installation `jsonschema` is absent because it is only a test extra, so this fallback is the default validation path, but it ignores constraints such as `pattern` and `minLength`. Consequently money-path events such as an execution command with `qty_steps: \"1.5\"` or a fill with `price_ticks: \"01\"` pass `validate()` despite violating their schemas and the canonical integer law; the fallback must enforce these constraints or `jsonschema` must be a runtime dependency.\n\nUseful? React with 👍 / 👎.",
        "path": "src/triad_origin/contracts.py",
        "pr_number": 1,
        "review_id": "4889010117",
        "root_node_id": "PRRC_kwDOTyUBrM7e-XFo",
        "thread_node_id": "PRRT_kwDOTyUBrM6Xeuh9",
        "url": "https://github.com/TriadAgentic/TriadOrigin/pull/1#discussion_r3740889448",
    },
    "3740889449": {
        "author": "chatgpt-codex-connector",
        "body": "**<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub>  Emit the contract manifest in its declared envelope**\n\nThe generated artifact declares `triad.contract_bundle.manifest.v1` but places bundle fields at the root and omits the common envelope and `payload` required by that schema. Validating the committed manifest currently fails immediately with `missing required field 'artifact_sha256'`, so any service consuming the published manifest through the contract validator cannot start or attest the bundle; generate the required envelope or use a separate schema for this artifact shape.\n\nUseful? React with 👍 / 👎.",
        "path": "tools/gen_manifest.py",
        "pr_number": 1,
        "review_id": "4889010117",
        "root_node_id": "PRRC_kwDOTyUBrM7e-XFp",
        "thread_node_id": "PRRT_kwDOTyUBrM6Xeuh-",
        "url": "https://github.com/TriadAgentic/TriadOrigin/pull/1#discussion_r3740889449",
    },
    "3740889452": {
        "author": "chatgpt-codex-connector",
        "body": "**<sub><sub>![P2 Badge](https://img.shields.io/badge/P2-yellow?style=flat)</sub></sub>  Include contract artifacts in installed distributions**\n\nThis repository-relative path works for an editable checkout, but a wheel places `triad_origin` under `site-packages` while the root-level `contracts/` tree is not included by the package-only setuptools configuration. In a normal wheel installation `_REGISTRY.exists()` is therefore false and every `known_contracts()` or `validate()` call fails; package the contract data and resolve it as an installed resource.\n\nUseful? React with 👍 / 👎.",
        "path": "src/triad_origin/contracts.py",
        "pr_number": 1,
        "review_id": "4889010117",
        "root_node_id": "PRRC_kwDOTyUBrM7e-XFs",
        "thread_node_id": "PRRT_kwDOTyUBrM6XeuiA",
        "url": "https://github.com/TriadAgentic/TriadOrigin/pull/1#discussion_r3740889452",
    },
    "3740889453": {
        "author": "chatgpt-codex-connector",
        "body": "**<sub><sub>![P2 Badge](https://img.shields.io/badge/P2-yellow?style=flat)</sub></sub>  Reject finite floats from the integer-only canonical wire**\n\nWhen an identity payload contains a finite float, this branch permits it even though the module's canonical-wire law specifies integer JSON numbers. It consequently encodes mathematically equivalent inputs such as `1` and `1.0` as different bytes and different identity digests, while also permitting semantic calculations to leak floats onto the wire; reject floats or define and enforce an explicit canonical float representation.\n\nUseful? React with 👍 / 👎.",
        "path": "src/triad_origin/canonical.py",
        "pr_number": 1,
        "review_id": "4889010117",
        "root_node_id": "PRRC_kwDOTyUBrM7e-XFt",
        "thread_node_id": "PRRT_kwDOTyUBrM6XeuiB",
        "url": "https://github.com/TriadAgentic/TriadOrigin/pull/1#discussion_r3740889453",
    },
    "3740901367": {
        "author": "chatgpt-codex-connector",
        "body": "**<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub>  Allow subsequent events under the active producer epoch**\n\nWhen a producer emits multiple authoritative events under one lease, every event carries the same fencing epoch. After the first event updates `_epoch[scope]`, this call rejects all later events because `assert_epoch_ge` requires a strictly greater value, effectively limiting each lease to one accepted event. Equality should be accepted for ordinary writes from the currently authorized epoch while lower or revoked epochs remain fenced.\n\nUseful? React with 👍 / 👎.",
        "path": "src/triad_origin/ingress.py",
        "pr_number": 2,
        "review_id": "4889021032",
        "root_node_id": "PRRC_kwDOTyUBrM7e-Z_3",
        "thread_node_id": "PRRT_kwDOTyUBrM6Xewk6",
        "url": "https://github.com/TriadAgentic/TriadOrigin/pull/2#discussion_r3740901367",
    },
    "3740901373": {
        "author": "chatgpt-codex-connector",
        "body": "**<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub>  Include replay metadata in the checkpoint integrity check**\n\nThe checksum covers only `state`, so corruption or modification of `input_offset`, `partition`, `digests`, or `identity_schema_version` still passes `load()`. In particular, a changed input offset makes `replay()` silently skip the wrong prefix, while changed digests can misrepresent the build/config used for the state; the integrity check must authenticate the replay-controlling metadata as well as the state.\n\nUseful? React with 👍 / 👎.",
        "path": "src/triad_origin/checkpoint.py",
        "pr_number": 2,
        "review_id": "4889021032",
        "root_node_id": "PRRC_kwDOTyUBrM7e-Z_9",
        "thread_node_id": "PRRT_kwDOTyUBrM6XewlA",
        "url": "https://github.com/TriadAgentic/TriadOrigin/pull/2#discussion_r3740901373",
    },
    "3740901374": {
        "author": "chatgpt-codex-connector",
        "body": "**<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub>  Preserve receipt order across independent connections**\n\nFor events from different connection epochs or source streams, `venue_sequence` and `receive_sequence` are not globally comparable, yet this key sorts those values before the recorded local receipt time and does not include connection identity. For example, an event received first on connection A with sequence 100 is moved after a later event on connection B with sequence 1, fabricating a cross-connection order and changing causal replay results; sequence ordering must be scoped to its source, with local receipt order preserved across sources.\n\nUseful? React with 👍 / 👎.",
        "path": "src/triad_origin/partition.py",
        "pr_number": 2,
        "review_id": "4889021032",
        "root_node_id": "PRRC_kwDOTyUBrM7e-Z_-",
        "thread_node_id": "PRRT_kwDOTyUBrM6XewlB",
        "url": "https://github.com/TriadAgentic/TriadOrigin/pull/2#discussion_r3740901374",
    },
    "3740901377": {
        "author": "chatgpt-codex-connector",
        "body": "**<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub>  Keep revoked scopes closed until a lease is accepted**\n\nAfter `revoke(scope)`, any message carrying an arbitrary token greater than the previously accepted value passes this branch even though no replacement lease has been validated. This lets writes bypass revocation merely by guessing a higher token; a revoked scope should reject every write until `accept()` validates an active higher-token lease and clears the revoked state.\n\nUseful? React with 👍 / 👎.",
        "path": "src/triad_origin/lease.py",
        "pr_number": 2,
        "review_id": "4889021032",
        "root_node_id": "PRRC_kwDOTyUBrM7e-aAB",
        "thread_node_id": "PRRT_kwDOTyUBrM6XewlD",
        "url": "https://github.com/TriadAgentic/TriadOrigin/pull/2#discussion_r3740901377",
    },
    "3740901381": {
        "author": "chatgpt-codex-connector",
        "body": "**<sub><sub>![P2 Badge](https://img.shields.io/badge/P2-yellow?style=flat)</sub></sub>  Emit a contract-valid heartbeat capability value**\n\nWhenever this payload is inserted into a `triad.service_heartbeat.v1` envelope, contract validation rejects it because that schema defines `payload.side_effect_capability` as a string while the builder always returns an object. Consequently the new health read-face cannot publish its documented heartbeat through the repository's contract boundary; the builder and pinned contract need to agree on one representation.\n\nUseful? React with 👍 / 👎.",
        "path": "src/triad_origin/health.py",
        "pr_number": 2,
        "review_id": "4889021032",
        "root_node_id": "PRRC_kwDOTyUBrM7e-aAF",
        "thread_node_id": "PRRT_kwDOTyUBrM6XewlF",
        "url": "https://github.com/TriadAgentic/TriadOrigin/pull/2#discussion_r3740901381",
    },
    "3740901383": {
        "author": "chatgpt-codex-connector",
        "body": "**<sub><sub>![P2 Badge](https://img.shields.io/badge/P2-yellow?style=flat)</sub></sub>  Serialize quarantine raw references according to the contract**\n\nOn every rejected input, this constructs `raw_reference` as an object, but `triad.quarantine_record.v1` requires that payload field to be a string. Wrapping the returned record in its declared quarantine envelope therefore fails validation precisely on the rejection path, preventing invalid input from producing publishable quarantine evidence.\n\nUseful? React with 👍 / 👎.",
        "path": "src/triad_origin/ingress.py",
        "pr_number": 2,
        "review_id": "4889021032",
        "root_node_id": "PRRC_kwDOTyUBrM7e-aAH",
        "thread_node_id": "PRRT_kwDOTyUBrM6XewlH",
        "url": "https://github.com/TriadAgentic/TriadOrigin/pull/2#discussion_r3740901383",
    },
    "3740938956": {
        "author": "chatgpt-codex-connector",
        "body": "**<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub>  Remove paper from the production promotion ladder**\n\nThis sentence directly contradicts the preceding release-blocking rule and ADR-005: production is LIVE-only, while paper/replay/simulation must remain separate offline research harnesses. Treating `shadow/paper/live` as three runtime modes can lead M5 configuration and service wiring to preserve the P0-forbidden paper production mode instead of retiring it.\n\nUseful? React with 👍 / 👎.",
        "path": "docs/plan/00_MASTER_PLAN.md",
        "pr_number": 3,
        "review_id": "4889056077",
        "root_node_id": "PRRC_kwDOTyUBrM7e-jLM",
        "thread_node_id": "PRRT_kwDOTyUBrM6Xe3Il",
        "url": "https://github.com/TriadAgentic/TriadOrigin/pull/3#discussion_r3740938956",
    },
    "3740938960": {
        "author": "chatgpt-codex-connector",
        "body": "**<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub>  Keep the lease coordinator work open**\n\nMarking SRV-024 complete removes its P0 control-plane work from every later milestone, but the checked M2 implementation is only an in-process `LeaseCoordinator`: its `_highest` and `_active` dictionaries reset on restart, issuance is not coordinated across processes, and it does not write the permanent DAT-008 fencing/audit ledger that this plan also marks complete on line 65. A restart or two coordinator instances can therefore reuse the same token, so the plan must retain ownership for a durable, race-safe Platform lease service/store.\n\nUseful? React with 👍 / 👎.",
        "path": "docs/plan/02_TRACEABILITY.md",
        "pr_number": 3,
        "review_id": "4889056077",
        "root_node_id": "PRRC_kwDOTyUBrM7e-jLQ",
        "thread_node_id": "PRRT_kwDOTyUBrM6Xe3Ip",
        "url": "https://github.com/TriadAgentic/TriadOrigin/pull/3#discussion_r3740938960",
    },
    "3740938963": {
        "author": "chatgpt-codex-connector",
        "body": "**<sub><sub>![P2 Badge](https://img.shields.io/badge/P2-yellow?style=flat)</sub></sub>  Assign the omitted OPS inventory items**\n\nThe advertised traceability is incomplete: a repo-wide search of `docs/plan` finds no `OPS-*` mapping at all, and the milestone deliverables do not assign required work such as the immutable build artifact (OPS-001), dedicated service definition (OPS-004), post-deploy replay smoke (OPS-006), or 26-hour ingress soak (OPS-009). Because this document says milestone scope is fixed, those inventory items can silently remain unimplemented when M6 is declared complete; map them to a milestone or explicitly defer/block each one.\n\nUseful? React with 👍 / 👎.",
        "path": "docs/plan/README.md",
        "pr_number": 3,
        "review_id": "4889056077",
        "root_node_id": "PRRC_kwDOTyUBrM7e-jLT",
        "thread_node_id": "PRRT_kwDOTyUBrM6Xe3Is",
        "url": "https://github.com/TriadAgentic/TriadOrigin/pull/3#discussion_r3740938963",
    },
    "3741134194": {
        "author": "chatgpt-codex-connector",
        "body": "**<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub>  Version the expanded checkpoint checksum**\n\nAny checkpoint written before this change stores a checksum of `state` only, but `load()` now recomputes it over all integrity material while the format remains `origin.checkpoint.v1`. Consequently, deploying this version with an existing checkpoint always raises `CheckpointError` and prevents warm restore; either introduce a new checkpoint version with explicit migration/fallback handling or preserve verification of the old v1 checksum.\n\nUseful? React with 👍 / 👎.",
        "path": "src/triad_origin/checkpoint.py",
        "pr_number": 4,
        "review_id": "4889242636",
        "root_node_id": "PRRC_kwDOTyUBrM7e_S1y",
        "thread_node_id": "PRRT_kwDOTyUBrM6XfZXt",
        "url": "https://github.com/TriadAgentic/TriadOrigin/pull/4#discussion_r3741134194",
    },
    "3741134196": {
        "author": "chatgpt-codex-connector",
        "body": "**<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub>  Include the contract tree in source distributions**\n\nWhen a wheel is built from an sdist, this copy fails because setuptools does not include the top-level `contracts/` directory in the generated sdist. This also makes the usual `python -m build` flow fail when it builds its wheel from the freshly created sdist, while the new smoke test misses the problem by building directly from the repository checkout; add the contract tree to the sdist manifest/package inputs.\n\nUseful? React with 👍 / 👎.",
        "path": "setup.py",
        "pr_number": 4,
        "review_id": "4889242636",
        "root_node_id": "PRRC_kwDOTyUBrM7e_S10",
        "thread_node_id": "PRRT_kwDOTyUBrM6XfZXu",
        "url": "https://github.com/TriadAgentic/TriadOrigin/pull/4#discussion_r3741134196",
    },
    "3741134197": {
        "author": "chatgpt-codex-connector",
        "body": "**<sub><sub>![P2 Badge](https://img.shields.io/badge/P2-yellow?style=flat)</sub></sub>  Cover standard-library networking in the DARK gate**\n\nThe capability gate can currently pass executable network code such as `import urllib.request; urllib.request.urlopen(...)` or `import http.client`, because neither module root nor the corresponding calls are forbidden. A future runtime change using these standard-library clients would therefore pass the advertised DARK CI boundary despite acquiring network capability; cover these routes or use an import allowlist rather than this incomplete blacklist.\n\nUseful? React with 👍 / 👎.",
        "path": "tools/verify_no_forbidden_capabilities.py",
        "pr_number": 4,
        "review_id": "4889242636",
        "root_node_id": "PRRC_kwDOTyUBrM7e_S11",
        "thread_node_id": "PRRT_kwDOTyUBrM6XfZXv",
        "url": "https://github.com/TriadAgentic/TriadOrigin/pull/4#discussion_r3741134197",
    },
    "3741211095": {
        "author": "chatgpt-codex-connector",
        "body": "**<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub>  Reject writes for scopes without an accepted lease**\n\nFor a fresh `ConsumerFence`, `_highest.get(scope, 0)` makes every positive token pass `accepts_write()` even when `accept()` has never validated an active lease for that scope. A caller can therefore authorize a guessed token on a new scope, bypassing the verify-only lease boundary; require the scope to exist in the accepted-token map before permitting writes.\n\nUseful? React with 👍 / 👎.",
        "path": "src/triad_origin/lease.py",
        "pr_number": 4,
        "review_id": "4889327416",
        "root_node_id": "PRRC_kwDOTyUBrM7e_lnX",
        "thread_node_id": "PRRT_kwDOTyUBrM6XfnSk",
        "url": "https://github.com/TriadAgentic/TriadOrigin/pull/4#discussion_r3741211095",
    },
    "3741211096": {
        "author": "chatgpt-codex-connector",
        "body": "**<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub>  Bind the CI evidence SHA to the receipt head**\n\nWhen a receipt supplies different well-formed values for top-level `head_sha` and `ci.head_sha`, this schema still validates it as `VERIFIED`. That allows a successful CI run for an unrelated commit to satisfy the documented exact-head gate; remove the duplicated identity or add a receipt validator that enforces equality before accepting the receipt.\n\nUseful? React with 👍 / 👎.",
        "path": "docs/plan/milestone_receipt.schema.json",
        "pr_number": 4,
        "review_id": "4889327416",
        "root_node_id": "PRRC_kwDOTyUBrM7e_lnY",
        "thread_node_id": "PRRT_kwDOTyUBrM6XfnSl",
        "url": "https://github.com/TriadAgentic/TriadOrigin/pull/4#discussion_r3741211096",
    },
    "3741211097": {
        "author": "chatgpt-codex-connector",
        "body": "**<sub><sub>![P2 Badge](https://img.shields.io/badge/P2-yellow?style=flat)</sub></sub>  Reject noncanonical ordering numbers instead of coercing them**\n\nWhen ordering is invoked before contract validation or on raw replay input, `int()` silently truncates floats and normalizes values such as `\"01\"`, `\"+1\"`, and whitespace-padded strings. This can collapse distinct receipt, connection, or sequence values and change deterministic replay order despite the stated fail-closed behavior; accept only actual integers or the contract's exact canonical decimal syntax.\n\nUseful? React with 👍 / 👎.",
        "path": "src/triad_origin/partition.py",
        "pr_number": 4,
        "review_id": "4889327416",
        "root_node_id": "PRRC_kwDOTyUBrM7e_lnZ",
        "thread_node_id": "PRRT_kwDOTyUBrM6XfnSm",
        "url": "https://github.com/TriadAgentic/TriadOrigin/pull/4#discussion_r3741211097",
    },
    "3741593887": {
        "author": "chatgpt-codex-connector",
        "body": "**<sub><sub>![P1 Badge](https://img.shields.io/badge/P1-orange?style=flat)</sub></sub>  Bind the packaged constraint to dependency evidence**\n\nWhen the receipt captures a dependency-spec/toolchain preimage that differs from the reviewed `constraints/ci.txt`, `_validate_r00_evidence_set` validates each side independently and still accepts the receipt: the sdist bytes are compared only with `source_files`, while `spec_path` is compared only with the toolchain package list. Thus this inclusion can seal a receipt claiming different exact pins from those packaged and reviewed; compare the bound dependency-spec bytes/digest directly with `source_files[\"constraints/ci.txt\"]` and add a mismatch test.\n\nUseful? React with 👍 / 👎.",
        "path": "MANIFEST.in",
        "pr_number": 7,
        "review_id": "4889698522",
        "root_node_id": "PRRC_kwDOTyUBrM7fBDEf",
        "thread_node_id": "PRRT_kwDOTyUBrM6XgoL6",
        "url": "https://github.com/TriadAgentic/TriadOrigin/pull/7#discussion_r3741593887",
    },
}

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


GitHubJsonGetter = Callable[[str], Any]
GitHubReviewThreadsGetter = Callable[[int], Any]
R00_REVIEW_THREADS_QUERY = """query R00ReviewThreads($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      reviewThreads(first: 100) {
        totalCount
        pageInfo { hasNextPage }
        nodes {
          id
          isResolved
          comments(first: 100) {
            totalCount
            pageInfo { hasNextPage }
            nodes {
              id
              fullDatabaseId
              url
              body
              path
              createdAt
              updatedAt
              replyTo { fullDatabaseId }
              author { login }
              pullRequestReview { fullDatabaseId }
            }
          }
        }
      }
    }
  }
}"""


def _expected_codex_review_body(head_sha: str) -> str:
    return (
        "\n### 💡 Codex Review\n\n"
        "Here are some automated review suggestions for this pull request.\n\n"
        f"**Reviewed commit:** `{head_sha[:10]}`\n    \n\n"
        "<details> <summary>ℹ️ About Codex in GitHub</summary>\n<br/>\n\n"
        "[Your team has set up Codex to review pull requests in this repo]"
        "(https://chatgpt.com/codex/cloud/settings/general). Reviews are triggered when you\n"
        "- Open a pull request for review\n"
        "- Mark a draft as ready\n"
        "- Comment \"@codex review\".\n\n"
        "If Codex has suggestions, it will comment; otherwise it will react with 👍.\n\n\n\n\n"
        "Codex can also answer questions or update the PR. Try commenting "
        "\"@codex address that feedback\".\n            \n</details>"
    )


def _expected_codex_review_request_body(
    head_sha: str, ci_run_id: str, ci_job_id: str
) -> str:
    return (
        "@codex review\n\n"
        "R00_EXACT_HEAD_REVIEW_V1\n"
        f"head_sha={head_sha}\n"
        f"ci_run_id={ci_run_id}\n"
        f"ci_job_id={ci_job_id}\n"
        "scope=R00_CORRECTIVE_RECEIPT\n"
        "required=P0=0,P1=0"
    )


def _expected_codex_clean_comment_body(head_sha: str) -> str:
    return (
        "Codex Review: Didn't find any major issues. What shall we delve into next?\n\n"
        f"**Reviewed commit:** `{head_sha[:10]}`\n\n"
        "<details> <summary>ℹ️ About Codex in GitHub</summary>\n<br/>\n\n"
        "[Your team has set up Codex to review pull requests in this repo]"
        "(https://chatgpt.com/codex/cloud/settings/general). Reviews are triggered when you\n"
        "- Open a pull request for review\n"
        "- Mark a draft as ready\n"
        "- Comment \"@codex review\".\n\n"
        "If Codex has suggestions, it will comment; otherwise it will react with 👍.\n\n\n\n\n"
        "Codex can also answer questions or update the PR. Try commenting "
        "\"@codex address that feedback\".\n            \n</details>"
    )


def _r00_pr7_preacceptance_review_baseline() -> list[dict[str, str]]:
    """Reviewed, immutable PR #7 review objects that precede final acceptance.

    GitHub does not expose a review-body update timestamp.  Persisting whatever
    the API returns after merge would therefore let a coordinated edit rewrite
    history.  These exact objects were observed before this evidence law was
    committed and are part of the reviewed source, not receipt-authored input.
    """
    first_head = "61f5c417a4a66f769e9ce534fd97ef074f654784"
    pin_head = "71d0400d0610ece52efcaacc958ef4f748418ddd"
    return [
        {
            "body": _expected_codex_review_body(first_head),
            "commit_id": first_head,
            "raw_reviewer": "chatgpt-codex-connector[bot]",
            "review_id": "4889698522",
            "reviewer": R00_REQUIRED_REVIEWER,
            "reviewer_id": R00_REQUIRED_REVIEWER_ID,
            "state": "COMMENTED",
            "submitted_at": "2026-08-08T20:46:32Z",
            "url": (
                "https://github.com/TriadAgentic/TriadOrigin/pull/7"
                "#pullrequestreview-4889698522"
            ),
        },
        {
            "body": "",
            "commit_id": pin_head,
            "raw_reviewer": R00_PR_AUTHOR,
            "review_id": "4889935294",
            "reviewer": R00_PR_AUTHOR,
            "reviewer_id": R00_PR_AUTHOR_ID,
            "state": "COMMENTED",
            "submitted_at": "2026-08-08T22:26:09Z",
            "url": (
                "https://github.com/TriadAgentic/TriadOrigin/pull/7"
                "#pullrequestreview-4889935294"
            ),
        },
        {
            "body": (
                "\n### 💡 Codex Review\n\n"
                "https://github.com/TriadAgentic/TriadOrigin/blob/"
                f"{pin_head}/tools/validate_milestone_receipt.py#L1050-L1051\n"
                "**<sub><sub>![P2 Badge](https://img.shields.io/badge/"
                "P2-yellow?style=flat)</sub></sub>  Reject wildcard versions in the "
                "dependency snapshot**\n\n"
                "When a receipt lists an additional package such as `example==1.*`, "
                "this condition treats it as exactly pinned merely because the string "
                "contains `==`; the reviewed constraint lines can still be a subset, so "
                "the receipt seals while its claimed resolved environment includes a "
                "floating dependency. Parse each package requirement and require a "
                "concrete, non-wildcard version (and reject empty or otherwise malformed "
                "pins) before accepting the toolchain snapshot.\n    \n\n"
                "<details> <summary>ℹ️ About Codex in GitHub</summary>\n<br/>\n\n"
                "[Your team has set up Codex to review pull requests in this repo]"
                "(https://chatgpt.com/codex/cloud/settings/general). Reviews are "
                "triggered when you\n"
                "- Open a pull request for review\n"
                "- Mark a draft as ready\n"
                "- Comment \"@codex review\".\n\n"
                "If Codex has suggestions, it will comment; otherwise it will react "
                "with 👍.\n\n\n\n\n"
                "Codex can also answer questions or update the PR. Try commenting "
                "\"@codex address that feedback\".\n            \n</details>"
            ),
            "commit_id": pin_head,
            "raw_reviewer": "chatgpt-codex-connector[bot]",
            "review_id": "4889942759",
            "reviewer": R00_REQUIRED_REVIEWER,
            "reviewer_id": R00_REQUIRED_REVIEWER_ID,
            "state": "COMMENTED",
            "submitted_at": "2026-08-08T22:30:51Z",
            "url": (
                "https://github.com/TriadAgentic/TriadOrigin/pull/7"
                "#pullrequestreview-4889942759"
            ),
        },
    ]


def _r00_pr7_preacceptance_comment_baseline() -> list[dict[str, str]]:
    """Reviewed PR #7 top-level comment prefix, before the final fresh pair."""
    pin_head = "71d0400d0610ece52efcaacc958ef4f748418ddd"
    observed_head = "73771e53105a915756ae14fac93dc616190c4d1a"
    rows = [
        (
            "5228488965",
            R00_PR_AUTHOR,
            R00_PR_AUTHOR,
            R00_PR_AUTHOR_ID,
            _expected_codex_review_request_body(
                pin_head, "31281524242", "93163545926"
            ),
            "2026-08-08T22:26:35Z",
        ),
        (
            "5228554814",
            R00_PR_AUTHOR,
            R00_PR_AUTHOR,
            R00_PR_AUTHOR_ID,
            (
                "R00_REVIEW_REMEDIATION_V1\n"
                "review_id=4889942759\n"
                "finding=reject-wildcard-dependency-pins\n"
                f"fixed_head={observed_head}\n"
                "ci_run_id=31282292552\n"
                "ci_job_id=93165454686\n"
                "status=FIXED_PENDING_CLEAN_REVIEW\n\n"
                "The receipt sealer now accepts only a narrow concrete "
                "`name==version` grammar, rejects wildcard/range/marker/URL/hash/"
                "malformed pins and normalized duplicate project names, validates raw "
                "non-comment constraint lines without whitespace/duplicate erasure, and "
                "uses the same law in the committed CI snapshot guard. CI passed 465 "
                "tests under each hash seed; reproducible sdist "
                "`8061367b223f9ebf15367752fe0bd28c7fdca0e6ec9efd81f08214e93b969804` "
                "and wheel "
                "`2f2b8546242020c0f555a2944b5c875d090e87f36f887f682306faa2b444eeb3`."
            ),
            "2026-08-08T22:44:51Z",
        ),
        (
            "5228555326",
            R00_PR_AUTHOR,
            R00_PR_AUTHOR,
            R00_PR_AUTHOR_ID,
            _expected_codex_review_request_body(
                observed_head, "31282292552", "93165454686"
            ),
            "2026-08-08T22:44:58Z",
        ),
        (
            "5228567753",
            R00_REQUIRED_REVIEWER,
            "chatgpt-codex-connector[bot]",
            R00_REQUIRED_REVIEWER_ID,
            _expected_codex_clean_comment_body(observed_head),
            "2026-08-08T22:48:28Z",
        ),
    ]
    return [
        {
            "author": author,
            "author_id": author_id,
            "body": body,
            "created_at": created_at,
            "id": comment_id,
            "raw_author": raw_author,
            "updated_at": created_at,
            "url": (
                "https://github.com/TriadAgentic/TriadOrigin/pull/7"
                f"#issuecomment-{comment_id}"
            ),
        }
        for comment_id, author, raw_author, author_id, body, created_at in rows
    ]


def _expected_remediation_reply_body(thread_id: str, merge_sha: str) -> str:
    return (
        "R00_REMEDIATION_CLOSURE_V1\n"
        f"thread_id={thread_id}\n"
        f"remediation_merge={merge_sha}\n"
        "receipt=evidence/receipts/R00.json\n"
        "status=RESOLVED\n"
    )


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
    receipt: dict[str, Any],
    schema: dict[str, Any],
    *,
    evidence_root: pathlib.Path,
    github_get_json: GitHubJsonGetter | None = None,
    github_get_review_threads: GitHubReviewThreadsGetter | None = None,
    git_root: pathlib.Path | None = None,
    receipt_path: pathlib.Path | None = None,
) -> None:
    """Reject receipts whose evidence, live review, or optional Git seal disagrees."""
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
        if receipt["base_sha"] != R00_IMPLEMENTATION_MERGE_SHA:
            problems.append("R00 corrective base does not equal the PR #4 implementation merge")
        if receipt["review"]["reviewer"] != R00_REQUIRED_REVIEWER:
            problems.append("R00 final reviewer is not the independent Codex reviewer")
        if commands != R00_REQUIRED_COMMANDS:
            problems.append("R00 tests do not equal the controlled required command set")
        artifact_kind_list = [artifact["kind"] for artifact in receipt["artifacts"]]
        artifact_kinds = set(artifact_kind_list)
        if not R00_REQUIRED_ARTIFACT_KINDS.issubset(artifact_kinds):
            problems.append("R00 artifacts omit source-tree, sdist, or wheel preimages")
        if len(artifact_kind_list) != len(artifact_kinds):
            problems.append("R00 artifact kinds must be unique; no claim may hide behind a duplicate")
        if not R00_REQUIRED_MANIFESTS.issubset(receipt["manifests"]):
            problems.append(
                "R00 manifests omit failed-attempt, contract, golden-vector, or test identity"
            )
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
    _validate_evidence_files(
        receipt,
        evidence_root,
        problems,
        github_get_json=github_get_json,
        github_get_review_threads=github_get_review_threads,
    )
    if git_root is not None or receipt_path is not None:
        if git_root is None or receipt_path is None:
            problems.append("Git-bound validation requires both git_root and receipt_path")
        else:
            _validate_git_binding(receipt, git_root, receipt_path, problems)
    if problems:
        raise ReceiptValidationError("; ".join(problems))


def _validate_evidence_files(
    receipt: dict[str, Any],
    evidence_root: pathlib.Path,
    problems: list[str],
    *,
    github_get_json: GitHubJsonGetter | None,
    github_get_review_threads: GitHubReviewThreadsGetter | None,
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
        _validate_r00_evidence_set(
            receipt,
            bound,
            root,
            problems,
            github_get_json=github_get_json,
            github_get_review_threads=github_get_review_threads,
        )
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
                "schema": "origin.review-evidence.v2",
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
        expected_review_fields = {
            "schema", "head_sha", "reviewer", "unresolved_actionable_threads", "verdict",
            "reviewed_prs", "inherited_thread_count", "pr4_thread_count", "threads",
        }
        acceptance_fields = {"final_review", "final_reaction"}.intersection(record)
        if len(acceptance_fields) != 1:
            problems.append(
                f"review evidence must contain exactly one final acceptance arm: {item['path']}"
            )
        else:
            expected_review_fields.update(acceptance_fields)
        if receipt["milestone_id"] == "R00":
            expected_review_fields.add("pr_author")
            if record.get("pr_author") != R00_PR_AUTHOR:
                problems.append(f"R00 review evidence omits the PR author: {item['path']}")
        if set(record) != expected_review_fields:
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
                final_reaction = record.get("final_reaction")
                if final_review is not None and (
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
                if final_reaction is not None and (
                    not isinstance(final_reaction, dict)
                    or set(final_reaction) != {
                        "accepted_at", "actor", "actor_id", "ci_job_id", "ci_run_id",
                        "clean_comment_body_sha256", "clean_comment_id", "clean_comment_url",
                        "content", "head_sha", "mode", "reaction_id", "reaction_node_id",
                        "request_body_sha256", "request_comment_id", "request_url", "verdict",
                    }
                    or final_reaction.get("mode") != "codex-clean-comment-pr-confirmation"
                    or final_reaction.get("head_sha") != receipt["head_sha"]
                    or final_reaction.get("verdict") != "PASS"
                    or final_reaction.get("actor") != R00_REQUIRED_REVIEWER
                    or final_reaction.get("actor_id") != R00_REQUIRED_REVIEWER_ID
                    or final_reaction.get("content") != "+1"
                    or any(
                        not isinstance(final_reaction.get(name), str)
                        or not final_reaction[name]
                        for name in {
                            "accepted_at", "ci_job_id", "ci_run_id", "clean_comment_id",
                            "clean_comment_url", "reaction_id", "reaction_node_id",
                            "request_comment_id", "request_url",
                        }
                    )
                ):
                    problems.append(
                        f"R00 final-head reaction evidence is incomplete: {item['path']}"
                    )
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


def _exact_dependency_pin_name(value: Any) -> str | None:
    """Return the normalized project name for one concrete ``name==version`` pin."""

    if not isinstance(value, str) or value != value.strip() or value.count("==") != 1:
        return None
    name, version = value.split("==", 1)
    if _DEPENDENCY_NAME_RE.fullmatch(name) is None:
        return None
    if _CONCRETE_VERSION_RE.fullmatch(version) is None:
        return None
    return re.sub(r"[-_.]+", "-", name).lower()


def _validate_r00_evidence_set(
    receipt: dict[str, Any],
    bound: dict[str, dict[str, Any]],
    root: pathlib.Path,
    problems: list[str],
    *,
    github_get_json: GitHubJsonGetter | None,
    github_get_review_threads: GitHubReviewThreadsGetter | None,
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
            spec_lines = [
                line for line in spec_path.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            ]
            spec_names = [_exact_dependency_pin_name(line) for line in spec_lines]
            snapshot = json.loads(snapshot_path.read_bytes())
            packages = snapshot.get("packages") if isinstance(snapshot, dict) else None
            package_names = (
                [_exact_dependency_pin_name(package) for package in packages]
                if isinstance(packages, list)
                else None
            )
            if (
                not spec_lines
                or any(name is None for name in spec_names)
                or len(spec_names) != len(set(spec_names))
                or not isinstance(packages, list)
                or not packages
                or package_names is None
                or any(name is None for name in package_names)
                or len(package_names) != len(set(package_names))
                or not set(spec_lines).issubset(set(packages))
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
    if spec_path is not None and source_files:
        try:
            reviewed_constraints = source_files["constraints/ci.txt"]
            persisted_constraints = spec_path.read_bytes()
        except (KeyError, OSError):
            reviewed_constraints = None
            persisted_constraints = None
        if reviewed_constraints is None or persisted_constraints != reviewed_constraints:
            problems.append(
                "R00 dependency specification does not equal reviewed constraints/ci.txt"
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
                    prefix + "constraints/ci.txt",
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

    ci_path = target("/ci/evidence_sha256")
    ci_record = None
    if ci_path is not None:
        try:
            ci_record = json.loads(ci_path.read_bytes())
        except (OSError, UnicodeError, json.JSONDecodeError):
            ci_record = None

    review_path = target("/review/review_sha256")
    review_api_path = target("/review/api_export_sha256")
    if review_path is not None and review_api_path is not None:
        _validate_r00_review_export(
            review_path,
            review_api_path,
            receipt["head_sha"],
            receipt["base_sha"],
            receipt["merge_sha"],
            receipt["merge_control"]["tree_sha"],
            receipt["ci"]["run_id"],
            str(ci_record.get("job_id")) if isinstance(ci_record, dict) else "",
            github_get_json,
            github_get_review_threads,
            problems,
        )

    if ci_path is not None:
        _validate_live_r00_ci(
            receipt,
            ci_record,
            github_get_json=github_get_json,
            problems=problems,
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

    failed_path = target("/manifests/failed_attempt")
    try:
        failed_raw = failed_path.read_bytes() if failed_path is not None else b""
        failed_attempt = json.loads(failed_raw)
    except (OSError, UnicodeError, json.JSONDecodeError):
        failed_attempt = None
    if (
        failed_attempt != R00_FAILED_ATTEMPT
        or canonical_json(failed_attempt) != failed_raw
    ):
        problems.append("R00 failed PR #4 receipt attempt is not exactly authenticated")

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
    base_sha: str,
    merge_sha: str,
    tree_sha: str,
    ci_run_id: str,
    ci_job_id: str,
    github_get_json: GitHubJsonGetter | None,
    github_get_review_threads: GitHubReviewThreadsGetter | None,
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
        export.get("schema") != "origin.github-review-export.v2"
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
    review_prs: dict[str, int] = {}
    covered_prs: set[int] = set()
    exported_pulls: dict[int, dict[str, Any]] = {}
    uses_reaction_arm = isinstance(review.get("final_reaction"), dict)
    for pull in export["pull_requests"]:
        if not isinstance(pull, dict) or pull.get("pr_number") not in R00_REVIEW_PRS:
            problems.append("R00 GitHub review export has an invalid pull request row")
            return
        pr_number = pull["pr_number"]
        if pr_number in covered_prs:
            problems.append("R00 GitHub review export has a duplicate pull request row")
            return
        covered_prs.add(pr_number)
        exported_pulls[pr_number] = pull
        expected_pull_fields = {"author", "inline_threads", "pr_number", "reviews"}
        if pr_number == R00_RECEIPT_PR:
            expected_pull_fields.update({
                "issue_comments",
                "pr_reactions",
                "pull_snapshot",
                "timeline",
            })
        if pr_number == R00_RECEIPT_PR and uses_reaction_arm:
            expected_pull_fields.add("selected_comment_reactions")
        if set(pull) != expected_pull_fields:
            problems.append("R00 GitHub review export has contradictory pull-request fields")
            return
        if pr_number == R00_RECEIPT_PR and pull.get("author") != R00_PR_AUTHOR:
            problems.append("R00 GitHub review export does not bind the corrective PR author")
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
                set(comment)
                != {
                    "id",
                    "is_resolved",
                    "path",
                    "remediation_reply",
                    "reply_inventory",
                    "review_id",
                    "root",
                    "thread_node_id",
                    "url",
                }
                or not isinstance(comment.get("thread_node_id"), str)
                or not comment["thread_node_id"]
                or not isinstance(comment.get("root"), dict)
                or not isinstance(comment.get("reply_inventory"), list)
                or not isinstance(comment_id, str)
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
            review_prs[review_id] = pr_number
    if covered_prs != R00_REVIEW_PRS:
        problems.append("R00 GitHub review export does not cover PR #1-#4 and PR #7")
    _validate_live_r00_review_threads(
        exported,
        exported_rows,
        github_get_review_threads=github_get_review_threads,
        problems=problems,
    )
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
    historical_actionable = set(R00_INHERITED_THREADS) | R00_KNOWN_PR4_THREADS
    corrective_actionable = {
        thread_id
        for thread_id, (pr_number, _, _) in exported.items()
        if pr_number == R00_RECEIPT_PR
    }
    known_actionable = historical_actionable | corrective_actionable
    for thread_id in known_actionable:
        api_thread = exported_rows.get(thread_id, {})
        inventory_thread = inventory_rows.get(thread_id, {})
        reply = api_thread.get("remediation_reply")
        pr_number = exported.get(thread_id, (None,))[0]
        expected_reply_url = (
            f"https://github.com/TriadAgentic/TriadOrigin/pull/{pr_number}"
            f"#discussion_r{reply.get('id') if isinstance(reply, dict) else ''}"
        )
        expected_closure_merge = (
            R00_IMPLEMENTATION_MERGE_SHA
            if thread_id in historical_actionable
            else merge_sha
        )
        expected_reply_body = _expected_remediation_reply_body(
            thread_id, expected_closure_merge
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
            or reply["body"] != expected_reply_body
        ):
            problems.append(
                "R00 actionable review thread lacks an API-bound resolution reply and fix/receipt reference"
            )
            break
    historical_review = reviews.get(R00_IMPLEMENTATION_REVIEW_ID)
    if (
        historical_review is None
        or review_prs.get(R00_IMPLEMENTATION_REVIEW_ID) != 4
        or historical_review.get("commit_id") != R00_IMPLEMENTATION_HEAD_SHA
        or historical_review.get("url") != R00_IMPLEMENTATION_REVIEW_URL
        or historical_review.get("reviewer") != R00_IMPLEMENTATION_REVIEWER
        or historical_review.get("state") not in {"APPROVED", "COMMENTED"}
        or historical_review.get("body") != R00_IMPLEMENTATION_REVIEW_BODY
    ):
        problems.append("R00 PR #4 implementation review is absent from the GitHub API export")
    _validate_live_r00_implementation_review(
        github_get_json=github_get_json,
        problems=problems,
    )
    allowed_postmerge_review_ids = {
        str(reply.get("review_id"))
        for row in exported_rows.values()
        if exported.get(str(row.get("id")), (None,))[0] == R00_RECEIPT_PR
        for reply in row.get("reply_inventory", [])
        if isinstance(reply, dict) and str(reply.get("review_id", "")).isdigit()
    }
    pr7_export = exported_pulls.get(R00_RECEIPT_PR, {})
    final_review = review.get("final_review")
    final_reaction = review.get("final_reaction")
    if isinstance(final_review, dict) and final_reaction is None:
        api_final = reviews.get(str(final_review.get("review_id")))
        final_body = api_final.get("body") if isinstance(api_final, dict) else None
        expected_final_body = _expected_codex_review_body(head_sha)
        if (
            api_final is None
            or review_prs.get(str(final_review.get("review_id"))) != R00_RECEIPT_PR
            or api_final.get("commit_id") != head_sha
            or api_final.get("url") != final_review.get("url")
            or api_final.get("reviewer") != final_review.get("reviewer")
            or final_review.get("reviewer") != R00_REQUIRED_REVIEWER
            or final_review.get("reviewer") == R00_PR_AUTHOR
            or api_final.get("state") != "COMMENTED"
            or not isinstance(final_body, str)
            or final_body != expected_final_body
            or final_review.get("body_sha256")
            != hashlib.sha256(final_body.encode("utf-8")).hexdigest()
        ):
            problems.append("R00 final review does not match the exact-head GitHub API export")
        _validate_live_r00_review(
            final_review,
            api_final if isinstance(api_final, dict) else {},
            persisted_comments=pr7_export.get("issue_comments"),
            persisted_reactions=pr7_export.get("pr_reactions"),
            persisted_reviews=pr7_export.get("reviews"),
            persisted_pull=pr7_export.get("pull_snapshot"),
            persisted_threads=pr7_export.get("inline_threads"),
            persisted_timeline=pr7_export.get("timeline"),
            allowed_postmerge_review_ids=allowed_postmerge_review_ids,
            head_sha=head_sha,
            base_sha=base_sha,
            merge_sha=merge_sha,
            tree_sha=tree_sha,
            github_get_json=github_get_json,
            problems=problems,
        )
    elif isinstance(final_reaction, dict) and final_review is None:
        if (
            not isinstance(pr7_export.get("issue_comments"), list)
            or not isinstance(pr7_export.get("pr_reactions"), list)
            or not isinstance(pr7_export.get("timeline"), list)
            or not isinstance(pr7_export.get("pull_snapshot"), dict)
            or not isinstance(pr7_export.get("selected_comment_reactions"), dict)
        ):
            problems.append("R00 clean-reaction export lacks complete acceptance inventories")
        _validate_live_r00_reaction(
            final_reaction,
            persisted_comments=pr7_export.get("issue_comments"),
            persisted_reactions=pr7_export.get("pr_reactions"),
            persisted_reviews=pr7_export.get("reviews"),
            persisted_pull=pr7_export.get("pull_snapshot"),
            persisted_selected_comment_reactions=pr7_export.get(
                "selected_comment_reactions"
            ),
            persisted_threads=pr7_export.get("inline_threads"),
            persisted_timeline=pr7_export.get("timeline"),
            allowed_postmerge_review_ids=allowed_postmerge_review_ids,
            head_sha=head_sha,
            base_sha=base_sha,
            merge_sha=merge_sha,
            tree_sha=tree_sha,
            ci_run_id=ci_run_id,
            ci_job_id=ci_job_id,
            github_get_json=github_get_json,
            problems=problems,
        )
    else:
        problems.append("R00 review evidence must select exactly one final acceptance arm")
    # Separate the two-pair GraphQL reads with the complete REST acceptance read so a
    # thread/comment mutation during sealing cannot hide between adjacent snapshots.
    _validate_live_r00_review_threads(
        exported,
        exported_rows,
        github_get_review_threads=github_get_review_threads,
        problems=problems,
    )


def _decimal_graphql_id(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value) if value >= 0 else None
    if isinstance(value, str) and value.isascii() and value.isdigit():
        return value
    return None


def _validate_live_r00_implementation_review(
    *,
    github_get_json: GitHubJsonGetter | None,
    problems: list[str],
) -> None:
    if github_get_json is None:
        problems.append("R00 sealing requires live PR #4 implementation-review revalidation")
        return
    try:
        review = github_get_json(
            f"/repos/TriadAgentic/TriadOrigin/pulls/4/reviews/"
            f"{R00_IMPLEMENTATION_REVIEW_ID}"
        )
    except Exception as exc:
        problems.append(
            f"R00 live PR #4 implementation-review revalidation failed: {type(exc).__name__}"
        )
        return
    reviewer = _normalized_github_login(
        review.get("user", {}).get("login")
        if isinstance(review, dict) and isinstance(review.get("user"), dict)
        else None
    )
    if (
        not isinstance(review, dict)
        or review.get("id") != int(R00_IMPLEMENTATION_REVIEW_ID)
        or review.get("commit_id") != R00_IMPLEMENTATION_HEAD_SHA
        or review.get("html_url") != R00_IMPLEMENTATION_REVIEW_URL
        or review.get("state") != "COMMENTED"
        or review.get("body") != R00_IMPLEMENTATION_REVIEW_BODY
        or reviewer != R00_IMPLEMENTATION_REVIEWER
    ):
        problems.append("R00 live PR #4 implementation review does not match history")


def _normalize_live_r00_review_threads(
    payloads: dict[int, Any],
) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    comment_ids: set[str] = set()
    comment_node_ids: set[str] = set()
    thread_node_ids: set[str] = set()
    for pr_number in sorted(R00_REVIEW_PRS):
        payload = payloads.get(pr_number)
        try:
            connection = payload["data"]["repository"]["pullRequest"]["reviewThreads"]
            nodes = connection["nodes"]
            page_info = connection["pageInfo"]
        except (KeyError, TypeError):
            raise ValueError("reviewThreads response is partial or malformed") from None
        if (
            not isinstance(connection, dict)
            or not isinstance(nodes, list)
            or connection.get("totalCount") != len(nodes)
            or not isinstance(page_info, dict)
            or page_info.get("hasNextPage") is not False
        ):
            raise ValueError("reviewThreads pagination is incomplete")
        for thread in nodes:
            if not isinstance(thread, dict):
                raise ValueError("review thread is not an object")
            thread_node_id = thread.get("id")
            comments = thread.get("comments")
            if (
                not isinstance(thread_node_id, str)
                or not thread_node_id
                or thread_node_id in thread_node_ids
                or not isinstance(thread.get("isResolved"), bool)
                or not isinstance(comments, dict)
                or not isinstance(comments.get("nodes"), list)
                or comments.get("totalCount") != len(comments["nodes"])
                or not isinstance(comments.get("pageInfo"), dict)
                or comments["pageInfo"].get("hasNextPage") is not False
                or not comments["nodes"]
            ):
                raise ValueError("review thread/comments are malformed or incomplete")
            thread_node_ids.add(thread_node_id)
            roots = [
                comment
                for comment in comments["nodes"]
                if isinstance(comment, dict) and comment.get("replyTo") is None
            ]
            if len(roots) != 1 or comments["nodes"][0] is not roots[0]:
                raise ValueError("review thread does not have one ordered root")
            root = roots[0]
            root_id = _decimal_graphql_id(root.get("fullDatabaseId"))
            root_review = root.get("pullRequestReview")
            root_review_id = _decimal_graphql_id(
                root_review.get("fullDatabaseId")
                if isinstance(root_review, dict)
                else None
            )
            root_author = root.get("author")
            root_node_id = root.get("id")
            root_created_at = root.get("createdAt")
            root_updated_at = root.get("updatedAt")
            expected_root_url = (
                f"https://github.com/TriadAgentic/TriadOrigin/pull/{pr_number}"
                f"#discussion_r{root_id or ''}"
            )
            if (
                root_id is None
                or root_id in comment_ids
                or root_review_id is None
                or root.get("url") != expected_root_url
                or not isinstance(root.get("path"), str)
                or not root["path"]
                or not isinstance(root.get("body"), str)
                or not isinstance(root_node_id, str)
                or not root_node_id
                or root_node_id in comment_node_ids
                or not isinstance(root_author, dict)
                or not isinstance(root_author.get("login"), str)
                or not root_author["login"]
                or _parse_github_time(root_created_at) is None
                or _parse_github_time(root_updated_at) is None
            ):
                raise ValueError("review root identity is malformed")
            root["body"].encode("utf-8")
            comment_ids.add(root_id)
            comment_node_ids.add(root_node_id)
            replies: dict[str, dict[str, str]] = {}
            reply_order: list[str] = []
            reply_inventory: list[dict[str, str]] = []
            for reply in comments["nodes"][1:]:
                reply_to = reply.get("replyTo") if isinstance(reply, dict) else None
                reply_author = reply.get("author") if isinstance(reply, dict) else None
                reply_id = _decimal_graphql_id(
                    reply.get("fullDatabaseId") if isinstance(reply, dict) else None
                )
                linked_root_id = _decimal_graphql_id(
                    reply_to.get("fullDatabaseId")
                    if isinstance(reply_to, dict)
                    else None
                )
                expected_reply_url = (
                    f"https://github.com/TriadAgentic/TriadOrigin/pull/{pr_number}"
                    f"#discussion_r{reply_id or ''}"
                )
                reply_review = reply.get("pullRequestReview") if isinstance(reply, dict) else None
                reply_review_id = _decimal_graphql_id(
                    reply_review.get("fullDatabaseId")
                    if isinstance(reply_review, dict)
                    else None
                )
                reply_node_id = reply.get("id") if isinstance(reply, dict) else None
                reply_created_at = reply.get("createdAt") if isinstance(reply, dict) else None
                reply_updated_at = reply.get("updatedAt") if isinstance(reply, dict) else None
                if (
                    reply_id is None
                    or reply_id in comment_ids
                    or linked_root_id != root_id
                    or reply.get("url") != expected_reply_url
                    or reply.get("path") != root.get("path")
                    or not isinstance(reply.get("body"), str)
                    or not isinstance(reply_node_id, str)
                    or not reply_node_id
                    or reply_node_id in comment_node_ids
                    or reply_review_id is None
                    or not isinstance(reply_author, dict)
                    or not isinstance(reply_author.get("login"), str)
                    or not reply_author["login"]
                    or _parse_github_time(reply_created_at) is None
                    or _parse_github_time(reply_updated_at) is None
                ):
                    raise ValueError("review reply identity is malformed")
                reply["body"].encode("utf-8")
                comment_ids.add(reply_id)
                comment_node_ids.add(reply_node_id)
                reply_order.append(reply_id)
                replies[reply_id] = {
                    "author": reply_author["login"],
                    "body": reply["body"],
                    "id": reply_id,
                    "url": reply["url"],
                }
                reply_inventory.append({
                    "author": reply_author["login"],
                    "body_sha256": hashlib.sha256(
                        reply["body"].encode("utf-8")
                    ).hexdigest(),
                    "created_at": reply_created_at,
                    "id": reply_id,
                    "node_id": reply_node_id,
                    "path": reply["path"],
                    "reply_to_id": root_id,
                    "review_id": reply_review_id,
                    "updated_at": reply_updated_at,
                    "url": reply["url"],
                })
            normalized[root_id] = {
                "is_resolved": thread["isResolved"],
                "path": root["path"],
                "pr_number": pr_number,
                "reply_inventory": reply_inventory,
                "review_id": root_review_id,
                "reply_order": reply_order,
                "replies": replies,
                "root": {
                    "author": root_author["login"],
                    "body_sha256": hashlib.sha256(
                        root["body"].encode("utf-8")
                    ).hexdigest(),
                    "created_at": root_created_at,
                    "node_id": root_node_id,
                    "review_id": root_review_id,
                    "updated_at": root_updated_at,
                    "url": root["url"],
                },
                "thread_node_id": thread_node_id,
                "url": root["url"],
            }
    return normalized


def _validate_live_r00_review_threads(
    exported: dict[str, tuple[int, str, bool]],
    exported_rows: dict[str, dict[str, Any]],
    *,
    github_get_review_threads: GitHubReviewThreadsGetter | None,
    problems: list[str],
) -> None:
    """Authenticate every persisted root, resolution, and selected reply through GraphQL."""
    if github_get_review_threads is None:
        problems.append("R00 sealing requires live GitHub GraphQL thread revalidation")
        return
    snapshots: list[dict[str, dict[str, Any]]] = []
    try:
        for _ in range(2):
            payloads = {
                pr_number: github_get_review_threads(pr_number)
                for pr_number in sorted(R00_REVIEW_PRS)
            }
            snapshots.append(_normalize_live_r00_review_threads(payloads))
    except (KeyError, TypeError, UnicodeError, ValueError) as exc:
        problems.append(f"R00 live GitHub thread revalidation failed: {type(exc).__name__}")
        return
    if snapshots[0] != snapshots[1]:
        problems.append("R00 live GitHub thread inventory changed during sealing")
        return
    live = snapshots[0]
    if set(live) != set(exported_rows):
        problems.append("R00 persisted thread roots do not equal the live GitHub inventory")
        return
    controlled_roots = (
        set(R00_INHERITED_THREADS) | R00_KNOWN_PR4_THREADS | R00_KNOWN_PR7_THREADS
    )
    if set(R00_REVIEWED_ROOTS) != controlled_roots:
        problems.append("R00 reviewed root manifest does not equal the controlled root set")
        return
    if set(live) != controlled_roots:
        problems.append("R00 live GitHub roots do not equal the reviewed controlled set")
        return
    historical_actionable = set(R00_INHERITED_THREADS) | R00_KNOWN_PR4_THREADS
    for thread_id, live_row in live.items():
        persisted = exported_rows[thread_id]
        persisted_identity = exported.get(thread_id)
        reviewed = R00_REVIEWED_ROOTS[thread_id]
        reviewed_root = {
            "author": reviewed["author"],
            "body_sha256": hashlib.sha256(
                str(reviewed["body"]).encode("utf-8")
            ).hexdigest(),
            "node_id": reviewed["root_node_id"],
            "review_id": reviewed["review_id"],
            "url": reviewed["url"],
        }
        live_reviewed_root = {
            key: live_row["root"].get(key) for key in reviewed_root
        }
        if (
            live_row["pr_number"] != reviewed["pr_number"]
            or live_row["path"] != reviewed["path"]
            or live_row["review_id"] != reviewed["review_id"]
            or live_row["thread_node_id"] != reviewed["thread_node_id"]
            or live_reviewed_root != reviewed_root
        ):
            problems.append("R00 live GitHub root differs from the reviewed pre-merge root")
            return
        if (
            persisted_identity
            != (live_row["pr_number"], live_row["url"], live_row["is_resolved"])
            or persisted.get("path") != live_row["path"]
            or persisted.get("review_id") != live_row["review_id"]
            or persisted.get("thread_node_id") != live_row["thread_node_id"]
            or persisted.get("root") != live_row["root"]
            or persisted.get("reply_inventory") != live_row["reply_inventory"]
        ):
            problems.append("R00 persisted review root disagrees with live GitHub GraphQL")
            return
        if thread_id in historical_actionable or live_row["pr_number"] == R00_RECEIPT_PR:
            reply = persisted.get("remediation_reply")
            if (
                live_row["is_resolved"] is not True
                or not isinstance(reply, dict)
                or live_row["replies"].get(str(reply.get("id"))) != reply
                or not live_row["reply_order"]
                or live_row["reply_order"][-1] != str(reply.get("id"))
            ):
                problems.append(
                    "R00 actionable thread resolution/reply is not authenticated by live GitHub GraphQL"
                )
                return


def _parse_github_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.utcoffset() is not None else None


def _normalized_github_login(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return value.removesuffix("[bot]")


def _validate_live_r00_ci(
    receipt: dict[str, Any],
    ci_record: Any,
    *,
    github_get_json: GitHubJsonGetter | None,
    problems: list[str],
) -> None:
    """Authenticate the selected PR #7 exact-head run and job through GitHub Actions."""
    if github_get_json is None:
        problems.append("R00 sealing requires live GitHub Actions revalidation")
        return
    if not isinstance(ci_record, dict):
        problems.append("R00 live CI revalidation lacks typed CI evidence")
        return
    run_id = receipt["ci"].get("run_id")
    job_id = ci_record.get("job_id")
    if (
        not isinstance(run_id, str)
        or not run_id.isdigit()
        or not isinstance(job_id, str)
        or not job_id.isdigit()
    ):
        problems.append("R00 live CI revalidation lacks decimal run/job IDs")
        return
    try:
        run = github_get_json(
            f"/repos/TriadAgentic/TriadOrigin/actions/runs/{run_id}"
        )
        job = github_get_json(
            f"/repos/TriadAgentic/TriadOrigin/actions/jobs/{job_id}"
        )
        pull = github_get_json("/repos/TriadAgentic/TriadOrigin/pulls/7")
    except Exception as exc:
        problems.append(f"R00 live GitHub Actions revalidation failed: {type(exc).__name__}")
        return
    if not isinstance(run, dict) or not isinstance(job, dict) or not isinstance(pull, dict):
        problems.append("R00 live GitHub Actions response has the wrong shape")
        return
    run_finished = _parse_github_time(run.get("updated_at"))
    merged_at = _parse_github_time(pull.get("merged_at"))
    pull_numbers = {
        item.get("number")
        for item in run.get("pull_requests", [])
        if isinstance(item, dict)
    } if isinstance(run.get("pull_requests"), list) else set()
    steps = job.get("steps")
    required_step_names = {name for name, _ in R00_REQUIRED_CI_STEPS}
    controlled_steps = (
        [
            (step.get("name"), step.get("conclusion"))
            for step in steps
            if isinstance(step, dict) and step.get("name") in required_step_names
        ]
        if isinstance(steps, list)
        else []
    )
    steps_ok = controlled_steps == R00_REQUIRED_CI_STEPS
    expected_run_url = (
        f"https://github.com/TriadAgentic/TriadOrigin/actions/runs/{run_id}"
    )
    expected_job_url = f"{expected_run_url}/job/{job_id}"
    if (
        run.get("id") != int(run_id)
        or run.get("event") != "pull_request"
        or run.get("name") != "CI"
        or run.get("path") != ".github/workflows/ci.yml"
        or run.get("head_branch") != "agent/r00-receipt-closure"
        or run.get("head_sha") != receipt["head_sha"]
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
        or run.get("html_url") != expected_run_url
        or pull_numbers != {R00_RECEIPT_PR}
        or run_finished is None
        or merged_at is None
        or run_finished > merged_at
        or job.get("id") != int(job_id)
        or job.get("run_id") != int(run_id)
        or job.get("name") != "test-and-verify"
        or job.get("head_sha") != receipt["head_sha"]
        or job.get("status") != "completed"
        or job.get("conclusion") != "success"
        or job.get("html_url") != expected_job_url
        or not steps_ok
    ):
        problems.append("R00 live CI is not the successful exact-head PR #7 run/job")


def _normalize_live_pr7_review(item: Any) -> dict[str, str]:
    if not isinstance(item, dict):
        raise ValueError("review is not an object")
    review_id = _decimal_graphql_id(item.get("id"))
    reviewer_record = item.get("user")
    raw_reviewer = (
        reviewer_record.get("login")
        if isinstance(reviewer_record, dict)
        else None
    )
    reviewer = _normalized_github_login(raw_reviewer)
    reviewer_id = (
        _decimal_graphql_id(reviewer_record.get("id"))
        if isinstance(reviewer_record, dict)
        else None
    )
    submitted_at = item.get("submitted_at")
    commit_id = item.get("commit_id")
    body = item.get("body")
    state = item.get("state")
    expected_url = (
        "https://github.com/TriadAgentic/TriadOrigin/pull/7"
        f"#pullrequestreview-{review_id or ''}"
    )
    if (
        review_id is None
        or reviewer is None
        or not isinstance(raw_reviewer, str)
        or not raw_reviewer
        or reviewer_id is None
        or not isinstance(commit_id, str)
        or re.fullmatch(r"[0-9a-f]{40}", commit_id) is None
        or not isinstance(body, str)
        or state not in {"APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED"}
        or _parse_github_time(submitted_at) is None
        or item.get("html_url") != expected_url
    ):
        raise ValueError("review identity/state is malformed")
    body.encode("utf-8")
    return {
        "body": body,
        "commit_id": commit_id,
        "raw_reviewer": raw_reviewer,
        "review_id": review_id,
        "reviewer": reviewer,
        "reviewer_id": reviewer_id,
        "state": state,
        "submitted_at": submitted_at,
        "url": expected_url,
    }


def _fetch_live_pr7_reviews(github_get_json: GitHubJsonGetter) -> list[dict[str, str]]:
    reviews: list[dict[str, str]] = []
    seen: set[str] = set()
    for page in range(1, 12):
        payload = github_get_json(
            f"/repos/TriadAgentic/TriadOrigin/pulls/7/reviews?per_page=100&page={page}"
        )
        if not isinstance(payload, list):
            raise ValueError("review page is not a list")
        if not payload:
            break
        if len(payload) > 100:
            raise ValueError("review page exceeds the controlled size")
        for item in payload:
            normalized = _normalize_live_pr7_review(item)
            if normalized["review_id"] in seen:
                raise ValueError("duplicate review identity")
            seen.add(normalized["review_id"])
            reviews.append(normalized)
    else:
        raise ValueError("review pagination exceeds the controlled page cap")
    reviews.sort(
        key=lambda item: (
            _parse_github_time(item["submitted_at"]),
            int(item["review_id"]),
        )
    )
    return reviews


def _review_history_matches_baseline(
    reviews: list[dict[str, str]],
    *,
    selected_review_id: str | None = None,
) -> bool:
    baseline = _r00_pr7_preacceptance_review_baseline()
    if reviews[:len(baseline)] != baseline:
        return False
    remainder = reviews[len(baseline):]
    if selected_review_id is None:
        return not remainder
    return len(remainder) == 1 and remainder[0].get("review_id") == selected_review_id


def _normalize_live_pr7_issue_comment(item: Any) -> dict[str, str]:
    if not isinstance(item, dict):
        raise ValueError("issue comment is not an object")
    comment_id = _decimal_graphql_id(item.get("id"))
    node_id = item.get("node_id")
    author_record = item.get("user")
    raw_author = author_record.get("login") if isinstance(author_record, dict) else None
    author = _normalized_github_login(
        raw_author
    )
    author_id = (
        _decimal_graphql_id(author_record.get("id"))
        if isinstance(author_record, dict)
        else None
    )
    body = item.get("body")
    created_at = item.get("created_at")
    updated_at = item.get("updated_at")
    expected_url = (
        "https://github.com/TriadAgentic/TriadOrigin/pull/7"
        f"#issuecomment-{comment_id or ''}"
    )
    if (
        comment_id is None
        or not isinstance(node_id, str)
        or not node_id
        or author is None
        or not isinstance(raw_author, str)
        or not raw_author
        or author_id is None
        or not isinstance(body, str)
        or _parse_github_time(created_at) is None
        or _parse_github_time(updated_at) is None
        or item.get("html_url") != expected_url
    ):
        raise ValueError("issue comment identity/content is malformed")
    body.encode("utf-8")
    return {
        "author": author,
        "author_id": author_id,
        "body": body,
        "created_at": created_at,
        "id": comment_id,
        "node_id": node_id,
        "raw_author": raw_author,
        "updated_at": updated_at,
        "url": expected_url,
    }


def _fetch_live_pr7_issue_comments(
    github_get_json: GitHubJsonGetter,
) -> list[dict[str, str]]:
    comments: list[dict[str, str]] = []
    seen: set[str] = set()
    for page in range(1, 12):
        payload = github_get_json(
            f"/repos/TriadAgentic/TriadOrigin/issues/7/comments?per_page=100&page={page}"
        )
        if not isinstance(payload, list):
            raise ValueError("issue-comment page is not a list")
        if not payload:
            break
        if len(payload) > 100:
            raise ValueError("issue-comment page exceeds the controlled size")
        for item in payload:
            normalized = _normalize_live_pr7_issue_comment(item)
            if normalized["id"] in seen:
                raise ValueError("duplicate issue-comment identity")
            seen.add(normalized["id"])
            comments.append(normalized)
    else:
        raise ValueError("issue-comment pagination exceeds the controlled page cap")
    comments.sort(
        key=lambda item: (_parse_github_time(item["created_at"]), int(item["id"]))
    )
    return comments


def _normalize_live_pr7_reaction(item: Any) -> dict[str, str]:
    if not isinstance(item, dict):
        raise ValueError("PR reaction is not an object")
    reaction_id = _decimal_graphql_id(item.get("id"))
    node_id = item.get("node_id")
    actor_record = item.get("user")
    raw_actor = actor_record.get("login") if isinstance(actor_record, dict) else None
    actor = _normalized_github_login(
        raw_actor
    )
    actor_id = (
        _decimal_graphql_id(actor_record.get("id"))
        if isinstance(actor_record, dict)
        else None
    )
    content = item.get("content")
    created_at = item.get("created_at")
    if (
        reaction_id is None
        or not isinstance(node_id, str)
        or not node_id
        or actor is None
        or not isinstance(raw_actor, str)
        or not raw_actor
        or actor_id is None
        or content not in {"+1", "-1", "laugh", "confused", "heart", "hooray", "rocket", "eyes"}
        or _parse_github_time(created_at) is None
    ):
        raise ValueError("PR reaction identity/content is malformed")
    return {
        "actor": actor,
        "actor_id": actor_id,
        "content": content,
        "created_at": created_at,
        "id": reaction_id,
        "node_id": node_id,
        "raw_actor": raw_actor,
    }


def _fetch_live_pr7_reactions(
    github_get_json: GitHubJsonGetter,
) -> list[dict[str, str]]:
    reactions: list[dict[str, str]] = []
    seen: set[str] = set()
    for page in range(1, 12):
        payload = github_get_json(
            f"/repos/TriadAgentic/TriadOrigin/issues/7/reactions?per_page=100&page={page}"
        )
        if not isinstance(payload, list):
            raise ValueError("PR-reaction page is not a list")
        if not payload:
            break
        if len(payload) > 100:
            raise ValueError("PR-reaction page exceeds the controlled size")
        for item in payload:
            normalized = _normalize_live_pr7_reaction(item)
            if normalized["id"] in seen:
                raise ValueError("duplicate PR-reaction identity")
            seen.add(normalized["id"])
            reactions.append(normalized)
    else:
        raise ValueError("PR-reaction pagination exceeds the controlled page cap")
    reactions.sort(
        key=lambda item: (_parse_github_time(item["created_at"]), int(item["id"]))
    )
    return reactions


def _normalize_live_pr7_pull(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError("pull request is not an object")
    user = item.get("user")
    raw_author = user.get("login") if isinstance(user, dict) else None
    author_id = (
        _decimal_graphql_id(user.get("id")) if isinstance(user, dict) else None
    )
    head = item.get("head")
    base = item.get("base")
    merged_at = item.get("merged_at")
    updated_at = item.get("updated_at")
    expected_url = "https://github.com/TriadAgentic/TriadOrigin/pull/7"
    if (
        item.get("number") != R00_RECEIPT_PR
        or item.get("html_url") != expected_url
        or _normalized_github_login(raw_author) != R00_PR_AUTHOR
        or raw_author != R00_PR_AUTHOR
        or author_id != R00_PR_AUTHOR_ID
        or not isinstance(head, dict)
        or re.fullmatch(r"[0-9a-f]{40}", str(head.get("sha"))) is None
        or not isinstance(base, dict)
        or re.fullmatch(r"[0-9a-f]{40}", str(base.get("sha"))) is None
        or item.get("merged") is not True
        or re.fullmatch(r"[0-9a-f]{40}", str(item.get("merge_commit_sha"))) is None
        or _parse_github_time(merged_at) is None
        or _parse_github_time(updated_at) is None
    ):
        raise ValueError("pull request identity/state is malformed")
    return {
        "author": R00_PR_AUTHOR,
        "author_id": author_id,
        "base_sha": base["sha"],
        "head_sha": head["sha"],
        "merge_commit_sha": item["merge_commit_sha"],
        "merged": True,
        "merged_at": merged_at,
        "number": R00_RECEIPT_PR,
        "updated_at": updated_at,
        "url": expected_url,
    }


def _normalize_live_pr7_timeline_event(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError("timeline event is not an object")
    event = item.get("event")
    if not isinstance(event, str) or re.fullmatch(r"[a-z_-]+", event) is None:
        raise ValueError("timeline event type is malformed")
    object_id = _decimal_graphql_id(item.get("id")) or ""
    node_id = item.get("node_id")
    node_id = node_id if isinstance(node_id, str) else ""
    commit_value = item.get("sha") if event == "committed" else item.get("commit_id")
    commit_sha = (
        commit_value
        if isinstance(commit_value, str)
        and re.fullmatch(r"[0-9a-f]{40}", commit_value) is not None
        else ""
    )
    if event == "committed" and not commit_sha:
        raise ValueError("committed timeline event lacks a commit SHA")
    created_at = (
        item.get("submitted_at", "")
        if event == "reviewed"
        else item.get("created_at", "")
    )
    if event != "committed" and _parse_github_time(created_at) is None:
        raise ValueError("timeline event timestamp is malformed")
    if event == "committed" and created_at not in {None, ""}:
        if _parse_github_time(created_at) is None:
            raise ValueError("committed timeline timestamp is malformed")
    raw_sha256 = hashlib.sha256(canonical_json(item)).hexdigest()
    identity_value = object_id or commit_sha or node_id or raw_sha256
    return {
        "commit_sha": commit_sha,
        "created_at": created_at or "",
        "event": event,
        "identity": f"{event}:{identity_value}",
        "node_id": node_id,
        "object_id": object_id,
        "raw_sha256": raw_sha256,
    }


def _fetch_live_pr7_timeline(
    github_get_json: GitHubJsonGetter,
) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    identities: set[str] = set()
    for page in range(1, 12):
        payload = github_get_json(
            f"/repos/TriadAgentic/TriadOrigin/issues/7/timeline?per_page=100&page={page}"
        )
        if not isinstance(payload, list):
            raise ValueError("timeline page is not a list")
        if not payload:
            break
        if len(payload) > 100:
            raise ValueError("timeline page exceeds the controlled size")
        for item in payload:
            normalized = _normalize_live_pr7_timeline_event(item)
            if normalized["identity"] in identities:
                raise ValueError("duplicate timeline-event identity")
            identities.add(normalized["identity"])
            normalized["position"] = len(timeline)
            timeline.append(normalized)
    else:
        raise ValueError("timeline pagination exceeds the controlled page cap")
    return timeline


def _fetch_live_comment_reactions(
    github_get_json: GitHubJsonGetter,
    comment_id: str,
) -> list[dict[str, str]]:
    reactions: list[dict[str, str]] = []
    seen: set[str] = set()
    for page in range(1, 12):
        payload = github_get_json(
            f"/repos/TriadAgentic/TriadOrigin/issues/comments/{comment_id}"
            f"/reactions?per_page=100&page={page}"
        )
        if not isinstance(payload, list):
            raise ValueError("comment-reaction page is not a list")
        if not payload:
            break
        if len(payload) > 100:
            raise ValueError("comment-reaction page exceeds the controlled size")
        for item in payload:
            normalized = _normalize_live_pr7_reaction(item)
            if normalized["id"] in seen:
                raise ValueError("duplicate comment-reaction identity")
            seen.add(normalized["id"])
            reactions.append(normalized)
    else:
        raise ValueError("comment-reaction pagination exceeds the controlled page cap")
    reactions.sort(
        key=lambda item: (_parse_github_time(item["created_at"]), int(item["id"]))
    )
    return reactions


def _validate_live_r00_review(
    final: dict[str, Any],
    persisted_review: dict[str, Any],
    *,
    persisted_comments: Any,
    persisted_reactions: Any,
    persisted_reviews: Any,
    persisted_pull: Any,
    persisted_threads: Any,
    persisted_timeline: Any,
    allowed_postmerge_review_ids: set[str],
    head_sha: str,
    base_sha: str,
    merge_sha: str,
    tree_sha: str,
    github_get_json: GitHubJsonGetter | None,
    problems: list[str],
) -> None:
    """Re-read corrective PR #7 and its independent review at receipt-sealing time."""
    if github_get_json is None:
        problems.append("R00 sealing requires live GitHub REST revalidation")
        return
    review_id = final.get("review_id")
    if not isinstance(review_id, str) or not review_id.isdigit():
        problems.append("R00 live review revalidation lacks a numeric review ID")
        return
    try:
        pull_raw = github_get_json("/repos/TriadAgentic/TriadOrigin/pulls/7")
        pull_snapshots = [_normalize_live_pr7_pull(pull_raw)]
        review = github_get_json(
            f"/repos/TriadAgentic/TriadOrigin/pulls/7/reviews/{review_id}"
        )
        head_commit = github_get_json(
            f"/repos/TriadAgentic/TriadOrigin/git/commits/{head_sha}"
        )
        final_comments = github_get_json(
            f"/repos/TriadAgentic/TriadOrigin/pulls/7/reviews/{review_id}/comments?per_page=100"
        )
        live_review_snapshots = [
            _fetch_live_pr7_reviews(github_get_json),
            _fetch_live_pr7_reviews(github_get_json),
        ]
        live_comment_snapshots = [
            _fetch_live_pr7_issue_comments(github_get_json),
            _fetch_live_pr7_issue_comments(github_get_json),
        ]
        live_reaction_snapshots = [
            _fetch_live_pr7_reactions(github_get_json),
            _fetch_live_pr7_reactions(github_get_json),
        ]
        live_timeline_snapshots = [
            _fetch_live_pr7_timeline(github_get_json),
            _fetch_live_pr7_timeline(github_get_json),
        ]
        pull_snapshots.append(
            _normalize_live_pr7_pull(
                github_get_json("/repos/TriadAgentic/TriadOrigin/pulls/7")
            )
        )
    except Exception as exc:  # Fail closed on network, API, and provider errors.
        problems.append(f"R00 live GitHub REST revalidation failed: {type(exc).__name__}")
        return
    if (
        not isinstance(pull_raw, dict)
        or not isinstance(review, dict)
        or not isinstance(head_commit, dict)
        or not isinstance(final_comments, list)
        or not all(isinstance(item, list) for item in live_review_snapshots)
        or not all(isinstance(item, list) for item in live_comment_snapshots)
        or not all(isinstance(item, list) for item in live_reaction_snapshots)
        or not all(isinstance(item, list) for item in live_timeline_snapshots)
    ):
        problems.append("R00 live GitHub review response has the wrong shape")
        return
    pull = pull_snapshots[0]
    review_user = review.get("user")
    raw_reviewer = (
        review_user.get("login") if isinstance(review_user, dict) else None
    )
    reviewer = _normalized_github_login(raw_reviewer)
    reviewer_id = (
        _decimal_graphql_id(review_user.get("id"))
        if isinstance(review_user, dict)
        else None
    )
    merged_at = _parse_github_time(pull.get("merged_at"))
    submitted_at = _parse_github_time(review.get("submitted_at"))
    expected_pr_url = "https://github.com/TriadAgentic/TriadOrigin/pull/7"
    expected_review_url = f"{expected_pr_url}#pullrequestreview-{review_id}"
    body = review.get("body")
    expected_body = _expected_codex_review_body(head_sha)
    review_snapshots_ok = live_review_snapshots[0] == live_review_snapshots[1]
    live_reviews = live_review_snapshots[0]
    live_comments = live_comment_snapshots[0]
    live_reactions = live_reaction_snapshots[0]
    live_timeline = live_timeline_snapshots[0]
    selected_review = next(
        (item for item in live_reviews if item["review_id"] == review_id),
        None,
    )
    inventory_ok = (
        isinstance(persisted_reviews, list)
        and persisted_reviews == live_reviews
        and isinstance(persisted_comments, list)
        and persisted_comments == live_comments
        and isinstance(persisted_reactions, list)
        and persisted_reactions == live_reactions
        and isinstance(persisted_pull, dict)
        and persisted_pull == pull
        and isinstance(persisted_timeline, list)
        and persisted_timeline == live_timeline
        and pull_snapshots[0] == pull_snapshots[1]
        and live_review_snapshots[0] == live_review_snapshots[1]
        and live_comment_snapshots[0] == live_comment_snapshots[1]
        and live_reaction_snapshots[0] == live_reaction_snapshots[1]
        and live_timeline_snapshots[0] == live_timeline_snapshots[1]
    )
    premerge_reviews = [
        item for item in live_reviews
        if merged_at is not None
        and _parse_github_time(item["submitted_at"]) <= merged_at
    ]
    review_order_ok = (
        selected_review is not None
        and all(item["state"] != "CHANGES_REQUESTED" for item in live_reviews)
        and _review_history_matches_baseline(
            premerge_reviews, selected_review_id=review_id
        )
    )
    if review_order_ok and submitted_at is not None and merged_at is not None:
        selected_key = (submitted_at, int(review_id))
        for item in live_reviews:
            item_time = _parse_github_time(item["submitted_at"])
            if item_time is None:
                review_order_ok = False
                break
            if item_time <= merged_at:
                if (item_time, int(item["review_id"])) > selected_key:
                    review_order_ok = False
                    break
            elif not (
                item["review_id"] in allowed_postmerge_review_ids
                and item["reviewer"] == R00_PR_AUTHOR
                and item["state"] == "COMMENTED"
                and item["body"] == ""
            ):
                review_order_ok = False
                break
    comment_baseline = _r00_pr7_preacceptance_comment_baseline()
    comments_ok = (
        len(live_comments) == len(comment_baseline)
        and [
            {key: item[key] for key in baseline_item}
            for item, baseline_item in zip(
                live_comments, comment_baseline, strict=True
            )
        ] == comment_baseline
        and all(
            item.get("created_at") == item.get("updated_at")
            for item in live_comments
        )
    )
    connector_reactions = [
        item for item in live_reactions
        if item.get("raw_actor") == "chatgpt-codex-connector[bot]"
        or item.get("actor_id") == R00_REQUIRED_REVIEWER_ID
    ]
    reactions_ok = (
        len(connector_reactions) == 1
        and connector_reactions[0].get("actor") == R00_REQUIRED_REVIEWER
        and connector_reactions[0].get("raw_actor")
        == "chatgpt-codex-connector[bot]"
        and connector_reactions[0].get("actor_id") == R00_REQUIRED_REVIEWER_ID
        and connector_reactions[0].get("content") == "+1"
    )
    selected_timeline = [
        item for item in live_timeline
        if item.get("event") == "reviewed"
        and item.get("object_id") == review_id
        and item.get("commit_sha") == head_sha
    ]
    merge_timeline = [
        item for item in live_timeline
        if item.get("event") == "merged" and item.get("commit_sha") == head_sha
    ]
    head_commits = [
        item for item in live_timeline
        if item.get("event") == "committed" and item.get("commit_sha") == head_sha
    ]
    timeline_ok = (
        len(selected_timeline) == 1
        and len(merge_timeline) == 1
        and bool(head_commits)
        and max(item["position"] for item in head_commits)
        < selected_timeline[0]["position"] < merge_timeline[0]["position"]
        and _parse_github_time(merge_timeline[0].get("created_at")) == merged_at
    )
    if timeline_ok:
        forbidden_head_events = {
            "automatic_base_change_succeeded",
            "base_ref_deleted",
            "base_ref_changed",
            "base_ref_force_pushed",
            "committed",
            "head_ref_deleted",
            "head_ref_force_pushed",
            "head_ref_restored",
        }
        timeline_ok = not any(
            (
                selected_timeline[0]["position"] < item["position"]
                < merge_timeline[0]["position"]
                and item["event"] in forbidden_head_events
            )
            or (
                item["position"] > selected_timeline[0]["position"]
                and item["event"] == "review_dismissed"
            )
            or (
                item["position"] > merge_timeline[0]["position"]
                and item["event"] == "head_ref_deleted"
            )
            for item in live_timeline
        )
    thread_activity_ok = _r00_thread_activity_precedes_acceptance(
        persisted_threads,
        accepted_at=submitted_at,
        merged_at=merged_at,
    )
    if (
        pull.get("number") != R00_RECEIPT_PR
        or pull.get("url") != expected_pr_url
        or pull.get("author") != R00_PR_AUTHOR
        or pull.get("author_id") != R00_PR_AUTHOR_ID
        or pull.get("head_sha") != head_sha
        or pull.get("base_sha") != base_sha
        or base_sha != R00_IMPLEMENTATION_MERGE_SHA
        or pull.get("merged") is not True
        or pull.get("merge_commit_sha") != merge_sha
        or head_commit.get("sha") != head_sha
        or not isinstance(head_commit.get("tree"), dict)
        or head_commit["tree"].get("sha") != tree_sha
        or merged_at is None
        or review.get("id") != int(review_id)
        or reviewer != R00_REQUIRED_REVIEWER
        or raw_reviewer != "chatgpt-codex-connector[bot]"
        or reviewer_id != R00_REQUIRED_REVIEWER_ID
        or reviewer == pull.get("author")
        or final.get("reviewer") != reviewer
        or review.get("commit_id") != head_sha
        or review.get("state") != "COMMENTED"
        or review.get("html_url") != expected_review_url
        or final.get("url") != expected_review_url
        or not isinstance(body, str)
        or body != persisted_review.get("body")
        or body != expected_body
        or final.get("body_sha256") != hashlib.sha256(body.encode("utf-8")).hexdigest()
        or submitted_at is None
        or submitted_at > merged_at
        or final_comments != []
        or selected_review != persisted_review
        or not inventory_ok
        or not review_order_ok
        or not comments_ok
        or not reactions_ok
        or not timeline_ok
        or not thread_activity_ok
        or not review_snapshots_ok
    ):
        problems.append("R00 live GitHub review is not an independent exact-head pre-merge review")


def _r00_thread_activity_precedes_acceptance(
    persisted_threads: Any,
    *,
    accepted_at: datetime | None,
    merged_at: datetime | None,
) -> bool:
    """Reject thread activity at/after acceptance except the sealed merge reply."""
    if (
        not isinstance(persisted_threads, list)
        or accepted_at is None
        or merged_at is None
        or accepted_at >= merged_at
    ):
        return False
    for thread in persisted_threads:
        if not isinstance(thread, dict):
            return False
        root = thread.get("root")
        replies = thread.get("reply_inventory")
        remediation = thread.get("remediation_reply")
        if (
            not isinstance(root, dict)
            or not isinstance(replies, list)
            or not isinstance(remediation, dict)
        ):
            return False
        selected = str(remediation.get("id", ""))
        if not selected.isdigit():
            return False
        root_created = _parse_github_time(root.get("created_at"))
        root_updated = _parse_github_time(root.get("updated_at"))
        if (
            root_created is None
            or root_updated is None
            or root_created >= accepted_at
            or root_updated >= accepted_at
        ):
            return False
        selected_count = 0
        for reply in replies:
            if not isinstance(reply, dict):
                return False
            reply_created = _parse_github_time(reply.get("created_at"))
            reply_updated = _parse_github_time(reply.get("updated_at"))
            reply_id = str(reply.get("id"))
            if reply_created is None or reply_updated is None:
                return False
            if reply_id == selected:
                selected_count += 1
                if reply_created <= merged_at or reply_updated != reply_created:
                    return False
            elif reply_created >= accepted_at or reply_updated >= accepted_at:
                return False
        if selected_count != 1:
            return False
    return True


def _validate_live_r00_reaction(
    final: dict[str, Any],
    *,
    persisted_comments: Any,
    persisted_reactions: Any,
    persisted_reviews: Any,
    persisted_pull: Any,
    persisted_selected_comment_reactions: Any,
    persisted_threads: Any,
    persisted_timeline: Any,
    allowed_postmerge_review_ids: set[str],
    head_sha: str,
    base_sha: str,
    merge_sha: str,
    tree_sha: str,
    ci_run_id: str,
    ci_job_id: str,
    github_get_json: GitHubJsonGetter | None,
    problems: list[str],
) -> None:
    """Authenticate a full-head trigger and exact Codex clean-comment result.

    GitHub retains one reaction of a given type per actor and PR.  The connector's
    PR-root ``+1`` is therefore authenticated corroborating state, not the
    head-binding event.  The unchanged clean comment, full-SHA trigger, and
    no-head-mutation timeline provide that binding.
    """
    if github_get_json is None:
        problems.append("R00 sealing requires live GitHub REST revalidation")
        return
    request_id = final.get("request_comment_id")
    clean_id = final.get("clean_comment_id")
    reaction_id = final.get("reaction_id")
    if any(not isinstance(value, str) or not value.isdigit() for value in (
        request_id, clean_id, reaction_id, ci_run_id, ci_job_id
    )):
        problems.append("R00 clean-reaction evidence lacks decimal live identities")
        return
    try:
        pull_snapshots = [
            _normalize_live_pr7_pull(
                github_get_json("/repos/TriadAgentic/TriadOrigin/pulls/7")
            )
        ]
        head_commit = github_get_json(
            f"/repos/TriadAgentic/TriadOrigin/git/commits/{head_sha}"
        )
        run = github_get_json(
            f"/repos/TriadAgentic/TriadOrigin/actions/runs/{ci_run_id}"
        )
        job = github_get_json(
            f"/repos/TriadAgentic/TriadOrigin/actions/jobs/{ci_job_id}"
        )
        live_review_snapshots = [
            _fetch_live_pr7_reviews(github_get_json),
            _fetch_live_pr7_reviews(github_get_json),
        ]
        live_comment_snapshots = [
            _fetch_live_pr7_issue_comments(github_get_json),
            _fetch_live_pr7_issue_comments(github_get_json),
        ]
        live_reaction_snapshots = [
            _fetch_live_pr7_reactions(github_get_json),
            _fetch_live_pr7_reactions(github_get_json),
        ]
        live_timeline_snapshots = [
            _fetch_live_pr7_timeline(github_get_json),
            _fetch_live_pr7_timeline(github_get_json),
        ]
        selected_comment_reaction_snapshots = {
            "trigger": [
                _fetch_live_comment_reactions(github_get_json, request_id),
                _fetch_live_comment_reactions(github_get_json, request_id),
            ],
            "clean_response": [
                _fetch_live_comment_reactions(github_get_json, clean_id),
                _fetch_live_comment_reactions(github_get_json, clean_id),
            ],
        }
        pull_snapshots.append(
            _normalize_live_pr7_pull(
                github_get_json("/repos/TriadAgentic/TriadOrigin/pulls/7")
            )
        )
    except Exception as exc:  # Fail closed on network, API, and provider errors.
        problems.append(f"R00 live GitHub clean-reaction revalidation failed: {type(exc).__name__}")
        return
    if (
        not isinstance(head_commit, dict)
        or not isinstance(run, dict)
        or not isinstance(job, dict)
        or not all(isinstance(item, list) for item in live_review_snapshots)
        or not all(isinstance(item, list) for item in live_comment_snapshots)
        or not all(isinstance(item, list) for item in live_reaction_snapshots)
        or not all(isinstance(item, list) for item in live_timeline_snapshots)
    ):
        problems.append("R00 live GitHub clean-reaction response has the wrong shape")
        return

    expected_pr_url = "https://github.com/TriadAgentic/TriadOrigin/pull/7"
    pull = pull_snapshots[0]
    merged_at = _parse_github_time(pull.get("merged_at"))
    run_completed_at = _parse_github_time(run.get("updated_at"))
    reviews = live_review_snapshots[0]
    comments = live_comment_snapshots[0]
    reactions = live_reaction_snapshots[0]
    timeline = live_timeline_snapshots[0]
    request = next((item for item in comments if item["id"] == request_id), None)
    clean = next((item for item in comments if item["id"] == clean_id), None)
    reaction = next((item for item in reactions if item["id"] == reaction_id), None)
    request_at = _parse_github_time(request.get("created_at")) if request else None
    clean_at = _parse_github_time(clean.get("created_at")) if clean else None
    reaction_at = _parse_github_time(reaction.get("created_at")) if reaction else None
    expected_request = _expected_codex_review_request_body(
        head_sha, ci_run_id, ci_job_id
    )
    expected_clean = _expected_codex_clean_comment_body(head_sha)
    actual_selected_comment_reactions = {
        name: snapshots[0]
        for name, snapshots in selected_comment_reaction_snapshots.items()
    }
    inventory_ok = (
        isinstance(persisted_reviews, list)
        and persisted_reviews == reviews
        and isinstance(persisted_comments, list)
        and persisted_comments == comments
        and isinstance(persisted_reactions, list)
        and persisted_reactions == reactions
        and isinstance(persisted_pull, dict)
        and persisted_pull == pull
        and isinstance(persisted_timeline, list)
        and persisted_timeline == timeline
        and isinstance(persisted_selected_comment_reactions, dict)
        and persisted_selected_comment_reactions == actual_selected_comment_reactions
        and pull_snapshots[0] == pull_snapshots[1]
        and live_review_snapshots[0] == live_review_snapshots[1]
        and live_comment_snapshots[0] == live_comment_snapshots[1]
        and live_reaction_snapshots[0] == live_reaction_snapshots[1]
        and live_timeline_snapshots[0] == live_timeline_snapshots[1]
        and all(
            snapshots[0] == snapshots[1] == []
            for snapshots in selected_comment_reaction_snapshots.values()
        )
    )
    premerge_reviews = [
        item for item in reviews
        if merged_at is not None
        and _parse_github_time(item["submitted_at"]) <= merged_at
    ]
    review_order_ok = (
        all(item["state"] != "CHANGES_REQUESTED" for item in reviews)
        and _review_history_matches_baseline(premerge_reviews)
    )
    if review_order_ok and request_at is not None and merged_at is not None:
        for item in reviews:
            item_time = _parse_github_time(item["submitted_at"])
            if item_time is None:
                review_order_ok = False
                break
            if item_time <= merged_at:
                if item_time >= request_at:
                    review_order_ok = False
                    break
            elif not (
                item["review_id"] in allowed_postmerge_review_ids
                and item["reviewer"] == R00_PR_AUTHOR
                and item["state"] == "COMMENTED"
                and item["body"] == ""
            ):
                review_order_ok = False
                break
    comment_baseline = _r00_pr7_preacceptance_comment_baseline()
    comments_final = (
        len(comments) == len(comment_baseline) + 2
        and [
            {key: item[key] for key in baseline_item}
            for item, baseline_item in zip(
                comments[:len(comment_baseline)], comment_baseline, strict=True
            )
        ] == comment_baseline
        and all(
            item.get("created_at") == item.get("updated_at")
            for item in comments
        )
        and comments[-2].get("id") == request_id
        and comments[-1].get("id") == clean_id
    )
    request_timeline = [
        item for item in timeline
        if item.get("event") == "commented" and item.get("object_id") == request_id
    ]
    clean_timeline = [
        item for item in timeline
        if item.get("event") == "commented" and item.get("object_id") == clean_id
    ]
    merge_timeline = [
        item for item in timeline
        if item.get("event") == "merged" and item.get("commit_sha") == head_sha
    ]
    head_commits = [
        item for item in timeline
        if item.get("event") == "committed" and item.get("commit_sha") == head_sha
    ]
    timeline_ok = (
        len(request_timeline) == 1
        and len(clean_timeline) == 1
        and len(merge_timeline) == 1
        and bool(head_commits)
        and request_timeline[0]["position"] < clean_timeline[0]["position"]
        < merge_timeline[0]["position"]
        and max(item["position"] for item in head_commits)
        < request_timeline[0]["position"]
        and _parse_github_time(merge_timeline[0].get("created_at")) == merged_at
    )
    if timeline_ok:
        forbidden_head_events = {
            "automatic_base_change_succeeded",
            "base_ref_deleted",
            "base_ref_changed",
            "base_ref_force_pushed",
            "committed",
            "head_ref_deleted",
            "head_ref_force_pushed",
            "head_ref_restored",
        }
        timeline_ok = not any(
            (
                request_timeline[0]["position"] < item["position"]
                < merge_timeline[0]["position"]
                and item["event"] in forbidden_head_events
            )
            or (
                item["position"] > request_timeline[0]["position"]
                and item["event"] == "review_dismissed"
            )
            or (
                item["position"] > merge_timeline[0]["position"]
                and item["event"] == "head_ref_deleted"
            )
            for item in timeline
        )

    thread_activity_ok = _r00_thread_activity_precedes_acceptance(
        persisted_threads,
        accepted_at=clean_at,
        merged_at=merged_at,
    )
    connector_reactions = [
        item for item in reactions
        if item.get("raw_actor") == "chatgpt-codex-connector[bot]"
        or item.get("actor_id") == R00_REQUIRED_REVIEWER_ID
    ]
    if (
        pull.get("number") != R00_RECEIPT_PR
        or pull.get("url") != expected_pr_url
        or pull.get("author") != R00_PR_AUTHOR
        or pull.get("author_id") != R00_PR_AUTHOR_ID
        or pull.get("head_sha") != head_sha
        or pull.get("base_sha") != base_sha
        or base_sha != R00_IMPLEMENTATION_MERGE_SHA
        or pull.get("merged") is not True
        or pull.get("merge_commit_sha") != merge_sha
        or head_commit.get("sha") != head_sha
        or not isinstance(head_commit.get("tree"), dict)
        or head_commit["tree"].get("sha") != tree_sha
        or run.get("id") != int(ci_run_id)
        or run.get("head_sha") != head_sha
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
        or job.get("id") != int(ci_job_id)
        or job.get("run_id") != int(ci_run_id)
        or job.get("head_sha") != head_sha
        or job.get("status") != "completed"
        or job.get("conclusion") != "success"
        or merged_at is None
        or run_completed_at is None
        or request is None
        or clean is None
        or reaction is None
        or request.get("author") != R00_PR_AUTHOR
        or request.get("raw_author") != R00_PR_AUTHOR
        or request.get("author_id") != R00_PR_AUTHOR_ID
        or request.get("body") != expected_request
        or request.get("created_at") != request.get("updated_at")
        or clean.get("author") != R00_REQUIRED_REVIEWER
        or clean.get("raw_author") != "chatgpt-codex-connector[bot]"
        or clean.get("author_id") != R00_REQUIRED_REVIEWER_ID
        or clean.get("body") != expected_clean
        or clean.get("created_at") != clean.get("updated_at")
        or reaction.get("actor") != R00_REQUIRED_REVIEWER
        or reaction.get("raw_actor") != "chatgpt-codex-connector[bot]"
        or reaction.get("actor_id") != R00_REQUIRED_REVIEWER_ID
        or reaction.get("content") != "+1"
        or connector_reactions != [reaction]
        or request_at is None
        or clean_at is None
        or reaction_at is None
        or not (run_completed_at < request_at < clean_at < merged_at)
        or reaction_at > clean_at
        or not comments_final
        or not inventory_ok
        or not review_order_ok
        or not timeline_ok
        or not thread_activity_ok
        or final.get("head_sha") != head_sha
        or final.get("ci_run_id") != ci_run_id
        or final.get("ci_job_id") != ci_job_id
        or final.get("accepted_at") != clean.get("created_at")
        or final.get("actor") != R00_REQUIRED_REVIEWER
        or final.get("actor_id") != R00_REQUIRED_REVIEWER_ID
        or final.get("content") != "+1"
        or final.get("request_comment_id") != request_id
        or final.get("request_url") != request.get("url")
        or final.get("request_body_sha256")
        != hashlib.sha256(expected_request.encode("utf-8")).hexdigest()
        or final.get("clean_comment_id") != clean_id
        or final.get("clean_comment_url") != clean.get("url")
        or final.get("clean_comment_body_sha256")
        != hashlib.sha256(expected_clean.encode("utf-8")).hexdigest()
        or final.get("reaction_id") != reaction_id
        or final.get("reaction_node_id") != reaction.get("node_id")
    ):
        problems.append(
            "R00 live GitHub clean-comment/reaction is not an exact-head pre-merge acceptance"
        )


def _github_get_json_from_token(token: str) -> GitHubJsonGetter:
    if not token or token.isspace():
        raise ReceiptValidationError("R00 sealing requires GITHUB_TOKEN")

    def get_json(path: str) -> Any:
        if not path.startswith("/repos/TriadAgentic/TriadOrigin/"):
            raise ReceiptValidationError("refusing an uncontrolled GitHub REST path")
        request = urllib.request.Request(
            "https://api.github.com" + path,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "triad-origin-r00-sealer",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read(1_048_577)
        except (OSError, urllib.error.HTTPError, urllib.error.URLError) as exc:
            raise ReceiptValidationError(
                f"GitHub REST request failed: {type(exc).__name__}"
            ) from exc
        if len(raw) > 1_048_576:
            raise ReceiptValidationError("GitHub REST response exceeds the controlled limit")
        try:
            value = json.loads(raw)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ReceiptValidationError("GitHub REST response is not JSON") from exc
        if not isinstance(value, (dict, list)):
            raise ReceiptValidationError("GitHub REST response root is not an object or array")
        return value

    return get_json


def _github_get_review_threads_from_token(token: str) -> GitHubReviewThreadsGetter:
    if not token or token.isspace():
        raise ReceiptValidationError("R00 sealing requires GITHUB_TOKEN")

    def get_review_threads(pr_number: int) -> Any:
        if isinstance(pr_number, bool) or pr_number not in R00_REVIEW_PRS:
            raise ReceiptValidationError("refusing an uncontrolled GitHub GraphQL PR")
        request_body = json.dumps(
            {
                "query": R00_REVIEW_THREADS_QUERY,
                "variables": {
                    "number": pr_number,
                    "owner": "TriadAgentic",
                    "repo": "TriadOrigin",
                },
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        request = urllib.request.Request(
            "https://api.github.com/graphql",
            data=request_body,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "triad-origin-r00-sealer",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read(1_048_577)
        except (OSError, urllib.error.HTTPError, urllib.error.URLError) as exc:
            raise ReceiptValidationError(
                f"GitHub GraphQL request failed: {type(exc).__name__}"
            ) from exc
        if len(raw) > 1_048_576:
            raise ReceiptValidationError("GitHub GraphQL response exceeds the controlled limit")
        try:
            value = json.loads(raw)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ReceiptValidationError("GitHub GraphQL response is not JSON") from exc
        if (
            not isinstance(value, dict)
            or value.get("errors")
            or not isinstance(value.get("data"), dict)
        ):
            raise ReceiptValidationError("GitHub GraphQL response is partial or has errors")
        return value

    return get_review_threads


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


def _git_output(root: pathlib.Path, *arguments: str) -> bytes:
    env = os.environ.copy()
    for name in (
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_COMMON_DIR",
        "GIT_DIR",
        "GIT_INDEX_FILE",
        "GIT_NAMESPACE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_REPLACE_REF_BASE",
        "GIT_WORK_TREE",
    ):
        env.pop(name, None)
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    result = subprocess.run(
        ["git", "-C", os.fspath(root), *arguments],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(detail or f"git {' '.join(arguments)} failed")
    return result.stdout


def _git_commit_identity(root: pathlib.Path, commit_sha: str) -> tuple[str, list[str]]:
    raw = _git_output(root, "cat-file", "commit", commit_sha)
    header = raw.split(b"\n\n", 1)[0]
    trees: list[str] = []
    parents: list[str] = []
    for line in header.splitlines():
        if line.startswith(b"tree "):
            trees.append(line.removeprefix(b"tree ").decode("ascii"))
        elif line.startswith(b"parent "):
            parents.append(line.removeprefix(b"parent ").decode("ascii"))
    if (
        len(trees) != 1
        or re.fullmatch(r"[0-9a-f]{40}", trees[0]) is None
        or any(re.fullmatch(r"[0-9a-f]{40}", parent) is None for parent in parents)
    ):
        raise ValueError("commit object has malformed tree/parent headers")
    return trees[0], parents


def _validate_git_binding(
    receipt: dict[str, Any],
    git_root: pathlib.Path,
    receipt_path: pathlib.Path,
    problems: list[str],
) -> None:
    """Authenticate the final R00 seal against immutable local Git objects."""
    try:
        root = git_root.resolve(strict=True)
        top = pathlib.Path(
            _git_output(root, "rev-parse", "--show-toplevel").decode("utf-8").strip()
        ).resolve(strict=True)
        if top != root:
            raise ValueError("git_root is not the repository top level")
        resolved_receipt = receipt_path.resolve(strict=True)
        relative_receipt = resolved_receipt.relative_to(root).as_posix()
        if (
            receipt.get("milestone_id") == "R00"
            and relative_receipt != "evidence/receipts/R00.json"
        ):
            raise ValueError("R00 receipt is not at its canonical repository path")
        receipt_bytes = resolved_receipt.read_bytes()
        if receipt_bytes != canonical_json(receipt):
            raise ValueError("receipt bytes are not canonical or do not match the validated object")

        merge_sha = receipt["merge_sha"]
        merge_tree, merge_parents = _git_commit_identity(root, merge_sha)
        if merge_tree != receipt["merge_control"]["tree_sha"]:
            raise ValueError("merge commit tree does not equal merge_control.tree_sha")
        if merge_parents != [receipt["base_sha"]]:
            raise ValueError("merge commit does not have the receipt base as its sole parent")
        if _git_output(root, "cat-file", "-t", merge_tree) != b"tree\n":
            raise ValueError("merge commit tree object is absent")

        head_sha = _git_output(root, "rev-parse", "--verify", "HEAD^{commit}").decode(
            "ascii"
        ).strip()
        branch = _git_output(root, "symbolic-ref", "--short", "HEAD").decode(
            "utf-8"
        ).strip()
        branch_head = _git_output(
            root,
            "rev-parse",
            "--verify",
            "refs/heads/evidence/r00-receipt^{commit}",
        ).decode("ascii").strip()
        if branch != "evidence/r00-receipt" or branch_head != head_sha:
            raise ValueError("receipt is not sealed on the canonical evidence branch ref")
        if _git_output(
            root, "status", "--porcelain=v1", "--untracked-files=all", "-z"
        ):
            raise ValueError("receipt worktree/index is not clean")
        _, receipt_parents = _git_commit_identity(root, head_sha)
        if receipt_parents != [merge_sha]:
            raise ValueError("current evidence commit is not a direct child of the merge commit")

        changed = _git_output(
            root,
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            "-z",
            head_sha,
        ).split(b"\0")
        changed_paths = [name.decode("utf-8") for name in changed if name]
        if not changed_paths or any(
            not pathlib.PurePosixPath(name).parts
            or pathlib.PurePosixPath(name).parts[0] != "evidence"
            for name in changed_paths
        ):
            raise ValueError("evidence commit changes a path outside evidence/")

        committed_paths = {relative_receipt}
        committed_paths.update(item["path"] for item in receipt["evidence_files"])
        if set(changed_paths) != committed_paths:
            raise ValueError("evidence commit path set does not exactly equal receipt preimages")
        for relative in sorted(committed_paths):
            path = pathlib.PurePosixPath(relative)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("receipt names an unsafe committed evidence path")
            disk = (root / pathlib.Path(*path.parts)).read_bytes()
            committed = _git_output(root, "cat-file", "blob", f"{head_sha}:{relative}")
            if committed != disk:
                raise ValueError(f"evidence commit does not contain exact bytes for {relative}")
    except (OSError, UnicodeError, KeyError, TypeError, ValueError) as exc:
        problems.append(f"R00 Git-object lineage is not authenticated: {exc}")


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
        github_get_json = None
        github_get_review_threads = None
        if receipt.get("milestone_id") == "R00":
            token = os.environ.get("GITHUB_TOKEN", "")
            github_get_json = _github_get_json_from_token(token)
            github_get_review_threads = _github_get_review_threads_from_token(token)
        validate_receipt(
            receipt,
            schema,
            evidence_root=ROOT,
            github_get_json=github_get_json,
            github_get_review_threads=github_get_review_threads,
            git_root=ROOT,
            receipt_path=receipt_path,
        )
    except (OSError, json.JSONDecodeError, jsonschema.ValidationError, ReceiptValidationError) as exc:
        print(f"FAIL: milestone receipt invalid: {exc}", file=sys.stderr)
        return 1
    print(f"OK: milestone receipt {receipt['receipt_id']} is structurally and semantically bound")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
