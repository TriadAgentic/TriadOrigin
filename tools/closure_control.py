#!/usr/bin/env python3
"""Fail-closed validation for the C0 closure semantics and generated status.

This checker is deliberately read-only.  It validates the canonical C0 data artifacts, their
Draft 2020-12 schemas, the digest/identity laws, the closed milestone graph and the generated
safe-hold status.  It also binds the B00R generation-2 source policy to the canonical B00R scope.

The JSON schemas are human-readable JSON.  The two governed data artifacts are exact canonical
JSON: accepting merely equivalent, pretty-printed JSON would make their byte identity ambiguous.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from triad_origin.canonical import CanonicalError, canonical_json, loads_canonical  # noqa: E402


SEMANTICS_SCHEMA_REL = pathlib.Path("docs/control/closure/closure_semantics.v1.schema.json")
SEMANTICS_REL = pathlib.Path("docs/control/closure/closure_semantics.v1.json")
STATUS_SCHEMA_REL = pathlib.Path("docs/control/closure/closure_status.v1.schema.json")
STATUS_REL = pathlib.Path("docs/control/closure/closure_status.v1.json")
STATUS_EVENTS_SCHEMA_REL = pathlib.Path("docs/control/closure/closure_status_events.v1.schema.json")
STATUS_EVENTS_REL = pathlib.Path("docs/control/closure/closure_status_events.v1.json")
TASK_BINDING_SCHEMA_REL = pathlib.Path("docs/control/closure/closure_task_bindings.v1.schema.json")
TASK_BINDING_REL = pathlib.Path("docs/control/closure/closure_task_bindings.v1.json")
B00R_POLICY_REL = pathlib.Path("docs/control/b00r_policy.v2.json")
BUILD_LEDGER_REL = pathlib.Path("docs/control/build_ledger.json")
BUILD_LEDGER_REVIEW_REL = pathlib.Path("docs/control/build_ledger_review.v1.json")
BUILD_LEDGER_REVIEW_SUBJECT_REL = pathlib.Path(
    "docs/control/closure/predecessors/build_ledger.REVIEWED_V2.json"
)
GENERATION_CONTEXT_SCHEMA_REL = pathlib.Path(
    "docs/control/closure/closure_generation_context.v1.schema.json"
)
GENERATION_CONTEXT_REL = pathlib.Path(
    "docs/control/closure/closure_generation_context.v1.json"
)
STATUS_DOC_REL = pathlib.Path("docs/plan/04_STATUS.md")
CHECKLIST_DOC_REL = pathlib.Path("docs/plan/08_BUILD_CHECKLIST.md")

SEMANTICS_SCHEMA = "triad.closure.semantics.v1"
SEMANTICS_DOMAIN = "triad.closure.semantics.artifact.v1"
STATUS_SCHEMA = "triad.closure.status.v1"
STATUS_DOMAIN = "triad.closure.status.artifact.v1"
STATUS_EVENTS_SCHEMA = "triad.closure.status_events.v1"
STATUS_EVENTS_DOMAIN = "triad.closure.status_events.artifact.v1"
STATUS_EVENT_DOMAIN = "triad.closure.status_event.v1"
TASK_BINDING_SCHEMA = "triad.closure.task_binding.v1"
TASK_BINDING_DOMAIN = "triad.closure.task_binding.artifact.v1"
SCOPE_DOMAIN = "triad.closure.milestone_scope.v1"
GENERATION_CONTEXT_SCHEMA = "triad.closure.generation_context.v1"
GENERATION_CONTEXT_DOMAIN = "triad.closure.generation_context.artifact.v1"

# The closed set of typed artifact-presence states.  PRESENCE IS NEVER CLOSURE: a controlling
# artifact that exists is ARTIFACT_PRESENT; a historical receipt that exists is
# HISTORICAL_RECEIPT_PRESERVED (preserved byte-unchanged, never a pass); a required-but-absent or
# unbound artifact is AUTHORITY_OPEN.  No presence fact may ever render as "passed" or a checked box.
PRESENCE_ARTIFACT_PRESENT = "ARTIFACT_PRESENT"
PRESENCE_HISTORICAL_RECEIPT_PRESERVED = "HISTORICAL_RECEIPT_PRESERVED"
PRESENCE_AUTHORITY_OPEN = "AUTHORITY_OPEN"
PRESENCE_STATES = (
    PRESENCE_ARTIFACT_PRESENT,
    PRESENCE_HISTORICAL_RECEIPT_PRESERVED,
    PRESENCE_AUTHORITY_OPEN,
)
# Controlling closure inputs whose on-disk presence the status doc states as ARTIFACT_PRESENT.
# Their presence is stat-derived (deterministic against the committed tree) and is NOT closure.
CONTROLLING_INPUT_ARTIFACT_RELS: tuple[pathlib.Path, ...] = (
    SEMANTICS_SCHEMA_REL,
    SEMANTICS_REL,
    STATUS_SCHEMA_REL,
    STATUS_EVENTS_SCHEMA_REL,
    STATUS_EVENTS_REL,
    TASK_BINDING_SCHEMA_REL,
    TASK_BINDING_REL,
    B00R_POLICY_REL,
    BUILD_LEDGER_REVIEW_SUBJECT_REL,
    GENERATION_CONTEXT_SCHEMA_REL,
    GENERATION_CONTEXT_REL,
)
CONTROLLING_INPUT_ARTIFACTS_SORTED: tuple[pathlib.Path, ...] = tuple(
    sorted(CONTROLLING_INPUT_ARTIFACT_RELS, key=lambda rel: rel.as_posix())
)

EXPECTED_MILESTONES: tuple[tuple[str, str], ...] = (
    ("CONTROL_FREEZE", "C0"),
    ("ORIGIN_REPAIR", "B00R_G2"),
    ("ORIGIN_REPAIR", "B01C"),
    ("ORIGIN_REPAIR", "B02C"),
    ("ORIGIN_REPAIR", "B03C"),
    ("ORIGIN_REPAIR", "B04C"),
    ("ORIGIN_REPAIR", "B05C"),
    ("ORIGIN_REPAIR", "B06R"),
    ("ORIGIN_REPAIR", "B07"),
    ("ESTATE_CROSS_REPO", "XC01"),
    ("ORIGIN_REPAIR", "B08"),
    ("ORIGIN_REPAIR", "B09"),
    ("ORIGIN_REPAIR", "B10"),
    ("ESTATE_CLOSURE", "BN"),
)

EXPECTED_PROFILE_IDS: Mapping[str, str] = {
    "B02C": "B02C_ACCEPTANCE_PROFILE_V1",
    "B03C": "B03C_ACCEPTANCE_PROFILE_V1",
    "B04C": "B04C_ACCEPTANCE_PROFILE_V1",
    "B05C": "B05C_ACCEPTANCE_PROFILE_V1",
    "B06R": "B06R_ACCEPTANCE_PROFILE_V1",
    "B07": "B07_ACCEPTANCE_PROFILE_V1",
    "XC01": "XC01_ACCEPTANCE_PROFILE_V1",
    "B08": "B08_ACCEPTANCE_PROFILE_V1",
    "B09": "B09_ACCEPTANCE_PROFILE_V1",
    "B10": "B10_ACCEPTANCE_PROFILE_V1",
}

EXPECTED_DECISIONS = tuple(f"D-{number:02d}" for number in range(1, 10))
EXPECTED_DECISION_RULES: Mapping[str, str] = {
    "D-01": "New milestones use track_id, milestone_id, and scope_digest; no new receipt may use a bare ambiguous B identifier.",
    "D-02": "B00R G2 owns repository governance, authority, provider chronology, receipt law, and the evidence root only; downstream formula, binding, contract, capability, runtime, and topology defects remain blocking at their owning milestones.",
    "D-03": "RC5_EFFECTIVE_CONSOLIDATION is additive over immutable RC3 and RC4 preimages; RC3 and RC4 bytes are never rewritten.",
    "D-04": "ORIGIN_REPAIR B10 is the terminal audit and seal; historical commodities and equities expansion is deferred to FUTURE_EXPANSION.",
    "D-05": "ESTATE_CLOSURE BN aggregates B10, G-1 through G9, cross-estate receipts, and fresh same-subject runtime evidence without granting activation authority.",
    "D-06": "The owner, author, or evidence producer cannot satisfy independent review; every final source and receipt head requires a separate reviewer and B10 requires two independent audits.",
    "D-07": "Normal execution remains post-only and maker-only; a separately bounded reduction-only emergency path remains unless signed replacement proof shows exposure cannot be stranded.",
    "D-08": "Repository closure preserves OFF/OFF/OFF/LIVE and authorizes no deployment, restart, PAPER, TESTNET, LIVE, venue effect, or arming.",
    "D-09": "Operational credentials never enter Git or evidence and must be rotated before B05 or B10 security attestation or any promotion.",
}
EXPECTED_CONFLICTS = tuple(f"C-{number:02d}" for number in range(1, 15))
EXPECTED_TEST_LAYERS = tuple(f"T{number}" for number in range(13))
NOT_APPLICABLE_CONTROL_FREEZE_RECEIPT = "NOT_APPLICABLE_CONTROL_FREEZE"
EXPECTED_B10_TERMINAL_CONTROL_SHA256 = (
    "5e785b9c6f04d5f2c0e41731950c822b2dff4e797ee0f93905349adfec63d31f"
)
EXPECTED_B10_ACCEPTANCE_PROFILE_SHA256 = (
    "58008b7c9ca69309c07cd7b6a030fdb35f7bd1c1f1ab2375197b5db5df514ca0"
)
EXPECTED_MILESTONE_PATH_LAWS_SHA256 = (
    "9f3fcb3109152cb3059a741de61a566dc91dd7f59760d1ce9b24aab65cd4a872"
)
EXPECTED_REVIEW_SUBJECT_SHA256 = (
    "78f6ce7254390997d54ce6732a46e138f24a56502677ba469dff22bf92f2b51e"
)
EXPECTED_REVIEW_SUBJECT_COMMIT = "b641edcf7e921e93030f681ae3e6339933f2bcc8"
EXPECTED_FORMULA_IDS = tuple(f"F{number:02d}" for number in range(24))
EXPECTED_INTERNAL_FORMULA_MILESTONES: Mapping[str, str] = {
    "F00": "B02C",
    **{f"F{number:02d}": "B03C" for number in range(2, 10) if number != 7},
    **{f"F{number:02d}": "B04C" for number in range(10, 18)},
    "F18": "B06R",
    "F19": "B06R",
}
# formula -> (owner engine, owner receipt slot, receipt milestone, conformance milestone)
EXPECTED_EXTERNAL_FORMULA_LAW: Mapping[str, tuple[str, str, str, str]] = {
    "F01": ("E01", "B02C-E01-F01", "B02C", "B02C"),
    "F07": ("E01", "B03C-E01-F07", "B03C", "B03C"),
    "F20": ("E08", "XC01-E08-F20", "XC01", "B09"),
    "F21": ("E09", "XC01-E09-F21-F22", "XC01", "B09"),
    "F22": ("E09", "XC01-E09-F21-F22", "XC01", "B09"),
    "F23": ("E10", "XC01-E10-F23", "XC01", "B09"),
}
EXPECTED_BLOCKER_SPECS: Mapping[str, tuple[str, str, str, str]] = {
    "B00R-G2-AUTHORITY-PINS": ("B00R_G2", "P0", "four authenticated G2 authority pins are absent", "D-02"),
    "B00R-G2-CANARY": ("B00R_G2", "P0", "rejected negative canary is NOT_ATTESTED", "T6"),
    "B00R-G2-EXACT-HEAD-REVIEW": ("B00R_G2", "P0", "B00R G2 exact-head review is UNBOUND", "review_policy:SOURCE_REVIEWER"),
    "B00R-G2-RECEIPT-ANCHOR": ("B00R_G2", "P0", "evidence-only receipt merge and protected anchor are absent", "T7"),
    "B00R-G2-RULESET": ("B00R_G2", "P0", "real live provider ruleset capture and external pin are NOT_ATTESTED", "T6"),
    "B02C-E01-OWNER-RECEIPT": ("B02C", "P0", "E01 F01 owner-repository receipt slot is UNBOUND and NOT_ATTESTED", "B02C_ACCEPTANCE_PROFILE_V1"),
    "B03C-E01-OWNER-RECEIPT": ("B03C", "P0", "E01 F07 owner-repository receipt slot is UNBOUND and NOT_ATTESTED", "B03C_ACCEPTANCE_PROFILE_V1"),
    "B05-AUTHORIZATION": ("B05C", "P0", "deployment and restart remain unauthorized", "D-08"),
    "B05-CREDENTIAL-ROTATION": ("B05C", "P0", "D-09 credential rotation is NOT_ATTESTED", "D-09"),
    "B05-PHYSICAL-ISOLATION-SOAK": ("B05C", "P0", "physical four-plane isolation and 24-hour SHADOW soak are NOT_ATTESTED", "T8:T9"),
    "B09-CONFORMANCE-DR": ("B09", "P0", "unique conformance and disaster-recovery owner proofs are NOT_ATTESTED", "T10:T11"),
    "B10-CREDENTIAL-GATE": ("B10", "P0", "D-09 credential rotation/security gate is NOT_ATTESTED", "D-09"),
    "B10-FROZEN-SUBJECT": ("B10", "P0", "B10 terminal subject registry is not frozen", "b10_terminal_control"),
    "B10-TWO-AUDITS": ("B10", "P0", "two distinct B10 auditor slots and adjudicator are UNBOUND", "b10_terminal_control"),
    "BN-FRESH-AGGREGATE": ("BN", "P0", "fresh identical-subject runtime and money-ledger aggregate is NOT_ATTESTED", "D-05:T8:T10"),
    "C0-EXACT-HEAD-REVIEW": ("C0", "P0", "C0 exact-head source review is UNBOUND", "review_policy:SOURCE_REVIEWER"),
    "C0-CURRENT-LEDGER-REVIEW": ("C0", "P0", "current CANDIDATE_V3 ledger has 94 rows changed since the frozen REVIEWED_V2 subject", "closure_task_bindings.v1.json:review_coverage"),
    "C0-OWNER-AUTH": ("C0", "P0", "C0 owner authentication is UNBOUND", "review_policy:C0_OWNER_AUTHENTICATOR"),
    "C0-TARGET-ALLOCATION-REVIEW": ("C0", "P0", "current task target allocations have no independently authenticated review", "closure_task_bindings.v1.json:target_allocation_review_state"),
    "LEGACY_B00_REALLOCATION_REQUIRED": ("C0", "P0", "legacy B00 tasks require explicit owner reallocation", "closure_task_bindings.v1.json"),
    "XC01-OWNER-RECEIPTS": ("XC01", "P0", "owner-repository receipt slots are UNBOUND and NOT_ATTESTED", "XC01_ACCEPTANCE_PROFILE_V1"),
}
EXPECTED_STATUS_EVENT_PREFIX_DIGESTS: tuple[str, ...] = (
    "8d02c050e76c9ba3132642736033939aca1ddd7ec438b8a44bf5a708d1bb6571",
    "8d0668ab8e70fe8ef4f13ea6ca99ea9116854bdacd5b2b529d5ab36c7c3b0ff7",
    "48aeda74961b04b55e7e9f94912736eed35b6380b243c1bcfae101c9b096f164",
    "b82aba34e5b1c666aba0fb663d81fc1ff3b1ae5420e65a3ea6a2e10241a8ce8f",
)
# legacy_ref -> (target kind, current milestone, disposition, receipt path, receipt SHA-256,
# receipt-scope SHA-256, receipt's own historical milestone token).  ``current milestone`` is None
# for historical-only and future-track rows.  These constants stop a self-consistent rewrite from
# silently aliasing an old receipt to a different new milestone.
EXPECTED_LEGACY_BINDINGS: Mapping[
    str, tuple[str, str | None, str, str | None, str | None, str | None, str | None]
] = {
    "R00": (
        "HISTORICAL_ONLY", None, "HISTORICAL_ONLY_INVALIDATED", "evidence/receipts/R00.json",
        "b1ea0b353637070dcc0d1b56bd01d43e856b86d830a73ccbbd4141fb5330687f",
        "9781e8e22ccb4863bd43f710a1f3754179e025809ba4e342f12410ddd0ffbcd8", "R00",
    ),
    "B00": (
        "COMPOSITE_IDENTITY", "B00R_G2", "FORWARD_REPAIR_SUCCESSOR",
        "evidence/receipts/B00.json",
        "2b0518ea0f9540b63ff8d771a131597da34c2acb3452d171020cd70bbc386877",
        "15a8b32df046cf1215397641850f0cca1d0ac5c5f6929171b6500c1f3140fd6e", "B00",
    ),
    "B00C": (
        "COMPOSITE_IDENTITY", "B00R_G2", "FORWARD_REPAIR_SUCCESSOR",
        "evidence/receipts/B00C.json",
        "b5f89dbf6cb27f90c9ab7a731baea91044abb2b21709607e9f29741fdc2abcf9",
        "dfbdfac2770eb21c65358e86100ef897aea43a6d43a7fd85ec9564f868b81a13", "B00C",
    ),
    "B00R_GENERATION_1": (
        "HISTORICAL_ONLY", None, "HISTORICAL_ONLY_INVALIDATED",
        "evidence/receipts/B00R.receipt.v3.json",
        "f1328ceb29a8730be93f4fd47d295ac96ef514a747385ab500256d6fa52a7cca",
        "caf2a2ee2ff7837e6285f8549b64c3b09603a6e4e82a321052d55817a8ddc56d", "B00R",
    ),
    "B01": (
        "COMPOSITE_IDENTITY", "B01C", "FORWARD_REPAIR_SUCCESSOR",
        "evidence/receipts/B01.json",
        "d456e673a82a12786a89bae1dc302f9e3a013f295962e0db8e80294241613cc6",
        "ab4d544de7056656c11f8194719be47397a8bf94bb034a64c32ef87b5355a302", "B01",
    ),
    "B01R": (
        "COMPOSITE_IDENTITY", "B01C", "FORWARD_REPAIR_SUCCESSOR",
        "evidence/receipts/B01R.json",
        "510dc65d3c2e6586a7370e5db1629624796459b4335d960e2b20380584dce6ea",
        "b94f13304e22985f483000cc20a7caa42ace6519c752866d925a4c7d050689d7", "B01R",
    ),
    "B02": (
        "COMPOSITE_IDENTITY", "B02C", "FORWARD_REPAIR_SUCCESSOR",
        "evidence/receipts/B02.json",
        "63df9ba2d52e2701af57adfbf9d46cdc64a87db0b411ea36885291373a3b7679",
        "9d3e42be33012a59efec262904053c2129773657cead2709395d49de2c02e4c1", "B02",
    ),
    "B03": (
        "COMPOSITE_IDENTITY", "B03C", "FORWARD_REPAIR_SUCCESSOR",
        "evidence/receipts/B03.json",
        "25486baaf425c281003ce1b7f40b6ffeb60f0f8dd8ce19cf9f76640561099fec",
        "b612c5a6e49d4f868929f3ff2d7cddfea10b3894b910e7a88334bf8114038240", "B03",
    ),
    "B04": (
        "COMPOSITE_IDENTITY", "B04C", "FORWARD_REPAIR_SUCCESSOR",
        "evidence/receipts/B04.json",
        "e235eeaf5739fb3b5a49be0abb24bf16c2a488b85a1c68948704b5f08c1f83c5",
        "3f489548cbd838cf6fedc96d7ea2b921ccc268b09309b7bb906c2f7788a03fa3", "B04",
    ),
    "B05": (
        "COMPOSITE_IDENTITY", "B05C", "FORWARD_REPAIR_SUCCESSOR",
        "evidence/receipts/B05.json",
        "2ba214fdcf3971e9dd9cfd7bf51324c6fbcfd871071e89b8d19e8977a7aadbb0",
        "cf918213ef81ea82ad0595bd9a6079b2e22fbe5d2110337f545d6cd57aedeebd", "B05",
    ),
    "B06": (
        "COMPOSITE_IDENTITY", "B06R", "FORWARD_REPAIR_SUCCESSOR",
        "evidence/receipts/B06.json",
        "2656ed5ce2a52fd6ff1230b2be7d5c0c233b16fe20fe7731d39fa5222261f928",
        "a6612d817a98e2d9c2d9610a8f85d15e8badad068b85dcb08537298eecab3d2d", "B06",
    ),
    "B07": (
        "COMPOSITE_IDENTITY", "B07", "FORWARD_REPAIR_SUCCESSOR",
        "evidence/receipts/B07.json",
        "5a8939f35d133f2965846eb03f4fd409ad7d33d030ee87312dbff7d9d4ae34e4",
        "533e6a38e284c8a4b2db34b46c8618ccfb6661a8f1ff6162de22241ed30870e1", "B07",
    ),
    "B08": ("COMPOSITE_IDENTITY", "B08", "PRESERVED_CURRENT_MEANING", None, None, None, None),
    "B09": ("COMPOSITE_IDENTITY", "B09", "PRESERVED_CURRENT_MEANING", None, None, None, None),
    "B10": ("FUTURE_TRACK", None, "DEFERRED_EXPANSION", None, None, None, None),
    "B10_EXPANSION": (
        "FUTURE_TRACK", None, "DEFERRED_EXPANSION", None, None, None, None,
    ),
    "BN": ("COMPOSITE_IDENTITY", "BN", "FORWARD_REPAIR_SUCCESSOR", None, None, None, None),
}
SAFE_HOLD = {
    "venue_environment": "OFF",
    "venue_activation": "OFF",
    "paper_activation": "OFF",
    "shadow_activation": "LIVE",
}

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "private-key-material",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    ),
    (
        "github-token",
        re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    ),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{16,}\b")),
    ("openai-style-key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("triad-mcp-token", re.compile(r"\btmc_[A-Za-z0-9_-]{16,}\b")),
    (
        "bearer-credential",
        re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{20,}"),
    ),
    (
        "assigned-credential",
        re.compile(
            r"(?i)\b(?:api[_ -]?key|access[_ -]?token|client[_ -]?secret|password)"
            r"\s*[:=]\s*[\"']?[A-Za-z0-9._~+/=-]{16,}"
        ),
    ),
    (
        "query-credential",
        re.compile(r"(?i)[?&](?:token|api_key|secret)=[A-Za-z0-9._~+/=-]{8,}"),
    ),
)


class ClosureControlError(ValueError):
    """Raised when a C0 control invariant fails."""


def _fail(code: str, detail: str) -> None:
    raise ClosureControlError(f"{code}: {detail}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("DUPLICATE_JSON_KEY", repr(key))
        result[key] = value
    return result


def _reject_float(token: str) -> Any:
    _fail("FLOAT_FORBIDDEN", token)


def load_json_object(path: pathlib.Path) -> dict[str, Any]:
    """Load noncanonical supporting JSON while rejecting ambiguous JSON constructs."""

    try:
        text = path.read_text(encoding="utf-8")
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_float=_reject_float,
            parse_constant=_reject_float,
        )
    except ClosureControlError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        _fail("JSON_LOAD_FAILED", f"{path}: {exc}")
    if not isinstance(value, dict):
        _fail("JSON_ROOT_NOT_OBJECT", str(path))
    return value


def load_canonical_object(path: pathlib.Path) -> dict[str, Any]:
    """Load an exact canonical JSON object, rejecting whitespace and equivalent encodings."""

    try:
        value = loads_canonical(path.read_bytes())
    except (OSError, CanonicalError) as exc:
        _fail("NONCANONICAL_CONTROL_ARTIFACT", f"{path}: {exc}")
    if not isinstance(value, dict):
        _fail("CONTROL_ROOT_NOT_OBJECT", str(path))
    return value


def _sha256_canonical(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def compute_envelope_digest(document: Mapping[str, Any], domain: str) -> str:
    """Compute the declared C0 envelope digest from its normative four-field preimage."""

    try:
        preimage = {
            "domain": domain,
            "schema": document["schema"],
            "version": document["version"],
            "payload": document["payload"],
        }
    except KeyError as exc:
        _fail("ENVELOPE_FIELD_MISSING", str(exc))
    return _sha256_canonical(preimage)


def scope_digest(scope: Mapping[str, Any]) -> str:
    """Return ``sha256(canonical_json(scope))`` under the scope's frozen domain field."""

    if scope.get("domain") != SCOPE_DOMAIN:
        _fail("SCOPE_DOMAIN_MISMATCH", repr(scope.get("domain")))
    return _sha256_canonical(scope)


