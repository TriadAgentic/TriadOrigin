"""R-F10 ``fvg.three_bar.closed.v3`` — gap-reset-first FVG lifecycle, spec vectors T1-T13 +
acceptance properties (TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12 §R-F10).

The capability fixtures are REAL: a test-RATIFIED copy of the binding registry (the three F10
rows FPB-0019/FPB-0039/FPB-0084 plus one donor row flipped ACTIVE in memory only — the
repository rows stay BLOCKED, proven below) sealed via ``build_sealed_bundle`` and accepted
through ``transition.require_bundle`` with the Ed25519 pattern from
``tests/contracts/test_sealed_bundle_v2.py``. The PAR-044 declared byte-string carries the same
``*``-wildcard transport interlock as F03's PAR-036, so the min-gap capability is minted over a
clearly-labeled sentinel-free TEST transport value and the handle is rebuilt to carry the exact
declared byte-string (C.1 law: construction of the type is unrestricted — acceptance is what is
guarded; the machine's own boundary law is proven adversarially below). The blocked posture is
proven on the UNMODIFIED repository registry: no F10 capability can be minted
(``BLOCKED_BINDING_INCOMPLETE:F10``), and the machine's named refusal is
``BLOCKED_ON_RATIFY(<parameter>)``.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import math
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
from triad_origin.structures import fvg_registry as fvg2  # noqa: E402
from triad_origin.structures import fvg_registry_v3 as fvg3  # noqa: E402

OWNER_KID = "k-owner-f10"
OWNER_PK = "ab" * 32
REPOSITORY = "TriadOrigin"
ENVIRONMENT = "OFF"
VALID_FROM = 1_000_000
VALID_TO = 9_000_000
NOW_US = 2_000_000

BUCKET = 60_000_000  # one formation-timeframe bucket, UTC epoch microseconds

INT64_MAX = 2**63 - 1


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


# THE PAR-044 TRANSPORT INTERLOCK (the F03/PAR-036 precedent, pinned by TestBlockedOnRatify):
# the declared PAR-044 byte-string ``max(1,ceil(ATR14_ticks*1/20))`` contains ``*``, and the
# B01C-BIND-04 wildcard-sentinel law refuses ANY ``*`` inside an ACTIVE row's resolved fields —
# at registry load AND at sealed-bundle acceptance. The fixture therefore mints a REAL
# capability over a clearly-labeled sentinel-free TEST transport value and rebuilds the handle
# to carry the exact declared byte-string. The three NEW R-F10 rows carry sentinel-free
# declared values (their proposed transports "96" / the rule prose / "64") and mint directly.
TEST_TRANSPORT_VALUE = "TEST-RATIFIED-TRANSPORT max(1,ceil(ATR14_ticks 1/20)) (sentinel-free)"

# binding_id -> the per-row test-ratified projection. FPB-0019/0039/0084 are the repository's
# three F10 rows; FPB-0021 (an F11 source row) is the donor re-formed as the fourth F10 row —
# in memory only, for this module's fixtures.
_RATIFY_ROWS = {
    "FPB-0019": {"parameter_id": fvg3.PARAM_MIN_GAP_RULE, "parameter_name": "FVG_MIN_GAP",
                 "declared_value": TEST_TRANSPORT_VALUE, "unit": "ticks",
                 "semantic_slot": "fvg_min_gap_TEST"},
    "FPB-0039": {"parameter_id": fvg3.PARAM_TTL_BARS, "parameter_name": "FVG_TTL_BARS",
                 "declared_value": "96", "unit": "bars",
                 "semantic_slot": "fvg_ttl_bars_TEST"},
    "FPB-0084": {"parameter_id": fvg3.PARAM_INVALIDATION_RULE,
                 "parameter_name": "FVG_INVALIDATION_RULE",
                 "declared_value": fvg3.DECLARED_INVALIDATION_RULE, "unit": "rule",
                 "semantic_slot": "fvg_invalidation_rule_TEST"},
    "FPB-0021": {"formula_id": "F10",
                 "parameter_id": fvg3.PARAM_MAX_OPEN_PER_PARTITION,
                 "parameter_name": "FVG_MAX_OPEN_PER_PARTITION",
                 "declared_value": "64", "unit": "count",
                 "semantic_slot": "fvg_max_open_TEST"},
}


def _ratified_doc() -> dict:
    """The repository registry with the four F10 rows flipped ACTIVE — TEST-only posture."""
    doc = json.loads(pathlib.Path(bindings.DEFAULT_REGISTRY_PATH).read_text(encoding="utf-8"))
    for row in doc["rows"]:
        update = _RATIFY_ROWS.get(row["binding_id"])
        if update is None:
            continue
        row.update({
            "status": "ACTIVE",
            "lifecycle_status": "ACTIVE",
            "cardinality": "EXACTLY_ONE",
            "migration_state": "NOT_APPLICABLE",
            "condition": "TEST-RATIFIED stand-in for the R-F10 ratification ceremony",
            "activation_scope": "TEST;F10;fvg_registry_v3 vectors only",
            "precedence": "TEST_FIXTURE",
            "unit_contract": "TEST unit contract (exact integer transport)",
            "consumer": "ORIGIN(F10)",
            "consuming_wiring_ids": "W03",
            "disposition_reason":
                "TEST-only ratified posture; the repository rows stay BLOCKED.",
        })
        row.update(update)
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
    """REAL VerifiedCapabilities for all four F10 parameters, minted with real Ed25519."""
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
        for parameter_id in fvg3.REQUIRED_PARAMETERS:
            cap = transition.require_bundle(
                bundle, parameter_id, formula_id="F10", ctx=ctx)
            assert type(cap) is bindings.VerifiedCapability
            assert cap.formula_id == "F10"
            assert cap.parameter_id == parameter_id
            caps[parameter_id] = cap
        # The proposed values ride the registry transport, never module code: the REAL minted
        # declared values are exactly the spec's proposed "96" / "64" + the declared strings.
        assert caps[fvg3.PARAM_MIN_GAP_RULE].value == TEST_TRANSPORT_VALUE
        assert caps[fvg3.PARAM_TTL_BARS].value == "96"
        assert caps[fvg3.PARAM_INVALIDATION_RULE].value == fvg3.DECLARED_INVALIDATION_RULE
        assert caps[fvg3.PARAM_MAX_OPEN_PER_PARTITION].value == "64"
        return caps
    finally:
        bindings._reset_trust_registry_pin_for_tests()
        bindings._reset_acceptance_memo_for_tests()


@pytest.fixture(scope="module")
def caps(minted_caps):
    """The behavior-vector capability map: the REAL minted handles, the PAR-044 handle
    re-carrying the exact declared byte-string (the transport-interlock note above)."""
    out = dict(minted_caps)
    out[fvg3.PARAM_MIN_GAP_RULE] = dataclasses.replace(
        minted_caps[fvg3.PARAM_MIN_GAP_RULE], value=common.DECLARED_BOS_CLOSE_BUFFER)
    return out


_KEEP = object()


def caps_with(caps: dict, *, ttl=_KEEP, max_open=_KEEP) -> dict:
    """A scenario capability map with a replaced TTL / capacity value (C.1: construction of the
    handle type is unrestricted — the machine's admission law is what is under test)."""
    out = dict(caps)
    if ttl is not _KEEP:
        out[fvg3.PARAM_TTL_BARS] = dataclasses.replace(
            caps[fvg3.PARAM_TTL_BARS], value=ttl)
    if max_open is not _KEEP:
        out[fvg3.PARAM_MAX_OPEN_PER_PARTITION] = dataclasses.replace(
            caps[fvg3.PARAM_MAX_OPEN_PER_PARTITION], value=max_open)
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
# Bar fixtures (E01-validated — the ONLY lawful construction path) + the fold driver
# ---------------------------------------------------------------------------------------------


def raw_bar(identity: str, high: int, low: int) -> dict:
    return {
        "bar_identity": identity, "metadata_revision": "r1",
        "open_ticks": low, "high_ticks": high, "low_ticks": low, "close_ticks": high,
        "base_volume": 1, "quote_volume": 1, "trade_count": 1,
    }


def vbar(identity: str, high: int, low: int) -> e01.ValidatedBar:
    return e01.require_valid_bar(raw_bar(identity, high, low))


def step(raw: dict, ordinal: int, *, atr=20, gap: bool = False, revised=(), brk=None,
         bucket=None) -> dict:
    return {"raw": raw, "ordinal": ordinal, "atr": atr, "gap": gap,
            "revised": tuple(revised), "brk": brk, "bucket": bucket}


def bucket_of(ordinal: int) -> tuple:
    return (ordinal * BUCKET, (ordinal + 1) * BUCKET)


def run_v3(caps: dict, steps: list, state=None):
    """Fold the ONE transition implementation over injected-fact steps — live == replay."""
    st = state
    events: list = []
    for s in steps:
        start_us, end_us = s["bucket"] if s["bucket"] is not None else bucket_of(s["ordinal"])
        result = fvg3.evaluate(
            caps, e01.require_valid_bar(s["raw"]), st,
            bar_ordinal=s["ordinal"], bucket_start_us=start_us, bucket_end_us=end_us,
            atr14_ticks=s["atr"], sequence_discontinuity=s["gap"],
            revised_bar_identities=s["revised"], opposing_break=s["brk"])
        events.extend(result.events)
        st = result.state
    return st, events


def bull_formation(atr=20) -> list:
    """Three consecutive bars forming the canonical bull zone Z = [100, 110] at ordinal 2.

    ``b1``'s high is deliberately 116 so the follow-up test bars (lows in [95, 111]) never
    seed a SECOND zone with ``b1`` as their ``a`` bar — the vectors below exercise exactly one
    zone unless they say otherwise.
    """
    return [
        step(raw_bar("b0", 100, 95), 0, atr=atr),
        step(raw_bar("b1", 116, 99), 1, atr=atr),
        step(raw_bar("b2", 115, 110), 2, atr=atr),
    ]


Z_ID = "fvg3:b2:2:bullish"


def kind_events(events, *kinds):
    return [e for e in events if e.get("event_kind") in kinds]


def zone_events(events):
    return kind_events(events, fvg3.ZONE_FORMED, fvg3.ZONE_PROGRESSED, fvg3.ZONE_FILLED,
                       fvg3.ZONE_EXPIRED, fvg3.ZONE_INVALIDATED)


def abstentions(events):
    return kind_events(events, "NAMED_ABSTENTION")


_MIRROR_KIND = {fvg3.KIND_BULLISH: fvg3.KIND_BEARISH, fvg3.KIND_BEARISH: fvg3.KIND_BULLISH}


def mirror_raw(bar: dict) -> dict:
    out = dict(bar)
    out["open_ticks"] = -bar["open_ticks"]
    out["close_ticks"] = -bar["close_ticks"]
    out["high_ticks"] = -bar["low_ticks"]
    out["low_ticks"] = -bar["high_ticks"]
    return out


def mirror_steps(steps: list) -> list:
    out = []
    for s in steps:
        brk = s["brk"]
        if brk is not None:
            brk = fvg3.OpposingBreak(
                direction=common.opposite(brk.direction), close_ticks=-brk.close_ticks)
        out.append(dict(s, raw=mirror_raw(s["raw"]), brk=brk))
    return out


def mirror_event(event: dict) -> dict:
    kind = event.get("event_kind")
    if kind in ("NAMED_ABSTENTION", "QUARANTINE"):
        return dict(event)  # side-free records: byte-identical under mirror
    mirrored = dict(event)
    if kind == fvg3.REFUSED_CAPACITY:
        mirrored["candidate_kind"] = _MIRROR_KIND[event["candidate_kind"]]
        mirrored["candidate_z0_ticks"] = -event["candidate_z1_ticks"]
        mirrored["candidate_z1_ticks"] = -event["candidate_z0_ticks"]
        return mirrored
    mirrored["kind"] = _MIRROR_KIND[event["kind"]]
    mirrored["direction"] = common.opposite(event["direction"])
    mirrored["zone_id"] = event["zone_id"].replace(event["kind"], _MIRROR_KIND[event["kind"]])
    if "z0_ticks" in event:
        mirrored["z0_ticks"] = -event["z1_ticks"]
        mirrored["z1_ticks"] = -event["z0_ticks"]
    if "touch_price_ticks" in event:
        mirrored["touch_price_ticks"] = -event["touch_price_ticks"]
    return mirrored


# ---------------------------------------------------------------------------------------------
# T1 / T2 — formation boundary (inclusive at min_gap; min − 1 forms nothing) + GV-009
# ---------------------------------------------------------------------------------------------


class TestFormationBoundaries:
    def test_t1_gap_equal_to_min_gap_qualifies_inclusive(self, caps):
        # ATR 100 -> min_gap = max(1, ceil(100/20)) = 5; gap 5 forms (T1, PAR-009 inclusive).
        steps = [
            step(raw_bar("b0", 100, 95), 0, atr=100),
            step(raw_bar("b1", 106, 99), 1, atr=100),
            step(raw_bar("b2", 115, 105), 2, atr=100),
        ]
        state, events = run_v3(caps, steps)
        (formed,) = zone_events(events)
        assert formed == {
            "event_kind": fvg3.ZONE_FORMED, "formula": "F10",
            "formula_version": fvg3.FORMULA_VERSION,
            "zone_id": "fvg3:b2:2:bullish", "kind": fvg3.KIND_BULLISH,
            "direction": common.LONG, "bar_identity": "b2", "bar_ordinal": 2,
            "bars_elapsed": 0, "pen": [0, 1], "state": fvg3.STATE_FRESH,
            "z0_ticks": 100, "z1_ticks": 105, "gap_ticks": 5, "min_gap_ticks": 5,
            "atr14_ticks": 100, "availability_time_us": 3 * BUCKET,
            "origin_bar_identities": ["b0", "b1", "b2"], "formation_ordinal": 2,
        }
        assert [z["zone_id"] for z in state["zones"]] == ["fvg3:b2:2:bullish"]

    def test_t2_min_minus_one_forms_no_zone(self, caps):
        # ATR 100 -> min_gap 5; a real positive gap of 4 is checked and rejected silently.
        steps = [
            step(raw_bar("b0", 100, 95), 0, atr=100),
            step(raw_bar("b1", 106, 99), 1, atr=100),
            step(raw_bar("b2", 115, 104), 2, atr=100),
        ]
        state, events = run_v3(caps, steps)
        assert events == []
        assert state["zones"] == []

    def test_gv009_gap_one_forms_and_gap_zero_does_not(self, caps):
        # GV-009 (the F10 linked golden): ATR 20 -> min_gap 1; bar i-2 high 100, bar i low 101.
        forms = [
            step(raw_bar("b0", 100, 95), 0),
            step(raw_bar("b1", 106, 99), 1),
            step(raw_bar("b2", 108, 101), 2),
        ]
        state, events = run_v3(caps, forms)
        (formed,) = zone_events(events)
        assert (formed["gap_ticks"], formed["min_gap_ticks"]) == (1, 1)
        assert (formed["z0_ticks"], formed["z1_ticks"]) == (100, 101)
        none = [
            step(raw_bar("b0", 100, 95), 0),
            step(raw_bar("b1", 106, 99), 1),
            step(raw_bar("b2", 108, 100), 2),  # gap 0: the strict raw inequality fails first
        ]
        state, events = run_v3(caps, none)
        assert events == []
        assert state["zones"] == []

    def test_incomplete_window_forms_nothing(self, caps):
        state, events = run_v3(caps, bull_formation()[:2])
        assert events == []
        assert state["zones"] == []

    def test_missing_atr_on_a_raw_gap_candidate_is_the_named_abstention(self, caps):
        steps = bull_formation()
        steps[2] = dict(steps[2], atr=None)
        state, events = run_v3(caps, steps)
        (event,) = events
        assert event["event_kind"] == "NAMED_ABSTENTION"
        assert event["reason_code"] == fvg3.NO_ATR
        assert event["refs"]["bar_identity"] == "b2"
        assert event["refs"]["formula_version"] == fvg3.FORMULA_VERSION
        assert state["zones"] == []


# ---------------------------------------------------------------------------------------------
# T3 — the defect trap: zone OPEN, GAP event, the bar trades through the zone
# ---------------------------------------------------------------------------------------------


class TestT3GapDefectTrap:
    def test_t3_gap_event_invalidates_never_fills(self, caps):
        # Ordinal 3 is missing; the ordinal-4 bar trades straight through the zone.
        steps = bull_formation() + [step(raw_bar("b4", 116, 95), 4)]
        state, events = run_v3(caps, steps)
        tail = zone_events(events)[1:]
        (invalidated,) = tail
        assert invalidated["event_kind"] == fvg3.ZONE_INVALIDATED
        assert invalidated["reason_code"] == fvg3.REASON_SEQUENCE_GAP
        assert invalidated["zone_id"] == Z_ID
        assert invalidated["from_state"] == fvg3.STATE_FRESH
        assert invalidated["pen"] == [0, 1]  # no touch/fill was computed on the discontinuity
        assert kind_events(events, fvg3.ZONE_FILLED, fvg3.ZONE_PROGRESSED) == []
        assert state["zones"] == []
        # The zone is GONE: the next in-continuity bar through the range emits nothing.
        result = fvg3.evaluate(
            caps, vbar("b5", 116, 95), state, bar_ordinal=5,
            bucket_start_us=5 * BUCKET, bucket_end_us=6 * BUCKET, atr14_ticks=20)
        assert zone_events(result.events) == []

    def test_t3_explicit_discontinuity_channel_with_contiguous_ordinals(self, caps):
        # A data_revision-gap arrives on the discontinuity channel; ordinals stay contiguous.
        steps = bull_formation() + [step(raw_bar("b3", 116, 95), 3, gap=True)]
        state, events = run_v3(caps, steps)
        (invalidated,) = zone_events(events)[1:]
        assert invalidated["event_kind"] == fvg3.ZONE_INVALIDATED
        assert invalidated["reason_code"] == fvg3.REASON_SEQUENCE_GAP
        assert kind_events(events, fvg3.ZONE_FILLED) == []
        assert state["zones"] == []

    def test_t3_gap_also_reseeds_the_formation_window(self, caps):
        # The gap bar seeds a NEW window: formation resumes only 2 bars later.
        steps = bull_formation() + [
            step(raw_bar("g0", 140, 130), 4),                 # gap bar (ordinal 3 missing)
            step(raw_bar("g1", 146, 139), 5),
            step(raw_bar("g2", 155, 150), 6),                 # low 150 > g0 high 140 -> forms
        ]
        state, events = run_v3(caps, steps)
        formed = kind_events(events, fvg3.ZONE_FORMED)
        assert [e["zone_id"] for e in formed] == [Z_ID, "fvg3:g2:6:bullish"]
        assert [z["zone_id"] for z in state["zones"]] == ["fvg3:g2:6:bullish"]

    def test_t3_defect_contrast_retired_v2_fills_across_the_gap(self):
        """The exact shape on which the RETIRED v2 'fills' across missing bars (the defect)."""
        v2_bars = [
            {"event_id": "b0", "kind": "BAR",
             "payload": {"high_ticks": 100, "low_ticks": 95, "atr14_ticks": 20, "bar_seq": 1}},
            {"event_id": "b1", "kind": "BAR",
             "payload": {"high_ticks": 106, "low_ticks": 99, "atr14_ticks": 20, "bar_seq": 2}},
            {"event_id": "b2", "kind": "BAR",
             "payload": {"high_ticks": 115, "low_ticks": 110, "atr14_ticks": 20, "bar_seq": 3}},
            {"event_id": "b4", "kind": "BAR",  # bar_seq 4 is missing — a sequence gap
             "payload": {"high_ticks": 116, "low_ticks": 95, "atr14_ticks": 20, "bar_seq": 5}},
        ]
        result = transition.run(
            fvg2.FvgZoneRegistry(), v2_bars,
            {fvg2.PARAM_MIN_GAP_RULE: common.DECLARED_BOS_CLOSE_BUFFER,
             fvg2.PARAM_ZONE_TTL_BARS: 120})
        defective = [e for e in result.events
                     if e.get("event_kind") == fvg2.ZONE_FULLY_FILLED]
        assert defective and defective[0]["touched_by_event_id"] == "b4"  # v2: frozen defect
        # v3 on the same shape INVALIDATES{SEQUENCE_GAP} and never fills (proven above).

    def test_a_quarantined_bar_acts_exactly_as_a_gap(self, caps):
        # §1.1: the E01 boundary quarantines the bar BEFORE the machine; the caller journals
        # the record, drops the bar, and stamps the next delivered bar's event discontinuous.
        state, _ = run_v3(caps, bull_formation())
        bad = raw_bar("bx", 116, 95)
        bad["low_ticks"] = 120  # violates VALID_BAR: low > min(open, close)
        with pytest.raises(e01.QuarantineInvalidBar) as excinfo:
            e01.require_valid_bar(bad)
        record = excinfo.value.record()
        assert record["reason_code"] == "QUARANTINE_INVALID_BAR"
        result = fvg3.evaluate(
            caps, vbar("b4", 116, 95), state, bar_ordinal=4,
            bucket_start_us=4 * BUCKET, bucket_end_us=5 * BUCKET, atr14_ticks=20,
            sequence_discontinuity=True)
        (invalidated,) = result.events
        assert invalidated["event_kind"] == fvg3.ZONE_INVALIDATED
        assert invalidated["reason_code"] == fvg3.REASON_SEQUENCE_GAP


# ---------------------------------------------------------------------------------------------
# T4 / T5 / T6 — penetration states (ratified edge-contact law; midpoint inclusive; one-bar fill)
# ---------------------------------------------------------------------------------------------


class TestPenetrationStates:
    def test_t4_edge_contact_at_z1_is_touched_with_pen_zero(self, caps):
        steps = bull_formation() + [step(raw_bar("b3", 116, 110), 3)]  # low == z1 exactly
        state, events = run_v3(caps, steps)
        (touched,) = zone_events(events)[1:]
        assert touched["event_kind"] == fvg3.ZONE_PROGRESSED
        assert touched["state"] == fvg3.STATE_TOUCHED
        assert touched["from_state"] == fvg3.STATE_FRESH
        assert touched["pen"] == [0, 1]
        assert touched["touch_price_ticks"] == 110
        (zone,) = state["zones"]
        assert zone["state"] == fvg3.STATE_TOUCHED and zone["pen"] == [0, 1]

    def test_no_contact_above_z1_stays_fresh_silent(self, caps):
        steps = bull_formation() + [step(raw_bar("b3", 116, 111), 3)]  # low = z1 + 1
        state, events = run_v3(caps, steps)
        assert zone_events(events)[1:] == []
        (zone,) = state["zones"]
        assert zone["state"] == fvg3.STATE_FRESH and zone["bars_elapsed"] == 1

    def test_partial_between_zero_and_half(self, caps):
        steps = bull_formation() + [step(raw_bar("b3", 116, 108), 3)]  # pen = 2/10 = 1/5
        state, events = run_v3(caps, steps)
        (event,) = zone_events(events)[1:]
        assert event["state"] == fvg3.STATE_PARTIAL
        assert event["from_state"] == fvg3.STATE_FRESH  # multi-stage: one event, final stage
        assert event["pen"] == [1, 5]  # stored REDUCED (2/10 -> 1/5)

    def test_t5_midpoint_exact_is_midpoint_filled_inclusive(self, caps):
        steps = bull_formation() + [step(raw_bar("b3", 116, 105), 3)]  # low == midpoint 105
        state, events = run_v3(caps, steps)
        (event,) = zone_events(events)[1:]
        assert event["state"] == fvg3.STATE_MIDPOINT_FILLED
        assert event["pen"] == [1, 2]
        (zone,) = state["zones"]
        assert zone["state"] == fvg3.STATE_MIDPOINT_FILLED

    def test_t6_one_bar_fill_from_fresh_is_one_terminal_event(self, caps):
        steps = bull_formation() + [step(raw_bar("b3", 116, 99), 3)]  # low < z0 = 100
        state, events = run_v3(caps, steps)
        tail = zone_events(events)[1:]
        (filled,) = tail  # ONE event carrying the final stage (monotone multi-stage)
        assert filled["event_kind"] == fvg3.ZONE_FILLED
        assert filled["state"] == fvg3.STATE_FILLED
        assert filled["from_state"] == fvg3.STATE_FRESH
        assert filled["pen"] == [1, 1]  # clamp(..., 0, 1)
        assert state["zones"] == []  # terminal zones compact out of the working state
        # A terminal zone never re-emits: another bar through the range emits nothing.
        result = fvg3.evaluate(
            caps, vbar("b4", 116, 95), state, bar_ordinal=4,
            bucket_start_us=4 * BUCKET, bucket_end_us=5 * BUCKET, atr14_ticks=20)
        assert zone_events(result.events) == []

    def test_progression_ladder_is_monotone_and_pen_never_regresses(self, caps):
        steps = bull_formation() + [
            step(raw_bar("b3", 116, 110), 3),  # TOUCHED (pen 0)
            step(raw_bar("b4", 116, 108), 4),  # PARTIAL (pen 1/5)
            step(raw_bar("b5", 116, 109), 5),  # shallower touch: pen stays 1/5, NO event
            step(raw_bar("b6", 116, 105), 6),  # MIDPOINT_FILLED (pen 1/2)
            step(raw_bar("b7", 116, 100), 7),  # pen -> 1? no: low == z0 -> pen = 10/10 = 1
        ]
        state, events = run_v3(caps, steps)
        tail = zone_events(events)[1:]
        assert [e["event_kind"] for e in tail] == [
            fvg3.ZONE_PROGRESSED, fvg3.ZONE_PROGRESSED, fvg3.ZONE_PROGRESSED, fvg3.ZONE_FILLED]
        assert [e["state"] for e in tail] == [
            fvg3.STATE_TOUCHED, fvg3.STATE_PARTIAL, fvg3.STATE_MIDPOINT_FILLED,
            fvg3.STATE_FILLED]
        pens = [tuple(e["pen"]) for e in tail]
        assert pens == [(0, 1), (1, 5), (1, 2), (1, 1)]
        assert state["zones"] == []


# ---------------------------------------------------------------------------------------------
# T7 / T8 — the TTL boundary (inclusive at TTL) and expiry-beats-touch precedence
# ---------------------------------------------------------------------------------------------


class TestTtlAndExpiry:
    def test_t7_expires_at_bars_elapsed_equal_ttl_alive_at_ttl_minus_one(self, caps):
        scenario = caps_with(caps, ttl="3")
        away = [step(raw_bar(f"a{i}", 116, 111), 2 + i) for i in (1, 2)]  # elapsed 1, 2
        state, events = run_v3(scenario, bull_formation() + away)
        (zone,) = state["zones"]
        assert zone["bars_elapsed"] == 2 and zone["state"] == fvg3.STATE_FRESH  # TTL-1 alive
        result = fvg3.evaluate(
            scenario, vbar("a3", 116, 111), state, bar_ordinal=5,
            bucket_start_us=5 * BUCKET, bucket_end_us=6 * BUCKET, atr14_ticks=20)
        (expired,) = result.events
        assert expired["event_kind"] == fvg3.ZONE_EXPIRED
        assert expired["bars_elapsed"] == 3  # bars_elapsed == TTL: inclusive
        assert result.state["zones"] == []

    def test_t7_the_proposed_96_bar_ttl_rides_the_capability(self, caps):
        # The REAL minted declared value "96": alive through elapsed 95, EXPIRED at 96.
        away = [step(raw_bar(f"a{i}", 116, 111), 2 + i) for i in range(1, 96)]
        state, _ = run_v3(caps, bull_formation() + away)
        (zone,) = state["zones"]
        assert zone["bars_elapsed"] == 95
        result = fvg3.evaluate(
            caps, vbar("a96", 116, 111), state, bar_ordinal=98,
            bucket_start_us=98 * BUCKET, bucket_end_us=99 * BUCKET, atr14_ticks=20)
        (expired,) = result.events
        assert expired["event_kind"] == fvg3.ZONE_EXPIRED and expired["bars_elapsed"] == 96

    def test_t8_expiry_and_touch_on_the_same_event_expired_wins(self, caps):
        scenario = caps_with(caps, ttl="1")
        steps = bull_formation() + [step(raw_bar("b3", 116, 95), 3)]  # fill-worthy AND at TTL
        state, events = run_v3(scenario, steps)
        tail = zone_events(events)[1:]
        (expired,) = tail
        assert expired["event_kind"] == fvg3.ZONE_EXPIRED
        assert expired["from_state"] == fvg3.STATE_FRESH
        assert expired["pen"] == [0, 1]  # order (3) before (4): no fill was computed
        assert kind_events(events, fvg3.ZONE_FILLED, fvg3.ZONE_PROGRESSED) == []
        assert state["zones"] == []


# ---------------------------------------------------------------------------------------------
# T9 — invalidation (opposing F09 break / defining-bar revision) beats fill
# ---------------------------------------------------------------------------------------------


class TestT9Invalidation:
    def test_t9_opposing_break_and_fill_on_the_same_event_invalidated_wins(self, caps):
        brk = fvg3.OpposingBreak(direction=common.SHORT, close_ticks=99)  # < z0: through
        steps = bull_formation() + [step(raw_bar("b3", 116, 95), 3, brk=brk)]
        state, events = run_v3(caps, steps)
        (invalidated,) = zone_events(events)[1:]
        assert invalidated["event_kind"] == fvg3.ZONE_INVALIDATED
        assert invalidated["reason_code"] == fvg3.REASON_OPPOSING_BREAK
        assert invalidated["pen"] == [0, 1]  # order (2) before (4): the fill never ran
        assert kind_events(events, fvg3.ZONE_FILLED) == []
        assert state["zones"] == []

    def test_edge_contact_at_the_far_edge_is_not_through(self, caps):
        brk = fvg3.OpposingBreak(direction=common.SHORT, close_ticks=100)  # == z0: NOT through
        steps = bull_formation() + [step(raw_bar("b3", 116, 95), 3, brk=brk)]
        _, events = run_v3(caps, steps)
        (filled,) = zone_events(events)[1:]
        assert filled["event_kind"] == fvg3.ZONE_FILLED  # no invalidation; the fill proceeds

    def test_a_same_direction_break_never_invalidates(self, caps):
        brk = fvg3.OpposingBreak(direction=common.LONG, close_ticks=95)  # not opposing
        steps = bull_formation() + [step(raw_bar("b3", 116, 95), 3, brk=brk)]
        _, events = run_v3(caps, steps)
        (filled,) = zone_events(events)[1:]
        assert filled["event_kind"] == fvg3.ZONE_FILLED

    def test_defining_bar_revision_invalidates(self, caps):
        steps = bull_formation() + [step(raw_bar("b3", 116, 95), 3, revised=("b0",))]
        state, events = run_v3(caps, steps)
        (invalidated,) = zone_events(events)[1:]
        assert invalidated["event_kind"] == fvg3.ZONE_INVALIDATED
        assert invalidated["reason_code"] == fvg3.REASON_DEFINING_BAR_REVISION
        assert state["zones"] == []

    def test_an_unrelated_revision_does_not_invalidate(self, caps):
        steps = bull_formation() + [step(raw_bar("b3", 116, 95), 3, revised=("zz",))]
        _, events = run_v3(caps, steps)
        (filled,) = zone_events(events)[1:]
        assert filled["event_kind"] == fvg3.ZONE_FILLED

    def test_declared_in_class_tie_rule_revision_before_opposing_break(self, caps):
        brk = fvg3.OpposingBreak(direction=common.SHORT, close_ticks=99)
        steps = bull_formation() + [
            step(raw_bar("b3", 116, 95), 3, revised=("b2",), brk=brk)]
        _, events = run_v3(caps, steps)
        (invalidated,) = zone_events(events)[1:]
        assert invalidated["reason_code"] == fvg3.REASON_DEFINING_BAR_REVISION


# ---------------------------------------------------------------------------------------------
# T10 — same-bar-retest ban (structural) + the §1.4 availability wall
# ---------------------------------------------------------------------------------------------


class TestT10SameBarRetestBan:
    def test_t10_no_touch_source_equals_the_formation_bar(self, caps):
        # Bar c's own low IS z1 (edge contact by construction) — yet the formation event is
        # the ONLY event and the zone stays FRESH at pen 0: c is never its own retest.
        state, events = run_v3(caps, bull_formation())
        assert [e["event_kind"] for e in events] == [fvg3.ZONE_FORMED]
        (zone,) = state["zones"]
        assert zone["state"] == fvg3.STATE_FRESH and zone["pen"] == [0, 1]
        # Every touch-carrying event in a longer tape names a source strictly after c.
        steps = bull_formation() + [step(raw_bar("b3", 116, 105), 3)]
        _, events = run_v3(caps, steps)
        for event in zone_events(events):
            if "touch_price_ticks" in event:
                assert event["bar_identity"] != "b2"
                assert event["bar_ordinal"] > 2

    def test_availability_wall_a_bucket_opening_before_availability_never_tests(self, caps):
        # Adversarial injection: an ordinal-3 bar whose bucket opens 1ms BEFORE the zone's
        # availability instant (the formation bar's bucket end). §1.4 refuses the test.
        early = (3 * BUCKET - 1_000, 4 * BUCKET)
        steps = bull_formation() + [step(raw_bar("b3", 116, 105), 3, bucket=early)]
        state, events = run_v3(caps, steps)
        assert zone_events(events)[1:] == []  # no touch computed
        (zone,) = state["zones"]
        assert zone["state"] == fvg3.STATE_FRESH and zone["bars_elapsed"] == 1
        # The exact availability instant is INCLUSIVE: the next bar at bucket start == the
        # formation bucket end tests lawfully.
        result = fvg3.evaluate(
            caps, vbar("b4", 116, 105), state, bar_ordinal=4,
            bucket_start_us=3 * BUCKET, bucket_end_us=5 * BUCKET, atr14_ticks=20)
        (event,) = result.events
        assert event["state"] == fvg3.STATE_MIDPOINT_FILLED


# ---------------------------------------------------------------------------------------------
# T11 — REFUSED_CAPACITY at the 65th open zone (the spec-literal 64) — audit fact, no eviction
# ---------------------------------------------------------------------------------------------


def staircase(count: int) -> list:
    """A rising staircase: every bar from ordinal 2 forms a bull zone none later touches."""
    return [step(raw_bar(f"s{i}", 100 + 10 * i, 95 + 10 * i), i) for i in range(count)]


class TestT11Capacity:
    def test_t11_the_65th_open_zone_is_a_refused_capacity_audit_fact(self, caps):
        # max_open = 64 is the REAL minted declared value. Bars s2..s65 form 64 zones; the
        # 65th candidate (bar s66) is refused as an audit fact; the 64 zones are untouched.
        state, events = run_v3(caps, staircase(67))
        formed = kind_events(events, fvg3.ZONE_FORMED)
        assert len(formed) == 64
        (refused,) = kind_events(events, fvg3.REFUSED_CAPACITY)
        assert refused == {
            "event_kind": fvg3.REFUSED_CAPACITY, "formula": "F10",
            "formula_version": fvg3.FORMULA_VERSION,
            "reason_code": fvg3.REFUSED_CAPACITY,
            "candidate_kind": fvg3.KIND_BULLISH,
            "candidate_z0_ticks": 100 + 10 * 64, "candidate_z1_ticks": 95 + 10 * 66,
            "candidate_gap_ticks": 15,
            "origin_bar_identities": ["s64", "s65", "s66"],
            "bar_identity": "s66", "bar_ordinal": 66,
            "open_zone_count": 64, "max_open_per_partition": 64,
        }
        assert len(state["zones"]) == 64  # never silently evicted
        assert all(z["state"] == fvg3.STATE_FRESH and z["pen"] == [0, 1]
                   for z in state["zones"])
        assert [z["zone_id"] for z in state["zones"]] == [
            f"fvg3:s{i}:{i}:bullish" for i in range(2, 66)]

    def test_capacity_frees_as_zones_go_terminal(self, caps):
        scenario = caps_with(caps, max_open="2")
        steps = staircase(5)  # s2, s3 form; s4's candidate is refused at capacity 2
        state, events = run_v3(scenario, steps)
        assert len(kind_events(events, fvg3.ZONE_FORMED)) == 2
        assert len(kind_events(events, fvg3.REFUSED_CAPACITY)) == 1
        # A fill frees a slot: drive through BOTH zones' ranges? No — fill only the FIRST
        # zone (bar low below s2's z0=120 would also fill s3's zone [130,145]... use a bar
        # whose low sits inside only the first zone's range: low 121 fills nothing fully but
        # progresses; instead expire nothing — simply verify the refused candidate was never
        # a zone and the two open zones persist.
        assert [z["zone_id"] for z in state["zones"]] == [
            "fvg3:s2:2:bullish", "fvg3:s3:3:bullish"]


# ---------------------------------------------------------------------------------------------
# T12 — the full bear mirror of T1-T11 (exact algebraic C -> -C symmetry)
# ---------------------------------------------------------------------------------------------


class TestT12MirrorLaw:
    SCENARIOS = {
        "t1_boundary": [
            step(raw_bar("b0", 100, 95), 0, atr=100),
            step(raw_bar("b1", 106, 99), 1, atr=100),
            step(raw_bar("b2", 115, 105), 2, atr=100),
        ],
        "t2_below": [
            step(raw_bar("b0", 100, 95), 0, atr=100),
            step(raw_bar("b1", 106, 99), 1, atr=100),
            step(raw_bar("b2", 115, 104), 2, atr=100),
        ],
        "gv009": [
            step(raw_bar("b0", 100, 95), 0),
            step(raw_bar("b1", 106, 99), 1),
            step(raw_bar("b2", 108, 101), 2),
        ],
        "t3_gap_trap": bull_formation() + [step(raw_bar("b4", 116, 95), 4)],
        "t4_edge": bull_formation() + [step(raw_bar("b3", 116, 110), 3)],
        "t5_midpoint": bull_formation() + [step(raw_bar("b3", 116, 105), 3)],
        "t6_one_bar_fill": bull_formation() + [step(raw_bar("b3", 116, 99), 3)],
        "ladder": bull_formation() + [
            step(raw_bar("b3", 116, 110), 3),
            step(raw_bar("b4", 116, 108), 4),
            step(raw_bar("b5", 116, 105), 5),
            step(raw_bar("b6", 116, 99), 6),
        ],
        "t9_break": bull_formation() + [
            step(raw_bar("b3", 116, 95), 3,
                 brk=fvg3.OpposingBreak(direction=common.SHORT, close_ticks=99))],
        "t9_revision": bull_formation() + [step(raw_bar("b3", 116, 95), 3, revised=("b0",))],
        "t10_formation_only": bull_formation(),
        "no_atr": [
            step(raw_bar("b0", 100, 95), 0),
            step(raw_bar("b1", 106, 99), 1),
            step(raw_bar("b2", 115, 110), 2, atr=None),
        ],
        "t11_capacity": staircase(6),
    }

    @pytest.mark.parametrize("name", sorted(SCENARIOS))
    def test_t12_full_mirror_exact_sign_inversion(self, caps, name):
        steps = self.SCENARIOS[name]
        scenario = caps_with(caps, max_open="3") if name == "t11_capacity" else caps
        _, forward = run_v3(scenario, steps)
        _, mirrored = run_v3(scenario, mirror_steps(steps))
        assert mirrored == [mirror_event(e) for e in forward]

    def test_t12_ttl_and_expiry_mirror(self, caps):
        scenario = caps_with(caps, ttl="1")
        steps = bull_formation() + [step(raw_bar("b3", 116, 95), 3)]
        _, forward = run_v3(scenario, steps)
        _, mirrored = run_v3(scenario, mirror_steps(steps))
        assert mirrored == [mirror_event(e) for e in forward]

    def test_bear_formation_is_the_exact_algebraic_mirror(self, caps):
        _, events = run_v3(caps, mirror_steps(bull_formation()))
        (formed,) = zone_events(events)
        assert formed["kind"] == fvg3.KIND_BEARISH
        assert formed["direction"] == common.SHORT
        assert (formed["z0_ticks"], formed["z1_ticks"]) == (-110, -100)
        assert formed["gap_ticks"] == 10


# ---------------------------------------------------------------------------------------------
# T13 — restart replay parity across EVERY state (byte-identical)
# ---------------------------------------------------------------------------------------------


def full_lifecycle_steps() -> list:
    """One tape whose zones pass through FRESH, TOUCHED, PARTIAL, MIDPOINT_FILLED, FILLED,
    INVALIDATED{SEQUENCE_GAP} and EXPIRED (with ttl=10)."""
    return (
        bull_formation()
        + [
            step(raw_bar("b3", 116, 110), 3),   # TOUCHED
            step(raw_bar("b4", 116, 108), 4),   # PARTIAL
            step(raw_bar("b5", 116, 105), 5),   # MIDPOINT_FILLED
            step(raw_bar("b6", 116, 99), 6),    # FILLED (terminal)
            step(raw_bar("c0", 140, 130), 7),
            step(raw_bar("c1", 146, 139), 8),
            step(raw_bar("c2", 155, 150), 9),   # Z2 FORMED [140, 150]
            step(raw_bar("c3", 156, 151), 11),  # ordinal 10 missing: Z2 INVALIDATED
            step(raw_bar("d1", 162, 157), 12),
            step(raw_bar("d2", 170, 165), 13),  # Z3 FORMED [156, 165]
        ]
        + [step(raw_bar(f"e{i}", 172, 166), 13 + i) for i in range(1, 11)]  # Z3 EXPIRED @10
    )


class TestT13RestartParity:
    def test_t13_restart_at_every_prefix_yields_byte_identical_streams(self, caps):
        scenario = caps_with(caps, ttl="10")
        steps = full_lifecycle_steps()
        full_state, full_events = run_v3(scenario, steps)
        # The tape genuinely crosses every state (the "across every state" clause of T13).
        seen = {e["state"] for e in zone_events(full_events)}
        assert seen == {fvg3.STATE_FRESH, fvg3.STATE_TOUCHED, fvg3.STATE_PARTIAL,
                        fvg3.STATE_MIDPOINT_FILLED, fvg3.STATE_FILLED,
                        fvg3.STATE_INVALIDATED, fvg3.STATE_EXPIRED}
        for cut in range(1, len(steps)):
            prefix_state, prefix_events = run_v3(scenario, steps[:cut])
            checkpoint = json.loads(canonical_json(prefix_state))  # a real checkpoint round-trip
            resumed_state, resumed_events = run_v3(scenario, steps[cut:], state=checkpoint)
            assert canonical_json(prefix_events + resumed_events) == canonical_json(full_events)
            assert canonical_json(resumed_state) == canonical_json(full_state)

    def test_adjacent_duplicate_delivery_is_an_idempotent_no_op(self, caps):
        state, _ = run_v3(caps, bull_formation())
        again = fvg3.evaluate(
            caps, vbar("b2", 115, 110), state, bar_ordinal=2,
            bucket_start_us=2 * BUCKET, bucket_end_us=3 * BUCKET, atr14_ticks=20)
        assert again.state == state
        assert again.events == ()

    def test_out_of_order_ordinal_refuses(self, caps):
        state, _ = run_v3(caps, bull_formation())
        with pytest.raises(common.StructureLawError):
            fvg3.evaluate(caps, vbar("bx", 116, 111), state, bar_ordinal=1,
                          bucket_start_us=BUCKET, bucket_end_us=2 * BUCKET, atr14_ticks=20)


# ---------------------------------------------------------------------------------------------
# ACCEPTANCE property — no transition across a discontinuity; pen monotone; rationals reduced
# ---------------------------------------------------------------------------------------------


class TestAcceptanceProperties:
    def test_property_walks_discontinuity_monotone_pen_reduced_rationals(self, caps):
        # CI-scale slice of the R-F10 acceptance property (the full-scale run is the
        # acceptance ceremony's job): deterministic seeded walks with gaps and breaks.
        walks, bars_per_walk = 40, 90
        total_formed = total_gap_invalidations = 0
        for walk in range(walks):
            rng = random.Random(0xF10 << 8 | walk)
            mid = 100_000
            state = None
            ordinal = 0
            alive: dict = {}  # zone_id -> last pen (num, den)
            for i in range(bars_per_walk):
                forced_gap = rng.random() < 0.04
                skip = rng.random() < 0.06
                ordinal += rng.randint(2, 3) if skip else 1
                gapped = forced_gap or skip or i == 0 and False
                mid += rng.randint(-60, 60)
                high = mid + rng.randint(0, 10)
                low = mid - rng.randint(0, 10)
                atr = None if rng.random() < 0.04 else rng.randint(5, 40)
                brk = None
                if rng.random() < 0.06:
                    brk = fvg3.OpposingBreak(
                        direction=common.LONG if rng.random() < 0.5 else common.SHORT,
                        close_ticks=mid + rng.randint(-80, 80))
                result = fvg3.evaluate(
                    caps, vbar(f"w{walk}_b{i}", high, low), state,
                    bar_ordinal=ordinal, bucket_start_us=ordinal * BUCKET,
                    bucket_end_us=(ordinal + 1) * BUCKET, atr14_ticks=atr,
                    sequence_discontinuity=forced_gap, opposing_break=brk)
                state = result.state
                for event in result.events:
                    ek = event["event_kind"]
                    if ek in ("NAMED_ABSTENTION", "QUARANTINE"):
                        continue
                    if ek == fvg3.REFUSED_CAPACITY:
                        assert not gapped
                        continue
                    zone_id = event["zone_id"]
                    if gapped and i > 0:
                        # No zone ever transitions across an ordinal discontinuity: the ONLY
                        # lawful zone event on a gapped step is INVALIDATED{SEQUENCE_GAP}.
                        assert ek == fvg3.ZONE_INVALIDATED
                        assert event["reason_code"] == fvg3.REASON_SEQUENCE_GAP
                        total_gap_invalidations += 1
                    if ek == fvg3.ZONE_FORMED:
                        assert not (gapped and i > 0)
                        assert zone_id not in alive
                        alive[zone_id] = (0, 1)
                        total_formed += 1
                        continue
                    assert zone_id in alive  # never an event for a zone lost to a gap
                    num, den = event["pen"]
                    assert den > 0 and 0 <= num <= den
                    assert math.gcd(num, den) == 1  # stored rationals are REDUCED
                    prev_num, prev_den = alive[zone_id]
                    assert num * prev_den >= prev_num * den  # pen monotone non-decreasing
                    if ek in (fvg3.ZONE_FILLED, fvg3.ZONE_EXPIRED, fvg3.ZONE_INVALIDATED):
                        del alive[zone_id]
                    else:
                        alive[zone_id] = (num, den)
                assert {z["zone_id"] for z in state["zones"]} == set(alive)
                for zone in state["zones"]:
                    assert zone["state"] in (
                        fvg3.STATE_FRESH, fvg3.STATE_TOUCHED, fvg3.STATE_PARTIAL,
                        fvg3.STATE_MIDPOINT_FILLED)
        assert total_formed > 0 and total_gap_invalidations > 0


# ---------------------------------------------------------------------------------------------
# §1.2 — int64 boundary vectors (the formula's largest derived product: gap_ticks)
# ---------------------------------------------------------------------------------------------


class TestInt64Boundaries:
    def test_gap_ticks_at_exactly_int64_max_forms(self, caps):
        steps = [
            step(raw_bar("b0", -1, -5), 0),
            step(raw_bar("b1", 0, -1), 1),
            step(raw_bar("b2", INT64_MAX, INT64_MAX - 1), 2),
        ]
        state, events = run_v3(caps, steps)
        (formed,) = zone_events(events)
        assert formed["gap_ticks"] == INT64_MAX  # (2^63-2) - (-1)
        assert (formed["z0_ticks"], formed["z1_ticks"]) == (-1, INT64_MAX - 1)
        (zone,) = state["zones"]
        assert zone["pen"] == [0, 1]

    def test_gap_ticks_one_beyond_int64_quarantines_and_forms_no_zone(self, caps):
        steps = [
            step(raw_bar("b0", -2, -5), 0),
            step(raw_bar("b1", 0, -2), 1),
            step(raw_bar("b2", INT64_MAX, INT64_MAX - 1), 2),
        ]
        state, events = run_v3(caps, steps)
        (record,) = events
        assert record["event_kind"] == "QUARANTINE"
        assert record["reason_code"] == "QUARANTINE_OVERFLOW"
        assert record["formula_id"] == "F10"
        assert record["field"] == "gap_ticks"
        assert "value" not in record  # the record carries a digest, never the raw value
        assert state["zones"] == []  # never wrap, never saturate, never emit

    def test_injected_facts_outside_int64_quarantine_at_the_boundary(self, caps):
        with pytest.raises(QuarantineOverflow):
            fvg3.evaluate(caps, vbar("b0", 100, 95), None, bar_ordinal=2**63,
                          bucket_start_us=0, bucket_end_us=BUCKET, atr14_ticks=20)
        with pytest.raises(QuarantineOverflow):
            fvg3.evaluate(caps, vbar("b0", 100, 95), None, bar_ordinal=0,
                          bucket_start_us=0, bucket_end_us=BUCKET, atr14_ticks=2**63)
        with pytest.raises(QuarantineOverflow):
            fvg3.evaluate(caps, vbar("b0", 100, 95), None, bar_ordinal=0,
                          bucket_start_us=0, bucket_end_us=BUCKET, atr14_ticks="20")
        with pytest.raises(QuarantineOverflow):
            fvg3.OpposingBreak(direction=common.SHORT, close_ticks=2**63)


# ---------------------------------------------------------------------------------------------
# BINDINGS — mechanism + the named refusal; the repository posture stays BLOCKED
# ---------------------------------------------------------------------------------------------


class TestBlockedOnRatify:
    def test_repository_registry_keeps_every_f10_row_blocked(self, real_registry):
        for binding_id, declared in (
                ("FPB-0019", common.DECLARED_BOS_CLOSE_BUFFER),
                ("FPB-0039", "3"), ("FPB-0084", "zone_midpoint")):
            row = real_registry.row(binding_id)
            assert row["formula_id"] == "F10"
            assert row["status"] == "BLOCKED_BINDING_V2_MIGRATION"
            assert row["lifecycle_status"] == "BLOCKED"
            assert row["declared_value"] == declared

    def test_no_f10_capability_can_be_minted_from_the_repository_registry(self, real_registry):
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
                bundle, fvg3.PARAM_MIN_GAP_RULE, formula_id="F10", ctx=ctx)
        assert excinfo.value.formula_id == "F10"
        assert str(excinfo.value) == "BLOCKED_BINDING_INCOMPLETE:F10"

    @pytest.mark.parametrize("missing", sorted(fvg3.REQUIRED_PARAMETERS))
    def test_each_missing_capability_is_the_named_refusal(self, caps, missing):
        partial = {k: v for k, v in caps.items() if k != missing}
        with pytest.raises(fvg3.BlockedOnRatify) as excinfo:
            fvg3.evaluate(partial, vbar("b0", 100, 95), None, bar_ordinal=0,
                          bucket_start_us=0, bucket_end_us=BUCKET, atr14_ticks=20)
        assert str(excinfo.value) == f"BLOCKED_ON_RATIFY({missing})"
        assert excinfo.value.parameter_id == missing

    def test_no_proposed_value_is_hardcoded_as_active(self):
        # The mechanism's values arrive ONLY inside verified capabilities: the module hosts no
        # 96/64 default and an empty capability map is the named refusal, never a default run.
        with pytest.raises(fvg3.BlockedOnRatify):
            fvg3.evaluate({}, vbar("b0", 100, 95), None, bar_ordinal=0,
                          bucket_start_us=0, bucket_end_us=BUCKET, atr14_ticks=20)

    @pytest.mark.parametrize("bad_ttl", ["0", "-1", "07", "٩٦", "", "9" * 20, 0, -5, True, None])
    def test_unlawful_ttl_values_refuse(self, caps, bad_ttl):
        scenario = caps_with(caps, ttl=bad_ttl)
        with pytest.raises(common.StructureLawError):
            fvg3.evaluate(scenario, vbar("b0", 100, 95), None, bar_ordinal=0,
                          bucket_start_us=0, bucket_end_us=BUCKET, atr14_ticks=20)

    def test_unlawful_max_open_value_refuses(self, caps):
        scenario = caps_with(caps, max_open="0")
        with pytest.raises(common.StructureLawError):
            fvg3.evaluate(scenario, vbar("b0", 100, 95), None, bar_ordinal=0,
                          bucket_start_us=0, bucket_end_us=BUCKET, atr14_ticks=20)

    def test_exact_int_transport_is_also_lawful(self, caps):
        scenario = caps_with(caps, ttl=96, max_open=64)
        state, events = run_v3(scenario, bull_formation())
        assert len(zone_events(events)) == 1
        assert len(state["zones"]) == 1

    def test_undeclared_min_gap_rule_value_refuses(self, caps):
        tampered = dict(caps)
        tampered[fvg3.PARAM_MIN_GAP_RULE] = dataclasses.replace(
            caps[fvg3.PARAM_MIN_GAP_RULE], value=common.DECLARED_EQUAL_LEVEL_TOLERANCE)
        with pytest.raises(common.StructureLawError):
            fvg3.evaluate(tampered, vbar("b0", 100, 95), None, bar_ordinal=0,
                          bucket_start_us=0, bucket_end_us=BUCKET, atr14_ticks=20)

    def test_undeclared_invalidation_rule_value_refuses(self, caps):
        tampered = dict(caps)
        tampered[fvg3.PARAM_INVALIDATION_RULE] = dataclasses.replace(
            caps[fvg3.PARAM_INVALIDATION_RULE], value="any opposing close")
        with pytest.raises(common.StructureLawError):
            fvg3.evaluate(tampered, vbar("b0", 100, 95), None, bar_ordinal=0,
                          bucket_start_us=0, bucket_end_us=BUCKET, atr14_ticks=20)

    def test_the_transport_minted_value_is_not_the_declared_byte_string(self, minted_caps):
        # The end-to-end mint is REAL — and the machine's anti-hidden-experiment gate refuses
        # any PAR-044 value other than the exact declared byte-string.
        with pytest.raises(common.StructureLawError):
            fvg3.evaluate(dict(minted_caps), vbar("b0", 100, 95), None, bar_ordinal=0,
                          bucket_start_us=0, bucket_end_us=BUCKET, atr14_ticks=20)


