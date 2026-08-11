#!/usr/bin/env python3
"""Validate the post-merge ``B00R_RECEIPT_ANCHOR_G2`` and protected tag ruleset.

This is intentionally a post-merge terminal gate.  A receipt PR can be reviewed before the anchor
exists, but ``b00r_gate --mode receipt`` cannot return ``PASS_REPOSITORY_SAFE_HOLD`` until:

* the checked-out commit is the expected receipt merge;
* an annotated (not lightweight) ``B00R_RECEIPT_ANCHOR_G2`` tag points to that commit and its message
  binds the canonical receipt path and SHA-256; and
* a raw provider tag-ruleset capture is externally SHA-256 pinned and proves active exact-tag
  update/deletion restrictions with no bypass actors.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys

try:  # importable both as `python tools/...` and as `from tools import ...`
    from tools.github_ruleset_live import (  # type: ignore
        LiveRulesetError, LiveRulesetUnavailable, fetch_anchor_tag_object_sha,
        fetch_and_match_live_ruleset, fetch_and_verify_receipt_merge)
except ModuleNotFoundError:  # pragma: no cover - direct script fallback
    from github_ruleset_live import (  # type: ignore
        LiveRulesetError, LiveRulesetUnavailable, fetch_anchor_tag_object_sha,
        fetch_and_match_live_ruleset, fetch_and_verify_receipt_merge)

ROOT = pathlib.Path(__file__).resolve().parent.parent
TAG_NAME = "B00R_RECEIPT_ANCHOR_G2"
RECEIPT_PATH = "evidence/receipts/B00R.g2.receipt.v3.json"
DEFAULT_RULESET = "evidence/B00R_G2/tag_ruleset.provider.json"
PIN_ENV = "B00R_G2_TAG_RULESET_SHA256"
EXPECTED_SOURCE_TYPE = "Repository"
EXPECTED_SOURCE = "TriadAgentic/TriadOrigin"
HEX40_RE = re.compile(r"[0-9a-f]{40}")
HEX64_RE = re.compile(r"[0-9a-f]{64}")


class AnchorError(ValueError):
    """The receipt anchor is absent or does not prove immutable closure."""


def _git(root: pathlib.Path, *args: str, blocked_if_missing: bool = False) -> bytes:
    env = dict(os.environ)
    for name in tuple(env):
        if name.startswith("GIT_") and name not in {"GIT_CONFIG_NOSYSTEM"}:
            env.pop(name, None)
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    proc = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=False, env=env
    )
    if proc.returncode:
        detail = proc.stderr.decode("utf-8", errors="replace").strip()
        prefix = "BLOCKED" if blocked_if_missing else "FAIL"
        raise AnchorError(f"{prefix}: GIT_COMMAND_FAILED: git {' '.join(args)}: {detail}")
    return proc.stdout


def _parse_tag(raw: bytes) -> tuple[dict[str, str], str]:
    try:
        head, message = raw.decode("utf-8").split("\n\n", 1)
    except (UnicodeDecodeError, ValueError) as exc:
        raise AnchorError(f"FAIL: ANCHOR_TAG_OBJECT_MALFORMED: {exc}") from exc
    headers: dict[str, str] = {}
    for line in head.splitlines():
        if line.startswith("tagger "):
            key, value = "tagger", line.removeprefix("tagger ")
        elif " " in line:
            key, value = line.split(" ", 1)
        else:
            raise AnchorError(f"FAIL: ANCHOR_TAG_HEADER_MALFORMED: {line!r}")
        if key in headers:
            raise AnchorError(f"FAIL: ANCHOR_TAG_HEADER_DUPLICATE: {key}")
        headers[key] = value
    return headers, message


def _parse_anchor_message(message: str) -> dict[str, str]:
    lines = message.rstrip("\n").splitlines()
    if not lines or lines[0] != "TRIAD-B00R-RECEIPT-ANCHOR-G2-V1":
        raise AnchorError("FAIL: ANCHOR_MESSAGE_PROFILE_MISMATCH")
    values: dict[str, str] = {}
    for line in lines[1:]:
        if "=" not in line:
            raise AnchorError(f"FAIL: ANCHOR_MESSAGE_LINE_MALFORMED: {line!r}")
        key, value = line.split("=", 1)
        if key in values or key not in {"receipt_path", "receipt_sha256"}:
            raise AnchorError(f"FAIL: ANCHOR_MESSAGE_FIELD_INVALID: {key!r}")
        values[key] = value
    if set(values) != {"receipt_path", "receipt_sha256"}:
        raise AnchorError(f"FAIL: ANCHOR_MESSAGE_FIELDS_INCOMPLETE: {sorted(values)}")
    return values


def _loads_unique_object(data: bytes) -> dict:
    def unique_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise AnchorError(f"FAIL: TAG_RULESET_DUPLICATE_KEY:{key}")
            value[key] = item
        return value
    try:
        document = json.loads(data, object_pairs_hook=unique_object)
    except AnchorError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AnchorError(f"FAIL: TAG_RULESET_NOT_JSON:{exc}") from exc
    if not isinstance(document, dict):
        raise AnchorError("FAIL: TAG_RULESET_NOT_OBJECT")
    return document


def _validate_ruleset(doc: dict) -> None:
    if not isinstance(doc, dict):
        raise AnchorError("FAIL: TAG_RULESET_NOT_OBJECT")
    if doc.get("target") != "tag":
        raise AnchorError(f"FAIL: TAG_RULESET_WRONG_TARGET: {doc.get('target')!r}")
    if doc.get("enforcement") != "active":
        raise AnchorError(f"FAIL: TAG_RULESET_NOT_ACTIVE: {doc.get('enforcement')!r}")
    if not isinstance(doc.get("id"), int) or isinstance(doc.get("id"), bool) or doc["id"] <= 0:
        raise AnchorError("FAIL: TAG_RULESET_ID_INVALID")
    if "note" in doc:
        raise AnchorError("FAIL: TAG_RULESET_SYNTHETIC_METADATA")
    name = doc.get("name")
    if (not isinstance(name, str) or not name.strip()
            or name.strip().upper() in {"DECLARATIVE", "TEMPLATE", "PLACEHOLDER"}):
        raise AnchorError("FAIL: TAG_RULESET_NAME_INVALID")
    if doc.get("source_type") != EXPECTED_SOURCE_TYPE or doc.get("source") != EXPECTED_SOURCE:
        raise AnchorError(
            "FAIL: TAG_RULESET_SOURCE_MISMATCH: "
            f"source_type={doc.get('source_type')!r} source={doc.get('source')!r}"
        )
    if doc.get("current_user_can_bypass") != "never":
        raise AnchorError(
            "FAIL: TAG_RULESET_CURRENT_USER_BYPASS_NOT_NEVER: "
            f"{doc.get('current_user_can_bypass')!r}"
        )
    node_id = doc.get("node_id")
    if node_id is not None and (
        not isinstance(node_id, str) or re.fullmatch(r"RRS_[A-Za-z0-9_-]+", node_id) is None
    ):
        raise AnchorError("FAIL: TAG_RULESET_NODE_ID_INVALID")
    links = doc.get("_links")
    if links is not None:
        self_link = links.get("self") if isinstance(links, dict) else None
        html_link = links.get("html") if isinstance(links, dict) else None
        expected_self = (
            f"https://api.github.com/repos/{EXPECTED_SOURCE}/rulesets/{doc['id']}"
        )
        expected_html = f"https://github.com/{EXPECTED_SOURCE}/rules/{doc['id']}"
        html_href = html_link.get("href") if isinstance(html_link, dict) else None
        if (not isinstance(self_link, dict) or self_link.get("href") != expected_self
                or html_href not in (None, expected_html)):
            raise AnchorError("FAIL: TAG_RULESET_PROVIDER_LINKS_MISMATCH")
    for field in ("created_at", "updated_at"):
        value = doc.get(field)
        if not isinstance(value, str) or re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?Z",
            value,
        ) is None:
            raise AnchorError(f"FAIL: TAG_RULESET_TIMESTAMP_INVALID:{field}")
    conditions = doc.get("conditions")
    ref_name = conditions.get("ref_name") if isinstance(conditions, dict) else None
    include = ref_name.get("include") if isinstance(ref_name, dict) else None
    exclude = ref_name.get("exclude") if isinstance(ref_name, dict) else None
    expected_ref = f"refs/tags/{TAG_NAME}"
    if include != [expected_ref] or exclude not in ([], None):
        raise AnchorError(
            f"FAIL: TAG_RULESET_SCOPE_NOT_EXACT: include={include!r} exclude={exclude!r}"
        )
    bypass = doc.get("bypass_actors")
    if bypass != []:
        raise AnchorError(f"FAIL: TAG_RULESET_BYPASS_ACTORS_PRESENT: {bypass!r}")
    rules = doc.get("rules")
    if not isinstance(rules, list):
        raise AnchorError("FAIL: TAG_RULESET_RULES_NOT_ARRAY")
    rule_types = {rule.get("type") for rule in rules if isinstance(rule, dict)}
    missing = {"update", "deletion"} - rule_types
    if missing:
        raise AnchorError(f"FAIL: TAG_RULESET_IMMUTABILITY_RULE_MISSING: {sorted(missing)}")


def _ruleset_time_us(value: object, field: str) -> int:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise AnchorError(f"FAIL: TAG_RULESET_TIMESTAMP_INVALID:{field}")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
        if parsed.tzinfo is None:
            raise ValueError("timezone absent")
        return int(parsed.timestamp() * 1_000_000)
    except (OverflowError, TypeError, ValueError) as exc:
        raise AnchorError(f"FAIL: TAG_RULESET_TIMESTAMP_INVALID:{field}") from exc


def _canonical_file(
    root: pathlib.Path,
    path: pathlib.Path,
    expected_rel: str,
    label: str,
) -> pathlib.Path:
    """Resolve one exact repository file while rejecting every symlink component."""
    lexical = path if path.is_absolute() else root / path
    try:
        rel = lexical.absolute().relative_to(root).as_posix()
    except ValueError as exc:
        raise AnchorError(f"FAIL: {label}_OUTSIDE_REPOSITORY: {path}") from exc
    if rel != expected_rel:
        raise AnchorError(f"FAIL: {label}_PATH_NOT_CANONICAL: {rel}")
    cursor = root
    for part in pathlib.PurePosixPath(rel).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise AnchorError(f"FAIL: {label}_SYMLINK: {rel}")
    if not cursor.is_file():
        raise AnchorError(f"BLOCKED: {label}_ABSENT: {rel}")
    return cursor


def _verify_static_bundle(
    *,
    root: pathlib.Path,
    expected_head: str,
    receipt_path: pathlib.Path,
    ruleset_path: pathlib.Path,
    ruleset_pin: str | None,
) -> tuple[str, bytes, str]:
    root = root.resolve()
    if HEX40_RE.fullmatch(expected_head or "") is None:
        raise AnchorError(f"FAIL: EXPECTED_HEAD_NOT_CANONICAL_HEX40: {expected_head!r}")
    actual_head = _git(root, "rev-parse", "HEAD").decode().strip()
    if actual_head != expected_head:
        raise AnchorError(f"FAIL: EXPECTED_HEAD_MISMATCH: {actual_head}!={expected_head}")
    if _git(root, "status", "--porcelain=v1", "--untracked-files=all").strip():
        raise AnchorError("FAIL: GIT_WORKTREE_NOT_CLEAN")

    receipt_path = _canonical_file(root, receipt_path, RECEIPT_PATH, "RECEIPT")
    receipt_rel = RECEIPT_PATH
    _git(root, "ls-files", "--error-unmatch", "--", receipt_rel)
    receipt_data = receipt_path.read_bytes()
    receipt_sha = hashlib.sha256(receipt_data).hexdigest()
    committed_receipt = _git(root, "show", f"{expected_head}:{receipt_rel}")
    if committed_receipt != receipt_data:
        raise AnchorError("FAIL: RECEIPT_WORKTREE_DIFFERS_FROM_EXPECTED_HEAD")
    try:
        receipt_document = _loads_unique_object(receipt_data)
        source_merge_sha = receipt_document["payload"]["source_merge_sha"]
    except (KeyError, TypeError) as exc:
        raise AnchorError("FAIL: RECEIPT_SOURCE_MERGE_IDENTITY_MALFORMED") from exc
    if not isinstance(source_merge_sha, str) or HEX40_RE.fullmatch(source_merge_sha) is None:
        raise AnchorError("FAIL: RECEIPT_SOURCE_MERGE_IDENTITY_MALFORMED")
    parent_row = _git(root, "rev-list", "--parents", "-n", "1", expected_head).decode().split()
    if (len(parent_row) != 3 or parent_row[0] != expected_head
            or parent_row[1] != source_merge_sha):
        raise AnchorError("FAIL: RECEIPT_MERGE_NOT_EXACT_TWO_PARENT_SOURCE_MERGE")
    if _git(root, "rev-parse", f"{expected_head}^{{tree}}").strip() != _git(
            root, "rev-parse", f"{parent_row[2]}^{{tree}}").strip():
        raise AnchorError("FAIL: RECEIPT_MERGE_TREE_DIFFERS_FROM_PR_HEAD")

    ref = f"refs/tags/{TAG_NAME}"
    tag_object_sha = _git(
        root, "rev-parse", "--verify", ref, blocked_if_missing=True).decode().strip()
    if HEX40_RE.fullmatch(tag_object_sha) is None:
        raise AnchorError("FAIL: ANCHOR_TAG_OBJECT_SHA_INVALID")
    object_type = _git(root, "cat-file", "-t", tag_object_sha).decode().strip()
    if object_type != "tag":
        raise AnchorError(f"FAIL: ANCHOR_TAG_NOT_ANNOTATED: type={object_type!r}")
    raw_tag = _git(root, "cat-file", "tag", tag_object_sha)
    headers, message = _parse_tag(raw_tag)
    if headers.get("object") != expected_head or headers.get("type") != "commit":
        raise AnchorError(
            f"FAIL: ANCHOR_TAG_TARGET_MISMATCH: object={headers.get('object')!r} "
            f"type={headers.get('type')!r}"
        )
    if headers.get("tag") != TAG_NAME or not headers.get("tagger"):
        raise AnchorError("FAIL: ANCHOR_TAG_IDENTITY_MISMATCH")
    values = _parse_anchor_message(message)
    if values["receipt_path"] != RECEIPT_PATH:
        raise AnchorError("FAIL: ANCHOR_RECEIPT_PATH_MISMATCH")
    if values["receipt_sha256"] != receipt_sha:
        raise AnchorError("FAIL: ANCHOR_RECEIPT_DIGEST_MISMATCH")
    if ruleset_pin is None or ruleset_pin == "":
        raise AnchorError(f"BLOCKED: EXTERNAL_TAG_RULESET_PIN_ABSENT: {PIN_ENV}")
    if HEX64_RE.fullmatch(ruleset_pin) is None or ruleset_pin == "0" * 64:
        raise AnchorError(f"FAIL: EXTERNAL_TAG_RULESET_PIN_INVALID: {ruleset_pin!r}")
    ruleset_path = _canonical_file(root, ruleset_path, DEFAULT_RULESET, "TAG_RULESET")
    ruleset_rel = DEFAULT_RULESET
    _git(root, "ls-files", "--error-unmatch", "--", ruleset_rel)
    ruleset_bytes = ruleset_path.read_bytes()
    committed_ruleset = _git(root, "show", f"{expected_head}:{ruleset_rel}")
    if committed_ruleset != ruleset_bytes:
        raise AnchorError("FAIL: TAG_RULESET_WORKTREE_DIFFERS_FROM_EXPECTED_HEAD")
    if hashlib.sha256(ruleset_bytes).hexdigest() != ruleset_pin:
        raise AnchorError("FAIL: TAG_RULESET_EXTERNAL_PIN_MISMATCH")
    ruleset = _loads_unique_object(ruleset_bytes)
    _validate_ruleset(ruleset)
    return receipt_sha, ruleset_bytes, tag_object_sha


def _verify_static(
    *,
    root: pathlib.Path,
    expected_head: str,
    receipt_path: pathlib.Path,
    ruleset_path: pathlib.Path,
    ruleset_pin: str | None,
) -> str:
    """Run the static anchor checks and return the bound receipt digest for unit callers."""
    receipt_sha, _ruleset_bytes, _tag_object_sha = _verify_static_bundle(
        root=root,
        expected_head=expected_head,
        receipt_path=receipt_path,
        ruleset_path=ruleset_path,
        ruleset_pin=ruleset_pin,
    )
    return receipt_sha


def verify(
    *,
    root: pathlib.Path,
    expected_head: str,
    receipt_path: pathlib.Path,
    ruleset_path: pathlib.Path,
    ruleset_pin: str | None,
    now_us: int,
    github_token: str | None,
    receipt_pr: int,
) -> str:
    """Run the complete terminal anchor gate, including a fresh authenticated provider GET."""
    if not isinstance(now_us, int) or isinstance(now_us, bool) or now_us <= 0:
        raise AnchorError("FAIL: NOW_US_INVALID")
    receipt_sha, ruleset_bytes, tag_object_sha = _verify_static_bundle(
        root=root,
        expected_head=expected_head,
        receipt_path=receipt_path,
        ruleset_path=ruleset_path,
        ruleset_pin=ruleset_pin,
    )
    receipt_proof = fetch_and_verify_receipt_merge(
        receipt_pr,
        expected_merge_sha=expected_head,
        expected_codeowner="djordi10",
        token=github_token,
        now_us=now_us,
    )
    parent_row = _git(root, "rev-list", "--parents", "-n", "1", expected_head).decode().split()
    if (len(parent_row) != 3 or parent_row[0] != expected_head
            or parent_row[2] != receipt_proof.head_sha):
        raise AnchorError("FAIL: RECEIPT_MERGE_NOT_EXACT_TWO_PARENT_PR_MERGE")
    # Static verification already proved the first parent is the receipt-declared source merge.
    receipt_git_time_us = int(
        _git(root, "show", "-s", "--format=%ct", expected_head).decode().strip()
    ) * 1_000_000
    if receipt_proof.merged_at_us != receipt_git_time_us:
        raise AnchorError("FAIL: RECEIPT_PR_PROVIDER_GIT_TIME_MISMATCH")
    ruleset_document = _loads_unique_object(ruleset_bytes)
    created_at_us = _ruleset_time_us(ruleset_document.get("created_at"), "created_at")
    updated_at_us = _ruleset_time_us(ruleset_document.get("updated_at"), "updated_at")
    if not created_at_us <= updated_at_us < receipt_proof.merged_at_us:
        raise AnchorError("FAIL: TAG_RULESET_NOT_EFFECTIVE_BEFORE_RECEIPT_MERGE")
    fetch_and_match_live_ruleset(
        ruleset_bytes, token=github_token, now_us=now_us,
        require_bypass_visibility=True)
    live_tag_object_sha = fetch_anchor_tag_object_sha(
        token=github_token, now_us=now_us)
    if live_tag_object_sha != tag_object_sha:
        raise AnchorError("FAIL: LIVE_ANCHOR_TAG_OBJECT_MISMATCH")
    return receipt_sha


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--now-us", required=True, type=int)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--receipt", default=RECEIPT_PATH)
    parser.add_argument("--ruleset", default=DEFAULT_RULESET)
    parser.add_argument("--ruleset-pin")
    parser.add_argument("--receipt-pr", required=True, type=int)
    args = parser.parse_args(argv)
    root = pathlib.Path(args.root)
    receipt = pathlib.Path(args.receipt)
    ruleset = pathlib.Path(args.ruleset)
    if not receipt.is_absolute():
        receipt = root / receipt
    if not ruleset.is_absolute():
        ruleset = root / ruleset
    pin = args.ruleset_pin if args.ruleset_pin is not None else os.environ.get(PIN_ENV)
    try:
        receipt_sha = verify(
            root=root,
            expected_head=args.expected_head,
            receipt_path=receipt,
            ruleset_path=ruleset,
            ruleset_pin=pin,
            now_us=args.now_us,
            github_token=os.environ.get("GITHUB_TOKEN"),
            receipt_pr=args.receipt_pr,
        )
    except LiveRulesetUnavailable as exc:
        print(f"BLOCKED: LIVE_TAG_PROVIDER_UNAVAILABLE:{exc}")
        return 1
    except LiveRulesetError as exc:
        if str(exc) == "LIVE_ANCHOR_TAG_REF_HTTP_STATUS:404":
            print("BLOCKED: LIVE_ANCHOR_TAG_ABSENT")
            return 1
        print(str(exc), file=sys.stderr)
        return 1
    except (AnchorError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        f"OK: {TAG_NAME} binds receipt merge {args.expected_head}, receipt {receipt_sha}, "
        "and a live no-bypass tag ruleset"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
