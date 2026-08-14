"""R-F14 ``reaction.first_touch.v2`` — computed causality; spec vectors T1-T11 + acceptance.

The capability fixture is REAL: a test-RATIFIED copy of the binding registry (the eight F14 rows
flipped ACTIVE in memory only — the repository rows stay BLOCKED, proven below; FPB-0038, whose
PAR-062 ordinal became structural in v2, is repurposed as the TEST transport row for the NEW
``RETEST_TTL_BARS`` binding) sealed via ``build_sealed_bundle`` and accepted through
``transition.require_bundle`` with the Ed25519 pattern from
``tests/contracts/test_sealed_bundle_v2.py``. The BLOCKED posture is proven on the UNMODIFIED
repository registry: no F14 capability can be minted, and the machine's named refusal is
``BLOCKED_ON_RATIFY(parameter_id)``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
import pathlib
import random
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import bindings, e01_interface as e01, transition  # noqa: E402
from triad_origin.canonical import (  # noqa: E402
    INT64_MAX, INT64_MIN, canonical_json, is_sha256_hex, loads_canonical, sha256_hex)
from triad_origin.exact import QuarantineOverflow  # noqa: E402
from triad_origin.structures import common  # noqa: E402
from triad_origin.structures import reaction_v2 as r2  # noqa: E402

OWNER_KID = "k-owner-f14"
OWNER_PK = "cd" * 32
REPOSITORY = "TriadOrigin"
ENVIRONMENT = "OFF"
VALID_FROM = 1_000_000
VALID_TO = 9_000_000
NOW_US = 2_000_000

# Scenario clock (microseconds). T_know=1s; the departure observation lands with elapsed
# EXACTLY 60000 ms (the PAR-167 inclusive boundary).
T_KNOW = 1_000_000
DEP_AVAIL = T_KNOW + 60_000_000


# ---------------------------------------------------------------------------------------------
# Capability fixtures (the C.1/C.3 seam, exercised for real — the F03 pattern)
# ---------------------------------------------------------------------------------------------


def _trust() -> dict:
    return {OWNER_KID: {"key_id": OWNER_KID, "identity": "owner@triad",
                        "role": "AUTHORITY_OWNER", "algorithm": "ed25519",
                        "public_key_hex": OWNER_PK, "revoked": False}}


def _trust_bytes(trust: dict) -> bytes:
    return json.dumps(trust, sort_keys=True).encode("utf-8")


def _bytes_bound_verify(pk: str, msg: bytes, sig_hex: str) -> bool:
    return sig_hex == hashlib.sha512(msg + bytes.fromhex(pk)).hexdigest()


def _standin_sign(msg: bytes) -> dict:
    return {"key_id": OWNER_KID,
            "signature_hex": hashlib.sha512(msg + bytes.fromhex(OWNER_PK)).hexdigest()}


def _signing_bytes_for(bundle) -> bytes:
    return bindings.sealed_bundle_signing_bytes(
        canonical_root_digest=bundle.canonical_root_digest,
        scope=bundle.scope, valid_from=bundle.valid_from, valid_to=bundle.valid_to)


@pytest.fixture(autouse=True)
def _fresh_process_state():
    bindings._reset_trust_registry_pin_for_tests()
    bindings._reset_acceptance_memo_for_tests()
    yield
    bindings._reset_trust_registry_pin_for_tests()
    bindings._reset_acceptance_memo_for_tests()


@pytest.fixture(scope="module")
def real_registry():
    return bindings.load_registry()


# THE PAR-050 TRANSPORT INTERLOCK (the F03 precedent, pinned below): the declared PAR-050
# byte-string ``max(2,ceil(ATR14_ticks*1/10))`` contains ``*``, which the B01C-BIND-04
# wildcard-sentinel law refuses inside an ACTIVE row's resolved fields — so TODAY no capability
# whose ``value`` is the declared rule can be minted end to end; the ratification train must
# additionally land a loader-acceptable declared-value transport. The fixture mints REAL
# capabilities (full build_sealed_bundle + require_bundle path, real Ed25519) with the PAR-050
# row carrying a clearly-labeled sentinel-free TEST transport value, then rebuilds that ONE
# handle to carry the exact declared byte-string (C.1 law: construction of the type is
# unrestricted — acceptance is what is guarded; the machine's own boundary law is proven
# adversarially in TestBoundaryRejections).
TEST_TRANSPORT_VALUE = "TEST-RATIFIED-TRANSPORT max(2,ceil(ATR14_ticks 1/10)) (sentinel-free)"

# The eight F14 registry rows; FPB-0038 (PAR-062, structural in v2) is repurposed as the
# RETEST_TTL_BARS TEST transport row — the real registry row is the ratification train's act.
_F14_TEST_ROWS = {
    "FPB-0025": {"parameter_id": r2.PARAMETER_MIN_DEPARTURE,
                 "declared_value": TEST_TRANSPORT_VALUE},
    "FPB-0038": {"parameter_id": r2.PARAMETER_RETEST_TTL_BARS,
                 "declared_value": r2.DECLARED_RETEST_TTL_BARS},
    "FPB-0074": {"parameter_id": r2.PARAMETER_MIN_DEPART_EVENTS,
                 "declared_value": r2.DECLARED_MIN_DEPART_EVENTS},
    "FPB-0075": {"parameter_id": r2.PARAMETER_MIN_DEPART_TIME_MS,
                 "declared_value": r2.DECLARED_MIN_DEPART_TIME_MS},
    "FPB-0076": {"parameter_id": r2.PARAMETER_CONTACT_PRICE_SOURCE,
                 "declared_value": r2.DECLARED_CONTACT_PRICE_SOURCE},
    "FPB-0089": {},
    "FPB-0093": {},
    "FPB-0097": {},
}


def _ratified_doc() -> dict:
    """The repository registry with the F14 rows flipped ACTIVE — a TEST-only ratified posture."""
    doc = json.loads(pathlib.Path(bindings.DEFAULT_REGISTRY_PATH).read_text(encoding="utf-8"))
    for row in doc["rows"]:
        overrides = _F14_TEST_ROWS.get(row["binding_id"])
        if overrides is None or row["formula_id"] != "F14":
            continue
        row.update({
            "status": "ACTIVE",
            "lifecycle_status": "ACTIVE",
            "cardinality": "EXACTLY_ONE",
            "migration_state": "NOT_APPLICABLE",
            "semantic_slot": f"f14_test_slot_{row['binding_id']}",
            "condition": "TEST-RATIFIED stand-in for the F14 ratification ceremony",
            "activation_scope": "TEST;F14;reaction_v2 vectors only",
            "precedence": "TEST_FIXTURE",
            "consumer": "ORIGIN(F14)",
            "consuming_wiring_ids": "W03",
            "disposition_reason":
                "TEST-only ratified posture; the repository rows stay BLOCKED.",
        })
        row.update(overrides)
        unsigned = {k: v for k, v in row.items() if k != "binding_digest"}
        row["binding_digest"] = sha256_hex(canonical_json(unsigned))
    counts: dict = {}
    for row in doc["rows"]:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    doc["status_counts"] = dict(sorted(counts.items()))
    return doc


@pytest.fixture(scope="module")
def ratified_registry():
    return bindings.BindingRegistry(_ratified_doc())


@pytest.fixture(scope="module")
def minted_caps(ratified_registry):
    """REAL VerifiedCapability handles for all five F14 parameters (real Ed25519)."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey, Ed25519PublicKey)

    bindings._reset_trust_registry_pin_for_tests()
    bindings._reset_acceptance_memo_for_tests()
    try:
        private = Ed25519PrivateKey.generate()
        pub_hex = private.public_key().public_bytes_raw().hex()
        trust = {OWNER_KID: {"key_id": OWNER_KID, "identity": "owner@triad",
                             "role": "AUTHORITY_OWNER", "algorithm": "ed25519",
                             "public_key_hex": pub_hex, "revoked": False}}
        raw = _trust_bytes(trust)
        bindings.pin_trust_registry_digest(sha256_hex(raw))
        unsigned = bindings.build_sealed_bundle(
            ratified_registry, repository=REPOSITORY, environment=ENVIRONMENT,
            valid_from=VALID_FROM, valid_to=VALID_TO,
            trust_registry_digest=sha256_hex(raw), signer_set=[OWNER_KID])
        signing = _signing_bytes_for(unsigned)
        bundle = dataclasses.replace(unsigned, signatures=[
            {"key_id": OWNER_KID, "signature_hex": private.sign(signing).hex()}])

        def ed25519_verify(public_key_hex: str, message: bytes, signature_hex: str) -> bool:
            try:
                key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
                key.verify(bytes.fromhex(signature_hex), message)
                return True
            except Exception:
                return False

        ctx = bindings.VerificationContext(
            trust=trust, trust_registry_bytes=raw, now_us=NOW_US,
            process_scope={"repository": REPOSITORY, "environment": ENVIRONMENT},
            verify_fn=ed25519_verify)
        caps = {}
        for parameter_id in r2.REQUIRED_PARAMETERS:
            cap = transition.require_bundle(bundle, parameter_id, formula_id="F14", ctx=ctx)
            assert type(cap) is bindings.VerifiedCapability
            assert cap.formula_id == "F14"
            assert cap.parameter_id == parameter_id
            caps[parameter_id] = cap
        assert caps[r2.PARAMETER_MIN_DEPARTURE].value == TEST_TRANSPORT_VALUE
        assert caps[r2.PARAMETER_RETEST_TTL_BARS].value == r2.DECLARED_RETEST_TTL_BARS
        return caps
    finally:
        bindings._reset_trust_registry_pin_for_tests()
        bindings._reset_acceptance_memo_for_tests()