def composite_id(scope: Mapping[str, Any]) -> str:
    digest = scope_digest(scope)
    try:
        track = scope["track_id"]
        milestone = scope["milestone_id"]
    except KeyError as exc:
        _fail("SCOPE_ID_FIELD_MISSING", str(exc))
    if not isinstance(track, str) or not isinstance(milestone, str):
        _fail("SCOPE_ID_FIELD_INVALID", "track_id and milestone_id must be strings")
    return f"{track}::{milestone}::sha256:{digest}"


def _require_digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None or value == "0" * 64:
        _fail("INVALID_SHA256", label)
    return value


def _require_sorted_unique_strings(values: Any, label: str, *, allow_empty: bool = False) -> None:
    if not isinstance(values, list) or (not allow_empty and not values):
        _fail("SET_FIELD_INVALID", f"{label} must be a{' nonempty' if not allow_empty else ''} list")
    if any(not isinstance(value, str) or not value for value in values):
        _fail("SET_FIELD_INVALID", f"{label} contains a non-string or empty member")
    if values != sorted(set(values)):
        _fail("SET_FIELD_NOT_CANONICAL", f"{label} must be sorted and unique")


def _require_canonical_repo_relative_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        _fail("PROFILE_REQUIRED_ARTIFACT_PATH_INVALID", label)
    path = pathlib.PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or ".." in path.parts
        or path.as_posix() != value
    ):
        _fail("PROFILE_REQUIRED_ARTIFACT_PATH_INVALID", label)
    return value


