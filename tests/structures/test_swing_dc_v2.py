"""R-F03 ``swing.dc.bar_extrema.v2`` — the ambiguous-bar law, spec vectors T1-T7 + acceptance.

The capability fixture is REAL: a test-RATIFIED copy of the binding registry (FPB-0011 flipped
ACTIVE in memory only — the repository row stays BLOCKED, proven below) sealed via
``build_sealed_bundle`` and accepted through ``transition.require_bundle`` with the Ed25519
pattern from ``tests/contracts/test_sealed_bundle_v2.py``. The GV-005 boundary posture
(``BLOCKED_UNTIL_PAR-036_RATIFIED``) is proven on the UNMODIFIED repository registry: no F03
capability can be minted, and the machine's named refusal is ``BLOCKED_ON_RATIFY(PAR-036)``.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import pathlib
import random
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import bindings, e01_interface as e01, transition  # noqa: E402
from triad_origin.canonical import canonical_json, sha256_hex  # noqa: E402
from triad_origin.exact import QuarantineOverflow  # noqa: E402
from triad_origin.structures import common  # noqa: E402
from triad_origin.structures import swing_dc_v2 as sdc  # noqa: E402
from triad_origin.structures import typed_level_registry as tlr  # noqa: E402

OWNER_KID = "k-owner-f03"
OWNER_PK = "ab" * 32
REPOSITORY = "TriadOrigin"
ENVIRONMENT = "OFF"
VALID_FROM = 1_000_000
VALID_TO = 9_000_000
NOW_US = 2_000_000


# ---------------------------------------------------------------------------------------------
# Capability fixtures (the C.1/C.3 seam, exercised for real)
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


# THE PAR-036 TRANSPORT INTERLOCK (pinned by TestBlockedOnRatifyAndInterlock below): the
# declared PAR-036 byte-string ``max(5,ceil(ATR14_ticks*1/4))`` contains ``*``, and the
# B01C-BIND-04 wildcard-sentinel law (`bindings._is_sentinel`) refuses ANY ``*`` inside an
# ACTIVE row's resolved fields — at registry load AND at sealed-bundle acceptance. So TODAY no
# capability whose ``value`` is the declared rule can be minted end to end; the ratification
# train (RC3-TASK-G2-BINDING-V2) must land a loader-acceptable declared-value transport. The
# fixture therefore mints a REAL capability (full build_sealed_bundle + require_bundle path,
# real Ed25519) over a clearly-labeled sentinel-free TEST transport value, then rebuilds the
# handle to carry the exact declared byte-string (C.1 law: construction of the type is
# unrestricted — acceptance is what is guarded; the machine's own boundary law is proven
# adversarially in TestBoundaryRejections).
TEST_TRANSPORT_VALUE = "TEST-RATIFIED-TRANSPORT max(5,ceil(ATR14_ticks 1/4)) (sentinel-free)"


def _ratified_doc(declared_value: str = TEST_TRANSPORT_VALUE) -> dict:
    """The repository registry with FPB-0011 flipped ACTIVE — a TEST-only ratified posture."""
    doc = json.loads(pathlib.Path(bindings.DEFAULT_REGISTRY_PATH).read_text(encoding="utf-8"))
    for row in doc["rows"]:
        if row["binding_id"] == "FPB-0011":
            row.update({
                "status": "ACTIVE",
                "lifecycle_status": "ACTIVE",
                "cardinality": "EXACTLY_ONE",
                "migration_state": "NOT_APPLICABLE",
                "declared_value": declared_value,
                "semantic_slot": "dc_reversal_delta_ticks_TEST",
                "condition": "TEST-RATIFIED stand-in for the PAR-036 ratification ceremony",
                "activation_scope": "TEST;F03;swing_dc_v2 vectors only",
                "precedence": "TEST_FIXTURE",
                "consumer": "ORIGIN(F03)",
                "consuming_wiring_ids": "W03",
                "disposition_reason":
                    "TEST-only ratified posture; the repository row stays BLOCKED.",
            })
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
def minted_transport_cap(ratified_registry):
    """A REAL VerifiedCapability for PAR-036/F03, minted with a real Ed25519 keypair."""
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
        cap = transition.require_bundle(
            bundle, sdc.PARAMETER_DC_REVERSAL, formula_id="F03", ctx=ctx)
        assert type(cap) is bindings.VerifiedCapability
        assert cap.formula_id == "F03"
        assert cap.parameter_id == sdc.PARAMETER_DC_REVERSAL
        assert cap.value == TEST_TRANSPORT_VALUE
        return cap
    finally:
        bindings._reset_trust_registry_pin_for_tests()
        bindings._reset_acceptance_memo_for_tests()


@pytest.fixture(scope="module")
def caps(minted_transport_cap):
    """The behavior-vector capability: the REAL minted handle re-carrying the exact declared
    PAR-036 byte-string (see the transport-interlock note above)."""
    cap = dataclasses.replace(minted_transport_cap, value=common.DECLARED_DC_REVERSAL)
    return {sdc.PARAMETER_DC_REVERSAL: cap}


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
# Bar fixtures (E01-validated — the ONLY lawful construction path) + the shared driver
# ---------------------------------------------------------------------------------------------


def raw_bar(identity: str, high: int, low: int) -> dict:
    return {
        "bar_identity": identity, "metadata_revision": "r1",
        "open_ticks": low, "high_ticks": high, "low_ticks": low, "close_ticks": high,
        "base_volume": 1, "quote_volume": 1, "trade_count": 1,
    }


def vbar(identity: str, high: int, low: int) -> e01.ValidatedBar:
    return e01.require_valid_bar(raw_bar(identity, high, low))


def mirror_raw(bar: dict) -> dict:
    out = dict(bar)
    out["open_ticks"] = -bar["open_ticks"]
    out["close_ticks"] = -bar["close_ticks"]
    out["high_ticks"] = -bar["low_ticks"]
    out["low_ticks"] = -bar["high_ticks"]
    return out


_MIRROR_KIND = {tlr.SWING_HIGH: tlr.SWING_LOW, tlr.SWING_LOW: tlr.SWING_HIGH}


def mirror_event(event: dict) -> dict:
    if event.get("event_kind") != tlr.TYPED_LEVEL:
        return dict(event)  # named abstentions are side-free: byte-identical under mirror
    mirrored = dict(event)
    mirrored["kind"] = _MIRROR_KIND[event["kind"]]
    mirrored["direction"] = common.opposite(event["direction"])
    mirrored["level_ticks"] = -event["level_ticks"]
    return mirrored


def run_v2(caps, steps, state=None):
    """Fold the ONE transition implementation over (raw_bar, atr) steps — live == replay."""
    st = state if state is not None else sdc.initial_state()
    events: list = []
    for raw, atr in steps:
        result = sdc.evaluate(caps, e01.require_valid_bar(raw), st, atr14_ticks=atr)
        events.extend(result.events)
        st = result.state
    return st, events


def typed_levels(events):
    return [e for e in events if e.get("event_kind") == tlr.TYPED_LEVEL]


def abstentions(events):
    return [e for e in events if e.get("event_kind") == "NAMED_ABSTENTION"]


def swing(kind, level, delta, origin, confirmed_by):
    return {
        "event_kind": tlr.TYPED_LEVEL, "formula": "F03",
        "semantic_version": sdc.SEMANTIC_VERSION, "kind": kind,
        "direction": common.LONG if kind == tlr.SWING_HIGH else common.SHORT,
        "level_ticks": level, "delta_ticks": delta,
        "origin_bar_identity": origin, "confirmed_by_bar_identity": confirmed_by,
    }


GV005_STEPS = [
    (raw_bar("b0", 1000, 998), 20),
    (raw_bar("b1", 999, 996), 20),   # reversal difference 4 < 5: one tick short, no confirm
    (raw_bar("b2", 999, 995), 20),   # reversal difference 5 == delta 5: equality confirms
]

# Reaches an UP leg lawfully: b1 confirms SWING_LOW(998) -> mode UP, prov_high=(1004, 5, b1).
UP_LEG_STEPS = [
    (raw_bar("b0", 1000, 998), 20),
    (raw_bar("b1", 1004, 999), 20),
]


# ---------------------------------------------------------------------------------------------
# GV-005 + T1/T2 (inclusive boundary, one tick short)
# ---------------------------------------------------------------------------------------------


class TestGoldenAndBoundaries:
    def test_gv005_delta_five_reversal_four_fails_five_passes(self, caps):
        _, events = run_v2(caps, GV005_STEPS)
        assert typed_levels(events) == [
            swing(tlr.SWING_HIGH, 1000, 5, "b0", "b2")]
        _, prefix_events = run_v2(caps, GV005_STEPS[:2])
        assert typed_levels(prefix_events) == []

    def test_t1_t2_leg_phase_exact_boundary_and_one_tick_short(self, caps):
        steps = UP_LEG_STEPS + [
            (raw_bar("b2", 1003, 1000), 20),  # T2: L_j = H_x - delta + 1 -> no confirm
            (raw_bar("b3", 1003, 999), 20),   # T1: L_j = H_x - delta exactly -> confirm
        ]
        _, events = run_v2(caps, steps)
        assert typed_levels(events) == [
            swing(tlr.SWING_LOW, 998, 5, "b0", "b1"),
            swing(tlr.SWING_HIGH, 1004, 5, "b1", "b3"),
        ]

    def test_new_extreme_resets_delta(self, caps):
        # A strictly better extreme under a bigger ATR refreezes delta at the new extreme.
        steps = UP_LEG_STEPS + [
            (raw_bar("b2", 1010, 1006), 40),  # extends only (1004-1006 < 0): delta -> 10
            (raw_bar("b3", 1005, 1000), 40),  # 1010 - 1000 == 10 == delta: equality confirms
        ]
        _, events = run_v2(caps, steps)
        assert typed_levels(events)[-1] == swing(tlr.SWING_HIGH, 1010, 10, "b2", "b3")


# ---------------------------------------------------------------------------------------------
# T3 — the ambiguous-bar law (PAR-036b ABSTAIN_EXTEND_WINS)
# ---------------------------------------------------------------------------------------------


class TestAmbiguousBarLaw:
    def test_t3_extension_wins_abstains_then_next_bar_confirms(self, caps):
        steps = UP_LEG_STEPS + [
            (raw_bar("b2", 1010, 998), 20),   # H_j > H_x AND L_j <= H_x - delta: ambiguous
            (raw_bar("b3", 1006, 1005), 20),  # 1010 - 1005 == 5: the NEW threshold confirms
        ]
        state, events = run_v2(caps, steps)
        facts = [e for e in abstentions(events)
                 if e["reason_code"] == sdc.AMBIGUOUS_BAR_ABSTENTION]
        assert len(facts) == 1
        assert facts[0]["refs"] == {
            "bar_identity": "b2", "rule": sdc.DC_AMBIGUOUS_BAR_RULE,
            "semantic_version": sdc.SEMANTIC_VERSION}
        assert typed_levels(events) == [
            swing(tlr.SWING_LOW, 998, 5, "b0", "b1"),
            swing(tlr.SWING_HIGH, 1010, 5, "b2", "b3"),
        ]
        # Nothing was confirmed BY the ambiguous bar itself.
        assert all(e["confirmed_by_bar_identity"] != "b2" for e in typed_levels(events))
        assert state["mode"] == "DOWN"

    def test_no_confirmation_ever_carries_confirm_bar_equal_extreme_bar(self, caps):
        steps = [
            (raw_bar("b0", 1000, 998), 20),
            (raw_bar("b1", 999, 995), 20),    # confirms SWING_HIGH(1000) -> DOWN leg
            (raw_bar("b2", 1001, 985), 20),   # v1 DEFECT bar: extends low AND reverses low
            (raw_bar("b3", 992, 991), 20),    # the new threshold (985 + 5 <= 992) confirms
        ]
        _, events = run_v2(caps, steps)
        levels = typed_levels(events)
        assert [e["kind"] for e in levels] == [tlr.SWING_HIGH, tlr.SWING_LOW]
        assert levels[1] == swing(tlr.SWING_LOW, 985, 5, "b2", "b3")
        assert all(
            e["origin_bar_identity"] != e["confirmed_by_bar_identity"] for e in levels)
        reasons = [e["reason_code"] for e in abstentions(events)]
        assert reasons == [sdc.AMBIGUOUS_BAR_ABSTENTION]

    def test_defect_contrast_the_retired_v1_confirms_at_its_own_bar(self):
        """The exact input on which retired v1 emits confirm_bar == extreme_bar (the defect)."""
        v1_bars = [
            {"event_id": "b0", "kind": "BAR",
             "payload": {"high_ticks": 1000, "low_ticks": 998, "atr14_ticks": 20}},
            {"event_id": "b1", "kind": "BAR",
             "payload": {"high_ticks": 999, "low_ticks": 995, "atr14_ticks": 20}},
            {"event_id": "b2", "kind": "BAR",
             "payload": {"high_ticks": 1001, "low_ticks": 985, "atr14_ticks": 20}},
        ]
        result = transition.run(
            tlr.DirectionalChangeSwing(), v1_bars,
            {tlr.PARAM_DC_REVERSAL_RULE: common.DECLARED_DC_REVERSAL})
        defective = [e for e in result.events if e.get("event_kind") == tlr.TYPED_LEVEL
                     and e["origin_event_id"] == e["confirmed_by_event_id"]]
        assert defective and defective[0]["origin_event_id"] == "b2"  # v1: frozen defect
        # v2 on the same shape abstains at b2 (proven above) — the repair closes exactly this.


# ---------------------------------------------------------------------------------------------
# T4 / T5 — equal extreme keeps earliest; warm-up abstains
# ---------------------------------------------------------------------------------------------


class TestEqualExtremeAndWarmup:
    def test_t4_equal_extreme_keeps_earliest_strictly_better_refreezes(self, caps):
        state, _ = run_v2(caps, UP_LEG_STEPS + [(raw_bar("b2", 1004, 1001), 40)])
        assert state["prov_high"] == {
            "extreme_ticks": 1004, "delta_ticks": 5, "origin_bar_identity": "b1"}
        state, _ = run_v2(caps, UP_LEG_STEPS + [
            (raw_bar("b2", 1004, 1001), 40),
            (raw_bar("b3", 1005, 1002), 40)])
        assert state["prov_high"] == {
            "extreme_ticks": 1005, "delta_ticks": 10, "origin_bar_identity": "b3"}

    def test_t5_warmup_null_atr_is_named_abstention_with_zero_mutation(self, caps):
        state = sdc.initial_state()
        result = sdc.evaluate(caps, vbar("b0", 1000, 998), state, atr14_ticks=None)
        assert result.state == sdc.initial_state()
        (event,) = result.events
        assert event["event_kind"] == "NAMED_ABSTENTION"
        assert event["reason_code"] == sdc.NO_ATR
        assert event["refs"]["bar_identity"] == "b0"
        # Mid-leg warm-up: no shortened fallback, zero mutation of the frozen leg.
        leg_state, _ = run_v2(caps, UP_LEG_STEPS)
        result = sdc.evaluate(caps, vbar("bx", 1200, 900), leg_state, atr14_ticks=None)
        assert result.state == leg_state
        assert [e["reason_code"] for e in result.events] == [sdc.NO_ATR]


# ---------------------------------------------------------------------------------------------
# SEED phase under the pre-bar law
# ---------------------------------------------------------------------------------------------


class TestSeedLaw:
    def test_monster_bar_extending_both_sides_abstains_and_extends_both(self, caps):
        state, events = run_v2(caps, [
            (raw_bar("b0", 1000, 998), 20),
            (raw_bar("b1", 1010, 990), 20),
        ])
        assert typed_levels(events) == []
        (fact,) = abstentions(events)
        assert fact["reason_code"] == sdc.AMBIGUOUS_BAR_ABSTENTION
        assert state["mode"] == "SEED"
        assert state["prov_high"] == {
            "extreme_ticks": 1010, "delta_ticks": 5, "origin_bar_identity": "b1"}
        assert state["prov_low"] == {
            "extreme_ticks": 990, "delta_ticks": 5, "origin_bar_identity": "b1"}

    def test_two_sided_confirm_tie_is_the_named_seed_abstention_and_reseed(self, caps):
        state, events = run_v2(caps, [
            (raw_bar("b0", 1010, 990), 20),
            (raw_bar("b1", 1000, 996), 20),  # both pre-bar reversals confirm, neither extends
        ])
        assert typed_levels(events) == []
        (fact,) = abstentions(events)
        assert fact["reason_code"] == sdc.AMBIGUOUS_SEED_REVERSAL
        assert state["mode"] == "SEED"
        assert state["prov_high"]["origin_bar_identity"] == "b1"
        assert state["prov_low"]["origin_bar_identity"] == "b1"

    def test_one_side_ambiguous_other_side_confirms(self, caps):
        state, events = run_v2(caps, [
            (raw_bar("b0", 1000, 990), 20),
            (raw_bar("b1", 996, 985), 20),  # low side extends+reverses; high side confirms
        ])
        assert [e.get("reason_code") for e in abstentions(events)] == [
            sdc.AMBIGUOUS_BAR_ABSTENTION]
        assert typed_levels(events) == [swing(tlr.SWING_HIGH, 1000, 5, "b0", "b1")]
        # The abstention audit fact precedes the confirmation (extension evaluated FIRST).
        assert events[0]["event_kind"] == "NAMED_ABSTENTION"
        assert state["mode"] == "DOWN"
        assert state["prov_low"] == {
            "extreme_ticks": 985, "delta_ticks": 5, "origin_bar_identity": "b1"}


# ---------------------------------------------------------------------------------------------
# T6 — the mirror law
# ---------------------------------------------------------------------------------------------


class TestMirrorLaw:
    SCENARIOS = {
        "gv005": GV005_STEPS,
        "t1_t2": UP_LEG_STEPS + [
            (raw_bar("b2", 1003, 1000), 20), (raw_bar("b3", 1003, 999), 20)],
        "t3_ambiguous": UP_LEG_STEPS + [
            (raw_bar("b2", 1010, 998), 20), (raw_bar("b3", 1006, 1005), 20)],
        "t4_equal": UP_LEG_STEPS + [
            (raw_bar("b2", 1004, 1001), 40), (raw_bar("b3", 1005, 1002), 40)],
        "t5_warmup": [(raw_bar("b0", 1000, 998), 20), (raw_bar("b1", 1004, 999), None)],
        "seed_monster": [(raw_bar("b0", 1000, 998), 20), (raw_bar("b1", 1010, 990), 20)],
        "seed_tie": [(raw_bar("b0", 1010, 990), 20), (raw_bar("b1", 1000, 996), 20)],
    }

    @pytest.mark.parametrize("name", sorted(SCENARIOS))
    def test_t6_full_mirror_exact_sign_inversion(self, caps, name):
        steps = self.SCENARIOS[name]
        _, forward = run_v2(caps, steps)
        _, mirrored = run_v2(caps, [(mirror_raw(raw), atr) for raw, atr in steps])
        assert mirrored == [mirror_event(e) for e in forward]


# ---------------------------------------------------------------------------------------------
# T7 — restart/prefix replay parity + idempotency
# ---------------------------------------------------------------------------------------------


class TestRestartParity:
    STEPS = UP_LEG_STEPS + [
        (raw_bar("b2", 1010, 998), 20),
        (raw_bar("b3", 1006, 1005), 20),
        (raw_bar("b4", 1004, 1000), 20),
        (raw_bar("b5", 1011, 1006), 20),
    ]

    def test_t7_restart_mid_leg_yields_byte_identical_swing_stream(self, caps):
        full_state, full_events = run_v2(caps, self.STEPS)
        for cut in range(1, len(self.STEPS)):
            prefix_state, prefix_events = run_v2(caps, self.STEPS[:cut])
            checkpoint = json.loads(canonical_json(prefix_state))  # a real checkpoint round-trip
            resumed_state, resumed_events = run_v2(caps, self.STEPS[cut:], state=checkpoint)
            assert canonical_json(prefix_events + resumed_events) == canonical_json(full_events)
            assert canonical_json(resumed_state) == canonical_json(full_state)

    def test_repeated_bar_identity_is_an_idempotent_no_op(self, caps):
        state, _ = run_v2(caps, self.STEPS[:3])
        again = sdc.evaluate(caps, vbar("b2", 1010, 998), state, atr14_ticks=20)
        assert again.state == state
        assert again.events == ()


# ---------------------------------------------------------------------------------------------
# Acceptance property — alternation over seeded random walks; never confirm at the extreme bar
# ---------------------------------------------------------------------------------------------


class TestAlternationProperty:
    def test_confirmed_swings_strictly_alternate_and_never_confirm_at_own_bar(self, caps):
        # CI-scale slice of the R-F03 acceptance property (the full 10^5-walk run is the
        # acceptance ceremony's job, not a unit test): deterministic seeded walks, both seeds.
        walks, bars_per_walk = 120, 80
        total_levels = 0
        for walk in range(walks):
            rng = random.Random(0xF03 << 8 | walk)
            mid = 100_000
            state = sdc.initial_state()
            kinds: list = []
            for i in range(bars_per_walk):
                mid += rng.randint(-25, 25)
                high = mid + rng.randint(0, 20)
                low = mid - rng.randint(0, 20)
                atr = None if rng.random() < 0.03 else rng.randint(4, 60)
                bar = vbar(f"w{walk}_b{i}", high, low)
                result = sdc.evaluate(caps, bar, state, atr14_ticks=atr)
                state = result.state
                for event in result.events:
                    if event.get("event_kind") == tlr.TYPED_LEVEL:
                        assert (event["origin_bar_identity"]
                                != event["confirmed_by_bar_identity"])
                        kinds.append(event["kind"])
                    else:
                        assert event["reason_code"] in (
                            sdc.NO_ATR, sdc.AMBIGUOUS_BAR_ABSTENTION,
                            sdc.AMBIGUOUS_SEED_REVERSAL)
            assert all(a != b for a, b in zip(kinds, kinds[1:]))
            total_levels += len(kinds)
        assert total_levels > 0  # the property ran against real confirmations


# ---------------------------------------------------------------------------------------------
# The delta mechanism (R-F03 CORRECTED LAW) + §1.2 wire-width boundary
# ---------------------------------------------------------------------------------------------


class TestDeltaMechanism:
    def test_general_three_term_formula_verbatim(self):
        assert sdc.delta_ticks_general(
            price_ticks_x=200_000, atr_ticks_before_x=20,
            min_reversal_ticks=5, reversal_bps=10, k_vol_num=1, k_vol_den=4) == 200
        assert sdc.delta_ticks_general(
            price_ticks_x=-200_000, atr_ticks_before_x=20,
            min_reversal_ticks=5, reversal_bps=10, k_vol_num=1, k_vol_den=4) == 200
        assert sdc.delta_ticks_general(
            price_ticks_x=100, atr_ticks_before_x=39,
            min_reversal_ticks=5, reversal_bps=0, k_vol_num=1, k_vol_den=4) == 10

    def test_declared_instantiation_equals_the_declared_rational_for_all_atr(self):
        for atr in list(range(1, 200)) + [10_000, 123_457]:
            for price in (1, 999, 10**9):
                assert sdc.declared_delta_ticks(
                    common.DECLARED_DC_REVERSAL, price, atr
                ) == common.evaluate_declared_rational(common.DECLARED_DC_REVERSAL, atr)

    def test_undeclared_rule_string_fails_closed(self):
        with pytest.raises(common.StructureLawError):
            sdc.declared_delta_ticks("max(1,ceil(ATR14_ticks*1/1))", 100, 20)

    def test_domain_law(self):
        with pytest.raises(common.StructureLawError):
            sdc.delta_ticks_general(price_ticks_x=1, atr_ticks_before_x=0,
                                    min_reversal_ticks=5, reversal_bps=0,
                                    k_vol_num=1, k_vol_den=4)
        with pytest.raises(common.StructureLawError):
            sdc.delta_ticks_general(price_ticks_x=1, atr_ticks_before_x=20,
                                    min_reversal_ticks=5, reversal_bps=0,
                                    k_vol_num=1, k_vol_den=0)

    def test_int64_boundary_pass_and_quarantine_one_beyond(self):
        # Largest lawful result at the signed-int64 boundary passes…
        assert sdc.delta_ticks_general(
            price_ticks_x=0, atr_ticks_before_x=1,
            min_reversal_ticks=2**63 - 1, reversal_bps=0,
            k_vol_num=1, k_vol_den=4) == 2**63 - 1
        # …one beyond quarantines (never wrap, never saturate, never emit).
        with pytest.raises(QuarantineOverflow):
            sdc.delta_ticks_general(
                price_ticks_x=0, atr_ticks_before_x=1,
                min_reversal_ticks=2**63, reversal_bps=0, k_vol_num=1, k_vol_den=4)

    def test_atr_outside_int64_quarantines_at_the_evaluate_boundary(self, caps):
        with pytest.raises(QuarantineOverflow):
            sdc.evaluate(caps, vbar("b0", 1000, 998), sdc.initial_state(),
                         atr14_ticks=2**63)
        with pytest.raises(QuarantineOverflow):
            sdc.evaluate(caps, vbar("b0", 1000, 998), sdc.initial_state(),
                         atr14_ticks="20")  # a non-int is just as un-emittable


# ---------------------------------------------------------------------------------------------
# GV-005 boundary posture — BLOCKED_UNTIL_PAR-036_RATIFIED (mechanism + named refusal)
# ---------------------------------------------------------------------------------------------


class TestBlockedOnRatify:
    def test_repository_registry_keeps_par036_blocked(self, real_registry):
        row = real_registry.row("FPB-0011")
        assert row["status"] == "BLOCKED_BINDING_V2_MIGRATION"
        assert row["lifecycle_status"] == "BLOCKED"
        assert row["declared_value"] == common.DECLARED_DC_REVERSAL

    def test_the_declared_byte_string_cannot_ride_an_active_row_today(self):
        """The PAR-036 transport interlock, pinned (see the fixture note).

        The declared rule contains ``*``; the B01C-BIND-04 wildcard-sentinel law refuses it in
        an ACTIVE row's resolved fields — at registry LOAD and at sealed-bundle ACCEPTANCE. The
        ratification train must resolve the declared-value transport; until then even a signed,
        ACTIVE-labeled row cannot mint an F03 capability carrying the declared byte-string.
        """
        exact_doc = _ratified_doc(declared_value=common.DECLARED_DC_REVERSAL)
        with pytest.raises(bindings.BindingRegistryError) as excinfo:
            bindings.BindingRegistry(exact_doc)
        assert "ACTIVE_BINDING_UNRESOLVED_FIELD" in str(excinfo.value)

        # Bypassing the loader changes nothing: acceptance re-checks the same law (step 5).
        trust = _trust()
        raw = _trust_bytes(trust)
        bindings.pin_trust_registry_digest(sha256_hex(raw))
        rows = exact_doc["rows"]
        coverage = {fid: "BLOCKED" for fid in bindings.FORMULA_IDS}
        for fid, status in (("F00", "ACTIVE"), ("F03", "ACTIVE")):
            coverage[fid] = status
        unsigned = bindings.SealedParameterBundle(
            schema_version=bindings.SEALED_SCHEMA_VERSION,
            scope={"repository": REPOSITORY, "environment": ENVIRONMENT},
            rows=rows,
            canonical_root_digest=bindings.canonical_rows_digest(rows),
            trust_registry_digest=sha256_hex(raw),
            signer_set=[OWNER_KID],
            signatures=[],
            valid_from=VALID_FROM,
            valid_to=VALID_TO,
            formula_coverage=coverage,
            row_preimage_digests=sorted(
                sha256_hex(canonical_json(row)) for row in rows),
        )
        bundle = dataclasses.replace(
            unsigned, signatures=[_standin_sign(_signing_bytes_for(unsigned))])
        ctx = bindings.VerificationContext(
            trust=trust, trust_registry_bytes=raw, now_us=NOW_US,
            process_scope={"repository": REPOSITORY, "environment": ENVIRONMENT},
            verify_fn=_bytes_bound_verify)
        with pytest.raises(bindings.BlockedBindingIncomplete) as blocked:
            transition.require_bundle(
                bundle, sdc.PARAMETER_DC_REVERSAL, formula_id="F03", ctx=ctx)
        assert blocked.value.formula_id == "F03"

    def test_machine_refuses_a_minted_value_that_is_not_the_declared_byte_string(
            self, minted_transport_cap):
        # The end-to-end mint is REAL — and the machine's anti-hidden-experiment gate refuses
        # any value other than the exact declared PAR-036 byte-string.
        with pytest.raises(common.StructureLawError):
            sdc.evaluate({sdc.PARAMETER_DC_REVERSAL: minted_transport_cap},
                         vbar("b0", 1000, 998), sdc.initial_state(), atr14_ticks=20)

    def test_no_f03_capability_can_be_minted_from_the_repository_registry(self, real_registry):
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
        with pytest.raises(bindings.BlockedBindingIncomplete) as excinfo:
            transition.require_bundle(
                bundle, sdc.PARAMETER_DC_REVERSAL, formula_id="F03", ctx=ctx)
        assert excinfo.value.formula_id == "F03"
        assert str(excinfo.value) == "BLOCKED_BINDING_INCOMPLETE:F03"

    def test_missing_capability_is_the_named_refusal(self):
        with pytest.raises(sdc.BlockedOnRatify) as excinfo:
            sdc.evaluate({}, vbar("b0", 1000, 998), sdc.initial_state(), atr14_ticks=20)
        assert str(excinfo.value) == "BLOCKED_ON_RATIFY(PAR-036)"
        assert excinfo.value.parameter_id == sdc.PARAMETER_DC_REVERSAL


# ---------------------------------------------------------------------------------------------
# The C.3 boundary — adversarial dynamic gate
# ---------------------------------------------------------------------------------------------


class TestBoundaryRejections:
    def test_hand_built_dict_in_place_of_a_capability_is_a_typed_rejection(self):
        state = sdc.initial_state()
        before = copy.deepcopy(state)
        forged = {"value": common.DECLARED_DC_REVERSAL,
                  "formula_id": "F03", "parameter_id": "PAR-036"}
        with pytest.raises(bindings.CapabilityForgeryError):
            sdc.evaluate({sdc.PARAMETER_DC_REVERSAL: forged},
                         vbar("b0", 1000, 998), state, atr14_ticks=20)
        assert state == before  # rejected BEFORE any state transition

    @pytest.mark.parametrize("junk", [17, "max(5,ceil(ATR14_ticks*1/4))", None, [1, 2]])
    def test_non_capability_entries_are_typed_rejections(self, junk):
        with pytest.raises(bindings.CapabilityForgeryError):
            sdc.evaluate({sdc.PARAMETER_DC_REVERSAL: junk},
                         vbar("b0", 1000, 998), sdc.initial_state(), atr14_ticks=20)

    def test_caps_container_must_be_a_mapping(self, caps):
        with pytest.raises(bindings.CapabilityForgeryError):
            sdc.evaluate([caps[sdc.PARAMETER_DC_REVERSAL]],
                         vbar("b0", 1000, 998), sdc.initial_state(), atr14_ticks=20)

    def test_unknown_parameter_key_is_refused(self, caps):
        widened = dict(caps)
        widened["PAR-999"] = caps[sdc.PARAMETER_DC_REVERSAL]
        with pytest.raises(bindings.CapabilityForgeryError):
            sdc.evaluate(widened, vbar("b0", 1000, 998), sdc.initial_state(), atr14_ticks=20)

    def test_foreign_formula_capability_is_refused(self, foreign_cap):
        assert foreign_cap.formula_id == "F00"  # a GENUINE capability — for another formula
        with pytest.raises(bindings.CapabilityForgeryError):
            sdc.evaluate({sdc.PARAMETER_DC_REVERSAL: foreign_cap},
                         vbar("b0", 1000, 998), sdc.initial_state(), atr14_ticks=20)

    def test_foreign_declared_rule_value_is_refused(self, caps):
        genuine = caps[sdc.PARAMETER_DC_REVERSAL]
        tampered = dataclasses.replace(genuine, value=common.DECLARED_EQUAL_LEVEL_TOLERANCE)
        with pytest.raises(common.StructureLawError):
            sdc.evaluate({sdc.PARAMETER_DC_REVERSAL: tampered},
                         vbar("b0", 1000, 998), sdc.initial_state(), atr14_ticks=20)

    def test_raw_dict_env_is_a_typed_boundary_rejection(self, caps):
        with pytest.raises(e01.QuarantineInvalidBar):
            sdc.evaluate(caps, raw_bar("b0", 1000, 998), sdc.initial_state(), atr14_ticks=20)

    def test_invalid_bar_quarantines_at_the_e01_boundary_never_reaching_the_machine(self):
        bad = raw_bar("b0", 1000, 998)
        bad["low_ticks"] = 2000  # violates VALID_BAR: low > high
        with pytest.raises(e01.QuarantineInvalidBar):
            e01.require_valid_bar(bad)

    def test_garbage_state_fails_closed(self, caps):
        with pytest.raises(common.StructureLawError):
            sdc.evaluate(caps, vbar("b0", 1000, 998), {"mode": "UP"}, atr14_ticks=20)
        bad = sdc.initial_state()
        bad["mode"] = "UP"  # UP with no frozen prov_high is not a lawful state
        with pytest.raises(common.StructureLawError):
            sdc.evaluate(caps, vbar("b0", 1000, 998), bad, atr14_ticks=20)


# ---------------------------------------------------------------------------------------------
# Version discipline (§1.5)
# ---------------------------------------------------------------------------------------------


class TestVersionDiscipline:
    def test_v2_atoms_carry_the_semantic_version_tag(self, caps):
        _, events = run_v2(caps, GV005_STEPS)
        for event in typed_levels(events):
            assert event["semantic_version"] == "swing.dc.bar_extrema.v2"

    def test_module_identity_constants(self):
        assert sdc.FORMULA_ID == "F03"
        assert sdc.SEMANTIC_VERSION == "swing.dc.bar_extrema.v2"
        assert sdc.RETIRED_PREDECESSOR == "swing.dc.bar_extrema.v1"
        assert sdc.DC_AMBIGUOUS_BAR_RULE == "ABSTAIN_EXTEND_WINS"
