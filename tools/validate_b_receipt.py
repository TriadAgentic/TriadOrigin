#!/usr/bin/env python3
"""Validate historical v2 receipts or a closure-capable canonical bare receipt-v3.

Strict v3 validation consumes the complete externally pinned authority context, a caller-supplied
trusted ``now_us``, an exact Git head, and a closed evidence manifest.  It never accepts a free
standing trust file, hard-coded threshold, self hash, or DSSE wrapper.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import contracts, governance  # noqa: E402
from triad_origin.canonical import (  # noqa: E402
    CanonicalError, canonical_json, loads_canonical, sha256_hex)
try:  # importable both as ``python tools/...`` and as ``from tools import ...``
    from tools.b00r_clean_runner import (  # type: ignore  # noqa: E402
        ALLOWED_EMPTY_PATHS, CleanRunnerError,
        validate_bundle as validate_clean_runner_bundle)
except ModuleNotFoundError:  # pragma: no cover - direct script fallback
    from b00r_clean_runner import (  # type: ignore  # noqa: E402
        ALLOWED_EMPTY_PATHS, CleanRunnerError,
        validate_bundle as validate_clean_runner_bundle)
try:  # importable both as ``python tools/...`` and as ``from tools import ...``
    from tools.validate_authority_root import (  # type: ignore  # noqa: E402
        AuthorityContext, AuthorityRootError, AuthorityRootUnavailable, ed25519_verify,
        load_authority_context, validate_git_bound_authority)
except ModuleNotFoundError:  # pragma: no cover - direct script fallback
    from validate_authority_root import (  # type: ignore  # noqa: E402
        AuthorityContext, AuthorityRootError, AuthorityRootUnavailable, ed25519_verify,
        load_authority_context, validate_git_bound_authority)
try:  # importable both as `python tools/...` and as `from tools import ...`
    from tools.github_ruleset_live import (  # type: ignore  # noqa: E402
        LiveRulesetError, LiveRulesetUnavailable, fetch_and_match_live_ruleset,
        fetch_and_match_pull_request,
        fetch_and_match_pull_request_review, fetch_and_match_rule_suite,
        fetch_and_verify_receipt_head, fetch_and_verify_receipt_merge,
        fetch_canary_ref_sha, fetch_repository_permission)
except ModuleNotFoundError:  # pragma: no cover - direct script fallback
    from github_ruleset_live import (  # type: ignore  # noqa: E402
        LiveRulesetError, LiveRulesetUnavailable, fetch_and_match_live_ruleset,
        fetch_and_match_pull_request,
        fetch_and_match_pull_request_review, fetch_and_match_rule_suite,
        fetch_and_verify_receipt_head, fetch_and_verify_receipt_merge,
        fetch_canary_ref_sha, fetch_repository_permission)


class ReceiptBindingError(ValueError):
    """Receipt bytes do not bind to the declared manifest or Git graph."""


class ReceiptBindingUnavailable(ReceiptBindingError):
    """A live provider or credential needed for terminal proof is unavailable."""


EVIDENCE_ROOT = "evidence/B00R_G2"
CANONICAL_MANIFEST_PATH = f"{EVIDENCE_ROOT}/evidence_manifest.json"
CANONICAL_RECEIPT_PATH = "evidence/receipts/B00R.g2.receipt.v3.json"
TAG_RULESET_ROLE = "TAG_RULESET_PROVIDER"
TAG_RULESET_PATH = f"{EVIDENCE_ROOT}/tag_ruleset.provider.json"
CANARY_PATH = f"{EVIDENCE_ROOT}/provider_negative_canary.v1.json"
CANARY_TRANSCRIPT_ROLE = "PROVIDER_NEGATIVE_CANARY_TRANSCRIPT"
CANARY_TRANSCRIPT_PATH = f"{EVIDENCE_ROOT}/provider_negative_canary.transcript.txt"
CANARY_RULE_SUITE_ROLE = "PROVIDER_NEGATIVE_CANARY_RULE_SUITE"
CANARY_RULE_SUITE_PATH = f"{EVIDENCE_ROOT}/provider_negative_canary.rule_suite.raw.json"
CANARY_REF = "refs/heads/b00r-ruleset-canary"
SOURCE_PR_ROLE = "SOURCE_PR_PROVIDER_RECORD"
SOURCE_PR_PATH = f"{EVIDENCE_ROOT}/source_pr.provider.raw.json"
SOURCE_PR_REVIEW_ROLE = "SOURCE_PR_APPROVED_REVIEW_PROVIDER_RECORD"
SOURCE_PR_REVIEW_PATH = f"{EVIDENCE_ROOT}/source_pr.approved_review.provider.raw.json"
CODEOWNERS_BOOTSTRAP_PR_ROLE = "CODEOWNERS_BOOTSTRAP_PR_PROVIDER_RECORD"
CODEOWNERS_BOOTSTRAP_PR_PATH = \
    f"{EVIDENCE_ROOT}/codeowners_bootstrap_pr.provider.raw.json"
CODEOWNERS_BOOTSTRAP_REVIEW_ROLE = \
    "CODEOWNERS_BOOTSTRAP_APPROVED_REVIEW_PROVIDER_RECORD"
CODEOWNERS_BOOTSTRAP_REVIEW_PATH = \
    f"{EVIDENCE_ROOT}/codeowners_bootstrap_pr.approved_review.provider.raw.json"
REPOSITORY_ID = 1_327_825_324
MAX_CANARY_TIME_SKEW_US = 5 * 60 * 1_000_000
RECEIPT_DIGEST_ROLE_FIELDS = {
    "WORKFLOW": "workflow_sha256",
    "CONTRACT_MANIFEST": "contract_manifest_sha256",
    "TEST_MANIFEST": "test_manifest_sha256",
    "CONFIG_BUNDLE": "config_bundle_sha256",
    "ROLLBACK_PROOF": "rollback_proof_sha256",
}


def _validate_tag_ruleset_manifest_entry(entries: list[dict]) -> None:
    """Require one signed-manifest binding for the canonical pre-anchor provider capture."""
    matches = [entry for entry in entries if entry.get("role") == TAG_RULESET_ROLE]
    if (len(matches) != 1
            or matches[0].get("path") != TAG_RULESET_PATH
            or matches[0].get("role_unique") is not True):
        raise ReceiptBindingError(
            f"TAG_RULESET_PROVIDER_ROLE_COUNT_OR_PATH:{len(matches)}")


def _validate_receipt_digest_roles(
    entries: list[dict], payload: dict, *, require_explicit_unique: bool = True
) -> None:
    """Bind each receipt digest field to exactly one singleton manifest role.

    Generation-2 B00R requires the new literal ``role_unique:true`` declaration.  Successor
    milestones retain the receipt-v3 legacy default where omission means singleton, while an
    explicit false declaration is still rejected for these reserved digest roles.
    """
    for role, field in RECEIPT_DIGEST_ROLE_FIELDS.items():
        matches = [entry for entry in entries if entry.get("role") == role]
        unique = (
            len(matches) == 1
            and (
                matches[0].get("role_unique") is True
                if require_explicit_unique
                else matches[0].get("role_unique", True) is True
            )
        )
        if not unique:
            raise ReceiptBindingError(
                f"EVIDENCE_RESERVED_ROLE_COUNT_OR_UNIQUENESS:{role}:{len(matches)}")
        if matches[0].get("sha256") != payload[field]:
            raise ReceiptBindingError(f"EVIDENCE_ROLE_DIGEST_MISMATCH:{role}")


def _loads_unique_json(data: bytes | str, label: str) -> dict:
    def _unique_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ReceiptBindingError(f"{label}_DUPLICATE_KEY:{key}")
            value[key] = item
        return value
    try:
        value = json.loads(data, object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReceiptBindingError(f"{label}_NOT_JSON:{exc}") from exc
    if not isinstance(value, dict):
        raise ReceiptBindingError(f"{label}_NOT_OBJECT")
    return value


def compute_signature(payload: dict) -> str:
    """Historical v2 self-integrity hash (not an authentication signature)."""
    unsigned = dict(payload)
    unsigned["signature"] = ""
    return sha256_hex(canonical_json(unsigned))


def _legacy(path: pathlib.Path) -> int:
    try:
        event = json.loads(path.read_text(encoding="utf-8"))
        contracts.validate(event, schema_id="triad.evidence_receipt.v2")
    except (OSError, json.JSONDecodeError, contracts.ContractError) as exc:
        print(f"FAIL: receipt is not contract-valid: {exc}", file=sys.stderr)
        return 1
    payload = event["payload"]
    milestone = payload.get("scope", {}).get("milestone")
    if path.stem != milestone:
        print(f"FAIL: receipt file {path.name} names milestone {milestone!r}", file=sys.stderr)
        return 1
    expected = compute_signature(payload)
    if payload.get("signature") != expected:
        print("FAIL: receipt self-integrity signature mismatch", file=sys.stderr)
        return 1
    print(f"OK: milestone receipt {milestone} self-integrity valid ({payload['result']}) "
          "— LEGACY v2, not a closure authentication")
    return 0


def _git(root: pathlib.Path, *args: str, text: bool = True) -> str | bytes:
    env = dict(os.environ)
    for name in tuple(env):
        if name.startswith("GIT_") and name not in {"GIT_CONFIG_NOSYSTEM"}:
            env.pop(name, None)
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    proc = subprocess.run(
        ["git", "-C", str(root), *args], check=False, capture_output=True,
        text=text, env=env)
    if proc.returncode:
        err = proc.stderr.strip() if text else proc.stderr.decode("utf-8", "replace").strip()
        raise ReceiptBindingError(f"GIT_COMMAND_FAILED:{' '.join(args)}:{err}")
    return proc.stdout.strip() if text else proc.stdout


def _relative_inside(path: pathlib.Path, root: pathlib.Path, label: str) -> str:
    try:
        return path.resolve(strict=True).relative_to(root).as_posix()
    except (OSError, ValueError):
        raise ReceiptBindingError(f"{label}_OUTSIDE_GIT_ROOT") from None


def _validate_source_pr_provider_record(
    *,
    entries: list[dict],
    root: pathlib.Path,
    payload: dict,
    now_us: int | None,
    github_token: str | None,
    require_live_provider: bool,
) -> int:
    """Return GitHub's authenticated merge time for the exact source PR/merge tuple."""
    matches = [entry for entry in entries if entry.get("role") == SOURCE_PR_ROLE]
    if (len(matches) != 1 or matches[0].get("path") != SOURCE_PR_PATH
            or matches[0].get("role_unique") is not True):
        raise ReceiptBindingError(f"SOURCE_PR_PROVIDER_ROLE_COUNT_OR_PATH:{len(matches)}")
    entry = matches[0]
    raw = (root / SOURCE_PR_PATH).read_bytes()
    if sha256_hex(raw) != entry.get("sha256"):
        raise ReceiptBindingError("SOURCE_PR_PROVIDER_DIGEST_MISMATCH")
    document = _loads_unique_json(raw, "SOURCE_PR_PROVIDER")
    source_pr = payload.get("source_pr")
    base = document.get("base")
    head = document.get("head")
    base_repo = base.get("repo") if isinstance(base, dict) else None
    head_repo = head.get("repo") if isinstance(head, dict) else None
    author = document.get("user")
    if (not isinstance(source_pr, int) or isinstance(source_pr, bool) or source_pr <= 0
            or document.get("number") != source_pr
            or document.get("state") != "closed" or document.get("merged") is not True
            or document.get("merge_commit_sha") != payload.get("source_merge_sha")
            or not isinstance(base, dict) or base.get("ref") != "main"
            or not isinstance(base_repo, dict)
            or base_repo.get("full_name") != "TriadAgentic/TriadOrigin"
            or base_repo.get("id") != REPOSITORY_ID
            or not isinstance(head, dict)
            or head.get("sha") != payload.get("final_source_head")
            or not isinstance(head_repo, dict)
            or head_repo.get("full_name") != "TriadAgentic/TriadOrigin"
            or head_repo.get("id") != REPOSITORY_ID
            or not isinstance(author, dict) or author.get("type") != "User"
            or not isinstance(author.get("login"), str) or not author.get("login")):
        raise ReceiptBindingError("SOURCE_PR_PROVIDER_IDENTITY_MISMATCH")
    try:
        merged_at_us = governance._parse_provider_utc_us(  # noqa: SLF001
            document.get("merged_at"))
    except governance.GovernanceError as exc:
        raise ReceiptBindingError(f"SOURCE_PR_PROVIDER_MERGED_AT_INVALID:{exc}") from exc
    if merged_at_us != payload.get("source_merge_time_us"):
        raise ReceiptBindingError("SOURCE_PR_PROVIDER_PAYLOAD_TIME_MISMATCH")
    observed_at_us = payload.get("observed_at_us")
    emitted_at_us = payload.get("emitted_at_us")
    if (not isinstance(observed_at_us, int) or isinstance(observed_at_us, bool)
            or not isinstance(emitted_at_us, int) or isinstance(emitted_at_us, bool)
            or not merged_at_us < observed_at_us <= emitted_at_us):
        raise ReceiptBindingError("SOURCE_PR_PROVIDER_RECEIPT_CHRONOLOGY_INVALID")
    if now_us is not None and merged_at_us > now_us:
        raise ReceiptBindingError("SOURCE_PR_PROVIDER_MERGED_AT_IN_FUTURE")
    if require_live_provider:
        if now_us is None:
            raise ReceiptBindingError("SOURCE_PR_PROVIDER_LIVE_NOW_ABSENT")
        try:
            fetch_and_match_pull_request(raw, token=github_token, now_us=now_us)
        except LiveRulesetUnavailable as exc:
            raise ReceiptBindingUnavailable(
                f"SOURCE_PR_PROVIDER_LIVE_PROOF:{exc}") from exc
        except LiveRulesetError as exc:
            raise ReceiptBindingError(f"SOURCE_PR_PROVIDER_LIVE_PROOF:{exc}") from exc
    return merged_at_us


