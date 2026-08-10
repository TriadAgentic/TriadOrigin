#!/usr/bin/env python3
"""B01C-CON-03/06 — the recursive schema-mutation corpus (WP-B01C-06 acceptance CLI).

This tool changes no schema. It drives the AUTHORITATIVE validator
(:func:`triad_origin.contracts.validate`) over every registered contract's valid golden, generates a
deterministic family of mutations, and proves two things:

* **CON-03 enforcement** — every mutation that violates a CLOSED constraint (a missing required
  member, a wrong type, a declared pattern/enum/const, a typed array item, a wire-canonical integer)
  is REFUSED. A closure-required mutation that passes is a validator hole (exit 1).
* **CON-01/02 inventory** — an ``unknown_nested_field`` probe is added at every object path; where it
  is refused the boundary is closed, where it passes the boundary is OPEN. The open set is the
  documented CON-01/CON-02 surface — enumerated as evidence, never closed here (closing a published
  schema is an owner/anchor-gated new-major train, not offline-prep).

Deterministic: the report and its ``corpus_digest`` are identical across ``PYTHONHASHSEED`` values.
Fail-closed: if the full validator is unavailable the tool exits 3 (never a silent pass).
"""

from __future__ import annotations

import argparse
import copy
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import contracts  # noqa: E402
from triad_origin.canonical import canonical_json, sha256_hex  # noqa: E402

GOLDEN = ROOT / "contracts" / "golden"

PROBE_KEY = "__triad_mutation_probe__"

# Families whose mutation violates a CLOSED constraint — the validator MUST refuse each.
CLOSURE_FAMILIES = (
    "missing_required", "wrong_type", "bad_pattern", "bad_enum", "bad_const",
    "malformed_array_item", "wire_noncanonical",
)


def _resolve(schema_root: dict, node: dict) -> dict:
    """Follow a local ``$ref`` and shallow-merge ``allOf`` so required/type/properties are visible.

    Conservative: unresolved composition (anyOf/oneOf/if) is returned as-is, which only REDUCES the
    mutations generated there — it never fabricates a false closure-required mutation.
    """
    seen = 0
    while isinstance(node, dict) and "$ref" in node and node["$ref"].startswith("#/") and seen < 8:
        target: object = schema_root
        for part in node["$ref"][2:].split("/"):
            if not isinstance(target, dict):
                return node
            target = target.get(part, {})
        node = target if isinstance(target, dict) else {}
        seen += 1
    if isinstance(node, dict) and isinstance(node.get("allOf"), list):
        merged: dict = {k: v for k, v in node.items() if k != "allOf"}
        props = dict(merged.get("properties", {}))
        required = list(merged.get("required", []))
        for sub in node["allOf"]:
            sub = _resolve(schema_root, sub) if isinstance(sub, dict) else {}
            props.update(sub.get("properties", {}))
            required.extend(sub.get("required", []))
            merged.setdefault("type", sub.get("type"))
            if sub.get("additionalProperties") is False:
                merged["additionalProperties"] = False
        if props:
            merged["properties"] = props
        if required:
            merged["required"] = sorted(set(required))
        return merged
    return node


def _wrong_typed_value(value: object) -> object:
    if isinstance(value, bool):
        return "not_a_bool"
    if isinstance(value, str):
        return 123456
    if isinstance(value, int):
        return "not_an_integer"
    if isinstance(value, float):
        return "not_a_number"
    if isinstance(value, list):
        return {"unexpected": "object"}
    if isinstance(value, dict):
        return ["unexpected", "array"]
    return "not_null"


def _violates(pattern: str, candidate: str) -> bool:
    """True iff ``candidate`` genuinely fails ``pattern`` under jsonschema semantics (re.search).

    jsonschema matches ``pattern`` with an unanchored, case-sensitive ``re.search``. Verifying the
    candidate against that exact predicate makes a REFUSE mutation *provably* pattern-violating —
    never a heuristic guess that a future unanchored/case-insensitive pattern could quietly satisfy.
    """
    try:
        return re.search(pattern, candidate) is None
    except re.error:
        return False  # an unparseable pattern is not a guaranteed violation


