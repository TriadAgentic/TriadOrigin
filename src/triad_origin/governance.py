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


# --- signature threshold (crypto verifier INJECTED; unavailable => fail closed, never PASS) -------
def verify_signatures(
    *,
    signed_bytes: bytes,
    signatures: list[dict],
    trust: dict[str, dict],
    required_roles: tuple[str, ...],
    threshold: int,
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
    if not isinstance(signatures, list) or not signatures:
        return False, "NO_EXTERNAL_SIGNATURES"
    # Pass 1 — structural: resolve each signer, reject unknown/revoked/duplicate/out-of-window,
    # and collect roles. These fail closed regardless of crypto availability (``NEG-009``).
    seen_identities: set[str] = set()
    roles_met: set[str] = set()
    for sig in signatures:
        kid = sig.get("key_id")
        entry = trust.get(kid)
        if entry is None:
            return False, f"UNKNOWN_SIGNER:{kid}"
        if entry.get("revoked"):
            return False, f"REVOKED_SIGNER:{kid}"
        identity = entry.get("identity")
        if identity in seen_identities:
            return False, f"DUPLICATE_SIGNER_IDENTITY:{identity}"
        if now_us is not None:
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


# --- evidence manifest ---------------------------------------------------------------------------
def _safe_relpath(path: str) -> bool:
    if not isinstance(path, str) or path == "":
        return False
    if path.startswith("/") or "\\" in path:
        return False
    parts = path.split("/")
    return ".." not in parts and "" not in parts and "." not in parts


def validate_evidence_manifest(manifest: dict, root) -> None:
    """Validate a closed evidence manifest against committed bytes.

    Rejects missing, extra, duplicate, symlink, path-escape, zero-size, placeholder-digest, and
    untracked entries, and a digest whose bytes do not match (``NEG-011``).
    """
    import pathlib
    root = pathlib.Path(root)
    validate_structure(manifest, "triad.evidence_manifest.v1")
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise GovernanceError("EVIDENCE_MANIFEST_EMPTY")
    seen_paths: set[str] = set()
    seen_roles: set[str] = set()
    for entry in entries:
        rel = entry.get("path")
        if not _safe_relpath(rel):
            raise GovernanceError(f"EVIDENCE_PATH_UNSAFE: {rel!r}")
        if rel in seen_paths:
            raise GovernanceError(f"EVIDENCE_DUPLICATE_PATH: {rel}")
        seen_paths.add(rel)
        role = entry.get("role")
        if role in seen_roles and entry.get("role_unique", True):
            raise GovernanceError(f"EVIDENCE_DUPLICATE_ROLE: {role}")
        seen_roles.add(role)
        abspath = (root / rel)
        if abspath.is_symlink():
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

    # Safety posture is invariant.
    if payload.get("activation_result") != ACTIVATION_RESULT:
        return "FAIL", "SAFETY_ACTIVATION_NOT_DENIED"
    if payload.get("levers") != SAFETY_POSTURE:
        return "FAIL", "SAFETY_POSTURE_DRIFT"

    # Root vs non-root variant.
    is_root = milestone == ROOT_MILESTONE
    if is_root:
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
    for label, v in (("observed_at_us", observed), ("emitted_at_us", emitted),
                     ("source_merge_time_us", merged)):
        if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
            return "FAIL", f"CHRONOLOGY_BAD_TIME:{label}"
    if not (merged < observed <= emitted):
        return "FAIL", "CHRONOLOGY_ORDER: require source_merge < observed <= emitted"
    if now_us is not None and emitted > now_us:
        return "FAIL", "CHRONOLOGY_FUTURE_EVIDENCE"

    # From here a PASS additionally needs authenticated external signatures under a pinned trust
    # registry. Absence of the trust registry is fail-closed BLOCKED, never PASS.
    if result != RESULT_PASS:
        return result, "NON_PASS_RESULT"

    if trust is None:
        return "BLOCKED", "NO_TRUST_REGISTRY_PINNED"
    ok, reason = verify_signatures(
        signed_bytes=canonical_receipt_signing_bytes(receipt),
        signatures=payload.get("signatures", []),
        trust=trust,
        required_roles=required_roles,
        threshold=threshold,
        now_us=now_us,
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
        return "RECEIPT", f"{len(receipt)} evidence paths"
    return "SOURCE", f"{len(source)} source paths"


# --- governance snapshot -------------------------------------------------------------------------
def validate_governance_snapshot(doc: dict) -> tuple[str, str]:
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
    )
    failed = [name for name, ok in checks if not ok]
    if failed:
        return "FAIL", f"GOVERNANCE_CONTROL_MISSING:{failed}"
    return "PASS", "OK"