def _validate_source_pr_approved_review(
    *,
    entries: list[dict],
    root: pathlib.Path,
    payload: dict,
    provider_merge_time_us: int,
    now_us: int | None,
    github_token: str | None,
    require_live_provider: bool,
) -> None:
    """Bind one real independent CODEOWNER approval to the exact source head before merge."""
    matches = [entry for entry in entries if entry.get("role") == SOURCE_PR_REVIEW_ROLE]
    if (len(matches) != 1 or matches[0].get("path") != SOURCE_PR_REVIEW_PATH
            or matches[0].get("role_unique") is not True):
        raise ReceiptBindingError(f"SOURCE_PR_REVIEW_ROLE_COUNT_OR_PATH:{len(matches)}")
    raw = (root / SOURCE_PR_REVIEW_PATH).read_bytes()
    if sha256_hex(raw) != matches[0].get("sha256"):
        raise ReceiptBindingError("SOURCE_PR_REVIEW_DIGEST_MISMATCH")
    record = _loads_unique_json(raw, "SOURCE_PR_REVIEW")
    review = record.get("review")
    user = review.get("user") if isinstance(review, dict) else None
    reviewer = user.get("login") if isinstance(user, dict) else None
    if (record.get("source_pr") != payload.get("source_pr")
            or record.get("source_head") != payload.get("final_source_head")
            or not isinstance(review, dict)
            or not isinstance(review.get("id"), int) or isinstance(review.get("id"), bool)
            or review.get("id") <= 0
            or review.get("state") != "APPROVED"
            or review.get("commit_id") != payload.get("final_source_head")
            or not isinstance(user, dict) or user.get("type") != "User"
            or not isinstance(reviewer, str) or not reviewer):
        raise ReceiptBindingError("SOURCE_PR_REVIEW_IDENTITY_MISMATCH")
    source_pr = _loads_unique_json(
        (root / SOURCE_PR_PATH).read_bytes(), "SOURCE_PR_PROVIDER_FOR_REVIEW")
    author = source_pr.get("user")
    author_login = author.get("login") if isinstance(author, dict) else None
    if not isinstance(author_login, str) or reviewer.lower() == author_login.lower():
        raise ReceiptBindingError("SOURCE_PR_REVIEW_NOT_INDEPENDENT_OF_AUTHOR")
    try:
        submitted_at_us = governance._parse_provider_utc_us(  # noqa: SLF001
            review.get("submitted_at"))
    except governance.GovernanceError as exc:
        raise ReceiptBindingError(f"SOURCE_PR_REVIEW_SUBMITTED_AT_INVALID:{exc}") from exc
    if submitted_at_us >= provider_merge_time_us:
        raise ReceiptBindingError("SOURCE_PR_REVIEW_NOT_BEFORE_SOURCE_MERGE")
    try:
        from tools.verify_codeowners import verify as verify_codeowners  # type: ignore
    except ModuleNotFoundError:  # pragma: no cover - direct script fallback
        from verify_codeowners import verify as verify_codeowners  # type: ignore
    _count, owners = verify_codeowners(root / ".github" / "CODEOWNERS")
    if owners != {f"@{reviewer}"}:
        raise ReceiptBindingError(
            f"SOURCE_PR_REVIEWER_NOT_SOLE_CODEOWNER:{reviewer}:{sorted(owners)}")
    if require_live_provider:
        if now_us is None:
            raise ReceiptBindingError("SOURCE_PR_REVIEW_LIVE_NOW_ABSENT")
        try:
            fetch_and_match_pull_request_review(
                raw, token=github_token, now_us=now_us)
            fetch_repository_permission(
                reviewer, token=github_token, now_us=now_us)
        except LiveRulesetUnavailable as exc:
            raise ReceiptBindingUnavailable(
                f"SOURCE_PR_REVIEW_LIVE_PROOF:{exc}") from exc
        except LiveRulesetError as exc:
            raise ReceiptBindingError(f"SOURCE_PR_REVIEW_LIVE_PROOF:{exc}") from exc