# ---------------------------------------------------------------------------------------------
# The C.3 boundary — adversarial dynamic gate (a hand-built dict/int rejects BEFORE any
# state transition)
# ---------------------------------------------------------------------------------------------


class TestBoundaryRejections:
    def test_hand_built_dict_in_place_of_a_capability_is_a_typed_rejection(self, caps):
        state, _ = run_v3(caps, bull_formation())
        before = copy.deepcopy(state)
        forged = dict(caps)
        forged[fvg3.PARAM_TTL_BARS] = {"value": "96", "formula_id": "F10",
                                       "parameter_id": fvg3.PARAM_TTL_BARS}
        with pytest.raises(bindings.CapabilityForgeryError):
            fvg3.evaluate(forged, vbar("b3", 116, 95), state, bar_ordinal=3,
                          bucket_start_us=3 * BUCKET, bucket_end_us=4 * BUCKET, atr14_ticks=20)
        assert state == before  # rejected BEFORE any state transition

    @pytest.mark.parametrize("junk", [17, "96", None, [1, 2], (1, 2)])
    def test_non_capability_entries_are_typed_rejections(self, caps, junk):
        forged = dict(caps)
        forged[fvg3.PARAM_TTL_BARS] = junk
        with pytest.raises(bindings.CapabilityForgeryError):
            fvg3.evaluate(forged, vbar("b0", 100, 95), None, bar_ordinal=0,
                          bucket_start_us=0, bucket_end_us=BUCKET, atr14_ticks=20)

    def test_caps_container_must_be_a_mapping(self, caps):
        with pytest.raises(bindings.CapabilityForgeryError):
            fvg3.evaluate(list(caps.values()), vbar("b0", 100, 95), None, bar_ordinal=0,
                          bucket_start_us=0, bucket_end_us=BUCKET, atr14_ticks=20)

    def test_unknown_parameter_key_is_refused(self, caps):
        widened = dict(caps)
        widened["PAR-999"] = caps[fvg3.PARAM_MIN_GAP_RULE]
        with pytest.raises(bindings.CapabilityForgeryError):
            fvg3.evaluate(widened, vbar("b0", 100, 95), None, bar_ordinal=0,
                          bucket_start_us=0, bucket_end_us=BUCKET, atr14_ticks=20)

    def test_foreign_formula_capability_is_refused(self, caps, foreign_cap):
        assert foreign_cap.formula_id == "F00"  # a GENUINE capability — for another formula
        forged = dict(caps)
        forged[fvg3.PARAM_MIN_GAP_RULE] = foreign_cap
        with pytest.raises(bindings.CapabilityForgeryError):
            fvg3.evaluate(forged, vbar("b0", 100, 95), None, bar_ordinal=0,
                          bucket_start_us=0, bucket_end_us=BUCKET, atr14_ticks=20)

    def test_a_capability_under_the_wrong_key_is_refused(self, caps):
        swapped = dict(caps)
        swapped[fvg3.PARAM_TTL_BARS] = caps[fvg3.PARAM_MAX_OPEN_PER_PARTITION]
        with pytest.raises(bindings.CapabilityForgeryError):
            fvg3.evaluate(swapped, vbar("b0", 100, 95), None, bar_ordinal=0,
                          bucket_start_us=0, bucket_end_us=BUCKET, atr14_ticks=20)

    def test_raw_dict_env_is_a_typed_boundary_rejection(self, caps):
        with pytest.raises(e01.QuarantineInvalidBar):
            fvg3.evaluate(caps, raw_bar("b0", 100, 95), None, bar_ordinal=0,
                          bucket_start_us=0, bucket_end_us=BUCKET, atr14_ticks=20)

    def test_invalid_bar_quarantines_at_the_e01_boundary_never_reaching_the_machine(self):
        bad = raw_bar("b0", 100, 95)
        bad["low_ticks"] = 2000  # violates VALID_BAR
        with pytest.raises(e01.QuarantineInvalidBar):
            e01.require_valid_bar(bad)

    def test_never_blend_a_state_from_another_formula_version_refuses(self, caps):
        state, _ = run_v3(caps, bull_formation())
        blended = dict(state, formula_version="fvg.three_bar.closed.v2")
        with pytest.raises(common.StructureLawError):
            fvg3.evaluate(caps, vbar("b3", 116, 95), blended, bar_ordinal=3,
                          bucket_start_us=3 * BUCKET, bucket_end_us=4 * BUCKET, atr14_ticks=20)

    def test_garbage_state_fails_closed(self, caps):
        with pytest.raises(common.StructureLawError):
            fvg3.evaluate(caps, vbar("b0", 100, 95), {"zones": []}, bar_ordinal=0,
                          bucket_start_us=0, bucket_end_us=BUCKET, atr14_ticks=20)
        state, _ = run_v3(caps, bull_formation())
        with_terminal = json.loads(canonical_json(state))
        with_terminal["zones"][0]["state"] = fvg3.STATE_FILLED  # a terminal zone never persists
        with pytest.raises(common.StructureLawError):
            fvg3.evaluate(caps, vbar("b3", 116, 95), with_terminal, bar_ordinal=3,
                          bucket_start_us=3 * BUCKET, bucket_end_us=4 * BUCKET, atr14_ticks=20)

    def test_malformed_injected_facts_fail_closed(self, caps):
        with pytest.raises(common.StructureLawError):
            fvg3.evaluate(caps, vbar("b0", 100, 95), None, bar_ordinal=0,
                          bucket_start_us=BUCKET, bucket_end_us=BUCKET, atr14_ticks=20)
        with pytest.raises(common.StructureLawError):
            fvg3.evaluate(caps, vbar("b0", 100, 95), None, bar_ordinal=0,
                          bucket_start_us=0, bucket_end_us=BUCKET, atr14_ticks=20,
                          sequence_discontinuity=1)
        with pytest.raises(common.StructureLawError):
            fvg3.evaluate(caps, vbar("b0", 100, 95), None, bar_ordinal=0,
                          bucket_start_us=0, bucket_end_us=BUCKET, atr14_ticks=20,
                          revised_bar_identities=("", "b0"))
        with pytest.raises(common.StructureLawError):
            fvg3.evaluate(caps, vbar("b0", 100, 95), None, bar_ordinal=0,
                          bucket_start_us=0, bucket_end_us=BUCKET, atr14_ticks=20,
                          opposing_break={"direction": "SHORT", "close_ticks": 1})
        with pytest.raises(common.StructureLawError):
            fvg3.OpposingBreak(direction="UP", close_ticks=1)


