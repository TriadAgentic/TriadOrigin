"""B00R governance and evidence law (forward-repair root).

This module is the single implementation of the repository-governance/evidence primitives the
B00R repair introduces. It is pure (no clock, no network, no environment read on the decision
path) and it **fails closed**: an absent, unauthenticated, placeholder, or unresolved input can
never yield a PASS. The only closure-capable receipt result is ``PASS_REPOSITORY_SAFE_HOLD``.

Nothing here activates anything. It grants no E08/E09 authority, venue, credential, order, PAPER,
TESTNET, LIVE, or money capability. The safety posture it asserts is invariant OFF/OFF/OFF/LIVE
(``venue_environment`` / ``venue_activation`` / ``paper_activation`` OFF, ``shadow_activation``
LIVE) with ``activation_result=DENIED_SAFE_HOLD``.

The load-bearing strictness laws (each exercised by ``tests/b00r``):

* digests are lowercase ``[0-9a-f]{64}``, nonzero, and never a placeholder token
  (``B00R-D08``/``NEG-005``);
* PASS scope is a closed structure that recursively rejects empty, null, whitespace, wildcard,
  and unknown-typed leaves (``B00R-D09``/``NEG-006``);
* an evidence digest resolves to exactly one committed, tracked, non-escaping, non-symlink file
  whose bytes hash to it (``NEG-011``);
* a receipt authenticates by profile-selected external signatures under an externally pinned trust
  registry, not by a self-hash (``B00R-D11``/``NEG-008``/``NEG-009``);
* only ``B00R`` may use the root receipt variant, and only with the authenticated repair-decision
  and invalidation-manifest digests; every successor binds an exact predecessor anchor
  (``NEG-018``/``B00R-D...``);
* evidence is observed strictly after the event it attests, with zero future tolerance
  (``B00R-D14``/``NEG-012``).
"""

from __future__ import annotations

import re
from typing import Any

from .canonical import canonical_json, sha256_hex
from . import contracts as _contracts

# --- constants -----------------------------------------------------------------------------------
# NB: the DARK-capability boundary forbids ``re.compile`` (a ``compile`` call) and any crypto/network
# import inside ``src/triad_origin``; this module therefore uses inline ``re.fullmatch`` and takes an
# INJECTED signature verifier (the Ed25519 bytes verification lives in the unscanned tool layer).
_HEX64 = r"[0-9a-f]{64}"
_HEX40 = r"[0-9a-f]{40}"
ZERO_DIGEST = "0" * 64

# Result vocabulary. Only PASS_REPOSITORY_SAFE_HOLD closes a milestone; a generic "PASS",
# activation grant, or live authority is not representable.
RESULT_PASS = "PASS_REPOSITORY_SAFE_HOLD"
RECEIPT_RESULTS = (RESULT_PASS, "FAIL", "BLOCKED", "UNAVAILABLE")

# Placeholder / sentinel tokens that a real digest field may never carry.
PLACEHOLDER_TOKENS = {
    "", "0", ZERO_DIGEST, "NOT_APPLICABLE", "N/A", "NA", "NONE", "NULL", "PENDING",
    "TBD", "TODO", "PLACEHOLDER", "UNKNOWN", "UNBOUND", "UNBOUND_DARK_BUILD",
}

# Immutable safety posture (OFF/OFF/OFF/LIVE). shadow_activation is fixed LIVE, not switchable.
SAFETY_POSTURE = {
    "venue_environment": "OFF",
    "venue_activation": "OFF",
    "paper_activation": "OFF",
    "shadow_activation": "LIVE",
}
ACTIVATION_RESULT = "DENIED_SAFE_HOLD"
GITHUB_ACTIONS_INTEGRATION_ID = 15368

# Trust-registry / decision vocabulary.
SIGNER_ROLES = ("EVIDENCE_PRODUCER", "INDEPENDENT_COUNTERSIGNER", "AUTHORITY_OWNER")
SUPPORTED_SIG_ALGORITHMS = ("ed25519",)
# Field-name substrings that would leak private key material — never permitted in a public
# registry, decision, or evidence artifact.
_SECRET_NAME_HINTS = ("private", "secret", "seed", "passphrase", "bearer", "token", "credential")


class GovernanceError(ValueError):
    """A governance/evidence law failure. Always fail closed."""