def _validate_codeowners_bootstrap(
    *,
    entries: list[dict],
    root: pathlib.Path,
    payload: dict,
    source_base_parent: str,
    source_provider_merge_time_us: int,
    now_us: int | None,
    github_token: str | None,
    require_live_provider: bool,
) -> None:
    """Prove ``source_base_parent`` is a separately reviewed CODEOWNERS-only PR merge."""
    pr_entries = [
        entry for entry in entries if entry.get("role") == CODEOWNERS_BOOTSTRAP_PR_ROLE
    ]
    if (len(pr_entries) != 1
            or pr_entries[0].get("path") != CODEOWNERS_BOOTSTRAP_PR_PATH
            or pr_entries[0].get("role_unique") is not True):
        raise ReceiptBindingError(
            f"CODEOWNERS_BOOTSTRAP_PR_ROLE_COUNT_OR_PATH:{len(pr_entries)}")
    pr_raw = (root / CODEOWNERS_BOOTSTRAP_PR_PATH).read_bytes()
    if sha256_hex(pr_raw) != pr_entries[0].get("sha256"):
        raise ReceiptBindingError("CODEOWNERS_BOOTSTRAP_PR_DIGEST_MISMATCH")
    document = _loads_unique_json(pr_raw, "CODEOWNERS_BOOTSTRAP_PR_PROVIDER")
    number = document.get("number")
    base = document.get("base")
    head = document.get("head")
    base_repo = base.get("repo") if isinstance(base, dict) else None
    head_repo = head.get("repo") if isinstance(head, dict) else None
    head_sha = head.get("sha") if isinstance(head, dict) else None
    author = document.get("user")
    author_login = author.get("login") if isinstance(author, dict) else None
    if (not isinstance(number, int) or isinstance(number, bool) or number <= 0
            or number == payload.get("source_pr")
            or document.get("state") != "closed" or document.get("merged") is not True
            or document.get("merge_commit_sha") != source_base_parent
            or not isinstance(base, dict) or base.get("ref") != "main"
            or not isinstance(base_repo, dict)
            or base_repo.get("full_name") != "TriadAgentic/TriadOrigin"
            or base_repo.get("id") != REPOSITORY_ID
            or not isinstance(head, dict)
            or not isinstance(head_sha, str)
            or re.fullmatch(r"[0-9a-f]{40}", head_sha) is None
            or not isinstance(head_repo, dict)
            or head_repo.get("full_name") != "TriadAgentic/TriadOrigin"
            or head_repo.get("id") != REPOSITORY_ID
            or not isinstance(author, dict) or author.get("type") != "User"
            or not isinstance(author_login, str) or not author_login):
        raise ReceiptBindingError("CODEOWNERS_BOOTSTRAP_PR_IDENTITY_MISMATCH")
    try:
        merged_at_us = governance._parse_provider_utc_us(  # noqa: SLF001
            document.get("merged_at"))
    except governance.GovernanceError as exc:
        raise ReceiptBindingError(
            f"CODEOWNERS_BOOTSTRAP_PR_MERGED_AT_INVALID:{exc}") from exc
    if merged_at_us >= source_provider_merge_time_us:
        raise ReceiptBindingError("CODEOWNERS_BOOTSTRAP_NOT_BEFORE_SOURCE_MERGE")
    if now_us is not None and merged_at_us > now_us:
        raise ReceiptBindingError("CODEOWNERS_BOOTSTRAP_MERGED_AT_IN_FUTURE")

    parent_row = str(
        _git(root, "rev-list", "--parents", "-n", "1", source_base_parent)).split()
    if (len(parent_row) != 3 or parent_row[0] != source_base_parent
            or parent_row[2] != head_sha):
        raise ReceiptBindingError("CODEOWNERS_BOOTSTRAP_NOT_EXACT_TWO_PARENT_PR_MERGE")
    bootstrap_base = parent_row[1]
    if str(_git(root, "rev-parse", f"{head_sha}^{{tree}}")) != str(
            _git(root, "rev-parse", f"{source_base_parent}^{{tree}}")):
        raise ReceiptBindingError("CODEOWNERS_BOOTSTRAP_HEAD_TREE_MISMATCH")
    bootstrap_time_us = int(str(
        _git(root, "show", "-s", "--format=%ct", source_base_parent))) * 1_000_000
    if merged_at_us != bootstrap_time_us:
        raise ReceiptBindingError("CODEOWNERS_BOOTSTRAP_PROVIDER_GIT_TIME_MISMATCH")
    changed = set(str(_git(
        root, "diff", "--name-only", bootstrap_base, head_sha)).splitlines())
    if changed != {".github/CODEOWNERS"}:
        raise ReceiptBindingError(
            f"CODEOWNERS_BOOTSTRAP_DIFF_NOT_EXACT:{sorted(changed)}")
    before = _git(root, "show", f"{bootstrap_base}:.github/CODEOWNERS", text=False)
    after = _git(root, "show", f"{source_base_parent}:.github/CODEOWNERS", text=False)
    if before == after:
        raise ReceiptBindingError("CODEOWNERS_BOOTSTRAP_BYTES_UNCHANGED")

    review_entries = [
        entry for entry in entries if entry.get("role") == CODEOWNERS_BOOTSTRAP_REVIEW_ROLE
    ]
    if (len(review_entries) != 1
            or review_entries[0].get("path") != CODEOWNERS_BOOTSTRAP_REVIEW_PATH
            or review_entries[0].get("role_unique") is not True):
        raise ReceiptBindingError(
            f"CODEOWNERS_BOOTSTRAP_REVIEW_ROLE_COUNT_OR_PATH:{len(review_entries)}")
    review_raw = (root / CODEOWNERS_BOOTSTRAP_REVIEW_PATH).read_bytes()
    if sha256_hex(review_raw) != review_entries[0].get("sha256"):
        raise ReceiptBindingError("CODEOWNERS_BOOTSTRAP_REVIEW_DIGEST_MISMATCH")
    record = _loads_unique_json(review_raw, "CODEOWNERS_BOOTSTRAP_REVIEW")
    review = record.get("review")
    user = review.get("user") if isinstance(review, dict) else None
    reviewer = user.get("login") if isinstance(user, dict) else None
    if (record.get("source_pr") != number
            or record.get("source_head") != head_sha
            or not isinstance(review, dict)
            or not isinstance(review.get("id"), int) or isinstance(review.get("id"), bool)
            or review.get("id") <= 0
            or review.get("state") != "APPROVED"
            or review.get("commit_id") != head_sha
            or not isinstance(user, dict) or user.get("type") != "User"
            or not isinstance(reviewer, str) or reviewer.lower() != "djordi10"):
        raise ReceiptBindingError("CODEOWNERS_BOOTSTRAP_REVIEW_IDENTITY_MISMATCH")
    if reviewer.lower() == author_login.lower():
        raise ReceiptBindingError("CODEOWNERS_BOOTSTRAP_REVIEW_NOT_INDEPENDENT")
    try:
        submitted_at_us = governance._parse_provider_utc_us(  # noqa: SLF001
            review.get("submitted_at"))
    except governance.GovernanceError as exc:
        raise ReceiptBindingError(
            f"CODEOWNERS_BOOTSTRAP_REVIEW_SUBMITTED_AT_INVALID:{exc}") from exc
    if submitted_at_us >= merged_at_us:
        raise ReceiptBindingError("CODEOWNERS_BOOTSTRAP_REVIEW_NOT_BEFORE_MERGE")
    if require_live_provider:
        if now_us is None:
            raise ReceiptBindingError("CODEOWNERS_BOOTSTRAP_LIVE_NOW_ABSENT")
        try:
            fetch_and_match_pull_request(pr_raw, token=github_token, now_us=now_us)
            fetch_and_match_pull_request_review(
                review_raw, token=github_token, now_us=now_us)
            fetch_repository_permission(
                reviewer, token=github_token, now_us=now_us)
        except LiveRulesetUnavailable as exc:
            raise ReceiptBindingUnavailable(
                f"CODEOWNERS_BOOTSTRAP_LIVE_PROOF:{exc}") from exc
        except LiveRulesetError as exc:
            raise ReceiptBindingError(
                f"CODEOWNERS_BOOTSTRAP_LIVE_PROOF:{exc}") from exc


