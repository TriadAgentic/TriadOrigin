"""R-F11 ``displacement.closed_path.v1`` (RETAINED) — the full VALID_BAR hardening battery.

Spec vectors T1-T9 (TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12 R-F11) + GV-010 (incl. its
embedded rc2 source vector) + the kept pre-repair laws (earliest-wins, gap, NO_ATR, supersede,
mirror, restart parity, never-float) re-authored through the §C.3 boundary: ``evaluate(caps,
env, state, ...)`` with REAL minted capabilities (the ``tests/structures/test_swing_dc_v2.py``
Ed25519 pattern) and E01-validated bars. The GV-010 boundary posture
(``BLOCKED_UNTIL_PAR-158_RATIFIED``) is proven on the UNMODIFIED repository registry: no F11
capability can be minted, and the machine's named refusal is ``BLOCKED_ON_RATIFY(<param>)``.

Dossier dispositions of pre-repair tests that CONTRADICTED the spec:

* ``test_bar_close_above_high_is_refused`` / ``test_bar_close_below_low_is_refused`` pinned the
  Phase-0 RAISE — the spec's T1/T2 failure mode is a QUARANTINE_INVALID_BAR record + the origin
  expiring unqualified (same class as gap); rewritten below as the T1/T2 vectors.
* the close-location boundary tests placed bar opens OUTSIDE ``[low, high]`` (the deliberate
  Phase-0 carve-out); the repair spec takes the open-in-range decision ("invalid bars were
  never contract-valid inputs"), so those vectors are re-authored with in-range opens that
  still isolate the boundary exactly.
* ratio pairs are now emitted REDUCED (§1.3 names body_ratio/close_loc verbatim), so the
  boundary assertions read the reduced pairs.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import bindings, e01_interface as e01, transition  # noqa: E402
from triad_origin.canonical import INT64_MAX, INT64_MIN, canonical_json, sha256_hex  # noqa: E402
from triad_origin.exact import QuarantineOverflow  # noqa: E402
from triad_origin.structures import common, displacement as disp  # noqa: E402

OWNER_KID = "k-owner-f11"
OWNER_PK = "cd" * 32
REPOSITORY = "TriadOrigin"
ENVIRONMENT = "OFF"
VALID_FROM = 1_000_000
VALID_TO = 9_000_000
NOW_US = 2_000_000

F11_ROW_IDS = ("FPB-0021", "FPB-0065", "FPB-0066", "FPB-0067")

# THE PAR-158 TRANSPORT INTERLOCK (the PAR-036 precedent, pinned by TestBlockedOnRatify below):
# the declared PAR-158 byte-string ``max(5,ceil(ATR14_before_origin*3/2))`` contains ``*``, and
# the B01C-BIND-04 wildcard-sentinel law refuses ANY ``*`` inside an ACTIVE row's resolved
# fields — at registry load AND at sealed-bundle acceptance. The fixture therefore mints REAL
# capabilities (full build_sealed_bundle + require_bundle, real Ed25519) over a clearly-labeled
# sentinel-free TEST transport value for PAR-158 only, then rebuilds that one handle to carry
# the exact declared byte-string (C.1 law: construction of the type is unrestricted —
# acceptance is what is guarded; the machine's own boundary law is proven adversarially in
# TestBoundaryRejections). PAR-046/PAR-157/PAR-159 declared values are sentinel-free and ride
# the mint verbatim.
TEST_TRANSPORT_VALUE = (
    "TEST-RATIFIED-TRANSPORT max(5,ceil(ATR14_before_origin 3/2)) (sentinel-free)")


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


def _ratified_doc(par158_value: str = TEST_TRANSPORT_VALUE) -> dict:
    """The repository registry with the four F11 rows flipped ACTIVE — TEST-only posture."""
    doc = json.loads(pathlib.Path(bindings.DEFAULT_REGISTRY_PATH).read_text(encoding="utf-8"))
    for row in doc["rows"]:
        if row["binding_id"] not in F11_ROW_IDS:
            continue
        declared = par158_value if row["parameter_id"] == "PAR-158" else row["declared_value"]
        row.update({
            "status": "ACTIVE",
            "lifecycle_status": "ACTIVE",
            "cardinality": "EXACTLY_ONE",
            "migration_state": "NOT_APPLICABLE",
            "declared_value": declared,
            "semantic_slot": f"f11_{row['parameter_id'].lower().replace('-', '_')}_TEST",
            "condition": "TEST-RATIFIED stand-in for the F11 ratification ceremony",
            "activation_scope": f"TEST;F11;{row['parameter_id']};displacement vectors only",
            "precedence": "TEST_FIXTURE",
            "consumer": "ORIGIN(F11)",
            "consuming_wiring_ids": "W03",
            "disposition_reason":
                "TEST-only ratified posture; the repository rows stay BLOCKED.",
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
def minted_caps(ratified_registry):
    """REAL VerifiedCapability handles for all four F11 parameters (real Ed25519 mint)."""
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
        out = {}
        for parameter_id in disp.REQUIRED_PARAMETERS:
            cap = transition.require_bundle(
                bundle, parameter_id, formula_id="F11", ctx=ctx)
            assert type(cap) is bindings.VerifiedCapability
            assert cap.formula_id == "F11"
            assert cap.parameter_id == parameter_id
            out[parameter_id] = cap
        assert out[disp.PARAMETER_MIN_MOVE].value == TEST_TRANSPORT_VALUE
        assert out[disp.PARAMETER_BODY_FRACTION].value == "13/20"
        assert out[disp.PARAMETER_HORIZON].value == "3"
        assert out[disp.PARAMETER_CLOSE_LOCATION].value == "4/5"
        return out
    finally:
        bindings._reset_trust_registry_pin_for_tests()
        bindings._reset_acceptance_memo_for_tests()


@pytest.fixture(scope="module")
def caps(minted_caps):
    """The behavior-vector capability set: the REAL minted PAR-158 handle re-carrying the
    exact declared byte-string (see the transport-interlock note above)."""
    out = dict(minted_caps)
    out[disp.PARAMETER_MIN_MOVE] = dataclasses.replace(
        minted_caps[disp.PARAMETER_MIN_MOVE], value=common.DECLARED_DISPLACEMENT_MIN_MOVE)
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
# Bar fixtures (E01-validated — the ONLY lawful construction path) + the shared driver
# ---------------------------------------------------------------------------------------------


def raw_bar(identity: str, open_ticks: int, close_ticks: int, high_ticks: int,
            low_ticks: int, *, base_volume: int = 1, quote_volume: int = 1,
            trade_count: int = 1) -> dict:
    return {
        "bar_identity": identity, "metadata_revision": "r1",
        "open_ticks": open_ticks, "close_ticks": close_ticks,
        "high_ticks": high_ticks, "low_ticks": low_ticks,
        "base_volume": base_volume, "quote_volume": quote_volume,
        "trade_count": trade_count,
    }


def raw_origin_bar(identity: str, open_ticks: int) -> dict:
    """A VALID origin bar around ``open_ticks`` (the origin's own OHLC beyond its open is
    immaterial to the formula — move is measured from the origin OPEN)."""
    return raw_bar(identity, open_ticks, open_ticks + 10, open_ticks + 30, open_ticks)


def origin(identity: str, index: int, open_ticks: int, atr: int | None = 10) -> tuple:
    return ("ORIGIN", raw_origin_bar(identity, open_ticks), index, atr)


def bar(identity: str, index: int, open_ticks: int, close_ticks: int, high_ticks: int,
        low_ticks: int) -> tuple:
    return ("BAR", raw_bar(identity, open_ticks, close_ticks, high_ticks, low_ticks), index)


def run_f11(caps, steps, state=None):
    """Fold the ONE transition implementation over steps — live == replay."""
    st = state if state is not None else disp.initial_state()
    events: list = []
    for step in steps:
        if step[0] == "ORIGIN":
            _, raw, index, atr = step
            result = disp.evaluate(
                caps, e01.require_valid_bar(raw), st,
                role=disp.ROLE_ORIGIN, bar_index=index, atr14_before_origin_ticks=atr)
        else:
            _, raw, index = step
            result = disp.evaluate(
                caps, e01.require_valid_bar(raw), st,
                role=disp.ROLE_BAR, bar_index=index)
        events.extend(result.events)
        st = result.state
    return st, events


def qualified(events):
    return [e for e in events if e.get("event_kind") == disp.DISPLACEMENT_QUALIFIED]


def abstentions(events):
    return [e for e in events if e.get("event_kind") == "NAMED_ABSTENTION"]


def quarantines(events):
    return [e for e in events if e.get("event_kind") == "QUARANTINE"]


def forged_bar(**overrides) -> e01.ValidatedBar:
    """A hand-built envelope object (dataclass construction is unrestricted by design) — the
    adversarial channel the module's local §1.1 defense-in-depth assertion exists for."""
    fields = {
        "bar_identity": "forged", "metadata_revision": "r1",
        "open_ticks": 0, "high_ticks": 20, "low_ticks": 0, "close_ticks": 16,
        "base_volume": 1, "quote_volume": 1, "trade_count": 1,
    }
    fields.update(overrides)
    return e01.ValidatedBar(**fields)