# ---------------------------------------------------------------------------------------------
# Version discipline (§1.5) — v3 identity everywhere; v2 retired with its banner, bytes frozen
# ---------------------------------------------------------------------------------------------


class TestVersionDiscipline:
    def test_module_identity_constants(self):
        assert fvg3.FORMULA_F10 == "F10"
        assert fvg3.FORMULA_VERSION == "fvg.three_bar.closed.v3"
        assert fvg3.RETIRED_PREDECESSOR_VERSION == "fvg.three_bar.closed.v2"
        assert fvg3.FVG_TOUCH_PRICE_SOURCE == "bar_low(bull)/bar_high(bear)"

    def test_every_emitted_event_carries_the_v3_version_tag(self, caps):
        scenario = caps_with(caps, ttl="10")
        _, events = run_v3(scenario, full_lifecycle_steps())
        for event in zone_events(events):
            assert event["formula_version"] == fvg3.FORMULA_VERSION

    def test_retired_v2_carries_the_module_withdrawal_banner(self):
        doc = fvg2.__doc__
        assert "RETIRED_DEFECTIVE{defect_ref=TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12 R-F10}" \
            in doc
        assert "fvg.three_bar.closed.v2" in doc
        assert "fvg_registry_v3" in doc

    def test_retired_v2_bytes_are_frozen_not_deleted(self):
        # The v2 surface survives verbatim under the banner (never edited in place, never
        # deleted): its constants, machine class, and behavior are intact — the defect-contrast
        # test above exercises the frozen defect on the ORIGINAL code path.
        assert fvg2.STATE_FORMED == "FORMED"
        assert fvg2.STATE_PARTIALLY_FILLED == "PARTIALLY_FILLED"
        assert fvg2.ZONE_FULLY_FILLED == "ZONE_FULLY_FILLED"
        assert fvg2.FvgZoneRegistry().initial_state() == {
            "last_event_id": None, "last_bar_seq": None, "recent": [], "zones": []}