def _validate_provider_negative_canary(
    *,
    entries: list[dict],
    root: pathlib.Path,
    provider_raw_path: pathlib.Path,
    provider_merge_time_us: int,
    now_us: int | None = None,
    github_token: str | None = None,
    require_live_rule_suite: bool = False,
    require_live_ref: bool = False,
) -> None:
    canary_entries = [entry for entry in entries
                      if entry.get("role") == "PROVIDER_NEGATIVE_CANARY"]
    if len(canary_entries) != 1:
        raise ReceiptBindingError(
            f"PROVIDER_NEGATIVE_CANARY_ROLE_COUNT:{len(canary_entries)}")
    entry = canary_entries[0]
    if entry.get("path") != CANARY_PATH or entry.get("role_unique") is not True:
        raise ReceiptBindingError("PROVIDER_NEGATIVE_CANARY_PATH_OR_UNIQUENESS")
    canary = _loads_unique_json((root / CANARY_PATH).read_bytes(), "PROVIDER_NEGATIVE_CANARY")
    expected_fields = {
        "profile", "canary_kind", "provider", "repository", "repository_id",
        "ruleset_id", "ref", "operation", "result", "exit_code", "attempted_at_us",
        "actor_id", "actor_name", "before_sha", "after_sha", "rule_suite_id",
        "rule_suite_path", "rule_suite_sha256", "transcript_path", "transcript_sha256",
    }
    if set(canary) != expected_fields:
        raise ReceiptBindingError(
            f"PROVIDER_NEGATIVE_CANARY_FIELDS:{sorted(set(canary) ^ expected_fields)}")
    expected_constants = {
        "profile": "TRIAD-B00R-PROVIDER-NEGATIVE-CANARY-V1",
        "canary_kind": "PROVIDER_NEGATIVE_CANARY",
        "provider": "github",
        "repository": "TriadAgentic/TriadOrigin",
        "repository_id": REPOSITORY_ID,
        "ref": CANARY_REF,
        "operation": "DIRECT_PUSH",
        "result": "REJECTED_BY_RULESET",
    }
    if any(canary.get(key) != value for key, value in expected_constants.items()):
        raise ReceiptBindingError("PROVIDER_NEGATIVE_CANARY_IDENTITY_MISMATCH")
    exit_code = canary.get("exit_code")
    if not isinstance(exit_code, int) or isinstance(exit_code, bool) or exit_code == 0:
        raise ReceiptBindingError("PROVIDER_NEGATIVE_CANARY_EXIT_CODE_NOT_REJECTED")
    actor_id = canary.get("actor_id")
    actor_name = canary.get("actor_name")
    if (not isinstance(actor_id, int) or isinstance(actor_id, bool) or actor_id <= 0
            or not isinstance(actor_name, str)
            or re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", actor_name)
            is None):
        raise ReceiptBindingError("PROVIDER_NEGATIVE_CANARY_ACTOR_INVALID")
    before_sha = canary.get("before_sha")
    after_sha = canary.get("after_sha")
    if (not isinstance(before_sha, str) or re.fullmatch(r"[0-9a-f]{40}", before_sha) is None
            or not isinstance(after_sha, str) or re.fullmatch(r"[0-9a-f]{40}", after_sha) is None
            or before_sha == "0" * 40 or after_sha == "0" * 40 or before_sha == after_sha):
        raise ReceiptBindingError("PROVIDER_NEGATIVE_CANARY_COMMIT_IDENTITY_INVALID")

    raw = _loads_unique_json(provider_raw_path.read_bytes(), "MAIN_RULESET_RAW")
    ruleset_id = raw.get("id")
    if (not isinstance(ruleset_id, int) or isinstance(ruleset_id, bool) or ruleset_id <= 0
            or canary.get("ruleset_id") != ruleset_id):
        raise ReceiptBindingError("PROVIDER_NEGATIVE_CANARY_RULESET_IDENTITY_MISMATCH")
    ref_name = raw.get("conditions", {}).get("ref_name", {})
    includes = ref_name.get("include") if isinstance(ref_name, dict) else None
    if not isinstance(includes, list) or CANARY_REF not in includes:
        raise ReceiptBindingError("PROVIDER_NEGATIVE_CANARY_REF_NOT_RULESET_TARGET")
    try:
        ruleset_updated_us = governance._parse_provider_utc_us(raw.get("updated_at"))  # noqa: SLF001
    except governance.GovernanceError as exc:
        raise ReceiptBindingError(
            f"PROVIDER_NEGATIVE_CANARY_RULESET_TIME_INVALID:{exc}") from exc

    rule_suite_path = canary.get("rule_suite_path")
    rule_suite_sha = canary.get("rule_suite_sha256")
    if rule_suite_path != CANARY_RULE_SUITE_PATH:
        raise ReceiptBindingError("PROVIDER_NEGATIVE_CANARY_RULE_SUITE_PATH_NONCANONICAL")
    try:
        governance.assert_hex64(rule_suite_sha, "provider_negative_canary.rule_suite_sha256")
    except governance.GovernanceError as exc:
        raise ReceiptBindingError(str(exc)) from exc
    rule_suite_entries = [
        item for item in entries if item.get("role") == CANARY_RULE_SUITE_ROLE
    ]
    if (len(rule_suite_entries) != 1
            or rule_suite_entries[0].get("path") != CANARY_RULE_SUITE_PATH
            or rule_suite_entries[0].get("sha256") != rule_suite_sha
            or rule_suite_entries[0].get("role_unique") is not True):
        raise ReceiptBindingError("PROVIDER_NEGATIVE_CANARY_RULE_SUITE_NOT_CLOSED")
    rule_suite_bytes = (root / CANARY_RULE_SUITE_PATH).read_bytes()
    if sha256_hex(rule_suite_bytes) != rule_suite_sha:
        raise ReceiptBindingError("PROVIDER_NEGATIVE_CANARY_RULE_SUITE_DIGEST_MISMATCH")
    rule_suite = _loads_unique_json(rule_suite_bytes, "PROVIDER_NEGATIVE_CANARY_RULE_SUITE")
    suite_id = canary.get("rule_suite_id")
    if (not isinstance(suite_id, int) or isinstance(suite_id, bool) or suite_id <= 0
            or rule_suite.get("id") != suite_id
            or rule_suite.get("repository_id") != REPOSITORY_ID
            or rule_suite.get("repository_name") != "TriadOrigin"
            or rule_suite.get("ref") != CANARY_REF
            or rule_suite.get("actor_id") != actor_id
            or rule_suite.get("actor_name") != actor_name
            or rule_suite.get("before_sha") != before_sha
            or rule_suite.get("after_sha") != after_sha
            or rule_suite.get("result") != "fail"):
        raise ReceiptBindingError("PROVIDER_NEGATIVE_CANARY_RULE_SUITE_IDENTITY_MISMATCH")
    evaluations = rule_suite.get("rule_evaluations")
    matching_failures = [] if not isinstance(evaluations, list) else [
        evaluation for evaluation in evaluations
        if isinstance(evaluation, dict)
        and isinstance(evaluation.get("rule_source"), dict)
        and evaluation["rule_source"].get("type") == "ruleset"
        and evaluation["rule_source"].get("id") == ruleset_id
        and evaluation["rule_source"].get("name") == raw.get("name")
        and evaluation.get("enforcement") == "active"
        and evaluation.get("result") == "fail"
        and evaluation.get("rule_type") == "pull_request"
    ]
    if not matching_failures:
        raise ReceiptBindingError("PROVIDER_NEGATIVE_CANARY_ACTIVE_RULESET_FAILURE_ABSENT")
    try:
        suite_pushed_at_us = governance._parse_provider_utc_us(  # noqa: SLF001
            rule_suite.get("pushed_at"))
    except governance.GovernanceError as exc:
        raise ReceiptBindingError(
            f"PROVIDER_NEGATIVE_CANARY_RULE_SUITE_TIME_INVALID:{exc}") from exc
    attempted_at_us = canary.get("attempted_at_us")
    if (not isinstance(attempted_at_us, int) or isinstance(attempted_at_us, bool)
            or not ruleset_updated_us < suite_pushed_at_us < provider_merge_time_us
            or not ruleset_updated_us < attempted_at_us < provider_merge_time_us
            or abs(attempted_at_us - suite_pushed_at_us) > MAX_CANARY_TIME_SKEW_US):
        raise ReceiptBindingError("PROVIDER_NEGATIVE_CANARY_CHRONOLOGY_INVALID")

    transcript_path = canary.get("transcript_path")
    transcript_sha = canary.get("transcript_sha256")
    try:
        governance.assert_hex64(
            transcript_sha, "provider_negative_canary.transcript_sha256")
    except governance.GovernanceError as exc:
        raise ReceiptBindingError(str(exc)) from exc
    transcript_entries = [item for item in entries
                          if item.get("role") == CANARY_TRANSCRIPT_ROLE]
    if (len(transcript_entries) != 1 or transcript_path != CANARY_TRANSCRIPT_PATH
            or transcript_entries[0].get("path") != CANARY_TRANSCRIPT_PATH
            or transcript_entries[0].get("sha256") != transcript_sha
            or transcript_entries[0].get("role_unique") is not True):
        raise ReceiptBindingError("PROVIDER_NEGATIVE_CANARY_TRANSCRIPT_NOT_CLOSED")
    transcript_bytes = (root / CANARY_TRANSCRIPT_PATH).read_bytes()
    if sha256_hex(transcript_bytes) != transcript_sha or len(transcript_bytes) > 64 * 1024:
        raise ReceiptBindingError("PROVIDER_NEGATIVE_CANARY_TRANSCRIPT_DIGEST_OR_SIZE")
    try:
        transcript = transcript_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReceiptBindingError("PROVIDER_NEGATIVE_CANARY_TRANSCRIPT_NOT_UTF8") from exc
    required_markers = (
        f"TRIAD_CANARY_REF={CANARY_REF}",
        f"TRIAD_CANARY_BEFORE_SHA={before_sha}",
        f"TRIAD_CANARY_AFTER_SHA={after_sha}",
        f"TRIAD_CANARY_ACTOR={actor_name}",
        f"TRIAD_CANARY_EXIT_CODE={exit_code}",
        f"git push --porcelain origin {after_sha}:{CANARY_REF}",
        f"GH013: Repository rule violations found for {CANARY_REF}",
        "[remote rejected]",
        "push declined due to repository rule violations",
    )
    if any(marker not in transcript for marker in required_markers):
        raise ReceiptBindingError("PROVIDER_NEGATIVE_CANARY_TRANSCRIPT_RULESET_MARKERS_ABSENT")
    forbidden_failures = (
        "authentication failed", "could not resolve host", "repository not found",
        "permission denied (publickey)", "non-fast-forward", "fetch first",
    )
    if any(marker in transcript.lower() for marker in forbidden_failures):
        raise ReceiptBindingError("PROVIDER_NEGATIVE_CANARY_TRANSCRIPT_WRONG_FAILURE_CLASS")

    if require_live_rule_suite or require_live_ref:
        if now_us is None:
            raise ReceiptBindingError("PROVIDER_NEGATIVE_CANARY_LIVE_NOW_ABSENT")
        try:
            if require_live_rule_suite:
                fetch_and_match_rule_suite(
                    rule_suite_bytes, token=github_token, now_us=now_us)
            current_ref_sha = (
                fetch_canary_ref_sha(token=github_token, now_us=now_us)
                if require_live_ref else before_sha
            )
        except LiveRulesetUnavailable as exc:
            raise ReceiptBindingUnavailable(
                f"PROVIDER_NEGATIVE_CANARY_LIVE_PROOF:{exc}") from exc
        except LiveRulesetError as exc:
            raise ReceiptBindingError(
                f"PROVIDER_NEGATIVE_CANARY_LIVE_PROOF:{exc}") from exc
        if current_ref_sha != before_sha:
            raise ReceiptBindingError("PROVIDER_NEGATIVE_CANARY_REMOTE_REF_MOVED")


