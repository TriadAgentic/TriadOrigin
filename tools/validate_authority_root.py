#!/usr/bin/env python3
"""Cryptographically verify the externally pinned B00R authority root.

Pins are public SHA-256 values supplied by protected environment variables or an out-of-tree JSON
file.  Repository bytes may never bootstrap their own authority.  Decisions are Ed25519 verified
over ``governance.canonical_decision_signing_bytes`` under an AUTHORITY_OWNER key in the pinned
registry; an ``authenticated`` boolean alone has no authority.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
from typing import Mapping

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from triad_origin import governance  # noqa: E402

GOV = ROOT / "docs" / "governance"
TRUST_REL = "docs/governance/trust/receipt_trust_registry.v1.json"
TRUST_REL_G2 = "docs/governance/trust/receipt_trust_registry.g2.v1.json"
AUTHORITY_SUBJECT_PATHS = {
    "RC2_complete_checklist":
        "docs/spec_rc2/01_TRIAD_ORIGIN_V7_COMPLETE_IMPLEMENTATION_CHECKLIST_1.0.0_RC2.html",
    "RC2_master_workbook":
        "docs/spec_rc2/TRIAD_ORIGIN_V7_IMPLEMENTATION_CONTROL_WORKBOOK_1.0.0_RC2.xlsx",
    "RC2_wiring_guide":
        "docs/spec_rc2/02_TRIAD_ORIGIN_V7_WIRING_FORMULA_AND_PLUMBING_GUIDE_1.0.0_RC2.html",
    "RC3_master_document":
        "docs/spec_rc3/TRIAD_ORIGIN_V7_COMPLETE_MASTER_SPECIFICATION_AND_MASTER_DOCUMENT_1.0.0_RC3.html",
    "RC4_master_addendum":
        "docs/spec_rc4/TRIAD_ORIGIN_V7_FOUR_PLANE_EXECUTION_AND_LEVER_MASTER_ADDENDUM_1.0.0_RC4.html",
    "rc3_effective_control_bundle": "docs/control/rc3_effective_control_bundle.json",
    "rc4_control_bundle": "docs/control/rc4_control_bundle.json",
}
PROFILE_SUBJECT_PATHS = {
    "evidence_manifest_schema": "contracts/schemas/triad.evidence_manifest.v1.schema.json",
    "evidence_receipt_v3_schema": "contracts/schemas/triad.evidence_receipt.v3.schema.json",
    "trust_registry_schema": "contracts/schemas/triad.receipt_trust_registry.v1.schema.json",
}
CANONICAL_AUTHORITY_PATHS = {
    "authority_bundle": "docs/governance/decisions/DEC-AUTHORITY-BUNDLE-001.json",
    "receipt_profile": "docs/governance/decisions/DEC-RECEIPT-PROFILE-001.json",
    "b00_repair": "docs/governance/decisions/DEC-B00-REPAIR-001.json",
    "trust_registry": "docs/governance/trust/receipt_trust_registry.v1.json",
}
GENERATION_2_AUTHORITY_PATHS = {
    "authority_bundle": "docs/governance/decisions/DEC-AUTHORITY-BUNDLE-002.json",
    "receipt_profile": "docs/governance/decisions/DEC-RECEIPT-PROFILE-002.json",
    "b00_repair": "docs/governance/decisions/DEC-B00-REPAIR-002.json",
    "trust_registry": TRUST_REL_G2,
}
CRYPTOGRAPHY_VERSION = "50.0.0"

# name -> (external pin name, expected decision id or None, authenticated file, template)
SUBJECTS = {
    "authority_bundle": (
        "AUTHORITY_BUNDLE_DECISION_SHA256", "DEC-AUTHORITY-BUNDLE-001",
        GOV / "decisions" / "DEC-AUTHORITY-BUNDLE-001.json",
        GOV / "decisions" / "DEC-AUTHORITY-BUNDLE-001.template.json"),
    "receipt_profile": (
        "RECEIPT_PROFILE_DECISION_SHA256", "DEC-RECEIPT-PROFILE-001",
        GOV / "decisions" / "DEC-RECEIPT-PROFILE-001.json",
        GOV / "decisions" / "DEC-RECEIPT-PROFILE-001.template.json"),
    "b00_repair": (
        "B00_REPAIR_DECISION_SHA256", "DEC-B00-REPAIR-001",
        GOV / "decisions" / "DEC-B00-REPAIR-001.json",
        GOV / "decisions" / "DEC-B00-REPAIR-001.template.json"),
    "trust_registry": (
        "RECEIPT_TRUST_REGISTRY_SHA256", None,
        GOV / "trust" / "receipt_trust_registry.v1.json",
        GOV / "trust" / "receipt_trust_registry.v1.template.json"),
}
GENERATION_2_SUBJECTS = {
    "authority_bundle": (
        "AUTHORITY_BUNDLE_G2_DECISION_SHA256", "DEC-AUTHORITY-BUNDLE-002",
        GOV / "decisions" / "DEC-AUTHORITY-BUNDLE-002.json",
        GOV / "decisions" / "DEC-AUTHORITY-BUNDLE-002.template.json"),
    "receipt_profile": (
        "RECEIPT_PROFILE_G2_DECISION_SHA256", "DEC-RECEIPT-PROFILE-002",
        GOV / "decisions" / "DEC-RECEIPT-PROFILE-002.json",
        GOV / "decisions" / "DEC-RECEIPT-PROFILE-002.template.json"),
    "b00_repair": (
        "B00R_G2_REPAIR_DECISION_SHA256", "DEC-B00-REPAIR-002",
        GOV / "decisions" / "DEC-B00-REPAIR-002.json",
        GOV / "decisions" / "DEC-B00-REPAIR-002.template.json"),
    "trust_registry": (
        "RECEIPT_G2_TRUST_REGISTRY_SHA256", None,
        GOV / "trust" / "receipt_trust_registry.g2.v1.json",
        GOV / "trust" / "receipt_trust_registry.g2.v1.template.json"),
}


def _authority_profile(repair_generation: int):
    if repair_generation == 1:
        return SUBJECTS, CANONICAL_AUTHORITY_PATHS
    if repair_generation == 2:
        return GENERATION_2_SUBJECTS, GENERATION_2_AUTHORITY_PATHS
    raise AuthorityRootError(f"REPAIR_GENERATION_UNSUPPORTED:{repair_generation}")


class AuthorityRootError(ValueError):
    """The supplied root is contradictory, malformed, or cryptographically invalid."""


class AuthorityRootUnavailable(AuthorityRootError):
    """An external owner input required to construct the authority root is absent."""


@dataclass(frozen=True)
class AuthorityContext:
    trust: dict[str, dict]
    decisions: dict[str, dict]
    digests: dict[str, str]
    receipt_threshold: int
    receipt_roles: tuple[str, ...]
    receipt_algorithm: str
    repair_generation: int = 2
    paths: dict[str, pathlib.Path] = field(default_factory=dict)


def ed25519_verify(public_key_hex: str, message: bytes, signature_hex: str) -> bool:
    """Verify one Ed25519 signature with the single pinned validation backend."""
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
        key.verify(bytes.fromhex(signature_hex), message)
        return True
    except Exception:
        return False


def require_pinned_crypto_backend() -> None:
    """Refuse silent crypto-backend drift on the closure verification path."""
    try:
        import cryptography
    except ImportError as exc:
        raise AuthorityRootUnavailable("CRYPTOGRAPHY_BACKEND_UNAVAILABLE") from exc
    if cryptography.__version__ != CRYPTOGRAPHY_VERSION:
        raise AuthorityRootUnavailable(
            f"CRYPTOGRAPHY_BACKEND_VERSION_MISMATCH:{cryptography.__version__}!={CRYPTOGRAPHY_VERSION}")


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(root: pathlib.Path, *args: str, text: bool = True) -> str | bytes:
    env = dict(os.environ)
    for name in tuple(env):
        if name.startswith("GIT_") and name != "GIT_CONFIG_NOSYSTEM":
            env.pop(name, None)
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          text=text, env=env)
    if proc.returncode:
        err = proc.stderr.strip() if text else proc.stderr.decode("utf-8", "replace").strip()
        raise AuthorityRootError(f"GIT_COMMAND_FAILED:{' '.join(args)}:{err}")
    return proc.stdout.strip() if text else proc.stdout


def validate_git_bound_authority(
    context: AuthorityContext,
    *,
    git_root: pathlib.Path,
    expected_head: str,
    object_head: str | None = None,
) -> None:
    """Prove all four canonical authority files are clean tracked blobs at an exact Git head."""
    _subjects, canonical_paths = _authority_profile(context.repair_generation)
    if re.fullmatch(r"[0-9a-f]{40}", expected_head or "") is None:
        raise AuthorityRootError("EXPECTED_HEAD_NOT_CANONICAL_SHA40")
    root = pathlib.Path(str(_git(git_root, "rev-parse", "--show-toplevel"))).resolve(strict=True)
    if root != git_root.resolve(strict=True):
        raise AuthorityRootError("GIT_ROOT_MISMATCH")
    if str(_git(root, "rev-parse", "HEAD")) != expected_head:
        raise AuthorityRootError("EXPECTED_HEAD_MISMATCH")
    if str(_git(root, "status", "--porcelain=v1", "--untracked-files=all")):
        raise AuthorityRootError("GIT_WORKTREE_NOT_CLEAN")
    for name, rel in canonical_paths.items():
        path = context.paths.get(name)
        if path is None:
            raise AuthorityRootError(f"AUTHORITY_PATH_MISSING:{name}")
        try:
            actual_rel = path.resolve(strict=True).relative_to(root).as_posix()
        except (OSError, ValueError):
            raise AuthorityRootError(f"AUTHORITY_PATH_OUTSIDE_GIT_ROOT:{name}") from None
        if actual_rel != rel:
            raise AuthorityRootError(f"AUTHORITY_PATH_NONCANONICAL:{name}:{actual_rel}")
        disk = path.read_bytes()
        if _git(root, "show", f"{expected_head}:{rel}", text=False) != disk:
            raise AuthorityRootError(f"AUTHORITY_GIT_BLOB_MISMATCH:{name}")
        if object_head is not None and _git(root, "show", f"{object_head}:{rel}", text=False) != disk:
            raise AuthorityRootError(f"AUTHORITY_SOURCE_GIT_BLOB_MISMATCH:{name}")
    supporting_paths = set(AUTHORITY_SUBJECT_PATHS.values()) | set(PROFILE_SUBJECT_PATHS.values()) | {
        "docs/governance/B00_B07_INVALIDATION_MANIFEST.v1.json",
    }
    if context.repair_generation == 1:
        supporting_paths.add("docs/control/b00r_policy.v1.json")
    else:
        supporting_paths.update({
            "docs/control/b00r_policy.v2.json",
            "docs/governance/B00R_GENERATION_LEDGER.v1.json",
        })
    for rel in supporting_paths:
        disk = (root / rel).read_bytes()
        if _git(root, "show", f"{expected_head}:{rel}", text=False) != disk:
            raise AuthorityRootError(f"AUTHORITY_SUBJECT_GIT_BLOB_MISMATCH:{rel}")
        if object_head is not None and _git(root, "show", f"{object_head}:{rel}", text=False) != disk:
            raise AuthorityRootError(f"AUTHORITY_SUBJECT_SOURCE_GIT_BLOB_MISMATCH:{rel}")


def _load_json(path: pathlib.Path) -> dict:
    def _unique_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise AuthorityRootError(f"{path}: duplicate JSON key {key!r}")
            value[key] = item
        return value
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AuthorityRootError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AuthorityRootError(f"{path}: JSON root must be an object")
    return value


def load_external_pins(
    *,
    pins_path: pathlib.Path | None = None,
    environ: Mapping[str, str] | None = None,
    repo_root: pathlib.Path = ROOT,
    repair_generation: int = 2,
) -> dict[str, str]:
    """Load and syntax-check pins, rejecting an in-repository pin file."""
    pins: dict[str, str] = {}
    if pins_path is not None:
        try:
            resolved = pins_path.resolve(strict=True)
            resolved.relative_to(repo_root.resolve(strict=True))
        except ValueError:
            pass
        except OSError as exc:
            raise AuthorityRootError(f"cannot resolve pin file: {exc}") from exc
        else:
            raise AuthorityRootError("EXTERNAL_PINS_MUST_BE_OUTSIDE_REPOSITORY")
        pins.update(_load_json(resolved))
    env = os.environ if environ is None else environ
    subjects, _canonical = _authority_profile(repair_generation)
    allowed = {meta[0] for meta in subjects.values()}
    unknown = set(pins) - allowed
    if unknown:
        raise AuthorityRootError(f"UNKNOWN_EXTERNAL_PIN_NAMES:{sorted(unknown)}")
    if pins_path is not None and set(pins) != allowed:
        raise AuthorityRootError(
            "EXTERNAL_PIN_FILE_KEY_SET_MISMATCH:"
            f"missing={sorted(allowed-set(pins))}:extra={sorted(set(pins)-allowed)}")
    for name in allowed:
        # GitHub `${{ vars.NAME }}` expands an undefined variable to the empty string. Treat that
        # exact representation as absent owner input (UNAVAILABLE), not as a malformed supplied
        # digest (FAIL). Nonempty whitespace or any other malformed value remains a hard failure.
        if name in env and env[name] != "":
            if name in pins and pins[name] != env[name]:
                raise AuthorityRootError(f"CONFLICTING_EXTERNAL_PIN:{name}")
            pins[name] = env[name]
    for name, value in pins.items():
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None \
                or value == "0" * 64:
            raise AuthorityRootError(f"INVALID_EXTERNAL_PIN:{name}")
    return pins


def _verify_subject_bindings(
    decisions: dict[str, dict],
    root: pathlib.Path,
    *,
    repair_generation: int,
) -> None:
    """Cross-bind locally resolvable subjects named by the signed decisions."""
    authority_paths = AUTHORITY_SUBJECT_PATHS
    profile_paths = PROFILE_SUBJECT_PATHS
    profile = decisions["receipt_profile"]
    trust_rel = TRUST_REL if repair_generation == 1 else TRUST_REL_G2
    if profile.get("authority_registry") != trust_rel \
            or profile.get("scope", {}).get("trust_registry") != trust_rel:
        raise AuthorityRootError("RECEIPT_PROFILE_TRUST_REGISTRY_PATH_MISMATCH")
    if set(profile.get("subject_sha256s", {})) != set(profile_paths):
        raise AuthorityRootError("RECEIPT_PROFILE_SUBJECT_SET_MISMATCH")
    for name, rel in profile_paths.items():
        path = root / rel
        if not path.is_file() or _sha256(path) != profile["subject_sha256s"].get(name):
            raise AuthorityRootError(f"DECISION_SUBJECT_MISMATCH:{name}")
    if (repair_generation == 2
            and profile.get("supersedes") != ["DEC-RECEIPT-PROFILE-001"]):
        raise AuthorityRootError("RECEIPT_PROFILE_G2_SUPERSESSION_MISMATCH")
    authority = decisions["authority_bundle"]
    if set(authority.get("subject_sha256s", {})) != set(authority_paths):
        raise AuthorityRootError("AUTHORITY_BUNDLE_SUBJECT_SET_MISMATCH")
    for name, rel in authority_paths.items():
        path = root / rel
        if not path.is_file() or _sha256(path) != authority["subject_sha256s"].get(name):
            raise AuthorityRootError(f"DECISION_SUBJECT_MISMATCH:{name}")
    if repair_generation == 2 and authority.get("supersedes") != ["DEC-AUTHORITY-BUNDLE-001"]:
        raise AuthorityRootError("AUTHORITY_BUNDLE_G2_SUPERSESSION_MISMATCH")

    repair = decisions["b00_repair"]
    subjects = repair.get("subject_sha256s", {})
    if repair_generation == 1:
        if set(subjects) != {"audited_start_sha", "invalidation_manifest"}:
            raise AuthorityRootError("B00_REPAIR_SUBJECT_SET_MISMATCH")
        invalidation = root / "docs/governance/B00_B07_INVALIDATION_MANIFEST.v1.json"
        if not invalidation.is_file() or _sha256(invalidation) != \
                subjects.get("invalidation_manifest"):
            raise AuthorityRootError("DECISION_SUBJECT_MISMATCH:invalidation_manifest")
        policy_path = root / "docs/control/b00r_policy.v1.json"
    else:
        expected = {
            "audited_start_sha", "generation_1_anchor_object_sha",
            "generation_1_receipt_sha256", "generation_ledger", "policy_v2",
        }
        if set(subjects) != expected:
            raise AuthorityRootError("B00R_G2_REPAIR_SUBJECT_SET_MISMATCH")
        generation_ledger = root / "docs/governance/B00R_GENERATION_LEDGER.v1.json"
        policy_path = root / "docs/control/b00r_policy.v2.json"
        generation_one_receipt = root / "evidence/receipts/B00R.receipt.v3.json"
        if _sha256(generation_ledger) != subjects.get("generation_ledger"):
            raise AuthorityRootError("DECISION_SUBJECT_MISMATCH:generation_ledger")
        if _sha256(policy_path) != subjects.get("policy_v2"):
            raise AuthorityRootError("DECISION_SUBJECT_MISMATCH:policy_v2")
        if _sha256(generation_one_receipt) != subjects.get("generation_1_receipt_sha256"):
            raise AuthorityRootError("DECISION_SUBJECT_MISMATCH:generation_1_receipt")
        anchor_object = str(_git(root, "rev-parse", "B00R_RECEIPT_ANCHOR"))
        if anchor_object != subjects.get("generation_1_anchor_object_sha"):
            raise AuthorityRootError("DECISION_SUBJECT_MISMATCH:generation_1_anchor")
        if repair.get("supersedes") != ["DEC-B00-REPAIR-001"]:
            raise AuthorityRootError("B00R_G2_REPAIR_SUPERSESSION_MISMATCH")
    audited = subjects.get("audited_start_sha")
    if repair.get("scope", {}).get("audited_start") != f"main@{audited}":
        raise AuthorityRootError("B00_REPAIR_AUDITED_START_SCOPE_MISMATCH")
    try:
        policy = _load_json(policy_path)
    except AuthorityRootError as exc:
        raise AuthorityRootError(f"B00_REPAIR_POLICY_UNAVAILABLE:{exc}") from exc
    if policy.get("audited_start_sha") != audited \
            or policy.get("repair_generation") != repair_generation:
        raise AuthorityRootError("B00_REPAIR_POLICY_AUDITED_START_MISMATCH")
    env = dict(os.environ)
    for name in tuple(env):
        if name.startswith("GIT_") and name != "GIT_CONFIG_NOSYSTEM":
            env.pop(name, None)
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    for args, label in (
        (("cat-file", "-e", f"{audited}^{{commit}}"), "AUDITED_START_NOT_COMMIT"),
        (("merge-base", "--is-ancestor", audited, "HEAD"), "AUDITED_START_NOT_ANCESTOR"),
    ):
        proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True, env=env)
        if proc.returncode:
            raise AuthorityRootError(f"B00_REPAIR_{label}")
    for name, doc in decisions.items():
        if doc.get("authority_registry") != trust_rel:
            raise AuthorityRootError(f"DECISION_AUTHORITY_REGISTRY_MISMATCH:{name}")


def load_authority_context(
    *,
    now_us: int,
    pins_path: pathlib.Path | None = None,
    environ: Mapping[str, str] | None = None,
    subject_paths: Mapping[str, pathlib.Path] | None = None,
    repo_root: pathlib.Path = ROOT,
    repair_generation: int = 2,
) -> AuthorityContext:
    """Load, externally pin, and cryptographically authenticate all four authority objects."""
    if not isinstance(now_us, int) or isinstance(now_us, bool) or now_us <= 0:
        raise AuthorityRootUnavailable("NOW_US_REQUIRED")
    require_pinned_crypto_backend()
    subjects, _canonical_paths = _authority_profile(repair_generation)
    pins = load_external_pins(
        pins_path=pins_path,
        environ=environ,
        repo_root=repo_root,
        repair_generation=repair_generation,
    )
    paths: dict[str, pathlib.Path] = {}
    for name, (_pin, _did, authenticated, template) in subjects.items():
        override = subject_paths.get(name) if subject_paths else None
        path = pathlib.Path(override) if override is not None else (
            authenticated if authenticated.exists() else template)
        if not path.exists():
            raise AuthorityRootUnavailable(f"{name}:AUTHORITY_OBJECT_ABSENT")
        paths[name] = path
    for name, (pin_name, _did, _authenticated, _template) in subjects.items():
        expected = pins.get(pin_name)
        if expected is None:
            raise AuthorityRootUnavailable(f"{name}:EXTERNAL_PIN_ABSENT:{pin_name}")
        actual = _sha256(paths[name])
        if actual != expected:
            raise AuthorityRootError(f"{name}:EXTERNAL_PIN_MISMATCH")

    registry = _load_json(paths["trust_registry"])
    if registry.get("authenticated") is not True:
        raise AuthorityRootUnavailable("trust_registry:NOT_AUTHENTICATED")
    try:
        trust = governance.validate_trust_registry(registry)
        governance.assert_usable_trust_registry(trust)
    except governance.GovernanceError as exc:
        raise AuthorityRootError(f"trust_registry:{exc}") from exc

    decisions: dict[str, dict] = {}
    for name in ("authority_bundle", "receipt_profile", "b00_repair"):
        doc = _load_json(paths[name])
        expected_id = subjects[name][1]
        if doc.get("decision_id") != expected_id:
            raise AuthorityRootError(f"{name}:DECISION_ID_MISMATCH")
        try:
            governance.validate_authenticated_decision(
                doc, trust=trust, now_us=now_us, verify_fn=ed25519_verify)
        except governance.GovernanceError as exc:
            if doc.get("authenticated") is not True or not doc.get("signatures"):
                raise AuthorityRootUnavailable(f"{name}:{exc}") from exc
            raise AuthorityRootError(f"{name}:{exc}") from exc
        decisions[name] = doc
    _verify_subject_bindings(decisions, repo_root, repair_generation=repair_generation)
    try:
        threshold, roles, algorithm = governance.receipt_profile_from_decision(
            decisions["receipt_profile"], repair_generation=repair_generation)
    except governance.GovernanceError as exc:
        raise AuthorityRootError(str(exc)) from exc
    return AuthorityContext(
        trust=trust,
        decisions=decisions,
        digests={name: _sha256(path) for name, path in paths.items()},
        receipt_threshold=threshold,
        receipt_roles=roles,
        receipt_algorithm=algorithm,
        repair_generation=repair_generation,
        paths=paths,
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--pins", type=pathlib.Path,
                        help="out-of-repository JSON object of external public pins")
    parser.add_argument("--now-us", type=int,
                        help="trusted current Unix time in microseconds (required for closure)")
    parser.add_argument("--expected-head",
                        help="exact event head whose tracked authority bytes are validated")
    parser.add_argument("--git-root", type=pathlib.Path, default=ROOT)
    parser.add_argument("--repair-generation", type=int, choices=(1, 2), default=2)
    args = parser.parse_args(argv)
    try:
        context = load_authority_context(
            now_us=args.now_us,
            pins_path=args.pins,
            repair_generation=args.repair_generation,
        )
    except AuthorityRootUnavailable as exc:
        print(f"UNAVAILABLE_AUTHORITY_ROOT: {exc}")
        return 1 if args.strict else 0
    except AuthorityRootError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    if args.strict:
        if args.expected_head is None:
            print("FAIL: --strict requires --expected-head", file=sys.stderr)
            return 2
        try:
            validate_git_bound_authority(
                context, git_root=args.git_root, expected_head=args.expected_head)
        except AuthorityRootError as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1
    print("OK: authority root Ed25519-authenticated, externally pinned, and Git-bound "
          f"(receipt threshold={context.receipt_threshold})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