# --- digest primitives ---------------------------------------------------------------------------
def is_hex64(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(_HEX64, value) is not None


def assert_hex64(value: object, where: str) -> str:
    """A digest field must be lowercase ``[0-9a-f]{64}``, nonzero, and non-placeholder."""
    if not isinstance(value, str):
        raise GovernanceError(f"DIGEST_NOT_STRING: {where} is {type(value).__name__}")
    if value in PLACEHOLDER_TOKENS:
        raise GovernanceError(f"DIGEST_PLACEHOLDER: {where}={value!r}")
    if re.fullmatch(_HEX64, value) is None:
        raise GovernanceError(
            f"DIGEST_NOT_CANONICAL_HEX64: {where}={value!r} "
            "(must be lowercase [0-9a-f]{64}, nonzero)")
    if value == ZERO_DIGEST:
        raise GovernanceError(f"DIGEST_ZERO: {where}")
    return value


def assert_no_placeholder(value: object, where: str) -> None:
    if isinstance(value, str) and value.strip().upper() in {t.upper() for t in PLACEHOLDER_TOKENS}:
        raise GovernanceError(f"PLACEHOLDER_VALUE: {where}={value!r}")


# --- closed-scope primitive ----------------------------------------------------------------------
def assert_closed_scope(node: Any, where: str = "scope") -> None:
    """Recursively reject empty, null, whitespace, wildcard, or unknown-typed scope leaves.

    Permitted leaves: nonempty non-whitespace non-wildcard strings, canonical integers, booleans.
    Permitted containers: nonempty objects (nonempty string keys) and nonempty arrays. A float,
    ``None``, an empty container, or a wildcard string is rejected (``NEG-006``).
    """
    if node is None:
        raise GovernanceError(f"SCOPE_NULL: {where}")
    if isinstance(node, bool):
        return
    if isinstance(node, float):
        raise GovernanceError(f"SCOPE_FLOAT: {where} (noncanonical numeric leaf)")
    if isinstance(node, int):
        return
    if isinstance(node, str):
        if node == "" or node.strip() == "":
            raise GovernanceError(f"SCOPE_EMPTY_STRING: {where}")
        if "*" in node:
            raise GovernanceError(f"SCOPE_WILDCARD: {where}={node!r}")
        return
    if isinstance(node, dict):
        if not node:
            raise GovernanceError(f"SCOPE_EMPTY_OBJECT: {where}")
        for key, value in node.items():
            if not isinstance(key, str) or key.strip() == "" or "*" in key:
                raise GovernanceError(f"SCOPE_BAD_KEY: {where}.{key!r}")
            assert_closed_scope(value, f"{where}.{key}")
        return
    if isinstance(node, list):
        if not node:
            raise GovernanceError(f"SCOPE_EMPTY_ARRAY: {where}")
        for i, value in enumerate(node):
            assert_closed_scope(value, f"{where}[{i}]")
        return
    raise GovernanceError(f"SCOPE_UNKNOWN_TYPE: {where} is {type(node).__name__}")


# --- schema loading (governance documents are validated structurally, not via the wire registry)--
def load_governance_schema(schema_id: str) -> dict:
    if not re.fullmatch(r"triad\.[a-z0-9_]+(?:\.[a-z0-9_]+)*\.v[1-9][0-9]*", schema_id):
        raise GovernanceError(f"invalid governance schema id: {schema_id!r}")
    path = _contracts._SCHEMA_DIR / f"{schema_id}.schema.json"  # noqa: SLF001 (same package)
    import json
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise GovernanceError(f"cannot load governance schema {schema_id!r}: {exc}") from exc


def validate_structure(doc: dict, schema_id: str) -> None:
    """Structural (closed-schema) validation of a governance document."""
    schema = load_governance_schema(schema_id)
    try:
        _contracts._validate_against_schema(schema, doc)  # noqa: SLF001 (same package)
    except _contracts.ContractError as exc:
        raise GovernanceError(f"SCHEMA_VIOLATION[{schema_id}]: {exc}") from exc


# --- no-secret guard -----------------------------------------------------------------------------
def assert_no_secret_material(doc: Any, where: str = "<root>") -> None:
    """A public governance artifact may carry no private key/seed/credential material."""
    if isinstance(doc, dict):
        for key, value in doc.items():
            k = str(key).lower()
            if any(hint in k for hint in _SECRET_NAME_HINTS) and value not in (None, "", [], {}):
                # A public key field named e.g. "public_key" is fine; a bare "private_key",
                # "seed", "secret", "bearer_token" carrying a value is not.
                if "public" not in k:
                    raise GovernanceError(f"SECRET_MATERIAL_PRESENT: {where}.{key}")
            assert_no_secret_material(value, f"{where}.{key}")
    elif isinstance(doc, list):
        for i, value in enumerate(doc):
            assert_no_secret_material(value, f"{where}[{i}]")
    elif isinstance(doc, str):
        if "BEGIN PRIVATE KEY" in doc or "BEGIN OPENSSH PRIVATE KEY" in doc:
            raise GovernanceError(f"SECRET_MATERIAL_PRESENT: PEM private key at {where}")


# --- trust registry ------------------------------------------------------------------------------
def validate_trust_registry(doc: dict) -> dict[str, dict]:
    """Validate a public receipt trust registry and return {key_id: entry}.

    A registry carries only public material. Every key has a unique id and identity, a role in
    :data:`SIGNER_ROLES`, an algorithm in :data:`SUPPORTED_SIG_ALGORITHMS`, a validity window, a
    scope, and a revocation flag.
    """
    validate_structure(doc, "triad.receipt_trust_registry.v1")
    assert_no_secret_material(doc)
    keys = doc.get("keys")
    if not isinstance(keys, list) or not keys:
        raise GovernanceError("TRUST_REGISTRY_EMPTY")
    by_id: dict[str, dict] = {}
    identities: set[str] = set()
    for entry in keys:
        kid = entry.get("key_id")
        if kid in by_id:
            raise GovernanceError(f"TRUST_REGISTRY_DUPLICATE_KEY_ID: {kid}")
        if entry.get("role") not in SIGNER_ROLES:
            raise GovernanceError(f"TRUST_REGISTRY_BAD_ROLE: {kid}={entry.get('role')!r}")
        if entry.get("algorithm") not in SUPPORTED_SIG_ALGORITHMS:
            raise GovernanceError(f"TRUST_REGISTRY_BAD_ALGORITHM: {kid}")
        by_id[kid] = entry
        identities.add(entry.get("identity"))
    if len(identities) != len(by_id):
        raise GovernanceError("TRUST_REGISTRY_DUPLICATE_IDENTITY")
    return by_id


def assert_usable_trust_registry(trust: dict[str, dict]) -> None:
    """Reject placeholder or unusable public-key material in a closure trust registry.

    The contract goldens intentionally exercise structural validation.  PASS-capable tools must
    additionally call this function so a syntactically valid all-zero template can never become a
    trust root merely by setting ``authenticated=true``.
    """
    if not trust:
        raise GovernanceError("TRUST_REGISTRY_EMPTY")
    public_keys: set[str] = set()
    roles: set[str] = set()
    for key_id, entry in trust.items():
        public_key = entry.get("public_key_hex")
        if not isinstance(public_key, str) or re.fullmatch(_HEX64, public_key) is None:
            raise GovernanceError(f"TRUST_REGISTRY_BAD_PUBLIC_KEY:{key_id}")
        if public_key == ZERO_DIGEST:
            raise GovernanceError(f"TRUST_REGISTRY_PLACEHOLDER_PUBLIC_KEY:{key_id}")
        if public_key in public_keys:
            raise GovernanceError(f"TRUST_REGISTRY_DUPLICATE_PUBLIC_KEY:{key_id}")
        public_keys.add(public_key)
        if entry.get("revoked") is not True:
            roles.add(entry.get("role"))
        not_before = entry.get("not_before_us")
        not_after = entry.get("not_after_us")
        if (not isinstance(not_before, int) or isinstance(not_before, bool)
                or not isinstance(not_after, int) or isinstance(not_after, bool)
                or not_before < 0 or not_after <= not_before):
            raise GovernanceError(f"TRUST_REGISTRY_BAD_VALIDITY_WINDOW:{key_id}")
        scope = entry.get("scope")
        if not isinstance(scope, str) or not scope.strip() or "*" in scope:
            raise GovernanceError(f"TRUST_REGISTRY_BAD_SCOPE:{key_id}")
    missing = set(SIGNER_ROLES) - roles
    if missing:
        raise GovernanceError(f"TRUST_REGISTRY_MISSING_ROLES:{sorted(missing)}")


# --- signature threshold (crypto verifier INJECTED; unavailable => fail closed, never PASS) -------
def verify_signatures(
    *,
    signed_bytes: bytes,
    signatures: list[dict],
    trust: dict[str, dict],
    required_roles: tuple[str, ...],
    threshold: int,
    required_scope: str | None = None,
    now_us: int | None = None,
    verify_fn=None,
) -> tuple[bool, str]:
    """Verify a threshold of distinct-identity signatures under the trust registry.

    Returns ``(ok, reason)``. ``ok`` is True only when at least ``threshold`` distinct trusted,
    active, in-window, correct-role signers each carry a cryptographically verified signature.
    Any unknown/expired/future/revoked/wrong-role/duplicate signer — or an absent crypto verifier
    (``verify_fn is None``) — yields ``ok=False`` with a named reason, never a silent pass
    (``NEG-008``/``NEG-009``). The Ed25519 byte verification is INJECTED as ``verify_fn`` by the
    tool layer, because the DARK boundary forbids a crypto import inside ``src/triad_origin``.
    """
    if not isinstance(threshold, int) or isinstance(threshold, bool) or threshold < 1:
        return False, "BAD_SIGNATURE_THRESHOLD"
    if len(set(required_roles)) != len(required_roles):
        return False, "DUPLICATE_REQUIRED_ROLE"
    if not isinstance(signatures, list) or not signatures:
        return False, "NO_EXTERNAL_SIGNATURES"
    # Pass 1 — structural: resolve each signer, reject unknown/revoked/duplicate/out-of-window,
    # and collect roles. These fail closed regardless of crypto availability (``NEG-009``).
    seen_identities: set[str] = set()
    roles_met: set[str] = set()
    for sig in signatures:
        if not isinstance(sig, dict):
            return False, "BAD_SIGNATURE_RECORD"
        kid = sig.get("key_id")
        entry = trust.get(kid)
        if entry is None:
            return False, f"UNKNOWN_SIGNER:{kid}"
        if entry.get("revoked"):
            return False, f"REVOKED_SIGNER:{kid}"
        if required_scope is not None and not _trust_scope_allows(entry.get("scope"), required_scope):
            return False, f"SIGNER_SCOPE_DENIED:{kid}:{required_scope}"
        signature_hex = sig.get("signature_hex")
        if not isinstance(signature_hex, str) or re.fullmatch(r"[0-9a-f]{128}", signature_hex) is None:
            return False, f"BAD_SIGNATURE_ENCODING:{kid}"
        identity = entry.get("identity")
        if identity in seen_identities:
            return False, f"DUPLICATE_SIGNER_IDENTITY:{identity}"
        if now_us is not None:
            if not isinstance(now_us, int) or isinstance(now_us, bool) or now_us <= 0:
                return False, "BAD_NOW_US"
            nb, na = entry.get("not_before_us"), entry.get("not_after_us")
            if isinstance(nb, int) and now_us < nb:
                return False, f"SIGNER_NOT_YET_VALID:{kid}"
            if isinstance(na, int) and now_us > na:
                return False, f"SIGNER_EXPIRED:{kid}"
        seen_identities.add(identity)
        roles_met.add(entry.get("role"))
    if len(seen_identities) < threshold:
        return False, f"BELOW_THRESHOLD:{len(seen_identities)}<{threshold}"
    for role in required_roles:
        if role not in roles_met:
            return False, f"MISSING_ROLE:{role}"
    # Pass 2 — crypto: verify every signature's bytes. An absent verifier is fail-closed
    # VERIFY_UNAVAILABLE (owner must run with a crypto library); a bad/forged signature is
    # BAD_SIGNATURE. Never a silent pass (``NEG-008``).
    if verify_fn is None:
        return False, "VERIFY_UNAVAILABLE"
    for sig in signatures:
        entry = trust[sig.get("key_id")]
        try:
            ok = bool(verify_fn(entry.get("public_key_hex", ""), signed_bytes,
                                sig.get("signature_hex", "")))
        except Exception:  # a raising verifier is a bad signature, never a pass
            ok = False
        if not ok:
            return False, f"BAD_SIGNATURE:{sig.get('key_id')}"
    return True, "OK"


_MILESTONE_SCOPE_ORDER = ("B00R", "B01C", "B02C", "B03C", "B04C", "B05C", "B06R", "B07")


def _trust_scope_allows(scope: object, target: str) -> bool:
    """Interpret a closed comma-list, plus the ratified ``B00R..B07`` milestone range."""
    if not isinstance(scope, str):
        return False
    for token in (item.strip() for item in scope.split(",")):
        if token == target:
            return True
        if ".." not in token:
            continue
        start, end = token.split("..", 1)
        try:
            target_i = _MILESTONE_SCOPE_ORDER.index(target)
            if (_MILESTONE_SCOPE_ORDER.index(start) <= target_i
                    <= _MILESTONE_SCOPE_ORDER.index(end)):
                return True
        except ValueError:
            continue
    return False


# --- governance decision -------------------------------------------------------------------------
def decision_is_authenticated(doc: dict) -> bool:
    """A decision is authenticated only if it structurally validates AND declares real signatures.

    A template carrying ``authenticated: false`` or an empty ``signatures`` array is never
    authenticated (fail-closed); actual cryptographic verification is done by
    :func:`validate_authority_root` against the externally pinned trust registry.
    """
    try:
        validate_structure(doc, "triad.governance_decision.v1")
    except GovernanceError:
        return False
    if doc.get("authenticated") is not True:
        return False
    sigs = doc.get("signatures")
    return isinstance(sigs, list) and len(sigs) >= 1


def canonical_decision_signing_bytes(decision: dict) -> bytes:
    """Canonical bytes signed for a governance decision.

    The signed object includes ``authenticated=true`` and every subject/scope field, but excludes
    only the signatures array.  This definition removes the old manual "sign what looks right"
    ambiguity and is shared by payload rendering and verification tools.
    """
    unsigned = dict(decision)
    unsigned.pop("signatures", None)
    data = canonical_json(unsigned)
    return data if isinstance(data, bytes) else data.encode("utf-8")


def validate_authenticated_decision(
    decision: dict,
    *,
    trust: dict[str, dict],
    now_us: int,
    verify_fn,
) -> None:
    """Cryptographically authenticate one ``DEC-*`` decision under an authority-owner key."""
    if not isinstance(now_us, int) or isinstance(now_us, bool) or now_us <= 0:
        raise GovernanceError("NOW_US_REQUIRED")
    validate_structure(decision, "triad.governance_decision.v1")
    assert_no_secret_material(decision)
    if decision.get("authenticated") is not True:
        raise GovernanceError("DECISION_UNAUTHENTICATED")
    effective = decision.get("effective_at_us")
    if not isinstance(effective, int) or isinstance(effective, bool) or effective <= 0:
        raise GovernanceError("DECISION_BAD_EFFECTIVE_TIME")
    if effective > now_us:
        raise GovernanceError("DECISION_NOT_YET_EFFECTIVE")
    expiry = decision.get("expiry_at_us")
    if expiry is not None:
        if not isinstance(expiry, int) or isinstance(expiry, bool) or expiry <= effective:
            raise GovernanceError("DECISION_BAD_EXPIRY")
        if now_us > expiry:
            raise GovernanceError("DECISION_EXPIRED")
    assert_closed_scope(decision.get("scope"), "decision.scope")
    subjects = decision.get("subject_sha256s")
    if not isinstance(subjects, dict) or not subjects:
        raise GovernanceError("DECISION_EMPTY_SUBJECTS")
    for name, digest in subjects.items():
        if not isinstance(name, str) or not name.strip():
            raise GovernanceError("DECISION_BAD_SUBJECT_NAME")
        if not isinstance(digest, str) or not (
                re.fullmatch(_HEX64, digest) or re.fullmatch(_HEX40, digest)):
            raise GovernanceError(f"DECISION_BAD_SUBJECT_DIGEST:{name}")
        if digest in ("0" * 40, ZERO_DIGEST):
            raise GovernanceError(f"DECISION_PLACEHOLDER_SUBJECT:{name}")
    ok, reason = verify_signatures(
        signed_bytes=canonical_decision_signing_bytes(decision),
        signatures=decision.get("signatures", []),
        trust=trust,
        required_roles=("AUTHORITY_OWNER",),
        threshold=1,
        required_scope=decision.get("decision_id"),
        # Key validity covers the decision action, while ``now_us`` above covers whether the
        # decision itself is currently effective/unexpired.
        now_us=effective,
        verify_fn=verify_fn,
    )
    if not ok:
        raise GovernanceError(f"DECISION_SIGNATURE_INVALID:{reason}")
    signer_ids = {sig.get("key_id") for sig in decision.get("signatures", [])}
    signer_identities = {trust[kid].get("identity") for kid in signer_ids if kid in trust}
    if decision.get("issuer") not in signer_identities:
        raise GovernanceError("DECISION_ISSUER_NOT_SIGNER_IDENTITY")


def receipt_profile_from_decision(decision: dict) -> tuple[int, tuple[str, ...], str]:
    """Return the explicitly ratified receipt signature profile.

    B00R v3 is canonical JSON with embedded Ed25519 signatures.  A decision selecting DSSE or a
    different framing must be implemented as a separately versioned envelope; it cannot silently
    pass through this validator.
    """
    scope = decision.get("scope", {})
    threshold = scope.get("signer_threshold")
    roles = scope.get("signer_roles")
    algorithm = scope.get("signature_algorithm")
    envelope = scope.get("envelope")
    if scope.get("canonicalization") != \
            "triad_origin.canonical.canonical_json (RFC8785-style sorted-key UTF-8)":
        raise GovernanceError("RECEIPT_PROFILE_CANONICALIZATION_MISMATCH")
    if scope.get("clock_law") != \
            "observed_at_us > source_merge_time_us; emitted_at_us >= observed_at_us; zero future tolerance":
        raise GovernanceError("RECEIPT_PROFILE_CLOCK_LAW_MISMATCH")
    if scope.get("trust_registry") != \
            "docs/governance/trust/receipt_trust_registry.v1.json":
        raise GovernanceError("RECEIPT_PROFILE_TRUST_PATH_MISMATCH")
    if scope.get("closure_anchor_mechanism") != \
            ("protected annotated tag B00R_RECEIPT_ANCHOR plus externally pinned active "
             "no-update/no-delete/no-bypass tag ruleset"):
        raise GovernanceError("RECEIPT_PROFILE_CLOSURE_ANCHOR_MISMATCH")
    if threshold != 2 or isinstance(threshold, bool):
        raise GovernanceError("RECEIPT_PROFILE_BAD_THRESHOLD")
    required_profile_roles = ["EVIDENCE_PRODUCER", "INDEPENDENT_COUNTERSIGNER"]
    if roles != required_profile_roles:
        raise GovernanceError("RECEIPT_PROFILE_BAD_ROLES")
    if algorithm != "ed25519":
        raise GovernanceError("RECEIPT_PROFILE_UNSUPPORTED_ALGORITHM")
    if envelope != "triad.evidence_receipt.v3 canonical-json":
        raise GovernanceError("RECEIPT_PROFILE_UNSUPPORTED_ENVELOPE")
    return threshold, tuple(roles), algorithm


# --- evidence manifest ---------------------------------------------------------------------------
def _safe_relpath(path: str) -> bool:
    if not isinstance(path, str) or path == "":
        return False
    if path.startswith("/") or "\\" in path:
        return False
    parts = path.split("/")
    return ".." not in parts and "" not in parts and "." not in parts


def validate_evidence_manifest(
    manifest: dict,
    root,
    *,
    expected_paths: set[str] | None = None,
    tracked_paths: set[str] | None = None,
) -> None:
    """Validate a closed evidence manifest against committed bytes.

    Rejects missing, extra, duplicate, symlink, path-escape, zero-size, placeholder-digest, and
    untracked entries, and a digest whose bytes do not match (``NEG-011``).
    """
    import pathlib
    root = pathlib.Path(root).resolve(strict=True)
    validate_structure(manifest, "triad.evidence_manifest.v1")
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise GovernanceError("EVIDENCE_MANIFEST_EMPTY")
    if manifest.get("entry_count") != len(entries):
        raise GovernanceError("EVIDENCE_ENTRY_COUNT_MISMATCH")
    declared_order = [entry.get("path") for entry in entries]
    if declared_order != sorted(declared_order):
        raise GovernanceError("EVIDENCE_PATHS_NOT_CANONICAL_ORDER")
    seen_paths: set[str] = set()
    seen_roles: set[str] = set()
    for entry in entries:
        rel = entry.get("path")
        if not _safe_relpath(rel):
            raise GovernanceError(f"EVIDENCE_PATH_UNSAFE: {rel!r}")
        if rel in seen_paths:
            raise GovernanceError(f"EVIDENCE_DUPLICATE_PATH: {rel}")
        seen_paths.add(rel)
        if tracked_paths is not None and rel not in tracked_paths:
            raise GovernanceError(f"EVIDENCE_UNTRACKED_FILE: {rel}")
        role = entry.get("role")
        if role in seen_roles and entry.get("role_unique", True):
            raise GovernanceError(f"EVIDENCE_DUPLICATE_ROLE: {role}")
        seen_roles.add(role)
        abspath = root / rel
        # Inspect exactly the candidate and its ancestors up to the evidence root.  Walking
        # ``Path.parents`` unbounded would inspect unrelated ancestors above ``root`` and could
        # reject a safe tree merely because (for example) /workspace itself is a symlink.
        cursor = abspath
        while True:
            if cursor.is_symlink():
                raise GovernanceError(f"EVIDENCE_SYMLINK: {rel}")
            if cursor == root:
                break
            cursor = cursor.parent
            if root not in (cursor, *cursor.parents):
                raise GovernanceError(f"EVIDENCE_PATH_ESCAPE: {rel}")
        try:
            resolved = abspath.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError):
            raise GovernanceError(f"EVIDENCE_PATH_ESCAPE: {rel}") from None
        if resolved != abspath:
            raise GovernanceError(f"EVIDENCE_SYMLINK: {rel}")
        if not abspath.is_file():
            raise GovernanceError(f"EVIDENCE_MISSING_FILE: {rel}")
        data = abspath.read_bytes()
        if len(data) == 0:
            raise GovernanceError(f"EVIDENCE_ZERO_SIZE: {rel}")
        declared_size = entry.get("size")
        if declared_size is not None and declared_size != len(data):
            raise GovernanceError(f"EVIDENCE_SIZE_MISMATCH: {rel}")
        digest = assert_hex64(entry.get("sha256"), f"evidence[{rel}].sha256")
        actual = sha256_hex(data)
        if actual != digest:
            raise GovernanceError(f"EVIDENCE_DIGEST_MISMATCH: {rel} ({actual[:16]} != "
                                  f"{digest[:16]})")
        expected_media = "application/json" if rel.endswith(".json") else "application/octet-stream"
        if entry.get("media_type") != expected_media:
            raise GovernanceError(f"EVIDENCE_MEDIA_TYPE_MISMATCH:{rel}")
    if expected_paths is not None and seen_paths != expected_paths:
        missing = sorted(expected_paths - seen_paths)
        extra = sorted(seen_paths - expected_paths)
        raise GovernanceError(f"EVIDENCE_CLOSED_SET_MISMATCH:missing={missing}:extra={extra}")


