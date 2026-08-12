"""R-F09 ``break.bar_close.v2`` battery — first-terminal lifecycle (Formula Repair §2).

Every spec test-vector row T1–T10 exists here, plus the availability/TTL/revision/GAP
mechanisms, the §1.2 wire-width boundaries, the C.3 typed-boundary adversarial drills, the
restart/prefix parity law, and the ACCEPTANCE property test (random tapes: per level,
count(terminal breaks) <= 1; no BOS/CHOCH label in output while the F08 refusal stands).

Capabilities are minted through the REAL sealed-bundle v2 acceptance path
(:func:`triad_origin.transition.require_bundle`) with a fixture Ed25519 keypair — the
``tests/contracts/test_sealed_bundle_v2.py`` pattern. The real registry's F09 rows are BLOCKED
(unmigrated), so the fixture bundle carries F09 rows edited ACTIVE — and one test proves the
UNEDITED registry refuses to mint any F09 capability at all (the honest dark posture).
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import json
import pathlib
import random
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import bindings, exact, transition  # noqa: E402
from triad_origin.canonical import canonical_json, sha256_hex  # noqa: E402
from triad_origin.e01_interface import (  # noqa: E402
    QuarantineInvalidBar,
    require_valid_bar,
)
from triad_origin.structures import break_v2, common  # noqa: E402
from triad_origin.structures.break_v2 import (  # noqa: E402
    BarObservation,
    EnvelopeRejected,
    LevelRegistration,
    LevelRevision,
    RefuseConfig,
    evaluate,
    initial_state,
    run_break_v2,
)

OWNER_KID = "k-owner-f09"
REPOSITORY = "TriadOrigin"
ENVIRONMENT = "OFF"
VALID_FROM = 1_000_000
VALID_TO = 9_000_000
NOW_US = 2_000_000

BASE_US = 1_000_000          # the default level availability instant T_L
BUCKET_US = 60_000_000       # formation-timeframe bucket length
LATENESS_US = 2_000_000      # allowed lateness (PAR-025-shaped fixture value)

RULE = common.DECLARED_BOS_CLOSE_BUFFER


# --- capability forge (real Ed25519 through the real acceptance path) -----------------------------


class _Forge:
    def __init__(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey, Ed25519PublicKey)

        self._private = Ed25519PrivateKey.generate()
        pub_hex = self._private.public_key().public_bytes_raw().hex()
        self.trust = {OWNER_KID: {
            "key_id": OWNER_KID, "identity": "owner@triad", "role": "AUTHORITY_OWNER",
            "algorithm": "ed25519", "public_key_hex": pub_hex, "revoked": False}}
        self.trust_bytes = json.dumps(self.trust, sort_keys=True).encode("utf-8")
        self.trust_digest = sha256_hex(self.trust_bytes)

        def _verify(public_key_hex: str, message: bytes, signature_hex: str) -> bool:
            try:
                key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
                key.verify(bytes.fromhex(signature_hex), message)
                return True
            except Exception:
                return False

        self.ctx = bindings.VerificationContext(
            trust=self.trust, trust_registry_bytes=self.trust_bytes, now_us=NOW_US,
            process_scope={"repository": REPOSITORY, "environment": ENVIRONMENT},
            verify_fn=_verify)
        self.registry = bindings.load_registry()
        self._base_rows = self.registry.rows()
        self._base_coverage = bindings.derive_formula_coverage(self.registry)

    @staticmethod
    def _resign_row(row: dict) -> dict:
        unsigned = {k: v for k, v in row.items() if k != "binding_digest"}
        row["binding_digest"] = sha256_hex(canonical_json(unsigned))
        return row

    def _sign(self, unsigned):
        signing = bindings.sealed_bundle_signing_bytes(
            canonical_root_digest=unsigned.canonical_root_digest, scope=unsigned.scope,
            valid_from=unsigned.valid_from, valid_to=unsigned.valid_to)
        return dataclasses.replace(unsigned, signatures=[
            {"key_id": OWNER_KID, "signature_hex": self._private.sign(signing).hex()}])

    def fixture_bundle(self, buffer_value, ttl_value):
        """A signed fixture bundle whose two F09 rows are edited ACTIVE (fixture surgery)."""
        rows = [dict(r) for r in self._base_rows]
        for row in rows:
            if row["binding_id"] == "FPB-0018":
                row["status"] = "ACTIVE"
                row["declared_value"] = buffer_value
                self._resign_row(row)
            elif row["binding_id"] == "FPB-0092":
                row["status"] = "ACTIVE"
                row["parameter_id"] = break_v2.PARAM_LEVEL_TTL
                row["parameter_name"] = break_v2.PARAM_LEVEL_TTL
                row["semantic_slot"] = "FIXTURE:F09.level_ttl_bars"
                row["declared_value"] = ttl_value
                self._resign_row(row)
        coverage = dict(self._base_coverage)
        coverage["F09"] = "ACTIVE"
        root = bindings.canonical_rows_digest(rows)
        unsigned = bindings.SealedParameterBundle(
            schema_version=bindings.SEALED_SCHEMA_VERSION,
            scope={"repository": REPOSITORY, "environment": ENVIRONMENT},
            rows=rows,
            canonical_root_digest=root,
            trust_registry_digest=self.trust_digest,
            signer_set=[OWNER_KID],
            signatures=[],
            valid_from=VALID_FROM,
            valid_to=VALID_TO,
            formula_coverage=coverage,
            row_preimage_digests=sorted(sha256_hex(canonical_json(r)) for r in rows),
        )
        return self._sign(unsigned)

    def genuine_bundle(self):
        """The UNEDITED registry, signed — F09 stays BLOCKED (the honest dark posture)."""
        unsigned = bindings.build_sealed_bundle(
            self.registry, repository=REPOSITORY, environment=ENVIRONMENT,
            valid_from=VALID_FROM, valid_to=VALID_TO,
            trust_registry_digest=self.trust_digest, signer_set=[OWNER_KID])
        return self._sign(unsigned)

    def mint(self, buffer_value, ttl_value=500, *, include_ttl=True):
        """Mint the F09 caps mapping through the REAL require_bundle acceptance.

        SENTINEL COLLISION (upstream, recorded as an open issue): the C.1 acceptance treats any
        ``declared_value`` containing ``"*"`` as an unresolved sentinel (``bindings._is_sentinel``),
        so an ACTIVE row carrying the literal PAR-043 rational rule
        ``max(1,ceil(ATR14_ticks*1/20))`` can never mint through acceptance today. Rule-face
        capabilities are therefore minted with a placeholder tick value through the REAL
        acceptance path and the verified handle's ``value`` is then swapped to the rule string
        (``dataclasses.replace`` — construction is UNRESTRICTED by the C.1 law; acceptance is
        what is guarded, and it ran in full). Every non-``*`` value mints verbatim.
        """
        rule_overlay = isinstance(buffer_value, str) and "*" in buffer_value
        mintable = 1 if rule_overlay else buffer_value
        bundle = self.fixture_bundle(mintable, ttl_value)
        buffer_cap = transition.require_bundle(
            bundle, break_v2.PARAM_BREAK_BUFFER, formula_id="F09", ctx=self.ctx)
        if rule_overlay:
            buffer_cap = dataclasses.replace(buffer_cap, value=buffer_value)
        caps = {break_v2.PARAM_BREAK_BUFFER: buffer_cap}
        if include_ttl:
            caps[break_v2.PARAM_LEVEL_TTL] = transition.require_bundle(
                bundle, break_v2.PARAM_LEVEL_TTL, formula_id="F09", ctx=self.ctx)
        return caps

    def mint_f00(self):
        """A genuine F00 capability (an ACTIVE formula in the real registry)."""
        return transition.require_bundle(
            self.genuine_bundle(), "PAR-001", formula_id="F00", ctx=self.ctx)


@pytest.fixture(scope="module")
def forge():
    bindings._reset_trust_registry_pin_for_tests()
    bindings._reset_acceptance_memo_for_tests()
    forge = _Forge()
    bindings.pin_trust_registry_digest(forge.trust_digest)
    yield forge
    bindings._reset_trust_registry_pin_for_tests()
    bindings._reset_acceptance_memo_for_tests()


@pytest.fixture(scope="module")
def caps(forge):
    """The workhorse caps: the declared PAR-043 rule + a FIXTURE-ratified TTL of 500 bars.

    500 is FIXTURE data minted through the fixture bundle — the module under test carries no
    executable 500 (asserted by ``test_proposed_ttl_value_is_never_hardcoded_as_active``).
    """
    return forge.mint(RULE, 500)


@pytest.fixture(scope="module")
def caps_ttl2(forge):
    return forge.mint(RULE, 2)


@pytest.fixture(scope="module")
def caps_no_ttl(forge):
    return forge.mint(RULE, 500, include_ttl=False)


@pytest.fixture(scope="module")
def caps_ttl_unratified(forge):
    return forge.mint(RULE, common.NOT_RATIFIED)


@pytest.fixture(scope="module")
def caps_b1(forge):
    return forge.mint(1, 500)


# --- envelope helpers ------------------------------------------------------------------------


def vbar(identity, close, *, open_=None, high=None, low=None):
    open_ = close if open_ is None else open_
    body_high = max(open_, close)
    body_low = min(open_, close)
    return require_valid_bar({
        "bar_identity": identity,
        "metadata_revision": "rev-1",
        "open_ticks": open_,
        "high_ticks": body_high if high is None else high,
        "low_ticks": body_low if low is None else low,
        "close_ticks": close,
        "base_volume": 1,
        "quote_volume": 1,
        "trade_count": 1,
    })


def bar(eid, close, *, ordinal, atr=20, open_=None, high=None, low=None,
        bucket_start=None, availability=None, seq=None):
    bucket = BASE_US + ordinal * BUCKET_US if bucket_start is None else bucket_start
    avail = bucket + BUCKET_US + LATENESS_US if availability is None else availability
    return BarObservation(
        bar=vbar(f"bar:{eid}", close, open_=open_, high=high, low=low),
        bucket_start_us=bucket,
        availability_time_us=avail,
        source_sequence=100 + ordinal if seq is None else seq,
        bar_ordinal=ordinal,
        atr14_ticks=atr,
        source_event_id=eid,
    )


def lvl(eid, level_id, ticks, direction=common.LONG, *, avail=BASE_US, formation=0,
        swing="SW1", revision=0):
    return LevelRegistration(
        level_id=level_id,
        level_ticks=ticks,
        direction=direction,
        availability_time_us=avail,
        formation_bar_ordinal=formation,
        defining_swing_id=swing,
        swing_revision=revision,
        source_event_id=eid,
    )


def revision(eid, swing, new_revision):
    return LevelRevision(
        defining_swing_id=swing, new_revision=new_revision, source_event_id=eid)


def kinds(events, kind):
    return [e for e in events if e.get("event_kind") == kind]


def breaks(events):
    return kinds(events, break_v2.BREAK_OCCURRENCE)


def abstentions(events):
    return kinds(events, "NAMED_ABSTENTION")


def run(caps_map, inputs, initial=None):
    return run_break_v2(caps_map, inputs, initial=initial)


# =================================================================================================
# The C.3 boundary — typed rejections BEFORE any state transition (the mandated adversarial drills)
# =================================================================================================


class TestBoundary:
    def test_hand_built_dict_int_str_in_place_of_a_capability_are_rejected(self, caps):
        state = initial_state()
        snapshot = copy.deepcopy(state)
        for forged in ({"value": RULE}, 5, RULE):
            with pytest.raises(bindings.CapabilityForgeryError):
                evaluate({break_v2.PARAM_BREAK_BUFFER: forged}, bar("c1", 1001, ordinal=0), state)
        assert state == snapshot  # rejected BEFORE any state transition

    def test_hand_built_dict_env_is_rejected_before_any_transition(self, caps):
        state = initial_state()
        snapshot = copy.deepcopy(state)
        with pytest.raises(EnvelopeRejected):
            evaluate(caps, {"kind": "BAR", "payload": {"close_ticks": 1001}}, state)
        with pytest.raises(EnvelopeRejected):
            evaluate(caps, 1001, state)
        assert state == snapshot

    def test_subclassed_envelope_and_capability_are_rejected_exact_type_law(self, caps):
        class WidenedBar(BarObservation):
            pass

        good = bar("c1", 1001, ordinal=0)
        widened = WidenedBar(
            bar=good.bar, bucket_start_us=good.bucket_start_us,
            availability_time_us=good.availability_time_us,
            source_sequence=good.source_sequence, bar_ordinal=good.bar_ordinal,
            atr14_ticks=good.atr14_ticks, source_event_id=good.source_event_id)
        with pytest.raises(EnvelopeRejected):
            evaluate(caps, widened, initial_state())

        class WidenedCap(bindings.VerifiedCapability):
            pass

        real = caps[break_v2.PARAM_BREAK_BUFFER]
        forged = WidenedCap(
            parameter_id=real.parameter_id, formula_id=real.formula_id, value=real.value,
            source_bundle_digest=real.source_bundle_digest,
            signed_root_digest=real.signed_root_digest, repository=real.repository,
            environment=real.environment, valid_from=real.valid_from, valid_to=real.valid_to,
            signer_key_ids=real.signer_key_ids, _row_canonical=b"{}")
        with pytest.raises(bindings.CapabilityForgeryError):
            evaluate({break_v2.PARAM_BREAK_BUFFER: forged}, good, initial_state())

    def test_bar_observation_wrapping_a_raw_dict_bar_is_rejected(self, caps):
        duck = BarObservation(
            bar={"close_ticks": 1001}, bucket_start_us=BASE_US,
            availability_time_us=BASE_US + BUCKET_US, source_sequence=1, bar_ordinal=0,
            atr14_ticks=20, source_event_id="c1")
        with pytest.raises(EnvelopeRejected):
            evaluate(caps, duck, initial_state())

    def test_wrong_formula_capability_is_refused(self, forge, caps):
        f00 = forge.mint_f00()
        assert f00.formula_id == "F00"
        with pytest.raises(bindings.CapabilityForgeryError):
            evaluate({break_v2.PARAM_BREAK_BUFFER: f00},
                     bar("c1", 1001, ordinal=0), initial_state())

    def test_capability_under_the_wrong_key_is_refused(self, caps):
        ttl_cap = caps[break_v2.PARAM_LEVEL_TTL]
        with pytest.raises(bindings.CapabilityForgeryError):
            evaluate({break_v2.PARAM_BREAK_BUFFER: ttl_cap},
                     bar("c1", 1001, ordinal=0), initial_state())

    def test_missing_required_buffer_capability_fails_closed(self, caps):
        with pytest.raises(transition.MissingParameterError):
            evaluate({}, bar("c1", 1001, ordinal=0), initial_state())

    def test_unknown_capability_key_is_refused(self, caps):
        widened = dict(caps)
        widened["PAR-999"] = caps[break_v2.PARAM_BREAK_BUFFER]
        with pytest.raises(RefuseConfig):
            evaluate(widened, bar("c1", 1001, ordinal=0), initial_state())

    def test_state_must_be_the_exact_v2_state_object(self, caps):
        with pytest.raises(EnvelopeRejected):
            evaluate(caps, bar("c1", 1001, ordinal=0), 42)
        with pytest.raises(EnvelopeRejected):
            evaluate(caps, bar("c1", 1001, ordinal=0), {"levels": {}})

    def test_bar_availability_must_follow_its_bucket_start(self, caps):
        with pytest.raises(EnvelopeRejected):
            evaluate(caps, bar("c1", 1001, ordinal=0, availability=BASE_US), initial_state())

    def test_real_registry_refuses_to_mint_any_f09_capability(self, forge):
        # The honest dark posture: F09's registry rows are BLOCKED (unmigrated), so the
        # production mint path cannot produce an F09 capability at all.
        with pytest.raises(bindings.BlockedBindingIncomplete) as excinfo:
            transition.require_bundle(
                forge.genuine_bundle(), break_v2.PARAM_BREAK_BUFFER,
                formula_id="F09", ctx=forge.ctx)
        assert excinfo.value.formula_id == "F09"


# =================================================================================================
# Spec vectors T1–T10
# =================================================================================================


class TestSpecVectors:
    def test_t1_close_at_level_plus_buffer_breaks_up_inclusive(self, caps):
        # ATR 20 => b = 1 (GV-008 numerics); C = L + b exactly.
        result = run(caps, [lvl("l1", "LV1", 1000), bar("c1", 1001, ordinal=0)])
        (occurrence,) = breaks(result.events)
        assert occurrence["direction"] == break_v2.UP_BREAK
        assert occurrence["terminal"] == break_v2.BROKEN_UP
        assert occurrence["level_ticks"] == 1000
        assert occurrence["buffer_ticks"] == 1
        assert occurrence["close_ticks"] == 1001
        assert occurrence["first_breach_source"] == "c1"
        assert occurrence["acceptance_source"] == "c1"
        assert occurrence["formula_version"] == "break.bar_close.v2"
        # ATR 40 => b = 2; equality at L + b passes (inclusive).
        at_edge = run(caps, [lvl("l1", "LV1", 1000), bar("c1", 1002, ordinal=0, atr=40)])
        assert len(breaks(at_edge.events)) == 1

    def test_t2_one_tick_short_emits_nothing(self, caps):
        result = run(caps, [lvl("l1", "LV1", 1000), bar("c1", 1000, ordinal=0)])
        assert breaks(result.events) == []
        atr40 = run(caps, [lvl("l1", "LV1", 1000), bar("c1", 1001, ordinal=0, atr=40)])
        assert breaks(atr40.events) == []

    def test_t3_wick_through_with_close_short_emits_nothing(self, caps):
        # H_j >= L + b while C_j < L + b: close-based only — the wick emits nothing.
        result = run(caps, [
            lvl("l1", "LV1", 1000),
            bar("c1", 1000, ordinal=0, open_=998, high=1005, low=995),
        ])
        assert breaks(result.events) == []
        assert kinds(result.events, break_v2.DUPLICATE_BREAK_IGNORED) == []
        # Mirror wick: low pierces L - b, close holds above.
        mirrored = run(caps, [
            lvl("l1", "LV1", 1000, direction=common.SHORT),
            bar("c1", 1000, ordinal=0, open_=1002, high=1005, low=995),
        ])
        assert breaks(mirrored.events) == []

    def test_t4_first_terminal_break_then_later_qualifying_close_is_duplicate_ignored(self, caps):
        result = run(caps, [
            lvl("l1", "LV1", 1000),
            bar("c1", 1001, ordinal=0),   # accepted up break at j
            bar("c2", 1000, ordinal=1),
            bar("c3", 1000, ordinal=2),
            bar("c4", 995, ordinal=3),    # qualifying DOWN close at j+3
        ])
        occurred = breaks(result.events)
        assert len(occurred) == 1
        assert occurred[0]["terminal"] == break_v2.BROKEN_UP
        (ignored,) = kinds(result.events, break_v2.DUPLICATE_BREAK_IGNORED)
        assert ignored["level_id"] == "LV1"
        assert ignored["ignored_direction"] == break_v2.DOWN_BREAK
        assert ignored["terminal"] == break_v2.BROKEN_UP
        assert ignored["source_event_id"] == "c4"
        record = result.final_state["levels"]["LV1"]
        assert record["lifecycle"] == break_v2.LIFECYCLE_RETIRED
        assert record["break"]["direction"] == break_v2.UP_BREAK

    def test_t5_late_finalizing_older_bucket_bar_is_ineligible(self, caps):
        # The level avails at T; an OLDER-bucket bar (bucket_start < T) finalizes late (its
        # availability is after T). Eligibility is on bucket_start, so it may not test L.
        t_level = BASE_US + 90_000_000
        inputs = [
            lvl("l1", "LV1", 1000, avail=t_level),
            bar("c1", 1005, ordinal=0, low=995, high=1006,
                bucket_start=BASE_US + BUCKET_US,          # < T_L
                availability=t_level + 32_000_000),        # finalizes AFTER T_L
            bar("c2", 1005, ordinal=1,
                bucket_start=t_level + 30_000_000,         # >= T_L
                availability=t_level + 92_000_000 + LATENESS_US),
        ]
        result = run(caps, inputs)
        occurred = breaks(result.events)
        assert len(occurred) == 1
        assert occurred[0]["first_breach_source"] == "c2"  # never the ineligible bar
        (audit,) = kinds(result.events, break_v2.INELIGIBLE_PRE_AVAILABILITY)
        assert audit["level_id"] == "LV1"
        assert audit["source_event_id"] == "c1"
        assert audit["bar_bucket_start_us"] == BASE_US + BUCKET_US
        assert audit["level_availability_time_us"] == t_level

    def test_t5b_ineligible_bar_not_intersecting_the_level_carries_no_audit(self, caps):
        t_level = BASE_US + 90_000_000
        result = run(caps, [
            lvl("l1", "LV1", 1000, avail=t_level),
            bar("c1", 1015, ordinal=0, open_=1012, low=1010, high=1020,
                bucket_start=BASE_US + BUCKET_US,
                availability=t_level + 32_000_000),
        ])
        assert breaks(result.events) == []
        assert kinds(result.events, break_v2.INELIGIBLE_PRE_AVAILABILITY) == []

    def test_t5c_eligibility_boundary_is_inclusive_at_the_availability_instant(self, caps):
        t_level = BASE_US + 90_000_000
        result = run(caps, [
            lvl("l1", "LV1", 1000, avail=t_level),
            bar("c1", 1001, ordinal=0, bucket_start=t_level,
                availability=t_level + BUCKET_US + LATENESS_US),
        ])
        assert len(breaks(result.events)) == 1  # bucket_start == T_L is eligible (>=)

    def test_t6_b1_close_at_the_level_is_neither_direction(self, caps_b1):
        result = run(caps_b1, [lvl("l1", "LV1", 1000), bar("c1", 1000, ordinal=0)])
        assert breaks(result.events) == []
        assert kinds(result.events, break_v2.DUPLICATE_BREAK_IGNORED) == []

    def test_t7_b0_config_is_refuse_config(self, forge):
        caps_b0 = forge.mint(0, 500)
        state = initial_state()
        snapshot = copy.deepcopy(state)
        with pytest.raises(RefuseConfig) as excinfo:
            evaluate(caps_b0, bar("c1", 1001, ordinal=0), state)
        assert excinfo.value.reason == "REFUSE_CONFIG"
        assert state == snapshot  # refused before any transition
        caps_neg = forge.mint(-3, 500)
        with pytest.raises(RefuseConfig):
            evaluate(caps_neg, lvl("l1", "LV1", 1000), state)

    def test_t8_defining_swing_revision_after_break_invalidates_and_voids(self, caps):
        head = run(caps, [
            lvl("l1", "LV1", 1000, swing="SW1", revision=0),
            bar("c1", 1001, ordinal=0),
        ])
        (occurrence,) = breaks(head.events)
        tail = run(caps, [revision("r1", "SW1", 1)], initial=head.final_state)
        (invalidated,) = kinds(tail.events, break_v2.LEVEL_INVALIDATED)
        assert invalidated["reason"] == break_v2.INVALIDATION_DEFINING_SWING_REVISED
        assert invalidated["prior_lifecycle"] == break_v2.LIFECYCLE_RETIRED
        assert invalidated["registered_revision"] == 0
        assert invalidated["revised_to"] == 1
        (void,) = kinds(tail.events, break_v2.BREAK_VOIDED_BY_REVISION)
        assert void["level_id"] == "LV1"
        assert void["voided_direction"] == break_v2.UP_BREAK
        assert void["first_breach_source"] == "c1"
        # Append-only: the original occurrence is never rewritten — the full stream still
        # carries it byte-identically, followed by the void.
        full = list(head.events) + list(tail.events)
        assert canonical_json(occurrence) in [canonical_json(e) for e in full]
        record = tail.final_state["levels"]["LV1"]
        assert record["lifecycle"] == break_v2.LIFECYCLE_INVALIDATED
        assert record["break_voided"] is True
        assert record["break"]["direction"] == break_v2.UP_BREAK  # the record itself survives

    def test_t8b_revision_of_an_armed_level_invalidates_without_a_void_event(self, caps):
        result = run(caps, [
            lvl("l1", "LV1", 1000, swing="SW1", revision=0),
            revision("r1", "SW1", 2),
            bar("c1", 1001, ordinal=0),
        ])
        (invalidated,) = kinds(result.events, break_v2.LEVEL_INVALIDATED)
        assert invalidated["prior_lifecycle"] == break_v2.LIFECYCLE_ARMED
        assert kinds(result.events, break_v2.BREAK_VOIDED_BY_REVISION) == []
        assert breaks(result.events) == []  # an invalidated level is never tested again

    def test_t8c_stale_or_unknown_revision_is_a_deterministic_noop(self, caps):
        head = run(caps, [lvl("l1", "LV1", 1000, swing="SW1", revision=3)])
        stale = run(caps, [revision("r1", "SW1", 3)], initial=head.final_state)
        assert stale.events == ()
        assert stale.final_state == head.final_state
        unknown = run(caps, [revision("r2", "SW-UNKNOWN", 9)], initial=head.final_state)
        assert unknown.events == ()
        assert unknown.final_state == head.final_state

    def test_t9_f08_uninitialized_generic_break_only_no_bos_choch_label(self, caps):
        result = run(caps, [
            lvl("l1", "LV1", 1000, direction=common.LONG),
            lvl("l2", "LV2", 2000, direction=common.SHORT),
            bar("c1", 1001, ordinal=0),
            bar("c2", 1998, ordinal=1),
        ])
        occurred = breaks(result.events)
        assert len(occurred) == 2
        for occurrence in occurred:
            assert occurrence["classification"] == break_v2.CLASSIFICATION_GENERIC
        dumped = json.dumps(list(result.events))
        assert "BOS" not in dumped and "CHOCH" not in dumped

    def test_t10_full_mirror_suite(self, forge):
        # The exact algebraic mirror C -> -C, up <-> down, high <-> low over a composite tape
        # exercising break, wick, eligibility, TTL expiry, duplicate and revision paths.
        caps2 = forge.mint(RULE, 2)
        t_late = BASE_US + 999_000_000_000  # LV_LATE never becomes eligible on this tape

        def tape(sign):
            def m(x):
                return sign * x

            def mbar(eid, close, *, ordinal, open_=None, high=None, low=None, **kw):
                o = close if open_ is None else open_
                hi = max(o, close) if high is None else high
                lo = min(o, close) if low is None else low
                if sign < 0:
                    return bar(eid, m(close), ordinal=ordinal,
                               open_=m(o), high=m(lo), low=m(hi), **kw)
                return bar(eid, close, ordinal=ordinal, open_=o, high=hi, low=lo, **kw)

            def mdir(direction):
                return direction if sign > 0 else common.opposite(direction)

            return [
                lvl("l1", "LV_A", m(1000), direction=mdir(common.LONG),
                    swing="SWA", revision=0, formation=0),
                lvl("l2", "LV_B", m(900), direction=mdir(common.SHORT),
                    swing="SWB", revision=0, formation=0),
                lvl("l3", "LV_LATE", m(1000), direction=mdir(common.LONG),
                    swing="SWC", revision=0, formation=0, avail=t_late),
                # LV_EXP first becomes ELIGIBLE at c4's bucket, where its age (3) already
                # exceeds TTL 2 — and c4's close would qualify: EXPIRED must dominate.
                lvl("l4", "LV_EXP", m(1200), direction=mdir(common.LONG),
                    swing="SWD", revision=0, formation=0, avail=BASE_US + 3 * BUCKET_US),
                # c1: wick through LV_A + b, close short — AND LV_B breaks up (900 + 1).
                mbar("c1", 1000, ordinal=0, open_=998, high=1005, low=995),
                mbar("c2", 1001, ordinal=1),  # LV_A breaks up; LV_B duplicate up
                mbar("c3", 899, ordinal=2),   # LV_A + LV_B duplicate down
                mbar("c4", 1001, ordinal=3),  # LV_EXP expires (age 3 > 2, beats the predicate)
                revision("r1", "SWB", 1),     # invalidates LV_B + voids its break
            ]

        straight = run(forge.mint(RULE, 2), tape(1))
        mirrored = run(caps2, tape(-1))
        assert len(straight.events) == len(mirrored.events) > 0
        flip = {break_v2.UP_BREAK: break_v2.DOWN_BREAK,
                break_v2.DOWN_BREAK: break_v2.UP_BREAK}
        flip_terminal = {break_v2.BROKEN_UP: break_v2.BROKEN_DOWN,
                         break_v2.BROKEN_DOWN: break_v2.BROKEN_UP}
        for s, r in zip(straight.events, mirrored.events):
            assert r["event_kind"] == s["event_kind"]
            if s["event_kind"] == break_v2.BREAK_OCCURRENCE:
                assert r["direction"] == flip[s["direction"]]
                assert r["terminal"] == flip_terminal[s["terminal"]]
                assert r["level_direction"] == common.opposite(s["level_direction"])
                assert r["level_ticks"] == -s["level_ticks"]
                assert r["close_ticks"] == -s["close_ticks"]
                assert r["buffer_ticks"] == s["buffer_ticks"]
                assert r["level_id"] == s["level_id"]
            elif s["event_kind"] == break_v2.DUPLICATE_BREAK_IGNORED:
                assert r["ignored_direction"] == flip[s["ignored_direction"]]
                assert r["terminal"] == flip_terminal[s["terminal"]]
                assert r["close_ticks"] == -s["close_ticks"]
                assert r["level_id"] == s["level_id"]
            elif s["event_kind"] == break_v2.INELIGIBLE_PRE_AVAILABILITY:
                assert r["level_ticks"] == -s["level_ticks"]
                assert r["level_id"] == s["level_id"]
            elif s["event_kind"] == break_v2.BREAK_VOIDED_BY_REVISION:
                assert r["voided_direction"] == flip[s["voided_direction"]]
                assert {k: v for k, v in r.items() if k != "voided_direction"} == {
                    k: v for k, v in s.items() if k != "voided_direction"}
            else:
                assert r == s  # expiry / gap-invalidations / abstentions are sign-free
        kinds_seen = {e["event_kind"] for e in straight.events}
        for expected in (break_v2.BREAK_OCCURRENCE, break_v2.DUPLICATE_BREAK_IGNORED,
                         break_v2.INELIGIBLE_PRE_AVAILABILITY, break_v2.LEVEL_EXPIRED,
                         break_v2.LEVEL_INVALIDATED, break_v2.BREAK_VOIDED_BY_REVISION):
            assert expected in kinds_seen


# =================================================================================================
# The first-terminal lifecycle, TTL, GAP, ordering, honest-null
# =================================================================================================


class TestLifecycle:
    def test_first_terminal_law_terminates_both_directions(self, caps):
        result = run(caps, [
            lvl("l1", "LV1", 1000),
            bar("c1", 1001, ordinal=0),
            bar("c2", 1005, ordinal=1),  # same direction again
            bar("c3", 990, ordinal=2),   # opposite direction
        ])
        assert len(breaks(result.events)) == 1
        ignored = kinds(result.events, break_v2.DUPLICATE_BREAK_IGNORED)
        assert [e["ignored_direction"] for e in ignored] == [
            break_v2.UP_BREAK, break_v2.DOWN_BREAK]

    def test_one_close_breaking_two_levels_emits_in_level_id_order(self, caps):
        result = run(caps, [
            lvl("l1", "LV_B", 1000),
            lvl("l2", "LV_A", 990),
            lvl("l3", "LV_C", 995),
            bar("c1", 1001, ordinal=0),
        ])
        occurred = breaks(result.events)
        assert [o["level_id"] for o in occurred] == ["LV_A", "LV_B", "LV_C"]
        assert all(o["direction"] == break_v2.UP_BREAK for o in occurred)

    def test_ttl_expiry_boundary_age_strictly_greater_than_ttl(self, caps_ttl2):
        neutral = [bar(f"c{i}", 1000, ordinal=i) for i in range(3)]  # ages 1, 2 — held
        held = run(caps_ttl2, [lvl("l1", "LV1", 1000, formation=0)] + neutral[1:3])
        assert kinds(held.events, break_v2.LEVEL_EXPIRED) == []
        expired = run(caps_ttl2, [bar("c3", 1000, ordinal=3)], initial=held.final_state)
        (event,) = kinds(expired.events, break_v2.LEVEL_EXPIRED)
        assert event["age_bars"] == 3
        assert event["level_ttl_bars"] == 2
        assert expired.final_state["levels"]["LV1"]["lifecycle"] == break_v2.LIFECYCLE_EXPIRED
        # An expired level never breaks and never carries a duplicate audit.
        after = run(caps_ttl2, [bar("c4", 1010, ordinal=4)], initial=expired.final_state)
        assert breaks(after.events) == []
        assert kinds(after.events, break_v2.DUPLICATE_BREAK_IGNORED) == []

    def test_precedence_expired_beats_terminal_on_the_same_event(self, caps_ttl2):
        result = run(caps_ttl2, [
            lvl("l1", "LV1", 1000, formation=0),
            bar("c1", 1000, ordinal=1),
            bar("c2", 1000, ordinal=2),
            bar("c3", 1005, ordinal=3),  # age 3 > 2 AND the close qualifies: EXPIRED wins
        ])
        assert breaks(result.events) == []
        assert len(kinds(result.events, break_v2.LEVEL_EXPIRED)) == 1

    def test_gap_invalidates_armed_levels_and_beats_a_qualifying_close(self, caps):
        result = run(caps, [
            lvl("l1", "LV1", 1000),
            bar("c1", 1000, ordinal=0),
            bar("c2", 1005, ordinal=2),  # ordinal hole (1 missing) + qualifying close
        ])
        assert breaks(result.events) == []
        (invalidated,) = kinds(result.events, break_v2.LEVEL_INVALIDATED)
        assert invalidated["reason"] == break_v2.INVALIDATION_BAR_STREAM_GAP
        assert result.final_state["levels"]["LV1"]["lifecycle"] == (
            break_v2.LIFECYCLE_INVALIDATED)

    def test_precedence_invalidated_beats_expired_on_the_same_event(self, caps_ttl2):
        result = run(caps_ttl2, [
            lvl("l1", "LV1", 1000, formation=0),
            bar("c1", 1000, ordinal=1),
            bar("c2", 1005, ordinal=5),  # gap AND age 5 > 2 AND qualifying close
        ])
        assert breaks(result.events) == []
        assert kinds(result.events, break_v2.LEVEL_EXPIRED) == []
        (invalidated,) = kinds(result.events, break_v2.LEVEL_INVALIDATED)
        assert invalidated["reason"] == break_v2.INVALIDATION_BAR_STREAM_GAP

    def test_gap_never_voids_a_recorded_break(self, caps):
        result = run(caps, [
            lvl("l1", "LV1", 1000, swing="SW1"),
            lvl("l2", "LV2", 1001, swing="SW2"),
            bar("c1", 1001, ordinal=0),   # LV1 breaks; LV2 (close == L) stays armed
            bar("c2", 1000, ordinal=2),   # gap
        ])
        assert len(breaks(result.events)) == 1
        assert kinds(result.events, break_v2.BREAK_VOIDED_BY_REVISION) == []
        levels = result.final_state["levels"]
        assert levels["LV1"]["lifecycle"] == break_v2.LIFECYCLE_RETIRED
        assert levels["LV1"]["break_voided"] is False
        assert levels["LV2"]["lifecycle"] == break_v2.LIFECYCLE_INVALIDATED

    def test_quarantined_bar_is_a_gap(self, caps):
        # §1.1: an invalid bar is quarantined at the E01 boundary (no atom possible — it can
        # never become a ValidatedBar); the resulting ordinal hole surfaces as a GAP here.
        with pytest.raises(QuarantineInvalidBar):
            require_valid_bar({
                "bar_identity": "bad", "metadata_revision": "rev-1",
                "open_ticks": 1000, "high_ticks": 990, "low_ticks": 995,
                "close_ticks": 1000, "base_volume": 1, "quote_volume": 1, "trade_count": 1})
        result = run(caps, [
            lvl("l1", "LV1", 1000),
            bar("c1", 1000, ordinal=0),
            # ordinal 1 was the quarantined bar — never delivered
            bar("c2", 1005, ordinal=2),
        ])
        assert breaks(result.events) == []
        (invalidated,) = kinds(result.events, break_v2.LEVEL_INVALIDATED)
        assert invalidated["reason"] == break_v2.INVALIDATION_BAR_STREAM_GAP

    def test_order_key_and_ordinal_regressions_are_refused(self, caps):
        head = run(caps, [lvl("l1", "LV1", 1000), bar("c1", 1000, ordinal=1)])
        with pytest.raises(common.StructureLawError):
            run(caps, [bar("c2", 1000, ordinal=2, bucket_start=BASE_US,
                           availability=BASE_US + 1, seq=0)], initial=head.final_state)
        b1 = bar("c1", 1000, ordinal=1)
        with pytest.raises(common.StructureLawError):
            run(caps, [bar("c2", 1000, ordinal=2,
                           availability=b1.availability_time_us,
                           seq=b1.source_sequence)], initial=head.final_state)
        with pytest.raises(common.StructureLawError):
            # A fresh (availability, sequence) key but a non-advancing ordinal.
            run(caps, [bar("c2", 1000, ordinal=1,
                           availability=b1.availability_time_us + 1_000_000,
                           seq=b1.source_sequence + 7)], initial=head.final_state)

    def test_null_atr_is_a_named_abstention_never_a_zero_buffer(self, caps):
        result = run(caps, [lvl("l1", "LV1", 1000), bar("c1", 2000, ordinal=0, atr=None)])
        assert breaks(result.events) == []
        (event,) = abstentions(result.events)
        assert event["reason_code"] == "F09_NO_ATR"
        assert event["formula"] == "F09"

    def test_null_atr_bar_still_expires_by_age(self, caps_ttl2):
        result = run(caps_ttl2, [
            lvl("l1", "LV1", 1000, formation=0),
            bar("c1", 2000, ordinal=3, atr=None),
        ])
        assert breaks(result.events) == []
        assert len(kinds(result.events, break_v2.LEVEL_EXPIRED)) == 1
        (event,) = abstentions(result.events)
        assert event["reason_code"] == "F09_NO_ATR"

    def test_non_positive_atr_is_refused_not_a_buffer(self, caps):
        with pytest.raises(common.StructureLawError):
            run(caps, [lvl("l1", "LV1", 1000), bar("c1", 1001, ordinal=0, atr=0)])

    def test_wrong_rule_string_is_refuse_config(self, forge):
        caps_wrong = forge.mint("max(1,ceil(ATR14_ticks*1/10))", 500)
        with pytest.raises(RefuseConfig):
            evaluate(caps_wrong, bar("c1", 1001, ordinal=0), initial_state())

    def test_registration_is_idempotent_and_a_bare_conflict_refuses(self, caps):
        idempotent = run(caps, [
            lvl("l1", "LV1", 1000),
            lvl("l2", "LV1", 1000),
            bar("c1", 1001, ordinal=0),
        ])
        assert len(breaks(idempotent.events)) == 1
        with pytest.raises(common.StructureLawError):
            run(caps, [lvl("l1", "LV1", 1000), lvl("l2", "LV1", 999)])

    def test_unregistered_levels_emit_nothing(self, caps):
        result = run(caps, [bar("c1", 1001, ordinal=0)])
        assert breaks(result.events) == []

    def test_direct_tick_buffer_face_needs_no_atr(self, forge):
        caps_b3 = forge.mint(3, 500)
        result = run(caps_b3, [
            lvl("l1", "LV1", 1000),
            bar("c1", 1003, ordinal=0, atr=None),
        ])
        (occurrence,) = breaks(result.events)
        assert occurrence["buffer_ticks"] == 3
        assert abstentions(result.events) == []  # the direct face never touches ATR
        short = run(caps_b3, [lvl("l1", "LV1", 1000), bar("c1", 1002, ordinal=0, atr=None)])
        assert breaks(short.events) == []


# =================================================================================================
# LEVEL_TTL_BARS — PROPOSED_MUST_RATIFY: mechanism wired, refusal stands
# =================================================================================================


class TestLevelTtlRefusal:
    def test_absent_ttl_capability_is_a_named_abstention_and_safe_hold(self, caps_no_ttl):
        head = run(caps_no_ttl, [lvl("l1", "LV1", 1000)])
        before = head.final_state
        result = run(caps_no_ttl, [bar("c1", 1005, ordinal=0)], initial=before)
        assert breaks(result.events) == []
        (event,) = abstentions(result.events)
        assert event["reason_code"] == "F09_UNAVAILABLE_LEVEL_TTL_NOT_RATIFIED"
        assert event["formula"] == "F09"
        assert result.final_state == before  # SAFE_HOLD: zero state mutation
        assert result.final_state["last_bar_ordinal"] is None

    def test_not_ratified_sentinel_ttl_is_the_same_refusal(self, caps_ttl_unratified):
        result = run(caps_ttl_unratified, [lvl("l1", "LV1", 1000), bar("c1", 1005, ordinal=0)])
        assert breaks(result.events) == []
        (event,) = abstentions(result.events)
        assert event["reason_code"] == "F09_UNAVAILABLE_LEVEL_TTL_NOT_RATIFIED"

    def test_registration_and_revision_channels_stay_live_under_the_refusal(self, caps_no_ttl):
        result = run(caps_no_ttl, [
            lvl("l1", "LV1", 1000, swing="SW1", revision=0),
            revision("r1", "SW1", 1),
        ])
        (invalidated,) = kinds(result.events, break_v2.LEVEL_INVALIDATED)
        assert invalidated["reason"] == break_v2.INVALIDATION_DEFINING_SWING_REVISED

    def test_malformed_ttl_values_are_refuse_config(self, forge):
        for bad in (0, -5, "garbage"):
            caps_bad = forge.mint(RULE, bad)
            with pytest.raises(RefuseConfig):
                evaluate(caps_bad, bar("c1", 1000, ordinal=0), initial_state())

    def test_proposed_ttl_value_is_never_hardcoded_as_active(self):
        # The spec proposes a value; §0 rule 1 forbids hardcoding it as active. No executable
        # integer constant 500 may exist anywhere in the v2 module (docstrings are strings).
        source = pathlib.Path(break_v2.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and not isinstance(node.value, bool):
                if isinstance(node.value, int):
                    assert node.value != 500, "the proposed LEVEL_TTL_BARS value is hardcoded"


# =================================================================================================
# §1.2 wire width — int64 boundaries (2^63 - 1 passes; one beyond quarantines)
# =================================================================================================


class TestWireWidth:
    def test_level_ticks_int64_edges(self, caps):
        top = 2 ** 63 - 1
        ok = run(caps, [lvl("l1", "LV_MAX", top)])
        assert ok.final_state["levels"]["LV_MAX"]["level_ticks"] == top
        ok_min = run(caps, [lvl("l1", "LV_MIN", -(2 ** 63))])
        assert ok_min.final_state["levels"]["LV_MIN"]["level_ticks"] == -(2 ** 63)
        state = initial_state()
        with pytest.raises(exact.QuarantineOverflow) as excinfo:
            evaluate(caps, lvl("l1", "LV_OVER", 2 ** 63), state)
        assert excinfo.value.formula_id == "F09"
        assert excinfo.value.field == "level_ticks"
        assert state == initial_state()  # quarantined before any transition
        with pytest.raises(exact.QuarantineOverflow):
            evaluate(caps, lvl("l1", "LV_UNDER", -(2 ** 63) - 1), state)

    def test_bar_time_fields_int64_edges(self, caps):
        with pytest.raises(exact.QuarantineOverflow):
            evaluate(caps, bar("c1", 1000, ordinal=0, bucket_start=2 ** 63), initial_state())
        with pytest.raises(exact.QuarantineOverflow):
            evaluate(caps, bar("c1", 1000, ordinal=0, availability=2 ** 63), initial_state())

    def test_direct_buffer_capability_int64_edge(self, forge):
        # The canonical wire itself refuses to CARRY an out-of-int64 declared_value: a bundle
        # with such a row cannot even be assembled (defense in depth below the formula).
        from triad_origin.canonical import CanonicalError

        with pytest.raises(CanonicalError):
            forge.fixture_bundle(2 ** 63, 500)
        # And the formula's own §1.2 boundary guard quarantines the value if a capability
        # PRESENTS it anyway (construction is unrestricted; the guard is per-formula law).
        caps_top = forge.mint(2 ** 63 - 1, 500)
        over = dataclasses.replace(
            caps_top[break_v2.PARAM_BREAK_BUFFER], value=2 ** 63)
        with pytest.raises(exact.QuarantineOverflow) as excinfo:
            evaluate({break_v2.PARAM_BREAK_BUFFER: over,
                      break_v2.PARAM_LEVEL_TTL: caps_top[break_v2.PARAM_LEVEL_TTL]},
                     bar("c1", 1000, ordinal=0), initial_state())
        assert excinfo.value.formula_id == "F09"
        assert excinfo.value.field == "break_buffer_ticks"
        # 2^63 - 1 is the lawful edge: it passes the guard, and nothing can qualify against it.
        result = run(caps_top, [lvl("l1", "LV1", 1000), bar("c1", 1001, ordinal=0)])
        assert breaks(result.events) == []


# =================================================================================================
# Determinism: restart/prefix parity, driver-style dedup, GV-008 numerics
# =================================================================================================


def composite_tape():
    # LV2 sits exactly ON the close path (b = 1 keeps close == L unbroken), so it stays ARMED
    # until its TTL-2 age crosses at ordinal 3.
    return [
        lvl("l1", "LV1", 1000, swing="SW1", formation=0),
        lvl("l2", "LV2", 1001, direction=common.SHORT, swing="SW2", formation=0),
        bar("c1", 1001, ordinal=0),                 # LV1 breaks up; LV2 held
        bar("c2", 1001, ordinal=1),                 # LV1 duplicate probe; LV2 held (age 1)
        revision("r1", "SW1", 1),                   # invalidates LV1 + voids its break
        bar("c3", 1001, ordinal=2),                 # LV1 invalid — no probe; LV2 held (age 2)
        bar("c4", 1001, ordinal=3),                 # LV2 expires (age 3 > 2)
    ]


class TestDeterminism:
    def test_restart_and_prefix_parity_over_the_composite_tape(self, caps_ttl2):
        inputs = composite_tape()
        full = run(caps_ttl2, inputs)
        assert len(breaks(full.events)) == 1
        assert len(kinds(full.events, break_v2.BREAK_VOIDED_BY_REVISION)) == 1
        assert len(kinds(full.events, break_v2.LEVEL_EXPIRED)) == 1
        for cut in range(1, len(inputs)):
            head = run(caps_ttl2, inputs[:cut])
            tail = run(caps_ttl2, inputs[cut:], initial=head.final_state)
            assert list(head.events) + list(tail.events) == list(full.events)
            assert tail.final_state == full.final_state

    def test_restart_after_a_break_never_double_counts_and_audits_the_duplicate(self, caps):
        head = run(caps, [lvl("l1", "LV1", 1000), bar("c1", 1001, ordinal=0)])
        assert len(breaks(head.events)) == 1
        tail = run(caps, [bar("c2", 990, ordinal=1)], initial=head.final_state)
        assert breaks(tail.events) == []
        (ignored,) = kinds(tail.events, break_v2.DUPLICATE_BREAK_IGNORED)
        assert ignored["ignored_direction"] == break_v2.DOWN_BREAK

    def test_exact_duplicate_envelope_is_deduped_by_the_fold(self, caps):
        repeated = bar("c1", 1001, ordinal=0)
        result = run(caps, [lvl("l1", "LV1", 1000), repeated, repeated])
        assert result.duplicate_count == 1
        assert len(breaks(result.events)) == 1

    def test_evaluate_never_mutates_the_callers_state(self, caps):
        state = run(caps, [lvl("l1", "LV1", 1000)]).final_state
        snapshot = copy.deepcopy(state)
        evaluate(caps, bar("c1", 1001, ordinal=0), state)
        assert state == snapshot

    def test_gv008_numerics_hold_for_v2(self, caps):
        # GV-008 (NOT a stale golden): ATR 20 => buffer 1; level 1000: close 1001 breaks,
        # close 1000 does not.
        assert common.evaluate_declared_rational(RULE, 20) == 1
        no_break = run(caps, [lvl("l1", "LV1", 1000), bar("c1", 1000, ordinal=0)])
        assert breaks(no_break.events) == []
        broke = run(caps, [lvl("l1", "LV1", 1000), bar("c1", 1001, ordinal=0)])
        assert len(breaks(broke.events)) == 1


# =================================================================================================
# ACCEPTANCE — property test over random tapes
# =================================================================================================


class TestAcceptanceProperty:
    def test_random_tapes_first_terminal_holds_and_no_label_ever_appears(self, forge):
        caps10 = forge.mint(RULE, 10)
        rng = random.Random(20260812)
        for _tape in range(25):
            inputs = []
            swings = [f"SW{n}" for n in range(3)]
            n_levels = rng.randint(2, 4)
            for n in range(n_levels):
                inputs.append(lvl(
                    f"l{n}", f"LV{n}", 1000 + rng.randint(-6, 6),
                    direction=rng.choice(common.DIRECTIONS),
                    swing=rng.choice(swings), revision=0,
                    formation=rng.randint(0, 2)))
            ordinal = 0
            close = 1000
            for step in range(40):
                ordinal += 1 if rng.random() > 0.05 else 2  # occasional GAP
                close += rng.randint(-8, 8)
                spread = rng.randint(0, 4)
                inputs.append(bar(
                    f"c{step}", close, ordinal=ordinal,
                    open_=close - rng.randint(-2, 2),
                    high=close + spread + 4, low=close - spread - 4,
                    atr=20 if rng.random() > 0.1 else None))
                if rng.random() < 0.08:
                    inputs.append(revision(f"r{step}", rng.choice(swings), rng.randint(1, 5)))
            first = run(caps10, inputs)
            second = run(caps10, inputs)
            assert [canonical_json(e) for e in first.events] == [
                canonical_json(e) for e in second.events]  # deterministic replay
            per_level: dict = {}
            for occurrence in breaks(first.events):
                per_level[occurrence["level_id"]] = per_level.get(
                    occurrence["level_id"], 0) + 1
            assert all(count <= 1 for count in per_level.values()), per_level
            dumped = json.dumps(list(first.events))
            assert "BOS" not in dumped and "CHOCH" not in dumped