# Non-qualifying filler bars exhaust the declared PAR-157 horizon (H = 3). Fillers are
# zero-range bars with C == O — the T7 shape, which can NEVER qualify in either direction
# regardless of the origin open (so any boundary vector stays isolated).
def window_fill(start_index: int, first: tuple | None = None) -> list:
    steps = [] if first is None else [first]
    index = start_index + len(steps)
    while len(steps) < 3:
        steps.append(bar(f"fill{index}", index, 7, 7, 7, 7))
        index += 1
    return steps


# ---------------------------------------------------------------------------------------------
# GV-010 (T3/T4 on the move axis): D_ticks = max(5, ceil(3*10/2)) = 15; 14 fails, 15 passes
# ---------------------------------------------------------------------------------------------


class TestGv010:
    def test_min_move_evaluates_to_fifteen_for_atr_ten(self):
        assert common.evaluate_displacement_min_move(10) == 15

    def test_move_fourteen_fails_and_the_origin_expires(self, caps):
        # A full-range bull marubozu isolates the move conjunct exactly (body/close-location
        # trivially satisfied at every move value tried here), per GV-010.
        steps = [origin("o", 100, 0, atr=10)] + window_fill(
            101, bar("b1", 101, 0, 14, 14, 0))
        state, events = run_f11(caps, steps)
        assert qualified(events) == []
        (event,) = abstentions(events)
        assert event["reason_code"] == disp.NO_QUALIFYING_BAR
        assert event["refs"]["origin_bar_index"] == 100
        assert event["refs"]["horizon"] == 3
        assert state["search"] is None

    def test_move_fifteen_passes_with_the_full_event_shape(self, caps):
        state, events = run_f11(caps, [
            origin("o", 100, 0, atr=10), bar("b1", 101, 0, 15, 15, 0)])
        (event,) = qualified(events)
        assert event == {
            "event_kind": disp.DISPLACEMENT_QUALIFIED,
            "formula": "F11",
            "semantic_version": "displacement.closed_path.v1",
            "direction": common.LONG,
            "origin_bar_index": 100,
            "qualifying_bar_index": 101,
            "move_ticks": 15,
            "d_ticks": 15,
            "body_ratio_numerator": 1,       # 15/15 reduced (§1.3)
            "body_ratio_denominator": 1,
            "close_loc_numerator": 1,        # 15/15 reduced (§1.3)
            "close_loc_denominator": 1,
            "origin_bar_identity": "o",
            "confirmed_by_bar_identity": "b1",
        }
        assert state["search"] is None

    def test_rc2_source_vector_passes_and_its_boundary_open_fails(self, caps):
        # GV-010 embedded rc2 vector: origin_open=100, ATR_before=20 -> D=30; trigger
        # O/H/L/C = 117/130/110/130 -> move=30 (equality), body=13/20, close_loc=20/20: PASS.
        _, events = run_f11(caps, [
            origin("o", 0, 100, atr=20), bar("b1", 1, 117, 130, 130, 110)])
        (event,) = qualified(events)
        assert event["move_ticks"] == 30
        assert event["d_ticks"] == 30
        assert (event["body_ratio_numerator"], event["body_ratio_denominator"]) == (13, 20)
        assert (event["close_loc_numerator"], event["close_loc_denominator"]) == (1, 1)
        # Boundary: trigger open=118 gives body 12/20 < 13/20 -> fail.
        steps = [origin("o", 0, 100, atr=20)] + window_fill(
            1, bar("b1", 1, 118, 130, 130, 110))
        _, events = run_f11(caps, steps)
        assert qualified(events) == []
        (event,) = abstentions(events)
        assert event["reason_code"] == disp.NO_QUALIFYING_BAR