def validate_receipt_bindings(
    receipt: dict,
    *,
    receipt_path: pathlib.Path,
    manifest_path: pathlib.Path,
    git_root: pathlib.Path,
    expected_head: str,
    authority: AuthorityContext,
    governance_evidence_paths: tuple[pathlib.Path, pathlib.Path] | None = None,
    now_us: int | None = None,
    github_token: str | None = None,
    require_live_source_pr: bool = False,
    require_live_rule_suite: bool = False,
    require_live_canary_ref: bool = False,
    receipt_pr: int | None = None,
    require_live_receipt_head: bool = False,
    require_live_receipt_pr: bool = False,
) -> int:
    """Cross-bind authority, receipt, manifest preimages, and immutable Git objects."""
    if re.fullmatch(r"[0-9a-f]{40}", expected_head or "") is None:
        raise ReceiptBindingError("EXPECTED_HEAD_NOT_CANONICAL_SHA40")
    root = pathlib.Path(str(_git(git_root, "rev-parse", "--show-toplevel"))).resolve(strict=True)
    if root != git_root.resolve(strict=True):
        raise ReceiptBindingError("GIT_ROOT_MISMATCH")
    head = str(_git(root, "rev-parse", "HEAD"))
    if head != expected_head:
        raise ReceiptBindingError(f"EXPECTED_HEAD_MISMATCH:{head}")
    if str(_git(root, "status", "--porcelain=v1", "--untracked-files=all")):
        raise ReceiptBindingError("GIT_WORKTREE_NOT_CLEAN")

    payload = receipt["payload"]
    milestone = payload["milestone"]
    receipt_rel = _relative_inside(receipt_path, root, "RECEIPT")
    expected_receipt_rel = (
        CANONICAL_RECEIPT_PATH
        if milestone == governance.ROOT_MILESTONE
        else f"evidence/receipts/{milestone}.receipt.v3.json"
    )
    if receipt_rel != expected_receipt_rel:
        raise ReceiptBindingError(f"RECEIPT_PATH_NONCANONICAL:{receipt_rel}")
    manifest_rel = _relative_inside(manifest_path, root, "MANIFEST")
    expected_namespace = (
        f"{EVIDENCE_ROOT}/"
        if milestone == governance.ROOT_MILESTONE
        else f"evidence/{milestone}/"
    )
    if milestone == governance.ROOT_MILESTONE and manifest_rel != CANONICAL_MANIFEST_PATH:
        raise ReceiptBindingError(f"MANIFEST_PATH_NONCANONICAL:{manifest_rel}")
    if not manifest_rel.startswith(expected_namespace):
        raise ReceiptBindingError(f"MANIFEST_PATH_WRONG_MILESTONE:{manifest_rel}")

    receipt_bytes = receipt_path.read_bytes()
    if receipt_bytes != canonical_json(receipt):
        raise ReceiptBindingError("RECEIPT_BYTES_NOT_CANONICAL_BARE_JSON")
    for rel, disk in ((receipt_rel, receipt_bytes), (manifest_rel, manifest_path.read_bytes())):
        committed = _git(root, "show", f"{expected_head}:{rel}", text=False)
        if committed != disk:
            raise ReceiptBindingError(f"GIT_BLOB_WORKTREE_MISMATCH:{rel}")

    manifest_bytes = manifest_path.read_bytes()
    if sha256_hex(manifest_bytes) != payload["evidence_manifest_sha256"]:
        raise ReceiptBindingError("EVIDENCE_MANIFEST_RECEIPT_DIGEST_MISMATCH")
    manifest = _loads_unique_json(manifest_bytes, "EVIDENCE_MANIFEST")
    paths = payload["evidence_ids"]
    digests = payload["evidence_sha256s"]
    entries = manifest.get("entries", [])
    if ([entry.get("path") for entry in entries] != paths
            or [entry.get("sha256") for entry in entries] != digests):
        raise ReceiptBindingError("EVIDENCE_INDEX_MANIFEST_ORDER_MISMATCH")
    tracked = set(str(_git(root, "ls-tree", "-r", "--name-only", expected_head)).splitlines())
    namespace_prefix = expected_namespace
    outside_namespace = sorted(item for item in paths if not item.startswith(namespace_prefix))
    if outside_namespace:
        raise ReceiptBindingError(f"EVIDENCE_ID_OUTSIDE_MILESTONE_NAMESPACE:{outside_namespace}")
    namespace_inventory = {item for item in tracked if item.startswith(namespace_prefix)}
    declared_namespace = {item for item in paths if item.startswith(namespace_prefix)}
    if manifest_rel in paths:
        raise ReceiptBindingError("EVIDENCE_MANIFEST_SELF_REFERENCE_FORBIDDEN")
    if manifest_rel not in namespace_inventory:
        raise ReceiptBindingError("EVIDENCE_MANIFEST_NOT_TRACKED_IN_NAMESPACE")
    # The manifest cannot list itself, so compare the remainder of the committed milestone
    # namespace exactly.  No tracked file may hide beside the receipt's closed evidence inventory.
    if namespace_inventory - {manifest_rel} != declared_namespace:
        missing = sorted(declared_namespace - namespace_inventory)
        extra = sorted((namespace_inventory - {manifest_rel}) - declared_namespace)
        raise ReceiptBindingError(
            f"EVIDENCE_NAMESPACE_NOT_CLOSED:missing={missing}:extra={extra}")
    try:
        governance.validate_evidence_manifest(
            manifest, root, expected_paths=set(paths), tracked_paths=tracked,
            allowed_empty_paths=(
                ALLOWED_EMPTY_PATHS
                if milestone == governance.ROOT_MILESTONE
                else frozenset()
            ))
    except governance.GovernanceError as exc:
        raise ReceiptBindingError(str(exc)) from exc

    if milestone == governance.ROOT_MILESTONE:
        _validate_tag_ruleset_manifest_entry(entries)
        try:
            validate_clean_runner_bundle(
                root, entries, payload, expected_head, now_us=now_us)
        except CleanRunnerError as exc:
            raise ReceiptBindingError(f"CLEAN_RUNNER_BUNDLE_INVALID:{exc}") from exc

    _validate_receipt_digest_roles(
        entries, payload,
        require_explicit_unique=(milestone == governance.ROOT_MILESTONE))

    source_merge = payload["source_merge_sha"]
    source_merge_time_us = payload["source_merge_time_us"]
    provider_merge_time_us = source_merge_time_us
    if milestone == governance.ROOT_MILESTONE:
        if governance_evidence_paths is None:
            raise ReceiptBindingError("PROVIDER_NEGATIVE_CANARY_GOVERNANCE_EVIDENCE_ABSENT")
        provider_merge_time_us = _validate_source_pr_provider_record(
            entries=entries, root=root, payload=payload, now_us=now_us,
            github_token=github_token, require_live_provider=require_live_source_pr)
        _validate_source_pr_approved_review(
            entries=entries,
            root=root,
            payload=payload,
            provider_merge_time_us=provider_merge_time_us,
            now_us=now_us,
            github_token=github_token,
            require_live_provider=require_live_source_pr,
        )
        _validate_provider_negative_canary(
            entries=entries,
            root=root,
            provider_raw_path=governance_evidence_paths[1],
            provider_merge_time_us=provider_merge_time_us,
            now_us=now_us,
            github_token=github_token,
            require_live_rule_suite=require_live_rule_suite,
            require_live_ref=require_live_canary_ref,
        )
    for name, decision in authority.decisions.items():
        effective_at_us = decision.get("effective_at_us")
        if (not isinstance(effective_at_us, int) or isinstance(effective_at_us, bool)
                or effective_at_us <= 0 or effective_at_us > provider_merge_time_us):
            raise ReceiptBindingError(f"AUTHORITY_DECISION_NOT_EFFECTIVE_BEFORE_SOURCE_MERGE:{name}")
    if str(_git(root, "cat-file", "-t", source_merge)) != "commit":
        raise ReceiptBindingError("SOURCE_MERGE_NOT_COMMIT")
    parent_row = str(_git(root, "rev-list", "--parents", "-n", "1", source_merge)).split()
    final_source = payload["final_source_head"]
    if len(parent_row) != 3 or parent_row[0] != source_merge:
        raise ReceiptBindingError("SOURCE_MERGE_NOT_EXACT_TWO_PARENT_MERGE")
    base_parent, source_parent = parent_row[1:]
    if source_parent != final_source:
        raise ReceiptBindingError("SOURCE_MERGE_SECOND_PARENT_NOT_FINAL_SOURCE_HEAD")
    # GitHub evaluates CODEOWNERS from the PR base.  Requiring the first parent to contain the
    # exact reviewed file prevents the corrective PR from self-bootstrapping its own owner rule.
    codeowners_rel = ".github/CODEOWNERS"
    codeowners_disk = (root / codeowners_rel).read_bytes()
    if _git(root, "show", f"{base_parent}:{codeowners_rel}", text=False) != codeowners_disk:
        raise ReceiptBindingError("SOURCE_PR_BASE_CODEOWNERS_NOT_BOOTSTRAPPED")
    if authority.paths:
        try:
            validate_git_bound_authority(
                authority, git_root=root, expected_head=expected_head, object_head=source_merge)
        except AuthorityRootError as exc:
            raise ReceiptBindingError(f"AUTHORITY_GIT_BINDING_INVALID:{exc}") from exc
    source_tree = str(_git(root, "rev-parse", f"{source_merge}^{{tree}}"))
    if source_tree != payload["source_merge_tree"]:
        raise ReceiptBindingError("SOURCE_MERGE_TREE_MISMATCH")
    source_time_s = int(str(_git(root, "show", "-s", "--format=%ct", source_merge)))
    if payload["source_merge_time_us"] != source_time_s * 1_000_000:
        raise ReceiptBindingError("SOURCE_MERGE_TIME_MISMATCH")
    if provider_merge_time_us != payload["source_merge_time_us"]:
        raise ReceiptBindingError("SOURCE_PR_PROVIDER_GIT_TIME_MISMATCH")
    if str(_git(root, "rev-parse", f"{final_source}^{{tree}}")) != source_tree:
        raise ReceiptBindingError("FINAL_SOURCE_HEAD_TREE_MISMATCH")
    _git(root, "merge-base", "--is-ancestor", final_source, source_merge)
    if _git(root, "merge-base", "--is-ancestor", source_merge, expected_head) != "":
        raise ReceiptBindingError("SOURCE_MERGE_NOT_ANCESTOR")  # pragma: no cover
    if governance_evidence_paths is not None:
        # These are source-phase controls, not receipt-manifest entries.  Bind their exact bytes
        # independently at both the declared source merge and receipt head, proving the receipt PR
        # did not rewrite the pinned governance evidence.
        for evidence_path in governance_evidence_paths:
            rel = _relative_inside(evidence_path, root, "GOVERNANCE_EVIDENCE")
            disk = evidence_path.read_bytes()
            source_blob = _git(root, "show", f"{source_merge}:{rel}", text=False)
            head_blob = _git(root, "show", f"{expected_head}:{rel}", text=False)
            if source_blob != disk or head_blob != disk:
                raise ReceiptBindingError(f"GOVERNANCE_EVIDENCE_GIT_BLOB_MISMATCH:{rel}")

    if milestone == governance.ROOT_MILESTONE:
        _validate_codeowners_bootstrap(
            entries=entries,
            root=root,
            payload=payload,
            source_base_parent=base_parent,
            source_provider_merge_time_us=provider_merge_time_us,
            now_us=now_us,
            github_token=github_token,
            require_live_provider=require_live_source_pr,
        )

    if milestone == governance.ROOT_MILESTONE:
        repair = authority.decisions["b00_repair"]
        if payload["repair_decision_sha256"] != authority.digests["b00_repair"]:
            raise ReceiptBindingError("REPAIR_DECISION_AUTHORITY_DIGEST_MISMATCH")
        subjects = repair["subject_sha256s"]
        if payload["invalidation_manifest_sha256"] != subjects["generation_ledger"]:
            raise ReceiptBindingError("INVALIDATION_MANIFEST_AUTHORITY_DIGEST_MISMATCH")
        if payload["audited_start_sha"] != subjects["audited_start_sha"]:
            raise ReceiptBindingError("AUDITED_START_AUTHORITY_MISMATCH")
        _git(root, "merge-base", "--is-ancestor", payload["audited_start_sha"], source_merge)

    changed = set(str(_git(root, "diff", "--name-only", source_merge, expected_head)).splitlines())
    if receipt_rel not in changed or manifest_rel not in changed:
        raise ReceiptBindingError("RECEIPT_OR_MANIFEST_NOT_POST_SOURCE_MERGE")
    escaped = sorted(path for path in changed
                     if path != receipt_rel and not path.startswith(namespace_prefix))
    if escaped:
        raise ReceiptBindingError(f"POST_SOURCE_MERGE_SOURCE_DRIFT:{escaped}")
    if require_live_receipt_head and require_live_receipt_pr:
        raise ReceiptBindingError("RECEIPT_PROVIDER_PROOF_MODES_CONFLICT")
    if require_live_receipt_head:
        if (not isinstance(receipt_pr, int) or isinstance(receipt_pr, bool)
                or receipt_pr <= 0):
            raise ReceiptBindingError("RECEIPT_PR_NUMBER_ABSENT_OR_INVALID")
        if now_us is None:
            raise ReceiptBindingError("RECEIPT_PR_LIVE_NOW_ABSENT")
        try:
            receipt_head_proof = fetch_and_verify_receipt_head(
                receipt_pr,
                expected_head_sha=expected_head,
                expected_base_sha=source_merge,
                expected_codeowner="djordi10",
                token=github_token,
                now_us=now_us,
            )
        except LiveRulesetUnavailable as exc:
            raise ReceiptBindingUnavailable(
                f"RECEIPT_PR_PREMERGE_LIVE_PROOF:{exc}") from exc
        except LiveRulesetError as exc:
            raise ReceiptBindingError(
                f"RECEIPT_PR_PREMERGE_LIVE_PROOF:{exc}") from exc
        if (receipt_head_proof.head_sha != expected_head
                or receipt_head_proof.base_sha != source_merge):
            raise ReceiptBindingError("RECEIPT_PR_PREMERGE_IDENTITY_MISMATCH")
    if require_live_receipt_pr:
        if (not isinstance(receipt_pr, int) or isinstance(receipt_pr, bool)
                or receipt_pr <= 0):
            raise ReceiptBindingError("RECEIPT_PR_NUMBER_ABSENT_OR_INVALID")
        if now_us is None:
            raise ReceiptBindingError("RECEIPT_PR_LIVE_NOW_ABSENT")
        try:
            receipt_proof = fetch_and_verify_receipt_merge(
                receipt_pr,
                expected_merge_sha=expected_head,
                expected_codeowner="djordi10",
                token=github_token,
                now_us=now_us,
            )
        except LiveRulesetUnavailable as exc:
            raise ReceiptBindingUnavailable(f"RECEIPT_PR_LIVE_PROOF:{exc}") from exc
        except LiveRulesetError as exc:
            raise ReceiptBindingError(f"RECEIPT_PR_LIVE_PROOF:{exc}") from exc
        receipt_parent_row = str(
            _git(root, "rev-list", "--parents", "-n", "1", expected_head)).split()
        if (len(receipt_parent_row) != 3 or receipt_parent_row[0] != expected_head
                or receipt_parent_row[1] != source_merge
                or receipt_parent_row[2] != receipt_proof.head_sha):
            raise ReceiptBindingError("RECEIPT_MERGE_NOT_EXACT_TWO_PARENT_PR_MERGE")
        if str(_git(root, "rev-parse", f"{receipt_proof.head_sha}^{{tree}}")) != str(
                _git(root, "rev-parse", f"{expected_head}^{{tree}}")):
            raise ReceiptBindingError("RECEIPT_PR_HEAD_TREE_MISMATCH")
        receipt_git_time_us = int(str(
            _git(root, "show", "-s", "--format=%ct", expected_head))) * 1_000_000
        if receipt_proof.merged_at_us != receipt_git_time_us:
            raise ReceiptBindingError("RECEIPT_PR_PROVIDER_GIT_TIME_MISMATCH")
        if receipt_proof.merged_at_us <= provider_merge_time_us:
            raise ReceiptBindingError("RECEIPT_PR_NOT_AFTER_SOURCE_MERGE")
    return provider_merge_time_us