def build_evidence_manifest(root, entries: list[dict]) -> dict:
    """Deterministically build a closed evidence manifest from committed files.

    ``entries`` are ``{"path", "role", ...}`` records; ``sha256``/``size``/``media_type`` are
    computed from the bytes so the manifest can never claim a digest a file does not have.
    """
    import pathlib
    root = pathlib.Path(root)
    out = []
    for entry in sorted(entries, key=lambda e: e["path"]):
        rel = entry["path"]
        if not _safe_relpath(rel):
            raise GovernanceError(f"EVIDENCE_PATH_UNSAFE: {rel!r}")
        abspath = root / rel
        if abspath.is_symlink() or not abspath.is_file():
            raise GovernanceError(f"EVIDENCE_NOT_A_TRACKED_FILE: {rel}")
        data = abspath.read_bytes()
        media = "application/json" if rel.endswith(".json") else "application/octet-stream"
        out.append({
            "path": rel,
            "role": entry["role"],
            "media_type": entry.get("media_type", media),
            "size": len(data),
            "sha256": sha256_hex(data),
        })
    return {
        "schema": "triad.evidence_manifest.v1",
        "schema_version": "1.0.0",
        "manifest_kind": "EVIDENCE_MANIFEST",
        "entry_count": len(out),
        "entries": out,
    }


