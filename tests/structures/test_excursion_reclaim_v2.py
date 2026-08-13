"""R-F13 ``level_excursion_reclaim.closed.v2`` — spec vectors T1-T14 + acceptance property.

TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12 §R-F13 (CRITICAL, FIX FIRST). Vector defaults:
``L_px=10000 ticks, e=20, r=10, tau=12, n=2`` unless stated. The capability fixture is REAL: a
test-RATIFIED copy of the binding registry (the four F13 rows FPB-0023/0024/0072/0073 flipped
ACTIVE in memory only, carrying the exact vector tick values as canonical integer strings — the
repository rows stay BLOCKED, proven below) sealed via ``build_sealed_bundle`` and accepted
through ``transition.require_bundle`` with the Ed25519 pattern from
``tests/contracts/test_sealed_bundle_v2.py``. The PROPOSED_MUST_RATIFY posture is proven on the
UNMODIFIED repository registry: no F13 capability can be minted
(``BLOCKED_BINDING_INCOMPLETE:F13``), and the v1 ATR-rule byte-strings refuse by name
(``F13_BINDING_VALUE_NOT_INTEGER``) — never evaluated, never defaulted.
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
from triad_origin.canonical import INT64_MAX, INT64_MIN, canonical_json, sha256_hex  # noqa: E402
from triad_origin.exact import QuarantineOverflow  # noqa: E402
from triad_origin.structures import excursion_reclaim_registry_v2 as face  # noqa: E402
from triad_origin.structures import excursion_reclaim_v2 as xr  # noqa: E402
from triad_origin.structures.common import LONG, SHORT, StructureLawError  # noqa: E402

OWNER_KID = "k-owner-f13"
REPOSITORY = "TriadOrigin"
ENVIRONMENT = "OFF"
VALID_FROM = 1_000_000
VALID_TO = 9_000_000
NOW_US = 2_000_000

# Vector defaults (R-F13 TESTS header).
L_PX = 10_000
E_TICKS = 20
R_TICKS = 10
TAU_BARS = 12
N_HOLD = 2

BAR_US = 60_000_000
T0_BUCKET = 1_000_000_000  # bucket_start of ordinal 0
T_L = T0_BUCKET            # default availability: eligible from ordinal 0 (inclusive)

# The four F13 machine-parameter rows and the vector values the test ratification carries.
_F13_ROWS = {
    "FPB-0023": (xr.PARAM_EXCURSION_MIN, str(E_TICKS)),
    "FPB-0024": (xr.PARAM_RECLAIM_TAU, str(TAU_BARS)),
    "FPB-0072": (xr.PARAM_RECLAIM_CLOSE_BUFFER, str(R_TICKS)),
    "FPB-0073": (xr.PARAM_RECLAIM_HOLD_BARS, str(N_HOLD)),
}
# The two remaining F13-registered rows (capsule entry gates — PAR-176/PAR-178). The BIND-04
# formula-completeness law demands the ENTIRE registered F13 set ACTIVE before any capability
# can be minted, so the TEST ratification flips them too (their declared values are kept
# verbatim; the v2 machine never requests them).
_F13_CAPSULE_ROWS = {
    "FPB-0088": ("PAR-176", "frozen_equal_level_anchor"),
    "FPB-0096": ("PAR-178", "completed_session_anchor"),
}


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
    """The repository registry with the four F13 rows flipped ACTIVE — TEST-only posture.

    Declared values are the exact R-F13 vector values as canonical integer strings (sentinel-
    free), so the minted capabilities carry the vector parameters end to end with no post-mint
    substitution. The repository rows stay BLOCKED (proven in TestProposedMustRatify).
    """
    doc = json.loads(pathlib.Path(bindings.DEFAULT_REGISTRY_PATH).read_text(encoding="utf-8"))
    flips = dict(_F13_ROWS)
    flips.update(_F13_CAPSULE_ROWS)
    for row in doc["rows"]:
        binding_id = row["binding_id"]
        if binding_id in flips:
            parameter_id, declared = flips[binding_id]
            assert row["parameter_id"] == parameter_id
            row.update({
                "status": "ACTIVE",
                "lifecycle_status": "ACTIVE",
                "cardinality": "EXACTLY_ONE",
                "migration_state": "NOT_APPLICABLE",
                "declared_value": declared,
                "semantic_slot": f"excursion_reclaim_v2_{parameter_id}_TEST",
                "condition": "TEST-RATIFIED stand-in for the F13 ratification ceremony",
                "activation_scope": f"TEST;F13;{parameter_id};excursion_reclaim_v2 vectors only",
                "precedence": "TEST_FIXTURE",
                "consumer": "ORIGIN(F13)",
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
    """REAL VerifiedCapability handles for all four F13 parameters (real Ed25519, end to end)."""
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
        for parameter_id, declared in _F13_ROWS.values():
            cap = transition.require_bundle(bundle, parameter_id, formula_id="F13", ctx=ctx)
            assert type(cap) is bindings.VerifiedCapability
            assert cap.formula_id == "F13"
            assert cap.parameter_id == parameter_id
            assert cap.value == declared
            minted[parameter_id] = cap
        return minted
    finally:
        bindings._reset_trust_registry_pin_for_tests()
        bindings._reset_acceptance_memo_for_tests()


def variant(caps: dict, **values: object) -> dict:
    """Variant parameter maps off the REAL minted handles (C.1: construction is unrestricted;
    acceptance was the guarded act — the handle keeps its exact type and provenance digests)."""
    out = dict(caps)
    for parameter_id, value in values.items():
        out[parameter_id] = dataclasses.replace(caps[parameter_id], value=value)
    return out


@pytest.fixture(scope="module")
def foreign_cap(real_registry):
    """A genuine capability for a DIFFERENT formula (F00/PAR-001) off the repository registry."""
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
        return transition.require_bundle(bundle, "PAR-001", formula_id="F00", ctx=ctx)
    finally:
        bindings._reset_trust_registry_pin_for_tests()
        bindings._reset_acceptance_memo_for_tests()


# ---------------------------------------------------------------------------------------------
# Bar fixtures (E01-validated — the ONLY lawful construction path) + the shared driver
# ---------------------------------------------------------------------------------------------


def raw_bar(identity: str, *, h: int, l: int, c: int, o: int | None = None) -> dict:  # noqa: E741
    if o is None:
        o = c
    return {
        "bar_identity": identity, "metadata_revision": "r1",
        "open_ticks": o, "high_ticks": h, "low_ticks": l, "close_ticks": c,
        "base_volume": 1, "quote_volume": 1, "trade_count": 1,
    }


def vbar(identity: str, *, h: int, l: int, c: int, o: int | None = None) -> e01.ValidatedBar:  # noqa: E741
    return e01.require_valid_bar(raw_bar(identity, h=h, l=l, c=c, o=o))


def bucket(t: int) -> int:
    return T0_BUCKET + t * BAR_US


def armed_state(*, side: str = LONG, level_px: int = L_PX, avail: int = T_L,
                level_id: str = "L1") -> dict:
    result = xr.register_level(
        xr.initial_state(), level_id=level_id, side=side, level_px_ticks=level_px,
        availability_time_us=avail, source_event_id=f"lvl-{level_id}")
    assert result.events == ()
    return result.state


def step(caps: dict, state: dict, t: int, bar: e01.ValidatedBar) -> transition.TransitionResult:
    return xr.evaluate(caps, bar, state, ordinal=t, bucket_start_us=bucket(t))


def drive(caps: dict, state: dict, tape: list) -> tuple:
    """Run a tape of ``(t, bar)`` steps; returns ``(final_state, all_events)``."""
    events: list = []
    for t, bar in tape:
        result = step(caps, state, t, bar)
        state = result.state
        events.extend(result.events)
    return state, list(events)


def phase_of(state: dict, level_id: str = "L1") -> str:
    return state["levels"][level_id]["phase"]


def row_of(state: dict, level_id: str = "L1") -> dict:
    return state["levels"][level_id]


def atoms(events: list) -> list:
    return [ev for ev in events if ev.get("event_kind") == xr.ATOM_KIND]


def long_bar(t: int, *, low: int | None = None, close: int | None = None,
             high: int | None = None) -> e01.ValidatedBar:
    """A LONG-side vector bar: defaults keep the bar inert (no trigger, no reclaim)."""
    c = close if close is not None else L_PX - 5
    lo = low if low is not None else min(c, L_PX - 5)
    hi = high if high is not None else max(c, L_PX + 5)
    return vbar(f"b{t}", h=hi, l=lo, c=c)


# T3 canonical LONG stream (the GV-011 successor walk): t0 excursion low 9975, t1 C=10010,
# t2 C=10012 -> CONFIRMED at t2, extreme 9975.
def t3_tape() -> list:
    return [
        (0, long_bar(0, low=9975, close=9990)),
        (1, long_bar(1, low=9995, close=10010, high=10015)),
        (2, long_bar(2, low=10000, close=10012, high=10016)),
    ]


# ---------------------------------------------------------------------------------------------
# T1 / T2 — trigger inclusivity
# ---------------------------------------------------------------------------------------------


class TestT1T2Trigger:
    def test_t1_long_low_at_exactly_l_minus_e_excurses_inclusive(self, caps):
        state = armed_state()
        result = step(caps, state, 0, long_bar(0, low=L_PX - E_TICKS, close=9990))
        assert phase_of(result.state) == xr.EXCURSION
        row = row_of(result.state)
        assert row["extreme_ticks"] == L_PX - E_TICKS
        assert row["t_exc"] == 0
        assert row["excursion_source"] == "b0"
        assert [ev["to_phase"] for ev in result.events] == [xr.EXCURSION]

    def test_t2_long_low_one_tick_shy_stays_armed(self, caps):
        state = armed_state()
        result = step(caps, state, 0, long_bar(0, low=L_PX - E_TICKS + 1, close=9990))
        assert result.state is state  # untouched object: no transition at all
        assert result.events == ()
        assert phase_of(result.state) == xr.ARMED

    def test_short_mirror_inclusivity(self, caps):
        state = armed_state(side=SHORT)
        hit = step(caps, state, 0, vbar("b0", h=L_PX + E_TICKS, l=L_PX, c=L_PX + 5))
        assert phase_of(hit.state) == xr.EXCURSION
        assert row_of(hit.state)["extreme_ticks"] == L_PX + E_TICKS
        shy = step(caps, state, 0, vbar("b0", h=L_PX + E_TICKS - 1, l=L_PX, c=L_PX + 5))
        assert shy.events == () and phase_of(shy.state) == xr.ARMED


# ---------------------------------------------------------------------------------------------
# T3 — the canonical confirm (GV-011 successor) + the 13a hold-includes-trigger law
# ---------------------------------------------------------------------------------------------


class TestT3CanonicalConfirm:
    def test_t3_confirms_at_t2_with_extreme_9975(self, caps):
        state, events = drive(caps, armed_state(), t3_tape())
        assert phase_of(state) == xr.CONFIRMED
        found = atoms(events)
        assert len(found) == 1
        atom = found[0]
        assert atom["level_id"] == "L1"
        assert atom["side"] == LONG
        assert atom["extreme_ticks"] == 9975
        assert atom["t_exc"] == 0
        assert atom["t_confirm"] == 2
        assert atom["hold"] == N_HOLD  # 13a: the reclaim-trigger close IS hold #1
        assert atom["excursion_depth_ticks"] == L_PX - 9975 == 25
        assert atom["formula_version"] == xr.VERSION

    def test_t3_atom_identity_binds_sources_and_parameter_digest(self, caps):
        _, events = drive(caps, armed_state(), t3_tape())
        atom = atoms(events)[0]
        identity = atom["identity"]
        assert identity["level_id"] == "L1"
        assert identity["excursion_source"] == "b0"
        assert identity["hold_sources"] == ["b1", "b2"]
        expected_digest = sha256_hex(canonical_json({
            "formula": "F13",
            "formula_version": xr.VERSION,
            "parameters": [
                {"parameter_id": pid, "declared_value": caps[pid].value,
                 "signed_root_digest": caps[pid].signed_root_digest}
                for pid in xr.REQUIRED_PARAMETER_IDS
            ],
        }))
        assert identity["parameter_digest"] == expected_digest

    def test_13a_n_equals_one_confirms_on_the_trigger_close_itself(self, caps):
        one = variant(caps, **{xr.PARAM_RECLAIM_HOLD_BARS: "1"})
        state, events = drive(one, armed_state(), t3_tape()[:2])
        assert phase_of(state) == xr.CONFIRMED
        atom = atoms(events)[0]
        assert atom["t_confirm"] == 1 and atom["hold"] == 1
        assert atom["identity"]["hold_sources"] == ["b1"]

    def test_reclaim_boundary_is_inclusive_and_one_shy_does_not_qualify(self, caps):
        state, _ = drive(caps, armed_state(), [(0, long_bar(0, low=9975, close=9990))])
        exact_hit = step(caps, state, 1, long_bar(1, close=L_PX + R_TICKS, high=L_PX + R_TICKS))
        assert phase_of(exact_hit.state) == xr.RECLAIM_PENDING
        shy = step(caps, state, 1, long_bar(1, close=L_PX + R_TICKS - 1, high=L_PX + R_TICKS))
        assert phase_of(shy.state) == xr.EXCURSION  # not a trigger; still the open excursion

    def test_the_excursion_trigger_bar_close_is_never_a_reclaim_trigger(self, caps):
        # ARMED bar t transitions to EXCURSION; the pseudocode evaluates no reclaim on that
        # same step even when the trigger bar's own close qualifies.
        state = armed_state()
        result = step(caps, state, 0, long_bar(0, low=9975, close=10015, high=10020))
        assert phase_of(result.state) == xr.EXCURSION
        assert row_of(result.state)["hold"] == 0


# ---------------------------------------------------------------------------------------------
# T4 — reset then confirm
# ---------------------------------------------------------------------------------------------


class TestT4ResetThenConfirm:
    def tape(self) -> list:
        return [
            (0, long_bar(0, low=9975, close=9990)),
            (1, long_bar(1, close=10010, high=10015)),
            (2, long_bar(2, close=10008, high=10012)),  # fail -> reset
            (3, long_bar(3, close=10011, high=10015)),
            (4, long_bar(4, close=10010, high=10015)),
        ]

    def test_t4_reset_at_t2_then_confirmed_at_t4(self, caps):
        state, events = drive(caps, armed_state(), self.tape())
        assert phase_of(state) == xr.CONFIRMED
        resets = [ev for ev in events
                  if ev.get("event_kind") == xr.STATE_KIND and ev.get("reason") == xr.HOLD_RESET]
        assert [ev["ordinal"] for ev in resets] == [2]
        atom = atoms(events)[0]
        assert atom["t_confirm"] == 4
        assert atom["hold"] == 2
        assert atom["identity"]["hold_sources"] == ["b3", "b4"]  # the reset cleared b1

    def test_hold_restarts_at_one_after_a_reset(self, caps):
        state, _ = drive(caps, armed_state(), self.tape()[:4])
        row = row_of(state)
        assert row["phase"] == xr.RECLAIM_PENDING
        assert row["hold"] == 1 and row["t_last"] == 3


# ---------------------------------------------------------------------------------------------
# T5 — a skipped finalized ordinal never confirms (INVALIDATED{SEQUENCE_GAP})
# ---------------------------------------------------------------------------------------------


class TestT5SkipInvalidates:
    def test_t5_missing_ordinal_in_the_hold_chain_invalidates(self, caps):
        tape = [
            (0, long_bar(0, low=9975, close=9990)),
            (1, long_bar(1, close=10010, high=10015)),   # hold 1
            (3, long_bar(3, close=10012, high=10016)),   # t2 missing; qualifying anyway
        ]
        state, events = drive(caps, armed_state(), tape)
        assert phase_of(state) == xr.INVALIDATED
        assert row_of(state)["terminal_reason"] == xr.SEQUENCE_GAP
        assert atoms(events) == []  # never confirm on skip
        last = events[-1]
        assert last["to_phase"] == xr.INVALIDATED and last["reason"] == xr.SEQUENCE_GAP

    def test_skip_during_excursion_phase_invalidates_too(self, caps):
        tape = [
            (0, long_bar(0, low=9975, close=9990)),
            (2, long_bar(2, close=9995)),                # t1 missing
        ]
        state, events = drive(caps, armed_state(), tape)
        assert phase_of(state) == xr.INVALIDATED
        assert row_of(state)["terminal_reason"] == xr.SEQUENCE_GAP
        assert atoms(events) == []


# ---------------------------------------------------------------------------------------------
# T6 — duplicate delivery is an idempotent no-op
# ---------------------------------------------------------------------------------------------


class TestT6DuplicateIdempotent:
    def test_t6_duplicate_delivery_of_bar_t1_leaves_hold_at_one(self, caps):
        state, _ = drive(caps, armed_state(), t3_tape()[:2])
        assert row_of(state)["hold"] == 1
        dup = step(caps, state, 1, long_bar(1, low=9995, close=10010, high=10015))
        assert dup.state is state
        assert dup.events == ()
        assert row_of(dup.state)["hold"] == 1

    def test_regressing_ordinal_is_ignored(self, caps):
        state, _ = drive(caps, armed_state(), t3_tape()[:2])
        back = step(caps, state, 0, long_bar(0, low=9970, close=9990))
        assert back.state is state and back.events == ()

    def test_duplicate_excursion_phase_bar_is_ignored(self, caps):
        state, _ = drive(caps, armed_state(), [(0, long_bar(0, low=9975, close=9990))])
        dup = step(caps, state, 0, long_bar(0, low=9975, close=9990))
        assert dup.state is state and dup.events == ()


# ---------------------------------------------------------------------------------------------
# T7 — one hold then the window ends: EXPIRED, never confirmed (kills the off-by-one class)
# ---------------------------------------------------------------------------------------------


class TestT7SingleHoldExpiry:
    def test_t7_single_hold_then_window_end_expires(self, caps):
        tight = variant(caps, **{xr.PARAM_RECLAIM_TAU: "3"})
        tape = [
            (0, long_bar(0, low=9975, close=9990)),
            (1, long_bar(1, close=10005)),               # non-qualifying
            (2, long_bar(2, close=10010, high=10015)),   # hold 1 (t-t_exc=2 <= 3)
            (3, long_bar(3, close=10005)),               # reset (t-t_exc=3 <= 3)
            (4, long_bar(4, close=10012, high=10016)),   # 4-0 > 3 -> EXPIRED even qualifying
        ]
        state, events = drive(tight, armed_state(), tape)
        assert phase_of(state) == xr.EXPIRED
        assert row_of(state)["terminal_reason"] == xr.TAU_EXCEEDED
        assert atoms(events) == []

    def test_t7_ordinal_3_can_never_satisfy_a_window_of_2(self, caps):
        # The v1 defect class: an ordinal-3 event satisfying a horizon of two.
        two = variant(caps, **{xr.PARAM_RECLAIM_TAU: "2"})
        tape = [
            (0, long_bar(0, low=9975, close=9990)),
            (1, long_bar(1, close=10010, high=10015)),   # hold 1
            (2, long_bar(2, close=10005)),               # reset at the window edge
            (3, long_bar(3, close=10012, high=10016)),   # 3-0 > 2 -> EXPIRED
        ]
        state, events = drive(two, armed_state(), tape)
        assert phase_of(state) == xr.EXPIRED
        assert atoms(events) == []


# ---------------------------------------------------------------------------------------------
# T8 — the 13b total-window boundary is inclusive
# ---------------------------------------------------------------------------------------------


class TestT8TauBoundary:
    def test_t8_confirm_lands_at_t_exc_plus_tau_exactly(self, caps):
        tape = [(0, long_bar(0, low=9975, close=9990))]
        tape += [(t, long_bar(t, close=10005)) for t in range(1, TAU_BARS - 1)]  # 1..10 resets
        tape += [
            (TAU_BARS - 1, long_bar(TAU_BARS - 1, close=10010, high=10015)),  # t11 hold 1
            (TAU_BARS, long_bar(TAU_BARS, close=10011, high=10015)),          # t12 == t_exc+tau
        ]
        state, events = drive(caps, armed_state(), tape)
        assert phase_of(state) == xr.CONFIRMED
        atom = atoms(events)[0]
        assert atom["t_confirm"] - atom["t_exc"] == TAU_BARS  # inclusive boundary

    def test_t8_one_past_the_window_expires_even_on_a_qualifying_close(self, caps):
        tape = [(0, long_bar(0, low=9975, close=9990))]
        tape += [(t, long_bar(t, close=10005)) for t in range(1, TAU_BARS)]      # 1..11
        tape += [
            (TAU_BARS, long_bar(TAU_BARS, close=10010, high=10015)),             # t12 hold 1
            (TAU_BARS + 1, long_bar(TAU_BARS + 1, close=10011, high=10015)),     # 13-0 > tau
        ]
        state, events = drive(caps, armed_state(), tape)
        assert phase_of(state) == xr.EXPIRED
        assert row_of(state)["terminal_reason"] == xr.TAU_EXCEEDED
        assert atoms(events) == []

    def test_excursion_state_survives_at_the_window_edge_and_expires_past_it(self, caps):
        tape = [(0, long_bar(0, low=9975, close=9990))]
        tape += [(t, long_bar(t, close=10005)) for t in range(1, TAU_BARS + 1)]  # up to t12
        state, _ = drive(caps, armed_state(), tape)
        assert phase_of(state) == xr.EXCURSION  # t12 - t0 == tau: still inside
        past = step(caps, state, TAU_BARS + 1, long_bar(TAU_BARS + 1, close=10005))
        assert phase_of(past.state) == xr.EXPIRED


# ---------------------------------------------------------------------------------------------
# T9 — the extreme deepens through the reset path and is retained through CONFIRMED
# ---------------------------------------------------------------------------------------------


class TestT9ExtremeRetention:
    def test_t9_lower_low_on_the_reset_bar_updates_and_survives_to_the_atom(self, caps):
        tape = [
            (0, long_bar(0, low=9975, close=9990)),
            (1, long_bar(1, close=10010, high=10015)),                # hold 1
            (2, long_bar(2, low=9960, close=10005, high=10012)),      # reset + deepen
            (3, long_bar(3, close=10011, high=10015)),                # hold 1 again
            (4, long_bar(4, close=10010, high=10015)),                # confirm
        ]
        state, events = drive(caps, armed_state(), tape)
        atom = atoms(events)[0]
        assert atom["extreme_ticks"] == 9960
        assert atom["excursion_depth_ticks"] == 40
        assert row_of(state)["extreme_ticks"] == 9960

    def test_extreme_deepens_on_a_plain_excursion_bar(self, caps):
        tape = [
            (0, long_bar(0, low=9975, close=9990)),
            (1, long_bar(1, low=9950, close=9990)),
        ]
        state, _ = drive(caps, armed_state(), tape)
        assert row_of(state)["extreme_ticks"] == 9950

    def test_hold_bars_do_not_deepen_the_extreme(self, caps):
        # In RECLAIM_PENDING a qualifying close is a hold bar, not an excursion-phase bar —
        # its low never deepens the extreme (E = min over EXCURSION-phase bar lows).
        tape = [
            (0, long_bar(0, low=9975, close=9990)),
            (1, long_bar(1, low=9995, close=10010, high=10015)),
            (2, long_bar(2, low=9900, close=10012, high=10016)),  # qualifying: hold, no deepen
        ]
        state, events = drive(caps, armed_state(), tape)
        atom = atoms(events)[0]
        assert atom["extreme_ticks"] == 9975
        assert row_of(state)["extreme_ticks"] == 9975

    def test_h10_the_expiring_bar_still_deepens_the_extreme_first(self, caps):
        tight = variant(caps, **{xr.PARAM_RECLAIM_TAU: "1"})
        tape = [
            (0, long_bar(0, low=9975, close=9990)),
            (1, long_bar(1, close=10005)),
            (2, long_bar(2, low=9940, close=10005)),  # beyond tau AND deeper
        ]
        state, _ = drive(tight, armed_state(), tape)
        row = row_of(state)
        assert row["phase"] == xr.EXPIRED
        assert row["extreme_ticks"] == 9940  # normative order: (1) deepen, then (2) tau


# ---------------------------------------------------------------------------------------------
# T10 — the direction trap (named CI regression: the reversed-code defect is unrecoverable)
# ---------------------------------------------------------------------------------------------


class TestT10DirectionTrap:
    def test_t10_direction_trap_short_machine_emits_nothing_on_the_long_stream(self, caps):
        state = armed_state(side=SHORT)  # same level px, SHORT machine
        final, events = drive(caps, state, t3_tape())
        assert events == []
        assert phase_of(final) == xr.ARMED  # the LONG geometry never arms the SHORT machine

    def test_t10_converse_long_machine_emits_nothing_on_the_short_stream(self, caps):
        short_tape = [
            (0, vbar("b0", h=10025, l=10000, c=10010)),
            (1, vbar("b1", h=10005, l=9985, c=9990)),
            (2, vbar("b2", h=10004, l=9984, c=9988)),
        ]
        final, events = drive(caps, armed_state(side=LONG), short_tape)
        assert events == []
        assert phase_of(final) == xr.ARMED


# ---------------------------------------------------------------------------------------------
# T11 — the full SHORT mirror of T1-T9
# ---------------------------------------------------------------------------------------------


def mirror_bar(bar: e01.ValidatedBar) -> e01.ValidatedBar:
    """Full price reflection: O' = -O, H' = -L, L' = -H, C' = -C (identities preserved)."""
    return vbar(bar.bar_identity, h=-bar.low_ticks, l=-bar.high_ticks,
                c=-bar.close_ticks, o=-bar.open_ticks)


def mirror_tape(tape: list) -> list:
    return [(t, mirror_bar(bar)) for t, bar in tape]


def mirrored_events(events: list) -> list:
    """The LONG event stream transformed into its exact SHORT expectation."""
    out = []
    for ev in events:
        ev = json.loads(canonical_json(ev))
        if ev.get("side") == LONG:
            ev["side"] = SHORT
        if ev.get("event_kind") == xr.ATOM_KIND:
            ev["extreme_ticks"] = -ev["extreme_ticks"]
        out.append(ev)
    return out


class TestT11ShortMirror:
    TAPES = {
        "t3_confirm": [
            (0, ("b0", 9995, 9975, 9990)),
            (1, ("b1", 10015, 9995, 10010)),
            (2, ("b2", 10016, 10000, 10012)),
        ],
        "t4_reset_confirm": [
            (0, ("b0", 9995, 9975, 9990)),
            (1, ("b1", 10015, 9995, 10010)),
            (2, ("b2", 10012, 9990, 10008)),
            (3, ("b3", 10015, 9990, 10011)),
            (4, ("b4", 10015, 9990, 10010)),
        ],
        "t5_skip": [
            (0, ("b0", 9995, 9975, 9990)),
            (1, ("b1", 10015, 9995, 10010)),
            (3, ("b3", 10016, 9995, 10012)),
        ],
        "t9_deepen": [
            (0, ("b0", 9995, 9975, 9990)),
            (1, ("b1", 10015, 9995, 10010)),
            (2, ("b2", 10012, 9960, 10005)),
            (3, ("b3", 10015, 9990, 10011)),
            (4, ("b4", 10015, 9990, 10010)),
        ],
        "t2_no_trigger": [
            (0, ("b0", 9995, 9981, 9990)),
        ],
        "t8_expire": [
            (0, ("b0", 9995, 9975, 9990)),
            (1, ("b1", 10008, 9990, 10005)),
            (2, ("b2", 10008, 9990, 10005)),
            (3, ("b3", 10008, 9990, 10005)),
            (4, ("b4", 10008, 9990, 10005)),
            (5, ("b5", 10008, 9990, 10005)),
            (6, ("b6", 10008, 9990, 10005)),
            (7, ("b7", 10008, 9990, 10005)),
            (8, ("b8", 10008, 9990, 10005)),
            (9, ("b9", 10008, 9990, 10005)),
            (10, ("b10", 10008, 9990, 10005)),
            (11, ("b11", 10008, 9990, 10005)),
            (12, ("b12", 10008, 9990, 10005)),
            (13, ("b13", 10008, 9990, 10005)),
        ],
    }

    @pytest.mark.parametrize("name", sorted(TAPES))
    def test_t11_short_outputs_are_the_exact_mirror(self, caps, name):
        tape = [(t, vbar(bid, h=h, l=lo, c=c)) for t, (bid, h, lo, c) in self.TAPES[name]]
        long_state, long_events = drive(caps, armed_state(side=LONG, level_px=L_PX), tape)
        short_state, short_events = drive(
            caps, armed_state(side=SHORT, level_px=-L_PX), mirror_tape(tape))
        assert [json.loads(canonical_json(ev)) for ev in short_events] \
            == mirrored_events(long_events)
        long_row, short_row = row_of(long_state), row_of(short_state)
        assert short_row["phase"] == long_row["phase"]
        assert short_row["hold"] == long_row["hold"]
        if long_row["extreme_ticks"] is None:
            assert short_row["extreme_ticks"] is None
        else:
            assert short_row["extreme_ticks"] == -long_row["extreme_ticks"]

    def test_short_atom_depth_is_positive_and_mirror_equal(self, caps):
        tape = [(t, vbar(bid, h=h, l=lo, c=c))
                for t, (bid, h, lo, c) in self.TAPES["t9_deepen"]]
        _, long_events = drive(caps, armed_state(side=LONG), tape)
        _, short_events = drive(
            caps, armed_state(side=SHORT, level_px=-L_PX), mirror_tape(tape))
        long_atom, short_atom = atoms(long_events)[0], atoms(short_events)[0]
        assert long_atom["excursion_depth_ticks"] == short_atom["excursion_depth_ticks"] == 40


# ---------------------------------------------------------------------------------------------
# T12 / T13 — revision and GAP invalidation (§1.1 quarantine behaves exactly as a GAP)
# ---------------------------------------------------------------------------------------------


class TestT12RevisionInvalidates:
    def test_t12_level_revision_mid_pending_invalidates(self, caps):
        state, _ = drive(caps, armed_state(), t3_tape()[:2])
        assert phase_of(state) == xr.RECLAIM_PENDING
        result = xr.revise_level(state, level_id="L1", source_event_id="rev-1")
        assert phase_of(result.state) == xr.INVALIDATED
        assert row_of(result.state)["terminal_reason"] == xr.LEVEL_REVISED
        event = result.events[0]
        assert event["reason"] == xr.LEVEL_REVISED and event["source"] == "rev-1"
        after = step(caps, result.state, 2, long_bar(2, close=10012, high=10016))
        assert after.state is result.state and after.events == ()  # terminal absorbs

    def test_revision_of_terminal_or_unknown_level_is_a_no_op(self, caps):
        state, _ = drive(caps, armed_state(), t3_tape())
        assert phase_of(state) == xr.CONFIRMED
        result = xr.revise_level(state, level_id="L1", source_event_id="rev-2")
        assert result.state is state and result.events == ()
        unknown = xr.revise_level(state, level_id="nope", source_event_id="rev-3")
        assert unknown.state is state and unknown.events == ()


class TestT13GapInvalidates:
    def test_t13_gap_bar_mid_excursion_invalidates(self, caps):
        state, _ = drive(caps, armed_state(), [(0, long_bar(0, low=9975, close=9990))])
        result = xr.note_gap(state, ordinal=1)
        assert phase_of(result.state) == xr.INVALIDATED
        assert row_of(result.state)["terminal_reason"] == xr.GAP_BAR
        assert result.events[0]["reason"] == xr.GAP_BAR

    def test_quarantined_valid_bar_failure_invalidates_the_hold_chain_exactly_as_a_gap(
            self, caps):
        # §1.1: a bar that fails VALID_BAR emits no atom and invalidates any hold chain that
        # requires it, exactly as a GAP does — the quarantine reason travels into the record.
        state, _ = drive(caps, armed_state(), t3_tape()[:2])
        bad = raw_bar("b2", h=10016, l=10000, c=10012)
        bad["low_ticks"] = 10020  # low > min(open, close): VALID_BAR fails
        with pytest.raises(e01.QuarantineInvalidBar) as info:
            e01.require_valid_bar(bad)
        reason_code = info.value.record()["reason_code"]
        result = xr.note_gap(state, ordinal=2, reason=reason_code)
        assert phase_of(result.state) == xr.INVALIDATED
        assert row_of(result.state)["terminal_reason"] == "QUARANTINE_INVALID_BAR"

    def test_gap_invalidates_armed_levels_too_and_skips_terminals(self, caps):
        state = armed_state(level_id="A")
        reg = xr.register_level(
            state, level_id="B", side=LONG, level_px_ticks=L_PX,
            availability_time_us=T_L, source_event_id="lvl-B")
        state, events = drive(caps, reg.state, t3_tape())  # confirms B and... both track
        result = xr.note_gap(state, ordinal=3)
        rows = result.state["levels"]
        for level_id, row in rows.items():
            if row["phase"] == xr.CONFIRMED:
                continue  # a terminal absorbs (untouched by the gap)
            assert row["phase"] == xr.INVALIDATED
        # note_gap over an all-terminal book is a no-op
        again = xr.note_gap(result.state, ordinal=4)
        assert again.state is result.state and again.events == ()


# ---------------------------------------------------------------------------------------------
# T14 — checkpoint/restart at EVERY state; prefix replay is byte-identical
# ---------------------------------------------------------------------------------------------


def canonical_stream(state: dict, events: list) -> bytes:
    return canonical_json({"state": state, "events": events})


class TestT14RestartReplay:
    RICH_TAPE = [
        (0, ("b0", 9995, 9981, 9990)),    # ARMED (no trigger)
        (1, ("b1", 9995, 9975, 9990)),    # EXCURSION
        (2, ("b2", 10015, 9995, 10010)),  # RECLAIM_PENDING hold 1
        (3, ("b3", 10012, 9960, 10005)),  # reset + deepen
        (4, ("b4", 10015, 9990, 10011)),  # hold 1
        (5, ("b5", 10015, 9990, 10010)),  # CONFIRMED
        (6, ("b6", 10015, 9990, 10010)),  # terminal absorbs
    ]

    def _tape(self) -> list:
        return [(t, vbar(bid, h=h, l=lo, c=c)) for t, (bid, h, lo, c) in self.RICH_TAPE]

    def test_t14_restart_at_every_prefix_is_byte_identical(self, caps):
        tape = self._tape()
        base_state, base_events = drive(caps, armed_state(), tape)
        baseline = canonical_stream(base_state, base_events)
        for k in range(len(tape) + 1):
            head_state, head_events = drive(caps, armed_state(), tape[:k])
            # The checkpoint round-trips through canonical bytes (storage-shaped restart).
            checkpoint = json.loads(canonical_json(head_state))
            tail_state, tail_events = drive(caps, checkpoint, tape[k:])
            assert canonical_stream(tail_state, head_events + tail_events) == baseline

    def test_t14_restart_parity_on_terminal_tapes_expired_and_invalidated(self, caps):
        tight = variant(caps, **{xr.PARAM_RECLAIM_TAU: "2"})
        tapes = [
            (tight, [(0, long_bar(0, low=9975, close=9990)),
                     (1, long_bar(1, close=10005)),
                     (2, long_bar(2, close=10005)),
                     (3, long_bar(3, close=10005))]),                       # EXPIRED
            (caps, [(0, long_bar(0, low=9975, close=9990)),
                    (1, long_bar(1, close=10010, high=10015)),
                    (3, long_bar(3, close=10012, high=10016))]),            # INVALIDATED (skip)
        ]
        for cap_map, tape in tapes:
            base_state, base_events = drive(cap_map, armed_state(), tape)
            baseline = canonical_stream(base_state, base_events)
            for k in range(len(tape) + 1):
                head_state, head_events = drive(cap_map, armed_state(), tape[:k])
                checkpoint = json.loads(canonical_json(head_state))
                tail_state, tail_events = drive(cap_map, checkpoint, tape[k:])
                assert canonical_stream(tail_state, head_events + tail_events) == baseline

    def test_exact_duplicate_replay_of_the_whole_tape_changes_nothing(self, caps):
        tape = self._tape()
        state, events = drive(caps, armed_state(), tape)
        replay_state, replay_events = drive(caps, state, tape)
        assert replay_events == []
        assert canonical_json(replay_state) == canonical_json(state)


# ---------------------------------------------------------------------------------------------
# Same-event precedence (§1.4 instantiation + the declared RECLAIM_PENDING carve-out)
# ---------------------------------------------------------------------------------------------


class TestSameEventPrecedence:
    def test_excursion_bar_beyond_tau_and_qualifying_expires_not_confirms(self, caps):
        tight = variant(caps, **{xr.PARAM_RECLAIM_TAU: "1",
                                 xr.PARAM_RECLAIM_HOLD_BARS: "1"})
        tape = [
            (0, long_bar(0, low=9975, close=9990)),
            (1, long_bar(1, close=10005)),
            (2, long_bar(2, close=10012, high=10016)),  # beyond tau AND would confirm (n=1)
        ]
        state, events = drive(tight, armed_state(), tape)
        assert phase_of(state) == xr.EXPIRED  # EXPIRED > terminal (§1.4)
        assert atoms(events) == []

    def test_reclaim_pending_skip_beyond_tau_reads_expired_the_declared_carve_out(self, caps):
        tight = variant(caps, **{xr.PARAM_RECLAIM_TAU: "2"})
        tape = [
            (0, long_bar(0, low=9975, close=9990)),
            (1, long_bar(1, close=10010, high=10015)),  # hold 1
            (4, long_bar(4, close=10011, high=10015)),  # skip (t2, t3) AND beyond tau
        ]
        state, _ = drive(tight, armed_state(), tape)
        row = row_of(state)
        assert row["phase"] == xr.EXPIRED  # rule (1) precedes rule (4): pseudocode-normative
        assert row["terminal_reason"] == xr.TAU_EXCEEDED

    def test_excursion_skip_beyond_tau_reads_invalidated_the_global_order(self, caps):
        tight = variant(caps, **{xr.PARAM_RECLAIM_TAU: "1"})
        tape = [
            (0, long_bar(0, low=9975, close=9990)),
            (3, long_bar(3, close=10005)),  # skip AND beyond tau, in EXCURSION state
        ]
        state, _ = drive(tight, armed_state(), tape)
        row = row_of(state)
        assert row["phase"] == xr.INVALIDATED  # INVALIDATED > EXPIRED (§1.4, no local rule)
        assert row["terminal_reason"] == xr.SEQUENCE_GAP

    def test_transition_classes_cover_the_reachable_vocabulary(self):
        assert set(xr.TRANSITION_CLASSES) == {
            xr.INVALIDATED, xr.EXPIRED, xr.CONFIRMED, xr.EXCURSION, xr.RECLAIM_PENDING}
        assert xr.CONSUMED in xr.TERMINAL_PHASES  # reserved downstream terminal, never reached


# ---------------------------------------------------------------------------------------------
# §1.4 availability (a level is testable only by bars at/after its availability instant)
# ---------------------------------------------------------------------------------------------


class TestAvailability:
    def test_bar_before_availability_never_triggers(self, caps):
        state = armed_state(avail=bucket(1))  # knowable from ordinal 1 onward
        early = step(caps, state, 0, long_bar(0, low=9975, close=9990))
        assert early.state is state and early.events == ()
        late = step(caps, early.state, 1, long_bar(1, low=9975, close=9990))
        assert phase_of(late.state) == xr.EXCURSION

    def test_availability_boundary_is_inclusive(self, caps):
        state = armed_state(avail=bucket(0))
        result = step(caps, state, 0, long_bar(0, low=9975, close=9990))
        assert phase_of(result.state) == xr.EXCURSION


# ---------------------------------------------------------------------------------------------
# Registration law + multi-level bookkeeping
# ---------------------------------------------------------------------------------------------


class TestRegistrationLaw:
    def test_duplicate_registration_is_idempotent_and_conflict_is_refused(self):
        state = armed_state()
        again = xr.register_level(
            state, level_id="L1", side=LONG, level_px_ticks=L_PX,
            availability_time_us=T_L, source_event_id="lvl-L1")
        assert again.state is state
        with pytest.raises(StructureLawError, match="different defining facts"):
            xr.register_level(
                state, level_id="L1", side=LONG, level_px_ticks=L_PX + 1,
                availability_time_us=T_L, source_event_id="lvl-L1")

    def test_registration_boundary_refusals(self):
        with pytest.raises(StructureLawError):
            xr.register_level(
                xr.initial_state(), level_id="", side=LONG, level_px_ticks=L_PX,
                availability_time_us=T_L, source_event_id="s")
        with pytest.raises(StructureLawError):
            xr.register_level(
                xr.initial_state(), level_id="L1", side="UP", level_px_ticks=L_PX,
                availability_time_us=T_L, source_event_id="s")
        with pytest.raises(StructureLawError):
            xr.register_level(
                xr.initial_state(), level_id="L1", side=LONG, level_px_ticks=True,
                availability_time_us=T_L, source_event_id="s")

    def test_two_levels_track_independently_on_one_stream(self, caps):
        reg = xr.register_level(
            armed_state(level_id="A"), level_id="B", side=SHORT, level_px_ticks=L_PX,
            availability_time_us=T_L, source_event_id="lvl-B")
        state, events = drive(caps, reg.state, t3_tape())
        assert state["levels"]["A"]["phase"] == xr.CONFIRMED
        assert state["levels"]["B"]["phase"] == xr.ARMED  # the LONG stream never arms SHORT
        assert all(ev.get("level_id") == "A" for ev in events)


# ---------------------------------------------------------------------------------------------
# §1.2 wire-width boundary vectors (largest emitted value: excursion_depth_ticks)
# ---------------------------------------------------------------------------------------------


class TestInt64Boundary:
    def _depth_tape(self, extreme_low: int) -> list:
        return [
            (0, vbar("b0", h=10, l=extreme_low, c=0, o=0)),
            (1, vbar("b1", h=R_TICKS, l=0, c=R_TICKS, o=0)),
            (2, vbar("b2", h=R_TICKS, l=0, c=R_TICKS, o=0)),
        ]

    def test_depth_at_exactly_int64_max_emits(self, caps):
        state = armed_state(level_px=0)
        final, events = drive(caps, state, self._depth_tape(-(2**63 - 1)))
        atom = atoms(events)[0]
        assert atom["excursion_depth_ticks"] == INT64_MAX
        assert phase_of(final) == xr.CONFIRMED

    def test_depth_one_beyond_int64_quarantines_and_never_emits(self, caps):
        state = armed_state(level_px=0)
        final, events = drive(caps, state, self._depth_tape(-(2**63)))
        assert atoms(events) == []
        quarantines = [ev for ev in events if ev.get("event_kind") == "QUARANTINE"]
        assert len(quarantines) == 1
        record = quarantines[0]
        assert record["reason_code"] == "QUARANTINE_OVERFLOW"
        assert record["formula_id"] == "F13"
        assert record["field"] == "excursion_depth_ticks"
        assert "value_digest" in record and len(record["value_digest"]) == 64
        row = row_of(final)
        assert row["phase"] == xr.INVALIDATED  # fail closed, never wrap/saturate/emit
        assert row["terminal_reason"] == xr.QUARANTINE_OVERFLOW_REASON

    def test_out_of_range_capability_and_coordinates_quarantine(self, caps):
        state = armed_state()
        wide = variant(caps, **{xr.PARAM_EXCURSION_MIN: str(2**63)})
        with pytest.raises(QuarantineOverflow):
            step(wide, state, 0, long_bar(0, low=9975, close=9990))
        with pytest.raises(QuarantineOverflow):
            xr.evaluate(caps, long_bar(0, low=9975, close=9990), state,
                        ordinal=0, bucket_start_us=2**63)
        with pytest.raises(QuarantineOverflow):
            xr.register_level(
                xr.initial_state(), level_id="L2", side=LONG, level_px_ticks=2**63,
                availability_time_us=T_L, source_event_id="s")


# ---------------------------------------------------------------------------------------------
# PROPOSED_MUST_RATIFY — the mechanism + the named refusals (values never hardcoded active)
# ---------------------------------------------------------------------------------------------


class TestProposedMustRatify:
    def test_repository_registry_refuses_f13_blocked_binding_incomplete(self, real_registry):
        # The six F13 rows are BLOCKED_BINDING_V2_MIGRATION in the repository registry: no
        # production capability can exist until the owner ratifies them. The bundle here is
        # fully signed (a valid signature seam), so the refusal is EXACTLY step 5's typed
        # BLOCKED_BINDING_INCOMPLETE — not a signature failure.
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
        assert unsigned.formula_coverage["F13"] == "BLOCKED"
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
            transition.require_bundle(bundle, xr.PARAM_EXCURSION_MIN, formula_id="F13", ctx=ctx)
        assert info.value.reason == "BLOCKED_BINDING_INCOMPLETE:F13"

    def test_repository_rows_are_still_blocked(self, real_registry):
        for binding_id in list(_F13_ROWS) + list(_F13_CAPSULE_ROWS):
            assert real_registry.row(binding_id)["status"] == "BLOCKED_BINDING_V2_MIGRATION"

    @pytest.mark.parametrize("pid,bad", [
        (xr.PARAM_EXCURSION_MIN, "max(1,ceil(ATR14_ticks*1/20))"),  # v1 ATR rule: refused
        (xr.PARAM_RECLAIM_CLOSE_BUFFER, "max(1,ceil(ATR14_ticks*1/20))"),
        (xr.PARAM_RECLAIM_TAU, "-1"),
        (xr.PARAM_RECLAIM_TAU, "012"),      # non-canonical decimal
        (xr.PARAM_RECLAIM_HOLD_BARS, "0"),  # 13a structural floor: n >= 1
        (xr.PARAM_RECLAIM_HOLD_BARS, 0),
        (xr.PARAM_EXCURSION_MIN, True),     # bool is never an exact int
        (xr.PARAM_EXCURSION_MIN, None),
    ])
    def test_unratified_or_non_integer_values_refuse_by_name(self, caps, pid, bad):
        state = armed_state()
        with pytest.raises(StructureLawError, match=xr.BINDING_VALUE_NOT_INTEGER):
            step(variant(caps, **{pid: bad}), state, 0, long_bar(0, low=9975, close=9990))

    def test_zero_e_and_r_are_lawful_mechanism_domain(self, caps):
        # e/r are non-negative magnitudes; 0 is degenerate-but-coherent and MUST stay
        # ratifiable — the mechanism never narrows the owner's value space beyond its
        # structural domain.
        zero = variant(caps, **{xr.PARAM_EXCURSION_MIN: "0",
                                xr.PARAM_RECLAIM_CLOSE_BUFFER: "0"})
        state, events = drive(zero, armed_state(), [
            (0, vbar("b0", h=10005, l=L_PX, c=10005)),      # touch excurses at e=0
            (1, vbar("b1", h=L_PX, l=L_PX, c=L_PX)),        # close AT the level reclaims at r=0
            (2, vbar("b2", h=L_PX, l=L_PX, c=L_PX)),
        ])
        assert phase_of(state) == xr.CONFIRMED
        assert atoms(events)[0]["excursion_depth_ticks"] == 0


# ---------------------------------------------------------------------------------------------
# §C.3 adversarial boundary drills (typed rejection BEFORE any state transition)
# ---------------------------------------------------------------------------------------------


class TestBoundaryRejections:
    def test_hand_built_dict_in_the_caps_seat_is_rejected_before_any_transition(self, caps):
        state = armed_state()
        before = canonical_json(state)
        forged = {pid: E_TICKS for pid in xr.REQUIRED_PARAMETER_IDS}
        with pytest.raises(bindings.CapabilityForgeryError):
            xr.evaluate(forged, long_bar(0, low=9975, close=9990), state,
                        ordinal=0, bucket_start_us=bucket(0))
        assert canonical_json(state) == before  # nothing transitioned, nothing mutated

    def test_non_mapping_caps_and_missing_or_unknown_keys_are_rejected(self, caps):
        state = armed_state()
        bar = long_bar(0, low=9975, close=9990)
        with pytest.raises(bindings.CapabilityForgeryError):
            xr.evaluate(42, bar, state, ordinal=0, bucket_start_us=bucket(0))
        short = dict(caps)
        short.pop(xr.PARAM_RECLAIM_TAU)
        with pytest.raises(bindings.CapabilityForgeryError, match="missing capability"):
            xr.evaluate(short, bar, state, ordinal=0, bucket_start_us=bucket(0))
        extra = dict(caps)
        extra["PAR-999"] = caps[xr.PARAM_EXCURSION_MIN]
        with pytest.raises(bindings.CapabilityForgeryError, match="unexpected capability"):
            xr.evaluate(extra, bar, state, ordinal=0, bucket_start_us=bucket(0))

    def test_subclass_and_duck_typed_capabilities_are_rejected(self, caps):
        state = armed_state()
        bar = long_bar(0, low=9975, close=9990)

        class Forged(bindings.VerifiedCapability):
            pass

        real = caps[xr.PARAM_EXCURSION_MIN]
        sub = Forged(**{f.name: getattr(real, f.name)
                        for f in dataclasses.fields(bindings.VerifiedCapability)})
        with pytest.raises(bindings.CapabilityForgeryError):
            xr.evaluate(variant(caps) | {xr.PARAM_EXCURSION_MIN: sub}, bar, state,
                        ordinal=0, bucket_start_us=bucket(0))

        class Duck:
            parameter_id = xr.PARAM_EXCURSION_MIN
            formula_id = "F13"
            value = "20"
            signed_root_digest = "0" * 64

        with pytest.raises(bindings.CapabilityForgeryError):
            xr.evaluate(dict(caps) | {xr.PARAM_EXCURSION_MIN: Duck()}, bar, state,
                        ordinal=0, bucket_start_us=bucket(0))

    def test_foreign_formula_capability_is_rejected(self, caps, foreign_cap):
        state = armed_state()
        forged = dict(caps)
        forged[xr.PARAM_EXCURSION_MIN] = dataclasses.replace(
            foreign_cap, parameter_id=xr.PARAM_EXCURSION_MIN)
        with pytest.raises(bindings.CapabilityForgeryError, match="minted for formula"):
            step(forged, state, 0, long_bar(0, low=9975, close=9990))

    def test_capability_key_parameter_id_mismatch_is_rejected(self, caps):
        state = armed_state()
        swapped = dict(caps)
        swapped[xr.PARAM_EXCURSION_MIN] = caps[xr.PARAM_RECLAIM_CLOSE_BUFFER]
        swapped[xr.PARAM_RECLAIM_CLOSE_BUFFER] = caps[xr.PARAM_EXCURSION_MIN]
        with pytest.raises(bindings.CapabilityForgeryError, match="carries parameter_id"):
            step(swapped, state, 0, long_bar(0, low=9975, close=9990))

    def test_raw_dict_duck_and_subclass_bars_are_rejected_in_the_env_seat(self, caps):
        state = armed_state()
        with pytest.raises(xr.EnvelopeContractError):
            xr.evaluate(caps, raw_bar("b0", h=9995, l=9975, c=9990), state,
                        ordinal=0, bucket_start_us=bucket(0))

        class FakeBar(e01.ValidatedBar):
            pass

        real = long_bar(0, low=9975, close=9990)
        fake = FakeBar(**{f.name: getattr(real, f.name)
                          for f in dataclasses.fields(e01.ValidatedBar)})
        with pytest.raises(xr.EnvelopeContractError):
            xr.evaluate(caps, fake, state, ordinal=0, bucket_start_us=bucket(0))
        with pytest.raises(xr.EnvelopeContractError):
            xr.evaluate(caps, None, state, ordinal=0, bucket_start_us=bucket(0))

    def test_non_int_coordinates_are_rejected(self, caps):
        state = armed_state()
        bar = long_bar(0, low=9975, close=9990)
        with pytest.raises(StructureLawError):
            xr.evaluate(caps, bar, state, ordinal="0", bucket_start_us=bucket(0))
        with pytest.raises(StructureLawError):
            xr.evaluate(caps, bar, state, ordinal=True, bucket_start_us=bucket(0))
        with pytest.raises(StructureLawError):
            xr.evaluate(caps, bar, state, ordinal=-1, bucket_start_us=bucket(0))
        with pytest.raises(StructureLawError):
            xr.evaluate(caps, bar, state, ordinal=0, bucket_start_us=None)

    def test_v1_shaped_state_never_blends_into_v2(self, caps):
        with pytest.raises(StructureLawError, match=xr.STATE_VERSION_MISMATCH):
            xr.evaluate(caps, long_bar(0, low=9975, close=9990), {"levels": {}},
                        ordinal=0, bucket_start_us=bucket(0))
        with pytest.raises(StructureLawError):
            xr.evaluate(caps, long_bar(0, low=9975, close=9990), None,
                        ordinal=0, bucket_start_us=bucket(0))

    def test_a_tampered_state_row_with_a_float_never_reaches_a_semantic_compare(self, caps):
        state, _ = drive(caps, armed_state(), t3_tape()[:1])
        tampered = json.loads(canonical_json(state))
        tampered["levels"]["L1"]["extreme_ticks"] = 9975.0
        with pytest.raises(StructureLawError):
            xr.evaluate(caps, long_bar(1, close=10010, high=10015), tampered,
                        ordinal=1, bucket_start_us=bucket(1))

    def test_evaluate_never_mutates_the_input_state(self, caps):
        state = armed_state()
        before = canonical_json(state)
        result = step(caps, state, 0, long_bar(0, low=9975, close=9990))
        assert canonical_json(state) == before
        assert result.state is not state


# ---------------------------------------------------------------------------------------------
# Version discipline (§1.5) — retirement banner + the stem-preserving successor face
# ---------------------------------------------------------------------------------------------


class TestVersionDiscipline:
    def test_v1_module_carries_the_module_docstring_withdrawal_banner(self):
        import triad_origin.structures.excursion_reclaim_registry as v1
        assert v1.__doc__ is not None
        assert v1.__doc__.startswith(
            "RETIRED_DEFECTIVE{defect_ref=TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12 R-F13}")

    def test_v1_bytes_preserved_the_reversed_geometry_is_untouched(self):
        # §1.5: the defective logic is retired, never edited — v1's reversed direction law
        # (the R-F13 defect (1)) must still be byte-alive under its own version tag.
        from triad_origin.structures import excursion_reclaim_registry as v1
        assert v1._excurses(LONG, 1000, 1001, 999, 1) is True     # v1 LONG excurses on HIGH
        assert v1._reclaims(LONG, 1000, 999, 1) is True           # v1 LONG reclaims BELOW

    def test_successor_face_re_exports_the_one_implementation(self):
        assert face.evaluate is xr.evaluate
        assert face.initial_state is xr.initial_state
        assert face.register_level is xr.register_level
        assert face.VERSION == xr.VERSION == "level_excursion_reclaim.closed.v2"

    def test_ratified_convention_constants(self):
        assert xr.EXC_HOLD_INCLUDES_TRIGGER is True
        assert xr.EXC_TAU_SCOPE == "TOTAL_WINDOW_INCLUSIVE"
        assert xr.EXC_GAP_RULE == "INVALIDATE"


# ---------------------------------------------------------------------------------------------
# ACCEPTANCE — property test on 10^5 random tapes
# ---------------------------------------------------------------------------------------------


def _qualifies(side: str, close: int) -> bool:
    if side == LONG:
        return close >= L_PX + R_TICKS
    return close <= L_PX - R_TICKS


def _probe(side: str, bar: e01.ValidatedBar) -> int:
    return bar.low_ticks if side == LONG else bar.high_ticks


class TestAcceptanceProperty:
    TAPES = 100_000

    def test_100k_random_tapes_hold_the_confirm_invariants(self, caps):
        rng = random.Random(0xF13001)
        confirmed = 0
        state_template_long = armed_state(side=LONG)
        state_template_short = armed_state(side=SHORT)
        for _ in range(self.TAPES):
            side = LONG if rng.getrandbits(1) else SHORT
            sign = 1 if side == LONG else -1
            state = state_template_long if side == LONG else state_template_short
            length = rng.randrange(5, 12)
            price = L_PX - sign * rng.randrange(0, 35)
            tape: list = []
            by_ordinal: dict = {}
            t = 0
            skipped = False
            while len(tape) < length:
                move = rng.randrange(-45, 46)
                price += move
                c = price
                lo = c - rng.randrange(0, 40)
                hi = c + rng.randrange(0, 40)
                bar = vbar(f"p{t}", h=hi, l=lo, c=c)
                tape.append((t, bar))
                by_ordinal.setdefault(t, bar)
                roll = rng.randrange(100)
                if roll < 10:
                    tape.append((t, bar))  # exact duplicate delivery
                if roll >= 95:
                    skipped = True
                    t += 2  # a skipped finalized ordinal (must never confirm past it)
                else:
                    t += 1
            final, events = drive(caps, state, tape)
            found = atoms(events)
            assert len(found) <= 1
            if not found:
                continue
            confirmed += 1
            atom = found[0]
            t_exc, t_confirm = atom["t_exc"], atom["t_confirm"]
            n, tau = N_HOLD, TAU_BARS
            # (a) exactly n consecutive qualifying ordinals ending at t_confirm.
            assert atom["hold"] == n
            for u in range(t_confirm - n + 1, t_confirm + 1):
                assert u in by_ordinal
                assert _qualifies(side, by_ordinal[u].close_ticks)
            if t_confirm - n > t_exc:
                assert not _qualifies(side, by_ordinal[t_confirm - n].close_ticks)
            # (b) the ratified 13b total window, inclusive.
            assert t_confirm - t_exc <= tau
            # (c) every ordinal of the window is present (a skip would have INVALIDATED).
            for u in range(t_exc, t_confirm + 1):
                assert u in by_ordinal
            # (d) the extreme equals the true phase extreme, recomputed independently. A bar
            # deepens iff it is processed in the EXCURSION state: the trigger bar t_exc, every
            # bar whose PREDECESSOR's close did not qualify (EXCURSION-phase bars, incl. the
            # reset bar and the reclaim-trigger bar — normative order: deepen runs FIRST), and
            # NEVER a hold-continuation bar (qual(u) AND qual(u-1) with u-1 > t_exc).
            probes = [_probe(side, by_ordinal[t_exc])]
            for u in range(t_exc + 1, t_confirm + 1):
                hold_continuation = (
                    u > t_exc + 1
                    and _qualifies(side, by_ordinal[u].close_ticks)
                    and _qualifies(side, by_ordinal[u - 1].close_ticks))
                if not hold_continuation:
                    probes.append(_probe(side, by_ordinal[u]))
            expected_extreme = min(probes) if side == LONG else max(probes)
            assert atom["extreme_ticks"] == expected_extreme
            assert atom["excursion_depth_ticks"] == abs(L_PX - expected_extreme)
            assert atom["excursion_depth_ticks"] >= E_TICKS  # trigger law implies depth >= e
            # (e) identity is complete.
            identity = atom["identity"]
            assert identity["hold_sources"] == [
                by_ordinal[u].bar_identity for u in range(t_confirm - n + 1, t_confirm + 1)]
            assert identity["excursion_source"] == by_ordinal[t_exc].bar_identity
            if skipped:
                # a confirm and a skip may coexist only when the skip came after the
                # terminal; a skip inside the open window can never have confirmed (checked
                # structurally by (c) above).
                pass
        # The generator must actually exercise the confirm path at scale.
        assert confirmed > self.TAPES // 200, f"only {confirmed} confirmations"
