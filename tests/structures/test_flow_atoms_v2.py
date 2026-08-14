"""R-F15/R-F16/R-F17 flow-atoms v2 battery (TRIAD-ORIGIN-V7-FORMULA-REPAIR-2026-08-12).

Every spec test-vector row for ``flow.tfi.window.v2`` (F15 T1–T12 + GV-013 pair),
``flow.ofi.best.v2`` / ``flow.ofi.best_norm.v1`` (F16 T1–T20 + GV-F16-01) and
``flow.book_tilt.band.v2`` (F17 T1–T10 + GV-014) exists here, plus the §C.3 typed-boundary
adversarial drills, the §1.2 wire-width boundaries, the PROPOSED_MUST_RATIFY refusals, and the
restart/prefix replay parity. Capabilities are minted through the REAL sealed-bundle v2 acceptance
path (:func:`triad_origin.transition.require_bundle`) with a fixture Ed25519 keypair — the
``tests/contracts/test_sealed_bundle_v2.py`` pattern — and the fixture edits the (BLOCKED) F15/F16/F17
registry rows ACTIVE; one test proves the UNEDITED registry refuses to mint (the honest dark posture).
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import bindings, exact, transition  # noqa: E402
from triad_origin.canonical import canonical_json, sha256_hex  # noqa: E402
from triad_origin.e01_interface import QuarantineInvalidTrade, validate_trade  # noqa: E402
from triad_origin.structures import common, flow_atoms_v2 as fv2  # noqa: E402
from triad_origin.structures.flow_atoms_v2 import (  # noqa: E402
    BookSnapshotObservation,
    BookUpdateObservation,
    EnvelopeRejected,
    RefuseConfig,
    TradeObservation,
    WindowClose,
    evaluate_f15,
    evaluate_f16,
    evaluate_f17,
    f15_initial_state,
    f16_initial_state,
    f17_initial_state,
    run_f15,
    run_f16,
    run_f17,
)

OWNER_KID = "k-owner-flow"
REPOSITORY = "TriadOrigin"
ENVIRONMENT = "OFF"
VALID_FROM = 1_000_000
VALID_TO = 9_000_000
NOW_US = 2_000_000

# F15 / F16 / F17 registry rows (all BLOCKED in the real registry) flipped ACTIVE by fixture surgery.
_F15_ROWS = {"FPB-0026": "PAR-052", "FPB-0027": "PAR-053", "FPB-0028": "PAR-054",
             "FPB-0029": "PAR-055", "FPB-0077": "PAR-169"}
_F16_ROWS = {"FPB-0030": "PAR-055", "FPB-0032": "PAR-056", "FPB-0033": "PAR-057",
             "FPB-0034": "PAR-058", "FPB-0078": "PAR-170"}
_F17_ROWS = {"FPB-0031": "PAR-055", "FPB-0035": "PAR-059", "FPB-0079": "PAR-171",
             "RC3-FPB-003": "RC3-PAR-STRUCT-002"}


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

    def fixture_bundle(self, formula_id: str, edits: dict):
        """A signed bundle whose ``formula_id`` rows are edited ACTIVE (fixture surgery)."""
        rows = [dict(r) for r in self._base_rows]
        for row in rows:
            bid = row["binding_id"]
            if bid in edits:
                row["status"] = "ACTIVE"
                row.update(edits[bid])
                self._resign_row(row)
        coverage = dict(self._base_coverage)
        coverage[formula_id] = "ACTIVE"
        root = bindings.canonical_rows_digest(rows)
        unsigned = bindings.SealedParameterBundle(
            schema_version=bindings.SEALED_SCHEMA_VERSION,
            scope={"repository": REPOSITORY, "environment": ENVIRONMENT},
            rows=rows, canonical_root_digest=root, trust_registry_digest=self.trust_digest,
            signer_set=[OWNER_KID], signatures=[], valid_from=VALID_FROM, valid_to=VALID_TO,
            formula_coverage=coverage,
            row_preimage_digests=sorted(sha256_hex(canonical_json(r)) for r in rows))
        return self._sign(unsigned)

    def genuine_bundle(self):
        """The UNEDITED registry, signed — F15/F16/F17 stay BLOCKED (the honest dark posture)."""
        unsigned = bindings.build_sealed_bundle(
            self.registry, repository=REPOSITORY, environment=ENVIRONMENT,
            valid_from=VALID_FROM, valid_to=VALID_TO,
            trust_registry_digest=self.trust_digest, signer_set=[OWNER_KID])
        return self._sign(unsigned)

    def _mint(self, bundle, parameter_id, formula_id):
        return transition.require_bundle(
            bundle, parameter_id, formula_id=formula_id, ctx=self.ctx)

    def mint_f15(self, window_trades=100, max_age=2000, min_trades=1):
        edits = {bid: {} for bid in _F15_ROWS}
        edits["FPB-0026"] = {"declared_value": window_trades}
        edits["FPB-0027"] = {"declared_value": max_age}
        edits["FPB-0028"] = {"declared_value": min_trades}
        bundle = self.fixture_bundle("F15", edits)
        return {
            fv2.PARAM_TFI_WINDOW_TRADES: self._mint(bundle, "PAR-052", "F15"),
            fv2.PARAM_TFI_WINDOW_MAX_AGE: self._mint(bundle, "PAR-053", "F15"),
            fv2.PARAM_TFI_MIN_TRADES: self._mint(bundle, "PAR-054", "F15"),
        }

    def mint_f16(self, window_updates=100, max_age=1000, min_updates=1, norm=None):
        lever_value = fv2.NORM_ACTIVATION_OFF if norm is None else norm
        edits = {bid: {} for bid in _F16_ROWS}
        edits["FPB-0032"] = {"declared_value": window_updates}
        edits["FPB-0033"] = {"declared_value": max_age}
        edits["FPB-0034"] = {"declared_value": min_updates}
        edits["FPB-0078"] = {"parameter_id": fv2.PARAM_OFI_NORM_ACTIVATION,
                             "parameter_name": fv2.PARAM_OFI_NORM_ACTIVATION,
                             "semantic_slot": "FIXTURE:F16.ofi_normalized_variant_activation",
                             "declared_value": lever_value}
        bundle = self.fixture_bundle("F16", edits)
        caps = {
            fv2.PARAM_OFI_WINDOW_UPDATES: self._mint(bundle, "PAR-056", "F16"),
            fv2.PARAM_OFI_WINDOW_MAX_AGE: self._mint(bundle, "PAR-057", "F16"),
            fv2.PARAM_OFI_MIN_UPDATES: self._mint(bundle, "PAR-058", "F16"),
        }
        if norm is not None:
            caps[fv2.PARAM_OFI_NORM_ACTIVATION] = self._mint(
                bundle, fv2.PARAM_OFI_NORM_ACTIVATION, "F16")
        return caps

    def mint_f17(self, min_depth=2, band=0, ttl=None):
        ttl_value = common.NOT_RATIFIED if ttl is None else ttl
        edits = {bid: {} for bid in _F17_ROWS}
        edits["RC3-FPB-003"] = {"parameter_id": fv2.PARAM_BOOK_TILT_MIN_DEPTH,
                                "parameter_name": fv2.PARAM_BOOK_TILT_MIN_DEPTH,
                                "declared_value": min_depth}
        edits["FPB-0035"] = {"parameter_id": fv2.PARAM_BOOK_TILT_BAND,
                             "parameter_name": fv2.PARAM_BOOK_TILT_BAND,
                             "declared_value": band}
        edits["FPB-0031"] = {"parameter_id": fv2.PARAM_BOOK_TILT_TTL,
                             "parameter_name": fv2.PARAM_BOOK_TILT_TTL,
                             "semantic_slot": "FIXTURE:F17.book_tilt_ttl",
                             "declared_value": ttl_value}
        bundle = self.fixture_bundle("F17", edits)
        caps = {
            fv2.PARAM_BOOK_TILT_MIN_DEPTH: self._mint(
                bundle, fv2.PARAM_BOOK_TILT_MIN_DEPTH, "F17"),
            fv2.PARAM_BOOK_TILT_BAND: self._mint(bundle, fv2.PARAM_BOOK_TILT_BAND, "F17"),
        }
        if ttl is not None:
            caps[fv2.PARAM_BOOK_TILT_TTL] = self._mint(bundle, fv2.PARAM_BOOK_TILT_TTL, "F17")
        return caps

    def mint_f00(self):
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
def f15caps(forge):
    return forge.mint_f15()


@pytest.fixture(scope="module")
def f16caps(forge):
    return forge.mint_f16(min_updates=1)


@pytest.fixture(scope="module")
def f17caps(forge):
    return forge.mint_f17(min_depth=2, band=0)


# --- envelope helpers ------------------------------------------------------------------------


def vtrade(tid, side, event_time, *, revision="rev-1"):
    return validate_trade({"trade_id": tid, "revision": revision,
                           "event_time_us": event_time, "aggressor_side": side})


def tobs(tid, side, event_time, price, qty, *, venue="BINANCE", instrument="BTCUSDT",
         meta="m1", src=None):
    return TradeObservation(
        trade=vtrade(tid, side, event_time), venue=venue, instrument=instrument,
        price_ticks=price, qty_steps=qty, metadata_revision=meta, source_event_id=src or tid)


def wclose(w_start, w_end, expected, watermark, src="wc"):
    return WindowClose(w_start=w_start, w_end=w_end, expected_trades=expected,
                       watermark_us=watermark, source_event_id=src)


def bupd(seq, *, pb, qb, pa, qa, event_time=None, eval_time=None, wm=True, src=None):
    et = seq * 10 if event_time is None else event_time
    ev = et if eval_time is None else eval_time
    return BookUpdateObservation(
        sequence=seq, event_time_us=et, eval_time_us=ev, best_bid_price_ticks=pb,
        best_bid_qty_steps=qb, best_ask_price_ticks=pa, best_ask_qty_steps=qa,
        watermark_complete=wm, source_event_id=src or f"u{seq}")


def snap(bids, asks, *, seq=1, event_time=0, eval_time=0, src=None):
    return BookSnapshotObservation(
        bid_levels=tuple(bids), ask_levels=tuple(asks), sequence=seq, event_time_us=event_time,
        eval_time_us=eval_time, source_event_id=src or f"s{seq}")


def features(events, version=None):
    out = [e for e in events if e.get("event_kind") == fv2.FEATURE]
    if version is not None:
        out = [e for e in out if e.get("formula_version") == version]
    return out


def abstentions(events):
    return [e for e in events if e.get("event_kind") == "NAMED_ABSTENTION"]


def reasons(events):
    return [e["reason_code"] for e in abstentions(events)]


def of_reason(events, reason_code):
    return [e for e in abstentions(events) if e["reason_code"] == reason_code]


# =================================================================================================
# The C.3 boundary — typed rejections BEFORE any state transition (per formula)
# =================================================================================================


class TestBoundary:
    def test_f15_hand_built_capability_forms_are_rejected(self, f15caps):
        state = f15_initial_state()
        snapshot = copy.deepcopy(state)
        env = tobs("t1", "BUY", 100, 1, 70)
        for forged in ({"value": 100}, 5, "100"):
            with pytest.raises(bindings.CapabilityForgeryError):
                evaluate_f15({fv2.PARAM_TFI_WINDOW_TRADES: forged,
                              fv2.PARAM_TFI_WINDOW_MAX_AGE: f15caps[fv2.PARAM_TFI_WINDOW_MAX_AGE],
                              fv2.PARAM_TFI_MIN_TRADES: f15caps[fv2.PARAM_TFI_MIN_TRADES]},
                             env, state)
        assert state == snapshot

    def test_f15_hand_built_dict_and_scalar_env_are_rejected(self, f15caps):
        state = f15_initial_state()
        snapshot = copy.deepcopy(state)
        with pytest.raises(EnvelopeRejected):
            evaluate_f15(f15caps, {"kind": "TRADE", "payload": {}}, state)
        with pytest.raises(EnvelopeRejected):
            evaluate_f15(f15caps, 42, state)
        assert state == snapshot

    def test_f15_subclassed_capability_and_env_refused_exact_type(self, f15caps):
        good = tobs("t1", "BUY", 100, 1, 70)

        class WidenedObs(TradeObservation):
            pass

        widened = WidenedObs(trade=good.trade, venue=good.venue, instrument=good.instrument,
                             price_ticks=good.price_ticks, qty_steps=good.qty_steps,
                             metadata_revision=good.metadata_revision,
                             source_event_id=good.source_event_id)
        with pytest.raises(EnvelopeRejected):
            evaluate_f15(f15caps, widened, f15_initial_state())

        class WidenedCap(bindings.VerifiedCapability):
            pass

        real = f15caps[fv2.PARAM_TFI_MIN_TRADES]
        forged = WidenedCap(
            parameter_id=real.parameter_id, formula_id=real.formula_id, value=real.value,
            source_bundle_digest=real.source_bundle_digest,
            signed_root_digest=real.signed_root_digest, repository=real.repository,
            environment=real.environment, valid_from=real.valid_from, valid_to=real.valid_to,
            signer_key_ids=real.signer_key_ids, _row_canonical=b"{}")
        caps = dict(f15caps)
        caps[fv2.PARAM_TFI_MIN_TRADES] = forged
        with pytest.raises(bindings.CapabilityForgeryError):
            evaluate_f15(caps, good, f15_initial_state())

    def test_f15_trade_observation_wrapping_a_raw_dict_trade_is_rejected(self, f15caps):
        duck = TradeObservation(
            trade={"trade_id": "t1", "aggressor_side": "BUY"}, venue="BINANCE",
            instrument="BTCUSDT", price_ticks=1, qty_steps=70, metadata_revision="m1",
            source_event_id="t1")
        with pytest.raises(EnvelopeRejected):
            evaluate_f15(f15caps, duck, f15_initial_state())

    def test_f15_wrong_formula_and_wrong_key_and_missing_and_unknown(self, forge, f15caps):
        f00 = forge.mint_f00()
        caps = dict(f15caps)
        caps[fv2.PARAM_TFI_MIN_TRADES] = f00
        with pytest.raises(bindings.CapabilityForgeryError):
            evaluate_f15(caps, tobs("t1", "BUY", 100, 1, 70), f15_initial_state())
        swapped = dict(f15caps)
        swapped[fv2.PARAM_TFI_MIN_TRADES] = f15caps[fv2.PARAM_TFI_WINDOW_TRADES]
        with pytest.raises(bindings.CapabilityForgeryError):
            evaluate_f15(swapped, tobs("t1", "BUY", 100, 1, 70), f15_initial_state())
        with pytest.raises(transition.MissingParameterError):
            evaluate_f15({}, tobs("t1", "BUY", 100, 1, 70), f15_initial_state())
        widened = dict(f15caps)
        widened["PAR-999"] = f15caps[fv2.PARAM_TFI_MIN_TRADES]
        with pytest.raises(RefuseConfig):
            evaluate_f15(widened, tobs("t1", "BUY", 100, 1, 70), f15_initial_state())

    def test_f15_state_must_be_the_exact_state_object(self, f15caps):
        with pytest.raises(EnvelopeRejected):
            evaluate_f15(f15caps, tobs("t1", "BUY", 100, 1, 70), 42)
        with pytest.raises(EnvelopeRejected):
            evaluate_f15(f15caps, tobs("t1", "BUY", 100, 1, 70), {"buffer": {}})

    def test_f16_hand_built_forms_are_rejected(self, f16caps):
        state = f16_initial_state()
        with pytest.raises(bindings.CapabilityForgeryError):
            evaluate_f16({fv2.PARAM_OFI_WINDOW_UPDATES: 5,
                          fv2.PARAM_OFI_WINDOW_MAX_AGE: f16caps[fv2.PARAM_OFI_WINDOW_MAX_AGE],
                          fv2.PARAM_OFI_MIN_UPDATES: f16caps[fv2.PARAM_OFI_MIN_UPDATES]},
                         bupd(0, pb=100, qb=5, pa=110, qa=7), state)
        with pytest.raises(EnvelopeRejected):
            evaluate_f16(f16caps, {"sequence": 0}, state)

    def test_f17_hand_built_forms_are_rejected(self, f17caps):
        state = f17_initial_state()
        with pytest.raises(bindings.CapabilityForgeryError):
            evaluate_f17({fv2.PARAM_BOOK_TILT_MIN_DEPTH: 5,
                          fv2.PARAM_BOOK_TILT_BAND: f17caps[fv2.PARAM_BOOK_TILT_BAND]},
                         snap([(1, 6)], [(2, 2)]), state)
        with pytest.raises(EnvelopeRejected):
            evaluate_f17(f17caps, {"bid_quote_depth": 600, "ask_quote_depth": 400}, state)

    def test_real_registry_refuses_to_mint_any_flow_capability(self, forge):
        for parameter_id, formula_id in (("PAR-052", "F15"), ("PAR-056", "F16"),
                                         ("PAR-059", "F17")):
            with pytest.raises(bindings.BlockedBindingIncomplete) as excinfo:
                transition.require_bundle(
                    forge.genuine_bundle(), parameter_id, formula_id=formula_id, ctx=forge.ctx)
            assert excinfo.value.formula_id == formula_id


# =================================================================================================
# R-F15 — flow.tfi.window.v2
# =================================================================================================


class TestF15:
    def test_t10_gv013_pair_reduced(self, f15caps):
        # (a) equal-price: buy atoms 70, sell atoms 30 -> TFI = +2/5 REDUCED.
        a = run_f15(f15caps, [
            tobs("b", "BUY", 100, 1, 70), tobs("s", "SELL", 200, 1, 30),
            wclose(0, 1000, 2, 1000)])
        (feat,) = features(a.events, fv2.F15_FORMULA_VERSION)
        assert feat["tfi"] == [2, 5]
        assert feat["buy_atoms"] == 70 and feat["sell_atoms"] == 30
        # (b) unequal-price: buy 70 steps @ 100 ticks = 7000, sell 30 steps @ 200 ticks = 6000
        #     -> TFI = 1000/13000 = +1/13 (a base-quantity computation would claim +2/5).
        b = run_f15(f15caps, [
            tobs("b", "BUY", 100, 100, 70), tobs("s", "SELL", 200, 200, 30),
            wclose(0, 1000, 2, 1000)])
        (featb,) = features(b.events, fv2.F15_FORMULA_VERSION)
        assert featb["tfi"] == [1, 13]
        assert featb["buy_atoms"] == 7000 and featb["sell_atoms"] == 6000

    def test_t1_all_buys_is_plus_one(self, f15caps):
        r = run_f15(f15caps, [tobs("b1", "BUY", 100, 1, 70), tobs("b2", "BUY", 200, 1, 30),
                              wclose(0, 1000, 2, 1000)])
        (feat,) = features(r.events, fv2.F15_FORMULA_VERSION)
        assert feat["tfi"] == [1, 1]

    def test_t2_all_sells_is_minus_one(self, f15caps):
        r = run_f15(f15caps, [tobs("s1", "SELL", 100, 1, 70), tobs("s2", "SELL", 200, 1, 30),
                              wclose(0, 1000, 2, 1000)])
        (feat,) = features(r.events, fv2.F15_FORMULA_VERSION)
        assert feat["tfi"] == [-1, 1]

    def test_t3_zero_denominator_is_a_named_null(self, f15caps):
        r = run_f15(f15caps, [tobs("z", "BUY", 100, 0, 5), wclose(0, 1000, 1, 1000)])
        assert features(r.events) == []
        assert reasons(r.events) == [fv2.F15_ZERO_DENOMINATOR]

    def test_t4_window_is_half_open_w_end_excluded(self, f15caps):
        # event at W_end-1 included, event at W_end excluded (half-open [W_start, W_end)).
        r = run_f15(f15caps, [
            tobs("in", "BUY", 999, 1, 50), tobs("out", "SELL", 1000, 1, 999),
            wclose(0, 1000, 1, 1000)])
        (feat,) = features(r.events, fv2.F15_FORMULA_VERSION)
        assert feat["trade_count"] == 1 and feat["tfi"] == [1, 1]

    def test_t5_arrival_order_is_irrelevant(self, f15caps):
        forward = run_f15(f15caps, [tobs("b", "BUY", 100, 100, 70),
                                    tobs("s", "SELL", 200, 200, 30), wclose(0, 1000, 2, 1000)])
        reverse = run_f15(f15caps, [tobs("s", "SELL", 200, 200, 30),
                                    tobs("b", "BUY", 100, 100, 70), wclose(0, 1000, 2, 1000)])
        assert (features(forward.events, fv2.F15_FORMULA_VERSION)[0]["tfi"]
                == features(reverse.events, fv2.F15_FORMULA_VERSION)[0]["tfi"] == [1, 13])

    def test_t6_duplicate_trade_id_ignored_regardless_of_adjacency(self, f15caps):
        r = run_f15(f15caps, [
            tobs("b", "BUY", 100, 1, 70), tobs("s", "SELL", 200, 1, 30),
            tobs("b", "BUY", 100, 1, 70),   # non-adjacent duplicate (same venue|instrument|id)
            wclose(0, 1000, 2, 1000)])
        (feat,) = features(r.events, fv2.F15_FORMULA_VERSION)
        assert feat["trade_count"] == 2 and feat["tfi"] == [2, 5]

    def test_t7_missing_aggressor_excluded_at_boundary_then_coverage_null(self, f15caps):
        # A missing/unknown flag never crosses validate_trade (excluded at the E01 boundary)...
        with pytest.raises(QuarantineInvalidTrade):
            validate_trade({"trade_id": "x", "revision": "rev-1", "event_time_us": 150})
        # ...so only 1 of the 2 expected trades is delivered -> coverage shortfall -> NULL{COVERAGE}.
        r = run_f15(f15caps, [tobs("b", "BUY", 100, 1, 70), wclose(0, 1000, 2, 1000)])
        assert features(r.events) == []
        assert reasons(r.events) == [fv2.F15_COVERAGE]

    def test_t8_mixed_metadata_revisions_is_a_named_null(self, f15caps):
        r = run_f15(f15caps, [
            tobs("b", "BUY", 100, 1, 70, meta="m1"),
            tobs("s", "SELL", 200, 1, 30, meta="m2"),
            wclose(0, 1000, 2, 1000)])
        assert features(r.events) == []
        assert reasons(r.events) == [fv2.F15_METADATA_REVISION_MIX]

    def test_t9_late_trade_emits_a_revision_original_immutable(self, f15caps):
        head = run_f15(f15caps, [
            tobs("b", "BUY", 100, 1, 70), tobs("s", "SELL", 200, 1, 30),
            wclose(0, 1000, 2, 1000)])
        (original,) = features(head.events, fv2.F15_FORMULA_VERSION)
        assert original["tfi"] == [2, 5]
        # A late buy trade whose event_time lands inside the already-emitted window.
        tail = run_f15(f15caps, [tobs("late", "BUY", 300, 1, 30)], initial=head.final_state)
        (rev,) = [e for e in tail.events if e["event_kind"] == fv2.TFI_REVISION]
        assert rev["superseded_revision_id"] == "0:1000#r1"
        assert rev["revision_id"] == "0:1000#r2"   # window_key is "0:1000"
        assert rev["late_trade_id"] == "late"
        assert rev["tfi"] == [7, 13]   # buy 70+30=100, sell 30 -> 70/130 = 7/13
        # The original FEATURE is never rewritten (append-only).
        full = list(head.events) + list(tail.events)
        assert canonical_json(original) in [canonical_json(e) for e in full]

    def test_t11_buy_sell_swap_negates_tfi(self, f15caps):
        base = run_f15(f15caps, [tobs("a", "BUY", 100, 100, 70),
                                 tobs("b", "SELL", 200, 200, 30), wclose(0, 1000, 2, 1000)])
        mirror = run_f15(f15caps, [tobs("a", "SELL", 100, 100, 70),
                                   tobs("b", "BUY", 200, 200, 30), wclose(0, 1000, 2, 1000)])
        base_tfi = features(base.events, fv2.F15_FORMULA_VERSION)[0]["tfi"]
        mirror_tfi = features(mirror.events, fv2.F15_FORMULA_VERSION)[0]["tfi"]
        assert base_tfi == [1, 13] and mirror_tfi == [-1, 13]

    def test_t12_int64_boundary_on_window_sums(self, forge):
        caps = forge.mint_f15(min_trades=1)
        top = 2 ** 63 - 1
        # A single buy trade whose atoms sit exactly at the int64 edge emits.
        ok = run_f15(caps, [tobs("b", "BUY", 100, top, 1), wclose(0, 1000, 1, 1000)])
        (feat,) = features(ok.events, fv2.F15_FORMULA_VERSION)
        assert feat["buy_atoms"] == top and feat["tfi"] == [1, 1]
        # A second buy atom of 1 pushes the window sum to 2**63 -> QUARANTINE_OVERFLOW.
        with pytest.raises(exact.QuarantineOverflow) as excinfo:
            run_f15(caps, [tobs("b", "BUY", 100, top, 1), tobs("c", "BUY", 150, 1, 1),
                           wclose(0, 1000, 2, 1000)])
        assert excinfo.value.formula_id == "F15"
        # A per-trade product beyond int64 quarantines at the atom boundary.
        with pytest.raises(exact.QuarantineOverflow):
            run_f15(caps, [tobs("b", "BUY", 100, 2 ** 62, 3), wclose(0, 1000, 1, 1000)])

    def test_watermark_pending_defers_emission(self, f15caps):
        r = run_f15(f15caps, [tobs("b", "BUY", 100, 1, 70), wclose(0, 1000, 1, 500)])
        assert features(r.events) == []
        assert reasons(r.events) == [fv2.F15_WATERMARK_PENDING]

    def test_insufficient_min_trades_is_a_named_null(self, forge):
        caps = forge.mint_f15(min_trades=2)
        r = run_f15(caps, [tobs("b", "BUY", 100, 1, 70), wclose(0, 1000, 1, 1000)])
        assert features(r.events) == []
        assert reasons(r.events) == [fv2.F15_INSUFFICIENT_COVERAGE]

    def test_bad_capability_faces_are_refuse_config(self, forge):
        for bad in (0, -3):
            caps = forge.mint_f15(min_trades=bad)
            with pytest.raises(RefuseConfig):
                evaluate_f15(caps, tobs("b", "BUY", 100, 1, 70), f15_initial_state())

    def test_restart_and_prefix_parity(self, f15caps):
        inputs = [tobs("b", "BUY", 100, 100, 70), tobs("s", "SELL", 200, 200, 30),
                  wclose(0, 1000, 2, 1000), tobs("late", "BUY", 300, 1, 30)]
        full = run_f15(f15caps, inputs)
        for cut in range(1, len(inputs)):
            head = run_f15(f15caps, inputs[:cut])
            tail = run_f15(f15caps, inputs[cut:], initial=head.final_state)
            assert list(head.events) + list(tail.events) == list(full.events)
            assert tail.final_state == full.final_state

    def test_exact_duplicate_envelope_is_deduped_by_the_fold(self, f15caps):
        wc = wclose(0, 1000, 1, 1000)
        r = run_f15(f15caps, [tobs("b", "BUY", 100, 1, 70), wc, wc])
        assert r.duplicate_count == 1

    def test_evaluate_never_mutates_the_callers_state(self, f15caps):
        state = run_f15(f15caps, [tobs("b", "BUY", 100, 1, 70)]).final_state
        snapshot = copy.deepcopy(state)
        evaluate_f15(f15caps, tobs("s", "SELL", 200, 1, 30), state)
        assert state == snapshot


def test_t9_revision_arithmetic_is_exact():
    # Independent check of the revised value used above: buy 70 + late buy 30 = 100, sell 30 ->
    # (100 - 30) / (100 + 30) = 70/130 = 7/13.
    assert exact.rational(70 + 30 - 30, 70 + 30 + 30) == (7, 13)


# =================================================================================================
# R-F16 — flow.ofi.best.v2 (+ flow.ofi.best_norm.v1, activation OFF)
# =================================================================================================

_DIRECTION_CASES = [
    # (bid_price, ask_price, expected e_n) with baseline Pb0=100/Pa0=110, Qb0=5/Qa0=7,
    # u1 Qb1=8/Qa1=9. Each hand-computed from the CKS event equation.
    ("bid_up_ask_up", 101, 111, 15),
    ("bid_up_ask_down", 101, 109, -1),
    ("bid_up_ask_same", 101, 110, 6),
    ("bid_down_ask_up", 99, 111, 2),
    ("bid_down_ask_down", 99, 109, -14),
    ("bid_down_ask_same", 99, 110, -7),
    ("bid_same_ask_up", 100, 111, 10),
    ("bid_same_ask_down", 100, 109, -6),
    ("bid_same_ask_same", 100, 110, 1),
]


class TestF16:
    @pytest.mark.parametrize("name,pb1,pa1,expected", _DIRECTION_CASES)
    def test_t1_to_t9_single_pair_direction_cases(self, f16caps, name, pb1, pa1, expected):
        r = run_f16(f16caps, [bupd(0, pb=100, qb=5, pa=110, qa=7),
                              bupd(1, pb=pb1, qb=8, pa=pa1, qa=9)])
        (feat,) = features(r.events, fv2.F16_FORMULA_VERSION)
        assert feat["ofi_value"] == expected, name
        assert feat["window_size"] == 1

    def test_t17_golden_gv_f16_01_ofi_is_plus_seven(self, forge):
        caps = forge.mint_f16(min_updates=3)
        r = run_f16(caps, [
            bupd(0, pb=100, qb=5, pa=101, qa=7),
            bupd(1, pb=100, qb=8, pa=101, qa=7),   # e1 = +3
            bupd(2, pb=99, qb=4, pa=101, qa=6),    # e2 = -7
            bupd(3, pb=99, qb=9, pa=102, qa=6)])   # e3 = +11
        (feat,) = features(r.events, fv2.F16_FORMULA_VERSION)
        assert feat["ofi_value"] == 7 and feat["window_size"] == 3

    def test_gv_f16_01_normalized_variant_when_lever_live(self, forge):
        caps = forge.mint_f16(min_updates=3, norm=fv2.NORM_ACTIVATION_LIVE)
        r = run_f16(caps, [
            bupd(0, pb=100, qb=5, pa=101, qa=7),
            bupd(1, pb=100, qb=8, pa=101, qa=7),
            bupd(2, pb=99, qb=4, pa=101, qa=6),
            bupd(3, pb=99, qb=9, pa=102, qa=6)])
        (norm,) = features(r.events, fv2.F16_NORM_FORMULA_VERSION)
        assert norm["ofi_norm"] == [21, 20]     # OFI 7 / D-bar (20/3) = 21/20
        assert norm["mean_depth"] == [20, 3]
        assert norm["ofi_value"] == 7

    def test_t19_lever_off_never_emits_the_norm_identity(self, forge):
        for caps in (forge.mint_f16(min_updates=3),                       # lever absent -> OFF
                     forge.mint_f16(min_updates=3, norm=fv2.NORM_ACTIVATION_OFF)):
            r = run_f16(caps, [
                bupd(0, pb=100, qb=5, pa=101, qa=7),
                bupd(1, pb=100, qb=8, pa=101, qa=7),
                bupd(2, pb=99, qb=4, pa=101, qa=6),
                bupd(3, pb=99, qb=9, pa=102, qa=6)])
            assert features(r.events, fv2.F16_NORM_FORMULA_VERSION) == []
            assert len(features(r.events, fv2.F16_FORMULA_VERSION)) == 1

    def test_retired_boolean_lever_value_is_refuse_config(self, forge):
        caps = forge.mint_f16(min_updates=1, norm="false")
        with pytest.raises(RefuseConfig):
            evaluate_f16(caps, bupd(0, pb=100, qb=5, pa=110, qa=7), f16_initial_state())

    def test_t10_crossed_book_is_invalid_pair_chain_broken(self, f16caps):
        r = run_f16(f16caps, [bupd(0, pb=100, qb=5, pa=110, qa=7),
                              bupd(1, pb=120, qb=5, pa=110, qa=7)])  # Pb >= Pa -> crossed
        assert features(r.events) == []
        (ab,) = of_reason(r.events, fv2.F16_INVALID_UPDATE)
        assert ab["refs"]["invalid_reason"] == "crossed_or_locked_book"
        assert r.final_state["prev_valid"] is None  # chain broken

    def test_t11_locked_book_is_invalid(self, f16caps):
        r = run_f16(f16caps, [bupd(0, pb=100, qb=5, pa=110, qa=7),
                              bupd(1, pb=110, qb=5, pa=110, qa=7)])  # Pb == Pa -> locked
        (ab,) = of_reason(r.events, fv2.F16_INVALID_UPDATE)
        assert ab["refs"]["invalid_reason"] == "crossed_or_locked_book"

    def test_t12_zero_quantity_side_is_invalid(self, f16caps):
        r = run_f16(f16caps, [bupd(0, pb=100, qb=5, pa=110, qa=7),
                              bupd(1, pb=100, qb=0, pa=110, qa=7)])
        (ab,) = of_reason(r.events, fv2.F16_INVALID_UPDATE)
        assert ab["refs"]["invalid_reason"] == "non_positive_bid_qty"

    def test_invalid_update_breaks_the_chain_but_the_window_continues(self, forge):
        caps = forge.mint_f16(min_updates=1)
        r = run_f16(caps, [
            bupd(0, pb=100, qb=5, pa=110, qa=7),
            bupd(1, pb=101, qb=8, pa=110, qa=7),   # valid pair -> e1, window=[e1]
            bupd(2, pb=120, qb=5, pa=110, qa=7),   # crossed -> chain break, window UNCHANGED
            bupd(3, pb=100, qb=5, pa=110, qa=7),   # new baseline (no e across the invalid)
            bupd(4, pb=101, qb=8, pa=110, qa=7)])  # valid pair vs u3 -> e4, window=[e1, e4]
        assert r.final_state["window"] and len(r.final_state["window"]) == 2  # window continued

    def test_t13_sequence_gap_nulls_the_whole_window_and_resets(self, forge):
        caps = forge.mint_f16(min_updates=1)
        r = run_f16(caps, [
            bupd(0, pb=100, qb=5, pa=110, qa=7),
            bupd(1, pb=101, qb=8, pa=110, qa=7),   # window=[e1]
            bupd(3, pb=102, qb=8, pa=110, qa=7)])  # seq 2 skipped -> GAP
        assert fv2.F16_SEQUENCE_GAP in reasons(r.events)
        assert r.final_state["window"] == []       # whole window void + reset

    def test_t14_duplicate_seq_is_ignored_count_unchanged(self, forge):
        caps = forge.mint_f16(min_updates=1)
        head = run_f16(caps, [bupd(0, pb=100, qb=5, pa=110, qa=7),
                              bupd(1, pb=101, qb=8, pa=110, qa=7)])
        before = head.final_state
        dup = run_f16(caps, [bupd(1, pb=999, qb=9, pa=1000, qa=9)], initial=before)
        assert dup.events == ()
        assert dup.final_state == before          # ignored: count and state unchanged

    def test_t15_stale_is_a_named_null(self, forge):
        caps = forge.mint_f16(min_updates=1, max_age=1000)   # 1000 ms == 1_000_000 us
        r = run_f16(caps, [
            bupd(0, pb=100, qb=5, pa=110, qa=7, event_time=0, eval_time=0),
            bupd(1, pb=101, qb=8, pa=110, qa=7, event_time=0, eval_time=2_000_000)])
        assert features(r.events) == []
        assert of_reason(r.events, fv2.F16_STALE)   # the u1 pair is fresh-checked and stale

    def test_t16_min_updates_boundary(self, forge):
        caps = forge.mint_f16(min_updates=2)
        r = run_f16(caps, [
            bupd(0, pb=100, qb=5, pa=110, qa=7),   # baseline, window 0 < 2 -> insufficient
            bupd(1, pb=101, qb=8, pa=110, qa=7),   # window=1 < 2 -> insufficient
            bupd(2, pb=102, qb=8, pa=110, qa=7)])  # window=2 >= 2 -> emit
        assert len(of_reason(r.events, fv2.F16_INSUFFICIENT_COVERAGE)) == 2
        assert len(features(r.events, fv2.F16_FORMULA_VERSION)) == 1

    def test_watermark_incomplete_suppresses_emission_but_state_advances(self, forge):
        caps = forge.mint_f16(min_updates=1)
        r = run_f16(caps, [bupd(0, pb=100, qb=5, pa=110, qa=7),
                           bupd(1, pb=101, qb=8, pa=110, qa=7, wm=False)])
        # u1 has window>=1 and is fresh but watermark-incomplete: silent non-emission (no feature,
        # no STALE); only the u0 baseline insufficiency is present.
        assert features(r.events) == []
        assert of_reason(r.events, fv2.F16_STALE) == []
        assert len(r.final_state["window"]) == 1  # the series still advanced

    def test_t18_mirror_exchanging_bid_ask_roles_negates_ofi(self, forge):
        caps = forge.mint_f16(min_updates=3)
        straight = [
            bupd(0, pb=100, qb=5, pa=101, qa=7),
            bupd(1, pb=100, qb=8, pa=101, qa=7),
            bupd(2, pb=99, qb=4, pa=101, qa=6),
            bupd(3, pb=99, qb=9, pa=102, qa=6)]

        def mirror(u):
            # RC3 mirror: price -> -price, bid <-> ask (qty swaps) — keeps the book uncrossed.
            return dataclasses.replace(
                u, best_bid_price_ticks=-u.best_ask_price_ticks,
                best_bid_qty_steps=u.best_ask_qty_steps,
                best_ask_price_ticks=-u.best_bid_price_ticks,
                best_ask_qty_steps=u.best_bid_qty_steps)

        s = run_f16(caps, straight)
        m = run_f16(caps, [mirror(u) for u in straight])
        assert features(s.events, fv2.F16_FORMULA_VERSION)[-1]["ofi_value"] == 7
        assert features(m.events, fv2.F16_FORMULA_VERSION)[-1]["ofi_value"] == -7

    def test_t20_int64_product_boundary(self, f16caps):
        # Both operands in int64 range, but price_ticks x qty_steps overflows (2**32 * 2**32).
        with pytest.raises(exact.QuarantineOverflow) as excinfo:
            evaluate_f16(f16caps, bupd(0, pb=2 ** 32, qb=2 ** 32, pa=2 ** 32 + 1, qa=1),
                         f16_initial_state())
        assert excinfo.value.formula_id == "F16"

    def test_restart_and_prefix_parity(self, forge):
        caps = forge.mint_f16(min_updates=1)
        inputs = [
            bupd(0, pb=100, qb=5, pa=110, qa=7),
            bupd(1, pb=101, qb=8, pa=110, qa=7),
            bupd(2, pb=120, qb=5, pa=110, qa=7),   # crossed
            bupd(3, pb=100, qb=5, pa=110, qa=7),
            bupd(5, pb=102, qb=8, pa=110, qa=7)]   # gap
        full = run_f16(caps, inputs)
        for cut in range(1, len(inputs)):
            head = run_f16(caps, inputs[:cut])
            tail = run_f16(caps, inputs[cut:], initial=head.final_state)
            assert list(head.events) + list(tail.events) == list(full.events)
            assert tail.final_state == full.final_state


# =================================================================================================
# R-F17 — flow.book_tilt.band.v2
# =================================================================================================


class TestF17:
    def test_gv014_reduced_tilt_one_fifth(self, f17caps):
        r = run_f17(f17caps, [snap([(1, 6)], [(2, 2)])])  # bid depth 6, ask depth 4 -> 1/5
        (feat,) = features(r.events, fv2.F17_FORMULA_VERSION)
        assert feat["tilt"] == [1, 5]
        assert feat["bid_quote_depth"] == 6 and feat["ask_quote_depth"] == 4

    def test_t1_balanced_is_zero(self, f17caps):
        r = run_f17(f17caps, [snap([(1, 5)], [(5, 1)])])  # 5 and 5
        (feat,) = features(r.events, fv2.F17_FORMULA_VERSION)
        assert feat["tilt"] == [0, 1]

    def test_t2_all_bid_is_plus_one_all_ask_is_minus_one(self, f17caps):
        allbid = run_f17(f17caps, [snap([(1, 6)], [])])
        assert features(allbid.events, fv2.F17_FORMULA_VERSION)[0]["tilt"] == [1, 1]
        allask = run_f17(f17caps, [snap([], [(2, 4)])])
        assert features(allask.events, fv2.F17_FORMULA_VERSION)[0]["tilt"] == [-1, 1]

    def test_t3_depth_floor_boundary(self, forge):
        caps = forge.mint_f17(min_depth=10, band=0)
        at_min = run_f17(caps, [snap([(1, 6)], [(2, 2)])])            # D = 6 + 4 = 10 == min
        assert features(at_min.events, fv2.F17_FORMULA_VERSION)[0]["tilt"] == [1, 5]
        below = run_f17(caps, [snap([(1, 5)], [(2, 2)])])            # D = 5 + 4 = 9 < min
        assert features(below.events) == []
        assert reasons(below.events) == [fv2.F17_INSUFFICIENT_DEPTH]

    def test_t4_min_zero_or_negative_config_is_refuse_config(self, forge):
        for bad in (0, -1):
            caps = forge.mint_f17(min_depth=bad, band=0)
            with pytest.raises(RefuseConfig) as excinfo:
                evaluate_f17(caps, snap([(1, 6)], [(2, 2)]), f17_initial_state())
            assert excinfo.value.reason == fv2.REFUSE_CONFIG

    def test_t5_band_edge_is_inclusive(self, forge):
        caps = forge.mint_f17(min_depth=2, band=5)
        # best_bid = 100; level at 95 is |95-100|=5 <= 5 (included); level at 94 is excluded.
        r = run_f17(caps, [snap([(100, 1), (95, 1), (94, 1)], [(300, 1)])])
        (feat,) = features(r.events, fv2.F17_FORMULA_VERSION)
        assert feat["bid_quote_depth"] == 100 + 95   # 94 excluded (beyond the band)

    def test_t6_crossed_book_is_a_named_null(self, f17caps):
        r = run_f17(f17caps, [snap([(100, 1)], [(99, 1)])])   # best_bid 100 >= best_ask 99
        assert features(r.events) == []
        assert reasons(r.events) == [fv2.F17_CROSSED_BOOK]

    def test_t7_stale_is_a_named_null(self, forge):
        caps = forge.mint_f17(min_depth=2, band=0, ttl=1000)
        r = run_f17(caps, [snap([(1, 6)], [(2, 2)], event_time=0, eval_time=2000)])
        assert features(r.events) == []
        assert reasons(r.events) == [fv2.F17_STALE]

    def test_t8_caller_supplied_sums_path_does_not_exist(self, f17caps):
        with pytest.raises(EnvelopeRejected):
            evaluate_f17(f17caps, {"bid_quote_depth_ticks_steps": 600,
                                   "ask_quote_depth_ticks_steps": 400}, f17_initial_state())

    def test_t9_bid_ask_depth_swap_negates_tilt(self, f17caps):
        base = run_f17(f17caps, [snap([(1, 6)], [(2, 2)])])          # 6 vs 4 -> +1/5
        swapped = run_f17(f17caps, [snap([(1, 4)], [(2, 3)])])       # 4 vs 6 -> -1/5
        assert features(base.events, fv2.F17_FORMULA_VERSION)[0]["tilt"] == [1, 5]
        assert features(swapped.events, fv2.F17_FORMULA_VERSION)[0]["tilt"] == [-1, 5]

    def test_t10_restart_and_prefix_parity(self, f17caps):
        inputs = [snap([(1, 6)], [(2, 2)], seq=1), snap([(1, 5)], [(2, 3)], seq=2),
                  snap([(100, 1)], [(99, 1)], seq=3), snap([(1, 6)], [], seq=4)]
        full = run_f17(f17caps, inputs)
        for cut in range(1, len(inputs)):
            head = run_f17(f17caps, inputs[:cut])
            tail = run_f17(f17caps, inputs[cut:], initial=head.final_state)
            assert list(head.events) + list(tail.events) == list(full.events)
            assert tail.final_state == full.final_state

    def test_not_ratified_min_depth_is_safe_hold(self, forge):
        caps = forge.mint_f17(min_depth=common.NOT_RATIFIED, band=0)
        state = f17_initial_state()
        r = run_f17(caps, [snap([(1, 6)], [(2, 2)])])
        assert features(r.events) == []
        assert reasons(r.events) == [fv2.F17_UNAVAILABLE_MIN_DEPTH]
        # SAFE_HOLD: zero state mutation.
        result = evaluate_f17(caps, snap([(1, 6)], [(2, 2)]), state)
        assert result.state == state

    def test_empty_book_is_a_named_null(self, f17caps):
        r = run_f17(f17caps, [snap([], [])])
        assert reasons(r.events) == [fv2.F17_EMPTY_BOOK]

    def test_int64_level_product_boundary(self, f17caps):
        # A banded level whose price_ticks x qty_steps overflows int64 (2**32 * 2**32) quarantines.
        with pytest.raises(exact.QuarantineOverflow) as excinfo:
            evaluate_f17(f17caps, snap([(2 ** 32, 2 ** 32)], [(2 ** 32 + 5, 1)]),
                         f17_initial_state())
        assert excinfo.value.formula_id == "F17"

    def test_book_sequence_regression_is_refused(self, f17caps):
        head = run_f17(f17caps, [snap([(1, 6)], [(2, 2)], seq=5)])
        with pytest.raises(common.StructureLawError):
            run_f17(f17caps, [snap([(1, 6)], [(2, 2)], seq=5)], initial=head.final_state)


# =================================================================================================
# Version discipline: the proposed depth-floor value is never hardcoded as an executable constant
# =================================================================================================


def test_proposed_min_depth_value_is_never_hardcoded_active():
    source = pathlib.Path(fv2.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and not isinstance(node.value, bool):
            if isinstance(node.value, int):
                assert node.value != 100, "the proposed BOOK_TILT_MIN_DEPTH value is hardcoded"