@pytest.fixture(scope="module")
def caps(minted_caps):
    """The behavior-vector capabilities: the REAL minted handles, with PAR-050 re-carrying the
    exact declared byte-string (see the transport-interlock note above)."""
    out = dict(minted_caps)
    out[r2.PARAMETER_MIN_DEPARTURE] = dataclasses.replace(
        minted_caps[r2.PARAMETER_MIN_DEPARTURE], value=common.DECLARED_MIN_DEPARTURE)
    return out


@pytest.fixture(scope="module")
def foreign_cap(real_registry):
    """A genuine capability for a DIFFERENT formula (F00/PAR-001) off the repository registry."""
    bindings._reset_trust_registry_pin_for_tests()
    bindings._reset_acceptance_memo_for_tests()
    try:
        trust = _trust()
        raw = _trust_bytes(trust)
        bindings.pin_trust_registry_digest(sha256_hex(raw))
        unsigned = bindings.build_sealed_bundle(
            real_registry, repository=REPOSITORY, environment=ENVIRONMENT,
            valid_from=VALID_FROM, valid_to=VALID_TO,
            trust_registry_digest=sha256_hex(raw), signer_set=[OWNER_KID])
        bundle = dataclasses.replace(
            unsigned, signatures=[_standin_sign(_signing_bytes_for(unsigned))])
        ctx = bindings.VerificationContext(
            trust=trust, trust_registry_bytes=raw, now_us=NOW_US,
            process_scope={"repository": REPOSITORY, "environment": ENVIRONMENT},
            verify_fn=_bytes_bound_verify)
        return transition.require_bundle(bundle, "PAR-001", formula_id="F00", ctx=ctx)
    finally:
        bindings._reset_trust_registry_pin_for_tests()
        bindings._reset_acceptance_memo_for_tests()


# ---------------------------------------------------------------------------------------------
# Observation fixtures (E01-validated — the ONLY lawful construction path) + drivers
# ---------------------------------------------------------------------------------------------


def raw_bar(identity: str, low: int, high: int) -> dict:
    return {
        "bar_identity": identity, "metadata_revision": "r1",
        "open_ticks": low, "high_ticks": high, "low_ticks": low, "close_ticks": high,
        "base_volume": 1, "quote_volume": 1, "trade_count": 1,
    }


def vbar(identity: str, low: int, high: int) -> e01.ValidatedBar:
    return e01.require_valid_bar(raw_bar(identity, low, high))


def obs(caps, state, identity, low, high, avail, atr=20):
    return r2.evaluate(
        caps, vbar(identity, low, high), state,
        observation_availability_us=avail, atr14_ticks=atr)


def registered(structure_id="s1", zone=(100, 105), side=common.LONG, t_know=T_KNOW):
    result = r2.register(
        r2.initial_state(), structure_id=structure_id, zone=list(zone), side=side,
        availability_time_us=t_know)
    return result.state