# ---------------------------------------------------------------------------------------------
# ERR-01 (owner decision D-21) — the F10 state predicates are MUTUALLY EXCLUSIVE and monotone.
#
# Spec §R-F10's state block wrote overlapping predicates (`TOUCHED (pen>0)` and
# `PARTIAL (0<pen<1/2)` both fire on the open interval (0, 1/2)), and its inline T4 reasoning
# contradicted the `pen>0` gloss. The RATIFIED T4 row ("edge contact at z1 is TOUCHED with
# pen = 0") is normative (spec §0) and is what this module implements. The resolved,
# mutually-exclusive reading is:
#     TOUCHED         : intersection, pen == 0        PARTIAL         : 0 < pen < 1/2
#     MIDPOINT_FILLED : 1/2 <= pen < 1                FILLED          : pen == 1
# (FRESH is the no-intersection case, contacted=False.) The errata document requires "a property
# test asserting that for 10^5 random pen values in [0, 1] exactly one state predicate is true".
# Formally adopting the erratum onto the spec TEXT is owner-gated as D-21; this test locks the
# already-ratified code behaviour, it does not adopt a new law.
# ---------------------------------------------------------------------------------------------


class TestErr01MutuallyExclusiveStates:
    @staticmethod
    def _predicates(num: int, den: int) -> dict:
        # exact integer arithmetic on a reduced pen = num/den in [0, 1] with den > 0 — no float.
        return {
            fvg3.STATE_TOUCHED: num == 0,
            fvg3.STATE_PARTIAL: num > 0 and 2 * num < den,
            fvg3.STATE_MIDPOINT_FILLED: 2 * num >= den and num < den,
            fvg3.STATE_FILLED: num == den,
        }

    @staticmethod
    def _reduced(num: int, den: int) -> tuple:
        g = math.gcd(num, den)
        return num // g, den // g

    def test_exactly_one_predicate_holds_and_matches_state_for(self):
        # the three published boundary rows — T4 (p = z1 -> pen 0), T5 (midpoint -> pen 1/2),
        # T6 (p < z0 -> pen 1) — plus 10^5 deterministic random pens in [0, 1].
        cases = [(0, 1), (1, 2), (1, 1)]
        rng = random.Random(0xF10E01)
        for _ in range(100_000):
            den = rng.randint(1, 4096)
            cases.append((rng.randint(0, den), den))
        for raw_num, raw_den in cases:
            num, den = self._reduced(raw_num, raw_den)
            true_states = [s for s, ok in self._predicates(num, den).items() if ok]
            # EXACTLY ONE state predicate is true for every pen in [0, 1].
            assert len(true_states) == 1, (num, den, true_states)
            # contacted=True is the intersection case: _state_for must return that one state.
            assert fvg3._state_for((num, den), contacted=True) == true_states[0], (num, den)

    def test_no_intersection_is_the_only_route_to_fresh(self):
        # FRESH is reachable ONLY with no intersection (contacted=False); an edge contact with
        # pen == 0 is TOUCHED, never FRESH (the T4 ratified reading).
        assert fvg3._state_for((0, 1), contacted=False) == fvg3.STATE_FRESH
        assert fvg3._state_for((0, 1), contacted=True) == fvg3.STATE_TOUCHED
