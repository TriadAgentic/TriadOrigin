#!/usr/bin/env python3
"""CO-01 — the post-RC4 effective-law compiler ``RC5_EFFECTIVE_CONSOLIDATION``.

TRIAD-ORIGIN-V7-CHANGE-ORDERS-2026-08-12 / CO-01. This is a pure, deterministic,
offline applier: ``apply(rc3_bundle, rc4_supersessions) -> rc5_bundle``. It compiles
RC3's machine registries plus RC4's ten supersessions into ONE machine-consumable
effective-law bundle, so no automated consumer can ever again ingest superseded F20
activation-mode budgets, boolean PAR-170, or W06/G5 connected-dark vocabulary.

Estate law honored here:
  * It NEVER mutates RC3 or RC4 bytes — it reads them and emits a SEPARATE artifact
    set (``rc5_bundle.json`` / ``rc5_manifest.json`` / ``rc5_conflict_report.json`` /
    ``rc5_bundle.schema.json``). That separation IS CO-01's whole point.
  * Every supersession is a TYPED operation against the MACHINE REGISTRIES
    (REPLACE_RECORD / RENAME_PARAMETER / REPLACE_SCHEMA / RETIRE_VOCABULARY) — never
    HTML text patching.
  * DARK: it produces the artifact; nothing consumes RC5 (consumption is gated behind
    B01C). It changes NO machine status and arms NOTHING. Posture stays OFF/OFF/OFF/LIVE.
  * Determinism: stdlib only, canonical JSON (sorted keys), sha256, no wall clock, no
    randomness. Byte-stable output across independent runs.
  * Stop rule: if a supersession is genuinely ambiguous against the machine registries
    (no clean typed target, or a token-replace whose exact superseded phrase is absent),
    the family HALTS with a typed conflict recorded in the conflict report — it does NOT
    guess; the compiler and the other nine still land.
"""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent  # docs/control

RC3_BUNDLE_PATH = ROOT / "rc3_effective_control_bundle.json"
RC4_BUNDLE_PATH = ROOT / "rc4_control_bundle.json"
RC3_HTML_PATH = (
    ROOT.parent
    / "spec_rc3"
    / "TRIAD_ORIGIN_V7_COMPLETE_MASTER_SPECIFICATION_AND_MASTER_DOCUMENT_1.0.0_RC3.html"
)
RC4_HTML_PATH = (
    ROOT.parent
    / "spec_rc4"
    / "TRIAD_ORIGIN_V7_FOUR_PLANE_EXECUTION_AND_LEVER_MASTER_ADDENDUM_1.0.0_RC4.html"
)

OUT_BUNDLE = ROOT / "rc5_bundle.json"
OUT_MANIFEST = ROOT / "rc5_manifest.json"
OUT_CONFLICT = ROOT / "rc5_conflict_report.json"
OUT_SCHEMA = ROOT / "rc5_bundle.schema.json"

APPLIER_VERSION = "triad.origin.v7.rc5_effective_consolidation.v1"
BUNDLE_SCHEMA_ID = "triad.origin.v7.rc5_effective_control_bundle.v1"

# Frozen input preimages (the RC3 master / RC4 addendum HTML bytes as pinned in the
# package validation record). Recomputed and asserted at build time.
RC3_HTML_SHA256 = "1a7f57265b707dceaa29fe09582cf6067dd5c438dcc4306de7d6900d4348f2c2"
RC4_HTML_SHA256 = "5db46aa6db02721b68fbf7c640a44db0b7a9ae2fac7423c80452a671fd9a7ff1"

# Typed operation vocabulary (CO-01 Step 2).
OP_REPLACE_RECORD = "REPLACE_RECORD"
OP_RENAME_PARAMETER = "RENAME_PARAMETER"
OP_REPLACE_SCHEMA = "REPLACE_SCHEMA"
OP_RETIRE_VOCABULARY = "RETIRE_VOCABULARY"

# Family application modes.
_MODE_TOKEN = "TOKEN_REPLACE"        # rewrite exact superseded phrases in effective fields
_MODE_DISPOSITION = "DISPOSITION"    # stamp a typed supersession disposition on primary rows
_MODE_SCHEMA = "SCHEMA_INSTALL"      # install a new effective schema block from RC4

# The list-collections of the RC3 machine bundle (the registries we consolidate).
_LIST_COLLECTIONS = (
    "tasks",
    "criteria",
    "verifications",
    "parameters",
    "formulas",
    "formula_parameter_bindings",
    "dependencies",
    "gates",
    "crosswalk",
    "golden_vectors",
    "wiring",
    "sources",
    "traceability",
)

# Per-record identity field (first present wins) — used to resolve DISPOSITION targets.
_IDENTITY_FIELDS = (
    "id",
    "criterion_id",
    "verification_id",
    "binding_id",
    "edge_id",
    "trace_id",
    "gate",
    "legacy_task_id",
)

