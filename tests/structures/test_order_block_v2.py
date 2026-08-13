"""R-F12 ``ob.displacement_bos.v2`` — spec vectors T1-T12, GV-F12-01 + acceptance property.

TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12 §R-F12. Vector defaults: ``W=8, H_bos=5`` (the
registry declared values), ``OB_MITIGATION_FRACTION=1/2``, ``OB_BREAK_BUFFER_TICKS=1``,
``OB_TTL_BARS=192`` (the proposed values, carried by TEST capabilities only — never hardcoded in
the machine, proven by scan). The capability fixture is REAL: a test-RATIFIED copy of the
binding registry (the five F12 rows FPB-0022/0068/0069/0070/0071 flipped ACTIVE in memory only,
carrying the exact vector values as declared strings — the repository rows stay BLOCKED, proven
below) sealed via ``build_sealed_bundle`` and accepted through ``transition.require_bundle``
with the Ed25519 pattern from ``tests/contracts/test_sealed_bundle_v2.py``. ``OB_TTL_BARS`` has
NO registry row at all, so its capability can only exist as a test derivation off a REAL minted
F12 handle (C.1: construction is unrestricted, acceptance was the guarded act) — the production
posture is the named refusal ``BLOCKED_ON_RATIFY(OB_TTL_BARS)``, proven below. The
PROPOSED_MUST_RATIFY posture is proven on the UNMODIFIED repository registry: no F12 capability
can be minted (``BLOCKED_BINDING_INCOMPLETE:F12``), and the unratified repository value strings
refuse by name — never evaluated, never defaulted.
"""

from __future__ import annotations

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
from triad_origin.canonical import INT64_MAX, canonical_json, sha256_hex  # noqa: E402
from triad_origin.exact import QuarantineOverflow  # noqa: E402
from triad_origin.structures import order_block_registry_v2 as face  # noqa: E402
from triad_origin.structures import order_block_v2 as ob  # noqa: E402
from triad_origin.structures.common import LONG, SHORT, StructureLawError  # noqa: E402

OWNER_KID = "k-owner-f12"
REPOSITORY = "TriadOrigin"
ENVIRONMENT = "OFF"
VALID_FROM = 1_000_000
VALID_TO = 9_000_000
NOW_US = 2_000_000

# Vector defaults (R-F12 BINDINGS: W/H_bos = the registry declared values; the three
# PROPOSED_MUST_RATIFY values ride ONLY in these test capabilities).
W_BARS = 8
H_BOS = 5
FRACTION = "1/2"
BUFFER_TICKS = 1
TTL_BARS = 192

BAR_US = 60_000_000
T0_BUCKET = 1_000_000_000

# The five registered F12 rows and the vector values the TEST ratification carries.
_F12_ROWS = {
    "FPB-0022": (ob.PARAM_LOOKBACK, str(W_BARS)),
    "FPB-0068": (ob.PARAM_BOS_HORIZON, str(H_BOS)),
    "FPB-0069": (ob.PARAM_OPPOSING, ob.DECLARED_OPPOSING_PREDICATE),
    "FPB-0070": (ob.PARAM_MITIGATION, FRACTION),
    "FPB-0071": (ob.PARAM_BREAK_BUFFER, str(BUFFER_TICKS)),
}

# The repository's UNRATIFIED declared values (must refuse by name, never evaluate).
REPO_MITIGATION_RULE = "penetration>=1/2"
REPO_BREAK_RULE = "finalized close beyond far edge by BOS_CLOSE_BUFFER"
V1_ATR_BUFFER_RULE = "max(1,ceil(ATR14_ticks*1/20))"


# ---------------------------------------------------------------------------------------------
# Capability fixtures (the C.1/C.3 seam, exercised for real)
# ---------------------------------------------------------------------------------------------


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