# --- receipt-v3 ----------------------------------------------------------------------------------
ROOT_MILESTONE = "B00R"


def canonical_receipt_signing_bytes(receipt: dict) -> bytes:
    """Canonical bytes signed by receipt signers: the receipt payload with ``signatures`` removed."""
    payload = dict(receipt.get("payload", {}))
    payload.pop("signatures", None)
    data = canonical_json(payload)
    return data if isinstance(data, bytes) else data.encode("utf-8")


def validate_receipt_v3(
    receipt: dict,
    *,
    milestone: str,
    trust: dict[str, dict] | None = None,
    threshold: int = 2,
    required_roles: tuple[str, ...] = ("EVIDENCE_PRODUCER", "INDEPENDENT_COUNTERSIGNER"),
    now_us: int | None = None,
    verify_fn=None,
) -> tuple[str, str]:
    """Validate a receipt-v3 document. Return ``(result, reason)``.

    ``result`` is one of :data:`RECEIPT_RESULTS`. A closure ``PASS_REPOSITORY_SAFE_HOLD`` is
    returned only when every structural, digest, scope, chronology, root/non-root, evidence, and
    signature law passes. Any absent owner input (no trust registry, no external signatures,
    unverifiable crypto) is BLOCKED — never PASS.
    """
    try:
        validate_structure(receipt, "triad.evidence_receipt.v3")
    except GovernanceError as exc:
        return "FAIL", str(exc)
    payload = receipt.get("payload", {})

    result = payload.get("result")
    if result not in RECEIPT_RESULTS:
        return "FAIL", f"RESULT_NOT_IN_ENUM:{result!r}"
    if payload.get("milestone") != milestone:
        return "FAIL", f"MILESTONE_MISMATCH:{payload.get('milestone')!r}!={milestone!r}"
    if payload.get("repository") != "TriadAgentic/TriadOrigin":
        return "FAIL", "REPOSITORY_IDENTITY_MISMATCH"
    source_pr = payload.get("source_pr")
    if not isinstance(source_pr, int) or isinstance(source_pr, bool) or source_pr <= 0:
        return "FAIL", "SOURCE_PR_INVALID"
    scope = payload.get("scope")
    if (not isinstance(scope, dict) or scope.get("milestone") != milestone
            or scope.get("repository") != payload.get("repository")):
        return "FAIL", "SCOPE_IDENTITY_MISMATCH"

    # Safety posture is invariant.
    if payload.get("activation_result") != ACTIVATION_RESULT:
        return "FAIL", "SAFETY_ACTIVATION_NOT_DENIED"
    if payload.get("levers") != SAFETY_POSTURE:
        return "FAIL", "SAFETY_POSTURE_DRIFT"

    # Root vs non-root variant.
    is_root = milestone == ROOT_MILESTONE
    if is_root:
        if payload.get("repair_generation") != 1:
            return "FAIL", "ROOT_REPAIR_GENERATION_MISMATCH"
        if payload.get("variant") != "ROOT":
            return "FAIL", "ROOT_MILESTONE_NOT_ROOT_VARIANT"
        if payload.get("predecessor"):
            return "FAIL", "ROOT_RECEIPT_HAS_PREDECESSOR"
        for field in ("repair_decision_sha256", "invalidation_manifest_sha256",
                      "audited_start_sha"):
            try:
                if field == "audited_start_sha":
                    v = payload.get(field)
                    if not isinstance(v, str) or re.fullmatch(r"[0-9a-f]{40}", v) is None:
                        return "FAIL", f"ROOT_BAD_AUDITED_START:{v!r}"
                else:
                    assert_hex64(payload.get(field), f"payload.{field}")
            except GovernanceError as exc:
                return "FAIL", str(exc)
    else:
        if payload.get("variant") != "SUCCESSOR":
            return "FAIL", "SUCCESSOR_MILESTONE_NOT_SUCCESSOR_VARIANT"
        pred = payload.get("predecessor")
        if not isinstance(pred, dict) or not pred:
            return "FAIL", "SUCCESSOR_MISSING_PREDECESSOR"
        try:
            assert_hex64(pred.get("receipt_sha256"), "predecessor.receipt_sha256")
            assert_no_placeholder(pred.get("anchor_id"), "predecessor.anchor_id")
        except GovernanceError as exc:
            return "FAIL", str(exc)
        if not pred.get("anchor_id"):
            return "FAIL", "SUCCESSOR_MISSING_ANCHOR"

    # Scope must be closed and nonempty.
    try:
        assert_closed_scope(payload.get("scope"), "payload.scope")
    except GovernanceError as exc:
        return "FAIL", str(exc)

    # Every declared digest is canonical hex64.
    for field in ("source_merge_sha", "source_merge_tree", "final_source_head",
                  "workflow_sha256", "contract_manifest_sha256", "test_manifest_sha256",
                  "evidence_manifest_sha256", "config_bundle_sha256", "rollback_proof_sha256"):
        v = payload.get(field)
        if field in ("source_merge_sha", "source_merge_tree", "final_source_head"):
            if not isinstance(v, str) or re.fullmatch(r"[0-9a-f]{40}", v) is None:
                return "FAIL", f"GIT_SHA_NOT_HEX40:{field}={v!r}"
        else:
            try:
                assert_hex64(v, f"payload.{field}")
            except GovernanceError as exc:
                return "FAIL", str(exc)

    # Chronology: observed strictly after source merge; emitted >= observed; no future.
    observed = payload.get("observed_at_us")
    emitted = payload.get("emitted_at_us")
    merged = payload.get("source_merge_time_us")
    expires = payload.get("expires_at_us")
    for label, v in (("observed_at_us", observed), ("emitted_at_us", emitted),
                     ("source_merge_time_us", merged), ("expires_at_us", expires)):
        if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
            return "FAIL", f"CHRONOLOGY_BAD_TIME:{label}"
    if not (merged < observed <= emitted):
        return "FAIL", "CHRONOLOGY_ORDER: require source_merge < observed <= emitted"
    if expires <= emitted:
        return "FAIL", "CHRONOLOGY_EXPIRY_NOT_AFTER_EMISSION"
    if result == RESULT_PASS and (not isinstance(now_us, int) or isinstance(now_us, bool)
                                  or now_us <= 0):
        return "BLOCKED", "NOW_US_REQUIRED"
    if now_us is not None and emitted > now_us:
        return "FAIL", "CHRONOLOGY_FUTURE_EVIDENCE"
    if now_us is not None and now_us > expires:
        return "FAIL", "RECEIPT_EXPIRED"

    # From here a PASS additionally needs authenticated external signatures under a pinned trust
    # registry. Absence of the trust registry is fail-closed BLOCKED, never PASS.
    if result != RESULT_PASS:
        return result, "NON_PASS_RESULT"

    if threshold != 2 or required_roles != (
            "EVIDENCE_PRODUCER", "INDEPENDENT_COUNTERSIGNER"):
        return "FAIL", "RECEIPT_PROFILE_SEPARATION_MISMATCH"

    evidence_ids = payload.get("evidence_ids")
    evidence_sha256s = payload.get("evidence_sha256s")
    if (not isinstance(evidence_ids, list) or not evidence_ids
            or len(evidence_ids) != len(evidence_sha256s or [])):
        return "FAIL", "EVIDENCE_INDEX_LENGTH_MISMATCH"
    if evidence_ids != sorted(evidence_ids) or len(set(evidence_ids)) != len(evidence_ids):
        return "FAIL", "EVIDENCE_IDS_NOT_CANONICAL_UNIQUE"
    if any(not _safe_relpath(path) for path in evidence_ids):
        return "FAIL", "EVIDENCE_ID_UNSAFE"
    try:
        for i, digest in enumerate(evidence_sha256s):
            assert_hex64(digest, f"payload.evidence_sha256s[{i}]")
    except GovernanceError as exc:
        return "FAIL", str(exc)

    if trust is None:
        return "BLOCKED", "NO_TRUST_REGISTRY_PINNED"
    ok, reason = verify_signatures(
        signed_bytes=canonical_receipt_signing_bytes(receipt),
        signatures=payload.get("signatures", []),
        trust=trust,
        required_roles=required_roles,
        threshold=threshold,
        required_scope=milestone,
        # A receipt signature must have been made inside the signer's validity window.  Current
        # revocation remains fail-closed via the registry; ordinary key expiry does not rewrite a
        # previously valid signature into the future.
        now_us=emitted,
        verify_fn=verify_fn,
    )
    if not ok:
        # A missing signature / unavailable crypto is BLOCKED (owner must act); a present but
        # wrong/forged/threshold-short signer is FAIL.
        if reason in ("NO_EXTERNAL_SIGNATURES",) or reason.startswith("VERIFY_UNAVAILABLE"):
            return "BLOCKED", reason
        return "FAIL", reason
    return RESULT_PASS, "OK"


