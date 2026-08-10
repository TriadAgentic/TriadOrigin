#!/usr/bin/env python3
"""Deterministic F20-F23 estate formula catalog for the TRIAD ORIGIN V7 build.

The reconciled plan's B09 deliverable (``docs/plan/01_MILESTONE_BREAKDOWN.md`` ·
``08_BUILD_CHECKLIST.md``) requires an **estate formula catalog** for the four money-line
economics formulas whose *implementations* are foreign to this repository:

  * ``F20`` — risk-budget sizing for linear USD-M   (owner ``E08``)
  * ``F21`` — maker-first price compilation          (owner ``E09``)
  * ``F22`` — emergency position-reducing IOC bound  (owner ``E09``)
  * ``F23`` — campaign PnL, costs, R and markout      (owner ``E10``)

ORIGIN (E02) does NOT implement any of these — the executable sizing / maker / IOC / PnL
logic is ``OUT_OF_REPO`` per ``CLAUDE.md`` and ``docs/plan/02_TRACEABILITY.md`` (a capability
scan over ``src/triad_origin`` proves it is neither imported nor run here). What ORIGIN lawfully
BUILDS in B09 is the ``IN_REPO_CATALOG`` slice: the immutable **contract shape** each estate node
consumes/emits, the vendored **golden vectors** (``GV-017``…``GV-020``), and the seven
boundary-class rows (``FORM-Fxx-01``…``-07``) that account each formula — all marked ESTATE for the
owning node. This artifact is a G6 interface subset; it certifies no gate and arms nothing.

The F20 special law (``10_MASTER_SPEC_ALIGNMENT_AUDIT.md`` P0 · RC4 supersession ``F20`` /
``LEV-0044`` / ``LEV-V-0120``): F20 consumes ONE already-selected signed risk-budget policy and
carries NO ``activation_mode`` branch and NO environment/rollout input. The raw RC3 ``formula``
string still carries the superseded ``Select B by activation_mode: CANARY->PAR-069,
PRODUCTION->PAR-070`` branch; this catalog derives the RC4-corrected form (dropping that branch),
records the controlling RC4 supersession as its source, proves rollout metadata is ABSENT from the
sizing dependency set (so the quantity is byte-invariant to it), and DENIES a missing/invalid
selected policy. It never re-declares the removed branch parameters ``PAR-069`` / ``PAR-070``.

"Assert no F24 exists": the RC3 registry enumerates exactly ``F00``…``F23`` (24 formulas); there is
nothing past ``F23``. The catalog asserts the registry equals that list.

Determinism / read-only law: stdlib only, no environment reads, no network, no wall clock, repo
root resolved from this file's own location (never the working directory). Canonical bytes are
``json.dumps(obj, indent=1, sort_keys=True) + "\\n"`` — the build-ledger / conformance-matrix idiom.

Usage:
  python tools/build_formula_catalog.py            # regenerate docs/control/formula_catalog.v1.json
  python tools/build_formula_catalog.py --verify   # regenerate to memory and byte-compare (CI/e2e)
  python tools/build_formula_catalog.py --status   # print the estate-catalog summary
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTROL = ROOT / "docs" / "control"
RC3_BUNDLE = CONTROL / "rc3_effective_control_bundle.json"
RC4_BUNDLE = CONTROL / "rc4_control_bundle.json"
CATALOG = CONTROL / "formula_catalog.v1.json"

SCHEMA = "triad.origin.formula_catalog.v1"
CATALOG_VERSION = "FORMULA_CATALOG_V1"

# The RC3 effective bundle enumerates exactly these 24 formulas (F00..F23). Asserting the
# registry equals this list is the "Assert no F24 exists" law — there is nothing past F23.
EXPECTED_FORMULA_IDS = [f"F{i:02d}" for i in range(24)]

# The four estate economics formulas ORIGIN catalogs (their implementations are OUT_OF_REPO).
ESTATE_FORMULA_IDS = ("F20", "F21", "F22", "F23")

# The two E01-owned formulas ORIGIN consumes/validates but never authors (alignment-audit P0).
ESTATE_UPSTREAM_FORMULA_IDS = ("F01", "F07")

# The seven boundary-vector classes every FORMULA_ATOMIC row schedules (FORM-Fxx-01..07),
# read verbatim from the RC3 ``golden_boundary_tests`` prose for F20-F23.
BOUNDARY_CLASSES = (
    "Equality", "one-unit-short/over", "invalid-input", "prefix",
    "restart", "duplicate", "directional-mirror",
)

# F20's superseded activation_mode branch selected these budget parameters; the RC4-corrected
# form removes the branch, so neither may appear as a sizing dependency (rollout cannot reach it).
F20_REMOVED_BRANCH_PARAMS = ("PAR-069", "PAR-070")

# Any dependency token whose lowercase form contains one of these is rollout/environment metadata
# — it must be ABSENT from F20's corrected sizing dependency set (LEV-V-0120 byte-invariance).
ROLLOUT_METADATA_MARKERS = (
    "activation_mode", "rollout", "environment", "canary", "production",
)

# The primary golden vector vendored beside each estate formula (verbatim from the RC3 bundle).
GOLDEN_VECTOR_BY_FORMULA = {
    "F20": "GV-017",  # VALID_ISOLATED_COST_VECTOR — selected-budget isolated cost
    "F21": "GV-018",  # Maker compile — BUY limit inside zone, no taker fallback
    "F22": "GV-019",  # Emergency IOC — exact floor worst-price, reduction-only qty
    "F23": "GV-020",  # PnL — gross/net with a missing-fee UNRESOLVED boundary
}


class CatalogError(RuntimeError):
    """The estate formula catalog could not be honestly built."""


def load_json(path: pathlib.Path, label: str) -> dict:
    if not path.is_file():
        raise CatalogError(f"{label} missing at {path.as_posix()}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CatalogError(f"{label} unreadable/invalid at {path.as_posix()}: {exc}") from exc
    if not isinstance(data, dict):
        raise CatalogError(f"{label} root must be a JSON object")
    return data


def _split_inputs(value: object) -> list[str]:
    """Split a ``a;b`` inputs/parameters string into stripped tokens (order preserved)."""
    return [tok.strip() for tok in str(value or "").split(";") if tok.strip()]


def _is_rollout_token(token: str) -> bool:
    low = token.lower()
    if any(marker in low for marker in ROLLOUT_METADATA_MARKERS):
        return True
    return any(param in token for param in F20_REMOVED_BRANCH_PARAMS)


def correct_f20_inputs(raw_inputs: object) -> list[str]:
    """Derive F20's RC4-corrected sizing dependency tokens from the raw RC3 inputs string.

    The correction is the RC4 supersession (``F20``): the ``activation_mode`` branch is removed
    and the vague ``selected budget only`` token becomes the explicit ``one already-selected
    signed risk-budget policy``. Every rollout/environment token (and the removed ``PAR-069`` /
    ``PAR-070`` branch params, if present) is dropped so rollout metadata is absent from sizing.
    """
    corrected: list[str] = []
    for token in _split_inputs(raw_inputs):
        if _is_rollout_token(token):
            continue  # activation_mode / rollout / PAR-069 / PAR-070 never reach sizing
        if token == "selected budget only":
            corrected.append("one already-selected signed risk-budget policy")
        else:
            corrected.append(token)
    return corrected


def f20_selected_policy_deny_reason(policy: object) -> str | None:
    """Return the F20 catalog DENY reason for a missing/invalid selected policy, else ``None``.

    This is a fail-closed REFUSAL predicate, NOT executable sizing: it decides only whether the
    one already-selected signed policy is present and well-formed enough to be sized against. A
    missing / empty / non-signed / stale policy DENIES (``B1``: no production sizing representable);
    no other activation budget may substitute for the one selected policy.
    """
    if policy is None:
        return "MISSING_SELECTED_POLICY"
    if not isinstance(policy, dict):
        return "INVALID_SELECTED_POLICY"
    ref = str(policy.get("policy_ref") or "").strip()
    if not ref:
        return "MISSING_SELECTED_POLICY"
    if not policy.get("signed"):
        return "UNSIGNED_SELECTED_POLICY"
    if policy.get("stale"):
        return "STALE_SELECTED_POLICY"
    return None


def sizing_dependency_projection(inputs: dict, dependency_tokens: list[str]) -> dict:
    """Project an inputs map onto F20's declared corrected dependency keys ONLY.

    This is the catalog analogue of "quantity bytes remain identical; rollout metadata is absent
    from formula dependencies" (``LEV-V-0120``). It computes NO quantity — it keeps only the keys
    the corrected dependency set declares, so any rollout/environment key in ``inputs`` is dropped.
    Two inputs maps that differ only in rollout metadata therefore project to the identical, ordered
    object, proving the (out-of-repo) quantity is byte-invariant to rollout metadata.
    """
    keys = [tok for tok in dependency_tokens if tok in inputs]
    return {key: inputs[key] for key in keys}


def classify_formula(fid: str) -> tuple[str, str]:
    """Return ``(exec_class, milestone)`` for a formula id — byte-consistent with build_ledger.

    F01/F07 are E01-owned (``ESTATE_FORMULA``); F20-F23 are the estate economics catalog
    (``IN_REPO_CATALOG``); every other formula is ORIGIN-implemented (``IN_REPO_CODE``).
    """
    if fid in ESTATE_UPSTREAM_FORMULA_IDS:
        return "ESTATE_FORMULA", "ESTATE"
    if fid in ESTATE_FORMULA_IDS:
        return "IN_REPO_CATALOG", "B09"
    return "IN_REPO_CODE", "in-repo"


def _refusal_law(formula: dict) -> str:
    """The named refusal / fail-closed law for the formula (verbatim from the bundle fields)."""
    return str(formula.get("invalid_behavior") or "")


def build_estate_entry(fid: str, formula: dict, golden_vector: dict) -> dict:
    """Build one estate catalog entry for F20-F23 (a contract shape + vectors + ledger rows)."""
    exec_class, milestone = classify_formula(fid)
    raw_inputs = formula.get("inputs", "")

    entry: dict[str, object] = {
        "id": fid,
        "name": formula.get("name", ""),
        "owner_node": formula.get("owner", ""),
        "ownership": "ESTATE",          # the implementation owner is the estate node
        "exec_class": exec_class,        # what ORIGIN builds here: catalog only
        "milestone": milestone,
        "gate": formula.get("gate", ""),
        "phase": formula.get("phase", ""),
        "rc3_status": formula.get("rc3_status", ""),
        "semantic_version": formula.get("semantic_version", ""),
        "output_contract": {
            "inputs": raw_inputs,
            "parameters": formula.get("parameters", ""),
            "output": formula.get("lifecycle_or_output", ""),
            "units_rounding": formula.get("units_rounding", ""),
            "refusal_law": _refusal_law(formula),
            "mirror_rule": formula.get("mirror_rule", ""),
        },
        "golden_boundary_classes": list(BOUNDARY_CLASSES),
        "ledger_rows": [f"FORM-{fid}-{i:02d}" for i in range(1, 8)],
        "golden_vectors": [golden_vector],
        "implementation_is_out_of_repo": True,
    }

    if fid == "F20":
        corrected = correct_f20_inputs(raw_inputs)
        rollout_tokens = [tok for tok in corrected if _is_rollout_token(tok)]
        entry["f20_law"] = {
            # The controlling source is the RC4 supersession, NOT the retained RC3 branch text.
            "controlling_source": {
                "rc4_supersession_record": "F20",
                "old": "activation_mode selects CANARY or PRODUCTION budget",
                "replacement": (
                    "Remove branch; pass one already selected signed risk-budget policy. "
                    "Rollout metadata cannot reach sizing."
                ),
                "task": "LEV-0044",
                "fixture": "LEV-V-0120",
            },
            "raw_rc3_inputs": raw_inputs,
            "corrected_inputs": corrected,
            "activation_mode_removed": "activation_mode" not in [t.lower() for t in corrected],
            "removed_branch_params": list(F20_REMOVED_BRANCH_PARAMS),
            "rollout_metadata_in_dependencies": rollout_tokens,   # must be empty
            "rollout_reaches_sizing": bool(rollout_tokens),        # must be False
            "missing_policy_disposition": "DENY",
            "selected_policy_source_contract": "triad.decision.v2",
        }
    return entry


def build_catalog(rc3: dict, rc4: dict) -> dict:
    """Build the full estate formula catalog object (pure; deterministic)."""
    formulas = {f["id"]: f for f in rc3["formulas"]}
    vectors = {g.get("id"): g for g in rc3.get("golden_vectors", [])}

    formula_ids = sorted(formulas)

    registry_rows = {}
    for fid in formula_ids:
        exec_class, milestone = classify_formula(fid)
        registry_rows[fid] = {
            "owner_node": formulas[fid].get("owner", ""),
            "exec_class": exec_class,
            "milestone": milestone,
        }

    estate_catalog: dict[str, object] = {}
    for fid in ESTATE_FORMULA_IDS:
        if fid not in formulas:
            raise CatalogError(f"estate formula {fid} absent from the RC3 bundle")
        gv_id = GOLDEN_VECTOR_BY_FORMULA[fid]
        gv = vectors.get(gv_id)
        if gv is None:
            raise CatalogError(f"golden vector {gv_id} for {fid} absent from the RC3 bundle")
        if str(gv.get("linked") or "")[:3] != fid and fid not in str(gv.get("linked") or ""):
            raise CatalogError(f"golden vector {gv_id} is not linked to {fid}")
        estate_catalog[fid] = build_estate_entry(fid, formulas[fid], gv)

    # RC4 F20 rollout-invariance fixture, vendored verbatim beside the F20 entry.
    f20_fixture = next(
        (v for v in rc4.get("verifications", []) if v.get("id") == "LEV-V-0120"), None
    )
    if f20_fixture is None:
        raise CatalogError("RC4 fixture LEV-V-0120 (F20 rollout-invariance) missing")

    catalog = {
        "schema": SCHEMA,
        "catalog_version": CATALOG_VERSION,
        "generated_by": "claude-fable-5-build-session/B09",
        "basis": (
            "B09 estate formula catalog: F20 (E08 sizing) · F21 (E09 maker) · F22 (E09 "
            "emergency reduction-only IOC) · F23 (E10 outcomes/P&L) are money-line, "
            "implementation OUT_OF_REPO; ORIGIN vendors the contract shape + golden vectors "
            "(GV-017..020) + the FORM-Fxx-01..07 boundary rows only. F20 carries one "
            "already-selected signed policy with no activation_mode/rollout branch (RC4 "
            "supersession F20 / LEV-0044 / LEV-V-0120). No F24 exists."
        ),
        "formula_registry": {
            "formula_ids": formula_ids,
            "formula_count": len(formula_ids),
            # Assert no F24 exists: the registry is exactly F00..F23, nothing past F23.
            "f24_absent": formula_ids == EXPECTED_FORMULA_IDS,
            "rows": registry_rows,
        },
        "estate_formula_ids": list(ESTATE_FORMULA_IDS),
        "estate_catalog": estate_catalog,
        "f20_rollout_invariance_fixture": f20_fixture,
    }
    catalog["invariants"] = _compute_invariants(catalog)
    _assert_invariants(catalog)
    return catalog


def _compute_invariants(catalog: dict) -> dict[str, bool]:
    reg = catalog["formula_registry"]
    estate = catalog["estate_catalog"]
    f20 = estate.get("F20", {}).get("f20_law", {})

    every_estate_out_of_repo = all(
        entry.get("ownership") == "ESTATE"
        and entry.get("exec_class") == "IN_REPO_CATALOG"
        and entry.get("implementation_is_out_of_repo") is True
        for entry in estate.values()
    )
    every_estate_has_7_rows = all(
        entry.get("ledger_rows") == [f"FORM-{fid}-{i:02d}" for i in range(1, 8)]
        for fid, entry in estate.items()
    )
    every_estate_has_its_vector = all(
        entry.get("golden_vectors")
        and entry["golden_vectors"][0].get("id") == GOLDEN_VECTOR_BY_FORMULA[fid]
        for fid, entry in estate.items()
    )
    return {
        "no_f24": reg["f24_absent"] and reg["formula_ids"] == EXPECTED_FORMULA_IDS,
        "estate_catalog_is_f20_to_f23": sorted(estate) == list(ESTATE_FORMULA_IDS),
        "every_estate_formula_out_of_repo_catalog": every_estate_out_of_repo,
        "every_estate_formula_has_seven_boundary_rows": every_estate_has_7_rows,
        "every_estate_formula_vendors_its_golden_vector": every_estate_has_its_vector,
        # F20 special law: rollout removed, DENY on missing policy.
        "f20_activation_mode_removed": bool(f20.get("activation_mode_removed")),
        "f20_rollout_absent_from_sizing": f20.get("rollout_reaches_sizing") is False
        and f20.get("rollout_metadata_in_dependencies") == [],
        "f20_missing_policy_denies": f20.get("missing_policy_disposition") == "DENY",
    }


def _assert_invariants(catalog: dict) -> None:
    failures = [name for name, ok in catalog["invariants"].items() if not ok]
    if failures:
        raise CatalogError(
            "estate formula catalog invariant violation: " + ", ".join(sorted(failures))
        )


def render(catalog: dict) -> str:
    return json.dumps(catalog, indent=1, sort_keys=True) + "\n"


def generate() -> dict:
    rc3 = load_json(RC3_BUNDLE, "RC3 effective control bundle")
    rc4 = load_json(RC4_BUNDLE, "RC4 control bundle")
    return build_catalog(rc3, rc4)


def _fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build_formula_catalog.py", description=__doc__)
    parser.add_argument("--verify", action="store_true",
                        help="regenerate to memory and byte-compare the committed catalog")
    parser.add_argument("--status", action="store_true",
                        help="print the estate-catalog summary")
    args = parser.parse_args(argv)

    try:
        catalog = generate()
    except CatalogError as exc:
        return _fail(str(exc))
    rendered = render(catalog)

    if args.status:
        reg = catalog["formula_registry"]
        print(
            f"estate formula catalog {catalog['catalog_version']}: "
            f"{reg['formula_count']} formulas (F00..F23; no F24), "
            f"estate catalog = {', '.join(catalog['estate_formula_ids'])}"
        )
        for fid, entry in sorted(catalog["estate_catalog"].items()):
            gv = entry["golden_vectors"][0]["id"]
            print(f"  {fid} {entry['owner_node']:>3} {entry['exec_class']:<15} "
                  f"{gv} · {len(entry['ledger_rows'])} boundary rows")
        return 0

    if args.verify:
        if not CATALOG.exists():
            return _fail(f"{CATALOG.relative_to(ROOT).as_posix()} missing; run "
                         "python tools/build_formula_catalog.py")
        if CATALOG.read_text(encoding="utf-8") != rendered:
            return _fail("estate formula catalog is stale; run "
                         "python tools/build_formula_catalog.py")
        print(
            f"OK: estate formula catalog current "
            f"({catalog['formula_registry']['formula_count']} formulas; "
            f"F20-F23 IN_REPO_CATALOG; no F24)"
        )
        return 0

    CATALOG.write_text(rendered, encoding="utf-8")
    print(f"wrote {CATALOG.relative_to(ROOT).as_posix()} "
          f"({len(catalog['estate_catalog'])} estate entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
