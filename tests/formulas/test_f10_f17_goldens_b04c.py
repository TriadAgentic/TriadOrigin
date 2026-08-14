"""B04C milestone golden home — the F10..F17 repaired-set headline vectors.

This file is the B04C acceptance profile's REQUIRED ARTIFACT
(``docs/control/closure/closure_semantics.v1.json`` →
``tests/formulas/test_f10_f17_goldens_b04c.py``). It executes the Part D §D.3 / §D.6 goldens that
the B04C repairs introduce or replace, on the repaired v2 surfaces, through the REAL C.1 sealed
capability acceptance:

* **GV-013 (F15, §D.3):** the unit pair — (a) equal-price buy 70 / sell 30 atoms → TFI ``+2/5``;
  (b) buy 70 steps @ 100 ticks = 7000 vs sell 30 steps @ 200 ticks = 6000 → TFI ``+1/13`` (a
  base-quantity computation would claim ``+2/5``; vector (b) makes the unit bug permanently
  detectable). Output reduced.
* **GV-F16-01 (F16, §D.6):** OFI = ``+7`` over the four-update tape; the normalized identity
  ``flow.ofi.best_norm.v1`` is a SEPARATE identity behind a default-OFF lever and must NEVER emit
  while the lever is OFF.

The other B04C goldens have their authoritative homes in the structure batteries (recorded in
``docs/control/formula_repair_overlay.v1.json``): GV-009 (F10) →
``tests/structures/test_fvg_registry_v3.py``; GV-011 (F13) →
``tests/structures/test_excursion_reclaim_v2.py``; GV-010 (F11) →
``tests/structures/test_displacement.py`` + the e2e ``structure_flow_walk``; GV-F12-01 (F12) →
``tests/structures/test_order_block_v2.py``. GV-013 + GV-F16-01 are re-walked here (and in the
e2e ``b04c_flow_goldens`` stage) because they are the spec's headline detectability traps.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import bindings, transition  # noqa: E402
from triad_origin.canonical import canonical_json, sha256_hex  # noqa: E402
from triad_origin.e01_interface import validate_trade  # noqa: E402
from triad_origin.structures import flow_atoms_v2 as fv2  # noqa: E402
from triad_origin.structures.flow_atoms_v2 import (  # noqa: E402
    BookUpdateObservation,
    TradeObservation,
    WindowClose,
    run_f15,
    run_f16,
)

OWNER_KID = "k-owner-b04c-goldens"
REPOSITORY = "TriadOrigin"
ENVIRONMENT = "OFF"
NOW_US = 2_000_000


class _Forge:
    """Real Ed25519 through the real C.1 acceptance; SELF_TEST fixture surgery flips the
    requested formula's rows ACTIVE. The genuine registry leaves them BLOCKED (honest-dark)."""

    def __init__(self) -> None:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey, Ed25519PublicKey)

        self._private = Ed25519PrivateKey.generate()
        pub_hex = self._private.public_key().public_bytes_raw().hex()
        self.trust = {OWNER_KID: {
            "key_id": OWNER_KID, "identity": "b04c-goldens@triad-origin",
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
            trust=self.trust, trust_registry_bytes=self.trust_bytes, now_us=NOW_US,
            process_scope={"repository": REPOSITORY, "environment": ENVIRONMENT},
            verify_fn=_verify)
        self.registry = bindings.load_registry()
        self._base_rows = self.registry.rows()
        self._base_coverage = bindings.derive_formula_coverage(self.registry)

    @staticmethod
    def _resign(row: dict) -> dict:
        unsigned = {k: v for k, v in row.items() if k != "binding_digest"}
        row["binding_digest"] = sha256_hex(canonical_json(unsigned))
        return row

    def _sign(self, unsigned):
        signing = bindings.sealed_bundle_signing_bytes(
            canonical_root_digest=unsigned.canonical_root_digest, scope=unsigned.scope,
            valid_from=unsigned.valid_from, valid_to=unsigned.valid_to)
        return dataclasses.replace(unsigned, signatures=[
            {"key_id": OWNER_KID, "signature_hex": self._private.sign(signing).hex()}])

    def bundle(self, formula_id: str, edits: dict):
        rows = [dict(r) for r in self._base_rows]
        coverage = dict(self._base_coverage)
        for row in rows:
            update = edits.get(row["binding_id"])
            if update is None:
                continue
            row.update(update)
            row["status"] = "ACTIVE"
            coverage[row["formula_id"]] = "ACTIVE"
            self._resign(row)
        root = bindings.canonical_rows_digest(rows)
        unsigned = bindings.SealedParameterBundle(
            schema_version=bindings.SEALED_SCHEMA_VERSION,
            scope={"repository": REPOSITORY, "environment": ENVIRONMENT},
            rows=rows, canonical_root_digest=root, trust_registry_digest=self.trust_digest,
            signer_set=[OWNER_KID], signatures=[], valid_from=1_000_000, valid_to=9_000_000,
            formula_coverage=coverage,
            row_preimage_digests=sorted(sha256_hex(canonical_json(r)) for r in rows))
        return self._sign(unsigned)


@pytest.fixture(scope="module")
def forge():
    bindings._reset_trust_registry_pin_for_tests()
    bindings._reset_acceptance_memo_for_tests()
    f = _Forge()
    bindings.pin_trust_registry_digest(f.trust_digest)
    yield f
    bindings._reset_trust_registry_pin_for_tests()
    bindings._reset_acceptance_memo_for_tests()


@pytest.fixture(scope="module")
def f15caps(forge):
    b = forge.bundle("F15", {
        "FPB-0026": {"declared_value": 100}, "FPB-0027": {"declared_value": 2000},
        "FPB-0028": {"declared_value": 1}, "FPB-0029": {}, "FPB-0077": {}})
    return {
        fv2.PARAM_TFI_WINDOW_TRADES: transition.require_bundle(b, "PAR-052", formula_id="F15", ctx=forge.ctx),
        fv2.PARAM_TFI_WINDOW_MAX_AGE: transition.require_bundle(b, "PAR-053", formula_id="F15", ctx=forge.ctx),
        fv2.PARAM_TFI_MIN_TRADES: transition.require_bundle(b, "PAR-054", formula_id="F15", ctx=forge.ctx),
    }


@pytest.fixture(scope="module")
def f16caps(forge):
    b = forge.bundle("F16", {
        "FPB-0030": {}, "FPB-0032": {"declared_value": 100},
        "FPB-0033": {"declared_value": 1000}, "FPB-0034": {"declared_value": 3},
        "FPB-0078": {"parameter_id": fv2.PARAM_OFI_NORM_ACTIVATION,
                     "parameter_name": fv2.PARAM_OFI_NORM_ACTIVATION,
                     "semantic_slot": "B04C:F16.ofi_normalized_variant_activation",
                     "declared_value": fv2.NORM_ACTIVATION_OFF}})
    return {
        fv2.PARAM_OFI_WINDOW_UPDATES: transition.require_bundle(b, "PAR-056", formula_id="F16", ctx=forge.ctx),
        fv2.PARAM_OFI_WINDOW_MAX_AGE: transition.require_bundle(b, "PAR-057", formula_id="F16", ctx=forge.ctx),
        fv2.PARAM_OFI_MIN_UPDATES: transition.require_bundle(b, "PAR-058", formula_id="F16", ctx=forge.ctx),
    }


def _tobs(tid, side, event_time, price, qty):
    return TradeObservation(
        trade=validate_trade({"trade_id": tid, "revision": "rev-1",
                              "event_time_us": event_time, "aggressor_side": side}),
        venue="BINANCE", instrument="BTCUSDT", price_ticks=price, qty_steps=qty,
        metadata_revision="m1", source_event_id=tid)


def _wclose():
    return WindowClose(w_start=0, w_end=1000, expected_trades=2, watermark_us=1000,
                       source_event_id="wc")


def _bupd(seq, pb, qb, pa, qa):
    return BookUpdateObservation(
        sequence=seq, event_time_us=seq * 10, eval_time_us=seq * 10,
        best_bid_price_ticks=pb, best_bid_qty_steps=qb, best_ask_price_ticks=pa,
        best_ask_qty_steps=qa, watermark_complete=True, source_event_id=f"u{seq}")


def _f15_feature(run):
    feats = [e for e in run.events
             if e.get("formula_version") == fv2.F15_FORMULA_VERSION
             and e.get("event_kind") == "FEATURE"]
    assert len(feats) == 1, f"expected one F15 feature, got {feats!r}"
    return feats[0]


class TestGV013UnitPair:
    def test_a_equal_price_tfi_is_plus_two_fifths_reduced(self, f15caps) -> None:
        feat = _f15_feature(run_f15(f15caps, [
            _tobs("b", "BUY", 100, 1, 70), _tobs("s", "SELL", 200, 1, 30), _wclose()]))
        assert feat["tfi"] == [2, 5]
        assert feat["buy_atoms"] == 70 and feat["sell_atoms"] == 30

    def test_b_unequal_price_tfi_is_plus_one_thirteenth_the_unit_bug_trap(self, f15caps) -> None:
        # A base-quantity computation would claim +2/5 here; the unit law makes it +1/13.
        feat = _f15_feature(run_f15(f15caps, [
            _tobs("b", "BUY", 100, 100, 70), _tobs("s", "SELL", 200, 200, 30), _wclose()]))
        assert feat["tfi"] == [1, 13]
        assert feat["buy_atoms"] == 7000 and feat["sell_atoms"] == 6000


class TestGVF1601:
    def test_ofi_is_plus_seven(self, f16caps) -> None:
        run = run_f16(f16caps, [
            _bupd(0, 100, 5, 101, 7), _bupd(1, 100, 8, 101, 7),   # e1 = +3
            _bupd(2, 99, 4, 101, 6), _bupd(3, 99, 9, 102, 6)])    # e2 = -7, e3 = +11
        feats = [e for e in run.events
                 if e.get("formula_version") == fv2.F16_FORMULA_VERSION
                 and e.get("event_kind") == "FEATURE"]
        assert len(feats) == 1 and feats[0]["ofi_value"] == 7 and feats[0]["window_size"] == 3

    def test_normalized_identity_never_emits_with_the_lever_off(self, f16caps) -> None:
        run = run_f16(f16caps, [
            _bupd(0, 100, 5, 101, 7), _bupd(1, 100, 8, 101, 7),
            _bupd(2, 99, 4, 101, 6), _bupd(3, 99, 9, 102, 6)])
        norm = [e for e in run.events
                if e.get("formula_version") == fv2.F16_NORM_FORMULA_VERSION]
        assert norm == [], f"the normalized identity emitted with the lever OFF: {norm!r}"


class TestHonestDarkOnTheGenuineRegistry:
    def test_the_unedited_registry_mints_no_f15_capability(self, forge) -> None:
        genuine = forge._sign(bindings.build_sealed_bundle(
            forge.registry, repository=REPOSITORY, environment=ENVIRONMENT,
            valid_from=1_000_000, valid_to=9_000_000,
            trust_registry_digest=forge.trust_digest, signer_set=[OWNER_KID]))
        with pytest.raises(bindings.BlockedBindingIncomplete):
            transition.require_bundle(genuine, "PAR-052", formula_id="F15", ctx=forge.ctx)