def validate_schema(schema: Mapping[str, Any], instance: Any, label: str) -> None:
    """Self-check and apply an exact Draft 2020-12 schema, failing closed if unavailable."""

    try:
        from jsonschema import Draft202012Validator
        from jsonschema.exceptions import SchemaError
    except ImportError as exc:  # pragma: no cover - exercised in a dependency-starved runner
        _fail("SCHEMA_VALIDATOR_UNAVAILABLE", str(exc))
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        _fail("WRONG_JSON_SCHEMA_DIALECT", label)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        _fail("SCHEMA_SELF_VALIDATION_FAILED", f"{label}: {exc.message}")
    errors = sorted(Draft202012Validator(schema).iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        error = errors[0]
        location = "/".join(str(part) for part in error.absolute_path) or "<root>"
        _fail("SCHEMA_INSTANCE_INVALID", f"{label}:{location}: {error.message}")


def validate_envelope(document: Mapping[str, Any], expected_schema: str, domain: str) -> str:
    if document.get("schema") != expected_schema or document.get("version") != "1":
        _fail("ENVELOPE_IDENTITY_MISMATCH", expected_schema)
    digest = document.get("digest")
    if not isinstance(digest, dict):
        _fail("DIGEST_ENVELOPE_MISSING", expected_schema)
    declared = _require_digest(digest.get("value"), f"{expected_schema}.digest.value")
    if digest.get("domain") != domain:
        _fail("DIGEST_DOMAIN_MISMATCH", expected_schema)
    actual = compute_envelope_digest(document, domain)
    if declared != actual:
        _fail("ARTIFACT_DIGEST_MISMATCH", f"{expected_schema}: {declared} != {actual}")
    return actual


def _milestone_maps(
    semantics: Mapping[str, Any],
) -> tuple[list[Mapping[str, Any]], dict[tuple[str, str], Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    milestones = semantics["payload"]["milestones"]
    if not isinstance(milestones, list):
        _fail("MILESTONE_REGISTRY_INVALID", "not an array")
    by_key: dict[tuple[str, str], Mapping[str, Any]] = {}
    by_identity: dict[str, Mapping[str, Any]] = {}
    for row in milestones:
        if not isinstance(row, dict) or not isinstance(row.get("scope"), dict):
            _fail("MILESTONE_ROW_INVALID", repr(row))
        scope = row["scope"]
        key = (scope.get("track_id"), scope.get("milestone_id"))
        identity = row.get("identity")
        if key in by_key or identity in by_identity:
            _fail("DUPLICATE_MILESTONE", repr(key))
        by_key[key] = row
        by_identity[identity] = row
    return milestones, by_key, by_identity


def _validate_dependency_dag(rows: Sequence[Mapping[str, Any]], identities: set[str]) -> None:
    graph: dict[str, tuple[str, ...]] = {}
    for row in rows:
        identity = row["identity"]
        dependencies = tuple(row["dependency_identities"])
        for dependency in dependencies:
            if dependency not in identities or dependency == identity:
                _fail("INVALID_MILESTONE_DEPENDENCY", f"{identity} -> {dependency}")
        graph[identity] = dependencies

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(identity: str) -> None:
        if identity in visiting:
            _fail("MILESTONE_DEPENDENCY_CYCLE", identity)
        if identity in visited:
            return
        visiting.add(identity)
        for dependency in graph[identity]:
            visit(dependency)
        visiting.remove(identity)
        visited.add(identity)

    for identity in graph:
        visit(identity)


def validate_milestones(semantics: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    rows, by_key, by_identity = _milestone_maps(semantics)
    actual_order = tuple(
        (row["scope"]["track_id"], row["scope"]["milestone_id"]) for row in rows
    )
    if actual_order != EXPECTED_MILESTONES or set(by_key) != set(EXPECTED_MILESTONES):
        _fail("MILESTONE_SET_OR_ORDER_MISMATCH", repr(actual_order))

    previous_identity: str | None = None
    for row, expected_key in zip(rows, EXPECTED_MILESTONES, strict=True):
        scope = row["scope"]
        if (scope["track_id"], scope["milestone_id"]) != expected_key:
            _fail("MILESTONE_SCOPE_ID_MISMATCH", repr(expected_key))
        calculated_scope_digest = scope_digest(scope)
        declared_scope_digest = row["scope_digest"]
        if declared_scope_digest.get("value") != calculated_scope_digest:
            _fail("SCOPE_DIGEST_MISMATCH", repr(expected_key))
        identity = composite_id(scope)
        if row["identity"] != identity:
            _fail("COMPOSITE_IDENTITY_MISMATCH", repr(expected_key))
        if row["predecessor_identity"] != previous_identity:
            _fail("PREDECESSOR_CHAIN_MISMATCH", identity)
        _require_sorted_unique_strings(scope["owns"], f"{identity}.scope.owns")
        _require_sorted_unique_strings(scope["excludes"], f"{identity}.scope.excludes")
        _require_sorted_unique_strings(row["exclusions"], f"{identity}.exclusions")
        _require_sorted_unique_strings(
            row["dependency_identities"], f"{identity}.dependency_identities", allow_empty=True
        )
        if previous_identity is not None and previous_identity not in row["dependency_identities"]:
            _fail("PREDECESSOR_NOT_A_DEPENDENCY", identity)
        previous_identity = identity

    _validate_dependency_dag(rows, set(by_identity))
    aggregate_path_laws = {
        f"{row['scope']['track_id']}::{row['scope']['milestone_id']}": row["path_law"]
        for row in rows
    }
    if _sha256_canonical(aggregate_path_laws) != EXPECTED_MILESTONE_PATH_LAWS_SHA256:
        _fail("MILESTONE_PATH_LAW_DIGEST_MISMATCH", "aggregate path-law mapping")
    xc01_identity = by_key[("ESTATE_CROSS_REPO", "XC01")]["identity"]
    b08_identity = by_key[("ORIGIN_REPAIR", "B08")]["identity"]
    b10_identity = by_key[("ORIGIN_REPAIR", "B10")]["identity"]
    expected_direct_dependencies = {
        ("ORIGIN_REPAIR", "B08"): {xc01_identity},
        ("ORIGIN_REPAIR", "B09"): {b08_identity, xc01_identity},
        ("ESTATE_CLOSURE", "BN"): {b10_identity, xc01_identity},
    }
    for key, expected_dependencies in expected_direct_dependencies.items():
        actual_dependencies = set(by_key[key]["dependency_identities"])
        if actual_dependencies != expected_dependencies:
            _fail(
                "XC01_DIRECT_DEPENDENCY_LAW_MISMATCH",
                f"{key!r}: {sorted(actual_dependencies)!r}",
            )
    xc01 = by_key[("ESTATE_CROSS_REPO", "XC01")]
    expected_xc01_path_law = {
        "adoption_manifest": "docs/control/adoption/XC01.v1.json",
        "anchor": "XC01_RECEIPT_ANCHOR",
        "source_receipt": "evidence/receipts/XC01.receipt.v4.json",
    }
    if xc01["path_law"] != expected_xc01_path_law:
        _fail("XC01_PATH_LAW_MISMATCH", repr(xc01["path_law"]))
    expected_bn_aggregate = [{
        "anchor": expected_xc01_path_law["anchor"],
        "milestone_identity": xc01_identity,
        "source_receipt": expected_xc01_path_law["source_receipt"],
    }]
    if by_key[("ESTATE_CLOSURE", "BN")].get("aggregate_receipt_dependencies") != expected_bn_aggregate:
        _fail("BN_XC01_RECEIPT_AGGREGATE_MISMATCH", "aggregate_receipt_dependencies")
    return by_key


def validate_decisions(semantics: Mapping[str, Any]) -> None:
    decisions = semantics["payload"]["decisions"]
    ids = tuple(row.get("decision_id") for row in decisions)
    if ids != EXPECTED_DECISIONS or len(set(ids)) != len(ids):
        _fail("DECISION_SET_OR_ORDER_MISMATCH", repr(ids))
    for row in decisions:
        if row.get("status") != "CONFIRMED" or row.get("cryptographic_authentication") != "NOT_CLAIMED":
            _fail("DECISION_AUTHORITY_OVERCLAIM", str(row.get("decision_id")))
        if row.get("controlling_rule") != EXPECTED_DECISION_RULES[row["decision_id"]]:
            _fail("DECISION_RULE_MISMATCH", row["decision_id"])


def validate_conflicts(
    semantics: Mapping[str, Any],
    milestones: Mapping[tuple[str, str], Mapping[str, Any]],
) -> None:
    payload = semantics["payload"]
    conflicts = payload["conflict_dispositions"]
    ids = tuple(row.get("conflict_id") for row in conflicts)
    if ids != EXPECTED_CONFLICTS or len(set(ids)) != len(ids):
        _fail("CONFLICT_SET_OR_ORDER_MISMATCH", repr(ids))
    known_identities = {row["identity"] for row in milestones.values()}
    for row in conflicts:
        _require_sorted_unique_strings(
            row["controlling_basis"], f"{row['conflict_id']}.controlling_basis"
        )
        if row["severity"] in {"P0", "P1"}:
            if row["blocking"] is not True or row["waiver_status"] != "NOT_WAIVED":
                _fail("P0_P1_CONFLICT_WAIVER", row["conflict_id"])
        elif row["waiver_status"] not in {"NOT_WAIVED", "NOT_APPLICABLE"}:
            _fail("CONFLICT_WAIVER_STATUS_INVALID", row["conflict_id"])
        if row["owner_identity"] not in known_identities:
            _fail("CONFLICT_OWNER_UNKNOWN", row["conflict_id"])

    blocked_rule = payload["state_machine"]["blocked_rule"]
    normalized = blocked_rule.upper().replace("-", "_")
    if "P0" not in normalized or "P1" not in normalized or "WAIVER" not in normalized:
        _fail("P0_P1_NON_WAIVER_LAW_MISSING", blocked_rule)


def validate_profiles(
    semantics: Mapping[str, Any], milestones: Mapping[tuple[str, str], Mapping[str, Any]]
) -> None:
    profiles = semantics["payload"]["acceptance_profiles"]
    by_id = {row.get("profile_id"): row for row in profiles}
    if set(by_id) != set(EXPECTED_PROFILE_IDS.values()) or len(by_id) != len(profiles):
        _fail("ACCEPTANCE_PROFILE_SET_MISMATCH", repr(tuple(by_id)))

    known_identities = {row["identity"] for row in milestones.values()}
    for milestone_id, profile_id in EXPECTED_PROFILE_IDS.items():
        track_id = "ESTATE_CROSS_REPO" if milestone_id == "XC01" else "ORIGIN_REPAIR"
        milestone = milestones[(track_id, milestone_id)]
        profile = by_id[profile_id]
        if profile["milestone_identity"] != milestone["identity"]:
            _fail("PROFILE_MILESTONE_MISMATCH", profile_id)
        if milestone["profile_ref"] != profile_id:
            _fail("MILESTONE_PROFILE_REF_MISMATCH", milestone_id)
        if profile["required_independent_reviews"] != milestone["required_independent_reviews"]:
            _fail("PROFILE_REVIEW_QUORUM_MISMATCH", profile_id)
        if profile["owned_scope"] != milestone["scope"]["owns"]:
            _fail("PROFILE_OWNED_SCOPE_MISMATCH", profile_id)
        if profile["excluded_scope"] != milestone["exclusions"]:
            _fail("PROFILE_EXCLUDED_SCOPE_MISMATCH", profile_id)
        predecessor = milestone["predecessor_identity"]
        if predecessor not in profile["prerequisite_identities"]:
            _fail("PROFILE_PREDECESSOR_MISSING", profile_id)
        if any(identity not in known_identities for identity in profile["prerequisite_identities"]):
            _fail("PROFILE_PREREQUISITE_UNKNOWN", profile_id)
        required_artifacts = profile.get("required_artifacts")
        if not isinstance(required_artifacts, list):
            _fail("PROFILE_REQUIRED_ARTIFACT_PATH_INVALID", profile_id)
        for index, artifact in enumerate(required_artifacts):
            _require_canonical_repo_relative_path(
                artifact, f"{profile_id}.required_artifacts[{index}]"
            )
        for field in (
            "owned_scope",
            "excluded_scope",
            "prerequisite_identities",
            "required_artifacts",
            "targeted_tests",
            "cumulative_tests",
            "external_tests",
            "external_evidence",
            "work_packages",
            "acceptance_criteria",
            "attack_vectors",
        ):
            _require_sorted_unique_strings(profile[field], f"{profile_id}.{field}")
        adoption_manifest = profile["adoption_manifest"]
        path = pathlib.PurePosixPath(adoption_manifest)
        if (
            not isinstance(adoption_manifest, str)
            or not adoption_manifest
            or path.is_absolute()
            or ".." in path.parts
            or path.as_posix() != adoption_manifest
        ):
            _fail("PROFILE_ADOPTION_MANIFEST_PATH_INVALID", profile_id)
        if adoption_manifest != milestone["path_law"]["adoption_manifest"]:
            _fail("PROFILE_ADOPTION_MANIFEST_MISMATCH", profile_id)

        owner_slots = profile.get("owner_repo_receipt_slots")
        expected_slots_by_milestone: Mapping[str, Mapping[str, tuple[str, tuple[str, ...]]]] = {
            "B02C": {
                "B02C-E01-F01": ("E01", ("F01",)),
            },
            "B03C": {
                "B03C-E01-F07": ("E01", ("F07",)),
            },
            "XC01": {
                "XC01-E08-F20": ("E08", ("F20",)),
                "XC01-E09-F21-F22": ("E09", ("F21", "F22")),
                "XC01-E10-F23": ("E10", ("F23",)),
            },
        }
        expected_slots = expected_slots_by_milestone.get(milestone_id)
        if expected_slots is not None:
            if not isinstance(owner_slots, list) or len(owner_slots) != len(expected_slots):
                _fail("OWNER_RECEIPT_SLOT_SET_MISMATCH", f"{milestone_id}:{owner_slots!r}")
            actual_slots = {
                slot.get("receipt_slot_id"): (
                    slot.get("owner_engine"), tuple(slot.get("formula_ids", ()))
                )
                for slot in owner_slots
            }
            if actual_slots != expected_slots:
                _fail("OWNER_RECEIPT_SLOT_SET_MISMATCH", f"{milestone_id}:{actual_slots!r}")
            for slot in owner_slots:
                if (
                    slot.get("provider_binding_state") != "UNBOUND"
                    or slot.get("attestation_state") != "NOT_ATTESTED"
                ):
                    _fail("OWNER_RECEIPT_SLOT_OVERCLAIM", slot["receipt_slot_id"])
            if milestone_id == "XC01":
                required_tokens = {
                    "WAVE-C-001", "WAVE-C-005", "WAVE-C-006", "E08", "E09", "E10",
                    "F20", "F21", "F22", "F23",
                }
                profile_text = canonical_json(profile).decode("utf-8")
                missing = sorted(token for token in required_tokens if token not in profile_text)
                if missing:
                    _fail("XC01_ACCEPTANCE_REQUIREMENT_MISSING", repr(missing))
                if "proxy" not in profile["failure_policy"].lower() and not any(
                    "proxy" in value.lower() for value in profile["excluded_scope"]
                ):
                    _fail("XC01_PROXY_EVIDENCE_LAW_MISSING", profile_id)
        elif owner_slots is not None:
            _fail("OWNER_RECEIPT_SLOTS_OUTSIDE_OWNER_MILESTONE", profile_id)
        if (
            profile_id == "B10_ACCEPTANCE_PROFILE_V1"
            and _sha256_canonical(profile) != EXPECTED_B10_ACCEPTANCE_PROFILE_SHA256
        ):
            _fail("B10_ACCEPTANCE_PROFILE_DIGEST_MISMATCH", profile_id)


def validate_test_matrix(
    semantics: Mapping[str, Any], milestones: Mapping[tuple[str, str], Mapping[str, Any]]
) -> None:
    payload = semantics["payload"]
    layers = payload["test_layers"]
    layer_ids = tuple(row.get("layer_id") for row in layers)
    if layer_ids != EXPECTED_TEST_LAYERS or len(set(layer_ids)) != len(layer_ids):
        _fail("TEST_LAYER_SET_OR_ORDER_MISMATCH", repr(layer_ids))

    expected_identities = tuple(milestones[key]["identity"] for key in EXPECTED_MILESTONES)
    matrix = payload["test_layer_matrix"]
    matrix_identities = tuple(row.get("milestone_identity") for row in matrix)
    if matrix_identities != expected_identities or len(set(matrix_identities)) != len(matrix_identities):
        _fail("TEST_MATRIX_MILESTONE_SET_OR_ORDER_MISMATCH", repr(matrix_identities))

    rows_by_identity = {row["milestone_identity"]: row for row in matrix}
    milestones_by_identity = {row["identity"]: row for row in milestones.values()}
    for identity, row in rows_by_identity.items():
        if set(row["layers"]) != set(EXPECTED_TEST_LAYERS):
            _fail("TEST_MATRIX_LAYER_SET_MISMATCH", identity)
        modes = tuple(row["layers"].values())
        if all(mode == "NOT_APPLICABLE" for mode in modes):
            _fail("TEST_MATRIX_EMPTY_ROW", identity)
        receipt_layer_not_applicable = row["layers"]["T7"] == "NOT_APPLICABLE"
        receipt_path_not_applicable = (
            milestones_by_identity[identity]["path_law"]["source_receipt"]
            == NOT_APPLICABLE_CONTROL_FREEZE_RECEIPT
        )
        if receipt_layer_not_applicable != receipt_path_not_applicable:
            _fail("RECEIPT_APPLICABILITY_MISMATCH", identity)

    for milestone_id in EXPECTED_PROFILE_IDS:
        track_id = "ESTATE_CROSS_REPO" if milestone_id == "XC01" else "ORIGIN_REPAIR"
        identity = milestones[(track_id, milestone_id)]["identity"]
        layers_for_profile = rows_by_identity[identity]["layers"]
        profile = next(
            row for row in payload["acceptance_profiles"]
            if row["milestone_identity"] == identity
        )
        for field, mode in (
            ("targeted_tests", "TARGETED"),
            ("cumulative_tests", "CUMULATIVE"),
            ("external_tests", "EXTERNAL"),
        ):
            declared = profile[field]
            expected = sorted(layer for layer, value in layers_for_profile.items() if value == mode)
            if any(layer not in EXPECTED_TEST_LAYERS for layer in declared):
                _fail("PROFILE_TEST_LAYER_UNKNOWN", f"{profile['profile_id']}:{field}")
            if declared != expected:
                _fail(
                    "PROFILE_TEST_MATRIX_MISMATCH",
                    f"{profile['profile_id']}:{field}: expected {expected!r}, got {declared!r}",
                )


def validate_legacy_crosswalk(
    semantics: Mapping[str, Any],
    milestones: Mapping[tuple[str, str], Mapping[str, Any]],
    root: pathlib.Path = ROOT,
) -> None:
    crosswalk = semantics["payload"]["legacy_crosswalk"]
    if not isinstance(crosswalk, list) or not crosswalk:
        _fail("LEGACY_CROSSWALK_EMPTY", "legacy_crosswalk")
    identities = {row["identity"] for row in milestones.values()}
    milestones_by_id = {key[1]: row for key, row in milestones.items()}
    seen_legacy: set[str] = set()
    actual_order = tuple(row.get("legacy_ref") for row in crosswalk)
    if actual_order != tuple(EXPECTED_LEGACY_BINDINGS):
        _fail("LEGACY_CROSSWALK_SET_OR_ORDER_MISMATCH", repr(actual_order))
    for row in crosswalk:
        if not isinstance(row, dict):
            _fail("LEGACY_CROSSWALK_ROW_INVALID", repr(row))
        legacy_id = row.get("legacy_ref")
        current_identity = row.get("current_identity")
        if not isinstance(legacy_id, str) or not legacy_id or legacy_id in seen_legacy:
            _fail("LEGACY_CROSSWALK_DUPLICATE", repr(legacy_id))
        (
            expected_kind,
            expected_milestone,
            expected_disposition,
            expected_receipt_path,
            expected_receipt_sha,
            expected_scope_digest,
            expected_receipt_milestone,
        ) = EXPECTED_LEGACY_BINDINGS[legacy_id]
        expected_identity = (
            milestones_by_id[expected_milestone]["identity"]
            if expected_milestone is not None else None
        )
        expected_future = "FUTURE_EXPANSION" if expected_kind == "FUTURE_TRACK" else None
        if (
            row.get("target_kind") != expected_kind
            or current_identity != expected_identity
            or row.get("future_track") != expected_future
            or row.get("disposition") != expected_disposition
        ):
            _fail("LEGACY_CROSSWALK_TARGET_INVALID", legacy_id)
        if current_identity is not None and current_identity not in identities:
            _fail("LEGACY_CROSSWALK_TARGET_INVALID", repr(current_identity))
        if (
            row.get("historical_receipt_path") != expected_receipt_path
            or row.get("historical_receipt_sha256") != expected_receipt_sha
            or row.get("historical_scope_digest") != expected_scope_digest
        ):
            _fail("LEGACY_RECEIPT_BINDING_MISMATCH", legacy_id)
        if expected_receipt_path is not None:
            receipt_path = root / expected_receipt_path
            try:
                receipt_bytes = receipt_path.read_bytes()
            except OSError as exc:
                _fail("LEGACY_RECEIPT_UNAVAILABLE", f"{legacy_id}: {exc}")
            if hashlib.sha256(receipt_bytes).hexdigest() != expected_receipt_sha:
                _fail("LEGACY_RECEIPT_BYTE_DIGEST_MISMATCH", legacy_id)
            receipt = load_json_object(receipt_path)
            receipt_scope = receipt.get("payload", {}).get("scope")
            if not isinstance(receipt_scope, dict):
                _fail("LEGACY_RECEIPT_SCOPE_MISSING", legacy_id)
            if receipt_scope.get("milestone") != expected_receipt_milestone:
                _fail("LEGACY_RECEIPT_SCOPE_ID_MISMATCH", legacy_id)
            if _sha256_canonical(receipt_scope) != expected_scope_digest:
                _fail("LEGACY_RECEIPT_SCOPE_DIGEST_MISMATCH", legacy_id)
        seen_legacy.add(legacy_id)
    if seen_legacy != set(EXPECTED_LEGACY_BINDINGS):
        _fail("LEGACY_CROSSWALK_SET_MISMATCH", repr(sorted(seen_legacy)))


def validate_review_policy(
    semantics: Mapping[str, Any], milestones: Mapping[tuple[str, str], Mapping[str, Any]]
) -> None:
    """Prove that every human/provider role is explicit, unbound, and fail-closed at C0."""

    policy = semantics["payload"]["review_policy"]
    if policy.get("binding_failure_rule") != (
        "UNBOUND_OR_SUBJECT_MISMATCH_BLOCKS_SOURCE_RECEIPT_AUDIT_AND_CLOSURE"
    ):
        _fail("REVIEW_BINDING_FAILURE_LAW_MISMATCH", repr(policy.get("binding_failure_rule")))
    requirements = policy.get("provider_identity_requirements", [])
    required_words = ("account", "event", "repository", "role", "subject", "timestamp")
    requirements_text = " ".join(requirements).lower()
    if any(word not in requirements_text for word in required_words):
        _fail("PROVIDER_IDENTITY_REQUIREMENT_INCOMPLETE", repr(requirements))
    independent_roles = {
        "SOURCE_REVIEWER", "RECEIPT_REVIEWER",
        "B10_RUNTIME_SIDE_EFFECT_AUDITOR", "B10_SEMANTIC_SOURCE_AUDITOR",
        "B10_ADJUDICATOR",
    }
    actor_roles = {
        "AUTHOR", "C0_OWNER_AUTHENTICATOR", "EVIDENCE_PRODUCER",
        "OWNER_DECISION_SIGNER", "RESULT_PRODUCER",
    }
    required_pairs = {
        (actor, reviewer)
        for actor in actor_roles
        for reviewer in independent_roles
    } | {
        ("B10_RUNTIME_SIDE_EFFECT_AUDITOR", "B10_SEMANTIC_SOURCE_AUDITOR"),
        ("B10_ADJUDICATOR", "B10_RUNTIME_SIDE_EFFECT_AUDITOR"),
        ("B10_ADJUDICATOR", "B10_SEMANTIC_SOURCE_AUDITOR"),
    }
    actual_pairs = {tuple(pair) for pair in policy.get("disjoint_pairs", [])}
    if actual_pairs != required_pairs:
        _fail("REVIEW_DISJOINT_PAIR_SET_MISMATCH", repr(sorted(actual_pairs)))
    roles = {row.get("role_id"): row.get("independent") for row in policy.get("role_registry", [])}
    expected_roles = {
        "AUTHOR": False, "C0_OWNER_AUTHENTICATOR": False,
        "EVIDENCE_PRODUCER": False, "OWNER_DECISION_SIGNER": False,
        "RESULT_PRODUCER": False,
        "SOURCE_REVIEWER": True, "RECEIPT_REVIEWER": True,
        "B10_RUNTIME_SIDE_EFFECT_AUDITOR": True,
        "B10_SEMANTIC_SOURCE_AUDITOR": True,
        "B10_ADJUDICATOR": True,
    }
    if roles != expected_roles or len(policy.get("role_registry", [])) != len(expected_roles):
        _fail("REVIEW_ROLE_REGISTRY_MISMATCH", repr(roles))
    if policy.get("controlling_entity_key") != "PROVIDER_ACCOUNT_IMMUTABLE_ID":
        _fail("REVIEW_CONTROLLING_ENTITY_KEY_MISMATCH", repr(policy.get("controlling_entity_key")))
    validate_role_identity_bindings(policy, {})

    expected_identities = [milestones[key]["identity"] for key in EXPECTED_MILESTONES]
    rows = policy.get("milestone_slots", [])
    if [row.get("milestone_identity") for row in rows] != expected_identities:
        _fail("REVIEW_SLOT_MILESTONE_SET_OR_ORDER_MISMATCH", "milestone_slots")
    test_layers = {
        row["milestone_identity"]: row["layers"]
        for row in semantics["payload"]["test_layer_matrix"]
    }
    for row in rows:
        identity = row["milestone_identity"]
        roles = [slot.get("role_id") for slot in row.get("slots", [])]
        milestone = next(item for item in milestones.values() if item["identity"] == identity)
        milestone_id = milestone["scope"]["milestone_id"]
        expected_slot_roles = {"SOURCE_REVIEWER"}
        if test_layers[identity]["T7"] != "NOT_APPLICABLE":
            expected_slot_roles.add("RECEIPT_REVIEWER")
        if milestone_id == "C0":
            expected_slot_roles.add("C0_OWNER_AUTHENTICATOR")
        if milestone_id == "B10":
            expected_slot_roles.update({
                "B10_RUNTIME_SIDE_EFFECT_AUDITOR",
                "B10_SEMANTIC_SOURCE_AUDITOR",
                "B10_ADJUDICATOR",
            })
        if len(roles) != len(set(roles)) or set(roles) != expected_slot_roles:
            _fail("REVIEW_SLOT_ROLE_SET_INVALID", identity)
        for slot in row["slots"]:
            if slot.get("binding_state") != "UNBOUND" or slot.get("provider_binding") is not None:
                _fail("REVIEW_SLOT_PREMATURE_BINDING", f"{identity}:{slot.get('role_id')}")
            hint = slot.get("eligible_hint")
            if hint is not None and not (
                milestone_id == "B00R_G2" and slot["role_id"] == "SOURCE_REVIEWER" and hint == "djordi10"
            ):
                _fail("REVIEW_ELIGIBLE_HINT_INVALID", f"{identity}:{slot['role_id']}")

    bn_dependencies = set(milestones[("ESTATE_CLOSURE", "BN")]["dependency_identities"])
    if milestones[("ESTATE_CROSS_REPO", "XC01")]["identity"] not in bn_dependencies:
        _fail("BN_XC01_AGGREGATE_DEPENDENCY_MISSING", "BN dependency_identities")


def validate_role_identity_bindings(
    policy: Mapping[str, Any], bindings: Mapping[str, str]
) -> None:
    """Reject controlling-entity aliasing for every declared disjoint role pair."""

    known_roles = {row.get("role_id") for row in policy.get("role_registry", [])}
    unknown = sorted(set(bindings) - known_roles)
    if unknown:
        _fail("REVIEW_IDENTITY_BINDING_ROLE_UNKNOWN", repr(unknown))
    for role, controlling_entity in bindings.items():
        if not isinstance(controlling_entity, str) or not controlling_entity:
            _fail("REVIEW_IDENTITY_BINDING_INVALID", role)
    for left, right in policy.get("disjoint_pairs", []):
        if left in bindings and right in bindings and bindings[left] == bindings[right]:
            _fail("REVIEW_CONTROLLING_ENTITY_ALIAS", f"{left}={right}")


def validate_b10_terminal_control(
    semantics: Mapping[str, Any], milestones: Mapping[tuple[str, str], Mapping[str, Any]]
) -> None:
    control = semantics["payload"]["b10_terminal_control"]
    b10_identity = milestones[("ORIGIN_REPAIR", "B10")]["identity"]
    if control.get("milestone_identity") != b10_identity:
        _fail("B10_CONTROL_IDENTITY_MISMATCH", repr(control.get("milestone_identity")))
    tasks = control.get("tasks", [])
    criteria = control.get("criteria", [])
    verifications = control.get("verifications", [])
    if not tasks or not criteria or not verifications:
        _fail("B10_CONTROL_EMPTY", "tasks criteria and verifications must be nonzero")
    task_ids = {row.get("task_id") for row in tasks}
    criterion_ids = {row.get("criterion_id") for row in criteria}
    verification_ids = {row.get("verification_id") for row in verifications}
    if len(task_ids) != len(tasks) or len(criterion_ids) != len(criteria) or len(verification_ids) != len(verifications):
        _fail("B10_CONTROL_DUPLICATE_ID", "task criterion or verification")
    graph: dict[str, tuple[str, ...]] = {}
    for row in tasks:
        task_id = row["task_id"]
        dependencies = tuple(row["dependency_task_ids"])
        if any(dep not in task_ids or dep == task_id for dep in dependencies):
            _fail("B10_TASK_DEPENDENCY_UNKNOWN", task_id)
        if any(ref not in criterion_ids for ref in row["criterion_ids"]):
            _fail("B10_TASK_CRITERION_UNKNOWN", task_id)
        if any(ref not in verification_ids for ref in row["verification_ids"]):
            _fail("B10_TASK_VERIFICATION_UNKNOWN", task_id)
        graph[task_id] = dependencies
    for verification in verifications:
        if any(ref not in criterion_ids for ref in verification["criterion_ids"]):
            _fail("B10_VERIFICATION_CRITERION_UNKNOWN", verification["verification_id"])
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visiting:
            _fail("B10_TASK_DEPENDENCY_CYCLE", task_id)
        if task_id in visited:
            return
        visiting.add(task_id)
        for dependency in graph[task_id]:
            visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in graph:
        visit(task_id)
    expected_criterion_consumption = {criterion_id: 1 for criterion_id in criterion_ids}
    task_criterion_consumption = Counter(
        criterion_id for row in tasks for criterion_id in row["criterion_ids"]
    )
    if dict(task_criterion_consumption) != expected_criterion_consumption:
        _fail("B10_TASK_CRITERION_CONSUMPTION_MISMATCH", repr(task_criterion_consumption))
    expected_verification_consumption = {
        verification_id: 1 for verification_id in verification_ids
    }
    task_verification_consumption = Counter(
        verification_id for row in tasks for verification_id in row["verification_ids"]
    )
    if dict(task_verification_consumption) != expected_verification_consumption:
        _fail(
            "B10_TASK_VERIFICATION_CONSUMPTION_MISMATCH",
            repr(task_verification_consumption),
        )
    verification_criterion_consumption = Counter(
        criterion_id for row in verifications for criterion_id in row["criterion_ids"]
    )
    if dict(verification_criterion_consumption) != expected_criterion_consumption:
        _fail(
            "B10_VERIFICATION_CRITERION_CONSUMPTION_MISMATCH",
            repr(verification_criterion_consumption),
        )
    dependency_targets = {
        dependency for dependencies in graph.values() for dependency in dependencies
    }
    terminal_tasks = task_ids - dependency_targets
    if len(terminal_tasks) != 1:
        _fail("B10_TERMINAL_TASK_SET_MISMATCH", repr(sorted(terminal_tasks)))
    terminal_task = next(iter(terminal_tasks))
    reaches_terminal: set[str] = set()
    pending = [terminal_task]
    while pending:
        task_id = pending.pop()
        if task_id in reaches_terminal:
            continue
        reaches_terminal.add(task_id)
        pending.extend(graph[task_id])
    if reaches_terminal != task_ids:
        _fail("B10_TERMINAL_TASK_REACHABILITY_MISMATCH", repr(sorted(reaches_terminal)))
    roles = [row.get("role_id") for row in control.get("audit_roles", [])]
    expected_roles = ["B10_RUNTIME_SIDE_EFFECT_AUDITOR", "B10_SEMANTIC_SOURCE_AUDITOR"]
    if roles != expected_roles or len(set(roles)) != 2:
        _fail("B10_AUDIT_ROLE_SET_MISMATCH", repr(roles))
    adjudication = control.get("adjudication", {})
    if (
        adjudication.get("adjudicator_role") != "B10_ADJUDICATOR"
        or sorted(adjudication.get("requires_audit_roles", [])) != sorted(expected_roles)
        or adjudication.get("state") != "UNBOUND"
    ):
        _fail("B10_ADJUDICATION_LAW_MISMATCH", repr(adjudication))
    receipt_law = control.get("receipt_anchor_law", {})
    b10_path_law = milestones[("ORIGIN_REPAIR", "B10")]["path_law"]
    if (
        receipt_law.get("anchor_must_follow_receipt_merge") is not True
        or receipt_law.get("required_result") != "PASS_REPOSITORY_SAFE_HOLD"
        or receipt_law.get("receipt_path") != b10_path_law["source_receipt"]
        or receipt_law.get("required_anchor") != b10_path_law["anchor"]
    ):
        _fail("B10_RECEIPT_ANCHOR_LAW_MISMATCH", repr(receipt_law))
    if _sha256_canonical(control) != EXPECTED_B10_TERMINAL_CONTROL_SHA256:
        _fail("B10_TERMINAL_CONTROL_DIGEST_MISMATCH", "b10_terminal_control")


def _formula_task_identity(task: Mapping[str, Any]) -> tuple[str, int] | None:
    task_id = str(task.get("id", ""))
    match = re.fullmatch(r"FORM-(F[0-9]{2})-([0-9]{2})", task_id)
    if match is None:
        if task_id.startswith("FORM-") or task.get("row_class") == "FORMULA_ATOMIC":
            _fail("FORMULA_TASK_NAMESPACE_INVALID", task_id)
        return None
    formula_id = match.group(1)
    ordinal = int(match.group(2))
    if formula_id not in EXPECTED_FORMULA_IDS or ordinal not in range(1, 8):
        _fail("FORMULA_TASK_NAMESPACE_INVALID", task_id)
    return formula_id, ordinal


def _expected_task_target(
    task: Mapping[str, Any], milestones: Mapping[tuple[str, str], Mapping[str, Any]]
) -> dict[str, Any]:
    identity_by_id = {key[1]: row["identity"] for key, row in milestones.items()}
    formula_identity = _formula_task_identity(task)
    if formula_identity is not None:
        formula_id, _ = formula_identity
        if formula_id in EXPECTED_EXTERNAL_FORMULA_LAW:
            owner, slot, receipt_milestone, conformance_milestone = (
                EXPECTED_EXTERNAL_FORMULA_LAW[formula_id]
            )
            return {
                "attestation_state": "NOT_ATTESTED",
                "conformance_milestone_identity": identity_by_id[conformance_milestone],
                "formula_id": formula_id,
                "kind": "FORMULA_EXTERNAL_OWNER_RECEIPT",
                "owner_engine": owner,
                "owner_receipt_slot_id": slot,
                "provider_binding_state": "UNBOUND",
                "receipt_milestone_identity": identity_by_id[receipt_milestone],
            }
        milestone_id = EXPECTED_INTERNAL_FORMULA_MILESTONES.get(formula_id)
        if milestone_id is None:
            _fail("FORMULA_OWNER_LAW_MISSING", formula_id)
        return {
            "consumer_milestone_identities": (
                [identity_by_id["B06R"]] if formula_id == "F14" else []
            ),
            "formula_id": formula_id,
            "implementation_milestone_identity": identity_by_id[milestone_id],
            "kind": "FORMULA_IMPLEMENTATION",
            "owner_engine": "E02",
        }

    legacy = task["milestone"]
    if legacy == "B00":
        return {
            "disposition_id": "LEGACY_B00_REALLOCATION_REQUIRED",
            "kind": "BLOCKING_DISPOSITION",
        }
    if legacy == "RESEARCH":
        return {"future_track": "FUTURE_EXPANSION", "kind": "FUTURE_EXPANSION"}
    if legacy in {"ESTATE", "OPERATOR"}:
        return {
            "kind": "EXTERNAL_OBLIGATION",
            "owner_binding_state": "UNBOUND",
            "owner_lane": legacy,
        }
    legacy_map = {
        "B01": "B01C", "B02": "B02C", "B03": "B03C", "B04": "B04C",
        "B05": "B05C", "B06": "B06R", "B07": "B07", "B08": "B08", "B09": "B09",
    }
    if legacy in legacy_map:
        return {
            "kind": "CURRENT_COMPOSITE_MILESTONE",
            "milestone_identity": identity_by_id[legacy_map[legacy]],
        }
    _fail("TASK_BINDING_LEGACY_MILESTONE_UNKNOWN", repr(legacy))


def validate_task_bindings(
    document: Mapping[str, Any], schema: Mapping[str, Any], semantics: Mapping[str, Any],
    root: pathlib.Path = ROOT,
) -> str:
    validate_schema(schema, document, "closure task bindings")
    digest = validate_envelope(document, TASK_BINDING_SCHEMA, TASK_BINDING_DOMAIN)
    payload = document["payload"]
    ledger_path = root / BUILD_LEDGER_REL
    review_path = root / BUILD_LEDGER_REVIEW_REL
    review_subject_path = root / BUILD_LEDGER_REVIEW_SUBJECT_REL
    ledger_bytes = ledger_path.read_bytes()
    review_bytes = review_path.read_bytes()
    review_subject_bytes = review_subject_path.read_bytes()
    if payload["source_ledger"]["byte_sha256"] != hashlib.sha256(ledger_bytes).hexdigest():
        _fail("TASK_BINDING_LEDGER_BYTE_DIGEST_MISMATCH", BUILD_LEDGER_REL.as_posix())
    if payload["legacy_review_artifact"]["byte_sha256"] != hashlib.sha256(review_bytes).hexdigest():
        _fail("TASK_BINDING_REVIEW_BYTE_DIGEST_MISMATCH", BUILD_LEDGER_REVIEW_REL.as_posix())
    subject_sha256 = hashlib.sha256(review_subject_bytes).hexdigest()
    if (
        subject_sha256 != EXPECTED_REVIEW_SUBJECT_SHA256
        or payload["review_subject_ledger"]["byte_sha256"] != subject_sha256
    ):
        _fail(
            "TASK_BINDING_REVIEW_SUBJECT_BYTE_DIGEST_MISMATCH",
            BUILD_LEDGER_REVIEW_SUBJECT_REL.as_posix(),
        )
    ledger = load_json_object(ledger_path)
    review = load_json_object(review_path)
    review_subject = load_json_object(review_subject_path)
    tasks = ledger.get("tasks", [])
    review_rows = review.get("rows", [])
    subject_rows = review_subject.get("tasks", [])
    if len(tasks) != 1250 or len(review_rows) != 1250 or len(subject_rows) != 1250:
        _fail(
            "TASK_BINDING_SOURCE_ROW_COUNT_MISMATCH",
            f"{len(tasks)}/{len(review_rows)}/{len(subject_rows)}",
        )
    if (
        ledger.get("ledger_version") != "CANDIDATE_V3"
        or review.get("ledger_version") != "REVIEWED_V2"
        or review_subject.get("ledger_version") != "REVIEWED_V2"
        or payload["source_ledger"]["ledger_version"] != "CANDIDATE_V3"
        or payload["legacy_review_artifact"]["reviewed_ledger_version"] != "REVIEWED_V2"
        or payload["review_subject_ledger"]["ledger_version"] != "REVIEWED_V2"
        or payload["review_subject_ledger"]["source_commit"] != EXPECTED_REVIEW_SUBJECT_COMMIT
    ):
        _fail("TASK_BINDING_REVIEW_VERSION_MISMATCH", "candidate/review subject")
    source_by_id = {row.get("id"): row for row in tasks}
    review_by_id = {row.get("id"): row for row in review_rows}
    subject_by_id = {row.get("id"): row for row in subject_rows}
    if (
        len(source_by_id) != 1250
        or set(source_by_id) != set(review_by_id)
        or set(source_by_id) != set(subject_by_id)
    ):
        _fail("TASK_BINDING_SOURCE_ID_SET_MISMATCH", "source/review/subject IDs")

    changed_ids = sorted(
        task_id for task_id in source_by_id
        if source_by_id[task_id] != subject_by_id[task_id]
    )
    unallocated_ids = sorted(
        task_id for task_id, task in source_by_id.items() if task["milestone"] == "B00"
    )
    expected_review_coverage = {
        "changed_row_count": 94,
        "changed_task_ids_sha256": _sha256_canonical(changed_ids),
        "current_ledger_review_state": "UNBOUND",
        "target_allocation_review_state": "UNBOUND",
        "unchanged_row_count": 1156,
    }
    if len(changed_ids) != 94 or payload["review_coverage"] != expected_review_coverage:
        _fail("TASK_BINDING_REVIEW_COVERAGE_MISMATCH", repr(payload["review_coverage"]))
    if len(unallocated_ids) != 97:
        _fail("TASK_BINDING_UNALLOCATED_SET_MISMATCH", str(len(unallocated_ids)))
    expected_dispositions = [
        {
            "disposition_id": "C0-CURRENT-LEDGER-REVIEW",
            "reason": "94 current ledger rows differ from the frozen REVIEWED_V2 review subject.",
            "severity": "P0",
            "status": "OPEN",
        },
        {
            "disposition_id": "C0-TARGET-ALLOCATION-REVIEW",
            "reason": "Current target allocations have no independently authenticated review.",
            "severity": "P0",
            "status": "OPEN",
        },
        {
            "disposition_id": "LEGACY_B00_REALLOCATION_REQUIRED",
            "reason": (
                "Legacy B00 tasks require explicit owner reallocation and may not be assigned "
                "to C0 or B00R G2."
            ),
            "severity": "P0",
            "status": "OPEN",
        },
    ]
    if payload["blocking_dispositions"] != expected_dispositions:
        _fail("TASK_BINDING_DISPOSITION_SET_MISMATCH", "blocking_dispositions")

    _, milestones, _ = _milestone_maps(semantics)
    rows = payload.get("rows", [])
    row_ids = [row.get("legacy_task_id") for row in rows]
    if len(rows) != 1250 or len(set(row_ids)) != 1250 or row_ids != sorted(source_by_id):
        _fail("TASK_BINDING_EXACTLY_ONCE_SET_MISMATCH", f"{len(rows)} rows")
    formula_ordinals: dict[str, set[int]] = {formula_id: set() for formula_id in EXPECTED_FORMULA_IDS}
    target_kind_counts: Counter[str] = Counter()
    forbidden_identities = {
        milestones[("CONTROL_FREEZE", "C0")]["identity"],
        milestones[("ORIGIN_REPAIR", "B00R_G2")]["identity"],
    }
    for row in rows:
        task_id = row["legacy_task_id"]
        task = source_by_id[task_id]
        review_row = review_by_id[task_id]
        subject_row = subject_by_id[task_id]
        if row["legacy_milestone"] != task["milestone"]:
            _fail("TASK_BINDING_LEGACY_MILESTONE_MISMATCH", task_id)
        if row["source_row_digest"] != _sha256_canonical(task):
            _fail("TASK_BINDING_SOURCE_ROW_DIGEST_MISMATCH", task_id)
        if row["legacy_review_row_digest"] != _sha256_canonical(review_row):
            _fail("TASK_BINDING_REVIEW_ROW_DIGEST_MISMATCH", task_id)
        if row["review_subject_row_digest"] != _sha256_canonical(subject_row):
            _fail("TASK_BINDING_REVIEW_SUBJECT_ROW_DIGEST_MISMATCH", task_id)
        expected_review_state = (
            "CHANGED_REVIEW_REQUIRED"
            if task_id in changed_ids
            else "UNCHANGED_SINCE_REVIEW_SUBJECT"
        )
        if row["source_review_state"] != expected_review_state:
            _fail("TASK_BINDING_ROW_REVIEW_STATE_MISMATCH", task_id)
        if row["target_allocation_review_state"] != "UNBOUND":
            _fail("TASK_BINDING_TARGET_REVIEW_OVERCLAIM", task_id)
        expected_target = _expected_task_target(task, milestones)
        if row["target"] != expected_target:
            _fail("TASK_BINDING_TARGET_MISMATCH", f"{task_id}: {row['target']!r}")
        if any(
            identity in canonical_json(row["target"]).decode("utf-8")
            for identity in forbidden_identities
        ):
            _fail("TASK_BINDING_C0_B00R_FORBIDDEN", task_id)
        target_kind_counts[row["target"]["kind"]] += 1
        formula_identity = _formula_task_identity(task)
        if formula_identity is not None:
            formula_ordinals[formula_identity[0]].add(formula_identity[1])
    expected_ordinals = set(range(1, 8))
    invalid_formula_sets = {
        formula_id: sorted(ordinals)
        for formula_id, ordinals in formula_ordinals.items()
        if ordinals != expected_ordinals
    }
    if invalid_formula_sets:
        _fail("FORMULA_TASK_SET_NOT_EXACT", repr(invalid_formula_sets))
    expected_kind_counts = {
        "BLOCKING_DISPOSITION": 97,
        "CURRENT_COMPOSITE_MILESTONE": 563,
        "EXTERNAL_OBLIGATION": 418,
        "FORMULA_EXTERNAL_OWNER_RECEIPT": 42,
        "FORMULA_IMPLEMENTATION": 126,
        "FUTURE_EXPANSION": 4,
    }
    if dict(target_kind_counts) != expected_kind_counts:
        _fail("TASK_BINDING_TARGET_KIND_COUNT_MISMATCH", repr(target_kind_counts))
    expected_allocation_summary = {
        "classified_target_task_count": 1153,
        "external_formula_receipt_task_count": 42,
        "external_obligation_task_count": 418,
        "target_allocation_review_state": "UNBOUND",
        "unallocated_task_count": 97,
        "unallocated_task_ids_sha256": _sha256_canonical(unallocated_ids),
    }
    if payload["allocation_summary"] != expected_allocation_summary:
        _fail("TASK_BINDING_ALLOCATION_SUMMARY_MISMATCH", repr(payload["allocation_summary"]))
    validate_no_secrets(document, "closure task bindings")
    return digest


def _status_event_digest(event: Mapping[str, Any]) -> str:
    preimage = {key: value for key, value in event.items() if key != "event_digest"}
    return _sha256_canonical({"domain": STATUS_EVENT_DOMAIN, "event": preimage})


def validate_status_events(
    document: Mapping[str, Any], schema: Mapping[str, Any], semantics: Mapping[str, Any],
    semantics_digest: str,
) -> tuple[str, dict[str, str]]:
    validate_schema(schema, document, "closure status events")
    digest = validate_envelope(document, STATUS_EVENTS_SCHEMA, STATUS_EVENTS_DOMAIN)
    payload = document["payload"]
    if payload["semantics_digest_sha256"] != semantics_digest:
        _fail("STATUS_EVENT_SEMANTICS_DIGEST_MISMATCH", "semantics_digest_sha256")
    if "PLACEHOLDER" in canonical_json(document).decode("utf-8").upper():
        _fail("STATUS_EVENT_PLACEHOLDER_FORBIDDEN", "event log")
    rows, _, by_identity = _milestone_maps(semantics)
    states = {row["identity"]: "NOT_STARTED" for row in rows}
    transition_map = {
        (row["from"], row["to"]): sorted(row["requires"])
        for row in semantics["payload"]["state_machine"]["transitions"]
    }
    previous: str | None = None
    events = payload["events"]
    if payload["event_count"] != len(events):
        _fail("STATUS_EVENT_COUNT_MISMATCH", repr(payload["event_count"]))
    prefix_anchor = semantics["payload"]["status_event_prefix_anchor"]
    prefix_count = prefix_anchor["event_count"]
    if len(events) < prefix_count:
        _fail("STATUS_EVENT_FROZEN_PREFIX_TRUNCATED", str(len(events)))
    actual_prefix = [event["event_digest"] for event in events[:prefix_count]]
    if actual_prefix != prefix_anchor["event_digests"]:
        _fail("STATUS_EVENT_FROZEN_PREFIX_REWRITTEN", repr(actual_prefix))
    if actual_prefix[-1] != prefix_anchor["chain_head_sha256"]:
        _fail("STATUS_EVENT_FROZEN_PREFIX_HEAD_MISMATCH", actual_prefix[-1])
    for sequence, event in enumerate(events):
        if event["sequence"] != sequence:
            _fail("STATUS_EVENT_SEQUENCE_MISMATCH", repr(event["sequence"]))
        if event["previous_event_digest"] != previous:
            _fail("STATUS_EVENT_CHAIN_MISMATCH", str(sequence))
        actual_digest = _status_event_digest(event)
        if event["event_digest"] != actual_digest:
            _fail("STATUS_EVENT_DIGEST_MISMATCH", str(sequence))
        identity = event["milestone_identity"]
        if identity not in by_identity:
            _fail("STATUS_EVENT_MILESTONE_UNKNOWN", identity)
        if event["from_state"] != states[identity]:
            _fail("STATUS_EVENT_REWRITTEN_HISTORY", f"{identity}:{event['from_state']}")
        transition = (event["from_state"], event["to_state"])
        if transition not in transition_map:
            _fail("STATUS_EVENT_ILLEGAL_TRANSITION", repr(transition))
        if sorted(event["satisfied_requirements"]) != transition_map[transition]:
            _fail("STATUS_EVENT_REQUIREMENT_SET_MISMATCH", repr(transition))
        if not event["evidence_refs"]:
            _fail("STATUS_EVENT_EVIDENCE_MISSING", str(sequence))
        # Current C0 input deliberately cannot advance into a closing-capable state while every
        # review/provider slot is UNBOUND and the blocker catalog is open.
        if event["to_state"] in {"SOURCE_READY", "SOURCE_MERGED", "RECEIPT_IN_PROGRESS", "RECEIPT_READY", "CLOSED"}:
            _fail("STATUS_EVENT_ADVANCE_WITH_OPEN_BLOCKERS", f"{identity}:{event['to_state']}")
        states[identity] = event["to_state"]
        previous = actual_digest
    if payload["chain_head_sha256"] != previous:
        _fail("STATUS_EVENT_CHAIN_HEAD_MISMATCH", repr(payload["chain_head_sha256"]))
    validate_no_secrets(document, "closure status events")
    return digest, states


def validate_semantics(
    semantics: Mapping[str, Any], schema: Mapping[str, Any], root: pathlib.Path = ROOT
) -> str:
    validate_schema(schema, semantics, "closure semantics")
    digest = validate_envelope(semantics, SEMANTICS_SCHEMA, SEMANTICS_DOMAIN)
    payload = semantics["payload"]
    if payload["activation_posture"] != SAFE_HOLD:
        _fail("ACTIVATION_POSTURE_MISMATCH", repr(payload["activation_posture"]))
    authority = payload["authority"]
    if authority["cryptographic_authentication"] != "NOT_CLAIMED":
        _fail("CRYPTOGRAPHIC_AUTHENTICATION_OVERCLAIM", "semantics")
    if authority["activation_authorized"] or not authority["repository_work_authorized"]:
        _fail("AUTHORIZATION_BOUNDARY_MISMATCH", repr(authority))
    prefix_anchor = payload["status_event_prefix_anchor"]
    if (
        prefix_anchor["event_count"] != len(EXPECTED_STATUS_EVENT_PREFIX_DIGESTS)
        or tuple(prefix_anchor["event_digests"]) != EXPECTED_STATUS_EVENT_PREFIX_DIGESTS
        or prefix_anchor["chain_head_sha256"] != EXPECTED_STATUS_EVENT_PREFIX_DIGESTS[-1]
    ):
        _fail("STATUS_EVENT_PREFIX_ANCHOR_INVALID", repr(prefix_anchor))
    milestones = validate_milestones(semantics)
    validate_decisions(semantics)
    validate_conflicts(semantics, milestones)
    validate_profiles(semantics, milestones)
    validate_test_matrix(semantics, milestones)
    validate_legacy_crosswalk(semantics, milestones, root)
    validate_review_policy(semantics, milestones)
    validate_b10_terminal_control(semantics, milestones)
    blocker_ids = [row.get("blocker_id") for row in payload["blocker_catalog"]]
    if blocker_ids != sorted(set(blocker_ids)):
        _fail("BLOCKER_CATALOG_NOT_CANONICAL", repr(blocker_ids))
    if set(blocker_ids) != set(EXPECTED_BLOCKER_SPECS):
        _fail("BLOCKER_CATALOG_SET_MISMATCH", repr(blocker_ids))
    identity_by_milestone = {key[1]: row["identity"] for key, row in milestones.items()}
    known_identities = set(identity_by_milestone.values())
    for blocker in payload["blocker_catalog"]:
        if blocker["owner_identity"] not in known_identities:
            _fail("BLOCKER_CATALOG_OWNER_UNKNOWN", blocker["blocker_id"])
        if blocker["severity"] not in {"P0", "P1"}:
            _fail("BLOCKER_CATALOG_SEVERITY_INVALID", blocker["blocker_id"])
        owner_milestone, severity, reason, provenance = EXPECTED_BLOCKER_SPECS[blocker["blocker_id"]]
        expected = {
            "blocker_id": blocker["blocker_id"],
            "owner_identity": identity_by_milestone[owner_milestone],
            "provenance_ref": provenance,
            "reason": reason,
            "severity": severity,
        }
        if blocker != expected:
            _fail("BLOCKER_CATALOG_SPEC_MISMATCH", blocker["blocker_id"])
    validate_no_secrets(semantics, "closure semantics")
    return digest


_GIT_HEAD_SHA1_RE = re.compile(r"[0-9a-f]{40}\Z")


def _real_git_head(root: pathlib.Path) -> str | None:
    """Return the real 40-hex git HEAD of ``root``, or ``None`` if git is unavailable.

    This is used ONLY by the operator-facing ``--stamp-context`` action to record a REAL provider
    head; it never fabricates a value.  The deterministic ``--check`` / ``--write`` paths never call
    git — they read the committed generation-context input.
    """

    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell, read-only
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, ValueError):
        return None
    if completed.returncode != 0:
        return None
    head = completed.stdout.strip()
    if _GIT_HEAD_SHA1_RE.fullmatch(head) is None:
        return None
    return head


def build_generation_context(head: str | None) -> dict[str, Any]:
    """Build the canonical generation-context envelope from a REAL (or absent) provider head.

    ``provider_run_id`` is always the typed ``AUTHORITY_OPEN`` placeholder: no authenticated
    provider (CI/Actions) run id is available offline, and a run id is NEVER fabricated.  When git
    is unavailable the provider head is honestly ``AUTHORITY_OPEN`` too, never a fabricated sha.
    """

    if head is None:
        provider_head = {
            "kind": "AUTHORITY_OPEN",
            "source": "git rev-parse HEAD",
            "value": None,
        }
    else:
        if _GIT_HEAD_SHA1_RE.fullmatch(head) is None:
            _fail("GENERATION_CONTEXT_HEAD_NOT_REAL", repr(head))
        provider_head = {
            "kind": "GIT_HEAD_SHA1",
            "source": "git rev-parse HEAD",
            "value": head,
        }
    payload = {
        "provider_head": provider_head,
        "provider_run_id": {
            "authority_note": (
                "No authenticated provider (CI/Actions) run id is available offline; the slot is "
                "AUTHORITY_OPEN and is never fabricated."
            ),
            "state": "AUTHORITY_OPEN",
            "value": None,
        },
    }
    document: dict[str, Any] = {
        "digest": {
            "algorithm": "sha256",
            "canonicalizer": "triad_origin.canonical.canonical_json",
            "domain": GENERATION_CONTEXT_DOMAIN,
            "preimage_rule": "canonical_json({domain,schema,version,payload})",
            "value": "",
        },
        "payload": payload,
        "schema": GENERATION_CONTEXT_SCHEMA,
        "version": "1",
    }
    document["digest"]["value"] = compute_envelope_digest(document, GENERATION_CONTEXT_DOMAIN)
    return document


def validate_generation_context(
    context: Mapping[str, Any], schema: Mapping[str, Any]
) -> str:
    """Validate the generation-context input; return its envelope digest.

    The provider head is either a real 40-hex git sha or the typed ``AUTHORITY_OPEN`` placeholder;
    the provider run id is always ``AUTHORITY_OPEN`` (never fabricated).  This is fail-closed: an
    ambiguous head kind, a head that claims ``GIT_HEAD_SHA1`` without a real sha, or a run id that
    overclaims a value is refused.
    """

    validate_schema(schema, context, "closure generation context")
    digest = validate_envelope(context, GENERATION_CONTEXT_SCHEMA, GENERATION_CONTEXT_DOMAIN)
    payload = context["payload"]
    head = payload["provider_head"]
    kind = head.get("kind")
    value = head.get("value")
    if kind == "GIT_HEAD_SHA1":
        if not isinstance(value, str) or _GIT_HEAD_SHA1_RE.fullmatch(value) is None:
            _fail("GENERATION_CONTEXT_HEAD_NOT_REAL", repr(value))
    elif kind == "AUTHORITY_OPEN":
        if value is not None:
            _fail("GENERATION_CONTEXT_HEAD_OVERCLAIM", repr(value))
    else:
        _fail("GENERATION_CONTEXT_HEAD_KIND_INVALID", repr(kind))
    run_id = payload["provider_run_id"]
    if run_id.get("state") != "AUTHORITY_OPEN" or run_id.get("value") is not None:
        _fail("GENERATION_CONTEXT_RUN_ID_OVERCLAIM", repr(run_id.get("value")))
    validate_no_secrets(context, "closure generation context")
    return digest


def _generation_context_reference(context: Mapping[str, Any], digest: str) -> dict[str, Any]:
    """Project the committed generation-context into the self-identifying status reference block."""

    head = context["payload"]["provider_head"]
    run_id = context["payload"]["provider_run_id"]
    return {
        "digest_domain": GENERATION_CONTEXT_DOMAIN,
        "digest_sha256": digest,
        "path": GENERATION_CONTEXT_REL.as_posix(),
        "provider_head_kind": head["kind"],
        "provider_head_value": head["value"],
        "provider_run_id_state": run_id["state"],
        "provider_run_id_value": run_id["value"],
        "schema": GENERATION_CONTEXT_SCHEMA,
    }


def _derive_artifact_presence(
    semantics: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    root: pathlib.Path,
) -> list[dict[str, str | None]]:
    """Derive the typed artifact-presence table — presence stated, never rendered as closure.

    * Controlling closure inputs that exist on disk are ``ARTIFACT_PRESENT`` (stat-derived;
      an absent one is ``AUTHORITY_OPEN``).
    * Legacy historical receipts named in the crosswalk are ``HISTORICAL_RECEIPT_PRESERVED``
      (their existence and byte digest are already asserted by ``validate_legacy_crosswalk``).
    * Every required-but-unmerged source receipt / unpublished protected anchor for an
      applicable milestone is ``AUTHORITY_OPEN``.
    """

    presence: list[dict[str, str | None]] = []
    for rel in CONTROLLING_INPUT_ARTIFACTS_SORTED:
        presence.append({
            "artifact_ref": rel.as_posix(),
            "presence_state": (
                PRESENCE_ARTIFACT_PRESENT
                if (root / rel).is_file()
                else PRESENCE_AUTHORITY_OPEN
            ),
            "subject_kind": "CONTROLLING_INPUT",
        })
    for entry in semantics["payload"]["legacy_crosswalk"]:
        receipt_path = entry.get("historical_receipt_path")
        if receipt_path is None:
            continue
        presence.append({
            "artifact_ref": receipt_path,
            "presence_state": PRESENCE_HISTORICAL_RECEIPT_PRESERVED,
            "subject_kind": "HISTORICAL_RECEIPT",
        })
    test_layers = {
        row["milestone_identity"]: row["layers"]
        for row in semantics["payload"]["test_layer_matrix"]
    }
    for row in rows:
        layers = test_layers[row["identity"]]
        if layers["T7"] == "NOT_APPLICABLE":
            continue
        presence.append({
            "artifact_ref": row["path_law"]["source_receipt"],
            "presence_state": PRESENCE_AUTHORITY_OPEN,
            "subject_kind": "REQUIRED_SOURCE_RECEIPT",
        })
        presence.append({
            "artifact_ref": row["path_law"]["anchor"],
            "presence_state": PRESENCE_AUTHORITY_OPEN,
            "subject_kind": "PROTECTED_ANCHOR",
        })
    presence.sort(key=lambda item: (item["subject_kind"], item["artifact_ref"]))
    return presence


def derive_status_projection(
    semantics: Mapping[str, Any], semantics_digest: str,
    status_events: Mapping[str, Any], status_events_digest: str,
    task_bindings: Mapping[str, Any], task_bindings_digest: str,
    work_states: Mapping[str, str],
    generation_context: Mapping[str, Any] | None = None,
    root: pathlib.Path = ROOT,
) -> dict[str, Any]:
    """Derive the sole status projection from normative controls plus chained events.

    ``generation_context`` is the committed generation-context input (the provider head + run-id
    the status is generated against); when omitted it is loaded from ``root`` so existing callers
    stay byte-identical.  ``root`` locates the tree for the stat-derived artifact-presence table.
    """

    if generation_context is None:
        generation_context = load_canonical_object(root / GENERATION_CONTEXT_REL)
    generation_context_digest = compute_envelope_digest(
        generation_context, GENERATION_CONTEXT_DOMAIN
    )
    rows, _, _ = _milestone_maps(semantics)
    blockers: list[dict[str, str]] = []

    def add_blocker(
        blocker_id: str, owner_identity: str, severity: str, reason: str,
        provenance_kind: str, provenance_ref: str,
    ) -> None:
        blockers.append({
            "blocker_id": blocker_id,
            "owner_identity": owner_identity,
            "provenance_kind": provenance_kind,
            "provenance_ref": provenance_ref,
            "reason": reason,
            "severity": severity,
            "status": "OPEN",
        })

    for catalog in semantics["payload"]["blocker_catalog"]:
        add_blocker(
            catalog["blocker_id"], catalog["owner_identity"], catalog["severity"],
            catalog["reason"], "SEMANTICS_BLOCKER_CATALOG", catalog["provenance_ref"],
        )
    slot_rows = {
        row["milestone_identity"]: row["slots"]
        for row in semantics["payload"]["review_policy"]["milestone_slots"]
    }
    test_layers = {
        row["milestone_identity"]: row["layers"]
        for row in semantics["payload"]["test_layer_matrix"]
    }
    runtime_applicability: dict[str, bool] = {}
    receipt_applicability: dict[str, bool] = {}
    for row in rows:
        identity = row["identity"]
        milestone_id = row["scope"]["milestone_id"]
        layers = test_layers[identity]
        runtime_applicable = layers["T8"] != "NOT_APPLICABLE"
        receipt_layer_not_applicable = layers["T7"] == "NOT_APPLICABLE"
        receipt_path_not_applicable = (
            row["path_law"]["source_receipt"] == NOT_APPLICABLE_CONTROL_FREEZE_RECEIPT
        )
        if receipt_layer_not_applicable != receipt_path_not_applicable:
            _fail("RECEIPT_APPLICABILITY_MISMATCH", identity)
        receipt_applicable = not receipt_layer_not_applicable
        runtime_applicability[identity] = runtime_applicable
        receipt_applicability[identity] = receipt_applicable
        for slot in slot_rows[identity]:
            if slot["role_id"] == "RECEIPT_REVIEWER" and not receipt_applicable:
                continue
            if slot["binding_state"] == "UNBOUND":
                add_blocker(
                    f"REVIEW-SLOT::{milestone_id}::{slot['role_id']}", identity, "P0",
                    f"{slot['role_id']} provider identity is UNBOUND",
                    "REVIEW_POLICY_SLOT", f"{identity}:{slot['role_id']}",
                )
        predecessor = row["predecessor_identity"]
        if predecessor is not None and work_states[predecessor] != "CLOSED":
            add_blocker(
                f"PREDECESSOR::{milestone_id}", identity, "P0",
                "exact predecessor is not CLOSED", "MILESTONE_DEPENDENCY", predecessor,
            )
        if receipt_applicable:
            add_blocker(
                f"RECEIPT::{milestone_id}", identity, "P0",
                "required evidence-only receipt is not merged", "PATH_LAW",
                row["path_law"]["source_receipt"],
            )
            add_blocker(
                f"ANCHOR::{milestone_id}", identity, "P0",
                "required protected anchor is not published", "PATH_LAW", row["path_law"]["anchor"],
            )
        if runtime_applicable:
            add_blocker(
                f"RUNTIME::{milestone_id}", identity, "P0",
                "applicable identical-subject runtime proof is NOT_ATTESTED", "TEST_LAYER", "T8",
            )
    blockers.sort(key=lambda item: item["blocker_id"])
    blocker_ids = [row["blocker_id"] for row in blockers]
    if len(blocker_ids) != len(set(blocker_ids)):
        _fail("DERIVED_BLOCKER_ID_COLLISION", repr(blocker_ids))
    reasons_by_owner: dict[str, list[str]] = {row["identity"]: [] for row in rows}
    for blocker in blockers:
        reasons_by_owner[blocker["owner_identity"]].append(blocker["blocker_id"])
    status_rows = []
    for row in rows:
        identity = row["identity"]
        reasons = sorted(reasons_by_owner[identity])
        if not reasons:
            _fail("DERIVED_FALSE_GREEN_MILESTONE", identity)
        status_rows.append({
            "blocking_reasons": reasons,
            "gate_state": "BLOCKED",
            "identity": identity,
            "receipt_state": (
                "BLOCKED" if receipt_applicability[identity] else "NOT_APPLICABLE"
            ),
            "runtime_state": (
                "NOT_ATTESTED" if runtime_applicability[identity] else "NOT_APPLICABLE"
            ),
            "work_state": work_states[identity],
        })
    current_work = [row["identity"] for row in rows if work_states[row["identity"]] == "SOURCE_IN_PROGRESS"]
    artifact_presence = _derive_artifact_presence(semantics, rows, root)
    payload = {
        "activation_posture": semantics["payload"]["activation_posture"],
        "artifact_presence": artifact_presence,
        "classification": "GENERATED_STATUS_NON_EVIDENCE",
        "closed_claims": [],
        "cryptographic_authentication": "NOT_CLAIMED",
        "current_work": current_work,
        "generation_context": _generation_context_reference(
            generation_context, generation_context_digest
        ),
        "generation_law": "Derived from canonical semantics, exact task bindings, and append-only chained status events; manual edits are forbidden.",
        "milestones": status_rows,
        "next_gate": "Complete C0 owner authentication and exact-head independent review; continue B00R G2 source validation without runtime or venue mutation.",
        "open_blockers": blockers,
        "overall_state": "SOURCE_IN_PROGRESS_BLOCKED_SAFE_HOLD",
        "program": semantics["payload"]["program"],
        "semantics_reference": {
            "digest_domain": SEMANTICS_DOMAIN, "digest_sha256": semantics_digest,
            "path": SEMANTICS_REL.as_posix(), "schema": SEMANTICS_SCHEMA,
        },
        "status_events_reference": {
            "chain_head_sha256": status_events["payload"]["chain_head_sha256"],
            "digest_domain": STATUS_EVENTS_DOMAIN, "digest_sha256": status_events_digest,
            "event_count": status_events["payload"]["event_count"],
            "path": STATUS_EVENTS_REL.as_posix(), "schema": STATUS_EVENTS_SCHEMA,
        },
        "task_binding_reference": {
            "changed_review_required_rows": task_bindings["payload"]["review_coverage"][
                "changed_row_count"
            ],
            "classified_target_task_count": task_bindings["payload"]["allocation_summary"][
                "classified_target_task_count"
            ],
            "digest_domain": TASK_BINDING_DOMAIN, "digest_sha256": task_bindings_digest,
            "external_formula_receipt_task_count": task_bindings["payload"][
                "allocation_summary"
            ]["external_formula_receipt_task_count"],
            "external_obligation_task_count": task_bindings["payload"]["allocation_summary"][
                "external_obligation_task_count"
            ],
            "path": TASK_BINDING_REL.as_posix(), "row_count": len(task_bindings["payload"]["rows"]),
            "schema": TASK_BINDING_SCHEMA,
            "source_ledger_review_state": task_bindings["payload"]["review_coverage"][
                "current_ledger_review_state"
            ],
            "target_allocation_review_state": task_bindings["payload"]["review_coverage"][
                "target_allocation_review_state"
            ],
            "unallocated_task_count": task_bindings["payload"]["allocation_summary"][
                "unallocated_task_count"
            ],
            "unchanged_review_subject_rows": task_bindings["payload"]["review_coverage"][
                "unchanged_row_count"
            ],
        },
    }
    document: dict[str, Any] = {
        "digest": {
            "algorithm": "sha256", "canonicalizer": "triad_origin.canonical.canonical_json",
            "domain": STATUS_DOMAIN,
            "preimage_rule": "canonical_json({domain,schema,version,payload})", "value": "",
        },
        "payload": payload, "schema": STATUS_SCHEMA, "version": "1",
    }
    document["digest"]["value"] = compute_envelope_digest(document, STATUS_DOMAIN)
    return document


def _render_provider_head_value(context_ref: Mapping[str, Any]) -> str:
    if context_ref["provider_head_kind"] == "GIT_HEAD_SHA1":
        return f"`GIT_HEAD_SHA1:{context_ref['provider_head_value']}`"
    return "`AUTHORITY_OPEN` (no authenticated provider head offline)"


def _render_generation_context_lines(payload: Mapping[str, Any]) -> list[str]:
    """The self-identifying provider head + run-id block shared by every generated status page.

    Embedding the real head this projection was generated against makes a stale-head status
    self-identifying (a reader compares it to the live head); the provider run-id slot is the typed
    ``AUTHORITY_OPEN`` placeholder — never a fabricated id.
    """

    context_ref = payload["generation_context"]
    return [
        f"- Generated against provider head: {_render_provider_head_value(context_ref)}",
        f"- Provider run id: `{context_ref['provider_run_id_state']}` "
        "(no authenticated provider run id offline)",
        f"- Generation context: `{context_ref['path']}` "
        f"(sha256 `{context_ref['digest_sha256']}`)",
    ]


def render_status_document(status: Mapping[str, Any]) -> bytes:
    payload = status["payload"]
    lines = [
        "# 04 · Generated Closure Status",
        "",
        "_Mechanical projection. Do not edit; run `python tools/closure_control.py --write`._",
        "",
        f"- Overall: `{payload['overall_state']}`",
        "- Activation posture: `OFF / OFF / OFF / LIVE`",
        f"- Open blockers: `{len(payload['open_blockers'])}`",
        "- Closed claims: `0`",
        *_render_generation_context_lines(payload),
        "",
        "## Milestones",
        "",
        "| Composite milestone | Work | Gate | Receipt | Runtime | Blockers |",
        "|---|---|---|---|---|---:|",
    ]
    for row in payload["milestones"]:
        lines.append(
            f"| `{row['identity']}` | `{row['work_state']}` | `{row['gate_state']}` | "
            f"`{row['receipt_state']}` | `{row['runtime_state']}` | {len(row['blocking_reasons'])} |"
        )
    lines.extend([
        "",
        "## Artifact presence",
        "",
        "_Presence is not closure. `ARTIFACT_PRESENT` = a controlling input exists on disk; "
        "`HISTORICAL_RECEIPT_PRESERVED` = a historical receipt preserved byte-unchanged; "
        "`AUTHORITY_OPEN` = a required artifact or authority is absent or unbound. A present "
        "artifact never renders as closure._",
        "",
        "| Subject | Kind | Presence |",
        "|---|---|---|",
    ])
    for item in payload["artifact_presence"]:
        lines.append(
            f"| `{item['artifact_ref']}` | `{item['subject_kind']}` | `{item['presence_state']}` |"
        )
    lines.extend(["", "## Next gate", "", payload["next_gate"], ""])
    return "\n".join(lines).encode("utf-8")


def render_checklist_document(status: Mapping[str, Any]) -> bytes:
    payload = status["payload"]
    lines = [
        "# 08 · Generated Closure Checklist",
        "",
        "_Mechanical projection. Do not edit; run `python tools/closure_control.py --write`._",
        "",
        "Safety baseline: `OFF / OFF / OFF / LIVE`. No deployment, restart, MCP enablement, arming, order action, venue mutation, or promotion is authorized.",
        "",
        *_render_generation_context_lines(payload),
        "",
    ]
    blockers_by_owner: dict[str, list[Mapping[str, Any]]] = {}
    for blocker in payload["open_blockers"]:
        blockers_by_owner.setdefault(blocker["owner_identity"], []).append(blocker)
    for row in payload["milestones"]:
        lines.extend([f"## `{row['identity']}`", ""])
        for blocker in blockers_by_owner[row["identity"]]:
            lines.append(
                f"- [ ] `{blocker['blocker_id']}` — {blocker['reason']} "
                f"(provenance: `{blocker['provenance_kind']}:{blocker['provenance_ref']}`)"
            )
        lines.append("")
    return "\n".join(lines).encode("utf-8")


_PRESENCE_FORBIDDEN_TOKEN_RE = re.compile(r"(?i)\bpass(?:ed|es|ing)?\b|\bclosed\b|\[x\]|✅")


def validate_artifact_presence(
    presence: Any, semantics: Mapping[str, Any], root: pathlib.Path
) -> None:
    """Fail closed unless the presence table is the exact derived projection with typed states.

    Every row must carry one of the closed :data:`PRESENCE_STATES`; a presence fact may NEVER be
    worded as a pass/close/checked box (PRESENCE IS NEVER CLOSURE); and the whole table must equal
    the deterministically derived projection (no injected or removed presence row).
    """

    rows, _, _ = _milestone_maps(semantics)
    expected = _derive_artifact_presence(semantics, rows, root)
    if presence != expected:
        _fail("STATUS_ARTIFACT_PRESENCE_MISMATCH", "artifact_presence")
    for item in presence:
        if item["presence_state"] not in PRESENCE_STATES:
            _fail("ARTIFACT_PRESENCE_STATE_INVALID", repr(item.get("presence_state")))
        for field in ("artifact_ref", "subject_kind", "presence_state"):
            if _PRESENCE_FORBIDDEN_TOKEN_RE.search(str(item[field])):
                _fail("ARTIFACT_PRESENCE_READS_AS_CLOSURE", f"{item['artifact_ref']}:{field}")


def validate_status(
    status: Mapping[str, Any],
    schema: Mapping[str, Any],
    semantics: Mapping[str, Any],
    semantics_digest: str,
    generation_context: Mapping[str, Any] | None = None,
    generation_context_digest: str | None = None,
    root: pathlib.Path = ROOT,
) -> str:
    validate_schema(schema, status, "closure status")
    digest = validate_envelope(status, STATUS_SCHEMA, STATUS_DOMAIN)
    payload = status["payload"]
    if payload["semantics_reference"]["digest_sha256"] != semantics_digest:
        _fail("STATUS_SEMANTICS_DIGEST_MISMATCH", "semantics_reference")
    if payload["activation_posture"] != SAFE_HOLD:
        _fail("STATUS_ACTIVATION_POSTURE_MISMATCH", repr(payload["activation_posture"]))
    if payload["cryptographic_authentication"] != "NOT_CLAIMED":
        _fail("CRYPTOGRAPHIC_AUTHENTICATION_OVERCLAIM", "status")

    if generation_context is None:
        generation_context = load_canonical_object(root / GENERATION_CONTEXT_REL)
    if generation_context_digest is None:
        generation_context_digest = compute_envelope_digest(
            generation_context, GENERATION_CONTEXT_DOMAIN
        )
    expected_context_ref = _generation_context_reference(
        generation_context, generation_context_digest
    )
    if payload["generation_context"] != expected_context_ref:
        _fail("STATUS_GENERATION_CONTEXT_MISMATCH", "generation_context")

    validate_artifact_presence(payload["artifact_presence"], semantics, root)

    rows, _, _ = _milestone_maps(semantics)
    expected_identities = tuple(row["identity"] for row in rows)
    status_rows = payload["milestones"]
    status_identities = tuple(row.get("identity") for row in status_rows)
    if status_identities != expected_identities or len(set(status_identities)) != len(status_identities):
        _fail("STATUS_MILESTONE_SET_OR_ORDER_MISMATCH", repr(status_identities))
    if tuple(payload["current_work"]) != expected_identities[:2]:
        _fail("STATUS_CURRENT_WORK_MISMATCH", repr(payload["current_work"]))

    test_layers = {
        row["milestone_identity"]: row["layers"]
        for row in semantics["payload"]["test_layer_matrix"]
    }
    blockers = payload["open_blockers"]
    blocker_ids = [row["blocker_id"] for row in blockers]
    blocker_id_set = set(blocker_ids)
    for index, row in enumerate(status_rows):
        milestone = rows[index]
        milestone_id = milestone["scope"]["milestone_id"]
        layers = test_layers[row["identity"]]
        expected_work_state = "SOURCE_IN_PROGRESS" if index < 2 else "NOT_STARTED"
        runtime_applicable = layers["T8"] != "NOT_APPLICABLE"
        expected_runtime_state = "NOT_ATTESTED" if runtime_applicable else "NOT_APPLICABLE"
        if row["work_state"] != expected_work_state:
            _fail("STATUS_WORK_STATE_MISMATCH", row["identity"])
        expected_receipt_state = (
            "NOT_APPLICABLE" if layers["T7"] == "NOT_APPLICABLE" else "BLOCKED"
        )
        if row["gate_state"] != "BLOCKED" or row["receipt_state"] != expected_receipt_state:
            _fail("STATUS_GATE_NOT_BLOCKED", row["identity"])
        if row["runtime_state"] != expected_runtime_state:
            _fail("STATUS_RUNTIME_STATE_MISMATCH", row["identity"])
        _require_sorted_unique_strings(row["blocking_reasons"], f"{row['identity']}.blocking_reasons")
        runtime_blocker = f"RUNTIME::{milestone_id}"
        runtime_membership = (
            runtime_blocker in blocker_id_set,
            runtime_blocker in row["blocking_reasons"],
        )
        if runtime_membership != (runtime_applicable, runtime_applicable):
            _fail("STATUS_RUNTIME_BLOCKER_APPLICABILITY_MISMATCH", row["identity"])

        receipt_layer_not_applicable = layers["T7"] == "NOT_APPLICABLE"
        receipt_path_not_applicable = (
            milestone["path_law"]["source_receipt"]
            == NOT_APPLICABLE_CONTROL_FREEZE_RECEIPT
        )
        if receipt_layer_not_applicable != receipt_path_not_applicable:
            _fail("RECEIPT_APPLICABILITY_MISMATCH", row["identity"])
        receipt_applicable = not receipt_layer_not_applicable
        receipt_blockers = (
            f"RECEIPT::{milestone_id}",
            f"ANCHOR::{milestone_id}",
            f"REVIEW-SLOT::{milestone_id}::RECEIPT_REVIEWER",
        )
        if any(
            (blocker_id in blocker_id_set) != receipt_applicable
            or (blocker_id in row["blocking_reasons"]) != receipt_applicable
            for blocker_id in receipt_blockers
        ):
            _fail("STATUS_RECEIPT_BLOCKER_APPLICABILITY_MISMATCH", row["identity"])

    if payload["closed_claims"]:
        _fail("CLOSED_CLAIM_WHILE_BLOCKED", repr(payload["closed_claims"]))
    if len(blocker_ids) != len(set(blocker_ids)):
        _fail("DUPLICATE_OPEN_BLOCKER", repr(blocker_ids))
    known_identities = set(expected_identities)
    for blocker in blockers:
        if blocker["owner_identity"] not in known_identities:
            _fail("BLOCKER_OWNER_UNKNOWN", blocker["blocker_id"])
        if blocker["severity"] not in {"P0", "P1"} or blocker["status"] != "OPEN":
            _fail("BLOCKER_NOT_FAIL_CLOSED", blocker["blocker_id"])
    validate_no_secrets(status, "closure status")
    return digest


def validate_b00r_policy(
    policy: Mapping[str, Any], semantics: Mapping[str, Any]
) -> None:
    _, milestones, _ = _milestone_maps(semantics)
    b00r = milestones[("ORIGIN_REPAIR", "B00R_G2")]
    binding = policy.get("pr_role_law", {}).get("source_pr", {}).get("composite_scope_binding")
    if not isinstance(binding, dict):
        _fail("B00R_SCOPE_BINDING_MISSING", "pr_role_law.source_pr.composite_scope_binding")
    expected = {
        "track_id": "ORIGIN_REPAIR",
        "milestone_id": "B00R_G2",
        "scope_digest": b00r["scope_digest"]["value"],
        "scope_digest_source": SEMANTICS_REL.as_posix(),
        "status": "BOUND_CANONICAL",
        "failure_behavior": "SOURCE_MERGE_FORBIDDEN_ON_SCOPE_BINDING_MISMATCH",
    }
    if binding != expected:
        _fail("B00R_SCOPE_BINDING_MISMATCH", f"expected {expected!r}, got {binding!r}")
    if policy.get("levers") != SAFE_HOLD:
        _fail("B00R_POLICY_ACTIVATION_POSTURE_MISMATCH", repr(policy.get("levers")))
    if policy.get("required_result") != b00r["permitted_result"]:
        _fail("B00R_POLICY_RESULT_MISMATCH", repr(policy.get("required_result")))
    validate_no_secrets(policy, "B00R policy")


def validate_no_secrets(value: Any, label: str) -> None:
    """Reject recognizable credential material; identifiers and pin *names* remain allowed."""

    text = canonical_json(value).decode("utf-8")
    for name, pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            _fail("SECRET_PATTERN_DETECTED", f"{label}:{name}")


def check_all(root: pathlib.Path = ROOT) -> dict[str, str | int]:
    """Validate every C0 control input without mutating the worktree."""

    semantics_schema = load_json_object(root / SEMANTICS_SCHEMA_REL)
    status_schema = load_json_object(root / STATUS_SCHEMA_REL)
    status_events_schema = load_json_object(root / STATUS_EVENTS_SCHEMA_REL)
    task_binding_schema = load_json_object(root / TASK_BINDING_SCHEMA_REL)
    generation_context_schema = load_json_object(root / GENERATION_CONTEXT_SCHEMA_REL)
    semantics = load_canonical_object(root / SEMANTICS_REL)
    status_events = load_canonical_object(root / STATUS_EVENTS_REL)
    task_bindings = load_canonical_object(root / TASK_BINDING_REL)
    generation_context = load_canonical_object(root / GENERATION_CONTEXT_REL)
    status = load_canonical_object(root / STATUS_REL)
    policy = load_json_object(root / B00R_POLICY_REL)

    semantics_digest = validate_semantics(semantics, semantics_schema, root)
    generation_context_digest = validate_generation_context(
        generation_context, generation_context_schema
    )
    task_bindings_digest = validate_task_bindings(
        task_bindings, task_binding_schema, semantics, root
    )
    status_events_digest, work_states = validate_status_events(
        status_events, status_events_schema, semantics, semantics_digest
    )
    expected_status = derive_status_projection(
        semantics, semantics_digest, status_events, status_events_digest,
        task_bindings, task_bindings_digest, work_states,
        generation_context, root,
    )
    if canonical_json(status) != canonical_json(expected_status):
        _fail("GENERATED_STATUS_DRIFT", "run tools/closure_control.py --write")
    status_digest = validate_status(
        status, status_schema, semantics, semantics_digest,
        generation_context, generation_context_digest, root,
    )
    expected_status_doc = render_status_document(expected_status)
    expected_checklist_doc = render_checklist_document(expected_status)
    try:
        actual_status_doc = (root / STATUS_DOC_REL).read_bytes()
        actual_checklist_doc = (root / CHECKLIST_DOC_REL).read_bytes()
    except OSError as exc:
        _fail("GENERATED_DOCUMENT_UNAVAILABLE", str(exc))
    if actual_status_doc != expected_status_doc:
        _fail("GENERATED_STATUS_DOCUMENT_DRIFT", STATUS_DOC_REL.as_posix())
    if actual_checklist_doc != expected_checklist_doc:
        _fail("GENERATED_CHECKLIST_DOCUMENT_DRIFT", CHECKLIST_DOC_REL.as_posix())
    validate_b00r_policy(policy, semantics)
    return {
        "semantics_digest": semantics_digest,
        "status_digest": status_digest,
        "status_events_digest": status_events_digest,
        "task_bindings_digest": task_bindings_digest,
        "milestones": len(EXPECTED_MILESTONES),
        "decisions": len(EXPECTED_DECISIONS),
        "conflicts": len(EXPECTED_CONFLICTS),
        "profiles": len(EXPECTED_PROFILE_IDS),
        "test_layers": len(EXPECTED_TEST_LAYERS),
        "task_bindings": len(task_bindings["payload"]["rows"]),
        "status_events": len(status_events["payload"]["events"]),
        "open_blockers": len(expected_status["payload"]["open_blockers"]),
    }


def write_generated_outputs(root: pathlib.Path = ROOT) -> dict[str, str | int]:
    """Validate immutable inputs, then mechanically rewrite only the three generated outputs."""

    semantics_schema = load_json_object(root / SEMANTICS_SCHEMA_REL)
    status_events_schema = load_json_object(root / STATUS_EVENTS_SCHEMA_REL)
    task_binding_schema = load_json_object(root / TASK_BINDING_SCHEMA_REL)
    generation_context_schema = load_json_object(root / GENERATION_CONTEXT_SCHEMA_REL)
    semantics = load_canonical_object(root / SEMANTICS_REL)
    status_events = load_canonical_object(root / STATUS_EVENTS_REL)
    task_bindings = load_canonical_object(root / TASK_BINDING_REL)
    generation_context = load_canonical_object(root / GENERATION_CONTEXT_REL)
    policy = load_json_object(root / B00R_POLICY_REL)
    semantics_digest = validate_semantics(semantics, semantics_schema, root)
    validate_generation_context(generation_context, generation_context_schema)
    task_bindings_digest = validate_task_bindings(
        task_bindings, task_binding_schema, semantics, root
    )
    status_events_digest, work_states = validate_status_events(
        status_events, status_events_schema, semantics, semantics_digest
    )
    validate_b00r_policy(policy, semantics)
    status = derive_status_projection(
        semantics, semantics_digest, status_events, status_events_digest,
        task_bindings, task_bindings_digest, work_states,
        generation_context, root,
    )
    (root / STATUS_REL).write_bytes(canonical_json(status))
    (root / STATUS_DOC_REL).write_bytes(render_status_document(status))
    (root / CHECKLIST_DOC_REL).write_bytes(render_checklist_document(status))
    return {
        "semantics_digest": semantics_digest,
        "status_digest": status["digest"]["value"],
        "status_events_digest": status_events_digest,
        "task_bindings_digest": task_bindings_digest,
        "milestones": len(EXPECTED_MILESTONES),
        "decisions": len(EXPECTED_DECISIONS),
        "conflicts": len(EXPECTED_CONFLICTS),
        "profiles": len(EXPECTED_PROFILE_IDS),
        "test_layers": len(EXPECTED_TEST_LAYERS),
        "task_bindings": len(task_bindings["payload"]["rows"]),
        "status_events": len(status_events["payload"]["events"]),
        "open_blockers": len(status["payload"]["open_blockers"]),
    }


def stamp_generation_context(root: pathlib.Path = ROOT) -> dict[str, Any]:
    """Operator action: record the REAL git HEAD into the generation-context input.

    This is the only path that reads git, and it never fabricates a value: the provider run id is
    always the typed ``AUTHORITY_OPEN`` placeholder, and if git is unavailable the provider head is
    honestly ``AUTHORITY_OPEN`` too.  The deterministic ``--check`` / ``--write`` paths only read the
    committed context this produces.
    """

    context = build_generation_context(_real_git_head(root))
    schema = load_json_object(root / GENERATION_CONTEXT_SCHEMA_REL)
    validate_generation_context(context, schema)
    (root / GENERATION_CONTEXT_REL).write_bytes(canonical_json(context))
    return context


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="read-only validation (the default; retained for explicit CI invocation)",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="mechanically regenerate closure_status.v1.json and the two documented projections",
    )
    parser.add_argument(
        "--stamp-context",
        action="store_true",
        help=(
            "operator action: record the real git HEAD into the generation-context input "
            "(provider run id stays the typed AUTHORITY_OPEN placeholder, never fabricated)"
        ),
    )
    parser.add_argument(
        "--require-closure-ready",
        action="store_true",
        help="validate structurally, then exit 2 unless the derived open-blocker count is zero",
    )
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=ROOT,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    if sum((args.check, args.write, args.require_closure_ready, args.stamp_context)) > 1:
        parser.error(
            "--check, --write, --stamp-context, and --require-closure-ready are mutually exclusive"
        )
    try:
        root = args.root.resolve()
        if args.stamp_context:
            context = stamp_generation_context(root)
            head = context["payload"]["provider_head"]
            print(
                "OK: generation context stamped; provider head "
                f"{head['kind']}"
                f"{':' + head['value'] if head['value'] else ''}; "
                "provider run id AUTHORITY_OPEN; no closure claim"
            )
            return 0
        result = write_generated_outputs(root) if args.write else check_all(root)
    except ClosureControlError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    if args.require_closure_ready and result["open_blockers"]:
        print(
            f"CLOSURE_NOT_READY: {result['open_blockers']} open blockers; no closure claim",
            file=sys.stderr,
        )
        return 2
    print(
        "OK: C0 closure control canonical; "
        f"{result['milestones']} milestones; {result['decisions']} decisions; "
        f"{result['conflicts']} conflict dispositions; {result['profiles']} profiles; "
        f"{result['test_layers']} test layers; {result['task_bindings']} task bindings; "
        f"{result['status_events']} chained status events; {result['open_blockers']} open blockers; "
        "OFF/OFF/OFF/LIVE; no closure claim"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
