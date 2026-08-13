"""B03C milestone golden home — the F02..F09 family registry vectors.

This file is the B03C acceptance profile's REQUIRED ARTIFACT
(``docs/control/closure/closure_semantics.v1.json`` →
``tests/formulas/test_f02_f09_goldens_b03c.py``). It executes:

* **GV-004 (F02):** ATR = 8 on a flat true-range-8 tape (the pre-existing linked golden,
  re-walked at the milestone home).
* **GV-F05-01 (F05, Part D §D.5):** N = 3, highs ``[10, 12, 11]`` → ``upper_t = 12``;
  lows ``[9, 9, 10]`` → ``lower_t = 9`` (equal lows: the extreme VALUE is the value).
  Current bar t excluded by construction (its high 15 must not change ``upper_t``).
  Warm-up with only 2 prior bars → NULL. Gap in window → NULL.
* **GV-003 (F01, Part D §D.2) — the Origin consume-half.** The watermark arithmetic
  (bucket ``[12:00:00, 12:01:00)``, ``allowed_lateness = 2s`` PAR-025, FINALIZED when source
  watermark ≥ ``12:01:02``) is E01-OWNED (CLAUDE.md reconciled law: ORIGIN consumes/validates,
  never authors bar finalization). Origin's executable half is the boundary law: only a
  FINALIZED + watermark-complete + READY bar is consumable; a late-data revision APPENDS
  ``data_revision r+1`` as a new event and the original availability is never rewritten —
  in Origin terms, same-index-different-bytes is a revision CONFLICT (poison), never a rewrite.

The deep F03/F04/F09 batteries live in ``tests/structures/test_swing_dc_v2.py`` /
``test_typed_levels.py`` / ``test_break_v2.py``; the milestone home ALSO WALKS the three B03C
HEADLINE repairs here (mirroring the B04C/B06R homes), each through the same acceptance path the
structure battery uses:

* **R-F03 (``swing.dc.bar_extrema.v2``):** the ambiguous-bar law ``ABSTAIN_EXTEND_WINS`` — a real
  C.1 sealed capability (FPB-0011 flipped ACTIVE, PAR-036, real Ed25519) drives one ambiguous bar
  and the extension wins (the swing is confirmed by the NEXT bar, never the ambiguous one). The
  UNEDITED registry mints no F03 capability and the missing-capability refusal is the named
  ``BLOCKED_ON_RATIFY(PAR-036)``.
* **R-F04 (``typed_level_registry`` FractalPivot):** ``SIMULTANEOUS_PIVOT = BOTH_EMIT`` — a single
  strict-unique high AND low bar emits BOTH atoms with distinct identity and a pinned order
  (pivot_high before pivot_low). Raw-params path (F04 is not on the sealed-capability seam).
* **R-F09 (``break.bar_close.v2``):** the first-terminal lifecycle — a first terminal break
  RETIRES the level and a later opposite qualifying close is a duplicate-ignored audit; ``b < 1``
  is a typed ``REFUSE_CONFIG``. Minted through the real acceptance (FPB-0018 + FPB-0092 ACTIVE);
  the UNEDITED registry mints no F09 capability.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import bindings, e01_interface as e01, features, transition  # noqa: E402
from triad_origin.canonical import canonical_json, sha256_hex  # noqa: E402
from triad_origin.e01_interface import (  # noqa: E402
    E01_BAR_NOT_FINALIZED,
    validate_finalized_bar,
)
from triad_origin.structures import break_v2, common  # noqa: E402
from triad_origin.structures import swing_dc_v2 as sdc  # noqa: E402
from triad_origin.structures import typed_level_registry as tlr  # noqa: E402


def bar(index, o, h, l, c, event_id=None):
    return {
        "event_id": event_id or f"bar_{index}",
        "payload": {
            "state_kind": "BAR",
            "bar_finalization_state": "FINALIZED",
            "watermark_complete": True,
            "validity": "READY",
            "bar_index": index,
            "bar_open_time_us": index * 60_000_000,
            "bar_close_time_us": (index + 1) * 60_000_000,
            "open_ticks": o,
            "high_ticks": h,
            "low_ticks": l,
            "close_ticks": c,
        },
    }


def run_ext(inputs, window):
    return transition.run(features.RollingExtreme(), inputs, {"window": window})


class TestGV004AtrEqualsEight:
    def test_flat_tr8_tape_yields_atr_8(self) -> None:
        inputs = [bar(i, 1000, 1008, 1000, 1000) for i in range(15)]
        result = transition.run(features.AtrCalculator(), inputs, {"atr_period": 14})
        feature = result.events[-1]
        assert feature["event_kind"] == "FEATURE"
        assert feature["atr_ticks"] == 8


class TestGVF0501RollingExtreme:
    def test_direct_golden_upper_12_lower_9_current_bar_excluded(self) -> None:
        inputs = [
            bar(0, 10, 10, 9, 9),    # high 10, low 9
            bar(1, 10, 12, 9, 11),   # high 12, low 9  (equal lows with bar 0)
            bar(2, 10, 11, 10, 10),  # high 11, low 10
            bar(3, 12, 15, 12, 14),  # current bar t — its high 15 must not appear
        ]
        result = run_ext(inputs, window=3)
        feature = result.events[3]
        assert feature["event_kind"] == "FEATURE"
        assert feature["upper_ticks"] == 12
        assert feature["lower_ticks"] == 9  # equal lows: the extreme value is the value
        assert feature["dependency_range"] == {"first_bar_index": 0, "last_bar_index": 2}

    def test_warmup_two_prior_bars_is_null(self) -> None:
        inputs = [bar(0, 10, 10, 9, 9), bar(1, 10, 12, 9, 11), bar(2, 10, 11, 10, 10)]
        result = run_ext(inputs, window=3)
        assert result.events[2]["event_kind"] == "NAMED_ABSTENTION"
        assert result.events[2]["reason_code"] == "F05_WARMUP"

    def test_gap_in_window_is_null(self) -> None:
        inputs = [
            bar(0, 10, 10, 9, 9),
            bar(1, 10, 12, 9, 11),
            bar(3, 10, 11, 10, 10),  # bar 2 missing — gap
            bar(4, 12, 15, 12, 14),
        ]
        result = run_ext(inputs, window=3)
        assert all(e["event_kind"] != "FEATURE" for e in result.events)


class TestGV003OriginConsumeHalf:
    def test_finalized_watermark_complete_ready_bar_is_consumable(self) -> None:
        verdict = validate_finalized_bar(bar(0, 10, 12, 9, 11))
        assert verdict["accepted"] is True
        assert verdict["bar"]["bar_index"] == 0

    def test_pre_watermark_bar_is_not_available_no_formula_evaluation(self) -> None:
        # E01 finalizes at watermark >= bucket_end + allowed_lateness; before that the bar
        # arrives non-FINALIZED and Origin must not evaluate any formula over it.
        env = bar(0, 10, 12, 9, 11)
        env["payload"]["bar_finalization_state"] = "FORMING"
        verdict = validate_finalized_bar(env)
        assert verdict["accepted"] is False
        assert verdict["event_kind"] == "QUARANTINE"
        assert verdict["reason_code"] == E01_BAR_NOT_FINALIZED

    def test_incomplete_watermark_is_not_available(self) -> None:
        env = bar(0, 10, 12, 9, 11)
        env["payload"]["watermark_complete"] = False
        verdict = validate_finalized_bar(env)
        assert verdict["accepted"] is False
        assert verdict["event_kind"] == "QUARANTINE"
        assert verdict["reason_code"] == E01_BAR_NOT_FINALIZED

    def test_late_data_revision_appends_never_rewrites(self) -> None:
        # GV-003's revision law at the Origin boundary: a late trade re-emits the bar as a NEW
        # revision event; the ORIGINAL bytes are never rewritten. Same-index-different-bytes
        # without that revision identity is therefore a CONFLICT that poisons the consumer —
        # the one behavior that would exist iff an original had been rewritten in place.
        original = bar(5, 10, 12, 9, 11, event_id="bar_5_r0")
        rewritten = bar(5, 10, 12, 9, 10, event_id="bar_5_r1")  # same index, different bytes
        result = transition.run(
            features.RollingExtreme(), [original, rewritten], {"window": 3})
        conflict = result.events[-1]
        assert conflict["event_kind"] == "QUARANTINE"
        assert conflict["reason_code"] == "E01_BAR_REVISION_CONFLICT"


# =================================================================================================
# R-F03 HEADLINE WALK — swing.dc.bar_extrema.v2 ABSTAIN_EXTEND_WINS (the ambiguous-bar law)
#
# Minted through the REAL C.1 sealed-capability acceptance (``build_sealed_bundle`` +
# ``transition.require_bundle``, real Ed25519), exactly as ``tests/structures/test_swing_dc_v2.py``
# does. FPB-0011 is flipped ACTIVE in a TEST-only ratified registry copy — the repository row stays
# BLOCKED (the honest-dark posture proven below). PAR-036's declared rule carries a ``*`` wildcard
# sentinel that acceptance refuses in an ACTIVE row, so the fixture mints over a sentinel-free TEST
# transport value and re-carries the exact declared byte-string on the verified handle (C.1:
# construction is unrestricted, acceptance is what is guarded — and it ran in full).
# =================================================================================================

F03_OWNER_KID = "k-owner-f03-b03c"
F03_TEST_TRANSPORT = "TEST-RATIFIED-TRANSPORT max(5,ceil(ATR14_ticks 1/4)) (sentinel-free)"


def _f03_ratified_doc(declared_value: str = F03_TEST_TRANSPORT) -> dict:
    """The repository registry with FPB-0011 flipped ACTIVE — a TEST-only ratified posture."""
    doc = json.loads(pathlib.Path(bindings.DEFAULT_REGISTRY_PATH).read_text(encoding="utf-8"))
    for row in doc["rows"]:
        if row["binding_id"] == "FPB-0011":
            row.update({
                "status": "ACTIVE", "lifecycle_status": "ACTIVE",
                "cardinality": "EXACTLY_ONE", "migration_state": "NOT_APPLICABLE",
                "declared_value": declared_value,
                "semantic_slot": "dc_reversal_delta_ticks_TEST",
                "condition": "TEST-RATIFIED stand-in for the PAR-036 ratification ceremony",
                "activation_scope": "TEST;F03;b03c golden home only",
                "precedence": "TEST_FIXTURE", "consumer": "ORIGIN(F03)",
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


def _f03_raw_bar(identity: str, high: int, low: int) -> dict:
    return {"bar_identity": identity, "metadata_revision": "r1",
            "open_ticks": low, "high_ticks": high, "low_ticks": low, "close_ticks": high,
            "base_volume": 1, "quote_volume": 1, "trade_count": 1}


def _f03_run(caps, steps, state=None):
    st = sdc.initial_state() if state is None else state
    events: list = []
    for raw, atr in steps:
        result = sdc.evaluate(caps, e01.require_valid_bar(raw), st, atr14_ticks=atr)
        events.extend(result.events)
        st = result.state
    return st, events


# Reaches an UP leg lawfully (b1 confirms SWING_LOW(998) -> mode UP, prov_high=(1004, 5, b1)).
F03_UP_LEG = [(_f03_raw_bar("b0", 1000, 998), 20), (_f03_raw_bar("b1", 1004, 999), 20)]


@pytest.fixture(scope="module")
def f03_forge():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey, Ed25519PublicKey)

    bindings._reset_trust_registry_pin_for_tests()
    bindings._reset_acceptance_memo_for_tests()
    private = Ed25519PrivateKey.generate()
    pub_hex = private.public_key().public_bytes_raw().hex()
    trust = {F03_OWNER_KID: {"key_id": F03_OWNER_KID, "identity": "b03c-f03@triad-origin",
                             "role": "AUTHORITY_OWNER", "algorithm": "ed25519",
                             "public_key_hex": pub_hex, "revoked": False}}
    raw = json.dumps(trust, sort_keys=True).encode("utf-8")
    digest = sha256_hex(raw)

    def _verify(public_key_hex: str, message: bytes, signature_hex: str) -> bool:
        try:
            key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
            key.verify(bytes.fromhex(signature_hex), message)
            return True
        except Exception:
            return False

    def _sign(unsigned):
        signing = bindings.sealed_bundle_signing_bytes(
            canonical_root_digest=unsigned.canonical_root_digest, scope=unsigned.scope,
            valid_from=unsigned.valid_from, valid_to=unsigned.valid_to)
        return dataclasses.replace(unsigned, signatures=[
            {"key_id": F03_OWNER_KID, "signature_hex": private.sign(signing).hex()}])

    ctx = bindings.VerificationContext(
        trust=trust, trust_registry_bytes=raw, now_us=2_000_000,
        process_scope={"repository": "TriadOrigin", "environment": "OFF"},
        verify_fn=_verify)
    ns = {"ctx": ctx, "digest": digest, "sign": _sign,
          "real_registry": bindings.load_registry(),
          "ratified_registry": bindings.BindingRegistry(_f03_ratified_doc())}
    yield ns
    bindings._reset_trust_registry_pin_for_tests()
    bindings._reset_acceptance_memo_for_tests()


@pytest.fixture(scope="module")
def f03_caps(f03_forge):
    """A REAL VerifiedCapability for PAR-036/F03 re-carrying the exact declared byte-string."""
    bindings._reset_trust_registry_pin_for_tests()
    bindings._reset_acceptance_memo_for_tests()
    bindings.pin_trust_registry_digest(f03_forge["digest"])
    unsigned = bindings.build_sealed_bundle(
        f03_forge["ratified_registry"], repository="TriadOrigin", environment="OFF",
        valid_from=1_000_000, valid_to=9_000_000,
        trust_registry_digest=f03_forge["digest"], signer_set=[F03_OWNER_KID])
    bundle = f03_forge["sign"](unsigned)
    cap = transition.require_bundle(
        bundle, sdc.PARAMETER_DC_REVERSAL, formula_id="F03", ctx=f03_forge["ctx"])
    assert type(cap) is bindings.VerifiedCapability and cap.formula_id == "F03"
    caps = {sdc.PARAMETER_DC_REVERSAL: dataclasses.replace(
        cap, value=common.DECLARED_DC_REVERSAL)}
    bindings._reset_trust_registry_pin_for_tests()
    bindings._reset_acceptance_memo_for_tests()
    return caps


class TestRF03AmbiguousBarLaw:
    def test_ambiguous_bar_abstains_extension_wins_then_next_bar_confirms(self, f03_caps):
        steps = F03_UP_LEG + [
            (_f03_raw_bar("b2", 1010, 998), 20),    # H_j > H_x AND L_j <= H_x - delta: ambiguous
            (_f03_raw_bar("b3", 1006, 1005), 20)]   # 1010 - 1005 == 5: the NEW threshold confirms
        state, events = _f03_run(f03_caps, steps)
        facts = [e for e in events
                 if e.get("event_kind") == "NAMED_ABSTENTION"
                 and e["reason_code"] == sdc.AMBIGUOUS_BAR_ABSTENTION]
        assert len(facts) == 1
        assert facts[0]["refs"] == {
            "bar_identity": "b2", "rule": sdc.DC_AMBIGUOUS_BAR_RULE,
            "semantic_version": sdc.SEMANTIC_VERSION}
        levels = [e for e in events if e.get("event_kind") == tlr.TYPED_LEVEL]
        # Extension wins: the SWING_HIGH takes b2's extended extreme (1010) and is confirmed by b3
        # — the ambiguous bar b2 confirms NOTHING itself.
        assert [(e["kind"], e["level_ticks"], e["confirmed_by_bar_identity"])
                for e in levels] == [
            (tlr.SWING_LOW, 998, "b1"), (tlr.SWING_HIGH, 1010, "b3")]
        assert all(e["confirmed_by_bar_identity"] != "b2" for e in levels)
        assert state["mode"] == "DOWN"

    def test_unedited_registry_mints_no_f03_capability(self, f03_forge):
        # Honest-dark: the repository registry keeps FPB-0011/PAR-036 BLOCKED, so the real mint
        # path cannot produce an F03 capability at all.
        bindings._reset_trust_registry_pin_for_tests()
        bindings._reset_acceptance_memo_for_tests()
        bindings.pin_trust_registry_digest(f03_forge["digest"])
        try:
            genuine = f03_forge["sign"](bindings.build_sealed_bundle(
                f03_forge["real_registry"], repository="TriadOrigin", environment="OFF",
                valid_from=1_000_000, valid_to=9_000_000,
                trust_registry_digest=f03_forge["digest"], signer_set=[F03_OWNER_KID]))
            with pytest.raises(bindings.BlockedBindingIncomplete) as excinfo:
                transition.require_bundle(
                    genuine, sdc.PARAMETER_DC_REVERSAL, formula_id="F03", ctx=f03_forge["ctx"])
            assert excinfo.value.formula_id == "F03"
        finally:
            bindings._reset_trust_registry_pin_for_tests()
            bindings._reset_acceptance_memo_for_tests()

    def test_missing_capability_is_the_named_blocked_on_ratify_refusal(self):
        with pytest.raises(sdc.BlockedOnRatify) as excinfo:
            sdc.evaluate({}, e01.require_valid_bar(_f03_raw_bar("b0", 1000, 998)),
                         sdc.initial_state(), atr14_ticks=20)
        assert str(excinfo.value) == "BLOCKED_ON_RATIFY(PAR-036)"


# =================================================================================================
# R-F04 HEADLINE WALK — typed_level_registry FractalPivot SIMULTANEOUS_PIVOT = BOTH_EMIT tie law
#
# The raw-params path (F04 is NOT on the sealed-capability seam), exactly as
# ``tests/structures/test_typed_levels.py::TestFractalPivotErratumRF04``.
# =================================================================================================

F04_PARAMS = {tlr.PARAM_FRACTAL_LEFT: 2, tlr.PARAM_FRACTAL_RIGHT: 2}


def _f04_bar(index: int, high: int, low: int, seq: int) -> dict:
    return {"event_id": f"b{index}", "kind": "BAR",
            "payload": {"high_ticks": high, "low_ticks": low, "bar_seq": seq}}


class TestRF04BothEmitTie:
    def test_simultaneous_strict_high_and_low_emit_both_atoms_pinned_order(self):
        # A huge-range bar amid flat bars: strict unique window max-high AND min-low at once.
        highs = [10, 11, 15, 11, 10]
        lows = [9, 8, 2, 8, 9]
        bars = [_f04_bar(i, h, l, seq=i) for i, (h, l) in enumerate(zip(highs, lows))]
        result = transition.run(tlr.FractalPivot(), bars, F04_PARAMS)
        levels = [e for e in result.events if e.get("event_kind") == tlr.TYPED_LEVEL]
        assert levels == [
            {"event_kind": tlr.TYPED_LEVEL, "formula": "F04", "kind": tlr.PIVOT_HIGH,
             "level_ticks": 15, "origin_event_id": "b2", "origin_bar_seq": 2,
             "confirmed_by_event_id": "b4"},
            {"event_kind": tlr.TYPED_LEVEL, "formula": "F04", "kind": tlr.PIVOT_LOW,
             "level_ticks": 2, "origin_event_id": "b2", "origin_bar_seq": 2,
             "confirmed_by_event_id": "b4"}]
        # Distinct identity: the two simultaneous atoms differ in kind AND level; emission order is
        # pinned deterministic (pivot_high before pivot_low).
        assert levels[0]["kind"] != levels[1]["kind"]
        assert levels[0]["level_ticks"] != levels[1]["level_ticks"]
        # Right-edge law untouched: nothing before bar i+R finalizes.
        early = transition.run(tlr.FractalPivot(), bars[:4], F04_PARAMS)
        assert [e for e in early.events if e.get("event_kind") == tlr.TYPED_LEVEL] == []


# =================================================================================================
# R-F09 HEADLINE WALK — break.bar_close.v2 first-terminal lifecycle + b >= 1 REFUSE_CONFIG
#
# Minted through the REAL sealed-bundle v2 acceptance (``transition.require_bundle``, real Ed25519),
# exactly as ``tests/structures/test_break_v2.py`` (FPB-0018 + FPB-0092 flipped ACTIVE in the
# fixture bundle). The declared PAR-043 rule carries a ``*`` sentinel, so the rule-face capability
# mints over a placeholder tick value and the verified handle's value is swapped to the rule string
# (construction unrestricted; acceptance ran in full). The UNEDITED registry mints no F09 cap.
# =================================================================================================

F09_OWNER_KID = "k-owner-f09-b03c"
F09_BASE_US = 1_000_000
F09_BUCKET_US = 60_000_000
F09_LATENESS_US = 2_000_000
F09_RULE = common.DECLARED_BOS_CLOSE_BUFFER


class _F09Forge:
    def __init__(self) -> None:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey, Ed25519PublicKey)

        self._private = Ed25519PrivateKey.generate()
        pub_hex = self._private.public_key().public_bytes_raw().hex()
        self.trust = {F09_OWNER_KID: {
            "key_id": F09_OWNER_KID, "identity": "b03c-f09@triad-origin",
            "role": "AUTHORITY_OWNER", "algorithm": "ed25519",
            "public_key_hex": pub_hex, "revoked": False}}
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
            trust=self.trust, trust_registry_bytes=self.trust_bytes, now_us=2_000_000,
            process_scope={"repository": "TriadOrigin", "environment": "OFF"},
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
            {"key_id": F09_OWNER_KID, "signature_hex": self._private.sign(signing).hex()}])

    def fixture_bundle(self, buffer_value, ttl_value):
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
            scope={"repository": "TriadOrigin", "environment": "OFF"},
            rows=rows, canonical_root_digest=root,
            trust_registry_digest=self.trust_digest, signer_set=[F09_OWNER_KID],
            signatures=[], valid_from=1_000_000, valid_to=9_000_000,
            formula_coverage=coverage,
            row_preimage_digests=sorted(sha256_hex(canonical_json(r)) for r in rows))
        return self._sign(unsigned)

    def genuine_bundle(self):
        return self._sign(bindings.build_sealed_bundle(
            self.registry, repository="TriadOrigin", environment="OFF",
            valid_from=1_000_000, valid_to=9_000_000,
            trust_registry_digest=self.trust_digest, signer_set=[F09_OWNER_KID]))

    def mint(self, buffer_value, ttl_value=500):
        rule_overlay = isinstance(buffer_value, str) and "*" in buffer_value
        mintable = 1 if rule_overlay else buffer_value
        bundle = self.fixture_bundle(mintable, ttl_value)
        buffer_cap = transition.require_bundle(
            bundle, break_v2.PARAM_BREAK_BUFFER, formula_id="F09", ctx=self.ctx)
        if rule_overlay:
            buffer_cap = dataclasses.replace(buffer_cap, value=buffer_value)
        return {break_v2.PARAM_BREAK_BUFFER: buffer_cap,
                break_v2.PARAM_LEVEL_TTL: transition.require_bundle(
                    bundle, break_v2.PARAM_LEVEL_TTL, formula_id="F09", ctx=self.ctx)}


@pytest.fixture(scope="module")
def f09_forge():
    bindings._reset_trust_registry_pin_for_tests()
    bindings._reset_acceptance_memo_for_tests()
    forge = _F09Forge()
    bindings.pin_trust_registry_digest(forge.trust_digest)
    yield forge
    bindings._reset_trust_registry_pin_for_tests()
    bindings._reset_acceptance_memo_for_tests()


@pytest.fixture(scope="module")
def f09_caps(f09_forge):
    return f09_forge.mint(F09_RULE, 500)


def _f09_vbar(identity: str, close: int):
    return e01.require_valid_bar({
        "bar_identity": identity, "metadata_revision": "rev-1",
        "open_ticks": close, "high_ticks": close, "low_ticks": close, "close_ticks": close,
        "base_volume": 1, "quote_volume": 1, "trade_count": 1})


def _f09_bar(eid: str, close: int, *, ordinal: int, atr: int = 20):
    bucket = F09_BASE_US + ordinal * F09_BUCKET_US
    avail = bucket + F09_BUCKET_US + F09_LATENESS_US
    return break_v2.BarObservation(
        bar=_f09_vbar(f"bar:{eid}", close), bucket_start_us=bucket,
        availability_time_us=avail, source_sequence=100 + ordinal, bar_ordinal=ordinal,
        atr14_ticks=atr, source_event_id=eid)


def _f09_lvl(eid: str, level_id: str, ticks: int, direction=common.LONG):
    return break_v2.LevelRegistration(
        level_id=level_id, level_ticks=ticks, direction=direction,
        availability_time_us=F09_BASE_US, formation_bar_ordinal=0,
        defining_swing_id="SW1", swing_revision=0, source_event_id=eid)


def _f09_kinds(events, kind):
    return [e for e in events if e.get("event_kind") == kind]


class TestRF09FirstTerminalLifecycle:
    def test_first_terminal_break_retires_the_level_and_a_later_close_is_duplicate_ignored(
            self, f09_caps):
        # ATR 20 => buffer 1 (GV-008 numerics); close 1001 == L + b breaks UP at c1.
        result = break_v2.run_break_v2(f09_caps, [
            _f09_lvl("l1", "LV1", 1000),
            _f09_bar("c1", 1001, ordinal=0),   # accepted UP break at j
            _f09_bar("c2", 1000, ordinal=1),
            _f09_bar("c3", 1000, ordinal=2),
            _f09_bar("c4", 995, ordinal=3)])   # qualifying DOWN close — first-terminal already set
        occurred = _f09_kinds(result.events, break_v2.BREAK_OCCURRENCE)
        assert len(occurred) == 1
        assert occurred[0]["direction"] == break_v2.UP_BREAK
        assert occurred[0]["terminal"] == break_v2.BROKEN_UP
        (ignored,) = _f09_kinds(result.events, break_v2.DUPLICATE_BREAK_IGNORED)
        assert ignored["level_id"] == "LV1"
        assert ignored["ignored_direction"] == break_v2.DOWN_BREAK
        assert ignored["terminal"] == break_v2.BROKEN_UP
        record = result.final_state["levels"]["LV1"]
        assert record["lifecycle"] == break_v2.LIFECYCLE_RETIRED
        assert record["break"]["direction"] == break_v2.UP_BREAK

    def test_buffer_below_one_is_a_typed_refuse_config(self, f09_forge):
        state = break_v2.initial_state()
        with pytest.raises(break_v2.RefuseConfig) as excinfo:
            break_v2.evaluate(
                f09_forge.mint(0, 500), _f09_bar("c1", 1001, ordinal=0), state)
        assert excinfo.value.reason == "REFUSE_CONFIG"
        assert state == break_v2.initial_state()  # refused before any transition
        with pytest.raises(break_v2.RefuseConfig):
            break_v2.evaluate(
                f09_forge.mint(-3, 500), _f09_lvl("l1", "LV1", 1000), state)

    def test_unedited_registry_mints_no_f09_capability(self, f09_forge):
        # Honest-dark: F09's registry rows are BLOCKED (unmigrated), so the production mint path
        # cannot produce an F09 capability at all.
        with pytest.raises(bindings.BlockedBindingIncomplete) as excinfo:
            transition.require_bundle(
                f09_forge.genuine_bundle(), break_v2.PARAM_BREAK_BUFFER,
                formula_id="F09", ctx=f09_forge.ctx)
        assert excinfo.value.formula_id == "F09"