# ---------------------------------------------------------------------------------------------
# T3/T4 — beta (13/20) and lambda (4/5) exact boundaries, inclusive; one unit under fails
# ---------------------------------------------------------------------------------------------


class TestRatioBoundaries:
    def test_body_ratio_equality_passes_and_one_unit_under_fails(self, caps):
        # range = 20 (H=20, L=0), close 17 clears the close-location floor (>= 16); body
        # numerator |C-O| = 13 exactly (equality) vs 12 (one under). Opens are IN RANGE.
        _, events = run_f11(caps, [
            origin("o", 0, -1000, atr=1), bar("b1", 1, 4, 17, 20, 0)])
        (event,) = qualified(events)
        assert (event["body_ratio_numerator"], event["body_ratio_denominator"]) == (13, 20)
        steps = [origin("o", 0, -1000, atr=1)] + window_fill(1, bar("b1", 1, 5, 17, 20, 0))
        _, events = run_f11(caps, steps)
        assert qualified(events) == []
        assert [e["reason_code"] for e in abstentions(events)] == [disp.NO_QUALIFYING_BAR]

    def test_close_location_equality_passes_and_one_unit_under_fails(self, caps):
        # range = 20; (C-L) must clear >= 16 (4/5 * 20). Open IN RANGE (O=0) still isolates
        # the boundary: body |16-0| = 16 >= 13 holds comfortably.
        _, events = run_f11(caps, [
            origin("o", 0, -1000, atr=1), bar("b1", 1, 0, 16, 20, 0)])
        (event,) = qualified(events)
        assert (event["close_loc_numerator"], event["close_loc_denominator"]) == (4, 5)
        steps = [origin("o", 0, -1000, atr=1)] + window_fill(1, bar("b1", 1, 0, 15, 20, 0))
        _, events = run_f11(caps, steps)
        assert qualified(events) == []
        assert [e["reason_code"] for e in abstentions(events)] == [disp.NO_QUALIFYING_BAR]

    def test_bear_close_location_boundary_is_exact(self, caps):
        # Bear mirror of the close-location boundary: (H-C)*5 >= range*4, open IN RANGE.
        _, events = run_f11(caps, [
            origin("o", 0, 1000, atr=1), bar("b1", 1, 17, 4, 20, 0)])
        (event,) = qualified(events)
        assert event["direction"] == common.SHORT
        assert (event["close_loc_numerator"], event["close_loc_denominator"]) == (4, 5)
        assert (event["body_ratio_numerator"], event["body_ratio_denominator"]) == (13, 20)
        steps = [origin("o", 0, 1000, atr=1)] + window_fill(1, bar("b1", 1, 18, 5, 20, 0))
        _, events = run_f11(caps, steps)
        assert qualified(events) == []
        assert [e["reason_code"] for e in abstentions(events)] == [disp.NO_QUALIFYING_BAR]

    def test_body_ratio_boundary_holds_exactly_where_float_division_misrounds(self, caps):
        scale = 10 ** 16
        range_ticks = 20 * scale
        close = 16 * scale
        low, high = 0, range_ticks
        at_threshold_open = close - 13 * scale       # |C-O| == 13*scale (equality passes)
        one_under_open = close - (13 * scale - 1)    # |C-O| == 13*scale - 1 (fails)

        # The adversarial proof: float(13*scale - 1) / float(20*scale) misrounds to exactly
        # 0.65, which a naive `ratio >= 0.65` comparison would wrongly accept.
        misrounded = (13 * scale - 1) / (20 * scale)
        assert misrounded == 0.65
        assert misrounded >= 0.65  # the float trap this test exists to catch

        _, events = run_f11(caps, [
            origin("o", 0, -10 * scale, atr=1),
            bar("b1", 1, at_threshold_open, close, high, low)])
        (event,) = qualified(events)
        assert (event["body_ratio_numerator"], event["body_ratio_denominator"]) == (13, 20)

        steps = [origin("o", 0, -10 * scale, atr=1)] + window_fill(
            1, bar("b1", 1, one_under_open, close, high, low))
        _, events = run_f11(caps, steps)
        assert qualified(events) == []
        assert [e["reason_code"] for e in abstentions(events)] == [disp.NO_QUALIFYING_BAR]


# ---------------------------------------------------------------------------------------------
# T5 — earliest qualifying bar wins; window exhaustion; T6 — gap; ordering law
# ---------------------------------------------------------------------------------------------


