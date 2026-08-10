#!/usr/bin/env python3
"""WP-B01C-06 — generate/verify the content-addressed B01C acceptance profile.

The B01C entry gate (``docs/repair/B01C_ENTRY_GATE.md`` §1) permits ONE separately-identified,
content-addressed ``B01C_ACCEPTANCE_PROFILE.v1`` that lists B01C-specific required evidence and is
referenced as an *immutable preimage* from the unchanged B00R receipt-v3 envelope. It is NOT a
contract, a binding, or a receipt; it mutates no published bytes; it claims no closure.

This tool is the single source of that profile. ``build_profile()`` composes it deterministically —
its safety levers and activation result are read from :mod:`triad_origin.governance` so the profile
can never drift from the estate posture — and ``profile_digest`` content-addresses the whole body.

Modes:

* (default / ``--write``) write ``docs/repair/B01C_ACCEPTANCE_PROFILE.v1.json`` from the generator.
* ``--check`` recompute and assert the on-disk file byte-matches the generator (drift-lock; exit 1 on
  drift). ``--print`` dumps the built profile as canonical JSON.

Honesty guards baked in (each asserted by the test): ``closure_claimed=false``,
``milestone_status=OFFLINE_PREP_UNRECEIPTED``, every owner/provider field ``null``/``UNAVAILABLE``,
``levers == governance.SAFETY_POSTURE``, ``activation_result == governance.ACTIVATION_RESULT``.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import governance  # noqa: E402
from triad_origin.canonical import canonical_json, sha256_hex  # noqa: E402

PROFILE_PATH = ROOT / "docs" / "repair" / "B01C_ACCEPTANCE_PROFILE.v1.json"

# The offline-prep evidence this profile stands over. Each row names its role and honest status;
# an OWNER_GATED / PENDING_B00R_ANCHOR row is never marked built (it cannot be, offline).
_REQUIRED_EVIDENCE = (
    {"id": "B01C-CON-03", "role": "authoritative_validator_required",
     "artifact": "src/triad_origin/contracts.py",
     "status": "OFFLINE_PREP_BUILT",
     "note": "validator-absent lane raises SchemaValidatorUnavailable, never a fallback PASS"},
    {"id": "B01C-CON-03/06", "role": "schema_mutation_corpus",
     "artifact": "tools/run_contract_mutations.py",
     "status": "OFFLINE_PREP_BUILT",
     "note": "every closure-required mutation refused; CON-01/02 open boundaries inventoried"},
    {"id": "B01C-BIND-01/03/06", "role": "binding_bundle_verifier",
     "artifact": "tools/verify_binding_bundle.py",
     "status": "OFFLINE_PREP_BUILT",
     "note": "105-row inventory + six-attack authenticity self-test; UNAVAILABLE_AUTHORITY offline"},
    {"id": "B01C-EVD-01", "role": "historical_receipt_negative_fixtures",
     "artifact": "tests/contracts/test_historical_receipt_negative_fixtures_b01c.py",
     "status": "OFFLINE_PREP_BUILT",
     "note": "B01/B01R/B02 receipts byte-frozen to the invalidation manifest; not a v3 PASS"},
    {"id": "B01C-EVD-01/strict", "role": "receipt_validator_failclosed",
     "artifact": "tests/tools/test_validate_b_receipt_failclosed_b01c.py",
     "status": "OFFLINE_PREP_BUILT",
     "note": "--strict fails closed to UNAVAILABLE_AUTHORITY_ROOT; never OK offline"},
    {"id": "B01C-CON-01", "role": "safety_significant_container_closure",
     "artifact": "tools/gen_contracts.py",
     "status": "OWNER_GATED_NEW_MAJOR",
     "note": "closing a published open container is a new-major + signed supersession, post-anchor"},
    {"id": "B01C-CON-02", "role": "additional_properties_closure",
     "artifact": "contracts/schemas/*",
     "status": "OWNER_GATED_NEW_MAJOR",
     "note": "closing additionalProperties changes published identity; deferred to the anchor train"},
    {"id": "B01C-GOV-01/02", "role": "authenticated_correction_records",
     "artifact": "evidence/corrections/",
     "status": "PENDING_B00R_ANCHOR",
     "note": "forward supersession records require the validated B00R correction ledger"},
    {"id": "B01C-RECEIPT", "role": "b01c_receipt_v3_closure",
     "artifact": "evidence/receipts/B01C.receipt.v3.json",
     "status": "PENDING_B00R_ANCHOR",
     "note": "no B01C receipt exists offline; closure requires the validated B00R_RECEIPT_ANCHOR"},
)


def build_profile() -> dict:
    """Compose the acceptance profile deterministically, with the content-addressed digest last."""
    body = {
        "profile_id": "B01C_ACCEPTANCE_PROFILE.v1",
        "profile_version": "1",
        "milestone": "B01C",
        "milestone_status": "OFFLINE_PREP_UNRECEIPTED",
        "closure_claimed": False,
        "permitted_result": governance.RESULT_PASS,
        "activation_result": governance.ACTIVATION_RESULT,
        "levers": dict(governance.SAFETY_POSTURE),
        "predecessor_hard": "B00R_RECEIPT_ANCHOR",
        # owner/provider inputs are out-of-repo and B00R is unvalidated -> honest absence, never faked
        "owner_gated_inputs": {
            "b00r_receipt_anchor_id": None,
            "b00r_receipt_merge_commit": None,
            "owner_countersignature": "UNAVAILABLE",
            "trust_registry_external_pin": "UNAVAILABLE",
            "provider_ruleset_pin": "UNAVAILABLE",
        },
        "invalidation_manifest": "docs/governance/B00_B07_INVALIDATION_MANIFEST.v1.json",
        "required_evidence": [dict(row) for row in _REQUIRED_EVIDENCE],
        "statement": (
            "Offline-prep acceptance profile for B01C. Lists B01C-specific required evidence and its "
            "honest status. It is an immutable content-addressed preimage, not a contract/binding/"
            "receipt; it mutates no published bytes and claims no closure. B01C becomes authoritative "
            "only from a validated B00R_RECEIPT_ANCHOR."),
    }
    body["profile_digest"] = _digest_of(body)
    return body


def _digest_of(body: dict) -> str:
    unsigned = {k: v for k, v in body.items() if k != "profile_digest"}
    return sha256_hex(canonical_json(unsigned))


def _serialize(profile: dict) -> str:
    return canonical_json(profile).decode("utf-8") + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="assert the on-disk profile byte-matches the generator (exit 1 on drift)")
    parser.add_argument("--print", dest="do_print", action="store_true")
    args = parser.parse_args(argv)

    profile = build_profile()
    serialized = _serialize(profile)

    if args.do_print:
        sys.stdout.write(serialized)
        return 0
    if args.check:
        if not PROFILE_PATH.exists():
            print(f"FAIL: {PROFILE_PATH} missing; run gen_acceptance_profile.py", file=sys.stderr)
            return 1
        on_disk = PROFILE_PATH.read_text(encoding="utf-8")
        if on_disk != serialized:
            print("FAIL: B01C_ACCEPTANCE_PROFILE.v1.json drifted from the generator", file=sys.stderr)
            return 1
        print(f"OK: acceptance profile current (profile_digest={profile['profile_digest'][:16]})")
        return 0

    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(serialized, encoding="utf-8")
    print(f"wrote {PROFILE_PATH} (profile_digest={profile['profile_digest'][:16]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