def _pattern_violator(pattern: str, value: str) -> str | None:
    """A string that DEFINITELY violates ``pattern``, or None if we cannot guarantee violation."""
    candidate: str | None = None
    if "[0-9a-f]" in pattern and "{" in pattern and value:
        upper = value.upper()
        candidate = upper if upper != value else None  # uppercase a lowercase-hex field
    elif ("(0|[1-9]" in pattern or "[0-9]" in pattern) and pattern.startswith("^"):
        candidate = "01"  # a leading-zero integer violates every canonical wire-int pattern
    if candidate is not None and _violates(pattern, candidate):
        return candidate
    return None


def _mutations(schema_root: dict, node: dict, value: object, ptr: str):
    """Yield ``(family, pointer, mutate_fn, kind)`` where kind is 'REFUSE' or 'PROBE'.

    ``mutate_fn(event_value)`` returns the mutated value at ``ptr``. Generation is deterministic
    (sorted keys) and only emits a closure-required family where the schema declares that constraint.
    """
    node = _resolve(schema_root, node)
    if not isinstance(node, dict):
        return
    t = node.get("type")

    # --- object node -----------------------------------------------------------------------------
    if isinstance(value, dict) and (t == "object" or "properties" in node or "required" in node):
        for req in sorted(node.get("required", [])):
            if req in value:
                yield ("missing_required", f"{ptr}/{req}",
                       (lambda v, k=req: {kk: vv for kk, vv in v.items() if kk != k}), "REFUSE")
        closed = node.get("additionalProperties") is False
        yield ("unknown_nested_field", f"{ptr}/{PROBE_KEY}",
               (lambda v: {**v, PROBE_KEY: "unexpected"}),
               "REFUSE" if closed else "PROBE")
        props = node.get("properties", {})
        for key in sorted(value):
            if key in props:
                yield from _mutations(schema_root, props[key], value[key], f"{ptr}/{key}")
        return

    # --- typed scalar ----------------------------------------------------------------------------
    if isinstance(t, str) and t not in ("object", "array"):
        yield ("wrong_type", ptr, (lambda v: _wrong_typed_value(v)), "REFUSE")
        if isinstance(node.get("enum"), list):
            yield ("bad_enum", ptr, (lambda v: "__not_in_enum__"), "REFUSE")
        if "const" in node:
            yield ("bad_const", ptr, (lambda v, c=node["const"]: f"not::{c}"), "REFUSE")
        if isinstance(value, str) and isinstance(node.get("pattern"), str):
            bad = _pattern_violator(node["pattern"], value)
            if bad is not None:
                yield ("bad_pattern", ptr, (lambda v, b=bad: b), "REFUSE")
            if "[0-9]" in node["pattern"] and ("(0|" in node["pattern"] or "[1-9]" in node["pattern"]) \
                    and _violates(node["pattern"], " 1"):
                yield ("wire_noncanonical", ptr, (lambda v: " 1"), "REFUSE")  # leading whitespace
        return

    # --- typed array -----------------------------------------------------------------------------
    if t == "array" and isinstance(value, list) and value:
        items = node.get("items")
        if isinstance(items, dict):
            yield ("malformed_array_item", f"{ptr}/0",
                   (lambda v: [_wrong_typed_value(v[0])] + list(v[1:])), "REFUSE")
            yield from _mutations(schema_root, items, value[0], f"{ptr}/0")


def _run_one(schema_id: str) -> dict:
    golden = json.loads((GOLDEN / schema_id / "valid.json").read_text(encoding="utf-8"))
    schema = _schema(schema_id)
    records = []
    for family, ptr, mutate, kind in _mutations(schema, schema, golden, ""):
        mutated = _materialize(golden, ptr, family, mutate)
        refused = _validate_refused(mutated, schema_id)
        records.append({"schema_id": schema_id, "pointer": ptr, "family": family,
                        "kind": kind, "refused": refused})
    return {"schema_id": schema_id, "records": records}


def _schema(schema_id: str) -> dict:
    return contracts.load_schema(schema_id)