class TestWindowLaws:
    def test_t5_earliest_qualifying_bar_wins_and_the_search_stops(self, caps):
        state, events = run_f11(caps, [
            origin("o", 100, 0, atr=10),
            bar("b1", 101, 0, 5, 5, 0),      # move=5 < D=15: fails
            bar("b2", 102, 0, 20, 20, 0),    # qualifies (earliest)
            bar("b3", 103, 0, 999, 999, 0),  # never evaluated: search already closed
        ])
        events_q = qualified(events)
        assert len(events_q) == 1
        assert events_q[0]["qualifying_bar_index"] == 102
        assert events_q[0]["move_ticks"] == 20
        assert abstentions(events) == []
        assert state["search"] is None

    def test_no_qualifying_bar_in_the_window_yields_exactly_one_abstention(self, caps):
        _, events = run_f11(caps, [
            origin("o", 100, 0, atr=10),
            bar("b1", 101, 0, 5, 5, 0),
            bar("b2", 102, 0, 3, 3, 0),
            bar("b3", 103, 0, 1, 1, 0),
        ])
        assert qualified(events) == []
        (event,) = abstentions(events)
        assert event["reason_code"] == disp.NO_QUALIFYING_BAR
        assert event["formula"] == "F11"
        assert event["refs"]["origin_bar_index"] == 100
        assert event["refs"]["horizon"] == 3

    def test_t6_gap_is_a_named_abstention_and_never_searches_across_it(self, caps):
        state, events = run_f11(caps, [
            origin("o", 100, 0, atr=10),
            bar("b1", 101, 0, 5, 5, 0),       # non-qualifying, examined=1
            bar("b2", 103, 0, 999, 999, 0),   # skips 102: gap, would otherwise qualify
        ])
        assert qualified(events) == []
        (event,) = abstentions(events)
        assert event["reason_code"] == disp.GAP_IN_SEARCH_WINDOW
        assert event["refs"]["expected_bar_index"] == 102
        assert event["refs"]["got_bar_index"] == 103
        assert state["search"] is None

    def test_bar_after_a_gap_abstention_is_a_harmless_no_op(self, caps):
        state, _ = run_f11(caps, [
            origin("o", 100, 0, atr=10),
            bar("b1", 101, 0, 5, 5, 0),
            bar("b2", 103, 0, 999, 999, 0),
        ])
        assert state["search"] is None
        stray_state, stray_events = run_f11(
            caps, [bar("b3", 104, 0, 999, 999, 0)], state=state)
        assert stray_events == []
        assert stray_state["search"] is None

    def test_backward_bar_index_is_a_structural_ordering_violation(self, caps):
        with pytest.raises(common.StructureLawError):
            run_f11(caps, [
                origin("o", 100, 0, atr=10),
                bar("b1", 101, 0, 5, 5, 0),
                bar("b2", 101, 1, 5, 5, 1),
            ])

    def test_bar_before_any_origin_is_a_harmless_no_op(self, caps):
        state, events = run_f11(caps, [bar("b1", 1, 0, 20, 20, 0)])
        assert events == []
        assert state["search"] is None


# ---------------------------------------------------------------------------------------------
# Warm-up + supersession
# ---------------------------------------------------------------------------------------------


class TestOriginLaws:
    def test_missing_atr_is_a_named_abstention_and_opens_no_search(self, caps):
        state, events = run_f11(caps, [
            origin("o", 100, 0, atr=None), bar("b1", 101, 0, 20, 20, 0)])
        assert qualified(events) == []
        (event,) = abstentions(events)
        assert event["reason_code"] == disp.NO_ATR
        assert event["formula"] == "F11"
        assert event["refs"]["origin_bar_index"] == 100
        assert state["search"] is None

    def test_a_new_origin_always_supersedes_a_still_open_search(self, caps):
        _, events = run_f11(caps, [
            origin("o1", 100, 0, atr=10),
            bar("b1", 101, 0, 5, 5, 0),          # non-qualifying for origin 100
            origin("o2", 200, 0, atr=10),        # supersedes: fresh window from origin 200
            bar("b2", 201, 0, 20, 20, 0),        # qualifies against the new origin
        ])
        (event,) = qualified(events)
        assert event["origin_bar_index"] == 200
        assert event["qualifying_bar_index"] == 201
        assert event["origin_bar_identity"] == "o2"
        assert abstentions(events) == []

    def test_a_bar_call_must_not_carry_the_origin_atr_dependency(self, caps):
        state, _ = run_f11(caps, [origin("o", 100, 0, atr=10)])
        with pytest.raises(common.StructureLawError):
            disp.evaluate(
                caps, e01.require_valid_bar(raw_bar("b1", 0, 20, 20, 0)), state,
                role=disp.ROLE_BAR, bar_index=101, atr14_before_origin_ticks=10)

    def test_unknown_role_is_refused(self, caps):
        with pytest.raises(common.StructureLawError):
            disp.evaluate(
                caps, e01.require_valid_bar(raw_bar("b1", 0, 20, 20, 0)),
                disp.initial_state(), role="TRADE", bar_index=1)


# ---------------------------------------------------------------------------------------------
# T7 — zero-range bar (H == L, C == O): body_ratio 0/1, fails beta > 0 deterministically
# ---------------------------------------------------------------------------------------------


class TestZeroRange:
    def test_t7_zero_range_bar_never_qualifies_even_with_a_huge_move(self, caps):
        # A VALID zero-range bar forces O == C == H == L; move is huge but body_ratio is 0/1
        # (< 13/20) and C > O / C < O are both false — deterministic non-qualification.
        state, events = run_f11(caps, [
            origin("o", 100, 0, atr=10), bar("b1", 101, 500, 500, 500, 500)])
        assert qualified(events) == []
        assert state["search"] is not None
        assert state["search"]["examined"] == 1
        # Full window of zero-range bars -> exactly one NO_QUALIFYING_BAR expiry.
        steps = [origin("o", 100, 0, atr=10)] + [
            bar(f"z{i}", 100 + i, 500, 500, 500, 500) for i in (1, 2, 3)]
        _, events = run_f11(caps, steps)
        assert qualified(events) == []
        assert [e["reason_code"] for e in abstentions(events)] == [disp.NO_QUALIFYING_BAR]


# ---------------------------------------------------------------------------------------------
# T1/T2 + volume arms — VALID_BAR failure = quarantine record + the origin expires (gap class)
# ---------------------------------------------------------------------------------------------