def departed(caps):
    """ELIGIBLE -> DEPARTED at DEP_AVAIL (distance 2 == dep_ticks with ATR 20; elapsed exactly
    60000 ms; count 1 >= 1)."""
    result = obs(caps, registered(), "dep", 107, 108, DEP_AVAIL)
    assert result.state["structures"]["s1"]["reaction_state"] == r2.DEPARTED
    return result.state


def kinds_and_reasons(events):
    out = []
    for event in events:
        if event.get("event_kind") == "NAMED_ABSTENTION":
            out.append(("NAMED_ABSTENTION", event["reason_code"]))
        else:
            out.append((event["event_kind"], event.get("to_state")))
    return out


def snapshot_roundtrip(state):
    return loads_canonical(canonical_json(state))


# ---------------------------------------------------------------------------------------------
# BLOCKED posture — the repository registry mints nothing; the machine names its refusal
# ---------------------------------------------------------------------------------------------


class TestBlockedPosture:
    def test_repository_registry_cannot_mint_an_f14_capability(self, real_registry):
        trust = _trust()
        raw = _trust_bytes(trust)
        bindings.pin_trust_registry_digest(sha256_hex(raw))
        unsigned = bindings.build_sealed_bundle(
            real_registry, repository=REPOSITORY, environment=ENVIRONMENT,
            valid_from=VALID_FROM, valid_to=VALID_TO,
            trust_registry_digest=sha256_hex(raw), signer_set=[OWNER_KID])
        bundle = dataclasses.replace(
            unsigned, signatures=[_standin_sign(_signing_bytes_for(unsigned))])
        ctx = bindings.VerificationContext(
            trust=trust, trust_registry_bytes=raw, now_us=NOW_US,
            process_scope={"repository": REPOSITORY, "environment": ENVIRONMENT},
            verify_fn=_bytes_bound_verify)
        with pytest.raises(bindings.BlockedBindingIncomplete):
            transition.require_bundle(
                bundle, r2.PARAMETER_MIN_DEPARTURE, formula_id="F14", ctx=ctx)

    def test_no_capability_is_the_named_refusal_blocked_on_ratify(self):
        state = registered()
        with pytest.raises(r2.BlockedOnRatify) as err:
            r2.evaluate({}, vbar("b1", 100, 101), state,
                        observation_availability_us=DEP_AVAIL, atr14_ticks=20)
        assert err.value.parameter_id == r2.PARAMETER_MIN_DEPARTURE
        assert "BLOCKED_ON_RATIFY(PAR-050)" in str(err.value)

    def test_missing_retest_ttl_capability_names_the_new_binding(self, caps):
        partial = {k: v for k, v in caps.items() if k != r2.PARAMETER_RETEST_TTL_BARS}
        state = registered()
        with pytest.raises(r2.BlockedOnRatify) as err:
            r2.evaluate(partial, vbar("b1", 100, 101), state,
                        observation_availability_us=DEP_AVAIL, atr14_ticks=20)
        assert err.value.parameter_id == r2.PARAMETER_RETEST_TTL_BARS

    def test_proposed_ttl_value_exists_only_as_the_declared_transport(self):
        # PROPOSED_MUST_RATIFY discipline: "288" is a declared-string transport in the closed
        # executable table, reachable ONLY through an authenticated capability.
        assert r2.DECLARED_RETEST_TTL_BARS == "288"
        assert r2._DECLARED_EXECUTABLE[r2.PARAMETER_RETEST_TTL_BARS] == {"288": 288}
        assert r2.RETEST_TTL_CLOCK == "FROM_T_KNOW"  # RATIFY_WITH_THIS_REPAIR — hardwired law


# ---------------------------------------------------------------------------------------------
# Boundary rejections (the §C.3 dynamic adversarial gate) + T2
# ---------------------------------------------------------------------------------------------