# --- source hashes -------------------------------------------------------------------------------
def parse_source_hashes(text: str) -> dict[str, str]:
    """Strict ``sha256sum``-style parse. Return {relpath: hex64}.

    Rejects blank/malformed lines, noncanonical (uppercase/short) hex, path escape, absolute
    paths, and duplicate paths (``NEG-002`` prerequisite).
    """
    out: dict[str, str] = {}
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip("\n")
        if line.strip() == "" or line.lstrip().startswith("#"):
            continue
        # sha256sum format: "<hex>␠␠<path>" (two spaces) or "<hex> *<path>".
        m = re.fullmatch(r"([0-9a-f]{64})\s[\s*](.+)", line)
        if m is None:
            raise GovernanceError(f"SOURCE_HASHES_MALFORMED_LINE:{lineno}:{line!r}")
        digest, rel = m.group(1), m.group(2)
        if not _safe_relpath(rel):
            raise GovernanceError(f"SOURCE_HASHES_UNSAFE_PATH:{rel!r}")
        if rel in out:
            raise GovernanceError(f"SOURCE_HASHES_DUPLICATE_PATH:{rel}")
        out[rel] = digest
    if not out:
        raise GovernanceError("SOURCE_HASHES_EMPTY")
    return out


# --- PR role classification ----------------------------------------------------------------------
RECEIPT_PATH_PREFIXES = ("evidence/",)
_CANONICAL_RECEIPT_RE = r"evidence/receipts/(B00R|B01C|B02C|B03C|B04C|B05C|B06R|B07)\.receipt\.v3\.json"
# A source PR may touch anything EXCEPT the evidence namespace; a receipt PR may touch ONLY the
# evidence namespace. Mixed content fails regardless of test results (``NEG-017``).


