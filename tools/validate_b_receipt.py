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
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import contracts, governance  # noqa: E402
from triad_origin.canonical import (  # noqa: E402
    CanonicalError, canonical_json, loads_canonical, sha256_hex)
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
        LiveRulesetError, fetch_and_match_live_ruleset)
except ModuleNotFoundError:  # pragma: no cover - direct script fallback
    from github_ruleset_live import (  # type: ignore  # noqa: E402
        LiveRulesetError, fetch_and_match_live_ruleset)


class ReceiptBindingError(ValueError):
    """Receipt bytes do not bind to the declared manifest or Git graph."""


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


def validate_receipt_bindings(
    receipt: dict,
    *,
    receipt_path: pathlib.Path,
    manifest_path: pathlib.Path,
    git_root: pathlib.Path,
    expected_head: str,
    authority: AuthorityContext,
    governance_evidence_paths: tuple[pathlib.Path, pathlib.Path] | None = None,
) -> None:
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
    expected_receipt_rel = f"evidence/receipts/{milestone}.receipt.v3.json"
    if receipt_rel != expected_receipt_rel:
        raise ReceiptBindingError(f"RECEIPT_PATH_NONCANONICAL:{receipt_rel}")
    manifest_rel = _relative_inside(manifest_path, root, "MANIFEST")
    if not manifest_rel.startswith(f"evidence/{milestone}/"):
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
    namespace_prefix = f"evidence/{milestone}/"
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
            manifest, root, expected_paths=set(paths), tracked_paths=tracked)
    except governance.GovernanceError as exc:
        raise ReceiptBindingError(str(exc)) from exc

    role_fields = {
        "WORKFLOW": "workflow_sha256",
        "CONTRACT_MANIFEST": "contract_manifest_sha256",
        "TEST_MANIFEST": "test_manifest_sha256",
        "CONFIG_BUNDLE": "config_bundle_sha256",
        "ROLLBACK_PROOF": "rollback_proof_sha256",
    }
    by_role = {entry.get("role"): entry.get("sha256") for entry in entries}
    for role, field in role_fields.items():
        if by_role.get(role) != payload[field]:
            raise ReceiptBindingError(f"EVIDENCE_ROLE_DIGEST_MISMATCH:{role}")

    source_merge = payload["source_merge_sha"]
    source_merge_time_us = payload["source_merge_time_us"]
    for name, decision in authority.decisions.items():
        effective_at_us = decision.get("effective_at_us")
        if (not isinstance(effective_at_us, int) or isinstance(effective_at_us, bool)
                or effective_at_us <= 0 or effective_at_us > source_merge_time_us):
            raise ReceiptBindingError(f"AUTHORITY_DECISION_NOT_EFFECTIVE_BEFORE_SOURCE_MERGE:{name}")
    if str(_git(root, "cat-file", "-t", source_merge)) != "commit":
        raise ReceiptBindingError("SOURCE_MERGE_NOT_COMMIT")
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
    final_source = payload["final_source_head"]
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
        repair = authority.decisions["b00_repair"]
        if payload["repair_decision_sha256"] != authority.digests["b00_repair"]:
            raise ReceiptBindingError("REPAIR_DECISION_AUTHORITY_DIGEST_MISMATCH")
        subjects = repair["subject_sha256s"]
        if payload["invalidation_manifest_sha256"] != subjects["invalidation_manifest"]:
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


def _validate_governance_evidence(
    *,
    snapshot_path: pathlib.Path,
    provider_raw_path: pathlib.Path,
    provider_pin: str | None,
    git_root: pathlib.Path,
    now_us: int,
    source_merge_time_us: int,
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
            require_bypass_visibility=True)
    except LiveRulesetError as exc:
        detail = str(exc)
        unavailable = (
            detail == "GITHUB_TOKEN_ABSENT"
            or detail.startswith("LIVE_RULESET_FETCH_FAILED:")
            or detail.startswith("LIVE_RULESET_HTTP_STATUS:")
        )
        prefix = "UNAVAILABLE_" if unavailable else ""
        raise ReceiptBindingError(
            f"{prefix}LIVE_PROVIDER_REVALIDATION:{detail}") from exc


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
        authority = load_authority_context(now_us=now_us, pins_path=pins_path)
    except AuthorityRootUnavailable as exc:
        print(f"BLOCKED: UNAVAILABLE_AUTHORITY_ROOT:{exc}")
        return 1
    except AuthorityRootError as exc:
        print(f"FAIL: AUTHORITY_ROOT_INVALID:{exc}", file=sys.stderr)
        return 1
    result, reason = governance.validate_receipt_v3(
        receipt, milestone=milestone, trust=authority.trust,
        threshold=authority.receipt_threshold, required_roles=authority.receipt_roles,
        now_us=now_us, verify_fn=ed25519_verify)
    if result != governance.RESULT_PASS:
        stream = sys.stderr if result == "FAIL" else sys.stdout
        print(f"{result}: {milestone} receipt-v3 not a closure PASS: {reason}", file=stream)
        return 1
    try:
        _validate_governance_evidence(
            snapshot_path=governance_snapshot_path, provider_raw_path=provider_raw_path,
            provider_pin=provider_pin, git_root=git_root, now_us=now_us,
            source_merge_time_us=receipt["payload"]["source_merge_time_us"])
        validate_receipt_bindings(
            receipt, receipt_path=path, manifest_path=manifest_path, git_root=git_root,
            expected_head=expected_head, authority=authority,
            governance_evidence_paths=(governance_snapshot_path, provider_raw_path))
    except (OSError, ValueError, ReceiptBindingError) as exc:
        print(f"FAIL: RECEIPT_BINDING_INVALID:{exc}", file=sys.stderr)
        return 1
    print(f"OK: {milestone} canonical receipt-v3 {result}; authority, manifest, and Git bound")
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
    return _strict(
        args.receipt, milestone=args.milestone, now_us=args.now_us, pins_path=args.pins,
        manifest_path=args.manifest, git_root=args.git_root, expected_head=args.expected_head,
        governance_snapshot_path=args.governance_snapshot,
        provider_raw_path=args.provider_raw, provider_pin=provider_pin)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