def _ratified_doc() -> dict:
    """The repository registry with the five F12 rows flipped ACTIVE — TEST-only posture.

    Declared values are the exact R-F12 vector values (sentinel-free), so the minted
    capabilities carry the vector parameters end to end with no post-mint substitution. The
    repository rows stay BLOCKED (proven in TestProposedMustRatify).
    """
    doc = json.loads(pathlib.Path(bindings.DEFAULT_REGISTRY_PATH).read_text(encoding="utf-8"))
    for row in doc["rows"]:
        binding_id = row["binding_id"]
        if binding_id in _F12_ROWS:
            parameter_id, declared = _F12_ROWS[binding_id]
            assert row["parameter_id"] == parameter_id
            row.update({
                "status": "ACTIVE",
                "lifecycle_status": "ACTIVE",
                "cardinality": "EXACTLY_ONE",
                "migration_state": "NOT_APPLICABLE",
                "declared_value": declared,
                "semantic_slot": f"order_block_v2_{parameter_id}_TEST",
                "condition": "TEST-RATIFIED stand-in for the F12 ratification ceremony",
                "activation_scope": f"TEST;F12;{parameter_id};order_block_v2 vectors only",
                "precedence": "TEST_FIXTURE",
                "consumer": "ORIGIN(F12)",
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
def caps():
    """REAL VerifiedCapability handles for the F12 parameters (real Ed25519, end to end).

    The five registered rows mint through the full ``build_sealed_bundle`` ->
    ``require_bundle`` path. ``OB_TTL_BARS`` has NO registry row (the R-F12 posture), so its
    handle is a test derivation off a REAL minted F12 capability via ``dataclasses.replace``
    (C.1: construction is unrestricted — acceptance was the guarded act; the boundary checks
    exact type + formula + key, which the derivation preserves).
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey, Ed25519PublicKey)

    bindings._reset_trust_registry_pin_for_tests()
    bindings._reset_acceptance_memo_for_tests()
    try:
        registry = bindings.BindingRegistry(_ratified_doc())
        private = Ed25519PrivateKey.generate()
        pub_hex = private.public_key().public_bytes_raw().hex()
        trust = {OWNER_KID: {"key_id": OWNER_KID, "identity": "owner@triad",
                             "role": "AUTHORITY_OWNER", "algorithm": "ed25519",
                             "public_key_hex": pub_hex, "revoked": False}}
        raw = json.dumps(trust, sort_keys=True).encode("utf-8")
        bindings.pin_trust_registry_digest(sha256_hex(raw))
        unsigned = bindings.build_sealed_bundle(
            registry, repository=REPOSITORY, environment=ENVIRONMENT,
            valid_from=VALID_FROM, valid_to=VALID_TO,
            trust_registry_digest=sha256_hex(raw), signer_set=[OWNER_KID])
        signing = bindings.sealed_bundle_signing_bytes(
            canonical_root_digest=unsigned.canonical_root_digest, scope=unsigned.scope,
            valid_from=unsigned.valid_from, valid_to=unsigned.valid_to)
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
        minted = {}
        for parameter_id, declared in _F12_ROWS.values():
            cap = transition.require_bundle(bundle, parameter_id, formula_id="F12", ctx=ctx)
            assert type(cap) is bindings.VerifiedCapability
            assert cap.formula_id == "F12"
            assert cap.parameter_id == parameter_id
            assert cap.value == declared
            minted[parameter_id] = cap
        minted[ob.PARAM_TTL] = dataclasses.replace(
            minted[ob.PARAM_LOOKBACK], parameter_id=ob.PARAM_TTL, value=str(TTL_BARS))
        return minted
    finally:
        bindings._reset_trust_registry_pin_for_tests()
        bindings._reset_acceptance_memo_for_tests()


def variant(caps: dict, **values: object) -> dict:
    """Variant parameter maps off the REAL minted handles (value-only derivations)."""
    out = dict(caps)
    for parameter_id, value in values.items():
        out[parameter_id] = dataclasses.replace(out[parameter_id], value=value)
    return out


# ---------------------------------------------------------------------------------------------
# Bar fixtures (E01-validated — the ONLY lawful construction path) + the script driver
# ---------------------------------------------------------------------------------------------


def raw_bar(identity: str, *, o: int, h: int, l: int, c: int) -> dict:  # noqa: E741
    return {
        "bar_identity": identity, "metadata_revision": "r1",
        "open_ticks": o, "high_ticks": h, "low_ticks": l, "close_ticks": c,
        "base_volume": 1, "quote_volume": 1, "trade_count": 1,
    }


def vbar(identity: str, *, o: int, h: int, l: int, c: int) -> e01.ValidatedBar:  # noqa: E741
    return e01.require_valid_bar(raw_bar(identity, o=o, h=h, l=l, c=c))


def bucket(i: int) -> int:
    return T0_BUCKET + i * BAR_US


def bar_step(i: int, *, o: int, h: int, l: int, c: int, src: str = "s1",  # noqa: E741
             identity: str | None = None, bucket_us: int | None = None) -> tuple:
    return ("bar", {
        "env": vbar(identity if identity is not None else f"{src}-b{i}", o=o, h=h, l=l, c=c),
        "source_id": src, "bar_index": i,
        "bucket_start_us": bucket(i) if bucket_us is None else bucket_us})


def disp_step(d_id: str, direction: str, g: int, avail_us: int | None = None) -> tuple:
    return ("disp", {
        "displacement_id": d_id, "direction": direction, "trigger_bar_index": g,
        "availability_time_us": bucket(g + 1) if avail_us is None else avail_us,
        "source_event_id": f"ev-{d_id}"})


def break_step(k_id: str, direction: str, j: int, close: int,
               avail_us: int | None = None) -> tuple:
    return ("break", {
        "bos_occurrence_id": k_id, "direction": direction, "break_bar_index": j,
        "close_ticks": close,
        "availability_time_us": bucket(j + 1) if avail_us is None else avail_us,
        "source_event_id": f"ev-{k_id}"})


def apply_step(caps: dict, state: dict, step: tuple) -> transition.TransitionResult:
    kind, kwargs = step
    if kind == "bar":
        return ob.evaluate(caps, kwargs["env"], state, source_id=kwargs["source_id"],
                           bar_index=kwargs["bar_index"],
                           bucket_start_us=kwargs["bucket_start_us"])
    if kind == "disp":
        return ob.register_displacement(caps, state, **kwargs)
    if kind == "break":
        return ob.register_break(caps, state, **kwargs)
    if kind == "gap":
        return ob.note_gap(state, **kwargs)
    if kind == "revise":
        return ob.revise_bar(state, **kwargs)
    raise AssertionError(f"unknown script step {kind!r}")


def drive(caps: dict, state: dict, script: list) -> tuple:
    events: list = []
    for step in script:
        result = apply_step(caps, state, step)
        state = result.state
        events.extend(result.events)
    return state, events


def phase_of(state: dict, ob_id: str) -> str:
    return state["blocks"][ob_id]["phase"]


def state_events(events: list, ob_id: str | None = None) -> list:
    out = [ev for ev in events if ev.get("event_kind") == ob.STATE_KIND]
    if ob_id is not None:
        out = [ev for ev in out if ev["ob_id"] == ob_id]
    return out


def first_touches(events: list) -> list:
    return [ev for ev in events if ev.get("event_kind") == ob.FIRST_TOUCH_KIND]


# The GV-F12-01 bull tape (tick=1): w1=(105,106,99,100) at index 7, w2=(104,105,100,101) at
# index 9; the second bull candidate triggers at index 6 (origin: the bearish index-5 bar).
def golden_script() -> list:
    steps = [bar_step(i, o=100, h=105, l=99, c=104) for i in range(0, 5)]     # bullish filler
    steps += [
        bar_step(5, o=103, h=104, l=100, c=101),          # bearish — d-006's origin
        bar_step(6, o=101, h=105, l=100, c=104),
        disp_step("d-006", LONG, 6),                      # the second pending bull candidate
        bar_step(7, o=105, h=106, l=99, c=100),           # w1 (bearish, index 7)
        bar_step(8, o=100, h=106, l=99, c=105),
        bar_step(9, o=104, h=105, l=100, c=101),          # w2 (bearish, index 9) — LATEST
        bar_step(10, o=101, h=112, l=100, c=111),         # the displacement trigger bar g
        disp_step("d-010", LONG, 10),
        bar_step(11, o=105, h=112, l=104, c=110),
        break_step("k-012", LONG, 12, 112),               # accepted up-break within H_bos
        bar_step(12, o=110, h=113, l=109, c=112),         # d-006 expires at its own H_bos here
        bar_step(13, o=106, h=107, l=103, c=105),         # touch: low 103 -> depth 1/4
        bar_step(14, o=104, h=106, l=101, c=103),         # low 101 -> depth 3/4 -> MITIGATED
        break_step("k-015", SHORT, 15, 99),               # down-break through 100 - buffer
    ]
    return steps


OB1 = "ob:d-010"
OB2 = "ob:d-006"


# ---------------------------------------------------------------------------------------------
# GV-F12-01 (spec T2 — latest-origin selection + the full lifecycle walk)
# ---------------------------------------------------------------------------------------------


class TestGoldenGVF1201:
    def test_gv_f12_01_full_walk(self, caps):
        state, events = drive(caps, ob.initial_state(), golden_script())
        # Origin selection: LATEST opposing bar wins — w2 (index 9), never w1 (index 7).
        row = state["blocks"][OB1]
        assert row["origin_bar_index"] == 9
        assert row["origin_bar_identity"] == "s1-b9"
        # Zone = [L_o, O_o] = [100, 104], frozen.
        assert [row["zone_low_ticks"], row["zone_high_ticks"]] == [100, 104]
        assert row["far_edge_ticks"] == 100
        assert row["proximal_edge_ticks"] == 104
        # CONFIRMED with lineage (d, k); the 1:1 consumption map holds.
        assert state["bos_consumed"] == {"k-012": OB1}
        assert row["bos_occurrence_id"] == "k-012"
        assert row["confirmed_bar_index"] == 12
        assert row["availability_time_us"] == bucket(13)
        assert row["ttl_deadline_bar_index"] == 12 + TTL_BARS
        confirm = [ev for ev in state_events(events, OB1)
                   if ev["to_phase"] == ob.CONFIRMED_BY_BOS]
        assert len(confirm) == 1
        assert confirm[0]["lineage"] == {
            "displacement_id": "d-010", "bos_occurrence_id": "k-012",
            "origin_bar_index": 9, "origin_source_id": "s1",
            "origin_bar_identity": "s1-b9"}
        assert confirm[0]["zone"] == [100, 104]
        # The second pending bull candidate may NOT consume k; it expires at its OWN H_bos.
        assert phase_of(state, OB2) == ob.EXPIRED
        assert state["blocks"][OB2]["terminal_reason"] == ob.BOS_HORIZON_ELAPSED
        assert state["blocks"][OB2]["bos_occurrence_id"] is None
        # Touch at low 103: TOUCHED then PARTIAL in one bar (depth 1 tick = 1/4 < 1/2).
        trail = [(ev["to_phase"], ev["bar_index"]) for ev in state_events(events, OB1)]
        assert trail == [
            (ob.DISPLACED, 10), (ob.CONFIRMED_BY_BOS, 12), (ob.FRESH, 12),
            (ob.TOUCHED, 13), (ob.PARTIAL, 13), (ob.MITIGATED, 14), (ob.BROKEN, 15)]
        touched = [ev for ev in state_events(events, OB1) if ev["to_phase"] == ob.TOUCHED]
        assert touched[0]["depth"] == [1, 4]
        # Later low 101 -> depth 3/4 >= 1/2 -> MITIGATED.
        mitigated = [ev for ev in state_events(events, OB1) if ev["to_phase"] == ob.MITIGATED]
        assert mitigated[0]["depth"] == [3, 4]
        # Later accepted down-break through 100 - buffer -> BROKEN.
        assert phase_of(state, OB1) == ob.BROKEN
        broken = [ev for ev in state_events(events, OB1) if ev["to_phase"] == ob.BROKEN]
        assert broken[0]["bos_occurrence_id"] == "k-015"
        assert broken[0]["reason"] == ob.OPPOSING_BOS_BREAK
        # First touch consumed atomically, exactly once.
        touches = first_touches(events)
        assert len(touches) == 1
        assert touches[0]["ob_id"] == OB1
        assert touches[0]["bar_index"] == 13
        assert touches[0]["depth"] == [1, 4]

    def test_golden_origin_event_carries_the_ratified_tie_rule(self, caps):
        _state, events = drive(caps, ob.initial_state(), golden_script())
        displaced = [ev for ev in state_events(events, OB1) if ev["to_phase"] == ob.DISPLACED]
        assert displaced[0]["from_phase"] == ob.ORIGIN_CANDIDATE
        assert displaced[0]["tie_rule"] == "LATEST_THEN_MIN_SOURCE_ID"
        assert displaced[0]["origin"] == {
            "bar_index": 9, "source_id": "s1", "bar_identity": "s1-b9"}


# ---------------------------------------------------------------------------------------------
# T1 — no BOS within H_bos: expire, never confirmed ("a large candle alone is not an OB")
# ---------------------------------------------------------------------------------------------


def pending_script(*, d_id: str = "d-002", direction: str = LONG, upto: int = 2) -> list:
    steps = [bar_step(0, o=100, h=105, l=99, c=104)]
    steps.append(bar_step(1, o=103, h=104, l=100, c=101))       # bearish origin
    steps += [bar_step(i, o=100, h=105, l=99, c=104) for i in range(2, upto + 1)]
    steps.append(disp_step(d_id, direction, upto))
    return steps


class TestT1HorizonExpiry:
    def test_no_bos_within_h_bos_expires_never_confirms(self, caps):
        script = pending_script(upto=2)  # g=2, deadline 7
        script += [bar_step(i, o=100, h=105, l=99, c=104) for i in range(3, 9)]
        state, events = drive(caps, ob.initial_state(), script)
        assert phase_of(state, "ob:d-002") == ob.EXPIRED
        assert state["blocks"]["ob:d-002"]["terminal_reason"] == ob.BOS_HORIZON_ELAPSED
        assert state["bos_consumed"] == {}
        expired = [ev for ev in state_events(events) if ev["to_phase"] == ob.EXPIRED]
        assert expired[0]["bar_index"] == 8  # strictly past the deadline (2 + 5 = 7)

    def test_at_deadline_bar_does_not_expire(self, caps):
        script = pending_script(upto=2)
        script += [bar_step(i, o=100, h=105, l=99, c=104) for i in range(3, 8)]  # up to bar 7
        state, _events = drive(caps, ob.initial_state(), script)
        assert phase_of(state, "ob:d-002") == ob.DISPLACED

    def test_break_at_h_bos_confirms_fifth_included(self, caps):
        script = pending_script(upto=2)
        script += [bar_step(i, o=100, h=105, l=99, c=104) for i in range(3, 7)]
        script.append(break_step("k-007", LONG, 7, 120))  # j - g = 5 == H_bos
        state, _events = drive(caps, ob.initial_state(), script)
        assert phase_of(state, "ob:d-002") == ob.FRESH
        assert state["bos_consumed"] == {"k-007": "ob:d-002"}

    def test_break_past_h_bos_never_confirms_sixth_fails(self, caps):
        script = pending_script(upto=2)
        script += [bar_step(i, o=100, h=105, l=99, c=104) for i in range(3, 8)]
        script.append(break_step("k-008", LONG, 8, 120))  # j - g = 6 > H_bos
        state, _events = drive(caps, ob.initial_state(), script)
        assert phase_of(state, "ob:d-002") == ob.DISPLACED  # untouched by the late break
        assert state["bos_consumed"] == {}

    def test_break_after_terminal_expiry_never_reopens(self, caps):
        script = pending_script(upto=2)
        script += [bar_step(i, o=100, h=105, l=99, c=104) for i in range(3, 9)]  # EXPIRED at 8
        script.append(break_step("k-009", LONG, 9, 120))
        state, _events = drive(caps, ob.initial_state(), script)
        assert phase_of(state, "ob:d-002") == ob.EXPIRED
        assert state["bos_consumed"] == {}


# ---------------------------------------------------------------------------------------------
# T3 — multi-source equal index: MINIMUM source_id; body size never participates
# ---------------------------------------------------------------------------------------------


class TestT3MultiSourceTie:
    def test_equal_index_tie_breaks_by_min_source_id_body_never_participates(self, caps):
        script = [
            bar_step(0, o=100, h=105, l=99, c=104),
            # Index 1 from TWO sources, both opposing: s_b carries the LARGER body, s_a the
            # smaller — under the deleted v1 rule s_b would win; under OB_ORIGIN_TIE the
            # minimum source_id (s_a) wins.
            bar_step(1, o=110, h=111, l=99, c=100, src="s_b"),
            bar_step(1, o=104, h=105, l=100, c=103, src="s_a"),
            bar_step(2, o=100, h=105, l=99, c=104),
            disp_step("d-t3", LONG, 2),
        ]
        state, _events = drive(caps, ob.initial_state(), script)
        row = state["blocks"]["ob:d-t3"]
        assert row["origin_bar_index"] == 1
        assert row["origin_source_id"] == "s_a"
        assert row["origin_bar_identity"] == "s_a-b1"
        # The zone is frozen from the winning bar (s_a): [100, 104].
        assert [row["zone_low_ticks"], row["zone_high_ticks"]] == [100, 104]

    def test_latest_index_beats_an_earlier_larger_body(self, caps):
        script = [
            bar_step(0, o=115, h=116, l=95, c=96),   # bearish, huge body, EARLIER
            bar_step(1, o=104, h=105, l=100, c=103),  # bearish, one-tick body, LATEST
            bar_step(2, o=100, h=105, l=99, c=104),
            disp_step("d-t3b", LONG, 2),
        ]
        state, _events = drive(caps, ob.initial_state(), script)
        assert state["blocks"]["ob:d-t3b"]["origin_bar_index"] == 1

    def test_no_opposing_origin_is_the_named_abstention(self, caps):
        script = [bar_step(i, o=100, h=105, l=99, c=104) for i in range(0, 3)]
        script.append(disp_step("d-none", LONG, 2))
        state, events = drive(caps, ob.initial_state(), script)
        assert state["blocks"] == {}
        named = [ev for ev in events if ev.get("reason_code") == ob.NO_OPPOSING_ORIGIN]
        assert len(named) == 1
        assert named[0]["refs"]["lookback_bars"] == W_BARS

    def test_lookback_boundary_w_included_w_plus_one_excluded(self, caps):
        # Opposing bar ONLY at offset W (index g - W): still found.
        script = [bar_step(0, o=103, h=104, l=100, c=101)]           # bearish at index 0
        script += [bar_step(i, o=100, h=105, l=99, c=104) for i in range(1, 9)]
        script.append(disp_step("d-w", LONG, 8))                     # g=8: window [0, 7]
        state, _ = drive(caps, ob.initial_state(), script)
        assert state["blocks"]["ob:d-w"]["origin_bar_index"] == 0
        # One further back (index 0 with g=9: window [1, 8]) is out of the lookback.
        script2 = [bar_step(0, o=103, h=104, l=100, c=101)]
        script2 += [bar_step(i, o=100, h=105, l=99, c=104) for i in range(1, 10)]
        script2.append(disp_step("d-w1", LONG, 9))
        state2, events2 = drive(caps, ob.initial_state(), script2)
        assert "ob:d-w1" not in state2["blocks"]
        assert [ev for ev in events2 if ev.get("reason_code") == ob.NO_OPPOSING_ORIGIN]

    def test_doji_never_opposes(self, caps):
        script = [
            bar_step(0, o=100, h=105, l=99, c=104),
            bar_step(1, o=102, h=105, l=99, c=102),   # doji: close == open
            bar_step(2, o=100, h=105, l=99, c=104),
            disp_step("d-doji", LONG, 2),
        ]
        state, events = drive(caps, ob.initial_state(), script)
        assert "ob:d-doji" not in state["blocks"]
        assert [ev for ev in events if ev.get("reason_code") == ob.NO_OPPOSING_ORIGIN]


# ---------------------------------------------------------------------------------------------
# T4 — one BOS + two pending same-direction: EARLIEST g claims; the map is 1:1
# ---------------------------------------------------------------------------------------------


class TestT4OneBosOneLineage:
    def two_pending_script(self) -> list:
        steps = [bar_step(i, o=100, h=105, l=99, c=104) for i in range(0, 4)]
        steps[1] = bar_step(1, o=103, h=104, l=100, c=101)   # bearish origin for both
        steps += [
            bar_step(4, o=103, h=104, l=100, c=101),          # bearish (d-late's origin)
            bar_step(5, o=100, h=105, l=99, c=104),
            disp_step("d-early", LONG, 5),                    # g=5, deadline 10
            bar_step(6, o=100, h=105, l=99, c=104),
            disp_step("d-late", LONG, 6),                     # g=6, deadline 11
        ]
        return steps

    def test_earliest_trigger_claims_the_bos_and_the_map_is_one_to_one(self, caps):
        script = self.two_pending_script()
        script.append(break_step("k-007", LONG, 7, 120))      # eligible for BOTH
        state, events = drive(caps, ob.initial_state(), script)
        assert state["bos_consumed"] == {"k-007": "ob:d-early"}
        assert phase_of(state, "ob:d-early") == ob.FRESH
        assert phase_of(state, "ob:d-late") == ob.DISPLACED   # remains pending
        confirms = [ev for ev in state_events(events) if ev["to_phase"] == ob.CONFIRMED_BY_BOS]
        assert len(confirms) == 1
        assert confirms[0]["ob_id"] == "ob:d-early"

    def test_the_other_pending_confirms_its_own_later_bos(self, caps):
        script = self.two_pending_script()
        script.append(break_step("k-007", LONG, 7, 120))
        script.append(bar_step(7, o=100, h=105, l=99, c=104))
        script.append(break_step("k-008", LONG, 8, 121))
        state, _events = drive(caps, ob.initial_state(), script)
        assert state["bos_consumed"] == {"k-007": "ob:d-early", "k-008": "ob:d-late"}
        assert state["blocks"]["ob:d-late"]["bos_occurrence_id"] == "k-008"
        # 1:1 both ways: distinct k -> distinct ob.
        assert len(set(state["bos_consumed"].values())) == len(state["bos_consumed"])

    def test_duplicate_bos_registration_is_an_idempotent_no_op(self, caps):
        script = self.two_pending_script()
        script.append(break_step("k-007", LONG, 7, 120))
        state, _ = drive(caps, ob.initial_state(), script)
        replay = apply_step(caps, state, break_step("k-007", LONG, 7, 120))
        assert replay.events == ()
        assert canonical_json(replay.state) == canonical_json(state)

    def test_conflicting_bos_facts_under_one_id_refuse(self, caps):
        script = self.two_pending_script()
        script.append(break_step("k-007", LONG, 7, 120))
        state, _ = drive(caps, ob.initial_state(), script)
        with pytest.raises(StructureLawError, match=ob.INPUT_IDENTITY_CONFLICT):
            apply_step(caps, state, break_step("k-007", LONG, 7, 121))

    def test_mismatched_direction_bos_confirms_nothing(self, caps):
        script = self.two_pending_script()
        script.append(break_step("k-short", SHORT, 7, 90))
        state, _events = drive(caps, ob.initial_state(), script)
        assert state["bos_consumed"] == {}
        assert phase_of(state, "ob:d-early") == ob.DISPLACED
        assert phase_of(state, "ob:d-late") == ob.DISPLACED

    def test_equal_trigger_residual_tie_takes_the_smallest_ob_id(self, caps):
        steps = [
            bar_step(0, o=103, h=104, l=100, c=101),
            bar_step(1, o=100, h=105, l=99, c=104),
            disp_step("d-b", LONG, 1),
            disp_step("d-a", LONG, 1),                        # same trigger bar g=1
            break_step("k-002", LONG, 2, 120),
        ]
        state, _ = drive(caps, ob.initial_state(), steps)
        assert state["bos_consumed"] == {"k-002": "ob:d-a"}   # deterministic residual rule
        assert phase_of(state, "ob:d-b") == ob.DISPLACED


# ---------------------------------------------------------------------------------------------
# T5 — zone-edge touch inclusive
# ---------------------------------------------------------------------------------------------


def confirmed_zone_script() -> list:
    """A confirmed bull zone [100, 104], availability bucket(13), TTL deadline 12 + TTL."""
    return golden_script()[:16]  # through bar 12 (confirmation landed at k-012/bar 12)


class TestT5EdgeTouchInclusive:
    def test_proximal_edge_touch_is_a_touch_with_zero_depth(self, caps):
        script = confirmed_zone_script()
        script.append(bar_step(13, o=106, h=107, l=104, c=105))   # low == z1 == 104
        state, events = drive(caps, ob.initial_state(), script)
        assert phase_of(state, OB1) == ob.TOUCHED
        assert state["blocks"][OB1]["max_depth"] == [0, 1]
        touches = first_touches(events)
        assert len(touches) == 1 and touches[0]["depth"] == [0, 1]
        assert not [ev for ev in state_events(events, OB1) if ev["to_phase"] == ob.PARTIAL]

    def test_one_tick_above_the_proximal_edge_is_no_touch(self, caps):
        script = confirmed_zone_script()
        script.append(bar_step(13, o=106, h=107, l=105, c=106))   # low == 105 > z1
        state, events = drive(caps, ob.initial_state(), script)
        assert phase_of(state, OB1) == ob.FRESH
        assert first_touches(events) == []

    def test_far_edge_touch_clamps_to_full_depth_and_mitigates(self, caps):
        script = confirmed_zone_script()
        script.append(bar_step(13, o=106, h=107, l=100, c=105))   # low == z0 == 100
        state, _events = drive(caps, ob.initial_state(), script)
        assert phase_of(state, OB1) == ob.MITIGATED
        assert state["blocks"][OB1]["max_depth"] == [1, 1]

    def test_exact_midpoint_mitigates(self, caps):
        # FPB-0070 boundary rule: exactly the midpoint mitigates (depth 2/4 = 1/2 >= 1/2).
        script = confirmed_zone_script()
        script.append(bar_step(13, o=106, h=107, l=102, c=105))
        state, _events = drive(caps, ob.initial_state(), script)
        assert phase_of(state, OB1) == ob.MITIGATED
        assert state["blocks"][OB1]["max_depth"] == [1, 2]


# ---------------------------------------------------------------------------------------------
# T6 — mitigation vs break on one bar: BROKEN wins (R-F12's own precedence order)
# ---------------------------------------------------------------------------------------------


class TestT6BrokenBeatsMitigation:
    def test_same_bar_break_preempts_the_mitigation_progression(self, caps):
        script = confirmed_zone_script()
        # The accepted opposing occurrence derived from bar 13 registers BEFORE bar 13
        # evaluates (the declared intake order); bar 13's low would have MITIGATED.
        script.append(break_step("k-013", SHORT, 13, 99))
        script.append(bar_step(13, o=104, h=105, l=99, c=99))
        state, events = drive(caps, ob.initial_state(), script)
        assert phase_of(state, OB1) == ob.BROKEN
        zone_events = state_events(events, OB1)
        assert [ev["to_phase"] for ev in zone_events if ev["bar_index"] == 13] == [ob.BROKEN]
        assert not [ev for ev in zone_events if ev["to_phase"] == ob.MITIGATED]
        assert first_touches(events) == []  # a terminal zone consumes no first touch

    def test_the_precedence_order_is_pinned_verbatim(self):
        assert ob.SAME_EVENT_PRECEDENCE == (
            ob.INVALIDATED, ob.BROKEN, ob.EXPIRED, ob.MITIGATED, ob.PARTIAL, ob.TOUCHED)
        assert ob.dominant_f12([ob.EXPIRED, ob.MITIGATED]) == ob.EXPIRED
        assert ob.dominant_f12([ob.MITIGATED, ob.BROKEN, ob.EXPIRED]) == ob.BROKEN
        assert ob.dominant_f12([ob.TOUCHED, ob.INVALIDATED]) == ob.INVALIDATED
        with pytest.raises(StructureLawError):
            ob.dominant_f12([])
        with pytest.raises(StructureLawError):
            ob.dominant_f12(["NOT_A_PHASE"])

    def test_break_one_tick_short_of_the_buffer_does_not_break(self, caps):
        script = confirmed_zone_script()
        script.append(break_step("k-013", SHORT, 13, 100))  # close == far edge, not far - b
        state, _events = drive(caps, ob.initial_state(), script)
        assert phase_of(state, OB1) == ob.FRESH

    def test_equality_at_the_buffered_boundary_breaks(self, caps):
        script = confirmed_zone_script()
        script.append(break_step("k-013", SHORT, 13, 99))   # close == far - b exactly
        state, _events = drive(caps, ob.initial_state(), script)
        assert phase_of(state, OB1) == ob.BROKEN

    def test_same_direction_break_never_breaks_the_zone(self, caps):
        script = confirmed_zone_script()
        script.append(break_step("k-013", LONG, 13, 99))    # same direction as the zone
        state, _events = drive(caps, ob.initial_state(), script)
        assert phase_of(state, OB1) == ob.FRESH


# ---------------------------------------------------------------------------------------------
# T7 — TTL boundary (the OB_TTL_BARS mechanism, capability-fed, inclusive at TTL)
# ---------------------------------------------------------------------------------------------


class TestT7TtlBoundary:
    def test_ttl_boundary_expires_inclusive_and_dominates_the_touch(self, caps):
        tight = variant(caps, **{ob.PARAM_TTL: "3"})          # deadline = 12 + 3 = 15
        script = confirmed_zone_script()
        script.append(bar_step(13, o=106, h=107, l=103, c=105))   # alive: TOUCHED + PARTIAL
        script.append(bar_step(14, o=104, h=106, l=101, c=103))   # alive: MITIGATED (14 < 15)
        script.append(bar_step(15, o=104, h=106, l=101, c=103))   # AT the TTL: EXPIRED only
        state, events = drive(tight, ob.initial_state(), script)
        assert phase_of(state, OB1) == ob.EXPIRED
        assert state["blocks"][OB1]["terminal_reason"] == ob.OB_TTL
        at_15 = [ev for ev in state_events(events, OB1) if ev["bar_index"] == 15]
        assert [ev["to_phase"] for ev in at_15] == [ob.EXPIRED]
        at_14 = [ev for ev in state_events(events, OB1) if ev["bar_index"] == 14]
        assert [ev["to_phase"] for ev in at_14] == [ob.MITIGATED]

    def test_ttl_expires_without_any_contact_too(self, caps):
        tight = variant(caps, **{ob.PARAM_TTL: "2"})          # deadline 14
        script = confirmed_zone_script()
        script.append(bar_step(13, o=110, h=111, l=109, c=110))  # no contact
        script.append(bar_step(14, o=110, h=111, l=109, c=110))  # no contact; TTL hits
        state, _events = drive(tight, ob.initial_state(), script)
        assert phase_of(state, OB1) == ob.EXPIRED
        assert state["blocks"][OB1]["terminal_reason"] == ob.OB_TTL

    def test_ttl_never_touches_a_pending_candidate(self, caps):
        tight = variant(caps, **{ob.PARAM_TTL: "1"})
        script = pending_script(upto=2)                      # deadline (H_bos) = 7
        script.append(bar_step(3, o=100, h=105, l=99, c=104))
        state, _events = drive(tight, ob.initial_state(), script)
        assert phase_of(state, "ob:d-002") == ob.DISPLACED   # H_bos governs pendings, not TTL


# ---------------------------------------------------------------------------------------------
# T8 — invalid-OHLC origin rejected (§1.1 VALID_BAR at the E01 boundary + the gap law)
# ---------------------------------------------------------------------------------------------


class TestT8InvalidOhlc:
    def test_close_above_high_is_quarantined_at_the_boundary(self):
        bad = raw_bar("bad", o=100, h=105, l=99, c=106)
        with pytest.raises(e01.QuarantineInvalidBar) as info:
            e01.require_valid_bar(bad)
        record = info.value.record()
        assert record["reason_code"] == "QUARANTINE_INVALID_BAR"
        assert record["accepted"] is False

    def test_open_below_low_and_missing_volume_quarantine(self):
        with pytest.raises(e01.QuarantineInvalidBar):
            e01.require_valid_bar(raw_bar("bad2", o=98, h=105, l=99, c=104))
        gutted = raw_bar("bad3", o=100, h=105, l=99, c=104)
        del gutted["base_volume"]
        with pytest.raises(e01.QuarantineInvalidBar):
            e01.require_valid_bar(gutted)

    def test_quarantined_bar_invalidates_exactly_as_a_gap(self, caps):
        # The would-be origin bar is invalid: it never ingests; the caller notes the gap
        # (§1.1 — a quarantined bar invalidates any window that requires it). The window
        # resets; the next displacement finds no origin and abstains — the invalid bar can
        # never be selected.
        script = confirmed_zone_script()
        state, _ = drive(caps, ob.initial_state(), script)
        result = ob.note_gap(state, bar_index=13, reason="QUARANTINE_INVALID_BAR")
        assert result.state["last_bar_index"] is None
        assert result.state["bars"] == {}
        assert phase_of(result.state, OB1) == ob.INVALIDATED
        assert result.state["blocks"][OB1]["terminal_reason"] == "QUARANTINE_INVALID_BAR"
        # A stale displacement after the gap refuses loudly — never a silent partial search.
        with pytest.raises(StructureLawError, match=ob.TRIGGER_OUT_OF_ORDER):
            apply_step(caps, result.state, disp_step("d-stale", LONG, 13))

    def test_index_skip_is_a_sequence_gap(self, caps):
        script = confirmed_zone_script()
        script.append(bar_step(14, o=106, h=107, l=105, c=106))  # skips index 13
        state, events = drive(caps, ob.initial_state(), script)
        assert phase_of(state, OB1) == ob.INVALIDATED
        assert state["blocks"][OB1]["terminal_reason"] == ob.SEQUENCE_GAP
        gap_events = [ev for ev in state_events(events, OB1)
                      if ev["reason"] == ob.SEQUENCE_GAP]
        assert len(gap_events) == 1
        # The window restarted at the skipping bar.
        assert state["last_bar_index"] == 14
        assert sorted(state["bars"]) == ["14"]


# ---------------------------------------------------------------------------------------------
# T9 — defining revision -> INVALIDATED
# ---------------------------------------------------------------------------------------------


class TestT9DefiningRevision:
    def test_origin_bar_revision_invalidates_the_confirmed_zone(self, caps):
        state, _ = drive(caps, ob.initial_state(), confirmed_zone_script())
        result = ob.revise_bar(state, bar_index=9, source_event_id="rev-9")
        assert phase_of(result.state, OB1) == ob.INVALIDATED
        assert result.state["blocks"][OB1]["terminal_reason"] == ob.DEFINING_REVISION
        events = state_events(list(result.events), OB1)
        assert events[0]["reason"] == ob.DEFINING_REVISION

    def test_trigger_bar_revision_invalidates_the_pending(self, caps):
        state, _ = drive(caps, ob.initial_state(), pending_script(upto=2))
        result = ob.revise_bar(state, bar_index=2, source_event_id="rev-2")
        assert phase_of(result.state, "ob:d-002") == ob.INVALIDATED

    def test_confirming_bos_bar_revision_invalidates_the_zone(self, caps):
        state, _ = drive(caps, ob.initial_state(), confirmed_zone_script())
        result = ob.revise_bar(state, bar_index=12, source_event_id="rev-12")
        assert phase_of(result.state, OB1) == ob.INVALIDATED

    def test_unrelated_revision_leaves_blocks_untouched(self, caps):
        state, _ = drive(caps, ob.initial_state(), confirmed_zone_script())
        result = ob.revise_bar(state, bar_index=3, source_event_id="rev-3")
        # Index 3 is pruned out of the window and defines no block: a strict no-op.
        assert result.events == ()
        assert canonical_json(result.state) == canonical_json(state)

    def test_terminal_absorbs_a_revision(self, caps):
        script = confirmed_zone_script()
        script.append(break_step("k-013", SHORT, 13, 99))
        state, _ = drive(caps, ob.initial_state(), script)
        assert phase_of(state, OB1) == ob.BROKEN
        result = ob.revise_bar(state, bar_index=9, source_event_id="rev-9")
        assert phase_of(result.state, OB1) == ob.BROKEN
        assert state_events(list(result.events), OB1) == []

    def test_in_window_revision_resets_the_window(self, caps):
        state, _ = drive(caps, ob.initial_state(), confirmed_zone_script())
        result = ob.revise_bar(state, bar_index=12, source_event_id="rev-12")
        assert result.state["last_bar_index"] is None
        assert result.state["bars"] == {}


# ---------------------------------------------------------------------------------------------
# T10 — first touch consumed exactly once (multi-source + duplicate + restart replay)
# ---------------------------------------------------------------------------------------------


class TestT10FirstTouchOnce:
    def test_deeper_same_index_second_source_never_reconsumes(self, caps):
        script = confirmed_zone_script()
        script.append(bar_step(13, o=106, h=107, l=103, c=105, src="s1"))
        script.append(bar_step(13, o=106, h=107, l=101, c=104, src="s2"))
        state, events = drive(caps, ob.initial_state(), script)
        assert phase_of(state, OB1) == ob.MITIGATED       # the deeper source advanced stages
        touches = first_touches(events)
        assert len(touches) == 1
        assert touches[0]["source_id"] == "s1"
        assert state["blocks"][OB1]["first_touch_bar_identity"] == "s1-b13"

    def test_exact_duplicate_bar_delivery_is_a_no_op(self, caps):
        script = confirmed_zone_script()
        touch = bar_step(13, o=106, h=107, l=103, c=105)
        script.append(touch)
        state, _ = drive(caps, ob.initial_state(), script)
        replay = apply_step(caps, state, touch)
        assert replay.events == ()
        assert canonical_json(replay.state) == canonical_json(state)

    def test_restart_replay_holds_exactly_one_consumption(self, caps):
        script = confirmed_zone_script()
        script.append(bar_step(13, o=106, h=107, l=103, c=105))
        script.append(bar_step(14, o=104, h=106, l=101, c=103))
        base_state, base_events = drive(caps, ob.initial_state(), script)
        assert len(first_touches(base_events)) == 1
        for cut in range(len(script) + 1):
            head_state, head_events = drive(caps, ob.initial_state(), script[:cut])
            checkpoint = json.loads(canonical_json(head_state))
            tail_state, tail_events = drive(caps, checkpoint, script[cut:])
            assert len(first_touches(head_events + tail_events)) == 1
            assert canonical_json(tail_state) == canonical_json(base_state)


# ---------------------------------------------------------------------------------------------
# T11 — full bear mirror (the golden walk price-reflected around 204)
# ---------------------------------------------------------------------------------------------


def _mirror(value: int) -> int:
    return 204 - value


def mirrored_golden_script() -> list:
    steps: list = []
    for kind, kwargs in golden_script():
        if kind == "bar":
            bar = kwargs["env"]
            steps.append(bar_step(
                kwargs["bar_index"], o=_mirror(bar.open_ticks), h=_mirror(bar.low_ticks),
                l=_mirror(bar.high_ticks), c=_mirror(bar.close_ticks),
                src=kwargs["source_id"], identity=bar.bar_identity))
        elif kind == "disp":
            steps.append(("disp", {**kwargs, "direction": SHORT}))
        elif kind == "break":
            steps.append(("break", {
                **kwargs,
                "direction": SHORT if kwargs["direction"] == LONG else LONG,
                "close_ticks": _mirror(kwargs["close_ticks"])}))
        else:  # pragma: no cover - the golden script carries no other faces
            steps.append((kind, kwargs))
    return steps


class TestT11BearMirror:
    def test_the_bear_walk_is_the_exact_mirror_of_the_bull_walk(self, caps):
        bull_state, bull_events = drive(caps, ob.initial_state(), golden_script())
        bear_state, bear_events = drive(caps, ob.initial_state(), mirrored_golden_script())
        bull_row = bull_state["blocks"][OB1]
        bear_row = bear_state["blocks"][OB1]
        assert bear_row["direction"] == SHORT
        assert bear_row["origin_bar_index"] == bull_row["origin_bar_index"] == 9
        # bear zone [O_o, H_o] is the reflected bull zone [L_o, O_o].
        assert bear_row["zone_low_ticks"] == _mirror(bull_row["zone_high_ticks"])
        assert bear_row["zone_high_ticks"] == _mirror(bull_row["zone_low_ticks"])
        assert bear_row["far_edge_ticks"] == _mirror(bull_row["far_edge_ticks"])
        assert bear_row["proximal_edge_ticks"] == _mirror(bull_row["proximal_edge_ticks"])
        assert bear_row["phase"] == bull_row["phase"] == ob.BROKEN
        assert bear_row["max_depth"] == bull_row["max_depth"] == [3, 4]
        assert bear_state["bos_consumed"] == bull_state["bos_consumed"]
        bull_trail = [(ev["to_phase"], ev["bar_index"], ev["reason"])
                      for ev in state_events(bull_events)]
        bear_trail = [(ev["to_phase"], ev["bar_index"], ev["reason"])
                      for ev in state_events(bear_events)]
        assert bear_trail == bull_trail
        bull_touch, = first_touches(bull_events)
        bear_touch, = first_touches(bear_events)
        assert bear_touch["depth"] == bull_touch["depth"] == [1, 4]


# ---------------------------------------------------------------------------------------------
# T12 — restart parity at EVERY cut point (checkpoints round-trip through canonical bytes)
# ---------------------------------------------------------------------------------------------


def canonical_stream(state: dict, events: list) -> bytes:
    return canonical_json({"state": state, "events": events})


class TestT12RestartParity:
    def _sweep(self, caps: dict, script: list) -> None:
        base_state, base_events = drive(caps, ob.initial_state(), script)
        baseline = canonical_stream(base_state, base_events)
        for cut in range(len(script) + 1):
            head_state, head_events = drive(caps, ob.initial_state(), script[:cut])
            checkpoint = json.loads(canonical_json(head_state))
            tail_state, tail_events = drive(caps, checkpoint, script[cut:])
            assert canonical_stream(tail_state, head_events + tail_events) == baseline

    def test_golden_walk_restart_parity(self, caps):
        self._sweep(caps, golden_script())

    def test_gap_and_revision_walk_restart_parity(self, caps):
        script = confirmed_zone_script()
        script.append(bar_step(13, o=106, h=107, l=103, c=105))
        script.append(("revise", {"bar_index": 9, "source_event_id": "rev-9"}))
        script.append(("gap", {"bar_index": None, "reason": ob.GAP_BAR}))
        script += [
            bar_step(20, o=100, h=105, l=99, c=104),
            bar_step(21, o=103, h=104, l=100, c=101),
            bar_step(22, o=100, h=105, l=99, c=104),
            disp_step("d-022", LONG, 22),
        ]
        self._sweep(caps, script)

    def test_sequence_gap_walk_restart_parity(self, caps):
        script = confirmed_zone_script()
        script.append(bar_step(15, o=106, h=107, l=105, c=106))  # index skip
        script.append(bar_step(16, o=103, h=104, l=100, c=101))
        script.append(bar_step(17, o=100, h=105, l=99, c=104))
        script.append(disp_step("d-017", LONG, 17))
        self._sweep(caps, script)


# ---------------------------------------------------------------------------------------------
# Availability (§1.4) — a zone confirmed at bar j is never tested by bar j itself
# ---------------------------------------------------------------------------------------------


class TestAvailability:
    def test_the_confirming_bar_cannot_touch_the_zone_it_confirmed(self, caps):
        script = golden_script()[:14]                       # through bar 11
        script.append(break_step("k-012", LONG, 12, 112))
        # Bar 12 dives INTO the zone — but its bucket starts before the zone availability
        # (max of displacement + BOS availability = bucket(13)), so it may not test it.
        script.append(bar_step(12, o=110, h=113, l=101, c=112))
        state, events = drive(caps, ob.initial_state(), script)
        assert phase_of(state, OB1) == ob.FRESH
        assert first_touches(events) == []
        # The very next bar may.
        result = apply_step(caps, state, bar_step(13, o=106, h=107, l=103, c=105))
        assert [ev for ev in result.events if ev.get("event_kind") == ob.FIRST_TOUCH_KIND]

    def test_zone_availability_is_the_max_of_both_availabilities(self, caps):
        state, _ = drive(caps, ob.initial_state(), confirmed_zone_script())
        row = state["blocks"][OB1]
        assert row["displacement_availability_us"] == bucket(11)
        assert row["availability_time_us"] == bucket(13)    # the BOS availability dominates


# ---------------------------------------------------------------------------------------------
# Intake-order + identity law (the declared stream contract, enforced structurally)
# ---------------------------------------------------------------------------------------------


class TestIntakeOrderLaw:
    def test_displacement_must_register_at_its_trigger_bar(self, caps):
        state, _ = drive(caps, ob.initial_state(), pending_script(upto=2)[:-1])
        with pytest.raises(StructureLawError, match=ob.TRIGGER_OUT_OF_ORDER):
            apply_step(caps, state, disp_step("d-x", LONG, 1))   # g != last (2)
        with pytest.raises(StructureLawError, match=ob.TRIGGER_OUT_OF_ORDER):
            apply_step(caps, state, disp_step("d-y", LONG, 3))   # a future trigger
        with pytest.raises(StructureLawError, match=ob.TRIGGER_OUT_OF_ORDER):
            apply_step(caps, ob.initial_state(), disp_step("d-z", LONG, 0))  # cold machine

    def test_duplicate_displacement_registration_is_idempotent(self, caps):
        script = pending_script(upto=2)
        state, _ = drive(caps, ob.initial_state(), script)
        replay = apply_step(caps, state, disp_step("d-002", LONG, 2))
        assert replay.events == ()
        assert canonical_json(replay.state) == canonical_json(state)
        with pytest.raises(StructureLawError, match=ob.INPUT_IDENTITY_CONFLICT):
            apply_step(caps, state, ("disp", {
                "displacement_id": "d-002", "direction": SHORT, "trigger_bar_index": 2,
                "availability_time_us": bucket(3), "source_event_id": "ev-d-002"}))

    def test_break_must_register_before_its_own_bar(self, caps):
        state, _ = drive(caps, ob.initial_state(), pending_script(upto=2))
        with pytest.raises(StructureLawError, match=ob.BREAK_OUT_OF_ORDER):
            apply_step(caps, state, break_step("k-2", LONG, 2, 120))   # j == last
        with pytest.raises(StructureLawError, match=ob.BREAK_OUT_OF_ORDER):
            apply_step(caps, state, break_step("k-4", LONG, 4, 120))   # j > last + 1
        with pytest.raises(StructureLawError, match=ob.BREAK_OUT_OF_ORDER):
            apply_step(caps, ob.initial_state(), break_step("k-0", LONG, 0, 120))

    def test_out_of_order_bar_refuses_unless_an_identical_recorded_duplicate(self, caps):
        script = pending_script(upto=2)
        state, _ = drive(caps, ob.initial_state(), script)
        replayed = apply_step(caps, state, bar_step(1, o=103, h=104, l=100, c=101))
        assert replayed.events == ()
        assert canonical_json(replayed.state) == canonical_json(state)
        with pytest.raises(StructureLawError, match=ob.BAR_OUT_OF_ORDER):
            apply_step(caps, state, bar_step(1, o=103, h=104, l=100, c=102))
        with pytest.raises(StructureLawError, match=ob.INPUT_IDENTITY_CONFLICT):
            apply_step(caps, state, bar_step(2, o=100, h=105, l=99, c=103))

    def test_v1_shaped_state_never_blends_into_v2(self, caps):
        v1_state = {"last_event_id": None, "order_blocks": {}}
        with pytest.raises(StructureLawError, match=ob.STATE_VERSION_MISMATCH):
            apply_step(caps, v1_state, bar_step(0, o=100, h=105, l=99, c=104))


# ---------------------------------------------------------------------------------------------
# §1.2 — int64 wire-width boundary vectors (the formula's largest persisted products)
# ---------------------------------------------------------------------------------------------


class TestInt64Boundary:
    def test_claim_deadline_at_int64_max_passes(self, caps):
        g = INT64_MAX - H_BOS
        script = [
            bar_step(g - 1, o=103, h=104, l=100, c=101, bucket_us=1_000),
            bar_step(g, o=100, h=105, l=99, c=104, bucket_us=2_000),
            disp_step("d-max", LONG, g, avail_us=3_000),
        ]
        state, _ = drive(caps, ob.initial_state(), script)
        assert state["blocks"]["ob:d-max"]["claim_deadline_bar_index"] == INT64_MAX

    def test_claim_deadline_one_beyond_quarantines(self, caps):
        g = INT64_MAX - H_BOS + 1
        script = [
            bar_step(g - 1, o=103, h=104, l=100, c=101, bucket_us=1_000),
            bar_step(g, o=100, h=105, l=99, c=104, bucket_us=2_000),
        ]
        state, _ = drive(caps, ob.initial_state(), script)
        before = canonical_json(state)
        with pytest.raises(QuarantineOverflow) as info:
            apply_step(caps, state, disp_step("d-over", LONG, g, avail_us=3_000))
        assert info.value.formula_id == "F12"
        assert info.value.field == "claim_deadline_bar_index"
        assert canonical_json(state) == before  # fail closed: nothing mutated, nothing emitted

    def test_ttl_deadline_overflow_at_confirmation_fails_closed(self, caps):
        g = INT64_MAX - 10
        script = [
            bar_step(g - 1, o=103, h=104, l=100, c=101, bucket_us=1_000),
            bar_step(g, o=100, h=105, l=99, c=104, bucket_us=2_000),
            disp_step("d-ttl", LONG, g, avail_us=3_000),
            break_step("k-ttl", LONG, g + 1, 120, avail_us=4_000),  # j + TTL overflows int64
        ]
        state, events = drive(caps, ob.initial_state(), script)
        assert phase_of(state, "ob:d-ttl") == ob.INVALIDATED
        assert state["blocks"]["ob:d-ttl"]["terminal_reason"] == ob.QUARANTINE_OVERFLOW_REASON
        # The claim happened: k is consumed (an overflow never widens later confirmations).
        assert state["bos_consumed"] == {"k-ttl": "ob:d-ttl"}
        records = [ev for ev in events if ev.get("reason_code") == "QUARANTINE_OVERFLOW"]
        assert len(records) == 1
        assert records[0]["field"] == "ttl_deadline_bar_index"

    def _confirmed_wide_zone(self, caps, *, origin_low: int, origin_open: int) -> dict:
        script = [
            bar_step(0, o=origin_open, h=origin_open, l=origin_low, c=origin_low),
            bar_step(1, o=0, h=10, l=-10, c=5),
            disp_step("d-wide", LONG, 1),
            break_step("k-wide", LONG, 2, 6),
            bar_step(2, o=0, h=10, l=-10, c=6),
        ]
        state, _ = drive(caps, ob.initial_state(), script)
        assert phase_of(state, "ob:d-wide") == ob.FRESH
        return state

    def test_depth_pair_at_int64_max_height_passes(self, caps):
        state = self._confirmed_wide_zone(caps, origin_low=0, origin_open=INT64_MAX)
        result = apply_step(caps, state, bar_step(3, o=2, h=3, l=1, c=2))
        blocks = result.state["blocks"]
        assert blocks["ob:d-wide"]["max_depth"] == [INT64_MAX - 1, INT64_MAX]
        assert blocks["ob:d-wide"]["phase"] == ob.MITIGATED

    def test_depth_pair_beyond_int64_quarantines_and_invalidates(self, caps):
        state = self._confirmed_wide_zone(
            caps, origin_low=-INT64_MAX - 1, origin_open=INT64_MAX)
        result = apply_step(
            caps, state, bar_step(3, o=INT64_MAX - 1, h=INT64_MAX, l=INT64_MAX - 1,
                                  c=INT64_MAX - 1))
        blocks = result.state["blocks"]
        assert blocks["ob:d-wide"]["phase"] == ob.INVALIDATED
        assert blocks["ob:d-wide"]["terminal_reason"] == ob.QUARANTINE_OVERFLOW_REASON
        records = [ev for ev in result.events
                   if ev.get("reason_code") == "QUARANTINE_OVERFLOW"]
        assert len(records) == 1


# ---------------------------------------------------------------------------------------------
# PROPOSED_MUST_RATIFY — mechanisms + named refusals; the proposed values never hardcoded
# ---------------------------------------------------------------------------------------------


class TestProposedMustRatify:
    def test_missing_ttl_capability_is_the_named_blocked_on_ratify(self, caps):
        capless = {pid: caps[pid] for pid in caps if pid != ob.PARAM_TTL}
        state = ob.initial_state()
        before = canonical_json(state)
        with pytest.raises(ob.BlockedOnRatify) as info:
            apply_step(capless, state, bar_step(0, o=100, h=105, l=99, c=104))
        assert str(info.value) == "BLOCKED_ON_RATIFY(OB_TTL_BARS)"
        assert canonical_json(state) == before
        with pytest.raises(ob.BlockedOnRatify):
            ob.register_displacement(
                capless, state, displacement_id="d", direction=LONG, trigger_bar_index=0,
                availability_time_us=1, source_event_id="ev")
        with pytest.raises(ob.BlockedOnRatify):
            ob.register_break(
                capless, state, bos_occurrence_id="k", direction=LONG, break_bar_index=0,
                close_ticks=1, availability_time_us=1, source_event_id="ev")

    def test_repository_mitigation_rule_string_refuses_by_name(self, caps):
        bad = variant(caps, **{ob.PARAM_MITIGATION: REPO_MITIGATION_RULE})
        with pytest.raises(StructureLawError, match=ob.BINDING_VALUE_NOT_RATIONAL):
            apply_step(bad, ob.initial_state(), bar_step(0, o=100, h=105, l=99, c=104))

    def test_repository_break_rule_prose_and_v1_atr_string_refuse_by_name(self, caps):
        for unratified in (REPO_BREAK_RULE, V1_ATR_BUFFER_RULE):
            bad = variant(caps, **{ob.PARAM_BREAK_BUFFER: unratified})
            with pytest.raises(StructureLawError, match=ob.BINDING_VALUE_NOT_INTEGER):
                apply_step(bad, ob.initial_state(), bar_step(0, o=100, h=105, l=99, c=104))

    def test_foreign_opposing_predicate_refuses_by_name(self, caps):
        bad = variant(caps, **{ob.PARAM_OPPOSING: "bull:close<=open; bear:close>=open"})
        with pytest.raises(StructureLawError, match=ob.BINDING_VALUE_NOT_DECLARED):
            apply_step(bad, ob.initial_state(), bar_step(0, o=100, h=105, l=99, c=104))

    @pytest.mark.parametrize("parameter_id,value,token", [
        (ob.PARAM_LOOKBACK, "0", ob.BINDING_VALUE_NOT_INTEGER),
        (ob.PARAM_LOOKBACK, True, ob.BINDING_VALUE_NOT_INTEGER),
        (ob.PARAM_BOS_HORIZON, "0", ob.BINDING_VALUE_NOT_INTEGER),
        (ob.PARAM_BREAK_BUFFER, "0", ob.BINDING_VALUE_NOT_INTEGER),   # F09 b >= 1 mirrored
        (ob.PARAM_TTL, "0", ob.BINDING_VALUE_NOT_INTEGER),
        (ob.PARAM_MITIGATION, "0/2", ob.BINDING_VALUE_NOT_RATIONAL),  # fraction must be > 0
        (ob.PARAM_MITIGATION, "3/2", ob.BINDING_VALUE_NOT_RATIONAL),  # and <= 1
        (ob.PARAM_MITIGATION, True, ob.BINDING_VALUE_NOT_RATIONAL),
    ])
    def test_structural_domain_floors_refuse_by_name(self, caps, parameter_id, value, token):
        bad = variant(caps, **{parameter_id: value})
        with pytest.raises(StructureLawError, match=token):
            apply_step(bad, ob.initial_state(), bar_step(0, o=100, h=105, l=99, c=104))

    def test_the_proposed_values_are_never_hardcoded_in_the_machine(self):
        import ast

        source = pathlib.Path(ob.__file__).read_text(encoding="utf-8")
        # R-F12 acceptance scan: no body-size output vocabulary survives anywhere in v2.
        assert "notional" not in source.lower()
        # The mechanism is capability-fed (a different TTL changes behavior — T7); the module
        # carries NO executable copy of the proposed numbers (192, or a 1/2 fraction literal).
        # Prose (docstrings/comments) may NAME the proposal; code may not evaluate it.
        int_constants = {
            node.value for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Constant) and type(node.value) is int
        }
        assert 192 not in int_constants
        string_constants = {
            node.value for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        assert "192" not in string_constants
        assert "1/2" not in string_constants

    def test_repository_f12_rows_stay_blocked(self, real_registry):
        for binding_id in _F12_ROWS:
            row = real_registry.row(binding_id)
            assert row["status"] == "BLOCKED_BINDING_V2_MIGRATION"
            assert row["lifecycle_status"] == "BLOCKED"

    def test_no_f12_capability_can_be_minted_from_the_repository_registry(self, real_registry):
        bindings._reset_trust_registry_pin_for_tests()
        bindings._reset_acceptance_memo_for_tests()
        try:
            pk = "ab" * 32
            trust = {OWNER_KID: {"key_id": OWNER_KID, "identity": "owner@triad",
                                 "role": "AUTHORITY_OWNER", "algorithm": "ed25519",
                                 "public_key_hex": pk, "revoked": False}}
            raw = json.dumps(trust, sort_keys=True).encode("utf-8")
            bindings.pin_trust_registry_digest(sha256_hex(raw))
            unsigned = bindings.build_sealed_bundle(
                real_registry, repository=REPOSITORY, environment=ENVIRONMENT,
                valid_from=VALID_FROM, valid_to=VALID_TO,
                trust_registry_digest=sha256_hex(raw), signer_set=[OWNER_KID])
            signing = bindings.sealed_bundle_signing_bytes(
                canonical_root_digest=unsigned.canonical_root_digest, scope=unsigned.scope,
                valid_from=unsigned.valid_from, valid_to=unsigned.valid_to)
            sig = hashlib.sha512(signing + bytes.fromhex(pk)).hexdigest()
            bundle = dataclasses.replace(
                unsigned, signatures=[{"key_id": OWNER_KID, "signature_hex": sig}])

            def verify(public_key_hex: str, message: bytes, signature_hex: str) -> bool:
                return signature_hex == hashlib.sha512(
                    message + bytes.fromhex(public_key_hex)).hexdigest()

            ctx = bindings.VerificationContext(
                trust=trust, trust_registry_bytes=raw, now_us=NOW_US,
                process_scope={"repository": REPOSITORY, "environment": ENVIRONMENT},
                verify_fn=verify)
            with pytest.raises(bindings.BlockedBindingIncomplete) as info:
                transition.require_bundle(bundle, ob.PARAM_LOOKBACK, formula_id="F12", ctx=ctx)
            assert "BLOCKED_BINDING_INCOMPLETE:F12" in str(info.value)
        finally:
            bindings._reset_trust_registry_pin_for_tests()
            bindings._reset_acceptance_memo_for_tests()

    def test_ratified_law_rows_are_pinned(self):
        assert ob.OB_ORIGIN_TIE == "LATEST_THEN_MIN_SOURCE_ID"
        assert ob.ONE_BOS_ONE_LINEAGE is True
        assert ob.DECLARED_OPPOSING_PREDICATE == "bull:close<open; bear:close>open"
        assert ob.REQUIRED_PARAMETER_IDS == (
            "PAR-047", "PAR-160", "PAR-161", "PAR-162", "PAR-163", "OB_TTL_BARS")


# ---------------------------------------------------------------------------------------------
# §C.3 adversarial boundary — hand-built objects are rejected BEFORE any state transition
# ---------------------------------------------------------------------------------------------


class TestAdversarialBoundary:
    def test_hand_built_dict_caps_are_rejected_before_any_transition(self, caps):
        state, _ = drive(caps, ob.initial_state(), pending_script(upto=2))
        before = canonical_json(state)
        forged = {pid: {"value": 8} for pid in ob.REQUIRED_PARAMETER_IDS}
        with pytest.raises(bindings.CapabilityForgeryError):
            apply_step(forged, state, bar_step(3, o=100, h=105, l=99, c=104))
        forged_ints = dict.fromkeys(ob.REQUIRED_PARAMETER_IDS, 8)
        with pytest.raises(bindings.CapabilityForgeryError):
            ob.register_displacement(
                forged_ints, state, displacement_id="d", direction=LONG,
                trigger_bar_index=2, availability_time_us=1, source_event_id="ev")
        with pytest.raises(bindings.CapabilityForgeryError):
            ob.register_break(
                forged_ints, state, bos_occurrence_id="k", direction=LONG,
                break_bar_index=3, close_ticks=1, availability_time_us=1,
                source_event_id="ev")
        with pytest.raises(bindings.CapabilityForgeryError):
            ob.evaluate("not-a-mapping", vbar("x", o=100, h=105, l=99, c=104), state,
                        source_id="s1", bar_index=3, bucket_start_us=bucket(3))
        assert canonical_json(state) == before

    def test_a_subclass_capability_is_a_forgery(self, caps):
        class Forged(bindings.VerifiedCapability):
            pass

        real = caps[ob.PARAM_LOOKBACK]
        fields = {f.name: getattr(real, f.name) for f in dataclasses.fields(real)}
        forged_map = dict(caps)
        forged_map[ob.PARAM_LOOKBACK] = Forged(**fields)
        with pytest.raises(bindings.CapabilityForgeryError):
            apply_step(forged_map, ob.initial_state(), bar_step(0, o=100, h=105, l=99, c=104))

    def test_a_foreign_formula_capability_is_a_forgery(self, caps):
        forged_map = dict(caps)
        forged_map[ob.PARAM_LOOKBACK] = dataclasses.replace(
            caps[ob.PARAM_LOOKBACK], formula_id="F13")
        with pytest.raises(bindings.CapabilityForgeryError):
            apply_step(forged_map, ob.initial_state(), bar_step(0, o=100, h=105, l=99, c=104))

    def test_a_mismatched_key_capability_is_a_forgery(self, caps):
        forged_map = dict(caps)
        forged_map[ob.PARAM_LOOKBACK] = caps[ob.PARAM_BOS_HORIZON]
        with pytest.raises(bindings.CapabilityForgeryError):
            apply_step(forged_map, ob.initial_state(), bar_step(0, o=100, h=105, l=99, c=104))

    def test_an_unknown_extra_capability_is_a_forgery(self, caps):
        forged_map = dict(caps)
        forged_map["PAR-999"] = caps[ob.PARAM_LOOKBACK]
        with pytest.raises(bindings.CapabilityForgeryError):
            apply_step(forged_map, ob.initial_state(), bar_step(0, o=100, h=105, l=99, c=104))

    def test_a_raw_dict_env_is_rejected_before_any_transition(self, caps):
        state = ob.initial_state()
        before = canonical_json(state)
        with pytest.raises(ob.EnvelopeContractError):
            ob.evaluate(caps, raw_bar("x", o=100, h=105, l=99, c=104), state,
                        source_id="s1", bar_index=0, bucket_start_us=bucket(0))
        assert canonical_json(state) == before

    def test_a_validated_bar_subclass_env_is_rejected(self, caps):
        class ForgedBar(e01.ValidatedBar):
            pass

        real = vbar("x", o=100, h=105, l=99, c=104)
        forged = ForgedBar(**{f.name: getattr(real, f.name)
                              for f in dataclasses.fields(real)})
        with pytest.raises(ob.EnvelopeContractError):
            ob.evaluate(caps, forged, ob.initial_state(), source_id="s1", bar_index=0,
                        bucket_start_us=bucket(0))


# ---------------------------------------------------------------------------------------------
# Version discipline (§1.5) — retirement banner + the stem-preserving successor face
# ---------------------------------------------------------------------------------------------


class TestVersionDiscipline:
    def test_v1_module_carries_the_module_docstring_withdrawal_banner(self):
        import triad_origin.structures.order_block_registry as v1
        assert v1.__doc__ is not None
        assert v1.__doc__.startswith(
            "RETIRED_DEFECTIVE{defect_ref=TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12 R-F12}")

    def test_v1_bytes_preserved_the_larger_body_tie_is_untouched(self):
        # §1.5: the defective logic is retired, never edited — v1's larger-body equal-offset
        # tie (the R-F12 defect (1)) must still be byte-alive under its own version tag.
        from triad_origin.structures import order_block_registry as v1
        small = {"source_id": "s_a", "offset": 1, "open_ticks": 104, "close_ticks": 103,
                 "high_ticks": 105, "low_ticks": 100}
        large = {"source_id": "s_b", "offset": 1, "open_ticks": 110, "close_ticks": 100,
                 "high_ticks": 111, "low_ticks": 99}
        winner = v1._select_origin(
            [v1._candidate_geometry(small), v1._candidate_geometry(large)], "LONG", 8)
        assert winner["source_id"] == "s_b"   # v1: larger body wins — deleted in v2

    def test_successor_face_re_exports_the_one_implementation(self):
        assert face.evaluate is ob.evaluate
        assert face.initial_state is ob.initial_state
        assert face.register_displacement is ob.register_displacement
        assert face.register_break is ob.register_break
        assert face.note_gap is ob.note_gap
        assert face.revise_bar is ob.revise_bar
        assert face.VERSION == ob.VERSION == "ob.displacement_bos.v2"
        assert ob.RETIRED_PREDECESSOR == "ob.displacement_bos.v1"

    def test_v2_events_carry_the_semantic_version(self, caps):
        _state, events = drive(caps, ob.initial_state(), golden_script())
        for ev in state_events(events) + first_touches(events):
            assert ev["formula"] == "F12"
            assert ev["formula_version"] == "ob.displacement_bos.v2"


# ---------------------------------------------------------------------------------------------
# ACCEPTANCE — property: |{ob : ob.bos_id = k}| <= 1 for every k over random tapes
# ---------------------------------------------------------------------------------------------


class TestAcceptanceProperty:
    TAPES = 300

    def test_random_tapes_hold_the_one_bos_one_lineage_invariant(self, caps):
        rng = random.Random(0xF12001)
        total_confirms = 0
        for tape_index in range(self.TAPES):
            state = ob.initial_state()
            events: list = []
            price = 10_000
            disp_n = 0
            break_n = 0
            i = 0
            for _step in range(rng.randrange(8, 28)):
                # Maybe an accepted break occurrence derived from the UPCOMING bar.
                if i > 0 and rng.randrange(100) < 35:
                    break_n += 1
                    direction = LONG if rng.getrandbits(1) else SHORT
                    close = price + rng.randrange(-60, 61)
                    result = apply_step(caps, state, break_step(
                        f"k{tape_index}-{break_n}", direction, i, close))
                    state = result.state
                    events.extend(result.events)
                move = rng.randrange(-30, 31)
                o = price
                c = price + move
                lo = min(o, c) - rng.randrange(0, 20)
                hi = max(o, c) + rng.randrange(0, 20)
                result = apply_step(caps, state, bar_step(i, o=o, h=hi, l=lo, c=c))
                state = result.state
                events.extend(result.events)
                price = c
                if rng.randrange(100) < 30:
                    disp_n += 1
                    direction = LONG if rng.getrandbits(1) else SHORT
                    result = apply_step(caps, state, disp_step(
                        f"d{tape_index}-{disp_n}", direction, i))
                    state = result.state
                    events.extend(result.events)
                i += 1
            confirms = [ev for ev in state_events(events)
                        if ev["to_phase"] == ob.CONFIRMED_BY_BOS]
            total_confirms += len(confirms)
            by_bos: dict = {}
            for ev in confirms:
                k = ev["lineage"]["bos_occurrence_id"]
                by_bos.setdefault(k, []).append(ev["ob_id"])
            for k, obs in by_bos.items():
                assert len(obs) <= 1, f"BOS {k} confirmed {obs}"
            consumed = state["bos_consumed"]
            assert len(set(consumed.values())) == len(consumed)  # 1:1 both directions
            assert {ev["lineage"]["bos_occurrence_id"]: ev["ob_id"]
                    for ev in confirms} == consumed
            for ob_id, row in state["blocks"].items():
                if row["bos_occurrence_id"] is not None:
                    assert consumed[row["bos_occurrence_id"]] == ob_id
        assert total_confirms > self.TAPES // 20, f"only {total_confirms} confirmations"