# Keys excluded from the EFFECTIVE view of a record: RC2 historical source fields, the
# crosswalk legacy_* evidence fields, and the RC5 stamps (which quote the old text as
# evidence). The §5 assertions scan only the effective view.
_HISTORICAL_PREFIXES = ("rc2_source", "legacy_")
_RC5_STAMP_KEYS = ("rc5_supersession", "rc5_superseded_evidence")


def _is_historical_key(key: str) -> bool:
    if key in _RC5_STAMP_KEYS:
        return True
    for prefix in _HISTORICAL_PREFIXES:
        if key.startswith(prefix):
            return True
    return False


def canonical(value: object) -> str:
    """Deterministic canonical JSON (sorted keys, compact separators)."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def record_digest(record: object) -> str:
    return sha256_text(canonical(record))


def _identity(record: dict) -> str | None:
    for field in _IDENTITY_FIELDS:
        if field in record and isinstance(record[field], str):
            return record[field]
    return None


def _effective_strings(record: dict):
    """Yield (key, string) for every effective (non-historical) string field, recursing
    into nested dict/list values so token scans see the whole effective payload."""

    def walk(key, value):
        if isinstance(value, str):
            yield key, value
        elif isinstance(value, dict):
            for sub_v in value.values():
                yield from walk(key, sub_v)
        elif isinstance(value, list):
            for item in value:
                yield from walk(key, item)

    for key, value in record.items():
        if _is_historical_key(key):
            continue
        yield from walk(key, value)


# --------------------------------------------------------------------------- #
# The ten supersession families (CO-01 Step 3), in fixed order.               #
#                                                                             #
# Each family carries: rc4_index (into rc4.supersessions), the CO-01 family    #
# label, the typed op, the mode, and mode-specific data. Replacement strings   #
# are transcribed VERBATIM from the RC4 replacement text — never invented.     #
# --------------------------------------------------------------------------- #

# S5 F20 — remove the activation_mode branch (RC4: "Remove branch; pass one already
# selected signed risk-budget policy. Rollout metadata cannot reach sizing.").
_F20_REPLACEMENTS = (
    (
        "Select B by activation_mode: CANARY->PAR-069, PRODUCTION->PAR-070, otherwise DENY.",
        "Let B be the single already-selected signed risk-budget policy value passed to "
        "sizing; rollout metadata does not reach sizing (RC4 F20 supersession: remove branch).",
    ),
    (
        "activation_mode;selected budget only;",
        "selected signed risk-budget policy only;",
    ),
)

# S9 PAR-170 — rename OFI_NORMALIZED_VARIANT_ENABLED -> OFI_NORMALIZED_VARIANT_ACTIVATION,
# boolean value false -> OFF, preserving its separate ratification state.
_PAR170_REPLACEMENTS = (
    ("OFI_NORMALIZED_VARIANT_ENABLED", "OFI_NORMALIZED_VARIANT_ACTIVATION"),
)

# S8 W06/G5 — retire connected-dark / prospective-dark; use explicit lever vocabulary.
_W06G5_REPLACEMENTS = (
    ("connected-dark", "explicit venue_environment/venue_activation lever"),
    ("prospective_dark", "explicit venue_environment/venue_activation lever"),
    ("prospective-dark", "explicit venue_environment/venue_activation lever"),
    ("connected_dark", "explicit venue_environment/venue_activation lever"),
)

# S6 C-027 — activation_manifest.v1 -> engine_control_manifest.v2.
_C027_REPLACEMENTS = (
    ("activation_manifest.v1", "engine_control_manifest.v2"),
)

# CO-03 additive-major contract additions that RC5 CARRIES (change-orders doc, CO-03 §5/§6 +
# acceptance "RC5 bundle's contract union contains all of the above"; "Depends on: CO-01 (RC5
# carries the additions as additive majors)"). These are NOT RC4 supersessions — they are a
# SEPARATE, clearly-labelled additive layer applied after the ten families, so the "exactly ten
# families" conflict-report invariant is untouched. The four other CO-03 union schemas
# (evidence_view.v2 / raw_venue_event.v2 / runtime_lifecycle.v2 / signed_recommendation.v1) are
# already present in the RC3 contract_union; only these two were declared as schemas but never
# folded into the effective union. Fixed order ⇒ byte-stable output.
_CO03_ADDITIVE_CONTRACT_UNION = (
    "transport_bindings.v1",
    "venue_execution_plan.v1",
)


def _rc4_replacement(rc4_bundle: dict, index: int) -> tuple[str, str, str]:
    row = rc4_bundle["supersessions"][index]
    return row["record"], row["old"], row["replacement"]


def _families(rc4_bundle: dict) -> list[dict]:
    return [
        {
            "family": "ADR-005-ENV-ENUM",
            "rc4_index": 0,
            "op": OP_REPLACE_SCHEMA,
            "mode": _MODE_SCHEMA,
            "schema_slot": "rc5_lever_vocabulary",
            "synthetic_record": "LEVER::venue_environment",
        },
        {
            "family": "DEP-010-ALIAS-RETIREMENT",
            "rc4_index": 1,
            "op": OP_RETIRE_VOCABULARY,
            "mode": _MODE_DISPOSITION,
            "id_set": ("DEP-010", "CHK-0310", "SCP-0310", "V-SCP-0310"),
        },
        {
            "family": "GAP-006-MISMATCH-ONLY",
            "rc4_index": 2,
            "op": OP_REPLACE_RECORD,
            "mode": _MODE_DISPOSITION,
            "id_set": ("GAP-006", "V-GAP-006"),
        },
        {
            "family": "SEC-015-EXACT-BINDING",
            "rc4_index": 3,
            "op": OP_REPLACE_RECORD,
            "mode": _MODE_DISPOSITION,
            "id_set": ("SEC-015", "CHK-0216", "SCP-0216", "V-SCP-0216"),
        },
        {
            "family": "F20-SINGLE-POLICY-SLOT",
            "rc4_index": 4,
            "op": OP_REPLACE_RECORD,
            "mode": _MODE_TOKEN,
            "trigger_tokens": ("activation_mode",),
            "replacements": _F20_REPLACEMENTS,
        },
        {
            "family": "C-027-ENGINE-CONTROL-MANIFEST-V2",
            "rc4_index": 5,
            "op": OP_REPLACE_SCHEMA,
            "mode": _MODE_TOKEN,
            "trigger_tokens": ("activation_manifest.v1",),
            "replacements": _C027_REPLACEMENTS,
            "also_contract_union": True,
        },
        {
            "family": "RC2-RECEIPT-SCHEMAS-STRICT-V2",
            "rc4_index": 6,
            "op": OP_REPLACE_SCHEMA,
            "mode": _MODE_SCHEMA,
            "schema_slot": "rc5_receipt_schema_binding",
            "synthetic_record": "SCHEMA::rc2_receipt_schemas",
        },
        {
            "family": "W06-G5-LEVER-VOCABULARY",
            "rc4_index": 7,
            "op": OP_RETIRE_VOCABULARY,
            "mode": _MODE_TOKEN,
            "trigger_tokens": ("connected-dark", "prospective_dark"),
            "replacements": _W06G5_REPLACEMENTS,
        },
        {
            "family": "PAR-170-RENAME-ACTIVATION",
            "rc4_index": 8,
            "op": OP_RENAME_PARAMETER,
            "mode": _MODE_TOKEN,
            "trigger_tokens": ("OFI_NORMALIZED_VARIANT_ENABLED",),
            "replacements": _PAR170_REPLACEMENTS,
            "value_transform": True,
        },
        {
            "family": "MCP-FAMILY-ACTIVATION-ENUM",
            "rc4_index": 9,
            "op": OP_REPLACE_SCHEMA,
            "mode": _MODE_SCHEMA,
            "schema_slot": "rc5_mcp_family_activation",
            "synthetic_record": "SCHEMA::mcp_family_activation",
        },
    ]


class AmbiguousSupersession(Exception):
    """A supersession has no clean typed target — recorded, never guessed (CO-01 stop rule)."""


# --------------------------------------------------------------------------- #
# Typed operation appliers.                                                    #
# --------------------------------------------------------------------------- #


def _stamp(record: dict, family: dict, rc4_bundle: dict, evidence: dict | None) -> None:
    rec, old, replacement = _rc4_replacement(rc4_bundle, family["rc4_index"])
    record["rc5_supersession"] = OrderedDict(
        [
            ("family", family["family"]),
            ("operation", family["op"]),
            ("rc4_record", rec),
            ("rc4_old", old),
            ("rc4_replacement", replacement),
            ("rc4_supersession_index", family["rc4_index"]),
        ]
    )
    if evidence:
        record["rc5_superseded_evidence"] = evidence


def _apply_token(bundle: dict, family: dict, rc4_bundle: dict) -> list[dict]:
    """TOKEN_REPLACE: locate records whose effective fields carry a trigger token, rewrite
    the exact superseded phrases (transcribed from RC4), preserve originals as evidence,
    stamp the supersession. Halts if a triggered field yields no phrase change."""
    tokens = family["trigger_tokens"]
    replacements = family["replacements"]
    touched: list[dict] = []

    for collection in _LIST_COLLECTIONS:
        for record in bundle.get(collection, []):
            if not isinstance(record, dict):
                continue
            triggered = any(
                any(tok in s for tok in tokens) for _, s in _effective_strings(record)
            )
            if not triggered:
                continue

            before = record_digest(record)
            evidence: dict[str, str] = {}
            changed_any = False
            for key, value in list(record.items()):
                if _is_historical_key(key) or not isinstance(value, str):
                    continue
                new_value = value
                for old, new in replacements:
                    new_value = new_value.replace(old, new)
                if new_value != value:
                    evidence[key] = value
                    record[key] = new_value
                    changed_any = True

            if family.get("value_transform"):
                changed_any = _par170_value_transform(record, evidence) or changed_any

            # A triggered record whose superseded token survives in an effective field
            # after the transcribed replacements is genuinely ambiguous — HALT it.
            surviving = [
                (k, s)
                for k, s in _effective_strings(record)
                if any(tok in s for tok in tokens)
            ]
            if surviving:
                raise AmbiguousSupersession(
                    f"{family['family']}: trigger token survives after replacement in "
                    f"{_identity(record)!r} fields {[k for k, _ in surviving]}"
                )
            if not changed_any:
                raise AmbiguousSupersession(
                    f"{family['family']}: triggered record {_identity(record)!r} yielded "
                    "no exact-phrase change"
                )

            _stamp(record, family, rc4_bundle, evidence)
            touched.append(
                _touched_row(collection, _identity(record), before, record_digest(record))
            )

    if not touched:
        raise AmbiguousSupersession(
            f"{family['family']}: no record carries any trigger token {tokens}"
        )

    if family.get("also_contract_union"):
        touched.extend(_apply_contract_union(bundle, family, rc4_bundle))
    return touched


def _par170_value_transform(record: dict, evidence: dict) -> bool:
    """Boolean false -> OFF and unit/value_type boolean -> lever activation enum, while
    preserving the separate ratification state (status untouched)."""
    changed = False
    if record.get("declared_value") == "false":
        evidence.setdefault("declared_value", "false")
        record["declared_value"] = "OFF"
        changed = True
    for field in ("unit", "value_type"):
        if record.get(field) == "boolean":
            evidence.setdefault(field, "boolean")
            record[field] = "lever_activation_enum(LIVE|OFF)"
            changed = True
    return changed


def _apply_contract_union(bundle: dict, family: dict, rc4_bundle: dict) -> list[dict]:
    ext = bundle.get("rc3_extensions", {})
    union = ext.get("contract_union")
    if not isinstance(union, list):
        return []
    before = record_digest(union)
    changed = False
    new_union = []
    for entry in union:
        new_entry = entry
        if isinstance(entry, str):
            for old, new in family["replacements"]:
                new_entry = new_entry.replace(old, new)
        if new_entry != entry:
            changed = True
        new_union.append(new_entry)
    if not changed:
        return []
    ext["contract_union"] = new_union
    ext.setdefault("rc5_contract_union_supersession", []).append(
        OrderedDict(
            [
                ("family", family["family"]),
                ("operation", family["op"]),
                ("replacements", [list(pair) for pair in family["replacements"]]),
            ]
        )
    )
    return [
        _touched_row(
            "rc3_extensions.contract_union", "contract_union", before, record_digest(new_union)
        )
    ]


def _apply_co03_additive_contracts(bundle: dict) -> list[str]:
    """Fold the CO-03 additive-major contracts (transport_bindings.v1, venue_execution_plan.v1)
    into the effective contract union — the additive layer RC5 CARRIES per CO-03. Idempotent and
    deterministic (fixed order, appended after the RC3 entries), so output stays byte-stable. A
    provenance row records exactly what was added; the ten RC4 supersession families are untouched.
    """
    ext = bundle.setdefault("rc3_extensions", {})
    union = ext.get("contract_union")
    if not isinstance(union, list):
        return []
    before = record_digest(union)
    added = [c for c in _CO03_ADDITIVE_CONTRACT_UNION if c not in union]
    if not added:
        return []
    union.extend(added)  # fixed order ⇒ byte-stable
    ext["rc5_co03_additive_contract_union"] = OrderedDict(
        [
            ("change_order", "CO-03"),
            ("layer", "ADDITIVE_MAJOR_NOT_AN_RC4_SUPERSESSION"),
            ("reason",
             "CO-03 §5/§6 declared these contracts; RC5 carries them as additive majors "
             "(CO-03 acceptance: the RC5 contract union contains all of the above)."),
            ("added", list(added)),
            ("before_digest", before),
            ("after_digest", record_digest(union)),
        ]
    )
    return added


def _apply_disposition(bundle: dict, family: dict, rc4_bundle: dict) -> list[dict]:
    """DISPOSITION: stamp the typed supersession on every PRIMARY registry row whose
    identity is in the family's id-set (edges/traceability that merely reference the id
    are not the superseded record and are left as derived references)."""
    id_set = set(family["id_set"])
    touched: list[dict] = []
    for collection in _LIST_COLLECTIONS:
        if collection in ("dependencies", "traceability"):
            continue  # derived reference edges, not the superseded record itself
        for record in bundle.get(collection, []):
            if not isinstance(record, dict):
                continue
            if _identity(record) in id_set:
                before = record_digest(record)
                _stamp(record, family, rc4_bundle, None)
                touched.append(
                    _touched_row(collection, _identity(record), before, record_digest(record))
                )
    if not touched:
        raise AmbiguousSupersession(
            f"{family['family']}: no primary registry row matches id-set {sorted(id_set)}"
        )
    return touched


def _apply_schema(bundle: dict, family: dict, rc3_bundle_src: dict, rc4_bundle: dict) -> list[dict]:
    """SCHEMA_INSTALL: install a new effective schema block, sourced from RC4 (never
    invented). The touched 'record' is the synthetic schema slot: before = absent."""
    slot = family["schema_slot"]
    rec, old, replacement = _rc4_replacement(rc4_bundle, family["rc4_index"])
    before = record_digest({"present": False, "rc4_record": rec})

    if slot == "rc5_lever_vocabulary":
        lever = rc4_bundle["lever_law"]
        block = OrderedDict(
            [
                ("venue_environment_enum", list(lever["venue_environment_enum"])),
                ("activation_enum", list(lever["activation_enum"])),
                ("valid_combinations", deepcopy(lever["valid_combinations"])),
                ("invalid_aliases", list(lever["invalid_aliases"])),
                ("case_sensitive", lever["case_sensitive"]),
                ("aliases", lever["aliases"]),
                ("coercion", lever["coercion"]),
                ("trim_input", lever["trim_input"]),
            ]
        )
    elif slot == "rc5_receipt_schema_binding":
        block = OrderedDict(
            [
                ("authoritative", "strict_v2"),
                ("semantic_combination_validation", True),
                (
                    "receipt_v2_requirements",
                    deepcopy(
                        rc3_bundle_src.get("rc3_extensions", {}).get(
                            "receipt_v2_requirements", []
                        )
                    ),
                ),
                ("retired", "RC2_arbitrary_string_receipt_schemas"),
            ]
        )
    elif slot == "rc5_mcp_family_activation":
        block = OrderedDict(
            [
                ("target_activation_enum", ["LIVE", "OFF"]),
                ("legacy_booleans", "HISTORICAL_RAW_EVIDENCE_ONLY"),
                ("historical_live_mcp_snapshot", deepcopy(rc4_bundle["live_mcp_snapshot"])),
            ]
        )
    else:  # pragma: no cover - guarded by the fixed family table
        raise AmbiguousSupersession(f"{family['family']}: unknown schema slot {slot!r}")

    installed = OrderedDict(
        [
            ("schema_slot", slot),
            ("family", family["family"]),
            ("operation", family["op"]),
            ("rc4_record", rec),
            ("rc4_old", old),
            ("rc4_replacement", replacement),
            ("effective", block),
        ]
    )
    bundle.setdefault("rc5_schema_installs", OrderedDict())[slot] = installed
    return [
        _touched_row("rc5_schema_installs", family["synthetic_record"], before, record_digest(installed))
    ]


def _touched_row(collection: str, identity: str | None, before: str, after: str) -> dict:
    return OrderedDict(
        [
            ("collection", collection),
            ("record", identity),
            ("before_digest", before),
            ("after_digest", after),
        ]
    )


# --------------------------------------------------------------------------- #
# §5 build-fail assertions.                                                    #
# --------------------------------------------------------------------------- #


class Rc5AssertionError(Exception):
    """A §5 effective-law assertion failed — the build fails, per CO-01 Step 5."""


def _scan_effective(bundle: dict, predicate):
    """Return a list of (collection, identity, key, value) for every effective string
    field satisfying predicate(value)."""
    hits = []
    for collection in _LIST_COLLECTIONS:
        for record in bundle.get(collection, []):
            if not isinstance(record, dict):
                continue
            ident = _identity(record)
            for key, value in _effective_strings(record):
                if predicate(value):
                    hits.append((collection, ident, key, value))
    return hits


# Each §5 assertion is guaranteed by exactly one supersession family. A HALTED family's
# guarantee is honestly NOT provided — its assertion is reported HALTED, never raised, and
# the superseded content it could not neutralize survives (recorded as a typed conflict).
_ASSERTION_FOR_FAMILY = {
    "F20-SINGLE-POLICY-SLOT": "no_activation_mode_budget_branch",
    "PAR-170-RENAME-ACTIVATION": "no_ofi_variant_enabled_boolean",
    "W06-G5-LEVER-VOCABULARY": "no_dark_vocabulary",
    "ADR-005-ENV-ENUM": "lever_fields_exact_rc4_enums",
}


def run_assertions(
    bundle: dict, rc4_bundle: dict, halted_families: set[str] | None = None
) -> list[dict]:
    """CO-01 Step 5: raises Rc5AssertionError on any violation of an APPLIED family's
    guarantee; a HALTED family's assertion is reported HALTED (not raised). Returns the log."""
    halted_families = halted_families or set()
    halted_assertions = {
        _ASSERTION_FOR_FAMILY[f] for f in halted_families if f in _ASSERTION_FOR_FAMILY
    }
    log: list[dict] = []

    def check(name: str, ok: bool, detail: str) -> None:
        if name in halted_assertions:
            log.append({"assertion": name, "result": "HALTED"})
            return
        if not ok:
            raise Rc5AssertionError(f"assertion_{name}: {detail}")
        log.append({"assertion": name, "result": "PASS"})

    # #1: no record contains activation_mode with CANARY|PRODUCTION budget semantics.
    hits = _scan_effective(
        bundle,
        lambda s: "activation_mode" in s and ("CANARY" in s or "PRODUCTION" in s),
    )
    check("no_activation_mode_budget_branch", not hits, f"{len(hits)} effective hit(s): {hits[:3]}")

    # #2: no boolean OFI_NORMALIZED_VARIANT_ENABLED token in any effective field.
    hits = _scan_effective(bundle, lambda s: "OFI_NORMALIZED_VARIANT_ENABLED" in s)
    check("no_ofi_variant_enabled_boolean", not hits, f"{len(hits)} effective hit(s): {hits[:3]}")

    # #3: no connected-dark / prospective-dark token in any effective field.
    dark = ("connected-dark", "connected_dark", "prospective-dark", "prospective_dark")
    hits = _scan_effective(bundle, lambda s: any(tok in s for tok in dark))
    check("no_dark_vocabulary", not hits, f"{len(hits)} effective hit(s): {hits[:3]}")

    # #4: lever fields accept exactly the RC4 enums.
    installs = bundle.get("rc5_schema_installs", {})
    lever = installs.get("rc5_lever_vocabulary", {}).get("effective", {})
    lever_ok = lever.get("venue_environment_enum") == list(
        rc4_bundle["lever_law"]["venue_environment_enum"]
    ) and lever.get("activation_enum") == list(rc4_bundle["lever_law"]["activation_enum"])
    check("lever_fields_exact_rc4_enums", lever_ok, "installed lever enums do not equal RC4")
    return log