class TestValidBarQuarantine:
    def _expire_via_quarantine(self, caps, bad_raw: dict, bar_index: int):
        state, _ = run_f11(caps, [origin("o", 100, 0, atr=10)])
        assert state["search"] is not None
        with pytest.raises(e01.QuarantineInvalidBar) as excinfo:
            e01.require_valid_bar(bad_raw)
        result = disp.evaluate_quarantined_bar(
            caps, excinfo.value, state, bar_index=bar_index)
        (record,) = result.events
        assert record["event_kind"] == "QUARANTINE"
        assert record["reason_code"] == e01.QUARANTINE_INVALID_BAR
        assert record["bar_identity"] == bad_raw.get("bar_identity")
        assert record["formula"] == "F11"
        assert record["refs"]["origin_bar_identity"] == "o"
        assert record["refs"]["origin_bar_index"] == 100
        assert record["refs"]["quarantined_bar_index"] == bar_index
        assert result.state["search"] is None
        # The origin expired unqualified: a later would-qualify bar is a harmless no-op
        # (exactly the gap-abstention law).
        after_state, after_events = run_f11(
            caps, [bar("b2", bar_index + 1, 0, 999, 999, 0)], state=result.state)
        assert after_events == []
        assert after_state["search"] is None

    def test_t1_close_above_high_quarantines_and_the_origin_expires(self, caps):
        self._expire_via_quarantine(caps, raw_bar("b1", 10, 25, 20, 0), 101)

    def test_t2_open_below_low_quarantines_and_the_origin_expires(self, caps):
        self._expire_via_quarantine(caps, raw_bar("b1", -5, 17, 20, 0), 101)

    def test_close_below_low_and_open_above_high_quarantine_too(self, caps):
        self._expire_via_quarantine(caps, raw_bar("b1", 10, -5, 20, 0), 101)
        self._expire_via_quarantine(caps, raw_bar("b1", 25, 17, 20, 0), 101)

    def test_missing_volume_and_negative_count_arms_quarantine(self, caps):
        missing = raw_bar("b1", 0, 17, 20, 0)
        del missing["base_volume"]
        self._expire_via_quarantine(caps, missing, 101)
        negative = raw_bar("b1", 0, 17, 20, 0, trade_count=-1)
        self._expire_via_quarantine(caps, negative, 101)

    def test_quarantine_with_no_open_search_is_a_harmless_no_op(self, caps):
        with pytest.raises(e01.QuarantineInvalidBar) as excinfo:
            e01.require_valid_bar(raw_bar("b1", 10, 25, 20, 0))
        result = disp.evaluate_quarantined_bar(
            caps, excinfo.value, disp.initial_state(), bar_index=1)
        assert result.events == ()
        assert result.state == disp.initial_state()

    def test_quarantine_input_must_be_the_typed_e01_artifact(self, caps):
        with pytest.raises(e01.QuarantineInvalidBar):
            disp.evaluate_quarantined_bar(
                caps, {"reason_code": "QUARANTINE_INVALID_BAR"}, disp.initial_state())

    def test_origin_bar_valid_bar_arm_boundary_refusal(self, caps):
        # "For origin bar o AND every candidate bar j: REQUIRE VALID_BAR" — an invalid ORIGIN
        # bar never becomes an envelope object at all.
        bad_origin = raw_bar("o", -5, 17, 20, 0)  # open below low
        with pytest.raises(e01.QuarantineInvalidBar):
            e01.require_valid_bar(bad_origin)


# ---------------------------------------------------------------------------------------------
# Defense in depth (R-F11 ACCEPTANCE): the local §1.1 assertion — every arm, forged envelopes
# ---------------------------------------------------------------------------------------------


class TestLocalDefenseInDepth:
    FORGED_ARMS = {
        "close_above_high": {"close_ticks": 25},
        "close_below_low": {"close_ticks": -5},
        "open_above_high": {"open_ticks": 25},
        "open_below_low": {"open_ticks": -5},
        "low_above_high": {"low_ticks": 30, "open_ticks": 30, "close_ticks": 30,
                           "high_ticks": 25},
        "negative_base_volume": {"base_volume": -1},
        "negative_quote_volume": {"quote_volume": -1},
        "negative_trade_count": {"trade_count": -1},
        "bool_trade_count": {"trade_count": True},
        "non_int_close": {"close_ticks": "16"},
        "over_int64_high": {"high_ticks": 2 ** 63, "close_ticks": 2 ** 63},
    }

    @pytest.mark.parametrize("arm", sorted(FORGED_ARMS))
    def test_every_forged_arm_quarantines_and_expires_the_open_search(self, caps, arm):
        state, _ = run_f11(caps, [origin("o", 100, 0, atr=10)])
        forged = forged_bar(bar_identity="b1", **self.FORGED_ARMS[arm])
        result = disp.evaluate(caps, forged, state, role=disp.ROLE_BAR, bar_index=101)
        assert qualified(result.events) == []
        (record,) = result.events
        assert record["event_kind"] == "QUARANTINE"
        assert record["reason_code"] == e01.QUARANTINE_INVALID_BAR
        assert record["refs"]["origin_bar_index"] == 100
        assert result.state["search"] is None

    def test_a_forged_origin_bar_quarantines_and_opens_no_search(self, caps):
        forged = forged_bar(bar_identity="o", open_ticks=-5)  # open below low
        result = disp.evaluate(
            caps, forged, disp.initial_state(),
            role=disp.ROLE_ORIGIN, bar_index=100, atr14_before_origin_ticks=10)
        (record,) = result.events
        assert record["reason_code"] == e01.QUARANTINE_INVALID_BAR
        assert result.state["search"] is None

    def test_the_exploit_bar_can_no_longer_fabricate_a_displacement(self, caps):
        # The audited R-F11 defect trap: close above high over-satisfies close-location.
        # Through the boundary it never constructs; forged past the boundary it quarantines.
        state, _ = run_f11(caps, [origin("o", 100, 0, atr=10)])
        forged = forged_bar(bar_identity="b1", open_ticks=0, close_ticks=25,
                            high_ticks=20, low_ticks=0)
        result = disp.evaluate(caps, forged, state, role=disp.ROLE_BAR, bar_index=101)
        assert qualified(result.events) == []
        assert result.state["search"] is None