def _validate_governance_evidence(
    *,
    snapshot_path: pathlib.Path,
    provider_raw_path: pathlib.Path,
    provider_pin: str | None,
    git_root: pathlib.Path,
    now_us: int,
    source_merge_time_us: int,
    require_bypass_visibility: bool,
) -> None:
    """Authenticate raw ruleset facts and prove the controls predate the source merge."""
    try:
        snapshot = _loads_unique_json(snapshot_path.read_bytes(), "GOVERNANCE_SNAPSHOT")
        raw_bytes = provider_raw_path.read_bytes()
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReceiptBindingError(f"GOVERNANCE_EVIDENCE_UNREADABLE:{exc}") from exc
    root = git_root.resolve(strict=True)
    snapshot_rel = _relative_inside(snapshot_path, root, "GOVERNANCE_SNAPSHOT")
    raw_rel = _relative_inside(provider_raw_path, root, "PROVIDER_RAW")
    if snapshot_rel != "docs/governance/rulesets/main.ruleset.provider.json" \
            or raw_rel != "docs/governance/rulesets/main.ruleset.provider.raw.json":
        raise ReceiptBindingError("GOVERNANCE_EVIDENCE_PATH_NONCANONICAL")
    if snapshot.get("provider", {}).get("api_response_path") != raw_rel:
        raise ReceiptBindingError("GOVERNANCE_PROVIDER_RESPONSE_PATH_MISMATCH")
    result, reason = governance.validate_governance_snapshot(
        snapshot, provider_raw_bytes=raw_bytes, external_pin=provider_pin,
        now_us=now_us, source_merge_time_us=source_merge_time_us)
    if result != "PASS":
        raise ReceiptBindingError(f"GOVERNANCE_SNAPSHOT_{result}:{reason}")
    try:
        fetch_and_match_live_ruleset(
            raw_bytes, token=os.environ.get("GITHUB_TOKEN"), now_us=now_us,
            require_bypass_visibility=require_bypass_visibility)
    except LiveRulesetUnavailable as exc:
        raise ReceiptBindingUnavailable(f"LIVE_PROVIDER_REVALIDATION:{exc}") from exc
    except LiveRulesetError as exc:
        raise ReceiptBindingError(f"LIVE_PROVIDER_REVALIDATION:{exc}") from exc


