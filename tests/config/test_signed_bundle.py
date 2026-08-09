"""B07 signed configuration bundle battery: the thirteen named domains, content-addressed
signature/verification, tamper detection, unknown-contract-reference refusal, honest
pending-vs-materialized reporting per domain."""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import contracts  # noqa: E402
from triad_origin.config import parameters as p  # noqa: E402
from triad_origin.config import signed_bundle as sb  # noqa: E402


@pytest.fixture(scope="module")
def registry() -> p.ParameterRegistry:
    return p.load_registry()


@pytest.fixture(scope="module")
def known_contracts() -> frozenset:
    return frozenset(contracts.known_contracts())


def test_the_thirteen_domains_are_exact_and_ordered_per_the_milestone_text():
    assert sb.DOMAINS == (
        "capsules", "geometry", "lifecycle", "regime_eligibility", "symbols", "staleness",
        "timing", "selected_policy_references", "transport_bindings", "compatibility",
        "treatment_rollback", "secrets_allowlist", "exact_four_plane_manifest",
    )


def test_build_produces_every_domain(registry, known_contracts):
    bundle = sb.build_signed_bundle(registry, known_contracts)
    assert set(bundle["domains"]) == set(sb.DOMAINS)


def test_every_referenced_contract_is_real(known_contracts):
    for cid in {c for ids in sb.DOMAIN_CONTRACTS.values() for c in ids}:
        assert cid in known_contracts


def test_every_domain_anchor_id_resolves_in_the_registry(registry):
    for domain, ids in sb.DOMAIN_ANCHORS.items():
        for pid in ids:
            registry.row(pid)  # raises ParameterUnknownError if the anchor itself is wrong


def test_signature_verifies(registry, known_contracts):
    bundle = sb.build_signed_bundle(registry, known_contracts)
    assert sb.verify_signed_bundle(bundle)


def test_signature_is_deterministic(registry, known_contracts):
    a = sb.build_signed_bundle(registry, known_contracts)
    b = sb.build_signed_bundle(registry, known_contracts)
    assert a["signature"] == b["signature"]


@pytest.mark.parametrize("field", ["parameter_digest", "bundle_version"])
def test_tampering_any_top_level_field_breaks_verification(registry, known_contracts, field):
    bundle = sb.build_signed_bundle(registry, known_contracts)
    tampered = dict(bundle)
    tampered[field] = "TAMPERED"
    assert not sb.verify_signed_bundle(tampered)


def test_tampering_a_domain_breaks_verification(registry, known_contracts):
    bundle = sb.build_signed_bundle(registry, known_contracts)
    tampered = dict(bundle)
    tampered["domains"] = dict(tampered["domains"])
    tampered["domains"]["capsules"] = {"materialized": {}, "pending": {},
                                        "referenced_contracts": ["INJECTED"]}
    assert not sb.verify_signed_bundle(tampered)


def test_not_a_dict_or_missing_signature_fails_verification():
    assert not sb.verify_signed_bundle({"no": "signature field"})
    assert not sb.verify_signed_bundle("not a dict")  # type: ignore[arg-type]


def test_unknown_contract_reference_fails_the_whole_build_closed(registry):
    empty_known = frozenset()
    with pytest.raises(sb.SignedBundleError):
        sb.build_signed_bundle(registry, empty_known)


def test_treatment_rollback_domain_carries_the_comparator_axes(registry, known_contracts):
    bundle = sb.build_signed_bundle(registry, known_contracts)
    domain = bundle["domains"]["treatment_rollback"]
    assert "RC3-PAR-EXP-001" in domain["materialized"]
    assert "RC3-PAR-EXP-002" in domain["materialized"]


def test_capsules_domain_is_honestly_all_pending_today(registry, known_contracts):
    # Every capsules anchor is PROPOSED_RC2_MUST_RATIFY or BLOCKING_OWNER_DECISION today — the
    # bundle must say so, never silently drop or fake-materialize them.
    bundle = sb.build_signed_bundle(registry, known_contracts)
    domain = bundle["domains"]["capsules"]
    assert domain["materialized"] == {}
    assert set(domain["pending"]) == set(sb.DOMAIN_ANCHORS["capsules"])


def test_contract_shaped_domains_carry_no_parameter_anchors_but_name_their_contract(
        registry, known_contracts):
    bundle = sb.build_signed_bundle(registry, known_contracts)
    for domain in ("selected_policy_references", "compatibility", "exact_four_plane_manifest"):
        view = bundle["domains"][domain]
        assert view["materialized"] == {}
        assert view["pending"] == {}
        assert view["referenced_contracts"] == list(sb.DOMAIN_CONTRACTS[domain])


def test_no_domain_is_silently_empty_of_both_anchors_and_contracts():
    for domain in sb.DOMAINS:
        has_anchors = bool(sb.DOMAIN_ANCHORS.get(domain))
        has_contracts = bool(sb.DOMAIN_CONTRACTS.get(domain))
        assert has_anchors or has_contracts, f"domain {domain!r} has no anchor of any kind"