class TestBoundaryRejections:
    def test_hand_built_dict_caps_rejected_before_any_state_transition(self):
        state = registered()
        frozen = canonical_json(state)
        forged = {
            r2.PARAMETER_MIN_DEPARTURE: common.DECLARED_MIN_DEPARTURE,
            r2.PARAMETER_MIN_DEPART_EVENTS: "1",
            r2.PARAMETER_MIN_DEPART_TIME_MS: "60000",
            r2.PARAMETER_CONTACT_PRICE_SOURCE: r2.DECLARED_CONTACT_PRICE_SOURCE,
            r2.PARAMETER_RETEST_TTL_BARS: "288",
        }
        with pytest.raises(bindings.CapabilityForgeryError):
            r2.evaluate(forged, vbar("b1", 107, 108, ), state,
                        observation_availability_us=DEP_AVAIL, atr14_ticks=20)
        assert canonical_json(state) == frozen  # no state transition happened

    def test_non_mapping_caps_and_fake_objects_rejected(self, caps):
        state = registered()
        with pytest.raises(bindings.CapabilityForgeryError):
            r2.evaluate(7, vbar("b1", 107, 108), state,
                        observation_availability_us=DEP_AVAIL, atr14_ticks=20)

        class FakeCap:
            parameter_id = r2.PARAMETER_MIN_DEPARTURE
            formula_id = "F14"
            value = common.DECLARED_MIN_DEPARTURE

        forged = dict(caps)
        forged[r2.PARAMETER_MIN_DEPARTURE] = FakeCap()
        with pytest.raises(bindings.CapabilityForgeryError):
            r2.evaluate(forged, vbar("b1", 107, 108), state,
                        observation_availability_us=DEP_AVAIL, atr14_ticks=20)

    def test_foreign_formula_capability_rejected(self, caps, foreign_cap):
        forged = dict(caps)
        forged[r2.PARAMETER_MIN_DEPARTURE] = foreign_cap
        with pytest.raises(bindings.CapabilityForgeryError):
            r2.evaluate(forged, vbar("b1", 107, 108), registered(),
                        observation_availability_us=DEP_AVAIL, atr14_ticks=20)

    def test_capability_under_the_wrong_key_rejected(self, caps):
        forged = dict(caps)
        forged[r2.PARAMETER_MIN_DEPARTURE] = caps[r2.PARAMETER_MIN_DEPART_EVENTS]
        with pytest.raises(bindings.CapabilityForgeryError):
            r2.evaluate(forged, vbar("b1", 107, 108), registered(),
                        observation_availability_us=DEP_AVAIL, atr14_ticks=20)

    def test_unknown_parameter_key_rejected(self, caps):
        forged = dict(caps)
        forged["PAR-999"] = caps[r2.PARAMETER_MIN_DEPARTURE]
        with pytest.raises(bindings.CapabilityForgeryError):
            r2.evaluate(forged, vbar("b1", 107, 108), registered(),
                        observation_availability_us=DEP_AVAIL, atr14_ticks=20)

    def test_undeclared_value_on_a_real_handle_refused(self, caps):
        forged = dict(caps)
        forged[r2.PARAMETER_RETEST_TTL_BARS] = dataclasses.replace(
            caps[r2.PARAMETER_RETEST_TTL_BARS], value="289")
        with pytest.raises(common.StructureLawError):
            r2.evaluate(forged, vbar("b1", 107, 108), registered(),
                        observation_availability_us=DEP_AVAIL, atr14_ticks=20)

    def test_raw_mapping_env_is_quarantined(self, caps):
        with pytest.raises(e01.QuarantineInvalidBar):
            r2.evaluate(caps, raw_bar("b1", 107, 108), registered(),
                        observation_availability_us=DEP_AVAIL, atr14_ticks=20)

    def test_validated_bar_subclass_is_quarantined(self, caps):
        class Sneaky(e01.ValidatedBar):
            pass

        bar = vbar("b1", 107, 108)
        sneaky = Sneaky(**{f.name: getattr(bar, f.name) for f in dataclasses.fields(bar)})
        with pytest.raises(e01.QuarantineInvalidBar):
            r2.evaluate(caps, sneaky, registered(),
                        observation_availability_us=DEP_AVAIL, atr14_ticks=20)

    def test_malformed_state_is_refused(self, caps):
        with pytest.raises(common.StructureLawError):
            r2.evaluate(caps, vbar("b1", 107, 108), {"structures": {}},
                        observation_availability_us=DEP_AVAIL, atr14_ticks=20)

    # T2 — the old caller-precomputed eligibility fields DO NOT EXIST on any public surface.
    def test_t2_old_api_fields_do_not_exist(self, caps):
        with pytest.raises(TypeError):
            r2.evaluate(caps, vbar("b1", 107, 108), registered(),
                        observation_availability_us=DEP_AVAIL, atr14_ticks=20,
                        directional_distance_from_near_edge_ticks=5)
        with pytest.raises(TypeError):
            r2.evaluate(caps, vbar("b1", 107, 108), registered(),
                        observation_availability_us=DEP_AVAIL, atr14_ticks=20,
                        depart_event_count=1)
        with pytest.raises(TypeError):
            r2.register(r2.initial_state(), structure_id="s1", zone=[100, 105],
                        side=common.LONG, availability_time_us=0, elapsed_depart_time_ms=60000)

    def test_t2_static_scan_no_entrypoint_can_inject_eligibility_facts(self):
        forbidden = {
            "directional_distance_from_near_edge_ticks", "depart_event_count",
            "elapsed_depart_time_ms", "contact_source", "event_time_us",
            "departure_availability_us", "reaction_state", "observation_count",
        }
        public = [r2.register, r2.evaluate, r2.invalidate, r2.invalidate_on_gap,
                  r2.initial_state, r2.registration_digest, r2.source_reaction_id]
        for fn in public:
            params = set(inspect.signature(fn).parameters)
            assert not (params & forbidden), (fn.__name__, params & forbidden)
        # The v1 fabricatable envelope is GONE from executable code (the module docstring may
        # name it as the retired defect it repairs).
        import ast
        source = pathlib.Path(r2.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        docstring = ast.get_docstring(tree) or ""
        assert "DEPARTURE_CANDIDATE" not in source.replace(docstring, "")


# ---------------------------------------------------------------------------------------------
# T7 — registration conflict law (typed REJECT_CONFLICT; idempotent identical re-registration)
# ---------------------------------------------------------------------------------------------


class TestRegistration:
    def test_registration_emits_the_frozen_digest(self):
        result = r2.register(
            r2.initial_state(), structure_id="s1", zone=[100, 105], side=common.LONG,
            availability_time_us=T_KNOW)
        (event,) = result.events
        assert event["event_kind"] == r2.REACTION_REGISTERED
        expected = sha256_hex(canonical_json({
            "digest_kind": "origin.f14.registration.v2",
            "structure_id": "s1", "z0_ticks": 100, "z1_ticks": 105,
            "side": common.LONG, "availability_time_us": T_KNOW,
        }))
        assert event["registration_digest"] == expected
        assert result.state["structures"]["s1"]["registration_digest"] == expected

    def test_t7_identical_reregistration_is_idempotent(self):
        state = registered()
        result = r2.register(
            state, structure_id="s1", zone=[100, 105], side=common.LONG,
            availability_time_us=T_KNOW)
        assert result.events == ()
        assert canonical_json(result.state) == canonical_json(state)

    @pytest.mark.parametrize("kwargs", [
        {"zone": [100, 106]},                       # different zone bytes
        {"zone": [99, 105]},
        {"side": common.SHORT},                     # frozen registration bytes differ
        {"availability_time_us": T_KNOW + 1},
    ])
    def test_t7_conflicting_reregistration_is_a_typed_reject_conflict(self, kwargs):
        state = registered()
        frozen = canonical_json(state)
        base = {"structure_id": "s1", "zone": [100, 105], "side": common.LONG,
                "availability_time_us": T_KNOW}
        base.update(kwargs)
        with pytest.raises(r2.RejectConflict) as err:
            r2.register(state, **base)
        assert err.value.structure_id == "s1"
        assert is_sha256_hex(err.value.frozen_digest)
        assert is_sha256_hex(err.value.incoming_digest)
        assert err.value.frozen_digest != err.value.incoming_digest
        assert "REJECT_CONFLICT:s1" in str(err.value)
        assert canonical_json(state) == frozen  # the frozen original is untouched

    def test_malformed_registrations_are_typed_refusals(self):
        state = r2.initial_state()
        with pytest.raises(common.StructureLawError):
            r2.register(state, structure_id="s1", zone=[105, 100], side=common.LONG,
                        availability_time_us=0)
        with pytest.raises(common.StructureLawError):
            r2.register(state, structure_id="s1", zone=[100, 105, 110], side=common.LONG,
                        availability_time_us=0)
        with pytest.raises(common.StructureLawError):
            r2.register(state, structure_id="", zone=[100, 105], side=common.LONG,
                        availability_time_us=0)
        with pytest.raises(common.StructureLawError):
            r2.register(state, structure_id="s1", zone=[100, 105], side="UP",
                        availability_time_us=0)


# ---------------------------------------------------------------------------------------------
# T1 — the pre-knowledge trap (STRICT: availability <= T_know is never a contact/input)
# ---------------------------------------------------------------------------------------------


class TestPreKnowledgeTrap:
    def test_t1_contact_before_knowledge_is_not_a_contact(self, caps):
        result = obs(caps, registered(), "early", 100, 105, T_KNOW - 1)
        row = result.state["structures"]["s1"]
        assert row["reaction_state"] == r2.ELIGIBLE
        assert row["observation_count"] == 0  # not a departure input either
        assert kinds_and_reasons(result.events) == [
            ("NAMED_ABSTENTION", r2.PRE_KNOWLEDGE_OBSERVATION)]

    def test_t1_contact_at_exact_knowledge_time_is_not_a_contact(self, caps):
        # Inverts the retired v1 behavior (equality confirmed under v1's >= guard).
        result = obs(caps, registered(), "atknow", 100, 105, T_KNOW)
        row = result.state["structures"]["s1"]
        assert row["reaction_state"] == r2.ELIGIBLE
        assert row["observation_count"] == 0
        assert kinds_and_reasons(result.events) == [
            ("NAMED_ABSTENTION", r2.PRE_KNOWLEDGE_OBSERVATION)]

    def test_t1_pre_knowledge_observation_is_not_a_departure_input(self, caps):
        # Distance/time would satisfy departure, but availability == T_know: excluded.
        result = obs(caps, registered(t_know=DEP_AVAIL), "atknow", 107, 108, DEP_AVAIL)
        assert result.state["structures"]["s1"]["reaction_state"] == r2.ELIGIBLE


# ---------------------------------------------------------------------------------------------
# T3 — departure computed inside; every conjunct at its inclusive boundary
# ---------------------------------------------------------------------------------------------


class TestDeparture:
    def test_t3_exact_dep_ticks_boundary_departs(self, caps):
        # ATR 20 -> dep_ticks = max(2, ceil(20/10)) = 2; low 107 - z1 105 = 2 (inclusive).
        result = obs(caps, registered(), "dep", 107, 108, DEP_AVAIL)
        row = result.state["structures"]["s1"]
        assert row["reaction_state"] == r2.DEPARTED
        assert row["departure_availability_us"] == DEP_AVAIL
        assert kinds_and_reasons(result.events) == [
            (r2.REACTION_STATE_CHANGED, r2.DEPARTED)]

    def test_t3_one_tick_short_does_not_depart(self, caps):
        result = obs(caps, registered(), "near", 106, 108, DEP_AVAIL)
        assert result.state["structures"]["s1"]["reaction_state"] == r2.ELIGIBLE
        assert result.events == ()

    def test_min_depart_time_boundary_is_inclusive_from_t_know(self, caps):
        # elapsed exactly 60000 ms since T_know departs; one microsecond less does not.
        early = obs(caps, registered(), "early", 107, 108, DEP_AVAIL - 1)
        assert early.state["structures"]["s1"]["reaction_state"] == r2.ELIGIBLE
        late = obs(caps, early.state, "ontime", 107, 108, DEP_AVAIL)
        assert late.state["structures"]["s1"]["reaction_state"] == r2.DEPARTED

    def test_no_atr_is_a_named_abstention_and_still_counts_the_observation(self, caps):
        result = obs(caps, registered(), "noatr", 107, 108, DEP_AVAIL, atr=None)
        row = result.state["structures"]["s1"]
        assert row["reaction_state"] == r2.ELIGIBLE
        assert row["observation_count"] == 1  # it IS an eligible observation (ages the TTL)
        assert kinds_and_reasons(result.events) == [("NAMED_ABSTENTION", r2.NO_ATR)]

    def test_no_re_departure_once_departed(self, caps):
        state = departed(caps)
        result = obs(caps, state, "again", 109, 110, DEP_AVAIL + 1_000_000)
        assert result.state["structures"]["s1"]["reaction_state"] == r2.DEPARTED
        assert result.events == ()
        assert result.state["structures"]["s1"]["departure_availability_us"] == DEP_AVAIL


# ---------------------------------------------------------------------------------------------
# T4/T5/T8 — first contact, exactly-once consumption, pre-departure audit facts (GV-012)
# ---------------------------------------------------------------------------------------------


class TestFirstContact:
    def test_t4_exact_zone_edge_contact_is_consumed(self, caps):
        state = departed(caps)
        result = obs(caps, state, "touch", 105, 110, DEP_AVAIL + 1)  # low == z1 exactly
        row = result.state["structures"]["s1"]
        assert row["reaction_state"] == r2.FIRST_TOUCH_CONSUMED
        (event,) = result.events
        assert event["event_kind"] == r2.REACTION_CONFIRMED
        assert event["first_touch_ordinal"] == 1
        assert is_sha256_hex(event["source_reaction_id"])
        assert event["registration_digest"] == row["registration_digest"]

    def test_strictly_outside_edge_is_not_a_contact(self, caps):
        state = departed(caps)
        result = obs(caps, state, "miss", 106, 110, DEP_AVAIL + 1)
        assert result.state["structures"]["s1"]["reaction_state"] == r2.DEPARTED
        assert result.events == ()

    def test_gv012_t5_second_identical_touch_no_second_candidate(self, caps):
        state = departed(caps)
        first = obs(caps, state, "touch1", 105, 110, DEP_AVAIL + 1)
        second = obs(caps, first.state, "touch2", 105, 110, DEP_AVAIL + 2)
        assert second.state["structures"]["s1"]["reaction_state"] == r2.FIRST_TOUCH_CONSUMED
        assert kinds_and_reasons(second.events) == [
            ("NAMED_ABSTENTION", r2.DUPLICATE_CONTACT_IGNORED)]
        confirms = [e for e in first.events + second.events
                    if e.get("event_kind") == r2.REACTION_CONFIRMED]
        assert len(confirms) == 1

    def test_t5_consumption_exactly_once_under_replay(self, caps):
        def full_run():
            state = departed(caps)
            events = []
            for ident, avail in (("touch1", DEP_AVAIL + 1), ("touch2", DEP_AVAIL + 2)):
                result = obs(caps, state, ident, 105, 110, avail)
                state = result.state
                events.extend(result.events)
            return canonical_json(state), kinds_and_reasons(events)

        assert full_run() == full_run()
        _, kinds = full_run()
        assert kinds.count((r2.REACTION_CONFIRMED, r2.FIRST_TOUCH_CONSUMED)) == 1

    def test_t8_pre_departure_touch_is_audit_only(self, caps):
        state = registered()
        touch = obs(caps, state, "pretouch", 103, 104, T_KNOW + 1)
        row = touch.state["structures"]["s1"]
        assert row["reaction_state"] == r2.ELIGIBLE
        assert kinds_and_reasons(touch.events) == [
            ("NAMED_ABSTENTION", r2.PRE_DEPARTURE_TOUCH)]
        # First retest is defined strictly after departure: the zone still departs + consumes.
        dep = obs(caps, touch.state, "dep", 107, 108, DEP_AVAIL)
        contact = obs(caps, dep.state, "touch", 105, 110, DEP_AVAIL + 1)
        assert contact.state["structures"]["s1"]["reaction_state"] == r2.FIRST_TOUCH_CONSUMED

    def test_source_reaction_id_is_the_frozen_b06r_digest(self, caps):
        state = departed(caps)
        result = obs(caps, state, "touch", 105, 110, DEP_AVAIL + 1)
        (event,) = result.events
        expected = sha256_hex(canonical_json({
            "digest_kind": "origin.f14.reaction.v2",
            "registration_digest": event["registration_digest"],
            "contact_availability_us": DEP_AVAIL + 1,
            "observed_low_ticks": 105, "observed_high_ticks": 110,
        }))
        assert event["source_reaction_id"] == expected


# ---------------------------------------------------------------------------------------------
# T9 — strict availability inequalities: formation != departure != contact
# ---------------------------------------------------------------------------------------------


class TestStrictOrder:
    def test_t9_departing_availability_can_never_be_the_contact(self, caps):
        state = departed(caps)  # T_depart == DEP_AVAIL
        # A sibling observation at the SAME availability instant intersects — not a contact.
        same = obs(caps, state, "same-instant", 105, 110, DEP_AVAIL)
        assert same.state["structures"]["s1"]["reaction_state"] == r2.DEPARTED
        later = obs(caps, same.state, "later", 105, 110, DEP_AVAIL + 1)
        row = later.state["structures"]["s1"]
        assert row["reaction_state"] == r2.FIRST_TOUCH_CONSUMED
        (event,) = later.events
        assert (event["contact_availability_us"]
                > event["departure_availability_us"]
                > event["knowledge_time_us"])

    def test_t9_formation_event_is_never_departure_or_contact(self, caps):
        # The registration instant itself (avail == T_know) is excluded by T1; the departure
        # instant is excluded from contact by the strict > above — assert the whole chain.
        state = registered()
        at_know = obs(caps, state, "atknow", 107, 108, T_KNOW)
        assert at_know.state["structures"]["s1"]["reaction_state"] == r2.ELIGIBLE
        dep = obs(caps, at_know.state, "dep", 107, 108, DEP_AVAIL)
        contact = obs(caps, dep.state, "touch", 105, 110, DEP_AVAIL + 1)
        (event,) = contact.events
        assert event["knowledge_time_us"] == T_KNOW
        assert event["departure_availability_us"] == DEP_AVAIL
        assert event["contact_availability_us"] == DEP_AVAIL + 1


# ---------------------------------------------------------------------------------------------
# T6 — RETEST TTL: inclusive equality expires; expiry beats contact on the same event
# ---------------------------------------------------------------------------------------------


def _age_to(caps, state, count_from, count_to, base_avail):
    """Feed non-intersecting, non-departing filler observations (low 109 high 110 on a DEPARTED
    zone; they neither contact nor re-depart — the only event a filler may produce is the TTL
    expiry itself once age reaches the bound)."""
    for i in range(count_from, count_to):
        result = obs(caps, state, f"fill{i}", 109, 110, base_avail + i)
        state = result.state
        assert not any(e.get("event_kind") == r2.REACTION_CONFIRMED for e in result.events)
    return state


class TestRetestTtl:
    def test_t6_ttl_equality_expires_and_contact_on_the_same_event_loses(self, caps):
        state = departed(caps)  # count 1
        state = _age_to(caps, state, 2, 288, DEP_AVAIL)  # counts 2..287
        assert state["structures"]["s1"]["observation_count"] == 287
        # The 288th eligible observation intersects: age == RETEST_TTL_BARS — EXPIRED wins.
        result = obs(caps, state, "contact-at-ttl", 105, 110, DEP_AVAIL + 288)
        row = result.state["structures"]["s1"]
        assert row["reaction_state"] == r2.EXPIRED
        assert kinds_and_reasons(result.events) == [
            (r2.REACTION_STATE_CHANGED, r2.EXPIRED),
            ("NAMED_ABSTENTION", r2.EXPIRY_OVER_CONTACT),
        ]
        assert not any(e.get("event_kind") == r2.REACTION_CONFIRMED for e in result.events)

    def test_contact_one_bar_inside_the_ttl_window_consumes(self, caps):
        state = departed(caps)
        state = _age_to(caps, state, 2, 287, DEP_AVAIL)  # counts 2..286
        result = obs(caps, state, "contact-286", 105, 110, DEP_AVAIL + 287)  # count 287 < 288
        assert result.state["structures"]["s1"]["reaction_state"] == r2.FIRST_TOUCH_CONSUMED

    def test_ttl_expires_from_eligible_too(self, caps):
        state = registered()
        for i in range(1, 288):  # sub-departure-distance fillers: distance 1 < dep_ticks 2
            result = obs(caps, state, f"f{i}", 106, 106, T_KNOW + i)
            state = result.state
        assert state["structures"]["s1"]["reaction_state"] == r2.ELIGIBLE
        result = obs(caps, state, "f288", 106, 106, T_KNOW + 288)
        assert result.state["structures"]["s1"]["reaction_state"] == r2.EXPIRED

    def test_expired_is_terminal_for_later_contacts(self, caps):
        state = departed(caps)
        state = _age_to(caps, state, 2, 289, DEP_AVAIL)  # count 288 expires on the 288th filler
        assert state["structures"]["s1"]["reaction_state"] == r2.EXPIRED
        result = obs(caps, state, "late", 105, 110, DEP_AVAIL + 400)
        assert result.state["structures"]["s1"]["reaction_state"] == r2.EXPIRED
        assert result.events == ()


# ---------------------------------------------------------------------------------------------
# INVALIDATED — structure revision / GAP; precedence over everything; terminal is final
# ---------------------------------------------------------------------------------------------


class TestInvalidation:
    def test_invalidate_from_eligible_and_departed(self, caps):
        for state in (registered(), departed(caps)):
            result = r2.invalidate(
                state, structure_id="s1", trigger_id="rev-1", reason="structure revision")
            row = result.state["structures"]["s1"]
            assert row["reaction_state"] == r2.INVALIDATED
            (event,) = result.events
            assert event["to_state"] == r2.INVALIDATED
            assert event["reason"] == "structure revision"

    def test_invalidate_unknown_structure_is_a_typed_refusal(self):
        with pytest.raises(common.StructureLawError):
            r2.invalidate(r2.initial_state(), structure_id="ghost", trigger_id="rev-1",
                          reason="structure revision")

    def test_invalidate_on_terminal_is_a_no_op(self, caps):
        state = departed(caps)
        consumed = obs(caps, state, "touch", 105, 110, DEP_AVAIL + 1).state
        result = r2.invalidate(
            consumed, structure_id="s1", trigger_id="rev-1", reason="late revision")
        assert result.events == ()
        assert result.state["structures"]["s1"]["reaction_state"] == r2.FIRST_TOUCH_CONSUMED

    def test_gap_invalidates_every_non_terminal_structure(self, caps):
        state = registered()
        state = r2.register(state, structure_id="s2", zone=[200, 205], side=common.SHORT,
                            availability_time_us=T_KNOW).state
        consumed = obs(caps, state, "dep", 107, 108, DEP_AVAIL)
        consumed = obs(caps, consumed.state, "touch", 105, 110, DEP_AVAIL + 1)
        assert consumed.state["structures"]["s1"]["reaction_state"] == r2.FIRST_TOUCH_CONSUMED
        result = r2.invalidate_on_gap(
            consumed.state, trigger_id="gap-1", reason="quarantined bar (GAP)")
        assert result.state["structures"]["s1"]["reaction_state"] == r2.FIRST_TOUCH_CONSUMED
        assert result.state["structures"]["s2"]["reaction_state"] == r2.INVALIDATED
        (event,) = result.events
        assert event["structure_id"] == "s2"

    def test_invalidated_ignores_later_contacts(self, caps):
        state = r2.invalidate(
            departed(caps), structure_id="s1", trigger_id="rev-1", reason="revision").state
        result = obs(caps, state, "touch", 105, 110, DEP_AVAIL + 1)
        assert result.state["structures"]["s1"]["reaction_state"] == r2.INVALIDATED
        assert result.events == ()


# ---------------------------------------------------------------------------------------------
# T10 — supply-side mirror (near/far edges swap under full reflection)
# ---------------------------------------------------------------------------------------------


class TestMirror:
    def test_t10_full_reflection_produces_the_mirrored_lifecycle(self, caps):
        steps = [  # (identity, low, high, avail, atr)
            ("pre", 90, 104, T_KNOW - 1, 20),          # pre-knowledge (audit)
            ("touch0", 103, 104, T_KNOW + 1, 20),      # pre-departure touch (audit)
            ("noatr", 107, 108, T_KNOW + 2, None),     # NO_ATR abstention
            ("dep", 107, 108, DEP_AVAIL, 20),          # departs
            ("miss", 106, 110, DEP_AVAIL + 1, 20),     # not a contact (low 106 > z1 105)
            ("touch", 105, 110, DEP_AVAIL + 2, 20),    # consumed at the exact edge
            ("dup", 105, 110, DEP_AVAIL + 3, 20),      # duplicate ignored
        ]

        def run(side):
            if side == common.LONG:
                state = registered(zone=(100, 105), side=common.LONG)
            else:
                state = registered(zone=(-105, -100), side=common.SHORT)
            seen_states, seen_events = [], []
            for ident, low, high, avail, atr in steps:
                if side == common.SHORT:
                    low, high = -high, -low
                result = obs(caps, state, ident, low, high, avail, atr=atr)
                state = result.state
                seen_states.append(state["structures"]["s1"]["reaction_state"])
                seen_events.extend(result.events)
            return seen_states, seen_events

        long_states, long_events = run(common.LONG)
        short_states, short_events = run(common.SHORT)
        assert long_states == short_states
        assert kinds_and_reasons(long_events) == kinds_and_reasons(short_events)
        long_confirm = [e for e in long_events if e["event_kind"] == r2.REACTION_CONFIRMED][0]
        short_confirm = [e for e in short_events if e["event_kind"] == r2.REACTION_CONFIRMED][0]
        assert short_confirm["observed_low_ticks"] == -long_confirm["observed_high_ticks"]
        assert short_confirm["observed_high_ticks"] == -long_confirm["observed_low_ticks"]
        assert short_confirm["side"] == common.opposite(long_confirm["side"])
        assert (short_confirm["contact_availability_us"]
                == long_confirm["contact_availability_us"])


# ---------------------------------------------------------------------------------------------
# T11 — ordering law + restart/prefix/replay parity
# ---------------------------------------------------------------------------------------------


class TestOrderingAndRestart:
    def test_availability_regression_is_a_typed_refusal(self, caps):
        state = obs(caps, registered(), "b1", 106, 106, T_KNOW + 10).state
        with pytest.raises(common.StructureLawError):
            obs(caps, state, "b2", 106, 106, T_KNOW + 9)

    def test_exact_retransmission_is_an_idempotent_no_op(self, caps):
        first = obs(caps, registered(), "b1", 106, 106, T_KNOW + 10)
        again = obs(caps, first.state, "b1", 106, 106, T_KNOW + 10)
        assert again.events == ()
        assert canonical_json(again.state) == canonical_json(first.state)

    def test_retransmission_with_a_different_availability_is_refused(self, caps):
        state = obs(caps, registered(), "b1", 106, 106, T_KNOW + 10).state
        with pytest.raises(common.StructureLawError):
            obs(caps, state, "b1", 106, 106, T_KNOW + 11)

    def test_t11_restart_parity_at_every_prefix(self, caps):
        steps = [
            ("touch0", 103, 104, T_KNOW + 1, 20),
            ("noatr", 107, 108, T_KNOW + 2, None),
            ("dep", 107, 108, DEP_AVAIL, 20),
            ("miss", 106, 110, DEP_AVAIL + 1, 20),
            ("touch", 105, 110, DEP_AVAIL + 2, 20),
            ("dup", 105, 110, DEP_AVAIL + 3, 20),
        ]

        def fold(state, stream):
            events = []
            for ident, low, high, avail, atr in stream:
                result = obs(caps, state, ident, low, high, avail, atr=atr)
                state = result.state
                events.extend(result.events)
            return state, events

        full_state, full_events = fold(registered(), steps)
        for cut in range(len(steps) + 1):
            prefix_state, prefix_events = fold(registered(), steps[:cut])
            resumed = snapshot_roundtrip(prefix_state)  # restart = canonical round-trip
            resumed_state, resumed_events = fold(resumed, steps[cut:])
            assert canonical_json(resumed_state) == canonical_json(full_state)
            assert prefix_events + resumed_events == full_events


# ---------------------------------------------------------------------------------------------
# §1.2 — int64 wire-width boundary vectors (largest transient differences stay lawful)
# ---------------------------------------------------------------------------------------------


class TestInt64Boundaries:
    def test_out_of_range_zone_is_quarantined(self):
        with pytest.raises(QuarantineOverflow) as err:
            r2.register(r2.initial_state(), structure_id="s1",
                        zone=[100, INT64_MAX + 1], side=common.LONG, availability_time_us=0)
        record = err.value.record()
        assert record["reason_code"] == "QUARANTINE_OVERFLOW"
        assert record["formula_id"] == "F14"
        assert "value_digest" in record and record["value_digest"]

    def test_out_of_range_observation_availability_is_quarantined(self, caps):
        with pytest.raises(QuarantineOverflow):
            r2.evaluate(caps, vbar("b1", 106, 106), registered(),
                        observation_availability_us=INT64_MAX + 1, atr14_ticks=20)

    def test_largest_transient_difference_is_lawful_and_departs(self, caps):
        # The formula's largest-product/difference boundary (§1.2): distance and elapsed are
        # transient comparison arithmetic near 2**64 — lawfully unbounded, no quarantine; every
        # persisted field stays int64.
        state = r2.register(
            r2.initial_state(), structure_id="wide", zone=[INT64_MIN, INT64_MIN + 1],
            side=common.LONG, availability_time_us=INT64_MIN).state
        result = r2.evaluate(
            caps, vbar("b1", INT64_MAX, INT64_MAX), state,
            observation_availability_us=INT64_MAX, atr14_ticks=20)
        row = result.state["structures"]["wide"]
        assert row["reaction_state"] == r2.DEPARTED  # distance == 2**64 - 2 >= dep_ticks
        assert row["departure_availability_us"] == INT64_MAX
        canonical_json(result.state)  # every persisted integer survives the canonical guard


# ---------------------------------------------------------------------------------------------
# ACCEPTANCE property — consumed contact > T_depart > T_know, always (seeded generator)
# ---------------------------------------------------------------------------------------------


class TestConsumptionProperty:
    def test_property_consumed_contact_strictly_after_departure_after_knowledge(self, caps):
        rng = random.Random(0)
        for trial in range(60):
            t_know = rng.randrange(0, 5_000_000)
            state = registered(t_know=t_know)
            avail = t_know - rng.randrange(0, 3)
            confirms = []
            for i in range(24):
                avail += rng.randrange(0, 40_000_000)
                low = rng.randrange(95, 112)
                high = low + rng.randrange(0, 6)
                atr = None if rng.random() < 0.1 else 20
                try:
                    result = obs(caps, state, f"t{trial}b{i}", low, high, avail, atr=atr)
                except common.StructureLawError:
                    continue  # ordering refusals are lawful outcomes of the generator
                state = result.state
                confirms.extend(
                    e for e in result.events if e.get("event_kind") == r2.REACTION_CONFIRMED)
            assert len(confirms) <= 1  # consumption at most once, ever
            for event in confirms:
                assert (event["contact_availability_us"]
                        > event["departure_availability_us"]
                        > event["knowledge_time_us"])


# ---------------------------------------------------------------------------------------------
# B06R exact-digest adoption surface — the canonicalizations are FROZEN here
# ---------------------------------------------------------------------------------------------


class TestB06RDigestFreeze:
    # Literal pins: a byte change to either canonicalization breaks these constants loudly.
    FROZEN_REGISTRATION = (
        "registration", "s1", 100, 105, common.LONG, 1_000_000)

    def test_registration_digest_canonicalization_is_frozen(self):
        digest = r2.registration_digest(
            structure_id="s1", z0_ticks=100, z1_ticks=105, side=common.LONG,
            availability_time_us=1_000_000)
        expected = sha256_hex(canonical_json({
            "digest_kind": "origin.f14.registration.v2",
            "structure_id": "s1", "z0_ticks": 100, "z1_ticks": 105,
            "side": "LONG", "availability_time_us": 1_000_000,
        }))
        assert digest == expected
        assert r2.REGISTRATION_DIGEST_KIND == "origin.f14.registration.v2"
        assert r2.REACTION_DIGEST_KIND == "origin.f14.reaction.v2"

    def test_confirmed_event_carries_both_b06r_identities(self, caps):
        state = departed(caps)
        result = obs(caps, state, "touch", 105, 110, DEP_AVAIL + 1)
        (event,) = result.events
        assert event["registration_digest"] == r2.registration_digest(
            structure_id="s1", z0_ticks=100, z1_ticks=105, side=common.LONG,
            availability_time_us=T_KNOW)
        assert event["source_reaction_id"] == r2.source_reaction_id(
            registration_digest_hex=event["registration_digest"],
            contact_availability_us=DEP_AVAIL + 1,
            observed_low_ticks=105, observed_high_ticks=110)