# --------------------------------------------------------------------------- #
# The pure applier.                                                            #
# --------------------------------------------------------------------------- #


def apply(rc3_bundle: dict, rc4_bundle: dict) -> tuple[dict, dict, dict]:
    """Compile RC3 + RC4's ten supersessions into (rc5_bundle, manifest, conflict_report).

    Pure: does not mutate its inputs. Applies each family as a typed operation; a family
    that is genuinely ambiguous is HALTED (typed conflict recorded) while the others land.
    """
    rc5 = deepcopy(rc3_bundle)
    families = _families(rc4_bundle)

    conflict_families: list[dict] = []
    operation_log: list[dict] = []
    halted: list[dict] = []
    halted_names: set[str] = set()

    for family in families:
        rc4_rec, rc4_old, rc4_replacement = _rc4_replacement(rc4_bundle, family["rc4_index"])
        entry = OrderedDict(
            [
                ("family", family["family"]),
                ("rc4_supersession_index", family["rc4_index"]),
                ("operation", family["op"]),
                ("mode", family["mode"]),
                ("rc4_record", rc4_rec),
                ("rc4_old", rc4_old),
                ("rc4_replacement", rc4_replacement),
            ]
        )
        # A family is applied transactionally: on a typed conflict we roll the whole
        # bundle back to its pre-family state so a partially-applied family never lands.
        snapshot = deepcopy(rc5)
        try:
            if family["mode"] == _MODE_TOKEN:
                touched = _apply_token(rc5, family, rc4_bundle)
            elif family["mode"] == _MODE_DISPOSITION:
                touched = _apply_disposition(rc5, family, rc4_bundle)
            elif family["mode"] == _MODE_SCHEMA:
                touched = _apply_schema(rc5, family, rc3_bundle, rc4_bundle)
            else:  # pragma: no cover - guarded by the fixed family table
                raise AmbiguousSupersession(f"{family['family']}: unknown mode")
            entry["status"] = "APPLIED"
            entry["records_touched"] = len(touched)
            conflict_families.append(
                OrderedDict(
                    [
                        ("family", family["family"]),
                        ("rc4_supersession_index", family["rc4_index"]),
                        ("operation", family["op"]),
                        ("status", "APPLIED"),
                        ("records_touched", len(touched)),
                        ("records", touched),
                    ]
                )
            )
        except AmbiguousSupersession as exc:
            # CO-01 stop rule: HALT this family with a typed conflict; do NOT guess.
            rc5.clear()
            rc5.update(snapshot)  # roll back the whole family — nothing partial lands
            entry["status"] = "HALTED_TYPED_CONFLICT"
            entry["conflict"] = str(exc)
            entry["records_touched"] = 0
            halted.append({"family": family["family"], "conflict": str(exc)})
            halted_names.add(family["family"])
            conflict_families.append(
                OrderedDict(
                    [
                        ("family", family["family"]),
                        ("rc4_supersession_index", family["rc4_index"]),
                        ("operation", family["op"]),
                        ("status", "HALTED_TYPED_CONFLICT"),
                        ("conflict", str(exc)),
                        ("records_touched", 0),
                        ("records", []),
                    ]
                )
            )
        operation_log.append(entry)

    # CO-03 additive-major contract additions (a SEPARATE layer from the ten RC4 families).
    co03_added = _apply_co03_additive_contracts(rc5)

    # Stamp RC5 provenance/disposition onto the effective bundle (DARK — arms nothing).
    rc5["rc5_provenance"] = OrderedDict(
        [
            ("schema", BUNDLE_SCHEMA_ID),
            ("applier_version", APPLIER_VERSION),
            ("document_id", "TRIAD-ORIGIN-V7-CHANGE-ORDERS-2026-08-12"),
            ("change_order", "CO-01"),
            ("authority", "DOES_NOT_ARM / DOES_NOT_MUTATE_RC3_OR_RC4_BYTES / DARK_UNTIL_B01C"),
            ("posture", "OFF/OFF/OFF/LIVE"),
            ("activation_result", "DENIED_SAFE_HOLD"),
            ("consumption", "GATED_BEHIND_B01C"),
            ("rc3_html_sha256", RC3_HTML_SHA256),
            ("rc4_html_sha256", RC4_HTML_SHA256),
            ("supersession_families_expected", len(families)),
            ("supersession_families_applied", len(families) - len(halted)),
            ("supersession_families_halted", len(halted)),
            ("co03_additive_contracts_carried", list(co03_added)),
            ("operation_log", operation_log),
        ]
    )

    assertion_log = run_assertions(rc5, rc4_bundle, halted_names)
    rc5["rc5_provenance"]["assertions"] = assertion_log

    output_digest = sha256_text(canonical(rc5))
    rc5["rc5_provenance"]["output_digest_self_excluded"] = _digest_excluding_self(rc5)

    manifest = OrderedDict(
        [
            ("schema", "triad.origin.v7.rc5_manifest.v1"),
            ("applier_version", APPLIER_VERSION),
            ("document_id", "TRIAD-ORIGIN-V7-CHANGE-ORDERS-2026-08-12"),
            ("change_order", "CO-01"),
            (
                "input_preimages",
                OrderedDict(
                    [
                        (
                            "rc3_master_html",
                            OrderedDict(
                                [
                                    (
                                        "path",
                                        "docs/spec_rc3/"
                                        "TRIAD_ORIGIN_V7_COMPLETE_MASTER_SPECIFICATION_"
                                        "AND_MASTER_DOCUMENT_1.0.0_RC3.html",
                                    ),
                                    ("sha256", RC3_HTML_SHA256),
                                ]
                            ),
                        ),
                        (
                            "rc4_addendum_html",
                            OrderedDict(
                                [
                                    (
                                        "path",
                                        "docs/spec_rc4/"
                                        "TRIAD_ORIGIN_V7_FOUR_PLANE_EXECUTION_"
                                        "AND_LEVER_MASTER_ADDENDUM_1.0.0_RC4.html",
                                    ),
                                    ("sha256", RC4_HTML_SHA256),
                                ]
                            ),
                        ),
                        (
                            "rc3_effective_control_bundle",
                            OrderedDict(
                                [
                                    ("path", "docs/control/rc3_effective_control_bundle.json"),
                                    ("sha256", record_digest(rc3_bundle)),
                                ]
                            ),
                        ),
                        (
                            "rc4_control_bundle",
                            OrderedDict(
                                [
                                    ("path", "docs/control/rc4_control_bundle.json"),
                                    ("sha256", record_digest(rc4_bundle)),
                                ]
                            ),
                        ),
                    ]
                ),
            ),
            ("operation_log", operation_log),
            ("supersession_families_expected", len(families)),
            ("supersession_families_applied", len(families) - len(halted)),
            ("supersession_families_halted", len(halted)),
            ("halted_families", halted),
            ("output_digest", output_digest),
            ("posture", "OFF/OFF/OFF/LIVE"),
            ("activation_result", "DENIED_SAFE_HOLD"),
        ]
    )

    conflict_report = OrderedDict(
        [
            ("schema", "triad.origin.v7.rc5_conflict_report.v1"),
            ("applier_version", APPLIER_VERSION),
            ("change_order", "CO-01"),
            ("families_expected", len(families)),
            ("families", conflict_families),
        ]
    )

    return rc5, manifest, conflict_report