# ---------------------------------------------------------------------------------------------
# T9 — §1.2 int64 boundary on move_j: largest lawful value passes, one beyond quarantines
# ---------------------------------------------------------------------------------------------


class TestInt64Boundary:
    def test_t9_move_at_int64_max_passes_and_is_emitted(self, caps):
        # origin open = INT64_MIN; candidate close = -1 -> move = 2^63 - 1 exactly.
        _, events = run_f11(caps, [
            origin("o", 0, INT64_MIN, atr=1),
            bar("b1", 1, -21, -1, -1, -21)])
        (event,) = qualified(events)
        assert event["move_ticks"] == INT64_MAX == 2 ** 63 - 1
        assert (event["body_ratio_numerator"], event["body_ratio_denominator"]) == (1, 1)

    def test_t9_move_one_beyond_int64_quarantines_never_wraps_never_emits(self, caps):
        # Same shape, close = 0 -> move = 2^63: one beyond the wire width. The bar satisfies
        # every qualification conjunct, so emission is attempted — and the §1.2 boundary
        # guard quarantines instead of emitting.
        state, _ = run_f11(caps, [origin("o", 0, INT64_MIN, atr=1)])
        with pytest.raises(QuarantineOverflow) as excinfo:
            disp.evaluate(
                caps, e01.require_valid_bar(raw_bar("b1", -20, 0, 0, -20)), state,
                role=disp.ROLE_BAR, bar_index=1)
        assert excinfo.value.formula_id == "F11"
        assert excinfo.value.field == "move_ticks"

    def test_atr_outside_int64_quarantines_at_the_origin_boundary(self, caps):
        with pytest.raises(QuarantineOverflow):
            run_f11(caps, [origin("o", 0, 0, atr=2 ** 63)])
        with pytest.raises(QuarantineOverflow):
            run_f11(caps, [origin("o", 0, 0, atr="10")])  # a non-int is just as un-emittable


# ---------------------------------------------------------------------------------------------
# T8 — full bear mirror (price reflection: O->-O, C->-C, H<->-L)
# ---------------------------------------------------------------------------------------------


class TestMirrorLaw:
    @staticmethod
    def reflect(step: tuple) -> tuple:
        def reflect_raw(raw: dict) -> dict:
            out = dict(raw)
            out["open_ticks"] = -raw["open_ticks"]
            out["close_ticks"] = -raw["close_ticks"]
            out["high_ticks"] = -raw["low_ticks"]
            out["low_ticks"] = -raw["high_ticks"]
            return out
        if step[0] == "ORIGIN":
            return ("ORIGIN", reflect_raw(step[1]), step[2], step[3])
        return ("BAR", reflect_raw(step[1]), step[2])

    def test_t8_long_short_mirror_is_exact_algebraic_symmetry(self, caps):
        straight = [
            origin("o", 100, 0, atr=10),
            bar("b1", 101, 0, 5, 5, 0),       # non-qualifying filler
            bar("b2", 102, 0, 20, 20, 0),     # qualifies LONG
        ]
        mirrored = [self.reflect(step) for step in straight]
        _, straight_events = run_f11(caps, straight)
        _, mirrored_events = run_f11(caps, mirrored)
        (s,) = qualified(straight_events)
        (m,) = qualified(mirrored_events)
        assert s["direction"] == common.LONG
        assert m["direction"] == common.SHORT
        assert m["move_ticks"] == -s["move_ticks"]
        assert m["d_ticks"] == s["d_ticks"]
        assert m["qualifying_bar_index"] == s["qualifying_bar_index"]
        assert m["origin_bar_index"] == s["origin_bar_index"]
        assert m["body_ratio_numerator"] == s["body_ratio_numerator"]
        assert m["body_ratio_denominator"] == s["body_ratio_denominator"]
        assert m["close_loc_numerator"] == s["close_loc_numerator"]
        assert m["close_loc_denominator"] == s["close_loc_denominator"]
        assert m["origin_bar_identity"] == s["origin_bar_identity"]
        assert m["confirmed_by_bar_identity"] == s["confirmed_by_bar_identity"]


# ---------------------------------------------------------------------------------------------
# Restart / prefix replay parity + idempotency + never-double-emit
# ---------------------------------------------------------------------------------------------


class TestRestartParity:
    QUALIFYING = [
        origin("o", 100, 0, atr=10),
        bar("b1", 101, 0, 5, 5, 0),
        bar("b2", 102, 0, 20, 20, 0),
    ]
    EXPIRING = [
        origin("o", 100, 0, atr=10),
        bar("b1", 101, 0, 5, 5, 0),
        bar("b2", 102, 0, 3, 3, 0),
        bar("b3", 103, 0, 1, 1, 0),
    ]

    @pytest.mark.parametrize("name", ["QUALIFYING", "EXPIRING"])
    def test_prefix_and_restart_invariance_across_every_cut_point(self, caps, name):
        steps = list(self.__class__.__dict__[name])
        full_state, full_events = run_f11(caps, steps)
        for cut in range(1, len(steps)):
            prefix_state, prefix_events = run_f11(caps, steps[:cut])
            checkpoint = json.loads(canonical_json(prefix_state))  # real checkpoint round-trip
            resumed_state, resumed_events = run_f11(caps, steps[cut:], state=checkpoint)
            assert canonical_json(prefix_events + resumed_events) == canonical_json(full_events)
            assert canonical_json(resumed_state) == canonical_json(full_state)

    def test_exact_retransmission_is_an_idempotent_no_op(self, caps):
        state, _ = run_f11(caps, self.QUALIFYING[:2])
        again = disp.evaluate(
            caps, e01.require_valid_bar(self.QUALIFYING[1][1]), state,
            role=disp.ROLE_BAR, bar_index=self.QUALIFYING[1][2])
        assert again.state == state
        assert again.events == ()

    def test_restart_after_qualification_never_double_emits(self, caps):
        state, events = run_f11(caps, self.QUALIFYING)
        assert len(qualified(events)) == 1
        after_state, after_events = run_f11(
            caps, [bar("b4", 103, 0, 20, 20, 0)], state=state)
        assert after_events == []
        assert after_state["search"] is None