def _materialize(golden: dict, ptr: str, family: str, mutate) -> dict:
    out = copy.deepcopy(golden)
    parts = [p for p in ptr.split("/") if p != ""]
    if family in ("missing_required", "unknown_nested_field"):
        container = _walk_to(out, parts[:-1])
        new = mutate(container)
        _set_at(out, parts[:-1], new)
        return out
    if family == "malformed_array_item":
        container = _walk_to(out, parts[:-1])   # the array
        _set_at(out, parts[:-1], mutate(container))
        return out
    # scalar value-level families
    container_parts, leaf = parts[:-1], parts[-1]
    parent = _walk_to(out, container_parts)
    cur = parent[int(leaf)] if isinstance(parent, list) else parent[leaf]
    newval = mutate(cur)
    if isinstance(parent, list):
        parent[int(leaf)] = newval
    else:
        parent[leaf] = newval
    return out


def _walk_to(obj, parts):
    for seg in parts:
        obj = obj[int(seg)] if isinstance(obj, list) else obj[seg]
    return obj


def _set_at(obj, parts, value):
    if not parts:
        # replacing root is not used (root is always an object with sub-parts)
        obj.clear()
        obj.update(value)
        return
    parent = _walk_to(obj, parts[:-1])
    leaf = parts[-1]
    if isinstance(parent, list):
        parent[int(leaf)] = value
    else:
        parent[leaf] = value


def _validate_refused(event: dict, schema_id: str) -> bool:
    try:
        contracts.validate(event, schema_id=schema_id)
        return False
    except contracts.SchemaValidatorUnavailable:
        raise
    except contracts.ContractError:
        return True


def run_profile(profile: str) -> dict:
    if profile != "B01C":
        raise SystemExit(f"unknown profile: {profile!r}")
    per_schema = []
    total = refused = wrongly_passed = open_boundaries = 0
    open_inventory = []
    wrong = []
    for schema_id in sorted(contracts.known_contracts()):
        result = _run_one(schema_id)
        for rec in result["records"]:
            total += 1
            if rec["kind"] == "PROBE":
                if not rec["refused"]:
                    open_boundaries += 1
                    open_inventory.append({"schema_id": schema_id, "pointer": rec["pointer"]})
                continue
            # REFUSE (closure-required)
            if rec["refused"]:
                refused += 1
            else:
                wrongly_passed += 1
                wrong.append({"schema_id": schema_id, "pointer": rec["pointer"],
                              "family": rec["family"]})
        per_schema.append({"schema_id": schema_id, "mutation_count": len(result["records"])})
    report = {
        "profile": profile,
        "validator": "full_draft2020_12",
        "contract_count": len(per_schema),
        "totals": {
            "mutations": total,
            "closure_required_refused": refused,
            "closure_required_wrongly_passed": wrongly_passed,
            "open_boundaries": open_boundaries,
        },
        "wrongly_passed": sorted(wrong, key=lambda r: (r["schema_id"], r["pointer"], r["family"])),
        "open_boundary_inventory": sorted(open_inventory,
                                          key=lambda r: (r["schema_id"], r["pointer"])),
        "per_schema": per_schema,
    }
    report["corpus_digest"] = sha256_hex(canonical_json(report))
    return report


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="B01C")
    parser.add_argument("--require-all-refused", action="store_true",
                        help="exit non-zero if any closure-required mutation wrongly passed")
    parser.add_argument("--json", action="store_true", help="print the full report as JSON")
    args = parser.parse_args(argv)
    try:
        report = run_profile(args.profile)
    except contracts.SchemaValidatorUnavailable as exc:
        print(f"SCHEMA_VALIDATOR_UNAVAILABLE: {exc}", file=sys.stderr)
        return 3
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        t = report["totals"]
        print(f"profile={report['profile']} contracts={report['contract_count']} "
              f"mutations={t['mutations']} refused={t['closure_required_refused']} "
              f"wrongly_passed={t['closure_required_wrongly_passed']} "
              f"open_boundaries={t['open_boundaries']} corpus_digest={report['corpus_digest'][:16]}")
    if args.require_all_refused and report["totals"]["closure_required_wrongly_passed"] != 0:
        print("FAIL: closure-required mutation(s) WRONGLY PASSED:", file=sys.stderr)
        for w in report["wrongly_passed"]:
            print(f"  {w['schema_id']} {w['pointer']} {w['family']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