def _digest_excluding_self(rc5: dict) -> str:
    """A stable digest of the bundle minus the self-referential digest fields — so the
    manifest's output_digest and this field are both reproducible and non-circular."""
    clone = deepcopy(rc5)
    prov = clone.get("rc5_provenance", {})
    prov.pop("output_digest_self_excluded", None)
    return sha256_text(canonical(clone))


# --------------------------------------------------------------------------- #
# Bundle JSON Schema (CO-01 Step 4).                                           #
# --------------------------------------------------------------------------- #


def build_schema() -> dict:
    return OrderedDict(
        [
            ("$schema", "https://json-schema.org/draft/2020-12/schema"),
            ("$id", "https://triad.internal/contracts/rc5_effective_control_bundle.v1.schema.json"),
            ("title", "RC5 effective consolidation bundle"),
            ("type", "object"),
            (
                "required",
                [
                    "schema",
                    "tasks",
                    "criteria",
                    "verifications",
                    "parameters",
                    "formulas",
                    "gates",
                    "wiring",
                    "rc5_provenance",
                    "rc5_schema_installs",
                ],
            ),
            (
                "properties",
                OrderedDict(
                    [
                        ("schema", {"type": "string"}),
                        ("tasks", {"type": "array"}),
                        ("criteria", {"type": "array"}),
                        ("verifications", {"type": "array"}),
                        ("parameters", {"type": "array"}),
                        ("formulas", {"type": "array"}),
                        ("formula_parameter_bindings", {"type": "array"}),
                        ("dependencies", {"type": "array"}),
                        ("gates", {"type": "array"}),
                        ("crosswalk", {"type": "array"}),
                        ("golden_vectors", {"type": "array"}),
                        ("wiring", {"type": "array"}),
                        (
                            "rc5_schema_installs",
                            OrderedDict(
                                [
                                    ("type", "object"),
                                    (
                                        "properties",
                                        OrderedDict(
                                            [
                                                (
                                                    "rc5_lever_vocabulary",
                                                    _schema_install_shape(),
                                                ),
                                                (
                                                    "rc5_receipt_schema_binding",
                                                    _schema_install_shape(),
                                                ),
                                                (
                                                    "rc5_mcp_family_activation",
                                                    _schema_install_shape(),
                                                ),
                                            ]
                                        ),
                                    ),
                                ]
                            ),
                        ),
                        (
                            "rc5_provenance",
                            OrderedDict(
                                [
                                    ("type", "object"),
                                    (
                                        "required",
                                        [
                                            "schema",
                                            "applier_version",
                                            "authority",
                                            "posture",
                                            "activation_result",
                                            "supersession_families_expected",
                                            "supersession_families_applied",
                                            "operation_log",
                                            "assertions",
                                        ],
                                    ),
                                    (
                                        "properties",
                                        OrderedDict(
                                            [
                                                ("schema", {"type": "string"}),
                                                ("applier_version", {"type": "string"}),
                                                ("authority", {"type": "string"}),
                                                (
                                                    "posture",
                                                    {"const": "OFF/OFF/OFF/LIVE"},
                                                ),
                                                (
                                                    "activation_result",
                                                    {"const": "DENIED_SAFE_HOLD"},
                                                ),
                                                (
                                                    "supersession_families_expected",
                                                    {"const": 10},
                                                ),
                                                (
                                                    "supersession_families_applied",
                                                    {"type": "integer"},
                                                ),
                                                (
                                                    "operation_log",
                                                    {"type": "array"},
                                                ),
                                                ("assertions", {"type": "array"}),
                                            ]
                                        ),
                                    ),
                                ]
                            ),
                        ),
                    ]
                ),
            ),
        ]
    )


