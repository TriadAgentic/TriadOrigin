"""B01C-CON-05 — exact digest grammar, not shape/length.

A 64-character string is not a digest. Uppercase hex, non-hex characters, short/padded strings,
and the all-zero placeholder are refused everywhere a real sha256 identity is required.
"""

from __future__ import annotations

import copy
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from triad_origin import contracts, health  # noqa: E402
from triad_origin.canonical import is_sha256_hex  # noqa: E402

GOLDEN = ROOT / "contracts" / "golden"

GOOD = "a" * 64
UPPER = "A" * 64
NONHEX = "g" * 64
SHORT = "a" * 63
ZERO = "0" * 64


class TestPredicate:
    @pytest.mark.parametrize("value", [GOOD, "0123456789abcdef" * 4, ZERO])
    def test_lowercase_hex64_accepts(self, value):
        assert is_sha256_hex(value)

    @pytest.mark.parametrize("value", [UPPER, NONHEX, SHORT, "a" * 65, "", 0, None, b"a" * 64])
    def test_everything_else_refuses(self, value):
        assert not is_sha256_hex(value)


class TestGateReceiptDigests:
    def _receipt(self, digest: str) -> dict:
        event = json.loads(
            (GOLDEN / "triad.gate_receipt.v2" / "valid.json").read_text(encoding="utf-8"))
        event["payload"]["producer_digests"] = {"contract_manifest": digest}
        return event

    def test_lowercase_hex_passes_semantic_law(self):
        # The semantic law accepts a proper digest (schema validation runs first under jsonschema).
        contracts._semantic_gate_receipt_v2(self._receipt(GOOD))

    @pytest.mark.parametrize("bad", [UPPER, NONHEX, SHORT, ZERO])
    def test_shape_only_digest_refused(self, bad):
        with pytest.raises(contracts.ContractError, match="GATE_PASS_MISSING_OR_PLACEHOLDER_DIGESTS"):
            contracts._semantic_gate_receipt_v2(self._receipt(bad))


class TestAttestationDigests:
    def _build(self, digest: str):
        return health.build_engine_attestation(
            contract_manifest_sha256=digest, config_bundle_sha256=digest,
            build_commit="f" * 40, artifact_sha256=digest,
            parameter_set_id="dark-parameters", parameter_digest=digest,
            instrument_map_digest=digest, universe_digest=digest,
            activation_manifest_id="not-armed", producer_epoch="0",
            environment="offline", host_identity="test-host",
            startup_receipt_id="startup-test")

    def test_lowercase_hex_builds(self):
        payload = self._build("1" * 64)
        assert payload["universe_digest"] == "1" * 64

    @pytest.mark.parametrize("bad", [UPPER, NONHEX, ZERO])
    def test_shape_only_or_placeholder_digest_refused(self, bad):
        with pytest.raises(contracts.ContractError):
            self._build(bad)