def _strict(
    path: pathlib.Path,
    *,
    milestone: str,
    now_us: int,
    pins_path: pathlib.Path | None,
    manifest_path: pathlib.Path,
    git_root: pathlib.Path,
    expected_head: str,
    governance_snapshot_path: pathlib.Path,
    provider_raw_path: pathlib.Path,
    provider_pin: str | None,
    require_bypass_visibility: bool,
    require_live_rule_suite: bool,
    require_live_canary_ref: bool,
    provider_proof_mode: str,
    receipt_pr: int | None,
) -> int:
    try:
        raw = path.read_bytes()
        receipt = loads_canonical(raw)
    except (OSError, CanonicalError) as exc:
        print(f"FAIL: receipt must be exact canonical bare JSON: {exc}", file=sys.stderr)
        return 1
    if not isinstance(receipt, dict):
        print("FAIL: receipt JSON root is not an object", file=sys.stderr)
        return 1
    try:
        authority = load_authority_context(
            now_us=now_us,
            pins_path=pins_path,
            repair_generation=2,
        )
    except AuthorityRootUnavailable as exc:
        print(f"BLOCKED: UNAVAILABLE_AUTHORITY_ROOT:{exc}")
        return 1
    except AuthorityRootError as exc:
        print(f"FAIL: AUTHORITY_ROOT_INVALID:{exc}", file=sys.stderr)
        return 1
    result, reason = governance.validate_receipt_v3(
        receipt, milestone=milestone, trust=authority.trust,
        threshold=authority.receipt_threshold, required_roles=authority.receipt_roles,
        now_us=now_us, verify_fn=ed25519_verify, expected_root_generation=2)
    if result != governance.RESULT_PASS:
        stream = sys.stderr if result == "FAIL" else sys.stdout
        print(f"{result}: {milestone} receipt-v3 not a closure PASS: {reason}", file=stream)
        return 1
    try:
        provider_merge_time_us = validate_receipt_bindings(
            receipt, receipt_path=path, manifest_path=manifest_path, git_root=git_root,
            expected_head=expected_head, authority=authority,
            governance_evidence_paths=(governance_snapshot_path, provider_raw_path),
            now_us=now_us, github_token=os.environ.get("GITHUB_TOKEN"),
            require_live_source_pr=True,
            require_live_rule_suite=require_live_rule_suite,
            require_live_canary_ref=require_live_canary_ref,
            receipt_pr=receipt_pr,
            require_live_receipt_pr=(
                milestone == governance.ROOT_MILESTONE
                and provider_proof_mode == "terminal"),
            require_live_receipt_head=(
                milestone == governance.ROOT_MILESTONE
                and provider_proof_mode == "premerge"))
        _validate_governance_evidence(
            snapshot_path=governance_snapshot_path, provider_raw_path=provider_raw_path,
            provider_pin=provider_pin, git_root=git_root, now_us=now_us,
            source_merge_time_us=provider_merge_time_us,
            require_bypass_visibility=require_bypass_visibility)
    except ReceiptBindingUnavailable as exc:
        print(f"BLOCKED: UNAVAILABLE_RECEIPT_BINDING:{exc}")
        return 1
    except (OSError, ValueError, ReceiptBindingError) as exc:
        print(f"FAIL: RECEIPT_BINDING_INVALID:{exc}", file=sys.stderr)
        return 1
    if provider_proof_mode == "nonterminal":
        print(
            f"OK_NONTERMINAL: {milestone} receipt-v3 {result}; static canary, authority, "
            "manifest, and Git bound, but privileged rule-suite/ref/bypass proof was not run; "
            "this cannot close B00R"
        )
    elif provider_proof_mode == "premerge":
        print(
            f"OK_PREMERGE: {milestone} receipt-v3 {result}; authority, manifest, Git, live "
            "source/review, rule-suite, unchanged canary ref, and visible empty bypass state "
            "bound, but the receipt merge does not yet exist; this cannot close B00R"
        )
    else:
        print(
            f"OK: {milestone} canonical receipt-v3 {result}; authority, manifest, Git, "
            "live rule-suite, unchanged canary ref, and visible empty bypass state bound"
        )
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Validate a milestone receipt.")
    parser.add_argument("receipt", type=pathlib.Path)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--milestone")
    parser.add_argument("--pins", type=pathlib.Path,
                        help="out-of-repository JSON containing all four authority pins")
    parser.add_argument("--now-us", type=int)
    parser.add_argument("--manifest", type=pathlib.Path)
    parser.add_argument("--git-root", type=pathlib.Path, default=ROOT)
    parser.add_argument("--expected-head")
    parser.add_argument("--governance-snapshot", type=pathlib.Path)
    parser.add_argument("--provider-raw", type=pathlib.Path)
    parser.add_argument("--provider-pin",
                        help="external SHA-256 pin (or protected MAIN_RULESET_EVIDENCE_SHA256)")
    parser.add_argument(
        "--require-bypass-visibility", action="store_true",
        help="terminal mode: live token must expose the provider bypass_actors field")
    parser.add_argument(
        "--nonterminal-provider-proof", action="store_true",
        help="CI-only: skip privileged rule-suite/ref/bypass reads and never claim closure")
    parser.add_argument(
        "--premerge-provider-proof", action="store_true",
        help=(
            "privileged receipt-head preflight: require live rule-suite/ref/bypass proof but "
            "do not require the not-yet-existing receipt merge; never claim closure"
        ))
    parser.add_argument(
        "--receipt-pr", type=int,
        help=(
            "premerge/terminal B00R GitHub receipt PR number bound to the exact receipt head"
        ))
    args = parser.parse_args(argv)
    if not args.strict:
        return _legacy(args.receipt)
    missing = [name for name, value in (
        ("--milestone", args.milestone), ("--now-us", args.now_us),
        ("--manifest", args.manifest), ("--expected-head", args.expected_head)) if value is None]
    missing.extend(name for name, value in (
        ("--governance-snapshot", args.governance_snapshot),
        ("--provider-raw", args.provider_raw)) if value is None)
    if missing:
        print(f"FAIL: --strict requires {', '.join(missing)}", file=sys.stderr)
        return 2
    env_provider_pin = os.environ.get("MAIN_RULESET_EVIDENCE_SHA256")
    if args.provider_pin and env_provider_pin and args.provider_pin != env_provider_pin:
        print("FAIL: conflicting CLI and protected-environment provider pins", file=sys.stderr)
        return 2
    provider_pin = env_provider_pin or args.provider_pin
    if provider_pin is None:
        print("FAIL: --strict requires --provider-pin or MAIN_RULESET_EVIDENCE_SHA256",
              file=sys.stderr)
        return 2
    if args.nonterminal_provider_proof and args.premerge_provider_proof:
        print("FAIL: nonterminal and premerge provider modes are mutually exclusive",
              file=sys.stderr)
        return 2
    if args.nonterminal_provider_proof and args.require_bypass_visibility:
        print("FAIL: nonterminal provider mode conflicts with terminal bypass visibility",
              file=sys.stderr)
        return 2
    if args.nonterminal_provider_proof and args.receipt_pr is not None:
        print("FAIL: nonterminal provider mode does not accept --receipt-pr", file=sys.stderr)
        return 2
    if args.premerge_provider_proof and args.milestone != governance.ROOT_MILESTONE:
        print("FAIL: premerge provider mode is defined only for B00R", file=sys.stderr)
        return 2
    provider_proof_mode = (
        "nonterminal" if args.nonterminal_provider_proof
        else "premerge" if args.premerge_provider_proof
        else "terminal"
    )
    if (
        args.milestone == governance.ROOT_MILESTONE
        and provider_proof_mode in {"premerge", "terminal"}
        and (args.receipt_pr is None or args.receipt_pr <= 0)
    ):
        print(
            f"FAIL: {provider_proof_mode} B00R strict mode requires a positive --receipt-pr",
            file=sys.stderr,
        )
        return 2
    privileged_provider_proof = provider_proof_mode in {"premerge", "terminal"}
    return _strict(
        args.receipt, milestone=args.milestone, now_us=args.now_us, pins_path=args.pins,
        manifest_path=args.manifest, git_root=args.git_root, expected_head=args.expected_head,
        governance_snapshot_path=args.governance_snapshot,
        provider_raw_path=args.provider_raw, provider_pin=provider_pin,
        require_bypass_visibility=(
            args.require_bypass_visibility or privileged_provider_proof),
        require_live_rule_suite=privileged_provider_proof,
        require_live_canary_ref=privileged_provider_proof,
        provider_proof_mode=provider_proof_mode,
        receipt_pr=args.receipt_pr)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