def _schema_install_shape() -> dict:
    return OrderedDict(
        [
            ("type", "object"),
            ("required", ["schema_slot", "family", "operation", "rc4_record", "effective"]),
            (
                "properties",
                OrderedDict(
                    [
                        ("schema_slot", {"type": "string"}),
                        ("family", {"type": "string"}),
                        (
                            "operation",
                            {
                                "enum": [
                                    OP_REPLACE_RECORD,
                                    OP_RENAME_PARAMETER,
                                    OP_REPLACE_SCHEMA,
                                    OP_RETIRE_VOCABULARY,
                                ]
                            },
                        ),
                        ("rc4_record", {"type": "string"}),
                        ("effective", {"type": "object"}),
                    ]
                ),
            ),
        ]
    )


# --------------------------------------------------------------------------- #
# Load / emit / verify.                                                        #
# --------------------------------------------------------------------------- #


def load_inputs() -> tuple[dict, dict]:
    rc3 = json.loads(RC3_BUNDLE_PATH.read_text(encoding="utf-8"))
    rc4 = json.loads(RC4_BUNDLE_PATH.read_text(encoding="utf-8"))
    return rc3, rc4


def verify_input_preimages() -> None:
    """Assert the frozen HTML preimage digests match the on-disk RC3/RC4 master bytes."""
    if RC3_HTML_PATH.exists():
        got = sha256_bytes(RC3_HTML_PATH.read_bytes())
        if got != RC3_HTML_SHA256:
            raise Rc5AssertionError(f"RC3 preimage digest mismatch: {got}")
    if RC4_HTML_PATH.exists():
        got = sha256_bytes(RC4_HTML_PATH.read_bytes())
        if got != RC4_HTML_SHA256:
            raise Rc5AssertionError(f"RC4 preimage digest mismatch: {got}")


def compile_rc5() -> tuple[dict, dict, dict, dict]:
    verify_input_preimages()
    rc3, rc4 = load_inputs()
    rc5, manifest, conflict = apply(rc3, rc4)
    schema = build_schema()
    return rc5, manifest, conflict, schema


def _dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main() -> int:
    rc5, manifest, conflict, schema = compile_rc5()
    _dump(OUT_BUNDLE, rc5)
    _dump(OUT_MANIFEST, manifest)
    _dump(OUT_CONFLICT, conflict)
    _dump(OUT_SCHEMA, schema)
    applied = manifest["supersession_families_applied"]
    halted = manifest["supersession_families_halted"]
    print(
        f"RC5 compiled: {applied}/{manifest['supersession_families_expected']} families applied, "
        f"{halted} halted; output_digest={manifest['output_digest'][:16]}…"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