def classify_changed_paths(paths: list[str]) -> tuple[str, str]:
    """Return ``(role, reason)`` where role is ``SOURCE``, ``RECEIPT``, ``MIXED``, or ``EMPTY``."""
    if not paths:
        return "EMPTY", "no changed paths"
    receipt = [p for p in paths if any(p.startswith(pre) for pre in RECEIPT_PATH_PREFIXES)]
    source = [p for p in paths if p not in receipt]
    if receipt and source:
        return "MIXED", f"source+receipt in one PR: {source[:2]} & {receipt[:2]}"
    if receipt:
        receipt_files = [p for p in receipt if p.startswith("evidence/receipts/")]
        if len(receipt_files) != 1 or re.fullmatch(_CANONICAL_RECEIPT_RE, receipt_files[0]) is None:
            return "INVALID", "receipt PR requires exactly one canonical *.receipt.v3.json"
        match = re.fullmatch(_CANONICAL_RECEIPT_RE, receipt_files[0])
        milestone = match.group(1)
        allowed_prefix = f"evidence/{milestone}/"
        bad = [p for p in receipt if p != receipt_files[0] and not p.startswith(allowed_prefix)]
        if bad:
            return "INVALID", f"cross-milestone or historical evidence paths: {bad[:2]}"
        if any(p.endswith(".dsse.json") for p in receipt):
            return "INVALID", "DSSE filename unsupported by receipt-v3 canonical JSON profile"
        return "RECEIPT", f"milestone={milestone};receipt={receipt_files[0]}"
    return "SOURCE", f"{len(source)} source paths"


