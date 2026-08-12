#!/usr/bin/env python3
"""CO-02 — canonical milestone registry + crosswalk: deterministic generation and fail-closed
verification (TRIAD-ORIGIN-V7-CHANGE-ORDERS-2026-08-12, CO-02).

The B-namespace collision killer.  This tool derives two governed artifacts from the repository's
existing canonical sources — it invents no fact:

  * ``docs/control/milestone_registry.v1.json`` — every milestone keyed by the composite identity
    ``track_id + milestone_id + scope_digest``; tracks ``LEGACY_PROGRAM`` (historical B00–B10,
    immutable), ``ORIGIN_REPAIR`` (B00R_G2, B01C, B02C, B03C, B04C, B05C, B06R, B07, B08, B09,
    B10), ``ESTATE_CROSS_REPO``, ``ESTATE_CLOSURE`` (BN aggregate only), ``FUTURE_EXPANSION``
    (deferred; ``ratified_by: PENDING-OWNER``) and ``CONTROL_FREEZE`` (the C0 route itself).
  * ``docs/control/milestone_crosswalk.v1.json`` — every old bare B ID mapped to its historical
    meaning, current allocation, and CO-02 disposition
    (``PRESERVED_HISTORICAL`` / ``SUPERSEDED_BY <composite>``).

Derivation sources (all in-repo; anything underivable is an explicit UNRESOLVED row, never
invented):

  * ``docs/control/closure/closure_semantics.v1.json`` — the CANONICAL machine semantics route
    (per repository law it always wins; this registry is a derived projection of it),
  * ``docs/governance/B00_B07_INVALIDATION_MANIFEST.v1.json`` — historical receipt bytes/dispositions,
  * ``docs/governance/B00R_GENERATION_LEDGER.v1.json`` — the generation-1/generation-2 record,
  * ``docs/plan/01_MILESTONE_BREAKDOWN.md`` — historical plan headings (text derivation only).

Verification (default mode) is fail-closed:

  1. both artifacts are exact canonical JSON whose embedded digest recomputes;
  2. both artifacts byte-equal a fresh regeneration from the pinned sources (hand edits fail);
  3. composite-key uniqueness; (track_id, milestone_id) uniqueness;
  4. the machine DAG (predecessor + dependency edges) is acyclic and every edge resolves;
  5. every machine row byte-agrees with the closure-semantics route (identity, predecessor,
     permitted result, path law, scope) — where the two disagree, THIS registry fails, the
     closure route wins;
  6. the ``ORIGIN_REPAIR::B10`` lane is NONZERO — real tasks/criteria/verifications/receipt law;
  7. the crosswalk covers exactly the canonical legacy references, with lawful CO-02 dispositions;
  8. no NEW bare-B receipt/task/status row is constructible under ``docs/governance`` +
     ``docs/control``: a bare B-series identifier in an identifier-bearing key fails unless the
     file is on the PRESERVED historical allowlist or the row itself is composite-keyed
     (carries ``track_id``);
  9. the safety posture is invariant: ``DENIED_SAFE_HOLD``, OFF/OFF/OFF/LIVE, closure never
     claimed, the FUTURE_EXPANSION row stays ``ratified_by: PENDING-OWNER`` (ratification is an
     owner act that ships with its own signed amendment — any other literal fails this build).

This tool certifies NO gate, closes NO milestone, and grants NO authority.  Exit 0 means only
that the derived registry agrees with its sources and the namespace law holds.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from triad_origin.canonical import CanonicalError, canonical_json, loads_canonical  # noqa: E402

# --- canonical paths ------------------------------------------------------------------------
REGISTRY_REL = pathlib.Path("docs/control/milestone_registry.v1.json")
CROSSWALK_REL = pathlib.Path("docs/control/milestone_crosswalk.v1.json")
SEMANTICS_REL = pathlib.Path("docs/control/closure/closure_semantics.v1.json")
INVALIDATION_REL = pathlib.Path("docs/governance/B00_B07_INVALIDATION_MANIFEST.v1.json")
GENERATION_LEDGER_REL = pathlib.Path("docs/governance/B00R_GENERATION_LEDGER.v1.json")
PLAN_BREAKDOWN_REL = pathlib.Path("docs/plan/01_MILESTONE_BREAKDOWN.md")

REGISTRY_SCHEMA = "triad.origin.milestone_registry.v1"
REGISTRY_DOMAIN = "triad.origin.milestone_registry.artifact.v1"
CROSSWALK_SCHEMA = "triad.origin.milestone_crosswalk.v1"
CROSSWALK_DOMAIN = "triad.origin.milestone_crosswalk.artifact.v1"
ARTIFACT_VERSION = "1.0.0"
PREPARED = "2026-08-12"
CHANGE_ORDER = "CO-02"
CHANGE_ORDER_DOCUMENT = "TRIAD-ORIGIN-V7-CHANGE-ORDERS-2026-08-12"

LEVERS = {
    "venue_environment": "OFF",
    "venue_activation": "OFF",
    "paper_activation": "OFF",
    "shadow_activation": "LIVE",
}

# LEGACY_PROGRAM membership (historical program identifiers; immutable).
LEGACY_PROGRAM_IDS = (
    "R00",
    "B00",
    "B00C",
    "B00R_GENERATION_1",
    "B01",
    "B01R",
    "B02",
    "B03",
    "B04",
    "B05",
    "B06",
    "B07",
    "B08",
    "B09",
    "B10",
)

ORIGIN_REPAIR_IDS = (
    "B00R_G2",
    "B01C",
    "B02C",
    "B03C",
    "B04C",
    "B05C",
    "B06R",
    "B07",
    "B08",
    "B09",
    "B10",
)

UNRESOLVED_SCOPE = "UNRESOLVED_NO_HISTORICAL_SCOPE_DIGEST"
UNRESOLVED_FUTURE_SCOPE = "UNRESOLVED_DEFERRED_SCOPE_NOT_RATIFIED"

# --- bare-B row law -------------------------------------------------------------------------
# Identifier-bearing keys whose bare B-series value would create a NEW bare-B receipt/task/status
# row.  ``legacy_ref`` / ``historical_*`` keys are crosswalk references BY DESIGN and are exempt.
BARE_B_IDENT_KEYS = frozenset(
    {
        "milestone",
        "milestone_id",
        "logical_milestone",
        "subject_milestone",
        "receipt_milestone",
        "status_milestone",
        "task_milestone",
    }
)
BARE_B_RE = re.compile(r"^(R00|BN|B00R(_GENERATION_1|_G2)?|B[0-9]{2}[CR]?|B10_EXPANSION)$")

# Historical / canonical files PRESERVED byte-unchanged; their existing bare-B rows are evidence,
# never new rows.  A NEW file, or a new bare-B row in a non-allowlisted file, fails.
BARE_B_PRESERVED_ALLOWLIST = (
    "docs/control/b00r_policy.v1.json",
    "docs/control/b00r_policy.v2.json",
    "docs/control/build_ledger.json",
    "docs/control/build_ledger_overrides.json",
    "docs/control/build_ledger_review.v1.json",
    "docs/control/closure/predecessors/build_ledger.REVIEWED_V2.json",
    "docs/governance/B00R_GENERATION_LEDGER.v1.json",
    "docs/governance/B00_B07_INVALIDATION_MANIFEST.v1.json",
    "docs/governance/decisions/DEC-B00-REPAIR-001.json",
    "docs/governance/decisions/DEC-B00-REPAIR-001.template.json",
    "docs/governance/decisions/DEC-B00-REPAIR-002.template.json",
    "docs/governance/decisions/DEC-B00-REPAIR-002.json",
)

FORBIDDEN_STATUS_CLAIMS = frozenset(
    {"PASS", "PASSED", "CLOSED", "COMPLETE", "COMPLETED", "CERTIFIED", "ACTIVATED"}
)


# --- helpers ----------------------------------------------------------------------------------
def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_canonical_object(path: pathlib.Path) -> dict[str, Any]:
    raw = path.read_bytes()
    obj = loads_canonical(raw)
    if not isinstance(obj, dict):
        raise CanonicalError(f"{path}: top-level object required")
    if canonical_json(obj) != raw:
        raise CanonicalError(f"{path}: bytes are not exact canonical JSON")
    return obj


def artifact_digest(domain: str, schema: str, version: str, payload: dict[str, Any]) -> str:
    preimage = canonical_json(
        {"domain": domain, "schema": schema, "version": version, "payload": payload}
    )
    return hashlib.sha256(preimage).hexdigest()


def wrap_artifact(domain: str, schema: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "digest": {
            "algorithm": "sha256",
            "canonicalizer": "triad_origin.canonical.canonical_json",
            "domain": domain,
            "preimage_rule": "canonical_json({domain,schema,version,payload})",
            "value": artifact_digest(domain, schema, ARTIFACT_VERSION, payload),
        },
        "payload": payload,
        "schema": schema,
        "version": ARTIFACT_VERSION,
    }


def composite(track_id: str, milestone_id: str, scope_digest: str) -> str:
    if re.fullmatch(r"[0-9a-f]{64}", scope_digest):
        return f"{track_id}::{milestone_id}::sha256:{scope_digest}"
    return f"{track_id}::{milestone_id}::{scope_digest}"


# --- source loading ---------------------------------------------------------------------------
def load_sources(root: pathlib.Path) -> dict[str, Any]:
    semantics_path = root / SEMANTICS_REL
    invalidation_path = root / INVALIDATION_REL
    ledger_path = root / GENERATION_LEDGER_REL
    plan_path = root / PLAN_BREAKDOWN_REL
    semantics = load_canonical_object(semantics_path)
    invalidation = json.loads(invalidation_path.read_text(encoding="utf-8"))
    generation_ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    plan_text = plan_path.read_text(encoding="utf-8")
    headings: dict[str, str] = {}
    for match in re.finditer(r"^### (\S+) · (.+)$", plan_text, flags=re.MULTILINE):
        headings.setdefault(match.group(1), match.group(2).strip())
    return {
        "semantics": semantics,
        "invalidation": invalidation,
        "generation_ledger": generation_ledger,
        "plan_headings": headings,
        "source_pins": [
            {"path": str(SEMANTICS_REL), "sha256": sha256_file(semantics_path)},
            {"path": str(INVALIDATION_REL), "sha256": sha256_file(invalidation_path)},
            {"path": str(GENERATION_LEDGER_REL), "sha256": sha256_file(ledger_path)},
            {"path": str(PLAN_BREAKDOWN_REL), "sha256": sha256_file(plan_path)},
        ],
    }


# --- generation -------------------------------------------------------------------------------
def _machine_rows(semantics: dict[str, Any]) -> list[dict[str, Any]]:
    payload = semantics["payload"]
    b10 = payload["b10_terminal_control"]
    rows: list[dict[str, Any]] = []
    for milestone in payload["milestones"]:
        scope = milestone["scope"]
        row: dict[str, Any] = {
            "row_kind": "MACHINE_CANONICAL_PROJECTION",
            "composite_identity": milestone["identity"],
            "track_id": scope["track_id"],
            "milestone_id": scope["milestone_id"],
            "scope_digest": milestone["scope_digest"]["value"],
            "scope_text": scope["scope_text"],
            "owns": scope["owns"],
            "excludes": scope["excludes"],
            "predecessor": milestone["predecessor_identity"],
            "dependency_identities": milestone["dependency_identities"],
            "owner": milestone["owner"],
            "path_law": milestone["path_law"],
            "permitted_terminal": milestone["permitted_result"],
            "profile_ref": milestone["profile_ref"],
            "required_independent_reviews": milestone["required_independent_reviews"],
            "status_route": str(pathlib.Path("docs/control/closure/closure_status.v1.json")),
            "status_note": "Status lives on the generated closure route only; presence of this row is never closure.",
            "derived_from": f"{SEMANTICS_REL}#payload.milestones",
        }
        if milestone["identity"] == b10["milestone_identity"]:
            row["lane"] = {
                "tasks": b10["tasks"],
                "criteria": b10["criteria"],
                "verifications": b10["verifications"],
                "receipt_anchor_law": b10["receipt_anchor_law"],
                "adjudication": b10["adjudication"],
                "audit_roles": b10["audit_roles"],
                "lane_note": "CO-02 requires the ORIGIN_REPAIR::B10 lane NONZERO; these rows are the canonical b10_terminal_control projection.",
            }
        rows.append(row)
    return rows


def _crosswalk_index(semantics: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["legacy_ref"]: row for row in semantics["payload"]["legacy_crosswalk"]}


def _legacy_rows(sources: dict[str, Any]) -> list[dict[str, Any]]:
    xwalk = _crosswalk_index(sources["semantics"])
    inval = {e["milestone"]: e for e in sources["invalidation"]["entries"]}
    headings = sources["plan_headings"]
    gen1 = sources["generation_ledger"]["generation_1"]
    rows: list[dict[str, Any]] = []
    for legacy_id in LEGACY_PROGRAM_IDS:
        xrow = xwalk.get(legacy_id)
        manifest_row = inval.get(legacy_id)
        scope_digest = UNRESOLVED_SCOPE
        historical_meaning = None
        successor = None
        receipt_path = None
        receipt_sha = None
        if xrow is not None:
            if xrow.get("historical_scope_digest"):
                scope_digest = xrow["historical_scope_digest"]
            historical_meaning = xrow["historical_meaning"]
            successor = xrow.get("current_identity")
            receipt_path = xrow.get("historical_receipt_path")
            receipt_sha = xrow.get("historical_receipt_sha256")
        row: dict[str, Any] = {
            "row_kind": "LEGACY_HISTORICAL_IMMUTABLE",
            "composite_identity": composite("LEGACY_PROGRAM", legacy_id, scope_digest),
            "track_id": "LEGACY_PROGRAM",
            "milestone_id": legacy_id,
            "scope_digest": scope_digest,
            "historical_meaning": historical_meaning
            or "UNRESOLVED_NOT_IN_CANONICAL_CROSSWALK",
            "plan_heading": headings.get(legacy_id),
            "historical_receipt_path": receipt_path,
            "historical_receipt_sha256": receipt_sha,
            "invalidation_disposition": (
                manifest_row["disposition"] if manifest_row else "NO_RECEIPT_ROW_IN_INVALIDATION_MANIFEST"
            ),
            "successor_identity": successor,
            "owner": "historical program (immutable evidence)",
            "predecessor": None,
            "permitted_terminal": None,
            "receipt_law": "IMMUTABLE_HISTORICAL_EVIDENCE; no new receipt, task, or status row may ever bind this bare identifier",
            "derived_from": f"{SEMANTICS_REL}#payload.legacy_crosswalk + {INVALIDATION_REL} + {PLAN_BREAKDOWN_REL}",
        }
        if legacy_id == "B00R_GENERATION_1":
            row["generation_1_record"] = {
                "disposition": gen1["disposition"],
                "reason_codes": gen1["reason_codes"],
                "receipt_path": gen1["receipt_path"],
                "receipt_sha256": gen1["receipt_sha256"],
                "anchor_tag": gen1["anchor_tag"],
                "immutability": gen1["immutability"],
            }
        if legacy_id == "B10":
            row["bare_id_collision"] = [
                {
                    "meaning": historical_meaning or "UNRESOLVED",
                    "source": str(SEMANTICS_REL) + "#payload.legacy_crosswalk",
                },
                {
                    "meaning": headings.get("B10", "UNRESOLVED"),
                    "source": str(PLAN_BREAKDOWN_REL) + "#B10 heading",
                },
            ]
            row["collision_note"] = (
                "The bare identifier B10 carried two different meanings in two corpora; this is the"
                " exact B-namespace collision CO-02 retires. Neither meaning is rewritten; the"
                " audit/terminal scope is allocated ORIGIN_REPAIR::B10 and the commodities/equities"
                " expansion scope is deferred under FUTURE_EXPANSION with an owner-pending row."
            )
        rows.append(row)
    return rows


def _future_expansion_row() -> dict[str, Any]:
    return {
        "row_kind": "FUTURE_EXPANSION_DEFERRED",
        "composite_identity": composite("FUTURE_EXPANSION", "B10_EXPANSION", UNRESOLVED_FUTURE_SCOPE),
        "track_id": "FUTURE_EXPANSION",
        "milestone_id": "B10_EXPANSION",
        "scope_digest": UNRESOLVED_FUTURE_SCOPE,
        "scope_text": "Historical commodities and equities expansion scope, explicitly preserved-or-deferred. No task, receipt, or status row may bind this row until an owner ratifies its scope.",
        "disposition": "PRESERVED_OR_DEFERRED",
        "ratified_by": "PENDING-OWNER",
        "signature_state": "PENDING_SIGNATURE",
        "refusal_while_pending": "FUTURE_EXPANSION_ROW_UNRATIFIED_NO_TASK_MAY_BIND",
        "owner": "OWNER (ratification pending)",
        "predecessor": None,
        "permitted_terminal": None,
        "derived_from": f"{SEMANTICS_REL}#payload.legacy_crosswalk (DEFERRED_EXPANSION rows)",
    }


def build_registry_payload(sources: dict[str, Any]) -> dict[str, Any]:
    rows = _machine_rows(sources["semantics"]) + _legacy_rows(sources) + [_future_expansion_row()]
    return {
        "activation_result": "DENIED_SAFE_HOLD",
        "authority_note": (
            "Derived projection. The canonical machine semantics and status route is"
            " docs/control/closure/; where this registry and the closure route disagree, the"
            " closure route wins and this registry FAILS verification. This registry closes"
            " nothing, activates nothing, and carries no authority."
        ),
        "bare_b_row_law": {
            "enforced_by": "tools/verify_milestone_registry.py",
            "identifier_keys": sorted(BARE_B_IDENT_KEYS),
            "preserved_allowlist": list(BARE_B_PRESERVED_ALLOWLIST),
            "rule": (
                "No NEW receipt, task, or status row under docs/governance or docs/control may"
                " carry a bare B-series identifier. Rows are keyed by the composite identity"
                " track_id + milestone_id + scope_digest. Existing historical files are preserved"
                " byte-unchanged on the allowlist; a composite-keyed row (carrying track_id) is"
                " lawful by construction."
            ),
        },
        "change_order": CHANGE_ORDER,
        "change_order_document": CHANGE_ORDER_DOCUMENT,
        "classification": "DERIVED_REGISTRY_NON_EVIDENCE",
        "closure_claimed": False,
        "derivation_sources": sources["source_pins"],
        "levers": LEVERS,
        "prepared": PREPARED,
        "rows": rows,
        "tracks": [
            {
                "track_id": "LEGACY_PROGRAM",
                "immutable": True,
                "description": "Historical B00–B10 program identifiers (plus R00, B01R and the generation-1 B00R attempt). Byte-preserved evidence; never a closure; never a new receipt target.",
                "members": list(LEGACY_PROGRAM_IDS),
            },
            {
                "track_id": "ORIGIN_REPAIR",
                "immutable": False,
                "description": "Forward-repair lane. Permitted terminal for every B-series row is PASS_REPOSITORY_SAFE_HOLD only.",
                "members": list(ORIGIN_REPAIR_IDS),
                "permitted_terminal": "PASS_REPOSITORY_SAFE_HOLD",
            },
            {
                "track_id": "ESTATE_CROSS_REPO",
                "immutable": False,
                "description": "Cross-repository lanes (WAVE-C, E00–E10 owner lanes, AG lanes). Only XC01 is machine-registered in this repository; the remaining lanes are estate-side and appear as explicit UNRESOLVED entries.",
                "members": ["XC01"],
            },
            {
                "track_id": "ESTATE_CLOSURE",
                "immutable": False,
                "description": "BN aggregate only.",
                "members": ["BN"],
            },
            {
                "track_id": "FUTURE_EXPANSION",
                "immutable": False,
                "description": "Commodities/equities expansion, deferred. Owner ratification pending.",
                "members": ["B10_EXPANSION"],
            },
            {
                "track_id": "CONTROL_FREEZE",
                "immutable": False,
                "description": "The C0 registry/crosswalk/status freeze itself (canonical closure route).",
                "members": ["C0"],
            },
        ],
        "unresolved_rows": [
            {
                "track_id": "ESTATE_CROSS_REPO",
                "subject": "WAVE-C / E00–E10 owner lanes / AG lanes",
                "state": "UNRESOLVED_NOT_DERIVABLE_FROM_THIS_REPOSITORY",
                "note": "These lanes live in sibling estate repositories; only ESTATE_CROSS_REPO::XC01 is derivable here. Registering them is estate-side work, never invented here.",
            },
            {
                "track_id": "LEGACY_PROGRAM",
                "subject": "historical scope digests for legacy B08, B09, B10",
                "state": UNRESOLVED_SCOPE,
                "note": "The canonical crosswalk carries no historical scope digest for these identifiers (no committed receipt ever existed); their composite keys carry the explicit UNRESOLVED sentinel rather than a fabricated digest.",
            },
            {
                "track_id": "LEGACY_PROGRAM",
                "subject": "R00 plan heading",
                "state": "UNRESOLVED_NOT_IN_PLAN_BREAKDOWN",
                "note": "docs/plan/01_MILESTONE_BREAKDOWN.md carries no R00 heading; the historical meaning derives from the canonical crosswalk only.",
            },
        ],
    }


CO02_DISPOSITION_MAP = {
    "HISTORICAL_ONLY_INVALIDATED": "PRESERVED_HISTORICAL",
    "FORWARD_REPAIR_SUCCESSOR": "SUPERSEDED_BY",
    "PRESERVED_CURRENT_MEANING": "SUPERSEDED_BY",
    "DEFERRED_EXPANSION": "PRESERVED_HISTORICAL",
}


def build_crosswalk_payload(sources: dict[str, Any]) -> dict[str, Any]:
    headings = sources["plan_headings"]
    rows: list[dict[str, Any]] = []
    for xrow in sources["semantics"]["payload"]["legacy_crosswalk"]:
        closure_disposition = xrow["disposition"]
        co02 = CO02_DISPOSITION_MAP[closure_disposition]
        current_allocation = xrow.get("current_identity")
        if closure_disposition == "DEFERRED_EXPANSION":
            current_allocation = composite(
                "FUTURE_EXPANSION", "B10_EXPANSION", UNRESOLVED_FUTURE_SCOPE
            )
        row = {
            "legacy_ref": xrow["legacy_ref"],
            "historical_meaning": xrow["historical_meaning"],
            "historical_receipt_path": xrow.get("historical_receipt_path"),
            "historical_receipt_sha256": xrow.get("historical_receipt_sha256"),
            "historical_scope_digest": xrow.get("historical_scope_digest"),
            "plan_heading": headings.get(xrow["legacy_ref"]),
            "closure_disposition": closure_disposition,
            "target_kind": xrow["target_kind"],
            "co02_disposition": co02,
            "superseded_by": xrow.get("current_identity") if co02 == "SUPERSEDED_BY" else None,
            "current_allocation": current_allocation,
        }
        rows.append(row)
    return {
        "activation_result": "DENIED_SAFE_HOLD",
        "canonical_source": {
            "artifact_digest": sources["semantics"]["digest"]["value"],
            "path": str(SEMANTICS_REL),
            "section": "payload.legacy_crosswalk",
        },
        "change_order": CHANGE_ORDER,
        "change_order_document": CHANGE_ORDER_DOCUMENT,
        "classification": "DERIVED_CROSSWALK_NON_EVIDENCE",
        "closure_claimed": False,
        "disposition_vocabulary": ["PRESERVED_HISTORICAL", "SUPERSEDED_BY"],
        "levers": LEVERS,
        "prepared": PREPARED,
        "rows": rows,
        "statement": (
            "Every old bare B identifier maps to exactly one historical meaning, current"
            " allocation, and disposition. Historical bytes are never edited; a superseded bare"
            " identifier is never a receipt target again."
        ),
    }


def write_artifacts(root: pathlib.Path) -> None:
    sources = load_sources(root)
    registry = wrap_artifact(REGISTRY_DOMAIN, REGISTRY_SCHEMA, build_registry_payload(sources))
    crosswalk = wrap_artifact(CROSSWALK_DOMAIN, CROSSWALK_SCHEMA, build_crosswalk_payload(sources))
    (root / REGISTRY_REL).write_bytes(canonical_json(registry))
    (root / CROSSWALK_REL).write_bytes(canonical_json(crosswalk))


# --- verification ------------------------------------------------------------------------------
def _check_regeneration(root: pathlib.Path, problems: list[str]) -> tuple[dict, dict] | None:
    try:
        sources = load_sources(root)
    except (OSError, CanonicalError, json.JSONDecodeError, KeyError) as exc:
        problems.append(f"DERIVATION_SOURCE_UNREADABLE: {exc}")
        return None
    try:
        registry = load_canonical_object(root / REGISTRY_REL)
        crosswalk = load_canonical_object(root / CROSSWALK_REL)
    except (OSError, CanonicalError) as exc:
        problems.append(f"ARTIFACT_UNREADABLE_OR_NOT_CANONICAL: {exc}")
        return None
    for artifact, domain, schema, name in (
        (registry, REGISTRY_DOMAIN, REGISTRY_SCHEMA, str(REGISTRY_REL)),
        (crosswalk, CROSSWALK_DOMAIN, CROSSWALK_SCHEMA, str(CROSSWALK_REL)),
    ):
        if artifact.get("schema") != schema or artifact.get("version") != ARTIFACT_VERSION:
            problems.append(f"{name}: schema/version mismatch")
            continue
        expected = artifact_digest(domain, schema, ARTIFACT_VERSION, artifact["payload"])
        if artifact["digest"]["value"] != expected:
            problems.append(f"{name}: embedded digest does not recompute")
    expected_registry = wrap_artifact(
        REGISTRY_DOMAIN, REGISTRY_SCHEMA, build_registry_payload(sources)
    )
    expected_crosswalk = wrap_artifact(
        CROSSWALK_DOMAIN, CROSSWALK_SCHEMA, build_crosswalk_payload(sources)
    )
    if canonical_json(expected_registry) != canonical_json(registry):
        problems.append(
            f"{REGISTRY_REL}: bytes differ from deterministic regeneration"
            " (hand edit or DERIVATION_SOURCE_DRIFT; rerun with --write and review)"
        )
    if canonical_json(expected_crosswalk) != canonical_json(crosswalk):
        problems.append(
            f"{CROSSWALK_REL}: bytes differ from deterministic regeneration"
            " (hand edit or DERIVATION_SOURCE_DRIFT; rerun with --write and review)"
        )
    return registry, crosswalk


def _check_uniqueness_and_dag(registry: dict[str, Any], problems: list[str]) -> None:
    rows = registry["payload"]["rows"]
    composites = [row["composite_identity"] for row in rows]
    if len(composites) != len(set(composites)):
        dupes = sorted({c for c in composites if composites.count(c) > 1})
        problems.append(f"COMPOSITE_KEY_DUPLICATE: {dupes}")
    pairs = [(row["track_id"], row["milestone_id"]) for row in rows]
    if len(pairs) != len(set(pairs)):
        dupes = sorted({p for p in pairs if pairs.count(p) > 1})
        problems.append(f"TRACK_MILESTONE_DUPLICATE: {dupes}")
    machine = {
        row["composite_identity"]: row
        for row in rows
        if row["row_kind"] == "MACHINE_CANONICAL_PROJECTION"
    }
    edges: dict[str, list[str]] = {}
    for identity, row in machine.items():
        targets = list(row.get("dependency_identities") or [])
        if row.get("predecessor"):
            targets.append(row["predecessor"])
        for target in targets:
            if target not in machine:
                problems.append(f"DANGLING_EDGE: {identity} -> {target}")
        edges[identity] = targets
    # Kahn / DFS cycle detection.
    WHITE, GREY, BLACK = 0, 1, 2
    colour = {node: WHITE for node in edges}

    def visit(node: str, stack: list[str]) -> None:
        colour[node] = GREY
        for target in edges.get(node, []):
            if target not in colour:
                continue
            if colour[target] == GREY:
                problems.append(f"DAG_CYCLE: {' -> '.join(stack + [node, target])}")
                return
            if colour[target] == WHITE:
                visit(target, stack + [node])
        colour[node] = BLACK

    for node in edges:
        if colour[node] == WHITE:
            visit(node, [])


def _check_machine_agreement(
    root: pathlib.Path, registry: dict[str, Any], problems: list[str]
) -> None:
    try:
        semantics = load_canonical_object(root / SEMANTICS_REL)
    except (OSError, CanonicalError) as exc:
        problems.append(f"CLOSURE_ROUTE_UNREADABLE: {exc}")
        return
    canonical_milestones = {m["identity"]: m for m in semantics["payload"]["milestones"]}
    machine_rows = {
        row["composite_identity"]: row
        for row in registry["payload"]["rows"]
        if row["row_kind"] == "MACHINE_CANONICAL_PROJECTION"
    }
    for identity in canonical_milestones:
        if identity not in machine_rows:
            problems.append(f"CLOSURE_MILESTONE_MISSING_FROM_REGISTRY: {identity}")
    for identity, row in machine_rows.items():
        canonical_row = canonical_milestones.get(identity)
        if canonical_row is None:
            problems.append(f"REGISTRY_MACHINE_ROW_NOT_IN_CLOSURE_ROUTE: {identity}")
            continue
        checks = (
            ("predecessor", row["predecessor"], canonical_row["predecessor_identity"]),
            ("permitted_terminal", row["permitted_terminal"], canonical_row["permitted_result"]),
            ("path_law", row["path_law"], canonical_row["path_law"]),
            ("owner", row["owner"], canonical_row["owner"]),
            ("scope_text", row["scope_text"], canonical_row["scope"]["scope_text"]),
            ("scope_digest", row["scope_digest"], canonical_row["scope_digest"]["value"]),
        )
        for field, got, want in checks:
            if got != want:
                problems.append(
                    f"CLOSURE_DISAGREEMENT ({identity}.{field}): registry={got!r} closure={want!r}"
                    " — the closure route wins; regenerate this registry"
                )
    b10 = semantics["payload"]["b10_terminal_control"]
    b10_row = machine_rows.get(b10["milestone_identity"])
    if b10_row is None:
        problems.append("B10_LANE_MISSING: no ORIGIN_REPAIR::B10 machine row")
    else:
        lane = b10_row.get("lane") or {}
        for key in ("tasks", "criteria", "verifications"):
            if not lane.get(key):
                problems.append(f"B10_LANE_ZERO: lane.{key} is empty or absent")
            elif lane[key] != b10[key]:
                problems.append(f"B10_LANE_DISAGREEMENT: lane.{key} differs from b10_terminal_control")
        if lane.get("receipt_anchor_law") != b10["receipt_anchor_law"]:
            problems.append("B10_LANE_DISAGREEMENT: receipt_anchor_law differs")


def _check_crosswalk(
    root: pathlib.Path, crosswalk: dict[str, Any], registry: dict[str, Any], problems: list[str]
) -> None:
    try:
        semantics = load_canonical_object(root / SEMANTICS_REL)
    except (OSError, CanonicalError) as exc:
        problems.append(f"CLOSURE_ROUTE_UNREADABLE: {exc}")
        return
    canonical_refs = {r["legacy_ref"] for r in semantics["payload"]["legacy_crosswalk"]}
    rows = crosswalk["payload"]["rows"]
    seen = [r["legacy_ref"] for r in rows]
    if sorted(seen) != sorted(canonical_refs):
        problems.append(
            f"CROSSWALK_COVERAGE: registry crosswalk refs {sorted(seen)} !="
            f" canonical refs {sorted(canonical_refs)}"
        )
    if len(seen) != len(set(seen)):
        problems.append("CROSSWALK_DUPLICATE_LEGACY_REF")
    machine_ids = {
        row["composite_identity"]
        for row in registry["payload"]["rows"]
        if row["row_kind"] == "MACHINE_CANONICAL_PROJECTION"
    }
    for row in rows:
        if row["co02_disposition"] not in ("PRESERVED_HISTORICAL", "SUPERSEDED_BY"):
            problems.append(f"CROSSWALK_DISPOSITION_INVALID: {row['legacy_ref']}")
        if row["co02_disposition"] == "SUPERSEDED_BY":
            target = row.get("superseded_by")
            if not target:
                problems.append(f"CROSSWALK_SUPERSEDED_BY_MISSING_TARGET: {row['legacy_ref']}")
            elif target not in machine_ids:
                problems.append(
                    f"CROSSWALK_SUPERSEDED_BY_UNKNOWN_TARGET: {row['legacy_ref']} -> {target}"
                )
        elif row.get("superseded_by"):
            problems.append(f"CROSSWALK_PRESERVED_WITH_TARGET: {row['legacy_ref']}")


def _iter_bare_b_rows(obj: Any, in_composite: bool = False):
    if isinstance(obj, dict):
        composite_here = in_composite or "track_id" in obj
        for key, value in obj.items():
            if (
                key in BARE_B_IDENT_KEYS
                and isinstance(value, str)
                and BARE_B_RE.fullmatch(value)
                and not composite_here
            ):
                yield key, value
            yield from _iter_bare_b_rows(value, composite_here)
    elif isinstance(obj, list):
        for value in obj:
            yield from _iter_bare_b_rows(value, in_composite)


def _check_bare_b_scan(root: pathlib.Path, problems: list[str]) -> None:
    allow = {root / rel for rel in BARE_B_PRESERVED_ALLOWLIST}
    for base in ("docs/governance", "docs/control"):
        for path in sorted((root / base).rglob("*.json")):
            if path in allow:
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                problems.append(f"BARE_B_SCAN_UNPARSEABLE: {path.relative_to(root)}: {exc}")
                continue
            for key, value in _iter_bare_b_rows(data):
                problems.append(
                    f"NEW_BARE_B_ROW: {path.relative_to(root)}: {key}={value}"
                    " (rows must be composite-keyed track_id::milestone_id::scope_digest,"
                    " or the file must be a PRESERVED historical allowlist entry)"
                )


def _check_safety(registry: dict[str, Any], problems: list[str]) -> None:
    payload = registry["payload"]
    if payload["activation_result"] != "DENIED_SAFE_HOLD":
        problems.append("SAFETY: activation_result must be DENIED_SAFE_HOLD")
    if payload["closure_claimed"] is not False:
        problems.append("SAFETY: closure_claimed must be false")
    if payload["levers"] != LEVERS:
        problems.append("SAFETY: levers must be exactly OFF/OFF/OFF/LIVE")
    future_rows = [
        row for row in payload["rows"] if row["row_kind"] == "FUTURE_EXPANSION_DEFERRED"
    ]
    if len(future_rows) != 1:
        problems.append("SAFETY: exactly one FUTURE_EXPANSION_DEFERRED row is required")
    else:
        row = future_rows[0]
        if row.get("ratified_by") != "PENDING-OWNER":
            problems.append(
                "SAFETY: FUTURE_EXPANSION row ratified_by must be the literal PENDING-OWNER;"
                " ratification is an owner act that ships with its own signed amendment"
            )
        if row.get("signature_state") != "PENDING_SIGNATURE":
            problems.append("SAFETY: FUTURE_EXPANSION row signature_state must be PENDING_SIGNATURE")
    for row in payload["rows"]:
        if row["track_id"] == "ORIGIN_REPAIR" and row["permitted_terminal"] != "PASS_REPOSITORY_SAFE_HOLD":
            problems.append(
                f"SAFETY: {row['composite_identity']} permitted_terminal must be PASS_REPOSITORY_SAFE_HOLD"
            )
        for key in ("status", "result", "gate_state"):
            value = row.get(key)
            if isinstance(value, str) and value.upper() in FORBIDDEN_STATUS_CLAIMS:
                problems.append(
                    f"SAFETY: {row['composite_identity']} carries a closure-claiming {key}={value}"
                )


def verify(root: pathlib.Path) -> list[str]:
    problems: list[str] = []
    loaded = _check_regeneration(root, problems)
    if loaded is None:
        return problems
    registry, crosswalk = loaded
    _check_uniqueness_and_dag(registry, problems)
    _check_machine_agreement(root, registry, problems)
    _check_crosswalk(root, crosswalk, registry, problems)
    _check_bare_b_scan(root, problems)
    _check_safety(registry, problems)
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Regenerate the two derived artifacts from the pinned sources (then verify).",
    )
    parser.add_argument("--root", default=str(ROOT), help="Repository root (tests only).")
    args = parser.parse_args(argv)
    root = pathlib.Path(args.root)
    if args.write:
        write_artifacts(root)
    problems = verify(root)
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}", file=sys.stderr)
        return 1
    registry = load_canonical_object(root / REGISTRY_REL)
    rows = registry["payload"]["rows"]
    print(
        "OK: milestone registry verified —"
        f" {len(rows)} rows, composite keys unique, DAG acyclic,"
        " ORIGIN_REPAIR::B10 lane nonzero, no new bare-B row constructible,"
        " posture DENIED_SAFE_HOLD (this verifies a registry; it closes nothing)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