# ---------------------------------------------------------------------------------------------
# GV-010 boundary posture — BLOCKED_UNTIL_PAR-158_RATIFIED (mechanism + named refusal)
# ---------------------------------------------------------------------------------------------


class TestBlockedOnRatify:
    def test_repository_registry_keeps_all_four_f11_rows_blocked(self, real_registry):
        for binding_id, parameter_id, declared in (
                ("FPB-0021", "PAR-046", common.DECLARED_DISPLACEMENT_BODY_FRACTION),
                ("FPB-0065", "PAR-157", disp.DECLARED_DISPLACEMENT_HORIZON),
                ("FPB-0066", "PAR-158", common.DECLARED_DISPLACEMENT_MIN_MOVE),
                ("FPB-0067", "PAR-159", common.DECLARED_DISPLACEMENT_CLOSE_LOCATION)):
            row = real_registry.row(binding_id)
            assert row["status"] == "BLOCKED_BINDING_V2_MIGRATION"
            assert row["lifecycle_status"] == "BLOCKED"
            assert row["parameter_id"] == parameter_id
            assert row["declared_value"] == declared

    def test_no_f11_capability_can_be_minted_from_the_repository_registry(self, real_registry):
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
                bundle, disp.PARAMETER_MIN_MOVE, formula_id="F11", ctx=ctx)
        assert excinfo.value.formula_id == "F11"
        assert str(excinfo.value) == "BLOCKED_BINDING_INCOMPLETE:F11"

    def test_the_declared_par158_byte_string_cannot_ride_an_active_row_today(self):
        # The PAR-158 transport interlock (the PAR-036 precedent): the declared byte-string
        # contains ``*`` and the wildcard-sentinel law refuses it in an ACTIVE row.
        with pytest.raises(bindings.BindingRegistryError) as excinfo:
            bindings.BindingRegistry(
                _ratified_doc(par158_value=common.DECLARED_DISPLACEMENT_MIN_MOVE))
        assert "ACTIVE_BINDING_UNRESOLVED_FIELD" in str(excinfo.value)

    def test_missing_capability_is_the_named_refusal(self):
        with pytest.raises(disp.BlockedOnRatify) as excinfo:
            disp.evaluate(
                {}, e01.require_valid_bar(raw_bar("b0", 0, 16, 20, 0)),
                disp.initial_state(), role=disp.ROLE_BAR, bar_index=1)
        assert str(excinfo.value) == "BLOCKED_ON_RATIFY(PAR-046)"
        assert excinfo.value.parameter_id == disp.PARAMETER_BODY_FRACTION

    def test_each_absent_parameter_is_named_in_declaration_order(self, caps):
        for parameter_id in disp.REQUIRED_PARAMETERS:
            partial = {k: v for k, v in caps.items() if k != parameter_id}
            with pytest.raises(disp.BlockedOnRatify) as excinfo:
                disp.evaluate(
                    partial, e01.require_valid_bar(raw_bar("b0", 0, 16, 20, 0)),
                    disp.initial_state(), role=disp.ROLE_BAR, bar_index=1)
            assert excinfo.value.parameter_id == parameter_id


# ---------------------------------------------------------------------------------------------
# The C.3 boundary — adversarial dynamic gate
# ---------------------------------------------------------------------------------------------