# --- governance snapshot -------------------------------------------------------------------------
def _parse_provider_utc_us(value: object) -> int:
    """Parse GitHub's UTC ISO-8601 timestamps without acquiring a runtime clock dependency."""
    if not isinstance(value, str):
        raise GovernanceError("GOVERNANCE_RAW_TIMESTAMP_NOT_STRING")
    match = re.fullmatch(
        r"([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})"
        r"(?:\.([0-9]{1,6}))?Z", value)
    if match is None:
        raise GovernanceError("GOVERNANCE_RAW_TIMESTAMP_NOT_CANONICAL_UTC")
    year, month, day, hour, minute, second = (int(match.group(i)) for i in range(1, 7))
    if year < 1970 or month < 1 or month > 12 or hour > 23 or minute > 59 or second > 59:
        raise GovernanceError("GOVERNANCE_RAW_TIMESTAMP_OUT_OF_RANGE")
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    month_days = (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    if day < 1 or day > month_days[month - 1]:
        raise GovernanceError("GOVERNANCE_RAW_TIMESTAMP_OUT_OF_RANGE")
    # Gregorian civil date -> days since 1970-01-01 (Howard Hinnant's integer algorithm).
    adjusted_year = year - (1 if month <= 2 else 0)
    era = adjusted_year // 400
    year_of_era = adjusted_year - era * 400
    shifted_month = month + (-3 if month > 2 else 9)
    day_of_year = (153 * shifted_month + 2) // 5 + day - 1
    day_of_era = year_of_era * 365 + year_of_era // 4 - year_of_era // 100 + day_of_year
    days = era * 146097 + day_of_era - 719468
    fraction = (match.group(7) or "").ljust(6, "0")
    micros = int(fraction) if fraction else 0
    return ((days * 86400 + hour * 3600 + minute * 60 + second) * 1_000_000 + micros)


def validate_governance_snapshot(
    doc: dict,
    *,
    provider_raw_bytes: bytes | None = None,
    external_pin: str | None = None,
    now_us: int | None = None,
    source_merge_time_us: int | None = None,
) -> tuple[str, str]:
    """Validate a provider governance snapshot. Return ``(result, reason)``.

    An unauthenticated template (``authenticated: false``) is fail-closed ``UNAVAILABLE``. A
    provider-authenticated snapshot must prove the no-bypass ruleset facts B00R requires.
    """
    try:
        validate_structure(doc, "triad.governance_snapshot.v1")
    except GovernanceError as exc:
        return "FAIL", str(exc)
    if doc.get("authenticated") is not True:
        return "UNAVAILABLE", "SNAPSHOT_UNAUTHENTICATED (owner/provider evidence absent)"
    if provider_raw_bytes is None or external_pin is None:
        return "UNAVAILABLE", "GOVERNANCE_PROVIDER_RAW_OR_EXTERNAL_PIN_ABSENT"
    if not isinstance(now_us, int) or isinstance(now_us, bool) or now_us <= 0:
        return "UNAVAILABLE", "GOVERNANCE_NOW_US_REQUIRED"
    provider = doc.get("provider")
    if not isinstance(provider, dict):
        return "FAIL", "GOVERNANCE_PROVIDER_EVIDENCE_MISSING"
    for key in ("name", "repository", "captured_at_us", "api_response_path",
                "api_response_sha256"):
        if key not in provider:
            return "FAIL", f"GOVERNANCE_PROVIDER_FIELD_MISSING:{key}"
    try:
        declared_pin = assert_hex64(provider.get("api_response_sha256"),
                                    "governance.provider.api_response_sha256")
        assert_hex64(external_pin, "governance.external_provider_pin")
    except GovernanceError as exc:
        return "FAIL", str(exc)
    actual_pin = sha256_hex(provider_raw_bytes)
    if actual_pin != declared_pin or actual_pin != external_pin:
        return "FAIL", "GOVERNANCE_PROVIDER_PIN_MISMATCH"
    if provider.get("name") != "github" or provider.get("repository") != "TriadAgentic/TriadOrigin":
        return "FAIL", "GOVERNANCE_PROVIDER_IDENTITY_MISMATCH"
    captured = provider.get("captured_at_us")
    effective = doc.get("effective_at_us")
    if (not isinstance(captured, int) or isinstance(captured, bool) or captured <= 0
            or captured > now_us):
        return "FAIL", "GOVERNANCE_CAPTURE_TIME_INVALID"
    if (not isinstance(effective, int) or isinstance(effective, bool) or effective <= 0
            or effective > captured):
        return "FAIL", "GOVERNANCE_EFFECTIVE_TIME_INVALID"
    if source_merge_time_us is not None:
        if (not isinstance(source_merge_time_us, int) or isinstance(source_merge_time_us, bool)
                or source_merge_time_us <= captured):
            return "FAIL", "GOVERNANCE_NOT_CAPTURED_BEFORE_SOURCE_MERGE"
    import json
    def _unique_object(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise GovernanceError(f"GOVERNANCE_PROVIDER_DUPLICATE_KEY:{key}")
            out[key] = value
        return out
    try:
        raw = json.loads(provider_raw_bytes, object_pairs_hook=_unique_object)
    except GovernanceError as exc:
        return "FAIL", str(exc)
    except (UnicodeError, ValueError, TypeError):
        return "FAIL", "GOVERNANCE_PROVIDER_RESPONSE_NOT_JSON"
    if not isinstance(raw, dict):
        return "FAIL", "GOVERNANCE_PROVIDER_RESPONSE_NOT_OBJECT"

    # A protected digest can authenticate bytes, but it cannot turn a hand-written template into
    # a GitHub API response. Require the stable provider identity fields emitted by
    # GET /repos/{owner}/{repo}/rulesets/{ruleset_id}, and reject local commentary explicitly.
    # This blocks the prior false-green where id="DECLARATIVE" plus a note saying enforcement was
    # pending was pinned and then accepted as an active no-bypass provider control.
    if "note" in raw or "note" in provider:
        return "FAIL", "GOVERNANCE_PROVIDER_SYNTHETIC_METADATA"
    raw_id = raw.get("id")
    if (not isinstance(raw_id, int) or isinstance(raw_id, bool) or raw_id <= 0):
        return "FAIL", "GOVERNANCE_RAW_RULESET_ID_NOT_PROVIDER_INTEGER"
    raw_name = raw.get("name")
    if (not isinstance(raw_name, str) or not raw_name.strip()
            or raw_name.strip().upper() in {"DECLARATIVE", "TEMPLATE", "PLACEHOLDER"}):
        return "FAIL", "GOVERNANCE_RAW_RULESET_NAME_NOT_PROVIDER"
    if raw.get("source_type") != "Repository":
        return "FAIL", "GOVERNANCE_RAW_SOURCE_TYPE_MISMATCH"
    if raw.get("current_user_can_bypass") != "never":
        return "FAIL", "GOVERNANCE_RAW_CURRENT_USER_BYPASS_NOT_NEVER"
    # node_id/_links are useful corroboration but optional in GitHub's published REST schema.
    # When present they must be provider-shaped and bind the same repository/ruleset identity.
    node_id = raw.get("node_id")
    if (node_id is not None
            and (not isinstance(node_id, str)
                 or re.fullmatch(r"RRS_[A-Za-z0-9_-]+", node_id) is None)):
        return "FAIL", "GOVERNANCE_RAW_NODE_ID_NOT_PROVIDER"
    links = raw.get("_links")
    if links is not None:
        self_link = links.get("self") if isinstance(links, dict) else None
        html_link = links.get("html") if isinstance(links, dict) else None
        expected_self = (
            f"https://api.github.com/repos/TriadAgentic/TriadOrigin/rulesets/{raw_id}"
        )
        expected_html = f"https://github.com/TriadAgentic/TriadOrigin/rules/{raw_id}"
        html_href = html_link.get("href") if isinstance(html_link, dict) else None
        if (not isinstance(self_link, dict) or self_link.get("href") != expected_self
                or html_href not in (None, expected_html)):
            return "FAIL", "GOVERNANCE_RAW_PROVIDER_LINKS_MISMATCH"
    try:
        created_us = _parse_provider_utc_us(raw.get("created_at"))
        updated_us = _parse_provider_utc_us(raw.get("updated_at"))
    except GovernanceError as exc:
        return "FAIL", str(exc)
    if not (created_us <= updated_us == effective <= captured):
        return "FAIL", "GOVERNANCE_EFFECTIVE_TIME_NOT_RAW_UPDATED_AT"

    # Derive every security-relevant fact from the raw GitHub ruleset response.  The normalized
    # snapshot is only an index; it may not authenticate itself by asserting booleans.
    if raw.get("target") != "branch" or raw.get("enforcement") != "active":
        return "FAIL", "GOVERNANCE_RAW_RULESET_NOT_ACTIVE_BRANCH"
    source = raw.get("source")
    if not isinstance(source, str) or source.lower() != "triadagentic/triadorigin":
        return "FAIL", "GOVERNANCE_RAW_RULESET_SOURCE_MISMATCH"
    if "bypass_actors" not in raw or raw.get("bypass_actors") != []:
        return "FAIL", "GOVERNANCE_RAW_BYPASS_NOT_PROVEN_EMPTY"
    conditions = raw.get("conditions")
    if not isinstance(conditions, dict):
        return "FAIL", "GOVERNANCE_RAW_CONDITIONS_MALFORMED"
    ref = conditions.get("ref_name", {})
    includes = ref.get("include") if isinstance(ref, dict) else None
    excludes = ref.get("exclude") if isinstance(ref, dict) else None
    canary_ref = "refs/heads/b00r-ruleset-canary"
    allowed_include_sets = (
        {"refs/heads/main", canary_ref},
    )
    # GitHub applies exclusions after inclusions.  Requiring an empty exclusion list prevents a
    # wildcard such as refs/heads/* from silently excluding main.  An explicit main ref is required;
    # ~DEFAULT_BRANCH could silently retarget if the repository default changes. The harmless canary
    # target is mandatory before the corrective source merge so the provider rejection can predate
    # that merge; it cannot be bolted on later without invalidating the closure chronology.
    if (not isinstance(includes, list)
            or not all(isinstance(item, str) for item in includes)
            or len(includes) != len(set(includes))
            or set(includes) not in allowed_include_sets or excludes != []):
        return "FAIL", "GOVERNANCE_RAW_MAIN_TARGET_NOT_PROVEN"
    raw_rules = raw.get("rules")
    if not isinstance(raw_rules, list):
        return "FAIL", "GOVERNANCE_RAW_RULES_MISSING"
    by_type: dict[str, list[dict]] = {}
    for rule in raw_rules:
        if not isinstance(rule, dict) or not isinstance(rule.get("type"), str):
            return "FAIL", "GOVERNANCE_RAW_RULE_MALFORMED"
        by_type.setdefault(rule["type"], []).append(rule)
    if len(by_type.get("pull_request", [])) != 1:
        return "FAIL", "GOVERNANCE_RAW_PULL_REQUEST_RULE_MISSING"
    pr = by_type["pull_request"][0].get("parameters", {})
    if not isinstance(pr, dict):
        return "FAIL", "GOVERNANCE_RAW_REVIEW_CONTROLS_MALFORMED"
    raw_approvals = pr.get("required_approving_review_count")
    if (not isinstance(raw_approvals, int) or isinstance(raw_approvals, bool)
            or raw_approvals < 1
            or pr.get("dismiss_stale_reviews_on_push") is not True
            or pr.get("require_code_owner_review") is not True
            or pr.get("require_last_push_approval") is not True
            or pr.get("required_review_thread_resolution") is not True):
        return "FAIL", "GOVERNANCE_RAW_REVIEW_CONTROLS_INCOMPLETE"
    if len(by_type.get("required_status_checks", [])) != 1:
        return "FAIL", "GOVERNANCE_RAW_STATUS_RULE_MISSING"
    status = by_type["required_status_checks"][0].get("parameters", {})
    if not isinstance(status, dict):
        return "FAIL", "GOVERNANCE_RAW_STATUS_CONTROL_MALFORMED"
    checks_raw = status.get("required_status_checks")
    if (not isinstance(checks_raw, list) or len(checks_raw) != 1
            or not isinstance(checks_raw[0], dict)):
        return "FAIL", "GOVERNANCE_RAW_STATUS_CHECKS_MALFORMED"
    contexts = [checks_raw[0].get("context")]
    integration_id = checks_raw[0].get("integration_id")
    if (status.get("strict_required_status_checks_policy") is not True
            or contexts != ["CI / test-and-verify"]
            or integration_id != GITHUB_ACTIONS_INTEGRATION_ID):
        return "FAIL", "GOVERNANCE_RAW_STATUS_CONTROL_MISMATCH"
    if len(by_type.get("deletion", [])) != 1 or len(by_type.get("non_fast_forward", [])) != 1:
        return "FAIL", "GOVERNANCE_RAW_HISTORY_CONTROLS_MISSING"
    ruleset = doc.get("ruleset", {})
    checks = (
        ("pull_request_required", ruleset.get("pull_request_required") is True),
        ("required_status_check",
         ruleset.get("required_status_check") == "CI / test-and-verify"),
        ("strict_required_status", ruleset.get("strict_required_status") is True),
        ("required_approvals", isinstance(ruleset.get("required_approvals"), int)
         and ruleset.get("required_approvals") >= 1),
        ("dismiss_stale_reviews", ruleset.get("dismiss_stale_reviews") is True),
        ("require_conversation_resolution",
         ruleset.get("require_conversation_resolution") is True),
        ("block_force_push", ruleset.get("block_force_push") is True),
        ("block_deletions", ruleset.get("block_deletions") is True),
        ("no_bypass_actors", not ruleset.get("bypass_actors")),
        ("targets_main", ruleset.get("target") in ("refs/heads/main", "~DEFAULT_BRANCH")),
        ("effective_time", isinstance(doc.get("effective_at_us"), int)),
        ("ruleset_id", str(raw.get("id")) == ruleset.get("ruleset_id")),
        ("raw_approvals", ruleset.get("required_approvals") == raw_approvals),
        ("raw_bypass", ruleset.get("bypass_actors") == raw.get("bypass_actors")),
    )
    failed = [name for name, ok in checks if not ok]
    if failed:
        return "FAIL", f"GOVERNANCE_CONTROL_MISSING:{failed}"
    return "PASS", "OK"