class TestBoundaryRejections:
    def test_hand_built_dict_in_place_of_a_capability_is_a_typed_rejection(self, caps):
        state = disp.initial_state()
        before = copy.deepcopy(state)
        forged = dict(caps)
        forged[disp.PARAMETER_MIN_MOVE] = {
            "value": common.DECLARED_DISPLACEMENT_MIN_MOVE,
            "formula_id": "F11", "parameter_id": "PAR-158"}
        with pytest.raises(bindings.CapabilityForgeryError):
            disp.evaluate(
                forged, e01.require_valid_bar(raw_bar("b0", 0, 16, 20, 0)), state,
                role=disp.ROLE_BAR, bar_index=1)
        assert state == before  # rejected BEFORE any state transition

    @pytest.mark.parametrize("junk", [17, "13/20", None, [1, 2]])
    def test_non_capability_entries_are_typed_rejections(self, caps, junk):
        forged = dict(caps)
        forged[disp.PARAMETER_BODY_FRACTION] = junk
        with pytest.raises(bindings.CapabilityForgeryError):
            disp.evaluate(
                forged, e01.require_valid_bar(raw_bar("b0", 0, 16, 20, 0)),
                disp.initial_state(), role=disp.ROLE_BAR, bar_index=1)

    def test_caps_container_must_be_a_mapping(self, caps):
        with pytest.raises(bindings.CapabilityForgeryError):
            disp.evaluate(
                list(caps.values()), e01.require_valid_bar(raw_bar("b0", 0, 16, 20, 0)),
                disp.initial_state(), role=disp.ROLE_BAR, bar_index=1)

    def test_unknown_parameter_key_is_refused(self, caps):
        widened = dict(caps)
        widened["PAR-999"] = caps[disp.PARAMETER_BODY_FRACTION]
        with pytest.raises(bindings.CapabilityForgeryError):
            disp.evaluate(
                widened, e01.require_valid_bar(raw_bar("b0", 0, 16, 20, 0)),
                disp.initial_state(), role=disp.ROLE_BAR, bar_index=1)

    def test_mixed_type_mapping_keys_are_still_a_typed_rejection(self, caps):
        widened = dict(caps)
        widened[17] = caps[disp.PARAMETER_BODY_FRACTION]
        with pytest.raises(bindings.CapabilityForgeryError):
            disp.evaluate(
                widened, e01.require_valid_bar(raw_bar("b0", 0, 16, 20, 0)),
                disp.initial_state(), role=disp.ROLE_BAR, bar_index=1)

    def test_foreign_formula_capability_is_refused(self, caps, foreign_cap):
        assert foreign_cap.formula_id == "F00"  # a GENUINE capability — for another formula
        forged = dict(caps)
        forged[disp.PARAMETER_BODY_FRACTION] = foreign_cap
        with pytest.raises(bindings.CapabilityForgeryError):
            disp.evaluate(
                forged, e01.require_valid_bar(raw_bar("b0", 0, 16, 20, 0)),
                disp.initial_state(), role=disp.ROLE_BAR, bar_index=1)

    def test_swapped_parameter_key_is_refused(self, caps):
        swapped = dict(caps)
        swapped[disp.PARAMETER_BODY_FRACTION] = caps[disp.PARAMETER_CLOSE_LOCATION]
        swapped[disp.PARAMETER_CLOSE_LOCATION] = caps[disp.PARAMETER_BODY_FRACTION]
        with pytest.raises(bindings.CapabilityForgeryError):
            disp.evaluate(
                swapped, e01.require_valid_bar(raw_bar("b0", 0, 16, 20, 0)),
                disp.initial_state(), role=disp.ROLE_BAR, bar_index=1)

    @pytest.mark.parametrize("parameter_id, bad_value", [
        ("PAR-158", "max(5,ceil(ATR14_ticks*1/4))"),   # the F03 rule is not the F11 rule
        ("PAR-046", "1/2"),
        ("PAR-159", "1/2"),
        ("PAR-157", "5"),
        ("PAR-157", 3),                                 # the int is not the declared string
    ])
    def test_tampered_declared_values_are_refused(self, caps, parameter_id, bad_value):
        tampered = dict(caps)
        tampered[parameter_id] = dataclasses.replace(caps[parameter_id], value=bad_value)
        with pytest.raises(common.StructureLawError):
            disp.evaluate(
                tampered, e01.require_valid_bar(raw_bar("b0", 0, 16, 20, 0)),
                disp.initial_state(), role=disp.ROLE_BAR, bar_index=1)

    def test_raw_dict_env_is_a_typed_boundary_rejection(self, caps):
        with pytest.raises(e01.QuarantineInvalidBar):
            disp.evaluate(
                caps, raw_bar("b0", 0, 16, 20, 0), disp.initial_state(),
                role=disp.ROLE_BAR, bar_index=1)

    def test_garbage_state_fails_closed(self, caps):
        with pytest.raises(common.StructureLawError):
            disp.evaluate(
                caps, e01.require_valid_bar(raw_bar("b0", 0, 16, 20, 0)),
                {"search": None}, role=disp.ROLE_BAR, bar_index=1)
        bad = disp.initial_state()
        bad["search"] = {"origin_bar_index": 1}
        with pytest.raises(common.StructureLawError):
            disp.evaluate(
                caps, e01.require_valid_bar(raw_bar("b0", 0, 16, 20, 0)), bad,
                role=disp.ROLE_BAR, bar_index=1)


# ---------------------------------------------------------------------------------------------
# Acceptance static scans: never-float / no raw-dict surface / no low<=high-only geometry
# ---------------------------------------------------------------------------------------------


class TestStaticScans:
    def test_no_division_operator_is_used_on_tick_values_in_this_module(self):
        import ast
        import inspect

        tree = ast.parse(inspect.getsource(disp))
        for node in ast.walk(tree):
            assert not isinstance(node, ast.BinOp) or not isinstance(
                node.op, (ast.Div, ast.FloorDiv))

    def test_no_low_high_only_geometry_check_remains(self):
        import ast
        import inspect

        source = inspect.getsource(disp)
        # The Phase-0 raise-based partial geometry guards are gone...
        assert "low_ticks exceeds high_ticks" not in source
        assert "close_ticks outside" not in source
        assert not [  # the partial-geometry helper no longer exists as CODE
            node for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.FunctionDef) and node.name == "_bar_geometry"]
        # ...and the local defense-in-depth assertion carries the FULL §1.1 arm set.
        assert "low <= min(open, close)" in source
        assert "max(open, close) <= high" in source
        assert "must each be >= 0" in source

    def test_module_scans_clean_under_the_c3_static_gate_regexes(self):
        import re

        text = pathlib.Path(disp.__file__).read_text(encoding="utf-8")
        assert not re.search(r"^\s*Params\s*=\s*dict", text, re.MULTILINE)
        assert not re.search(r"def\s+\w*evaluate\w*\s*\([^)]*[Dd]ict\[str,\s*Any\]",
                             text, re.DOTALL)
        assert not re.search(r"(?:transition\.)?require\(\s*params", text)
        assert not re.search(r"\b(ValidatedBar|ValidatedTrade|ValidatedBookUpdate)\s*\(", text)
        assert "RETIRED_DEFECTIVE" not in text  # v1 is RETAINED, not retired (§1.5)


# ---------------------------------------------------------------------------------------------
# Version discipline (§1.5) — v1 retained, stamped on every emitted fact
# ---------------------------------------------------------------------------------------------


class TestVersionDiscipline:
    def test_module_identity_constants(self):
        assert disp.FORMULA_F11 == "F11"
        assert disp.SEMANTIC_VERSION == "displacement.closed_path.v1"
        assert disp.REQUIRED_PARAMETERS == ("PAR-046", "PAR-157", "PAR-158", "PAR-159")
        assert disp.DECLARED_DISPLACEMENT_HORIZON == "3"

    def test_every_emitted_fact_carries_the_semantic_version(self, caps):
        _, events = run_f11(caps, [
            origin("o", 100, 0, atr=10), bar("b1", 101, 0, 15, 15, 0)])
        (event,) = qualified(events)
        assert event["semantic_version"] == "displacement.closed_path.v1"
        _, events = run_f11(caps, [origin("o2", 200, 0, atr=None)])
        (event,) = abstentions(events)
        assert event["refs"]["semantic_version"] == "displacement.closed_path.v1"
